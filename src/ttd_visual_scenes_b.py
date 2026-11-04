"""
src/ttd_visual_scenes_b.py
Dark fantasy procedural visual engine - Scene 3 (Vanguard), Scene 4 (Sniper), Scene 5 (Boss).

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
    COLOR_WITCH_FIRE_VIOLET,
    draw_tactical_hud_panel,
    render_creeping_black_fog,
    render_lightning_and_ambient,
    render_torrential_rain,
)


def render_scene_03_vanguard(
    draw: ImageDraw.ImageDraw,
    t: float,
    duration: float,
    audio_features: Optional[Dict[str, Any]],
    width: int = 1280,
    height: int = 720,
    font_main: Any = None,
    font_sub: Any = None,
) -> None:
    """Scene 3: Lucas's heavy spiked paveze shield, diving gargoyle silhouette, sparks & shockwave."""
    ground_y = 560
    draw.rectangle([(0, ground_y), (width, height)], fill=(28, 36, 52), outline=COLOR_WEATHERED_IRON, width=2)

    # Lucas's Heavy Spiked Paveze Shield (center-left: x=460..580, y=260..570)
    sx0, sy0, sx1, sy1 = 460, 260, 580, 570
    paveze_pts = [(sx0 + 20, sy0), (sx1 - 20, sy0), (sx1, sy1 - 30), (sx1 - 40, sy1 + 15), (sx0 + 40, sy1 + 15), (sx0, sy1 - 30)]
    draw.polygon(paveze_pts, fill=(55, 65, 81), outline=COLOR_WEATHERED_IRON, width=4)
    draw.line([(sx0 + 60, sy0), (sx0 + 60, sy1)], fill=COLOR_WEATHERED_IRON, width=3)
    draw.ellipse([(sx0 + 45, sy0 + 130), (sx0 + 75, sy0 + 160)], fill=(85, 95, 115), outline=COLOR_PITCH_AMBER, width=2)

    # Descending gargoyle monster silhouette (diving at 45 deg from upper right)
    gx = 780 - int(math.sin(min(1.0, t / 4.0) * math.pi * 0.5) * 160)
    gy = 160 + int(math.sin(min(1.0, t / 4.0) * math.pi * 0.5) * 170)
    garg_pts = [(gx, gy), (gx + 70, gy - 40), (gx + 110, gy + 10), (gx + 40, gy + 30), (gx + 60, gy + 70), (gx - 10, gy + 45)]
    draw.polygon(garg_pts, fill=COLOR_OBSIDIAN_BLACK, outline=COLOR_ARTERIAL_CRIMSON, width=2)

    # Kinetic spark shower at impact point (x=560, y=360)
    imp_x, imp_y = 560, 360
    shock_r = int((t * 90.0) % 120.0)
    draw.ellipse([(imp_x - shock_r, imp_y - shock_r), (imp_x + shock_r, imp_y + shock_r)], outline=(245, 158, 11, max(0, 220 - shock_r * 2)), width=2)
    for s_i in range(36):
        s_ang = s_i * 0.174 + t * 4.0
        s_len = 15.0 + (s_i % 6) * 9.0
        draw.line([(imp_x, imp_y), (imp_x + math.cos(s_ang) * s_len, imp_y + math.sin(s_ang) * s_len)], fill=COLOR_PITCH_AMBER, width=2)

    render_torrential_rain(draw, t, width, height, num_drops=140)
    render_lightning_and_ambient(draw, t, audio_features, width, height)

    # Vanguard Defense Telemetry
    draw_tactical_hud_panel(draw, (48, 84, 500, 236), "\u0410\u0412\u0410\u041d\u0413\u0410\u0420\u0414: \u0420\u042b\u0426\u0410\u0420\u042c \u041b\u0423\u041a\u0410\u0421", COLOR_PITCH_AMBER, font_sub)
    draw.text((64, 118), "\u0411\u0410\u0421\u0422\u0418\u041e\u041d: \u0420\u041e\u0421\u0422\u041e\u0412\u041e\u0419 \u041f\u0410\u0412\u0415\u0417\u0410 \u0412 \u041a\u0410\u041c\u041d\u0415", fill=COLOR_TEXT_WHITE, font=font_sub)
    draw.text((64, 145), "\u0423\u0414\u0410\u0420: \u0413\u0410\u0420\u0413\u0423\u041b\u042c\u042f (\u041f\u0418\u041a\u0418\u0420\u041e\u0412\u0410\u041d\u0418\u0415 45\u00b0)", fill=COLOR_ARTERIAL_CRIMSON, font=font_sub)
    draw.text((64, 172), "\u041f\u0420\u041e\u0427\u041d\u041e\u0421\u0422\u042c \u0429\u0418\u0422\u0410: 94.6% (\u041f\u041e\u0413\u041b\u041e\u0429\u0415\u041d\u0418\u0415 \u041c\u0410\u041a\u0421.)", fill=COLOR_PITCH_AMBER, font=font_sub)
    draw.text((64, 199), "\u041b\u0418\u041d\u0418\u042f \u041e\u0411\u041e\u0420\u041e\u041d\u042b: \u0414\u0415\u0420\u0416\u0418\u0422\u0421\u042f", fill=COLOR_ARCANE_CYAN, font=font_sub)


