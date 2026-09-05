import uuid

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _create_item(subject: str = "DB") -> str:
    product = client.post(
        "/products", json={"name": "Handoff", "key_prefix": uuid.uuid4().hex[:8].upper()}
    ).json()
    item = client.post(
        "/knowledge-items",
        json={
            "scope": "product",
            "scope_ref_id": product["id"],
            "content": {
                "kind": "decision",
                "subject": subject,
                "chosen": "Postgres",
                "alternatives_considered": [],
                "rationale": "x",
            },
        },
    ).json()
    return item["id"]


def test_create_and_list_relation_by_from_item(db_session):
    item_a = _create_item("A")
    item_b = _create_item("B")

    response = client.post(
        "/knowledge-relations",
        json={"from_item_id": item_b, "to_item_id": item_a, "relation_type": "supersedes"},
    )
    assert response.status_code == 201
    assert response.json()["relation_type"] == "supersedes"

    response = client.get(f"/knowledge-relations?from_item_id={item_b}")
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["to_item_id"] == item_a


def test_list_relation_by_to_item(db_session):
    item_a = _create_item("A")
    item_b = _create_item("B")

    client.post(
        "/knowledge-relations",
        json={"from_item_id": item_b, "to_item_id": item_a, "relation_type": "supersedes"},
    )

    response = client.get(f"/knowledge-relations?to_item_id={item_a}")
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["from_item_id"] == item_b


def test_create_relation_rejects_self_link(db_session):
    item_a = _create_item("A")

    response = client.post(
        "/knowledge-relations",
        json={"from_item_id": item_a, "to_item_id": item_a, "relation_type": "supersedes"},
    )
    assert response.status_code == 422


def test_create_relation_rejects_missing_from_item(db_session):
    item_a = _create_item("A")

    response = client.post(
        "/knowledge-relations",
        json={
            "from_item_id": "00000000-0000-0000-0000-000000000000",
            "to_item_id": item_a,
            "relation_type": "supersedes",
        },
    )
    assert response.status_code == 404


def test_create_relation_rejects_missing_to_item(db_session):
    item_a = _create_item("A")

    response = client.post(
        "/knowledge-relations",
        json={
            "from_item_id": item_a,
            "to_item_id": "00000000-0000-0000-0000-000000000000",
            "relation_type": "supersedes",
        },
    )
    assert response.status_code == 404


def test_list_relations_requires_exactly_one_filter(db_session):
    response = client.get("/knowledge-relations")
    assert response.status_code == 422

    item_a = _create_item("A")
    item_b = _create_item("B")
    response = client.get(f"/knowledge-relations?from_item_id={item_a}&to_item_id={item_b}")
    assert response.status_code == 422


def test_delete_relation(db_session):
    item_a = _create_item("A")
    item_b = _create_item("B")
    response = client.post(
        "/knowledge-relations",
        json={"from_item_id": item_b, "to_item_id": item_a, "relation_type": "supersedes"},
    )
    relation_id = response.json()["id"]

    response = client.delete(f"/knowledge-relations/{relation_id}")
    assert response.status_code == 204
