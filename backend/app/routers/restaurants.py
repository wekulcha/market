from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import select, true
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.config import get_settings
from app.database import get_db
from app.models.enums import MealCategory
from app.models.meal import Meal
from app.models.restaurant import Restaurant
from app.models.user import User
from app.schemas.meal import MealDto
from app.schemas.restaurant import RestaurantDto, RestaurantPatchDto
from app.services import staff_access
from app.services.telegram_auth import verify_telegram_init_data

router = APIRouter(prefix="/api/v1/restaurants", tags=["restaurants"])


def _normalize_group_chat_id(chat_id: int | None) -> int | None:
    if chat_id is None:
        return None
    if chat_id > 0:
        # Админ вводит peer/group id без префикса, Telegram Bot API ожидает -100...
        return -int(f"100{chat_id}")
    return chat_id


def _to_dto(r: Restaurant) -> RestaurantDto:
    return RestaurantDto(
        id=r.id,
        name=r.name,
        address=r.address,
        imageLink=r.image_link,
        workingHoursFrom=r.working_hours_from,
        workingHoursTo=r.working_hours_to,
        ordersAcceptFrom=r.orders_accept_from,
        ordersAcceptTo=r.orders_accept_to,
        telegramGroupChatId=r.telegram_group_chat_id,
    )


def _meal_dto(m: Meal) -> MealDto:
    return MealDto(
        id=m.id, restaurantId=m.restaurant_id, name=m.name,
        description=m.description, weight=m.weight, calorie=m.calorie,
        imageLink=m.image_link, category=m.category,
        price=m.price, requiresFinalWeight=m.requires_final_weight, available=m.is_available,
    )


@router.get("")
async def get_all(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Restaurant).where(Restaurant.is_active == true()))
    return [_to_dto(r) for r in result.scalars().all()]


@router.get("/{restaurant_id}")
async def get_by_id(
    restaurant_id: int,
    db: AsyncSession = Depends(get_db),
    x_telegram_init_data: str | None = Header(None, alias="X-Telegram-Init-Data"),
):
    result = await db.execute(select(Restaurant).where(Restaurant.id == restaurant_id))
    r = result.scalars().first()
    if not r:
        raise HTTPException(404, "Restaurant not found")
    if r.is_active:
        return _to_dto(r)
    if x_telegram_init_data:
        settings = get_settings()
        tg = verify_telegram_init_data(x_telegram_init_data, settings.admin_bot_token)
        if tg:
            result_u = await db.execute(select(User).where(User.id == tg["id"]))
            u = result_u.scalars().first()
            if u:
                await staff_access.require_restaurant_staff(db, u.id, restaurant_id)
                return _to_dto(r)
    raise HTTPException(404, "Restaurant not found")


@router.patch("/{restaurant_id}")
async def patch_restaurant(
    restaurant_id: int,
    body: RestaurantPatchDto,
    db: AsyncSession = Depends(get_db),
    x_telegram_init_data: str = Header(..., alias="X-Telegram-Init-Data"),
):
    settings = get_settings()
    tg = verify_telegram_init_data(x_telegram_init_data, settings.admin_bot_token)
    if not tg:
        raise HTTPException(401, "Invalid Telegram init data")
    result = await db.execute(select(User).where(User.id == tg["id"]))
    u = result.scalars().first()
    if not u:
        raise HTTPException(403, "Unknown user")
    await staff_access.require_can_edit_menu(db, u.id, restaurant_id)

    result = await db.execute(select(Restaurant).where(Restaurant.id == restaurant_id))
    r = result.scalars().first()
    if not r:
        raise HTTPException(404, "Restaurant not found")

    if body.name is not None:
        r.name = body.name.strip()
    if body.address is not None:
        r.address = body.address.strip()
    if body.imageLink is not None:
        r.image_link = body.imageLink.strip() or None
    if body.workingHoursFrom is not None:
        v = body.workingHoursFrom.strip() or None
        r.working_hours_from = v
    if body.workingHoursTo is not None:
        v = body.workingHoursTo.strip() or None
        r.working_hours_to = v
    if body.ordersAcceptFrom is not None:
        v = body.ordersAcceptFrom.strip() or None
        r.orders_accept_from = v
    if body.ordersAcceptTo is not None:
        v = body.ordersAcceptTo.strip() or None
        r.orders_accept_to = v
    if "telegramGroupChatId" in body.model_fields_set:
        r.telegram_group_chat_id = _normalize_group_chat_id(body.telegramGroupChatId)
    await db.flush()
    return _to_dto(r)


@router.get("/{restaurant_id}/meals")
async def get_meals(
    restaurant_id: int,
    category: str | None = None,
    availableOnly: bool = True,
    db: AsyncSession = Depends(get_db),
    x_telegram_init_data: str | None = Header(None, alias="X-Telegram-Init-Data"),
):
    result = await db.execute(select(Restaurant).where(Restaurant.id == restaurant_id))
    r = result.scalars().first()
    if not r:
        raise HTTPException(404, "Restaurant not found")
    if not r.is_active:
        if availableOnly:
            raise HTTPException(404, "Restaurant not found")
        if not x_telegram_init_data:
            raise HTTPException(404, "Restaurant not found")
        settings = get_settings()
        tg = verify_telegram_init_data(x_telegram_init_data, settings.admin_bot_token)
        if not tg:
            raise HTTPException(404, "Restaurant not found")
        result_u = await db.execute(select(User).where(User.id == tg["id"]))
        u = result_u.scalars().first()
        if not u:
            raise HTTPException(404, "Restaurant not found")
        await staff_access.require_restaurant_staff(db, u.id, restaurant_id)

    if not availableOnly:
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
        await staff_access.require_restaurant_staff(db, u.id, restaurant_id)

    query = select(Meal).where(Meal.restaurant_id == restaurant_id)
    if availableOnly:
        query = query.where(Meal.is_available == True)  # noqa: E712
    if category:
        try:
            cat = MealCategory(category)
        except ValueError:
            raise HTTPException(400, f"Invalid category: {category}")
        query = query.where(Meal.category == cat.value)

    result = await db.execute(query)
    return [_meal_dto(m) for m in result.scalars().all()]
