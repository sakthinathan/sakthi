"""Order request/response schemas."""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


class OrderInputResponse(BaseModel):
    id: str
    input_type: str
    file_path: Optional[str]
    original_text: Optional[str]
    original_language: Optional[str]
    extraction_confidence: Optional[float]
    processing_status: str
    error_message: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class OrderItemResponse(BaseModel):
    id: str
    product_name: str
    product_name_original: Optional[str]
    quantity: int
    unit_price: Optional[float]
    total_price: Optional[float]
    confidence: Optional[float]

    model_config = {"from_attributes": True}


class OrderItemUpdate(BaseModel):
    product_name: Optional[str] = None
    quantity: Optional[int] = Field(None, ge=1)
    unit_price: Optional[float] = Field(None, ge=0)


class OrderResponse(BaseModel):
    id: str
    order_number: str
    customer_id: Optional[str]
    order_input_id: Optional[str]
    status: str
    priority: str
    is_express: bool
    is_vip_order: bool
    special_instructions: Optional[str]
    subtotal: float
    total: float
    review_notes: Optional[str]
    items: List[OrderItemResponse] = []
    order_input: Optional[OrderInputResponse] = None
    customer_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class OrderListResponse(BaseModel):
    orders: list[OrderResponse]
    total: int
    page: int
    per_page: int


class OrderIntakeResponse(BaseModel):
    order_id: str
    order_number: str
    input_id: str
    status: str
    extracted_data: Dict[str, Any] = {}
    confidence: Optional[float]
    message: str
    is_mock: bool = False
    provider_metadata: Optional[Dict[str, Any]] = None


class OrderReviewUpdate(BaseModel):
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
    delivery_address: Optional[str] = None
    special_instructions: Optional[str] = None
    items: Optional[List[OrderItemUpdate]] = None
    review_notes: Optional[str] = None
