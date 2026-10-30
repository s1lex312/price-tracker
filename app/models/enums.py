"""Enumerations shared across the application."""

import enum


class ProductSource(enum.StrEnum):
    """Supported price sources."""

    BOOKS_TOSCRAPE = "books_toscrape"
    COINGECKO = "coingecko"
    PLAYWRIGHT_JS = "playwright_js"
