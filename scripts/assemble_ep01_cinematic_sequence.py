#!/usr/bin/env python3
"""
scripts/assemble_ep01_cinematic_sequence.py
Master Milestone 1 Cinematic Video Sequence Assembler for Episode 1 Prologue Climax.
Strictly implements Pure Option 3 High-Energy Multi-Angle Combat, combining:
- Lucas in battered plate armor with shield and sword vs Gothic Throne Hall Boss
- CRT 'CLEAR! Congratulations!' fanfare and Streamer triumph
- Streamer remorse and transition into pitch-black terminal void
Strictly adheres to container specifications:
- 1280x720 progressive scan, 24.0 fps CFR, H.264 (yuv420p), CRF 18, preset fast
- FastStart atom layout (ftyp -> moov -> free -> mdat)
- Strictly zero audio streams (-an)
- Terminal void darkness invariant: bottom 33% mean luminance <= 25.0
100% English-only source code and comments (0 literal Cyrillic characters).
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
from typing import Any, Dict, List, Optional, Tuple

import cv2
import imageio_ffmpeg
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_SEGMENTS_DIR = ROOT_DIR / "output" / "ttd_ep01_manga_transitions" / "segments"
DEFAULT_OUTPUT_DIR = ROOT_DIR / "output" / "ttd_ep01_manga_transitions"
DEFAULT_BRAIN_DIR = Path(r"C:\Users\Orakul Grey\.gemini\antigravity\brain\94dd6a04-54e7-4e8c-9551-224cace4f85f")
DEFAULT_SUBPROCESS_TIMEOUT: float = 300.0

# 16-Micro-Shot Specification Matrix across 7 Macro-Segments (Pure Option 3)
PROLOGUE_COMBAT_SHOTS = [
    {
        "shot_id": "SHOT-01",
        "phase": "Battle: Wide Arena",
        "camera": "High-Angle Extreme Wide Shot (24mm, -10 deg)",
        "dur_sec": 2.5,
        "style_domain": "DOMAIN 2: Fortiche Arcane 3D",
        "subject": "Ruined Cathedral Throne Hall; colossal boss looming over ruined columns; Lucas centered",
    },
    {
        "shot_id": "SHOT-02",
        "phase": "Battle: Overhead Strategy",
        "camera": "Top-Down Isometric Tactical View (28mm, 15 deg pan)",
        "dur_sec": 2.0,
        "style_domain": "DOMAIN 1/2: Arcane Tactical UI",
        "subject": "Cyan defense hex tiles, aggressive red boss vector cones, Lucas maneuvering at choke point",
    },
    {
        "shot_id": "SHOT-03",
        "phase": "Battle: Close Combat Parries",
        "camera": "Dutch-Tilt Low-Angle Combat Close-Up (50mm handheld orbital)",
        "dur_sec": 2.2,
        "style_domain": "DOMAIN 2: Fortiche Arcane 3D",
        "subject": "Lucas in dark scarred plate, round buckler shield blocking boss tentacle/claw, sparks & sweat",
    },
    {
        "shot_id": "SHOT-04",
        "phase": "Battle: Decisive Strike Climax",
        "camera": "Dramatic Low-Angle Upward Tracking (+4% Z-glide)",
        "dur_sec": 2.8,
        "style_domain": "DOMAIN 2: Fortiche Arcane 3D",
        "subject": "Leaping upward diagonal golden broadsword arc bisecting the boss; blinding mana shockwave",
    },
    {
        "shot_id": "SHOT-05",
        "phase": "Victory: CRT CLEAR! Fanfare",
        "camera": "Direct Frontal Macro on CRT Glass (+2% optical push-in)",
        "dur_sec": 1.8,
        "style_domain": "Retro Game CRT UI",
        "subject": "Curved glass CRT monitor displaying glowing golden pixel runes CLEAR! CONGRATULATIONS!",
    },
    {
        "shot_id": "SHOT-06",
        "phase": "Streamer: Ecstatic Triumph",
        "camera": "Frontal Medium Shot at Eye Level (locked tripod)",
        "dur_sec": 2.2,
        "style_domain": "Arcane 2.5D Chiaroscuro",
        "subject": "STREAMER FACE-LOCKED: Ash leaps back in chair, arms thrown high in roar (Yaw <= 5 deg)",
    },
    {
        "shot_id": "SHOT-07",
        "phase": "Streamer: Shout into Mic",
        "camera": "Low-Angle Dynamic Close-Up (+3% forward Z-glide)",
        "dur_sec": 2.0,
        "style_domain": "Arcane 2.5D Chiaroscuro",
        "subject": "STREAMER FACE-LOCKED: Ash leans forward shouting into boom mic: 'I beat this game!'",
    },
    {
        "shot_id": "SHOT-08",
        "phase": "Streamer: Webcam Address",
        "camera": "Frontal Medium Close-Up at Eye Level (locked tripod)",
        "dur_sec": 2.0,
        "style_domain": "Arcane 2.5D Chiaroscuro",
        "subject": "STREAMER WEBCAM PINNED: Cocky smirk, right index finger pointing into webcam lens (Yaw 0 deg)",
    },
    {
        "shot_id": "SHOT-09",
        "phase": "Broadcast: Foxy 300K Alert",
        "camera": "Medium 3/4 Shot of Desk Setup (locked framing)",
        "dur_sec": 2.2,
        "style_domain": "Arcane 2.5D / Stream HUD",
        "subject": "Golden FOXY 300,000 KRW banner pops up; Ash clasps hands in grateful acknowledgment",
    },
    {
        "shot_id": "SHOT-10",
        "phase": "Broadcast: Reading Chat",
        "camera": "Extreme Close-Up on Eye-Line (locked tripod)",
        "dur_sec": 2.0,
        "style_domain": "Arcane 2.5D Chiaroscuro",
        "subject": "CHAT SEQUENCE: Smirk dissolves; dark pupils flick 10 deg upper-right reading priestess death",
    },
    {
        "shot_id": "SHOT-11",
        "phase": "Streamer: Somber Silence",
        "camera": "Low-Angle Desk Shot (+2% slow push-in)",
        "dur_sec": 2.2,
        "style_domain": "Arcane 2.5D Chiaroscuro",
        "subject": "STREAMER PITCH DOWN: Head bowed 10 deg, hands motionless on RGB keyboard; survivor's guilt",
    },
    {
        "shot_id": "SHOT-12",
        "phase": "Monitor: MVP Reward Card",
        "camera": "Direct Frontal Monitor Push-In (+4% optical scale)",
        "dur_sec": 2.5,
        "style_domain": "DOMAIN 1: 2D Cel-Shaded Anime UI",
        "subject": "Cel-shaded 2D anime bust portrait inside golden laurel wreath: STAGE MVP - Lucas [SSR]",
    },
    {
        "shot_id": "SHOT-13",
        "phase": "Reality: Rampart Carnage",
        "camera": "High-Angle Sweeping Crane (20 deg tilt)",
        "dur_sec": 2.8,
        "style_domain": "DOMAIN 2: Fortiche Arcane 3D",
        "subject": "Devastated stone ramparts strewn with fallen imperial soldiers, broken spears, black smoke",
    },
    {
        "shot_id": "SHOT-14",
        "phase": "Cathedral: Fallen Boss",
        "camera": "Low-Angle Floor Tracking Shot along marble",
        "dur_sec": 2.5,
        "style_domain": "DOMAIN 2: Fortiche Arcane 3D",
        "subject": "LUCAS REAR LOCK: Full rear view of Lucas standing motionless over lifeless boss on steps",
    },
    {
        "shot_id": "SHOT-15",
        "phase": "Transition: Environmental Decay",
        "camera": "Medium Rear Shot on Shoulders (+2% slow push-in)",
        "dur_sec": 2.5,
        "style_domain": "DOMAIN 2: Fortiche Arcane 3D",
        "subject": "LUCAS REAR LOCK: Cathedral columns, steps, and background walls dissolve into shadow",
    },
    {
        "shot_id": "SHOT-16",
        "phase": "Climax: Lucas in Dark Void",
        "camera": "Static Low-Angle Wide Rear Shot (locked tripod)",
        "dur_sec": 3.0,
        "style_domain": "DOMAIN 2: Fortiche Arcane 3D in Void",
        "subject": "LUCAS REAR IN VOID: Solitary back in scarred plate armor; bowed head; pure #000000 void",
    },
]


CARD_SPECS: List[Dict[str, Any]] = [
    {
        "seg_id": 1,
        "filename": "segment_01.mp4",
        "frame_idx": 119,
        "title": "Scene 1: Wide Arena Boss Clash (Lucas vs Colossal Boss)",
        "badge": "Segment 01 | 00:00.00 - 00:09.96 | Anchors: Wide Arena Battle",
        "micro_shots": ["SHOT-01", "SHOT-02"],
        "gaze_lock": "LUCAS COMBAT ACTION: Shield & sword combat, charging into arena, zero webcam streamer",
        "style_domain": "DOMAIN 2: Fortiche Arcane 3D",
        "is_climax": False,
    },
    {
        "seg_id": 2,
        "filename": "segment_02.mp4",
        "frame_idx": 120,
        "title": "Scene 2: Low-Angle Shield Block & Sparks (Round Shield Parry)",
        "badge": "Segment 02 | 00:09.96 - 00:19.96 | Anchors: Shield Sparks Parry",
        "micro_shots": ["SHOT-03"],
        "gaze_lock": "LUCAS SHIELD PARRY: Low-angle close-up, sparks across round shield, counter-slash",
        "style_domain": "DOMAIN 2: Fortiche Arcane 3D",
        "is_climax": False,
    },
    {
        "seg_id": 3,
        "filename": "segment_03.mp4",
        "frame_idx": 119,
        "title": "Scene 3: Decisive Final Strike to CLEAR! Fanfare",
        "badge": "Segment 03 | 00:19.96 - 00:29.92 | Anchors: Broadsword Cleave -> Clear",
        "micro_shots": ["SHOT-04", "SHOT-05"],
        "gaze_lock": "CRT GAME CLEAR FANFARE: Sweeping sword strike into glowing dual monitor victory screen",
        "style_domain": "Fortiche Arcane 2.5D -> Retro CRT UI",
        "is_climax": False,
    },
    {
        "seg_id": 4,
        "filename": "segment_04.mp4",
        "frame_idx": 120,
        "title": "Scene 4: Rectangular Desk Dual Monitors & Stream Setup",
        "badge": "Segment 04 | 00:29.92 - 00:39.92 | Anchors: RGB PC & Dual Monitors",
        "micro_shots": ["SHOT-09", "SHOT-11"],
        "gaze_lock": "DESK & STREAM CHAT SETUP: RGB mechanical keyboard, 3-ring PC tower, dual monitors, 0 face morphing",
        "style_domain": "Fortiche Arcane 2.5D Chiaroscuro",
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


def _format_stream(stream: Any) -> str:
    """Format stdout or stderr payload from subprocess exception or completed process."""
    if stream is None:
        return ""
    if isinstance(stream, bytes):
        return stream.decode("utf-8", errors="replace")
    return str(stream)


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


def discover_segments(segments_dir: Path, option3_dir: Optional[Path] = None) -> List[Path]:
    """Discover and validate all 7 sequential transition segments, prioritizing Option 3 boss scenes for 1..4."""
    opt3_dir = option3_dir or (ROOT_DIR / "output" / "ttd_ep01_option3_boss_battle" / "segments")
    segs: List[Path] = []
    segments_dir.mkdir(parents=True, exist_ok=True)
    for i in range(1, 8):
        name = f"segment_{i:02d}.mp4"
        if i <= 4 and opt3_dir.is_dir() and (opt3_dir / name).is_file():
            src_seg = opt3_dir / name
            dst_seg = segments_dir / name
            if segments_dir.resolve() != opt3_dir.resolve():
                try:
                    shutil.copy2(src_seg, dst_seg)
                except Exception:
                    pass
            segs.append(dst_seg if dst_seg.is_file() else src_seg)
        else:
            seg_p = segments_dir / name
            if not seg_p.is_file():
                if opt3_dir.is_dir() and (opt3_dir / name).is_file():
                    seg_p = opt3_dir / name
                else:
                    raise FileNotFoundError(f"Missing required segment {name} in {segments_dir} or {opt3_dir}")
            if i >= 5 and opt3_dir.is_dir() and not (opt3_dir / name).is_file():
                try:
                    shutil.copy2(seg_p, opt3_dir / name)
                except Exception:
                    pass
            segs.append(seg_p)
    if len(segs) < 7:
        raise ValueError(f"Expected 7 segments, found {len(segs)}")
    return segs


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
    segments: List[Path],
    output_mp4: Path,
    fps: int = 24,
    crf: int = 18,
    preset: str = "fast",
    timeout_sec: float = DEFAULT_SUBPROCESS_TIMEOUT,
) -> Path:
    """Concatenate video segments using FFmpeg filter_complex with PTS normalization."""
    inputs: List[str] = []
    for s in segments:
        inputs.extend(["-i", str(s)])

    n = len(segments)
    filter_parts: List[str] = []
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
    expected_duration: Optional[float] = None,
    *,
    master_video: Path | str | None = None,
    ffmpeg_exe: Optional[str] = None,
    timeout_sec: float = DEFAULT_SUBPROCESS_TIMEOUT,
) -> Dict[str, Any]:
    """Verify master video geometry, CFR frame rate, faststart atom order, silent audio, and terminal void darkness."""
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

    # Sample terminal frame for void darkness invariant
    cap.set(cv2.CAP_PROP_POS_FRAMES, max(0, frame_count - 1))
    ret, term_bgr = cap.read()
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
    if "yuv420p" not in stderr.lower():
        raise AssertionError("Pixel format must be yuv420p!")

    # Verify faststart atom order: moov atom must precede mdat atom
    atoms = parse_iso_bmff_atoms(video_path)
    atom_names = [a[0] for a in atoms]
    if "moov" not in atom_names or "mdat" not in atom_names:
        raise AssertionError(f"Expected both moov and mdat boxes in MP4, found: {atom_names}")
    moov_idx = atom_names.index("moov")
    mdat_idx = atom_names.index("mdat")
    if moov_idx > mdat_idx:
        raise AssertionError(f"Faststart violated: moov box at index {moov_idx} follows mdat at {mdat_idx}")

    # Terminal void darkness invariant check
    terminal_luma: Optional[float] = None
    if ret and term_bgr is not None:
        bottom_third = term_bgr[int(h * 0.67):, :, :]
        # ITU-R BT.601 for BGR: 0.114*B + 0.587*G + 0.299*R
        luma = 0.114 * bottom_third[:, :, 0] + 0.587 * bottom_third[:, :, 1] + 0.299 * bottom_third[:, :, 2]
        terminal_luma = float(np.mean(luma))
        if terminal_luma > 25.0:
            raise AssertionError(f"Terminal void darkness invariant violated: bottom third luma {terminal_luma:.2f} > 25.0")

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
        "pix_fmt": "yuv420p",
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


def build_manifest(
    master_mp4: Path,
    v_info: Dict[str, Any],
    contact_sheet_path: Path,
    segments_dir: Path,
    crf: int,
    preset: str,
    brain_dir: Path,
) -> Dict[str, Any]:
    """Construct canonical provenance and combat matrix manifest."""
    return {
        "project": "Tyrant of the Tower Defense Game - Episode 1 Manga Flow Transitions",
        "milestone": "Milestone 1: Cinematic Boss Fight Multi-Angle Video Assembly",
        "option": "Pure Option 3: High-Energy Multi-Angle Combat",
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
        "pix_fmt": v_info["pix_fmt"],
        "crf": crf,
        "preset": preset,
        "terminal_void_luma": v_info.get("terminal_void_luma"),
        "delivery_timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "contact_sheet": {
            "filename": contact_sheet_path.name,
            "dimensions": "1360x1825",
            "sha256": compute_sha256(contact_sheet_path) if contact_sheet_path.is_file() else None,
            "bytes": contact_sheet_path.stat().st_size if contact_sheet_path.is_file() else 0,
            "card_count": len(CARD_SPECS),
            "terminal_climax": "Segment 7 Frame 238 Lucas Solitary Back in Dark Void",
        },
        "combat_micro_shots": PROLOGUE_COMBAT_SHOTS,
        "segments": [
            {
                "segment_index": spec["seg_id"],
                "filename": spec["filename"],
                "sha256": compute_sha256(segments_dir / spec["filename"]),
                "bytes": (segments_dir / spec["filename"]).stat().st_size,
                "title": spec["title"],
                "badge": spec["badge"],
                "micro_shots": spec.get("micro_shots", []),
                "gaze_lock": spec.get("gaze_lock", ""),
                "style_domain": spec.get("style_domain", ""),
            }
            for spec in CARD_SPECS[:7]
        ],
        "mirrored_brain_directory": str(brain_dir),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Assemble Episode 1 Manga Flow Transitions Cinematic Sequence")
    parser.add_argument("--segments-dir", type=Path, default=DEFAULT_SEGMENTS_DIR, help="Path to input segments directory")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help="Path to output deliverables directory")
    parser.add_argument("--brain-dir", type=Path, default=DEFAULT_BRAIN_DIR, help="Path to brain report directory")
    parser.add_argument("--crf", type=int, default=18, help="H.264 CRF quality level (default: 18)")
    parser.add_argument("--preset", default="fast", help="FFmpeg x264 preset (default: fast)")
    parser.add_argument("--fps", type=int, default=24, help="Constant frame rate (default: 24)")
    parser.add_argument("--force", action="store_true", help="Force complete re-assembly even if master video exists")
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

        total_dur: Optional[float] = None
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
            if v_info.get("terminal_void_luma") is not None:
                print(f"Terminal Void Darkness Luma: {v_info['terminal_void_luma']:.2f} <= 25.0 (PASS)", flush=True)
            print("=== Verification Complete: Master Video Valid (0 Errors) ===", flush=True)
            return 0
        except Exception as exc:
            print(f"ERROR: Verification failed: {exc}", file=sys.stderr, flush=True)
            return 1

    print("=== Episode 1 Pure Option 3 Cinematic Master Assembler ===", flush=True)
    segments = discover_segments(args.segments_dir)
    print(f"Discovered {len(segments)} segments in {args.segments_dir}:", flush=True)
    for s in segments:
        print(f"  * {s.name}: {s.stat().st_size:,} bytes", flush=True)

    ffmpeg_exe = resolve_ffmpeg_exe()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    t0 = time.monotonic()
    assemble_filter_complex(ffmpeg_exe, segments, master_mp4, fps=args.fps, crf=args.crf, preset=args.preset, timeout_sec=args.timeout)
    elapsed = time.monotonic() - t0
    print(f"Assembly completed in {elapsed:.2f}s -> {master_mp4}", flush=True)

    v_info = verify_assembled_video(ffmpeg_exe, master_mp4, timeout_sec=args.timeout)
    print(f"Verification: {v_info['width']}x{v_info['height']} @ {v_info['fps']}fps, "
          f"{v_info['frame_count']} frames ({v_info['duration']:.2f}s), Silent: {v_info['silent']}, Faststart: {v_info['faststart']}", flush=True)
    if v_info.get("terminal_void_luma") is not None:
        print(f"Terminal Void Darkness Luma: {v_info['terminal_void_luma']:.2f} <= 25.0 (PASS)", flush=True)

    artifacts: List[Path] = [master_mp4]

    # Contact sheet
    contact_sheet_path = args.output_dir / "ep01_manga_transitions_contact_sheet.png"
    if not args.skip_contact_sheet:
        render_contact_sheet(args.segments_dir, contact_sheet_path)
        print(f"Generated visual contact sheet: {contact_sheet_path} ({contact_sheet_path.stat().st_size:,} bytes)", flush=True)
        artifacts.append(contact_sheet_path)

    # Provenance Manifests (both canonical manifest.json and ttd_episode_01_assembly_manifest.json)
    manifest_data = build_manifest(master_mp4, v_info, contact_sheet_path, args.segments_dir, args.crf, args.preset, args.brain_dir)
    manifest_json_str = json.dumps(manifest_data, indent=2)

    manifest_path = args.output_dir / "manifest.json"
    manifest_path.write_text(manifest_json_str, encoding="utf-8")
    print(f"Written delivery manifest: {manifest_path}", flush=True)
    artifacts.append(manifest_path)

    alias_manifest = args.output_dir / "ttd_episode_01_assembly_manifest.json"
    alias_manifest.write_text(manifest_json_str, encoding="utf-8")
    print(f"Written assembly manifest: {alias_manifest}", flush=True)
    artifacts.append(alias_manifest)

    # Deliver to Brain
    if not args.skip_brain_copy:
        deliver_to_brain(artifacts, args.brain_dir)

    print("=== Assembly & Delivery Complete (0 Errors) ===", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
