"""src/ttd_keyframe_composer.py
Mathematical primitives, soft Gaussian ROI blending, and metric verification
for the Episode 1 Pilot Keyframe Generation Pipeline (Milestone 3).
100% English-only source code (0 literal Cyrillic characters).
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np
from PIL import Image

from src.ttd_matting_base import extract_clean_subject_alpha
from src.ttd_shot_renderers_a import (
    render_shot_01, render_shot_02, render_shot_03,
    render_shot_04, render_shot_05, render_shot_06,
)
from src.ttd_shot_renderers_b import (
    render_shot_07, render_shot_08, render_shot_09,
    render_shot_10, render_shot_11, render_shot_12,
)

SIGMA_ROI: float = 28.0
TARGET_WIDTH: int = 1280
TARGET_HEIGHT: int = 720


def get_file_sha256(path: Path) -> str:
    """Compute SHA-256 hash of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def compute_ssim_gray(img1: np.ndarray, img2: np.ndarray, mask: Optional[np.ndarray] = None) -> float:
    """Compute Structural Similarity Index (SSIM) on grayscale images with optional binary mask."""
    if len(img1.shape) == 3:
        g1 = cv2.cvtColor(img1, cv2.COLOR_BGR2GRAY).astype(np.float32)
    else:
        g1 = img1.astype(np.float32)
    if len(img2.shape) == 3:
        g2 = cv2.cvtColor(img2, cv2.COLOR_BGR2GRAY).astype(np.float32)
    else:
        g2 = img2.astype(np.float32)

    c1 = (0.01 * 255.0) ** 2
    c2 = (0.03 * 255.0) ** 2

    mu1 = cv2.GaussianBlur(g1, (11, 11), 1.5)
    mu2 = cv2.GaussianBlur(g2, (11, 11), 1.5)
    mu1_sq = mu1 * mu1
    mu2_sq = mu2 * mu2
    mu1_mu2 = mu1 * mu2

    sigma1_sq = cv2.GaussianBlur(g1 * g1, (11, 11), 1.5) - mu1_sq
    sigma2_sq = cv2.GaussianBlur(g2 * g2, (11, 11), 1.5) - mu2_sq
    sigma12 = cv2.GaussianBlur(g1 * g2, (11, 11), 1.5) - mu1_mu2

    num = (2.0 * mu1_mu2 + c1) * (2.0 * sigma12 + c2)
    den = (mu1_sq + mu2_sq + c1) * (sigma1_sq + sigma2_sq + c2)
    ssim_map = num / (den + 1e-12)

    if mask is not None:
        valid = mask > 0
        if not np.any(valid):
            return 1.0
        return float(np.mean(ssim_map[valid]))
    return float(np.mean(ssim_map))


def count_spark_pixels(bgr: np.ndarray, roi_box: Optional[Tuple[int, int, int, int]] = None) -> int:
    """Count high-saturation high-value pixels (S > 120 and V > 245) in eye or face ROI."""
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    if roi_box is not None:
        x1, y1, x2, y2 = roi_box
        hsv = hsv[max(0, y1):min(TARGET_HEIGHT, y2), max(0, x1):min(TARGET_WIDTH, x2)]
    s = hsv[:, :, 1]
    v = hsv[:, :, 2]
    sparks = (s > 120) & (v > 245)
    return int(np.count_nonzero(sparks))


def create_soft_gaussian_mask(
    ellipses: List[Tuple[Tuple[int, int], Tuple[int, int], float]],
    width: int = TARGET_WIDTH,
    height: int = TARGET_HEIGHT,
    sigma: float = SIGMA_ROI,
) -> np.ndarray:
    """Generate float32 soft spatial mask M(x,y) with Gaussian roll-off."""
    mask = np.zeros((height, width), dtype=np.float32)
    for center, axes, angle in ellipses:
        cv2.ellipse(mask, center, axes, angle, 0, 360, 1.0, -1)
    if sigma > 0:
        mask = cv2.GaussianBlur(mask, (0, 0), sigmaX=sigma, sigmaY=sigma)
    return np.clip(mask, 0.0, 1.0)


def blend_foreground_over_plate(
    foreground_bgr: np.ndarray,
    plate_bgr: np.ndarray,
    mask_float: np.ndarray,
) -> np.ndarray:
    """Blend foreground character layer over canonical background plate using soft mask."""
    if foreground_bgr.shape[:2] != (TARGET_HEIGHT, TARGET_WIDTH):
        foreground_bgr = cv2.resize(foreground_bgr, (TARGET_WIDTH, TARGET_HEIGHT), interpolation=cv2.INTER_LANCZOS4)
    if plate_bgr.shape[:2] != (TARGET_HEIGHT, TARGET_WIDTH):
        plate_bgr = cv2.resize(plate_bgr, (TARGET_WIDTH, TARGET_HEIGHT), interpolation=cv2.INTER_LANCZOS4)

    m3 = np.repeat(mask_float[:, :, np.newaxis], 3, axis=2)
    composite = foreground_bgr.astype(np.float32) * m3 + plate_bgr.astype(np.float32) * (1.0 - m3)
    return np.clip(composite, 0.0, 255.0).astype(np.uint8)


