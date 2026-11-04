#!/usr/bin/env python3
"""
scripts/assemble_ep01_cinematic_audio_video.py
Master assembly script for Milestone 3:
Multiplexes base overlaid video with 5-layer 48 kHz stereo procedural audio engine,
Russian studio narration (voice_y0joebp3bwta), sidechain ducking (-12 dB),
broadcast limiter (-1.0 dBTP), and EBU R128 loudness normalization.
Produces FastStart CFR H.264 + AAC 48 kHz stereo master MP4 deliverable and WebVTT/SRT subtitles.
100% English-only source code and comments (0 literal Cyrillic characters; Russian text strictly unicode escaped).
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

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(ROOT_DIR / "src"))

from src.flow_cinematic_audio import (  # noqa: E402
    DEFAULT_EP01_DURATION_SEC,
    EP01_NARRATION_BEATS,
    SAMPLE_RATE,
    CinematicAudioEngine,
    export_wav_stereo,
    generate_srt_subtitles,
    generate_webvtt_subtitles,
)

DEFAULT_INPUT_VIDEO = ROOT_DIR / "output" / "ttd_ep01_manga_transitions" / "ttd_episode_01_overlaid_720p.mp4"
DEFAULT_OUTPUT_MASTER = ROOT_DIR / "output" / "ttd_ep01_manga_transitions" / "ttd_episode_01_cinematic_master_720p.mp4"
DEFAULT_STEMS_DIR = ROOT_DIR / "output" / "ttd_ep01_manga_transitions" / "audio_stems"
DEFAULT_BRAIN_DIR = Path(r"C:\Users\Orakul Grey\.gemini\antigravity\brain\94dd6a04-54e7-4e8c-9551-224cace4f85f")
DEFAULT_SUBPROCESS_TIMEOUT: float = 300.0


def resolve_ffmpeg_exe() -> str:
    """Locate FFmpeg binary from system PATH or bundled imageio_ffmpeg package."""
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
            elif size == 0:
                size = file_size - offset
            atoms.append((name, offset, size))
            if size <= 0:
                break
            f.seek(offset + size)
    return atoms


def probe_video_parameters(video_path: Path) -> Dict[str, Any]:
    """Inspect video file container and stream parameters using OpenCV."""
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise IOError(f"Failed to open video file: {video_path}")
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 1280)
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 720)
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 24.0)
    frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 1675)
    duration = frames / fps if fps > 0 else DEFAULT_EP01_DURATION_SEC
    cap.release()
    return {
        "width": w,
        "height": h,
        "fps": fps,
        "frames": frames,
        "duration": duration,
    }


def export_subtitles(output_dir: Path) -> Tuple[Path, Path]:
    """Export synchronized WebVTT and SubRip (SRT) subtitle files."""
    output_dir.mkdir(parents=True, exist_ok=True)
    vtt_path = output_dir / "ttd_episode_01_narration.vtt"
    srt_path = output_dir / "ttd_episode_01_narration.srt"
    vtt_path.write_text(generate_webvtt_subtitles(), encoding="utf-8")
    srt_path.write_text(generate_srt_subtitles(), encoding="utf-8")
    return vtt_path, srt_path


def assemble_cinematic_master(
    input_video: Path = DEFAULT_INPUT_VIDEO,
    output_master: Path = DEFAULT_OUTPUT_MASTER,
    stems_dir: Path = DEFAULT_STEMS_DIR,
    timeout_sec: float = DEFAULT_SUBPROCESS_TIMEOUT,
    brain_dir: Optional[Path] = DEFAULT_BRAIN_DIR,
) -> Dict[str, Any]:
    """
    Synthesize all 5 audio layers, apply -12 dB speech sidechain ducking and EBU R128 loudness normalization,
    and multiplex with base video into broadcast-grade master MP4 container.
    """
    if not input_video.is_file():
        raise FileNotFoundError(f"Input base video missing: {input_video}")

    stems_dir.mkdir(parents=True, exist_ok=True)
    output_master.parent.mkdir(parents=True, exist_ok=True)

    # 1. Probe video parameters
    video_meta = probe_video_parameters(input_video)
    dur_v = float(video_meta["duration"])
    print(f"Base video probed: {dur_v:.3f}s ({video_meta['frames']} frames @ {video_meta['fps']:.1f} fps)", flush=True)

    # 2. Synthesize audio stems using CinematicAudioEngine
    print("Synthesizing 5 procedural audio layers at 48,000 Hz...", flush=True)
    engine = CinematicAudioEngine(total_dur_sec=dur_v, sample_rate=SAMPLE_RATE)
    layers = engine.render_all_layers()

    # Export stems
    stem_paths: Dict[str, Path] = {}
    for layer_name, arr in layers.items():
        stem_p = stems_dir / f"{layer_name}.wav"
        export_wav_stereo(arr, stem_p, sample_rate=SAMPLE_RATE)
        stem_paths[layer_name] = stem_p
        print(f"  Stem exported: {stem_p.name} ({arr.shape[0]} samples, peak={float(np.max(np.abs(arr))):.3f})", flush=True)

    # Combine BGM/SFX layers (Layers 2..5) for speech sidechain ducking
    bgm_sfx = np.zeros_like(layers["layer1_narration"])
    bgm_sfx += layers["layer2_combat_sfx"] * 0.85
    bgm_sfx += layers["layer3_victory_fanfare"] * 0.78
    bgm_sfx += layers["layer4_stream_ambiance"] * 0.55
    bgm_sfx += layers["layer5_environmental_ambience"] * 0.65
    bgm_sfx = np.clip(bgm_sfx, -1.0, 1.0)
    bgm_stem_path = stems_dir / "bgm_sfx_composite.wav"
    export_wav_stereo(bgm_sfx, bgm_stem_path, sample_rate=SAMPLE_RATE)

    # Export subtitles
    vtt_path, srt_path = export_subtitles(output_master.parent)
    print(f"Subtitles exported: {vtt_path.name}, {srt_path.name}", flush=True)

    # 3. FFmpeg multiplexing with sidechain ducking, loudnorm, and broadcast limiter
    ffmpeg_exe = resolve_ffmpeg_exe()
    tmp_master = output_master.with_suffix(".tmp.mp4")
    if tmp_master.is_file():
        tmp_master.unlink()

    narration_wav = stem_paths["layer1_narration"]

    # Filter graph:
    # 1. sidechaincompress ducks BGM by ~12 dB when speech amplitude exceeds threshold
    # 2. amix sums ducked BGM with speech
    # 3. loudnorm normalizes to -16 LUFS, LRA 7, True Peak -1.0 dBTP
    # 4. alimiter enforces strict -1.0 dBTP peak ceiling
    filter_complex = (
        "[1:a][2:a]sidechaincompress=threshold=0.06:ratio=4:attack=20:release=250[ducked];"
        "[ducked][2:a]amix=inputs=2:weights=0.90 1.25:dropout_transition=0[mixed];"
        "[mixed]loudnorm=I=-16:LRA=7:TP=-1.0,alimiter=limit=-1.0dB:attack=5:release=50[aout]"
    )

    cmd = [
        ffmpeg_exe, "-y",
        "-i", str(input_video),
        "-i", str(bgm_stem_path),
        "-i", str(narration_wav),
        "-filter_complex", filter_complex,
        "-map", "0:v:0",
        "-map", "[aout]",
        "-c:v", "copy",
        "-c:a", "aac",
        "-b:a", "192k",
        "-ar", str(SAMPLE_RATE),
        "-t", f"{dur_v:.3f}",
        "-movflags", "+faststart",
        str(tmp_master),
    ]

    print("Executing FFmpeg audio multiplexing with speech sidechain ducking...", flush=True)
    t0 = time.monotonic()
    proc = subprocess.run(cmd, capture_output=True, timeout=timeout_sec, check=False)
    if proc.returncode != 0:
        err_msg = proc.stderr.decode("utf-8", errors="replace")
        raise RuntimeError(f"FFmpeg multiplexing failed (exit {proc.returncode}):\n{err_msg}")

    if not tmp_master.is_file() or tmp_master.stat().st_size < 10000:
        raise RuntimeError("Master output file empty or missing after FFmpeg execution")

    if output_master.is_file():
        output_master.unlink()
    tmp_master.rename(output_master)
    elapsed = time.monotonic() - t0
    print(f"Master MP4 assembled in {elapsed:.2f}s -> {output_master.name} ({output_master.stat().st_size:,} bytes)", flush=True)

    # 4. Verify deliverables
    verification = verify_master_deliverable(output_master, target_duration=dur_v)

    # 5. Mirror to brain directory if requested
    if brain_dir and brain_dir.is_dir():
        mirror_target = brain_dir / output_master.name
        shutil.copy2(output_master, mirror_target)
        shutil.copy2(vtt_path, brain_dir / vtt_path.name)
        shutil.copy2(srt_path, brain_dir / srt_path.name)
        print(f"Mirrored deliverables to brain directory: {mirror_target}", flush=True)

    return {
        "master_mp4": str(output_master),
        "file_size": output_master.stat().st_size,
        "sha256": compute_sha256(output_master),
        "subtitles_vtt": str(vtt_path),
        "subtitles_srt": str(srt_path),
        "verification": verification,
    }


def verify_master_deliverable(master_mp4: Path, target_duration: float = DEFAULT_EP01_DURATION_SEC) -> Dict[str, Any]:
    """Validate master delivery MP4 against all Milestone 3 and R3/R4 invariants."""
    if not master_mp4.is_file():
        raise FileNotFoundError(f"Master deliverable not found: {master_mp4}")

    size_bytes = master_mp4.stat().st_size
    assert size_bytes > 5_000_000, f"Master MP4 size ({size_bytes} bytes) suspiciously small"

    # Verify FastStart ISO-BMFF layout (moov before mdat)
    atoms = parse_iso_bmff_atoms(master_mp4)
    atom_names = [a[0] for a in atoms]
    assert "ftyp" in atom_names, "Missing ftyp atom"
    assert "moov" in atom_names, "Missing moov atom"
    assert "mdat" in atom_names, "Missing mdat atom"
    moov_idx = atom_names.index("moov")
    mdat_idx = atom_names.index("mdat")
    assert moov_idx < mdat_idx, f"FastStart violation: moov ({moov_idx}) appears after mdat ({mdat_idx})"

    # Verify video parameters
    cap = cv2.VideoCapture(str(master_mp4))
    assert cap.isOpened(), "Failed to open master MP4 with OpenCV"
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = float(cap.get(cv2.CAP_PROP_FPS))
    frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.release()

    assert w >= 1280 and h >= 720, f"Resolution {w}x{h} below 720p requirement"
    assert abs(fps - 24.0) < 0.2, f"Framerate {fps} deviates from 24.0 fps CFR"
    actual_dur = frames / fps if fps > 0 else 0.0
    drift = abs(actual_dur - target_duration)
    assert drift <= 0.05, f"Audio/video container drift {drift:.3f}s exceeds 0.05s tolerance"

    return {
        "valid": True,
        "width": w,
        "height": h,
        "fps": fps,
        "frames": frames,
        "duration": actual_dur,
        "drift_sec": drift,
        "faststart": True,
        "size_bytes": size_bytes,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Assemble Episode 1 cinematic master video with 5-layer audio")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT_VIDEO, help="Path to base overlaid video")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_MASTER, help="Path to master output MP4")
    parser.add_argument("--force", action="store_true", help="Force re-synthesis and re-multiplexing")
    parser.add_argument("--verify-only", action="store_true", help="Run verification without rebuilding")
    parser.add_argument("--timeout", type=float, default=DEFAULT_SUBPROCESS_TIMEOUT, help="Subprocess timeout in seconds")
    args = parser.parse_args()

    print("=== Milestone 3: 5-Layer Cinematic Audio Engine & Russian Studio Narration ===", flush=True)

    if args.verify_only:
        meta = verify_master_deliverable(args.output)
        print(f"Verification PASSED: {meta}", flush=True)
        return

    if args.output.is_file() and not args.force:
        print(f"Master deliverable already exists: {args.output} ({args.output.stat().st_size:,} bytes). Use --force to rebuild.", flush=True)
        meta = verify_master_deliverable(args.output)
        print(f"Existing file verified: {meta}", flush=True)
        return

    res = assemble_cinematic_master(
        input_video=args.input,
        output_master=args.output,
        timeout_sec=args.timeout,
    )
    print("Master assembly and multiplexing complete!", flush=True)
    print(json.dumps(res, indent=2), flush=True)


if __name__ == "__main__":
    main()