def render_scene_04_sniper(
    draw: ImageDraw.ImageDraw,
    t: float,
    duration: float,
    audio_features: Optional[Dict[str, Any]],
    width: int = 1280,
    height: int = 720,
    font_main: Any = None,
    font_sub: Any = None,
) -> None:
    """Scene 4: Lily's sniper targeting reticle with mil-dot hashmarks, mana trajectory, ECG monitor."""
    # Darkened optical focus vignette
    rx, ry = 640, 330
    draw.ellipse([(rx - 260, ry - 260), (rx + 260, ry + 260)], outline=COLOR_ARCANE_CYAN, width=2)
    draw.ellipse([(rx - 130, ry - 130), (rx + 130, ry + 130)], outline=(6, 182, 212, 140), width=1)
    draw.line([(rx - 300, ry), (rx + 300, ry)], fill=COLOR_ARCANE_CYAN, width=1)
    draw.line([(rx, ry - 300), (rx, ry + 300)], fill=COLOR_ARCANE_CYAN, width=1)

    # Mil-dot hashmarks along reticle
    for step in range(-240, 241, 40):
        if step != 0:
            draw.line([(rx + step, ry - 6), (rx + step, ry + 6)], fill=COLOR_ARCANE_CYAN, width=1)
            draw.line([(rx - 6, ry + step), (rx + 6, ry + step)], fill=COLOR_ARCANE_CYAN, width=1)

    # Parabolic azure mana trajectory line
    pts: List[Tuple[int, int]] = []
    for x_i in range(180, rx + 1, 16):
        frac = (x_i - 180) / max(1, rx - 180)
        y_i = int(600 - frac * 270 - math.sin(frac * math.pi) * 45)
        pts.append((x_i, y_i))
    if len(pts) > 1:
        draw.line(pts, fill=COLOR_ARCANE_CYAN, width=3)

    # Target Lock Box around target weak point
    lock_size = 28 + int(math.sin(t * 7.0) * 4)
    draw.rectangle([(rx - lock_size, ry - lock_size), (rx + lock_size, ry + lock_size)], outline=COLOR_ARTERIAL_CRIMSON, width=2)

    # ECG Focus Monitor Waveform (calming from panic to awakened sniper focus)
    ecg_y = 570
    draw.line([(60, ecg_y), (420, ecg_y)], fill=(50, 70, 90), width=1)
    ecg_pts: List[Tuple[float, float]] = []
    for ex in range(60, 420, 4):
        phase = (ex - 60) * 0.08 + t * 8.0
        pulse = math.sin(phase) * (20.0 if t < 3.0 else 9.0)
        ecg_pts.append((float(ex), float(ecg_y + pulse)))
    if len(ecg_pts) > 1:
        draw.line(ecg_pts, fill=COLOR_ARCANE_CYAN, width=2)

    render_torrential_rain(draw, t, width, height, num_drops=60)

    # Sniper Telemetry HUD
    draw_tactical_hud_panel(draw, (48, 84, 500, 236), "\u0421\u041d\u0410\u0419\u041f\u0415\u0420: \u041b\u0423\u0427\u041d\u0418\u0426\u0410 \u041b\u0418\u041b\u0418", COLOR_ARCANE_CYAN, font_sub)
    draw.text((64, 118), "\u0424\u041e\u041a\u0423\u0421: \u041f\u0420\u041e\u0411\u0423\u0416\u0414\u0415\u041d\u0418\u0415 \u0425\u0418\u0429\u041d\u0418\u041a\u0410", fill=COLOR_TEXT_WHITE, font=font_sub)
    draw.text((64, 145), "\u0411\u0410\u041b\u041b\u0418\u0421\u0422\u0418\u041a\u0410: \u0411\u041e\u0414\u041a\u0418\u041d + \u041b\u0410\u0417\u0423\u0420\u041d\u0410\u042f \u041c\u0410\u041d\u0410", fill=COLOR_ARCANE_CYAN, font=font_sub)
    draw.text((64, 172), "\u041f\u0423\u041b\u042c\u0421: 48 \u0423\u0414/\u041c\u0418\u041d (\u041b\u0415\u0414\u042f\u041d\u041e\u0415 \u0421\u041f\u041e\u041a\u041e\u0419\u0421\u0422\u0412\u0418\u0415)", fill=COLOR_PITCH_AMBER, font=font_sub)
    draw.text((64, 199), "\u0426\u0415\u041b\u042c: \u0423\u042f\u0417\u0412\u0418\u041c\u041e\u0415 \u0421\u041e\u0427\u041b\u0415\u041d\u0415\u041d\u0418\u0415 (\u0417\u0410\u0425\u0412\u0410\u0422)", fill=COLOR_ARTERIAL_CRIMSON, font=font_sub)


