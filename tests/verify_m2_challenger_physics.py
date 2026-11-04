# -*- coding: utf-8 -*-
"""Adversarial empirical verification harness for M2 telemetry slider physics.

Requirements Traceability:
- REQ-M2-INVARIANT-FREEZE: Zero motion for pinned/invariant gauges across u in [0, 1].
- REQ-M2-METRIC-CONTRACTION: Physical contraction for decreasing metrics (v1 < v0).
- REQ-M2-BADGE-NON-OVERLAP: No overlap between status badges, labels, and value readouts.
"""

from __future__ import annotations

import copy
from typing import Any, Dict, List, Tuple
import pytest
from PIL import Image, ImageDraw

from scripts.moiad_chapters_spec import MOIAD_PARTS_SPEC
from scripts.moiad_visual_engines import (
    _render_frozen_gauges,
    _get_phase_chrome_template,
    _text_width,
    load_moiad_fonts,
)


class GaugeDrawSpy:
    """Spy wrapper around ImageDraw.Draw capturing all rendered primitives."""

    def __init__(self, draw: ImageDraw.ImageDraw):
        self._draw = draw
        self.rects: List[Tuple[Tuple[int, int, int, int], Dict[str, Any]]] = []
        self.texts: List[Tuple[Tuple[int, int], str, Dict[str, Any]]] = []

    def rounded_rectangle(self, xy: Any, **kwargs: Any) -> None:
        self.rects.append((tuple(xy), kwargs))
        self._draw.rounded_rectangle(xy, **kwargs)

    def text(self, xy: Any, text: str, **kwargs: Any) -> None:
        self.texts.append((tuple(xy), str(text), kwargs))
        self._draw.text(xy, text, **kwargs)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._draw, name)


