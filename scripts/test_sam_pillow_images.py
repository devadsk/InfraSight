"""
Evaluate SAM 3.1 on 3 generated Pillow server bay images (Phase 1 Fix 6 Gate).
Images:
1. data/images/SRV004_BAY04_AMBER_SOLID.png
2. data/images/SRV001_BAY02_GREEN.png
3. data/images/SRV003_BAY01_RED.png

Concepts tested per image:
- 'drive tray' (macro component)
- 'rectangle' (shape / border)
- 'LED indicator' (micro target)
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
SAM_MODEL = os.getenv("META_SAM_MODEL", "sam-3.1")

images = [
    "data/images/SRV004_BAY04_AMBER_SOLID.png",
    "data/images/SRV001_BAY02_GREEN.png",
    "data/images/SRV003_BAY01_RED.png",
]
concepts = ["drive tray", "rectangle", "LED indicator"]

print("==================================================")
print("  SAM 3.1 Gate Evaluation on 3 Generated Images")
print("==================================================")

results = []

for img_path in images:
    print(f"\nImage: {img_path}")
    with open(img_path, "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode("utf-8")
    data_url = f"data:image/png;base64,{img_b64}"

    for concept in concepts:
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
                timeout=45
            )
            data = resp.json()
            text_content = ""
            for block in data.get("output", []):
                for c in block.get("content", []):
                    if c.get("type") == "output_text":
                        text_content += c.get("text", "")

            matched = len(text_content) > 0 and "<|box;" in text_content
            box_count = text_content.count("<|box;")
            res_item = {
                "image": Path(img_path).name,
                "concept": concept,
                "status_code": resp.status_code,
                "matched": matched,
                "box_count": box_count,
                "sample_marker": text_content[:100] if matched else None
            }
            results.append(res_item)
            mark_str = f"MATCH ({box_count} boxes)" if matched else "NO MATCH"
            print(f"  Concept '{concept}': {mark_str}")
        except Exception as e:
            print(f"  Concept '{concept}': ERROR ({e})")
            results.append({"image": Path(img_path).name, "concept": concept, "matched": False, "error": str(e)})

# Summary table
print("\n=== SUMMARY TABLE ===")
print("| Image | Concept | Matched | Boxes Detected |")
print("|---|---|---|---|")
for r in results:
    m = "YES" if r.get("matched") else "NO"
    bc = r.get("box_count", 0)
    print(f"| {r['image']} | {r['concept']} | {m} | {bc} |")

# Determine SAM gate outcome
led_matches = [r for r in results if r["concept"] == "LED indicator" and r.get("matched")]
macro_matches = [r for r in results if r["concept"] in ["drive tray", "rectangle"] and r.get("matched")]

print(f"\nGate analysis: Macro objects matched in {len(macro_matches)} requests. Small LED indicators matched in {len(led_matches)} requests.")
if len(led_matches) == 0:
    print("GATE OUTCOME: Concept 'LED indicator' returns 0 matches on small synthetic renders.")
    print("ACTION: Per Addendum 2.2 Gate rules, system will use Macro SAM / Bounding Box + Deterministic Pixel Hue Analysis, with Spark-only fallback labelled clearly.")
