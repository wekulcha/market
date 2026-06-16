"""support weighted order items

Revision ID: 20260610_0005
Revises: 20260610_0004
Create Date: 2026-06-16
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260610_0005"
down_revision = "20260610_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "meal",
        sa.Column("requires_final_weight", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("order_position", sa.Column("final_weight_grams", sa.Integer(), nullable=True))
    op.alter_column("meal", "requires_final_weight", server_default=None)


def downgrade() -> None:
    op.drop_column("order_position", "final_weight_grams")
    op.drop_column("meal", "requires_final_weight")
