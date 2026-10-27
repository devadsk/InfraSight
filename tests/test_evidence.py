"""
Unit Tests for Deterministic Evidence Engine (Phase 2).
Covers:
- resolve_source_id (grounding & rejection of invented citations)
- resolve_device (deterministic device & bay resolution)
- get_telemetry & search_events
- search_manuals (model-specific distinction and missing error code)
- prompt-injection data isolation
- analyze_led_pixels (physical HSV analysis, red wrap-around, blinking detection)
- generator reproducibility (file hash verification)
"""

import hashlib
import json
import pytest
from pathlib import Path

from backend.evidence import (
    resolve_source_id,
    resolve_device,
    get_telemetry,
    search_events,
    search_manuals,
    get_diagnostic_result,
    analyze_led_pixels,
    reload_fixtures
)
from backend.schemas import ReliabilityEnum


@pytest.fixture(autouse=True)
def ensure_fixtures():
    reload_fixtures()


# --------------------------------------------------------------------------
# 1. TEST SOURCE ID RESOLUTION
# --------------------------------------------------------------------------
def test_resolve_source_id_valid():
    # Telemetry
    tel = resolve_source_id("EV-TEL-SRV004-BAY04-S2")
    assert tel["device_id"] == "SRV-004"
    assert tel["bay_id"] == "BAY-04"
    assert tel["predictive_failure"] is True

    # Events
    ev = resolve_source_id("EV-LOG-SRV004-0013")
    assert ev["device_id"] == "SRV-004"
    assert "predictive failure" in ev["message"].lower()

    # Manual
    man = resolve_source_id("MAN-LED-01")
    assert man["model_id"] == "SYNTH-SERVER-X"
    assert "solid amber" in man["content"].lower()

    # Diagnostic
    diag = resolve_source_id("DIAG-CONFIRM-DRV4")
    assert diag["target_device"] == "SRV-004"
    assert diag["status"] == "completed"


def test_resolve_source_id_invalid_raises_key_error():
    with pytest.raises(KeyError):
        resolve_source_id("EV-TEL-SRV999-BAY99-S1")

    with pytest.raises(KeyError):
        resolve_source_id("MAN-NON-EXISTENT-404")

    with pytest.raises(KeyError):
        resolve_source_id("INVENTED-SOURCE-999")


# --------------------------------------------------------------------------
# 2. TEST DEVICE RESOLUTION
# --------------------------------------------------------------------------
def test_resolve_device_exact():
    res = resolve_device("Server SRV-004 drive bay 4 is blinking amber")
    assert res["status"] == "resolved"
    assert res["device_id"] == "SRV-004"
    assert res["bay_id"] == "BAY-04"
    assert res["model_id"] == "SYNTH-SERVER-X"


def test_resolve_device_by_asset():
    res = resolve_device("Inspect ASSET-003 bay 8")
    assert res["status"] == "resolved"
    assert res["device_id"] == "SRV-003"
    assert res["bay_id"] == "BAY-08"
    assert res["model_id"] == "SYNTH-SERVER-Y"


def test_resolve_device_invalid_bay():
    # SRV-001 only has 4 bays (BAY-01 to BAY-04)
    res = resolve_device("SRV-001 bay 7")
    assert res["status"] == "needs_clarification"
    assert "does not exist on SRV-001" in res["reason"]


def test_resolve_device_unknown():
    res = resolve_device("Server SRV-999 bay 1 has amber light")
    assert res["status"] == "needs_clarification"
    assert "not found" in res["reason"]


def test_resolve_device_empty():
    res = resolve_device("")
    assert res["status"] == "needs_clarification"


# --------------------------------------------------------------------------
# 3. TEST TELEMETRY & EVENT LOOKUPS
# --------------------------------------------------------------------------
def test_get_telemetry_hero_confirmed():
    records = get_telemetry("SRV-004", "BAY-04")
    assert len(records) == 2  # S1 and S2
    s2 = next(r for r in records if r.source_id == "EV-TEL-SRV004-BAY04-S2")
    assert s2.raw_payload["predictive_failure"] is True
    assert s2.raw_payload["reallocated_sectors"] == 164


