from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.deps.b2b import B2BPrincipal, require_seller, seller_profile_for
from app.models.b2b import (
    AuditLog,
    B2BCategory,
    B2BOrder,
    B2BOrderItem,
    BuyerProfile,
    InventoryBalance,
    InventoryMovement,
    Offer,
    OfferImage,
    OfferRevision,
    OrderFulfillmentGroup,
    SellerProfile,
)
from app.services.b2b_common import page_offset, utcnow
from app.services.b2b_images import store_offer_image
from app.services.b2b_inventory import InventoryError, to_quantity, validate_order_quantity
from app.services.b2b_notifications import enqueue_notification
from app.services.b2b_orders import transition_order
from app.services.phone_norm import normalize_phone_to_storage


router = APIRouter(prefix="/api/seller", tags=["b2b-seller"])


class StrictBody(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SellerProfilePatch(StrictBody):
    companyName: str | None = Field(default=None, max_length=250)
    companyType: str | None = Field(default=None, max_length=32)
    inn: str | None = Field(default=None, max_length=20)
    contactName: str | None = Field(default=None, max_length=200)
    phone: str | None = Field(default=None, max_length=32)
    pickupAddress: str | None = Field(default=None, max_length=2000)
    pickupHours: str | None = Field(default=None, max_length=250)


class SellerOfferBody(StrictBody):
    name: str | None = Field(default=None, min_length=2, max_length=300)
    description: str | None = Field(default=None, max_length=10_000)
    category: str | None = Field(default=None, max_length=200)
    procurementUnitPriceKopecks: int | None = Field(default=None, ge=0)
    currency: str | None = Field(default="RUB", min_length=3, max_length=3)
    unit: str | None = Field(default=None, max_length=32)
    packageSize: Decimal | str | None = None
    totalQuantity: Decimal | None = Field(default=None, gt=0)
    minimumQuantity: Decimal | None = Field(default=None, gt=0)
    quantityStep: Decimal | None = Field(default=None, gt=0)
    shelfLife: str | None = Field(default=None, max_length=100)
    storageConditions: str | None = Field(default=None, max_length=2000)
    expiresAt: str | None = Field(default=None, max_length=100)


def _profile_dto(profile: SellerProfile) -> dict:
    return {
        "id": str(profile.id),
        "companyName": profile.company_name,
        "inn": profile.inn,
        "contactName": profile.contact_name or "",
        "phone": profile.phone or "",
        "pickupAddress": profile.pickup_address or "",
        "verificationStatus": profile.status,
        "rejectionReason": profile.admin_comment if profile.status in {"SUSPENDED", "BLOCKED"} else None,
    }


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    raw = value.strip()[:10]
    try:
        return date.fromisoformat(raw)
    except ValueError as exc:
        raise HTTPException(422, "Дата должна быть в формате YYYY-MM-DD") from exc


async def _category(db: AsyncSession, value: str | None) -> B2BCategory:
    if not value:
        raise HTTPException(422, "Категория обязательна")
    category = None
    try:
        category = await db.get(B2BCategory, UUID(value))
    except ValueError:
        category = (
            await db.execute(
                select(B2BCategory).where(
                    (B2BCategory.slug == value) | (B2BCategory.name == value),
                    B2BCategory.is_active.is_(True),
                )
            )
        ).scalars().first()
    if not category or not category.is_active:
        raise HTTPException(422, "Категория не найдена")
    return category


async def _latest_revision(db: AsyncSession, offer_id: UUID) -> OfferRevision | None:
    return (
        await db.execute(
            select(OfferRevision)
            .where(OfferRevision.offer_id == offer_id)
            .order_by(OfferRevision.revision_number.desc())
            .limit(1)
        )
    ).scalars().first()


async def _offer_dto(db: AsyncSession, offer: Offer) -> dict:
    revision = await _latest_revision(db, offer.id)
    if not revision:
        raise HTTPException(500, "У предложения отсутствует revision")
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
    # Seller projection intentionally excludes platform markup, margin and buyer price.
    return {
        "id": str(offer.id),
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
    }


@router.get("/me")
async def seller_me(
    principal: B2BPrincipal = Depends(require_seller),
    db: AsyncSession = Depends(get_db),
):
    return _profile_dto(await seller_profile_for(db, principal.user.id))


@router.patch("/me")
async def update_seller_me(
    body: SellerProfilePatch,
    principal: B2BPrincipal = Depends(require_seller),
    db: AsyncSession = Depends(get_db),
):
    profile = await seller_profile_for(db, principal.user.id)
    values = body.model_dump(exclude_unset=True)
    mapping = {
        "companyName": "company_name",
        "companyType": "company_type",
        "inn": "inn",
        "contactName": "contact_name",
        "pickupAddress": "pickup_address",
        "pickupHours": "pickup_hours",
    }
    for key, attribute in mapping.items():
        if key in values:
            setattr(profile, attribute, values[key] or None)
    if "phone" in values:
        phone = normalize_phone_to_storage(values["phone"] or "")
        if not phone:
            raise HTTPException(422, "Некорректный телефон")
        profile.phone = phone
        principal.user.phone = phone
    await db.flush()
    return _profile_dto(profile)


@router.get("/offers")
async def seller_offers(
    page: int = 1,
    page_size: int = Query(20, alias="pageSize"),
    principal: B2BPrincipal = Depends(require_seller),
    db: AsyncSession = Depends(get_db),
):
    profile = await seller_profile_for(db, principal.user.id)
    offset, limit = page_offset(page, page_size)
    total = int(
        (
            await db.execute(
                select(func.count(Offer.id)).where(Offer.seller_profile_id == profile.id)
            )
        ).scalar_one()
    )
    offers = list(
        (
            await db.execute(
                select(Offer)
                .where(Offer.seller_profile_id == profile.id)
                .order_by(Offer.updated_at.desc())
                .offset(offset)
                .limit(limit)
            )
        ).scalars().all()
    )
    return {
        "items": [await _offer_dto(db, offer) for offer in offers],
        "total": total,
        "page": page,
        "pageSize": page_size,
    }


@router.get("/offers/{offer_id}")
async def seller_offer(
    offer_id: UUID,
    principal: B2BPrincipal = Depends(require_seller),
    db: AsyncSession = Depends(get_db),
):
    profile = await seller_profile_for(db, principal.user.id)
    offer = await db.get(Offer, offer_id)
    if not offer or offer.seller_profile_id != profile.id:
        raise HTTPException(404, "Предложение не найдено")
    return await _offer_dto(db, offer)


@router.post("/offers", status_code=201)
async def create_offer(
    body: SellerOfferBody,
    request: Request,
    principal: B2BPrincipal = Depends(require_seller),
    db: AsyncSession = Depends(get_db),
):
    profile = await seller_profile_for(db, principal.user.id)
    if not profile.pickup_address:
        raise HTTPException(422, "Сначала заполните адрес забора в профиле")
    required = {
        "name": body.name,
        "description": body.description,
        "category": body.category,
        "procurementUnitPriceKopecks": body.procurementUnitPriceKopecks,
        "unit": body.unit,
        "totalQuantity": body.totalQuantity,
        "minimumQuantity": body.minimumQuantity,
        "quantityStep": body.quantityStep,
    }
    missing = [key for key, value in required.items() if value is None]
    if missing:
        raise HTTPException(422, f"Не заполнены поля: {', '.join(missing)}")
    category = await _category(db, body.category)
    try:
        total = to_quantity(body.totalQuantity, field="totalQuantity")
        minimum = to_quantity(body.minimumQuantity, field="minimumQuantity")
        step = to_quantity(body.quantityStep, field="quantityStep")
        validate_order_quantity(minimum, minimum, step)
        package_size = to_quantity(body.packageSize or "1", field="packageSize")
    except InventoryError as exc:
        raise HTTPException(422, str(exc)) from exc
    offer = Offer(seller_profile_id=profile.id, status="DRAFT")
    db.add(offer)
    await db.flush()
    expiration = _parse_date(body.expiresAt or body.shelfLife)
    revision = OfferRevision(
        offer_id=offer.id,
        revision_number=1,
        category_id=category.id,
        original_title=body.name,
        original_description=body.description or "",
        supplier_unit_price_kopecks=body.procurementUnitPriceKopecks,
        currency=(body.currency or "RUB").upper(),
        sale_unit=body.unit,
        package_size=package_size,
        proposed_total_quantity=total,
        minimum_order_quantity=minimum,
        quantity_step=step,
        expiration_date=expiration,
        storage_conditions=body.storageConditions,
        pickup_address=profile.pickup_address,
        pickup_hours=profile.pickup_hours,
        created_by_user_id=principal.user.id,
    )
    db.add(revision)
    balance = InventoryBalance(
        offer_id=offer.id,
        total_quantity=total,
        reserved_quantity=Decimal("0"),
        sold_quantity=Decimal("0"),
    )
    db.add(balance)
    await db.flush()
    db.add(
        InventoryMovement(
            inventory_balance_id=balance.id,
            movement_type="INITIAL",
            quantity=total,
            total_after=total,
            reserved_after=Decimal("0"),
            sold_after=Decimal("0"),
            actor_user_id=principal.user.id,
            reason="Initial seller offer quantity",
        )
    )
    db.add(
        AuditLog(
            actor_user_id=principal.user.id,
            action="OFFER_DRAFT_CREATED",
            entity_type="offer",
            entity_id=str(offer.id),
            request_id=getattr(request.state, "request_id", None),
        )
    )
    await db.flush()
    return await _offer_dto(db, offer)


@router.patch("/offers/{offer_id}")
async def update_offer(
    offer_id: UUID,
    body: SellerOfferBody,
    request: Request,
    principal: B2BPrincipal = Depends(require_seller),
    db: AsyncSession = Depends(get_db),
):
    profile = await seller_profile_for(db, principal.user.id)
    offer = (
        await db.execute(select(Offer).where(Offer.id == offer_id).with_for_update())
    ).scalars().first()
    if not offer or offer.seller_profile_id != profile.id:
        raise HTTPException(404, "Предложение не найдено")
    if offer.status not in {"DRAFT", "CHANGES_REQUESTED", "REJECTED"}:
        raise HTTPException(409, "Коммерческие поля отправленного предложения менять нельзя")
    revision = await _latest_revision(db, offer.id)
    if not revision:
        raise HTTPException(500, "Revision не найден")
    values = body.model_dump(exclude_unset=True)
    if "name" in values and values["name"]:
        revision.original_title = values["name"]
    if "description" in values:
        revision.original_description = values["description"] or ""
    if "category" in values:
        revision.category_id = (await _category(db, values["category"])).id
    if "procurementUnitPriceKopecks" in values:
        revision.supplier_unit_price_kopecks = values["procurementUnitPriceKopecks"]
    if "currency" in values and values["currency"]:
        revision.currency = values["currency"].upper()
    if "unit" in values and values["unit"]:
        revision.sale_unit = values["unit"]
    quantity_fields = {
        "packageSize": "package_size",
        "minimumQuantity": "minimum_order_quantity",
        "quantityStep": "quantity_step",
    }
    try:
        for key, attribute in quantity_fields.items():
            if key in values and values[key] is not None:
                setattr(revision, attribute, to_quantity(values[key], field=key))
        validate_order_quantity(
            revision.minimum_order_quantity,
            revision.minimum_order_quantity,
            revision.quantity_step,
        )
    except InventoryError as exc:
        raise HTTPException(422, str(exc)) from exc
    if "totalQuantity" in values and values["totalQuantity"] is not None:
        new_total = to_quantity(values["totalQuantity"], field="totalQuantity")
        balance = (
            await db.execute(
                select(InventoryBalance)
                .where(InventoryBalance.offer_id == offer.id)
                .with_for_update()
            )
        ).scalars().one()
        if new_total < balance.reserved_quantity + balance.sold_quantity:
            raise HTTPException(409, "Новый остаток меньше уже зарезервированного/проданного")
        delta = abs(new_total - balance.total_quantity)
        if delta:
            balance.total_quantity = new_total
            balance.version += 1
            db.add(
                InventoryMovement(
                    inventory_balance_id=balance.id,
                    movement_type="ADJUSTMENT",
                    quantity=delta,
                    total_after=balance.total_quantity,
                    reserved_after=balance.reserved_quantity,
                    sold_after=balance.sold_quantity,
                    actor_user_id=principal.user.id,
                    reason="Seller adjusted draft quantity",
                )
            )
        revision.proposed_total_quantity = new_total
    if "storageConditions" in values:
        revision.storage_conditions = values["storageConditions"]
    if "expiresAt" in values or "shelfLife" in values:
        revision.expiration_date = _parse_date(values.get("expiresAt") or values.get("shelfLife"))
    offer.status = "DRAFT"
    offer.version += 1
    db.add(
        AuditLog(
            actor_user_id=principal.user.id,
            action="OFFER_DRAFT_UPDATED",
            entity_type="offer",
            entity_id=str(offer.id),
            request_id=getattr(request.state, "request_id", None),
        )
    )
    await db.flush()
    return await _offer_dto(db, offer)


@router.post("/offers/{offer_id}/images", status_code=201)
async def upload_offer_image(
    offer_id: UUID,
    file: UploadFile = File(...),
    principal: B2BPrincipal = Depends(require_seller),
    db: AsyncSession = Depends(get_db),
):
    profile = await seller_profile_for(db, principal.user.id)
    offer = await db.get(Offer, offer_id)
    if not offer or offer.seller_profile_id != profile.id:
        raise HTTPException(404, "Предложение не найдено")
    if offer.status not in {"DRAFT", "CHANGES_REQUESTED", "REJECTED"}:
        raise HTTPException(409, "Изображения отправленного предложения менять нельзя")
    revision = await _latest_revision(db, offer.id)
    count = int(
        (
            await db.execute(
                select(func.count(OfferImage.id)).where(OfferImage.revision_id == revision.id)
            )
        ).scalar_one()
    )
    if count >= get_settings().offer_max_images:
        raise HTTPException(409, "Достигнут лимит изображений")
    stored = await store_offer_image(file, offer.id, revision.id)
    image = OfferImage(
        revision_id=revision.id,
        storage_key=stored.storage_key,
        public_url=stored.public_url,
        mime_type=stored.mime_type,
        size_bytes=stored.size_bytes,
        width=stored.width,
        height=stored.height,
        display_order=count,
    )
    db.add(image)
    await db.flush()
    return {"id": str(image.id), "url": image.public_url}


@router.post("/offers/{offer_id}/submit")
async def submit_offer(
    offer_id: UUID,
    request: Request,
    principal: B2BPrincipal = Depends(require_seller),
    db: AsyncSession = Depends(get_db),
):
    profile = await seller_profile_for(db, principal.user.id)
    if profile.status != "VERIFIED":
        raise HTTPException(409, "Поставщик должен пройти проверку администратора")
    offer = (
        await db.execute(select(Offer).where(Offer.id == offer_id).with_for_update())
    ).scalars().first()
    if not offer or offer.seller_profile_id != profile.id:
        raise HTTPException(404, "Предложение не найдено")
    if offer.status not in {"DRAFT", "CHANGES_REQUESTED", "REJECTED"}:
        raise HTTPException(409, "Предложение уже отправлено")
    revision = await _latest_revision(db, offer.id)
    image_count = int(
        (
            await db.execute(
                select(func.count(OfferImage.id)).where(OfferImage.revision_id == revision.id)
            )
        ).scalar_one()
    )
    if image_count < 1:
        raise HTTPException(422, "Добавьте хотя бы одно изображение")
    offer.status = "SUBMITTED"
    offer.submitted_at = utcnow()
    offer.rejection_reason = None
    for admin_id in get_settings().b2b_admin_telegram_ids:
        await enqueue_notification(
            db,
            user_id=None,
            recipient=admin_id,
            event_type="OFFER_SUBMITTED",
            idempotency_key=f"offer-submitted:{offer.id}:{offer.version}:{admin_id}",
            text=f"Новое предложение на модерации: {revision.original_title}",
            bot_scope="ADMIN",
            deep_link=f"{get_settings().public_base_url.rstrip('/')}{get_settings().b2b_admin_app_path}/offers/{offer.id}",
            deep_link_label="Связаться",
            actions=[
                {"label": "Одобрить", "callbackData": f"b2b:approve:{offer.id}"},
                {"label": "Отклонить", "callbackData": f"b2b:reject:{offer.id}"},
                {
                    "label": "Запросить изменения",
                    "callbackData": f"b2b:request_changes:{offer.id}",
                },
            ],
        )
    db.add(
        AuditLog(
            actor_user_id=principal.user.id,
            action="OFFER_SUBMITTED",
            entity_type="offer",
            entity_id=str(offer.id),
            request_id=getattr(request.state, "request_id", None),
        )
    )
    await db.flush()
    return await _offer_dto(db, offer)


@router.post("/offers/{offer_id}/archive")
async def archive_offer(
    offer_id: UUID,
    principal: B2BPrincipal = Depends(require_seller),
    db: AsyncSession = Depends(get_db),
):
    profile = await seller_profile_for(db, principal.user.id)
    offer = await db.get(Offer, offer_id)
    if not offer or offer.seller_profile_id != profile.id:
        raise HTTPException(404, "Предложение не найдено")
    offer.status = "ARCHIVED"
    offer.archived_at = utcnow()
    await db.flush()
    return await _offer_dto(db, offer)


def _seller_order_dto(group: OrderFulfillmentGroup, order: B2BOrder, count: int, quantity: Decimal) -> dict:
    return {
        "id": str(group.id),
        "number": order.order_number,
        "status": group.status,
        "createdAt": order.created_at,
        "itemsCount": count,
        "quantityLabel": str(quantity),
        "pickupWindow": None,
    }


@router.get("/orders")
async def seller_orders(
    page: int = 1,
    page_size: int = Query(20, alias="pageSize"),
    principal: B2BPrincipal = Depends(require_seller),
    db: AsyncSession = Depends(get_db),
):
    profile = await seller_profile_for(db, principal.user.id)
    offset, limit = page_offset(page, page_size)
    total = int(
        (
            await db.execute(
                select(func.count(OrderFulfillmentGroup.id)).where(
                    OrderFulfillmentGroup.seller_profile_id == profile.id
                )
            )
        ).scalar_one()
    )
    groups = list(
        (
            await db.execute(
                select(OrderFulfillmentGroup)
                .where(OrderFulfillmentGroup.seller_profile_id == profile.id)
                .order_by(OrderFulfillmentGroup.created_at.desc())
                .offset(offset)
                .limit(limit)
            )
        ).scalars().all()
    )
    items = []
    for group in groups:
        order = await db.get(B2BOrder, group.order_id)
        count, quantity = (
            await db.execute(
                select(func.count(B2BOrderItem.id), func.coalesce(func.sum(B2BOrderItem.quantity), 0)).where(
                    B2BOrderItem.fulfillment_group_id == group.id
                )
            )
        ).one()
        items.append(_seller_order_dto(group, order, int(count), Decimal(quantity)))
    return {"items": items, "total": total, "page": page, "pageSize": page_size}


async def _seller_group(
    db: AsyncSession,
    group_id: UUID,
    seller_profile_id: UUID,
) -> tuple[OrderFulfillmentGroup, B2BOrder]:
    group = (
        await db.execute(
            select(OrderFulfillmentGroup)
            .where(OrderFulfillmentGroup.id == group_id)
            .with_for_update()
        )
    ).scalars().first()
    if not group or group.seller_profile_id != seller_profile_id:
        raise HTTPException(404, "Заказ поставщика не найден")
    order = (
        await db.execute(select(B2BOrder).where(B2BOrder.id == group.order_id).with_for_update())
    ).scalars().one()
    return group, order


@router.post("/orders/{group_id}/confirm")
async def confirm_seller_order(
    group_id: UUID,
    principal: B2BPrincipal = Depends(require_seller),
    db: AsyncSession = Depends(get_db),
):
    profile = await seller_profile_for(db, principal.user.id)
    group, order = await _seller_group(db, group_id, profile.id)
    if group.status != "PENDING_CONFIRMATION":
        raise HTTPException(409, "Заказ уже подтверждён или недоступен")
    group.status = "CONFIRMED"
    group.seller_confirmed_at = utcnow()
    remaining = int(
        (
            await db.execute(
                select(func.count(OrderFulfillmentGroup.id)).where(
                    OrderFulfillmentGroup.order_id == order.id,
                    OrderFulfillmentGroup.id != group.id,
                    OrderFulfillmentGroup.status.not_in(
                        ("CONFIRMED", "SELLER_PREPARING", "READY_FOR_PICKUP")
                    ),
                )
            )
        ).scalar_one()
    )
    if remaining == 0 and order.status == "PENDING_CONFIRMATION":
        await transition_order(
            db,
            order,
            "CONFIRMED",
            actor_user_id=principal.user.id,
            actor_type="SELLER",
            comment="Все поставщики подтвердили наличие",
        )
    count = int(
        (
            await db.execute(
                select(func.count(B2BOrderItem.id)).where(B2BOrderItem.fulfillment_group_id == group.id)
            )
        ).scalar_one()
    )
    return _seller_order_dto(group, order, count, Decimal("0"))


@router.post("/orders/{group_id}/ready")
async def ready_seller_order(
    group_id: UUID,
    principal: B2BPrincipal = Depends(require_seller),
    db: AsyncSession = Depends(get_db),
):
    profile = await seller_profile_for(db, principal.user.id)
    group, order = await _seller_group(db, group_id, profile.id)
    if group.status not in {"CONFIRMED", "SELLER_PREPARING"}:
        raise HTTPException(409, "Сначала подтвердите наличие")
    group.status = "READY_FOR_PICKUP"
    group.ready_at = utcnow()
    not_ready = int(
        (
            await db.execute(
                select(func.count(OrderFulfillmentGroup.id)).where(
                    OrderFulfillmentGroup.order_id == order.id,
                    OrderFulfillmentGroup.id != group.id,
                    OrderFulfillmentGroup.status != "READY_FOR_PICKUP",
                )
            )
        ).scalar_one()
    )
    if not_ready == 0:
        if order.status == "PENDING_CONFIRMATION":
            await transition_order(
                db,
                order,
                "CONFIRMED",
                actor_user_id=principal.user.id,
                actor_type="SELLER",
                comment="Все поставщики подтвердили наличие",
            )
        if order.status == "CONFIRMED":
            await transition_order(
                db,
                order,
                "SELLER_PREPARING",
                actor_user_id=principal.user.id,
                actor_type="SELLER",
            )
        if order.status == "SELLER_PREPARING":
            await transition_order(
                db,
                order,
                "READY_FOR_PICKUP",
                actor_user_id=principal.user.id,
                actor_type="SELLER",
                comment="Все поставщики отметили готовность",
            )
        buyer = await db.get(BuyerProfile, order.buyer_profile_id)
        if not buyer:
            raise HTTPException(409, "Профиль покупателя заказа не найден")
        await enqueue_notification(
            db,
            user_id=buyer.user_id,
            recipient=buyer.user_id,
            event_type="ORDER_READY_FOR_PICKUP",
            idempotency_key=f"buyer-order-ready:{order.id}",
            text=f"Заказ {order.order_number} готов к передаче курьеру.",
            bot_scope="BUYER",
            deep_link=f"{get_settings().public_base_url.rstrip('/')}{get_settings().buyer_app_path}/orders/{order.id}",
        )
    count = int(
        (
            await db.execute(
                select(func.count(B2BOrderItem.id)).where(B2BOrderItem.fulfillment_group_id == group.id)
            )
        ).scalar_one()
    )
    return _seller_order_dto(group, order, count, Decimal("0"))
