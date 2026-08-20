from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


RoleCode = Literal["BUYER", "SELLER", "ADMIN", "SUPERADMIN", "DISPATCHER", "COURIER"]
BuyerStatus = Literal[
    "INVITED", "REGISTERED", "TRIAL", "ACTIVE", "PAST_DUE", "EXPIRED", "BLOCKED"
]
SellerStatus = Literal["PENDING", "VERIFIED", "SUSPENDED", "BLOCKED"]
OfferStatus = Literal[
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
]
OrderStatus = Literal[
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
]
PaymentStatus = Literal["PENDING", "PAID", "FAILED", "CANCELED", "REFUNDED"]
DeliveryStatus = Literal[
    "PENDING", "ASSIGNED", "PICKED_UP", "IN_DELIVERY", "DELIVERED", "CANCELED", "FAILED"
]
MarkupType = Literal["PERCENT", "FIXED", "MANUAL"]
MoneyKopecks = Annotated[int, Field(ge=0)]
PositiveMoneyKopecks = Annotated[int, Field(gt=0)]
Quantity = Annotated[Decimal, Field(gt=0, max_digits=18, decimal_places=3)]
NonNegativeQuantity = Annotated[Decimal, Field(ge=0, max_digits=18, decimal_places=3)]


def _to_camel(name: str) -> str:
    head, *tail = name.split("_")
    return head + "".join(part.capitalize() for part in tail)


class B2BSchema(BaseModel):
    """Strict API base; accepts ORM snake_case and emits the public camelCase contract."""

    model_config = ConfigDict(
        alias_generator=_to_camel,
        populate_by_name=True,
        from_attributes=True,
        extra="forbid",
        str_strip_whitespace=True,
    )

    @field_validator("currency", mode="before", check_fields=False)
    @classmethod
    def normalize_currency(cls, value: Any) -> Any:
        return value.upper() if isinstance(value, str) else value


class TimestampedResponse(B2BSchema):
    id: UUID
    created_at: datetime
    updated_at: datetime


class TelegramAuthRequest(B2BSchema):
    init_data_raw: Annotated[str, Field(min_length=1, max_length=16_384)]
    role: Literal["BUYER", "SELLER", "ADMIN", "SUPERADMIN"]


class AuthUserResponse(B2BSchema):
    id: int
    telegram_id: int
    username: str | None = None
    display_name: str
    roles: list[RoleCode]


class AuthSessionResponse(B2BSchema):
    access_token: str
    access_token_expires_at: datetime
    user: AuthUserResponse


class BuyerProfilePatch(B2BSchema):
    company_type: Annotated[str | None, Field(max_length=32)] = None
    company_name: Annotated[str | None, Field(max_length=250)] = None
    inn: Annotated[str | None, Field(pattern=r"^\d{10}(\d{2})?$")] = None
    contact_name: Annotated[str | None, Field(max_length=200)] = None
    phone: Annotated[str | None, Field(max_length=32)] = None


class BuyerProfileResponse(TimestampedResponse):
    user_id: int
    status: BuyerStatus
    company_type: str | None = None
    company_name: str | None = None
    inn: str | None = None
    contact_name: str | None = None
    phone: str | None = None


class SellerProfilePatch(B2BSchema):
    company_type: Annotated[str | None, Field(max_length=32)] = None
    company_name: Annotated[str | None, Field(min_length=1, max_length=250)] = None
    inn: Annotated[str | None, Field(pattern=r"^\d{10}(\d{2})?$")] = None
    legal_details: dict[str, Any] | None = None
    contact_name: Annotated[str | None, Field(max_length=200)] = None
    phone: Annotated[str | None, Field(max_length=32)] = None
    pickup_address: Annotated[str | None, Field(max_length=2_000)] = None
    pickup_hours: Annotated[str | None, Field(max_length=250)] = None


class SellerProfileResponse(TimestampedResponse):
    user_id: int
    status: SellerStatus
    company_type: str | None = None
    company_name: str
    inn: str | None = None
    legal_details: dict[str, Any] | None = None
    contact_name: str | None = None
    phone: str | None = None
    pickup_address: str | None = None
    pickup_hours: str | None = None
    verified_at: datetime | None = None


