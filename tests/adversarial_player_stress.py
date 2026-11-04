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
SCREENSHOT_DIR = OUTPUT_DIR / "test_screenshots"
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
REPORT_DIR = REPO_ROOT / ".agents" / "teamwork" / "m2_challenger_1_gen10"
REPORT_DIR.mkdir(parents=True, exist_ok=True)

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

def test_rapid_tab_switching(page, target_url):
    print("\n[STRESS TEST A] Rapid Tab Switching (20 rapid clicks in 2.0s)...", flush=True)
    page.goto(target_url, wait_until="networkidle")
    page.wait_for_timeout(500)

    # Initial memory benchmark
    init_mem = page.evaluate("() => window.performance && window.performance.memory ? window.performance.memory.usedJSHeapSize : null")

    # DEF-UI-005 verification: save node reference and verify detachment after click
    node_detachment_verified = page.evaluate("""() => {
        const btn0 = document.querySelector('#lesson-tabs .tab-btn');
        window.__savedBtn0 = btn0;
        return btn0 !== null;
    }""")

    tab_count = page.locator("#lesson-tabs .tab-btn").count()
    click_history = []
    start_time = time.time()

    # Perform 20 rapid clicks cycling through tabs 0..6
    for i in range(20):
        target_tab = i % tab_count
        # Target button
        btn = page.locator(f"#lesson-tabs .tab-btn >> nth={target_tab}")
        btn.click()
        click_history.append({"click_index": i, "tab_targeted": target_tab, "elapsed": round(time.time() - start_time, 4)})
        time.sleep(0.08)  # ~80ms interval -> ~1.6s total

    total_duration = time.time() - start_time
    page.wait_for_timeout(500)

    # Check DOM reference survival
    node_detached_after_rapid_clicks = page.evaluate("""() => {
        return !document.body.contains(window.__savedBtn0);
    }""")

    # Final memory benchmark
    final_mem = page.evaluate("() => window.performance && window.performance.memory ? window.performance.memory.usedJSHeapSize : null")
    mem_delta = (final_mem - init_mem) if (final_mem and init_mem) else None

    # Check event responsiveness after barrage: click tab 2 deliberately
    page.locator("#lesson-tabs .tab-btn >> nth=2").click()
    page.wait_for_timeout(300)
    settled_title = page.locator("#active-title").inner_text()
    settled_src = page.locator("#main-player").get_attribute("src")
    settled_tab_class = page.locator("#lesson-tabs .tab-btn >> nth=2").get_attribute("class") or ""
    # Check for Variant 5 keyword using unicode escape \u0412\u0430\u0440\u0438\u0430\u043d\u0442
    tab_responsive_after_stress = ("active" in settled_tab_class) and ("\u0412\u0430\u0440\u0438\u0430\u043d\u0442" in settled_title or "5" in settled_title)

    shot_path = SCREENSHOT_DIR / "stress_rapid_tabs.png"
    page.screenshot(path=str(shot_path), full_page=False)

    return {
        "scenario": "RAPID_TAB_SWITCHING",
        "total_clicks": len(click_history),
        "duration_sec": round(total_duration, 3),
        "clicks_per_sec": round(len(click_history) / total_duration, 2),
        "node_detachment_verified": node_detached_after_rapid_clicks,
        "initial_heap_bytes": init_mem,
        "final_heap_bytes": final_mem,
        "heap_delta_bytes": mem_delta,
        "tab_responsive_after_stress": tab_responsive_after_stress,
        "settled_title": settled_title,
        "settled_src": settled_src,
        "screenshot": str(shot_path)
    }

