# Phase 4 Basic Task Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** CRUD for Task (linking Feature + Project + optional Sprint, sharing Feature's per-Product issue-number counter) and AcceptanceCriterion (basic/gherkin), plus a split-view side panel — the first UI pattern in this project that isn't full-page navigation.

**Architecture:** `Task` reuses `app.issue_numbers.allocate_issue_number` (built in Phase 1, extracted in Phase 2) — the exact same counter Feature uses, so `HAND-12` might be a Feature and `HAND-13` a Task. `AcceptanceCriterion` is nested under `/tasks/{task_id}/acceptance-criteria` — the one deliberate deviation from this project's flat-REST convention, since it has no meaning independent of its Task. Frontend adds a fifth hierarchy level (`FeatureDetailPage`) and a `TaskPanel` component that opens as a fixed side panel on click, with local component state only (no route change).

**Tech Stack:** Same as Phase 3 — no new dependencies on either side.

**Spec:** [docs/superpowers/specs/2026-09-05-phase4-basic-task-design.md](../specs/2026-09-05-phase4-basic-task-design.md)

## Global Constraints

- `tasks.generated_from_draft_id` is NOT added this phase — `task_drafts` doesn't exist until Phase 6; added then with its real FK
- `acceptance_criteria.task_draft_id` and its polymorphic `CHECK` are NOT added this phase — `task_id` is `NOT NULL` for now, relaxed to nullable + CHECK added in Phase 6/7
- `tasks.relevant_knowledge JSONB DEFAULT '[]'` IS added this phase (portable via the same `with_variant` trick as Phase 3) — stays `[]`, populated by Phase 8
- `task_type`, `status` (on Task), `format` (on AcceptanceCriterion) are plain `Text` columns constrained via Pydantic `Literal`, not Postgres `ENUM`
- Task's `issue_number`/`issue_key` MUST go through the existing `allocate_issue_number(db, product_id)` helper from `app/issue_numbers.py` — never a second counter
- `AcceptanceCriterion` routes are nested (`/tasks/{task_id}/acceptance-criteria`), not flat — deliberate, do not "fix" this to match other resources
- Every new model column with a Python-side `default=` gets a matching `server_default=` from the start
- All repo content in English

---

### Task 1: Task and AcceptanceCriterion Models, Migration

**Files:**
- Modify: `backend/app/models.py`
- Create: `backend/alembic/versions/0005_basic_task.py`
- Modify: `backend/tests/test_models.py`

**Interfaces:**
- Produces: `app.models.Task` (with an `issue_key` computed property reading `feature.epic.initiative.product.key_prefix`), `app.models.AcceptanceCriterion`. Consumed by Task 2 (`Task`) and Task 3 (`AcceptanceCriterion`).

- [ ] **Step 1: Add the models**

In `backend/app/models.py`, add these two classes at the end of the file (after `KnowledgeRelation`):

```python
class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    feature_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("features.id", ondelete="CASCADE"))
    project_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("projects.id", ondelete="RESTRICT"))
    sprint_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID, ForeignKey("sprints.id", ondelete="SET NULL"), default=None
    )
    superseded_by_task_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID, ForeignKey("tasks.id", ondelete="SET NULL"), default=None
    )
    title: Mapped[str] = mapped_column(Text)
    task_type: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, default="todo", server_default="todo")
    issue_number: Mapped[int] = mapped_column()
    outdated_reason: Mapped[str | None] = mapped_column(Text, default=None)
    context: Mapped[str | None] = mapped_column(Text, default=None)
    scope: Mapped[str | None] = mapped_column(Text, default=None)
    out_of_scope: Mapped[str | None] = mapped_column(Text, default=None)
    position: Mapped[int | None] = mapped_column(default=None)
    relevant_knowledge: Mapped[list] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"), default=list, server_default="[]"
    )
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    feature: Mapped["Feature"] = relationship()

    @property
    def issue_key(self) -> str:
        return f"{self.feature.epic.initiative.product.key_prefix}-{self.issue_number}"


class AcceptanceCriterion(Base):
    __tablename__ = "acceptance_criteria"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    task_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("tasks.id", ondelete="CASCADE"))
    format: Mapped[str] = mapped_column(Text, default="basic", server_default="basic")
    description: Mapped[str | None] = mapped_column(Text, default=None)
    given: Mapped[str | None] = mapped_column(Text, default=None)
    when_: Mapped[str | None] = mapped_column(Text, default=None)
    then_: Mapped[str | None] = mapped_column(Text, default=None)
    position: Mapped[int] = mapped_column(default=0, server_default="0")
    checked: Mapped[bool] = mapped_column(default=False, server_default="false")
    checked_at: Mapped[datetime | None] = mapped_column(default=None)
    checked_by: Mapped[uuid.UUID | None] = mapped_column(GUID, default=None)
    notes: Mapped[str | None] = mapped_column(Text, default=None)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
```

