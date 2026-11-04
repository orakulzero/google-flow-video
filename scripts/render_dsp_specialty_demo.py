"""
Render the 3-scene DSP specialty educational video in the @WildMathing / Manim
1:1 vertical-projection visual canon:
Topic: Sampling Theorem (Kotelnikov-Nyquist), Aliasing Physics, and Sallen-Key
Anti-Aliasing Filter (AAF) from the DSP coursework theoretical foundation.

- Scene 1 (Sampling & Kotelnikov Theorem, f < f_s / 2):
  Top graph: Continuous analog signal u(t) with moving sampling strobe at period T_s.
  Bottom graph (strictly aligned horizontally, 1:1 vertical projection): Discrete
  samples x[n] = u(n * T_s) dropped straight down from the analog curve, accurately
  reconstructing the signal when f < f_s / 2.

- Scene 2 (Physics of Frequency Folding / Aliasing, f > f_s / 2):
  Top graph: High-frequency interference wave (f_high > f_s / 2) sampled at period T_s.
  Bottom graph (strictly aligned horizontally, 1:1 vertical projection): The exact
  same sample points dropped vertically down form a false low-frequency alias wave
  f_alias = |f_s - f_high| inside the useful passband!

- Scene 3 (Sallen-Key Anti-Aliasing Low-Pass Filter before ADC):
  Left-top graph: Input mixture u_in(t) = useful low-frequency signal + high-frequency noise.
  Left-bottom graph (1:1 vertical alignment): Output u_out(t) after the 2nd-order
  Sallen-Key filter where the high-frequency noise is suppressed prior to sampling.
  Right graph: Magnitude response |H(f)| showing the passband, cutoff f_0, Nyquist
  boundary f_s / 2, and stopband attenuation of the interference component.
"""

from __future__ import annotations

import asyncio
import io
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Dict, List, Tuple

import imageio_ffmpeg
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
if str(ROOT_DIR / "src") not in sys.path:
    sys.path.insert(0, str(ROOT_DIR / "src"))

from scripts.render_simple_flow_demo import (  # noqa: E402
    COL_CYAN,
    COL_GOLD,
    COL_GREEN,
    COL_RED,
    COL_WHITE,
    _align_captions_to_wav,
    _draw_arrow_2x,
    _draw_dashed_line_2x,
    _draw_wildmathing_subtitles,
)
from src.flow_bridge import (  # noqa: E402
    FlowClient,
    FlowEducationalCompositor,
    FlowScene,
    build_srt_subtitles,
    build_webvtt_subtitles,
)


def _build_dsp_scene1_base() -> Image.Image:
    """
    Scene 1 Base Canvas (1280x720):
    - Left/Center (x in [0.9, 7.6]):
      * Upper plot (y_c1 = 5.05): Continuous analog signal u(t) = A sin(2*pi*f_0*t)
      * Lower plot (y_c2 = 2.45): Discrete sequence x[n] = u(n*T_s) directly below u(t)
        sharing the exact same horizontal time coordinates!
    - Right panel (x in [8.1, 12.3]):
      * Kotelnikov-Nyquist sampling theorem equations & physical explanation.
    """
    plt.rcParams["mathtext.fontset"] = "cm"
    d = chr(36)
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
        0.55,
        6.86,
        "01. \u0414\u0438\u0441\u043a\u0440\u0435\u0442\u0438\u0437\u0430\u0446\u0438\u044f \u0441\u0438\u0433\u043d\u0430\u043b\u0430 \u0438 \u0443\u0441\u043b\u043e\u0432\u0438\u0435 \u041a\u043e\u0442\u0435\u043b\u044c\u043d\u0438\u043a\u043e\u0432\u0430 ("
        + d
        + r"f < f_s / 2"
        + d
        + ")",
        color="#E2E8F0",
        fontsize=13.5,
        weight="bold",
        va="center",
    )

    gx0, gw = 0.95, 6.35
    yc_top = 5.05
    yc_bot = 2.45
    amp_y = 0.92

    # Upper axes: Continuous signal u(t)
    ax.annotate("", xy=(gx0 + gw + 0.30, yc_top), xytext=(gx0, yc_top), arrowprops=dict(arrowstyle="->", color="#64748B", lw=1.7))
    ax.annotate("", xy=(gx0, yc_top + amp_y + 0.30), xytext=(gx0, yc_top - amp_y - 0.25), arrowprops=dict(arrowstyle="->", color="#64748B", lw=1.7))
    ax.text(gx0 + 0.14, yc_top + amp_y + 0.18, "\u0410\u043d\u0430\u043b\u043e\u0433\u043e\u0432\u044b\u0439 \u0441\u0438\u0433\u043d\u0430\u043b " + d + "u(t)" + d, color="#38BDF8", fontsize=12.5, weight="bold")
    ax.text(gx0 + gw + 0.35, yc_top - 0.05, d + "t" + d, color="#94A3B8", fontsize=14)

    # Lower axes: Discrete sequence x[n] = u(n * T_s) directly below u(t)
    ax.annotate("", xy=(gx0 + gw + 0.30, yc_bot), xytext=(gx0, yc_bot), arrowprops=dict(arrowstyle="->", color="#64748B", lw=1.7))
    ax.annotate("", xy=(gx0, yc_bot + amp_y + 0.28), xytext=(gx0, yc_bot - amp_y - 0.22), arrowprops=dict(arrowstyle="->", color="#64748B", lw=1.7))
    ax.text(
        gx0 + 0.14,
        yc_bot - amp_y - 0.32,
        "\u0414\u0438\u0441\u043a\u0440\u0435\u0442\u043d\u044b\u0435 \u043e\u0442\u0441\u0447\u0451\u0442\u044b " + d + r"x[n] = u(nT_s)" + d,
        color="#4ADE80",
        fontsize=12.5,
        weight="bold",
    )
    ax.text(gx0 + gw + 0.35, yc_bot - 0.05, d + "nT_s" + d, color="#94A3B8", fontsize=13.5)

    # Faint continuous guide curves on both upper and lower plots (2 full periods, 16 samples -> 8 samples/period)
    u_arr = np.linspace(0.0, 1.0, 400)
    y_wave = amp_y * np.sin(2.0 * np.pi * 2.0 * u_arr)
    ax.plot(gx0 + u_arr * gw, yc_top + y_wave, color="#38BDF8", lw=1.2, alpha=0.28)
    ax.plot(gx0 + u_arr * gw, yc_bot + y_wave, color="#4ADE80", lw=1.2, ls="--", alpha=0.25)

    # Vertical grid guide lines for sample instants n = 0..16
    n_samples = 16
    for k in range(n_samples + 1):
        uk = k / float(n_samples)
        xk = gx0 + uk * gw
        ax.plot([xk, xk], [yc_bot - amp_y, yc_top + amp_y], color="#1E293B", lw=0.8, ls=":", zorder=1)

    # Right half: LaTeX equations & physical explanation
    rx_card = 10.25
    eq1 = d + r"x[n] = u(n T_s), \qquad T_s = \frac{1}{f_s}" + d
    ax.text(
        rx_card,
        5.90,
        eq1,
        color="#F8FAFC",
        fontsize=16.0,
        ha="center",
        va="center",
        bbox=dict(boxstyle="round,pad=0.38", facecolor="#131C31", edgecolor="#38BDF8", lw=1.4),
    )

    eq2_clean = d + r"f_{\max} < \frac{f_s}{2}, \qquad N_{\mathrm{T}} = \frac{f_s}{f_0} \geq 2" + d
    ax.text(
        rx_card,
        4.85,
        eq2_clean,
        color="#F8FAFC",
        fontsize=15.0,
        ha="center",
        va="center",
        bbox=dict(boxstyle="round,pad=0.36", facecolor="#131C31", edgecolor="#4ADE80", lw=1.3),
    )

    ax.text(8.05, 4.02, "\u2022 \u0428\u0430\u0433 \u0434\u0438\u0441\u043a\u0440\u0435\u0442\u0438\u0437\u0430\u0446\u0438\u0438 " + d + "T_s" + d + " \u2014 \u0438\u043d\u0442\u0435\u0440\u0432\u0430\u043b \u043c\u0435\u0436\u0434\u0443", color="#E2E8F0", fontsize=11.8)
    ax.text(8.25, 3.68, "\u0441\u043e\u0441\u0435\u0434\u043d\u0438\u043c\u0438 \u0437\u0430\u043c\u0435\u0440\u0430\u043c\u0438 \u043d\u0430\u043f\u0440\u044f\u0436\u0435\u043d\u0438\u044f \u0410\u0426\u041f", color="#94A3B8", fontsize=11.5)

    ax.text(8.05, 3.15, "\u2022 \u0417\u043e\u043b\u043e\u0442\u044b\u0435 \u043b\u0438\u043d\u0438\u0438 \u043f\u043e\u043a\u0430\u0437\u044b\u0432\u0430\u044e\u0442 \u043f\u0435\u0440\u0435\u043d\u043e\u0441 \u043a\u0430\u0436\u0434\u043e\u0439", color="#FBBF24", fontsize=11.8)
    ax.text(8.25, 2.81, "\u0432\u044b\u0431\u043e\u0440\u043a\u0438 \u0441 \u0430\u043d\u0430\u043b\u043e\u0433\u043e\u0432\u043e\u0439 \u0432\u043e\u043b\u043d\u044b \u0432 \u0446\u0438\u0444\u0440\u043e\u0432\u043e\u0439 \u043e\u0442\u0441\u0447\u0451\u0442", color="#FBBF24", fontsize=11.5)

    ax.text(8.05, 2.25, "\u2022 \u041f\u0440\u0438 " + d + r"f_s / f_0 = 8 > 2" + d + " \u043e\u0433\u0438\u0431\u0430\u044e\u0449\u0430\u044f \u043e\u0442\u0441\u0447\u0451\u0442\u043e\u0432", color="#4ADE80", fontsize=11.8)
    ax.text(8.25, 1.91, "\u0442\u043e\u0447\u043d\u043e \u0432\u043e\u0441\u0441\u0442\u0430\u043d\u0430\u0432\u043b\u0438\u0432\u0430\u0435\u0442 \u0438\u0441\u0445\u043e\u0434\u043d\u0443\u044e \u0444\u043e\u0440\u043c\u0443 \u0432\u043e\u043b\u043d\u044b", color="#4ADE80", fontsize=11.5)

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=100)
    plt.close(fig)
    buf.seek(0)
    return Image.open(buf).convert("RGB")


