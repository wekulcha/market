from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.database import get_db
from app.models.courier import Courier
from app.models.enums import OrderStatus
from app.models.order import Order
from app.schemas.courier import CourierPanelOverviewDto
from app.schemas.order import OrderDto

router = APIRouter(prefix="/api/v1/courier-panel", tags=["courier-panel"])

ACTIVE_DELIVERY = {OrderStatus.CREATED, OrderStatus.ACCEPTED, OrderStatus.COOKING, OrderStatus.DELIVERY}


def _order_dto(o: Order) -> OrderDto:
    return OrderDto(
        id=o.id, status=o.status.value, userId=o.user_id,
        deliveryAddress=o.delivery_address, restaurantId=o.restaurant_id,
        createdAt=o.created_at, updatedAt=o.updated_at,
        courierId=o.courier_id, orderType=o.order_type.value,
        itemsTotal=o.items_total, deliveryFee=o.delivery_fee,
        serviceFee=o.service_fee, total=o.total, isPaid=o.is_paid,
    )


async def _resolve_courier(db: AsyncSession, user_id: int) -> Courier:
    result = await db.execute(
        select(Courier).options(joinedload(Courier.user)).where(Courier.user_id == user_id)
    )
    c = result.unique().scalars().first()
    if not c:
        raise HTTPException(404, "Courier profile not found")
    return c


async def _courier_orders(db: AsyncSession, courier_id: int) -> list[Order]:
    result = await db.execute(
        select(Order)
        .options(joinedload(Order.user), joinedload(Order.restaurant), joinedload(Order.courier))
        .where(Order.courier_id == courier_id)
    )
    return list(result.unique().scalars().all())


async def _user_orders(db: AsyncSession, user_id: int) -> list[Order]:
    result = await db.execute(
        select(Order)
        .options(joinedload(Order.user), joinedload(Order.restaurant), joinedload(Order.courier))
        .where(Order.user_id == user_id)
    )
    return list(result.unique().scalars().all())


@router.get("/{user_id}")
async def get_overview(user_id: int, db: AsyncSession = Depends(get_db)):
    courier = await _resolve_courier(db, user_id)
    courier_orders = await _courier_orders(db, courier.id)
    created_orders = await _user_orders(db, user_id)

    return CourierPanelOverviewDto(
        courierId=courier.id,
        userId=user_id,
        deliveryOrders=[_order_dto(o) for o in courier_orders if o.status in ACTIVE_DELIVERY],
        deliveryHistory=[_order_dto(o) for o in courier_orders if o.status == OrderStatus.DONE],
        createdOrders=[_order_dto(o) for o in created_orders],
    )


@router.get("/{user_id}/delivery-orders")
async def delivery_orders(user_id: int, db: AsyncSession = Depends(get_db)):
    courier = await _resolve_courier(db, user_id)
    orders = await _courier_orders(db, courier.id)
    return [_order_dto(o) for o in orders if o.status in ACTIVE_DELIVERY]


@router.get("/{user_id}/delivery-history")
async def delivery_history(user_id: int, db: AsyncSession = Depends(get_db)):
    courier = await _resolve_courier(db, user_id)
    orders = await _courier_orders(db, courier.id)
    return [_order_dto(o) for o in orders if o.status == OrderStatus.DONE]


@router.get("/{user_id}/created-orders")
async def created_orders(user_id: int, db: AsyncSession = Depends(get_db)):
    await _resolve_courier(db, user_id)
    orders = await _user_orders(db, user_id)
    return [_order_dto(o) for o in orders]
