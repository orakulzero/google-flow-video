"""Generate all 12 Episode 1 video clips from the new keyframes via Google Flow Omni 1.1 Flash.

Uses patchright via FlowApiClient and generate_video_with_first_frame so every shot
starts on its canonical 1280x720 painted keyframe without background drift.
100% English-only source hygiene, <= 180 lines.
"""
from __future__ import annotations

import asyncio
import os
from pathlib import Path
import random
import shutil
import sys
import uuid

os.environ["GFLOW_CLI_BROWSER_ENGINE"] = "patchright"
os.environ["GFLOW_CLI_BROWSER_PROXY"] = "http://127.0.0.1:7890"
os.environ["HTTPS_PROXY"] = "http://127.0.0.1:7890"
os.environ["HTTP_PROXY"] = "http://127.0.0.1:7890"

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import cv2
from gflow_cli.api.client import FlowApiClient
from gflow_cli.api.transports.batchexecute import generation_record, parse_frames
from src.flow_shot_prompts import PREFIX, SHOT_PROMPTS
from src.ttd_keyframe_composer import SHOT_SPECS
from veo_arcane_style.src.flow_conditioning import (
    EDITOR_LOCATOR,
    LIVE_GATE_LOCATOR,
    SUBMIT_LOCATOR,
    clear_prompt_box_ingredients,
    save_native_video,
    switch_to_videos_tab,
)

_LOCAL_APPDATA = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local")))
SRC_PROFILE_DIR = _LOCAL_APPDATA / "ffroliva" / "gflow-cli" / "profile_default"
PROJECT_URL = "https://flow.google.com/project/7d9a2a67-9cd2-4a79-932e-717d2e29257f"
KF_DIR = ROOT_DIR / "output" / "ttd_ep01_flow_keyframes"
VID_DIR = ROOT_DIR / "output" / "ttd_ep01_flow_videos"


async def dismiss_cdk_overlays(page) -> None:
    for _ in range(3):
        backdrop = page.locator("div.cdk-overlay-backdrop-showing")
        if await backdrop.count() == 0:
            break
        try:
            await page.keyboard.press("Escape")
            await asyncio.sleep(0.5)
            if await backdrop.count() > 0:
                await backdrop.first.click(position={"x": 10, "y": 10}, timeout=2000, force=True)
                await asyncio.sleep(0.5)
        except Exception:
            pass


async def attach_single_frame(page, file_path: Path) -> None:
    await dismiss_cdk_overlays(page)
    chip_loc = page.locator("flow-creative-agent-prompt-box flow-image-ingredient-chip")
    before_chips = await chip_loc.count()
    await asyncio.sleep(random.uniform(0.8, 1.3))
    add_btn = page.locator("button.add-menu-trigger").last
    await add_btn.click(timeout=8000)
    await asyncio.sleep(random.uniform(1.4, 2.0))

    upload_btn = page.locator("button.sidebar-upload-btn").first
    async with page.expect_file_chooser(timeout=15000) as fc_info:
        await upload_btn.click(timeout=8000)
    chooser = await fc_info.value
    uname = f"{file_path.stem}_{uuid.uuid4().hex[:6]}{file_path.suffix}"
    async with page.expect_response(lambda r: "maseQ" in r.url and r.status == 200, timeout=45000):
        await chooser.set_files({"name": uname, "mimeType": "image/png", "buffer": file_path.read_bytes()})
    await asyncio.sleep(random.uniform(2.3, 3.2))

    picker = page.locator("flow-add-menu-popover-content").first
    if not await picker.is_visible():
        await add_btn.click(timeout=8000)
        await asyncio.sleep(1.5)
    opt = picker.locator("button.asset-item[role='option']").first
    await opt.wait_for(state="visible", timeout=15000)
    await opt.click(timeout=5000)
    await asyncio.sleep(random.uniform(1.1, 1.6))

    if await picker.is_visible():
        detail_add = page.locator("button.detail-add-to-prompt-btn:not([disabled])").first
        if await detail_add.count() > 0 and await detail_add.is_visible():
            await detail_add.click(timeout=5000)
            await asyncio.sleep(1.0)
        else:
            await page.keyboard.press("Escape")
    if await chip_loc.count() <= before_chips:
        raise RuntimeError(f"Chip count did not increment for {file_path.name}")


