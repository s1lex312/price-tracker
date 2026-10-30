"""Health check endpoint."""

import logging

import redis.asyncio as aioredis
from fastapi import APIRouter
from sqlalchemy import text

from app.api.deps import SessionDep
from app.core.config import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


@router.get("/health")
async def health(session: SessionDep) -> dict[str, str]:
    """Report API, database and task-queue (Redis) status."""
    try:
        await session.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception:
        logger.exception("Health check: database probe failed")
        db_status = "error"

    redis_client = aioredis.from_url(
        get_settings().redis_url,
        socket_timeout=1,
        socket_connect_timeout=1,
    )
    try:
        await redis_client.ping()
        scheduler_status = "running"
    except Exception:
        logger.warning("Health check: Redis ping failed")
        scheduler_status = "stopped"
    finally:
        await redis_client.aclose()

    return {"status": "ok", "db": db_status, "scheduler": scheduler_status}
