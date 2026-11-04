#!/usr/bin/env python3
"""scripts/generate_ttd_ep01_flow_keyframes.py
Production generator for all 12 episodic 720p 16:9 master keyframes for
The Tactical Deadlock (TTD) Episode 1 Pilot.
Grounded on canonical background plates with soft Gaussian ROI blending (sigma=28.0)
and automated forensic quality gating (SSIM_bg >= 0.85, MAE_bg <= 6.0, sparks <= 4).
100% English-only source code (0 literal Cyrillic characters).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import sys
from typing import Any, Dict, List

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.ttd_keyframe_composer import (
    SHOT_SPECS,
    compose_and_save_shot_keyframe,
    get_file_sha256,
)

DEFAULT_OUTPUT_DIR = ROOT_DIR / "output" / "ttd_ep01_flow_keyframes"
DEFAULT_BRAIN_DIR = Path(r"C:\Users\Orakul Grey\.gemini\antigravity\brain\94dd6a04-54e7-4e8c-9551-224cace4f85f")
SHOT_MATRIX_PATH = ROOT_DIR / "docs" / "ttd_ep01_shot_matrix.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate Episode 1 Pilot Keyframes")
    parser.add_argument("--shot-ids", type=str, default="all", help="Comma-separated shot IDs or 'all'")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help="Destination directory")
    parser.add_argument("--brain-dir", type=Path, default=DEFAULT_BRAIN_DIR, help="Persistent brain directory")
    parser.add_argument("--force", action="store_true", help="Force overwrite existing keyframes")
    parser.add_argument("--verify-only", action="store_true", help="Audit and verify existing keyframes without re-rendering")
    parser.add_argument("--dry-run", action="store_true", help="Pre-flight check without file modifications")
    parser.add_argument("--mirror", action="store_true", default=True, help="Mirror generated keyframes to brain directory")
    return parser.parse_args()


def run_keyframe_pipeline(args: argparse.Namespace) -> int:
    out_dir: Path = args.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    if not SHOT_MATRIX_PATH.is_file():
        print(f"Error: Shot matrix not found at {SHOT_MATRIX_PATH}", file=sys.stderr)
        return 1

    with open(SHOT_MATRIX_PATH, "r", encoding="utf-8") as f:
        shot_matrix: List[Dict[str, Any]] = json.load(f)

    shot_map = {s["shot_id"]: s for s in shot_matrix}

    if args.shot_ids.strip().lower() == "all":
        target_ids = sorted(SHOT_SPECS.keys())
    else:
        target_ids = [s.strip().upper() for s in args.shot_ids.split(",") if s.strip()]

    print(f"Processing {len(target_ids)} keyframes into {out_dir}...")
    manifest_entries: List[Dict[str, Any]] = []
    failures: List[str] = []

    for sid in target_ids:
        if sid not in SHOT_SPECS:
            print(f"Warning: Shot {sid} not in SHOT_SPECS, skipping.", file=sys.stderr)
            failures.append(sid)
            continue

        filename = f"ttd_ep01_{sid.lower().replace('-', '_')}_keyframe.png"
        out_file = out_dir / filename

        if args.dry_run:
            print(f"[DRY-RUN] Would process {sid} -> {out_file.name}")
            continue

        try:
            audit = compose_and_save_shot_keyframe(
                shot_id=sid,
                output_path=out_file,
                root_dir=ROOT_DIR,
                force=args.force or not args.verify_only,
            )
            audit["filename"] = filename
            meta = shot_map.get(sid, {})
            audit["scene_title"] = meta.get("scene_title", "")
            audit["duration_seconds"] = meta.get("duration_seconds", 0.0)
            audit["characters"] = meta.get("characters", [])
            audit["positive_prompt"] = meta.get("positive_prompt", "")
            manifest_entries.append(audit)

            status = "PASS" if (audit["bg_drift_passed"] and audit["spark_gate_passed"]) else "FAIL"
            print(f"[{status}] {sid}: MAE_bg={audit['mae_bg']:.4f}, SSIM_bg={audit['ssim_bg']:.4f}, sparks={audit['spark_count']}")
            if status == "FAIL":
                failures.append(sid)

            if args.mirror and args.brain_dir and args.brain_dir.is_dir() and out_file.is_file():
                dest = args.brain_dir / filename
                shutil.copy2(out_file, dest)

        except Exception as e:
            print(f"[ERROR] Failed processing {sid}: {e}", file=sys.stderr)
            failures.append(sid)

    if args.dry_run:
        print("Dry run completed successfully.")
        return 0

    manifest = {
        "manifest_type": "ttd_ep01_flow_keyframes",
        "total_keyframes": len(manifest_entries),
        "failures_count": len(failures),
        "all_passed": (len(failures) == 0 and len(manifest_entries) == len(target_ids)),
        "keyframes": manifest_entries,
    }
    manifest_path = out_dir / "manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    if args.mirror and args.brain_dir and args.brain_dir.is_dir():
        legacy_mf = ROOT_DIR / "output" / "ttd_ep01_manga_transitions" / "manifest.json"
        if legacy_mf.is_file():
            shutil.copy2(legacy_mf, args.brain_dir / "manifest.json")
        shutil.copy2(manifest_path, args.brain_dir / "ttd_ep01_flow_keyframes_manifest.json")

    print(f"\nManifest written to {manifest_path} (All passed: {manifest['all_passed']})")
    return 0 if manifest["all_passed"] else 1


if __name__ == "__main__":
    sys.exit(run_keyframe_pipeline(parse_args()))
