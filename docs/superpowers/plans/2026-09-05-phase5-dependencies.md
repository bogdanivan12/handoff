# Phase 5: Dependencies Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `TaskDependency` and `FeatureDependency` edges with CRUD, a computed "is this task blocked" check, and the UI to manage dependencies and see blocked tasks, since the Kanban board (where the spec's UI language assumes this lives) doesn't exist until Phase 11.

**Architecture:** Two new join-table entities (`task_dependencies`, `feature_dependencies`), each with nested REST routes under their owning entity (same exception-precedent as `AcceptanceCriterion`). `Task` gains a computed `is_blocked` boolean (attached at query time via a small helper, not a stored column) so the existing Task list can render a lock icon without N+1 queries. `GET /tasks` and `GET /features` gain an alternate `product_id` filter to back the two dependency pickers.

**Tech Stack:** FastAPI + SQLAlchemy 2.0 async + Alembic (backend); React + TypeScript + Vite (frontend). Same stack as Phases 0-4.

**Spec:** `docs/superpowers/specs/2026-09-05-phase5-dependencies-design.md`

## Global Constraints

- `schema.sql` gets two new tables (`task_dependencies`, `feature_dependencies`), added in this phase — mirror `knowledge_relations`' style exactly: `uuid_generate_v4()` PK default, `TIMESTAMPTZ NOT NULL DEFAULT now()`, named self-link `CHECK`, two indexes (one per FK direction), `ON DELETE CASCADE` on both FKs.
- No uniqueness constraint on the (owner, target) pair and no general cycle detection — matches `knowledge_relations` precedent and the spec's explicit exclusion of an "interactive graph editor for dependencies" (spec §7).
- Feature's `impact`/`effort`/`priority`/`success_looks_like` columns (spec §4.3) are **out of scope for this phase** — do not add them. They're only consumed starting Phase 11.
- Every new route pre-checks conditions the DB's own constraints would otherwise turn into a raw 500 (missing FK target → 404, self-reference → 400) — matches the precedent set in Phase 4's final review for the Task/Project `RESTRICT` FK.
- `TaskDependencyRead`/`FeatureDependencyRead` embed a summary of the depended-on entity (`id`, `issue_key`, `title`/`name`, `status`) so the frontend never needs a second round-trip per row.

---

### Task 1: Data model — `TaskDependency`, `FeatureDependency`, migration, `schema.sql`

**Files:**
- Modify: `schema.sql`
- Modify: `backend/app/models.py`
- Create: `backend/alembic/versions/0006_dependencies.py`
- Modify: `backend/tests/test_models.py`

**Interfaces:**
- Produces: `app.models.TaskDependency` (`id`, `task_id`, `depends_on_task_id`, `created_at`, `depends_on_task` relationship), `app.models.FeatureDependency` (`id`, `feature_id`, `depends_on_feature_id`, `created_at`, `depends_on_feature` relationship). Task 2 and Task 3 consume both.

- [ ] **Step 1: Add the two tables to `schema.sql`**

