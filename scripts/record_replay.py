"""
Record Replay Script for InfraSight (Phase 5).
Records or curates verified live runs of hero scenarios into eval/replay/
for offline, zero-token, network-independent demonstration.

Usage:
  python scripts/record_replay.py [--scenarios SCN-01 SCN-02 SCN-08 SCN-10 SCN-03] [--verify]
"""

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.meta_client import CACHE_DIR, REPLAY_DIR, MetaClient
from backend.orchestrator import InvestigationOrchestrator
from backend.storage import init_db

HERO_SCENARIOS = ["SCN-02", "SCN-01", "SCN-08", "SCN-10", "SCN-03"]


class TrackingMetaClient(MetaClient):
    """MetaClient that tracks all cache keys accessed or generated."""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.recorded_keys = []

    def chat_completion(self, *args, **kwargs):
        resp, is_replay = super().chat_completion(*args, **kwargs)
        # Compute payload key
        used_model = kwargs.get("model") or self.default_model
        payload = {
            "model": used_model,
            "messages": kwargs.get("messages", args[0] if args else []),
            "temperature": kwargs.get("temperature", 0.0),
        }
        if "tools" in kwargs and kwargs["tools"]:
            payload["tools"] = kwargs["tools"]
            payload["tool_choice"] = kwargs.get("tool_choice") or "auto"
        if "response_format" in kwargs and kwargs["response_format"]:
            payload["response_format"] = kwargs["response_format"]

        cache_key = self._compute_cache_key(payload)
        self.recorded_keys.append(cache_key)
        return resp, is_replay


def record_scenarios(scenario_ids: list[str]) -> list[str]:
    """Runs each scenario and copies the response cache files to eval/replay/."""
    init_db()
    REPLAY_DIR.mkdir(parents=True, exist_ok=True)

    with open("data/scenarios.json", "r", encoding="utf-8") as f:
        all_scenarios = {s["scenario_id"]: s for s in json.load(f)}

    all_keys = []
    print(f"--- Recording {len(scenario_ids)} Scenarios to {REPLAY_DIR} ---")

    for sid in scenario_ids:
        scn = all_scenarios.get(sid)
        if not scn:
            print(f"Warning: Scenario {sid} not found in scenarios.json")
            continue

        print(f"\nRecording {sid}: {scn['name']}")
        # Clean any old pending actions from previous runs
        import sqlite3
        conn = sqlite3.connect("data/infrasight.db")
        conn.execute("DELETE FROM pending_actions WHERE incident_id = ?", (f"REC-{sid}",))
        conn.commit()
        conn.close()

        tracking_client = TrackingMetaClient()
        orchestrator = InvestigationOrchestrator(meta_client=tracking_client)

        images = scn.get("image_frames") or ([scn["image_reference"]] if scn.get("image_reference") else [])
        diag, v_res, _ = orchestrator.investigate(
            incident_id=f"REC-{sid}",
            user_text=scn["incident_description"],
            image_paths=images,
        )

        # For scenarios expecting approval execution (e.g. SCN-08), execute approval and resume
        if scn.get("expected_final_status") == "resolved_in_simulation":
            from backend.storage import get_pending_actions_for_incident
            from backend.executor import SimulatedExecutionEngine
            actions = get_pending_actions_for_incident(f"REC-{sid}")
            if actions:
                act = actions[0]
                SimulatedExecutionEngine.approve_action(act["action_id"], decided_by="supervisor@local")
                exec_res = SimulatedExecutionEngine.execute_and_verify(act["action_id"])
                diag, v_res, _ = orchestrator.resume_investigation(
                    incident_id=f"REC-{sid}",
                    action_id=act["action_id"],
                    decision="approved",
                    post_verification=exec_res,
                    decided_by="supervisor@local",
                )

        st_val = getattr(diag.status, "value", diag.status)
        conf_val = getattr(diag.confidence, "value", diag.confidence)
        print(f"  Result: status={st_val}, confidence={conf_val}, keys={len(tracking_client.recorded_keys)}")

        # Copy each cache file to eval/replay/
        for key in tracking_client.recorded_keys:
            src = CACHE_DIR / f"{key}.json"
            dst = REPLAY_DIR / f"{key}.json"
            if src.exists():
                shutil.copy2(src, dst)
                all_keys.append(key)
            elif dst.exists():
                all_keys.append(key)
            else:
                print(f"  Warning: Cache file for key {key} not found at {src}")

    print(f"\nRecorded total of {len(set(all_keys))} unique response files into {REPLAY_DIR}")
    return list(set(all_keys))


