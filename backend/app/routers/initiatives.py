import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import Initiative, Product
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
    product = await db.get(Product, payload.product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")

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
