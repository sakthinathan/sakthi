"""
Orders Router
Endpoints for handwritten/voice intake, review, approval, rejection, and listing.
"""
import os
import uuid
import aiofiles
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, Query, Header, Response
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from sqlalchemy.orm import selectinload
from typing import Optional, List

from app.database import get_db
from app.config import get_settings
from app.models.order import Order, OrderItem, OrderInput
from app.models.customer import Customer
from app.schemas.order import (
    OrderIntakeResponse, OrderResponse, OrderListResponse,
    OrderReviewUpdate, OrderItemResponse, OrderInputResponse
)
from app.services.sarvam import sarvam_service
from app.services.order_service import (
    create_order_from_extraction, get_order_with_relations, apply_vip_rules
)
from app.services.audit_service import log_action
import structlog

logger = structlog.get_logger()
router = APIRouter()
settings = get_settings()

@router.post("/intake/image", response_model=OrderIntakeResponse)
async def intake_handwritten_image(
    file: UploadFile = File(...),
    idempotency_key: Optional[str] = Header(None, alias="X-Idempotency-Key"),
    db: AsyncSession = Depends(get_db)
):
    """
    Intake handwritten festive order chits via Sarvam Document AI
    """
    if file.content_type not in ["image/jpeg", "image/png", "image/webp", "image/jpg"]:
        raise HTTPException(status_code=400, detail="Only JPG, PNG and WebP images supported")

    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Image size exceeds 10MB limit")

    filename = f"{uuid.uuid4().hex}_{file.filename}"
    file_path = os.path.join(settings.upload_dir, filename)
    async with aiofiles.open(file_path, "wb") as f:
        await f.write(content)

    extraction = await sarvam_service.extract_from_image(content, file.filename or "chit.jpg")
    ext_data = extraction.get("data", {})
    confidence = ext_data.get("confidence", 0.85)

    order_input = OrderInput(
        input_type="image",
        file_path=file_path,
        original_text=ext_data.get("raw_text"),
        original_language=ext_data.get("original_language", "en"),
        sarvam_response=extraction,
        extraction_confidence=confidence,
        processing_status="completed" if extraction.get("success", True) else "failed"
    )
    db.add(order_input)
    await db.flush()

    order = await create_order_from_extraction(db, ext_data, order_input.id, idempotency_key)
    await db.commit()

    provider_meta = {
        "provider": extraction.get("provider", "sarvam_document_ai"),
        "status": extraction.get("status", "live" if not extraction.get("is_mock") else "fallback"),
        "is_mock": extraction.get("is_mock", False),
        "failure_reason": extraction.get("failure_reason")
    }

    return OrderIntakeResponse(
        order_id=order.id,
        order_number=order.order_number,
        input_id=order_input.id,
        status=order.status,
        extracted_data=ext_data,
        confidence=confidence,
        message="Handwritten order chit successfully analyzed via Sarvam Document AI",
        is_mock=extraction.get("is_mock", False),
        provider_metadata=provider_meta
    )

@router.post("/intake/audio", response_model=OrderIntakeResponse)
async def intake_voice_order(
    file: UploadFile = File(...),
    language: str = Form("hi-IN"),
    idempotency_key: Optional[str] = Header(None, alias="X-Idempotency-Key"),
    db: AsyncSession = Depends(get_db)
):
    """
    Intake regional language voice notes via Sarvam Saaras v4
    """
    content = await file.read()
    if len(content) > 20 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Audio file exceeds 20MB limit")

    filename = f"{uuid.uuid4().hex}_{file.filename or 'voice.wav'}"
    file_path = os.path.join(settings.upload_dir, filename)
    async with aiofiles.open(file_path, "wb") as f:
        await f.write(content)

    transcription = await sarvam_service.transcribe_audio(content, file.filename or "voice.wav", language)
    ext_data = transcription.get("data", {})
    confidence = ext_data.get("confidence", 0.88)

    order_input = OrderInput(
        input_type="audio",
        file_path=file_path,
        original_text=transcription.get("transcript"),
        original_language=language,
        sarvam_response=transcription,
        extraction_confidence=confidence,
        processing_status="completed" if transcription.get("success", True) else "failed"
    )
    db.add(order_input)
    await db.flush()

    order = await create_order_from_extraction(db, ext_data, order_input.id, idempotency_key)
    await db.commit()

    provider_meta = {
        "provider": transcription.get("provider", "sarvam_saaras_stt"),
        "status": transcription.get("status", "live" if not transcription.get("is_mock") else "fallback"),
        "is_mock": transcription.get("is_mock", False),
        "failure_reason": transcription.get("failure_reason")
    }

    return OrderIntakeResponse(
        order_id=order.id,
        order_number=order.order_number,
        input_id=order_input.id,
        status=order.status,
        extracted_data=ext_data,
        confidence=confidence,
        message=f"Regional voice note transcribed and normalized via Sarvam Saaras v4 ({language})",
        is_mock=transcription.get("is_mock", False),
        provider_metadata=provider_meta
    )

