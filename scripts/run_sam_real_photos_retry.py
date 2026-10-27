"""
SAM 3.1 Retry on 3 Real User Photos (Part A Step 0).
Budget limit: exactly 6 calls total.
Concepts: "LED", "light", "indicator light", "small circle".
Photos:
1. data/images/user_photos/external_hard_disk.jpeg
2. data/images/user_photos/Raspberrypi.jpg
3. data/images/user_photos/router.jpeg

Saves:
- Raw JSON responses in docs/sam_samples/real_photos_retry/
- Overlay images in docs/sam_samples/real_photos_retry/
"""

import base64
import json
import os
import re
import requests
from pathlib import Path
from dotenv import load_dotenv
from PIL import Image, ImageDraw

load_dotenv()
API_KEY = os.getenv("META_API_KEY")
API_BASE = os.getenv("META_API_BASE", "https://api.meta.ai/v1")
SAM_MODEL = os.getenv("META_SAM_MODEL", "sam-3.1")

OUT_DIR = Path("docs/sam_samples/real_photos_retry")
OUT_DIR.mkdir(parents=True, exist_ok=True)

CALL_PLAN = [
    {"photo": "data/images/user_photos/external_hard_disk.jpeg", "concept": "LED"},
    {"photo": "data/images/user_photos/external_hard_disk.jpeg", "concept": "light"},
    {"photo": "data/images/user_photos/Raspberrypi.jpg", "concept": "LED"},
    {"photo": "data/images/user_photos/Raspberrypi.jpg", "concept": "indicator light"},
    {"photo": "data/images/user_photos/router.jpeg", "concept": "LED"},
    {"photo": "data/images/user_photos/router.jpeg", "concept": "small circle"},
]

assert len(CALL_PLAN) <= 6, "SAM budget strictly capped at 6 calls!"


def parse_boxes(sam_text: str):
    """
    Extracts box coordinates from SAM marker text:
    <|box;x1=...;y1=...;x2=...;y2=...;w=...;h=...|>
    """
    pattern = r"<\|box;x1=(\d+);y1=(\d+);x2=(\d+);y2=(\d+);w=(\d+);h=(\d+)\|>"
    matches = re.findall(pattern, sam_text)
    boxes = []
    for m in matches:
        boxes.append({
            "x1": int(m[0]),
            "y1": int(m[1]),
            "x2": int(m[2]),
            "y2": int(m[3]),
            "w": int(m[4]),
            "h": int(m[5]),
        })
    return boxes


def main():
    print("==================================================")
    print("  SAM 3.1 Real Photo Retry (Max 6 Calls Budget)")
    print("==================================================")

    results = []

    for idx, item in enumerate(CALL_PLAN, 1):
        photo_path = Path(item["photo"])
        concept = item["concept"]
        print(f"\n[Call {idx}/6] Photo: {photo_path.name} | Concept: '{concept}'")

        # Open and resize photo if extremely large to prevent payload timeouts, preserving aspect ratio
        with Image.open(photo_path) as img:
            img_rgb = img.convert("RGB")
            # Downscale if max dimension > 1280 to keep request fast and well within payload limits
            max_dim = max(img_rgb.size)
            if max_dim > 1280:
                scale = 1280 / max_dim
                new_size = (int(img_rgb.width * scale), int(img_rgb.height * scale))
                working_img = img_rgb.resize(new_size, Image.Resampling.LANCZOS)
            else:
                working_img = img_rgb.copy()

        import io
        buf = io.BytesIO()
        working_img.save(buf, format="JPEG", quality=90)
        img_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
        data_url = f"data:image/jpeg;base64,{img_b64}"

        payload = {
            "model": SAM_MODEL,
            "input": [
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": concept},
                        {"type": "input_image", "image_url": data_url}
                    ]
                }
            ]
        }

        try:
            resp = requests.post(
                f"{API_BASE}/responses",
                headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
                json=payload,
                timeout=60
            )
            data = resp.json()

            # Save raw response
            call_stem = f"call_{idx}_{photo_path.stem}_{concept.replace(' ', '_')}"
            raw_file = OUT_DIR / f"{call_stem}_response.json"
            with open(raw_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)

            text_content = ""
            for block in data.get("output", []):
                for c in block.get("content", []):
                    if c.get("type") == "output_text":
                        text_content += c.get("text", "")

            boxes = parse_boxes(text_content)
            matched = len(boxes) > 0

            # Draw overlay
            overlay = working_img.copy()
            draw = ImageDraw.Draw(overlay)
            for b in boxes:
                # Meta coordinates are typically normalized or in image coordinate space
                draw.rectangle([b["x1"], b["y1"], b["x2"], b["y2"]], outline="cyan", width=3)
                draw.text((b["x1"] + 2, max(0, b["y1"] - 12)), f"{concept}", fill="cyan")

            overlay_file = OUT_DIR / f"{call_stem}_overlay.jpg"
            overlay.save(overlay_file, format="JPEG", quality=90)

            print(f"  Status: {resp.status_code} | Boxes found: {len(boxes)} | Overlay saved: {overlay_file.name}")
            results.append({
                "call": idx,
                "photo": photo_path.name,
                "concept": concept,
                "status_code": resp.status_code,
                "box_count": len(boxes),
                "matched": matched,
                "overlay_file": str(overlay_file)
            })

        except Exception as e:
            print(f"  Error: {e}")
            results.append({
                "call": idx,
                "photo": photo_path.name,
                "concept": concept,
                "error": str(e),
                "box_count": 0,
                "matched": False
            })

    # Save summary
    summary_file = OUT_DIR / "sam_retry_summary.json"
    with open(summary_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print("\n==================================================")
    print("  SAM 3.1 RETRY SUMMARY (Final Decision Gate)")
    print("==================================================")
    total_boxes = sum(r.get("box_count", 0) for r in results)
    for r in results:
        status_str = f"{r.get('box_count', 0)} boxes" if r.get("matched") else "0 boxes (no match)"
        print(f"Call {r['call']}: {r['photo']} with '{r['concept']}' -> {status_str}")

    print(f"\nTotal SAM calls made: {len(results)}/6")
    print(f"Total boxes detected: {total_boxes}")
    print("Decision is final: SAM retry completed, no further SAM budget will be expended.")


if __name__ == "__main__":
    main()
