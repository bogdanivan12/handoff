# Phase 2 Project & Sprint Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** CRUD for Project and Sprint, both scoped to a Product (not nested under Initiative/Epic/Feature), plus the `features.default_project_id → projects.id` foreign key that Phase 1 deliberately deferred until `projects` existed.

**Architecture:** Two new SQLAlchemy models (`Project`, `Sprint`) following the exact same shape as Phase 1's `Initiative`/`Epic`, one migration, two flat-REST routers, and one new frontend page (`ProductSettingsPage`) reachable from a "Settings" link on the existing `ProductDetailPage`. No new business logic — no counters, no computed fields, unlike Phase 1's Feature.

**Tech Stack:** Same as Phase 1 — no new dependencies needed on either side.

**Spec:** [docs/superpowers/specs/2026-09-05-phase2-project-sprint-design.md](../specs/2026-09-05-phase2-project-sprint-design.md)

## Global Constraints

- `Sprint.status` is a plain `Text` column (`planned`/`active`/`completed`), default `"planned"` — no Postgres `ENUM`, same simplification Phase 1 used for `Feature.status`
- `Sprint.start_date`/`end_date` are nullable `Date` columns — no validation that start ≤ end in this phase
- `features.default_project_id` gets its FK constraint (`ON DELETE SET NULL`) in this phase's migration — no UI to set it yet, DB-level only
- `POST /projects` and `POST /sprints` both check the parent Product exists first and return 404 (not a raw 500), matching the pattern Phase 1's final review established for `POST /initiatives`/`POST /epics`
- All repo content in English

---

### Task 1: Project and Sprint Models, Migration, FK Fix

**Files:**
- Modify: `backend/app/models.py`
- Create: `backend/alembic/versions/0003_project_sprint.py`
- Modify: `backend/tests/test_models.py`

**Interfaces:**
- Produces: `app.models.Project`, `app.models.Sprint` (both with a `product_id` FK and a `product` relationship). `Feature.default_project_id` gains a real `ForeignKey("projects.id", ondelete="SET NULL")` (it was a bare `GUID` column with no constraint before). Consumed by Task 2's schemas/routers.

- [ ] **Step 1: Add the models**

In `backend/app/models.py`, add `Date` to the existing `from sqlalchemy import ...` line (it currently imports `ForeignKey, Text, func` — add `Date` to that same import) and `date` to the existing `from datetime import datetime` line (making it `from datetime import date, datetime`).

Add these two classes after `Epic` and before `Feature`:

```python
class Project(Base):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    product_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("products.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text, default=None)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    product: Mapped["Product"] = relationship(back_populates="projects")


class Sprint(Base):
    __tablename__ = "sprints"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    product_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("products.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(Text)
    start_date: Mapped[date | None] = mapped_column(Date, default=None)
    end_date: Mapped[date | None] = mapped_column(Date, default=None)
    status: Mapped[str] = mapped_column(Text, default="planned")
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    product: Mapped["Product"] = relationship(back_populates="sprints")
```

In the `Product` class, add these two relationships alongside the existing `initiatives` relationship:

```python
    projects: Mapped[list["Project"]] = relationship(
        back_populates="product", cascade="all, delete-orphan"
    )
    sprints: Mapped[list["Sprint"]] = relationship(
        back_populates="product", cascade="all, delete-orphan"
    )
```

In the `Feature` class, change the existing `default_project_id` line from:

```python
    default_project_id: Mapped[uuid.UUID | None] = mapped_column(GUID, default=None)
```

to:

```python
    default_project_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID, ForeignKey("projects.id", ondelete="SET NULL"), default=None
    )
```

- [ ] **Step 2: Write the migration**

Create `backend/alembic/versions/0003_project_sprint.py`:

```python
"""project and sprint

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-05 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "projects",
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
        "sprints",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "product_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("products.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default="planned"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )

    op.create_foreign_key(
        "fk_features_default_project_id",
        "features",
        "projects",
        ["default_project_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_features_default_project_id", "features", type_="foreignkey")
    op.drop_table("sprints")
    op.drop_table("projects")
```

- [ ] **Step 3: Verify the migration chain (no DB connection needed)**