def _extract_gauge_bars_and_badges(
    gauges: List[Dict[str, Any]], u: float, fonts: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """Execute _render_frozen_gauges with spy and extract geometric attributes."""
    img = Image.new("RGBA", (1280, 720), (255, 255, 255, 0))
    draw = ImageDraw.Draw(img)
    spy = GaugeDrawSpy(draw)

    _render_frozen_gauges(spy, gauges, u, fonts)

    results = []
    for g_idx, g in enumerate(gauges[:3]):
        gy = 266 + g_idx * 52
        # Track: [914, gy + 20, 1246, gy + 30]
        # Bar:   [914, gy + 20, 914 + fill_w, gy + 30]
        fill_rects = [
            r for r, kw in spy.rects
            if r[0] == 914 and r[1] == gy + 20 and r[3] == gy + 30 and r[2] < 1246
        ]
        if not fill_rects:
            # Full width fill matches 1246
            fill_rects = [
                r for r, kw in spy.rects
                if r[0] == 914 and r[1] == gy + 20 and r[3] == gy + 30 and r[2] == 1246
            ]
        fill_w = fill_rects[0][2] - 914 if fill_rects else None

        # Badge rect: [badge_x0, gy, badge_x1, gy + 17]
        badge_rects = [
            r for r, kw in spy.rects
            if r[1] == gy and r[3] == gy + 17
        ]
        badge_box = badge_rects[0] if badge_rects else None

        # Texts at this line gy
        line_texts = [t for t in spy.texts if t[0][1] == gy or t[0][1] == gy + 1]

        results.append({
            "gauge": g,
            "fill_w": fill_w,
            "badge_box": badge_box,
            "line_texts": line_texts,
            "u": u,
        })
    return results


def _find_chapter_gauges(ch_id: str) -> List[Dict[str, Any]]:
    for part in MOIAD_PARTS_SPEC:
        for ch in part.get("chapters", []):
            if ch.get("ch_id") == ch_id:
                return ch.get("gauges", [])
    raise ValueError(f"Chapter {ch_id} not found in MOIAD_PARTS_SPEC")


def test_adversarial_100_point_u_sample_pinned_gauges_zero_motion():
    """Assert max(fill_w) - min(fill_w) == 0 across 100 sample points in [0.0, 1.0]."""
    fonts = load_moiad_fonts()
    u_samples = [i / 99.0 for i in range(100)]

    # Collect pinned gauges from real chapters
    target_chapters = ["ch_1_2", "ch_2_4", "ch_4_1"]
    test_suites: List[Tuple[str, Dict[str, Any]]] = []

    for ch_id in target_chapters:
        for g in _find_chapter_gauges(ch_id):
            v0, v1 = float(g.get("v0", 0.0)), float(g.get("v1", 0.0))
            if g.get("pinned", False) or abs(v1 - v0) < 1e-6:
                test_suites.append((f"{ch_id}:{g['label']}", g))

    # Add synthetic adversarial pinned test cases
    synthetic_pinned = [
        {"label": "Synthetic Absolute Zero", "v0": 0.0, "v1": 0.0, "unit": "hz", "pinned_ratio": 0.25},
        {"label": "Synthetic Large Constant", "v0": 1e6, "v1": 1e6, "unit": "req", "pinned_ratio": 0.90},
        {"label": "Synthetic Negative Offset", "v0": -42.5, "v1": -42.5, "unit": "db", "pinned_ratio": 0.50},
        {"label": "Synthetic Flagged Invariant", "v0": 12.0, "v1": 99.0, "pinned": True, "pinned_ratio": 0.77, "unit": "ms"},
        {"label": "\u0418\u043d\u0432\u0430\u0440\u0438\u0430\u043d\u0442 Cyrillic Label", "v0": 3.1415, "v1": 3.1415, "unit": "rad"},
    ]
    for s_g in synthetic_pinned:
        test_suites.append((f"synthetic:{s_g['label']}", s_g))

    assert len(test_suites) >= 5, f"Expected at least 5 pinned test suites, got {len(test_suites)}"

    measurements = {}
    for name, g in test_suites:
        widths = []
        for u in u_samples:
            res = _extract_gauge_bars_and_badges([g], u, fonts)
            w = res[0]["fill_w"]
            assert w is not None, f"Gauge {name} rendered no fill bar at u={u}"
            widths.append(w)

        w_min = min(widths)
        w_max = max(widths)
        delta_w = w_max - w_min
        measurements[name] = {"min": w_min, "max": w_max, "delta": delta_w}

        # Absolute zero motion assertion!
        assert delta_w == 0, (
            f"Adversarial failure: Gauge '{name}' exhibited motion! "
            f"min(w)={w_min}, max(w)={w_max}, delta={delta_w} across 100 points of u!"
        )

    # Confirm expected ratios match mathematical definition int(332 * pinned_ratio)
    for name, g in test_suites:
        expected_ratio = float(g.get("pinned_ratio", 0.65))
        expected_w = max(14, int(332 * expected_ratio))
        actual_w = measurements[name]["min"]
        assert actual_w == expected_w, (
            f"Gauge '{name}' fill_w={actual_w} differs from expected {expected_w} "
            f"(pinned_ratio={expected_ratio})"
        )


def test_adversarial_decreasing_metrics_physical_contraction():
    """Assert fill_w(u=1.0) < fill_w(u=0.0) and monotonic contraction across 100 points."""
    fonts = load_moiad_fonts()
    u_samples = [i / 99.0 for i in range(100)]

    decreasing_cases: List[Tuple[str, Dict[str, Any]]] = [
        ("ch_2_4:GLS", {"label": "GLS Decorrelation", "v0": 0.96, "v1": 0.925, "unit": "slope"}),
        ("ch_4_1:TimeLeakage", {"label": "Temporal Leakage", "v0": 34.0, "v1": 0.0, "unit": "%"}),
        ("ch_3_1:LossCost", {"label": "Financial Loss", "v0": 412.0, "v1": 168.0, "unit": "kRub"}),
        ("ch_4_3:MAPE", {"label": "Forecast MAPE Error", "v0": 9.80, "v1": 5.42, "unit": "%"}),
        ("ch_2_3:StdError", {"label": "CLT Standard Error", "v0": 0.2887, "v1": 0.0289, "unit": "se"}),
        ("synthetic:MicroDelta", {"label": "Micro Delta", "v0": 1.0001, "v1": 1.0000, "unit": "val"}),
        ("synthetic:NegativeDecay", {"label": "Negative Decay", "v0": -10.0, "v1": -50.0, "unit": "db"}),
    ]

    for name, g in decreasing_cases:
        widths = []
        for u in u_samples:
            res = _extract_gauge_bars_and_badges([g], u, fonts)
            widths.append(res[0]["fill_w"])

        w_start = widths[0]
        w_end = widths[-1]

        # 1. Start must exceed end: physical contraction!
        assert w_end < w_start, (
            f"Contraction violated for '{name}': w(u=0.0)={w_start}, w(u=1.0)={w_end}"
        )

        # 2. Maximum contraction range: starts at max capacity 332, contracts to bottom floor 39
        assert w_start == 332, f"'{name}' expected start at 332 (100%), got {w_start}"
        assert w_end == max(14, int(332 * 0.12)), (
            f"'{name}' expected end at {max(14, int(332 * 0.12))}, got {w_end}"
        )

        # 3. Monotonic non-increasing: w(u_i) >= w(u_{i+1})
        for i in range(len(widths) - 1):
            assert widths[i] >= widths[i + 1], (
                f"Monotonicity violated for '{name}' at index {i} "
                f"(u={u_samples[i]:.3f}): {widths[i]} < {widths[i+1]}"
            )


def test_adversarial_status_badge_text_and_no_overlap():
    """Assert status badges ('\u0418\u041d\u0412\u0410\u0420\u0418\u0410\u041d\u0422' / '\u0424\u0418\u041a\u0421') render with zero overlap with labels and values."""
    fonts = load_moiad_fonts()

    test_cases = [
        # (label, v0, v1, pinned, pinned_ratio, expected_badge)
        ("\u041c\u0435\u0434\u0438\u0430\u043d\u0430 \u0437\u0430\u0434\u0435\u0440\u0436\u043a\u0438 (\u0438\u043d\u0432\u0430\u0440\u0438\u0430\u043d\u0442)", 20.58, 20.58, True, 0.50, "[\u0418\u041d\u0412\u0410\u0420\u0418\u0410\u041d\u0422]"),
        ("\u0417\u0430\u0431\u043e\u0440 \u0422\u044c\u044e\u043a\u0438 Q3 + 1.5*IQR", 10.5, 10.5, True, 0.65, "[\u0424\u0418\u041a\u0421]"),
        ("\u0421\u043c\u0435\u0449\u0435\u043d\u043d\u044b\u0439 \u043d\u0430\u043a\u043b\u043e\u043d OLS (a)", 0.96, 0.96, True, 0.70, "[\u0424\u0418\u041a\u0421]"),
        ("\u0414\u043b\u0438\u043d\u0430 \u0447\u0430\u0441\u043e\u0432\u043e\u0433\u043e \u0440\u044f\u0434\u0430 \u0442\u0440\u0430\u0444\u0438\u043a\u0430", 17520.0, 17520.0, True, 0.85, "[\u0424\u0418\u041a\u0421]"),
        ("\u041e\u0447\u0435\u043d\u044c \u0434\u043b\u0438\u043d\u043d\u044b\u0439 \u0442\u0435\u0445\u043d\u0438\u0447\u0435\u0441\u043a\u0438\u0439 \u0438\u043d\u0432\u0430\u0440\u0438\u0430\u043d\u0442 \u043f\u0430\u0440\u0430\u043c\u0435\u0442\u0440\u043e\u0432 \u0441\u0435\u0442\u0438", 100.0, 100.0, True, 0.60, "[\u0418\u041d\u0412\u0410\u0420\u0418\u0410\u041d\u0422]"),
        ("Short", 5.0, 5.0, True, 0.50, "[\u0424\u0418\u041a\u0421]"),
    ]

    for label, v0, v1, pinned, p_ratio, expected_badge in test_cases:
        gauge = {
            "label": label,
            "v0": v0,
            "v1": v1,
            "unit": "ms",
            "pinned": pinned,
            "pinned_ratio": p_ratio,
        }

        # 1. Render gauges via spy
        res = _extract_gauge_bars_and_badges([gauge], u=0.5, fonts=fonts)
        item = res[0]
        badge_box = item["badge_box"]
        assert badge_box is not None, f"Badge not rendered for pinned gauge '{label}'"

        bx0, by0, bx1, by1 = badge_box

        # 2. Check badge text content
        badge_text_found = False
        val_text_box = None
        for (tx, ty), text, kw in item["line_texts"]:
            if text == expected_badge:
                badge_text_found = True
            elif "ms" in text:
                val_text_box = (tx, ty)

        assert badge_text_found, (
            f"Expected badge '{expected_badge}' not found in rendered texts: {item['line_texts']}"
        )
        assert val_text_box is not None, f"Value text not found in line texts: {item['line_texts']}"

        # 3. Assert clearance between badge right edge and value text left edge
        val_x = val_text_box[0]
        gap_badge_to_val = val_x - bx1
        assert gap_badge_to_val >= 4, (
            f"Badge overlaps with value text for '{label}': "
            f"badge_x1={bx1}, val_x={val_x}, gap={gap_badge_to_val} px (< 4 px)"
        )

        # 4. Check label clearance in template rendering
        dummy_spec = {
            "ch_id": "test_ch",
            "ch_num": "9.9",
            "title": "Test Title",
            "formula_title": "Formula",
            "formula_str": "x = 1",
            "formula_desc": "Desc",
            "phases": [{"num": "01", "title": "P1", "desc": "Desc"}],
            "gauges": [gauge],
            # No info_block so gauges are rendered in template
        }
        tpl = _get_phase_chrome_template(dummy_spec, phase_idx=0, fonts=fonts)
        tpl_draw = ImageDraw.Draw(tpl)

        # Compute label width as drawn by template
        val_str = f"{v0:.3f} ms" if abs(v0) < 2.0 and v0 != int(v0) else f"{v0:.1f} ms"
        vw = _text_width(tpl_draw, val_str, fonts["mono_b"])
        bw = _text_width(tpl_draw, expected_badge, fonts["pill_s"])
        max_vw = vw + bw + 14
        max_label_w = 1246 - max_vw - 16 - 914

        from scripts.moiad_visual_engines import _fit_single_line
        lbl_txt, lbl_fnt = _fit_single_line(
            tpl_draw, label, fonts["body_s"],
            [fonts["pill_s"], fonts["pill_10"], fonts["pill_95"]],
            max_label_w
        )
        actual_label_w = _text_width(tpl_draw, lbl_txt, lbl_fnt)
        label_right_edge = 914 + actual_label_w

        # Badge left edge is bx0
        gap_label_to_badge = bx0 - label_right_edge
        assert gap_label_to_badge >= 10, (
            f"Badge overlaps with label for '{label}': "
            f"label_right={label_right_edge}, badge_left={bx0}, gap={gap_label_to_badge} px (< 10 px)"
        )


def test_adversarial_pixel_level_immobility_and_contraction():
    """Verify raw pixel buffers for absolute zero movement on invariants and visual contraction."""
    import numpy as np

    fonts = load_moiad_fonts()

    # Pinned gauge: check pixel diff across u = 0.0, 0.5, 1.0
    pinned_gauge = {
        "label": "Tukey IQR Invariant",
        "v0": 10.5,
        "v1": 10.5,
        "unit": "IQR",
        "pinned": True,
        "pinned_ratio": 0.65,
        "color": "emerald",
    }

    images = []
    for u in (0.0, 0.25, 0.5, 0.75, 1.0):
        img = Image.new("RGBA", (1280, 720), (255, 255, 255, 255))
        draw = ImageDraw.Draw(img)
        _render_frozen_gauges(draw, [pinned_gauge], u=u, fonts=fonts)
        # Crop the gauge bar area: [910, 260, 1250, 310]
        crop = np.array(img.crop((910, 260, 1250, 310)))
        images.append(crop)

    # Pixel-level zero motion: max diff must be 0!
    for i in range(1, len(images)):
        diff = np.abs(images[i].astype(np.int32) - images[0].astype(np.int32))
        max_diff = int(np.max(diff))
        assert max_diff == 0, f"Pixel difference detected for invariant gauge at step {i}: max_diff={max_diff}"

    # Decreasing gauge: check filled pixel count contracts
    decreasing_gauge = {
        "label": "Loss Decay",
        "v0": 100.0,
        "v1": 10.0,
        "unit": "loss",
        "color": "rose",
    }

    fill_pixel_counts = []
    for u in (0.0, 0.5, 1.0):
        img = Image.new("RGBA", (1280, 720), (255, 255, 255, 255))
        draw = ImageDraw.Draw(img)
        _render_frozen_gauges(draw, [decreasing_gauge], u=u, fonts=fonts)
        crop = np.array(img.crop((914, 286, 1246, 296)))  # bar track y: 266+20=286 to 296
        # Count saturated COL_ROSE foreground fill pixels (G < 50, B < 100)
        fg_pixels = np.sum((crop[:, :, 0] > 200) & (crop[:, :, 1] < 50) & (crop[:, :, 2] < 100))
        fill_pixel_counts.append(fg_pixels)

    # Must be strictly decreasing: e.g. 3311 -> 1846 -> 386 pixels!
    assert fill_pixel_counts[0] > fill_pixel_counts[1] > fill_pixel_counts[2], (
        f"Visual fill pixels failed to contract: {fill_pixel_counts}"
    )



def test_adversarial_extrapolation_bounds_and_safety():
    """Verify fill_w remains clamped inside Card 2 bounds even for out-of-bounds u."""
    fonts = load_moiad_fonts()

    gauges = [
        {"label": "Growing", "v0": 10.0, "v1": 100.0, "unit": "%", "color": "emerald"},
        {"label": "Decaying", "v0": 100.0, "v1": 10.0, "unit": "loss", "color": "rose"},
        {"label": "Pinned", "v0": 50.0, "v1": 50.0, "pinned": True, "pinned_ratio": 0.65, "unit": "fixed"},
    ]

    for extreme_u in (-10.0, -0.5, 0.0, 1.0, 1.5, 100.0):
        res = _extract_gauge_bars_and_badges(gauges, u=extreme_u, fonts=fonts)
        for item in res:
            w = item["fill_w"]
            assert 14 <= w <= 332, (
                f"Out of bounds fill_w={w} at extreme u={extreme_u} for {item['gauge']['label']}"
            )
            # Ensure bar does not exceed Card 2 right boundary x=1246
            bar_x1 = 914 + w
            assert bar_x1 <= 1246, f"Bar right edge {bar_x1} exceeded card edge 1246"


def test_adversarial_all_16_chapters_fallback_gauge_render_integration():
    """Verify all 16 chapters render fallback frozen gauges without crash or overflow."""
    fonts = load_moiad_fonts()

    for part in MOIAD_PARTS_SPEC:
        for ch in part.get("chapters", []):
            ch_fallback = dict(ch)
            ch_fallback["info_block"] = None  # Force gauge fallback

            tpl = _get_phase_chrome_template(ch_fallback, phase_idx=0, fonts=fonts)
            assert isinstance(tpl, Image.Image)

            for u in (0.0, 0.5, 1.0):
                img = tpl.copy()
                draw = ImageDraw.Draw(img)
                _render_frozen_gauges(draw, ch_fallback.get("gauges", []), u=u, fonts=fonts)
                assert img.size == (1280, 720)
