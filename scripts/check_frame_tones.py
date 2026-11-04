#!/usr/bin/env python3
"""Inspect visual contents of frames 001 to 026 in detail."""

import cv2
import numpy as np
from pathlib import Path
import json

SRC_DIR = Path("output/ttd_arcane_characters/episode1_frames/ep01")

for i in range(1, 27):
    p = SRC_DIR / f"frame_{i:03d}.jpg"
    img = cv2.imread(str(p))
    h, w, c = img.shape
    
    # Calculate some color statistics
    b, g, r = cv2.split(img)
    blue_bias = float(np.mean(b) - np.mean(r))
    brightness = float(np.mean(img))
    
    # Simple color classification
    # High blue/cyan vs dark vs warm/gold
    tone = "neutral"
    if brightness < 60:
        tone = "very dark / shadowy"
    elif blue_bias > 15:
        tone = "cool blue / cyan ambient"
    elif blue_bias < -15:
        tone = "warm golden / amber"
        
    print(f"Frame {i:03d}: {w}x{h}, aspect={w/h:.2f}, brightness={brightness:.1f}, tone={tone}")
