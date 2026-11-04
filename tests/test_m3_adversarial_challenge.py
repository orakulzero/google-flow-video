"""
tests/test_m3_adversarial_challenge.py
Empirical adversarial challenger test suite authored by m3_assembly_challenger_1.
Rigorous stress testing for Milestone 3 silent video master deliverable:
1. Full Bitstream Decoding Stress (ffmpeg -v error -i <file> -f null - -> exit 0, empty stderr).
2. Dynamic Motion & Non-Freeze Verification (12 sample frames across 69.8s timeline: std > 15.0, sequential MSE > 50.0).
3. Zero-Audio Container Audit (FFmpeg/ffprobe descriptor inspection -> strictly 0 audio streams).
4. Streaming Faststart Layout (Binary ISO-BMFF top-level boxes: moov byte offset < mdat byte offset).
5. Byte-for-byte SHA-256 mirror parity between output/ and brain/ directories.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import struct
import subprocess
from typing import List, Tuple

import cv2
import imageio_ffmpeg
import numpy as np
import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent
PRIMARY_MP4 = ROOT_DIR / "output" / "ttd_ep01_manga_transitions" / "ttd_episode_01_silent_720p.mp4"
BRAIN_MP4 = Path(r"C:\Users\Orakul Grey\.gemini\antigravity\brain\94dd6a04-54e7-4e8c-9551-224cace4f85f\ttd_episode_01_silent_720p.mp4")

TARGETS = [PRIMARY_MP4, BRAIN_MP4]


def compute_sha256(path: Path) -> str:
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def parse_top_level_atoms(path: Path) -> List[Tuple[str, int, int]]:
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


@pytest.mark.parametrize("target_path", TARGETS)
def test_full_bitstream_decoding_stress(target_path: Path) -> None:
    """Stress test bitstream decoding: decode 100% packets without error or stream drops."""
    assert target_path.is_file(), f"Target video does not exist: {target_path}"
    assert target_path.stat().st_size > 15_000_000, f"File size unexpectedly small: {target_path.stat().st_size}"

    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    cmd = [
        ffmpeg_exe,
        "-v",
        "error",
        "-i",
        str(target_path),
        "-f",
        "null",
        "-",
    ]
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        errors="replace",
        check=False,
    )
    assert proc.returncode == 0, f"FFmpeg decoding failed with code {proc.returncode}. Stderr: {proc.stderr}"
    assert proc.stderr.strip() == "", f"FFmpeg emitted decoding errors/warnings: {proc.stderr}"


@pytest.mark.parametrize("target_path", TARGETS)
def test_dynamic_motion_and_non_freeze(target_path: Path) -> None:
    """Sample 12 equidistant frames across timeline to prove frame std > 15.0 and sequential MSE > 50.0."""
    cap = cv2.VideoCapture(str(target_path))
    assert cap.isOpened(), f"Cannot open video with cv2: {target_path}"

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 24.0
    duration = total_frames / fps
    assert total_frames >= 1600, f"Frame count {total_frames} below expected threshold"
    assert 69.0 <= duration <= 71.0, f"Duration {duration:.2f}s not in expected range"

    sample_indices = np.linspace(0, total_frames - 1, num=12, dtype=int)
    frames_bgr = []
    stds = []

    for idx in sample_indices:
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(idx))
        ret, frame = cap.read()
        assert ret, f"Failed to read frame at index {idx}"
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        std_val = float(np.std(gray))
        stds.append(std_val)
        assert std_val > 15.0, f"Frame {idx} std variance {std_val:.2f} <= 15.0 (potential blank/blackout)"
        frames_bgr.append(frame.astype(np.float32))

    cap.release()

    # Verify sequential MSE between consecutive equidistant sample frames
    mses = []
    for i in range(len(frames_bgr) - 1):
        f1 = frames_bgr[i]
        f2 = frames_bgr[i + 1]
        mse = float(np.mean((f1 - f2) ** 2))
        mses.append(mse)
        assert mse > 50.0, (
            f"Sequential sample MSE between index {sample_indices[i]} and {sample_indices[i+1]} "
            f"is {mse:.2f} <= 50.0 (static freeze detected)"
        )

    # Global motion statistics assertion
    assert np.mean(mses) > 100.0, f"Average sequential MSE {np.mean(mses):.2f} <= 100.0"
    assert np.mean(stds) > 30.0, f"Average frame variance {np.mean(stds):.2f} <= 30.0"


@pytest.mark.parametrize("target_path", TARGETS)
def test_zero_audio_container_audit(target_path: Path) -> None:
    """Audit all container streams: assert strictly 0 audio streams exist in container."""
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    probe_cmd = [
        ffmpeg_exe,
        "-hide_banner",
        "-i",
        str(target_path),
    ]
    proc = subprocess.run(
        probe_cmd,
        capture_output=True,
        text=True,
        errors="replace",
        check=False,
    )
    stderr = proc.stderr or ""
    assert "Audio:" not in stderr, f"Audio stream detected in banner: {stderr}"

    # Also inspect using ffprobe JSON stream parser if ffprobe exists, or verify stream list
    stream_lines = [line.strip() for line in stderr.splitlines() if "Stream #" in line]
    assert len(stream_lines) == 1, f"Expected exactly 1 stream in container, found {len(stream_lines)}: {stream_lines}"
    assert "Video:" in stream_lines[0], f"Stream 0 is not Video: {stream_lines[0]}"
    assert "Audio:" not in stream_lines[0], f"Stream 0 contains audio: {stream_lines[0]}"


@pytest.mark.parametrize("target_path", TARGETS)
def test_streaming_faststart_iso_bmff_layout(target_path: Path) -> None:
    """Assert ISO-BMFF top-level box structure: moov byte offset strictly precedes mdat."""
    atoms = parse_top_level_atoms(target_path)
    box_names = [a[0] for a in atoms]
    assert "ftyp" in box_names, f"ftyp box missing: {box_names}"
    assert "moov" in box_names, f"moov box missing: {box_names}"
    assert "mdat" in box_names, f"mdat box missing: {box_names}"

    moov_info = next(a for a in atoms if a[0] == "moov")
    mdat_info = next(a for a in atoms if a[0] == "mdat")

    moov_offset = moov_info[1]
    mdat_offset = mdat_info[1]

    assert moov_offset < mdat_offset, (
        f"Faststart violation in {target_path.name}: moov offset {moov_offset} >= mdat offset {mdat_offset}"
    )


def test_byte_for_byte_sha256_mirror_parity() -> None:
    """Verify bitwise SHA-256 equivalence between primary output and brain mirror deliverable."""
    assert PRIMARY_MP4.is_file(), f"Primary MP4 missing: {PRIMARY_MP4}"
    assert BRAIN_MP4.is_file(), f"Brain MP4 missing: {BRAIN_MP4}"

    primary_sha = compute_sha256(PRIMARY_MP4)
    brain_sha = compute_sha256(BRAIN_MP4)

    assert primary_sha == brain_sha, (
        f"SHA-256 mismatch between primary and brain deliverable!\n"
        f"Primary: {primary_sha}\nBrain:   {brain_sha}"
    )


def test_zero_cyrillic_hygiene() -> None:
    """ISO 9001 English-only compliance: strictly 0 Cyrillic characters in test suite."""
    code_text = Path(__file__).read_text(encoding="utf-8")
    matches = re.findall(r"[\u0400-\u04FF]", code_text)
    assert len(matches) == 0, f"Found {len(matches)} Cyrillic characters in test file."
