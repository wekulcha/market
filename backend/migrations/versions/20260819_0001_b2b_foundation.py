"""add isolated B2B marketplace foundation

Revision ID: 20260819_0001
Revises: 20260610_0006
Create Date: 2026-08-19
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260819_0001"
down_revision = "20260610_0006"
branch_labels = None
depends_on = None


ROLE_CODES = ("BUYER", "SELLER", "ADMIN", "SUPERADMIN", "DISPATCHER", "COURIER")
BUYER_STATUSES = ("INVITED", "REGISTERED", "TRIAL", "ACTIVE", "PAST_DUE", "EXPIRED", "BLOCKED")
SELLER_STATUSES = ("PENDING", "VERIFIED", "SUSPENDED", "BLOCKED")
INVITE_STATUSES = ("ACTIVE", "EXHAUSTED", "EXPIRED", "REVOKED")
SUBSCRIPTION_STATUSES = ("TRIAL", "ACTIVE", "PAST_DUE", "EXPIRED", "CANCELED", "BLOCKED")
PAYMENT_STATUSES = ("PENDING", "PAID", "FAILED", "CANCELED", "REFUNDED")
OFFER_STATUSES = (
    "DRAFT", "SUBMITTED", "UNDER_REVIEW", "CHANGES_REQUESTED", "REJECTED",
    "APPROVED", "PUBLISHED", "PAUSED", "SOLD_OUT", "EXPIRED", "ARCHIVED",
)
MARKUP_TYPES = ("PERCENT", "FIXED", "MANUAL")
RESERVATION_STATUSES = ("ACTIVE", "RELEASED", "CONVERTED", "EXPIRED", "CANCELED")
INVENTORY_MOVEMENT_TYPES = ("INITIAL", "ADJUSTMENT", "RESERVE", "RELEASE", "SALE", "CANCEL", "RETURN")
CART_STATUSES = ("ACTIVE", "CHECKED_OUT", "ABANDONED")
ORDER_STATUSES = (
    "DRAFT", "RESERVED", "PENDING_CONFIRMATION", "CONFIRMED", "SELLER_PREPARING",
    "READY_FOR_PICKUP", "COURIER_ASSIGNED", "PICKED_UP", "IN_DELIVERY",
    "DELIVERED", "COMPLETED", "CANCELED", "REFUNDED",
)
ORDER_PAYMENT_METHODS = ("PAY_ON_DELIVERY", "BANK_TRANSFER", "MANUAL")
DELIVERY_STATUSES = ("PENDING", "ASSIGNED", "PICKED_UP", "IN_DELIVERY", "DELIVERED", "CANCELED", "FAILED")
NOTIFICATION_STATUSES = ("PENDING", "PROCESSING", "RETRY", "SENT", "FAILED", "CANCELED")
WEBHOOK_STATUSES = ("RECEIVED", "PROCESSED", "IGNORED", "FAILED")


UUID = postgresql.UUID(as_uuid=True)
JSONB = postgresql.JSONB(astext_type=sa.Text())
QTY = sa.Numeric(18, 3)


def _id() -> sa.Column[Any]:
    return sa.Column("id", UUID, nullable=False, primary_key=True)


def _created_at() -> sa.Column[Any]:
    return sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
    )


def _timestamps() -> tuple[sa.Column[Any], sa.Column[Any]]:
    return (
        _created_at(),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )


def _enum_check(column: str, values: Iterable[str], name: str) -> sa.CheckConstraint:
    allowed = ", ".join(f"'{value}'" for value in values)
    return sa.CheckConstraint(f"{column} IN ({allowed})", name=name)


def _fk_uuid(
    name: str,
    target: str,
    *,
    nullable: bool = True,
    ondelete: str,
) -> sa.Column[Any]:
    return sa.Column(
        name,
        UUID,
        sa.ForeignKey(target, ondelete=ondelete),
        nullable=nullable,
    )


def _fk_user(name: str, *, nullable: bool = True, ondelete: str) -> sa.Column[Any]:
    return sa.Column(
        name,
        sa.BigInteger(),
        sa.ForeignKey("users.id", ondelete=ondelete),
        nullable=nullable,
    )


def _create_timestamped(
    name: str,
    *elements: sa.SchemaItem,
    indexes: tuple[tuple[str, tuple[str, ...], bool, sa.TextClause | None], ...] = (),
) -> None:
    op.create_table(name, *elements, _id(), *_timestamps())
    for index_name, columns, unique, where in indexes:
        kwargs: dict[str, Any] = {"unique": unique}
        if where is not None:
            kwargs["postgresql_where"] = where
        op.create_index(index_name, name, list(columns), **kwargs)


def upgrade() -> None:
    _create_timestamped(
        "b2b_roles",
        sa.Column("code", sa.String(32), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        _enum_check("code", ROLE_CODES, "ck_b2b_roles_code"),
        sa.UniqueConstraint("code", name="uq_b2b_roles_code"),
    )

    _create_timestamped(
        "b2b_subscription_plans",
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("price_kopecks", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("duration_days", sa.Integer(), nullable=False),
        sa.Column("trial_days", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("metadata", JSONB, nullable=True),
        sa.CheckConstraint("price_kopecks >= 0", name="ck_b2b_subscription_plans_price"),
        sa.CheckConstraint("duration_days > 0", name="ck_b2b_subscription_plans_duration"),
        sa.CheckConstraint("trial_days >= 0", name="ck_b2b_subscription_plans_trial"),
        sa.CheckConstraint("char_length(currency) = 3", name="ck_b2b_subscription_plans_currency"),
        sa.UniqueConstraint("code", name="uq_b2b_subscription_plans_code"),
    )

    _create_timestamped(
        "b2b_categories",
        _fk_uuid("parent_id", "b2b_categories.id", ondelete="RESTRICT"),
        sa.Column("slug", sa.String(120), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.UniqueConstraint("slug", name="uq_b2b_categories_slug"),
        indexes=(
            ("ix_b2b_categories_parent", ("parent_id",), False, None),
            ("ix_b2b_categories_active_sort", ("is_active", "sort_order"), False, None),
        ),
    )

    _create_timestamped(
        "b2b_user_roles",
        _fk_user("user_id", nullable=False, ondelete="CASCADE"),
        _fk_uuid("role_id", "b2b_roles.id", nullable=False, ondelete="CASCADE"),
        _fk_user("granted_by_user_id", ondelete="SET NULL"),
        sa.UniqueConstraint("user_id", "role_id", name="uq_b2b_user_roles_user_role"),
        indexes=(
            ("ix_b2b_user_roles_user_id", ("user_id",), False, None),
            ("ix_b2b_user_roles_role_id", ("role_id",), False, None),
        ),
    )

    _create_timestamped(
        "b2b_telegram_accounts",
        _fk_user("user_id", nullable=False, ondelete="CASCADE"),
        sa.Column("telegram_user_id", sa.BigInteger(), nullable=False),
        sa.Column("bot_scope", sa.String(32), nullable=False),
        sa.Column("username", sa.String(200), nullable=True),
        sa.Column("first_name", sa.String(200), nullable=True),
        sa.Column("last_name", sa.String(200), nullable=True),
        sa.Column("language_code", sa.String(16), nullable=True),
        sa.Column("last_authenticated_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("telegram_user_id", "bot_scope", name="uq_b2b_telegram_accounts_tg_scope"),
        sa.UniqueConstraint("user_id", "bot_scope", name="uq_b2b_telegram_accounts_user_scope"),
        indexes=(("ix_b2b_telegram_accounts_user_id", ("user_id",), False, None),),
    )

    _create_timestamped(
        "b2b_buyer_profiles",
        _fk_user("user_id", nullable=False, ondelete="RESTRICT"),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("company_type", sa.String(32), nullable=True),
        sa.Column("company_name", sa.String(250), nullable=True),
        sa.Column("inn", sa.String(20), nullable=True),
        sa.Column("contact_name", sa.String(200), nullable=True),
        sa.Column("phone", sa.String(32), nullable=True),
        sa.Column("admin_comment", sa.Text(), nullable=True),
        sa.Column("blocked_at", sa.DateTime(timezone=True), nullable=True),
        _enum_check("status", BUYER_STATUSES, "ck_b2b_buyer_profiles_status"),
        sa.UniqueConstraint("user_id", name="uq_b2b_buyer_profiles_user_id"),
        indexes=(("ix_b2b_buyer_profiles_status", ("status",), False, None),),
    )

    _create_timestamped(
        "b2b_seller_profiles",
        _fk_user("user_id", nullable=False, ondelete="RESTRICT"),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("company_type", sa.String(32), nullable=True),
        sa.Column("company_name", sa.String(250), nullable=False),
        sa.Column("inn", sa.String(20), nullable=True),
        sa.Column("legal_details", JSONB, nullable=True),
        sa.Column("contact_name", sa.String(200), nullable=True),
        sa.Column("phone", sa.String(32), nullable=True),
        sa.Column("pickup_address", sa.Text(), nullable=True),
        sa.Column("pickup_hours", sa.String(250), nullable=True),
        sa.Column("admin_comment", sa.Text(), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        _enum_check("status", SELLER_STATUSES, "ck_b2b_seller_profiles_status"),
        sa.UniqueConstraint("user_id", name="uq_b2b_seller_profiles_user_id"),
        indexes=(("ix_b2b_seller_profiles_status", ("status",), False, None),),
    )

    _create_timestamped(
        "b2b_buyer_addresses",
        _fk_uuid("buyer_profile_id", "b2b_buyer_profiles.id", nullable=False, ondelete="CASCADE"),
        sa.Column("label", sa.String(120), nullable=False),
        sa.Column("address", sa.Text(), nullable=False),
        sa.Column("contact_name", sa.String(200), nullable=True),
        sa.Column("contact_phone", sa.String(32), nullable=True),
        sa.Column("delivery_instructions", sa.Text(), nullable=True),
        sa.Column("is_default", sa.Boolean(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        indexes=(("ix_b2b_buyer_addresses_buyer", ("buyer_profile_id",), False, None),),
    )

    _create_timestamped(
        "b2b_invite_links",
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        _fk_user("created_by_user_id", ondelete="SET NULL"),
        _fk_uuid("plan_id", "b2b_subscription_plans.id", ondelete="SET NULL"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("max_uses", sa.Integer(), nullable=False),
        sa.Column("use_count", sa.Integer(), nullable=False),
        sa.Column("trial_days", sa.Integer(), nullable=False),
        sa.Column("bound_telegram_user_id", sa.BigInteger(), nullable=True),
        _fk_user("activated_by_user_id", ondelete="SET NULL"),
        sa.Column("source", sa.String(120), nullable=True),
        sa.Column("manager_label", sa.String(120), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        _enum_check("status", INVITE_STATUSES, "ck_b2b_invite_links_status"),
        sa.CheckConstraint("max_uses > 0", name="ck_b2b_invite_links_max_uses"),
        sa.CheckConstraint("use_count >= 0 AND use_count <= max_uses", name="ck_b2b_invite_links_uses"),
        sa.CheckConstraint("trial_days >= 0", name="ck_b2b_invite_links_trial"),
        sa.UniqueConstraint("token_hash", name="uq_b2b_invite_links_token_hash"),
        indexes=(("ix_b2b_invite_links_status_expires", ("status", "expires_at"), False, None),),
    )

    _create_timestamped(
        "b2b_subscriptions",
        _fk_uuid("buyer_profile_id", "b2b_buyer_profiles.id", nullable=False, ondelete="RESTRICT"),
        _fk_uuid("plan_id", "b2b_subscription_plans.id", nullable=False, ondelete="RESTRICT"),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("grace_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("canceled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("override_reason", sa.Text(), nullable=True),
        _fk_user("granted_by_user_id", ondelete="SET NULL"),
        _enum_check("status", SUBSCRIPTION_STATUSES, "ck_b2b_subscriptions_status"),
        sa.CheckConstraint("ends_at > starts_at", name="ck_b2b_subscriptions_period"),
        indexes=(
            ("ix_b2b_subscriptions_buyer_status", ("buyer_profile_id", "status"), False, None),
            ("ix_b2b_subscriptions_ends_at", ("ends_at",), False, None),
        ),
    )

    _create_timestamped(
        "b2b_subscription_payments",
        _fk_uuid("buyer_profile_id", "b2b_buyer_profiles.id", nullable=False, ondelete="RESTRICT"),
        _fk_uuid("plan_id", "b2b_subscription_plans.id", nullable=False, ondelete="RESTRICT"),
        _fk_uuid("subscription_id", "b2b_subscriptions.id", ondelete="SET NULL"),
        sa.Column("provider", sa.String(64), nullable=False),
        sa.Column("provider_payment_id", sa.String(200), nullable=True),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("amount_kopecks", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("confirmation_url", sa.Text(), nullable=True),
        sa.Column("provider_payload", JSONB, nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("refunded_at", sa.DateTime(timezone=True), nullable=True),
        _enum_check("status", PAYMENT_STATUSES, "ck_b2b_subscription_payments_status"),
        sa.CheckConstraint("amount_kopecks > 0", name="ck_b2b_subscription_payments_amount"),
        sa.CheckConstraint("char_length(currency) = 3", name="ck_b2b_subscription_payments_currency"),
        sa.UniqueConstraint("provider", "idempotency_key", name="uq_b2b_payments_provider_idempotency"),
        sa.UniqueConstraint("provider", "provider_payment_id", name="uq_b2b_payments_provider_payment"),
        indexes=(
            ("ix_b2b_subscription_payments_buyer", ("buyer_profile_id", "created_at"), False, None),
            ("ix_b2b_subscription_payments_status", ("status",), False, None),
        ),
    )

    _create_timestamped(
        "b2b_offers",
        _fk_uuid("seller_profile_id", "b2b_seller_profiles.id", nullable=False, ondelete="RESTRICT"),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("admin_comment", sa.Text(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        _fk_user("reviewed_by_user_id", ondelete="SET NULL"),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("publication_starts_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        _enum_check("status", OFFER_STATUSES, "ck_b2b_offers_status"),
        sa.CheckConstraint("version > 0", name="ck_b2b_offers_version"),
        sa.CheckConstraint(
            "publication_starts_at IS NULL OR expires_at IS NULL OR expires_at > publication_starts_at",
            name="ck_b2b_offers_publication_window",
        ),
        indexes=(
            ("ix_b2b_offers_seller_status", ("seller_profile_id", "status"), False, None),
            ("ix_b2b_offers_catalog", ("status", "published_at", "expires_at"), False, None),
        ),
    )

    _create_timestamped(
        "b2b_offer_revisions",
        _fk_uuid("offer_id", "b2b_offers.id", nullable=False, ondelete="CASCADE"),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        _fk_uuid("category_id", "b2b_categories.id", nullable=False, ondelete="RESTRICT"),
        sa.Column("original_title", sa.String(300), nullable=False),
        sa.Column("original_description", sa.Text(), nullable=False),
        sa.Column("public_title", sa.String(300), nullable=True),
        sa.Column("public_description", sa.Text(), nullable=True),
        sa.Column("brand", sa.String(200), nullable=True),
        sa.Column("supplier_unit_price_kopecks", sa.BigInteger(), nullable=False),
        sa.Column("markup_type", sa.String(24), nullable=True),
        sa.Column("markup_value", sa.Numeric(18, 4), nullable=True),
        sa.Column("buyer_unit_price_kopecks", sa.BigInteger(), nullable=True),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("sale_unit", sa.String(32), nullable=False),
        sa.Column("package_size", QTY, nullable=False),
        sa.Column("proposed_total_quantity", QTY, nullable=False),
        sa.Column("minimum_order_quantity", QTY, nullable=False),
        sa.Column("quantity_step", QTY, nullable=False),
        sa.Column("production_date", sa.Date(), nullable=True),
        sa.Column("expiration_date", sa.Date(), nullable=True),
        sa.Column("storage_conditions", sa.Text(), nullable=True),
        sa.Column("pickup_address", sa.Text(), nullable=False),
        sa.Column("pickup_hours", sa.String(250), nullable=True),
        sa.Column("supplier_comment", sa.Text(), nullable=True),
        sa.Column("admin_comment", sa.Text(), nullable=True),
        sa.Column("change_summary", sa.Text(), nullable=True),
        _fk_user("created_by_user_id", ondelete="SET NULL"),
        sa.Column("is_published", sa.Boolean(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("offer_id", "revision_number", name="uq_b2b_offer_revisions_number"),
        sa.CheckConstraint("revision_number > 0", name="ck_b2b_offer_revisions_number"),
        sa.CheckConstraint("supplier_unit_price_kopecks >= 0", name="ck_b2b_offer_revisions_supplier_price"),
        sa.CheckConstraint(
            "buyer_unit_price_kopecks IS NULL OR buyer_unit_price_kopecks >= supplier_unit_price_kopecks",
            name="ck_b2b_offer_revisions_buyer_price",
        ),
        sa.CheckConstraint("package_size > 0", name="ck_b2b_offer_revisions_package_size"),
        sa.CheckConstraint("proposed_total_quantity > 0", name="ck_b2b_offer_revisions_total_quantity"),
        sa.CheckConstraint("minimum_order_quantity > 0", name="ck_b2b_offer_revisions_minimum"),
        sa.CheckConstraint("quantity_step > 0", name="ck_b2b_offer_revisions_step"),
        sa.CheckConstraint(
            "minimum_order_quantity <= proposed_total_quantity",
            name="ck_b2b_offer_revisions_minimum_total",
        ),
        sa.CheckConstraint(
            "production_date IS NULL OR expiration_date IS NULL OR expiration_date >= production_date",
            name="ck_b2b_offer_revisions_dates",
        ),
        sa.CheckConstraint("char_length(currency) = 3", name="ck_b2b_offer_revisions_currency"),
        _enum_check("markup_type", MARKUP_TYPES, "ck_b2b_offer_revisions_markup_type"),
        indexes=(("ix_b2b_offer_revisions_offer_published", ("offer_id", "is_published"), False, None),),
    )

    _create_timestamped(
        "b2b_offer_images",
        _fk_uuid("revision_id", "b2b_offer_revisions.id", nullable=False, ondelete="CASCADE"),
        sa.Column("storage_key", sa.String(1024), nullable=False),
        sa.Column("public_url", sa.Text(), nullable=False),
        sa.Column("mime_type", sa.String(100), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("display_order", sa.Integer(), nullable=False),
        sa.UniqueConstraint("revision_id", "display_order", name="uq_b2b_offer_images_order"),
        sa.UniqueConstraint("storage_key", name="uq_b2b_offer_images_storage_key"),
        sa.CheckConstraint("display_order >= 0", name="ck_b2b_offer_images_order"),
        sa.CheckConstraint("size_bytes > 0", name="ck_b2b_offer_images_size"),
        indexes=(("ix_b2b_offer_images_revision", ("revision_id",), False, None),),
    )

    _create_timestamped(
        "b2b_inventory_balances",
        _fk_uuid("offer_id", "b2b_offers.id", nullable=False, ondelete="RESTRICT"),
        sa.Column("total_quantity", QTY, nullable=False),
        sa.Column("reserved_quantity", QTY, nullable=False),
        sa.Column("sold_quantity", QTY, nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.UniqueConstraint("offer_id", name="uq_b2b_inventory_balances_offer_id"),
        sa.CheckConstraint("total_quantity >= 0", name="ck_b2b_inventory_balances_total"),
        sa.CheckConstraint("reserved_quantity >= 0", name="ck_b2b_inventory_balances_reserved"),
        sa.CheckConstraint("sold_quantity >= 0", name="ck_b2b_inventory_balances_sold"),
        sa.CheckConstraint(
            "reserved_quantity + sold_quantity <= total_quantity",
            name="ck_b2b_inventory_balances_available",
        ),
        sa.CheckConstraint("version > 0", name="ck_b2b_inventory_balances_version"),
    )

    _create_timestamped(
        "b2b_carts",
        _fk_uuid("buyer_profile_id", "b2b_buyer_profiles.id", nullable=False, ondelete="CASCADE"),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("checked_out_at", sa.DateTime(timezone=True), nullable=True),
        _enum_check("status", CART_STATUSES, "ck_b2b_carts_status"),
        indexes=(
            ("ix_b2b_carts_buyer_status", ("buyer_profile_id", "status"), False, None),
            (
                "uq_b2b_carts_one_active",
                ("buyer_profile_id",),
                True,
                sa.text("status = 'ACTIVE'"),
            ),
        ),
    )

    _create_timestamped(
        "b2b_cart_items",
        _fk_uuid("cart_id", "b2b_carts.id", nullable=False, ondelete="CASCADE"),
        _fk_uuid("offer_id", "b2b_offers.id", nullable=False, ondelete="RESTRICT"),
        sa.Column("quantity", QTY, nullable=False),
        sa.UniqueConstraint("cart_id", "offer_id", name="uq_b2b_cart_items_offer"),
        sa.CheckConstraint("quantity > 0", name="ck_b2b_cart_items_quantity"),
        indexes=(("ix_b2b_cart_items_cart", ("cart_id",), False, None),),
    )

    _create_timestamped(
        "b2b_orders",
        sa.Column("order_number", sa.String(40), nullable=False),
        _fk_uuid("buyer_profile_id", "b2b_buyer_profiles.id", nullable=False, ondelete="RESTRICT"),
        _fk_uuid("cart_id", "b2b_carts.id", ondelete="SET NULL"),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("payment_method", sa.String(32), nullable=False),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("delivery_address_snapshot", sa.Text(), nullable=False),
        sa.Column("recipient_name", sa.String(200), nullable=False),
        sa.Column("recipient_phone", sa.String(32), nullable=False),
        sa.Column("desired_delivery_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("desired_delivery_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("items_total_kopecks", sa.BigInteger(), nullable=False),
        sa.Column("delivery_fee_kopecks", sa.BigInteger(), nullable=False),
        sa.Column("total_kopecks", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("reserved_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("canceled_at", sa.DateTime(timezone=True), nullable=True),
        _enum_check("status", ORDER_STATUSES, "ck_b2b_orders_status"),
        _enum_check("payment_method", ORDER_PAYMENT_METHODS, "ck_b2b_orders_payment_method"),
        sa.CheckConstraint("items_total_kopecks >= 0", name="ck_b2b_orders_items_total"),
        sa.CheckConstraint("delivery_fee_kopecks >= 0", name="ck_b2b_orders_delivery_fee"),
        sa.CheckConstraint(
            "total_kopecks = items_total_kopecks + delivery_fee_kopecks",
            name="ck_b2b_orders_total",
        ),
        sa.CheckConstraint("char_length(currency) = 3", name="ck_b2b_orders_currency"),
        sa.UniqueConstraint("order_number", name="uq_b2b_orders_order_number"),
        sa.UniqueConstraint("idempotency_key", name="uq_b2b_orders_idempotency_key"),
        indexes=(
            ("ix_b2b_orders_buyer_created", ("buyer_profile_id", "created_at"), False, None),
            ("ix_b2b_orders_status_created", ("status", "created_at"), False, None),
        ),
    )

    _create_timestamped(
        "b2b_order_fulfillment_groups",
        _fk_uuid("order_id", "b2b_orders.id", nullable=False, ondelete="CASCADE"),
        _fk_uuid("seller_profile_id", "b2b_seller_profiles.id", nullable=False, ondelete="RESTRICT"),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("pickup_address_snapshot", sa.Text(), nullable=False),
        sa.Column("pickup_window_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("pickup_window_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("seller_confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ready_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("order_id", "seller_profile_id", name="uq_b2b_fulfillment_order_seller"),
        _enum_check("status", ORDER_STATUSES, "ck_b2b_fulfillment_status"),
        indexes=(("ix_b2b_fulfillment_seller_status", ("seller_profile_id", "status"), False, None),),
    )

    _create_timestamped(
        "b2b_order_items",
        _fk_uuid("order_id", "b2b_orders.id", nullable=False, ondelete="CASCADE"),
        _fk_uuid(
            "fulfillment_group_id",
            "b2b_order_fulfillment_groups.id",
            nullable=False,
            ondelete="CASCADE",
        ),
        _fk_uuid("offer_id", "b2b_offers.id", nullable=False, ondelete="RESTRICT"),
        _fk_uuid("offer_revision_id", "b2b_offer_revisions.id", nullable=False, ondelete="RESTRICT"),
        sa.Column("public_title_snapshot", sa.String(300), nullable=False),
        sa.Column("quantity", QTY, nullable=False),
        sa.Column("sale_unit_snapshot", sa.String(32), nullable=False),
        sa.Column("supplier_unit_price_kopecks", sa.BigInteger(), nullable=False),
        sa.Column("buyer_unit_price_kopecks", sa.BigInteger(), nullable=False),
        sa.Column("supplier_total_kopecks", sa.BigInteger(), nullable=False),
        sa.Column("buyer_total_kopecks", sa.BigInteger(), nullable=False),
        sa.Column("margin_kopecks", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("pickup_address_snapshot", sa.Text(), nullable=False),
        sa.Column("expiration_date_snapshot", sa.Date(), nullable=True),
        sa.CheckConstraint("quantity > 0", name="ck_b2b_order_items_quantity"),
        sa.CheckConstraint(
            "supplier_unit_price_kopecks >= 0",
            name="ck_b2b_order_items_supplier_price",
        ),
        sa.CheckConstraint(
            "buyer_unit_price_kopecks >= supplier_unit_price_kopecks",
            name="ck_b2b_order_items_buyer_price",
        ),
        sa.CheckConstraint("supplier_total_kopecks >= 0", name="ck_b2b_order_items_supplier_total"),
        sa.CheckConstraint(
            "buyer_total_kopecks >= supplier_total_kopecks",
            name="ck_b2b_order_items_buyer_total",
        ),
        sa.CheckConstraint(
            "margin_kopecks = buyer_total_kopecks - supplier_total_kopecks",
            name="ck_b2b_order_items_margin",
        ),
        indexes=(
            ("ix_b2b_order_items_order", ("order_id",), False, None),
            ("ix_b2b_order_items_fulfillment", ("fulfillment_group_id",), False, None),
        ),
    )

    _create_timestamped(
        "b2b_inventory_reservations",
        _fk_uuid(
            "inventory_balance_id",
            "b2b_inventory_balances.id",
            nullable=False,
            ondelete="RESTRICT",
        ),
        _fk_uuid("buyer_profile_id", "b2b_buyer_profiles.id", nullable=False, ondelete="RESTRICT"),
        _fk_uuid("order_id", "b2b_orders.id", ondelete="SET NULL"),
        sa.Column("quantity", QTY, nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("converted_at", sa.DateTime(timezone=True), nullable=True),
        _enum_check("status", RESERVATION_STATUSES, "ck_b2b_inventory_reservations_status"),
        sa.CheckConstraint("quantity > 0", name="ck_b2b_inventory_reservations_quantity"),
        sa.UniqueConstraint("idempotency_key", name="uq_b2b_inventory_reservations_idempotency"),
        indexes=(
            (
                "ix_b2b_inventory_reservations_balance_status",
                ("inventory_balance_id", "status"),
                False,
                None,
            ),
            ("ix_b2b_inventory_reservations_expires", ("status", "expires_at"), False, None),
            ("ix_b2b_inventory_reservations_order", ("order_id",), False, None),
        ),
    )

    _create_timestamped(
        "b2b_inventory_movements",
        _fk_uuid(
            "inventory_balance_id",
            "b2b_inventory_balances.id",
            nullable=False,
            ondelete="RESTRICT",
        ),
        _fk_uuid("reservation_id", "b2b_inventory_reservations.id", ondelete="SET NULL"),
        sa.Column("movement_type", sa.String(24), nullable=False),
        sa.Column("quantity", QTY, nullable=False),
        sa.Column("total_after", QTY, nullable=False),
        sa.Column("reserved_after", QTY, nullable=False),
        sa.Column("sold_after", QTY, nullable=False),
        _fk_user("actor_user_id", ondelete="SET NULL"),
        sa.Column("reason", sa.Text(), nullable=False),
        _enum_check("movement_type", INVENTORY_MOVEMENT_TYPES, "ck_b2b_inventory_movements_type"),
        sa.CheckConstraint("quantity > 0", name="ck_b2b_inventory_movements_quantity"),
        sa.CheckConstraint(
            "total_after >= 0 AND reserved_after >= 0 AND sold_after >= 0",
            name="ck_b2b_inventory_movements_after_nonnegative",
        ),
        sa.CheckConstraint(
            "reserved_after + sold_after <= total_after",
            name="ck_b2b_inventory_movements_after_available",
        ),
        indexes=(
            (
                "ix_b2b_inventory_movements_balance_created",
                ("inventory_balance_id", "created_at"),
                False,
                None,
            ),
        ),
    )

    _create_timestamped(
        "b2b_order_status_history",
        _fk_uuid("order_id", "b2b_orders.id", nullable=False, ondelete="CASCADE"),
        sa.Column("from_status", sa.String(32), nullable=True),
        sa.Column("to_status", sa.String(32), nullable=False),
        _fk_user("actor_user_id", ondelete="SET NULL"),
        sa.Column("actor_type", sa.String(32), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        _enum_check("to_status", ORDER_STATUSES, "ck_b2b_order_status_history_to"),
        indexes=(
            ("ix_b2b_order_status_history_order_created", ("order_id", "created_at"), False, None),
        ),
    )

    _create_timestamped(
        "b2b_deliveries",
        _fk_uuid("order_id", "b2b_orders.id", nullable=False, ondelete="CASCADE"),
        _fk_uuid(
            "fulfillment_group_id",
            "b2b_order_fulfillment_groups.id",
            ondelete="SET NULL",
        ),
        sa.Column("provider", sa.String(64), nullable=False),
        sa.Column("external_delivery_id", sa.String(200), nullable=True),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("pickup_address_snapshot", sa.Text(), nullable=False),
        sa.Column("delivery_address_snapshot", sa.Text(), nullable=False),
        sa.Column("pickup_window_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("pickup_window_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivery_window_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivery_window_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("courier_name", sa.String(200), nullable=True),
        sa.Column("courier_contact", sa.String(100), nullable=True),
        sa.Column("cost_kopecks", sa.BigInteger(), nullable=True),
        sa.Column("internal_notes", sa.Text(), nullable=True),
        sa.Column("picked_up_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        _enum_check("status", DELIVERY_STATUSES, "ck_b2b_deliveries_status"),
        sa.CheckConstraint(
            "cost_kopecks IS NULL OR cost_kopecks >= 0",
            name="ck_b2b_deliveries_cost",
        ),
        indexes=(
            ("ix_b2b_deliveries_order", ("order_id",), False, None),
            ("ix_b2b_deliveries_status", ("status",), False, None),
        ),
    )

    _create_timestamped(
        "b2b_delivery_status_history",
        _fk_uuid("delivery_id", "b2b_deliveries.id", nullable=False, ondelete="CASCADE"),
        sa.Column("from_status", sa.String(24), nullable=True),
        sa.Column("to_status", sa.String(24), nullable=False),
        _fk_user("actor_user_id", ondelete="SET NULL"),
        sa.Column("comment", sa.Text(), nullable=True),
        _enum_check("to_status", DELIVERY_STATUSES, "ck_b2b_delivery_status_history_to"),
        indexes=(
            (
                "ix_b2b_delivery_status_history_delivery_created",
                ("delivery_id", "created_at"),
                False,
                None,
            ),
        ),
    )

    _create_timestamped(
        "b2b_notifications",
        _fk_user("user_id", ondelete="SET NULL"),
        sa.Column("channel", sa.String(32), nullable=False),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("idempotency_key", sa.String(160), nullable=False),
        sa.Column("recipient", sa.String(200), nullable=False),
        sa.Column("deep_link", sa.Text(), nullable=True),
        sa.Column("payload", JSONB, nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("final_error", sa.Text(), nullable=True),
        _enum_check("status", NOTIFICATION_STATUSES, "ck_b2b_notifications_status"),
        sa.CheckConstraint("attempt_count >= 0", name="ck_b2b_notifications_attempt_count"),
        sa.CheckConstraint("max_attempts > 0", name="ck_b2b_notifications_max_attempts"),
        sa.UniqueConstraint("idempotency_key", name="uq_b2b_notifications_idempotency_key"),
        indexes=(
            ("ix_b2b_notifications_dispatch", ("status", "next_attempt_at"), False, None),
            ("ix_b2b_notifications_user_created", ("user_id", "created_at"), False, None),
        ),
    )

    _create_timestamped(
        "b2b_webhook_events",
        sa.Column("provider", sa.String(64), nullable=False),
        sa.Column("external_event_id", sa.String(200), nullable=False),
        sa.Column("payload_hash", sa.String(64), nullable=False),
        sa.Column("payload", JSONB, nullable=True),
        sa.Column("signature_valid", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        _enum_check("status", WEBHOOK_STATUSES, "ck_b2b_webhook_events_status"),
        sa.UniqueConstraint("provider", "external_event_id", name="uq_b2b_webhook_events_provider_event"),
        indexes=(
            ("ix_b2b_webhook_events_status_created", ("status", "created_at"), False, None),
        ),
    )

    _create_timestamped(
        "b2b_audit_logs",
        _fk_user("actor_user_id", ondelete="SET NULL"),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("entity_type", sa.String(100), nullable=False),
        sa.Column("entity_id", sa.String(100), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("before_data", JSONB, nullable=True),
        sa.Column("after_data", JSONB, nullable=True),
        sa.Column("request_id", sa.String(100), nullable=True),
        sa.Column("correlation_id", sa.String(100), nullable=True),
        sa.Column("ip_address", sa.String(64), nullable=True),
        indexes=(
            (
                "ix_b2b_audit_logs_entity_created",
                ("entity_type", "entity_id", "created_at"),
                False,
                None,
            ),
            ("ix_b2b_audit_logs_actor_created", ("actor_user_id", "created_at"), False, None),
            ("ix_b2b_audit_logs_correlation", ("correlation_id",), False, None),
        ),
    )

    _create_timestamped(
        "b2b_system_settings",
        sa.Column("key", sa.String(120), nullable=False),
        sa.Column("value", JSONB, nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_public", sa.Boolean(), nullable=False),
        _fk_user("updated_by_user_id", ondelete="SET NULL"),
        sa.UniqueConstraint("key", name="uq_b2b_system_settings_key"),
    )


def downgrade() -> None:
    # Reverse dependency order; table-owned constraints and indexes are removed
    # atomically with their tables.
    for table_name in (
        "b2b_system_settings",
        "b2b_audit_logs",
        "b2b_webhook_events",
        "b2b_notifications",
        "b2b_delivery_status_history",
        "b2b_deliveries",
        "b2b_order_status_history",
        "b2b_inventory_movements",
        "b2b_inventory_reservations",
        "b2b_order_items",
        "b2b_order_fulfillment_groups",
        "b2b_orders",
        "b2b_cart_items",
        "b2b_carts",
        "b2b_inventory_balances",
        "b2b_offer_images",
        "b2b_offer_revisions",
        "b2b_offers",
        "b2b_subscription_payments",
        "b2b_subscriptions",
        "b2b_invite_links",
        "b2b_buyer_addresses",
        "b2b_seller_profiles",
        "b2b_buyer_profiles",
        "b2b_telegram_accounts",
        "b2b_user_roles",
        "b2b_categories",
        "b2b_subscription_plans",
        "b2b_roles",
    ):
        op.drop_table(table_name)
