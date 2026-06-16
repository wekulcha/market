from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from app.database import get_db
from app.deps.superadmin import require_superadmin
from app.models.courier import Courier
from app.models.enums import StaffPermission
from app.models.meal import Meal
from app.models.order import Order
from app.models.order_position import OrderPosition
from app.models.restaurant import Restaurant
from app.models.subscription_log import SubscriptionLog
from app.models.staff import Staff
from app.models.user import User
from app.models.user_activity_log import UserActivityLog
from app.schemas.activity import ActivityLogDto
from app.schemas.admin import (
    AdminAssignCourierRequestDto,
    AdminAssignStaffRequestDto,
    AdminCourierDto,
    AdminCreateRestaurantRequestDto,
    AdminOrderDetailDto,
    AdminOrderHistoryItemDto,
    AdminOrderPositionLineDto,
    AdminOrderSummaryDto,
    AdminRestaurantDto,
    AdminRestaurantOverviewDto,
    AdminSetActiveDto,
    AdminStaffAssignmentDto,
    AdminStatsSummaryDto,
    AdminUserOverviewDto,
)
from app.schemas.meal import MealDto
from app.schemas.order import OrderDto
from app.schemas.staff import StaffDto
router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


def _meal_dto(m: Meal) -> MealDto:
    return MealDto(
        id=m.id, restaurantId=m.restaurant_id, name=m.name,
        description=m.description, weight=m.weight, calorie=m.calorie,
        imageLink=m.image_link, category=m.category,
        price=m.price, requiresFinalWeight=m.requires_final_weight, available=m.is_available,
    )


def _order_dto(o: Order) -> OrderDto:
    return OrderDto(
        id=o.id, status=o.status.value, userId=o.user_id,
        deliveryAddress=o.delivery_address, restaurantId=o.restaurant_id,
        createdAt=o.created_at, updatedAt=o.updated_at,
        courierId=o.courier_id, orderType=o.order_type.value,
        itemsTotal=o.items_total, deliveryFee=o.delivery_fee,
        serviceFee=o.service_fee, total=o.total, isPaid=o.is_paid,
    )


def _staff_dto(s: Staff) -> StaffDto:
    return StaffDto(
        id=s.id, userId=s.user_id,
        restaurantId=s.restaurant_id, permission=s.permission.value,
    )


def _activity_log_dto(log: UserActivityLog) -> ActivityLogDto:
    return ActivityLogDto(
        id=log.id,
        userId=log.user_id,
        event=log.event,
        source=log.source,
        metadata=log.metadata_json,
        createdAt=log.created_at,
    )


async def _grant_owner_full_staff_access(
    db: AsyncSession,
    *,
    restaurant_id: int,
    owner_user_id: int,
) -> None:
    """Владелец = все права staff для этого ресторана (меню + заказы)."""
    for perm in StaffPermission:
        existing = await db.execute(
            select(Staff).where(
                Staff.user_id == owner_user_id,
                Staff.restaurant_id == restaurant_id,
                Staff.permission == perm,
            )
        )
        if existing.scalars().first():
            continue
        db.add(
            Staff(
                user_id=owner_user_id,
                restaurant_id=restaurant_id,
                permission=perm,
            )
        )
    await db.flush()


@router.get("/users")
async def get_all_users(
    db: AsyncSession = Depends(get_db),
    _caller: User = Depends(require_superadmin),
):
    users_result = await db.execute(select(User))
    users = users_result.scalars().all()

    overviews = []
    for user in users:
        courier_result = await db.execute(select(Courier).where(Courier.user_id == user.id))
        is_courier = courier_result.scalars().first() is not None

        staff_result = await db.execute(
            select(Staff)
            .options(joinedload(Staff.restaurant))
            .where(Staff.user_id == user.id)
        )
        staff_assignments = [
            AdminStaffAssignmentDto(
                staffId=s.id, restaurantId=s.restaurant_id,
                restaurantName=s.restaurant.name, permission=s.permission.value,
            )
            for s in staff_result.unique().scalars().all()
        ]

        orders_result = await db.execute(
            select(Order)
            .options(joinedload(Order.restaurant))
            .where(Order.user_id == user.id)
        )
        order_history = [
            AdminOrderHistoryItemDto(
                orderId=o.id, status=o.status.value,
                restaurantId=o.restaurant_id, restaurantName=o.restaurant.name,
                total=o.total, createdAt=o.created_at,
            )
            for o in orders_result.unique().scalars().all()
        ]

        overviews.append(AdminUserOverviewDto(
            id=user.id, username=user.username, phone=user.phone,
            email=user.email, address=user.address,
            isActive=user.is_active,
            courier=is_courier,
            staffAssignments=staff_assignments,
            orderHistory=order_history,
        ))
    return overviews


