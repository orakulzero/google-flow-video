#!/usr/bin/env python3
"""
Full 34-Question DSP56824 Defense Cheatsheet Video Series Generator
(@WildMathing / Manim 1:1 Vertical-Projection Style, 1280x720 HD @ 24 fps).

Generates 6 thematic 3-scene video modules (18 scenes total) covering all 34 questions
(#01..#34) of `DSP56824_Defense_Cheatsheet.md`, plus:
- `output/dsp_specialty_demo/dsp_full_cheatsheet_master.mp4` (complete 6-module compilation)
- `output/dsp_specialty_demo/index.html` (interactive 34-question video navigator)
- Per-module `.mp4`, `.srt`, `.vtt`, and `contact_sheet.png` verification sheets.

Every scene enforces:
1. Strict 1:1 vertical projection between the upper physical/signal diagram and the
   lower mathematical/response graph along the shared horizontal axis `x`.
2. 100% word-for-word identity between spoken studio female narration (`voice_y0joebp3bwta`)
   and on-screen subtitles (`narration_text == tts_narration_text`), locked to actual
   acoustic pauses in the WAV waveform via `_align_captions_to_wav`.
"""

from __future__ import annotations

import asyncio
import io
import json
import math
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Callable, Dict, List, Tuple

import imageio_ffmpeg
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.render_simple_flow_demo import (
    COL_CYAN,
    COL_GOLD,
    COL_GREEN,
    COL_RED,
    _align_captions_to_wav,
    _draw_arrow_2x,
    _draw_dashed_line_2x,
    _draw_wildmathing_subtitles,
)
from src.flow_bridge import (
    FlowClient,
    FlowEducationalCompositor,
    FlowScene,
    build_srt_subtitles,
    build_webvtt_subtitles,
)


def _new_base_fig(header_text: str) -> Tuple[plt.Figure, plt.Axes]:
    """Create a 1280x720 dark Manim/WildMathing coordinate canvas with header."""
    plt.rcParams["mathtext.fontset"] = "cm"
    fig = plt.figure(figsize=(12.8, 7.2), dpi=100, facecolor="#0D111A")
    ax = fig.add_axes([0, 0, 1, 1], facecolor="#0D111A")
    ax.set_xlim(0, 12.8)
    ax.set_ylim(0, 7.2)
    ax.axis("off")

    for x in np.arange(0.8, 12.8, 0.8):
        ax.axvline(x, color="#151E2E", lw=0.6, zorder=0)
    for y in np.arange(0.8, 7.2, 0.8):
        ax.axhline(y, color="#151E2E", lw=0.6, zorder=0)

    ax.text(
        0.52,
        6.86,
        header_text,
        color="#E2E8F0",
        fontsize=13.0,
        weight="bold",
        va="center",
    )
    return fig, ax


def _draw_dual_vertical_axes(
    ax: plt.Axes,
    gx0: float,
    gw: float,
    yc_top: float,
    yc_bot: float,
    amp_y: float,
    top_title: str,
    top_color: str,
    bot_title: str,
    bot_color: str,
    top_xlab: str,
    bot_xlab: str,
    n_grid: int = 16,
) -> None:
    """Draw strictly aligned upper and lower coordinate axes for 1:1 vertical projection."""
    ax.annotate("", xy=(gx0 + gw + 0.28, yc_top), xytext=(gx0, yc_top), arrowprops=dict(arrowstyle="->", color="#64748B", lw=1.7))
    ax.annotate("", xy=(gx0, yc_top + amp_y + 0.28), xytext=(gx0, yc_top - amp_y - 0.22), arrowprops=dict(arrowstyle="->", color="#64748B", lw=1.7))
    ax.text(gx0 + 0.08, yc_top + amp_y + 0.16, top_title, color=top_color, fontsize=9.4, weight="bold")
    ax.text(gx0 + gw + 0.30, yc_top - 0.05, top_xlab, color="#94A3B8", fontsize=11.8)

    ax.annotate("", xy=(gx0 + gw + 0.28, yc_bot), xytext=(gx0, yc_bot), arrowprops=dict(arrowstyle="->", color="#64748B", lw=1.7))
    ax.annotate("", xy=(gx0, yc_bot + amp_y + 0.28), xytext=(gx0, yc_bot - amp_y - 0.22), arrowprops=dict(arrowstyle="->", color="#64748B", lw=1.7))
    ax.text(gx0 + 0.08, yc_bot - amp_y - 0.32, bot_title, color=bot_color, fontsize=9.4, weight="bold")
    ax.text(gx0 + gw + 0.30, yc_bot - 0.05, bot_xlab, color="#94A3B8", fontsize=11.8)

    for k in range(n_grid + 1):
        uk = k / float(max(1, n_grid))
        xk = gx0 + uk * gw
        ax.plot([xk, xk], [yc_bot - amp_y, yc_top + amp_y], color="#1E293B", lw=0.8, ls=":", zorder=1)


