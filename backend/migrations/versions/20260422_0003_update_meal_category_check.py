"""update meal category check constraint

Revision ID: 20260422_0003
Revises: 20260422_0002
"""

from __future__ import annotations

from alembic import op

revision = "20260422_0003"
down_revision = "20260422_0002"
branch_labels = None
depends_on = None


MEAL_CATEGORY_VALUES = (
    "FIRST",
    "SECOND",
    "SOUP",
    "SALAD",
    "SIDE",
    "BAKERY",
    "KEBAB",
    "GRILL",
    "COMBO",
    "SNACK",
    "BREAKFAST",
    "DESSERT",
    "DRINK",
    "SAUCE",
    "PLATTER",
)


def upgrade() -> None:
    values_sql = ", ".join(f"'{value}'" for value in MEAL_CATEGORY_VALUES)
    op.execute(
        """
        ALTER TABLE meal
        DROP CONSTRAINT IF EXISTS meal_category_check
        """
    )
    op.execute(
        f"""
        ALTER TABLE meal
        ADD CONSTRAINT meal_category_check
        CHECK (category IS NULL OR category IN ({values_sql}))
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE meal
        DROP CONSTRAINT IF EXISTS meal_category_check
        """
    )
