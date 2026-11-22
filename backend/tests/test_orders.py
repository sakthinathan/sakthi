import pytest
import io

@pytest.mark.asyncio
async def test_order_intake_and_approval(client):
    # 1. Image intake using mock fallback
    dummy_image = io.BytesIO(b"fake-festive-chit-image-content")
    files = {"file": ("chit.jpg", dummy_image, "image/jpeg")}

    res = await client.post("/api/orders/intake/image", files=files)
    assert res.status_code == 200
    data = res.json()
    assert "order_id" in data
    assert data["status"] == "pending_review"
    order_id = data["order_id"]

    # 2. Get order details
    order_res = await client.get(f"/api/orders/{order_id}")
    assert order_res.status_code == 200
    order_data = order_res.json()
    assert len(order_data["items"]) >= 1

    # 3. Human in the loop review update
    review_payload = {
        "customer_name": "Smt. Rajeshwari Iyer (Verified)",
        "special_instructions": "Packed with saffron ribbon"
    }
    rev_res = await client.put(f"/api/orders/{order_id}/review", json=review_payload)
    assert rev_res.status_code == 200

    # 4. Approve order
    appr_res = await client.post(f"/api/orders/{order_id}/approve")
    assert appr_res.status_code == 200
    assert appr_res.json()["status"] == "approved"
