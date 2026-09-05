import uuid
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _create_product() -> str:
    unique_id = str(uuid.uuid4())[:8]
    response = client.post(
        "/products", json={"name": f"Product-{unique_id}", "key_prefix": f"P{unique_id[:3].upper()}"}
    )
    return response.json()["id"]


def test_create_and_get_project(db_session):
    product_id = _create_product()

    response = client.post("/projects", json={"product_id": product_id, "name": "Web App"})
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Web App"
    assert body["product_id"] == product_id

    response = client.get(f"/projects/{body['id']}")
    assert response.status_code == 200


def test_list_projects_filtered_by_product(db_session):
    product_a = _create_product()
    product_b = _create_product()

    client.post("/projects", json={"product_id": product_a, "name": "A1"})
    client.post("/projects", json={"product_id": product_b, "name": "B1"})

    response = client.get(f"/projects?product_id={product_a}")
    assert response.status_code == 200
    names = [p["name"] for p in response.json()]
    assert names == ["A1"]


def test_create_project_rejects_missing_product(db_session):
    response = client.post(
        "/projects",
        json={"product_id": "00000000-0000-0000-0000-000000000000", "name": "Orphan"},
    )
    assert response.status_code == 404


def test_get_project_not_found(db_session):
    response = client.get("/projects/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404


def test_update_project(db_session):
    product_id = _create_product()
    response = client.post("/projects", json={"product_id": product_id, "name": "Old"})
    project_id = response.json()["id"]

    response = client.patch(f"/projects/{project_id}", json={"name": "New"})
    assert response.status_code == 200
    assert response.json()["name"] == "New"


def test_delete_project(db_session):
    product_id = _create_product()
    response = client.post("/projects", json={"product_id": product_id, "name": "Temp"})
    project_id = response.json()["id"]

    response = client.delete(f"/projects/{project_id}")
    assert response.status_code == 204

    response = client.get(f"/projects/{project_id}")
    assert response.status_code == 404
