#!/usr/bin/env python3
"""Detailed visual composition analysis for frames 001 to 026."""

from pathlib import Path
import json
import cv2
import numpy as np
from PIL import Image

SRC_DIR = Path("output/ttd_arcane_characters/episode1_frames/ep01")
CLEAN_DIR = Path("output/ttd_ep01_manga_transitions/clean_frames")

def get_palette(img_bgr, k=4):
    pixels = img_bgr.reshape(-1, 3).astype(np.float32)
    # sample 10000 pixels for speed
    if len(pixels) > 10000:
        idx = np.random.choice(len(pixels), 10000, replace=False)
        pixels = pixels[idx]
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 10, 1.0)
    _, labels, centers = cv2.kmeans(pixels, k, None, criteria, 3, cv2.KMEANS_RANDOM_CENTERS)
    counts = np.bincount(labels.flatten())
    order = np.argsort(-counts)
    palette = []
    for o in order:
        b, g, r = centers[o]
        palette.append({
            "hex": f"#{int(r):02x}{int(g):02x}{int(b):02x}",
            "rgb": [int(r), int(g), int(b)],
            "pct": round(float(counts[o] / len(pixels) * 100), 1)
        })
    return palette

def analyze_frame_visuals(f_num):
    src_p = SRC_DIR / f"frame_{f_num:03d}.jpg"
    clean_p = CLEAN_DIR / f"ep01_frame_{f_num:03d}_clean.png"
    if not src_p.is_file():
        return None
    
    bgr = cv2.imread(str(src_p))
    h, w = bgr.shape[:2]
    
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    
    # Check vertical third luminances
    top_lum = round(float(np.mean(gray[:h//3, :])), 1)
    mid_lum = round(float(np.mean(gray[h//3:2*h//3, :])), 1)
    bot_lum = round(float(np.mean(gray[2*h//3:, :])), 1)
    
    pal = get_palette(bgr, k=4)
    
    # Contrast & edges
    laplacian_var = round(float(cv2.Laplacian(gray, cv2.CV_64F).var()), 1)
    
    return {
        "frame": f_num,
        "width": w,
        "height": h,
        "top_mid_bot_lum": [top_lum, mid_lum, bot_lum],
        "sharpness_laplacian": laplacian_var,
        "palette": pal,
    }

visual_data = []
for i in range(1, 27):
    v = analyze_frame_visuals(i)
    if v:
        visual_data.append(v)

out_path = Path("output/ep01_frames_visual_analysis.json")
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(visual_data, f, indent=2)

print(f"Visual analysis complete for {len(visual_data)} frames -> {out_path}")
