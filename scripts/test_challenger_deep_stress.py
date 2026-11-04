"""
scripts/test_challenger_deep_stress.py
Empirical Challenger Adversarial Stress Test Suite for Google Flow Video HTML Player.
"""
import json
import os
import sys
import time
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from playwright.sync_api import sync_playwright

REPO_ROOT = Path("e:/ANTIGRAVITY/flow_video_testbench").resolve()
OUTPUT_DIR = REPO_ROOT / "output"
SCREENSHOT_DIR = OUTPUT_DIR / "challenger_screenshots"
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

class QuietHTTPHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(REPO_ROOT), **kwargs)

    def log_message(self, format, *args):
        pass

def start_server():
    server = ThreadingHTTPServer(("127.0.0.1", 0), QuietHTTPHandler)
    port = server.server_port
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, port

def run_challenger_stress():
    server, port = start_server()
    target_url = f"http://127.0.0.1:{port}/output/index.html"
    print(f"Challenger server active at: {target_url}", flush=True)

    results = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "target_url": target_url,
        "checks": {}
    }

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1920, "height": 1080})
        page = context.new_page()

        page_errors = []
        page.on("pageerror", lambda err: page_errors.append(str(err)))
        failed_requests = []
        page.on("response", lambda r: failed_requests.append({"url": r.url, "status": r.status}) if r.status >= 400 else None)

        page.goto(target_url, wait_until="networkidle")
        page.wait_for_timeout(300)

        # 1. RAPID TAB CLICKING STRESS (40 clicks across tabs)
        print("[1] Rapid Tab Switching Stress (40 clicks)...", flush=True)
        tab_count = page.locator("#lesson-tabs .tab-btn").count()
        save_btn0 = page.evaluate("() => { window.__btn0 = document.querySelector('#lesson-tabs .tab-btn'); return window.__btn0 !== null; }")

        t0 = time.time()
        for i in range(40):
            idx = i % tab_count
            page.locator(f"#lesson-tabs .tab-btn >> nth={idx}").click()
            time.sleep(0.02)
        tab_elapsed = time.time() - t0

        btn0_survived = page.evaluate("() => document.body.contains(window.__btn0)")
        settled_tab_active = page.locator(f"#lesson-tabs .tab-btn >> nth={39 % tab_count}").get_attribute("class") or ""

        results["checks"]["rapid_tabs"] = {
            "clicks": 40,
            "elapsed_sec": round(tab_elapsed, 3),
            "btn0_survived_in_dom": btn0_survived,
            "has_active_class": "active" in settled_tab_active,
            "page_errors": len(page_errors)
        }

        # 2. PLAYBACK RATE VERIFICATION & PERSISTENCE
        print("[2] Playback Rate Verification (0.75, 1.0, 1.25, 1.5, 2.0)...", flush=True)
        speeds = [0.75, 1.0, 1.25, 1.5, 2.0]
        speed_results = {}
        for sp in speeds:
            btn = page.locator(f".rate-btn:has-text('{sp}x')")
            btn.click()
            actual_rate = page.evaluate("() => document.getElementById('main-player').playbackRate")
            active_btn_count = page.locator(".rate-btn.active").count()
            speed_results[f"{sp}x"] = {
                "button_active": "active" in (btn.get_attribute("class") or ""),
                "actual_rate": actual_rate,
                "single_active_button": active_btn_count == 1,
                "matches": abs(actual_rate - sp) < 1e-4
            }

        # Check rate persistence across tab switch
        page.locator(".rate-btn:has-text('2.0x')").click()
        page.locator("#lesson-tabs .tab-btn >> nth=1").click()
        page.wait_for_timeout(200)
        rate_after_tab_switch = page.evaluate("() => document.getElementById('main-player').playbackRate")
        results["checks"]["playback_rates"] = {
            "rates": speed_results,
            "all_rates_matched": all(v["matches"] and v["single_active_button"] for v in speed_results.values()),
            "rate_after_tab_switch": rate_after_tab_switch
        }

        # 3. SCRUBBER & CHAPTER SEEKING
        print("[3] Scrubber & Chapter/Scene Seeking...", flush=True)
        # Select lesson 0
        page.locator("#lesson-tabs .tab-btn >> nth=0").click()
        page.wait_for_timeout(200)
        scene_count = page.locator("#scenes-container .scene-card").count()
        seek_checks = []
        for s_idx in range(scene_count):
            card = page.locator(f"#scenes-container .scene-card >> nth={s_idx}")
            card.click()
            time.sleep(0.05)
            is_active_card = "active-scene" in (card.get_attribute("class") or "")
            clip_btn = page.locator(f"#clip-buttons .tab-btn >> nth={s_idx + 1}")
            is_active_clip = "active" in (clip_btn.get_attribute("class") or "")
            src_val = page.locator("#main-player").get_attribute("src") or ""
            seek_checks.append({
                "scene_idx": s_idx,
                "is_active_card": is_active_card,
                "is_active_clip": is_active_clip,
                "has_src": len(src_val) > 0 and not src_val.startswith("output/output")
            })

        # Test video scrubbing (setting currentTime and checking seeked)
        scrub_check = page.evaluate("""() => {
            const v = document.getElementById('main-player');
            const initialTime = v.currentTime;
            v.currentTime = 2.5;
            return {
                initialTime: initialTime,
                newTime: v.currentTime,
                seeking: v.seeking !== undefined
            };
        }""")

        results["checks"]["scrubber_and_scenes"] = {
            "scene_cards_tested": len(seek_checks),
            "all_scenes_coordinated": all(c["is_active_card"] and c["is_active_clip"] and c["has_src"] for c in seek_checks),
            "scrub_check": scrub_check
        }

        # 4. SUBTITLE MOUNTING & CUE RENDERING
        print("[4] Subtitle Mounting & Cue Rendering...", flush=True)
        sub_results = {}
        for l_idx in range(tab_count):
            page.locator(f"#lesson-tabs .tab-btn >> nth={l_idx}").click()
            page.wait_for_timeout(150)
            sub_eval = page.evaluate("""() => {
                const v = document.getElementById('main-player');
                const tracks = Array.from(v.querySelectorAll('track'));
                const tt = v.textTracks;
                return {
                    track_elements_count: tracks.length,
                    track_kinds: tracks.map(t => t.kind),
                    track_labels: tracks.map(t => t.label),
                    track_langs: tracks.map(t => t.srclang),
                    track_srcs_blob: tracks.map(t => t.src.startsWith('blob:')),
                    text_tracks_length: tt ? tt.length : 0,
                    text_track_mode: (tt && tt.length > 0) ? tt[0].mode : null
                };
            }""")
            sub_results[f"lesson_{l_idx}"] = sub_eval

        results["checks"]["subtitles"] = {
            "lessons_checked": len(sub_results),
            "all_lessons_have_single_sub_track": all(s["track_elements_count"] == 1 and s["text_track_mode"] == "showing" for s in sub_results.values()),
            "details": sub_results
        }

        # 5. VIEWPORT SCALING & OVERFLOW AUDIT (320, 375, 768, 1366, 1920, 2560)
        print("[5] Viewport Scaling & Overflow Audit...", flush=True)
        viewports = [
            (320, 568, "320px_mobile_small"),
            (375, 667, "375px_mobile_se"),
            (768, 1024, "768px_tablet_portrait"),
            (1366, 768, "1366px_laptop"),
            (1920, 1080, "1920px_fhd"),
            (2560, 1440, "2560px_2k")
        ]
        vp_results = {}
        for w, h, name in viewports:
            page.set_viewport_size({"width": w, "height": h})
            page.wait_for_timeout(100)
            metrics = page.evaluate("""() => {
                const docEl = document.documentElement;
                const body = document.body;
                const player = document.getElementById('main-player');
                const pRect = player.getBoundingClientRect();
                return {
                    window_inner_w: window.innerWidth,
                    doc_scroll_w: docEl.scrollWidth,
                    doc_client_w: docEl.clientWidth,
                    body_scroll_w: body.scrollWidth,
                    body_client_w: body.clientWidth,
                    has_doc_overflow: docEl.scrollWidth > window.innerWidth,
                    has_body_overflow: body.scrollWidth > body.clientWidth,
                    player_top: Math.round(pRect.top),
                    player_height: Math.round(pRect.height),
                    player_width: Math.round(pRect.width),
                    aspect_ratio: Math.round((pRect.width / pRect.height) * 100) / 100
                };
            }""")
            metrics["screenshot"] = str(SCREENSHOT_DIR / f"vp_{name}.png")
            page.screenshot(path=metrics["screenshot"])
            vp_results[name] = metrics

        results["checks"]["viewports"] = {
            "all_viewports_zero_overflow": all(not v["has_doc_overflow"] and not v["has_body_overflow"] for v in vp_results.values()),
            "details": vp_results
        }

        # 6. ALL MEDIA URL INTEGRITY (Zero 404s)
        print("[6] Media URL Integrity (Zero 404s)...", flush=True)
        all_media_urls = page.evaluate("""() => {
            const urls = [];
            LESSONS.forEach(l => {
                if (l.project && l.project.assembled_video_url) {
                    urls.push(resolveMediaPath(l.project.assembled_video_url));
                }
                if (l.project && l.project.scenes) {
                    l.project.scenes.forEach(s => {
                        if (s.video_url) urls.push(resolveMediaPath(s.video_url));
                    });
                }
            });
            // Also add hero links
            document.querySelectorAll('.hero-card a').forEach(a => urls.push(a.getAttribute('href')));
            return urls;
        }""")

        media_status_checks = []
        for rel_url in all_media_urls:
            full_req_url = f"http://127.0.0.1:{port}/output/{rel_url}" if not rel_url.startswith("http") and not rel_url.startswith("/") else (f"http://127.0.0.1:{port}{rel_url}" if rel_url.startswith("/") else rel_url)
            res = page.request.get(full_req_url)
            media_status_checks.append({
                "url": rel_url,
                "full_url": full_req_url,
                "status": res.status,
                "ok": res.status in (200, 206)
            })

        failing_media = [m for m in media_status_checks if not m["ok"]]
        results["checks"]["media_integrity"] = {
            "total_urls_checked": len(media_status_checks),
            "failing_urls_count": len(failing_media),
            "all_media_accessible": len(failing_media) == 0,
            "failing_sample": failing_media[:5]
        }

        # Global page error audit
        results["checks"]["global_errors"] = {
            "page_errors_count": len(page_errors),
            "page_errors": page_errors,
            "failed_requests_count": len(failed_requests),
            "failed_requests": failed_requests[:10]
        }

        browser.close()

    out_json = OUTPUT_DIR / "challenger_deep_stress_results.json"
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\nAll tests completed. Report saved to: {out_json}", flush=True)
    return results

if __name__ == "__main__":
    res = run_challenger_stress()
    sys.exit(0)
