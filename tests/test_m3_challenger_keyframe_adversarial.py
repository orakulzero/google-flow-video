"""tests/test_m3_challenger_keyframe_adversarial.py
Milestone 3 Empirical Challenger 1 (m3_challenger_1) Adversarial Test Suite.
Independently verifies:
1. Background SSIM and MAE drift suppression across all 12 master keyframes.
2. Multi-threshold mask stress tests and corner invariance.
3. Eye spark audit (S > 120, V > 245 count <= 4) and zero glowing eyes on Knight Lucas.
4. Armor crevice spark analysis and hue purity.
5. Bit-for-bit SHA-256 match with persistent brain storage mirror.
6. 100% English-only linguistic hygiene (0 literal Cyrillic characters).
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import cv2
import numpy as np
import pytest

from src.ttd_keyframe_composer import (
    SHOT_SPECS,
    compute_ssim_gray,
    count_spark_pixels,
    create_soft_gaussian_mask,
    TARGET_WIDTH,
    TARGET_HEIGHT,
)

ROOT_DIR = Path(__file__).resolve().parent.parent
KEYFRAMES_DIR = ROOT_DIR / "output" / "ttd_ep01_flow_keyframes"
PLATES_DIR = ROOT_DIR / "output" / "canonical_plates"
VIDEOS_DIR = ROOT_DIR / "output" / "ttd_ep01_flow_videos"
BRAIN_DIR = Path(r"C:\Users\Orakul Grey\.gemini\antigravity\brain\94dd6a04-54e7-4e8c-9551-224cace4f85f")
LUCAS_SHOTS = ["SHOT-03", "SHOT-04", "SHOT-08", "SHOT-11", "SHOT-12"]


def get_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def test_empirical_all_12_keyframes_ssim_mae_drift_suppression() -> None:
    """Calculate independent SSIM and MAE against canonical background plates."""
    assert KEYFRAMES_DIR.is_dir(), f"Missing keyframe directory: {KEYFRAMES_DIR}"
    assert PLATES_DIR.is_dir(), f"Missing plates directory: {PLATES_DIR}"

    for i in range(1, 13):
        shot_id = f"SHOT-{i:02d}"
        fname = f"ttd_ep01_shot_{i:02d}_keyframe.png"
        kf_path = KEYFRAMES_DIR / fname
        assert kf_path.is_file(), f"Missing keyframe file: {fname}"

        kf_bgr = cv2.imread(str(kf_path))
        assert kf_bgr is not None and kf_bgr.shape == (TARGET_HEIGHT, TARGET_WIDTH, 3)

        spec = SHOT_SPECS[shot_id]
        plate_path = PLATES_DIR / spec["bg_plate"]
        assert plate_path.is_file(), f"Missing plate file: {plate_path}"
        plate_bgr = cv2.imread(str(plate_path))
        assert plate_bgr is not None and plate_bgr.shape == (TARGET_HEIGHT, TARGET_WIDTH, 3)

        mask = create_soft_gaussian_mask(spec["ellipses"])
        bg_zone = mask < 0.15

        diff = np.abs(kf_bgr.astype(np.float32) - plate_bgr.astype(np.float32))
        mae_bg = float(np.mean(diff[bg_zone]))
        ssim_bg = compute_ssim_gray(kf_bgr, plate_bgr, mask=bg_zone.astype(np.uint8))

        assert mae_bg <= 6.0, f"{shot_id}: Background MAE {mae_bg:.4f} exceeded upper limit 6.0"
        assert ssim_bg >= 0.85, f"{shot_id}: Background SSIM {ssim_bg:.4f} dropped below lower limit 0.85"


def test_empirical_drift_stress_multi_thresholds_and_corners() -> None:
    """Stress-test background stability across multiple mask thresholds and corners."""
    for i in range(1, 13):
        shot_id = f"SHOT-{i:02d}"
        fname = f"ttd_ep01_shot_{i:02d}_keyframe.png"
        kf_bgr = cv2.imread(str(KEYFRAMES_DIR / fname))
        spec = SHOT_SPECS[shot_id]
        plate_bgr = cv2.imread(str(PLATES_DIR / spec["bg_plate"]))
        mask = create_soft_gaussian_mask(spec["ellipses"])

        diff = np.abs(kf_bgr.astype(np.float32) - plate_bgr.astype(np.float32))

        # Pure background (mask < 0.01)
        pure_bg = mask < 0.01
        mae_pure = float(np.mean(diff[pure_bg]))
        ssim_pure = compute_ssim_gray(kf_bgr, plate_bgr, mask=pure_bg.astype(np.uint8))
        assert mae_pure <= 1.0, f"{shot_id}: Pure background MAE {mae_pure:.4f} > 1.0"
        assert ssim_pure >= 0.99, f"{shot_id}: Pure background SSIM {ssim_pure:.4f} < 0.99"

        # Top-left corner (0:200, 0:300)
        tl_corner = np.zeros_like(mask, dtype=bool)
        tl_corner[0:200, 0:300] = True
        mae_tl = float(np.mean(diff[tl_corner]))
        assert mae_tl <= 1.0, f"{shot_id}: Top-left corner MAE {mae_tl:.4f} > 1.0"


def test_empirical_eye_sparks_and_lucas_glowing_eyes_absence() -> None:
    """Scan eye bounding boxes for illegal arcade sparks (V > 245, S > 120 count <= 4) and glowing eyes."""
    for i in range(1, 13):
        shot_id = f"SHOT-{i:02d}"
        fname = f"ttd_ep01_shot_{i:02d}_keyframe.png"
        kf_bgr = cv2.imread(str(KEYFRAMES_DIR / fname))
        spec = SHOT_SPECS[shot_id]

        x1, y1, x2, y2 = spec["eye_box"]
        eye_crop = kf_bgr[y1:y2, x1:x2]
        hsv_eye = cv2.cvtColor(eye_crop, cv2.COLOR_BGR2HSV)

        # Illegal arcade sparks
        sparks = (hsv_eye[:, :, 1] > 120) & (hsv_eye[:, :, 2] > 245)
        spark_count = int(np.count_nonzero(sparks))
        assert spark_count <= 4, f"{shot_id}: Eye sparks count {spark_count} > 4"

        # Knight Lucas specific assertions
        if shot_id in LUCAS_SHOTS:
            assert spark_count == 0, f"{shot_id} (Lucas): Expected 0 sparks, got {spark_count}"
            # Assert zero glowing eyes: emissive saturated glow (S > 80, V > 240)
            glow_pixels = (hsv_eye[:, :, 1] > 80) & (hsv_eye[:, :, 2] > 240)
            glow_count = int(np.count_nonzero(glow_pixels))
            assert glow_count == 0, f"{shot_id} (Lucas): Found {glow_count} glowing eye pixels"


def test_empirical_armor_crevice_sparks_and_flame_hue_purity() -> None:
    """Assert armor crevices do not contain artificial neon sparks (only natural torch flame)."""
    for shot_id in LUCAS_SHOTS:
        fname = f"ttd_ep01_shot_{int(shot_id.split('-')[1]):02d}_keyframe.png"
        kf_bgr = cv2.imread(str(KEYFRAMES_DIR / fname))
        hsv = cv2.cvtColor(kf_bgr, cv2.COLOR_BGR2HSV)

        # Neon arcade spark signature: Hue between 75 and 165 (cyan, blue, magenta) with high S and V
        neon_sparks = (hsv[:, :, 0] >= 75) & (hsv[:, :, 0] <= 165) & (hsv[:, :, 1] > 100) & (hsv[:, :, 2] > 220)
        neon_count = int(np.count_nonzero(neon_sparks))
        assert neon_count == 0, f"{shot_id}: Found {neon_count} illegal neon arcade sparks"


def test_empirical_brain_mirror_bit_for_bit_parity() -> None:
    """Verify bit-for-bit SHA-256 match between local deliverables and persistent brain storage."""
    assert BRAIN_DIR.is_dir(), f"Brain mirror directory missing: {BRAIN_DIR}"

    for i in range(1, 13):
        fname = f"ttd_ep01_shot_{i:02d}_keyframe.png"
        src_p = KEYFRAMES_DIR / fname
        dst_p = BRAIN_DIR / fname
        assert src_p.is_file(), f"Source keyframe missing: {src_p}"
        assert dst_p.is_file(), f"Mirrored keyframe missing: {dst_p}"
        assert get_sha256(src_p) == get_sha256(dst_p), f"SHA-256 mismatch for {fname}"


def test_empirical_upper_sky_text_variance_zero_model_sheet_glyphs() -> None:
    """Assert upper sky Laplacian variance <= 180.0 in SHOT-08, 11, and 12 (no '3/4 ANGLE' glyphs)."""
    for sid in [8, 11, 12]:
        fname = f"ttd_ep01_shot_{sid:02d}_keyframe.png"
        img = cv2.imread(str(KEYFRAMES_DIR / fname))
        sky = img[:150, 350:900]
        gray = cv2.cvtColor(sky, cv2.COLOR_BGR2GRAY)
        lap_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        assert lap_var <= 180.0, f"SHOT-{sid:02d}: sky Laplacian variance {lap_var:.2f} > 180.0"


def test_empirical_differential_paper_halo_and_edge_retention() -> None:
    """Assert differential paper halo ratio Phi_paper <= 0.005 and edge retention R_edge in [0.90, 1.15]."""
    for sid in range(1, 13):
        shot_id = f"SHOT-{sid:02d}"
        spec = SHOT_SPECS[shot_id]
        kf = cv2.imread(str(KEYFRAMES_DIR / f"ttd_ep01_shot_{sid:02d}_keyframe.png"))
        pl = cv2.imread(str(PLATES_DIR / spec["bg_plate"]))
        mask = create_soft_gaussian_mask(spec["ellipses"])
        omega_env = mask < 0.15

        lap_kf = np.abs(cv2.Laplacian(cv2.cvtColor(kf, cv2.COLOR_BGR2GRAY), cv2.CV_64F))
        lap_pl = np.abs(cv2.Laplacian(cv2.cvtColor(pl, cv2.COLOR_BGR2GRAY), cv2.CV_64F))
        r_edge = float(np.sum(lap_kf[omega_env]) / (np.sum(lap_pl[omega_env]) + 1e-6))
        assert 0.90 <= r_edge <= 1.15, f"{shot_id}: Edge retention {r_edge:.4f} outside [0.90, 1.15]"

        hsv_pl = cv2.cvtColor(pl, cv2.COLOR_BGR2HSV)
        paper_pl = (hsv_pl[:, :, 2] > 175) & (hsv_pl[:, :, 1] < 45) & omega_env
        hsv_kf = cv2.cvtColor(kf, cv2.COLOR_BGR2HSV)
        paper_kf = (hsv_kf[:, :, 2] > 175) & (hsv_kf[:, :, 1] < 45) & omega_env
        delta_paper = float(np.sum(paper_kf & (~paper_pl)) / np.sum(omega_env))
        assert delta_paper <= 0.005, f"{shot_id}: Delta paper halo {delta_paper:.5f} > 0.005"


def test_empirical_multi_character_connectedness_and_anti_severed_limbs() -> None:
    """Assert multi-character primary masses capture >= 95% of foreground in SHOT-08 and SHOT-12."""
    for sid in [8, 12]:
        shot_id = f"SHOT-{sid:02d}"
        spec = SHOT_SPECS[shot_id]
        kf = cv2.imread(str(KEYFRAMES_DIR / f"ttd_ep01_shot_{sid:02d}_keyframe.png"))
        pl = cv2.imread(str(PLATES_DIR / spec["bg_plate"]))
        diff = np.mean(np.abs(kf.astype(np.float32) - pl.astype(np.float32)), axis=2)
        fg_mask = (diff > 10.0).astype(np.uint8)
        num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(fg_mask)
        areas = stats[1:, cv2.CC_STAT_AREA]
        sorted_areas = sorted(areas, reverse=True)
        top2_area = sum(sorted_areas[:2])
        total_area = sum(areas)
        mass_ratio = top2_area / (total_area + 1e-6)
        assert mass_ratio >= 0.95, f"{shot_id}: Primary mass ratio {mass_ratio:.3f} < 0.95"


def test_empirical_zero_cyrillic_hygiene() -> None:
    """Enforce 100% English-only characters (0 Cyrillic) in this test suite."""
    text = Path(__file__).read_text(encoding="utf-8")
    cyrillic_matches = re.findall(r"[\u0400-\u04FF]", text)
    assert len(cyrillic_matches) == 0, f"Found {len(cyrillic_matches)} Cyrillic characters in {Path(__file__).name}"

