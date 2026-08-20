from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


ROLE_CODES = ("BUYER", "SELLER", "ADMIN", "SUPERADMIN", "DISPATCHER", "COURIER")
BUYER_STATUSES = ("INVITED", "REGISTERED", "TRIAL", "ACTIVE", "PAST_DUE", "EXPIRED", "BLOCKED")
SELLER_STATUSES = ("PENDING", "VERIFIED", "SUSPENDED", "BLOCKED")
INVITE_STATUSES = ("ACTIVE", "EXHAUSTED", "EXPIRED", "REVOKED")
SUBSCRIPTION_STATUSES = ("TRIAL", "ACTIVE", "PAST_DUE", "EXPIRED", "CANCELED", "BLOCKED")
PAYMENT_STATUSES = ("PENDING", "PAID", "FAILED", "CANCELED", "REFUNDED")
OFFER_STATUSES = (
    "DRAFT",
    "SUBMITTED",
    "UNDER_REVIEW",
    "CHANGES_REQUESTED",
    "REJECTED",
    "APPROVED",
    "PUBLISHED",
    "PAUSED",
    "SOLD_OUT",
    "EXPIRED",
    "ARCHIVED",
)
MARKUP_TYPES = ("PERCENT", "FIXED", "MANUAL")
RESERVATION_STATUSES = ("ACTIVE", "RELEASED", "CONVERTED", "EXPIRED", "CANCELED")
INVENTORY_MOVEMENT_TYPES = (
    "INITIAL",
    "ADJUSTMENT",
    "RESERVE",
    "RELEASE",
    "SALE",
    "CANCEL",
    "RETURN",
)
CART_STATUSES = ("ACTIVE", "CHECKED_OUT", "ABANDONED")
ORDER_STATUSES = (
    "DRAFT",
    "RESERVED",
    "PENDING_CONFIRMATION",
    "CONFIRMED",
    "SELLER_PREPARING",
    "READY_FOR_PICKUP",
    "COURIER_ASSIGNED",
    "PICKED_UP",
    "IN_DELIVERY",
    "DELIVERED",
    "COMPLETED",
    "CANCELED",
    "REFUNDED",
)
ORDER_PAYMENT_METHODS = ("PAY_ON_DELIVERY", "BANK_TRANSFER", "MANUAL")
DELIVERY_STATUSES = (
    "PENDING",
    "ASSIGNED",
    "PICKED_UP",
    "IN_DELIVERY",
    "DELIVERED",
    "CANCELED",
    "FAILED",
)
NOTIFICATION_STATUSES = ("PENDING", "PROCESSING", "RETRY", "SENT", "FAILED", "CANCELED")
WEBHOOK_STATUSES = ("RECEIVED", "PROCESSED", "IGNORED", "FAILED")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _enum_check(column: str, values: tuple[str, ...], name: str) -> CheckConstraint:
    allowed = ", ".join(f"'{value}'" for value in values)
    return CheckConstraint(f"{column} IN ({allowed})", name=name)


class UUIDPrimaryKeyMixin:
    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
        server_default=func.now(),
    )


class B2BRole(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "b2b_roles"
    __table_args__ = (
        _enum_check("code", ROLE_CODES, "ck_b2b_roles_code"),
    )

    code: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)


class B2BUserRole(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "b2b_user_roles"
    __table_args__ = (
        UniqueConstraint("user_id", "role_id", name="uq_b2b_user_roles_user_role"),
        Index("ix_b2b_user_roles_role_id", "role_id"),
    )

    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("b2b_roles.id", ondelete="CASCADE"),
        nullable=False,
    )
    granted_by_user_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )


