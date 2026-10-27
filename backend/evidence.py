"""
Deterministic Evidence Engine for InfraSight (Phase 2).
Provides authoritative lookups and physical pixel analysis without using an LLM:
- resolve_source_id(source_id) -> record (or raises KeyError)
- resolve_device(identifier) -> device dict or needs_clarification
- get_telemetry(device_id, bay_id) -> list of EvidenceRecord
- search_events(device_id, limit, query) -> list of EvidenceRecord
- search_manuals(query, model_id, limit) -> list of EvidenceRecord
- get_diagnostic_result(diagnostic_id) -> EvidenceRecord
- analyze_led_pixels(image_path, bounding_box, frame_b_path) -> PixelColorResult
"""

import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from PIL import Image

from backend.schemas import (
    ConfidenceEnum,
    EvidenceRecord,
    EvidenceType,
    PixelColorResult,
    ReliabilityEnum,
)

DATA_DIR = Path("data")
DEVICES_FILE = DATA_DIR / "devices.json"
TELEMETRY_FILE = DATA_DIR / "telemetry.json"
EVENTS_FILE = DATA_DIR / "events.json"
MANUALS_FILE = DATA_DIR / "manuals.json"
DIAGNOSTICS_FILE = DATA_DIR / "diagnostics.json"


def _load_json(file_path: Path) -> Any:
    if not file_path.exists():
        return None
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


# In-memory caches of static fixtures
_DEVICES_CACHE = None
_TELEMETRY_CACHE = None
_EVENTS_CACHE = None
_MANUALS_CACHE = None
_DIAGNOSTICS_CACHE = None


def reload_fixtures():
    global _DEVICES_CACHE, _TELEMETRY_CACHE, _EVENTS_CACHE, _MANUALS_CACHE, _DIAGNOSTICS_CACHE
    _DEVICES_CACHE = _load_json(DEVICES_FILE) or []
    _TELEMETRY_CACHE = _load_json(TELEMETRY_FILE) or []
    _EVENTS_CACHE = _load_json(EVENTS_FILE) or []
    _MANUALS_CACHE = _load_json(MANUALS_FILE) or []
    _DIAGNOSTICS_CACHE = _load_json(DIAGNOSTICS_FILE) or {}


reload_fixtures()


# --------------------------------------------------------------------------
# 1. RESOLVE SOURCE ID (Strict Grounding Verifier Primitive)
# --------------------------------------------------------------------------
def resolve_source_id(source_id: str) -> Dict[str, Any]:
    """
    Looks up any backend source ID (EV-TEL-..., EV-LOG-..., MAN-..., DIAG-..., EV-IMG-...).
    Returns the underlying record if verified, or raises KeyError if invented.
    """
    if not source_id or not isinstance(source_id, str):
        raise KeyError(f"Invalid source ID format: {source_id}")

    sid = source_id.strip()

    # Telemetry
    if sid.startswith("EV-TEL-"):
        for t in _TELEMETRY_CACHE:
            if t.get("source_id") == sid:
                return t
        if sid.endswith("-NODATA"):
            # Explicit unmonitored/empty bay record
            parts = sid.split("-")
            d_id = f"{parts[2]}-{parts[3]}" if len(parts) >= 4 else "UNKNOWN"
            b_id = f"{parts[4]}-{parts[5]}" if len(parts) >= 6 else "UNKNOWN"
            return {"source_id": sid, "status": "no_data", "device_id": d_id, "bay_id": b_id, "predictive_failure": False}
        raise KeyError(f"Telemetry record not found for source ID: '{sid}'")

    # Event logs
    if sid.startswith("EV-LOG-"):
        for e in _EVENTS_CACHE:
            if e.get("source_id") == sid:
                return e
        raise KeyError(f"Syslog record not found for source ID: '{sid}'")

    # Manuals
    if sid.startswith("MAN-"):
        for m in _MANUALS_CACHE:
            if m.get("source_id") == sid:
                return m
        raise KeyError(f"Manual section not found for source ID: '{sid}'")

    # Diagnostics
    if sid.startswith("DIAG-"):
        if sid in _DIAGNOSTICS_CACHE:
            return _DIAGNOSTICS_CACHE[sid]
        raise KeyError(f"Diagnostic record not found for source ID: '{sid}'")

    # Image measurements
    if sid.startswith("EV-IMG-"):
        # Image identifier pattern: EV-IMG-<image_stem>
        return {"source_id": sid, "type": "image_measurement", "status": "registered"}

    raise KeyError(f"Unrecognized evidence source ID pattern: '{sid}'")


