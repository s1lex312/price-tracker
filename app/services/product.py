"""Product business logic."""

import uuid
from collections.abc import Sequence
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestError, NotFoundError
from app.models.price_history import PriceHistory
from app.models.product import Product
from app.parsers import get_parser_cls
from app.repositories.price_history import PriceHistoryRepository
from app.repositories.product import ProductRepository
from app.schemas.product import ProductCreate


class ProductService:
    """Use-cases around products and their price history."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._products = ProductRepository(session)
        self._history = PriceHistoryRepository(session)

    async def create(self, data: ProductCreate) -> Product:
        """Create a product; currency defaults to the source parser's."""
        currency = data.currency or get_parser_cls(data.source).currency
        if currency is None:
            raise BadRequestError(
                f"currency is required for source {data.source.value}"
            )
        product = Product(
            user_telegram_id=data.user_telegram_id,
            name=data.name,
            source=data.source,
            external_id=data.external_id,
            target_price=data.target_price,
            currency=currency,
            price_selector=data.price_selector,
        )
        await self._products.create(product)
        await self._session.commit()
        return product

    async def get(self, product_id: uuid.UUID) -> Product:
        """Return a product by id or raise NotFoundError."""
        product = await self._products.get(product_id)
        if product is None:
            raise NotFoundError(f"Product {product_id} not found")
        return product

    async def list(self) -> Sequence[Product]:
        """Return all products, newest first."""
        return await self._products.list_all()

    async def update_target_price(
        self, product_id: uuid.UUID, target_price: Decimal
    ) -> Product:
        """Update the alert threshold of a product."""
        product = await self.get(product_id)
        product.target_price = target_price
        await self._session.commit()
        return product

    async def delete(self, product_id: uuid.UUID) -> None:
        """Delete a product and its history."""
        product = await self.get(product_id)
        await self._products.delete(product)
        await self._session.commit()

    async def history(
        self, product_id: uuid.UUID, limit: int = 100
    ) -> Sequence[PriceHistory]:
        """Return the latest price observations, newest first."""
        await self.get(product_id)
        return await self._history.list_for_product(product_id, limit)
