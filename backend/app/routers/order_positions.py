from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.config import get_settings
from app.database import get_db
from app.deps.superadmin import assert_superadmin
from app.models.order import Order
from app.models.order_position import OrderPosition
from app.models.user import User
from app.schemas.order import OrderDto
from app.schemas.order_position import OrderPositionDto, OrderPositionFinalWeightPatchDto
from app.services.session_auth import get_user_from_bearer
from app.services import staff_access
from app.services.telegram_notifier import notify_user_status_changed
from app.services.telegram_auth import verify_telegram_init_data

router = APIRouter(prefix="/api/v1/order-positions", tags=["order-positions"])


def _to_dto(p: OrderPosition) -> OrderPositionDto:
    return OrderPositionDto(
        id=p.id, mealId=p.meal_id, orderId=p.order_id,
        mealName=p.meal.name if p.meal else None,
        mealWeight=p.meal.weight if p.meal else None,
        mealRequiresFinalWeight=p.meal.requires_final_weight if p.meal else False,
        quantity=p.quantity, unitPrice=p.unit_price, totalPrice=p.total_price,
        finalWeightGrams=p.final_weight_grams,
    )


def _order_to_dto(order: Order) -> OrderDto:
    return OrderDto(
        id=order.id,
        status=order.status.value,
        userId=order.user_id,
        deliveryAddress=order.delivery_address,
        tableNumber=order.table_number,
        comment=order.comment,
        restaurantId=order.restaurant_id,
        createdAt=order.created_at,
        updatedAt=order.updated_at,
        courierId=order.courier_id,
        orderType=order.order_type.value,
        itemsTotal=order.items_total,
        deliveryFee=order.delivery_fee,
        serviceFee=order.service_fee,
        total=order.total,
        isPaid=order.is_paid,
    )


def _require_internal(secret: str | None) -> None:
    settings = get_settings()
    if not settings.internal_api_secret:
        raise HTTPException(503, "Internal API secret is not configured")
    if not secret or secret != settings.internal_api_secret:
        raise HTTPException(401, "Invalid internal secret")


@router.get("")
async def get_all(
    orderId: int | None = None,
    mealId: int | None = None,
    db: AsyncSession = Depends(get_db),
    x_telegram_init_data: str | None = Header(None, alias="X-Telegram-Init-Data"),
    authorization: str | None = Header(None, alias="Authorization"),
):
    if orderId is not None:
        result = await db.execute(
            select(Order)
            .options(joinedload(Order.restaurant))
            .where(Order.id == orderId)
        )
        order = result.unique().scalars().first()
        if not order:
            raise HTTPException(404, "Order not found")

        bearer_user = await get_user_from_bearer(db, authorization)
        if bearer_user and bearer_user.id == order.user_id:
            pass
        else:
            if not x_telegram_init_data:
                raise HTTPException(401, "Telegram init data required")
            settings = get_settings()
            tg = verify_telegram_init_data(x_telegram_init_data, settings.admin_bot_token)
            if not tg:
                raise HTTPException(401, "Invalid Telegram init data")
            result = await db.execute(select(User).where(User.id == tg["id"]))
            u = result.scalars().first()
            if not u:
                raise HTTPException(403, "Unknown user")
            await staff_access.require_restaurant_staff(db, u.id, order.restaurant_id)

        result = await db.execute(
            select(OrderPosition)
            .options(joinedload(OrderPosition.meal), joinedload(OrderPosition.order))
            .where(OrderPosition.order_id == orderId)
        )
        return [_to_dto(p) for p in result.unique().scalars().all()]

    if mealId is not None:
        await assert_superadmin(db, authorization)
        result = await db.execute(
            select(OrderPosition)
            .options(joinedload(OrderPosition.meal), joinedload(OrderPosition.order))
            .where(OrderPosition.meal_id == mealId)
        )
        return [_to_dto(p) for p in result.unique().scalars().all()]

    await assert_superadmin(db, authorization)
    result = await db.execute(
        select(OrderPosition)
        .options(joinedload(OrderPosition.meal), joinedload(OrderPosition.order))
    )
    return [_to_dto(p) for p in result.unique().scalars().all()]


@router.get("/{pos_id}")
async def get_by_id(pos_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(OrderPosition).where(OrderPosition.id == pos_id))
    p = result.scalars().first()
    if not p:
        raise HTTPException(404, "Order position not found")
    return _to_dto(p)


