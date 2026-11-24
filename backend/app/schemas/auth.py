"""Pydantic schemas for authentication and operator profile."""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field


class OperatorLoginRequest(BaseModel):
    email: str = Field(..., description="Operator email address")
    password: str = Field(..., min_length=6, description="Operator password")


class OperatorResponse(BaseModel):
    id: str
    email: str
    name: str
    role: str
    is_active: bool
    created_at: Optional[datetime] = None
    last_login: Optional[datetime] = None

    model_config = {"from_attributes": True}


class OperatorLoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    operator: OperatorResponse
    message: str = "Authentication successful"


class OperatorMessageResponse(BaseModel):
    message: str
