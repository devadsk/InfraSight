"""
Incident Report Generator for InfraSight (Phase 5).
Generates comprehensive Markdown post-incident audit reports adhering to Master Spec Step 9.
Clearly marked as synthetic/simulated.
"""

import json
from typing import Any, Dict, List, Optional
from backend.storage import (
    get_incident,
    get_incident_audit_trail,
    get_incident_state,
    get_incident_usage,
    get_pending_actions_for_incident,
)


def generate_incident_markdown_report(incident_id: str) -> str:
    """
    Generates a full Markdown audit report for an incident:
    1. Incident Overview & Simulated Environment Notice
    2. Device & Hardware Identity
    3. Multimodal Physical Perception (Pixel vs Vision)
    4. Technical Evidence Registry (Telemetry, Logs, Manuals)
    5. Diagnostic Findings & Verifier Corroboration
    6. Safety Policy & Action Execution History
    7. Read-Back Verification Audit
    8. LLM Resource & Token Cost Ledger
    9. Complete Chronological Audit Timeline
    """
    inc = get_incident(incident_id)
    if not inc:
        return f"# Error: Incident '{incident_id}' not found."

    audit_trail = get_incident_audit_trail(incident_id)
    pending_actions = get_pending_actions_for_incident(incident_id)
    usage = get_incident_usage(incident_id)
    diag = inc.get("raw_diagnosis") or {}

    status = inc.get("final_status", "unknown").upper()
    confidence = inc.get("confidence", "unknown").upper()
    device_id = inc.get("device_id") or "UNKNOWN"
    bay_id = inc.get("bay_id") or "N/A"
    created_at = inc.get("created_at") or "Unknown"
    mode = (inc.get("mode") or "live").upper()

    md = []

    # 1. Title & Header
    md.append(f"# InfraSight Incident Report: {incident_id}")
    md.append("")
    md.append("> **Simulated Environment Notice:** All devices, telemetry readings, kernel event logs, and vendor manuals are synthetic data generated for testing and demonstration purposes.")
    md.append("")
    md.append(f"**Execution Mode:** `{mode}` | **Final Status:** `{status}` | **Confidence:** `{confidence}` | **Recorded:** `{created_at}`")
    md.append("")
    md.append("---")
    md.append("")

    # 2. Executive Summary
    md.append("## 1. Executive Summary")
    md.append("")
    md.append(f"**User Reported Incident:**")
    md.append(f"> {inc.get('user_text', 'No user text recorded.')}")
    md.append("")
    md.append(f"**Diagnostic Summary:**")
    md.append(f"> {inc.get('summary', 'Investigation in progress or inconclusive.')}")
    md.append("")
    if diag.get("recommended_action"):
        md.append(f"**Recommended Next Step:** {diag.get('recommended_action')}")
        md.append("")

    # 3. Hardware Identity & Scope
    md.append("## 2. Hardware Identity & Scope Resolution")
    md.append("")
    md.append(f"| Property | Value |")
    md.append(f"|---|---|")
    md.append(f"| **Target Chassis ID** | `{device_id}` |")
    md.append(f"| **Drive Bay Component** | `{bay_id}` |")
    md.append(f"| **Associated Images** | {len(inc.get('image_paths', []))} frame(s) analyzed |")
    md.append("")

    # 4. Perception & Visual Analysis
    md.append("## 3. Multimodal Physical Perception")
    md.append("")
    perception_events = [e for e in audit_trail if e.get("event_type") == "perception_completed"]
    if perception_events:
        details = perception_events[0].get("details", {})
        obs = details.get("observations", [])
        if obs:
            md.append("| Frame Index | Source | Visual Indication | Confidence / State |")
            md.append("|---|---|---|---|")
            for o in obs:
                src = o.get("source", "sensor")
                color = o.get("detected_color", "unknown")
                pattern = o.get("pattern", "solid")
                dev = o.get("device_label", device_id)
                md.append(f"| Frame | `{src}` | `{color.upper()} ({pattern})` | Device `{dev}` |")
            md.append("")
        else:
            md.append("*No visual indicators detected in uploaded frames.*")
            md.append("")
    else:
        md.append("*Direct telemetry inquiry (no image frames uploaded).*")
        md.append("")

    # 5. Evidence Registry
    md.append("## 4. Authoritative Evidence Registry")
    md.append("")
    supporting = diag.get("supporting_evidence_ids", [])
    contradicting = diag.get("contradictory_evidence_ids", [])

    if supporting:
        md.append(f"**Supporting Evidence Cited ({len(supporting)}):**")
        for eid in supporting:
            md.append(f"- `[{eid}]`")
        md.append("")

    if contradicting:
        md.append(f"**Contradictory / Refuting Evidence Cited ({len(contradicting)}):**")
        for eid in contradicting:
            md.append(f"- `[{eid}]` *(refutes alternative fault hypotheses)*")
        md.append("")

    if diag.get("missing_information"):
        md.append(f"**Missing Information / Unperformed Discriminating Tests:**")
        md.append(f"> {diag.get('missing_information')}")
        md.append("")

    # 6. Safety Policy & Action History
    md.append("## 5. Security Policy & Action Governance")
    md.append("")
    if pending_actions:
        md.append("| Action ID | Tool / Action | Arguments | Status | Decided By | Executed Result |")
        md.append("|---|---|---|---|---|---|")
        for pa in pending_actions:
            aid = pa.get("action_id")
            tool = pa.get("tool")
            args = pa.get("canonical_args", "{}")
            st = pa.get("status", "unknown").upper()
            decider = pa.get("decided_by") or "Pending"
            res = pa.get("result_ref") or "None"
            md.append(f"| `{aid}` | `{tool}` | `{args}` | `{st}` | `{decider}` | `{res}` |")
        md.append("")
    else:
        md.append("*No consequential mutations proposed. Investigation strictly non-destructive (Class A read-only).*")
        md.append("")

    # 7. Model Activity & Token Accounting
    md.append("## 6. Meta Model Resource & Cost Ledger")
    md.append("")
    calls = usage.get("calls", [])
    if calls:
        md.append("| Purpose | Model ID | Latency | Tokens | Cost (USD) | Replay |")
        md.append("|---|---|:---:|:---:|:---:|:---:|")
        for c in calls:
            p = c.get("purpose")
            mid = c.get("model_id")
            lat = f"{c.get('latency_s', 0.0):.2f}s"
            tok = f"{c.get('total_tokens', 0):,}"
            cost = f"${c.get('estimated_cost_usd', 0.0):.4f}"
            rep = "YES" if c.get("is_replay") else "NO"
            md.append(f"| `{p}` | `{mid}` | {lat} | {tok} | {cost} | {rep} |")
        md.append("")
        md.append(f"**Incident Cumulative Resource Usage:** `{usage.get('total_tokens', 0):,}` tokens | **Total Cost:** `${usage.get('total_cost_usd', 0.0):.4f} USD`")
        md.append("")

    # 8. Complete Audit Trail
    md.append("## 7. Chronological Audit Trail")
    md.append("")
    if audit_trail:
        md.append("| Step | Timestamp | Event Type | Details Summary |")
        md.append("|:---:|---|---|---|")
        for ev in audit_trail:
            st_num = ev.get("step_number", 0)
            ts = ev.get("timestamp", "")
            etype = ev.get("event_type", "")
            det = json.dumps(ev.get("details", {}))
            det_summary = det[:80] + ("..." if len(det) > 80 else "")
            md.append(f"| {st_num} | `{ts}` | `{etype}` | `{det_summary}` |")
        md.append("")

    md.append("---")
    md.append("*Generated automatically by InfraSight Evidence-First Diagnostic Engine.*")

    return "\n".join(md)
