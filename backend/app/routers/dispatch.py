"""
Dispatch Router
Delivery route optimization, address validation, geocoding and AQI planning.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.dispatch import DispatchDetail
from app.schemas.dispatch import (
    AddressValidationRequest, AddressValidationResponse,
    AirQualityResponse, DispatchResponse
)
from app.services.dispatch_service import validate_and_geocode_order
from app.services.google_apis import google_maps_service

router = APIRouter()

@router.get("/{order_id}", response_model=DispatchResponse)
async def get_dispatch_details(order_id: str, db: AsyncSession = Depends(get_db)):
    """Fetch dispatch and routing information for order"""
    stmt = select(DispatchDetail).where(DispatchDetail.order_id == order_id)
    dispatch = (await db.execute(stmt)).scalar_one_or_none()
    if not dispatch:
        raise HTTPException(status_code=404, detail="Dispatch details not found for this order")

    return DispatchResponse.model_validate(dispatch)

@router.post("/{order_id}/validate-address", response_model=DispatchResponse)
async def validate_address_endpoint(
    order_id: str,
    req: AddressValidationRequest,
    db: AsyncSession = Depends(get_db)
):
    """Validate address via Google Address Validation API and update coordinates"""
    dispatch = await validate_and_geocode_order(db, order_id, req.address)
    val_res = getattr(dispatch, "_val_res", {})
    resp = DispatchResponse.model_validate(dispatch)
    resp.provider_metadata = {
        "provider": val_res.get("provider", "google_address_validation"),
        "status": val_res.get("status", "live" if not val_res.get("is_mock") else "fallback"),
        "is_mock": val_res.get("is_mock", False),
        "error": val_res.get("error")
    }
    return resp

@router.get("/{order_id}/air-quality", response_model=AirQualityResponse)
async def get_air_quality_endpoint(order_id: str, db: AsyncSession = Depends(get_db)):
    """Contextual Air Quality Telemetry for festive delivery routing"""
    stmt = select(DispatchDetail).where(DispatchDetail.order_id == order_id)
    dispatch = (await db.execute(stmt)).scalar_one_or_none()
    if not dispatch or not dispatch.latitude or not dispatch.longitude:
        raise HTTPException(status_code=400, detail="Delivery coordinates not yet resolved. Validate address first.")

    res = await google_maps_service.get_air_quality(float(dispatch.latitude), float(dispatch.longitude))

    # Persist updated telemetry to dispatch record
    if res.get("aqi_value") is not None:
        dispatch.aqi_value = res.get("aqi_value")
        dispatch.aqi_category = res.get("aqi_category")
        await db.commit()

    return AirQualityResponse(
        aqi_value=res.get("aqi_value"),
        aqi_category=res.get("aqi_category"),
        dominant_pollutant=res.get("dominant_pollutant"),
        health_recommendations=res.get("health_recommendations"),
        location=res.get("location"),
        is_mock=res.get("is_mock", True),
        disclaimer=res.get("disclaimer"),
        updated_at=res.get("updated_at"),
        provider_metadata={
            "provider": res.get("provider", "google_air_quality"),
            "status": res.get("status", "live" if not res.get("is_mock") else "fallback"),
            "is_mock": res.get("is_mock", True),
            "error": res.get("error")
        }
    )
