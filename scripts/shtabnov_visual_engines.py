#!/usr/bin/env python3
"""
Zero-Jitter Hardware Schematic, Pipeline, Memory-Map & Curve-Dot Visual Engines
for Shtabnov A. R. Variant 19 DSP Coursework Defense Videos (1280x720 HD @ 24 fps).

Key visual design principles:
1. NO vertical line dividing static diagrams or schematic blocks.
2. Whole-block sequential spotlighting (`focus_zones`): each IC, pipeline stage,
   cipher slot, register field, or bus line illuminates as a complete unit with an
   anti-aliased glowing rounded highlight border and corner accents.
3. Curve-following moving dots (`curve_dots`): on coordinate plots, curves reveal
   smoothly inside the plot frame only (0.0 px shake) while glowing dots ride
   directly along the mathematical curves `y(u)` with vertical stems to the axis.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image, ImageDraw

from scripts.render_dsp_cheatsheet_videos import (
    _draw_right_info_panel,
    _fig_to_rgb,
    _new_base_fig,
)
from scripts.render_simple_flow_demo import (
    COL_CYAN,
    COL_GOLD,
    COL_GREEN,
    COL_RED,
    _draw_wildmathing_subtitles,
)
from src.flow_bridge import FlowScene

COL_PURPLE: Tuple[int, int, int] = (192, 132, 252)


def _hex_to_rgb(h: str) -> Tuple[int, int, int]:
    s = h.lstrip("#")
    return int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16)


def _draw_hw_box(
    ax: plt.Axes,
    x: float,
    y: float,
    w: float,
    h: float,
    title: str,
    sub: str,
    edge_col: str,
    face_col: str = "#131C31",
    alpha: float = 1.0,
    fs_title: float = 8.4,
    fs_sub: float = 7.2,
    lw: float = 1.5,
    focus_list: Optional[List[Tuple[float, float, float, float, Tuple[int, int, int]]]] = None,
) -> None:
    """Draw a rounded hardware IC / pipeline block and optionally register it as a focus zone."""
    patch = mpatches.FancyBboxPatch(
        (x, y),
        w,
        h,
        boxstyle="round,pad=0.04,rounding_size=0.10",
        facecolor=face_col,
        edgecolor=edge_col,
        linewidth=lw,
        alpha=alpha,
        zorder=3,
    )
    ax.add_patch(patch)
    if sub:
        ax.text(
            x + w * 0.5,
            y + h * 0.68,
            title,
            ha="center",
            va="center",
            color="#F8FAFC",
            fontsize=fs_title,
            weight="bold",
            alpha=alpha,
            zorder=4,
        )
        ax.text(
            x + w * 0.5,
            y + h * 0.30,
            sub,
            ha="center",
            va="center",
            color="#CBD5E1",
            fontsize=fs_sub,
            alpha=alpha,
            zorder=4,
        )
    else:
        ax.text(
            x + w * 0.5,
            y + h * 0.50,
            title,
            ha="center",
            va="center",
            color="#F8FAFC",
            fontsize=fs_title,
            weight="bold",
            alpha=alpha,
            zorder=4,
        )
    if focus_list is not None:
        focus_list.append((x, y, w, h, _hex_to_rgb(edge_col)))


def _draw_bus_arrow(
    ax: plt.Axes,
    x0: float,
    y0: float,
    x1: float,
    y1: float,
    col: str,
    label: str = "",
    alpha: float = 1.0,
    lw: float = 1.6,
    bidir: bool = False,
    ly_off: float = 0.11,
    focus_list: Optional[List[Tuple[float, float, float, float, Tuple[int, int, int]]]] = None,
) -> None:
    """Draw a clean anti-aliased schematic bus arrow and optionally register its band as a focus zone."""
    style = "<->" if bidir else "->"
    ax.annotate(
        "",
        xy=(x1, y1),
        xytext=(x0, y0),
        arrowprops=dict(arrowstyle=style, color=col, lw=lw, alpha=alpha, shrinkA=0, shrinkB=0),
        zorder=2,
    )
    if label:
        ax.text(
            0.5 * (x0 + x1),
            0.5 * (y0 + y1) + ly_off,
            label,
            ha="center",
            va="center",
            color=col,
            fontsize=7.3,
            weight="bold",
            alpha=alpha,
            zorder=4,
        )
    if focus_list is not None:
        bx = min(x0, x1)
        bw = abs(x1 - x0)
        by = min(y0, y1) - 0.10
        bh = max(0.34, abs(y1 - y0) + 0.34)
        focus_list.append((bx, by, bw, bh, _hex_to_rgb(col)))


def _draw_plot_box(
    ax: plt.Axes,
    x0: float,
    y0: float,
    w: float,
    h: float,
    title: str,
    title_col: str,
    xlab: str = "",
    y_zero_frac: float = 0.50,
) -> None:
    """Draw a clean bounded coordinate frame for a non-shaking plot panel."""
    rect = mpatches.FancyBboxPatch(
        (x0, y0),
        w,
        h,
        boxstyle="round,pad=0.02,rounding_size=0.08",
        facecolor="#0F172A",
        edgecolor="#1E293B",
        linewidth=1.1,
        zorder=1,
    )
    ax.add_patch(rect)
    y_axis = y0 + h * y_zero_frac
    ax.plot([x0 + 0.10, x0 + w - 0.10], [y_axis, y_axis], color="#334155", lw=0.9, zorder=2)
    ax.text(x0 + 0.12, y0 + h - 0.18, title, color=title_col, fontsize=8.6, weight="bold", va="center", zorder=4)
    if xlab:
        ax.text(x0 + w - 0.14, y0 + 0.14, xlab, color="#94A3B8", fontsize=7.6, ha="right", va="center", zorder=4)


def _draw_scene_mode(ax: plt.Axes, mode: str, lit: bool) -> Dict[str, Any]:
    """
    Draw the left-hand visual canvas (`x in [0.65, 7.25]`, `y in [1.55, 6.35]`)
    for either the base blueprint (`lit=False`) or active (`lit=True`) state.
    Returns `{"focus_zones": ..., "plot_reveal": ..., "curve_dots": ..., "packets": ...}`.
    """
    a_val = 1.0 if lit else 0.36
    lw_val = 2.0 if lit else 1.1
    face_hi = "#172542" if lit else "#111827"
    focus_zones: List[Tuple[float, float, float, float, Tuple[int, int, int]]] = []
    curve_dots: List[Tuple[np.ndarray, np.ndarray, Tuple[int, int, int], float]] = []
    packets: List[Tuple[float, float, float, float, Tuple[int, int, int]]] = []
    plot_reveal: Optional[Tuple[float, float, float, float]] = None

    if mode == "cipher_isolation":
        ax.text(0.75, 6.20, "\u041f\u043e\u0437\u0438\u0446\u0438\u043e\u043d\u043d\u044b\u0439 \u0434\u0435\u0448\u0438\u0444\u0440\u0430\u0442\u043e\u0440 \u0448\u0438\u0444\u0440\u0430 \u0412\u0430\u0440\u0438\u0430\u043d\u0442\u0430 19 (\u0441\u0442\u0440. 4, 13 \u041f\u0417):", color="#38BDF8", fontsize=8.8, weight="bold")
        slots = [
            ("\u0410", "cos(x)", "#38BDF8"),
            ("1", "5\u00b710\u207b\u2074", "#38BDF8"),
            ("3", "10 \u043a\u0413\u0446", "#38BDF8"),
            ("2", "\u0410\u0426\u041f \u043f\u043e\u0441\u043b.", "#4ADE80"),
            ("2", "\u0426\u0410\u041f \u043f\u043e\u0441\u043b.", "#4ADE80"),
            ("0", "\u041f\u0417\u0423 \u043d\u0435\u0442", "#FBBF24"),
            ("2", "2 \u0426\u041e\u0421", "#FBBF24"),
            ("9", "\u041a\u043b\u0430\u0432+\u0418\u043d\u0434", "#F87171"),
        ]
        for idx, (sym, desc, col) in enumerate(slots):
            sx = 0.72 + idx * 0.81
            _draw_hw_box(ax, sx, 5.15, 0.75, 0.88, sym, desc, col, face_hi, alpha=a_val, fs_title=9.8, fs_sub=6.7, lw=lw_val, focus_list=focus_zones)

        ax.text(0.75, 4.82, "\u0421\u0442\u0440\u0443\u043a\u0442\u0443\u0440\u043d\u0430\u044f \u0441\u0445\u0435\u043c\u0430 \u0412\u0430\u0440\u0438\u0430\u043d\u0442\u0430 2 (\u0440\u0438\u0441. 2.2 \u0441\u0442\u0440. 28 \u041f\u0417 \u0438 \u0447\u0435\u0440\u0442\u0451\u0436 \u041a\u041d\u0424\u0423.411711.001 \u042d2):", color="#4ADE80", fontsize=8.6, weight="bold")
        _draw_hw_box(ax, 0.72, 3.45, 1.35, 1.10, "SB1 + DD4", "ADM708 (POR)\nWDT 1.6 \u0441", "#FBBF24", face_hi, alpha=a_val, fs_title=7.8, fs_sub=6.6, lw=lw_val, focus_list=focus_zones)
        _draw_hw_box(ax, 0.72, 1.75, 1.35, 1.10, "HG1 + X6", "\u0418\u043d\u0434. PC0..6\n\u041a\u043b\u0430\u0432. SPI1", "#F87171", face_hi, alpha=a_val, fs_title=7.8, fs_sub=6.6, lw=lw_val, focus_list=focus_zones)
        _draw_hw_box(ax, 2.45, 2.35, 1.50, 1.65, "HOST: DD3\nSTM32F103", "72 \u041c\u0413\u0446 (ZQ1)\nSPI2 Master\nPA3=RST_DSP", "#38BDF8", face_hi, alpha=a_val, fs_title=8.0, fs_sub=6.6, lw=lw_val, focus_list=focus_zones)
        _draw_hw_box(ax, 4.38, 3.40, 1.38, 1.18, "DD1: \u0426\u041e\u0421 1\nADSP-21369", "400 \u041c\u0413\u0446, 2\u041c\u0431\nPA1=CS1, PA2", "#4ADE80", face_hi, alpha=a_val, fs_title=7.8, fs_sub=6.5, lw=lw_val, focus_list=focus_zones)
        _draw_hw_box(ax, 4.38, 1.72, 1.38, 1.18, "DD2: \u0426\u041e\u0421 2\nADSP-21369", "400 \u041c\u0413\u0446, 2\u041c\u0431\nPB0=CS2, PB1", "#4ADE80", face_hi, alpha=a_val, fs_title=7.8, fs_sub=6.5, lw=lw_val, focus_list=focus_zones)
        _draw_hw_box(ax, 6.12, 3.40, 1.08, 1.18, "DD5: AD1938", "24 \u0431\u0438\u0442, 96\u043a\nSPORT0+SPIB", "#C084FC", face_hi, alpha=a_val, fs_title=7.6, fs_sub=6.4, lw=lw_val, focus_list=focus_zones)
        _draw_hw_box(ax, 6.12, 1.72, 1.08, 1.18, "DD6: AD1938", "24 \u0431\u0438\u0442, 96\u043a\nSPORT0+SPIB", "#C084FC", face_hi, alpha=a_val, fs_title=7.6, fs_sub=6.4, lw=lw_val, focus_list=focus_zones)

        _draw_bus_arrow(ax, 2.09, 3.85, 2.43, 3.45, "#FBBF24", "NRST", alpha=a_val)
        _draw_bus_arrow(ax, 2.09, 2.35, 2.43, 2.85, "#F87171", "SPI1", alpha=a_val, bidir=True)
        _draw_bus_arrow(ax, 3.97, 3.55, 4.36, 3.88, "#38BDF8", "SPI2", alpha=a_val, bidir=True)
        _draw_bus_arrow(ax, 3.97, 2.75, 4.36, 2.35, "#38BDF8", "SPI2", alpha=a_val, bidir=True)
        _draw_bus_arrow(ax, 5.78, 3.98, 6.10, 3.98, "#4ADE80", "SPORT0", alpha=a_val, bidir=True)
        _draw_bus_arrow(ax, 5.78, 2.30, 6.10, 2.30, "#4ADE80", "SPORT0", alpha=a_val, bidir=True)
        packets.extend([
            (3.97, 3.55, 4.36, 3.88, COL_CYAN),
            (5.78, 3.98, 6.10, 3.98, COL_GREEN),
            (5.78, 2.30, 6.10, 2.30, COL_GREEN),
        ])
        return {"focus_zones": focus_zones, "plot_reveal": plot_reveal, "curve_dots": curve_dots, "packets": packets}

    if mode == "cos_transform":
        ax.text(0.75, 6.20, "\u041f\u0443\u0442\u0435\u0432\u043e\u0434\u0438\u0442\u0435\u043b\u044c \u043f\u043e 79 \u0441\u0442\u0440\u0430\u043d\u0438\u0446\u0430\u043c \u041f\u0417 (\u0412\u043e\u043f\u0440\u043e\u0441 \u21161 \u0434\u043e\u0446. \u0410. \u041d. \u0414\u0435\u0434\u043e\u0432\u0430):", color="#38BDF8", fontsize=8.8, weight="bold")
        pz_blocks = [
            ("\u0421\u0442\u0440. 1\u201311 \u041f\u0417", "\u0417\u0430\u0434\u0430\u043d\u0438\u0435 (\u0441. 4)\n\u0428\u0438\u0444\u0440 \u0412\u0430\u0440. 19", "#38BDF8"),
            ("\u0421\u0442\u0440. 12\u201324 \u041f\u0417", "\u0420\u0430\u0437\u0434\u0435\u043b 2.1: cos(x)\n\u0411\u0435\u0441\u0441\u0435\u043b\u044c, \u0413\u043e\u0440\u043d\u0435\u0440 P6", "#4ADE80"),
            ("\u0421\u0442\u0440. 25\u201352 \u041f\u0417", "\u0420\u0430\u0437\u0434\u0435\u043b\u044b 2.2\u20132.4\n\u0421\u0445\u0435\u043c\u0430 \u042d2 (DD1..6)", "#FBBF24"),
            ("\u0421\u0442\u0440. 53\u201379 \u041f\u0417", "\u0420\u0430\u0437\u0434\u0435\u043b 2.5 + \u041f\u0440. 1\n\u041a\u0430\u0440\u043a\u0430\u0441 DMA + ISR", "#C084FC"),
        ]
        for idx, (pt, ps, pcol) in enumerate(pz_blocks):
            bx = 0.72 + idx * 1.64
            _draw_hw_box(ax, bx, 4.80, 1.52, 1.18, pt, ps, pcol, face_hi, alpha=a_val, fs_title=8.1, fs_sub=6.9, lw=lw_val, focus_list=focus_zones)
            if idx < 3:
                _draw_bus_arrow(ax, bx + 1.53, 5.39, bx + 1.63, 5.39, pcol, alpha=a_val)

        ax.text(0.75, 4.42, "\u041c\u043e\u0441\u0442 \u043d\u0430 \u0441\u0442\u0440. 78 \u041f\u0417: \u0432\u0441\u0442\u0430\u0432\u043a\u0430 4 \u043a\u043e\u043c\u0430\u043d\u0434 \u0441\u0445\u0435\u043c\u044b \u0413\u043e\u0440\u043d\u0435\u0440\u0430 \u0432 \u043e\u0431\u0440\u0430\u0431\u043e\u0442\u0447\u0438\u043a dma_rx_isr:", color="#4ADE80", fontsize=8.5, weight="bold")
        _draw_hw_box(ax, 0.72, 2.95, 1.38, 1.22, "SPORT0 DMA\nrx_buf", "F0 = FLOAT R0\nx \u2208 [-1; +1]", "#38BDF8", face_hi, alpha=a_val, fs_title=7.8, fs_sub=6.8, lw=lw_val, focus_list=focus_zones)
        _draw_hw_box(
            ax, 2.38, 2.82, 3.12, 1.45,
            "\u042f\u0434\u0440\u043e dma_rx_isr (\u0441\u0442\u0440. 78 \u041f\u0417): 8 \u0442\u0430\u043a\u0442\u043e\u0432",
            "1) F4 = F0 * F0  (u = x\u00b2)\n2) F8 = F8*F4 + F12  (s1, s2, y = cos x)",
            "#4ADE80", face_hi, alpha=a_val, fs_title=8.0, fs_sub=7.1, lw=lw_val, focus_list=focus_zones,
        )
        _draw_hw_box(ax, 5.78, 2.95, 1.42, 1.22, "SPORT0 DMA\ntx_buf", "R0 = FIX F0\n\u0432 \u0426\u0410\u041f AD1938", "#FBBF24", face_hi, alpha=a_val, fs_title=7.8, fs_sub=6.8, lw=lw_val, focus_list=focus_zones)
        _draw_bus_arrow(ax, 2.12, 3.56, 2.36, 3.56, "#38BDF8", alpha=a_val)
        _draw_bus_arrow(ax, 5.52, 3.56, 5.76, 3.56, "#4ADE80", alpha=a_val)

        _draw_plot_box(ax, 0.72, 1.62, 6.48, 1.02, "y(n) = cos(x(n)) \u2208 [0,5403; 1,0]", "#4ADE80", "nT_s")
        u_arr = np.linspace(0.0, 1.0, 400)
        x_arr = 0.84 + u_arr * 6.24
        y_in = 2.13 + 0.34 * np.sin(2.0 * np.pi * 2.0 * u_arr)
        y_out = 2.13 + 0.34 * ((np.cos(np.sin(2.0 * np.pi * 2.0 * u_arr)) - 0.77) / 0.23)
        ax.plot(x_arr, y_in, color="#38BDF8", lw=1.4 if lit else 0.9, alpha=a_val * 0.75, ls="--")
        ax.plot(x_arr, y_out, color="#4ADE80", lw=2.2 if lit else 1.1, alpha=a_val)
        plot_reveal = (0.72, 1.62, 6.48, 1.02)
        curve_dots.append((x_arr, y_in, COL_CYAN, 2.13))
        curve_dots.append((x_arr, y_out, COL_GREEN, 2.13))
        packets.append((2.12, 3.56, 5.76, 3.56, COL_GREEN))
        return {"focus_zones": focus_zones, "plot_reveal": plot_reveal, "curve_dots": curve_dots, "packets": packets}

    if mode == "bessel_spectrum":
        _draw_plot_box(ax, 0.72, 4.32, 6.48, 1.95, "\u041d\u0435\u043b\u0438\u043d\u0435\u0439\u043d\u044b\u0439 \u043e\u0442\u043a\u043b\u0438\u043a y(t) = cos(sin 2\u03c0f\u2080t) \u2014 \u0443\u0434\u0432\u043e\u0435\u043d\u0438\u0435 \u0447\u0430\u0441\u0442\u043e\u0442\u044b (\u0441\u0442\u0440. 14 \u041f\u0417)", "#38BDF8", "t")
        u_arr = np.linspace(0.0, 1.0, 450)
        x_arr = 0.84 + u_arr * 6.24
        x_in = np.sin(2.0 * np.pi * 2.0 * u_arr)
        y_in = 5.25 + 0.62 * x_in
        y_out = 5.25 + 0.62 * ((np.cos(x_in) - 0.77) / 0.23)
        ax.plot(x_arr, y_in, color="#38BDF8", lw=1.5 if lit else 0.9, ls="--", alpha=a_val * 0.75)
        ax.plot(x_arr, y_out, color="#4ADE80", lw=2.4 if lit else 1.1, alpha=a_val)
        plot_reveal = (0.72, 4.32, 6.48, 1.95)
        curve_dots.append((x_arr, y_in, COL_CYAN, 5.25))
        curve_dots.append((x_arr, y_out, COL_GREEN, 5.25))

        _draw_plot_box(ax, 0.72, 1.62, 6.48, 2.48, "\u0421\u043f\u0435\u043a\u0442\u0440 \u042f\u043a\u043e\u0431\u0438\u2013\u0410\u043d\u0433\u0435\u0440\u0430 20\u00b7lg|2J\u2082\u2096(1)| \u0438 \u043f\u043e\u0440\u043e\u0433 -66 \u0434\u0411 (\u0422\u0430\u0431\u043b. 1 \u0441\u0442\u0440. 16 \u041f\u0417)", "#4ADE80", "f, \u043a\u0413\u0446", y_zero_frac=0.12)
        harms = [
            ("0 \u043a\u0413\u0446", -2.3, "#38BDF8"),
            ("20 \u043a\u0413\u0446\n(2k=2)", -13.1, "#4ADE80"),
            ("40 \u043a\u0413\u0446\n(2k=4)", -43.8, "#4ADE80"),
            ("60 \u043a\u0413\u0446\n(2k=6)", -67.0, "#F87171"),
            ("80 \u043a\u0413\u0446\n(2k=8)", -94.6, "#64748B"),
        ]
        y_base = 1.92
        for idx, (flbl, db_val, bcol) in enumerate(harms):
            bx = 1.05 + idx * 1.18
            bh = max(0.12, ((105.0 + db_val) / 105.0) * 1.62)
            rect = mpatches.FancyBboxPatch((bx, y_base), 0.68, bh, boxstyle="round,pad=0.01,rounding_size=0.04", facecolor=bcol, edgecolor="#F8FAFC" if lit else bcol, lw=1.2, alpha=a_val * 0.88, zorder=3)
            ax.add_patch(rect)
            ax.text(bx + 0.34, y_base + bh + 0.11, f"{db_val:.1f} \u0434\u0411", ha="center", va="center", color="#F8FAFC", fontsize=7.4, weight="bold", alpha=a_val, zorder=4)
            ax.text(bx + 0.34, 1.75, flbl, ha="center", va="center", color="#CBD5E1", fontsize=6.7, alpha=a_val, zorder=4)
            focus_zones.append((bx - 0.08, 1.66, 0.84, bh + 0.48, _hex_to_rgb(bcol)))
        y_thr = y_base + ((105.0 - 66.0) / 105.0) * 1.62
        ax.plot([0.85, 7.05], [y_thr, y_thr], color="#F87171", lw=1.6, ls="--", alpha=a_val, zorder=4)
        ax.text(6.98, y_thr + 0.11, "\u041f\u043e\u0440\u043e\u0433 -66 \u0434\u0411 \u2192 Fmax=40 \u043a\u0413\u0446 \u2192 Fs=96 \u043a\u0413\u0446", ha="right", va="center", color="#FBBF24", fontsize=7.4, weight="bold", alpha=a_val, zorder=4)
        return {"focus_zones": focus_zones, "plot_reveal": plot_reveal, "curve_dots": curve_dots, "packets": packets}

    if mode == "horner_poly":
        ax.text(0.75, 6.20, "\u041a\u043e\u043d\u0432\u0435\u0439\u0435\u0440 \u0441\u0445\u0435\u043c\u044b \u0413\u043e\u0440\u043d\u0435\u0440\u0430 P\u2086(x): 4 \u0443\u043c\u043d\u043e\u0436\u0435\u043d\u0438\u044f \u0432\u043c\u0435\u0441\u0442\u043e 12 (\u0422\u0430\u0431\u043b. 2 \u0441\u0442\u0440. 19 \u041f\u0417):", color="#38BDF8", fontsize=8.7, weight="bold")
        stages = [
            ("\u0428\u0430\u0433 1: u = x\u00b2", "F4 = F0 * F0\nu \u2208 [0; 1]", "#38BDF8"),
            ("\u0428\u0430\u0433 2: s\u2081(u)", "c\u2082 + u\u00b7c\u2083\n1/24 - u/720", "#4ADE80"),
            ("\u0428\u0430\u0433 3: s\u2082(u)", "c\u2081 + u\u00b7s\u2081\n-0.5 + u\u00b7s\u2081", "#FBBF24"),
            ("\u0428\u0430\u0433 4: P\u2086(x)", "1.0 + u\u00b7s\u2082\n\u0394 = 2.45\u00b710\u207b\u2075", "#C084FC"),
        ]
        for idx, (st, ss, scol) in enumerate(stages):
            sx = 0.72 + idx * 1.64
            _draw_hw_box(ax, sx, 4.65, 1.50, 1.32, st, ss, scol, face_hi, alpha=a_val, fs_title=8.2, fs_sub=7.0, lw=lw_val, focus_list=focus_zones)
            if idx < 3:
                _draw_bus_arrow(ax, sx + 1.51, 5.31, sx + 1.63, 5.31, scol, alpha=a_val)
        packets.append((0.90, 5.31, 6.90, 5.31, COL_GOLD))

        _draw_plot_box(ax, 0.72, 1.62, 6.48, 2.72, "\u041f\u043e\u0433\u0440\u0435\u0448\u043d\u043e\u0441\u0442\u044c \u0430\u043f\u043f\u0440\u043e\u043a\u0441\u0438\u043c\u0430\u0446\u0438\u0438 |\u0394(x)|: P\u2084(x) (\u043e\u0442\u043a\u0430\u0437) vs P\u2086(x) (\u043d\u043e\u0440\u043c\u0430 \u2264 5\u00b710\u207b\u2074)", "#4ADE80", "x \u2208 [-1; +1]", y_zero_frac=0.08)
        u_arr = np.linspace(0.0, 1.0, 450)
        x_arr = 0.84 + u_arr * 6.24
        x_val = 2.0 * u_arr - 1.0
        y_p4 = 1.82 + 1.95 * (x_val**4)
        y_p6 = 1.82 + 0.32 * (x_val**6)
        y_lim = 1.82 + 1.15
        ax.plot(x_arr, y_p4, color="#F87171", lw=1.8 if lit else 1.0, ls="--", alpha=a_val)
        ax.plot(x_arr, y_p6, color="#4ADE80", lw=2.5 if lit else 1.1, alpha=a_val)
        ax.plot([0.84, 7.08], [y_lim, y_lim], color="#FBBF24", lw=1.4, ls="-.", alpha=a_val)
        ax.text(3.96, y_lim + 0.12, "\u0414\u043e\u043f\u0443\u0441\u043a \u0394\u0434\u043e\u043f = 5\u00b710\u207b\u2074 (\u0443 P\u2086 \u043c\u0430\u043a\u0441. 2,45\u00b710\u207b\u2075 \u2014 \u0437\u0430\u043f\u0430\u0441 20\u00d7!)", ha="center", va="center", color="#FBBF24", fontsize=7.5, weight="bold", alpha=a_val)
        plot_reveal = (0.72, 1.62, 6.48, 2.72)
        curve_dots.append((x_arr, y_p4, COL_RED, 1.82))
        curve_dots.append((x_arr, y_p6, COL_GREEN, 1.82))
        return {"focus_zones": focus_zones, "plot_reveal": plot_reveal, "curve_dots": curve_dots, "packets": packets}

    if mode == "enob_tangent":
        _draw_plot_box(ax, 0.72, 4.25, 6.48, 2.02, "\u041a\u043e\u044d\u0444\u0444\u0438\u0446\u0438\u0435\u043d\u0442 \u0443\u0441\u0438\u043b\u0435\u043d\u0438\u044f \u043e\u0448\u0438\u0431\u043a\u0438 k(x) = |tg x| \u2192 k_max = tg(1) = 1,557 (\u0441\u0442\u0440. 20 \u041f\u0417)", "#38BDF8", "|x|, \u0440\u0430\u0434", y_zero_frac=0.12)
        u_arr = np.linspace(0.0, 1.0, 450)
        x_arr = 0.84 + u_arr * 6.24
        y_tan = 4.48 + 1.42 * (np.tan(u_arr) / math.tan(1.0))
        ax.plot(x_arr, y_tan, color="#38BDF8", lw=2.4 if lit else 1.1, alpha=a_val)
        ax.plot([0.84, 7.08], [4.48 + 1.42, 4.48 + 1.42], color="#FBBF24", lw=1.2, ls="--", alpha=a_val)
        ax.text(6.95, 4.48 + 1.28, "k(1) = 1,557 \u2192 N_min = 13 \u0431\u0438\u0442", ha="right", va="center", color="#FBBF24", fontsize=7.6, weight="bold", alpha=a_val)
        plot_reveal = (0.72, 4.25, 6.48, 2.02)
        curve_dots.append((x_arr, y_tan, COL_CYAN, 4.48))

        ax.text(0.75, 3.92, "\u0420\u0430\u0437\u0440\u044f\u0434\u043d\u0430\u044f \u0441\u0435\u0442\u043a\u0430 24-\u0431\u0438\u0442\u043d\u043e\u0433\u043e \u043a\u043e\u0434\u0435\u043a\u0430 AD1938 \u0438 \u043c\u0430\u043d\u0442\u0438\u0441\u0441\u044b IEEE-754 (\u0441\u0442\u0440. 21, 35 \u041f\u0417):", color="#4ADE80", fontsize=8.5, weight="bold")
        _draw_hw_box(ax, 0.72, 2.55, 3.45, 1.18, "\u0411\u0438\u0442\u044b B23 .. B11 (13 \u0440\u0430\u0437\u0440\u044f\u0434\u043e\u0432)", "\u041c\u0438\u043d\u0438\u043c\u0443\u043c \u043f\u043e \u0422\u0417: N \u2265 13 \u0431\u0438\u0442\n(\u0434\u043b\u044f \u0394 \u2264 5\u00b710\u207b\u2074 \u043f\u0440\u0438 k=1,557)", "#38BDF8", face_hi, alpha=a_val, fs_title=8.1, fs_sub=7.0, lw=lw_val, focus_list=focus_zones)
        _draw_hw_box(ax, 4.25, 2.55, 1.35, 1.18, "B10..B8", "ENOB = 15,32\n(SNR 94 \u0434\u0411)", "#4ADE80", face_hi, alpha=a_val, fs_title=8.1, fs_sub=6.9, lw=lw_val, focus_list=focus_zones)
        _draw_hw_box(ax, 5.68, 2.55, 1.52, 1.18, "B7 .. B0 (8 \u0431\u0438\u0442)", "\u0417\u0430\u043f\u0430\u0441 24-\u0431\u0438\u0442\n\u043a\u043e\u0434\u0435\u043a\u0430 AD1938", "#FBBF24", face_hi, alpha=a_val, fs_title=8.0, fs_sub=6.9, lw=lw_val, focus_list=focus_zones)
        _draw_hw_box(ax, 0.72, 1.65, 6.48, 0.72, "\u0412\u043d\u0443\u0442\u0440\u0438 ADSP-21369: 32/40-\u0431\u0438\u0442\u043d\u044b\u0439 \u0444\u043e\u0440\u043c\u0430\u0442 IEEE-754 (1 \u0431\u0438\u0442 \u0437\u043d\u0430\u043a + 8 \u0431\u0438\u0442 \u043f\u043e\u0440\u044f\u0434\u043e\u043a + 24/32 \u0431\u0438\u0442\u0430 \u043c\u0430\u043d\u0442\u0438\u0441\u0441\u044b)", "", "#C084FC", face_hi, alpha=a_val, fs_title=7.8, lw=lw_val, focus_list=focus_zones)
        return {"focus_zones": focus_zones, "plot_reveal": plot_reveal, "curve_dots": curve_dots, "packets": packets}

    if mode == "sharc_float":
        ax.text(0.75, 6.20, "\u0410\u0440\u0445\u0438\u0442\u0435\u043a\u0442\u0443\u0440\u0430 SIMD-\u044f\u0434\u0440\u0430 ADSP-21369 SHARC (400 \u041c\u0413\u0446, 2,4 GFLOPS, \u0441\u0442\u0440. 32\u201334 \u041f\u0417):", color="#38BDF8", fontsize=8.7, weight="bold")
        _draw_hw_box(ax, 0.72, 4.58, 1.48, 1.38, "\u041a\u044d\u0448 PM + DAG", "48-\u0431\u0438\u0442 ISA\nDAG1 / DAG2\n\u0428\u0438\u043d\u044b PMD/DMD", "#38BDF8", face_hi, alpha=a_val, fs_title=8.0, fs_sub=6.8, lw=lw_val, focus_list=focus_zones)
        _draw_hw_box(ax, 2.48, 4.58, 2.15, 1.38, "\u0423\u0437\u0435\u043b PEx (SIMD #1)", "ALU + MAC + Shifter\nIEEE-754 32/40 \u0431\u0438\u0442\n\u0420\u0435\u0433\u0438\u0441\u0442\u0440\u044b F0..F15", "#4ADE80", face_hi, alpha=a_val, fs_title=8.2, fs_sub=6.9, lw=lw_val, focus_list=focus_zones)
        _draw_hw_box(ax, 4.88, 4.58, 2.32, 1.38, "\u0423\u0437\u0435\u043b PEy (SIMD #2)\n+ SRU / 6\u00d7SPORT / 2\u00d7SPI", "1 \u0442\u0430\u043a\u0442 = 2,5 \u043d\u0441\nSPI (Slave) + SPIB (Master)", "#FBBF24", face_hi, alpha=a_val, fs_title=7.8, fs_sub=6.8, lw=lw_val, focus_list=focus_zones)
        _draw_bus_arrow(ax, 2.22, 5.27, 2.46, 5.27, "#38BDF8", alpha=a_val)
        _draw_bus_arrow(ax, 4.65, 5.27, 4.86, 5.27, "#4ADE80", alpha=a_val, bidir=True)

        ax.text(0.75, 4.22, "\u0421\u0440\u0430\u0432\u043d\u0435\u043d\u0438\u0435 3 \u043a\u0430\u043d\u0434\u0438\u0434\u0430\u0442\u043e\u0432 (\u0412\u043e\u043f\u0440\u043e\u0441 \u21162 \u0414\u0435\u0434\u043e\u0432\u0430) \u0438 \u0437\u0430\u043f\u0430\u0441 \u0440\u0435\u0430\u043b\u044c\u043d\u043e\u0433\u043e \u0432\u0440\u0435\u043c\u0435\u043d\u0438 (96 \u043a\u0413\u0446):", color="#4ADE80", fontsize=8.5, weight="bold")
        _draw_hw_box(ax, 0.72, 2.68, 2.02, 1.32, "ADSP-BF561\n(\u041e\u0422\u041a\u041b\u041e\u041d\u0401\u041d)", "16-\u0431\u0438\u0442 \u0444\u0438\u043a\u0441. \u0442\u043e\u0447\u043a\u0430\n\u041f\u043e\u0442\u0435\u0440\u044f x\u2076, 1\u00d7SPI", "#F87171", face_hi, alpha=a_val, fs_title=7.9, fs_sub=6.8, lw=lw_val, focus_list=focus_zones)
        _draw_hw_box(ax, 2.92, 2.68, 2.02, 1.32, "ADSP-21489\n(\u0418\u0417\u0411\u042b\u0422\u041e\u0427\u0415\u041d)", "5 \u041c\u0431\u0438\u0442 SRAM (\u043d\u0430\u043c\n\u043d\u0443\u0436\u043d\u043e \u043b\u0438\u0448\u044c 14 \u041a\u0411)", "#FBBF24", face_hi, alpha=a_val, fs_title=7.9, fs_sub=6.8, lw=lw_val, focus_list=focus_zones)
        _draw_hw_box(ax, 5.12, 2.68, 2.08, 1.32, "ADSP-21369\n(\u0412\u042b\u0411\u0420\u0410\u041d DD1/DD2)", "IEEE-754, 2 \u041c\u0431\u0438\u0442\nSRU + 2\u00d7SPI (\u041f\u0417\u0423=0)", "#4ADE80", face_hi, alpha=a_val, fs_title=8.0, fs_sub=6.8, lw=lw_val, focus_list=focus_zones)
        _draw_hw_box(ax, 0.72, 1.65, 6.48, 0.82, "\u0411\u044e\u0434\u0436\u0435\u0442 \u043e\u0442\u0441\u0447\u0451\u0442\u0430 96 \u043a\u0413\u0446 (10,4 \u043c\u043a\u0441 = 4166 \u0442\u0430\u043a\u0442\u043e\u0432): \u0413\u043e\u0440\u043d\u0435\u0440 + \u043a\u0430\u0441\u043a\u0430\u0434\u044b = 55 \u0442\u0430\u043a\u0442\u043e\u0432 (1,37% \u0426\u041f, \u0437\u0430\u043f\u0430\u0441 98,6%)", "", "#38BDF8", face_hi, alpha=a_val, fs_title=7.7, lw=lw_val, focus_list=focus_zones)
        packets.append((2.22, 5.27, 4.86, 5.27, COL_GREEN))
        return {"focus_zones": focus_zones, "plot_reveal": plot_reveal, "curve_dots": curve_dots, "packets": packets}

    if mode == "sram_dag":
        ax.text(0.75, 6.20, "4 \u0431\u0430\u043d\u043a\u0430 \u0434\u0432\u0443\u0445\u043f\u043e\u0440\u0442\u043e\u0432\u043e\u0439 SRAM ADSP-21369 = 2 \u041c\u0431\u0438\u0442 (\u0422\u0430\u0431\u043b\u0438\u0446\u0430 5, \u0441\u0442\u0440. 52 \u041f\u0417):", color="#38BDF8", fontsize=8.7, weight="bold")
        banks = [
            ("\u0411\u043b\u043e\u043a 0 (64 \u041a\u0411)", "0x00090000\n\u041a\u043e\u0434 + IVT (PM)\n~2 \u041a\u0411 (0,8%)", "#38BDF8"),
            ("\u0411\u043b\u043e\u043a 1 (64 \u041a\u0411)", "0x000B2000\n\u041a\u043e\u044d\u0444\u0444\u0438\u0446\u0438\u0435\u043d\u0442\u044b\n\u0428\u0438\u043d\u0430 PMD", "#4ADE80"),
            ("\u0411\u043b\u043e\u043a 2 (64 \u041a\u0411)", "0x000C0000\ndelay + rx/tx_buf\n\u0428\u0438\u043d\u044b DMD + IOD", "#FBBF24"),
            ("\u0411\u043b\u043e\u043a 3 (64 \u041a\u0411)", "0x000E0000\n\u0421\u0442\u0435\u043a 4\u041a\u0411 + Mailbox\n\u0421\u0432\u043e\u0431\u043e\u0434\u043d\u043e >94%", "#C084FC"),
        ]
        for idx, (bt, bs, bcol) in enumerate(banks):
            bx = 0.72 + idx * 1.64
            _draw_hw_box(ax, bx, 4.48, 1.52, 1.48, bt, bs, bcol, face_hi, alpha=a_val, fs_title=8.0, fs_sub=6.7, lw=lw_val, focus_list=focus_zones)

        ax.text(0.75, 4.12, "\u0410\u043f\u043f\u0430\u0440\u0430\u0442\u043d\u044b\u0439 \u043a\u043e\u043b\u044c\u0446\u0435\u0432\u043e\u0439 \u0431\u0443\u0444\u0435\u0440 DAG1 (B\u2080, I\u2080, L\u2080=384, M\u2080=1) \u0438 \u0432\u044b\u0431\u043e\u0440\u043a\u0430 \u0437\u0430 1 \u0442\u0430\u043a\u0442:", color="#4ADE80", fontsize=8.5, weight="bold")
        cx, cy, r_ring = 1.95, 2.75, 0.92
        circle_bg = mpatches.Circle((cx, cy), r_ring, facecolor="#111827", edgecolor="#38BDF8", lw=1.6, alpha=a_val, zorder=2)
        ax.add_patch(circle_bg)
        circle_in = mpatches.Circle((cx, cy), r_ring * 0.52, facecolor="#0D111A", edgecolor="#4ADE80", lw=1.2, alpha=a_val, zorder=3)
        ax.add_patch(circle_in)
        ax.text(cx, cy, "DAG1\nL\u2080=384", ha="center", va="center", color="#F8FAFC", fontsize=7.6, weight="bold", alpha=a_val, zorder=4)
        for k in range(8):
            ang = 2.0 * math.pi * k / 8.0
            px = cx + (r_ring * 0.76) * math.cos(ang)
            py = cy + (r_ring * 0.76) * math.sin(ang)
            dot = mpatches.Circle((px, py), 0.08, facecolor="#4ADE80" if k == 0 else "#38BDF8", edgecolor="none", alpha=a_val, zorder=4)
            ax.add_patch(dot)
        ax.text(cx, cy + r_ring + 0.14, "B\u2080 (0x000C0000)", ha="center", va="center", color="#4ADE80", fontsize=7.2, weight="bold", alpha=a_val)
        focus_zones.append((cx - r_ring - 0.10, cy - r_ring - 0.10, 2.0 * (r_ring + 0.10), 2.0 * (r_ring + 0.14), COL_CYAN))

        _draw_hw_box(
            ax, 3.25, 1.72, 3.95, 2.15,
            "\u0420\u0435\u0433\u0438\u0441\u0442\u0440\u044b DAG1/DAG2 \u0438 \u043f\u0430\u0440\u0430\u043b\u043b\u0435\u043b\u044c\u043d\u044b\u0439 MAC (\u0441\u0442\u0440. 51, 78 \u041f\u0417)",
            "B0 = delay_line (0x000C0000),  L0 = 384 (>0 \u2192 \u043a\u043e\u043b\u044c\u0446\u043e!)\nI_new = B0 + ((I_old - B0 + M0) mod L0) \u2014 0 \u0442\u0430\u043a\u0442\u043e\u0432 \u0426\u041f!\nF12=F2*F4, F8=F8+F12, F2=DM(I0,M0), F4=PM(I8,M8);",
            "#4ADE80", face_hi, alpha=a_val, fs_title=8.1, fs_sub=7.0, lw=lw_val, focus_list=focus_zones,
        )
        return {"focus_zones": focus_zones, "plot_reveal": plot_reveal, "curve_dots": curve_dots, "packets": packets}

    if mode == "sigma_delta":
        ax.text(0.75, 6.20, "\u0421\u0442\u0440\u0443\u043a\u0442\u0443\u0440\u043d\u0430\u044f \u0441\u0445\u0435\u043c\u0430 24-\u0431\u0438\u0442\u043d\u043e\u0433\u043e \u03a3\u0394-\u043a\u043e\u0434\u0435\u043a\u0430 AD1938 (\u0412\u043e\u043f\u0440\u043e\u0441 \u21163 \u0414\u0435\u0434\u043e\u0432\u0430, \u0441\u0442\u0440. 35 \u041f\u0417):", color="#38BDF8", fontsize=8.6, weight="bold")
        sd_blocks = [
            ("\u0412\u0445\u043e\u0434 + \u03a3", "ADC1LP (1\u0412)\n\u0412\u044b\u0447\u0438\u0442\u0430\u0442\u0435\u043b\u044c", "#38BDF8"),
            ("\u0418\u043d\u0442\u0435\u0433\u0440\u0430\u0442\u043e\u0440", "\u041d\u0430\u043a\u043e\u043f\u043b\u0435\u043d\u0438\u0435\n\u043e\u0448\u0438\u0431\u043a\u0438 H(s)", "#4ADE80"),
            ("\u041c\u043e\u0434\u0443\u043b\u044f\u0442\u043e\u0440 64\u00d7", "6,144 \u041c\u0413\u0446 (\u043e\u0442 G1)\n+ \u041e\u041e\u0421 1-\u0431\u0438\u0442 \u0426\u0410\u041f", "#FBBF24"),
            ("\u0426\u0438\u0444\u0440. \u0424\u041d\u0427 \u00f764", "\u0414\u0435\u0446\u0438\u043c\u0430\u0442\u043e\u0440\n24 \u0431\u0438\u0442 @ 96 \u043a\u0413\u0446", "#C084FC"),
        ]
        for idx, (st, ss, scol) in enumerate(sd_blocks):
            sx = 0.72 + idx * 1.64
            _draw_hw_box(ax, sx, 4.72, 1.50, 1.25, st, ss, scol, face_hi, alpha=a_val, fs_title=8.0, fs_sub=6.8, lw=lw_val, focus_list=focus_zones)
            if idx < 3:
                _draw_bus_arrow(ax, sx + 1.51, 5.34, sx + 1.63, 5.34, scol, alpha=a_val)
        packets.append((0.90, 5.34, 6.90, 5.34, COL_CYAN))

        _draw_plot_box(ax, 0.72, 1.62, 6.48, 2.82, "\u0412\u044b\u0442\u0435\u0441\u043d\u0435\u043d\u0438\u0435 \u0448\u0443\u043c\u0430 \u043a\u0432\u0430\u043d\u0442\u043e\u0432\u0430\u043d\u0438\u044f (Noise Shaping) \u0438 \u0441\u0440\u0435\u0437 \u0446\u0438\u0444\u0440\u043e\u0432\u044b\u043c \u0424\u041d\u0427 (SNR = 108 \u0434\u0411)", "#4ADE80", "f", y_zero_frac=0.10)
        u_arr = np.linspace(0.0, 1.0, 450)
        x_arr = 0.84 + u_arr * 6.24
        pass_patch = mpatches.Rectangle((0.84, 1.78), 2.05, 2.20, facecolor="#14532D", edgecolor="#4ADE80", lw=1.0, alpha=0.35 * a_val, zorder=2)
        ax.add_patch(pass_patch)
        y_nyq = np.full_like(u_arr, 3.15)
        y_ns = 1.90 + 2.05 * (u_arr**2.1)
        ax.plot(x_arr, y_nyq, color="#94A3B8", lw=1.3, ls="--", alpha=a_val)
        ax.plot(x_arr, y_ns, color="#4ADE80", lw=2.5 if lit else 1.1, alpha=a_val)
        ax.text(1.85, 2.35, "\u041f\u043e\u043b\u043e\u0441\u0430 0..48 \u043a\u0413\u0446\nSNR > 105 \u0434\u0411", ha="center", va="center", color="#4ADE80", fontsize=7.6, weight="bold", alpha=a_val)
        ax.text(5.30, 3.65, "\u0412\u044b\u0442\u0435\u0441\u043d\u0435\u043d\u043d\u044b\u0439 \u0412\u0427-\u0448\u0443\u043c\n(\u0441\u0440\u0435\u0437\u0430\u0435\u0442\u0441\u044f \u0434\u0435\u0446\u0438\u043c\u0430\u0442\u043e\u0440\u043e\u043c)", ha="center", va="center", color="#FBBF24", fontsize=7.4, weight="bold", alpha=a_val)
        plot_reveal = (0.72, 1.62, 6.48, 2.82)
        curve_dots.append((x_arr, y_ns, COL_GREEN, 1.90))
        return {"focus_zones": focus_zones, "plot_reveal": plot_reveal, "curve_dots": curve_dots, "packets": packets}

    if mode == "sport_spib":
        ax.text(0.75, 6.20, "9 \u043b\u0438\u043d\u0438\u0439 \u0441\u0432\u044f\u0437\u0438 AD1938 (DD5/DD6) \u2194 ADSP-21369 (DD1/DD2) \u043d\u0430 \u0441\u0445\u0435\u043c\u0435 \u042d2 (\u0422\u0430\u0431\u043b. 4 \u0441\u0442\u0440. 46 \u041f\u0417):", color="#38BDF8", fontsize=8.6, weight="bold")
        _draw_hw_box(ax, 0.72, 2.58, 1.55, 3.38, "DD5 / DD6\nAD1938 (24 \u0431\u0438\u0442)", "\u041a\u0432\u0430\u0440\u0446 G1 =\n24,576 \u041c\u0413\u0446\n\nSPORT0: Master!\nSPIB: Slave", "#C084FC", face_hi, alpha=a_val, fs_title=8.2, fs_sub=7.0, lw=lw_val, focus_list=focus_zones)
        _draw_hw_box(ax, 5.65, 2.58, 1.55, 3.38, "DD1 / DD2\nADSP-21369", "\u041c\u0430\u0442\u0440\u0438\u0446\u0430 SRU\nDAI_P01..P04\n\nSPORT0: Slave\nSPIB: Master!", "#4ADE80", face_hi, alpha=a_val, fs_title=8.2, fs_sub=7.0, lw=lw_val, focus_list=focus_zones)

        bus_rows = [
            (5.65, "1. ABCLK/DBCLK (6,144 \u041c\u0413\u0446) \u2500\u2500\u25ba DAI_P01 (SPORT0_CLK)", "#38BDF8", False),
            (5.15, "2. ALRCLK/DLRCLK (96 \u043a\u0413\u0446)  \u2500\u2500\u25ba DAI_P02 (SPORT0_FS)", "#38BDF8", False),
            (4.65, "3\u20134. ASDATA1 (\u0410\u0426\u041f) / DSDATA1 (\u0426\u0410\u041f) \u25c4\u25ba DAI_P03 / P04", "#4ADE80", True),
            (3.95, "5\u20138. CLATCH, CCLK, CDATA, COUT \u25c4\u2500\u2500 SPIB (SPIDS = CS)", "#FBBF24", True),
            (3.35, "9. \u0412\u0445\u043e\u0434 PD/RST (\u0410\u043f\u043f\u0430\u0440\u0430\u0442\u043d\u044b\u0439 \u0441\u0431\u0440\u043e\u0441) \u25c4\u2500\u2500 FLAG1 / PA4", "#F87171", True),
        ]
        for by, btxt, bcol, rev in bus_rows:
            x_start, x_end = (5.62, 2.30) if rev else (2.30, 5.62)
            _draw_bus_arrow(ax, x_start, by, x_end, by, bcol, btxt, alpha=a_val, ly_off=0.13, focus_list=focus_zones)

        _draw_hw_box(
            ax, 0.72, 1.62, 6.48, 0.80,
            "\u0422\u0430\u0431\u043b\u0438\u0446\u0430 codec_tab[6] (\u0441\u0442\u0440. 48, 76 \u041f\u0417): Reg 0x00=0x80 (PLL ON) | 0x01 | 0x02 (96\u043a) | 0x03 (I2S 24b) | 0x0E=0x02 (HPF ON) | 0x0F",
            "", "#FBBF24", face_hi, alpha=a_val, fs_title=7.5, lw=lw_val, focus_list=focus_zones,
        )
        packets.extend([
            (2.30, 5.15, 5.62, 5.15, COL_CYAN),
            (5.62, 3.95, 2.30, 3.95, COL_GOLD),
        ])
        return {"focus_zones": focus_zones, "plot_reveal": plot_reveal, "curve_dots": curve_dots, "packets": packets}

    if mode == "dma_pipeline":
        ax.text(0.75, 6.20, "\u0424\u043e\u043d\u043e\u0432\u044b\u0439 \u041f\u0414\u041f \u0441 \u0430\u0432\u0442\u043e\u0441\u0446\u0435\u043f\u043a\u043e\u0439 (Chaining DMA SPORT0, 0% \u0426\u041f, \u0441\u0442\u0440. 49, 77 \u041f\u0417):", color="#38BDF8", fontsize=8.6, weight="bold")
        dma_chain = [
            ("\u0410\u0426\u041f AD1938", "SPORT0 RX\n96 \u043a\u0413\u0446 I2S", "#C084FC"),
            ("\u0411\u0443\u0444\u0435\u0440 rx_buf", "\u0411\u043b\u043e\u043a 2 SRAM\n\u0428\u0438\u043d\u0430 IOD DMA", "#38BDF8"),
            ("dma_rx_isr", "\u041f\u0440\u0435\u0440\u044b\u0432\u0430\u043d\u0438\u0435\n\u0433\u043e\u0442\u043e\u0432\u043d\u043e\u0441\u0442\u0438", "#4ADE80"),
            ("\u0411\u0443\u0444\u0435\u0440 tx_buf", "\u0412\u044b\u0433\u0440\u0443\u0437\u043a\u0430 \u0432\nSPORT0 TX", "#FBBF24"),
        ]
        for idx, (dt, ds, dcol) in enumerate(dma_chain):
            dx = 0.72 + idx * 1.64
            _draw_hw_box(ax, dx, 4.68, 1.50, 1.28, dt, ds, dcol, face_hi, alpha=a_val, fs_title=8.0, fs_sub=6.9, lw=lw_val, focus_list=focus_zones)
            if idx < 3:
                _draw_bus_arrow(ax, dx + 1.51, 5.32, dx + 1.63, 5.32, dcol, alpha=a_val)
        packets.append((0.90, 5.32, 6.90, 5.32, COL_CYAN))

        ax.text(0.75, 4.25, "\u041a\u043e\u043d\u0432\u0435\u0439\u0435\u0440 \u043e\u0431\u0440\u0430\u0431\u043e\u0442\u043a\u0438 24-\u0431\u0438\u0442\u043d\u043e\u0433\u043e \u043e\u0442\u0441\u0447\u0451\u0442\u0430 \u0432\u043d\u0443\u0442\u0440\u0438 dma_rx_isr (\u0441\u0442\u0440. 78 \u041f\u0417):", color="#4ADE80", fontsize=8.5, weight="bold")
        conv = [
            ("1. FLOAT R0 BY -23", "\u0426\u0435\u043b\u044b\u0439 24-\u0431\u0438\u0442 \u043a\u043e\u0434 R0\n\u2192 F0 \u2208 [-1,0; +1,0] \u0440\u0430\u0434\n(\u0437\u0430 1 \u0442\u0430\u043a\u0442 \u0410\u041b\u0423)", "#38BDF8"),
            ("2. \u0421\u0445\u0435\u043c\u0430 \u0413\u043e\u0440\u043d\u0435\u0440\u0430 P\u2086(x)", "F4 = F0 * F0\n3\u00d7 (F8 = F8*F4 + F12)\nF0 = cos(x) (\u0437\u0430 8 \u0442\u0430\u043a\u0442\u043e\u0432)", "#4ADE80"),
            ("3. FIX F0 BY 23", "\u041f\u043b\u0430\u0432\u0430\u044e\u0449\u0430\u044f \u0442\u043e\u0447\u043a\u0430 F0\n\u2192 24-\u0431\u0438\u0442 \u043a\u043e\u0434 \u0426\u0410\u041f R0\n\u0417\u0430\u043f\u0438\u0441\u044c DM(tx_buf) = R0", "#FBBF24"),
        ]
        for idx, (ct, cs, ccol) in enumerate(conv):
            cx = 0.72 + idx * 2.22
            _draw_hw_box(ax, cx, 1.72, 2.04, 2.25, ct, cs, ccol, face_hi, alpha=a_val, fs_title=8.1, fs_sub=7.0, lw=lw_val, focus_list=focus_zones)
            if idx < 2:
                _draw_bus_arrow(ax, cx + 2.06, 2.84, cx + 2.20, 2.84, ccol, alpha=a_val)
        packets.append((0.90, 2.84, 6.80, 2.84, COL_GREEN))
        return {"focus_zones": focus_zones, "plot_reveal": plot_reveal, "curve_dots": curve_dots, "packets": packets}

    if mode == "sb1_adm708":
        ax.text(0.75, 6.20, "\u0426\u0435\u043f\u044c \u0441\u0431\u0440\u043e\u0441\u0430 \u043d\u0430 \u0441\u0445\u0435\u043c\u0435 \u042d2 (\u0412\u043e\u043f\u0440\u043e\u0441 \u21164 \u0414\u0435\u0434\u043e\u0432\u0430, \u0441\u0442\u0440. 39 \u041f\u0417):", color="#38BDF8", fontsize=8.6, weight="bold")
        rst_nodes = [
            ("\u041a\u043d\u043e\u043f\u043a\u0430 SB1 + RC", "R19=10\u043a, C52=10\u043c\u043a\u0424\n\u03c4 = 100 \u043c\u0441 (\u0432\u0445\u043e\u0434 MR)", "#F87171"),
            ("DD4: ADM708", "\u0412\u044b\u0432.1 MR, \u0412\u044b\u0432.6 WDI\nBOR 2,93\u0412, POR 200 \u043c\u0441", "#FBBF24"),
            ("DD3: STM32F103", "\u0412\u0445\u043e\u0434 NRST (\u0432\u044b\u0432. 7)\nPB9 \u2192 WDI (1,6 \u0441)", "#38BDF8"),
            ("PA3 (RST_DSP)", "\u0421\u0431\u0440\u043e\u0441 DD1 \u0438 DD2\n\u0424\u0440\u043e\u043d\u0442 \u2191 \u2192 BOOT_CFG", "#4ADE80"),
        ]
        for idx, (rt, rs, rcol) in enumerate(rst_nodes):
            rx = 0.72 + idx * 1.64
            _draw_hw_box(ax, rx, 4.72, 1.50, 1.25, rt, rs, rcol, face_hi, alpha=a_val, fs_title=7.9, fs_sub=6.7, lw=lw_val, focus_list=focus_zones)
            if idx < 3:
                _draw_bus_arrow(ax, rx + 1.51, 5.34, rx + 1.63, 5.34, rcol, alpha=a_val)
        packets.append((0.90, 5.34, 6.90, 5.34, COL_GOLD))

        _draw_plot_box(ax, 0.72, 1.62, 6.48, 2.85, "\u0412\u0440\u0435\u043c\u0435\u043d\u043d\u0430\u044f \u0434\u0438\u0430\u0433\u0440\u0430\u043c\u043c\u0430 \u043f\u043e\u0434\u0430\u0432\u043b\u0435\u043d\u0438\u044f \u0434\u0440\u0435\u0431\u0435\u0437\u0433\u0430 SB1 \u0438 \u0438\u043c\u043f\u0443\u043b\u044c\u0441\u0430 POR 200 \u043c\u0441:", "#4ADE80", "t", y_zero_frac=0.08)
        u_arr = np.linspace(0.0, 1.0, 500)
        x_arr = 0.84 + u_arr * 6.24
        sb1_sig = 3.55 + np.where((u_arr >= 0.16) & (u_arr <= 0.42), 0.0, 0.42)
        adm_sig = 2.75 + np.where((u_arr >= 0.16) & (u_arr <= 0.72), 0.0, 0.42)
        dsp_sig = 1.90 + np.where((u_arr >= 0.18) & (u_arr <= 0.80), 0.0, 0.42)
        ax.plot(x_arr, sb1_sig, color="#F87171", lw=2.1 if lit else 1.0, alpha=a_val)
        ax.plot(x_arr, adm_sig, color="#FBBF24", lw=2.1 if lit else 1.0, alpha=a_val)
        ax.plot(x_arr, dsp_sig, color="#4ADE80", lw=2.2 if lit else 1.0, alpha=a_val)
        ax.text(0.92, 4.08, "1. \u0412\u0445\u043e\u0434 MR (SB1 = 0)", color="#F87171", fontsize=7.2, weight="bold", alpha=a_val)
        ax.text(0.92, 3.28, "2. RESET DD4 \u2192 NRST DD3 (\u0443\u0434\u0435\u0440\u0436\u0430\u043d\u0438\u0435 200 \u043c\u0441)", color="#FBBF24", fontsize=7.2, weight="bold", alpha=a_val)
        ax.text(0.92, 2.42, "3. PA3 (RST_DSP) \u2192 \u0424\u0440\u043e\u043d\u0442 \u2191 \u0437\u0430\u0449\u0451\u043b\u043a\u0438\u0432\u0430\u0435\u0442 BOOT_CFG=00", color="#4ADE80", fontsize=7.2, weight="bold", alpha=a_val)
        plot_reveal = (0.72, 1.62, 6.48, 2.85)
        curve_dots.append((x_arr, sb1_sig, COL_RED, 3.55))
        curve_dots.append((x_arr, adm_sig, COL_GOLD, 2.75))
        curve_dots.append((x_arr, dsp_sig, COL_GREEN, 1.90))
        return {"focus_zones": focus_zones, "plot_reveal": plot_reveal, "curve_dots": curve_dots, "packets": packets}

    if mode == "boot_cfg_8modes":
        ax.text(0.75, 6.20, "\u041c\u0430\u0442\u0440\u0438\u0446\u0430 \u0432\u044b\u0431\u043e\u0440\u0430 \u00ab1 \u0438\u0437 8 \u0432\u0430\u0440\u0438\u0430\u043d\u0442\u043e\u0432\u00bb \u0441\u0442\u0430\u0440\u0442\u0430 (\u0422\u0430\u0431\u043b. 3 \u0441\u0442\u0440. 41 \u041f\u0417, \u0412\u043e\u043f\u0440\u043e\u0441 \u21164 \u0414\u0435\u0434\u043e\u0432\u0430):", color="#38BDF8", fontsize=8.6, weight="bold")
        modes_grid = [
            ("000: SPI Slave [\u042d2]", "\u0417\u0430\u0433\u0440\u0443\u0437\u043a\u0430 \u043e\u0442 STM32\n384 \u0441\u043b. \u2192 0x00090000", "#4ADE80"),
            ("001: SPI Master", "\u0412\u043d\u0435\u0448\u043d\u044f\u044f SPI Flash\n(\u043f\u043e \u0448\u0438\u0444\u0440\u0443 \u041f\u0417\u0423=0)", "#38BDF8"),
            ("010: AMI PROM 8/16", "\u041f\u0430\u0440\u0430\u043b\u043b\u0435\u043b\u044c\u043d\u043e\u0435 \u041f\u0417\u0423\n\u043f\u043e \u0432\u043d\u0435\u0448\u043d\u0435\u0439 \u0448\u0438\u043d\u0435", "#38BDF8"),
            ("011: Link / Host", "\u0417\u0430\u0433\u0440\u0443\u0437\u043a\u0430 \u0447\u0435\u0440\u0435\u0437\n\u043b\u0438\u043d\u043a-\u043f\u043e\u0440\u0442", "#38BDF8"),
            ("100: PLL 16:1 + HG1='4'", "CCLK = 400 \u041c\u0413\u0446\n\u0420\u0435\u0436\u0438\u043c cos(x) \u0413\u043e\u0440\u043d\u0435\u0440", "#FBBF24"),
            ("101: PLL 32:1 + HG1='5'", "\u0420\u0435\u0436\u0438\u043c \u041a\u0418\u0425 \u041a\u0430\u0439\u0437\u0435\u0440\u0430\nN=384, L=M=6", "#FBBF24"),
            ("110: \u041a\u0430\u043d\u0430\u043b DD1 (HG1='6')", "CS1 (PA1=0) \u0430\u043a\u0442\u0438\u0432\u0435\u043d\n\u0422\u0435\u0441\u0442 \u0442\u0440\u0430\u043a\u0442\u0430 #1", "#C084FC"),
            ("111: DD1+DD2 (HG1='7')", "\u0414\u0432\u0443\u0445\u043a\u0430\u043d\u0430\u043b\u044c\u043d\u044b\u0439 \u0441\u0442\u0430\u0440\u0442\nPA1/PB0 + X6/HG1", "#F87171"),
        ]
        for idx, (mt, ms, mcol) in enumerate(modes_grid):
            col_i = idx % 4
            row_i = idx // 4
            mx = 0.72 + col_i * 1.64
            my = 4.92 if row_i == 0 else 3.68
            _draw_hw_box(ax, mx, my, 1.52, 1.08, mt, ms, mcol, face_hi, alpha=a_val, fs_title=7.4, fs_sub=6.5, lw=lw_val, focus_list=focus_zones)

        ax.text(0.75, 3.32, "\u041a\u043e\u043d\u0432\u0435\u0439\u0435\u0440 \u043f\u043e\u043e\u0447\u0435\u0440\u0451\u0434\u043d\u043e\u0439 \u0437\u0430\u0433\u0440\u0443\u0437\u043a\u0438 Boot Kernel (384 \u0441\u043b\u043e\u0432\u0430 \u00d7 48 \u0431\u0438\u0442) \u043e\u0442 DD3 \u043f\u043e SPI2:", color="#4ADE80", fontsize=8.4, weight="bold")
        _draw_hw_box(ax, 0.72, 1.72, 1.95, 1.38, "1. \u0424\u0440\u043e\u043d\u0442 \u2191 PA3 (RST)", "\u0417\u0430\u0449\u0451\u043b\u043a\u0438\u0432\u0430\u043d\u0438\u0435\nBOOT_CFG1..0 = 00", "#38BDF8", face_hi, alpha=a_val, fs_title=7.9, fs_sub=6.9, lw=lw_val, focus_list=focus_zones)
        _draw_hw_box(ax, 2.95, 1.72, 1.98, 1.38, "2. PA1 (CS1) = 0", "\u0417\u0430\u0433\u0440\u0443\u0437\u043a\u0430 DD1 (#1)\n\u0432 \u0411\u043b\u043e\u043a 0 (0x00090000)", "#4ADE80", face_hi, alpha=a_val, fs_title=7.9, fs_sub=6.9, lw=lw_val, focus_list=focus_zones)
        _draw_hw_box(ax, 5.20, 1.72, 2.00, 1.38, "3. PB0 (CS2) = 0", "\u0417\u0430\u0433\u0440\u0443\u0437\u043a\u0430 DD2 (#2)\n+ \u0440\u0435\u0436\u0438\u043c X6 \u2192 HG1", "#FBBF24", face_hi, alpha=a_val, fs_title=7.9, fs_sub=6.9, lw=lw_val, focus_list=focus_zones)
        _draw_bus_arrow(ax, 2.69, 2.41, 2.93, 2.41, "#38BDF8", alpha=a_val)
        _draw_bus_arrow(ax, 4.95, 2.41, 5.18, 2.41, "#4ADE80", alpha=a_val)
        packets.append((0.90, 2.41, 6.80, 2.41, COL_GREEN))
        return {"focus_zones": focus_zones, "plot_reveal": plot_reveal, "curve_dots": curve_dots, "packets": packets}

    if mode == "spi2_8lines":
        ax.text(0.75, 6.20, "8 \u043b\u0438\u043d\u0438\u0439 \u043e\u0431\u043c\u0435\u043d\u0430 HOST STM32 (DD3) \u2194 \u0426\u041e\u0421 DD1, DD2 (\u0422\u0430\u0431\u043b. 2 \u0441\u0442\u0440. 40 \u041f\u0417, \u0412\u043e\u043f\u0440\u043e\u0441 \u21165):", color="#38BDF8", fontsize=8.6, weight="bold")
        _draw_hw_box(ax, 0.72, 1.72, 1.68, 4.22, "HOST: DD3\nSTM32F103C8T6", "Cortex-M3 72 \u041c\u0413\u0446\n(\u043a\u0432\u0430\u0440\u0446 ZQ1 8 \u041c\u0413\u0446)\n\nSPI2 Master:\nPB13 = SCK\nPB15 = MOSI\nPB14 = MISO\n\nPA3 = RST_DSP", "#38BDF8", face_hi, alpha=a_val, fs_title=8.2, fs_sub=6.9, lw=lw_val, focus_list=focus_zones)
        _draw_hw_box(ax, 5.45, 4.02, 1.75, 1.92, "DD1: \u0426\u041e\u0421 #1\nADSP-21369", "SPI Slave\nSPIDS \u25c4\u2500 PA1 (CS1)\nFLAG0 \u2500\u25ba PA2 (EXTI2)", "#4ADE80", face_hi, alpha=a_val, fs_title=8.1, fs_sub=6.8, lw=lw_val, focus_list=focus_zones)
        _draw_hw_box(ax, 5.45, 1.72, 1.75, 1.92, "DD2: \u0426\u041e\u0421 #2\nADSP-21369", "SPI Slave\nSPIDS \u25c4\u2500 PB0 (CS2)\nFLAG0 \u2500\u25ba PB1 (EXTI1)", "#FBBF24", face_hi, alpha=a_val, fs_title=8.1, fs_sub=6.8, lw=lw_val, focus_list=focus_zones)

        l_rows = [
            (5.55, "1\u20133. PB13 (SCK), PB15 (MOSI), PB14 (MISO) \u2192 \u041e\u0431\u0449\u0430\u044f \u0448\u0438\u043d\u0430 SPI2", "#38BDF8", 5.42),
            (4.90, "5. PA1 (SPI_CS_DSP1 = 0) \u2500\u2500\u25ba SPIDS DD1 (\u0412\u044b\u0431\u043e\u0440 \u0426\u041e\u0421 #1)", "#4ADE80", 5.42),
            (4.25, "7. PA2 (EXTI2) \u25c4\u2500\u2500 FLAG0 DD1 (\u041a\u0432\u0438\u0442\u0430\u043d\u0446\u0438\u044f \u0433\u043e\u0442\u043e\u0432\u043d\u043e\u0441\u0442\u0438 #1)", "#4ADE80", 5.42),
            (3.40, "4. PA3 (RST_DSP) \u2500\u2500\u25ba \u041e\u0431\u0449\u0438\u0439 \u0430\u043f\u043f\u0430\u0440\u0430\u0442\u043d\u044b\u0439 \u0441\u0431\u0440\u043e\u0441 RESET DD1 \u0438 DD2", "#F87171", 5.42),
            (2.75, "6. PB0 (SPI_CS_DSP2 = 0) \u2500\u2500\u25ba SPIDS DD2 (\u0412\u044b\u0431\u043e\u0440 \u0426\u041e\u0421 #2)", "#FBBF24", 5.42),
            (2.05, "8. PB1 (EXTI1) \u25c4\u2500\u2500 FLAG0 DD2 (\u041a\u0432\u0438\u0442\u0430\u043d\u0446\u0438\u044f \u0433\u043e\u0442\u043e\u0432\u043d\u043e\u0441\u0442\u0438 #2)", "#FBBF24", 5.42),
        ]
        for ly, ltxt, lcol, x1 in l_rows:
            _draw_bus_arrow(ax, 2.43, ly, x1, ly, lcol, ltxt, alpha=a_val, bidir=True, ly_off=0.12, focus_list=focus_zones)
        packets.extend([
            (2.43, 4.90, 5.42, 4.90, COL_GREEN),
            (2.43, 2.75, 5.42, 2.75, COL_GOLD),
        ])
        return {"focus_zones": focus_zones, "plot_reveal": plot_reveal, "curve_dots": curve_dots, "packets": packets}

    if mode == "mailbox_flag0":
        ax.text(0.75, 6.20, "\u0424\u043e\u0440\u043c\u0430\u0442 \u043a\u0430\u0434\u0440\u0430 \u043f\u0440\u043e\u0442\u043e\u043a\u043e\u043b\u0430 \u00ab\u041f\u043e\u0447\u0442\u043e\u0432\u043e\u0433\u043e \u044f\u0449\u0438\u043a\u0430\u00bb (Mailbox \u0432 \u0411\u043b\u043e\u043a\u0435 3 SRAM, \u0441\u0442\u0440. 42\u201344 \u041f\u0417):", color="#38BDF8", fontsize=8.6, weight="bold")
        pkt_fields = [
            ("SYNC", "0x55AA\n(16 \u0431\u0438\u0442)", "#38BDF8", 1.15),
            ("CMD_ID", "0xA5 / 0xB2\n\u041a\u043e\u0434 \u043a\u043e\u043c\u0430\u043d\u0434\u044b", "#4ADE80", 1.25),
            ("LEN", "N \u0441\u043b\u043e\u0432\n(16 \u0431\u0438\u0442)", "#FBBF24", 1.10),
            ("PAYLOAD", "\u041f\u0430\u0440\u0430\u043c\u0435\u0442\u0440\u044b / \u043a\u043e\u044d\u0444\u0444.\n(32-\u0431\u0438\u0442 \u0441\u043b\u043e\u0432\u0430)", "#C084FC", 1.65),
            ("CRC16", "\u041f\u043e\u043b\u0438\u043d\u043e\u043c\n0x8005", "#F87171", 1.05),
        ]
        cur_x = 0.72
        for ft, fs, fcol, fw in pkt_fields:
            _draw_hw_box(ax, cur_x, 4.78, fw, 1.20, ft, fs, fcol, face_hi, alpha=a_val, fs_title=8.1, fs_sub=6.8, lw=lw_val, focus_list=focus_zones)
            cur_x += fw + 0.07

        ax.text(0.75, 4.35, "\u0410\u0441\u0438\u043d\u0445\u0440\u043e\u043d\u043d\u043e\u0435 \u043e\u0431\u0441\u043b\u0443\u0436\u0438\u0432\u0430\u043d\u0438\u0435 \u0431\u0435\u0437 \u0441\u0440\u044b\u0432\u0430 \u0430\u0443\u0434\u0438\u043e\u043f\u043e\u0442\u043e\u043a\u0430 SPORT0 (96 \u043a\u0413\u0446):", color="#4ADE80", fontsize=8.5, weight="bold")
        mb_stages = [
            ("1. \u0424\u043e\u043d\u043e\u0432\u044b\u0439 DMA SPI (\u043d\u0438\u0437\u0448\u0438\u0439 \u043f\u0440\u0438\u043e\u0440.)", "STM32 \u043e\u043f\u0443\u0441\u043a\u0430\u0435\u0442 CS=0 (PA1/PB0) \u0438 \u043f\u0435\u0440\u0435\u0434\u0430\u0451\u0442 \u043f\u0430\u043a\u0435\u0442;\nDMA SPI \u043f\u0438\u0448\u0435\u0442 \u0432 Mailbox (\u0411\u043b\u043e\u043a 3), \u043d\u0435 \u0442\u043e\u0440\u043c\u043e\u0437\u044f SPORT0!", "#38BDF8", 3.25),
            ("2. \u041f\u0440\u043e\u0432\u0435\u0440\u043a\u0430 CRC16 \u0432 \u0444\u043e\u043d\u043e\u0432\u043e\u043c \u0446\u0438\u043a\u043b\u0435", "\u0412 \u043f\u0430\u0443\u0437\u0430\u0445 \u043c\u0435\u0436\u0434\u0443 \u043e\u0442\u0441\u0447\u0451\u0442\u0430\u043c\u0438 96 \u043a\u0413\u0446 \u044f\u0434\u0440\u043e \u043f\u0440\u043e\u0432\u0435\u0440\u044f\u0435\u0442 CRC16\n\u0438 \u0430\u0442\u043e\u043c\u0430\u0440\u043d\u043e \u043e\u0431\u043d\u043e\u0432\u043b\u044f\u0435\u0442 \u0440\u0435\u0436\u0438\u043c / \u043a\u043e\u044d\u0444\u0444\u0438\u0446\u0438\u0435\u043d\u0442\u044b", "#FBBF24", 2.45),
            ("3. \u0410\u043f\u043f\u0430\u0440\u0430\u0442\u043d\u0430\u044f \u043a\u0432\u0438\u0442\u0430\u043d\u0446\u0438\u044f FLAG0 \u2191", "\u0426\u041e\u0421 \u043f\u043e\u0434\u043d\u0438\u043c\u0430\u0435\u0442 FLAG0 \u2192 \u0432\u0445\u043e\u0434 PA2 / PB1 STM32 \u0432\u044b\u0437\u044b\u0432\u0430\u0435\u0442\n\u043f\u0440\u0435\u0440\u044b\u0432\u0430\u043d\u0438\u0435 EXTI (\u0431\u0435\u0437 \u0445\u043e\u043b\u043e\u0441\u0442\u043e\u0433\u043e \u043e\u043f\u0440\u043e\u0441\u0430 \u0448\u0438\u043d\u044b!)", "#4ADE80", 1.65),
        ]
        for st, ss, scol, sy in mb_stages:
            _draw_hw_box(ax, 0.72, sy, 6.48, 0.72, st, ss, scol, face_hi, alpha=a_val, fs_title=7.8, fs_sub=6.7, lw=lw_val, focus_list=focus_zones)
        packets.append((0.90, 5.38, 6.90, 5.38, COL_CYAN))
        return {"focus_zones": focus_zones, "plot_reveal": plot_reveal, "curve_dots": curve_dots, "packets": packets}

    if mode == "polyphase_kaiser":
        ax.text(0.75, 6.20, "6-\u0444\u0430\u0437\u043d\u0430\u044f \u043f\u043e\u043b\u0438\u0444\u0430\u0437\u043d\u0430\u044f \u0441\u0442\u0440\u0443\u043a\u0442\u0443\u0440\u0430 \u041a\u0418\u0425-\u0444\u0438\u043b\u044c\u0442\u0440\u0430 (N=384, L=M=6 \u2192 64 \u043e\u0442\u0432\u043e\u0434\u0430/\u0444\u0430\u0437\u0443, \u0441\u0442\u0440. 53\u201364):", color="#38BDF8", fontsize=8.5, weight="bold")
        for idx in range(6):
            bx = 0.72 + idx * 1.09
            bcol = "#4ADE80" if idx % 2 == 0 else "#38BDF8"
            _draw_hw_box(ax, bx, 4.65, 1.00, 1.32, f"E{idx}(z)", "64 \u043e\u0442\u0432\u043e\u0434\u0430\n(384 / 6)\n64 MAC", bcol, face_hi, alpha=a_val, fs_title=8.2, fs_sub=6.7, lw=lw_val, focus_list=focus_zones)
        packets.append((0.90, 5.31, 6.90, 5.31, COL_GREEN))

        _draw_plot_box(ax, 0.72, 1.62, 6.48, 2.75, "\u0410\u0427\u0425 \u0424\u041d\u0427 \u0441 \u043e\u043a\u043d\u043e\u043c \u041a\u0430\u0439\u0437\u0435\u0440\u0430 (\u03b2 = 6,76, F_pass = 3,4 \u043a\u0413\u0446, F_stop = 4,0 \u043a\u0413\u0446, A_stop = -68,5 \u0434\u0411):", "#4ADE80", "f, \u043a\u0413\u0446", y_zero_frac=0.08)
        u_arr = np.linspace(0.0, 1.0, 500)
        x_arr = 0.84 + u_arr * 6.24
        trans = 1.0 / (1.0 + np.exp((u_arr - 0.36) / 0.020))
        rip = 0.14 * (1.0 - trans) * np.abs(np.cos(2.0 * np.pi * 10.0 * u_arr))
        y_kaiser = 1.85 + 1.95 * trans + rip
        ax.plot(x_arr, y_kaiser, color="#4ADE80", lw=2.4 if lit else 1.1, alpha=a_val)
        ax.plot([0.84, 7.08], [2.12, 2.12], color="#F87171", lw=1.3, ls="--", alpha=a_val)
        ax.text(5.35, 2.26, "\u041f\u043e\u0434\u0430\u0432\u043b\u0435\u043d\u0438\u0435 -68,5 \u0434\u0411 (\u043d\u043e\u0440\u043c\u0430 \u2264 -66 \u0434\u0411)", ha="center", va="center", color="#F87171", fontsize=7.4, weight="bold", alpha=a_val)
        ax.text(5.35, 3.65, "\u042d\u043a\u043e\u043d\u043e\u043c\u0438\u044f 6\u00d7: 3,072 MMAC/\u0441 \u0432\u043c\u0435\u0441\u0442\u043e 18,432", ha="center", va="center", color="#FBBF24", fontsize=7.5, weight="bold", alpha=a_val)
        plot_reveal = (0.72, 1.62, 6.48, 2.75)
        curve_dots.append((x_arr, y_kaiser, COL_GREEN, 1.85))
        return {"focus_zones": focus_zones, "plot_reveal": plot_reveal, "curve_dots": curve_dots, "packets": packets}

    ax.text(0.75, 6.20, "\u041a\u0430\u0440\u0442\u0430-\u0430\u0443\u0434\u0438\u0442 6 \u0442\u043e\u043d\u043a\u0438\u0445 \u043c\u0435\u0441\u0442 \u0447\u0435\u0440\u0442\u0435\u0436\u0430 \u041a\u041d\u0424\u0423.411711.001 \u042d2 \u0434\u043b\u044f \u0437\u0430\u0449\u0438\u0442\u044b \u043d\u0430 \u00ab\u041e\u0442\u043b\u0438\u0447\u043d\u043e\u00bb:", color="#38BDF8", fontsize=8.6, weight="bold")
    audit_cards = [
        ("1. \u0418\u043d\u0434\u0438\u043a\u0430\u0442\u043e\u0440 HG1 (\u042d2)", "\u041f\u0440\u044f\u043c\u043e\u0435 \u043f\u043e\u0434\u043a\u043b\u044e\u0447\u0435\u043d\u0438\u0435 \u043a PC0..PC6\nSTM32 \u0447\u0435\u0440\u0435\u0437 R1..R7 (\u0431\u0435\u0437 \u0440\u0435\u0433\u0438\u0441\u0442\u0440\u0430)", "#38BDF8"),
        ("2. \u041a\u0432\u0430\u0440\u0446\u044b ZQ1 \u0438 G1", "ZQ1 = 8 \u041c\u0413\u0446 (PLL \u00d79 = 72 \u041c\u0413\u0446)\nG1 = 24,576 \u041c\u0413\u0446 \u0434\u043b\u044f AD1938", "#4ADE80"),
        ("3. \u0421\u0443\u043f\u0435\u0440\u0432\u0438\u0437\u043e\u0440 DD4 ADM708", "\u0412\u044b\u0432.1 MR \u2190 SB1, \u0412\u044b\u0432.6 WDI \u2190 PB9\n\u0412\u044b\u0432.7 RESET \u2192 NRST DD3 (200 \u043c\u0441)", "#FBBF24"),
        ("4. \u041c\u0430\u0442\u0440\u0438\u0446\u0430 SRU (DAI)", "\u041f\u0440\u043e\u0433\u0440\u0430\u043c\u043c\u043d\u0430\u044f \u043a\u043e\u043c\u043c\u0443\u0442\u0430\u0446\u0438\u044f DAI_P01..04\n\u0432 init_sru (\u0441\u0442\u0440. 75 \u041f\u0417)", "#C084FC"),
        ("5. \u0412\u0445\u043e\u0434 DA1 + \u0424\u0412\u0427 AD1938", "\u041e\u0423 DA1 (AD822) \u2192 1 \u0412 \u0421\u041a\u0417\n+ \u0446\u0438\u0444\u0440\u043e\u0432\u043e\u0439 \u0424\u0412\u0427 Reg 0x0E=0x02", "#F87171"),
        ("6. \u041c\u043e\u0441\u0442 \u043d\u0430 \u0441\u0442\u0440. 78 \u041f\u0417", "4 \u043a\u043e\u043c\u0430\u043d\u0434\u044b \u0441\u0445\u0435\u043c\u044b \u0413\u043e\u0440\u043d\u0435\u0440\u0430 cos(x)\n\u0432\u043d\u0443\u0442\u0440\u0438 dma_rx_isr (SPORT0 DMA)", "#4ADE80"),
    ]
    for idx, (at, asub, acol) in enumerate(audit_cards):
        col_i = idx % 2
        row_i = idx // 2
        cx = 0.72 + col_i * 3.32
        cy = 4.65 - row_i * 1.48
        _draw_hw_box(ax, cx, cy, 3.16, 1.30, at, asub, acol, face_hi, alpha=a_val, fs_title=8.1, fs_sub=6.9, lw=lw_val, focus_list=focus_zones)
    return {"focus_zones": focus_zones, "plot_reveal": plot_reveal, "curve_dots": curve_dots, "packets": packets}


def build_scene_visual_layers(
    spec: Dict[str, Any],
) -> Tuple[np.ndarray, np.ndarray, Dict[str, Any]]:
    """
    Pre-render both the `dim` and `lit` anti-aliased 1280x720 Matplotlib canvases
    for a scene once. Returns `(dim_rgb_arr, lit_rgb_arr, anim_meta)`.
    """
    fig_dim, ax_dim = _new_base_fig(spec["header"])
    _draw_scene_mode(ax_dim, spec["mode"], lit=False)
    _draw_right_info_panel(
        ax_dim,
        spec["eq1"],
        "#38BDF8",
        spec["eq2"],
        "#4ADE80",
        spec["bullets"],
    )
    img_dim = _fig_to_rgb(fig_dim)

    fig_lit, ax_lit = _new_base_fig(spec["header"])
    anim_meta = _draw_scene_mode(ax_lit, spec["mode"], lit=True)
    _draw_right_info_panel(
        ax_lit,
        spec["eq1"],
        "#38BDF8",
        spec["eq2"],
        "#4ADE80",
        spec["bullets"],
    )
    img_lit = _fig_to_rgb(fig_lit)

    return np.asarray(img_dim, dtype=np.uint8), np.asarray(img_lit, dtype=np.uint8), anim_meta


def _blend_subpixel_packet(
    frame_arr: np.ndarray,
    xf: float,
    yf: float,
    col: Tuple[int, int, int],
    radius_px: int = 12,
) -> None:
    """Blend a sub-pixel anti-aliased glowing dot/packet at exact float figure coords `(xf, yf)`."""
    px = xf * 100.0
    py = (7.2 - yf) * 100.0
    ix, iy = int(round(px)), int(round(py))
    r = radius_px
    x0, x1 = max(0, ix - r), min(1280, ix + r + 1)
    y0, y1 = max(0, iy - r), min(720, iy + r + 1)
    if x0 >= x1 or y0 >= y1:
        return
    yy, xx = np.ogrid[y0:y1, x0:x1]
    d2 = (xx.astype(np.float32) - px) ** 2 + (yy.astype(np.float32) - py) ** 2
    glow = np.clip(np.exp(-d2 / 24.0) * 0.88, 0.0, 1.0)[..., None]
    core = np.clip(np.exp(-d2 / 5.0), 0.0, 1.0)[..., None]
    target_col = np.array(col, dtype=np.float32).reshape((1, 1, 3))
    white_col = np.array([255.0, 255.0, 255.0], dtype=np.float32).reshape((1, 1, 3))
    patch = frame_arr[y0:y1, x0:x1].astype(np.float32)
    patch = patch * (1.0 - glow) + target_col * glow
    patch = patch * (1.0 - core * 0.82) + white_col * (core * 0.82)
    frame_arr[y0:y1, x0:x1] = np.clip(patch, 0.0, 255.0).astype(np.uint8)


def _blend_vertical_stem(
    frame_arr: np.ndarray,
    xf: float,
    yf_a: float,
    yf_b: float,
    col: Tuple[int, int, int],
) -> None:
    """Blend a short anti-aliased vertical stem inside a plot from axis `yf_a` to curve point `yf_b`."""
    px = xf * 100.0
    py_a = (7.2 - yf_a) * 100.0
    py_b = (7.2 - yf_b) * 100.0
    y0 = max(0, int(round(min(py_a, py_b))))
    y1 = min(720, int(round(max(py_a, py_b))) + 1)
    ix = int(round(px))
    x0, x1 = max(0, ix - 3), min(1280, ix + 4)
    if x0 >= x1 or y0 >= y1:
        return
    xx = np.arange(x0, x1, dtype=np.float32).reshape((1, -1, 1))
    w_x = (0.55 * np.exp(-0.5 * ((xx - px) / 1.1) ** 2))
    target_col = np.array(col, dtype=np.float32).reshape((1, 1, 3))
    patch = frame_arr[y0:y1, x0:x1].astype(np.float32)
    frame_arr[y0:y1, x0:x1] = np.clip(patch * (1.0 - w_x) + target_col * w_x, 0.0, 255.0).astype(np.uint8)


def _draw_focus_spotlight(
    img_rgb: Image.Image,
    zx: float,
    zy: float,
    zw: float,
    zh: float,
    col: Tuple[int, int, int],
    local_u: float,
) -> Image.Image:
    """Draw a 2x-supersampled glowing rounded highlight border & corner brackets around an active block."""
    pad = 0.05
    x0 = max(0, int(round((zx - pad) * 100.0)) - 8)
    y0 = max(0, int(round((7.2 - (zy + zh + pad)) * 100.0)) - 8)
    x1 = min(1280, int(round((zx + zw + pad) * 100.0)) + 8)
    y1 = min(720, int(round((7.2 - (zy - pad)) * 100.0)) + 8)
    w1, h1 = x1 - x0, y1 - y0
    if w1 <= 8 or h1 <= 8:
        return img_rgb

    ov2 = Image.new("RGBA", (w1 * 2, h1 * 2), (0, 0, 0, 0))
    d2 = ImageDraw.Draw(ov2)
    pulse = 0.85 + 0.15 * math.sin(2.0 * math.pi * local_u)
    a_glow = int(round(95 * pulse))
    a_main = int(round(245 * pulse))

    # Outer soft halo + inner crisp border + white highlight rim
    d2.rounded_rectangle([6, 6, w1 * 2 - 7, h1 * 2 - 7], radius=22, outline=(*col, a_glow), width=10)
    d2.rounded_rectangle([12, 12, w1 * 2 - 13, h1 * 2 - 13], radius=18, outline=(*col, a_main), width=5)
    d2.rounded_rectangle([14, 14, w1 * 2 - 15, h1 * 2 - 15], radius=16, outline=(255, 255, 255, 150), width=2)

    ov1 = ov2.resize((w1, h1), resample=Image.Resampling.BILINEAR)
    rgba = img_rgb.convert("RGBA")
    rgba.alpha_composite(ov1, dest=(x0, y0))
    return rgba.convert("RGB")


def render_zero_jitter_frame(
    dim_arr: np.ndarray,
    lit_arr: np.ndarray,
    anim_meta: Dict[str, Any],
    spec: Dict[str, Any],
    flow_sc: FlowScene,
    u: float,
    f_sub: Any,
) -> Image.Image:
    """
    Composite a single 1280x720 frame at progress `u in [0, 1]` with:
    1. Whole-block sequential illumination & spotlighting (`focus_zones`) — NO vertical slicing line!
    2. Bounded plot curve reveal (`plot_reveal`) + curve-following moving dots (`curve_dots`).
    3. Sub-pixel glowing bus packets (`packets`) and rotating DAG1 ring pointer.
    4. Synchronized studio subtitle bar at the bottom.
    """
    u_clamped = max(0.01, min(0.995, float(u)))
    frame_arr = dim_arr.copy()

    # 1. Whole-block sequential illumination (never slices blocks in half)
    zones = anim_meta.get("focus_zones", [])
    act_zone: Optional[Tuple[float, float, float, float, Tuple[int, int, int]]] = None
    loc_u = 0.5
    if zones:
        f_z = u_clamped * len(zones)
        act_idx = min(len(zones) - 1, int(f_z))
        loc_u = f_z - act_idx
        for z_i in range(act_idx + 1):
            zx, zy, zw, zh, zcol = zones[z_i]
            bx0 = max(0, int(round((zx - 0.05) * 100.0)))
            bx1 = min(1280, int(round((zx + zw + 0.05) * 100.0)))
            by0 = max(0, int(round((7.2 - (zy + zh + 0.05)) * 100.0)))
            by1 = min(720, int(round((7.2 - (zy - 0.05)) * 100.0)))
            if bx0 >= bx1 or by0 >= by1:
                continue
            if z_i < act_idx:
                frame_arr[by0:by1, bx0:bx1] = lit_arr[by0:by1, bx0:bx1]
            else:
                w_z = min(1.0, 0.35 + loc_u * 2.2)
                lit_patch = lit_arr[by0:by1, bx0:bx1].astype(np.float32)
                dim_patch = frame_arr[by0:by1, bx0:bx1].astype(np.float32)
                frame_arr[by0:by1, bx0:bx1] = (lit_patch * w_z + dim_patch * (1.0 - w_z)).astype(np.uint8)
        act_zone = zones[act_idx]

    # 2. Bounded progressive curve reveal strictly inside the plot panel (if present)
    plot_rev = anim_meta.get("plot_reveal")
    if plot_rev is not None:
        px0_f, py0_f, pw_f, ph_f = plot_rev
        px0 = max(0, int(round(px0_f * 100.0)))
        px1 = min(1280, int(round((px0_f + pw_f) * 100.0)))
        py0 = max(0, int(round((7.2 - (py0_f + ph_f)) * 100.0)))
        py1 = min(720, int(round((7.2 - py0_f) * 100.0)))
        if px1 > px0 and py1 > py0:
            x_cur_px = (px0_f + 0.12 + u_clamped * (pw_f - 0.24)) * 100.0
            x_idx = np.arange(px0, px1, dtype=np.float32)
            alpha_1d = (0.5 * (1.0 - np.tanh((x_idx - x_cur_px) / 2.5))).reshape((1, -1, 1))
            lit_sl = lit_arr[py0:py1, px0:px1].astype(np.float32)
            dim_sl = frame_arr[py0:py1, px0:px1].astype(np.float32)
            frame_arr[py0:py1, px0:px1] = np.clip(lit_sl * alpha_1d + dim_sl * (1.0 - alpha_1d), 0.0, 255.0).astype(np.uint8)

    # 3. Curve-following moving dots with short vertical stems to the plot axis
    for x_arr, y_arr, dot_col, y_axis in anim_meta.get("curve_dots", []):
        xf_dot = float(x_arr[0] + u_clamped * (x_arr[-1] - x_arr[0]))
        yf_dot = float(np.interp(xf_dot, x_arr, y_arr))
        _blend_vertical_stem(frame_arr, xf_dot, y_axis, yf_dot, dot_col)
        _blend_subpixel_packet(frame_arr, xf_dot, yf_dot, dot_col, radius_px=13)

    # 4. Sub-pixel glowing bus packets traveling along schematic arrows
    for idx, (x0, y0, x1, y1, col) in enumerate(anim_meta.get("packets", [])):
        phase = (u_clamped * 3.5 + idx * 0.31) % 1.0
        px_f = x0 + (x1 - x0) * phase
        py_f = y0 + (y1 - y0) * phase
        _blend_subpixel_packet(frame_arr, px_f, py_f, col, radius_px=11)

    # 5. Special rotating pointer I0 inside DAG1 circular buffer ring (Scene l2_2)
    if spec["mode"] == "sram_dag":
        cx, cy, r_ring = 1.95, 2.75, 0.76
        ang = 2.0 * math.pi * ((u_clamped * 3.0) % 1.0)
        for frac in (0.35, 0.68, 1.0):
            _blend_subpixel_packet(
                frame_arr,
                cx + (r_ring * frac) * math.cos(ang),
                cy + (r_ring * frac) * math.sin(ang),
                COL_GREEN if frac == 1.0 else COL_GOLD,
                radius_px=11,
            )

    # 6. Apply 2x-supersampled glowing rounded spotlight frame around active whole block
    final_rgb = Image.fromarray(frame_arr, mode="RGB")
    if act_zone is not None:
        zx, zy, zw, zh, zcol = act_zone
        final_rgb = _draw_focus_spotlight(final_rgb, zx, zy, zw, zh, zcol, loc_u)

    _draw_wildmathing_subtitles(final_rgb, flow_sc, float(u_clamped), f_sub)
    return final_rgb
