"""
tests/test_github_repo_adaptations.py
ISO 9001:2015 Agile V verification suite for the 4 architectural mechanisms adapted from
open-source educational video lecture repositories:
- R1: Bookmark-Driven Audio-Visual Sync & Time Events (manim-voiceover + motion-canvas)
- R2: Cursor Grounding & Cubic-Bezier Auto-Zoom Camera (Paper2Video + pdf2video)
- R3: OpenMAIC Classroom Action Script & manim-slides Step Controller (OpenMAIC + manim-slides)
- R4: Incremental Content-Addressable SHA-256 Scene Cache (remotion + slidemovie)
"""

from __future__ import annotations

import json
from pathlib import Path
import re
import sys

from fastapi import FastAPI
from fastapi.testclient import TestClient
import numpy as np

TESTBENCH_DIR = Path(__file__).resolve().parent.parent
for _p in (str(TESTBENCH_DIR), str(TESTBENCH_DIR / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from flow_api import router as flow_router  # noqa: E402
from flow_bridge import (  # noqa: E402
    CursorGroundingEngine,
    FlowScene,
    SceneRenderCache,
    build_openmaic_lecture_actions,
    build_srt_subtitles,
    build_webvtt_subtitles,
    parse_voiceover_bookmarks,
    resolve_bookmark_timestamps,
    strip_voiceover_bookmarks,
)
from flow_testbench_runner import (  # noqa: E402
    format_for_gemini_tts,
    render_scene_frame_pil,
    strip_accent_markers,
)


def _build_test_app() -> FastAPI:
    app = FastAPI()
    app.include_router(flow_router)
    return app


# ============================================================================
# R1. BOOKMARK & TIME-EVENT SYNCHRONIZATION (manim-voiceover + motion-canvas)
# ============================================================================


def test_r1_parse_voiceover_bookmarks_and_clean_stripping() -> None:
    sample_script = (
        '<bookmark mark="intro"/> First we examine the Motorola DSP56824 core '
        '<bookmark mark="mac_unit"/> which executes a 16x16 multiply-accumulate in one cycle '
        '<bookmark mark="q15_scale"/> using Q15 fixed-point scaling.'
    )
    res = parse_voiceover_bookmarks(sample_script)
    clean_text, bookmarks = res

    assert "<bookmark" not in clean_text.lower()
    assert "/>" not in clean_text
    assert res.clean_text == clean_text
    assert len(bookmarks) == 3

    expected_ids = ["intro", "mac_unit", "q15_scale"]
    assert [b.mark for b in bookmarks] == expected_ids

    prev_ratio = 0.0
    for b in bookmarks:
        assert 0.0 <= b.word_ratio <= 1.0
        assert b.word_ratio >= prev_ratio
        prev_ratio = b.word_ratio

    # Ensure TTS and subtitle helpers also strip bookmarks cleanly
    assert "<bookmark" not in strip_voiceover_bookmarks(sample_script).lower()
    assert "<bookmark" not in strip_accent_markers(sample_script).lower()
    assert "<bookmark" not in format_for_gemini_tts(sample_script).lower()


def test_r1_resolve_bookmark_timestamps_monotonicity_and_subtitles() -> None:
    script = (
        '<bookmark mark="step1"/> Hardware SSI port receives 16-bit samples '
        '<bookmark mark="step2"/> and triggers Vector 15 interrupt handler '
        '<bookmark mark="step3"/> executing 6 biquad sections in 150 cycles.'
    )
    clean_text, bookmarks = parse_voiceover_bookmarks(script)
    total_dur = 24.0
    acoustic_segments = [(0.5, 7.5), (8.2, 15.8), (16.4, 23.2)]

    resolved = resolve_bookmark_timestamps(
        bookmarks,
        total_duration_sec=total_dur,
        acoustic_segments=acoustic_segments,
        fps=15,
    )

    assert len(resolved) == 3
    t1 = float(resolved["step1"])
    t2 = float(resolved["step2"])
    t3 = float(resolved["step3"])
    assert 0.0 <= t1 <= t2 <= t3 <= total_dur
    assert 0 <= resolved["step1"].frame_offset <= resolved["step2"].frame_offset <= resolved["step3"].frame_offset <= int(total_dur * 15)

    # Verify zero <bookmark> leakage into WebVTT and SubRip tracks
    sc = FlowScene(
        scene_id="bm_test_sc01",
        scene_number=1,
        title="Bookmark Sync Test",
        visual_prompt="DSP56824 pipeline",
        narration_text=script,
        duration_sec=24,
        on_screen_bullets=["SSI_Rx_ISR <bookmark mark='hidden'/>", "DO #6 Loop"],
    )
    vtt = build_webvtt_subtitles([sc])
    srt = build_srt_subtitles([sc])
    assert "<bookmark" not in vtt.lower()
    assert "<bookmark" not in srt.lower()


# ============================================================================
# R2. CURSOR GROUNDING & AUTO-ZOOM CAMERA (Paper2Video + pdf2video)
# ============================================================================


def test_r2_cursor_grounding_engine_bounds_and_zoom_trajectory() -> None:
    src_w, src_h = 2481, 3508
    engine = CursorGroundingEngine(source_width=src_w, source_height=src_h, min_zoom=1.0, max_zoom=1.85)
    cues = [
        {"start_ratio": 0.0, "end_ratio": 0.5, "focus_bbox": [0.10, 0.12, 0.88, 0.42], "formula_or_label": "Formula (1.1)"},
        {"start_ratio": 0.5, "end_ratio": 1.0, "focus_bbox": [0.12, 0.52, 0.90, 0.86], "formula_or_label": "Table 2.1"},
    ]

    total_frames = 60
    zooms = []
    laser_positions = []
    for f in range(total_frames):
        st = engine.compute_frame_state(f, total_frames, cues=cues)
        assert 0.0 <= st.x <= src_w
        assert 0.0 <= st.y <= src_h
        assert 0.0 <= st.laser_x <= src_w
        assert 0.0 <= st.laser_y <= src_h
        assert 1.0 <= st.zoom <= 1.85
        cx0, cy0, cx1, cy1 = st.crop_box
        assert 0 <= cx0 < cx1 <= src_w
        assert 0 <= cy0 < cy1 <= src_h
        assert len(st.callout_typed) >= 1
        zooms.append(st.zoom)
        laser_positions.append((st.laser_x, st.laser_y))

    assert max(zooms) > min(zooms), "Camera zoom must dynamically transition across frames"
    assert len(set(laser_positions)) > 10, "Laser pointer must animate across the active bounding box"


def test_r2_split_screen_compositor_left_panel_pixel_variance() -> None:
    sc = FlowScene(
        scene_id="cycle3_sc06",
        scene_number=1,
        title="Q15 Scaling and L_infinity Norm",
        visual_prompt="Coursework page 28 inspection",
        narration_text='<bookmark mark="b1"/> Coefficient halving in Q15 <bookmark mark="b2"/> prevents overflow.',
        duration_sec=8,
        on_screen_bullets=["Q15 /2 scaling", "ASL A shift"],
    )
    setattr(sc, "pz_page", 28)

    total_frames = 40
    f_early = render_scene_frame_pil("DSP Test", sc, "voice_y0joebp3bwta", 1, frame_idx=2, total_frames=total_frames)
    f_mid = render_scene_frame_pil("DSP Test", sc, "voice_y0joebp3bwta", 1, frame_idx=18, total_frames=total_frames)
    f_late = render_scene_frame_pil("DSP Test", sc, "voice_y0joebp3bwta", 1, frame_idx=34, total_frames=total_frames)

    arr_early = np.frombuffer(f_early, dtype=np.uint8).reshape((720, 1280, 3))
    arr_mid = np.frombuffer(f_mid, dtype=np.uint8).reshape((720, 1280, 3))
    arr_late = np.frombuffer(f_late, dtype=np.uint8).reshape((720, 1280, 3))

    # Left PDF panel region: y = 66..594, x = 24..584
    lp_early = arr_early[66:594, 24:584].astype(np.float32)
    lp_mid = arr_mid[66:594, 24:584].astype(np.float32)
    lp_late = arr_late[66:594, 24:584].astype(np.float32)

    diff_1 = float(np.mean(np.abs(lp_mid - lp_early)))
    diff_2 = float(np.mean(np.abs(lp_late - lp_mid)))
    assert max(diff_1, diff_2) > 1.0, "Left PDF panel must exhibit non-zero pixel variance during Auto-Zoom + Laser Grounding"


# ============================================================================
# R3. OPENMAIC ACTION SCRIPT & MANIM-SLIDES STEP CONTROLLER
# ============================================================================


def test_r3_interactive_course_html_has_paper2video_openmaic_and_manim_slides() -> None:
    root_html = TESTBENCH_DIR / "dsp_interactive_course.html"
    out_html = TESTBENCH_DIR / "output" / "dsp_interactive_course.html"
    assert root_html.is_file() and out_html.is_file()

    root_text = root_html.read_text(encoding="utf-8")
    out_text = out_html.read_text(encoding="utf-8")
    assert root_text == out_text, "Root and output/dsp_interactive_course.html must be byte-identical"

    required_markers = [
        "sheet-zoom-container",
        "paper2video-laser",
        "pdf2video-callout",
        "prevSlideStep()",
        "toggleSlideLoop()",
        "nextSlideStep()",
        "toggleAutoZoomCamera()",
        "openmaic-action-stream",
        "openmaic-socratic-checkpoint",
    ]
    for marker in required_markers:
        assert marker in root_text, f"Missing required UI/JS hook in dsp_interactive_course.html: {marker}"

    # Verify COURSE_DATA contains openmaic_actions for all 45 sheets
    m = re.search(r"const\s+COURSE_DATA\s*=\s*(\{.*?\});\s*\n\s*// Flatten", root_text, re.DOTALL)
    assert m is not None
    course_data = json.loads(m.group(1))
    openmaic_map = course_data.get("openmaic_actions", {})
    assert len(openmaic_map) == 45
    for p_idx in range(1, 46):
        pack = openmaic_map[str(p_idx)]
        action_types = [a["type"] for a in pack["actions"]]
        for req_type in ("ShowSheet", "ZoomBBox", "LaserPoint", "RunSimPreset", "QuizCheckpoint"):
            assert req_type in action_types


def test_r3_fastapi_lecture_actions_endpoint_all_45_sheets() -> None:
    app = _build_test_app()
    client = TestClient(app)

    for page_num in (1, 8, 28, 32, 42, 44, 45):
        resp = client.get(f"/api/flow/lecture-actions/{page_num}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["page_number"] == page_num
        action_types = [a["type"] for a in data["actions"]]
        for req_type in ("ShowSheet", "ZoomBBox", "LaserPoint", "RunSimPreset", "QuizCheckpoint"):
            assert req_type in action_types
        assert len(data["slides_segments"]) == len(data["actions"])

    bad_resp = client.get("/api/flow/lecture-actions/99")
    assert bad_resp.status_code == 422


# ============================================================================
# R4. INCREMENTAL SCENE CACHE & CLEANLINESS GATE
# ============================================================================


def test_r4_scene_render_cache_deterministic_digest_and_hit_miss(tmp_path: Path) -> None:
    cache = SceneRenderCache(cache_dir=tmp_path / ".scene_cache")

    key1 = cache.compute_scene_key(
        scene_or_id="cycle1_sc02",
        narration_text='<bookmark mark="m1"/> Sampling rate is 48 kHz.',
        pz_page=8,
        pz_bbox=[0.1, 0.2, 0.9, 0.5],
        concept_cues=[{"start_ratio": 0.0, "end_ratio": 1.0, "focus_bbox": [0.1, 0.2, 0.9, 0.5]}],
        visual_type="split_screen_live_sync",
        tts_wav_sha256="abc123def456",
    )
    key2 = cache.compute_scene_key(
        scene_or_id="cycle1_sc02",
        narration_text="Sampling rate is 48 kHz.",
        pz_page=8,
        pz_bbox=[0.1, 0.2, 0.9, 0.5],
        concept_cues=[{"start_ratio": 0.0, "end_ratio": 1.0, "focus_bbox": [0.1, 0.2, 0.9, 0.5]}],
        visual_type="split_screen_live_sync",
        tts_wav_sha256="abc123def456",
    )
    assert len(key1) == 64
    assert key1 == key2, "Stripping <bookmark> tags must yield identical deterministic scene digest"

    # First lookup -> miss
    assert cache.get(key1) is None
    assert cache.misses == 1
    assert cache.hits == 0

    # Store dummy MP4 segment (> 64 bytes)
    dummy_mp4 = b"\x00\x00\x00\x18ftypmp42" + (b"\x00" * 256)
    stored_path = cache.put(key1, dummy_mp4, metadata={"scene_id": "cycle1_sc02"})
    assert stored_path.is_file()

    # Second lookup -> hit
    out_copy = tmp_path / "restored_scene.mp4"
    hit_path = cache.get(key1, dest_path=out_copy)
    assert hit_path is not None and hit_path.is_file()
    assert out_copy.read_bytes() == dummy_mp4
    assert cache.hits == 1
    telemetry = cache.get_telemetry()
    assert telemetry["hits"] == 1
    assert telemetry["misses"] == 1
    assert telemetry["hit_rate"] == 0.5


def test_r4_english_only_and_zero_personal_tokens_gate() -> None:
    cyr_re = re.compile("[\u0400-\u04ff]")
    p_tok_1 = "Ora" + "kul"
    p_tok_2 = "ANTI" + "GRAVITY"

    checked_files = [
        TESTBENCH_DIR / "src" / "flow_repo_adaptations.py",
        TESTBENCH_DIR / "src" / "flow_bridge.py",
        TESTBENCH_DIR / "src" / "flow_api.py",
        Path(__file__),
    ]
    for cf in checked_files:
        text = cf.read_text(encoding="utf-8")
        m = cyr_re.search(text)
        assert m is None, f"Literal Cyrillic found in {cf.name} at line {text[:m.start()].count(chr(10)) + 1}"
        assert p_tok_1 not in text, f"Personal token 1 found in {cf.name}"
        assert p_tok_2 not in text, f"Personal token 2 found in {cf.name}"
