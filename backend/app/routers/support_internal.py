from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.models.support_ticket import SupportTicket

router = APIRouter(prefix="/api/v1/internal/support", tags=["internal-support"])

TICKET_OPEN = "open"
TICKET_CLOSED = "closed"


class SupportOpenTicketBody(BaseModel):
    userTelegramId: int
    username: str | None = None


class SupportTicketView(BaseModel):
    id: int
    userTelegramId: int
    status: str


def _require_internal(secret: str | None) -> None:
    settings = get_settings()
    if not settings.internal_api_secret or secret != settings.internal_api_secret:
        raise HTTPException(401, "Invalid internal secret")


@router.post("/tickets/open", status_code=201)
async def open_or_get_ticket(
    body: SupportOpenTicketBody,
    db: AsyncSession = Depends(get_db),
    x_kulcha_internal_secret: str | None = Header(None, alias="X-Kulcha-Internal-Secret"),
):
    _require_internal(x_kulcha_internal_secret)
    result = await db.execute(
        select(SupportTicket).where(
            SupportTicket.user_telegram_id == body.userTelegramId,
            SupportTicket.status == TICKET_OPEN,
        )
    )
    existing = result.scalars().first()
    if existing:
        return SupportTicketView(
            id=existing.id,
            userTelegramId=existing.user_telegram_id,
            status=existing.status,
        )
    t = SupportTicket(
        user_telegram_id=body.userTelegramId,
        status=TICKET_OPEN,
        created_at=datetime.now(),
        closed_at=None,
    )
    db.add(t)
    await db.flush()
    return SupportTicketView(id=t.id, userTelegramId=t.user_telegram_id, status=t.status)


@router.get("/tickets/{ticket_id}")
async def get_ticket(
    ticket_id: int,
    db: AsyncSession = Depends(get_db),
    x_kulcha_internal_secret: str | None = Header(None, alias="X-Kulcha-Internal-Secret"),
):
    _require_internal(x_kulcha_internal_secret)
    result = await db.execute(select(SupportTicket).where(SupportTicket.id == ticket_id))
    t = result.scalars().first()
    if not t:
        raise HTTPException(404, "Ticket not found")
    return SupportTicketView(id=t.id, userTelegramId=t.user_telegram_id, status=t.status)


@router.post("/tickets/{ticket_id}/close", status_code=204)
async def close_ticket(
    ticket_id: int,
    db: AsyncSession = Depends(get_db),
    x_kulcha_internal_secret: str | None = Header(None, alias="X-Kulcha-Internal-Secret"),
):
    _require_internal(x_kulcha_internal_secret)
    result = await db.execute(select(SupportTicket).where(SupportTicket.id == ticket_id))
    t = result.scalars().first()
    if not t:
        raise HTTPException(404, "Ticket not found")
    t.status = TICKET_CLOSED
    t.closed_at = datetime.now()
    await db.flush()