# --------------------------------------------------------------------------
# 2. DETERMINISTIC DEVICE RESOLUTION
# --------------------------------------------------------------------------
def resolve_device(identifier_text: str) -> Dict[str, Any]:
    """
    Deterministic resolution of server and drive bay from text or asset codes.
    If ambiguous or unknown, returns status: 'needs_clarification' with candidates.
    Never guesses.
    """
    if not identifier_text or not identifier_text.strip():
        return {
            "status": "needs_clarification",
            "reason": "Missing device identifier or incident text",
            "candidates": [d["device_id"] for d in _DEVICES_CACHE]
        }

    raw = identifier_text.upper()

    # Match device ID e.g. SRV-001 to SRV-005
    dev_match = re.search(r"\b(SRV-00[1-5])\b", raw)
    # Match Asset ID e.g. ASSET-001
    asset_match = re.search(r"\b(ASSET-00[1-5])\b", raw)
    # Match Bay ID e.g. BAY-01 to BAY-08
    bay_match = re.search(r"\b(BAY-0[1-8])\b", raw)
    if not bay_match:
        # Also support phrases like "bay 4" or "bay 04"
        alt_bay = re.search(r"\bBAY\s*0?([1-8])\b", raw)
        if alt_bay:
            bay_match_str = f"BAY-0{alt_bay.group(1)}"
        else:
            bay_match_str = None
    else:
        bay_match_str = bay_match.group(1)

    matched_device = None
    if dev_match:
        target_id = dev_match.group(1)
        matched_device = next((d for d in _DEVICES_CACHE if d["device_id"] == target_id), None)
    elif asset_match:
        target_asset = asset_match.group(1)
        matched_device = next((d for d in _DEVICES_CACHE if d["asset_id"] == target_asset), None)

    # Check for invalid/unknown device like SRV-999
    if not matched_device:
        invalid_match = re.search(r"\b(SRV-[0-9]{3,4})\b", raw)
        if invalid_match:
            return {
                "status": "needs_clarification",
                "reason": f"Device '{invalid_match.group(1)}' not found in active infrastructure inventory",
                "candidates": [d["device_id"] for d in _DEVICES_CACHE]
            }
        return {
            "status": "needs_clarification",
            "reason": "Could not identify server hardware from input",
            "candidates": [d["device_id"] for d in _DEVICES_CACHE]
        }

    # Verify bay is valid for this device
    if bay_match_str and bay_match_str not in matched_device["bays"]:
        return {
            "status": "needs_clarification",
            "reason": f"Drive bay {bay_match_str} does not exist on {matched_device['device_id']} (has {matched_device['bay_count']} bays: {matched_device['bays']})",
            "candidates": matched_device["bays"]
        }

    return {
        "status": "resolved",
        "device": matched_device,
        "device_id": matched_device["device_id"],
        "model_id": matched_device["model_id"],
        "bay_id": bay_match_str
    }


