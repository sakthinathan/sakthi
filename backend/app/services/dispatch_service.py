"""
Dispatch Business Logic Service
Handles address geocoding, validation, air quality telemetry, and routing.
"""
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.dispatch import DispatchDetail
from app.models.order import Order
from app.services.google_apis import google_maps_service
from app.services.audit_service import log_action
import structlog

logger = structlog.get_logger()

async def validate_and_geocode_order(
    db: AsyncSession,
    order_id: str,
    address: str
) -> DispatchDetail:
    """Validate delivery address, retrieve geocordinates and AQI metrics"""
    # Fetch or create dispatch detail
    stmt = select(DispatchDetail).where(DispatchDetail.order_id == order_id)
    dispatch = (await db.execute(stmt)).scalar_one_or_none()

    if not dispatch:
        dispatch = DispatchDetail(order_id=order_id, delivery_address=address)
        db.add(dispatch)

    # 1. Validate Address
    val_res = await google_maps_service.validate_address(address)
    dispatch.delivery_address = address
    dispatch.validated_address = val_res.get("validated_address")
    dispatch.validation_status = val_res.get("validation_status", "validated")
    dispatch.latitude = val_res.get("latitude")
    dispatch.longitude = val_res.get("longitude")
    dispatch.geocoding_status = val_res.get("geocoding_status", "OK")

    # 2. Fetch Air Quality Telemetry if coordinates resolved
    if dispatch.latitude and dispatch.longitude:
        aqi_res = await google_maps_service.get_air_quality(float(dispatch.latitude), float(dispatch.longitude))
        dispatch.aqi_value = aqi_res.get("aqi_value")
        dispatch.aqi_category = aqi_res.get("aqi_category")

    await log_action(
        db,
        entity_type="dispatch",
        action="address_validated",
        entity_id=dispatch.id,
        actor="system",
        details={
            "order_id": order_id,
            "status": dispatch.validation_status,
            "lat": float(dispatch.latitude) if dispatch.latitude else None,
            "lng": float(dispatch.longitude) if dispatch.longitude else None,
            "aqi": dispatch.aqi_value
        }
    )

    await db.commit()
    await db.refresh(dispatch)
    return dispatch
