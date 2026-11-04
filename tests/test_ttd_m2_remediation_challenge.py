"""
tests/test_ttd_m2_remediation_challenge.py
Adversarial empirical stress-test suite authored by m2_remediation_challenger_2.
Verifies:
1. CLI Robustness & Verification Interface (--dry-run, invalid arguments, verify_segment negative oracles).
2. Narrative Arc Boundary Verification (7-segment chain ep01_frame_001_clean.png -> ep01_frame_026_clean.png).
3. Visual Beat Coverage (victory, chat, title card, map, desk, corpses, Lucas solitary back).
4. Code hygiene and strictly zero Cyrillic characters in remediation script.
"""
from __future__ import annotations

import os
from pathlib import Path
import re
import subprocess
import sys
import cv2
import pytest

from scripts.generate_ep01_manga_flow_transitions import (
    TRANSITIONS,
    DEFAULT_CLEAN_DIR,
    DEFAULT_SEGMENTS_DIR,
    resolve_ffmpeg_exe,
    verify_segment,
)


def test_cli_dry_run_execution_and_asset_discovery() -> None:
    """Empirically test --dry-run CLI flag: exits cleanly (code 0) without browser automation."""
    cmd = [sys.executable, "scripts/generate_ep01_manga_flow_transitions.py", "--dry-run"]
    res = subprocess.run(cmd, capture_output=True, text=True, check=False)
    assert res.returncode == 0, f"--dry-run failed with code {res.returncode}: {res.stderr}"
    assert "Manga Flow Transitions Pipeline" in res.stdout
    assert "[DRY RUN] Validating keyframe assets and pipeline configuration..." in res.stdout
    assert "Total segments: 7, Missing assets: 0" in res.stdout
    assert "Targets: [1, 2, 3, 4, 5, 6, 7]" in res.stdout


def test_cli_argument_validation_and_invalid_choices() -> None:
    """Stress-test CLI parameter constraints: invalid segment IDs must fail immediately."""
    cmd_invalid = [
        sys.executable,
        "scripts/generate_ep01_manga_flow_transitions.py",
        "--segment",
        "99",
        "--dry-run",
    ]
    res = subprocess.run(cmd_invalid, capture_output=True, text=True, check=False)
    assert res.returncode == 2, "Expected argparse exit code 2 for invalid segment choice"
    assert "invalid choice" in res.stderr.lower() or "error" in res.stderr.lower()


def test_empirical_verify_segment_positive_oracle() -> None:
    """Verify that all 7 generated segment files pass verify_segment with strict invariants."""
    assert DEFAULT_SEGMENTS_DIR.is_dir(), f"Segments directory {DEFAULT_SEGMENTS_DIR} does not exist"
    segment_files = sorted(DEFAULT_SEGMENTS_DIR.glob("segment_*.mp4"))
    assert len(segment_files) == 7, f"Expected 7 segments, found {len(segment_files)}"

    for seg_p in segment_files:
        v = verify_segment(seg_p)
        assert v["valid"] is True, f"Segment {seg_p.name} failed verification: {v.get('error')}"
        assert v["width"] == 1280
        assert v["height"] == 720
        assert v["fps"] == 24.0
        assert v["duration"] >= 3.0
        assert v["file_size"] > 1_000_000
        assert v["h264_codec"] is True
        assert v["silent"] is True


def test_empirical_verify_segment_negative_oracles_truncation_and_corruption(tmp_path: Path) -> None:
    """Stress-test verify_segment rejection oracle against non-existent, empty, and corrupted files."""
    # 1. Non-existent file
    missing = tmp_path / "non_existent.mp4"
    res_missing = verify_segment(missing)
    assert res_missing["valid"] is False
    assert "does not exist" in res_missing["error"]

    # 2. 0-byte file
    empty = tmp_path / "empty.mp4"
    empty.write_bytes(b"")
    res_empty = verify_segment(empty)
    assert res_empty["valid"] is False
    assert "too small" in res_empty["error"]

    # 3. Truncated file (10 KB < 50 KB threshold)
    truncated = tmp_path / "truncated.mp4"
    truncated.write_bytes(b"\x00" * 10240)
    res_trunc = verify_segment(truncated)
    assert res_trunc["valid"] is False
    assert "too small" in res_trunc["error"]

    # 4. Corrupted file (> 50 KB but random invalid garbage bytes)
    corrupt = tmp_path / "corrupt_garbage.mp4"
    corrupt.write_bytes(os.urandom(65536))
    res_corrupt = verify_segment(corrupt)
    assert res_corrupt["valid"] is False
    assert "failed to open" in res_corrupt["error"] or "error" in res_corrupt["error"]


