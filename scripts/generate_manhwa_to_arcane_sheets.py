"""Generate Arcane (Fortiche) character sheets directly from original manhwa frames via Google Flow i2i."""

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

REF_DIR = Path("output/ttd_arcane_characters/manga_refs")
OUT_DIR = Path("output/ttd_arcane_characters/manhwa_i2i")
BRAIN_DIR = Path(r"C:\Users\Orakul Grey\.gemini\antigravity\brain\94dd6a04-54e7-4e8c-9551-224cace4f85f")

ARCANE_I2I_PREFIX = (
    "Make me a picture in a 16:9 aspect ratio: Based ONLY on the single attached reference manhwa frame, "
    "create a character concept turnaround sheet in the hand-painted brushwork style of Fortiche Production Arcane. "
    "Strictly preserve the exact hairstyle, hair color, eye color, facial structure, expression, clothing/armor, and "
    "weapons shown in the attached reference image, translated into Fortiche Arcane's 2.5D/3D painterly oil and "
    "gouache brushwork with dramatic chiaroscuro rim lighting, showing close-up face portrait, 3/4 view, and "
    "full-body turnaround on a clean parchment background. No text, no labels, no typography."
)

MANHWA_I2I_JOBS = [
    (
        "ash_manhwa_cover.jpg",
        "ash_from_manhwa.jpg",
        "01. Эш Эверблэк — Принц-командир (из фрейма манхвы)",
        f"{ARCANE_I2I_PREFIX} Character: Male commander Ash Everblack with short messy black hair, sharp dark eyes, black and gold imperial coat, holding a sword as shown in the attached reference.",
    ),
    (
        "lucas_manhwa_intro.jpg",
        "lucas_from_manhwa.jpg",
        "02. Лукас Макгрегор — Рыцарь-телохранитель (из фрейма манхвы)",
        f"{ARCANE_I2I_PREFIX} Character: Blonde SSR vanguard knight Lucas MacGregor in his exact armor and blue cape from the attached reference.",
    ),
    (
        "damien_manhwa_action.jpg",
        "damien_from_manhwa.jpg",
        "03. Дэмиен — Снайпер «Всевидящее Око» (из фрейма манхвы)",
        f"{ARCANE_I2I_PREFIX} Character: Slim young dark-haired marksman Damien with glowing golden-green sniper eyes, green hooded ranger cloak, aiming his long-barreled wood-and-brass sniper rifle from the attached reference.",
    ),
    (
        "eider_manhwa.jpg",
        "damien_eye_from_manhwa.jpg",
        "04. Эйдер — Директор и казначей Эша (из фрейма манхвы)",
        (
            f"{ARCANE_I2I_PREFIX} Character: Young male aide and treasurer Eider from the attached reference, with "
            "short messy ash-blonde/greyish hair, wearing large round wire-rimmed eyeglasses (spectacles), white dress "
            "shirt, dark necktie, and tailored brown merchant-scholar vest, holding a ledger book and coin pouch "
            "(civilian scholar/treasurer attire — NO rifle, NO weapons, NO cape, NO armor)."
        ),
    ),
    (
        "evangeline_manhwa_young.jpg",
        "evangeline_from_manhwa.jpg",
        "05. Евангелина Кросс — SSR Рыцарь-щитоносец (из фрейма манхвы)",
        f"{ARCANE_I2I_PREFIX} Character: Petite teenage girl knight Evangeline Cross with rose-pink hair, crimson eyes, wearing heavy silver-and-rose plate armor and holding a massive cavalry lance and fortress shield from the attached reference.",
    ),
    (
        "jupiter_manhwa.jpg",
        "jupiter_from_manhwa.jpg",
        "06. Юпитер — Маг молний (из фрейма манхвы)",
        f"{ARCANE_I2I_PREFIX} Character: Veteran one-eyed lightning mage mercenary Jupiter with white hair, eyepatch, and cigar from the attached reference.",
    ),
    (
        "lily_manhwa_1.jpg",
        "lily_from_manhwa.jpg",
        "07. Лили — Алхимик-инженер (из фрейма манхвы)",
        f"{ARCANE_I2I_PREFIX} Character: Red-haired mage alchemist Lily in her exact outfit and expression from the attached reference.",
    ),
    (
        "black_spider_queen_manhwa.jpg",
        "spider_queen_from_manhwa.jpg",
        "08. Босс 1-й волны: Паучья Королева (из фрейма манхвы)",
        (
            "Make me a picture in a 16:9 aspect ratio: Creature Concept Turnaround Sheet in the hand-painted "
            "dark-fantasy style of Fortiche Production Arcane. Based directly on the attached reference manhwa frame, "
            "depict ONLY the colossal NON-HUMAN Black Spider Queen monster boss (giant terrifying eight-legged arachnid "
            "beast with jagged black chitinous carapace, glowing crimson cluster eyes, and venomous mandibles — NO human "
            "body, NO human face). Show front view, side profile, and menacing attack pose on a clean parchment background. "
            "No text, no labels."
        ),
    ),
]


