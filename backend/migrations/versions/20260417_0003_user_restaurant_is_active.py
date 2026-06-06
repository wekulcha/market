"""user and restaurant is_active flags

Revision ID: 0003
Revises: 0002
Create Date: 2026-04-17

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260417_0003"
down_revision = "20260417_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )
    op.add_column(
        "restaurant",
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )
    op.alter_column("users", "is_active", server_default=None)
    op.alter_column("restaurant", "is_active", server_default=None)


def downgrade() -> None:
    op.drop_column("restaurant", "is_active")
    op.drop_column("users", "is_active")