@router.get("/couriers")
async def get_all_couriers(
    db: AsyncSession = Depends(get_db),
    _caller: User = Depends(require_superadmin),
):
    result = await db.execute(select(Courier).options(joinedload(Courier.user)))
    return [
        AdminCourierDto(
            courierId=c.id, userId=c.user.id,
            username=c.user.username, phone=c.user.phone, email=c.user.email,
        )
        for c in result.unique().scalars().all()
    ]


@router.get("/restaurants")
async def get_all_restaurants(
    db: AsyncSession = Depends(get_db),
    _caller: User = Depends(require_superadmin),
):
    restaurants_result = await db.execute(select(Restaurant))
    restaurants = restaurants_result.scalars().all()

    overviews = []
    for r in restaurants:
        staff_result = await db.execute(
            select(Staff).options(joinedload(Staff.user))
            .where(Staff.restaurant_id == r.id)
        )
        staff_list = [_staff_dto(s) for s in staff_result.unique().scalars().all()]

        meals_result = await db.execute(select(Meal).where(Meal.restaurant_id == r.id))
        meals_list = [_meal_dto(m) for m in meals_result.scalars().all()]

        orders_result = await db.execute(
            select(Order)
            .options(joinedload(Order.user), joinedload(Order.restaurant), joinedload(Order.courier))
            .where(Order.restaurant_id == r.id)
        )
        orders_list = [_order_dto(o) for o in orders_result.unique().scalars().all()]

        overviews.append(AdminRestaurantOverviewDto(
            id=r.id, name=r.name, address=r.address,
            imageLink=r.image_link,
            isActive=r.is_active,
            staff=staff_list, meals=meals_list, orderHistory=orders_list,
        ))
    return overviews


@router.get("/users/{user_id}/restaurants")
async def get_user_restaurants(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    _caller: User = Depends(require_superadmin),
):
    result = await db.execute(select(User).where(User.id == user_id))
    if not result.scalars().first():
        raise HTTPException(404, "User not found")

    staff_result = await db.execute(
        select(Staff)
        .options(joinedload(Staff.restaurant), joinedload(Staff.user))
        .where(Staff.user_id == user_id)
    )
    staff_list = staff_result.unique().scalars().all()

    grouped: dict[int, list[Staff]] = {}
    for s in staff_list:
        grouped.setdefault(s.restaurant_id, []).append(s)

    restaurants = []
    for assignments in grouped.values():
        first = assignments[0]
        restaurants.append(AdminRestaurantDto(
            id=first.restaurant.id, name=first.restaurant.name,
            address=first.restaurant.address, ownerUserId=first.user_id,
            ownerPermissions=list({s.permission.value for s in assignments}),
        ))
    restaurants.sort(key=lambda r: r.name)
    return restaurants


@router.get("/users/{user_id}/activity", response_model=list[ActivityLogDto])
async def get_user_activity_logs(
    user_id: int,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    _caller: User = Depends(require_superadmin),
):
    result = await db.execute(select(User).where(User.id == user_id))
    if not result.scalars().first():
        raise HTTPException(404, "User not found")

    safe_limit = min(max(limit, 1), 300)
    logs_result = await db.execute(
        select(UserActivityLog)
        .where(UserActivityLog.user_id == user_id)
        .order_by(UserActivityLog.created_at.desc(), UserActivityLog.id.desc())
        .limit(safe_limit)
    )
    return [_activity_log_dto(log) for log in logs_result.scalars().all()]


@router.post("/restaurants", status_code=201)
async def create_restaurant(
    request: AdminCreateRestaurantRequestDto,
    db: AsyncSession = Depends(get_db),
    _caller: User = Depends(require_superadmin),
):
    if not request.name or not request.name.strip():
        raise HTTPException(400, "Нужно указать название магазина")
    if not request.address or not request.address.strip():
        raise HTTPException(400, "Нужно указать адрес магазина")

    result = await db.execute(select(User).where(User.id == request.ownerUserId))
    owner = result.scalars().first()
    if not owner:
        raise HTTPException(
            404,
            "Пользователь с таким ID не найден. Сначала создайте пользователя (например, /start в боте).",
        )

    restaurant = Restaurant(
        name=request.name.strip(),
        address=request.address.strip(),
        is_active=True,
    )
    db.add(restaurant)
    await db.flush()

    await _grant_owner_full_staff_access(
        db, restaurant_id=restaurant.id, owner_user_id=owner.id
    )

    return AdminRestaurantDto(
        id=restaurant.id,
        name=restaurant.name,
        address=restaurant.address,
        ownerUserId=owner.id,
        ownerPermissions=[p.value for p in StaffPermission],
    )


