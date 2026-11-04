"""Generate Arcane combat clips using Gemini Omni 1.1 Flash via Patchright on Google Flow.

Uses patchright.async_api directly (avoiding Runtime.enable CDP leaks and
navigator own-property tampering) with a clean profile copy to prevent
PUBLIC_ERROR_UNUSUAL_ACTIVITY ("browser extensions that modify the page").
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
import random
import re
import shutil
import sys
import uuid

os.environ["GFLOW_CLI_BROWSER_ENGINE"] = "patchright"
os.environ["GFLOW_CLI_BROWSER_PROXY"] = "http://127.0.0.1:7890"
os.environ["HTTPS_PROXY"] = "http://127.0.0.1:7890"
os.environ["HTTP_PROXY"] = "http://127.0.0.1:7890"

from gflow_cli.api.client import FlowApiClient

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
CLEAN_PROFILE_DIR = _LOCAL_APPDATA / "ffroliva" / "gflow-cli" / "profile_omni_clean"
PROJECT_URL = "https://flow.google.com/project/7d9a2a67-9cd2-4a79-932e-717d2e29257f"
PROXY_URL = "http://127.0.0.1:7890"
DATASET_DIR = Path("veo_arcane_style/dataset")
OUTPUT_DIR = Path("veo_arcane_style/output")

CLIPS = [
    {
        "name": "omni_clip_01_vi_interpolation_720p.mp4",
        "mode": "interpolation",
        "frames": [
            DATASET_DIR / "pairs/pair_170629_shot_000/first_frame.png",
            DATASET_DIR / "pairs/pair_170629_shot_000/last_frame.png",
        ],
        "prompt": (
            "Use generate_video_with_interpolation with model_display_name='Omni 1.1 Flash', "
            "aspect_ratio='16:9', duration='4s', the first attached image as start_image_media_id, "
            "and the second attached image as end_image_media_id. "
            "Prompt: Hand-painted 2.5D animation style with visible impasto brushwork and "
            "dual-tone magenta-cyan chiaroscuro lighting. Single unbroken continuous shot in a locked "
            "static tight close-up camera framing; the camera never zooms out and never changes angle. "
            "Her shoulders and arms remain out of frame below the bottom edge (only the gauntlets on her "
            "hands are mechanical). In the immediate foreground, both oversized mechanical gauntlets "
            "stay locked in front of her chin (circular metallic piston rings on the left, rectangular "
            "steel knuckle plates on the right pressing against the vertical magenta glow) while her "
            "face transitions smoothly from clenched teeth in shadow to an open-mouthed battle cry "
            "illuminated by bright golden-orange sparks erupting around the gauntlet knuckles."
        ),
    },
    {
        "name": "omni_clip_02_jinx_interpolation_720p.mp4",
        "mode": "interpolation",
        "frames": [
            DATASET_DIR / "pairs/pair_270000_shot_015/first_frame.png",
            DATASET_DIR / "pairs/pair_270000_shot_015/last_frame.png",
        ],
        "prompt": (
            "Use generate_video_with_interpolation with model_display_name='Omni 1.1 Flash', "
            "aspect_ratio='16:9', duration='4s', the first attached image as start_image_media_id, "
            "and the second attached image as end_image_media_id. "
            "Prompt: Hand-painted 2.5D animation style with visible impasto brushwork and "
            "dual-tone magenta-cyan chiaroscuro lighting. Single unbroken continuous energy charge-up in "
            "a locked static side-profile camera framing; the camera never cuts and never changes angle. "
            "The blue-haired woman remains in the exact same side-profile pose holding her massive "
            "shark-headed mechanical cannon steadily on her shoulder aimed toward the upper-left. The "
            "cannon never fires a projectile, never produces an orange explosion, and never leaves her "
            "shoulder. Instead, glowing cyan-white plasma and diagonal blue light rays originate from "
            "inside the open shark jaws, internal barrel seams, and rear exhaust cone, building steadily "
            "into a blinding cyan-white radial overcharge flare in the final frame."
        ),
    },
]

CLIPS.extend([
    {
        "name": "omni_clip_01_vi_r2v6_720p.mp4",
        "mode": "r2v_6frames",
        "frames": [
            DATASET_DIR / "pairs/pair_170629_shot_000/first_frame.png",
            DATASET_DIR / "pairs/pair_170629_shot_000/omni_ref_0.png",
            DATASET_DIR / "pairs/pair_170629_shot_000/omni_ref_1.png",
            DATASET_DIR / "pairs/pair_170629_shot_000/omni_ref_2.png",
            DATASET_DIR / "pairs/pair_170629_shot_000/omni_ref_3.png",
            DATASET_DIR / "pairs/pair_170629_shot_000/last_frame.png",
        ],
        "prompt": (
            "Use generate_video_with_references with model_display_name='Omni 1.1 Flash', "
            "aspect_ratio='16:9', duration='4s', and all 6 attached images in chronological order "
            "as reference_image_media_ids. "
            "Prompt: Follow the exact chronological progression of the 6 reference keyframes "
            "in a locked static tight close-up camera framing without ever zooming out or changing angle. "
            "Hand-painted 2.5D animation style with visible impasto brushwork and dual-tone magenta-cyan "
            "chiaroscuro lighting. Both oversized mechanical gauntlets remain in front of her chin while "
            "her face transitions smoothly from clenched teeth in shadow to an open-mouthed battle cry "
            "illuminated by bright golden-orange sparks."
        ),
    },
    {
        "name": "omni_clip_02_jinx_r2v6_720p.mp4",
        "mode": "r2v_6frames",
        "frames": [
            DATASET_DIR / "pairs/pair_270000_shot_015/first_frame.png",
            DATASET_DIR / "pairs/pair_270000_shot_015/omni_ref_0.png",
            DATASET_DIR / "pairs/pair_270000_shot_015/omni_ref_1.png",
            DATASET_DIR / "pairs/pair_270000_shot_015/omni_ref_2.png",
            DATASET_DIR / "pairs/pair_270000_shot_015/omni_ref_3.png",
            DATASET_DIR / "pairs/pair_270000_shot_015/last_frame.png",
        ],
        "prompt": (
            "Use generate_video_with_references with model_display_name='Omni 1.1 Flash', "
            "aspect_ratio='16:9', duration='4s', and all 6 attached images in chronological order "
            "as reference_image_media_ids. "
            "Prompt: Follow the exact chronological progression of the 6 reference keyframes "
            "in a locked static side-profile camera framing without ever cutting or changing angle. "
            "Hand-painted 2.5D animation style with visible impasto brushwork and dual-tone magenta-cyan "
            "chiaroscuro lighting. The blue-haired woman holds her massive shark-headed mechanical cannon "
            "steadily on her shoulder while glowing cyan-white plasma and diagonal blue light rays build "
            "from inside the open shark jaws into a blinding cyan-white radial overcharge flare."
        ),
    },
    {
        "name": "omni_clip_03_lucas_interpolation_720p.mp4",
        "mode": "interpolation",
        "frames": [
            DATASET_DIR / "pairs/pair_ttd_ep01_lucas_001/first_frame.png",
            DATASET_DIR / "pairs/pair_ttd_ep01_lucas_001/last_frame.png",
        ],
        "prompt": (
            "Use generate_video_with_interpolation with model_display_name='Omni 1.1 Flash', "
            "aspect_ratio='16:9', duration='4s', the first attached image as start_image_media_id, "
            "and the second attached image as end_image_media_id. "
            "Prompt: Dynamic three-quarter (3/4) tight close-up camera pushing in ~15% closer onto the "
            "blond knight's face as he leans forward and roars the command to attack ('CHARGE!'). "
            "Hand-painted 2.5D animation style with visible impasto oil brushwork, sculpted facial planes, "
            "and warm flickering torchlight against cool night-slate rim light. His eyes remain natural "
            "warm amber-brown human irises with realistic torchlight catchlights only, with zero glowing "
            "eyes and zero floating sparks on his steel gorget or pauldron. Over 4 seconds, his clenched "
            "jaw opens wide into a commanding battle shout while the armored vanguard soldiers with steel "
            "helmets, spears, and raised torches behind his shoulders surge forward into the charge."
        ),
    },
])


def prepare_clean_profile() -> Path:
    """Seed a clean Chrome user-data-dir with only Local State and Cookies DB."""
    if CLEAN_PROFILE_DIR.exists():
        shutil.rmtree(CLEAN_PROFILE_DIR, ignore_errors=True)
    net_dir = CLEAN_PROFILE_DIR / "Default" / "Network"
    net_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(SRC_PROFILE_DIR / "Local State", CLEAN_PROFILE_DIR / "Local State")
    shutil.copy2(SRC_PROFILE_DIR / "Default" / "Network" / "Cookies", net_dir / "Cookies")
    return CLEAN_PROFILE_DIR


async def attach_frame_human(page, file_path: Path, reuse_existing_picker_idx: int = -1) -> None:
    """Attach a frame from the existing asset library or upload with human jitter."""
    chip_loc = page.locator("flow-creative-agent-prompt-box flow-image-ingredient-chip")
    before_chips = await chip_loc.count()

    await asyncio.sleep(random.uniform(0.8, 1.4))
    add_btn = page.locator("button.add-menu-trigger").last
    await add_btn.click(timeout=8000)
    await asyncio.sleep(random.uniform(1.5, 2.2))

    if reuse_existing_picker_idx < 0:
        upload_btn = page.locator("button.sidebar-upload-btn").first
        async with page.expect_file_chooser(timeout=15000) as fc_info:
            await upload_btn.click(timeout=8000)
        chooser = await fc_info.value
        unique_filename = f"{file_path.stem}_{uuid.uuid4().hex[:6]}{file_path.suffix}"
        async with page.expect_response(lambda r: "maseQ" in r.url and r.status == 200, timeout=45000):
            await chooser.set_files({
                "name": unique_filename,
                "mimeType": "image/png",
                "buffer": file_path.read_bytes(),
            })
        await asyncio.sleep(random.uniform(2.5, 3.5))
        picker_idx = 0
    else:
        picker_idx = reuse_existing_picker_idx

    picker = page.locator("flow-add-menu-popover-content").first
    if not await picker.is_visible():
        await add_btn.click(timeout=8000)
        await asyncio.sleep(1.5)

    opt = picker.locator("button.asset-item[role='option']").nth(picker_idx)
    await opt.wait_for(state="visible", timeout=15000)
    await opt.click(timeout=5000)
    await asyncio.sleep(random.uniform(1.2, 1.8))

    if await picker.is_visible():
        detail_add = page.locator("button.detail-add-to-prompt-btn:not([disabled])").first
        if await detail_add.count() > 0 and await detail_add.is_visible():
            await detail_add.click(timeout=5000)
            await asyncio.sleep(1.0)
        else:
            await page.keyboard.press("Escape")
            await asyncio.sleep(0.5)

    after_chips = await chip_loc.count()
    if after_chips <= before_chips:
        raise RuntimeError(
            f"Ingredient chip count did not increment for {file_path.name} ({before_chips} -> {after_chips})"
        )


async def run_one_clip(page, clip_spec: dict, rpc_state: dict, reuse_top2: bool = False) -> Path:
    out_path = OUTPUT_DIR / clip_spec["name"]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    print(f"\n=== Starting {clip_spec['name']} ({clip_spec['mode']}) ===", flush=True)

    rpc_state["job_queued"] = False
    rpc_state["job_completed"] = False
    rpc_state["direct_video_url"] = ""

    await switch_to_videos_tab(page)
    await asyncio.sleep(random.uniform(1.2, 2.0))

    baseline_tiles = await page.locator("flow-video-tile:not(:has(flow-pending-tile))").count()
    baseline_first_img = ""
    if baseline_tiles > 0:
        try:
            baseline_first_img = await page.locator("flow-video-tile:not(:has(flow-pending-tile)) img").first.get_attribute("src") or ""
        except Exception:
            pass
    print(f"Baseline finished video tiles: {baseline_tiles}", flush=True)

    new_session_btn = page.locator("button.header-action:has(mat-icon:text-is('edit_square'))").first
    if await new_session_btn.count() > 0 and await new_session_btn.is_visible():
        await new_session_btn.click(timeout=5000)
        await asyncio.sleep(random.uniform(2.0, 2.8))

    await clear_prompt_box_ingredients(page)
    if reuse_top2 and len(clip_spec["frames"]) == 2:
        print("Reusing already uploaded first_frame (idx 1) and last_frame (idx 0) from library...", flush=True)
        await attach_frame_human(page, clip_spec["frames"][0], reuse_existing_picker_idx=1)
        await attach_frame_human(page, clip_spec["frames"][1], reuse_existing_picker_idx=0)
    else:
        for idx, frame_path in enumerate(clip_spec["frames"]):
            print(f"Attaching frame {idx + 1}/{len(clip_spec['frames'])}: {frame_path.name}", flush=True)
            await attach_frame_human(page, frame_path.resolve(), reuse_existing_picker_idx=-1)

    await switch_to_videos_tab(page)
    await asyncio.sleep(1.0)

    editor = page.locator(EDITOR_LOCATOR).last
    await editor.click(timeout=5000)
    await asyncio.sleep(random.uniform(0.5, 1.0))
    await editor.press_sequentially(clip_spec["prompt"], delay=5)
    await asyncio.sleep(random.uniform(1.2, 2.0))

    submit_btn = page.locator(SUBMIT_LOCATOR).last
    await submit_btn.hover(timeout=5000)
    await asyncio.sleep(random.uniform(0.3, 0.6))
    await submit_btn.click(timeout=5000)
    print("Submitted prompt via Patchright!", flush=True)

    saw_pending = False
    for step in range(110):
        await asyncio.sleep(3.0)
        gates = page.locator(LIVE_GATE_LOCATOR)
        if await gates.count() > 0:
            approve = gates.first.locator(
                "div[role='radio'].option-row:not(.read-only):has(mat-icon:text-is('check'))"
            ).first
            if await approve.count() > 0 and await approve.is_visible():
                print("[GATE] Approving credit confirmation gate...", flush=True)
                await approve.click(timeout=5000)
                await asyncio.sleep(2.0)

        pending_cnt = await page.locator("flow-video-tile flow-pending-tile").count()
        if pending_cnt > 0:
            saw_pending = True

        if step in (2, 5, 10, 18, 30, 45, 60):
            bubbles = page.locator("flow-chat-bubble")
            cnt = await bubbles.count()
            last_txt = ""
            if cnt > 0:
                last_txt = (await bubbles.nth(cnt - 1).inner_text()).replace("\n", " ")[:220]
            print(f"[Step {step} | Pending={pending_cnt} | Bubbles={cnt}] {last_txt}", flush=True)

        if rpc_state["job_completed"] and rpc_state["direct_video_url"]:
            await asyncio.sleep(2.0)
            break

        if (saw_pending or rpc_state["job_queued"]) and pending_cnt == 0 and step >= 6:
            fin_tiles = page.locator("flow-video-tile:not(:has(flow-pending-tile))")
            fin_cnt = await fin_tiles.count()
            if fin_cnt > 0:
                cur_first_img = ""
                try:
                    cur_first_img = await fin_tiles.first.locator("img").first.get_attribute("src") or ""
                except Exception:
                    pass
                if fin_cnt > baseline_tiles or (cur_first_img and cur_first_img != baseline_first_img):
                    try:
                        await fin_tiles.first.hover(timeout=5000)
                        await asyncio.sleep(2.0)
                        vid_el = fin_tiles.first.locator("video").first
                        if await vid_el.count() > 0:
                            dom_src = await vid_el.get_attribute("src") or ""
                            if dom_src:
                                rpc_state["direct_video_url"] = dom_src
                                rpc_state["job_completed"] = True
                                print(f"[DOM Tile] Captured new video src via hover!", flush=True)
                                await page.mouse.move(0, 0)
                                break
                    except Exception:
                        pass

    vid_src = rpc_state["direct_video_url"]
    if not vid_src:
        raise RuntimeError("No direct_video_url captured from as29s")

    print(f"Downloading video from signed URL: {vid_src[:90]}...", flush=True)
    await save_native_video(page, vid_src, "omni_flow", out_path)
    print(f"Saved {out_path} ({out_path.stat().st_size} bytes)", flush=True)
    return out_path


async def recover_latest_finished_video(page, out_path: Path) -> Path:
    """Download the newest finished video tile on the Videos tab."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    await switch_to_videos_tab(page)
    await asyncio.sleep(2.5)
    fin_tiles = page.locator("flow-video-tile:not(:has(flow-pending-tile))")
    cnt = await fin_tiles.count()
    print(f"[Recover] Found {cnt} finished video tiles on grid.", flush=True)
    if cnt == 0:
        raise RuntimeError("No finished video tiles on grid to recover")
    tile = fin_tiles.first
    await tile.hover(timeout=5000)
    await asyncio.sleep(2.5)
    vid_el = tile.locator("video").first
    await vid_el.wait_for(state="attached", timeout=8000)
    dom_src = await vid_el.get_attribute("src") or ""
    await page.mouse.move(0, 0)
    if not dom_src:
        raise RuntimeError("Failed to read video src on hover")
    print(f"[Recover] Downloading {out_path.name} from {dom_src[:90]}...", flush=True)
    await save_native_video(page, dom_src, "omni_flow_recovered", out_path)
    print(f"[Recover] Saved {out_path} ({out_path.stat().st_size} bytes)", flush=True)
    return out_path


