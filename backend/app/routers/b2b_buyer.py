from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from typing import Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import and_, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.deps.b2b import (
    B2BPrincipal,
    active_subscription_for,
    buyer_profile_for,
    catalog_access,
    require_active_subscription,
    require_buyer,
)
from app.models.b2b import (
    B2BCategory,
    B2BOrder,
    B2BOrderItem,
    B2BOrderStatusHistory,
    BuyerAddress,
    BuyerProfile,
    Cart,
    CartItem,
    InventoryBalance,
    InventoryMovement,
    InventoryReservation,
    Offer,
    OfferImage,
    OfferRevision,
    OrderFulfillmentGroup,
    SellerProfile,
    Subscription,
    SubscriptionPayment,
    SubscriptionPlan,
)
from app.models.user import User
from app.services.b2b_common import (
    available_quantity_label,
    page_offset,
    require_idempotency_key,
    utcnow,
)
from app.services.b2b_inventory import InventoryError, validate_order_quantity
from app.services.b2b_notifications import enqueue_notification
from app.services.b2b_orders import transition_order
from app.services.b2b_payments import MockPaymentProvider, PaymentError, PaymentRequest
from app.services.b2b_pricing import calculate_line_total_kopecks
from app.services.b2b_subscriptions import activate_paid_subscription
from app.services.b2b_settings import runtime_setting
from app.services.phone_norm import normalize_phone_to_storage


router = APIRouter(prefix="/api/buyer", tags=["b2b-buyer"])


class StrictBody(BaseModel):
    model_config = ConfigDict(extra="forbid")


class BuyerProfilePatch(StrictBody):
    companyName: str | None = Field(default=None, max_length=250)
    legalForm: str | None = Field(default=None, max_length=32)
    inn: str | None = Field(default=None, max_length=20)
    contactName: str | None = Field(default=None, max_length=200)
    phone: str | None = Field(default=None, max_length=32)
    email: str | None = Field(default=None, max_length=320)


class AddressBody(StrictBody):
    label: str = Field(min_length=1, max_length=120)
    value: str = Field(min_length=5, max_length=2000)
    contactName: str | None = Field(default=None, max_length=200)
    contactPhone: str | None = Field(default=None, max_length=32)
    instructions: str | None = Field(default=None, max_length=2000)
    isDefault: bool = False


class PaymentBody(StrictBody):
    planId: UUID | None = None
    returnUrl: str | None = Field(default=None, max_length=2000)
    idempotencyKey: str | None = Field(default=None, min_length=8, max_length=128)


class CartItemBody(StrictBody):
    offerId: UUID | None = None
    quantity: Decimal = Field(gt=0)


class CheckoutBody(StrictBody):
    addressId: UUID
    recipientName: str = Field(min_length=1, max_length=200)
    recipientPhone: str = Field(min_length=6, max_length=32)
    deliveryWindow: str | None = Field(default=None, max_length=250)
    comment: str | None = Field(default=None, max_length=2000)
    paymentMethod: Literal["PAY_ON_DELIVERY", "BANK_TRANSFER", "MANUAL"] = "PAY_ON_DELIVERY"
    idempotencyKey: str = Field(min_length=8, max_length=128)
    termsAccepted: Literal[True]


async def _lock_idempotency_key(db: AsyncSession, namespace: str, key: str) -> None:
    """Serialize equal keys before their unique rows exist (PostgreSQL runtime)."""
    get_bind = getattr(db, "get_bind", None)
    if not callable(get_bind):
        return
    bind = get_bind()
    if bind.dialect.name != "postgresql":
        return
    await db.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
        {"key": f"kulcha-b2b:{namespace}:{key}"},
    )


def _subscription_dto(
    subscription: Subscription | None,
    plan: SubscriptionPlan | None,
    access: str,
) -> dict:
    return {
        "status": subscription.status if subscription else "NONE",
        "accessPolicy": access,
        "planName": plan.name if plan else None,
        "amountKopecks": plan.price_kopecks if plan else None,
        "currency": plan.currency if plan else "RUB",
        "expiresAt": subscription.ends_at if subscription else None,
        "autoRenew": False,
    }