@router.post("/couriers", status_code=201)
async def assign_courier(
    request: AdminAssignCourierRequestDto,
    db: AsyncSession = Depends(get_db),
    _caller: User = Depends(require_superadmin),
):
    result = await db.execute(select(User).where(User.id == request.userId))
    user = result.scalars().first()
    if not user:
        raise HTTPException(404, "User not found")

    existing = await db.execute(select(Courier).where(Courier.user_id == user.id))
    if existing.scalars().first():
        raise HTTPException(409, "User is already assigned as courier")

    courier = Courier(user_id=user.id)
    db.add(courier)
    await db.flush()

    return AdminCourierDto(
        courierId=courier.id, userId=user.id,
        username=user.username, phone=user.phone, email=user.email,
    )


@router.post("/restaurants/{restaurant_id}/staff", status_code=201)
async def assign_staff(
    restaurant_id: int,
    request: AdminAssignStaffRequestDto,
    db: AsyncSession = Depends(get_db),
    _caller: User = Depends(require_superadmin),
):
    if not request.permission:
        raise HTTPException(400, "permission is required")

    result = await db.execute(select(Restaurant).where(Restaurant.id == restaurant_id))
    if not result.scalars().first():
        raise HTTPException(404, "Restaurant not found")

    result = await db.execute(select(User).where(User.id == request.userId))
    user = result.scalars().first()
    if not user:
        raise HTTPException(404, "User not found")

    try:
        perm = StaffPermission(request.permission)
    except ValueError:
        raise HTTPException(400, f"Invalid permission: {request.permission}")

    existing = await db.execute(
        select(Staff).where(
            Staff.user_id == user.id,
            Staff.restaurant_id == restaurant_id,
            Staff.permission == perm,
        )
    )
    if existing.scalars().first():
        raise HTTPException(409, "Staff permission already assigned")

    s = Staff(user_id=user.id, restaurant_id=restaurant_id, permission=perm)
    db.add(s)
    await db.flush()

    return _staff_dto(s)


@router.delete("/couriers/{courier_id}", status_code=204)
async def remove_courier(
    courier_id: int,
    db: AsyncSession = Depends(get_db),
    _caller: User = Depends(require_superadmin),
):
    result = await db.execute(select(Courier).where(Courier.id == courier_id))
    c = result.scalars().first()
    if not c:
        raise HTTPException(404, "Courier not found")
    await db.delete(c)


@router.get("/orders", response_model=list[AdminOrderSummaryDto])
async def admin_list_orders(
    db: AsyncSession = Depends(get_db),
    _caller: User = Depends(require_superadmin),
    q: str | None = None,
):
    stmt = (
        select(Order)
        .options(joinedload(Order.user), joinedload(Order.restaurant))
        .order_by(Order.created_at.desc())
    )
    raw = (q or "").strip()
    if raw:
        conds = [Restaurant.name.ilike(f"%{raw}%")]
        if raw.isdigit():
            n = int(raw)
            conds.extend(
                [
                    Order.id == n,
                    Order.user_id == n,
                    Order.restaurant_id == n,
                ]
            )
        stmt = stmt.join(Restaurant, Order.restaurant_id == Restaurant.id).where(or_(*conds))
    result = await db.execute(stmt)
    rows = result.unique().scalars().all()
    return [
        AdminOrderSummaryDto(
            id=o.id,
            status=o.status.value,
            createdAt=o.created_at,
            updatedAt=o.updated_at,
            orderType=o.order_type.value,
            restaurantId=o.restaurant_id,
            restaurantName=o.restaurant.name,
            userId=o.user_id,
            username=o.user.username,
            total=o.total,
        )
        for o in rows
    ]


@router.get("/orders/{order_id}", response_model=AdminOrderDetailDto)
async def admin_order_detail(
    order_id: int,
    db: AsyncSession = Depends(get_db),
    _caller: User = Depends(require_superadmin),
):
    result = await db.execute(
        select(Order)
        .options(joinedload(Order.user), joinedload(Order.restaurant))
        .where(Order.id == order_id)
    )
    o = result.unique().scalars().first()
    if not o:
        raise HTTPException(404, "Order not found")
    pos_result = await db.execute(
        select(OrderPosition)
        .options(joinedload(OrderPosition.meal), selectinload(OrderPosition.unit_weights))
        .where(OrderPosition.order_id == order_id)
    )
    positions = [
        AdminOrderPositionLineDto(
            mealName=p.meal.name,
            mealWeight=p.meal.weight,
            finalWeightGrams=p.final_weight_grams,
            finalWeightGramsList=[w.weight_grams for w in (p.unit_weights or [])],
            quantity=p.quantity,
            unitPrice=p.unit_price,
            totalPrice=p.total_price,
        )
        for p in pos_result.unique().scalars().all()
    ]
    return AdminOrderDetailDto(
        id=o.id,
        status=o.status.value,
        createdAt=o.created_at,
        updatedAt=o.updated_at,
        orderType=o.order_type.value,
        deliveryAddress=o.delivery_address,
        tableNumber=o.table_number,
        restaurantId=o.restaurant_id,
        restaurantName=o.restaurant.name,
        userId=o.user_id,
        username=o.user.username,
        phone=o.user.phone,
        itemsTotal=o.items_total,
        deliveryFee=o.delivery_fee,
        serviceFee=o.service_fee,
        total=o.total,
        positions=positions,
    )


