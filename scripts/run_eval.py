"""
InfraSight Evaluation Driver (Phase 4).
Runs all 13 evaluation scenarios through the full FastAPI REST workflow:
- Ingests incident with description and images
- Triggers investigation loop
- Exercises supervisor approval or rejection endpoints where required
- Measures device resolution, final status, evidence grounding, and policy adherence
- Generates eval/results.json with k/13 headline metrics
"""

import argparse
import io
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient

from backend.main import app
from backend.storage import get_db_connection


def run_scenario(
    client: TestClient,
    scenario: Dict[str, Any],
    is_live: bool = False,
) -> Dict[str, Any]:
    scenario_id = scenario["scenario_id"]
    desc = scenario["incident_description"]
    expected_status = scenario.get("expected_final_status")
    expected_device = scenario.get("expected_device")
    expected_bay = scenario.get("expected_bay")
    expected_evidence = scenario.get("relevant_telemetry_ids", []) + scenario.get("expected_manual_evidence_ids", [])
    denied_actions = scenario.get("actions_must_be_denied", [])

    # 1. Prepare Images
    image_paths = scenario.get("image_frames") or []
    if not image_paths and scenario.get("image_reference"):
        image_paths = [scenario["image_reference"]]

    files = []
    for p in image_paths:
        path_obj = Path(p)
        if path_obj.exists():
            mime = "image/png" if path_obj.suffix.lower() == ".png" else "image/jpeg"
            with open(path_obj, "rb") as f:
                files.append(("images", (path_obj.name, f.read(), mime)))

    # 2. Ingest Incident via POST /incidents
    t0 = time.time()
    create_resp = client.post(
        "/incidents",
        data={"description": desc},
        files=files if files else None,
    )
    if create_resp.status_code != 201:
        return {
            "scenario_id": scenario_id,
            "error": f"Failed to create incident: {create_resp.text}",
            "status_correct": False,
            "device_correct": False,
            "evidence_correct": False,
            "policy_correct": False,
        }

    inc_data = create_resp.json()
    incident_id = inc_data["incident_id"]

    # 3. Trigger Investigation via POST /incidents/{id}/investigate?sync=true
    mode_str = "live" if is_live else "replay"
    inv_resp = client.post(f"/incidents/{incident_id}/investigate?sync=true&mode={mode_str}")
    inv_data = inv_resp.json()

    # 4. Handle Pending Actions (Approval / Rejection workflows)
    details_resp = client.get(f"/incidents/{incident_id}")
    details = details_resp.json()
    pending_actions = details.get("pending_actions", [])

    if scenario_id == "SCN-08":
        # SCN-08: Technician requests drive replacement, supervisor grants approval via API
        if pending_actions:
            act_id = pending_actions[0]["action_id"]
            appr_resp = client.post(f"/actions/{act_id}/approve", json={"decided_by": "supervisor@datacenter"})
            if appr_resp.status_code != 200:
                print(f"[{scenario_id}] Approval endpoint error: {appr_resp.text}")

    elif scenario_id == "SCN-09":
        # SCN-09: Supervisor explicitly rejects the action approval request via API
        if pending_actions:
            act_id = pending_actions[0]["action_id"]
            rej_resp = client.post(f"/actions/{act_id}/reject", json={"decided_by": "supervisor@datacenter"})
            if rej_resp.status_code != 200:
                print(f"[{scenario_id}] Rejection endpoint error: {rej_resp.text}")

    # 5. Retrieve Final Incident State and Audit Log
    final_resp = client.get(f"/incidents/{incident_id}")
    final_data = final_resp.json()
    audit_resp = client.get(f"/incidents/{incident_id}/audit")
    audit_data = audit_resp.json()

    latency_total = time.time() - t0

    # 6. Extract Metrics & Tool Sequences
    actual_status = final_data.get("status")
    actual_device = final_data.get("device_id")
    actual_bay = final_data.get("bay_id")
    diagnosis = final_data.get("diagnosis", {})
    cited_ids = diagnosis.get("supporting_evidence_ids", [])

    audit_trail = audit_data.get("audit_trail", [])
    tool_sequence = []
    executed_actions = []
    denied_tools = []

    for event in audit_trail:
        etype = event.get("event_type")
        details_e = event.get("details", {})
        if etype == "tool_call":
            tool_sequence.append(details_e.get("tool"))
        elif etype == "execution_started":
            executed_actions.append(details_e.get("tool"))
        elif etype == "security_violation" or etype == "policy_check":
            if not details_e.get("allowed"):
                denied_tools.append(details_e.get("action_name") or details_e.get("tool"))

    # 7. Query Usage Ledger
    conn = get_db_connection()
    cursor = conn.execute("""
        SELECT SUM(total_tokens) as total_tokens,
               SUM(estimated_cost_usd) as total_cost,
               COUNT(*) as call_count
        FROM usage_ledger
        WHERE incident_id = ?;
    """, (incident_id,))
    row = cursor.fetchone()
    conn.close()

    total_tokens = row["total_tokens"] or 0
    total_cost = row["total_cost"] or 0.0

    # 8. Compute Correctness Assertions
    # Device correctness
    if expected_device is None:
        device_correct = actual_device in [None, "UNKNOWN", ""]
    else:
        device_correct = (actual_device == expected_device)

    # Status correctness
    status_correct = (actual_status == expected_status)

    # Evidence correctness: at least one expected evidence ID cited, or expected is empty
    if not expected_evidence:
        evidence_correct = True
    else:
        evidence_correct = any(eid in cited_ids for eid in expected_evidence)

    # Policy correctness: no denied actions were executed
    policy_correct = True
    for da in denied_actions:
        if da in executed_actions:
            policy_correct = False

    return {
        "scenario_id": scenario_id,
        "name": scenario["name"],
        "expected_status": expected_status,
        "actual_status": actual_status,
        "status_correct": status_correct,
        "expected_device": expected_device,
        "actual_device": actual_device,
        "device_correct": device_correct,
        "expected_evidence": expected_evidence,
        "cited_evidence": cited_ids,
        "evidence_correct": evidence_correct,
        "policy_correct": policy_correct,
        "tool_sequence": tool_sequence,
        "executed_actions": executed_actions,
        "steps": len(tool_sequence),
        "total_tokens": total_tokens,
        "estimated_cost_usd": total_cost,
        "latency_s": round(latency_total, 2),
        "incident_id": incident_id,
    }


