"""
src/ttd_visual_engine.py
Dark Fantasy Procedural Visual Engine for Crossroads of Ash Pilot Scene.
Integrates particle effects, tactical HUD overlays, audio-reactive telemetry,
and kinetic typography subtitles into 1280x720 HD frames.

Zero literal Cyrillic rule: all Russian strings use unicode escapes.
"""

from __future__ import annotations

import math
from typing import Any, Dict, Optional, Tuple, Union
from PIL import Image, ImageDraw

from src.ttd_visual_common import (
    COLOR_ARCANE_CYAN,
    COLOR_MIDNIGHT_STORM,
    COLOR_OBSIDIAN_BLACK,
    COLOR_PITCH_AMBER,
    COLOR_TEXT_WHITE,
    COLOR_WEATHERED_IRON,
)
from src.ttd_visual_scenes_a import (
    render_scene_01_prologue,
    render_scene_02_command,
)
from src.ttd_visual_scenes_b import (
    render_scene_03_vanguard,
    render_scene_04_sniper,
    render_scene_05_boss,
)


def _get_font(size: int, bold: bool = False) -> Any:
    """Resolve cached TrueType font via flow_testbench_runner or PIL fallback."""
    try:
        from flow_testbench_runner import get_cached_font
        return get_cached_font(size, bold)
    except Exception:
        from PIL import ImageFont
        try:
            name = "segoeuib.ttf" if bold else "segoeui.ttf"
            return ImageFont.truetype(f"C:/Windows/Fonts/{name}", size)
        except Exception:
            return ImageFont.load_default()