class BuyerAddressInput(B2BSchema):
    label: Annotated[str, Field(min_length=1, max_length=120)]
    address: Annotated[str, Field(min_length=1, max_length=2_000)]
    contact_name: Annotated[str | None, Field(max_length=200)] = None
    contact_phone: Annotated[str | None, Field(max_length=32)] = None
    delivery_instructions: Annotated[str | None, Field(max_length=2_000)] = None
    is_default: bool = False
    is_active: bool = True


class BuyerAddressResponse(BuyerAddressInput, TimestampedResponse):
    buyer_profile_id: UUID


class InviteCreateRequest(B2BSchema):
    plan_id: UUID | None = None
    expires_at: datetime
    max_uses: Annotated[int, Field(gt=0, le=100_000)] = 1
    trial_days: Annotated[int, Field(ge=0, le=365)] = 0
    bound_telegram_user_id: int | None = None
    source: Annotated[str | None, Field(max_length=120)] = None
    manager_label: Annotated[str | None, Field(max_length=120)] = None


class InviteCreateResponse(TimestampedResponse):
    token: str
    status: Literal["ACTIVE", "EXHAUSTED", "EXPIRED", "REVOKED"]
    expires_at: datetime
    max_uses: int
    use_count: int
    trial_days: int


class InviteActivateRequest(B2BSchema):
    token: Annotated[str, Field(min_length=24, max_length=512)]


class SubscriptionPlanResponse(TimestampedResponse):
    code: str
    name: str
    description: str | None = None
    price_kopecks: MoneyKopecks
    currency: Annotated[str, Field(min_length=3, max_length=3)]
    duration_days: int
    trial_days: int
    is_active: bool


class SubscriptionResponse(TimestampedResponse):
    buyer_profile_id: UUID
    plan_id: UUID
    status: Literal["TRIAL", "ACTIVE", "PAST_DUE", "EXPIRED", "CANCELED", "BLOCKED"]
    starts_at: datetime
    ends_at: datetime
    grace_until: datetime | None = None
    canceled_at: datetime | None = None
    source: str


class SubscriptionPaymentCreateRequest(B2BSchema):
    plan_id: UUID
    idempotency_key: Annotated[str, Field(min_length=8, max_length=128)]
    return_url: Annotated[str | None, Field(max_length=2_000)] = None


class SubscriptionPaymentResponse(TimestampedResponse):
    plan_id: UUID
    subscription_id: UUID | None = None
    provider: str
    provider_payment_id: str | None = None
    status: PaymentStatus
    amount_kopecks: PositiveMoneyKopecks
    currency: str
    confirmation_url: str | None = None
    paid_at: datetime | None = None


class CategoryResponse(TimestampedResponse):
    parent_id: UUID | None = None
    slug: str
    name: str
    sort_order: int
    is_active: bool


class OfferImageInput(B2BSchema):
    storage_key: Annotated[str, Field(min_length=1, max_length=1_024)]
    public_url: Annotated[str, Field(min_length=1, max_length=4_096)]
    mime_type: Annotated[str, Field(pattern=r"^image/[a-zA-Z0-9.+-]+$", max_length=100)]
    size_bytes: Annotated[int, Field(gt=0)]
    width: Annotated[int | None, Field(gt=0)] = None
    height: Annotated[int | None, Field(gt=0)] = None
    display_order: Annotated[int, Field(ge=0)] = 0


class OfferImageResponse(OfferImageInput, TimestampedResponse):
    revision_id: UUID


class SellerOfferRevisionInput(B2BSchema):
    category_id: UUID
    original_title: Annotated[str, Field(min_length=1, max_length=300)]
    original_description: Annotated[str, Field(min_length=1, max_length=20_000)]
    brand: Annotated[str | None, Field(max_length=200)] = None
    supplier_unit_price_kopecks: MoneyKopecks
    currency: Annotated[str, Field(pattern=r"^[A-Z]{3}$")] = "RUB"
    sale_unit: Annotated[str, Field(min_length=1, max_length=32)]
    package_size: Quantity
    proposed_total_quantity: Quantity
    minimum_order_quantity: Quantity
    quantity_step: Quantity
    production_date: date | None = None
    expiration_date: date | None = None
    storage_conditions: Annotated[str | None, Field(max_length=5_000)] = None
    pickup_address: Annotated[str, Field(min_length=1, max_length=2_000)]
    pickup_hours: Annotated[str | None, Field(max_length=250)] = None
    supplier_comment: Annotated[str | None, Field(max_length=5_000)] = None
    images: list[OfferImageInput] = Field(default_factory=list, max_length=10)

    @model_validator(mode="after")
    def validate_dates_and_quantities(self) -> SellerOfferRevisionInput:
        if self.production_date and self.expiration_date:
            if self.expiration_date < self.production_date:
                raise ValueError("expiration_date cannot precede production_date")
        if self.minimum_order_quantity > self.proposed_total_quantity:
            raise ValueError("minimum_order_quantity cannot exceed proposed_total_quantity")
        if self.minimum_order_quantity % self.quantity_step != 0:
            raise ValueError("minimum_order_quantity must align with quantity_step")
        return self


