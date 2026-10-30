"""Health check endpoint."""

import logging

from fastapi import APIRouter, Request
from sqlalchemy import text

from app.api.deps import SessionDep

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


@router.get("/health")
async def health(request: Request, session: SessionDep) -> dict[str, str]:
    """Report API, database and scheduler status."""
    try:
        await session.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception:
        logger.exception("Health check: database probe failed")
        db_status = "error"

    scheduler = getattr(request.app.state, "scheduler", None)
    scheduler_status = (
        "running"
        if scheduler is not None and scheduler.running
        else "stopped"
    )
    return {"status": "ok", "db": db_status, "scheduler": scheduler_status}
