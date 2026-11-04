"""
src/flow_cli.py
Unified CLI and Hybrid Multi-Scene Stitching Pipeline (M8) for Google Flow & ManimGX Studio.

Supports `--engine {flow,manimgx,hybrid}` and stitches heterogeneous scenes into a single
`.mp4` + `.srt` + `.vtt` + `contact_sheet.png`:
  - Scene 1: Deterministic `seek(t)` / `draw(t)` hardware block & exploded node view
    (`STM32H743` + `IS61LV6416` FMC bus + ESKD/PE telemetry) driven by `closed_form_spring`.
  - Scene 2: Mathematical derivation of transfer function H(z) and Z-plane pole-zero
    stability geometry via `StudioVoiceScene` (`manimgx`) with word-level `[span]` highlights.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import wave
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import imageio_ffmpeg
from manimgx.audio.sound import RATE
import numpy as np
from PIL import Image, ImageDraw, ImageFont

import asyncio
from flow_bridge import FlowClient
from flow_diff_tour import (
    build_diff_tour_from_git_range,
    render_diff_tour_to_mp4,
    validate_diff_tour,
    verify_tour_code_refs_against_git,
)
from flow_manimgx import (
    DspBiquadTransferScene,
    GeminiStudioVoice,
    build_contact_sheet,
    inspect_manimgx_scene,
    mix_studio_audio_with_ducking_and_sfx,
    render_manimgx_scene_to_mp4,
)
from flow_prompt_library import (
    closed_form_spring,
    get_flow_prompt_library,
    match_position_transition,
    plan_semantic_beats,
    validate_deterministic_seek_contract,
)


def _format_srt_timestamp(seconds: float) -> str:
    ms = max(0, int(round(seconds * 1000.0)))
    hh = ms // 3_600_000
    mm = (ms // 60_000) % 60
    ss = (ms // 1000) % 60
    rem = ms % 1000
    return f"{hh:02d}:{mm:02d}:{ss:02d},{rem:03d}"


def _format_vtt_timestamp(seconds: float) -> str:
    return _format_srt_timestamp(seconds).replace(",", ".")


def draw_hardware_exploded_frame_at_t(
    t_sec: float,
    duration_sec: float,
    *,
    width: int = 1280,
    height: int = 720,
    active_word_idx: int = -1,
    words: Sequence[str] = (),
) -> Image.Image:
    """
    Pure deterministic `draw(t)` renderer (`window.seek(t)` contract) for Scene 1:
    Exploded hardware block diagram of `STM32H743` + `IS61LV6416` SRAM over 16-bit FMC bus
    with `closed_form_spring` kinetics on dark zero-clutter canvas.
    """
    w, h = int(width), int(height)
    img = Image.new("RGB", (w, h), (11, 15, 25))
    draw = ImageDraw.Draw(img, "RGBA")

    # Subtle engineering blueprint grid
    grid_step = max(32, w // 20)
    for gx in range(0, w, grid_step):
        draw.line([(gx, 0), (gx, h)], fill=(30, 41, 59, 90), width=1)
    for gy in range(0, h, grid_step):
        draw.line([(0, gy), (w, gy)], fill=(30, 41, 59, 90), width=1)

    # Analytical critically damped spring entrances for each architectural block
    s_header = float(closed_form_spring(t_sec - 0.02, zeta=1.0, omega0=14.0))
    s_mcu = float(closed_form_spring(t_sec - 0.12, zeta=1.0, omega0=12.0))
    s_bus = float(closed_form_spring(t_sec - 0.35, zeta=1.0, omega0=12.0))
    s_sram = float(closed_form_spring(t_sec - 0.55, zeta=1.0, omega0=12.0))

    # Top header banner
    header_y = int(round(-40.0 * (1.0 - s_header) + 22.0))
    draw.rounded_rectangle(
        [int(w * 0.05), header_y, int(w * 0.95), header_y + int(h * 0.09)],
        radius=10,
        fill=(15, 23, 42, 235),
        outline=(56, 189, 248, 220),
        width=2,
    )
    draw.text(
        (int(w * 0.08), header_y + int(h * 0.025)),
        "SCENE 1: STM32H743 + IS61LV6416 EXPLODED HARDWARE NODE [window.seek(t)]",
        fill=(56, 189, 248, 255),
    )

    # Left Block: STM32H743VIT6 Cortex-M7 Node (slides & expands from left via spring, clamped inside frame REQ-005)
    mcu_start_box = (w * 0.025, h * 0.22, w * 0.325, h * 0.62)
    mcu_target_box = (w * 0.06, h * 0.20, w * 0.36, h * 0.64)
    mx0, my0, mx1, my1 = match_position_transition(
        mcu_start_box, mcu_target_box, t_sec - 0.08, zeta=1.0, omega0=12.0
    )
    mx0 = max(24.0, float(mx0))
    # Exploded 3D/2.5D shadow layer offset proportional to spring settle
    explode_off = int(round(14.0 * s_mcu))
    draw.rounded_rectangle(
        [int(mx0) + explode_off, int(my0) + explode_off, int(mx1) + explode_off, int(my1) + explode_off],
        radius=12,
        fill=(8, 47, 73, 180),
        outline=(14, 165, 233, 140),
        width=2,
    )
    draw.rounded_rectangle(
        [int(mx0), int(my0), int(mx1), int(my1)],
        radius=12,
        fill=(15, 23, 42, 245),
        outline=(56, 189, 248, 255),
        width=3,
    )
    draw.text((int(mx0) + 18, int(my0) + 16), "STM32H743VIT6 (480 MHz)", fill=(248, 250, 252, 255))
    draw.text((int(mx0) + 18, int(my0) + 44), "Cortex-M7 FPU + L1 Cache", fill=(148, 163, 184, 255))
    draw.rounded_rectangle(
        [int(mx0) + 16, int(my0) + int((my1 - my0) * 0.36), int(mx1) - 16, int(my0) + int((my1 - my0) * 0.62)],
        radius=8,
        fill=(30, 58, 138, 210),
        outline=(96, 165, 250, 255),
        width=2,
    )
    draw.text(
        (int(mx0) + 28, int(my0) + int((my1 - my0) * 0.45)),
        "DMA1 Ping-Pong Stream",
        fill=(224, 242, 254, 255),
    )
    draw.rounded_rectangle(
        [int(mx0) + 16, int(my0) + int((my1 - my0) * 0.68), int(mx1) - 16, int(my1) - 16],
        radius=8,
        fill=(6, 78, 59, 210),
        outline=(52, 211, 153, 255),
        width=2,
    )
    draw.text(
        (int(mx0) + 28, int(my0) + int((my1 - my0) * 0.76)),
        "FMC Bank1 Controller",
        fill=(209, 250, 229, 255),
    )

    # Right Block: IS61LV6416-10TL Async SRAM (slides from right via spring, clamped inside frame REQ-005)
    sram_start_box = (w * 0.675, h * 0.22, w * 0.965, h * 0.62)
    sram_target_box = (w * 0.64, h * 0.20, w * 0.94, h * 0.64)
    sx0, sy0, sx1, sy1 = match_position_transition(
        sram_start_box, sram_target_box, t_sec - 0.30, zeta=1.0, omega0=12.0
    )
    sram_off = int(round(14.0 * s_sram))
    sx1 = min(float(w - 24 - max(0, sram_off)), float(sx1))
    draw.rounded_rectangle(
        [int(sx0) + sram_off, int(sy0) + sram_off, int(sx1) + sram_off, int(sy1) + sram_off],
        radius=12,
        fill=(76, 29, 149, 175),
        outline=(168, 85, 247, 140),
        width=2,
    )
    draw.rounded_rectangle(
        [int(sx0), int(sy0), int(sx1), int(sy1)],
        radius=12,
        fill=(15, 23, 42, 245),
        outline=(192, 132, 252, 255),
        width=3,
    )
    draw.text((int(sx0) + 18, int(sy0) + 16), "IS61LV6416-10TL SRAM", fill=(248, 250, 252, 255))
    draw.text((int(sx0) + 18, int(sy0) + 44), "64K x 16-bit (10 ns Access)", fill=(216, 180, 254, 255))
    draw.rounded_rectangle(
        [int(sx0) + 16, int(sy0) + int((sy1 - sy0) * 0.36), int(sx1) - 16, int(sy0) + int((sy1 - sy0) * 0.62)],
        radius=8,
        fill=(88, 28, 135, 210),
        outline=(216, 180, 254, 255),
        width=2,
    )
    draw.text(
        (int(sx0) + 28, int(sy0) + int((sy1 - sy0) * 0.45)),
        "ADDSET = 1 | DATAST = 2",
        fill=(250, 245, 255, 255),
    )
    draw.rounded_rectangle(
        [int(sx0) + 16, int(sy0) + int((sy1 - sy0) * 0.68), int(sx1) - 16, int(sy1) - 16],
        radius=8,
        fill=(124, 45, 18, 210),
        outline=(251, 191, 36, 255),
        width=2,
    )
    draw.text(
        (int(sx0) + 28, int(sy0) + int((sy1 - sy0) * 0.76)),
        "Ring Buffer w_n[k-1, k-2]",
        fill=(254, 243, 199, 255),
    )

    # Center FMC 16-bit Parallel Bus lanes with animated packet pulse
    bus_x0 = int(mx1) + 10
    bus_x1 = max(bus_x0 + 20, int(sx0) - 10)
    bus_lanes = (
        ("A[15:0] ADDR", int(h * 0.30), (56, 189, 248, 255)),
        ("D[15:0] DATA", int(h * 0.42), (251, 191, 36, 255)),
        ("NE1 / NOE / NWE", int(h * 0.54), (52, 211, 153, 255)),
    )
    cur_bus_end = int(bus_x0 + (bus_x1 - bus_x0) * min(1.0, max(0.05, s_bus)))
    for label, ly, col in bus_lanes:
        draw.line([(bus_x0, ly), (cur_bus_end, ly)], fill=col, width=4)
        # Travelling wave packet along bus
        phase = (t_sec * 1.65) % 1.0
        px = int(bus_x0 + (cur_bus_end - bus_x0) * phase)
        draw.ellipse([px - 6, ly - 6, px + 6, ly + 6], fill=(255, 255, 255, 255), outline=col, width=2)
        draw.text((bus_x0 + 12, ly - 20), label, fill=col)

    # Kinetic Subtitle Bar with Amber-Gold (#FBBF24) Active Word Highlight
    if words:
        sub_y0 = int(h * 0.85)
        sub_y1 = int(h * 0.95)
        draw.rounded_rectangle(
            [int(w * 0.08), sub_y0, int(w * 0.92), sub_y1],
            radius=10,
            fill=(9, 13, 22, 240),
            outline=(71, 85, 105, 200),
            width=2,
        )
        # Render sliding window of words around active_word_idx
        win_size = 9
        idx_center = max(0, active_word_idx)
        start_w = max(0, min(len(words) - win_size, idx_center - win_size // 2))
        end_w = min(len(words), start_w + win_size)
        cursor_x = int(w * 0.12)
        text_y = sub_y0 + int((sub_y1 - sub_y0) * 0.32)
        for w_i in range(start_w, end_w):
            tok = words[w_i]
            is_active = w_i == active_word_idx
            color = (251, 191, 36, 255) if is_active else (226, 232, 240, 235)
            if is_active:
                pill_w = max(28, len(tok) * 9 + 12)
                draw.rounded_rectangle(
                    [cursor_x - 4, text_y - 4, cursor_x + pill_w - 6, text_y + 20],
                    radius=5,
                    fill=(120, 53, 15, 190),
                    outline=(251, 191, 36, 255),
                    width=1,
                )
            draw.text((cursor_x, text_y), tok, fill=color)
            cursor_x += max(34, (len(tok) + 1) * 9)

    return img


def render_hardware_spring_scene_to_mp4(
    output_path: Union[str, Path],
    *,
    width: int = 1280,
    height: int = 720,
    fps: int = 30,
    narration_script: str = (
        "Hardware node [STM32H743 microcontroller] drives [external SRAM IS61LV6416] "
        "over the [sixteen bit FMC bus] with critically damped spring timing."
    ),
    voice: Optional[GeminiStudioVoice] = None,
    enable_ducking_and_sfx: bool = True,
    duck_db: float = -12.0,
) -> Dict[str, Any]:
    """
    Render Scene 1 (`STM32H743` + `IS61LV6416` hardware block / exploded node diagram)
    using deterministic `seek(t)` frame stepping, `closed_form_spring` kinetics, and
    48 kHz female narration with `-12 dB` auto-ducking and SFX accents.
    """
    w = int(width) + (int(width) % 2)
    h = int(height) + (int(height) % 2)
    fps_int = max(1, int(fps))

    active_voice = voice or GeminiStudioVoice()
    clean_text = re.sub(r"\[([^\]]+)\]", r"\1", narration_script).strip()
    speech_obj = active_voice(clean_text)

    words_meta = list(speech_obj.words)
    word_tokens = [getattr(wd, "text", getattr(wd, "word", str(wd))) for wd in words_meta]
    speech_samples = speech_obj.samples
    duration_sec = max(1.5, round(float(len(speech_samples) / float(RATE)) + 0.25, 4))
    total_frames = max(1, int(round(duration_sec * fps_int)))

    # Identify span start timestamps from bracketed tokens in narration_script
    span_timestamps: List[float] = [0.15, round(duration_sec * 0.42, 3), round(duration_sec * 0.72, 3)]
    transition_timestamps: List[float] = [0.04]

    if enable_ducking_and_sfx:
        mix_info = mix_studio_audio_with_ducking_and_sfx(
            speech_samples,
            duration_sec=duration_sec,
            span_timestamps=span_timestamps,
            transition_timestamps=transition_timestamps,
            duck_db=duck_db,
            rate=RATE,
        )
        final_audio = mix_info["mixed_samples"]
        audio_telemetry = {k: v for k, v in mix_info.items() if k != "mixed_samples"}
    else:
        final_audio = speech_samples
        audio_telemetry = None

    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    out_p = Path(output_path).resolve()
    out_p.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_root = Path(tmp_dir)
        video_only_mp4 = tmp_root / "hw_video.mp4"
        wav_path = tmp_root / "hw_audio.wav"

        ffmpeg_cmd = [
            ffmpeg_exe,
            "-y",
            "-f",
            "rawvideo",
            "-vcodec",
            "rawvideo",
            "-s",
            f"{w}x{h}",
            "-pix_fmt",
            "rgb24",
            "-r",
            str(fps_int),
            "-i",
            "pipe:0",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-preset",
            "ultrafast",
            "-crf",
            "20",
            "-movflags",
            "+faststart",
            str(video_only_mp4),
        ]
        proc = subprocess.Popen(
            ffmpeg_cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        try:
            for f_idx in range(total_frames):
                t_sec = f_idx / float(fps_int)
                active_idx = -1
                for w_i, wd in enumerate(words_meta):
                    if wd.start <= t_sec <= wd.end + 0.06:
                        active_idx = w_i
                        break
                frame_img = draw_hardware_exploded_frame_at_t(
                    t_sec,
                    duration_sec,
                    width=w,
                    height=h,
                    active_word_idx=active_idx,
                    words=word_tokens,
                )
                if proc.stdin is not None:
                    proc.stdin.write(frame_img.tobytes())
        finally:
            if proc.stdin is not None:
                proc.stdin.close()
            _, stderr_bytes = proc.communicate(timeout=60)
            if proc.returncode != 0:
                err_msg = stderr_bytes.decode("utf-8", errors="replace")[-600:]
                raise RuntimeError(f"Hardware seek(t) FFmpeg pipe failed: {err_msg}")

        with wave.open(str(wav_path), "wb") as wf:
            wf.setnchannels(int(final_audio.shape[1]))
            wf.setsampwidth(2)
            wf.setframerate(RATE)
            pcm16 = (
                (np.clip(final_audio, -1.0, 1.0) * 32767.0)
                .round()
                .astype("<i2")
                .tobytes()
            )
            wf.writeframes(pcm16)

        mux_cmd = [
            ffmpeg_exe,
            "-y",
            "-i",
            str(video_only_mp4),
            "-i",
            str(wav_path),
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-ar",
            str(RATE),
            "-shortest",
            "-movflags",
            "+faststart",
            str(out_p),
        ]
        subprocess.run(
            mux_cmd,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            timeout=60,
        )

    srt_text = (
        f"1\n{_format_srt_timestamp(0.0)} --> {_format_srt_timestamp(duration_sec)}\n"
        f"{clean_text}\n\n"
    )
    vtt_text = (
        f"WEBVTT\n\n1\n{_format_vtt_timestamp(0.0)} --> {_format_vtt_timestamp(duration_sec)}\n"
        f"{clean_text}\n\n"
    )
    out_p.with_suffix(".srt").write_text(srt_text, encoding="utf-8")
    out_p.with_suffix(".vtt").write_text(vtt_text, encoding="utf-8")

    return {
        "ok": True,
        "scene_type": "seek_canvas_hardware_spring",
        "scene_name": "HardwareExplodedSpringScene",
        "output_path": str(out_p),
        "video_size_bytes": out_p.stat().st_size,
        "width": w,
        "height": h,
        "fps": fps_int,
        "frame_count": total_frames,
        "duration_sec": duration_sec,
        "has_audio": True,
        "audio_mix": audio_telemetry,
        "subtitles_srt": srt_text,
        "subtitles_vtt": vtt_text,
        "captions": [{"start": 0.0, "end": duration_sec, "text": clean_text}],
    }


def _extract_caption_entries(scene_res: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract normalized `{start, end, text}` caption entries from a scene result dict."""
    if scene_res.get("captions"):
        return [
            {
                "start": float(c["start"]),
                "end": float(c["end"]),
                "text": str(c["text"]).strip(),
            }
            for c in scene_res["captions"]
            if str(c.get("text", "")).strip()
        ]
    srt = (scene_res.get("subtitles_srt") or "").strip()
    entries: List[Dict[str, Any]] = []
    if srt:
        blocks = re.split(r"\n\s*\n", srt)
        for blk in blocks:
            lines = [ln.strip() for ln in blk.splitlines() if ln.strip()]
            if len(lines) >= 2:
                time_line = lines[1] if "-->" in lines[1] else lines[0]
                m_time = re.search(
                    r"(\d+):(\d+):(\d+)[,.](\d+)\s*-->\s*(\d+):(\d+):(\d+)[,.](\d+)",
                    time_line,
                )
                if m_time:
                    s_sec = (
                        int(m_time.group(1)) * 3600.0
                        + int(m_time.group(2)) * 60.0
                        + int(m_time.group(3))
                        + int(m_time.group(4)) / 1000.0
                    )
                    e_sec = (
                        int(m_time.group(5)) * 3600.0
                        + int(m_time.group(6)) * 60.0
                        + int(m_time.group(7))
                        + int(m_time.group(8)) / 1000.0
                    )
                    txt = " ".join(lines[2:] if "-->" in lines[1] else lines[1:])
                    entries.append({"start": s_sec, "end": e_sec, "text": txt})
    if not entries:
        dur = float(scene_res.get("duration_sec", 2.0))
        entries.append(
            {
                "start": 0.0,
                "end": dur,
                "text": str(scene_res.get("scene_name", "Scene")),
            }
        )
    return entries


