from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_create_and_get_product(db_session):
    response = client.post("/products", json={"name": "Handoff", "key_prefix": "HAND"})
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Handoff"
    assert body["key_prefix"] == "HAND"

    response = client.get(f"/products/{body['id']}")
    assert response.status_code == 200
    assert response.json()["id"] == body["id"]


def test_list_products(db_session):
    client.post("/products", json={"name": "A", "key_prefix": "A"})
    client.post("/products", json={"name": "B", "key_prefix": "B"})

    response = client.get("/products")
    assert response.status_code == 200
    names = {p["name"] for p in response.json()}
    assert names == {"A", "B"}


def test_get_product_not_found(db_session):
    response = client.get("/products/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404


def test_update_product(db_session):
    response = client.post("/products", json={"name": "Old", "key_prefix": "OLD"})
    product_id = response.json()["id"]

    response = client.patch(f"/products/{product_id}", json={"name": "New"})
    assert response.status_code == 200
    assert response.json()["name"] == "New"
    assert response.json()["key_prefix"] == "OLD"


def test_delete_product(db_session):
    response = client.post("/products", json={"name": "Temp", "key_prefix": "TMP"})
    product_id = response.json()["id"]

    response = client.delete(f"/products/{product_id}")
    assert response.status_code == 204

    response = client.get(f"/products/{product_id}")
    assert response.status_code == 404
