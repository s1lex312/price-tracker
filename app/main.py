"""FastAPI application factory."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api import health, products
from app.core.config import get_settings
from app.core.exceptions import AppError
from app.core.logging import configure_logging
from app.db.session import build_engine, build_session_factory
from app.scheduler.jobs import check_prices_job

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Startup: engine/session factory. Shutdown: dispose engine."""
    settings = get_settings()
    configure_logging(settings.log_level)

    engine = build_engine(settings.database_url)
    app.state.session_factory = build_session_factory(engine)

    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        check_prices_job,
        trigger=IntervalTrigger(minutes=settings.scheduler_interval_minutes),
        args=[app.state.session_factory, None, settings],
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
    await engine.dispose()


def create_app() -> FastAPI:
    """Assemble the FastAPI application."""
    app = FastAPI(title="Price Tracker", version="1.0.0", lifespan=lifespan)

    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    app.include_router(health.router, prefix="/api/v1")
    app.include_router(products.router, prefix="/api/v1")

    return app


app = create_app()
