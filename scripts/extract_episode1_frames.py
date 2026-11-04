"""Download LINE Webtoon Episode 1..3 strips, stitch vertically, and segment into clean uncut manhwa frames."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import io
from pathlib import Path
import re
import urllib.request

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Referer": "https://www.webtoons.com/",
}

BASE_OUT = Path("output/ttd_arcane_characters/episode1_frames")


def fetch_bytes(url: str) -> bytes:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.read()


def download_episode_strips(ep_no: int) -> list[Image.Image]:
    ep_url = f"https://www.webtoons.com/en/fantasy/i-became-the-tyrant-of-a-defense-game/episode-{ep_no}/viewer?title_no=10765&episode_no={ep_no}"
    html = fetch_bytes(ep_url).decode("utf-8", "ignore")
    m = re.search(r'id="_imageList"[^>]*>(.*?)</div>', html, re.S)
    block = m.group(1) if m else html
    img_urls = re.findall(r'data-url="(https://webtoon-phinf\.pstatic\.net/[^"]+)"', block)
    print(f"[Ep {ep_no}] Downloading {len(img_urls)} full-width comic strips in parallel...", flush=True)

    def _dl(idx_url: tuple[int, str]) -> tuple[int, Image.Image | None]:
        idx, u = idx_url
        try:
            raw = fetch_bytes(u)
            im = Image.open(io.BytesIO(raw)).convert("RGB")
            return (idx, im) if im.width >= 600 else (idx, None)
        except Exception:
            return idx, None

    with ThreadPoolExecutor(max_workers=16) as pool:
        results = list(pool.map(_dl, enumerate(img_urls)))
    results.sort(key=lambda x: x[0])
    return [im for _, im in results if im is not None]


def segment_into_panels(strips: list[Image.Image], ep_no: int) -> list[Path]:
    ep_dir = BASE_OUT / f"ep{ep_no:02d}"
    ep_dir.mkdir(parents=True, exist_ok=True)
    for old_f in ep_dir.glob("frame_*.jpg"):
        old_f.unlink()

    target_w = max(im.width for im in strips)
    arrays = [np.asarray(im, dtype=np.uint8) for im in strips if im.width == target_w]
    full = np.concatenate(arrays, axis=0)
    h, w, _ = full.shape
    print(f"[Ep {ep_no}] Stitched canvas: {w}x{h}px. Segmenting along panel gutters...", flush=True)

    # A row is a gutter if pixel std across width is < 4.5 and mean is near-white (>242) or near-black (<14)
    row_std = full.astype(np.float32).std(axis=(1, 2))
    row_mean = full.astype(np.float32).mean(axis=(1, 2))
    is_gutter = (row_std < 4.5) & ((row_mean > 242.0) | (row_mean < 14.0))

    panels: list[tuple[int, int]] = []
    in_panel = False
    start_y = 0
    gutter_run = 0
    for y in range(h):
        if is_gutter[y]:
            gutter_run += 1
            if in_panel and gutter_run >= 18:
                end_y = y - gutter_run + 1
                if end_y - start_y >= 260:
                    panels.append((start_y, end_y))
                in_panel = False
        else:
            if not in_panel:
                start_y = y
                in_panel = True
            gutter_run = 0
    if in_panel and h - start_y >= 260:
        panels.append((start_y, h))

    saved_paths: list[Path] = []
    frame_idx = 1
    for y0, y1 in panels:
        ph = y1 - y0
        # If a single continuous scroll panel is super tall (> 1800px), slice at local minimum std rows every ~1100px
        cur = y0
        while cur < y1:
            if y1 - cur <= 1650:
                sub_y1 = y1
            else:
                search_start = cur + 800
                search_end = min(cur + 1500, y1 - 250)
                best_offset = int(np.argmin(row_std[search_start:search_end]))
                sub_y1 = search_start + best_offset
            crop = full[cur:sub_y1]
            # Keep only panels with rich visual content (overall std > 18)
            if crop.shape[0] >= 260 and crop.astype(np.float32).std() > 18.0:
                out_p = ep_dir / f"frame_{frame_idx:03d}.jpg"
                Image.fromarray(crop).save(out_p, quality=94)
                saved_paths.append(out_p)
                frame_idx += 1
            cur = sub_y1

    print(f"[Ep {ep_no}] Extracted {len(saved_paths)} clean visual panels into {ep_dir}", flush=True)
    return saved_paths


def build_contact_grids(ep_no: int, frames: list[Path], per_grid: int = 36, cols: int = 6) -> list[Path]:
    grid_paths: list[Path] = []
    tw, th = 230, 300
    try:
        font = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", 15)
    except Exception:
        font = ImageFont.load_default()

    for chunk_i in range(0, len(frames), per_grid):
        chunk = frames[chunk_i : chunk_i + per_grid]
        rows = (len(chunk) + cols - 1) // cols
        grid = Image.new("RGB", (cols * tw, rows * th), (16, 18, 24))
        draw = ImageDraw.Draw(grid)
        for i, fp in enumerate(chunk):
            r, c = divmod(i, cols)
            x0, y0 = c * tw, r * th
            im = Image.open(fp).convert("RGB")
            im.thumbnail((tw - 8, th - 28), Image.Resampling.LANCZOS)
            grid.paste(im, (x0 + (tw - im.width) // 2, y0 + 24 + (th - 28 - im.height) // 2))
            draw.rectangle([x0 + 2, y0 + 2, x0 + tw - 2, y0 + 22], fill=(28, 32, 46))
            draw.text((x0 + 6, y0 + 4), f"Ep{ep_no:02d} #{fp.stem.split('_')[1]}", fill=(245, 205, 110), font=font)
        gp = BASE_OUT / f"ep{ep_no:02d}_grid_part{(chunk_i // per_grid) + 1}.jpg"
        grid.save(gp, quality=90)
        grid_paths.append(gp)
    return grid_paths


def main() -> int:
    BASE_OUT.mkdir(parents=True, exist_ok=True)
    for ep in (1, 2, 3):
        strips = download_episode_strips(ep)
        frames = segment_into_panels(strips, ep)
        grids = build_contact_grids(ep, frames)
        print(f"[Ep {ep}] Built {len(grids)} contact sheets: {[g.name for g in grids]}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
