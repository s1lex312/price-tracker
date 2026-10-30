"""Telegram alert notifications."""

import logging

from aiogram import Bot

from app.models.product import Product

logger = logging.getLogger(__name__)


class TelegramNotifier:
    """Sends price alerts through a Telegram bot.

    With an empty token the notifier degrades to logging, so local
    development and CI do not require a real bot.
    """

    def __init__(self, token: str) -> None:
        self._bot = Bot(token=token) if token else None

    async def send_price_alert(self, user_telegram_id: int, product: Product) -> None:
        """Notify a user that the product dropped to/below the target."""
        if self._bot is None:
            logger.info(
                "ALERT_BOT_TOKEN not set, alert logged only: " "%s -> telegram user %s",
                product.name,
                user_telegram_id,
            )
            return
        await self._bot.send_message(
            chat_id=user_telegram_id, text=self._format_message(product)
        )

    async def close(self) -> None:
        """Release the bot's HTTP session."""
        if self._bot is not None:
            await self._bot.session.close()

    @staticmethod
    def _format_message(product: Product) -> str:
        return (
            "\U0001f514 Цена упала ниже порога!\n"
            f"Товар: {product.name}\n"
            f"Текущая цена: {product.current_price} {product.currency}\n"
            f"Целевая цена: {product.target_price} {product.currency}\n"
            f"Источник: {product.external_id}"
        )
