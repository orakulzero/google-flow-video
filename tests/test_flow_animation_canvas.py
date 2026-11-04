"""
Automated pytest suite for Mayer CTML validation and Core Animation Canvas (Milestone 1).

Verifies:
1. Modality Rule: On-screen labels strictly <= 6 words per label.
2. Transition Density: Scene exhibits >= 4.0 visual state transitions per 30 seconds.
3. Zero-Clutter Check: No forbidden HUD tokens (ESKD border stamps, entropy badges, bullet cards).
4. Core Animation Canvas: CameraState, coordinate projections, and in-memory frame rendering.
5. REQ-004: 100% zero literal Cyrillic characters in codebase and tests.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"
for _p in (str(REPO_ROOT), str(SRC_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from flow_animation_canvas import AnimationCanvas, CameraState, CameraTransition, CanvasLayer
from src.flow_ctml_linter import (
    count_label_words,
    validate_modality_rule,
    validate_transition_density,
    validate_zero_clutter,
    validate_mayer_ctml_compliance,
    ModalityValidationResult,
    DensityValidationResult,
    ClutterValidationResult,
    CTMLValidationResult,
)


# ============================================================================
# Section 1: Modality Rule Tests (<= 6 words per label)
# ============================================================================


def test_modality_rule_accepts_valid_short_labels() -> None:
    valid_labels = [
        "DSP56824",                             # 1 word
        "IS61LV6416 SRAM",                      # 2 words
        "16-bit Parallel FMC Bus",              # 4 words
        "Critical Pole Radius r=0.9878",        # 4 words
        "ADDSET = 1 | DATAST = 2",              # 5 words
        "Direct Form II Biquad Section 1",      # 6 words
    ]
    res: ModalityValidationResult = validate_modality_rule(valid_labels, max_words=6)
    assert res.ok is True
    assert len(res.violations) == 0
    assert res.max_words_found == 6
    assert res.checked_count == len(valid_labels)


def test_modality_rule_rejects_verbose_sentence() -> None:
    verbose_labels = [
        "The DSP56824 processes incoming audio samples quickly",  # 7 words
        "This is an explanatory text card describing the memory architecture in full detail",  # 12 words
    ]
    res: ModalityValidationResult = validate_modality_rule(verbose_labels, max_words=6)
    assert res.ok is False
    assert len(res.violations) == 2
    assert res.violations[0].word_count == 7
    assert res.violations[1].word_count == 13


def test_modality_rule_boundary_empty_and_whitespace() -> None:
    boundary_labels = ["", "   ", "\t\n", "---", "***"]
    res = validate_modality_rule(boundary_labels, max_words=6)
    assert res.ok is True
    assert res.max_words_found == 0
    assert len(res.violations) == 0


def test_modality_rule_hyphenated_and_technical_terms() -> None:
    labels = [
        "Anti-aliasing Sallen-Key low-pass filter stage",  # 5 hyphenated words
        "Q15 fixed-point coefficient quantization",        # 4 words
    ]
    res = validate_modality_rule(labels, max_words=6)
    assert res.ok is True
    assert len(res.violations) == 0


def test_modality_rule_handles_latex_equations() -> None:
    latex_labels = [
        r"$H(z) = \frac{b_0 + b_1 z^{-1}}{1 + a_1 z^{-1}}$",
        r"$|z| = 1$",
    ]
    for expr in latex_labels:
        w_count = count_label_words(expr)
        assert w_count == 1


# ============================================================================
# Section 2: Transition Density Tests (D_trans >= 4.0 per 30s)
# ============================================================================


def test_transition_density_exact_four_per_thirty_seconds() -> None:
    # 4 transitions over 30.0s = 4.0 transitions per 30s (gaps: 3.0, 7.0, 7.0, 7.0, 6.0 <= 7.5s)
    transitions = [3.0, 10.0, 17.0, 24.0]
    res: DensityValidationResult = validate_transition_density(
        transitions, duration_sec=30.0, min_density_per_30s=4.0
    )
    assert res.ok is True
    assert pytest.approx(res.density_per_30s, 0.01) == 4.0
    assert res.total_transitions == 4


def test_transition_density_high_retention_beats() -> None:
    # 12 semantic beats over 30.0s = 12.0 transitions per 30s
    beats = [i * 2.5 for i in range(12)]
    res = validate_transition_density(beats, duration_sec=30.0, min_density_per_30s=4.0)
    assert res.ok is True
    assert pytest.approx(res.density_per_30s, 0.01) == 12.0
    assert res.uniformity_ok is True


def test_transition_density_fails_on_static_slideshow() -> None:
    # 1 transition in 30.0s = 1.0 transitions per 30s -> FAILS
    res_one = validate_transition_density([5.0], duration_sec=30.0, min_density_per_30s=4.0)
    assert res_one.ok is False
    assert pytest.approx(res_one.density_per_30s, 0.01) == 1.0

    # 0 transitions in 30.0s = 0.0 -> FAILS
    res_zero = validate_transition_density([], duration_sec=30.0, min_density_per_30s=4.0)
    assert res_zero.ok is False
    assert res_zero.density_per_30s == 0.0


def test_transition_density_scales_with_duration() -> None:
    # 60s scene with 8 transitions = 4.0 transitions per 30s -> PASS (gaps <= 7.5s)
    res_60 = validate_transition_density([3.5 + i * 7.5 for i in range(8)], duration_sec=60.0)
    assert res_60.ok is True
    assert pytest.approx(res_60.density_per_30s, 0.01) == 4.0

    # 15s scene with 2 transitions = 4.0 transitions per 30s -> PASS
    res_15 = validate_transition_density([3.0, 9.0], duration_sec=15.0)
    assert res_15.ok is True
    assert pytest.approx(res_15.density_per_30s, 0.01) == 4.0

    # 10s scene with 1 transition = 3.0 transitions per 30s -> FAILS (< 4.0)
    res_10 = validate_transition_density([5.0], duration_sec=10.0)
    assert res_10.ok is False
    assert pytest.approx(res_10.density_per_30s, 0.01) == 3.0


def test_transition_density_detects_prolonged_static_freeze() -> None:
    # 4 transitions bunched in first 2 seconds of a 30s scene (gap = 28s > 7.5s)
    bunched = [0.2, 0.6, 1.2, 1.8]
    res = validate_transition_density(
        bunched, duration_sec=30.0, min_density_per_30s=4.0, max_static_hold_sec=7.5
    )
    assert res.density_per_30s >= 4.0
    assert res.uniformity_ok is False
    assert res.max_gap_sec > 7.5
    assert res.ok is False


def test_transition_density_invalid_duration_raises() -> None:
    with pytest.raises(ValueError, match="strictly positive"):
        validate_transition_density([1.0], duration_sec=0.0)
    with pytest.raises(ValueError, match="strictly positive"):
        validate_transition_density([1.0], duration_sec=-10.0)


# ============================================================================
# Section 3: Zero-Clutter Tests (Forbidden Tokens & Telemetry Removal)
# ============================================================================


def test_zero_clutter_detects_forbidden_eskd_stamp() -> None:
    cluttered_texts = [
        "ESKD GOST 2.104 Stamp: OK (300 DPI)",
        "Title: Architecture",
    ]
    res: ClutterValidationResult = validate_zero_clutter(drawn_texts=cluttered_texts)
    assert res.ok is False
    assert len(res.violations) == 1
    assert "ESKD GOST 2.104" in res.violations[0].token


def test_zero_clutter_detects_forbidden_entropy_badge() -> None:
    cluttered_texts = [
        "PE/ELF .text Entropy: 5.82 bits/B | Spring: zeta=1.0",
        "Waveform FFT",
    ]
    res = validate_zero_clutter(drawn_texts=cluttered_texts)
    assert res.ok is False
    assert len(res.violations) == 1
    assert "Entropy" in res.violations[0].token


def test_zero_clutter_detects_bullet_list_markers() -> None:
    bullet_texts = [
        "\u2022 First static bullet point",
        "- Second static bullet point",
    ]
    res = validate_zero_clutter(drawn_texts=bullet_texts)
    assert res.ok is False
    assert len(res.violations) == 2


def test_zero_clutter_detects_legacy_gost_watermark() -> None:
    # Use Unicode escapes to test legacy Cyrillic watermark without violating REQ-004
    legacy_badge = "\u0413\u041e\u0421\u0422 2.304 \u2022 300 DPI"
    res = validate_zero_clutter(drawn_texts=[legacy_badge, "Valid Label"])
    assert res.ok is False
    assert len(res.violations) == 1


def test_zero_clutter_passes_clean_engineering_diagram() -> None:
    clean_texts = [
        "Motorola DSP56824",
        "IS61LV6416 SRAM",
        "40 MHz Core Clock",
        "Biquad Section 1",
        "L_infinity Normalized",
    ]
    res = validate_zero_clutter(drawn_texts=clean_texts)
    assert res.ok is True
    assert len(res.violations) == 0

    # Also verify AnimationCanvas clean rendering and coordinate transforms
    canvas = AnimationCanvas(width=1280, height=720)
    canvas.set_camera(CameraState(cx=400.0, cy=300.0, zoom=1.5), duration_sec=1.0)
    sx, sy = canvas.world_to_screen(400.0, 300.0, 1.5)
    assert abs(sx - 640.0) < 1e-3
    assert abs(sy - 360.0) < 1e-3
    wx, wy = canvas.screen_to_world(640.0, 360.0, 1.5)
    assert abs(wx - 400.0) < 1e-3
    assert abs(wy - 300.0) < 1e-3

    # Vectorized point conversion
    pts = np.array([[400.0, 300.0], [0.0, 0.0]])
    s_pts = canvas.world_to_screen_np(pts, 1.5)
    assert s_pts.shape == (2, 2)
    assert abs(s_pts[0, 0] - 640.0) < 1e-3

    frame = canvas.render_frame_at_t(1.5)
    assert frame.size == (1280, 720)
    raw_bytes = canvas.render_frame_bytes(1.5)
    assert len(raw_bytes) == 1280 * 720 * 3


# ============================================================================
# Section 4: Composite CTML Compliance & REQ-004 Cleanliness
# ============================================================================


def test_validate_mayer_ctml_compliance_composite_pass_and_fail() -> None:
    # 1. Compliant scene: short labels, 4 transitions, clean texts
    res_pass: CTMLValidationResult = validate_mayer_ctml_compliance(
        labels=["DSP56824 Core", "IS61LV6416 SRAM", "Parallel FMC Bus"],
        transitions=[3.0, 10.0, 17.0, 24.0],
        duration_sec=30.0,
        drawn_texts=["Valid HUD Badge"],
    )
    assert res_pass.valid is True
    assert res_pass.overall_score == 1.0
    assert "PASS" in res_pass.summary_report

    # 2. Non-compliant scene: 12-word label + ESKD stamp + 1 transition
    res_fail = validate_mayer_ctml_compliance(
        labels=["This label is way too long and explains everything on screen instead of speaking"],
        transitions=[5.0],
        duration_sec=30.0,
        drawn_texts=["ESKD GOST 2.104 Stamp: OK"],
    )
    assert res_fail.valid is False
    assert res_fail.overall_score < 0.5
    assert "FAIL" in res_fail.summary_report

    # Verify AnimationCanvas helper integration
    assert AnimationCanvas.validate_label_word_count("DSP56824 Core") is True
    assert AnimationCanvas.validate_label_word_count("Too many words in this label on screen") is False


def test_req004_zero_cyrillic_in_validation_files() -> None:
    """Verify zero literal Cyrillic characters in validation and test files."""
    cyrillic_re = re.compile(r"[\u0400-\u04ff]")
    files_to_check = [
        Path(__file__).resolve(),
        REPO_ROOT / "src" / "flow_ctml_linter.py",
        REPO_ROOT / "flow_animation_canvas.py",
    ]
    for p in files_to_check:
        assert p.is_file(), f"Missing file: {p.name}"
        content = p.read_text(encoding="utf-8")
        match = cyrillic_re.search(content)
        assert match is None, f"REQ-004 violation in {p.name} at pos {match.start()}"


def test_req004_zero_personal_tokens_in_validation_files() -> None:
    """Verify zero personal or workspace tokens in validation and test files."""
    tok_a = ("Ora" + "kul").lower()
    tok_b = ("ANTI" + "GRAVITY").lower()
    files_to_check = [
        Path(__file__).resolve(),
        REPO_ROOT / "src" / "flow_ctml_linter.py",
        REPO_ROOT / "flow_animation_canvas.py",
    ]
    for p in files_to_check:
        assert p.is_file(), f"Missing file: {p.name}"
        content = p.read_text(encoding="utf-8").lower()
        assert tok_a not in content, f"Personal token found in {p.name}"
        assert tok_b not in content, f"Workspace token found in {p.name}"
