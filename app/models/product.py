"""Product ORM model."""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Boolean, Enum as SAEnum, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UTCDateTime
from app.models.enums import ProductSource
from app.models.price_history import PriceHistory


class Product(Base):
    """A tracked product with a target price."""

    __tablename__ = "products"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_telegram_id: Mapped[int] = mapped_column(BigInteger, index=True)
    name: Mapped[str] = mapped_column(String(255))
    source: Mapped[ProductSource] = mapped_column(
        SAEnum(ProductSource, native_enum=False, length=32)
    )
    external_id: Mapped[str] = mapped_column(String(512))
    target_price: Mapped[Decimal] = mapped_column(Numeric(18, 8))
    current_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 8))
    currency: Mapped[str] = mapped_column(String(8))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    last_error: Mapped[str | None] = mapped_column(String(1024))
    last_alert_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), server_default=func.now(), onupdate=func.now()
    )

    history: Mapped[list[PriceHistory]] = relationship(
        back_populates="product", cascade="all, delete-orphan"
    )
