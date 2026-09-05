import uuid

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Product


async def allocate_issue_number(db: AsyncSession, product_id: uuid.UUID) -> int:
    """Atomically reserve the next issue number for a Product.

    MUST be called inside the same transaction/session as the insert of the
    row being numbered (Feature today, Task from Phase 4 onward) — the
    counter increment and that insert commit together or not at all. There
    is exactly one counter per Product (`Product.next_issue_number`),
    shared across every issue-numbered entity type. Never create a second
    counter or a per-entity-type sequence.
    """
    result = await db.execute(
        update(Product)
        .where(Product.id == product_id)
        .values(next_issue_number=Product.next_issue_number + 1)
        .returning(Product.next_issue_number)
    )
    return result.scalar_one() - 1
