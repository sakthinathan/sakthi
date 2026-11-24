"""
Order Business Logic Service
Handles order number generation, persistence, item calculation, and VIP rule application.
"""
from datetime import datetime, timezone
import random
from typing import Dict, Any, Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models.order import Order, OrderItem, OrderInput
from app.models.customer import Customer
from app.models.dispatch import DispatchDetail
from app.services.flagsmith_service import flagsmith_service
from app.services.audit_service import log_action
import structlog

logger = structlog.get_logger()

def generate_order_number() -> str:
    """Generate sequential order number format: UTS-DDMMYY-XXXX"""
    now = datetime.now(timezone.utc)
    date_str = now.strftime("%d%m%y")
    rand_seq = random.randint(1000, 9999)
    return f"UTS-{date_str}-{rand_seq}"

async def get_order_with_relations(db: AsyncSession, order_id: str) -> Optional[Order]:
    """Fetch order with eager loaded relations"""
    stmt = (
        select(Order)
        .where(Order.id == order_id)
        .options(
            selectinload(Order.customer),
            selectinload(Order.order_input),
            selectinload(Order.items),
            selectinload(Order.dispatch),
        )
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()

async def create_order_from_extraction(
    db: AsyncSession,
    extracted_data: Dict[str, Any],
    order_input_id: str,
    idempotency_key: Optional[str] = None
) -> Order:
    """Create customer, order, items and initial dispatch from extracted order data"""
    if idempotency_key:
        stmt = select(Order).where(Order.idempotency_key == idempotency_key)
        existing = (await db.execute(stmt)).scalar_one_or_none()
        if existing:
            logger.info("Idempotent order lookup matched existing order", order_id=existing.id)
            return existing

    customer_name = extracted_data.get("customer_name") or "Valued Festive Customer"
    phone = extracted_data.get("phone")
    delivery_address = extracted_data.get("delivery_address") or "Bengaluru, Karnataka"

    # Match or create customer
    customer = None
    if phone:
        cust_stmt = select(Customer).where(Customer.phone == phone).order_by(Customer.created_at.asc())
        customer = (await db.execute(cust_stmt)).scalars().first()

    if not customer:
        customer = Customer(
            name=customer_name,
            phone=phone,
            tier="regular",
            is_vip=False
        )
        db.add(customer)
        await db.flush()

    order = Order(
        order_number=generate_order_number(),
        customer_id=customer.id,
        order_input_id=order_input_id,
        status="pending_review",
        priority="normal",
        is_express=False,
        is_vip_order=customer.is_vip,
        special_instructions=extracted_data.get("special_instructions"),
        idempotency_key=idempotency_key
    )
    db.add(order)
    await db.flush()

    # Create Order Items
    items_data = extracted_data.get("items", [])
    total_amount = 0.0
    for it in items_data:
        p_name = it.get("product_name", "Festive Item")
        qty = int(it.get("quantity", 1))
        unit_p = float(it.get("unit_price") or 350.0)
        item_tot = qty * unit_p
        total_amount += item_tot

        order_item = OrderItem(
            order_id=order.id,
            product_name=p_name,
            quantity=qty,
            unit_price=unit_p,
            total_price=item_tot,
            confidence=extracted_data.get("confidence", 0.9)
        )
        db.add(order_item)

    order.subtotal = total_amount
    order.total = total_amount

    # Create initial dispatch entry
    dispatch = DispatchDetail(
        order_id=order.id,
        delivery_address=delivery_address,
        validation_status="pending",
        dispatch_status="pending"
    )
    db.add(dispatch)

    await db.flush()
    await log_action(
        db,
        entity_type="order",
        action="created_from_extraction",
        entity_id=order.id,
        actor="sarvam_intelligence",
        details={"order_number": order.order_number, "items_count": len(items_data)}
    )

    return order

async def apply_vip_rules(db: AsyncSession, order: Order) -> Order:
    """Evaluate VIP rules and update priority/express flag using Flagsmith live identity traits"""
    is_vip = bool(order.customer and (order.customer.is_vip or order.customer.tier in ["vip", "premium"]))
    customer_id = str(order.customer_id) if order.customer_id else None

    vip_eval = flagsmith_service.evaluate_vip_express_delivery(customer_id=customer_id, is_vip=is_vip)

    order.is_vip_order = is_vip
    order.priority = "high" if is_vip else "normal"
    order.is_express = vip_eval["allowed"]
    return order
