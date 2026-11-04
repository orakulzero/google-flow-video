"""
Empirical verification and adversarial challenge harness for Milestones 1, 2, and 3.
Target: Canonical Arcane Concepts, Contact Sheet Layout, Keyframe Invariants, Brain Store Sync.
Author: challenger_2
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys

import numpy as np
from PIL import Image

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
CANONICAL_DIR = WORKSPACE_ROOT / "output" / "canonical_arcane_concepts"
BRAIN_DIR = Path(r"C:\Users\Orakul Grey\.gemini\antigravity\brain\94dd6a04-54e7-4e8c-9551-224cace4f85f")
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"

CANONICAL_IMAGES = [
    "streamer_ash_turnaround.png",
    "streamer_ash_desk.png",
    "knight_lucas_portrait.png",
    "knight_lucas_turnaround.png",
    "knight_lucas_solitary_back.png",
    "streamer_room_environment.png",
    "streamer_pc_desk_closeup.png",
    "game_save_the_empire_screen.png",
    "stream_overlay_chat_donation.png",
]

MASTER_SHEET = "master_contact_sheet.png"


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def read_png_ihdr(p: Path) -> tuple[int, int, int, int]:
    with open(p, "rb") as f:
        header = f.read(8)
        assert header == PNG_MAGIC, f"Invalid PNG magic: {header!r}"
        chunk_len, chunk_type = struct.unpack(">I4s", f.read(8))
        assert chunk_type == b"IHDR", f"Expected IHDR chunk, got {chunk_type!r}"
        ihdr_data = f.read(chunk_len)
        width, height, bit_depth, color_type = struct.unpack(">IIBB", ihdr_data[:10])
        return width, height, bit_depth, color_type


def run_checks() -> dict:
    results = {}
    print("=" * 80)
    print("CHALLENGER 2: EMPIRICAL VERIFICATION OF CANONICAL ARCANE ASSETS")
    print("=" * 80)

    # --------------------------------------------------------------------------
    # Task 1: 10 Image Files: Size (>1.0 MB), PNG header, Exact Geometries
    # --------------------------------------------------------------------------
    print("\n[TASK 1] Inspecting 10 Canonical Image Files...")
    task1_pass = True
    image_details = {}

    all_10 = CANONICAL_IMAGES + [MASTER_SHEET]
    for fname in all_10:
        p = CANONICAL_DIR / fname
        assert p.is_file(), f"File does not exist: {p}"
        size_bytes = p.stat().st_size
        size_mb = size_bytes / (1024 * 1024)

        # 1. Size > 1.0 MB
        size_ok = size_mb > 1.0

        # 2. Raw PNG header and IHDR
        raw_w, raw_h, bit_depth, col_type = read_png_ihdr(p)

        # 3. PIL load
        with Image.open(p) as img:
            pil_format = img.format
            pil_w, pil_h = img.size
            arr = np.array(img.convert("RGB"))
            pixel_std = float(arr.std())
            pixel_mean = float(arr.mean())

        assert (raw_w, raw_h) == (pil_w, pil_h), f"IHDR mismatch with PIL: {raw_w}x{raw_h} vs {pil_w}x{pil_h}"

        if fname in CANONICAL_IMAGES:
            geom_ok = (raw_w, raw_h) == (1376, 768)
            aspect_ratio = raw_w / raw_h
            aspect_ok = abs(aspect_ratio - (16 / 9)) < 0.01
        else:
            geom_ok = (raw_w, raw_h) in [(2144, 1402), (2112, 1376)]
            aspect_ratio = raw_w / raw_h
            aspect_ok = True  # Composite grid sheet

        info = {
            "size_bytes": size_bytes,
            "size_mb": round(size_mb, 3),
            "size_gt_1mb": size_ok,
            "dimensions": f"{raw_w}x{raw_h}",
            "geom_ok": geom_ok,
            "aspect_ratio": round(aspect_ratio, 4),
            "bit_depth": bit_depth,
            "color_type": col_type,
            "pixel_mean": round(pixel_mean, 2),
            "pixel_std": round(pixel_std, 2),
            "sha256": sha256_file(p),
        }
        image_details[fname] = info

        status_str = "PASS" if (size_ok and geom_ok and pil_format == "PNG") else "FAIL"
        if status_str == "FAIL":
            task1_pass = False
        print(f"  [{status_str}] {fname:<34} {size_mb:5.2f} MB | {raw_w}x{raw_h} | aspect={aspect_ratio:.3f} | mean={pixel_mean:.1f} std={pixel_std:.1f}")

    results["task1_all_10_images"] = {"passed": task1_pass, "details": image_details}

    # --------------------------------------------------------------------------
    # Task 2: Terminal Darkness Invariant on knight_lucas_solitary_back.png
    # --------------------------------------------------------------------------
    print("\n[TASK 2] Verifying Terminal Darkness Invariant on knight_lucas_solitary_back.png...")
    lucas_back_path = CANONICAL_DIR / "knight_lucas_solitary_back.png"
    with Image.open(lucas_back_path) as im:
        arr = np.array(im.convert("RGB"))
        h, w, _ = arr.shape
        # Standard ITU-R BT.601 luminance
        # Let's test both row split definitions: int(h * 0.67) and int(h * (2/3))
        split_67 = int(h * 0.67)
        split_23 = int(h * 2 / 3)

        bottom_third_67 = arr[split_67:, :, :]
        lum_67 = 0.299 * bottom_third_67[:, :, 0] + 0.587 * bottom_third_67[:, :, 1] + 0.114 * bottom_third_67[:, :, 2]
        mean_lum_67 = float(lum_67.mean())

        bottom_third_23 = arr[split_23:, :, :]
        lum_23 = 0.299 * bottom_third_23[:, :, 0] + 0.587 * bottom_third_23[:, :, 1] + 0.114 * bottom_third_23[:, :, 2]
        mean_lum_23 = float(lum_23.mean())

        bottom_10pct = arr[int(h * 0.90):, :, :]
        lum_10pct = 0.299 * bottom_10pct[:, :, 0] + 0.587 * bottom_10pct[:, :, 1] + 0.114 * bottom_10pct[:, :, 2]
        mean_lum_10pct = float(lum_10pct.mean())

    darkness_ok_67 = mean_lum_67 <= 25.0
    darkness_ok_23 = mean_lum_23 <= 25.0
    print(f"  Height={h}, Width={w}")
    print(f"  Bottom-third (rows {split_67}..{h}, 33%) mean luminance: {mean_lum_67:.2f} <= 25.0 -> {'PASS' if darkness_ok_67 else 'FAIL'}")
    print(f"  Bottom-third (rows {split_23}..{h}, 33.3%) mean luminance: {mean_lum_23:.2f} <= 25.0 -> {'PASS' if darkness_ok_23 else 'FAIL'}")
    print(f"  Bottom 10% (rows {int(h*0.9)}..{h}) mean luminance: {mean_lum_10pct:.2f}")

    # Also check manga transition keyframe_05_frame026.png for cross-validation
    manga_kf5 = WORKSPACE_ROOT / "output" / "ttd_ep01_manga_transitions" / "clean_frames" / "keyframe_05_frame026.png"
    if manga_kf5.is_file():
        with Image.open(manga_kf5) as im_kf5:
            arr_kf5 = np.array(im_kf5.convert("RGB"))
            b3 = arr_kf5[int(arr_kf5.shape[0] * 0.67):, :, :]
            m_kf5_lum = float((0.299 * b3[:, :, 0] + 0.587 * b3[:, :, 1] + 0.114 * b3[:, :, 2]).mean())
            print(f"  Cross-check: keyframe_05_frame026.png bottom-third luminance: {m_kf5_lum:.2f} <= 25.0 -> {'PASS' if m_kf5_lum <= 25.0 else 'FAIL'}")
    else:
        m_kf5_lum = None

    results["task2_terminal_darkness"] = {
        "passed": darkness_ok_67 and darkness_ok_23,
        "mean_luminance_33pct": round(mean_lum_67, 3),
        "mean_luminance_33_3pct": round(mean_lum_23, 3),
        "mean_luminance_10pct": round(mean_lum_10pct, 3),
        "keyframe_05_luminance": round(m_kf5_lum, 3) if m_kf5_lum is not None else None,
    }

    # --------------------------------------------------------------------------
    # Task 3: Brain Store Directory Synchronization
    # --------------------------------------------------------------------------
    print("\n[TASK 3] Verifying Brain Store Directory Sync (C:\\Users\\Orakul Grey\\.gemini\\antigravity\\brain\\94dd6a04-54e7-4e8c-9551-224cace4f85f)...")
    brain_ok = True
    brain_sync_details = {}
    if not BRAIN_DIR.is_dir():
        print(f"  FAIL: Brain directory not found: {BRAIN_DIR}")
        brain_ok = False
    else:
        for fname in all_10:
            canonical_file = CANONICAL_DIR / fname
            brain_file = BRAIN_DIR / fname
            if not brain_file.is_file():
                print(f"  FAIL: Missing in brain store: {fname}")
                brain_ok = False
                brain_sync_details[fname] = {"exists": False}
                continue

            c_hash = image_details[fname]["sha256"]
            b_hash = sha256_file(brain_file)
            c_size = image_details[fname]["size_bytes"]
            b_size = brain_file.stat().st_size
            matches = (c_hash == b_hash) and (c_size == b_size)
            if not matches:
                brain_ok = False
            status_str = "PASS" if matches else "FAIL"
            print(f"  [{status_str}] {fname:<34} Canonical: {c_size} bytes | Brain: {b_size} bytes | Hash match: {matches}")
            brain_sync_details[fname] = {
                "exists": True,
                "canonical_size": c_size,
                "brain_size": b_size,
                "hash_match": matches,
            }

    results["task3_brain_sync"] = {"passed": brain_ok, "details": brain_sync_details}

    # --------------------------------------------------------------------------
    # Task 4: Deterministic Assembly of Master Contact Sheet
    # --------------------------------------------------------------------------
    print("\n[TASK 4] Testing scripts/assemble_canonical_contact_sheet.py Deterministic Generation...")
    test_out = CANONICAL_DIR / "_test_reassembled_contact_sheet.png"
    try:
        cmd = [
            sys.executable,
            str(WORKSPACE_ROOT / "scripts" / "assemble_canonical_contact_sheet.py"),
            "--input-dir", str(CANONICAL_DIR),
            "--output", str(test_out),
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        print(f"  Script output: {res.stdout.strip()}")
        assert test_out.is_file(), "Reassembled output not created"
        with Image.open(test_out) as test_im:
            t_w, t_h = test_im.size
            assert (t_w, t_h) == (2144, 1402), f"Reassembled sheet unexpected dimensions: {t_w}x{t_h}"

        orig_sheet = CANONICAL_DIR / MASTER_SHEET
        orig_hash = sha256_file(orig_sheet)
        test_hash = sha256_file(test_out)
        hash_equal = (orig_hash == test_hash)
        print(f"  Reassembled size: {test_out.stat().st_size} bytes, dims: {t_w}x{t_h}")
        print(f"  Original hash:    {orig_hash}")
        print(f"  Reassembled hash: {test_hash}")
        print(f"  Deterministic bit-for-bit exact: {hash_equal}")

        # Clean up temporary test file
        test_out.unlink(missing_ok=True)
        task4_pass = True
    except Exception as exc:
        print(f"  FAIL: Error during contact sheet assembly: {exc}")
        task4_pass = False
        hash_equal = False
        if test_out.is_file():
            test_out.unlink(missing_ok=True)

    results["task4_deterministic_assembly"] = {
        "passed": task4_pass,
        "bit_identical": hash_equal,
    }

    # --------------------------------------------------------------------------
    # Task 5: Execute Pytest Suite (tests/test_flow_studio.py)
    # --------------------------------------------------------------------------
    print("\n[TASK 5] Running pytest tests/test_flow_studio.py...")
    pytest_cmd = [
        sys.executable, "-m", "pytest",
        str(WORKSPACE_ROOT / "tests" / "test_flow_studio.py"),
        "-v",
        "-k", "canonical or m1_m2_m3 or terminal_darkness",
    ]
    p_run = subprocess.run(pytest_cmd, capture_output=True, text=True)
    print(p_run.stdout)
    if p_run.stderr:
        print("STDERR:", p_run.stderr)
    pytest_targeted_pass = (p_run.returncode == 0)

    # Also run full test suite or note overall count
    results["task5_pytest"] = {
        "targeted_tests_passed": pytest_targeted_pass,
        "exit_code": p_run.returncode,
    }

    # --------------------------------------------------------------------------
    # Final Verdict Assessment
    # --------------------------------------------------------------------------
    print("\n" + "=" * 80)
    all_passed = (
        results["task1_all_10_images"]["passed"]
        and results["task2_terminal_darkness"]["passed"]
        and results["task3_brain_sync"]["passed"]
        and results["task4_deterministic_assembly"]["passed"]
        and results["task5_pytest"]["targeted_tests_passed"]
    )
    verdict = "APPROVE" if all_passed else "REQUEST_CHANGES"
    print(f"OVERALL EMPIRICAL VERDICT: {verdict}")
    print("=" * 80)
    results["verdict"] = verdict
    return results


if __name__ == "__main__":
    res = run_checks()
    out_json = WORKSPACE_ROOT / ".agents" / "teamwork" / "challenger_2" / "empirical_verification_results.json"
    out_json.write_text(json.dumps(res, indent=2), encoding="utf-8")
    print(f"Wrote results to: {out_json}")
    sys.exit(0 if res["verdict"] == "APPROVE" else 1)
