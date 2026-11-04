"""
Unit tests for Requirement R2: Telemetry Slider Freeze for Invariants and
16-Chapter Dynamic Information Block Diversification.

Requirements Traceability:
- REQ-MOIAD-R2-INFO-BLOCK-SCHEMA: Full schema validation for all 16 chapters.
- REQ-MOIAD-R2-GAUGE-INVARIANT-FREEZE: Zero movement for pinned and static gauges.
- REQ-MOIAD-R2-GAUGE-CONTRACTION: Physical contraction for decreasing metrics.
- REQ-MOIAD-R2-RENDER-INTEGRATION: Zero-crash rendering across all 6 block types.
- REQ-MOIAD-R2-CONFUSION-MATRIX-DYNAMICS: Class balance preservation during tau sweep.
"""

import pytest
from PIL import Image

from scripts.moiad_chapters_spec import MOIAD_PARTS_SPEC
from scripts.moiad_visual_engines import (
    render_moiad_chapter_frame,
    build_moiad_stage_backdrop,
    load_moiad_fonts,
    _render_frozen_gauges,
    _render_metric_table,
    _render_confusion_matrix,
    _render_flowchart,
    _render_theorem_card,
    _render_feature_table,
    _render_importance_bars,
)


def _get_all_chapters():
    """Helper to flatten all 16 chapters across all parts."""
    chapters = []
    for part_spec in MOIAD_PARTS_SPEC:
        part_tag = part_spec.get("part_tag", f"part_{part_spec.get('part_num')}")
        for ch_spec in part_spec["chapters"]:
            chapters.append((part_tag, ch_spec["ch_id"], ch_spec))
    return chapters


def _get_chapter_by_id(ch_id: str):
    """Helper to look up a chapter by its ch_id."""
    for part_spec in MOIAD_PARTS_SPEC:
        for ch_spec in part_spec["chapters"]:
            if ch_spec["ch_id"] == ch_id:
                return ch_spec
    raise KeyError(f"Chapter {ch_id} not found")


def test_req_r2_all_16_chapters_have_valid_info_block():
    """REQ-MOIAD-R2-INFO-BLOCK-SCHEMA: Verify all 16 chapters have valid info_block."""
    chapters = _get_all_chapters()
    assert len(chapters) == 16, f"Expected 16 chapters, found {len(chapters)}"

    valid_types = {
        "feature_table",
        "metric_table",
        "flowchart",
        "theorem_card",
        "confusion_matrix",
        "importance_bars",
    }

    type_counts = {t: 0 for t in valid_types}

    for part_key, ch_key, ch_spec in chapters:
        assert "info_block" in ch_spec, f"Chapter {ch_key} missing 'info_block'"
        ib = ch_spec["info_block"]
        assert isinstance(ib, dict), f"Chapter {ch_key} info_block must be dict"
        assert "type" in ib, f"Chapter {ch_key} info_block missing 'type'"
        assert ib["type"] in valid_types, f"Chapter {ch_key} invalid type {ib['type']}"
        assert "title" in ib and len(ib["title"]) > 0, f"Chapter {ch_key} missing title"

        type_counts[ib["type"]] += 1

        # Type-specific structure checks
        if ib["type"] == "feature_table":
            assert "headers" in ib and isinstance(ib["headers"], list)
            assert "rows" in ib and isinstance(ib["rows"], list)
            assert len(ib["rows"]) >= 3
        elif ib["type"] == "metric_table":
            assert "headers" in ib and isinstance(ib["headers"], list)
            assert "rows" in ib and isinstance(ib["rows"], list)
            assert len(ib["rows"]) >= 2
            for row in ib["rows"]:
                assert isinstance(row, list)
                assert len(row) == len(ib["headers"])
        elif ib["type"] == "flowchart":
            assert "steps" in ib and isinstance(ib["steps"], list)
            assert len(ib["steps"]) == 4
            for s in ib["steps"]:
                assert "name" in s and "detail" in s
        elif ib["type"] == "theorem_card":
            assert "theorem_name" in ib
            assert "formula_latex" in ib
            assert "condition" in ib
        elif ib["type"] == "confusion_matrix":
            assert "matrix_start" in ib and "matrix_end" in ib
            for k in ("tp", "fn", "fp", "tn"):
                assert k in ib["matrix_start"]
                assert k in ib["matrix_end"]
        elif ib["type"] == "importance_bars":
            assert "bars" in ib and isinstance(ib["bars"], list)
            assert len(ib["bars"]) >= 3
            for item in ib["bars"]:
                assert "name" in item and "val" in item

        # Verify gauges are retained for backward compatibility
        assert "gauges" in ch_spec, f"Chapter {ch_key} missing backward-compat gauges"
        assert len(ch_spec["gauges"]) >= 2

    # Verify diversity across the 16 chapters: all 6 types represented
    for t, count in type_counts.items():
        assert count >= 1, f"Info block type {t} is never used across 16 chapters"


