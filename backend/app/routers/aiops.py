"""
AIOps Router
Incident management, Gemini BYOM investigation, mitigation approval & execution.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from sqlalchemy.orm import selectinload
from typing import List

from app.database import get_db
from app.models.incident import Incident, IncidentAction
from app.schemas.incident import (
    IncidentCreate, IncidentResponse, IncidentListResponse,
    IncidentActionResponse, ActionApproval, InvestigationResponse,
    RecoveryVerification, ServiceStatus
)
from app.services.nudgebee import (
    ServiceHealthManager, IncidentWorkflowService
)
from app.services.flagsmith_service import flagsmith_service
from app.services.audit_service import log_action
from app.models.operator import Operator
from app.routers.auth import require_roles, get_current_operator
from datetime import datetime, timezone

router = APIRouter()

@router.get("/services", response_model=List[ServiceStatus])
async def get_services_status():
    """Inspect active service health for utsavops-checkout and newsletter-worker"""
    return ServiceHealthManager.get_all_services()

@router.post("/services/{service_name}/simulate-degradation")
async def simulate_service_degradation(
    service_name: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Demo trigger: Simulates sudden festive traffic burst & checkout degradation
    """
    result = ServiceHealthManager.simulate_degradation(service_name)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])

    # Auto-create incident for SRE cockpit
    incident = await IncidentWorkflowService.create_incident(
        db=db,
        title=f"Festive Traffic Surge — High p99 Latency & Connection Exhaustion on {service_name}",
        service_name=service_name,
        severity="critical",
        evidence={
            "symptom": "p99 latency degraded from 142ms to 4800ms",
            "cpu_utilization": "98%",
            "error_rate": "18.4%",
            "trigger": "Simulated Diwali evening order spike"
        }
    )

    return {
        "message": f"Degradation simulated on {service_name}",
        "incident_id": incident.id,
        "details": result
    }

@router.get("/incidents", response_model=IncidentListResponse)
async def list_incidents(db: AsyncSession = Depends(get_db)):
    """List operational incidents with their action logs"""
    stmt = (
        select(Incident)
        .options(selectinload(Incident.actions))
        .order_by(desc(Incident.created_at))
    )
    incidents = (await db.execute(stmt)).scalars().all()

    formatted = []
    for inc in incidents:
        formatted.append(IncidentResponse(
            id=inc.id,
            title=inc.title,
            service_name=inc.service_name,
            severity=inc.severity,
            status=inc.status,
            detected_at=inc.detected_at,
            resolved_at=inc.resolved_at,
            root_cause=inc.root_cause,
            evidence=inc.evidence or {},
            actions=[
                IncidentActionResponse.model_validate(act) for act in inc.actions
            ],
            created_at=inc.created_at,
            updated_at=inc.updated_at
        ))

    return IncidentListResponse(incidents=formatted, total=len(formatted))

@router.get("/incidents/{incident_id}", response_model=IncidentResponse)
async def get_incident(incident_id: str, db: AsyncSession = Depends(get_db)):
    """Get single incident details with RCA timeline"""
    stmt = (
        select(Incident)
        .where(Incident.id == incident_id)
        .options(selectinload(Incident.actions))
    )
    inc = (await db.execute(stmt)).scalar_one_or_none()
    if not inc:
        raise HTTPException(status_code=404, detail="Incident not found")

    return IncidentResponse(
        id=inc.id,
        title=inc.title,
        service_name=inc.service_name,
        severity=inc.severity,
        status=inc.status,
        detected_at=inc.detected_at,
        resolved_at=inc.resolved_at,
        root_cause=inc.root_cause,
        evidence=inc.evidence or {},
        actions=[IncidentActionResponse.model_validate(act) for act in inc.actions],
        created_at=inc.created_at,
        updated_at=inc.updated_at
    )

@router.post("/incidents/{incident_id}/investigate", response_model=InvestigationResponse)
async def investigate_incident_endpoint(
    incident_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Trigger NudgeBee + Gemini BYOM Root-Cause Analysis"""
    try:
        res = await IncidentWorkflowService.investigate_incident(db, incident_id)
        return res
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.post("/incidents/{incident_id}/actions/{action_id}/approve")
async def approve_incident_action(
    incident_id: str,
    action_id: str,
    body: ActionApproval,
    db: AsyncSession = Depends(get_db),
    operator: Operator = Depends(require_roles("admin", "sre_lead"))
):
    """Human-in-the-loop approval before disruptive mitigation (requires admin/sre_lead)"""
    stmt = select(IncidentAction).where(IncidentAction.id == action_id, IncidentAction.incident_id == incident_id)
    action = (await db.execute(stmt)).scalar_one_or_none()
    if not action:
        raise HTTPException(status_code=404, detail="Action not found")

    action.status = "approved"
    action.approved_by = body.approved_by or operator.name
    action.approved_at = datetime.now(timezone.utc)

    await log_action(
        db,
        entity_type="incident_action",
        action="mitigation_approved",
        entity_id=action.id,
        actor=f"operator:{operator.email}",
        details={"notes": body.notes, "action_type": action.action_type, "approver": body.approved_by}
    )
    await db.commit()
    return {"message": "Mitigation approved", "action_id": action.id, "status": action.status}

@router.post("/incidents/{incident_id}/actions/{action_id}/execute")
async def execute_incident_action(
    incident_id: str,
    action_id: str,
    db: AsyncSession = Depends(get_db),
    operator: Operator = Depends(require_roles("admin", "sre_lead"))
):
    """Execute authorized, allowlisted mitigation (requires admin/sre_lead)"""
    try:
        act = await IncidentWorkflowService.execute_mitigation(db, incident_id, action_id)
        return {
            "message": "Mitigation executed successfully",
            "action_id": act.id,
            "status": act.status,
            "result": act.result
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/incidents/{incident_id}/verify", response_model=RecoveryVerification)
async def verify_recovery_endpoint(
    incident_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Verify service recovery and close incident"""
    try:
        return await IncidentWorkflowService.verify_recovery(db, incident_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.post("/incidents/{incident_id}/restore")
async def restore_changes_endpoint(
    incident_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Restore temporary workload or flag modifications"""
    flagsmith_service.toggle_surge_mode(False)
    ServiceHealthManager.restore_service("utsavops-checkout")
    ServiceHealthManager.restore_service("newsletter-worker")

    await log_action(
        db,
        entity_type="incident",
        action="workload_restored",
        entity_id=incident_id,
        actor="operator",
        details={"surge_mode": False, "cluster_restored": True}
    )
    await db.commit()
    return {"message": "Cluster state and feature flags restored to normal operational parameters"}
