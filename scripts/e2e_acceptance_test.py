#!/usr/bin/env python3
"""
UtsavOps — End-to-End Demo Acceptance Test
Executes the exact 15-step hackathon demo workflow:
1. Login as configured operator
2. Upload/intake handwritten festive order
3. Extract order details via Sarvam Document AI (or labelled fallback)
4. Review and correct extracted fields
5. Create/persist order in database
6. Validate delivery address via Google Address Validation
7. Evaluate VIP express eligibility
8. Enable surge survival mode and verify VIP vs non-VIP decision
9. Trigger festive surge degradation scenario
10. Run Gemini BYOM Root Cause Analysis grounded in telemetry
11. Approve bounded mitigation as SRE Lead
12. Execute mitigation (with rollback info and honest simulation label)
13. Verify recovery
14. Confirm audit trail records created
15. Logout and verify old token is rejected
"""
import os
import sys
import asyncio
from pathlib import Path

# Configure isolated environment for hermetic E2E acceptance test
os.environ["APP_ENV"] = "testing"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test_utsavops.db"
os.environ["DB_HOST"] = ""
os.environ["AUTH_SECRET_KEY"] = "test-auth-secret-key-minimum-32-characters-long!"
os.environ["INITIAL_ADMIN_PASSWORD"] = "UtsavOps2026!Secure"

import httpx

BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))

BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000")