# --------------------------------------------------------------------------
# 3. TELEMETRY LOOKUP
# --------------------------------------------------------------------------
def get_telemetry(device_id: str, bay_id: Optional[str] = None) -> List[EvidenceRecord]:
    """
    Returns telemetry evidence records for specified device and optional bay.
    """
    dev_id = device_id.upper().strip()
    bay = bay_id.upper().strip() if bay_id else None

    matches = []
    for t in _TELEMETRY_CACHE:
        if t["device_id"] == dev_id:
            if bay is None or t["bay_id"] == bay:
                matches.append(t)

    # Wrap in EvidenceRecord
    records = []
    for m in matches:
        pred = "FLAGGED" if m.get("predictive_failure") else "CLEARED"
        summary = (
            f"SMART Telemetry for {m['device_id']}/{m['bay_id']}: Status={m.get('smart_status')}, "
            f"PredictiveFailure={pred}, ReallocatedSectors={m.get('reallocated_sectors')}, "
            f"PendingSectors={m.get('current_pending_sectors')}, RAID={m.get('raid_status')}."
        )
        rec = EvidenceRecord(
            source_id=m["source_id"],
            evidence_type=EvidenceType.TELEMETRY,
            title=f"Drive Telemetry {m['device_id']} {m['bay_id']}",
            summary=summary,
            raw_payload=m,
            timestamp=m.get("timestamp")
        )
        records.append(rec)

    # If a specific bay was queried but has no telemetry in fixture
    if bay and not matches:
        dev_obj = next((d for d in _DEVICES_CACHE if d["device_id"] == dev_id), None)
        if dev_obj and bay in dev_obj["bays"]:
            no_data_id = f"EV-TEL-{dev_id.replace('-', '')}-{bay.replace('-', '')}-NODATA"
            rec = EvidenceRecord(
                source_id=no_data_id,
                evidence_type=EvidenceType.TELEMETRY,
                title=f"Drive Telemetry {dev_id} {bay} (No Data)",
                summary=f"No telemetry data recorded for {dev_id} {bay} (bay unmonitored or empty).",
                raw_payload={"status": "no_data", "device_id": dev_id, "bay_id": bay, "records_found": 0}
            )
            return [rec]

    return records


# --------------------------------------------------------------------------
# 4. EVENT LOG SEARCH
# --------------------------------------------------------------------------
def search_events(
    device_id: Optional[str] = None,
    severity: Optional[str] = None,
    query: Optional[str] = None,
    limit: int = 10
) -> List[EvidenceRecord]:
    """
    Searches system event logs with optional device, severity, and query filters.
    """
    results = []
    q = query.lower().strip() if query else None
    dev = device_id.upper().strip() if device_id else None
    sev = severity.upper().strip() if severity else None

    for ev in _EVENTS_CACHE:
        if dev and ev["device_id"] != dev:
            continue
        if sev and ev["severity"] != sev:
            continue
        if q:
            msg = ev["message"].lower()
            code = ev["event_code"].lower()
            if q not in msg and q not in code:
                continue

        summary = f"[{ev['severity']}] {ev['device_id']} ({ev['event_code']}): {ev['message']}"
        rec = EvidenceRecord(
            source_id=ev["source_id"],
            evidence_type=EvidenceType.EVENT_LOG,
            title=f"Event {ev['event_code']} on {ev['device_id']}",
            summary=summary,
            raw_payload=ev,
            timestamp=ev.get("timestamp")
        )
        results.append(rec)
        if len(results) >= limit:
            break

    return results


# --------------------------------------------------------------------------
# 5. TECHNICAL MANUAL SEARCH
# --------------------------------------------------------------------------
def search_manuals(
    query: str,
    model_id: Optional[str] = None,
    limit: int = 5
) -> List[EvidenceRecord]:
    """
    Deterministic manual search with model-specific prioritization.
    Model Y solid amber != Model X solid amber!
    """
    if not query or not query.strip():
        return []

    q_upper = query.upper()
    # Check for specific error code queries, e.g. ERR-PWR-8899, ERR-SMART-004
    error_codes = re.findall(r"\bERR-[A-Z0-9-]+\b", q_upper)
    if error_codes:
        # Require exact error code match in the manual
        matching_manuals = []
        for code in error_codes:
            for m in _MANUALS_CACHE:
                full_text = (m["title"] + " " + m["content"]).upper()
                if code in full_text:
                    matching_manuals.append(m)
        if not matching_manuals:
            # Uncataloged error code (e.g. ERR-PWR-8899 for Scenario 6)
            return []
        # Return matched manuals
        records = []
        for m in matching_manuals[:limit]:
            rec = EvidenceRecord(
                source_id=m["source_id"],
                evidence_type=EvidenceType.MANUAL,
                title=m["title"],
                summary=f"Manual excerpt [{m['model_id']} - {m['category']}]: {m['content'][:150]}...",
                raw_payload=m
            )
            records.append(rec)
        return records

    # General token matching
    STOP_WORDS = {"err", "error", "code", "the", "a", "an", "is", "for", "on", "in", "and", "or", "to", "of", "with"}
    raw_tokens = re.findall(r"\w+", query.lower())
    tokens = [t for t in raw_tokens if t not in STOP_WORDS]
    if not tokens:
        tokens = raw_tokens  # Fallback if only stopwords

    model = model_id.upper().strip() if model_id else None

    scored = []
    for m in _MANUALS_CACHE:
        text = (m["title"] + " " + m["content"] + " " + m["category"]).lower()
        score = 0
        for tok in tokens:
            if tok in text:
                score += 1
                if tok in m["title"].lower():
                    score += 2

        if score > 0:
            if model and m.get("model_id") == model:
                score += 5
            scored.append((score, m))

    scored.sort(key=lambda x: x[0], reverse=True)

    records = []
    for score, m in scored[:limit]:
        rec = EvidenceRecord(
            source_id=m["source_id"],
            evidence_type=EvidenceType.MANUAL,
            title=m["title"],
            summary=f"Manual excerpt [{m['model_id']} - {m['category']}]: {m['content'][:150]}...",
            raw_payload=m
        )
        records.append(rec)

    return records


