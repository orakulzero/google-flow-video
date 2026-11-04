"""Generate Episode 1 (8 legacy scenes or 120-shot 3-Act Stage 0 manifest) of 'Tyrant of the Tower Defense Game' in Google Flow using Omni 1.1 Flash."""

from __future__ import annotations

import argparse
import asyncio
import os
from pathlib import Path
import sys
import time
from typing import Optional

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

try:
    from gflow_cli.api.client import FlowApiClient
    from gflow_cli.api.transports.agent_only_composer import (
        EDITOR,
        LIVE_GATE,
        SUBMIT,
        AgentOnlyComposer,
        _Run,
        download_video,
    )
    from gflow_cli.api.transports.migrated_composer import ASPECT_LIGATURE, VIDEO_MODEL_MENU_MATCHERS
    from gflow_cli.api.video import Aspect as VideoAspect, VideoModel
except ImportError:
    FlowApiClient = None  # type: ignore[assignment]
    AgentOnlyComposer = None  # type: ignore[assignment]
    EDITOR = LIVE_GATE = SUBMIT = ""
    _Run = download_video = None  # type: ignore[assignment]
    ASPECT_LIGATURE = {}
    VIDEO_MODEL_MENU_MATCHERS = {}
    VideoAspect = VideoModel = None  # type: ignore[assignment]

from src.flow_repo_adaptations import SceneRenderCache
from src.ttd_storyboard import ShotManifestEntry, load_ep01_3act_manifest

os.environ.setdefault("GFLOW_CLI_FLOW_HOST", "flow.google.com")
os.environ.setdefault("GFLOW_CLI_AGENT_CONFIRM", "never")
os.environ.setdefault("GFLOW_CLI_BROWSER_WINDOW_POSITION", "-30000,-30000")
os.environ.setdefault("GFLOW_CLI_UPDATE_CHECK", "0")

CANON_DIR = Path("output/ttd_arcane_characters/episode1_canon")
SHEETS_DIR = CANON_DIR / "arcane_sheets"
SCENES_DIR = CANON_DIR / "scenes_manhwa"
OUT_DIR = Path("output/ttd_ep01_omni_flash")
CLIPS_DIR = OUT_DIR / "clips"

STYLE_DIRECTIVE = (
    "Make me a video in a 16:9 aspect ratio: Hand-painted 2.5D/3D animation in the style of Fortiche Production "
    "Arcane. Use the attached Arcane character turnaround sheet for the exact painterly character design and colors, "
    "and use the attached manhwa frame for the scene composition and action. IMPORTANT: Fullscreen cinematic 16:9 "
    "shot with NO comic panel borders, NO split screens, and NO speech bubbles or text overlays."
)

