# Phase 1 Product Hierarchy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** CRUD for Product → Initiative → Epic → Feature, with auto-generated issue keys (`HAND-12`) on Features, plus a frontend that lets a user build and navigate that hierarchy through a breadcrumb.

**Architecture:** Four SQLAlchemy models sharing one migration, one flat-REST router per resource (parent filtering via query params, not nested URLs), and a computed (never stored) `issue_key` on Feature built from an atomically-incremented per-Product counter. Frontend gains its first real router (`react-router-dom`) and one page per hierarchy level, each with an inline create form and a breadcrumb built from route params.

**Tech Stack:** Same as Phase 0 (Python 3.12, uv, FastAPI, SQLAlchemy 2.0 async, Alembic, pytest) plus `aiosqlite` (test-only, in-memory DB — no local/homelab Postgres needed to run the backend suite) and `react-router-dom` on the frontend.

**Spec:** [docs/superpowers/specs/2026-09-05-phase1-product-hierarchy-design.md](../specs/2026-09-05-phase1-product-hierarchy-design.md)

## Global Constraints

- `issue_number` is assigned via one atomic `UPDATE products SET next_issue_number = next_issue_number + 1 ... RETURNING next_issue_number` per Feature insert — never a per-row Postgres sequence
- `issue_key` (`{key_prefix}-{issue_number}`) is computed at read time only, never stored
- API is flat REST with parent-id query params (`GET /initiatives?product_id=`), not nested URLs — the frontend's URL nesting is a separate, unrelated concern (browser navigation state only)
- Backend tests run against in-memory SQLite (`aiosqlite`), never the homelab Postgres — this phase's tables use only portable column types, so this is safe for now
- All new UUID primary/foreign key columns use a backend-agnostic `GUID` type (native `UUID` on Postgres, `CHAR(36)` elsewhere) so the same models work against SQLite in tests and Postgres in production
- `acceptance_criteria_format_default` / `acceptance_criteria_format` are plain `Text` columns (not a Postgres `ENUM`) in this phase — the stricter type lands when Phase 4 actually uses the value; this is a deliberate simplification, not an oversight
- `updated_at` refresh uses SQLAlchemy's ORM-level `onupdate=func.now()`, not a Postgres trigger — portable across SQLite/Postgres, unlike `schema.sql`'s trigger-based approach
- All repo content in English

---

### Task 1: Models, Migration, and Test Infrastructure

**Files:**
- Create: `backend/app/db_types.py`
- Create: `backend/app/models.py`
- Modify: `backend/alembic/env.py`
- Create: `backend/alembic/versions/0002_product_hierarchy.py`
- Modify: `backend/pyproject.toml`
- Modify: `backend/tests/conftest.py`
- Test: `backend/tests/test_models.py`

**Interfaces:**
- Produces: `app.models.Base` (declarative base, its `.metadata` used by both the migration's hand-written DDL — for reference — and the test fixture's `create_all`), `app.models.Product`, `.Initiative`, `.Epic`, `.Feature` (SQLAlchemy 2.0 mapped classes). `app.db_types.GUID` (portable UUID type). A `db_session` pytest fixture in `conftest.py` that Tasks 2 and 3 reuse verbatim — it creates a fresh in-memory SQLite engine per test, runs `Base.metadata.create_all`, and overrides `app.db.get_db` to yield a SQLite-backed session.

- [ ] **Step 1: Add the portable UUID type**

Create `backend/app/db_types.py`:

```python
import uuid

from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.types import CHAR, TypeDecorator


class GUID(TypeDecorator):
    """Platform-independent UUID: native UUID on PostgreSQL, CHAR(36)
    elsewhere (SQLite, used only in tests)."""

    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PG_UUID(as_uuid=True))
        return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        if dialect.name == "postgresql":
            return str(value)
        if not isinstance(value, uuid.UUID):
            return str(uuid.UUID(str(value)))
        return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        if not isinstance(value, uuid.UUID):
            return uuid.UUID(value)
        return value
```

- [ ] **Step 2: Write the models**

Create `backend/app/models.py`:

```python
import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from app.db_types import GUID


class Base(DeclarativeBase):
    pass


class Product(Base):
    __tablename__ = "products"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text, default=None)
    acceptance_criteria_format_default: Mapped[str] = mapped_column(Text, default="basic")
    key_prefix: Mapped[str] = mapped_column(Text)
    next_issue_number: Mapped[int] = mapped_column(default=1)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    initiatives: Mapped[list["Initiative"]] = relationship(
        back_populates="product", cascade="all, delete-orphan"
    )


class Initiative(Base):
    __tablename__ = "initiatives"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    product_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("products.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text, default=None)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    product: Mapped["Product"] = relationship(back_populates="initiatives")
    epics: Mapped[list["Epic"]] = relationship(back_populates="initiative", cascade="all, delete-orphan")


class Epic(Base):
    __tablename__ = "epics"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    initiative_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("initiatives.id", ondelete="CASCADE")
    )
    name: Mapped[str] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text, default=None)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    initiative: Mapped["Initiative"] = relationship(back_populates="epics")
    features: Mapped[list["Feature"]] = relationship(back_populates="epic", cascade="all, delete-orphan")


class Feature(Base):
    __tablename__ = "features"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    epic_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("epics.id", ondelete="CASCADE"))
    default_project_id: Mapped[uuid.UUID | None] = mapped_column(GUID, default=None)
    name: Mapped[str] = mapped_column(Text)
    requirements: Mapped[str | None] = mapped_column(Text, default=None)
    status: Mapped[str] = mapped_column(Text, default="draft")
    acceptance_criteria_format: Mapped[str] = mapped_column(Text, default="basic")
    issue_number: Mapped[int] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    epic: Mapped["Epic"] = relationship(back_populates="features")

    @property
    def issue_key(self) -> str:
        return f"{self.epic.initiative.product.key_prefix}-{self.issue_number}"
```