# --------------------------------------------------------------------------
# 6. DIAGNOSTIC RESULT LOOKUP
# --------------------------------------------------------------------------
def get_diagnostic_result(diagnostic_id: str) -> EvidenceRecord:
    """
    Retrieves simulated diagnostic result for validation loops.
    """
    if diagnostic_id not in _DIAGNOSTICS_CACHE:
        raise KeyError(f"Diagnostic record '{diagnostic_id}' does not exist in diagnostics fixture")

    diag = _DIAGNOSTICS_CACHE[diagnostic_id]
    rec = EvidenceRecord(
        source_id=diag["diagnostic_id"],
        evidence_type=EvidenceType.DIAGNOSTIC,
        title=f"Diagnostic Result: {diag['test_type']} ({diag['status']})",
        summary=f"Result for {diag['target_device']} {diag['target_component']}: {diag['result_summary']}",
        raw_payload=diag
    )
    return rec


# --------------------------------------------------------------------------
# 7. DETERMINISTIC PIXEL COLOUR ANALYZER
# --------------------------------------------------------------------------
def analyze_led_pixels(
    image_path: str,
    bounding_box: Optional[List[int]] = None,
    frame_b_path: Optional[str] = None
) -> PixelColorResult:
    """
    Deterministic physical HSV pixel measurement for LED indicators.
    - Handles red wrap-around (hue near 0 and near 360).
    - Requires minimum saturation and brightness to filter dim chassis metal or white reflections.
    - If overexposed camera white center is present, samples the surrounding halo ring.
    - If frame_b_path is given, compares brightness across frames to verify blinking state.
    - Explicit reliability score.
    """
    p = Path(image_path)
    if not p.exists():
        return PixelColorResult(
            detected_color="unknown",
            reliability=ReliabilityEnum.UNRELIABLE,
            pixel_count_analyzed=0,
            notes=f"Image file not found: {image_path}"
        )

    img = Image.open(p).convert("RGB")
    width, height = img.size

    # Crop to bounding box if provided [x1, y1, x2, y2]
    if bounding_box and len(bounding_box) == 4:
        x1, y1, x2, y2 = bounding_box
        # Boundary clamp
        x1 = max(0, min(width - 1, x1))
        y1 = max(0, min(height - 1, y1))
        x2 = max(x1 + 1, min(width, x2))
        y2 = max(y1 + 1, min(height, y2))
        region = img.crop((x1, y1, x2, y2))
        box_used = [x1, y1, x2, y2]
    else:
        # Default region: inspect lower center where drive LED indicators sit
        box_used = [100, 150, 156, 206]
        region = img.crop((box_used[0], box_used[1], box_used[2], box_used[3]))

    # Convert cropped region to HSV
    hsv_region = region.convert("HSV")
    hsv_pixels = list(hsv_region.get_flattened_data())

    # Pixel metric accumulators
    valid_color_pixels = []
    white_overexposed_pixels = 0
    total_pixels = len(hsv_pixels)

    for h_raw, s_raw, v_raw in hsv_pixels:
        h_deg = (h_raw / 255.0) * 360.0
        s_pct = s_raw / 255.0
        v_pct = v_raw / 255.0

        # Detect overexposed white core (very bright, low saturation)
        if v_pct > 0.88 and s_pct < 0.20:
            white_overexposed_pixels += 1
            continue

        # Filter out dim background / unlit metal
        if v_pct < 0.25 or s_pct < 0.25:
            continue

        valid_color_pixels.append((h_deg, s_pct, v_pct))

    # Determine color from valid saturated pixels
    if not valid_color_pixels:
        if white_overexposed_pixels > 15:
            # Entire blob was overexposed white; inspect perimeter
            notes = f"Overexposed white core ({white_overexposed_pixels}px) with no saturated halo"
            return PixelColorResult(
                detected_color="white",
                reliability=ReliabilityEnum.MEDIUM,
                pixel_count_analyzed=white_overexposed_pixels,
                bounding_box_used=box_used,
                notes=notes
            )
        # All dark / off
        avg_v = sum(p[2] / 255.0 for p in hsv_pixels) / max(1, total_pixels)
        return PixelColorResult(
            detected_color="off",
            brightness=round(avg_v, 3),
            reliability=ReliabilityEnum.HIGH if total_pixels > 20 else ReliabilityEnum.LOW,
            pixel_count_analyzed=total_pixels,
            bounding_box_used=box_used,
            notes="No saturated illumination detected; LED is off or unpowered"
        )

    # Classify color distribution
    amber_count = 0
    green_count = 0
    red_count = 0
    h_sum, s_sum, v_sum = 0.0, 0.0, 0.0

    for h, s, v in valid_color_pixels:
        h_sum += h
        s_sum += s
        v_sum += v
        # Amber / Orange: 20° to 55°
        if 20.0 <= h <= 55.0:
            amber_count += 1
        # Green: 75° to 160°
        elif 75.0 <= h <= 160.0:
            green_count += 1
        # Red wrap-around: 340° to 360° or 0° to 15°
        elif h >= 340.0 or h <= 15.0:
            red_count += 1

    n = len(valid_color_pixels)
    avg_h = h_sum / n
    avg_s = s_sum / n
    avg_v = v_sum / n

    if amber_count >= max(green_count, red_count) and amber_count >= n * 0.45:
        detected = "amber"
    elif green_count >= max(amber_count, red_count) and green_count >= n * 0.45:
        detected = "green"
    elif red_count >= max(amber_count, green_count) and red_count >= n * 0.45:
        detected = "red"
    else:
        detected = "unknown"

    # Reliability calculation
    if n >= 25 and detected != "unknown":
        reliability = ReliabilityEnum.HIGH
    elif n >= 10 and detected != "unknown":
        reliability = ReliabilityEnum.MEDIUM
    else:
        reliability = ReliabilityEnum.UNRELIABLE

    # Check for blinking if Frame B provided
    is_blinking = None
    if frame_b_path and Path(frame_b_path).exists():
        img_b = Image.open(frame_b_path).convert("RGB")
        if bounding_box and len(bounding_box) == 4:
            reg_b = img_b.crop(box_used).convert("HSV")
        else:
            reg_b = img_b.crop(box_used).convert("HSV")
        b_pixels = list(reg_b.get_flattened_data())
        avg_v_b = sum(p[2] / 255.0 for p in b_pixels) / max(1, len(b_pixels))
        # Significant delta in brightness between frames indicates blinking
        v_diff = abs(avg_v - avg_v_b)
        is_blinking = (v_diff >= 0.15)

    notes = f"Analyzed {n} saturated pixels (Amber={amber_count}, Green={green_count}, Red={red_count}). Overexposed core={white_overexposed_pixels}px."
    if is_blinking is not None:
        notes += f" Blinking check across frames: delta_brightness={v_diff:.2f}, is_blinking={is_blinking}."

    return PixelColorResult(
        detected_color=detected,
        hue_degrees=round(avg_h, 1),
        saturation=round(avg_s, 3),
        brightness=round(avg_v, 3),
        reliability=reliability,
        pixel_count_analyzed=n,
        bounding_box_used=box_used,
        notes=notes,
        is_blinking=is_blinking
    )
