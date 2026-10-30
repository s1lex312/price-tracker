"""Price history persistence."""

import uuid
from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.price_history import PriceHistory


class PriceHistoryRepository:
    """Access to the price_history table."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, entry: PriceHistory) -> PriceHistory:
        """Persist a new price observation."""
        self._session.add(entry)
        await self._session.flush()
        return entry

    async def list_for_product(
        self, product_id: uuid.UUID, limit: int = 100
    ) -> Sequence[PriceHistory]:
        """Return the latest observations for a product, newest first."""
        result = await self._session.execute(
            select(PriceHistory)
            .where(PriceHistory.product_id == product_id)
            .order_by(PriceHistory.checked_at.desc())
            .limit(limit)
        )
        return result.scalars().all()

    async def latest_check_map(self) -> dict[uuid.UUID, datetime]:
        """Map product id -> timestamp of its latest price check."""
        result = await self._session.execute(
            select(
                PriceHistory.product_id,
                func.max(PriceHistory.checked_at),
            ).group_by(PriceHistory.product_id)
        )
        return {row[0]: row[1] for row in result.all()}
