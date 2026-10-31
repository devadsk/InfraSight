# InfraSight Live Demonstration Checklist & Presenter Runbook
*(All hardware devices, telemetry, logs, and remediation actions execute in a simulated environment)*

---

## 1. Pre-Demo Environment Verification

Before presenting or recording the walkthrough:

1. **Verify Clean Ports:**
   ```bash
   netstat -ano | findstr :8000
   netstat -ano | findstr :8501
   ```
   *Ensure ports 8000 (FastAPI backend) and 8501 (Streamlit UI) are free.*

2. **Verify Offline Replay Integrity (Zero Token Cost):**
   ```bash
   python scripts/record_replay.py --verify
   ```
   *Expected output: `[PASS]` for all 5 hero scenarios (SCN-02, SCN-01, SCN-08, SCN-10, SCN-03).*

3. **Verify All Unit Tests Pass:**
   ```bash
   python -m pytest tests/ -q
   ```
   *Expected output: `84 passed`.*

4. **Launch Local Services:**
   ```bash
   python scripts/run_local.py
   ```
   *Access Streamlit UI at `http://localhost:8501` and API docs at `http://localhost:8000/docs`.*

---

## 2. Hero Scenario Demonstration Walkthrough (3-Minute Track)

| Step | Scenario | Focus Area | What to Show in the UI | Key Voiceover Talking Point |
| :---: | :--- | :--- | :--- | :--- |
| **1** | **SCN-02** | Contradiction Refutation *(Hero 2)* | Select `SCN-02` from dropdown -> Click **Start Investigation** | "InfraSight refuses to jump to conclusions: an amber LED does not mean a dead drive. The multimodal perception engine detects a blinking amber LED, queries telemetry and RAID state, finds an active rebuild in progress, and refutes drive replacement." |
| **2** | **SCN-02** | Multimodal Perception Tab | Switch to **Image & Perception** tab | "Here we see our guarded perception pipeline: SAM 3.1 localizes candidate drive trays, while deterministic HSV pixel analysis measures hue and blinking frequency. Notice the green safety boundary bounding the LED." |
| **3** | **SCN-01** | Confirmed Drive Failure *(Hero 1)* | Select `SCN-01` -> Click **Start Investigation** | "In Hero 1, an amber LED is corroborated by 142 reallocated sectors and a SMART predictive failure flag. The model proposes a Class B drive replacement, which enters the server-side approval queue." |
| **4** | **SCN-08** | Human Supervisor Approval Flow | Click **Approve Drive Replacement** button in UI | "Consequential hardware actions are never autonomous. The human supervisor reviews the pending action and clicks Approve. The simulated execution engine swaps the drive in simulation, reads back post-action telemetry, and verifies resolution." |
| **5** | **SCN-10** | Class C Safety Denial | Select `SCN-10` -> Click **Start Investigation** | "Security boundaries are enforced strictly in backend code. When an incident or prompt injection requests arbitrary shell commands (`rm -rf /`), our policy engine blocks it with an immediate Class C denial." |
| **6** | **SCN-03** | Hidden Telemetry Defect | Select `SCN-03` -> Click **Start Investigation** | "The image shows a reassuring solid green LED, but background telemetry reveals 34 pending sectors. InfraSight refuses to trust visual indicators alone and safely demands more evidence via a diagnostic surface scan." |

---

## 3. Supplementary Features to Highlight

1. **Meta Model Usage Ledger Tab:**
   - Demonstrates strict accounting across every `muse-spark-1.3` and `sam-3.1` call.
   - Highlights that replay mode records zero tokens and $0.00 spend.
2. **Post-Incident Markdown Report Tab:**
   - Demonstrates one-click export of an enterprise-ready IT incident post-mortem with evidence grounding IDs (`EV-TEL-...`, `EV-LOG-...`, `MAN-...`).
3. **Negative-Control Harness Self-Test:**
   - Terminal demonstration: `python scripts/run_eval.py --self-test` proves that the evaluation harness catches invalid evidence, unapproved executions, and hallucinations.

---

## 4. Presenter Contingency Notes

- **Network Failure or No API Key:** The system defaults to 100% offline Replay Mode (`REPLAY_MODE=true`). No internet connection or API credits are required.
- **Accidental Live API Switch:** Live API mode is protected by `LIVE_PASSWORD` and bounded by a strict `$5.00/day` spend cap and 3-run session limit.
- **Port Conflict:** If port 8000 or 8501 is occupied, terminate any existing python processes with `Stop-Process -Name python* -Force` and restart `scripts/run_local.py`.

