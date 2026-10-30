"""Notification channels."""

from app.core.config import Settings
from app.notifiers.composite import CompositeNotifier
from app.notifiers.email import EmailNotifier
from app.notifiers.telegram import TelegramNotifier


def build_notifier(settings: Settings) -> CompositeNotifier:
    """Assemble the composite notifier from application settings."""
    return CompositeNotifier(
        telegram=TelegramNotifier(settings.alert_bot_token),
        email=EmailNotifier(settings),
    )


__all__ = [
    "CompositeNotifier",
    "EmailNotifier",
    "TelegramNotifier",
    "build_notifier",
]
