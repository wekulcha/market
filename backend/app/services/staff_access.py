from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import StaffPermission
from app.models.staff import Staff


async def require_restaurant_staff(db: AsyncSession, user_id: int, restaurant_id: int) -> None:
    result = await db.execute(
        select(Staff).where(Staff.user_id == user_id, Staff.restaurant_id == restaurant_id)
    )
    if not result.scalars().first():
        raise HTTPException(403, "No access to this restaurant")


async def require_can_edit_menu(db: AsyncSession, user_id: int, restaurant_id: int) -> None:
    result = await db.execute(
        select(Staff).where(
            Staff.user_id == user_id,
            Staff.restaurant_id == restaurant_id,
            Staff.permission == StaffPermission.CAN_EDIT_MENU,
        )
    )
    if not result.scalars().first():
        raise HTTPException(403, "Cannot edit menu for this restaurant")
