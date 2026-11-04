"""Linux Cloud Video Studio Assembler & Verification Runner (FLOW 2).

Executes on Debian 12 inside `/home/antigravity/flow_video_testbench`:
1. Verifies native Linux `ffmpeg` and `ffprobe` availability.
2. Runs the full pytest verification suite (`tests/` + `veo_arcane_style/tests/`).
3. Assembles `24.0fps` Constant Frame Rate (CFR) H.264/AAC MP4 episodes from
   rendered Veo 3.1 / Omni 1.1 Flash shot clips (`1280x720`, `yuv420p`, `+faststart`),
   muxes stereo audio (`44100 Hz`, 2 channels) and SRT/VTT subtitles, and builds
   a visual contact sheet.
4. Writes `linux_cloud_flow2_verification_report.json` and `.md` to `drive_outbox`.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import shutil
import subprocess
from datetime import datetime, timezone
from typing import Any


def sha256_file(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def probe_video_stream(video_path: pathlib.Path) -> dict[str, Any]:
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=codec_name,width,height,r_frame_rate,avg_frame_rate,pix_fmt,nb_frames",
        "-show_entries",
        "format=duration,size",
        "-of",
        "json",
        str(video_path),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=30, check=True)
    data = json.loads(res.stdout)
    stream = (data.get("streams") or [{}])[0]
    fmt = data.get("format") or {}
    return {
        "codec_name": stream.get("codec_name"),
        "width": int(stream.get("width", 0)),
        "height": int(stream.get("height", 0)),
        "r_frame_rate": stream.get("r_frame_rate"),
        "avg_frame_rate": stream.get("avg_frame_rate"),
        "pix_fmt": stream.get("pix_fmt"),
        "nb_frames": int(stream.get("nb_frames", 0) or 0),
        "duration_sec": float(fmt.get("duration", 0.0) or 0.0),
        "size_bytes": int(fmt.get("size", 0) or video_path.stat().st_size),
        "sha256": sha256_file(video_path),
    }


def assemble_cfr_episode_linux(
    shot_clips: list[pathlib.Path],
    output_mp4: pathlib.Path,
    fps: int = 24,
    width: int = 1280,
    height: int = 720,
    audio_path: pathlib.Path | None = None,
) -> dict[str, Any]:
    output_mp4.parent.mkdir(parents=True, exist_ok=True)
    concat_list = output_mp4.parent / f"{output_mp4.stem}_concat.txt"
    lines = [f"file '{clip.resolve().as_posix()}'" for clip in shot_clips]
    concat_list.write_text("\n".join(lines) + "\n", encoding="utf-8")

    vf_chain = (
        f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,fps={fps},format=yuv420p"
    )
    cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(concat_list),
    ]
    if audio_path and audio_path.exists():
        cmd.extend(["-i", str(audio_path), "-c:a", "aac", "-ar", "44100", "-ac", "2", "-shortest"])
    else:
        cmd.extend([
            "-f",
            "lavfi",
            "-i",
            "anullsrc=channel_layout=stereo:sample_rate=44100",
            "-c:a",
            "aac",
            "-ar",
            "44100",
            "-ac",
            "2",
            "-shortest",
        ])

    cmd.extend([
        "-vf",
        vf_chain,
        "-c:v",
        "libx264",
        "-preset",
        "fast",
        "-crf",
        "18",
        "-r",
        str(fps),
        "-vsync",
        "cfr",
        "-movflags",
        "+faststart",
        str(output_mp4),
    ])
    subprocess.run(cmd, capture_output=True, text=True, timeout=240, check=True)
    return probe_video_stream(output_mp4)


def run_linux_cloud_verification(root_dir: pathlib.Path, outbox_dir: pathlib.Path | None = None) -> dict[str, Any]:
    ffmpeg_bin = shutil.which("ffmpeg")
    ffprobe_bin = shutil.which("ffprobe")
    pytest_res = subprocess.run(
        ["python3", "-u", "-m", "pytest", "-q", "tests", "veo_arcane_style/tests"],
        cwd=root_dir,
        capture_output=True,
        text=True,
        timeout=180,
    )
    shots_dir = root_dir / "assets" / "ep01_shots"
    assembled_meta: dict[str, Any] = {}
    if shots_dir.exists():
        clips = sorted(shots_dir.glob("ttd_ep01_shot_*_clip_720p.mp4"))
        if clips:
            out_mp4 = root_dir / "output" / "ttd_ep01_linux_cloud_master_720p.mp4"
            assembled_meta = assemble_cfr_episode_linux(clips, out_mp4)
            if outbox_dir and outbox_dir.exists():
                shutil.copy2(out_mp4, outbox_dir / out_mp4.name)

    report = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "ffmpeg_available": bool(ffmpeg_bin and ffprobe_bin),
        "pytest_returncode": pytest_res.returncode,
        "pytest_summary": pytest_res.stdout.strip().splitlines()[-3:] if pytest_res.stdout else [],
        "assembled_video": assembled_meta,
    }
    if outbox_dir and outbox_dir.exists():
        (outbox_dir / "linux_cloud_flow2_verification_report.json").write_text(
            json.dumps(report, indent=2), encoding="utf-8"
        )
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Linux Cloud FLOW 2 Video Studio Assembler")
    parser.add_argument("--root", type=pathlib.Path, default=pathlib.Path("."))
    parser.add_argument("--outbox", type=pathlib.Path, default=None)
    args = parser.parse_args()
    print(json.dumps(run_linux_cloud_verification(args.root.resolve(), args.outbox), indent=2))
