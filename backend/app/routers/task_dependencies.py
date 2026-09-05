import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased, selectinload

from app.db import get_db
from app.models import Epic, Feature, Initiative, Task, TaskDependency
from app.schemas import TaskDependencyCreate, TaskDependencyRead, TaskIsBlockedRead
from app.task_blocking import DONE_STATUS

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
        .where(TaskDependency.task_id == task_id, depends_on.status != DONE_STATUS)
        .options(
            selectinload(depends_on.feature)
            .selectinload(Feature.epic)
            .selectinload(Epic.initiative)
            .selectinload(Initiative.product)
        )
        .order_by(TaskDependency.created_at)
    )
    blocking_tasks = list(result.scalars().all())
    return TaskIsBlockedRead(
        is_blocked=len(blocking_tasks) > 0,
        blocking_tasks=blocking_tasks,
    )