class TelegramAccount(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "b2b_telegram_accounts"
    __table_args__ = (
        UniqueConstraint(
            "telegram_user_id",
            "bot_scope",
            name="uq_b2b_telegram_accounts_tg_scope",
        ),
        UniqueConstraint("user_id", "bot_scope", name="uq_b2b_telegram_accounts_user_scope"),
        Index("ix_b2b_telegram_accounts_user_id", "user_id"),
    )

    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    bot_scope: Mapped[str] = mapped_column(String(32), nullable=False)
    username: Mapped[str | None] = mapped_column(String(200), nullable=True)
    first_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    language_code: Mapped[str | None] = mapped_column(String(16), nullable=True)
    last_authenticated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class BuyerProfile(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "b2b_buyer_profiles"
    __table_args__ = (
        _enum_check("status", BUYER_STATUSES, "ck_b2b_buyer_profiles_status"),
        Index("ix_b2b_buyer_profiles_status", "status"),
    )

    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="REGISTERED")
    company_type: Mapped[str | None] = mapped_column(String(32))
    company_name: Mapped[str | None] = mapped_column(String(250))
    inn: Mapped[str | None] = mapped_column(String(20))
    contact_name: Mapped[str | None] = mapped_column(String(200))
    phone: Mapped[str | None] = mapped_column(String(32))
    admin_comment: Mapped[str | None] = mapped_column(Text)
    blocked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SellerProfile(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "b2b_seller_profiles"
    __table_args__ = (
        _enum_check("status", SELLER_STATUSES, "ck_b2b_seller_profiles_status"),
        Index("ix_b2b_seller_profiles_status", "status"),
    )

    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="PENDING")
    company_type: Mapped[str | None] = mapped_column(String(32))
    company_name: Mapped[str] = mapped_column(String(250), nullable=False)
    inn: Mapped[str | None] = mapped_column(String(20))
    legal_details: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    contact_name: Mapped[str | None] = mapped_column(String(200))
    phone: Mapped[str | None] = mapped_column(String(32))
    pickup_address: Mapped[str | None] = mapped_column(Text)
    pickup_hours: Mapped[str | None] = mapped_column(String(250))
    admin_comment: Mapped[str | None] = mapped_column(Text)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class BuyerAddress(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "b2b_buyer_addresses"
    __table_args__ = (Index("ix_b2b_buyer_addresses_buyer", "buyer_profile_id"),)

    buyer_profile_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("b2b_buyer_profiles.id", ondelete="CASCADE"),
        nullable=False,
    )
    label: Mapped[str] = mapped_column(String(120), nullable=False)
    address: Mapped[str] = mapped_column(Text, nullable=False)
    contact_name: Mapped[str | None] = mapped_column(String(200))
    contact_phone: Mapped[str | None] = mapped_column(String(32))
    delivery_instructions: Mapped[str | None] = mapped_column(Text)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class SubscriptionPlan(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "b2b_subscription_plans"
    __table_args__ = (
        CheckConstraint("price_kopecks >= 0", name="ck_b2b_subscription_plans_price"),
        CheckConstraint("duration_days > 0", name="ck_b2b_subscription_plans_duration"),
        CheckConstraint("trial_days >= 0", name="ck_b2b_subscription_plans_trial"),
        CheckConstraint("char_length(currency) = 3", name="ck_b2b_subscription_plans_currency"),
    )

    code: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    price_kopecks: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="RUB")
    duration_days: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    trial_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSONB)


class InviteLink(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "b2b_invite_links"
    __table_args__ = (
        _enum_check("status", INVITE_STATUSES, "ck_b2b_invite_links_status"),
        CheckConstraint("max_uses > 0", name="ck_b2b_invite_links_max_uses"),
        CheckConstraint("use_count >= 0 AND use_count <= max_uses", name="ck_b2b_invite_links_uses"),
        CheckConstraint("trial_days >= 0", name="ck_b2b_invite_links_trial"),
        Index("ix_b2b_invite_links_status_expires", "status", "expires_at"),
    )

    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="ACTIVE")
    created_by_user_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="SET NULL"),
    )
    plan_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("b2b_subscription_plans.id", ondelete="SET NULL"),
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    max_uses: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    use_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    trial_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    bound_telegram_user_id: Mapped[int | None] = mapped_column(BigInteger)
    activated_by_user_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="SET NULL"),
    )
    source: Mapped[str | None] = mapped_column(String(120))
    manager_label: Mapped[str | None] = mapped_column(String(120))
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Subscription(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "b2b_subscriptions"
    __table_args__ = (
        _enum_check("status", SUBSCRIPTION_STATUSES, "ck_b2b_subscriptions_status"),
        CheckConstraint("ends_at > starts_at", name="ck_b2b_subscriptions_period"),
        Index("ix_b2b_subscriptions_buyer_status", "buyer_profile_id", "status"),
        Index("ix_b2b_subscriptions_ends_at", "ends_at"),
    )

    buyer_profile_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("b2b_buyer_profiles.id", ondelete="RESTRICT"),
        nullable=False,
    )
    plan_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("b2b_subscription_plans.id", ondelete="RESTRICT"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    grace_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    canceled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="PAYMENT")
    override_reason: Mapped[str | None] = mapped_column(Text)
    granted_by_user_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="SET NULL"),
    )


