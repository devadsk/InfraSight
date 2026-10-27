"""
SAM 3.1 Test & Overlay Generator (Part A, Item 3).
Tests concepts 'LED' and 'drive tray' across 3 generated images:
1. data/images/SRV004_BAY04_AMBER_SOLID.png
2. data/images/SRV001_BAY02_GREEN.png
3. data/images/SRV003_BAY01_RED.png

Saves:
- Raw JSON responses in docs/sam_samples/
- Overlay images in docs/sam_samples/
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

OUT_DIR = Path("docs/sam_samples")
OUT_DIR.mkdir(parents=True, exist_ok=True)

test_images = [
    "data/images/SRV004_BAY04_AMBER_SOLID.png",
    "data/images/SRV001_BAY02_GREEN.png",
    "data/images/SRV003_BAY01_RED.png"
]
concepts = ["LED", "drive tray"]


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
    print("  SAM 3.1 Verification on Concepts 'LED' & 'drive tray'")
    print("==================================================")

    results_summary = []

    for img_path_str in test_images:
        img_p = Path(img_path_str)
        stem = img_p.stem
        print(f"\nProcessing image: {img_p.name}")

        with open(img_p, "rb") as f:
            b64_str = base64.b64encode(f.read()).decode("utf-8")
        data_url = f"data:image/png;base64,{b64_str}"

        # Base image for drawing overlay
        overlay_img = Image.open(img_p).convert("RGB")
        draw = ImageDraw.Draw(overlay_img)

        img_results = {"image": img_p.name, "concepts": {}}
        detected_any = False

        for c in concepts:
            payload = {
                "model": SAM_MODEL,
                "input": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "input_text", "text": c},
                            {"type": "input_image", "image_url": data_url}
                        ]
                    }
                ]
            }

            resp = requests.post(
                f"{API_BASE}/responses",
                headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
                json=payload,
                timeout=45
            )

            raw_file = OUT_DIR / f"raw_sam_{stem}_{c.replace(' ', '_')}.json"
            data = resp.json()
            raw_file.write_text(json.dumps(data, indent=2), encoding="utf-8")

            # Extract output text
            text_content = ""
            for block in data.get("output", []):
                for item in block.get("content", []):
                    if item.get("type") == "output_text":
                        text_content += item.get("text", "")

            boxes = parse_boxes(text_content)
            img_results["concepts"][c] = {
                "box_count": len(boxes),
                "boxes": boxes,
                "text_snippet": text_content[:80] if text_content else "EMPTY"
            }
            print(f"  Concept '{c}': {len(boxes)} boxes detected. Marker text length: {len(text_content)}")

            if boxes:
                detected_any = True
                for b in boxes:
                    draw.rectangle([(b["x1"], b["y1"]), (b["x2"], b["y2"])], outline=(0, 255, 0), width=2)
                    draw.text((b["x1"] + 2, b["y1"] + 2), f"SAM:{c}", fill=(0, 255, 0))

        if not detected_any:
            # Explicitly annotate fallback on the overlay
            draw.rectangle([(10, 10), (246, 35)], fill=(40, 20, 20), outline=(255, 60, 60))
            draw.text((15, 16), "SAM 3.1: 0 matches (Fallback active)", fill=(255, 200, 200))

        overlay_out_path = OUT_DIR / f"overlay_{stem}.png"
        overlay_img.save(overlay_out_path)
        print(f"  Saved overlay image -> {overlay_out_path}")
        results_summary.append(img_results)

    # Save summary report
    summary_file = OUT_DIR / "sam_gate_results.json"
    summary_file.write_text(json.dumps(results_summary, indent=2), encoding="utf-8")
    print(f"\nWrote {summary_file}")


if __name__ == "__main__":
    main()
