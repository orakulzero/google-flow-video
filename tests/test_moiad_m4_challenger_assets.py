"""
Empirical Adversarial Test Suite for Milestone 4 Delivery Assets (m4_challenger_r3_2).
Validates all 85 delivery media assets in Primary and Secondary destinations against Source:
- Exact inventory count (85 files: 21 MP4s, 21 VTTs, 21 SRTs, 21 PNGs, 1 JSON)
- Zero-byte file absence (0 files with size 0 bytes)
- Byte-exact size match and cryptographic SHA-256 parity
- ISO-BMFF container validation and faststart atom layout (moov preceding mdat)
- Clean stream decoding via ffmpeg with zero corruption
- Subtitle and PNG structural integrity and manifest consistency
Critical Invariant: Zero (0) literal Cyrillic characters across the entire suite.
"""

from __future__ import annotations

import hashlib
import json
import struct
import subprocess
from pathlib import Path
from typing import List, Tuple

import imageio_ffmpeg
from PIL import Image
import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT_DIR / "output" / "moiad_video_course"
DST1_DIR = Path("E:/STUDY_NEW_GEN/\u041c\u041e\u0438\u0410\u0414/videos")
DST2_DIR = Path("E:/STUDY_NEW_GEN/\u041c\u041e\u0438\u0410\u0414/reports/release_final/videos")

EXPECTED_CHAPTERS = [f"ch_{p}_{c}" for p in range(1, 5) for c in range(1, 5)]
EXPECTED_PARTS = [f"pr{p}_video" for p in range(1, 5)]


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


def _parse_mp4_atoms(path: Path) -> List[Tuple[str, int, int]]:
    atoms: List[Tuple[str, int, int]] = []
    file_size = path.stat().st_size
    offset = 0
    with open(path, "rb") as f:
        while offset < file_size:
            f.seek(offset)
            hdr = f.read(8)
            if len(hdr) < 8:
                break
            size, name_bytes = struct.unpack(">I4s", hdr)
            name = name_bytes.decode("latin1", errors="replace")
            if size == 1:
                size = struct.unpack(">Q", f.read(8))[0]
            elif size == 0:
                size = file_size - offset
            atoms.append((name, offset, size))
            if size <= 0:
                break
            offset += size
    return atoms


def test_asset_inventory_counts_and_zero_byte_absence() -> None:
    assert SRC_DIR.is_dir(), f"Source dir missing: {SRC_DIR}"
    assert DST1_DIR.is_dir(), f"Primary dir missing: {DST1_DIR}"
    assert DST2_DIR.is_dir(), f"Secondary dir missing: {DST2_DIR}"

    src_files = sorted([f.name for f in SRC_DIR.iterdir() if f.is_file()])
    dst1_files = sorted([f.name for f in DST1_DIR.iterdir() if f.is_file()])
    dst2_files = sorted([f.name for f in DST2_DIR.iterdir() if f.is_file()])

    assert len(src_files) == 85, f"Expected 85 files in SRC, found {len(src_files)}"
    assert len(dst1_files) == 85, f"Expected 85 files in DST1, found {len(dst1_files)}"
    assert len(dst2_files) == 85, f"Expected 85 files in DST2, found {len(dst2_files)}"
    assert src_files == dst1_files, "DST1 filenames do not match SRC"
    assert src_files == dst2_files, "DST2 filenames do not match SRC"

    for d, d_name in [(SRC_DIR, "SRC"), (DST1_DIR, "DST1"), (DST2_DIR, "DST2")]:
        for f in d.iterdir():
            if f.is_file():
                assert f.stat().st_size > 0, f"Zero-byte file detected in {d_name}: {f.name}"


def test_sha256_cryptographic_parity() -> None:
    for f in sorted(SRC_DIR.iterdir()):
        if not f.is_file():
            continue
        h_src = _sha256(f)
        sz_src = f.stat().st_size

        f1 = DST1_DIR / f.name
        f2 = DST2_DIR / f.name

        assert f1.stat().st_size == sz_src, f"Size mismatch for {f.name} in DST1"
        assert f2.stat().st_size == sz_src, f"Size mismatch for {f.name} in DST2"

        h1 = _sha256(f1)
        h2 = _sha256(f2)

        assert h1 == h_src, f"SHA-256 mismatch for {f.name} between SRC and DST1"
        assert h2 == h_src, f"SHA-256 mismatch for {f.name} between SRC and DST2"


