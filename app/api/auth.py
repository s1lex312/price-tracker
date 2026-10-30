"""Telegram Login Widget authentication for the dashboard."""

import hashlib
import hmac
import logging
import time
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from app.core.config import Settings, get_settings
from app.core.exceptions import AuthRequiredError

logger = logging.getLogger(__name__)

router = APIRouter(tags=["auth"])

templates = Jinja2Templates(
    directory=Path(__file__).resolve().parent.parent / "templates"
)

MAX_AUTH_AGE_SECONDS = 86400


def verify_telegram_auth(data: dict[str, str], bot_token: str) -> bool:
    """Verify the signature Telegram sends to the widget callback.

    See https://core.telegram.org/widgets/login#checking-authorization
    """
    check_hash = data.get("hash")
    if not check_hash:
        return False
    check_string = "\n".join(
        f"{key}={value}" for key, value in sorted(data.items()) if key != "hash"
    )
    secret = hashlib.sha256(bot_token.encode()).digest()
    computed = hmac.new(secret, check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(computed, check_hash):
        return False
    try:
        auth_date = int(data.get("auth_date", "0"))
    except ValueError:
        return False
    return 0 < time.time() - auth_date < MAX_AUTH_AGE_SECONDS


async def require_user(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
) -> int:
    """Gate for dashboard routes; returns the demo user when auth is off."""
    if not getattr(request.app.state, "auth_enabled", False):
        return settings.demo_user_id
    user_id = request.session.get("user_id")
    if user_id is None:
        raise AuthRequiredError()
    return user_id


@router.get("/login")
async def login_page(request: Request):
    """Render the login page with the Telegram widget.

    The bot username is fetched lazily and cached: Telegram API access
    may flap at startup, and a restart should not be required to heal.
    """
    if not getattr(request.app.state, "auth_enabled", False):
        return RedirectResponse("/", status_code=303)
    bot_username = getattr(request.app.state, "bot_username", None)
    if bot_username is None:
        try:
            bot_username = await request.app.state.notifier.get_bot_username()
            request.app.state.bot_username = bot_username
        except Exception:
            logger.warning("Login page: Telegram API unreachable", exc_info=True)
    return templates.TemplateResponse(
        request,
        "login.html",
        {
            "bot_username": bot_username,
            "error": request.query_params.get("error"),
        },
    )


@router.get("/auth/telegram")
async def telegram_callback(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
):
    """Widget callback: verify the signature, open a session."""
    if not getattr(request.app.state, "auth_enabled", False):
        return RedirectResponse("/", status_code=303)
    data = dict(request.query_params)
    if not verify_telegram_auth(data, settings.alert_bot_token):
        logger.warning("Telegram login failed the signature check")
        return RedirectResponse("/login?error=1", status_code=303)
    request.session["user_id"] = int(data["id"])
    request.session["first_name"] = data.get("first_name", "")
    logger.info("Telegram user %s logged in", data["id"])
    return RedirectResponse("/", status_code=303)


@router.post("/logout")
async def logout(request: Request):
    """Drop the session."""
    request.session.clear()
    return RedirectResponse("/login", status_code=303)
