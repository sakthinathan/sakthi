import pytest
from app.routers.auth import seed_initial_admin

@pytest.mark.asyncio
async def test_auth_login_success(client, test_session):
    await seed_initial_admin(test_session)
    payload = {
        "email": "admin@utsavops.internal",
        "password": "UtsavOps2026!Secure"
    }
    res = await client.post("/api/auth/login", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["operator"]["email"] == "admin@utsavops.internal"
    assert data["operator"]["role"] == "admin"

@pytest.mark.asyncio
async def test_auth_login_invalid_credentials(client, test_session):
    await seed_initial_admin(test_session)
    payload = {
        "email": "admin@utsavops.internal",
        "password": "WrongPassword123!"
    }
    res = await client.post("/api/auth/login", json=payload)
    assert res.status_code == 401
    assert "Invalid email or password" in res.json()["detail"]

@pytest.mark.asyncio
async def test_auth_me_with_valid_token(client, test_session):
    await seed_initial_admin(test_session)
    # 1. Login to get token
    login_res = await client.post(
        "/api/auth/login",
        json={"email": "admin@utsavops.internal", "password": "UtsavOps2026!Secure"}
    )
    token = login_res.json()["access_token"]

    # 2. Access /api/auth/me
    headers = {"Authorization": f"Bearer {token}"}
    me_res = await client.get("/api/auth/me", headers=headers)
    assert me_res.status_code == 200
    me_data = me_res.json()
    assert me_data["email"] == "admin@utsavops.internal"
    assert me_data["name"] == "UtsavOps Lead SRE"

@pytest.mark.asyncio
async def test_auth_me_without_token(client):
    res = await client.get("/api/auth/me")
    assert res.status_code == 401

@pytest.mark.asyncio
async def test_auth_logout(client):
    res = await client.post("/api/auth/logout")
    assert res.status_code == 200
    assert "logged out" in res.json()["message"].lower()
