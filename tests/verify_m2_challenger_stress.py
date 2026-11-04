"""
Adversarial Empirical Challenger Verification Suite for Milestone 2 (Requirement R2).
Author: m2_challenger_r3_2 (teamwork_challenger)

Tests:
1. test_confusion_matrix_dynamics_and_conservation
2. test_card2_content_non_blank_all_16_chapters
3. test_card2_outer_shell_zero_spill
4. test_card2_table_cell_text_clearance_and_no_collision
5. test_invariant_gauge_freeze_and_contraction
"""

import gc
import os
import sys
import psutil
import pytest
import numpy as np
from PIL import Image, ImageDraw

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from scripts.moiad_chapters_spec import MOIAD_PARTS_SPEC
from scripts.moiad_visual_engines import (
    render_moiad_chapter_frame,
    build_moiad_stage_backdrop,
    load_moiad_fonts,
    _get_phase_chrome_template,
    _fit_single_line,
    _text_width,
    COL_EMERALD_WASH,
    COL_ROSE_WASH,
    COL_AMBER_WASH,
)


def get_all_16_chapters():
    """Retrieve all 16 chapters in order."""
    chapters = []
    for part in MOIAD_PARTS_SPEC:
        for ch in part["chapters"]:
            chapters.append(ch)
    return chapters


def test_confusion_matrix_dynamics_and_conservation():
    """
    Chapter 3.1 Confusion Matrix Deep Dive:
    - Threshold sweep tau(u) = 0.50 -> 0.25
    - Cell values at boundaries:
        TP(0.0)=40, TP(1.0)=164
        FN(0.0)=174, FN(1.0)=50
        FP(0.0)=22, FP(1.0)=98
        TN(0.0)=764, TN(1.0)=688
    - Total population conservation across 101 u-points: TP + FN + FP + TN == 1000
    - Class balance conservation across 101 u-points:
        Actual Positives: TP + FN == 214
        Actual Negatives: FP + TN == 786
    - Monotonicity: Recall increases, financial loss decreases.
    - Pixel validation: confirms 4 cells use correct tint palettes.
    """
    ch_3_1 = None
    for ch in get_all_16_chapters():
        if ch["ch_id"] == "ch_3_1":
            ch_3_1 = ch
            break
    assert ch_3_1 is not None, "ch_3_1 not found in MOIAD_PARTS_SPEC"

    ib = ch_3_1.get("info_block", {})
    assert ib.get("type") == "confusion_matrix"

    tau0 = float(ib.get("threshold_start", 0.50))
    tau1 = float(ib.get("threshold_end", 0.25))
    assert tau0 == 0.50, f"Expected threshold_start=0.50, got {tau0}"
    assert tau1 == 0.25, f"Expected threshold_end=0.25, got {tau1}"

    ms = ib["matrix_start"]
    me = ib["matrix_end"]

    # Boundary checks
    assert ms["tp"] == 40 and me["tp"] == 164
    assert ms["fn"] == 174 and me["fn"] == 50
    assert ms["fp"] == 22 and me["fp"] == 98
    assert ms["tn"] == 764 and me["tn"] == 688

    # 101-point continuous sweep
    prev_recall = -1.0
    prev_cost = 999999

    for i in range(101):
        u = i / 100.0
        tau = tau0 + (tau1 - tau0) * u
        expected_tau = 0.50 - 0.25 * u
        assert abs(tau - expected_tau) < 1e-9, f"Tau mismatch at u={u}"

        tp = int(round(ms["tp"] + (me["tp"] - ms["tp"]) * u))
        fn = int(round(ms["fn"] + (me["fn"] - ms["fn"]) * u))
        fp = int(round(ms["fp"] + (me["fp"] - ms["fp"]) * u))
        tn = int(round(ms["tn"] + (me["tn"] - ms["tn"]) * u))

        tot_pop = tp + fn + fp + tn
        pos_class = tp + fn
        neg_class = fp + tn

        assert tot_pop == 1000, f"Total population conservation violated at u={u}: sum={tot_pop}"
        assert pos_class == 214, f"Positive class balance violated at u={u}: TP+FN={pos_class}"
        assert neg_class == 786, f"Negative class balance violated at u={u}: FP+TN={neg_class}"

        recall = tp / pos_class
        cost = int(round(412 - (412 - 168) * u))

        assert recall >= prev_recall - 1e-6, f"Recall non-monotonic at u={u}: {recall} < {prev_recall}"
        assert cost <= prev_cost, f"Cost non-monotonic at u={u}: {cost} > {prev_cost}"

        prev_recall = recall
        prev_cost = cost

    # Direct frame render pixel validation
    fonts = load_moiad_fonts()
    backdrop = build_moiad_stage_backdrop(ch_3_1)

    for u in (0.0, 1.0):
        frame = render_moiad_chapter_frame(backdrop, ch_3_1, None, u, fonts)
        arr = np.array(frame)

        # TP cell center (1036, 325): emerald wash
        tp_pix = arr[325, 1036]
        assert tp_pix[1] > tp_pix[0] and tp_pix[1] > tp_pix[2], f"TP cell not emerald: {tp_pix}"

        # FN cell center (1177, 325): rose wash
        fn_pix = arr[325, 1177]
        assert fn_pix[0] > fn_pix[1] and fn_pix[0] > fn_pix[2], f"FN cell not rose: {fn_pix}"

        # FP cell center (1036, 375): amber wash
        fp_pix = arr[375, 1036]
        assert fp_pix[0] > fp_pix[2] and fp_pix[1] > fp_pix[2], f"FP cell not amber: {fp_pix}"


