import os
import uuid

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _create_task() -> str:
    product = client.post(
        "/products", json={"name": "Handoff", "key_prefix": uuid.uuid4().hex[:8].upper()}
    ).json()
    initiative = client.post(
        "/initiatives", json={"product_id": product["id"], "name": "Core"}
    ).json()
    epic = client.post("/epics", json={"initiative_id": initiative["id"], "name": "Auth"}).json()
    feature = client.post("/features", json={"epic_id": epic["id"], "name": "Login"}).json()
    project = client.post("/projects", json={"product_id": product["id"], "name": "Web App"}).json()
    task = client.post(
        "/tasks",
        json={
            "feature_id": feature["id"],
            "project_id": project["id"],
            "title": "Wire up login form",
            "task_type": "feature",
        },
    ).json()
    return task["id"]


def test_create_and_list_basic_criterion(db_session):
    task_id = _create_task()

    response = client.post(
        f"/tasks/{task_id}/acceptance-criteria",
        json={"format": "basic", "description": "Form submits successfully"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["format"] == "basic"
    assert body["checked"] is False

    response = client.get(f"/tasks/{task_id}/acceptance-criteria")
    assert response.status_code == 200
    assert len(response.json()) == 1


def test_create_gherkin_criterion(db_session):
    task_id = _create_task()

    response = client.post(
        f"/tasks/{task_id}/acceptance-criteria",
        json={
            "format": "gherkin",
            "given": "a valid login form",
            "when_": "the user submits it",
            "then_": "they are redirected to the dashboard",
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["format"] == "gherkin"
    assert body["then_"] == "they are redirected to the dashboard"


def test_create_criterion_rejects_missing_task(db_session):
    response = client.post(
        "/tasks/00000000-0000-0000-0000-000000000000/acceptance-criteria",
        json={"format": "basic", "description": "x"},
    )
    assert response.status_code == 404


def test_toggle_criterion_checked_sets_checked_at(db_session):
    task_id = _create_task()
    response = client.post(
        f"/tasks/{task_id}/acceptance-criteria",
        json={"format": "basic", "description": "Form submits"},
    )
    criterion_id = response.json()["id"]
    assert response.json()["checked_at"] is None

    response = client.patch(
        f"/tasks/{task_id}/acceptance-criteria/{criterion_id}", json={"checked": True}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["checked"] is True
    assert body["checked_at"] is not None

    response = client.patch(
        f"/tasks/{task_id}/acceptance-criteria/{criterion_id}", json={"checked": False}
    )
    assert response.json()["checked"] is False
    assert response.json()["checked_at"] is None


def test_update_criterion_rejects_wrong_task(db_session):
    task_a = _create_task()
    task_b = _create_task()

    response = client.post(
        f"/tasks/{task_a}/acceptance-criteria", json={"format": "basic", "description": "x"}
    )
    criterion_id = response.json()["id"]

    response = client.patch(
        f"/tasks/{task_b}/acceptance-criteria/{criterion_id}", json={"checked": True}
    )
    assert response.status_code == 404


def test_delete_criterion(db_session):
    task_id = _create_task()
    response = client.post(
        f"/tasks/{task_id}/acceptance-criteria", json={"format": "basic", "description": "Temp"}
    )
    criterion_id = response.json()["id"]

    response = client.delete(f"/tasks/{task_id}/acceptance-criteria/{criterion_id}")
    assert response.status_code == 204

    response = client.get(f"/tasks/{task_id}/acceptance-criteria")
    assert response.json() == []


def test_criterion_checked_at_round_trips_as_timezone_aware(db_session):
    task_id = _create_task()
    response = client.post(
        f"/tasks/{task_id}/acceptance-criteria", json={"format": "basic", "description": "x"}
    )
    criterion_id = response.json()["id"]

    # This request would fail with a 500 error (DataError) against real Postgres before the fix,
    # because the router sets a timezone-aware datetime (datetime.now(timezone.utc)) but the
    # ORM model column was naively typed. The fix adds DateTime(timezone=True) to the column.
    response = client.patch(
        f"/tasks/{task_id}/acceptance-criteria/{criterion_id}", json={"checked": True}
    )
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    checked_at = response.json()["checked_at"]
    assert checked_at is not None
    # A timezone-aware ISO 8601 string ends with "Z" or a "+HH:MM"/"-HH:MM" offset —
    # a naive datetime serializes with neither, which is what this bug produced.
    # For Postgres, we verify timezone format; SQLite doesn't preserve timezone info in testing.
    if os.environ.get("TEST_DATABASE_TYPE") != "sqlite":
        assert checked_at.endswith("Z") or "+" in checked_at[10:] or checked_at.count("-") > 2
