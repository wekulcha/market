from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Query
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.config import get_settings
from app.database import get_db
from app.models.enums import OrderStatus, OrderType
from app.models.meal import Meal
from app.models.order import Order
from app.models.restaurant import Restaurant
from app.models.order_position import OrderPosition
from app.models.staff import Staff
from app.models.user import User
from app.schemas.order import (
    DailyOrderPositionSummaryDto,
    DailyOrderTypeSummaryDto,
    DailyRestaurantSummaryDto,
    DailyStaffSummaryDto,
    OrderCheckoutRequest,
    OrderDto,
    OrderPaidPatchDto,
    OrderReviewPatchDto,
    OrderStatusPatchDto,
    PublicOrderReviewDto,
    PublicOrderReviewsDto,
)
from app.deps.superadmin import assert_superadmin
from app.services import staff_access
from app.services.activity_log import log_user_activity
from app.services.session_auth import get_user_from_bearer
from app.services.telegram_auth import verify_bot_link_token, verify_telegram_init_data
from app.services.phone_norm import is_proper_registered_phone, is_russian_order_phone
from app.services.restaurant_hours import msk_today_utc_naive_bounds, restaurant_accepts_orders_now
from app.services.telegram_notifier import (
    notify_order_placed_detached,
    notify_order_review_detached,
    notify_user_status_changed,
)

router = APIRouter(prefix="/api/v1/orders", tags=["orders"])
MIN_ORDER_ITEMS_TOTAL = Decimal("500")


def _to_dto(order: Order) -> OrderDto:
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
        reviewRating=order.review_rating,
        reviewText=order.review_text,
        reviewCreatedAt=order.review_created_at,
    )


def _public_review_phone(user: User | None) -> str:
    raw = (user.phone if user else "") or ""
    if raw.strip().startswith("tg-"):
        return "номер скрыт"
    digits = "".join(c for c in raw if c.isdigit())
    if len(digits) >= 4:
        return f"***{digits[-4:]}"
    return "номер скрыт"


def _to_public_review_dto(order: Order) -> PublicOrderReviewDto:
    return PublicOrderReviewDto(
        id=int(order.id),
        maskedPhone=_public_review_phone(order.user),
        rating=int(order.review_rating or 0),
        text=order.review_text,
        createdAt=order.review_created_at or order.updated_at or order.created_at,
    )


async def _require_customer_user(
    db: AsyncSession,
    authorization: str | None = None,
) -> User:
    bearer_user = await get_user_from_bearer(db, authorization)
    if bearer_user:
        return bearer_user
    raise HTTPException(401, "Authorization bearer token is required")


async def _require_admin_user(db: AsyncSession, init_data: str) -> User:
    settings = get_settings()
    tg = verify_telegram_init_data(init_data, settings.admin_bot_token)
    if not tg:
        raise HTTPException(401, "Invalid Telegram init data")
    result = await db.execute(select(User).where(User.id == tg["id"]))
    user = result.scalars().first()
    if not user:
        raise HTTPException(403, "Unknown user")
    return user


async def _require_admin_or_bot_user(
    db: AsyncSession,
    init_data: str,
    bot_auth_token: str | None,
) -> User:
    settings = get_settings()
    telegram_id: int | None = None

    if init_data:
        tg = verify_telegram_init_data(init_data, settings.admin_bot_token)
        if tg and tg.get("id") is not None:
            telegram_id = int(tg["id"])

    if telegram_id is None and bot_auth_token:
        telegram_id = verify_bot_link_token(bot_auth_token, settings.admin_bot_token)

    if telegram_id is None:
        raise HTTPException(401, "Telegram init data or bot auth token is required")

    result = await db.execute(select(User).where(User.id == telegram_id))
    user = result.scalars().first()
    if not user:
        raise HTTPException(403, "Unknown user")
    return user


