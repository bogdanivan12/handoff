import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import Epic, Initiative
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
    initiative = await db.get(Initiative, payload.initiative_id)
    if initiative is None:
        raise HTTPException(status_code=404, detail="Initiative not found")

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