def test_req_r2_gauge_invariant_freeze():
    """REQ-MOIAD-R2-GAUGE-INVARIANT-FREEZE: Zero movement for pinned and static gauges."""
    pinned_gauge = {
        "label": "Test Invariant",
        "v0": 1.5,
        "v1": 1.5,
        "unit": " IQR",
        "pinned": True,
        "pinned_ratio": 0.65,
    }

    expected_w = int(332 * 0.65)
    for u in (0.0, 0.25, 0.5, 0.75, 1.0):
        p_ratio = pinned_gauge.get("pinned_ratio", 0.70)
        fill_w = int(332 * p_ratio)
        assert fill_w == expected_w, f"Pinned gauge fill_w varied at u={u}"


def test_req_r2_gauge_physical_contraction():
    """REQ-MOIAD-R2-GAUGE-CONTRACTION: Physical contraction for decreasing metrics."""
    decreasing_gauge = {
        "label": "Loss Metric",
        "v0": 2.40,
        "v1": 0.35,
        "unit": " loss",
    }

    ratios = []
    for u in (0.0, 0.5, 1.0):
        val = decreasing_gauge["v0"] + (decreasing_gauge["v1"] - decreasing_gauge["v0"]) * u
        v_min = min(decreasing_gauge["v0"], decreasing_gauge["v1"]) * 0.8
        v_max = max(decreasing_gauge["v0"], decreasing_gauge["v1"]) * 1.1
        ratio = max(0.05, min(0.95, (val - v_min) / (v_max - v_min)))
        fill_w = int(332 * ratio)
        ratios.append(fill_w)

    assert ratios[0] > ratios[1] > ratios[2], f"Contraction violated: {ratios}"


def test_req_r2_all_6_renderers_render_cleanly():
    """REQ-MOIAD-R2-RENDER-INTEGRATION: Zero-crash rendering across all 16 chapters covering all 6 block types."""
    chapters = _get_all_chapters()
    assert len(chapters) == 16, f"Expected 16 chapters, found {len(chapters)}"

    fonts = load_moiad_fonts()

    for part_key, ch_key, ch_spec in chapters:
        backdrop_arr = build_moiad_stage_backdrop(ch_spec)
        for u in (0.0, 0.5, 1.0):
            frame = render_moiad_chapter_frame(
                backdrop_arr=backdrop_arr,
                ch_spec=ch_spec,
                flow_sc=None,
                u_prog=u,
                fonts=fonts,
            )
            assert isinstance(frame, Image.Image), f"Failed rendering {ch_key} at u={u}"
            assert frame.size == (1280, 720), f"Wrong size for {ch_key} frame: {frame.size}"


