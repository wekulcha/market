"""expand mealcategory enum values

Revision ID: 20260422_0001
Revises: 20260419_0002
"""

from __future__ import annotations

from alembic import op

revision = "20260422_0001"
down_revision = "20260419_0002"
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
        f"""
        DO $$
        DECLARE
            v text;
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM pg_type
                WHERE typname = 'mealcategory'
            ) THEN
                FOREACH v IN ARRAY ARRAY[{values_sql}]
                LOOP
                    IF NOT EXISTS (
                        SELECT 1
                        FROM pg_enum e
                        JOIN pg_type t ON t.oid = e.enumtypid
                        WHERE t.typname = 'mealcategory' AND e.enumlabel = v
                    ) THEN
                        EXECUTE format('ALTER TYPE mealcategory ADD VALUE %L', v);
                    END IF;
                END LOOP;
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    # Удаление enum values в PostgreSQL небезопасно и не поддерживается простым ALTER TYPE.
    pass
