#!/usr/bin/env python3
"""
scripts/assemble_ep01_silent_video.py
Assembles 7 genuine Google Flow manga transition segments into a unified 720p silent MP4
with strictly zero audio tracks, generates an 8-card visual contact sheet, writes
provenance manifest, and delivers all artifacts to the root architecture brain directory.
Strictly zero Cyrillic characters.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import time
from typing import Any

import cv2
import imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFont

ROOT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_SEGMENTS_DIR = ROOT_DIR / "output" / "ttd_ep01_manga_transitions" / "segments"
DEFAULT_OUTPUT_DIR = ROOT_DIR / "output" / "ttd_ep01_manga_transitions"
DEFAULT_BRAIN_DIR = Path(r"C:\Users\Orakul Grey\.gemini\antigravity\brain\94dd6a04-54e7-4e8c-9551-224cace4f85f")
DEFAULT_SUBPROCESS_TIMEOUT: float = 300.0


def _format_stream(stream: Any) -> str:
    """Format stdout or stderr payload from subprocess exception or completed process."""
    if stream is None:
        return ""
    if isinstance(stream, bytes):
        return stream.decode("utf-8", errors="replace")
    return str(stream)


CARD_SPECS = [
    {
        "seg_id": 1,
        "filename": "segment_01.mp4",
        "frame_idx": 119,
        "title": "Scene 1: Game Clear Fanfare to Victory Celebration",
        "badge": "Segment 01 | 00:00.00 - 00:09.96 | Anchors: Frame 001 -> 002",
        "micro_shots": ["MS-01A", "MS-01B", "MS-01C"],
        "gaze_lock": "STREAMER FACE-LOCKED: Head yaw <= 5 deg, eyes locked on screen/webcam, specular catchlights",
        "style_domain": "Retro CRT UI -> Fortiche Arcane 2.5D",
        "is_climax": False,
    },
    {
        "seg_id": 2,
        "filename": "segment_02.mp4",
        "frame_idx": 120,
        "title": "Scene 2: Gamer Victory to Streamer Chat Reaction",
        "badge": "Segment 02 | 00:09.96 - 00:19.96 | Anchors: Frame 002 -> 004",
        "micro_shots": ["MS-02A", "MS-02B"],
        "gaze_lock": "STREAMER WEBCAM GAZE PINNED: Eyes dead-center into webcam, index finger point, head yaw 0 deg",
        "style_domain": "Fortiche Arcane 2.5D Animation",
        "is_climax": False,
    },
    {
        "seg_id": 3,
        "filename": "segment_03.mp4",
        "frame_idx": 119,
        "title": "Scene 3: Streamer Reaction to 'Save the Empire' Title Card",
        "badge": "Segment 03 | 00:19.96 - 00:29.92 | Anchors: Frame 004 -> 005",
        "micro_shots": ["MS-03A", "MS-03B"],
        "gaze_lock": "STREAMER POSITION LOCKED: Seated facing dual monitors, zero rear monitors, head yaw 0 deg",
        "style_domain": "Fortiche Arcane 2.5D Chiaroscuro",
        "is_climax": False,
    },
    {
        "seg_id": 4,
        "filename": "segment_04.mp4",
        "frame_idx": 120,
        "title": "Scene 4: Title Card to Tactical Defense Strategy Map",
        "badge": "Segment 04 | 00:29.92 - 00:39.92 | Anchors: Frame 005 -> 009",
        "micro_shots": ["MS-03A", "MS-04A"],
        "gaze_lock": "TACTICAL MAP & STREAM HUD: Hex defense grid, donation alert bloom, zero lateral drift",
        "style_domain": "Tactical War Map / Stream HUD Overlay",
        "is_climax": False,
    },
    {
        "seg_id": 5,
        "filename": "segment_05.mp4",
        "frame_idx": 119,
        "title": "Scene 5: Strategy Map to Streamer Broadcast Workstation",
        "badge": "Segment 05 | 00:39.92 - 00:49.88 | Anchors: Frame 009 -> 014",
        "micro_shots": ["MS-04B", "MS-04C", "MS-05A"],
        "gaze_lock": "STREAMER FACE-LOCKED (PITCH DOWN): Head bowed down 10 deg, eyes on keyboard and chat HUD",
        "style_domain": "Fortiche Arcane 2.5D Chiaroscuro",
        "is_climax": False,
    },
    {
        "seg_id": 6,
        "filename": "segment_06.mp4",
        "frame_idx": 119,
        "title": "Scene 6: Broadcast Workstation to Battlefield Ramparts",
        "badge": "Segment 06 | 00:49.88 - 00:59.84 | Anchors: Frame 014 -> 023",
        "micro_shots": ["MS-05C", "MS-06A", "MS-06B"],
        "gaze_lock": "LUCAS DUAL-STYLE TRANSITION: Domain 1 2D card -> Domain 2 Arcane cinematic 3D ramparts",
        "style_domain": "DOMAIN 1 (2D Card) -> DOMAIN 2 (Arcane 3D)",
        "is_climax": False,
    },
    {
        "seg_id": 7,
        "filename": "segment_07.mp4",
        "frame_idx": 108,
        "title": "Scene 7A: Rampart Ruins Dissolving into Darkness",
        "badge": "Segment 07 | 00:59.84 - 01:05.00 | Anchors: Frame 023 -> Void",
        "micro_shots": ["MS-07A", "MS-07B"],
        "gaze_lock": "LUCAS REAR ORIENTATION LOCK: Head bowed, back squarely to camera, cathedral hall fading",
        "style_domain": "DOMAIN 2: Arcane Cinematic 3D Dissolve",
        "is_climax": False,
    },
    {
        "seg_id": 8,
        "filename": "segment_07.mp4",
        "frame_idx": 238,
        "title": "Scene 7B Climax: Dark Void & Lucas Solitary Back",
        "badge": "Terminal Climax | 01:05.00 - 01:09.80 | Anchors: Void -> Frame 026",
        "micro_shots": ["MS-07C"],
        "gaze_lock": "LUCAS ICONIC LONELY BACK IN VOID: Motionless rear stance, pure pitch-black void (#000000)",
        "style_domain": "DOMAIN 2: Arcane 3D Solitary Back in Void",
        "is_climax": True,
    },
]


def resolve_ffmpeg_exe() -> str:
    """Resolve FFmpeg binary from PATH or imageio_ffmpeg bundled distribution."""
    return shutil.which("ffmpeg") or imageio_ffmpeg.get_ffmpeg_exe()


def compute_sha256(file_path: Path) -> str:
    """Compute hex SHA-256 digest of a file."""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def parse_iso_bmff_atoms(file_path: Path) -> list[tuple[str, int, int]]:
    """Parse top-level ISO-BMFF box types, byte offsets, and box sizes."""
    atoms: list[tuple[str, int, int]] = []
    with open(file_path, "rb") as f:
        file_size = f.seek(0, 2)
        f.seek(0)
        while f.tell() < file_size:
            offset = f.tell()
            header = f.read(8)
            if len(header) < 8:
                break
            size, typ_bytes = struct.unpack(">I4s", header)
            typ = typ_bytes.decode("latin1", errors="replace")
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


def discover_segments(segments_dir: Path) -> list[Path]:
    """Discover and validate all 7 sequential transition segments."""
    if not segments_dir.is_dir():
        raise FileNotFoundError(f"Segments directory not found: {segments_dir}")
    segs = sorted(segments_dir.glob("segment_*.mp4"))
    if len(segs) < 7:
        raise ValueError(f"Expected at least 7 segments in {segments_dir}, found {len(segs)}")
    return segs[:7]


def load_font(font_name: str, size: int) -> ImageFont.ImageFont:
    """Load specified Windows TrueType font with robust fallbacks."""
    candidates = [
        f"C:/Windows/Fonts/{font_name}.ttf",
        "C:/Windows/Fonts/segoeuib.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
        "C:/Windows/Fonts/arial.ttf",
    ]
    for c in candidates:
        try:
            return ImageFont.truetype(c, size)
        except Exception:
            continue
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def assemble_filter_complex(
    ffmpeg_exe: str,
    segments: list[Path],
    output_mp4: Path,
    fps: int = 24,
    crf: int = 18,
    preset: str = "fast",
    timeout_sec: float = DEFAULT_SUBPROCESS_TIMEOUT,
) -> Path:
    """Concatenate video segments using FFmpeg filter_complex with PTS normalization."""
    inputs: list[str] = []
    for s in segments:
        inputs.extend(["-i", str(s)])

    n = len(segments)
    filter_parts: list[str] = []
    for i in range(n):
        filter_parts.append(f"[{i}:v]setpts=PTS-STARTPTS[v{i}]")
    concat_inputs = "".join([f"[v{i}]" for i in range(n)])
    filter_parts.append(f"{concat_inputs}concat=n={n}:v=1:a=0[vcat]")
    filter_parts.append(f"[vcat]fps={fps},format=yuv420p[vout]")
    filter_graph = ";".join(filter_parts)

    tmp_out = output_mp4.with_suffix(".tmp.mp4")
    if tmp_out.is_file():
        tmp_out.unlink()

    cmd = [
        ffmpeg_exe, "-y",
        *inputs,
        "-filter_complex", filter_graph,
        "-map", "[vout]",
        "-c:v", "libx264",
        "-preset", preset,
        "-crf", str(crf),
        "-pix_fmt", "yuv420p",
        "-an",
        "-movflags", "+faststart",
        str(tmp_out),
    ]

    print(f"Executing filter_complex concatenation across {n} segments (timeout={timeout_sec}s)...", flush=True)
    try:
        res = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            errors="replace",
            check=False,
            timeout=timeout_sec,
        )
    except subprocess.TimeoutExpired as exc:
        if tmp_out.is_file():
            try:
                tmp_out.unlink()
            except OSError:
                pass
        stderr_tail = _format_stream(exc.stderr)[-1000:]
        raise RuntimeError(
            f"FFmpeg filter_complex assembly timed out after {timeout_sec}s:\n{stderr_tail}"
        ) from exc

    if res.returncode != 0 or not tmp_out.is_file() or tmp_out.stat().st_size < 10_000:
        if tmp_out.is_file():
            try:
                tmp_out.unlink()
            except OSError:
                pass
        raise RuntimeError(f"FFmpeg filter_complex assembly failed ({res.returncode}):\n{res.stderr[-1000:]}")

    if output_mp4.is_file():
        output_mp4.unlink()
    tmp_out.rename(output_mp4)
    return output_mp4


def assemble_concat_demuxer(
    ffmpeg_exe: str,
    segments: list[Path],
    output_mp4: Path,
    fps: int = 24,
    crf: int = 18,
    preset: str = "fast",
    timeout_sec: float = DEFAULT_SUBPROCESS_TIMEOUT,
) -> Path:
    """Concatenate video segments using FFmpeg concat demuxer as alternative strategy."""
    list_path = output_mp4.parent / "ep01_concat_list.txt"
    lines = [f"file '{s.resolve().as_posix()}'" for s in segments]
    list_path.write_text("\n".join(lines), encoding="utf-8")

    tmp_out = output_mp4.with_suffix(".tmp.mp4")
    if tmp_out.is_file():
        tmp_out.unlink()

    cmd = [
        ffmpeg_exe, "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(list_path),
        "-vf", f"fps={fps},format=yuv420p",
        "-c:v", "libx264",
        "-preset", preset,
        "-crf", str(crf),
        "-pix_fmt", "yuv420p",
        "-an",
        "-movflags", "+faststart",
        str(tmp_out),
    ]

    print(f"Executing concat demuxer assembly across {len(segments)} segments (timeout={timeout_sec}s)...", flush=True)
    try:
        res = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            errors="replace",
            check=False,
            timeout=timeout_sec,
        )
    except subprocess.TimeoutExpired as exc:
        if tmp_out.is_file():
            try:
                tmp_out.unlink()
            except OSError:
                pass
        stderr_tail = _format_stream(exc.stderr)[-1000:]
        raise RuntimeError(
            f"FFmpeg concat demuxer assembly timed out after {timeout_sec}s:\n{stderr_tail}"
        ) from exc
    finally:
        if list_path.is_file():
            try:
                list_path.unlink()
            except OSError:
                pass

    if res.returncode != 0 or not tmp_out.is_file() or tmp_out.stat().st_size < 10_000:
        if tmp_out.is_file():
            try:
                tmp_out.unlink()
            except OSError:
                pass
        raise RuntimeError(f"FFmpeg concat demuxer assembly failed ({res.returncode}):\n{res.stderr[-1000:]}")

    if output_mp4.is_file():
        output_mp4.unlink()
    tmp_out.rename(output_mp4)
    return output_mp4


def render_contact_sheet(segments_dir: Path, out_png: Path) -> Path:
    """Render high-resolution 2x4 visual contact sheet matching prototype geometry."""
    cols, rows = 2, 4
    tw, th = 660, 425
    margin = 20
    top_header_h = 85
    canvas_w = margin * 2 + cols * tw
    canvas_h = margin * 2 + top_header_h + rows * th

    sheet = Image.new("RGB", (canvas_w, canvas_h), (14, 16, 22))
    draw = ImageDraw.Draw(sheet)

    font_title = load_font("segoeuib", 24)
    font_sub = load_font("segoeui", 13)
    font_card_title = load_font("segoeuib", 14)
    font_badge = load_font("consola", 12)

    # Super header
    draw.text((margin + 6, margin + 4), "EPISODE 1: MANGA FLOW TRANSITIONS - VISUAL CONTACT SHEET", fill=(245, 205, 110), font=font_title)
    draw.text(
        (margin + 6, margin + 38),
        "Tyrant of the Tower Defense Game | 7-Segment Google Flow Omni Flash Transitions | 1280x720 24fps | Silent (-an) | 69.80s Master Arc",
        fill=(170, 185, 210),
        font=font_sub,
    )
    draw.line([(margin + 6, margin + 68), (canvas_w - margin - 6, margin + 68)], fill=(45, 52, 72), width=1)

    for i, spec in enumerate(CARD_SPECS):
        r, c = divmod(i, cols)
        x0 = margin + c * tw
        y0 = margin + top_header_h + r * th

        box_rect = [x0 + 8, y0 + 6, x0 + tw - 8, y0 + th - 6]
        border_col = (210, 170, 70) if spec["is_climax"] else (45, 52, 72)
        card_fill = (32, 24, 20) if spec["is_climax"] else (24, 28, 40)
        draw.rectangle(box_rect, fill=card_fill, outline=border_col, width=2 if spec["is_climax"] else 1)

        hdr_fill = (52, 38, 26) if spec["is_climax"] else (32, 38, 54)
        draw.rectangle([x0 + 8, y0 + 6, x0 + tw - 8, y0 + 44], fill=hdr_fill)

        title_col = (255, 215, 120) if spec["is_climax"] else (240, 240, 248)
        draw.text((x0 + 18, y0 + 10), spec["title"][:58], fill=title_col, font=font_card_title)
        draw.text((x0 + 18, y0 + 28), spec["badge"], fill=(120, 195, 255), font=font_badge)

        vid_p = segments_dir / spec["filename"]
        cap = cv2.VideoCapture(str(vid_p))
        cap.set(cv2.CAP_PROP_POS_FRAMES, spec["frame_idx"])
        ret, frame_bgr = cap.read()
        cap.release()

        if ret and frame_bgr is not None:
            frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
            im = Image.fromarray(frame_rgb)
            im = im.resize((640, 360), Image.Resampling.LANCZOS)
            thumb_x = x0 + (tw - 640) // 2
            thumb_y = y0 + 48
            sheet.paste(im, (thumb_x, thumb_y))
            if spec["is_climax"]:
                draw.rectangle(
                    [thumb_x - 1, thumb_y - 1, thumb_x + 640, thumb_y + 360],
                    outline=(240, 198, 105),
                    width=2,
                )

    out_png.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out_png, quality=94)
    return out_png


def verify_assembled_video(
    target_or_ffmpeg: Path | str | None = None,
    master_mp4: Path | str | None = None,
    expected_duration: float | None = None,
    *,
    master_video: Path | str | None = None,
    ffmpeg_exe: str | None = None,
    timeout_sec: float = DEFAULT_SUBPROCESS_TIMEOUT,
) -> dict[str, Any]:
    """Verify master video geometry, CFR frame rate, faststart atom order, and silent audio.

    Supports both legacy signature (ffmpeg_exe, master_mp4) and modern keyword/positional
    signature (master_video, expected_duration=total_dur).
    """
    if master_mp4 is not None:
        video_path = Path(master_mp4)
        active_ffmpeg = str(ffmpeg_exe or target_or_ffmpeg) if (ffmpeg_exe or target_or_ffmpeg) else resolve_ffmpeg_exe()
    else:
        vid = master_video or target_or_ffmpeg
        if vid is None:
            raise ValueError("Master video path must be provided")
        video_path = Path(vid)
        active_ffmpeg = str(ffmpeg_exe) if ffmpeg_exe else resolve_ffmpeg_exe()

    if not video_path.is_file():
        raise FileNotFoundError(f"Master video not found: {video_path}")

    file_size = video_path.stat().st_size
    if file_size < 10_000_000:
        raise ValueError(f"Master video unexpectedly small: {file_size} bytes")

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Failed to open video with OpenCV: {video_path}")

    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 24.0)
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = frame_count / fps if fps > 0 else 0.0
    cap.release()

    if (w, h) != (1280, 720):
        raise ValueError(f"Resolution mismatch: expected 1280x720, got {w}x{h}")
    if abs(fps - 24.0) > 0.1:
        raise ValueError(f"FPS mismatch: expected 24.0, got {fps}")

    if expected_duration is not None:
        if abs(duration - expected_duration) > 2.0:
            raise ValueError(
                f"Duration mismatch: expected {expected_duration:.2f}s (+/-2.0s), got {duration:.2f}s"
            )
    else:
        if duration < 68.0 or duration > 72.0:
            raise ValueError(f"Duration out of expected [68.0s, 72.0s] bounds: {duration:.2f}s")

    # Verify zero audio streams and codec via FFmpeg banner
    try:
        probe = subprocess.run(
            [active_ffmpeg, "-hide_banner", "-i", str(video_path)],
            capture_output=True,
            text=True,
            errors="replace",
            check=False,
            timeout=timeout_sec,
        )
        stderr = probe.stderr or ""
    except subprocess.TimeoutExpired as exc:
        stderr_tail = _format_stream(exc.stderr)[-1000:]
        raise RuntimeError(
            f"FFmpeg probe timed out after {timeout_sec}s on {video_path}:\n{stderr_tail}"
        ) from exc

    if "Audio:" in stderr:
        raise AssertionError("Audio stream detected! Assembled video must be strictly silent.")
    if "h264" not in stderr.lower() and "avc1" not in stderr.lower():
        raise AssertionError("Video codec is not H.264/AVC!")

    # Verify faststart atom order: moov atom must precede mdat atom
    atoms = parse_iso_bmff_atoms(video_path)
    atom_names = [a[0] for a in atoms]
    if "moov" not in atom_names or "mdat" not in atom_names:
        raise AssertionError(f"Expected both moov and mdat boxes in MP4, found: {atom_names}")
    moov_idx = atom_names.index("moov")
    mdat_idx = atom_names.index("mdat")
    if moov_idx > mdat_idx:
        raise AssertionError(f"Faststart violated: moov box at index {moov_idx} follows mdat at {mdat_idx}")

    return {
        "valid": True,
        "width": w,
        "height": h,
        "fps": fps,
        "frame_count": frame_count,
        "duration": duration,
        "file_size": file_size,
        "silent": True,
        "codec": "h264",
        "faststart": True,
        "atoms": atom_names,
    }


def deliver_to_brain(artifacts: list[Path], brain_dir: Path) -> list[Path]:
    """Mirror generated deliverables into the root architecture brain directory."""
    brain_dir.mkdir(parents=True, exist_ok=True)
    delivered: list[Path] = []
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
    parser = argparse.ArgumentParser(description="Assemble Episode 1 Manga Flow Transitions Silent Video")
    parser.add_argument("--segments-dir", type=Path, default=DEFAULT_SEGMENTS_DIR, help="Path to input segments directory")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help="Path to output deliverables directory")
    parser.add_argument("--brain-dir", type=Path, default=DEFAULT_BRAIN_DIR, help="Path to brain report directory")
    parser.add_argument("--strategy", choices=["filter_complex", "concat_demuxer"], default="filter_complex", help="Assembly strategy")
    parser.add_argument("--crf", type=int, default=15, help="H.264 CRF quality level")
    parser.add_argument("--preset", default="fast", help="FFmpeg x264 preset")
    parser.add_argument("--fps", type=int, default=24, help="Constant frame rate")
    parser.add_argument("--skip-contact-sheet", action="store_true", help="Skip generating contact sheet")
    parser.add_argument("--skip-brain-copy", action="store_true", help="Skip mirroring artifacts to brain directory")
    parser.add_argument("--verify-only", action="store_true", help="Run verification on existing deliverables without re-assembling")
    parser.add_argument("--timeout", type=float, default=DEFAULT_SUBPROCESS_TIMEOUT, help="Subprocess timeout in seconds (default: 300.0)")
    args = parser.parse_args()

    master_mp4 = args.output_dir / "ttd_episode_01_silent_720p.mp4"

    if args.verify_only:
        print("=== Episode 1 Manga Flow Transitions Verification Mode ===", flush=True)
        print(f"Target deliverable: {master_mp4}", flush=True)
        if not master_mp4.is_file():
            print(f"ERROR: Deliverable not found: {master_mp4}", file=sys.stderr, flush=True)
            return 1

        total_dur: float | None = None
        if args.segments_dir.is_dir():
            try:
                segs = discover_segments(args.segments_dir)
                durs = []
                for s in segs:
                    c = cv2.VideoCapture(str(s))
                    if c.isOpened():
                        f_cnt = c.get(cv2.CAP_PROP_FRAME_COUNT)
                        f_fps = c.get(cv2.CAP_PROP_FPS) or 24.0
                        durs.append(f_cnt / f_fps if f_fps > 0 else 0.0)
                        c.release()
                if durs:
                    total_dur = sum(durs)
                    print(f"Calculated expected duration across {len(durs)} segments: {total_dur:.2f}s", flush=True)
            except Exception as e:
                print(f"Note: Could not calculate duration from segments ({e}), using default bounds", flush=True)

        try:
            v_info = verify_assembled_video(master_mp4, expected_duration=total_dur, timeout_sec=args.timeout)
            print(f"Verification: {v_info['width']}x{v_info['height']} @ {v_info['fps']}fps, "
                  f"{v_info['frame_count']} frames ({v_info['duration']:.2f}s), "
                  f"Silent: {v_info['silent']}, Faststart: {v_info['faststart']}, Codec: {v_info['codec']}", flush=True)
            print("=== Verification Complete: Master Video Valid (0 Errors) ===", flush=True)
            return 0
        except Exception as exc:
            print(f"ERROR: Verification failed: {exc}", file=sys.stderr, flush=True)
            return 1

    print("=== Episode 1 Manga Flow Transitions Master Assembler ===", flush=True)
    segments = discover_segments(args.segments_dir)
    print(f"Discovered {len(segments)} segments in {args.segments_dir}:", flush=True)
    for s in segments:
        print(f"  * {s.name}: {s.stat().st_size:,} bytes", flush=True)

    ffmpeg_exe = resolve_ffmpeg_exe()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    t0 = time.monotonic()
    if args.strategy == "filter_complex":
        assemble_filter_complex(ffmpeg_exe, segments, master_mp4, fps=args.fps, crf=args.crf, preset=args.preset, timeout_sec=args.timeout)
    else:
        assemble_concat_demuxer(ffmpeg_exe, segments, master_mp4, fps=args.fps, crf=args.crf, preset=args.preset, timeout_sec=args.timeout)
    elapsed = time.monotonic() - t0
    print(f"Assembly completed in {elapsed:.2f}s -> {master_mp4}", flush=True)

    v_info = verify_assembled_video(ffmpeg_exe, master_mp4, timeout_sec=args.timeout)
    print(f"Verification: {v_info['width']}x{v_info['height']} @ {v_info['fps']}fps, "
          f"{v_info['frame_count']} frames ({v_info['duration']:.2f}s), Silent: {v_info['silent']}, Faststart: {v_info['faststart']}", flush=True)

    artifacts: list[Path] = [master_mp4]

    # Contact sheet
    contact_sheet_path = args.output_dir / "ep01_manga_transitions_contact_sheet.png"
    if not args.skip_contact_sheet:
        render_contact_sheet(args.segments_dir, contact_sheet_path)
        print(f"Generated visual contact sheet: {contact_sheet_path} ({contact_sheet_path.stat().st_size:,} bytes)", flush=True)
        artifacts.append(contact_sheet_path)

    # Provenance Manifest
    manifest_path = args.output_dir / "manifest.json"
    manifest_data = {
        "project": "Tyrant of the Tower Defense Game - Episode 1 Manga Flow Transitions",
        "master_video": master_mp4.name,
        "master_sha256": compute_sha256(master_mp4),
        "master_bytes": v_info["file_size"],
        "resolution": f"{v_info['width']}x{v_info['height']}",
        "fps": v_info["fps"],
        "frame_count": v_info["frame_count"],
        "duration_seconds": v_info["duration"],
        "audio_streams": 0,
        "silent": True,
        "faststart": True,
        "codec": v_info["codec"],
        "pix_fmt": "yuv420p",
        "crf": args.crf,
        "preset": args.preset,
        "delivery_timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "contact_sheet": {
            "filename": contact_sheet_path.name,
            "dimensions": "1360x1825",
            "sha256": compute_sha256(contact_sheet_path) if contact_sheet_path.is_file() else None,
            "bytes": contact_sheet_path.stat().st_size if contact_sheet_path.is_file() else 0,
            "card_count": len(CARD_SPECS),
            "terminal_climax": "Segment 7 Frame 238 Lucas Solitary Back in Dark Void",
        },
        "segments": [
            {
                "segment_index": spec["seg_id"],
                "filename": spec["filename"],
                "sha256": compute_sha256(args.segments_dir / spec["filename"]),
                "bytes": (args.segments_dir / spec["filename"]).stat().st_size,
                "title": spec["title"],
                "badge": spec["badge"],
                "micro_shots": spec.get("micro_shots", []),
                "gaze_lock": spec.get("gaze_lock", ""),
                "style_domain": spec.get("style_domain", ""),
            }
            for spec in CARD_SPECS[:7]
        ],
        "mirrored_brain_directory": str(args.brain_dir),
    }

    manifest_json_str = json.dumps(manifest_data, indent=2)
    manifest_path.write_text(manifest_json_str, encoding="utf-8")
    print(f"Written delivery manifest: {manifest_path}", flush=True)
    artifacts.append(manifest_path)

    # Also write alias for backward compatibility
    alias_manifest = args.output_dir / "ttd_episode_01_assembly_manifest.json"
    alias_manifest.write_text(manifest_json_str, encoding="utf-8")

    # Deliver to Brain
    if not args.skip_brain_copy:
        deliver_to_brain(artifacts, args.brain_dir)

    print("=== Assembly & Delivery Complete (0 Errors) ===", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
