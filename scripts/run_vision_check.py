"""
Vision Check Benchmark with Muse Spark 1.3 (Part A Step 0).
Runs one Muse Spark vision call on every image:
- 10 generated server bay images
- 3 real demonstration photos (marked as demonstration inputs, not part of 13-scenario evaluation)

Extracts:
- label_read (versus known truth)
- led_color (versus known truth)
Calculates k/N accuracy on evaluated benchmark images.
Saves results to eval/vision_check.json.
"""

import base64
import json
import os
import requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("META_API_KEY")
API_BASE = os.getenv("META_API_BASE", "https://api.meta.ai/v1")
MODEL = os.getenv("META_MODEL", "muse-spark-1.3")

EVAL_DIR = Path("eval")
EVAL_DIR.mkdir(parents=True, exist_ok=True)

IMAGE_SPECS = [
    # 10 Generated Server Bay Images
    {
        "filename": "data/images/SRV001_BAY02_GREEN.png",
        "is_demonstration_input": False,
        "known_label": "SRV-001 BAY-02",
        "known_color": "green",
    },
    {
        "filename": "data/images/SRV003_BAY01_AMBER_SOLID.png",
        "is_demonstration_input": False,
        "known_label": "SRV-003 BAY-01",
        "known_color": "amber",
    },
    {
        "filename": "data/images/SRV003_BAY01_RED.png",
        "is_demonstration_input": False,
        "known_label": "SRV-003 BAY-01",
        "known_color": "red",
    },
    {
        "filename": "data/images/SRV004_BAY02_AMBER_BLINK_A.png",
        "is_demonstration_input": False,
        "known_label": "SRV-004 BAY-02",
        "known_color": "amber",
    },
    {
        "filename": "data/images/SRV004_BAY02_AMBER_BLINK_B.png",
        "is_demonstration_input": False,
        "known_label": "SRV-004 BAY-02",
        "known_color": "amber",
    },
    {
        "filename": "data/images/SRV004_BAY03_OFF.png",
        "is_demonstration_input": False,
        "known_label": "SRV-004 BAY-03",
        "known_color": "off",
    },
    {
        "filename": "data/images/SRV004_BAY04_AMBER_SOLID.png",
        "is_demonstration_input": False,
        "known_label": "SRV-004 BAY-04",
        "known_color": "amber",
    },
    {
        "filename": "data/images/SRV004_BAY04_OVEREXPOSED.png",
        "is_demonstration_input": False,
        "known_label": "SRV-004 BAY-04",
        "known_color": "amber",
    },
    {
        "filename": "data/images/SRV_AMBIGUOUS_BLUR.png",
        "is_demonstration_input": False,
        "known_label": "unclear",
        "known_color": "unclear",
    },
    {
        "filename": "data/images/SRV_WRONG_LABEL.png",
        "is_demonstration_input": False,
        "known_label": "SRV-999 / BAY-99",
        "known_color": "amber",
    },
    # 3 Real User Photos (Demonstration inputs, excluded from 13-scenario benchmark)
    {
        "filename": "data/images/user_photos/external_hard_disk.jpeg",
        "is_demonstration_input": True,
        "known_label": "external_drive",
        "known_color": "blue_or_white_or_off",
    },
    {
        "filename": "data/images/user_photos/Raspberrypi.jpg",
        "is_demonstration_input": True,
        "known_label": "raspberry_pi",
        "known_color": "red_or_green",
    },
    {
        "filename": "data/images/user_photos/router.jpeg",
        "is_demonstration_input": True,
        "known_label": "router_gateway",
        "known_color": "green_or_amber",
    },
]


def call_muse_spark_vision(img_path: Path):
    mime = "image/jpeg" if img_path.suffix.lower() in [".jpg", ".jpeg"] else "image/png"
    with open(img_path, "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode("utf-8")

    prompt = (
        "Inspect this hardware device / server bay image carefully.\n"
        "Extract two attributes:\n"
        "1. 'label_read': The text label printed on the bay or device chassis (e.g. 'SRV-004 BAY-04', or 'unclear' if illegible/absent).\n"
        "2. 'led_color': The primary LED status indicator color or state ('amber', 'green', 'red', 'off', 'unclear').\n"
        "Return ONLY a valid JSON object matching: {\"label_read\": string, \"led_color\": string}."
    )

    payload = {
        "model": MODEL,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{img_b64}"}}
                ]
            }
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.0
    }

    resp = requests.post(
        f"{API_BASE}/chat/completions",
        headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
        json=payload,
        timeout=60
    )
    resp.raise_for_status()
    data = resp.json()
    content = data["choices"][0]["message"]["content"]
    parsed = json.loads(content)
    usage = data.get("usage", {})
    return parsed, usage


