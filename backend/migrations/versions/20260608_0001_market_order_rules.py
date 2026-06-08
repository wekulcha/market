"""market order rules

Revision ID: 20260608_0001
Revises: 20260606_0001
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260608_0001"
down_revision = "20260606_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "meal",
        "image_link",
        existing_type=sa.String(length=2048),
        nullable=True,
    )


def downgrade() -> None:
    op.execute("UPDATE meal SET image_link = '' WHERE image_link IS NULL")
    op.alter_column(
        "meal",
        "image_link",
        existing_type=sa.String(length=2048),
        nullable=False,
    )