BLED_FILES_TO_REGEN = {
    "ash_from_manhwa.jpg",
    "damien_from_manhwa.jpg",
    "damien_eye_from_manhwa.jpg",
    "evangeline_from_manhwa.jpg",
    "spider_queen_from_manhwa.jpg",
}


async def start_fresh_agent_session(page, composer: AgentOnlyComposer) -> None:
    """Reload project page and click 'edit_square' so the Flow Agent has zero prior character bleed."""
    await page.goto(
        "https://flow.google.com/project/7d9a2a67-9cd2-4a79-932e-717d2e29257f",
        wait_until="domcontentloaded",
        timeout=60000,
    )
    await asyncio.sleep(4.0)
    new_session_btn = page.locator("button.header-action:has(mat-icon:text-is('edit_square'))").first
    if await new_session_btn.count() > 0 and await new_session_btn.is_visible():
        await new_session_btn.click(timeout=5000)
        await asyncio.sleep(1.5)

    # Clear any remaining chips or text in the composer
    chip_close = page.locator(
        "flow-agent-panel button:has(mat-icon:text-is('cancel')), "
        "flow-agent-panel button:has(mat-icon:text-is('close'))"
    )
    cnt = await chip_close.count()
    for _ in range(cnt):
        try:
            if await chip_close.first.is_visible():
                await chip_close.first.click(timeout=2000)
                await asyncio.sleep(0.3)
        except Exception:
            break

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
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    # Remove only the 5 bled files that still have the old marker or haven't been regenerated cleanly
    regen_marker = OUT_DIR / ".clean_session_regen_done"
    if not regen_marker.is_file():
        for fname in BLED_FILES_TO_REGEN:
            p = OUT_DIR / fname
            if p.is_file():
                p.unlink()
                print(f"Removed bled sheet {fname} for clean fresh-session regeneration", flush=True)
        regen_marker.write_text("started", encoding="utf-8")

    prof = Path(r"C:\Users\Orakul Grey\AppData\Local\ffroliva\gflow-cli\profile_default")
    async with FlowApiClient(prof) as client:
        page = client._page
        assert page is not None
        await page.goto(
            "https://flow.google.com/project/7d9a2a67-9cd2-4a79-932e-717d2e29257f",
            wait_until="domcontentloaded",
            timeout=60000,
        )
        await asyncio.sleep(5)
        composer = AgentOnlyComposer()

        for idx, (ref_name, out_name, label, directive) in enumerate(MANHWA_I2I_JOBS, 1):
            out_p = OUT_DIR / out_name
            if out_p.is_file() and out_p.stat().st_size > 10000:
                print(f"[{idx}/{len(MANHWA_I2I_JOBS)}] Keeping verified {out_name}", flush=True)
                shutil.copy2(out_p, BRAIN_DIR / out_name)
                continue

            ref_p = REF_DIR / ref_name
            print(f"[{idx}/{len(MANHWA_I2I_JOBS)}] Generating {out_name} from {ref_name} (FRESH SESSION)...", flush=True)
            await start_fresh_agent_session(page, composer)

            before_upload_uuids = set((await composer._media(page)).keys())

            add_ing = page.locator("button.add-menu-trigger").last
            await add_ing.click(timeout=5000)
            await asyncio.sleep(1.5)

            upload_btn = page.locator("button.sidebar-upload-btn").first
            async with page.expect_file_chooser(timeout=10000) as fc_info:
                await upload_btn.click(timeout=5000)
            chooser = await fc_info.value
            await chooser.set_files(str(ref_p))
            await asyncio.sleep(4.5)

            dialogs = await page.locator("mat-dialog-container button").count()
            if dialogs > 0:
                await page.locator("mat-dialog-container button").last.click(timeout=5000)
                await asyncio.sleep(3.5)

            add_to_prompt = page.locator("button.detail-add-to-prompt-btn")
            if await add_to_prompt.count() > 0 and await add_to_prompt.first.is_visible():
                await add_to_prompt.first.click(timeout=5000)
                await asyncio.sleep(1.5)

            after_upload_uuids = set((await composer._media(page)).keys())
            uploaded_uuids = after_upload_uuids - before_upload_uuids
            print(f"  Attached {ref_name} (upload tiles: {uploaded_uuids})", flush=True)

            baseline_gates = await page.locator(LIVE_GATE).count()
            editor = page.locator(EDITOR).last
            await editor.click(timeout=5000)
            await page.keyboard.insert_text(directive)
            await asyncio.sleep(0.5)
            await page.locator(SUBMIT).last.click(timeout=5000)

            run = _Run("image", IMAGE_BUDGET_S, time.monotonic() + IMAGE_BUDGET_S, baseline_gates, 1)
            winner_src = None
            while time.monotonic() < run.deadline:
                if await composer._gate_turn(page, run):
                    continue
                in_flight = bool(await page.locator(IN_FLIGHT).count())
                cur_media = await composer._media(page)
                candidates = [
                    m for u, m in cur_media.items()
                    if u not in before_upload_uuids and u not in uploaded_uuids
                ]
                if candidates and not in_flight:
                    for cand in candidates:
                        full_u = _full_size_src(cand.src)
                        w, h = await _natural_size(page, full_u)
                        if w > h and w >= 1000:
                            winner_src = full_u
                            break
                    if not winner_src:
                        winner_src = _full_size_src(candidates[0].src)
                    break
                await asyncio.sleep(1.2)

            if winner_src:
                resp = await page.request.get(winner_src, timeout=60000)
                out_p.write_bytes(await resp.body())
                shutil.copy2(out_p, BRAIN_DIR / out_name)
                if out_name == "damien_eye_from_manhwa.jpg":
                    shutil.copy2(out_p, OUT_DIR / "eider_from_manhwa.jpg")
                print(f"  -> SAVED {out_name} ({out_p.stat().st_size // 1024} KB)", flush=True)
            else:
                print(f"  -> FAILED/TIMED OUT on {out_name}", flush=True)

    print("Building Manhwa vs Arcane comparison contact sheet...", flush=True)
    row_h, sheet_w = 330, 1380
    sheet = Image.new("RGB", (sheet_w, 70 + len(MANHWA_I2I_JOBS) * row_h), (14, 16, 22))
    draw = ImageDraw.Draw(sheet)
    try:
        t_font = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", 22)
        l_font = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", 16)
    except Exception:
        t_font = l_font = ImageFont.load_default()

    draw.text((20, 18), "MANHWA FRAME (LEFT) -> GOOGLE FLOW NANO BANANA PRO ARCANE SHEET (RIGHT)", fill=(240, 198, 105), font=t_font)
    for i, (ref_name, out_name, label, _) in enumerate(MANHWA_I2I_JOBS):
        y0 = 65 + i * row_h
        ref_p, out_p = REF_DIR / ref_name, OUT_DIR / out_name
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

    comp_path = OUT_DIR / "manhwa_vs_arcane_contact_sheet.png"
    sheet.save(comp_path)
    shutil.copy2(comp_path, BRAIN_DIR / "manhwa_vs_arcane_contact_sheet.png")
    print(f"Saved comparison sheet to {comp_path}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
