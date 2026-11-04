"""
Empirical Adversarial Verification Suite for Milestone 4 Challenger 1 (m4_challenger_r3_1).
Zero literal Cyrillic invariant enforced.
"""

from __future__ import annotations

import math
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Tuple

import imageio_ffmpeg
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import scripts.moiad_visual_engines as ve
import scripts.moiad_chapters_spec as cs


def extract_frame_ffmpeg(video_path: Path, timestamp_sec: float) -> np.ndarray:
    """Extract an exact frame from an MP4 file at timestamp_sec using ffmpeg."""
    assert video_path.is_file(), f"Video file not found: {video_path}"
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    cmd = [
        ffmpeg,
        "-ss",
        f"{timestamp_sec:.4f}",
        "-i",
        str(video_path),
        "-vframes",
        "1",
        "-f",
        "image2pipe",
        "-pix_fmt",
        "rgb24",
        "-vcodec",
        "rawvideo",
        "-",
    ]
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    raw = res.stdout
    assert len(raw) == 1280 * 720 * 3, f"Expected 1280x720x3 = 2764800 bytes, got {len(raw)}"
    return np.frombuffer(raw, dtype=np.uint8).reshape((720, 1280, 3))


def audit_task_1_and_2_frame_extraction() -> Dict[str, np.ndarray]:
    """Task 1 & 2: Extract frame at 0:01:29 (89.0s in pr1_video / master, 7.21s in ch_1_3) and direct engine render."""
    course_dir = REPO_ROOT / "output" / "moiad_video_course"
    ch13_mp4 = course_dir / "ch_1_3.mp4"
    pr1_mp4 = course_dir / "pr1_video.mp4"
    master_mp4 = course_dir / "moiad_full_video_course.mp4"

    # Chapter durations
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    durs = {}
    for ch_name in ["ch_1_1", "ch_1_2", "ch_1_3"]:
        p = course_dir / f"{ch_name}.mp4"
        info = subprocess.run([ffmpeg, "-i", str(p)], capture_output=True, text=True, errors="replace")
        for line in info.stderr.splitlines():
            if "Duration:" in line:
                part = line.split("Duration:")[1].split(",")[0].strip()
                h, m, s = part.split(":")
                durs[ch_name] = float(h) * 3600 + float(m) * 60 + float(s)
                break

    ch13_start = durs["ch_1_1"] + durs["ch_1_2"]
    ch13_dur = durs["ch_1_3"]
    target_ts = 89.0  # 0:01:29
    rel_ts = target_ts - ch13_start
    u_val = rel_ts / ch13_dur

    print(f"[AUDIT] ch_1_1: {durs['ch_1_1']:.2f}s, ch_1_2: {durs['ch_1_2']:.2f}s -> ch_1_3 offset: {ch13_start:.2f}s")
    print(f"[AUDIT] Target ts 0:01:29 (89.0s) -> rel_ts in ch_1_3: {rel_ts:.3f}s (u = {u_val:.4f})")
    assert 0.0 <= rel_ts <= ch13_dur, f"Relative timestamp {rel_ts} out of ch_1_3 range [0, {ch13_dur}]"

    # Extract actual frames
    frame_pr1_89 = extract_frame_ffmpeg(pr1_mp4, target_ts)
    frame_master_89 = extract_frame_ffmpeg(master_mp4, target_ts)
    frame_ch13_rel = extract_frame_ffmpeg(ch13_mp4, rel_ts)

    # Save to disk for inspection
    out_dir = REPO_ROOT / "tests"
    Image.fromarray(frame_pr1_89).save(out_dir / "extracted_frame_89s_pr1.png")
    Image.fromarray(frame_ch13_rel).save(out_dir / "extracted_frame_ch13_rel.png")

    # Direct synthetic render via moiad_visual_engines
    ch_1_3 = next(ch for p in cs.MOIAD_PARTS_SPEC for ch in p["chapters"] if ch["ch_id"] == "ch_1_3")
    backdrop_arr = ve.build_moiad_stage_backdrop(ch_1_3)
    fonts = ve.load_moiad_fonts()
    sent_boundaries = [0.0, 6.470, 16.710, 25.780, 37.040]
    frame_synthetic_pil = ve.render_moiad_chapter_frame(
        backdrop_arr=backdrop_arr,
        ch_spec=ch_1_3,
        flow_sc=None,
        u_prog=u_val,
        fonts=fonts,
        sentence_boundaries=sent_boundaries,
    )
    frame_synthetic = np.array(frame_synthetic_pil)
    frame_synthetic_pil.save(out_dir / "rendered_synthetic_u1947.png")

    return {
        "pr1_89": frame_pr1_89,
        "master_89": frame_master_89,
        "ch13_rel": frame_ch13_rel,
        "synthetic": frame_synthetic,
        "u_val": u_val,
        "u_switch": 16.710 / 37.040,
    }


