"""Tests for the demo mode (AUTH_ENABLED=false)."""

from collections.abc import AsyncIterator

from httpx import ASGITransport, AsyncClient

from app.api.deps import get_session
from app.core.config import Settings, get_settings
from app.main import create_app


def make_client(session_factory, auth_enabled: bool) -> AsyncClient:
    """Client for an app with a given dashboard-auth state."""
    app = create_app()

    async def override_get_session() -> AsyncIterator:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_settings] = lambda: Settings(auth_enabled=auth_enabled)
    # mirror the lifespan decision
    app.state.auth_enabled = auth_enabled
    app.state.bot_username = None
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def test_demo_mode_dashboard_open_without_session(
    session_factory,
) -> None:
    async with make_client(session_factory, auth_enabled=False) as client:
        resp = await client.get("/")

    assert resp.status_code == 200
    assert "Demo mode (AUTH_ENABLED=false)" in resp.text


async def test_auth_enabled_dashboard_requires_login(session_factory) -> None:
    async with make_client(session_factory, auth_enabled=True) as client:
        resp = await client.get("/")

    assert resp.status_code == 303
    assert resp.headers["location"] == "/login"
