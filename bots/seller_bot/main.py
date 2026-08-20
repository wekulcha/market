from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aiogram import Dispatcher  # noqa: E402
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
    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    await run_bot(
        settings=settings,
        dispatcher=dispatcher,
        commands=[
            BotCommand(command="start", description="Регистрация поставщика"),
            BotCommand(command="offers", description="Мои предложения"),
            BotCommand(command="new_offer", description="Новое предложение"),
            BotCommand(command="orders", description="Заказы и резервы"),
            BotCommand(command="support", description="Поддержка"),
        ],
    )


if __name__ == "__main__":
    try:
        asyncio.run(run())
    except RuntimeError as exc:
        logger.critical("Seller bot configuration error: %s", exc)
        raise SystemExit(2) from exc