Both classes use `Feature`, `JSONB`, `JSON`, `relationship` — all already imported in this file from prior phases (`relationship` from Phase 1, `JSONB`/`JSON` from Phase 3). No new imports needed.

- [ ] **Step 2: Write the migration**

Create `backend/alembic/versions/0005_basic_task.py`:

```python
"""basic task

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-05 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tasks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "feature_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("features.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "sprint_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("sprints.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "superseded_by_task_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("task_type", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="todo"),
        sa.Column("issue_number", sa.Integer(), nullable=False),
        sa.Column("outdated_reason", sa.Text(), nullable=True),
        sa.Column("context", sa.Text(), nullable=True),
        sa.Column("scope", sa.Text(), nullable=True),
        sa.Column("out_of_scope", sa.Text(), nullable=True),
        sa.Column("position", sa.Integer(), nullable=True),
        sa.Column("relevant_knowledge", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_foreign_key(
        "fk_tasks_superseded_by_task_id",
        "tasks",
        "tasks",
        ["superseded_by_task_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_table(
        "acceptance_criteria",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "task_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tasks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("format", sa.Text(), nullable=False, server_default="basic"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("given", sa.Text(), nullable=True),
        sa.Column("when_", sa.Text(), nullable=True),
        sa.Column("then_", sa.Text(), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("checked", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("checked_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )


def downgrade() -> None:
    op.drop_table("acceptance_criteria")
    op.drop_constraint("fk_tasks_superseded_by_task_id", "tasks", type_="foreignkey")
    op.drop_table("tasks")
```

- [ ] **Step 3: Verify the migration chain (no DB connection needed)**

Run: `cd backend && uv run alembic heads`
Expected: `0005 (head)`

- [ ] **Step 4: Write a test proving the counter sharing and the AcceptanceCriterion link**

In `backend/tests/test_models.py`, add `Task, AcceptanceCriterion` to the existing `from app.models import ...` import line, then append:

```python


def test_task_shares_issue_counter_with_feature_and_has_acceptance_criteria(db_session):
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
            await session.flush()

            project = Project(product_id=product.id, name="Web App")
            session.add(project)
            await session.flush()

            task = Task(
                feature_id=feature.id,
                project_id=project.id,
                title="Wire up login form",
                task_type="feature",
                issue_number=2,
            )
            session.add(task)
            await session.flush()

            criterion = AcceptanceCriterion(
                task_id=task.id, format="basic", description="Form submits"
            )
            session.add(criterion)
            await session.commit()

            result = await session.execute(
                select(Task)
                .where(Task.id == task.id)
                .options(
                    selectinload(Task.feature)
                    .selectinload(Feature.epic)
                    .selectinload(Epic.initiative)
                    .selectinload(Initiative.product)
                )
            )
            loaded = result.scalar_one()
            assert loaded.issue_key == "HAND-2"

            result = await session.execute(
                select(AcceptanceCriterion).where(AcceptanceCriterion.task_id == task.id)
            )
            assert result.scalar_one().description == "Form submits"
            break

    asyncio.run(_run())
```

This is a four-step eager-load chain: `Task.feature` → `Feature.epic` →
`Epic.initiative` → `Initiative.product`, matching `Task.issue_key`'s own
property implementation (`self.feature.epic.initiative.product.key_prefix`)
exactly — each hop must be eager-loaded or accessing it after the session
closes raises `MissingGreenlet`. `Feature` is already imported in this test
file from prior phases.

- [ ] **Step 5: Run the test to verify it passes**

