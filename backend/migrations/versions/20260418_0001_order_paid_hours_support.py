"""order is_paid, restaurant hours, support_ticket

Revision ID: 20260418_0001
Revises: 20260417_0004
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260418_0001"
down_revision = "20260417_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "orders",
        sa.Column("is_paid", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.alter_column("orders", "is_paid", server_default=None)

    op.add_column("restaurant", sa.Column("working_hours_from", sa.String(length=8), nullable=True))
    op.add_column("restaurant", sa.Column("working_hours_to", sa.String(length=8), nullable=True))
    op.add_column("restaurant", sa.Column("orders_accept_from", sa.String(length=8), nullable=True))
    op.add_column("restaurant", sa.Column("orders_accept_to", sa.String(length=8), nullable=True))

    op.create_table(
        "support_ticket",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("closed_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_support_ticket_user_status",
        "support_ticket",
        ["user_telegram_id", "status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_support_ticket_user_status", table_name="support_ticket")
    op.drop_table("support_ticket")
    op.drop_column("restaurant", "orders_accept_to")
    op.drop_column("restaurant", "orders_accept_from")
    op.drop_column("restaurant", "working_hours_to")
    op.drop_column("restaurant", "working_hours_from")
    op.drop_column("orders", "is_paid")
