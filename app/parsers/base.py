"""Abstract parser interface and parser exceptions."""

import asyncio
from abc import ABC, abstractmethod
from decimal import Decimal

import httpx

from app.models.enums import ProductSource


class ParserError(Exception):
    """Base error for all price parsers."""


class ParserNetworkError(ParserError):
    """Network-level failure: timeout, connection error, unexpected HTTP code."""


class ParserBlockedError(ParserError):
    """Source blocked the request (HTTP 403/429) after all retries."""


class ParserStructureError(ParserError):
    """Response received, but the price could not be extracted from it."""


class BaseParser(ABC):
    """Abstract price parser with retrying HTTP GET helper."""

    source: ProductSource
    currency: str

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
    async def fetch_price(self, external_id: str) -> Decimal:
        """Fetch the current price for the given external identifier."""
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
