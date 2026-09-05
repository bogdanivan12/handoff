import uuid

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _create_feature_and_project(key_prefix: str | None = None) -> tuple[str, str]:
    product = client.post(
        "/products",
        json={"name": "Handoff", "key_prefix": key_prefix or uuid.uuid4().hex[:8].upper()},
    ).json()
    initiative = client.post(
        "/initiatives", json={"product_id": product["id"], "name": "Core"}
    ).json()
    epic = client.post("/epics", json={"initiative_id": initiative["id"], "name": "Auth"}).json()
    feature = client.post("/features", json={"epic_id": epic["id"], "name": "Login"}).json()
    project = client.post("/projects", json={"product_id": product["id"], "name": "Web App"}).json()
    return feature["id"], project["id"]


def test_create_and_get_task(db_session):
    feature_id, project_id = _create_feature_and_project()

    response = client.post(
        "/tasks",
        json={
            "feature_id": feature_id,
            "project_id": project_id,
            "title": "Wire up login form",
            "task_type": "feature",
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["title"] == "Wire up login form"
    assert body["status"] == "todo"

    response = client.get(f"/tasks/{body['id']}")
    assert response.status_code == 200


def test_task_shares_issue_counter_with_feature(db_session):
    key_prefix = uuid.uuid4().hex[:8].upper()
    feature_id, project_id = _create_feature_and_project(key_prefix)

    feature_response = client.get(f"/features/{feature_id}")
    feature_issue_number = feature_response.json()["issue_number"]

    response = client.post(
        "/tasks",
        json={
            "feature_id": feature_id,
            "project_id": project_id,
            "title": "Wire up login form",
            "task_type": "feature",
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["issue_number"] == feature_issue_number + 1
    assert body["issue_key"] == f"{key_prefix}-{feature_issue_number + 1}"


def test_list_tasks_filtered_by_feature(db_session):
    feature_a, project_a = _create_feature_and_project()
    feature_b, project_b = _create_feature_and_project()

    client.post(
        "/tasks",
        json={
            "feature_id": feature_a,
            "project_id": project_a,
            "title": "A1",
            "task_type": "feature",
        },
    )
    client.post(
        "/tasks",
        json={
            "feature_id": feature_b,
            "project_id": project_b,
            "title": "B1",
            "task_type": "feature",
        },
    )

    response = client.get(f"/tasks?feature_id={feature_a}")
    assert response.status_code == 200
    titles = [t["title"] for t in response.json()]
    assert titles == ["A1"]


def test_create_task_rejects_missing_feature(db_session):
    _, project_id = _create_feature_and_project()

    response = client.post(
        "/tasks",
        json={
            "feature_id": "00000000-0000-0000-0000-000000000000",
            "project_id": project_id,
            "title": "Orphan",
            "task_type": "feature",
        },
    )
    assert response.status_code == 404


def test_create_task_rejects_missing_project(db_session):
    feature_id, _ = _create_feature_and_project()

    response = client.post(
        "/tasks",
        json={
            "feature_id": feature_id,
            "project_id": "00000000-0000-0000-0000-000000000000",
            "title": "Orphan",
            "task_type": "feature",
        },
    )
    assert response.status_code == 404


def test_create_task_rejects_missing_sprint(db_session):
    feature_id, project_id = _create_feature_and_project()

    response = client.post(
        "/tasks",
        json={
            "feature_id": feature_id,
            "project_id": project_id,
            "sprint_id": "00000000-0000-0000-0000-000000000000",
            "title": "Orphan",
            "task_type": "feature",
        },
    )
    assert response.status_code == 404


def test_get_task_not_found(db_session):
    response = client.get("/tasks/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404


def test_update_task_status(db_session):
    feature_id, project_id = _create_feature_and_project()
    response = client.post(
        "/tasks",
        json={"feature_id": feature_id, "project_id": project_id, "title": "Old", "task_type": "bug"},
    )
    task_id = response.json()["id"]

    response = client.patch(f"/tasks/{task_id}", json={"status": "in_progress", "title": "New"})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "in_progress"
    assert body["title"] == "New"


def test_delete_task(db_session):
    feature_id, project_id = _create_feature_and_project()
    response = client.post(
        "/tasks",
        json={
            "feature_id": feature_id,
            "project_id": project_id,
            "title": "Temp",
            "task_type": "chore",
        },
    )
    task_id = response.json()["id"]

    response = client.delete(f"/tasks/{task_id}")
    assert response.status_code == 204

    response = client.get(f"/tasks/{task_id}")
    assert response.status_code == 404
