import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db import get_db
from app.issue_numbers import allocate_issue_number
from app.models import Epic, Feature, Initiative
from app.schemas import FeatureCreate, FeatureRead, FeatureUpdate

router = APIRouter(prefix="/features", tags=["features"])

_EAGER_LOAD = (
    selectinload(Feature.epic).selectinload(Epic.initiative).selectinload(Initiative.product)
)


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


@router.post("", response_model=FeatureRead, status_code=201)
async def create_feature(payload: FeatureCreate, db: AsyncSession = Depends(get_db)) -> Feature:
    epic = await db.get(Epic, payload.epic_id)
    if epic is None:
        raise HTTPException(status_code=404, detail="Epic not found")

    initiative = await db.get(Initiative, epic.initiative_id)
    if initiative is None:
        raise HTTPException(status_code=404, detail="Initiative not found")

    new_issue_number = await allocate_issue_number(db, initiative.product_id)

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
