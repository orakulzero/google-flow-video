"""Adversarial empirical verification script for challenger_2_iter2.

Verifies:
1. knight_lucas_solitary_back (.png, .jpg, and brain store mirror) geometry and luminance.
2. Upper-two-thirds visual integrity (rows 0..511) and C1 boundary transition.
3. master_contact_sheet (.png and brain mirror) geometry, 9 populated cells, hashes.
4. Cyrillic hygiene in tests/test_flow_studio.py.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import numpy as np
from PIL import Image

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
CANONICAL_DIR = WORKSPACE_ROOT / "output" / "canonical_arcane_concepts"
BRAIN_DIR = Path(r"C:\Users\Orakul Grey\.gemini\antigravity\brain\94dd6a04-54e7-4e8c-9551-224cace4f85f")
TEST_FILE = WORKSPACE_ROOT / "tests" / "test_flow_studio.py"


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def compute_luma_rec601(rgb: np.ndarray) -> np.ndarray:
    return 0.299 * rgb[:, :, 0] + 0.587 * rgb[:, :, 1] + 0.114 * rgb[:, :, 2]


def compute_luma_rec709(rgb: np.ndarray) -> np.ndarray:
    return 0.2126 * rgb[:, :, 0] + 0.7152 * rgb[:, :, 1] + 0.0722 * rgb[:, :, 2]


def inspect_lucas_images() -> dict:
    results = {}
    png_path = CANONICAL_DIR / "knight_lucas_solitary_back.png"
    jpg_path = CANONICAL_DIR / "knight_lucas_solitary_back.jpg"
    brain_png = BRAIN_DIR / "knight_lucas_solitary_back.png"
    brain_jpg = BRAIN_DIR / "knight_lucas_solitary_back.jpg"

    for name, p in [("canonical_png", png_path), ("canonical_jpg", jpg_path),
                    ("brain_png", brain_png), ("brain_jpg", brain_jpg)]:
        assert p.is_file(), f"File missing: {p}"
        with Image.open(p) as im:
            w, h = im.size
            arr = np.array(im.convert("RGB")).astype(np.float32)
            fmt = im.format

        # Invariant checks
        geom_ok = (w, h) == (1376, 768)
        
        # Bottom-third luminance calculations
        bt_512 = arr[512:, :, :]
        bt_67 = arr[int(h * 0.67):, :, :]  # row 514..768
        
        lum_601_512 = float(compute_luma_rec601(bt_512).mean())
        lum_601_67 = float(compute_luma_rec601(bt_67).mean())
        lum_709_512 = float(compute_luma_rec709(bt_512).mean())
        lum_709_67 = float(compute_luma_rec709(bt_67).mean())

        # Upper two-thirds integrity (rows 0..511)
        upper = arr[:512, :, :]
        upper_mean = float(compute_luma_rec601(upper).mean())
        upper_std = float(compute_luma_rec601(upper).std())
        
        # Boundary transition smoothness: row 511 vs row 512
        r511_mean = float(compute_luma_rec601(arr[511:512, :, :]).mean())
        r512_mean = float(compute_luma_rec601(arr[512:513, :, :]).mean())
        boundary_delta = abs(r512_mean - r511_mean)

        results[name] = {
            "path": str(p),
            "size_bytes": p.stat().st_size,
            "sha256": sha256_file(p),
            "format": fmt,
            "dimensions": f"{w}x{h}",
            "geom_ok": geom_ok,
            "lum_rec601_512": round(lum_601_512, 3),
            "lum_rec601_67": round(lum_601_67, 3),
            "lum_rec709_512": round(lum_709_512, 3),
            "lum_rec709_67": round(lum_709_67, 3),
            "lum_512_ok": lum_601_512 <= 25.0,
            "lum_67_ok": lum_601_67 <= 25.0,
            "upper_mean": round(upper_mean, 3),
            "upper_std": round(upper_std, 3),
            "upper_ok": (upper_mean > 20.0 and upper_std > 20.0),
            "r511_mean": round(r511_mean, 3),
            "r512_mean": round(r512_mean, 3),
            "boundary_delta": round(boundary_delta, 3),
        }
    return results


def inspect_master_contact_sheet() -> dict:
    canonical_sheet = CANONICAL_DIR / "master_contact_sheet.png"
    brain_sheet = BRAIN_DIR / "master_contact_sheet.png"

    assert canonical_sheet.is_file(), f"Missing {canonical_sheet}"
    assert brain_sheet.is_file(), f"Missing {brain_sheet}"

    c_hash = sha256_file(canonical_sheet)
    b_hash = sha256_file(brain_sheet)
    c_size = canonical_sheet.stat().st_size
    b_size = brain_sheet.stat().st_size

    with Image.open(canonical_sheet) as im:
        w, h = im.size
        arr = np.array(im.convert("RGB")).astype(np.float32)

    # In master_contact_sheet.png, check 3x3 cells
    # Overall dimension is 2144x1402
    # Title header takes top ~120px, then grid rows and padding
    # Let's sample 9 distinct regions corresponding to the 9 concept images:
    # Row 0: y in [150..450], Cols: [40..680], [740..1380], [1440..2080]
    # Row 1: y in [560..860], Cols: [40..680], [740..1380], [1440..2080]
    # Row 2: y in [970..1270], Cols: [40..680], [740..1380], [1440..2080]
    cell_names = [
        "Ash Turnaround (top-left)",
        "Ash Desk (top-center)",
        "Lucas Portrait (top-right)",
        "Lucas Turnaround (mid-left)",
        "Lucas Solitary Back (mid-center)",
        "Streamer Room (mid-right)",
        "Streamer Desk Closeup (bot-left)",
        "Save The Empire (bot-center)",
        "Stream Overlay (bot-right)",
    ]

    cell_boxes = [
        (150, 450, 40, 680),
        (150, 450, 740, 1380),
        (150, 450, 1440, 2080),
        (560, 860, 40, 680),
        (560, 860, 740, 1380),
        (560, 860, 1440, 2080),
        (970, 1270, 40, 680),
        (970, 1270, 740, 1380),
        (970, 1270, 1440, 2080),
    ]

    cell_stats = []
    for name, (y0, y1, x0, x1) in zip(cell_names, cell_boxes):
        crop = arr[y0:y1, x0:x1, :]
        luma = compute_luma_rec601(crop)
        m = float(luma.mean())
        s = float(luma.std())
        populated = (m > 10.0 and s > 10.0)
        cell_stats.append({
            "name": name,
            "region": f"y=[{y0}..{y1}], x=[{x0}..{x1}]",
            "mean_luma": round(m, 2),
            "std_luma": round(s, 2),
            "populated": populated,
        })

    all_cells_populated = all(c["populated"] for c in cell_stats)

    return {
        "dimensions": f"{w}x{h}",
        "geom_ok": (w, h) == (2144, 1402),
        "canonical_size": c_size,
        "brain_size": b_size,
        "c_hash": c_hash,
        "b_hash": b_hash,
        "hashes_identical": (c_hash == b_hash),
        "all_cells_populated": all_cells_populated,
        "cell_stats": cell_stats,
    }


def check_cyrillic_hygiene() -> dict:
    content = TEST_FILE.read_text(encoding="utf-8")
    cyrillic_chars = []
    for i, line in enumerate(content.splitlines(), start=1):
        for c in line:
            if "\u0400" <= c <= "\u04ff":
                cyrillic_chars.append({"line": i, "char": c, "text": line.strip()})
    return {
        "cyrillic_count": len(cyrillic_chars),
        "violations": cyrillic_chars[:10],
        "passed": len(cyrillic_chars) == 0,
    }


def main() -> int:
    lucas_data = inspect_lucas_images()
    sheet_data = inspect_master_contact_sheet()
    cyrillic_data = check_cyrillic_hygiene()

    out = {
        "lucas_analysis": lucas_data,
        "contact_sheet_analysis": sheet_data,
        "cyrillic_hygiene": cyrillic_data,
    }
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
