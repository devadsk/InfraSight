# Meta Model API Verification & Benchmark Notes

**Date:** 2026-10-27 10:55:28 UTC  
**Target Host:** `https://api.meta.ai/v1`  
**Text Model Verified:** `muse-spark-1.3` (on `/v1/chat/completions`)  
**SAM Model Verified:** `sam-3.1` (on `/v1/responses`)  

## 1. Summary of Verified Capabilities & Benchmarks

| Test | Feature | Status | Endpoint Used | Latency (s) | Tokens (In/Out) | Est. Cost ($) |
|---|---|---|---|---|---|---|
| Test 1: Text Request | Succeeded. Response: I am Meta AI, an AI assi... | **PASS** | `/v1/chat/completions` | 3.001 | 29 / 429 | $0.001860 |
| Test 2: Multimodal Request | Multimodal analysis completed: In the image:
... | **PASS** | `/v1/chat/completions` | 2.922 | 27 / 565 | $0.002450 |
| Test 3: Function Calling | Tool called: lookup_device_telemetry args={"b... | **PASS** | `/v1/chat/completions` | 1.443 | 101 / 156 | $0.000864 |
| Test 4: Investigation & Final Diagnosis | Separate diagnosis validated schema. Confiden... | **PASS** | `/v1/chat/completions` | 5.061 | 927 / 1105 | $0.005855 |
| Test 5: SAM 3.1 Perception | SAM 3.1 returned real markers (markers_detect... | **PASS** | `/v1/responses` | 2.013 | N/A | $0.002500 |

**Total Session Cost:** `$0.013529`

## 2. Detailed Verification Findings

### A. Routing & Endpoints
- **Muse Spark 1.3:** Successfully routed to `/v1/chat/completions` for all text, multimodal vision, tool-calling turns, and strict structured output.
- **SAM 3.1:** Exclusively hosted on `/v1/responses`. (Calling `/v1/chat/completions` returns HTTP 404: `'The model sam-3.1 is not available on this endpoint. Use /v1/responses.'`).

### B. Observed SAM 3.1 Marker Format (From Real Detection)
- **Raw Evidence:** Preserved in [`docs/sam_samples/sam_rectangle_sample.json`](file:///d:/InfraSight/docs/sam_samples/sam_rectangle_sample.json).
- **Stream/Line Format:**
  `<0f><ID><|box;x1=...;y1=...;x2=...;y2=...;w=...;h=...|><|mask;x=0;y=0;data=...|>,<ID><|box...>`
- **Observed Coordinate Accuracy:** Bounding boxes matched synthetic drawing geometry precisely (`x1=20, y1=20, x2=236, y2=236` for drive tray outer border; `x1=40, y1=90, x2=216, y2=130` for label banner).

### C. Final Diagnosis & Tool Calling Architecture
- **Separate Final Diagnosis Step:** In multi-turn tool loops, tool queries are executed using `tools=[...]`. After all diagnostic tools execute, the orchestrator makes a **separate structured-output call with no tools** (`response_format={'type': 'json_schema', ...}`).
- **Confidence Schema:** Strict categorical enum `['low', 'medium', 'high']` verified; numeric floating-point probabilities are prohibited.
- **Evidence ID Grounding:** Model correctly cites backend source IDs (`EV-TEL-SRV004-BAY04-S2`) in `cited_evidence_ids`.

### D. Token Usage & Latency Accounting
- Always-on reasoning adds latency (1.0s to 6.5s per turn). Orchestration must execute asynchronously with status polling in the UI.
- Token usage parser extracts `input_tokens` and `output_tokens` across both endpoint types and flags any response lacking explicit usage metrics.
