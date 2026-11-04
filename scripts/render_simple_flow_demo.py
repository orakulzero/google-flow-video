"""
Render the 3-scene physical pendulum & resonance educational video in the
@WildMathing / Manim visual canon with 1-to-1 vertical geometric projection:

- Scene 1 (Damped Pendulum):
  Mathematical pendulum at top-left/center swinging horizontally around x = x_eq.
  Directly below it, the damping graph x(t) has its vertical time axis t collinear
  with the pendulum's equilibrium line (x = x_eq), so the bob's horizontal deflection
  and the graph's point match 100% pixel-for-pixel via a vertical projection line.

- Scene 2 (Energy Transformation & Phase Trajectory):
  Clear, intuitive physics: the same damped pendulum at top-left with live velocity
  vector v(t), directly above its (x, v_x) phase diagram (linked by a vertical
  projection line), paired on the right with the real-time energy conversion graph
  E_pot(t) <-> E_kin(t) and live energy bars.

- Scene 3 (Driven Resonance):
  Driven pendulum at top-left under external periodic force F_ext(t) = F_0 cos(omega_0 t)
  whose oscillation amplitude grows in time. Directly below it (collinear with x = x_eq)
  is the time-domain resonance build-up graph x(t) matching the bob's amplitude 1:1
  at every instant, paired on the right with the Lorentzian resonance peak A(omega).
"""

from __future__ import annotations

import asyncio
import io
import json
import math
from pathlib import Path
import re
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

from src.flow_bridge import (  # noqa: E402
    FlowClient,
    FlowEducationalCompositor,
    FlowScene,
    build_srt_subtitles,
    build_webvtt_subtitles,
)

# @WildMathing / Manim Color Palette (RGB)
COL_BG = (13, 17, 26)         # #0D111A
COL_CYAN = (56, 189, 248)     # #38BDF8 - coordinate x(t), E_pot
COL_GOLD = (251, 191, 36)     # #FBBF24 - projection trace, resonance, F_ext
COL_RED = (248, 113, 113)     # #F87171 - damping envelope, friction force, E_total
COL_GREEN = (74, 222, 128)    # #4ADE80 - restoring force, velocity v(t), E_kin
COL_MUTED = (148, 163, 184)   # #94A3B8 - axes & secondary labels
COL_WHITE = (248, 250, 252)   # #F8FAFC - equations & primary text


def _render_latex_sprite(
    tex: str,
    fontsize: int = 16,
    color: str = "#F8FAFC",
    dpi: int = 130,
) -> Image.Image:
    """Render a transparent Computer Modern LaTeX formula sprite via matplotlib.mathtext."""
    plt.rcParams["mathtext.fontset"] = "cm"
    fig = plt.figure(figsize=(6.5, 1.3), dpi=dpi)
    fig.patch.set_alpha(0.0)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_axis_off()
    ax.patch.set_alpha(0.0)
    ax.text(0.5, 0.5, tex, fontsize=fontsize, color=color, ha="center", va="center")
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, transparent=True)
    plt.close(fig)
    buf.seek(0)
    im = Image.open(buf).convert("RGBA")
    bbox = im.getbbox()
    if bbox:
        pad = 6
        x0 = max(0, bbox[0] - pad)
        y0 = max(0, bbox[1] - pad)
        x1 = min(im.width, bbox[2] + pad)
        y1 = min(im.height, bbox[3] + pad)
        return im.crop((x0, y0, x1, y1))
    return im


