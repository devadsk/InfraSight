"""
Tests for Phase 5: Streamlit Interface, API Endpoints, and Replay Mode.
Covers:
- API endpoints: /scenarios, /usage/summary, /incidents/{id}/report, mode & usage fields.
- Security: scenarios endpoint never exposes rubrics or expected answers.
- Streamlit AppTest: banner rendering, scenario loading, diagnosis card, approval panel, and error banners.
"""

import io
import json
from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient
from streamlit.testing.v1 import AppTest

from backend.main import app
from backend.storage import (
    init_db,
    record_incident,
    record_pending_action,
    record_usage,
    update_incident_status,
)


@pytest.fixture
def client(tmp_path, monkeypatch):
    """Provides a fresh isolated test client with a temporary SQLite database."""
    db_file = tmp_path / "test_phase5.db"
    monkeypatch.setattr("backend.storage.DB_PATH", db_file)
    monkeypatch.setattr("backend.main.UPLOAD_DIR", tmp_path / "uploads")
    init_db(db_file)
    with TestClient(app) as test_client:
        yield test_client


# Mock scenario data for Streamlit AppTest tests
MOCK_SCENARIOS = [
    {
        "scenario_id": "SCN-02",
        "name": "Hero 2: Rebuild Contradiction (Amber != Failed)",
        "category": "Hero Contradiction",
        "incident_description": "Amber LED observed on server SRV-004 bay 2.",
        "image_reference": "data/images/SRV004_BAY02_AMBER_BLINK_A.png",
        "image_frames": ["data/images/SRV004_BAY02_AMBER_BLINK_A.png"],
    },
    {
        "scenario_id": "SCN-01",
        "name": "Hero 1: Confirmed Drive Failure",
        "category": "Hero Confirmed",
        "incident_description": "Solid amber LED on SRV-004 bay 4.",
        "image_reference": "data/images/SRV004_BAY04_AMBER_SOLID.png",
        "image_frames": ["data/images/SRV004_BAY04_AMBER_SOLID.png"],
    },
]

MOCK_USAGE = {
    "total_calls": 5,
    "total_tokens": 2500,
    "total_cost_usd": 0.0015,
    "by_purpose": [],
}


# ---------------------------------------------------------------------------
# 1. Backend API Endpoint Tests
# ---------------------------------------------------------------------------

def test_api_scenarios_sanitized_and_ordered(client):
    """GET /scenarios must return sanitized scenarios with hero cases first and NO expected answers."""
    resp = client.get("/scenarios")
    assert resp.status_code == 200
    scenarios = resp.json()
    assert len(scenarios) >= 5

    # Check Hero order: SCN-02, SCN-01, SCN-10, SCN-08, SCN-03
    first_five_ids = [s["scenario_id"] for s in scenarios[:5]]
    assert first_five_ids == ["SCN-02", "SCN-01", "SCN-10", "SCN-08", "SCN-03"]

    # Security check: NEVER expose expected answers or rubrics
    forbidden_keys = {
        "expected_device",
        "expected_bay",
        "expected_manual_evidence_ids",
        "relevant_telemetry_ids",
        "acceptable_diagnosis_set",
        "allowed_diagnostic_actions",
        "actions_must_be_denied",
        "expected_final_status",
    }
    for scn in scenarios:
        assert "scenario_id" in scn
        assert "name" in scn
        assert "incident_description" in scn
        for fk in forbidden_keys:
            assert fk not in scn, f"Security Violation: '{fk}' leaked in scenario {scn['scenario_id']}!"


