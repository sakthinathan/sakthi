"""
Customer Management Service
Handles customer lookup, VIP eligibility, and lifetime value calculation.
"""
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.customer import Customer
from app.models.order import Order

async def get_or_create_customer(
    db: AsyncSession,
    name: str,
    phone: Optional[str] = None,
    email: Optional[str] = None
) -> Customer:
    """Find existing customer by phone or name, or create a new one"""
    customer = None
    if phone:
        stmt = select(Customer).where(Customer.phone == phone).order_by(Customer.created_at.asc())
        customer = (await db.execute(stmt)).scalars().first()

    if not customer and name:
        stmt = select(Customer).where(Customer.name.ilike(name)).order_by(Customer.created_at.asc())
        customer = (await db.execute(stmt)).scalars().first()

    if not customer:
        customer = Customer(
            name=name,
            phone=phone,
            email=email,
            tier="regular",
            is_vip=False
        )
        db.add(customer)
        await db.flush()

    return customer

async def update_customer_stats(db: AsyncSession, customer_id: str) -> None:
    """Recalculate total orders and spend from order records"""
    stmt = select(Customer).where(Customer.id == customer_id)
    customer = (await db.execute(stmt)).scalar_one_or_none()
    if not customer:
        return

    orders_stmt = select(Order).where(Order.customer_id == customer_id, Order.status == "approved")
    orders = (await db.execute(orders_stmt)).scalars().all()

    customer.total_orders = len(orders)
    customer.total_spent = sum(float(o.total or 0) for o in orders)

    # Automatic VIP Promotion rule: >= 5 orders or >= 10,000 INR
    if customer.total_orders >= 5 or customer.total_spent >= 10000.0:
        customer.is_vip = True
        customer.tier = "vip"

    await db.flush()
