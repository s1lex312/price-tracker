"""Tests for the books.toscrape.com, CoinGecko and Playwright parsers."""

import sys
from decimal import Decimal

import httpx
import pytest
import respx

from app.parsers.base import (
    ParserBlockedError,
    ParserError,
    ParserNetworkError,
    ParserStructureError,
    extract_price,
)
from app.parsers.books_toscrape import BooksToScrapeParser
from app.parsers.coingecko import API_URL as COINGECKO_API_URL
from app.parsers.coingecko import CoinGeckoParser
from app.parsers.playwright_js import PlaywrightParser

BOOK_URL = "https://books.toscrape.com/catalogue/a-light-in-the-attic_1000/index.html"

HTML_OK = "<html><body><p class='price_color'>&pound;51.77</p></body></html>"
HTML_NO_PRICE = "<html><body><p>No price here</p></body></html>"


def make_parser() -> BooksToScrapeParser:
    return BooksToScrapeParser(retry_delay=0)


@respx.mock
async def test_books_fetch_price_success() -> None:
    route = respx.get(BOOK_URL).mock(return_value=httpx.Response(200, text=HTML_OK))

    price = await make_parser().fetch_price(BOOK_URL)

    assert price == Decimal("51.77")
    assert route.call_count == 1


@respx.mock
async def test_books_price_not_found() -> None:
    respx.get(BOOK_URL).mock(return_value=httpx.Response(200, text=HTML_NO_PRICE))

    with pytest.raises(ParserStructureError):
        await make_parser().fetch_price(BOOK_URL)


@respx.mock
async def test_books_timeout() -> None:
    respx.get(BOOK_URL).mock(side_effect=httpx.ConnectTimeout("boom"))

    with pytest.raises(ParserNetworkError):
        await make_parser().fetch_price(BOOK_URL)


@respx.mock
async def test_books_403_blocked_after_retries() -> None:
    route = respx.get(BOOK_URL).mock(return_value=httpx.Response(403))

    with pytest.raises(ParserBlockedError):
        await make_parser().fetch_price(BOOK_URL)

    assert route.call_count == 2


@respx.mock
async def test_books_403_then_success_on_retry() -> None:
    route = respx.get(BOOK_URL).mock(
        side_effect=[
            httpx.Response(403),
            httpx.Response(200, text=HTML_OK),
        ]
    )

    price = await make_parser().fetch_price(BOOK_URL)

    assert price == Decimal("51.77")
    assert route.call_count == 2


# --- CoinGecko ---


def make_coingecko_parser() -> CoinGeckoParser:
    return CoinGeckoParser(retry_delay=0)


@respx.mock
async def test_coingecko_fetch_price_success() -> None:
    route = respx.get(COINGECKO_API_URL).mock(
        return_value=httpx.Response(200, json={"bitcoin": {"usd": 67000.5}})
    )

    price = await make_coingecko_parser().fetch_price("bitcoin")

    assert price == Decimal("67000.5")
    assert route.call_count == 1


@respx.mock
async def test_coingecko_429_blocked_after_retries() -> None:
    route = respx.get(COINGECKO_API_URL).mock(return_value=httpx.Response(429))

    with pytest.raises(ParserBlockedError):
        await make_coingecko_parser().fetch_price("bitcoin")

    assert route.call_count == 2


@respx.mock
async def test_coingecko_unknown_coin_id() -> None:
    respx.get(COINGECKO_API_URL).mock(return_value=httpx.Response(200, json={}))

    with pytest.raises(ParserStructureError):
        await make_coingecko_parser().fetch_price("no-such-coin")


# --- extract_price helper ---


def test_extract_price_strips_currency_symbol() -> None:
    assert extract_price("$51.77") == Decimal("51.77")


def test_extract_price_dollars_with_label() -> None:
    assert extract_price("Price: $1234.50") == Decimal("1234.50")


def test_extract_price_no_digits() -> None:
    with pytest.raises(ParserStructureError):
        extract_price("no price")


# --- Playwright parser ---


async def test_playwright_requires_selector() -> None:
    parser = PlaywrightParser(retry_delay=0)
    with pytest.raises(ParserStructureError, match="price_selector"):
        await parser.fetch_price("https://example.com")


async def test_playwright_missing_extra(monkeypatch) -> None:
    # sys.modules[name] = None makes `import name` raise ImportError,
    # regardless of whether playwright is actually installed
    monkeypatch.setitem(sys.modules, "playwright", None)
    monkeypatch.setitem(sys.modules, "playwright.async_api", None)

    parser = PlaywrightParser(retry_delay=0)
    with pytest.raises(ParserError, match="--profile playwright"):
        await parser.fetch_price("https://example.com", selector=".price")