async def _profile_dto(db: AsyncSession, user: User, profile: object) -> dict:
    addresses = list(
        (
            await db.execute(
                select(BuyerAddress)
                .where(
                    BuyerAddress.buyer_profile_id == profile.id,
                    BuyerAddress.is_active.is_(True),
                )
                .order_by(BuyerAddress.is_default.desc(), BuyerAddress.created_at)
            )
        ).scalars().all()
    )
    subscription = await active_subscription_for(db, profile.id)
    plan = await db.get(SubscriptionPlan, subscription.plan_id) if subscription else None
    access = await catalog_access(db, profile.id)
    return {
        "id": str(profile.id),
        "companyName": profile.company_name or "",
        "legalForm": profile.company_type,
        "inn": profile.inn,
        "contactName": profile.contact_name or user.username,
        "phone": profile.phone or user.phone,
        "email": user.email,
        "addresses": [
            {
                "id": str(address.id),
                "label": address.label,
                "value": address.address,
                "isDefault": address.is_default,
            }
            for address in addresses
        ],
        "subscription": _subscription_dto(subscription, plan, access),
    }


async def _published_offer_query(db: AsyncSession, offer_id: UUID | None = None):
    now = utcnow()
    stmt = (
        select(Offer, OfferRevision, B2BCategory, InventoryBalance)
        .join(
            OfferRevision,
            and_(OfferRevision.offer_id == Offer.id, OfferRevision.is_published.is_(True)),
        )
        .join(B2BCategory, B2BCategory.id == OfferRevision.category_id)
        .join(InventoryBalance, InventoryBalance.offer_id == Offer.id)
        .where(
            Offer.status == "PUBLISHED",
            or_(Offer.publication_starts_at.is_(None), Offer.publication_starts_at <= now),
            or_(Offer.expires_at.is_(None), Offer.expires_at > now),
            InventoryBalance.total_quantity
            > InventoryBalance.reserved_quantity + InventoryBalance.sold_quantity,
        )
    )
    if offer_id:
        stmt = stmt.where(Offer.id == offer_id)
    return stmt


async def _images_by_revision(db: AsyncSession, revision_ids: list[UUID]) -> dict[UUID, list[str]]:
    if not revision_ids:
        return {}
    result = await db.execute(
        select(OfferImage)
        .where(OfferImage.revision_id.in_(revision_ids))
        .order_by(OfferImage.revision_id, OfferImage.display_order)
    )
    images: dict[UUID, list[str]] = {}
    for image in result.scalars().all():
        images.setdefault(image.revision_id, []).append(image.public_url)
    return images


def _offer_dto(row: tuple, images: list[str], access: str) -> dict:
    offer, revision, category, balance = row
    show_price = access in {"FULL", "READ_ONLY"}
    return {
        "id": str(offer.id),
        "publicName": revision.public_title or revision.original_title,
        "publicDescription": revision.public_description or revision.original_description,
        "category": category.name,
        "photos": images,
        "buyerUnitPriceKopecks": revision.buyer_unit_price_kopecks if show_price else None,
        "currency": revision.currency,
        "unit": revision.sale_unit,
        "packageSize": str(revision.package_size),
        "availableQuantityLabel": available_quantity_label(balance.available_quantity),
        "minimumQuantity": float(revision.minimum_order_quantity),
        "quantityStep": float(revision.quantity_step),
        "shelfLife": revision.expiration_date.isoformat() if revision.expiration_date else None,
        "storageConditions": revision.storage_conditions,
        "deliveryTerms": "Условия и окно доставки подтвердит администратор",
        "expiresAt": offer.expires_at,
    }


@router.get("/me")
async def buyer_me(
    principal: B2BPrincipal = Depends(require_buyer),
    db: AsyncSession = Depends(get_db),
):
    profile = await buyer_profile_for(db, principal.user.id)
    return await _profile_dto(db, principal.user, profile)


@router.patch("/me")
async def update_buyer_me(
    body: BuyerProfilePatch,
    principal: B2BPrincipal = Depends(require_buyer),
    db: AsyncSession = Depends(get_db),
):
    profile = await buyer_profile_for(db, principal.user.id)
    values = body.model_dump(exclude_unset=True)
    mapping = {
        "companyName": "company_name",
        "legalForm": "company_type",
        "inn": "inn",
        "contactName": "contact_name",
    }
    for key, attribute in mapping.items():
        if key in values:
            setattr(profile, attribute, values[key] or None)
    if "phone" in values:
        phone = normalize_phone_to_storage(values["phone"] or "")
        if not phone:
            raise HTTPException(422, "Некорректный номер телефона")
        profile.phone = phone
        principal.user.phone = phone
    if "email" in values:
        principal.user.email = values["email"] or None
    await db.flush()
    return await _profile_dto(db, principal.user, profile)


