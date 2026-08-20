from __future__ import annotations

from typing import Any, Self

import httpx

from .config import BotSettings


class BotAPIError(RuntimeError):
    def __init__(
        self, status_code: int, public_message: str = "Сервис временно недоступен"
    ) -> None:
        super().__init__(public_message)
        self.status_code = status_code
        self.public_message = public_message


class InternalBotAPI:
    """Small service client shared by all B2B bots.

    The internal secret is sent only in a header and is never included in URLs or logs.
    """

    def __init__(self, settings: BotSettings) -> None:
        self._client = httpx.AsyncClient(
            base_url=settings.api_base,
            timeout=settings.request_timeout_seconds,
            headers={
                "X-B2B-Internal-Secret": settings.internal_api_secret,
                "User-Agent": f"kulcha-b2b-{settings.role}-bot/1.0",
            },
        )

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._client.aclose()

    @staticmethod
    def _public_error(response: httpx.Response) -> BotAPIError:
        if response.status_code in {401, 403}:
            return BotAPIError(
                response.status_code, "Нет доступа или приглашение недействительно"
            )
        if response.status_code == 404:
            return BotAPIError(response.status_code, "Запись не найдена")
        if response.status_code == 409:
            return BotAPIError(response.status_code, "Данные уже были использованы")
        if response.status_code == 422:
            return BotAPIError(response.status_code, "Проверьте введённые данные")
        return BotAPIError(response.status_code)

    async def _json(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        try:
            response = await self._client.request(method, path, **kwargs)
        except httpx.HTTPError as exc:
            raise BotAPIError(503) from exc
        if response.status_code < 200 or response.status_code >= 300:
            raise self._public_error(response)
        if not response.content:
            return {}
        try:
            payload = response.json()
        except ValueError as exc:
            raise BotAPIError(502) from exc
        return payload if isinstance(payload, dict) else {"items": payload}

    async def register_buyer(
        self,
        *,
        telegram_id: int,
        username: str | None,
        phone: str,
        invite_token: str,
    ) -> dict[str, Any]:
        return await self._json(
            "POST",
            "/api/internal/bots/buyer/register",
            json={
                "telegramId": telegram_id,
                "username": username,
                "phone": phone,
                "inviteToken": invite_token,
            },
        )

    async def register_seller(
        self,
        *,
        telegram_id: int,
        username: str | None,
        phone: str,
    ) -> dict[str, Any]:
        return await self._json(
            "POST",
            "/api/internal/bots/seller/register",
            json={
                "telegramId": telegram_id,
                "username": username,
                "phone": phone,
            },
        )

    async def status(self, telegram_id: int) -> dict[str, Any]:
        return await self._json("GET", f"/api/internal/bots/status/{telegram_id}")

    async def admin_offer_action(
        self,
        *,
        offer_id: str,
        action: str,
        actor_telegram_id: int,
        reason: str | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {"action": action}
        if reason:
            body["reason"] = reason
        return await self._json(
            "POST",
            f"/api/internal/bots/admin/offers/{offer_id}/{action}",
            json=body,
            headers={"X-Telegram-User-ID": str(actor_telegram_id)},
        )
