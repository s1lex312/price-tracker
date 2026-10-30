"""Abstract parser interface and parser exceptions."""

import asyncio
import re
from abc import ABC, abstractmethod
from decimal import Decimal, InvalidOperation

import httpx

from app.models.enums import ProductSource

_NON_NUMERIC = re.compile(r"[^0-9.]")


class ParserError(Exception):
    """Base error for all price parsers."""


class ParserNetworkError(ParserError):
    """Network-level failure: timeout, connection error, unexpected HTTP code."""


class ParserBlockedError(ParserError):
    """Source blocked the request (HTTP 403/429) after all retries."""


class ParserStructureError(ParserError):
    """Response received, but the price could not be extracted from it."""


def extract_price(raw_text: str) -> Decimal:
    """Parse a Decimal price out of raw text, ignoring currency symbols."""
    cleaned = _NON_NUMERIC.sub("", raw_text)
    if not cleaned:
        raise ParserStructureError(f"No numeric price in {raw_text!r}")
    try:
        return Decimal(cleaned)
    except InvalidOperation as exc:
        raise ParserStructureError(f"Cannot parse price {cleaned!r}") from exc


class BaseParser(ABC):
    """Abstract price parser with retrying HTTP GET helper."""

    source: ProductSource
    currency: str | None = None  # None = must be supplied by the user

    def __init__(
        self,
        *,
        timeout: float = 10.0,
        max_retries: int = 2,
        retry_delay: float = 1.0,
    ) -> None:
        self._timeout = timeout
        self._max_retries = max_retries
        self._retry_delay = retry_delay

    @abstractmethod
    async def fetch_price(
        self, external_id: str, *, selector: str | None = None
    ) -> Decimal:
        """Fetch the current price for the given external identifier.

        ``selector`` is only used by browser-based parsers (playwright_js).
        """
        ...

    async def _get(
        self, url: str, params: dict[str, str] | None = None
    ) -> httpx.Response:
        """Perform a GET request, retrying on HTTP 403/429.

        Raises:
            ParserNetworkError: on timeout, connection or unexpected HTTP error.
            ParserBlockedError: when the source keeps returning 403/429.
        """
        for attempt in range(1, self._max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    response = await client.get(url, params=params)
            except (httpx.TimeoutException, httpx.ConnectError) as exc:
                raise ParserNetworkError(f"Request to {url} failed: {exc}") from exc

            if response.status_code in (403, 429):
                if attempt < self._max_retries:
                    await asyncio.sleep(self._retry_delay)
                    continue
                raise ParserBlockedError(
                    f"{url} returned HTTP {response.status_code} "
                    f"after {self._max_retries} attempts"
                )

            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                raise ParserNetworkError(
                    f"{url} returned HTTP {response.status_code}"
                ) from exc
            return response

        raise ParserError("unreachable")  # pragma: no cover
