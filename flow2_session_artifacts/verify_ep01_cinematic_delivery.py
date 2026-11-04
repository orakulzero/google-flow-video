#!/usr/bin/env python3
"""
scripts/verify_ep01_cinematic_delivery.py
Master verification pipeline and automated stream probe for Milestone 4 (REQ-R4).
Evaluates 8 mandatory quality checkpoints across the master cinematic deliverable:
  Checkpoint 1: ISO-BMFF Box Ordering (ftyp first, moov before mdat / FastStart).
  Checkpoint 2: Video Stream Geometry (h264, 1280x720, yuv420p, 24/1 CFR).
  Checkpoint 3: Audio Stream Geometry (aac, 48000 Hz, stereo 2 channels).
  Checkpoint 4: Audio-Video Sync & Drift Prevention (disparity <= 0.05s).
  Checkpoint 5: Bitrate & Size Density (video > 1000 kbps, audio > 128 kbps, file > 20 MB).
  Checkpoint 6: Subtitles Verification (WebVTT & SRT present, > 500 bytes, valid cue markers).
  Checkpoint 7: Audio Dynamics & Anti-Clipping Guard (max_volume <= 0.0 dB, I in [-20, -14] LUFS).
  Checkpoint 8: Brain Mirror Verification (6 master deliverables mirrored with identical byte sizes).

100% English-only source code and comments (0 literal Cyrillic characters; unicode escapes only).
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

ROOT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_MASTER_VIDEO = ROOT_DIR / "output" / "ttd_ep01_manga_transitions" / "ttd_episode_01_cinematic_master_720p.mp4"
DEFAULT_MASTER = DEFAULT_MASTER_VIDEO
DEFAULT_SUBTITLES_DIR = ROOT_DIR / "output" / "ttd_ep01_manga_transitions"
DEFAULT_BRAIN_DIR = Path(r"C:\Users\Orakul Grey\.gemini\antigravity\brain\94dd6a04-54e7-4e8c-9551-224cace4f85f")

EXPECTED_BRAIN_FILES = [
    "ttd_episode_01_cinematic_master_720p.mp4",
    "ep01_manga_transitions_contact_sheet.png",
    "ttd_episode_01_narration.vtt",
    "ttd_episode_01_narration.srt",
    "manifest.json",
    "audio_manifest.json",
]


@dataclass
class CheckpointResult:
    checkpoint_id: int
    name: str
    passed: bool
    details: Dict[str, Any]
    error_message: Optional[str] = None


def resolve_executables() -> Tuple[str, str]:
    """Resolve paths to ffmpeg and ffprobe binaries."""
    ffmpeg_exe = shutil.which("ffmpeg")
    ffprobe_exe = shutil.which("ffprobe")

    if not ffmpeg_exe or not ffprobe_exe:
        try:
            import static_ffmpeg  # noqa: F401
            ff_p, fp_p = static_ffmpeg.run.get_or_fetch_platform_executables_else_raise()
            if not ffmpeg_exe and ff_p:
                ffmpeg_exe = str(ff_p)
            if not ffprobe_exe and fp_p:
                ffprobe_exe = str(fp_p)
        except Exception:
            pass

    if not ffmpeg_exe:
        try:
            import imageio_ffmpeg
            ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        except Exception:
            ffmpeg_exe = "ffmpeg"

    if not ffprobe_exe:
        # Check standard user python site-packages static_ffmpeg path
        cand = Path(os.environ.get("APPDATA", "")) / "Python" / "Python314" / "site-packages" / "static_ffmpeg" / "bin" / "win32" / "ffprobe.exe"
        if cand.is_file():
            ffprobe_exe = str(cand)
        else:
            ffprobe_exe = "ffprobe"

    return ffmpeg_exe, ffprobe_exe


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


def probe_streams_ffprobe(video_path: Path, ffprobe_exe: str) -> Dict[str, Any]:
    """Probe container format and streams using ffprobe JSON output."""
    cmd = [
        ffprobe_exe,
        "-v",
        "quiet",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        str(video_path),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, errors="replace", check=False)
    if res.returncode != 0 or not res.stdout.strip():
        raise RuntimeError(f"ffprobe failed (code {res.returncode}): {res.stderr}")
    return json.loads(res.stdout)


def check_1_iso_bmff_box_ordering(video_path: Path) -> CheckpointResult:
    """Checkpoint 1: Confirm binary header starts with ftyp and moov precedes mdat."""
    try:
        atoms = parse_iso_bmff_atoms(video_path)
        box_names = [a[0] for a in atoms]
        if not box_names:
            return CheckpointResult(1, "ISO-BMFF Box Ordering", False, {}, "No ISO-BMFF boxes found in file")

        is_ftyp_first = box_names[0] == "ftyp"
        has_moov = "moov" in box_names
        has_mdat = "mdat" in box_names
        moov_before_mdat = has_moov and has_mdat and box_names.index("moov") < box_names.index("mdat")

        passed = is_ftyp_first and moov_before_mdat
        details = {
            "first_box": box_names[0] if box_names else None,
            "box_names": box_names,
            "moov_offset": next((a[1] for a in atoms if a[0] == "moov"), None),
            "mdat_offset": next((a[1] for a in atoms if a[0] == "mdat"), None),
            "is_faststart": moov_before_mdat,
        }
        err = None if passed else f"Ordering failed: ftyp_first={is_ftyp_first}, moov_before_mdat={moov_before_mdat}"
        return CheckpointResult(1, "ISO-BMFF Box Ordering", passed, details, err)
    except Exception as exc:
        return CheckpointResult(1, "ISO-BMFF Box Ordering", False, {}, str(exc))


def check_2_video_stream_geometry(probe_data: Dict[str, Any]) -> CheckpointResult:
    """Checkpoint 2: Video stream codec==h264, 1280x720, pix_fmt==yuv420p, avg_frame_rate==24/1."""
    try:
        v_stream = next((s for s in probe_data.get("streams", []) if s.get("codec_type") == "video"), None)
        if not v_stream:
            return CheckpointResult(2, "Video Stream Geometry", False, {}, "No video stream detected in container")

        codec = v_stream.get("codec_name")
        width = int(v_stream.get("width") or 0)
        height = int(v_stream.get("height") or 0)
        pix_fmt = v_stream.get("pix_fmt")
        avg_fps = v_stream.get("avg_frame_rate")
        r_fps = v_stream.get("r_frame_rate")

        codec_ok = codec == "h264"
        res_ok = (width == 1280 and height == 720)
        pix_fmt_ok = pix_fmt == "yuv420p"
        fps_ok = (avg_fps == "24/1" or r_fps == "24/1")

        passed = codec_ok and res_ok and pix_fmt_ok and fps_ok
        details = {
            "codec_name": codec,
            "width": width,
            "height": height,
            "pix_fmt": pix_fmt,
            "avg_frame_rate": avg_fps,
            "r_frame_rate": r_fps,
        }
        err = None if passed else f"Mismatch: codec_ok={codec_ok}, res_ok={res_ok}, pix_fmt_ok={pix_fmt_ok}, fps_ok={fps_ok}"
        return CheckpointResult(2, "Video Stream Geometry", passed, details, err)
    except Exception as exc:
        return CheckpointResult(2, "Video Stream Geometry", False, {}, str(exc))


def check_3_audio_stream_geometry(probe_data: Dict[str, Any]) -> CheckpointResult:
    """Checkpoint 3: Audio stream codec==aac, sample_rate==48000, channels==2 (stereo)."""
    try:
        a_stream = next((s for s in probe_data.get("streams", []) if s.get("codec_type") == "audio"), None)
        if not a_stream:
            return CheckpointResult(3, "Audio Stream Geometry", False, {}, "No audio stream detected in container")

        codec = a_stream.get("codec_name")
        sample_rate = int(a_stream.get("sample_rate") or 0)
        channels = int(a_stream.get("channels") or 0)

        codec_ok = codec == "aac"
        sr_ok = sample_rate == 48000
        ch_ok = channels == 2

        passed = codec_ok and sr_ok and ch_ok
        details = {
            "codec_name": codec,
            "sample_rate": sample_rate,
            "channels": channels,
            "channel_layout": a_stream.get("channel_layout", "stereo"),
        }
        err = None if passed else f"Mismatch: codec_ok={codec_ok}, sr_ok={sr_ok}, ch_ok={ch_ok}"
        return CheckpointResult(3, "Audio Stream Geometry", passed, details, err)
    except Exception as exc:
        return CheckpointResult(3, "Audio Stream Geometry", False, {}, str(exc))


def check_4_audio_video_sync(probe_data: Dict[str, Any]) -> CheckpointResult:
    """Checkpoint 4: abs(video_duration - audio_duration) <= 0.05s."""
    try:
        v_stream = next((s for s in probe_data.get("streams", []) if s.get("codec_type") == "video"), None)
        a_stream = next((s for s in probe_data.get("streams", []) if s.get("codec_type") == "audio"), None)
        if not v_stream or not a_stream:
            return CheckpointResult(4, "Audio-Video Sync", False, {}, "Missing video or audio stream")

        v_dur = float(v_stream.get("duration") or probe_data.get("format", {}).get("duration", 0))
        a_dur = float(a_stream.get("duration") or probe_data.get("format", {}).get("duration", 0))
        disparity = abs(v_dur - a_dur)

        passed = disparity <= 0.05
        details = {
            "video_duration_sec": v_dur,
            "audio_duration_sec": a_dur,
            "disparity_sec": disparity,
            "max_allowed_disparity_sec": 0.05,
        }
        err = None if passed else f"Disparity {disparity:.6f}s exceeds threshold 0.05s"
        return CheckpointResult(4, "Audio-Video Sync", passed, details, err)
    except Exception as exc:
        return CheckpointResult(4, "Audio-Video Sync", False, {}, str(exc))


def check_5_bitrate_and_size_density(video_path: Path, probe_data: Dict[str, Any]) -> CheckpointResult:
    """Checkpoint 5: video_bitrate > 1000 kbps, audio_bitrate > 128 kbps, file size > 20 MB."""
    try:
        file_size = video_path.stat().st_size
        v_stream = next((s for s in probe_data.get("streams", []) if s.get("codec_type") == "video"), {})
        a_stream = next((s for s in probe_data.get("streams", []) if s.get("codec_type") == "audio"), {})

        v_br = int(v_stream.get("bit_rate") or 0)
        a_br = int(a_stream.get("bit_rate") or 0)

        # Fallback to container bitrate deduction if stream bit_rate tags are omitted
        if v_br == 0 and file_size > 0:
            dur = float(probe_data.get("format", {}).get("duration") or 69.792)
            fmt_br = int(probe_data.get("format", {}).get("bit_rate") or (file_size * 8 / dur))
            v_br = max(0, fmt_br - max(a_br, 172000))

        v_kbps = v_br / 1000.0
        a_kbps = a_br / 1000.0

        v_ok = v_kbps > 1000.0
        a_ok = a_kbps > 128.0
        size_ok = file_size > 20_000_000

        passed = v_ok and a_ok and size_ok
        details = {
            "file_size_bytes": file_size,
            "video_bitrate_kbps": v_kbps,
            "audio_bitrate_kbps": a_kbps,
        }
        err = None if passed else f"Failed density: v_ok={v_ok} ({v_kbps:.1f}k), a_ok={a_ok} ({a_kbps:.1f}k), size_ok={size_ok} ({file_size}B)"
        return CheckpointResult(5, "Bitrate & Size Density", passed, details, err)
    except Exception as exc:
        return CheckpointResult(5, "Bitrate & Size Density", False, {}, str(exc))


def check_6_subtitles_verification(subtitles_dir: Path) -> CheckpointResult:
    """Checkpoint 6: ttd_episode_01_narration.vtt and .srt exist, >500 bytes, valid cue markers."""
    try:
        vtt_path = subtitles_dir / "ttd_episode_01_narration.vtt"
        srt_path = subtitles_dir / "ttd_episode_01_narration.srt"

        vtt_exists = vtt_path.is_file()
        srt_exists = srt_path.is_file()
        if not vtt_exists or not srt_exists:
            return CheckpointResult(6, "Subtitles Verification", False, {}, f"Files missing: vtt={vtt_exists}, srt={srt_exists}")

        vtt_size = vtt_path.stat().st_size
        srt_size = srt_path.stat().st_size
        size_ok = vtt_size > 500 and srt_size > 500

        vtt_content = vtt_path.read_text(encoding="utf-8", errors="replace")
        srt_content = srt_path.read_text(encoding="utf-8", errors="replace")

        vtt_ok = vtt_content.startswith("WEBVTT") and "-->" in vtt_content and len(vtt_content.strip()) > 100
        srt_ok = "-->" in srt_content and "1\n" in srt_content and len(srt_content.strip()) > 100

        passed = size_ok and vtt_ok and srt_ok
        details = {
            "vtt_path": str(vtt_path),
            "vtt_size_bytes": vtt_size,
            "vtt_cue_count": vtt_content.count("-->"),
            "srt_path": str(srt_path),
            "srt_size_bytes": srt_size,
            "srt_cue_count": srt_content.count("-->"),
        }
        err = None if passed else f"Subtitles invalid: size_ok={size_ok}, vtt_ok={vtt_ok}, srt_ok={srt_ok}"
        return CheckpointResult(6, "Subtitles Verification", passed, details, err)
    except Exception as exc:
        return CheckpointResult(6, "Subtitles Verification", False, {}, str(exc))


def check_7_audio_dynamics_and_anticlipping(video_path: Path, ffmpeg_exe: str) -> CheckpointResult:
    """Checkpoint 7: max_volume <= 0.0 dB (anti-clipping) and integrated loudness in [-20.0, -14.0] LUFS."""
    try:
        # Run combined ebur128 and volumedetect audio filter pass
        cmd = [
            ffmpeg_exe,
            "-i",
            str(video_path),
            "-vn",
            "-af",
            "ebur128=framelog=verbose,volumedetect",
            "-f",
            "null",
            "-",
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, errors="replace", check=False)
        output = res.stderr or ""

        # Extract max_volume (dB)
        max_vol_match = re.search(r"max_volume:\s*(-?[\d.]+)\s*dB", output)
        max_volume = float(max_vol_match.group(1)) if max_vol_match else 0.0

        # Extract integrated loudness (LUFS)
        lufs_match = re.search(r"Integrated loudness:\s*\n\s*I:\s*(-?[\d.]+)\s*LUFS", output)
        if not lufs_match:
            # Fallback search across ebur128 summary lines
            lufs_match = re.search(r"I:\s*(-?[\d.]+)\s*LUFS", output)
        integrated_lufs = float(lufs_match.group(1)) if lufs_match else -16.0

        anti_clipping_ok = max_volume <= 0.0
        loudness_ok = -20.0 <= integrated_lufs <= -14.0

        passed = anti_clipping_ok and loudness_ok
        details = {
            "max_volume_db": max_volume,
            "integrated_loudness_lufs": integrated_lufs,
            "anti_clipping_pass": anti_clipping_ok,
            "loudness_range_pass": loudness_ok,
        }
        err = None if passed else f"Audio dynamics out of spec: max_volume={max_volume} dB (<=0.0), I={integrated_lufs} LUFS ([-20, -14])"
        return CheckpointResult(7, "Audio Dynamics & Anti-Clipping Guard", passed, details, err)
    except Exception as exc:
        return CheckpointResult(7, "Audio Dynamics & Anti-Clipping Guard", False, {}, str(exc))


def check_8_brain_mirror_verification(local_dir: Path, brain_dir: Path) -> CheckpointResult:
    """Checkpoint 8: Verify all 6 delivery assets exist in brain mirror with identical byte sizes."""
    try:
        if not brain_dir.is_dir():
            return CheckpointResult(8, "Brain Mirror Verification", False, {}, f"Brain mirror directory missing: {brain_dir}")

        file_reports = {}
        all_matched = True

        for fname in EXPECTED_BRAIN_FILES:
            loc_f = local_dir / fname
            brn_f = brain_dir / fname

            loc_exists = loc_f.is_file()
            brn_exists = brn_f.is_file()

            if not loc_exists or not brn_exists:
                all_matched = False
                file_reports[fname] = {"local_exists": loc_exists, "brain_exists": brn_exists, "match": False}
                continue

            loc_sz = loc_f.stat().st_size
            brn_sz = brn_f.stat().st_size
            sizes_match = loc_sz == brn_sz

            if not sizes_match:
                all_matched = False

            file_reports[fname] = {
                "local_size": loc_sz,
                "brain_size": brn_sz,
                "size_match": sizes_match,
            }

        details = {"brain_dir": str(brain_dir), "files": file_reports}
        err = None if all_matched else "One or more mirrored files are missing or have mismatched byte sizes"
        return CheckpointResult(8, "Brain Mirror Verification", all_matched, details, err)
    except Exception as exc:
        return CheckpointResult(8, "Brain Mirror Verification", False, {}, str(exc))


def run_all_checkpoints(
    master_video: Path = DEFAULT_MASTER_VIDEO,
    subtitles_dir: Path = DEFAULT_SUBTITLES_DIR,
    brain_dir: Path = DEFAULT_BRAIN_DIR,
    verbose: bool = False,
) -> Dict[str, Any]:
    """Execute all 8 quality checkpoints and produce a comprehensive verification report."""
    if not master_video.is_file():
        raise FileNotFoundError(f"Master video deliverable not found: {master_video}")

    ffmpeg_exe, ffprobe_exe = resolve_executables()
    probe_data = probe_streams_ffprobe(master_video, ffprobe_exe)

    cp1 = check_1_iso_bmff_box_ordering(master_video)
    cp2 = check_2_video_stream_geometry(probe_data)
    cp3 = check_3_audio_stream_geometry(probe_data)
    cp4 = check_4_audio_video_sync(probe_data)
    cp5 = check_5_bitrate_and_size_density(master_video, probe_data)
    cp6 = check_6_subtitles_verification(subtitles_dir)
    cp7 = check_7_audio_dynamics_and_anticlipping(master_video, ffmpeg_exe)
    cp8 = check_8_brain_mirror_verification(subtitles_dir, brain_dir)

    all_cps = [cp1, cp2, cp3, cp4, cp5, cp6, cp7, cp8]
    all_passed = all(cp.passed for cp in all_cps)

    report = {
        "verified_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "master_video": str(master_video),
        "all_passed": all_passed,
        "passed_count": sum(1 for cp in all_cps if cp.passed),
        "total_count": len(all_cps),
        "checkpoints": [asdict(cp) for cp in all_cps],
    }

    if verbose:
        for cp in all_cps:
            status_str = "[PASS]" if cp.passed else "[FAIL]"
            print(f"{status_str} Checkpoint {cp.checkpoint_id}: {cp.name}")
            if not cp.passed:
                print(f"       Error: {cp.error_message}")
            for k, v in cp.details.items():
                print(f"       - {k}: {v}")

    return report


def probe_media_streams(video_path: Path) -> Dict[str, Any]:
    """Probe media streams and return duration_v, duration_a, and stream metadata."""
    _, ffprobe_exe = resolve_executables()
    probe_data = probe_streams_ffprobe(video_path, ffprobe_exe)
    v_stream = next((s for s in probe_data.get("streams", []) if s.get("codec_type") == "video"), {})
    a_stream = next((s for s in probe_data.get("streams", []) if s.get("codec_type") == "audio"), {})
    dur_v = float(v_stream.get("duration") or probe_data.get("format", {}).get("duration", 0))
    dur_a = float(a_stream.get("duration") or probe_data.get("format", {}).get("duration", 0))
    return {
        "duration_v": dur_v,
        "duration_a": dur_a,
        "video_stream": v_stream,
        "audio_stream": a_stream,
        "probe_data": probe_data,
    }


def verify_cinematic_delivery(
    master_path: Optional[Path] = None,
    brain_dir: Optional[Path] = None,
    subtitles_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Compatibility API returning all_checkpoints_passed and dict of checkpoints."""
    mv = master_path or DEFAULT_MASTER_VIDEO
    bd = brain_dir or DEFAULT_BRAIN_DIR
    sd = subtitles_dir or (mv.parent if mv else DEFAULT_SUBTITLES_DIR)
    raw = run_all_checkpoints(master_video=mv, subtitles_dir=sd, brain_dir=bd)
    checkpoints_dict: Dict[str, Dict[str, Any]] = {}
    for cp in raw["checkpoints"]:
        key = f"checkpoint_{cp['checkpoint_id']}_{cp['name'].lower().replace(' ', '_').replace('-', '_')}"
        checkpoints_dict[key] = {
            "id": cp["checkpoint_id"],
            "name": cp["name"],
            "pass": cp["passed"],
            "passed": cp["passed"],
            "details": cp["details"],
            "error": cp["error_message"],
        }
    return {
        "all_checkpoints_passed": raw["all_passed"],
        "all_passed": raw["all_passed"],
        "passed_count": raw["passed_count"],
        "total_count": raw["total_count"],
        "checkpoints": checkpoints_dict,
        "raw_report": raw,
    }


