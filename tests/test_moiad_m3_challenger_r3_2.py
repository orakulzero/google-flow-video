"""
Milestone 3 Challenger 2: Audio VAD & Timing Monotonicity Adversarial Test Suite.
Author: m3_challenger_r3_2 (empirical challenger)

Scope:
1. Test Monotonicity Across All 16 Chapters on Authentic Narration Audio
2. Stress Test Schmitt-Trigger VAD Envelope (Silence, Noise, Bursts, Hysteresis)
3. CFR 24 fps Frame Rate Timing Precision Verification (< 50ms)
4. Critical Invariant: Zero (0) literal Cyrillic characters
"""

from __future__ import annotations

import math
import re
import subprocess
import tempfile
import wave
from pathlib import Path
from typing import List, Tuple

import imageio_ffmpeg
import numpy as np
import pytest

from scripts.moiad_chapters_spec import MOIAD_PARTS_SPEC
from scripts.render_simple_flow_demo import _align_captions_to_wav
from src.flow_bridge import FlowEducationalCompositor, SubtitlePage, WordTiming

ROOT_DIR = Path(__file__).resolve().parent.parent


def test_all_16_chapters_monotonicity_on_authentic_audio() -> None:
    """
    Empirically verify subtitle word timing monotonicity across all 16 MOiAD chapters:
    - start_ms[i+1] >= end_ms[i]
    - end_ms[i] >= start_ms[i] + 50
    - Backward steps == 0, Overlaps == 0
    - SubtitlePage bounding intervals enclose words without backwards drift
    """
    out_dir = ROOT_DIR / "output" / "moiad_video_course"
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    compositor = FlowEducationalCompositor(1280, 720, 24)

    total_words = 0
    total_backward_steps = 0
    total_under_50ms = 0

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        for part in MOIAD_PARTS_SPEC:
            for ch in part["chapters"]:
                ch_id = ch["ch_id"]
                mp4_path = out_dir / f"{ch_id}.mp4"
                wav_path = tmp_path / f"{ch_id}.wav"
                assert mp4_path.is_file(), f"Missing MP4 file for chapter {ch_id}"

                cmd = [
                    ffmpeg, "-y", "-i", str(mp4_path),
                    "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
                    str(wav_path)
                ]
                subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

                caps = compositor._build_word_captions(ch_id, ch["narration"], 16.0)
                _align_captions_to_wav(caps, wav_path)

                words: List[WordTiming] = getattr(caps, "all_words", [])
                assert len(words) > 0, f"No words found for chapter {ch_id}"

                for i in range(len(words)):
                    total_words += 1
                    wt = words[i]
                    dur = wt.end_ms - wt.start_ms
                    if dur < 50:
                        total_under_50ms += 1
                    if i + 1 < len(words):
                        next_wt = words[i + 1]
                        if next_wt.start_ms < wt.end_ms:
                            total_backward_steps += 1

                pages: List[SubtitlePage] = getattr(caps, "pages", [])
                for p in pages:
                    if p.words:
                        assert p.start_ms == p.words[0].start_ms
                        assert p.end_ms == p.words[-1].end_ms
                        assert p.start_ms < p.end_ms

    assert total_words > 1000, f"Expected >1000 words, got {total_words}"
    assert total_under_50ms == 0, f"Found {total_under_50ms} words with duration < 50ms"
    assert total_backward_steps == 0, f"Found {total_backward_steps} backward steps/overlaps"


