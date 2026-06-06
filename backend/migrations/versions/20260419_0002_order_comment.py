"""orders.comment column

Revision ID: 20260419_0002
Revises: 20260419_0001
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260419_0002"
down_revision = "20260419_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("orders", sa.Column("comment", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("orders", "comment")
