#!/usr/bin/env python3
"""
scripts/generate_ep01_manga_flow_transitions.py
Generates 720p H.264 silent video transition segments across sequential keyframes
for Tyrant of the Tower Defense Game (Episode 1) using genuine Google Flow
automation (#799 AgentOnlyComposer / FlowApiClient).
"""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from typing import Any
import urllib.request

import cv2
import imageio_ffmpeg

from gflow_cli.api.client import FlowApiClient
from gflow_cli.api.transports.agent_only_composer import (
    EDITOR,
    FINISHED_VIDEO_TILE,
    LIVE_GATE,
    SUBMIT,
    AgentOnlyComposer,
    _Run,
    _VIDEO_JS,
    download_video,
)
from gflow_cli.api.transports.migrated_composer import ASPECT_LIGATURE, VIDEO_MODEL_MENU_MATCHERS
from gflow_cli.api.video import Aspect as VideoAspect, VideoModel

TESTBENCH_DIR = Path(__file__).resolve().parent.parent
DEFAULT_PROJECT_ID = "7d9a2a67-9cd2-4a79-932e-717d2e29257f"
DEFAULT_PROXY = "http://127.0.0.1:7890"
DEFAULT_PROFILE_DIR = Path(r"C:\Users\Orakul Grey\AppData\Local\ffroliva\gflow-cli\profile_default")
DEFAULT_CLEAN_DIR = TESTBENCH_DIR / "output" / "ttd_ep01_manga_transitions" / "clean_frames"
DEFAULT_SEGMENTS_DIR = TESTBENCH_DIR / "output" / "ttd_ep01_manga_transitions" / "segments"


@dataclass
class TransitionSpec:
    segment_id: int
    start_keyframe: str
    end_keyframe: str
    title: str
    prompt: str
    duration_sec: float = 3.5


@dataclass
class PipelineConfig:
    project_id: str
    proxy_url: str
    profile_dir: Path
    clean_dir: Path
    out_dir: Path
    model: str = "omni-flash"
    timeout_sec: int = 360
    max_retries: int = 2
    force: bool = False
    keep_raw: bool = False
    dry_run: bool = False
    target_segment: int | None = None


