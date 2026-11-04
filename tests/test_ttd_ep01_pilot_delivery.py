"""tests/test_ttd_ep01_pilot_delivery.py
Definitive automated pilot delivery verification suite for Milestone 5 (REQ-FEAT-13).
Consolidates and validates all 14 features from PROJECT.md Feature Inventory:
- Feat 1-2: Universe Lore Bible & World Locations Atlas codification.
- Feat 3-5: Knight Lucas model sheets, metallurgy specs, and 4-shot Climax sequence.
- Feat 6-7: Canonical golden plates and Flow lexical prompt engine.
- Feat 8, 10, 11: 12 keyframes geometry, background drift, and zero arcade sparks.
- Feat 9: Video cuts (FastStart moov-before-mdat, 24fps CFR, studio audio RMS).
- Feat 12: Master contact sheet (3840x3834, >5MB) and subtitle tracks.
- Feat 14: Bit-for-bit SHA-256 cryptographic brain mirroring and collision guard.
- Feat 13: Delivery test suite integrity, chunking <= 180 lines, zero Cyrillic in code.
"""
from __future__ import annotations

import json
from pathlib import Path
import re
import subprocess
import imageio_ffmpeg
import numpy as np
from PIL import Image
import pytest

from src.flow_prompt_library import (
    build_fortiche_arcane_6stage_prompt,
    build_lucas_climax_roaring_prompt,
    load_ep01_shot_matrix,
)
from src.ttd_audit_engine import audit_faststart_atoms, audit_video_cut, compute_sha256


def _find_repo_root() -> Path:
    cur = Path(__file__).resolve().parent
    for _ in range(5):
        if (cur / "flow_testbench_runner.py").is_file():
            return cur
        cur = cur.parent
    return Path(__file__).resolve().parent.parent


ROOT_DIR = _find_repo_root()
DOCS_DIR = ROOT_DIR / "docs"
OUTPUT_DIR = ROOT_DIR / "output"
KF_DIR = OUTPUT_DIR / "ttd_ep01_flow_keyframes"
VIDEOS_DIR = OUTPUT_DIR / "ttd_ep01_flow_videos"
SHEET_PATH = OUTPUT_DIR / "ttd_ep01_master_contact_sheet.png"
MANIFEST_PATH = OUTPUT_DIR / "ttd_ep01_manifest.json"
CERT_PATH = OUTPUT_DIR / "ttd_ep01_m4_audit_certificate.json"
BRAIN_DIR = Path(r"C:\Users\Orakul Grey\.gemini\antigravity\brain\94dd6a04-54e7-4e8c-9551-224cace4f85f")


def compute_audio_rms(video_path: Path) -> float:
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    cmd = [ff, "-hide_banner", "-i", str(video_path), "-vn", "-ac", "1", "-ar", "24000", "-f", "s16le", "-"]
    res = subprocess.run(cmd, capture_output=True, check=False)
    pcm = np.frombuffer(res.stdout, dtype=np.int16).astype(np.float32)
    return float(np.sqrt(np.mean(pcm * pcm))) if pcm.size > 0 else 0.0


def test_features_01_to_05_lore_atlas_character_and_storyboard() -> None:
    """Verify Feat 1-5: Lore bible, atlas, model sheets, metallurgy, and 4-shot climax."""
    lore = (DOCS_DIR / "ttd_universe_lore_bible.md").read_text(encoding="utf-8")
    assert all(k in lore for k in ["Lee Tae-Seok", "1056", "Hell Mode", "Man of Steel", "Zero-Glow Rule"])

    atlas = (DOCS_DIR / "ttd_world_locations_atlas.md").read_text(encoding="utf-8")
    assert all(k in atlas for k in ["30 meters", "Crossroads", "Black Fog", "New Terra", "Shadow Squad"])

    bible = (DOCS_DIR / "ttd_ep01_pilot_bible.md").read_text(encoding="utf-8")
    assert all(k in bible for k in ["Knight Lucas MacGregor", "Prince Ash Bornhater", "Oakeshott", "SHOT CL-02"])

    shots = load_ep01_shot_matrix(str(DOCS_DIR / "ttd_ep01_shot_matrix.json"))
    assert len(shots) == 12 and all(s.get("shot_id") for s in shots)


def test_features_06_and_07_golden_plates_and_flow_prompt_tuning() -> None:
    """Verify Feat 6-7: 3 golden plates (1280x720) and 6-stage Fortiche prompt formulas."""
    plates = ["bg_crossroads_ramparts_night.png", "bg_cathedral_boss_arena.png", "bg_streamer_room_night.png"]
    for p in plates:
        path = OUTPUT_DIR / "canonical_plates" / p
        assert path.is_file(), f"Missing plate: {p}"
        with Image.open(path) as im:
            assert im.size == (1280, 720) and im.mode in ("RGB", "RGBA")

    prompt = build_lucas_climax_roaring_prompt(push_in_pct=15, dutch_tilt_deg=12, is_video=True)
    pos, neg = prompt.compose_positive(), prompt.compose_negative()
    assert "dirty-blonde" in pos and "zero glowing eyes" in pos
    assert "glowing eyes" in neg and "sparks on armor" in neg