- [ ] **Step 3: Wire Alembic's `env.py` to the real metadata**

In `backend/alembic/env.py`, replace the line `target_metadata = None` with:

```python
from app.models import Base

target_metadata = Base.metadata
```

(Add the import near the existing `from app.config import settings` line; keep `target_metadata = Base.metadata` where `target_metadata = None` was.)

- [ ] **Step 4: Write the migration by hand**

Create `backend/alembic/versions/0002_product_hierarchy.py`:

```python
"""product hierarchy

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-05 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "products",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "acceptance_criteria_format_default",
            sa.Text(),
            nullable=False,
            server_default="basic",
        ),
        sa.Column("key_prefix", sa.Text(), nullable=False),
        sa.Column("next_issue_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )

    op.create_table(
        "initiatives",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "product_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("products.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )

    op.create_table(
        "epics",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "initiative_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("initiatives.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )

    op.create_table(
        "features",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "epic_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("epics.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("default_project_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("requirements", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default="draft"),
        sa.Column(
            "acceptance_criteria_format", sa.Text(), nullable=False, server_default="basic"
        ),
        sa.Column("issue_number", sa.Integer(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )


def downgrade() -> None:
    op.drop_table("features")
    op.drop_table("epics")
    op.drop_table("initiatives")
    op.drop_table("products")
```

- [ ] **Step 5: Verify the migration chain (no DB connection needed)**

Run: `cd backend && uv run alembic heads`
Expected: `0002 (head)`

- [ ] **Step 6: Add the test-only SQLite dependency**

In `backend/pyproject.toml`, add `"aiosqlite>=0.20"` to the `[dependency-groups]` `dev` list (alongside `pytest` and `httpx`). Then run: `uv sync`

- [ ] **Step 7: Build the shared test DB fixture**

Replace the contents of `backend/tests/conftest.py` with:

```python
import asyncio
import os

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test")

import pytest
from sqlalchemy import event
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.db import get_db
from app.main import app
from app.models import Base

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture
def db_session():
    engine = create_async_engine(
        TEST_DATABASE_URL,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine.sync_engine, "connect")
    def _enable_foreign_keys(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async def _create_tables():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    asyncio.run(_create_tables())

    session_maker = async_sessionmaker(engine, expire_on_commit=False)

    async def _override_get_db():
        async with session_maker() as session:
            yield session

    app.dependency_overrides[get_db] = _override_get_db
    yield
    app.dependency_overrides.clear()

    async def _dispose():
        await engine.dispose()

    asyncio.run(_dispose())
```

Note: the top of the file (`os.environ.setdefault("DATABASE_URL", ...)`) is unchanged from Phase 0 — `app.config.settings` still needs *a* value for `database_url` at import time even though the tests never touch that database (they use the SQLite `db_session` fixture instead).

- [ ] **Step 8: Write a test proving the fixture and models work together**

Create `backend/tests/test_models.py`:

```python
import asyncio

from sqlalchemy.orm import selectinload
from sqlalchemy import select

from app.db import get_db
from app.main import app
from app.models import Epic, Feature, Initiative, Product


def test_can_create_full_hierarchy_and_compute_issue_key(db_session):
    async def _run():
        override = app.dependency_overrides[get_db]
        async for session in override():
            product = Product(name="Handoff", key_prefix="HAND")
            session.add(product)
            await session.flush()

            initiative = Initiative(product_id=product.id, name="Core")
            session.add(initiative)
            await session.flush()

            epic = Epic(initiative_id=initiative.id, name="Auth")
            session.add(epic)
            await session.flush()

            feature = Feature(epic_id=epic.id, name="Login", issue_number=1)
            session.add(feature)
            await session.commit()

            result = await session.execute(
                select(Feature)
                .where(Feature.id == feature.id)
                .options(
                    selectinload(Feature.epic)
                    .selectinload(Epic.initiative)
                    .selectinload(Initiative.product)
                )
            )
            loaded = result.scalar_one()
            assert loaded.issue_key == "HAND-1"
            break

    asyncio.run(_run())
```

- [ ] **Step 9: Run the test to verify it passes**

Run: `uv run pytest tests/test_models.py -v` (from `backend/`)
Expected: `1 passed`

- [ ] **Step 10: Run the full backend suite**

Run: `uv run pytest -v` (from `backend/`)
Expected: `4 passed` (the existing 3 from Phase 0 plus this one)

- [ ] **Step 11: Commit**

```bash
git add backend/app/db_types.py backend/app/models.py backend/alembic/env.py backend/alembic/versions/0002_product_hierarchy.py backend/pyproject.toml backend/uv.lock backend/tests/conftest.py backend/tests/test_models.py
git commit -m "feat(backend): add product hierarchy models, migration, and SQLite test fixture"
```

---

### Task 2: Products, Initiatives, Epics CRUD

**Files:**
- Create: `backend/app/schemas.py`
- Create: `backend/app/routers/products.py`
- Create: `backend/app/routers/initiatives.py`
- Create: `backend/app/routers/epics.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_products.py`
- Test: `backend/tests/test_initiatives.py`
- Test: `backend/tests/test_epics.py`

**Interfaces:**
- Consumes: `app.models.Product/.Initiative/.Epic` (Task 1), the `db_session` fixture (Task 1)
- Produces: `app.schemas.ProductCreate/.ProductUpdate/.ProductRead`, `.InitiativeCreate/.InitiativeUpdate/.InitiativeRead`, `.EpicCreate/.EpicUpdate/.EpicRead` (Task 3 adds `Feature*` to the same file). Routers mounted at `/products`, `/initiatives`, `/epics` — Task 3's `/features` router follows the identical shape.

- [ ] **Step 1: Write the Pydantic schemas**

Create `backend/app/schemas.py`:

