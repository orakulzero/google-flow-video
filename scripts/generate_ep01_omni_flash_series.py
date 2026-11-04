"""Generate Episode 1 (8 scenes) of 'Tyrant of the Tower Defense Game' in Google Flow using Omni 1.1 Flash."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
import time

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

os.environ["GFLOW_CLI_BROWSER_PROXY"] = "http://127.0.0.1:7890"
os.environ["HTTPS_PROXY"] = "http://127.0.0.1:7890"
os.environ["HTTP_PROXY"] = "http://127.0.0.1:7890"
os.environ["GFLOW_CLI_FLOW_HOST"] = "flow.google.com"
os.environ["GFLOW_CLI_AGENT_CONFIRM"] = "never"
os.environ["GFLOW_CLI_BROWSER_WINDOW_POSITION"] = "-30000,-30000"
os.environ["GFLOW_CLI_UPDATE_CHECK"] = "0"

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


async def main() -> int:
    CLIPS_DIR.mkdir(parents=True, exist_ok=True)
    prof = Path(r"C:\Users\Orakul Grey\AppData\Local\ffroliva\gflow-cli\profile_default")

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
