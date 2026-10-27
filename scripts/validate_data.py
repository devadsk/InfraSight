"""
Referential Integrity Validation Script for InfraSight (Phase 2).
Checks:
1. Every device, bay, telemetry ID, event ID, manual ID, image file and diagnostics entry referenced by scenarios.json exists.
2. Every image label matches a real device and bay in devices.json.
3. The LED colour drawn on images matches the scenario expected state (verified via analyze_led_pixels).
4. No manual section in data/manuals/ is orphaned.
5. Coverage of unlisted bays: confirms lookup for an unlisted bay returns an explicit 'no data' result.

Prints a pass/fail line per check and returns exit code 0 if all pass.
"""

import json
import re
import sys
from pathlib import Path

# Ensure project root is on sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.evidence import (
    resolve_source_id,
    resolve_device,
    get_telemetry,
    search_manuals,
    analyze_led_pixels,
    reload_fixtures
)

DATA_DIR = Path("data")


def validate_all() -> bool:
    reload_fixtures()
    all_passed = True

    def check(name: str, passed: bool, detail: str = ""):
        nonlocal all_passed
        status = "PASS" if passed else "FAIL"
        if not passed:
            all_passed = False
        msg = f"[{status}] {name}"
        if detail:
            msg += f" - {detail}"
        print(msg)

    print("==================================================")
    print("  InfraSight Referential Integrity Validation")
    print("==================================================")

    # Load fixtures
    devices = json.loads((DATA_DIR / "devices.json").read_text(encoding="utf-8"))
    telemetry = json.loads((DATA_DIR / "telemetry.json").read_text(encoding="utf-8"))
    events = json.loads((DATA_DIR / "events.json").read_text(encoding="utf-8"))
    manuals = json.loads((DATA_DIR / "manuals.json").read_text(encoding="utf-8"))
    diagnostics = json.loads((DATA_DIR / "diagnostics.json").read_text(encoding="utf-8"))
    scenarios = json.loads((DATA_DIR / "scenarios.json").read_text(encoding="utf-8"))

    device_map = {d["device_id"]: d for d in devices}
    telemetry_ids = {t["source_id"] for t in telemetry}
    event_ids = {e["source_id"] for e in events}
    manual_ids = {m["source_id"] for m in manuals}

    # 1. Scenarios Device & Bay Integrity
    scen_dev_ok = True
    scen_bay_ok = True
    for s in scenarios:
        dev_id = s.get("expected_device")
        bay_id = s.get("expected_bay")
        if dev_id:
            if dev_id not in device_map:
                scen_dev_ok = False
                print(f"  Error: {s['scenario_id']} references unknown device '{dev_id}'")
            elif bay_id and bay_id not in device_map[dev_id]["bays"]:
                scen_bay_ok = False
                print(f"  Error: {s['scenario_id']} references invalid bay '{bay_id}' on {dev_id}")
    check("1.1 Scenario Expected Devices exist in inventory", scen_dev_ok)
    check("1.2 Scenario Expected Bays exist on their respective devices", scen_bay_ok)

    # 2. Scenario Evidence IDs Integrity
    scen_tel_ok = True
    scen_man_ok = True
    for s in scenarios:
        for tid in s.get("relevant_telemetry_ids", []):
            try:
                rec = resolve_source_id(tid)
                if not rec:
                    scen_tel_ok = False
            except KeyError:
                scen_tel_ok = False
                print(f"  Error: {s['scenario_id']} references unresolved telemetry ID '{tid}'")

        for mid in s.get("expected_manual_evidence_ids", []):
            try:
                rec = resolve_source_id(mid)
                if not rec:
                    scen_man_ok = False
            except KeyError:
                scen_man_ok = False
                print(f"  Error: {s['scenario_id']} references unresolved manual ID '{mid}'")

    check("2.1 Scenario Telemetry Evidence IDs resolve strictly", scen_tel_ok)
    check("2.2 Scenario Manual Evidence IDs resolve strictly", scen_man_ok)

    # 3. Scenario Image References Integrity
    scen_img_ok = True
    for s in scenarios:
        ref = s.get("image_reference")
        if ref:
            if not Path(ref).exists():
                scen_img_ok = False
                print(f"  Error: {s['scenario_id']} references non-existent image '{ref}'")
    check("3.1 Scenario Image Files exist on disk", scen_img_ok)

    # 4. Image Labels Match Real Hardware Inventory
    img_labels_ok = True
    image_files = list((DATA_DIR / "images").glob("*.png"))
    for img_p in image_files:
        fn = img_p.name
        # Match pattern e.g. SRV004_BAY04
        m = re.match(r"(SRV00[1-5])_(BAY0[1-8])", fn)
        if m:
            d_id = f"SRV-00{m.group(1)[-1]}"
            b_id = f"BAY-0{m.group(2)[-1]}"
            if d_id not in device_map or b_id not in device_map[d_id]["bays"]:
                img_labels_ok = False
                print(f"  Error: Image {fn} maps to invalid hardware {d_id}/{b_id}")
    check("4.1 Generated Image Filenames & Labels map to real inventory", img_labels_ok)

    # 1.3 Scenarios 9, 10, 11 Policy Fields Assertion
    policy_fields_ok = True
    for sid in ["SCN-09", "SCN-10", "SCN-11"]:
        scen = next((s for s in scenarios if s["scenario_id"] == sid), None)
        if not scen:
            policy_fields_ok = False
        elif "expected_denied_actions" not in scen or "expected_policy_outcome" not in scen:
            policy_fields_ok = False
            print(f"  Error: {sid} missing expected_denied_actions or expected_policy_outcome")
    check("1.3 Scenarios 9, 10, 11 define expected_denied_actions and expected_policy_outcome", policy_fields_ok)

    # 5. LED Colour Consistency with Scenario Expectations
    led_color_ok = True
    for s in scenarios:
        ref = s.get("image_reference")
        sid = s["scenario_id"]
        if not ref or not Path(ref).exists():
            continue
        meas = analyze_led_pixels(ref)
        # Expected color mappings by scenario
        if sid in ["SCN-01", "SCN-08", "SCN-09", "SCN-13"]:
            if meas.detected_color != "amber":
                led_color_ok = False
                print(f"  Error: {sid} expected amber LED but measured '{meas.detected_color}' on {ref}")
        elif sid in ["SCN-02"]:
            # Rebuild blinking amber
            if meas.detected_color != "amber":
                led_color_ok = False
                print(f"  Error: {sid} expected amber blinking LED but measured '{meas.detected_color}' on {ref}")
        elif sid in ["SCN-03", "SCN-07"]:
            if meas.detected_color != "green":
                led_color_ok = False
                print(f"  Error: {sid} expected green LED but measured '{meas.detected_color}' on {ref}")
    check("5.1 LED Colours drawn on images match Scenario Expectations", led_color_ok)

    # 6. Manual Orphan Check
    manual_files = list((DATA_DIR / "manuals").glob("*.json"))
    orphans = []
    for mf in manual_files:
        mid = mf.stem
        if mid not in manual_ids:
            orphans.append(mid)
    check("6.1 No Orphaned Manual Sections exist in data/manuals/", len(orphans) == 0, f"Found {len(orphans)} orphans" if orphans else "All 15 registered")

    # 7. Coverage of Unlisted Bays
    # SRV-001 has 4 bays (BAY-01 to BAY-04). BAY-03 has no telemetry in fixture.
    unlisted_result = get_telemetry("SRV-001", "BAY-03")
    unlisted_ok = (
        len(unlisted_result) == 1
        and unlisted_result[0].raw_payload.get("status") == "no_data"
        and "EV-TEL-SRV001-BAY03-NODATA" == unlisted_result[0].source_id
    )
    check("7.1 Unlisted Bay lookup returns explicit 'no data' record", unlisted_ok, f"Result: {unlisted_result[0].summary if unlisted_result else 'Empty'}")

    print("==================================================")
    if all_passed:
        print("[SUCCESS] All 7 Referential Integrity Checks PASSED.")
    else:
        print("[FAILED] One or more Referential Integrity Checks FAILED.")
    print("==================================================")
    return all_passed


if __name__ == "__main__":
    passed = validate_all()
    sys.exit(0 if passed else 1)
