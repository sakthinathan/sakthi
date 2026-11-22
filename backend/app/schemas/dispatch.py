"""Dispatch and address validation schemas."""
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime


class AddressValidationRequest(BaseModel):
    address: str = Field(..., min_length=1)


class AddressValidationResponse(BaseModel):
    validated_address: Optional[str]
    validation_status: str  # validated, invalid, partial_match
    latitude: Optional[float]
    longitude: Optional[float]
    geocoding_status: Optional[str]
    validation_details: Dict[str, Any] = {}
    is_mock: bool = False


class AirQualityResponse(BaseModel):
    aqi_value: Optional[int]
    aqi_category: Optional[str]
    dominant_pollutant: Optional[str]
    health_recommendations: Optional[str]
    location: Optional[str]
    is_mock: bool = False
    disclaimer: str = "Air quality data is provided as contextual delivery-planning information only. It does not constitute proof that a delivery is safe or unsafe."


class DispatchResponse(BaseModel):
    id: str
    order_id: str
    delivery_address: str
    validated_address: Optional[str]
    validation_status: str
    latitude: Optional[float]
    longitude: Optional[float]
    geocoding_status: Optional[str]
    aqi_value: Optional[int]
    aqi_category: Optional[str]
    dispatch_status: str
    estimated_delivery: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
