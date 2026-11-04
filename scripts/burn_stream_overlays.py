#!/usr/bin/env python3
"""
scripts/burn_stream_overlays.py
High-performance FFmpeg in-memory overlay burning pipeline for Milestone 2.
Streams 1280x720 frames from silent base video, applies dynamic Pillow RGBA
manga stream chat and donation banner overlays, and writes directly into FFmpeg
stdin rawvideo pipe producing FastStart CFR H.264 MP4.
100% English-only source code and comments (0 literal Cyrillic characters).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

import cv2
import imageio_ffmpeg
import numpy as np
from PIL import Image

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(ROOT_DIR / "src"))

from src.flow_stream_overlays import (  # noqa: E402
    CANVAS_HEIGHT,
    CANVAS_WIDTH,
    CHAT_X_MAX,
    CHAT_X_MIN,
    CHAT_Y_MAX,
    CHAT_Y_MIN,
    DONATION_X_MAX,
    DONATION_X_MIN,
    DONATION_Y_MAX,
    DONATION_Y_MIN,
    MangaStreamOverlayEngine,
    verify_overlay_bounds,
)

DEFAULT_INPUT_MP4 = ROOT_DIR / "output" / "ttd_ep01_manga_transitions" / "ttd_episode_01_silent_720p.mp4"
DEFAULT_OUTPUT_MP4 = ROOT_DIR / "output" / "ttd_ep01_manga_transitions" / "ttd_episode_01_overlaid_720p.mp4"
DEFAULT_BRAIN_DIR = Path(r"C:\Users\Orakul Grey\.gemini\antigravity\brain\94dd6a04-54e7-4e8c-9551-224cace4f85f")
DEFAULT_SUBPROCESS_TIMEOUT: float = 300.0


def resolve_ffmpeg_exe() -> str:
    """Locate FFmpeg executable from system PATH or imageio_ffmpeg bundled binary."""
    return shutil.which("ffmpeg") or imageio_ffmpeg.get_ffmpeg_exe()


def compute_sha256(file_path: Path) -> str:
    """Compute hex SHA-256 digest of file."""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def parse_iso_bmff_atoms(file_path: Path) -> List[Tuple[str, int, int]]:
    """Parse top-level ISO-BMFF box types, byte offsets, and box sizes."""
    atoms: List[Tuple[str, int, int]] = []
    with open(file_path, "rb") as f:
        file_size = f.seek(0, 2)
        f.seek(0)
        while f.tell() < file_size:
            offset = f.tell()
            header = f.read(8)
            if len(header) < 8:
                break
            size = struct.unpack(">I", header[:4])[0]
            name = header[4:8].decode("latin1", errors="replace")
            if size == 1:
                ext_header = f.read(8)
                if len(ext_header) < 8:
                    break
                size = struct.unpack(">Q", ext_header)[0]
                payload_offset = offset + 16
            elif size == 0:
                size = file_size - offset
                payload_offset = offset + 8
            else:
                payload_offset = offset + 8
            atoms.append((name, offset, size))
            if size <= 0:
                break
            f.seek(offset + size)
    return atoms


def burn_overlays_to_mp4(
    input_mp4: Path,
    output_mp4: Path,
    crf: int = 15,
    preset: str = "fast",
    timeout_sec: float = 300.0,
) -> Path:
    """Stream base frames into Pillow overlay engine and write to FFmpeg stdin rawvideo pipe."""
    if not input_mp4.is_file():
        raise FileNotFoundError(f"Input video does not exist: {input_mp4}")

    cap = cv2.VideoCapture(str(input_mp4))
    if not cap.isOpened():
        raise IOError(f"Failed to open video source: {input_mp4}")

    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or CANVAS_WIDTH)
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or CANVAS_HEIGHT)
    fps = cap.get(cv2.CAP_PROP_FPS) or 24.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 1676)

    ffmpeg_exe = resolve_ffmpeg_exe()
    output_mp4.parent.mkdir(parents=True, exist_ok=True)
    tmp_out = output_mp4.with_suffix(".tmp.mp4")
    if tmp_out.is_file():
        tmp_out.unlink()

    cmd = [
        ffmpeg_exe, "-y",
        "-f", "rawvideo",
        "-vcodec", "rawvideo",
        "-s", f"{width}x{height}",
        "-pix_fmt", "rgb24",
        "-r", str(fps),
        "-i", "-",
        "-c:v", "libx264",
        "-preset", preset,
        "-crf", str(crf),
        "-pix_fmt", "yuv420p",
        "-an",
        "-movflags", "+faststart",
        str(tmp_out),
    ]

    print(f"Starting in-memory overlay burning: {input_mp4.name} ({total_frames} frames @ {fps:.1f} fps)...", flush=True)
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

    engine = MangaStreamOverlayEngine(width=width, height=height)
    frame_idx = 0
    t0 = time.monotonic()

    try:
        while True:
            ret, frame_bgr = cap.read()
            if not ret or frame_bgr is None:
                break

            t = frame_idx / fps
            # Convert BGR (cv2) to RGB (PIL)
            frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
            base_pil = Image.fromarray(frame_rgb)

            # Apply overlays if within active timeframe (before full void dissolve)
            alpha_scale = engine.get_alpha_scale(t)
            if alpha_scale > 0.0:
                overlay = engine.render_overlay_frame(t)
                base_rgba = base_pil.convert("RGBA")
                composited_rgba = Image.alpha_composite(base_rgba, overlay)
                out_arr = np.array(composited_rgba.convert("RGB"))
            else:
                out_arr = frame_rgb

            proc.stdin.write(out_arr.tobytes())
            frame_idx += 1

            if frame_idx % 240 == 0 or frame_idx == total_frames:
                pct = (frame_idx / total_frames) * 100.0 if total_frames > 0 else 0.0
                rate = frame_idx / max(0.001, (time.monotonic() - t0))
                print(f"  Frame {frame_idx:04d}/{total_frames} ({pct:5.1f}%) | Processing speed: {rate:5.1f} fps", flush=True)

    finally:
        cap.release()
        if proc.stdin:
            proc.stdin.close()

    stderr_output = proc.stderr.read().decode("utf-8", errors="replace") if proc.stderr else ""
    proc.wait(timeout=60.0)

    if proc.returncode != 0 or not tmp_out.is_file() or tmp_out.stat().st_size < 100_000:
        if tmp_out.is_file():
            tmp_out.unlink()
        raise RuntimeError(f"FFmpeg overlay burn failed (code {proc.returncode}):\n{stderr_output[-1000:]}")

    if output_mp4.is_file():
        output_mp4.unlink()
    tmp_out.rename(output_mp4)

    elapsed = time.monotonic() - t0
    fps_avg = frame_idx / max(0.001, elapsed)
    print(f"Successfully burned {frame_idx} overlaid frames in {elapsed:.2f}s ({fps_avg:.1f} FPS) -> {output_mp4.name}", flush=True)
    return output_mp4


def verify_overlaid_video(video_path: Path, timeout_sec: float = 300.0) -> Dict[str, Any]:
    """Verify ISO-BMFF container, FastStart atom ordering, and terminal void darkness."""
    if not video_path.is_file():
        raise FileNotFoundError(f"Video file does not exist: {video_path}")

    file_size = video_path.stat().st_size
    if file_size < 500_000:
        raise ValueError(f"Video file abnormally small: {file_size} bytes")

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise IOError(f"Could not open video with OpenCV: {video_path}")

    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 24.0
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = frame_count / fps if fps > 0 else 0.0

    if (w, h) != (CANVAS_WIDTH, CANVAS_HEIGHT):
        cap.release()
        raise AssertionError(f"Resolution mismatch: expected {CANVAS_WIDTH}x{CANVAS_HEIGHT}, got {w}x{h}")
    if abs(fps - 24.0) > 0.5:
        cap.release()
        raise AssertionError(f"Frame rate mismatch: expected 24.0 fps, got {fps:.2f}")

    # Inspect terminal frame for void darkness
    cap.set(cv2.CAP_PROP_POS_FRAMES, max(0, frame_count - 5))
    ret, term_bgr = cap.read()
    cap.release()

    atoms = parse_iso_bmff_atoms(video_path)
    atom_names = [a[0] for a in atoms]
    if "ftyp" not in atom_names or "moov" not in atom_names or "mdat" not in atom_names:
        raise AssertionError(f"Missing mandatory ISO-BMFF atoms in {atom_names}")
    moov_idx = atom_names.index("moov")
    mdat_idx = atom_names.index("mdat")
    if moov_idx > mdat_idx:
        raise AssertionError(f"FastStart violated: moov box at index {moov_idx} follows mdat at {mdat_idx}")

    terminal_luma: Optional[float] = None
    if ret and term_bgr is not None:
        bottom_third = term_bgr[int(h * 0.67):, :, :]
        luma = 0.114 * bottom_third[:, :, 0] + 0.587 * bottom_third[:, :, 1] + 0.299 * bottom_third[:, :, 2]
        terminal_luma = float(np.mean(luma))
        if terminal_luma > 25.0:
            raise AssertionError(f"Terminal void darkness violated: bottom luma {terminal_luma:.2f} > 25.0")

    return {
        "valid": True,
        "width": w,
        "height": h,
        "fps": fps,
        "frame_count": frame_count,
        "duration": duration,
        "file_size": file_size,
        "faststart": True,
        "atoms": atom_names,
        "terminal_void_luma": terminal_luma,
    }


def deliver_to_brain(artifacts: List[Path], brain_dir: Path) -> List[Path]:
    """Mirror generated deliverables into the root architecture brain directory."""
    brain_dir.mkdir(parents=True, exist_ok=True)
    delivered: List[Path] = []
    for art in artifacts:
        if art.is_file():
            dst = brain_dir / art.name
            shutil.copy2(art, dst)
            if not dst.is_file() or dst.stat().st_size != art.stat().st_size:
                raise IOError(f"Failed to copy artifact to brain: {dst}")
            delivered.append(dst)
            print(f"Delivered to Brain: {dst.name} ({dst.stat().st_size:,} bytes)", flush=True)
    return delivered


def main() -> int:
    parser = argparse.ArgumentParser(description="Burn Manga Stream Overlays onto Episode 1 Climax Video")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT_MP4, help="Input silent 720p base MP4")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_MP4, help="Output overlaid 720p MP4")
    parser.add_argument("--brain-dir", type=Path, default=DEFAULT_BRAIN_DIR, help="Path to brain mirror directory")
    parser.add_argument("--crf", type=int, default=15, help="H.264 CRF quality level (default: 15)")
    parser.add_argument("--preset", default="fast", help="FFmpeg x264 preset (default: fast)")
    parser.add_argument("--force", action="store_true", help="Force re-burning even if deliverable exists")
    parser.add_argument("--verify-only", action="store_true", help="Run verification checks on existing output")
    parser.add_argument("--timeout", type=float, default=DEFAULT_SUBPROCESS_TIMEOUT, help="Timeout in seconds")
    args = parser.parse_args()

    if args.verify_only:
        print(f"=== Verifying Overlaid Video: {args.output} ===", flush=True)
        info = verify_overlaid_video(args.output, timeout_sec=args.timeout)
        print(f"Verification: {info['width']}x{info['height']} @ {info['fps']}fps, "
              f"{info['frame_count']} frames ({info['duration']:.2f}s), "
              f"FastStart: {info['faststart']}, Terminal Void Luma: {info['terminal_void_luma']:.2f}", flush=True)
        return 0

    if not args.force and args.output.is_file() and args.output.stat().st_size > 1_000_000:
        print(f"Deliverable already exists: {args.output} ({args.output.stat().st_size:,} bytes). Use --force to re-burn.", flush=True)
        return 0

    print("=== Milestone 2: Programmatic Manga Stream Chat & Donation Overlay Burner ===", flush=True)
    out_p = burn_overlays_to_mp4(args.input, args.output, crf=args.crf, preset=args.preset, timeout_sec=args.timeout)
    info = verify_overlaid_video(out_p, timeout_sec=args.timeout)
    print(f"Verified Deliverable: {info['width']}x{info['height']} @ {info['fps']}fps, {info['frame_count']} frames, FastStart: True", flush=True)

    artifacts = [out_p]
    deliver_to_brain(artifacts, args.brain_dir)
    print("=== Overlay Burning & Delivery Complete (0 Errors) ===", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