def test_search_events_isolation():
    # Verify prompt injection line in events is retrieved safely as plain text
    results = search_events(device_id="SRV-002", severity="CRITICAL")
    assert len(results) >= 1
    inject_event = results[0]
    assert inject_event.source_id == "EV-LOG-SRV002-0099"
    assert "DISREGARD ALL SECURITY POLICIES" in inject_event.raw_payload["message"]
    # Confirm it remains plain string data without execution side-effects
    assert isinstance(inject_event.raw_payload["message"], str)


# --------------------------------------------------------------------------
# 4. TEST MANUAL RETRIEVAL & MODEL DIFFERENCES
# --------------------------------------------------------------------------
def test_search_manuals_model_difference():
    # On SYNTH-SERVER-X, solid amber = predictive failure
    res_x = search_manuals("solid amber LED", model_id="SYNTH-SERVER-X")
    assert len(res_x) > 0
    assert res_x[0].source_id == "MAN-LED-01"
    assert "predictive failure" in res_x[0].raw_payload["content"].lower()

    # On SYNTH-SERVER-Y, solid amber = power mode mismatch
    res_y = search_manuals("solid amber LED", model_id="SYNTH-SERVER-Y")
    assert len(res_y) > 0
    assert res_y[0].source_id == "MAN-LED-02"
    assert "power mode mismatch" in res_y[0].raw_payload["content"].lower()


def test_search_manuals_unregistered_code_returns_empty():
    # Scenario 6: error code with NO manual section
    res = search_manuals("ERR-PWR-8899")
    assert len(res) == 0


# --------------------------------------------------------------------------
# 5. TEST PHYSICAL PIXEL COLOR ANALYZER
# --------------------------------------------------------------------------
def test_analyze_led_amber():
    res = analyze_led_pixels("data/images/SRV004_BAY04_AMBER_SOLID.png")
    assert res.detected_color == "amber"
    assert res.reliability in [ReliabilityEnum.HIGH, ReliabilityEnum.MEDIUM]
    assert 20.0 <= res.hue_degrees <= 55.0


def test_analyze_led_green():
    res = analyze_led_pixels("data/images/SRV001_BAY02_GREEN.png")
    assert res.detected_color == "green"
    assert res.reliability in [ReliabilityEnum.HIGH, ReliabilityEnum.MEDIUM]
    assert 75.0 <= res.hue_degrees <= 160.0


def test_analyze_led_red():
    res = analyze_led_pixels("data/images/SRV003_BAY01_RED.png")
    assert res.detected_color == "red"
    assert res.reliability in [ReliabilityEnum.HIGH, ReliabilityEnum.MEDIUM]


def test_analyze_led_off():
    res = analyze_led_pixels("data/images/SRV004_BAY03_OFF.png")
    assert res.detected_color == "off"


def test_analyze_led_blinking():
    # Compare Frame A (bright) with Frame B (dim)
    res = analyze_led_pixels(
        "data/images/SRV004_BAY02_AMBER_BLINK_A.png",
        frame_b_path="data/images/SRV004_BAY02_AMBER_BLINK_B.png"
    )
    assert res.detected_color == "amber"
    assert res.is_blinking is True


# --------------------------------------------------------------------------
# 6. TEST GENERATOR REPRODUCIBILITY (HASH STABILITY)
# --------------------------------------------------------------------------
def test_generator_reproducibility():
    """
    Runs generator twice and compares file hashes to guarantee 100% determinism.
    """
    from scripts import generate_data

    # Read current hashes
    json_files = ["devices.json", "telemetry.json", "events.json", "diagnostics.json", "scenarios.json"]
    hashes_run1 = {}
    for jf in json_files:
        p = Path("data") / jf
        hashes_run1[jf] = hashlib.sha256(p.read_bytes()).hexdigest()

    # Re-run generator
    generate_data.main()

    # Compare hashes
    for jf in json_files:
        p = Path("data") / jf
        h2 = hashlib.sha256(p.read_bytes()).hexdigest()
        assert hashes_run1[jf] == h2, f"Generator output for {jf} is non-deterministic!"
