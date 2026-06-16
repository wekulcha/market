from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from app.config import get_settings
from app.database import get_db
from app.deps.superadmin import assert_superadmin
from app.models.order import Order
from app.models.order_position import OrderPosition, OrderPositionUnitWeight
from app.models.user import User
from app.schemas.order import OrderDto
from app.schemas.order_position import (
    OrderFinalWeightsPatchDto,
    OrderPositionDto,
    OrderPositionFinalWeightPatchDto,
)
from app.services.session_auth import get_user_from_bearer
from app.services import staff_access
from app.services.telegram_notifier import notify_user_status_changed
from app.services.telegram_auth import verify_telegram_init_data

router = APIRouter(prefix="/api/v1/order-positions", tags=["order-positions"])


def _to_dto(p: OrderPosition) -> OrderPositionDto:
    unit_weights = sorted(
        getattr(p, "unit_weights", []) or [],
        key=lambda w: w.unit_index,
    )
    final_weights = [w.weight_grams for w in unit_weights]
    if not final_weights and p.final_weight_grams is not None:
        final_weights = [p.final_weight_grams]
    return OrderPositionDto(
        id=p.id, mealId=p.meal_id, orderId=p.order_id,
        mealName=p.meal.name if p.meal else None,
        mealWeight=p.meal.weight if p.meal else None,
        mealRequiresFinalWeight=p.meal.requires_final_weight if p.meal else False,
        quantity=p.quantity, unitPrice=p.unit_price, totalPrice=p.total_price,
        finalWeightGrams=p.final_weight_grams,
        finalWeightGramsList=final_weights,
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
    x_kulcha_internal_secret: str | None = Header(None, alias="X-Market-Internal-Secret"),
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

        settings = get_settings()
        internal_authorized = bool(
            settings.internal_api_secret
            and x_kulcha_internal_secret == settings.internal_api_secret
        )
        bearer_user = await get_user_from_bearer(db, authorization)
        if internal_authorized or (bearer_user and bearer_user.id == order.user_id):
            pass
        else:
            if not x_telegram_init_data:
                raise HTTPException(401, "Telegram init data required")
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
            .options(
                joinedload(OrderPosition.meal),
                joinedload(OrderPosition.order),
                selectinload(OrderPosition.unit_weights),
            )
            .where(OrderPosition.order_id == orderId)
        )
        return [_to_dto(p) for p in result.unique().scalars().all()]

    if mealId is not None:
        await assert_superadmin(db, authorization)
        result = await db.execute(
            select(OrderPosition)
            .options(
                joinedload(OrderPosition.meal),
                joinedload(OrderPosition.order),
                selectinload(OrderPosition.unit_weights),
            )
            .where(OrderPosition.meal_id == mealId)
        )
        return [_to_dto(p) for p in result.unique().scalars().all()]

    await assert_superadmin(db, authorization)
    result = await db.execute(
        select(OrderPosition)
        .options(
            joinedload(OrderPosition.meal),
            joinedload(OrderPosition.order),
            selectinload(OrderPosition.unit_weights),
        )
    )
    return [_to_dto(p) for p in result.unique().scalars().all()]


@router.get("/{pos_id}")
async def get_by_id(pos_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(OrderPosition)
        .options(selectinload(OrderPosition.unit_weights))
        .where(OrderPosition.id == pos_id)
    )
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


async def _resolve_actor_name(
    db: AsyncSession,
    restaurant_id: int,
    x_telegram_init_data: str | None,
    x_kulcha_internal_secret: str | None,
    x_kulcha_actor_name: str | None,
) -> str | None:
    settings = get_settings()
    if settings.internal_api_secret and x_kulcha_internal_secret == settings.internal_api_secret:
        return x_kulcha_actor_name
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
    await staff_access.require_restaurant_staff(db, actor.id, restaurant_id)
    return f"@{actor.username}" if actor.username else f"id:{actor.id}"


def _validate_weight_grams(grams: int) -> None:
    if grams <= 0 or grams > 100_000:
        raise HTTPException(400, "Укажите финальный вес в граммах")


