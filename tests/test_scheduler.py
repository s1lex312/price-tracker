"""Tests for the periodic price-check job and the alert cooldown."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock

import httpx
import respx

from app.core.config import Settings
from app.models.enums import ProductSource
from app.models.product import Product
from app.scheduler.jobs import check_prices_job
from app.schemas.product import ProductCreate
from app.services.product import ProductService
from tests.test_products_api import BOOK_URL, HTML_OK

HTML_NO_PRICE = "<html><body><p>No price here</p></body></html>"
SECOND_BOOK_URL = (
    "https://books.toscrape.com/catalogue/tipping-the-velvet_999/index.html"
)


async def create_product(session_factory, **overrides) -> Product:
    """Persist a product through the service layer."""
    payload = {
        "name": "Book",
        "source": ProductSource.BOOKS_TOSCRAPE,
        "external_id": BOOK_URL,
        "target_price": Decimal("60.00"),
        "user_telegram_id": 123456,
    }
    payload.update(overrides)
    async with session_factory() as session:
        return await ProductService(session).create(ProductCreate(**payload))


async def read_product(session_factory, product_id) -> Product:
    async with session_factory() as session:
        return await ProductService(session).get(product_id)


def make_settings() -> Settings:
    return Settings(alert_cooldown_hours=24)


@respx.mock
async def test_job_writes_history_and_updates_price(session_factory) -> None:
    respx.get(BOOK_URL).mock(return_value=httpx.Response(200, text=HTML_OK))
    product = await create_product(session_factory)

    refreshed = await check_prices_job(session_factory, None, make_settings())

    assert refreshed == [product.id]
    product = await read_product(session_factory, product.id)
    assert product.current_price == Decimal("51.77000000")
    assert product.last_error is None

    async with session_factory() as session:
        history = await ProductService(session).history(product.id)
    assert len(history) == 1
    assert history[0].price == Decimal("51.77000000")


@respx.mock
async def test_job_sends_alert_below_threshold(session_factory) -> None:
    respx.get(BOOK_URL).mock(return_value=httpx.Response(200, text=HTML_OK))
    product = await create_product(session_factory, target_price=Decimal("60.00"))
    notifier = AsyncMock()

    await check_prices_job(session_factory, notifier, make_settings())

    notifier.send_price_alert.assert_awaited_once()
    args = notifier.send_price_alert.await_args.args
    assert args[0] == 123456
    assert args[1].id == product.id

    product = await read_product(session_factory, product.id)
    assert product.last_alert_at is not None


@respx.mock
async def test_no_alert_above_threshold(session_factory) -> None:
    respx.get(BOOK_URL).mock(return_value=httpx.Response(200, text=HTML_OK))
    await create_product(session_factory, target_price=Decimal("40.00"))
    notifier = AsyncMock()

    await check_prices_job(session_factory, notifier, make_settings())

    notifier.send_price_alert.assert_not_awaited()


@respx.mock
async def test_cooldown_prevents_second_alert(session_factory) -> None:
    respx.get(BOOK_URL).mock(return_value=httpx.Response(200, text=HTML_OK))
    await create_product(session_factory, target_price=Decimal("60.00"))
    notifier = AsyncMock()
    settings = make_settings()

    await check_prices_job(session_factory, notifier, settings)
    await check_prices_job(session_factory, notifier, settings)

    assert notifier.send_price_alert.await_count == 1


@respx.mock
async def test_alert_fires_again_after_cooldown(session_factory) -> None:
    respx.get(BOOK_URL).mock(return_value=httpx.Response(200, text=HTML_OK))
    product = await create_product(session_factory, target_price=Decimal("60.00"))
    notifier = AsyncMock()
    settings = make_settings()

    await check_prices_job(session_factory, notifier, settings)
    assert notifier.send_price_alert.await_count == 1

    # Simulate that the previous alert was sent 25 hours ago
    async with session_factory() as session:
        stale = await ProductService(session).get(product.id)
        stale.last_alert_at = datetime.now(UTC) - timedelta(hours=25)
        await session.commit()

    await check_prices_job(session_factory, notifier, settings)

    assert notifier.send_price_alert.await_count == 2


@respx.mock
async def test_job_continues_after_parser_error(session_factory) -> None:
    respx.get(BOOK_URL).mock(return_value=httpx.Response(200, text=HTML_NO_PRICE))
    respx.get(SECOND_BOOK_URL).mock(return_value=httpx.Response(200, text=HTML_OK))
    broken = await create_product(session_factory, name="Broken book")
    healthy = await create_product(
        session_factory, name="Healthy book", external_id=SECOND_BOOK_URL
    )

    refreshed = await check_prices_job(session_factory, None, make_settings())

    assert refreshed == [healthy.id]
    broken = await read_product(session_factory, broken.id)
    assert broken.last_error is not None
    assert broken.current_price is None


async def test_job_with_no_products(session_factory) -> None:
    refreshed = await check_prices_job(session_factory, None, make_settings())
    assert refreshed == []
