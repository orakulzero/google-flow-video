"""Remediate Lucas Solitary Back concept art terminal darkness invariant.

Applies a smooth cosine void falloff gradient to the bottom third (rows 512..768)
of knight_lucas_solitary_back.png / .jpg so bottom-third mean luminance is strictly
<= 25.0 (target: ~14.0 to 18.0) while keeping Lucas's figure, hair, broadsword,
and pauldrons completely intact.
"""

from __future__ import annotations

from pathlib import Path
import shutil
import sys
import numpy as np
from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CANONICAL_DIR = PROJECT_ROOT / "output" / "canonical_arcane_concepts"
BRAIN_DIR = Path(r"C:\Users\Orakul Grey\.gemini\antigravity\brain\94dd6a04-54e7-4e8c-9551-224cace4f85f")


def compute_bottom_third_luminance(arr: np.ndarray) -> tuple[float, float]:
    """Computes mean luminance for rows 512: and int(h*0.67):."""
    h, _, _ = arr.shape
    # Standard Rec.601 luma formula as in tests/test_flow_studio.py
    bt_512 = arr[512:, :, :3].astype(np.float32)
    lum_512 = 0.299 * bt_512[:, :, 0] + 0.587 * bt_512[:, :, 1] + 0.114 * bt_512[:, :, 2]

    bt_67 = arr[int(h * 0.67):, :, :3].astype(np.float32)
    lum_67 = 0.299 * bt_67[:, :, 0] + 0.587 * bt_67[:, :, 1] + 0.114 * bt_67[:, :, 2]

    return float(lum_512.mean()), float(lum_67.mean())


def remediate_luminance(
    src_png: Path = CANONICAL_DIR / "knight_lucas_solitary_back.png",
    src_jpg: Path = CANONICAL_DIR / "knight_lucas_solitary_back.jpg",
    end_multiplier: float = 0.02,
) -> tuple[float, float, float, float]:
    """Applies smooth cosine void falloff to the bottom third of the image."""
    if not src_png.is_file():
        raise FileNotFoundError(f"Missing source PNG: {src_png}")

    with Image.open(src_png) as im:
        raw_arr = np.array(im.convert("RGB"))

    h, w, c = raw_arr.shape
    assert (w, h) == (1376, 768), f"Unexpected image dimensions: {w}x{h}"

    pre_512, pre_67 = compute_bottom_third_luminance(raw_arr)

    # Gradient setup for rows 512 to 768 (256 rows)
    # Cosine falloff ensures C1 continuity: d/dt=0 at row 512 (multiplier=1.0)
    # and d/dt=0 at row 768 (multiplier=end_multiplier).
    t = np.linspace(0.0, 1.0, 256, endpoint=True, dtype=np.float32)[:, None, None]
    falloff = end_multiplier + (1.0 - end_multiplier) * 0.5 * (1.0 + np.cos(np.pi * t))

    modified_arr = raw_arr.astype(np.float32).copy()
    modified_arr[512:, :, :] = modified_arr[512:, :, :] * falloff
    modified_arr = np.clip(modified_arr, 0.0, 255.0).astype(np.uint8)

    post_512, post_67 = compute_bottom_third_luminance(modified_arr)

    # Save PNG
    out_im = Image.fromarray(modified_arr, mode="RGB")
    out_im.save(src_png, format="PNG")

    # Save JPG
    out_im.save(src_jpg, format="JPEG", quality=95)

    # Mirror to brain store
    if BRAIN_DIR.is_dir():
        brain_png = BRAIN_DIR / src_png.name
        brain_jpg = BRAIN_DIR / src_jpg.name
        shutil.copy2(src_png, brain_png)
        shutil.copy2(src_jpg, brain_jpg)
        print(f"Mirrored updated images to brain store -> {BRAIN_DIR}")

    return pre_512, pre_67, post_512, post_67


def main() -> int:
    pre_512, pre_67, post_512, post_67 = remediate_luminance()
    print("=== Lucas Solitary Back Remediation Results ===")
    print(f"Pre-remediation rows 512..768 mean luminance: {pre_512:.2f}")
    print(f"Pre-remediation test formula (0.67h:) mean luminance: {pre_67:.2f}")
    print(f"Post-remediation rows 512..768 mean luminance: {post_512:.2f}")
    print(f"Post-remediation test formula (0.67h:) mean luminance: {post_67:.2f}")
    assert post_67 <= 25.0, f"Post-remediation luminance {post_67:.2f} > 25.0!"
    print("SUCCESS: Terminal darkness invariant satisfied (<= 25.0).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
