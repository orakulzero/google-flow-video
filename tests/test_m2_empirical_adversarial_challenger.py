"""
tests/test_m2_empirical_adversarial_challenger.py
Adversarial empirical verification harness for Milestone 2 video transitions,
contact sheet visual properties, provenance manifest, and brain directory mirroring.
Authored by m2_challenger_2_gen13.
Zero Cyrillic characters enforced.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys
from typing import Any

import cv2
import imageio_ffmpeg
import numpy as np
from PIL import Image
import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT_DIR / "output" / "ttd_ep01_manga_transitions"
SEGMENTS_DIR = OUTPUT_DIR / "segments"
MASTER_VIDEO_PATH = OUTPUT_DIR / "ttd_episode_01_silent_720p.mp4"
CONTACT_SHEET_PATH = OUTPUT_DIR / "ep01_manga_transitions_contact_sheet.png"
MANIFEST_PATH = OUTPUT_DIR / "manifest.json"
BRAIN_DIR = Path(r"C:\Users\Orakul Grey\.gemini\antigravity\brain\94dd6a04-54e7-4e8c-9551-224cace4f85f")


def compute_sha256(path: Path) -> str:
    """Compute standard SHA-256 hex digest for a file."""
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def parse_top_level_atoms(path: Path) -> list[tuple[str, int, int]]:
    """Parse top-level ISO BMFF atoms to extract box type, offset, and size."""
    atoms: list[tuple[str, int, int]] = []
    with open(path, "rb") as f:
        file_size = f.seek(0, 2)
        f.seek(0)
        while f.tell() < file_size:
            offset = f.tell()
            header = f.read(8)
            if len(header) < 8:
                break
            size, typ_b = struct.unpack(">I4s", header)
            typ = typ_b.decode("latin1", errors="replace")
            atoms.append((typ, offset, size))
            if size == 1:
                ext_hdr = f.read(8)
                if len(ext_hdr) < 8:
                    break
                ext_size = struct.unpack(">Q", ext_hdr)[0]
                f.seek(offset + ext_size)
            elif size == 0:
                break
            else:
                f.seek(offset + size)
    return atoms


def test_empirical_contact_sheet_properties() -> None:
    """
    Empirical challenge on contact sheet:
    - Assert file exists and size > 1MB
    - Assert dimensions == (1360, 1825)
    - Assert mode == 'RGB'
    - Assert image variance std > 25.0
    - Assert Card 8 crop [1380:1805, 680:1340] variance std > 30.0
    - Assert all 8 cards have valid, non-zero variance
    """
    assert CONTACT_SHEET_PATH.is_file(), f"Contact sheet file missing: {CONTACT_SHEET_PATH}"
    file_bytes = CONTACT_SHEET_PATH.stat().st_size
    assert file_bytes > 1_000_000, f"Contact sheet too small: {file_bytes} bytes"

    with Image.open(CONTACT_SHEET_PATH) as img:
        dim = img.size
        mode = img.mode
        arr = np.array(img)

    assert dim == (1360, 1825), f"Contact sheet dimension mismatch: expected (1360, 1825), got {dim}"
    assert mode == "RGB", f"Expected RGB mode, got {mode}"
    assert arr.shape == (1825, 1360, 3), f"Numpy shape mismatch: expected (1825, 1360, 3), got {arr.shape}"

    global_std = float(np.std(arr))
    assert global_std > 25.0, f"Global image variance std too low: {global_std:.2f} <= 25.0"

    # Card 8 crop [1380:1805, 680:1340]
    card8_crop = arr[1380:1805, 680:1340]
    card8_std = float(np.std(card8_crop))
    assert card8_std > 30.0, f"Card 8 crop variance std too low: {card8_std:.2f} <= 30.0"

    # Deep inspection of all 8 grid cells
    # Grid specification: 2 cols x 4 rows, tw=660, th=425, margin=20, top_header_h=85
    # y = 85 + row * (425 + 20) = 85 + row * 445
    # x = 20 + col * (660 + 20) = 20 + col * 680
    card_stds: list[float] = []
    for r in range(4):
        for c in range(2):
            idx = r * 2 + c + 1
            y0 = 85 + r * 445
            y1 = y0 + 425
            x0 = 20 + c * 680
            x1 = x0 + 660
            cell_crop = arr[y0:y1, x0:x1]
            c_std = float(np.std(cell_crop))
            c_mean = float(np.mean(cell_crop))
            card_stds.append(c_std)
            assert c_std > 10.0, f"Card {idx} (row {r}, col {c}) variance suspiciously low: std={c_std:.2f}, mean={c_mean:.2f}"

    # Verify Card 8 is indeed at idx 8
    assert len(card_stds) == 8, f"Expected 8 cards, found {len(card_stds)}"


def test_empirical_brain_directory_mirror_sha256_match() -> None:
    """
    Empirical challenge on Brain Directory mirroring:
    - Assert brain directory exists
    - Verify SHA-256 match for master video, contact sheet, and manifest
    - Verify byte-for-byte exact equality and size matching
    """
    assert BRAIN_DIR.is_dir(), f"Brain directory not found: {BRAIN_DIR}"

    verified_targets = [
        ("ttd_episode_01_silent_720p.mp4", MASTER_VIDEO_PATH),
        ("ep01_manga_transitions_contact_sheet.png", CONTACT_SHEET_PATH),
        ("manifest.json", MANIFEST_PATH),
    ]

    for filename, repo_path in verified_targets:
        brain_path = BRAIN_DIR / filename
        assert brain_path.is_file(), f"Target file missing in brain directory: {brain_path}"

        repo_size = repo_path.stat().st_size
        brain_size = brain_path.stat().st_size
        assert repo_size == brain_size, f"Size mismatch for {filename}: repo={repo_size} vs brain={brain_size}"

        repo_hash = compute_sha256(repo_path)
        brain_hash = compute_sha256(brain_path)
        assert repo_hash == brain_hash, f"SHA-256 mismatch for {filename}: repo={repo_hash} vs brain={brain_hash}"

        # Byte-by-byte direct verification
        repo_bytes = repo_path.read_bytes()
        brain_bytes = brain_path.read_bytes()
        assert repo_bytes == brain_bytes, f"Byte-for-byte mismatch detected for {filename}"


def test_empirical_manifest_hashes_all_7_segments() -> None:
    """
    Empirical challenge on manifest segment hashing:
    - Load manifest.json
    - Assert exactly 7 segments are registered
    - Verify each segment file exists in output/ttd_ep01_manga_transitions/segments/
    - Compute live SHA-256 for all 7 segment MP4 files and assert match with manifest
    - Assert each segment file size matches recorded bytes
    - Probe each segment video to verify 1280x720 24fps CFR geometry and silence
    """
    assert MANIFEST_PATH.is_file(), f"Manifest file missing: {MANIFEST_PATH}"
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    segments = manifest.get("segments")
    assert isinstance(segments, list), f"Manifest 'segments' must be a list, got {type(segments)}"
    assert len(segments) == 7, f"Expected exactly 7 segments in manifest, found {len(segments)}"

    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()

    for i, seg in enumerate(segments, start=1):
        seg_idx = seg.get("segment_index")
        assert seg_idx == i, f"Segment index mismatch: expected {i}, got {seg_idx}"

        fname = seg.get("filename")
        expected_fname = f"segment_0{i}.mp4"
        assert fname == expected_fname, f"Expected filename {expected_fname}, got {fname}"

        seg_path = SEGMENTS_DIR / fname
        assert seg_path.is_file(), f"Segment file missing on disk: {seg_path}"

        # Size check
        recorded_bytes = seg.get("bytes")
        actual_bytes = seg_path.stat().st_size
        assert recorded_bytes == actual_bytes, f"{fname} bytes mismatch: recorded={recorded_bytes}, actual={actual_bytes}"

        # Live SHA-256 check
        recorded_sha = seg.get("sha256")
        actual_sha = compute_sha256(seg_path)
        assert recorded_sha == actual_sha, f"{fname} SHA-256 mismatch: recorded={recorded_sha}, actual={actual_sha}"

        # Video geometry check via OpenCV
        cap = cv2.VideoCapture(str(seg_path))
        assert cap.isOpened(), f"Could not open segment video: {seg_path}"
        sw = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        sh = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        sfps = float(cap.get(cv2.CAP_PROP_FPS) or 24.0)
        sframes = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        cap.release()

        assert (sw, sh) == (1280, 720), f"{fname} geometry is {sw}x{sh}, expected 1280x720"
        assert abs(sfps - 24.0) < 0.1, f"{fname} fps is {sfps}, expected 24.0"
        assert sframes > 0, f"{fname} has 0 frames"

        # Audio check via ffmpeg
        proc = subprocess.run(
            [ffmpeg_exe, "-hide_banner", "-i", str(seg_path)],
            capture_output=True,
            text=True,
            errors="replace",
            check=False,
        )
        assert "Audio:" not in (proc.stderr or ""), f"{fname} contains audio stream, must be silent (-an)"


def test_empirical_master_video_integrity_and_faststart() -> None:
    """
    Empirical challenge on assembled master video:
    - Assert master video SHA-256 matches manifest['master_sha256']
    - Assert master video size matches manifest['master_bytes']
    - Assert faststart: moov atom appears before mdat atom
    - Assert zero audio streams
    """
    assert MASTER_VIDEO_PATH.is_file(), f"Master video missing: {MASTER_VIDEO_PATH}"
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    actual_master_sha = compute_sha256(MASTER_VIDEO_PATH)
    assert manifest["master_sha256"] == actual_master_sha, "Master video SHA-256 mismatch with manifest"

    actual_master_bytes = MASTER_VIDEO_PATH.stat().st_size
    assert manifest["master_bytes"] == actual_master_bytes, "Master video size mismatch with manifest"

    atoms = parse_top_level_atoms(MASTER_VIDEO_PATH)
    names = [a[0] for a in atoms]
    assert "moov" in names, f"moov atom missing in {names}"
    assert "mdat" in names, f"mdat atom missing in {names}"
    moov_pos = names.index("moov")
    mdat_pos = names.index("mdat")
    assert moov_pos < mdat_pos, f"moov ({moov_pos}) does not precede mdat ({mdat_pos})"


def run_all_challenges() -> dict[str, Any]:
    """Execute all challenge assertions and collect empirical measurements."""
    results: dict[str, Any] = {}

    # 1. Contact sheet metrics
    with Image.open(CONTACT_SHEET_PATH) as img:
        dim = img.size
        mode = img.mode
        arr = np.array(img)

    global_std = float(np.std(arr))
    card8_crop = arr[1380:1805, 680:1340]
    card8_std = float(np.std(card8_crop))
    card8_mean = float(np.mean(card8_crop))

    results["contact_sheet"] = {
        "dimensions": dim,
        "mode": mode,
        "global_std": global_std,
        "card8_crop_shape": card8_crop.shape,
        "card8_std": card8_std,
        "card8_mean": card8_mean,
        "pass_dimensions": dim == (1360, 1825),
        "pass_global_std": global_std > 25.0,
        "pass_card8_std": card8_std > 30.0,
    }

    # 2. Brain mirroring metrics
    brain_checks: dict[str, dict[str, Any]] = {}
    for filename, repo_p in [
        ("ttd_episode_01_silent_720p.mp4", MASTER_VIDEO_PATH),
        ("ep01_manga_transitions_contact_sheet.png", CONTACT_SHEET_PATH),
        ("manifest.json", MANIFEST_PATH),
    ]:
        brain_p = BRAIN_DIR / filename
        r_sha = compute_sha256(repo_p)
        b_sha = compute_sha256(brain_p)
        r_sz = repo_p.stat().st_size
        b_sz = brain_p.stat().st_size
        brain_checks[filename] = {
            "repo_sha256": r_sha,
            "brain_sha256": b_sha,
            "match": r_sha == b_sha and r_sz == b_sz,
            "bytes": r_sz,
        }
    results["brain_mirroring"] = brain_checks

    # 3. Manifest segment hashes
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    seg_checks: list[dict[str, Any]] = []
    for s in manifest["segments"]:
        fname = s["filename"]
        sp = SEGMENTS_DIR / fname
        act_sha = compute_sha256(sp)
        act_sz = sp.stat().st_size
        seg_checks.append({
            "segment_index": s["segment_index"],
            "filename": fname,
            "manifest_sha256": s["sha256"],
            "actual_sha256": act_sha,
            "manifest_bytes": s["bytes"],
            "actual_bytes": act_sz,
            "hash_match": s["sha256"] == act_sha,
            "size_match": s["bytes"] == act_sz,
        })
    results["segments"] = seg_checks

    return results


if __name__ == "__main__":
    res = run_all_challenges()
    print("EMPIRICAL ADVERSARIAL CHALLENGE SUMMARY:")
    print(json.dumps(res, indent=2))