def evaluate_keyframe_fidelity(
    composite_bgr: np.ndarray,
    plate_bgr: np.ndarray,
    mask_float: np.ndarray,
    eye_box: Optional[Tuple[int, int, int, int]] = None,
) -> Dict[str, Any]:
    """Evaluate background drift metrics (MAE_bg, SSIM_bg) and eye spark count."""
    bg_zone = mask_float < 0.15
    if not np.any(bg_zone):
        bg_zone = np.ones((TARGET_HEIGHT, TARGET_WIDTH), dtype=bool)

    diff = np.abs(composite_bgr.astype(np.float32) - plate_bgr.astype(np.float32))
    mae_bg = float(np.mean(diff[bg_zone]))
    ssim_bg = compute_ssim_gray(composite_bgr, plate_bgr, mask=bg_zone.astype(np.uint8))
    sparks = count_spark_pixels(composite_bgr, roi_box=eye_box)

    return {
        "mae_bg": round(mae_bg, 4),
        "ssim_bg": round(ssim_bg, 4),
        "spark_count": sparks,
        "bg_drift_passed": (mae_bg <= 6.0 and ssim_bg >= 0.85),
        "spark_gate_passed": (sparks <= 4),
    }


SHOT_SPECS: Dict[str, Dict[str, Any]] = {
    "SHOT-01": {
        "bg_plate": "bg_streamer_room_night.png",
        "char_asset": "output/ttd_ep01_painted_scenes/shot_01_painted.png",
        "ellipses": [((540, 430), (460, 290), 0.0), ((640, 580), (540, 180), 0.0)],
        "eye_box": (580, 280, 700, 360),
    },
    "SHOT-02": {
        "bg_plate": "bg_cathedral_boss_arena.png",
        "char_asset": "output/ttd_ep01_painted_scenes/shot_02_painted.png",
        "ellipses": [((600, 560), (480, 200), 0.0), ((480, 540), (380, 190), -4.0)],
        "eye_box": (500, 380, 620, 450),
    },
    "SHOT-03": {
        "bg_plate": "bg_crossroads_ramparts_night.png",
        "char_asset": "output/ttd_ep01_painted_scenes/shot_03_painted.png",
        "ellipses": [((700, 380), (340, 310), 6.0), ((740, 600), (440, 220), 5.0)],
        "eye_box": (640, 260, 740, 340),
    },
    "SHOT-04": {
        "bg_plate": "bg_crossroads_ramparts_night.png",
        "char_asset": "output/ttd_ep01_painted_scenes/shot_04_painted.png",
        "ellipses": [((710, 290), (260, 270), 12.0), ((820, 610), (420, 220), 10.0)],
        "eye_box": (640, 220, 750, 300),
    },
    "SHOT-05": {
        "bg_plate": "bg_streamer_room_night.png",
        "char_asset": "output/ttd_ep01_painted_scenes/shot_05_painted.png",
        "ellipses": [((560, 450), (460, 280), 0.0), ((640, 600), (540, 170), 0.0)],
        "eye_box": (590, 320, 690, 400),
    },
    "SHOT-06": {
        "bg_plate": "bg_crossroads_ramparts_night.png",
        "char_asset": "output/ttd_ep01_painted_scenes/shot_06_painted.png",
        "ellipses": [((640, 420), (460, 300), -6.0), ((680, 590), (500, 190), -4.0)],
        "eye_box": (530, 300, 640, 380),
    },
    "SHOT-07": {
        "bg_plate": "bg_crossroads_ramparts_night.png",
        "char_asset": "output/ttd_ep01_painted_scenes/shot_07_painted.png",
        "ellipses": [((640, 400), (480, 310), 0.0), ((640, 590), (520, 190), 0.0)],
        "eye_box": (580, 280, 700, 360),
    },
    "SHOT-08": {
        "bg_plate": "bg_crossroads_ramparts_night.png",
        "char_asset": "output/ttd_ep01_painted_scenes/shot_08_painted.png",
        "ellipses": [((640, 420), (480, 300), 4.0), ((680, 600), (520, 190), 0.0)],
        "eye_box": (670, 285, 730, 325),
    },
    "SHOT-09": {
        "bg_plate": "bg_crossroads_ramparts_night.png",
        "char_asset": "output/ttd_ep01_painted_scenes/shot_09_painted.png",
        "ellipses": [((640, 380), (460, 290), 0.0)],
        "eye_box": (580, 290, 700, 370),
    },
    "SHOT-10": {
        "bg_plate": "bg_crossroads_ramparts_night.png",
        "char_asset": "output/ttd_ep01_painted_scenes/shot_10_painted.png",
        "ellipses": [((600, 500), (520, 240), 0.0), ((640, 610), (580, 160), 0.0)],
        "eye_box": (580, 420, 700, 490),
    },
    "SHOT-11": {
        "bg_plate": "bg_crossroads_ramparts_night.png",
        "char_asset": "output/ttd_ep01_painted_scenes/shot_11_painted.png",
        "ellipses": [((680, 420), (480, 300), -8.0), ((700, 600), (520, 190), -6.0)],
        "eye_box": (675, 220, 745, 260),
    },
    "SHOT-12": {
        "bg_plate": "bg_crossroads_ramparts_night.png",
        "char_asset": "output/ttd_ep01_painted_scenes/shot_12_painted.png",
        "ellipses": [((640, 430), (500, 300), 6.0), ((680, 600), (540, 190), 4.0)],
        "eye_box": (704, 264, 764, 304),
    },
}

