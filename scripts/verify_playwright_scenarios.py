import json
import os
import sys
import time
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from playwright.sync_api import sync_playwright

REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = REPO_ROOT / "output"
SCREENSHOT_DIR = OUTPUT_DIR / "test_screenshots"
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

class QuietHTTPHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(REPO_ROOT), **kwargs)

    def log_message(self, format, *args):
        pass

def start_test_server():
    server = ThreadingHTTPServer(("127.0.0.1", 0), QuietHTTPHandler)
    port = server.server_port
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, port

def run_5_scenarios():
    server, port = start_test_server()
    target_url = f"http://127.0.0.1:{port}/output/index.html"
    print(f"Testing target: {target_url}")

    results = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        # Scenario 1: Initial Playback & Media Loading
        print("\n=== Scenario 1: Initial Playback & Media Loading ===")
        context1 = browser.new_context(viewport={"width": 1920, "height": 1080})
        page1 = context1.new_page()
        network_responses = []
        page1.on("response", lambda res: network_responses.append({"url": res.url, "status": res.status}))
        console_msgs = []
        page1.on("console", lambda msg: console_msgs.append(f"[{msg.type}] {msg.text}"))

        t0 = time.time()
        page1.goto(target_url, wait_until="networkidle")
        load_time = time.time() - t0

        v_src = page1.eval_on_selector("#main-player", "el => el.src")
        v_current = page1.eval_on_selector("#main-player", "el => el.currentSrc")
        v_error = page1.eval_on_selector("#main-player", "el => el.error ? el.error.message : null")
        v_ready = page1.eval_on_selector("#main-player", "el => el.readyState")
        v_network = page1.eval_on_selector("#main-player", "el => el.networkState")

        err_404s = [r for r in network_responses if r["status"] == 404]
        media_statuses = [r["status"] for r in network_responses if ".mp4" in r["url"]]

        # Hero link check
        hero_href = page1.eval_on_selector("a[href*='dsp_defense']", "el => el.href")
        hero_res = page1.request.get(hero_href)

        s1_pass = (len(err_404s) == 0) and (v_error is None) and (hero_res.status == 200) and (200 in media_statuses or 206 in media_statuses or len(media_statuses) > 0)
        results["scenario_1_media_load"] = {
            "status": "PASS" if s1_pass else "FAIL",
            "load_time_sec": round(load_time, 3),
            "video_src": v_src,
            "video_error": v_error,
            "video_ready_state": v_ready,
            "video_network_state": v_network,
            "error_404_count": len(err_404s),
            "console_errors_count": len(console_msgs),
            "hero_href": hero_href,
            "hero_status": hero_res.status,
            "media_response_statuses": media_statuses
        }
        print(f"Scenario 1 Status: {results['scenario_1_media_load']['status']}")
        print(f"  404s: {len(err_404s)}, Video error: {v_error}, Media statuses: {media_statuses}")
        context1.close()

        # Scenario 2: WebVTT Subtitle Mounting & Closed Captions
        print("\n=== Scenario 2: WebVTT Subtitle Mounting & Closed Captions ===")
        context2 = browser.new_context(viewport={"width": 1920, "height": 1080})
        page2 = context2.new_page()
        page2.goto(target_url, wait_until="networkidle")

        track_count = page2.eval_on_selector_all("#main-player track", "tracks => tracks.length")
        track_info = page2.evaluate("""() => {
            const v = document.getElementById('main-player');
            const t = v.querySelector('track');
            const tt = v.textTracks;
            return {
                hasTrack: t !== null,
                kind: t ? t.kind : null,
                srclang: t ? t.srclang : null,
                label: t ? t.label : null,
                srcStartsWithBlob: t ? t.src.startsWith('blob:') : false,
                textTracksLength: tt ? tt.length : 0,
                firstTextTrackMode: (tt && tt.length > 0) ? tt[0].mode : null
            };
        }""")

        s2_pass = (track_count >= 1) and track_info["hasTrack"] and track_info["srcStartsWithBlob"] and (track_info["textTracksLength"] >= 1)
        results["scenario_2_subtitles"] = {
            "status": "PASS" if s2_pass else "FAIL",
            "track_count": track_count,
            "track_details": track_info
        }
        print(f"Scenario 2 Status: {results['scenario_2_subtitles']['status']}")
        print(f"  Tracks mounted: {track_count}, Blob URL: {track_info['srcStartsWithBlob']}, Label: {track_info['label']}")
        context2.close()

        # Scenario 3: Lesson Tab Switching & Scene Clip Selection
        print("\n=== Scenario 3: Lesson Tab Switching & Scene Clip Selection ===")
        context3 = browser.new_context(viewport={"width": 1920, "height": 1080})
        page3 = context3.new_page()
        page3.goto(target_url, wait_until="networkidle")

        # Verify non-destructive tab click
        survival_check = page3.evaluate("""() => {
            const btn0 = document.querySelector('#lesson-tabs .tab-btn');
            window.__anchorBtn0 = btn0;
            const btn1 = document.querySelectorAll('#lesson-tabs .tab-btn')[1];
            btn1.click();
            return document.body.contains(window.__anchorBtn0);
        }""")

        # Verify active class on tab 1
        tab1_active = page3.eval_on_selector("#lesson-tabs .tab-btn:nth-child(2)", "el => el.classList.contains('active')")
        tab0_active = page3.eval_on_selector("#lesson-tabs .tab-btn:nth-child(1)", "el => el.classList.contains('active')")

        # Test scene clip selection
        clip1_click = page3.evaluate("""() => {
            const clip1 = document.querySelectorAll('#clip-buttons .tab-btn')[1];
            if (clip1) clip1.click();
            const fullBtn = document.querySelectorAll('#clip-buttons .tab-btn')[0];
            const card1 = document.querySelectorAll('#scenes-container .scene-card')[0];
            return {
                clip1_active: clip1 ? clip1.classList.contains('active') : false,
                full_active: fullBtn ? fullBtn.classList.contains('active') : false,
                card1_active_scene: card1 ? card1.classList.contains('active-scene') : false
            };
        }""")

        s3_pass = survival_check and tab1_active and (not tab0_active) and clip1_click["clip1_active"] and (not clip1_click["full_active"]) and clip1_click["card1_active_scene"]
        results["scenario_3_tabs_clips"] = {
            "status": "PASS" if s3_pass else "FAIL",
            "dom_node_survived_tab_switch": survival_check,
            "tab_active_toggled": tab1_active and not tab0_active,
            "scene_clip_active": clip1_click["clip1_active"],
            "full_button_deactivated": not clip1_click["full_active"],
            "scene_card_highlighted": clip1_click["card1_active_scene"]
        }
        print(f"Scenario 3 Status: {results['scenario_3_tabs_clips']['status']}")
        print(f"  DOM survival: {survival_check}, Clip active: {clip1_click['clip1_active']}, Card active-scene: {clip1_click['card1_active_scene']}")
        context3.close()

        # Scenario 4: Playback Rate Controls
        print("\n=== Scenario 4: Playback Rate Controls ===")
        context4 = browser.new_context(viewport={"width": 1920, "height": 1080})
        page4 = context4.new_page()
        page4.goto(target_url, wait_until="networkidle")

        rates_tested = []
        rate_buttons = page4.query_selector_all(".rate-btn")
        for btn in rate_buttons:
            text = btn.inner_text().strip().replace("x", "")
            expected_rate = float(text)
            btn.click()
            actual_rate = page4.eval_on_selector("#main-player", "el => el.playbackRate")
            is_active = btn.evaluate("el => el.classList.contains('active')")
            rates_tested.append({
                "expected": expected_rate,
                "actual": actual_rate,
                "active_class": is_active,
                "matched": abs(expected_rate - actual_rate) < 0.01
            })

        s4_pass = (len(rates_tested) == 5) and all(r["matched"] for r in rates_tested)
        results["scenario_4_playback_rates"] = {
            "status": "PASS" if s4_pass else "FAIL",
            "rates_count": len(rates_tested),
            "rates_tested": rates_tested
        }
        print(f"Scenario 4 Status: {results['scenario_4_playback_rates']['status']}")
        for r in rates_tested:
            print(f"  Rate {r['expected']}x -> actual {r['actual']}x (active={r['active_class']}, matched={r['matched']})")
        context4.close()

        # Scenario 5: Responsive Multi-Device Reflow
        print("\n=== Scenario 5: Responsive Multi-Device Reflow ===")
        viewports = [
            ("Desktop 1920x1080", 1920, 1080),
            ("Laptop 1366x768", 1366, 768),
            ("Tablet 768x1024", 768, 1024),
            ("Mobile 375x667", 375, 667)
        ]
        context5 = browser.new_context()
        page5 = context5.new_page()
        page5.goto(target_url, wait_until="networkidle")

        vp_results = []
        for name, w, h in viewports:
            page5.set_viewport_size({"width": w, "height": h})
            page5.wait_for_timeout(200)
            metrics = page5.evaluate("""() => {
                const p = document.getElementById('main-player');
                const pBox = p.getBoundingClientRect();
                const bScrollW = document.body.scrollWidth;
                const bClientW = document.body.clientWidth;
                const comp = window.getComputedStyle(p);
                return {
                    playerTop: pBox.top,
                    playerHeight: pBox.height,
                    playerWidth: pBox.width,
                    aspectRatio: comp.aspectRatio,
                    scrollWidth: bScrollW,
                    clientWidth: bClientW,
                    hasHorizontalOverflow: bScrollW > bClientW
                };
            }""")
            vp_results.append({
                "profile": name,
                "viewport": f"{w}x{h}",
                "player_top_px": round(metrics["playerTop"], 1),
                "aspect_ratio": metrics["aspectRatio"],
                "scroll_width": metrics["scrollWidth"],
                "client_width": metrics["clientWidth"],
                "has_horizontal_overflow": metrics["hasHorizontalOverflow"]
            })

        s5_pass = all(not v["has_horizontal_overflow"] for v in vp_results)
        results["scenario_5_responsive"] = {
            "status": "PASS" if s5_pass else "FAIL",
            "viewports": vp_results
        }
        print(f"Scenario 5 Status: {results['scenario_5_responsive']['status']}")
        for v in vp_results:
            print(f"  {v['profile']}: top={v['player_top_px']}px, aspect={v['aspect_ratio']}, overflow={v['has_horizontal_overflow']}")
        context5.close()

        browser.close()

    out_file = OUTPUT_DIR / "playwright_scenario_verification.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\nAll 5 Scenarios Executed! Saved to {out_file}")

if __name__ == "__main__":
    run_5_scenarios()
