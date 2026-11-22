"""Incident and incident action models for AIOps."""
from sqlalchemy import String, Boolean, Text, JSON, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional, List
from datetime import datetime

from app.database import Base, TimestampMixin, generate_uuid


class Incident(Base, TimestampMixin):
    """Service incident record."""
    __tablename__ = "incidents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    service_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    # Severities: critical, high, medium, low
    status: Mapped[str] = mapped_column(String(20), default="detected", index=True)
    # Statuses: detected, investigating, mitigating, resolved, closed
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(__import__('datetime').timezone.utc),
    )
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    root_cause: Mapped[Optional[str]] = mapped_column(Text)
    evidence: Mapped[Optional[dict]] = mapped_column(JSON, default=dict)

    # Relationships
    actions: Mapped[List["IncidentAction"]] = relationship(
        "IncidentAction", back_populates="incident", cascade="all, delete-orphan",
        order_by="IncidentAction.created_at",
    )

    def __repr__(self) -> str:
        return f"<Incident {self.title} ({self.status})>"


class IncidentAction(Base, TimestampMixin):
    """An action taken or proposed during incident response."""
    __tablename__ = "incident_actions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    incident_id: Mapped[str] = mapped_column(String(36), ForeignKey("incidents.id"), nullable=False)
    action_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # Types: investigation, mitigation, escalation, communication, restoration
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="proposed")
    # Statuses: proposed, approved, executing, completed, failed, rolled_back
    requires_approval: Mapped[bool] = mapped_column(Boolean, default=True)
    approved_by: Mapped[Optional[str]] = mapped_column(String(100))
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    executed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    result: Mapped[Optional[dict]] = mapped_column(JSON)
    rollback_info: Mapped[Optional[dict]] = mapped_column(JSON)

    # Relationships
    incident: Mapped["Incident"] = relationship("Incident", back_populates="actions")

    def __repr__(self) -> str:
        return f"<IncidentAction {self.action_type} ({self.status})>"
