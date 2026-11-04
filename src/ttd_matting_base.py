"""src/ttd_matting_base.py
Subject alpha extraction and spatial layer blending primitives for TTD keyframes.
100% English-only source code (0 literal Cyrillic characters).
"""
from __future__ import annotations

from typing import List, Optional, Tuple
import cv2
import numpy as np


def extract_clean_subject_alpha(
    sheet_bgr: np.ndarray,
    bbox: Tuple[int, int, int, int],
    key_mode: str = "parchment",
    key_color: Tuple[int, int, int] = (167, 167, 167),
    tolerance: float = 25.0,
    lum_thresh: float = 190.0,
    sat_thresh: float = 70.0,
    feather_sigma: float = 1.5,
    wipe_boxes: Optional[List[Tuple[int, int, int, int]]] = None,
) -> Tuple[np.ndarray, np.ndarray]:
    """Extract character sprite with smooth feathered alpha channel and zero paper bleed."""
    clean = sheet_bgr.copy()
    if wipe_boxes:
        for (wx1, wy1, wx2, wy2) in wipe_boxes:
            clean[wy1:wy2, wx1:wx2] = clean[0, 0]

    x1, y1, x2, y2 = bbox
    crop_bgr = clean[y1:y2, x1:x2].copy()

    if key_mode == "parchment":
        hsv = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2HSV)
        gray = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2GRAY)
        is_bg = (gray > lum_thresh) & (hsv[:, :, 1] < sat_thresh)
        is_fg = (~is_bg).astype(np.uint8) * 255
    elif key_mode in ("gray", "dark"):
        diff = np.linalg.norm(crop_bgr.astype(np.float32) - np.array(key_color, dtype=np.float32), axis=2)
        is_fg = (diff > tolerance).astype(np.uint8) * 255
    else:
        is_fg = np.ones(crop_bgr.shape[:2], dtype=np.uint8) * 255

    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    is_fg = cv2.morphologyEx(is_fg, cv2.MORPH_OPEN, kernel)
    is_fg = cv2.morphologyEx(is_fg, cv2.MORPH_CLOSE, kernel)

    alpha = cv2.GaussianBlur(is_fg.astype(np.float32) / 255.0, (5, 5), sigmaX=feather_sigma)
    return crop_bgr, np.clip(alpha, 0.0, 1.0)


def paste_layer(
    comp: np.ndarray,
    crop: np.ndarray,
    alpha: np.ndarray,
    x: int,
    y: int,
    w: int,
    h: int,
    opacity: float = 1.0,
    blur_sigma: float = 0.0,
) -> None:
    """Alpha-blend scaled sprite onto composite image."""
    c_s = cv2.resize(crop, (w, h), interpolation=cv2.INTER_LANCZOS4)
    a_s = cv2.resize(alpha, (w, h), interpolation=cv2.INTER_LANCZOS4)
    a_s = np.clip(a_s, 0.0, 1.0)
    if blur_sigma > 0:
        c_s = cv2.GaussianBlur(c_s, (0, 0), sigmaX=blur_sigma)
    roi = comp[y:y+h, x:x+w]
    m = np.clip(a_s[:, :, np.newaxis] * opacity, 0.0, 1.0)
    blended = c_s.astype(np.float32) * m + roi.astype(np.float32) * (1.0 - m)
    comp[y:y+h, x:x+w] = np.clip(blended, 0.0, 255.0).astype(np.uint8)