def _build_scene1_base_canvas() -> Tuple[Image.Image, Dict[str, Image.Image]]:
    """
    Build Scene 1 base canvas (1280x720):
    - Top-left/center (x_eq = 3.9): Mathematical pendulum swinging horizontally around x = x_eq.
    - Directly below (x_eq = 3.9, y from 3.85 down to 1.35): Damping graph x(t) with vertical
      time axis t collinear with the pendulum equilibrium line x = x_eq.
    - Right half (x in [7.3, 12.2]): @WildMathing LaTeX physics explanation & live amplitude meter.
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

    # Scene header
    ax.text(
        0.55,
        6.86,
        "01. \u0417\u0430\u0442\u0443\u0445\u0430\u044e\u0449\u0438\u0435 \u043a\u043e\u043b\u0435\u0431\u0430\u043d\u0438\u044f: \u0433\u0440\u0430\u0444\u0438\u043a \u0437\u0430\u0442\u0443\u0445\u0430\u043d\u0438\u044f \u043f\u043e\u0434 \u043c\u0430\u044f\u0442\u043d\u0438\u043a\u043e\u043c",
        color="#E2E8F0",
        fontsize=13.5,
        weight="bold",
        va="center",
    )

    x_eq = 3.90
    A0_m = 1.65
    y_top = 3.82
    y_bot = 1.38
    H_t = y_top - y_bot

    # Label for equilibrium line at top
    ax.text(
        x_eq,
        6.45,
        "\u041e\u0441\u044c \u0440\u0430\u0432\u043d\u043e\u0432\u0435\u0441\u0438\u044f " + d + "x = 0" + d,
        color="#94A3B8",
        fontsize=11.5,
        ha="center",
    )

    # Horizontal x-axis of the damping graph directly under the pendulum
    ax.annotate(
        "",
        xy=(x_eq + A0_m + 0.55, y_top),
        xytext=(x_eq - A0_m - 0.55, y_top),
        arrowprops=dict(arrowstyle="->", color="#64748B", lw=1.8),
    )
    # Vertical time axis t running DOWNWARD exactly along the equilibrium line x = x_eq
    ax.annotate(
        "",
        xy=(x_eq, y_bot - 0.22),
        xytext=(x_eq, y_top + 0.12),
        arrowprops=dict(arrowstyle="->", color="#64748B", lw=1.8),
    )

    # Ticks on horizontal displacement axis x
    for dx_val, lbl_tex in ((-A0_m, r"-A_0"), (0.0, r"0"), (A0_m, r"+A_0")):
        tx = x_eq + dx_val
        ax.plot([tx, tx], [y_top - 0.07, y_top + 0.07], color="#94A3B8", lw=1.4)
        if dx_val != 0.0:
            ax.text(tx, y_top + 0.14, d + lbl_tex + d, color="#94A3B8", fontsize=12.5, ha="center")
        else:
            ax.text(tx + 0.12, y_top + 0.12, d + "0" + d, color="#94A3B8", fontsize=12)

    ax.text(x_eq + A0_m + 0.62, y_top - 0.05, d + "x(t)" + d, color="#38BDF8", fontsize=15.5)
    ax.text(
        x_eq + 0.16,
        y_bot - 0.22,
        "\u0412\u0440\u0435\u043c\u044f " + d + r"t \downarrow" + d,
        color="#FBBF24",
        fontsize=13,
        weight="bold",
        va="center",
    )

    # Symmetric exponential damping envelopes +-A_0 * exp(-gamma * t) narrowing downward toward x_eq
    u_arr = np.linspace(0.0, 1.0, 400)
    env_arr = A0_m * np.exp(-1.55 * u_arr)
    y_arr = y_top - u_arr * H_t
    ax.plot(x_eq + env_arr, y_arr, color="#F87171", lw=1.5, ls="--", alpha=0.82)
    ax.plot(x_eq - env_arr, y_arr, color="#F87171", lw=1.5, ls="--", alpha=0.82)
    ax.text(x_eq + A0_m * 0.72, y_top - 0.85, d + r"+A_0 e^{-\gamma t}" + d, color="#F87171", fontsize=13.5)
    ax.text(x_eq - A0_m * 0.72, y_top - 0.85, d + r"-A_0 e^{-\gamma t}" + d, color="#F87171", fontsize=13.5, ha="right")

    # Faint full wave guide
    wave_guide = env_arr * np.cos(2.0 * np.pi * 3.5 * u_arr)
    ax.plot(x_eq + wave_guide, y_arr, color="#38BDF8", lw=1.0, alpha=0.20)

    # Right half: Pedagogical physics cards & live amplitude scale
    rx_card = 9.65
    eq1_tex = d + r"\ddot{x} + 2\gamma\dot{x} + \omega_0^2 x = 0" + d
    ax.text(
        rx_card,
        6.02,
        eq1_tex,
        color="#F8FAFC",
        fontsize=17.5,
        ha="center",
        va="center",
        bbox=dict(boxstyle="round,pad=0.40", facecolor="#131C31", edgecolor="#38BDF8", lw=1.4),
    )

    eq2_tex = d + r"x(t) = A_0 e^{-\gamma t}\cos(\omega_d t), \quad A(t) = A_0 e^{-\gamma t}" + d
    ax.text(
        rx_card,
        5.05,
        eq2_tex,
        color="#F8FAFC",
        fontsize=15.0,
        ha="center",
        va="center",
        bbox=dict(boxstyle="round,pad=0.38", facecolor="#131C31", edgecolor="#F87171", lw=1.2),
    )

    # Explanatory bullets on the right
    ax.text(
        7.15,
        4.22,
        "\u2022 \u0417\u0435\u043b\u0451\u043d\u044b\u0439 \u0432\u0435\u043a\u0442\u043e\u0440 "
        + d
        + r"\vec{F}_r = -mg\sin\theta"
        + d
        + " \u0442\u044f\u043d\u0435\u0442 \u0433\u0440\u0443\u0437 \u043a \u043e\u0441\u0438 "
        + d
        + "x=0"
        + d,
        color="#4ADE80",
        fontsize=12.0,
    )
    ax.text(
        7.15,
        3.74,
        "\u2022 \u041a\u0440\u0430\u0441\u043d\u044b\u0439 \u0432\u0435\u043a\u0442\u043e\u0440 "
        + d
        + r"\vec{F}_d = -b\vec{v}"
        + d
        + " (\u0442\u0440\u0435\u043d\u0438\u0435) \u0442\u043e\u0440\u043c\u043e\u0437\u0438\u0442 \u0434\u0432\u0438\u0436\u0435\u043d\u0438\u0435",
        color="#F87171",
        fontsize=12.0,
    )
    ax.text(
        7.15,
        3.26,
        "\u2022 \u0417\u043e\u043b\u043e\u0442\u043e\u0439 \u043f\u0443\u043d\u043a\u0442\u0438\u0440 \u043f\u0440\u043e\u0435\u0446\u0438\u0440\u0443\u0435\u0442 \u043f\u043e\u043b\u043e\u0436\u0435\u043d\u0438\u0435 \u0433\u0440\u0443\u0437\u0430 \u043d\u0430 \u0433\u0440\u0430\u0444\u0438\u043a",
        color="#FBBF24",
        fontsize=12.0,
    )

    ax.text(
        7.15,
        2.52,
        "\u0422\u0435\u043a\u0443\u0449\u0430\u044f \u0430\u043c\u043f\u043b\u0438\u0442\u0443\u0434\u0430 \u0440\u0430\u0437\u043c\u0430\u0445\u0430 " + d + r"A(t) = A_0 e^{-\gamma t}" + d + ":",
        color="#E2E8F0",
        fontsize=12.5,
        weight="bold",
    )

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=100)
    plt.close(fig)
    buf.seek(0)
    base_img = Image.open(buf).convert("RGB")

    sprites = {
        "fr": _render_latex_sprite(d + r"\vec{F}_r" + d, fontsize=14, color="#4ADE80"),
        "fd": _render_latex_sprite(d + r"\vec{F}_d" + d, fontsize=14, color="#F87171"),
    }
    return base_img, sprites


def _build_scene2_base_canvas() -> Tuple[Image.Image, Dict[str, Image.Image]]:
    """
    Build Scene 2 base canvas (1280x720):
    - Top-left (x_eq = 3.55): Mathematical pendulum with velocity vector v(t).
    - Directly below (x_eq = 3.55, cy_p = 2.55): Phase diagram (Displacement x vs Velocity v_x)
      sharing the exact same horizontal x axis and equilibrium centerline x = 0!
    - Right half (x in [7.2, 12.1]): Energy conversion graph E_pot(t) <-> E_kin(t) and total
      mechanical energy E_total(t) = E_0 exp(-2*gamma*t).
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
        "02. \u0421\u0432\u044f\u0437\u044c \u0441\u043a\u043e\u0440\u043e\u0441\u0442\u0438 \u0441 \u043e\u0442\u043a\u043b\u043e\u043d\u0435\u043d\u0438\u0435\u043c \u0438 \u043f\u0440\u0435\u0432\u0440\u0430\u0449\u0435\u043d\u0438\u0435 \u044d\u043d\u0435\u0440\u0433\u0438\u0438",
        color="#E2E8F0",
        fontsize=13.5,
        weight="bold",
        va="center",
    )

    x_eq = 3.55
    R_p = 1.50
    cy_p = 2.55

    ax.text(
        x_eq,
        6.45,
        "\u0420\u0430\u0432\u043d\u043e\u0432\u0435\u0441\u0438\u0435 " + d + "x = 0" + d + " (\u043c\u0430\u043a\u0441. \u0441\u043a\u043e\u0440\u043e\u0441\u0442\u044c)",
        color="#94A3B8",
        fontsize=11.5,
        ha="center",
    )

    # Phase diagram directly below the pendulum sharing x_eq = 3.55
    ax.annotate(
        "",
        xy=(x_eq + R_p + 0.50, cy_p),
        xytext=(x_eq - R_p - 0.50, cy_p),
        arrowprops=dict(arrowstyle="->", color="#64748B", lw=1.7),
    )
    ax.annotate(
        "",
        xy=(x_eq, cy_p + 1.25),
        xytext=(x_eq, cy_p - 1.25),
        arrowprops=dict(arrowstyle="->", color="#64748B", lw=1.7),
    )
    ax.text(x_eq + R_p + 0.55, cy_p - 0.05, d + "x" + d, color="#38BDF8", fontsize=15)
    ax.text(x_eq + 0.14, cy_p + 1.18, "\u0421\u043a\u043e\u0440\u043e\u0441\u0442\u044c " + d + "v_x" + d, color="#4ADE80", fontsize=12.5, weight="bold")
    ax.text(x_eq + R_p + 0.08, cy_p + 0.14, "\u041a\u0440\u0430\u0439: " + d + "v=0" + d, color="#38BDF8", fontsize=10.5, ha="left")
    ax.text(x_eq - R_p - 0.08, cy_p + 0.14, "\u041a\u0440\u0430\u0439: " + d + "v=0" + d, color="#38BDF8", fontsize=10.5, ha="right")

    # Faint full phase spiral guide (ellipse with aspect 1.50 horizontal, 1.05 vertical)
    u_sp = np.linspace(0.0, 1.0, 400)
    r_sp = np.exp(-1.45 * u_sp)
    x_sp = x_eq + R_p * r_sp * np.cos(2.0 * np.pi * 3.0 * u_sp)
    y_sp = cy_p - 1.05 * r_sp * np.sin(2.0 * np.pi * 3.0 * u_sp)
    ax.plot(x_sp, y_sp, color="#4ADE80", lw=1.0, alpha=0.22)

    # Right half: Energy transformation formula + curves E_pot(t), E_kin(t), E_total(t)
    eq_en = (
        d
        + r"E(t) = E_p(t) + E_k(t) = \frac{kx^2}{2} + \frac{mv^2}{2} = E_0 e^{-2\gamma t}"
        + d
    )
    ax.text(
        9.45,
        6.05,
        eq_en,
        color="#F8FAFC",
        fontsize=15.0,
        ha="center",
        va="center",
        bbox=dict(boxstyle="round,pad=0.38", facecolor="#131C31", edgecolor="#4ADE80", lw=1.4),
    )

    # Energy time plot axes: x in [7.0, 11.7], y in [2.35, 5.05]
    ex0, ew, ey0, eh = 7.0, 4.6, 2.45, 2.50
    ax.annotate("", xy=(ex0 + ew + 0.30, ey0), xytext=(ex0, ey0), arrowprops=dict(arrowstyle="->", color="#64748B", lw=1.7))
    ax.annotate("", xy=(ex0, ey0 + eh + 0.25), xytext=(ex0, ey0), arrowprops=dict(arrowstyle="->", color="#64748B", lw=1.7))
    ax.text(ex0 + ew + 0.35, ey0 - 0.05, d + "t" + d, color="#94A3B8", fontsize=14.5)
    ax.text(ex0 + 0.14, ey0 + eh + 0.18, "\u042d\u043d\u0435\u0440\u0433\u0438\u044f " + d + "E(t)" + d, color="#E2E8F0", fontsize=13, weight="bold")

    t_e = np.linspace(0.0, 1.0, 400)
    etot = np.exp(-2.2 * t_e)
    epot = etot * (np.cos(2.0 * np.pi * 3.0 * t_e) ** 2)
    ekin = etot * (np.sin(2.0 * np.pi * 3.0 * t_e) ** 2)
    tx_e = ex0 + t_e * ew
    ax.plot(tx_e, ey0 + etot * eh, color="#F87171", lw=1.8, ls="--", alpha=0.85)
    ax.plot(tx_e, ey0 + epot * eh, color="#38BDF8", lw=1.1, alpha=0.25)
    ax.plot(tx_e, ey0 + ekin * eh, color="#4ADE80", lw=1.1, alpha=0.25)

    ax.text(ex0 + 1.45, ey0 + eh * 0.78, d + r"E(t) = E_0 e^{-2\gamma t}" + d + " (\u0443\u0431\u044b\u0432\u0430\u0435\u0442 \u0438\u0437-\u0437\u0430 \u0442\u0440\u0435\u043d\u0438\u044f)", color="#F87171", fontsize=12)
    ax.text(ex0 + 0.10, 1.96, "\u25a0 " + d + r"E_p = kx^2/2" + d + " \u2014 \u043f\u043e\u0442\u0435\u043d\u0446\u0438\u0430\u043b\u044c\u043d\u0430\u044f (\u043c\u0430\u043a\u0441. \u043d\u0430 \u043a\u0440\u0430\u044f\u0445)", color="#38BDF8", fontsize=11.8, weight="bold")
    ax.text(ex0 + 0.10, 1.54, "\u25a0 " + d + r"E_k = mv^2/2" + d + " \u2014 \u043a\u0438\u043d\u0435\u0442\u0438\u0447\u0435\u0441\u043a\u0430\u044f (\u043c\u0430\u043a\u0441. \u0432 \u0446\u0435\u043d\u0442\u0440\u0435 " + d + "x=0" + d + ")", color="#4ADE80", fontsize=11.8, weight="bold")

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=100)
    plt.close(fig)
    buf.seek(0)
    return Image.open(buf).convert("RGB"), {}


