"""Celery application: periodic price checks via the Redis broker."""

import asyncio
import logging

from celery import Celery

from app.core.config import get_settings
from app.db.session import build_engine, build_session_factory
from app.notifiers import build_notifier
from app.scheduler.jobs import check_prices_job

logger = logging.getLogger(__name__)

settings = get_settings()

celery_app = Celery(
    "price_tracker",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.beat_schedule = {
    "price-check": {
        "task": "app.scheduler.celery_app.price_check_task",
        "schedule": float(settings.scheduler_interval_minutes * 60),
    }
}


async def _run_price_check() -> None:
    """Run one full price-check pass with fresh connections."""
    engine = build_engine(settings.database_url)
    notifier = build_notifier(settings)
    try:
        await check_prices_job(build_session_factory(engine), notifier, settings)
    finally:
        await notifier.close()
        await engine.dispose()


@celery_app.task(name="price_check")
def price_check_task() -> None:
    """Celery task wrapper around the async price-check job."""
    asyncio.run(_run_price_check())
