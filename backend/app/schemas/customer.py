"""Customer request/response schemas."""
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime


class CustomerCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    phone: Optional[str] = Field(None, max_length=20)
    email: Optional[str] = Field(None, max_length=255)
    tier: str = Field("regular", pattern="^(regular|vip|premium)$")
    is_vip: bool = False


class CustomerUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    phone: Optional[str] = Field(None, max_length=20)
    email: Optional[str] = Field(None, max_length=255)
    tier: Optional[str] = Field(None, pattern="^(regular|vip|premium)$")
    is_vip: Optional[bool] = None


class CustomerResponse(BaseModel):
    id: str
    name: str
    phone: Optional[str]
    email: Optional[str]
    tier: str
    total_orders: int
    total_spent: float
    is_vip: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CustomerListResponse(BaseModel):
    customers: list[CustomerResponse]
    total: int
    page: int
    per_page: int
