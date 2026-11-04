"""Generate the 14 seamless continuation clips (01b..12b, 02c, 04c) via Google Flow Omni 1.1 Flash.

Extracts the final frame of each preceding clip and submits it to generate_video_with_first_frame
with explicit 'Continuous, unbroken single shot, no scene cuts' prompting so every scene plays
as a continuous 8-to-12 second sequence covering all Chapter 1 novel/manhwa events.
100% English-only source hygiene, <= 180 lines.
"""
from __future__ import annotations

import asyncio
import os
from pathlib import Path
import random
import shutil
import sys

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
from scripts.generate_ttd_ep01_flow_clips import (
    PROJECT_URL,
    SRC_PROFILE_DIR,
    VID_DIR,
    attach_single_frame,
    dismiss_cdk_overlays,
)
from src.flow_extended_prompts import EXTENDED_CLIP_SPECS, PREFIX
from veo_arcane_style.src.flow_conditioning import (
    EDITOR_LOCATOR,
    LIVE_GATE_LOCATOR,
    SUBMIT_LOCATOR,
    clear_prompt_box_ingredients,
    save_native_video,
    switch_to_videos_tab,
)


def extract_last_frame(video_path: Path, out_png: Path) -> Path:
    """Extract the final valid frame of a video clip as a 1280x720 PNG."""
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open source video: {video_path}")
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.set(cv2.CAP_PROP_POS_FRAMES, max(0, total - 3))
    last_bgr = None
    while True:
        ok, frame = cap.read()
        if not ok or frame is None:
            break
        last_bgr = frame
    cap.release()
    if last_bgr is None:
        raise RuntimeError(f"Could not read last frame from {video_path}")
    if (last_bgr.shape[1], last_bgr.shape[0]) != (1280, 720):
        last_bgr = cv2.resize(last_bgr, (1280, 720), interpolation=cv2.INTER_LANCZOS4)
    cv2.imwrite(str(out_png), last_bgr)
    return out_png


async def run_extended_clip(page, clip_id: str, rpc_state: dict, fallback_clean: bool = False) -> Path:
    out_path = VID_DIR / f"ttd_ep01_shot_{clip_id}_clip_720p.mp4"
    if out_path.is_file() and out_path.stat().st_size >= 200_000:
        print(f"[SKIP] SHOT-{clip_id} already exists ({out_path.stat().st_size} bytes)", flush=True)
        return out_path

    src_clip_name, prompt = EXTENDED_CLIP_SPECS[clip_id]
    src_clip_path = VID_DIR / src_clip_name
    if not src_clip_path.is_file():
        raise FileNotFoundError(f"Prerequisite clip missing for {clip_id}: {src_clip_path}")

    start_png = VID_DIR / f"_lastframe_for_{clip_id}.png"
    extract_last_frame(src_clip_path, start_png)
    if fallback_clean:
        prompt = PREFIX + "Smooth continuous camera movement with atmospheric rain and flickering light."

    print(f"\n=== Generating Extended SHOT-{clip_id} from last frame of {src_clip_name} ===", flush=True)
    rpc_state.update({"job_queued": False, "job_completed": False, "direct_video_url": ""})

    await dismiss_cdk_overlays(page)
    await switch_to_videos_tab(page)
    await asyncio.sleep(random.uniform(1.2, 1.8))
    await dismiss_cdk_overlays(page)

    baseline_tiles = await page.locator("flow-video-tile:not(:has(flow-pending-tile))").count()
    baseline_first_img = ""
    if baseline_tiles > 0:
        try:
            baseline_first_img = await page.locator("flow-video-tile:not(:has(flow-pending-tile)) img").first.get_attribute("src") or ""
        except Exception:
            pass

    new_session_btn = page.locator("button.header-action:has(mat-icon:text-is('edit_square'))").first
    if await new_session_btn.count() > 0 and await new_session_btn.is_visible():
        try:
            await new_session_btn.hover(timeout=3000)
            await asyncio.sleep(random.uniform(0.3, 0.6))
            await new_session_btn.click(timeout=4000)
            await asyncio.sleep(random.uniform(2.0, 2.8))
        except Exception:
            await dismiss_cdk_overlays(page)

    await clear_prompt_box_ingredients(page)
    print(f"Attaching {start_png.name}...", flush=True)
    await attach_single_frame(page, start_png.resolve())

    await switch_to_videos_tab(page)
    await asyncio.sleep(random.uniform(0.9, 1.4))
    await page.mouse.move(random.randint(320, 680), random.randint(260, 480), steps=14)

    editor = page.locator(EDITOR_LOCATOR).last
    await editor.hover(timeout=5000)
    await asyncio.sleep(random.uniform(0.3, 0.5))
    await editor.click(timeout=5000)
    await asyncio.sleep(random.uniform(0.5, 0.9))
    await editor.press_sequentially(prompt, delay=6)
    await asyncio.sleep(random.uniform(1.3, 2.1))

    submit_btn = page.locator(SUBMIT_LOCATOR).last
    await submit_btn.hover(timeout=5000)
    await asyncio.sleep(random.uniform(0.4, 0.7))
    await submit_btn.click(timeout=5000)
    print(f"Submitted SHOT-{clip_id} to Google Flow Omni 1.1 Flash!", flush=True)

    saw_pending = False
    retried_captcha = False
    for step in range(95):
        await asyncio.sleep(3.0)
        pending_cnt = await page.locator("flow-video-tile flow-pending-tile").count()
        if pending_cnt > 0:
            saw_pending = True

        bubbles = page.locator("flow-chat-bubble")
        cnt = await bubbles.count()
        last_txt = (await bubbles.nth(cnt - 1).inner_text()).replace("\n", " ")[:220] if cnt > 0 else ""
        if step in (3, 8, 16, 28):
            print(f"[SHOT-{clip_id} Step {step} | Pending={pending_cnt}] {last_txt}", flush=True)

        if step >= 2 and pending_cnt == 0 and ("\u043f\u043e\u0434\u043e\u0437\u0440\u0438\u0442\u0435\u043b\u044c\u043d" in last_txt or "suspicious" in last_txt.lower()):
            if not retried_captcha:
                retried_captcha = True
                retry_btn = page.locator("flow-chat-bubble button").last
                if await retry_btn.count() > 0 and await retry_btn.is_visible():
                    print("[RETRY] Clicking in-bubble Retry after human mouse movement...", flush=True)
                    await page.mouse.move(random.randint(250, 750), random.randint(200, 500), steps=20)
                    await asyncio.sleep(2.5)
                    await retry_btn.hover(timeout=3000)
                    await asyncio.sleep(0.5)
                    await retry_btn.click(timeout=3000)
                    continue
            raise RuntimeError(f"Unusual activity gate on {clip_id}: {last_txt[:120]}")

        if step >= 3 and pending_cnt == 0 and any(
            e in last_txt for e in ("\u041e\u0448\u0438\u0431\u043a\u0430", "\u043d\u0430\u0440\u0443\u0448\u0430\u0442", "Something went wrong", "violate", "can't generate")
        ):
            raise RuntimeError(f"Rejected: {last_txt[:140]}")

        if rpc_state["job_completed"] and rpc_state["direct_video_url"]:
            await asyncio.sleep(1.5)
            break

        if (saw_pending or rpc_state["job_queued"]) and pending_cnt == 0 and step >= 6:
            fin_tiles = page.locator("flow-video-tile:not(:has(flow-pending-tile))")
            fin_cnt = await fin_tiles.count()
            if fin_cnt > 0:
                cur_img = await fin_tiles.first.locator("img").first.get_attribute("src") or ""
                if fin_cnt > baseline_tiles or (cur_img and cur_img != baseline_first_img):
                    await fin_tiles.first.hover(timeout=5000)
                    await asyncio.sleep(2.0)
                    vid_el = fin_tiles.first.locator("video").first
                    if await vid_el.count() > 0:
                        dom_src = await vid_el.get_attribute("src") or ""
                        if dom_src:
                            rpc_state.update({"direct_video_url": dom_src, "job_completed": True})
                            await page.mouse.move(0, 0)
                            break

    if not rpc_state["direct_video_url"]:
        raise RuntimeError(f"No direct_video_url captured for SHOT-{clip_id}")
    await save_native_video(page, rpc_state["direct_video_url"], f"shot_{clip_id}", out_path)
    print(f"Saved {out_path.name} ({out_path.stat().st_size} bytes)", flush=True)
    if start_png.is_file():
        start_png.unlink()
    return out_path


