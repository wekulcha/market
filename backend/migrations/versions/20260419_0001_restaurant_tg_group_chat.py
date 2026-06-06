"""restaurant telegram group chat id

Revision ID: 20260419_0001
Revises: 20260418_0001
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260419_0001"
down_revision = "20260418_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("restaurant", sa.Column("telegram_group_chat_id", sa.BigInteger(), nullable=True))


def downgrade() -> None:
    op.drop_column("restaurant", "telegram_group_chat_id")
