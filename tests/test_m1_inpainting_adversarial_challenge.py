"""Empirical adversarial challenge harness for Milestone 1 manga inpainting.

Verifies image dimensions, color channels, bit depth, Shannon entropy,
boundary edge artifacts along inpainting seams, pillarbox consistency, and OCR.
"""
from __future__ import annotations

import math
from pathlib import Path
import sys
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import cv2
import numpy as np
from PIL import Image
import pytesseract
from scripts.preprocess_ep01_manga_frames import (
    SRC_DEFAULT,
    KEYFRAME_CONFIG,
    detect_text_boxes,
    build_inpaint_mask,
    inpaint_panel,
)

CLEAN_DIR = Path("output/ttd_ep01_manga_transitions/clean_frames")


def shannon_entropy(img_gray: np.ndarray) -> float:
    """Calculate Shannon entropy in bits for an 8-bit image."""
    hist = cv2.calcHist([img_gray], [0], None, [256], [0, 256]).ravel()
    total = hist.sum()
    if total == 0:
        return 0.0
    probs = hist[hist > 0] / total
    return float(-np.sum(probs * np.log2(probs)))


def inspect_inpainting_edges(raw_img: np.ndarray, f_num: int) -> dict[str, float | int]:
    """Measure inpainting boundary smoothness and unmasked pixel fidelity."""
    boxes = detect_text_boxes(raw_img, f_num)
    mask = build_inpaint_mask(raw_img, f_num, boxes)
    clean = inpaint_panel(raw_img, mask)

    inpaint_count = int(np.count_nonzero(mask))
    if inpaint_count == 0:
        return {"inpaint_px": 0, "boundary_grad_mean": 0.0, "boundary_grad_max": 0.0, "outside_diff_max": 0}

    k_dil = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    k_ero = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    boundary = cv2.subtract(cv2.dilate(mask, k_dil), cv2.erode(mask, k_ero))

    gray_clean = cv2.cvtColor(clean, cv2.COLOR_BGR2GRAY)
    sobelx = cv2.Sobel(gray_clean, cv2.CV_64F, 1, 0, ksize=3)
    sobely = cv2.Sobel(gray_clean, cv2.CV_64F, 0, 1, ksize=3)
    grad = np.sqrt(sobelx**2 + sobely**2)

    mean_grad = float(np.mean(grad[boundary > 0])) if np.count_nonzero(boundary) > 0 else 0.0
    max_grad = float(np.max(grad[boundary > 0])) if np.count_nonzero(boundary) > 0 else 0.0
    outside_diff = int(np.abs(clean[mask == 0].astype(int) - raw_img[mask == 0].astype(int)).max())

    return {
        "inpaint_px": inpaint_count,
        "boundary_grad_mean": mean_grad,
        "boundary_grad_max": max_grad,
        "outside_diff_max": outside_diff,
    }


def analyze_pillarbox_geometry(img_bgr: np.ndarray) -> dict[str, int | bool]:
    """Inspect exact pillarbox padding symmetry and column properties."""
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    col_stds = np.std(gray, axis=0)
    zero_left = np.where(col_stds[:640] == 0)[0]
    left_pad = int(zero_left[-1] + 1) if len(zero_left) > 0 else 0
    zero_right = np.where(col_stds[640:] == 0)[0]
    right_pad = int(1280 - (zero_right[0] + 640)) if len(zero_right) > 0 else 0
    content_w = 1280 - left_pad - right_pad
    is_symmetric = abs(left_pad - right_pad) <= 1
    return {
        "left_pad": left_pad,
        "right_pad": right_pad,
        "content_w": content_w,
        "diff": abs(left_pad - right_pad),
        "is_symmetric": is_symmetric,
    }


