"""FastAPI application factory."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.api import auth, dashboard, health, products
from app.core.config import get_settings
from app.core.exceptions import AppError, AuthRequiredError
from app.core.logging import configure_logging
from app.db.session import build_engine, build_session_factory
from app.notifiers import build_notifier

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Startup: engine/session factory, notifier, auth. Shutdown: cleanup."""
    settings = get_settings()
    configure_logging(settings.log_level)

    engine = build_engine(settings.database_url)
    app.state.session_factory = build_session_factory(engine)

    notifier = build_notifier(settings)
    app.state.notifier = notifier

    # Dashboard auth via Telegram Login Widget; off without a token
    # or when AUTH_ENABLED=false (demo mode)
    app.state.auth_enabled = settings.auth_enabled and bool(settings.alert_bot_token)
    app.state.bot_username = None
    if app.state.auth_enabled:
        try:
            app.state.bot_username = await notifier.get_bot_username()
        except Exception:
            logger.exception("Could not fetch bot username")
    if not settings.auth_enabled:
        logger.warning("Demo mode: dashboard auth disabled (AUTH_ENABLED=false)")

    logger.info("Application started (env=%s)", settings.environment)

    yield

    await notifier.close()
    await engine.dispose()


def create_app() -> FastAPI:
    """Assemble the FastAPI application."""
    settings = get_settings()
    app = FastAPI(title="Price Tracker", version="1.1.0", lifespan=lifespan)
    app.add_middleware(SessionMiddleware, secret_key=settings.secret_key)

    @app.exception_handler(AuthRequiredError)
    async def auth_required_handler(
        request: Request, exc: AuthRequiredError
    ) -> RedirectResponse:
        return RedirectResponse("/login", status_code=303)

    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    app.include_router(health.router, prefix="/api/v1")
    app.include_router(products.router, prefix="/api/v1")
    app.include_router(auth.router)
    app.include_router(dashboard.router)
    app.mount(
        "/static",
        StaticFiles(directory=BASE_DIR / "static"),
        name="static",
    )

    return app


app = create_app()