def _empty_type_summary(order_type: str) -> dict[str, object]:
    return {
        "orderType": order_type,
        "ordersCount": 0,
        "revenue": Decimal("0"),
        "paidOrdersCount": 0,
        "unpaidOrdersCount": 0,
        "paidRevenue": Decimal("0"),
        "unpaidRevenue": Decimal("0"),
        "cancelledOrdersCount": 0,
        "cancelledRevenue": Decimal("0"),
        "avgCheck": Decimal("0"),
        "itemsTotal": Decimal("0"),
        "deliveryFeeTotal": Decimal("0"),
        "serviceFeeTotal": Decimal("0"),
        "courierAssignedOrdersCount": 0,
        "positions": defaultdict(lambda: {"mealName": "", "mealWeight": None, "quantity": 0, "totalPrice": Decimal("0")}),
    }


def _build_type_summary(data: dict[str, object]) -> DailyOrderTypeSummaryDto:
    orders_count = int(data["ordersCount"])
    paid_orders_count = int(data["paidOrdersCount"])
    revenue = Decimal(data["revenue"])
    positions_raw = data["positions"]
    assert isinstance(positions_raw, defaultdict)
    positions = [
        DailyOrderPositionSummaryDto(
            mealName=str(values["mealName"] or meal_name),
            mealWeight=values["mealWeight"] if values["mealWeight"] is not None else None,
            quantity=int(values["quantity"]),
            totalPrice=Decimal(values["totalPrice"]),
        )
        for meal_name, values in sorted(
            positions_raw.items(),
            key=lambda item: (-int(item[1]["quantity"]), item[0].lower()),
        )
    ]
    avg_check = (revenue / paid_orders_count) if paid_orders_count > 0 else Decimal("0")
    return DailyOrderTypeSummaryDto(
        orderType=str(data["orderType"]),
        ordersCount=orders_count,
        revenue=revenue,
        paidOrdersCount=paid_orders_count,
        unpaidOrdersCount=int(data["unpaidOrdersCount"]),
        paidRevenue=Decimal(data["paidRevenue"]),
        unpaidRevenue=Decimal(data["unpaidRevenue"]),
        cancelledOrdersCount=int(data["cancelledOrdersCount"]),
        cancelledRevenue=Decimal(data["cancelledRevenue"]),
        avgCheck=avg_check,
        itemsTotal=Decimal(data["itemsTotal"]),
        deliveryFeeTotal=Decimal(data["deliveryFeeTotal"]),
        serviceFeeTotal=Decimal(data["serviceFeeTotal"]),
        courierAssignedOrdersCount=int(data["courierAssignedOrdersCount"]),
        positions=positions,
    )


