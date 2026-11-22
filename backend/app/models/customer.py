"""Customer model."""
from sqlalchemy import String, Boolean, Integer, Numeric, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional, List

from app.database import Base, TimestampMixin, generate_uuid


class Customer(Base, TimestampMixin):
    __tablename__ = "customers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    phone: Mapped[Optional[str]] = mapped_column(String(20), index=True)
    email: Mapped[Optional[str]] = mapped_column(String(255))
    tier: Mapped[str] = mapped_column(String(20), default="regular")  # regular, vip, premium
    total_orders: Mapped[int] = mapped_column(Integer, default=0)
    total_spent: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    is_vip: Mapped[bool] = mapped_column(Boolean, default=False)
    metadata_json: Mapped[Optional[dict]] = mapped_column("metadata", JSON, default=dict)

    # Relationships
    orders: Mapped[List["Order"]] = relationship("Order", back_populates="customer")

    def __repr__(self) -> str:
        return f"<Customer {self.name} ({self.tier})>"
