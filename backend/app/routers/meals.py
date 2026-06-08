from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import func, select, update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.config import get_settings
from app.database import get_db
from app.models.enums import MealCategory
from app.models.meal import Meal
from app.models.order_position import OrderPosition
from app.models.restaurant import Restaurant
from app.models.user import User
from app.schemas.meal import MealCategoryAvailabilityPatchDto, MealDto
from app.services import staff_access
from app.services.telegram_auth import verify_telegram_init_data

router = APIRouter(prefix="/api/v1/meals", tags=["meals"])


def _raise_meal_category_db_error(exc: DBAPIError) -> None:
    message = str(exc).lower()
    if (
        "invalid input value for enum" in message
        or "mealcategory" in message
        or "meal_category_check" in message
        or "checkviolationerror" in message
    ):
        raise HTTPException(
            400,
            "Категория товара не поддерживается текущей схемой БД. Примените последние миграции backend.",
        ) from exc
    raise exc


def _to_dto(m: Meal) -> MealDto:
    return MealDto(
        id=m.id, restaurantId=m.restaurant_id, name=m.name,
        description=m.description, weight=m.weight, calorie=m.calorie,
        imageLink=m.image_link, category=m.category,
        price=m.price, available=m.is_available,
    )


async def _require_menu_editor(db: AsyncSession, init_data: str, restaurant_id: int) -> None:
    settings = get_settings()
    tg = verify_telegram_init_data(init_data, settings.admin_bot_token)
    if not tg:
        raise HTTPException(401, "Invalid Telegram init data")
    result = await db.execute(select(User).where(User.id == tg["id"]))
    u = result.scalars().first()
    if not u:
        raise HTTPException(403, "Unknown user")
    await staff_access.require_can_edit_menu(db, u.id, restaurant_id)


@router.get("")
async def get_all(
    restaurantId: int | None = None,
    category: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    if restaurantId is not None and category is not None:
        r0 = await db.execute(select(Restaurant).where(Restaurant.id == restaurantId))
        rrest = r0.scalars().first()
        if not rrest or not rrest.is_active:
            return []
        try:
            cat = MealCategory(category)
        except ValueError:
            raise HTTPException(400, f"Invalid category: {category}")
        result = await db.execute(
            select(Meal).where(
                Meal.restaurant_id == restaurantId,
                Meal.is_available == True,  # noqa: E712
                Meal.category == cat.value,
            )
        )
        return [_to_dto(m) for m in result.scalars().all()]

    if restaurantId is not None:
        r0 = await db.execute(select(Restaurant).where(Restaurant.id == restaurantId))
        rrest = r0.scalars().first()
        if not rrest or not rrest.is_active:
            return []
        result = await db.execute(
            select(Meal).where(Meal.restaurant_id == restaurantId, Meal.is_available == True)  # noqa: E712
        )
        return [_to_dto(m) for m in result.scalars().all()]

    result = await db.execute(select(Meal))
    return [_to_dto(m) for m in result.scalars().all()]


@router.get("/{meal_id}")
async def get_by_id(meal_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Meal).options(joinedload(Meal.restaurant)).where(Meal.id == meal_id)
    )
    m = result.unique().scalars().first()
    if not m:
        raise HTTPException(404, "Meal not found")
    return _to_dto(m)


@router.post("", status_code=201)
async def create_meal(
    dto: MealDto,
    db: AsyncSession = Depends(get_db),
    x_telegram_init_data: str = Header(..., alias="X-Telegram-Init-Data"),
):
    await _require_menu_editor(db, x_telegram_init_data, dto.restaurantId)
    category_value = MealCategory(dto.category).value if dto.category else None
    meal = Meal(
        restaurant_id=dto.restaurantId, name=dto.name,
        description=dto.description, weight=dto.weight, calorie=dto.calorie,
        image_link=(dto.imageLink or "").strip() or None,
        category=category_value,
        price=dto.price, is_available=dto.available if dto.available is not None else True,
    )
    db.add(meal)
    try:
        await db.flush()
    except DBAPIError as exc:
        _raise_meal_category_db_error(exc)
    return _to_dto(meal)


@router.put("/{meal_id}")
async def update_meal(
    meal_id: int,
    dto: MealDto,
    db: AsyncSession = Depends(get_db),
    x_telegram_init_data: str = Header(..., alias="X-Telegram-Init-Data"),
):
    result = await db.execute(
        select(Meal).options(joinedload(Meal.restaurant)).where(Meal.id == meal_id)
    )
    existing = result.unique().scalars().first()
    if not existing:
        raise HTTPException(404, "Meal not found")
    await _require_menu_editor(db, x_telegram_init_data, existing.restaurant_id)

    if dto.name is not None:
        existing.name = dto.name
    if dto.description is not None:
        existing.description = dto.description
    if dto.weight is not None:
        existing.weight = dto.weight
    if dto.calorie is not None:
        existing.calorie = dto.calorie
    if "imageLink" in dto.model_fields_set:
        existing.image_link = (dto.imageLink or "").strip() or None
    if dto.category is not None:
        existing.category = MealCategory(dto.category).value
    if dto.price is not None:
        existing.price = dto.price
    if dto.available is not None:
        existing.is_available = dto.available
    if dto.restaurantId is not None:
        existing.restaurant_id = dto.restaurantId

    try:
        await db.flush()
    except DBAPIError as exc:
        _raise_meal_category_db_error(exc)
    return _to_dto(existing)


@router.patch("/category-availability")
async def update_category_availability(
    dto: MealCategoryAvailabilityPatchDto,
    db: AsyncSession = Depends(get_db),
    x_telegram_init_data: str = Header(..., alias="X-Telegram-Init-Data"),
):
    await _require_menu_editor(db, x_telegram_init_data, dto.restaurantId)
    try:
        category_value = MealCategory(dto.category).value
    except ValueError as exc:
        raise HTTPException(400, f"Invalid category: {dto.category}") from exc

    await db.execute(
        update(Meal)
        .where(
            Meal.restaurant_id == dto.restaurantId,
            Meal.category == category_value,
        )
        .values(is_available=dto.available)
    )

    result = await db.execute(
        select(Meal).where(
            Meal.restaurant_id == dto.restaurantId,
            Meal.category == category_value,
        )
    )
    return [_to_dto(meal) for meal in result.scalars().all()]


@router.delete("/{meal_id}", status_code=204)
async def delete_meal(
    meal_id: int,
    db: AsyncSession = Depends(get_db),
    x_telegram_init_data: str = Header(..., alias="X-Telegram-Init-Data"),
):
    result = await db.execute(
        select(Meal).options(joinedload(Meal.restaurant)).where(Meal.id == meal_id)
    )
    existing = result.unique().scalars().first()
    if not existing:
        raise HTTPException(404, "Meal not found")
    await _require_menu_editor(db, x_telegram_init_data, existing.restaurant_id)
    cnt = await db.execute(
        select(func.count()).select_from(OrderPosition).where(OrderPosition.meal_id == meal_id)
    )
    if (cnt.scalar() or 0) > 0:
        raise HTTPException(400, "Нельзя удалить товар: он уже встречается в заказах.")
    await db.delete(existing)
