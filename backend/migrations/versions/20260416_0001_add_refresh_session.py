"""add refresh_session table

Revision ID: 20260416_0001
Revises: 20260415_0000
Create Date: 2026-04-16 22:25:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260416_0001"
down_revision = "20260415_0000"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "refresh_session",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("token_hash", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("last_used_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_refresh_session_token_hash",
        "refresh_session",
        ["token_hash"],
        unique=True,
    )
    op.create_index(
        "ix_refresh_session_user_id",
        "refresh_session",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_refresh_session_user_id", table_name="refresh_session")
    op.drop_index("ix_refresh_session_token_hash", table_name="refresh_session")
    op.drop_table("refresh_session")
