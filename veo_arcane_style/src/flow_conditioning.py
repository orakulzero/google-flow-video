"""Google Flow Reference Conditioning and Browser Automation Utilities.

Provides ingredient attachment for start/end frames, generation polling,
and native AAC audio preservation for Veo 3.1 and Gemini Omni Flash.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
import time
from typing import Optional, Set, Tuple
import uuid

# Selectors from Google Flow client library
EDITOR_LOCATOR = "div.ProseMirror, div[contenteditable='true']"
SUBMIT_LOCATOR = "flow-generate-icon-button button, button.flow-submit-btn, button[aria-label='Submit'], button.submit-button"
LIVE_GATE_LOCATOR = "flow-permission-message, flow-approval-gate, mat-dialog-container"
FINISHED_TILE_LOCATOR = "flow-video-tile:not(:has(flow-pending-tile))"
VIDEO_STATE_JS = """() => {
    const pending = document.querySelectorAll('flow-pending-tile, mat-progress-spinner').length;
    const tiles = document.querySelectorAll('flow-video-tile:not(:has(flow-pending-tile))');
    const finished = [];
    tiles.forEach(tile => {
        const v = tile.querySelector('video');
        const img = tile.querySelector('img');
        finished.push({
            video: v ? (v.currentSrc || v.src || '') : '',
            img: img ? (img.currentSrc || img.src || '') : ''
        });
    });
    return { pending, finished };
}"""


async def switch_to_videos_tab(page) -> None:
    """Ensure videos tab is active in Google Flow project canvas."""
    vid_nav = page.locator("flow-project-nav-list *:has(mat-icon:text-is('videocam'))").last
    if await vid_nav.count() > 0:
        try:
            await vid_nav.click(timeout=5000)
            await asyncio.sleep(2.0)
        except Exception:
            pass


async def clear_prompt_box_ingredients(page) -> None:
    """Dismiss any open popover and clear existing ingredient chips in the prompt box."""
    for _ in range(3):
        try:
            await page.keyboard.press("Escape")
            await asyncio.sleep(0.3)
        except Exception:
            break

    rem_btns = page.locator("flow-creative-agent-prompt-box button[aria-label='Remove']")
    while await rem_btns.count() > 0:
        try:
            await rem_btns.first.click(timeout=3000)
            await asyncio.sleep(0.4)
        except Exception:
            break


async def attach_frame_ingredient(page, file_path: Path) -> None:
    """Upload and attach a reference frame image as an ingredient chip in Google Flow."""
    if not file_path.is_file():
        raise FileNotFoundError(f"Reference frame not found: {file_path}")

    for _ in range(2):
        try:
            await page.keyboard.press("Escape")
            await asyncio.sleep(0.3)
        except Exception:
            break

    chip_loc = page.locator("flow-creative-agent-prompt-box flow-image-ingredient-chip")
    before_chips = await chip_loc.count()

    add_btn = page.locator("button.add-menu-trigger").last
    await add_btn.click(timeout=8000)
    await asyncio.sleep(1.5)

    upload_btn = page.locator("button.sidebar-upload-btn").first
    async with page.expect_file_chooser(timeout=15000) as fc_info:
        await upload_btn.click(timeout=8000)
    chooser = await fc_info.value

    unique_filename = f"{file_path.stem}_{uuid.uuid4().hex[:6]}{file_path.suffix}"
    try:
        async with page.expect_response(lambda r: "maseQ" in r.url, timeout=45000):
            await chooser.set_files({
                "name": unique_filename,
                "mimeType": "image/png",
                "buffer": file_path.read_bytes(),
            })
    except Exception:
        await asyncio.sleep(5.0)

    await asyncio.sleep(2.5)

    picker = page.locator("flow-add-menu-popover-content").first
    if not await picker.is_visible():
        await add_btn.click(timeout=8000)
        await asyncio.sleep(1.5)

    opt = picker.locator("button.asset-item[role='option']").first
    await opt.wait_for(state="visible", timeout=15000)
    await opt.click(timeout=5000)
    await asyncio.sleep(1.2)

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
            f"Failed to attach image chip for {file_path.name} (chips {before_chips} -> {after_chips})"
        )


async def await_flow_video(
    page,
    baseline_keys: Set[str],
    timeout_s: float = 360.0,
) -> Tuple[str, str]:
    """Poll Google Flow for completed video generation and return (uuid, video_src)."""
    t0 = time.monotonic()
    deadline = t0 + timeout_s
    started = False

    while time.monotonic() < deadline:
        gates = page.locator(LIVE_GATE_LOCATOR)
        if await gates.count() > 0:
            approve = gates.first.locator(
                "div[role='radio'].option-row:not(.read-only):has(mat-icon:text-is('check'))"
            ).first
            if await approve.count() > 0 and await approve.is_visible():
                await approve.click(timeout=5000)
                await asyncio.sleep(2.0)

        state = await page.evaluate(VIDEO_STATE_JS)
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
                break

        if (started or new_idx >= 0) and pending == 0 and new_idx >= 0 and new_key:
            tile = page.locator(FINISHED_TILE_LOCATOR).nth(new_idx)
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
                return f"flow_{token[:24]}", vid_src

        if (time.monotonic() - t0) > 15.0:
            panel = page.locator("flow-agent-panel")
            if await panel.count() > 0:
                text = await panel.last.inner_text()
                ru_err = "\u0427\u0442\u043e-\u0442\u043e \u043f\u043e\u0448\u043b\u043e \u043d\u0435 \u0442\u0430\u043a"
                if "Something went wrong" in text or ru_err in text:
                    raise RuntimeError("Google Flow returned error in agent panel.")
            if int(time.monotonic() - t0) % 16 < 2 and pending == 0:
                await switch_to_videos_tab(page)

        await asyncio.sleep(2.0)

    raise TimeoutError(f"Timed out after {timeout_s}s waiting for Google Flow video generation.")


async def save_native_video(
    page,
    vid_src: str,
    video_uuid: str,
    out_path: Path,
) -> Path:
    """Download and save the generated video stream, retaining native AAC audio."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    video_bytes: Optional[bytes] = None
    try:
        resp = await page.request.get(vid_src, timeout=180000, max_redirects=5)
        if resp.status < 300:
            body = await resp.body()
            if len(body) > 1000 and body[4:8] == b"ftyp":
                video_bytes = body
    except Exception:
        pass

    if video_bytes is None:
        body_b64 = await page.evaluate(
            """async (src) => {
                const resp = await fetch(src, { credentials: 'omit' });
                const blob = await resp.blob();
                return new Promise((resolve, reject) => {
                    const reader = new FileReader();
                    reader.onloadend = () => resolve(reader.result.split(',')[1]);
                    reader.onerror = reject;
                    reader.readAsDataURL(blob);
                });
            }""",
            vid_src,
        )
        import base64
        video_bytes = base64.b64decode(body_b64)

    if len(video_bytes) < 1000:
        raise ValueError(f"Downloaded video too small ({len(video_bytes)} bytes)")
    out_path.write_bytes(video_bytes)

    # Ensure FastStart layout (moov before mdat)
    try:
        header = video_bytes[:262144]
        moov_idx = header.find(b"moov")
        mdat_idx = header.find(b"mdat")
        if moov_idx == -1 or (mdat_idx != -1 and moov_idx > mdat_idx):
            import shutil, subprocess
            try:
                import imageio_ffmpeg
                ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
            except Exception:
                ffmpeg_exe = shutil.which("ffmpeg")
            if ffmpeg_exe:
                tmp_fs = out_path.with_suffix(".fs.tmp.mp4")
                cmd = [ffmpeg_exe, "-y", "-i", str(out_path), "-c", "copy", "-movflags", "+faststart", str(tmp_fs)]
                proc = subprocess.run(cmd, capture_output=True, timeout=30)
                if proc.returncode == 0 and tmp_fs.is_file() and tmp_fs.stat().st_size > 1000:
                    tmp_fs.replace(out_path)
    except Exception:
        pass

    return out_path
