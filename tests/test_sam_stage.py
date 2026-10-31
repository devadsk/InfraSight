"""
Unit tests for SAM 3.1 Guarded Runtime Stage (Phase 6, Part B1).
Verifies:
1. SAM candidate box accepted and used when bright saturated blob is verified.
2. SAM candidate box rejected when region lacks illumination or saturation (dim metal/dark plastic).
3. SAM zero-match handled safely with fallback to default region.
"""

import pytest
from pathlib import Path
from backend.evidence import parse_sam_markers, guard_sam_box, analyze_led_pixels
from backend.meta_client import MetaClient
from backend.orchestrator import InvestigationOrchestrator
from backend.tools import ToolDispatcher


def test_sam_marker_parsing():
    """Test parsing both marker formats (<|box;...|> and [x1, y1, x2, y2])."""
    text1 = "<0f>0<|box;x1=215;y1=176;x2=233;y2=202;w=304;h=657|>"
    boxes1 = parse_sam_markers(text1)
    assert len(boxes1) == 1
    assert boxes1[0]["x1"] == 215
    assert boxes1[0]["y1"] == 176
    assert boxes1[0]["x2"] == 233
    assert boxes1[0]["y2"] == 202

    text2 = "Detected candidate [100, 150, 156, 206]"
    boxes2 = parse_sam_markers(text2)
    assert len(boxes2) == 1
    assert boxes2[0]["x1"] == 100
    assert boxes2[0]["y1"] == 150


def test_sam_stage_box_used_guard_passed():
    """
    Case 1: SAM candidate box is USED when guard verifies bright saturated LED.
    Tested on Raspberrypi.jpg where the localized power indicator LED is bright red.
    """
    img_path = "data/images/user_photos/Raspberrypi.jpg"
    assert Path(img_path).exists()

    candidate_box = {"x1": 215, "y1": 176, "x2": 233, "y2": 202, "w": 18, "h": 26}
    passed, pixel_res, reason = guard_sam_box(img_path, candidate_box)

    assert passed is True
    assert pixel_res.detected_color == "red"
    assert pixel_res.pixel_count_analyzed >= 10
    assert "Passed" in reason

    # Test through orchestrator perception step with enable_sam=True
    client = MetaClient(replay_mode=True)
    orch = InvestigationOrchestrator(meta_client=client)
    dispatcher = ToolDispatcher()

    obs, label, color = orch._analyze_images(
        incident_id="INC-TEST-SAM-USED",
        image_paths=[img_path],
        dispatcher=dispatcher,
        enable_sam=True,
    )

    sam_obs = [o for o in obs if o.get("type") == "sam_localization"]
    assert len(sam_obs) == 1
    assert sam_obs[0]["status"] == "used"
    assert sam_obs[0]["guard_result"] == "passed"
    assert sam_obs[0]["source_id"] == "EV-IMG-Raspberrypi-SAM"
    assert "EV-IMG-Raspberrypi-SAM" in dispatcher.registered_evidence_ids


def test_sam_stage_box_rejected_guard_failed():
    """
    Case 2: SAM candidate box is REJECTED when candidate region lacks saturated illumination.
    Tested on external_hard_disk.jpeg where the indicator is unpowered/dark.
    """
    img_path = "data/images/user_photos/external_hard_disk.jpeg"
    assert Path(img_path).exists()

    candidate_box = {"x1": 657, "y1": 718, "x2": 677, "y2": 739, "w": 20, "h": 21}
    passed, pixel_res, reason = guard_sam_box(img_path, candidate_box)

    assert passed is False
    assert pixel_res.detected_color == "off"
    assert "Rejected" in reason

    # Test through orchestrator perception step
    client = MetaClient(replay_mode=True)
    orch = InvestigationOrchestrator(meta_client=client)
    dispatcher = ToolDispatcher()

    obs, label, color = orch._analyze_images(
        incident_id="INC-TEST-SAM-REJECT",
        image_paths=[img_path],
        dispatcher=dispatcher,
        enable_sam=True,
    )

    sam_obs = [o for o in obs if o.get("type") == "sam_localization"]
    assert len(sam_obs) == 1
    assert sam_obs[0]["status"] == "rejected"
    assert sam_obs[0]["guard_result"] == "failed"


def test_sam_stage_zero_match_fallback():
    """
    Case 3: SAM returns 0 candidate boxes (zero-match).
    Tested on router.jpeg where SAM returned 0 matches for 'LED'.
    System must record zero_match and safely fall back without crashing.
    """
    img_path = "data/images/user_photos/router.jpeg"
    assert Path(img_path).exists()

    client = MetaClient(replay_mode=True)
    orch = InvestigationOrchestrator(meta_client=client)
    dispatcher = ToolDispatcher()

    obs, label, color = orch._analyze_images(
        incident_id="INC-TEST-SAM-ZERO",
        image_paths=[img_path],
        dispatcher=dispatcher,
        enable_sam=True,
    )

    sam_obs = [o for o in obs if o.get("type") == "sam_localization"]
    assert len(sam_obs) == 1
    assert sam_obs[0]["status"] == "zero_match"
    assert sam_obs[0]["guard_result"] == "bypassed"
    assert sam_obs[0]["box_count"] == 0