TRANSITIONS: list[TransitionSpec] = [
    TransitionSpec(
        segment_id=1,
        start_keyframe="ep01_frame_001_clean.png",
        end_keyframe="ep01_frame_002_clean.png",
        title="Game Clear Fanfare to Gamer Ecstatic Victory Celebration",
        prompt=(
            "Make me a video in a 16:9 aspect ratio: Hand-painted dark fantasy animation in manhwa style. "
            "Cinematic anime camera dolly back from a glowing retro CRT game clear announcement screen pulsing with "
            "golden victory runes and vibrant pixel fanfare. The bright monitor glow washes over a dark gaming bedroom "
            "as the exhausted black-haired gamer in a light-blue hoodie throws both arms up into the air in ecstatic, "
            "roaring triumph. Smooth camera orbit with warm monitor light reflections, highly detailed manhwa animation "
            "style, seamless transition, no comic panels, no text overlays."
        ),
        duration_sec=3.5,
    ),
    TransitionSpec(
        segment_id=2,
        start_keyframe="ep01_frame_002_clean.png",
        end_keyframe="ep01_frame_004_clean.png",
        title="Gamer Victory Celebration to Streamer Live Chat Reaction",
        prompt=(
            "Make me a video in a 16:9 aspect ratio: Hand-painted dark fantasy animation in manhwa style. "
            "Dynamic anime camera push-in as the cheering gamer lowers his arms and leans excitedly toward the "
            "ultrawide streaming display. The dim bedroom atmosphere shifts as glowing live stream UI elements and "
            "vibrant chat reactions illuminate his expressive face and headset. Fast cinematic motion blur into the "
            "second frame where the streamer shouts with intense passion directly into the web camera, vibrant RGB "
            "lighting reflections, cinematic 16:9 720p manhwa art style, seamless continuity."
        ),
        duration_sec=3.5,
    ),
    TransitionSpec(
        segment_id=3,
        start_keyframe="ep01_frame_004_clean.png",
        end_keyframe="ep01_frame_005_clean.png",
        title="Streamer Reaction dissolving into Save the Empire Gothic Title Screen",
        prompt=(
            "Make me a video in a 16:9 aspect ratio: Hand-painted dark fantasy animation in manhwa style. "
            "Cinematic dissolve and rack focus from the shouting streamer's illuminated face into the dark, ornate "
            "fantasy universe of the game. A blinding flare of golden and crimson magical energy erupts across the screen, "
            "resolving into the majestic, weather-worn gothic stone monument and golden title screen of 'Save the Empire'. "
            "Swirling atmospheric dust motes and ancient arcane runes hover in twilight, dramatic dark fantasy aesthetic, "
            "cinematic 16:9 720p, seamless frame-to-frame flow."
        ),
        duration_sec=3.5,
    ),
    TransitionSpec(
        segment_id=4,
        start_keyframe="ep01_frame_005_clean.png",
        end_keyframe="ep01_frame_009_clean.png",
        title="Title Screen zooming in and dissolving into Tactical Strategy Map & Defense Grid",
        prompt=(
            "Make me a video in a 16:9 aspect ratio: Hand-painted dark fantasy animation in manhwa style. "
            "Slow, grand cinematic camera zoom penetrating straight through the gothic title card into an intricate "
            "top-down strategy battle grid. The weathered title art transforms into a stylized dark fantasy tactical "
            "warfare map of Crossroads fortress, with glowing grid hexes, tactical defense lines, and miniature troop "
            "formation markers. Ambient glowing war-room parchment texture, subtle pulse of arcane radar lines, clean "
            "16:9 widescreen anime transition, zero comic artifacts."
        ),
        duration_sec=3.5,
    ),
    TransitionSpec(
        segment_id=5,
        start_keyframe="ep01_frame_009_clean.png",
        end_keyframe="ep01_frame_014_clean.png",
        title="Strategy Map pulling back into Modern Streamer Broadcast Desk",
        prompt=(
            "Make me a video in a 16:9 aspect ratio: Hand-painted dark fantasy animation in manhwa style. "
            "Smooth cinematic zoom-out from the tactical defense map, pulling out of the computer display to reveal "
            "the modern streamer broadcast workstation in a darkened room. Glowing ultrawide monitors, a professional "
            "boom microphone, desktop sound mixer, and animated donation alert graphics reflect soft neon light onto "
            "acoustic wall panels. Fluid camera motion tracking from digital game pixels to physical streamer battle "
            "station, cinematic 16:9 720p, seamless visual flow."
        ),
        duration_sec=3.5,
    ),
    TransitionSpec(
        segment_id=6,
        start_keyframe="ep01_frame_014_clean.png",
        end_keyframe="ep01_frame_023_clean.png",
        title="Streamer Desk dissolving into Desperate Battlefield Ramparts & Fallen Soldier Corpses",
        prompt=(
            "Make me a video in a 16:9 aspect ratio: Hand-painted dark fantasy animation in manhwa style. "
            "Dramatic, somber dissolve as the modern cozy glow of the streaming station shatters and fades into "
            "cold, ash-choked fantasy twilight. Swirling black smoke, falling rain, and flickering embers drift across "
            "the bloody stone battlements of Crossroads fortress. The camera pans down slowly across broken shields, "
            "shattered broadswords, and fallen soldier corpses lying silent on the drenched flagstones. Gritty dark "
            "fantasy atmosphere, painterly manhwa animation style, 16:9 720p, seamless transition."
        ),
        duration_sec=4.0,
    ),
    TransitionSpec(
        segment_id=7,
        start_keyframe="ep01_frame_023_clean.png",
        end_keyframe="ep01_frame_026_clean.png",
        title="Rampart Carnage & Drifting Smoke dissolving into Pitch Black Void with Lucas Solitary Back",
        prompt=(
            "Make me a video in a 16:9 aspect ratio: Hand-painted dark fantasy animation in manhwa style. "
            "The smoke and ruins of the battlefield ramparts gradually dissolve into an abyss of absolute "
            "pitch-black darkness. The camera smoothly orbits around and settles behind vanguard knight Lucas "
            "standing completely solitary in the void. His weathered silver-and-steel plate armor is stained with "
            "soot, and his tattered blue-and-white cape flutters gently in an unseen cold breeze, head bowed in "
            "profound grief and exhaustion. Haunting, somber cinematic anime lighting, 16:9 720p, seamless finish "
            "on Lucas solitary back."
        ),
        duration_sec=4.0,
    ),
]


