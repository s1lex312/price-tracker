"""Email alert notifications via SMTP (STARTTLS)."""

import logging
from email.message import EmailMessage

import aiosmtplib

from app.core.config import Settings
from app.models.product import Product

logger = logging.getLogger(__name__)


class EmailNotifier:
    """Sends price alerts by email; disabled without SMTP settings."""

    def __init__(self, settings: Settings) -> None:
        self._host = settings.smtp_host
        self._port = settings.smtp_port
        self._user = settings.smtp_user
        self._password = settings.smtp_password
        self._from = settings.smtp_from or settings.smtp_user
        self._to = settings.alert_email_to

    @property
    def enabled(self) -> bool:
        """True when both the server and the recipient are configured."""
        return bool(self._host and self._to)

    async def send_price_alert(self, user_telegram_id: int, product: Product) -> None:
        """Send the alert email; logs and no-ops when not configured."""
        if not self.enabled:
            logger.info(
                "SMTP not configured, email alert logged only: %s",
                product.name,
            )
            return
        await aiosmtplib.send(
            self._build_message(product),
            hostname=self._host,
            port=self._port,
            username=self._user or None,
            password=self._password or None,
            start_tls=True,
        )
        logger.info("Email alert for %s sent to %s", product.name, self._to)

    async def close(self) -> None:
        """No persistent resources (kept for interface symmetry)."""

    def _build_message(self, product: Product) -> EmailMessage:
        message = EmailMessage()
        message["Subject"] = f"Price Tracker: {product.name}"
        message["From"] = self._from
        message["To"] = self._to
        message.set_content(
            "Цена упала ниже порога!\n\n"
            f"Товар: {product.name}\n"
            f"Текущая цена: {product.current_price} {product.currency}\n"
            f"Целевая цена: {product.target_price} {product.currency}\n"
            f"Источник: {product.external_id}\n"
        )
        return message
