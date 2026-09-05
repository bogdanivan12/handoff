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
