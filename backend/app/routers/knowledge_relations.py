import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import KnowledgeItem, KnowledgeRelation
from app.schemas import KnowledgeRelationCreate, KnowledgeRelationRead

router = APIRouter(prefix="/knowledge-relations", tags=["knowledge-relations"])


@router.get("", response_model=list[KnowledgeRelationRead])
async def list_knowledge_relations(
    from_item_id: uuid.UUID | None = Query(default=None),
    to_item_id: uuid.UUID | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> list[KnowledgeRelation]:
    if (from_item_id is None) == (to_item_id is None):
        raise HTTPException(
            status_code=422, detail="Provide exactly one of from_item_id or to_item_id"
        )

    query = select(KnowledgeRelation)
    if from_item_id is not None:
        query = query.where(KnowledgeRelation.from_item_id == from_item_id)
    else:
        query = query.where(KnowledgeRelation.to_item_id == to_item_id)

    result = await db.execute(query.order_by(KnowledgeRelation.created_at))
    return list(result.scalars().all())


@router.post("", response_model=KnowledgeRelationRead, status_code=201)
async def create_knowledge_relation(
    payload: KnowledgeRelationCreate, db: AsyncSession = Depends(get_db)
) -> KnowledgeRelation:
    if payload.from_item_id == payload.to_item_id:
        raise HTTPException(status_code=422, detail="from_item_id and to_item_id must differ")

    from_item = await db.get(KnowledgeItem, payload.from_item_id)
    if from_item is None:
        raise HTTPException(status_code=404, detail="from_item_id not found")

    to_item = await db.get(KnowledgeItem, payload.to_item_id)
    if to_item is None:
        raise HTTPException(status_code=404, detail="to_item_id not found")

    relation = KnowledgeRelation(**payload.model_dump())
    db.add(relation)
    await db.commit()
    await db.refresh(relation)
    return relation


@router.delete("/{relation_id}", status_code=204)
async def delete_knowledge_relation(
    relation_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> None:
    relation = await db.get(KnowledgeRelation, relation_id)
    if relation is None:
        raise HTTPException(status_code=404, detail="Knowledge relation not found")
    await db.delete(relation)
    await db.commit()
