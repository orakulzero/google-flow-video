"""src/solo_leveling_hud_renderer.py
Deterministic Solo Leveling-style diegetic holographic status window renderer.
Generates translucent RGBA glassmorphic HUD panels and crystalline system chimes
for FFmpeg alpha-compositing over Gemini Omni 1.1 Flash video shots.
Enforces 100% English-only source hygiene (0 literal Cyrillic characters in source).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
import wave
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from src.ttd_storyboard import StatusWindowSpec

THEME_PALETTES: Dict[str, Dict[str, Tuple[int, int, int, int]]] = {
    "BLUE_CYAN": {
        "bg": (7, 19, 36, 214),
        "header_bg": (12, 42, 78, 235),
        "border": (0, 229, 255, 245),
        "glow": (0, 185, 255, 95),
        "title": (180, 245, 255, 255),
        "text": (235, 248, 255, 255),
        "bar_fill": (0, 215, 255, 240),
    },
    "CRIMSON_WARNING": {
        "bg": (38, 8, 14, 220),
        "header_bg": (82, 14, 26, 238),
        "border": (255, 52, 76, 250),
        "glow": (255, 32, 56, 105),
        "title": (255, 195, 202, 255),
        "text": (255, 236, 238, 255),
        "bar_fill": (255, 48, 68, 245),
    },
    "GOLD_AWAKENING": {
        "bg": (34, 24, 6, 222),
        "header_bg": (76, 54, 10, 238),
        "border": (255, 210, 64, 250),
        "glow": (255, 190, 40, 110),
        "title": (255, 242, 175, 255),
        "text": (255, 250, 230, 255),
        "bar_fill": (255, 205, 55, 245),
    },
}

FONT_CANDIDATES: Tuple[str, ...] = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
)


def _load_font(size: int) -> Union[ImageFont.FreeTypeFont, ImageFont.ImageFont]:
    for fp in FONT_CANDIDATES:
        if Path(fp).is_file():
            try:
                return ImageFont.truetype(fp, size)
            except Exception:
                continue
    return ImageFont.load_default()


def _coerce_spec(spec: Union[StatusWindowSpec, Dict[str, Any]]) -> StatusWindowSpec:
    if isinstance(spec, StatusWindowSpec):
        return spec
    return StatusWindowSpec.from_dict(spec)


def render_status_window_frame_rgba(
    spec: Union[StatusWindowSpec, Dict[str, Any]],
    width: int = 1280,
    height: int = 720,
    progress: float = 1.0,
) -> Image.Image:
    """Render a single 1280x720 RGBA frame containing the Solo Leveling holographic window."""
    s = _coerce_spec(spec)
    pal = THEME_PALETTES.get(s.theme_color, THEME_PALETTES["BLUE_CYAN"])
    canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas, "RGBA")

    box_w = min(620, int(width * 0.48))
    line_count = max(1, len(s.body_lines))
    extra_bar_h = 46 if s.resource_bar else 0
    full_box_h = 84 + line_count * 32 + extra_bar_h

    p_clamped = max(0.08, min(1.0, float(progress)))
    box_h = max(48, int(full_box_h * p_clamped))

    anchor = s.screen_anchor.upper()
    if anchor == "CENTER_LEFT":
        x0, y0 = 56, max(48, (height - full_box_h) // 2)
    elif anchor == "BOTTOM_RIGHT":
        x0, y0 = width - box_w - 56, height - full_box_h - 64
    else:
        x0, y0 = width - box_w - 56, 52

    x1, y1 = x0 + box_w, y0 + box_h

    # Outer Solo Leveling glow & double angular frame
    draw.rectangle([x0 - 4, y0 - 4, x1 + 4, y1 + 4], outline=pal["glow"], width=3)
    draw.rectangle([x0, y0, x1, y1], fill=pal["bg"], outline=pal["border"], width=2)
    draw.rectangle([x0 + 6, y0 + 6, x1 - 6, y1 - 6], outline=pal["glow"], width=1)

    # Corner brackets
    c_len = 18
    b_col = pal["border"]
    for cx, cy, dx, dy in (
        (x0, y0, 1, 1),
        (x1, y0, -1, 1),
        (x0, y1, 1, -1),
        (x1, y1, -1, -1),
    ):
        draw.line([(cx, cy), (cx + dx * c_len, cy)], fill=b_col, width=4)
        draw.line([(cx, cy), (cx, cy + dy * c_len)], fill=b_col, width=4)

    if p_clamped < 0.35:
        return canvas

    # Header bar
    hdr_h = 46
    draw.rectangle([x0 + 8, y0 + 8, x1 - 8, y0 + 8 + hdr_h], fill=pal["header_bg"], outline=pal["border"], width=1)

    f_title = _load_font(19)
    f_body = _load_font(16)
    f_badge = _load_font(16)

    tx = x0 + 18
    if s.rank_badge:
        badge_txt = f"[{s.rank_badge}]"
        draw.rectangle([tx, y0 + 15, tx + 64, y0 + 47], fill=pal["border"])
        draw.text((tx + 8, y0 + 19), badge_txt, fill=(8, 12, 20, 255), font=f_badge)
        tx += 74

    draw.text((tx, y0 + 19), s.header_title[:46], fill=pal["title"], font=f_title)

    cur_y = y0 + 66
    for line in s.body_lines:
        if cur_y + 26 > y1 - 10:
            break
        draw.text((x0 + 20, cur_y), line[:68], fill=pal["text"], font=f_body)
        cur_y += 30

    if s.resource_bar and cur_y + 34 <= y1 - 8:
        lbl = str(s.resource_bar.get("label", "MP"))
        to_pct = max(0, min(100, int(s.resource_bar.get("to_pct", 0))))
        status_str = str(s.resource_bar.get("status", f"{to_pct}%"))
        bar_x0, bar_y0 = x0 + 20, cur_y + 6
        bar_w = box_w - 40
        bar_h = 20
        draw.rectangle([bar_x0, bar_y0, bar_x0 + bar_w, bar_y0 + bar_h], fill=(16, 20, 28, 230), outline=pal["border"], width=1)
        fill_w = int((bar_w - 4) * (to_pct / 100.0))
        if fill_w > 0:
            draw.rectangle([bar_x0 + 2, bar_y0 + 2, bar_x0 + 2 + fill_w, bar_y0 + bar_h - 2], fill=pal["bar_fill"])
        draw.text((bar_x0 + 8, bar_y0 + 1), f"{lbl}: {to_pct}% ({status_str})", fill=pal["text"], font=f_body)

    return canvas


def render_status_window_overlay(
    spec: Union[StatusWindowSpec, Dict[str, Any]],
    width_or_path: Union[int, str, Path] = 1280,
    height: int = 720,
    fps: int = 24,
    output_dir: Optional[Union[str, Path]] = None,
    shot_id: str = "SHOT-001",
) -> Path:
    """Render and save the RGBA PNG overlay for FFmpeg timed overlay compositing."""
    if isinstance(width_or_path, (str, Path)) and not str(width_or_path).isdigit():
        out_png = Path(width_or_path)
        out_png.parent.mkdir(parents=True, exist_ok=True)
        w = 1280
    else:
        w = int(width_or_path)
        out_root = Path(output_dir) if output_dir else Path("output/ttd_ep01_omni_flash/hud_overlays")
        out_root.mkdir(parents=True, exist_ok=True)
        out_png = out_root / f"{shot_id}_solo_hud.png"
    img = render_status_window_frame_rgba(spec, width=w, height=height, progress=1.0)
    img.save(out_png, format="PNG")
    return out_png


def synthesize_hud_chime_wav(
    output_path_or_theme: Union[str, Path],
    theme_color_or_path: Union[str, Path] = "BLUE_CYAN",
    sample_rate: int = 48000,
) -> Path:
    """Synthesize a crystalline Solo Leveling system window notification chime WAV (48kHz stereo)."""
    known_themes = {"BLUE_CYAN", "CRIMSON_WARNING", "GOLD_AWAKENING"}
    if str(output_path_or_theme) in known_themes and str(theme_color_or_path) not in known_themes:
        theme_color = str(output_path_or_theme)
        out_p = Path(theme_color_or_path)
    else:
        out_p = Path(output_path_or_theme)
        theme_color = str(theme_color_or_path)
    out_p.parent.mkdir(parents=True, exist_ok=True)
    dur = 0.55
    t = np.linspace(0.0, dur, int(sample_rate * dur), endpoint=False, dtype=np.float32)

    if theme_color == "CRIMSON_WARNING":
        freqs = (880.0, 622.25, 440.0)
    elif theme_color == "GOLD_AWAKENING":
        freqs = (1046.50, 1318.51, 1567.98, 2093.00)
    else:
        freqs = (1174.66, 1479.98, 1760.00)

    env = np.exp(-t * 7.5) * (1.0 - np.exp(-t * 90.0))
    sig = np.zeros_like(t)
    for idx, f in enumerate(freqs):
        shift = min(len(t) - 1, int(idx * 0.045 * sample_rate))
        part = np.sin(2.0 * np.pi * f * t) * env
        sig += np.roll(part, shift) / len(freqs)

    stereo = np.stack([sig, np.roll(sig, int(0.004 * sample_rate))], axis=-1)
    pcm16 = (np.clip(stereo, -0.95, 0.95) * 14000.0).astype(np.int16)
    with wave.open(str(out_p), "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm16.tobytes())
    return out_p