def test_rapid_scene_clicking(page, target_url):
    print("\n[STRESS TEST B] Rapid Scene Clicking & URL Changes...", flush=True)
    # Start on lesson 0 (4 scenes)
    page.goto(target_url, wait_until="networkidle")
    page.wait_for_timeout(300)

    initial_page_url = page.url
    scene_btn_count = page.locator("#clip-buttons .tab-btn").count()

    scene_click_results = []
    url_changes_observed = []
    play_exceptions = []

    # Rapidly click through all scene buttons (1..scene_btn_count-1) multiple times
    for cycle in range(3):
        for s_idx in range(1, scene_btn_count):
            btn = page.locator(f"#clip-buttons .tab-btn >> nth={s_idx}")
            btn_text = btn.inner_text()
            btn.click()
            time.sleep(0.05)  # 50ms rapid cadence

            current_player_src = page.locator("#main-player").get_attribute("src")
            current_page_url = page.url

            # Verify active class on scene button vs full lesson button
            classes = btn.get_attribute("class") or ""
            full_btn_classes = page.locator("#clip-buttons .tab-btn >> nth=0").get_attribute("class") or ""

            scene_click_results.append({
                "cycle": cycle,
                "scene_index": s_idx,
                "button_text": btn_text,
                "player_src": current_player_src,
                "page_url": current_page_url,
                "scene_btn_has_active": "active" in classes,
                "full_btn_has_active": "active" in full_btn_classes
            })
            if current_page_url != initial_page_url:
                url_changes_observed.append(current_page_url)

    # Test scene card clicks rapidly
    card_count = page.locator("#scenes-container .scene-card").count()
    for c_idx in range(card_count):
        card = page.locator(f"#scenes-container .scene-card >> nth={c_idx}")
        card.click()
        time.sleep(0.05)

    card_last_src = page.locator("#main-player").get_attribute("src")

    return {
        "scenario": "RAPID_SCENE_CLICKING",
        "total_scene_clicks": len(scene_click_results),
        "browser_url_modified": len(url_changes_observed) > 0,
        "browser_url_states": url_changes_observed,
        "last_player_src": card_last_src,
        "def_ui_006_confirmed": all(not r["scene_btn_has_active"] for r in scene_click_results) and all(r["full_btn_has_active"] for r in scene_click_results)
    }

def test_network_failure_handling(browser, target_url):
    print("\n[STRESS TEST C] Network Failure Handling & Unreachable Media...", flush=True)
    context = browser.new_context(viewport={"width": 1920, "height": 1080})
    page = context.new_page()

    failed_media_requests = []
    page.on("response", lambda res: failed_media_requests.append({"url": res.url, "status": res.status}) if ".mp4" in res.url and res.status >= 400 else None)

    page.goto(target_url, wait_until="networkidle")
    page.wait_for_timeout(500)

    # 1. Natural double-path 404 observation
    natural_error = page.evaluate("""() => {
        const v = document.getElementById('main-player');
        return {
            src: v.src,
            currentSrc: v.currentSrc,
            networkState: v.networkState,
            readyState: v.readyState,
            error: v.error ? { code: v.error.code, message: v.error.message } : null,
            hasErrorFeedbackUI: document.querySelector('.error-banner, .player-error, [role="alert"]') !== null
        };
    }""")

    # 2. Adversarial network failure: route all .mp4 to fail (net::ERR_CONNECTION_REFUSED or 500)
    page.route("**/*.mp4", lambda route: route.abort("connectionrefused"))
    # Switch to tab 1 to trigger new video load
    page.locator("#lesson-tabs .tab-btn >> nth=1").click()
    page.wait_for_timeout(600)

    simulated_failure_eval = page.evaluate("""() => {
        const v = document.getElementById('main-player');
        return {
            src: v.src,
            currentSrc: v.currentSrc,
            networkState: v.networkState,
            readyState: v.readyState,
            error: v.error ? { code: v.error.code, message: v.error.message } : null,
            hasErrorFeedbackUI: document.querySelector('.error-banner, .player-error, [role="alert"]') !== null
        };
    }""")

    shot_path = SCREENSHOT_DIR / "stress_network_failure.png"
    page.screenshot(path=str(shot_path), full_page=False)

    context.close()

    return {
        "scenario": "NETWORK_FAILURE_HANDLING",
        "natural_path_error": natural_error,
        "simulated_outage_error": simulated_failure_eval,
        "user_error_feedback_provided": natural_error["hasErrorFeedbackUI"] or simulated_failure_eval["hasErrorFeedbackUI"],
        "screenshot": str(shot_path)
    }

