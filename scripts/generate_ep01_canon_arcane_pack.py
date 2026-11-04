"""Curate Episode 1..3 manhwa frames (characters + 12 storyboard scenes) and generate Arcane sheets in Google Flow."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
import shutil
import time

from PIL import Image, ImageDraw, ImageFont

from gflow_cli.api.client import FlowApiClient
from gflow_cli.api.image import Aspect as ImageAspect, Model as ImageModel
from gflow_cli.api.transports.agent_only_composer import (
    EDITOR,
    IMAGE_BUDGET_S,
    IN_FLIGHT,
    LIVE_GATE,
    SUBMIT,
    AgentOnlyComposer,
    _full_size_src,
    _natural_size,
    _Run,
)
from gflow_cli.api.transports.migrated_composer import IMAGE_ASPECT_LIGATURE, IMAGE_MODEL_MENU_MATCHERS

os.environ["GFLOW_CLI_BROWSER_PROXY"] = "http://127.0.0.1:7890"
os.environ["HTTPS_PROXY"] = "http://127.0.0.1:7890"
os.environ["HTTP_PROXY"] = "http://127.0.0.1:7890"
os.environ["GFLOW_CLI_FLOW_HOST"] = "flow.google.com"
os.environ["GFLOW_CLI_AGENT_CONFIRM"] = "never"
os.environ["GFLOW_CLI_BROWSER_WINDOW_POSITION"] = "-30000,-30000"
os.environ["GFLOW_CLI_UPDATE_CHECK"] = "0"

FRAMES_ROOT = Path("output/ttd_arcane_characters/episode1_frames")
CANON_DIR = Path("output/ttd_arcane_characters/episode1_canon")
SHEETS_DIR = CANON_DIR / "arcane_sheets"
SCENES_DIR = CANON_DIR / "scenes_manhwa"
BRAIN_DIR = Path(r"C:\Users\Orakul Grey\.gemini\antigravity\brain\94dd6a04-54e7-4e8c-9551-224cace4f85f")

PREFIX = (
    "Make me a picture in a 16:9 aspect ratio: Based ONLY on the single attached reference manhwa frame from Episode 1, "
    "create a character concept turnaround sheet in the hand-painted brushwork style of Fortiche Production Arcane. "
    "Strictly preserve the exact hairstyle, hair color, eye color, glasses/facial details, and Episode 1 outfit/armor "
    "shown in the attached reference image, translated into Fortiche Arcane's 2.5D/3D painterly oil and gouache "
    "brushwork with dramatic chiaroscuro rim lighting, showing close-up face portrait, 3/4 view, and full-body "
    "turnaround on a clean parchment background. No text, no speech bubbles, no labels."
)

# Exact character appearances from Episode 1..3 (Stage 0 Tutorial at the Forward Base)
EP01_CHARACTER_JOBS = [
    (
        "ep01/frame_003.jpg",
        "ep01_ash_gamer_arcane.jpg",
        "01. Эш (Пролог Гл.1) — Геймер в голубом худи до переноса в игру",
        (
            f"{PREFIX} Character: Young Korean male gamer from Episode 1 with messy black hair, dark eyes, wearing a "
            "light-blue pullover hoodie and gaming headset at his PC desk (human gamer ONLY — NO monsters, NO spiders, "
            "NO armor). Show close-up face portrait, 3/4 view, and full-body standing turnaround in the blue hoodie."
        ),
    ),
    (
        "ep01/frame_094.jpg",
        "ep01_ash_commander_arcane.jpg",
        "02. Эш Эверблэк (Гл.1–2) — Пробуждение на стене (Мундир принца)",
        f"{PREFIX} Character: Third Prince Commander Ash Everblack from Episode 1 with messy black hair, amber-brown eyes, battle soot/blood on cheek, wearing a black Imperial Commander coat with gold epaulets, gold aiguillette cord, high collar, and crimson-lined cape.",
    ),
    (
        "ep01/frame_193.jpg",
        "ep01_lucas_knight_arcane.jpg",
        "03. Лукас Макгрегор (Гл.1) — Рыцарь-телохранитель (Серебряный доспех)",
        f"{PREFIX} Character: Blonde guard knight Lucas MacGregor from Episode 1 with golden-blonde hair, golden-amber eyes, wearing silver-and-dark-steel layered plate armor with pauldrons, white-and-blue knight cape, and broadsword.",
    ),
    (
        "ep02/frame_129.jpg",
        "ep01_demian_priest_arcane.jpg",
        "04. Дэмиен (Гл.2–3) — Дебют: Жрец в круглых очках -> Снайпер",
        f"{PREFIX} Character: Young male priest Demian from Episode 2 with tousled brown hair, wearing large round wire-rimmed eyeglasses (spectacles), black priest cassock robe with white-and-gold clerical collar and trim (his exact Episode 2 debut before getting a sniper rifle).",
    ),
    (
        "ep02/frame_119.jpg",
        "ep01_lily_flameskin_arcane.jpg",
        "05. Лили (Гл.2–3) — Дебют: Маг огня в красном плаще («Огненная кожа»)",
        f"{PREFIX} Character: Young female fire mage Lily from Episode 2 with reddish-brown side-braided hair, warm brown eyes, wearing a red hooded cloak over a white belted tunic and brown leather corset waist-vest, holding a wooden mage staff.",
    ),
    (
        "ep02/frame_106.jpg",
        "ep01_ken_infiltrator_arcane.jpg",
        "06. Кен (Гл.2–3) — Дебют: Щитоносец со шрамом («Мелкий вор»)",
        f"{PREFIX} Character: Male guard party fighter Ken from Episode 2 with short spiky black hair, a diagonal scar across his cheek, fierce dark eyes, wearing dark gunmetal-steel plate armor with sword and shield.",
    ),
    (
        "ep03/frame_110.jpg",
        "ep01_mana_cannon_arcane.jpg",
        "07. Древняя Мана-Пушка и расчёт крепости (Гл.1–3)",
        (
            "Make me a picture in a 16:9 aspect ratio: Prop & Crew Concept Sheet in the hand-painted style of Fortiche "
            "Production Arcane, based directly on the attached Episode 3 manhwa frame: the ornate white-and-gold Ancient "
            "Mana Cannon artillery piece overflowing with glowing cyan hextech-like mana energy atop the stone fortress "
            "rampart, flanked by two helmeted Forward Base artillery soldiers in red tunics and steel breastplates. "
            "No text, no speech bubbles."
        ),
    ),
    (
        "ep01/frame_166.jpg",
        "ep01_black_spider_arcane.jpg",
        "08. Легион Чёрных Пауков и Паучья Королева (Гл.1–3, зелёный яд)",
        (
            "Make me a picture in a 16:9 aspect ratio: Creature Concept Turnaround Sheet in the hand-painted dark-fantasy "
            "style of Fortiche Production Arcane, based directly on the attached Episode 1 manhwa frame: colossal NON-HUMAN "
            "Black Spider Assault Monster & Queen with jagged black chitinous armor, glowing red eyes, and glowing toxic "
            "emerald-green venom dripping from its fangs and abdomen sacs (NO human body, NO human face). Show front, side, "
            "and attack pose on parchment background. No text, no labels."
        ),
    ),
]


# 12 sequential scenes of the Pilot Episode directly from Episodes 1..3 of the manhwa
EP01_STORYBOARD_SCENES = [
    ("ep01/frame_003.jpg", "scene_01_gamer_clear.jpg", "Сцена 01: Прохождение игры на Адской сложности"),
    ("ep01/frame_042.jpg", "scene_02_director_invite.jpg", "Сцена 02: Послание Директора Mr.A и перенос"),
    ("ep01/frame_094.jpg", "scene_03_ash_awakening.jpg", "Сцена 03: Пробуждение в теле принца Эша под обстрелом"),
    ("ep01/frame_149.jpg", "scene_04_spider_breach.jpg", "Сцена 04: Прорыв Чёрных Пауков на стену крепости"),
    ("ep01/frame_166.jpg", "scene_05_spider_jaws.jpg", "Сцена 05: Пасть паука-штурмовика над Эшем"),
    ("ep01/frame_180.jpg", "scene_06_lucas_rescue.jpg", "Сцена 06: Золотой рассекающий удар Лукаса Макгрегора"),
    ("ep01/frame_198.jpg", "scene_07_burning_fortress.jpg", "Сцена 07: Панорама осаждённого Передового Форта"),
    ("ep02/frame_076.jpg", "scene_08_system_tactics.jpg", "Сцена 08: Ночной анализ Системы (1000 пауков и Мана-пушка)"),
    ("ep02/frame_101.jpg", "scene_09_guard_party.jpg", "Сцена 09: Сбор личного отряда (Лили, Кен, Дэмиен)"),
    ("ep03/frame_014.jpg", "scene_10_inverted_traits.jpg", "Сцена 10: Пробуждение скрытых талантов (Лили — танк, Дэмиен — снайпер)"),
    ("ep03/frame_094.jpg", "scene_11_dawn_command.jpg", "Сцена 11: Рассвет 1 марта — Эш командует генеральной обороной"),
    ("ep03/frame_110.jpg", "scene_12_mana_cannon_queen.jpg", "Сцена 12: Перегрузка Древней Мана-Пушки и выстрел по Королеве"),
]


def build_storyboard_grid() -> Path:
    SCENES_DIR.mkdir(parents=True, exist_ok=True)
    cols, rows = 4, 3
    tw, th = 340, 420
    grid = Image.new("RGB", (cols * tw, 60 + rows * th), (14, 16, 22))
    draw = ImageDraw.Draw(grid)
    try:
        t_font = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", 22)
        l_font = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", 14)
    except Exception:
        t_font = l_font = ImageFont.load_default()

    draw.text((20, 16), "EPISODE 1 STORYBOARD: 12 SEQUENTIAL FRAMES DIRECTLY FROM MANHWA (CH 1-3)", fill=(240, 198, 105), font=t_font)
    for i, (src_rel, dst_name, title) in enumerate(EP01_STORYBOARD_SCENES):
        src_p = FRAMES_ROOT / src_rel
        dst_p = SCENES_DIR / dst_name
        shutil.copy2(src_p, dst_p)
        r, c = divmod(i, cols)
        x0, y0 = c * tw, 60 + r * th
        draw.rectangle([x0 + 4, y0 + 4, x0 + tw - 4, y0 + 30], fill=(28, 32, 46))
        draw.text((x0 + 10, y0 + 8), title[:42], fill=(240, 240, 248), font=l_font)
        im = Image.open(src_p).convert("RGB")
        im.thumbnail((tw - 16, th - 42), Image.Resampling.LANCZOS)
        grid.paste(im, (x0 + (tw - im.width) // 2, y0 + 34 + (th - 42 - im.height) // 2))

    out_grid = CANON_DIR / "ep01_storyboard_12scenes_grid.jpg"
    grid.save(out_grid, quality=92)
    shutil.copy2(out_grid, BRAIN_DIR / out_grid.name)
    print(f"Saved 12-scene Episode 1 storyboard grid -> {out_grid}", flush=True)
    return out_grid


async def start_fresh_agent_session(page, composer: AgentOnlyComposer) -> None:
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
        section="image",
        aspect_ligature=IMAGE_ASPECT_LIGATURE[ImageAspect.LANDSCAPE],
        count=1,
        model=IMAGE_MODEL_MENU_MATCHERS[ImageModel.GEM_PIX_2],
        confirm="never",
    )
    editor = page.locator(EDITOR).last
    await editor.click(timeout=5000)
    await page.keyboard.press("ControlOrMeta+a")
    await page.keyboard.press("Delete")


async def main() -> int:
    CANON_DIR.mkdir(parents=True, exist_ok=True)
    SHEETS_DIR.mkdir(parents=True, exist_ok=True)
    build_storyboard_grid()

    prof = Path(r"C:\Users\Orakul Grey\AppData\Local\ffroliva\gflow-cli\profile_default")
    async with FlowApiClient(prof) as client:
        page = client._page
        assert page is not None
        composer = AgentOnlyComposer()

        for idx, (ref_rel, out_name, label, directive) in enumerate(EP01_CHARACTER_JOBS, 1):
            ref_p = FRAMES_ROOT / ref_rel
            shutil.copy2(ref_p, CANON_DIR / f"ref_{idx:02d}_{Path(ref_rel).name}")
            out_p = SHEETS_DIR / out_name
            if out_p.is_file() and out_p.stat().st_size > 10000:
                print(f"[{idx}/{len(EP01_CHARACTER_JOBS)}] Reusing {out_name}", flush=True)
                shutil.copy2(out_p, BRAIN_DIR / out_name)
                continue

            print(f"[{idx}/{len(EP01_CHARACTER_JOBS)}] Generating {out_name} from {ref_rel}...", flush=True)
            await start_fresh_agent_session(page, composer)
            before_upload_uuids = set((await composer._media(page)).keys())

            await page.locator("button.add-menu-trigger").last.click(timeout=5000)
            await asyncio.sleep(1.5)
            upload_btn = page.locator("button.sidebar-upload-btn").first
            async with page.expect_file_chooser(timeout=10000) as fc_info:
                await upload_btn.click(timeout=5000)
            chooser = await fc_info.value
            await chooser.set_files(str(ref_p))
            await asyncio.sleep(4.5)

            if await page.locator("mat-dialog-container button").count() > 0:
                await page.locator("mat-dialog-container button").last.click(timeout=5000)
                await asyncio.sleep(3.5)

            add_to_prompt = page.locator("button.detail-add-to-prompt-btn")
            if await add_to_prompt.count() > 0 and await add_to_prompt.first.is_visible():
                await add_to_prompt.first.click(timeout=5000)
                await asyncio.sleep(2.5)

            pre_submit_uuids = before_upload_uuids | set((await composer._media(page)).keys())

            baseline_gates = await page.locator(LIVE_GATE).count()
            editor = page.locator(EDITOR).last
            await editor.click(timeout=5000)
            await page.keyboard.insert_text(directive)
            await asyncio.sleep(0.5)
            await page.locator(SUBMIT).last.click(timeout=5000)
            await asyncio.sleep(8.0)

            run = _Run("image", IMAGE_BUDGET_S, time.monotonic() + IMAGE_BUDGET_S, baseline_gates, 1)
            winner_src = None
            while time.monotonic() < run.deadline:
                if await composer._gate_turn(page, run):
                    continue
                in_flight = bool(await page.locator(IN_FLIGHT).count())
                cur_media = await composer._media(page)
                candidates = [m for u, m in cur_media.items() if u not in pre_submit_uuids]
                if candidates and not in_flight:
                    for cand in candidates:
                        full_u = _full_size_src(cand.src)
                        w, h = await _natural_size(page, full_u)
                        if w > h and w >= 1200:
                            winner_src = full_u
                            break
                        else:
                            # Mark uploaded/thumbnail tile as ignored so we keep waiting for the 1376x768 sheet
                            pre_submit_uuids.add(cand.uuid)
                    if winner_src:
                        break
                await asyncio.sleep(1.5)

            if winner_src:
                resp = await page.request.get(winner_src, timeout=60000)
                out_p.write_bytes(await resp.body())
                shutil.copy2(out_p, BRAIN_DIR / out_name)
                print(f"  -> SAVED {out_name} ({out_p.stat().st_size // 1024} KB)", flush=True)

    row_h, sheet_w = 330, 1380
    sheet = Image.new("RGB", (sheet_w, 70 + len(EP01_CHARACTER_JOBS) * row_h), (14, 16, 22))
    draw = ImageDraw.Draw(sheet)
    try:
        t_font = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", 22)
        l_font = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", 16)
    except Exception:
        t_font = l_font = ImageFont.load_default()
    draw.text((20, 18), "EPISODE 1-3 MANHWA FRAME (LEFT) -> GOOGLE FLOW ARCANE SHEET (RIGHT)", fill=(240, 198, 105), font=t_font)
    for i, (ref_rel, out_name, label, _) in enumerate(EP01_CHARACTER_JOBS):
        y0 = 65 + i * row_h
        ref_p, out_p = FRAMES_ROOT / ref_rel, SHEETS_DIR / out_name
        draw.rectangle([15, y0, sheet_w - 15, y0 + 28], fill=(28, 32, 46))
        draw.text((25, y0 + 5), label, fill=(240, 240, 248), font=l_font)
        if ref_p.is_file():
            im_r = Image.open(ref_p).convert("RGB")
            im_r.thumbnail((340, row_h - 42), Image.Resampling.LANCZOS)
            sheet.paste(im_r, (20 + (340 - im_r.width) // 2, y0 + 34 + (row_h - 42 - im_r.height) // 2))
        if out_p.is_file():
            im_o = Image.open(out_p).convert("RGB")
            im_o.thumbnail((960, row_h - 42), Image.Resampling.LANCZOS)
            sheet.paste(im_o, (385, y0 + 34))
    comp_path = CANON_DIR / "ep01_manhwa_vs_arcane_sheet.png"
    sheet.save(comp_path)
    shutil.copy2(comp_path, BRAIN_DIR / comp_path.name)
    print(f"Saved Episode 1 comparison sheet -> {comp_path}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