def stitch_hybrid_scenes_to_mp4(
    scene_results: Sequence[Dict[str, Any]],
    output_mp4: Union[str, Path],
    *,
    contact_sheet_png: Optional[Union[str, Path]] = None,
    cols: int = 5,
    rows: int = 4,
) -> Dict[str, Any]:
    """
    Stitch multiple heterogeneous scene MP4 files (`seek(t)` hardware scene + `manimgx`
    mathematical scene) into a unified `.mp4` + `.srt` + `.vtt` + `contact_sheet.png`.
    """
    if not scene_results:
        raise ValueError("scene_results must contain at least one rendered scene")

    out_mp4 = Path(output_mp4).resolve()
    out_mp4.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()

    with tempfile.TemporaryDirectory() as tmp_dir:
        concat_list = Path(tmp_dir) / "concat_scenes.txt"
        lines: List[str] = []
        for res in scene_results:
            clip_p = Path(res["output_path"]).resolve()
            if not clip_p.is_file():
                raise FileNotFoundError(f"Scene MP4 missing: {clip_p}")
            escaped = str(clip_p).replace("'", "'\\''")
            lines.append(f"file '{escaped}'")
        concat_list.write_text("\n".join(lines) + "\n", encoding="utf-8")

        cmd = [
            ffmpeg_exe,
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_list),
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-preset",
            "ultrafast",
            "-crf",
            "20",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-ar",
            str(RATE),
            "-movflags",
            "+faststart",
            str(out_mp4),
        ]
        proc = subprocess.run(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            timeout=90,
        )
        if proc.returncode != 0 or not out_mp4.is_file():
            err_msg = proc.stderr.decode("utf-8", errors="replace")[-600:]
            raise RuntimeError(f"Hybrid scene stitching failed: {err_msg}")

    # Merge and offset SRT and WebVTT subtitles across all scenes
    merged_captions: List[Dict[str, Any]] = []
    time_offset = 0.0
    for res in scene_results:
        for cap in _extract_caption_entries(res):
            merged_captions.append(
                {
                    "start": round(time_offset + float(cap["start"]), 3),
                    "end": round(time_offset + float(cap["end"]), 3),
                    "text": cap["text"],
                }
            )
        time_offset += float(res.get("duration_sec", 0.0))

    srt_lines: List[str] = []
    vtt_lines: List[str] = ["WEBVTT", ""]
    for idx, cap in enumerate(merged_captions, 1):
        s_srt = _format_srt_timestamp(cap["start"])
        e_srt = _format_srt_timestamp(cap["end"])
        srt_lines.extend([str(idx), f"{s_srt} --> {e_srt}", cap["text"], ""])

        s_vtt = _format_vtt_timestamp(cap["start"])
        e_vtt = _format_vtt_timestamp(cap["end"])
        vtt_lines.extend([str(idx), f"{s_vtt} --> {e_vtt}", cap["text"], ""])

    srt_text = "\n".join(srt_lines)
    vtt_text = "\n".join(vtt_lines)
    srt_path = out_mp4.with_suffix(".srt")
    vtt_path = out_mp4.with_suffix(".vtt")
    srt_path.write_text(srt_text, encoding="utf-8")
    vtt_path.write_text(vtt_text, encoding="utf-8")

    sheet_path = (
        Path(contact_sheet_png).resolve()
        if contact_sheet_png is not None
        else (out_mp4.parent / "contact_sheet.png")
    )
    sheet_report = build_contact_sheet(out_mp4, sheet_path, cols=cols, rows=rows)

    return {
        "ok": bool(sheet_report["ok"]) and out_mp4.is_file(),
        "output_mp4": str(out_mp4),
        "output_srt": str(srt_path),
        "output_vtt": str(vtt_path),
        "contact_sheet_png": str(sheet_path),
        "contact_sheet": sheet_report,
        "scene_count": len(scene_results),
        "total_duration_sec": round(time_offset, 4),
        "video_size_bytes": out_mp4.stat().st_size,
        "subtitles_srt": srt_text,
        "subtitles_vtt": vtt_text,
        "captions": merged_captions,
    }


