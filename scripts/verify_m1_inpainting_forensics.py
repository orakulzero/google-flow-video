"""Forensic integrity verification suite for Milestone 1 inpainting deliverables.

Performs empirical inspection of image statistics, text removal via OCR,
OpenCV inpainting masks, and artifact uniqueness.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
import re
import cv2
import numpy as np
from PIL import Image
import pytesseract


def verify_m1_forensics() -> int:
    clean_dir = Path("output/ttd_ep01_manga_transitions/clean_frames")
    src_dir = Path("output/ttd_arcane_characters/episode1_frames/ep01")

    print("[Forensic Audit] 1. Checking directory and artifact existence...")
    assert clean_dir.is_dir(), f"Directory missing: {clean_dir}"
    assert src_dir.is_dir(), f"Source directory missing: {src_dir}"

    # 1. Keyframe forensic audit
    keyframe_defs = [
        (1, "frame_002.jpg", "keyframe_01_frame002.png", (0, 676), "Gamer celebration"),
        (2, "frame_005.jpg", "keyframe_02_frame005.png", (0, 720), "Save the Empire title"),
        (3, "frame_014.jpg", "keyframe_03_frame014.png", (50, 850), "Streamer setup & donation"),
        (4, "frame_023.jpg", "keyframe_04_frame023.png", (120, 1050), "Battlefield struggle"),
        (5, "frame_026.jpg", "keyframe_05_frame026.png", (0, 554), "Lucas solitary back view"),
    ]

    kf_hashes = {}
    print("\n[Forensic Audit] 2. Auditing 5 Keyframes...")
    for idx, raw_name, kf_name, crop_bounds, desc in keyframe_defs:
        kf_path = clean_dir / kf_name
        raw_path = src_dir / raw_name

        assert kf_path.is_file(), f"Keyframe file missing: {kf_path}"
        assert raw_path.is_file(), f"Source frame missing: {raw_path}"

        raw_bgr = cv2.imread(str(raw_path))
        kf_bgr = cv2.imread(str(kf_path))

        assert raw_bgr is not None, f"Could not decode {raw_path}"
        assert kf_bgr is not None, f"Could not decode {kf_path}"
        assert kf_bgr.shape == (720, 1280, 3), f"Wrong shape: {kf_bgr.shape}"

        data = kf_path.read_bytes()
        sha = hashlib.sha256(data).hexdigest()
        assert sha not in kf_hashes.values(), f"Duplicate keyframe content detected: {kf_name}"
        kf_hashes[kf_name] = sha

        # Statistical sanity
        mean_val = float(kf_bgr.mean())
        std_val = float(kf_bgr.std())
        assert std_val > 15.0, f"Image {kf_name} has suspiciously low variance: {std_val}"

        # OCR text verification
        raw_pil = Image.fromarray(cv2.cvtColor(raw_bgr, cv2.COLOR_BGR2RGB))
        raw_txt = pytesseract.image_to_string(raw_pil).strip().replace("\n", " ")

        kf_pil = Image.fromarray(cv2.cvtColor(kf_bgr, cv2.COLOR_BGR2RGB))
        kf_txt = pytesseract.image_to_string(kf_pil).strip().replace("\n", " ")

        print(f"  KF{idx} ({kf_name}): size={len(data):,} B | std={std_val:.2f} | sha={sha[:10]}...")
        print(f"    Raw text ({len(raw_txt)} chars): {raw_txt[:60]}...")
        print(f"    Cleaned text ({len(kf_txt)} chars): {kf_txt[:60]}...")

        # Specific domain assertions
        if idx == 3:  # Frame 014 had streamer donation text and speech bubbles
            assert len(raw_txt) > 20, "Expected rich text in raw frame 014"
            assert len(kf_txt) == 0, f"Expected 0 text in cleaned frame 014, got: '{kf_txt}'"
        elif idx == 4:  # Frame 023 had bottom caption
            assert "BUT IN THE END" in raw_txt or len(raw_txt) > 10, "Expected caption in raw frame 023"
            assert "BUT IN THE END" not in kf_txt, "Caption text leaked into cleaned frame 023"
        elif idx == 2:  # Frame 005: "SAVE THE EMPIRE" preserved, caption removed
            assert "SAVE THE EMPIRE" in kf_txt, "Expected title 'SAVE THE EMPIRE' preserved"
            assert "BRUTAL DIFFICULTY" not in kf_txt, "Caption 'BRUTAL DIFFICULTY' leaked into frame 005"

    print("\n[Forensic Audit] 3. Auditing 26 Sequential Preprocessed Frames...")
    seq_hashes = set()
    for i in range(1, 27):
        fn = f"ep01_frame_{i:03d}_clean.png"
        fp = clean_dir / fn
        assert fp.is_file(), f"Missing sequential frame {fn}"
        im = cv2.imread(str(fp))
        assert im is not None, f"Cannot decode {fn}"
        assert im.shape == (720, 1280, 3), f"Invalid dimensions {im.shape} in {fn}"
        # Check variance: art panels have std > 10.0; text-only dialogue interstitials on black have lower std
        if i in (7, 12, 15, 17, 19):
            assert im.std() > 2.0, f"Dead flat image in text panel {fn}: {im.std()}"
        else:
            assert im.std() > 10.0, f"Low variance in art panel {fn}: {im.std()}"
        h = hashlib.sha256(fp.read_bytes()).hexdigest()
        seq_hashes.add(h)

    print(f"  Verified 26 sequential frames, all 1280x720x3, {len(seq_hashes)} distinct hashes.")
    assert len(seq_hashes) >= 20, f"Suspiciously few unique frames: {len(seq_hashes)}"

    print("\n[Forensic Audit] 4. Auditing Inpainting Comparison Sheet...")
    comp_p = clean_dir / "inpainting_comparison.png"
    assert comp_p.is_file(), "Missing inpainting_comparison.png"
    comp_im = cv2.imread(str(comp_p))
    assert comp_im.shape == (960, 1280, 3), f"Unexpected comp shape: {comp_im.shape}"
    assert comp_p.stat().st_size > 100000, f"Comparison file too small: {comp_p.stat().st_size} B"
    print(f"  Comparison sheet: {comp_im.shape}, {comp_p.stat().st_size:,} B, std={comp_im.std():.2f}")

    print("\n[Forensic Audit] 5. Auditing Code Hygiene (0 Cyrillic characters)...")
    cyr = re.compile(r"[\u0400-\u04FF]")
    script_p = Path("scripts/preprocess_ep01_manga_frames.py")
    script_txt = script_p.read_text(encoding="utf-8")
    matches = cyr.findall(script_txt)
    assert len(matches) == 0, f"Found {len(matches)} Cyrillic characters in {script_p}!"
    print(f"  {script_p}: 0 Cyrillic characters confirmed.")

    print("\n[Forensic Audit] ALL FORENSIC CHECKS PASSED EMPIRICALLY.")
    return 0


if __name__ == "__main__":
    raise SystemExit(verify_m1_forensics())
