"""Runtime introspection of the Celery fleet."""

import asyncio
import logging

from app.scheduler.celery_app import celery_app
from app.scheduler.queues import PLAYWRIGHT_QUEUE

logger = logging.getLogger(__name__)


async def playwright_worker_online(timeout: float = 1.0) -> bool:
    """True when a worker consuming the playwright queue is online.

    Broker/inspect failures are treated as "offline" — the caller
    would rather warn the user than silently accept JS products.
    """
    try:
        return await asyncio.to_thread(_playwright_worker_online, timeout)
    except Exception:
        logger.warning("Celery inspect failed", exc_info=True)
        return False


def _playwright_worker_online(timeout: float) -> bool:
    inspector = celery_app.control.inspect(timeout=timeout)
    active_queues = inspector.active_queues() or {}
    return any(
        queue.get("name") == PLAYWRIGHT_QUEUE
        for queues in active_queues.values()
        for queue in queues
    )
