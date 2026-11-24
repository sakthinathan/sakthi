import pytest

@pytest.mark.asyncio
async def test_customer_lifecycle(auth_client):
    client = auth_client
    # 1. Create customer
    create_payload = {
        "name": "Diwali Sweets Buyer",
        "phone": "+91 99999 88888",
        "tier": "regular",
        "is_vip": False
    }
    res = await client.post("/api/customers", json=create_payload)
    assert res.status_code == 200
    cust = res.json()
    assert cust["name"] == "Diwali Sweets Buyer"
    assert cust["is_vip"] is False
    cust_id = cust["id"]

    # 2. Toggle VIP status
    res_vip = await client.post(f"/api/customers/{cust_id}/vip")
    assert res_vip.status_code == 200
    assert res_vip.json()["is_vip"] is True
    assert res_vip.json()["tier"] == "vip"

    # 3. List customers
    res_list = await client.get("/api/customers")
    assert res_list.status_code == 200
    data = res_list.json()
    assert data["total"] >= 1
