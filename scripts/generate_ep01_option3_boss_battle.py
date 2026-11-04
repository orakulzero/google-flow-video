#!/usr/bin/env python3
"""
scripts/generate_ep01_option3_boss_battle.py
Generate Episode 1 Option 3 Boss Battle & Monitor Scenes in Google Flow.
Renders 4 genuine multi-angle boss fight & monitor scenes:
- Segment 1: Wide Arena Boss Clash (Lucas vs monstrous Boss in ruined Cathedral Throne Hall)
- Segment 2: Low-Angle Shield Block & Sparks (Lucas blocks with round shield & counter-slashes)
- Segment 3: Decisive Final Strike -> CLEAR! Congratulations! (Broadsword cleave to victory fanfare)
- Segment 4: Rectangular Desk Dual Monitors & Stream Setup (RGB keyboard, 3-ring PC, dual monitors)
Standardizes all segments to 1280x720 24.0 fps CFR silent (-an) H.264 MP4.
Zero streamer webcam talking-head clips. 100% English-only code and comments.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional, Tuple
import uuid

import cv2
import imageio_ffmpeg
import numpy as np
from PIL import Image

ROOT_DIR = Path(__file__).resolve().parent.parent
CONCEPTS_DIR = ROOT_DIR / "output" / "canonical_arcane_concepts"
OUT_DIR = ROOT_DIR / "output" / "ttd_ep01_option3_boss_battle"
SEGMENTS_DIR = OUT_DIR / "segments"
LEGACY_SEGMENTS_DIR = ROOT_DIR / "output" / "ttd_ep01_manga_transitions" / "segments"
BRAIN_DIR = Path(r"C:\Users\Orakul Grey\.gemini\antigravity\brain\94dd6a04-54e7-4e8c-9551-224cace4f85f")

PROJECT_ID = "7d9a2a67-9cd2-4a79-932e-717d2e29257f"
PROXY_URL = "http://127.0.0.1:7890"
PROFILE_DIR = Path(r"C:\Users\Orakul Grey\AppData\Local\ffroliva\gflow-cli\profile_default")

OPTION3_BEATS: List[Dict[str, Any]] = [
    {
        "id": 1,
        "title": "Scene 1: Wide Arena Boss Clash (frames 001-004)",
        "duration_sec": 9.96,
        "frames": 239,
        "refs": ["knight_lucas_in_monitor.png"],
        "prompt": (
            "Make me a video in a 16:9 aspect ratio: Hand-painted Fortiche Production Arcane 2.5D animation (DOMAIN 2). "
            "Extreme wide-angle cinematic shot of the shattered gothic Cathedral Throne Hall. Adult blonde Knight Lucas MacGregor "
            "in dark battered steel plate armor with deep monster claw gouges, holding his compact iron-rimmed round buckler shield "
            "on his left arm and weathered steel broadsword in his right hand, charges boldly across the ruined marble floor. "
            "Ahead of him, a colossal monstrous Shadow Boss looms amidst swirling dark violet abyssal energy, shattered stone pillars, "
            "and moonlight streaming through high broken stained-glass windows. Dynamic tracking camera pushing forward into the arena. "
            "Strictly zero streamer face, zero modern bedroom."
        ),
        "negative_prompt": (
            "streamer, webcam talking head, modern bedroom, human face talking to camera, 2D anime card, smiling, "
            "speech bubbles, text overlays, clean parade armor, distorted weapons, cartoon morphing"
        ),
    },
    {
        "id": 2,
        "title": "Scene 2: Low-Angle Shield Block & Sparks (frames 005-008)",
        "duration_sec": 9.96,
        "frames": 239,
        "refs": ["knight_lucas_in_monitor.png"],
        "prompt": (
            "Make me a video in a 16:9 aspect ratio: Hand-painted Fortiche Production Arcane 2.5D animation matching the exact blonde knight from the attached reference image (thick golden-blonde hair, handsome adult knight in dark steel plate armor). Dynamic low-angle combat shot inside the dark gothic Cathedral as blonde Knight Lucas braces his round iron-rimmed buckler shield against a massive dark-violet tentacle strike from the Shadow Boss, showering bright orange sparks across his shield as he counter-slashes with his steel broadsword. Strictly blonde hair matching reference, never bald or old."
        ),
        "negative_prompt": (
            "streamer face, webcam, bedroom, modern desk, smiling, looking at camera, speech bubbles, blurry textures, "
            "extra limbs, clean pristine armor, cartoon morphing, bald, gray hair, old man, wrinkled face"
        ),
    },
    {
        "id": 3,
        "title": "Scene 3: Decisive Final Strike to CLEAR! Fanfare (frames 009-012)",
        "duration_sec": 10.00,
        "frames": 240,
        "refs": ["knight_lucas_in_monitor.png", "streamer_room_environment.png"],
        "prompt": (
            "Make me a video in a 16:9 aspect ratio: Stylized Fortiche Arcane 2.5D animation transitioning to CRT game victory fanfare. "
            "Sweeping dynamic camera follows Knight Lucas delivering a soaring upward broadsword cleave straight through the colossal boss, "
            "causing the monster to erupt into a dazzling shockwave of golden light and dissolving dark particles. The blinding golden "
            "radiance rapidly transitions into the glowing curved dual flat monitors at the dark streamer gaming desk, displaying the "
            "triumphant golden runic victory text 'CLEAR! Congratulations!' across the screen. Cinematic camera push-in toward the "
            "glowing gaming screens, strictly zero streamer face animation, zero talking head."
        ),
        "negative_prompt": (
            "streamer face, webcam talking head, streamer screaming, distorted mouth, turning head, rear monitors behind chair, "
            "speech bubbles, cartoon morphing"
        ),
    },
    {
        "id": 4,
        "title": "Scene 4: Rectangular Desk Dual Monitors & Stream Setup (frames 013-016)",
        "duration_sec": 9.96,
        "frames": 239,
        "refs": ["streamer_room_environment.png"],
        "prompt": (
            "Make me a video in a 16:9 aspect ratio: Hand-painted Fortiche Production Arcane 2.5D animation matching the exact dark bedroom and rectangular gaming desk from the attached reference image. Slow cinematic camera push-in toward the dual flat monitors displaying the golden victory screen on the left monitor and dark chat panel on the right monitor, with the glowing mechanical keyboard and 3-ring RGB PC tower on the right under the desk. Strictly keep the exact room layout from the reference image with zero floating text overlays in the air."
        ),
        "negative_prompt": (
            "streamer face, talking head webcam, human head morphing, rear glowing screens behind chair, floating headphones, "
            "distorted hands, speech bubbles, floating text, floating letters, gibberish words, donapation, donatije"
        ),
    },
]


def resolve_ffmpeg_exe() -> str:
    found = shutil.which("ffmpeg")
    return found if found else imageio_ffmpeg.get_ffmpeg_exe()


def get_video_duration(video_path: Path) -> float:
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        return 0.0
    fps = cap.get(cv2.CAP_PROP_FPS) or 24.0
    frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
    cap.release()
    return frames / fps if fps > 0 else 0.0


def standardize_to_720p_silent(raw_mp4: Path, final_mp4: Path, target_dur: float = 10.0, target_frames: int = 240) -> Path:
    """Normalize clip to 1280x720 24fps CFR H.264 yuv420p with strictly zero audio (-an)."""
    ffmpeg_exe = resolve_ffmpeg_exe()
    tmp_out = final_mp4.with_suffix(".std.tmp.mp4")
    raw_dur = get_video_duration(raw_mp4)
    if raw_dur <= 0.2:
        raw_dur = 8.0
    pts_factor = (target_frames / 24.0 + 0.1) / raw_dur
    vf = (
        f"scale=1280:720:force_original_aspect_ratio=decrease,"
        f"pad=1280:720:(ow-iw)/2:(oh-ih)/2:black,"
        f"setpts={pts_factor:.6f}*PTS,fps=24"
    )
    cmd = [
        ffmpeg_exe,
        "-y",
        "-i",
        str(raw_mp4),
        "-vf",
        vf,
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-r",
        "24",
        "-frames:v",
        str(target_frames),
        "-crf",
        "18",
        "-preset",
        "fast",
        "-an",
        "-movflags",
        "+faststart",
        str(tmp_out),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=120)
    if proc.returncode == 0 and tmp_out.is_file() and tmp_out.stat().st_size > 20_000:
        if final_mp4.is_file():
            final_mp4.unlink()
        tmp_out.rename(final_mp4)
        return final_mp4
    raise RuntimeError(f"720p silent standardization failed: {proc.stderr[-400:]}")


async def switch_to_videos_tab(page: Any) -> None:
    vid_nav = page.locator("flow-project-nav-list *:has(mat-icon:text-is('videocam'))").last
    if await vid_nav.count() > 0:
        try:
            await vid_nav.click(timeout=5000)
            await asyncio.sleep(2.5)
        except Exception:
            pass


async def attach_ingredient_file(page: Any, file_path: Path) -> None:
    add_btn = page.locator("button.add-menu-trigger").last
    await add_btn.click(timeout=8000)
    await asyncio.sleep(1.5)
    upload_btn = page.locator("button.sidebar-upload-btn").first
    async with page.expect_file_chooser(timeout=15000) as fc_info:
        await upload_btn.click(timeout=8000)
    chooser = await fc_info.value
    uniq_name = f"{file_path.stem}_{uuid.uuid4().hex[:6]}.png"
    await chooser.set_files({"name": uniq_name, "mimeType": "image/png", "buffer": file_path.read_bytes()})
    await asyncio.sleep(4.5)
    detail_add = page.locator("button.detail-add-to-prompt-btn:not([disabled])").first
    try:
        await detail_add.wait_for(state="visible", timeout=20000)
        await detail_add.click(timeout=5000)
        await asyncio.sleep(2.5)
    except Exception as exc:
        print(f"    [WARN] detail_add fallback for {file_path.name}: {exc}", flush=True)
        await page.keyboard.press("Escape")
        await asyncio.sleep(1.0)


async def await_generated_video(page: Any, baseline_keys: set[str], timeout_s: float = 360.0) -> Tuple[str, str]:
    from gflow_cli.api.transports.agent_only_composer import (
        FINISHED_VIDEO_TILE,
        LIVE_GATE,
        _VIDEO_JS,
    )
    t0 = time.monotonic()
    deadline = t0 + timeout_s
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

        if pending > 0:
            started = True

        new_idx = -1
        new_key = ""
        for idx, item in enumerate(finished):
            k = item.get("video") or item.get("img") or ""
            if k and k not in baseline_keys:
                new_idx = idx
                new_key = k

        if (started or new_idx >= 0) and pending == 0 and new_idx >= 0 and new_key:
            tile = page.locator(FINISHED_VIDEO_TILE).nth(new_idx)
            await tile.hover(timeout=5000)
            await asyncio.sleep(2.0)
            vid_src = await page.evaluate(
                """(idx) => {
                const tiles = document.querySelectorAll('flow-video-tile:not(:has(flow-pending-tile))');
                const tile = tiles[idx];
                const vid = tile ? tile.querySelector('video') : null;
                return vid ? (vid.currentSrc || vid.src || '') : '';
            }""",
                new_idx,
            )
            await page.mouse.move(0, 0)
            if vid_src:
                token = new_key.split("/asb/")[-1].split("=")[0].split("?")[0] if "/asb/" in new_key else "clip"
                return f"flow_asb_{token[:24]}", vid_src

        if (time.monotonic() - t0) > 12.0:
            panel_tail = (await page.locator("flow-agent-panel").inner_text())[-320:]
            if "\u0427\u0442\u043e-\u0442\u043e \u043f\u043e\u0448\u043b\u043e \u043d\u0435 \u0442\u0430\u043a" in panel_tail or "Something went wrong" in panel_tail:
                raise RuntimeError("Google Flow returned 'Something went wrong' error in agent panel.")

        await asyncio.sleep(2.0)

    raise TimeoutError(f"Timed out after {timeout_s}s waiting for video generation in Google Flow.")




def parse_cli_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate Episode 1 Option 3 Boss Battle Scenes in Google Flow")
    parser.add_argument("--force", action="store_true", default=False, help="Force fresh regeneration")
    parser.add_argument("--model", choices=["veo-fast", "veo-lite", "omni-flash"], default="veo-fast", help="Flow video model")
    parser.add_argument("--segment", type=int, choices=range(1, 5), default=None, help="Target specific segment (1..4)")
    parser.add_argument("--use-flow", action="store_true", default=True, help="Strict Google Flow execution (default: True)")
    parser.add_argument("--no-flow", dest="use_flow", action="store_false", help="Disable Flow generation (strictly prohibited)")
    return parser.parse_args()


async def generate_option3_segments(force: bool = False, use_flow: bool = True, model_name: str = "veo-fast", target_seg: Optional[int] = None) -> List[Path]:
    if not use_flow:
        raise ValueError("Option 3 requires genuine Google Flow generation; local fallback is prohibited.")

    SEGMENTS_DIR.mkdir(parents=True, exist_ok=True)
    target_beats = [b for b in OPTION3_BEATS if b["id"] == target_seg] if target_seg else OPTION3_BEATS
    rendered: List[Path] = []

    from gflow_cli.api.client import FlowApiClient
    from gflow_cli.api.transports.agent_only_composer import (
        EDITOR,
        SUBMIT,
        AgentOnlyComposer,
        _VIDEO_JS,
        download_video,
    )
    from gflow_cli.api.transports.migrated_composer import ASPECT_LIGATURE, VIDEO_MODEL_MENU_MATCHERS
    from gflow_cli.api.video import Aspect as VideoAspect, VideoModel

    os.environ["GFLOW_CLI_BROWSER_PROXY"] = PROXY_URL
    os.environ["HTTPS_PROXY"] = PROXY_URL
    os.environ["HTTP_PROXY"] = PROXY_URL
    os.environ["GFLOW_CLI_FLOW_HOST"] = "flow.google.com"
    os.environ["GFLOW_CLI_AGENT_CONFIRM"] = "never"
    os.environ["GFLOW_CLI_BROWSER_WINDOW_POSITION"] = "-30000,-30000"
    os.environ["GFLOW_CLI_UPDATE_CHECK"] = "0"

    model_map = {
        "veo-fast": VideoModel.VEO_3_1_FAST,
        "veo-lite": VideoModel.VEO_3_1_LITE,
        "omni-flash": VideoModel.OMNI_FLASH,
    }
    selected_model = model_map.get(model_name, VideoModel.VEO_3_1_FAST)

    for beat in target_beats:
        seg_id = beat["id"]
        out_p = SEGMENTS_DIR / f"segment_{seg_id:02d}.mp4"
        if not force and out_p.is_file() and out_p.stat().st_size > 100_000:
            print(f"[Option 3] Reusing verified Segment {seg_id:02d}: {out_p.name} ({out_p.stat().st_size // 1024} KB)", flush=True)
            rendered.append(out_p)
            continue

        flow_success = False
        last_exc: Optional[Exception] = None

        for attempt in range(1, 4):
            try:
                print(f"[Option 3 Flow] Rendering Segment {seg_id:02d} in Google Flow (attempt {attempt}/3, model {model_name})...", flush=True)
                async with FlowApiClient(PROFILE_DIR) as client:
                    page = client._page
                    composer = AgentOnlyComposer()
                    await page.goto(f"https://flow.google.com/project/{PROJECT_ID}", wait_until="domcontentloaded", timeout=60000)
                    await asyncio.sleep(6.5)
                    await switch_to_videos_tab(page)

                    new_btn = page.locator("button.header-action:has(mat-icon:text-is('edit_square'))").first
                    if await new_btn.count() > 0 and await new_btn.is_visible():
                        await new_btn.click(timeout=5000)
                        await asyncio.sleep(2.0)

                    await page.keyboard.press("Escape")
                    await asyncio.sleep(0.5)
                    await composer.apply_defaults(
                        page,
                        section="video",
                        aspect_ligature=ASPECT_LIGATURE[VideoAspect.LANDSCAPE],
                        count=1,
                        model=VIDEO_MODEL_MENU_MATCHERS[selected_model],
                        confirm="never",
                    )

                    for r_name in beat["refs"]:
                        rp = CONCEPTS_DIR / r_name
                        if rp.is_file():
                            print(f"  Attaching concept sheet: {rp.name}", flush=True)
                            await attach_ingredient_file(page, rp)

                    await switch_to_videos_tab(page)
                    base_state = await page.evaluate(_VIDEO_JS)
                    base_keys = {
                        (t.get("video") or t.get("img") or "")
                        for t in base_state.get("finished", [])
                        if (t.get("video") or t.get("img"))
                    }

                    editor = page.locator(EDITOR).last
                    await editor.click(timeout=5000)
                    await page.keyboard.press("ControlOrMeta+a")
                    await page.keyboard.press("Delete")
                    await editor.type(str(beat["prompt"]), delay=8)
                    await asyncio.sleep(1.0)
                    await page.locator(SUBMIT).last.click(timeout=5000)
                    print(f"  Submitted Segment {seg_id:02d} prompt to Flow. Awaiting video...", flush=True)

                    v_uuid, v_src = await await_generated_video(page, base_keys, timeout_s=400.0)
                    raw_mp4 = SEGMENTS_DIR / f"segment_{seg_id:02d}.raw.mp4"

                    async def _save(_u: str, body: bytes) -> Path:
                        raw_mp4.write_bytes(body)
                        return raw_mp4

                    await download_video(page, v_src, v_uuid, _save)
                    standardize_to_720p_silent(raw_mp4, out_p, target_dur=beat["duration_sec"], target_frames=beat["frames"])
                    if raw_mp4.is_file():
                        raw_mp4.unlink()
                    if LEGACY_SEGMENTS_DIR.is_dir():
                        shutil.copy2(out_p, LEGACY_SEGMENTS_DIR / out_p.name)
                    flow_success = True
                    print(f"  -> Flow Success: Saved {out_p.name} ({out_p.stat().st_size // 1024} KB, 720p silent CFR)", flush=True)
                    rendered.append(out_p)
                    break
            except Exception as exc:
                last_exc = exc
                print(f"  [WARN] Segment {seg_id:02d} attempt {attempt} failed: {exc}", flush=True)
                if attempt < 3:
                    await asyncio.sleep(5.0)

        if not flow_success:
            raise RuntimeError(f"Google Flow failed to render Segment {seg_id:02d} after 3 attempts: {last_exc}")

    return rendered


def main() -> int:
    args = parse_cli_args()
    rendered = asyncio.run(generate_option3_segments(force=args.force, use_flow=args.use_flow, model_name=args.model, target_seg=args.segment))
    print(f"Successfully rendered {len(rendered)} genuine Option 3 Flow segments.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