@router.post("/addresses", status_code=201)
async def create_address(
    body: AddressBody,
    principal: B2BPrincipal = Depends(require_buyer),
    db: AsyncSession = Depends(get_db),
):
    profile = await buyer_profile_for(db, principal.user.id)
    if body.isDefault:
        result = await db.execute(
            select(BuyerAddress).where(BuyerAddress.buyer_profile_id == profile.id)
        )
        for address in result.scalars().all():
            address.is_default = False
    address = BuyerAddress(
        buyer_profile_id=profile.id,
        label=body.label,
        address=body.value,
        contact_name=body.contactName,
        contact_phone=normalize_phone_to_storage(body.contactPhone or "") or None,
        delivery_instructions=body.instructions,
        is_default=body.isDefault,
        is_active=True,
    )
    db.add(address)
    await db.flush()
    return {"id": str(address.id), "label": address.label, "value": address.address, "isDefault": address.is_default}


@router.get("/subscription")
async def buyer_subscription(
    principal: B2BPrincipal = Depends(require_buyer),
    db: AsyncSession = Depends(get_db),
):
    profile = await buyer_profile_for(db, principal.user.id)
    subscription = await active_subscription_for(db, profile.id)
    plan = await db.get(SubscriptionPlan, subscription.plan_id) if subscription else None
    return _subscription_dto(subscription, plan, await catalog_access(db, profile.id))


@router.post("/subscription/payments", status_code=201)
async def create_subscription_payment(
    body: PaymentBody,
    principal: B2BPrincipal = Depends(require_buyer),
    db: AsyncSession = Depends(get_db),
    idempotency_header: str | None = Header(None, alias="Idempotency-Key"),
):
    profile = await buyer_profile_for(db, principal.user.id)
    idempotency_key = require_idempotency_key(idempotency_header or body.idempotencyKey)
    if idempotency_header and body.idempotencyKey and idempotency_header != body.idempotencyKey:
        raise HTTPException(409, "Idempotency-Key header и body не совпадают")
    await _lock_idempotency_key(db, "subscription-payment", idempotency_key)
    settings = get_settings()
    if settings.payment_provider != "mock":
        raise HTTPException(503, "Production payment provider ещё не настроен")
    if not settings.payment_webhook_secret:
        raise HTTPException(503, "PAYMENT_WEBHOOK_SECRET не настроен")
    plan = await db.get(SubscriptionPlan, body.planId) if body.planId else None
    if not plan:
        plan = (
            await db.execute(
                select(SubscriptionPlan)
                .where(SubscriptionPlan.is_active.is_(True))
                .order_by(SubscriptionPlan.price_kopecks)
                .limit(1)
            )
        ).scalars().first()
    if not plan or not plan.is_active:
        raise HTTPException(404, "Активный тариф не найден")
    existing = (
        await db.execute(
            select(SubscriptionPayment).where(
                SubscriptionPayment.provider == "mock",
                SubscriptionPayment.idempotency_key == idempotency_key,
            )
        )
    ).scalars().first()
    if existing:
        if existing.buyer_profile_id != profile.id:
            raise HTTPException(409, "Idempotency-Key уже использован другим покупателем")
        if existing.plan_id != plan.id:
            raise HTTPException(409, "Idempotency-Key уже использован для другого тарифа")
        return {
            "id": str(existing.id),
            "status": existing.status,
            "paymentUrl": existing.confirmation_url,
        }
    try:
        provider = MockPaymentProvider(
            environment=settings.app_env,
            webhook_secret=settings.payment_webhook_secret,
        )
        intent = await provider.create_payment(
            PaymentRequest(
                idempotency_key=idempotency_key,
                amount_kopecks=plan.price_kopecks,
                currency=plan.currency,
                return_url=body.returnUrl,
                metadata={"buyerProfileId": str(profile.id), "planId": str(plan.id)},
            )
        )
    except (PaymentError, RuntimeError) as exc:
        raise HTTPException(503, str(exc)) from exc
    payment = SubscriptionPayment(
        buyer_profile_id=profile.id,
        plan_id=plan.id,
        provider=intent.provider,
        provider_payment_id=intent.provider_payment_id,
        idempotency_key=idempotency_key,
        status=intent.status.value,
        amount_kopecks=intent.amount_kopecks,
        currency=intent.currency,
        confirmation_url=intent.confirmation_url,
        provider_payload=dict(intent.raw_payload),
    )
    db.add(payment)
    await db.flush()
    return {"id": str(payment.id), "status": payment.status, "paymentUrl": payment.confirmation_url}


