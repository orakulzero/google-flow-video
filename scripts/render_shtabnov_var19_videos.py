#!/usr/bin/env python3
"""
Shtabnov A. R. Variant 19 DSP Coursework Defense Video Generator
(@WildMathing / Manim 1:1 Vertical-Projection Style, 1280x720 HD @ 24 fps).

Covers all 7 modules (16 scenes: l0_1..l6_2) of Shtabnov's Defense Cheatsheet:
- Cipher `A, 1, 3, 2, 2, 0, 2, 9` & 79-page PZ Navigator
- Assoc. Prof. A. N. Dedov's 5 Defense Questions
- Polyphase Kaiser FIR Filter (N=384, L=M=6) & 6 Subtle Points of A2 Schematic E2

Outputs to:
- `e:/ANTIGRAVITY/flow_video_testbench/output/shtabnov_var19_videos/`
- `E:/STUDY_NEW_GEN/DSP/shtabnov_defense/videos/` (if present on disk)
"""

from __future__ import annotations

import asyncio
import json
import math
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Tuple

import imageio_ffmpeg
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.render_dsp_cheatsheet_videos import (
    _draw_dual_vertical_axes,
    _draw_right_info_panel,
    _fig_to_rgb,
    _new_base_fig,
)
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
from scripts.shtabnov_scenes_spec import SHTABNOV_MODULES_SPEC
from scripts.shtabnov_visual_engines import (
    build_scene_visual_layers,
    render_zero_jitter_frame,
)
from src.flow_bridge import (
    FlowClient,
    FlowEducationalCompositor,
    FlowScene,
    build_srt_subtitles,
    build_webvtt_subtitles,
)

GX0 = 0.92
GW = 6.35
YC_TOP = 5.05
YC_BOT = 2.45
AMP_Y = 0.86


