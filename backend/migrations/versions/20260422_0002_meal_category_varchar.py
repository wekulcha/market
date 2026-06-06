"""convert meal.category to varchar

Revision ID: 20260422_0002
Revises: 20260422_0001
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260422_0002"
down_revision = "20260422_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE meal
        ALTER COLUMN category TYPE VARCHAR(64)
        USING category::text
        """
    )


def downgrade() -> None:
    op.alter_column(
        "meal",
        "category",
        existing_type=sa.String(length=64),
        type_=sa.String(length=64),
        existing_nullable=True,
    )