@router.post("/subscription/payments/{payment_id}/mock-confirm")
async def mock_confirm_payment(
    payment_id: UUID,
    principal: B2BPrincipal = Depends(require_buyer),
    db: AsyncSession = Depends(get_db),
):
    if get_settings().app_env.lower() not in {"development", "dev", "local", "test", "testing"}:
        raise HTTPException(404, "Not found")
    profile = await buyer_profile_for(db, principal.user.id)
    payment = await db.get(SubscriptionPayment, payment_id, with_for_update=True)
    if not payment or payment.buyer_profile_id != profile.id:
        raise HTTPException(404, "Платёж не найден")
    subscription = await activate_paid_subscription(db, payment)
    return {"status": payment.status, "subscriptionEndsAt": subscription.ends_at}


@router.get("/catalog")
async def catalog(
    search: str | None = Query(None, max_length=200),
    category: str | None = Query(None, max_length=120),
    sort: Literal["NEWEST", "PRICE_ASC", "PRICE_DESC", "EXPIRY_ASC"] = "NEWEST",
    page: int = 1,
    page_size: int = Query(20, alias="pageSize"),
    principal: B2BPrincipal = Depends(require_buyer),
    db: AsyncSession = Depends(get_db),
):
    profile = await buyer_profile_for(db, principal.user.id)
    access = await catalog_access(db, profile.id)
    if access == "BLOCKED":
        return {"items": [], "total": 0, "page": page, "pageSize": page_size, "accessPolicy": access}
    offset, limit = page_offset(page, page_size)
    stmt = await _published_offer_query(db)
    if search:
        pattern = f"%{search.strip()}%"
        stmt = stmt.where(
            or_(OfferRevision.public_title.ilike(pattern), OfferRevision.original_title.ilike(pattern))
        )
    if category:
        stmt = stmt.where(or_(B2BCategory.slug == category, B2BCategory.name == category))
    ordering = {
        "NEWEST": Offer.published_at.desc(),
        "PRICE_ASC": OfferRevision.buyer_unit_price_kopecks.asc(),
        "PRICE_DESC": OfferRevision.buyer_unit_price_kopecks.desc(),
        "EXPIRY_ASC": Offer.expires_at.asc().nulls_last(),
    }[sort]
    rows = list((await db.execute(stmt.order_by(ordering).offset(offset).limit(limit))).all())
    # Count from the filtered statement without pagination/order.
    total = int((await db.execute(select(func.count()).select_from(stmt.order_by(None).subquery()))).scalar_one())
    images = await _images_by_revision(db, [row[1].id for row in rows])
    return {
        "items": [_offer_dto(row, images.get(row[1].id, []), access) for row in rows],
        "total": total,
        "page": page,
        "pageSize": page_size,
        "accessPolicy": access,
    }


@router.get("/catalog/{offer_id}")
async def catalog_offer(
    offer_id: UUID,
    principal: B2BPrincipal = Depends(require_buyer),
    db: AsyncSession = Depends(get_db),
):
    profile = await buyer_profile_for(db, principal.user.id)
    access = await catalog_access(db, profile.id)
    if access == "BLOCKED":
        raise HTTPException(403, "Каталог недоступен без подписки")
    row = (await db.execute(await _published_offer_query(db, offer_id))).first()
    if not row:
        raise HTTPException(404, "Предложение не найдено")
    images = await _images_by_revision(db, [row[1].id])
    return _offer_dto(row, images.get(row[1].id, []), access)


async def _active_cart(db: AsyncSession, buyer_profile_id: UUID, *, create: bool = True) -> Cart | None:
    cart = (
        await db.execute(
            select(Cart).where(Cart.buyer_profile_id == buyer_profile_id, Cart.status == "ACTIVE")
        )
    ).scalars().first()
    if not cart and create:
        await db.get(BuyerProfile, buyer_profile_id, with_for_update=True)
        cart = (
            await db.execute(
                select(Cart).where(
                    Cart.buyer_profile_id == buyer_profile_id,
                    Cart.status == "ACTIVE",
                )
            )
        ).scalars().first()
        if not cart:
            cart = Cart(buyer_profile_id=buyer_profile_id, status="ACTIVE")
            db.add(cart)
            await db.flush()
    return cart


