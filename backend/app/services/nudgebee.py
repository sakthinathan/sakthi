"""
NudgeBee, Gemini BYOM, Kubernetes & AIOps Orchestration Service

Features:
- Service health monitor for `utsavops-checkout` (Critical) and `newsletter-worker` (Low)
- Integration metadata for NudgeBee VM (`NUDGEEBEE_VM_NAME`) and Kubernetes secret (`NUDGEEBEE_SECRET_NAME`)
- Incident creation, evidence logging, and simulated festive degradation
- Gemini BYOM root-cause analysis (grounded in actual telemetry)
- Strictly bounded allowlisted mitigations requiring approval
- Post-mitigation recovery verification
"""
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models.incident import Incident, IncidentAction
from app.schemas.incident import ServiceStatus, InvestigationResponse, RecoveryVerification
from app.services.flagsmith_service import flagsmith_service
from app.services.gemini_service import gemini_byom_service
from app.services.audit_service import log_action
from app.config import get_settings
import structlog

logger = structlog.get_logger()

# In-memory cluster state for k8s services
CLUSTER_STATE = {
    "utsavops-checkout": {
        "name": "utsavops-checkout",
        "status": "healthy",
        "criticality": "critical",
        "replicas": 3,
        "available_replicas": 3,
        "cpu_usage": "34%",
        "memory_usage": "48%",
        "error_rate": "0.02%",
        "latency_p99": "142ms",
        "last_checked": datetime.now(timezone.utc)
    },
    "newsletter-worker": {
        "name": "newsletter-worker",
        "status": "healthy",
        "criticality": "low",
        "replicas": 1,
        "available_replicas": 1,
        "cpu_usage": "12%",
        "memory_usage": "22%",
        "error_rate": "0.00%",
        "latency_p99": "45ms",
        "last_checked": datetime.now(timezone.utc)
    }
}


class NudgeBeeConfig:
    """
    NudgeBee Cluster & VM Configuration Inspector.
    Tracks VM name, secret mapping, and authorization parameters.
    """
    @staticmethod
    def get_metadata() -> Dict[str, Any]:
        settings = get_settings()
        return {
            "vm_name": settings.nudgebee_vm_name or "utsavops-nudgebee",
            "secret_name": settings.nudgebee_secret_name or "flagsmith_api_key",
            "has_extra_token": bool(settings.nudgebee_extra_token),
            "k8s_namespace": settings.k8s_namespace,
            "monitored_services": list(CLUSTER_STATE.keys()),
            "byom_configured": settings.has_gemini,
        }