class SellerOfferCreateRequest(B2BSchema):
    revision: SellerOfferRevisionInput


class AdminOfferPricingPatch(B2BSchema):
    public_title: Annotated[str | None, Field(max_length=300)] = None
    public_description: Annotated[str | None, Field(max_length=20_000)] = None
    markup_type: MarkupType
    markup_value: Annotated[Decimal, Field(ge=0, max_digits=18, decimal_places=4)]
    buyer_unit_price_kopecks: MoneyKopecks
    admin_comment: Annotated[str | None, Field(max_length=5_000)] = None


class OfferModerationRequest(B2BSchema):
    action: Literal["REVIEW", "REQUEST_CHANGES", "REJECT", "APPROVE", "PUBLISH", "PAUSE", "ARCHIVE"]
    reason: Annotated[str | None, Field(max_length=5_000)] = None


class BuyerOfferResponse(TimestampedResponse):
    """Buyer-safe catalog projection: no supplier price, markup, or internal comments."""

    status: OfferStatus
    revision_id: UUID
    category_id: UUID
    public_title: str
    public_description: str
    brand: str | None = None
    buyer_unit_price_kopecks: MoneyKopecks
    currency: str
    sale_unit: str
    package_size: Quantity
    available_quantity: NonNegativeQuantity
    minimum_order_quantity: Quantity
    quantity_step: Quantity
    production_date: date | None = None
    expiration_date: date | None = None
    storage_conditions: str | None = None
    images: list[OfferImageResponse] = Field(default_factory=list)
    published_at: datetime | None = None
    expires_at: datetime | None = None


class SellerOfferResponse(TimestampedResponse):
    """Seller projection intentionally excludes buyer price and platform margin."""

    seller_profile_id: UUID
    status: OfferStatus
    revision_id: UUID
    revision_number: int
    category_id: UUID
    original_title: str
    original_description: str
    brand: str | None = None
    supplier_unit_price_kopecks: MoneyKopecks
    currency: str
    sale_unit: str
    proposed_total_quantity: Quantity
    available_quantity: NonNegativeQuantity
    minimum_order_quantity: Quantity
    quantity_step: Quantity
    rejection_reason: str | None = None
    submitted_at: datetime | None = None
    reviewed_at: datetime | None = None
    published_at: datetime | None = None
    images: list[OfferImageResponse] = Field(default_factory=list)


class AdminOfferResponse(SellerOfferResponse):
    public_title: str | None = None
    public_description: str | None = None
    markup_type: MarkupType | None = None
    markup_value: Decimal | None = None
    buyer_unit_price_kopecks: MoneyKopecks | None = None
    admin_comment: str | None = None
    reviewed_by_user_id: int | None = None


class CartItemUpsertRequest(B2BSchema):
    offer_id: UUID
    quantity: Quantity


class CartItemResponse(TimestampedResponse):
    offer_id: UUID
    public_title: str
    quantity: Quantity
    buyer_unit_price_kopecks: MoneyKopecks
    line_total_kopecks: MoneyKopecks
    currency: str
    available_quantity: NonNegativeQuantity


class CartResponse(TimestampedResponse):
    buyer_profile_id: UUID
    status: Literal["ACTIVE", "CHECKED_OUT", "ABANDONED"]
    items: list[CartItemResponse] = Field(default_factory=list)
    items_total_kopecks: MoneyKopecks
    currency: str = "RUB"


