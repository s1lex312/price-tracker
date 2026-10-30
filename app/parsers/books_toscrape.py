"""Parser for the books.toscrape.com training site."""

import re
from decimal import Decimal, InvalidOperation

from bs4 import BeautifulSoup

from app.models.enums import ProductSource
from app.parsers.base import BaseParser, ParserStructureError

_NON_NUMERIC = re.compile(r"[^0-9.]")


class BooksToScrapeParser(BaseParser):
    """Extracts the GBP price from a books.toscrape.com product page."""

    source = ProductSource.BOOKS_TOSCRAPE
    currency = "GBP"

    async def fetch_price(self, external_id: str) -> Decimal:
        """Fetch the price from a full product page URL."""
        response = await self._get(external_id)
        soup = BeautifulSoup(response.text, "html.parser")
        node = soup.select_one("p.price_color")
        if node is None:
            raise ParserStructureError(
                f"Price element (.price_color) not found at {external_id}"
            )
        cleaned = _NON_NUMERIC.sub("", node.get_text(strip=True))
        try:
            return Decimal(cleaned)
        except InvalidOperation as exc:
            raise ParserStructureError(
                f"Cannot parse price {cleaned!r} at {external_id}"
            ) from exc
