"""Price history ORM model."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, Numeric, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UTCDateTime

if TYPE_CHECKING:
    from app.models.product import Product


class PriceHistory(Base):
    """A single price observation for a product."""

    __tablename__ = "price_history"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE")
    )
    price: Mapped[Decimal] = mapped_column(Numeric(18, 8))
    checked_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), server_default=func.now()
    )

    product: Mapped["Product"] = relationship(back_populates="history")

    __table_args__ = (
        Index("ix_price_history_product_checked", "product_id", "checked_at"),
    )
