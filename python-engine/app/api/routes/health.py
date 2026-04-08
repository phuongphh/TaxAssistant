import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.db.database import engine as db_engine

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check():
    """Readiness check — verifies database connectivity."""
    checks: dict = {"service": "tax-assistant-engine"}
    healthy = True

    # Database
    try:
        async with db_engine.connect() as conn:
            await conn.execute(__import__("sqlalchemy").text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as e:
        checks["database"] = f"error: {type(e).__name__}"
        healthy = False
        logger.warning("Health check: database unreachable: %s", e)

    checks["status"] = "healthy" if healthy else "degraded"
    status_code = 200 if healthy else 503
    return JSONResponse(content=checks, status_code=status_code)


@router.get("/health/live")
async def liveness():
    """Liveness probe — always returns 200 if the process is running."""
    return {"status": "alive"}
