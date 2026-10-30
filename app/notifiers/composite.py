"""Composite notifier: fans alerts out to every configured channel."""

import logging

from app.models.product import Product
from app.notifiers.email import EmailNotifier
from app.notifiers.telegram import TelegramNotifier

logger = logging.getLogger(__name__)


class CompositeNotifier:
    """Delivers each alert via Telegram and email.

    A failing channel never blocks the others and never propagates.
    """

    def __init__(self, telegram: TelegramNotifier, email: EmailNotifier) -> None:
        self._telegram = telegram
        self._email = email

    async def send_price_alert(self, user_telegram_id: int, product: Product) -> None:
        """Send the alert through all channels, isolating failures."""
        for channel in (self._telegram, self._email):
            try:
                await channel.send_price_alert(user_telegram_id, product)
            except Exception:
                logger.exception(
                    "Alert channel %s failed for product %s",
                    type(channel).__name__,
                    product.id,
                )

    async def get_bot_username(self) -> str | None:
        """Delegate to the Telegram channel (login widget needs it)."""
        return await self._telegram.get_bot_username()

    async def close(self) -> None:
        """Release resources held by all channels."""
        await self._telegram.close()
        await self._email.close()