Run: `cd backend && uv run alembic heads`
Expected: `0003 (head)`

- [ ] **Step 4: Write a test proving the models and the new FK work together**

Append to `backend/tests/test_models.py` (add `Project, Sprint` to the existing `from app.models import Epic, Feature, Initiative, Product` import line):

```python


def test_can_create_project_and_sprint_and_link_feature_default_project(db_session):
    async def _run():
        override = app.dependency_overrides[get_db]
        async for session in override():
            product = Product(name="Handoff", key_prefix="HAND")
            session.add(product)
            await session.flush()

            project = Project(product_id=product.id, name="Web App")
            sprint = Sprint(product_id=product.id, name="Sprint 1")
            session.add_all([project, sprint])
            await session.flush()

            initiative = Initiative(product_id=product.id, name="Core")
            session.add(initiative)
            await session.flush()

            epic = Epic(initiative_id=initiative.id, name="Auth")
            session.add(epic)
            await session.flush()

            feature = Feature(
                epic_id=epic.id, name="Login", issue_number=1, default_project_id=project.id
            )
            session.add(feature)
            await session.commit()

            result = await session.execute(select(Feature).where(Feature.id == feature.id))
            loaded = result.scalar_one()
            assert loaded.default_project_id == project.id
            break

    asyncio.run(_run())
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `uv run pytest tests/test_models.py -v` (from `backend/`)
Expected: `2 passed`

- [ ] **Step 6: Run the full backend suite**

Run: `uv run pytest -v` (from `backend/`)
Expected: `32 passed` (31 from Phase 1 + this one new test)

- [ ] **Step 7: Commit**

```bash
git add backend/app/models.py backend/alembic/versions/0003_project_sprint.py backend/tests/test_models.py
git commit -m "feat(backend): add Project and Sprint models, migration, and features.default_project_id FK"
```

---

### Task 2: Projects and Sprints CRUD

**Files:**
- Modify: `backend/app/schemas.py`
- Create: `backend/app/routers/projects.py`
- Create: `backend/app/routers/sprints.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_projects.py`
- Test: `backend/tests/test_sprints.py`

**Interfaces:**
- Consumes: `app.models.Project/.Sprint/.Product` (Task 1)
- Produces: `app.schemas.ProjectCreate/.ProjectUpdate/.ProjectRead`, `.SprintCreate/.SprintUpdate/.SprintRead`. Routers mounted at `/projects` and `/sprints` — consumed by Task 3's frontend API client.

- [ ] **Step 1: Add the schemas**

Add `date` to `backend/app/schemas.py`'s existing `from datetime import datetime` line (making it `from datetime import date, datetime`). Then append:

```python


class ProjectCreate(BaseModel):
    product_id: uuid.UUID
    name: str
    description: str | None = None


class ProjectUpdate(BaseModel):
    name: str | None = None
    description: str | None = None


class ProjectRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    product_id: uuid.UUID
    name: str
    description: str | None
    created_at: datetime
    updated_at: datetime


class SprintCreate(BaseModel):
    product_id: uuid.UUID
    name: str
    start_date: date | None = None
    end_date: date | None = None


class SprintUpdate(BaseModel):
    name: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    status: str | None = None


class SprintRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    product_id: uuid.UUID
    name: str
    start_date: date | None
    end_date: date | None
    status: str
    created_at: datetime
    updated_at: datetime
```

- [ ] **Step 2: Write the failing Projects tests**

Create `backend/tests/test_projects.py`:

```python
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _create_product() -> str:
    response = client.post("/products", json={"name": "Handoff", "key_prefix": "HAND"})
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
```

- [ ] **Step 3: Run to verify it fails**

Run: `uv run pytest tests/test_projects.py -v` (from `backend/`)
Expected: FAIL — `404 Not Found` on `POST /projects`

- [ ] **Step 4: Implement the Projects router**

Create `backend/app/routers/projects.py`:

```python
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import Product, Project
from app.schemas import ProjectCreate, ProjectRead, ProjectUpdate

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("", response_model=list[ProjectRead])
async def list_projects(
    product_id: uuid.UUID = Query(...), db: AsyncSession = Depends(get_db)
) -> list[Project]:
    result = await db.execute(
        select(Project).where(Project.product_id == product_id).order_by(Project.created_at)
    )
    return list(result.scalars().all())