def test_mp4_isobmff_faststart_atoms() -> None:
    mp4_files = sorted(DST1_DIR.glob("*.mp4"))
    assert len(mp4_files) == 21, f"Expected 21 MP4 files in DST1, found {len(mp4_files)}"

    for p in mp4_files:
        atoms = _parse_mp4_atoms(p)
        assert len(atoms) >= 2, f"Too few atoms in {p.name}: {atoms}"
        assert atoms[0][0] == "ftyp", f"{p.name} does not start with ftyp: {atoms[0]}"

        moov_boxes = [a for a in atoms if a[0] == "moov"]
        mdat_boxes = [a for a in atoms if a[0] == "mdat"]

        assert len(moov_boxes) == 1, f"{p.name} must contain exactly one moov atom"
        assert len(mdat_boxes) == 1, f"{p.name} must contain exactly one mdat atom"

        moov_offset = moov_boxes[0][1]
        mdat_offset = mdat_boxes[0][1]
        assert moov_offset < mdat_offset, (
            f"Faststart violation in {p.name}: moov@{moov_offset} >= mdat@{mdat_offset}"
        )


def test_mp4_stream_decoding_and_zero_bitstream_errors() -> None:
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    mp4_files = sorted(DST1_DIR.glob("*.mp4"))

    for p in mp4_files:
        res = subprocess.run(
            [ffmpeg, "-v", "error", "-xerror", "-i", str(p), "-f", "null", "-"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        assert res.returncode == 0, f"ffmpeg failed on {p.name}: {res.stderr}"
        assert not res.stderr.strip(), f"Bitstream decode errors in {p.name}: {res.stderr}"


def test_manifest_structure_and_asset_references() -> None:
    manifest_p = DST1_DIR / "manifest.json"
    with open(manifest_p, "r", encoding="utf-8") as f:
        mf = json.load(f)

    assert mf["total_parts"] == 4
    assert mf["total_chapters"] == 16
    assert abs(mf["total_duration_sec"] - 602.88) < 0.1
    assert (DST1_DIR / mf["master_video"]).is_file()
    assert (DST1_DIR / mf["master_contact_sheet"]).is_file()

    part_ids = [p["part_id"] for p in mf["parts"]]
    assert part_ids == EXPECTED_PARTS

    for p in mf["parts"]:
        assert (DST1_DIR / p["mp4"]).is_file()
        assert (DST1_DIR / p["vtt"]).is_file()
        assert (DST1_DIR / p["srt"]).is_file()
        assert (DST1_DIR / p["contact_sheet"]).is_file()
        assert len(p["chapters"]) == 4
        for ch in p["chapters"]:
            assert (DST1_DIR / ch["mp4"]).is_file()
            assert (DST1_DIR / ch["vtt"]).is_file()
            assert (DST1_DIR / ch["keyframe"]).is_file()


def test_subtitles_and_contact_sheets_integrity() -> None:
    vtts = sorted(DST1_DIR.glob("*.vtt"))
    srts = sorted(DST1_DIR.glob("*.srt"))
    pngs = sorted(DST1_DIR.glob("*.png"))

    assert len(vtts) == 21
    assert len(srts) == 21
    assert len(pngs) == 21

    for p in vtts:
        text = p.read_text(encoding="utf-8")
        assert text.startswith("WEBVTT"), f"Missing WEBVTT header in {p.name}"
        assert "-->" in text, f"Missing cue timestamps in {p.name}"

    for p in srts:
        text = p.read_text(encoding="utf-8")
        assert "-->" in text, f"Missing cue timestamps in {p.name}"
        assert text.strip().splitlines()[0] == "1", f"Invalid first cue index in {p.name}"

    for p in pngs:
        with Image.open(p) as img:
            img.verify()
        with Image.open(p) as img:
            assert img.format == "PNG", f"Expected PNG format for {p.name}"
            assert img.size in [(1280, 720), (1920, 1080)], f"Invalid dimensions in {p.name}"
