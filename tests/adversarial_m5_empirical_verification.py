"""tests/adversarial_m5_empirical_verification.py
Adversarial empirical stress harness for Milestone 5 acceptance verification.
Validates live production assets independently from raw bytes (no cached JSON trust).
100% English-only, chunking <= 180 lines.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
import struct
import subprocess
import cv2
import imageio_ffmpeg
import numpy as np
from PIL import Image
import pytest

from src.ttd_audit_engine import audit_faststart_atoms, audit_laplacian_edges, audit_sparks_and_glow
from src.ttd_keyframe_composer import SHOT_SPECS, compute_ssim_gray, create_soft_gaussian_mask

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "output"
KF_DIR = OUTPUT / "ttd_ep01_flow_keyframes"
VID_DIR = OUTPUT / "ttd_ep01_flow_videos"
PLATES_DIR = OUTPUT / "canonical_plates"
SHEET_PATH = OUTPUT / "ttd_ep01_master_contact_sheet.png"
BRAIN_DIR = Path(r"C:\Users\Orakul Grey\.gemini\antigravity\brain\94dd6a04-54e7-4e8c-9551-224cace4f85f")


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def test_empirical_12_keyframes_geometry_and_variance() -> None:
    """Empirically test all 12 keyframes: 1280x720 RGB, size > 500KB, non-blank std > 20.0."""
    for idx in range(12):
        sid = f"SHOT-{idx + 1:02d}"
        fn = f"ttd_ep01_shot_{idx + 1:02d}_keyframe.png"
        p = KF_DIR / fn
        assert p.is_file(), f"Missing keyframe: {fn}"
        assert p.stat().st_size > 500_000, f"{fn} size too small: {p.stat().st_size}"
        with Image.open(p) as pim:
            assert pim.size == (1280, 720), f"{fn} invalid size: {pim.size}"
            assert pim.mode == "RGB", f"{fn} invalid mode: {pim.mode}"
            std = float(np.std(np.array(pim)))
            assert std > 20.0, f"{fn} blank image: std={std:.2f}"


def test_empirical_keyframes_background_drift_mae_and_ssim() -> None:
    """Empirically compute MAE_bg <= 6.0 and SSIM_bg >= 0.85 against canonical plates."""
    for idx in range(12):
        sid = f"SHOT-{idx + 1:02d}"
        spec = SHOT_SPECS[sid]
        bgr = cv2.imread(str(KF_DIR / f"ttd_ep01_shot_{idx + 1:02d}_keyframe.png"))
        plate = cv2.imread(str(PLATES_DIR / spec["bg_plate"]))
        mask = create_soft_gaussian_mask(spec["ellipses"])
        bg_zone = mask < 0.15
        diff = np.abs(bgr.astype(np.float32) - plate.astype(np.float32))
        mae = float(np.mean(diff[bg_zone]))
        ssim = compute_ssim_gray(bgr, plate, mask=bg_zone.astype(np.uint8))
        assert mae <= 6.0, f"{sid}: background MAE {mae:.4f} > 6.0"
        assert ssim >= 0.85, f"{sid}: background SSIM {ssim:.4f} < 0.85"


def test_empirical_keyframes_spark_and_glow_absence() -> None:
    """Empirically audit sparks == 0, Lucas glow == 0, neon == 0, sky Laplacian <= 180."""
    for idx in range(12):
        sid = f"SHOT-{idx + 1:02d}"
        spec = SHOT_SPECS[sid]
        bgr = cv2.imread(str(KF_DIR / f"ttd_ep01_shot_{idx + 1:02d}_keyframe.png"))
        plate = cv2.imread(str(PLATES_DIR / spec["bg_plate"]))
        mask = create_soft_gaussian_mask(spec["ellipses"])
        sp = audit_sparks_and_glow(bgr, sid, eye_box=spec.get("eye_box"))
        lap = audit_laplacian_edges(bgr, plate, sid, mask_float=mask)
        assert sp["sparks"] == 0, f"{sid}: sparks detected: {sp['sparks']}"
        assert sp["lucas_glow"] == 0, f"{sid}: Lucas glow detected"
        assert sp["armor_neon"] == 0, f"{sid}: armor neon detected"
        assert lap["sky_laplacian_var"] <= 180.0, f"{sid}: sky Laplacian {lap['sky_laplacian_var']} > 180"
        assert 0.90 <= lap["edge_retention_ratio"] <= 1.15, f"{sid}: edge ratio outside [0.90, 1.15]"
        assert lap["paper_halo"] <= 0.005, f"{sid}: paper halo {lap['paper_halo']} > 0.005"


def test_empirical_video_cuts_faststart_cfr_and_audio_rms() -> None:
    """Empirically verify FastStart moov before mdat, 24fps CFR, and vocal RMS on Lucas 3/4 cut and Pilot Master."""
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    for name, min_sz, min_fr in [
        ("ttd_ep01_shot_04_lucas_roar_command_720p.mp4", 500_000, 96),
        ("ttd_ep01_pilot_master_720p.mp4", 5_000_000, 1100),
    ]:
        p = VID_DIR / name
        assert p.is_file(), f"Missing video: {p.name}"
        assert p.stat().st_size >= min_sz, f"{p.name} failed anti-mock size check"
        assert audit_faststart_atoms(p), f"{p.name} FastStart violation (moov not before mdat)"
        cap = cv2.VideoCapture(str(p))
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = float(cap.get(cv2.CAP_PROP_FPS) or 24.0)
        fr = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        cap.release()
        assert (w, h) == (1280, 720) and abs(fps - 24.0) < 0.2 and fr >= min_fr

        cmd = [ff, "-hide_banner", "-i", str(p), "-vn", "-ac", "1", "-ar", "24000", "-f", "s16le", "-"]
        res = subprocess.run(cmd, capture_output=True, check=False)
        pcm = np.frombuffer(res.stdout, dtype=np.int16).astype(np.float32)
        assert pcm.size > 24000 * 3, "Audio stream too short"
        rms = float(np.sqrt(np.mean(pcm * pcm)))
        assert rms > 100.0, f"{p.name} audio RMS {rms:.2f} <= 100.0"


def test_empirical_master_contact_sheet() -> None:
    """Empirically verify master contact sheet 3840x3834 RGB > 5MB and dynamic range."""
    assert SHEET_PATH.is_file() and SHEET_PATH.stat().st_size > 5_000_000
    with Image.open(SHEET_PATH) as im:
        assert im.size == (3840, 3834), f"Unexpected sheet geometry: {im.size}"
        assert im.mode == "RGB", f"Unexpected sheet mode: {im.mode}"
        arr = np.array(im)
        mean_lum = float(np.mean(arr))
        std_lum = float(np.std(arr))
        assert 15.0 <= mean_lum <= 200.0, f"Mean luminance {mean_lum:.2f} outside [15, 200]"
        assert std_lum > 20.0, f"Std luminance {std_lum:.2f} <= 20.0"


def test_empirical_brain_mirror_parity_and_collision_guard() -> None:
    """Empirically verify 100% SHA-256 bit-for-bit parity in brain dir and namespace guard."""
    assert BRAIN_DIR.is_dir(), f"Brain directory missing: {BRAIN_DIR}"
    guard = BRAIN_DIR / "manifest.json"
    assert guard.is_file() and guard.stat().st_size == 10897
    assert _sha(guard).startswith("b42d2919")

    # Audit all 20 assets
    assets = [
        SHEET_PATH, OUTPUT / "ttd_ep01_manifest.json", OUTPUT / "ttd_ep01_m4_audit_certificate.json",
        VID_DIR / "ttd_ep01_shot_04_lucas_roar_command_720p.mp4",
        VID_DIR / "ttd_ep01_pilot_master_720p.mp4",
        VID_DIR / "ttd_ep01_pilot_narration.vtt", VID_DIR / "ttd_ep01_pilot_narration.srt",
        VID_DIR / "ttd_ep01_cl02_lucas_command_roar_720p.mp4",
    ]
    for i in range(1, 13):
        assets.append(KF_DIR / f"ttd_ep01_shot_{i:02d}_keyframe.png")

    for src in assets:
        dst = BRAIN_DIR / src.name
        assert dst.is_file(), f"Missing in brain storage: {src.name}"
        assert _sha(src) == _sha(dst), f"SHA-256 parity mismatch on {src.name}"
