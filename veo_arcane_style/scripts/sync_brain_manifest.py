"""Manifest Indexer and Brain Mirror Parity Synchronizer for Veo Arcane Style.

Provides complete SHA-256 cryptographic indexing and metadata extraction
for all 10 deliverables, validating parity across local output and brain mirror.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any, Dict, List, Optional, Tuple

import cv2
from PIL import Image

try:
    import imageio_ffmpeg
except ImportError:
    imageio_ffmpeg = None  # type: ignore[assignment]

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = next((p for p in SCRIPT_DIR.parents if (p / "veo_arcane_style").is_dir()), SCRIPT_DIR.parents[1])
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "veo_arcane_style" / "output"
DEFAULT_BRAIN_DIR = Path(r"C:\Users\Orakul Grey\.gemini\antigravity\brain\94dd6a04-54e7-4e8c-9551-224cace4f85f")

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


def compute_sha256(path: Path) -> str:
    """Compute SHA-256 hash in 64KB chunks."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def check_faststart(video_path: Path) -> bool:
    """Check ISO-BMFF FastStart layout (moov before mdat in first 256KB)."""
    if not video_path.is_file() or video_path.stat().st_size < 100:
        return False
    header = video_path.read_bytes()[:262144]
    moov = header.find(b"moov")
    mdat = header.find(b"mdat")
    return moov != -1 and (mdat == -1 or moov < mdat)


def get_ffmpeg_exe() -> Optional[str]:
    """Discover ffmpeg executable via imageio_ffmpeg or system PATH."""
    if imageio_ffmpeg is not None:
        try:
            exe = imageio_ffmpeg.get_ffmpeg_exe()
            if exe and Path(exe).is_file():
                return str(exe)
        except Exception:
            pass
    return shutil.which("ffmpeg")