Run: `uv run pytest tests/test_models.py -v` (from `backend/`)
Expected: `4 passed`

- [ ] **Step 6: Run the full backend suite**

Run: `uv run pytest -v` (from `backend/`)
Expected: `70 passed` (69 from Phase 3 + this one new test)

- [ ] **Step 7: Commit**

```bash
git add backend/app/models.py backend/alembic/versions/0005_basic_task.py backend/tests/test_models.py
git commit -m "feat(backend): add Task and AcceptanceCriterion models and migration"
```

---

### Task 2: Task CRUD

**Files:**
- Modify: `backend/app/schemas.py`
- Create: `backend/app/routers/tasks.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_tasks.py`

**Interfaces:**
- Consumes: `app.models.Task/.Feature/.Project/.Sprint/.Epic/.Initiative` (Task 1 / Phases 1-2), `app.issue_numbers.allocate_issue_number` (Phase 1/2)
- Produces: `app.schemas.TaskCreate/.TaskUpdate/.TaskRead`. Router mounted at `/tasks` — consumed by Task 4's frontend.

- [ ] **Step 1: Add the schemas**

Append to `backend/app/schemas.py`:

```python


class TaskCreate(BaseModel):
    feature_id: uuid.UUID
    project_id: uuid.UUID
    sprint_id: uuid.UUID | None = None
    title: str
    task_type: Literal["feature", "bug", "improvement", "chore", "research"]
    context: str | None = None
    scope: str | None = None
    out_of_scope: str | None = None
    position: int | None = None


class TaskUpdate(BaseModel):
    title: str | None = None
    task_type: Literal["feature", "bug", "improvement", "chore", "research"] | None = None
    status: Literal["todo", "in_progress", "done", "outdated"] | None = None
    sprint_id: uuid.UUID | None = None
    context: str | None = None
    scope: str | None = None
    out_of_scope: str | None = None
    position: int | None = None


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

- [ ] **Step 2: Write the failing tests**

Create `backend/tests/test_tasks.py`:

```python
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
```

- [ ] **Step 3: Run to verify it fails**

Run: `uv run pytest tests/test_tasks.py -v` (from `backend/`)
Expected: FAIL — `404 Not Found` on `POST /tasks`

- [ ] **Step 4: Implement the router**

Create `backend/app/routers/tasks.py`:

```python
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db import get_db
from app.issue_numbers import allocate_issue_number
from app.models import Epic, Feature, Initiative, Project, Sprint, Task
from app.schemas import TaskCreate, TaskRead, TaskUpdate

router = APIRouter(prefix="/tasks", tags=["tasks"])

_EAGER_LOAD = (
    selectinload(Task.feature)
    .selectinload(Feature.epic)
    .selectinload(Epic.initiative)
    .selectinload(Initiative.product)
)


@router.get("", response_model=list[TaskRead])
async def list_tasks(
    feature_id: uuid.UUID = Query(...), db: AsyncSession = Depends(get_db)
) -> list[Task]:
    result = await db.execute(
        select(Task)
        .where(Task.feature_id == feature_id)
        .options(_EAGER_LOAD)
        .order_by(Task.created_at)
    )
    return list(result.scalars().all())


