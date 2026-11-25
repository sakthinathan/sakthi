"""
Demo Seed Data Script for UtsavOps
Pre-populates realistic Indian festive commerce records:
- Festive Sweet & Gift Shoppers (VIP and Regular)
- Sample handwritten chits and multilingual voice orders
- Audit logs and feature flag snapshots
"""
import asyncio
from datetime import datetime, timezone, timedelta
from app.database import AsyncSessionLocal, init_db
from app.models.customer import Customer
from app.models.order import Order, OrderItem, OrderInput
from app.models.dispatch import DispatchDetail
from app.models.audit import AuditLog
from app.models.operator import Operator
from app.routers.auth import seed_initial_admin
from app.utils.security import hash_password
from sqlalchemy import select
import structlog

logger = structlog.get_logger()

async def seed_demo_data():
    await init_db()
    async with AsyncSessionLocal() as db:
        logger.info("Seeding UtsavOps festive demo data...")

        # 0. Seed Default Operator using environment-driven configuration
        await seed_initial_admin(db)

        # 1. Customers (idempotent lookup by phone)
        customers_data = [
            {
                "name": "Dr. Meenakshi Sundaram",
                "phone": "+91 98410 54321",
                "email": "meenakshi.s@gmail.com",
                "tier": "vip",
                "is_vip": True,
                "total_orders": 8,
                "total_spent": 18450.0
            },
            {
                "name": "Smt. Rajeshwari Iyer",
                "phone": "+91 98401 23456",
                "email": "rajeshwari.iyer@outlook.com",
                "tier": "vip",
                "is_vip": True,
                "total_orders": 12,
                "total_spent": 32800.0
            },
            {
                "name": "Shri Harish Kapoor",
                "phone": "+91 98102 77889",
                "email": "hkapoor.delhi@gmail.com",
                "tier": "regular",
                "is_vip": False,
                "total_orders": 2,
                "total_spent": 2400.0
            },
            {
                "name": "Vikram Sethi",
                "phone": "+91 97422 11002",
                "email": "vikram.sethi@blrmail.com",
                "tier": "regular",
                "is_vip": False,
                "total_orders": 1,
                "total_spent": 1200.0
            }
        ]

        created_customers = []
        for cd in customers_data:
            c_check = await db.execute(select(Customer).where(Customer.phone == cd["phone"]))
            existing_cust = c_check.scalars().first()
            if existing_cust:
                created_customers.append(existing_cust)
            else:
                cust = Customer(**cd)
                db.add(cust)
                created_customers.append(cust)

        await db.flush()

        # 2. Orders with items & dispatch
        # Order 1: Pending Review (Tamil handwritten chit)
        ord1_check = await db.execute(select(Order).where(Order.order_number == "UTS-221126-1001"))
        ord1 = ord1_check.scalars().first()
        ord1_is_new = False
        if not ord1:
            ord1_is_new = True
            inp1 = OrderInput(
                input_type="image",
                original_text="தீபாவளி ஆர்டர்: ராஜேஸ்வரி ஐயர். காஜு கத்லி 500g 2 பாக்கெட், மோதிச்சூர் லட்டு 1kg, டிரை ஃப்ரூட்ஸ் ஹாம்பர் 1. மல்லேஸ்வரம்.",
                original_language="ta-IN",
                extraction_confidence=0.94,
                processing_status="completed"
            )
            db.add(inp1)
            await db.flush()

            ord1 = Order(
                order_number="UTS-221126-1001",
                customer_id=created_customers[1].id,
                order_input_id=inp1.id,
                status="pending_review",
                priority="high",
                is_express=True,
                is_vip_order=True,
                special_instructions="Diwali gift gold wrap requested. Deliver before 6 PM.",
                subtotal=2770.0,
                total=2770.0
            )
            db.add(ord1)
            await db.flush()

            db.add_all([
                OrderItem(order_id=ord1.id, product_name="Special Kaju Katli (500g)", quantity=2, unit_price=550.0, total_price=1100.0, confidence=0.96),
                OrderItem(order_id=ord1.id, product_name="Motichoor Laddu Box (1kg)", quantity=1, unit_price=420.0, total_price=420.0, confidence=0.92),
                OrderItem(order_id=ord1.id, product_name="Dry Fruit Gift Hamper", quantity=1, unit_price=1250.0, total_price=1250.0, confidence=0.95),
            ])

            db.add(DispatchDetail(
                order_id=ord1.id,
                delivery_address="Flat 4B, Sri Krishna Apts, 12th Cross, Malleshwaram, Bengaluru 560003",
                validated_address="12th Cross Rd, Malleshwaram, Bengaluru, Karnataka 560003, India",
                validation_status="validated",
                latitude=13.0033,
                longitude=77.5694,
                aqi_value=92,
                aqi_category="Moderate",
                dispatch_status="pending"
            ))

        # Order 2: Approved Order (Hindi voice note)
        ord2_check = await db.execute(select(Order).where(Order.order_number == "UTS-221126-1002"))
        ord2 = ord2_check.scalars().first()
        ord2_is_new = False
        if not ord2:
            ord2_is_new = True
            inp2 = OrderInput(
                input_type="audio",
                original_text="नमस्ते, मुझे दो डिब्बे काजू कतली और एक किलो गुलाब जामुन चाहिए। पता है शांति कुंज गुड़गांव।",
                original_language="hi-IN",
                extraction_confidence=0.91,
                processing_status="completed"
            )
            db.add(inp2)
            await db.flush()

            ord2 = Order(
                order_number="UTS-221126-1002",
                customer_id=created_customers[2].id,
                order_input_id=inp2.id,
                status="approved",
                priority="normal",
                is_express=False,
                is_vip_order=False,
                special_instructions="Leave with security guard if door unanswered",
                subtotal=1480.0,
                total=1480.0
            )
            db.add(ord2)
            await db.flush()

            db.add_all([
                OrderItem(order_id=ord2.id, product_name="Special Kaju Katli (500g)", quantity=2, unit_price=550.0, total_price=1100.0, confidence=0.92),
                OrderItem(order_id=ord2.id, product_name="Gulab Jamun (1kg)", quantity=1, unit_price=380.0, total_price=380.0, confidence=0.89),
            ])

            db.add(DispatchDetail(
                order_id=ord2.id,
                delivery_address="B-104, Shanti Kunj, Sector 14, Gurgaon, Haryana 122001",
                validated_address="Sector 14, Gurugram, Haryana 122001, India",
                validation_status="validated",
                latitude=28.4744,
                longitude=77.0519,
                aqi_value=145,
                aqi_category="Unhealthy for Sensitive Groups",
                dispatch_status="assigned"
            ))

        # Audit logs
        if ord1_is_new or ord2_is_new:
            db.add_all([
                AuditLog(entity_type="order", entity_id=ord1.id, action="created_from_sarvam_doc_ai", actor="sarvam_service", details={"confidence": 0.94}),
                AuditLog(entity_type="order", entity_id=ord2.id, action="created_from_saaras_voice", actor="sarvam_service", details={"confidence": 0.91}),
                AuditLog(entity_type="order", entity_id=ord2.id, action="order_approved", actor="store_manager", details={"order_number": ord2.order_number}),
                AuditLog(entity_type="system", action="system_initialized", actor="orchestrator", details={"app": "UtsavOps 1.0"})
            ])

        await db.commit()
        logger.info("Demo festive data seeded successfully!")

if __name__ == "__main__":
    asyncio.run(seed_demo_data())