def prepare_clean_profile() -> Path:
    """Seed a clean Chrome user-data-dir with only Local State and Cookies DB."""
    clean_dir = SRC_PROFILE_DIR.parent / "profile_omni_clean"
    if clean_dir.exists():
        shutil.rmtree(clean_dir, ignore_errors=True)
    net_dir = clean_dir / "Default" / "Network"
    net_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(SRC_PROFILE_DIR / "Local State", clean_dir / "Local State")
    shutil.copy2(SRC_PROFILE_DIR / "Default" / "Network" / "Cookies", net_dir / "Cookies")
    return clean_dir


async def main() -> None:
    import shutil
    VID_DIR.mkdir(parents=True, exist_ok=True)
    targets = [a for a in sys.argv[1:] if a in EXTENDED_CLIP_SPECS] or list(EXTENDED_CLIP_SPECS.keys())
    pending = [
        c for c in targets
        if not (VID_DIR / f"ttd_ep01_shot_{c}_clip_720p.mp4").is_file()
        or (VID_DIR / f"ttd_ep01_shot_{c}_clip_720p.mp4").stat().st_size < 200_000
    ]
    if not pending:
        print("All requested extended clips already exist!", flush=True)
        return

    rpc_state = {"job_queued": False, "job_completed": False, "direct_video_url": ""}
    async with FlowApiClient(SRC_PROFILE_DIR) as flow_client:
        page = flow_client._page

        async def on_response(resp):
            if "batchexecute" in resp.url and any(k in resp.url for k in ("rpcids=bOKtO", "rpcids=as29s")):
                try:
                    body = await resp.text()
                    if "rpcids=bOKtO" in resp.url:
                        rpc_state["job_queued"] = True
                        print("[RPC bOKtO] Video generation queued on Flow backend", flush=True)
                    elif "rpcids=as29s" in resp.url and rpc_state["job_queued"]:
                        for r_id, payload in parse_frames(body):
                            if r_id == "as29s" and payload is not None:
                                rec = generation_record(r_id, payload)
                                if rec.is_done and rec.video_url and "flow-content.google/video/" in rec.video_url:
                                    rpc_state.update({"direct_video_url": rec.video_url, "job_completed": True})
                                    print(f"[RPC as29s] Completed URL captured (size={rec.size_bytes})", flush=True)
                except Exception:
                    pass

        page.on("response", on_response)
        await page.goto(PROJECT_URL, wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(6.5)
        for cid in pending:
            for att in range(1, 3):
                try:
                    await run_extended_clip(page, cid, rpc_state, fallback_clean=(att > 1))
                    break
                except Exception as exc:
                    print(f"[WARN] SHOT-{cid} attempt {att} failed: {exc}", flush=True)
                    await asyncio.sleep(4.0)


if __name__ == "__main__":
    import shutil
    asyncio.run(main())