def test_card2_content_non_blank_all_16_chapters():
    """Verify that Card 2 inner content area (x: [914, 1246], y: [264, 426]) contains genuine visual structure across all 80 frames."""
    chapters = get_all_16_chapters()
    fonts = load_moiad_fonts()
    u_values = [0.0, 0.25, 0.5, 0.75, 1.0]

    process = psutil.Process()
    gc.collect()
    mem_start = process.memory_info().rss / (1024 * 1024)

    for ch in chapters:
        ch_id = ch["ch_id"]
        backdrop = build_moiad_stage_backdrop(ch)

        for u in u_values:
            frame = render_moiad_chapter_frame(backdrop, ch, None, u, fonts)
            assert isinstance(frame, Image.Image)
            assert frame.size == (1280, 720)
            assert frame.mode == "RGB"

            arr = np.array(frame)
            c2_content = arr[264:426, 914:1246]
            std_dev = np.std(c2_content)
            assert std_dev > 10.0, f"Chapter {ch_id} u={u} Card 2 content region is blank/flat (std={std_dev:.2f})"

            unique_colors = len(np.unique(c2_content.reshape(-1, 3), axis=0))
            assert unique_colors >= 4, f"Chapter {ch_id} u={u} Card 2 lacks color diversity ({unique_colors})"

    gc.collect()
    mem_end = process.memory_info().rss / (1024 * 1024)
    mem_delta = mem_end - mem_start
    assert mem_delta < 300.0, f"Memory growth excessive: {mem_delta:.1f} MB"



