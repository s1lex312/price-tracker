"""Products REST API."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_price_service, get_product_service
from app.schemas.product import PricePoint, ProductCreate, ProductRead
from app.services.price import PriceService
from app.services.product import ProductService

router = APIRouter(prefix="/products", tags=["products"])

ProductServiceDep = Annotated[ProductService, Depends(get_product_service)]
PriceServiceDep = Annotated[PriceService, Depends(get_price_service)]


@router.get("", response_model=list[ProductRead])
async def list_products(service: ProductServiceDep) -> list[ProductRead]:
    """List all tracked products."""
    return await service.list()


@router.post("", response_model=ProductRead, status_code=201)
async def create_product(
    data: ProductCreate, service: ProductServiceDep
) -> ProductRead:
    """Create a tracked product."""
    return await service.create(data)


@router.get("/{product_id}", response_model=ProductRead)
async def get_product(
    product_id: UUID, service: ProductServiceDep
) -> ProductRead:
    """Get a single product."""
    return await service.get(product_id)


@router.delete("/{product_id}", status_code=204)
async def delete_product(
    product_id: UUID, service: ProductServiceDep
) -> None:
    """Delete a product and its price history."""
    await service.delete(product_id)


@router.post("/{product_id}/refresh", response_model=ProductRead)
async def refresh_product(
    product_id: UUID, service: PriceServiceDep
) -> ProductRead:
    """Fetch the current price immediately (bypasses the scheduler)."""
    return await service.refresh_product(product_id)


@router.get("/{product_id}/history", response_model=list[PricePoint])
async def product_history(
    product_id: UUID,
    service: ProductServiceDep,
    limit: Annotated[int, Query(ge=1, le=1000)] = 100,
) -> list[PricePoint]:
    """Return the latest price observations, newest first."""
    return await service.history(product_id, limit)