def render_hybrid_stm32_biquad_lesson(
    output_dir: Union[str, Path],
    *,
    width: int = 1280,
    height: int = 720,
    fps: int = 30,
    supersample: int = 1,
    language: str = "en",
    cols: int = 5,
    rows: int = 4,
) -> Dict[str, Any]:
    """
    End-to-end M8 Hybrid Lesson Pipeline:
      - Scene 1: Hardware block / exploded node diagram (`STM32H743` + `IS61LV6416`)
        with `closed_form_spring` kinetics and deterministic `seek(t)`.
      - Scene 2: Mathematical derivation of transfer function H(z) and Z-plane via
        `StudioVoiceScene` (`manimgx` `DspBiquadTransferScene`) with `[span]` sync.
      - Stitches both into unified `.mp4` + `.srt` + `.vtt` + `contact_sheet.png`.
    """
    out_root = Path(output_dir).resolve()
    out_root.mkdir(parents=True, exist_ok=True)

    voice = GeminiStudioVoice(language=language)

    scene1_mp4 = out_root / "scene_01_stm32h743_hardware_spring.mp4"
    scene1_res = render_hardware_spring_scene_to_mp4(
        scene1_mp4,
        width=width,
        height=height,
        fps=fps,
        voice=voice,
    )

    scene2_mp4 = out_root / "scene_02_manimgx_biquad_zplane.mp4"
    scene2_res = render_manimgx_scene_to_mp4(
        DspBiquadTransferScene,
        scene2_mp4,
        width=width,
        height=height,
        fps=fps,
        supersample=supersample,
        voice=voice,
        inspect_layout=True,
        enable_ducking_and_sfx=True,
    )

    final_mp4 = out_root / "hybrid_stm32_biquad_lesson.mp4"
    contact_png = out_root / "contact_sheet.png"
    stitched = stitch_hybrid_scenes_to_mp4(
        [scene1_res, scene2_res],
        final_mp4,
        contact_sheet_png=contact_png,
        cols=cols,
        rows=rows,
    )
    stitched["scenes"] = [scene1_res, scene2_res]
    return stitched


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Google Flow & ManimGX Hybrid Educational Video Studio CLI"
    )
    parser.add_argument(
        "--topic",
        default="STM32H743 + IS61LV6416 IIR Biquad Filter Pipeline",
        help="Educational lesson topic",
    )
    parser.add_argument("--scenes", type=int, default=2, help="Number of scenes")
    parser.add_argument("--language", default="en", help="Language code (en or ru)")
    parser.add_argument(
        "--engine",
        choices=("flow", "cloud-flow", "manimgx", "hybrid", "diff-tour"),
        default="manimgx",
        help="Rendering engine pipeline ('flow', 'cloud-flow', 'manimgx', 'hybrid', or 'diff-tour')",
    )
    parser.add_argument(
        "--cloud",
        action="store_true",
        help="Force 100%% cloud execution via Google Flow / Veo 3.1 (models/omni_1p2_pro_gemini_app)",
    )
    parser.add_argument(
        "--tour-json",
        default=None,
        help="Optional path to a diff-tour v1 JSON file for --engine diff-tour",
    )
    parser.add_argument(
        "--repo-path",
        default=None,
        help="Optional git repository path for diff-tour code verification",
    )
    parser.add_argument(
        "--output-dir",
        default="output/hybrid_stm32_biquad_lesson",
        help="Output directory for .mp4, .srt, .vtt, and contact_sheet.png",
    )
    parser.add_argument("--width", type=int, default=1280, help="Video width in pixels")
    parser.add_argument("--height", type=int, default=720, help="Video height in pixels")
    parser.add_argument("--fps", type=int, default=30, help="Frames per second")
    parser.add_argument("--cols", type=int, default=5, help="Contact sheet columns")
    parser.add_argument("--rows", type=int, default=4, help="Contact sheet rows")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run storyboard/layout inspection without full MP4 assembly",
    )
    parser.add_argument(
        "--assemble",
        action="store_true",
        help="Assemble final MP4, SRT, VTT, and contact_sheet.png",
    )
    parser.add_argument(
        "--compose-educational",
        action="store_true",
        help="Use FlowEducationalCompositor (720p HD + Studio TTS + animated plots + Cloud Flow Veo 3.1 plates)",
    )
    return parser