def _draw_right_info_panel(
    ax: plt.Axes,
    eq1: str,
    eq1_border: str,
    eq2: str,
    eq2_border: str,
    bullets: List[Tuple[str, str, str]],
) -> None:
    """Draw two LaTeX formula cards and 3 two-line physical bullets on the right half."""
    rx_card = 10.18
    ax.text(
        rx_card,
        5.90,
        eq1,
        color="#F8FAFC",
        fontsize=11.8,
        ha="center",
        va="center",
        bbox=dict(boxstyle="round,pad=0.30", facecolor="#131C31", edgecolor=eq1_border, lw=1.4),
    )
    ax.text(
        rx_card,
        4.84,
        eq2,
        color="#F8FAFC",
        fontsize=11.5,
        ha="center",
        va="center",
        bbox=dict(boxstyle="round,pad=0.28", facecolor="#131C31", edgecolor=eq2_border, lw=1.3),
    )
    y_positions = [(4.02, 3.68), (3.14, 2.80), (2.26, 1.92)]
    for (y1, y2), (line1, line2, col) in zip(y_positions, bullets):
        fs1 = min(8.6, 8.6 * 57.0 / max(1, len(line1)))
        fs2 = min(8.5, 8.5 * 62.0 / max(1, len(line2)))
        ax.text(7.52, y1, "\u2022 " + line1, color=col, fontsize=fs1, weight="bold")
        ax.text(7.68, y2, line2, color="#CBD5E1", fontsize=fs2)


def _fig_to_rgb(fig: plt.Figure) -> Image.Image:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=100)
    plt.close(fig)
    buf.seek(0)
    return Image.open(buf).convert("RGB")

# =============================================================================
# MODULE 2 (Questions #01, #02, #06, #12, #14, #16):
# Q15 Fixed-Point Quantization, SNR/ENOB, 36-Bit MAC Guard Bits & ASL Scaling
# =============================================================================


