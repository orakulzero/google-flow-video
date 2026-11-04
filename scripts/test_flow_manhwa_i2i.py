"""Test uploading ash_manhwa_cover.jpg via button.sidebar-upload-btn and attaching via button.detail-add-to-prompt-btn in flow.google.com."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

from gflow_cli.api.client import FlowApiClient
from gflow_cli.api.image import Aspect as ImageAspect, Model as ImageModel
from gflow_cli.api.transports.agent_only_composer import (
    EDITOR,
    IMAGE_BUDGET_S,
    LIVE_GATE,
    SUBMIT,
    AgentOnlyComposer,
    _full_size_src,
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


async def main() -> None:
    prof = Path(r"C:\Users\Orakul Grey\AppData\Local\ffroliva\gflow-cli\profile_default")
    manhwa_ref = Path(r"e:\ANTIGRAVITY\flow_video_testbench\output\ttd_arcane_characters\manga_refs\ash_manhwa_cover.jpg")
    out_file = Path(r"e:\ANTIGRAVITY\flow_video_testbench\output\ttd_arcane_characters\manhwa_i2i\ash_from_manhwa_v1.jpg")
    out_file.parent.mkdir(parents=True, exist_ok=True)

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
        await composer.apply_defaults(
            page,
            section="image",
            aspect_ligature=IMAGE_ASPECT_LIGATURE[ImageAspect.LANDSCAPE],
            count=1,
            model=IMAGE_MODEL_MENU_MATCHERS[ImageModel.GEM_PIX_2],
            confirm="never",
        )

        # Clear editor first BEFORE attaching ingredient
        editor = page.locator(EDITOR).last
        await editor.click(timeout=5000)
        await page.keyboard.press("ControlOrMeta+a")
        await page.keyboard.press("Delete")

        # Open ingredient menu and upload manhwa_ref
        add_ing = page.locator("button.add-menu-trigger").last
        await add_ing.click(timeout=5000)
        await asyncio.sleep(1.5)

        upload_btn = page.locator("button.sidebar-upload-btn").first
        async with page.expect_file_chooser(timeout=10000) as fc_info:
            await upload_btn.click(timeout=5000)
        chooser = await fc_info.value
        await chooser.set_files(str(manhwa_ref))
        print("Uploaded file to chooser, waiting for upload to settle...", flush=True)
        await asyncio.sleep(5)

        # Check if an upload-rights dialog appeared
        dialogs = await page.locator("mat-dialog-container button").count()
        if dialogs > 0:
            print(f"Found {dialogs} dialog buttons, clicking confirm...", flush=True)
            await page.locator("mat-dialog-container button").last.click(timeout=5000)
            await asyncio.sleep(4)

        # Check if the overlay is still open or if the ingredient was auto-added or needs 'detail-add-to-prompt-btn'
        add_to_prompt = page.locator("button.detail-add-to-prompt-btn")
        if await add_to_prompt.count() > 0 and await add_to_prompt.first.is_visible():
            print("Clicking detail-add-to-prompt-btn...", flush=True)
            await add_to_prompt.first.click(timeout=5000)
            await asyncio.sleep(1.5)

        # Inspect editor HTML to confirm the attached reference chip is inside or beside the prompt box
        editor_info = await page.evaluate(
            """() => {
                const box = document.querySelector('flow-prompt-box, flow-agent-panel');
                return box ? box.innerText.slice(-300) : 'no box';
            }"""
        )
        print("Composer state after attach:", repr(editor_info), flush=True)

        baseline_gates = await page.locator(LIVE_GATE).count()
        baseline_uuids = await composer._any_uuids(page)

        directive = (
            "Generate 1 image in 16:9 aspect ratio: Based directly on the attached reference manhwa frame of "
            "Ash Everblack, create a character concept turnaround sheet in the hand-painted brushwork style of "
            "Fortiche Production Arcane. Preserve his exact hairstyle, facial expression, eye color, and dark-and-gold "
            "royal commander outfit from the reference image, rendered with visible oil and gouache brushstrokes, "
            "dramatic chiaroscuro rim lighting, showing close-up face portrait, 3/4 view, and full-body turnaround "
            "on a clean parchment background. No text, no labels."
        )
        await editor.click(timeout=5000)
        await page.keyboard.insert_text(directive)
        await asyncio.sleep(0.5)
        submit = page.locator(SUBMIT).last
        await submit.click(timeout=5000)
        print("Submitted manhwa i2i prompt! Waiting for image...", flush=True)

        run = _Run("image", IMAGE_BUDGET_S, asyncio.get_running_loop().time() + IMAGE_BUDGET_S, baseline_gates, 1)
        # Use time.monotonic() for _Run deadline
        import time as _time
        run = _Run("image", IMAGE_BUDGET_S, _time.monotonic() + IMAGE_BUDGET_S, baseline_gates, 1)
        media = await composer._await_images(page, run, 1, baseline_uuids)
        src = _full_size_src(media[0].src)
        resp = await page.request.get(src, timeout=60000)
        out_file.write_bytes(await resp.body())
        print(f"SUCCESS! Saved {out_file} ({out_file.stat().st_size // 1024} KB)", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
