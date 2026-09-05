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