def _build_m2_s1_base() -> Image.Image:
    d = chr(36)
    fig, ax = _new_base_fig(
        "\u041c\u043e\u0434\u0443\u043b\u044c 2 \u2022 \u0421\u0446\u0435\u043d\u0430 1 (#02, #06, #12): \u041a\u0432\u0430\u043d\u0442\u043e\u0432\u0430\u043d\u0438\u0435 \u0432 \u0441\u0435\u0442\u043a\u0435 Q15, \u0448\u0443\u043c \u043e\u043a\u0440\u0443\u0433\u043b\u0435\u043d\u0438\u044f \u0438 SNR / ENOB"
    )
    gx0, gw, yc_top, yc_bot, amp_y = 0.92, 6.35, 5.05, 2.45, 0.88
    _draw_dual_vertical_axes(
        ax,
        gx0,
        gw,
        yc_top,
        yc_bot,
        amp_y,
        "\u042d\u0442\u0430\u043b\u043e\u043d IEEE-754 " + d + "u(t)" + d + " \u0438 \u0441\u0442\u0443\u043f\u0435\u043d\u0447\u0430\u0442\u044b\u0439 \u0441\u0438\u0433\u043d\u0430\u043b " + d + "x_q[n]" + d,
        "#38BDF8",
        "\u041e\u0448\u0438\u0431\u043a\u0430 (\u0448\u0443\u043c) \u043a\u0432\u0430\u043d\u0442\u043e\u0432\u0430\u043d\u0438\u044f " + d + r"e[n] = x_q[n] - u(nT_s) \in [-\Delta/2, +\Delta/2]" + d,
        "#FBBF24",
        d + "t" + d,
        d + "nT_s" + d,
        n_grid=16,
    )
    u_arr = np.linspace(0.0, 1.0, 500)
    y_ref = amp_y * np.sin(2.0 * np.pi * 1.5 * u_arr)
    y_quant = np.round(y_ref / (amp_y / 4.0)) * (amp_y / 4.0)
    y_err = (y_quant - y_ref) * 2.8
    ax.plot(gx0 + u_arr * gw, yc_top + y_ref, color="#38BDF8", lw=1.1, alpha=0.28)
    ax.plot(gx0 + u_arr * gw, yc_top + y_quant, color="#4ADE80", lw=1.2, alpha=0.28)
    ax.plot(gx0 + u_arr * gw, yc_bot + y_err, color="#FBBF24", lw=1.1, alpha=0.25)
    ax.axhline(yc_bot + 0.50 * amp_y, xmin=gx0 / 12.8, xmax=(gx0 + gw) / 12.8, color="#64748B", lw=0.9, ls="--")
    ax.axhline(yc_bot - 0.50 * amp_y, xmin=gx0 / 12.8, xmax=(gx0 + gw) / 12.8, color="#64748B", lw=0.9, ls="--")

    _draw_right_info_panel(
        ax,
        d + r"\mathrm{SNR} = 6.02 \cdot N + 1.76\,\mathrm{dB}" + d,
        "#38BDF8",
        d + r"\mathrm{ENOB} = \frac{\mathrm{SINAD} - 1.76}{6.02} = 11.97\,\mathrm{bit}" + d,
        "#4ADE80",
        [
            (
                "\u041a\u0430\u0436\u0434\u044b\u0439 \u0431\u0438\u0442 \u0440\u0430\u0437\u0440\u044f\u0434\u043d\u043e\u0441\u0442\u0438 N \u0443\u043c\u0435\u043d\u044c\u0448\u0430\u0435\u0442 \u0448\u0430\u0433 \u0432\u0434\u0432\u043e\u0435",
                "\u0438 \u0434\u0430\u0451\u0442 +6,02 \u0434\u0411 \u043a \u043e\u0442\u043d\u043e\u0448\u0435\u043d\u0438\u044e \u0441\u0438\u0433\u043d\u0430\u043b/\u0448\u0443\u043c (98 \u0434\u0411 \u0434\u043b\u044f 16 \u0431\u0438\u0442)",
                "#38BDF8",
            ),
            (
                "\u041d\u0438\u0436\u043d\u0438\u0439 \u0433\u0440\u0430\u0444\u0438\u043a: \u0440\u0430\u0437\u043d\u043e\u0441\u0442\u044c \u0441\u0442\u0443\u043f\u0435\u043d\u0435\u043a \u0438 \u044d\u0442\u0430\u043b\u043e\u043d\u043d\u043e\u0439 \u0432\u043e\u043b\u043d\u044b",
                "\u043e\u0431\u0440\u0430\u0437\u0443\u0435\u0442 \u0448\u0443\u043c \u043a\u0432\u0430\u043d\u0442\u043e\u0432\u0430\u043d\u0438\u044f \u0432 \u043a\u043e\u0440\u0438\u0434\u043e\u0440\u0435 \u043f\u043e\u043b\u043e\u0432\u0438\u043d\u044b \u0448\u0430\u0433\u0430",
                "#FBBF24",
            ),
            (
                "\u0412 \u043a\u0443\u0440\u0441\u043e\u0432\u043e\u043c \u043f\u0440\u043e\u0435\u043a\u0442\u0435: \u043a\u043e\u0434\u0435\u043a AD73322 \u0434\u0430\u0451\u0442 80 \u0434\u0411,",
                "\u0430 \u0441\u043a\u0432\u043e\u0437\u043d\u043e\u0439 \u0444\u0438\u043b\u044c\u0442\u0440 Q15 \u2014 73,80 \u0434\u0411 (\u043f\u0440\u0438 \u043d\u043e\u0440\u043c\u0435 \u0422\u0417 \u2265 72 \u0434\u0411)",
                "#4ADE80",
            ),
        ],
    )
    return _fig_to_rgb(fig)


