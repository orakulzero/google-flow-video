"""
src/ttd_visual_common.py
Dark fantasy procedural visual engine - common VFX and particle systems.
Provides rain simulation, floating brazier embers, creeping Black Fog ribbons,
and audio-reactive ambient lighting for Crossroads Fortress.

Zero literal Cyrillic rule: all Russian strings use unicode escapes.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple
from PIL import Image, ImageDraw

COLOR_MIDNIGHT_STORM: Tuple[int, int, int] = (15, 23, 42)
COLOR_OBSIDIAN_BLACK: Tuple[int, int, int] = (2, 6, 23)
COLOR_PITCH_AMBER: Tuple[int, int, int] = (245, 158, 11)
COLOR_ARCANE_CYAN: Tuple[int, int, int] = (6, 182, 212)
COLOR_ARTERIAL_CRIMSON: Tuple[int, int, int] = (220, 38, 38)
COLOR_WITCH_FIRE_VIOLET: Tuple[int, int, int] = (139, 92, 246)
COLOR_WEATHERED_IRON: Tuple[int, int, int] = (100, 116, 139)
COLOR_TEXT_WHITE: Tuple[int, int, int] = (248, 250, 252)


def render_torrential_rain(
    draw: ImageDraw.ImageDraw,
    t: float,
    width: int = 1280,
    height: int = 720,
    num_drops: int = 180,
) -> None:
    """Draw slanted torrential rain streaks with ground baseline splash rings."""
    slant_rad = math.radians(75.0)
    dx = math.cos(slant_rad) * 45.0
    dy = math.sin(slant_rad) * 45.0
    speed = 1100.0

    for i in range(num_drops):
        seed_x = (i * 137.5) % width
        seed_y = (i * 89.3) % height
        curr_y = (seed_y + t * speed) % height
        curr_x = (seed_x - (t * speed) / math.tan(slant_rad)) % width

        alpha_val = int(70 + 80 * ((i % 5) / 5.0))
        col = (180, 210, 240, alpha_val)
        draw.line(
            [(curr_x, curr_y), (curr_x + dx, curr_y + dy)],
            fill=col,
            width=1 if i % 3 != 0 else 2,
        )

        if curr_y > height - 140:
            splash_r = int(2 + 4 * ((i % 4) / 4.0))
            draw.ellipse(
                [(curr_x - splash_r, curr_y - 1), (curr_x + splash_r, curr_y + 2)],
                outline=(160, 200, 240, int(alpha_val * 0.7)),
                width=1,
            )


def render_brazier_embers(
    draw: ImageDraw.ImageDraw,
    t: float,
    brazier_anchors: List[Tuple[int, int]],
    num_embers_per_brazier: int = 20,
) -> None:
    """Draw rising amber embers drifting with sinusoidal sway."""
    for b_idx, (bx, by) in enumerate(brazier_anchors):
        for e_idx in range(num_embers_per_brazier):
            phase = (e_idx * 1.618 + b_idx * 3.1415)
            life = (t * 1.5 + e_idx * 0.18) % 2.5
            progress = life / 2.5
            ey = by - progress * 240.0
            sway = math.sin(t * 3.5 + phase) * 20.0
            ex = bx + sway + (e_idx % 7 - 3) * 6.0

            alpha = int(255 * (1.0 - progress) * (0.6 + 0.4 * math.sin(t * 6.0 + phase)))
            r = max(1, int(3.5 * (1.0 - progress * 0.5)))
            ember_col = (245, 158 + int(50 * (1.0 - progress)), 11, max(0, min(255, alpha)))
            draw.ellipse([(ex - r, ey - r), (ex + r, ey + r)], fill=ember_col)


def render_creeping_black_fog(
    draw: ImageDraw.ImageDraw,
    t: float,
    width: int = 1280,
    height: int = 720,
) -> None:
    """Draw multi-layered undulating Black Fog ribbons along the bottom third."""
    fog_base_y = height - 180
    for layer in range(3):
        freq = 0.004 + layer * 0.002
        speed = 35.0 + layer * 20.0
        amp = 18.0 + layer * 12.0
        y_offset = layer * 40

        points: List[Tuple[float, float]] = []
        for x in range(0, width + 40, 20):
            sine_y = math.sin(x * freq + t * (1.2 + layer * 0.4) + layer) * amp
            points.append((float(x), fog_base_y + y_offset + sine_y))
        points.append((float(width), float(height)))
        points.append((0.0, float(height)))

        fog_alpha = 110 + layer * 45
        col = (2 + layer * 3, 6 + layer * 4, 18 + layer * 6, fog_alpha)
        draw.polygon(points, fill=col)


def render_lightning_and_ambient(
    draw: ImageDraw.ImageDraw,
    t: float,
    audio_features: Optional[Dict[str, Any]],
    width: int = 1280,
    height: int = 720,
) -> None:
    """Draw audio-reactive or periodic ambient lightning flashes."""
    rms = float(audio_features.get("rms", 0.0)) if audio_features else 0.0
    is_flash = (rms > 0.62) or (int(t * 1.5) % 9 == 0 and (t * 1.5 - int(t * 1.5)) < 0.12)
    if is_flash:
        flash_alpha = int(45 + 50 * min(1.0, max(0.0, rms)))
        draw.rectangle([(0, 0), (width, height)], fill=(180, 220, 255, flash_alpha))


def draw_tactical_hud_panel(
    draw: ImageDraw.ImageDraw,
    box: Tuple[int, int, int, int],
    title: str,
    accent_color: Tuple[int, int, int] = COLOR_ARCANE_CYAN,
    font_title: Any = None,
) -> None:
    """Render a dark frosted-glass tactical HUD frame with a dedicated header band and corner brackets."""
    x0, y0, x1, y1 = box
    top_y = y0 - 6
    header_bottom = y0 + 24

    # Main opaque-dark obsidian body so background rain never slices through text
    draw.rectangle(
        [(x0, top_y), (x1, y1)],
        fill=(7, 12, 24, 242),
        outline=accent_color + (255,),
        width=1,
    )

    # Dedicated header band with solid fill and bottom divider line
    if title:
        draw.rectangle(
            [(x0, top_y), (x1, header_bottom)],
            fill=(14, 26, 48, 250),
            outline=accent_color + (255,),
            width=1,
        )
        draw.text((x0 + 14, top_y + 5), title, fill=accent_color + (255,), font=font_title)

    # Glowing corner brackets on outer bounds
    b_len = 12
    c_rgba = accent_color + (255,)
    draw.line([(x0, top_y), (x0 + b_len, top_y)], fill=c_rgba, width=2)
    draw.line([(x0, top_y), (x0, top_y + b_len)], fill=c_rgba, width=2)
    draw.line([(x1, top_y), (x1 - b_len, top_y)], fill=c_rgba, width=2)
    draw.line([(x1, top_y), (x1, top_y + b_len)], fill=c_rgba, width=2)
    draw.line([(x0, y1), (x0 + b_len, y1)], fill=c_rgba, width=2)
    draw.line([(x0, y1), (x0, y1 - b_len)], fill=c_rgba, width=2)
    draw.line([(x1, y1), (x1 - b_len, y1)], fill=c_rgba, width=2)
    draw.line([(x1, y1), (x1, y1 - b_len)], fill=c_rgba, width=2)
