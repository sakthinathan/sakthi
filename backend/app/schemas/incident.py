"""Incident and AIOps schemas."""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


class IncidentCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    service_name: str = Field(..., min_length=1, max_length=100)
    severity: str = Field(..., pattern="^(critical|high|medium|low)$")
    evidence: Dict[str, Any] = {}


class IncidentActionResponse(BaseModel):
    id: str
    incident_id: str
    action_type: str
    description: str
    status: str
    requires_approval: bool
    approved_by: Optional[str]
    approved_at: Optional[datetime]
    executed_at: Optional[datetime]
    result: Optional[Dict[str, Any]]
    rollback_info: Optional[Dict[str, Any]]
    created_at: datetime

    model_config = {"from_attributes": True}


class IncidentResponse(BaseModel):
    id: str
    title: str
    service_name: str
    severity: str
    status: str
    detected_at: datetime
    resolved_at: Optional[datetime]
    root_cause: Optional[str]
    evidence: Dict[str, Any] = {}
    actions: List[IncidentActionResponse] = []
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class IncidentListResponse(BaseModel):
    incidents: list[IncidentResponse]
    total: int


class ActionApproval(BaseModel):
    approved_by: str = Field(..., min_length=1)
    notes: Optional[str] = None


class InvestigationResponse(BaseModel):
    incident_id: str
    root_cause: Optional[str]
    evidence: Dict[str, Any] = {}
    recommended_actions: List[Dict[str, Any]] = []
    is_mock: bool = False


class RecoveryVerification(BaseModel):
    incident_id: str
    service_name: str
    is_healthy: bool
    health_details: Dict[str, Any] = {}
    verified_at: datetime


class ServiceStatus(BaseModel):
    name: str
    status: str  # healthy, degraded, down, unknown
    criticality: str  # critical, high, medium, low
    last_checked: Optional[datetime] = None
    details: Dict[str, Any] = {}
    is_simulated: bool = True