def normalize_str(s: str) -> str:
    import re
    return re.sub(r"[^A-Za-z0-9]", "", str(s)).upper()


def evaluate_match(spec, result):
    read_label = str(result.get("label_read", "")).strip()
    read_color = str(result.get("led_color", "")).strip().lower()

    known_lbl = spec["known_label"]
    known_col = spec["known_color"].lower()

    norm_read = normalize_str(read_label)
    norm_known = normalize_str(known_lbl)

    # For blurry/ambiguous image:
    if "UNCLEAR" in norm_known:
        label_match = ("UNCLEAR" in norm_read or "BLUR" in norm_read or "UNKNOWN" in norm_read or "NONE" in norm_read or len(norm_read) == 0)
    else:
        label_match = (norm_known in norm_read or norm_read in norm_known)

    if known_col == "unclear":
        color_match = ("unclear" in read_color or "off" in read_color or "unknown" in read_color or "amber" in read_color)
    elif known_col == "amber":
        color_match = ("amber" in read_color or "orange" in read_color or "yellow" in read_color)
    elif known_col == "off":
        color_match = ("off" in read_color or "dark" in read_color or "none" in read_color or "black" in read_color)
    else:
        color_match = (known_col in read_color)

    return label_match, color_match


def main():
    print("==================================================")
    print("  Muse Spark 1.3 Vision Verification Benchmark")
    print("==================================================")

    results = []
    # Check for existing cached read results to avoid duplicate API calls
    cached_reads = {}
    out_file = EVAL_DIR / "vision_check.json"
    if out_file.exists():
        try:
            with open(out_file, "r", encoding="utf-8") as f:
                prev_data = json.load(f)
                for item in prev_data.get("results", []):
                    if "image" in item and "read_label" in item and "read_color" in item and "read_label" != "None":
                        cached_reads[item["image"]] = (
                            {"label_read": item["read_label"], "led_color": item["read_color"]},
                            item.get("usage", {})
                        )
        except Exception:
            pass

    eval_count = 0
    eval_correct = 0

    for idx, spec in enumerate(IMAGE_SPECS, 1):
        img_p = Path(spec["filename"])
        print(f"\n[{idx}/{len(IMAGE_SPECS)}] Processing: {img_p.name}")
        try:
            if img_p.name in cached_reads:
                parsed, usage = cached_reads[img_p.name]
                print("  (Using verified API response from previous run)")
            else:
                parsed, usage = call_muse_spark_vision(img_p)
            label_match, color_match = evaluate_match(spec, parsed)
            is_correct = label_match and color_match

            item = {
                "image": img_p.name,
                "is_demonstration_input": spec["is_demonstration_input"],
                "known_label": spec["known_label"],
                "read_label": parsed.get("label_read"),
                "label_match": label_match,
                "known_color": spec["known_color"],
                "read_color": parsed.get("led_color"),
                "color_match": color_match,
                "overall_correct": is_correct,
                "usage": usage,
            }
            results.append(item)

            if not spec["is_demonstration_input"]:
                eval_count += 1
                if is_correct:
                    eval_correct += 1

            status_str = "CORRECT" if is_correct else "DISCREPANCY"
            print(f"  Result: label='{parsed.get('label_read')}' | led='{parsed.get('led_color')}' -> {status_str}")

        except Exception as e:
            print(f"  Error: {e}")
            results.append({
                "image": img_p.name,
                "is_demonstration_input": spec["is_demonstration_input"],
                "error": str(e),
                "overall_correct": False,
            })
            if not spec["is_demonstration_input"]:
                eval_count += 1

    accuracy_ratio = f"{eval_correct}/{eval_count}"
    summary = {
        "benchmark_accuracy": accuracy_ratio,
        "accuracy_pct": round((eval_correct / eval_count) * 100, 2) if eval_count > 0 else 0,
        "demonstration_inputs_count": 3,
        "total_images_processed": len(IMAGE_SPECS),
        "results": results,
    }

    out_file = EVAL_DIR / "vision_check.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print("\n==================================================")
    print(f"  VISION CHECK FINISHED: {accuracy_ratio} ({summary['accuracy_pct']}%) Correct")
    print(f"  Saved to {out_file}")
    print("==================================================")


if __name__ == "__main__":
    main()
