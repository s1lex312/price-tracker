"""Server-rendered dashboard (Jinja2 + Chart.js)."""

import json
import logging
from decimal import Decimal
from pathlib import Path
from typing import Annotated
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError

from app.api.auth import require_user
from app.api.deps import SessionDep, get_price_service
from app.api.products import PLAYWRIGHT_WORKER_HINT
from app.core.exceptions import AppError
from app.models.enums import ProductSource
from app.repositories.price_history import PriceHistoryRepository
from app.repositories.product import ProductRepository
from app.scheduler.inspection import playwright_worker_online
from app.schemas.product import ProductCreate
from app.services.price import PriceService
from app.services.product import ProductService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["dashboard"], dependencies=[Depends(require_user)])

templates = Jinja2Templates(
    directory=Path(__file__).resolve().parent.parent / "templates"
)


def _redirect(url: str) -> RedirectResponse:
    """Redirect after a form POST (303 = always follow with GET)."""
    return RedirectResponse(url=url, status_code=303)


def _error_redirect(url: str, message: str) -> RedirectResponse:
    return _redirect(f"{url}?error={quote(message[:200])}")


@router.get("/")
async def index(request: Request, session: SessionDep):
    """Dashboard home: table of products and the add-product form."""
    service = ProductService(session)
    products = await service.list()
    last_checked = await PriceHistoryRepository(session).latest_check_map()

    js_pending = await ProductRepository(session).count_active_by_source(
        ProductSource.PLAYWRIGHT_JS
    )
    playwright_worker_missing = js_pending > 0 and not (
        await playwright_worker_online()
    )

    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "products": products,
            "last_checked": last_checked,
            "error": request.query_params.get("error"),
            "auth_enabled": getattr(request.app.state, "auth_enabled", False),
            "js_pending": js_pending,
            "playwright_worker_missing": playwright_worker_missing,
        },
    )


@router.post("/products")
async def create_product_form(
    session: SessionDep,
    name: Annotated[str, Form()],
    source: Annotated[ProductSource, Form()],
    external_id: Annotated[str, Form()],
    target_price: Annotated[Decimal, Form()],
    user_telegram_id: Annotated[int, Form()],
    currency: Annotated[str, Form()] = "",
    price_selector: Annotated[str, Form()] = "",
):
    """Handle the add-product form."""
    try:
        data = ProductCreate(
            name=name,
            source=source,
            external_id=external_id,
            target_price=target_price,
            currency=currency or None,
            user_telegram_id=user_telegram_id,
            price_selector=price_selector or None,
        )
    except ValidationError as exc:
        message = exc.errors()[0].get("msg", "Invalid input")
        return _error_redirect("/", message)

    if data.source == ProductSource.PLAYWRIGHT_JS and not (
        await playwright_worker_online()
    ):
        return _error_redirect("/", PLAYWRIGHT_WORKER_HINT)

    try:
        await ProductService(session).create(data)
    except AppError as exc:
        return _error_redirect("/", exc.detail)
    return _redirect("/")


@router.get("/products/{product_id}")
async def product_detail(product_id: UUID, request: Request, session: SessionDep):
    """Product card: price chart, recent history, target-price form."""
    service = ProductService(session)
    try:
        product = await service.get(product_id)
    except AppError:
        return _redirect("/")

    history = await service.history(product_id, limit=100)
    chronological = list(reversed(history))
    chart_labels = json.dumps(
        [point.checked_at.strftime("%d.%m %H:%M") for point in chronological]
    )
    chart_data = json.dumps([float(point.price) for point in chronological])

    return templates.TemplateResponse(
        request,
        "product.html",
        {
            "product": product,
            "history": history[:20],
            "chart_labels": chart_labels,
            "chart_data": chart_data,
            "error": request.query_params.get("error"),
            "auth_enabled": getattr(request.app.state, "auth_enabled", False),
        },
    )


@router.post("/products/{product_id}/refresh")
async def refresh_product_form(
    product_id: UUID,
    service: Annotated[PriceService, Depends(get_price_service)],
):
    """Force a price refresh from the dashboard."""
    try:
        await service.refresh_product(product_id)
    except AppError as exc:
        return _error_redirect(f"/products/{product_id}", exc.detail)
    return _redirect(f"/products/{product_id}")


@router.post("/products/{product_id}/target-price")
async def update_target_price_form(
    product_id: UUID,
    session: SessionDep,
    target_price: Annotated[Decimal, Form()],
):
    """Handle the target-price change form."""
    try:
        await ProductService(session).update_target_price(product_id, target_price)
    except AppError as exc:
        return _error_redirect(f"/products/{product_id}", exc.detail)
    return _redirect(f"/products/{product_id}")


@router.post("/products/{product_id}/delete")
async def delete_product_form(product_id: UUID, session: SessionDep):
    """Handle the delete button."""
    try:
        await ProductService(session).delete(product_id)
    except AppError:
        logger.info("Delete requested for missing product %s", product_id)
    return _redirect("/")
