"""Repositories: database access layer."""

from app.repositories.price_history import PriceHistoryRepository
from app.repositories.product import ProductRepository

__all__ = ["PriceHistoryRepository", "ProductRepository"]