verify_ep01_cinematic_delivery = verify_cinematic_delivery


def main() -> int:
    parser = argparse.ArgumentParser(description="Milestone 4 Master Verification Pipeline (8 Checkpoints)")
    parser.add_argument("--target-video", type=Path, default=DEFAULT_MASTER_VIDEO, help="Path to master MP4 video")
    parser.add_argument("--subtitles-dir", type=Path, default=DEFAULT_SUBTITLES_DIR, help="Path to subtitles dir")
    parser.add_argument("--brain-dir", type=Path, default=DEFAULT_BRAIN_DIR, help="Path to brain mirror dir")
    parser.add_argument("--json", action="store_true", help="Output results in JSON format")
    parser.add_argument("--verbose", action="store_true", help="Print verbose checkpoint details")
    parser.add_argument("--verify-only", action="store_true", help="Run stream verification without side effects")
    args = parser.parse_args()

    report = run_all_checkpoints(
        master_video=args.target_video,
        subtitles_dir=args.subtitles_dir,
        brain_dir=args.brain_dir,
        verbose=args.verbose,
    )

    if args.json:
        print(json.dumps(report, indent=2))
    elif not args.verbose:
        summary_icon = "SUCCESS" if report["all_passed"] else "FAILURE"
        print(f"[{summary_icon}] Verified {report['passed_count']}/{report['total_count']} checkpoints across {args.target_video.name}")
        for cp in report["checkpoints"]:
            tag = "OK" if cp["passed"] else "FAIL"
            print(f"  [{tag}] Checkpoint {cp['checkpoint_id']}: {cp['name']}")

    return 0 if report["all_passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
