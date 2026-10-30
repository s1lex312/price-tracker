"""Parser for the books.toscrape.com training site."""

from decimal import Decimal

from bs4 import BeautifulSoup

from app.models.enums import ProductSource
from app.parsers.base import BaseParser, ParserStructureError, extract_price


class BooksToScrapeParser(BaseParser):
    """Extracts the GBP price from a books.toscrape.com product page."""

    source = ProductSource.BOOKS_TOSCRAPE
    currency = "GBP"

    async def fetch_price(
        self, external_id: str, *, selector: str | None = None
    ) -> Decimal:
        """Fetch the price from a full product page URL."""
        response = await self._get(external_id)
        soup = BeautifulSoup(response.text, "html.parser")
        node = soup.select_one("p.price_color")
        if node is None:
            raise ParserStructureError(
                f"Price element (.price_color) not found at {external_id}"
            )
        return extract_price(node.get_text(strip=True))
