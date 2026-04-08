from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "tax-assistant-engine",
    }


@router.get("/health/live")
async def liveness():
    return {"status": "alive"}
