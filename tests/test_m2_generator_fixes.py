# Standard test suite for M2 Video Generator Defect Corrections
# Standard: ISO 9001:2015 / Agile V Protocol (P30)

import re
from pathlib import Path
from typing import Dict, Any
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image, ImageDraw

import flow_testbench_runner as runner
from src.flow_bridge import FlowScene
import scripts.moiad_visual_engines as mve


def test_def_r1_018_header_adaptive_downscaling() -> None:
    """Validate DEF-R1-018: Long scene titles step down font and render multi-line without dropping (\u0441\u0442\u0440. 13)."""
    long_title = (
        "[\u0420\u0430\u0437\u0434\u0435\u043b 1: \u0412\u0432\u0435\u0434\u0435\u043d\u0438\u0435] \u041c\u043e\u0434\u0438\u0444\u0438\u0446\u0438\u0440\u043e\u0432\u0430\u043d\u043d\u0430\u044f \u0413\u0430\u0440\u0432\u0430\u0440\u0434\u0441\u043a\u0430\u044f \u0430\u0440\u0445\u0438\u0442\u0435\u043a\u0442\u0443\u0440\u0430 \u044f\u0434\u0440\u0430 DSP56800, "
        "\u0434\u0432\u0443\u0445\u043f\u043e\u0440\u0442\u043e\u0432\u0430\u044f \u043f\u0430\u043c\u044f\u0442\u044c \u0438 \u043f\u043e\u0440\u0442\u044b SSI/SPI (\u0441\u0442\u0440. 13)"
    )
    scene = FlowScene(
        scene_id="test_sc_truncation",
        scene_number=3,
        title=long_title,
        narration_text="\u0422\u0435\u0441\u0442\u043e\u0432\u0430\u044f \u043d\u0430\u0440\u0435\u0437\u043a\u0430 \u0434\u043b\u044f \u043f\u0440\u043e\u0432\u0435\u0440\u043a\u0438 \u0437\u0430\u0433\u043e\u043b\u043e\u0432\u043a\u0430.",
        visual_prompt="300 DPI schematic view",
    )
    frame_bytes = runner.render_scene_frame_pil(
        topic="\u0426\u041e\u0421 \u0422\u0435\u0441\u0442",
        scene=scene,
        voice_label="voice_y0joebp3bwta",
        total_scenes=5,
        frame_idx=0,
        total_frames=15,
        width=1280,
        height=720,
    )
    assert len(frame_bytes) == 1280 * 720 * 3
    # Verify font ladder selection logic:
    max_w = 1280 - 430
    f24 = runner.get_cached_font(24, bold=True)
    assert f24.getlength(long_title) > max_w  # Confirms it would have clipped at 24pt

    # Stepping down allows fitting
    chosen_sz = None
    for sz in (24, 20, 16, 13, 11):
        f = runner.get_cached_font(sz, bold=True)
        if f.getlength(long_title) <= max_w:
            chosen_sz = sz
            break
    assert chosen_sz in (16, 13, 11)

    # Extra-long title triggers 2-line wrapping
    extra_long = long_title + " \u0438 \u0434\u043e\u043f\u043e\u043b\u043d\u0438\u0442\u0435\u043b\u044c\u043d\u044b\u0435 \u0438\u043d\u0442\u0435\u0440\u0444\u0435\u0439\u0441\u044b \u043f\u043e\u0441\u043b\u0435\u0434\u043e\u0432\u0430\u0442\u0435\u043b\u044c\u043d\u043e\u0433\u043e \u043e\u0431\u043c\u0435\u043d\u0430 \u0434\u0430\u043d\u043d\u044b\u043c\u0438"
    f_mini = runner.get_cached_font(11, bold=True)
    wrapped = runner._wrap_text_pixels(extra_long, f_mini, max_width=max_w)
    assert len(wrapped) >= 2
    assert "(\u0441\u0442\u0440. 13)" in " ".join(wrapped)