def test_api_usage_summary(client):
    """GET /usage/summary returns aggregated tokens and cost from ledger."""
    record_usage(
        purpose="test_eval",
        model_id="muse-spark-1.3",
        usage={"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
        incident_id="INC-TEST-001",
    )

    resp = client.get("/usage/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_calls"] >= 1
    assert data["total_tokens"] >= 150
    assert "total_cost_usd" in data
    assert "by_purpose" in data


def test_api_incident_report_markdown(client):
    """GET /incidents/{id}/report returns full Markdown audit report per Master Spec Step 9."""
    record_incident(
        incident_id="INC-REPORT-1",
        user_text="Amber blinking LED on SRV-004 bay 2.",
        device_id="SRV-004",
        bay_id="BAY-02",
        final_status="not_confirmed",
        confidence="high",
        summary="Drive is healthy; RAID rebuild in progress.",
        raw_diagnosis={"supporting_evidence_ids": ["MAN-RAID-01"], "contradictory_evidence_ids": []},
        mode="replay",
    )

    resp = client.get("/incidents/INC-REPORT-1/report")
    assert resp.status_code == 200
    data = resp.json()
    assert data["format"] == "markdown"
    report_text = data["report"]
    assert "Simulated Environment Notice" in report_text
    assert "SRV-004" in report_text
    assert "NOT_CONFIRMED" in report_text
    assert "MAN-RAID-01" in report_text


def test_api_mode_and_usage_in_incident_details(client):
    """GET /incidents/{id} includes execution mode and per-call usage accounting."""
    record_incident(
        incident_id="INC-MODE-1",
        user_text="Checking drive status.",
        final_status="confirmed",
        mode="replay",
    )
    record_usage(
        purpose="synthesize_diagnosis",
        model_id="muse-spark-1.3",
        usage={"prompt_tokens": 200, "completion_tokens": 100, "total_tokens": 300},
        incident_id="INC-MODE-1",
        is_replay=True,
    )

    resp = client.get("/incidents/INC-MODE-1")
    assert resp.status_code == 200
    data = resp.json()
    assert data["mode"] == "replay"
    assert "usage" in data
    assert data["usage"]["total_tokens"] == 300
    assert len(data["usage"]["calls"]) == 1
    assert data["usage"]["calls"][0]["is_replay"] == 1


# ---------------------------------------------------------------------------
# 2. Streamlit AppTest Smoke Tests
# ---------------------------------------------------------------------------

def test_streamlit_app_renders_banner():
    """Streamlit app renders persistent simulated environment banner."""
    with patch("frontend.api_client.InfraSightAPIClient.health_check", return_value={"status": "ok", "mode": "simulated"}), \
         patch("frontend.api_client.InfraSightAPIClient.list_scenarios", return_value=MOCK_SCENARIOS), \
         patch("frontend.api_client.InfraSightAPIClient.get_usage_summary", return_value=MOCK_USAGE):
        at = AppTest.from_file("frontend/app.py", default_timeout=15)
        at.run()
        assert not at.exception
        html_blocks = [m.value for m in at.markdown]
        banner_found = any("Simulated environment:" in h for h in html_blocks)
        assert banner_found, "Persistent simulated banner missing from app!"


def test_streamlit_app_loads_scenarios():
    """Streamlit app sidebar loads synthetic scenario picker."""
    with patch("frontend.api_client.InfraSightAPIClient.health_check", return_value={"status": "ok", "mode": "simulated"}), \
         patch("frontend.api_client.InfraSightAPIClient.list_scenarios", return_value=MOCK_SCENARIOS), \
         patch("frontend.api_client.InfraSightAPIClient.get_usage_summary", return_value=MOCK_USAGE):
        at = AppTest.from_file("frontend/app.py", default_timeout=15)
        at.run()
        assert not at.exception
        assert len(at.sidebar.selectbox) >= 1
        picker = at.sidebar.selectbox[0]
        assert "Hero 2" in picker.options[0] or "SCN-02" in picker.options[0]


def test_streamlit_app_diagnosis_card_render():
    """Streamlit app renders diagnosis card when incident is loaded in session_state."""
    mock_incident = {
        "incident_id": "INC-MOCK-01",
        "status": "not_confirmed",
        "confidence": "high",
        "device_id": "SRV-004",
        "bay_id": "BAY-02",
        "summary": "Drive is verified healthy. Amber light indicates active RAID rebuild.",
        "diagnosis": {
            "status": "not_confirmed",
            "confidence": "high",
            "supporting_evidence_ids": ["MAN-RAID-01", "EV-TEL-01"],
            "contradictory_evidence_ids": [],
            "missing_information": None,
            "recommended_action": "Do not replace drive; allow RAID array rebuild to complete.",
        },
        "pending_actions": [],
        "timeline": [
            {"step_number": 0, "timestamp": "2026-10-29T10:00:00Z", "event_type": "incident_created", "details": {}},
        ],
        "mode": "replay",
        "usage": {"call_count": 2, "total_tokens": 1200, "total_cost_usd": 0.0008, "calls": []},
    }

    with patch("frontend.api_client.InfraSightAPIClient.health_check", return_value={"status": "ok", "mode": "simulated"}), \
         patch("frontend.api_client.InfraSightAPIClient.list_scenarios", return_value=MOCK_SCENARIOS), \
         patch("frontend.api_client.InfraSightAPIClient.get_usage_summary", return_value=MOCK_USAGE), \
         patch("frontend.api_client.InfraSightAPIClient.get_incident", return_value=mock_incident), \
         patch("frontend.api_client.InfraSightAPIClient.get_incident_report", return_value="# Mock Report"):
        at = AppTest.from_file("frontend/app.py", default_timeout=15)
        at.session_state["current_incident_id"] = "INC-MOCK-01"
        at.run()

        assert not at.exception
        markdown_texts = " ".join([m.value for m in at.markdown])
        assert "NOT_CONFIRMED" in markdown_texts
        success_texts = " ".join([s.value for s in at.success])
        assert "Do not replace drive" in success_texts


def test_streamlit_app_approval_panel_render_and_action():
    """Streamlit app renders approval panel for pending action and calls approve_action."""
    mock_incident = {
        "incident_id": "INC-APP-01",
        "status": "awaiting_approval",
        "confidence": "high",
        "device_id": "SRV-004",
        "bay_id": "BAY-04",
        "summary": "Drive degradation confirmed. Replacement requires human authorization.",
        "diagnosis": {
            "status": "awaiting_approval",
            "confidence": "high",
            "supporting_evidence_ids": ["EV-TEL-BAY04-01"],
            "contradictory_evidence_ids": [],
            "recommended_action": "Approve drive replacement.",
        },
        "pending_actions": [
            {
                "action_id": "ACT-TEST-001",
                "tool": "replace_drive",
                "canonical_args": '{"device_id": "SRV-004", "bay_id": "BAY-04"}',
                "args_hash": "a1b2c3d4",
                "status": "pending",
                "expires_at": "2026-10-29T12:00:00Z",
            }
        ],
        "timeline": [],
        "mode": "replay",
        "usage": {"call_count": 1, "total_tokens": 800, "total_cost_usd": 0.0005, "calls": []},
    }

    with patch("frontend.api_client.InfraSightAPIClient.health_check", return_value={"status": "ok", "mode": "simulated"}), \
         patch("frontend.api_client.InfraSightAPIClient.list_scenarios", return_value=MOCK_SCENARIOS), \
         patch("frontend.api_client.InfraSightAPIClient.get_usage_summary", return_value=MOCK_USAGE), \
         patch("frontend.api_client.InfraSightAPIClient.get_incident", return_value=mock_incident), \
         patch("frontend.api_client.InfraSightAPIClient.get_incident_report", return_value="# Report"), \
         patch("frontend.api_client.InfraSightAPIClient.approve_action", return_value=(True, "Approved", {})) as mock_approve:
        at = AppTest.from_file("frontend/app.py", default_timeout=15)
        at.session_state["current_incident_id"] = "INC-APP-01"
        at.run()
        assert not at.exception

        markdown_texts = " ".join([m.value for m in at.markdown])
        assert "Human Supervisor Approval Gate" in markdown_texts
        warning_texts = " ".join([w.value for w in at.warning])
        assert "replace_drive" in warning_texts

        approve_btn = next((b for b in at.button if "Approve Action" in b.label), None)
        assert approve_btn is not None
        approve_btn.click().run()
        assert mock_approve.called


def test_streamlit_app_handles_connection_error():
    """Streamlit app shows error banner without crashing when backend is unreachable."""
    from frontend.api_client import APIConnectionError

    with patch("frontend.api_client.InfraSightAPIClient.health_check", side_effect=APIConnectionError("Backend connection refused.")), \
         patch("frontend.api_client.InfraSightAPIClient.list_scenarios", side_effect=APIConnectionError("Scenarios unavailable.")), \
         patch("frontend.api_client.InfraSightAPIClient.get_usage_summary", return_value=MOCK_USAGE):
        at = AppTest.from_file("frontend/app.py", default_timeout=15)
        at.run()
        assert not at.exception
        assert len(at.sidebar.error) >= 1
        assert "Backend Offline" in at.sidebar.error[0].value