Insert this block right after the `acceptance_criteria` table definition (before the `-- GENERATED PROMPT` section, or wherever the `acceptance_criteria` table's block ends):

```sql
-- ============================================================
-- DEPENDENCIES
-- ============================================================

CREATE TABLE task_dependencies (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  task_id UUID NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
  depends_on_task_id UUID NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (task_id != depends_on_task_id)
);

CREATE INDEX idx_task_dependencies_task ON task_dependencies(task_id);
CREATE INDEX idx_task_dependencies_depends_on ON task_dependencies(depends_on_task_id);

CREATE TABLE feature_dependencies (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  feature_id UUID NOT NULL REFERENCES features(id) ON DELETE CASCADE,
  depends_on_feature_id UUID NOT NULL REFERENCES features(id) ON DELETE CASCADE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (feature_id != depends_on_feature_id)
);

CREATE INDEX idx_feature_dependencies_feature ON feature_dependencies(feature_id);
CREATE INDEX idx_feature_dependencies_depends_on ON feature_dependencies(depends_on_feature_id);
```

- [ ] **Step 2: Add the two ORM classes to `backend/app/models.py`**

Append at the end of the file, after the `AcceptanceCriterion` class:

```python
class TaskDependency(Base):
    __tablename__ = "task_dependencies"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    task_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("tasks.id", ondelete="CASCADE"))
    depends_on_task_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("tasks.id", ondelete="CASCADE")
    )
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    depends_on_task: Mapped["Task"] = relationship(foreign_keys=[depends_on_task_id])

    __table_args__ = (
        CheckConstraint("task_id != depends_on_task_id", name="ck_task_dependencies_no_self_link"),
    )


class FeatureDependency(Base):
    __tablename__ = "feature_dependencies"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    feature_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("features.id", ondelete="CASCADE")
    )
    depends_on_feature_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("features.id", ondelete="CASCADE")
    )
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    depends_on_feature: Mapped["Feature"] = relationship(foreign_keys=[depends_on_feature_id])

    __table_args__ = (
        CheckConstraint(
            "feature_id != depends_on_feature_id", name="ck_feature_dependencies_no_self_link"
        ),
    )
```

- [ ] **Step 3: Write the migration**

Create `backend/alembic/versions/0006_dependencies.py`:

```python
"""dependencies

Revision ID: 0006
Revises: 0005
Create Date: 2026-09-05 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "task_dependencies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "task_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tasks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "depends_on_task_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tasks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("task_id != depends_on_task_id", name="ck_task_dependencies_no_self_link"),
    )
    op.create_index("idx_task_dependencies_task", "task_dependencies", ["task_id"])
    op.create_index(
        "idx_task_dependencies_depends_on", "task_dependencies", ["depends_on_task_id"]
    )

    op.create_table(
        "feature_dependencies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "feature_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("features.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "depends_on_feature_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("features.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "feature_id != depends_on_feature_id", name="ck_feature_dependencies_no_self_link"
        ),
    )
    op.create_index("idx_feature_dependencies_feature", "feature_dependencies", ["feature_id"])
    op.create_index(
        "idx_feature_dependencies_depends_on", "feature_dependencies", ["depends_on_feature_id"]
    )


def downgrade() -> None:
    op.drop_table("feature_dependencies")
    op.drop_table("task_dependencies")
```

- [ ] **Step 4: Run the migration against the test/dev SQLite path**

Run: `cd backend && uv run alembic upgrade head`
Expected: no errors (SQLite tests build tables via `Base.metadata.create_all`, not Alembic, but this confirms the migration itself is syntactically valid and reversible — also run `uv run alembic downgrade -1 && uv run alembic upgrade head` to confirm `downgrade()` works).

- [ ] **Step 5: Write a model-level test**

Add to `backend/tests/test_models.py` (add `TaskDependency` and `FeatureDependency` to the existing `from app.models import (...)` block, alphabetically), and add this test function:

```python
def test_can_create_task_and_feature_dependencies(db_session):
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

            feature_a = Feature(epic_id=epic.id, name="Login", issue_number=1)
            feature_b = Feature(epic_id=epic.id, name="Logout", issue_number=2)
            session.add_all([feature_a, feature_b])
            await session.flush()

            project = Project(product_id=product.id, name="Web App")
            session.add(project)
            await session.flush()

            task_a = Task(
                feature_id=feature_a.id,
                project_id=project.id,
                title="A",
                task_type="feature",
                issue_number=3,
            )
            task_b = Task(
                feature_id=feature_a.id,
                project_id=project.id,
                title="B",
                task_type="feature",
                issue_number=4,
            )
            session.add_all([task_a, task_b])
            await session.flush()

            task_dep = TaskDependency(task_id=task_a.id, depends_on_task_id=task_b.id)
            feature_dep = FeatureDependency(
                feature_id=feature_a.id, depends_on_feature_id=feature_b.id
            )
            session.add_all([task_dep, feature_dep])
            await session.commit()

            result = await session.execute(
                select(TaskDependency).where(TaskDependency.task_id == task_a.id)
            )
            loaded_task_dep = result.scalar_one()
            assert loaded_task_dep.depends_on_task_id == task_b.id

            result = await session.execute(
                select(FeatureDependency).where(FeatureDependency.feature_id == feature_a.id)
            )
            loaded_feature_dep = result.scalar_one()
            assert loaded_feature_dep.depends_on_feature_id == feature_b.id

            await session.delete(task_b)
            await session.commit()

            result = await session.execute(
                select(TaskDependency).where(TaskDependency.task_id == task_a.id)
            )
            assert result.scalar_one_or_none() is None
            break

    asyncio.run(_run())
```

This exercises both models and confirms the `ON DELETE CASCADE` (deleting `task_b`, the depended-on task, removes the `TaskDependency` row referencing it).

- [ ] **Step 6: Run tests**

Run: `cd backend && uv run pytest tests/test_models.py -v`
Expected: PASS (new test + all existing model tests).

- [ ] **Step 7: Commit**

```bash
git add schema.sql backend/app/models.py backend/alembic/versions/0006_dependencies.py backend/tests/test_models.py
git commit -m "feat(backend): add TaskDependency and FeatureDependency models and migration"
```

---

### Task 2: Task Dependency CRUD, `is-blocked`, computed `is_blocked` on Task

**Files:**
- Create: `backend/app/task_blocking.py`
- Create: `backend/app/routers/task_dependencies.py`
- Modify: `backend/app/schemas.py`
- Modify: `backend/app/routers/tasks.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_task_dependencies.py`
- Modify: `backend/tests/test_tasks.py`

**Interfaces:**
- Consumes: `app.models.TaskDependency`, `app.models.Task` (Task 1).
- Produces: `GET/POST /tasks/{task_id}/dependencies`, `DELETE /tasks/{task_id}/dependencies/{id}`, `GET /tasks/{task_id}/is-blocked`; `TaskRead.is_blocked: bool`; `GET /tasks?product_id=` as an alternate to `?feature_id=`. Task 4 (frontend) consumes all of these.

- [ ] **Step 1: Write the blocked-computation helper**

Create `backend/app/task_blocking.py`:

```python
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.models import Task, TaskDependency


async def compute_is_blocked_map(
    db: AsyncSession, task_ids: list[uuid.UUID]
) -> dict[uuid.UUID, bool]:
    if not task_ids:
        return {}
    depends_on = aliased(Task)
    result = await db.execute(
        select(TaskDependency.task_id)
        .join(depends_on, TaskDependency.depends_on_task_id == depends_on.id)
        .where(TaskDependency.task_id.in_(task_ids), depends_on.status != "done")
        .distinct()
    )
    blocked_ids = set(result.scalars().all())
    return {task_id: task_id in blocked_ids for task_id in task_ids}


async def attach_is_blocked(db: AsyncSession, tasks: list[Task]) -> list[Task]:
    blocked_map = await compute_is_blocked_map(db, [task.id for task in tasks])
    for task in tasks:
        task.is_blocked = blocked_map.get(task.id, False)
    return tasks
```

- [ ] **Step 2: Add schemas**

Add to `backend/app/schemas.py`, right after `TaskRead` (add `is_blocked: bool` to `TaskRead` itself — see the exact diff below — then add the new classes after `AcceptanceCriterionRead` at the end of the file):

Change `TaskRead` from:
```python
class TaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    feature_id: uuid.UUID
    project_id: uuid.UUID
    sprint_id: uuid.UUID | None
    title: str
    task_type: str
    status: str
    issue_number: int
    issue_key: str
    context: str | None
    scope: str | None
    out_of_scope: str | None
    position: int | None
    created_at: datetime
    updated_at: datetime
```
to (added `is_blocked: bool` as the last field):
```python
class TaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    feature_id: uuid.UUID
    project_id: uuid.UUID
    sprint_id: uuid.UUID | None
    title: str
    task_type: str
    status: str
    issue_number: int
    issue_key: str
    context: str | None
    scope: str | None
    out_of_scope: str | None
    position: int | None
    created_at: datetime
    updated_at: datetime
    is_blocked: bool
```

Append at the end of `schemas.py` (after `AcceptanceCriterionRead`):

```python
class TaskDependencyTaskSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    issue_key: str
    title: str
    status: str


class TaskDependencyCreate(BaseModel):
    depends_on_task_id: uuid.UUID


class TaskDependencyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    task_id: uuid.UUID
    depends_on_task: TaskDependencyTaskSummary
    created_at: datetime


class TaskIsBlockedRead(BaseModel):
    is_blocked: bool
    blocking_tasks: list[TaskDependencyTaskSummary]
```

- [ ] **Step 3: Write the nested router**

Create `backend/app/routers/task_dependencies.py`:

```python
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased, selectinload

from app.db import get_db
from app.models import Epic, Feature, Initiative, Task, TaskDependency
from app.schemas import TaskDependencyCreate, TaskDependencyRead, TaskIsBlockedRead

router = APIRouter(tags=["task-dependencies"])

_DEPENDS_ON_EAGER_LOAD = selectinload(TaskDependency.depends_on_task).options(
    selectinload(Task.feature).selectinload(Feature.epic).selectinload(Epic.initiative).selectinload(
        Initiative.product
    )
)


@router.get("/tasks/{task_id}/dependencies", response_model=list[TaskDependencyRead])
async def list_task_dependencies(
    task_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> list[TaskDependency]:
    task = await db.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")

    result = await db.execute(
        select(TaskDependency)
        .where(TaskDependency.task_id == task_id)
        .options(_DEPENDS_ON_EAGER_LOAD)
        .order_by(TaskDependency.created_at)
    )
    return list(result.scalars().all())


@router.post(
    "/tasks/{task_id}/dependencies", response_model=TaskDependencyRead, status_code=201
)
async def create_task_dependency(
    task_id: uuid.UUID, payload: TaskDependencyCreate, db: AsyncSession = Depends(get_db)
) -> TaskDependency:
    task = await db.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")

    depends_on_task = await db.get(Task, payload.depends_on_task_id)
    if depends_on_task is None:
        raise HTTPException(status_code=404, detail="Dependency task not found")

    if payload.depends_on_task_id == task_id:
        raise HTTPException(status_code=400, detail="A task cannot depend on itself")

    dependency = TaskDependency(task_id=task_id, depends_on_task_id=payload.depends_on_task_id)
    db.add(dependency)
    await db.commit()

    result = await db.execute(
        select(TaskDependency)
        .where(TaskDependency.id == dependency.id)
        .options(_DEPENDS_ON_EAGER_LOAD)
    )
    return result.scalar_one()


@router.delete("/tasks/{task_id}/dependencies/{dependency_id}", status_code=204)
async def delete_task_dependency(
    task_id: uuid.UUID, dependency_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> None:
    dependency = await db.get(TaskDependency, dependency_id)
    if dependency is None or dependency.task_id != task_id:
        raise HTTPException(status_code=404, detail="Task dependency not found")
    await db.delete(dependency)
    await db.commit()


@router.get("/tasks/{task_id}/is-blocked", response_model=TaskIsBlockedRead)
async def get_task_is_blocked(
    task_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> TaskIsBlockedRead:
    task = await db.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")

    depends_on = aliased(Task)
    result = await db.execute(
        select(depends_on)
        .join(TaskDependency, TaskDependency.depends_on_task_id == depends_on.id)
        .where(TaskDependency.task_id == task_id, depends_on.status != "done")
        .options(
            selectinload(depends_on.feature)
            .selectinload(Feature.epic)
            .selectinload(Epic.initiative)
            .selectinload(Initiative.product)
        )
    )
    blocking_tasks = list(result.scalars().all())
    return TaskIsBlockedRead(
        is_blocked=len(blocking_tasks) > 0,
        blocking_tasks=blocking_tasks,
    )
```

Note: `TaskIsBlockedRead(blocking_tasks=blocking_tasks)` works because Pydantic validates each list item against `TaskDependencyTaskSummary` using `from_attributes=True` on that nested model, even though the outer `TaskIsBlockedRead` itself is constructed directly (not from an ORM object) — Pydantic v2 applies each field's own validation mode.

- [ ] **Step 4: Wire `is_blocked` and the `product_id` filter into `tasks.py`**

Modify `backend/app/routers/tasks.py`. Add the import:
```python
from app.task_blocking import attach_is_blocked
```

Replace `list_tasks` (currently requires `feature_id` only) with:
```python
@router.get("", response_model=list[TaskRead])
async def list_tasks(
    feature_id: uuid.UUID | None = Query(default=None),
    product_id: uuid.UUID | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> list[Task]:
    if (feature_id is None) == (product_id is None):
        raise HTTPException(
            status_code=400, detail="Exactly one of feature_id or product_id is required"
        )

    if feature_id is not None:
        query = select(Task).where(Task.feature_id == feature_id)
    else:
        query = (
            select(Task)
            .join(Feature, Task.feature_id == Feature.id)
            .join(Epic, Feature.epic_id == Epic.id)
            .join(Initiative, Epic.initiative_id == Initiative.id)
            .where(Initiative.product_id == product_id)
        )

    result = await db.execute(query.options(_EAGER_LOAD).order_by(Task.created_at))
    tasks = list(result.scalars().all())
    await attach_is_blocked(db, tasks)
    return tasks
```

In `create_task`, right before `return result.scalar_one()`, change to:
```python
    task = result.scalar_one()
    await attach_is_blocked(db, [task])
    return task
```

In `get_task`, right before `return task`, add:
```python
    await attach_is_blocked(db, [task])
    return task
```

In `update_task`, right before `return result.scalar_one()`, change the same way as `create_task`:
```python
    task = result.scalar_one()
    await attach_is_blocked(db, [task])
    return task
```

- [ ] **Step 5: Register the new router**

In `backend/app/main.py`, add the import next to the `acceptance_criteria_router` import:
```python
from app.routers.task_dependencies import router as task_dependencies_router
```
and register it after `app.include_router(acceptance_criteria_router)`:
```python
app.include_router(task_dependencies_router)
```

- [ ] **Step 6: Write tests**

Create `backend/tests/test_task_dependencies.py`:

```python
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
```

Also add `is_blocked` assertions are implicitly covered by the above; no changes needed to existing tests in `test_tasks.py` since `TaskRead.is_blocked` is additive and every existing test only asserts specific fields (`response.json()["title"]`, etc.) rather than exact-matching the whole body — **except** verify this by reading `test_tasks.py` in full before starting (already done during planning: none of the existing assertions do exact dict equality on a `TaskRead`, so no existing test breaks).

- [ ] **Step 7: Run tests**

Run: `cd backend && uv run pytest -v`
Expected: PASS, all tests including the new ones in `test_task_dependencies.py`.

- [ ] **Step 8: Commit**

```bash
git add backend/app/task_blocking.py backend/app/routers/task_dependencies.py backend/app/schemas.py backend/app/routers/tasks.py backend/app/main.py backend/tests/test_task_dependencies.py
git commit -m "feat(backend): add TaskDependency CRUD, is-blocked check, and product-scoped task listing"
```

---

### Task 3: Feature Dependency CRUD, product-scoped Feature listing

**Files:**
- Create: `backend/app/routers/feature_dependencies.py`
- Modify: `backend/app/schemas.py`
- Modify: `backend/app/routers/features.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_feature_dependencies.py`

**Interfaces:**
- Consumes: `app.models.FeatureDependency`, `app.models.Feature` (Task 1).
- Produces: `GET/POST /features/{feature_id}/dependencies`, `DELETE /features/{feature_id}/dependencies/{id}`; `GET /features?product_id=` as an alternate to `?epic_id=`. Task 5 (frontend) consumes both.

- [ ] **Step 1: Add schemas**

Append to `backend/app/schemas.py` (after the Task-dependency schemas added in Task 2):

```python
class FeatureDependencyFeatureSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    issue_key: str
    name: str
    status: str


class FeatureDependencyCreate(BaseModel):
    depends_on_feature_id: uuid.UUID


class FeatureDependencyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    feature_id: uuid.UUID
    depends_on_feature: FeatureDependencyFeatureSummary
    created_at: datetime
```

- [ ] **Step 2: Write the nested router**

Create `backend/app/routers/feature_dependencies.py`:

```python
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db import get_db
from app.models import Epic, Feature, FeatureDependency, Initiative
from app.schemas import FeatureDependencyCreate, FeatureDependencyRead

router = APIRouter(tags=["feature-dependencies"])

_DEPENDS_ON_EAGER_LOAD = selectinload(FeatureDependency.depends_on_feature).options(
    selectinload(Feature.epic).selectinload(Epic.initiative).selectinload(Initiative.product)
)


@router.get("/features/{feature_id}/dependencies", response_model=list[FeatureDependencyRead])
async def list_feature_dependencies(
    feature_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> list[FeatureDependency]:
    feature = await db.get(Feature, feature_id)
    if feature is None:
        raise HTTPException(status_code=404, detail="Feature not found")

    result = await db.execute(
        select(FeatureDependency)
        .where(FeatureDependency.feature_id == feature_id)
        .options(_DEPENDS_ON_EAGER_LOAD)
        .order_by(FeatureDependency.created_at)
    )
    return list(result.scalars().all())


@router.post(
    "/features/{feature_id}/dependencies", response_model=FeatureDependencyRead, status_code=201
)
async def create_feature_dependency(
    feature_id: uuid.UUID, payload: FeatureDependencyCreate, db: AsyncSession = Depends(get_db)
) -> FeatureDependency:
    feature = await db.get(Feature, feature_id)
    if feature is None:
        raise HTTPException(status_code=404, detail="Feature not found")

    depends_on_feature = await db.get(Feature, payload.depends_on_feature_id)
    if depends_on_feature is None:
        raise HTTPException(status_code=404, detail="Dependency feature not found")

    if payload.depends_on_feature_id == feature_id:
        raise HTTPException(status_code=400, detail="A feature cannot depend on itself")

    dependency = FeatureDependency(
        feature_id=feature_id, depends_on_feature_id=payload.depends_on_feature_id
    )
    db.add(dependency)
    await db.commit()

    result = await db.execute(
        select(FeatureDependency)
        .where(FeatureDependency.id == dependency.id)
        .options(_DEPENDS_ON_EAGER_LOAD)
    )
    return result.scalar_one()


@router.delete("/features/{feature_id}/dependencies/{dependency_id}", status_code=204)
async def delete_feature_dependency(
    feature_id: uuid.UUID, dependency_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> None:
    dependency = await db.get(FeatureDependency, dependency_id)
    if dependency is None or dependency.feature_id != feature_id:
        raise HTTPException(status_code=404, detail="Feature dependency not found")
    await db.delete(dependency)
    await db.commit()
```

- [ ] **Step 3: Add the `product_id` filter to `list_features`**

Modify `backend/app/routers/features.py`. Replace `list_features` with:

```python
@router.get("", response_model=list[FeatureRead])
async def list_features(
    epic_id: uuid.UUID | None = Query(default=None),
    product_id: uuid.UUID | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> list[Feature]:
    if (epic_id is None) == (product_id is None):
        raise HTTPException(
            status_code=400, detail="Exactly one of epic_id or product_id is required"
        )

    if epic_id is not None:
        query = select(Feature).where(Feature.epic_id == epic_id)
    else:
        query = (
            select(Feature)
            .join(Epic, Feature.epic_id == Epic.id)
            .join(Initiative, Epic.initiative_id == Initiative.id)
            .where(Initiative.product_id == product_id)
        )

    result = await db.execute(query.options(_EAGER_LOAD).order_by(Feature.created_at))
    return list(result.scalars().all())
```

Add `Initiative` to the existing `from app.models import Epic, Feature, Initiative` import — it's already there, no change needed to that line.

- [ ] **Step 4: Register the new router**

In `backend/app/main.py`, add the import next to `task_dependencies_router`:
```python
from app.routers.feature_dependencies import router as feature_dependencies_router
```
and register it after `app.include_router(task_dependencies_router)`:
```python
app.include_router(feature_dependencies_router)
```

- [ ] **Step 5: Write tests**

Create `backend/tests/test_feature_dependencies.py`:

```python
import uuid

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _create_feature(key_prefix: str | None = None) -> tuple[str, str]:
    product = client.post(
        "/products", json={"name": "Handoff", "key_prefix": key_prefix or uuid.uuid4().hex[:8].upper()}
    ).json()
    initiative = client.post(
        "/initiatives", json={"product_id": product["id"], "name": "Core"}
    ).json()
    epic = client.post("/epics", json={"initiative_id": initiative["id"], "name": "Auth"}).json()
    feature = client.post("/features", json={"epic_id": epic["id"], "name": "Login"}).json()
    return feature["id"], product["id"]


def test_create_and_list_feature_dependency(db_session):
    feature_a, _ = _create_feature()
    feature_b, _ = _create_feature()

    response = client.post(
        f"/features/{feature_a}/dependencies", json={"depends_on_feature_id": feature_b}
    )
    assert response.status_code == 201
    body = response.json()
    assert body["feature_id"] == feature_a
    assert body["depends_on_feature"]["id"] == feature_b

    response = client.get(f"/features/{feature_a}/dependencies")
    assert response.status_code == 200
    assert len(response.json()) == 1


def test_create_feature_dependency_rejects_self_reference(db_session):
    feature_a, _ = _create_feature()

    response = client.post(
        f"/features/{feature_a}/dependencies", json={"depends_on_feature_id": feature_a}
    )
    assert response.status_code == 400


def test_create_feature_dependency_rejects_missing_feature(db_session):
    feature_a, _ = _create_feature()

    response = client.post(
        f"/features/{feature_a}/dependencies",
        json={"depends_on_feature_id": "00000000-0000-0000-0000-000000000000"},
    )
    assert response.status_code == 404


def test_delete_feature_dependency_rejects_wrong_feature(db_session):
    feature_a, _ = _create_feature()
    feature_b, _ = _create_feature()
    feature_c, _ = _create_feature()

    response = client.post(
        f"/features/{feature_a}/dependencies", json={"depends_on_feature_id": feature_b}
    )
    dependency_id = response.json()["id"]

    response = client.delete(f"/features/{feature_c}/dependencies/{dependency_id}")
    assert response.status_code == 404


def test_delete_feature_dependency(db_session):
    feature_a, _ = _create_feature()
    feature_b, _ = _create_feature()

    response = client.post(
        f"/features/{feature_a}/dependencies", json={"depends_on_feature_id": feature_b}
    )
    dependency_id = response.json()["id"]

    response = client.delete(f"/features/{feature_a}/dependencies/{dependency_id}")
    assert response.status_code == 204

    response = client.get(f"/features/{feature_a}/dependencies")
    assert response.json() == []


def test_list_features_by_product(db_session):
    key_prefix = uuid.uuid4().hex[:8].upper()
    product = client.post("/products", json={"name": "Handoff", "key_prefix": key_prefix}).json()
    initiative = client.post(
        "/initiatives", json={"product_id": product["id"], "name": "Core"}
    ).json()
    epic = client.post("/epics", json={"initiative_id": initiative["id"], "name": "Auth"}).json()
    client.post("/features", json={"epic_id": epic["id"], "name": "F1"})
    client.post("/features", json={"epic_id": epic["id"], "name": "F2"})

    response = client.get(f"/features?product_id={product['id']}")
    assert response.status_code == 200
    names = {f["name"] for f in response.json()}
    assert names == {"F1", "F2"}


def test_list_features_rejects_neither_filter(db_session):
    response = client.get("/features")
    assert response.status_code == 400


def test_list_features_rejects_both_filters(db_session):
    feature_id, product_id = _create_feature()
    feature = client.get(f"/features/{feature_id}").json()

    response = client.get(f"/features?epic_id={feature['epic_id']}&product_id={product_id}")
    assert response.status_code == 400
```

- [ ] **Step 6: Run tests**

Run: `cd backend && uv run pytest -v`
Expected: PASS, all tests including the new ones in `test_feature_dependencies.py`.

- [ ] **Step 7: Commit**

```bash
git add backend/app/routers/feature_dependencies.py backend/app/schemas.py backend/app/routers/features.py backend/app/main.py backend/tests/test_feature_dependencies.py
git commit -m "feat(backend): add FeatureDependency CRUD and product-scoped feature listing"
```

---

### Task 4: Frontend — Task dependencies UI + blocked-task styling

**Files:**
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/components/TaskPanel.tsx`
- Modify: `frontend/src/pages/FeatureDetailPage.tsx`

**Interfaces:**
- Consumes: `GET/POST /tasks/{task_id}/dependencies`, `DELETE .../{id}`, `GET /tasks/{task_id}/is-blocked`, `GET /tasks?product_id=`, `TaskRead.is_blocked` (all Task 2).
- Produces: `TaskPanel` gains a `productId: string` required prop (Task 5 does not depend on this, but note it when touching `TaskPanel`'s call site again).

- [ ] **Step 1: Add types and API methods to `api.ts`**

Add `is_blocked: boolean;` as the last field of the existing `Task` interface (after `updated_at: string;`):
```typescript
export interface Task {
  id: string;
  feature_id: string;
  project_id: string;
  sprint_id: string | null;
  title: string;
  task_type: string;
  status: string;
  issue_number: number;
  issue_key: string;
  context: string | null;
  scope: string | null;
  out_of_scope: string | null;
  position: number | null;
  created_at: string;
  updated_at: string;
  is_blocked: boolean;
}
```

Add new interfaces after `AcceptanceCriterion`:
```typescript
export interface TaskDependencyTaskSummary {
  id: string;
  issue_key: string;
  title: string;
  status: string;
}

export interface TaskDependency {
  id: string;
  task_id: string;
  depends_on_task: TaskDependencyTaskSummary;
  created_at: string;
}

export interface TaskIsBlocked {
  is_blocked: boolean;
  blocking_tasks: TaskDependencyTaskSummary[];
}
```

Add new methods to the `api` object, after `toggleAcceptanceCriterion`:
```typescript
  listTasksByProduct: (productId: string) => request<Task[]>(`/tasks?product_id=${productId}`),

  listTaskDependencies: (taskId: string) =>
    request<TaskDependency[]>(`/tasks/${taskId}/dependencies`),
  createTaskDependency: (taskId: string, dependsOnTaskId: string) =>
    request<TaskDependency>(`/tasks/${taskId}/dependencies`, {
      method: "POST",
      body: JSON.stringify({ depends_on_task_id: dependsOnTaskId }),
    }),
  deleteTaskDependency: (taskId: string, dependencyId: string) =>
    request<void>(`/tasks/${taskId}/dependencies/${dependencyId}`, { method: "DELETE" }),
  getTaskIsBlocked: (taskId: string) => request<TaskIsBlocked>(`/tasks/${taskId}/is-blocked`),
```

- [ ] **Step 2: Add the "Depends on" section to `TaskPanel`**

Modify `frontend/src/components/TaskPanel.tsx`:

Add `productId: string` to `TaskPanelProps`:
```typescript
interface TaskPanelProps {
  taskId: string | null;
  featureId: string;
  productId: string;
  projects: Project[];
  onClose: () => void;
  onSaved: () => void;
}
```

Update the function signature:
```typescript
export function TaskPanel({ taskId, featureId, productId, projects, onClose, onSaved }: TaskPanelProps) {
```

Add new imports to the top-of-file import line:
```typescript
import { api, type AcceptanceCriterion, type Project, type Task, type TaskDependency, type TaskIsBlocked } from "@/lib/api";
```

Add new state, alongside the existing `criteria` state:
```typescript
  const [dependencies, setDependencies] = useState<TaskDependency[]>([]);
  const [productTasks, setProductTasks] = useState<Task[]>([]);
  const [selectedDependencyId, setSelectedDependencyId] = useState("");
  const [isBlocked, setIsBlocked] = useState<TaskIsBlocked | null>(null);
```

Extend the existing `useEffect` (the one that loads the task on `taskId` change) to also load dependencies, the product-wide task list, and the blocked status:
```typescript
  useEffect(() => {
    if (!taskId) return;
    api.getTask(taskId).then((loaded) => {
      setTask(loaded);
      setTitle(loaded.title);
      setTaskType(loaded.task_type);
      setStatus(loaded.status);
      setContext(loaded.context ?? "");
    });
    api.listAcceptanceCriteria(taskId).then(setCriteria);
    api.listTaskDependencies(taskId).then(setDependencies);
    api.listTasksByProduct(productId).then(setProductTasks);
    api.getTaskIsBlocked(taskId).then(setIsBlocked);
  }, [taskId, productId]);
```

Add two new handlers, near `handleToggleCriterion`:
```typescript
  const handleAddDependency = async () => {
    if (!taskId || !selectedDependencyId) return;
    await api.createTaskDependency(taskId, selectedDependencyId);
    setSelectedDependencyId("");
    api.listTaskDependencies(taskId).then(setDependencies);
    api.getTaskIsBlocked(taskId).then(setIsBlocked);
  };

  const handleRemoveDependency = async (dependencyId: string) => {
    if (!taskId) return;
    await api.deleteTaskDependency(taskId, dependencyId);
    api.listTaskDependencies(taskId).then(setDependencies);
    api.getTaskIsBlocked(taskId).then(setIsBlocked);
  };
```

Add the new section's JSX right after the closing `</div>` of the Acceptance Criteria section (i.e. after the `{taskId && (...)}` block that contains "Acceptance Criteria", and still inside the same top-level returned `<div>`):

```tsx
      {taskId && (
        <div className="mt-6">
          <h3 className="mb-2 text-sm font-semibold">Depends on</h3>
          {isBlocked?.is_blocked && (
            <p className="mb-2 rounded bg-yellow-50 p-2 text-sm text-yellow-800">
              Blocked by {isBlocked.blocking_tasks.length} unresolved{" "}
              {isBlocked.blocking_tasks.length === 1 ? "dependency" : "dependencies"}.
            </p>
          )}
          <div className="flex flex-col gap-2">
            {dependencies.map((dependency) => (
              <div key={dependency.id} className="flex items-center justify-between text-sm">
                <span>
                  <span className="rounded bg-blue-100 px-2 py-0.5 text-xs font-mono text-blue-800">
                    {dependency.depends_on_task.issue_key}
                  </span>{" "}
                  {dependency.depends_on_task.title} ({dependency.depends_on_task.status})
                </span>
                <button
                  type="button"
                  onClick={() => handleRemoveDependency(dependency.id)}
                  className="text-xs underline"
                >
                  Remove
                </button>
              </div>
            ))}
          </div>
          <div className="mt-3 flex gap-2">
            <select
              className="flex-1 rounded border px-2 py-1"
              value={selectedDependencyId}
              onChange={(event) => setSelectedDependencyId(event.target.value)}
            >
              <option value="">Select a task…</option>
              {productTasks
                .filter(
                  (candidate) =>
                    candidate.id !== taskId &&
                    !dependencies.some((dep) => dep.depends_on_task.id === candidate.id),
                )
                .map((candidate) => (
                  <option key={candidate.id} value={candidate.id}>
                    {candidate.issue_key} — {candidate.title}
                  </option>
                ))}
            </select>
            <Button type="button" onClick={handleAddDependency} disabled={!selectedDependencyId}>
              Add
            </Button>
          </div>
        </div>
      )}
```

- [ ] **Step 3: Pass `productId` from `FeatureDetailPage` and render blocked-task styling**

Modify `frontend/src/pages/FeatureDetailPage.tsx`. Update the `<TaskPanel>` call site to add `productId={product.id}`:
```tsx
      {openTaskId && (
        <TaskPanel
          key={openTaskId}
          taskId={openTaskId === "new" ? null : openTaskId}
          featureId={feature.id}
          productId={product.id}
          projects={projects}
          onClose={() => setOpenTaskId(null)}
          onSaved={() => {
            setOpenTaskId(null);
            loadTasks();
          }}
        />
      )}
```

Update the task-list row rendering to show blocked styling. Replace:
```tsx
        {tasks.map((task) => (
          <button
            key={task.id}
            type="button"
            onClick={() => setOpenTaskId(task.id)}
            className="rounded border p-4 text-left hover:bg-gray-50"
          >
            <div className="flex items-center gap-2">
              <span className="rounded bg-blue-100 px-2 py-0.5 text-xs font-mono text-blue-800">
                {task.issue_key}
              </span>
              <span className="rounded bg-gray-100 px-2 py-0.5 text-xs font-mono">
                {task.task_type}
              </span>
              <span>{task.title}</span>
            </div>
            <div className="mt-1 text-sm text-muted-foreground">{task.status}</div>
          </button>
        ))}
```
with:
```tsx
        {tasks.map((task) => (
          <button
            key={task.id}
            type="button"
            onClick={() => setOpenTaskId(task.id)}
            className={`rounded border p-4 text-left hover:bg-gray-50 ${task.is_blocked ? "opacity-50" : ""}`}
          >
            <div className="flex items-center gap-2">
              {task.is_blocked && <span title="Blocked">🔒</span>}
              <span className="rounded bg-blue-100 px-2 py-0.5 text-xs font-mono text-blue-800">
                {task.issue_key}
              </span>
              <span className="rounded bg-gray-100 px-2 py-0.5 text-xs font-mono">
                {task.task_type}
              </span>
              <span>{task.title}</span>
            </div>
            <div className="mt-1 text-sm text-muted-foreground">{task.status}</div>
          </button>
        ))}
```

- [ ] **Step 4: Typecheck**

Run: `cd frontend && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/api.ts frontend/src/components/TaskPanel.tsx frontend/src/pages/FeatureDetailPage.tsx
git commit -m "feat(frontend): add Task dependencies UI and blocked-task styling"
```

---

### Task 5: Frontend — Feature dependencies UI

**Files:**
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/pages/FeatureDetailPage.tsx`

**Interfaces:**
- Consumes: `GET/POST /features/{feature_id}/dependencies`, `DELETE .../{id}`, `GET /features?product_id=` (Task 3).

- [ ] **Step 1: Add types and API methods to `api.ts`**

Add new interfaces after `TaskIsBlocked` (added in Task 4):
```typescript
export interface FeatureDependencyFeatureSummary {
  id: string;
  issue_key: string;
  name: string;
  status: string;
}

export interface FeatureDependency {
  id: string;
  feature_id: string;
  depends_on_feature: FeatureDependencyFeatureSummary;
  created_at: string;
}
```

Add new methods to the `api` object, after `getTaskIsBlocked`:
```typescript
  listFeaturesByProduct: (productId: string) =>
    request<Feature[]>(`/features?product_id=${productId}`),

  listFeatureDependencies: (featureId: string) =>
    request<FeatureDependency[]>(`/features/${featureId}/dependencies`),
  createFeatureDependency: (featureId: string, dependsOnFeatureId: string) =>
    request<FeatureDependency>(`/features/${featureId}/dependencies`, {
      method: "POST",
      body: JSON.stringify({ depends_on_feature_id: dependsOnFeatureId }),
    }),
  deleteFeatureDependency: (featureId: string, dependencyId: string) =>
    request<void>(`/features/${featureId}/dependencies/${dependencyId}`, { method: "DELETE" }),
```

- [ ] **Step 2: Add a "Depends on" section to `FeatureDetailPage`**

Modify `frontend/src/pages/FeatureDetailPage.tsx`.

Add new imports to the existing `@/lib/api` import block:
```typescript
import {
  api,
  type Epic,
  type Feature,
  type FeatureDependency,
  type Initiative,
  type Product,
  type Project,
  type Task,
} from "@/lib/api";
```

Add new state, alongside `openTaskId`:
```typescript
  const [featureDependencies, setFeatureDependencies] = useState<FeatureDependency[]>([]);
  const [productFeatures, setProductFeatures] = useState<Feature[]>([]);
  const [selectedFeatureDependencyId, setSelectedFeatureDependencyId] = useState("");
```

Extend the `load()` function's `Promise.all` to also fetch dependencies and the product-wide feature list. Replace:
```typescript
  const load = () => {
    if (!productId || !initiativeId || !epicId || !featureId) return;
    setLoadError(false);
    Promise.all([
      api.getProduct(productId),
      api.getInitiative(initiativeId),
      api.getEpic(epicId),
      api.getFeature(featureId),
      api.listProjects(productId),
      api.listTasks(featureId),
    ])
      .then(([productResult, initiativeResult, epicResult, featureResult, projectsResult, tasksResult]) => {
        setProduct(productResult);
        setInitiative(initiativeResult);
        setEpic(epicResult);
        setFeature(featureResult);
        setProjects(projectsResult);
        setTasks(tasksResult);
      })
      .catch(() => setLoadError(true));
  };
```
with:
```typescript
  const load = () => {
    if (!productId || !initiativeId || !epicId || !featureId) return;
    setLoadError(false);
    Promise.all([
      api.getProduct(productId),
      api.getInitiative(initiativeId),
      api.getEpic(epicId),
      api.getFeature(featureId),
      api.listProjects(productId),
      api.listTasks(featureId),
      api.listFeatureDependencies(featureId),
      api.listFeaturesByProduct(productId),
    ])
      .then(
        ([
          productResult,
          initiativeResult,
          epicResult,
          featureResult,
          projectsResult,
          tasksResult,
          featureDependenciesResult,
          productFeaturesResult,
        ]) => {
          setProduct(productResult);
          setInitiative(initiativeResult);
          setEpic(epicResult);
          setFeature(featureResult);
          setProjects(projectsResult);
          setTasks(tasksResult);
          setFeatureDependencies(featureDependenciesResult);
          setProductFeatures(productFeaturesResult);
        },
      )
      .catch(() => setLoadError(true));
  };
```

Add two new handlers, near `loadTasks`:
```typescript
  const loadFeatureDependencies = () => {
    if (!featureId) return;
    api.listFeatureDependencies(featureId).then(setFeatureDependencies).catch(() => {
      // best-effort refresh; the list simply stays stale until the next successful load
    });
  };

  const handleAddFeatureDependency = async () => {
    if (!featureId || !selectedFeatureDependencyId) return;
    await api.createFeatureDependency(featureId, selectedFeatureDependencyId);
    setSelectedFeatureDependencyId("");
    loadFeatureDependencies();
  };

  const handleRemoveFeatureDependency = async (dependencyId: string) => {
    if (!featureId) return;
    await api.deleteFeatureDependency(featureId, dependencyId);
    loadFeatureDependencies();
  };
```

Add the new section's JSX right after the closing `</div>` of the Tasks list block (the `<div className="flex flex-col gap-2">{tasks.map(...)}</div>`), and before the `{openTaskId && (<TaskPanel .../>)}` block:

```tsx
      <div className="mt-6">
        <h3 className="mb-2 text-sm font-semibold">Depends on</h3>
        <div className="flex flex-col gap-2">
          {featureDependencies.map((dependency) => (
            <div key={dependency.id} className="flex items-center justify-between text-sm">
              <span>
                <span className="rounded bg-blue-100 px-2 py-0.5 text-xs font-mono text-blue-800">
                  {dependency.depends_on_feature.issue_key}
                </span>{" "}
                {dependency.depends_on_feature.name} ({dependency.depends_on_feature.status})
              </span>
              <button
                type="button"
                onClick={() => handleRemoveFeatureDependency(dependency.id)}
                className="text-xs underline"
              >
                Remove
              </button>
            </div>
          ))}
        </div>
        <div className="mt-3 flex gap-2">
          <select
            className="flex-1 rounded border px-2 py-1"
            value={selectedFeatureDependencyId}
            onChange={(event) => setSelectedFeatureDependencyId(event.target.value)}
          >
            <option value="">Select a feature…</option>
            {productFeatures
              .filter(
                (candidate) =>
                  candidate.id !== feature.id &&
                  !featureDependencies.some((dep) => dep.depends_on_feature.id === candidate.id),
              )
              .map((candidate) => (
                <option key={candidate.id} value={candidate.id}>
                  {candidate.issue_key} — {candidate.name}
                </option>
              ))}
          </select>
          <Button
            type="button"
            onClick={handleAddFeatureDependency}
            disabled={!selectedFeatureDependencyId}
          >
            Add
          </Button>
        </div>
      </div>
```

- [ ] **Step 3: Typecheck**

Run: `cd frontend && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/lib/api.ts frontend/src/pages/FeatureDetailPage.tsx
git commit -m "feat(frontend): add Feature dependencies UI"
```