def _build_scene3_base_canvas() -> Tuple[Image.Image, Dict[str, Image.Image]]:
    """
    Build Scene 3 base canvas (1280x720):
    - Top-left (x_eq = 3.55): Driven mathematical pendulum under periodic force F_ext(t) = F_0 cos(omega_0 t).
    - Directly below (x_eq = 3.55, y from 3.82 down to 1.38): Time-domain resonance build-up graph x(t)
      whose vertical time axis t coincides with the equilibrium line x = 0, so the pendulum's growing
      amplitude matches the graph 100% pixel-for-pixel at every instant!
    - Right half (x in [7.2, 12.1]): Lorentzian frequency response curve A(omega) showing why omega = omega_0
      produces maximum steady-state swing.
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
        "03. \u0420\u0435\u0437\u043e\u043d\u0430\u043d\u0441: \u0440\u0430\u0441\u043a\u0430\u0447\u043a\u0430 \u043c\u0430\u044f\u0442\u043d\u0438\u043a\u0430 \u043f\u043e \u0432\u0440\u0435\u043c\u0435\u043d\u0438 \u0438 \u043f\u0438\u043a \u0410\u0427\u0425",
        color="#E2E8F0",
        fontsize=13.5,
        weight="bold",
        va="center",
    )

    x_eq = 3.55
    A_max = 1.65
    y_top = 3.82
    y_bot = 1.38
    H_t = y_top - y_bot

    ax.text(
        x_eq,
        6.45,
        "\u041e\u0441\u044c \u0440\u0430\u0432\u043d\u043e\u0432\u0435\u0441\u0438\u044f " + d + "x = 0" + d + " (\u0440\u0430\u0441\u043a\u0430\u0447\u043a\u0430 \u043f\u0440\u0438 " + d + r"\omega = \omega_0" + d + ")",
        color="#FBBF24",
        fontsize=11.5,
        ha="center",
        weight="bold",
    )

    # Horizontal x-axis directly below the driven pendulum
    ax.annotate(
        "",
        xy=(x_eq + A_max + 0.50, y_top),
        xytext=(x_eq - A_max - 0.50, y_top),
        arrowprops=dict(arrowstyle="->", color="#64748B", lw=1.8),
    )
    # Vertical time axis t running DOWNWARD along x = x_eq
    ax.annotate(
        "",
        xy=(x_eq, y_bot - 0.22),
        xytext=(x_eq, y_top + 0.12),
        arrowprops=dict(arrowstyle="->", color="#64748B", lw=1.8),
    )
    for dx_val, lbl_tex in ((-A_max, r"-A_{\max}"), (0.0, r"0"), (A_max, r"+A_{\max}")):
        tx = x_eq + dx_val
        ax.plot([tx, tx], [y_top - 0.07, y_top + 0.07], color="#94A3B8", lw=1.4)
        if dx_val != 0.0:
            ax.text(tx, y_top + 0.14, d + lbl_tex + d, color="#FBBF24", fontsize=12, ha="center")
    ax.text(x_eq + A_max + 0.56, y_top - 0.05, d + "x(t)" + d, color="#38BDF8", fontsize=15)
    ax.text(
        x_eq + 0.15,
        y_bot - 0.22,
        "\u0412\u0440\u0435\u043c\u044f " + d + r"t \downarrow" + d,
        color="#FBBF24",
        fontsize=13,
        weight="bold",
        va="center",
    )

    # Expanding resonance envelopes +-A(t) = +-A_max * (0.18 + 0.82*(1 - exp(-2.5*u)))
    u_arr = np.linspace(0.0, 1.0, 400)
    env_grow = A_max * (0.18 + 0.82 * (1.0 - np.exp(-2.5 * u_arr)))
    y_arr = y_top - u_arr * H_t
    ax.plot(x_eq + env_grow, y_arr, color="#FBBF24", lw=1.5, ls="--", alpha=0.85)
    ax.plot(x_eq - env_grow, y_arr, color="#FBBF24", lw=1.5, ls="--", alpha=0.85)
    ax.text(x_eq + A_max + 0.12, y_bot + 0.35, d + r"+A(t)\uparrow" + d, color="#FBBF24", fontsize=12.5, ha="left")
    ax.text(x_eq - A_max - 0.12, y_bot + 0.35, d + r"-A(t)\uparrow" + d, color="#FBBF24", fontsize=12.5, ha="right")

    wave_grow = env_grow * np.sin(2.0 * np.pi * 4.0 * u_arr)
    ax.plot(x_eq + wave_grow, y_arr, color="#38BDF8", lw=1.0, alpha=0.20)

    # Right half: Formula + Resonance Curve A(omega)
    eq_res = (
        d
        + r"\ddot{x} + 2\gamma\dot{x} + \omega_0^2 x = \frac{F_0}{m}\cos(\omega t), \quad \omega = \omega_0 \Longrightarrow A_{\max} = \frac{F_0}{2m\gamma\omega_0}"
        + d
    )
    ax.text(
        9.50,
        6.05,
        eq_res,
        color="#F8FAFC",
        fontsize=14.2,
        ha="center",
        va="center",
        bbox=dict(boxstyle="round,pad=0.36", facecolor="#131C31", edgecolor="#FBBF24", lw=1.4),
    )

    rx0, rw, ry0, rh = 7.05, 4.75, 1.75, 3.25
    ax.annotate("", xy=(rx0 + rw + 0.30, ry0), xytext=(rx0, ry0), arrowprops=dict(arrowstyle="->", color="#64748B", lw=1.7))
    ax.annotate("", xy=(rx0, ry0 + rh + 0.25), xytext=(rx0, ry0), arrowprops=dict(arrowstyle="->", color="#64748B", lw=1.7))
    ax.text(rx0 + rw + 0.35, ry0 - 0.05, d + r"\omega/\omega_0" + d, color="#94A3B8", fontsize=14.5)
    ax.text(rx0 + 0.12, ry0 + rh + 0.16, "\u0410\u043c\u043f\u043b\u0438\u0442\u0443\u0434\u0430 " + d + r"A(\omega)" + d, color="#38BDF8", fontsize=13, weight="bold")

    u_freq = np.linspace(0.02, 2.2, 400)
    x_freq = rx0 + (u_freq / 2.2) * rw
    q_main = 5.0
    amp_main = 1.0 / np.sqrt((1.0 - u_freq**2) ** 2 + (u_freq / q_main) ** 2)
    y_main = ry0 + (amp_main / 5.0) * rh
    ax.plot(x_freq, y_main, color="#38BDF8", lw=2.2, alpha=0.85)

    # Secondary high-friction curve Q=1.8
    amp_low = 1.0 / np.sqrt((1.0 - u_freq**2) ** 2 + (u_freq / 1.8) ** 2)
    ax.plot(x_freq, ry0 + (amp_low / 5.0) * rh, color="#F87171", lw=1.4, ls="--", alpha=0.75)
    ax.text(rx0 + (1.35 / 2.2) * rw, ry0 + 0.92, "\u0411\u043e\u043b\u044c\u0448\u043e\u0435 \u0442\u0440\u0435\u043d\u0438\u0435", color="#F87171", fontsize=11.5)

    # Resonance vertical line at omega / omega_0 = 1.0
    res_x = rx0 + (1.0 / 2.2) * rw
    res_top_y = ry0 + rh
    ax.plot([res_x, res_x], [ry0, res_top_y], color="#FBBF24", lw=1.5, ls=":")
    ax.text(res_x, ry0 - 0.28, d + r"\omega = \omega_0" + d + " (\u0420\u0435\u0437\u043e\u043d\u0430\u043d\u0441)", color="#FBBF24", fontsize=12.5, ha="center", weight="bold")
    ax.text(res_x + 0.14, res_top_y - 0.08, d + r"A_{\max}" + d, color="#FBBF24", fontsize=14, weight="bold")

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=100)
    plt.close(fig)
    buf.seek(0)
    return Image.open(buf).convert("RGB"), {}


def _draw_arrow_2x(
    draw: ImageDraw.ImageDraw,
    x0: float,
    y0: float,
    x1: float,
    y1: float,
    color: Tuple[int, int, int, int],
    width: int = 6,
    head_len: int = 24,
    head_w: int = 12,
) -> None:
    """Draw a smooth anti-aliased vector arrow on the 2x supersampled canvas."""
    dx = x1 - x0
    dy = y1 - y0
    length = math.hypot(dx, dy)
    if length < 4:
        return
    ux, uy = dx / length, dy / length
    px, py = -uy, ux
    bx = x1 - ux * head_len
    by = y1 - uy * head_len
    draw.line([(x0, y0), (bx, by)], fill=color, width=width)
    poly = [
        (x1, y1),
        (bx + px * head_w, by + py * head_w),
        (bx - px * head_w, by - py * head_w),
    ]
    draw.polygon(poly, fill=color)


def _draw_dashed_line_2x(
    draw: ImageDraw.ImageDraw,
    x0: float,
    y0: float,
    x1: float,
    y1: float,
    color: Tuple[int, int, int, int],
    width: int = 4,
    dash_len: int = 16,
    gap_len: int = 12,
) -> None:
    dx = x1 - x0
    dy = y1 - y0
    dist = math.hypot(dx, dy)
    if dist < 2:
        return
    ux, uy = dx / dist, dy / dist
    cur = 0.0
    while cur < dist:
        nxt = min(dist, cur + dash_len)
        draw.line(
            [(x0 + ux * cur, y0 + uy * cur), (x0 + ux * nxt, y0 + uy * nxt)],
            fill=color,
            width=width,
        )
        cur += dash_len + gap_len


def _draw_wildmathing_subtitles(
    img: Image.Image,
    scene: FlowScene,
    p: float,
    f_sub: ImageFont.FreeTypeFont,
) -> None:
    """Draw clean, minimal centered @WildMathing subtitles at the bottom of the 1280x720 frame."""
    draw = ImageDraw.Draw(img)
    W, H = img.size
    sub_x0, sub_y0, sub_x1, sub_y1 = 110, 622, 1170, 704
    draw.rounded_rectangle(
        [sub_x0, sub_y0, sub_x1, sub_y1],
        radius=12,
        fill=(15, 22, 36),
        outline=(42, 62, 96),
        width=1,
    )
    captions = scene.captions
    cur_ms = int(round(p * max(1, (captions.duration_ms if captions else scene.duration_sec * 1000))))
    if captions and getattr(captions, "pages", None):
        active_page = captions.pages[0]
        for pg in captions.pages:
            if pg.start_ms <= cur_ms <= pg.end_ms:
                active_page = pg
                break
            if cur_ms > pg.end_ms:
                active_page = pg

        active_word_idx = -1
        for wt in active_page.words:
            if wt.start_ms <= cur_ms <= wt.end_ms:
                active_word_idx = wt.word_index
                break
        if active_word_idx == -1 and active_page.words:
            for wt in active_page.words:
                if cur_ms >= wt.start_ms:
                    active_word_idx = wt.word_index

        for line_i in range(2):
            line_words = [wt for wt in active_page.words if wt.line_index == line_i]
            if not line_words:
                continue
            word_widths: List[int] = []
            for wt in line_words:
                try:
                    tw_i = int(f_sub.getlength(wt.word + " "))
                except Exception:
                    tw_i = (len(wt.word) + 1) * 11
                word_widths.append(tw_i)
            total_w = sum(word_widths)
            cursor_x = max(sub_x0 + 24, (W - total_w) // 2)
            y_line = sub_y0 + 13 + line_i * 32
            for wt, tw in zip(line_words, word_widths):
                is_curr = wt.word_index == active_word_idx
                if is_curr:
                    draw.rounded_rectangle(
                        [cursor_x - 4, y_line - 1, cursor_x + tw - 4, y_line + 25],
                        radius=4,
                        fill=(52, 42, 14),
                    )
                    draw.text((cursor_x, y_line), wt.word, fill=COL_GOLD, font=f_sub)
                else:
                    draw.text((cursor_x, y_line), wt.word, fill=COL_WHITE, font=f_sub)
                cursor_x += tw


class WildMathingPhysicsRenderer:
    """
    Full-canvas @WildMathing / Manim-style 2x-supersampled renderer with 1-to-1
    vertical alignment between the mathematical pendulum and the graphs directly below it.
    """

    def __init__(self) -> None:
        self.s1_base, self.s1_sprites = _build_scene1_base_canvas()
        self.s2_base, self.s2_sprites = _build_scene2_base_canvas()
        self.s3_base, self.s3_sprites = _build_scene3_base_canvas()
        try:
            self.f_sub = ImageFont.truetype("C:/Windows/Fonts/segoeuib.ttf", 19)
            self.f_bob = ImageFont.truetype("C:/Windows/Fonts/timesbi.ttf", 36)
            self.f_hud = ImageFont.truetype("C:/Windows/Fonts/segoeuib.ttf", 28)
        except Exception:
            self.f_sub = ImageFont.load_default()
            self.f_bob = self.f_sub
            self.f_hud = self.f_sub

    def _mx(self, x_math: float) -> float:
        """Convert matplotlib x in [0, 12.8] to 2x supersampled pixel x in [0, 2560]."""
        return x_math * 200.0

    def _my(self, y_math: float) -> float:
        """Convert matplotlib y in [0, 7.2] to 2x supersampled pixel y in [0, 1440]."""
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
            # SCENE 1: Damped Pendulum ABOVE + Vertical-Time Damping Graph BELOW
            # Exact geometric match: bx_m == wx_m at every instant p!
            # =========================================================================
            x_eq = 3.90
            y_piv = 6.22
            L_m = 1.75
            A0_m = 1.65
            y_top = 3.82
            y_bot = 1.38
            H_t = y_top - y_bot

            env_p = A0_m * math.exp(-1.55 * p)
            phase = 2.0 * math.pi * 3.5 * p
            dx_m = env_p * math.cos(phase)
            vx_norm = -env_p * math.sin(phase)

            # Bob position: horizontal coordinate is strictly x_eq + dx_m!
            bx_m = x_eq + dx_m
            sin_th = max(-0.95, min(0.95, dx_m / L_m))
            theta = math.asin(sin_th)
            by_m = y_piv - L_m * math.cos(theta)

            px, py = self._mx(x_eq), self._my(y_piv)
            bx, by = self._mx(bx_m), self._my(by_m)

            # Continuous vertical equilibrium dashed reference from ceiling straight into time axis t
            _draw_dashed_line_2x(
                d2x, px, py, px, self._my(y_top), (100, 116, 139, 210), width=3, dash_len=14, gap_len=10
            )
            # Ceiling support bar
            d2x.line([(px - 220, py), (px + 220, py)], fill=(148, 163, 184, 255), width=8)
            # Angle arc for theta(t)
            if abs(theta) > 0.02:
                arc_r = 105
                deg_eq = 90.0
                deg_rod = 90.0 - math.degrees(theta)
                a0, a1 = min(deg_eq, deg_rod), max(deg_eq, deg_rod)
                d2x.arc([px - arc_r, py - arc_r, px + arc_r, py + arc_r], start=a0, end=a1, fill=(*COL_GOLD, 235), width=5)

            # Pendulum rod
            d2x.line([(px, py), (bx, by)], fill=(226, 232, 240, 255), width=6)

            # Live wave x(t) traced downward along vertical time axis t up to current p
            n_pts = max(2, int(p * 320))
            wave_pts: List[Tuple[float, float]] = []
            for i in range(n_pts + 1):
                u = min(p, i / 320.0)
                dx_u = A0_m * math.exp(-1.55 * u) * math.cos(2.0 * math.pi * 3.5 * u)
                wx_u = self._mx(x_eq + dx_u)
                wy_u = self._my(y_top - u * H_t)
                wave_pts.append((wx_u, wy_u))
            if len(wave_pts) > 1:
                d2x.line(wave_pts, fill=(*COL_CYAN, 255), width=7)

            cur_wx, cur_wy = wave_pts[-1]
            # STRICTLY VERTICAL golden projection line from the pendulum bob (bx, by) straight down to (cur_wx, cur_wy)!
            _draw_dashed_line_2x(d2x, bx, by, cur_wx, cur_wy, (*COL_GOLD, 245), width=5, dash_len=14, gap_len=10)
            # Horizontal deviation bar from equilibrium axis x_eq to current wave point (cur_wx, cur_wy)
            d2x.line([(px, cur_wy), (cur_wx, cur_wy)], fill=(*COL_GOLD, 190), width=4)
            d2x.ellipse([cur_wx - 15, cur_wy - 15, cur_wx + 15, cur_wy + 15], fill=(*COL_GOLD, 255))

            # Bob circle m
            r_bob = 54
            d2x.ellipse([bx - r_bob, by - r_bob, bx + r_bob, by + r_bob], fill=(*COL_CYAN, 255), outline=(224, 242, 254, 255), width=5)
            d2x.text((bx - 16, by - 22), "m", fill=(13, 17, 26, 255), font=self.f_bob)

            # Restoring force vector F_r (green, pointing horizontally/tangentially back toward x_eq)
            fr_sign = -1.0 if dx_m >= 0.0 else 1.0
            fr_len = 65.0 + abs(dx_m / A0_m) * 180.0
            _draw_arrow_2x(
                d2x,
                bx + fr_sign * (r_bob + 4),
                by - 8,
                bx + fr_sign * (r_bob + fr_len),
                by - 8,
                (*COL_GREEN, 255),
                width=7,
                head_len=24,
            )
            # Viscous damping force vector F_d (red, opposite to velocity vx_norm)
            fd_sign = -1.0 if vx_norm >= 0.0 else 1.0
            fd_len = 60.0 + abs(vx_norm / A0_m) * 165.0
            _draw_arrow_2x(
                d2x,
                bx + fd_sign * (r_bob + 4),
                by + 12,
                bx + fd_sign * (r_bob + fd_len),
                by + 12,
                (*COL_RED, 255),
                width=7,
                head_len=24,
            )

            # Right-side live amplitude progress bar (shows A(t) / A_0 decaying in real time)
            bar_x0, bar_y0 = self._mx(7.35), self._my(2.15)
            bar_w_max = 880.0
            bar_h = 44.0
            ratio_amp = math.exp(-1.55 * p)
            d2x.rounded_rectangle([bar_x0, bar_y0, bar_x0 + bar_w_max, bar_y0 + bar_h], radius=10, fill=(22, 32, 52, 255), outline=(71, 85, 105, 255), width=3)
            d2x.rounded_rectangle([bar_x0, bar_y0, bar_x0 + bar_w_max * ratio_amp, bar_y0 + bar_h], radius=10, fill=(*COL_RED, 230))
            pct_txt = f"A(t) = {int(round(ratio_amp * 100))}% A0"
            d2x.text((bar_x0 + 24, bar_y0 + 6), pct_txt, fill=(248, 250, 252, 255), font=self.f_hud)

        elif sc_num == 2:
            # =========================================================================
            # SCENE 2: Pendulum ABOVE + Phase Diagram (x, v_x) BELOW + Energy Graph RIGHT
            # Strict vertical alignment: bx == sx on the phase diagram!
            # =========================================================================
            x_eq = 3.55
            y_piv = 6.22
            L_m = 1.70
            R_p = 1.50
            cy_p = 2.55

            env_p = math.exp(-1.45 * p)
            phase = 2.0 * math.pi * 3.0 * p
            dx_m = R_p * env_p * math.cos(phase)
            vy_phase = -1.05 * env_p * math.sin(phase)

            bx_m = x_eq + dx_m
            sin_th = max(-0.95, min(0.95, dx_m / L_m))
            theta = math.asin(sin_th)
            by_m = y_piv - L_m * math.cos(theta)

            px, py = self._mx(x_eq), self._my(y_piv)
            bx, by = self._mx(bx_m), self._my(by_m)

            # Equilibrium reference line from ceiling down to phase portrait origin
            _draw_dashed_line_2x(
                d2x, px, py, px, self._my(cy_p + 1.25), (100, 116, 139, 200), width=3, dash_len=14, gap_len=10
            )
            d2x.line([(px - 200, py), (px + 200, py)], fill=(148, 163, 184, 255), width=8)
            d2x.line([(px, py), (bx, by)], fill=(226, 232, 240, 255), width=6)

            # Phase spiral (x, v_x) traced up to current p directly below the pendulum
            n_sp = max(2, int(p * 300))
            sp_pts: List[Tuple[float, float]] = []
            for i in range(n_sp + 1):
                u = min(p, i / 300.0)
                r_u = math.exp(-1.45 * u)
                sx_u = self._mx(x_eq + R_p * r_u * math.cos(2.0 * math.pi * 3.0 * u))
                sy_u = self._my(cy_p - 1.05 * r_u * np.sin(2.0 * np.pi * 3.0 * u))
                sp_pts.append((sx_u, sy_u))
            if len(sp_pts) > 1:
                d2x.line(sp_pts, fill=(*COL_GREEN, 255), width=7)

            cur_sx, cur_sy = sp_pts[-1]
            # STRICTLY VERTICAL golden projection line from pendulum bob (bx, by) straight down to phase point (cur_sx, cur_sy)!
            _draw_dashed_line_2x(d2x, bx, by, cur_sx, cur_sy, (*COL_GOLD, 245), width=5, dash_len=14, gap_len=10)
            # Horizontal projection to velocity axis v_x
            _draw_dashed_line_2x(d2x, cur_sx, cur_sy, px, cur_sy, (*COL_GREEN, 210), width=4, dash_len=10, gap_len=8)
            d2x.ellipse([cur_sx - 15, cur_sy - 15, cur_sx + 15, cur_sy + 15], fill=(*COL_GOLD, 255))

            # Bob circle m + live green velocity arrow v(t)
            r_bob = 54
            d2x.ellipse([bx - r_bob, by - r_bob, bx + r_bob, by + r_bob], fill=(*COL_CYAN, 255), outline=(224, 242, 254, 255), width=5)
            d2x.text((bx - 16, by - 22), "m", fill=(13, 17, 26, 255), font=self.f_bob)

            if abs(vy_phase) > 0.04:
                v_sign = 1.0 if vy_phase >= 0.0 else -1.0
                v_len = 55.0 + abs(vy_phase) * 195.0
                _draw_arrow_2x(
                    d2x,
                    bx + v_sign * (r_bob + 4),
                    by,
                    bx + v_sign * (r_bob + v_len),
                    by,
                    (*COL_GREEN, 255),
                    width=7,
                    head_len=24,
                )

            # Right half: Live Energy curves E_pot(t) (cyan) and E_kin(t) (green) traced up to current p
            ex0, ew, ey0, eh = 7.0, 4.6, 2.40, 2.55
            n_en = max(2, int(p * 300))
            epot_pts: List[Tuple[float, float]] = []
            ekin_pts: List[Tuple[float, float]] = []
            for i in range(n_en + 1):
                u = min(p, i / 300.0)
                et = math.exp(-2.2 * u)
                ep = et * (math.cos(2.0 * math.pi * 3.0 * u) ** 2)
                ek = et * (math.sin(2.0 * math.pi * 3.0 * u) ** 2)
                ex_u = self._mx(ex0 + u * ew)
                epot_pts.append((ex_u, self._my(ey0 + ep * eh)))
                ekin_pts.append((ex_u, self._my(ey0 + ek * eh)))
            if len(epot_pts) > 1:
                d2x.line(epot_pts, fill=(*COL_CYAN, 255), width=6)
                d2x.line(ekin_pts, fill=(*COL_GREEN, 255), width=6)
            d2x.ellipse([epot_pts[-1][0] - 12, epot_pts[-1][1] - 12, epot_pts[-1][0] + 12, epot_pts[-1][1] + 12], fill=(*COL_CYAN, 255))
            d2x.ellipse([ekin_pts[-1][0] - 12, ekin_pts[-1][1] - 12, ekin_pts[-1][0] + 12, ekin_pts[-1][1] + 12], fill=(*COL_GREEN, 255))

        else:
            # =========================================================================
            # SCENE 3: Driven Pendulum ABOVE + Time-Domain Resonance Build-Up BELOW
            # 100% 1-to-1 Amplitude & Position Match: bx == wx at every instant p!
            # Plus synchronized tracker on the Resonance Peak A(omega) on the right!
            # =========================================================================
            x_eq = 3.55
            y_piv = 6.22
            L_m = 1.75
            A_max = 1.65
            y_top = 3.82
            y_bot = 1.38
            H_t = y_top - y_bot

            # Growing resonance envelope A(p) under driving frequency omega = omega_0
            amp_now = A_max * (0.18 + 0.82 * (1.0 - math.exp(-2.5 * p)))
            phase = 2.0 * math.pi * 4.0 * p
            dx_m = amp_now * math.sin(phase)
            f_ext_val = math.cos(phase)  # Driving force in phase with velocity cos(phase)!

            bx_m = x_eq + dx_m
            sin_th = max(-0.95, min(0.95, dx_m / L_m))
            theta = math.asin(sin_th)
            by_m = y_piv - L_m * math.cos(theta)

            px, py = self._mx(x_eq), self._my(y_piv)
            bx, by = self._mx(bx_m), self._my(by_m)

            # Vertical equilibrium reference line from ceiling into time axis t
            _draw_dashed_line_2x(
                d2x, px, py, px, self._my(y_top), (100, 116, 139, 210), width=3, dash_len=14, gap_len=10
            )
            d2x.line([(px - 220, py), (px + 220, py)], fill=(148, 163, 184, 255), width=8)
            d2x.line([(px, py), (bx, by)], fill=(226, 232, 240, 255), width=6)

            # Live resonance build-up wave x(t) directly below the pendulum
            n_pts = max(2, int(p * 320))
            wave_pts: List[Tuple[float, float]] = []
            for i in range(n_pts + 1):
                u = min(p, i / 320.0)
                amp_u = A_max * (0.18 + 0.82 * (1.0 - math.exp(-2.5 * u)))
                dx_u = amp_u * math.sin(2.0 * math.pi * 4.0 * u)
                wx_u = self._mx(x_eq + dx_u)
                wy_u = self._my(y_top - u * H_t)
                wave_pts.append((wx_u, wy_u))
            if len(wave_pts) > 1:
                d2x.line(wave_pts, fill=(*COL_CYAN, 255), width=7)

            cur_wx, cur_wy = wave_pts[-1]
            # STRICTLY VERTICAL golden projection line from driven bob (bx, by) straight down to (cur_wx, cur_wy)!
            _draw_dashed_line_2x(d2x, bx, by, cur_wx, cur_wy, (*COL_GOLD, 245), width=5, dash_len=14, gap_len=10)
            d2x.line([(px, cur_wy), (cur_wx, cur_wy)], fill=(*COL_GOLD, 190), width=4)
            d2x.ellipse([cur_wx - 15, cur_wy - 15, cur_wx + 15, cur_wy + 15], fill=(*COL_GOLD, 255))

            # Current envelope width bracket [-amp_now, +amp_now] both near the bob and on the time graph
            left_env_x = self._mx(x_eq - amp_now)
            right_env_x = self._mx(x_eq + amp_now)
            d2x.ellipse([left_env_x - 9, cur_wy - 9, left_env_x + 9, cur_wy + 9], fill=(*COL_GOLD, 200))
            d2x.ellipse([right_env_x - 9, cur_wy - 9, right_env_x + 9, cur_wy + 9], fill=(*COL_GOLD, 200))

            # Bob circle m + golden external driving force vector F_ext(t) pushing in phase with velocity!
            r_bob = 54
            d2x.ellipse([bx - r_bob, by - r_bob, bx + r_bob, by + r_bob], fill=(*COL_CYAN, 255), outline=(224, 242, 254, 255), width=5)
            d2x.text((bx - 16, by - 22), "m", fill=(13, 17, 26, 255), font=self.f_bob)

            f_sign = 1.0 if f_ext_val >= 0.0 else -1.0
            f_len = 65.0 + abs(f_ext_val) * 165.0
            _draw_arrow_2x(
                d2x,
                bx + f_sign * (r_bob + 4),
                by,
                bx + f_sign * (r_bob + f_len),
                by,
                (*COL_GOLD, 255),
                width=7,
                head_len=24,
            )

            # Right half: Synchronized rising marker on the resonance peak omega = omega_0
            rx0, rw, ry0, rh = 7.05, 4.75, 1.75, 3.25
            res_x = self._mx(rx0 + (1.0 / 2.2) * rw)
            # Height on the resonance peak grows identically to (amp_now / A_max) * rh!
            cur_peak_y = self._my(ry0 + (amp_now / A_max) * rh)
            base_peak_y = self._my(ry0)
            _draw_arrow_2x(d2x, res_x, base_peak_y, res_x, cur_peak_y, (*COL_GOLD, 255), width=7, head_len=24)
            d2x.ellipse([res_x - 15, cur_peak_y - 15, res_x + 15, cur_peak_y + 15], fill=(*COL_GOLD, 255))

        # Downsample 2x overlay (2560x1440) -> 1280x720 with LANCZOS and composite onto base
        ov1x = ov2x.resize((1280, 720), Image.Resampling.LANCZOS)
        base_rgba = base.convert("RGBA")
        base_rgba.alpha_composite(ov1x)

        final_rgb = base_rgba.convert("RGB")
        _draw_wildmathing_subtitles(final_rgb, scene, p, self.f_sub)
        return final_rgb.tobytes()


# Typographic trailing prepositions, conjunctions, and particles that must not dangle at line or cue ends
_DANGLING_WORDS = {
    # Russian prepositions, conjunctions, and particles (Unicode-escaped for strict ASCII code hygiene)
    "\u0432", "\u0438", "\u043a", "\u043e", "\u0441", "\u0443", "\u043e\u0442", "\u0434\u043e",
    "\u043f\u043e", "\u043d\u0430", "\u0437\u0430", "\u0438\u0437", "\u043e\u0431", "\u0441\u043e",
    "\u043a\u043e", "\u0432\u043e", "\u0434\u043b\u044f", "\u043f\u0440\u0438", "\u043f\u0440\u043e",
    "\u0431\u0435\u0437", "\u043d\u0430\u0434", "\u043f\u043e\u0434", "\u043f\u0440\u0435\u0434",
    "\u0447\u0435\u0440\u0435\u0437", "\u043d\u0435", "\u043d\u0438", "\u0436\u0435", "\u043b\u0438",
    "\u0431\u044b", "\u043d\u043e", "\u0434\u0430", "\u0430", "\u0438\u043b\u0438", "\u0447\u0442\u043e",
    "\u043a\u0430\u043a",
    # English prepositions and conjunctions
    "a", "an", "the", "of", "in", "to", "for", "and", "or", "with", "at", "by", "on",
    # Mathematical and typographical symbols
    "=", "+", "-", "\u2014", "\u2013",
}


def _clean_sub_word(w: str) -> str:
    """Strip trailing punctuation, quotes, and dashes for robust dangling particle checks."""
    return re.sub(r"[,.:;!?()\"\u00ab\u00bb\u2014\u2013]+$", "", str(w)).lower()


def _align_captions_to_wav(captions: object, wav_path: Path) -> None:
    """
    Build clause-aligned subtitle pages and WordTiming intervals locked directly to
    the acoustic silence pauses and syllable cadence of `wav_path`.
    Each sentence or major clause sits on its own clean 2-line SubtitlePage, and
    clause transitions occur inside the actual spoken pauses of the WAV waveform.
    """
    import wave
    from src.flow_bridge import SubtitlePage, WordTiming

    all_words: List[WordTiming] = getattr(captions, "all_words", None) or []
    if not all_words:
        return

    dur_ms = int(getattr(captions, "duration_ms", 5000))
    first_ms = 120
    last_ms = max(first_ms + 500, dur_ms - 120)
    pause_runs: List[Tuple[int, int, int]] = []

    try:
        if wav_path.is_file() and wav_path.stat().st_size > 1000:
            with wave.open(str(wav_path), "rb") as wf:
                sr = wf.getframerate()
                nchannels = wf.getnchannels()
                sampwidth = wf.getsampwidth()
                raw = wf.readframes(wf.getnframes())
            if sampwidth == 2:
                pcm_raw = np.frombuffer(raw, dtype=np.int16)
                if nchannels > 1:
                    pcm_raw = pcm_raw.reshape(-1, nchannels)[:, 0]
                pcm = pcm_raw.astype(np.float32)
            else:
                pcm = np.frombuffer(raw, dtype=np.int8).astype(np.float32) * 256.0

            dur_ms = int(round((pcm.size / float(sr)) * 1000.0))
            setattr(captions, "duration_ms", dur_ms)

            # Continuous Schmitt-trigger VAD speech envelope projection
            # Hop = 10ms, Window = 20ms
            hop_len = max(1, int(sr * 0.010))
            win_len = max(1, int(sr * 0.020))
            if pcm.size >= win_len:
                n_w = (pcm.size - win_len) // hop_len + 1
                rms = np.zeros(n_w, dtype=np.float32)
                for i in range(n_w):
                    chunk = pcm[i * hop_len : i * hop_len + win_len]
                    rms[i] = float(np.sqrt(np.mean(chunk * chunk)))

                max_amp = float(np.max(rms)) if rms.size > 0 else 0.0
                th_high = max(350.0, 0.15 * max_amp)
                th_low = max(150.0, 0.05 * max_amp)

                # Schmitt-trigger state machine
                is_voiced = np.zeros(n_w, dtype=bool)
                st = False
                for i, r in enumerate(rms):
                    if not st and r >= th_high:
                        st = True
                    elif st and r <= th_low:
                        st = False
                    is_voiced[i] = st

                # Extract raw continuous voiced blocks
                diff = np.diff(is_voiced.astype(np.int32))
                starts = list(np.where(diff == 1)[0] + 1)
                ends = list(np.where(diff == -1)[0] + 1)
                if n_w > 0 and is_voiced[0]:
                    starts.insert(0, 0)
                if n_w > 0 and is_voiced[-1]:
                    ends.append(n_w)

                raw_bursts = [
                    (s * 10, min(dur_ms, e * 10))
                    for s, e in zip(starts, ends)
                    if (e - s) * 10 >= 80
                ]

                if raw_bursts:
                    # Bridge short silence gaps (< 200ms)
                    merged_voiced: List[Tuple[int, int]] = [raw_bursts[0]]
                    for cur_s, cur_e in raw_bursts[1:]:
                        prev_s, prev_e = merged_voiced[-1]
                        if cur_s - prev_e < 200:
                            merged_voiced[-1] = (prev_s, cur_e)
                        else:
                            merged_voiced.append((cur_s, cur_e))

                    first_ms = max(20, merged_voiced[0][0])
                    last_ms = min(dur_ms - 20, merged_voiced[-1][1])

                    # Extract acoustic silence pauses between voiced blocks
                    for idx_b in range(len(merged_voiced) - 1):
                        ps = merged_voiced[idx_b][1]
                        pe = merged_voiced[idx_b + 1][0]
                        pdur = pe - ps
                        if pdur >= 90:
                            pause_runs.append((ps, pe, pdur))
    except Exception:
        pass

    # Group words into natural clauses (splitting at '.', '!', '?', ':', ';', or ',' when clause >= 10 words)
    raw_clauses: List[List[WordTiming]] = []
    cur_cl: List[WordTiming] = []
    for wt in all_words:
        cur_cl.append(wt)
        w_txt = wt.word
        is_sent_end = w_txt.endswith(".") or w_txt.endswith("!") or w_txt.endswith("?")
        is_semi_end = w_txt.endswith(":") or w_txt.endswith(";")
        is_comma_end = w_txt.endswith(",")
        if is_sent_end or (is_semi_end and len(cur_cl) >= 6) or (is_comma_end and len(cur_cl) >= 10):
            raw_clauses.append(cur_cl)
            cur_cl = []
    if cur_cl:
        if raw_clauses and len(cur_cl) < 5:
            raw_clauses[-1].extend(cur_cl)
        else:
            raw_clauses.append(cur_cl)

    # Split any long clause (> 17 words) at an internal punctuation mark or balanced midpoint
    clauses: List[List[WordTiming]] = []
    for cl in raw_clauses:
        if len(cl) > 17:
            mid = len(cl) // 2
            punct_candidates = [
                idx + 1
                for idx in range(3, len(cl) - 4)
                if cl[idx].word.endswith((",", ";", ":", "\u2014", "\u2013"))
            ]
            if punct_candidates:
                split_k = min(punct_candidates, key=lambda k: abs(k - mid))
            else:
                split_k = mid
                while split_k > 3 and _clean_sub_word(cl[split_k - 1].word) in _DANGLING_WORDS:
                    split_k -= 1
            clauses.append(cl[:split_k])
            clauses.append(cl[split_k:])
        else:
            clauses.append(cl)

    vowels = set("\u0430\u0435\u0451\u0438\u043e\u0443\u044b\u044d\u044e\u044faeiouy")

    def _word_syl(w: str) -> float:
        w_low = w.lower()
        nv = sum(1 for c in w_low if c in vowels)
        nl = sum(1 for c in w_low if c.isalpha())
        return max(1.0, float(nv) + float(max(0, nl - nv)) * 0.20)

    clause_syls = [sum(_word_syl(wt.word) for wt in cl) for cl in clauses]
    tot_syls = max(1.0, sum(clause_syls))

    # Match each inter-clause boundary to the closest prominent acoustic pause run in `pause_runs`
    n_cl = len(clauses)
    bounds: List[Tuple[int, int]] = []  # (pause_start_ms, pause_end_ms) between clause k and k+1
    cum_syl = 0.0
    used_pauses = set()
    min_allowed_ps = first_ms + 100
    for k in range(n_cl - 1):
        cum_syl += clause_syls[k]
        expected_ms = first_ms + (cum_syl / tot_syls) * (last_ms - first_ms)
        last_w = clauses[k][-1].word
        is_major = last_w.endswith(".") or last_w.endswith("!") or last_w.endswith(":")
        best_idx = -1
        best_score = -1e9
        for p_idx, (ps, pe, pdur) in enumerate(pause_runs):
            if p_idx in used_pauses or ps < min_allowed_ps:
                continue
            p_mid = 0.5 * (ps + pe)
            dist = abs(p_mid - expected_ms)
            max_dist = 2400.0 if is_major else 1600.0
            if dist <= max_dist:
                score = float(pdur) * (2.5 if is_major else 1.2) - dist * 0.18
                if score > best_score:
                    best_score = score
                    best_idx = p_idx
        if best_idx >= 0:
            used_pauses.add(best_idx)
            ps, pe, _ = pause_runs[best_idx]
            bounds.append((ps, pe))
            min_allowed_ps = pe + 80
        else:
            pad = 220 if is_major else 90
            b_ms = int(round(max(float(min_allowed_ps + pad // 2), expected_ms)))
            bounds.append((max(first_ms, b_ms - pad // 2), min(last_ms, b_ms + pad // 2)))
            min_allowed_ps = bounds[-1][1] + 80

    # Ensure bounds are strictly monotonic
    clean_bounds: List[Tuple[int, int]] = []
    prev_t = first_ms + 100
    for ps, pe in bounds:
        cs = max(prev_t, ps)
        ce = max(cs + 40, pe)
        clean_bounds.append((cs, ce))
        prev_t = ce + 100

    _PAIR_MERGES = {
        ("\u043e\u0434\u0438\u043d", "\u043e\u0434\u0438\u043d"): "1.1",
        ("\u043e\u0434\u0438\u043d", "\u0434\u0432\u0430"): "1.2",
        ("\u043e\u0434\u0438\u043d", "\u0442\u0440\u0438"): "1.3",
        ("\u043e\u0434\u0438\u043d", "\u0447\u0435\u0442\u044b\u0440\u0435"): "1.4",
        ("\u0434\u0432\u0430", "\u043e\u0434\u0438\u043d"): "2.1",
        ("\u0434\u0432\u0430", "\u0434\u0432\u0430"): "2.2",
        ("\u0434\u0432\u0430", "\u0442\u0440\u0438"): "2.3",
        ("\u0434\u0432\u0430", "\u0447\u0435\u0442\u044b\u0440\u0435"): "2.4",
        ("\u0442\u0440\u0438", "\u043e\u0434\u0438\u043d"): "3.1",
        ("\u0442\u0440\u0438", "\u0434\u0432\u0430"): "3.2",
        ("\u0442\u0440\u0438", "\u0442\u0440\u0438"): "3.3",
        ("\u0442\u0440\u0438", "\u0447\u0435\u0442\u044b\u0440\u0435"): "3.4",
        ("\u0447\u0435\u0442\u044b\u0440\u0435", "\u043e\u0434\u0438\u043d"): "4.1",
        ("\u0447\u0435\u0442\u044b\u0440\u0435", "\u0434\u0432\u0430"): "4.2",
        ("\u0447\u0435\u0442\u044b\u0440\u0435", "\u0442\u0440\u0438"): "4.3",
        ("\u0447\u0435\u0442\u044b\u0440\u0435", "\u0447\u0435\u0442\u044b\u0440\u0435"): "4.4",
        ("\u0443\u0430\u043d", "\u0445\u043e\u0442"): "One-Hot",
        ("\u0442\u0440\u0438", "\u0441\u0438\u0433\u043c\u0430"): "3\u03c3",
    }

    # Build SubtitlePages and WordTimings for each clause
    new_pages: List[SubtitlePage] = []
    new_all_words: List[WordTiming] = []
    for k, cl in enumerate(clauses):
        cl_start = first_ms if k == 0 else clean_bounds[k - 1][1]
        cl_end = last_ms if k == n_cl - 1 else clean_bounds[k][0]
        n_words = len(cl)
        cl_span = max(50.0 * n_words, float(cl_end - cl_start))
        w_syls = [_word_syl(wt.word) for wt in cl]
        cl_tot = max(1.0, sum(w_syls))
        avail_span = max(0.0, cl_span - 50.0 * n_words)
        cur_t = float(cl_start)
        for idx_w, (wt, ws) in enumerate(zip(cl, w_syls)):
            w_extra = (ws / cl_tot) * avail_span
            wd = 50.0 + w_extra
            wt.start_ms = int(round(cur_t))
            if idx_w == n_words - 1:
                wt.end_ms = max(wt.start_ms + 50, int(round(cl_end)))
                cur_t = float(wt.end_ms)
            else:
                wt.end_ms = max(wt.start_ms + 50, int(round(cur_t + wd)))
                cur_t = float(wt.end_ms)

        merged_cl: List[WordTiming] = []
        idx_m = 0
        while idx_m < len(cl):
            if idx_m + 1 < len(cl):
                w0_clean = _clean_sub_word(cl[idx_m].word)
                w1_raw = cl[idx_m + 1].word
                w1_clean = _clean_sub_word(w1_raw)
                repl = _PAIR_MERGES.get((w0_clean, w1_clean))
                if repl is not None:
                    trail = w1_raw[len(w1_clean):] if len(w1_raw) > len(w1_clean) else ""
                    cl[idx_m].word = repl + trail
                    cl[idx_m].end_ms = cl[idx_m + 1].end_ms
                    merged_cl.append(cl[idx_m])
                    idx_m += 2
                    continue
            merged_cl.append(cl[idx_m])
            idx_m += 1
        cl = merged_cl

        if len(cl) <= 6:
            line0 = [wt.word for wt in cl]
            line1 = []
            mid = len(cl)
        else:
            mid = max(1, (len(cl) + 1) // 2)
            while mid > 1 and (
                _clean_sub_word(cl[mid - 1].word) in _DANGLING_WORDS
                or (len(_clean_sub_word(cl[mid - 1].word)) <= 2 and not cl[mid - 1].word.endswith((",", ".", ":")))
            ):
                mid -= 1
            line0 = [wt.word for wt in cl[:mid]]
            line1 = [wt.word for wt in cl[mid:]]
        for li_idx, wt in enumerate(cl):
            wt.word_index = len(new_all_words)
            wt.page_index = k
            wt.line_index = 0 if li_idx < mid else 1
            new_all_words.append(wt)
        new_pages.append(
            SubtitlePage(
                page_index=k,
                start_ms=cl[0].start_ms,
                end_ms=cl[-1].end_ms,
                lines=[line0, line1] if line1 else [line0],
                words=cl,
            )
        )

    # Final strict monotonic non-overlapping invariant enforcement
    for idx_w in range(len(new_all_words)):
        wt = new_all_words[idx_w]
        if wt.end_ms < wt.start_ms + 50:
            wt.end_ms = wt.start_ms + 50
        if idx_w + 1 < len(new_all_words):
            next_wt = new_all_words[idx_w + 1]
            if next_wt.start_ms < wt.end_ms:
                next_wt.start_ms = wt.end_ms
            if next_wt.end_ms < next_wt.start_ms + 50:
                next_wt.end_ms = next_wt.start_ms + 50

    # Ensure SubtitlePage intervals enclose words without backwards drift
    for page in new_pages:
        if page.words:
            page.start_ms = page.words[0].start_ms
            page.end_ms = page.words[-1].end_ms

    setattr(captions, "all_words", new_all_words)
    setattr(captions, "pages", new_pages)


async def run_simple_demo() -> dict:
    out_dir = ROOT_DIR / "output" / "simple_flow_demo"
    out_dir.mkdir(parents=True, exist_ok=True)

    topic_ru = (
        "\u041a\u043e\u043b\u0435\u0431\u0430\u043d\u0438\u044f \u043c\u0430\u0442\u0435\u043c\u0430\u0442\u0438\u0447\u0435\u0441\u043a\u043e\u0433\u043e "
        "\u043c\u0430\u044f\u0442\u043d\u0438\u043a\u0430: \u0437\u0430\u0442\u0443\u0445\u0430\u043d\u0438\u0435, \u044d\u043d\u0435\u0440\u0433\u0438\u044f \u0438 \u0440\u0435\u0437\u043e\u043d\u0430\u043d\u0441"
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
        "\u0420\u0430\u0441\u0441\u043c\u043e\u0442\u0440\u0438\u043c \u0441\u0432\u043e\u0431\u043e\u0434\u043d\u044b\u0435 \u0437\u0430\u0442\u0443\u0445\u0430\u044e\u0449\u0438\u0435 \u043a\u043e\u043b\u0435\u0431\u0430\u043d\u0438\u044f \u043c\u0430\u044f\u0442\u043d\u0438\u043a\u0430. "
        "\u0412\u043e\u0437\u0432\u0440\u0430\u0449\u0430\u044e\u0449\u0430\u044f \u0441\u0438\u043b\u0430 \u0442\u044f\u043d\u0435\u0442 \u0433\u0440\u0443\u0437 \u043a \u043f\u043e\u043b\u043e\u0436\u0435\u043d\u0438\u044e \u0440\u0430\u0432\u043d\u043e\u0432\u0435\u0441\u0438\u044f, \u0430 \u0441\u0438\u043b\u0430 \u0442\u0440\u0435\u043d\u0438\u044f \u0442\u043e\u0440\u043c\u043e\u0437\u0438\u0442 \u0434\u0432\u0438\u0436\u0435\u043d\u0438\u0435. "
        "\u041d\u0430 \u0433\u0440\u0430\u0444\u0438\u043a\u0435 \u043f\u043e\u0434 \u043c\u0430\u044f\u0442\u043d\u0438\u043a\u043e\u043c \u0432\u0438\u0434\u043d\u043e, \u043a\u0430\u043a \u0440\u0430\u0437\u043c\u0430\u0445 \u043a\u043e\u043b\u0435\u0431\u0430\u043d\u0438\u0439 \u0441\u043e \u0432\u0440\u0435\u043c\u0435\u043d\u0435\u043c \u043f\u043b\u0430\u0432\u043d\u043e \u0443\u0431\u044b\u0432\u0430\u0435\u0442."
    )
    s2_text = (
        "\u041f\u0440\u043e\u0441\u043b\u0435\u0434\u0438\u043c \u0437\u0430 \u0441\u043a\u043e\u0440\u043e\u0441\u0442\u044c\u044e \u0438 \u044d\u043d\u0435\u0440\u0433\u0438\u0435\u0439 \u043c\u0430\u044f\u0442\u043d\u0438\u043a\u0430. "
        "\u0412 \u043a\u0440\u0430\u0439\u043d\u0438\u0445 \u0442\u043e\u0447\u043a\u0430\u0445 \u0433\u0440\u0443\u0437 \u043d\u0430 \u043c\u0433\u043d\u043e\u0432\u0435\u043d\u0438\u0435 \u043e\u0441\u0442\u0430\u043d\u0430\u0432\u043b\u0438\u0432\u0430\u0435\u0442\u0441\u044f, \u0438 \u0435\u0433\u043e \u043f\u043e\u0442\u0435\u043d\u0446\u0438\u0430\u043b\u044c\u043d\u0430\u044f \u044d\u043d\u0435\u0440\u0433\u0438\u044f \u043c\u0430\u043a\u0441\u0438\u043c\u0430\u043b\u044c\u043d\u0430. "
        "\u041f\u0440\u0438 \u043f\u0440\u043e\u0445\u043e\u0436\u0434\u0435\u043d\u0438\u0438 \u0447\u0435\u0440\u0435\u0437 \u0440\u0430\u0432\u043d\u043e\u0432\u0435\u0441\u0438\u0435 \u0441\u043a\u043e\u0440\u043e\u0441\u0442\u044c \u0438 \u043a\u0438\u043d\u0435\u0442\u0438\u0447\u0435\u0441\u043a\u0430\u044f \u044d\u043d\u0435\u0440\u0433\u0438\u044f \u0434\u043e\u0441\u0442\u0438\u0433\u0430\u044e\u0442 \u043c\u0430\u043a\u0441\u0438\u043c\u0443\u043c\u0430, \u043d\u043e \u0438\u0437-\u0437\u0430 \u0442\u0440\u0435\u043d\u0438\u044f \u043f\u043e\u043b\u043d\u0430\u044f \u044d\u043d\u0435\u0440\u0433\u0438\u044f \u043f\u043e\u0441\u0442\u0435\u043f\u0435\u043d\u043d\u043e \u0443\u0431\u044b\u0432\u0430\u0435\u0442."
    )
    s3_text = (
        "\u0422\u0435\u043f\u0435\u0440\u044c \u043f\u0440\u0438\u043b\u043e\u0436\u0438\u043c \u043a \u043c\u0430\u044f\u0442\u043d\u0438\u043a\u0443 \u0432\u043d\u0435\u0448\u043d\u044e\u044e \u043f\u0435\u0440\u0438\u043e\u0434\u0438\u0447\u0435\u0441\u043a\u0443\u044e \u0441\u0438\u043b\u0443, \u043a\u043e\u0442\u043e\u0440\u0430\u044f \u043f\u043e\u0434\u0442\u0430\u043b\u043a\u0438\u0432\u0430\u0435\u0442 \u0433\u0440\u0443\u0437 \u0432 \u0442\u0430\u043a\u0442 \u0435\u0433\u043e \u0441\u043e\u0431\u0441\u0442\u0432\u0435\u043d\u043d\u044b\u043c \u043a\u043e\u043b\u0435\u0431\u0430\u043d\u0438\u044f\u043c. "
        "\u0412\u043e\u0437\u043d\u0438\u043a\u0430\u0435\u0442 \u044f\u0432\u043b\u0435\u043d\u0438\u0435 \u0440\u0435\u0437\u043e\u043d\u0430\u043d\u0441\u0430: \u0433\u0440\u0430\u0444\u0438\u043a \u043f\u043e\u0434 \u043c\u0430\u044f\u0442\u043d\u0438\u043a\u043e\u043c \u043d\u0430\u0433\u043b\u044f\u0434\u043d\u043e \u043f\u043e\u043a\u0430\u0437\u044b\u0432\u0430\u0435\u0442, \u043a\u0430\u043a \u0441 \u043a\u0430\u0436\u0434\u044b\u043c \u043a\u0430\u0447\u0430\u043d\u0438\u0435\u043c \u0430\u043c\u043f\u043b\u0438\u0442\u0443\u0434\u0430 \u0432\u043e\u0437\u0440\u0430\u0441\u0442\u0430\u0435\u0442 \u0434\u043e \u043c\u0430\u043a\u0441\u0438\u043c\u0430\u043b\u044c\u043d\u043e\u0433\u043e \u043f\u0438\u043a\u0430."
    )

    custom_scenes_data = [
        {
            "title": "\u0421\u0446\u0435\u043d\u0430 1: \u0417\u0430\u0442\u0443\u0445\u0430\u044e\u0449\u0438\u0435 \u043a\u043e\u043b\u0435\u0431\u0430\u043d\u0438\u044f \u0438 \u0433\u0440\u0430\u0444\u0438\u043a \u043f\u043e\u0434 \u043c\u0430\u044f\u0442\u043d\u0438\u043a\u043e\u043c",
            "narration_text": s1_text,
            "tts_narration_text": s1_text,
        },
        {
            "title": "\u0421\u0446\u0435\u043d\u0430 2: \u0421\u0432\u044f\u0437\u044c \u0441\u043a\u043e\u0440\u043e\u0441\u0442\u0438 \u0441 \u043e\u0442\u043a\u043b\u043e\u043d\u0435\u043d\u0438\u0435\u043c \u0438 \u044d\u043d\u0435\u0440\u0433\u0438\u044f",
            "narration_text": s2_text,
            "tts_narration_text": s2_text,
        },
        {
            "title": "\u0421\u0446\u0435\u043d\u0430 3: \u0420\u0435\u0437\u043e\u043d\u0430\u043d\u0441\u043d\u0430\u044f \u0440\u0430\u0441\u043a\u0430\u0447\u043a\u0430 \u043c\u0430\u044f\u0442\u043d\u0438\u043a\u0430 \u0438 \u043f\u0438\u043a \u0410\u0427\u0425",
            "narration_text": s3_text,
            "tts_narration_text": s3_text,
        },
    ]

    for sc, custom in zip(project.scenes, custom_scenes_data):
        sc.title = custom["title"]
        sc.narration_text = custom["narration_text"]
        sc.tts_narration_text = custom["tts_narration_text"]

    wm_renderer = WildMathingPhysicsRenderer()
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
            sc_out = out_dir / f"scene_{sc.scene_number:02d}_pendulum_demo.mp4"
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
                raw_rgb = wm_renderer.render_frame(sc, f_idx, total_frames)
                proc.stdin.write(raw_rgb)
            proc.stdin.close()
            proc.wait(timeout=120)
            scene_mp4_paths.append(sc_out)

    # Concatenate the 3 scenes into simple_flow_demo.mp4
    demo_mp4 = out_dir / "simple_flow_demo.mp4"
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
    (out_dir / "simple_flow_demo.srt").write_text(srt_text, encoding="utf-8")
    (out_dir / "simple_flow_demo.vtt").write_text(vtt_text, encoding="utf-8")

    # Build a 3x2 contact sheet (t=25% and t=75% of each scene)
    sheet_w, sheet_h = 1280, 1080
    sheet = Image.new("RGB", (sheet_w, sheet_h), (10, 15, 28))
    thumb_w, thumb_h = 620, 348
    for s_idx, sc in enumerate(project.scenes):
        for col_idx, ratio in enumerate((0.25, 0.75)):
            tot_f = 96
            f_idx = int(tot_f * ratio)
            raw = wm_renderer.render_frame(sc, f_idx, tot_f)
            frame_im = Image.frombytes("RGB", (1280, 720), raw)
            if col_idx == 1:
                frame_im.save(out_dir / f"wildmathing_scene_{sc.scene_number:02d}_keyframe.png")
            thumb = frame_im.resize((thumb_w, thumb_h), Image.Resampling.LANCZOS)
            x_pos = 14 + col_idx * (thumb_w + 12)
            y_pos = 10 + s_idx * (thumb_h + 8)
            sheet.paste(thumb, (x_pos, y_pos))

    contact_sheet_path = out_dir / "contact_sheet.png"
    sheet.save(contact_sheet_path)

    manifest = {
        "style": "@WildMathing / Manim Vertical-Projection 1:1 Physics",
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
    asyncio.run(run_simple_demo())
