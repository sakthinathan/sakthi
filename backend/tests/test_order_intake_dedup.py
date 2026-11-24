import pytest
import io
from app.models.customer import Customer
from app.services.order_service import create_order_from_extraction
from sqlalchemy import select

@pytest.mark.asyncio
async def test_order_intake_duplicate_customer_prevention(test_session):
    # Seed an existing customer with a specific phone number
    c1 = Customer(
        name="Smt. Rajeshwari Iyer",
        phone="+91 98401 23456",
        tier="regular",
        is_vip=False
    )
    test_session.add(c1)
    await test_session.commit()

    # Extract 1st order with same phone
    extracted_1 = {
        "customer_name": "Smt. Rajeshwari Iyer",
        "phone": "+91 98401 23456",
        "delivery_address": "Mylapore, Chennai",
        "items": [{"product_name": "Mysore Pak 1kg", "quantity": 2, "unit_price": 450.0}]
    }

    order_1 = await create_order_from_extraction(test_session, extracted_1, order_input_id="in-1")
    await test_session.commit()
    assert order_1.customer_id == c1.id

    # Extract 2nd order with same phone
    extracted_2 = {
        "customer_name": "Rajeshwari Iyer",
        "phone": "+91 98401 23456",
        "delivery_address": "Mylapore, Chennai",
        "items": [{"product_name": "Kaju Katli 500g", "quantity": 1, "unit_price": 500.0}]
    }

    order_2 = await create_order_from_extraction(test_session, extracted_2, order_input_id="in-2")
    await test_session.commit()
    assert order_2.customer_id == c1.id

    # Verify only 1 customer exists in database
    cust_res = await test_session.execute(select(Customer).where(Customer.phone == "+91 98401 23456"))
    customers = cust_res.scalars().all()
    assert len(customers) == 1

@pytest.mark.asyncio
async def test_order_intake_idempotency(test_session):
    extracted = {
        "customer_name": "Vikram Patel",
        "phone": "+91 98765 43210",
        "delivery_address": "Indiranagar, Bengaluru",
        "items": [{"product_name": "Motichoor Ladoo 1kg", "quantity": 3, "unit_price": 300.0}]
    }

    # First call with idempotency key
    order_a = await create_order_from_extraction(
        test_session, extracted, order_input_id="in-10", idempotency_key="idemp-key-12345"
    )
    await test_session.commit()

    # Second call with identical idempotency key
    order_b = await create_order_from_extraction(
        test_session, extracted, order_input_id="in-11", idempotency_key="idemp-key-12345"
    )
    await test_session.commit()

    assert order_a.id == order_b.id
    assert order_a.order_number == order_b.order_number
