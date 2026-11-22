"""Order, OrderItem, and OrderInput models."""
from sqlalchemy import String, Boolean, Integer, Numeric, Text, JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional, List

from app.database import Base, TimestampMixin, generate_uuid


class OrderInput(Base, TimestampMixin):
    """Stores the original unprocessed input (image/audio/text)."""
    __tablename__ = "order_inputs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    input_type: Mapped[str] = mapped_column(String(20), nullable=False)  # image, audio, text
    file_path: Mapped[Optional[str]] = mapped_column(String(500))
    original_text: Mapped[Optional[str]] = mapped_column(Text)
    original_language: Mapped[Optional[str]] = mapped_column(String(10))
    sarvam_response: Mapped[Optional[dict]] = mapped_column(JSON)
    extraction_confidence: Mapped[Optional[float]] = mapped_column(Numeric(5, 4))
    processing_status: Mapped[str] = mapped_column(String(20), default="pending")
    error_message: Mapped[Optional[str]] = mapped_column(Text)

    # Relationships
    order: Mapped[Optional["Order"]] = relationship("Order", back_populates="order_input", uselist=False)

    def __repr__(self) -> str:
        return f"<OrderInput {self.id[:8]} ({self.input_type}, {self.processing_status})>"


class Order(Base, TimestampMixin):
    """Main order record."""
    __tablename__ = "orders"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    order_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    customer_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("customers.id"))
    order_input_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("order_inputs.id"))
    status: Mapped[str] = mapped_column(String(20), default="pending_review", index=True)
    # Statuses: pending_review, approved, rejected, processing, dispatched, delivered, cancelled
    priority: Mapped[str] = mapped_column(String(20), default="normal")
    is_express: Mapped[bool] = mapped_column(Boolean, default=False)
    is_vip_order: Mapped[bool] = mapped_column(Boolean, default=False)
    special_instructions: Mapped[Optional[str]] = mapped_column(Text)
    subtotal: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    total: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    review_notes: Mapped[Optional[str]] = mapped_column(Text)
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(100), unique=True)

    # Relationships
    customer: Mapped[Optional["Customer"]] = relationship("Customer", back_populates="orders")
    order_input: Mapped[Optional["OrderInput"]] = relationship("OrderInput", back_populates="order")
    items: Mapped[List["OrderItem"]] = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")
    dispatch: Mapped[Optional["DispatchDetail"]] = relationship("DispatchDetail", back_populates="order", uselist=False)

    def __repr__(self) -> str:
        return f"<Order {self.order_number} ({self.status})>"


class OrderItem(Base, TimestampMixin):
    """Individual line item within an order."""
    __tablename__ = "order_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    order_id: Mapped[str] = mapped_column(String(36), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    product_name: Mapped[str] = mapped_column(String(255), nullable=False)
    product_name_original: Mapped[Optional[str]] = mapped_column(String(255))
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    unit_price: Mapped[Optional[float]] = mapped_column(Numeric(10, 2))
    total_price: Mapped[Optional[float]] = mapped_column(Numeric(10, 2))
    confidence: Mapped[Optional[float]] = mapped_column(Numeric(5, 4))

    # Relationships
    order: Mapped["Order"] = relationship("Order", back_populates="items")

    def __repr__(self) -> str:
        return f"<OrderItem {self.product_name} x{self.quantity}>"
