from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import select, update as sa_update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.config import get_settings
from app.database import get_db
from app.models.courier import Courier
from app.models.order import Order
from app.models.staff import Staff
from app.models.user import User
from app.schemas.user import UserDto, UserRestaurantDto
from app.services.phone_norm import normalize_phone_to_storage
from app.services.session_auth import ensure_customer, get_user_from_bearer
from app.services.telegram_auth import verify_bot_link_token, verify_telegram_init_data

router = APIRouter(prefix="/api/v1/users", tags=["users"])


def _to_dto(u: User) -> UserDto:
    return UserDto(
        id=u.id, username=u.username, phone=u.phone,
        email=u.email, address=u.address, registeredAt=u.registered_at,
    )


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


async def _require_customer_id(
    db: AsyncSession,
    init_data: str,
    bot_auth_token: str | None = None,
) -> int:
    settings = get_settings()
    tid: int | None = None
    username: str | None = None

    if init_data:
        tg = verify_telegram_init_data(init_data, settings.user_bot_token)
        if tg and tg.get("id") is not None:
            tid = int(tg["id"])
            username = tg.get("username")

    if tid is None and bot_auth_token:
        tid = verify_bot_link_token(bot_auth_token, settings.user_bot_token)

    if tid is None:
        raise HTTPException(401, "Invalid Telegram init data")

    user = await ensure_customer(db, tid, username)
    return user.id


async def _list_restaurants_for_staff(db: AsyncSession, user_id: int) -> list[UserRestaurantDto]:
    result = await db.execute(
        select(Staff).options(joinedload(Staff.restaurant)).where(Staff.user_id == user_id)
    )
    staff_list = result.unique().scalars().all()
    grouped: dict[int, list[Staff]] = {}
    for s in staff_list:
        grouped.setdefault(s.restaurant_id, []).append(s)
    restaurants = []
    for assignments in grouped.values():
        first = assignments[0]
        restaurants.append(UserRestaurantDto(
            id=first.restaurant.id, name=first.restaurant.name,
            address=first.restaurant.address,
            permissions=list({s.permission.value for s in assignments}),
        ))
    restaurants.sort(key=lambda r: r.name)
    return restaurants


@router.get("")
async def get_all(
    phone: str | None = None,
    username: str | None = None,
    telegramId: int | None = None,
    db: AsyncSession = Depends(get_db),
):
    if telegramId is not None:
        result = await db.execute(select(User).where(User.id == telegramId))
        u = result.scalars().first()
        return [_to_dto(u)] if u else []
    if phone:
        lookup_phone = normalize_phone_to_storage(phone) or phone
        result = await db.execute(select(User).where(User.phone == lookup_phone))
        u = result.scalars().first()
        return [_to_dto(u)] if u else []
    if username:
        result = await db.execute(select(User).where(User.username == username))
        u = result.scalars().first()
        return [_to_dto(u)] if u else []
    result = await db.execute(select(User))
    return [_to_dto(u) for u in result.scalars().all()]


@router.get("/{user_id}")
async def get_by_id(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    authorization: str | None = Header(None, alias="Authorization"),
    x_telegram_init_data: str | None = Header(None, alias="X-Telegram-Init-Data"),
    x_init_data: str | None = Header(None, alias="X-Init-Data"),
    x_kulcha_bot_auth: str | None = Header(None, alias="X-Market-Bot-Auth"),
):
    bearer_user = await get_user_from_bearer(db, authorization)
    if bearer_user:
        if bearer_user.id != user_id:
            raise HTTPException(403, "Cannot access another user")
        return _to_dto(bearer_user)

    init_data = (x_telegram_init_data or x_init_data or "").strip()
    try:
        admin = await _require_admin_user(db, init_data)
        rests = await _list_restaurants_for_staff(db, admin.id)
        if not rests:
            raise HTTPException(403, "Not a staff member")
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalars().first()
        if not user:
            raise HTTPException(404, "User not found")
        return _to_dto(user)
    except HTTPException as ex:
        if ex.status_code != 401:
            raise

    db_id = await _require_customer_id(db, init_data, x_kulcha_bot_auth)
    if db_id != user_id:
        raise HTTPException(403, "Cannot access another user")
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalars().first()
    if not user:
        raise HTTPException(404, "User not found")
    return _to_dto(user)


