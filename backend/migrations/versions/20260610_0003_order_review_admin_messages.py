"""store order review admin messages

Revision ID: 20260610_0003
Revises: 20260610_0002
Create Date: 2026-06-10
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260610_0003"
down_revision = "20260610_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("orders", sa.Column("review_admin_messages", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("orders", "review_admin_messages")
