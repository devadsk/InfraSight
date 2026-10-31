# InfraSight - Hackathon Submission Document
*(simulated environment: all devices, telemetry, logs, and manuals are synthetic)*

**Hackathon Track:** Indie Developer Track  
**Hackathon Theme:** Build for Your World  
**Repository:** {{TO_FILL_BY_DEVELOPER: repo_url}}  
**Video Demonstration:** {{TO_FILL_BY_DEVELOPER: video_url}}  
**Hosted Application:** {{TO_FILL_BY_DEVELOPER: hosted_demo_url}}  
**Live Access Password Decision:** {{TO_FILL_BY_DEVELOPER: live_password_decision}}  
**Team Members:** {{TO_FILL_BY_DEVELOPER: team_members}}  

---

## 1. Project Title & Tagline

- **Project Title:** InfraSight
- **Tagline:** Evidence-first multimodal IT infrastructure troubleshooting assistant with deterministic verification and server-side safety controls in a simulated environment.

---

## 2. Why Build for Your World

{{TO_FILL_BY_DEVELOPER: why_build_for_your_world}}

### Developer Personal Connection
{{TO_FILL_BY_DEVELOPER: personal_connection}}

---

## 3. Problem Statement & Architecture

In enterprise data centers and edge server installations, hardware troubleshooting is fraught with high-stakes failure modes:
1. **Perceptual Ambiguity:** Blinking status LEDs frequently indicate active, non-fault operational states (e.g. background RAID volume rebuilds). Pulling a healthy rebuilding drive causes unrecoverable data loss.
2. **Context Disconnects:** Generic alerts rarely correlate visual evidence with hardware vendor manuals and deep SMART telemetry before proposing remediation.
3. **Safety Risks in Agentic AI:** Unconstrained generative models permitted to invoke raw shell commands or trigger reboot cycles risk cascading outages or succumbing to indirect prompt injections in system logs.

**InfraSight** addresses these challenges through an **evidence-first, bounded-autonomy architecture**:
- **Multimodal Visual Inspection:** Leverages Meta's `muse-spark-1.3` for high-level image inspection and Meta's `sam-3.1` for promptable indicator localization.
- **Deterministic Physical Guarding:** Visual proposals are guarded by physical HSV pixel analysis across sequential frames to accurately measure color and distinguish solid from blinking states.
- **Anti-Hallucination Verifier:** Every factual assertion must cite registered evidence IDs (`EV-TEL-...`, `EV-LOG-...`, `EV-IMG-...`, `MAN-...`). Invented or unverified IDs trigger a fail-safe fallback.
- **Server-Side Safety Policy:** Remediation operations are segmented into Class A (read-only automated telemetry queries), Class B (consequential actions like drive swaps requiring explicit human supervisor approval), and Class C (prohibited commands denied unconditionally by code).

---

## 4. Meta Tooling Detail & Model Utilization

All model interactions are strictly authenticated and logged to an append-only SQLite usage ledger (`usage_ledger`):

| Model ID | Endpoint | Purpose in InfraSight | Verification Source |
| :--- | :--- | :--- | :--- |
| `muse-spark-1.3` | `/v1/chat/completions` | Multimodal chassis label/color extraction, autonomous tool investigation loop, and structured diagnosis synthesis | Verified in request payload, API response, and `usage_ledger` |
| `sam-3.1` | `/v1/responses` | Promptable spatial concept localization ("LED", "indicator light") on server chassis photos | Verified via `/v1/responses` and `docs/SAM_RESULTS.md` |

### Model Autonomy & Guardrails (from live transcripts)
- **Autonomous Tool-Calling:** The model autonomously determines which telemetry sources, event logs, and vendor manuals to inspect across up to 4 sequential investigation turns per incident.
- **Execution Barricade:** The model possesses zero tool access to execute physical changes. Consequential actions (`replace_drive`, `restart_service`) can only be *proposed* into a server-side pending queue. Execution is locked until an authenticated human supervisor issues approval.
- **Spatial Perception Guard:** SAM 3.1 proposals are verified by deterministic HSV analysis. Tested across 3 real hardware photos: 1 bright LED candidate was accepted (`Raspberrypi.jpg`), 1 unlit bezel candidate was rejected (`external_hard_disk.jpeg`), and 1 produced a zero-match fallback (`router.jpeg`).

---

## 5. Built During the Hackathon

All code, data fixtures, tests, and documentation were conceived and implemented during the hackathon period (October 27, 2026 – October 31, 2026):

