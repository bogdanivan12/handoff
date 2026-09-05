import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db import get_db
from app.issue_numbers import allocate_issue_number
from app.models import Epic, Feature, Initiative, Project, Sprint, Task
from app.schemas import TaskCreate, TaskRead, TaskUpdate
from app.task_blocking import attach_is_blocked

router = APIRouter(prefix="/tasks", tags=["tasks"])

_EAGER_LOAD = (
    selectinload(Task.feature)
    .selectinload(Feature.epic)
    .selectinload(Epic.initiative)
    .selectinload(Initiative.product)
)


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

    if project.product_id != initiative.product_id:
        raise HTTPException(
            status_code=400, detail="Project does not belong to this Feature's Product"
        )
    if payload.sprint_id is not None and sprint.product_id != initiative.product_id:
        raise HTTPException(
            status_code=400, detail="Sprint does not belong to this Feature's Product"
        )

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
    task = result.scalar_one()
    await attach_is_blocked(db, [task])
    return task


@router.get("/{task_id}", response_model=TaskRead)
async def get_task(task_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> Task:
    result = await db.execute(select(Task).where(Task.id == task_id).options(_EAGER_LOAD))
    task = result.scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    await attach_is_blocked(db, [task])
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
    task = result.scalar_one()
    await attach_is_blocked(db, [task])
    return task


@router.delete("/{task_id}", status_code=204)
async def delete_task(task_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> None:
    task = await db.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    await db.delete(task)
    await db.commit()