def _eval_mode_pair(mode: str, u: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """
    Evaluate normalized upper `y_top(u)` and lower `y_bot(u)` curves in `[-1, +1]`
    for `u in [0, 1]` so that every `u` shares an exact 1:1 vertical projection.
    """
    u = np.asarray(u, dtype=float)
    if mode == "cipher_isolation":
        # Upper: slow SPI2 / keypad burst pulses from DD3 (STM32)
        gate = ((np.sin(2.0 * np.pi * 2.0 * u) > 0.35)).astype(float)
        y_top = 0.78 * gate * np.sign(np.sin(2.0 * np.pi * 14.0 * u))
        # Lower: uninterrupted 96 kHz SPORT0 audio stream between AD1938 and ADSP-21369
        y_bot = 0.85 * np.cos(np.sin(2.0 * np.pi * 2.0 * u))
        return y_top, y_bot

    if mode == "cos_transform":
        # Upper: input x(n) in [-1, +1] rad inside rx_buf
        x_val = np.sin(2.0 * np.pi * 1.5 * u)
        y_top = 0.88 * x_val
        # Lower: Horner output y(n) = cos(x(n)) mapped to [-0.85, +0.85]
        cos_val = np.cos(x_val)  # in [0.5403, 1.0]
        y_bot = ((cos_val - 0.77) / 0.23) * 0.82
        return y_top, y_bot

    if mode == "bessel_spectrum":
        # Upper: nonlinear time wave y(t) = cos(sin(2*pi*f0*t))
        x_val = np.sin(2.0 * np.pi * 2.0 * u)
        y_top = ((np.cos(x_val) - 0.77) / 0.23) * 0.82
        # Lower: Bessel even-harmonic spectral peaks at u = 0.05 (DC), 0.25 (20k), 0.50 (40k), 0.75 (60k)
        centers = [(0.06, 0.90), (0.28, 0.68), (0.52, 0.38), (0.76, -0.45)]
        y_bot = np.full_like(u, -0.75)
        for uc, h in centers:
            y_bot = np.maximum(y_bot, h * np.exp(-((u - uc) / 0.032) ** 2) - 0.75 * (1.0 - np.exp(-((u - uc) / 0.032) ** 2)))
        return y_top, y_bot

    if mode == "horner_poly":
        # Upper: x in [-1, +1] -> cos(x)
        x_val = 2.0 * u - 1.0
        y_top = ((np.cos(x_val) - 0.54) / 0.46) * 1.6 - 0.80
        # Lower: normalized Chebyshev/Taylor 6th-order residual error ripple
        y_bot = 0.72 * np.cos(6.0 * np.arccos(np.clip(x_val, -1.0, 1.0))) * (0.4 + 0.6 * (x_val**2))
        return y_top, y_bot

    if mode == "enob_tangent":
        # Upper: |y'(x)| = |sin(x)| slope magnitude on x in [-1, +1]
        x_val = 2.0 * u - 1.0
        y_top = 1.65 * np.abs(np.sin(x_val)) - 0.82
        # Lower: error amplification factor k(x) = tan(|x|) / 1.557
        y_bot = 1.65 * (np.tan(np.abs(x_val)) / math.tan(1.0)) - 0.82
        return y_top, y_bot
    if mode == "sharc_float":
        # Upper: 16-bit fixed-point quantized staircase with clipping risk
        raw = np.sin(2.0 * np.pi * 1.5 * u)
        y_top = np.round(raw * 3.5) / 3.5 * 0.85
        # Lower: 32/40-bit IEEE-754 floating-point exact Horner evaluation
        y_bot = ((np.cos(raw) - 0.77) / 0.23) * 0.84
        return y_top, y_bot

    if mode == "sram_dag":
        # Upper: dual-bus Harvard simultaneous DM(I0,M0) + PM(I8,M8) fetch pulses
        y_top = 0.78 * np.sin(2.0 * np.pi * 8.0 * u) * np.cos(2.0 * np.pi * 1.0 * u)
        # Lower: circular buffer pointer I0 modulo L0 sawtooth wrap-around
        saw = ((u * 3.0) % 1.0) * 1.64 - 0.82
        y_bot = saw
        return y_top, y_bot

    if mode == "sigma_delta":
        # Upper: high-rate 64x oversampled Sigma-Delta PDM pulse density modulation
        analog = np.sin(2.0 * np.pi * 1.2 * u)
        carrier = np.sin(2.0 * np.pi * 28.0 * u)
        y_top = 0.78 * np.where(analog >= 0.75 * carrier, 1.0, -1.0)
        # Lower: Noise Shaping high-pass spectrum pushed above f_0 and cut by decimator
        noise_hp = -0.75 + 1.55 * (u**2.4)
        decim_mask = np.where(u <= 0.42, 0.78 * np.exp(-((u - 0.16) / 0.08) ** 2), -0.68)
        y_bot = np.where(u <= 0.42, decim_mask, noise_hp * 0.85)
        return y_top, y_bot

    if mode == "sport_spib":
        # Upper: SPORT0 I2S frame sync ALRCLK + ABCLK + 24-bit audio data word
        alr = np.where(((u * 2.0) % 1.0) < 0.5, 0.72, -0.72)
        bclk = 0.22 * np.sin(2.0 * np.pi * 24.0 * u)
        y_top = np.clip(alr + bclk, -0.88, 0.88)
        # Lower: SPIB CLATCH envelope + 24-bit control word burst (6 registers)
        active = (u >= 0.15) & (u <= 0.85)
        y_bot = np.where(active, 0.75 * np.sign(np.sin(2.0 * np.pi * 18.0 * u)), 0.78)
        return y_top, y_bot

    if mode == "dma_pipeline":
        # Upper: incoming 24-bit integer slots normalized by FLOAT R0 BY -23
        y_top = 0.84 * np.sin(2.0 * np.pi * 2.0 * u)
        # Lower: processed frame in tx_buf after Horner & FIX F0 BY 23
        x_val = np.sin(2.0 * np.pi * 2.0 * u)
        y_bot = ((np.cos(x_val) - 0.77) / 0.23) * 0.84
        return y_top, y_bot

    if mode == "sb1_adm708":
        # Upper: manual button SB1 press on MR input with contact bounce at u in [0.18, 0.46]
        pressed = (u >= 0.18) & (u <= 0.46)
        bounce = ((u >= 0.18) & (u <= 0.23)) | ((u >= 0.43) & (u <= 0.46))
        y_top = np.where(pressed, -0.75, 0.78)
        y_top = np.where(bounce, 0.75 * np.sign(np.sin(2.0 * np.pi * 45.0 * u)), y_top)
        # Lower: clean ADM708 RESET output held low during press + 200 ms POR delay until u = 0.78
        y_bot = np.where((u >= 0.18) & (u <= 0.78), -0.78, 0.78)
        return y_top, y_bot

    if mode == "boot_cfg_8modes":
        # Upper: RST_DSP rising edge at u = 0.28 latching BOOT_CFG1..0 = 00
        y_top = np.where(u < 0.28, -0.76, 0.78)
        # Lower: sequential SPI2 Slave Boot bursts to DD1 (u in 0.32..0.60) and DD2 (u in 0.66..0.94)
        burst1 = (u >= 0.32) & (u <= 0.60)
        burst2 = (u >= 0.66) & (u <= 0.94)
        clk = 0.76 * np.sin(2.0 * np.pi * 22.0 * u)
        y_bot = np.where(burst1 | burst2, clk, -0.72)
        return y_top, y_bot

    if mode == "spi2_8lines":
        # Upper: shared SPI2_SCK + MOSI command packet frames
        pkt = ((u >= 0.12) & (u <= 0.44)) | ((u >= 0.56) & (u <= 0.88))
        y_top = np.where(pkt, 0.78 * np.sin(2.0 * np.pi * 20.0 * u), 0.0)
        # Lower: dedicated chip-select SEL_DSP1 (first window) and SEL_DSP2 (second window)
        y_bot = np.where((u >= 0.12) & (u <= 0.44), -0.78, np.where((u >= 0.56) & (u <= 0.88), 0.78, 0.0))
        return y_top, y_bot

    if mode == "mailbox_flag0":
        # Upper: SPI command written into SRAM Mailbox at u in [0.15, 0.38]
        cmd_win = (u >= 0.15) & (u <= 0.38)
        y_top = np.where(cmd_win, 0.78 * np.sign(np.sin(2.0 * np.pi * 16.0 * u)), -0.65)
        # Lower: background execution & rising edge of FLAG0 -> EXTI at u = 0.62
        y_bot = np.where(u < 0.62, -0.75, 0.80)
        return y_top, y_bot

    if mode == "polyphase_kaiser":
        # Upper: Kaiser-windowed sinc impulse response h(k) of length N = 384
        v = (u - 0.5) * 10.0
        sinc_v = np.sinc(v)
        win = np.i0(6.76 * np.sqrt(np.clip(1.0 - ((u - 0.5) * 2.0) ** 2, 0.0, 1.0))) / np.i0(6.76)
        y_top = 0.88 * sinc_v * win
        # Lower: Magnitude response |H(f)| in dB (flat passband up to u=0.38, -73.2 dB stopband)
        trans = 1.0 / (1.0 + np.exp((u - 0.42) / 0.025))
        rip = 0.12 * (1.0 - trans) * np.abs(np.cos(2.0 * np.pi * 9.0 * u))
        y_bot = -0.78 + 1.56 * trans + rip
        return y_top, y_bot

    # Default / e2_subtle_points:
    # Upper: SRU routing & single-ended 1 Vrms input wave on ADC1LP
    x_val = np.sin(2.0 * np.pi * 2.0 * u)
    y_top = 0.84 * x_val
    # Lower: single-ended output OL1 wave y(n) = cos(x(n))
    y_bot = ((np.cos(x_val) - 0.77) / 0.23) * 0.84
    return y_top, y_bot


def _build_scene_base_image(spec: Dict[str, Any]) -> Image.Image:
    """Build the 1280x720 static matplotlib canvas for a Shtabnov defense scene."""
    fig, ax = _new_base_fig(spec["header"])
    _draw_dual_vertical_axes(
        ax,
        GX0,
        GW,
        YC_TOP,
        YC_BOT,
        AMP_Y,
        spec["top_title"],
        "#38BDF8",
        spec["bot_title"],
        "#4ADE80",
        spec["top_xlab"],
        spec["bot_xlab"],
        n_grid=16,
    )

    u_grid = np.linspace(0.0, 1.0, 500)
    y_top, y_bot = _eval_mode_pair(spec["mode"], u_grid)
    ax.plot(GX0 + u_grid * GW, YC_TOP + AMP_Y * y_top, color="#38BDF8", lw=1.2, alpha=0.26)
    ax.plot(GX0 + u_grid * GW, YC_BOT + AMP_Y * y_bot, color="#4ADE80", lw=1.2, alpha=0.26)

    if spec["mode"] == "bessel_spectrum":
        # Threshold line -66 dB (0.05%) on lower graph
        ax.axhline(
            YC_BOT - 0.15 * AMP_Y,
            xmin=GX0 / 12.8,
            xmax=(GX0 + GW) / 12.8,
            color="#F87171",
            lw=1.1,
            ls="--",
        )
    elif spec["mode"] in ("horner_poly", "enob_tangent", "polyphase_kaiser"):
        ax.axhline(
            YC_BOT + 0.55 * AMP_Y,
            xmin=GX0 / 12.8,
            xmax=(GX0 + GW) / 12.8,
            color="#FBBF24",
            lw=1.0,
            ls="--",
        )

    _draw_right_info_panel(
        ax,
        spec["eq1"],
        "#38BDF8",
        spec["eq2"],
        "#4ADE80",
        spec["bullets"],
    )
    return _fig_to_rgb(fig)


def _to_px1(x_fig: float, y_fig: float) -> Tuple[int, int]:
    """Convert figure coordinates `(0..12.8, 0..7.2)` to 1280x720 pixel coordinates."""
    return int(round(x_fig * 100.0)), int(round((7.2 - y_fig) * 100.0))


def _render_scene_frame(
    base_img: Image.Image,
    spec: Dict[str, Any],
    flow_sc: FlowScene,
    u: float,
    f_sub: Any,
) -> Image.Image:
    """
    Render a single 1280x720 frame at normalized progress `u in [0, 1]` with:
    - Upper progressive curve + discrete sample stems
    - Lower progressive curve + discrete sample stems
    - Active 1:1 vertical golden projection line connecting `(x_tip, y_top_tip)` and `(x_tip, y_bot_tip)`
    - Synchronized WildMathing subtitle bar at the bottom.
    """
    u_clamped = max(0.02, min(0.99, float(u)))
    frame_rgba = base_img.convert("RGBA")
    overlay = Image.new("RGBA", (1280, 720), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    n_pts = max(8, int(220 * u_clamped))
    u_trace = np.linspace(0.0, u_clamped, n_pts)
    y_top_arr, y_bot_arr = _eval_mode_pair(spec["mode"], u_trace)

    pts_top = [_to_px1(GX0 + float(uk) * GW, YC_TOP + AMP_Y * float(yk)) for uk, yk in zip(u_trace, y_top_arr)]
    pts_bot = [_to_px1(GX0 + float(uk) * GW, YC_BOT + AMP_Y * float(yk)) for uk, yk in zip(u_trace, y_bot_arr)]

    if len(pts_top) >= 2:
        draw.line(pts_top, fill=(*COL_CYAN, 255), width=3)
    if len(pts_bot) >= 2:
        draw.line(pts_bot, fill=(*COL_GREEN, 255), width=3)

    # Discrete sample stems & vertical projection lines at 16 grid intervals
    n_grid = 16
    for k in range(1, n_grid + 1):
        uk = k / float(n_grid)
        if uk > u_clamped + 1e-6:
            break
        yt_k, yb_k = _eval_mode_pair(spec["mode"], np.array([uk]))
        xf = GX0 + uk * GW
        yt_f = YC_TOP + AMP_Y * float(yt_k[0])
        yb_f = YC_BOT + AMP_Y * float(yb_k[0])

        p_top_axis = _to_px1(xf, YC_TOP)
        p_top_pt = _to_px1(xf, yt_f)
        p_bot_axis = _to_px1(xf, YC_BOT)
        p_bot_pt = _to_px1(xf, yb_f)

        draw.line([p_top_axis, p_top_pt], fill=(56, 189, 248, 185), width=2)
        draw.line([p_bot_axis, p_bot_pt], fill=(74, 222, 128, 185), width=2)
        _draw_dashed_line_2x(
            draw,
            p_top_pt[0],
            p_top_pt[1],
            p_bot_pt[0],
            p_bot_pt[1],
            (251, 191, 36, 105),
            width=1,
            dash_len=5,
            gap_len=5,
        )

        r_dot = 4
        draw.ellipse([p_top_pt[0] - r_dot, p_top_pt[1] - r_dot, p_top_pt[0] + r_dot, p_top_pt[1] + r_dot], fill=(*COL_CYAN, 255))
        draw.ellipse([p_bot_pt[0] - r_dot, p_bot_pt[1] - r_dot, p_bot_pt[0] + r_dot, p_bot_pt[1] + r_dot], fill=(*COL_GREEN, 255))

    # Active moving 1:1 vertical golden projection cursor at `u_clamped`
    yt_cur, yb_cur = _eval_mode_pair(spec["mode"], np.array([u_clamped]))
    xf_cur = GX0 + u_clamped * GW
    p_cur_top = _to_px1(xf_cur, YC_TOP + AMP_Y * float(yt_cur[0]))
    p_cur_bot = _to_px1(xf_cur, YC_BOT + AMP_Y * float(yb_cur[0]))

    _draw_dashed_line_2x(
        draw,
        p_cur_top[0],
        p_cur_top[1],
        p_cur_bot[0],
        p_cur_bot[1],
        (*COL_GOLD, 255),
        width=3,
        dash_len=7,
        gap_len=5,
    )
    _draw_arrow_2x(
        draw,
        p_cur_top[0],
        p_cur_top[1],
        p_cur_bot[0],
        p_cur_bot[1],
        (*COL_GOLD, 255),
        width=2,
        head_len=10,
    )

    for px, py, col in [(p_cur_top[0], p_cur_top[1], (*COL_CYAN, 255)), (p_cur_bot[0], p_cur_bot[1], (*COL_GREEN, 255))]:
        draw.ellipse([px - 8, py - 8, px + 8, py + 8], fill=(251, 191, 36, 90))
        draw.ellipse([px - 5, py - 5, px + 5, py + 5], fill=col, outline=(255, 255, 255, 255), width=2)

    frame_rgba.alpha_composite(overlay)
    final_rgb = frame_rgba.convert("RGB")
    _draw_wildmathing_subtitles(final_rgb, flow_sc, float(u), f_sub)
    return final_rgb


def _build_html_player(out_dir: Path, modules_meta: List[Dict[str, Any]]) -> Path:
    """Generate an interactive HTML5 video course navigator for Shtabnov Variant 19."""
    cards_html: List[str] = []
    for m in modules_meta:
        scenes_li = "".join(
            f"<li><code>{s['scene_key']}</code> &mdash; {s['header']} ({s['duration']:.1f} s)</li>"
            for s in m["scenes"]
        )
        cards_html.append(
            f"""
            <div class="card">
              <h2>{m['module_title']}</h2>
              <video controls preload="metadata" width="100%" src="{m['video_file']}"></video>
              <ul class="scene-list">{scenes_li}</ul>
              <p class="links">
                <a href="{m['video_file']}" download>MP4 ({m['duration']:.1f}s)</a> |
                <a href="{m['srt_file']}">SRT</a> |
                <a href="{m['vtt_file']}">WebVTT</a> |
                <a href="{m['contact_sheet']}" target="_blank">Contact Sheet</a>
              </p>
            </div>
            """
        )

    html = f"""<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="utf-8" />
  <title>Shtabnov A. R. Variant 19 — Complete DSP Defense Video Course</title>
  <style>
    body {{
      background: #0b0f19;
      color: #e2e8f0;
      font-family: system-ui, -apple-system, sans-serif;
      margin: 0;
      padding: 28px 36px;
    }}
    h1 {{ color: #38bdf8; margin-bottom: 6px; }}
    .sub {{ color: #94a3b8; margin-bottom: 24px; }}
    .master-box {{
      background: #131c31;
      border: 2px solid #fbbf24;
      border-radius: 12px;
      padding: 20px;
      margin-bottom: 28px;
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(520px, 1fr));
      gap: 22px;
    }}
    .card {{
      background: #131c31;
      border: 1px solid #1e293b;
      border-radius: 10px;
      padding: 16px;
    }}
    .card h2 {{ font-size: 1.06rem; color: #4ade80; margin-top: 0; }}
    .scene-list {{ font-size: 0.9rem; color: #cbd5e1; padding-left: 18px; }}
    .links a {{ color: #38bdf8; text-decoration: none; font-size: 0.9rem; }}
  </style>
</head>
<body>
  <h1>Shtabnov A. R. (Variant 19: A, 1, 3, 2, 2, 0, 2, 9) — DSP Defense Video Course</h1>
  <div class="sub">
    7 Modules &bull; 16 Scenes (1280x720 HD @ 24 fps, WildMathing 1:1 Vertical Projection, Studio Female Narration)
  </div>
  <div class="master-box">
    <h2>Master Compilation — All 7 Modules (16 Defense Lessons)</h2>
    <video controls preload="metadata" width="100%" src="shtabnov_var19_full_defense.mp4"></video>
    <p class="links">
      <a href="shtabnov_var19_full_defense.mp4" download>Download Master MP4</a> |
      <a href="shtabnov_var19_full_defense.srt">Master SRT</a> |
      <a href="shtabnov_var19_full_defense.vtt">Master WebVTT</a> |
      <a href="master_contact_sheet.png" target="_blank">Master Contact Sheet</a>
    </p>
  </div>
  <div class="grid">
    {''.join(cards_html)}
  </div>
</body>
</html>
"""
    index_path = out_dir / "index.html"
    index_path.write_text(html, encoding="utf-8")
    return index_path


async def render_all_shtabnov_videos() -> Dict[str, Any]:
    out_dir = ROOT_DIR / "output" / "shtabnov_var19_videos"
    out_dir.mkdir(parents=True, exist_ok=True)

    compositor = FlowEducationalCompositor(width=1280, height=720, fps=24)
    fps = 24
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    try:
        f_sub = ImageFont.truetype("C:/Windows/Fonts/segoeuib.ttf", 19)
    except Exception:
        f_sub = ImageFont.load_default()

    modules_meta: List[Dict[str, Any]] = []
    all_master_scenes: List[FlowScene] = []
    all_module_mp4s: List[Path] = []
    master_keyframes: List[Image.Image] = []

    for mod in SHTABNOV_MODULES_SPEC:
        mod_id = mod["module_id"]
        mod_scenes_flow: List[FlowScene] = []
        mod_scene_mp4s: List[Path] = []
        mod_keyframes: List[Image.Image] = []
        mod_scene_summaries: List[Dict[str, Any]] = []

        for idx, sc_spec in enumerate(mod["scenes"], start=1):
            narration = sc_spec["narration"]
            flow_sc = FlowScene(
                scene_id=f"scene_{sc_spec['scene_key']}",
                scene_number=idx,
                title=sc_spec["header"],
                visual_prompt=f"WildMathing 1:1 vertical projection for {sc_spec['scene_key']}",
                narration_text=narration,
                tts_narration_text=narration,
                duration_sec=10,
                voice_persona="voice_y0joebp3bwta",
            )

            dim_arr, lit_arr, packets = build_scene_visual_layers(sc_spec)
            scene_mp4 = out_dir / f"scene_{sc_spec['scene_key']}.mp4"

            with tempfile.TemporaryDirectory() as tmp_dir:
                tmp_path = Path(tmp_dir)
                voice_wav = tmp_path / "voiceover.wav"
                dur = await compositor._synthesize_scene_voiceover(
                    scene=flow_sc,
                    language="ru",
                    out_wav=voice_wav,
                )
                total_dur = float(max(dur, 5.0))
                flow_sc.duration_sec = max(5, int(round(total_dur)))
                flow_sc.captions = compositor._build_word_captions(
                    scene_id=flow_sc.scene_id,
                    narration_text=narration,
                    duration_sec=total_dur,
                )
                _align_captions_to_wav(flow_sc.captions, voice_wav)
                mod_scenes_flow.append(flow_sc)

                n_frames = max(48, int(round(total_dur * fps)))
                kf_step = int(n_frames * 0.68)
                kf_path = out_dir / f"keyframe_{sc_spec['scene_key']}.png"
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
                    str(fps),
                    "-i",
                    "-",
                    "-i",
                    str(voice_wav),
                    "-c:v",
                    "libx264",
                    "-pix_fmt",
                    "yuv420p",
                    "-preset",
                    "ultrafast",
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
                    str(scene_mp4),
                ]
                proc = subprocess.Popen(
                    cmd,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                assert proc.stdin is not None
                for s_idx in range(n_frames):
                    u_prog = s_idx / float(max(1, n_frames - 1))
                    frame_rgb = render_zero_jitter_frame(
                        dim_arr, lit_arr, packets, sc_spec, flow_sc, u_prog, f_sub
                    )
                    proc.stdin.write(frame_rgb.tobytes())
                    if s_idx == kf_step:
                        frame_rgb.save(kf_path, format="PNG")
                        mod_keyframes.append(frame_rgb)
                        master_keyframes.append(frame_rgb)
                proc.stdin.close()
                proc.wait(timeout=180)

            mod_scene_mp4s.append(scene_mp4)
            master_sc = FlowScene(
                scene_id=f"master_{sc_spec['scene_key']}",
                scene_number=len(all_master_scenes) + 1,
                title=sc_spec["header"],
                visual_prompt=flow_sc.visual_prompt,
                narration_text=narration,
                tts_narration_text=narration,
                duration_sec=flow_sc.duration_sec,
                captions=flow_sc.captions,
            )
            all_master_scenes.append(master_sc)
            mod_scene_summaries.append(
                {
                    "scene_key": sc_spec["scene_key"],
                    "header": sc_spec["header"],
                    "duration": round(total_dur, 2),
                    "scene_mp4": scene_mp4.name,
                }
            )
            print(f"[SHTABNOV] Rendered scene {sc_spec['scene_key']} ({total_dur:.2f}s) -> {scene_mp4.name}", flush=True)

        # Concatenate module MP4
        mod_mp4 = out_dir / f"{mod_id}.mp4"
        concat_txt = out_dir / f"{mod_id}_concat.txt"
        concat_txt.write_text("\n".join(f"file '{p.name}'" for p in mod_scene_mp4s), encoding="utf-8")
        subprocess.run(
            [ffmpeg_exe, "-y", "-f", "concat", "-safe", "0", "-i", str(concat_txt), "-c", "copy", str(mod_mp4)],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        concat_txt.unlink(missing_ok=True)
        all_module_mp4s.append(mod_mp4)

        mod_srt = out_dir / f"{mod_id}.srt"
        mod_vtt = out_dir / f"{mod_id}.vtt"
        mod_srt.write_text(build_srt_subtitles(mod_scenes_flow), encoding="utf-8")
        mod_vtt.write_text(build_webvtt_subtitles(mod_scenes_flow), encoding="utf-8")

        # Save module contact sheet
        cs_img = Image.new("RGB", (640 * len(mod_keyframes), 360), (13, 17, 26))
        for k_i, kf in enumerate(mod_keyframes):
            cs_img.paste(kf.resize((640, 360), Image.Resampling.LANCZOS), (k_i * 640, 0))
        cs_path = out_dir / f"contact_sheet_m{mod['module_num']}.png"
        cs_img.save(cs_path, format="PNG")

        mod_dur = sum(s.duration_sec for s in mod_scenes_flow)
        modules_meta.append(
            {
                "module_id": mod_id,
                "module_num": mod["module_num"],
                "module_title": mod["module_title"],
                "video_file": mod_mp4.name,
                "srt_file": mod_srt.name,
                "vtt_file": mod_vtt.name,
                "contact_sheet": cs_path.name,
                "duration": round(mod_dur, 2),
                "scenes": mod_scene_summaries,
            }
        )
        print(f"[SHTABNOV] Completed Module {mod['module_num']}: {mod_mp4.name} ({mod_dur:.2f}s)")

    # Concatenate full Master Defense Video across all 7 modules (16 scenes)
    master_mp4 = out_dir / "shtabnov_var19_full_defense.mp4"
    master_concat = out_dir / "master_concat.txt"
    master_concat.write_text("\n".join(f"file '{p.name}'" for p in all_module_mp4s), encoding="utf-8")
    subprocess.run(
        [ffmpeg_exe, "-y", "-f", "concat", "-safe", "0", "-i", str(master_concat), "-c", "copy", str(master_mp4)],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    master_concat.unlink(missing_ok=True)

    master_srt = out_dir / "shtabnov_var19_full_defense.srt"
    master_vtt = out_dir / "shtabnov_var19_full_defense.vtt"
    master_srt.write_text(build_srt_subtitles(all_master_scenes), encoding="utf-8")
    master_vtt.write_text(build_webvtt_subtitles(all_master_scenes), encoding="utf-8")

    # 4x4 Master Contact Sheet (all 16 scenes)
    grid_cs = Image.new("RGB", (4 * 480, 4 * 270), (13, 17, 26))
    for idx, kf in enumerate(master_keyframes[:16]):
        r_i, c_i = divmod(idx, 4)
        grid_cs.paste(kf.resize((480, 270), Image.Resampling.LANCZOS), (c_i * 480, r_i * 270))
    master_cs_path = out_dir / "master_contact_sheet.png"
    grid_cs.save(master_cs_path, format="PNG")

    index_path = _build_html_player(out_dir, modules_meta)

    manifest = {
        "variant": "Shtabnov A. R. — Variant 19 (A, 1, 3, 2, 2, 0, 2, 9)",
        "total_modules": len(modules_meta),
        "total_scenes": len(all_master_scenes),
        "total_duration_sec": round(sum(s.duration_sec for s in all_master_scenes), 2),
        "master_video": str(master_mp4),
        "master_contact_sheet": str(master_cs_path),
        "index_html": str(index_path),
        "modules": modules_meta,
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    # Mirror outputs into E:/STUDY_NEW_GEN/.../shtabnov_defense/videos if folder exists
    ext_study_dir = Path("E:/STUDY_NEW_GEN/\u0426\u041e\u0421/shtabnov_defense")
    if ext_study_dir.exists():
        ext_vid_dir = ext_study_dir / "videos"
        ext_vid_dir.mkdir(parents=True, exist_ok=True)
        for item in out_dir.iterdir():
            if item.is_file():
                shutil.copy2(item, ext_vid_dir / item.name)
        manifest["mirrored_to"] = str(ext_vid_dir)

    return manifest


if __name__ == "__main__":
    res = asyncio.run(render_all_shtabnov_videos())
    print(json.dumps(res, ensure_ascii=False, indent=2))
