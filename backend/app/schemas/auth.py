from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class BotTokenRequest(BaseModel):
    token: str


class TelegramLoginRequest(BaseModel):
    initDataRaw: str


class AuthUserDto(BaseModel):
    id: int
    username: str
    phone: str
    email: str | None = None
    address: str | None = None
    registeredAt: datetime


class AuthSessionDto(BaseModel):
    accessToken: str
    accessTokenExpiresAt: datetime
    user: AuthUserDto
