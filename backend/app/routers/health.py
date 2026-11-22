"""
Health & Readiness Endpoints
"""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.database import get_db
from app.schemas.common import HealthResponse
from app.config import get_settings

router = APIRouter()
settings = get_settings()

@router.get("/health", response_model=HealthResponse)
async def health_check(db: AsyncSession = Depends(get_db)):
    """Liveness probe with database connection validation"""
    db_status = "connected"
    try:
        await db.execute(text("SELECT 1"))
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"

    services = {
        "database": db_status,
        "sarvam_ai": "configured" if settings.has_sarvam else "mock_fallback",
        "flagsmith": "configured" if settings.has_flagsmith else "local_fallback",
        "google_maps": "configured" if settings.has_google_maps else "mock_fallback",
        "nudgebee": "configured" if settings.has_nudgebee else "simulated",
        "gemini": "configured" if settings.has_gemini else "rule_based"
    }

    return HealthResponse(
        status="healthy" if "unhealthy" not in db_status else "degraded",
        version="1.0.0",
        database=db_status,
        timestamp=datetime.now(timezone.utc),
        services=services
    )

@router.get("/ready")
async def readiness_check(db: AsyncSession = Depends(get_db)):
    """Readiness probe for Kubernetes"""
    try:
        await db.execute(text("SELECT 1"))
        return {"status": "ready"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database not ready: {str(e)}"
        )
