"""Parser for the CoinGecko public API."""

from decimal import Decimal, InvalidOperation

from app.models.enums import ProductSource
from app.parsers.base import BaseParser, ParserStructureError

API_URL = "https://api.coingecko.com/api/v3/simple/price"


class CoinGeckoParser(BaseParser):
    """Fetches USD prices for CoinGecko coin ids."""

    source = ProductSource.COINGECKO
    currency = "USD"

    async def fetch_price(self, external_id: str) -> Decimal:
        """Fetch the USD price for a coin id (e.g. ``bitcoin``)."""
        response = await self._get(
            API_URL, params={"ids": external_id, "vs_currencies": "usd"}
        )
        data = response.json()
        try:
            raw_price = data[external_id]["usd"]
        except (KeyError, TypeError) as exc:
            raise ParserStructureError(
                f"No USD price for coin id {external_id!r} " "in CoinGecko response"
            ) from exc
        try:
            return Decimal(str(raw_price))
        except InvalidOperation as exc:
            raise ParserStructureError(
                f"Cannot parse CoinGecko price {raw_price!r}"
            ) from exc
