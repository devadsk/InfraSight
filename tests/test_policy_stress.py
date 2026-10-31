"""
Tests for Policy Stress Test (Phase 6 / Close-Out A3).
Asserts that all 5 scripted adversarial requests are intercepted and denied by real backend boundaries:
  (a) Arbitrary shell command
  (b) Restart without supervisor approval
  (c) Replacement on wrong/unauthorized device
  (d) Unknown action name
  (e) Tool call with injected approval flag
"""

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.policy_stress import run_policy_stress_test, STRESS_TEST_LABEL
from backend.storage import get_incident_audit_trail, init_db


@pytest.fixture
def client(tmp_path):
    test_db = tmp_path / "test_stress.db"
    init_db(test_db)
    return TestClient(app)


def test_policy_stress_test_backend_unit(tmp_path):
    test_db = tmp_path / "stress_unit.db"
    init_db(test_db)

    res = run_policy_stress_test(db_path=test_db)

    assert res["status"] == "unresolved"
    assert res["label"] == STRESS_TEST_LABEL

    outcomes = {o["step"]: o for o in res["outcomes"]}
    assert len(outcomes) == 5

    # (a) Arbitrary shell command denied
    assert outcomes["a"]["status"] == "denied"
    assert "Class C" in outcomes["a"]["policy_class"]

    # (b) Restart without approval denied
    assert outcomes["b"]["status"] == "denied"
    assert "Class B" in outcomes["b"]["policy_class"]

    # (c) Wrong device replacement denied
    assert outcomes["c"]["status"] == "denied"
    assert "Class C" in outcomes["c"]["policy_class"]

    # (d) Unknown action name denied
    assert outcomes["d"]["status"] == "denied"
    assert "Class C" in outcomes["d"]["policy_class"]

    # (e) Injected approval flag ignored & execution denied
    assert outcomes["e"]["status"] == "denied"
    assert "Class B" in outcomes["e"]["policy_class"]

    # Verify audit events recorded in database
    trail = get_incident_audit_trail(res["incident_id"], db_path=test_db)
    event_types = [e["event_type"] for e in trail]
    assert "policy_decision" in event_types
    assert "authorization_denied" in event_types
    assert "incident_received" in event_types


def test_policy_stress_test_api_endpoint(client):
    resp = client.post("/policy/stress-test")
    assert resp.status_code == 200
    data = resp.json()

    assert data["status"] == "unresolved"
    assert data["label"] == STRESS_TEST_LABEL
    assert len(data["outcomes"]) == 5

    steps = [o["step"] for o in data["outcomes"]]
    assert steps == ["a", "b", "c", "d", "e"]
    for o in data["outcomes"]:
        assert o["status"] == "denied"
