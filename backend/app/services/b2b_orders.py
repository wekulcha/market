from __future__ import annotations

from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.b2b import (
    B2BOrder,
    B2BOrderStatusHistory,
    BuyerProfile,
    InventoryBalance,
    InventoryMovement,
    InventoryReservation,
    OrderFulfillmentGroup,
    SellerProfile,
)
from app.services.b2b_common import utcnow
from app.services.b2b_notifications import enqueue_notification
from app.services.b2b_state import InvalidOrderTransition, validate_order_transition


async def _locked_reservations(
    db: AsyncSession,
    order_id: object,
) -> list[InventoryReservation]:
    result = await db.execute(
        select(InventoryReservation)
        .where(InventoryReservation.order_id == order_id)
        .order_by(InventoryReservation.inventory_balance_id)
        .with_for_update()
    )
    return list(result.scalars().all())


async def convert_order_reservations(db: AsyncSession, order: B2BOrder) -> None:
    for reservation in await _locked_reservations(db, order.id):
        if reservation.status == "CONVERTED":
            continue
        if reservation.status != "ACTIVE":
            raise HTTPException(409, "Резерв заказа уже недоступен")
        balance = await db.get(
            InventoryBalance,
            reservation.inventory_balance_id,
            with_for_update=True,
        )
        if not balance or balance.reserved_quantity < reservation.quantity:
            raise HTTPException(409, "Остаток резерва повреждён")
        balance.reserved_quantity -= reservation.quantity
        balance.sold_quantity += reservation.quantity
        balance.version += 1
        reservation.status = "CONVERTED"
        reservation.converted_at = utcnow()
        db.add(
            InventoryMovement(
                inventory_balance_id=balance.id,
                reservation_id=reservation.id,
                movement_type="SALE",
                quantity=reservation.quantity,
                total_after=balance.total_quantity,
                reserved_after=balance.reserved_quantity,
                sold_after=balance.sold_quantity,
                reason=f"Order {order.order_number} confirmed",
            )
        )


async def release_order_inventory(
    db: AsyncSession,
    order: B2BOrder,
    *,
    reason: str,
    actor_user_id: int | None,
) -> None:
    for reservation in await _locked_reservations(db, order.id):
        balance = await db.get(
            InventoryBalance,
            reservation.inventory_balance_id,
            with_for_update=True,
        )
        if not balance:
            raise HTTPException(409, "Остаток резерва не найден")
        movement_type: str
        if reservation.status == "ACTIVE":
            if balance.reserved_quantity < reservation.quantity:
                raise HTTPException(409, "Невозможно освободить повреждённый резерв")
            balance.reserved_quantity -= reservation.quantity
            reservation.status = "RELEASED"
            reservation.released_at = utcnow()
            movement_type = "RELEASE"
        elif reservation.status == "CONVERTED":
            if balance.sold_quantity < reservation.quantity:
                raise HTTPException(409, "Невозможно вернуть повреждённую продажу")
            balance.sold_quantity -= reservation.quantity
            reservation.status = "CANCELED"
            reservation.released_at = utcnow()
            movement_type = "CANCEL"
        else:
            continue
        balance.version += 1
        db.add(
            InventoryMovement(
                inventory_balance_id=balance.id,
                reservation_id=reservation.id,
                movement_type=movement_type,
                quantity=reservation.quantity,
                total_after=balance.total_quantity,
                reserved_after=balance.reserved_quantity,
                sold_after=balance.sold_quantity,
                actor_user_id=actor_user_id,
                reason=reason,
            )
        )


async def transition_order(
    db: AsyncSession,
    order: B2BOrder,
    target_status: str,
    *,
    actor_user_id: int | None,
    actor_type: str,
    comment: str | None = None,
) -> B2BOrder:
    try:
        target = validate_order_transition(order.status, target_status)
    except InvalidOrderTransition as exc:
        raise HTTPException(409, str(exc)) from exc
    previous = order.status
    if target.value == "CONFIRMED":
        await convert_order_reservations(db, order)
    elif target.value == "CANCELED":
        await release_order_inventory(
            db,
            order,
            reason=comment or f"Order {order.order_number} canceled",
            actor_user_id=actor_user_id,
        )
        order.canceled_at = utcnow()
    elif target.value == "COMPLETED":
        order.completed_at = utcnow()
    order.status = target.value
    db.add(
        B2BOrderStatusHistory(
            order_id=order.id,
            from_status=previous,
            to_status=target.value,
            actor_user_id=actor_user_id,
            actor_type=actor_type,
            comment=comment,
        )
    )
    await db.flush()
    return order


async def expire_reservations(db: AsyncSession, *, now: datetime | None = None) -> int:
    current = now or utcnow()
    result = await db.execute(
        select(B2BOrder)
        .where(
            B2BOrder.status.in_(("RESERVED", "PENDING_CONFIRMATION")),
            exists(
                select(1).where(
                    InventoryReservation.order_id == B2BOrder.id,
                    InventoryReservation.status == "ACTIVE",
                    InventoryReservation.expires_at <= current,
                )
            ),
        )
        .with_for_update()
    )
    orders = list(result.scalars().all())
    for order in orders:
        await release_order_inventory(
            db,
            order,
            reason="Reservation TTL expired",
            actor_user_id=None,
        )
        previous = order.status
        order.status = "CANCELED"
        order.canceled_at = current
        db.add(
            B2BOrderStatusHistory(
                order_id=order.id,
                from_status=previous,
                to_status="CANCELED",
                actor_type="SYSTEM",
                comment="Reservation TTL expired",
            )
        )
        settings = get_settings()
        buyer = await db.get(BuyerProfile, order.buyer_profile_id)
        if buyer:
            await enqueue_notification(
                db,
                user_id=buyer.user_id,
                recipient=buyer.user_id,
                event_type="RESERVATION_EXPIRED",
                idempotency_key=f"reservation-expired:buyer:{order.id}",
                text=f"Резерв заказа {order.order_number} истёк; остатки возвращены в каталог.",
                bot_scope="BUYER",
                deep_link=(
                    f"{settings.public_base_url.rstrip('/')}"
                    f"{settings.buyer_app_path}/orders/{order.id}"
                ),
            )
        groups = list(
            (
                await db.execute(
                    select(OrderFulfillmentGroup)
                    .where(OrderFulfillmentGroup.order_id == order.id)
                    .with_for_update()
                )
            ).scalars().all()
        )
        for group in groups:
            group.status = "CANCELED"
            seller = await db.get(SellerProfile, group.seller_profile_id)
            if seller:
                await enqueue_notification(
                    db,
                    user_id=seller.user_id,
                    recipient=seller.user_id,
                    event_type="RESERVATION_EXPIRED",
                    idempotency_key=f"reservation-expired:seller:{order.id}:{seller.id}",
                    text=f"Заказ {order.order_number} отменён: срок резерва истёк.",
                    bot_scope="SELLER",
                    deep_link=(
                        f"{settings.public_base_url.rstrip('/')}"
                        f"{settings.seller_app_path}/orders"
                    ),
                )
    await db.flush()
    return len(orders)
