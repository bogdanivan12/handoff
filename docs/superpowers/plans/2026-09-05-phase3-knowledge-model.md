# Phase 3 Knowledge Model Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** CRUD for `KnowledgeItem` (a typed fact scoped to a Product or a Project, with a Pydantic-discriminated-union `content` field per type) and `KnowledgeRelation` (a directed link between two facts), plus a frontend page with a scope selector and a dynamic create form.

**Architecture:** Six Pydantic content models (one per `KnowledgeItem` type) form a discriminated union on their `kind` field; the API accepts only `content` and derives the DB row's `type` column from `content.kind` server-side, so the two can never disagree. `KnowledgeRelation` is a simple directed edge with an app-level (not just DB-level) "no self-link" check. No new frontend routing pattern — one more page in the same family as `ProductSettingsPage`.

**Tech Stack:** Same as Phase 2 — no new dependencies. Uses SQLAlchemy's built-in `TypeEngine.with_variant` for the JSON/JSONB cross-dialect column (no new custom type needed, unlike `GUID`).

**Spec:** [docs/superpowers/specs/2026-09-05-phase3-knowledge-model-design.md](../specs/2026-09-05-phase3-knowledge-model-design.md)

## Global Constraints

- No `embedding`/pgvector column this phase — deliberately deferred until vector search is actually built
- `type`, `scope`, `provenance`, `status` (on `KnowledgeItem`), `relation_type` (on `KnowledgeRelation`) are plain `Text` columns, not Postgres `ENUM`s
- `KnowledgeItem.type` is **always derived server-side** from `content.kind` — the create/update schemas never accept a separate `type` field from the client
- `content`'s stored JSON **includes** the `kind` discriminator key (not stripped) — required so a stored item deserializes back into the correct Pydantic variant on read
- `POST /knowledge-items` validates `scope_ref_id` resolves to a real Product (`scope="product"`) or Project (`scope="project"`) — 404 if not
- `POST /knowledge-relations` validates both `from_item_id`/`to_item_id` exist (404) and that they differ (422), before ever reaching the DB's `CHECK` constraint
- Every new model column that has a Python-side `default=` also gets a matching `server_default=` from the start (Phase 2's final review had to retrofit this — do it correctly here the first time)
- All repo content in English

---

### Task 1: Content Models, KnowledgeItem/KnowledgeRelation Models, Migration

**Files:**
- Create: `backend/app/knowledge_content.py`
- Modify: `backend/app/models.py`
- Create: `backend/alembic/versions/0004_knowledge_model.py`
- Modify: `backend/tests/test_models.py`

**Interfaces:**
- Produces: `app.knowledge_content.KnowledgeContent` (the discriminated union type: `Annotated[Union[DecisionContent, ConventionContent, ConstraintContent, DomainConceptContent, TechnicalFactContent, KnownIssueContent], Field(discriminator="kind")]`) and the six individual content model classes. `app.models.KnowledgeItem`, `app.models.KnowledgeRelation`. Consumed by Task 2 (`KnowledgeItem`, `KnowledgeContent`) and Task 3 (`KnowledgeRelation`).

- [ ] **Step 1: Write the six content models and the discriminated union**

Create `backend/app/knowledge_content.py`:

```python
from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field


class DecisionContent(BaseModel):
    kind: Literal["decision"] = "decision"
    subject: str
    chosen: str
    alternatives_considered: list[str] = []
    rationale: str


class ConventionContent(BaseModel):
    kind: Literal["convention"] = "convention"
    subject: str
    rule: str
    example: str | None = None


class ConstraintContent(BaseModel):
    kind: Literal["constraint"] = "constraint"
    subject: str
    rule: str
    rationale: str | None = None
    severity: Literal["hard", "soft"]


class DomainConceptContent(BaseModel):
    kind: Literal["domain_concept"] = "domain_concept"
    term: str
    definition: str
    related_terms: list[str] = []


class TechnicalFactContent(BaseModel):
    kind: Literal["technical_fact"] = "technical_fact"
    subject: str
    fact: str
    verified_at: str | None = None


class KnownIssueContent(BaseModel):
    kind: Literal["known_issue"] = "known_issue"
    subject: str
    description: str
    workaround: str | None = None
    status: str = "open"


KnowledgeContent = Annotated[
    Union[
        DecisionContent,
        ConventionContent,
        ConstraintContent,
        DomainConceptContent,
        TechnicalFactContent,
        KnownIssueContent,
    ],
    Field(discriminator="kind"),
]
```

- [ ] **Step 2: Add the models**

In `backend/app/models.py`, add `CheckConstraint, JSON, Numeric` to the existing `from sqlalchemy import Date, ForeignKey, Text, func` line, and add a new import line right after it:

```python
from sqlalchemy.dialects.postgresql import JSONB
```

Add these two classes at the end of the file (after `Sprint`):

```python
class KnowledgeItem(Base):
    __tablename__ = "knowledge_items"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    type: Mapped[str] = mapped_column(Text)
    scope: Mapped[str] = mapped_column(Text)
    scope_ref_id: Mapped[uuid.UUID] = mapped_column(GUID)
    content: Mapped[dict] = mapped_column(JSONB().with_variant(JSON(), "sqlite"))
    confidence: Mapped[float | None] = mapped_column(Numeric(3, 2), default=None)
    provenance: Mapped[str] = mapped_column(Text, default="manual", server_default="manual")
    source_ref_type: Mapped[str | None] = mapped_column(Text, default=None)
    source_ref_id: Mapped[uuid.UUID | None] = mapped_column(GUID, default=None)
    status: Mapped[str] = mapped_column(Text, default="active", server_default="active")
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())


class KnowledgeRelation(Base):
    __tablename__ = "knowledge_relations"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    from_item_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("knowledge_items.id", ondelete="CASCADE")
    )
    to_item_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("knowledge_items.id", ondelete="CASCADE")
    )
    relation_type: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    __table_args__ = (
        CheckConstraint("from_item_id != to_item_id", name="ck_knowledge_relations_no_self_link"),
    )
```

- [ ] **Step 3: Write the migration**

Create `backend/alembic/versions/0004_knowledge_model.py`:

```python
"""knowledge model

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-05 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "knowledge_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("scope", sa.Text(), nullable=False),
        sa.Column("scope_ref_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("content", postgresql.JSONB(), nullable=False),
        sa.Column("confidence", sa.Numeric(3, 2), nullable=True),
        sa.Column("provenance", sa.Text(), nullable=False, server_default="manual"),
        sa.Column("source_ref_type", sa.Text(), nullable=True),
        sa.Column("source_ref_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default="active"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )

    op.create_table(
        "knowledge_relations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "from_item_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("knowledge_items.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "to_item_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("knowledge_items.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("relation_type", sa.Text(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "from_item_id != to_item_id", name="ck_knowledge_relations_no_self_link"
        ),
    )


def downgrade() -> None:
    op.drop_table("knowledge_relations")
    op.drop_table("knowledge_items")
```

- [ ] **Step 4: Verify the migration chain (no DB connection needed)**

Run: `cd backend && uv run alembic heads`
Expected: `0004 (head)`

- [ ] **Step 5: Write a test proving the models and JSON content round-trip**

In `backend/tests/test_models.py`, add `KnowledgeItem, KnowledgeRelation` to the existing `from app.models import ...` import line, then append:

```python


def test_can_create_knowledge_item_and_relation(db_session):
    async def _run():
        override = app.dependency_overrides[get_db]
        async for session in override():
            product = Product(name="Handoff", key_prefix="HAND")
            session.add(product)
            await session.flush()

            item_a = KnowledgeItem(
                type="decision",
                scope="product",
                scope_ref_id=product.id,
                content={
                    "kind": "decision",
                    "subject": "DB",
                    "chosen": "Postgres",
                    "alternatives_considered": ["MySQL"],
                    "rationale": "team familiarity",
                },
            )
            item_b = KnowledgeItem(
                type="decision",
                scope="product",
                scope_ref_id=product.id,
                content={
                    "kind": "decision",
                    "subject": "DB",
                    "chosen": "MySQL",
                    "alternatives_considered": [],
                    "rationale": "changed our minds",
                },
            )
            session.add_all([item_a, item_b])
            await session.flush()

            relation = KnowledgeRelation(
                from_item_id=item_b.id, to_item_id=item_a.id, relation_type="supersedes"
            )
            session.add(relation)
            await session.commit()

            result = await session.execute(
                select(KnowledgeItem).where(KnowledgeItem.id == item_a.id)
            )
            loaded = result.scalar_one()
            assert loaded.content["chosen"] == "Postgres"
            break

    asyncio.run(_run())
```

- [ ] **Step 6: Run the test to verify it passes**

Run: `uv run pytest tests/test_models.py -v` (from `backend/`)
Expected: `3 passed`

- [ ] **Step 7: Run the full backend suite**

Run: `uv run pytest -v` (from `backend/`)
Expected: `45 passed` (44 from Phase 2 + this one new test)

- [ ] **Step 8: Commit**

```bash
git add backend/app/knowledge_content.py backend/app/models.py backend/alembic/versions/0004_knowledge_model.py backend/tests/test_models.py
git commit -m "feat(backend): add knowledge content models, KnowledgeItem/KnowledgeRelation models, and migration"
```

---

### Task 2: KnowledgeItem CRUD

**Files:**
- Modify: `backend/app/schemas.py`
- Create: `backend/app/routers/knowledge_items.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_knowledge_items.py`

**Interfaces:**
- Consumes: `app.knowledge_content.KnowledgeContent` (Task 1), `app.models.KnowledgeItem/.Product/.Project` (Task 1 / Phase 1-2)
- Produces: `app.schemas.KnowledgeItemCreate/.KnowledgeItemUpdate/.KnowledgeItemRead`. Router mounted at `/knowledge-items` — consumed by Task 4's frontend API client.

- [ ] **Step 1: Add the schemas**

In `backend/app/schemas.py`, add `from typing import Literal` to the imports, and `from app.knowledge_content import KnowledgeContent`. Then append:

```python


class KnowledgeItemCreate(BaseModel):
    scope: Literal["product", "project"]
    scope_ref_id: uuid.UUID
    content: KnowledgeContent
    confidence: float | None = None
    provenance: str = "manual"


class KnowledgeItemUpdate(BaseModel):
    content: KnowledgeContent | None = None
    status: str | None = None


class KnowledgeItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    type: str
    scope: str
    scope_ref_id: uuid.UUID
    content: dict
    confidence: float | None
    provenance: str
    status: str
    created_at: datetime
    updated_at: datetime
```

- [ ] **Step 2: Write the failing tests**

Create `backend/tests/test_knowledge_items.py`:

```python
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
```

- [ ] **Step 3: Run to verify it fails**

Run: `uv run pytest tests/test_knowledge_items.py -v` (from `backend/`)
Expected: FAIL — `404 Not Found` on `POST /knowledge-items`

- [ ] **Step 4: Implement the router**

Create `backend/app/routers/knowledge_items.py`:

```python
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import KnowledgeItem, Product, Project
from app.schemas import KnowledgeItemCreate, KnowledgeItemRead, KnowledgeItemUpdate

router = APIRouter(prefix="/knowledge-items", tags=["knowledge-items"])


async def _validate_scope_ref(scope: str, scope_ref_id: uuid.UUID, db: AsyncSession) -> None:
    if scope == "product":
        entity = await db.get(Product, scope_ref_id)
        if entity is None:
            raise HTTPException(status_code=404, detail="Product not found")
    else:
        entity = await db.get(Project, scope_ref_id)
        if entity is None:
            raise HTTPException(status_code=404, detail="Project not found")


@router.get("", response_model=list[KnowledgeItemRead])
async def list_knowledge_items(
    scope: str = Query(...),
    scope_ref_id: uuid.UUID = Query(...),
    db: AsyncSession = Depends(get_db),
) -> list[KnowledgeItem]:
    result = await db.execute(
        select(KnowledgeItem)
        .where(KnowledgeItem.scope == scope, KnowledgeItem.scope_ref_id == scope_ref_id)
        .order_by(KnowledgeItem.created_at)
    )
    return list(result.scalars().all())


@router.post("", response_model=KnowledgeItemRead, status_code=201)
async def create_knowledge_item(
    payload: KnowledgeItemCreate, db: AsyncSession = Depends(get_db)
) -> KnowledgeItem:
    await _validate_scope_ref(payload.scope, payload.scope_ref_id, db)

    item = KnowledgeItem(
        type=payload.content.kind,
        scope=payload.scope,
        scope_ref_id=payload.scope_ref_id,
        content=payload.content.model_dump(),
        confidence=payload.confidence,
        provenance=payload.provenance,
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return item


@router.get("/{item_id}", response_model=KnowledgeItemRead)
async def get_knowledge_item(
    item_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> KnowledgeItem:
    item = await db.get(KnowledgeItem, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Knowledge item not found")
    return item


@router.patch("/{item_id}", response_model=KnowledgeItemRead)
async def update_knowledge_item(
    item_id: uuid.UUID, payload: KnowledgeItemUpdate, db: AsyncSession = Depends(get_db)
) -> KnowledgeItem:
    item = await db.get(KnowledgeItem, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Knowledge item not found")

    updates = payload.model_dump(exclude_unset=True)
    if "content" in updates and updates["content"] is not None:
        item.content = payload.content.model_dump()
        item.type = payload.content.kind
    if "status" in updates and updates["status"] is not None:
        item.status = payload.status

    await db.commit()
    await db.refresh(item)
    return item


@router.delete("/{item_id}", status_code=204)
async def delete_knowledge_item(item_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> None:
    item = await db.get(KnowledgeItem, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Knowledge item not found")
    await db.delete(item)
    await db.commit()
```

- [ ] **Step 5: Wire the router into the app**

In `backend/app/main.py`, add `from app.routers.knowledge_items import router as knowledge_items_router` alongside the other router imports, and `app.include_router(knowledge_items_router)` alongside the other includes.

- [ ] **Step 6: Run the tests to verify they pass**

Run: `uv run pytest tests/test_knowledge_items.py -v` (from `backend/`)
Expected: `11 passed`

- [ ] **Step 7: Run the full backend suite**

Run: `uv run pytest -v` (from `backend/`)
Expected: `56 passed` (45 from Task 1 + 11 knowledge item tests)

- [ ] **Step 8: Commit**

```bash
git add backend/app/schemas.py backend/app/routers/knowledge_items.py backend/app/main.py backend/tests/test_knowledge_items.py
git commit -m "feat(backend): add KnowledgeItem CRUD with discriminated content union"
```

---

### Task 3: KnowledgeRelation CRUD

**Files:**
- Modify: `backend/app/schemas.py`
- Create: `backend/app/routers/knowledge_relations.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_knowledge_relations.py`

**Interfaces:**
- Consumes: `app.models.KnowledgeItem/.KnowledgeRelation` (Task 1)
- Produces: `app.schemas.KnowledgeRelationCreate/.KnowledgeRelationRead`. Router mounted at `/knowledge-relations` — not consumed by any frontend task in this plan (API exists for Phase 9's later use).

- [ ] **Step 1: Add the schemas**

Append to `backend/app/schemas.py`:

```python


class KnowledgeRelationCreate(BaseModel):
    from_item_id: uuid.UUID
    to_item_id: uuid.UUID
    relation_type: Literal["supersedes", "conflicts_with", "derived_from", "refines"]


class KnowledgeRelationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    from_item_id: uuid.UUID
    to_item_id: uuid.UUID
    relation_type: str
    created_at: datetime
```

- [ ] **Step 2: Write the failing tests**

Create `backend/tests/test_knowledge_relations.py`:

```python
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
```

- [ ] **Step 3: Run to verify it fails**

Run: `uv run pytest tests/test_knowledge_relations.py -v` (from `backend/`)
Expected: FAIL — `404 Not Found` on `POST /knowledge-relations`

- [ ] **Step 4: Implement the router**

Create `backend/app/routers/knowledge_relations.py`:

```python
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import KnowledgeItem, KnowledgeRelation
from app.schemas import KnowledgeRelationCreate, KnowledgeRelationRead

router = APIRouter(prefix="/knowledge-relations", tags=["knowledge-relations"])


@router.get("", response_model=list[KnowledgeRelationRead])
async def list_knowledge_relations(
    from_item_id: uuid.UUID | None = Query(default=None),
    to_item_id: uuid.UUID | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> list[KnowledgeRelation]:
    if (from_item_id is None) == (to_item_id is None):
        raise HTTPException(
            status_code=422, detail="Provide exactly one of from_item_id or to_item_id"
        )

    query = select(KnowledgeRelation)
    if from_item_id is not None:
        query = query.where(KnowledgeRelation.from_item_id == from_item_id)
    else:
        query = query.where(KnowledgeRelation.to_item_id == to_item_id)

    result = await db.execute(query.order_by(KnowledgeRelation.created_at))
    return list(result.scalars().all())


@router.post("", response_model=KnowledgeRelationRead, status_code=201)
async def create_knowledge_relation(
    payload: KnowledgeRelationCreate, db: AsyncSession = Depends(get_db)
) -> KnowledgeRelation:
    if payload.from_item_id == payload.to_item_id:
        raise HTTPException(status_code=422, detail="from_item_id and to_item_id must differ")

    from_item = await db.get(KnowledgeItem, payload.from_item_id)
    if from_item is None:
        raise HTTPException(status_code=404, detail="from_item_id not found")

    to_item = await db.get(KnowledgeItem, payload.to_item_id)
    if to_item is None:
        raise HTTPException(status_code=404, detail="to_item_id not found")

    relation = KnowledgeRelation(**payload.model_dump())
    db.add(relation)
    await db.commit()
    await db.refresh(relation)
    return relation


@router.delete("/{relation_id}", status_code=204)
async def delete_knowledge_relation(
    relation_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> None:
    relation = await db.get(KnowledgeRelation, relation_id)
    if relation is None:
        raise HTTPException(status_code=404, detail="Knowledge relation not found")
    await db.delete(relation)
    await db.commit()
```

- [ ] **Step 5: Wire the router into the app**

Same pattern as Task 2, importing and including `knowledge_relations_router` in `backend/app/main.py`.

- [ ] **Step 6: Run the full backend suite**

Run: `uv run pytest -v` (from `backend/`)
Expected: `63 passed` (56 from Task 2 + 7 knowledge relation tests)

- [ ] **Step 7: Commit**

```bash
git add backend/app/schemas.py backend/app/routers/knowledge_relations.py backend/app/main.py backend/tests/test_knowledge_relations.py
git commit -m "feat(backend): add KnowledgeRelation CRUD"
```

---

### Task 4: Frontend Knowledge Page

**Files:**
- Modify: `frontend/src/lib/api.ts`
- Create: `frontend/src/pages/ProductKnowledgePage.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/pages/ProductDetailPage.tsx`

**Interfaces:**
- Consumes: `api.getProduct`, `api.listProjects` (already exist), new `api.listKnowledgeItems`/`.createKnowledgeItem` (this task adds them)
- Produces: nothing consumed by later tasks — this is the last task of the plan.

- [ ] **Step 1: Add the KnowledgeItem type and methods to the API client**

In `frontend/src/lib/api.ts`, add this interface near the existing ones:

```typescript
export interface KnowledgeItem {
  id: string;
  type: string;
  scope: string;
  scope_ref_id: string;
  content: Record<string, unknown>;
  confidence: number | null;
  provenance: string;
  status: string;
  created_at: string;
  updated_at: string;
}
```

Add these methods to the exported `api` object:

```typescript
  listKnowledgeItems: (scope: string, scopeRefId: string) =>
    request<KnowledgeItem[]>(`/knowledge-items?scope=${scope}&scope_ref_id=${scopeRefId}`),
  createKnowledgeItem: (data: {
    scope: string;
    scope_ref_id: string;
    content: Record<string, unknown>;
  }) => request<KnowledgeItem>("/knowledge-items", { method: "POST", body: JSON.stringify(data) }),
```

- [ ] **Step 2: Write the Knowledge page**

Create `frontend/src/pages/ProductKnowledgePage.tsx`:

```tsx
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { Breadcrumb } from "@/components/Breadcrumb";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api, type KnowledgeItem, type Product, type Project } from "@/lib/api";

type ContentKind =
  | "decision"
  | "convention"
  | "constraint"
  | "domain_concept"
  | "technical_fact"
  | "known_issue";

function summarize(item: KnowledgeItem): string {
  const content = item.content;
  switch (item.type) {
    case "decision":
      return `Chose ${String(content.chosen)} for ${String(content.subject)}`;
    case "convention":
      return `${String(content.subject)}: ${String(content.rule)}`;
    case "constraint":
      return `${String(content.subject)}: ${String(content.rule)} (${String(content.severity)})`;
    case "domain_concept":
      return `${String(content.term)}: ${String(content.definition)}`;
    case "technical_fact":
      return `${String(content.subject)}: ${String(content.fact)}`;
    case "known_issue":
      return String(content.description);
    default:
      return JSON.stringify(content);
  }
}

export function ProductKnowledgePage() {
  const { productId } = useParams<{ productId: string }>();
  const [product, setProduct] = useState<Product | null>(null);
  const [projects, setProjects] = useState<Project[]>([]);
  const [items, setItems] = useState<KnowledgeItem[]>([]);
  const [loadError, setLoadError] = useState(false);

  const [selectedScopeRefId, setSelectedScopeRefId] = useState<string>("");
  const [showForm, setShowForm] = useState(false);
  const [kind, setKind] = useState<ContentKind>("decision");
  const [fields, setFields] = useState<Record<string, string>>({});

  const scope = selectedScopeRefId === productId ? "product" : "project";

  const load = () => {
    if (!productId) return;
    setLoadError(false);
    Promise.all([api.getProduct(productId), api.listProjects(productId)])
      .then(([productResult, projectsResult]) => {
        setProduct(productResult);
        setProjects(projectsResult);
        if (!selectedScopeRefId) setSelectedScopeRefId(productId);
      })
      .catch(() => setLoadError(true));
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [productId]);

  useEffect(() => {
    if (!selectedScopeRefId) return;
    api
      .listKnowledgeItems(scope, selectedScopeRefId)
      .then(setItems)
      .catch(() => setLoadError(true));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedScopeRefId]);

  const setField = (name: string, value: string) => {
    setFields((prev) => ({ ...prev, [name]: value }));
  };

  const buildContent = (): Record<string, unknown> => {
    switch (kind) {
      case "decision":
        return {
          kind,
          subject: fields.subject ?? "",
          chosen: fields.chosen ?? "",
          alternatives_considered: (fields.alternatives_considered ?? "")
            .split(",")
            .map((s) => s.trim())
            .filter(Boolean),
          rationale: fields.rationale ?? "",
        };
      case "convention":
        return {
          kind,
          subject: fields.subject ?? "",
          rule: fields.rule ?? "",
          example: fields.example || undefined,
        };
      case "constraint":
        return {
          kind,
          subject: fields.subject ?? "",
          rule: fields.rule ?? "",
          rationale: fields.rationale || undefined,
          severity: fields.severity ?? "soft",
        };
      case "domain_concept":
        return {
          kind,
          term: fields.term ?? "",
          definition: fields.definition ?? "",
          related_terms: (fields.related_terms ?? "")
            .split(",")
            .map((s) => s.trim())
            .filter(Boolean),
        };
      case "technical_fact":
        return {
          kind,
          subject: fields.subject ?? "",
          fact: fields.fact ?? "",
          verified_at: fields.verified_at || undefined,
        };
      case "known_issue":
        return {
          kind,
          subject: fields.subject ?? "",
          description: fields.description ?? "",
          workaround: fields.workaround || undefined,
          status: fields.status || "open",
        };
    }
  };

  const handleCreate = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!selectedScopeRefId) return;
    try {
      await api.createKnowledgeItem({
        scope,
        scope_ref_id: selectedScopeRefId,
        content: buildContent(),
      });
      setFields({});
      setShowForm(false);
      api.listKnowledgeItems(scope, selectedScopeRefId).then(setItems);
    } catch {
      // form stays open with input intact
    }
  };

  if (loadError) {
    return (
      <div className="mx-auto max-w-2xl p-8">
        <p className="text-red-600">Couldn't load this page. It may have been deleted.</p>
        <Link to="/" className="text-sm underline">
          Back to Products
        </Link>
      </div>
    );
  }

  if (!product) return null;

  return (
    <div className="mx-auto max-w-2xl p-8">
      <Breadcrumb
        items={[
          { label: "Products", to: "/" },
          { label: product.name, to: `/products/${product.id}` },
          { label: "Knowledge", to: `/products/${product.id}/knowledge` },
        ]}
      />

      <h1 className="mb-4 text-2xl font-semibold">{product.name} — Knowledge</h1>

      <div className="mb-4 flex items-center justify-between gap-2">
        <select
          className="rounded border px-2 py-1"
          value={selectedScopeRefId}
          onChange={(event) => setSelectedScopeRefId(event.target.value)}
        >
          <option value={product.id}>Product-level</option>
          {projects.map((project) => (
            <option key={project.id} value={project.id}>
              Project: {project.name}
            </option>
          ))}
        </select>
        <Button onClick={() => setShowForm((value) => !value)}>New Knowledge Item</Button>
      </div>

      {showForm && (
        <form onSubmit={handleCreate} className="mb-6 flex flex-col gap-2 rounded border p-4">
          <select
            className="rounded border px-2 py-1"
            value={kind}
            onChange={(event) => {
              setKind(event.target.value as ContentKind);
              setFields({});
            }}
          >
            <option value="decision">Decision</option>
            <option value="convention">Convention</option>
            <option value="constraint">Constraint</option>
            <option value="domain_concept">Domain Concept</option>
            <option value="technical_fact">Technical Fact</option>
            <option value="known_issue">Known Issue</option>
          </select>

          {kind === "decision" && (
            <>
              <input
                className="rounded border px-2 py-1"
                placeholder="Subject"
                value={fields.subject ?? ""}
                onChange={(event) => setField("subject", event.target.value)}
                required
              />
              <input
                className="rounded border px-2 py-1"
                placeholder="Chosen"
                value={fields.chosen ?? ""}
                onChange={(event) => setField("chosen", event.target.value)}
                required
              />
              <input
                className="rounded border px-2 py-1"
                placeholder="Alternatives considered (comma-separated)"
                value={fields.alternatives_considered ?? ""}
                onChange={(event) => setField("alternatives_considered", event.target.value)}
              />
              <input
                className="rounded border px-2 py-1"
                placeholder="Rationale"
                value={fields.rationale ?? ""}
                onChange={(event) => setField("rationale", event.target.value)}
                required
              />
            </>
          )}

          {kind === "convention" && (
            <>
              <input
                className="rounded border px-2 py-1"
                placeholder="Subject"
                value={fields.subject ?? ""}
                onChange={(event) => setField("subject", event.target.value)}
                required
              />
              <input
                className="rounded border px-2 py-1"
                placeholder="Rule"
                value={fields.rule ?? ""}
                onChange={(event) => setField("rule", event.target.value)}
                required
              />
              <input
                className="rounded border px-2 py-1"
                placeholder="Example (optional)"
                value={fields.example ?? ""}
                onChange={(event) => setField("example", event.target.value)}
              />
            </>
          )}

          {kind === "constraint" && (
            <>
              <input
                className="rounded border px-2 py-1"
                placeholder="Subject"
                value={fields.subject ?? ""}
                onChange={(event) => setField("subject", event.target.value)}
                required
              />
              <input
                className="rounded border px-2 py-1"
                placeholder="Rule"
                value={fields.rule ?? ""}
                onChange={(event) => setField("rule", event.target.value)}
                required
              />
              <input
                className="rounded border px-2 py-1"
                placeholder="Rationale (optional)"
                value={fields.rationale ?? ""}
                onChange={(event) => setField("rationale", event.target.value)}
              />
              <select
                className="rounded border px-2 py-1"
                value={fields.severity ?? "soft"}
                onChange={(event) => setField("severity", event.target.value)}
              >
                <option value="hard">Hard</option>
                <option value="soft">Soft</option>
              </select>
            </>
          )}

          {kind === "domain_concept" && (
            <>
              <input
                className="rounded border px-2 py-1"
                placeholder="Term"
                value={fields.term ?? ""}
                onChange={(event) => setField("term", event.target.value)}
                required
              />
              <input
                className="rounded border px-2 py-1"
                placeholder="Definition"
                value={fields.definition ?? ""}
                onChange={(event) => setField("definition", event.target.value)}
                required
              />
              <input
                className="rounded border px-2 py-1"
                placeholder="Related terms (comma-separated)"
                value={fields.related_terms ?? ""}
                onChange={(event) => setField("related_terms", event.target.value)}
              />
            </>
          )}

          {kind === "technical_fact" && (
            <>
              <input
                className="rounded border px-2 py-1"
                placeholder="Subject"
                value={fields.subject ?? ""}
                onChange={(event) => setField("subject", event.target.value)}
                required
              />
              <input
                className="rounded border px-2 py-1"
                placeholder="Fact"
                value={fields.fact ?? ""}
                onChange={(event) => setField("fact", event.target.value)}
                required
              />
              <input
                className="rounded border px-2 py-1"
                type="date"
                value={fields.verified_at ?? ""}
                onChange={(event) => setField("verified_at", event.target.value)}
              />
            </>
          )}

          {kind === "known_issue" && (
            <>
              <input
                className="rounded border px-2 py-1"
                placeholder="Subject"
                value={fields.subject ?? ""}
                onChange={(event) => setField("subject", event.target.value)}
                required
              />
              <input
                className="rounded border px-2 py-1"
                placeholder="Description"
                value={fields.description ?? ""}
                onChange={(event) => setField("description", event.target.value)}
                required
              />
              <input
                className="rounded border px-2 py-1"
                placeholder="Workaround (optional)"
                value={fields.workaround ?? ""}
                onChange={(event) => setField("workaround", event.target.value)}
              />
            </>
          )}

          <Button type="submit">Create</Button>
        </form>
      )}

      <div className="flex flex-col gap-2">
        {items.map((item) => (
          <Card key={item.id}>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <span className="rounded bg-gray-100 px-2 py-0.5 text-xs font-mono">
                  {item.type}
                </span>
              </CardTitle>
            </CardHeader>
            <CardContent className="text-sm text-muted-foreground">{summarize(item)}</CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Add the route**

In `frontend/src/App.tsx`, add the import:

```tsx
import { ProductKnowledgePage } from "@/pages/ProductKnowledgePage";
```

and add this route inside `<Routes>`:

```tsx
        <Route path="/products/:productId/knowledge" element={<ProductKnowledgePage />} />
```

- [ ] **Step 4: Link to Knowledge from the Product detail page**

In `frontend/src/pages/ProductDetailPage.tsx`, find this block (added by Phase 2):

```tsx
        <div className="flex items-center gap-2">
          <Link to={`/products/${product.id}/settings`} className="text-sm underline">
            Settings
          </Link>
          <Button onClick={() => setShowForm((value) => !value)}>New Initiative</Button>
        </div>
```

Replace it with:

```tsx
        <div className="flex items-center gap-2">
          <Link to={`/products/${product.id}/settings`} className="text-sm underline">
            Settings
          </Link>
          <Link to={`/products/${product.id}/knowledge`} className="text-sm underline">
            Knowledge
          </Link>
          <Button onClick={() => setShowForm((value) => !value)}>New Initiative</Button>
        </div>
```

- [ ] **Step 5: Verify the build compiles**

Run: `cd frontend && npm run build`
Expected: exits 0, no TypeScript errors

- [ ] **Step 6: Manual smoke test**

Run: `npm run dev` (from `frontend/`, with the backend also running per the root README's instructions)
Open the app: go to a Product, click "Knowledge", create a Decision item and a Constraint item, switch the scope selector to a Project (if one exists) and confirm the list changes to show that scope's items, confirm each item's card shows the right type badge and one-line summary.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/lib/api.ts frontend/src/pages/ProductKnowledgePage.tsx frontend/src/App.tsx frontend/src/pages/ProductDetailPage.tsx
git commit -m "feat(frontend): add Product Knowledge page with dynamic per-type form"
```
