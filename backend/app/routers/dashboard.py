"""
Dashboard Router
Statistics, metrics, active incidents, and service health overview.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.database import get_db
from app.models.order import Order
from app.models.customer import Customer
from app.models.incident import Incident
from app.schemas.common import DashboardStats

router = APIRouter()

@router.get("/stats", response_model=DashboardStats)
async def get_dashboard_stats(db: AsyncSession = Depends(get_db)):
    """Aggregate statistics for the executive dashboard"""
    # Total orders
    tot_orders = (await db.execute(select(func.count(Order.id)))).scalar() or 0
    pending_orders = (await db.execute(select(func.count(Order.id)).where(Order.status == "pending_review"))).scalar() or 0
    approved_orders = (await db.execute(select(func.count(Order.id)).where(Order.status == "approved"))).scalar() or 0
    vip_orders = (await db.execute(select(func.count(Order.id)).where(Order.is_vip_order == True))).scalar() or 0
    needs_review = pending_orders

    # Customers
    total_customers = (await db.execute(select(func.count(Customer.id)))).scalar() or 0
    vip_customers = (await db.execute(select(func.count(Customer.id)).where(Customer.is_vip == True))).scalar() or 0

    # Incidents
    active_incidents = (await db.execute(
        select(func.count(Incident.id)).where(Incident.status.in_(["detected", "investigating", "mitigating"]))
    )).scalar() or 0

    # Flagsmith fallback values (or live from service)
    surge_active = False
    express_enabled = True
    try:
        from app.services.flagsmith_service import flagsmith_service
        surge_active = flagsmith_service.get_surge_mode()
        express_enabled = flagsmith_service.get_express_delivery_enabled()
    except Exception:
        pass

    return DashboardStats(
        total_orders=tot_orders,
        pending_orders=pending_orders,
        approved_orders=approved_orders,
        vip_orders=vip_orders,
        orders_needing_review=needs_review,
        active_incidents=active_incidents,
        services_healthy=2 if active_incidents == 0 else 1,
        services_total=2,
        surge_mode_active=surge_active,
        express_delivery_enabled=express_enabled,
        total_customers=total_customers,
        vip_customers=vip_customers
    )
