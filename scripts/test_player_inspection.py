"""
scripts/test_player_inspection.py
Automated inspection script for output/index.html and index.html using Playwright.
"""

from pathlib import Path
from playwright.sync_api import sync_playwright


def inspect_player():
    root = Path(__file__).resolve().parent.parent
    targets = [
        ("root_index", root / "index.html"),
        ("output_index", root / "output" / "index.html"),
    ]

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        for label, path in targets:
            print(f"\n==========================================")
            print(f"Target: {label} ({path})")
            print(f"==========================================")
            page = browser.new_page()

            console_msgs = []
            page.on("console", lambda msg: console_msgs.append(f"[{msg.type}] {msg.text}"))
            failed_reqs = []
            page.on("requestfailed", lambda req: failed_reqs.append(f"{req.url}: {req.failure}"))

            page.goto(path.as_uri())

            # Basic checks
            title = page.title()
            print(f"Page Title: {title}")
            video_src = page.eval_on_selector("#main-player", "el => el.src")
            video_current = page.eval_on_selector("#main-player", "el => el.currentSrc")
            video_err = page.eval_on_selector("#main-player", "el => el.error ? el.error.message : null")
            print(f"Initial Video src: {video_src}")
            print(f"Initial Video currentSrc: {video_current}")
            print(f"Initial Video error: {video_err}")

            tabs = page.query_selector_all("#lesson-tabs .tab-btn")
            print(f"Lesson Tabs Count: {len(tabs)}")

            tabs_count = len(tabs)
            for idx in range(tabs_count):
                current_tabs = page.query_selector_all("#lesson-tabs .tab-btn")
                current_tabs[idx].click()
                active_title = page.eval_on_selector("#active-title", "el => el.textContent")
                current_src = page.eval_on_selector("#main-player", "el => el.src")
                clip_btns = page.query_selector_all("#clip-buttons button")
                cards = page.query_selector_all("#scenes-container .scene-card")
                print(f"  Lesson {idx}: clips={len(clip_btns)}, scenes={len(cards)}, src={current_src}")

            # Test viewports / responsive layout
            viewports = [
                ("Desktop 1920x1080", 1920, 1080),
                ("Desktop 1280x720", 1280, 720),
                ("Tablet Landscape 1024x768", 1024, 768),
                ("Tablet Portrait 768x1024", 768, 1024),
                ("Mobile iPhone 11 414x896", 414, 896),
                ("Mobile iPhone SE 375x667", 375, 667),
            ]
            print("\nResponsive Viewport Audit:")
            for vp_name, w, h in viewports:
                page.set_viewport_size({"width": w, "height": h})
                grid_cols = page.eval_on_selector(".grid", "el => window.getComputedStyle(el).gridTemplateColumns")
                body_scroll_w = page.evaluate("() => document.body.scrollWidth")
                body_client_w = page.evaluate("() => document.body.clientWidth")
                has_overflow = body_scroll_w > body_client_w
                print(f"  [{vp_name}] Grid cols: '{grid_cols}', Body: scrollWidth={body_scroll_w}, clientWidth={body_client_w}, Horizontal Overflow: {has_overflow}")

            print(f"\nConsole Errors Count: {len(console_msgs)}")
            for msg in console_msgs[:5]:
                print(f"  Console: {msg}")
            print(f"Failed Network Requests Count: {len(failed_reqs)}")
            for req in failed_reqs[:5]:
                print(f"  Failed Req: {req}")

            page.close()

        browser.close()


if __name__ == "__main__":
    inspect_player()
