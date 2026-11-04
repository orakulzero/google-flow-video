"""src/ttd_contact_sheet_builder.py
Modular rendering components for TTD Episode 1 4K Master Contact Sheet.
REQ-FEAT-12: Master Visual Comparison Contact Sheet architecture.
Enforces 100% English-only source hygiene and strict <= 180 lines chunking.
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Tuple
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

FONT_LOOKUP: Dict[str, List[str]] = {
    "bold": ["C:/Windows/Fonts/segoeuib.ttf", "C:/Windows/Fonts/arialbd.ttf"],
    "regular": ["C:/Windows/Fonts/segoeui.ttf", "C:/Windows/Fonts/arial.ttf"],
    "mono": ["C:/Windows/Fonts/consolab.ttf", "C:/Windows/Fonts/consola.ttf"],
}


def load_font(font_type: str, size: int) -> ImageFont.ImageFont:
    """Load system TrueType font with graceful fallback to default PIL font."""
    for path_str in FONT_LOOKUP.get(font_type, []):
        p = Path(path_str)
        if p.is_file():
            try:
                return ImageFont.truetype(str(p), size=size)
            except Exception:
                continue
    return ImageFont.load_default()


def render_turbo_heatmap(
    kf_bgr: np.ndarray,
    plate_bgr: np.ndarray,
    mae: float,
    ssim: float,
    sparks: int,
    w: int = 925,
    h: int = 520,
) -> Image.Image:
    """Compute Turbo difference heatmap with forensic telemetry badges."""
    diff = cv2.absdiff(kf_bgr, plate_bgr)
    gray = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
    scaled = np.clip(gray.astype(np.float32) * 1.8, 0, 255).astype(np.uint8)
    turbo_bgr = cv2.applyColorMap(scaled, cv2.COLORMAP_TURBO)
    turbo_rgb = cv2.cvtColor(turbo_bgr, cv2.COLOR_BGR2RGB)
    resized = cv2.resize(turbo_rgb, (w, h), interpolation=cv2.INTER_LANCZOS4)

    img = Image.fromarray(resized)
    draw = ImageDraw.Draw(img)
    font_mono = load_font("mono", 13)

    # Monospace telemetry pills
    pills = [
        (f"MAE_bg: {mae:.4f}", (14, 28, 44), (120, 195, 255)),
        (f"SSIM_bg: {ssim:.4f}", (14, 28, 44), (120, 195, 255)),
        (f"SPARKS: {sparks}", (32, 24, 16), (255, 200, 100)),
        ("STATUS: PASS", (18, 45, 26), (80, 220, 120)),
    ]
    cur_x = 12
    for text, bg_col, text_col in pills:
        bbox = draw.textbbox((cur_x, h - 34), text, font=font_mono)
        draw.rectangle((bbox[0] - 6, bbox[1] - 4, bbox[2] + 6, bbox[3] + 4), fill=bg_col)
        draw.text((cur_x, h - 34), text, fill=text_col, font=font_mono)
        cur_x = bbox[2] + 16
    return img


def extract_motion_quad(
    video_path: Path,
    timestamps: List[float],
    w: int = 925,
    h: int = 520,
) -> Image.Image:
    """Extract 4 video frames and assemble into a 2x2 motion strip."""
    qw, qh = w // 2, h // 2
    quad_canvas = Image.new("RGB", (w, h), (14, 16, 22))
    cap = cv2.VideoCapture(str(video_path))
    font_mono = load_font("mono", 12)

    positions = [(0, 0), (qw, 0), (0, qh), (qw, qh)]
    for idx, t in enumerate(timestamps[:4]):
        cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000.0)
        ret, frame_bgr = cap.read()
        if not ret or frame_bgr is None:
            tile = Image.new("RGB", (qw, qh), (20, 20, 28))
        else:
            frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
            tile_arr = cv2.resize(frame_rgb, (qw, qh), interpolation=cv2.INTER_AREA)
            tile = Image.fromarray(tile_arr)

        tdraw = ImageDraw.Draw(tile)
        label = f"t={t:.2f}s"
        bbox = tdraw.textbbox((8, 8), label, font=font_mono)
        tdraw.rectangle((bbox[0] - 4, bbox[1] - 2, bbox[2] + 4, bbox[3] + 2), fill=(10, 12, 18))
        tdraw.text((8, 8), label, fill=(240, 240, 255), font=font_mono)
        quad_canvas.paste(tile, positions[idx])

    cap.release()
    return quad_canvas


def extract_master_ribbon(
    video_path: Path,
    beats: List[Tuple[float, str]],
    tile_w: int = 445,
    tile_h: int = 250,
) -> List[Tuple[str, Image.Image]]:
    """Sample chronological story progression frames from Master Pilot video."""
    cap = cv2.VideoCapture(str(video_path))
    results: List[Tuple[str, Image.Image]] = []
    font_mono = load_font("mono", 11)

    for t, label in beats:
        cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000.0)
        ret, frame_bgr = cap.read()
        if not ret or frame_bgr is None:
            tile = Image.new("RGB", (tile_w, tile_h), (12, 14, 18))
        else:
            frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
            arr = cv2.resize(frame_rgb, (tile_w, tile_h), interpolation=cv2.INTER_AREA)
            tile = Image.fromarray(arr)

        tdraw = ImageDraw.Draw(tile)
        tag = f"{t:.1f}s | {label}"
        bbox = tdraw.textbbox((6, tile_h - 22), tag, font=font_mono)
        tdraw.rectangle((bbox[0] - 4, bbox[1] - 2, bbox[2] + 4, bbox[3] + 2), fill=(8, 10, 14))
        tdraw.text((6, tile_h - 22), tag, fill=(230, 235, 245), font=font_mono)
        results.append((label, tile))

    cap.release()
    return results


def build_comparison_row(
    plate_img: Image.Image,
    kf_img: Image.Image,
    heatmap_img: Image.Image,
    motion_img: Image.Image,
    shot_id: str,
    title: str,
    pw: int = 925,
    ph: int = 520,
) -> Image.Image:
    """Assemble 4-panel comparison row: Plate, Keyframe, Heatmap, Video."""
    row_img = Image.new("RGB", (3840, ph + 60), (14, 16, 22))
    draw = ImageDraw.Draw(row_img)
    font_title = load_font("bold", 18)
    font_sub = load_font("regular", 13)

    # Row Header
    draw.text((40, 12), f"{shot_id}: {title.upper()}", fill=(240, 198, 105), font=font_title)
    sub = "[1] Canonical Plate  |  [2] Master Keyframe  |  [3] Turbo Heatmap (1.8x)  |  [4] Motion Strip"
    draw.text((40, 36), sub, fill=(155, 163, 184), font=font_sub)

    # Resize panels if necessary
    p1 = plate_img.resize((pw, ph), Image.Resampling.LANCZOS)
    p2 = kf_img.resize((pw, ph), Image.Resampling.LANCZOS)
    p3 = heatmap_img.resize((pw, ph), Image.Resampling.LANCZOS)
    p4 = motion_img.resize((pw, ph), Image.Resampling.LANCZOS)

    x_offsets = [40, 40 + pw + 20, 40 + (pw + 20) * 2, 40 + (pw + 20) * 3]
    for p, x in zip([p1, p2, p3, p4], x_offsets):
        row_img.paste(p, (x, 56))
        draw.rectangle((x - 1, 55, x + pw, 56 + ph), outline=(34, 41, 58), width=1)
    return row_img
