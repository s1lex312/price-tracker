"""FastAPI application factory."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
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
from app.scheduler.jobs import check_prices_job

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Startup: engine/session factory. Shutdown: dispose engine."""
    settings = get_settings()
    configure_logging(settings.log_level)

    engine = build_engine(settings.database_url)
    app.state.session_factory = build_session_factory(engine)

    notifier = build_notifier(settings)
    app.state.notifier = notifier

    # Dashboard auth via Telegram Login Widget; disabled without a token
    app.state.auth_enabled = bool(settings.alert_bot_token)
    app.state.bot_username = None
    if app.state.auth_enabled:
        try:
            app.state.bot_username = await notifier.get_bot_username()
        except Exception:
            logger.exception("Could not fetch bot username")

    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        check_prices_job,
        trigger=IntervalTrigger(minutes=settings.scheduler_interval_minutes),
        args=[app.state.session_factory, notifier, settings],
        id="price_check",
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()
    app.state.scheduler = scheduler
    logger.info(
        "Application started (env=%s, price check every %d min)",
        settings.environment,
        settings.scheduler_interval_minutes,
    )

    yield

    scheduler.shutdown(wait=False)
    await notifier.close()
    await engine.dispose()


def create_app() -> FastAPI:
    """Assemble the FastAPI application."""
    settings = get_settings()
    app = FastAPI(title="Price Tracker", version="1.0.0", lifespan=lifespan)
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
