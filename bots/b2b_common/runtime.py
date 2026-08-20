from __future__ import annotations

import asyncio
import logging
import signal
from collections.abc import Sequence

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode
from aiogram.types import BotCommand
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web
from redis.asyncio import Redis

from .api import InternalBotAPI
from .config import BotSettings
from .webhook import WebhookDedupMiddleware

logger = logging.getLogger("kulcha.b2b.bot_runtime")
DEDUP_REDIS_KEY = web.AppKey("dedup_redis", Redis)


async def _health(request: web.Request) -> web.Response:
    redis = request.app[DEDUP_REDIS_KEY]
    try:
        await redis.ping()
    except Exception:
        return web.json_response({"status": "not_ready"}, status=503)
    return web.json_response({"status": "ok", "redis": "ok"})


async def _serve_webhook(
    *,
    settings: BotSettings,
    dispatcher: Dispatcher,
    bot: Bot,
    redis: Redis,
) -> None:
    app = web.Application(client_max_size=2 * 1024 * 1024)
    app[DEDUP_REDIS_KEY] = redis
    app.router.add_get("/health", _health)
    SimpleRequestHandler(
        dispatcher=dispatcher,
        bot=bot,
        handle_in_background=False,
        secret_token=settings.webhook_secret,
    ).register(app, path=settings.webhook_path)
    setup_application(app, dispatcher, bot=bot)

    runner = web.AppRunner(app, access_log=None)
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    registered_signals: list[signal.Signals] = []
    for signal_name in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(signal_name, stop.set)
            registered_signals.append(signal_name)
        except (
            NotImplementedError,
            RuntimeError,
        ):  # pragma: no cover - Windows fallback
            pass

    try:
        await runner.setup()
        site = web.TCPSite(
            runner, host=settings.webhook_host, port=settings.webhook_port
        )
        await site.start()
        await bot.set_webhook(
            settings.webhook_url,
            secret_token=settings.webhook_secret,
            allowed_updates=dispatcher.resolve_used_update_types(),
            drop_pending_updates=False,
        )
        logger.info(
            "B2B %s bot webhook listening on %s:%s%s",
            settings.role,
            settings.webhook_host,
            settings.webhook_port,
            settings.webhook_path,
        )
        await stop.wait()
    finally:
        for signal_name in registered_signals:
            loop.remove_signal_handler(signal_name)
        await runner.cleanup()


async def run_bot(
    *,
    settings: BotSettings,
    dispatcher: Dispatcher,
    commands: Sequence[BotCommand],
    require_admin_allowlist: bool = False,
) -> None:
    settings.validate_runtime(require_admin_allowlist=require_admin_allowlist)
    session = (
        AiohttpSession(proxy=settings.telegram_proxy_url)
        if settings.telegram_proxy_url
        else None
    )
    bot = Bot(
        token=settings.token,
        session=session,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dispatcher["bot_settings"] = settings
    dedup_redis: Redis | None = None

    try:
        if settings.bot_mode == "webhook":
            dedup_redis = Redis.from_url(settings.redis_url, decode_responses=True)
            await dedup_redis.ping()
            dispatcher.update.outer_middleware(
                WebhookDedupMiddleware(dedup_redis, role=settings.role)
            )
        async with InternalBotAPI(settings) as api_client:
            dispatcher["api_client"] = api_client
            await bot.set_my_commands(list(commands))
            if settings.bot_mode == "webhook":
                assert dedup_redis is not None
                await _serve_webhook(
                    settings=settings,
                    dispatcher=dispatcher,
                    bot=bot,
                    redis=dedup_redis,
                )
                return

            await bot.delete_webhook(drop_pending_updates=False)
            logger.info("Starting B2B %s bot in polling mode", settings.role)
            await dispatcher.start_polling(
                bot,
                allowed_updates=dispatcher.resolve_used_update_types(),
                close_bot_session=False,
            )
    finally:
        if dedup_redis is not None:
            await dedup_redis.aclose()
        # The webhook request handler also closes this session on app shutdown;
        # aiogram sessions are idempotently closeable and this covers early failures.
        await bot.session.close()
