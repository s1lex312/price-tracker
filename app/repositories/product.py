"""Product persistence."""

import uuid
from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import ProductSource
from app.models.product import Product


class ProductRepository:
    """CRUD access to the products table."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, product: Product) -> Product:
        """Persist a new product."""
        self._session.add(product)
        await self._session.flush()
        return product

    async def get(self, product_id: uuid.UUID) -> Product | None:
        """Return a product by id or None."""
        return await self._session.get(Product, product_id)

    async def list_all(self) -> Sequence[Product]:
        """Return all products, newest first."""
        result = await self._session.execute(
            select(Product).order_by(Product.created_at.desc())
        )
        return result.scalars().all()

    async def list_active_ids(self) -> Sequence[uuid.UUID]:
        """Return ids of all active products."""
        result = await self._session.execute(
            select(Product.id).where(Product.is_active.is_(True))
        )
        return result.scalars().all()

    async def list_active_brief(self) -> Sequence[tuple[uuid.UUID, str]]:
        """Return (id, source) pairs of all active products."""
        result = await self._session.execute(
            select(Product.id, Product.source).where(Product.is_active.is_(True))
        )
        return [(row[0], row[1]) for row in result.all()]

    async def count_active_by_source(self, source: ProductSource) -> int:
        """Count active products of the given source."""
        result = await self._session.execute(
            select(func.count())
            .select_from(Product)
            .where(Product.is_active.is_(True), Product.source == source)
        )
        return result.scalar_one()

    async def delete(self, product: Product) -> None:
        """Delete a product (history rows cascade)."""
        await self._session.delete(product)