@router.get("")
async def get_all(
    userId: int | None = None,
    restaurantId: int | None = None,
    status: str | None = None,
    todayOnly: bool = False,
    db: AsyncSession = Depends(get_db),
    authorization: str | None = Header(None, alias="Authorization"),
    x_telegram_init_data: str | None = Header(None, alias="X-Telegram-Init-Data"),
    x_init_data: str | None = Header(None, alias="X-Init-Data"),
    x_kulcha_bot_secret: str | None = Header(None, alias="X-Market-Bot-Secret"),
):
    settings = get_settings()
    init_data = (x_telegram_init_data or x_init_data or "").strip()
    if userId is not None:
        if (
            x_kulcha_bot_secret
            and settings.bot_api_secret
            and x_kulcha_bot_secret == settings.bot_api_secret
        ):
            result = await db.execute(
                select(Order)
                .options(
                    joinedload(Order.user),
                    joinedload(Order.restaurant),
                    joinedload(Order.courier),
                )
                .where(Order.user_id == userId)
                .order_by(Order.created_at.desc())
            )
            return [_to_dto(order) for order in result.unique().scalars().all()]

        user = await _require_customer_user(db, authorization)
        if user.id != userId:
            raise HTTPException(403, "Cannot read other users orders")
        result = await db.execute(
            select(Order)
            .options(joinedload(Order.user), joinedload(Order.restaurant), joinedload(Order.courier))
            .where(Order.user_id == userId)
            .order_by(Order.created_at.desc())
        )
        return [_to_dto(order) for order in result.unique().scalars().all()]

    if restaurantId is not None:
        admin = await _require_admin_user(db, init_data)
        await staff_access.require_restaurant_staff(db, admin.id, restaurantId)
        stmt = (
            select(Order)
            .options(joinedload(Order.user), joinedload(Order.restaurant), joinedload(Order.courier))
            .where(Order.restaurant_id == restaurantId)
        )
        if status and status.upper() != "ALL":
            try:
                stmt = stmt.where(Order.status == OrderStatus(status))
            except ValueError as exc:
                raise HTTPException(400, f"Invalid status: {status}") from exc
        if todayOnly:
            start, end = msk_today_utc_naive_bounds()
            active_statuses = [
                OrderStatus.CREATED,
                OrderStatus.ACCEPTED,
                OrderStatus.COOKING,
                OrderStatus.DELIVERY,
            ]
            stmt = stmt.where(
                or_(
                    and_(Order.created_at >= start, Order.created_at < end),
                    Order.status.in_(active_statuses),
                ),
            )
        stmt = stmt.order_by(Order.created_at.desc())
        result = await db.execute(stmt)
        return [_to_dto(order) for order in result.unique().scalars().all()]

    if status is not None:
        await assert_superadmin(db, authorization)
        try:
            parsed_status = OrderStatus(status)
        except ValueError as exc:
            raise HTTPException(400, f"Invalid status: {status}") from exc
        result = await db.execute(
            select(Order)
            .options(joinedload(Order.user), joinedload(Order.restaurant), joinedload(Order.courier))
            .where(Order.status == parsed_status)
            .order_by(Order.created_at.desc())
        )
        return [_to_dto(order) for order in result.unique().scalars().all()]

    await assert_superadmin(db, authorization)
    result = await db.execute(
        select(Order)
        .options(joinedload(Order.user), joinedload(Order.restaurant), joinedload(Order.courier))
        .order_by(Order.created_at.desc())
    )
    return [_to_dto(order) for order in result.unique().scalars().all()]