async def _cart_dto(db: AsyncSession, cart: Cart, access: str = "FULL") -> dict:
    result = await db.execute(
        select(CartItem, Offer, OfferRevision, B2BCategory, InventoryBalance)
        .join(Offer, Offer.id == CartItem.offer_id)
        .join(OfferRevision, and_(OfferRevision.offer_id == Offer.id, OfferRevision.is_published.is_(True)))
        .join(B2BCategory, B2BCategory.id == OfferRevision.category_id)
        .join(InventoryBalance, InventoryBalance.offer_id == Offer.id)
        .where(CartItem.cart_id == cart.id)
        .order_by(CartItem.created_at)
    )
    rows = list(result.all())
    images = await _images_by_revision(db, [row[2].id for row in rows])
    lines = []
    total = 0
    expose_totals = access in {"FULL", "READ_ONLY"}
    for item, offer, revision, category, balance in rows:
        line_total = (
            calculate_line_total_kopecks(revision.buyer_unit_price_kopecks or 0, item.quantity)
            if expose_totals
            else 0
        )
        total += line_total
        lines.append(
            {
                "id": str(item.id),
                "offer": _offer_dto(
                    (offer, revision, category, balance),
                    images.get(revision.id, []),
                    access,
                ),
                "quantity": float(item.quantity),
            }
        )
    return {
        "lines": lines,
        "itemsTotalKopecks": total,
        "deliveryFeeKopecks": None,
        "totalKopecks": total,
        "currency": "RUB",
        "expiresAt": None,
    }


@router.get("/cart")
async def get_cart(
    principal: B2BPrincipal = Depends(require_buyer),
    db: AsyncSession = Depends(get_db),
):
    profile = await buyer_profile_for(db, principal.user.id)
    cart = await _active_cart(db, profile.id)
    return await _cart_dto(db, cart, await catalog_access(db, profile.id))


async def _validate_cart_offer(db: AsyncSession, offer_id: UUID, quantity: Decimal):
    row = (await db.execute(await _published_offer_query(db, offer_id))).first()
    if not row:
        raise HTTPException(404, "Предложение недоступно")
    _, revision, _, balance = row
    if revision.buyer_unit_price_kopecks is None:
        raise HTTPException(409, "Цена предложения ещё не установлена")
    try:
        requested = validate_order_quantity(
            quantity,
            revision.minimum_order_quantity,
            revision.quantity_step,
        )
    except InventoryError as exc:
        raise HTTPException(422, str(exc)) from exc
    if requested > balance.available_quantity:
        raise HTTPException(409, "Недостаточный остаток")
    return requested


@router.post("/cart/items", status_code=201)
async def add_cart_item(
    body: CartItemBody,
    principal: B2BPrincipal = Depends(require_buyer),
    db: AsyncSession = Depends(get_db),
):
    if body.offerId is None:
        raise HTTPException(422, "offerId обязателен")
    profile = await buyer_profile_for(db, principal.user.id)
    await require_active_subscription(db, profile.id)
    requested = await _validate_cart_offer(db, body.offerId, body.quantity)
    cart = await _active_cart(db, profile.id)
    item = (
        await db.execute(
            select(CartItem).where(CartItem.cart_id == cart.id, CartItem.offer_id == body.offerId)
        )
    ).scalars().first()
    if item:
        item.quantity = requested
    else:
        db.add(CartItem(cart_id=cart.id, offer_id=body.offerId, quantity=requested))
    await db.flush()
    return await _cart_dto(db, cart)


@router.patch("/cart/items/{item_id}")
async def update_cart_item(
    item_id: UUID,
    body: CartItemBody,
    principal: B2BPrincipal = Depends(require_buyer),
    db: AsyncSession = Depends(get_db),
):
    profile = await buyer_profile_for(db, principal.user.id)
    await require_active_subscription(db, profile.id)
    cart = await _active_cart(db, profile.id)
    item = await db.get(CartItem, item_id)
    if not item or item.cart_id != cart.id:
        raise HTTPException(404, "Позиция корзины не найдена")
    item.quantity = await _validate_cart_offer(db, item.offer_id, body.quantity)
    await db.flush()
    return await _cart_dto(db, cart)


@router.delete("/cart/items/{item_id}")
async def remove_cart_item(
    item_id: UUID,
    principal: B2BPrincipal = Depends(require_buyer),
    db: AsyncSession = Depends(get_db),
):
    profile = await buyer_profile_for(db, principal.user.id)
    cart = await _active_cart(db, profile.id)
    item = await db.get(CartItem, item_id)
    if not item or item.cart_id != cart.id:
        raise HTTPException(404, "Позиция корзины не найдена")
    await db.delete(item)
    await db.flush()
    return await _cart_dto(db, cart)