@router.get("/stats/summary", response_model=AdminStatsSummaryDto)
async def admin_stats_summary(
    db: AsyncSession = Depends(get_db),
    _caller: User = Depends(require_superadmin),
):
    users_n = int(await db.scalar(select(func.count()).select_from(User)) or 0)
    rest_n = int(await db.scalar(select(func.count()).select_from(Restaurant)) or 0)
    orders_n = int(await db.scalar(select(func.count()).select_from(Order)) or 0)
    return AdminStatsSummaryDto(users=users_n, restaurants=rest_n, orders=orders_n)


@router.patch("/users/{user_id}/status")
async def set_user_active(
    user_id: int,
    body: AdminSetActiveDto,
    db: AsyncSession = Depends(get_db),
    _caller: User = Depends(require_superadmin),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalars().first()
    if not user:
        raise HTTPException(404, "User not found")
    user.is_active = body.isActive
    await db.flush()
    return {"ok": True}


@router.delete("/users/{user_id}", status_code=204)
async def delete_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    _caller: User = Depends(require_superadmin),
):
    n_orders = await db.scalar(select(func.count()).select_from(Order).where(Order.user_id == user_id))
    if n_orders and int(n_orders) > 0:
        raise HTTPException(
            409,
            "У пользователя есть заказы. Отключите аккаунт вместо удаления.",
        )
    await db.execute(delete(Staff).where(Staff.user_id == user_id))
    await db.execute(delete(Courier).where(Courier.user_id == user_id))
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalars().first()
    if not user:
        raise HTTPException(404, "User not found")
    await db.delete(user)


@router.patch("/restaurants/{restaurant_id}/status")
async def set_restaurant_active(
    restaurant_id: int,
    body: AdminSetActiveDto,
    db: AsyncSession = Depends(get_db),
    _caller: User = Depends(require_superadmin),
):
    result = await db.execute(select(Restaurant).where(Restaurant.id == restaurant_id))
    r = result.scalars().first()
    if not r:
        raise HTTPException(404, "Restaurant not found")
    r.is_active = body.isActive
    await db.flush()
    return {"ok": True}


@router.delete("/restaurants/{restaurant_id}", status_code=204)
async def delete_restaurant(
    restaurant_id: int,
    db: AsyncSession = Depends(get_db),
    _caller: User = Depends(require_superadmin),
):
    n_orders = await db.scalar(
        select(func.count()).select_from(Order).where(Order.restaurant_id == restaurant_id)
    )
    if n_orders and int(n_orders) > 0:
        raise HTTPException(
            409,
            "У магазина есть заказы. Деактивируйте вместо удаления.",
        )
    await db.execute(delete(SubscriptionLog).where(SubscriptionLog.restaurant_id == restaurant_id))
    await db.execute(delete(Meal).where(Meal.restaurant_id == restaurant_id))
    await db.execute(delete(Staff).where(Staff.restaurant_id == restaurant_id))
    result = await db.execute(select(Restaurant).where(Restaurant.id == restaurant_id))
    r = result.scalars().first()
    if not r:
        raise HTTPException(404, "Restaurant not found")
    await db.delete(r)


@router.delete("/restaurants/{restaurant_id}/analytics", status_code=204)
async def reset_restaurant_analytics(
    restaurant_id: int,
    db: AsyncSession = Depends(get_db),
    _caller: User = Depends(require_superadmin),
):
    restaurant = (
        await db.execute(select(Restaurant).where(Restaurant.id == restaurant_id))
    ).scalars().first()
    if not restaurant:
        raise HTTPException(404, "Restaurant not found")

    order_ids = list(
        (
            await db.execute(select(Order.id).where(Order.restaurant_id == restaurant_id))
        )
        .scalars()
        .all()
    )

    if order_ids:
        await db.execute(delete(OrderPosition).where(OrderPosition.order_id.in_(order_ids)))
        await db.execute(delete(Order).where(Order.id.in_(order_ids)))