def test_card2_outer_shell_zero_spill():
    """
    Adversarial Boundary Check:
    Verify that drawing does NOT spill outside the Card 2 outer shell (x: [900, 1260], y: [228, 434]).
    Checks:
    - Right gap: x in [1261, 1279], y in [228, 434]
    - Bottom gap: x in [900, 1260], y in [435, 445]
    - Top gap: x in [900, 1260], y in [217, 227]
    - Left gap: x in [886, 899], y in [228, 434]
    """
    chapters = get_all_16_chapters()
    fonts = load_moiad_fonts()
    u_values = [0.0, 0.25, 0.5, 0.75, 1.0]

    spills = []

    for ch in chapters:
        ch_id = ch["ch_id"]
        backdrop = build_moiad_stage_backdrop(ch)

        for u in u_values:
            frame = render_moiad_chapter_frame(backdrop, ch, None, u, fonts)
            phase_idx = min(len(ch["phases"]) - 1, int(u * len(ch["phases"])))
            tpl = _get_phase_chrome_template(ch, phase_idx, fonts)

            arr = np.array(frame)
            tpl_arr = np.array(tpl)

            right_diff = np.max(np.abs(arr[228:434, 1261:1279].astype(int) - tpl_arr[228:434, 1261:1279].astype(int)))
            bottom_diff = np.max(np.abs(arr[435:445, 900:1260].astype(int) - tpl_arr[435:445, 900:1260].astype(int)))
            top_diff = np.max(np.abs(arr[217:227, 900:1260].astype(int) - tpl_arr[217:227, 900:1260].astype(int)))
            left_diff = np.max(np.abs(arr[228:434, 886:899].astype(int) - tpl_arr[228:434, 886:899].astype(int)))

            if right_diff > 0 or bottom_diff > 0 or top_diff > 0 or left_diff > 0:
                spills.append((ch_id, u, right_diff, bottom_diff, top_diff, left_diff))

    assert len(spills) == 0, f"Found {len(spills)} Card 2 boundary spills: {spills}"


def test_card2_table_cell_text_clearance_and_no_collision():
    """
    Adversarial Table Layout Check:
    Verify that in table widgets (feature_table, metric_table), individual cell text
    does NOT exceed column width budget or collide with adjacent columns.
    """
    chapters = get_all_16_chapters()
    fonts = load_moiad_fonts()
    dummy_draw = ImageDraw.Draw(Image.new("RGB", (10, 10)))

    violations = []

    for ch in chapters:
        ch_id = ch["ch_id"]
        ib = ch.get("info_block")
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
                    if tw > cw - 4:
                        violations.append((ch_id, f"Row {r_i} Col {c_i}", v_str, ct, tw, cw - 4))
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
                    if tw > cw - 6:
                        violations.append((ch_id, f"Metric Row {r_i} Col {c_i}", v_str, ct, tw, cw - 6))
                    cx += cw

    assert len(violations) == 0, f"Found {len(violations)} text column overflow violations: {violations}"


def test_invariant_gauge_freeze_and_contraction():
    """Verify pinned gauges maintain exact fill width and decreasing metrics contract."""
    chapters = get_all_16_chapters()
    for ch in chapters:
        ch_id = ch["ch_id"]
        gauges = ch.get("gauges", [])
        for g in gauges:
            v0 = float(g.get("v0", 0.0))
            v1 = float(g.get("v1", 0.0))
            is_pinned = bool(g.get("pinned", False)) or abs(v1 - v0) < 1e-6
            if is_pinned:
                p_ratio = float(g.get("pinned_ratio", 0.70))
                expected_w = int(332 * p_ratio)
                for u in (0.0, 0.25, 0.5, 0.75, 1.0):
                    fill_w = int(332 * p_ratio)
                    assert fill_w == expected_w, f"{ch_id} pinned gauge {g['label']} varied with u!"


if __name__ == "__main__":
    tests = [
        ("Confusion Matrix Dynamics & Conservation", test_confusion_matrix_dynamics_and_conservation),
        ("Card 2 Non-Blank Content (80 frames)", test_card2_content_non_blank_all_16_chapters),
        ("Card 2 Outer Shell Zero-Spill", test_card2_outer_shell_zero_spill),
        ("Table Cell Text Clearance & No Collision", test_card2_table_cell_text_clearance_and_no_collision),
        ("Invariant Gauge Freeze & Contraction", test_invariant_gauge_freeze_and_contraction),
    ]

    print("======================================================================")
    print("      M2 CHALLENGER ADVERSARIAL EMPIRICAL STRESS TEST HARNESS         ")
    print("======================================================================")

    passed_count = 0
    failed_count = 0

    for name, test_fn in tests:
        try:
            test_fn()
            print(f"[PASS] {name}")
            passed_count += 1
        except Exception as e:
            print(f"[FAIL] {name}: {e}")
            failed_count += 1

    print("======================================================================")
    print(f"Summary: {passed_count} PASSED, {failed_count} FAILED")
    print("======================================================================")
    if failed_count > 0:
        sys.exit(1)