def extract_media_parameters(src_p: Path, ext: str, ffmpeg_exe: Optional[str]) -> Dict[str, Any]:
    """Extract container and stream parameters for video, image, or document."""
    params: Dict[str, Any] = {}
    if ext == ".mp4":
        cap = cv2.VideoCapture(str(src_p))
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
        fc = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        cap.release()
        dur = round(fc / fps, 2) if fps > 0 else 0.0

        has_h264, has_aac = False, False
        if ffmpeg_exe:
            try:
                res = subprocess.run([ffmpeg_exe, "-hide_banner", "-i", str(src_p)], capture_output=True, text=True, timeout=10)
                stderr = res.stderr.lower()
                has_h264 = "h264" in stderr or "avc1" in stderr
                has_aac = "aac" in stderr
            except Exception:
                pass

        params = {
            "width": w,
            "height": h,
            "fps": fps,
            "frame_count": fc,
            "duration_seconds": dur,
            "video_codec": "h264" if has_h264 else "unknown",
            "audio_codec": "aac" if has_aac else "none",
            "faststart": check_faststart(src_p),
            "is_hd": (w >= 1280 and h >= 720),
        }
    elif ext == ".png":
        with Image.open(src_p) as im:
            params = {
                "width": im.width,
                "height": im.height,
                "mode": im.mode,
                "format": im.format,
            }
    elif ext in [".json", ".md", ".log"]:
        with open(src_p, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        params = {
            "line_count": len(lines),
            "char_count": sum(len(l) for l in lines),
        }
    return params


def build_manifest_and_sync(
    output_dir: Path,
    brain_dir: Path,
    sync_stale_files: bool = True,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Index deliverables, optionally sync stale files to brain, and write manifest.json."""
    if not output_dir.is_dir():
        raise FileNotFoundError(f"Output directory does not exist: {output_dir}")

    ffmpeg_exe = get_ffmpeg_exe()
    deliverables: List[Dict[str, Any]] = []

    # 1. Pre-sync pass if enabled
    if sync_stale_files and not dry_run:
        brain_dir.mkdir(parents=True, exist_ok=True)
        for rel, _, _ in DELIVERABLE_SPECS:
            src_p = output_dir / rel
            dst_p = brain_dir / rel
            if not src_p.is_file():
                continue
            needs_copy = False
            if not dst_p.is_file():
                needs_copy = True
            elif dst_p.stat().st_size != src_p.stat().st_size:
                needs_copy = True
            elif compute_sha256(src_p) != compute_sha256(dst_p):
                needs_copy = True

            if needs_copy:
                dst_p.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src_p, dst_p)

    # 2. Complete Indexing pass
    for rel, ftype, mime in DELIVERABLE_SPECS:
        src_p = output_dir / rel
        dst_p = brain_dir / rel

        if not src_p.is_file():
            raise FileNotFoundError(f"Required deliverable missing in output dir: {src_p}")

        src_stat = src_p.stat()
        src_sha = compute_sha256(src_p)
        src_mtime = datetime.datetime.fromtimestamp(src_stat.st_mtime, tz=datetime.timezone.utc).isoformat()

        dst_exists = dst_p.is_file()
        dst_stat = dst_p.stat() if dst_exists else None
        dst_sha = compute_sha256(dst_p) if dst_exists else None
        parity = (src_sha == dst_sha) if (dst_exists and dst_sha) else False

        media_params = extract_media_parameters(src_p, src_p.suffix.lower(), ffmpeg_exe)

        entry = {
            "relative_path": rel.replace("\\", "/"),
            "file_name": src_p.name,
            "file_type": ftype,
            "mime_type": mime,
            "size_bytes": src_stat.st_size,
            "sha256": src_sha,
            "mtime_utc": src_mtime,
            "media_parameters": media_params,
            "brain_mirror": {
                "mirrored_path": str(dst_p),
                "exists": dst_exists,
                "size_bytes": dst_stat.st_size if dst_stat else None,
                "sha256": dst_sha,
                "parity_match": parity,
            },
        }
        deliverables.append(entry)

    matched_count = sum(1 for e in deliverables if e["brain_mirror"]["parity_match"])
    status_str = "VERIFIED_BIT_FOR_BIT_PARITY" if matched_count == len(deliverables) else f"PARTIAL_MATCH_{matched_count}_OF_{len(deliverables)}"

    manifest = {
        "manifest_version": "1.0.0",
        "project": "Google Veo 3.1 Arcane Style Benchmark",
        "milestone": "Milestone 4: Dual Verification Suite & Brain Mirroring Final Signoff",
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "local_output_root": str(output_dir),
        "brain_mirror_root": str(brain_dir),
        "total_deliverables": len(deliverables),
        "parity_summary": {
            "total_deliverables": len(deliverables),
            "parity_matched": matched_count,
            "parity_mismatched": len(deliverables) - matched_count,
            "status": status_str,
        },
        "deliverables": deliverables,
    }

    if not dry_run:
        # Atomic write to local output directory
        local_manifest = output_dir / "manifest.json"
        tmp_manifest = output_dir / "manifest.json.tmp"
        with open(tmp_manifest, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)
        tmp_manifest.replace(local_manifest)

        # Mirror manifest.json to brain directory
        brain_dir.mkdir(parents=True, exist_ok=True)
        brain_manifest = brain_dir / "manifest.json"
        shutil.copy2(local_manifest, brain_manifest)

        # Validate manifest parity
        if compute_sha256(local_manifest) != compute_sha256(brain_manifest):
            raise IOError("SHA-256 parity mismatch between local and mirrored manifest.json")

    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Manifest Generator and Brain Mirror Synchronizer")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--mirror-dir", type=Path, default=DEFAULT_BRAIN_DIR)
    parser.add_argument("--no-sync", action="store_true", help="Skip syncing stale files to brain mirror")
    parser.add_argument("--dry-run", action="store_true", help="Print manifest without writing files")
    args = parser.parse_args()

    manifest = build_manifest_and_sync(
        output_dir=args.output_dir,
        brain_dir=args.mirror_dir,
        sync_stale_files=not args.no_sync,
        dry_run=args.dry_run,
    )
    print(json.dumps(manifest["parity_summary"], indent=2))


if __name__ == "__main__":
    main()
