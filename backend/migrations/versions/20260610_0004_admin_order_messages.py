"""store admin order messages

Revision ID: 20260610_0004
Revises: 20260610_0003
Create Date: 2026-06-16
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260610_0004"
down_revision = "20260610_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("orders", sa.Column("admin_order_messages", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("orders", "admin_order_messages")