def test_mobile_touch_targets(browser, target_url):
    print("\n[STRESS TEST D] Mobile Touch Target Heights (375x667 Viewport)...", flush=True)
    context = browser.new_context(viewport={"width": 375, "height": 667})
    page = context.new_page()
    page.goto(target_url, wait_until="networkidle")
    page.wait_for_timeout(500)

    touch_target_analysis = page.evaluate("""() => {
        const targets = [];
        const selectorList = [
            { group: 'hero_links', sel: "a[href*='dsp_defense_index.html']" },
            { group: 'tab_buttons', sel: "#lesson-tabs .tab-btn" },
            { group: 'clip_buttons', sel: "#clip-buttons .tab-btn" },
            { group: 'scene_cards', sel: "#scenes-container .scene-card" }
        ];

        for (const item of selectorList) {
            const elements = document.querySelectorAll(item.sel);
            elements.forEach((el, idx) => {
                const rect = el.getBoundingClientRect();
                targets.push({
                    group: item.group,
                    index: idx,
                    text: el.innerText.trim().substring(0, 35),
                    width: Math.round(rect.width * 10) / 10,
                    height: Math.round(rect.height * 10) / 10,
                    top: Math.round(rect.top * 10) / 10,
                    left: Math.round(rect.left * 10) / 10,
                    passes_apple_hig_44px: rect.height >= 44 && rect.width >= 44,
                    passes_wcag_24px: rect.height >= 24 && rect.width >= 24
                });
            });
        }

        const player = document.getElementById('main-player');
        const playerRect = player.getBoundingClientRect();

        return {
            total_interactive_elements: targets.length,
            elements: targets,
            player_bounding_top: Math.round(playerRect.top * 10) / 10,
            player_bounding_height: Math.round(playerRect.height * 10) / 10
        };
    }""")

    shot_path = SCREENSHOT_DIR / "stress_mobile_touch_targets.png"
    page.screenshot(path=str(shot_path), full_page=True)

    context.close()

    elements = touch_target_analysis["elements"]
    failing_apple_44 = [e for e in elements if not e["passes_apple_hig_44px"]]
    failing_wcag_24 = [e for e in elements if not e["passes_wcag_24px"]]

    return {
        "scenario": "MOBILE_TOUCH_TARGETS",
        "viewport": {"width": 375, "height": 667},
        "total_targets_measured": len(elements),
        "targets_failing_apple_hig_44px": len(failing_apple_44),
        "targets_failing_wcag_24px": len(failing_wcag_24),
        "failing_elements_sample": failing_apple_44[:5],
        "player_top_coord": touch_target_analysis["player_bounding_top"],
        "def_ui_003_confirmed": touch_target_analysis["player_bounding_top"] > 1800,
        "screenshot": str(shot_path)
    }

def test_verify_8_defects(browser, target_url):
    print("\n[STRESS TEST E] Independent Verification of All 8 Defects...", flush=True)
    context = browser.new_context(viewport={"width": 1920, "height": 1080})
    page = context.new_page()

    network_responses = []
    page.on("response", lambda r: network_responses.append({"url": r.url, "status": r.status}))

    page.goto(target_url, wait_until="networkidle")
    page.wait_for_timeout(500)

    # DEF-UI-001: Path resolution duplication causing 404
    v_eval = page.evaluate("""() => {
        const v = document.getElementById('main-player');
        return {
            src: v.src,
            error_code: v.error ? v.error.code : null,
            networkState: v.networkState
        };
    }""")
    def_001_holds = ("output/output/" in v_eval["src"]) and (v_eval["error_code"] == 4)

    # DEF-UI-002: Missing <track> elements
    tracks_count = page.locator("#main-player track").count()
    text_tracks_len = page.evaluate("() => document.getElementById('main-player').textTracks ? document.getElementById('main-player').textTracks.length : 0")
    def_002_holds = (tracks_count == 0) and (text_tracks_len == 0)

    # DEF-UI-003: Mobile displacement checked via 375x667 context
    mobile_ctx = browser.new_context(viewport={"width": 375, "height": 667})
    m_page = mobile_ctx.new_page()
    m_page.goto(target_url, wait_until="networkidle")
    player_top = m_page.evaluate("() => document.getElementById('main-player').getBoundingClientRect().top")
    mobile_ctx.close()
    def_003_holds = player_top > 1800

    # DEF-UI-004: Missing playback rate controls
    rate_controls = page.locator("select[id*='rate'], button[class*='rate'], .speed-selector").count()
    def_004_holds = (rate_controls == 0)

    # DEF-UI-005: DOM thrashing on tab click
    thrash_detected = page.evaluate("""() => {
        const firstTab = document.querySelector('#lesson-tabs .tab-btn');
        const secondTab = document.querySelectorAll('#lesson-tabs .tab-btn')[1];
        secondTab.click();
        return !document.body.contains(firstTab);
    }""")
    def_005_holds = thrash_detected

    # DEF-UI-006: Scene clip button active state missing
    page.locator("#clip-buttons .tab-btn >> nth=1").click()
    page.wait_for_timeout(200)
    btn1_active = "active" in (page.locator("#clip-buttons .tab-btn >> nth=1").get_attribute("class") or "")
    full_active = "active" in (page.locator("#clip-buttons .tab-btn >> nth=0").get_attribute("class") or "")
    def_006_holds = (not btn1_active) and full_active

    # DEF-UI-007: Missing aspect-ratio on video
    video_style = page.evaluate("""() => {
        const v = document.getElementById('main-player');
        const computed = window.getComputedStyle(v);
        return {
            aspectRatio: computed.aspectRatio,
            height: v.getBoundingClientRect().height
        };
    }""")
    def_007_holds = (video_style["aspectRatio"] == "auto")

    # DEF-UI-008: Broken hero link to dsp_defense_index.html
    hero_href = page.locator("a[href*='output/dsp_defense_index.html']").get_attribute("href")
    resolved_hero = page.evaluate("() => document.querySelector(\"a[href*='output/dsp_defense_index.html']\").href")
    hero_404 = any(r["status"] == 404 and "output/output/dsp_defense_index.html" in r["url"] for r in network_responses)
    # Perform direct navigation attempt to verify 404
    hero_res = page.request.get(resolved_hero)
    def_008_holds = (hero_res.status == 404) and ("output/dsp_defense_index.html" in (hero_href or ""))

    context.close()

    defects_verified = [
        {"id": "DEF-UI-001", "name": "Video Path Duplication (output/output 404)", "holds": def_001_holds, "details": v_eval},
        {"id": "DEF-UI-002", "name": "Zero Subtitle <track> Elements", "holds": def_002_holds, "details": {"tracks": tracks_count, "textTracks": text_tracks_len}},
        {"id": "DEF-UI-003", "name": "Mobile Vertical Displacement (>1800px)", "holds": def_003_holds, "details": {"player_top_px": player_top}},
        {"id": "DEF-UI-004", "name": "Missing Playback Rate Controls", "holds": def_004_holds, "details": {"rate_controls": rate_controls}},
        {"id": "DEF-UI-005", "name": "DOM Thrashing / Node Destruction on Tab Switch", "holds": def_005_holds, "details": {"original_node_detached": thrash_detected}},
        {"id": "DEF-UI-006", "name": "Scene Clip Buttons Never Gain Active State", "holds": def_006_holds, "details": {"scene_btn_active": btn1_active, "full_btn_active": full_active}},
        {"id": "DEF-UI-007", "name": "Missing Video Container aspect-ratio (CLS)", "holds": def_007_holds, "details": video_style},
        {"id": "DEF-UI-008", "name": "Broken Hero Link to Workstation (404)", "holds": def_008_holds, "details": {"resolved_url": resolved_hero, "http_status": hero_res.status}}
    ]

    return {
        "scenario": "DEFECT_VERIFICATION_MATRIX",
        "all_defects_confirmed": all(d["holds"] for d in defects_verified),
        "defects": defects_verified
    }