class CheckoutRequest(B2BSchema):
    idempotency_key: Annotated[str, Field(min_length=8, max_length=128)]
    address_id: UUID
    recipient_name: Annotated[str, Field(min_length=1, max_length=200)]
    recipient_phone: Annotated[str, Field(min_length=6, max_length=32)]
    payment_method: Literal["PAY_ON_DELIVERY", "BANK_TRANSFER", "MANUAL"]
    desired_delivery_from: datetime | None = None
    desired_delivery_to: datetime | None = None
    comment: Annotated[str | None, Field(max_length=5_000)] = None
    terms_accepted: Literal[True]

    @model_validator(mode="after")
    def validate_delivery_window(self) -> CheckoutRequest:
        if (
            self.desired_delivery_from
            and self.desired_delivery_to
            and self.desired_delivery_to <= self.desired_delivery_from
        ):
            raise ValueError("desired_delivery_to must be after desired_delivery_from")
        return self


class OrderStatusPatch(B2BSchema):
    status: OrderStatus
    comment: Annotated[str | None, Field(max_length=5_000)] = None


class BuyerOrderItemResponse(B2BSchema):
    id: UUID
    offer_id: UUID
    public_title: str
    quantity: Quantity
    sale_unit: str
    buyer_unit_price_kopecks: MoneyKopecks
    buyer_total_kopecks: MoneyKopecks
    currency: str
    expiration_date: date | None = None


class SellerOrderItemResponse(B2BSchema):
    id: UUID
    order_id: UUID
    offer_id: UUID
    public_title: str
    quantity: Quantity
    sale_unit: str
    supplier_unit_price_kopecks: MoneyKopecks
    supplier_total_kopecks: MoneyKopecks
    currency: str


class AdminOrderItemResponse(BuyerOrderItemResponse):
    supplier_unit_price_kopecks: MoneyKopecks
    supplier_total_kopecks: MoneyKopecks
    margin_kopecks: MoneyKopecks


class FulfillmentGroupResponse(TimestampedResponse):
    order_id: UUID
    seller_profile_id: UUID
    status: OrderStatus
    pickup_address: str
    pickup_window_from: datetime | None = None
    pickup_window_to: datetime | None = None
    seller_confirmed_at: datetime | None = None
    ready_at: datetime | None = None


class BuyerOrderResponse(TimestampedResponse):
    order_number: str
    status: OrderStatus
    payment_method: Literal["PAY_ON_DELIVERY", "BANK_TRANSFER", "MANUAL"]
    delivery_address: str
    recipient_name: str
    recipient_phone: str
    desired_delivery_from: datetime | None = None
    desired_delivery_to: datetime | None = None
    comment: str | None = None
    items_total_kopecks: MoneyKopecks
    delivery_fee_kopecks: MoneyKopecks
    total_kopecks: MoneyKopecks
    currency: str
    items: list[BuyerOrderItemResponse] = Field(default_factory=list)


class SellerFulfillmentResponse(FulfillmentGroupResponse):
    items: list[SellerOrderItemResponse] = Field(default_factory=list)


class AdminOrderResponse(BuyerOrderResponse):
    buyer_profile_id: UUID
    items: list[AdminOrderItemResponse] = Field(default_factory=list)
    fulfillment_groups: list[FulfillmentGroupResponse] = Field(default_factory=list)


class DeliveryPatch(B2BSchema):
    status: DeliveryStatus | None = None
    courier_name: Annotated[str | None, Field(max_length=200)] = None
    courier_contact: Annotated[str | None, Field(max_length=100)] = None
    pickup_window_from: datetime | None = None
    pickup_window_to: datetime | None = None
    delivery_window_from: datetime | None = None
    delivery_window_to: datetime | None = None
    cost_kopecks: MoneyKopecks | None = None
    internal_notes: Annotated[str | None, Field(max_length=5_000)] = None


class DeliveryResponse(TimestampedResponse):
    order_id: UUID
    fulfillment_group_id: UUID | None = None
    provider: str
    external_delivery_id: str | None = None
    status: DeliveryStatus
    pickup_address: str
    delivery_address: str
    courier_name: str | None = None
    courier_contact: str | None = None
    cost_kopecks: MoneyKopecks | None = None
    picked_up_at: datetime | None = None
    delivered_at: datetime | None = None


class PageMeta(B2BSchema):
    limit: Annotated[int, Field(ge=1, le=200)]
    offset: Annotated[int, Field(ge=0)]
    total: Annotated[int, Field(ge=0)]


class BuyerOfferPage(B2BSchema):
    items: list[BuyerOfferResponse]
    page: PageMeta


class OrderPage(B2BSchema):
    items: list[BuyerOrderResponse]
    page: PageMeta
