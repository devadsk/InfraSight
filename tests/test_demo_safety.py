"""
Unit tests for Public Demo Safety & Cost Controls (Phase 6, Part B2).
Verifies:
1. Replay mode operates unrestricted with zero live tokens and no password.
2. LIVE_PASSWORD gating enforces 403 on live mode and file uploads.
3. Daily spend cap enforces 429 when ledger spend exceeds limit.
4. Per-session quota enforces 429 on exceeding max live runs.
5. Upload auto-delete purges stale uploads.
"""

import os
import time
from pathlib import Path
from fastapi.testclient import TestClient
import pytest

from backend.main import app, SESSION_LIVE_RUNS, cleanup_old_uploads, UPLOAD_DIR
from backend.storage import init_db


@pytest.fixture(autouse=True)
def setup_test_env():
    init_db()
    SESSION_LIVE_RUNS.clear()
    old_env = dict(os.environ)
    yield
    os.environ.clear()
    os.environ.update(old_env)


def test_replay_mode_unrestricted():
    """Replay mode must operate freely without LIVE_PASSWORD or session quota."""
    client = TestClient(app)
    # Even if LIVE_PASSWORD is set in env
    os.environ["LIVE_PASSWORD"] = "secret123"

    resp = client.post("/incidents", data={"description": "Test incident", "mode": "replay"})
    assert resp.status_code == 201
    inc_id = resp.json()["incident_id"]

    resp2 = client.post(f"/incidents/{inc_id}/investigate", params={"mode": "replay", "sync": True})
    assert resp2.status_code == 200
    assert resp2.json()["mode"] == "replay"


def test_live_password_protection():
    """When LIVE_PASSWORD is set, live mode requires the passcode."""
    client = TestClient(app)
    os.environ["LIVE_PASSWORD"] = "hackathon2026"

    # 1. Missing password -> 403
    resp_no_pwd = client.post("/incidents", data={"description": "Test incident", "mode": "live"})
    assert resp_no_pwd.status_code == 403
    assert "LIVE_PASSWORD" in resp_no_pwd.json()["detail"]

    # 2. Invalid password -> 403
    resp_bad_pwd = client.post(
        "/incidents",
        data={"description": "Test incident", "mode": "live", "live_password": "wrong"},
    )
    assert resp_bad_pwd.status_code == 403

    # 3. Correct password -> 201
    resp_good_pwd = client.post(
        "/incidents",
        data={"description": "Test incident", "mode": "live", "live_password": "hackathon2026"},
    )
    assert resp_good_pwd.status_code == 201


def test_file_upload_password_protection():
    """File upload requires LIVE_PASSWORD when configured."""
    client = TestClient(app)
    os.environ["LIVE_PASSWORD"] = "hackathon2026"

    fake_png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 20
    files = [("images", ("test.png", fake_png, "image/png"))]

    # Without password -> 403
    resp = client.post("/incidents", data={"description": "Upload test", "mode": "replay"}, files=files)
    assert resp.status_code == 403

    # With correct password -> 201
    resp_ok = client.post(
        "/incidents",
        data={"description": "Upload test", "mode": "replay", "live_password": "hackathon2026"},
        files=files,
    )
    assert resp_ok.status_code == 201


def test_daily_spend_cap_enforcement():
    """When daily live spend exceeds configured cap, live mode returns 429."""
    client = TestClient(app)
    # Set daily cap to $0.00 to force threshold exceedance
    os.environ["DAILY_SPEND_CAP_USD"] = "0.00"

    resp = client.post("/incidents", data={"description": "Spend test", "mode": "live"})
    assert resp.status_code == 429
    assert "Daily live API spend cap" in resp.json()["detail"]


def test_per_session_live_investigation_quota():
    """Live investigations are capped at 3 per session."""
    client = TestClient(app)
    session_headers = {"X-Session-ID": "tester-session-99"}

    # Run 3 live requests
    for i in range(3):
        resp = client.post(
            "/incidents",
            data={"description": f"Session test {i}", "mode": "live"},
            headers=session_headers,
        )
        assert resp.status_code == 201, f"Run {i+1} failed"

    # 4th run -> 429 Quota Exceeded
    resp_4 = client.post(
        "/incidents",
        data={"description": "Session test 4", "mode": "live"},
        headers=session_headers,
    )
    assert resp_4.status_code == 429
    assert "Per-session limit" in resp_4.json()["detail"]


def test_upload_auto_delete():
    """Stale user uploaded files are automatically purged by cleanup_old_uploads."""
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    test_file = UPLOAD_DIR / "stale_test_image.png"
    test_file.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00")

    # Set access/mod time to 15 minutes ago
    past_time = time.time() - 900
    os.utime(test_file, (past_time, past_time))

    deleted_count = cleanup_old_uploads(max_age_seconds=600)
    assert deleted_count >= 1
    assert not test_file.exists()