def resolve_ffmpeg_exe() -> str:
    """Find a functional FFmpeg executable."""
    found = shutil.which("ffmpeg")
    if found:
        return found
    return imageio_ffmpeg.get_ffmpeg_exe()


def check_proxy_reachability(proxy_url: str = DEFAULT_PROXY, timeout_sec: float = 8.0) -> bool:
    """Verify that the browser proxy endpoint is alive and passing traffic."""
    try:
        proxy_handler = urllib.request.ProxyHandler({"http": proxy_url, "https": proxy_url})
        opener = urllib.request.build_opener(proxy_handler)
        req = urllib.request.Request("https://www.google.com")
        with opener.open(req, timeout=timeout_sec) as resp:
            return bool(resp.status == 200)
    except Exception:
        return False


def cleanup_chrome_profile_locks(profile_dir: Path) -> dict[str, int]:
    """Clean up stale Chrome profile locks and terminate orphaned headless processes."""
    killed_processes = 0
    removed_lock_files = 0

    try:
        import psutil

        for proc in psutil.process_iter(["pid", "name", "cmdline"]):
            try:
                if proc.info["name"] == "chrome.exe":
                    cmdline = " ".join(proc.info["cmdline"] or [])
                    if "ffroliva" in cmdline and "profile_default" in cmdline:
                        proc.kill()
                        killed_processes += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
    except ImportError:
        pass

    if profile_dir.is_dir():
        for lock_name in ("SingletonLock", "SingletonCookie", "SingletonSocket", "lockfile"):
            lock_p = profile_dir / lock_name
            if lock_p.exists():
                try:
                    lock_p.unlink()
                    removed_lock_files += 1
                except OSError:
                    pass

    return {"killed_processes": killed_processes, "removed_lock_files": removed_lock_files}


def configure_gflow_environment(proxy_url: str = DEFAULT_PROXY) -> None:
    """Set process environment variables for gflow-cli browser automation."""
    os.environ["GFLOW_CLI_BROWSER_PROXY"] = proxy_url
    os.environ["HTTPS_PROXY"] = proxy_url
    os.environ["HTTP_PROXY"] = proxy_url
    os.environ["GFLOW_CLI_FLOW_HOST"] = "flow.google.com"
    os.environ["GFLOW_CLI_AGENT_CONFIRM"] = "never"
    os.environ["GFLOW_CLI_BROWSER_WINDOW_POSITION"] = "-30000,-30000"
    os.environ["GFLOW_CLI_UPDATE_CHECK"] = "0"
    os.environ["GFLOW_CLI_LEASE_WAIT_SECONDS"] = "30"


