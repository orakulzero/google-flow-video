#!/usr/bin/env python3
"""Generate the Episode 1 Opening Silent Video Sequence (frames 001..032) in Google Flow.

Anchors every segment on the 9 approved canonical Arcane concept art sheets in
output/canonical_arcane_concepts/ so room architecture, dual monitors, 3-ring RGB PC,
Streamer Ash, and adult Knight Lucas remain 100% consistent without detail drift.
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
import uuid

import cv2
import imageio_ffmpeg
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.flow_prompt_library import (
    PROLOGUE_MICRO_SHOTS,
    compose_flow_micro_shot_payload,
    get_micro_shot_by_id,
)

from gflow_cli.api.client import FlowApiClient
from gflow_cli.api.transports.agent_only_composer import (
    EDITOR,
    FINISHED_VIDEO_TILE,
    LIVE_GATE,
    SUBMIT,
    AgentOnlyComposer,
    _VIDEO_JS,
    download_video,
)
from gflow_cli.api.transports.migrated_composer import ASPECT_LIGATURE, VIDEO_MODEL_MENU_MATCHERS
from gflow_cli.api.video import Aspect as VideoAspect, VideoModel

TESTBENCH_DIR = Path(__file__).resolve().parent.parent
PROJECT_ID = "7d9a2a67-9cd2-4a79-932e-717d2e29257f"
PROXY_URL = "http://127.0.0.1:7890"
PROFILE_DIR = Path(r"C:\Users\Orakul Grey\AppData\Local\ffroliva\gflow-cli\profile_default")
CONCEPTS_DIR = TESTBENCH_DIR / "output" / "canonical_arcane_concepts"
OUT_DIR = TESTBENCH_DIR / "output" / "ttd_ep01_manga_transitions"
SEGMENTS_DIR = OUT_DIR / "segments_canon"
BRAIN_DIR = Path(r"C:\Users\Orakul Grey\.gemini\antigravity\brain\94dd6a04-54e7-4e8c-9551-224cace4f85f")


def build_lucas_void_end_keyframe() -> Path:
    """Create Flow-safe Boss Hall and terminal frame_031 void keyframes around adult Lucas."""
    src_path = CONCEPTS_DIR / "knight_lucas_solitary_back.png"
    flow_safe_path = CONCEPTS_DIR / "knight_lucas_solitary_back_flow.png"
    out_path = CONCEPTS_DIR / "knight_lucas_void_end.png"
    src = cv2.imread(str(src_path))
    if src is None:
        raise FileNotFoundError(f"Missing {src_path}")
    h, w = src.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)

    d_body = ((xx - w * 0.455) / (w * 0.085)) ** 2 + ((yy - h * 0.50) / (h * 0.38)) ** 2
    d_shield = ((xx - w * 0.395) / (w * 0.045)) ** 2 + ((yy - h * 0.34) / (h * 0.12)) ** 2
    d_sword = ((xx - w * 0.525) / (w * 0.055)) ** 2 + ((yy - h * 0.44) / (h * 0.12)) ** 2
    lucas_keep = np.clip(1.35 - np.minimum(np.minimum(d_body, d_shield), d_sword), 0.0, 1.0) ** 1.6

    pillar_keep = np.clip((h * 0.39 - yy) / (h * 0.08), 0.0, 1.0)
    keep_flow = np.maximum(lucas_keep, pillar_keep)[:, :, np.newaxis]
    stone_shadow = np.full_like(src, (24, 18, 14))
    flow_img = (
        src.astype(np.float32) * keep_flow + stone_shadow.astype(np.float32) * (1.0 - keep_flow) * 0.4
    ).clip(0, 255).astype(np.uint8)
    cv2.imwrite(str(flow_safe_path), flow_img)

    knee_fade = np.clip((h * 0.86 - yy) / (h * 0.12), 0.0, 1.0)
    void_mask = (lucas_keep * knee_fade)[:, :, np.newaxis]
    void_img = (flow_img.astype(np.float32) * void_mask).clip(0, 255).astype(np.uint8)
    cv2.imwrite(str(out_path), void_img)
    return out_path


CANON_BEATS: list[dict[str, object]] = [
    {
        "id": 1,
        "title": "01. Monitor 'CLEAR!' Fanfare -> Streamer Ash Ecstatic Victory (frames 001-004)",
        "micro_shots": ["MS-01A", "MS-01B", "MS-01C"],
        "gaze_lock": "STREAMER FACE-LOCKED: Head yaw strictly <= 5 deg, facial plane aligned with monitor/webcam, specular cyan catchlights in pupils",
        "style_domain": "Retro CRT UI -> Fortiche Arcane 2.5D",
        "refs": ["streamer_ash_webcam_pov_anchor.png"],
        "prompt": (
            "Make me a video in a 16:9 aspect ratio: Hand-painted Fortiche Production Arcane 2.5D animation. "
            "Webcam POV matching the exact character face and bedroom lighting in the attached reference image. "
            "Streamer Ash in his light-blue pullover hoodie and black gaming headset sits in his gaming chair facing the webcam. "
            "Restrained triumphant acting: confident fist-pump and warm proud smile, identical face and calm gaze to the reference image. "
            "Behind him are only dark bedroom curtains with cyan monitor reflection. Strictly zero rear monitors behind chair, "
            "zero screaming grimace, head yaw strictly 0 deg, eyes locked forward into the webcam."
        ),
        "negative_prompt": (
            "screaming grimace, distorted mouth, wide open screaming mouth, rear glowing monitors, monitors behind back, "
            "second screen behind chair, turning head away, side glance, looking away, profile view of face, head twisting, "
            "wandering eyes, asymmetrical headset, floating headphones, speech bubbles, cartoon morphing, lateral drift"
        ),
    },
    {
        "id": 2,
        "title": "02. 'Save the Empire' Box Art -> Ash Proudly Addressing Stream (frames 005-009)",
        "micro_shots": ["MS-02A", "MS-02B"],
        "gaze_lock": "STREAMER WEBCAM GAZE PINNED: Eyes dead-center into webcam lens, index finger point, head yaw 0 deg",
        "style_domain": "Dark Fantasy Lore -> Fortiche Arcane 2.5D Animation",
        "refs": ["streamer_ash_front_face_anchor.png"],
        "prompt": (
            "Make me a video in a 16:9 aspect ratio: Stylized 2D/2.5D hand-painted Fortiche Arcane animation "
            "(strictly animated 2D/2.5D illustration style matching the attached reference image, never live-action "
            "or photorealistic). 2D animated Streamer Ash (young man with messy black hair, wearing his light-blue pullover "
            "hoodie and black over-ear headset) sits in his gaming chair at his desk, dark curtains behind him with zero rear monitors, "
            "smiling and gesturing proudly as he talks to his stream. STREAMER WEBCAM GAZE PINNED: Head yaw strictly 0 deg, "
            "eyes locked dead-center into the 4K webcam lens with confident half-smirk, right index finger pointing squarely forward. "
            "Strictly zero monitors behind chair."
        ),
        "negative_prompt": (
            "rear glowing monitors, monitors behind back, second screen behind chair, turning head away, looking away from webcam, "
            "side glance, distorted hand, extra fingers, loose headset, floating headphones, rear monitors"
        ),
    },
    {
        "id": 3,
        "title": "03. Rectangular Desk Closeup & 'FOXY 300,000 KRW' Stream Alert (frames 011-016)",
        "micro_shots": ["MS-03A", "MS-03B", "MS-04A"],
        "gaze_lock": "STREAMER FACE-LOCKED: Symmetrical posture, locked tripod framing, zero lateral drift",
        "style_domain": "Fortiche Arcane 2.5D / Modern Stream HUD Overlay",
        "refs": ["stream_overlay_chat_donation.png"],
        "prompt": (
            "Make me a video in a 16:9 aspect ratio: Stylized 2D/2.5D hand-painted Fortiche Arcane animation "
            "matching the attached reference image. Close-up of the dark-purple livestream broadcast interface "
            "(strictly zero platform brand logos) showing blonde knight Lucas standing inside the gothic Cathedral "
            "Throne Hall on the main gameplay canvas, 2D animated Streamer Ash in his light-blue hoodie cheering in "
            "the lower-left webcam overlay, the golden 'FOXY donated 300,000 KRW ($300)!' alert banner glowing at "
            "the top center, and the right-hand STREAM CHAT column scrolling with excited viewer messages. "
            "STREAMER FACE-LOCKED: Symmetrical posture, locked tripod framing, zero lateral drift, hands clasped in front of chest."
        ),
        "negative_prompt": (
            "turning head away, side glance, looking away, asymmetrical headset, detached headphones, distorted hands, extra fingers, rear monitors, speech bubbles"
        ),
    },
    {
        "id": 4,
        "title": "04. Viewer Comment on Fallen Priestess -> Ash's Somber Reflection (frames 018-021)",
        "micro_shots": ["MS-04B", "MS-04C", "MS-05A", "MS-05C"],
        "gaze_lock": "STREAMER FACE-LOCKED (PITCH DOWN ONLY): Head bowed down 10 deg along pitch axis, head yaw 0 deg, eyes on keyboard and chat HUD",
        "style_domain": "Fortiche Arcane 2.5D Chiaroscuro",
        "refs": ["streamer_ash_webcam_pov_anchor.png"],
        "prompt": (
            "Make me a video in a 16:9 aspect ratio: Hand-painted Fortiche Production Arcane 2.5D animation. "
            "Medium close-up webcam POV matching the attached reference image. Streamer Ash in his light-blue pullover "
            "hoodie and black headset sits facing the camera against the dark curtain wall (zero rear monitors, zero stream HUD boxes). "
            "His confident smile gently softens into a quiet, wistful, somber reflection as he looks at his screen. "
            "STREAMER FACE-LOCKED (PITCH DOWN ONLY): Head slightly bowed down 10 degrees, head yaw strictly 0 deg, "
            "calm expressive eyes, zero lateral head turn, zero HUD overlay boxes, clean cinematic character shot."
        ),
        "negative_prompt": (
            "stream hud boxes, chat window, donation banner, text overlay, ui boxes, rear glowing monitors, monitors behind back, "
            "second screen behind chair, turning head away, side glance, looking away, twisted neck, distorted fingers, "
            "floating headset, rear monitors, speech bubbles"
        ),
    },
    {
        "id": 5,
        "title": "05. PC Monitor Push-In: Gothic Throne Hall & Adult Knight Lucas (frames 022-025)",
        "micro_shots": ["MS-06A"],
        "gaze_lock": "Tactical 2D UI asset on monitor (No human subject in room)",
        "style_domain": "DOMAIN 1: 2D Tactical Game Card (Monitor UI)",
        "refs": ["knight_lucas_portrait.png", "game_save_the_empire_screen.png"],
        "prompt": (
            "Make me a video in a 16:9 aspect ratio: Stylized 2D tactical game illustration and Fortiche Arcane 2.5D animation. "
            "Camera pushes directly into the PC monitor window ('Save the Empire' frame from first attached reference) "
            "revealing the digital 2D tactical RPG character reward card (DOMAIN 1): clean stylized 2D anime bust portrait "
            "of blonde vanguard knight Lucas in polished silver armor with golden laurel wreath and 'STAGE MVP - Lucas [SSR]' "
            "banner, framed within the gothic Cathedral Throne Hall window with circular stained-glass rose window and translucent blue UI. "
            "Flat screen lighting, zero 3D gore, strictly stylized digital UI asset on monitor."
        ),
        "negative_prompt": (
            "3D CGI impasto, realistic human skin, dirty battered armor, blood, rain, battlefield background, streamer face, speech bubbles, blurry text"
        ),
    },
    {
        "id": 6,
        "title": "06. Boss Hall Floor Pan: Adult Lucas Over the Fallen Princess of the Lake (frames 026-028)",
        "micro_shots": ["MS-06B", "MS-07A"],
        "gaze_lock": "LUCAS REAR ORIENTATION LOCK: Head bowed, eyes unseen, back squarely to camera",
        "style_domain": "DOMAIN 2: Fortiche Production Arcane Cinematic 3D",
        "refs": ["knight_lucas_solitary_back_flow.png"],
        "prompt": (
            "Make me a video in a 16:9 aspect ratio: Hand-painted Fortiche Production Arcane 2.5D animation (DOMAIN 2). "
            "Inside the dark gothic Cathedral Throne Hall (matching the attached reference), the camera pans "
            "smoothly across the shattered stone steps to the tall, broad-shouldered adult knight Lucas MacGregor standing "
            "with his back turned (wearing dark-steel plate armor with deep monster claw gouges, no cape, compact round buckler "
            "shield on his left arm, weathered steel broadsword lowered in his right hand). "
            "LUCAS REAR ORIENTATION LOCK: Head bowed, broad muscular shoulders hunched forward, back turned squarely to camera."
        ),
        "negative_prompt": (
            "front view of face, turning head around, modern room, streamer, 2D anime card, smiling, bright cheery lighting, speech bubbles, clean parade armor"
        ),
    },
    {
        "id": 7,
        "title": "07. Boss Hall Fades to Pitch-Black Void Leaving Only Lucas's Lonely Back (frames 029-032)",
        "micro_shots": ["MS-07B", "MS-07C"],
        "gaze_lock": "LUCAS ICONIC LONELY BACK IN VOID: Motionless rear stance, pure pitch-black void (#000000)",
        "style_domain": "DOMAIN 2: Fortiche Arcane Cinematic 3D in Pure Pitch-Black Void",
        "refs": ["knight_lucas_void_end.png"],
        "prompt": (
            "Make me a video in a 16:9 aspect ratio: Hand-painted Fortiche Production Arcane 2.5D animation (DOMAIN 2). "
            "Starting from the dark gothic Cathedral Throne Hall, the surrounding stone pillars, floor, and "
            "background slowly darken and dissolve completely into a pure pitch-black void (#000000) matching the "
            "attached reference image, until ONLY the solitary back of adult knight Lucas (weathered steel plate "
            "armor, compact round buckler on left arm, lowered broadsword in right hand, no cape) remains standing "
            "alone in total darkness. Cold cyan volumetric rim light tracing outer contours of silver armor, pure black background."
        ),
        "negative_prompt": (
            "turning head around, front view of face, side profile, ambient background light, gray fog, floor lines, pillars, modern room, speech bubbles, bright colors"
        ),
    },
]


def resolve_ffmpeg_exe() -> str:
    found = shutil.which("ffmpeg")
    return found if found else imageio_ffmpeg.get_ffmpeg_exe()


def get_video_duration(video_path: Path) -> float:
    """Probe duration in seconds using OpenCV."""
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        return 0.0
    fps = cap.get(cv2.CAP_PROP_FPS) or 24.0
    frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
    cap.release()
    return frames / fps if fps > 0 else 0.0


def standardize_to_720p_silent(raw_mp4: Path, final_mp4: Path) -> Path:
    """Normalize any generated clip to 1280x720 24fps CFR (10.00s) H.264 with strictly 0 audio (-an)."""
    ffmpeg_exe = resolve_ffmpeg_exe()
    tmp_out = final_mp4.with_suffix(".std.tmp.mp4")
    raw_dur = get_video_duration(raw_mp4)
    if raw_dur <= 0.5:
        raw_dur = 5.0
    pts_factor = 10.0 / raw_dur
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
        "-t",
        "10.0",
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


async def switch_to_videos_tab(page) -> None:
    """Switch the left navigation menu to 'Videos' so _VIDEO_JS observes all finished video tiles."""
    vid_nav = page.locator("flow-project-nav-list *:has(mat-icon:text-is('videocam'))").last
    if await vid_nav.count() > 0:
        try:
            await vid_nav.click(timeout=5000)
            await asyncio.sleep(2.5)
        except Exception:
            pass


async def attach_ingredient_file(page, file_path: Path) -> None:
    """Attach a canonical Arcane concept art PNG into the Flow composer using a unique upload name."""
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


async def await_generated_video(page, baseline_keys: set[str], timeout_s: float = 360.0) -> tuple[str, str]:
    """Wait for Google Flow Omni Flash to finish video generation and return (uuid, video_src)."""
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


def assemble_master_silent_video(segment_paths: list[Path], out_mp4: Path) -> Path:
    """Concatenate all 7 silent 720p segments into a unified faststart MP4 with 0 audio streams."""
    ffmpeg_exe = resolve_ffmpeg_exe()
    concat_txt = out_mp4.parent / "concat_canon_segments.txt"
    lines = [f"file '{p.resolve().as_posix()}'" for p in segment_paths]
    concat_txt.write_text("\n".join(lines) + "\n", encoding="utf-8")
    tmp_out = out_mp4.with_suffix(".tmp.mp4")
    cmd = [
        ffmpeg_exe,
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(concat_txt),
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-r",
        "24",
        "-crf",
        "18",
        "-preset",
        "fast",
        "-an",
        "-movflags",
        "+faststart",
        str(tmp_out),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=180)
    if proc.returncode != 0 or not tmp_out.is_file() or tmp_out.stat().st_size < 100_000:
        raise RuntimeError(f"Master assembly failed: {proc.stderr[-400:]}")
    if out_mp4.is_file():
        out_mp4.unlink()
    tmp_out.rename(out_mp4)
    return out_mp4


def build_video_contact_sheet(segment_paths: list[Path] | Path, out_png: Path) -> Path:
    """Render high-resolution 2x4 visual contact sheet matching canonical geometry (1360x1825)."""
    cols, rows = 2, 4
    tw, th = 660, 425
    margin = 20
    top_header_h = 85
    canvas_w = margin * 2 + cols * tw
    canvas_h = margin * 2 + top_header_h + rows * th

    sheet = Image.new("RGB", (canvas_w, canvas_h), (14, 16, 22))
    draw = ImageDraw.Draw(sheet)

    def _get_font(name: str, size: int) -> ImageFont.ImageFont:
        for p in [f"C:/Windows/Fonts/{name}.ttf", "C:/Windows/Fonts/segoeuib.ttf", "C:/Windows/Fonts/arialbd.ttf", "C:/Windows/Fonts/arial.ttf"]:
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                continue
        return ImageFont.load_default()

    font_title = _get_font("segoeuib", 24)
    font_sub = _get_font("segoeui", 13)
    font_card_title = _get_font("segoeuib", 14)
    font_badge = _get_font("consola", 12)

    draw.text((margin + 6, margin + 4), "EPISODE 1: MANGA FLOW TRANSITIONS - VISUAL CONTACT SHEET", fill=(245, 205, 110), font=font_title)
    draw.text(
        (margin + 6, margin + 38),
        "Tyrant of the Tower Defense Game | 7-Segment Google Flow Omni Flash Transitions | 1280x720 24fps | Silent (-an) | 69.80s Master Arc",
        fill=(170, 185, 210),
        font=font_sub,
    )
    draw.line([(margin + 6, margin + 68), (canvas_w - margin - 6, margin + 68)], fill=(45, 52, 72), width=1)

    if isinstance(segment_paths, Path) and segment_paths.is_dir():
        segs = [segment_paths / f"segment_{i:02d}.mp4" for i in range(1, 8)]
    elif isinstance(segment_paths, list):
        segs = segment_paths
    else:
        segs = [SEGMENTS_DIR / f"segment_{i:02d}.mp4" for i in range(1, 8)]

    card_meta = [
        {"title": "Scene 1: Game Clear Fanfare to Victory Celebration", "badge": "Segment 01 | 00:00.00 - 00:09.96 | Anchors: Frame 001 -> 002", "frame_idx": 119, "seg_idx": 0, "is_climax": False},
        {"title": "Scene 2: Gamer Victory to Streamer Chat Reaction", "badge": "Segment 02 | 00:09.96 - 00:19.96 | Anchors: Frame 002 -> 004", "frame_idx": 120, "seg_idx": 1, "is_climax": False},
        {"title": "Scene 3: Streamer Reaction to 'Save the Empire' Title Card", "badge": "Segment 03 | 00:19.96 - 00:29.92 | Anchors: Frame 004 -> 005", "frame_idx": 119, "seg_idx": 2, "is_climax": False},
        {"title": "Scene 4: Title Card to Tactical Defense Strategy Map", "badge": "Segment 04 | 00:29.92 - 00:39.92 | Anchors: Frame 005 -> 009", "frame_idx": 120, "seg_idx": 3, "is_climax": False},
        {"title": "Scene 5: Strategy Map to Streamer Broadcast Workstation", "badge": "Segment 05 | 00:39.92 - 00:49.88 | Anchors: Frame 009 -> 014", "frame_idx": 119, "seg_idx": 4, "is_climax": False},
        {"title": "Scene 6: Broadcast Workstation to Battlefield Ramparts", "badge": "Segment 06 | 00:49.88 - 00:59.84 | Anchors: Frame 014 -> 023", "frame_idx": 119, "seg_idx": 5, "is_climax": False},
        {"title": "Scene 7A: Rampart Ruins Dissolving into Darkness", "badge": "Segment 07 | 00:59.84 - 01:05.00 | Anchors: Frame 023 -> Void", "frame_idx": 108, "seg_idx": 6, "is_climax": False},
        {"title": "Scene 7B Climax: Dark Void & Lucas Solitary Back", "badge": "Terminal Climax | 01:05.00 - 01:09.80 | Anchors: Void -> Frame 026", "frame_idx": 238, "seg_idx": 6, "is_climax": True},
    ]

    for i, meta in enumerate(card_meta):
        r, c = divmod(i, cols)
        x0 = margin + c * tw
        y0 = margin + top_header_h + r * th

        box_rect = [x0 + 8, y0 + 6, x0 + tw - 8, y0 + th - 6]
        border_col = (240, 198, 105) if meta["is_climax"] else (45, 52, 72)
        card_fill = (32, 24, 20) if meta["is_climax"] else (24, 28, 40)
        draw.rectangle(box_rect, fill=card_fill, outline=border_col, width=2 if meta["is_climax"] else 1)

        hdr_fill = (52, 38, 26) if meta["is_climax"] else (32, 38, 54)
        draw.rectangle([x0 + 8, y0 + 6, x0 + tw - 8, y0 + 44], fill=hdr_fill)

        title_col = (255, 215, 120) if meta["is_climax"] else (240, 240, 248)
        draw.text((x0 + 18, y0 + 10), meta["title"][:58], fill=title_col, font=font_card_title)
        draw.text((x0 + 18, y0 + 28), meta["badge"], fill=(120, 195, 255), font=font_badge)

        seg_file = segs[meta["seg_idx"]]
        cap = cv2.VideoCapture(str(seg_file))
        cap.set(cv2.CAP_PROP_POS_FRAMES, meta["frame_idx"])
        ret, frame_bgr = cap.read()
        cap.release()

        if ret and frame_bgr is not None:
            frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
            im = Image.fromarray(frame_rgb)
            im = im.resize((640, 360), Image.Resampling.LANCZOS)
            thumb_x = x0 + (tw - 640) // 2
            thumb_y = y0 + 48
            sheet.paste(im, (thumb_x, thumb_y))
            if meta["is_climax"]:
                draw.rectangle([thumb_x - 1, thumb_y - 1, thumb_x + 640, thumb_y + 360], outline=(240, 198, 105), width=2)

    out_png.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out_png, quality=94)
    return out_png


def parse_cli_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate Episode 1 Canonical Arcane Flow Video in Google Flow")
    parser.add_argument("--force", action="store_true", default=True, help="Force fresh regeneration, ignoring cache")
    parser.add_argument("--no-force", dest="force", action="store_false", help="Allow reusing existing segments if present")
    parser.add_argument("--model", choices=["veo-fast", "veo-lite", "omni-flash"], default="veo-fast", help="Google Flow video model")
    parser.add_argument("--segment", type=int, choices=range(1, 8), default=None, help="Target specific segment (1..7)")
    return parser.parse_args()


async def main(cli_args: argparse.Namespace | None = None) -> int:
    args = cli_args if cli_args is not None else parse_cli_args()

    os.environ["GFLOW_CLI_BROWSER_PROXY"] = PROXY_URL
    os.environ["HTTPS_PROXY"] = PROXY_URL
    os.environ["HTTP_PROXY"] = PROXY_URL
    os.environ["GFLOW_CLI_FLOW_HOST"] = "flow.google.com"
    os.environ["GFLOW_CLI_AGENT_CONFIRM"] = "never"
    os.environ["GFLOW_CLI_BROWSER_WINDOW_POSITION"] = "-30000,-30000"
    os.environ["GFLOW_CLI_UPDATE_CHECK"] = "0"

    SEGMENTS_DIR.mkdir(parents=True, exist_ok=True)
    build_lucas_void_end_keyframe()

    MODEL_CHOICE_MAP = {
        "veo-fast": VideoModel.VEO_3_1_FAST,
        "veo-lite": VideoModel.VEO_3_1_LITE,
        "omni-flash": VideoModel.OMNI_FLASH,
    }
    selected_model = MODEL_CHOICE_MAP.get(args.model, VideoModel.VEO_3_1_FAST)

    target_beats = [b for b in CANON_BEATS if b["id"] == args.segment] if args.segment else CANON_BEATS

    segment_paths: list[Path] = []
    for beat in target_beats:
        seg_id = int(beat["id"])
        out_seg = SEGMENTS_DIR / f"segment_{seg_id:02d}.mp4"
        if not args.force and out_seg.is_file() and out_seg.stat().st_size > 50_000:
            print(f"[Beat {seg_id}/7] Reusing verified {out_seg.name} ({out_seg.stat().st_size // 1024} KB)", flush=True)
            segment_paths.append(out_seg)
            continue

        for attempt in range(1, 4):
            try:
                print(f"[Beat {seg_id}/7] Rendering {beat['title']} (attempt {attempt}, model {args.model})...", flush=True)
                async with FlowApiClient(PROFILE_DIR) as client:
                    page = client._page
                    assert page is not None
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

                    for ref_name in beat["refs"]:
                        ref_path = CONCEPTS_DIR / str(ref_name)
                        print(f"  Attaching canonical sheet: {ref_path.name}", flush=True)
                        await attach_ingredient_file(page, ref_path)

                    await switch_to_videos_tab(page)
                    baseline_state = await page.evaluate(_VIDEO_JS)
                    baseline_keys = {
                        (t.get("video") or t.get("img") or "")
                        for t in baseline_state.get("finished", [])
                        if (t.get("video") or t.get("img"))
                    }

                    editor = page.locator(EDITOR).last
                    await editor.click(timeout=5000)
                    await page.keyboard.press("ControlOrMeta+a")
                    await page.keyboard.press("Delete")
                    await editor.type(str(beat["prompt"]), delay=8)
                    await asyncio.sleep(1.0)
                    await page.locator(SUBMIT).last.click(timeout=5000)
                    print(f"  Submitted Beat {seg_id} to Google Flow (baseline tiles={len(baseline_keys)}). Awaiting video...", flush=True)

                    budget_s = 400.0
                    video_uuid, vid_src = await await_generated_video(page, baseline_keys, timeout_s=budget_s)

                    raw_mp4 = SEGMENTS_DIR / f"segment_{seg_id:02d}.raw.mp4"

                    async def _save(_uuid: str, body: bytes) -> Path:
                        raw_mp4.write_bytes(body)
                        return raw_mp4

                    await download_video(page, vid_src, video_uuid, _save)
                    standardize_to_720p_silent(raw_mp4, out_seg)
                    if raw_mp4.is_file():
                        raw_mp4.unlink()
                    print(f"  -> SAVED {out_seg.name} ({out_seg.stat().st_size // 1024} KB, silent 720p)", flush=True)
                    segment_paths.append(out_seg)
                await asyncio.sleep(2.0)
                break
            except Exception as exc:
                print(f"  [WARN] Beat {seg_id} attempt {attempt} failed: {exc}", flush=True)
                if attempt == 3:
                    raise
                await asyncio.sleep(5.0)

    all_segments = [SEGMENTS_DIR / f"segment_{i:02d}.mp4" for i in range(1, 8)]
    if not all(s.is_file() for s in all_segments):
        print(f"Rendered segment(s). Missing {sum(1 for s in all_segments if not s.is_file())}/7 segments for assembly.", flush=True)
        return 0
    segment_paths = all_segments

    master_mp4 = OUT_DIR / "ttd_episode_01_silent_720p.mp4"
    assemble_master_silent_video(segment_paths, master_mp4)
    contact_png = OUT_DIR / "ep01_manga_transitions_contact_sheet.png"
    build_video_contact_sheet(segment_paths, contact_png)

    cap_m = cv2.VideoCapture(str(master_mp4))
    m_fps = float(cap_m.get(cv2.CAP_PROP_FPS) or 24.0)
    m_frames = int(cap_m.get(cv2.CAP_PROP_FRAME_COUNT))
    m_duration = round(m_frames / m_fps, 2) if m_fps > 0 else 70.0
    cap_m.release()

    def _sha256(p: Path) -> str:
        h = hashlib.sha256()
        with open(p, "rb") as f:
            while chunk := f.read(65536):
                h.update(chunk)
            return h.hexdigest()

    manifest_path = OUT_DIR / "manifest.json"
    manifest_data = {
        "project": "Tyrant of the Tower Defense Game - Episode 1 Manga Flow Transitions",
        "master_video": master_mp4.name,
        "master_sha256": _sha256(master_mp4),
        "master_bytes": master_mp4.stat().st_size,
        "resolution": "1280x720",
        "fps": 24.0,
        "frame_count": m_frames,
        "duration_seconds": m_duration,
        "audio_streams": 0,
        "silent": True,
        "faststart": True,
        "codec": "h264",
        "pix_fmt": "yuv420p",
        "crf": 18,
        "preset": "fast",
        "delivery_timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "contact_sheet": {
            "filename": contact_png.name,
            "dimensions": "1360x1825",
            "sha256": _sha256(contact_png),
            "bytes": contact_png.stat().st_size,
            "card_count": 8,
            "terminal_climax": "Segment 7 Frame 238 Lucas Solitary Back in Dark Void",
        },
        "segments": [
            {
                "segment_index": idx,
                "filename": f"segment_{idx:02d}.mp4",
                "sha256": _sha256(seg_p),
                "bytes": seg_p.stat().st_size,
                "title": CANON_BEATS[idx - 1]["title"],
                "badge": f"Segment {idx:02d} | Anchors: Beat {idx}",
                "micro_shots": CANON_BEATS[idx - 1].get("micro_shots", []),
                "gaze_lock": CANON_BEATS[idx - 1].get("gaze_lock", ""),
                "style_domain": CANON_BEATS[idx - 1].get("style_domain", ""),
            }
            for idx, seg_p in enumerate(segment_paths, 1)
        ],
        "mirrored_brain_directory": str(BRAIN_DIR),
    }
    manifest_path.write_text(json.dumps(manifest_data, indent=2), encoding="utf-8")

    # Copy to brain directory and canonical segments folder
    shutil.copy2(master_mp4, BRAIN_DIR / "ttd_episode_01_silent_720p.mp4")
    shutil.copy2(contact_png, BRAIN_DIR / "ep01_manga_transitions_contact_sheet.png")
    shutil.copy2(manifest_path, BRAIN_DIR / "manifest.json")
    for idx, seg_p in enumerate(segment_paths, 1):
        shutil.copy2(seg_p, OUT_DIR / "segments" / f"segment_{idx:02d}.mp4")
        shutil.copy2(seg_p, BRAIN_DIR / f"segment_{idx:02d}.mp4")

    print(f"ALL 7 CANONICAL BEATS RENDERED & ASSEMBLED -> {master_mp4} ({master_mp4.stat().st_size // 1024} KB)", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