EP01_OMNI_SCENES = [
    (
        "scene_01",
        "ep01_ash_gamer_arcane.jpg",
        "scene_01_gamer_clear.jpg",
        (
            f"{STYLE_DIRECTIVE} Scene: In a dark room lit by a glowing ultrawide PC monitor, the exhausted black-haired "
            "gamer in a light-blue hoodie and headset pumps his fists as golden victory runes flash on the screen, then "
            "a blinding vortex of golden-blue light erupts from the monitor and pulls him in. Cinematic camera push-in, "
            "dramatic electronic hum and magical whoosh."
        ),
    ),
    (
        "scene_02",
        "ep01_ash_commander_arcane.jpg",
        "scene_03_ash_awakening.jpg",
        (
            f"{STYLE_DIRECTIVE} Scene: Third Prince Ash Everblack in his black-and-gold Imperial Commander uniform and "
            "crimson cape gasps awake on the burning stone ramparts of the Forward Base as glowing emerald-green acid "
            "artillery shells explode against the battlements around him. Ash wipes blood from his cheek, looking around "
            "in shock. Explosions, roaring fire, and medieval battle cries."
        ),
    ),
    (
        "scene_03",
        "ep01_black_spider_arcane.jpg",
        "scene_05_spider_jaws.jpg",
        (
            f"{STYLE_DIRECTIVE} Scene: A colossal terrifying Black Spider monster with jagged black chitinous armor, "
            "clustered glowing red eyes, and neon-green toxic venom dripping from its mandibles leaps onto the stone "
            "fortress wall, towering over the camera and lunging forward with a monstrous screech."
        ),
    ),
    (
        "scene_04",
        "ep01_lucas_knight_arcane.jpg",
        "scene_06b_lucas_hero.jpg",
        (
            f"{STYLE_DIRECTIVE} Scene: Medium-full shot of heroic blonde vanguard knight Lucas MacGregor in the "
            "foreground wearing his silver-and-dark-steel plate armor and white-and-blue cape, swinging his glowing "
            "golden broadsword in a blazing arc that bisects the giant black spider behind him amid golden sparks and "
            "emerald venom mist. Focus on Lucas MacGregor's face, blonde hair, and silver armor."
        ),
    ),
    (
        "scene_05",
        "ep01_lily_flameskin_arcane.jpg",
        "scene_10_inverted_traits.jpg",
        (
            f"{STYLE_DIRECTIVE} Scene: Inside the torchlit stone war room, red-haired fire mage Lily in her white tunic, "
            "brown leather corset vest, and red hooded cloak dodges a sudden dagger test slash from Ash; a fiery golden-red "
            "aura of Flame Skin erupts around her body as she glares with fierce determination."
        ),
    ),
    (
        "scene_06",
        "ep01_demian_priest_arcane.jpg",
        "scene_09_guard_party.jpg",
        (
            f"{STYLE_DIRECTIVE} Scene: Young priest Demian with tousled brown hair, round wire-rimmed glasses, and a "
            "black-and-gold priest cassock stands alongside scarred shield-fighter Ken in dark plate armor; Demian "
            "adjusts his round glasses as his eyes ignite with supernatural white-gold sniper focus."
        ),
    ),
    (
        "scene_07",
        "ep01_ash_commander_arcane.jpg",
        "ep01_mana_cannon_arcane.jpg",
        (
            f"{STYLE_DIRECTIVE} Scene: At fiery dawn atop the Forward Base fortress wall, Prince Ash Everblack with his "
            "messy black hair, amber eyes, and black-and-gold Imperial Commander uniform with crimson cape (from the first "
            "attached sheet) raises his sword in command beside the ornate white-and-gold Ancient Mana Cannon and two "
            "armored artillery soldiers (from the second attached sheet) as the cannon overloads with cyan mana lightning."
        ),
    ),
    (
        "scene_08",
        "ep01_mana_cannon_arcane.jpg",
        "scene_12_mana_cannon_queen.jpg",
        (
            f"{STYLE_DIRECTIVE} Scene: The overloaded white-and-gold Ancient Mana Cannon on the fortress rampart fires "
            "a colossal blinding beam of cyan hextech mana energy across the battlefield, obliterating the giant Black "
            "Spider Queen in her distant nest in a massive shockwave of blue light and emerald sparks."
        ),
    ),
]


async def attach_ingredient_file(page, file_path: Path) -> None:
    await page.locator("button.add-menu-trigger").last.click(timeout=8000)
    await asyncio.sleep(1.5)
    upload_btn = page.locator("button.sidebar-upload-btn").first
    async with page.expect_file_chooser(timeout=15000) as fc_info:
        await upload_btn.click(timeout=8000)
    chooser = await fc_info.value
    await chooser.set_files(str(file_path))
    await asyncio.sleep(5.0)
    if await page.locator("mat-dialog-container button").count() > 0:
        await page.locator("mat-dialog-container button").last.click(timeout=8000)
        await asyncio.sleep(3.5)
    enabled_add = page.locator("button.detail-add-to-prompt-btn:not([disabled])").first
    try:
        await enabled_add.wait_for(state="visible", timeout=25000)
        await enabled_add.click(timeout=8000)
        await asyncio.sleep(2.0)
    except Exception:
        await page.keyboard.press("Escape")
        await asyncio.sleep(1.0)


