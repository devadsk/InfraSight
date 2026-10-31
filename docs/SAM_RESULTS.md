# SAM 3.1 Spatial Awareness & Guarded Perception Evaluation

## 1. Overview & Architecture (Phase 6, Part B1)

InfraSight incorporates a **guarded spatial perception pipeline** that couples Meta's `sam-3.1` model (spatial promptable segmentation/localization via `/v1/responses`) with deterministic HSV pixel verification:

1. **SAM 3.1 Localization Stage:** Prompts `sam-3.1` with the physical concept `"LED"` (or `"indicator light"`) on the incoming hardware photograph.
2. **Deterministic Bright Saturated Blob Guard:** SAM candidate bounding boxes (`<|box;x1=...;y1=...;x2=...;y2=...;w=...;h=...|>`) are subjected to physical pixel analysis before acceptance:
   - Must contain $\ge 10$ saturated pixels.
   - Saturation $S \ge 0.20$ and Brightness $V \ge 0.25$.
   - Hue must classify to a distinct active state (`amber`, `green`, `red`).
   - Dim metal, unlit indicators, chassis reflections, or false positives are **rejected**.
3. **Evidence Registration & Fail-Safe Fallback:**
   - **Used (Guard Passed):** Registers evidence ID `EV-IMG-<filename>-SAM` and anchors the pixel analysis crop to the validated box.
   - **Rejected (Guard Failed):** Logs candidate boxes and rejection rationale, falling back safely to default drive bay coordinates.
   - **Zero-Match (No Markers):** Falls back safely to default region pixel analysis with zero tokens wasted on subsequent spatial stages.

---

## 2. Evaluation on 3 Real User Hardware Photos

The pipeline was evaluated against the 3 tracked user photos in `data/images/user_photos/`:

| Photo File | Concept | Raw SAM 3.1 Output | Guarded Pixel Analysis Verification | Guard Outcome | Evidence Registered |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `Raspberrypi.jpg` | `"LED"` | `1 box`: `[215, 176, 233, 202]` | `detected_color="red"`, 307 saturated px ($S=0.89$, $V=0.82$), core=137px | **PASSED (USED)** | `EV-IMG-Raspberrypi-SAM` |
| `external_hard_disk.jpeg` | `"LED"` | `1 box`: `[657, 718, 677, 739]` | `detected_color="off"`, 0 saturated px ($V=0.12$, unpowered dark plastic) | **FAILED (REJECTED)** | None (Fell back to default region) |
| `router.jpeg` | `"LED"` | `0 boxes` (empty response `""`) | No candidate coordinates returned | **ZERO-MATCH (BYPASSED)** | None (Fell back to default region) |

---

## 3. Key Observations & Design Justification

1. **Safety Against Hallucinated Bounding Boxes:** Object segmenters frequently detect inactive LED bezels or dark circular holes as "LEDs". In `external_hard_disk.jpeg`, SAM successfully identified the physical indicator window, but the device was unpowered. The deterministic HSV guard successfully identified `detected_color="off"` and refused to register a false illumination claim.
2. **True Positive Precision:** In `Raspberrypi.jpg`, the power LED was brightly illuminated red. SAM isolated the exact sub-region $[215, 176, 233, 202]$, and the guard passed it with high confidence ($S=0.89, V=0.82, 307\text{ px}$), registering `EV-IMG-Raspberrypi-SAM`.
3. **Resilience to Zero Matches:** On ambiguous or cluttered devices (`router.jpeg`), SAM did not locate an LED under the default prompt. The pipeline handled the 0-match case gracefully without error, proceeding with standard chassis analysis.

---

## 4. Test Verification

Automated regression coverage for all 3 states is codified in `tests/test_sam_stage.py`:
- `test_sam_marker_parsing`: Validates regex extraction of SAM marker tokens.
- `test_sam_stage_box_used_guard_passed`: Validates accepted bright red LED on `Raspberrypi.jpg`.
- `test_sam_stage_box_rejected_guard_failed`: Validates rejection of unpowered LED on `external_hard_disk.jpeg`.
- `test_sam_stage_zero_match_fallback`: Validates 0-box fallback on `router.jpeg`.
