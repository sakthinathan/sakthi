"""Dispatch and delivery details model."""
from sqlalchemy import String, Integer, Numeric, Text, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional
from datetime import datetime

from app.database import Base, TimestampMixin, generate_uuid


class DispatchDetail(Base, TimestampMixin):
    """Delivery address validation and dispatch information."""
    __tablename__ = "dispatch_details"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    order_id: Mapped[str] = mapped_column(String(36), ForeignKey("orders.id"), unique=True, nullable=False)
    delivery_address: Mapped[str] = mapped_column(Text, nullable=False)
    validated_address: Mapped[Optional[str]] = mapped_column(Text)
    validation_status: Mapped[str] = mapped_column(String(20), default="pending")
    # Statuses: pending, validated, invalid, partial_match
    latitude: Mapped[Optional[float]] = mapped_column(Numeric(10, 7))
    longitude: Mapped[Optional[float]] = mapped_column(Numeric(10, 7))
    geocoding_status: Mapped[Optional[str]] = mapped_column(String(20))
    aqi_value: Mapped[Optional[int]] = mapped_column(Integer)
    aqi_category: Mapped[Optional[str]] = mapped_column(String(50))
    dispatch_status: Mapped[str] = mapped_column(String(20), default="pending")
    # Dispatch statuses: pending, assigned, in_transit, delivered
    estimated_delivery: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Relationships
    order: Mapped["Order"] = relationship("Order", back_populates="dispatch")

    def __repr__(self) -> str:
        return f"<DispatchDetail order={self.order_id[:8]} ({self.dispatch_status})>"