```python
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ProductCreate(BaseModel):
    name: str
    description: str | None = None
    key_prefix: str


class ProductUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    key_prefix: str | None = None


class ProductRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None
    key_prefix: str
    created_at: datetime
    updated_at: datetime


class InitiativeCreate(BaseModel):
    product_id: uuid.UUID
    name: str
    description: str | None = None


class InitiativeUpdate(BaseModel):
    name: str | None = None
    description: str | None = None


class InitiativeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    product_id: uuid.UUID
    name: str
    description: str | None
    created_at: datetime
    updated_at: datetime


class EpicCreate(BaseModel):
    initiative_id: uuid.UUID
    name: str
    description: str | None = None


class EpicUpdate(BaseModel):
    name: str | None = None
    description: str | None = None


class EpicRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    initiative_id: uuid.UUID
    name: str
    description: str | None
    created_at: datetime
    updated_at: datetime
```

- [ ] **Step 2: Write the failing Products tests**

Create `backend/tests/test_products.py`:

```python
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
```

- [ ] **Step 3: Run to verify it fails**

Run: `uv run pytest tests/test_products.py -v` (from `backend/`)
Expected: FAIL — `404 Not Found` on `POST /products` (route doesn't exist yet)

- [ ] **Step 4: Implement the Products router**

Create `backend/app/routers/products.py`:

```python
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import Product
from app.schemas import ProductCreate, ProductRead, ProductUpdate

router = APIRouter(prefix="/products", tags=["products"])


@router.get("", response_model=list[ProductRead])
async def list_products(db: AsyncSession = Depends(get_db)) -> list[Product]:
    result = await db.execute(select(Product).order_by(Product.created_at))
    return list(result.scalars().all())


@router.post("", response_model=ProductRead, status_code=201)
async def create_product(payload: ProductCreate, db: AsyncSession = Depends(get_db)) -> Product:
    product = Product(**payload.model_dump())
    db.add(product)
    await db.commit()
    await db.refresh(product)
    return product


@router.get("/{product_id}", response_model=ProductRead)
async def get_product(product_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> Product:
    product = await db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


@router.patch("/{product_id}", response_model=ProductRead)
async def update_product(
    product_id: uuid.UUID, payload: ProductUpdate, db: AsyncSession = Depends(get_db)
) -> Product:
    product = await db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(product, field, value)
    await db.commit()
    await db.refresh(product)
    return product


@router.delete("/{product_id}", status_code=204)
async def delete_product(product_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> None:
    product = await db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    await db.delete(product)
    await db.commit()
```

- [ ] **Step 5: Wire the router into the app**

In `backend/app/main.py`, add:

```python
from app.routers.products import router as products_router
```

next to the existing `from app.routers.health import router as health_router`, and add:

```python
app.include_router(products_router)
```

next to `app.include_router(health_router)`.

- [ ] **Step 6: Run Products tests to verify they pass**

Run: `uv run pytest tests/test_products.py -v` (from `backend/`)
Expected: `5 passed`

- [ ] **Step 7: Write the failing Initiatives tests**

Create `backend/tests/test_initiatives.py`:

```python
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _create_product() -> str:
    response = client.post("/products", json={"name": "Handoff", "key_prefix": "HAND"})
    return response.json()["id"]


def test_create_and_get_initiative(db_session):
    product_id = _create_product()

    response = client.post("/initiatives", json={"product_id": product_id, "name": "Core"})
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Core"
    assert body["product_id"] == product_id

    response = client.get(f"/initiatives/{body['id']}")
    assert response.status_code == 200


def test_list_initiatives_filtered_by_product(db_session):
    product_a = _create_product()
    product_b = _create_product()

    client.post("/initiatives", json={"product_id": product_a, "name": "A1"})
    client.post("/initiatives", json={"product_id": product_b, "name": "B1"})

    response = client.get(f"/initiatives?product_id={product_a}")
    assert response.status_code == 200
    names = [i["name"] for i in response.json()]
    assert names == ["A1"]


def test_get_initiative_not_found(db_session):
    response = client.get("/initiatives/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404


def test_update_initiative(db_session):
    product_id = _create_product()
    response = client.post("/initiatives", json={"product_id": product_id, "name": "Old"})
    initiative_id = response.json()["id"]

    response = client.patch(f"/initiatives/{initiative_id}", json={"name": "New"})
    assert response.status_code == 200
    assert response.json()["name"] == "New"


def test_delete_initiative(db_session):
    product_id = _create_product()
    response = client.post("/initiatives", json={"product_id": product_id, "name": "Temp"})
    initiative_id = response.json()["id"]

    response = client.delete(f"/initiatives/{initiative_id}")
    assert response.status_code == 204

    response = client.get(f"/initiatives/{initiative_id}")
    assert response.status_code == 404
```

- [ ] **Step 8: Run to verify it fails**

Run: `uv run pytest tests/test_initiatives.py -v` (from `backend/`)
Expected: FAIL — `404 Not Found` on `POST /initiatives`

- [ ] **Step 9: Implement the Initiatives router**

Create `backend/app/routers/initiatives.py`:

```python
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import Initiative
from app.schemas import InitiativeCreate, InitiativeRead, InitiativeUpdate

router = APIRouter(prefix="/initiatives", tags=["initiatives"])


@router.get("", response_model=list[InitiativeRead])
async def list_initiatives(
    product_id: uuid.UUID = Query(...), db: AsyncSession = Depends(get_db)
) -> list[Initiative]:
    result = await db.execute(
        select(Initiative).where(Initiative.product_id == product_id).order_by(Initiative.created_at)
    )
    return list(result.scalars().all())


@router.post("", response_model=InitiativeRead, status_code=201)
async def create_initiative(
    payload: InitiativeCreate, db: AsyncSession = Depends(get_db)
) -> Initiative:
    initiative = Initiative(**payload.model_dump())
    db.add(initiative)
    await db.commit()
    await db.refresh(initiative)
    return initiative


@router.get("/{initiative_id}", response_model=InitiativeRead)
async def get_initiative(initiative_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> Initiative:
    initiative = await db.get(Initiative, initiative_id)
    if initiative is None:
        raise HTTPException(status_code=404, detail="Initiative not found")
    return initiative


@router.patch("/{initiative_id}", response_model=InitiativeRead)
async def update_initiative(
    initiative_id: uuid.UUID, payload: InitiativeUpdate, db: AsyncSession = Depends(get_db)
) -> Initiative:
    initiative = await db.get(Initiative, initiative_id)
    if initiative is None:
        raise HTTPException(status_code=404, detail="Initiative not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(initiative, field, value)
    await db.commit()
    await db.refresh(initiative)
    return initiative


@router.delete("/{initiative_id}", status_code=204)
async def delete_initiative(initiative_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> None:
    initiative = await db.get(Initiative, initiative_id)
    if initiative is None:
        raise HTTPException(status_code=404, detail="Initiative not found")
    await db.delete(initiative)
    await db.commit()
```

- [ ] **Step 10: Wire the router into the app**

In `backend/app/main.py`, add the import and `app.include_router(initiatives_router)` the same way as Step 5.

- [ ] **Step 11: Run Initiatives tests to verify they pass**

Run: `uv run pytest tests/test_initiatives.py -v` (from `backend/`)
Expected: `5 passed`

- [ ] **Step 12: Write the failing Epics tests**

Create `backend/tests/test_epics.py`:

```python
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
```

- [ ] **Step 13: Run to verify it fails**

Run: `uv run pytest tests/test_epics.py -v` (from `backend/`)
Expected: FAIL — `404 Not Found` on `POST /epics`

- [ ] **Step 14: Implement the Epics router**

Create `backend/app/routers/epics.py`:

```python
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import Epic
from app.schemas import EpicCreate, EpicRead, EpicUpdate

router = APIRouter(prefix="/epics", tags=["epics"])


@router.get("", response_model=list[EpicRead])
async def list_epics(
    initiative_id: uuid.UUID = Query(...), db: AsyncSession = Depends(get_db)
) -> list[Epic]:
    result = await db.execute(
        select(Epic).where(Epic.initiative_id == initiative_id).order_by(Epic.created_at)
    )
    return list(result.scalars().all())


@router.post("", response_model=EpicRead, status_code=201)
async def create_epic(payload: EpicCreate, db: AsyncSession = Depends(get_db)) -> Epic:
    epic = Epic(**payload.model_dump())
    db.add(epic)
    await db.commit()
    await db.refresh(epic)
    return epic


@router.get("/{epic_id}", response_model=EpicRead)
async def get_epic(epic_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> Epic:
    epic = await db.get(Epic, epic_id)
    if epic is None:
        raise HTTPException(status_code=404, detail="Epic not found")
    return epic


@router.patch("/{epic_id}", response_model=EpicRead)
async def update_epic(epic_id: uuid.UUID, payload: EpicUpdate, db: AsyncSession = Depends(get_db)) -> Epic:
    epic = await db.get(Epic, epic_id)
    if epic is None:
        raise HTTPException(status_code=404, detail="Epic not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(epic, field, value)
    await db.commit()
    await db.refresh(epic)
    return epic


@router.delete("/{epic_id}", status_code=204)
async def delete_epic(epic_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> None:
    epic = await db.get(Epic, epic_id)
    if epic is None:
        raise HTTPException(status_code=404, detail="Epic not found")
    await db.delete(epic)
    await db.commit()
```

- [ ] **Step 15: Wire the router into the app**

Same pattern as Step 5/10, importing and including `epics_router` in `backend/app/main.py`.

- [ ] **Step 16: Run the full backend suite**

Run: `uv run pytest -v` (from `backend/`)
Expected: `19 passed` (4 from before + 5 Products + 5 Initiatives + 5 Epics)

- [ ] **Step 17: Commit**

```bash
git add backend/app/schemas.py backend/app/routers/products.py backend/app/routers/initiatives.py backend/app/routers/epics.py backend/app/main.py backend/tests/test_products.py backend/tests/test_initiatives.py backend/tests/test_epics.py
git commit -m "feat(backend): add Products, Initiatives, Epics CRUD"
```

---

### Task 3: Features CRUD with Issue Numbering

**Files:**
- Modify: `backend/app/schemas.py`
- Create: `backend/app/routers/features.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_features.py`

**Interfaces:**
- Consumes: `app.models.Feature/.Epic/.Initiative/.Product` (Task 1), `app.schemas.*` (Task 2's file, appending to it)
- Produces: `app.schemas.FeatureCreate/.FeatureUpdate/.FeatureRead` (the last one carries computed `issue_key: str`). Router mounted at `/features` — consumed by the frontend (Task 5) via `GET/POST /features`.

- [ ] **Step 1: Add the Feature schemas**

Append to `backend/app/schemas.py`:

```python


class FeatureCreate(BaseModel):
    epic_id: uuid.UUID
    name: str
    requirements: str | None = None


class FeatureUpdate(BaseModel):
    name: str | None = None
    requirements: str | None = None
    status: str | None = None


class FeatureRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    epic_id: uuid.UUID
    name: str
    requirements: str | None
    status: str
    acceptance_criteria_format: str
    issue_number: int
    issue_key: str
    created_at: datetime
    updated_at: datetime
```

- [ ] **Step 2: Write the failing Features tests**

Create `backend/tests/test_features.py`:

```python
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _create_epic(key_prefix: str = "HAND") -> str:
    product = client.post("/products", json={"name": "Handoff", "key_prefix": key_prefix}).json()
    initiative = client.post(
        "/initiatives", json={"product_id": product["id"], "name": "Core"}
    ).json()
    epic = client.post("/epics", json={"initiative_id": initiative["id"], "name": "Auth"}).json()
    return epic["id"]


def test_create_and_get_feature(db_session):
    epic_id = _create_epic()

    response = client.post("/features", json={"epic_id": epic_id, "name": "Login"})
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Login"
    assert body["issue_number"] == 1
    assert body["issue_key"] == "HAND-1"

    response = client.get(f"/features/{body['id']}")
    assert response.status_code == 200
    assert response.json()["issue_key"] == "HAND-1"


def test_feature_issue_numbers_increment_per_product(db_session):
    epic_id = _create_epic(key_prefix="HAND")

    first = client.post("/features", json={"epic_id": epic_id, "name": "First"}).json()
    second = client.post("/features", json={"epic_id": epic_id, "name": "Second"}).json()

    assert first["issue_number"] == 1
    assert second["issue_number"] == 2
    assert first["issue_key"] == "HAND-1"
    assert second["issue_key"] == "HAND-2"


def test_feature_issue_numbers_independent_per_product(db_session):
    epic_a = _create_epic(key_prefix="AAA")
    epic_b = _create_epic(key_prefix="BBB")

    feature_a = client.post("/features", json={"epic_id": epic_a, "name": "A1"}).json()
    feature_b = client.post("/features", json={"epic_id": epic_b, "name": "B1"}).json()

    assert feature_a["issue_number"] == 1
    assert feature_b["issue_number"] == 1
    assert feature_a["issue_key"] == "AAA-1"
    assert feature_b["issue_key"] == "BBB-1"


def test_list_features_filtered_by_epic(db_session):
    epic_a = _create_epic()
    epic_b = _create_epic()

    client.post("/features", json={"epic_id": epic_a, "name": "A1"})
    client.post("/features", json={"epic_id": epic_b, "name": "B1"})

    response = client.get(f"/features?epic_id={epic_a}")
    assert response.status_code == 200
    names = [f["name"] for f in response.json()]
    assert names == ["A1"]


def test_get_feature_not_found(db_session):
    response = client.get("/features/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404


def test_update_feature(db_session):
    epic_id = _create_epic()
    response = client.post("/features", json={"epic_id": epic_id, "name": "Old"})
    feature_id = response.json()["id"]

    response = client.patch(f"/features/{feature_id}", json={"name": "New", "status": "ready"})
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "New"
    assert body["status"] == "ready"
    assert body["issue_number"] == 1


def test_delete_feature(db_session):
    epic_id = _create_epic()
    response = client.post("/features", json={"epic_id": epic_id, "name": "Temp"})
    feature_id = response.json()["id"]

    response = client.delete(f"/features/{feature_id}")
    assert response.status_code == 204

    response = client.get(f"/features/{feature_id}")
    assert response.status_code == 404
```

- [ ] **Step 3: Run to verify it fails**

Run: `uv run pytest tests/test_features.py -v` (from `backend/`)
Expected: FAIL — `404 Not Found` on `POST /features`

- [ ] **Step 4: Implement the Features router**

Create `backend/app/routers/features.py`:

```python
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db import get_db
from app.models import Epic, Feature, Initiative, Product
from app.schemas import FeatureCreate, FeatureRead, FeatureUpdate

router = APIRouter(prefix="/features", tags=["features"])

_EAGER_LOAD = (
    selectinload(Feature.epic).selectinload(Epic.initiative).selectinload(Initiative.product)
)


@router.get("", response_model=list[FeatureRead])
async def list_features(
    epic_id: uuid.UUID = Query(...), db: AsyncSession = Depends(get_db)
) -> list[Feature]:
    result = await db.execute(
        select(Feature).where(Feature.epic_id == epic_id).options(_EAGER_LOAD).order_by(Feature.created_at)
    )
    return list(result.scalars().all())


@router.post("", response_model=FeatureRead, status_code=201)
async def create_feature(payload: FeatureCreate, db: AsyncSession = Depends(get_db)) -> Feature:
    epic = await db.get(Epic, payload.epic_id)
    if epic is None:
        raise HTTPException(status_code=404, detail="Epic not found")

    initiative = await db.get(Initiative, epic.initiative_id)
    if initiative is None:
        raise HTTPException(status_code=404, detail="Initiative not found")

    result = await db.execute(
        update(Product)
        .where(Product.id == initiative.product_id)
        .values(next_issue_number=Product.next_issue_number + 1)
        .returning(Product.next_issue_number)
    )
    new_issue_number = result.scalar_one() - 1

    feature = Feature(
        epic_id=payload.epic_id,
        name=payload.name,
        requirements=payload.requirements,
        issue_number=new_issue_number,
    )
    db.add(feature)
    await db.commit()

    result = await db.execute(select(Feature).where(Feature.id == feature.id).options(_EAGER_LOAD))
    return result.scalar_one()


@router.get("/{feature_id}", response_model=FeatureRead)
async def get_feature(feature_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> Feature:
    result = await db.execute(
        select(Feature).where(Feature.id == feature_id).options(_EAGER_LOAD)
    )
    feature = result.scalar_one_or_none()
    if feature is None:
        raise HTTPException(status_code=404, detail="Feature not found")
    return feature


@router.patch("/{feature_id}", response_model=FeatureRead)
async def update_feature(
    feature_id: uuid.UUID, payload: FeatureUpdate, db: AsyncSession = Depends(get_db)
) -> Feature:
    feature = await db.get(Feature, feature_id)
    if feature is None:
        raise HTTPException(status_code=404, detail="Feature not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(feature, field, value)
    await db.commit()

    result = await db.execute(
        select(Feature).where(Feature.id == feature_id).options(_EAGER_LOAD)
    )
    return result.scalar_one()


@router.delete("/{feature_id}", status_code=204)
async def delete_feature(feature_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> None:
    feature = await db.get(Feature, feature_id)
    if feature is None:
        raise HTTPException(status_code=404, detail="Feature not found")
    await db.delete(feature)
    await db.commit()
```

- [ ] **Step 5: Wire the router into the app**

Same pattern as Task 2, importing and including `features_router` in `backend/app/main.py`.

- [ ] **Step 6: Run Features tests to verify they pass**

Run: `uv run pytest tests/test_features.py -v` (from `backend/`)
Expected: `7 passed`

- [ ] **Step 7: Run the full backend suite**

Run: `uv run pytest -v` (from `backend/`)
Expected: `26 passed`

- [ ] **Step 8: Commit**

```bash
git add backend/app/schemas.py backend/app/routers/features.py backend/app/main.py backend/tests/test_features.py
git commit -m "feat(backend): add Features CRUD with atomic issue numbering"
```

---

### Task 4: Frontend Routing, API Client, and Products Page

**Files:**
- Modify: `frontend/package.json` (via `npm install`)
- Create: `frontend/src/lib/api.ts`
- Create: `frontend/src/components/Breadcrumb.tsx`
- Create: `frontend/src/pages/ProductsPage.tsx`
- Create: `frontend/src/pages/HealthPage.tsx`
- Modify: `frontend/src/App.tsx`

**Interfaces:**
- Produces: `api` object (`frontend/src/lib/api.ts`) with `listProducts`, `createProduct`, `getProduct`, `listInitiatives`, `createInitiative`, `getInitiative`, `listEpics`, `createEpic`, `getEpic`, `listFeatures`, `createFeature` — Task 5's pages consume all of these except the Product ones, which this task's `ProductsPage` already uses. `Breadcrumb` component (`items: {label, to}[]` prop) — consumed by Task 5's three detail pages.

- [ ] **Step 1: Install the router**

Run: `cd frontend && npm install react-router-dom`
Expected: exits 0, adds `react-router-dom` to `package.json` dependencies.

- [ ] **Step 2: Write the API client**

Create `frontend/src/lib/api.ts`:

```typescript
const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export interface Product {
  id: string;
  name: string;
  description: string | null;
  key_prefix: string;
  created_at: string;
  updated_at: string;
}

export interface Initiative {
  id: string;
  product_id: string;
  name: string;
  description: string | null;
  created_at: string;
  updated_at: string;
}

export interface Epic {
  id: string;
  initiative_id: string;
  name: string;
  description: string | null;
  created_at: string;
  updated_at: string;
}

export interface Feature {
  id: string;
  epic_id: string;
  name: string;
  requirements: string | null;
  status: string;
  acceptance_criteria_format: string;
  issue_number: number;
  issue_key: string;
  created_at: string;
  updated_at: string;
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!response.ok) {
    throw new Error(`Request to ${path} failed with status ${response.status}`);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return response.json() as Promise<T>;
}

export const api = {
  listProducts: () => request<Product[]>("/products"),
  createProduct: (data: { name: string; description?: string; key_prefix: string }) =>
    request<Product>("/products", { method: "POST", body: JSON.stringify(data) }),
  getProduct: (id: string) => request<Product>(`/products/${id}`),

  listInitiatives: (productId: string) =>
    request<Initiative[]>(`/initiatives?product_id=${productId}`),
  createInitiative: (data: { product_id: string; name: string; description?: string }) =>
    request<Initiative>("/initiatives", { method: "POST", body: JSON.stringify(data) }),
  getInitiative: (id: string) => request<Initiative>(`/initiatives/${id}`),

  listEpics: (initiativeId: string) => request<Epic[]>(`/epics?initiative_id=${initiativeId}`),
  createEpic: (data: { initiative_id: string; name: string; description?: string }) =>
    request<Epic>("/epics", { method: "POST", body: JSON.stringify(data) }),
  getEpic: (id: string) => request<Epic>(`/epics/${id}`),

  listFeatures: (epicId: string) => request<Feature[]>(`/features?epic_id=${epicId}`),
  createFeature: (data: { epic_id: string; name: string; requirements?: string }) =>
    request<Feature>("/features", { method: "POST", body: JSON.stringify(data) }),
};
```

- [ ] **Step 3: Write the Breadcrumb component**

Create `frontend/src/components/Breadcrumb.tsx`:

```tsx
import { Link } from "react-router-dom";

export interface BreadcrumbItem {
  label: string;
  to: string;
}

export function Breadcrumb({ items }: { items: BreadcrumbItem[] }) {
  return (
    <nav className="mb-4 flex items-center gap-2 text-sm text-muted-foreground">
      {items.map((item, index) => (
        <span key={item.to} className="flex items-center gap-2">
          {index > 0 && <span>/</span>}
          <Link to={item.to} className="hover:text-foreground hover:underline">
            {item.label}
          </Link>
        </span>
      ))}
    </nav>
  );
}
```

- [ ] **Step 4: Write the Products page**

Create `frontend/src/pages/ProductsPage.tsx`:

```tsx
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api, type Product } from "@/lib/api";

export function ProductsPage() {
  const [products, setProducts] = useState<Product[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [name, setName] = useState("");
  const [keyPrefix, setKeyPrefix] = useState("");

  const loadProducts = () => {
    api.listProducts().then(setProducts);
  };

  useEffect(() => {
    loadProducts();
  }, []);

  const handleCreate = async (event: React.FormEvent) => {
    event.preventDefault();
    await api.createProduct({ name, key_prefix: keyPrefix });
    setName("");
    setKeyPrefix("");
    setShowForm(false);
    loadProducts();
  };

  return (
    <div className="mx-auto max-w-2xl p-8">
      <div className="mb-4 flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Products</h1>
        <Button onClick={() => setShowForm((value) => !value)}>New Product</Button>
      </div>

      {showForm && (
        <form onSubmit={handleCreate} className="mb-6 flex flex-col gap-2 rounded border p-4">
          <input
            className="rounded border px-2 py-1"
            placeholder="Name"
            value={name}
            onChange={(event) => setName(event.target.value)}
            required
          />
          <input
            className="rounded border px-2 py-1"
            placeholder="Key prefix (e.g. HAND)"
            value={keyPrefix}
            onChange={(event) => setKeyPrefix(event.target.value.toUpperCase())}
            required
          />
          <Button type="submit">Create</Button>
        </form>
      )}

      <div className="flex flex-col gap-2">
        {products.map((product) => (
          <Link key={product.id} to={`/products/${product.id}`}>
            <Card>
              <CardHeader>
                <CardTitle>{product.name}</CardTitle>
              </CardHeader>
              <CardContent className="text-sm text-muted-foreground">
                {product.key_prefix}
              </CardContent>
            </Card>
          </Link>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 5: Move the health check to its own page**

Create `frontend/src/pages/HealthPage.tsx` with exactly Phase 0's `App.tsx` content, renamed:

```tsx
import { useEffect, useState } from "react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

type HealthStatus = "checking" | "ok" | "error";

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export function HealthPage() {
  const [status, setStatus] = useState<HealthStatus>("checking");

  useEffect(() => {
    fetch(`${API_URL}/health`)
      .then((response) => setStatus(response.ok ? "ok" : "error"))
      .catch(() => setStatus("error"));
  }, []);

  const statusColor =
    status === "ok" ? "text-green-600" : status === "error" ? "text-red-600" : "text-gray-500";

  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50">
      <Card className="w-80">
        <CardHeader>
          <CardTitle>Handoff — Backend Health</CardTitle>
        </CardHeader>
        <CardContent>
          <p className={statusColor}>
            {status === "checking" && "Checking..."}
            {status === "ok" && "✓ Connected"}
            {status === "error" && "✗ Unreachable"}
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
```

- [ ] **Step 6: Wire the router in `App.tsx`**

Replace the contents of `frontend/src/App.tsx` with:

```tsx
import { BrowserRouter, Route, Routes } from "react-router-dom";

import { HealthPage } from "@/pages/HealthPage";
import { ProductsPage } from "@/pages/ProductsPage";

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<ProductsPage />} />
        <Route path="/health" element={<HealthPage />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
```

(Task 5 adds the three drill-down routes to this same file.)

- [ ] **Step 7: Verify the build compiles**

Run: `cd frontend && npm run build`
Expected: exits 0, no TypeScript errors

- [ ] **Step 8: Commit**

```bash
git add frontend/package.json frontend/package-lock.json frontend/src/lib/api.ts frontend/src/components/Breadcrumb.tsx frontend/src/pages/ProductsPage.tsx frontend/src/pages/HealthPage.tsx frontend/src/App.tsx
git commit -m "feat(frontend): add router, API client, and Products page"
```

---

### Task 5: Frontend Drill-Down Pages (Initiative, Epic, Feature)

**Files:**
- Create: `frontend/src/pages/ProductDetailPage.tsx`
- Create: `frontend/src/pages/InitiativeDetailPage.tsx`
- Create: `frontend/src/pages/EpicDetailPage.tsx`
- Modify: `frontend/src/App.tsx`

**Interfaces:**
- Consumes: `api` (Task 4's `frontend/src/lib/api.ts`), `Breadcrumb` (Task 4's `frontend/src/components/Breadcrumb.tsx`)
- Produces: nothing consumed by later tasks in this plan — this is the last task.

- [ ] **Step 1: Write the Product detail page (shows Initiatives)**

Create `frontend/src/pages/ProductDetailPage.tsx`:

```tsx
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { Breadcrumb } from "@/components/Breadcrumb";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { api, type Initiative, type Product } from "@/lib/api";

export function ProductDetailPage() {
  const { productId } = useParams<{ productId: string }>();
  const [product, setProduct] = useState<Product | null>(null);
  const [initiatives, setInitiatives] = useState<Initiative[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [name, setName] = useState("");

  const load = () => {
    if (!productId) return;
    api.getProduct(productId).then(setProduct);
    api.listInitiatives(productId).then(setInitiatives);
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [productId]);

  const handleCreate = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!productId) return;
    await api.createInitiative({ product_id: productId, name });
    setName("");
    setShowForm(false);
    load();
  };

  if (!product) return null;

  return (
    <div className="mx-auto max-w-2xl p-8">
      <Breadcrumb
        items={[
          { label: "Products", to: "/" },
          { label: product.name, to: `/products/${product.id}` },
        ]}
      />

      <div className="mb-4 flex items-center justify-between">
        <h1 className="text-2xl font-semibold">{product.name} — Initiatives</h1>
        <Button onClick={() => setShowForm((value) => !value)}>New Initiative</Button>
      </div>

      {showForm && (
        <form onSubmit={handleCreate} className="mb-6 flex flex-col gap-2 rounded border p-4">
          <input
            className="rounded border px-2 py-1"
            placeholder="Name"
            value={name}
            onChange={(event) => setName(event.target.value)}
            required
          />
          <Button type="submit">Create</Button>
        </form>
      )}

      <div className="flex flex-col gap-2">
        {initiatives.map((initiative) => (
          <Link key={initiative.id} to={`/products/${product.id}/initiatives/${initiative.id}`}>
            <Card>
              <CardHeader>
                <CardTitle>{initiative.name}</CardTitle>
              </CardHeader>
            </Card>
          </Link>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Write the Initiative detail page (shows Epics)**

Create `frontend/src/pages/InitiativeDetailPage.tsx`:

```tsx
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { Breadcrumb } from "@/components/Breadcrumb";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { api, type Epic, type Initiative, type Product } from "@/lib/api";

export function InitiativeDetailPage() {
  const { productId, initiativeId } = useParams<{ productId: string; initiativeId: string }>();
  const [product, setProduct] = useState<Product | null>(null);
  const [initiative, setInitiative] = useState<Initiative | null>(null);
  const [epics, setEpics] = useState<Epic[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [name, setName] = useState("");

  const load = () => {
    if (!productId || !initiativeId) return;
    api.getProduct(productId).then(setProduct);
    api.getInitiative(initiativeId).then(setInitiative);
    api.listEpics(initiativeId).then(setEpics);
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [productId, initiativeId]);

  const handleCreate = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!initiativeId) return;
    await api.createEpic({ initiative_id: initiativeId, name });
    setName("");
    setShowForm(false);
    load();
  };

  if (!product || !initiative) return null;

  return (
    <div className="mx-auto max-w-2xl p-8">
      <Breadcrumb
        items={[
          { label: "Products", to: "/" },
          { label: product.name, to: `/products/${product.id}` },
          { label: initiative.name, to: `/products/${product.id}/initiatives/${initiative.id}` },
        ]}
      />

      <div className="mb-4 flex items-center justify-between">
        <h1 className="text-2xl font-semibold">{initiative.name} — Epics</h1>
        <Button onClick={() => setShowForm((value) => !value)}>New Epic</Button>
      </div>

      {showForm && (
        <form onSubmit={handleCreate} className="mb-6 flex flex-col gap-2 rounded border p-4">
          <input
            className="rounded border px-2 py-1"
            placeholder="Name"
            value={name}
            onChange={(event) => setName(event.target.value)}
            required
          />
          <Button type="submit">Create</Button>
        </form>
      )}

      <div className="flex flex-col gap-2">
        {epics.map((epic) => (
          <Link
            key={epic.id}
            to={`/products/${product.id}/initiatives/${initiative.id}/epics/${epic.id}`}
          >
            <Card>
              <CardHeader>
                <CardTitle>{epic.name}</CardTitle>
              </CardHeader>
            </Card>
          </Link>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Write the Epic detail page (shows Features with issue key badges)**

Create `frontend/src/pages/EpicDetailPage.tsx`:

```tsx
import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";

import { Breadcrumb } from "@/components/Breadcrumb";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api, type Epic, type Feature, type Initiative, type Product } from "@/lib/api";

export function EpicDetailPage() {
  const { productId, initiativeId, epicId } = useParams<{
    productId: string;
    initiativeId: string;
    epicId: string;
  }>();
  const [product, setProduct] = useState<Product | null>(null);
  const [initiative, setInitiative] = useState<Initiative | null>(null);
  const [epic, setEpic] = useState<Epic | null>(null);
  const [features, setFeatures] = useState<Feature[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [name, setName] = useState("");

  const load = () => {
    if (!productId || !initiativeId || !epicId) return;
    api.getProduct(productId).then(setProduct);
    api.getInitiative(initiativeId).then(setInitiative);
    api.getEpic(epicId).then(setEpic);
    api.listFeatures(epicId).then(setFeatures);
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [productId, initiativeId, epicId]);

  const handleCreate = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!epicId) return;
    await api.createFeature({ epic_id: epicId, name });
    setName("");
    setShowForm(false);
    load();
  };

  if (!product || !initiative || !epic) return null;

  return (
    <div className="mx-auto max-w-2xl p-8">
      <Breadcrumb
        items={[
          { label: "Products", to: "/" },
          { label: product.name, to: `/products/${product.id}` },
          { label: initiative.name, to: `/products/${product.id}/initiatives/${initiative.id}` },
          {
            label: epic.name,
            to: `/products/${product.id}/initiatives/${initiative.id}/epics/${epic.id}`,
          },
        ]}
      />

      <div className="mb-4 flex items-center justify-between">
        <h1 className="text-2xl font-semibold">{epic.name} — Features</h1>
        <Button onClick={() => setShowForm((value) => !value)}>New Feature</Button>
      </div>

      {showForm && (
        <form onSubmit={handleCreate} className="mb-6 flex flex-col gap-2 rounded border p-4">
          <input
            className="rounded border px-2 py-1"
            placeholder="Name"
            value={name}
            onChange={(event) => setName(event.target.value)}
            required
          />
          <Button type="submit">Create</Button>
        </form>
      )}

      <div className="flex flex-col gap-2">
        {features.map((feature) => (
          <Card key={feature.id}>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <span className="rounded bg-blue-100 px-2 py-0.5 font-mono text-xs text-blue-800">
                  {feature.issue_key}
                </span>
                {feature.name}
              </CardTitle>
            </CardHeader>
            <CardContent className="text-sm text-muted-foreground">{feature.status}</CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Add the three drill-down routes**

In `frontend/src/App.tsx`, add the imports:

```tsx
import { EpicDetailPage } from "@/pages/EpicDetailPage";
import { InitiativeDetailPage } from "@/pages/InitiativeDetailPage";
import { ProductDetailPage } from "@/pages/ProductDetailPage";
```

and add these routes inside `<Routes>`, alongside the existing `/` and `/health`:

```tsx
        <Route path="/products/:productId" element={<ProductDetailPage />} />
        <Route
          path="/products/:productId/initiatives/:initiativeId"
          element={<InitiativeDetailPage />}
        />
        <Route
          path="/products/:productId/initiatives/:initiativeId/epics/:epicId"
          element={<EpicDetailPage />}
        />
```

- [ ] **Step 5: Verify the build compiles**

Run: `cd frontend && npm run build`
Expected: exits 0, no TypeScript errors

- [ ] **Step 6: Manual smoke test**

Run: `npm run dev` (from `frontend/`, with the backend also running per its own README instructions)
Open the app in a browser: create a Product, click into it, create an Initiative, click into it, create an Epic, click into it, create a Feature. Expected: breadcrumb grows at each level, the Feature shows an `issue_key` badge like `HAND-1`.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/pages/ProductDetailPage.tsx frontend/src/pages/InitiativeDetailPage.tsx frontend/src/pages/EpicDetailPage.tsx frontend/src/App.tsx
git commit -m "feat(frontend): add Initiative, Epic, Feature drill-down pages"
```