def _build_dsp_scene2_base() -> Image.Image:
    """
    Scene 2 Base Canvas (1280x720):
    Physics of Aliasing (f_high > f_s / 2):
    - Upper plot (y_c1 = 5.05): Fast interference signal u_high(t) with 7 cycles across the window,
      sampled at only N_s = 8 intervals (so f_high = 7/8 f_s > f_s/2!).
    - Lower plot (y_c2 = 2.45): Directly below, the exact same sample points x[n] fall on a slow
      1-cycle alias sine wave u_alias(t) of frequency f_alias = |f_s - f_high| = 1/8 f_s!
    """
    plt.rcParams["mathtext.fontset"] = "cm"
    d = chr(36)
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
        0.55,
        6.86,
        "02. \u042d\u0444\u0444\u0435\u043a\u0442 \u043d\u0430\u043b\u043e\u0436\u0435\u043d\u0438\u044f \u0447\u0430\u0441\u0442\u043e\u0442 (\u0430\u043b\u0438\u0430\u0441\u0438\u043d\u0433) \u043f\u0440\u0438 "
        + d
        + r"f_{\mathrm{BX}} > f_s / 2"
        + d,
        color="#E2E8F0",
        fontsize=13.5,
        weight="bold",
        va="center",
    )

    gx0, gw = 0.95, 6.35
    yc_top = 5.05
    yc_bot = 2.45
    amp_y = 0.92

    # Upper axes: Fast input interference u_high(t)
    ax.annotate("", xy=(gx0 + gw + 0.30, yc_top), xytext=(gx0, yc_top), arrowprops=dict(arrowstyle="->", color="#64748B", lw=1.7))
    ax.annotate("", xy=(gx0, yc_top + amp_y + 0.30), xytext=(gx0, yc_top - amp_y - 0.25), arrowprops=dict(arrowstyle="->", color="#64748B", lw=1.7))
    ax.text(
        gx0 + 0.14,
        yc_top + amp_y + 0.18,
        "\u0412\u044b\u0441\u043e\u043a\u043e\u0447\u0430\u0441\u0442\u043e\u0442\u043d\u0430\u044f \u043f\u043e\u043c\u0435\u0445\u0430 (" + d + r"f_{\mathrm{BX}} > f_s/2" + d + ")",
        color="#38BDF8",
        fontsize=12.2,
        weight="bold",
    )
    ax.text(gx0 + gw + 0.35, yc_top - 0.05, d + "t" + d, color="#94A3B8", fontsize=14)

    # Lower axes: False low-frequency alias wave reconstructed from the same samples
    ax.annotate("", xy=(gx0 + gw + 0.30, yc_bot), xytext=(gx0, yc_bot), arrowprops=dict(arrowstyle="->", color="#64748B", lw=1.7))
    ax.annotate("", xy=(gx0, yc_bot + amp_y + 0.28), xytext=(gx0, yc_bot - amp_y - 0.22), arrowprops=dict(arrowstyle="->", color="#64748B", lw=1.7))
    ax.text(
        gx0 + 0.14,
        yc_bot - amp_y - 0.32,
        "\u041b\u043e\u0436\u043d\u0430\u044f \u043d\u0438\u0437\u043a\u0430\u044f \u0447\u0430\u0441\u0442\u043e\u0442\u0430 \u2014 \u0430\u043b\u0438\u0430\u0441 (" + d + r"f_{\mathrm{a}} = |f_s - f_{\mathrm{BX}}|" + d + ")",
        color="#F87171",
        fontsize=12.2,
        weight="bold",
    )
    ax.text(gx0 + gw + 0.35, yc_bot - 0.05, d + "nT_s" + d, color="#94A3B8", fontsize=13.5)

    # Note the mathematical identity: sin(2*pi * 7 * (k/8)) == -sin(2*pi * 1 * (k/8))!
    u_arr = np.linspace(0.0, 1.0, 600)
    y_fast = amp_y * np.sin(2.0 * np.pi * 7.0 * u_arr)
    y_alias = -amp_y * np.sin(2.0 * np.pi * 1.0 * u_arr)
    ax.plot(gx0 + u_arr * gw, yc_top + y_fast, color="#38BDF8", lw=1.1, alpha=0.30)
    ax.plot(gx0 + u_arr * gw, yc_bot + y_alias, color="#F87171", lw=1.3, ls="--", alpha=0.32)

    n_samples = 8
    for k in range(n_samples + 1):
        uk = k / float(n_samples)
        xk = gx0 + uk * gw
        ax.plot([xk, xk], [yc_bot - amp_y, yc_top + amp_y], color="#1E293B", lw=0.9, ls=":", zorder=1)

    # Right half: Aliasing formula & physical explanation
    rx_card = 10.25
    eq1 = d + r"f_{\mathrm{BX}} > \frac{f_s}{2} \quad \Longrightarrow \quad f_{\mathrm{a}} = |f_s - f_{\mathrm{BX}}|" + d
    ax.text(
        rx_card,
        5.90,
        eq1,
        color="#F8FAFC",
        fontsize=15.0,
        ha="center",
        va="center",
        bbox=dict(boxstyle="round,pad=0.38", facecolor="#131C31", edgecolor="#F87171", lw=1.4),
    )

    eq2 = d + r"\sin(2\pi f_{\mathrm{BX}} n T_s) = -\sin(2\pi f_{\mathrm{a}} n T_s)" + d
    ax.text(
        rx_card,
        4.85,
        eq2,
        color="#F8FAFC",
        fontsize=14.8,
        ha="center",
        va="center",
        bbox=dict(boxstyle="round,pad=0.36", facecolor="#131C31", edgecolor="#FBBF24", lw=1.3),
    )

    ax.text(8.05, 4.02, "\u2022 \u0412\u0435\u0440\u0445\u043d\u0438\u0439 \u0433\u0440\u0430\u0444\u0438\u043a: \u0431\u044b\u0441\u0442\u0440\u0430\u044f \u043f\u043e\u043c\u0435\u0445\u0430 \u0441\u043e\u0432\u0435\u0440\u0448\u0430\u0435\u0442", color="#38BDF8", fontsize=11.8)
    ax.text(8.25, 3.68, "7 \u043f\u043e\u043b\u043d\u044b\u0445 \u043f\u0435\u0440\u0438\u043e\u0434\u043e\u0432 \u043d\u0430 8 \u0438\u043d\u0442\u0435\u0440\u0432\u0430\u043b\u043e\u0432 \u043e\u0442\u0441\u0447\u0451\u0442\u043e\u0432", color="#94A3B8", fontsize=11.5)

    ax.text(8.05, 3.15, "\u2022 \u0412\u044b\u0431\u043e\u0440\u043a\u0438 \u0431\u0435\u0440\u0443\u0442\u0441\u044f \u0441\u043b\u0438\u0448\u043a\u043e\u043c \u0440\u0435\u0434\u043a\u043e \u0438 \u043f\u043e\u043f\u0430\u0434\u0430\u044e\u0442", color="#FBBF24", fontsize=11.8)
    ax.text(8.25, 2.81, "\u043d\u0430 \u0440\u0430\u0437\u043d\u044b\u0435 \u0432\u0438\u0442\u043a\u0438 \u0432\u044b\u0441\u043e\u043a\u043e\u0447\u0430\u0441\u0442\u043e\u0442\u043d\u043e\u0439 \u0432\u043e\u043b\u043d\u044b", color="#FBBF24", fontsize=11.5)

    ax.text(8.05, 2.25, "\u2022 \u041d\u0438\u0436\u043d\u0438\u0439 \u0433\u0440\u0430\u0444\u0438\u043a: \u0447\u0435\u0440\u0435\u0437 \u0442\u0435 \u0436\u0435 \u0442\u043e\u0447\u043a\u0438 \u043f\u0440\u043e\u0445\u043e\u0434\u0438\u0442", color="#F87171", fontsize=11.8)
    ax.text(8.25, 1.91, "\u043b\u043e\u0436\u043d\u0430\u044f \u043c\u0435\u0434\u043b\u0435\u043d\u043d\u0430\u044f \u0441\u0438\u043d\u0443\u0441\u043e\u0438\u0434\u0430 \u0432 \u0440\u0430\u0431\u043e\u0447\u0435\u0439 \u043f\u043e\u043b\u043e\u0441\u0435", color="#F87171", fontsize=11.5)

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=100)
    plt.close(fig)
    buf.seek(0)
    return Image.open(buf).convert("RGB")