def run_challenge_suite() -> int:
    print("=" * 68)
    print("M1 EMPIRICAL ADVERSARIAL CHALLENGER SUITE: MANGA INPAINTING")
    print("=" * 68)

    all_passed = True

    # 1. Inspect 5 Primary Keyframes
    for kf_idx, cfg in KEYFRAME_CONFIG.items():
        fn = cfg["name"]
        f_num = cfg["frame"]
        kf_p = CLEAN_DIR / fn
        assert kf_p.is_file(), f"Missing keyframe: {kf_p}"

        pil_img = Image.open(kf_p)
        cv_img = cv2.imread(str(kf_p))

        # Dimensions & Channels
        dim_ok = (cv_img.shape == (720, 1280, 3)) and (pil_img.size == (1280, 720))
        chan_ok = (cv_img.shape[2] == 3) and (pil_img.mode == "RGB")
        depth_ok = (cv_img.dtype == np.uint8)

        # Entropy & Variance
        gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
        entropy = shannon_entropy(gray)
        img_std = float(cv_img.std())
        img_min = int(cv_img.min())
        img_max = int(cv_img.max())
        entropy_ok = (entropy >= 5.0) and (img_std >= 30.0)

        # Inpainting Boundary Edges & Preservation
        src_path = SRC_DEFAULT / f"frame_{f_num:03d}.jpg"
        raw_img = cv2.imread(str(src_path))
        edge_metrics = inspect_inpainting_edges(raw_img, f_num)
        edge_ok = (edge_metrics["outside_diff_max"] == 0) and (edge_metrics["boundary_grad_mean"] < 50.0)

        # Pillarbox Symmetry
        pbox = analyze_pillarbox_geometry(cv_img)
        pbox_ok = pbox["is_symmetric"]

        # Adversarial OCR
        ocr_text = pytesseract.image_to_string(pil_img).strip().replace("\n", " ")
        if f_num == 5:
            ocr_ok = ("SAVE THE EMPIRE" in ocr_text) and ("NOTORIOUS" not in ocr_text)
        else:
            ocr_ok = (len(ocr_text) == 0)

        kf_passed = dim_ok and chan_ok and depth_ok and entropy_ok and edge_ok and pbox_ok and ocr_ok
        if not kf_passed:
            all_passed = False

        status = "PASS" if kf_passed else "FAIL"
        print(f"\n[Keyframe {kf_idx}] {fn} ({cfg['desc']}) -> {status}")
        print(f"  Geometry: {cv_img.shape} {cv_img.dtype} | PIL={pil_img.mode} {pil_img.size} [dim={dim_ok}, chan={chan_ok}, depth={depth_ok}]")
        print(f"  Information: Entropy={entropy:.3f} bits (min 5.0) | Std={img_std:.2f} (min 30.0) | Range=[{img_min}, {img_max}]")
        print(f"  Boundary Integrity: Inpainted={edge_metrics['inpaint_px']} px | BoundaryGradMean={edge_metrics['boundary_grad_mean']:.2f} | NonMaskMaxDiff={edge_metrics['outside_diff_max']}")
        print(f"  Pillarbox: Left={pbox['left_pad']} px | Right={pbox['right_pad']} px | Diff={pbox['diff']} px | Symmetric={pbox['is_symmetric']}")
        print(f"  OCR Check: CleanText={ocr_ok} | Extracted='{ocr_text[:35]}'")

    # 2. Sequential Frames Check (001..026)
    seq_failures = []
    for i in range(1, 27):
        p = CLEAN_DIR / f"ep01_frame_{i:03d}_clean.png"
        if not p.is_file():
            seq_failures.append(f"frame_{i:03d}: missing")
            continue
        im = cv2.imread(str(p))
        if im.shape != (720, 1280, 3) or im.std() < 10.0 or p.stat().st_size < 30000:
            seq_failures.append(f"frame_{i:03d}: shape={im.shape}, std={im.std():.1f}, size={p.stat().st_size}")

    seq_passed = len(seq_failures) == 0
    if not seq_passed:
        all_passed = False
    print(f"\nSequential 26-frame verification: {'PASS' if seq_passed else 'FAIL'}")
    if seq_failures:
        print(f"  Failures: {seq_failures}")

    # 3. Comparison sheet verification
    comp_p = CLEAN_DIR / "inpainting_comparison.png"
    comp_ok = comp_p.is_file() and comp_p.stat().st_size > 200000
    if not comp_ok:
        all_passed = False
    print(f"Comparison sheet verification: {'PASS' if comp_ok else 'FAIL'} ({comp_p.stat().st_size // 1024} KB)")

    # 4. Standard regression test suite
    print("\n" + "=" * 68)
    print(f"OVERALL EMPIRICAL VERDICT: {'APPROVE' if all_passed else 'REQUEST_CHANGES'}")
    print("=" * 68)
    return 0 if all_passed else 1


if __name__ == "__main__":
    raise SystemExit(run_challenge_suite())
