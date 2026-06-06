from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.database import get_db
from app.models.subscription_log import SubscriptionLog
from app.schemas.subscription_log import SubscriptionLogDto

router = APIRouter(prefix="/api/v1/subscription-logs", tags=["subscription-logs"])


def _to_dto(log: SubscriptionLog) -> SubscriptionLogDto:
    return SubscriptionLogDto(
        id=log.id, restaurantId=log.restaurant_id,
        price=log.price, startDttm=log.start_dttm, endDttm=log.end_dttm,
    )


@router.get("")
async def get_all(
    restaurantId: int | None = None,
    activeOnly: bool = False,
    db: AsyncSession = Depends(get_db),
):
    if activeOnly:
        now = datetime.now()
        result = await db.execute(
            select(SubscriptionLog)
            .options(joinedload(SubscriptionLog.restaurant))
            .where(SubscriptionLog.end_dttm > now)
        )
        return [_to_dto(l) for l in result.unique().scalars().all()]

    if restaurantId is not None:
        result = await db.execute(
            select(SubscriptionLog)
            .options(joinedload(SubscriptionLog.restaurant))
            .where(SubscriptionLog.restaurant_id == restaurantId)
        )
        return [_to_dto(l) for l in result.unique().scalars().all()]

    result = await db.execute(
        select(SubscriptionLog).options(joinedload(SubscriptionLog.restaurant))
    )
    return [_to_dto(l) for l in result.unique().scalars().all()]


@router.get("/{log_id}")
async def get_by_id(log_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(SubscriptionLog)
        .options(joinedload(SubscriptionLog.restaurant))
        .where(SubscriptionLog.id == log_id)
    )
    log = result.unique().scalars().first()
    if not log:
        raise HTTPException(404, "Subscription log not found")
    return _to_dto(log)


@router.post("", status_code=201)
async def create_log(dto: SubscriptionLogDto, db: AsyncSession = Depends(get_db)):
    log = SubscriptionLog(
        restaurant_id=dto.restaurantId,
        price=dto.price, start_dttm=dto.startDttm, end_dttm=dto.endDttm,
    )
    db.add(log)
    await db.flush()
    return _to_dto(log)


@router.put("/{log_id}")
async def update_log(log_id: int, dto: SubscriptionLogDto, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(SubscriptionLog).where(SubscriptionLog.id == log_id))
    existing = result.scalars().first()
    if not existing:
        raise HTTPException(404, "Subscription log not found")
    if dto.restaurantId is not None:
        existing.restaurant_id = dto.restaurantId
    if dto.price is not None:
        existing.price = dto.price
    if dto.startDttm is not None:
        existing.start_dttm = dto.startDttm
    if dto.endDttm is not None:
        existing.end_dttm = dto.endDttm
    await db.flush()
    return _to_dto(existing)


@router.delete("/{log_id}", status_code=204)
async def delete_log(log_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(SubscriptionLog).where(SubscriptionLog.id == log_id))
    log = result.scalars().first()
    if log:
        await db.delete(log)
