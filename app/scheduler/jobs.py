"""Price checking job logic (transport-agnostic, used by Celery)."""

import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.core.exceptions import AppError
from app.repositories.product import ProductRepository
from app.services.price import PriceService

logger = logging.getLogger(__name__)


async def refresh_product_standalone(
    session_factory: async_sessionmaker[AsyncSession],
    notifier: object | None,
    settings: Settings,
    product_id: uuid.UUID,
) -> bool:
    """Refresh one product in its own session; True on success.

    A parser failure is stored on the product and logged, never raised.
    """
    async with session_factory() as session:
        try:
            await PriceService(
                session, notifier=notifier, settings=settings
            ).refresh_product(product_id)
        except AppError as exc:
            logger.warning("Price check failed for %s: %s", product_id, exc.detail)
            return False
    return True


async def check_prices_job(
    session_factory: async_sessionmaker[AsyncSession],
    notifier: object | None,
    settings: Settings,
) -> list[uuid.UUID]:
    """Refresh all active products in-process (tests, manual runs).

    The production path goes through Celery: ``dispatch_price_check_task``
    fans out one ``refresh_product`` task per product. This function
    remains for a single-process full pass. Returns refreshed ids.
    """
    async with session_factory() as session:
        product_ids = list(await ProductRepository(session).list_active_ids())

    logger.info("Price check started for %d products", len(product_ids))
    refreshed: list[uuid.UUID] = []
    for product_id in product_ids:
        if await refresh_product_standalone(
            session_factory, notifier, settings, product_id
        ):
            refreshed.append(product_id)
    logger.info(
        "Price check finished: %d/%d succeeded",
        len(refreshed),
        len(product_ids),
    )
    return refreshed