def _order_summary(order: B2BOrder, items_count: int) -> dict:
    window = None
    if order.desired_delivery_from or order.desired_delivery_to:
        window = f"{order.desired_delivery_from or ''} — {order.desired_delivery_to or ''}"
    return {
        "id": str(order.id),
        "number": order.order_number,
        "status": order.status,
        "createdAt": order.created_at,
        "deliveryAddress": order.delivery_address_snapshot,
        "deliveryWindow": window,
        "totalKopecks": order.total_kopecks,
        "currency": order.currency,
        "itemsCount": items_count,
    }


@router.post("/orders", status_code=201)
async def create_order(
    body: CheckoutBody,
    request: Request,
    principal: B2BPrincipal = Depends(require_buyer),
    db: AsyncSession = Depends(get_db),
    idempotency_header: str | None = Header(None, alias="Idempotency-Key"),
):
    profile = await buyer_profile_for(db, principal.user.id)
    await require_active_subscription(db, profile.id)
    key = require_idempotency_key(idempotency_header or body.idempotencyKey)
    if idempotency_header and idempotency_header != body.idempotencyKey:
        raise HTTPException(409, "Idempotency-Key header и body не совпадают")
    await _lock_idempotency_key(db, "order", key)
    existing = (
        await db.execute(select(B2BOrder).where(B2BOrder.idempotency_key == key))
    ).scalars().first()
    if existing:
        if existing.buyer_profile_id != profile.id:
            raise HTTPException(409, "Idempotency-Key уже использован другим покупателем")
        count = int(
            (
                await db.execute(
                    select(func.count(B2BOrderItem.id)).where(B2BOrderItem.order_id == existing.id)
                )
            ).scalar_one()
        )
        return _order_summary(existing, count)
    address = await db.get(BuyerAddress, body.addressId)
    if not address or address.buyer_profile_id != profile.id or not address.is_active:
        raise HTTPException(404, "Адрес доставки не найден")
    phone = normalize_phone_to_storage(body.recipientPhone)
    if not phone:
        raise HTTPException(422, "Некорректный телефон получателя")
    cart = (
        await db.execute(
            select(Cart)
            .where(Cart.buyer_profile_id == profile.id, Cart.status == "ACTIVE")
            .with_for_update()
        )
    ).scalars().first()
    if not cart:
        raise HTTPException(409, "Корзина пуста")
    cart_items = list(
        (
            await db.execute(
                select(CartItem).where(CartItem.cart_id == cart.id).order_by(CartItem.offer_id)
            )
        ).scalars().all()
    )
    if not cart_items:
        raise HTTPException(409, "Корзина пуста")
    offer_ids = [item.offer_id for item in cart_items]
    balances = list(
        (
            await db.execute(
                select(InventoryBalance)
                .where(InventoryBalance.offer_id.in_(offer_ids))
                .order_by(InventoryBalance.offer_id)
                .with_for_update()
            )
        ).scalars().all()
    )
    balance_by_offer = {balance.offer_id: balance for balance in balances}
    details: list[tuple[CartItem, Offer, OfferRevision, InventoryBalance, SellerProfile]] = []
    items_total = 0
    for item in cart_items:
        offer = await db.get(Offer, item.offer_id)
        revision = (
            await db.execute(
                select(OfferRevision).where(
                    OfferRevision.offer_id == item.offer_id,
                    OfferRevision.is_published.is_(True),
                )
            )
        ).scalars().first()
        balance = balance_by_offer.get(item.offer_id)
        if not offer or offer.status != "PUBLISHED" or not revision or not balance:
            raise HTTPException(409, "Одна из позиций больше недоступна")
        try:
            quantity = validate_order_quantity(
                item.quantity,
                revision.minimum_order_quantity,
                revision.quantity_step,
            )
        except InventoryError as exc:
            raise HTTPException(422, str(exc)) from exc
        if quantity > balance.available_quantity:
            raise HTTPException(409, f"Недостаточный остаток: {revision.public_title or revision.original_title}")
        if revision.buyer_unit_price_kopecks is None:
            raise HTTPException(409, "Цена предложения изменилась")
        seller = await db.get(SellerProfile, offer.seller_profile_id)
        if not seller or seller.status != "VERIFIED":
            raise HTTPException(409, "Поставщик одной из позиций недоступен")
        item.quantity = quantity
        items_total += calculate_line_total_kopecks(revision.buyer_unit_price_kopecks, quantity)
        details.append((item, offer, revision, balance, seller))

    order_id = uuid4()
    comment_parts = [part for part in [body.comment, f"Желаемое окно: {body.deliveryWindow}" if body.deliveryWindow else None] if part]
    order = B2BOrder(
        id=order_id,
        order_number=f"B2B-{utcnow():%Y%m%d}-{str(order_id)[:8].upper()}",
        buyer_profile_id=profile.id,
        cart_id=cart.id,
        status="PENDING_CONFIRMATION",
        payment_method=body.paymentMethod,
        idempotency_key=key,
        delivery_address_snapshot=address.address,
        recipient_name=body.recipientName,
        recipient_phone=phone,
        comment="\n".join(comment_parts) or None,
        items_total_kopecks=items_total,
        delivery_fee_kopecks=0,
        total_kopecks=items_total,
        currency=await runtime_setting(db, "defaultCurrency", get_settings().default_currency),
        reserved_until=utcnow()
        + timedelta(
            minutes=await runtime_setting(
                db,
                "reservationTtlMinutes",
                get_settings().reservation_ttl_minutes,
            )
        ),
    )
    db.add(order)
    await db.flush()
    groups: dict[UUID, OrderFulfillmentGroup] = {}
    for _, _, _, _, seller in details:
        if seller.id not in groups:
            group = OrderFulfillmentGroup(
                order_id=order.id,
                seller_profile_id=seller.id,
                status="PENDING_CONFIRMATION",
                pickup_address_snapshot=seller.pickup_address or "Адрес уточняется администратором",
            )
            db.add(group)
            groups[seller.id] = group
    await db.flush()
    for item, offer, revision, balance, seller in details:
        supplier_total = calculate_line_total_kopecks(
            revision.supplier_unit_price_kopecks,
            item.quantity,
        )
        buyer_total = calculate_line_total_kopecks(
            revision.buyer_unit_price_kopecks,
            item.quantity,
        )
        db.add(
            B2BOrderItem(
                order_id=order.id,
                fulfillment_group_id=groups[seller.id].id,
                offer_id=offer.id,
                offer_revision_id=revision.id,
                public_title_snapshot=revision.public_title or revision.original_title,
                quantity=item.quantity,
                sale_unit_snapshot=revision.sale_unit,
                supplier_unit_price_kopecks=revision.supplier_unit_price_kopecks,
                buyer_unit_price_kopecks=revision.buyer_unit_price_kopecks,
                supplier_total_kopecks=supplier_total,
                buyer_total_kopecks=buyer_total,
                margin_kopecks=buyer_total - supplier_total,
                currency=revision.currency,
                pickup_address_snapshot=revision.pickup_address,
                expiration_date_snapshot=revision.expiration_date,
            )
        )
        reservation = InventoryReservation(
            inventory_balance_id=balance.id,
            buyer_profile_id=profile.id,
            order_id=order.id,
            quantity=item.quantity,
            status="ACTIVE",
            idempotency_key=f"{order.id}:{offer.id}",
            expires_at=order.reserved_until,
        )
        db.add(reservation)
        await db.flush()
        balance.reserved_quantity += item.quantity
        balance.version += 1
        db.add(
            InventoryMovement(
                inventory_balance_id=balance.id,
                reservation_id=reservation.id,
                movement_type="RESERVE",
                quantity=item.quantity,
                total_after=balance.total_quantity,
                reserved_after=balance.reserved_quantity,
                sold_after=balance.sold_quantity,
                actor_user_id=principal.user.id,
                reason=f"Checkout {order.order_number}",
            )
        )
    db.add(
        B2BOrderStatusHistory(
            order_id=order.id,
            from_status=None,
            to_status="RESERVED",
            actor_user_id=principal.user.id,
            actor_type="BUYER",
            comment="Inventory reserved transactionally",
        )
    )
    db.add(
        B2BOrderStatusHistory(
            order_id=order.id,
            from_status="RESERVED",
            to_status="PENDING_CONFIRMATION",
            actor_user_id=principal.user.id,
            actor_type="SYSTEM",
        )
    )
    cart.status = "CHECKED_OUT"
    cart.checked_out_at = utcnow()
    for seller in {detail[4].id: detail[4] for detail in details}.values():
        await enqueue_notification(
            db,
            user_id=seller.user_id,
            recipient=seller.user_id,
            event_type="SELLER_ORDER_CREATED",
            idempotency_key=f"seller-order-created:{order.id}:{seller.id}",
            text=f"Новый заказ {order.order_number}. Подтвердите наличие в приложении поставщика.",
            bot_scope="SELLER",
            deep_link=f"{get_settings().public_base_url.rstrip('/')}{get_settings().seller_app_path}/orders",
        )
    await enqueue_notification(
        db,
        user_id=profile.user_id,
        recipient=profile.user_id,
        event_type="BUYER_ORDER_RESERVED",
        idempotency_key=f"buyer-order-created:{order.id}",
        text=(
            f"Заказ {order.order_number} создан. Товары зарезервированы до "
            f"{order.reserved_until:%d.%m.%Y %H:%M}."
        ),
        bot_scope="BUYER",
        deep_link=(
            f"{get_settings().public_base_url.rstrip('/')}"
            f"{get_settings().buyer_app_path}/orders/{order.id}"
        ),
    )
    await db.flush()
    return _order_summary(order, len(details))


