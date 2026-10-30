"""Price refreshing and threshold alerting."""

import asyncio
import logging
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.exceptions import (
    ConflictError,
    ExternalServiceError,
    NotFoundError,
)
from app.models.price_history import PriceHistory
from app.models.product import Product
from app.parsers import ParserError, get_parser
from app.repositories.price_history import PriceHistoryRepository
from app.repositories.product import ProductRepository

logger = logging.getLogger(__name__)

# Per-product refresh locks (process-local: guards double-clicks and
# parallel API calls within one process; the celery worker has its own).
_refresh_locks: dict[uuid.UUID, asyncio.Lock] = {}


class PriceService:
    """Fetches prices, stores history, fires threshold alerts."""

    def __init__(
        self,
        session: AsyncSession,
        notifier: object | None = None,
        settings: Settings | None = None,
    ) -> None:
        self._session = session
        self._notifier = notifier
        self._settings = settings or get_settings()
        self._products = ProductRepository(session)
        self._history = PriceHistoryRepository(session)

    async def refresh_product(self, product_id: uuid.UUID) -> Product:
        """Fetch the current price, store history and maybe alert.

        Raises ConflictError when a refresh for this product is already
        running in this process. Parser failures are stored on the
        product (``last_error``) and re-raised as ExternalServiceError.
        """
        lock = _refresh_locks.setdefault(product_id, asyncio.Lock())
        if lock.locked():
            raise ConflictError("Refresh already in progress")
        async with lock:
            return await self._refresh_product(product_id)

    async def _refresh_product(self, product_id: uuid.UUID) -> Product:
        """The refresh itself, called under the per-product lock."""
        product = await self._products.get(product_id)
        if product is None:
            raise NotFoundError(f"Product {product_id} not found")

        parser = get_parser(product.source)
        try:
            price = await parser.fetch_price(
                product.external_id, selector=product.price_selector
            )
        except ParserError as exc:
            product.last_error = str(exc)
            await self._session.commit()
            logger.warning("Price fetch failed for %s: %s", product.id, exc)
            raise ExternalServiceError(str(exc)) from exc

        await self._history.add(PriceHistory(product_id=product.id, price=price))
        product.current_price = price
        product.last_error = None

        if price <= product.target_price and self._alert_due(product):
            await self._send_alert(product)

        await self._session.commit()
        return product

    def _alert_due(self, product: Product) -> bool:
        """Check the per-product alert cooldown."""
        if self._notifier is None:
            return False
        if product.last_alert_at is None:
            return True
        cooldown = timedelta(hours=self._settings.alert_cooldown_hours)
        return datetime.now(UTC) - product.last_alert_at >= cooldown

    async def _send_alert(self, product: Product) -> None:
        """Send the alert; failures are logged, never raised."""
        try:
            await self._notifier.send_price_alert(product.user_telegram_id, product)
        except Exception:
            logger.exception("Alert send failed for product %s", product.id)
            return
        product.last_alert_at = datetime.now(UTC)