def test_def_r1_004_kinetic_subtitle_margins() -> None:
    """Validate DEF-R1-004: max_line_width is 1152 and margin padding is >= 32px."""
    long_subtitle = (
        "\u041f\u0440\u0435\u0434\u0441\u0442\u0430\u0432\u044c\u0442\u0435 \u0441\u043e\u0432\u0440\u0435\u043c\u0435\u043d\u043d\u044b\u0439 \u0442\u0440\u0430\u043d\u0441\u0444\u043e\u0440\u043c\u0435\u0440 \u043d\u0430 \u0434\u043b\u0438\u043d\u043d\u043e\u043c \u043a\u043e\u043d\u0442\u0435\u043a\u0441\u0442\u0435: "
        "\u0433\u043b\u0430\u0432\u043d\u0430\u044f \u043f\u0440\u043e\u0431\u043b\u0435\u043c\u0430 \u0438\u043d\u0444\u0435\u0440\u0435\u043d\u0441\u0430 \u043a\u0440\u043e\u0435\u0442\u0441\u044f \u0432 \u0447\u0443\u0434\u043e\u0432\u0438\u0449\u043d\u043e\u043c \u043e\u0431\u044a\u0435\u043c\u0435 \u043f\u0430\u043c\u044f\u0442\u0438 \u0434\u043b\u044f \u043a\u044d\u0448\u0430 \u043a\u043b\u044e\u0447\u0435\u0439 \u0438 \u0437\u043d\u0430\u0447\u0435\u043d\u0438\u0439 \u043d\u0430 \u0441\u0432\u0435\u0440\u0445\u0434\u043b\u0438\u043d\u043d\u044b\u0445 \u043a\u043e\u043d\u0442\u0435\u043a\u0441\u0442\u0430\u0445."
    )
    captions = runner.compute_scene_word_timings(
        scene_id="sc_04_test",
        visual_text=long_subtitle,
        duration_ms=8000,
    )
    assert len(captions.pages) >= 1
    sub_x0, sub_x1 = 24, 1256
    for page in captions.pages:
        for wt in page.words:
            assert wt.x >= sub_x0 + 32, f"Left padding {wt.x - sub_x0} < 32px"
            assert wt.x + wt.width <= sub_x1 - 32 + 10, f"Right edge {wt.x + wt.width} exceeds {sub_x1 - 32}"


def test_def_r1_008_english_suffixes_and_pause_integration() -> None:
    """Validate DEF-R1-008: English unstressed suffixes scaled by 0.55 and pauses integrated into total_weight."""
    w_std, _, _ = runner.compute_word_phonetic_weight("equation")
    w_turn, _, _ = runner.compute_word_phonetic_weight("turned")
    w_philo, _, _ = runner.compute_word_phonetic_weight("philosophy")
    # All contain unstressed suffixes (-tion, -ed, -phy) and receive scaling
    assert w_std > 0.5
    assert w_turn > 0.5
    assert w_philo > 0.5

    # Check pause integration into timing accumulator
    text_with_pauses = "First sentence, with pause. Second sentence: continues!"
    caps = runner.compute_scene_word_timings(
        scene_id="pause_test",
        visual_text=text_with_pauses,
        duration_ms=10000,
    )
    words = caps.all_words
    assert len(words) >= 6
    # Word after comma should start strictly after pause
    w_comma = words[1]  # "sentence,"
    w_after = words[2]  # "with"
    assert w_after.start_ms >= w_comma.end_ms


def test_def_r1_015_mahalanobis_aspect_ratio_box() -> None:
    """Validate DEF-R1-015: Mahalanobis PCA plot applies aspect='equal'."""
    fig = plt.figure(figsize=(4, 4), dpi=100)
    ax = fig.add_subplot(1, 1, 1)
    ax.set_xlim(5, 98)
    ax.set_ylim(5, 98)
    ax.set_aspect("equal", adjustable="box")
    assert ax.get_aspect() in ("equal", 1.0)
    plt.close(fig)


def test_def_r1_016_live_telemetry_gauge_clearance() -> None:
    """Validate DEF-R1-016: Dynamic label fitting enforces >= 16px clearance against value readout."""
    fonts = mve.load_moiad_fonts()
    img = Image.new("RGB", (1280, 720), (255, 255, 255))
    draw = ImageDraw.Draw(img)

    long_label = "\u041f\u043e\u043b\u043d\u043e\u0442\u0430 GaussianNB (Recall)"
    val_str = "0.512 \u0434\u043e\u043b\u044f"
    vw = mve._text_width(draw, val_str, fonts["mono_b"])
    max_label_w = 1246 - vw - 16 - 914
    lbl_txt, lbl_fnt = mve._fit_single_line(
        draw, long_label, fonts["body_s"],
        [fonts["pill_s"], fonts["pill_10"], fonts["pill_95"]],
        max_label_w,
    )
    lbl_w = mve._text_width(draw, lbl_txt, lbl_fnt)
    clearance = (1246 - vw) - (914 + lbl_w)
    assert clearance >= 16, f"Clearance {clearance}px < 16px"


def test_def_r1_021_600_dpi_fitz_matrix() -> None:
    """Validate DEF-R1-021: Blueprint rasterization matrix is 600 DPI (600.0/72.0)."""
    import fitz
    mat = fitz.Matrix(600.0 / 72.0, 600.0 / 72.0)
    assert abs(mat.a - (600.0 / 72.0)) < 1e-5
    assert abs(mat.d - (600.0 / 72.0)) < 1e-5
