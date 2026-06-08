"""add extra market meal categories

Revision ID: 20260608_0002
Revises: 20260608_0001
"""

from __future__ import annotations

from alembic import op

revision = "20260608_0002"
down_revision = "20260608_0001"
branch_labels = None
depends_on = None


MARKET_MEAL_CATEGORY_VALUES = (
    "FOOD",
    "VEGETABLES_HERBS",
    "FRUITS_BERRIES",
    "DAIRY_EGGS",
    "DRIED_FRUITS_NUTS",
    "MEAT_POULTRY",
    "FISH_SEAFOOD",
    "SAUSAGE",
    "PASTA_GRAINS",
    "OILS_SAUCES_SPICES",
    "CANNED_PICKLES",
    "BREAD_BAKERY",
    "SWEETS",
    "JUICES_SODAS",
)

LEGACY_MEAL_CATEGORY_VALUES = (
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


def _values_sql(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def upgrade() -> None:
    values_sql = _values_sql(MARKET_MEAL_CATEGORY_VALUES + LEGACY_MEAL_CATEGORY_VALUES)
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
    previous_market_values = tuple(
        value for value in MARKET_MEAL_CATEGORY_VALUES if value not in {"FOOD", "JUICES_SODAS"}
    )
    values_sql = _values_sql(previous_market_values + LEGACY_MEAL_CATEGORY_VALUES)
    op.execute(
        """
        ALTER TABLE meal
        DROP CONSTRAINT IF EXISTS meal_category_check
        """
    )
    op.execute(
        """
        UPDATE meal
        SET category = NULL
        WHERE category IN ('FOOD', 'JUICES_SODAS')
        """
    )
    op.execute(
        f"""
        ALTER TABLE meal
        ADD CONSTRAINT meal_category_check
        CHECK (category IS NULL OR category IN ({values_sql}))
        """
    )
