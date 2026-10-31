# InfraSight - Demonstration Video Script & Walkthrough

> **Evaluation Environment Notice:** All remediation actions and hardware infrastructure operate within a **simulated environment**. Metrics cited are measured evaluation results ($k/N$).

---

## Part 1: Full 3-Minute Video Walkthrough Script (180 Seconds)

### Timeline & Second-by-Second Breakdown

| Timestamp | Screen / Visual Focus | Spoken Narration (Voiceover) | Key UI Elements Highlighted |
| :--- | :--- | :--- | :--- |
| **00:00 – 00:25** | Title slide & Streamlit UI Overview | "In modern data centers and edge IT environments, troubleshooting is noisy and high-stakes. Technicians misinterpret flashing status LEDs, alert consoles emit incomplete warnings, and autonomous remediation scripts risk catastrophic outages by executing destructive actions without human oversight. This is **InfraSight**—an evidence-first, multimodal IT troubleshooting assistant built for the Meta Global AI Developer Hackathon." | InfraSight header, System Status badge (`simulated`), Mode selector |
| **00:25 – 00:55** | **Hero 1: SCN-02 (Rebuild Contradiction)** | "Let's load our first hero scenario: a technician reports an amber blinking drive on server SRV-001 drive bay 2, suspecting failure. Watch what happens: InfraSight doesn't just ask an LLM to guess. It runs deterministic HSV pixel analysis across two temporal frames. It proves the LED is actually solid green—not blinking amber. It queries RAID controller telemetry, identifies a normal volume rebuild in progress, and issues a `not_confirmed` diagnosis with high confidence. It prevented a technician from pulling a healthy, active rebuild drive." | Timeline event cards, Multimodal Perception tab showing Hue/Brightness analysis, RAID telemetry evidence card |
| **00:55 – 01:25** | **Hero 2: SCN-01 (Class B Remediation & Human-in-the-Loop)** | "Now consider a genuine drive failure on SRV-004 bay 4. Telemetry verifies 248 reallocated sectors and a predictive failure flag. Here, the assistant proposes remediation: `replace_drive`. But InfraSight enforces strict safety tiers: Class B actions cannot execute autonomously. The backend halts and waits for server-side human approval. As supervisor, I review the diff and click 'Approve'. Only then does the simulated execution engine swap the drive and re-verify normal telemetry." | Pending Action modal, Human Approval button, Simulated executor output, Resolved verification |
| **01:25 – 01:50** | **Hero 3: SCN-10 & Scripted Policy Stress (Class C Denial)** | "What about adversarial attacks? In SCN-10, an uncataloged manual contains an indirect prompt injection attempting to trick the model into running arbitrary shell reboots. The model refuses. Furthermore, clicking 'Policy Stress Test' proves that even if an attacker completely compromises an LLM, our backend policy engine deterministically intercepts and denies all Class C actions, unknown tools, and unauthorized devices before execution." | Policy Stress Test results, 5 Class C denial badges, Audit trail showing code-level policy enforcement |
| **01:50 – 02:15** | **SAM 3.1 Spatial Awareness & Perception Guard** | "InfraSight also integrates Meta's `sam-3.1` for promptable spatial concept localization. Evaluated on real hardware photos, SAM localizes indicator regions, which are guarded by deterministic pixel analysis. If a region lacks saturated illumination—such as an unpowered external disk—the guard rejects it. If it contains a bright LED, like this Raspberry Pi power indicator, it is verified and registered as evidence." | SAM 3.1 detection boxes, Guarded HSV verification results, Registered `EV-IMG-...-SAM` evidence |
| **02:15 – 02:40** | **Meta Model Transparency & Accounting Ledger** | "Under the hood, InfraSight is powered exclusively by Meta's `muse-spark-1.3` and `sam-3.1`. The Meta Model Activity tab renders our verifiable SQLite usage ledger: exact token counts, latencies, and costs for every single call. For offline evaluation, our replay mode runs with zero external API calls and zero token expenditure." | Meta Model Activity tab, Per-call token breakdown, SQLite usage ledger table |
| **02:40 – 03:00** | **Conclusion & Measured Results** | "Across our evaluation suite of 16 scenarios, InfraSight achieves a 15/16 strict pass rate (93.8%) with zero regressions against baseline. By pairing Meta models with deterministic verification and server-side policy controls, InfraSight delivers trustworthy, safe infrastructure operations." | Evaluation comparison summary, GitHub repository link, Closing slide |

---

## Part 2: 30–60 Second Social Media ("X" Cut) Script

**Target Duration:** 45 seconds  
**Objective:** Maximum punch, showing multimodal contradiction and human-in-the-loop safety in under a minute.

- **[00:00 – 00:10] Hook:** "Can you trust an AI assistant to troubleshoot enterprise IT hardware without pulling the wrong drive or running unauthorized shell commands?"
- **[00:10 – 00:25] The Multimodal Contradiction:** "Watch InfraSight analyze this server bay. The technician reported an amber blinking failure, but InfraSight’s physical pixel pipeline measures solid green illumination. RAID telemetry reveals a volume rebuild in progress—preventing a catastrophic false drive pull."
- **[00:25 – 00:38] Human-in-the-Loop Safety:** "When a drive is genuinely broken, InfraSight proposes remediation, but halts. Class B actions require server-side supervisor approval before simulated execution."
- **[00:38 – 00:45] CTA & Architecture:** "Built with Meta's `muse-spark-1.3` and `sam-3.1`, featuring deterministic verification and verifiable token accounting. Check out InfraSight on GitHub."

---

## Part 3: Recording Tips & Screen Layout Recommendations

1. **Browser Zoom:** Set browser zoom to 100% or 110% on a 1920x1080 resolution.
2. **Tab Arrangement:** Keep Streamlit UI on the main screen; navigate cleanly between:
   - Overview Tab (Diagnosis, Pending Actions)
   - Evidence Registry Tab (Registered citations)
   - Perception Tab (Pixel HSV analysis & SAM overlays)
   - Meta Model Activity Tab (Verifiable ledger)
3. **Execution Mode:** Use **Replay Mode** during recording to eliminate network latency, ensuring instantaneous and reproducible UI responses.