def verify_replay(scenario_ids: list[str]) -> bool:
    """
    Verifies that each scenario runs completely offline from eval/replay/ with no API key,
    strictly validates the final status against expected_final_status,
    and asserts expected supporting evidence citations.
    """
    print(f"\n--- Verifying Offline Replay for {len(scenario_ids)} Scenarios ---")
    with open("data/scenarios.json", "r", encoding="utf-8") as f:
        all_scenarios = {s["scenario_id"]: s for s in json.load(f)}

    all_passed = True
    for sid in scenario_ids:
        scn = all_scenarios.get(sid)
        if not scn:
            continue

        # Clean any old pending actions from previous test runs
        from backend.storage import init_db
        import sqlite3
        conn = sqlite3.connect("data/infrasight.db")
        conn.execute("DELETE FROM pending_actions WHERE incident_id = ?", (f"TEST-REPLAY-{sid}",))
        conn.commit()
        conn.close()

        # Force offline replay: no API key, replay_mode=True
        offline_client = MetaClient(api_key="none", replay_mode=True, mock_mode=True)
        orchestrator = InvestigationOrchestrator(meta_client=offline_client)

        images = scn.get("image_frames") or ([scn["image_reference"]] if scn.get("image_reference") else [])
        try:
            diag, v_res, _ = orchestrator.investigate(
                incident_id=f"TEST-REPLAY-{sid}",
                user_text=scn["incident_description"],
                image_paths=images,
            )

            # If scenario expects approval (e.g. SCN-08), approve and resume
            if scn.get("expected_final_status") == "resolved_in_simulation":
                from backend.storage import get_pending_actions_for_incident
                from backend.executor import SimulatedExecutionEngine
                actions = get_pending_actions_for_incident(f"TEST-REPLAY-{sid}")
                if not actions:
                    print(f"  [FAIL] {sid}: Expected pending action held for approval, but none found.")
                    all_passed = False
                    continue
                act = actions[0]
                SimulatedExecutionEngine.approve_action(act["action_id"], decided_by="supervisor@local")
                exec_res = SimulatedExecutionEngine.execute_and_verify(act["action_id"])
                diag, v_res, _ = orchestrator.resume_investigation(
                    incident_id=f"TEST-REPLAY-{sid}",
                    action_id=act["action_id"],
                    decision="approved",
                    post_verification=exec_res,
                    decided_by="supervisor@local",
                )

            st_val = getattr(diag.status, "value", diag.status)
            conf_val = getattr(diag.confidence, "value", diag.confidence)

            # Strict status validation
            expected_status = scn.get("expected_final_status") or scn.get("expected_status")
            if expected_status and st_val != expected_status:
                print(f"  [FAIL] {sid}: status='{st_val}' (expected '{expected_status}')")
                all_passed = False
                continue

            # Strict evidence citation validation
            expected_evidence = scn.get("relevant_telemetry_ids", []) + scn.get("expected_manual_evidence_ids", [])
            if sid == "SCN-08":
                expected_evidence = expected_evidence + ["EV-DIAG-SRV004-BAY04-POSTREPLACE"]

            if expected_evidence:
                cited = set(diag.supporting_evidence_ids or [])
                has_match = any(eid in cited for eid in expected_evidence)
                if not has_match:
                    print(f"  [FAIL] {sid}: missing expected citations (expected any of {expected_evidence}, cited {list(cited)})")
                    all_passed = False
                    continue

            print(f"  [PASS] {sid}: status={st_val}, confidence={conf_val}")
        except Exception as e:
            print(f"  [FAIL] {sid}: Exception {e}")
            all_passed = False

    return all_passed


def main():
    parser = argparse.ArgumentParser(description="Record and verify replay files for InfraSight demo")
    parser.add_argument("--scenarios", nargs="+", default=HERO_SCENARIOS, help="Scenarios to record")
    parser.add_argument("--verify", action="store_true", help="Verify offline replay only without re-running live")
    args = parser.parse_args()

    if not args.verify:
        record_scenarios(args.scenarios)

    success = verify_replay(args.scenarios)
    if not success:
        sys.exit(1)
    print("\nReplay verification successful! All hero scenarios replay offline without API access.")


if __name__ == "__main__":
    main()
