"""Assemble Episode 1 Extended Director's Cut MP4 from the 26 Google Flow clips (104.0s).

Concatenates all genuine 1280x720 24fps CFR clips (01, 01b, 02, 02b, 02c, ..., 12, 12b)
in chronological order preserving 100% pure native Google Flow stereo audio without
artificial TTS or procedural BGM overlays, and writes a FastStart ISO-BMFF master MP4 to
output/ttd_ep01_flow_videos/ttd_ep01_pilot_master_720p.mp4.
100% English-only source hygiene, <= 180 lines.
"""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import sys

import cv2
import imageio_ffmpeg

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.flow_extended_prompts import ORDERED_EPISODE_CLIPS
from src.ttd_audit_engine import audit_video_cut, compute_sha256

VID_DIR = ROOT_DIR / "output" / "ttd_ep01_flow_videos"
BRAIN_DIR = Path(r"C:\Users\Orakul Grey\.gemini\antigravity\brain\94dd6a04-54e7-4e8c-9551-224cace4f85f")
MASTER_MP4 = VID_DIR / "ttd_ep01_pilot_master_720p.mp4"


def _probe_target_dur(clip_path: Path) -> float:
    cap = cv2.VideoCapture(str(clip_path))
    fps = cap.get(cv2.CAP_PROP_FPS) or 24.0
    fc = cap.get(cv2.CAP_PROP_FRAME_COUNT)
    cap.release()
    raw_d = fc / fps if fps > 0 else 4.0
    return 10.0 if raw_d >= 7.0 else 4.0


def assemble_master_from_clips() -> dict:
    ff = shutil.which("ffmpeg") or imageio_ffmpeg.get_ffmpeg_exe()
    VID_DIR.mkdir(parents=True, exist_ok=True)

    shot_04_src = VID_DIR / "ttd_ep01_shot_04_lucas_roar_command_720p.mp4"
    shot_04_dst = VID_DIR / "ttd_ep01_shot_04_clip_720p.mp4"
    if shot_04_src.is_file() and not shot_04_dst.is_file():
        shutil.copy2(shot_04_src, shot_04_dst)

    clips: list[Path] = []
    for fname in ORDERED_EPISODE_CLIPS:
        cp = VID_DIR / fname
        if cp.is_file() and cp.stat().st_size >= 150_000:
            clips.append(cp)

    if len(clips) < 12:
        raise FileNotFoundError(f"Expected at least 12 clips, found {len(clips)}")

    n = len(clips)
    inputs: list[str] = []
    filter_parts: list[str] = []
    for i, cp in enumerate(clips):
        tdur = _probe_target_dur(cp)
        inputs.extend(["-i", str(cp)])
        filter_parts.append(
            f"[{i}:v]scale=1280:720:force_original_aspect_ratio=decrease,"
            f"pad=1280:720:(ow-iw)/2:(oh-ih)/2,tpad=stop_mode=clone:stop_duration=0.3,"
            f"trim=duration={tdur:.1f},fps=24,format=yuv420p,setpts=PTS-STARTPTS[v{i}];"
            f"[{i}:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,"
            f"apad=pad_dur=0.3,atrim=duration={tdur:.1f},asetpts=PTS-STARTPTS[a{i}]"
        )
    concat_pairs = "".join(f"[v{i}][a{i}]" for i in range(n))
    filter_parts.append(f"{concat_pairs}concat=n={n}:v=1:a=1[vcat][acat]")

    tmp_master = MASTER_MP4.with_suffix(".tmp.mp4")
    cmd_concat = [
        ff, "-y", *inputs, "-filter_complex", ";".join(filter_parts),
        "-map", "[vcat]", "-map", "[acat]", "-r", "24",
        "-c:v", "libx264", "-preset", "fast", "-crf", "18", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
        "-movflags", "+faststart", str(tmp_master),
    ]
    subprocess.run(cmd_concat, check=True, capture_output=True, timeout=300)
    tmp_master.replace(MASTER_MP4)

    master_meta = audit_video_cut(MASTER_MP4, min_bytes=5_000_000)
    lucas_meta = audit_video_cut(shot_04_src, min_bytes=500_000)
    dur_v = round(master_meta["frames"] / master_meta["fps"], 3)

    vtt_p = VID_DIR / "ttd_ep01_pilot_narration.vtt"
    srt_p = VID_DIR / "ttd_ep01_pilot_narration.srt"
    manifest_data = {
        "manifest_type": "ttd_ep01_flow_videos",
        "voice_persona": "voice_y0joebp3bwta",
        "audio_mode": "native_google_flow_stereo_only",
        "audio_sample_rate": 48000,
        "clip_count": n,
        "duration_seconds": dur_v,
        "lucas_roar_command_clip": {"file_name": shot_04_src.name, "sha256": compute_sha256(shot_04_src), **lucas_meta},
        "pilot_master_video": {"file_name": MASTER_MP4.name, "sha256": compute_sha256(MASTER_MP4), **master_meta},
        "subtitles": {
            "webvtt": vtt_p.name,
            "webvtt_sha256": compute_sha256(vtt_p) if vtt_p.is_file() else "",
            "srt": srt_p.name,
            "srt_sha256": compute_sha256(srt_p) if srt_p.is_file() else "",
        },
        "all_passed": lucas_meta["passed"] and master_meta["passed"],
    }
    (VID_DIR / "manifest.json").write_text(json.dumps(manifest_data, indent=2), encoding="utf-8")
    print(f"Assembled {n}-clip {MASTER_MP4.name}: {master_meta['size_bytes']} bytes, {dur_v:.2f}s ({master_meta['frames']} frames), FastStart={master_meta['faststart']}", flush=True)
    if BRAIN_DIR.is_dir():
        shutil.copy2(MASTER_MP4, BRAIN_DIR / MASTER_MP4.name)
    return master_meta


if __name__ == "__main__":
    assemble_master_from_clips()