def _build_m2_s2_base() -> Image.Image:
    d = chr(36)
    fig, ax = _new_base_fig(
        "\u041c\u043e\u0434\u0443\u043b\u044c 2 \u2022 \u0421\u0446\u0435\u043d\u0430 2 (#01, #14): \u0417\u0430\u0449\u0438\u0442\u043d\u044b\u0435 \u0431\u0438\u0442\u044b \u0430\u043a\u043a\u0443\u043c\u0443\u043b\u044f\u0442\u043e\u0440\u0430 (M = 2N + G = 36 \u0431\u0438\u0442) \u0438 \u043d\u0430\u0441\u044b\u0449\u0435\u043d\u0438\u0435"
    )
    gx0, gw, yc_top, yc_bot, amp_y = 0.92, 6.35, 5.05, 2.45, 0.88
    _draw_dual_vertical_axes(
        ax,
        gx0,
        gw,
        yc_top,
        yc_bot,
        amp_y,
        "\u0411\u0435\u0437 \u0437\u0430\u0449\u0438\u0442\u044b: \u0441\u0431\u0440\u043e\u0441 \u0437\u043d\u0430\u043a\u0430 (Wrap-Around) \u043f\u0440\u0438 \u0432\u044b\u0445\u043e\u0434\u0435 \u0437\u0430 " + d + r"\pm 1" + d,
        "#F87171",
        "36-\u0431\u0438\u0442\u043d\u044b\u0439 \u0430\u043a\u043a\u0443\u043c\u0443\u043b\u044f\u0442\u043e\u0440 (G=4 \u0431\u0438\u0442\u0430) + \u0430\u043f\u043f\u0430\u0440\u0430\u0442\u043d\u043e\u0435 \u043d\u0430\u0441\u044b\u0449\u0435\u043d\u0438\u0435 (Saturation)",
        "#4ADE80",
        d + "t" + d,
        d + "nT_s" + d,
        n_grid=16,
    )
    ax.axhline(yc_top + 0.68 * amp_y, xmin=gx0 / 12.8, xmax=(gx0 + gw) / 12.8, color="#FBBF24", lw=1.0, ls="--")
    ax.axhline(yc_top - 0.68 * amp_y, xmin=gx0 / 12.8, xmax=(gx0 + gw) / 12.8, color="#FBBF24", lw=1.0, ls="--")
    ax.axhline(yc_bot + 0.68 * amp_y, xmin=gx0 / 12.8, xmax=(gx0 + gw) / 12.8, color="#FBBF24", lw=1.0, ls="--")
    ax.axhline(yc_bot - 0.68 * amp_y, xmin=gx0 / 12.8, xmax=(gx0 + gw) / 12.8, color="#FBBF24", lw=1.0, ls="--")

    _draw_right_info_panel(
        ax,
        d + r"M = 2N + G = 32 + 4 = 36\,\mathrm{bit}" + d,
        "#4ADE80",
        d + r"K_{\max} = 2^G = 2^4 = 16\,\mathrm{MAC} \quad (+24\,\mathrm{dB})" + d,
        "#FBBF24",
        [
            (
                "\u0420\u0435\u0433\u0438\u0441\u0442\u0440\u044b X0 \u0438 Y0/Y1 (16 \u0431\u0438\u0442) \u0434\u0430\u044e\u0442 32-\u0431\u0438\u0442\u043d\u043e\u0435 \u043f\u0440\u043e\u0438\u0437\u0432\u0435\u0434\u0435\u043d\u0438\u0435,",
                "\u0430 4 \u0437\u0430\u0449\u0438\u0442\u043d\u044b\u0445 \u0431\u0438\u0442\u0430 A2/B2 \u0443\u0434\u0435\u0440\u0436\u0438\u0432\u0430\u044e\u0442 \u0441\u0443\u043c\u043c\u0443 \u0431\u0435\u0437 \u043f\u0435\u0440\u0435\u043f\u043e\u043b\u043d\u0435\u043d\u0438\u044f",
                "#38BDF8",
            ),
            (
                "\u0412\u0435\u0440\u0445\u043d\u0438\u0439 \u0433\u0440\u0430\u0444\u0438\u043a: \u0431\u0435\u0437 \u0437\u0430\u0449\u0438\u0442\u044b \u043f\u0440\u0435\u0432\u044b\u0448\u0435\u043d\u0438\u0435 \u043f\u043e\u0440\u043e\u0433\u0430 +1",
                "\u043c\u0433\u043d\u043e\u0432\u0435\u043d\u043d\u043e \u043e\u043f\u0440\u043e\u043a\u0438\u0434\u044b\u0432\u0430\u0435\u0442 \u0432\u043e\u043b\u043d\u0443 \u0432 \u043e\u0442\u0440\u0438\u0446\u0430\u0442\u0435\u043b\u044c\u043d\u044b\u0439 \u043f\u0438\u043a -1",
                "#F87171",
            ),
            (
                "\u041d\u0438\u0436\u043d\u0438\u0439 \u0433\u0440\u0430\u0444\u0438\u043a: \u043b\u043e\u0433\u0438\u043a\u0430 \u043d\u0430\u0441\u044b\u0449\u0435\u043d\u0438\u044f (Saturation) \u043c\u044f\u0433\u043a\u043e",
                "\u043e\u0433\u0440\u0430\u043d\u0438\u0447\u0438\u0432\u0430\u0435\u0442 \u0432\u0435\u0440\u0448\u0438\u043d\u0443 \u043d\u0430 \u0443\u0440\u043e\u0432\u043d\u0435 \u00b11 \u043f\u0440\u0438 \u0432\u044b\u0433\u0440\u0443\u0437\u043a\u0435 \u0432 \u041e\u0417\u0423",
                "#4ADE80",
            ),
        ],
    )
    return _fig_to_rgb(fig)


