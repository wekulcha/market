from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.database import get_db
from app.models.courier import Courier
from app.schemas.courier import CourierDto

router = APIRouter(prefix="/api/v1/couriers", tags=["couriers"])


def _to_dto(c: Courier) -> CourierDto:
    return CourierDto(id=c.id, userId=c.user_id)


@router.get("")
async def get_all(userId: int | None = None, db: AsyncSession = Depends(get_db)):
    if userId is not None:
        result = await db.execute(
            select(Courier).options(joinedload(Courier.user)).where(Courier.user_id == userId)
        )
        c = result.unique().scalars().first()
        return [_to_dto(c)] if c else []
    result = await db.execute(select(Courier).options(joinedload(Courier.user)))
    return [_to_dto(c) for c in result.unique().scalars().all()]


@router.get("/{courier_id}")
async def get_by_id(courier_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Courier).options(joinedload(Courier.user)).where(Courier.id == courier_id)
    )
    c = result.unique().scalars().first()
    if not c:
        raise HTTPException(404, "Courier not found")
    return _to_dto(c)


@router.post("", status_code=201)
async def create_courier(dto: CourierDto, db: AsyncSession = Depends(get_db)):
    if not dto.userId:
        raise HTTPException(400, "userId is required")
    existing = await db.execute(select(Courier).where(Courier.user_id == dto.userId))
    if existing.scalars().first():
        raise HTTPException(409, "User is already assigned as courier")
    c = Courier(user_id=dto.userId)
    db.add(c)
    await db.flush()
    return _to_dto(c)


@router.put("/{courier_id}")
async def update_courier(courier_id: int, dto: CourierDto, db: AsyncSession = Depends(get_db)):
    if not dto.userId:
        raise HTTPException(400, "userId is required")
    result = await db.execute(
        select(Courier).options(joinedload(Courier.user)).where(Courier.id == courier_id)
    )
    existing = result.unique().scalars().first()
    if not existing:
        raise HTTPException(404, "Courier not found")
    if existing.user_id != dto.userId:
        dup = await db.execute(select(Courier).where(Courier.user_id == dto.userId))
        if dup.scalars().first():
            raise HTTPException(409, "User is already assigned as courier")
    existing.user_id = dto.userId
    await db.flush()
    return _to_dto(existing)


@router.delete("/{courier_id}", status_code=204)
async def delete_courier(courier_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Courier).where(Courier.id == courier_id))
    c = result.scalars().first()
    if c:
        await db.delete(c)
