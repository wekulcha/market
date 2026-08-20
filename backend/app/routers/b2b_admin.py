from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.deps.b2b import B2BPrincipal, require_admin
from app.models.b2b import (
    AuditLog,
    B2BCategory,
    B2BOrder,
    B2BOrderItem,
    BuyerProfile,
    Delivery,
    DeliveryStatusHistory,
    InventoryBalance,
    InviteLink,
    Notification,
    Offer,
    OfferImage,
    OfferRevision,
    OrderFulfillmentGroup,
    SellerProfile,
    Subscription,
    SubscriptionPlan,
    SystemSetting,
)
from app.services.b2b_common import issue_invite_token, page_offset, utcnow
from app.services.b2b_delivery import (
    DeliveryProviderError,
    DeliveryRequest,
    get_delivery_provider,
)
from app.services.b2b_notifications import enqueue_notification
from app.services.b2b_orders import transition_order
from app.services.b2b_pricing import PricingError, build_price_snapshot
from app.services.b2b_rate_limit import rate_limit
from app.services.b2b_settings import runtime_setting


router = APIRouter(prefix="/api/admin", tags=["b2b-admin"])


class StrictBody(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ModerationBody(StrictBody):
    decision: Literal["APPROVE", "REJECT", "REQUEST_CHANGES"]
    reason: str | None = Field(default=None, max_length=2000)


class PricingBody(StrictBody):
    markupType: Literal["PERCENT", "FIXED", "MANUAL"]
    markupPercent: Decimal | None = None
    fixedMarkupKopecks: int | None = Field(default=None, ge=0)
    manualBuyerUnitPriceKopecks: int | None = Field(default=None, ge=0)


class InviteBody(StrictBody):
    label: str | None = Field(default=None, max_length=120)
    expiresInDays: int = Field(default=7, ge=1, le=365)
    maxUses: int = Field(default=1, ge=1, le=100)
    planId: UUID | None = None
    trialDays: int = Field(default=0, ge=0, le=365)
    source: str | None = Field(default=None, max_length=120)


class TransitionBody(StrictBody):
    status: str = Field(min_length=2, max_length=32)
    comment: str | None = Field(default=None, max_length=2000)


class DeliveryBody(StrictBody):
    orderId: UUID
    courierName: str = Field(min_length=1, max_length=200)
    courierContact: str | None = Field(default=None, max_length=100)
    pickupWindow: str | None = Field(default=None, max_length=250)
    deliveryWindow: str | None = Field(default=None, max_length=250)
    costKopecks: int | None = Field(default=None, ge=0)


class DeliveryStatusBody(StrictBody):
    status: Literal["ASSIGNED", "PICKED_UP", "IN_DELIVERY", "DELIVERED", "CANCELED", "FAILED"]
    comment: str | None = Field(default=None, max_length=2000)


class SubscriptionOverrideBody(StrictBody):
    buyerId: UUID
    status: Literal["TRIAL", "ACTIVE", "PAST_DUE", "EXPIRED", "CANCELED", "BLOCKED"]
    expiresAt: datetime
    reason: str = Field(min_length=3, max_length=2000)
    planId: UUID | None = None


class SellerStatusBody(StrictBody):
    status: Literal["PENDING", "VERIFIED", "SUSPENDED", "BLOCKED"]
    reason: str = Field(min_length=3, max_length=2000)


class PlanBody(StrictBody):
    code: str = Field(min_length=2, max_length=64)
    name: str = Field(min_length=2, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    priceKopecks: int = Field(ge=0)
    durationDays: int = Field(default=30, gt=0, le=366)
    trialDays: int = Field(default=0, ge=0, le=365)


class PlanPatch(StrictBody):
    code: str | None = Field(default=None, min_length=2, max_length=64)
    name: str | None = Field(default=None, min_length=2, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    priceKopecks: int | None = Field(default=None, ge=0)
    durationDays: int | None = Field(default=None, gt=0, le=366)
    trialDays: int | None = Field(default=None, ge=0, le=365)
    isActive: bool | None = None


class SettingsPatch(StrictBody):
    appName: str | None = Field(default=None, min_length=1, max_length=120)
    catalogAccessPolicy: Literal["BLOCKED", "TEASER", "READ_ONLY"] | None = None
    reservationTtlMinutes: int | None = Field(default=None, ge=1, le=1440)
    subscriptionGracePeriodDays: int | None = Field(default=None, ge=0, le=365)
    defaultCurrency: str | None = Field(default=None, min_length=3, max_length=3)
    timezone: str | None = Field(default=None, min_length=1, max_length=100)

    @field_validator("defaultCurrency")
    @classmethod
    def validate_currency(cls, value: str | None) -> str | None:
        if value is None:
            return None
        currency = value.upper()
        if not currency.isalpha():
            raise ValueError("Валюта должна быть трёхбуквенным ISO-кодом")
        return currency

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str | None) -> str | None:
        if value is None:
            return None
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("Неизвестный часовой пояс IANA") from exc
        return value


async def _audit(
    db: AsyncSession,
    request: Request,
    actor: B2BPrincipal,
    *,
    action: str,
    entity_type: str,
    entity_id: object,
    reason: str | None = None,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
) -> None:
    db.add(
        AuditLog(
            actor_user_id=actor.user.id,
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id),
            reason=reason,
            before_data=before,
            after_data=after,
            request_id=getattr(request.state, "request_id", None),
            correlation_id=getattr(request.state, "request_id", None),
            ip_address=request.client.host if request.client else None,
        )
    )


async def _admin_offer_dto(db: AsyncSession, offer: Offer) -> dict:
    revision = (
        await db.execute(
            select(OfferRevision)
            .where(OfferRevision.offer_id == offer.id)
            .order_by(OfferRevision.revision_number.desc())
            .limit(1)
        )
    ).scalars().first()
    if not revision:
        raise HTTPException(500, "Offer revision missing")
    seller = await db.get(SellerProfile, offer.seller_profile_id)
    category = await db.get(B2BCategory, revision.category_id)
    balance = (
        await db.execute(select(InventoryBalance).where(InventoryBalance.offer_id == offer.id))
    ).scalars().first()
    images = list(
        (
            await db.execute(
                select(OfferImage)
                .where(OfferImage.revision_id == revision.id)
                .order_by(OfferImage.display_order)
            )
        ).scalars().all()
    )
    markup_value = revision.markup_value
    return {
        "id": str(offer.id),
        "title": revision.public_title or revision.original_title,
        "subtitle": seller.company_name if seller else None,
        "amountKopecks": revision.buyer_unit_price_kopecks,
        "createdAt": offer.created_at,
        "name": revision.original_title,
        "description": revision.original_description,
        "category": category.name if category else "",
        "photos": [image.public_url for image in images],
        "procurementUnitPriceKopecks": revision.supplier_unit_price_kopecks,
        "currency": revision.currency,
        "unit": revision.sale_unit,
        "packageSize": str(revision.package_size),
        "totalQuantity": float(balance.total_quantity if balance else revision.proposed_total_quantity),
        "reservedQuantity": float(balance.reserved_quantity if balance else 0),
        "availableQuantity": float(balance.available_quantity if balance else 0),
        "minimumQuantity": float(revision.minimum_order_quantity),
        "quantityStep": float(revision.quantity_step),
        "shelfLife": revision.expiration_date.isoformat() if revision.expiration_date else None,
        "storageConditions": revision.storage_conditions,
        "expiresAt": offer.expires_at,
        "status": offer.status,
        "rejectionReason": offer.rejection_reason,
        "updatedAt": offer.updated_at,
        "sellerDisplayName": seller.company_name if seller else "",
        "sellerId": str(seller.id) if seller else "",
        "proposedBuyerUnitPriceKopecks": revision.buyer_unit_price_kopecks,
        "markupType": revision.markup_type or "PERCENT",
        "markupValue": float(markup_value) if markup_value is not None else None,
        "fixedMarkupKopecks": int(markup_value) if revision.markup_type == "FIXED" and markup_value is not None else None,
        "manualBuyerUnitPriceKopecks": int(markup_value) if revision.markup_type == "MANUAL" and markup_value is not None else None,
        "internalComment": offer.admin_comment,
    }


@router.get("/dashboard")
async def dashboard(
    principal: B2BPrincipal = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    del principal
    now = utcnow()
    pending_offers = int(
        (
            await db.execute(
                select(func.count(Offer.id)).where(Offer.status.in_(("SUBMITTED", "UNDER_REVIEW")))
            )
        ).scalar_one()
    )
    active_offers = int(
        (await db.execute(select(func.count(Offer.id)).where(Offer.status == "PUBLISHED"))).scalar_one()
    )
    inventory_rows = list(
        (
            await db.execute(
                select(InventoryBalance, OfferRevision)
                .join(Offer, Offer.id == InventoryBalance.offer_id)
                .join(
                    OfferRevision,
                    (OfferRevision.offer_id == Offer.id) & (OfferRevision.is_published.is_(True)),
                )
                .where(Offer.status == "PUBLISHED")
            )
        ).all()
    )
    inventory_value = sum(
        int((balance.available_quantity * revision.supplier_unit_price_kopecks).quantize(Decimal("1")))
        for balance, revision in inventory_rows
    )
    low_stock = sum(
        1
        for balance, revision in inventory_rows
        if balance.available_quantity <= revision.minimum_order_quantity * 2
    )
    valid_order_statuses = (
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
    )
    new_orders = int(
        (
            await db.execute(
                select(func.count(B2BOrder.id)).where(B2BOrder.created_at >= now - timedelta(days=1))
            )
        ).scalar_one()
    )
    gmv = int(
        (
            await db.execute(
                select(func.coalesce(func.sum(B2BOrder.total_kopecks), 0)).where(
                    B2BOrder.status.in_(valid_order_statuses)
                )
            )
        ).scalar_one()
    )
    margin = int(
        (
            await db.execute(
                select(func.coalesce(func.sum(B2BOrderItem.margin_kopecks), 0))
                .join(B2BOrder, B2BOrder.id == B2BOrderItem.order_id)
                .where(B2BOrder.status.in_(valid_order_statuses))
            )
        ).scalar_one()
    )
    active_subscribers = int(
        (
            await db.execute(
                select(func.count(func.distinct(Subscription.buyer_profile_id))).where(
                    Subscription.status.in_(("TRIAL", "ACTIVE")),
                    Subscription.ends_at > now,
                )
            )
        ).scalar_one()
    )
    mrr = int(
        (
            await db.execute(
                select(func.coalesce(func.sum(SubscriptionPlan.price_kopecks), 0))
                .select_from(Subscription)
                .join(SubscriptionPlan, SubscriptionPlan.id == Subscription.plan_id)
                .where(Subscription.status == "ACTIVE", Subscription.ends_at > now)
            )
        ).scalar_one()
    )
    attention = int(
        (
            await db.execute(
                select(func.count(B2BOrder.id)).where(
                    B2BOrder.status.in_(("PENDING_CONFIRMATION", "READY_FOR_PICKUP"))
                )
            )
        ).scalar_one()
    )
    return {
        "pendingOffers": pending_offers,
        "activeOffers": active_offers,
        "inventoryValueKopecks": inventory_value,
        "newOrders": new_orders,
        "gmvKopecks": gmv,
        "markupRevenueKopecks": margin,
        "mrrKopecks": mrr,
        "activeSubscribers": active_subscribers,
        "lowStockOffers": low_stock,
        "ordersRequiringAttention": attention,
    }


@router.get("/offers")
async def admin_offers(
    status: str | None = None,
    search: str | None = Query(None, max_length=200),
    page: int = 1,
    page_size: int = Query(20, alias="pageSize"),
    principal: B2BPrincipal = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    del principal
    offset, limit = page_offset(page, page_size)
    stmt = select(Offer).join(OfferRevision, OfferRevision.offer_id == Offer.id)
    count_stmt = select(func.count(func.distinct(Offer.id))).select_from(Offer).join(
        OfferRevision, OfferRevision.offer_id == Offer.id
    )
    statuses: tuple[str, ...] | None = None
    if status:
        statuses = ("SUBMITTED", "UNDER_REVIEW") if status == "PENDING_MODERATION" else tuple(status.split(","))
        stmt = stmt.where(Offer.status.in_(statuses))
        count_stmt = count_stmt.where(Offer.status.in_(statuses))
    if search:
        pattern = f"%{search.strip()}%"
        stmt = stmt.where(OfferRevision.original_title.ilike(pattern))
        count_stmt = count_stmt.where(OfferRevision.original_title.ilike(pattern))
    stmt = stmt.distinct().order_by(Offer.updated_at.desc()).offset(offset).limit(limit)
    offers = list((await db.execute(stmt)).scalars().all())
    total = int((await db.execute(count_stmt)).scalar_one())
    return {
        "items": [await _admin_offer_dto(db, offer) for offer in offers],
        "total": total,
        "page": page,
        "pageSize": page_size,
    }


@router.post("/offers/{offer_id}/moderate")
async def moderate_offer(
    offer_id: UUID,
    body: ModerationBody,
    request: Request,
    principal: B2BPrincipal = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    offer = (
        await db.execute(select(Offer).where(Offer.id == offer_id).with_for_update())
    ).scalars().first()
    if not offer:
        raise HTTPException(404, "Предложение не найдено")
    if offer.status not in {"SUBMITTED", "UNDER_REVIEW", "CHANGES_REQUESTED"}:
        raise HTTPException(409, "Предложение нельзя модерировать из текущего статуса")
    seller = await db.get(SellerProfile, offer.seller_profile_id)
    if body.decision == "APPROVE" and (not seller or seller.status != "VERIFIED"):
        raise HTTPException(409, "Сначала подтвердите поставщика")
    if body.decision in {"REJECT", "REQUEST_CHANGES"} and not (body.reason or "").strip():
        raise HTTPException(422, "Укажите причину")
    before = offer.status
    offer.status = {
        "APPROVE": "APPROVED",
        "REJECT": "REJECTED",
        "REQUEST_CHANGES": "CHANGES_REQUESTED",
    }[body.decision]
    offer.rejection_reason = None if body.decision == "APPROVE" else body.reason
    offer.reviewed_at = utcnow()
    offer.reviewed_by_user_id = principal.user.id
    await _audit(
        db,
        request,
        principal,
        action=f"OFFER_{body.decision}",
        entity_type="offer",
        entity_id=offer.id,
        reason=body.reason,
        before={"status": before},
        after={"status": offer.status},
    )
    if seller:
        await enqueue_notification(
            db,
            user_id=seller.user_id,
            recipient=seller.user_id,
            event_type=f"OFFER_{offer.status}",
            idempotency_key=f"offer-moderated:{offer.id}:{offer.status}:{offer.version}",
            text=f"Статус предложения изменён: {offer.status}. {body.reason or ''}".strip(),
            bot_scope="SELLER",
            deep_link=f"{get_settings().public_base_url.rstrip('/')}{get_settings().seller_app_path}/offers/{offer.id}",
        )
    await db.flush()
    return await _admin_offer_dto(db, offer)


@router.post("/offers/{offer_id}/pricing")
async def price_offer(
    offer_id: UUID,
    body: PricingBody,
    request: Request,
    principal: B2BPrincipal = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    offer = await db.get(Offer, offer_id)
    if not offer:
        raise HTTPException(404, "Предложение не найдено")
    if offer.status not in {"APPROVED", "UNDER_REVIEW"}:
        raise HTTPException(409, "Сначала одобрите предложение")
    revision = (
        await db.execute(
            select(OfferRevision)
            .where(OfferRevision.offer_id == offer.id)
            .order_by(OfferRevision.revision_number.desc())
            .limit(1)
            .with_for_update()
        )
    ).scalars().one()
    value: Decimal | int | None = {
        "PERCENT": body.markupPercent,
        "FIXED": body.fixedMarkupKopecks,
        "MANUAL": body.manualBuyerUnitPriceKopecks,
    }[body.markupType]
    if value is None:
        raise HTTPException(422, "Не указано значение наценки")
    try:
        snapshot = build_price_snapshot(
            revision.supplier_unit_price_kopecks,
            body.markupType,
            value,
        )
    except PricingError as exc:
        raise HTTPException(422, str(exc)) from exc
    before = {"buyerUnitPriceKopecks": revision.buyer_unit_price_kopecks}
    revision.markup_type = snapshot.markup_type.value
    revision.markup_value = snapshot.markup_value
    revision.buyer_unit_price_kopecks = snapshot.buyer_unit_price_kopecks
    await _audit(
        db,
        request,
        principal,
        action="OFFER_PRICED",
        entity_type="offer",
        entity_id=offer.id,
        before=before,
        after={
            "markupType": revision.markup_type,
            "markupValue": str(revision.markup_value),
            "buyerUnitPriceKopecks": revision.buyer_unit_price_kopecks,
        },
    )
    await db.flush()
    return await _admin_offer_dto(db, offer)


@router.post("/offers/{offer_id}/publish")
async def publish_offer(
    offer_id: UUID,
    request: Request,
    principal: B2BPrincipal = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    offer = (
        await db.execute(select(Offer).where(Offer.id == offer_id).with_for_update())
    ).scalars().first()
    if not offer:
        raise HTTPException(404, "Предложение не найдено")
    if offer.status != "APPROVED":
        raise HTTPException(409, "Можно публиковать только одобренное предложение")
    revision = (
        await db.execute(
            select(OfferRevision)
            .where(OfferRevision.offer_id == offer.id)
            .order_by(OfferRevision.revision_number.desc())
            .limit(1)
            .with_for_update()
        )
    ).scalars().one()
    if revision.buyer_unit_price_kopecks is None or revision.markup_type is None:
        raise HTTPException(409, "Сначала установите наценку")
    image_count = int(
        (
            await db.execute(
                select(func.count(OfferImage.id)).where(OfferImage.revision_id == revision.id)
            )
        ).scalar_one()
    )
    if image_count < 1:
        raise HTTPException(409, "Нельзя публиковать предложение без фото")
    balance = (
        await db.execute(select(InventoryBalance).where(InventoryBalance.offer_id == offer.id))
    ).scalars().one()
    if balance.available_quantity <= 0:
        raise HTTPException(409, "Нет доступного остатка")
    result = await db.execute(select(OfferRevision).where(OfferRevision.offer_id == offer.id))
    for existing in result.scalars().all():
        existing.is_published = existing.id == revision.id
    revision.public_title = revision.public_title or revision.original_title
    revision.public_description = revision.public_description or revision.original_description
    revision.published_at = utcnow()
    offer.status = "PUBLISHED"
    offer.published_at = utcnow()
    offer.publication_starts_at = offer.publication_starts_at or utcnow()
    await _audit(
        db,
        request,
        principal,
        action="OFFER_PUBLISHED",
        entity_type="offer",
        entity_id=offer.id,
    )
    seller = await db.get(SellerProfile, offer.seller_profile_id)
    if seller:
        await enqueue_notification(
            db,
            user_id=seller.user_id,
            recipient=seller.user_id,
            event_type="OFFER_PUBLISHED",
            idempotency_key=f"seller-offer-published:{offer.id}:{revision.id}",
            text=f"Предложение «{revision.public_title}» опубликовано.",
            bot_scope="SELLER",
            deep_link=(
                f"{get_settings().public_base_url.rstrip('/')}"
                f"{get_settings().seller_app_path}/offers/{offer.id}"
            ),
        )
    active_buyers = list(
        (
            await db.execute(
                select(BuyerProfile)
                .join(Subscription, Subscription.buyer_profile_id == BuyerProfile.id)
                .where(
                    Subscription.status.in_(("TRIAL", "ACTIVE", "PAST_DUE")),
                    Subscription.ends_at > utcnow(),
                )
                .distinct()
            )
        ).scalars().all()
    )
    for buyer in active_buyers:
        await enqueue_notification(
            db,
            user_id=buyer.user_id,
            recipient=buyer.user_id,
            event_type="BUYER_NEW_OFFER",
            idempotency_key=f"buyer-new-offer:{offer.id}:{buyer.id}",
            text=f"В каталоге новое предложение: «{revision.public_title}».",
            bot_scope="BUYER",
            deep_link=(
                f"{get_settings().public_base_url.rstrip('/')}"
                f"{get_settings().buyer_app_path}/catalog/{offer.id}"
            ),
        )
    await db.flush()
    return await _admin_offer_dto(db, offer)


@router.post("/offers/{offer_id}/pause")
async def pause_offer(
    offer_id: UUID,
    request: Request,
    principal: B2BPrincipal = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    offer = await db.get(Offer, offer_id)
    if not offer or offer.status != "PUBLISHED":
        raise HTTPException(409, "Опубликованное предложение не найдено")
    offer.status = "PAUSED"
    await _audit(db, request, principal, action="OFFER_PAUSED", entity_type="offer", entity_id=offer.id)
    return await _admin_offer_dto(db, offer)


def _simple(title: str, subtitle: str | None, status: str, entity_id: object, *, amount: int | None = None, created=None) -> dict:
    return {
        "id": str(entity_id),
        "title": title,
        "subtitle": subtitle,
        "status": status,
        "amountKopecks": amount,
        "createdAt": created,
    }


@router.get("/sellers")
async def sellers(
    page: int = 1,
    page_size: int = Query(20, alias="pageSize"),
    search: str | None = Query(None, max_length=200),
    principal: B2BPrincipal = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    del principal
    offset, limit = page_offset(page, page_size)
    stmt = select(SellerProfile)
    count_stmt = select(func.count(SellerProfile.id))
    if search:
        pattern = f"%{search.strip()}%"
        criterion = or_(SellerProfile.company_name.ilike(pattern), SellerProfile.inn.ilike(pattern))
        stmt, count_stmt = stmt.where(criterion), count_stmt.where(criterion)
    rows = list((await db.execute(stmt.order_by(SellerProfile.created_at.desc()).offset(offset).limit(limit))).scalars().all())
    total = int((await db.execute(count_stmt)).scalar_one())
    return {
        "items": [_simple(row.company_name, row.contact_name, row.status, row.id, created=row.created_at) for row in rows],
        "total": total,
        "page": page,
        "pageSize": page_size,
    }


@router.post("/sellers/{seller_id}/status")
async def set_seller_status(
    seller_id: UUID,
    body: SellerStatusBody,
    request: Request,
    principal: B2BPrincipal = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    seller = await db.get(SellerProfile, seller_id)
    if not seller:
        raise HTTPException(404, "Поставщик не найден")
    before = seller.status
    seller.status = body.status
    seller.admin_comment = body.reason
    seller.verified_at = utcnow() if body.status == "VERIFIED" else seller.verified_at
    await _audit(
        db,
        request,
        principal,
        action="SELLER_STATUS_CHANGED",
        entity_type="seller_profile",
        entity_id=seller.id,
        reason=body.reason,
        before={"status": before},
        after={"status": body.status},
    )
    return _simple(seller.company_name, seller.contact_name, seller.status, seller.id)


@router.get("/buyers")
async def buyers(
    page: int = 1,
    page_size: int = Query(20, alias="pageSize"),
    search: str | None = Query(None, max_length=200),
    principal: B2BPrincipal = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    del principal
    offset, limit = page_offset(page, page_size)
    stmt = select(BuyerProfile)
    count_stmt = select(func.count(BuyerProfile.id))
    if search:
        pattern = f"%{search.strip()}%"
        criterion = or_(BuyerProfile.company_name.ilike(pattern), BuyerProfile.inn.ilike(pattern))
        stmt, count_stmt = stmt.where(criterion), count_stmt.where(criterion)
    rows = list((await db.execute(stmt.order_by(BuyerProfile.created_at.desc()).offset(offset).limit(limit))).scalars().all())
    total = int((await db.execute(count_stmt)).scalar_one())
    return {
        "items": [_simple(row.company_name or f"Покупатель {row.id}", row.contact_name, row.status, row.id, created=row.created_at) for row in rows],
        "total": total,
        "page": page,
        "pageSize": page_size,
    }


@router.post(
    "/invites",
    status_code=201,
    dependencies=[Depends(rate_limit("admin-invite-create", requests=60, seconds=60))],
)
async def create_invite(
    body: InviteBody,
    request: Request,
    principal: B2BPrincipal = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    settings = get_settings()
    if not settings.b2b_buyer_bot_username:
        raise HTTPException(503, "BUYER_BOT_USERNAME не настроен")
    plan = await db.get(SubscriptionPlan, body.planId) if body.planId else None
    if body.planId and not plan:
        raise HTTPException(404, "Тариф не найден")
    raw, token_hash = issue_invite_token()
    invite = InviteLink(
        token_hash=token_hash,
        status="ACTIVE",
        created_by_user_id=principal.user.id,
        plan_id=plan.id if plan else None,
        expires_at=utcnow() + timedelta(days=body.expiresInDays),
        max_uses=body.maxUses,
        use_count=0,
        trial_days=body.trialDays,
        source=body.source,
        manager_label=body.label,
    )
    db.add(invite)
    await db.flush()
    await _audit(db, request, principal, action="INVITE_CREATED", entity_type="invite_link", entity_id=invite.id)
    username = settings.b2b_buyer_bot_username.lstrip("@")
    return {
        "id": str(invite.id),
        "token": raw,
        "deepLink": f"https://t.me/{username}?start=invite_{raw}",
        "expiresAt": invite.expires_at,
    }


@router.get("/invites")
async def invites(
    page: int = 1,
    page_size: int = Query(20, alias="pageSize"),
    principal: B2BPrincipal = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    del principal
    offset, limit = page_offset(page, page_size)
    total = int((await db.execute(select(func.count(InviteLink.id)))).scalar_one())
    rows = list((await db.execute(select(InviteLink).order_by(InviteLink.created_at.desc()).offset(offset).limit(limit))).scalars().all())
    return {
        "items": [_simple(row.manager_label or "Приглашение", row.source, row.status, row.id, created=row.created_at) for row in rows],
        "total": total,
        "page": page,
        "pageSize": page_size,
    }


@router.post("/invites/{invite_id}/revoke")
async def revoke_invite(
    invite_id: UUID,
    request: Request,
    principal: B2BPrincipal = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    invite = await db.get(InviteLink, invite_id)
    if not invite:
        raise HTTPException(404, "Приглашение не найдено")
    invite.status = "REVOKED"
    invite.revoked_at = utcnow()
    await _audit(db, request, principal, action="INVITE_REVOKED", entity_type="invite_link", entity_id=invite.id)
    return {"id": str(invite.id), "status": invite.status}


@router.get("/subscriptions")
async def subscriptions(
    page: int = 1,
    page_size: int = Query(20, alias="pageSize"),
    principal: B2BPrincipal = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    del principal
    offset, limit = page_offset(page, page_size)
    total = int((await db.execute(select(func.count(Subscription.id)))).scalar_one())
    rows = list((await db.execute(select(Subscription).order_by(Subscription.created_at.desc()).offset(offset).limit(limit))).scalars().all())
    items = []
    for row in rows:
        buyer = await db.get(BuyerProfile, row.buyer_profile_id)
        plan = await db.get(SubscriptionPlan, row.plan_id)
        items.append(_simple(buyer.company_name or str(buyer.id), plan.name, row.status, row.id, amount=plan.price_kopecks, created=row.created_at))
    return {"items": items, "total": total, "page": page, "pageSize": page_size}


@router.post("/subscriptions/override")
async def override_subscription(
    body: SubscriptionOverrideBody,
    request: Request,
    principal: B2BPrincipal = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    buyer = await db.get(BuyerProfile, body.buyerId)
    if not buyer:
        raise HTTPException(404, "Покупатель не найден")
    plan = await db.get(SubscriptionPlan, body.planId) if body.planId else None
    if not plan:
        plan = (
            await db.execute(select(SubscriptionPlan).where(SubscriptionPlan.is_active.is_(True)).limit(1))
        ).scalars().first()
    if not plan:
        raise HTTPException(409, "Создайте тариф")
    now = utcnow()
    if body.expiresAt.tzinfo is None or body.expiresAt.utcoffset() is None:
        raise HTTPException(422, "Дата окончания должна содержать timezone")
    if body.expiresAt <= now:
        raise HTTPException(422, "Дата окончания должна быть в будущем")
    subscription = Subscription(
        buyer_profile_id=buyer.id,
        plan_id=plan.id,
        status=body.status,
        starts_at=now,
        ends_at=body.expiresAt,
        source="ADMIN_OVERRIDE",
        override_reason=body.reason,
        granted_by_user_id=principal.user.id,
    )
    db.add(subscription)
    buyer.status = "ACTIVE" if body.status in {"ACTIVE", "TRIAL"} else body.status
    await db.flush()
    await _audit(
        db,
        request,
        principal,
        action="SUBSCRIPTION_OVERRIDDEN",
        entity_type="subscription",
        entity_id=subscription.id,
        reason=body.reason,
        after={"status": body.status, "endsAt": body.expiresAt.isoformat()},
    )
    return _simple(buyer.company_name or str(buyer.id), plan.name, subscription.status, subscription.id, amount=plan.price_kopecks)


@router.post("/plans", status_code=201)
async def create_plan(
    body: PlanBody,
    request: Request,
    principal: B2BPrincipal = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    if "SUPERADMIN" not in principal.roles:
        raise HTTPException(403, "Тарифы может менять только SUPERADMIN")
    code = body.code.strip().upper()
    duplicate = (
        await db.execute(select(SubscriptionPlan.id).where(SubscriptionPlan.code == code))
    ).scalar_one_or_none()
    if duplicate:
        raise HTTPException(409, "Тариф с таким кодом уже существует")
    plan = SubscriptionPlan(
        code=code,
        name=body.name,
        description=body.description,
        price_kopecks=body.priceKopecks,
        currency=await runtime_setting(db, "defaultCurrency", get_settings().default_currency),
        duration_days=body.durationDays,
        trial_days=body.trialDays,
        is_active=True,
    )
    db.add(plan)
    await db.flush()
    await _audit(db, request, principal, action="PLAN_CREATED", entity_type="subscription_plan", entity_id=plan.id)
    return {"id": str(plan.id), "code": plan.code, "name": plan.name, "priceKopecks": plan.price_kopecks}


@router.get("/plans")
async def plans(
    active: bool | None = None,
    principal: B2BPrincipal = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    del principal
    stmt = select(SubscriptionPlan).order_by(SubscriptionPlan.created_at.desc())
    if active is not None:
        stmt = stmt.where(SubscriptionPlan.is_active.is_(active))
    rows = list((await db.execute(stmt)).scalars().all())
    return {
        "items": [
            {
                "id": str(plan.id),
                "code": plan.code,
                "name": plan.name,
                "description": plan.description,
                "priceKopecks": plan.price_kopecks,
                "currency": plan.currency,
                "durationDays": plan.duration_days,
                "trialDays": plan.trial_days,
                "isActive": plan.is_active,
                "createdAt": plan.created_at,
            }
            for plan in rows
        ]
    }


@router.patch("/plans/{plan_id}")
async def update_plan(
    plan_id: UUID,
    body: PlanPatch,
    request: Request,
    principal: B2BPrincipal = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    if "SUPERADMIN" not in principal.roles:
        raise HTTPException(403, "Тарифы может менять только SUPERADMIN")
    plan = await db.get(SubscriptionPlan, plan_id)
    if not plan:
        raise HTTPException(404, "Тариф не найден")
    values = body.model_dump(exclude_unset=True, exclude_none=True)
    if not values:
        raise HTTPException(422, "Не переданы изменения тарифа")
    before = {
        "code": plan.code,
        "name": plan.name,
        "priceKopecks": plan.price_kopecks,
        "durationDays": plan.duration_days,
        "trialDays": plan.trial_days,
        "isActive": plan.is_active,
    }
    if "code" in values:
        code = str(values["code"]).strip().upper()
        duplicate = (
            await db.execute(
                select(SubscriptionPlan.id).where(
                    SubscriptionPlan.code == code,
                    SubscriptionPlan.id != plan.id,
                )
            )
        ).scalar_one_or_none()
        if duplicate:
            raise HTTPException(409, "Тариф с таким кодом уже существует")
        plan.code = code
    field_map = {
        "name": "name",
        "description": "description",
        "priceKopecks": "price_kopecks",
        "durationDays": "duration_days",
        "trialDays": "trial_days",
        "isActive": "is_active",
    }
    for external, internal in field_map.items():
        if external in values:
            setattr(plan, internal, values[external])
    await _audit(
        db,
        request,
        principal,
        action="PLAN_UPDATED",
        entity_type="subscription_plan",
        entity_id=plan.id,
        before=before,
        after=body.model_dump(exclude_unset=True),
    )
    await db.flush()
    return {
        "id": str(plan.id),
        "code": plan.code,
        "name": plan.name,
        "description": plan.description,
        "priceKopecks": plan.price_kopecks,
        "currency": plan.currency,
        "durationDays": plan.duration_days,
        "trialDays": plan.trial_days,
        "isActive": plan.is_active,
    }


@router.get("/orders")
async def orders(
    page: int = 1,
    page_size: int = Query(20, alias="pageSize"),
    search: str | None = Query(None, max_length=100),
    principal: B2BPrincipal = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    del principal
    offset, limit = page_offset(page, page_size)
    stmt = select(B2BOrder)
    count_stmt = select(func.count(B2BOrder.id))
    if search:
        criterion = B2BOrder.order_number.ilike(f"%{search.strip()}%")
        stmt, count_stmt = stmt.where(criterion), count_stmt.where(criterion)
    rows = list((await db.execute(stmt.order_by(B2BOrder.created_at.desc()).offset(offset).limit(limit))).scalars().all())
    total = int((await db.execute(count_stmt)).scalar_one())
    return {
        "items": [_simple(row.order_number, row.delivery_address_snapshot, row.status, row.id, amount=row.total_kopecks, created=row.created_at) for row in rows],
        "total": total,
        "page": page,
        "pageSize": page_size,
    }


@router.post("/orders/{order_id}/transition")
async def admin_transition_order(
    order_id: UUID,
    body: TransitionBody,
    request: Request,
    principal: B2BPrincipal = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    order = (
        await db.execute(select(B2BOrder).where(B2BOrder.id == order_id).with_for_update())
    ).scalars().first()
    if not order:
        raise HTTPException(404, "Заказ не найден")
    before = order.status
    if body.status == "COURIER_ASSIGNED":
        has_delivery = int(
            (
                await db.execute(select(func.count(Delivery.id)).where(Delivery.order_id == order.id))
            ).scalar_one()
        )
        if not has_delivery:
            raise HTTPException(409, "Сначала назначьте доставку")
    await transition_order(
        db,
        order,
        body.status,
        actor_user_id=principal.user.id,
        actor_type="ADMIN",
        comment=body.comment,
    )
    await _audit(
        db,
        request,
        principal,
        action="ORDER_STATUS_CHANGED",
        entity_type="order",
        entity_id=order.id,
        reason=body.comment,
        before={"status": before},
        after={"status": order.status},
    )
    return _simple(order.order_number, order.delivery_address_snapshot, order.status, order.id, amount=order.total_kopecks)


@router.post("/deliveries", status_code=201)
async def create_delivery(
    body: DeliveryBody,
    request: Request,
    principal: B2BPrincipal = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    order = (
        await db.execute(select(B2BOrder).where(B2BOrder.id == body.orderId).with_for_update())
    ).scalars().first()
    if not order:
        raise HTTPException(404, "Заказ не найден")
    if order.status != "READY_FOR_PICKUP":
        raise HTTPException(409, "Товар ещё не готов к забору")
    groups = list(
        (
            await db.execute(
                select(OrderFulfillmentGroup).where(OrderFulfillmentGroup.order_id == order.id)
            )
        ).scalars().all()
    )
    if not groups:
        raise HTTPException(409, "В заказе нет fulfillment groups")
    try:
        provider = get_delivery_provider(get_settings().delivery_provider)
    except DeliveryProviderError as exc:
        raise HTTPException(503, "Провайдер доставки не настроен") from exc
    deliveries = []
    for group in groups:
        try:
            assignment = await provider.assign(
                DeliveryRequest(
                    order_number=order.order_number,
                    pickup_address=group.pickup_address_snapshot,
                    delivery_address=order.delivery_address_snapshot,
                    courier_name=body.courierName,
                    courier_contact=body.courierContact,
                    pickup_window=body.pickupWindow,
                    delivery_window=body.deliveryWindow,
                    cost_kopecks=body.costKopecks,
                )
            )
        except DeliveryProviderError as exc:
            raise HTTPException(422, str(exc)) from exc
        delivery = Delivery(
            order_id=order.id,
            fulfillment_group_id=group.id,
            provider=assignment.provider,
            external_delivery_id=assignment.external_delivery_id,
            status=assignment.status,
            pickup_address_snapshot=group.pickup_address_snapshot,
            delivery_address_snapshot=order.delivery_address_snapshot,
            courier_name=assignment.courier_name,
            courier_contact=assignment.courier_contact,
            cost_kopecks=assignment.cost_kopecks,
            internal_notes=assignment.internal_notes,
        )
        db.add(delivery)
        deliveries.append(delivery)
    await db.flush()
    for delivery in deliveries:
        db.add(
            DeliveryStatusHistory(
                delivery_id=delivery.id,
                from_status=None,
                to_status="ASSIGNED",
                actor_user_id=principal.user.id,
                comment=f"Курьер: {body.courierName}",
            )
        )
    for delivery, group in zip(deliveries, groups, strict=True):
        seller = await db.get(SellerProfile, group.seller_profile_id)
        if seller:
            await enqueue_notification(
                db,
                user_id=seller.user_id,
                recipient=seller.user_id,
                event_type="DELIVERY_ASSIGNED",
                idempotency_key=f"seller-delivery-assigned:{delivery.id}",
                text=(
                    f"Для заказа {order.order_number} назначен курьер "
                    f"{body.courierName}. Окно забора: {body.pickupWindow or 'уточняется'}."
                ),
                bot_scope="SELLER",
                deep_link=(
                    f"{get_settings().public_base_url.rstrip('/')}"
                    f"{get_settings().seller_app_path}/orders"
                ),
            )
    buyer = await db.get(BuyerProfile, order.buyer_profile_id)
    if buyer:
        await enqueue_notification(
            db,
            user_id=buyer.user_id,
            recipient=buyer.user_id,
            event_type="ORDER_COURIER_ASSIGNED",
            idempotency_key=f"buyer-order-status:{order.id}:COURIER_ASSIGNED",
            text=f"Заказ {order.order_number}: назначена доставка.",
            bot_scope="BUYER",
            deep_link=(
                f"{get_settings().public_base_url.rstrip('/')}"
                f"{get_settings().buyer_app_path}/orders/{order.id}"
            ),
        )
    await transition_order(
        db,
        order,
        "COURIER_ASSIGNED",
        actor_user_id=principal.user.id,
        actor_type="ADMIN",
        comment=f"Курьер: {body.courierName}",
    )
    await _audit(db, request, principal, action="DELIVERY_ASSIGNED", entity_type="order", entity_id=order.id)
    return {"items": [{"id": str(delivery.id), "status": delivery.status} for delivery in deliveries]}


@router.get("/deliveries")
async def deliveries(
    page: int = 1,
    page_size: int = Query(20, alias="pageSize"),
    principal: B2BPrincipal = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    del principal
    offset, limit = page_offset(page, page_size)
    total = int((await db.execute(select(func.count(Delivery.id)))).scalar_one())
    rows = list((await db.execute(select(Delivery).order_by(Delivery.created_at.desc()).offset(offset).limit(limit))).scalars().all())
    return {
        "items": [_simple(row.courier_name or row.provider, row.delivery_address_snapshot, row.status, row.id, amount=row.cost_kopecks, created=row.created_at) for row in rows],
        "total": total,
        "page": page,
        "pageSize": page_size,
    }


@router.post("/deliveries/{delivery_id}/status")
async def delivery_status(
    delivery_id: UUID,
    body: DeliveryStatusBody,
    request: Request,
    principal: B2BPrincipal = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    delivery = (
        await db.execute(select(Delivery).where(Delivery.id == delivery_id).with_for_update())
    ).scalars().first()
    if not delivery:
        raise HTTPException(404, "Доставка не найдена")
    before = delivery.status
    if body.status == before:
        return _simple(
            delivery.courier_name or delivery.provider,
            delivery.delivery_address_snapshot,
            delivery.status,
            delivery.id,
        )
    allowed_delivery_transitions = {
        "ASSIGNED": {"PICKED_UP", "CANCELED", "FAILED"},
        "PICKED_UP": {"IN_DELIVERY", "CANCELED", "FAILED"},
        "IN_DELIVERY": {"DELIVERED", "CANCELED", "FAILED"},
        "FAILED": {"ASSIGNED", "CANCELED"},
        "DELIVERED": set(),
        "CANCELED": set(),
    }
    if body.status not in allowed_delivery_transitions.get(before, set()):
        raise HTTPException(409, f"Переход доставки {before} → {body.status} запрещён")
    delivery.status = body.status
    now = utcnow()
    if body.status == "PICKED_UP":
        delivery.picked_up_at = now
    if body.status == "DELIVERED":
        delivery.delivered_at = now
    db.add(
        DeliveryStatusHistory(
            delivery_id=delivery.id,
            from_status=before,
            to_status=body.status,
            actor_user_id=principal.user.id,
            comment=body.comment,
        )
    )
    await db.flush()
    order = await db.get(B2BOrder, delivery.order_id, with_for_update=True)
    delivery_statuses = list(
        (
            await db.execute(select(Delivery.status).where(Delivery.order_id == order.id))
        ).scalars().all()
    )
    parent_transitions: list[str] = []
    if order.status == "COURIER_ASSIGNED" and all(
        status in {"PICKED_UP", "IN_DELIVERY", "DELIVERED"}
        for status in delivery_statuses
    ):
        parent_transitions.append("PICKED_UP")
    effective_status = parent_transitions[-1] if parent_transitions else order.status
    if effective_status == "PICKED_UP" and all(
        status in {"IN_DELIVERY", "DELIVERED"} for status in delivery_statuses
    ):
        parent_transitions.append("IN_DELIVERY")
    effective_status = parent_transitions[-1] if parent_transitions else order.status
    if effective_status == "IN_DELIVERY" and all(
        status == "DELIVERED" for status in delivery_statuses
    ):
        parent_transitions.append("DELIVERED")
    for target in parent_transitions:
        await transition_order(
            db,
            order,
            target,
            actor_user_id=principal.user.id,
            actor_type="ADMIN",
            comment=body.comment,
        )
        buyer = await db.get(BuyerProfile, order.buyer_profile_id)
        if buyer:
            await enqueue_notification(
                db,
                user_id=buyer.user_id,
                recipient=buyer.user_id,
                event_type=f"ORDER_{target}",
                idempotency_key=f"buyer-order-status:{order.id}:{target}",
                text=f"Заказ {order.order_number}: новый статус {target}.",
                bot_scope="BUYER",
                deep_link=(
                    f"{get_settings().public_base_url.rstrip('/')}"
                    f"{get_settings().buyer_app_path}/orders/{order.id}"
                ),
            )
    await _audit(
        db,
        request,
        principal,
        action="DELIVERY_STATUS_CHANGED",
        entity_type="delivery",
        entity_id=delivery.id,
        reason=body.comment,
        before={"status": before},
        after={"status": body.status},
    )
    group = await db.get(OrderFulfillmentGroup, delivery.fulfillment_group_id)
    seller = await db.get(SellerProfile, group.seller_profile_id) if group else None
    if seller:
        await enqueue_notification(
            db,
            user_id=seller.user_id,
            recipient=seller.user_id,
            event_type=f"DELIVERY_{body.status}",
            idempotency_key=f"seller-delivery-status:{delivery.id}:{body.status}",
            text=f"Доставка заказа {order.order_number}: статус {body.status}.",
            bot_scope="SELLER",
            deep_link=(
                f"{get_settings().public_base_url.rstrip('/')}"
                f"{get_settings().seller_app_path}/orders"
            ),
        )
    return _simple(delivery.courier_name or delivery.provider, delivery.delivery_address_snapshot, delivery.status, delivery.id)


async def _generic_admin_list(db: AsyncSession, model, *, page: int, page_size: int, mapper):
    offset, limit = page_offset(page, page_size)
    total = int((await db.execute(select(func.count(model.id)))).scalar_one())
    rows = list((await db.execute(select(model).order_by(model.created_at.desc()).offset(offset).limit(limit))).scalars().all())
    return {"items": [mapper(row) for row in rows], "total": total, "page": page, "pageSize": page_size}


@router.get("/notifications")
async def notifications(
    page: int = 1,
    page_size: int = Query(20, alias="pageSize"),
    principal: B2BPrincipal = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    del principal
    return await _generic_admin_list(
        db,
        Notification,
        page=page,
        page_size=page_size,
        mapper=lambda row: _simple(row.event_type, row.recipient, row.status, row.id, created=row.created_at),
    )


@router.post("/notifications/{notification_id}/retry")
async def retry_notification(
    notification_id: UUID,
    request: Request,
    principal: B2BPrincipal = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    notification = await db.get(Notification, notification_id)
    if not notification or notification.status not in {"FAILED", "RETRY"}:
        raise HTTPException(409, "Уведомление недоступно для повтора")
    notification.status = "RETRY"
    notification.attempt_count = 0
    notification.next_attempt_at = utcnow()
    notification.final_error = None
    await _audit(db, request, principal, action="NOTIFICATION_RETRIED", entity_type="notification", entity_id=notification.id)
    return {"id": str(notification.id), "status": notification.status}


@router.get("/audit")
async def audit_log(
    page: int = 1,
    page_size: int = Query(20, alias="pageSize"),
    principal: B2BPrincipal = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    del principal
    return await _generic_admin_list(
        db,
        AuditLog,
        page=page,
        page_size=page_size,
        mapper=lambda row: _simple(row.action, f"{row.entity_type}:{row.entity_id}", "RECORDED", row.id, created=row.created_at),
    )


@router.get("/settings")
async def settings(
    principal: B2BPrincipal = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    del principal
    rows = list((await db.execute(select(SystemSetting))).scalars().all())
    configured = {
        "appName": get_settings().b2b_app_name,
        "catalogAccessPolicy": get_settings().catalog_access_policy,
        "reservationTtlMinutes": get_settings().reservation_ttl_minutes,
        "subscriptionGracePeriodDays": get_settings().subscription_grace_period_days,
        "defaultCurrency": get_settings().default_currency,
        "timezone": get_settings().app_timezone,
    }
    configured.update({row.key: row.value.get("value") for row in rows})
    return configured


@router.patch("/settings")
async def update_settings(
    body: SettingsPatch,
    request: Request,
    principal: B2BPrincipal = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    if "SUPERADMIN" not in principal.roles:
        raise HTTPException(403, "Настройки может менять только SUPERADMIN")
    values = body.model_dump(exclude_unset=True, exclude_none=True)
    if not values:
        raise HTTPException(422, "Не передано ни одной настройки")
    for key, value in values.items():
        setting = (
            await db.execute(select(SystemSetting).where(SystemSetting.key == key))
        ).scalars().first()
        if not setting:
            setting = SystemSetting(key=key, value={"value": value}, updated_by_user_id=principal.user.id)
            db.add(setting)
        else:
            setting.value = {"value": value}
            setting.updated_by_user_id = principal.user.id
        await _audit(db, request, principal, action="SETTING_CHANGED", entity_type="system_setting", entity_id=key, after={"value": value})
    await db.flush()
    return await settings(principal, db)
