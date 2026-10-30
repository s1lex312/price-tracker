"""Enumerations shared across the application."""

import enum


class ProductSource(str, enum.Enum):
    """Supported price sources."""

    BOOKS_TOSCRAPE = "books_toscrape"
    COINGECKO = "coingecko"
