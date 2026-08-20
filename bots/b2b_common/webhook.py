from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Update
from redis.asyncio import Redis


class WebhookUpdateInProgress(RuntimeError):
    """Ask Telegram to retry instead of acknowledging a concurrent update early."""


class WebhookDedupMiddleware(BaseMiddleware):
    def __init__(
        self,
        redis: Redis,
        *,
        role: str,
        done_ttl_seconds: int = 7 * 24 * 60 * 60,
        lock_ttl_seconds: int = 60,
    ) -> None:
        self.redis = redis
        self.role = role
        self.done_ttl_seconds = done_ttl_seconds
        self.lock_ttl_seconds = lock_ttl_seconds

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if not isinstance(event, Update):
            return await handler(event, data)

        prefix = f"kulcha:b2b:webhook:{self.role}:{event.update_id}"
        done_key = f"{prefix}:done"
        lock_key = f"{prefix}:lock"
        if await self.redis.exists(done_key):
            return None

        acquired = await self.redis.set(
            lock_key,
            "1",
            ex=self.lock_ttl_seconds,
            nx=True,
        )
        if not acquired:
            if await self.redis.exists(done_key):
                return None
            raise WebhookUpdateInProgress(
                f"Webhook update {event.update_id} is in progress"
            )

        try:
            result = await handler(event, data)
        except Exception:
            await self.redis.delete(lock_key)
            raise

        pipeline = self.redis.pipeline(transaction=True)
        pipeline.set(done_key, "1", ex=self.done_ttl_seconds)
        pipeline.delete(lock_key)
        await pipeline.execute()
        return result
