"""add order reviews

Revision ID: 20260610_0001
Revises: 20260608_0002
Create Date: 2026-06-10
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260610_0001"
down_revision = "20260608_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("orders", sa.Column("review_rating", sa.Integer(), nullable=True))
    op.add_column("orders", sa.Column("review_text", sa.String(), nullable=True))
    op.add_column("orders", sa.Column("review_created_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("orders", "review_created_at")
    op.drop_column("orders", "review_text")
    op.drop_column("orders", "review_rating")
