"""Product persistence."""

import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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

    async def delete(self, product: Product) -> None:
        """Delete a product (history rows cascade)."""
        await self._session.delete(product)