class SubscriptionPayment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "b2b_subscription_payments"
    __table_args__ = (
        _enum_check("status", PAYMENT_STATUSES, "ck_b2b_subscription_payments_status"),
        CheckConstraint("amount_kopecks > 0", name="ck_b2b_subscription_payments_amount"),
        CheckConstraint("char_length(currency) = 3", name="ck_b2b_subscription_payments_currency"),
        UniqueConstraint("provider", "idempotency_key", name="uq_b2b_payments_provider_idempotency"),
        UniqueConstraint("provider", "provider_payment_id", name="uq_b2b_payments_provider_payment"),
        Index("ix_b2b_subscription_payments_buyer", "buyer_profile_id", "created_at"),
        Index("ix_b2b_subscription_payments_status", "status"),
    )

    buyer_profile_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("b2b_buyer_profiles.id", ondelete="RESTRICT"),
        nullable=False,
    )
    plan_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("b2b_subscription_plans.id", ondelete="RESTRICT"),
        nullable=False,
    )
    subscription_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("b2b_subscriptions.id", ondelete="SET NULL"),
    )
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    provider_payment_id: Mapped[str | None] = mapped_column(String(200))
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="PENDING")
    amount_kopecks: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="RUB")
    confirmation_url: Mapped[str | None] = mapped_column(Text)
    provider_payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    refunded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class B2BCategory(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "b2b_categories"
    __table_args__ = (
        Index("ix_b2b_categories_parent", "parent_id"),
        Index("ix_b2b_categories_active_sort", "is_active", "sort_order"),
    )

    parent_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("b2b_categories.id", ondelete="RESTRICT"),
    )
    slug: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class Offer(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "b2b_offers"
    __table_args__ = (
        _enum_check("status", OFFER_STATUSES, "ck_b2b_offers_status"),
        CheckConstraint("version > 0", name="ck_b2b_offers_version"),
        CheckConstraint(
            "publication_starts_at IS NULL OR expires_at IS NULL OR expires_at > publication_starts_at",
            name="ck_b2b_offers_publication_window",
        ),
        Index("ix_b2b_offers_seller_status", "seller_profile_id", "status"),
        Index("ix_b2b_offers_catalog", "status", "published_at", "expires_at"),
    )

    seller_profile_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("b2b_seller_profiles.id", ondelete="RESTRICT"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="DRAFT")
    rejection_reason: Mapped[str | None] = mapped_column(Text)
    admin_comment: Mapped[str | None] = mapped_column(Text)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reviewed_by_user_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="SET NULL"),
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    publication_starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class OfferRevision(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "b2b_offer_revisions"
    __table_args__ = (
        UniqueConstraint("offer_id", "revision_number", name="uq_b2b_offer_revisions_number"),
        CheckConstraint("revision_number > 0", name="ck_b2b_offer_revisions_number"),
        CheckConstraint("supplier_unit_price_kopecks >= 0", name="ck_b2b_offer_revisions_supplier_price"),
        CheckConstraint(
            "buyer_unit_price_kopecks IS NULL OR buyer_unit_price_kopecks >= supplier_unit_price_kopecks",
            name="ck_b2b_offer_revisions_buyer_price",
        ),
        CheckConstraint("package_size > 0", name="ck_b2b_offer_revisions_package_size"),
        CheckConstraint("proposed_total_quantity > 0", name="ck_b2b_offer_revisions_total_quantity"),
        CheckConstraint("minimum_order_quantity > 0", name="ck_b2b_offer_revisions_minimum"),
        CheckConstraint("quantity_step > 0", name="ck_b2b_offer_revisions_step"),
        CheckConstraint(
            "minimum_order_quantity <= proposed_total_quantity",
            name="ck_b2b_offer_revisions_minimum_total",
        ),
        CheckConstraint(
            "production_date IS NULL OR expiration_date IS NULL OR expiration_date >= production_date",
            name="ck_b2b_offer_revisions_dates",
        ),
        CheckConstraint("char_length(currency) = 3", name="ck_b2b_offer_revisions_currency"),
        _enum_check("markup_type", MARKUP_TYPES, "ck_b2b_offer_revisions_markup_type"),
        Index("ix_b2b_offer_revisions_offer_published", "offer_id", "is_published"),
    )

    offer_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("b2b_offers.id", ondelete="CASCADE"),
        nullable=False,
    )
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False)
    category_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("b2b_categories.id", ondelete="RESTRICT"),
        nullable=False,
    )
    original_title: Mapped[str] = mapped_column(String(300), nullable=False)
    original_description: Mapped[str] = mapped_column(Text, nullable=False)
    public_title: Mapped[str | None] = mapped_column(String(300))
    public_description: Mapped[str | None] = mapped_column(Text)
    brand: Mapped[str | None] = mapped_column(String(200))
    supplier_unit_price_kopecks: Mapped[int] = mapped_column(BigInteger, nullable=False)
    markup_type: Mapped[str | None] = mapped_column(String(24))
    markup_value: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    buyer_unit_price_kopecks: Mapped[int | None] = mapped_column(BigInteger)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="RUB")
    sale_unit: Mapped[str] = mapped_column(String(32), nullable=False)
    package_size: Mapped[Decimal] = mapped_column(Numeric(18, 3), nullable=False)
    proposed_total_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 3), nullable=False)
    minimum_order_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 3), nullable=False)
    quantity_step: Mapped[Decimal] = mapped_column(Numeric(18, 3), nullable=False)
    production_date: Mapped[date | None] = mapped_column(Date)
    expiration_date: Mapped[date | None] = mapped_column(Date)
    storage_conditions: Mapped[str | None] = mapped_column(Text)
    pickup_address: Mapped[str] = mapped_column(Text, nullable=False)
    pickup_hours: Mapped[str | None] = mapped_column(String(250))
    supplier_comment: Mapped[str | None] = mapped_column(Text)
    admin_comment: Mapped[str | None] = mapped_column(Text)
    change_summary: Mapped[str | None] = mapped_column(Text)
    created_by_user_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="SET NULL"),
    )
    is_published: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class OfferImage(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "b2b_offer_images"
    __table_args__ = (
        UniqueConstraint("revision_id", "display_order", name="uq_b2b_offer_images_order"),
        CheckConstraint("display_order >= 0", name="ck_b2b_offer_images_order"),
        CheckConstraint("size_bytes > 0", name="ck_b2b_offer_images_size"),
        Index("ix_b2b_offer_images_revision", "revision_id"),
    )

    revision_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("b2b_offer_revisions.id", ondelete="CASCADE"),
        nullable=False,
    )
    storage_key: Mapped[str] = mapped_column(String(1024), nullable=False, unique=True)
    public_url: Mapped[str] = mapped_column(Text, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class InventoryBalance(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "b2b_inventory_balances"
    __table_args__ = (
        CheckConstraint("total_quantity >= 0", name="ck_b2b_inventory_balances_total"),
        CheckConstraint("reserved_quantity >= 0", name="ck_b2b_inventory_balances_reserved"),
        CheckConstraint("sold_quantity >= 0", name="ck_b2b_inventory_balances_sold"),
        CheckConstraint(
            "reserved_quantity + sold_quantity <= total_quantity",
            name="ck_b2b_inventory_balances_available",
        ),
        CheckConstraint("version > 0", name="ck_b2b_inventory_balances_version"),
    )

    offer_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("b2b_offers.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
    )
    total_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 3), nullable=False)
    reserved_quantity: Mapped[Decimal] = mapped_column(
        Numeric(18, 3), nullable=False, default=Decimal("0")
    )
    sold_quantity: Mapped[Decimal] = mapped_column(
        Numeric(18, 3), nullable=False, default=Decimal("0")
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    @property
    def available_quantity(self) -> Decimal:
        return self.total_quantity - self.reserved_quantity - self.sold_quantity


class Cart(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "b2b_carts"
    __table_args__ = (
        _enum_check("status", CART_STATUSES, "ck_b2b_carts_status"),
        Index("ix_b2b_carts_buyer_status", "buyer_profile_id", "status"),
        Index(
            "uq_b2b_carts_one_active",
            "buyer_profile_id",
            unique=True,
            postgresql_where=text("status = 'ACTIVE'"),
        ),
    )

    buyer_profile_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("b2b_buyer_profiles.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="ACTIVE")
    checked_out_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CartItem(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "b2b_cart_items"
    __table_args__ = (
        UniqueConstraint("cart_id", "offer_id", name="uq_b2b_cart_items_offer"),
        CheckConstraint("quantity > 0", name="ck_b2b_cart_items_quantity"),
        Index("ix_b2b_cart_items_cart", "cart_id"),
    )

    cart_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("b2b_carts.id", ondelete="CASCADE"),
        nullable=False,
    )
    offer_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("b2b_offers.id", ondelete="RESTRICT"),
        nullable=False,
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 3), nullable=False)


class B2BOrder(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "b2b_orders"
    __table_args__ = (
        _enum_check("status", ORDER_STATUSES, "ck_b2b_orders_status"),
        _enum_check("payment_method", ORDER_PAYMENT_METHODS, "ck_b2b_orders_payment_method"),
        CheckConstraint("items_total_kopecks >= 0", name="ck_b2b_orders_items_total"),
        CheckConstraint("delivery_fee_kopecks >= 0", name="ck_b2b_orders_delivery_fee"),
        CheckConstraint("total_kopecks = items_total_kopecks + delivery_fee_kopecks", name="ck_b2b_orders_total"),
        CheckConstraint("char_length(currency) = 3", name="ck_b2b_orders_currency"),
        Index("ix_b2b_orders_buyer_created", "buyer_profile_id", "created_at"),
        Index("ix_b2b_orders_status_created", "status", "created_at"),
    )

    order_number: Mapped[str] = mapped_column(String(40), nullable=False, unique=True)
    buyer_profile_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("b2b_buyer_profiles.id", ondelete="RESTRICT"),
        nullable=False,
    )
    cart_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("b2b_carts.id", ondelete="SET NULL"),
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="DRAFT")
    payment_method: Mapped[str] = mapped_column(String(32), nullable=False, default="MANUAL")
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    delivery_address_snapshot: Mapped[str] = mapped_column(Text, nullable=False)
    recipient_name: Mapped[str] = mapped_column(String(200), nullable=False)
    recipient_phone: Mapped[str] = mapped_column(String(32), nullable=False)
    desired_delivery_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    desired_delivery_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    comment: Mapped[str | None] = mapped_column(Text)
    items_total_kopecks: Mapped[int] = mapped_column(BigInteger, nullable=False)
    delivery_fee_kopecks: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    total_kopecks: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="RUB")
    reserved_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    canceled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class OrderFulfillmentGroup(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "b2b_order_fulfillment_groups"
    __table_args__ = (
        UniqueConstraint("order_id", "seller_profile_id", name="uq_b2b_fulfillment_order_seller"),
        _enum_check("status", ORDER_STATUSES, "ck_b2b_fulfillment_status"),
        Index("ix_b2b_fulfillment_seller_status", "seller_profile_id", "status"),
    )

    order_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("b2b_orders.id", ondelete="CASCADE"),
        nullable=False,
    )
    seller_profile_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("b2b_seller_profiles.id", ondelete="RESTRICT"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="PENDING_CONFIRMATION")
    pickup_address_snapshot: Mapped[str] = mapped_column(Text, nullable=False)
    pickup_window_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    pickup_window_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    seller_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ready_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class B2BOrderItem(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "b2b_order_items"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_b2b_order_items_quantity"),
        CheckConstraint("supplier_unit_price_kopecks >= 0", name="ck_b2b_order_items_supplier_price"),
        CheckConstraint("buyer_unit_price_kopecks >= supplier_unit_price_kopecks", name="ck_b2b_order_items_buyer_price"),
        CheckConstraint("supplier_total_kopecks >= 0", name="ck_b2b_order_items_supplier_total"),
        CheckConstraint("buyer_total_kopecks >= supplier_total_kopecks", name="ck_b2b_order_items_buyer_total"),
        CheckConstraint("margin_kopecks = buyer_total_kopecks - supplier_total_kopecks", name="ck_b2b_order_items_margin"),
        Index("ix_b2b_order_items_order", "order_id"),
        Index("ix_b2b_order_items_fulfillment", "fulfillment_group_id"),
    )

    order_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("b2b_orders.id", ondelete="CASCADE"),
        nullable=False,
    )
    fulfillment_group_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("b2b_order_fulfillment_groups.id", ondelete="CASCADE"),
        nullable=False,
    )
    offer_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("b2b_offers.id", ondelete="RESTRICT"),
        nullable=False,
    )
    offer_revision_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("b2b_offer_revisions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    public_title_snapshot: Mapped[str] = mapped_column(String(300), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 3), nullable=False)
    sale_unit_snapshot: Mapped[str] = mapped_column(String(32), nullable=False)
    supplier_unit_price_kopecks: Mapped[int] = mapped_column(BigInteger, nullable=False)
    buyer_unit_price_kopecks: Mapped[int] = mapped_column(BigInteger, nullable=False)
    supplier_total_kopecks: Mapped[int] = mapped_column(BigInteger, nullable=False)
    buyer_total_kopecks: Mapped[int] = mapped_column(BigInteger, nullable=False)
    margin_kopecks: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="RUB")
    pickup_address_snapshot: Mapped[str] = mapped_column(Text, nullable=False)
    expiration_date_snapshot: Mapped[date | None] = mapped_column(Date)