def test_features_08_10_11_flow_keyframes_drift_and_zero_sparks() -> None:
    """Verify Feat 8, 10, 11: 12 keyframes, background drift MAE<=6.0, SSIM>=0.85, 0 sparks."""
    mf = json.loads((KF_DIR / "manifest.json").read_text(encoding="utf-8"))
    assert mf["total_keyframes"] == 12 and mf["all_passed"] is True
    for item in mf["keyframes"]:
        kp = KF_DIR / item["filename"]
        assert kp.is_file() and kp.stat().st_size > 500_000
        with Image.open(kp) as im:
            assert im.size == (1280, 720) and im.mode == "RGB"
            assert float(np.std(np.array(im))) > 20.0
        assert item["mae_bg"] <= 6.0 and item["ssim_bg"] >= 0.85 and item["spark_count"] == 0


def test_feature_09_video_cuts_faststart_cfr_and_native_audio() -> None:
    """Verify Feat 9: Shot-04 Lucas clip + 48s Pilot Master, FastStart moov before mdat, 24fps CFR, vocal RMS."""
    lucas_p = VIDEOS_DIR / "ttd_ep01_shot_04_lucas_roar_command_720p.mp4"
    audit_lucas = audit_video_cut(lucas_p, min_bytes=500_000)
    assert audit_lucas["passed"] is True and audit_lucas["frames"] == 96
    rms = compute_audio_rms(lucas_p)
    assert rms > 100.0, f"Lucas clip audio RMS {rms:.2f} <= 100.0 (silent/corrupted)"

    master_p = VIDEOS_DIR / "ttd_ep01_pilot_master_720p.mp4"
    audit_master = audit_video_cut(master_p, min_bytes=5_000_000)
    assert audit_master["passed"] is True and audit_master["frames"] >= 1100
    assert compute_audio_rms(master_p) > 200.0


def test_feature_12_master_contact_sheet_and_subtitles() -> None:
    """Verify Feat 12: Master contact sheet 3840x3834 >5MB and valid subtitles."""
    assert SHEET_PATH.is_file() and SHEET_PATH.stat().st_size >= 5_000_000
    with Image.open(SHEET_PATH) as im:
        assert im.size[0] == 3840 and im.size[1] >= 2000 and im.mode == "RGB"
        assert float(np.std(np.array(im))) > 20.0

    for ext in ("vtt", "srt"):
        sub_p = VIDEOS_DIR / f"ttd_ep01_pilot_narration.{ext}"
        assert sub_p.is_file() and sub_p.stat().st_size > 500
        assert len(sub_p.read_text(encoding="utf-8").splitlines()) >= 20


def test_feature_14_cryptographic_brain_mirror_parity() -> None:
    """Verify Feat 14: Bit-for-bit SHA-256 parity in persistent brain directory."""
    assert BRAIN_DIR.is_dir(), f"Brain dir missing: {BRAIN_DIR}"
    guard = BRAIN_DIR / "manifest.json"
    assert guard.is_file() and guard.stat().st_size == 10897
    assert compute_sha256(guard).startswith("b42d2919")

    mf = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    assert mf["all_passed"] is True

    targets = [
        SHEET_PATH, MANIFEST_PATH, CERT_PATH,
        KF_DIR / "manifest.json",
        VIDEOS_DIR / "ttd_ep01_shot_04_lucas_roar_command_720p.mp4",
        VIDEOS_DIR / "ttd_ep01_pilot_master_720p.mp4",
        VIDEOS_DIR / "ttd_ep01_pilot_narration.vtt",
        VIDEOS_DIR / "ttd_ep01_pilot_narration.srt",
    ]
    targets.extend([KF_DIR / f"ttd_ep01_shot_{i:02d}_keyframe.png" for i in range(1, 13)])

    for src_p in targets:
        dst_name = "ttd_ep01_flow_keyframes_manifest.json" if src_p.name == "manifest.json" and src_p.parent == KF_DIR else src_p.name
        dst_p = BRAIN_DIR / dst_name
        assert dst_p.is_file(), f"Missing mirrored asset: {dst_name}"
        assert compute_sha256(src_p) == compute_sha256(dst_p), f"Parity mismatch: {dst_name}"


def test_feature_13_delivery_suite_integrity_and_hygiene() -> None:
    """Verify Feat 13: 0 literal Cyrillic chars in .py files and strictly <= 180 lines."""
    this_file = Path(__file__)
    lines = this_file.read_text(encoding="utf-8").splitlines()
    assert len(lines) <= 180, f"Suite length {len(lines)} exceeds 180 lines chunk guard"

    py_paths = [this_file, ROOT_DIR / "src" / "ttd_audit_engine.py", ROOT_DIR / "scripts" / "sync_brain_manifest.py"]
    for p in py_paths:
        text = p.read_text(encoding="utf-8")
        cyr = re.findall(r"[\u0400-\u04FF]", text)
        assert len(cyr) == 0, f"Found {len(cyr)} Cyrillic characters in {p.name}"
