"""Periodic price checking job."""

import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.core.exceptions import AppError
from app.repositories.product import ProductRepository
from app.services.price import PriceService

logger = logging.getLogger(__name__)


async def check_prices_job(
    session_factory: async_sessionmaker[AsyncSession],
    notifier: object | None,
    settings: Settings,
) -> list[uuid.UUID]:
    """Refresh prices for all active products.

    Each product is refreshed in its own session; a parser failure on
    one product is logged and never aborts the whole run. Returns the
    list of successfully refreshed product ids.
    """
    async with session_factory() as session:
        product_ids = list(await ProductRepository(session).list_active_ids())

    logger.info("Price check started for %d products", len(product_ids))
    refreshed: list[uuid.UUID] = []
    for product_id in product_ids:
        async with session_factory() as session:
            try:
                await PriceService(
                    session, notifier=notifier, settings=settings
                ).refresh_product(product_id)
            except AppError as exc:
                logger.warning(
                    "Price check failed for %s: %s", product_id, exc.detail
                )
            else:
                refreshed.append(product_id)
    logger.info(
        "Price check finished: %d/%d succeeded", len(refreshed), len(product_ids)
    )
    return refreshed