class InventoryReservation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "b2b_inventory_reservations"
    __table_args__ = (
        _enum_check("status", RESERVATION_STATUSES, "ck_b2b_inventory_reservations_status"),
        CheckConstraint("quantity > 0", name="ck_b2b_inventory_reservations_quantity"),
        UniqueConstraint("idempotency_key", name="uq_b2b_inventory_reservations_idempotency"),
        Index("ix_b2b_inventory_reservations_balance_status", "inventory_balance_id", "status"),
        Index("ix_b2b_inventory_reservations_expires", "status", "expires_at"),
        Index("ix_b2b_inventory_reservations_order", "order_id"),
    )

    inventory_balance_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("b2b_inventory_balances.id", ondelete="RESTRICT"),
        nullable=False,
    )
    buyer_profile_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("b2b_buyer_profiles.id", ondelete="RESTRICT"),
        nullable=False,
    )
    order_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("b2b_orders.id", ondelete="SET NULL"),
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 3), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="ACTIVE")
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    converted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class InventoryMovement(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "b2b_inventory_movements"
    __table_args__ = (
        _enum_check("movement_type", INVENTORY_MOVEMENT_TYPES, "ck_b2b_inventory_movements_type"),
        CheckConstraint("quantity > 0", name="ck_b2b_inventory_movements_quantity"),
        CheckConstraint("total_after >= 0 AND reserved_after >= 0 AND sold_after >= 0", name="ck_b2b_inventory_movements_after_nonnegative"),
        CheckConstraint("reserved_after + sold_after <= total_after", name="ck_b2b_inventory_movements_after_available"),
        Index("ix_b2b_inventory_movements_balance_created", "inventory_balance_id", "created_at"),
    )

    inventory_balance_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("b2b_inventory_balances.id", ondelete="RESTRICT"),
        nullable=False,
    )
    reservation_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("b2b_inventory_reservations.id", ondelete="SET NULL"),
    )
    movement_type: Mapped[str] = mapped_column(String(24), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 3), nullable=False)
    total_after: Mapped[Decimal] = mapped_column(Numeric(18, 3), nullable=False)
    reserved_after: Mapped[Decimal] = mapped_column(Numeric(18, 3), nullable=False)
    sold_after: Mapped[Decimal] = mapped_column(Numeric(18, 3), nullable=False)
    actor_user_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="SET NULL"),
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)


