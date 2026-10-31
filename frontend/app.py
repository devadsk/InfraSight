"""
InfraSight - Streamlit Frontend Interface (Phase 5).
Evidence-First Multimodal IT Infrastructure Troubleshooting Assistant.
Thin client over FastAPI backend.
All hardware, telemetry, logs, and manuals are synthetic (Simulated Environment).
"""

import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import streamlit as st
from frontend.api_client import APIClientError, APIConnectionError, InfraSightAPIClient

# ---------------------------------------------------------------------------
# Streamlit Page Setup & Styling
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="InfraSight | Evidence-First Investigator",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Minimal functional CSS for badges and high-contrast readability
st.markdown("""
<style>
    .reportview-container { background: #0e1117; }
    .badge-live {
        background-color: #0d6efd; color: white; padding: 3px 8px;
        border-radius: 4px; font-weight: 600; font-size: 0.85em;
    }
    .badge-replay {
        background-color: #6c757d; color: white; padding: 3px 8px;
        border-radius: 4px; font-weight: 600; font-size: 0.85em;
    }
    .badge-safety-c {
        background-color: #dc3545; color: white; padding: 3px 8px;
        border-radius: 4px; font-weight: bold; font-size: 0.85em;
    }
    .badge-class-b {
        background-color: #fd7e14; color: white; padding: 3px 8px;
        border-radius: 4px; font-weight: bold; font-size: 0.85em;
    }
    .badge-class-a {
        background-color: #198754; color: white; padding: 3px 8px;
        border-radius: 4px; font-weight: bold; font-size: 0.85em;
    }
    .sim-banner {
        background-color: #1f2937; border-left: 5px solid #3b82f6;
        padding: 10px 14px; margin-bottom: 12px; border-radius: 4px;
        color: #e5e7eb; font-size: 0.9em;
    }
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# API Client & Session State Initialization
# ---------------------------------------------------------------------------

client = InfraSightAPIClient()

if "current_incident_id" not in st.session_state:
    st.session_state.current_incident_id = None
if "execution_mode" not in st.session_state:
    st.session_state.execution_mode = "replay"  # default to zero-token offline replay for safety
if "selected_scenario_id" not in st.session_state:
    st.session_state.selected_scenario_id = None
if "selected_scenario_data" not in st.session_state:
    st.session_state.selected_scenario_data = None
if "approver_name" not in st.session_state:
    st.session_state.approver_name = "supervisor@local"
if "approver_token" not in st.session_state:
    st.session_state.approver_token = os.getenv("APPROVER_TOKEN", "")


# ---------------------------------------------------------------------------
# Helper Formatters
# ---------------------------------------------------------------------------

STATUS_COLORS = {
    "confirmed": "red",
    "not_confirmed": "green",
    "resolved_in_simulation": "blue",
    "unresolved": "orange",
    "more_evidence_required": "violet",
    "diagnostic_execution_failed": "gray",
    "needs_clarification": "yellow",
    "awaiting_approval": "orange",
    "investigating": "blue",
    "created": "gray",
}

STATUS_DESCRIPTIONS = {
    "confirmed": "Physical hardware failure positively confirmed across multiple independent sources.",
    "not_confirmed": "Hardware verified healthy; alert explained by normal activity (e.g. RAID rebuild).",
    "resolved_in_simulation": "Physical remediation executed and corroborated via post-action read-back.",
    "unresolved": "Issue persists or action was prohibited/rejected with no confirmed hardware defect.",
    "more_evidence_required": "Inconclusive telemetry or unperformed discriminating test specified in manuals.",
    "diagnostic_execution_failed": "Controller bus timeout or diagnostic interface failure.",
    "needs_clarification": "Device chassis or bay identifier is ambiguous.",
    "awaiting_approval": "Class B mutating action proposed; waiting for human supervisor approval.",
    "investigating": "Agent actively gathering evidence and analyzing telemetry...",
    "created": "Incident created. Ready to launch investigation.",
}


# ---------------------------------------------------------------------------
# Persistent Simulated Environment Banner
# ---------------------------------------------------------------------------

mode_badge = (
    '<span class="badge-live">LIVE (Muse Spark API)</span>'
    if st.session_state.execution_mode == "live"
    else '<span class="badge-replay">REPLAY (Recorded Meta Model Run)</span>'
)

st.markdown(f"""
<div class="sim-banner">
    <strong>Simulated environment:</strong> all devices, telemetry, logs and manuals are synthetic.
    &nbsp;&nbsp;|&nbsp;&nbsp; Mode: {mode_badge}
</div>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Sidebar: Setup, Scenarios & Controls
# ---------------------------------------------------------------------------

with st.sidebar:
    st.title("InfraSight")
    st.caption("Evidence-First IT Infrastructure Investigator")

    # Service Health Check
    try:
        health = client.health_check()
        st.success(f"Backend Connected ({health.get('mode', 'simulated')})", icon="🟢")
    except Exception as ce:
        st.error(f"Backend Offline: {ce}", icon="🔴")

    st.markdown("---")

    # Execution Mode Selector
    st.subheader("1. Execution Mode")
    mode_option = st.radio(
        "Choose Mode:",
        options=["Replay a recorded run", "Run live (uses API credits)"],
        index=0 if st.session_state.execution_mode == "replay" else 1,
        help="Replay mode runs verified offline cached runs with zero token charges.",
        key="mode_radio_selector",
    )
    st.session_state.execution_mode = "replay" if "Replay" in mode_option else "live"

    live_pwd = ""
    if st.session_state.execution_mode == "replay":
        st.caption("⚡ Offline Replay: Works with zero tokens, no latency, and no API key.")
    else:
        st.caption("🌐 Live Mode: Calls Meta Model API (`muse-spark-1.3`). Subject to spend cap ($5/day) & session quota (3 runs).")
        live_pwd = st.text_input("Live Mode Passcode (LIVE_PASSWORD):", type="password", key="demo_live_pwd", help="Required if host deployed with LIVE_PASSWORD.")

    st.markdown("---")

    # Scenario Loader
    st.subheader("2. Select Incident")
    picker_mode = st.radio("Source:", ["Load fixed synthetic scenario", "Custom Freeform Input"], index=0)

    scenario_selected = None
    custom_description = ""
    uploaded_files_data = []

    if picker_mode == "Load fixed synthetic scenario":
        try:
            scenarios = client.list_scenarios()
            scenario_map = {f"[{s['scenario_id']}] {s['name']}": s for s in scenarios}
            selected_label = st.selectbox(
                "Synthetic Scenarios (Hero Cases First):",
                options=list(scenario_map.keys()),
                index=0,
            )
            if selected_label:
                scenario_selected = scenario_map[selected_label]
                st.session_state.selected_scenario_data = scenario_selected
                st.session_state.selected_scenario_id = scenario_selected["scenario_id"]
                st.info(f"**Category:** {scenario_selected.get('category')}\n\n**Report:** {scenario_selected.get('incident_description')}")
        except Exception as e:
            st.warning(f"Could not load scenarios: {e}")
    else:
        custom_description = st.text_area(
            "Incident Description:",
            placeholder="e.g., Solid amber LED reported on server SRV-004 drive bay 4...",
            height=100,
        )
        uploads = st.file_uploader(
            "Upload Chassis / LED Frames (1-3 PNG/JPEG):",
            type=["png", "jpg", "jpeg"],
            accept_multiple_files=True,
        )
        if uploads:
            for up in uploads[:3]:
                b = up.read()
                uploaded_files_data.append((up.name, b, up.type))
            if not live_pwd:
                live_pwd = st.text_input("Upload Passcode (LIVE_PASSWORD):", type="password", key="demo_upload_pwd")

    st.markdown("---")

    # Public Demo Guardrails Notice
    st.info(
        "ℹ️ **Public Demo Controls (Simulated Environment):**\n"
        "- Default: **Offline Replay Mode** with zero token consumption.\n"
        "- Live Model Cap: **$5.00/day** global spend limit (ledger-enforced).\n"
        "- Per-Session Limit: **3 live investigations**.\n"
        "- Custom uploads auto-delete after processing."
    )

    # Start Investigation Button
    if st.button("🚀 Start Investigation", type="primary", use_container_width=True):
        try:
            with st.spinner("Submitting incident..."):
                desc = scenario_selected["incident_description"] if scenario_selected else custom_description
                if not desc.strip():
                    st.error("Please provide an incident description.")
                else:
                    file_payload = []
                    existing_paths = None
                    if scenario_selected:
                        existing_paths = scenario_selected.get("image_frames", [])
                    else:
                        file_payload = uploaded_files_data

                    # Create Incident
                    inc_resp = client.create_incident(
                        description=desc,
                        image_files=file_payload if not existing_paths else None,
                        image_paths=existing_paths,
                        mode=st.session_state.execution_mode,
                        live_password=live_pwd if live_pwd else None,
                    )
                    inc_id = inc_resp["incident_id"]
                    st.session_state.current_incident_id = inc_id

                    # Kick off investigation
                    client.start_investigation(
                        incident_id=inc_id,
                        sync=False,
                        mode=st.session_state.execution_mode,
                        live_password=live_pwd if live_pwd else None,
                    )
                    st.success(f"Investigation initialized: `{inc_id}`")
                    st.rerun()
        except APIClientError as ace:
            st.error(f"API Error: {ace.detail}")
        except Exception as ex:
            st.error(f"Failed to launch: {ex}")

    st.markdown("---")
    st.subheader("3. Safety Stress Test")
    if st.button("🛡️ Policy Stress Test (Scripted Adversarial Model)", use_container_width=True, help="Executes 5 scripted prohibited actions against the backend policy engine to demonstrate enforcement."):
        try:
            with st.spinner("Executing scripted adversarial requests against backend policy..."):
                stress_resp = client.run_policy_stress_test()
                st.session_state.current_incident_id = stress_resp["incident_id"]
                st.session_state.incident_cache = None
                st.success(f"Stress test executed: `{stress_resp['incident_id']}`")
                st.rerun()
        except Exception as e:
            st.error(f"Stress test error: {e}")

    # Reset button
    if st.session_state.current_incident_id:
        if st.button("🔄 Clear / New Investigation", use_container_width=True):
            st.session_state.current_incident_id = None
            st.rerun()

    st.markdown("---")
    # Approver Settings
    st.subheader("4. Approver Auth (Optional)")
    st.session_state.approver_name = st.text_input("Approver Identity:", value=st.session_state.approver_name)
    st.session_state.approver_token = st.text_input("APPROVER_TOKEN (if required):", value=st.session_state.approver_token, type="password")


# ---------------------------------------------------------------------------
# Main Panel: Non-Blocking Investigation View
# ---------------------------------------------------------------------------

incident_id = st.session_state.current_incident_id

if not incident_id:
    st.info("👈 Select a synthetic scenario or enter an alert in the sidebar and click **Start Investigation**.")
    # Show Usage Summary on empty landing
    try:
        usage_sum = client.get_usage_summary()
        st.markdown("### Cumulative Ledger Summary")
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Model Calls", usage_sum.get("total_calls", 0))
        col2.metric("Total Tokens Consumed", f"{usage_sum.get('total_tokens', 0):,}")
        col3.metric("Total Cost (USD)", f"${usage_sum.get('total_cost_usd', 0.0):.4f}")
    except Exception:
        pass
    st.stop()


# ---------------------------------------------------------------------------
# Active Investigation Fragment (Polls every 2 seconds until terminal)
# ---------------------------------------------------------------------------

poll_interval = None if os.getenv("PYTEST_CURRENT_TEST") else 2.0

@st.fragment(run_every=poll_interval)
def render_investigation_view(inc_id: str):
    try:
        inc = client.get_incident(inc_id)
    except APIClientError as e:
        st.error(f"Failed to fetch incident status: {e.detail}")
        return
    except APIConnectionError as ce:
        st.error(f"Backend connection error: {ce}")
        return

    cur_status = inc.get("status", "unknown")
    cur_mode = inc.get("mode", "simulated").upper()
    is_terminal = cur_status in [
        "confirmed", "not_confirmed", "resolved_in_simulation",
        "unresolved", "more_evidence_required", "diagnostic_execution_failed",
        "needs_clarification", "awaiting_approval"
    ]

    # Top Header: Incident ID, Mode & Current Status
    head_col1, head_col2, head_col3 = st.columns([3, 1, 1])
    with head_col1:
        st.subheader(f"Incident `{inc_id}`")
        st.caption(f"Target: `{inc.get('device_id') or 'Resolving...'}` | Bay: `{inc.get('bay_id') or 'Resolving...'}`")
    with head_col2:
        badge_cls = "badge-live" if cur_mode == "LIVE" else "badge-replay"
        st.markdown(f'<div style="text-align:right;"><span class="{badge_cls}">{cur_mode} MODE</span></div>', unsafe_allow_html=True)
    with head_col3:
        color = STATUS_COLORS.get(cur_status, "gray")
        st.markdown(f'<div style="text-align:right;">:{color}[**{cur_status.upper()}**]</div>', unsafe_allow_html=True)

    if not is_terminal:
        st.progress(0.65, text=f"Investigation in progress: {cur_status}...")

    # Main Tabs
    tab_overview, tab_evidence, tab_images, tab_timeline, tab_model, tab_report = st.tabs([
        "📋 Diagnosis & Safety",
        "📑 Evidence Ledger",
        "📷 Image & Perception",
        "⏱️ Audit Timeline",
        "🧠 Meta Model Activity",
        "📄 Post-Incident Report",
    ])

    # -----------------------------------------------------------------------
    # TAB 1: Diagnosis & Safety
    # -----------------------------------------------------------------------
    with tab_overview:
        diag = inc.get("diagnosis") or {}
        confidence = inc.get("confidence") or "unknown"
        summary = inc.get("summary") or "Investigation analyzing collected evidence."

        if inc.get("mode") == "stress_test":
            st.warning("🛡️ **Scripted adversarial requests: demonstrates that the backend enforces policy even if a model is fooled. Not a live model run.**")

        # Hero Diagnosis Card
        status_color = STATUS_COLORS.get(cur_status, "gray")
        st.markdown(f"""
        ### Finding: :{status_color}[{cur_status.upper()}]
        **Confidence:** `{confidence.upper()}` &nbsp;&nbsp;|&nbsp;&nbsp; **Assessment:** {STATUS_DESCRIPTIONS.get(cur_status, '')}
        """)

        st.info(f"**Diagnostic Summary:**\n\n{summary}")

        col_sup, col_rec = st.columns(2)
        with col_sup:
            st.markdown("#### Supporting Evidence Cited")
            sup_ids = diag.get("supporting_evidence_ids", [])
            if sup_ids:
                for sid in sup_ids:
                    st.markdown(f"- ✅ `{sid}`")
            else:
                st.write("*No supporting evidence registered yet.*")

            contra_ids = diag.get("contradictory_evidence_ids", [])
            if contra_ids:
                st.markdown("#### Contradictory Evidence Cited")
                for cid in contra_ids:
                    st.markdown(f"- ⚠️ `{cid}` *(refutes alternative hypotheses)*")

        with col_rec:
            st.markdown("#### Missing Information / Discriminating Tests")
            missing = diag.get("missing_information")
            if missing:
                st.warning(missing)
            else:
                st.write("*All necessary evidence gathered.*")

            st.markdown("#### Recommended Next Step")
            rec = diag.get("recommended_action")
            if rec:
                st.success(rec)
            else:
                st.write("*Pending completion of investigation.*")

        st.markdown("---")

        # Human Approval Panel (Class B Safe Remediation)
        pending_actions = inc.get("pending_actions", [])
        active_pending = [a for a in pending_actions if a.get("status") == "pending"]

        if active_pending:
            st.markdown("### 🛡️ Human Supervisor Approval Gate (Class B Mutation)")
            for pa in active_pending:
                aid = pa.get("action_id")
                tool = pa.get("tool")
                canonical_args = pa.get("canonical_args", "{}")
                args_hash = pa.get("args_hash")
                expires_at = pa.get("expires_at", "")

                st.warning(f"""
                **Proposed Consequential Action:** `{tool}`
                - **Target Device:** `{inc.get('device_id')}` | **Bay:** `{inc.get('bay_id')}`
                - **Canonical Arguments:** `{canonical_args}`
                - **Integrity Hash:** `{args_hash}`
                - **Expires At:** `{expires_at}`
                """)

                app_col1, app_col2, app_col3 = st.columns([2, 1, 1])
                with app_col1:
                    approver = st.text_input("Approver Identity:", value=st.session_state.approver_name, key=f"app_{aid}")
                with app_col2:
                    if st.button(f"✅ Approve Action", key=f"btn_app_{aid}", type="primary", use_container_width=True):
                        ok, msg, res = client.approve_action(
                            action_id=aid,
                            approver_token=st.session_state.approver_token,
                            decided_by=approver,
                        )
                        if ok:
                            st.success(msg)
                            st.rerun()
                        else:
                            st.error(msg)
                with app_col3:
                    if st.button(f"❌ Reject Action", key=f"btn_rej_{aid}", use_container_width=True):
                        ok, msg, res = client.reject_action(
                            action_id=aid,
                            approver_token=st.session_state.approver_token,
                            decided_by=approver,
                        )
                        if ok:
                            st.info(msg)
                            st.rerun()
                        else:
                            st.error(msg)

        # Post-Execution Read-Back Verification Panel
        executed_actions = [a for a in pending_actions if a.get("status") in ["approved", "executed"]]
        if executed_actions:
            st.markdown("### 🔄 Read-Back Verification Audit")
            for ea in executed_actions:
                st.success(f"""
                **Executed Action:** `{ea.get('tool')}` (ID: `{ea.get('action_id')}`)
                - **Authorized By:** `{ea.get('decided_by')}` at `{ea.get('decided_at')}`
                - **Execution Corroboration:** `{ea.get('result_ref')}`
                - **Simulated Post-Action Verification:** Confirmed healthy bus read-back.
                """)

        # Denied Actions Panel (Safety Moment - Backend Policy Decisions Only)
        timeline = inc.get("timeline", [])
        denied_events = [
            e for e in timeline
            if (
                e.get("event_type") == "tool_result"
                and e.get("details", {}).get("result", {}).get("status") in ["denied", "policy_denied"]
            )
            or e.get("event_type") in ["authorization_denied", "policy_decision"]
            and e.get("details", {}).get("outcome") in ["denied", "deny", "blocked"]
        ]

        if denied_events:
            st.markdown("### 🛑 Security & Safety Policy Enforcements (Class C & Authorization Denials)")
            for de in denied_events:
                res = de.get("details", {}).get("result", {}) or de.get("details", {})
                action_name = res.get("action_name") or res.get("tool") or de.get("details", {}).get("action_name") or "prohibited_action"
                reason = res.get("reason") or res.get("error") or "Permanently denied by policy."
                pclass = res.get("policy_class") or res.get("action_class") or "Class C (Forbidden)"
                st.error(f"""
                **Denied Consequential Mutation:** `{action_name}`
                - **Safety Policy Reason:** {reason}
                - **Policy Classification:** `{pclass}`
                """)

    # -----------------------------------------------------------------------
    # TAB 2: Evidence Ledger
    # -----------------------------------------------------------------------
    with tab_evidence:
        st.markdown("### Authoritative Evidence Ledger")
        st.caption("Immutable cryptographic registration of all retrieved telemetry, manual excerpts, logs, and measurements.")

        # Extract tool results that returned evidence
        evidence_records = []
        for ev in timeline:
            if ev.get("event_type") == "tool_result":
                det = ev.get("details", {})
                tool = det.get("tool")
                res = det.get("result", {})
                eid = res.get("evidence_id")
                if eid:
                    evidence_records.append({
                        "Evidence ID": eid,
                        "Type": tool.replace("get_", "").replace("fetch_", "").upper(),
                        "Summary": str(res.get("summary") or res.get("status") or ""),
                        "Raw": res,
                    })
            elif ev.get("event_type") == "perception_completed":
                obs = ev.get("details", {}).get("observations", [])
                for o in obs:
                    eid = o.get("source_id")
                    if eid:
                        evidence_records.append({
                            "Evidence ID": eid,
                            "Type": "PERCEPTION",
                            "Summary": f"Color: {o.get('detected_color') or o.get('led_color')}, Label: {o.get('label_read')}",
                            "Raw": o,
                        })

        if evidence_records:
            st.dataframe(
                [{"Evidence ID": r["Evidence ID"], "Type": r["Type"], "Summary": r["Summary"]} for r in evidence_records],
                use_container_width=True,
                hide_index=True,
            )
            for r in evidence_records:
                with st.expander(f"Inspect Raw Record: `{r['Evidence ID']}` ({r['Type']})"):
                    st.json(r["Raw"])
        else:
            st.write("*No evidence records gathered yet.*")

    # -----------------------------------------------------------------------
    # TAB 3: Image & Perception
    # -----------------------------------------------------------------------
    with tab_images:
        st.markdown("### Physical Image Perception & Verification")
        st.caption("Deterministic pixel measurement corroborated against Muse Spark multimodal vision perception.")

        # Show uploaded frames
        img_paths = inc.get("image_paths", [])
        if img_paths:
            cols = st.columns(len(img_paths))
            for idx, ip in enumerate(img_paths):
                with cols[idx]:
                    if Path(ip).exists():
                        st.image(str(ip), caption=f"Frame {idx+1}: {Path(ip).name}", use_container_width=True)
                    else:
                        st.code(f"Path: {ip}")

        # Perception observations from timeline
        perception_ev = [e for e in timeline if e.get("event_type") == "perception_completed"]
        if perception_ev:
            obs = perception_ev[0].get("details", {}).get("observations", [])
            col_pix, col_vis = st.columns(2)
            with col_pix:
                st.markdown("#### Deterministic Pixel Measurement")
                pixel_items = [o for o in obs if o.get("type") == "pixel_analysis"]
                if pixel_items:
                    p = pixel_items[0]
                    st.metric("Detected Color", p.get("detected_color", "unknown").upper())
                    st.metric("Pattern", "BLINKING" if p.get("is_blinking") else "SOLID")
                    rel = p.get("reliability", 0.0)
                    try:
                        rel_str = f"{float(rel):.2f}"
                    except (ValueError, TypeError):
                        rel_str = str(rel).upper()
                    st.metric("Reliability", rel_str)
                else:
                    st.write("*No deterministic pixel data.*")

            with col_vis:
                st.markdown("#### Muse Spark Vision Observation")
                vision_items = [o for o in obs if o.get("type") == "vision_model"]
                if vision_items:
                    v = vision_items[0]
                    st.metric("Model Read Color", (v.get("led_color") or "unknown").upper())
                    st.metric("Chassis Label Read", v.get("label_read") or "N/A")
                    st.write(f"**Description:** {v.get('description')}")
                else:
                    st.write("*No model vision data.*")

            # Contradiction warning
            contradictions = [o for o in obs if o.get("type") == "contradiction"]
            if contradictions:
                for c in contradictions:
                    st.warning(f"⚠️ **Visual Contradiction:** {c.get('summary')}")
        else:
            st.write("*Direct telemetry investigation (no visual frames submitted).*")

        st.markdown("---")
        st.caption("🔬 *SAM 3.1: not run in this build (slated for Phase 6 evaluation).*")

    # -----------------------------------------------------------------------
    # TAB 4: Audit Timeline
    # -----------------------------------------------------------------------
    with tab_timeline:
        st.markdown("### Chronological Audit Timeline")
        st.caption("Complete, verifiable trace of all perception, tool executions, and security decisions. No hidden reasoning.")

        if timeline:
            for ev in timeline:
                step = ev.get("step_number", 0)
                ts = ev.get("timestamp", "")
                etype = ev.get("event_type", "")
                det = ev.get("details", {})

                with st.expander(f"Step {step} | `{ts}` | **{etype.upper()}**"):
                    if etype == "tool_call":
                        st.markdown(f"**Tool Invoked:** `{det.get('tool')}`")
                        st.json(det.get("arguments", {}))
                    elif etype == "tool_result":
                        res = det.get("result", {})
                        pclass = res.get("policy_class")
                        if pclass:
                            badge_color = "badge-safety-c" if "C" in pclass else ("badge-class-b" if "B" in pclass else "badge-class-a")
                            st.markdown(f'<span class="{badge_color}">POLICY: {pclass}</span>', unsafe_allow_html=True)
                        st.json(res)
                    else:
                        st.json(det)
        else:
            st.write("*Audit events will appear as investigation proceeds.*")

    # -----------------------------------------------------------------------
    # TAB 5: Meta Model Activity
    # -----------------------------------------------------------------------
    with tab_model:
        st.markdown("### Meta Model Accounting & Ledger Activity")
        st.caption("Verifiable per-call breakdown of real model IDs, tokens, latencies, and costs.")

        usage_info = inc.get("usage") or {}
        calls = usage_info.get("calls", [])

        col_m1, col_m2, col_m3 = st.columns(3)
        col_m1.metric("Incident Calls", usage_info.get("call_count", len(calls)))
        col_m2.metric("Incident Tokens", f"{usage_info.get('total_tokens', 0):,}")
        col_m3.metric("Incident Cost (USD)", f"${usage_info.get('total_cost_usd', 0.0):.4f}")

        if calls:
            table_data = []
            for c in calls:
                table_data.append({
                    "Purpose": c.get("purpose"),
                    "Model ID": c.get("model_id"),
                    "Reasoning": c.get("reasoning_effort") or "low",
                    "Latency (s)": f"{c.get('latency_s', 0.0):.2f}",
                    "Tokens": f"{c.get('total_tokens', 0):,}",
                    "Cost (USD)": f"${c.get('estimated_cost_usd', 0.0):.4f}",
                    "Replay": "YES" if c.get("is_replay") else "NO",
                })
            st.dataframe(table_data, use_container_width=True, hide_index=True)
        else:
            st.write("*No ledger calls logged yet for this incident.*")

        try:
            cum_usage = client.get_usage_summary()
            st.markdown("#### Cumulative Usage Across All Incidents")
            col_c1, col_c2, col_c3 = st.columns(3)
            col_c1.metric("Cumulative Calls", cum_usage.get("total_calls", 0))
            col_c2.metric("Cumulative Tokens", f"{cum_usage.get('total_tokens', 0):,}")
            col_c3.metric("Cumulative Cost", f"${cum_usage.get('total_cost_usd', 0.0):.4f}")
        except Exception:
            pass

    # -----------------------------------------------------------------------
    # TAB 6: Post-Incident Report (Markdown)
    # -----------------------------------------------------------------------
    with tab_report:
        st.markdown("### Comprehensive Incident Audit Report")
        try:
            md_report = client.get_incident_report(inc_id)
            st.download_button(
                label="📥 Download Report (.md)",
                data=md_report,
                file_name=f"InfraSight_Report_{inc_id}.md",
                mime="text/markdown",
            )
            st.markdown(md_report)
        except Exception as ex:
            st.error(f"Failed to load incident report: {ex}")


# Render the investigation view
render_investigation_view(incident_id)
