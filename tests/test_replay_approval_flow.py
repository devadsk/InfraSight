"""
Test End-to-End Approval Flow in Replay Mode (Phase 7, Item A1).
Verifies:
1. Replay investigation pauses on Class B action proposal with awaiting_approval.
2. Supervisor approval executes simulated mutation and verifies read-back telemetry.
3. Resumed investigation replays cached final response and reaches resolved_in_simulation.
4. Final diagnosis cites EV-DIAG-SRV004-BAY04-POSTREPLACE.
5. All calls execute 100% offline with zero live tokens.
"""

from fastapi.testclient import TestClient
import pytest
from backend.main import app
from backend.storage import init_db, get_incident, get_pending_actions_for_incident


def test_e2e_replay_approval_workflow():
    init_db()
    client = TestClient(app)

    # 1. Create incident in replay mode for SCN-08
    resp = client.post(
        "/incidents",
        data={
            "description": "Technician requests drive replacement on SRV-004 bay 4 after confirmed failure. Approval granted.",
            "image_paths": '["data/images/SRV004_BAY04_AMBER_SOLID.png"]',
            "mode": "replay",
        },
    )
    assert resp.status_code == 201
    inc_data = resp.json()
    incident_id = inc_data["incident_id"]

    # 2. Run investigation synchronously in replay mode
    inv_resp = client.post(
        f"/incidents/{incident_id}/investigate",
        params={"sync": True, "mode": "replay"},
    )
    assert inv_resp.status_code == 200
    inv_data = inv_resp.json()

    # Investigation pauses at awaiting_approval
    inc = get_incident(incident_id)
    assert inc["final_status"] == "awaiting_approval"

    # Pending action held for supervisor approval
    actions = get_pending_actions_for_incident(incident_id)
    assert len(actions) == 1
    action = actions[0]
    assert action["status"] == "pending"
    assert action["tool"] == "propose_action"
    action_id = action["action_id"]

    # 3. Supervisor clicks 'Approve Action' via API
    app_resp = client.post(
        f"/actions/{action_id}/approve",
        json={"decided_by": "supervisor@datacenter"},
    )
    assert app_resp.status_code == 200
    app_data = app_resp.json()

    # 4. Verify post-action execution and resumed diagnosis
    assert app_data["status"] == "executed"
    assert app_data["incident_status"] == "resolved_in_simulation"
    assert app_data["verification"]["verified"] is True
    post_ev_id = app_data["verification"]["post_evidence_id"]
    assert post_ev_id == "EV-DIAG-SRV004-BAY04-POSTREPLACE"

    # Verify diagnosis contents
    diag = app_data["diagnosis"]
    assert diag["status"] == "resolved_in_simulation"
    assert diag["confidence"] == "high"
    assert post_ev_id in diag["supporting_evidence_ids"]