- **October 27, 2026:** Workspace initialization, Meta client API integration (`muse-spark-1.3`, `sam-3.1`), synthetic data fixtures (`data/scenarios.json`, `data/telemetry.json`, `data/events.json`, `data/manuals/`), deterministic HSV pixel analysis, and referential integrity validator.
- **October 28, 2026:** Autonomous multi-turn orchestrator, sliding window event filtering, structured diagnosis schema validation, server-side approval engine, simulated execution engine, and initial REST API.
- **October 29, 2026:** Server-side policy engine, allowlist enforcement, negative-control evaluation harness (`--self-test`), and prompt freeze declaration.
- **October 30, 2026:** Streamlit operator interface, dual-mode execution (live API vs. offline replay), and verifiable token accounting dashboard.
- **October 31, 2026:** Hardened live evaluation (3 certified live repeats with cache bypass), SAM 3.1 guarded spatial perception, backend policy stress tests, and deployment packaging.

---

## 6. Measured Evaluation Results (Simulated Environment)

Evaluated on October 31, 2026, across our frozen benchmark suite of 17 scenarios using live Meta `muse-spark-1.3` calls with cache bypass:

| Evaluation Dimension | Metric / Score ($k/N$) | Percentage | Verification Status |
| :--- | :---: | :---: | :--- |
| **Development Scenarios (Run 1 & 3)** | 12/14 | **85.7%** | Certified live (SCN-07 conservative; SCN-16 uncataloged) |
| **Development Scenarios (Run 2)** | 13/14 | **92.9%** | Certified live |
| **Same-Logic Variants (All Runs)** | 3/3 | **100.0%** | Consistent across all 3 live repeats |
| **Device Resolution Accuracy** | 17/17 | **100.0%** | Zero hallucinated chassis or bay IDs |
| **Policy Adherence & Safety** | 17/17 | **100.0%** | Zero unapproved Class B/C executions |
| **Multi-Run Consistency** | 15/17 | **88.2%** | Consistent across 3 live runs (SCN-07 stable conservative) |
| **Negative-Control Self-Tests** | 4/4 | **100.0%** | Catches fake IDs, unregistered IDs, and unauthorized calls |
| **Offline Replay Verification** | 5/5 | **100.0%** | Hero cases replay with zero tokens and zero network |
| **Backend Policy Stress Test** | 5/5 | **100.0%** | Intercepts and denies all 5 scripted Class C attacks |
| **Total Live Evaluation Calls** | 215 live calls | **100% live** | Zero replayed rows served during live evaluation |
| **Total 3-Repeat Evaluation Cost** | $0.573 USD | — | Recorded in SQLite `usage_ledger` |

*Note on SCN-16 and SCN-07:* In SCN-16 (uncataloged error code `CODE-Y-PWR-9999`), the model cited 6 evidence items and noted the missing manual documentation in `missing_information`, but evaluated healthy drive telemetry to conclude `not_confirmed` in Run 1 (strict fail), while passing in Runs 2 & 3. In SCN-07, after an extended diagnostic scan cleared pending sectors, the model consistently produced conservative `more_evidence_required` across all 3 runs requesting ongoing monitoring.

---

## 7. Limitations

1. **Simulated Environment:** All server models, SMART telemetry values, syslog streams, and vendor manuals are synthetic fixtures designed to emulate real hardware failure modes; InfraSight has not been attached to production IPMI or BMC management buses.
2. **Sequential Dual-Frame Analysis:** LED blinking detection relies on two sequential photographic frames captured ~0.5–1.0s apart rather than a continuous high-speed video feed.
3. **Action Surface:** The simulated execution engine currently supports `replace_drive` and `restart_service`. Additional hardware remediations require extending the allowlist and simulation adapters.
4. **Chassis Scope:** Scenarios evaluate single-rack multi-server installations (`SRV-001` to `SRV-004`). Fleet-wide cross-datacenter orchestration is outside the current scope.

---

## 8. How Judges Can Run It

### Option A: 100% Offline Replay Mode (Recommended: Zero API Key, Zero Cost)
Judges can explore the full application and verify all hero scenarios without configuring a Meta API key:
```bash
# 1. Clone repository and install dependencies
git clone {{TO_FILL_BY_DEVELOPER: repo_url}}
cd infrasight
python -m venv venv
# Windows: venv\Scripts\activate | Linux/macOS: source venv/bin/activate
pip install -r requirements.txt

# 2. Run unit test suite (84 passing tests)
pytest tests/

# 3. Verify offline replay traces for hero scenarios
python scripts/record_replay.py --verify

# 4. Launch interactive Streamlit interface in Replay Mode
streamlit run frontend/app.py
```

### Option B: Live Meta Model API Evaluation
To run live against Meta's Model API:
```bash
# 1. Add your Meta Model API Key to .env
echo "META_API_KEY=your_key_here" >> .env

# 2. Run live evaluation across all 17 benchmark scenarios
python scripts/run_eval.py --live --compare
```

### Option C: Containerized Deployment
```bash
docker build -t infrasight .
docker run -p 8501:8501 -e REPLAY_MODE=true infrasight
```
