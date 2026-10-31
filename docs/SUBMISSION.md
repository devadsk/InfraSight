# InfraSight - Hackathon Submission Document

**Hackathon Track:** Indie Developer Track  
**Submission Category:** Multimodal Systems & Agentic AI  
**Repository:** [InfraSight GitHub Repository](https://github.com/example/infrasight) *(Simulated Environment)*  

---

## 1. Project Title & Tagline

- **Project Title:** InfraSight
- **Tagline:** Evidence-first multimodal IT infrastructure troubleshooting assistant with deterministic verification and server-side safety controls (simulated environment).

---

## 2. Executive Summary & Problem Statement

Modern data centers and enterprise IT environments suffer from acute **alert fatigue**, **observability disconnects**, and **automation hazards**:
1. **Perceptual Discrepancies:** Human technicians frequently misidentify indicator states (e.g. confusing solid amber fault LEDs with amber activity blinkers or normal green activity).
2. **Context Disconnects:** Raw alerts rarely cross-reference vendor hardware manuals, historical telemetry, and visual evidence before proposing invasive fixes.
3. **Safety Risks in Autonomous Remediation:** Generative AI agents that directly execute shell commands or reboot servers risk causing cascading outages or falling prey to prompt injections.

**InfraSight** solves this with an **evidence-first agentic architecture**:
- Integrates Meta's `muse-spark-1.3` for multimodal visual perception, tool-calling investigation, and structured diagnosis.
- Integrates Meta's `sam-3.1` for promptable spatial concept localization, guarded by deterministic HSV pixel analysis.
- Enforces a **Deterministic Verifier** that validates every citation against registered evidence and denies ungrounded claims.
- Implements **Server-Side Safety Tiers**: Class A (read-only automated), Class B (human-in-the-loop supervisor approval required), and Class C (prohibited actions denied unconditionally).

---

## 3. Verified Meta Model Identity & API Utilization

All model interactions are logged to a persistent SQLite usage ledger (`usage_ledger`) with exact token counts, latencies, and costs:

| Model ID | Endpoint | Purpose in InfraSight | Verification Source |
| :--- | :--- | :--- | :--- |
| `muse-spark-1.3` | `/v1/chat/completions` | Multimodal visual inspection, multi-step investigation loop, tool calling, structured JSON output | Verified in request payload & `usage_ledger` |
| `sam-3.1` | `/v1/responses` | Promptable spatial concept localization ("LED", "indicator light") | Verified on `/v1/responses` & `docs/sam_samples/` |

*No unverified or surrogate models were utilized.*

---

## 4. Key Capabilities & Technical Innovations

1. **Dual-Frame Multimodal Perception & Pixel Guard:**
   - Evaluates two sequential frames of hardware chassis images using deterministic physical HSV hue and brightness analysis.
   - Accurately distinguishes solid from blinking indicators without reliance on unreliable frame-rate approximations.
   - Detects discrepancies between high-level vision model claims and physical pixel measurements.
2. **Deterministic Citation Verification:**
   - Every claim in the diagnosis must cite valid, registered evidence IDs (`EV-TEL-...`, `EV-LOG-...`, `EV-IMG-...`, `MAN-...`).
   - If a model cites an unregistered ID or hallucinated parameter, the verifier downgrades or rejects the diagnosis to fail-safe `more_evidence_required`.
3. **Strict Policy Engine & Scripted Adversarial Resilience:**
   - Action proposals adhere to an immutable schema allowlist (`replace_drive`, `restart_service`).
   - Scripted adversarial testing demonstrates that even if a model is completely fooled by an indirect prompt injection, arbitrary shell commands (`reboot -f`), unknown tools, and unapproved devices are intercepted and denied by backend code.
4. **Offline Replay Mode & Cost Guardrails:**
   - Packaged with 100% offline replay traces for the entire evaluation suite, allowing evaluators to run full tests and UI exploration with zero API keys and zero token charges.
   - Production safety controls include a **$5.00/day global spend cap**, **3 runs per session limit**, and `LIVE_PASSWORD` protection.

---

## 5. Measured Evaluation Results (Simulated Environment)

Across our standardized evaluation benchmark of 17 scenarios:

| Category | Passed / Total ($k/N$) | Percentage |
| :--- | :--- | :--- |
| **Development Scenarios** | 13/14 | **92.9%** |
| **Same-Logic Held-Out Scenarios** | 3/3 | **100.0%** |
| **Overall Strict Benchmark Score** | **16/17** | **94.1%** |
| **Regressions Against Baseline** | **0/17** | **0.0%** |
| **Offline Replay Verification** | **5/5 Hero Cases** | **100.0%** |
| **Policy Stress Test** | **5/5 Prohibited Actions Blocked** | **100.0%** |

*(All tests executed in simulated environment with zero live API calls during pytest).*

---

## 6. Video Demonstration & Links

- **Full 3-Minute Walkthrough:** [YouTube / Demo Video Link](https://youtube.com/example)
- **Short 45s Social Cut:** Included in `docs/DEMO_SCRIPT.md`
- **Interactive Web App:** `http://localhost:8501` (Streamlit + FastAPI)
- **Deployment Documentation:** [`docs/DEPLOY.md`](file:///d:/InfraSight/docs/DEPLOY.md)

