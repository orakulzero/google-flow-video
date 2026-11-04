"""
tests/test_m2_remediation_empirical_challenger.py
Empirical stress-test suite authored by m2_remediation_challenger_1.
Verifies stream invariants, motion entropy, visual continuity, and container robustness
across the 7 Google Flow video segments (segment_01.mp4 .. segment_07.mp4).
"""
from __future__ import annotations

import math
import os
from pathlib import Path
import re
import subprocess
from typing import Any

import cv2
import imageio_ffmpeg
import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SEGMENTS_DIR = REPO_ROOT / "output" / "ttd_ep01_manga_transitions" / "segments"
CLEAN_DIR = REPO_ROOT / "output" / "ttd_ep01_manga_transitions" / "clean_frames"

EXPECTED_SEGMENT_COUNT = 7
FFMPEG_EXE = imageio_ffmpeg.get_ffmpeg_exe()


def get_stream_metadata(mp4_path: Path) -> dict[str, Any]:
    """Extract stream parameters using FFmpeg inspect."""
    res = subprocess.run(
        [FFMPEG_EXE, "-i", str(mp4_path)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    stderr = res.stderr or ""

    dur_match = re.search(r"Duration:\s*(\d{2}):(\d{2}):(\d{2}\.\d+)", stderr)
    duration_s = 0.0
    if dur_match:
        h, m, s = int(dur_match.group(1)), int(dur_match.group(2)), float(dur_match.group(3))
        duration_s = h * 3600 + m * 60 + s

    audio_matches = re.findall(r"Stream #\d+:\d+.*?: Audio:", stderr)
    video_matches = re.findall(r"Stream #\d+:\d+.*?: Video: ([^,\n]+)", stderr)

    cap = cv2.VideoCapture(str(mp4_path))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.release()

    is_h264 = "h264" in stderr.lower() or "avc1" in stderr.lower()
    is_yuv420p = "yuv420p" in stderr.lower()

    return {
        "file_size": mp4_path.stat().st_size,
        "duration": duration_s,
        "width": width,
        "height": height,
        "fps": fps,
        "frame_count": frame_count,
        "is_h264": is_h264,
        "is_yuv420p": is_yuv420p,
        "audio_stream_count": len(audio_matches),
        "video_stream_count": len(video_matches),
    }


def compute_frame_entropy(frame: np.ndarray) -> float:
    """Calculate Shannon entropy of grayscale frame."""
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if len(frame.shape) == 3 else frame
    hist = cv2.calcHist([gray], [0], None, [256], [0, 256]).flatten()
    prob = hist / (hist.sum() + 1e-12)
    prob = prob[prob > 0]
    return float(-np.sum(prob * np.log2(prob)))


def test_challenge_1_stream_invariant_oracle() -> None:
    """Oracle verifying 1280x720, h264, yuv420p, 24fps, silent, >1MB, 9.5-10.5s."""
    assert SEGMENTS_DIR.is_dir(), f"Segments directory missing: {SEGMENTS_DIR}"
    segments = sorted(SEGMENTS_DIR.glob("segment_*.mp4"))
    assert len(segments) == EXPECTED_SEGMENT_COUNT, f"Expected 7 segments, found {len(segments)}"

    for seg in segments:
        meta = get_stream_metadata(seg)
        # 1. Dimensions
        assert meta["width"] == 1280, f"{seg.name}: width {meta['width']} != 1280"
        assert meta["height"] == 720, f"{seg.name}: height {meta['height']} != 720"
        # 2. Codec and pixel format
        assert meta["is_h264"] is True, f"{seg.name}: codec not h264"
        assert meta["is_yuv420p"] is True, f"{seg.name}: pix_fmt not yuv420p"
        # 3. Frame rate
        assert abs(meta["fps"] - 24.0) < 0.05, f"{seg.name}: fps {meta['fps']} != 24.0"
        # 4. Audio stream count == 0
        assert meta["audio_stream_count"] == 0, f"{seg.name}: has {meta['audio_stream_count']} audio streams"
        # 5. Duration
        assert 9.5 <= meta["duration"] <= 10.5, f"{seg.name}: duration {meta['duration']}s out of bounds"
        # 6. File size
        assert meta["file_size"] > 1_000_000, f"{seg.name}: size {meta['file_size']} <= 1MB"


def test_challenge_2_motion_and_entropy_empirical_verification() -> None:
    """Verify non-freeze dynamic interpolation via equidistant sample MSE and entropy."""
    segments = sorted(SEGMENTS_DIR.glob("segment_*.mp4"))
    times = [0.5, 2.5, 5.0, 7.5, 9.5]

    for seg in segments:
        cap = cv2.VideoCapture(str(seg))
        fps = cap.get(cv2.CAP_PROP_FPS) or 24.0
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        frames: list[np.ndarray] = []

        for t in times:
            idx = min(int(t * fps), total_frames - 1)
            cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
            ret, frame = cap.read()
            assert ret is True, f"Failed reading frame at t={t}s from {seg.name}"
            frames.append(frame)
        cap.release()

        # Frame 0 vs Frame 4 (0.5s -> 9.5s) substantial generative displacement
        f0_f = frames[0].astype(np.float64)
        f4_f = frames[4].astype(np.float64)
        total_mse = float(np.mean((f0_f - f4_f) ** 2))
        assert total_mse > 100.0, f"{seg.name}: total MSE {total_mse:.2f} <= 100.0 (static freeze frame)"

        # Continuous motion across intermediate intervals
        for step_idx in range(len(frames) - 1):
            s_f1 = frames[step_idx].astype(np.float64)
            s_f2 = frames[step_idx + 1].astype(np.float64)
            step_mse = float(np.mean((s_f1 - s_f2) ** 2))
            assert step_mse > 50.0, f"{seg.name} step {step_idx}->{step_idx+1} MSE {step_mse:.2f} too low"

        # Entropy check: ensure frame is not a blank canvas (entropy > 1.5 bits)
        for t_idx, fr in enumerate(frames):
            ent = compute_frame_entropy(fr)
            assert ent > 1.5, f"{seg.name} frame {times[t_idx]}s entropy {ent:.2f} <= 1.5 (blank screen)"


def test_challenge_3_visual_continuity_and_thematic_arc() -> None:
    """Verify transition boundary alignment and final Lucas back-view target panel."""
    # Check segment 7 final frame corresponds to Lucas solitary back in darkness
    cap7 = cv2.VideoCapture(str(SEGMENTS_DIR / "segment_07.mp4"))
    total7 = int(cap7.get(cv2.CAP_PROP_FRAME_COUNT))
    cap7.set(cv2.CAP_PROP_POS_FRAMES, total7 - 1)
    ret7, end7 = cap7.read()
    cap7.release()
    assert ret7 is True, "Failed reading final frame of segment_07"

    # Lucas plate armor and cape check: non-zero center, dark borders
    h, w = end7.shape[:2]
    center_roi = end7[int(h * 0.2) : int(h * 0.8), int(w * 0.3) : int(w * 0.7)]
    border_left = end7[:, : int(w * 0.15)]
    border_right = end7[:, int(w * 0.85) :]

    assert np.mean(center_roi) > 20.0, "Segment 7 center ROI is empty"
    assert np.mean(border_left) < 15.0, "Segment 7 left border should be dark void"
    assert np.mean(border_right) < 15.0, "Segment 7 right border should be dark void"

    # Check narrative continuity between S03 end and S04 start (Save the Empire title card)
    cap3 = cv2.VideoCapture(str(SEGMENTS_DIR / "segment_03.mp4"))
    cap3.set(cv2.CAP_PROP_POS_FRAMES, int(cap3.get(cv2.CAP_PROP_FRAME_COUNT)) - 1)
    _, s3_end = cap3.read()
    cap3.release()

    cap4 = cv2.VideoCapture(str(SEGMENTS_DIR / "segment_04.mp4"))
    cap4.set(cv2.CAP_PROP_POS_FRAMES, 0)
    _, s4_start = cap4.read()
    cap4.release()

    diff_3_4 = float(np.mean(cv2.absdiff(s3_end, s4_start)))
    assert diff_3_4 < 50.0, f"S03 end to S04 start diff {diff_3_4:.2f} indicates narrative discontinuity"


def test_challenge_4_container_robustness() -> None:
    """Decode every packet in each MP4 container with FFmpeg to assert zero corruption."""
    segments = sorted(SEGMENTS_DIR.glob("segment_*.mp4"))
    for seg in segments:
        cmd = [FFMPEG_EXE, "-v", "error", "-i", str(seg), "-f", "null", "-"]
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
        assert proc.returncode == 0, f"{seg.name} ffmpeg decode failed with code {proc.returncode}"
        assert proc.stderr.strip() == "", f"{seg.name} ffmpeg decode errors: {proc.stderr}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