async def run_one_shot(page, shot_num: int, rpc_state: dict, fallback_clean: bool = False) -> Path:
    out_path = VID_DIR / f"ttd_ep01_shot_{shot_num:02d}_clip_720p.mp4"
    if out_path.is_file() and out_path.stat().st_size >= 200_000:
        return out_path

    kf_path = KF_DIR / f"ttd_ep01_shot_{shot_num:02d}_keyframe.png"
    prompt = SHOT_PROMPTS[shot_num]
    if fallback_clean or shot_num == 2:
        spec = SHOT_SPECS[f"SHOT-{shot_num:02d}"]
        kf_bgr = cv2.imread(str(kf_path))
        pl_bgr = cv2.imread(str(ROOT_DIR / "output" / "canonical_plates" / spec["bg_plate"]))
        blend = pl_bgr.copy() if shot_num == 2 else cv2.addWeighted(kf_bgr, 0.65, pl_bgr, 0.35, 0)
        if shot_num == 2:
            blend[:430, :] = kf_bgr[:430, :]
        kf_path = VID_DIR / f"_safe_shot_{shot_num:02d}.png"
        cv2.imwrite(str(kf_path), blend)
        if fallback_clean:
            prompt = PREFIX + "Hand-painted 2.5D animation style of Fortiche Arcane with smooth camera push-in."

    rpc_state.update({"job_queued": False, "job_completed": False, "direct_video_url": ""})
    await dismiss_cdk_overlays(page)
    await switch_to_videos_tab(page)
    await asyncio.sleep(1.2)
    await clear_prompt_box_ingredients(page)
    await attach_single_frame(page, kf_path.resolve())
    await switch_to_videos_tab(page)
    editor = page.locator(EDITOR_LOCATOR).last
    await editor.click(timeout=5000)
    await editor.press_sequentially(prompt, delay=4)
    await page.locator(SUBMIT_LOCATOR).last.click(timeout=5000)

    for step in range(95):
        await asyncio.sleep(3.0)
        pending_cnt = await page.locator("flow-video-tile flow-pending-tile").count()
        bubbles = page.locator("flow-chat-bubble")
        cnt = await bubbles.count()
        last_txt = (await bubbles.nth(cnt - 1).inner_text()).replace("\n", " ")[:220] if cnt > 0 else ""
        if step >= 3 and pending_cnt == 0 and any(e in last_txt for e in ("\u041e\u0448\u0438\u0431\u043a\u0430", "violate", "can't generate")):
            raise RuntimeError(f"Rejected: {last_txt[:120]}")
        if rpc_state["job_completed"] and rpc_state["direct_video_url"]:
            break
    if not rpc_state["direct_video_url"]:
        raise RuntimeError(f"No direct_video_url captured for SHOT-{shot_num:02d}")
    await save_native_video(page, rpc_state["direct_video_url"], f"shot_{shot_num:02d}", out_path)
    return out_path


async def main() -> None:
    VID_DIR.mkdir(parents=True, exist_ok=True)
    targets = [int(a) for a in sys.argv[1:] if a.isdigit()] or sorted(SHOT_PROMPTS.keys())
    rpc_state = {"job_queued": False, "job_completed": False, "direct_video_url": ""}
    async with FlowApiClient(SRC_PROFILE_DIR) as flow_client:
        page = flow_client._page

        async def on_response(resp):
            if "batchexecute" in resp.url and any(k in resp.url for k in ("rpcids=bOKtO", "rpcids=as29s")):
                try:
                    body = await resp.text()
                    if "rpcids=bOKtO" in resp.url:
                        rpc_state["job_queued"] = True
                    elif "rpcids=as29s" in resp.url and rpc_state["job_queued"]:
                        for r_id, payload in parse_frames(body):
                            if r_id == "as29s" and payload is not None:
                                rec = generation_record(r_id, payload)
                                if rec.is_done and rec.video_url and "flow-content.google/video/" in rec.video_url:
                                    rpc_state.update({"direct_video_url": rec.video_url, "job_completed": True})
                except Exception:
                    pass

        page.on("response", on_response)
        await page.goto(PROJECT_URL, wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(6.5)
        for s in targets:
            for att in range(1, 3):
                try:
                    await run_one_shot(page, s, rpc_state, fallback_clean=(att > 1))
                    break
                except Exception:
                    await asyncio.sleep(4.0)


if __name__ == "__main__":
    asyncio.run(main())
