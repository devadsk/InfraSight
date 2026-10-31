# InfraSight - Demonstration Video Script & Walkthrough

> **Evaluation Environment Notice:** All remediation actions and hardware infrastructure operate within a **simulated environment**. All cited metrics are measured evaluation results ($k/N$).

---

## Part 1: Full Video Walkthrough Script (< 2:55 Runtime, Table Format)

- **Total Word Count:** 288 words (strict limit: $\le$ 330 words at 130 WPM).
- **Structure:** Cold open on Streamlit UI in the first 20 seconds. Hero 1 executed live; subsequent heroes run in offline replay mode.
- **On-Screen Watermark:** "Simulated environment: synthetic devices, telemetry, and manual rules".

| Time | Screen & Visual Focus | Spoken Narration (Voiceover) | Word Count | Exact UI Clicks & Fallback Plan |
| :--- | :--- | :--- | :---: | :--- |
| **00:00 – 00:20** | **Cold Open on UI:** Browser opens directly on InfraSight Streamlit UI (1920x1080). Watermark "Simulated environment" visible. Overview tab with system status badge. | "In enterprise data centers, ambiguous alerts and flashing LEDs cause costly false drive pulls and cascading outages. This is InfraSight: an evidence-first multimodal troubleshooting assistant built with Meta’s Muse Spark and SAM 3.1 in a simulated environment." | 38 words | **Click:** Ensure "Live Mode" is toggled in sidebar. Select scenario dropdown: `SCN-02`. |
| **00:20 – 00:55** | **Hero 1 (SCN-02 Live Run):** Dual image frames displayed in UI. Click "Investigate". Live API call executes. Multimodal perception displays HSV blinking amber; RAID telemetry card displays 68.4% rebuild; vendor manual card displays `MAN-LED-01`. Status badge renders `not_confirmed`. | "A technician suspects a drive failure on server SRV-004 bay 2. We click Investigate live. InfraSight’s two-frame pixel analysis measures blinking amber. But telemetry shows the RAID array actively rebuilding at 68.4%, and vendor manual MAN-LED-01 confirms blinking amber indicates normal rebuild activity. InfraSight diagnoses not_confirmed, preventing a false drive pull." | 54 words | **Click:** Click "Investigate (Live)" button.<br>**Fallback Plan:** If network latency exceeds 8s, toggle "Replay Mode" in sidebar to demonstrate cached live response instantly. |
| **00:55 – 01:25** | **Hero 2 (SCN-01 & SCN-08 Flow):** Toggle Replay Mode. Load SCN-01: confirmed drive defect with 164 reallocated sectors. Switch to SCN-08: replacement proposed, held as pending Class B action. Supervisor reviews diff, clicks "Approve". Execution card shows simulated drive swap and readback verification. | "In replay mode, scenario SCN-01 diagnoses a genuine drive failure on bay 4 with 164 reallocated sectors. In scenario SCN-08, replacement is proposed. Because physical remediation is Class B, InfraSight halts for human supervisor approval. We click Approve; the simulated engine replaces the drive and reads back healthy telemetry." | 52 words | **Click:** Select `SCN-08` from dropdown. Click "Approve & Execute" button in Pending Actions panel. |
| **01:25 – 01:55** | **Hero 3 (SCN-10 Refusal & Policy Stress):** Load SCN-10: technician requests `rm -rf /`; model textual refusal shown. Navigate to Safety & Policy tab. Click "Run Policy Stress Test". Table populates with 5 Class C denial badges. | "In scenario SCN-10, a technician requests an unauthorized shell command; Muse Spark refuses in text. To test code-level defenses, our Policy Stress Test proves that when a scripted adversarial model proposes five prohibited actions, the backend intercepts and denies every one as Class C." | 46 words | **Click:** Select `SCN-10`. Switch to "Safety & Policy" tab. Click "Run Policy Stress Test" button. |
| **01:55 – 02:20** | **Perception Guard & SAM 3.1:** Perception tab displaying bounding boxes on real photos: Raspberry Pi (green box, bright red LED), external hard drive (rejected unlit bezel), and router (zero match). | "For spatial localization, SAM 3.1 was evaluated on three real hardware photos: one bright LED was accepted by our pixel guard, one unlit bezel was rejected, and one produced a zero-match fallback. Physical pixel measurements always guard spatial proposals." | 40 words | **Click:** Switch to "Perception & SAM" tab. Click through the 3 real photo cards. |
| **02:20 – 02:40** | **Verifiable Ledger & Accounting:** Meta Model Activity tab displaying SQLite `usage_ledger`. Columns: purpose, model (`muse-spark-1.3`), prompt tokens, completion tokens, cost, latency. | "The Meta Model Activity tab renders our SQLite usage ledger, displaying exact tokens, latencies, and costs for every call. SCN-01 consumed 19,476 tokens costing less than one cent." | 28 words | **Click:** Switch to "Model Activity" tab. Scroll down through the live call ledger table. |
| **02:40 – 02:55** | **Conclusion & Measured Results:** Closing slide with GitHub repository link, test badges (84 unit tests passed, 100% live evaluation), and architecture summary. | "Across our frozen 17-scenario benchmark, InfraSight achieved 12/14 development and 3/3 same-logic variant passes, with 15/17 consistent across three live runs. Grounded reasoning and server-side safety keep infrastructure reliable." | 30 words | **Visual:** Fade out to summary slide with repo link and evaluation metrics table. |

---

## Part 2: 30–45 Second Social Media ("X" Cut) Script

- **Target Duration:** 40 seconds (~91 words at 135 WPM).
- **Objective:** Concise demonstration of multimodal rebuild contradiction and human-in-the-loop safety in under 45 seconds.

- **[00:00 – 00:10] Hook:** "Can an AI troubleshoot data center hardware without pulling the wrong drive? In a simulated environment, meet InfraSight."
- **[00:10 – 00:25] The Rebuild Contradiction:** "A technician spots a blinking amber LED on server SRV-004 bay 2. InfraSight verifies blinking amber, but telemetry proves the RAID array is actively rebuilding at 68.4%. Citing vendor manual MAN-LED-01, it rules not_confirmed, preventing an accidental outage."
- **[00:25 – 00:38] Human-in-the-Loop Safety:** "When telemetry confirms 164 reallocated sectors, replacement is proposed but halted. Class B actions require human supervisor approval before execution."
- **[00:38 – 00:45] Architecture & Call to Action:** "Powered by Meta's `muse-spark-1.3` and `sam-3.1` with deterministic verification. Check out InfraSight on GitHub."

---

## Part 3: Recording Instructions & Operator Checklist

1. **Resolution & Scaling:** Set display resolution to 1920x1080 and browser zoom to 100%.
2. **Pre-Recording Verification:** Run `python scripts/record_replay.py --verify` prior to recording to ensure all replay caches are intact.
3. **Execution Mode Flow:**
   - Begin with Live Mode on SCN-02 to demonstrate real API interaction with `muse-spark-1.3`.
   - Switch to Replay Mode for SCN-08 and SCN-10 for instantaneous, network-independent UI transitions.
4. **On-Screen Captions:** Add a semi-transparent footer caption: *"Simulated environment: all servers, telemetry, and vendor manuals are synthetic."*
