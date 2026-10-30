"""Price parsers for supported sources."""

from app.models.enums import ProductSource
from app.parsers.base import (
    BaseParser,
    ParserBlockedError,
    ParserError,
    ParserNetworkError,
    ParserStructureError,
)
from app.parsers.books_toscrape import BooksToScrapeParser
from app.parsers.coingecko import CoinGeckoParser

_PARSERS: dict[ProductSource, type[BaseParser]] = {
    ProductSource.BOOKS_TOSCRAPE: BooksToScrapeParser,
    ProductSource.COINGECKO: CoinGeckoParser,
}


def get_parser(source: ProductSource) -> BaseParser:
    """Instantiate the parser registered for the given source."""
    return _PARSERS[source]()


__all__ = [
    "BaseParser",
    "ParserBlockedError",
    "ParserError",
    "ParserNetworkError",
    "ParserStructureError",
    "get_parser",
]
