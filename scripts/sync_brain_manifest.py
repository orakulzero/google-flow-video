"""scripts/sync_brain_manifest.py
Synchronizes and cryptographically verifies Episode 1 pilot deliverables in persistent brain storage.
Enforces namespace collision guard on brain/manifest.json and mirrors all primary and ancillary assets.
100% English-only, chunking <= 180 lines (REQ-FEAT-14).
"""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import shutil
import sys

BRAIN_DIR = Path(r"C:\Users\Orakul Grey\.gemini\antigravity\brain\94dd6a04-54e7-4e8c-9551-224cace4f85f")
ROOT_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT_DIR / "output"
KF_DIR = OUTPUT_DIR / "ttd_ep01_flow_keyframes"
VIDEOS_DIR = OUTPUT_DIR / "ttd_ep01_flow_videos"


def compute_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def get_delivery_catalog() -> list[dict[str, any]]:
    catalog: list[dict[str, any]] = []

    # 18 Primary Deliverables
    primary_items = [
        (OUTPUT_DIR / "ttd_ep01_master_contact_sheet.png", "ttd_ep01_master_contact_sheet.png", "Master Contact Sheet"),
        (OUTPUT_DIR / "ttd_ep01_manifest.json", "ttd_ep01_manifest.json", "Master Manifest"),
        (OUTPUT_DIR / "ttd_ep01_m4_audit_certificate.json", "ttd_ep01_m4_audit_certificate.json", "M4 Audit Certificate"),
        (VIDEOS_DIR / "ttd_ep01_shot_04_lucas_roar_command_720p.mp4", "ttd_ep01_shot_04_lucas_roar_command_720p.mp4", "Shot 04 Video"),
        (VIDEOS_DIR / "ttd_ep01_pilot_master_720p.mp4", "ttd_ep01_pilot_master_720p.mp4", "Pilot Master Video"),
        (VIDEOS_DIR / "ttd_ep01_pilot_narration.vtt", "ttd_ep01_pilot_narration.vtt", "Narration WebVTT"),
        (VIDEOS_DIR / "ttd_ep01_pilot_narration.srt", "ttd_ep01_pilot_narration.srt", "Narration SRT"),
    ]
    for idx in range(1, 13):
        fn = f"ttd_ep01_shot_{idx:02d}_keyframe.png"
        primary_items.append((KF_DIR / fn, fn, f"Keyframe Shot {idx:02d}"))

    for src, dst_name, desc in primary_items:
        catalog.append({"src": src, "dst_name": dst_name, "desc": desc, "type": "primary"})

    # 2 Ancillary Deliverables
    ancillary_items = [
        (KF_DIR / "manifest.json", "ttd_ep01_flow_keyframes_manifest.json", "Keyframes Manifest"),
        (VIDEOS_DIR / "ttd_ep01_cl02_lucas_command_roar_720p.mp4", "ttd_ep01_cl02_lucas_command_roar_720p.mp4", "CL-02 Video Cut"),
    ]
    for src, dst_name, desc in ancillary_items:
        catalog.append({"src": src, "dst_name": dst_name, "desc": desc, "type": "ancillary"})

    return catalog


def verify_namespace_collision_guard(brain_dir: Path) -> bool:
    target = brain_dir / "manifest.json"
    if not target.is_file():
        print(f"[FAIL] Namespace guard: {target} does not exist!")
        return False
    size = target.stat().st_size
    sha = compute_sha256(target)
    if size != 10897 or not sha.startswith("b42d2919"):
        print(f"[FAIL] Namespace guard violated: size={size} (expected 10897), sha={sha} (expected b42d2919...)")
        return False
    print(f"[OK] Namespace collision guard verified: brain/manifest.json intact ({size} bytes, SHA: {sha[:16]}...)")
    return True


def sync_and_verify(brain_dir: Path, verify_only: bool = False) -> bool:
    if not brain_dir.is_dir():
        print(f"[ERROR] Brain storage directory does not exist: {brain_dir}")
        return False

    guard_ok = verify_namespace_collision_guard(brain_dir)
    if not guard_ok:
        return False

    catalog = get_delivery_catalog()
    all_matched = True

    for item in catalog:
        src = item["src"]
        dst_name = item["dst_name"]
        dst = brain_dir / dst_name

        if not src.is_file():
            print(f"[FAIL] Source file missing: {src}")
            all_matched = False
            continue

        src_sha = compute_sha256(src)
        src_size = src.stat().st_size

        if not dst.is_file():
            if verify_only:
                print(f"[MISSING] {dst_name} ({item['desc']}) not found in brain storage")
                all_matched = False
                continue
            print(f"[MIRROR] Copying missing {src.name} -> {dst_name} ({src_size} bytes)...")
            shutil.copy2(src, dst)

        dst_sha = compute_sha256(dst)
        if src_sha != dst_sha:
            if verify_only:
                print(f"[MISMATCH] {dst_name}: src_sha={src_sha[:12]} != dst_sha={dst_sha[:12]}")
                all_matched = False
                continue
            print(f"[UPDATE] Re-copying diverged {src.name} -> {dst_name}...")
            shutil.copy2(src, dst)
            dst_sha = compute_sha256(dst)

        if src_sha == dst_sha:
            print(f"[PARITY] {dst_name:<42s} | {src_size:>9d} bytes | SHA: {dst_sha[:16]}... | OK")
        else:
            print(f"[FAIL] Parity failure on {dst_name} after sync!")
            all_matched = False

    return all_matched


def main() -> int:
    parser = argparse.ArgumentParser(description="Synchronize & verify Episode 1 deliverables in brain storage")
    parser.add_argument("--verify-only", action="store_true", help="Only verify bit-for-bit SHA-256 parity without copying")
    parser.add_argument("--brain-dir", type=Path, default=BRAIN_DIR, help="Path to brain storage directory")
    args = parser.parse_args()

    mode = "VERIFY ONLY" if args.verify_only else "SYNC & VERIFY"
    print(f"=== Brain Mirror Synchronizer ({mode}) ===")
    print(f"Target Directory: {args.brain_dir}\n")

    success = sync_and_verify(args.brain_dir, verify_only=args.verify_only)
    if success:
        print("\n[SUCCESS] 100% cryptographic SHA-256 parity confirmed across all Episode 1 deliverables.")
        return 0
    else:
        print("\n[ERROR] Brain mirror synchronization failed verification.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
