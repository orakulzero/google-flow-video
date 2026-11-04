"""
tests/test_m1_iter2_remediation_challenge.py
Adversarial empirical stress-test suite verifying Milestone 1 Iteration 2 remediations
for render_latex_to_slot and _get_phase_chrome_template in scripts/moiad_visual_engines.py.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict

import matplotlib._pylab_helpers as pylab_helpers
import matplotlib.pyplot as plt
import numpy as np
import pytest
from PIL import Image, ImageFont

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import scripts.moiad_visual_engines as ve


# ============================================================================
# 1. EMPTY, WHITESPACE, NONE, AND TYPE RESILIENCE
# ============================================================================


@pytest.mark.parametrize(
    "valid_falsy",
    [
        "",
        "   ",
        "\t\n  \r\n",
        None,
        12345,
        False,
        3.14159,
    ],
)
def test_render_latex_empty_whitespace_none_inputs(valid_falsy: Any) -> None:
    """Verify render_latex_to_slot safely handles empty, whitespace, None, and hashable types without raising."""
    n0 = len(plt.get_fignums())
    img = ve.render_latex_to_slot(valid_falsy, max_w=332, max_h=38, color="#18212F")
    n1 = len(plt.get_fignums())

    assert isinstance(img, Image.Image), f"Expected PIL Image, got {type(img)}"
    assert img.mode == "RGBA", f"Expected RGBA mode, got {img.mode}"
    assert img.size == (332, 38), f"Expected (332, 38), got {img.size}"
    assert n0 == n1, f"Figure leaked on input {valid_falsy}: {n0} vs {n1}"

    # Verify image is completely transparent
    arr = np.array(img)
    assert np.all(arr[:, :, 3] == 0), f"Expected blank transparent image for {valid_falsy}"


def test_render_latex_unhashable_type_exposure() -> None:
    """Demonstrate that non-string unhashable inputs raise TypeError before isinstance check."""
    # When an unhashable type is passed, cache_key lookup at line 852 fails
    with pytest.raises(TypeError, match="unhashable type"):
        ve.render_latex_to_slot(["bad", "list"])  # type: ignore[arg-type]


# ============================================================================
# 2. FIGURE MEMORY LEAK TEST ACROSS SYNTAX ERRORS
# ============================================================================


def test_render_latex_figure_leak_on_syntax_errors() -> None:
    """Stress-test 50 distinct malformed LaTeX syntax strings to verify zero Matplotlib figure leaks."""
    invalid_expressions = [
        r"\invalid{macro",
        r"\frac{unclosed",
        r"\sqrt[incomplete",
        r"\begin{pmatrix} 1 & 0 \end{pmatrix}",
        r"\left( \frac{1}{2}",
        r"\unknowncommand{123}",
        r"x^{y^{z^{",
        r"\sum_{i=1}^{",
        r"\int_{0}^{\infty",
        r"\mathbf{unclosed",
        r"\mathrm{",
        r"\over\over\over",
        r"\underline{unclosed",
        r"\widehat{",
        r"\widetilde{",
        r"\bar{",
        r"\dot{",
        r"\ddot{",
        r"\binom{a}{",
        r"\vec{",
    ] + [f"\\badtex_{{{i}}}^{{unclosed" for i in range(30)]

    assert len(invalid_expressions) == 50

    # Ensure clean starting state
    plt.close("all")
    initial_fignums = plt.get_fignums()
    initial_managers = pylab_helpers.Gcf.get_all_fig_managers()
    assert len(initial_fignums) == 0
    assert len(initial_managers) == 0

    for idx, bad_expr in enumerate(invalid_expressions):
        img = ve.render_latex_to_slot(bad_expr, max_w=332, max_h=38)
        assert isinstance(img, Image.Image)
        assert img.mode == "RGBA"
        # On syntax error, returns blank slot (332, 38) with alpha == 0
        assert img.size == (332, 38)
        assert np.all(np.array(img)[:, :, 3] == 0)

        current_fignums = plt.get_fignums()
        current_managers = pylab_helpers.Gcf.get_all_fig_managers()
        assert len(current_fignums) == 0, f"Leaked figure on expression {idx} ({bad_expr}): {current_fignums}"
        assert len(current_managers) == 0, f"Leaked manager on expression {idx}: {current_managers}"


# ============================================================================
# 3. EXTREME SCALING CLAMPING TEST
# ============================================================================


@pytest.mark.parametrize(
    "dim",
    [
        (0, 0),
        (1, 1),
        (-5, -5),
        (-100, 38),
        (332, -50),
        (0, 38),
        (332, 0),
        (2, 2),
        (1, 10),
        (10, 1),
    ],
)
def test_render_latex_extreme_scaling_clamping(dim: tuple[int, int]) -> None:
    """Verify render_latex_to_slot clamps degenerate dimensions to >= (1, 1) without crashing."""
    w, h = dim
    img = ve.render_latex_to_slot(r"E = mc^2", max_w=w, max_h=h)
    assert isinstance(img, Image.Image)
    assert img.width >= 1, f"Expected width >= 1 for dim {dim}, got {img.width}"
    assert img.height >= 1, f"Expected height >= 1 for dim {dim}, got {img.height}"
    assert img.mode == "RGBA"


def test_render_latex_scaling_aspect_ratio_preservation() -> None:
    """Verify standard formula scales within slot while preserving valid proportions."""
    img = ve.render_latex_to_slot(r"\frac{a}{b} = c", max_w=332, max_h=38)
    assert img.width <= 332
    assert img.height <= 38
    assert img.width > 20
    assert img.height > 10
    arr = np.array(img)
    assert np.max(arr[:, :, 3]) == 255


# ============================================================================
# 4. CACHE ISOLATION AGAINST POISONING TEST
# ============================================================================


def test_render_latex_cache_isolation_across_dimensions_and_colors() -> None:
    """Verify degenerate or custom parameter calls do not poison normal production calls."""
    expr = r"D_{\mathrm{KS}} = \sup |F_n(x) - F(x)|"

    # Step 1: Call with degenerate dimensions (0, 0)
    deg_img = ve.render_latex_to_slot(expr, max_w=0, max_h=0)
    assert deg_img.size == (1, 1)

    # Step 2: Call with standard dimensions (332, 38)
    prod_img = ve.render_latex_to_slot(expr, max_w=332, max_h=38)
    assert prod_img.size != (1, 1)
    assert prod_img.width > 50
    assert prod_img.height > 10

    # Step 3: Verify compound cache keys exist separately
    assert ve._LATEX_FORMULA_CACHE[(expr, 0, 0, "#18212F")].size == (1, 1)
    assert ve._LATEX_FORMULA_CACHE[(expr, 332, 38, "#18212F")].size == prod_img.size

    # Step 4: Verify color distinction in cache
    red_img = ve.render_latex_to_slot(expr, max_w=332, max_h=38, color="#FF0000")
    blue_img = ve.render_latex_to_slot(expr, max_w=332, max_h=38, color="#0000FF")

    red_arr = np.array(red_img)
    blue_arr = np.array(blue_img)

    red_mask = red_arr[:, :, 3] > 100
    blue_mask = blue_arr[:, :, 3] > 100

    assert np.mean(red_arr[red_mask, 0]) > 200
    assert np.mean(blue_arr[blue_mask, 2]) > 200


# ============================================================================
# 5. CALLER SAFETY NET AND FALLBACK IN _get_phase_chrome_template
# ============================================================================


def _create_synthetic_fonts() -> Dict[str, Any]:
    default_font = ImageFont.load_default()
    keys = [
        "pill_b",
        "pill_s",
        "pill_10",
        "pill_95",
        "hdr_b",
        "hdr_m",
        "card_t",
        "eq_b",
        "body_s",
        "mono_b",
        "body",
    ]
    return {k: default_font for k in keys}


def test_phase_chrome_template_fallback_defect_on_broken_latex() -> None:
    """
    Empirically demonstrate the defect in _get_phase_chrome_template:
    When formula_latex has a syntax error, render_latex_to_slot returns a blank (332, 38) image.
    Because eq_img.width (332) > 1 and eq_img.height (38) > 1, line 959 incorrectly marks
    rendered_latex = True, skipping the plain text fallback and leaving the formula card blank.
    """
    fonts = _create_synthetic_fonts()
    broken_spec = {
        "ch_id": "test_broken_latex_defect",
        "ch_num": "1.1",
        "title": "Title For Broken Latex Defect Test",
        "phases": [{"num": "01", "title": "Phase 1", "desc": "Phase Description"}],
        "formula_title": "Theoretical Bound",
        "formula_latex": r"\broken{unclosed_macro",
        "formula_str": "fallback_equation(x) = y + 42",
        "formula_desc": "",  # Empty desc so only formula area is evaluated
        "gauges": [],
    }

    ve._PHASE_CHROME_CACHE.pop(("test_broken_latex_defect", 0), None)

    tpl = ve._get_phase_chrome_template(broken_spec, 0, fonts)
    arr = np.array(tpl)
    # Card 01 formula slot area: x: 914..1240, y: 98..136
    card_crop = arr[98:136, 914:1240]

    # Contract requirement: on broken LaTeX, plain text formula_str must be rendered as fallback.
    # When text is rendered, card_crop must have dark ink pixels (dark_pixels > 20).
    dark_pixels = np.sum(np.mean(card_crop, axis=2) < 100)
    assert dark_pixels > 20, (
        f"Fallback plain text was not rendered on broken LaTeX (dark_pixels={dark_pixels}). "
        f"Defect: render_latex_to_slot returned blank (332, 38) image whose dimensions > 1 "
        f"improperly marked rendered_latex=True, bypassing text fallback."
    )


def test_phase_chrome_template_fallback_success_when_latex_is_none() -> None:
    """When formula_latex is None or empty, the plain text fallback is successfully reached."""
    fonts = _create_synthetic_fonts()
    none_spec = {
        "ch_id": "test_none_latex_fallback",
        "ch_num": "1.2",
        "title": "Title For None Latex",
        "phases": [{"num": "01", "title": "Phase 1", "desc": "Phase Description"}],
        "formula_title": "None Formula",
        "formula_latex": None,
        "formula_str": "fallback_equation(x) = y + 42",
        "formula_desc": "",
        "gauges": [],
    }

    ve._PHASE_CHROME_CACHE.pop(("test_none_latex_fallback", 0), None)

    tpl = ve._get_phase_chrome_template(none_spec, 0, fonts)
    arr = np.array(tpl)
    card_crop = arr[98:136, 914:1240]

    # Contrast against the broken_latex case: here plain text IS rendered
    dark_pixels = np.sum(np.mean(card_crop, axis=2) < 100)
    assert dark_pixels > 20, f"Expected text pixels when formula_latex is None, got {dark_pixels}"