async def _save_position_unit_weights(
    db: AsyncSession,
    position: OrderPosition,
    weights: list[int],
) -> None:
    if not position.meal or not position.meal.requires_final_weight:
        raise HTTPException(400, "Для этой позиции финальный вес не требуется")
    if len(weights) != position.quantity:
        raise HTTPException(
            400,
            f"Для позиции {position.id} нужно указать {position.quantity} значений веса",
        )
    for grams in weights:
        _validate_weight_grams(grams)

    await db.execute(
        delete(OrderPositionUnitWeight).where(
            OrderPositionUnitWeight.order_position_id == position.id
        )
    )
    total_weight = sum(weights)
    position.final_weight_grams = total_weight
    position.total_price = (
        position.unit_price * Decimal(total_weight) / Decimal("1000")
    ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    for idx, grams in enumerate(weights, start=1):
        db.add(
            OrderPositionUnitWeight(
                order_position_id=position.id,
                unit_index=idx,
                weight_grams=grams,
            )
        )


async def _recalculate_order_totals(db: AsyncSession, order: Order) -> None:
    positions_result = await db.execute(
        select(OrderPosition).where(OrderPosition.order_id == order.id)
    )
    positions = positions_result.scalars().all()
    order.items_total = sum((p.total_price for p in positions), Decimal("0"))
    order.total = order.items_total + order.delivery_fee + order.service_fee


@router.patch("/orders/{order_id}/final-weights", response_model=OrderDto)
async def set_order_final_weights(
    order_id: int,
    dto: OrderFinalWeightsPatchDto,
    db: AsyncSession = Depends(get_db),
    x_telegram_init_data: str | None = Header(None, alias="X-Telegram-Init-Data"),
    x_kulcha_internal_secret: str | None = Header(None, alias="X-Market-Internal-Secret"),
    x_kulcha_actor_name: str | None = Header(None, alias="X-Market-Actor-Name"),
):
    result = await db.execute(
        select(Order)
        .options(joinedload(Order.user), joinedload(Order.restaurant))
        .where(Order.id == order_id)
    )
    order = result.unique().scalars().first()
    if not order:
        raise HTTPException(404, "Order not found")

    actor_name = await _resolve_actor_name(
        db,
        order.restaurant_id,
        x_telegram_init_data,
        x_kulcha_internal_secret,
        x_kulcha_actor_name,
    )

    positions_result = await db.execute(
        select(OrderPosition)
        .options(joinedload(OrderPosition.meal), selectinload(OrderPosition.unit_weights))
        .where(OrderPosition.order_id == order_id)
    )
    positions_by_id = {p.id: p for p in positions_result.unique().scalars().all()}
    if not dto.positions:
        raise HTTPException(400, "Нет позиций для сохранения")

    for item in dto.positions:
        position = positions_by_id.get(item.positionId)
        if not position:
            raise HTTPException(404, f"Позиция {item.positionId} не найдена")
        await _save_position_unit_weights(db, position, item.finalWeightGramsList)

    await _recalculate_order_totals(db, order)
    await db.flush()
    await notify_user_status_changed(db, order.id, admin_actor=actor_name)
    return _order_to_dto(order)


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

    actor_name = await _resolve_actor_name(
        db,
        position.order.restaurant_id,
        x_telegram_init_data,
        x_kulcha_internal_secret,
        x_kulcha_actor_name,
    )

    grams = dto.finalWeightGrams
    if grams is not None:
        _validate_weight_grams(grams)

    position.final_weight_grams = grams
    await db.execute(
        delete(OrderPositionUnitWeight).where(
            OrderPositionUnitWeight.order_position_id == position.id
        )
    )
    if grams is None:
        position.total_price = position.unit_price * position.quantity
    else:
        position.total_price = (
            position.unit_price * Decimal(grams) / Decimal("1000")
        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        db.add(
            OrderPositionUnitWeight(
                order_position_id=position.id,
                unit_index=1,
                weight_grams=grams,
            )
        )

    order = position.order
    await _recalculate_order_totals(db, order)
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
