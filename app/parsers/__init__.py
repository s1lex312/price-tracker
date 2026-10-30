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
from app.parsers.playwright_js import PlaywrightParser

_PARSERS: dict[ProductSource, type[BaseParser]] = {
    ProductSource.BOOKS_TOSCRAPE: BooksToScrapeParser,
    ProductSource.COINGECKO: CoinGeckoParser,
    ProductSource.PLAYWRIGHT_JS: PlaywrightParser,
}


def get_parser(source: ProductSource) -> BaseParser:
    """Instantiate the parser registered for the given source."""
    return _PARSERS[source]()


def get_parser_cls(source: ProductSource) -> type[BaseParser]:
    """Return the parser class registered for the given source."""
    return _PARSERS[source]


__all__ = [
    "BaseParser",
    "ParserBlockedError",
    "ParserError",
    "ParserNetworkError",
    "ParserStructureError",
    "get_parser",
    "get_parser_cls",
]