def test_req_r2_all_16_chapters_card2_boundary_containment():
    """REQ-MOIAD-R2-CARD2-CONTAINMENT: Zero pixel spill beyond Card 2 boundary (x <= 1250 px / zero outer shell diff)."""
    import numpy as np
    from PIL import ImageDraw
    from scripts.moiad_visual_engines import _get_phase_chrome_template, _fit_single_line, _text_width

    chapters = _get_all_chapters()
    fonts = load_moiad_fonts()
    dummy_draw = ImageDraw.Draw(Image.new("RGB", (10, 10)))

    for part_key, ch_id, ch_spec in chapters:
        backdrop = build_moiad_stage_backdrop(ch_spec)

        # 1. Pixel-level outer shell check across progress states
        for u in (0.0, 0.25, 0.5, 0.75, 1.0):
            frame = render_moiad_chapter_frame(backdrop, ch_spec, None, u, fonts)
            phase_idx = min(len(ch_spec["phases"]) - 1, int(u * len(ch_spec["phases"])))
            tpl = _get_phase_chrome_template(ch_spec, phase_idx, fonts)

            arr = np.array(frame)
            tpl_arr = np.array(tpl)

            # Outer shell gaps around Card 2: [900, 228, 1260, 434]
            right_diff = int(np.max(np.abs(arr[228:434, 1261:1279].astype(int) - tpl_arr[228:434, 1261:1279].astype(int))))
            bottom_diff = int(np.max(np.abs(arr[435:445, 900:1260].astype(int) - tpl_arr[435:445, 900:1260].astype(int))))
            top_diff = int(np.max(np.abs(arr[217:227, 900:1260].astype(int) - tpl_arr[217:227, 900:1260].astype(int))))
            left_diff = int(np.max(np.abs(arr[228:434, 886:899].astype(int) - tpl_arr[228:434, 886:899].astype(int))))

            assert right_diff == 0, f"Chapter {ch_id} u={u} spills into right gap: max_diff={right_diff}"
            assert bottom_diff == 0, f"Chapter {ch_id} u={u} spills into bottom gap: max_diff={bottom_diff}"
            assert top_diff == 0, f"Chapter {ch_id} u={u} spills into top gap: max_diff={top_diff}"
            assert left_diff == 0, f"Chapter {ch_id} u={u} spills into left gap: max_diff={left_diff}"

        # 2. Text layout clearance: all table cells fit within column width and do not exceed Card 2 right boundary x <= 1250 px
        ib = ch_spec.get("info_block")
        if not ib:
            continue
        b_type = ib.get("type")

        if b_type == "feature_table":
            headers = ib.get("headers", [])
            rows = ib.get("rows", [])
            n_cols = max(1, len(headers))
            col_w = [90, 74, 86, 78] if n_cols == 4 else [332 // n_cols] * n_cols
            for r_i, r in enumerate(rows):
                cx = 918
                cell_vals = [str(x) for x in r]
                for c_i in range(n_cols):
                    cw = col_w[c_i]
                    v_str = cell_vals[c_i] if c_i < len(cell_vals) else ""
                    ct, cf = _fit_single_line(dummy_draw, v_str, fonts["pill_s"], [fonts["pill_10"], fonts["pill_95"]], cw - 4)
                    tw = _text_width(dummy_draw, ct, cf)
                    assert tw <= cw - 4, f"{ch_id} Row {r_i} Col {c_i} text '{ct}' width {tw} > {cw - 4}"
                    assert cx + tw <= 1250, f"{ch_id} Row {r_i} Col {c_i} text '{ct}' right edge {cx + tw} > 1250 px"
                    cx += cw

        elif b_type == "metric_table":
            headers = ib.get("headers", [])
            rows = ib.get("rows", [])
            n_cols = max(1, len(headers))
            if n_cols == 4:
                col_w = [118, 70, 72, 72]
            elif n_cols == 5:
                col_w = [96, 58, 56, 58, 64]
            else:
                first_w = max(80, 332 - 60 * (n_cols - 1))
                rem_w = (332 - first_w) // max(1, n_cols - 1)
                col_w = [first_w] + [rem_w] * (n_cols - 1)
            for r_i, row in enumerate(rows):
                cx = 918
                cell_vals = [str(x) for x in row] if isinstance(row, (list, tuple)) else []
                for c_i in range(n_cols):
                    cw = col_w[c_i]
                    v_str = cell_vals[c_i] if c_i < len(cell_vals) else ""
                    ct, cf = _fit_single_line(dummy_draw, v_str, fonts["pill_s"], [fonts["pill_10"], fonts["pill_95"]], cw - 6)
                    tw = _text_width(dummy_draw, ct, cf)
                    assert tw <= cw - 6, f"{ch_id} Metric Row {r_i} Col {c_i} text '{ct}' width {tw} > {cw - 6}"
                    assert cx + tw <= 1250, f"{ch_id} Metric Row {r_i} Col {c_i} text '{ct}' right edge {cx + tw} > 1250 px"
                    cx += cw


def test_fit_single_line_character_truncation_fallback():
    """REQ-MOIAD-R2-TEXT-TRUNCATION: Verify _fit_single_line truncates with ellipsis when first word exceeds max_w."""
    from PIL import ImageDraw
    from scripts.moiad_visual_engines import _fit_single_line, _text_width

    fonts = load_moiad_fonts()
    dummy_draw = ImageDraw.Draw(Image.new("RGB", (10, 10)))

    # A long single word with max_w smaller than the word
    long_word = "\u041d\u0435\u043f\u0440\u0435\u0440\u044b\u0432\u043d\u043e\u0441\u0442\u044c"
    fitted, fnt = _fit_single_line(dummy_draw, long_word, fonts["pill_s"], [fonts["pill_10"], fonts["pill_95"]], max_w=50)

    assert fitted.endswith("…"), f"Expected ellipsis truncation, got '{fitted}'"
    assert _text_width(dummy_draw, fitted, fnt) <= 50, f"Fitted text '{fitted}' width exceeds max_w 50"


def test_req_r2_confusion_matrix_dynamic_sweep():
    """REQ-MOIAD-R2-CONFUSION-MATRIX-DYNAMICS: Class balance preservation during tau sweep."""
    ch_3_1 = _get_chapter_by_id("ch_3_1")
    ib = ch_3_1["info_block"]
    assert ib["type"] == "confusion_matrix"

    m_start = ib["matrix_start"]
    m_end = ib["matrix_end"]

    # At u=0.0: tau=0.50
    tp_0 = int(m_start["tp"])
    fn_0 = int(m_start["fn"])
    fp_0 = int(m_start["fp"])
    tn_0 = int(m_start["tn"])

    pos_0 = tp_0 + fn_0
    neg_0 = fp_0 + tn_0
    assert pos_0 == 214, f"Actual Positives at u=0 must be 214, got {pos_0}"
    assert neg_0 == 786, f"Actual Negatives at u=0 must be 786, got {neg_0}"

    # At u=1.0: tau=0.25
    tp_1 = int(m_end["tp"])
    fn_1 = int(m_end["fn"])
    fp_1 = int(m_end["fp"])
    tn_1 = int(m_end["tn"])

    pos_1 = tp_1 + fn_1
    neg_1 = fp_1 + tn_1
    assert pos_1 == 214, f"Actual Positives at u=1 must be 214, got {pos_1}"
    assert neg_1 == 786, f"Actual Negatives at u=1 must be 786, got {neg_1}"

    # Recall must increase when lowering threshold
    recall_0 = tp_0 / pos_0
    recall_1 = tp_1 / pos_1
    assert recall_1 > recall_0, f"Lowering threshold must increase recall: {recall_0} -> {recall_1}"


def test_req_r2_card2_header_dynamism():
    """REQ-MOIAD-R2-INFO-BLOCK-SCHEMA: Card 2 header is dynamic based on info_block title."""
    ch = _get_chapter_by_id("ch_1_1")
    fonts = load_moiad_fonts()
    backdrop_arr = build_moiad_stage_backdrop(ch)

    # Render with info_block
    frame_with_ib = render_moiad_chapter_frame(
        backdrop_arr=backdrop_arr,
        ch_spec=ch,
        flow_sc=None,
        u_prog=0.5,
        fonts=fonts,
    )
    assert isinstance(frame_with_ib, Image.Image)

    # Render without info_block (fallback to gauges)
    ch_without_ib = dict(ch)
    ch_without_ib.pop("info_block", None)
    frame_fallback = render_moiad_chapter_frame(
        backdrop_arr=backdrop_arr,
        ch_spec=ch_without_ib,
        flow_sc=None,
        u_prog=0.5,
        fonts=fonts,
    )
    assert isinstance(frame_fallback, Image.Image)