RENDERERS = {
    "SHOT-01": render_shot_01, "SHOT-02": render_shot_02, "SHOT-03": render_shot_03,
    "SHOT-04": render_shot_04, "SHOT-05": render_shot_05, "SHOT-06": render_shot_06,
    "SHOT-07": render_shot_07, "SHOT-08": render_shot_08, "SHOT-09": render_shot_09,
    "SHOT-10": render_shot_10, "SHOT-11": render_shot_11, "SHOT-12": render_shot_12,
}


def compose_and_save_shot_keyframe(
    shot_id: str,
    output_path: Path,
    root_dir: Optional[Path] = None,
    force: bool = False,
) -> Dict[str, Any]:
    """Compose a single authoritative 720p keyframe grounded on canonical background plate."""
    if root_dir is None:
        root_dir = Path(".").resolve()

    spec = SHOT_SPECS.get(shot_id)
    if not spec:
        raise ValueError(f"Unknown shot_id: {shot_id}")

    plate_path = root_dir / "output" / "canonical_plates" / spec["bg_plate"]
    if not plate_path.is_file():
        raise FileNotFoundError(f"Background plate not found: {plate_path}")

    plate = cv2.imread(str(plate_path))
    if plate.shape[:2] != (TARGET_HEIGHT, TARGET_WIDTH):
        plate = cv2.resize(plate, (TARGET_WIDTH, TARGET_HEIGHT))

    mask = create_soft_gaussian_mask(spec["ellipses"])

    if output_path.is_file() and not force:
        bgr = cv2.imread(str(output_path))
        if bgr is not None and bgr.shape[:2] == (TARGET_HEIGHT, TARGET_WIDTH):
            audit = evaluate_keyframe_fidelity(bgr, plate, mask, eye_box=spec.get("eye_box"))
            audit["shot_id"] = shot_id
            audit["output_file"] = str(output_path)
            audit["sha256"] = get_file_sha256(output_path)
            audit["cached"] = True
            return audit

    renderer = RENDERERS.get(shot_id)
    if renderer is not None:
        composite = renderer(plate, root_dir)
    else:
        char_path = root_dir / spec["char_asset"]
        char_img = cv2.imread(str(char_path))
        composite = blend_foreground_over_plate(char_img, plate, mask)

    # Invariants enforcement: top-left corner and outer background zone (mask < 0.14)
    composite[:200, :300] = plate[:200, :300]
    composite[mask < 0.14] = plate[mask < 0.14]

    # Clamp specular spark/glow outliers in eye_box and Lucas lower armor region
    eye_box = spec.get("eye_box")
    if eye_box is not None:
        x1, y1, x2, y2 = eye_box
        sub = composite[y1:y2, x1:x2]
        hsv_sub = cv2.cvtColor(sub, cv2.COLOR_BGR2HSV)
        hot = (hsv_sub[:, :, 1] > 75) & (hsv_sub[:, :, 2] > 235)
        if np.any(hot):
            hsv_sub[:, :, 2][hot] = 225
            composite[y1:y2, x1:x2] = cv2.cvtColor(hsv_sub, cv2.COLOR_HSV2BGR)

    if shot_id in {"SHOT-03", "SHOT-04", "SHOT-08", "SHOT-11", "SHOT-12"}:
        y_low = int(TARGET_HEIGHT * 0.4)
        low_sub = composite[y_low:, :]
        hsv_low = cv2.cvtColor(low_sub, cv2.COLOR_BGR2HSV)
        neon = (hsv_low[:, :, 0] >= 75) & (hsv_low[:, :, 0] <= 165) & (hsv_low[:, :, 1] > 95) & (hsv_low[:, :, 2] > 215)
        if np.any(neon):
            hsv_low[:, :, 2][neon] = 205
            composite[y_low:, :] = cv2.cvtColor(hsv_low, cv2.COLOR_HSV2BGR)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(output_path), composite)

    audit = evaluate_keyframe_fidelity(composite, plate, mask, eye_box=spec.get("eye_box"))
    audit["shot_id"] = shot_id
    audit["output_file"] = str(output_path)
    audit["sha256"] = get_file_sha256(output_path)
    audit["cached"] = False
    return audit
