from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _create_epic(key_prefix: str = "HAND") -> str:
    product = client.post("/products", json={"name": "Handoff", "key_prefix": key_prefix}).json()
    initiative = client.post(
        "/initiatives", json={"product_id": product["id"], "name": "Core"}
    ).json()
    epic = client.post("/epics", json={"initiative_id": initiative["id"], "name": "Auth"}).json()
    return epic["id"]


def test_create_and_get_feature(db_session):
    epic_id = _create_epic()

    response = client.post("/features", json={"epic_id": epic_id, "name": "Login"})
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Login"
    assert body["issue_number"] == 1
    assert body["issue_key"] == "HAND-1"

    response = client.get(f"/features/{body['id']}")
    assert response.status_code == 200
    assert response.json()["issue_key"] == "HAND-1"


def test_feature_issue_numbers_increment_per_product(db_session):
    epic_id = _create_epic(key_prefix="HAND")

    first = client.post("/features", json={"epic_id": epic_id, "name": "First"}).json()
    second = client.post("/features", json={"epic_id": epic_id, "name": "Second"}).json()

    assert first["issue_number"] == 1
    assert second["issue_number"] == 2
    assert first["issue_key"] == "HAND-1"
    assert second["issue_key"] == "HAND-2"


def test_feature_issue_numbers_independent_per_product(db_session):
    epic_a = _create_epic(key_prefix="AAA")
    epic_b = _create_epic(key_prefix="BBB")

    feature_a = client.post("/features", json={"epic_id": epic_a, "name": "A1"}).json()
    feature_b = client.post("/features", json={"epic_id": epic_b, "name": "B1"}).json()

    assert feature_a["issue_number"] == 1
    assert feature_b["issue_number"] == 1
    assert feature_a["issue_key"] == "AAA-1"
    assert feature_b["issue_key"] == "BBB-1"


def test_list_features_filtered_by_epic(db_session):
    epic_a = _create_epic(key_prefix="FEA")
    epic_b = _create_epic(key_prefix="FEB")

    client.post("/features", json={"epic_id": epic_a, "name": "A1"})
    client.post("/features", json={"epic_id": epic_b, "name": "B1"})

    response = client.get(f"/features?epic_id={epic_a}")
    assert response.status_code == 200
    names = [f["name"] for f in response.json()]
    assert names == ["A1"]


def test_get_feature_not_found(db_session):
    response = client.get("/features/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404


def test_update_feature(db_session):
    epic_id = _create_epic()
    response = client.post("/features", json={"epic_id": epic_id, "name": "Old"})
    feature_id = response.json()["id"]

    response = client.patch(f"/features/{feature_id}", json={"name": "New", "status": "ready"})
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "New"
    assert body["status"] == "ready"
    assert body["issue_number"] == 1


def test_delete_feature(db_session):
    epic_id = _create_epic()
    response = client.post("/features", json={"epic_id": epic_id, "name": "Temp"})
    feature_id = response.json()["id"]

    response = client.delete(f"/features/{feature_id}")
    assert response.status_code == 204

    response = client.get(f"/features/{feature_id}")
    assert response.status_code == 404
