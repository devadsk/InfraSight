"""
Verify that user photos have zero metadata/EXIF tags (Photo Privacy Gate).
"""

from pathlib import Path
from PIL import Image

photo_dir = Path("data/images/user_photos")
photos = sorted([f for f in photo_dir.iterdir() if f.is_file() and f.suffix.lower() in [".jpg", ".jpeg", ".png"]])

print("==================================================")
print("  Photo Metadata & EXIF Privacy Verification")
print("==================================================")

all_clean = True
for p in photos:
    img = Image.open(p)
    exif = img.getexif()
    tag_count = len(exif)
    info_keys = len(img.info.keys())
    print(f"File: {p.name:<25} | EXIF tags: {tag_count} | Info metadata entries: {info_keys}")
    if tag_count > 0:
        all_clean = False

if all_clean:
    print("[SUCCESS] All user photos have 0 EXIF metadata tags.")
else:
    print("[FAIL] Metadata detected in one or more photos.")