@router.post("", response_model=ProjectRead, status_code=201)
async def create_project(payload: ProjectCreate, db: AsyncSession = Depends(get_db)) -> Project:
    product = await db.get(Product, payload.product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")

    project = Project(**payload.model_dump())
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return project


@router.get("/{project_id}", response_model=ProjectRead)
async def get_project(project_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> Project:
    project = await db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.patch("/{project_id}", response_model=ProjectRead)
async def update_project(
    project_id: uuid.UUID, payload: ProjectUpdate, db: AsyncSession = Depends(get_db)
) -> Project:
    project = await db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(project, field, value)
    await db.commit()
    await db.refresh(project)
    return project


@router.delete("/{project_id}", status_code=204)
async def delete_project(project_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> None:
    project = await db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    await db.delete(project)
    await db.commit()
```

- [ ] **Step 5: Wire the router into the app**

In `backend/app/main.py`, add `from app.routers.projects import router as projects_router` alongside the other router imports, and `app.include_router(projects_router)` alongside the other includes.

- [ ] **Step 6: Run Projects tests to verify they pass**

Run: `uv run pytest tests/test_projects.py -v` (from `backend/`)
Expected: `6 passed`

- [ ] **Step 7: Write the failing Sprints tests**

Create `backend/tests/test_sprints.py`:

```python
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _create_product() -> str:
    response = client.post("/products", json={"name": "Handoff", "key_prefix": "HAND"})
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
```

- [ ] **Step 8: Run to verify it fails**

Run: `uv run pytest tests/test_sprints.py -v` (from `backend/`)
Expected: FAIL — `404 Not Found` on `POST /sprints`

- [ ] **Step 9: Implement the Sprints router**

Create `backend/app/routers/sprints.py`:

```python
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import Product, Sprint
from app.schemas import SprintCreate, SprintRead, SprintUpdate

router = APIRouter(prefix="/sprints", tags=["sprints"])


@router.get("", response_model=list[SprintRead])
async def list_sprints(
    product_id: uuid.UUID = Query(...), db: AsyncSession = Depends(get_db)
) -> list[Sprint]:
    result = await db.execute(
        select(Sprint).where(Sprint.product_id == product_id).order_by(Sprint.created_at)
    )
    return list(result.scalars().all())


@router.post("", response_model=SprintRead, status_code=201)
async def create_sprint(payload: SprintCreate, db: AsyncSession = Depends(get_db)) -> Sprint:
    product = await db.get(Product, payload.product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")

    sprint = Sprint(**payload.model_dump())
    db.add(sprint)
    await db.commit()
    await db.refresh(sprint)
    return sprint


@router.get("/{sprint_id}", response_model=SprintRead)
async def get_sprint(sprint_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> Sprint:
    sprint = await db.get(Sprint, sprint_id)
    if sprint is None:
        raise HTTPException(status_code=404, detail="Sprint not found")
    return sprint


@router.patch("/{sprint_id}", response_model=SprintRead)
async def update_sprint(
    sprint_id: uuid.UUID, payload: SprintUpdate, db: AsyncSession = Depends(get_db)
) -> Sprint:
    sprint = await db.get(Sprint, sprint_id)
    if sprint is None:
        raise HTTPException(status_code=404, detail="Sprint not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(sprint, field, value)
    await db.commit()
    await db.refresh(sprint)
    return sprint


@router.delete("/{sprint_id}", status_code=204)
async def delete_sprint(sprint_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> None:
    sprint = await db.get(Sprint, sprint_id)
    if sprint is None:
        raise HTTPException(status_code=404, detail="Sprint not found")
    await db.delete(sprint)
    await db.commit()
```

- [ ] **Step 10: Wire the router into the app**

Same pattern as Step 5, importing and including `sprints_router` in `backend/app/main.py`.

- [ ] **Step 11: Run the full backend suite**

Run: `uv run pytest -v` (from `backend/`)
Expected: `44 passed` (32 from Task 1 + 6 Projects + 6 Sprints)

- [ ] **Step 12: Commit**

```bash
git add backend/app/schemas.py backend/app/routers/projects.py backend/app/routers/sprints.py backend/app/main.py backend/tests/test_projects.py backend/tests/test_sprints.py
git commit -m "feat(backend): add Projects and Sprints CRUD"
```

---

### Task 3: Frontend Settings Page

**Files:**
- Modify: `frontend/src/lib/api.ts`
- Create: `frontend/src/pages/ProductSettingsPage.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/pages/ProductDetailPage.tsx`

**Interfaces:**
- Consumes: `api.getProduct` (already exists), new `api.listProjects`/`.createProject`/`.listSprints`/`.createSprint` (this task adds them to the same `api.ts`)
- Produces: nothing consumed by later tasks — this is the last task of the plan.

- [ ] **Step 1: Add Project/Sprint types and methods to the API client**

In `frontend/src/lib/api.ts`, add these two interfaces near the existing `Initiative`/`Epic` interfaces:

```typescript
export interface Project {
  id: string;
  product_id: string;
  name: string;
  description: string | null;
  created_at: string;
  updated_at: string;
}

export interface Sprint {
  id: string;
  product_id: string;
  name: string;
  start_date: string | null;
  end_date: string | null;
  status: string;
  created_at: string;
  updated_at: string;
}
```

Add these methods to the exported `api` object, alongside the existing `listEpics`/`createEpic` entries:

```typescript
  listProjects: (productId: string) => request<Project[]>(`/projects?product_id=${productId}`),
  createProject: (data: { product_id: string; name: string; description?: string }) =>
    request<Project>("/projects", { method: "POST", body: JSON.stringify(data) }),

  listSprints: (productId: string) => request<Sprint[]>(`/sprints?product_id=${productId}`),
  createSprint: (data: {
    product_id: string;
    name: string;
    start_date?: string;
    end_date?: string;
  }) => request<Sprint>("/sprints", { method: "POST", body: JSON.stringify(data) }),
```

- [ ] **Step 2: Write the Settings page**

Create `frontend/src/pages/ProductSettingsPage.tsx`:

```tsx
import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";

import { Breadcrumb } from "@/components/Breadcrumb";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api, type Product, type Project, type Sprint } from "@/lib/api";

export function ProductSettingsPage() {
  const { productId } = useParams<{ productId: string }>();
  const [product, setProduct] = useState<Product | null>(null);
  const [projects, setProjects] = useState<Project[]>([]);
  const [sprints, setSprints] = useState<Sprint[]>([]);
  const [loadError, setLoadError] = useState(false);

  const [showProjectForm, setShowProjectForm] = useState(false);
  const [projectName, setProjectName] = useState("");

  const [showSprintForm, setShowSprintForm] = useState(false);
  const [sprintName, setSprintName] = useState("");
  const [sprintStart, setSprintStart] = useState("");
  const [sprintEnd, setSprintEnd] = useState("");

  const load = () => {
    if (!productId) return;
    setLoadError(false);
    Promise.all([
      api.getProduct(productId),
      api.listProjects(productId),
      api.listSprints(productId),
    ])
      .then(([productResult, projectsResult, sprintsResult]) => {
        setProduct(productResult);
        setProjects(projectsResult);
        setSprints(sprintsResult);
      })
      .catch(() => setLoadError(true));
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [productId]);

  const handleCreateProject = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!productId) return;
    try {
      await api.createProject({ product_id: productId, name: projectName });
      setProjectName("");
      setShowProjectForm(false);
      load();
    } catch {
      // form stays open with input intact
    }
  };

  const handleCreateSprint = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!productId) return;
    try {
      await api.createSprint({
        product_id: productId,
        name: sprintName,
        start_date: sprintStart || undefined,
        end_date: sprintEnd || undefined,
      });
      setSprintName("");
      setSprintStart("");
      setSprintEnd("");
      setShowSprintForm(false);
      load();
    } catch {
      // form stays open with input intact
    }
  };

  if (loadError) {
    return (
      <div className="mx-auto max-w-2xl p-8">
        <p className="text-red-600">Couldn't load this page. It may have been deleted.</p>
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
          { label: "Settings", to: `/products/${product.id}/settings` },
        ]}
      />

      <section className="mb-8">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-xl font-semibold">Projects</h2>
          <Button onClick={() => setShowProjectForm((value) => !value)}>New Project</Button>
        </div>

        {showProjectForm && (
          <form
            onSubmit={handleCreateProject}
            className="mb-4 flex flex-col gap-2 rounded border p-4"
          >
            <input
              className="rounded border px-2 py-1"
              placeholder="Name"
              value={projectName}
              onChange={(event) => setProjectName(event.target.value)}
              required
            />
            <Button type="submit">Create</Button>
          </form>
        )}

        <div className="flex flex-col gap-2">
          {projects.map((project) => (
            <Card key={project.id}>
              <CardHeader>
                <CardTitle>{project.name}</CardTitle>
              </CardHeader>
            </Card>
          ))}
        </div>
      </section>

      <section>
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-xl font-semibold">Sprints</h2>
          <Button onClick={() => setShowSprintForm((value) => !value)}>New Sprint</Button>
        </div>

        {showSprintForm && (
          <form
            onSubmit={handleCreateSprint}
            className="mb-4 flex flex-col gap-2 rounded border p-4"
          >
            <input
              className="rounded border px-2 py-1"
              placeholder="Name"
              value={sprintName}
              onChange={(event) => setSprintName(event.target.value)}
              required
            />
            <input
              className="rounded border px-2 py-1"
              type="date"
              value={sprintStart}
              onChange={(event) => setSprintStart(event.target.value)}
            />
            <input
              className="rounded border px-2 py-1"
              type="date"
              value={sprintEnd}
              onChange={(event) => setSprintEnd(event.target.value)}
            />
            <Button type="submit">Create</Button>
          </form>
        )}

        <div className="flex flex-col gap-2">
          {sprints.map((sprint) => (
            <Card key={sprint.id}>
              <CardHeader>
                <CardTitle>{sprint.name}</CardTitle>
              </CardHeader>
              <CardContent className="text-sm text-muted-foreground">
                {sprint.status}
                {sprint.start_date && ` · ${sprint.start_date}`}
                {sprint.end_date && ` → ${sprint.end_date}`}
              </CardContent>
            </Card>
          ))}
        </div>
      </section>
    </div>
  );
}
```

- [ ] **Step 3: Add the route**

In `frontend/src/App.tsx`, add the import:

```tsx
import { ProductSettingsPage } from "@/pages/ProductSettingsPage";
```

and add this route inside `<Routes>`, alongside the existing `/products/:productId` route:

```tsx
        <Route path="/products/:productId/settings" element={<ProductSettingsPage />} />
```

- [ ] **Step 4: Link to Settings from the Product detail page**

In `frontend/src/pages/ProductDetailPage.tsx`, find this block (the header row above the Initiatives list):

```tsx
      <div className="mb-4 flex items-center justify-between">
        <h1 className="text-2xl font-semibold">{product.name} — Initiatives</h1>
        <Button onClick={() => setShowForm((value) => !value)}>New Initiative</Button>
      </div>
```

Replace it with:

```tsx
      <div className="mb-4 flex items-center justify-between">
        <h1 className="text-2xl font-semibold">{product.name} — Initiatives</h1>
        <div className="flex items-center gap-2">
          <Link to={`/products/${product.id}/settings`} className="text-sm underline">
            Settings
          </Link>
          <Button onClick={() => setShowForm((value) => !value)}>New Initiative</Button>
        </div>
      </div>
```

(`Link` is already imported in this file from `react-router-dom` — it's used for the Initiative links further down.)

- [ ] **Step 5: Verify the build compiles**

Run: `cd frontend && npm run build`
Expected: exits 0, no TypeScript errors

- [ ] **Step 6: Manual smoke test**

Run: `npm run dev` (from `frontend/`, with the backend also running per the root README's instructions)
Open the app: go to a Product, click "Settings", create a Project and a Sprint (with dates), confirm both appear in their respective sections and the breadcrumb reads `Products / <product> / Settings`.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/lib/api.ts frontend/src/pages/ProductSettingsPage.tsx frontend/src/App.tsx frontend/src/pages/ProductDetailPage.tsx
git commit -m "feat(frontend): add Product Settings page for Projects and Sprints"
```
