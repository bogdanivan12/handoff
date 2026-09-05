import uuid

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _create_task(key_prefix: str | None = None) -> str:
    product = client.post(
        "/products", json={"name": "Handoff", "key_prefix": key_prefix or uuid.uuid4().hex[:8].upper()}
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
            "title": "Task",
            "task_type": "feature",
        },
    ).json()
    return task["id"]


def test_create_and_list_task_dependency(db_session):
    task_a = _create_task()
    task_b = _create_task()

    response = client.post(f"/tasks/{task_a}/dependencies", json={"depends_on_task_id": task_b})
    assert response.status_code == 201
    body = response.json()
    assert body["task_id"] == task_a
    assert body["depends_on_task"]["id"] == task_b

    response = client.get(f"/tasks/{task_a}/dependencies")
    assert response.status_code == 200
    assert len(response.json()) == 1


def test_create_dependency_rejects_self_reference(db_session):
    task_a = _create_task()

    response = client.post(f"/tasks/{task_a}/dependencies", json={"depends_on_task_id": task_a})
    assert response.status_code == 400


def test_create_dependency_rejects_missing_task(db_session):
    task_a = _create_task()

    response = client.post(
        f"/tasks/{task_a}/dependencies",
        json={"depends_on_task_id": "00000000-0000-0000-0000-000000000000"},
    )
    assert response.status_code == 404


def test_create_dependency_rejects_missing_owner_task(db_session):
    task_b = _create_task()

    response = client.post(
        "/tasks/00000000-0000-0000-0000-000000000000/dependencies",
        json={"depends_on_task_id": task_b},
    )
    assert response.status_code == 404


def test_delete_dependency_rejects_wrong_task(db_session):
    task_a = _create_task()
    task_b = _create_task()
    task_c = _create_task()

    response = client.post(f"/tasks/{task_a}/dependencies", json={"depends_on_task_id": task_b})
    dependency_id = response.json()["id"]

    response = client.delete(f"/tasks/{task_c}/dependencies/{dependency_id}")
    assert response.status_code == 404


def test_delete_dependency(db_session):
    task_a = _create_task()
    task_b = _create_task()

    response = client.post(f"/tasks/{task_a}/dependencies", json={"depends_on_task_id": task_b})
    dependency_id = response.json()["id"]

    response = client.delete(f"/tasks/{task_a}/dependencies/{dependency_id}")
    assert response.status_code == 204

    response = client.get(f"/tasks/{task_a}/dependencies")
    assert response.json() == []


def test_is_blocked_false_with_no_dependencies(db_session):
    task_a = _create_task()

    response = client.get(f"/tasks/{task_a}/is-blocked")
    assert response.status_code == 200
    assert response.json() == {"is_blocked": False, "blocking_tasks": []}


def test_is_blocked_false_when_dependency_is_done(db_session):
    task_a = _create_task()
    task_b = _create_task()
    client.post(f"/tasks/{task_a}/dependencies", json={"depends_on_task_id": task_b})
    client.patch(f"/tasks/{task_b}", json={"status": "done"})

    response = client.get(f"/tasks/{task_a}/is-blocked")
    assert response.json() == {"is_blocked": False, "blocking_tasks": []}


def test_is_blocked_true_when_dependency_is_not_done(db_session):
    task_a = _create_task()
    task_b = _create_task()
    client.post(f"/tasks/{task_a}/dependencies", json={"depends_on_task_id": task_b})

    response = client.get(f"/tasks/{task_a}/is-blocked")
    body = response.json()
    assert body["is_blocked"] is True
    assert len(body["blocking_tasks"]) == 1
    assert body["blocking_tasks"][0]["id"] == task_b


def test_task_read_includes_is_blocked(db_session):
    task_a = _create_task()
    task_b = _create_task()
    client.post(f"/tasks/{task_a}/dependencies", json={"depends_on_task_id": task_b})

    response = client.get(f"/tasks/{task_a}")
    assert response.json()["is_blocked"] is True

    response = client.get(f"/tasks/{task_b}")
    assert response.json()["is_blocked"] is False


def test_list_tasks_by_product(db_session):
    key_prefix = uuid.uuid4().hex[:8].upper()
    product = client.post("/products", json={"name": "Handoff", "key_prefix": key_prefix}).json()
    initiative = client.post(
        "/initiatives", json={"product_id": product["id"], "name": "Core"}
    ).json()
    epic = client.post("/epics", json={"initiative_id": initiative["id"], "name": "Auth"}).json()
    feature_a = client.post("/features", json={"epic_id": epic["id"], "name": "F1"}).json()
    feature_b = client.post("/features", json={"epic_id": epic["id"], "name": "F2"}).json()
    project = client.post("/projects", json={"product_id": product["id"], "name": "Web App"}).json()
    client.post(
        "/tasks",
        json={"feature_id": feature_a["id"], "project_id": project["id"], "title": "A", "task_type": "feature"},
    )
    client.post(
        "/tasks",
        json={"feature_id": feature_b["id"], "project_id": project["id"], "title": "B", "task_type": "feature"},
    )

    response = client.get(f"/tasks?product_id={product['id']}")
    assert response.status_code == 200
    titles = {t["title"] for t in response.json()}
    assert titles == {"A", "B"}


def test_list_tasks_rejects_neither_filter(db_session):
    response = client.get("/tasks")
    assert response.status_code == 400


def test_list_tasks_rejects_both_filters(db_session):
    task_id = _create_task()
    task = client.get(f"/tasks/{task_id}").json()

    response = client.get(f"/tasks?feature_id={task['feature_id']}&product_id={uuid.uuid4()}")
    assert response.status_code == 400