@router.get("/today-summary", response_model=DailyStaffSummaryDto)
async def get_today_summary(
    db: AsyncSession = Depends(get_db),
    x_telegram_init_data: str | None = Header(None, alias="X-Telegram-Init-Data"),
    x_init_data: str | None = Header(None, alias="X-Init-Data"),
    x_kulcha_bot_auth: str | None = Header(None, alias="X-Market-Bot-Auth"),
):
    init_data = (x_telegram_init_data or x_init_data or "").strip()
    actor = await _require_admin_or_bot_user(db, init_data, x_kulcha_bot_auth)

    staff_result = await db.execute(
        select(Staff)
        .options(joinedload(Staff.restaurant))
        .where(Staff.user_id == actor.id)
    )
    staff_list = staff_result.unique().scalars().all()
    restaurants_by_id: dict[int, Restaurant] = {}
    for assignment in staff_list:
        restaurant = assignment.restaurant
        if restaurant and restaurant.is_active:
            restaurants_by_id[restaurant.id] = restaurant

    if not restaurants_by_id:
        raise HTTPException(403, "Нет доступа к магазину")

    start, end = msk_today_utc_naive_bounds()
    restaurant_ids = sorted(restaurants_by_id)

    orders_result = await db.execute(
        select(Order)
        .options(joinedload(Order.restaurant))
        .where(
            Order.restaurant_id.in_(restaurant_ids),
            Order.created_at >= start,
            Order.created_at < end,
        )
        .order_by(Order.created_at.asc(), Order.id.asc())
    )
    orders = orders_result.unique().scalars().all()
    order_ids = [order.id for order in orders]

    positions_by_order_id: dict[int, list[OrderPosition]] = defaultdict(list)
    if order_ids:
        positions_result = await db.execute(
            select(OrderPosition)
            .options(joinedload(OrderPosition.meal))
            .where(OrderPosition.order_id.in_(order_ids))
        )
        for position in positions_result.unique().scalars().all():
            positions_by_order_id[position.order_id].append(position)

    restaurant_buckets: dict[int, dict[str, object]] = {}
    for restaurant_id, restaurant in restaurants_by_id.items():
        restaurant_buckets[restaurant_id] = {
            "restaurantId": restaurant_id,
            "restaurantName": restaurant.name,
            "totalOrdersCount": 0,
            "totalRevenue": Decimal("0"),
            "paidOrdersCount": 0,
            "unpaidOrdersCount": 0,
            "paidRevenue": Decimal("0"),
            "unpaidRevenue": Decimal("0"),
            "cancelledOrdersCount": 0,
            "cancelledRevenue": Decimal("0"),
            "dineIn": _empty_type_summary("DINE_IN"),
            "delivery": _empty_type_summary("DELIVERY"),
        }

    for order in orders:
        if order.status == OrderStatus.CANCELLED:
            continue

        bucket = restaurant_buckets[order.restaurant_id]
        bucket["totalOrdersCount"] = int(bucket["totalOrdersCount"]) + 1
        if order.is_paid:
            bucket["paidOrdersCount"] = int(bucket["paidOrdersCount"]) + 1
            bucket["paidRevenue"] = Decimal(bucket["paidRevenue"]) + order.total
            bucket["totalRevenue"] = Decimal(bucket["totalRevenue"]) + order.total
        else:
            bucket["unpaidOrdersCount"] = int(bucket["unpaidOrdersCount"]) + 1
            bucket["unpaidRevenue"] = Decimal(bucket["unpaidRevenue"]) + order.total

        section_key = "delivery" if order.order_type == OrderType.DELIVERY else "dineIn"
        section = bucket[section_key]
        assert isinstance(section, dict)
        section["ordersCount"] = int(section["ordersCount"]) + 1
        if order.is_paid:
            section["paidOrdersCount"] = int(section["paidOrdersCount"]) + 1
            section["paidRevenue"] = Decimal(section["paidRevenue"]) + order.total
            section["revenue"] = Decimal(section["revenue"]) + order.total
            section["itemsTotal"] = Decimal(section["itemsTotal"]) + order.items_total
            section["deliveryFeeTotal"] = Decimal(section["deliveryFeeTotal"]) + order.delivery_fee
            section["serviceFeeTotal"] = Decimal(section["serviceFeeTotal"]) + order.service_fee
        else:
            section["unpaidOrdersCount"] = int(section["unpaidOrdersCount"]) + 1
            section["unpaidRevenue"] = Decimal(section["unpaidRevenue"]) + order.total
        if order.order_type == OrderType.DELIVERY and order.courier_id is not None:
            section["courierAssignedOrdersCount"] = int(section["courierAssignedOrdersCount"]) + 1
        positions = section["positions"]
        assert isinstance(positions, defaultdict)
        for position in positions_by_order_id.get(order.id, []):
            meal_name = position.meal.name if position.meal else f"Блюдо #{position.meal_id}"
            meal_weight = position.meal.weight if position.meal else None
            position_key = f"{meal_name}|{meal_weight or ''}"
            entry = positions[position_key]
            entry["mealName"] = meal_name
            entry["mealWeight"] = meal_weight
            entry["quantity"] += position.quantity
            entry["totalPrice"] += position.total_price

    restaurant_summaries: list[DailyRestaurantSummaryDto] = []
    for restaurant_id in restaurant_ids:
        bucket = restaurant_buckets[restaurant_id]
        total_orders = int(bucket["totalOrdersCount"])
        paid_orders = int(bucket["paidOrdersCount"])
        total_revenue = Decimal(bucket["totalRevenue"])
        restaurant_summaries.append(
            DailyRestaurantSummaryDto(
                restaurantId=restaurant_id,
                restaurantName=str(bucket["restaurantName"]),
                totalOrdersCount=total_orders,
                totalRevenue=total_revenue,
                paidOrdersCount=int(bucket["paidOrdersCount"]),
                unpaidOrdersCount=int(bucket["unpaidOrdersCount"]),
                paidRevenue=Decimal(bucket["paidRevenue"]),
                unpaidRevenue=Decimal(bucket["unpaidRevenue"]),
                cancelledOrdersCount=int(bucket["cancelledOrdersCount"]),
                cancelledRevenue=Decimal(bucket["cancelledRevenue"]),
                avgCheck=(total_revenue / paid_orders) if paid_orders > 0 else Decimal("0"),
                dineIn=_build_type_summary(bucket["dineIn"]),
                delivery=_build_type_summary(bucket["delivery"]),
            )
        )

    return DailyStaffSummaryDto(
        reportDate=start.date().isoformat(),
        timezone="Europe/Moscow",
        generatedAt=datetime.now(),
        restaurants=restaurant_summaries,
    )


