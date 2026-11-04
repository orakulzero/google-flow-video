"""src/ttd_audit_engine.py
Forensic quality audit engine for TTD Episode 1 Milestone 4.
REQ-FEAT-10: Background Drift Suppression.
REQ-FEAT-11: Spark & Laser Laplacian Exclusion Audit.
REQ-FEAT-14: Master Manifest & Brain Mirror Parity.
Enforces 100% English-only source hygiene and strict <= 180 lines chunking.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
import struct
from typing import Any, Dict, List, Optional, Tuple
import cv2
import numpy as np

LUCAS_SHOTS = {"SHOT-03", "SHOT-04", "SHOT-08", "SHOT-11", "SHOT-12"}
OUTDOOR_SHOTS = {"SHOT-03", "SHOT-08", "SHOT-11", "SHOT-12"}


def compute_sha256(path: Path) -> str:
    """Compute cryptographic SHA-256 digest in 64KB chunks."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def audit_sparks_and_glow(
    bgr: np.ndarray,
    shot_id: str,
    eye_box: Optional[Tuple[int, int, int, int]] = None,
) -> Dict[str, Any]:
    """Audit arcade magic sparks, Lucas eye glow, and neon armor crevices."""
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    h, w = bgr.shape[:2]

    eye_hsv = hsv
    if eye_box:
        x1, y1, x2, y2 = eye_box
        eye_hsv = hsv[max(0, y1):min(h, y2), max(0, x1):min(w, x2)]
    sparks = int(np.count_nonzero((eye_hsv[:, :, 1] > 120) & (eye_hsv[:, :, 2] > 245)))

    lucas_glow, armor_neon = 0, 0
    if shot_id in LUCAS_SHOTS:
        lucas_glow = int(np.count_nonzero((eye_hsv[:, :, 1] > 80) & (eye_hsv[:, :, 2] > 240)))
        lower_hsv = hsv[int(h * 0.4):, :]
        lh, ls, lv = lower_hsv[:, :, 0], lower_hsv[:, :, 1], lower_hsv[:, :, 2]
        armor_neon = int(np.count_nonzero((lh >= 75) & (lh <= 165) & (ls > 100) & (lv > 220)))

    passed = (sparks <= 4) and (lucas_glow == 0) and (armor_neon == 0)
    return {
        "sparks": sparks, "lucas_glow": lucas_glow,
        "armor_neon": armor_neon, "passed": passed,
    }


def audit_laplacian_edges(
    kf_bgr: np.ndarray,
    plate_bgr: np.ndarray,
    shot_id: str,
    mask_float: Optional[np.ndarray] = None,
) -> Dict[str, Any]:
    """Audit sky Laplacian variance, edge retention, and differential paper halo."""
    sky_var, sky_passed = 0.0, True
    if shot_id in OUTDOOR_SHOTS:
        sky_crop = kf_bgr[0:150, 350:900]
        gray_sky = cv2.cvtColor(sky_crop, cv2.COLOR_BGR2GRAY)
        sky_var = float(cv2.Laplacian(gray_sky, cv2.CV_64F).var())
        sky_passed = sky_var <= 180.0

    if mask_float is not None:
        omega_env = mask_float < 0.15
    else:
        omega_env = np.ones((kf_bgr.shape[0], kf_bgr.shape[1]), dtype=bool)

    lap_kf = np.abs(cv2.Laplacian(cv2.cvtColor(kf_bgr, cv2.COLOR_BGR2GRAY), cv2.CV_64F))
    lap_pl = np.abs(cv2.Laplacian(cv2.cvtColor(plate_bgr, cv2.COLOR_BGR2GRAY), cv2.CV_64F))
    edge_ratio = float(np.sum(lap_kf[omega_env]) / (np.sum(lap_pl[omega_env]) + 1e-6))
    retention_passed = 0.90 <= edge_ratio <= 1.15

    hsv_pl = cv2.cvtColor(plate_bgr, cv2.COLOR_BGR2HSV)
    paper_pl = (hsv_pl[:, :, 2] > 175) & (hsv_pl[:, :, 1] < 45) & omega_env
    hsv_kf = cv2.cvtColor(kf_bgr, cv2.COLOR_BGR2HSV)
    paper_kf = (hsv_kf[:, :, 2] > 175) & (hsv_kf[:, :, 1] < 45) & omega_env
    paper_halo = float(np.sum(paper_kf & (~paper_pl)) / np.sum(omega_env))
    halo_passed = paper_halo <= 0.005

    return {
        "sky_laplacian_var": round(sky_var, 2),
        "edge_retention_ratio": round(edge_ratio, 4),
        "paper_halo": round(paper_halo, 6),
        "passed": sky_passed and retention_passed and halo_passed,
    }


def audit_faststart_atoms(video_path: Path) -> bool:
    """Validate ISO-BMFF FastStart box structure (moov preceding mdat)."""
    atoms: List[str] = []
    with open(video_path, "rb") as f:
        size_total = f.seek(0, 2)
        f.seek(0)
        while f.tell() < size_total:
            off = f.tell()
            hdr = f.read(8)
            if len(hdr) < 8:
                break
            box_sz, box_t = struct.unpack(">I4s", hdr)
            tag = box_t.decode("latin1", errors="replace")
            atoms.append(tag)
            if box_sz == 1:
                ext = f.read(8)
                if len(ext) < 8:
                    break
                es = struct.unpack(">Q", ext)[0]
                f.seek(off + es)
            elif box_sz > 0:
                f.seek(off + box_sz)
            else:
                break
    return ("moov" in atoms) and ("mdat" in atoms) and (atoms.index("moov") < atoms.index("mdat"))


def audit_video_cut(video_path: Path, min_bytes: int = 500_000) -> Dict[str, Any]:
    """Validate MP4 video deliverable container, CFR, and FastStart parameters."""
    sz = video_path.stat().st_size
    anti_mock = sz >= min_bytes
    faststart = audit_faststart_atoms(video_path)

    cap = cv2.VideoCapture(str(video_path))
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 24.0)
    frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.release()

    geo_ok = (w == 1280 and h == 720)
    fps_ok = abs(fps - 24.0) < 0.2
    passed = anti_mock and faststart and geo_ok and fps_ok
    return {
        "size_bytes": sz,
        "width": w,
        "height": h,
        "fps": round(fps, 2),
        "frames": frames,
        "faststart": faststart,
        "anti_mock_passed": anti_mock,
        "passed": passed,
    }
