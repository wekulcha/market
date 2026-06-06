"""orders.table_number for dine-in

Revision ID: 20260417_0004
Revises: 20260417_0003
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260417_0004"
down_revision = "20260417_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("orders", sa.Column("table_number", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("orders", "table_number")
