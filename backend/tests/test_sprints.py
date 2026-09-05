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


def test_create_and_get_sprint(db_session):
    product_id = _create_product()

    response = client.post(
        "/sprints",
        json={
            "product_id": product_id,
            "name": "Sprint 1",
            "start_date": "2026-01-01",
            "end_date": "2026-01-14",
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Sprint 1"
    assert body["status"] == "planned"
    assert body["start_date"] == "2026-01-01"
    assert body["end_date"] == "2026-01-14"

    response = client.get(f"/sprints/{body['id']}")
    assert response.status_code == 200


def test_list_sprints_filtered_by_product(db_session):
    product_a = _create_product()
    product_b = _create_product()

    client.post("/sprints", json={"product_id": product_a, "name": "A1"})
    client.post("/sprints", json={"product_id": product_b, "name": "B1"})

    response = client.get(f"/sprints?product_id={product_a}")
    assert response.status_code == 200
    names = [s["name"] for s in response.json()]
    assert names == ["A1"]


def test_create_sprint_rejects_missing_product(db_session):
    response = client.post(
        "/sprints",
        json={"product_id": "00000000-0000-0000-0000-000000000000", "name": "Orphan"},
    )
    assert response.status_code == 404


def test_get_sprint_not_found(db_session):
    response = client.get("/sprints/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404


def test_update_sprint_status(db_session):
    product_id = _create_product()
    response = client.post("/sprints", json={"product_id": product_id, "name": "Sprint 1"})
    sprint_id = response.json()["id"]

    response = client.patch(f"/sprints/{sprint_id}", json={"status": "active"})
    assert response.status_code == 200
    assert response.json()["status"] == "active"


def test_delete_sprint(db_session):
    product_id = _create_product()
    response = client.post("/sprints", json={"product_id": product_id, "name": "Temp"})
    sprint_id = response.json()["id"]

    response = client.delete(f"/sprints/{sprint_id}")
    assert response.status_code == 204

    response = client.get(f"/sprints/{sprint_id}")
    assert response.status_code == 404
