"""dependencies

Revision ID: 0006
Revises: 0005
Create Date: 2026-09-05 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "task_dependencies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "task_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tasks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "depends_on_task_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tasks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("task_id != depends_on_task_id", name="ck_task_dependencies_no_self_link"),
    )
    op.create_index("idx_task_dependencies_task", "task_dependencies", ["task_id"])
    op.create_index(
        "idx_task_dependencies_depends_on", "task_dependencies", ["depends_on_task_id"]
    )

    op.create_table(
        "feature_dependencies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "feature_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("features.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "depends_on_feature_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("features.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "feature_id != depends_on_feature_id", name="ck_feature_dependencies_no_self_link"
        ),
    )
    op.create_index("idx_feature_dependencies_feature", "feature_dependencies", ["feature_id"])
    op.create_index(
        "idx_feature_dependencies_depends_on", "feature_dependencies", ["depends_on_feature_id"]
    )


def downgrade() -> None:
    op.drop_table("feature_dependencies")
    op.drop_table("task_dependencies")