@router.get("/{user_id}/my-restaurants")
async def get_my_restaurants(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    x_telegram_init_data: str = Header(..., alias="X-Telegram-Init-Data"),
):
    admin = await _require_admin_user(db, x_telegram_init_data)
    if admin.id != user_id:
        raise HTTPException(403, "Cannot access another user")
    return await _list_restaurants_for_staff(db, user_id)


@router.post("", status_code=201)
async def create_user(
    dto: UserDto,
    db: AsyncSession = Depends(get_db),
    x_kulcha_bot_secret: str | None = Header(None, alias="X-Market-Bot-Secret"),
):
    settings = get_settings()
    want = settings.bot_api_secret
    if want:
        if not x_kulcha_bot_secret or x_kulcha_bot_secret != want:
            raise HTTPException(401, "Invalid bot API secret")

    tg_id = dto.id
    if tg_id is None:
        raise HTTPException(400, "id (Telegram) is required")

    result = await db.execute(select(User).where(User.id == tg_id))
    existing = result.scalars().first()
    normalized_phone = normalize_phone_to_storage(dto.phone or "") if dto.phone else None
    if dto.phone and not normalized_phone:
        raise HTTPException(400, "Некорректный номер телефона")

    if existing:
        existing.username = dto.username or existing.username
        if normalized_phone and normalized_phone != existing.phone:
            result = await db.execute(select(User).where(User.phone == normalized_phone))
            legacy = result.scalars().first()
            if legacy and legacy.id != existing.id:
                await db.execute(sa_update(Order).where(Order.user_id == legacy.id).values(user_id=existing.id))
                await db.execute(sa_update(Staff).where(Staff.user_id == legacy.id).values(user_id=existing.id))
                await db.execute(sa_update(Courier).where(Courier.user_id == legacy.id).values(user_id=existing.id))
                await db.delete(legacy)
                await db.flush()
        existing.phone = normalized_phone or existing.phone
        if dto.email is not None:
            existing.email = dto.email
        if dto.address is not None:
            existing.address = dto.address
        await db.flush()
        return _to_dto(existing)

    if normalized_phone:
        result = await db.execute(select(User).where(User.phone == normalized_phone))
        legacy = result.scalars().first()
        if legacy and legacy.id != tg_id:
            await db.execute(sa_update(Order).where(Order.user_id == legacy.id).values(user_id=tg_id))
            await db.execute(sa_update(Staff).where(Staff.user_id == legacy.id).values(user_id=tg_id))
            await db.execute(sa_update(Courier).where(Courier.user_id == legacy.id).values(user_id=tg_id))
            await db.delete(legacy)
            await db.flush()

    user = User(
        id=tg_id,
        username=dto.username or f"tg_{tg_id}",
        phone=normalized_phone or f"tg-{tg_id}",
        email=dto.email,
        address=dto.address,
        registered_at=dto.registeredAt or datetime.now(),
    )
    db.add(user)
    await db.flush()
    return _to_dto(user)


@router.put("/{user_id}")
async def update_user(
    user_id: int,
    dto: UserDto,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalars().first()
    if not user:
        raise HTTPException(404, "User not found")
    if dto.username is not None:
        user.username = dto.username
    if dto.phone is not None:
        norm = normalize_phone_to_storage(dto.phone)
        if not norm:
            raise HTTPException(400, "Некорректный номер телефона")
        duplicate = await db.execute(select(User).where(User.phone == norm, User.id != user_id))
        if duplicate.scalars().first():
            raise HTTPException(409, "Этот номер телефона уже используется")
        user.phone = norm
    if dto.email is not None:
        user.email = dto.email
    if dto.address is not None:
        user.address = dto.address
    if dto.registeredAt is not None:
        user.registered_at = dto.registeredAt
    await db.flush()
    return _to_dto(user)


@router.delete("/{user_id}", status_code=204)
async def delete_user(user_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalars().first()
    if user:
        await db.delete(user)