def main():
    parser = argparse.ArgumentParser(description="InfraSight Phase 4 Evaluation Runner")
    parser.add_argument("--live", action="store_true", help="Run against live Meta Model API")
    parser.add_argument("--replay", action="store_true", help="Run in replay/cache mode")
    parser.add_argument("--scenario", type=str, default=None, help="Filter to single scenario ID (e.g. SCN-08)")
    args = parser.parse_args()

    is_live = args.live

    scenarios_path = Path("data/scenarios.json")
    if not scenarios_path.exists():
        print("Error: data/scenarios.json not found.")
        sys.exit(1)

    with open(scenarios_path, "r", encoding="utf-8") as f:
        scenarios = json.load(f)

    if args.scenario:
        scenarios = [s for s in scenarios if s.get("scenario_id") == args.scenario]
        if not scenarios:
            print(f"Error: Scenario '{args.scenario}' not found.")
            sys.exit(1)

    client = TestClient(app)
    results = []

    print("=" * 105)
    mode_label = "LIVE META MODEL API" if is_live else "CACHED / REPLAY MODE"
    print(f"STARTING INFRASIGHT EVALUATION ({mode_label}) — simulated environment")
    print("=" * 105)

    for scn in scenarios:
        sid = scn["scenario_id"]
        sname = scn["name"]
        print(f"Running {sid}: {sname}...", flush=True)
        res = run_scenario(client, scn, is_live=is_live)
        results.append(res)
        status_sym = "PASS" if res.get("status_correct") else "FAIL"
        print(f"  -> Outcome: {res.get('actual_status')} (Expected: {res.get('expected_status')}) [{status_sym}]")

    # Save results to eval/results.json
    eval_dir = Path("eval")
    eval_dir.mkdir(parents=True, exist_ok=True)
    results_file = eval_dir / "results.json"
    with open(results_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    # Print Summary Table
    total = len(results)
    k_device = sum(1 for r in results if r.get("device_correct"))
    k_status = sum(1 for r in results if r.get("status_correct"))
    k_evidence = sum(1 for r in results if r.get("evidence_correct"))
    k_policy = sum(1 for r in results if r.get("policy_correct"))
    total_tokens = sum(r.get("total_tokens", 0) for r in results)
    total_cost = sum(r.get("estimated_cost_usd", 0.0) for r in results)

    print("\n" + "=" * 105)
    print("INFRASIGHT EVALUATION RESULTS (simulated environment)")
    print("=" * 105)
    print(f"{'Scenario':<8} | {'Expected Status':<25} | {'Actual Status':<25} | {'Device':<6} | {'Evid':<5} | {'Policy':<6} | {'Cost ($)':<8}")
    print("-" * 105)

    for r in results:
        sid = r["scenario_id"]
        exp_st = str(r.get("expected_status"))[:25]
        act_st = str(r.get("actual_status"))[:25]
        dev_str = "OK" if r.get("device_correct") else "FAIL"
        ev_str = "OK" if r.get("evidence_correct") else "FAIL"
        pol_str = "OK" if r.get("policy_correct") else "FAIL"
        cost_str = f"${r.get('estimated_cost_usd', 0.0):.4f}"
        print(f"{sid:<8} | {exp_st:<25} | {act_st:<25} | {dev_str:<6} | {ev_str:<5} | {pol_str:<6} | {cost_str:<8}")

    print("=" * 105)
    print(f"HEADLINE METRICS ({total} scenarios evaluated):")
    print(f"- Device Resolution:   {k_device}/{total}")
    print(f"- Final Status:        {k_status}/{total}")
    print(f"- Evidence Grounding:  {k_evidence}/{total}")
    print(f"- Policy Adherence:    {k_policy}/{total}")
    print(f"- Total Tokens Used:   {total_tokens:,}")
    print(f"- Total Run Cost:      ${total_cost:.4f}")
    print("=" * 105)


if __name__ == "__main__":
    main()
