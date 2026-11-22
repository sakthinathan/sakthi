"""Audit logging service — records all significant actions."""
from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.audit import AuditLog


async def log_action(
    db: AsyncSession,
    entity_type: str,
    action: str,
    entity_id: Optional[str] = None,
    actor: str = "system",
    details: Optional[Dict[str, Any]] = None,
) -> AuditLog:
    """Record an action in the audit trail."""
    entry = AuditLog(
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        actor=actor,
        details=details or {},
    )
    db.add(entry)
    await db.flush()
    return entry
