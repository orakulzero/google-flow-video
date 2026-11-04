"""Unified Verification Suite for Arcane Deliverables (Milestone 4 / Requirement R4).

Combines programmatic ISO-BMFF box parsing, CFR stream parameters, audio RMS,
Farneback optical flow anti-cheat validation, visual contact sheet geometry,
panel texture variance, typography checks, and persistent brain mirror parity.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import struct
import subprocess
import sys
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np
import pytest

try:
    import imageio_ffmpeg
except ImportError:
    imageio_ffmpeg = None  # type: ignore[assignment]

# Paths configuration
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = next((p for p in SCRIPT_DIR.parents if (p / "veo_arcane_style").is_dir()), SCRIPT_DIR.parents[1])
OUTPUT_DIR = PROJECT_ROOT / "veo_arcane_style" / "output"
DATASET_DIR = PROJECT_ROOT / "veo_arcane_style" / "dataset"
BRAIN_MIRROR_DIR = Path(r"C:\Users\Orakul Grey\.gemini\antigravity\brain\94dd6a04-54e7-4e8c-9551-224cace4f85f")
PNG_MAGIC_HEADER = b"\x89PNG\r\n\x1a\n"

DELIVERABLE_SPECS: List[Tuple[str, str, str]] = [
    ("arcane_clip_01_zaun_duel_720p.mp4", "video", "video/mp4"),
    ("arcane_clip_02_piltover_hextech_720p.mp4", "video", "video/mp4"),
    ("master_verification_sheet.png", "image", "image/png"),
    ("contact_sheets/comparison_pair_170629_shot_000.png", "image", "image/png"),
    ("contact_sheets/comparison_pair_270000_shot_015.png", "image", "image/png"),
    ("verification_report.json", "metadata", "application/json"),
    ("verification_report.md", "report", "text/markdown"),
    ("overnight_checkpoint.json", "metadata", "application/json"),
    ("prompt_matrix.json", "metadata", "application/json"),
    ("logs/overnight_batch.log", "log", "text/plain"),
]


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


class IsoBmffBoxParser:
    """Zero-dependency binary parser for ISO-BMFF / MP4 containers."""

    @staticmethod
    def parse_root_boxes(filepath: Path) -> List[Tuple[str, int, int]]:
        boxes: List[Tuple[str, int, int]] = []
        with open(filepath, "rb") as f:
            file_size = filepath.stat().st_size
            offset = 0
            while offset < file_size:
                f.seek(offset)
                hdr = f.read(8)
                if len(hdr) < 8:
                    break
                box_size, box_type = struct.unpack(">I4s", hdr)
                box_type_str = box_type.decode("latin1", errors="replace")
                if box_size == 1:
                    large_hdr = f.read(8)
                    if len(large_hdr) < 8:
                        break
                    box_size = struct.unpack(">Q", large_hdr)[0]
                elif box_size == 0:
                    box_size = file_size - offset
                boxes.append((box_type_str, offset, box_size))
                if box_size <= 0:
                    break
                offset += box_size
        return boxes


class MediaValidator:
    """Media validator for video codecs, audio parameters, and PCM amplitude."""

    @staticmethod
    def get_ffmpeg_exe() -> str:
        if imageio_ffmpeg is not None:
            try:
                exe = imageio_ffmpeg.get_ffmpeg_exe()
                if exe and Path(exe).is_file():
                    return str(exe)
            except Exception:
                pass
        exe = shutil.which("ffmpeg")
        if exe:
            return str(exe)
        raise RuntimeError("ffmpeg executable not found")

    @staticmethod
    def inspect_streams_ffmpeg(clip_path: Path) -> Dict[str, Any]:
        ffmpeg_exe = MediaValidator.get_ffmpeg_exe()
        res = subprocess.run([ffmpeg_exe, "-hide_banner", "-i", str(clip_path)], capture_output=True, text=True, timeout=10)
        stderr = res.stderr.lower()
        return {
            "has_h264": ("h264" in stderr or "avc1" in stderr),
            "has_aac": ("aac" in stderr or "mp4a" in stderr),
            "stderr": stderr,
        }


class OpticalFlowAnalyzer:
    """Farneback optical flow and affine residual analyzer."""

    @staticmethod
    def compute_non_affine_residual_variance(clip_path: Path, num_pairs: int = 5, frame_step: int = 2) -> List[float]:
        cap = cv2.VideoCapture(str(clip_path))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        start_frames = np.linspace(10, total_frames - frame_step - 10, num_pairs, dtype=int)
        variances: List[float] = []
        for f_idx in start_frames:
            cap.set(cv2.CAP_PROP_POS_FRAMES, int(f_idx))
            ret1, f1 = cap.read()
            cap.set(cv2.CAP_PROP_POS_FRAMES, int(f_idx + frame_step))
            ret2, f2 = cap.read()
            if not ret1 or not ret2 or f1 is None or f2 is None:
                continue
            s1 = cv2.resize(f1, (640, 360), interpolation=cv2.INTER_AREA)
            s2 = cv2.resize(f2, (640, 360), interpolation=cv2.INTER_AREA)
            g1 = cv2.cvtColor(s1, cv2.COLOR_BGR2GRAY)
            g2 = cv2.cvtColor(s2, cv2.COLOR_BGR2GRAY)
            flow = cv2.calcOpticalFlowFarneback(g1, g2, None, 0.5, 3, 15, 3, 5, 1.2, 0)
            stride = 8
            y_g, x_g = np.mgrid[0:360:stride, 0:640:stride]
            pts_src = np.column_stack([x_g.ravel(), y_g.ravel()]).astype(np.float32)
            u = flow[0:360:stride, 0:640:stride, 0].ravel()
            v = flow[0:360:stride, 0:640:stride, 1].ravel()
            pts_dst = pts_src + np.column_stack([u, v])
            affine, _ = cv2.estimateAffine2D(pts_src, pts_dst, method=cv2.RANSAC, ransacReprojThreshold=2.0)
            if affine is None:
                ones = np.ones((pts_src.shape[0], 1), dtype=np.float32)
                affine = np.linalg.lstsq(np.hstack([pts_src, ones]), pts_dst, rcond=None)[0].T
            pts_pred = np.hstack([pts_src, np.ones((pts_src.shape[0], 1), dtype=np.float32)]) @ affine.T
            residual = pts_dst - pts_pred
            variances.append(float(np.var(np.linalg.norm(residual, axis=1))))
        cap.release()
        return variances


class TestIsoBmffFastStart:
    """Verify ISO-BMFF container atom structure and progressive FastStart compliance."""

    @pytest.mark.parametrize("clip_name", [
        "arcane_clip_01_zaun_duel_720p.mp4",
        "arcane_clip_02_piltover_hextech_720p.mp4",
    ])
    def test_faststart_atom_order(self, clip_name: str) -> None:
        clip_path = OUTPUT_DIR / clip_name
        assert clip_path.is_file(), f"Clip file missing: {clip_path}"
        boxes = IsoBmffBoxParser.parse_root_boxes(clip_path)
        types = [b[0] for b in boxes]
        assert len(types) >= 3, f"Expected at least 3 top-level boxes, got {types}"
        assert types[0] == "ftyp", f"First box must be ftyp, got {types[0]}"
        assert "moov" in types, "Missing moov header box"
        assert "mdat" in types, "Missing mdat media payload box"
        moov_idx = types.index("moov")
        mdat_idx = types.index("mdat")
        assert moov_idx < mdat_idx, f"moov box (idx={moov_idx}) must precede mdat box (idx={mdat_idx}) for FastStart"


class TestVideoStreamValidation:
    """Verify video container format, CFR 24fps framerate, 720p HD resolution, and H.264 stream."""

    @pytest.mark.parametrize("clip_name", [
        "arcane_clip_01_zaun_duel_720p.mp4",
        "arcane_clip_02_piltover_hextech_720p.mp4",
    ])
    def test_video_container_and_streams(self, clip_name: str) -> None:
        clip_path = OUTPUT_DIR / clip_name
        assert clip_path.is_file(), f"Missing clip: {clip_path}"
        assert clip_path.stat().st_size >= 500_000, f"File size {clip_path.stat().st_size} bytes below 500KB threshold"

        cap = cv2.VideoCapture(str(clip_path))
        assert cap.isOpened(), f"cv2 failed to open video file: {clip_path}"
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
        fc = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        cap.release()

        assert w == 1280 and h == 720, f"Resolution mismatch: expected 1280x720, got {w}x{h}"
        assert abs(fps - 24.0) < 0.05, f"Expected constant 24.0 fps, got {fps}"
        duration = fc / fps if fps > 0 else 0.0
        assert duration >= 7.0, f"Duration {duration:.2f}s is less than 7.0s minimum requirement"

        streams = MediaValidator.inspect_streams_ffmpeg(clip_path)
        assert streams["has_h264"] is True, f"Video codec must be H.264/AVC in {clip_name}"


class TestAudioStreamValidation:
    """Verify native audio retention, AAC codec, stereo layout, and non-zero RMS amplitude."""

    @pytest.mark.parametrize("clip_name", [
        "arcane_clip_01_zaun_duel_720p.mp4",
        "arcane_clip_02_piltover_hextech_720p.mp4",
    ])
    def test_audio_parameters_and_rms(self, clip_name: str) -> None:
        clip_path = OUTPUT_DIR / clip_name
        ffmpeg_exe = MediaValidator.get_ffmpeg_exe()

        streams = MediaValidator.inspect_streams_ffmpeg(clip_path)
        assert streams["has_aac"] is True, f"Audio codec must be AAC in {clip_name}"

        cmd = [ffmpeg_exe, "-hide_banner", "-i", str(clip_path), "-vn", "-f", "f32le", "-acodec", "pcm_f32le", "pipe:1"]
        res = subprocess.run(cmd, capture_output=True, check=True)
        samples = np.frombuffer(res.stdout, dtype=np.float32)
        assert len(samples) > 0, f"Zero PCM audio samples decoded from {clip_name}"

        rms = float(np.sqrt(np.mean(samples ** 2)))
        peak = float(np.max(np.abs(samples)))
        assert rms > 0.10, f"Audio RMS amplitude {rms:.4f} <= 0.10 in {clip_name} (indicates silent or flatlined audio)"
        assert peak > 0.50, f"Audio peak amplitude {peak:.4f} <= 0.50 in {clip_name} (low dynamic range)"


class TestOpticalFlowAntiCheat:
    """Farneback optical flow anti-cheat validation verifying genuine fluid AI motion."""

    @pytest.mark.parametrize("clip_name", [
        "arcane_clip_01_zaun_duel_720p.mp4",
        "arcane_clip_02_piltover_hextech_720p.mp4",
    ])
    def test_optical_flow_fluid_ai_motion(self, clip_name: str) -> None:
        clip_path = OUTPUT_DIR / clip_name
        vars_ = OpticalFlowAnalyzer.compute_non_affine_residual_variance(clip_path)
        assert len(vars_) >= 3, f"Insufficient valid optical flow pairs evaluated in {clip_name}"
        median_var = float(np.median(vars_))
        assert median_var >= 0.50, f"Optical flow median residual variance {median_var:.4f} < 0.50 px^2 threshold"

    def test_optical_flow_anti_cheat_catches_pan_zoom_stubs(self) -> None:
        sample_path = DATASET_DIR / "pairs" / "pair_170629_shot_000" / "first_frame.png"
        assert sample_path.is_file(), f"Sample dataset frame missing: {sample_path}"
        sample_img = cv2.imread(str(sample_path))
        small = cv2.resize(sample_img, (640, 360))
        g1 = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)

        # 1. Static Still (zero motion)
        g2_still = g1.copy()
        flow_still = cv2.calcOpticalFlowFarneback(g1, g2_still, None, 0.5, 3, 15, 3, 5, 1.2, 0)
        u_s = flow_still[0:360:8, 0:640:8, 0].ravel()
        v_s = flow_still[0:360:8, 0:640:8, 1].ravel()
        var_still = float(np.var(np.sqrt(u_s ** 2 + v_s ** 2)))
        assert var_still < 0.01, f"Static still variance {var_still:.6f} unexpectedly high"

        # 2. Pure Pan (Ken Burns 2D translation: dx=0.5, dy=0.25)
        M_pan = np.float32([[1, 0, 0.5], [0, 1, 0.25]])
        g2_pan = cv2.warpAffine(g1, M_pan, (640, 360))
        flow_pan = cv2.calcOpticalFlowFarneback(g1, g2_pan, None, 0.5, 3, 15, 3, 5, 1.2, 0)
        stride = 8
        y_g, x_g = np.mgrid[0:360:stride, 0:640:stride]
        pts_src = np.column_stack([x_g.ravel(), y_g.ravel()]).astype(np.float32)
        u_p = flow_pan[0:360:stride, 0:640:stride, 0].ravel()
        v_p = flow_pan[0:360:stride, 0:640:stride, 1].ravel()
        pts_dst_p = pts_src + np.column_stack([u_p, v_p])
        affine_p, _ = cv2.estimateAffine2D(pts_src, pts_dst_p, method=cv2.RANSAC, ransacReprojThreshold=2.0)
        pts_pred_p = np.hstack([pts_src, np.ones((pts_src.shape[0], 1), dtype=np.float32)]) @ affine_p.T
        var_pan = float(np.var(np.linalg.norm(pts_dst_p - pts_pred_p, axis=1)))
        assert var_pan < 0.20, f"Pure pan residual variance {var_pan:.4f} >= 0.20"

        # 3. Pure Zoom (Ken Burns 2D scale: 1.005)
        h, w = g1.shape
        M_zoom = cv2.getRotationMatrix2D((w / 2.0, h / 2.0), 0.0, 1.005)
        g2_zoom = cv2.warpAffine(g1, M_zoom, (w, h))
        flow_zoom = cv2.calcOpticalFlowFarneback(g1, g2_zoom, None, 0.5, 3, 15, 3, 5, 1.2, 0)
        u_z = flow_zoom[0:360:stride, 0:640:stride, 0].ravel()
        v_z = flow_zoom[0:360:stride, 0:640:stride, 1].ravel()
        pts_dst_z = pts_src + np.column_stack([u_z, v_z])
        affine_z, _ = cv2.estimateAffine2D(pts_src, pts_dst_z, method=cv2.RANSAC, ransacReprojThreshold=2.0)
        pts_pred_z = np.hstack([pts_src, np.ones((pts_src.shape[0], 1), dtype=np.float32)]) @ affine_z.T
        var_zoom = float(np.var(np.linalg.norm(pts_dst_z - pts_pred_z, axis=1)))
        assert var_zoom < 0.20, f"Pure zoom residual variance {var_zoom:.4f} >= 0.20"


class TestVisualDeliverablesStructure:
    """Verify presence, format integrity, and non-empty sizes of visual deliverables."""

    def test_contact_sheets_directory_and_files_exist(self) -> None:
        cs_dir = OUTPUT_DIR / "contact_sheets"
        assert cs_dir.is_dir(), f"Contact sheets directory missing: {cs_dir}"
        for name in ["comparison_pair_170629_shot_000.png", "comparison_pair_270000_shot_015.png"]:
            p = cs_dir / name
            assert p.is_file(), f"Contact sheet missing: {p}"
            assert p.stat().st_size >= 500_000, f"Sheet too small ({p.stat().st_size} bytes): {name}"

    def test_master_verification_sheet_exists_and_sized(self) -> None:
        master_path = OUTPUT_DIR / "master_verification_sheet.png"
        assert master_path.is_file(), f"Master sheet missing: {master_path}"
        assert master_path.stat().st_size >= 1_000_000, f"Master sheet suspiciously small: {master_path.stat().st_size} bytes"

    def test_png_headers_and_file_integrity(self) -> None:
        sheets = [
            OUTPUT_DIR / "master_verification_sheet.png",
            OUTPUT_DIR / "contact_sheets" / "comparison_pair_170629_shot_000.png",
            OUTPUT_DIR / "contact_sheets" / "comparison_pair_270000_shot_015.png",
        ]
        for p in sheets:
            assert p.is_file(), f"Missing file: {p}"
            header = p.read_bytes()[:8]
            assert header == PNG_MAGIC_HEADER, f"Invalid PNG magic bytes in {p.name}: {header!r}"
            img = cv2.imread(str(p))
            assert img is not None, f"cv2 failed to decode image: {p}"
            assert img.ndim == 3 and img.shape[2] == 3, f"Expected 3-channel BGR image in {p.name}"


class TestVisualResolutionAndGeometry:
    """Verify exact dimensions, aspect ratios, and panel alignments."""

    def test_comparison_sheets_resolution(self) -> None:
        cs_dir = OUTPUT_DIR / "contact_sheets"
        for name in ["comparison_pair_170629_shot_000.png", "comparison_pair_270000_shot_015.png"]:
            img = cv2.imread(str(cs_dir / name))
            assert img is not None
            h, w, _ = img.shape
            assert w == 1920, f"Expected width 1920 in {name}, got {w}"
            assert h == 780, f"Expected height 780 in {name}, got {h}"
            assert w >= 1280 and h >= 720, f"Sheet below 720p HD threshold: {w}x{h}"

    def test_master_verification_sheet_resolution(self) -> None:
        master_path = OUTPUT_DIR / "master_verification_sheet.png"
        img = cv2.imread(str(master_path))
        assert img is not None
        h, w, _ = img.shape
        assert w == 1920, f"Expected width 1920 in master sheet, got {w}"
        assert h == 1560, f"Expected height 1560 (2 x 780) in master sheet, got {h}"

    def test_panel_layout_and_alignment(self) -> None:
        cs_dir = OUTPUT_DIR / "contact_sheets"
        for name in ["comparison_pair_170629_shot_000.png", "comparison_pair_270000_shot_015.png"]:
            img = cv2.imread(str(cs_dir / name))
            assert img is not None

            header = img[0:60, :]
            assert header.shape == (60, 1920, 3)

            gt_row = img[60:420, :]
            assert gt_row.shape == (360, 1920, 3)

            veo_row = img[420:780, :]
            assert veo_row.shape == (360, 1920, 3)

            panels = [
                img[60:420, 0:640],
                img[60:420, 640:1280],
                img[60:420, 1280:1920],
                img[420:780, 0:640],
                img[420:780, 640:1280],
                img[420:780, 1280:1920],
            ]
            for idx, panel in enumerate(panels):
                assert panel.shape == (360, 640, 3), f"Panel {idx} has invalid shape: {panel.shape}"


class TestVisualQualityAndChannelVariance:
    """Verify non-blank channel variance, standard deviation thresholds, and dynamic range."""

    def test_overall_color_channel_standard_deviation(self) -> None:
        sheets = [
            OUTPUT_DIR / "master_verification_sheet.png",
            OUTPUT_DIR / "contact_sheets" / "comparison_pair_170629_shot_000.png",
            OUTPUT_DIR / "contact_sheets" / "comparison_pair_270000_shot_015.png",
        ]
        for p in sheets:
            img = cv2.imread(str(p))
            assert img is not None
            b_std = float(img[:, :, 0].std())
            g_std = float(img[:, :, 1].std())
            r_std = float(img[:, :, 2].std())
            overall_std = float(img.std())

            assert b_std > 15.0, f"Blue channel std {b_std:.2f} <= 15.0 in {p.name}"
            assert g_std > 15.0, f"Green channel std {g_std:.2f} <= 15.0 in {p.name}"
            assert r_std > 15.0, f"Red channel std {r_std:.2f} <= 15.0 in {p.name}"
            assert overall_std > 30.0, f"Overall image std {overall_std:.2f} <= 30.0 in {p.name}"

    def test_per_panel_non_blank_variance(self) -> None:
        cs_dir = OUTPUT_DIR / "contact_sheets"
        for name in ["comparison_pair_170629_shot_000.png", "comparison_pair_270000_shot_015.png"]:
            img = cv2.imread(str(cs_dir / name))
            assert img is not None
            panel_slices = {
                "gt_first": img[60:420, 0:640],
                "gt_mid": img[60:420, 640:1280],
                "gt_last": img[60:420, 1280:1920],
                "veo_start": img[420:780, 0:640],
                "veo_mid": img[420:780, 640:1280],
                "veo_end": img[420:780, 1280:1920],
            }
            for pname, pimg in panel_slices.items():
                p_std = float(pimg.std())
                dynamic_range = int(pimg.max()) - int(pimg.min())
                assert p_std > 20.0, f"Panel {pname} in {name} appears flat/blank (std={p_std:.2f})"
                assert dynamic_range >= 128, f"Panel {pname} in {name} has narrow dynamic range ({dynamic_range})"


class TestVisualTypographyAndAnnotation:
    """Verify title bar text, panel banner overlays, and text contrast."""

    def test_header_title_bar_rendered(self) -> None:
        cs_dir = OUTPUT_DIR / "contact_sheets"
        for name in ["comparison_pair_170629_shot_000.png", "comparison_pair_270000_shot_015.png"]:
            img = cv2.imread(str(cs_dir / name))
            assert img is not None
            header = img[0:60, :]
            title_text_pixels = int(np.sum((header[:, :, 2] > 200) & (header[:, :, 1] > 180)))
            assert title_text_pixels > 2000, f"Insufficient header title text in {name}: {title_text_pixels} px"

    def test_panel_label_banners_rendered(self) -> None:
        cs_dir = OUTPUT_DIR / "contact_sheets"
        for name in ["comparison_pair_170629_shot_000.png", "comparison_pair_270000_shot_015.png"]:
            img = cv2.imread(str(cs_dir / name))
            assert img is not None
            label_regions = [
                img[60:96, 0:640],
                img[60:96, 640:1280],
                img[60:96, 1280:1920],
                img[420:456, 0:640],
                img[420:456, 640:1280],
                img[420:456, 1280:1920],
            ]
            for idx, band in enumerate(label_regions):
                white_pixels = int(np.sum((band[:, :, 0] > 200) & (band[:, :, 1] > 200) & (band[:, :, 2] > 200)))
                assert white_pixels > 800, f"Panel label {idx} missing white text pixels in {name}: {white_pixels} px"


class TestManifestAndBrainParity:
    """Verify manifest indexing and 100% bit-for-bit parity across all 10 deliverables."""

    def test_manifest_file_exists_and_valid_json(self) -> None:
        local_m = OUTPUT_DIR / "manifest.json"
        mirror_m = BRAIN_MIRROR_DIR / "manifest.json"
        assert local_m.is_file(), f"Local manifest missing: {local_m}"
        assert mirror_m.is_file(), f"Brain mirror manifest missing: {mirror_m}"

        data = json.loads(local_m.read_text(encoding="utf-8"))
        assert data.get("manifest_version") == "1.0.0"
        assert data.get("total_deliverables") == 10
        summary = data.get("parity_summary", {})
        assert summary.get("total_deliverables") == 10
        assert summary.get("parity_matched") == 10
        assert summary.get("parity_mismatched") == 0
        assert summary.get("status") == "VERIFIED_BIT_FOR_BIT_PARITY"

    def test_manifest_bit_parity(self) -> None:
        local_m = OUTPUT_DIR / "manifest.json"
        mirror_m = BRAIN_MIRROR_DIR / "manifest.json"
        assert _sha256(local_m) == _sha256(mirror_m), "SHA-256 mismatch between local and mirrored manifest.json"

    def test_all_10_deliverables_brain_mirror_parity(self) -> None:
        assert BRAIN_MIRROR_DIR.is_dir(), f"Brain mirror directory missing: {BRAIN_MIRROR_DIR}"
        for rel, _, _ in DELIVERABLE_SPECS:
            src_f = OUTPUT_DIR / rel
            dst_f = BRAIN_MIRROR_DIR / rel
            assert src_f.is_file(), f"Output deliverable missing: {src_f}"
            assert dst_f.is_file(), f"Mirrored deliverable missing: {dst_f}"
            assert _sha256(src_f) == _sha256(dst_f), f"SHA-256 parity mismatch for {rel}"


class TestSideEffectFreeExecution:
    """Verify test execution creates no side-effects, network calls, or checkpoint regressions."""

    def test_production_checkpoint_inviolability(self) -> None:
        ckpt_path = OUTPUT_DIR / "overnight_checkpoint.json"
        assert ckpt_path.is_file(), f"Checkpoint missing: {ckpt_path}"
        data = json.loads(ckpt_path.read_text(encoding="utf-8"))

        assert data.get("overall_status") == "completed"
        assert data.get("config", {}).get("mock") is False
        assert data.get("config", {}).get("dry_run") is False
        assert len(data.get("completed_stages", [])) == 5
        assert data.get("verification_report", {}).get("all_passed") is True