def main():
    print("="*70, flush=True)
    print("M2 CHALLENGER 1: ADVERSARIAL HTML PLAYER STRESS TESTBENCH", flush=True)
    print("="*70, flush=True)

    server, port = start_test_server()
    target_url = f"http://127.0.0.1:{port}/output/index.html"
    print(f"Server listening on http://127.0.0.1:{port}", flush=True)
    print(f"Target URL: {target_url}\n", flush=True)

    suite_results = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "testbench_url": target_url,
        "results": {}
    }

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        desktop_ctx = browser.new_context(viewport={"width": 1920, "height": 1080})
        page = desktop_ctx.new_page()

        # Stress test A
        suite_results["results"]["rapid_tabs"] = test_rapid_tab_switching(page, target_url)

        # Stress test B
        suite_results["results"]["rapid_scenes"] = test_rapid_scene_clicking(page, target_url)

        desktop_ctx.close()

        # Stress test C
        suite_results["results"]["network_failure"] = test_network_failure_handling(browser, target_url)

        # Stress test D
        suite_results["results"]["mobile_touch"] = test_mobile_touch_targets(browser, target_url)

        # Defect Verification Matrix
        suite_results["results"]["defect_matrix"] = test_verify_8_defects(browser, target_url)

        browser.close()

    results_file = REPORT_DIR / "adversarial_stress_results.json"
    with open(results_file, "w", encoding="utf-8") as f:
        json.dump(suite_results, f, indent=2, ensure_ascii=False)

    print("\n" + "="*70, flush=True)
    print(f"ADVERSARIAL STRESS SUITE COMPLETE. Saved to: {results_file}", flush=True)
    print("="*70, flush=True)

    # Print summary
    matrix = suite_results["results"]["defect_matrix"]
    print(f"All 8 Defects Empirically Verified: {matrix['all_defects_confirmed']}")
    for d in matrix["defects"]:
        status = "CONFIRMED" if d["holds"] else "REFUTED"
        print(f"  [{status}] {d['id']}: {d['name']}")

if __name__ == "__main__":
    main()
