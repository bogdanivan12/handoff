from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _create_initiative() -> str:
    product = client.post("/products", json={"name": "Handoff", "key_prefix": "HAND"}).json()
    initiative = client.post(
        "/initiatives", json={"product_id": product["id"], "name": "Core"}
    ).json()
    return initiative["id"]


def test_create_and_get_epic(db_session):
    initiative_id = _create_initiative()

    response = client.post("/epics", json={"initiative_id": initiative_id, "name": "Auth"})
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Auth"
    assert body["initiative_id"] == initiative_id

    response = client.get(f"/epics/{body['id']}")
    assert response.status_code == 200


def test_list_epics_filtered_by_initiative(db_session):
    initiative_a = _create_initiative()
    initiative_b = _create_initiative()

    client.post("/epics", json={"initiative_id": initiative_a, "name": "A1"})
    client.post("/epics", json={"initiative_id": initiative_b, "name": "B1"})

    response = client.get(f"/epics?initiative_id={initiative_a}")
    assert response.status_code == 200
    names = [e["name"] for e in response.json()]
    assert names == ["A1"]


def test_get_epic_not_found(db_session):
    response = client.get("/epics/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404


def test_update_epic(db_session):
    initiative_id = _create_initiative()
    response = client.post("/epics", json={"initiative_id": initiative_id, "name": "Old"})
    epic_id = response.json()["id"]

    response = client.patch(f"/epics/{epic_id}", json={"name": "New"})
    assert response.status_code == 200
    assert response.json()["name"] == "New"


def test_delete_epic(db_session):
    initiative_id = _create_initiative()
    response = client.post("/epics", json={"initiative_id": initiative_id, "name": "Temp"})
    epic_id = response.json()["id"]

    response = client.delete(f"/epics/{epic_id}")
    assert response.status_code == 204

    response = client.get(f"/epics/{epic_id}")
    assert response.status_code == 404
