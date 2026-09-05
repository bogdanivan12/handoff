import uuid

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _create_feature(key_prefix: str | None = None) -> tuple[str, str]:
    product = client.post(
        "/products", json={"name": "Handoff", "key_prefix": key_prefix or uuid.uuid4().hex[:8].upper()}
    ).json()
    initiative = client.post(
        "/initiatives", json={"product_id": product["id"], "name": "Core"}
    ).json()
    epic = client.post("/epics", json={"initiative_id": initiative["id"], "name": "Auth"}).json()
    feature = client.post("/features", json={"epic_id": epic["id"], "name": "Login"}).json()
    return feature["id"], product["id"]


def test_create_and_list_feature_dependency(db_session):
    feature_a, _ = _create_feature()
    feature_b, _ = _create_feature()

    response = client.post(
        f"/features/{feature_a}/dependencies", json={"depends_on_feature_id": feature_b}
    )
    assert response.status_code == 201
    body = response.json()
    assert body["feature_id"] == feature_a
    assert body["depends_on_feature"]["id"] == feature_b

    response = client.get(f"/features/{feature_a}/dependencies")
    assert response.status_code == 200
    assert len(response.json()) == 1


def test_create_feature_dependency_rejects_self_reference(db_session):
    feature_a, _ = _create_feature()

    response = client.post(
        f"/features/{feature_a}/dependencies", json={"depends_on_feature_id": feature_a}
    )
    assert response.status_code == 400


def test_create_feature_dependency_rejects_missing_feature(db_session):
    feature_a, _ = _create_feature()

    response = client.post(
        f"/features/{feature_a}/dependencies",
        json={"depends_on_feature_id": "00000000-0000-0000-0000-000000000000"},
    )
    assert response.status_code == 404


def test_create_feature_dependency_rejects_missing_owner_feature(db_session):
    feature_b, _ = _create_feature()

    response = client.post(
        "/features/00000000-0000-0000-0000-000000000000/dependencies",
        json={"depends_on_feature_id": feature_b},
    )
    assert response.status_code == 404


def test_delete_feature_dependency_rejects_wrong_feature(db_session):
    feature_a, _ = _create_feature()
    feature_b, _ = _create_feature()
    feature_c, _ = _create_feature()

    response = client.post(
        f"/features/{feature_a}/dependencies", json={"depends_on_feature_id": feature_b}
    )
    dependency_id = response.json()["id"]

    response = client.delete(f"/features/{feature_c}/dependencies/{dependency_id}")
    assert response.status_code == 404


def test_delete_feature_dependency(db_session):
    feature_a, _ = _create_feature()
    feature_b, _ = _create_feature()

    response = client.post(
        f"/features/{feature_a}/dependencies", json={"depends_on_feature_id": feature_b}
    )
    dependency_id = response.json()["id"]

    response = client.delete(f"/features/{feature_a}/dependencies/{dependency_id}")
    assert response.status_code == 204

    response = client.get(f"/features/{feature_a}/dependencies")
    assert response.json() == []


def test_list_features_by_product(db_session):
    key_prefix = uuid.uuid4().hex[:8].upper()
    product = client.post("/products", json={"name": "Handoff", "key_prefix": key_prefix}).json()
    initiative = client.post(
        "/initiatives", json={"product_id": product["id"], "name": "Core"}
    ).json()
    epic = client.post("/epics", json={"initiative_id": initiative["id"], "name": "Auth"}).json()
    client.post("/features", json={"epic_id": epic["id"], "name": "F1"})
    client.post("/features", json={"epic_id": epic["id"], "name": "F2"})

    response = client.get(f"/features?product_id={product['id']}")
    assert response.status_code == 200
    names = {f["name"] for f in response.json()}
    assert names == {"F1", "F2"}


def test_list_features_rejects_neither_filter(db_session):
    response = client.get("/features")
    assert response.status_code == 400


def test_list_features_rejects_both_filters(db_session):
    feature_id, product_id = _create_feature()
    feature = client.get(f"/features/{feature_id}").json()

    response = client.get(f"/features?epic_id={feature['epic_id']}&product_id={product_id}")
    assert response.status_code == 400
