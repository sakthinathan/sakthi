"""
Audit Logs Router
Immutable audit trail for compliance and operational observability.
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from typing import Optional, List

from app.database import get_db
from app.models.audit import AuditLog
from app.schemas.common import AuditLogResponse

router = APIRouter()

@router.get("", response_model=List[AuditLogResponse])
async def list_audit_logs(
    entity_type: Optional[str] = None,
    action: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db)
):
    """Fetch audit history in reverse chronological order"""
    query = select(AuditLog).order_by(desc(AuditLog.created_at)).limit(limit)

    if entity_type:
        query = query.where(AuditLog.entity_type == entity_type)
    if action:
        query = query.where(AuditLog.action == action)

    logs = (await db.execute(query)).scalars().all()
    return [AuditLogResponse.model_validate(l) for l in logs]
