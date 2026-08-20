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
            BotCommand(command="start", description="Открыть оперативную админку"),
            BotCommand(command="dashboard", description="Dashboard"),
            BotCommand(command="offers", description="Модерация предложений"),
            BotCommand(command="orders", description="Заказы"),
            BotCommand(command="support", description="Поддержка"),
        ],
        require_admin_allowlist=True,
    )


if __name__ == "__main__":
    try:
        asyncio.run(run())
    except RuntimeError as exc:
        logger.critical("Admin bot configuration error: %s", exc)
        raise SystemExit(2) from exc