@router.post("", response_model=TaskRead, status_code=201)
async def create_task(payload: TaskCreate, db: AsyncSession = Depends(get_db)) -> Task:
    feature = await db.get(Feature, payload.feature_id)
    if feature is None:
        raise HTTPException(status_code=404, detail="Feature not found")

    project = await db.get(Project, payload.project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    if payload.sprint_id is not None:
        sprint = await db.get(Sprint, payload.sprint_id)
        if sprint is None:
            raise HTTPException(status_code=404, detail="Sprint not found")

    epic = await db.get(Epic, feature.epic_id)
    initiative = await db.get(Initiative, epic.initiative_id)

    issue_number = await allocate_issue_number(db, initiative.product_id)

    task = Task(
        feature_id=payload.feature_id,
        project_id=payload.project_id,
        sprint_id=payload.sprint_id,
        title=payload.title,
        task_type=payload.task_type,
        context=payload.context,
        scope=payload.scope,
        out_of_scope=payload.out_of_scope,
        position=payload.position,
        issue_number=issue_number,
    )
    db.add(task)
    await db.commit()

    result = await db.execute(select(Task).where(Task.id == task.id).options(_EAGER_LOAD))
    return result.scalar_one()


@router.get("/{task_id}", response_model=TaskRead)
async def get_task(task_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> Task:
    result = await db.execute(select(Task).where(Task.id == task_id).options(_EAGER_LOAD))
    task = result.scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.patch("/{task_id}", response_model=TaskRead)
async def update_task(
    task_id: uuid.UUID, payload: TaskUpdate, db: AsyncSession = Depends(get_db)
) -> Task:
    task = await db.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")

    updates = payload.model_dump(exclude_unset=True)
    if "sprint_id" in updates and updates["sprint_id"] is not None:
        sprint = await db.get(Sprint, updates["sprint_id"])
        if sprint is None:
            raise HTTPException(status_code=404, detail="Sprint not found")

    for field, value in updates.items():
        setattr(task, field, value)

    await db.commit()

    result = await db.execute(select(Task).where(Task.id == task_id).options(_EAGER_LOAD))
    return result.scalar_one()


@router.delete("/{task_id}", status_code=204)
async def delete_task(task_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> None:
    task = await db.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    await db.delete(task)
    await db.commit()
```

- [ ] **Step 5: Wire the router into the app**

In `backend/app/main.py`, add `from app.routers.tasks import router as tasks_router` alongside the other router imports, and `app.include_router(tasks_router)` alongside the other includes.

- [ ] **Step 6: Run the tests to verify they pass**

Run: `uv run pytest tests/test_tasks.py -v` (from `backend/`)
Expected: `9 passed`

- [ ] **Step 7: Run the full backend suite**

Run: `uv run pytest -v` (from `backend/`)
Expected: `79 passed` (70 from Task 1 + 9 task tests)

- [ ] **Step 8: Commit**

```bash
git add backend/app/schemas.py backend/app/routers/tasks.py backend/app/main.py backend/tests/test_tasks.py
git commit -m "feat(backend): add Task CRUD reusing Feature's issue-number counter"
```

---

### Task 3: AcceptanceCriterion CRUD

**Files:**
- Modify: `backend/app/schemas.py`
- Create: `backend/app/routers/acceptance_criteria.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_acceptance_criteria.py`

**Interfaces:**
- Consumes: `app.models.AcceptanceCriterion/.Task` (Task 1 / Task 2)
- Produces: `app.schemas.AcceptanceCriterionCreate/.AcceptanceCriterionUpdate/.AcceptanceCriterionRead`. Router mounted at `/tasks/{task_id}/acceptance-criteria` — consumed by Task 4's frontend `TaskPanel`.

- [ ] **Step 1: Add the schemas**

Append to `backend/app/schemas.py`:

```python


class AcceptanceCriterionCreate(BaseModel):
    format: Literal["basic", "gherkin"] = "basic"
    description: str | None = None
    given: str | None = None
    when_: str | None = None
    then_: str | None = None
    position: int = 0


class AcceptanceCriterionUpdate(BaseModel):
    description: str | None = None
    given: str | None = None
    when_: str | None = None
    then_: str | None = None
    position: int | None = None
    checked: bool | None = None
    notes: str | None = None


class AcceptanceCriterionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    task_id: uuid.UUID
    format: str
    description: str | None
    given: str | None
    when_: str | None
    then_: str | None
    position: int
    checked: bool
    checked_at: datetime | None
    notes: str | None
    created_at: datetime
```

- [ ] **Step 2: Write the failing tests**

Create `backend/tests/test_acceptance_criteria.py`:

```python
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
```

- [ ] **Step 3: Run to verify it fails**

Run: `uv run pytest tests/test_acceptance_criteria.py -v` (from `backend/`)
Expected: FAIL — `404 Not Found` on `POST /tasks/{task_id}/acceptance-criteria`

- [ ] **Step 4: Implement the router**

Create `backend/app/routers/acceptance_criteria.py`. Note: paths are written out in full on each route decorator rather than via `APIRouter(prefix=...)` — FastAPI's router `prefix` cannot itself contain a path parameter like `{task_id}`, so each route declares its complete path:

```python
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import AcceptanceCriterion, Task
from app.schemas import (
    AcceptanceCriterionCreate,
    AcceptanceCriterionRead,
    AcceptanceCriterionUpdate,
)

router = APIRouter(tags=["acceptance-criteria"])


@router.get("/tasks/{task_id}/acceptance-criteria", response_model=list[AcceptanceCriterionRead])
async def list_acceptance_criteria(
    task_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> list[AcceptanceCriterion]:
    task = await db.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")

    result = await db.execute(
        select(AcceptanceCriterion)
        .where(AcceptanceCriterion.task_id == task_id)
        .order_by(AcceptanceCriterion.position)
    )
    return list(result.scalars().all())


@router.post(
    "/tasks/{task_id}/acceptance-criteria",
    response_model=AcceptanceCriterionRead,
    status_code=201,
)
async def create_acceptance_criterion(
    task_id: uuid.UUID, payload: AcceptanceCriterionCreate, db: AsyncSession = Depends(get_db)
) -> AcceptanceCriterion:
    task = await db.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")

    criterion = AcceptanceCriterion(task_id=task_id, **payload.model_dump())
    db.add(criterion)
    await db.commit()
    await db.refresh(criterion)
    return criterion


@router.patch(
    "/tasks/{task_id}/acceptance-criteria/{criterion_id}", response_model=AcceptanceCriterionRead
)
async def update_acceptance_criterion(
    task_id: uuid.UUID,
    criterion_id: uuid.UUID,
    payload: AcceptanceCriterionUpdate,
    db: AsyncSession = Depends(get_db),
) -> AcceptanceCriterion:
    criterion = await db.get(AcceptanceCriterion, criterion_id)
    if criterion is None or criterion.task_id != task_id:
        raise HTTPException(status_code=404, detail="Acceptance criterion not found")

    updates = payload.model_dump(exclude_unset=True)
    if "checked" in updates:
        criterion.checked = updates.pop("checked")
        criterion.checked_at = datetime.now(timezone.utc) if criterion.checked else None

    for field, value in updates.items():
        setattr(criterion, field, value)

    await db.commit()
    await db.refresh(criterion)
    return criterion


@router.delete("/tasks/{task_id}/acceptance-criteria/{criterion_id}", status_code=204)
async def delete_acceptance_criterion(
    task_id: uuid.UUID, criterion_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> None:
    criterion = await db.get(AcceptanceCriterion, criterion_id)
    if criterion is None or criterion.task_id != task_id:
        raise HTTPException(status_code=404, detail="Acceptance criterion not found")
    await db.delete(criterion)
    await db.commit()
```

- [ ] **Step 5: Wire the router into the app**

In `backend/app/main.py`, add `from app.routers.acceptance_criteria import router as acceptance_criteria_router` and `app.include_router(acceptance_criteria_router)`.

- [ ] **Step 6: Run the full backend suite**

Run: `uv run pytest -v` (from `backend/`)
Expected: `85 passed` (79 from Task 2 + 6 acceptance criteria tests)

- [ ] **Step 7: Commit**

```bash
git add backend/app/schemas.py backend/app/routers/acceptance_criteria.py backend/app/main.py backend/tests/test_acceptance_criteria.py
git commit -m "feat(backend): add nested AcceptanceCriterion CRUD"
```

---

### Task 4: Frontend — FeatureDetailPage and the Split-View TaskPanel

**Files:**
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/pages/EpicDetailPage.tsx`
- Create: `frontend/src/pages/FeatureDetailPage.tsx`
- Create: `frontend/src/components/TaskPanel.tsx`
- Modify: `frontend/src/App.tsx`

**Interfaces:**
- Consumes: `api.getEpic`, `api.getInitiative`, `api.getProduct`, `api.listProjects` (already exist), new `api.getFeature`/`.listTasks`/`.createTask`/`.getTask`/`.updateTask`/`.listAcceptanceCriteria`/`.createAcceptanceCriterion`/`.toggleAcceptanceCriterion` (this task adds them)
- Produces: nothing consumed by later tasks — this is the last task of the plan.

- [ ] **Step 1: Add Task/AcceptanceCriterion types and methods to the API client**

In `frontend/src/lib/api.ts`, add these interfaces near the existing ones:

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
}

export interface AcceptanceCriterion {
  id: string;
  task_id: string;
  format: string;
  description: string | null;
  given: string | null;
  when_: string | null;
  then_: string | null;
  position: number;
  checked: boolean;
  checked_at: string | null;
  notes: string | null;
  created_at: string;
}
```

Add these methods to the exported `api` object (add `getFeature` near the existing Feature methods, the rest near the end):

```typescript
  getFeature: (id: string) => request<Feature>(`/features/${id}`),
```

```typescript
  listTasks: (featureId: string) => request<Task[]>(`/tasks?feature_id=${featureId}`),
  createTask: (data: { feature_id: string; project_id: string; title: string; task_type: string }) =>
    request<Task>("/tasks", { method: "POST", body: JSON.stringify(data) }),
  getTask: (id: string) => request<Task>(`/tasks/${id}`),
  updateTask: (
    id: string,
    data: Partial<{ title: string; task_type: string; status: string; context: string }>,
  ) => request<Task>(`/tasks/${id}`, { method: "PATCH", body: JSON.stringify(data) }),

  listAcceptanceCriteria: (taskId: string) =>
    request<AcceptanceCriterion[]>(`/tasks/${taskId}/acceptance-criteria`),
  createAcceptanceCriterion: (
    taskId: string,
    data: { format: string; description?: string; given?: string; when_?: string; then_?: string },
  ) =>
    request<AcceptanceCriterion>(`/tasks/${taskId}/acceptance-criteria`, {
      method: "POST",
      body: JSON.stringify(data),
    }),
  toggleAcceptanceCriterion: (taskId: string, criterionId: string, checked: boolean) =>
    request<AcceptanceCriterion>(`/tasks/${taskId}/acceptance-criteria/${criterionId}`, {
      method: "PATCH",
      body: JSON.stringify({ checked }),
    }),
```

- [ ] **Step 2: Make Feature cards on the Epic page clickable**

In `frontend/src/pages/EpicDetailPage.tsx`, find this block:

```tsx
      <div className="flex flex-col gap-2">
        {features.map((feature) => (
          <Card key={feature.id}>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <span className="rounded bg-blue-100 px-2 py-0.5 text-xs font-mono text-blue-800">
                  {feature.issue_key}
                </span>
                {feature.name}
              </CardTitle>
            </CardHeader>
            <CardContent className="text-sm text-muted-foreground">{feature.status}</CardContent>
          </Card>
        ))}
      </div>
```

Replace it with:

```tsx
      <div className="flex flex-col gap-2">
        {features.map((feature) => (
          <Link
            key={feature.id}
            to={`/products/${productId}/initiatives/${initiativeId}/epics/${epicId}/features/${feature.id}`}
          >
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <span className="rounded bg-blue-100 px-2 py-0.5 text-xs font-mono text-blue-800">
                    {feature.issue_key}
                  </span>
                  {feature.name}
                </CardTitle>
              </CardHeader>
              <CardContent className="text-sm text-muted-foreground">{feature.status}</CardContent>
            </Card>
          </Link>
        ))}
      </div>
```

(`Link`, `productId`, `initiativeId`, `epicId` are already imported/in scope in this file.)

- [ ] **Step 3: Write the split-view TaskPanel component**

Create `frontend/src/components/TaskPanel.tsx`:

```tsx
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { api, type AcceptanceCriterion, type Project, type Task } from "@/lib/api";

interface TaskPanelProps {
  taskId: string | null;
  featureId: string;
  projects: Project[];
  onClose: () => void;
  onSaved: () => void;
}

export function TaskPanel({ taskId, featureId, projects, onClose, onSaved }: TaskPanelProps) {
  const [task, setTask] = useState<Task | null>(null);
  const [criteria, setCriteria] = useState<AcceptanceCriterion[]>([]);
  const [title, setTitle] = useState("");
  const [taskType, setTaskType] = useState("feature");
  const [projectId, setProjectId] = useState(projects[0]?.id ?? "");
  const [status, setStatus] = useState("todo");
  const [context, setContext] = useState("");

  const [acFormat, setAcFormat] = useState<"basic" | "gherkin">("basic");
  const [acDescription, setAcDescription] = useState("");
  const [acGiven, setAcGiven] = useState("");
  const [acWhen, setAcWhen] = useState("");
  const [acThen, setAcThen] = useState("");

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
  }, [taskId]);

  const handleSave = async (event: React.FormEvent) => {
    event.preventDefault();
    try {
      if (taskId) {
        await api.updateTask(taskId, { title, task_type: taskType, status, context });
      } else {
        await api.createTask({ feature_id: featureId, project_id: projectId, title, task_type: taskType });
      }
      onSaved();
    } catch {
      // panel stays open with input intact
    }
  };

  const handleAddCriterion = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!taskId) return;
    try {
      await api.createAcceptanceCriterion(taskId, {
        format: acFormat,
        description: acFormat === "basic" ? acDescription : undefined,
        given: acFormat === "gherkin" ? acGiven : undefined,
        when_: acFormat === "gherkin" ? acWhen : undefined,
        then_: acFormat === "gherkin" ? acThen : undefined,
      });
      setAcDescription("");
      setAcGiven("");
      setAcWhen("");
      setAcThen("");
      api.listAcceptanceCriteria(taskId).then(setCriteria);
    } catch {
      // form stays open with input intact
    }
  };

  const handleToggleCriterion = async (criterionId: string, checked: boolean) => {
    if (!taskId) return;
    await api.toggleAcceptanceCriterion(taskId, criterionId, checked);
    api.listAcceptanceCriteria(taskId).then(setCriteria);
  };

  return (
    <div className="fixed inset-y-0 right-0 z-50 flex w-96 flex-col overflow-y-auto border-l bg-white p-6 shadow-lg">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-lg font-semibold">{taskId ? (task?.issue_key ?? "Task") : "New Task"}</h2>
        <button type="button" onClick={onClose} className="text-sm underline">
          Close
        </button>
      </div>

      <form onSubmit={handleSave} className="flex flex-col gap-2">
        <input
          className="rounded border px-2 py-1"
          placeholder="Title"
          value={title}
          onChange={(event) => setTitle(event.target.value)}
          required
        />
        <select
          className="rounded border px-2 py-1"
          value={taskType}
          onChange={(event) => setTaskType(event.target.value)}
        >
          <option value="feature">Feature</option>
          <option value="bug">Bug</option>
          <option value="improvement">Improvement</option>
          <option value="chore">Chore</option>
          <option value="research">Research</option>
        </select>
        {!taskId && (
          <select
            className="rounded border px-2 py-1"
            value={projectId}
            onChange={(event) => setProjectId(event.target.value)}
            required
          >
            {projects.map((project) => (
              <option key={project.id} value={project.id}>
                {project.name}
              </option>
            ))}
          </select>
        )}
        {taskId && (
          <select
            className="rounded border px-2 py-1"
            value={status}
            onChange={(event) => setStatus(event.target.value)}
          >
            <option value="todo">Todo</option>
            <option value="in_progress">In Progress</option>
            <option value="done">Done</option>
            <option value="outdated">Outdated</option>
          </select>
        )}
        <textarea
          className="rounded border px-2 py-1"
          placeholder="Context"
          value={context}
          onChange={(event) => setContext(event.target.value)}
        />
        <Button type="submit">{taskId ? "Save" : "Create"}</Button>
      </form>

      {taskId && (
        <div className="mt-6">
          <h3 className="mb-2 text-sm font-semibold">Acceptance Criteria</h3>
          <div className="flex flex-col gap-2">
            {criteria.map((criterion) => (
              <label key={criterion.id} className="flex items-start gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={criterion.checked}
                  onChange={(event) => handleToggleCriterion(criterion.id, event.target.checked)}
                />
                <span>
                  {criterion.format === "basic"
                    ? criterion.description
                    : `Given ${criterion.given}, when ${criterion.when_}, then ${criterion.then_}`}
                </span>
              </label>
            ))}
          </div>

          <form onSubmit={handleAddCriterion} className="mt-3 flex flex-col gap-2">
            <select
              className="rounded border px-2 py-1"
              value={acFormat}
              onChange={(event) => setAcFormat(event.target.value as "basic" | "gherkin")}
            >
              <option value="basic">Basic</option>
              <option value="gherkin">Gherkin</option>
            </select>
            {acFormat === "basic" && (
              <input
                className="rounded border px-2 py-1"
                placeholder="Description"
                value={acDescription}
                onChange={(event) => setAcDescription(event.target.value)}
                required
              />
            )}
            {acFormat === "gherkin" && (
              <>
                <input
                  className="rounded border px-2 py-1"
                  placeholder="Given"
                  value={acGiven}
                  onChange={(event) => setAcGiven(event.target.value)}
                  required
                />
                <input
                  className="rounded border px-2 py-1"
                  placeholder="When"
                  value={acWhen}
                  onChange={(event) => setAcWhen(event.target.value)}
                  required
                />
                <input
                  className="rounded border px-2 py-1"
                  placeholder="Then"
                  value={acThen}
                  onChange={(event) => setAcThen(event.target.value)}
                  required
                />
              </>
            )}
            <Button type="submit">Add Criterion</Button>
          </form>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Write the Feature detail page**

Create `frontend/src/pages/FeatureDetailPage.tsx`:

```tsx
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { Breadcrumb } from "@/components/Breadcrumb";
import { Button } from "@/components/ui/button";
import { TaskPanel } from "@/components/TaskPanel";
import {
  api,
  type Epic,
  type Feature,
  type Initiative,
  type Product,
  type Project,
  type Task,
} from "@/lib/api";

export function FeatureDetailPage() {
  const { productId, initiativeId, epicId, featureId } = useParams<{
    productId: string;
    initiativeId: string;
    epicId: string;
    featureId: string;
  }>();
  const [product, setProduct] = useState<Product | null>(null);
  const [initiative, setInitiative] = useState<Initiative | null>(null);
  const [epic, setEpic] = useState<Epic | null>(null);
  const [feature, setFeature] = useState<Feature | null>(null);
  const [projects, setProjects] = useState<Project[]>([]);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [loadError, setLoadError] = useState(false);
  const [openTaskId, setOpenTaskId] = useState<string | "new" | null>(null);

  const loadTasks = () => {
    if (!featureId) return;
    api.listTasks(featureId).then(setTasks);
  };

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

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [productId, initiativeId, epicId, featureId]);

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

  if (!product || !initiative || !epic || !feature) return null;

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
          {
            label: feature.name,
            to: `/products/${product.id}/initiatives/${initiative.id}/epics/${epic.id}/features/${feature.id}`,
          },
        ]}
      />

      <div className="mb-4 flex items-center justify-between">
        <h1 className="text-2xl font-semibold">{feature.name} — Tasks</h1>
        <Button onClick={() => setOpenTaskId("new")}>New Task</Button>
      </div>

      <div className="flex flex-col gap-2">
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
      </div>

      {openTaskId && (
        <TaskPanel
          taskId={openTaskId === "new" ? null : openTaskId}
          featureId={feature.id}
          projects={projects}
          onClose={() => setOpenTaskId(null)}
          onSaved={() => {
            setOpenTaskId(null);
            loadTasks();
          }}
        />
      )}
    </div>
  );
}
```

- [ ] **Step 5: Add the route**

In `frontend/src/App.tsx`, add the import:

```tsx
import { FeatureDetailPage } from "@/pages/FeatureDetailPage";
```

and add this route inside `<Routes>`:

```tsx
        <Route
          path="/products/:productId/initiatives/:initiativeId/epics/:epicId/features/:featureId"
          element={<FeatureDetailPage />}
        />
```

- [ ] **Step 6: Verify the build compiles**

Run: `cd frontend && npm run build`
Expected: exits 0, no TypeScript errors

- [ ] **Step 7: Manual smoke test**

Run: `npm run dev` (from `frontend/`, with the backend also running per the root README's instructions)
Open the app: navigate to a Feature, click "New Task", fill in a title and pick a Project, submit — confirm the panel closes and the new Task appears in the list with an issue_key badge. Click the Task to reopen the panel, change its status, add a basic Acceptance Criterion, check it off, and confirm the checkbox state persists after closing and reopening the panel.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/lib/api.ts frontend/src/pages/EpicDetailPage.tsx frontend/src/pages/FeatureDetailPage.tsx frontend/src/components/TaskPanel.tsx frontend/src/App.tsx
git commit -m "feat(frontend): add FeatureDetailPage and split-view TaskPanel"
```
