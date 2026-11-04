#!/usr/bin/env python3
"""Script to inspect frames 001-026 and extract complete visual and OCR metadata."""

from pathlib import Path
import json
import cv2
import numpy as np
from PIL import Image
import pytesseract

SRC_DIR = Path("output/ttd_arcane_characters/episode1_frames/ep01")
CLEAN_DIR = Path("output/ttd_ep01_manga_transitions/clean_frames")

results = []

for i in range(1, 27):
    src_p = SRC_DIR / f"frame_{i:03d}.jpg"
    clean_p = CLEAN_DIR / f"ep01_frame_{i:03d}_clean.png"

    if not src_p.is_file():
        results.append({"frame": i, "status": "missing"})
        continue

    img = Image.open(src_p)
    w, h = img.size
    aspect = round(w / h, 3)

    # Color analysis
    arr = np.array(img)
    mean_rgb = [round(float(x), 1) for x in arr.mean(axis=(0, 1))]
    std_rgb = [round(float(x), 1) for x in arr.std(axis=(0, 1))]

    # OCR text extraction
    ocr_rus_eng = ""
    try:
        raw_text = pytesseract.image_to_string(img, lang="rus+eng")
        lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
        ocr_rus_eng = "\n".join(lines)
    except Exception as exc:
        ocr_rus_eng = f"ERROR: {exc}"

    clean_info = {}
    if clean_p.is_file():
        c_img = Image.open(clean_p)
        clean_info["clean_size"] = list(c_img.size)
        clean_info["clean_exists"] = True
    else:
        clean_info["clean_exists"] = False

    results.append({
        "frame": i,
        "width": w,
        "height": h,
        "aspect_ratio": aspect,
        "mean_rgb": mean_rgb,
        "std_rgb": std_rgb,
        "ocr_text": ocr_rus_eng,
        "clean_info": clean_info,
    })

out_json = Path("output/ep01_frames_001_026_analysis.json")
with open(out_json, "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

print(f"Analyzed {len(results)} frames. Output saved to {out_json}")
