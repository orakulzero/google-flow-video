"""Stage and Pre-Flight Audit the Episode 1 Knight Lucas 1280x720 3/4 Close-Up Pair.

Stages the 3/4 close-up keyframe pair (first_frame.png and last_frame.png at 1280x720)
where Knight Lucas commands the vanguard charge with dynamic camera push-in,
grounded Fortiche Arcane brushwork, natural human eyes (zero magic sparks),
and charging infantry in the background.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict

import cv2
import numpy as np
from PIL import Image, ImageDraw

CANONICAL_SRC = Path("output/canonical_arcane_concepts/knight_lucas_portrait.png")
PAIR_DIR = Path("veo_arcane_style/dataset/pairs/pair_ttd_ep01_lucas_001")
DATASET_INDEX_PATH = Path("veo_arcane_style/dataset/metadata/dataset_index.json")


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def _normalize_image_to_720p(src_path: Path, dst_path: Path) -> Path:
    """Center-crop to 16:9 if needed and Lanczos-resize to exact 1280x720 RGB PNG."""
    if not src_path.is_file():
        raise FileNotFoundError(f"Source image missing: {src_path}")
    dst_path.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(src_path) as im:
        rw, rh = im.size
        target_ratio = 16.0 / 9.0
        cur_ratio = rw / float(rh)
        im_rgb = im.convert("RGB")
        if abs(cur_ratio - target_ratio) > 0.004:
            if cur_ratio > target_ratio:
                new_w = int(round(rh * target_ratio))
                x0 = (rw - new_w) // 2
                im_rgb = im_rgb.crop((x0, 0, x0 + new_w, rh))
            else:
                new_h = int(round(rw / target_ratio))
                y0 = (rh - new_h) // 2
                im_rgb = im_rgb.crop((0, y0, rw, y0 + new_h))
        resized = im_rgb.resize((1280, 720), Image.Resampling.LANCZOS)
        resized.save(dst_path)
    return dst_path


def build_lucas_3q_closeup_mask(width: int = 1280, height: int = 720) -> np.ndarray:
    """Build float32 soft mask over Lucas's 3/4 close-up head & steel gorget/pauldron."""
    mask = np.zeros((height, width), dtype=np.float32)
    # 1. Lucas's 3/4 head & wind-swept blond hair (center-right)
    cv2.ellipse(mask, (710, 290), (260, 270), 0, 0, 360, 1.0, -1)
    # 2. Steel gorget & shoulder pauldron (bottom-center to bottom-right)
    cv2.ellipse(mask, (820, 610), (420, 220), 0, 0, 360, 1.0, -1)
    mask = cv2.GaussianBlur(mask, (0, 0), sigmaX=28.0, sigmaY=28.0)
    return np.clip(mask, 0.0, 1.0)


def stage_3q_closeup_pair(
    first_raw_path: Path = PAIR_DIR / "first_frame_raw.png",
    last_raw_path: Path = PAIR_DIR / "last_frame_raw.png",
    out_first_path: Path = PAIR_DIR / "first_frame.png",
    out_last_path: Path = PAIR_DIR / "last_frame.png",
) -> Dict[str, float]:
    """Verify canonical reference is untouched and normalize 3/4 close-up start/end frames to 1280x720."""
    if not CANONICAL_SRC.is_file():
        raise FileNotFoundError(f"Canonical source image missing: {CANONICAL_SRC}")
    with Image.open(CANONICAL_SRC) as im_canon:
        if im_canon.size != (1376, 768):
            raise ValueError(f"Canonical source mutated: {im_canon.size}")

    _normalize_image_to_720p(first_raw_path, out_first_path)
    _normalize_image_to_720p(last_raw_path, out_last_path)

    first_rgb = np.array(Image.open(out_first_path).convert("RGB"), dtype=np.float32)
    last_rgb = np.array(Image.open(out_last_path).convert("RGB"), dtype=np.float32)
    mask = build_lucas_3q_closeup_mask(1280, 720)
    diff = np.abs(last_rgb - first_rgb)
    mae_bg = float(np.mean(diff[mask < 0.15]))
    mae_roi = float(np.mean(diff[mask > 0.50]))
    mae_global = float(np.mean(diff))
    return {
        "mae_bg": round(mae_bg, 4),
        "mae_roi": round(mae_roi, 4),
        "mae_global": round(mae_global, 4),
    }


