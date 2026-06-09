"""add user activity logs

Revision ID: 20260610_0002
Revises: 20260610_0001
Create Date: 2026-06-10
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260610_0002"
down_revision = "20260610_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_activity_log",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("event", sa.String(length=64), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_user_activity_log_user_id", "user_activity_log", ["user_id"], unique=False)
    op.create_index("ix_user_activity_log_event", "user_activity_log", ["event"], unique=False)
    op.create_index("ix_user_activity_log_created_at", "user_activity_log", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_user_activity_log_created_at", table_name="user_activity_log")
    op.drop_index("ix_user_activity_log_event", table_name="user_activity_log")
    op.drop_index("ix_user_activity_log_user_id", table_name="user_activity_log")
    op.drop_table("user_activity_log")