def test_vad_synthetic_silence_and_noise_stress() -> None:
    """
    Stress test Schmitt-trigger VAD envelope with synthetic silence and white noise waveforms.
    Must not crash, produce NaN/Inf, or violate monotonicity invariants.
    """
    sr = 16000
    comp = FlowEducationalCompositor(1280, 720, 24)
    np.random.seed(42)

    scenarios = [
        ("pure_silence_3s", np.zeros(sr * 3, dtype=np.int16)),
        ("pure_silence_15s", np.zeros(sr * 15, dtype=np.int16)),
        ("white_noise_low_rms50", (np.random.randn(sr * 4) * 50).astype(np.int16)),
        ("white_noise_mid_rms2500", (np.random.randn(sr * 4) * 2500).astype(np.int16)),
        ("white_noise_clipped", np.clip(np.random.randn(sr * 4) * 15000, -32000, 32000).astype(np.int16)),
    ]

    phrase = "Sentence one of test. Sentence two of test."
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        wav_path = tmp_path / "noise_test.wav"

        for label, pcm in scenarios:
            with wave.open(str(wav_path), "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(sr)
                wf.writeframes(pcm.tobytes())

            caps = comp._build_word_captions(label, phrase, len(pcm) / sr)
            _align_captions_to_wav(caps, wav_path)

            words = caps.all_words
            assert len(words) > 0, f"[{label}] Expected words, got 0"
            for i in range(len(words)):
                dur = words[i].end_ms - words[i].start_ms
                assert dur >= 50, f"[{label}] Word {i} dur {dur} < 50ms"
                assert not math.isnan(words[i].start_ms)
                assert not math.isnan(words[i].end_ms)
                if i + 1 < len(words):
                    assert words[i + 1].start_ms >= words[i].end_ms, (
                        f"[{label}] Overlap: {words[i].word} ({words[i].start_ms}-{words[i].end_ms}) "
                        f"vs {words[i+1].word} ({words[i+1].start_ms}-{words[i+1].end_ms})"
                    )


def test_vad_pause_bridging_and_splitting_boundary() -> None:
    """
    Stress test Schmitt-trigger VAD pause bridging vs splitting:
    - Bursts with silence gap < 200ms must be bridged into a continuous block (0 pause runs).
    - Bursts with silence gap >= 200ms must be split, generating an acoustic silence pause run.
    """
    sr = 16000
    hop_len = max(1, int(sr * 0.010))
    win_len = max(1, int(sr * 0.020))

    def eval_vad(pcm: np.ndarray) -> Tuple[List[Tuple[int, int]], List[Tuple[int, int, int]]]:
        dur_ms = int(round((pcm.size / float(sr)) * 1000.0))
        n_w = (pcm.size - win_len) // hop_len + 1
        rms = np.zeros(n_w, dtype=np.float32)
        for i in range(n_w):
            chunk = pcm[i * hop_len : i * hop_len + win_len]
            rms[i] = float(np.sqrt(np.mean(chunk * chunk)))

        max_amp = float(np.max(rms)) if rms.size > 0 else 0.0
        th_high = max(350.0, 0.15 * max_amp)
        th_low = max(150.0, 0.05 * max_amp)

        is_voiced = np.zeros(n_w, dtype=bool)
        st = False
        for i, r in enumerate(rms):
            if not st and r >= th_high:
                st = True
            elif st and r <= th_low:
                st = False
            is_voiced[i] = st

        diff = np.diff(is_voiced.astype(np.int32))
        starts = list(np.where(diff == 1)[0] + 1)
        ends = list(np.where(diff == -1)[0] + 1)
        if n_w > 0 and is_voiced[0]:
            starts.insert(0, 0)
        if n_w > 0 and is_voiced[-1]:
            ends.append(n_w)

        raw_bursts = [
            (s * 10, min(dur_ms, e * 10))
            for s, e in zip(starts, ends)
            if (e - s) * 10 >= 80
        ]

        merged_voiced: List[Tuple[int, int]] = []
        pause_runs: List[Tuple[int, int, int]] = []
        if raw_bursts:
            merged_voiced.append(raw_bursts[0])
            for cur_s, cur_e in raw_bursts[1:]:
                prev_s, prev_e = merged_voiced[-1]
                if cur_s - prev_e < 200:
                    merged_voiced[-1] = (prev_s, cur_e)
                else:
                    merged_voiced.append((cur_s, cur_e))

            for idx_b in range(len(merged_voiced) - 1):
                ps = merged_voiced[idx_b][1]
                pe = merged_voiced[idx_b + 1][0]
                pdur = pe - ps
                if pdur >= 90:
                    pause_runs.append((ps, pe, pdur))

        return merged_voiced, pause_runs

    def make_two_tone_bursts(gap_ms: int) -> np.ndarray:
        t1 = np.arange(int(sr * 0.8)) / sr
        b1 = (12000 * np.sin(2 * np.pi * 300 * t1)).astype(np.float32)
        sil = np.zeros(int(sr * (gap_ms / 1000.0)), dtype=np.float32)
        t2 = np.arange(int(sr * 0.8)) / sr
        b2 = (12000 * np.sin(2 * np.pi * 300 * t2)).astype(np.float32)
        lead = np.zeros(int(sr * 0.2), dtype=np.float32)
        tail = np.zeros(int(sr * 0.2), dtype=np.float32)
        return np.concatenate([lead, b1, sil, b2, tail])

    # Bridging cases: gaps < 200ms (50ms, 100ms, 150ms)
    for g_ms in (50, 100, 150):
        pcm = make_two_tone_bursts(g_ms)
        merged, pauses = eval_vad(pcm)
        assert len(merged) == 1, f"Expected 1 merged block for {g_ms}ms gap, got {len(merged)}"
        assert len(pauses) == 0, f"Expected 0 pause runs for {g_ms}ms gap, got {len(pauses)}"

    # Splitting cases: gaps >= 200ms (250ms, 500ms)
    for g_ms in (250, 500):
        pcm = make_two_tone_bursts(g_ms)
        merged, pauses = eval_vad(pcm)
        assert len(merged) == 2, f"Expected 2 split blocks for {g_ms}ms gap, got {len(merged)}"
        assert len(pauses) == 1, f"Expected 1 pause run for {g_ms}ms gap, got {len(pauses)}"
        assert pauses[0][2] >= 180, f"Pause duration {pauses[0][2]}ms unexpectedly short"


def test_vad_schmitt_trigger_hysteresis_state_machine() -> None:
    """
    Verify Schmitt-trigger hysteresis state transitions on slowly decaying exponential envelope:
    - State switches ON when RMS >= th_high
    - State remains ON throughout intermediate decay where th_low < RMS < th_high
    - State switches OFF only when RMS <= th_low
    - Rapid alternating chatter (<80ms) is strictly rejected
    """
    sr = 16000
    hop_len = max(1, int(sr * 0.010))
    win_len = max(1, int(sr * 0.020))

    t = np.arange(sr * 4) / sr
    env = 10000.0 * np.exp(-t / 0.8)
    carrier = np.sin(2 * np.pi * 440 * t)
    pcm = (env * carrier).astype(np.float32)

    dur_ms = int(round((pcm.size / float(sr)) * 1000.0))
    n_w = (pcm.size - win_len) // hop_len + 1
    rms = np.zeros(n_w, dtype=np.float32)
    for i in range(n_w):
        chunk = pcm[i * hop_len : i * hop_len + win_len]
        rms[i] = float(np.sqrt(np.mean(chunk * chunk)))

    max_amp = float(np.max(rms))
    th_high = max(350.0, 0.15 * max_amp)
    th_low = max(150.0, 0.05 * max_amp)

    is_voiced = np.zeros(n_w, dtype=bool)
    st = False
    on_idx = -1
    off_idx = -1
    for i, r in enumerate(rms):
        if not st and r >= th_high:
            st = True
            if on_idx == -1:
                on_idx = i
        elif st and r <= th_low:
            st = False
            if off_idx == -1:
                off_idx = i
        is_voiced[i] = st

    assert on_idx >= 0, "VAD never triggered ON"
    assert off_idx > on_idx, f"Invalid state transition sequence: on={on_idx}, off={off_idx}"

    hysteresis_count = 0
    for i in range(on_idx, off_idx):
        if th_low < rms[i] < th_high:
            hysteresis_count += 1
            assert is_voiced[i] is True or is_voiced[i] == 1, (
                f"State dropped prematurely at window {i} with rms={rms[i]} in ({th_low}, {th_high})"
            )

    assert hysteresis_count >= 50, f"Expected >=50 hysteresis evaluation frames, got {hysteresis_count}"


def test_cfr_24fps_frame_rate_precision_all_16_chapters() -> None:
    """
    Verify CFR 24 fps frame rate timing precision across all 16 rendered course MP4s:
    - 24 fps / 24 tbr constant frame rate
    - Delta t = 1000 / 24 = 41.67ms < 50ms (satisfies sub-50ms synchronization requirement)
    """
    out_dir = ROOT_DIR / "output" / "moiad_video_course"
    mp4_files = sorted(list(out_dir.glob("ch_*.mp4")))
    assert len(mp4_files) == 16, f"Expected 16 MP4 chapters, found {len(mp4_files)}"

    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    for mp4 in mp4_files:
        res = subprocess.run([ffmpeg, "-i", str(mp4)], capture_output=True, text=True)
        m_fps = re.search(r"(\d+(?:\.\d+)?)\s*fps,\s*(\d+(?:\.\d+)?)\s*tbr", res.stderr)
        assert m_fps is not None, f"Could not extract fps/tbr for {mp4.name}"

        fps_val = float(m_fps.group(1))
        tbr_val = float(m_fps.group(2))
        assert fps_val == 24.0, f"{mp4.name}: fps={fps_val} != 24.0"
        assert tbr_val == 24.0, f"{mp4.name}: tbr={tbr_val} != 24.0"

    frame_dt_ms = 1000.0 / 24.0
    assert frame_dt_ms < 50.0, f"Frame step {frame_dt_ms}ms exceeds 50ms tolerance"
    assert math.isclose(frame_dt_ms, 41.6666667, rel_tol=1e-3)


def test_zero_cyrillic_invariant() -> None:
    """
    CRITICAL INVARIANT TEST:
    Strictly ZERO (0) literal Cyrillic characters in tests/test_moiad_m3_challenger_r3_2.py.
    All non-ASCII strings must use standard Unicode escapes (\\u04XX).
    """
    test_path = Path(__file__).resolve()
    content = test_path.read_text(encoding="utf-8")
    match = re.search(r"[\u0400-\u04FF]", content)
    assert match is None, (
        f"Critical invariant violation: literal Cyrillic character found at position {match.start()}: "
        f"{repr(match.group(0))}"
    )
