from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aiogram import Dispatcher  # noqa: E402
from aiogram.fsm.storage.memory import MemoryStorage  # noqa: E402
from aiogram.fsm.storage.redis import RedisStorage  # noqa: E402
from aiogram.types import BotCommand  # noqa: E402
from b2b_common.runtime import run_bot  # noqa: E402
from config import settings  # noqa: E402
from handlers import router  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger(__name__)


async def run() -> None:
    if settings.bot_mode == "webhook":
        settings.validate_runtime()
        storage = RedisStorage.from_url(
            settings.redis_url,
            state_ttl=24 * 60 * 60,
            data_ttl=24 * 60 * 60,
        )
        dispatcher = Dispatcher(
            storage=storage,
            events_isolation=storage.create_isolation(),
        )
    else:
        dispatcher = Dispatcher(storage=MemoryStorage())
    dispatcher.include_router(router)
    await run_bot(
        settings=settings,
        dispatcher=dispatcher,
        commands=[
            BotCommand(
                command="start", description="Начать или активировать приглашение"
            ),
            BotCommand(command="catalog", description="Открыть каталог"),
            BotCommand(command="orders", description="Мои заказы"),
            BotCommand(command="subscription", description="Моя подписка"),
            BotCommand(command="support", description="Поддержка"),
        ],
    )


if __name__ == "__main__":
    try:
        asyncio.run(run())
    except RuntimeError as exc:
        logger.critical("Buyer bot configuration error: %s", exc)
        raise SystemExit(2) from exc
