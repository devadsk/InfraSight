"""
Live API Check on Scenario 1 and Scenario 2 (Phase 3 Part B).
Runs Muse Spark 1.3 live through the complete Investigation Orchestrator.
Saves full transcripts and usage records in eval/transcripts/.
"""

import json
import os
import sys
import time
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.meta_client import MetaClient
from backend.orchestrator import InvestigationOrchestrator
from backend.storage import get_incident_audit_trail, get_db_connection

load_dotenv()

TRANSCRIPTS_DIR = Path("eval/transcripts")
TRANSCRIPTS_DIR.mkdir(parents=True, exist_ok=True)


def run_scenario(scenario_id: str, desc: str, image_path: str = None):
    print(f"\n==================================================")
    print(f"  RUNNING LIVE INVESTIGATION: {scenario_id}")
    print(f"==================================================")
    print(f"Description: {desc}")
    print(f"Image: {image_path}")

    # Use live client with MOCK_MODE=False
    client = MetaClient(mock_mode=False)
    orchestrator = InvestigationOrchestrator(meta_client=client, max_steps=6)

    t0 = time.time()
    images = [image_path] if image_path else []
    diagnosis, verification, _ = orchestrator.investigate(
        incident_id=scenario_id,
        user_text=desc,
        image_paths=images,
    )
    elapsed = time.time() - t0

    # Retrieve audit trail from SQLite
    trail = get_incident_audit_trail(scenario_id)

    # Retrieve usage ledger for this scenario
    conn = get_db_connection()
    cursor = conn.execute("""
        SELECT purpose, model_id, reasoning_effort, prompt_tokens, completion_tokens, cached_tokens, total_tokens, estimated_cost_usd, latency_s, is_replay
        FROM usage_ledger
        WHERE incident_id = ?
        ORDER BY call_id ASC;
    """, (scenario_id,))
    usage_records = [dict(r) for r in cursor.fetchall()]
    conn.close()

    total_tokens = sum(u.get("total_tokens", 0) for u in usage_records)
    total_cost = sum(u.get("estimated_cost_usd", 0.0) for u in usage_records)
    steps_count = sum(1 for e in trail if e["event_type"] == "tool_call")

    transcript = {
        "scenario_id": scenario_id,
        "incident_description": desc,
        "image_path": image_path,
        "elapsed_seconds": round(elapsed, 2),
        "total_steps": steps_count,
        "total_tokens": total_tokens,
        "total_cost_usd": round(total_cost, 6),
        "final_diagnosis": diagnosis.model_dump(),
        "verification": verification.to_dict(),
        "audit_events": trail,
        "usage_ledger": usage_records,
    }

    transcript_file = TRANSCRIPTS_DIR / f"{scenario_id}_transcript.json"
    with open(transcript_file, "w", encoding="utf-8") as f:
        json.dump(transcript, f, indent=2)

    print(f"\nCompleted in {elapsed:.2f}s | Steps: {steps_count} | Tokens: {total_tokens} | Cost: ${total_cost:.5f}")
    print(f"Final Status: {diagnosis.status.value} (Confidence: {diagnosis.confidence})")
    print(f"Verified: {verification.is_valid} (Downgraded: {verification.downgraded})")
    print(f"Summary: {diagnosis.summary}")
    print(f"Saved transcript to {transcript_file}")

    return transcript


def main():
    # Load scenarios
    with open("data/scenarios.json", "r", encoding="utf-8") as f:
        scenarios = json.load(f)

    scenarios_by_id = {s["scenario_id"]: s for s in scenarios}

    s1 = scenarios_by_id["SCN-01"]
    s2 = scenarios_by_id["SCN-02"]

    t1 = run_scenario(
        scenario_id="SCN-01",
        desc=s1["incident_description"],
        image_path=s1.get("image_reference")
    )

    t2 = run_scenario(
        scenario_id="SCN-02",
        desc=s2["incident_description"],
        image_path=s2.get("image_reference")
    )

    print("\n==================================================")
    print("  LIVE EVALUATION COMPLETE")
    print("==================================================")
    print(f"SCN-01: Status={t1['final_diagnosis']['status']} | Steps={t1['total_steps']} | Cost=${t1['total_cost_usd']:.4f}")
    print(f"SCN-02: Status={t2['final_diagnosis']['status']} | Steps={t2['total_steps']} | Cost=${t2['total_cost_usd']:.4f}")


if __name__ == "__main__":
    main()
