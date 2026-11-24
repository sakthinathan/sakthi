"""Comprehensive Authentication and Security Tests for Phase 2C."""
import pytest
from datetime import timedelta
from app.models.operator import Operator
from app.utils.security import (
    create_access_token,
    clear_login_failures,
    hash_password,
)


@pytest.mark.asyncio
async def test_auth_security_tampered_token(client):
    """Tampered token signature must be strictly rejected."""
    # Create valid token
    valid_token = create_access_token({"sub": "test-id", "email": "test@internal", "role": "admin"})
    parts = valid_token.split(".")
    # Tamper payload
    tampered_token = f"{parts[0]}xyz.{parts[1]}"

    res = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {tampered_token}"})
    assert res.status_code == 401
    assert "Invalid, expired, or tampered" in res.json()["detail"]


@pytest.mark.asyncio
async def test_auth_security_expired_token(client):
    """Expired token must be rejected."""
    expired_token = create_access_token(
        {"sub": "test-id", "email": "test@internal", "role": "admin"},
        expires_delta=timedelta(seconds=-10),  # expired 10 seconds ago
    )
    res = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {expired_token}"})
    assert res.status_code == 401
    assert "Invalid, expired, or tampered" in res.json()["detail"]


@pytest.mark.asyncio
async def test_auth_security_revoked_token_after_logout(client):
    """Logged out tokens must be blacklisted and rejected on subsequent requests."""
    # 1. Login
    login_res = await client.post(
        "/api/auth/login",
        json={"email": "admin@utsavops.internal", "password": "UtsavOps2026!Secure"},
    )
    assert login_res.status_code == 200
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Verify token works
    me_res1 = await client.get("/api/auth/me", headers=headers)
    assert me_res1.status_code == 200

    # 3. Logout (revokes token on server side)
    logout_res = await client.post("/api/auth/logout", headers=headers)
    assert logout_res.status_code == 200

    # 4. Attempt to use revoked token
    me_res2 = await client.get("/api/auth/me", headers=headers)
    assert me_res2.status_code == 401
    assert "revoked" in me_res2.json()["detail"].lower()


@pytest.mark.asyncio
async def test_auth_security_inactive_operator_rejected(client, test_session):
    """Deactivated operator accounts must be blocked from logging in or using sessions."""
    # Seed deactivated operator
    deactivated = Operator(
        email="inactive@utsavops.internal",
        hashed_password=hash_password("InactivePass123!"),
        name="Deactivated Operator",
        role="operator",
        is_active=False,
    )
    test_session.add(deactivated)
    await test_session.commit()

    # Login should fail with 403 Forbidden
    login_res = await client.post(
        "/api/auth/login",
        json={"email": "inactive@utsavops.internal", "password": "InactivePass123!"},
    )
    assert login_res.status_code == 403
    assert "deactivated" in login_res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_auth_security_rate_limiting(client):
    """5 consecutive failed login attempts must trigger 429 Too Many Requests."""
    target_email = "brute_force_target@utsavops.internal"
    clear_login_failures(target_email)

    for i in range(5):
        res = await client.post(
            "/api/auth/login",
            json={"email": target_email, "password": f"wrong-pass-{i}"},
        )
        assert res.status_code == 401

    # 6th attempt should be blocked by rate limiter
    blocked_res = await client.post(
        "/api/auth/login",
        json={"email": target_email, "password": "any-password"},
    )
    assert blocked_res.status_code == 429
    assert "Too many failed login attempts" in blocked_res.json()["detail"]
    clear_login_failures(target_email)


@pytest.mark.asyncio
async def test_auth_security_role_based_access_control(client, test_session):
    """Operator role without admin/sre_lead privileges cannot trigger sensitive surge mode."""
    # Create operator with low-privilege role
    low_priv = Operator(
        email="viewer@utsavops.internal",
        hashed_password=hash_password("ViewerPass123!"),
        name="Junior Operator",
        role="operator",
        is_active=True,
    )
    test_session.add(low_priv)
    await test_session.commit()

    # Generate token for low-privilege operator
    token = create_access_token({"sub": low_priv.id, "email": low_priv.email, "role": low_priv.role})
    headers = {"Authorization": f"Bearer {token}"}

    # Attempt to toggle surge mode (requires admin or sre_lead)
    surge_res = await client.post(
        "/api/flags/surge-mode",
        json={"enabled": True, "reason": "Unauthorized surge attempt"},
        headers=headers,
    )
    assert surge_res.status_code == 403
    assert "Permission denied" in surge_res.json()["detail"]