def _build_m2_s3_base() -> Image.Image:
    d = chr(36)
    fig, ax = _new_base_fig(
        "\u041c\u043e\u0434\u0443\u043b\u044c 2 \u2022 \u0421\u0446\u0435\u043d\u0430 3 (#16): \u041c\u0430\u0441\u0448\u0442\u0430\u0431\u0438\u0440\u043e\u0432\u0430\u043d\u0438\u0435 \u043a\u043e\u044d\u0444\u0444\u0438\u0446\u0438\u0435\u043d\u0442\u043e\u0432 " + d + "a_1 / 2" + d + " \u0432 Q15 \u0438 \u0441\u0434\u0432\u0438\u0433 ASL A"
    )
    gx0, gw, yc_top, yc_bot, amp_y = 0.92, 6.35, 5.05, 2.45, 0.88
    _draw_dual_vertical_axes(
        ax,
        gx0,
        gw,
        yc_top,
        yc_bot,
        amp_y,
        "\u041d\u0430\u043a\u043e\u043f\u043b\u0435\u043d\u0438\u0435 \u0441 \u043f\u043e\u043b\u043e\u0432\u0438\u043d\u043d\u044b\u043c\u0438 \u043a\u043e\u044d\u0444\u0444\u0438\u0446\u0438\u0435\u043d\u0442\u0430\u043c\u0438 " + d + r"w_{\mathrm{half}}[n] = \frac{1}{2} w[n]" + d,
        "#38BDF8",
        "\u0412\u043e\u0441\u0441\u0442\u0430\u043d\u043e\u0432\u043b\u0435\u043d\u0438\u0435 \u043c\u0430\u0441\u0448\u0442\u0430\u0431\u0430 \u0430\u0440\u0438\u0444\u043c\u0435\u0442\u0438\u0447\u0435\u0441\u043a\u0438\u043c \u0441\u0434\u0432\u0438\u0433\u043e\u043c ASL A (" + d + r"\times 2" + d + ")",
        "#4ADE80",
        d + "nT_s" + d,
        d + "nT_s" + d,
        n_grid=16,
    )
    _draw_right_info_panel(
        ax,
        d + r"|a_{1,k}| \in (1;\, 2) \quad \Longrightarrow \quad \tilde{a}_{1,k} = \frac{a_{1,k}}{2} \in (-1;\, +1)" + d,
        "#38BDF8",
        d + r"\mathrm{MAC}\;\; X0,Y0,A \quad \Longrightarrow \quad \mathrm{ASL}\;\; A \;\; (\times 2)" + d,
        "#FBBF24",
        [
            (
                "\u0424\u043e\u0440\u043c\u0430\u0442 Q15 (1.15) \u0445\u0440\u0430\u043d\u0438\u0442 \u0442\u043e\u043b\u044c\u043a\u043e \u0434\u0440\u043e\u0431\u043d\u044b\u0435 \u0447\u0438\u0441\u043b\u0430 [-1; +1),",
                "\u0430 \u043a\u043e\u044d\u0444\u0444\u0438\u0446\u0438\u0435\u043d\u0442 \u0440\u0435\u0437\u043e\u043d\u0430\u043d\u0441\u043d\u043e\u0439 \u0441\u0435\u043a\u0446\u0438\u0438 a1 \u0434\u043e\u0441\u0442\u0438\u0433\u0430\u0435\u0442 1,97",
                "#38BDF8",
            ),
            (
                "\u0412\u0435\u0440\u0445\u043d\u0438\u0439 \u0433\u0440\u0430\u0444\u0438\u043a: \u0432 \u041f\u0417\u0423 \u0437\u0430\u043f\u0438\u0441\u044b\u0432\u0430\u044e\u0442 \u043f\u043e\u043b\u043e\u0432\u0438\u043d\u043d\u044b\u0435 \u043a\u043e\u044d\u0444\u0444\u0438\u0446\u0438\u0435\u043d\u0442\u044b,",
                "\u043f\u043e\u044d\u0442\u043e\u043c\u0443 \u0441\u0443\u043c\u043c\u0430 MAC \u0432 \u0430\u043a\u043a\u0443\u043c\u0443\u043b\u044f\u0442\u043e\u0440\u0435 \u0432\u0434\u0432\u043e\u0435 \u043c\u0435\u043d\u044c\u0448\u0435 \u0438\u0441\u0442\u0438\u043d\u043d\u043e\u0439",
                "#FBBF24",
            ),
            (
                "\u041d\u0438\u0436\u043d\u0438\u0439 \u0433\u0440\u0430\u0444\u0438\u043a: \u0438\u043d\u0441\u0442\u0440\u0443\u043a\u0446\u0438\u044f ASL A \u0437\u0430 1 \u0442\u0430\u043a\u0442 \u0441\u0434\u0432\u0438\u0433\u0430\u0435\u0442",
                "\u0430\u043a\u043a\u0443\u043c\u0443\u043b\u044f\u0442\u043e\u0440 \u0432\u043b\u0435\u0432\u043e \u0438 \u0442\u043e\u0447\u043d\u043e \u0432\u043e\u0441\u0441\u0442\u0430\u043d\u0430\u0432\u043b\u0438\u0432\u0430\u0435\u0442 \u0430\u043c\u043f\u043b\u0438\u0442\u0443\u0434\u0443",
                "#4ADE80",
            ),
        ],
    )
    return _fig_to_rgb(fig)
