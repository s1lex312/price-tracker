"""Celery application: periodic price checks via the Redis broker.

Beat enqueues a dispatcher on the ``default`` queue; the dispatcher
fans out one task per active product, routing ``playwright_js``
products to the dedicated ``playwright`` queue.
"""

import asyncio
import logging
import uuid

from celery import Celery
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import get_settings
from app.db.session import build_engine, build_session_factory
from app.models.enums import ProductSource
from app.notifiers import build_notifier
from app.repositories.product import ProductRepository
from app.scheduler.jobs import refresh_product_standalone
from app.scheduler.queues import queue_for_source

logger = logging.getLogger(__name__)

settings = get_settings()

celery_app = Celery(
    "price_tracker",
    broker=settings.redis_url,
    backend=settings.redis_url,
)
celery_app.conf.task_default_queue = "default"

celery_app.conf.beat_schedule = {
    "price-check": {
        "task": "app.scheduler.celery_app.dispatch_price_check_task",
        "schedule": float(settings.scheduler_interval_minutes * 60),
    }
}


async def _dispatch(session_factory: async_sessionmaker[AsyncSession]) -> int:
    """Fan out one refresh task per active product. Returns task count."""
    async with session_factory() as session:
        products = await ProductRepository(session).list_active_brief()

    for product_id, source in products:
        refresh_product_task.apply_async(
            args=[str(product_id)],
            queue=queue_for_source(ProductSource(source)),
        )
    logger.info(
        "Dispatched %d refresh tasks (%d playwright)",
        len(products),
        sum(1 for _, s in products if s == ProductSource.PLAYWRIGHT_JS),
    )
    return len(products)


@celery_app.task(name="dispatch_price_check")
def dispatch_price_check_task() -> int:
    """Beat entry point: fan out per-product refresh tasks."""
    return asyncio.run(_dispatch_standalone())


async def _dispatch_standalone() -> int:
    engine = build_engine(settings.database_url)
    try:
        return await _dispatch(build_session_factory(engine))
    finally:
        await engine.dispose()


@celery_app.task(name="refresh_product")
def refresh_product_task(product_id: str) -> None:
    """Refresh a single product; runs on the queue for its source."""
    asyncio.run(_refresh_one(uuid.UUID(product_id)))


async def _refresh_one(product_id: uuid.UUID) -> None:
    engine = build_engine(settings.database_url)
    notifier = build_notifier(settings)
    try:
        await refresh_product_standalone(
            build_session_factory(engine), notifier, settings, product_id
        )
    finally:
        await notifier.close()
        await engine.dispose()