@router.get("/reviews", response_model=PublicOrderReviewsDto)
async def get_public_reviews(
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    reviews_filter = Order.review_rating.is_not(None)

    summary_result = await db.execute(
        select(func.count(Order.id), func.avg(Order.review_rating)).where(reviews_filter)
    )
    reviews_count, average_rating = summary_result.one()

    reviews_result = await db.execute(
        select(Order)
        .options(joinedload(Order.user))
        .where(reviews_filter)
        .order_by(Order.review_created_at.desc(), Order.created_at.desc(), Order.id.desc())
        .limit(limit)
    )
    reviews = [_to_public_review_dto(order) for order in reviews_result.unique().scalars().all()]

    return PublicOrderReviewsDto(
        reviewsCount=int(reviews_count or 0),
        averageRating=float(average_rating) if average_rating is not None else None,
        reviews=reviews,
    )


@router.get("/my")
async def get_my_orders(
    db: AsyncSession = Depends(get_db),
    authorization: str | None = Header(None, alias="Authorization"),
):
    user = await get_user_from_bearer(db, authorization)
    if not user:
        raise HTTPException(401, "Authorization bearer token is required")

    result = await db.execute(
        select(Order)
        .options(joinedload(Order.user), joinedload(Order.restaurant), joinedload(Order.courier))
        .where(Order.user_id == user.id)
        .order_by(Order.created_at.desc())
    )
    return [_to_dto(order) for order in result.unique().scalars().all()]


@router.get("/{order_id}")
async def get_by_id(
    order_id: int,
    db: AsyncSession = Depends(get_db),
    authorization: str | None = Header(None, alias="Authorization"),
    x_telegram_init_data: str | None = Header(None, alias="X-Telegram-Init-Data"),
    x_init_data: str | None = Header(None, alias="X-Init-Data"),
    x_kulcha_internal_secret: str | None = Header(None, alias="X-Market-Internal-Secret"),
):
    result = await db.execute(
        select(Order)
        .options(joinedload(Order.user), joinedload(Order.restaurant), joinedload(Order.courier))
        .where(Order.id == order_id)
    )
    order = result.unique().scalars().first()
    if not order:
        raise HTTPException(404, "Order not found")

    settings = get_settings()
    if settings.internal_api_secret and x_kulcha_internal_secret == settings.internal_api_secret:
        return _to_dto(order)

    bearer_user = await get_user_from_bearer(db, authorization)
    if bearer_user:
        if order.user_id != bearer_user.id:
            raise HTTPException(403, "Forbidden")
        return _to_dto(order)

    init_data = (x_telegram_init_data or x_init_data or "").strip()
    try:
        admin = await _require_admin_user(db, init_data)
        await staff_access.require_restaurant_staff(db, admin.id, order.restaurant_id)
        return _to_dto(order)
    except HTTPException as exc:
        if exc.status_code != 401:
            raise

    raise HTTPException(401, "Authorization bearer token is required")


@router.post("/checkout", status_code=201)
async def checkout(
    body: OrderCheckoutRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    authorization: str | None = Header(None, alias="Authorization"),
):
    customer = await _require_customer_user(db, authorization)

    if not is_proper_registered_phone(customer.phone):
        raise HTTPException(
            403,
            "Вы не зарегистрировались. Зайдите в бот Kulcha Market, отправьте /start и поделитесь контактом.",
        )
    if not is_russian_order_phone(customer.phone):
        raise HTTPException(
            403,
            "Для заказа нужно указать и сохранить российский номер телефона.",
        )

    if not body.items:
        raise HTTPException(400, "Invalid checkout payload")

    r_check = await db.execute(select(Restaurant).where(Restaurant.id == body.restaurantId))
    rest_row = r_check.scalars().first()
    if not rest_row or not rest_row.is_active:
        raise HTTPException(400, "Магазин недоступен")

    if not restaurant_accepts_orders_now(rest_row):
        raise HTTPException(400, "Сейчас магазин не принимает заказы (вне времени приёма).")

    unavailable: list[str] = []
    lines_payload: list[tuple[Meal, Decimal, int]] = []
    for line in body.items:
        if line.quantity is None or line.quantity <= 0:
            raise HTTPException(400, "Invalid order line")
        result = await db.execute(
            select(Meal).options(joinedload(Meal.restaurant)).where(Meal.id == line.mealId)
        )
        meal = result.unique().scalars().first()
        if not meal:
            raise HTTPException(400, "Unknown meal")
        if meal.restaurant_id != body.restaurantId:
            raise HTTPException(400, "Meal does not belong to restaurant")
        if not meal.is_available:
            unavailable.append(meal.name)
            continue
        unit_price = line.unitPrice if line.unitPrice is not None else meal.price
        lines_payload.append((meal, unit_price, line.quantity))

    if unavailable:
        raise HTTPException(
            400,
            f"Нет в наличии: {', '.join(unavailable)}",
        )
    if not lines_payload:
        raise HTTPException(400, "В заказе нет доступных товаров.")

    calculated_items_total = sum(
        (unit_price * qty for _, unit_price, qty in lines_payload),
        Decimal("0"),
    )
    if calculated_items_total < MIN_ORDER_ITEMS_TOTAL:
        raise HTTPException(
            400,
            f"Минимальная сумма заказа — {MIN_ORDER_ITEMS_TOTAL:.0f} ₽.",
        )

    delivery_fee = body.deliveryFee or Decimal(0)
    service_fee = body.serviceFee or Decimal(0)
    total = calculated_items_total + delivery_fee + service_fee

    tn = (body.tableNumber.strip() if body.tableNumber else None) or None
    comment = (body.comment.strip() if body.comment else None) or None
    if body.orderType == OrderType.DELIVERY.value and not (body.deliveryAddress or "").strip():
        raise HTTPException(400, "Укажите адрес доставки (доставка только внутри Фуд Сити).")
    if body.orderType == OrderType.DINE_IN.value and not tn:
        raise HTTPException(400, "Укажите номер стола для заказа в зале.")
    order = Order(
        status=OrderStatus.CREATED,
        user_id=customer.id,
        delivery_address=body.deliveryAddress,
        table_number=tn,
        comment=comment,
        restaurant_id=body.restaurantId,
        created_at=datetime.now(),
        updated_at=datetime.now(),
        order_type=OrderType(body.orderType),
        items_total=calculated_items_total,
        delivery_fee=delivery_fee,
        service_fee=service_fee,
        total=total,
        is_paid=False,
    )
    db.add(order)
    await db.flush()

    for meal, unit_price, qty in lines_payload:
        line_total = unit_price * qty
        position = OrderPosition(
            meal_id=meal.id,
            order_id=order.id,
            quantity=qty,
            unit_price=unit_price,
            total_price=line_total,
        )
        db.add(position)

    await db.flush()
    await log_user_activity(
        db,
        user_id=customer.id,
        event="checkout_created",
        source="backend",
        metadata={"orderId": order.id, "total": str(total), "restaurantId": body.restaurantId},
    )
    response = _to_dto(order)
    order_id = int(order.id)
    await db.commit()
    background_tasks.add_task(notify_order_placed_detached, order_id)
    return response


@router.put("/{order_id}")
async def update_order(
    order_id: int,
    dto: OrderDto,
    db: AsyncSession = Depends(get_db),
    x_telegram_init_data: str = Header(..., alias="X-Telegram-Init-Data"),
):
    result = await db.execute(
        select(Order)
        .options(joinedload(Order.user), joinedload(Order.restaurant), joinedload(Order.courier))
        .where(Order.id == order_id)
    )
    existing = result.unique().scalars().first()
    if not existing:
        raise HTTPException(404, "Order not found")

    admin = await _require_admin_user(db, x_telegram_init_data)
    await staff_access.require_restaurant_staff(db, admin.id, existing.restaurant_id)

    if dto.status is not None:
        existing.status = OrderStatus(dto.status)
    if dto.deliveryAddress is not None:
        existing.delivery_address = dto.deliveryAddress
    if dto.comment is not None:
        existing.comment = dto.comment
    if dto.courierId is not None:
        existing.courier_id = dto.courierId
    if dto.orderType is not None:
        existing.order_type = OrderType(dto.orderType)
    if dto.itemsTotal is not None:
        existing.items_total = dto.itemsTotal
    if dto.deliveryFee is not None:
        existing.delivery_fee = dto.deliveryFee
    if dto.serviceFee is not None:
        existing.service_fee = dto.serviceFee
    if dto.total is not None:
        existing.total = dto.total
    if dto.isPaid is not None:
        existing.is_paid = dto.isPaid
    existing.updated_at = datetime.now()

    await db.flush()
    actor = f"@{admin.username}" if admin.username else f"id:{admin.id}"
    await notify_user_status_changed(db, order_id, admin_actor=actor)

    return _to_dto(existing)


@router.post("/{order_id}/cancel")
async def cancel_my_order(
    order_id: int,
    db: AsyncSession = Depends(get_db),
    authorization: str | None = Header(None, alias="Authorization"),
):
    customer = await _require_customer_user(db, authorization)
    result = await db.execute(select(Order).where(Order.id == order_id))
    order = result.scalars().first()
    if not order:
        raise HTTPException(404, "Order not found")
    if order.user_id != customer.id:
        raise HTTPException(403, "Forbidden")
    if order.status != OrderStatus.CREATED:
        raise HTTPException(400, "Отменить можно только заказ до принятия рестораном.")
    order.status = OrderStatus.CANCELLED
    order.updated_at = datetime.now()
    await db.flush()
    await notify_user_status_changed(db, order_id)
    return _to_dto(order)


@router.post("/{order_id}/review")
async def patch_review(
    order_id: int,
    body: OrderReviewPatchDto,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    authorization: str | None = Header(None, alias="Authorization"),
    x_kulcha_bot_secret: str | None = Header(None, alias="X-Market-Bot-Secret"),
):
    if body.rating < 1 or body.rating > 5:
        raise HTTPException(400, "Оценка должна быть от 1 до 5")

    settings = get_settings()
    bot_authorized = bool(
        x_kulcha_bot_secret
        and settings.bot_api_secret
        and x_kulcha_bot_secret == settings.bot_api_secret
    )
    actor = None if bot_authorized else await get_user_from_bearer(db, authorization)
    if not bot_authorized and not actor:
        raise HTTPException(401, "Authorization bearer token is required")

    result = await db.execute(
        select(Order)
        .options(joinedload(Order.user), joinedload(Order.restaurant), joinedload(Order.courier))
        .where(Order.id == order_id)
    )
    order = result.unique().scalars().first()
    if not order:
        raise HTTPException(404, "Order not found")
    if actor and order.user_id != actor.id:
        raise HTTPException(403, "Forbidden")
    if order.status != OrderStatus.DONE:
        raise HTTPException(400, "Оставить отзыв можно только после завершения заказа.")

    text = body.text.strip()[:1000] if body.text else None
    order.review_rating = body.rating
    if body.text is not None:
        order.review_text = text
    order.review_created_at = order.review_created_at or datetime.now()
    order.updated_at = datetime.now()
    await log_user_activity(
        db,
        user_id=order.user_id,
        event="review_saved",
        source="bot" if bot_authorized else "webapp",
        metadata={"orderId": order.id, "rating": body.rating, "hasText": bool(text)},
    )

    await db.flush()
    response = _to_dto(order)
    await db.commit()
    background_tasks.add_task(notify_order_review_detached, order_id)
    return response


@router.patch("/{order_id}/paid")
async def patch_paid(
    order_id: int,
    body: OrderPaidPatchDto,
    db: AsyncSession = Depends(get_db),
    x_telegram_init_data: str | None = Header(None, alias="X-Telegram-Init-Data"),
    x_kulcha_internal_secret: str | None = Header(None, alias="X-Market-Internal-Secret"),
    x_kulcha_actor_name: str | None = Header(None, alias="X-Market-Actor-Name"),
):
    result = await db.execute(
        select(Order)
        .options(joinedload(Order.user), joinedload(Order.restaurant), joinedload(Order.courier))
        .where(Order.id == order_id)
    )
    order = result.unique().scalars().first()
    if not order:
        raise HTTPException(404, "Order not found")
    settings = get_settings()
    if settings.internal_api_secret and x_kulcha_internal_secret == settings.internal_api_secret:
        actor_name = x_kulcha_actor_name
        pass
    else:
        if not x_telegram_init_data:
            raise HTTPException(401, "X-Telegram-Init-Data is required")
        admin = await _require_admin_user(db, x_telegram_init_data)
        await staff_access.require_restaurant_staff(db, admin.id, order.restaurant_id)
        actor_name = f"@{admin.username}" if admin.username else f"id:{admin.id}"
    if order.status == OrderStatus.CANCELLED and body.isPaid:
        raise HTTPException(400, "Отменённый заказ нельзя отметить оплаченным")
    order.is_paid = body.isPaid
    order.updated_at = datetime.now()
    await db.flush()
    await notify_user_status_changed(db, order_id, admin_actor=actor_name, notify_user=False)
    return _to_dto(order)


@router.patch("/{order_id}/status")
async def patch_status(
    order_id: int,
    body: OrderStatusPatchDto,
    db: AsyncSession = Depends(get_db),
    x_kulcha_internal_secret: str = Header(..., alias="X-Market-Internal-Secret"),
    x_kulcha_actor_name: str | None = Header(None, alias="X-Market-Actor-Name"),
):
    settings = get_settings()
    if not settings.internal_api_secret:
        raise HTTPException(503, "Internal API secret is not configured")
    if x_kulcha_internal_secret != settings.internal_api_secret:
        raise HTTPException(401, "Invalid internal secret")

    result = await db.execute(
        select(Order)
        .options(joinedload(Order.user), joinedload(Order.restaurant), joinedload(Order.courier))
        .where(Order.id == order_id)
    )
    order = result.unique().scalars().first()
    if not order:
        raise HTTPException(404, "Order not found")

    order.status = OrderStatus(body.status)
    order.updated_at = datetime.now()
    await db.flush()

    await notify_user_status_changed(db, order_id, admin_actor=x_kulcha_actor_name)

    return _to_dto(order)


@router.delete("/{order_id}", status_code=204)
async def delete_order(order_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Order).where(Order.id == order_id))
    order = result.scalars().first()
    if order:
        await db.delete(order)