@router.get("/orders")
async def buyer_orders(
    page: int = 1,
    page_size: int = Query(20, alias="pageSize"),
    principal: B2BPrincipal = Depends(require_buyer),
    db: AsyncSession = Depends(get_db),
):
    profile = await buyer_profile_for(db, principal.user.id)
    offset, limit = page_offset(page, page_size)
    total = int(
        (
            await db.execute(
                select(func.count(B2BOrder.id)).where(B2BOrder.buyer_profile_id == profile.id)
            )
        ).scalar_one()
    )
    orders = list(
        (
            await db.execute(
                select(B2BOrder)
                .where(B2BOrder.buyer_profile_id == profile.id)
                .order_by(B2BOrder.created_at.desc())
                .offset(offset)
                .limit(limit)
            )
        ).scalars().all()
    )
    counts = {}
    if orders:
        result = await db.execute(
            select(B2BOrderItem.order_id, func.count(B2BOrderItem.id))
            .where(B2BOrderItem.order_id.in_([order.id for order in orders]))
            .group_by(B2BOrderItem.order_id)
        )
        counts = dict(result.all())
    return {
        "items": [_order_summary(order, int(counts.get(order.id, 0))) for order in orders],
        "total": total,
        "page": page,
        "pageSize": page_size,
    }


