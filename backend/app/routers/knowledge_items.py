import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import KnowledgeItem, Product, Project
from app.schemas import KnowledgeItemCreate, KnowledgeItemRead, KnowledgeItemUpdate

router = APIRouter(prefix="/knowledge-items", tags=["knowledge-items"])


async def _validate_scope_ref(scope: str, scope_ref_id: uuid.UUID, db: AsyncSession) -> None:
    if scope == "product":
        entity = await db.get(Product, scope_ref_id)
        if entity is None:
            raise HTTPException(status_code=404, detail="Product not found")
    else:
        entity = await db.get(Project, scope_ref_id)
        if entity is None:
            raise HTTPException(status_code=404, detail="Project not found")


@router.get("", response_model=list[KnowledgeItemRead])
async def list_knowledge_items(
    scope: Literal["product", "project"] = Query(...),
    scope_ref_id: uuid.UUID = Query(...),
    db: AsyncSession = Depends(get_db),
) -> list[KnowledgeItem]:
    result = await db.execute(
        select(KnowledgeItem)
        .where(KnowledgeItem.scope == scope, KnowledgeItem.scope_ref_id == scope_ref_id)
        .order_by(KnowledgeItem.created_at)
    )
    return list(result.scalars().all())


@router.post("", response_model=KnowledgeItemRead, status_code=201)
async def create_knowledge_item(
    payload: KnowledgeItemCreate, db: AsyncSession = Depends(get_db)
) -> KnowledgeItem:
    await _validate_scope_ref(payload.scope, payload.scope_ref_id, db)

    item = KnowledgeItem(
        type=payload.content.kind,
        scope=payload.scope,
        scope_ref_id=payload.scope_ref_id,
        content=payload.content.model_dump(),
        confidence=payload.confidence,
        provenance=payload.provenance,
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return item


@router.get("/{item_id}", response_model=KnowledgeItemRead)
async def get_knowledge_item(
    item_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> KnowledgeItem:
    item = await db.get(KnowledgeItem, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Knowledge item not found")
    return item


@router.patch("/{item_id}", response_model=KnowledgeItemRead)
async def update_knowledge_item(
    item_id: uuid.UUID, payload: KnowledgeItemUpdate, db: AsyncSession = Depends(get_db)
) -> KnowledgeItem:
    item = await db.get(KnowledgeItem, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Knowledge item not found")

    updates = payload.model_dump(exclude_unset=True)
    if "content" in updates and updates["content"] is not None:
        item.content = payload.content.model_dump()
        item.type = payload.content.kind
    if "status" in updates and updates["status"] is not None:
        item.status = payload.status

    await db.commit()
    await db.refresh(item)
    return item


@router.delete("/{item_id}", status_code=204)
async def delete_knowledge_item(item_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> None:
    item = await db.get(KnowledgeItem, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Knowledge item not found")
    await db.delete(item)
    await db.commit()
