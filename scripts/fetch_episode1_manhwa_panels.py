"""Fetch actual sequential manhwa panels from Episode 1..6 of 'I Became the Tyrant of a Defense Game' on LINE Webtoon."""

from __future__ import annotations

import io
from pathlib import Path
import re
import urllib.request

from PIL import Image

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Referer": "https://www.webtoons.com/",
}


def get_html(url: str) -> str:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.read().decode("utf-8", "ignore")


def main() -> int:
    list_url = "https://www.webtoons.com/en/fantasy/i-became-the-tyrant-of-a-defense-game/list?title_no=10765"
    html = get_html(list_url)
    links = re.findall(
        r'href="(https://www\.webtoons\.com/en/fantasy/i-became-the-tyrant-of-a-defense-game/[^"]+viewer\?title_no=10765&episode_no=\d+)"',
        html,
    )
    print(f"Found {len(set(links))} episode links on page 1:")
    for u in sorted(set(links)):
        print(" ", u)

    # Also test direct episode_no=1..6 viewer URLs
    for ep in range(1, 7):
        ep_url = f"https://www.webtoons.com/en/fantasy/i-became-the-tyrant-of-a-defense-game/episode-{ep}/viewer?title_no=10765&episode_no={ep}"
        try:
            ep_html = get_html(ep_url)
            title_m = re.search(r"<title>([^<]+)</title>", ep_html)
            imgs = re.findall(r'data-url="(https://webtoon-phinf\.pstatic\.net/[^"]+)"', ep_html)
            print(f"Episode {ep}: title={title_m.group(1) if title_m else '?'} | {len(imgs)} panel strips")
        except Exception as exc:
            print(f"Episode {ep} error: {exc}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
