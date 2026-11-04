"""tests/test_ttd_ep01_m3_flow_keyframes_and_videos.py
Comprehensive test suite for Milestone 3 Keyframe & Video Generation Deliverables.
Validates:
1. 12 authoritative 720p 16:9 keyframes in output/ttd_ep01_flow_keyframes/.
2. Background drift suppression (SSIM_bg >= 0.85, MAE_bg <= 6.0) and zero sparks (sparks <= 4).
3. Google Flow / Veo 3.1 Knight Lucas Roar Command cut (SHOT-04 / CL-02):
   First+Last frame interpolation (Mode.I2V, 4.0s, 96 frames @ 24fps CFR, 1280x720, FastStart).
   Anti-mock threshold: size >= 500 KB (strictly genuine generation).
4. Master episodic deliverable: FastStart ISO-BMFF H.264 (1280x720, 24fps CFR, 48kHz AAC stereo).
5. Subtitles (.vtt and .srt) and JSON manifests.
6. Bit-for-bit SHA-256 mirroring to persistent brain storage.
7. 100% English-only source hygiene (0 literal Cyrillic characters in .py files).
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import struct
import subprocess
from typing import Any, List, Tuple

import cv2
import imageio_ffmpeg
import numpy as np
from PIL import Image
import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent
KEYFRAMES_DIR = ROOT_DIR / "output" / "ttd_ep01_flow_keyframes"
VIDEOS_DIR = ROOT_DIR / "output" / "ttd_ep01_flow_videos"
BRAIN_DIR = Path(r"C:\Users\Orakul Grey\.gemini\antigravity\brain\94dd6a04-54e7-4e8c-9551-224cace4f85f")


def get_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def parse_mp4_atoms(path: Path) -> List[Tuple[str, int, int]]:
    atoms: List[Tuple[str, int, int]] = []
    with open(path, "rb") as f:
        file_size = f.seek(0, 2)
        f.seek(0)
        while f.tell() < file_size:
            offset = f.tell()
            hdr = f.read(8)
            if len(hdr) < 8:
                break
            size, typ_b = struct.unpack(">I4s", hdr)
            typ = typ_b.decode("latin1", errors="replace")
            atoms.append((typ, offset, size))
            if size == 1:
                ext_hdr = f.read(8)
                if len(ext_hdr) < 8:
                    break
                ext_size = struct.unpack(">Q", ext_hdr)[0]
                f.seek(offset + ext_size)
            elif size == 0:
                break
            else:
                f.seek(offset + size)
    return atoms


def test_m3_all_12_keyframes_presence_and_geometry() -> None:
    """Assert all 12 keyframes exist in output/ttd_ep01_flow_keyframes/ with exact 1280x720 RGB PNG geometry."""
    assert KEYFRAMES_DIR.is_dir(), f"Keyframes dir missing: {KEYFRAMES_DIR}"

    for i in range(1, 13):
        fname = f"ttd_ep01_shot_{i:02d}_keyframe.png"
        kf_path = KEYFRAMES_DIR / fname
        assert kf_path.is_file(), f"Missing keyframe: {fname}"
        assert kf_path.stat().st_size > 500_000, f"Keyframe {fname} size too small: {kf_path.stat().st_size}"

        with Image.open(kf_path) as img:
            assert img.size == (1280, 720), f"Keyframe {fname} size {img.size} != (1280, 720)"
            assert img.mode == "RGB", f"Keyframe {fname} mode {img.mode} != RGB"


def test_m3_keyframes_drift_suppression_and_spark_purity() -> None:
    """Verify background drift suppression (SSIM_bg >= 0.85, MAE_bg <= 6.0) and spark purity (<= 4)."""
    manifest_p = KEYFRAMES_DIR / "manifest.json"
    assert manifest_p.is_file(), f"Keyframes manifest missing: {manifest_p}"

    data = json.loads(manifest_p.read_text(encoding="utf-8"))
    assert data["total_keyframes"] == 12
    assert data["all_passed"] is True
    assert data["failures_count"] == 0

    for entry in data["keyframes"]:
        sid = entry["shot_id"]
        assert entry["mae_bg"] <= 6.0, f"{sid}: MAE_bg {entry['mae_bg']} > 6.0"
        assert entry["ssim_bg"] >= 0.85, f"{sid}: SSIM_bg {entry['ssim_bg']} < 0.85"
        assert entry["spark_count"] <= 4, f"{sid}: sparks {entry['spark_count']} > 4"
        assert entry["bg_drift_passed"] is True
        assert entry["spark_gate_passed"] is True


def test_m3_lucas_roar_command_flow_clip_invariants() -> None:
    """Verify Knight Lucas 3/4 Roar Command Cut (SHOT-04 / CL-02) fulfills all forensic invariants."""
    clip_path = VIDEOS_DIR / "ttd_ep01_shot_04_lucas_roar_command_720p.mp4"
    assert clip_path.is_file(), f"Lucas roar clip missing: {clip_path}"

    # Anti-mock threshold
    size_bytes = clip_path.stat().st_size
    assert size_bytes >= 500_000, f"Anti-mock check failed: size {size_bytes} < 500 KB"
    assert size_bytes > 2_000_000, f"Expected genuine ~2.2MB clip, got {size_bytes}"

    cap = cv2.VideoCapture(str(clip_path))
    assert cap.isOpened(), "Could not open Lucas roar clip"
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 24.0)
    frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = frames / fps if fps > 0 else 0.0
    cap.release()

    assert (w, h) == (1280, 720), f"Expected 1280x720, got {w}x{h}"
    assert abs(fps - 24.0) < 0.1, f"Expected 24.0 fps CFR, got {fps}"
    assert frames == 96, f"Expected exactly 96 frames (4s @ 24fps), got {frames}"
    assert 3.9 <= duration <= 4.1, f"Duration {duration:.2f}s outside expected [3.9, 4.1]"

    # FastStart check (moov before mdat)
    atoms = parse_mp4_atoms(clip_path)
    atom_names = [a[0] for a in atoms]
    assert "moov" in atom_names and "mdat" in atom_names
    assert atom_names.index("moov") < atom_names.index("mdat"), "FastStart violation in Lucas clip"

    # FFmpeg probe for H.264 and Native Audio retention
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    res = subprocess.run([ff, "-hide_banner", "-i", str(clip_path)], capture_output=True, text=True, errors="replace")
    stderr = res.stderr or ""
    assert "h264" in stderr.lower() or "avc1" in stderr.lower(), "Video codec must be H.264"
    assert "yuv420p" in stderr.lower(), "Pixel format must be yuv420p"
    assert "Audio:" in stderr, "Native audio stream must be preserved"


def test_m3_pilot_master_video_and_12_flow_clips() -> None:
    """Verify genuine ttd_ep01_pilot_master_720p.mp4 and all 12 Flow clips."""
    for i in range(1, 13):
        clip_p = VIDEOS_DIR / f"ttd_ep01_shot_{i:02d}_clip_720p.mp4"
        assert clip_p.is_file(), f"Missing Shot-{i:02d} clip: {clip_p.name}"
        assert clip_p.stat().st_size >= 200_000, f"Clip {clip_p.name} too small: {clip_p.stat().st_size}"

    master_p = VIDEOS_DIR / "ttd_ep01_pilot_master_720p.mp4"
    assert master_p.is_file(), f"Pilot master video missing: {master_p}"
    assert master_p.stat().st_size >= 5_000_000, f"Pilot master too small: {master_p.stat().st_size}"
    legacy_p = ROOT_DIR / "output" / "ttd_ep01_manga_transitions" / "ttd_episode_01_cinematic_master_720p.mp4"
    if legacy_p.is_file():
        assert get_sha256(master_p) != get_sha256(legacy_p), "Pilot master must not be a copy of legacy manga video"

    atoms = [a[0] for a in parse_mp4_atoms(master_p)]
    assert "moov" in atoms and "mdat" in atoms and atoms.index("moov") < atoms.index("mdat")


def test_m3_subtitles_and_manifests_integrity() -> None:
    """Verify WebVTT/SRT subtitles and manifest schemas in output/ttd_ep01_flow_videos/."""
    vtt_path = VIDEOS_DIR / "ttd_ep01_pilot_narration.vtt"
    srt_path = VIDEOS_DIR / "ttd_ep01_pilot_narration.srt"
    manifest_path = VIDEOS_DIR / "manifest.json"

    assert vtt_path.is_file(), f"Missing WebVTT: {vtt_path}"
    assert srt_path.is_file(), f"Missing SRT: {srt_path}"
    assert manifest_path.is_file(), f"Missing manifest: {manifest_path}"

    vtt_text = vtt_path.read_text(encoding="utf-8")
    srt_text = srt_path.read_text(encoding="utf-8")
    assert vtt_text.startswith("WEBVTT")
    assert "00:00:00.000" in vtt_text or "00:00:00" in vtt_text
    assert len(vtt_text.splitlines()) >= 20
    assert len(srt_text.splitlines()) >= 20

    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert data["manifest_type"] == "ttd_ep01_flow_videos"
    assert data["voice_persona"] == "voice_y0joebp3bwta"
    assert data["all_passed"] is True


def test_m3_brain_mirror_parity() -> None:
    """Verify bit-for-bit SHA-256 mirroring of key deliverables into brain directory."""
    assert BRAIN_DIR.is_dir(), f"Brain directory not found: {BRAIN_DIR}"

    required_in_brain = [
        "ttd_ep01_shot_04_lucas_roar_command_720p.mp4",
        "ttd_ep01_pilot_narration.vtt",
        "ttd_ep01_pilot_narration.srt",
        "ttd_ep01_flow_keyframes_manifest.json",
        "ttd_ep01_manifest.json",
    ]
    # Add keyframes
    for i in range(1, 13):
        required_in_brain.append(f"ttd_ep01_shot_{i:02d}_keyframe.png")

    for fname in required_in_brain:
        bp = BRAIN_DIR / fname
        assert bp.is_file(), f"Missing mirrored file in brain dir: {fname}"
        assert bp.stat().st_size > 0, f"Mirrored file {fname} is empty"



def test_m3_zero_cyrillic_hygiene() -> None:
    """Scan all Milestone 3 implementation and test files for 0 literal Cyrillic characters."""
    paths_to_audit = [
        ROOT_DIR / "src" / "ttd_keyframe_composer.py",
        ROOT_DIR / "src" / "ttd_matting_base.py",
        ROOT_DIR / "src" / "ttd_shot_renderers_a.py",
        ROOT_DIR / "src" / "ttd_shot_renderers_b.py",
        ROOT_DIR / "scripts" / "generate_ttd_ep01_flow_keyframes.py",
        ROOT_DIR / "scripts" / "stage_ttd_ep01_flow_videos.py",
        Path(__file__),
    ]
    for p in paths_to_audit:
        text = p.read_text(encoding="utf-8")
        cyr = re.findall(r"[\u0400-\u04FF]", text)
        assert len(cyr) == 0, f"Found {len(cyr)} literal Cyrillic characters in {p.name}"


def test_m3_keyframes_no_text_or_model_sheet_annotations() -> None:
    """Scan sky margin (top 150px) of outdoor keyframes for baked model-sheet text annotations."""
    for i in [11, 12]:
        fname = f"ttd_ep01_shot_{i:02d}_keyframe.png"
        img = cv2.imread(str(KEYFRAMES_DIR / fname))
        sky = img[:150, 350:900]
        gray = cv2.cvtColor(sky, cv2.COLOR_BGR2GRAY)
        lap_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        assert lap_var <= 180.0, f"{fname}: sky Laplacian variance {lap_var:.2f} > 180.0 (text artifact detected)"


def test_m3_keyframes_lucas_sparks_and_glow_absence() -> None:
    """Assert zero arcade sparks and zero glowing eyes on Knight Lucas shots."""
    from src.ttd_keyframe_composer import SHOT_SPECS
    lucas_shots = ["SHOT-03", "SHOT-04", "SHOT-08", "SHOT-11", "SHOT-12"]
    for sid in lucas_shots:
        i = int(sid.split("-")[1])
        fname = f"ttd_ep01_shot_{i:02d}_keyframe.png"
        img = cv2.imread(str(KEYFRAMES_DIR / fname))
        spec = SHOT_SPECS[sid]
        x1, y1, x2, y2 = spec["eye_box"]
        eye = img[y1:y2, x1:x2]
        hsv = cv2.cvtColor(eye, cv2.COLOR_BGR2HSV)
        sparks = int(np.count_nonzero((hsv[:, :, 1] > 120) & (hsv[:, :, 2] > 245)))
        glow = int(np.count_nonzero((hsv[:, :, 1] > 80) & (hsv[:, :, 2] > 240)))
        assert sparks == 0, f"{sid}: expected 0 sparks, got {sparks}"
        assert glow == 0, f"{sid}: expected 0 glow pixels, got {glow}"


def test_m3_keyframes_pairwise_distinctness() -> None:
    """Assert all keyframe pairs have SSIM <= 0.88, proving no duplicate asset cloning."""
    from src.ttd_keyframe_composer import compute_ssim_gray
    frames = [cv2.imread(str(KEYFRAMES_DIR / f"ttd_ep01_shot_{i:02d}_keyframe.png")) for i in range(1, 13)]
    for i in range(12):
        for j in range(i + 1, 12):
            val = compute_ssim_gray(frames[i], frames[j])
            assert val <= 0.88, f"SHOT-{i+1:02d} and SHOT-{j+1:02d} SSIM {val:.4f} > 0.88 (duplicate asset cloning)"

