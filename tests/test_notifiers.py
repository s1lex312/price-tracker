"""Tests for the notification channels and the composite."""

from decimal import Decimal
from unittest.mock import AsyncMock

from app.core.config import Settings
from app.models.enums import ProductSource
from app.models.product import Product
from app.notifiers import build_notifier
from app.notifiers.composite import CompositeNotifier
from app.notifiers.email import EmailNotifier
from app.notifiers.telegram import TelegramNotifier


def make_product() -> Product:
    return Product(
        user_telegram_id=123456,
        name="A Light in the Attic",
        source=ProductSource.BOOKS_TOSCRAPE,
        external_id="https://books.toscrape.com/catalogue/x_1/index.html",
        target_price=Decimal("60.00"),
        current_price=Decimal("51.77"),
        currency="GBP",
    )


# --- EmailNotifier ---


async def test_email_disabled_without_settings() -> None:
    notifier = EmailNotifier(Settings(smtp_host="", alert_email_to=""))

    assert notifier.enabled is False
    # must not raise, must not touch the network
    await notifier.send_price_alert(123456, make_product())


async def test_email_sends_via_smtp(monkeypatch) -> None:
    settings = Settings(
        smtp_host="smtp.test.dev",
        smtp_port=587,
        smtp_user="bot@test.dev",
        smtp_password="secret",
        alert_email_to="me@test.dev",
    )
    notifier = EmailNotifier(settings)
    mock_send = AsyncMock()
    monkeypatch.setattr("app.notifiers.email.aiosmtplib.send", mock_send)

    await notifier.send_price_alert(123456, make_product())

    assert notifier.enabled is True
    mock_send.assert_awaited_once()
    message = mock_send.await_args.args[0]
    assert message["To"] == "me@test.dev"
    assert message["From"] == "bot@test.dev"
    assert "A Light in the Attic" in message["Subject"]
    assert "51.77" in message.get_content()


# --- TelegramNotifier (offline paths) ---


async def test_telegram_disabled_without_token() -> None:
    notifier = TelegramNotifier(token="")
    # must not raise; alert is logged only
    await notifier.send_price_alert(123456, make_product())
    assert await notifier.get_bot_username() is None
    await notifier.close()


def test_telegram_message_format() -> None:
    text = TelegramNotifier._format_message(make_product())
    assert "A Light in the Attic" in text
    assert "51.77 GBP" in text
    assert "60.00 GBP" in text


# --- CompositeNotifier ---


async def test_composite_fans_out_to_all_channels() -> None:
    telegram, email = AsyncMock(), AsyncMock()
    notifier = CompositeNotifier(telegram=telegram, email=email)
    product = make_product()

    await notifier.send_price_alert(123456, product)

    telegram.send_price_alert.assert_awaited_once_with(123456, product)
    email.send_price_alert.assert_awaited_once_with(123456, product)


async def test_composite_isolates_channel_failure() -> None:
    telegram = AsyncMock()
    telegram.send_price_alert.side_effect = RuntimeError("telegram down")
    email = AsyncMock()
    notifier = CompositeNotifier(telegram=telegram, email=email)

    # telegram fails -> email still delivered, no exception propagates
    await notifier.send_price_alert(123456, make_product())

    email.send_price_alert.assert_awaited_once()


async def test_composite_close_closes_all_channels() -> None:
    telegram, email = AsyncMock(), AsyncMock()
    notifier = CompositeNotifier(telegram=telegram, email=email)

    await notifier.close()

    telegram.close.assert_awaited_once()
    email.close.assert_awaited_once()


def test_build_notifier_assembles_composite() -> None:
    notifier = build_notifier(Settings())
    assert isinstance(notifier, CompositeNotifier)