async def main() -> None:
    from gflow_cli.api.transports.batchexecute import generation_record, parse_frames

    raw_args = sys.argv[1:]
    recover_0 = "--recover-0" in raw_args
    recover_3 = "--recover-3" in raw_args
    recover_4 = "--recover-4" in raw_args
    reuse_top2_flag = "--reuse-top2" in raw_args
    indices = [int(a) for a in raw_args if not a.startswith("--")]
    rpc_state = {"job_queued": False, "job_completed": False, "direct_video_url": ""}

    async with FlowApiClient(SRC_PROFILE_DIR) as flow_client:
        page = flow_client._page

        async def on_response(resp):
            url = resp.url
            if "FlowAgentService" in url or "SendAgentMessage" in url:
                print(f"[Agent RPC {resp.status}] {url[:100]}", flush=True)
            if "batchexecute" not in url:
                return
            if any(k in url for k in ("rpcids=ngNC2", "rpcids=bOKtO", "rpcids=vrrFtb", "rpcids=jwpduf", "rpcids=as29s")):
                try:
                    body = await resp.text()
                    if "rpcids=ngNC2" in url:
                        print(f"[RPC ngNC2] {body[:320]}", flush=True)
                    elif "rpcids=vrrFtb" in url:
                        print(f"[RPC vrrFtb] {body[:350]}", flush=True)
                    elif "rpcids=bOKtO" in url:
                        rpc_state["job_queued"] = True
                        print(f"[RPC bOKtO] Job queued: {body[:450]}", flush=True)
                    elif "rpcids=jwpduf" in url and rpc_state["job_queued"]:
                        print(f"[RPC jwpduf] Poll: {body[:280]}", flush=True)
                    elif "rpcids=as29s" in url and rpc_state["job_queued"]:
                        for rpcid, payload in parse_frames(body):
                            if rpcid == "as29s" and payload is not None:
                                rec = generation_record(rpcid, payload)
                                if rec.is_done and rec.video_url and "flow-content.google/video/" in rec.video_url:
                                    rpc_state["direct_video_url"] = rec.video_url
                                    rpc_state["job_completed"] = True
                                    print(
                                        f"[RPC as29s] Completed video URL captured (size={rec.size_bytes}): "
                                        f"{rec.video_url[:90]}...",
                                        flush=True,
                                    )
                except Exception as exc:
                    print(f"[RPC parse warn] {exc}", flush=True)

        page.on("response", on_response)
        await page.goto(PROJECT_URL, wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(6.5)

        if recover_0:
            await recover_latest_finished_video(page, OUTPUT_DIR / CLIPS[0]["name"])
        if recover_3:
            await recover_latest_finished_video(page, OUTPUT_DIR / CLIPS[3]["name"])
        if recover_4:
            await recover_latest_finished_video(page, OUTPUT_DIR / CLIPS[4]["name"])

        for idx in indices:
            await run_one_clip(page, CLIPS[idx], rpc_state, reuse_top2=reuse_top2_flag)


if __name__ == "__main__":
    asyncio.run(main())
