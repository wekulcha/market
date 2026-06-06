from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.config import get_settings
from app.database import get_db
from app.models.enums import StaffPermission
from app.models.staff import Staff
from app.models.user import User
from app.schemas.staff import AddStaffRequestDto, StaffMemberDto
from app.services.phone_norm import normalize_ru_phone_to_storage
from app.services import staff_access
from app.services.telegram_auth import verify_telegram_init_data

router = APIRouter(prefix="/api/v1/restaurants/{restaurant_id}/staff", tags=["restaurant-staff"])


def _effective_permission(assignments: list[Staff]) -> StaffPermission:
    for assignment in assignments:
        if assignment.permission == StaffPermission.CAN_EDIT_MENU:
            return StaffPermission.CAN_EDIT_MENU
    return StaffPermission.CAN_LOOK_ORDERS


def _to_member(s: Staff) -> StaffMemberDto:
    return StaffMemberDto(
        staffId=s.id, userId=s.user.id,
        username=s.user.username, phone=s.user.phone,
        permission=s.permission.value,
    )


def _group_staff(items: list[Staff]) -> list[StaffMemberDto]:
    grouped: dict[tuple[int, int], list[Staff]] = {}
    for item in items:
        grouped.setdefault((item.user_id, item.restaurant_id), []).append(item)

    members: list[StaffMemberDto] = []
    for assignments in grouped.values():
        assignments.sort(key=lambda assignment: assignment.id)
        primary = assignments[0]
        members.append(
            StaffMemberDto(
                staffId=primary.id,
                userId=primary.user.id,
                username=primary.user.username,
                phone=primary.user.phone,
                permission=_effective_permission(assignments).value,
            )
        )
    members.sort(key=lambda member: (member.username or "", member.userId))
    return members


async def _require_admin_actor(
    db: AsyncSession, init_data: str, restaurant_id: int, menu: bool,
) -> int:
    settings = get_settings()
    tg = verify_telegram_init_data(init_data, settings.admin_bot_token)
    if not tg:
        raise HTTPException(401, "Invalid Telegram init data")
    result = await db.execute(select(User).where(User.id == tg["id"]))
    actor = result.scalars().first()
    if not actor:
        raise HTTPException(403, "Unknown admin user")
    if menu:
        await staff_access.require_can_edit_menu(db, actor.id, restaurant_id)
    else:
        await staff_access.require_restaurant_staff(db, actor.id, restaurant_id)
    return actor.id


@router.get("")
async def list_staff(
    restaurant_id: int,
    db: AsyncSession = Depends(get_db),
    x_telegram_init_data: str = Header(..., alias="X-Telegram-Init-Data"),
):
    await _require_admin_actor(db, x_telegram_init_data, restaurant_id, True)
    result = await db.execute(
        select(Staff)
        .options(joinedload(Staff.user))
        .where(Staff.restaurant_id == restaurant_id)
    )
    return _group_staff(result.unique().scalars().all())


@router.post("", status_code=201)
async def add_staff(
    restaurant_id: int,
    body: AddStaffRequestDto,
    db: AsyncSession = Depends(get_db),
    x_telegram_init_data: str = Header(..., alias="X-Telegram-Init-Data"),
):
    await _require_admin_actor(db, x_telegram_init_data, restaurant_id, True)

    if body.telegramId is not None:
        result = await db.execute(select(User).where(User.id == body.telegramId))
        target = result.scalars().first()
    else:
        norm = normalize_ru_phone_to_storage(body.phone or "")
        if not norm:
            raise HTTPException(400, "Некорректный номер телефона")
        result = await db.execute(select(User).where(User.phone == norm))
        target = result.scalars().first()
    if not target:
        raise HTTPException(
            400,
            "Пользователь не найден. Сначала /start в боте Kulcha Market и номер телефона.",
        )

    try:
        perm = StaffPermission(body.permission)
    except ValueError:
        raise HTTPException(400, f"Invalid permission: {body.permission}")

    existing = await db.execute(
        select(Staff)
        .where(
            Staff.user_id == target.id,
            Staff.restaurant_id == restaurant_id,
        )
        .order_by(Staff.id.asc())
    )
    existing_assignments = existing.scalars().all()
    if existing_assignments and _effective_permission(existing_assignments) == perm:
        raise HTTPException(409, "У сотрудника уже установлен такой доступ")
    for assignment in existing_assignments:
        await db.delete(assignment)

    staff = Staff(user_id=target.id, restaurant_id=restaurant_id, permission=perm)
    db.add(staff)
    await db.flush()

    result = await db.execute(
        select(Staff).options(joinedload(Staff.user)).where(Staff.id == staff.id)
    )
    hydrated = result.unique().scalar_one()
    return _to_member(hydrated)


@router.delete("/{staff_id}", status_code=204)
async def remove_staff(
    restaurant_id: int,
    staff_id: int,
    db: AsyncSession = Depends(get_db),
    x_telegram_init_data: str = Header(..., alias="X-Telegram-Init-Data"),
):
    db_user_id = await _require_admin_actor(db, x_telegram_init_data, restaurant_id, True)

    result = await db.execute(
        select(Staff)
        .options(joinedload(Staff.user), joinedload(Staff.restaurant))
        .where(Staff.id == staff_id)
    )
    s = result.unique().scalars().first()
    if not s:
        raise HTTPException(404, "Staff not found")
    if s.restaurant_id != restaurant_id:
        raise HTTPException(404, "Staff not found")
    if s.user_id == db_user_id:
        raise HTTPException(400, "Нельзя удалить самого себя")
    assignments = await db.execute(
        select(Staff).where(
            Staff.user_id == s.user_id,
            Staff.restaurant_id == restaurant_id,
        )
    )
    for assignment in assignments.scalars().all():
        await db.delete(assignment)
