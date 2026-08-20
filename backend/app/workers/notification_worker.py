from __future__ import annotations

import asyncio
import logging
import signal

from app.config import get_settings
from app.database import async_session
from app.services.b2b_notifications import (
    claim_notifications,
    deliver_claimed,
    enqueue_due_reminders,
    wait_or_stop,
)
from app.services.b2b_metrics import WORKER_ITERATION_FAILURES
from app.services.b2b_orders import expire_reservations
from app.services.b2b_subscriptions import expire_subscriptions


logger = logging.getLogger("kulcha.b2b.worker")


async def run() -> None:
    logging.basicConfig(level=logging.INFO)
    settings = get_settings()
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for signal_name in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(signal_name, stop.set)
        except NotImplementedError:  # pragma: no cover - Windows/dev fallback
            pass

    logger.info("notification_worker_started")
    while not stop.is_set():
        try:
            async with async_session() as db:
                async with db.begin():
                    expired = await expire_reservations(db)
                    expired_subscriptions = await expire_subscriptions(db)
                    reminders = await enqueue_due_reminders(db)
                    claimed = await claim_notifications(db)
                if expired:
                    logger.info("expired_reservations count=%s", expired)
                if expired_subscriptions:
                    logger.info("expired_subscriptions count=%s", expired_subscriptions)
                if reminders:
                    logger.info("notification_reminders_enqueued count=%s", reminders)
                if claimed:
                    async with db.begin():
                        await deliver_claimed(db, claimed)
                    logger.info("notification_batch_processed count=%s", len(claimed))
        except Exception:
            WORKER_ITERATION_FAILURES.inc()
            logger.exception("notification_worker_iteration_failed")
        await wait_or_stop(stop, settings.notification_poll_seconds)
    logger.info("notification_worker_stopped")


if __name__ == "__main__":
    asyncio.run(run())