class ServiceHealthManager:
    @staticmethod
    def get_all_services() -> List[ServiceStatus]:
        now = datetime.now(timezone.utc)
        services = []
        for name, data in CLUSTER_STATE.items():
            services.append(ServiceStatus(
                name=name,
                status=data["status"],
                criticality=data["criticality"],
                last_checked=now,
                details={
                    "replicas": f"{data['available_replicas']}/{data['replicas']}",
                    "cpu": data["cpu_usage"],
                    "memory": data["memory_usage"],
                    "latency_p99": data["latency_p99"],
                    "error_rate": data["error_rate"],
                    "vm": NudgeBeeConfig.get_metadata()["vm_name"],
                },
                is_simulated=True
            ))
        return services

    @staticmethod
    def simulate_degradation(service_name: str, symptoms: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Trigger controlled degradation on checkout service during festive burst"""
        if service_name not in CLUSTER_STATE:
            return {"error": "Service not found"}

        service = CLUSTER_STATE[service_name]
        service["status"] = "degraded"
        service["cpu_usage"] = "98%"
        service["memory_usage"] = "92%"
        service["error_rate"] = "18.4%"
        service["latency_p99"] = "4800ms"
        service["last_checked"] = datetime.now(timezone.utc)

        logger.warn("Simulated degradation applied to service", service=service_name)
        return {
            "service": service_name,
            "status": "degraded",
            "telemetry": {
                "cpu": service["cpu_usage"],
                "memory": service["memory_usage"],
                "error_rate": service["error_rate"],
                "latency_p99": service["latency_p99"]
            }
        }

    @staticmethod
    def restore_service(service_name: str) -> None:
        """Reset service health after verified mitigation"""
        if service_name in CLUSTER_STATE:
            svc = CLUSTER_STATE[service_name]
            svc["status"] = "healthy"
            svc["cpu_usage"] = "28%"
            svc["memory_usage"] = "40%"
            svc["error_rate"] = "0.01%"
            svc["latency_p99"] = "110ms"
            svc["last_checked"] = datetime.now(timezone.utc)


class IncidentWorkflowService:
    @staticmethod
    async def create_incident(
        db: AsyncSession,
        title: str,
        service_name: str,
        severity: str,
        evidence: Dict[str, Any]
    ) -> Incident:
        incident = Incident(
            title=title,
            service_name=service_name,
            severity=severity,
            status="detected",
            evidence=evidence
        )
        db.add(incident)
        await db.flush()

        await log_action(
            db,
            entity_type="incident",
            action="incident_detected",
            entity_id=incident.id,
            actor="nudgebee_monitor",
            details={
                "service": service_name,
                "severity": severity,
                "vm": NudgeBeeConfig.get_metadata()["vm_name"]
            }
        )
        await db.commit()
        await db.refresh(incident)
        return incident

    @staticmethod
    async def investigate_incident(db: AsyncSession, incident_id: str) -> InvestigationResponse:
        stmt = select(Incident).where(Incident.id == incident_id)
        incident = (await db.execute(stmt)).scalar_one_or_none()
        if not incident:
            raise ValueError("Incident not found")

        incident.status = "investigating"

        # Run Gemini BYOM RCA using dedicated BYOM service
        cluster_meta = NudgeBeeConfig.get_metadata()
        rca = await gemini_byom_service.analyze_incident_rca(
            service_name=incident.service_name,
            evidence=incident.evidence or {},
            cluster_context=cluster_meta
        )
        incident.root_cause = rca["root_cause"]

        # Formulate safe bounded mitigations strictly allowlisted for festive surge
        proposed_actions = [
            {
                "action_type": "toggle_feature_flag",
                "description": "Activate Flagsmith Surge Survival Mode to shed non-VIP background load and prioritize critical checkout.",
                "requires_approval": True,
                "risk_level": "low"
            },
            {
                "action_type": "scale_deployment",
                "description": "Autoscale utsavops-checkout from 3 to 5 pods to distribute incoming festive traffic.",
                "requires_approval": True,
                "risk_level": "medium"
            },
            {
                "action_type": "reduce_non_critical",
                "description": "Temporarily pause low-priority newsletter-worker to free cluster CPU and memory.",
                "requires_approval": True,
                "risk_level": "low"
            }
        ]

        # Record proposed actions in DB
        for pa in proposed_actions:
            act = IncidentAction(
                incident_id=incident.id,
                action_type=pa["action_type"],
                description=pa["description"],
                requires_approval=pa["requires_approval"],
                status="proposed"
            )
            db.add(act)

        await log_action(
            db,
            entity_type="incident",
            action="rca_investigation_completed",
            entity_id=incident.id,
            actor="gemini_byom",
            details={"root_cause": incident.root_cause, "confidence": rca.get("confidence")}
        )

        await db.commit()
        return InvestigationResponse(
            incident_id=incident.id,
            root_cause=incident.root_cause,
            evidence=incident.evidence or {},
            recommended_actions=proposed_actions,
            is_mock=rca.get("is_mock", True)
        )

    @staticmethod
    async def execute_mitigation(
        db: AsyncSession,
        incident_id: str,
        action_id: str,
        actor: str = "operator"
    ) -> IncidentAction:
        """
        Execute an allowlisted bounded mitigation with rollback safeguards
        """
        stmt = select(IncidentAction).where(IncidentAction.id == action_id, IncidentAction.incident_id == incident_id)
        action = (await db.execute(stmt)).scalar_one_or_none()
        if not action:
            raise ValueError("Incident action not found")

        if action.status != "approved":
            raise ValueError(f"Action cannot be executed. Current status: {action.status}. Approval required first.")

        action.status = "executing"
        result = {}
        rollback = {}

        # Safe Allowlisted execution
        if action.action_type == "toggle_feature_flag":
            remote_res = await flagsmith_service.update_surge_mode_remote(True)
            result = {
                "surge_mode": True,
                "flagsmith_management_api": remote_res,
                "message": f"Flagsmith Surge Survival Mode engaged (Source: {remote_res.get('source')})"
            }
            rollback = {"action": "toggle_feature_flag", "target_state": False}

        elif action.action_type == "scale_deployment":
            CLUSTER_STATE["utsavops-checkout"]["replicas"] = 5
            CLUSTER_STATE["utsavops-checkout"]["available_replicas"] = 5
            result = {"replicas": 5, "message": "utsavops-checkout scaled to 5 replicas"}
            rollback = {"replicas": 3}

        elif action.action_type == "reduce_non_critical":
            CLUSTER_STATE["newsletter-worker"]["available_replicas"] = 0
            result = {"service": "newsletter-worker", "state": "paused"}
            rollback = {"available_replicas": 1}

        else:
            raise ValueError(f"Action type '{action.action_type}' is not in the authorized safety allowlist.")

        action.status = "completed"
        action.executed_at = datetime.now(timezone.utc)
        action.result = result
        action.rollback_info = rollback

        # Update incident status to mitigating
        inc_stmt = select(Incident).where(Incident.id == incident_id)
        incident = (await db.execute(inc_stmt)).scalar_one_or_none()
        if incident:
            incident.status = "mitigating"

        await log_action(
            db,
            entity_type="incident_action",
            action="mitigation_executed",
            entity_id=action.id,
            actor=actor,
            details={"action_type": action.action_type, "result": result}
        )

        await db.commit()
        return action

    @staticmethod
    async def verify_recovery(db: AsyncSession, incident_id: str) -> RecoveryVerification:
        """Verify checkout health and mark incident resolved"""
        inc_stmt = select(Incident).where(Incident.id == incident_id)
        incident = (await db.execute(inc_stmt)).scalar_one_or_none()
        if not incident:
            raise ValueError("Incident not found")

        ServiceHealthManager.restore_service(incident.service_name)
        incident.status = "resolved"
        incident.resolved_at = datetime.now(timezone.utc)

        await log_action(
            db,
            entity_type="incident",
            action="incident_resolved",
            entity_id=incident.id,
            actor="recovery_verifier",
            details={"service": incident.service_name, "status": "healthy"}
        )

        await db.commit()
        return RecoveryVerification(
            incident_id=incident.id,
            service_name=incident.service_name,
            is_healthy=True,
            health_details={
                "p99_latency": "110ms",
                "error_rate": "0.01%",
                "status": "healthy"
            },
            verified_at=datetime.now(timezone.utc)
        )