class B2BOrderStatusHistory(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "b2b_order_status_history"
    __table_args__ = (
        _enum_check("to_status", ORDER_STATUSES, "ck_b2b_order_status_history_to"),
        Index("ix_b2b_order_status_history_order_created", "order_id", "created_at"),
    )

    order_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("b2b_orders.id", ondelete="CASCADE"),
        nullable=False,
    )
    from_status: Mapped[str | None] = mapped_column(String(32))
    to_status: Mapped[str] = mapped_column(String(32), nullable=False)
    actor_user_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="SET NULL"),
    )
    actor_type: Mapped[str] = mapped_column(String(32), nullable=False, default="SYSTEM")
    comment: Mapped[str | None] = mapped_column(Text)
class Delivery(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "b2b_deliveries"
    __table_args__ = (
        _enum_check("status", DELIVERY_STATUSES, "ck_b2b_deliveries_status"),
        CheckConstraint("cost_kopecks IS NULL OR cost_kopecks >= 0", name="ck_b2b_deliveries_cost"),
        Index("ix_b2b_deliveries_order", "order_id"),
        Index("ix_b2b_deliveries_status", "status"),
    )

    order_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("b2b_orders.id", ondelete="CASCADE"),
        nullable=False,
    )
    fulfillment_group_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("b2b_order_fulfillment_groups.id", ondelete="SET NULL"),
    )
    provider: Mapped[str] = mapped_column(String(64), nullable=False, default="MANUAL")
    external_delivery_id: Mapped[str | None] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="PENDING")
    pickup_address_snapshot: Mapped[str] = mapped_column(Text, nullable=False)
    delivery_address_snapshot: Mapped[str] = mapped_column(Text, nullable=False)
    pickup_window_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    pickup_window_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    delivery_window_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    delivery_window_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    courier_name: Mapped[str | None] = mapped_column(String(200))
    courier_contact: Mapped[str | None] = mapped_column(String(100))
    cost_kopecks: Mapped[int | None] = mapped_column(BigInteger)
    internal_notes: Mapped[str | None] = mapped_column(Text)
    picked_up_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class DeliveryStatusHistory(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "b2b_delivery_status_history"
    __table_args__ = (
        _enum_check("to_status", DELIVERY_STATUSES, "ck_b2b_delivery_status_history_to"),
        Index("ix_b2b_delivery_status_history_delivery_created", "delivery_id", "created_at"),
    )

    delivery_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("b2b_deliveries.id", ondelete="CASCADE"),
        nullable=False,
    )
    from_status: Mapped[str | None] = mapped_column(String(24))
    to_status: Mapped[str] = mapped_column(String(24), nullable=False)
    actor_user_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="SET NULL"),
    )
    comment: Mapped[str | None] = mapped_column(Text)
