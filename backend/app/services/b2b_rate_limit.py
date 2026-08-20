from __future__ import annotations

import asyncio
import time
from collections import defaultdict, deque
from collections.abc import Callable

from fastapi import HTTPException, Request


class InMemoryRateLimiter:
    """Small fixed-window limiter for sensitive endpoints.

    It intentionally uses the socket peer instead of an untrusted forwarded
    header.  A shared gateway limiter should replace this adapter when the API
    is scaled to multiple processes.
    """

    def __init__(self) -> None:
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = asyncio.Lock()

    async def check(self, key: str, limit: int, window_seconds: int) -> None:
        now = time.monotonic()
        cutoff = now - window_seconds
        async with self._lock:
            events = self._events[key]
            while events and events[0] <= cutoff:
                events.popleft()
            if len(events) >= limit:
                retry_after = max(1, int(window_seconds - (now - events[0])))
                raise HTTPException(
                    status_code=429,
                    detail="Слишком много запросов. Повторите попытку позже.",
                    headers={"Retry-After": str(retry_after)},
                )
            events.append(now)


limiter = InMemoryRateLimiter()


def rate_limit(scope: str, *, requests: int, seconds: int) -> Callable[[Request], None]:
    async def dependency(request: Request) -> None:
        peer = request.client.host if request.client else "unknown"
        await limiter.check(f"{scope}:{peer}", requests, seconds)

    return dependency