def validate_and_write_preflight_audit(pair_dir: Path = PAIR_DIR) -> Dict[str, Any]:
    """Validate 1280x720 3/4 close-up pair geometry & regional MAE gates and write audit artifacts."""
    f_path = pair_dir / "first_frame.png"
    l_path = pair_dir / "last_frame.png"
    f_arr = np.array(Image.open(f_path).convert("RGB"))
    l_arr = np.array(Image.open(l_path).convert("RGB"))

    if f_arr.shape != (720, 1280, 3) or l_arr.shape != (720, 1280, 3):
        raise ValueError(f"Invalid pair shapes: {f_arr.shape} vs {l_arr.shape}")

    mask = build_lucas_3q_closeup_mask(1280, 720)
    diff = np.abs(l_arr.astype(np.float32) - f_arr.astype(np.float32))
    mae_bg = float(np.mean(diff[mask < 0.15]))
    mae_roi = float(np.mean(diff[mask > 0.50]))
    mae_global = float(np.mean(diff))

    if not (8.0 <= mae_roi <= 65.0):
        raise ValueError(f"Foreground action gate failed: MAE_roi={mae_roi:.2f} not in [8.0, 65.0]")
    if not (5.0 <= mae_bg <= 65.0):
        raise ValueError(f"Dynamic camera/vanguard background gate failed: MAE_bg={mae_bg:.2f} not in [5.0, 65.0]")

    diag = Image.new("RGB", (1290, 260), (14, 16, 24))
    draw = ImageDraw.Draw(diag)
    p1 = Image.fromarray(f_arr).resize((416, 234), Image.Resampling.LANCZOS)
    p2 = Image.fromarray(l_arr).resize((416, 234), Image.Resampling.LANCZOS)
    heat = np.clip(diff.mean(axis=2) * 3.0, 0, 255).astype(np.uint8)
    heat_bgr = cv2.applyColorMap(heat, cv2.COLORMAP_INFERNO)
    p3 = Image.fromarray(cv2.cvtColor(heat_bgr, cv2.COLOR_BGR2RGB)).resize((416, 234), Image.Resampling.LANCZOS)
    diag.paste(p1, (10, 20))
    diag.paste(p2, (436, 20))
    diag.paste(p3, (862, 20))
    draw.text((14, 4), "FIRST FRAME 3/4 CLOSE-UP (1280x720)", fill=(120, 230, 255))
    draw.text((440, 4), "LAST FRAME COMMAND CHARGE (1280x720)", fill=(120, 255, 160))
    draw.text((866, 4), f"MOTION HEATMAP (MAE_roi={mae_roi:.2f}, MAE_bg={mae_bg:.2f})", fill=(255, 220, 90))
    diag.save(pair_dir / "preflight_pair_diff.png")

    audit = {
        "pair_id": "pair_ttd_ep01_lucas_001",
        "framing": "3/4 close-up with vanguard soldiers and dynamic push-in",
        "gate_passed": True,
        "first_frame": str(f_path),
        "last_frame": str(l_path),
        "first_sha256": _sha256(f_path),
        "last_sha256": _sha256(l_path),
        "width": 1280,
        "height": 720,
        "mae_bg": round(mae_bg, 4),
        "mae_roi": round(mae_roi, 4),
        "mae_global": round(mae_global, 4),
    }
    (pair_dir / "preflight_pair_audit.json").write_text(json.dumps(audit, indent=2), encoding="utf-8")
    return audit


if __name__ == "__main__":
    stage_3q_closeup_pair()
    res = validate_and_write_preflight_audit()
    print("Pre-flight audit passed:", json.dumps(res, indent=2))
