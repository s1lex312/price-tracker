"""Pydantic schemas for the products API."""

import re
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator

from app.models.enums import ProductSource

_COIN_ID = re.compile(r"[a-z0-9-]+")


class ProductCreate(BaseModel):
    """Payload for creating a tracked product."""

    name: str = Field(min_length=1, max_length=255)
    source: ProductSource
    external_id: str = Field(min_length=1, max_length=512)
    target_price: Decimal = Field(gt=0)
    currency: str | None = Field(default=None, max_length=8)
    user_telegram_id: int

    @field_validator("external_id")
    @classmethod
    def check_external_id(cls, value: str, info: ValidationInfo) -> str:
        """Validate external_id against the rules of the chosen source."""
        source = info.data.get("source")
        if source == ProductSource.BOOKS_TOSCRAPE:
            if "books.toscrape.com" not in value:
                raise ValueError("external_id must be a books.toscrape.com URL")
        elif source == ProductSource.COINGECKO:
            if not _COIN_ID.fullmatch(value):
                raise ValueError(
                    "external_id must be a CoinGecko coin id "
                    "(lowercase slug, e.g. 'bitcoin')"
                )
        return value


class ProductRead(BaseModel):
    """Product representation returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_telegram_id: int
    name: str
    source: ProductSource
    external_id: str
    target_price: Decimal
    current_price: Decimal | None
    currency: str
    is_active: bool
    last_error: str | None
    last_alert_at: datetime | None
    created_at: datetime
    updated_at: datetime


class PricePoint(BaseModel):
    """A single price observation."""

    model_config = ConfigDict(from_attributes=True)

    price: Decimal
    checked_at: datetime
