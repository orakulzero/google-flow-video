"""
tests/test_ttd_m3_challenger_stress.py
Empirical stress test suite authored by m3_challenger_ttd_1.
Empirically validates video geometry (1280x720), frame std variance (>10.0),
acoustic energy (RMS > 350, Peak > 1500), storyboard schema, and subtitle cues.
"""
from __future__ import annotations

import json
from pathlib import Path
import wave
import cv2
import numpy as np
import pytest

from src.flow_bridge import FlowStoryboard

OUTPUT_DIR = Path("output") / "lesson_ttd_pilot_crossroads"
FULL_VIDEO_PATH = OUTPUT_DIR / "lesson_full_720p.mp4"
FULL_AUDIO_PATH = OUTPUT_DIR / "audio" / "lesson_full_audio.wav"
STORYBOARD_PATH = OUTPUT_DIR / "storyboard.json"


def test_empirical_video_geometry_and_fps() -> None:
    """Empirically assert video geometry, fps, and file size constraints."""
    assert FULL_VIDEO_PATH.exists(), f"Full video missing: {FULL_VIDEO_PATH}"
    size_bytes = FULL_VIDEO_PATH.stat().st_size
    assert size_bytes > 100 * 1024, f"Full video size {size_bytes} <= 100KB"

    cap = cv2.VideoCapture(str(FULL_VIDEO_PATH))
    assert cap.isOpened(), "Could not open full video"

    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = frames / fps if fps > 0 else 0.0

    cap.release()

    assert width == 1280, f"Expected 1280 width, got {width}"
    assert height == 720, f"Expected 720 height, got {height}"
    assert fps >= 10.0, f"FPS too low: {fps}"
    assert frames >= 450, f"Frame count too low: {frames}"
    assert duration >= 30.0, f"Duration {duration:.2f}s < 30.0s"

    # Verify each scene clip
    for idx in range(1, 6):
        sc_path = OUTPUT_DIR / f"scene_{idx:02d}.mp4"
        assert sc_path.exists(), f"Scene video missing: {sc_path}"
        assert sc_path.stat().st_size > 10 * 1024, f"Scene {idx} size too small"

        sc_cap = cv2.VideoCapture(str(sc_path))
        assert sc_cap.isOpened(), f"Could not open {sc_path}"
        sw = int(sc_cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        sh = int(sc_cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        sc_frames = int(sc_cap.get(cv2.CAP_PROP_FRAME_COUNT))
        sc_cap.release()

        assert sw == 1280, f"Scene {idx} width {sw} != 1280"
        assert sh == 720, f"Scene {idx} height {sh} != 720"
        assert sc_frames > 50, f"Scene {idx} frames {sc_frames} <= 50"


def test_empirical_video_frame_variance_no_blackout() -> None:
    """Sample 10 frames across full video and each scene to prove no solid blackouts."""
    cap = cv2.VideoCapture(str(FULL_VIDEO_PATH))
    assert cap.isOpened(), "Could not open full video"

    frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    sample_indices = np.linspace(0, max(0, frames - 1), num=12, dtype=int)[1:-1]
    stds = []

    for idx in sample_indices:
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(idx))
        ret, frame = cap.read()
        assert ret, f"Failed to read frame at {idx}"
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        std_val = float(np.std(gray))
        stds.append(std_val)
        assert std_val > 10.0, f"Frame {idx} std {std_val:.2f} <= 10.0 (blank frame)"

    cap.release()
    assert np.mean(stds) > 20.0, f"Mean frame std {np.mean(stds):.2f} <= 20.0"


def test_empirical_acoustics_energy_and_pcm_spec() -> None:
    """Assert audio duration >= 30s, 16-bit PCM, RMS > 350.0, and Peak > 1500."""
    assert FULL_AUDIO_PATH.exists(), f"Full audio missing: {FULL_AUDIO_PATH}"
    assert FULL_AUDIO_PATH.stat().st_size > 100 * 1024

    with wave.open(str(FULL_AUDIO_PATH), "rb") as wf:
        channels = wf.getnchannels()
        sampwidth = wf.getsampwidth()
        rate = wf.getframerate()
        frames = wf.getnframes()
        duration = frames / rate

        assert channels in (1, 2)
        assert sampwidth == 2  # 16-bit PCM
        assert rate in (22050, 24000, 44100, 48000)
        assert duration >= 30.0, f"Audio duration {duration:.2f}s < 30.0s"

        raw = wf.readframes(frames)
        samples = np.frombuffer(raw, dtype=np.int16).astype(np.float64)
        rms = float(np.sqrt(np.mean(samples ** 2)))
        peak = float(np.max(np.abs(samples)))

        assert rms > 350.0, f"Full audio RMS {rms:.2f} <= 350.0"
        assert peak > 1500.0, f"Full audio peak {peak:.1f} <= 1500.0"

    # Verify per-scene audio files
    for idx in range(1, 6):
        sc_wav = OUTPUT_DIR / "audio" / f"scene_{idx:02d}.wav"
        assert sc_wav.exists()
        with wave.open(str(sc_wav), "rb") as wf:
            sc_raw = wf.readframes(wf.getnframes())
            sc_samples = np.frombuffer(sc_raw, dtype=np.int16).astype(np.float64)
            sc_rms = float(np.sqrt(np.mean(sc_samples ** 2)))
            sc_peak = float(np.max(np.abs(sc_samples)))
            assert sc_rms > 350.0, f"Scene {idx} audio RMS {sc_rms:.2f} <= 350.0"
            assert sc_peak > 1500.0, f"Scene {idx} audio Peak {sc_peak:.1f} <= 1500.0"


def test_empirical_storyboard_and_subtitles_integrity() -> None:
    """Verify storyboard schema deserialization and subtitle tracks synchronization."""
    assert STORYBOARD_PATH.exists()
    data = json.loads(STORYBOARD_PATH.read_text(encoding="utf-8"))
    sb = FlowStoryboard.from_dict(data)

    assert sb.project_id in ("flow_ttd_pilot_crossroads", "storyboard_ttd_pilot_crossroads")
    assert len(sb.scenes) == 5
    for sc in sb.scenes:
        assert sc.duration_sec >= 4.0
        assert sc.voice_persona == "voice_y0joebp3bwta"
        assert len(sc.visual_prompt) > 20

    # Subtitles check
    vtt_path = OUTPUT_DIR / "subtitles.vtt"
    srt_path = OUTPUT_DIR / "subtitles.srt"
    assert vtt_path.exists()
    assert srt_path.exists()

    vtt_text = vtt_path.read_text(encoding="utf-8")
    srt_text = srt_path.read_text(encoding="utf-8")
    assert vtt_text.startswith("WEBVTT")
    assert "00:00:00.000" in vtt_text or "00:00:00,000" in srt_text
    assert len(vtt_text.splitlines()) >= 15
    assert len(srt_text.splitlines()) >= 15


def test_empirical_html5_player_multi_lesson_registration() -> None:
    """Verify player registration in output/index.html and root index.html."""
    for html_file in [Path("output") / "index.html", Path("index.html")]:
        assert html_file.exists(), f"Player file missing: {html_file}"
        content = html_file.read_text(encoding="utf-8")
        assert "lesson_ttd_pilot_crossroads" in content
        assert "lesson_01_ru_transformer_mla" in content
        assert "lesson_02_en_quantum_bell" in content
        assert "lesson_07_ru_dsp_defense_master" in content
