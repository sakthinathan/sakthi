"""
Customers Router
Manage festive customer profiles, tiers, and VIP status.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from typing import Optional, List

from app.database import get_db
from app.models.customer import Customer
from app.schemas.customer import (
    CustomerCreate, CustomerUpdate, CustomerResponse, CustomerListResponse
)
from app.services.audit_service import log_action

router = APIRouter()

@router.get("", response_model=CustomerListResponse)
async def list_customers(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    vip_only: Optional[bool] = None,
    search: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """List customer directory with VIP filter and search"""
    query = select(Customer).order_by(desc(Customer.total_spent))

    if vip_only is not None:
        query = query.where(Customer.is_vip == vip_only)

    if search:
        query = query.where(
            (Customer.name.ilike(f"%{search}%")) |
            (Customer.phone.ilike(f"%{search}%"))
        )

    count_stmt = select(func.count(Customer.id))
    if vip_only is not None:
        count_stmt = count_stmt.where(Customer.is_vip == vip_only)
    total = (await db.execute(count_stmt)).scalar() or 0

    offset = (page - 1) * per_page
    query = query.offset(offset).limit(per_page)
    customers = (await db.execute(query)).scalars().all()

    return CustomerListResponse(
        customers=[CustomerResponse.model_validate(c) for c in customers],
        total=total,
        page=page,
        per_page=per_page
    )

@router.get("/{customer_id}", response_model=CustomerResponse)
async def get_customer(customer_id: str, db: AsyncSession = Depends(get_db)):
    """Fetch customer details"""
    stmt = select(Customer).where(Customer.id == customer_id)
    customer = (await db.execute(stmt)).scalar_one_or_none()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    return CustomerResponse.model_validate(customer)

@router.post("", response_model=CustomerResponse)
async def create_customer(
    data: CustomerCreate,
    db: AsyncSession = Depends(get_db)
):
    """Register customer manually"""
    customer = Customer(
        name=data.name,
        phone=data.phone,
        email=data.email,
        tier=data.tier,
        is_vip=data.is_vip or data.tier in ["vip", "premium"]
    )
    db.add(customer)
    await db.commit()
    await db.refresh(customer)
    return CustomerResponse.model_validate(customer)

@router.post("/{customer_id}/vip")
async def toggle_vip(customer_id: str, db: AsyncSession = Depends(get_db)):
    """Toggle VIP customer status"""
    stmt = select(Customer).where(Customer.id == customer_id)
    customer = (await db.execute(stmt)).scalar_one_or_none()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    customer.is_vip = not customer.is_vip
    customer.tier = "vip" if customer.is_vip else "regular"

    await log_action(
        db,
        entity_type="customer",
        action="vip_status_toggled",
        entity_id=customer.id,
        actor="operator",
        details={"new_vip_status": customer.is_vip, "tier": customer.tier}
    )
    await db.commit()
    return {"id": customer.id, "name": customer.name, "is_vip": customer.is_vip, "tier": customer.tier}
