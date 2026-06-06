from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.database import get_db
from app.models.enums import StaffPermission
from app.models.staff import Staff
from app.schemas.staff import StaffDto

router = APIRouter(prefix="/api/v1/staff", tags=["staff"])


def _to_dto(s: Staff) -> StaffDto:
    return StaffDto(
        id=s.id, userId=s.user_id,
        restaurantId=s.restaurant_id, permission=s.permission.value,
    )


@router.get("")
async def get_all(
    userId: int | None = None,
    restaurantId: int | None = None,
    permission: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    query = select(Staff).options(joinedload(Staff.user), joinedload(Staff.restaurant))
    if userId is not None:
        query = query.where(Staff.user_id == userId)
    elif restaurantId is not None:
        query = query.where(Staff.restaurant_id == restaurantId)
    elif permission is not None:
        try:
            perm = StaffPermission(permission)
        except ValueError:
            raise HTTPException(400, f"Invalid permission: {permission}")
        query = query.where(Staff.permission == perm)
    result = await db.execute(query)
    return [_to_dto(s) for s in result.unique().scalars().all()]


@router.get("/{staff_id}")
async def get_by_id(staff_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Staff).options(joinedload(Staff.user), joinedload(Staff.restaurant))
        .where(Staff.id == staff_id)
    )
    s = result.unique().scalars().first()
    if not s:
        raise HTTPException(404, "Staff not found")
    return _to_dto(s)


@router.post("", status_code=201)
async def create_staff(dto: StaffDto, db: AsyncSession = Depends(get_db)):
    if not dto.userId:
        raise HTTPException(400, "userId is required")
    if not dto.restaurantId:
        raise HTTPException(400, "restaurantId is required")
    if not dto.permission:
        raise HTTPException(400, "permission is required")

    s = Staff(
        user_id=dto.userId, restaurant_id=dto.restaurantId,
        permission=StaffPermission(dto.permission),
    )
    db.add(s)
    await db.flush()
    return _to_dto(s)


@router.put("/{staff_id}")
async def update_staff(staff_id: int, dto: StaffDto, db: AsyncSession = Depends(get_db)):
    if not dto.userId:
        raise HTTPException(400, "userId is required")
    if not dto.restaurantId:
        raise HTTPException(400, "restaurantId is required")
    if not dto.permission:
        raise HTTPException(400, "permission is required")

    result = await db.execute(select(Staff).where(Staff.id == staff_id))
    existing = result.scalars().first()
    if not existing:
        raise HTTPException(404, "Staff not found")
    existing.user_id = dto.userId
    existing.restaurant_id = dto.restaurantId
    existing.permission = StaffPermission(dto.permission)
    await db.flush()
    return _to_dto(existing)


@router.delete("/{staff_id}", status_code=204)
async def delete_staff(staff_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Staff).where(Staff.id == staff_id))
    s = result.scalars().first()
    if s:
        await db.delete(s)