def audit_task_3_emerald_highlight_suppression(frames: Dict[str, Any]) -> Dict[str, Any]:
    """
    Task 3: Check right chart area (x in [700, 1260], y in [100, 520]):
    Measure emerald highlight pixel count (#00e5a3 / rgb(0, 229, 163)). Must be strictly 0.
    Also check right stage chart area (x in [454, 878], y in [74, 584]) for any rogue selection box.
    """
    results = {}

    target_emerald_rgb = np.array([0, 229, 163], dtype=np.float32)
    col_emerald_def = np.array([5, 150, 105], dtype=np.float32)

    for name in ["pr1_89", "master_89", "ch13_rel", "synthetic"]:
        arr = frames[name]
        # Crop region specified in dispatch: x in [700, 1260], y in [100, 520]
        crop_dispatch = arr[100:520, 700:1260].astype(np.float32)

        # 1. Exact match #00e5a3
        exact_emerald = np.all(arr[100:520, 700:1260] == [0, 229, 163], axis=2)
        count_exact_dispatch = int(np.sum(exact_emerald))

        # 2. Tolerant distance match (distance < 25)
        dist_emerald = np.linalg.norm(crop_dispatch - target_emerald_rgb, axis=2)
        count_fuzzy_dispatch = int(np.sum(dist_emerald < 25.0))

        # 3. Stage right chart specific area: x in [454, 878], y in [100, 520]
        crop_stage_right = arr[100:520, 454:878].astype(np.float32)
        exact_stage_right = np.all(arr[100:520, 454:878] == [0, 229, 163], axis=2)
        count_exact_stage = int(np.sum(exact_stage_right))
        dist_stage_right = np.linalg.norm(crop_stage_right - target_emerald_rgb, axis=2)
        count_fuzzy_stage = int(np.sum(dist_stage_right < 25.0))

        # 4. Check COL_EMERALD [5, 150, 105] highlight box pixels in right stage chart
        dist_col_emerald_stage = np.linalg.norm(crop_stage_right - col_emerald_def, axis=2)
        count_col_emerald_stage = int(np.sum(dist_col_emerald_stage < 10.0))

        results[name] = {
            "count_exact_dispatch": count_exact_dispatch,
            "count_fuzzy_dispatch": count_fuzzy_dispatch,
            "count_exact_stage": count_exact_stage,
            "count_fuzzy_stage": count_fuzzy_stage,
            "count_col_emerald_stage": count_col_emerald_stage,
        }
        print(
            f"[AUDIT] Emerald pixel audit for {name:<9}: "
            f"dispatch area [700:1260, 100:520] exact={count_exact_dispatch}, fuzzy={count_fuzzy_dispatch} | "
            f"stage chart [454:878, 100:520] exact={count_exact_stage}, fuzzy={count_fuzzy_stage}, col_emerald={count_col_emerald_stage}"
        )

        assert count_exact_dispatch == 0, f"Violation: {count_exact_dispatch} exact #00e5a3 pixels found in {name}!"
        assert count_fuzzy_dispatch == 0, f"Violation: {count_fuzzy_dispatch} fuzzy emerald pixels found in {name}!"
        assert count_exact_stage == 0, f"Violation: {count_exact_stage} exact #00e5a3 pixels found in right stage of {name}!"
        assert count_fuzzy_stage == 0, f"Violation: {count_fuzzy_stage} fuzzy emerald pixels found in right stage of {name}!"
        assert count_col_emerald_stage == 0, f"Violation: {count_col_emerald_stage} COL_EMERALD pixels in right stage of {name}!"

    return results


