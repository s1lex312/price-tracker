"""Shared FastAPI dependencies."""

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.price import PriceService
from app.services.product import ProductService


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    """Yield a DB session from the app-level session factory."""
    factory = request.app.state.session_factory
    async with factory() as session:
        yield session


SessionDep = Annotated[AsyncSession, Depends(get_session)]


def get_product_service(session: SessionDep) -> ProductService:
    """Build a ProductService bound to the request session."""
    return ProductService(session)


def get_price_service(request: Request, session: SessionDep) -> PriceService:
    """Build a PriceService with the app-level notifier attached."""
    notifier = getattr(request.app.state, "notifier", None)
    return PriceService(session, notifier=notifier)
