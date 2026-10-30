"""FastAPI application factory."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api import health, products
from app.core.config import get_settings
from app.core.exceptions import AppError
from app.core.logging import configure_logging
from app.db.session import build_engine, build_session_factory

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Startup: engine/session factory. Shutdown: dispose engine."""
    settings = get_settings()
    configure_logging(settings.log_level)

    engine = build_engine(settings.database_url)
    app.state.session_factory = build_session_factory(engine)
    logger.info("Application started (env=%s)", settings.environment)

    yield

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
