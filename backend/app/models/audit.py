"""Audit log and feature flag snapshot models."""
from sqlalchemy import String, JSON, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from typing import Optional
from datetime import datetime, timezone

from app.database import Base, generate_uuid


class AuditLog(Base):
    """Immutable audit trail for all significant actions."""
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    entity_id: Mapped[Optional[str]] = mapped_column(String(36))
    action: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    actor: Mapped[str] = mapped_column(String(100), default="system")
    details: Mapped[Optional[dict]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )

    def __repr__(self) -> str:
        return f"<AuditLog {self.entity_type}.{self.action} by {self.actor}>"


class FeatureFlagSnapshot(Base):
    """Point-in-time snapshot of feature flag evaluations."""
    __tablename__ = "feature_flag_snapshots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    flag_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    flag_value: Mapped[dict] = mapped_column(JSON, nullable=False)
    evaluated_for: Mapped[Optional[str]] = mapped_column(String(255))
    source: Mapped[str] = mapped_column(String(20), default="flagsmith")
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<FeatureFlagSnapshot {self.flag_name}={self.flag_value}>"