def audit_task_4_bar_selection_centering() -> List[Dict[str, Any]]:
    """
    Task 4: Check bar chart selection coordinate centering across all 5 bars:
    Measure horizontal centering deviation |(x0 + x1)/2 - x_bar_center|.
    Must be strictly < 1.0 px across all 5 bars.
    """
    fig = plt.figure(figsize=(8.64, 5.40), dpi=200, facecolor="#FFFFFF")
    gs = fig.add_gridspec(1, 2, left=0.075, right=0.975, top=0.88, bottom=0.12, wspace=0.22)
    ax1 = fig.add_subplot(gs[0, 0])
    ax2 = fig.add_subplot(gs[0, 1])
    ve._populate_backdrop_pr1_pr2("missing_mechanisms", ax1, ax2)
    fig.canvas.draw()

    scale_x = 864.0 / (8.64 * 200.0)
    scale_y = 540.0 / (5.40 * 200.0)

    def data_to_stage(x_d: float, y_d: float) -> Tuple[float, float]:
        disp = ax2.transData.transform((x_d, y_d))
        return disp[0] * scale_x, (5.40 * 200.0 - disp[1]) * scale_y

    bar_labels = ["CPU", "\u0426\u041e\u0414", "RAM", "\u041e\u0442\u043a\u043b\u0438\u043a", "\u0421\u0442\u0430\u0442\u0443\u0441"]
    bar_heights = [40, 39, 35, 30, 27]
    bar_width = 0.55
    bh_n_list = [40 / 48.0, 39 / 48.0, 35 / 48.0, 30 / 48.0, 27 / 48.0]
    half_w = 0.0549

    bar_audit_rows = []
    print(f"\n{'Idx':<3} | {'Label':<6} | {'Bar x_c':<9} | {'Box x_c':<9} | {'Deviation (px)':<14} | {'Clear_L':<7} | {'Clear_R':<7} | Status")
    print("-" * 80)

    for i in range(5):
        px_l, py_b = data_to_stage(i - bar_width / 2.0, 0.0)
        px_r, py_t = data_to_stage(i + bar_width / 2.0, bar_heights[i])
        bar_xc = (px_l + px_r) / 2.0
        bar_w = px_r - px_l

        bx_c = 0.1004 + i * 0.1998
        bh_n = bh_n_list[i]

        tl_x_2x = int((492.1 + max(0.01, bx_c - half_w) * 350.3) * 2.0)
        tl_y_2x = int((475.2 - min(0.98, bh_n + 0.02) * 410.4) * 2.0)
        br_x_2x = int((492.1 + min(0.99, bx_c + half_w) * 350.3) * 2.0)
        br_y_2x = int((475.2 - 0.0 * 410.4) * 2.0)

        box_l = (tl_x_2x - 4) // 2
        box_t = (tl_y_2x - 4) // 2
        box_r = (br_x_2x + 4) // 2
        box_b = (br_y_2x + 4) // 2

        box_xc = (box_l + box_r) / 2.0
        box_w = box_r - box_l

        deviation = abs(box_xc - bar_xc)
        clear_l = px_l - box_l
        clear_r = box_r - px_r

        row = {
            "idx": i,
            "label": bar_labels[i],
            "bar_xc": bar_xc,
            "box_xc": box_xc,
            "deviation": deviation,
            "bar_w": bar_w,
            "box_w": box_w,
            "clear_l": clear_l,
            "clear_r": clear_r,
        }
        bar_audit_rows.append(row)

        status_str = "PASS (<1.0px)" if deviation < 1.0 and clear_l > 0 and clear_r > 0 else "FAIL"
        print(f"{i:<3} | {bar_labels[i]:<6} | {bar_xc:<9.3f} | {box_xc:<9.3f} | {deviation:<14.4f} | {clear_l:<7.2f} | {clear_r:<7.2f} | {status_str}")

        assert deviation < 1.0, f"Bar {i} deviation {deviation:.4f}px >= 1.0px!"
        assert clear_l > 0, f"Bar {i} left clearance <= 0!"
        assert clear_r > 0, f"Bar {i} right clearance <= 0!"

    plt.close(fig)
    max_dev = max(r["deviation"] for r in bar_audit_rows)
    print(f"[AUDIT] Maximum centering deviation across all 5 bars: {max_dev:.4f} px (Threshold < 1.0 px)\n")
    return bar_audit_rows


