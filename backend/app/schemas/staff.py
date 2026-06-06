from __future__ import annotations

from pydantic import BaseModel, model_validator


class StaffDto(BaseModel):
    id: int | None = None
    userId: int | None = None
    restaurantId: int | None = None
    permission: str | None = None


class StaffMemberDto(BaseModel):
    staffId: int
    userId: int
    username: str | None = None
    phone: str | None = None
    permission: str


class AddStaffRequestDto(BaseModel):
    telegramId: int | None = None
    phone: str | None = None
    permission: str

    @model_validator(mode="after")
    def _one_identifier(self) -> AddStaffRequestDto:
        has_tg = self.telegramId is not None
        has_phone = bool(self.phone and str(self.phone).strip())
        if has_tg == has_phone:
            raise ValueError("Укажите ровно одно: telegramId или phone")
        return self