def _build_dsp_scene3_base() -> Image.Image:
    """
    Scene 3 Base Canvas (1280x720):
    Anti-Aliasing Sallen-Key Low-Pass Filter before the ADC:
    - Left-Top plot (y_c1 = 5.05): Input mixture u_in(t) = useful signal + high-frequency interference.
    - Left-Bottom plot (y_c2 = 2.45): Filtered signal u_out(t) directly below u_in(t) where the
      high-frequency interference is suppressed and clean samples x[n] are taken!
    - Right plot: Magnitude frequency response |H(f)| of the Sallen-Key filter showing passband
      (useful signal passed) and stopband above f_s / 2 (interference suppressed).
    """
    plt.rcParams["mathtext.fontset"] = "cm"
    d = chr(36)
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
        0.55,
        6.86,
        "03. \u0417\u0430\u0449\u0438\u0442\u0430 \u043e\u0442 \u043d\u0430\u043b\u043e\u0436\u0435\u043d\u0438\u044f: \u0430\u043d\u0430\u043b\u043e\u0433\u043e\u0432\u044b\u0439 \u0424\u041d\u0427 \u0421\u0430\u043b\u043b\u0435\u043d\u0430\u2014\u041a\u0435\u044f \u043f\u0435\u0440\u0435\u0434 \u0410\u0426\u041f",
        color="#E2E8F0",
        fontsize=13.5,
        weight="bold",
        va="center",
    )

    gx0, gw = 0.85, 5.45
    yc_top = 5.05
    yc_bot = 2.45
    amp_y = 0.88

    # Left-top axes: Input signal + high-frequency noise
    ax.annotate("", xy=(gx0 + gw + 0.28, yc_top), xytext=(gx0, yc_top), arrowprops=dict(arrowstyle="->", color="#64748B", lw=1.7))
    ax.annotate("", xy=(gx0, yc_top + amp_y + 0.30), xytext=(gx0, yc_top - amp_y - 0.25), arrowprops=dict(arrowstyle="->", color="#64748B", lw=1.7))
    ax.text(
        gx0 + 0.12,
        yc_top + amp_y + 0.18,
        "\u0414\u043e \u0444\u0438\u043b\u044c\u0442\u0440\u0430: \u0441\u0438\u0433\u043d\u0430\u043b + \u0412\u0427-\u043f\u043e\u043c\u0435\u0445\u0430 " + d + r"u_{\mathrm{BX}}(t)" + d,
        color="#F87171",
        fontsize=11.8,
        weight="bold",
    )
    ax.text(gx0 + gw + 0.33, yc_top - 0.05, d + "t" + d, color="#94A3B8", fontsize=13.5)

    # Left-bottom axes: Clean filtered output u_out(t) directly below u_in(t)
    ax.annotate("", xy=(gx0 + gw + 0.28, yc_bot), xytext=(gx0, yc_bot), arrowprops=dict(arrowstyle="->", color="#64748B", lw=1.7))
    ax.annotate("", xy=(gx0, yc_bot + amp_y + 0.28), xytext=(gx0, yc_bot - amp_y - 0.22), arrowprops=dict(arrowstyle="->", color="#64748B", lw=1.7))
    ax.text(
        gx0 + 0.12,
        yc_bot - amp_y - 0.32,
        "\u041f\u043e\u0441\u043b\u0435 \u0424\u041d\u0427 \u0421\u0430\u043b\u043b\u0435\u043d\u0430\u2014\u041a\u0435\u044f: \u0447\u0438\u0441\u0442\u044b\u0435 \u043e\u0442\u0441\u0447\u0451\u0442\u044b " + d + "x[n]" + d,
        color="#4ADE80",
        fontsize=11.8,
        weight="bold",
    )
    ax.text(gx0 + gw + 0.33, yc_bot - 0.05, d + "nT_s" + d, color="#94A3B8", fontsize=13.0)

    u_arr = np.linspace(0.0, 1.0, 500)
    y_clean = 0.62 * np.sin(2.0 * np.pi * 2.0 * u_arr)
    y_noisy = y_clean + 0.32 * np.sin(2.0 * np.pi * 15.0 * u_arr)
    ax.plot(gx0 + u_arr * gw, yc_top + y_noisy, color="#F87171", lw=1.1, alpha=0.28)
    ax.plot(gx0 + u_arr * gw, yc_bot + y_clean, color="#4ADE80", lw=1.2, alpha=0.28)

    n_samples = 14
    for k in range(n_samples + 1):
        uk = k / float(n_samples)
        xk = gx0 + uk * gw
        ax.plot([xk, xk], [yc_bot - amp_y, yc_top + amp_y], color="#1E293B", lw=0.8, ls=":", zorder=1)

    # Right half: Sallen-Key transfer function & frequency response |H(f)|
    eq_sk = d + r"|H(f)| = \frac{1}{\sqrt{\left(1 - (f/f_0)^2\right)^2 + \left(f/(Q f_0)\right)^2}}" + d
    ax.text(
        9.65,
        5.92,
        eq_sk,
        color="#F8FAFC",
        fontsize=14.5,
        ha="center",
        va="center",
        bbox=dict(boxstyle="round,pad=0.36", facecolor="#131C31", edgecolor="#FBBF24", lw=1.4),
    )

    rx0, rw, ry0, rh = 7.10, 4.80, 1.75, 2.95
    ax.annotate("", xy=(rx0 + rw + 0.30, ry0), xytext=(rx0, ry0), arrowprops=dict(arrowstyle="->", color="#64748B", lw=1.7))
    ax.annotate("", xy=(rx0, ry0 + rh + 0.34), xytext=(rx0, ry0), arrowprops=dict(arrowstyle="->", color="#64748B", lw=1.7))
    ax.text(rx0 + rw + 0.35, ry0 - 0.05, d + "f" + d, color="#94A3B8", fontsize=14.5)
    ax.text(rx0 + 0.14, ry0 + rh + 0.25, "\u0410\u0427\u0425 \u0444\u0438\u043b\u044c\u0442\u0440\u0430 " + d + "|H(f)|" + d, color="#38BDF8", fontsize=12.5, weight="bold")

    # Sallen-Key 2nd-order LPF response with Q = 0.707, cutoff at u_f = 1.0
    f_norm = np.linspace(0.0, 2.4, 400)
    q_sk = 0.736
    h_mag = 1.0 / np.sqrt((1.0 - f_norm**2) ** 2 + (f_norm / q_sk) ** 2)
    h_mag = np.clip(h_mag, 0.0, 1.05)
    ax.plot(rx0 + (f_norm / 2.4) * rw, ry0 + h_mag * (rh * 0.85), color="#38BDF8", lw=2.4, alpha=0.90)

    # Nyquist boundary line at f_norm = 1.05
    nyq_x = rx0 + (1.05 / 2.4) * rw
    ax.plot([nyq_x, nyq_x], [ry0, ry0 + rh], color="#FBBF24", lw=1.6, ls="--")
    ax.text(nyq_x, ry0 - 0.28, d + r"f_s / 2" + d + " (\u0413\u0440\u0430\u043d\u0438\u0446\u0430 \u041a\u043e\u0442\u0435\u043b\u044c\u043d\u0438\u043a\u043e\u0432\u0430)", color="#FBBF24", fontsize=11.5, ha="center", weight="bold")

    # Useful signal spectral bar in passband (f_norm = 0.42)
    f_sig_x = rx0 + (0.42 / 2.4) * rw
    ax.text(f_sig_x, ry0 + rh * 0.88, "\u041f\u043e\u043b\u0435\u0437\u043d\u044b\u0439\n\u0441\u0438\u0433\u043d\u0430\u043b", color="#4ADE80", fontsize=11.0, ha="center", weight="bold")

    # High-frequency interference in stopband (f_norm = 1.85)
    f_noise_x = rx0 + (1.85 / 2.4) * rw
    ax.text(f_noise_x, ry0 + rh * 0.58, "\u0412\u0427-\u043f\u043e\u043c\u0435\u0445\u0430\n(\u043f\u043e\u0434\u0430\u0432\u043b\u0435\u043d\u0430)", color="#F87171", fontsize=11.0, ha="center", weight="bold")

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=100)
    plt.close(fig)
    buf.seek(0)
    return Image.open(buf).convert("RGB")


