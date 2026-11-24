"""
Feature Flags Router
Live inspection, evaluation, and surge survival mode controls.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Dict, Any

from app.database import get_db
from app.models.customer import Customer
from app.models.audit import FeatureFlagSnapshot
from app.schemas.common import FlagEvaluationRequest, SurgeModeRequest
from app.services.flagsmith_service import flagsmith_service
from app.services.audit_service import log_action

router = APIRouter()

@router.get("")
async def get_flags():
    """Get all feature flags and their current evaluated states"""
    return {
        "flags": flagsmith_service.get_all_flags(),
        "surge_survival_mode": flagsmith_service.get_surge_mode()
    }

@router.get("/business-rules")
async def get_business_rules():
    """Inspect active business rules and surge enforcement status"""
    surge = flagsmith_service.get_surge_mode()
    return {
        "surge_mode_active": surge,
        "rules": {
            "vip_express_delivery": True,
            "non_vip_express_delivery": not surge,
            "festive_bundle_price": flagsmith_service.get_festive_bundle_price(),
            "active_sarvam_routing": flagsmith_service.get_flag_value("sarvam_ai_routing")
        },
        "description": "During surge conditions, VIP customers retain express delivery while non-VIP orders are routed to standard dispatch."
    }

@router.post("/evaluate")
async def evaluate_for_customer(
    req: FlagEvaluationRequest,
    db: AsyncSession = Depends(get_db)
):
    """Evaluate flags for specific customer identity (taking VIP traits into account)"""
    is_vip = False
    traits = {}
    if req.customer_id:
        stmt = select(Customer).where(Customer.id == req.customer_id)
        cust = (await db.execute(stmt)).scalar_one_or_none()
        if cust:
            is_vip = cust.is_vip
            traits = {
                "is_vip": cust.is_vip,
                "tier": cust.tier,
                "total_orders": cust.total_orders,
                "total_spent": float(cust.total_spent or 0)
            }

    flags = flagsmith_service.get_all_flags(identity=req.customer_id, traits=traits)
    vip_eval = flagsmith_service.evaluate_vip_express_delivery(req.customer_id, is_vip)
    allow_express = vip_eval["allowed"]

    # Save evaluation snapshot
    snapshot = FeatureFlagSnapshot(
        flag_name="surge_survival_mode",
        flag_value={"express_allowed": allow_express, "is_vip": is_vip, "vip_evaluation": vip_eval},
        evaluated_for=req.customer_id,
        source=vip_eval.get("source", "flagsmith")
    )
    db.add(snapshot)
    await db.commit()

    return {
        "customer_id": req.customer_id,
        "is_vip": is_vip,
        "express_delivery_allowed": allow_express,
        "vip_evaluation": vip_eval,
        "flags": flags
    }

@router.post("/surge-mode")
async def toggle_surge_mode(
    req: SurgeModeRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Operator surge survival mode trigger.
    Protects checkout during festive surges.
    """
    res = await flagsmith_service.update_surge_mode_remote(req.enabled)

    await log_action(
        db,
        entity_type="feature_flag",
        action="surge_mode_toggled",
        actor="operator",
        details={"enabled": req.enabled, "management_api": res, "reason": req.reason or "Manual operational adjustment"}
    )
    await db.commit()

    return {
        "surge_survival_mode": req.enabled,
        "management_api": res,
        "message": f"Surge survival mode {'ENABLED - Express delivery restricted to VIPs only' if req.enabled else 'DISABLED - Normal delivery limits restored'}"
    }
