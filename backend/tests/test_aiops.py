import pytest

@pytest.mark.asyncio
async def test_aiops_incident_workflow(client):
    # 1. Check services
    services_res = await client.get("/api/aiops/services")
    assert services_res.status_code == 200
    services = services_res.json()
    assert len(services) >= 2

    # 2. Simulate degradation on utsavops-checkout
    sim_res = await client.post("/api/aiops/services/utsavops-checkout/simulate-degradation")
    assert sim_res.status_code == 200
    incident_id = sim_res.json()["incident_id"]

    # 3. Investigate incident (Gemini BYOM RCA)
    inv_res = await client.post(f"/api/aiops/incidents/{incident_id}/investigate")
    assert inv_res.status_code == 200
    inv_data = inv_res.json()
    assert "root_cause" in inv_data
    assert len(inv_data["recommended_actions"]) >= 1

    # 4. Fetch incident details to find action ID
    inc_res = await client.get(f"/api/aiops/incidents/{incident_id}")
    assert inc_res.status_code == 200
    actions = inc_res.json()["actions"]
    assert len(actions) >= 1
    action_id = actions[0]["id"]

    # 5. Approve action
    appr_res = await client.post(
        f"/api/aiops/incidents/{incident_id}/actions/{action_id}/approve",
        json={"approved_by": "Lead SRE", "notes": "Approved for surge load shedding"}
    )
    assert appr_res.status_code == 200

    # 6. Execute action
    exec_res = await client.post(f"/api/aiops/incidents/{incident_id}/actions/{action_id}/execute")
    assert exec_res.status_code == 200
    assert exec_res.json()["status"] == "completed"

    # 7. Verify recovery
    verif_res = await client.post(f"/api/aiops/incidents/{incident_id}/verify")
    assert verif_res.status_code == 200
    assert verif_res.json()["is_healthy"] is True