def render_scene_05_boss(
    draw: ImageDraw.ImageDraw,
    t: float,
    duration: float,
    audio_features: Optional[Dict[str, Any]],
    width: int = 1280,
    height: int = 720,
    font_main: Any = None,
    font_sub: Any = None,
) -> None:
    """Scene 5: Cursed Living Armor Vanguard, Tactical Trinity synergy triangle, soul-core detonation."""
    # Colossal Living Armor silhouette (center: x=640, y=180..520)
    bx, by = 640, 310
    armor_pts = [(bx - 90, by - 120), (bx + 90, by - 120), (bx + 110, by + 10), (bx + 80, by + 160), (bx - 80, by + 160), (bx - 110, by + 10)]
    draw.polygon(armor_pts, fill=COLOR_OBSIDIAN_BLACK, outline=COLOR_WITCH_FIRE_VIOLET, width=3)

    # Raised executioner greatsword
    draw.line([(bx + 80, by - 60), (bx + 170, by - 190)], fill=COLOR_WEATHERED_IRON, width=8)
    draw.line([(bx + 60, by - 90), (bx + 100, by - 60)], fill=COLOR_WEATHERED_IRON, width=5)

    # Exposed soul-core with pulsating witch-fire detonation
    core_r = 26 + int(math.sin(t * 10.0) * 8)
    draw.ellipse([(bx - core_r, by - core_r), (bx + core_r, by + core_r)], fill=COLOR_WITCH_FIRE_VIOLET, outline=COLOR_ARTERIAL_CRIMSON, width=3)
    for shard_i in range(16):
        sh_ang = shard_i * 0.392 + t * 3.0
        sh_dist = 40.0 + (shard_i % 4) * 18.0
        draw.line([(bx, by), (bx + math.cos(sh_ang) * sh_dist, by + math.sin(sh_ang) * sh_dist)], fill=COLOR_ARTERIAL_CRIMSON, width=2)

    # Tactical Trinity Synergy Triangle
    n_ash = (bx, 100)
    n_lucas = (bx - 320, 500)
    n_lily = (bx + 320, 500)
    draw.polygon([n_ash, n_lucas, n_lily], outline=COLOR_ARCANE_CYAN, width=2)
    for nx, ny in (n_ash, n_lucas, n_lily):
        draw.ellipse([(nx - 10, ny - 10), (nx + 10, ny + 10)], fill=COLOR_ARCANE_CYAN, outline=COLOR_TEXT_WHITE, width=2)

    render_creeping_black_fog(draw, t, width, height)
    render_torrential_rain(draw, t, width, height, num_drops=150)
    render_lightning_and_ambient(draw, t, audio_features, width, height)

    # Boss Climax HUD
    draw_tactical_hud_panel(draw, (48, 84, 520, 236), "\u0422\u0410\u041a\u0422\u0418\u0427\u0415\u0421\u041a\u041e\u0415 \u0422\u0420\u041e\u0415\u0414\u0418\u041d\u0421\u0422\u0412\u041e", COLOR_WITCH_FIRE_VIOLET, font_sub)
    draw.text((64, 118), "\u0411\u041e\u0421\u0421: \u041f\u0420\u041e\u041a\u041b\u042f\u0422\u042b\u0419 \u0416\u0418\u0412\u041e\u0419 \u0414\u041e\u0421\u041f\u0415\u0425", fill=COLOR_ARTERIAL_CRIMSON, font=font_sub)
    draw.text((64, 145), "\u0429\u0418\u0422: \u041b\u0423\u041a\u0410\u0421 \u041f\u0420\u0418\u041d\u0418\u041c\u0410\u0415\u0422 \u0421\u041e\u041a\u0420\u0423\u0428\u0418\u0422\u0415\u041b\u042c\u041d\u042b\u0419 \u0423\u0414\u0410\u0420", fill=COLOR_PITCH_AMBER, font=font_sub)
    draw.text((64, 172), "\u0420\u0410\u0421\u0427\u0401\u0422: \u042d\u0428 \u0412\u0421\u041a\u0420\u042b\u0412\u0410\u0415\u0422 \u042f\u0414\u0420\u041e \u0414\u0423\u0428\u0418", fill=COLOR_ARCANE_CYAN, font=font_sub)
    draw.text((64, 199), "\u0424\u0418\u041d\u0410\u041b: \u041b\u0418\u041b\u0418 \u041f\u0420\u041e\u041d\u0417\u0410\u0415\u0422 \u041a\u041e\u0420\u0415 (\u0414\u0415\u0422\u041e\u041d\u0410\u0426\u0418\u042f)", fill=COLOR_WITCH_FIRE_VIOLET, font=font_sub)