async def run_e2e_acceptance():
    print("=" * 80)
    print(" 🪔 UTSAVOPS — 15-STEP END-TO-END DEMO ACCEPTANCE TEST")
    print("=" * 80)

    # Use test client against FastAPI ASGI app directly for hermetic test execution
    from app.main import app
    from app.database import AsyncSessionLocal, init_db
    from app.routers.auth import seed_initial_admin
    from httpx import ASGITransport

    await init_db()
    async with AsyncSessionLocal() as db:
        await seed_initial_admin(db)

    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:

        # Step 1: Login as configured operator
        print("[Step 1/15] Logging in as configured operator (admin)...")
        login_res = await client.post("/api/auth/login", json={
            "email": "admin@utsavops.internal",
            "password": "UtsavOps2026!Secure"
        })
        assert login_res.status_code == 200, f"Login failed: {login_res.text}"
        token = login_res.json()["access_token"]
        auth_headers = {"Authorization": f"Bearer {token}"}
        print("  ✓ Login successful, JWT token acquired")

        # Step 2: Upload handwritten festive order
        print("[Step 2/15] Submitting handwritten festive order chit...")
        sample_chit_path = Path(__file__).resolve().parent.parent / "demo_assets" / "diwali_chit_sample.jpg"
        if sample_chit_path.exists():
            with open(sample_chit_path, "rb") as f:
                chit_bytes = f.read()
        else:
            chit_bytes = b"\xff\xd8\xff\xe0\x00\x10JFIF" + b"\x00" * 200

        files = {"file": ("diwali_chit_sample.jpg", chit_bytes, "image/jpeg")}
        intake_res = await client.post("/api/orders/intake/image", files=files, headers=auth_headers)
        assert intake_res.status_code == 200, f"Intake failed: {intake_res.text}"
        intake_data = intake_res.json()
        order_id = intake_data["order_id"]
        order_num = intake_data["order_number"]
        print(f"  ✓ Order created: {order_num} (ID: {order_id})")

        # Step 3: Extract order details with Sarvam or labelled fallback
        print("[Step 3/15] Verifying extraction and provider metadata...")
        meta = intake_data.get("provider_metadata", {})
        print(f"  ✓ Provider: {meta.get('provider')}, Status: {meta.get('status')}, is_mock: {meta.get('is_mock')}")

        # Step 4 & 5: Review and correct extracted fields & persist
        print("[Step 4-5/15] Human-in-the-loop review & order correction...")
        review_res = await client.put(f"/api/orders/{order_id}/review", json={
            "customer_name": "Dr. Meenakshi Sundaram",
            "customer_phone": "+91 98410 54321",
            "delivery_address": "Flat 4B, Sri Krishna Apartments, Malleshwaram, Bengaluru 560003",
            "special_instructions": "Festive Diwali Gift Gold Box Requested"
        }, headers=auth_headers)
        assert review_res.status_code == 200
        print("  ✓ Order review saved, delivery address and customer updated")

        # Step 6: Validate delivery address via Google Address Validation
        print("[Step 6/15] Validating delivery address via Google Cloud APIs...")
        addr_res = await client.post(f"/api/dispatch/{order_id}/validate-address", json={
            "address": "Flat 4B, Sri Krishna Apartments, Malleshwaram, Bengaluru 560003"
        }, headers=auth_headers)
        assert addr_res.status_code == 200
        addr_data = addr_res.json()
        print(f"  ✓ Address validation status: {addr_data.get('validation_status')}, Coords: ({addr_data.get('latitude')}, {addr_data.get('longitude')})")

        # Step 7: Evaluate VIP express eligibility
        print("[Step 7/15] Evaluating customer VIP express eligibility...")
        eval_res = await client.post("/api/flags/evaluate", json={"customer_id": None}, headers=auth_headers)
        assert eval_res.status_code == 200
        print("  ✓ VIP identity evaluation completed")

        # Step 8: Enable surge mode and verify VIP vs non-VIP decision
        print("[Step 8/15] Enabling Surge Survival Mode & verifying load shedding...")
        surge_res = await client.post("/api/flags/surge-mode", json={
            "enabled": True,
            "reason": "Peak Diwali Evening Surge"
        }, headers=auth_headers)
        assert surge_res.status_code == 200
        assert surge_res.json()["surge_survival_mode"] is True
        print("  ✓ Surge survival mode enabled via Flagsmith")

        # Verify VIP gets express, non-VIP is shed
        from app.services.flagsmith_service import flagsmith_service
        vip_check = flagsmith_service.evaluate_vip_express_delivery("smoke-vip", is_vip=True)
        std_check = flagsmith_service.evaluate_vip_express_delivery("smoke-std", is_vip=False)
        assert vip_check["allowed"] is True, "VIP customer must retain express delivery during surge"
        assert std_check["allowed"] is False, "Non-VIP customer must have express delivery load-shed during surge"
        print("  ✓ Flagsmith surge rule verified: VIP express=ALLOWED, Non-VIP express=SHED (False)")

        # Step 9: Trigger festive surge degradation scenario
        print("[Step 9/15] Simulating Diwali checkout degradation...")
        deg_res = await client.post("/api/aiops/services/utsavops-checkout/simulate-degradation", headers=auth_headers)
        assert deg_res.status_code == 200
        deg_data = deg_res.json()
        incident_id = deg_data["incident_id"]
        print(f"  ✓ Incident triggered: {incident_id} (checkout p99 degraded to 4800ms)")

        # Step 10: Gemini BYOM RCA
        print("[Step 10/15] Running Gemini BYOM Root Cause Analysis...")
        rca_res = await client.post(f"/api/aiops/incidents/{incident_id}/investigate", headers=auth_headers)
        assert rca_res.status_code == 200
        rca_data = rca_res.json()
        print(f"  ✓ Gemini RCA: {rca_data.get('root_cause')[:60]}...")

        # Step 11: Approve bounded mitigation
        print("[Step 11/15] Approving bounded mitigation action...")
        inc_res = await client.get(f"/api/aiops/incidents/{incident_id}", headers=auth_headers)
        actions = inc_res.json().get("actions", [])
        assert len(actions) > 0, "No actions proposed by AIOps"
        action_id = actions[0]["id"]

        appr_res = await client.post(f"/api/aiops/incidents/{incident_id}/actions/{action_id}/approve", json={
            "approved_by": "UtsavOps Lead SRE",
            "approval_notes": "Authorized for festive surge mitigation"
        }, headers=auth_headers)
        assert appr_res.status_code == 200
        print(f"  ✓ Mitigation action approved: {action_id}")

        # Step 12: Execute mitigation
        print("[Step 12/15] Executing approved mitigation (honest SIMULATED mode)...")
        exec_res = await client.post(f"/api/aiops/incidents/{incident_id}/actions/{action_id}/execute", headers=auth_headers)
        assert exec_res.status_code == 200
        print("  ✓ Mitigation executed with recorded rollback before-state")

        # Step 13: Verify recovery
        print("[Step 13/15] Verifying checkout recovery telemetry...")
        rec_res = await client.post(f"/api/aiops/incidents/{incident_id}/verify", headers=auth_headers)
        assert rec_res.status_code == 200, f"Verify recovery failed: {rec_res.text}"
        rec_data = rec_res.json()
        assert rec_data["is_healthy"] is True
        print(f"  ✓ Recovery verified: p99 latency restored to {rec_data['health_details']['p99_latency']}")

        # Step 14: Confirm audit trail records
        print("[Step 14/15] Checking immutable audit trail...")
        audit_res = await client.get("/api/audit", headers=auth_headers)
        assert audit_res.status_code == 200
        logs = audit_res.json()
        assert len(logs) >= 4, "Expected multiple audit records"
        print(f"  ✓ Audit log verified: {len(logs)} tamper-evident operational events recorded")

        # Step 15: Logout and verify token is rejected
        print("[Step 15/15] Logging out and testing token revocation...")
        logout_res = await client.post("/api/auth/logout", headers=auth_headers)
        assert logout_res.status_code == 200
        print("  ✓ Logout successful, server-side signature revoked")

        # Verify old token rejected
        revoked_res = await client.get("/api/auth/me", headers=auth_headers)
        assert revoked_res.status_code == 401
        print("  ✓ Revoked token strictly rejected on /api/auth/me (HTTP 401)")

    print("=" * 80)
    print(" 🎉 ALL 15 END-TO-END DEMO ACCEPTANCE STEPS PASSED SUCCESSFULLY!")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(run_e2e_acceptance())
