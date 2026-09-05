import uuid

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _create_product() -> str:
    key_prefix = uuid.uuid4().hex[:8].upper()
    response = client.post("/products", json={"name": "Handoff", "key_prefix": key_prefix})
    return response.json()["id"]


def test_create_and_get_initiative(db_session):
    product_id = _create_product()

    response = client.post("/initiatives", json={"product_id": product_id, "name": "Core"})
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Core"
    assert body["product_id"] == product_id

    response = client.get(f"/initiatives/{body['id']}")
    assert response.status_code == 200


def test_list_initiatives_filtered_by_product(db_session):
    product_a = _create_product()
    product_b = _create_product()

    client.post("/initiatives", json={"product_id": product_a, "name": "A1"})
    client.post("/initiatives", json={"product_id": product_b, "name": "B1"})

    response = client.get(f"/initiatives?product_id={product_a}")
    assert response.status_code == 200
    names = [i["name"] for i in response.json()]
    assert names == ["A1"]


def test_get_initiative_not_found(db_session):
    response = client.get("/initiatives/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404


def test_update_initiative(db_session):
    product_id = _create_product()
    response = client.post("/initiatives", json={"product_id": product_id, "name": "Old"})
    initiative_id = response.json()["id"]

    response = client.patch(f"/initiatives/{initiative_id}", json={"name": "New"})
    assert response.status_code == 200
    assert response.json()["name"] == "New"


def test_delete_initiative(db_session):
    product_id = _create_product()
    response = client.post("/initiatives", json={"product_id": product_id, "name": "Temp"})
    initiative_id = response.json()["id"]

    response = client.delete(f"/initiatives/{initiative_id}")
    assert response.status_code == 204

    response = client.get(f"/initiatives/{initiative_id}")
    assert response.status_code == 404


def test_create_initiative_rejects_missing_product(db_session):
    response = client.post(
        "/initiatives",
        json={"product_id": "00000000-0000-0000-0000-000000000000", "name": "Orphan"},
    )
    assert response.status_code == 404
