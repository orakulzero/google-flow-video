"""tests/test_ttd_ep01_m4_visual_audit.py
Pytest verification suite for Milestone 4 Visual Audit, Contact Sheet, and Brain Mirror Parity.
Validates:
1. Master contact sheet geometry (3840 px width, RGB, anti-mock size > 5MB, non-blank variance).
2. Quality audit certificate schema, metrics thresholds (drift, sparks, Laplacian, video faststart).
3. Master manifest completeness and structure (12 keyframes, 2 video cuts, subtitles, contact sheet).
4. Bit-for-bit SHA-256 brain mirror parity.
5. 100% English-only code hygiene (0 literal Cyrillic characters).
REQ-FEAT-10, REQ-FEAT-11, REQ-FEAT-12, REQ-FEAT-14.
Strictly <= 180 lines.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import numpy as np
from PIL import Image

ROOT_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT_DIR / "output"
SHEET_PATH = OUTPUT_DIR / "ttd_ep01_master_contact_sheet.png"
CERT_PATH = OUTPUT_DIR / "ttd_ep01_m4_audit_certificate.json"
MANIFEST_PATH = OUTPUT_DIR / "ttd_ep01_manifest.json"
BRAIN_DIR = Path(r"C:\Users\Orakul Grey\.gemini\antigravity\brain\94dd6a04-54e7-4e8c-9551-224cace4f85f")


def get_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def test_m4_master_contact_sheet_geometry_and_integrity() -> None:
    """Verify master contact sheet exists, has 4K width, non-blank luminance, and passes anti-mock."""
    assert SHEET_PATH.is_file(), f"Master contact sheet missing: {SHEET_PATH}"
    assert SHEET_PATH.stat().st_size >= 5_000_000, f"Contact sheet size too small: {SHEET_PATH.stat().st_size}"

    with Image.open(SHEET_PATH) as im:
        assert im.mode == "RGB", f"Expected RGB mode, got {im.mode}"
        assert im.size[0] == 3840, f"Expected 3840 px width, got {im.size[0]}"
        assert im.size[1] >= 2000, f"Height {im.size[1]} too small"

        arr = np.array(im)
        assert float(np.std(arr)) > 20.0, "Contact sheet appears blank or uniform"
        mean_lum = float(np.mean(arr))
        assert 15.0 <= mean_lum <= 200.0, f"Mean luminance {mean_lum} outside valid dynamic range"


def test_m4_audit_certificate_structure_and_metrics() -> None:
    """Verify audit certificate schema, passing status, and strict metric thresholds."""
    assert CERT_PATH.is_file(), f"Audit certificate missing: {CERT_PATH}"
    cert = json.loads(CERT_PATH.read_text(encoding="utf-8"))

    assert cert["certificate_type"] == "ttd_ep01_m4_quality_audit"
    assert cert["overall_status"] == "PASSED"
    assert cert["total_keyframes"] == 12

    drift = cert["drift_audit"]
    assert drift["passed"] is True
    assert drift["max_mae_bg"] <= 6.0
    assert drift["min_ssim_bg"] >= 0.85

    sparks = cert["spark_laser_audit"]
    assert sparks["passed"] is True
    assert sparks["max_sparks_count"] <= 4

    lap = cert["laplacian_edge_audit"]
    assert lap["passed"] is True
    assert lap["max_sky_laplacian_var"] <= 180.0
    assert 0.90 <= lap["edge_min"] and lap["edge_max"] <= 1.15
    assert lap["max_halo"] <= 0.005

    vid = cert["video_audit"]
    assert vid["passed"] is True
    assert vid["lucas_clip"]["faststart"] is True
    assert vid["lucas_clip"]["anti_mock_passed"] is True
    assert vid["master_pilot"]["faststart"] is True
    assert vid["master_pilot"]["anti_mock_passed"] is True


def test_m4_master_manifest_schema_and_completeness() -> None:
    """Verify unified master manifest indexes all keyframes, video cuts, and contact sheet."""
    assert MANIFEST_PATH.is_file(), f"Master manifest missing: {MANIFEST_PATH}"
    mf = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    assert mf["manifest_type"] == "ttd_ep01_master_production_manifest"
    assert mf["all_passed"] is True
    assert mf["master_contact_sheet"]["width"] == 3840
    assert mf["master_contact_sheet"]["sha256"] == get_sha256(SHEET_PATH)

    kf_info = mf["keyframes"]
    assert kf_info["count"] == 12
    assert len(kf_info["items"]) == 12
    assert kf_info["spark_violations"] == 0

    vids = mf["video_cuts"]
    assert vids["count"] == 2
    assert "lucas_roar_command_clip" in vids
    assert "pilot_master_video" in vids

    subs = mf["subtitles"]
    assert "webvtt" in subs and "srt" in subs


def test_m4_brain_mirror_parity_and_sha256_match() -> None:
    """Verify bit-for-bit SHA-256 mirror parity in persistent brain directory."""
    assert BRAIN_DIR.is_dir(), f"Brain directory missing: {BRAIN_DIR}"

    # 1. Master contact sheet parity
    brain_sheet = BRAIN_DIR / SHEET_PATH.name
    assert brain_sheet.is_file(), f"Mirrored contact sheet missing: {brain_sheet}"
    assert get_sha256(SHEET_PATH) == get_sha256(brain_sheet)

    # 2. Master manifest parity
    brain_mf = BRAIN_DIR / MANIFEST_PATH.name
    assert brain_mf.is_file(), f"Mirrored master manifest missing: {brain_mf}"
    assert get_sha256(MANIFEST_PATH) == get_sha256(brain_mf)

    # 3. Manga transitions manifest regression guard
    legacy_mf = OUTPUT_DIR / "ttd_ep01_manga_transitions" / "manifest.json"
    brain_root_mf = BRAIN_DIR / "manifest.json"
    assert brain_root_mf.is_file()
    assert get_sha256(legacy_mf) == get_sha256(brain_root_mf)


def test_m4_zero_cyrillic_hygiene() -> None:
    """Scan all Milestone 4 source and test files for 0 literal Cyrillic characters."""
    paths_to_audit = [
        ROOT_DIR / "src" / "ttd_contact_sheet_builder.py",
        ROOT_DIR / "src" / "ttd_audit_engine.py",
        ROOT_DIR / "scripts" / "render_ttd_ep01_contact_sheet.py",
        ROOT_DIR / "scripts" / "verify_m4_quality_audit.py",
        Path(__file__),
    ]
    for p in paths_to_audit:
        assert p.is_file(), f"File missing for hygiene audit: {p}"
        text = p.read_text(encoding="utf-8")
        cyr = re.findall(r"[\u0400-\u04FF]", text)
        assert len(cyr) == 0, f"Found {len(cyr)} literal Cyrillic characters in {p.name}"