class WildMathingDSPSpecialtyRenderer:
    """
    2x-supersampled @WildMathing renderer for the DSP specialty video on
    Sampling, Aliasing, and Sallen-Key Anti-Aliasing Filtering.
    """

    def __init__(self) -> None:
        self.s1_base = _build_dsp_scene1_base()
        self.s2_base = _build_dsp_scene2_base()
        self.s3_base = _build_dsp_scene3_base()
        try:
            self.f_sub = ImageFont.truetype("C:/Windows/Fonts/segoeuib.ttf", 19)
        except Exception:
            self.f_sub = ImageFont.load_default()

    def _mx(self, x_math: float) -> float:
        return x_math * 200.0

    def _my(self, y_math: float) -> float:
        return (7.2 - y_math) * 200.0

    def render_frame(self, scene: FlowScene, frame_idx: int, total_frames: int) -> bytes:
        p = max(0.0, min(1.0, frame_idx / float(max(1, total_frames - 1))))
        sc_num = scene.scene_number

        if sc_num == 1:
            base = self.s1_base.copy()
        elif sc_num == 2:
            base = self.s2_base.copy()
        else:
            base = self.s3_base.copy()

        ov2x = Image.new("RGBA", (2560, 1440), (0, 0, 0, 0))
        d2x = ImageDraw.Draw(ov2x)

        if sc_num == 1:
            # =========================================================================
            # SCENE 1: Continuous signal u(t) ABOVE + Discrete stems x[n] BELOW
            # 1:1 vertical projection at every sample instant k * T_s <= p!
            # =========================================================================
            gx0, gw = 0.95, 6.35
            yc_top = 5.05
            yc_bot = 2.45
            amp_y = 0.92

            n_pts = max(2, int(p * 320))
            top_pts: List[Tuple[float, float]] = []
            bot_pts: List[Tuple[float, float]] = []
            for i in range(n_pts + 1):
                u = min(p, i / 320.0)
                val = amp_y * math.sin(2.0 * math.pi * 2.0 * u)
                px_u = self._mx(gx0 + u * gw)
                top_pts.append((px_u, self._my(yc_top + val)))
                bot_pts.append((px_u, self._my(yc_bot + val)))
            if len(top_pts) > 1:
                d2x.line(top_pts, fill=(*COL_CYAN, 255), width=7)
                d2x.line(bot_pts, fill=(*COL_GREEN, 165), width=4)

            # Draw all discrete samples k = 0..16 that have been reached by time p
            n_samples = 16
            for k in range(n_samples + 1):
                uk = k / float(n_samples)
                if uk > p + 1e-4:
                    break
                val_k = amp_y * math.sin(2.0 * math.pi * 2.0 * uk)
                sx = self._mx(gx0 + uk * gw)
                sy_top = self._my(yc_top + val_k)
                sy_bot_axis = self._my(yc_bot)
                sy_bot_val = self._my(yc_bot + val_k)

                # Vertical projection dashed line from upper curve point (sx, sy_top) to lower sample point (sx, sy_bot_val)
                if k > 0:
                    _draw_dashed_line_2x(d2x, sx, sy_top, sx, sy_bot_val, (*COL_GOLD, 165), width=3, dash_len=12, gap_len=10)
                # Discrete stem on lower plot from axis (sx, sy_bot_axis) to (sx, sy_bot_val)
                d2x.line([(sx, sy_bot_axis), (sx, sy_bot_val)], fill=(*COL_GREEN, 255), width=6)
                d2x.ellipse([sx - 11, sy_top - 11, sx + 11, sy_top + 11], fill=(*COL_CYAN, 255), outline=(248, 250, 252, 255), width=3)
                d2x.ellipse([sx - 12, sy_bot_val - 12, sx + 12, sy_bot_val + 12], fill=(*COL_GREEN, 255), outline=(248, 250, 252, 255), width=3)

            # Active sweeping sampling cursor at current p
            cur_x, cur_y_top = top_pts[-1]
            _, cur_y_bot = bot_pts[-1]
            _draw_dashed_line_2x(d2x, cur_x, cur_y_top, cur_x, cur_y_bot, (*COL_GOLD, 255), width=5, dash_len=14, gap_len=10)
            d2x.ellipse([cur_x - 16, cur_y_top - 16, cur_x + 16, cur_y_top + 16], fill=(*COL_GOLD, 255))
            d2x.ellipse([cur_x - 16, cur_y_bot - 16, cur_x + 16, cur_y_bot + 16], fill=(*COL_GOLD, 255))

        elif sc_num == 2:
            # =========================================================================
            # SCENE 2: Fast interference (7 cycles) ABOVE + Slow Alias Wave (1 cycle) BELOW
            # Exact mathematical coincidence at every sample k = 0..8:
            # sin(2*pi * 7 * (k/8)) == -sin(2*pi * 1 * (k/8))!
            # =========================================================================
            gx0, gw = 0.95, 6.35
            yc_top = 5.05
            yc_bot = 2.45
            amp_y = 0.92

            n_pts = max(2, int(p * 450))
            fast_pts: List[Tuple[float, float]] = []
            alias_pts: List[Tuple[float, float]] = []
            for i in range(n_pts + 1):
                u = min(p, i / 450.0)
                v_fast = amp_y * math.sin(2.0 * math.pi * 7.0 * u)
                v_alias = -amp_y * math.sin(2.0 * math.pi * 1.0 * u)
                px_u = self._mx(gx0 + u * gw)
                fast_pts.append((px_u, self._my(yc_top + v_fast)))
                alias_pts.append((px_u, self._my(yc_bot + v_alias)))
            if len(fast_pts) > 1:
                d2x.line(fast_pts, fill=(*COL_CYAN, 255), width=6)
                d2x.line(alias_pts, fill=(*COL_RED, 255), width=7)

            n_samples = 8
            for k in range(n_samples + 1):
                uk = k / float(n_samples)
                if uk > p + 1e-4:
                    break
                # At uk = k/8, both waves have the EXACT same value!
                val_k = -amp_y * math.sin(2.0 * math.pi * 1.0 * uk)
                sx = self._mx(gx0 + uk * gw)
                sy_top = self._my(yc_top + val_k)
                sy_bot_axis = self._my(yc_bot)
                sy_bot_val = self._my(yc_bot + val_k)

                # Vertical golden projection line dropping straight from the fast wave's sample to the slow alias wave!
                if k > 0:
                    _draw_dashed_line_2x(d2x, sx, sy_top, sx, sy_bot_val, (*COL_GOLD, 230), width=4, dash_len=14, gap_len=10)
                d2x.line([(sx, sy_bot_axis), (sx, sy_bot_val)], fill=(*COL_RED, 255), width=6)
                d2x.ellipse([sx - 14, sy_top - 14, sx + 14, sy_top + 14], fill=(*COL_GOLD, 255), outline=(248, 250, 252, 255), width=3)
                d2x.ellipse([sx - 14, sy_bot_val - 14, sx + 14, sy_bot_val + 14], fill=(*COL_GOLD, 255), outline=(248, 250, 252, 255), width=3)

            cur_x, cur_y_top = fast_pts[-1]
            _, cur_y_bot = alias_pts[-1]
            _draw_dashed_line_2x(d2x, cur_x, cur_y_top, cur_x, cur_y_bot, (*COL_GOLD, 255), width=5, dash_len=14, gap_len=10)
            d2x.ellipse([cur_x - 15, cur_y_top - 15, cur_x + 15, cur_y_top + 15], fill=(*COL_CYAN, 255))
            d2x.ellipse([cur_x - 15, cur_y_bot - 15, cur_x + 15, cur_y_bot + 15], fill=(*COL_RED, 255))

        else:
            # =========================================================================
            # SCENE 3: Noisy Input ABOVE + Clean Sallen-Key Output BELOW + |H(f)| RIGHT
            # =========================================================================
            gx0, gw = 0.85, 5.45
            yc_top = 5.05
            yc_bot = 2.45

            n_pts = max(2, int(p * 400))
            noisy_pts: List[Tuple[float, float]] = []
            clean_pts: List[Tuple[float, float]] = []
            for i in range(n_pts + 1):
                u = min(p, i / 400.0)
                v_clean = 0.62 * math.sin(2.0 * math.pi * 2.0 * u)
                v_noisy = v_clean + 0.32 * math.sin(2.0 * math.pi * 15.0 * u)
                px_u = self._mx(gx0 + u * gw)
                noisy_pts.append((px_u, self._my(yc_top + v_noisy)))
                clean_pts.append((px_u, self._my(yc_bot + v_clean)))
            if len(noisy_pts) > 1:
                d2x.line(noisy_pts, fill=(*COL_RED, 255), width=5)
                d2x.line(clean_pts, fill=(*COL_GREEN, 255), width=7)

            n_samples = 14
            for k in range(n_samples + 1):
                uk = k / float(n_samples)
                if uk > p + 1e-4:
                    break
                v_clean_k = 0.62 * math.sin(2.0 * math.pi * 2.0 * uk)
                v_noisy_k = v_clean_k + 0.32 * math.sin(2.0 * math.pi * 15.0 * uk)
                sx = self._mx(gx0 + uk * gw)
                sy_top = self._my(yc_top + v_noisy_k)
                sy_bot_axis = self._my(yc_bot)
                sy_bot_val = self._my(yc_bot + v_clean_k)

                if k > 0:
                    _draw_dashed_line_2x(d2x, sx, sy_top, sx, sy_bot_val, (*COL_GOLD, 165), width=3, dash_len=12, gap_len=10)
                d2x.line([(sx, sy_bot_axis), (sx, sy_bot_val)], fill=(*COL_GREEN, 255), width=6)
                d2x.ellipse([sx - 11, sy_bot_val - 11, sx + 11, sy_bot_val + 11], fill=(*COL_GREEN, 255), outline=(248, 250, 252, 255), width=3)

            cur_x, cur_y_top = noisy_pts[-1]
            _, cur_y_bot = clean_pts[-1]
            _draw_dashed_line_2x(d2x, cur_x, cur_y_top, cur_x, cur_y_bot, (*COL_GOLD, 255), width=5, dash_len=14, gap_len=10)
            d2x.ellipse([cur_x - 15, cur_y_top - 15, cur_x + 15, cur_y_top + 15], fill=(*COL_RED, 255))
            d2x.ellipse([cur_x - 15, cur_y_bot - 15, cur_x + 15, cur_y_bot + 15], fill=(*COL_GREEN, 255))

            # Right half: Animated spectral arrows on |H(f)| showing passband transmission vs stopband attenuation
            rx0, rw, ry0, rh = 7.10, 4.80, 1.75, 2.95
            f_sig_x = self._mx(rx0 + (0.42 / 2.4) * rw)
            f_noise_x = self._mx(rx0 + (1.85 / 2.4) * rw)
            base_y = self._my(ry0)
            sig_top_y = self._my(ry0 + 0.83 * rh)
            noise_in_y = self._my(ry0 + 0.45 * rh)
            noise_out_y = self._my(ry0 + 0.08 * rh)

            # Green arrow: useful low-frequency signal passes with gain ~ 1.0
            _draw_arrow_2x(d2x, f_sig_x, base_y, f_sig_x, sig_top_y, (*COL_GREEN, 255), width=8, head_len=24)
            # Red dashed ghost of input interference vs crushed output after Sallen-Key LPF
            _draw_dashed_line_2x(d2x, f_noise_x, base_y, f_noise_x, noise_in_y, (*COL_RED, 180), width=5, dash_len=10, gap_len=8)
            _draw_arrow_2x(d2x, f_noise_x, noise_in_y, f_noise_x, noise_out_y, (*COL_GOLD, 255), width=7, head_len=22)

        ov1x = ov2x.resize((1280, 720), Image.Resampling.LANCZOS)
        base_rgba = base.convert("RGBA")
        base_rgba.alpha_composite(ov1x)
        final_rgb = base_rgba.convert("RGB")
        _draw_wildmathing_subtitles(final_rgb, scene, p, self.f_sub)
        return final_rgb.tobytes()