@router.get("/orders/{order_id}")
async def buyer_order(
    order_id: UUID,
    principal: B2BPrincipal = Depends(require_buyer),
    db: AsyncSession = Depends(get_db),
):
    profile = await buyer_profile_for(db, principal.user.id)
    order = await db.get(B2BOrder, order_id)
    if not order or order.buyer_profile_id != profile.id:
        raise HTTPException(404, "Заказ не найден")
    items = list(
        (
            await db.execute(
                select(B2BOrderItem).where(B2BOrderItem.order_id == order.id)
            )
        ).scalars().all()
    )
    dto = _order_summary(order, len(items))
    # Buyer projection deliberately excludes supplier cost, margin, seller and pickup data.
    dto["items"] = [
        {
            "id": str(item.id),
            "title": item.public_title_snapshot,
            "quantity": float(item.quantity),
            "unit": item.sale_unit_snapshot,
            "buyerUnitPriceKopecks": item.buyer_unit_price_kopecks,
            "buyerTotalKopecks": item.buyer_total_kopecks,
        }
        for item in items
    ]
    return dto


@router.post("/orders/{order_id}/cancel")
async def cancel_buyer_order(
    order_id: UUID,
    principal: B2BPrincipal = Depends(require_buyer),
    db: AsyncSession = Depends(get_db),
):
    profile = await buyer_profile_for(db, principal.user.id)
    order = (
        await db.execute(
            select(B2BOrder).where(B2BOrder.id == order_id).with_for_update()
        )
    ).scalars().first()
    if not order or order.buyer_profile_id != profile.id:
        raise HTTPException(404, "Заказ не найден")
    if order.status not in {"RESERVED", "PENDING_CONFIRMATION"}:
        raise HTTPException(409, "Заказ уже нельзя отменить самостоятельно")
    await transition_order(
        db,
        order,
        "CANCELED",
        actor_user_id=principal.user.id,
        actor_type="BUYER",
        comment="Отменено покупателем",
    )
    return _order_summary(order, 0)
