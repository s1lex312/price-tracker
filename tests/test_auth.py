"""Tests for Telegram Login Widget authentication."""

import hashlib
import hmac
import time
from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.auth import MAX_AUTH_AGE_SECONDS, verify_telegram_auth
from app.api.deps import get_session
from app.core.config import Settings, get_settings
from app.main import create_app

TEST_TOKEN = "123:test-token"


def make_auth_payload(user_id: int = 42, auth_date: int | None = None) -> dict:
    """Craft a correctly signed Telegram widget callback payload."""
    data = {
        "id": str(user_id),
        "first_name": "Test",
        "auth_date": str(auth_date or int(time.time())),
    }
    check_string = "\n".join(f"{k}={v}" for k, v in sorted(data.items()))
    secret = hashlib.sha256(TEST_TOKEN.encode()).digest()
    data["hash"] = hmac.new(secret, check_string.encode(), hashlib.sha256).hexdigest()
    return data


# --- pure verification ---


def test_verify_valid_signature() -> None:
    assert verify_telegram_auth(make_auth_payload(), TEST_TOKEN) is True


def test_verify_tampered_payload() -> None:
    data = make_auth_payload()
    data["first_name"] = "Mallory"  # signature no longer matches
    assert verify_telegram_auth(data, TEST_TOKEN) is False


def test_verify_expired_auth_date() -> None:
    stale = int(time.time()) - MAX_AUTH_AGE_SECONDS - 10
    data = make_auth_payload(auth_date=stale)  # valid signature, old date
    assert verify_telegram_auth(data, TEST_TOKEN) is False


def test_verify_missing_hash() -> None:
    data = make_auth_payload()
    del data["hash"]
    assert verify_telegram_auth(data, TEST_TOKEN) is False


# --- HTTP flow ---


@pytest.fixture
async def auth_client(session_factory) -> AsyncIterator[AsyncClient]:
    """Client for an app with Telegram auth ENABLED."""
    app = create_app()

    async def override_get_session() -> AsyncIterator:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_settings] = lambda: Settings(
        alert_bot_token=TEST_TOKEN
    )
    app.state.auth_enabled = True
    app.state.bot_username = "pricecheck111_bot"

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as test_client:
        yield test_client


async def test_dashboard_requires_login(auth_client: AsyncClient) -> None:
    resp = await auth_client.get("/")

    assert resp.status_code == 303
    assert resp.headers["location"] == "/login"


async def test_login_page_renders_widget(auth_client: AsyncClient) -> None:
    resp = await auth_client.get("/login")

    assert resp.status_code == 200
    assert "telegram-widget.js" in resp.text
    assert "pricecheck111_bot" in resp.text


async def test_callback_valid_signature_logs_in(
    auth_client: AsyncClient,
) -> None:
    payload = make_auth_payload()
    resp = await auth_client.get("/auth/telegram", params=payload)

    assert resp.status_code == 303
    assert resp.headers["location"] == "/"
    assert "session" in auth_client.cookies

    # session now unlocks the dashboard
    dashboard = await auth_client.get("/")
    assert dashboard.status_code == 200


async def test_callback_bad_signature_rejected(
    auth_client: AsyncClient,
) -> None:
    payload = make_auth_payload()
    payload["first_name"] = "Mallory"

    resp = await auth_client.get("/auth/telegram", params=payload)

    assert resp.status_code == 303
    assert resp.headers["location"] == "/login?error=1"

    dashboard = await auth_client.get("/")
    assert dashboard.status_code == 303


async def test_logout(auth_client: AsyncClient) -> None:
    await auth_client.get("/auth/telegram", params=make_auth_payload())

    resp = await auth_client.post("/logout")

    assert resp.status_code == 303
    dashboard = await auth_client.get("/")
    assert dashboard.status_code == 303


async def test_api_stays_open_without_session(
    auth_client: AsyncClient,
) -> None:
    resp = await auth_client.get("/api/v1/products")
    assert resp.status_code == 200
