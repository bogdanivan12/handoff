import uuid

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _create_product() -> str:
    response = client.post(
        "/products", json={"name": "Handoff", "key_prefix": uuid.uuid4().hex[:8].upper()}
    )
    return response.json()["id"]


def _decision_content(subject: str = "DB", chosen: str = "Postgres") -> dict:
    return {
        "kind": "decision",
        "subject": subject,
        "chosen": chosen,
        "alternatives_considered": ["MySQL"],
        "rationale": "team familiarity",
    }


def test_create_and_get_knowledge_item(db_session):
    product_id = _create_product()

    response = client.post(
        "/knowledge-items",
        json={"scope": "product", "scope_ref_id": product_id, "content": _decision_content()},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["type"] == "decision"
    assert body["content"]["chosen"] == "Postgres"
    assert body["status"] == "active"

    response = client.get(f"/knowledge-items/{body['id']}")
    assert response.status_code == 200


def test_list_knowledge_items_filtered_by_scope(db_session):
    product_a = _create_product()
    product_b = _create_product()

    client.post(
        "/knowledge-items",
        json={"scope": "product", "scope_ref_id": product_a, "content": _decision_content("A")},
    )
    client.post(
        "/knowledge-items",
        json={"scope": "product", "scope_ref_id": product_b, "content": _decision_content("B")},
    )

    response = client.get(f"/knowledge-items?scope=product&scope_ref_id={product_a}")
    assert response.status_code == 200
    subjects = [item["content"]["subject"] for item in response.json()]
    assert subjects == ["A"]


def test_create_knowledge_item_rejects_missing_product(db_session):
    response = client.post(
        "/knowledge-items",
        json={
            "scope": "product",
            "scope_ref_id": "00000000-0000-0000-0000-000000000000",
            "content": _decision_content(),
        },
    )
    assert response.status_code == 404


def test_create_knowledge_item_rejects_missing_project(db_session):
    response = client.post(
        "/knowledge-items",
        json={
            "scope": "project",
            "scope_ref_id": "00000000-0000-0000-0000-000000000000",
            "content": _decision_content(),
        },
    )
    assert response.status_code == 404


def test_create_knowledge_item_rejects_invalid_content_kind(db_session):
    product_id = _create_product()

    response = client.post(
        "/knowledge-items",
        json={
            "scope": "product",
            "scope_ref_id": product_id,
            "content": {"kind": "bogus", "subject": "x"},
        },
    )
    assert response.status_code == 422


def test_create_knowledge_item_with_constraint_type(db_session):
    product_id = _create_product()

    response = client.post(
        "/knowledge-items",
        json={
            "scope": "product",
            "scope_ref_id": product_id,
            "content": {
                "kind": "constraint",
                "subject": "API",
                "rule": "must be backward compatible",
                "severity": "hard",
            },
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["type"] == "constraint"
    assert body["content"]["severity"] == "hard"


def test_get_knowledge_item_not_found(db_session):
    response = client.get("/knowledge-items/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404


def test_update_knowledge_item_status(db_session):
    product_id = _create_product()
    response = client.post(
        "/knowledge-items",
        json={"scope": "product", "scope_ref_id": product_id, "content": _decision_content()},
    )
    item_id = response.json()["id"]

    response = client.patch(f"/knowledge-items/{item_id}", json={"status": "superseded"})
    assert response.status_code == 200
    assert response.json()["status"] == "superseded"


def test_update_knowledge_item_content_changes_type(db_session):
    product_id = _create_product()
    response = client.post(
        "/knowledge-items",
        json={"scope": "product", "scope_ref_id": product_id, "content": _decision_content()},
    )
    item_id = response.json()["id"]

    response = client.patch(
        f"/knowledge-items/{item_id}",
        json={
            "content": {
                "kind": "constraint",
                "subject": "Changed",
                "rule": "new rule",
                "severity": "soft",
            }
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["type"] == "constraint"
    assert body["content"]["rule"] == "new rule"


def test_delete_knowledge_item(db_session):
    product_id = _create_product()
    response = client.post(
        "/knowledge-items",
        json={"scope": "product", "scope_ref_id": product_id, "content": _decision_content()},
    )
    item_id = response.json()["id"]

    response = client.delete(f"/knowledge-items/{item_id}")
    assert response.status_code == 204

    response = client.get(f"/knowledge-items/{item_id}")
    assert response.status_code == 404


def test_create_knowledge_item_rejects_invalid_confidence(db_session):
    product_id = _create_product()

    response = client.post(
        "/knowledge-items",
        json={
            "scope": "product",
            "scope_ref_id": product_id,
            "content": _decision_content(),
            "confidence": 12.5,
        },
    )
    assert response.status_code == 422


def test_create_knowledge_item_rejects_invalid_provenance(db_session):
    product_id = _create_product()

    response = client.post(
        "/knowledge-items",
        json={
            "scope": "product",
            "scope_ref_id": product_id,
            "content": _decision_content(),
            "provenance": "not-a-real-provenance",
        },
    )
    assert response.status_code == 422


def test_update_knowledge_item_rejects_invalid_status(db_session):
    product_id = _create_product()
    response = client.post(
        "/knowledge-items",
        json={"scope": "product", "scope_ref_id": product_id, "content": _decision_content()},
    )
    item_id = response.json()["id"]

    response = client.patch(f"/knowledge-items/{item_id}", json={"status": "totally-bogus"})
    assert response.status_code == 422


def test_list_knowledge_items_rejects_invalid_scope(db_session):
    product_id = _create_product()

    response = client.get(f"/knowledge-items?scope=bogus&scope_ref_id={product_id}")
    assert response.status_code == 422
