"""
src/ttd_visual_scenes_a.py
Dark fantasy procedural visual engine - Scene 1 (Prologue) & Scene 2 (Command).

Zero literal Cyrillic rule: all Russian strings use unicode escapes.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple
from PIL import Image, ImageDraw

from src.ttd_visual_common import (
    COLOR_ARCANE_CYAN,
    COLOR_ARTERIAL_CRIMSON,
    COLOR_MIDNIGHT_STORM,
    COLOR_OBSIDIAN_BLACK,
    COLOR_PITCH_AMBER,
    COLOR_TEXT_WHITE,
    COLOR_WEATHERED_IRON,
    draw_tactical_hud_panel,
    render_brazier_embers,
    render_creeping_black_fog,
    render_lightning_and_ambient,
    render_torrential_rain,
)


def render_scene_01_prologue(
    draw: ImageDraw.ImageDraw,
    t: float,
    duration: float,
    audio_features: Optional[Dict[str, Any]],
    width: int = 1280,
    height: int = 720,
    font_main: Any = None,
    font_sub: Any = None,
) -> None:
    """Scene 1: Cyclopean battlements, blood moon rim light, braziers, fortress telemetry."""
    # Sky and blood moon
    moon_x, moon_y, moon_r = 980, 150, 68
    for r_i in range(moon_r + 40, moon_r, -4):
        alpha = int(45 * (1.0 - (r_i - moon_r) / 40.0))
        draw.ellipse([(moon_x - r_i, moon_y - r_i), (moon_x + r_i, moon_y + r_i)], fill=(180, 20, 30, alpha))
    draw.ellipse([(moon_x - moon_r, moon_y - moon_r), (moon_x + moon_r, moon_y + moon_r)], fill=(220, 38, 38))
    draw.ellipse([(moon_x - moon_r + 15, moon_y - moon_r - 5), (moon_x + moon_r + 15, moon_y + moon_r - 5)], fill=(15, 23, 42))

    # Cyclopean battlement wall and crenellations
    wall_y = 480
    draw.rectangle([(0, wall_y), (width, height)], fill=(25, 33, 50))
    for c_idx, cx in enumerate(range(40, width, 140)):
        draw.rectangle([(cx, wall_y - 50), (cx + 80, wall_y)], fill=(32, 42, 62), outline=COLOR_WEATHERED_IRON, width=2)
    draw.line([(0, wall_y), (width, wall_y)], fill=COLOR_WEATHERED_IRON, width=3)

    # Braziers
    braziers = [(240, wall_y - 20), (1040, wall_y - 20)]
    for bx, by in braziers:
        draw.polygon([(bx - 30, by), (bx + 30, by), (bx + 20, by + 40), (bx - 20, by + 40)], fill=(40, 48, 65), outline=COLOR_WEATHERED_IRON, width=2)
        flame_h = 30 + int(math.sin(t * 8.0 + bx) * 8)
        draw.polygon([(bx - 18, by), (bx + 18, by), (bx, by - flame_h)], fill=COLOR_PITCH_AMBER)
        draw.polygon([(bx - 10, by), (bx + 10, by), (bx, by - int(flame_h * 0.7))], fill=(254, 240, 138))

    render_creeping_black_fog(draw, t, width, height)
    render_brazier_embers(draw, t, braziers)
    render_torrential_rain(draw, t, width, height)
    render_lightning_and_ambient(draw, t, audio_features, width, height)

    # Fortress Telemetry Overlay
    draw_tactical_hud_panel(draw, (48, 84, 480, 236), "\u0422\u0415\u041b\u0415\u041c\u0415\u0422\u0420\u0418\u042f \u041a\u0420\u0415\u041f\u041e\u0421\u0422\u0418", COLOR_ARCANE_CYAN, font_sub)
    draw.text((64, 118), "\u0421\u0415\u041a\u0422\u041e\u0420: \u042e\u0416\u041d\u042b\u0419 \u0420\u0423\u0411\u0415\u0416 (30\u043c)", fill=COLOR_TEXT_WHITE, font=font_sub)
    draw.text((64, 145), "\u0423\u0413\u0420\u041e\u0417\u0410: \u0427\u0401\u0420\u041d\u042b\u0419 \u0422\u0423\u041c\u0410\u041d (300\u043c)", fill=COLOR_ARTERIAL_CRIMSON, font=font_sub)
    draw.text((64, 172), "\u041f\u041e\u0414\u041a\u0420\u0415\u041f\u041b\u0415\u041d\u0418\u042f: 0 (\u0418\u0417\u041e\u041b\u042f\u0426\u0418\u042f)", fill=COLOR_PITCH_AMBER, font=font_sub)
    draw.text((64, 199), "\u0421\u0422\u0410\u0422\u0423\u0421: \u0411\u041e\u0415\u0412\u0410\u042f \u0413\u041e\u0422\u041e\u0412\u041d\u041e\u0421\u0422\u042c", fill=COLOR_ARCANE_CYAN, font=font_sub)


def render_scene_02_command(
    draw: ImageDraw.ImageDraw,
    t: float,
    duration: float,
    audio_features: Optional[Dict[str, Any]],
    width: int = 1280,
    height: int = 720,
    font_main: Any = None,
    font_sub: Any = None,
) -> None:
    """Scene 2: Holographic tactical defense radar, wave vectors, attrition equation, dispatch crystal."""
    # Tactical radar display (x=640, y=340)
    rx, ry = 640, 340
    for r_ring in (70, 140, 210, 280):
        draw.ellipse([(rx - r_ring, ry - r_ring), (rx + r_ring, ry + r_ring)], outline=(6, 182, 212, 120), width=1)
        draw.text((rx + 8, ry - r_ring + 4), f"{r_ring * 10 // 7}\u043c", fill=(6, 182, 212, 180), font=font_sub)

    # Crosshair axes
    draw.line([(rx - 290, ry), (rx + 290, ry)], fill=(6, 182, 212, 80), width=1)
    draw.line([(rx, ry - 290), (rx, ry + 290)], fill=(6, 182, 212, 80), width=1)

    # Rotating radar sweep line
    angle = (t * 1.8) % (2.0 * math.pi)
    sweep_x = rx + math.cos(angle) * 280.0
    sweep_y = ry + math.sin(angle) * 280.0
    draw.line([(rx, ry), (sweep_x, sweep_y)], fill=COLOR_ARCANE_CYAN, width=2)

    # Approaching wave contact vectors
    for w_i in range(5):
        dist = 260.0 - ((t * 22.0 + w_i * 45.0) % 200.0)
        w_ang = math.radians(190.0 + w_i * 8.0)
        wx = rx + math.cos(w_ang) * dist
        wy = ry + math.sin(w_ang) * dist
        draw.ellipse([(wx - 5, wy - 5), (wx + 5, wy + 5)], fill=COLOR_ARTERIAL_CRIMSON)
        draw.line([(wx, wy), (wx + math.cos(w_ang) * 16, wy + math.sin(w_ang) * 16)], fill=COLOR_ARTERIAL_CRIMSON, width=2)

    # Pulsing dispatch crystal (top right: x=1120, y=140)
    rms_val = float(audio_features.get("rms", 0.3)) if audio_features else 0.3
    c_pulse = 20 + int(math.sin(t * 6.0) * 4) + int(rms_val * 14)
    cx_pos, cy_pos = 1120, 140
    draw.ellipse([(cx_pos - c_pulse * 2, cy_pos - c_pulse * 2), (cx_pos + c_pulse * 2, cy_pos + c_pulse * 2)], fill=(6, 182, 212, 40))
    crystal_pts = [(cx_pos, cy_pos - c_pulse), (cx_pos + c_pulse, cy_pos), (cx_pos, cy_pos + c_pulse), (cx_pos - c_pulse, cy_pos)]
    draw.polygon(crystal_pts, fill=(6, 182, 212, 230), outline=(240, 249, 255), width=2)

    render_torrential_rain(draw, t, width, height, num_drops=70)

    # Tactical status and attrition equation HUD
    draw_tactical_hud_panel(draw, (48, 84, 520, 236), "\u0423\u0420\u0410\u0412\u041d\u0415\u041d\u0418\u0415 \u0412\u042b\u0416\u0418\u0412\u0410\u041d\u0418\u042f", COLOR_ARCANE_CYAN, font_sub)
    draw.text((64, 118), "P(SURVIVAL) = f(\u0421\u0442\u0440\u0435\u043b\u044b, \u0429\u0438\u0442, \u041d\u043e\u043b\u044c_\u041f\u0430\u043d\u0438\u043a\u0438)", fill=COLOR_TEXT_WHITE, font=font_sub)
    draw.text((64, 145), "\u041a\u041e\u041c\u0410\u041d\u0414\u0418\u0420: \u041f\u0420\u0418\u041d\u0426 \u042d\u0428 (\u0410\u041a\u0422\u0418\u0412\u0415\u041d)", fill=COLOR_ARCANE_CYAN, font=font_sub)
    draw.text((64, 172), "\u0410\u0412\u0410\u041d\u0413\u0410\u0420\u0414: \u0420\u042b\u0426\u0410\u0420\u042c \u041b\u0423\u041a\u0410\u0421 (\u0429\u0418\u0422 \u041d\u0410 \u041f\u041e\u0417\u0418\u0426\u0418\u0418)", fill=COLOR_PITCH_AMBER, font=font_sub)
    draw.text((64, 199), "\u0421\u041d\u0410\u0419\u041f\u0415\u0420: \u041b\u0418\u041b\u0418 (\u041e\u0416\u0418\u0414\u0410\u041d\u0418\u0415 \u041f\u0420\u0418\u041a\u0410\u0417\u0410)", fill=COLOR_WEATHERED_IRON, font=font_sub)
