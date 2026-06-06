"""restaurant image_link, orders user telegram message id

Revision ID: 20260417_0002
Revises: 20260416_0001
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260417_0002"
down_revision = "20260416_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("restaurant", sa.Column("image_link", sa.String(), nullable=True))
    op.add_column(
        "orders",
        sa.Column("user_telegram_notify_message_id", sa.BigInteger(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("orders", "user_telegram_notify_message_id")
    op.drop_column("restaurant", "image_link")