def resolve_flow_browser_profile() -> Path:
    """Resolve Flow browser profile path across Linux and Windows without hardcoded user paths."""
    env_prof = os.environ.get("GFLOW_CLI_PROFILE_DIR", "").strip()
    if env_prof:
        return Path(env_prof)
    local_app = os.environ.get("LOCALAPPDATA", "").strip()
    if local_app:
        return Path(local_app) / "ffroliva" / "gflow-cli" / "profile_default"
    return Path.home() / ".local" / "share" / "gflow-cli" / "profile_default"


def resolve_shot_start_frame(
    shot: ShotManifestEntry,
    cache: SceneRenderCache,
    clips_dir: Path = CLIPS_DIR,
    root_dir: Path = ROOT_DIR,
    prev_clip_path: Optional[Path] = None,
) -> Path:
    """
    Resolve start frame image for a shot according to its chain_mode:
    - HARD_ANCHOR_RESET (chain_depth == 0): uses curated artwork `shot.start_frame_anchor`.
    - FRAME_CHAIN_LAST_TO_FIRST (1 <= chain_depth <= 3): extracts and caches the final frame
      of the preceding shot clip via `SceneRenderCache.extract_and_cache_last_frame()`.
    """
    if shot.chain_mode == "HARD_ANCHOR_RESET" or shot.chain_depth == 0:
        p = Path(shot.start_frame_anchor)
        return p if p.is_absolute() else (root_dir / p)

    shot_num = int(shot.shot_id.split("-")[-1])
    prev_shot_id = f"SHOT-{shot_num - 1:03d}"
    cached_last = cache.cache_dir / f"{prev_shot_id}_last.jpg"
    if cached_last.is_file() and cached_last.stat().st_size > 100:
        return cached_last

    source_clip = prev_clip_path or (clips_dir / f"{prev_shot_id}_omni.mp4")
    if source_clip.is_file():
        return cache.extract_and_cache_last_frame(prev_shot_id, source_clip)

    # Fallback if running in dry-run without rendered clip
    p = Path(shot.start_frame_anchor)
    return p if p.is_absolute() else (root_dir / p)


def ensure_canonical_anchor_images(root_dir: Path = ROOT_DIR) -> None:
    """Populate canonical 1280x720 anchor frames and turnaround sheets from staged 720p Flow clips if missing."""
    import shutil
    import subprocess

    ff = shutil.which("ffmpeg") or str(Path.home() / ".local" / "bin" / "ffmpeg")
    shots_dir = root_dir / "assets" / "ep01_shots"
    if not shots_dir.is_dir():
        return

    scenes_dir = root_dir / SCENES_DIR
    sheets_dir = root_dir / SHEETS_DIR
    scenes_dir.mkdir(parents=True, exist_ok=True)
    sheets_dir.mkdir(parents=True, exist_ok=True)

    mapping = [
        (scenes_dir / "scene_01_gamer_clear.jpg", "ttd_ep01_shot_05_clip_720p.mp4", "1.5"),
        (scenes_dir / "scene_03_ash_awakening.jpg", "ttd_ep01_shot_07_clip_720p.mp4", "1.5"),
        (scenes_dir / "scene_05_spider_jaws.jpg", "ttd_ep01_shot_10_clip_720p.mp4", "2.0"),
        (scenes_dir / "scene_06b_lucas_hero.jpg", "ttd_ep01_shot_04_clip_720p.mp4", "1.8"),
        (scenes_dir / "scene_09_guard_party.jpg", "ttd_ep01_shot_08_clip_720p.mp4", "1.5"),
        (scenes_dir / "scene_10_inverted_traits.jpg", "ttd_ep01_shot_09_clip_720p.mp4", "1.5"),
        (scenes_dir / "scene_12_mana_cannon_queen.jpg", "ttd_ep01_shot_12_clip_720p.mp4", "2.0"),
        (sheets_dir / "ep01_ash_gamer_arcane.jpg", "ttd_ep01_shot_01_clip_720p.mp4", "1.2"),
        (sheets_dir / "ep01_ash_commander_arcane.jpg", "ttd_ep01_shot_07_clip_720p.mp4", "2.2"),
        (sheets_dir / "ep01_black_spider_arcane.jpg", "ttd_ep01_shot_10_clip_720p.mp4", "2.8"),
        (sheets_dir / "ep01_lucas_knight_arcane.jpg", "ttd_ep01_shot_03_clip_720p.mp4", "1.8"),
        (sheets_dir / "ep01_demian_priest_arcane.jpg", "ttd_ep01_shot_08_clip_720p.mp4", "2.2"),
        (sheets_dir / "ep01_lily_flameskin_arcane.jpg", "ttd_ep01_shot_09_clip_720p.mp4", "2.2"),
        (sheets_dir / "ep01_mana_cannon_arcane.jpg", "ttd_ep01_shot_11_clip_720p.mp4", "2.0"),
    ]
    for dst_img, src_clip_name, ts in mapping:
        src_clip = shots_dir / src_clip_name
        if not dst_img.is_file() and src_clip.is_file():
            subprocess.run(
                [ff, "-y", "-ss", ts, "-i", str(src_clip), "-frames:v", "1", "-q:v", "2", str(dst_img)],
                check=False,
                capture_output=True,
                timeout=20,
            )


