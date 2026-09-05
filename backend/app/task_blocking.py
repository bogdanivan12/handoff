import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.models import Task, TaskDependency

# Single source of truth for "does this dependency block its dependent task".
# Only "done" is non-blocking — "outdated" is deliberately still blocking,
# matching the design doc's literal wording (schema.sql's task_status enum
# treats outdated as terminal, paired with superseded_by_task_id).
DONE_STATUS = "done"


async def compute_is_blocked_map(
    db: AsyncSession, task_ids: list[uuid.UUID]
) -> dict[uuid.UUID, bool]:
    if not task_ids:
        return {}
    depends_on = aliased(Task)
    result = await db.execute(
        select(TaskDependency.task_id)
        .join(depends_on, TaskDependency.depends_on_task_id == depends_on.id)
        .where(TaskDependency.task_id.in_(task_ids), depends_on.status != DONE_STATUS)
        .distinct()
    )
    blocked_ids = set(result.scalars().all())
    return {task_id: task_id in blocked_ids for task_id in task_ids}


async def attach_is_blocked(db: AsyncSession, tasks: list[Task]) -> list[Task]:
    blocked_map = await compute_is_blocked_map(db, [task.id for task in tasks])
    for task in tasks:
        task.is_blocked = blocked_map.get(task.id, False)
    return tasks