def run_cli(argv: Optional[Sequence[str]] = None) -> Dict[str, Any]:
    """Programmatic entrypoint for `src/flow_cli.py`."""
    parser = build_arg_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    out_dir = Path(args.output_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.engine == "diff-tour":
        repo_root = (
            Path(args.repo_path).resolve()
            if args.repo_path
            else Path(__file__).resolve().parent.parent
        )
        if args.tour_json:
            tour_doc = json.loads(Path(args.tour_json).read_text(encoding="utf-8"))
        else:
            tour_doc = build_diff_tour_from_git_range(repo_root, title=args.topic)
        tour_json_out = out_dir / "tour.json"
        tour_json_out.write_text(
            json.dumps(tour_doc, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        if args.dry_run and not args.assemble:
            val_rep = validate_diff_tour(tour_doc)
            git_rep = verify_tour_code_refs_against_git(tour_doc, repo_root)
            return {
                "engine": "diff-tour",
                "mode": "dry_run",
                "topic": args.topic,
                "tour_json": str(tour_json_out),
                "validation": val_rep,
                "git_verification": git_rep,
            }
        out_mp4 = out_dir / "diff_tour_walkthrough.mp4"
        res = render_diff_tour_to_mp4(
            tour_doc,
            out_mp4,
            repo_path=repo_root,
            width=args.width,
            height=args.height,
            fps=args.fps,
            language=args.language,
            cols=args.cols,
            rows=args.rows,
        )
        res["engine"] = "diff-tour"
        res["tour_json"] = str(tour_json_out)
        return res

    if args.engine in ("manimgx", "hybrid"):
        if args.dry_run and not args.assemble:
            diag = inspect_manimgx_scene(
                DspBiquadTransferScene,
                width=args.width,
                height=args.height,
                fps=args.fps,
                auto_heal=True,
            )
            return {
                "engine": args.engine,
                "mode": "dry_run",
                "topic": args.topic,
                "diagnostics": diag,
            }

        res = render_hybrid_stm32_biquad_lesson(
            out_dir,
            width=args.width,
            height=args.height,
            fps=args.fps,
            language=args.language,
            cols=args.cols,
            rows=args.rows,
        )
        res["engine"] = args.engine
        res["topic"] = args.topic
        return res

    # `flow` / `cloud-flow` storyboard + Veo 3.1 cloud bridge mode
    use_cloud = bool(args.cloud or args.engine == "cloud-flow")
    compose_edu = bool(getattr(args, "compose_educational", False) or args.engine == "cloud-flow")
    client = FlowClient()
    project = asyncio.run(
        client.generate_educational_storyboard(
            topic=args.topic,
            scene_count=args.scenes,
            language=args.language,
        )
    )
    payload: Dict[str, Any] = {
        "ok": True,
        "engine": args.engine,
        "use_cloud": use_cloud,
        "compose_educational": compose_edu,
        "topic": args.topic,
        "project_id": project.project_id,
        "scene_count": len(project.scenes),
    }
    if args.assemble:
        rendered = asyncio.run(
            client.render_educational_lesson(
                project,
                use_cloud=use_cloud,
                compose_educational=compose_edu,
            )
        )
        mp4_path = out_dir / "flow_lesson.mp4"
        if rendered.get("mp4_bytes"):
            mp4_path.write_bytes(rendered["mp4_bytes"])
        srt_path = out_dir / "flow_lesson.srt"
        vtt_path = out_dir / "flow_lesson.vtt"
        if project.subtitles_srt:
            srt_path.write_text(project.subtitles_srt, encoding="utf-8")
        if project.subtitles_vtt:
            vtt_path.write_text(project.subtitles_vtt, encoding="utf-8")
        payload["assembled_mp4"] = str(mp4_path)
        payload["video_size_bytes"] = int(rendered.get("video_size_bytes", 0))
        if compose_edu and mp4_path.is_file() and mp4_path.stat().st_size > 10_000:
            from flow_bridge import FlowEducationalCompositor

            sheet = FlowEducationalCompositor.build_contact_sheet(
                mp4_path=mp4_path,
                out_png=out_dir / "contact_sheet.png",
                scene_count=len(project.scenes),
            )
            if sheet:
                payload["contact_sheet"] = str(sheet)
    return payload


def main(argv: Optional[Sequence[str]] = None) -> int:
    result = run_cli(argv)
    summary = {
        k: v
        for k, v in result.items()
        if k not in ("mp4_bytes", "scenes")
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