PROJECT_URL = "https://flow.google.com/project/7d9a2a67-9cd2-4a79-932e-717d2e29257f"


def _log(msg: str) -> None:
    """Print unbuffered to stdout (for UI task logs) and append to flow_batch.log."""
    import time as _time
    stamp = _time.strftime("%H:%M:%S")
    line = f"[{stamp}] {msg}"
    print(line, flush=True)
    try:
        log_file = ROOT_DIR / "output" / "ttd_ep01_omni_flash" / "flow_batch.log"
        log_file.parent.mkdir(parents=True, exist_ok=True)
        with log_file.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
            fh.flush()
    except Exception:
        pass


def sanitize_flow_clip_cuts(clip_path: Path, target_dur: float = 8.0) -> None:
    """Detect any mid-clip camera cut or style break in a 10s Flow clip and trim/retime before the cut."""
    import shutil
    import subprocess
    import cv2

    if not clip_path.is_file():
        return
    cap = cv2.VideoCapture(str(clip_path))
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 24.0)
    fc = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    if fc < int(fps * 4.5):
        cap.release()
        return

    ref_idx = int(fps * 0.75)
    cap.set(cv2.CAP_PROP_POS_FRAMES, ref_idx)
    ok_ref, ref_frame = cap.read()
    if not ok_ref or ref_frame is None:
        cap.release()
        return

    ref_hsv = cv2.cvtColor(ref_frame, cv2.COLOR_BGR2HSV)
    ref_hist = cv2.calcHist([ref_hsv], [0, 1], None, [32, 32], [0, 180, 0, 256])
    cv2.normalize(ref_hist, ref_hist, 0, 1, cv2.NORM_MINMAX)

    cut_sec: Optional[float] = None
    step = max(1, int(fps * 0.25))
    for idx in range(int(fps * 2.5), fc - 2, step):
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ok_c, cand = cap.read()
        if not ok_c or cand is None:
            continue
        cand_hsv = cv2.cvtColor(cand, cv2.COLOR_BGR2HSV)
        cand_hist = cv2.calcHist([cand_hsv], [0, 1], None, [32, 32], [0, 180, 0, 256])
        cv2.normalize(cand_hist, cand_hist, 0, 1, cv2.NORM_MINMAX)
        corr = float(cv2.compareHist(ref_hist, cand_hist, cv2.HISTCMP_CORREL))
        if corr < 0.25:
            t_s = idx / fps
            if t_s >= 4.0:
                cut_sec = max(3.8, t_s - 0.25)
                break
    cap.release()

    if cut_sec is not None and cut_sec < target_dur:
        ff = shutil.which("ffmpeg") or str(Path.home() / ".local" / "bin" / "ffmpeg")
        stretch = round(target_dur / cut_sec, 4)
        atempo_val = max(0.5, min(1.0, round(1.0 / stretch, 4)))
        tmp_out = clip_path.with_suffix(".sanitized.mp4")
        proc = subprocess.run(
            [
                ff,
                "-y",
                "-t",
                f"{cut_sec:.2f}",
                "-i",
                str(clip_path),
                "-vf",
                f"setpts={stretch:.4f}*PTS,fps=24",
                "-af",
                f"atempo={atempo_val:.4f}",
                "-t",
                f"{target_dur:.2f}",
                "-c:v",
                "libx264",
                "-preset",
                "fast",
                "-crf",
                "18",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                "-movflags",
                "+faststart",
                str(tmp_out),
            ],
            check=False,
            capture_output=True,
            timeout=60,
        )
        if proc.returncode == 0 and tmp_out.is_file() and tmp_out.stat().st_size > 1_000_000:
            tmp_out.replace(clip_path)
        elif tmp_out.is_file():
            tmp_out.unlink(missing_ok=True)


