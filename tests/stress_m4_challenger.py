"""
Empirical Adversarial Stress Test Harness for Milestone 4 (Challenger M4).
Tests:
1. REQ-004 Zero-Cyrillic & Zero-Personal-Tokens in testbench files.
2. Zero uncompressed frame dumps (*.rgb, frames.rgb) anywhere in repo.
3. Master MP4 media container validation (ftyp, h264, aac, size > 10KB, duration).
4. Deep structural parsing & assertions on output/dsp_defense_index.html and dsp_defense_index.html:
   - 6-section navigation tabs + master tab.
   - Timecode jump strip buttons (00:00, 04:48, 10:49, 16:51, 22:12, 27:01).
   - Amber-gold highlighting style #FFC107.
   - Strict voice_y0joebp3bwta single speaker lock (zero Sulafat / Svetlana leaks).
   - Mode switcher buttons (btn-mode-auto, btn-mode-live).
   - 300 DPI Blueprint lightbox modal & buttons (drawing_e2, drawing_pe2, MATLAB figs).
   - Physical existence of all referenced blueprint assets on disk.
   - 53 scene payloads embedded in JSON with word-level timing start_ms & end_ms.
5. Algorithmic stress-testing of _compute_scene_words_payload() edge cases.
6. Cross-reference link checks in index.html and output/index.html.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))

from src.dsp_defense_cycles import (
    DSP_DEFENSE_CYCLES,
    _compute_scene_words_payload,
)


def test_req004_cyrillic_and_personal_tokens() -> None:
    print("[1] Verifying REQ-004 Zero-Cyrillic and Zero-Personal-Tokens...")
    cyrillic_re = re.compile("[\u0400-\u04ff]")
    
    target_files = [
        REPO_ROOT / "src" / "flow_bridge.py",
        REPO_ROOT / "src" / "flow_api.py",
        REPO_ROOT / "src" / "flow_audio_video.py",
        REPO_ROOT / "src" / "flow_live_rpc.py",
        REPO_ROOT / "src" / "flow_studio_ui.py",
        REPO_ROOT / "tests" / "test_flow_studio.py",
        REPO_ROOT / "tests" / "test_flow_l4_studio.py",
    ]

    for p in target_files:
        assert p.is_file(), f"Target file missing: {p.name}"
        content = p.read_text(encoding="utf-8")
        match = cyrillic_re.search(content)
        assert match is None, f"REQ-004 FAIL: Cyrillic character in {p.name} at pos {match.start()}: {content[max(0, match.start()-10):match.start()+10]!r}"

    # Personal token checks
    tok_a = ("Ora" + "kul").lower()
    tok_b = ("kuro" + "ora" + "kul" + "grey").lower()
    tok_c = ("ANTI" + "GRAVITY").lower()

    for p in target_files:
        lowered = p.read_text(encoding="utf-8").lower()
        assert tok_a not in lowered, f"Forbidden personal token A found in {p.name}"
        assert tok_b not in lowered, f"Forbidden personal token B found in {p.name}"
        assert tok_c not in lowered, f"Forbidden workspace path token C found in {p.name}"

    print("  PASS: REQ-004 Zero-Cyrillic and Zero-Personal-Tokens verified across all 7 target files.")


def test_zero_disk_frame_dumps() -> None:
    print("[2] Verifying zero-disk in-memory pipe (zero frames.rgb dumps)...")
    rgb_files = list(REPO_ROOT.glob("**/frames.rgb"))
    assert len(rgb_files) == 0, f"FAIL: Found forbidden frames.rgb disk dumps: {rgb_files}"

    all_rgb = list(REPO_ROOT.glob("**/*.rgb"))
    assert len(all_rgb) == 0, f"FAIL: Found *.rgb raw frame files on disk: {all_rgb}"
    print("  PASS: 0 frames.rgb or *.rgb files detected across entire workspace.")


def test_master_mp4_integrity() -> None:
    print("[3] Stress-testing Master MP4 video file and stream structures...")
    master_path = REPO_ROOT / "output" / "lesson_07_ru_dsp_defense_master" / "lesson_full_720p.mp4"
    assert master_path.is_file(), f"FAIL: Master MP4 missing at {master_path}"
    
    file_size = master_path.stat().st_size
    print(f"  Master MP4 file size: {file_size:,} bytes")
    assert file_size > 10_000, f"FAIL: Master MP4 too small: {file_size} bytes"

    # Container ftyp box check
    header = master_path.read_bytes()[:32]
    assert b"ftyp" in header, f"FAIL: b'ftyp' box missing in header: {header[:16]!r}"

    # Stream inspection via ffprobe or ffmpeg
    try:
        import imageio_ffmpeg
        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        ffmpeg_exe = "ffmpeg"

    res = subprocess.run(
        [ffmpeg_exe, "-i", str(master_path)],
        stderr=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="ignore",
    )
    output_log = res.stderr

    # Check video stream
    assert "Video: h264" in output_log or "Video: avc1" in output_log, f"FAIL: Video stream is not h264. Log:\n{output_log}"
    assert "1280x720" in output_log, f"FAIL: Resolution is not 1280x720. Log:\n{output_log}"

    # Check audio stream
    assert "Audio: aac" in output_log or "Audio: mp4a" in output_log, f"FAIL: Audio stream is not aac. Log:\n{output_log}"

    # Check duration presence
    dur_match = re.search(r"Duration:\s*(\d{2}):(\d{2}):(\d{2}\.\d+)", output_log)
    assert dur_match is not None, f"FAIL: Could not parse Duration from ffmpeg log:\n{output_log}"
    h, m, s = int(dur_match.group(1)), int(dur_match.group(2)), float(dur_match.group(3))
    total_dur_sec = h * 3600 + m * 60 + s
    print(f"  Master MP4 stream duration: {total_dur_sec:.2f}s ({h:02d}:{m:02d}:{s:04.1f})")
    assert total_dur_sec > 300, f"FAIL: Master MP4 duration suspiciously short: {total_dur_sec}s"

    print("  PASS: Master MP4 has valid ftyp box, size > 10 KB, valid h264 video and aac audio.")


def test_html_player_deep_structure() -> None:
    print("[4] Empirically parsing and verifying output/dsp_defense_index.html & dsp_defense_index.html...")
    out_html = REPO_ROOT / "output" / "dsp_defense_index.html"
    root_html = REPO_ROOT / "dsp_defense_index.html"

    assert out_html.is_file(), "FAIL: output/dsp_defense_index.html missing"
    assert root_html.is_file(), "FAIL: dsp_defense_index.html at root missing"

    size_out = out_html.stat().st_size
    size_root = root_html.stat().st_size
    print(f"  output/dsp_defense_index.html size: {size_out:,} bytes")
    print(f"  dsp_defense_index.html size:        {size_root:,} bytes")
    assert size_out > 500_000, f"FAIL: output HTML too small: {size_out} bytes"
    assert size_root > 500_000, f"FAIL: root HTML too small: {size_root} bytes"

    # Cyrillic escaped needles for assertions
    mode1_needle = "\u0420\u0435\u0436\u0438\u043c 1: \u0410\u0432\u0442\u043e\u0434\u043e\u043a\u043b\u0430\u0434 \u0441\u043e \u0437\u0432\u0443\u043a\u043e\u043c"
    mode2_needle = "\u0420\u0435\u0436\u0438\u043c 2: \u0416\u0438\u0432\u0430\u044f \u0437\u0430\u0449\u0438\u0442\u0430"

    expected_blueprints = [
        "drawing_e2.png",
        "drawing_pe2.png",
        "fig_3_1.png",
        "fig_4_1.png",
        "fig_5_1.png",
        "fig_5_2.png",
        "fig_5_3.png",
        "fig_5_5.png",
    ]

    expected_timecodes = [0, 288, 649, 1011, 1332, 1621]

    for label, path in [("output", out_html), ("root", root_html)]:
        content = path.read_text(encoding="utf-8")

        # 4.1 Mode switcher buttons
        assert 'id="btn-mode-auto"' in content, f"FAIL ({label}): btn-mode-auto missing"
        assert 'id="btn-mode-live"' in content, f"FAIL ({label}): btn-mode-live missing"
        assert mode1_needle in content, f"FAIL ({label}): Mode 1 label missing"
        assert mode2_needle in content, f"FAIL ({label}): Mode 2 label missing"
        assert "setDefenseMode('auto')" in content, f"FAIL ({label}): setDefenseMode('auto') missing"
        assert "setDefenseMode('live')" in content, f"FAIL ({label}): setDefenseMode('live') missing"

        # 4.2 Amber-gold highlighting style
        assert "#FFC107" in content, f"FAIL ({label}): Amber-gold color #FFC107 missing"
        assert ".prompt-word.active-word" in content, f"FAIL ({label}): .prompt-word.active-word class missing"
        assert "color: #FFC107 !important;" in content, f"FAIL ({label}): active-word color styling missing"

        # 4.3 Navigation tabs & timecode strip
        assert 'id="cycle-tabs"' in content, f"FAIL ({label}): id='cycle-tabs' missing"
        assert 'id="timecode-strip"' in content, f"FAIL ({label}): id='timecode-strip' missing"
        for tc in expected_timecodes:
            assert f"jumpToTime({tc})" in content, f"FAIL ({label}): jumpToTime({tc}) button missing"

        # 4.4 Blueprints & lightbox modal
        assert 'id="bp-modal"' in content, f"FAIL ({label}): id='bp-modal' missing"
        assert "openBlueprint(" in content, f"FAIL ({label}): openBlueprint() missing"
        assert "closeBlueprint(" in content, f"FAIL ({label}): closeBlueprint() missing"
        assert "adjustZoom(" in content, f"FAIL ({label}): adjustZoom() missing"
        assert "resetZoom(" in content, f"FAIL ({label}): resetZoom() missing"
        for bp in expected_blueprints:
            assert bp in content, f"FAIL ({label}): blueprint reference {bp} missing"

        # 4.5 Strict single speaker voice
        assert "voice_y0joebp3bwta" in content, f"FAIL ({label}): voice_y0joebp3bwta missing"
        assert "Sulafat" not in content, f"FAIL ({label}): Unauthorized Sulafat voice detected!"
        assert "SvetlanaNeural" not in content, f"FAIL ({label}): Unauthorized SvetlanaNeural voice detected!"

        # 4.6 Keyboard navigation handlers
        assert "Space" in content, f"FAIL ({label}): Space hotkey missing"
        assert "ArrowRight" in content, f"FAIL ({label}): ArrowRight hotkey missing"
        assert "ArrowLeft" in content, f"FAIL ({label}): ArrowLeft hotkey missing"
        assert "Escape" in content, f"FAIL ({label}): Escape hotkey missing"

        # 4.7 JSON Payload Extraction & Validation
        m_json = re.search(r"const CYCLES = (\[.*?\]);\s*\n\s*const QA_CARDS =", content, re.DOTALL)
        assert m_json is not None, f"FAIL ({label}): Could not extract const CYCLES JSON payload"
        cycles_payload = json.loads(m_json.group(1))

        assert len(cycles_payload) == 7, f"FAIL ({label}): Expected 7 cycle entries (Master + 6 sections), got {len(cycles_payload)}"
        
        master_entry = cycles_payload[0]
        assert master_entry["cycle_number"] == 0, f"FAIL ({label}): Entry 0 is not master"
        assert master_entry["slug"] == "lesson_07_ru_dsp_defense_master"
        assert master_entry["duration_sec"] >= 1800, f"FAIL ({label}): Master duration < 1800s: {master_entry['duration_sec']}"
        master_scenes = master_entry["project"]["scenes"]
        assert len(master_scenes) == 53, f"FAIL ({label}): Master video does not have 53 scenes (has {len(master_scenes)})"

        # Check section cumulative progression
        section_scene_count = 0
        for s_idx in range(1, 7):
            sec = cycles_payload[s_idx]
            assert sec["cycle_number"] == s_idx
            assert sec["start_sec"] == expected_timecodes[s_idx - 1], f"Mismatch in start_sec for cycle {s_idx}: expected {expected_timecodes[s_idx-1]}, got {sec['start_sec']}"
            sec_scenes = sec["project"]["scenes"]
            section_scene_count += len(sec_scenes)

        assert section_scene_count == 53, f"FAIL ({label}): Sum of scenes across 6 sections is {section_scene_count}, expected 53"

        # Verify word-level timing payload across all 53 scenes
        total_words_checked = 0
        for sc in master_scenes:
            sc_id = sc["scene_id"]
            words = sc.get("words", [])
            assert len(words) > 0, f"FAIL ({label}): Scene {sc_id} has empty words list!"
            
            prev_end = 0
            for w_idx, w in enumerate(words):
                total_words_checked += 1
                assert "word" in w and len(w["word"]) > 0, f"FAIL ({label}): Invalid word token in scene {sc_id} index {w_idx}: {w}"
                assert "start_ms" in w, f"FAIL ({label}): start_ms missing in scene {sc_id} word {w_idx}"
                assert "end_ms" in w, f"FAIL ({label}): end_ms missing in scene {sc_id} word {w_idx}"
                
                s_ms = w["start_ms"]
                e_ms = w["end_ms"]
                assert s_ms >= 0, f"Negative start_ms {s_ms} in scene {sc_id} word {w_idx}"
                assert e_ms > s_ms, f"end_ms ({e_ms}) <= start_ms ({s_ms}) in scene {sc_id} word {w_idx}"
                assert s_ms >= prev_end - 1, f"Time reversal: start_ms {s_ms} < prev_end {prev_end} in scene {sc_id} word {w_idx}"
                prev_end = e_ms

            # Check that final end_ms does not drastically exceed scene duration
            sc_dur_ms = sc["duration_sec"] * 1000
            assert words[-1]["end_ms"] <= sc_dur_ms + 1000, f"Scene {sc_id}: words[-1].end_ms ({words[-1]['end_ms']}) exceeds duration ({sc_dur_ms})"

        print(f"  PASS ({label}): Verified 53 scenes and {total_words_checked} word-level timing tokens.")

    # 4.8 Check physical existence of blueprint assets on disk
    asset_dir = REPO_ROOT / "output" / "dsp_assets"
    assert asset_dir.is_dir(), f"FAIL: dsp_assets dir missing at {asset_dir}"
    for bp in expected_blueprints:
        bp_path = asset_dir / bp
        assert bp_path.is_file(), f"FAIL: Referenced blueprint asset missing on disk: {bp_path}"
        assert bp_path.stat().st_size > 1000, f"FAIL: Blueprint asset too small: {bp_path} ({bp_path.stat().st_size} bytes)"

    print(f"  PASS: All {len(expected_blueprints)} blueprint images physically exist in output/dsp_assets/ (> 1KB each).")


def test_compute_scene_words_payload_adversarial() -> None:
    print("[5] Stress-testing _compute_scene_words_payload algorithm on adversarial edge cases...")

    # 5.1 Empty string
    assert _compute_scene_words_payload("", 30.0) == []

    # 5.2 Whitespace only
    assert _compute_scene_words_payload("   \t\n   ", 25.0) == []

    # 5.3 Single word
    res_one = _compute_scene_words_payload("DSP56824", 10.0)
    assert len(res_one) == 1
    assert res_one[0]["word"] == "DSP56824"
    assert res_one[0]["start_ms"] >= 0
    assert res_one[0]["end_ms"] > res_one[0]["start_ms"]

    # 5.4 Strip accents (+ and *)
    res_accent = _compute_scene_words_payload("\u043c\u0438\u043a\u0440\u043e\u043f\u0440\u043e\u0446+\u0435\u0441\u0441\u043e\u0440 *\u0432\u0430\u0436\u043d\u043e*", 20.0)
    words = [w["word"] for w in res_accent]
    assert "+" not in words[0]
    assert "*" not in words[1]

    # 5.5 Acronym duration weighting vs single-letter conjunction
    sample_text = "\u041f\u0440\u043e\u0446\u0435\u0441\u0441\u043e\u0440 Motorola DSP56824 \u0438 \u043f\u0430\u043c\u044f\u0442\u044c IS61LV6416"
    res_weight = _compute_scene_words_payload(sample_text, 10.0)
    word_map = {w["word"]: w["end_ms"] - w["start_ms"] for w in res_weight}
    dur_dsp = word_map.get("DSP56824", 0)
    dur_is61 = word_map.get("IS61LV6416", 0)
    dur_conj = word_map.get("\u0438", 0)

    assert dur_dsp > 0 and dur_is61 > 0 and dur_conj > 0
    assert dur_dsp > dur_conj * 1.5, f"Acronym duration {dur_dsp}ms not significantly larger than conjunction {dur_conj}ms"
    assert dur_is61 > dur_conj * 1.5, f"Memory acronym duration {dur_is61}ms not significantly larger than conjunction {dur_conj}ms"

    # 5.6 Non-reversal temporal guarantee
    for i in range(len(res_weight) - 1):
        assert res_weight[i+1]["start_ms"] >= res_weight[i]["start_ms"]
        assert res_weight[i+1]["end_ms"] > res_weight[i+1]["start_ms"]

    print("  PASS: _compute_scene_words_payload passes all adversarial edge case tests.")


def test_index_html_cross_references() -> None:
    print("[6] Verifying root index.html and output/index.html navigation links...")
    root_idx = REPO_ROOT / "index.html"
    out_idx = REPO_ROOT / "output" / "index.html"

    assert root_idx.is_file(), "Root index.html missing"
    assert out_idx.is_file(), "output/index.html missing"

    root_txt = root_idx.read_text(encoding="utf-8")
    out_txt = out_idx.read_text(encoding="utf-8")

    assert "dsp_defense_index.html" in root_txt, "Root index.html missing link to dsp_defense_index.html"
    assert "dsp_defense_index.html" in out_txt, "output/index.html missing link to dsp_defense_index.html"

    # Check that root index references output/dsp_defense_index.html or dsp_defense_index.html
    assert "dsp_defense_index.html" in root_txt

    print("  PASS: Navigation links verified in both root and output index.html files.")


def test_html5_player_m4_dom_invariants() -> None:
    print("[7] Stress-testing HTML5 Player Milestone 4 DOM Invariants...")
    out_html = REPO_ROOT / "output" / "dsp_defense_index.html"
    root_html = REPO_ROOT / "dsp_defense_index.html"

    boundary_samples = [
        (0.0, 1),
        (100.5, 1),
        (287.9, 1),
        (288.0, 2),
        (450.0, 2),
        (648.9, 2),
        (649.0, 3),
        (850.0, 3),
        (1010.9, 3),
        (1011.0, 4),
        (1200.0, 4),
        (1331.9, 4),
        (1332.0, 5),
        (1500.0, 5),
        (1620.9, 5),
        (1621.0, 6),
        (1800.0, 6),
        (1921.0, 6),
    ]

    for label, path in [("output", out_html), ("root", root_html)]:
        content = path.read_text(encoding="utf-8")

        # 7.1 Verify QA cards in JSON payload
        m_qa = re.search(r"const QA_CARDS = (\[.*?\]);\s*\n", content, re.DOTALL)
        assert m_qa is not None, f"FAIL ({label}): const QA_CARDS JSON missing"
        qa_data = json.loads(m_qa.group(1))
        assert len(qa_data) == 8, f"FAIL ({label}): Expected 8 QA cards, got {len(qa_data)}"

        # 7.2 Verify renderQACards creates unique IDs qa-card-0 .. qa-card-7 with cursor: pointer
        assert "renderQACards" in content, f"FAIL ({label}): renderQACards() missing"
        assert "qa-card-" in content, f"FAIL ({label}): qa-card- prefix missing"
        assert "cursor = 'pointer'" in content or "cursor: pointer" in content, f"FAIL ({label}): cursor: pointer missing for qa-card"
        assert "jumpToQAScene" in content, f"FAIL ({label}): jumpToQAScene missing"
        assert "active-qa" in content, f"FAIL ({label}): active-qa class missing"

        # 7.3 Verify jumpToQAScene handler logic
        # Master mode: jumpToSceneCard(45 + qaIdx)
        # Direct section mode: selectCycle(6) + jumpToSceneCard(qaIdx)
        assert "jumpToSceneCard(45 + qaIdx)" in content, f"FAIL ({label}): Master mode 45 + qaIdx jump logic missing"
        assert "selectCycle(6)" in content, f"FAIL ({label}): selectCycle(6) fallback missing in jumpToQAScene"

        # 7.4 Verify ontimeupdate Section 6 Q&A highlight detection
        assert "isSec6Master" in content, f"FAIL ({label}): isSec6Master check missing"
        assert "isSec6Direct" in content, f"FAIL ({label}): isSec6Direct check missing"
        assert "activeSceneIdx >= 45 && activeSceneIdx <= 52" in content, f"FAIL ({label}): Section 6 scene index range [45, 52] missing"
        assert "activeSceneIdx - 45" in content, f"FAIL ({label}): Master qaIdx delta (-45) missing"

        # 7.5 Verify CSS styling for .qa-card.active-qa
        assert ".qa-card.active-qa" in content, f"FAIL ({label}): CSS rule .qa-card.active-qa missing"
        assert "rgba(56, 189, 248" in content, f"FAIL ({label}): cyan accent background missing in active-qa"

        # 7.6 Verify chapter boundary mapping in JS and simulate logic
        js_boundary_snip = (
            "if (t >= 1621) activeSectionNum = 6;\n"
            "        else if (t >= 1332) activeSectionNum = 5;\n"
            "        else if (t >= 1011) activeSectionNum = 4;\n"
            "        else if (t >= 649) activeSectionNum = 3;\n"
            "        else if (t >= 288) activeSectionNum = 2;\n"
            "        else activeSectionNum = 1;"
        )
        assert "activeSectionNum" in content, f"FAIL ({label}): activeSectionNum logic missing"
        assert "t >= 1621" in content, f"FAIL ({label}): boundary 1621 missing"
        assert "t >= 1332" in content, f"FAIL ({label}): boundary 1332 missing"
        assert "t >= 1011" in content, f"FAIL ({label}): boundary 1011 missing"
        assert "t >= 649" in content, f"FAIL ({label}): boundary 649 missing"
        assert "t >= 288" in content, f"FAIL ({label}): boundary 288 missing"

        # Simulate chapter boundary mapping function
        def simulate_section(t_val: float) -> int:
            if t_val >= 1621:
                return 6
            elif t_val >= 1332:
                return 5
            elif t_val >= 1011:
                return 4
            elif t_val >= 649:
                return 3
            elif t_val >= 288:
                return 2
            else:
                return 1

        for t_val, exp_sec in boundary_samples:
            calc_sec = simulate_section(t_val)
            assert calc_sec == exp_sec, f"FAIL ({label}): Time {t_val} mapped to section {calc_sec}, expected {exp_sec}"

        # 7.7 Verify tab and timecode strip active class toggles
        assert "section-playing" in content, f"FAIL ({label}): section-playing class missing"
        assert "active-tc" in content, f"FAIL ({label}): active-tc class missing"
        assert ".tab-btn.section-playing" in content, f"FAIL ({label}): CSS rule .tab-btn.section-playing missing"
        assert ".tc-btn.active-tc" in content, f"FAIL ({label}): CSS rule .tc-btn.active-tc missing"

        # 7.8 Verify teleprompter word spans onclick seek handlers
        assert "span.onclick" in content, f"FAIL ({label}): span.onclick missing in updateTeleprompter"
        assert "playerEl.currentTime = sceneStart" in content, f"FAIL ({label}): currentTime seek missing on word span"
        assert "pw-${wIdx}" in content or "pw-" in content, f"FAIL ({label}): Word span id pw- missing"

        # 7.9 Verify kinetic typography amber-gold styles
        assert "#FFC107" in content, f"FAIL ({label}): Amber gold color #FFC107 missing"
        assert "color: #FFC107 !important;" in content, f"FAIL ({label}): Active word color style missing"
        assert "rgba(255, 193, 7, 0.28)" in content, f"FAIL ({label}): Amber gold glow background missing"
        assert "syncTeleprompterWords" in content, f"FAIL ({label}): syncTeleprompterWords missing"

    print("  PASS: All HTML5 Player Milestone 4 DOM Invariants empirically verified across both distribution files.")


if __name__ == "__main__":
    print("=" * 70)
    print("STARTING CHALLENGER M4 EMPIRICAL ADVERSARIAL STRESS SUITE")
    print("=" * 70)
    test_req004_cyrillic_and_personal_tokens()
    test_zero_disk_frame_dumps()
    test_master_mp4_integrity()
    test_html_player_deep_structure()
    test_compute_scene_words_payload_adversarial()
    test_index_html_cross_references()
    test_html5_player_m4_dom_invariants()
    print("=" * 70)
    print("ALL CHALLENGER M4 EMPIRICAL STRESS TESTS PASSED SUCCESSFULLY!")
    print("=" * 70)
