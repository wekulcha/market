from __future__ import annotations

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
from app.schemas.order_position import OrderPositionDto
from app.services.session_auth import get_user_from_bearer
from app.services import staff_access
from app.services.telegram_auth import verify_telegram_init_data

router = APIRouter(prefix="/api/v1/order-positions", tags=["order-positions"])


def _to_dto(p: OrderPosition) -> OrderPositionDto:
    return OrderPositionDto(
        id=p.id, mealId=p.meal_id, orderId=p.order_id,
        mealName=p.meal.name if p.meal else None,
        mealWeight=p.meal.weight if p.meal else None,
        quantity=p.quantity, unitPrice=p.unit_price, totalPrice=p.total_price,
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
    await db.flush()
    return _to_dto(existing)


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