async def render_act_from_manifest(
    act_id: int,
    manifest_path: Path = ROOT_DIR / "config" / "ep01_3act_manifest.json",
    clips_dir: Path = CLIPS_DIR,
    dry_run: bool = False,
    max_shots: Optional[int] = None,
) -> list[Path]:
    """Render all shots for a specific Act (1, 2, or 3) from ep01_3act_manifest.json using real Google Flow Omni 1.1 Flash."""
    manifest = load_ep01_3act_manifest(manifest_path)
    target_acts = [a for a in manifest.acts if a.act_id == act_id]
    if not target_acts:
        raise ValueError(f"Act {act_id} not found in {manifest_path}")
    act = target_acts[0]
    shots_to_process = act.shots[:max_shots] if max_shots is not None else act.shots
    clips_dir.mkdir(parents=True, exist_ok=True)
    cache = SceneRenderCache()
    rendered_paths: list[Path] = []

    if dry_run:
        for shot in shots_to_process:
            _ = resolve_shot_start_frame(shot, cache, clips_dir=clips_dir)
            rendered_paths.append(clips_dir / f"{shot.shot_id}_omni.mp4")
        return rendered_paths

    ensure_canonical_anchor_images(ROOT_DIR)
    prof = resolve_flow_browser_profile()

    client_cls = FlowApiClient
    if client_cls is None or not hasattr(client_cls, "__aenter__"):
        from src.cloud_cdp_flow_client import CloudCDPFlowClient, load_flow_cookies_payload
        cookie_payload = load_flow_cookies_payload()
        if not cookie_payload.get("cookies"):
            raise RuntimeError(
                "No authenticated Google Flow session cookies found in 04_flow_session_state/flow_session_cookies.json. "
                "Run `python scripts/export_flow_session_bundle.py` on Windows first."
            )
        client_cls = CloudCDPFlowClient

    from veo_arcane_style.src.flow_conditioning import (
        EDITOR_LOCATOR,
        SUBMIT_LOCATOR,
        VIDEO_STATE_JS,
        attach_frame_ingredient,
        await_flow_video,
        clear_prompt_box_ingredients,
        save_native_video,
        switch_to_videos_tab,
    )

    _log(f"=== Starting Act {act_id} ({len(shots_to_process)} shots) in Google Flow Omni 1.1 Flash ===")
    async with client_cls(prof) as client:
        page = client._page
        assert page is not None
        await page.goto(PROJECT_URL, wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(6.0)
        if "/about" in str(page.url) or "accounts.google.com" in str(page.url):
            raise RuntimeError(
                f"Google Flow redirected to unauthenticated URL ({page.url}). "
                "Run `python scripts/export_flow_session_bundle.py` to refresh flow_session_cookies.json."
            )
        if hasattr(client, "persist_rotated_cookies"):
            await client.persist_rotated_cookies()

        for idx, shot in enumerate(shots_to_process, 1):
            out_mp4 = clips_dir / f"{shot.shot_id}_omni.mp4"
            if out_mp4.is_file() and out_mp4.stat().st_size > 2_000_000:
                cache.extract_and_cache_last_frame(shot.shot_id, out_mp4)
                rendered_paths.append(out_mp4)
                _log(
                    f"[{idx}/{len(shots_to_process)}] Reusing verified {out_mp4.name} ({out_mp4.stat().st_size // 1024} KB)"
                )
                continue

            start_img = resolve_shot_start_frame(shot, cache, clips_dir=clips_dir)
            canonical_ref = start_img
            if shot.character_sheet_refs:
                cand_sheet = ROOT_DIR / SHEETS_DIR / shot.character_sheet_refs[0]
                if cand_sheet.is_file():
                    canonical_ref = cand_sheet

            for attempt in range(1, 6):
                try:
                    if attempt > 1:
                        await page.goto(PROJECT_URL, wait_until="domcontentloaded", timeout=60000)
                        await asyncio.sleep(6.0)
                    _log(
                        f"[{idx}/{len(shots_to_process)}] Submitting {shot.shot_id} (ref={canonical_ref.name}) [attempt {attempt}/5]..."
                    )
                    await switch_to_videos_tab(page)
                    await asyncio.sleep(1.5)
                    await clear_prompt_box_ingredients(page)

                    if canonical_ref.is_file():
                        await attach_frame_ingredient(page, canonical_ref.resolve())

                    state_before = await page.evaluate(VIDEO_STATE_JS)
                    baseline_keys: set[str] = set()
                    for item in (state_before or {}).get("finished", []):
                        for k in (item.get("video"), item.get("img"), item.get("uuid")):
                            if k:
                                baseline_keys.add(str(k))

                    editor = page.locator(EDITOR_LOCATOR).last
                    await editor.click(timeout=5000)
                    await editor.press_sequentially(shot.omni_visual_prompt, delay=4)
                    await asyncio.sleep(0.5)
                    await page.locator(SUBMIT_LOCATOR).last.click(timeout=5000)

                    vid_uuid, vid_src = await await_flow_video(page, baseline_keys, timeout_s=360.0)
                    await save_native_video(page, vid_src, vid_uuid, out_mp4)
                    sanitize_flow_clip_cuts(out_mp4, target_dur=shot.duration_sec)
                    cache.extract_and_cache_last_frame(shot.shot_id, out_mp4)
                    if hasattr(client, "persist_rotated_cookies"):
                        await client.persist_rotated_cookies()
                    rendered_paths.append(out_mp4)
                    _log(f"[Flow Omni 1.1 Flash] Rendered {shot.shot_id} -> {out_mp4.name} ({out_mp4.stat().st_size // 1024} KB)")
                    await asyncio.sleep(2.5)
                    break
                except Exception as exc:
                    _log(f"[WARN] {shot.shot_id} attempt {attempt}/5 failed: {exc}")
                    if attempt == 5:
                        raise
                    await asyncio.sleep(10.0 * attempt)

    return rendered_paths


async def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Render TTD Episode 1 via Omni 1.1 Flash")
    parser.add_argument("--act", type=int, choices=[1, 2, 3], default=None, help="Render specific Act (1..3) from 120-shot manifest")
    parser.add_argument("--all-acts", action="store_true", help="Render all 3 Acts (SHOT-001..SHOT-120) from 120-shot manifest")
    parser.add_argument("--max-shots", type=int, default=None, help="Limit number of shots per Act in this run")
    parser.add_argument("--manifest", type=Path, default=ROOT_DIR / "config" / "ep01_3act_manifest.json")
    parser.add_argument("--dry-run", action="store_true", help="Validate manifest & frame-chaining without launching browser")
    args = parser.parse_args(argv)

    if args.all_acts:
        total = 0
        for act_id in (1, 2, 3):
            paths = await render_act_from_manifest(
                act_id, manifest_path=args.manifest, dry_run=args.dry_run, max_shots=args.max_shots
            )
            print(f"Act {act_id}: rendered {len(paths)} shots", flush=True)
            total += len(paths)
        print(f"All 3 Acts complete: {total} shots rendered in {CLIPS_DIR}", flush=True)
        return 0

    if args.act is not None:
        paths = await render_act_from_manifest(
            args.act, manifest_path=args.manifest, dry_run=args.dry_run, max_shots=args.max_shots
        )
        print(f"Act {args.act}: prepared {len(paths)} shots", flush=True)
        return 0


    CLIPS_DIR.mkdir(parents=True, exist_ok=True)
    if args.dry_run or FlowApiClient is None:
        return 0

    prof = resolve_flow_browser_profile()
    async with FlowApiClient(prof) as client:
        page = client._page
        assert page is not None
        composer = AgentOnlyComposer()

        for idx, (scene_id, sheet_name, manhwa_name, directive) in enumerate(EP01_OMNI_SCENES, 1):
            out_mp4 = CLIPS_DIR / f"{scene_id}_omni.mp4"
            if out_mp4.is_file() and out_mp4.stat().st_size > 50_000:
                print(f"[{idx}/{len(EP01_OMNI_SCENES)}] Reusing existing {out_mp4.name} ({out_mp4.stat().st_size // 1024} KB)", flush=True)
                continue

            for attempt in range(1, 3):
                try:
                    print(f"[{idx}/{len(EP01_OMNI_SCENES)}] Rendering {scene_id} via Omni 1.1 Flash ({sheet_name} + {manhwa_name}) [attempt {attempt}]...", flush=True)
                    await page.goto(
                        "https://flow.google.com/project/7d9a2a67-9cd2-4a79-932e-717d2e29257f",
                        wait_until="domcontentloaded",
                        timeout=60000,
                    )
                    await asyncio.sleep(7.0)
                    new_session_btn = page.locator("button.header-action:has(mat-icon:text-is('edit_square'))").first
                    if await new_session_btn.count() > 0 and await new_session_btn.is_visible():
                        await new_session_btn.click(timeout=5000)
                        await asyncio.sleep(2.0)

                    await composer.apply_defaults(
                        page,
                        section="video",
                        aspect_ligature=ASPECT_LIGATURE[VideoAspect.LANDSCAPE],
                        count=1,
                        model=VIDEO_MODEL_MENU_MATCHERS[VideoModel.OMNI_FLASH],
                        confirm="never",
                    )

                    await attach_ingredient_file(page, SHEETS_DIR / sheet_name)
                    sec_p = (SCENES_DIR / manhwa_name) if (SCENES_DIR / manhwa_name).is_file() else (SHEETS_DIR / manhwa_name)
                    await attach_ingredient_file(page, sec_p)

                    baseline_gates = await page.locator(LIVE_GATE).count()
                    baseline, baseline_head = await composer._video_baseline(page)

                    editor = page.locator(EDITOR).last
                    await editor.click(timeout=5000)
                    await page.keyboard.press("ControlOrMeta+a")
                    await page.keyboard.press("Delete")
                    await page.keyboard.insert_text(directive)
                    await asyncio.sleep(0.5)
                    await page.locator(SUBMIT).last.click(timeout=5000)
                    print(f"  Submitted {scene_id} to Omni 1.1 Flash. Waiting for video tile...", flush=True)

                    budget_s = 360.0
                    run = _Run("video", budget_s, time.monotonic() + budget_s, baseline_gates, 1)
                    (media,) = await composer._await_video(page, run, 1, baseline, baseline_head, None)

                    async def _save_clip(_uuid: str, body: bytes) -> Path:
                        out_mp4.write_bytes(body)
                        return out_mp4

                    await download_video(page, media.src, media.uuid, _save_clip)
                    print(f"  -> SAVED {out_mp4.name} ({out_mp4.stat().st_size // 1024} KB, uuid={media.uuid})", flush=True)
                    break
                except Exception as exc:
                    print(f"  [WARN] {scene_id} attempt {attempt} failed: {exc}", flush=True)
                    await asyncio.sleep(4.0)

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

