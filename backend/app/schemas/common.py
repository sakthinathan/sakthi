"""Common schemas shared across modules."""
from pydantic import BaseModel, Field
from typing import Optional, Any, Dict
from datetime import datetime


class HealthResponse(BaseModel):
    status: str = "healthy"
    version: str = "1.0.0"
    database: str = "connected"
    timestamp: datetime
    services: Dict[str, str] = {}


class DashboardStats(BaseModel):
    total_orders: int = 0
    pending_orders: int = 0
    approved_orders: int = 0
    vip_orders: int = 0
    orders_needing_review: int = 0
    active_incidents: int = 0
    services_healthy: int = 0
    services_total: int = 0
    surge_mode_active: bool = False
    express_delivery_enabled: bool = True
    total_customers: int = 0
    vip_customers: int = 0


class APIError(BaseModel):
    error: str
    detail: Optional[str] = None
    code: Optional[str] = None


class PaginationParams(BaseModel):
    page: int = Field(1, ge=1)
    per_page: int = Field(20, ge=1, le=100)

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.per_page


class AuditLogResponse(BaseModel):
    id: str
    entity_type: str
    entity_id: Optional[str]
    action: str
    actor: str
    details: Dict[str, Any] = {}
    created_at: datetime

    model_config = {"from_attributes": True}


class FlagEvaluationRequest(BaseModel):
    customer_id: Optional[str] = None
    flags: Optional[list[str]] = None


class FlagValueResponse(BaseModel):
    flag_name: str
    enabled: bool
    value: Optional[Any] = None
    source: str = "flagsmith"  # flagsmith, fallback, mock


class SurgeModeRequest(BaseModel):
    enabled: bool
    reason: Optional[str] = None