def audit_task_5_card1_formula_rendering() -> Dict[str, Any]:
    """
    Task 5: Inspect Card 1 formula slot to ensure formula is rendered crisply via LaTeX without fallback errors.
    """
    ch_1_3 = next(ch for p in cs.MOIAD_PARTS_SPEC for ch in p["chapters"] if ch["ch_id"] == "ch_1_3")
    tex_expr = ch_1_3["formula_latex"]
    print(f"[AUDIT] Formula expression: {tex_expr}")

    # Render formula to slot
    rendered_slot = ve.render_latex_to_slot(tex_expr, max_w=332, max_h=38, color="#18212F")
    assert isinstance(rendered_slot, Image.Image)
    assert rendered_slot.mode == "RGBA"
    w, h = rendered_slot.size
    print(f"[AUDIT] Rendered slot dimensions: {w}x{h} px (max slot: 332x38 px)")
    assert 10 < w <= 332, f"Slot width {w} out of expected range (10, 332]"
    assert 10 < h <= 38, f"Slot height {h} out of expected range (10, 38]"

    # Non-blank check
    slot_arr = np.array(rendered_slot)
    alpha = slot_arr[:, :, 3]
    max_alpha = int(np.max(alpha))
    assert max_alpha == 255, f"Alpha channel max is {max_alpha}, expected 255 (anti-aliased text)"
    ink_pixels = int(np.sum(alpha > 50))
    print(f"[AUDIT] Rendered formula ink pixels (alpha > 50): {ink_pixels}")
    assert ink_pixels > 150, f"Suspiciously few ink pixels: {ink_pixels}"

    # Verify anti-aliasing gradient: must contain intermediate alpha values
    intermediate_alpha = np.sum((alpha > 10) & (alpha < 240))
    print(f"[AUDIT] Anti-aliased intermediate alpha pixels: {intermediate_alpha}")
    assert intermediate_alpha > 50, "Formula lacks anti-aliased font rendering"

    # Card 1 template inspection: Card 1 formula slot is located at x: 914..1246, y: 98..136
    fonts = ve.load_moiad_fonts()
    tpl = ve._get_phase_chrome_template(ch_1_3, phase_idx=1, fonts=fonts)
    tpl_arr = np.array(tpl)
    card1_slot = tpl_arr[98:136, 914:1246]
    # In Card 1, background is white (#FFFFFF = 255, 255, 255). Text ink pixels are dark (mean < 180)
    dark_ink_in_card = int(np.sum(np.mean(card1_slot, axis=2) < 180))
    print(f"[AUDIT] Card 1 slot dark ink pixels on template: {dark_ink_in_card}")
    assert dark_ink_in_card > 150, f"Card 1 slot appears blank or unpopulated: {dark_ink_in_card} pixels"

    # Save crop for record
    Image.fromarray(card1_slot).save(REPO_ROOT / "tests" / "card1_formula_slot_crop.png")

    return {
        "formula_tex": tex_expr,
        "width": w,
        "height": h,
        "ink_pixels": ink_pixels,
        "intermediate_alpha": intermediate_alpha,
        "dark_ink_in_card": dark_ink_in_card,
    }


def test_audit_task_1_and_2_frame_extraction():
    """Verify frame extraction at 0:01:29 and direct engine render comparison."""
    frames = audit_task_1_and_2_frame_extraction()
    assert "pr1_89" in frames
    assert "ch13_rel" in frames
    assert "synthetic" in frames


def test_audit_task_3_emerald_highlight_suppression():
    """Verify strictly zero emerald highlight pixels in right chart area at 0:01:29."""
    frames = audit_task_1_and_2_frame_extraction()
    res = audit_task_3_emerald_highlight_suppression(frames)
    for name, counts in res.items():
        assert counts["count_exact_dispatch"] == 0
        assert counts["count_fuzzy_dispatch"] == 0
        assert counts["count_exact_stage"] == 0
        assert counts["count_fuzzy_stage"] == 0


def test_audit_task_4_bar_selection_centering():
    """Verify sub-pixel horizontal centering deviation < 1.0px across all 5 bars."""
    rows = audit_task_4_bar_selection_centering()
    assert len(rows) == 5
    for r in rows:
        assert r["deviation"] < 1.0
        assert r["clear_l"] > 0
        assert r["clear_r"] > 0


def test_audit_task_5_card1_formula_rendering():
    """Verify Card 1 LaTeX formula slot renders crisply without fallback or clipping."""
    res = audit_task_5_card1_formula_rendering()
    assert res["width"] <= 332
    assert res["height"] <= 38
    assert res["ink_pixels"] > 150
    assert res["intermediate_alpha"] > 50


def main():
    print("=" * 80)
    print("EMPIRICAL CHALLENGER VERIFICATION (m4_challenger_r3_1)")
    print("=" * 80)

    frames = audit_task_1_and_2_frame_extraction()
    emerald_results = audit_task_3_emerald_highlight_suppression(frames)
    bar_results = audit_task_4_bar_selection_centering()
    formula_results = audit_task_5_card1_formula_rendering()

    print("=" * 80)
    print("ALL 4 AUDIT PILLARS VERIFIED EMPIRICALLY: VERDICT = APPROVE")
    print("=" * 80)


if __name__ == "__main__":
    main()

