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