def standardize_to_720p_silent(raw_mp4: Path, final_mp4: Path) -> Path:
    """Standardize video to 1280x720 24fps H.264 strictly silent MP4 container."""
    ffmpeg_exe = resolve_ffmpeg_exe()
    tmp_out = final_mp4.with_suffix(".std.tmp.mp4")
    cmd = [
        ffmpeg_exe,
        "-y",
        "-i",
        str(raw_mp4),
        "-vf",
        "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2:black",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-r",
        "24",
        "-an",
        "-movflags",
        "+faststart",
        str(tmp_out),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode == 0 and tmp_out.is_file() and tmp_out.stat().st_size > 10_000:
        if final_mp4.is_file():
            final_mp4.unlink()
        tmp_out.rename(final_mp4)
        return final_mp4
    raise RuntimeError(f"Standardization to 720p silent failed: {proc.stderr[-400:]}")


def verify_segment(mp4_path: Path) -> dict[str, Any]:
    """Verify segment MP4 exists, is 1280x720 H.264, has non-zero duration, and zero audio channels."""
    if not mp4_path.is_file():
        return {"valid": False, "error": f"File {mp4_path} does not exist"}
    file_size = mp4_path.stat().st_size
    if file_size < 50_000:
        return {"valid": False, "error": f"File size too small ({file_size} bytes, min 50000)"}

    cap = cv2.VideoCapture(str(mp4_path))
    if not cap.isOpened():
        return {"valid": False, "error": "cv2.VideoCapture failed to open file"}

    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 24.0)
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = frame_count / fps if fps > 0 else 0.0
    cap.release()

    if width != 1280 or height != 720:
        return {"valid": False, "error": f"Invalid resolution {width}x{height}, expected 1280x720"}
    if duration < 1.0:
        return {"valid": False, "error": f"Duration too short ({duration:.2f}s)"}

    ffmpeg_exe = resolve_ffmpeg_exe()
    proc = subprocess.run(
        [ffmpeg_exe, "-hide_banner", "-i", str(mp4_path)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    stderr_out = proc.stderr or ""
    has_audio = "Audio:" in stderr_out
    has_h264 = "h264" in stderr_out.lower() or "avc1" in stderr_out.lower()

    if has_audio:
        return {"valid": False, "error": "Audio stream detected (strictly silent required)"}

    return {
        "valid": True,
        "width": width,
        "height": height,
        "fps": fps,
        "frame_count": frame_count,
        "duration": duration,
        "file_size": file_size,
        "h264_codec": has_h264,
        "silent": not has_audio,
    }


async def attach_ingredient_file(page, file_path: Path) -> None:
    """Upload and attach a keyframe image ingredient to the prompt composer."""
    add_btn = page.locator("button.add-menu-trigger").last
    await add_btn.click(timeout=8000)
    await asyncio.sleep(1.5)
    upload_btn = page.locator("button.sidebar-upload-btn").first
    async with page.expect_file_chooser(timeout=15000) as fc_info:
        await upload_btn.click(timeout=8000)
    chooser = await fc_info.value
    await chooser.set_files(str(file_path))
    await asyncio.sleep(4.0)
    detail_add = page.locator("button.detail-add-to-prompt-btn:not([disabled])").first
    try:
        await detail_add.wait_for(state="visible", timeout=20000)
        await detail_add.click(timeout=5000)
        await asyncio.sleep(2.0)
    except Exception:
        await page.keyboard.press("Escape")
        await asyncio.sleep(1.0)


async def clear_prompt_chips(page) -> None:
    """Remove existing ingredient chips from the prompt box."""
    chips = page.locator("flow-ingredient-chip button.chip-container")
    for _ in range(await chips.count()):
        try:
            if await chips.first.count() > 0 and await chips.first.is_visible(timeout=1000):
                await chips.first.click(timeout=2000)
                await asyncio.sleep(0.4)
        except Exception:
            break


async def await_generated_video(page, baseline_head: str | None, timeout_s: float = 360.0) -> tuple[str, str]:
    """Wait for Google Flow Omni Flash to finish video generation and return (uuid, video_src)."""
    deadline = time.monotonic() + timeout_s
    started = False
    while time.monotonic() < deadline:
        gates = page.locator(LIVE_GATE)
        if await gates.count() > 0:
            approve_btn = gates.first.locator(
                "div[role='radio'].option-row:not(.read-only):has(mat-icon:text-is('check'))"
            ).first
            if await approve_btn.count() > 0 and await approve_btn.is_visible(timeout=1000):
                await approve_btn.click(timeout=5000)
                await asyncio.sleep(2.0)

        state = await page.evaluate(_VIDEO_JS)
        pending = state.get("pending", 0)
        finished = state.get("finished", [])
        head = finished[0] if finished else None
        head_key = (head.get("video") or head.get("img") or "") if head else ""

        if pending > 0:
            started = True

        if (started or len(finished) > 0) and pending == 0 and head_key:
            if baseline_head is None or head_key != baseline_head:
                tile = page.locator(FINISHED_VIDEO_TILE).first
                await tile.hover(timeout=5000)
                await asyncio.sleep(2.0)
                vid_src = await page.evaluate('''() => {
                    const tile = document.querySelector('flow-video-tile:not(:has(flow-pending-tile))');
                    const vid = tile ? tile.querySelector('video') : null;
                    return vid ? (vid.currentSrc || vid.src || '') : '';
                }''')
                await page.mouse.move(0, 0)
                if vid_src:
                    token = head_key.split("/asb/")[-1].split("=")[0].split("?")[0] if "/asb/" in head_key else "clip"
                    video_uuid = f"flow_asb_{token[:24]}"
                    return video_uuid, vid_src

        await asyncio.sleep(2.0)

    raise TimeoutError(f"Timed out after {timeout_s}s waiting for video generation in Google Flow.")


async def render_segment_clip(
    page,
    composer: AgentOnlyComposer,
    spec: TransitionSpec,
    config: PipelineConfig,
) -> Path:
    """Submit prompt with attached keyframes and download the raw generated video from Google Flow."""
    start_path = config.clean_dir / spec.start_keyframe
    end_path = config.clean_dir / spec.end_keyframe

    if not start_path.is_file() or not end_path.is_file():
        raise FileNotFoundError(f"Missing keyframe: {start_path} or {end_path}")

    await clear_prompt_chips(page)

    await composer.apply_defaults(
        page,
        section="video",
        aspect_ligature=ASPECT_LIGATURE[VideoAspect.LANDSCAPE],
        count=1,
        model=VIDEO_MODEL_MENU_MATCHERS[VideoModel.OMNI_FLASH],
        confirm="never",
    )

    print(f"    Attaching start keyframe: {spec.start_keyframe}...", flush=True)
    await attach_ingredient_file(page, start_path)
    print(f"    Attaching end keyframe: {spec.end_keyframe}...", flush=True)
    await attach_ingredient_file(page, end_path)

    baseline_state = await page.evaluate(_VIDEO_JS)
    head = baseline_state["finished"][0] if baseline_state.get("finished") else None
    baseline_head = (head.get("video") or head.get("img") or "") if head else None

    editor = page.locator(EDITOR).last
    await editor.click(timeout=5000)
    await page.keyboard.press("ControlOrMeta+a")
    await page.keyboard.press("Delete")
    await page.keyboard.insert_text(spec.prompt)
    await asyncio.sleep(0.5)

    print("    Submitting prompt to Google Flow Omni Flash...", flush=True)
    await page.locator(SUBMIT).last.click(timeout=5000)

    budget_s = float(config.timeout_sec)
    print(f"    Waiting for video generation (budget={budget_s}s)...", flush=True)
    video_uuid, vid_src = await await_generated_video(page, baseline_head, timeout_s=budget_s)

    raw_path = config.out_dir / f"segment_{spec.segment_id:02d}.raw.mp4"

    async def _save_clip(_uuid: str, body: bytes) -> Path:
        raw_path.write_bytes(body)
        return raw_path

    print(f"    Downloading generated video tile (uuid={video_uuid})...", flush=True)
    await download_video(page, vid_src, video_uuid, _save_clip)
    return raw_path


async def run_pipeline(
    config: PipelineConfig,
    transitions: list[TransitionSpec],
) -> list[dict[str, Any]]:
    """Execute continuous transition generation pipeline across specified segments."""
    config.out_dir.mkdir(parents=True, exist_ok=True)
    targets = [t for t in transitions if config.target_segment is None or t.segment_id == config.target_segment]

    print("\n=== Manga Flow Transitions Pipeline ===", flush=True)
    print(f"Project: {config.project_id}", flush=True)
    print(f"Proxy: {config.proxy_url}", flush=True)
    print(f"Targets: {[t.segment_id for t in targets]}", flush=True)

    proxy_ok = check_proxy_reachability(config.proxy_url)
    print(f"Proxy Reachability: {'OK (200)' if proxy_ok else 'FAILED'}", flush=True)

    if config.dry_run:
        print("\n[DRY RUN] Validating keyframe assets and pipeline configuration...", flush=True)
        missing_count = 0
        for spec in targets:
            start_p = config.clean_dir / spec.start_keyframe
            end_p = config.clean_dir / spec.end_keyframe
            start_ok = start_p.is_file()
            end_ok = end_p.is_file()
            if not start_ok or not end_ok:
                missing_count += 1
            print(
                f"  Segment {spec.segment_id}: {spec.start_keyframe} ({'FOUND' if start_ok else 'MISSING'}) -> "
                f"{spec.end_keyframe} ({'FOUND' if end_ok else 'MISSING'}) | {spec.title}",
                flush=True,
            )
        print(f"\n[DRY RUN] Total segments: {len(targets)}, Missing assets: {missing_count}", flush=True)
        if not proxy_ok:
            print("[DRY RUN WARN] Proxy check failed; verify proxy is running before live execution.", flush=True)
        return []

    if not proxy_ok:
        raise RuntimeError(f"Proxy {config.proxy_url} is unreachable. Ensure proxy is active before running.")

    lock_info = cleanup_chrome_profile_locks(config.profile_dir)
    print(
        f"Profile Sanitization: killed {lock_info['killed_processes']} processes, "
        f"removed {lock_info['removed_lock_files']} lock files.",
        flush=True,
    )
    configure_gflow_environment(config.proxy_url)

    results: list[dict[str, Any]] = []

    async with FlowApiClient(config.profile_dir) as client:
        page = client._page
        assert page is not None
        composer = AgentOnlyComposer()

        print(f"Navigating to Google Flow project https://flow.google.com/project/{config.project_id}...", flush=True)
        await page.goto(
            f"https://flow.google.com/project/{config.project_id}",
            wait_until="domcontentloaded",
            timeout=60000,
        )
        await asyncio.sleep(6.0)

        new_session_btn = page.locator("button.header-action:has(mat-icon:text-is('edit_square'))").first
        if await new_session_btn.count() > 0 and await new_session_btn.is_visible():
            await new_session_btn.click(timeout=5000)
            await asyncio.sleep(2.0)

        for idx, spec in enumerate(targets, 1):
            out_mp4 = config.out_dir / f"segment_{spec.segment_id:02d}.mp4"
            print(f"\n[{idx}/{len(targets)}] --- Segment {spec.segment_id}: {spec.title} ---", flush=True)
            print(f"  Graph: {spec.start_keyframe} -> {spec.end_keyframe}", flush=True)

            if not config.force and out_mp4.is_file():
                v = verify_segment(out_mp4)
                if v["valid"]:
                    print(
                        f"  Existing segment is valid ({v['duration']:.2f}s, {v['file_size']} bytes). Reusing.",
                        flush=True,
                    )
                    results.append({"spec": spec, "output_path": str(out_mp4), "verification": v, "cached": True})
                    continue

            for attempt in range(1, config.max_retries + 1):
                try:
                    if attempt > 1:
                        print(f"  [RETRY] Resetting session for attempt {attempt}...", flush=True)
                        await page.goto(
                            f"https://flow.google.com/project/{config.project_id}",
                            wait_until="domcontentloaded",
                            timeout=60000,
                        )
                        await asyncio.sleep(6.0)
                        if await new_session_btn.count() > 0 and await new_session_btn.is_visible():
                            await new_session_btn.click(timeout=5000)
                            await asyncio.sleep(2.0)

                    raw_clip = await render_segment_clip(page, composer, spec, config)
                    std_clip = standardize_to_720p_silent(raw_clip, out_mp4)
                    if not config.keep_raw and raw_clip.is_file() and raw_clip != std_clip:
                        raw_clip.unlink()

                    verification = verify_segment(std_clip)
                    if not verification["valid"]:
                        raise RuntimeError(f"Segment failed verification: {verification.get('error')}")

                    print(
                        f"  -> SUCCESS: Segment {spec.segment_id} verified: 1280x720, "
                        f"duration={verification['duration']:.2f}s, size={verification['file_size']} bytes",
                        flush=True,
                    )
                    results.append(
                        {"spec": spec, "output_path": str(std_clip), "verification": verification, "cached": False}
                    )
                    break
                except Exception as exc:
                    print(f"  [WARN] Attempt {attempt} failed: {exc}", flush=True)
                    if attempt == config.max_retries:
                        raise RuntimeError(
                            f"Segment {spec.segment_id} failed after {config.max_retries} attempts: {exc}"
                        ) from exc
                    await asyncio.sleep(5.0)

    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate 7 continuous manga transitions via Google Flow.")
    parser.add_argument("--project", default=DEFAULT_PROJECT_ID, help="Google Flow project ID")
    parser.add_argument("--proxy", default=DEFAULT_PROXY, help="HTTP/HTTPS proxy URL")
    parser.add_argument("--profile-dir", type=Path, default=DEFAULT_PROFILE_DIR, help="Chrome profile directory")
    parser.add_argument("--clean-dir", type=Path, default=DEFAULT_CLEAN_DIR, help="Path to clean keyframes dir")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_SEGMENTS_DIR, help="Output segments directory")
    parser.add_argument("--model", default="omni-flash", help="Video generation model")
    parser.add_argument("--segment", type=int, default=None, choices=list(range(1, 8)), help="Target single segment")
    parser.add_argument("--all", action="store_true", help="Generate all 7 continuous segments")
    parser.add_argument("--timeout", type=int, default=360, help="Per-segment generation timeout in seconds")
    parser.add_argument("--max-retries", type=int, default=2, help="Maximum attempts per segment")
    parser.add_argument("--force", action="store_true", help="Force re-generation even if valid MP4 exists")
    parser.add_argument("--keep-raw", action="store_true", help="Keep raw unstandardized downloaded video")
    parser.add_argument("--dry-run", action="store_true", help="Dry run validation without launching browser")
    args = parser.parse_args()

    config = PipelineConfig(
        project_id=args.project,
        proxy_url=args.proxy,
        profile_dir=args.profile_dir,
        clean_dir=args.clean_dir,
        out_dir=args.out_dir,
        model=args.model,
        timeout_sec=args.timeout,
        max_retries=args.max_retries,
        force=args.force,
        keep_raw=args.keep_raw,
        dry_run=args.dry_run,
        target_segment=args.segment,
    )

    results = asyncio.run(run_pipeline(config, TRANSITIONS))
    if results:
        print("\n=== Generation Summary ===", flush=True)
        for r in results:
            spec = r["spec"]
            v = r["verification"]
            cached_flag = "[CACHED]" if r.get("cached") else "[GENERATED]"
            print(
                f"Segment {spec.segment_id} {cached_flag}: {r['output_path']} "
                f"({v['duration']:.2f}s, {v['width']}x{v['height']}, {v['file_size']} bytes)",
                flush=True,
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
