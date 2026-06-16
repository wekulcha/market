"""store per-unit final weights

Revision ID: 20260610_0006
Revises: 20260610_0005
Create Date: 2026-06-16
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260610_0006"
down_revision = "20260610_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "order_position_unit_weight",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("order_position_id", sa.BigInteger(), nullable=False),
        sa.Column("unit_index", sa.Integer(), nullable=False),
        sa.Column("weight_grams", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["order_position_id"],
            ["order_position.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_unique_constraint(
        "uq_order_position_unit_weight_position_index",
        "order_position_unit_weight",
        ["order_position_id", "unit_index"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_order_position_unit_weight_position_index",
        "order_position_unit_weight",
        type_="unique",
    )
    op.drop_table("order_position_unit_weight")
