"""
tests/test_ttd_m3_delivery_verification.py
Comprehensive delivery verification test suite for Episode 1 Manga Flow Transitions (Milestone 3).
Validates master video geometry (1280x720 24fps CFR), strictly zero audio streams,
faststart atom layout (moov before mdat), contact sheet dimensions (1360x1825) & non-blank variance,
provenance manifest integrity, brain directory SHA-256 mirroring, CLI arguments (--help, --verify-only),
and 100% English-only hygiene.
Strictly zero Cyrillic characters.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import struct
import subprocess
import sys
from typing import Any

import cv2
import imageio_ffmpeg
import numpy as np
from PIL import Image
import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT_DIR / "output" / "ttd_ep01_manga_transitions"
SEGMENTS_DIR = OUTPUT_DIR / "segments"
MASTER_VIDEO_PATH = OUTPUT_DIR / "ttd_episode_01_silent_720p.mp4"
CONTACT_SHEET_PATH = OUTPUT_DIR / "ep01_manga_transitions_contact_sheet.png"
MANIFEST_PATH = OUTPUT_DIR / "manifest.json"
BRAIN_DIR = Path(r"C:\Users\Orakul Grey\.gemini\antigravity\brain\94dd6a04-54e7-4e8c-9551-224cace4f85f")
SCRIPT_PATH = ROOT_DIR / "scripts" / "assemble_ep01_silent_video.py"


def get_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def parse_mp4_atoms(path: Path) -> list[tuple[str, int, int]]:
    atoms: list[tuple[str, int, int]] = []
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


def test_m3_artifacts_existence_and_non_zero_size() -> None:
    """Verify all 3 primary output artifacts exist and meet minimum size thresholds."""
    assert MASTER_VIDEO_PATH.is_file(), f"Master video missing: {MASTER_VIDEO_PATH}"
    assert MASTER_VIDEO_PATH.stat().st_size > 15_000_000, f"Master video size too small: {MASTER_VIDEO_PATH.stat().st_size}"

    assert CONTACT_SHEET_PATH.is_file(), f"Contact sheet missing: {CONTACT_SHEET_PATH}"
    assert CONTACT_SHEET_PATH.stat().st_size > 1_000_000, f"Contact sheet too small: {CONTACT_SHEET_PATH.stat().st_size}"

    assert MANIFEST_PATH.is_file(), f"Manifest missing: {MANIFEST_PATH}"
    assert MANIFEST_PATH.stat().st_size > 500, f"Manifest size too small: {MANIFEST_PATH.stat().st_size}"


def test_m3_master_video_geometry_and_cfr() -> None:
    """Assert master video geometry is 1280x720, 24fps CFR, with duration ~69.8s."""
    cap = cv2.VideoCapture(str(MASTER_VIDEO_PATH))
    assert cap.isOpened(), f"Could not open master video with OpenCV: {MASTER_VIDEO_PATH}"

    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 24.0)
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = frame_count / fps if fps > 0 else 0.0
    cap.release()

    assert (w, h) == (1280, 720), f"Expected 1280x720, got {w}x{h}"
    assert abs(fps - 24.0) < 0.1, f"Expected 24.0 fps CFR, got {fps}"
    assert frame_count >= 1670, f"Frame count too low: {frame_count}"
    assert 69.0 <= duration <= 71.0, f"Duration {duration:.2f}s outside expected [69.0s, 71.0s]"


def test_m3_master_video_codec_and_strictly_zero_audio() -> None:
    """Probe master video with FFmpeg to assert H.264 yuv420p and strictly zero audio streams."""
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    res = subprocess.run(
        [ffmpeg_exe, "-hide_banner", "-i", str(MASTER_VIDEO_PATH)],
        capture_output=True,
        text=True,
        errors="replace",
        check=False,
    )
    stderr = res.stderr or ""
    assert "Audio:" not in stderr, "Audio stream detected! Assembled video must be strictly silent (-an)."
    assert "h264" in stderr.lower() or "avc1" in stderr.lower(), "Video codec must be H.264/AVC."
    assert "yuv420p" in stderr.lower(), "Pixel format must be yuv420p."


def test_m3_faststart_atom_order_moov_before_mdat() -> None:
    """Parse top-level MP4 atoms to verify faststart layout where moov precedes mdat."""
    atoms = parse_mp4_atoms(MASTER_VIDEO_PATH)
    atom_names = [a[0] for a in atoms]
    assert "moov" in atom_names, f"moov atom missing in MP4: {atom_names}"
    assert "mdat" in atom_names, f"mdat atom missing in MP4: {atom_names}"

    moov_idx = atom_names.index("moov")
    mdat_idx = atom_names.index("mdat")
    assert moov_idx < mdat_idx, f"Faststart violation: moov (idx {moov_idx}) does not precede mdat (idx {mdat_idx})"


def test_m3_contact_sheet_dimensions_palette_and_non_blank() -> None:
    """Verify contact sheet image geometry (1360x1825), non-blank variance, and Card 8 gold accent."""
    with Image.open(CONTACT_SHEET_PATH) as img:
        assert img.size == (1360, 1825), f"Contact sheet size {img.size} != (1360, 1825)"
        assert img.mode == "RGB", f"Contact sheet mode {img.mode} != RGB"
        arr = np.array(img)

    # Assert non-blank canvas
    std_val = float(np.std(arr))
    assert std_val > 25.0, f"Contact sheet image std {std_val:.2f} <= 25.0 (blank or corrupted)"

    # Assert Card 8 (bottom right cell) contains the climax frame with gold border
    # Card 8 coordinates: col=1 (x ~ 680..1340), row=3 (y ~ 1380..1805)
    card8_crop = arr[1380:1805, 680:1340]
    card8_std = float(np.std(card8_crop))
    assert card8_std > 30.0, f"Card 8 crop variance {card8_std:.2f} <= 30.0"


def test_m3_provenance_manifest_structure_and_segment_hashes() -> None:
    """Verify manifest.json metadata, durations, faststart status, and segment hashes."""
    data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    assert data["master_video"] == "ttd_episode_01_silent_720p.mp4"
    assert data["resolution"] == "1280x720"
    assert data["fps"] == 24.0
    assert data["silent"] is True
    assert data["faststart"] is True
    assert data["audio_streams"] == 0
    assert 69.0 <= data["duration_seconds"] <= 71.0

    # Verify SHA-256 recorded in manifest matches live master video
    actual_master_sha = get_sha256(MASTER_VIDEO_PATH)
    assert data["master_sha256"] == actual_master_sha, "Manifest master SHA-256 mismatch"

    # Verify all 7 segments are indexed and hashes match
    assert len(data["segments"]) == 7, f"Expected 7 segments in manifest, found {len(data['segments'])}"
    for seg_entry in data["segments"]:
        seg_p = SEGMENTS_DIR / seg_entry["filename"]
        assert seg_p.is_file(), f"Segment file missing: {seg_p}"
        actual_seg_sha = get_sha256(seg_p)
        assert seg_entry["sha256"] == actual_seg_sha, f"Segment {seg_p.name} SHA-256 mismatch"


def test_m3_brain_mirroring_and_sha256_exact_match() -> None:
    """Verify all 3 artifacts are mirrored to brain directory with identical SHA-256 hashes."""
    assert BRAIN_DIR.is_dir(), f"Brain directory not found: {BRAIN_DIR}"

    artifacts = [
        ("ttd_episode_01_silent_720p.mp4", MASTER_VIDEO_PATH),
        ("ep01_manga_transitions_contact_sheet.png", CONTACT_SHEET_PATH),
        ("manifest.json", MANIFEST_PATH),
    ]

    for name, src_path in artifacts:
        dst_path = BRAIN_DIR / name
        assert dst_path.is_file(), f"Mirrored artifact missing in brain dir: {dst_path}"
        assert dst_path.stat().st_size == src_path.stat().st_size, f"Size mismatch for {name}"
        src_sha = get_sha256(src_path)
        dst_sha = get_sha256(dst_path)
        assert src_sha == dst_sha, f"SHA-256 hash mismatch for mirrored artifact {name}"


def test_m3_cli_help() -> None:
    """Assert that CLI --help executes with exit code 0 and documents --verify-only."""
    res = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--help"],
        capture_output=True,
        text=True,
        errors="replace",
        check=False,
    )
    assert res.returncode == 0, f"Expected returncode 0 from --help, got {res.returncode}. Stderr: {res.stderr}"
    stdout = res.stdout or ""
    assert "--verify-only" in stdout, "Expected '--verify-only' option documented in CLI --help output."


def test_m3_cli_verify_only() -> None:
    """Assert that CLI --verify-only executes with exit code 0 and outputs verification metrics."""
    res = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--verify-only"],
        capture_output=True,
        text=True,
        errors="replace",
        check=False,
    )
    assert res.returncode == 0, f"Expected returncode 0 from --verify-only, got {res.returncode}. Stderr: {res.stderr}"
    stdout = res.stdout or ""
    assert "Verification:" in stdout, f"Expected 'Verification:' in stdout. Got:\n{stdout}"
    assert "1280x720" in stdout, f"Expected '1280x720' in stdout. Got:\n{stdout}"
    assert "Silent: True" in stdout, f"Expected 'Silent: True' in stdout. Got:\n{stdout}"
    assert "Faststart: True" in stdout, f"Expected 'Faststart: True' in stdout. Got:\n{stdout}"
    assert "Executing filter_complex" not in stdout, "verify-only must not re-execute video concatenation."
    assert "Traceback" not in (res.stderr or ""), f"Unexpected traceback in stderr:\n{res.stderr}"


def test_m3_zero_cyrillic_hygiene() -> None:
    """Enforce strict ISO 9001 zero Cyrillic hygiene across assembly script and test suite."""
    paths_to_audit = [
        ROOT_DIR / "scripts" / "assemble_ep01_silent_video.py",
        Path(__file__),
    ]
    for p in paths_to_audit:
        text = p.read_text(encoding="utf-8")
        cyrillic_matches = re.findall(r"[\u0400-\u04FF]", text)
        assert len(cyrillic_matches) == 0, f"Found {len(cyrillic_matches)} Cyrillic chars in {p.name}"