@router.get("", response_model=OrderListResponse)
async def list_orders(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    search: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """List orders with pagination, status filter and search"""
    query = select(Order).options(
        selectinload(Order.customer),
        selectinload(Order.items),
        selectinload(Order.order_input)
    ).order_by(desc(Order.created_at))

    if status:
        query = query.where(Order.status == status)

    if search:
        query = query.join(Order.customer).where(
            (Order.order_number.ilike(f"%{search}%")) |
            (Customer.name.ilike(f"%{search}%"))
        )

    # Count
    count_stmt = select(func.count(Order.id))
    if status:
        count_stmt = count_stmt.where(Order.status == status)
    total = (await db.execute(count_stmt)).scalar() or 0

    offset = (page - 1) * per_page
    query = query.offset(offset).limit(per_page)
    results = (await db.execute(query)).scalars().all()

    formatted_orders = []
    for o in results:
        formatted_orders.append(OrderResponse(
            id=o.id,
            order_number=o.order_number,
            customer_id=o.customer_id,
            order_input_id=o.order_input_id,
            status=o.status,
            priority=o.priority,
            is_express=o.is_express,
            is_vip_order=o.is_vip_order,
            special_instructions=o.special_instructions,
            subtotal=float(o.subtotal or 0),
            total=float(o.total or 0),
            review_notes=o.review_notes,
            customer_name=o.customer.name if o.customer else "Guest",
            items=[
                OrderItemResponse(
                    id=it.id,
                    product_name=it.product_name,
                    product_name_original=it.product_name_original,
                    quantity=it.quantity,
                    unit_price=float(it.unit_price or 0),
                    total_price=float(it.total_price or 0),
                    confidence=float(it.confidence or 1.0)
                ) for it in o.items
            ],
            order_input=OrderInputResponse(
                id=o.order_input.id,
                input_type=o.order_input.input_type,
                file_path=o.order_input.file_path,
                original_text=o.order_input.original_text,
                original_language=o.order_input.original_language,
                extraction_confidence=float(o.order_input.extraction_confidence or 0.9),
                processing_status=o.order_input.processing_status,
                error_message=o.order_input.error_message,
                created_at=o.order_input.created_at
            ) if o.order_input else None,
            created_at=o.created_at,
            updated_at=o.updated_at
        ))

    return OrderListResponse(
        orders=formatted_orders,
        total=total,
        page=page,
        per_page=per_page
    )

@router.get("/{order_id}", response_model=OrderResponse)
async def get_order(order_id: str, db: AsyncSession = Depends(get_db)):
    """Fetch order details with full relations"""
    order = await get_order_with_relations(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    return OrderResponse(
        id=order.id,
        order_number=order.order_number,
        customer_id=order.customer_id,
        order_input_id=order.order_input_id,
        status=order.status,
        priority=order.priority,
        is_express=order.is_express,
        is_vip_order=order.is_vip_order,
        special_instructions=order.special_instructions,
        subtotal=float(order.subtotal or 0),
        total=float(order.total or 0),
        review_notes=order.review_notes,
        customer_name=order.customer.name if order.customer else "Guest",
        items=[
            OrderItemResponse(
                id=it.id,
                product_name=it.product_name,
                product_name_original=it.product_name_original,
                quantity=it.quantity,
                unit_price=float(it.unit_price or 0),
                total_price=float(it.total_price or 0),
                confidence=float(it.confidence or 1.0)
            ) for it in order.items
        ],
        order_input=OrderInputResponse(
            id=order.order_input.id,
            input_type=order.order_input.input_type,
            file_path=order.order_input.file_path,
            original_text=order.order_input.original_text,
            original_language=order.order_input.original_language,
            extraction_confidence=float(order.order_input.extraction_confidence or 0.9),
            processing_status=order.order_input.processing_status,
            error_message=order.order_input.error_message,
            created_at=order.order_input.created_at
        ) if order.order_input else None,
        created_at=order.created_at,
        updated_at=order.updated_at
    )

@router.put("/{order_id}/review")
async def review_order(
    order_id: str,
    update_data: OrderReviewUpdate,
    db: AsyncSession = Depends(get_db)
):
    """
    Allow human-in-the-loop correction before order confirmation
    """
    order = await get_order_with_relations(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    if update_data.customer_name and order.customer:
        order.customer.name = update_data.customer_name
    if update_data.customer_phone and order.customer:
        order.customer.phone = update_data.customer_phone
    if update_data.special_instructions is not None:
        order.special_instructions = update_data.special_instructions
    if update_data.review_notes is not None:
        order.review_notes = update_data.review_notes

    # Update delivery address in dispatch if provided
    if update_data.delivery_address and order.dispatch:
        order.dispatch.delivery_address = update_data.delivery_address
        order.dispatch.validation_status = "pending"

    # Update items if provided
    if update_data.items:
        # Recompute totals
        total_price = 0.0
        # For simplicity, if count matches, update directly
        for idx, item_up in enumerate(update_data.items):
            if idx < len(order.items):
                target_item = order.items[idx]
                if item_up.product_name:
                    target_item.product_name = item_up.product_name
                if item_up.quantity is not None:
                    target_item.quantity = item_up.quantity
                if item_up.unit_price is not None:
                    target_item.unit_price = item_up.unit_price
                target_item.total_price = target_item.quantity * float(target_item.unit_price or 0)
                total_price += target_item.total_price
        order.subtotal = total_price
        order.total = total_price

    await log_action(
        db,
        entity_type="order",
        action="human_review_edited",
        entity_id=order.id,
        actor="operator",
        details={"updated_fields": list(update_data.model_dump(exclude_unset=True).keys())}
    )
    await db.commit()
    return {"message": "Order review saved successfully", "order_id": order.id}

@router.post("/{order_id}/approve")
async def approve_order(order_id: str, db: AsyncSession = Depends(get_db)):
    """Approve order and apply VIP / Express delivery rules"""
    order = await get_order_with_relations(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    order.status = "approved"
    await apply_vip_rules(db, order)

    # Update customer stats
    if order.customer:
        order.customer.total_orders += 1
        order.customer.total_spent = float(order.customer.total_spent or 0) + float(order.total or 0)

    await log_action(
        db,
        entity_type="order",
        action="order_approved",
        entity_id=order.id,
        actor="operator",
        details={"order_number": order.order_number, "is_vip": order.is_vip_order}
    )
    await db.commit()
    return {"message": f"Order {order.order_number} approved", "status": order.status}

@router.post("/{order_id}/reject")
async def reject_order(
    order_id: str,
    reason: str = Query("Unable to fulfill", description="Reason for rejection"),
    db: AsyncSession = Depends(get_db)
):
    """Reject order with reason"""
    order = await get_order_with_relations(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    order.status = "rejected"
    order.review_notes = reason

    await log_action(
        db,
        entity_type="order",
        action="order_rejected",
        entity_id=order.id,
        actor="operator",
        details={"reason": reason}
    )
    await db.commit()
    return {"message": f"Order {order.order_number} rejected", "status": order.status}

@router.post("/{order_id}/voice-confirmation")
async def voice_confirmation(
    order_id: str,
    language: str = Query("hi-IN"),
    db: AsyncSession = Depends(get_db)
):
    """Generate audio confirmation using Sarvam Bulbul v3"""
    order = await get_order_with_relations(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    customer_name = order.customer.name if order.customer else "ग्राहक"
    text_message = f"नमस्ते {customer_name}! आपका उत्सवऑप्स ऑर्डर {order.order_number} स्वीकार कर लिया गया है। कुल राशि {int(order.total)} रुपये है।"

    audio_bytes = await sarvam_service.generate_voice_confirmation(text_message, language)
    return Response(content=audio_bytes, media_type="audio/wav")
