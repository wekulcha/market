"""initial schema

Revision ID: 20260415_0000
Revises:
Create Date: 2026-04-15 00:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260415_0000"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger(), autoincrement=False, nullable=False),
        sa.Column("username", sa.String(length=200), nullable=False),
        sa.Column("phone", sa.String(), nullable=False),
        sa.Column("email", sa.String(), nullable=True),
        sa.Column("address", sa.String(), nullable=True),
        sa.Column("registered_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("phone"),
    )

    op.create_table(
        "restaurant",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("address", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "courier",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )

    op.create_table(
        "meal",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("restaurant_id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("weight", sa.Integer(), nullable=True),
        sa.Column("calorie", sa.Integer(), nullable=True),
        sa.Column("image_link", sa.String(length=2048), nullable=False),
        sa.Column("category", sa.String(length=64), nullable=True),
        sa.Column("price", sa.Numeric(), nullable=False),
        sa.Column("is_available", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["restaurant_id"], ["restaurant.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "staff",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("restaurant_id", sa.BigInteger(), nullable=False),
        sa.Column("permission", sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(["restaurant_id"], ["restaurant.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "restaurant_id", "permission"),
    )

    op.create_table(
        "subscription_log",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("restaurant_id", sa.BigInteger(), nullable=False),
        sa.Column("price", sa.Numeric(), nullable=True),
        sa.Column("start_dttm", sa.DateTime(), nullable=True),
        sa.Column("end_dttm", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["restaurant_id"], ["restaurant.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "orders",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("delivery_address", sa.String(), nullable=True),
        sa.Column("restaurant_id", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("courier_id", sa.BigInteger(), nullable=True),
        sa.Column("order_type", sa.String(length=64), nullable=False),
        sa.Column("items_total", sa.Numeric(), nullable=False),
        sa.Column("delivery_fee", sa.Numeric(), nullable=False),
        sa.Column("service_fee", sa.Numeric(), nullable=False),
        sa.Column("total", sa.Numeric(), nullable=False),
        sa.ForeignKeyConstraint(["courier_id"], ["courier.id"]),
        sa.ForeignKeyConstraint(["restaurant_id"], ["restaurant.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "order_position",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("meal_id", sa.BigInteger(), nullable=False),
        sa.Column("order_id", sa.BigInteger(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_price", sa.Numeric(), nullable=False),
        sa.Column("total_price", sa.Numeric(), nullable=False),
        sa.ForeignKeyConstraint(["meal_id"], ["meal.id"]),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("order_position")
    op.drop_table("orders")
    op.drop_table("subscription_log")
    op.drop_table("staff")
    op.drop_table("meal")
    op.drop_table("courier")
    op.drop_table("restaurant")
    op.drop_table("users")