async def run_dsp_specialty_demo() -> dict:
    out_dir = ROOT_DIR / "output" / "dsp_specialty_demo"
    out_dir.mkdir(parents=True, exist_ok=True)

    topic_ru = (
        "\u0414\u0438\u0441\u043a\u0440\u0435\u0442\u0438\u0437\u0430\u0446\u0438\u044f \u0441\u0438\u0433\u043d\u0430\u043b\u043e\u0432, "
        "\u044d\u0444\u0444\u0435\u043a\u0442 \u043d\u0430\u043b\u043e\u0436\u0435\u043d\u0438\u044f \u0447\u0430\u0441\u0442\u043e\u0442 \u0438 \u0444\u0438\u043b\u044c\u0442\u0440 \u0421\u0430\u043b\u043b\u0435\u043d\u0430\u2014\u041a\u0435\u044f"
    )
    client = FlowClient()
    project = await client.generate_educational_storyboard(
        topic=topic_ru,
        scene_count=3,
        language="ru",
        target_audience="university",
        voice_persona="voice_y0joebp3bwta",
    )

    s1_text = (
        "\u041f\u0440\u0438 \u043e\u0446\u0438\u0444\u0440\u043e\u0432\u043a\u0435 \u043d\u0435\u043f\u0440\u0435\u0440\u044b\u0432\u043d\u043e\u0433\u043e \u0441\u0438\u0433\u043d\u0430\u043b\u0430 \u043f\u0440\u0435\u043e\u0431\u0440\u0430\u0437\u043e\u0432\u0430\u0442\u0435\u043b\u044c \u0431\u0435\u0440\u0451\u0442 \u043c\u0433\u043d\u043e\u0432\u0435\u043d\u043d\u044b\u0435 \u043e\u0442\u0441\u0447\u0451\u0442\u044b \u0447\u0435\u0440\u0435\u0437 \u0440\u0430\u0432\u043d\u044b\u0435 \u0438\u043d\u0442\u0435\u0440\u0432\u0430\u043b\u044b \u0432\u0440\u0435\u043c\u0435\u043d\u0438. "
        "\u041d\u0430 \u043d\u0438\u0436\u043d\u0435\u043c \u0433\u0440\u0430\u0444\u0438\u043a\u0435 \u0432\u0438\u0434\u043d\u043e, \u0447\u0442\u043e \u043f\u043e\u043a\u0430 \u0447\u0430\u0441\u0442\u043e\u0442\u0430 \u0432\u043e\u043b\u043d\u044b \u043d\u0438\u0436\u0435 \u043f\u043e\u043b\u043e\u0432\u0438\u043d\u044b \u0447\u0430\u0441\u0442\u043e\u0442\u044b \u0434\u0438\u0441\u043a\u0440\u0435\u0442\u0438\u0437\u0430\u0446\u0438\u0438, \u043f\u043e \u0442\u043e\u0447\u043a\u0430\u043c \u0442\u043e\u0447\u043d\u043e \u0432\u043e\u0441\u0441\u0442\u0430\u043d\u0430\u0432\u043b\u0438\u0432\u0430\u0435\u0442\u0441\u044f \u0438\u0441\u0445\u043e\u0434\u043d\u0430\u044f \u0444\u043e\u0440\u043c\u0430 \u0441\u0438\u0433\u043d\u0430\u043b\u0430."
    )
    s2_text = (
        "\u0415\u0441\u043b\u0438 \u0436\u0435 \u0447\u0430\u0441\u0442\u043e\u0442\u0430 \u0432\u0445\u043e\u0434\u043d\u043e\u0439 \u043f\u043e\u043c\u0435\u0445\u0438 \u043f\u0440\u0435\u0432\u044b\u0448\u0430\u0435\u0442 \u0433\u0440\u0430\u043d\u0438\u0446\u0443 \u041a\u043e\u0442\u0435\u043b\u044c\u043d\u0438\u043a\u043e\u0432\u0430, \u0440\u0435\u0434\u043a\u0438\u0435 \u0432\u044b\u0431\u043e\u0440\u043a\u0438 \u043f\u043e\u043f\u0430\u0434\u0430\u044e\u0442 \u043d\u0430 \u0440\u0430\u0437\u043d\u044b\u0435 \u043f\u0435\u0440\u0438\u043e\u0434\u044b \u0431\u044b\u0441\u0442\u0440\u043e\u0433\u043e \u043a\u043e\u043b\u0435\u0431\u0430\u043d\u0438\u044f. "
        "\u041f\u0440\u043e\u0435\u043a\u0446\u0438\u044f \u043e\u0442\u0441\u0447\u0451\u0442\u043e\u0432 \u043d\u0430 \u043d\u0438\u0436\u043d\u0438\u0439 \u0433\u0440\u0430\u0444\u0438\u043a \u043d\u0430\u0433\u043b\u044f\u0434\u043d\u043e \u043f\u043e\u043a\u0430\u0437\u044b\u0432\u0430\u0435\u0442 \u044d\u0444\u0444\u0435\u043a\u0442 \u043d\u0430\u043b\u043e\u0436\u0435\u043d\u0438\u044f: \u0431\u044b\u0441\u0442\u0440\u0430\u044f \u043f\u043e\u043c\u0435\u0445\u0430 \u043f\u0440\u0435\u0432\u0440\u0430\u0449\u0430\u0435\u0442\u0441\u044f \u0432 \u043b\u043e\u0436\u043d\u0443\u044e \u043d\u0438\u0437\u043a\u043e\u0447\u0430\u0441\u0442\u043e\u0442\u043d\u0443\u044e \u0432\u043e\u043b\u043d\u0443."
    )
    s3_text = (
        "\u0427\u0442\u043e\u0431\u044b \u043f\u0440\u0435\u0434\u043e\u0442\u0432\u0440\u0430\u0442\u0438\u0442\u044c \u043d\u0430\u043b\u043e\u0436\u0435\u043d\u0438\u0435 \u0447\u0430\u0441\u0442\u043e\u0442, \u043f\u0435\u0440\u0435\u0434 \u0432\u0445\u043e\u0434\u043e\u043c \u043f\u0440\u0435\u043e\u0431\u0440\u0430\u0437\u043e\u0432\u0430\u0442\u0435\u043b\u044f \u0443\u0441\u0442\u0430\u043d\u0430\u0432\u043b\u0438\u0432\u0430\u044e\u0442 \u0430\u043d\u0430\u043b\u043e\u0433\u043e\u0432\u044b\u0439 \u0444\u0438\u043b\u044c\u0442\u0440 \u043d\u0438\u0436\u043d\u0438\u0445 \u0447\u0430\u0441\u0442\u043e\u0442 \u0421\u0430\u043b\u043b\u0435\u043d\u0430\u2014\u041a\u0435\u044f. "
        "\u041a\u0430\u043a \u043f\u043e\u043a\u0430\u0437\u0430\u043d\u043e \u043d\u0430 \u0433\u0440\u0430\u0444\u0438\u043a\u0430\u0445 \u0441\u043b\u0435\u0432\u0430 \u0438 \u043d\u0430 \u0445\u0430\u0440\u0430\u043a\u0442\u0435\u0440\u0438\u0441\u0442\u0438\u043a\u0435 \u0441\u043f\u0440\u0430\u0432\u0430, \u0444\u0438\u043b\u044c\u0442\u0440 \u0441\u0432\u043e\u0431\u043e\u0434\u043d\u043e \u043f\u0440\u043e\u043f\u0443\u0441\u043a\u0430\u0435\u0442 \u043f\u043e\u043b\u0435\u0437\u043d\u044b\u0439 \u0441\u0438\u0433\u043d\u0430\u043b, \u043d\u043e \u043f\u043e\u0434\u0430\u0432\u043b\u044f\u0435\u0442 \u0432\u044b\u0441\u043e\u043a\u043e\u0447\u0430\u0441\u0442\u043e\u0442\u043d\u044b\u0435 \u043f\u043e\u043c\u0435\u0445\u0438 \u0435\u0449\u0451 \u0434\u043e \u0438\u0445 \u043e\u0446\u0438\u0444\u0440\u043e\u0432\u043a\u0438."
    )

    custom_scenes_data = [
        {
            "title": "\u0421\u0446\u0435\u043d\u0430 1: \u0414\u0438\u0441\u043a\u0440\u0435\u0442\u0438\u0437\u0430\u0446\u0438\u044f \u0441\u0438\u0433\u043d\u0430\u043b\u0430 \u0438 \u0443\u0441\u043b\u043e\u0432\u0438\u0435 \u041a\u043e\u0442\u0435\u043b\u044c\u043d\u0438\u043a\u043e\u0432\u0430",
            "narration_text": s1_text,
            "tts_narration_text": s1_text,
        },
        {
            "title": "\u0421\u0446\u0435\u043d\u0430 2: \u042d\u0444\u0444\u0435\u043a\u0442 \u043d\u0430\u043b\u043e\u0436\u0435\u043d\u0438\u044f \u0447\u0430\u0441\u0442\u043e\u0442 (\u0430\u043b\u0438\u0430\u0441\u0438\u043d\u0433)",
            "narration_text": s2_text,
            "tts_narration_text": s2_text,
        },
        {
            "title": "\u0421\u0446\u0435\u043d\u0430 3: \u0410\u043d\u0442\u0438\u0430\u043b\u0438\u0430\u0441\u0438\u043d\u0433\u043e\u0432\u044b\u0439 \u0424\u041d\u0427 \u0421\u0430\u043b\u043b\u0435\u043d\u0430\u2014\u041a\u0435\u044f \u043f\u0435\u0440\u0435\u0434 \u0410\u0426\u041f",
            "narration_text": s3_text,
            "tts_narration_text": s3_text,
        },
    ]

    for sc, custom in zip(project.scenes, custom_scenes_data):
        sc.title = custom["title"]
        sc.narration_text = custom["narration_text"]
        sc.tts_narration_text = custom["tts_narration_text"]

    renderer = WildMathingDSPSpecialtyRenderer()
    compositor = FlowEducationalCompositor(width=1280, height=720, fps=24)
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()

    scene_mp4_paths: List[Path] = []
    for sc in project.scenes:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_p = Path(tmp_dir)
            voice_wav = tmp_p / "voiceover.wav"
            duration_sec = await compositor._synthesize_scene_voiceover(
                scene=sc,
                language=project.language,
                out_wav=voice_wav,
            )
            sc.duration_sec = max(3, int(round(duration_sec)))
            sc.captions = compositor._build_word_captions(
                scene_id=sc.scene_id,
                narration_text=sc.narration_text,
                duration_sec=float(duration_sec),
            )
            _align_captions_to_wav(sc.captions, voice_wav)
            total_frames = max(48, int(duration_sec * 24))
            sc_out = out_dir / f"scene_{sc.scene_number:02d}_dsp_aliasing.mp4"
            cmd = [
                ffmpeg_exe,
                "-y",
                "-loglevel",
                "error",
                "-f",
                "rawvideo",
                "-vcodec",
                "rawvideo",
                "-s",
                "1280x720",
                "-pix_fmt",
                "rgb24",
                "-r",
                "24",
                "-i",
                "-",
                "-i",
                str(voice_wav),
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-preset",
                "fast",
                "-crf",
                "18",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                "-ar",
                "48000",
                "-ac",
                "2",
                "-shortest",
                "-movflags",
                "+faststart",
                str(sc_out),
            ]
            proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            assert proc.stdin is not None
            for f_idx in range(total_frames):
                raw_rgb = renderer.render_frame(sc, f_idx, total_frames)
                proc.stdin.write(raw_rgb)
            proc.stdin.close()
            proc.wait(timeout=120)
            scene_mp4_paths.append(sc_out)

    demo_mp4 = out_dir / "dsp_aliasing_demo.mp4"
    concat_txt = out_dir / "concat_list.txt"
    concat_txt.write_text(
        "\n".join(f"file '{p.name}'" for p in scene_mp4_paths),
        encoding="utf-8",
    )
    subprocess.run(
        [
            ffmpeg_exe,
            "-y",
            "-loglevel",
            "error",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_txt),
            "-c",
            "copy",
            "-movflags",
            "+faststart",
            str(demo_mp4),
        ],
        check=True,
    )

    srt_text = build_srt_subtitles(project.scenes)
    vtt_text = build_webvtt_subtitles(project.scenes)
    (out_dir / "dsp_aliasing_demo.srt").write_text(srt_text, encoding="utf-8")
    (out_dir / "dsp_aliasing_demo.vtt").write_text(vtt_text, encoding="utf-8")

    sheet_w, sheet_h = 1280, 1080
    sheet = Image.new("RGB", (sheet_w, sheet_h), (10, 15, 28))
    thumb_w, thumb_h = 620, 348
    for s_idx, sc in enumerate(project.scenes):
        for col_idx, ratio in enumerate((0.25, 0.75)):
            tot_f = 96
            f_idx = int(tot_f * ratio)
            raw = renderer.render_frame(sc, f_idx, tot_f)
            frame_im = Image.frombytes("RGB", (1280, 720), raw)
            if col_idx == 1:
                frame_im.save(out_dir / f"dsp_scene_{sc.scene_number:02d}_keyframe.png")
            thumb = frame_im.resize((thumb_w, thumb_h), Image.Resampling.LANCZOS)
            x_pos = 14 + col_idx * (thumb_w + 12)
            y_pos = 10 + s_idx * (thumb_h + 8)
            sheet.paste(thumb, (x_pos, y_pos))

    contact_sheet_path = out_dir / "contact_sheet.png"
    sheet.save(contact_sheet_path)

    manifest = {
        "style": "@WildMathing / Manim Vertical-Projection 1:1 DSP Specialty",
        "topic": topic_ru,
        "demo_mp4": str(demo_mp4),
        "demo_mp4_size_bytes": demo_mp4.stat().st_size if demo_mp4.is_file() else 0,
        "contact_sheet": str(contact_sheet_path),
    }
    (out_dir / "demo_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return manifest


if __name__ == "__main__":
    asyncio.run(run_dsp_specialty_demo())