def test_empirical_verify_segment_negative_oracles_invalid_geometry_and_audio(tmp_path: Path) -> None:
    """Stress-test verify_segment against non-compliant resolution, short duration, and audio tracks."""
    ffmpeg_exe = resolve_ffmpeg_exe()

    # 1. Synthesize 640x360 silent video (> 50KB to pass size check)
    res_bad_geom = tmp_path / "bad_geometry.mp4"
    subprocess.run(
        [
            ffmpeg_exe, "-y", "-f", "lavfi", "-i", "testsrc=size=640x360:rate=24:duration=4",
            "-c:v", "libx264", "-b:v", "1M", "-pix_fmt", "yuv420p", "-an", str(res_bad_geom)
        ],
        capture_output=True,
        check=True,
    )
    assert res_bad_geom.stat().st_size > 50000
    res_geom_out = verify_segment(res_bad_geom)
    assert res_geom_out["valid"] is False
    assert "Invalid resolution" in res_geom_out["error"]

    # 2. Synthesize 1280x720 video with duration < 1.0s (0.5s) padded to > 50KB
    res_short = tmp_path / "too_short.mp4"
    subprocess.run(
        [
            ffmpeg_exe, "-y", "-f", "lavfi", "-i", "testsrc=size=1280x720:rate=24:duration=0.5",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-an", str(res_short)
        ],
        capture_output=True,
        check=True,
    )
    # Pad file so it passes the 50KB size check and triggers duration check
    res_short.write_bytes(res_short.read_bytes() + b"\x00" * 60000)
    assert res_short.stat().st_size > 50000
    res_short_out = verify_segment(res_short)
    assert res_short_out["valid"] is False
    assert "Duration too short" in res_short_out["error"]

    # 3. Synthesize 1280x720 video WITH an audio stream (> 50KB)
    res_audio = tmp_path / "has_audio.mp4"
    subprocess.run(
        [
            ffmpeg_exe, "-y", "-f", "lavfi", "-i", "testsrc=size=1280x720:rate=24:duration=3",
            "-f", "lavfi", "-i", "sine=f=440:d=3",
            "-c:v", "libx264", "-b:v", "1M", "-pix_fmt", "yuv420p", "-c:a", "aac", str(res_audio)
        ],
        capture_output=True,
        check=True,
    )
    assert res_audio.stat().st_size > 50000
    res_audio_out = verify_segment(res_audio)
    assert res_audio_out["valid"] is False
    assert "Audio stream detected" in res_audio_out["error"]


def test_narrative_arc_graph_continuity_and_boundary_invariants() -> None:
    """Verify 7-segment keyframe graph continuity from ep01_frame_001_clean to ep01_frame_026_clean."""
    assert len(TRANSITIONS) == 7, f"Expected 7 transitions, found {len(TRANSITIONS)}"

    # Boundary 1: Starting node must be frame 001
    assert TRANSITIONS[0].start_keyframe == "ep01_frame_001_clean.png"

    # Boundary 2: Ending node must be frame 026
    assert TRANSITIONS[-1].end_keyframe == "ep01_frame_026_clean.png"

    # Continuous graph chaining: end of segment i must equal start of segment i+1
    for idx in range(len(TRANSITIONS) - 1):
        curr_spec = TRANSITIONS[idx]
        next_spec = TRANSITIONS[idx + 1]
        assert curr_spec.end_keyframe == next_spec.start_keyframe, (
            f"Broken graph chain between segment {curr_spec.segment_id} and {next_spec.segment_id}: "
            f"{curr_spec.end_keyframe} != {next_spec.start_keyframe}"
        )


def test_narrative_visual_beats_coverage() -> None:
    """Verify that all essential story beats are mapped into prompt semantics."""
    prompts_joined = " ".join([t.prompt.lower() for t in TRANSITIONS])
    titles_joined = " ".join([t.title.lower() for t in TRANSITIONS])
    all_text = f"{prompts_joined} {titles_joined}"

    # Beat 1: Gamer celebration
    assert "victory" in all_text and "triumph" in all_text
    # Beat 2: Streamer chat
    assert "chat" in all_text or "streamer" in all_text
    # Beat 3: Gothic title screen
    assert "save the empire" in all_text or "title" in all_text
    # Beat 4: Tactical defense map
    assert "strategy" in all_text and "map" in all_text
    # Beat 5: Streamer desk / broadcast workstation
    assert "broadcast" in all_text or "workstation" in all_text
    # Beat 6: Battlefield corpses / fallen soldiers
    assert "battlefield" in all_text or "corpses" in all_text or "fallen soldier" in all_text
    # Beat 7: Lucas solitary back
    assert "lucas" in all_text and ("solitary back" in all_text or "behind vanguard knight" in all_text)


def test_clean_keyframe_assets_exist_and_geometry() -> None:
    """Ensure all clean keyframe PNGs referenced in TRANSITIONS exist and are 1280x720."""
    referenced_keyframes = set()
    for spec in TRANSITIONS:
        referenced_keyframes.add(spec.start_keyframe)
        referenced_keyframes.add(spec.end_keyframe)

    for kf_name in referenced_keyframes:
        kf_path = DEFAULT_CLEAN_DIR / kf_name
        assert kf_path.is_file(), f"Referenced keyframe missing: {kf_path}"
        img = cv2.imread(str(kf_path))
        assert img is not None, f"Failed to read image {kf_path}"
        h, w, c = img.shape
        assert (w, h) == (1280, 720), f"Keyframe {kf_name} has invalid geometry {w}x{h}, expected 1280x720"


def test_zero_optical_flow_mock_fallback_leakage() -> None:
    """Assert zero optical flow fallback code or mock generators remain in script."""
    script_p = Path("scripts/generate_ep01_manga_flow_transitions.py")
    script_text = script_p.read_text(encoding="utf-8")
    assert "calcOpticalFlowFarneback" not in script_text
    assert "render_optical_flow_transition" not in script_text
    assert "mock" not in script_text.lower()


def test_zero_cyrillic_hygiene_in_remediation_code_and_tests() -> None:
    """Verify zero Cyrillic characters exist across remediation scripts and test suites."""
    target_paths = [
        Path("scripts/generate_ep01_manga_flow_transitions.py"),
        Path("scripts/preprocess_ep01_manga_frames.py"),
        Path("tests/test_ttd_m2_remediation_challenge.py"),
    ]
    cyrillic_pattern = re.compile(r"[\u0400-\u04FF]")
    for p in target_paths:
        if p.is_file():
            text = p.read_text(encoding="utf-8")
            matches = list(cyrillic_pattern.finditer(text))
            assert not matches, f"Found {len(matches)} Cyrillic characters in {p}"