class Notification(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "b2b_notifications"
    __table_args__ = (
        _enum_check("status", NOTIFICATION_STATUSES, "ck_b2b_notifications_status"),
        CheckConstraint("attempt_count >= 0", name="ck_b2b_notifications_attempt_count"),
        CheckConstraint("max_attempts > 0", name="ck_b2b_notifications_max_attempts"),
        Index("ix_b2b_notifications_dispatch", "status", "next_attempt_at"),
        Index("ix_b2b_notifications_user_created", "user_id", "created_at"),
    )

    user_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="SET NULL"),
    )
    channel: Mapped[str] = mapped_column(String(32), nullable=False, default="TELEGRAM")
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(160), nullable=False, unique=True)
    recipient: Mapped[str] = mapped_column(String(200), nullable=False)
    deep_link: Mapped[str | None] = mapped_column(Text)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="PENDING")
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    final_error: Mapped[str | None] = mapped_column(Text)


class WebhookEvent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "b2b_webhook_events"
    __table_args__ = (
        _enum_check("status", WEBHOOK_STATUSES, "ck_b2b_webhook_events_status"),
        UniqueConstraint("provider", "external_event_id", name="uq_b2b_webhook_events_provider_event"),
        Index("ix_b2b_webhook_events_status_created", "status", "created_at"),
    )

    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    external_event_id: Mapped[str] = mapped_column(String(200), nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    signature_valid: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="RECEIVED")
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error: Mapped[str | None] = mapped_column(Text)


class AuditLog(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "b2b_audit_logs"
    __table_args__ = (
        Index("ix_b2b_audit_logs_entity_created", "entity_type", "entity_id", "created_at"),
        Index("ix_b2b_audit_logs_actor_created", "actor_user_id", "created_at"),
        Index("ix_b2b_audit_logs_correlation", "correlation_id"),
    )

    actor_user_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="SET NULL"),
    )
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(100), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    before_data: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    after_data: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    request_id: Mapped[str | None] = mapped_column(String(100))
    correlation_id: Mapped[str | None] = mapped_column(String(100))
    ip_address: Mapped[str | None] = mapped_column(String(64))
class SystemSetting(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "b2b_system_settings"

    key: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    value: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    is_public: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    updated_by_user_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="SET NULL"),
    )
