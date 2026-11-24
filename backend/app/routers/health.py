"""
Health & Readiness Endpoints
Monitors live database status and integration availability without leaking sensitive credentials.
"""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db, check_database_health
from app.schemas.common import HealthResponse
from app.config import get_settings

router = APIRouter()
settings = get_settings()


@router.get("/health", response_model=HealthResponse)
async def health_check(db: AsyncSession = Depends(get_db)):
    """Liveness probe with database connection validation"""
    db_health = await check_database_health(db)
    db_status = db_health.get("status", "unknown")

    services = {
        "database": f"{db_status} ({db_health.get('type')})",
        "sarvam_ai": "configured" if settings.has_sarvam else "mock_fallback",
        "flagsmith": "configured" if settings.has_flagsmith else "local_fallback",
        "google_maps": "configured" if settings.has_google_maps else "mock_fallback",
        "gemini": "configured" if settings.has_gemini else "rule_based",
        "nudgebee": "configured" if settings.has_nudgebee_config else "simulated"
    }

    return HealthResponse(
        status="healthy" if db_status == "connected" else "degraded",
        version="1.0.0",
        database=db_status,
        timestamp=datetime.now(timezone.utc),
        services=services
    )


@router.get("/ready")
async def readiness_check(db: AsyncSession = Depends(get_db)):
    """Readiness probe for Kubernetes pod lifecycle"""
    db_health = await check_database_health(db)
    if db_health.get("status") == "connected":
        return {"status": "ready", "database": db_health.get("type")}

    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Database connection not ready"
    )