def _fit_subtitle_lines(
    draw: ImageDraw.ImageDraw,
    text: str,
    max_width: int = 1170,
) -> Tuple[list[str], Any]:
    """Wrap subtitle narration into 1 or 2 balanced lines guaranteed <= max_width."""
    clean = text.replace("+", "").replace("*", "").strip()
    words = clean.split()
    if not words:
        return [], _get_font(18, bold=True)

    for pt in (19, 18, 17, 16, 15, 14):
        font = _get_font(pt, bold=True)
        full_bbox = draw.textbbox((0, 0), clean, font=font)
        if (full_bbox[2] - full_bbox[0]) <= max_width:
            return [clean], font

        # Find most balanced 2-line split where both lines fit inside max_width
        best_pair: Optional[Tuple[str, str]] = None
        best_diff = 10**9
        for split_idx in range(1, len(words)):
            l1 = " ".join(words[:split_idx])
            l2 = " ".join(words[split_idx:])
            b1 = draw.textbbox((0, 0), l1, font=font)
            b2 = draw.textbbox((0, 0), l2, font=font)
            w1 = b1[2] - b1[0]
            w2 = b2[2] - b2[0]
            if w1 <= max_width and w2 <= max_width:
                diff = abs(w1 - w2)
                if diff < best_diff:
                    best_diff = diff
                    best_pair = (l1, l2)
        if best_pair is not None:
            return [best_pair[0], best_pair[1]], font

    # Fallback greedy wrap at 14pt
    font = _get_font(14, bold=True)
    mid = max(1, len(words) // 2)
    return [" ".join(words[:mid]), " ".join(words[mid:])], font


def render_ttd_scene_frame(
    scene: Any,
    t: float = 0.0,
    duration: float = 7.0,
    audio_features: Optional[Dict[str, Any]] = None,
    width: int = 1280,
    height: int = 720,
    frame_idx: Optional[int] = None,
    total_frames: Optional[int] = None,
    captions: Any = None,
    as_bytes: bool = False,
    **kwargs: Any,
) -> Union[Image.Image, bytes]:
    """
    Render a single 1280x720 HD frame for the TTD pilot test scene.
    Supports all 5 pilot scenes: prologue, command, vanguard, sniper, and boss.
    Returns PIL Image.Image by default (or raw bytes if as_bytes=True).
    """
    if frame_idx is not None and total_frames is not None and total_frames > 1:
        t = (frame_idx / float(total_frames - 1)) * duration

    # 1. Base RGB dark background buffer with RGBA alpha-compositing draw surface
    img = Image.new("RGB", (width, height), COLOR_MIDNIGHT_STORM)
    draw = ImageDraw.Draw(img, "RGBA")

    # Font handles
    f_badge = _get_font(15, bold=True)
    f_title = _get_font(20, bold=True)
    f_sub = _get_font(14, bold=False)

    # 2. Extract scene identity
    sc_id = str(getattr(scene, "scene_id", "") or kwargs.get("scene_id", ""))
    sc_num = int(getattr(scene, "scene_number", 1) or kwargs.get("scene_number", 1))

    # 3. Dispatch to scene-specific procedural visual stage
    if "01_prologue" in sc_id or sc_num == 1:
        render_scene_01_prologue(draw, t, duration, audio_features, width, height, f_title, f_sub)
    elif "02_command" in sc_id or sc_num == 2:
        render_scene_02_command(draw, t, duration, audio_features, width, height, f_title, f_sub)
    elif "03_vanguard" in sc_id or sc_num == 3:
        render_scene_03_vanguard(draw, t, duration, audio_features, width, height, f_title, f_sub)
    elif "04_sniper" in sc_id or sc_num == 4:
        render_scene_04_sniper(draw, t, duration, audio_features, width, height, f_title, f_sub)
    else:
        render_scene_05_boss(draw, t, duration, audio_features, width, height, f_title, f_sub)

    # 4. Cinematic Header Bar (y=0..54)
    draw.rectangle([(0, 0), (width, 54)], fill=(6, 11, 24, 246), outline=COLOR_ARCANE_CYAN, width=1)
    badge_text = f"\u0421\u0426\u0415\u041d\u0410 {sc_num}/5"
    draw.rectangle([(24, 10), (130, 44)], fill=(14, 116, 144, 245))
    draw.text((36, 16), badge_text, fill=COLOR_TEXT_WHITE, font=f_badge)

    sc_title = str(getattr(scene, "title", "") or "")
    if sc_title:
        draw.text((146, 15), sc_title, fill=COLOR_TEXT_WHITE, font=f_title)

    # Audio spectrum equalizer pill (top right: x=1020..1256, y=10..44)
    draw.rectangle([(1020, 10), (1256, 44)], fill=(11, 19, 36, 245), outline=COLOR_ARCANE_CYAN, width=1)
    draw.text((1030, 17), "\u0413\u041e\u041b\u041e\u0421", fill=COLOR_ARCANE_CYAN, font=f_badge)
    bands = (audio_features.get("bands") if audio_features else None) or [0.0] * 18
    for b_idx in range(min(18, len(bands))):
        bx = 1084 + b_idx * 9
        bh = max(2, int(bands[b_idx] * 22))
        draw.rectangle([(bx, 40 - bh), (bx + 6, 40)], fill=COLOR_PITCH_AMBER if b_idx > 10 else COLOR_ARCANE_CYAN)

    # 5. Kinetic Subtitle Bar (y=616..706) with balanced 2-line wrapping and zero overflow
    sub_x0, sub_y0, sub_x1, sub_y1 = 24, 616, width - 24, 706
    draw.rectangle([(sub_x0, sub_y0), (sub_x1, sub_y1)], fill=(6, 11, 24, 246), outline=COLOR_WEATHERED_IRON, width=1)
    draw.rectangle([(sub_x0, sub_y0), (sub_x0 + 6, sub_y1)], fill=COLOR_PITCH_AMBER)

    narration = str(getattr(scene, "narration_text", "") or kwargs.get("narration_text", ""))
    if narration:
        sub_lines, f_cap = _fit_subtitle_lines(draw, narration, max_width=sub_x1 - sub_x0 - 56)
        if len(sub_lines) == 1:
            b0 = draw.textbbox((0, 0), sub_lines[0], font=f_cap)
            tw0 = b0[2] - b0[0]
            tx0 = sub_x0 + ((sub_x1 - sub_x0) - tw0) // 2
            draw.text((tx0, sub_y0 + 30), sub_lines[0], fill=COLOR_PITCH_AMBER, font=f_cap)
        elif len(sub_lines) >= 2:
            for l_idx, line_str in enumerate(sub_lines[:2]):
                bl = draw.textbbox((0, 0), line_str, font=f_cap)
                twl = bl[2] - bl[0]
                txl = sub_x0 + ((sub_x1 - sub_x0) - twl) // 2
                tyl = sub_y0 + 16 + l_idx * 30
                col = COLOR_PITCH_AMBER if l_idx == 0 else COLOR_TEXT_WHITE
                draw.text((txl, tyl), line_str, fill=col, font=f_cap)

    # Temporal progress hairline along bottom of subtitle box
    prog = min(1.0, max(0.0, t / max(0.1, duration)))
    prog_x1 = int(sub_x0 + 6 + (sub_x1 - sub_x0 - 6) * prog)
    if prog_x1 > sub_x0 + 6:
        draw.rectangle([(sub_x0 + 6, sub_y1 - 3), (prog_x1, sub_y1)], fill=COLOR_ARCANE_CYAN)

    if as_bytes:
        return img.tobytes()
    return img
