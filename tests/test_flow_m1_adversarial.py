import re
import sys
from pathlib import Path
from typing import List, Tuple

import numpy as np
import pytest

TESTBENCH_DIR = Path(__file__).resolve().parent.parent
for _p in (str(TESTBENCH_DIR), str(TESTBENCH_DIR / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import flow_testbench_runner as runner
from src.flow_bridge import (
    FlowScene,
    WordTiming,
    SubtitlePage,
    SceneCaptions,
    build_webvtt_subtitles,
    build_srt_subtitles,
)


# ============================================================================
# Section 1: Extreme Audio Inputs for segment_acoustic_vad_16k
# ============================================================================


def test_vad_empty_and_sub_window_pcm() -> None:
    """Empirically test zero-length and sub-window PCM frames."""
    # 1. Zero length
    v, p = runner.segment_acoustic_vad_16k(np.zeros(0, dtype=np.int16))
    assert v == []
    assert p == []

    # 2. Sub-window silence (< 320 samples = 20ms at 16kHz)
    v_sub, p_sub = runner.segment_acoustic_vad_16k(np.zeros(160, dtype=np.int16))
    assert v_sub == []
    assert p_sub == [(0, 10)]

    # 3. Sub-window loud signal
    loud_sub = np.full(160, 20000, dtype=np.int16)
    v_loud_sub, p_loud_sub = runner.segment_acoustic_vad_16k(loud_sub)
    assert v_loud_sub == [(0, 10)]
    assert p_loud_sub == []


def test_vad_completely_silent_pcm_various_durations() -> None:
    """Empirically verify silence produces zero voiced bursts and single pause block."""
    for sec in [0.5, 1.0, 5.0, 30.0]:
        n_samples = int(sec * 16000)
        pcm = np.zeros(n_samples, dtype=np.int16)
        dur_ms = int(sec * 1000)
        voiced, pauses = runner.segment_acoustic_vad_16k(pcm)
        assert voiced == []
        assert pauses == [(0, dur_ms)]


def test_vad_maximum_amplitude_square_and_dc() -> None:
    """Empirically verify maximum-amplitude signals don't overflow or produce NaN."""
    sample_rate = 16000
    dur_sec = 2.0
    total_samples = int(dur_sec * sample_rate)

    # 1. Full-scale positive DC (+32767)
    pcm_dc_pos = np.full(total_samples, 32767, dtype=np.int16)
    v_pos, p_pos = runner.segment_acoustic_vad_16k(pcm_dc_pos)
    assert len(v_pos) == 1
    assert v_pos[0][0] == 0
    assert v_pos[0][1] == 2000
    assert p_pos == []

    # 2. Full-scale negative DC (-32767)
    pcm_dc_neg = np.full(total_samples, -32767, dtype=np.int16)
    v_neg, p_neg = runner.segment_acoustic_vad_16k(pcm_dc_neg)
    assert len(v_neg) == 1
    assert v_neg[0] == (0, 2000)
    assert p_neg == []

    # 3. Full-scale Nyquist square wave alternating +32767, -32767
    pcm_sq = np.empty(total_samples, dtype=np.int16)
    pcm_sq[0::2] = 32767
    pcm_sq[1::2] = -32767
    v_sq, p_sq = runner.segment_acoustic_vad_16k(pcm_sq)
    assert len(v_sq) == 1
    assert v_sq[0] == (0, 2000)
    assert p_sq == []


def test_vad_rapid_alternating_5ms_intervals() -> None:
    """
    Rapid 5ms alternating voiced (high RMS) and unvoiced (zero) signals.
    Each 5ms is smaller than min_burst_ms (100ms) and frame_ms (10ms).
    """
    sample_rate = 16000
    # 5ms = 80 samples at 16kHz
    period = 160  # 10ms total period (5ms loud, 5ms zero)
    n_periods = 200  # 2.0 seconds
    pcm = np.zeros(n_periods * period, dtype=np.int16)
    for p in range(n_periods):
        pcm[p * period : p * period + 80] = 20000

    voiced, pauses = runner.segment_acoustic_vad_16k(pcm)
    # The RMS of 5ms at 20000 and 5ms at 0 in a 20ms window:
    # chunk has 50% duty cycle, RMS = 20000 / sqrt(2) ~ 14142 > 350.
    # Therefore, window smoothed RMS is constantly high and does not flicker or crash.
    assert len(voiced) == 1
    assert voiced[0] == (0, 2000)


def test_vad_threshold_hysteresis_boundaries_349_and_151() -> None:
    """
    Test dual-threshold Schmitt trigger around 350 voiced and 150 pause thresholds.
    """
    sample_rate = 16000
    n_samples = 16000  # 1 second

    # Signal 1: Constant RMS = 349.0 (strictly below threshold_voiced = 350.0)
    # When starting in unvoiced state, RMS = 349 must NOT trigger voiced state.
    pcm_349 = np.full(n_samples, 349, dtype=np.int16)
    v_349, p_349 = runner.segment_acoustic_vad_16k(pcm_349)
    assert v_349 == [], "RMS 349 must not trigger voiced state (threshold is 350)"
    assert p_349 == [(0, 1000)]

    # Signal 2: Constant RMS = 351.0 (strictly above threshold_voiced = 350.0)
    pcm_351 = np.full(n_samples, 351, dtype=np.int16)
    v_351, p_351 = runner.segment_acoustic_vad_16k(pcm_351)
    assert len(v_351) == 1, "RMS 351 must trigger voiced state"
    assert v_351[0] == (0, 1000)

    # Signal 3: Hysteresis check: trigger to voiced (RMS 1000 for 300ms),
    # then drop to 151 RMS for 400ms, then drop to 149 RMS for 300ms.
    # In the 151 RMS region (> 150 pause threshold), the state must REMAIN VOICED.
    # In the 149 RMS region (<= 150 pause threshold), the state must TRANSITION TO PAUSE.
    pcm_hyst = np.zeros(16000, dtype=np.int16)
    # 0 to 300ms: RMS 1000 (loud)
    pcm_hyst[0 : int(0.3 * 16000)] = 1000
    # 300ms to 700ms (400ms): RMS 151 (between 150 and 350)
    pcm_hyst[int(0.3 * 16000) : int(0.7 * 16000)] = 151
    # 700ms to 1000ms (300ms): RMS 149 (below 150)
    pcm_hyst[int(0.7 * 16000) : 16000] = 149

    v_hyst, p_hyst = runner.segment_acoustic_vad_16k(pcm_hyst)
    assert len(v_hyst) == 1
    # Voiced block must extend through the 151 RMS section (up to ~700ms)
    assert v_hyst[0][0] == 0
    assert 680 <= v_hyst[0][1] <= 720
    assert len(p_hyst) == 1
    assert 680 <= p_hyst[0][0] <= 720
    assert p_hyst[0][1] == 1000


# ============================================================================
# Section 2: Bridging Stress (190ms vs 210ms)
# ============================================================================


def test_vad_bridging_exact_190ms_vs_210ms() -> None:
    """
    Test plosive closure bridging:
    Gaps < 200ms (e.g. 190ms) must bridge into a single voiced block.
    Gaps >= 200ms (e.g. 210ms) must remain split into distinct voiced blocks.
    """
    sample_rate = 16000
    burst_dur_ms = 300
    burst_samples = int(burst_dur_ms * sample_rate / 1000)

    # 1. Gap of exactly 190ms
    gap_190_ms = 190
    gap_190_samples = int(gap_190_ms * sample_rate / 1000)
    total_samples_190 = burst_samples + gap_190_samples + burst_samples
    pcm_190 = np.zeros(total_samples_190, dtype=np.int16)
    pcm_190[:burst_samples] = 5000
    pcm_190[burst_samples + gap_190_samples :] = 5000

    v_190, p_190 = runner.segment_acoustic_vad_16k(pcm_190, min_pause_ms=200)
    assert len(v_190) == 1, f"Expected 1 merged voiced block for 190ms gap, got {v_190}"
    assert p_190 == [], f"Expected 0 pauses for bridged 190ms gap, got {p_190}"

    # 2. Gap of exactly 210ms
    gap_210_ms = 210
    gap_210_samples = int(gap_210_ms * sample_rate / 1000)
    total_samples_210 = burst_samples + gap_210_samples + burst_samples
    pcm_210 = np.zeros(total_samples_210, dtype=np.int16)
    pcm_210[:burst_samples] = 5000
    pcm_210[burst_samples + gap_210_samples :] = 5000

    v_210, p_210 = runner.segment_acoustic_vad_16k(pcm_210, min_pause_ms=200)
    assert len(v_210) == 2, f"Expected 2 separate voiced blocks for 210ms gap, got {v_210}"
    assert len(p_210) == 1, f"Expected 1 pause block for 210ms gap, got {p_210}"
    # Verify the pause start and end match the burst gap
    assert p_210[0][0] == v_210[0][1]
    assert p_210[0][1] == v_210[1][0]


def test_vad_boundary_exact_200ms() -> None:
    """Gap of exactly 200ms with min_pause_ms=200: gap < min_pause_ms is False, so splits."""
    sample_rate = 16000
    burst_samples = int(300 * sample_rate / 1000)
    gap_samples = int(200 * sample_rate / 1000)
    pcm = np.zeros(burst_samples + gap_samples + burst_samples, dtype=np.int16)
    pcm[:burst_samples] = 5000
    pcm[burst_samples + gap_samples :] = 5000

    v, p = runner.segment_acoustic_vad_16k(pcm, min_pause_ms=200)
    assert len(v) == 2, "200ms gap should split when min_pause_ms=200"
    assert len(p) == 1


# ============================================================================
# Section 3: Acronym Weighting, Single-Letter Tokens, and Empty Visual Text
# ============================================================================


def test_phonetic_weight_extreme_long_acronyms() -> None:
    """Test expansion and syllable weighting on extreme hardware acronyms."""
    # Known catalog acronym: IS61LV6416
    w_is61, _, spoken_is61 = runner.compute_word_phonetic_weight("IS61LV6416")
    assert w_is61 >= 18.0, f"IS61LV6416 weight should be >= 18, got {w_is61}"

    # Unknown huge synthetic alphanumeric acronym
    huge_acronym = "ABCDEFGHIJKLMNO1234567890XYZ"
    w_huge, _, spoken_huge = runner.compute_word_phonetic_weight(huge_acronym)
    assert w_huge >= 1.0
    assert spoken_huge == huge_acronym


def test_phonetic_weight_single_letter_tokens() -> None:
    """Test single-letter conjunctions and prepositions have non-zero bounded weight."""
    tokens = ["a", "i", "v", "k", "o", "s", "u", "ya", "\u0438", "\u0432", "\u0441"]
    for tok in tokens:
        w, p, _ = runner.compute_word_phonetic_weight(tok)
        assert w >= 1.0, f"Token {tok} must have weight >= 1.0, got {w}"
        assert p == 0.0


def test_phonetic_weight_punctuation_heavy_sentences() -> None:
    """Test pause weighting behavior on punctuation-heavy tokens."""
    tokens = [
        ("word,", 1.3),
        ("word;", 1.3),
        ("word.", 2.2),
        ("word!", 2.2),
        ("word?", 2.2),
        ("word\u2014", 2.0),
        ("word:", 2.0),
        ("word", 0.0),
    ]
    for tok, expected_pause in tokens:
        _, pause_w, _ = runner.compute_word_phonetic_weight(tok)
        assert pause_w == expected_pause


def test_compute_scene_word_timings_empty_and_whitespace_text() -> None:
    """Empty or whitespace-only visual text must return empty SceneCaptions without crash."""
    for empty_text in ["", "   ", "\t\n\r"]:
        captions = runner.compute_scene_word_timings(
            scene_id="empty_scene",
            visual_text=empty_text,
            duration_ms=5000,
        )
        assert captions.scene_id == "empty_scene"
        assert captions.duration_ms == 5000
        assert captions.pages == []
        assert captions.all_words == []


# ============================================================================
# Section 4: Numerical Stability, Zero Division, and Negative Timestamps
# ============================================================================


def test_compute_scene_word_timings_monotonicity_and_non_negative() -> None:
    """Empirically test that timestamps are non-negative and monotonically non-decreasing."""
    test_texts = [
        "SingleWord",
        "Short phrase with two words",
        "Motorola DSP56824 and AD73322 with IS61LV6416 SRAM.",
        "A B C D E F G H I J K L M N O P Q R S T U V W X Y Z",
        "Word, with; heavy... punctuation?! And: dashes\u2014here.",
    ]

    for txt in test_texts:
        for dur in [500, 1000, 5000, 30000]:
            captions = runner.compute_scene_word_timings(
                scene_id="test_mono",
                visual_text=txt,
                duration_ms=dur,
            )
            assert len(captions.all_words) > 0

            # Verify WordTiming non-negativity and bounds
            for idx, wt in enumerate(captions.all_words):
                assert wt.start_ms >= 0, f"Negative start_ms {wt.start_ms} on word {wt.word}"
                assert wt.end_ms >= wt.start_ms, f"end_ms < start_ms on word {wt.word}"
                if idx > 0:
                    prev_wt = captions.all_words[idx - 1]
                    assert wt.start_ms >= prev_wt.start_ms, "start_ms non-monotonic"

            # Verify SubtitlePage non-negativity and consistency
            for p in captions.pages:
                assert p.start_ms >= 0, f"Negative page start_ms: {p.start_ms}"
                assert p.end_ms >= p.start_ms, f"Page end_ms {p.end_ms} < start_ms {p.start_ms}"


def test_compute_word_level_timings_extreme_durations_and_fps() -> None:
    """Check compute_word_level_timings edge cases: fps=0, total_frames=0, etc."""
    # fps=0 guarded by max(1, fps)
    cap = runner.compute_word_level_timings(
        audio_path=None,
        ffmpeg_exe=None,
        visual_text="Test word timings",
        fps=0,
        total_frames=100,
    )
    assert cap.duration_ms == 100000
    assert len(cap.all_words) == 3


def test_captions_subtitles_e2e_stress() -> None:
    """Stress test build_webvtt_subtitles and build_srt_subtitles with various caption structures."""
    # Scene with captions
    cap = runner.compute_scene_word_timings(
        scene_id="sc1",
        visual_text="Fast high precision DSP testing",
        duration_ms=4000,
    )
    sc = FlowScene(
        scene_id="sc1",
        scene_number=1,
        title="DSP Intro",
        narration_text="Fast high precision DSP testing",
        visual_prompt="DSP waveform",
        duration_sec=4,
        captions=cap,
    )
    vtt = build_webvtt_subtitles([sc])
    srt = build_srt_subtitles([sc])

    assert "WEBVTT" in vtt
    assert "<00:00:0" in vtt  # Has intra-cue timestamps
    assert "00:00:00,000 -->" in srt