@router.post("", status_code=201)
async def create_position(
    dto: OrderPositionDto,
    db: AsyncSession = Depends(get_db),
    x_kulcha_internal_secret: str = Header(..., alias="X-Market-Internal-Secret"),
):
    _require_internal(x_kulcha_internal_secret)
    pos = OrderPosition(
        meal_id=dto.mealId, order_id=dto.orderId,
        quantity=dto.quantity, unit_price=dto.unitPrice, total_price=dto.totalPrice,
    )
    db.add(pos)
    await db.flush()
    return _to_dto(pos)


@router.put("/{pos_id}")
async def update_position(
    pos_id: int,
    dto: OrderPositionDto,
    db: AsyncSession = Depends(get_db),
    x_kulcha_internal_secret: str = Header(..., alias="X-Market-Internal-Secret"),
):
    _require_internal(x_kulcha_internal_secret)
    result = await db.execute(select(OrderPosition).where(OrderPosition.id == pos_id))
    existing = result.scalars().first()
    if not existing:
        raise HTTPException(404, "Order position not found")
    if dto.mealId is not None:
        existing.meal_id = dto.mealId
    if dto.orderId is not None:
        existing.order_id = dto.orderId
    if dto.quantity is not None:
        existing.quantity = dto.quantity
    if dto.unitPrice is not None:
        existing.unit_price = dto.unitPrice
    if dto.totalPrice is not None:
        existing.total_price = dto.totalPrice
    if dto.finalWeightGrams is not None:
        existing.final_weight_grams = dto.finalWeightGrams
    await db.flush()
    return _to_dto(existing)


@router.patch("/{pos_id}/final-weight", response_model=OrderDto)
async def set_final_weight(
    pos_id: int,
    dto: OrderPositionFinalWeightPatchDto,
    db: AsyncSession = Depends(get_db),
    x_telegram_init_data: str | None = Header(None, alias="X-Telegram-Init-Data"),
    x_kulcha_internal_secret: str | None = Header(None, alias="X-Market-Internal-Secret"),
    x_kulcha_actor_name: str | None = Header(None, alias="X-Market-Actor-Name"),
):
    result = await db.execute(
        select(OrderPosition)
        .options(
            joinedload(OrderPosition.meal),
            joinedload(OrderPosition.order).joinedload(Order.user),
            joinedload(OrderPosition.order).joinedload(Order.restaurant),
        )
        .where(OrderPosition.id == pos_id)
    )
    position = result.unique().scalars().first()
    if not position:
        raise HTTPException(404, "Order position not found")
    if not position.meal or not position.meal.requires_final_weight:
        raise HTTPException(400, "Для этой позиции финальный вес не требуется")

    settings = get_settings()
    if settings.internal_api_secret and x_kulcha_internal_secret == settings.internal_api_secret:
        actor_name = x_kulcha_actor_name
    else:
        if not x_telegram_init_data:
            raise HTTPException(401, "X-Telegram-Init-Data is required")
        tg = verify_telegram_init_data(x_telegram_init_data, settings.admin_bot_token)
        if not tg:
            raise HTTPException(401, "Invalid Telegram init data")
        user_id = int(tg["id"])
        result = await db.execute(select(User).where(User.id == user_id))
        actor = result.scalars().first()
        if not actor:
            raise HTTPException(403, "Unknown user")
        await staff_access.require_restaurant_staff(db, actor.id, position.order.restaurant_id)
        actor_name = f"@{actor.username}" if actor.username else f"id:{actor.id}"

    grams = dto.finalWeightGrams
    if grams is not None and (grams <= 0 or grams > 100_000):
        raise HTTPException(400, "Укажите финальный вес в граммах")

    position.final_weight_grams = grams
    if grams is None:
        position.total_price = position.unit_price * position.quantity
    else:
        position.total_price = (
            position.unit_price * Decimal(grams) / Decimal("1000")
        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    order = position.order
    positions_result = await db.execute(
        select(OrderPosition).where(OrderPosition.order_id == order.id)
    )
    positions = positions_result.scalars().all()
    order.items_total = sum((p.total_price for p in positions), Decimal("0"))
    order.total = order.items_total + order.delivery_fee + order.service_fee
    await db.flush()
    await notify_user_status_changed(db, order.id, admin_actor=actor_name)
    return _order_to_dto(order)


@router.delete("/{pos_id}", status_code=204)
async def delete_position(
    pos_id: int,
    db: AsyncSession = Depends(get_db),
    x_kulcha_internal_secret: str = Header(..., alias="X-Market-Internal-Secret"),
):
    _require_internal(x_kulcha_internal_secret)
    result = await db.execute(select(OrderPosition).where(OrderPosition.id == pos_id))
    p = result.scalars().first()
    if p:
        await db.delete(p)
