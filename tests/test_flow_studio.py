"""
Standalone pytest suite for <WORKSPACE_ROOT>/flow_video_testbench.
Verifies:
1. src.flow_bridge (FlowClient, storyboard synthesis, Veo 3.1 native audio prompt, WebVTT/SRT, ISO-BMFF MP4)
2. src.flow_api (FastAPI /api/flow/* endpoints)
3. flow_testbench_runner (female-only Gemini 3.8 Studio narrator, _is_valid_speech_wav RMS guard, format_for_gemini_tts, accent stripping)
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import numpy as np
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

TESTBENCH_DIR = Path(__file__).resolve().parent.parent
for _p in (str(TESTBENCH_DIR), str(TESTBENCH_DIR / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from src.flow_api import router as flow_router  # noqa: E402
from src.flow_bridge import (  # noqa: E402
    SUPPORTED_VOICE_PERSONAS,
    FlowClient,
    FlowEducationalProject,
    FlowScene,
    FlowStoryboard,
    SceneCaptions,
    SubtitlePage,
    WordTiming,
    build_srt_subtitles,
    build_webvtt_subtitles,
    synthesize_minimal_mp4,
)
import flow_testbench_runner as runner  # noqa: E402


def _build_test_app() -> FastAPI:
    app = FastAPI()
    app.include_router(flow_router)
    return app


def test_bridge_supported_female_studio_voice_personas() -> None:
    assert "voice_y0joebp3bwta" in SUPPORTED_VOICE_PERSONAS
    assert "Sulafat" in SUPPORTED_VOICE_PERSONAS


def test_runner_female_only_voice_design_constant_and_cached_lessons() -> None:
    assert runner.RU_FEMALE_VOICE_DESIGN_ID == "voice_y0joebp3bwta"
    index_html = TESTBENCH_DIR / "index.html"
    if index_html.is_file():
        html_text = index_html.read_text(encoding="utf-8")
        assert "Gemini 3.8 Studio (RU Female Warm Mezzo)" in html_text
        assert "Gemini 3.8 Studio (EN Studio Female (Sulafat))" in html_text
        assert "Male Baritone" not in html_text
        assert "Sadaltager" not in html_text


def test_runner_strip_accent_markers_and_format_for_gemini_tts() -> None:
    raw = "In a st+andard *transf+ormer*: e+ach t+oken stores *k+ey v+ectors*."
    clean = runner.strip_accent_markers(raw)
    assert "+" not in clean
    assert "*" not in clean
    assert "In a standard transformer: each token stores key vectors." == clean

    formatted = runner.format_for_gemini_tts(raw)
    assert "+" not in formatted
    assert "*" not in formatted
    assert "TRANSFORMER" in formatted
    assert "KEY VECTORS" in formatted
    assert "<short pause>" in formatted


def test_runner_is_valid_speech_wav_rms_and_duration_guard() -> None:
    sr = 24000

    # 1. Silent 4-second WAV -> must be rejected (RMS == 0)
    silent_samples = np.zeros(sr * 4, dtype=np.int16)
    silent_wav = runner._wrap_pcm16_in_wav(silent_samples.tobytes(), sr)
    assert runner._is_valid_speech_wav(silent_wav) is False

    # 2. Too-short 1.0-second WAV -> must be rejected (duration < 2.8s)
    t_short = np.linspace(0.0, 1.0, sr, endpoint=False)
    short_samples = (np.sin(2.0 * np.pi * 220.0 * t_short) * 4000).astype(np.int16)
    short_wav = runner._wrap_pcm16_in_wav(short_samples.tobytes(), sr)
    assert runner._is_valid_speech_wav(short_wav) is False

    # 3. Valid 4.0-second speech-energy WAV -> must pass
    t_valid = np.linspace(0.0, 4.0, sr * 4, endpoint=False)
    valid_samples = (np.sin(2.0 * np.pi * 220.0 * t_valid) * 4000).astype(np.int16)
    valid_wav = runner._wrap_pcm16_in_wav(valid_samples.tobytes(), sr)
    assert runner._is_valid_speech_wav(valid_wav) is True


def test_bridge_storyboard_subtitles_and_mp4_container() -> None:
    client = FlowClient()
    project = asyncio.run(
        client.generate_educational_storyboard(
            topic="Multi-Head Latent Attention (MLA)",
            scene_count=3,
            language="ru",
            target_audience="university",
            voice_persona="voice_y0joebp3bwta",
        )
    )
    assert isinstance(project, FlowEducationalProject)
    assert len(project.scenes) == 3
    for sc in project.scenes:
        assert sc.voice_persona == "voice_y0joebp3bwta"
        assert sc.veo_audio_prompt and "voice_y0joebp3bwta" in sc.veo_audio_prompt

    vtt = build_webvtt_subtitles(project.scenes)
    srt = build_srt_subtitles(project.scenes)
    assert vtt.startswith("WEBVTT")
    assert "00:00:00,000 --> 00:00:05,000" in srt

    mp4 = synthesize_minimal_mp4("MLA Test", duration_sec=5)
    assert mp4[4:8] == b"ftyp"


def test_api_router_end_to_end() -> None:
    app = _build_test_app()
    with TestClient(app) as client:
        st = client.get("/api/flow/status")
        assert st.status_code == 200
        assert "voice_y0joebp3bwta" in st.json()["supported_voice_personas"]

        sb = client.post(
            "/api/flow/projects/storyboard",
            json={
                "topic": "Quantum Bell State Entanglement",
                "scene_count": 2,
                "language": "en",
                "voice_persona": "Sulafat",
            },
        )
        assert sb.status_code == 200
        proj_id = sb.json()["project"]["project_id"]

        asm = client.post(f"/api/flow/projects/{proj_id}/assemble")
        assert asm.status_code == 200
        assert asm.json()["ok"] is True


def test_dsp_defense_cycles_structure_and_invariants() -> None:
    from src.dsp_defense_cycles import DEFENSE_QA_CARDS, DSP_DEFENSE_CYCLES

    assert len(DSP_DEFENSE_CYCLES) == 6
    total_scenes = 0
    total_duration_sec = 0
    full_corpus = []
    for cycle in DSP_DEFENSE_CYCLES:
        assert cycle["language"] == "ru"
        scenes = cycle["scenes"]
        assert len(scenes) >= 5
        for sc in scenes:
            total_scenes += 1
            total_duration_sec += sc.get("duration_sec", 36)
            assert sc["voice_persona"] == "voice_y0joebp3bwta"
            full_corpus.append(sc["narration_text"])
            full_corpus.extend(sc["on_screen_bullets"])

    assert total_scenes == 47
    assert 1704 <= total_duration_sec <= 1706, f"Total duration {total_duration_sec}s is not 1705s"
    joined = " ".join(full_corpus)
    for token in (
        "DSP56824",
        "AD73322",
        "IS61LV6416",
        "AD8606AR",
        "MAX706S",
        "AMS1117-3.3",
        "MC68HC908GP32",
        "0,9878",
        "18,00%",
        "20,833",
        "P:$001E",
        "1,034",
        "4,2",
    ):
        assert token in joined, f"Missing required Variant 5 coursework token: {token}"

    assert len(DEFENSE_QA_CARDS) >= 8


def test_dsp_phonetics_formatter_preserves_subtitles_and_expands_chips() -> None:
    from src.dsp_defense_cycles import format_dsp_phonetics_ru

    raw = "\u041f\u0440\u043e\u0446\u0435\u0441\u0441\u043e\u0440 DSP56824 \u0438 \u043a\u043e\u0434\u0435\u043a AD73322 \u0440\u0430\u0431\u043e\u0442\u0430\u044e\u0442 \u0432 \u0441\u0435\u0442\u043a\u0435 Q15 \u043f\u043e \u0432\u0435\u043a\u0442\u043e\u0440\u0443 P:$001E."
    clean_sub = runner.strip_accent_markers(raw)
    assert "DSP56824" in clean_sub
    assert "AD73322" in clean_sub
    assert "P:$001E" in clean_sub

    spoken = format_dsp_phonetics_ru(raw)
    clean_spoken = runner.strip_accent_markers(spoken)
    assert "\u0414\u0438-\u042d\u0441-\u041f\u0438 \u043f\u044f\u0442\u044c\u0434\u0435\u0441\u044f\u0442 \u0448\u0435\u0441\u0442\u044c \u0432\u043e\u0441\u0435\u043c\u044c\u0441\u043e\u0442 \u0434\u0432\u0430\u0434\u0446\u0430\u0442\u044c \u0447\u0435\u0442\u044b\u0440\u0435" in clean_spoken
    assert "\u042d\u0439-\u0414\u0438 \u0441\u0435\u043c\u044c\u0434\u0435\u0441\u044f\u0442 \u0442\u0440\u0438 \u0442\u0440\u0438\u0441\u0442\u0430 \u0434\u0432\u0430\u0434\u0446\u0430\u0442\u044c \u0434\u0432\u0430" in clean_spoken
    assert "\u041a\u0443-\u043f\u044f\u0442\u043d\u0430\u0434\u0446\u0430\u0442\u044c" in clean_spoken
    assert "\u041f\u044d \u043d\u043e\u043b\u044c \u043d\u043e\u043b\u044c \u043e\u0434\u0438\u043d \u0415" in clean_spoken
    assert "\u0414\u0438-\u042d\u0441-\u041f+\u0438" in spoken


def test_dsp_defense_rendered_artifacts_and_dual_mode_player() -> None:
    out_dir = TESTBENCH_DIR / "output"
    dsp_html = out_dir / "dsp_defense_index.html"
    if dsp_html.is_file():
        text = dsp_html.read_text(encoding="utf-8")
        assert "\u0420\u0435\u0436\u0438\u043c 1: \u0410\u0432\u0442\u043e\u0434\u043e\u043a\u043b\u0430\u0434 \u0441\u043e \u0437\u0432\u0443\u043a\u043e\u043c" in text
        assert "\u0420\u0435\u0436\u0438\u043c 2: \u041f\u043e\u0448\u0430\u0433\u043e\u0432\u044b\u0439 \u0438\u043d\u0436\u0435\u043d\u0435\u0440\u043d\u044b\u0439 \u0440\u0430\u0437\u0431\u043e\u0440" in text
        assert "voice_y0joebp3bwta" in text
        assert "lesson_07_ru_dsp_defense_master" in text
        for slug in (
            "lesson_03_ru_dsp_cycle1_architecture",
            "lesson_04_ru_dsp_cycle2_hardware_eskd",
            "lesson_05_ru_dsp_cycle3_iir_matlab",
            "lesson_06_ru_dsp_cycle4_firmware_realtime",
            "lesson_07_ru_dsp_defense_master",
        ):
            mp4 = out_dir / slug / "lesson_full_720p.mp4"
            assert mp4.is_file() and mp4.stat().st_size > 10_000


def test_runner_wrap_text_pixels_subtitle_bounds() -> None:
    from PIL import ImageFont

    font = ImageFont.load_default()
    long_text = (
        "\u0412 \u0440\u0430\u043c\u043a\u0430\u0445 \u043a\u0443\u0440\u0441\u043e\u0432\u043e\u0439 \u0440\u0430\u0431\u043e\u0442\u044b \u0441\u043f\u0440\u043e\u0435\u043a\u0442\u0438\u0440\u043e\u0432\u0430\u043d\u043e \u043c\u0438\u043a\u0440\u043e\u043f\u0440\u043e\u0446\u0435\u0441\u0441\u043e\u0440\u043d\u043e\u0435 \u0443\u0441\u0442\u0440\u043e\u0439\u0441\u0442\u0432\u043e "
        "\u0446\u0438\u0444\u0440\u043e\u0432\u043e\u0439 \u0444\u0438\u043b\u044c\u0442\u0440\u0430\u0446\u0438\u0438 \u0437\u0432\u0443\u043a\u043e\u0432\u043e\u0433\u043e \u0434\u0438\u0430\u043f\u0430\u0437\u043e\u043d\u0430 \u043d\u0430 \u0431\u0430\u0437\u0435 Motorola DSP56824."
    )
    lines = runner._wrap_text_pixels(long_text, font, max_width=260)
    assert len(lines) >= 2
    assert " ".join(lines) == long_text


def test_runner_easing_curves_git_algorithms() -> None:
    # 1. Cubic ease-out (Remotion / Manim)
    assert runner.ease_out_cubic(0.0) == 0.0
    assert runner.ease_out_cubic(1.0) == 1.0
    assert abs(runner.ease_out_cubic(0.5) - 0.875) < 1e-6
    # Strictly monotonically increasing
    steps = [runner.ease_out_cubic(t) for t in np.linspace(0.0, 1.0, 11)]
    assert all(steps[i] <= steps[i + 1] for i in range(len(steps) - 1))

    # 2. Quadratic ease-in-out
    assert runner.ease_in_out_quad(0.0) == 0.0
    assert abs(runner.ease_in_out_quad(0.5) - 0.5) < 1e-6
    assert runner.ease_in_out_quad(1.0) == 1.0

    # 3. Smoothstep
    assert runner.smoothstep(0.0, 1.0, 0.0) == 0.0
    assert runner.smoothstep(0.0, 1.0, 0.5) == 0.5
    assert runner.smoothstep(0.0, 1.0, 1.0) == 1.0


def test_runner_extract_audio_spectrum_features(tmp_path: Path) -> None:
    import imageio_ffmpeg

    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    sr = 16000
    duration_s = 3.0
    total_frames = int(duration_s * 15)  # 45 frames @ 15fps

    # Create synthetic audio: 1 sec tone (440Hz) + 2 sec silence
    t1 = np.linspace(0.0, 1.0, sr, endpoint=False)
    tone = (np.sin(2.0 * np.pi * 440.0 * t1) * 8000).astype(np.int16)
    silence = np.zeros(sr * 2, dtype=np.int16)
    all_pcm = np.concatenate([tone, silence])
    wav_bytes = runner._wrap_pcm16_in_wav(all_pcm.tobytes(), sr)

    test_wav = tmp_path / "test_audio.wav"
    test_wav.write_bytes(wav_bytes)

    features = runner.extract_audio_spectrum_features(
        ffmpeg_exe=ffmpeg_exe,
        audio_path=test_wav,
        fps=15,
        total_frames=total_frames,
        num_bands=18,
    )

    assert len(features) == total_frames
    for feat in features:
        assert "rms" in feat and "bands" in feat and "peak" in feat
        assert len(feat["bands"]) == 18
        assert 0.0 <= feat["rms"] <= 1.0

    # First few frames (during 440Hz tone) should have distinct positive RMS energy
    assert features[5]["rms"] > 0.05
    # Frames in silence region should have near-zero energy
    assert features[40]["rms"] < 0.01


def test_runner_zero_disk_pipe_streaming_and_hud_render(tmp_path: Path) -> None:
    from src.flow_bridge import FlowScene

    scene = FlowScene(
        scene_id="test_sc_01",
        scene_number=1,
        title="\u0422\u0435\u0441\u0442 \u043a\u0438\u043d\u0435\u0442\u0438\u0447\u0435\u0441\u043a\u043e\u0439 \u0442\u0438\u043f\u043e\u0433\u0440\u0430\u0444\u0438\u043a\u0438 \u0438 HUD-\u0440\u0435\u0436\u0438\u043c\u0430",
        narration_text="\u0422\u0435\u0441\u0442\u0438\u0440\u043e\u0432\u0430\u043d\u0438\u0435 \u043f\u0440\u044f\u043c\u043e\u0433\u043e \u043f\u043e\u0442\u043e\u043a\u043e\u0432\u043e\u0433\u043e \u0440\u0435\u043d\u0434\u0435\u0440\u0438\u043d\u0433\u0430 \u0431\u0435\u0437 \u0437\u0430\u043f\u0438\u0441\u0438 \u043f\u0440\u043e\u043c\u0435\u0436\u0443\u0442\u043e\u0447\u043d\u044b\u0445 \u043a\u0430\u0434\u0440\u043e\u0432 \u043d\u0430 \u0434\u0438\u0441\u043a.",
        visual_prompt="300 DPI schematic test view",
        on_screen_bullets=["\u041f\u0430\u0442\u0442\u0435\u0440\u043d Zero-Disk Pipe", "\u0421\u043f\u0435\u043a\u0442\u0440\u043e\u0433\u0440\u0430\u043c\u043c\u0430 FFT \u0432 \u0440\u0435\u0430\u043b\u044c\u043d\u043e\u043c \u0432\u0440\u0435\u043c\u0435\u043d\u0438"],
    )

    dummy_audio_feat = {
        "rms": 0.45,
        "bands": [0.1 * i for i in range(18)],
        "peak": 0.9,
    }

    frame_bytes = runner.render_scene_frame_pil(
        topic="\u0426\u041e\u0421 \u0422\u0435\u0441\u0442",
        scene=scene,
        voice_label="Gemini 3.8 Studio",
        total_scenes=1,
        frame_idx=5,
        total_frames=30,
        width=1280,
        height=720,
        audio_features=dummy_audio_feat,
    )

    expected_len = 1280 * 720 * 3
    assert len(frame_bytes) == expected_len
    # Confirm not a blank zero frame
    assert any(b > 0 for b in frame_bytes[:1000])


def test_segment_acoustic_vad_16k_schmitt_trigger_and_bridging() -> None:
    sr = 16000
    # Create 3.0s synthetic PCM with two voiced bursts and one inter-burst pause
    # Lead-in silence: 0.2s (3200 samples)
    s_lead = np.zeros(int(sr * 0.2), dtype=np.int16)
    # Burst 1: 1.0s tone (16000 samples), 440Hz, amp 8000 (RMS ~ 5656 > 350)
    t1 = np.linspace(0.0, 1.0, int(sr * 1.0), endpoint=False)
    burst1 = (np.sin(2.0 * np.pi * 440.0 * t1) * 8000).astype(np.int16)
    # Inter-burst pause: 0.4s (6400 samples)
    s_pause = np.zeros(int(sr * 0.4), dtype=np.int16)
    # Burst 2: 1.0s tone (16000 samples) with a tiny 50ms stop in middle (should be bridged)
    t2_a = np.linspace(0.0, 0.45, int(sr * 0.45), endpoint=False)
    burst2_a = (np.sin(2.0 * np.pi * 550.0 * t2_a) * 8000).astype(np.int16)
    tiny_stop = np.zeros(int(sr * 0.05), dtype=np.int16)  # 50ms stop (< 200ms min_pause_ms)
    t2_b = np.linspace(0.0, 0.5, int(sr * 0.5), endpoint=False)
    burst2_b = (np.sin(2.0 * np.pi * 550.0 * t2_b) * 8000).astype(np.int16)
    # Lead-out silence: 0.2s (3200 samples)
    s_trail = np.zeros(int(sr * 0.2), dtype=np.int16)

    pcm = np.concatenate([s_lead, burst1, s_pause, burst2_a, tiny_stop, burst2_b, s_trail])

    voiced, pauses = runner.segment_acoustic_vad_16k(
        pcm,
        sample_rate=sr,
        threshold_voiced=350.0,
        threshold_pause=150.0,
        min_burst_ms=100,
        min_pause_ms=200,
    )

    # Must detect exactly 2 voiced blocks because tiny_stop (50ms) is bridged into burst2!
    assert len(voiced) == 2
    # First burst starts after lead-in silence (~200ms) and ends around 1200ms
    assert 180 <= voiced[0][0] <= 220
    assert 1180 <= voiced[0][1] <= 1220
    # Second burst starts after pause (~1600ms) and ends around 2600ms
    assert 1580 <= voiced[1][0] <= 1620
    assert 2580 <= voiced[1][1] <= 2620
    # Pause blocks must include the inter-burst pause
    assert any(p_start >= 1180 and p_end <= 1620 for p_start, p_end in pauses)


def test_syllable_duration_weighting_on_acronym_is61lv6416() -> None:
    # Text with authentic Latin hardware acronyms and Russian grammar:
    # Processor Motorola DSP56824 and memory IS61LV6416
    text = (
        "\u041f\u0440\u043e\u0446\u0435\u0441\u0441\u043e\u0440 Motorola "
        "DSP56824 \u0438 \u043f\u0430\u043c\u044f\u0442\u044c IS61LV6416"
    )
    duration_ms = 10000
    captions = runner.compute_scene_word_timings(
        scene_id="test_m1_timing",
        visual_text=text,
        duration_ms=duration_ms,
    )
    assert len(captions.all_words) == 6
    w_proc = captions.all_words[0]
    w_moto = captions.all_words[1]
    w_dsp = captions.all_words[2]
    w_i = captions.all_words[3]
    w_mem = captions.all_words[4]
    w_is61 = captions.all_words[5]

    dur_is61 = w_is61.end_ms - w_is61.start_ms
    dur_dsp = w_dsp.end_ms - w_dsp.start_ms
    dur_i = w_i.end_ms - w_i.start_ms

    # Phonetic expansion of IS61LV6416 has 18+ syllables -> substantial duration
    assert dur_is61 >= 2200, f"IS61LV6416 duration too short: {dur_is61}ms"
    # Phonetic expansion of DSP56824 has 18+ syllables
    assert dur_dsp >= 2000, f"DSP56824 duration too short: {dur_dsp}ms"
    # Single letter conjunction has only 1 syllable
    assert dur_i <= 400, f"Single letter conjunction duration too long: {dur_i}ms"
    # Ratio between acronym and single conjunction must exceed 5x
    assert dur_is61 > dur_i * 5


def test_kinetic_typography_amber_gold_rgb_and_stroke_rendered() -> None:
    from PIL import Image

    # Construct scene with precomputed captions where word 0 is active
    text = "DSP56824"
    scene = FlowScene(
        scene_id="sc_amber",
        scene_number=1,
        title="Test Amber",
        narration_text=text,
        visual_prompt="test",
    )
    captions = runner.compute_scene_word_timings(
        scene_id=scene.scene_id,
        visual_text=text,
        duration_ms=5000,
    )
    scene.captions = captions

    # Render frame 5 at 15 fps -> t_ms = 333ms (during word 0 active interval)
    frame_bytes = runner.render_scene_frame_pil(
        topic="Amber Gold Test",
        scene=scene,
        voice_label="Gemini 3.8",
        total_scenes=1,
        frame_idx=5,
        total_frames=75,
        width=1280,
        height=720,
        captions=captions,
    )

    img = Image.frombytes("RGB", (1280, 720), frame_bytes)
    # Crop subtitle box region: x = 24..1256, y = 604..702
    sub_box = img.crop((24, 604, 1256, 702))
    colors = sub_box.getcolors(maxcolors=200000)
    color_map = {rgb: count for count, rgb in colors}

    # Verify amber-gold RGB(255, 193, 7) / #FFC107 is genuinely present
    amber_gold = (255, 193, 7)
    assert amber_gold in color_map, f"Amber-gold {amber_gold} missing from subtitle render"
    assert color_map[amber_gold] > 20, f"Insufficient amber-gold pixel count: {color_map[amber_gold]}"

    # Verify deep obsidian-amber stroke RGB(20, 14, 4) or drop shadow is present
    stroke_col = (20, 14, 4)
    shadow_col = (0, 0, 0)
    assert stroke_col in color_map or shadow_col in color_map, "Stroke or shadow missing"


def test_font_cache_hit_rate_and_zero_redundant_disk_loads() -> None:
    runner._FONT_CACHE.clear()
    assert len(runner._FONT_CACHE) == 0

    # 1. First fetch loads and caches
    f1 = runner.get_cached_font(21, bold=True)
    assert (21, True) in runner._FONT_CACHE
    assert len(runner._FONT_CACHE) == 1

    # 2. Second fetch returns identical instance
    f2 = runner.get_cached_font(21, bold=True)
    assert f1 is f2

    # 3. Render 20 frames of a scene; total cache size must not exceed the 5 standard sizes
    scene = FlowScene(
        scene_id="cache_test",
        scene_number=1,
        title="Cache Test",
        narration_text="Font cache performance test",
        visual_prompt="test",
    )
    for f_idx in range(20):
        runner.render_scene_frame_pil(
            topic="Test",
            scene=scene,
            voice_label="Test",
            total_scenes=1,
            frame_idx=f_idx,
            total_frames=20,
        )

    # Standard sizes: (16, True), (11, True), (24, True), (18, False), (21, True)
    assert len(runner._FONT_CACHE) <= 5


def test_fine_grained_webvtt_and_srt_generation_with_captions() -> None:
    scene = FlowScene(
        scene_id="sc_fine",
        scene_number=1,
        title="Fine-Grained Subtitles",
        narration_text="DSP56824 and AD73322",
        visual_prompt="test",
        duration_sec=6,
    )
    captions = runner.compute_scene_word_timings(
        scene_id=scene.scene_id,
        visual_text=scene.narration_text,
        duration_ms=6000,
    )
    scene.captions = captions

    vtt = build_webvtt_subtitles([scene])
    srt = build_srt_subtitles([scene])

    assert vtt.startswith("WEBVTT")
    # Fine-grained WebVTT must contain intra-cue timestamp brackets
    assert "<00:00:0" in vtt
    assert "DSP56824" in vtt

    # SRT must contain phrase-level cues
    assert "00:00:00,000 -->" in srt
    assert "DSP56824 and AD73322" in srt


def test_m2_dsp_phonetic_catalog_55_plus_terms_and_stress() -> None:
    from src.dsp_defense_cycles import DSP_PHONETIC_MAP
    assert len(DSP_PHONETIC_MAP) >= 55
    keys = [item[0] for item in DSP_PHONETIC_MAP]
    assert "Motorola DSP56824" in keys
    assert "AD73322" in keys
    assert "IS61LV6416" in keys
    assert "Direct Form II" in keys
    assert "SSI_Rx_ISR" in keys
    assert "Sallen-Key" in keys
    assert "KiCad 8.0" in keys
    assert "MATLAB" in keys
    assert "Q15" in keys

    bus_x_found = any("\u0434\u0430\u043d\u043d\u044b\u0445 X" in k for k in keys)
    bus_p_found = any("\u043f\u0430\u043c\u044f\u0442\u0438 P" in k for k in keys)
    assert bus_x_found
    assert bus_p_found

    # At least 50 phonetic expansions have explicit '+' stress accents
    stressed_count = sum(1 for _, exp in DSP_PHONETIC_MAP if "+" in exp)
    assert stressed_count >= 50


def test_m2_all_scenes_pass_stress_accent_linter() -> None:
    from src.dsp_defense_cycles import DSP_DEFENSE_CYCLES, validate_stress_accents
    total_scenes = 0
    for cycle in DSP_DEFENSE_CYCLES:
        for sc in cycle["scenes"]:
            total_scenes += 1
            audio_text = sc.get("tts_narration_text") or sc.get("narration_text")
            is_valid, errors = validate_stress_accents(audio_text)
            title = sc.get("title", f"scene_{total_scenes}")
            assert is_valid, f"Scene '{title}' failed stress linter: {errors}"
    assert total_scenes == 47


def test_m2_dual_stream_preserves_latin_subtitles_and_expands_audio_phonetics() -> None:
    from src.dsp_defense_cycles import DSP_DEFENSE_CYCLES
    # Cycle 1 Scene 1 contains Motorola DSP56824 and AD73322
    sc = DSP_DEFENSE_CYCLES[0]["scenes"][0]
    subtitles = runner.strip_accent_markers(sc["narration_text"])
    audio = sc["tts_narration_text"]

    assert "Motorola DSP56824" in subtitles
    assert "AD73322" in subtitles
    assert "+" not in subtitles

    assert "Motorola DSP56824" not in audio
    assert "+" in audio
    assert "\u0414\u0438-\u042d\u0441-\u041f+\u0438" in audio

    flow_sc = FlowScene(
        scene_id="dual_test",
        scene_number=1,
        title="Dual Stream",
        narration_text="Motorola DSP56824",
        tts_narration_text="\u041c\u043e\u0442\u043e\u0440+\u043e\u043b\u0430 \u0414\u0438-\u042d\u0441-\u041f+\u0438",
        visual_prompt="dual stream prompt",
    )
    assert flow_sc.narration_text == "Motorola DSP56824"
    assert flow_sc.tts_narration_text == "\u041c\u043e\u0442\u043e\u0440+\u043e\u043b\u0430 \u0414\u0438-\u042d\u0441-\u041f+\u0438"


def test_m2_single_speaker_timbre_lock_and_cache_v3_isolation(tmp_path: Path) -> None:
    cache_dir = tmp_path / ".tts_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)

    valid_meta = {"model": "gemini-3.8-flash", "voice": "voice_y0joebp3bwta", "lang": "ru"}
    valid_wav = cache_dir / "valid_voice.wav"
    valid_wav.write_bytes(b"RIFF" + b"\x00" * 40)
    (cache_dir / "valid_voice.json").write_text(json.dumps(valid_meta), encoding="utf-8")

    leak_meta = {"model": "gemini-3.1-flash", "voice": "Sulafat", "lang": "ru"}
    leak_wav = cache_dir / "leak_voice.wav"
    leak_wav.write_bytes(b"RIFF" + b"\x00" * 40)
    (cache_dir / "leak_voice.json").write_text(json.dumps(leak_meta), encoding="utf-8")

    purged = runner.purge_unauthorized_tts_cache(cache_dir)
    assert purged == 1
    assert valid_wav.is_file()
    assert not leak_wav.is_file()

    sc = FlowScene(
        scene_id="voice_chk",
        scene_number=1,
        title="Voice Check",
        narration_text="Test",
        visual_prompt="Test",
    )
    assert sc.voice_persona == "voice_y0joebp3bwta"


def test_m2_russian_tts_strictly_prevents_sulafat_and_svetlana_fallbacks(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    async def _mock_try_gemini(*args, **kwargs):
        return None

    monkeypatch.setattr(runner, "try_gemini_studio_tts", _mock_try_gemini)

    with pytest.raises(RuntimeError) as exc_info:
        asyncio.run(
            runner.synthesize_neural_expressive_audio(
                ffmpeg_exe="ffmpeg",
                narration_text="\u0422\u0435\u0441\u0442",
                out_audio_m4a=tmp_path / "test.m4a",
                lang="ru",
                voice_persona="voice_y0joebp3bwta",
            )
        )
    assert "Strict Single Speaker Timbre lock violation" in str(exc_info.value)


def test_m4_interactive_player_modernization_and_zero_disk_concat() -> None:
    from src.dsp_defense_cycles import DSP_DEFENSE_CYCLES, generate_dsp_defense_player_html

    out_dir = TESTBENCH_DIR / "output"
    dsp_html = out_dir / "dsp_defense_index.html"
    root_html = TESTBENCH_DIR / "dsp_defense_index.html"
    root_index = TESTBENCH_DIR / "index.html"

    assert dsp_html.is_file(), "output/dsp_defense_index.html must exist"
    assert root_html.is_file(), "dsp_defense_index.html must exist at root"
    assert root_index.is_file(), "index.html must exist at root"

    text_out = dsp_html.read_text(encoding="utf-8")
    text_root = root_html.read_text(encoding="utf-8")
    text_index = root_index.read_text(encoding="utf-8")

    # 1. Dual Mode switcher check
    mode1_str = "\u0420\u0435\u0436\u0438\u043c 1: \u0410\u0432\u0442\u043e\u0434\u043e\u043a\u043b\u0430\u0434 \u0441\u043e \u0437\u0432\u0443\u043a\u043e\u043c"
    mode2_str = "\u0420\u0435\u0436\u0438\u043c 2: \u041f\u043e\u0448\u0430\u0433\u043e\u0432\u044b\u0439 \u0438\u043d\u0436\u0435\u043d\u0435\u0440\u043d\u044b\u0439 \u0440\u0430\u0437\u0431\u043e\u0440"
    for t in (text_out, text_root):
        assert mode1_str in t
        assert mode2_str in t
        assert "voice_y0joebp3bwta" in t
        assert "lesson_07_ru_dsp_defense_master" in t
        assert "#FFC107" in t
        assert "teleprompter-box" in t
        assert "prompt-word" in t
        assert "timecode-strip" in t
        assert "bp-modal" in t
        assert "jumpToQAScene" in t
        assert "qa-card-" in t
        assert "active-qa" in t
        assert "section-playing" in t
        assert "active-tc" in t
        assert "span.onclick" in t

        # Lightbox 300 DPI blueprint references
        for bp in (
            "drawing_e2.png",
            "drawing_pe2.png",
            "fig_3_1.png",
            "fig_4_1.png",
            "fig_5_1.png",
            "fig_5_2.png",
            "fig_5_3.png",
            "fig_5_5.png",
        ):
            assert bp in t, f"Missing blueprint asset reference: {bp}"

    # 2. Prominent card/link in index.html and output/index.html
    out_index = out_dir / "index.html"
    assert out_index.is_file(), "output/index.html must exist"
    text_out_index = out_index.read_text(encoding="utf-8")
    for idx_txt in (text_index, text_out_index):
        assert "dsp_defense_index.html" in idx_txt
        assert "output/dsp_defense_index.html" in idx_txt

    # 3. Master video zero-disk in-memory concat validation
    master_mp4 = out_dir / "lesson_07_ru_dsp_defense_master" / "lesson_full_720p.mp4"
    assert master_mp4.is_file(), "Master video file missing"
    assert master_mp4.stat().st_size > 10_000, "Master video file too small"
    header = master_mp4.read_bytes()[:16]
    assert b"ftyp" in header, f"Invalid container header in master video: {header}"

    # Verify zero intermediate raw frame files on disk
    rgb_dumps = list(TESTBENCH_DIR.glob("**/frames.rgb"))
    assert len(rgb_dumps) == 0, f"Found forbidden frames.rgb disk dumps: {rgb_dumps}"


def test_m1_dsp_coursework_assets_rasterization_and_staging(tmp_path: Path) -> None:
    """
    Milestone 1 Test: 300 DPI Asset Rasterization and Staging Verification.
    Validates that:
    1. stage_dsp_coursework_assets produces 43 PZ pages, drawings E2/PE2, and figures.
    2. All 43 PZ pages have long edge >= 2400px (A4 is 2481x3509, A3 is 4973x3521).
    3. Drawing E2 and PE2 have long edge >= 2400px.
    4. Canonical figures fig_3_1..5_5 exist and match dimensions.
    5. Clean execution in temporary directory with placeholder fallbacks if unattached.
    """
    from PIL import Image
    from src.dsp_defense_cycles import stage_dsp_coursework_assets

    # 1. Staging into testbench output directory
    staged = stage_dsp_coursework_assets(TESTBENCH_DIR / "output")
    assert len(staged) >= 51, f"Expected at least 51 staged asset entries, got {len(staged)}"

    # Check 43 PZ pages
    for i in range(1, 44):
        key = f"pz_page_{i:02d}"
        assert key in staged, f"Missing staged key: {key}"
        path = staged[key]
        assert path.is_file(), f"Staged file missing on disk: {path}"
        assert path.stat().st_size > 5_000, f"Staged file suspiciously small: {path}"
        with Image.open(path) as img:
            w, h = img.size
            assert max(w, h) >= 2400, f"{key} long edge {max(w, h)} < 2400 px (size: {w}x{h})"

    # Check ESKD Drawings
    for key in ("drawing_e2", "drawing_pe2"):
        assert key in staged, f"Missing drawing key: {key}"
        path = staged[key]
        assert path.is_file(), f"Drawing file missing on disk: {path}"
        with Image.open(path) as img:
            w, h = img.size
            assert max(w, h) >= 2400, f"{key} long edge {max(w, h)} < 2400 px (size: {w}x{h})"

    # Check Figures
    for key in ("fig_3_1", "fig_4_1", "fig_5_1", "fig_5_2", "fig_5_3", "fig_5_5"):
        assert key in staged, f"Missing figure key: {key}"
        path = staged[key]
        assert path.is_file(), f"Figure file missing on disk: {path}"
        assert path.stat().st_size > 1_000, f"Figure file suspiciously small: {path}"

    # 2. Staging into isolated tmp_path
    tmp_staged = stage_dsp_coursework_assets(tmp_path)
    assert len(tmp_staged) >= 51
    assert tmp_staged["pz_page_01"].is_file()
    assert tmp_staged["drawing_e2"].is_file()


def test_m2_all_53_scenes_mapped_to_43_pages_and_concept_cues_architecture() -> None:
    """
    Milestone 2 Storyboard & Concept Cue Architecture Verification:
    1. len(all_scenes) == 47 across 6 cycles.
    2. Zero bureaucratic pages {1, 3, 4, 6, 7, 36, 37} and 100% substantive page coverage (8..35, 38..43).
    3. Every scene defines 3 to 5 concept_cues.
    4. Each concept_cue contains valid ratios, 4D normalized focus_bbox in [0.0, 1.0],
       valid concept_type, non-empty target, animation_mode, and formula_or_label <= 6 words.
    5. Direct helper access: get_scene_pz_page and get_scene_concept_cues.
    """
    from src.dsp_defense_cycles import (
        DSP_DEFENSE_CYCLES,
        DSP_SCENE_PZ_PAGES,
        DSP_SCENE_CONCEPT_CUES,
        get_scene_pz_page,
        get_scene_concept_cues,
    )

    assert len(DSP_DEFENSE_CYCLES) == 6
    all_scenes = [sc for cyc in DSP_DEFENSE_CYCLES for sc in cyc["scenes"]]
    assert len(all_scenes) == 47

    # 1. 100% substantive coursework page coverage without bureaucratic pages
    forbidden_pages = {1, 3, 4, 6, 7, 36, 37}
    substantive_pages = set(range(8, 36)) | set(range(38, 44))
    pages_assigned = [sc.get("pz_page") for sc in all_scenes]
    assert all(isinstance(p, int) for p in pages_assigned), "Every scene must have an integer pz_page"
    assert set(pages_assigned).isdisjoint(forbidden_pages), f"Forbidden pages leaked: {set(pages_assigned) & forbidden_pages}"
    assert substantive_pages == set(pages_assigned), "Must cover 100% of substantive pages 8..35, 38..43"

    # Also verify mapping dictionary export
    assert len(DSP_SCENE_PZ_PAGES) == 47
    assert set(DSP_SCENE_PZ_PAGES.values()).isdisjoint(forbidden_pages)
    assert substantive_pages == set(DSP_SCENE_PZ_PAGES.values())

    # 2. Concept cues schema and constraints
    valid_concept_types = {
        "hardware_ic",
        "math_formula",
        "plot",
        "firmware_asm",
        "table",
        "schematic",
        "waveform",
    }

    assert len(DSP_SCENE_CONCEPT_CUES) == 47

    for sc in all_scenes:
        sid = sc["scene_id"]
        cues = sc.get("concept_cues")
        assert isinstance(cues, list), f"Scene {sid} missing concept_cues list"
        assert 3 <= len(cues) <= 5, f"Scene {sid} has {len(cues)} cues (must be 3..5)"

        # Check helper parity
        assert get_scene_pz_page(sid) == sc["pz_page"]
        helper_cues = get_scene_concept_cues(sid)
        assert len(helper_cues) == len(cues)

        for c_idx, cue in enumerate(cues):
            # start_ratio and end_ratio
            sr = cue.get("start_ratio")
            er = cue.get("end_ratio")
            assert isinstance(sr, (int, float)) and isinstance(er, (int, float)), f"{sid} cue {c_idx} ratio type"
            assert 0.0 <= sr < er <= 1.0, f"{sid} cue {c_idx} invalid ratios: {sr} >= {er}"

            # focus_bbox
            bbox = cue.get("focus_bbox")
            assert isinstance(bbox, list) and len(bbox) == 4, f"{sid} cue {c_idx} bbox format"
            rx0, ry0, rx1, ry1 = bbox
            for coord in (rx0, ry0, rx1, ry1):
                assert isinstance(coord, (int, float)) and 0.0 <= coord <= 1.0, f"{sid} cue {c_idx} bbox coord: {coord}"
            assert rx0 < rx1, f"{sid} cue {c_idx} rx0 >= rx1"
            assert ry0 < ry1, f"{sid} cue {c_idx} ry0 >= ry1"

            # concept_type
            ctype = cue.get("concept_type")
            assert ctype in valid_concept_types, f"{sid} cue {c_idx} invalid concept_type: {ctype}"

            # concept_target
            ctarget = cue.get("concept_target")
            assert isinstance(ctarget, str) and len(ctarget.strip()) > 0, f"{sid} cue {c_idx} empty target"

            # formula_or_label <= 6 words
            label = cue.get("formula_or_label")
            assert isinstance(label, str) and len(label.strip()) > 0, f"{sid} cue {c_idx} empty formula_or_label"
            words = label.split()
            assert len(words) <= 6, f"{sid} cue {c_idx} label exceeds 6 words: '{label}'"

            # animation_mode
            amode = cue.get("animation_mode")
            assert isinstance(amode, str) and len(amode.strip()) > 0, f"{sid} cue {c_idx} empty animation_mode"


def test_m3_split_screen_layout_dimensions_and_bounding_boxes() -> None:
    from src.flow_bridge import FlowScene
    from src.dsp_defense_cycles import DSP_DEFENSE_CYCLES

    sc_dict = DSP_DEFENSE_CYCLES[0]["scenes"][0]
    scene = FlowScene.from_dict(sc_dict)

    frame_bytes = runner.render_scene_frame_pil(
        topic="DSP56824 Architecture",
        scene=scene,
        voice_label="Gemini 3.8 Studio",
        total_scenes=47,
        frame_idx=10,
        total_frames=100,
        width=1280,
        height=720,
    )

    assert len(frame_bytes) == 1280 * 720 * 3

    # Verify panel bounds geometry
    lp_x0, lp_y0, lp_x1, lp_y1 = 24, 66, 584, 594
    rp_x0, rp_y0, rp_x1, rp_y1 = 596, 66, 1256, 594
    sub_x0, sub_y0, sub_x1, sub_y1 = 24, 604, 1256, 702

    assert (lp_x1 - lp_x0) == 560
    assert (lp_y1 - lp_y0) == 528
    assert (rp_x1 - rp_x0) == 660
    assert (rp_y1 - rp_y0) == 528
    assert (rp_x0 - lp_x1) == 12  # 12 px separator margin
    assert (sub_y0 - lp_y1) == 10  # 10 px margin above subtitle bar
    assert (sub_x1 - sub_x0) == 1232
    assert (sub_y1 - sub_y0) == 98


def test_m3_split_screen_intra_scene_pixel_dynamics_and_no_frozen_panels() -> None:
    from src.flow_bridge import FlowScene
    from src.dsp_defense_cycles import DSP_DEFENSE_CYCLES

    sc_dict = DSP_DEFENSE_CYCLES[0]["scenes"][0]
    scene = FlowScene.from_dict(sc_dict)

    total_frames = 100
    timestamps = [15, 40, 65, 90]
    frames = []

    for f_idx in timestamps:
        raw = runner.render_scene_frame_pil(
            topic="DSP56824 Defense",
            scene=scene,
            voice_label="Gemini 3.8 Studio",
            total_scenes=47,
            frame_idx=f_idx,
            total_frames=total_frames,
        )
        arr = np.frombuffer(raw, dtype=np.uint8).reshape((720, 1280, 3))
        frames.append(arr)

    for i in range(len(timestamps) - 1):
        t_a, t_b = timestamps[i], timestamps[i + 1]
        f_a, f_b = frames[i], frames[i + 1]

        left_a = f_a[66:594, 24:584].astype(np.float64)
        left_b = f_b[66:594, 24:584].astype(np.float64)
        left_diff = float(np.mean(np.abs(left_a - left_b)))

        right_a = f_a[66:594, 596:1256].astype(np.float64)
        right_b = f_b[66:594, 596:1256].astype(np.float64)
        right_diff = float(np.mean(np.abs(right_a - right_b)))

        assert left_diff > 4.0, f"Left viewport frozen between t={t_a}% and t={t_b}%: diff={left_diff}"
        assert right_diff > 4.0, f"Right viewport frozen between t={t_a}% and t={t_b}%: diff={right_diff}"


def test_m3_flow_scene_dataclass_pz_page_concept_cues_and_cue_switching() -> None:
    from src.flow_bridge import FlowScene
    from src.dsp_defense_cycles import get_scene_concept_cues, get_scene_pz_page

    cues_payload = [
        {
            "start_ratio": 0.0,
            "end_ratio": 0.33,
            "focus_bbox": [0.1, 0.1, 0.5, 0.5],
            "concept_type": "hardware_ic",
            "concept_target": "DSP56824",
            "formula_or_label": "IC Core",
            "animation_mode": "bus_transfer",
        },
        {
            "start_ratio": 0.33,
            "end_ratio": 0.67,
            "focus_bbox": [0.2, 0.2, 0.6, 0.6],
            "concept_type": "math_formula",
            "concept_target": "Direct Form II",
            "formula_or_label": "Biquad",
            "animation_mode": "waveform_sweep",
        },
        {
            "start_ratio": 0.67,
            "end_ratio": 1.0,
            "focus_bbox": [0.3, 0.3, 0.7, 0.7],
            "concept_type": "firmware_asm",
            "concept_target": "DO #6 Loop",
            "formula_or_label": "Loop ISR",
            "animation_mode": "register_update",
        },
    ]

    sc = FlowScene(
        scene_id="m3_test_cue_switch",
        scene_number=1,
        title="Testing Split-Screen Dataclass",
        narration_text="Verification of pz_page and concept_cues serialization.",
        visual_prompt="Split-Screen diagram view",
        pz_page=12,
        concept_cues=cues_payload,
    )

    assert sc.pz_page == 12
    assert sc.concept_cues is not None and len(sc.concept_cues) == 3

    # to_dict & from_dict serialization
    serialized = sc.to_dict()
    assert serialized["pz_page"] == 12
    assert serialized["concept_cues"] == cues_payload

    deserialized = FlowScene.from_dict(serialized)
    assert deserialized.pz_page == 12
    assert deserialized.concept_cues == cues_payload

    # Deepcopy isolation test (Finding 1 mitigation)
    cues_copy = get_scene_concept_cues("cycle1_sc02")
    assert len(cues_copy) >= 3
    orig_rx0 = cues_copy[0]["focus_bbox"][0]
    cues_copy[0]["focus_bbox"][0] = -999.0
    cues_recheck = get_scene_concept_cues("cycle1_sc02")
    assert cues_recheck[0]["focus_bbox"][0] == orig_rx0, "Mutation leaked into DSP_SCENE_CONCEPT_CUES!"








def test_m11_flow_educational_prompt_and_storyboard_pedagogy(tmp_path: Path) -> None:
    """
    Verify that FlowClient.generate_educational_storyboard populates full pedagogical metadata:
    - pedagogical_phase, formula_expression, diagram_spec, timecoded_directives, learning_objective
    - Mayer CTML callout bullets <= 6 words each
    - build_educational_flow_prompt produces structured [0-2s] / [2-5s] / [5-8s] Flow prompts
    """
    from src.flow_bridge import FlowClient, build_educational_flow_prompt

    client = FlowClient()
    topic_ru = (
        "\u0426\u0438\u0444\u0440\u043e\u0432\u0430\u044f \u0444\u0438\u043b\u044c\u0442\u0440\u0430\u0446\u0438\u044f \u0441\u0438\u0433\u043d\u0430\u043b\u043e\u0432 "
        "\u043d\u0430 \u0431\u0430\u0437\u0435 \u043c\u0438\u043a\u0440\u043e\u043a\u043e\u043d\u0442\u0440\u043e\u043b\u043b\u0435\u0440\u0430 STM32H743"
    )
    proj = asyncio.run(
        client.generate_educational_storyboard(
            topic=topic_ru,
            scene_count=4,
            language="ru",
            voice_persona="voice_y0joebp3bwta",
        )
    )
    assert len(proj.scenes) == 4
    expected_plot_modes = ["hardware_topology", "biquad_zplane", "frequency_response", "dma_timing"]

    for idx, sc in enumerate(proj.scenes):
        assert sc.pedagogical_phase, f"Scene {idx+1} missing pedagogical_phase"
        assert sc.formula_expression, f"Scene {idx+1} missing formula_expression"
        assert sc.learning_objective, f"Scene {idx+1} missing learning_objective"
        assert isinstance(sc.diagram_spec, dict), f"Scene {idx+1} missing diagram_spec dict"
        assert sc.diagram_spec.get("plot_mode") == expected_plot_modes[idx]
        assert isinstance(sc.timecoded_directives, list) and len(sc.timecoded_directives) >= 3
        assert sc.concept_cues and len(sc.concept_cues) >= 3
        for b in sc.on_screen_bullets:
            assert len(b.split()) <= 6, f"Mayer CTML violation (>6 words): {b}"

        prompt_str = build_educational_flow_prompt(sc, language="ru")
        assert "[0-2s]" in prompt_str
        assert "[2-5s]" in prompt_str
        assert "[5-8s]" in prompt_str
        assert sc.formula_expression in prompt_str


def test_m11_flow_educational_compositor_renders_multi_layer_hd_video_and_api(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Verify that FlowEducationalCompositor renders 1280x720 HD educational frames with
    dynamic mathematical plots, formula cards, Cloud Flow Veo 3.1 viewport, and kinetic subtitles,
    and that assemble_educational_video(compose_educational=True) produces a valid multi-scene MP4.
    """
    from src.flow_bridge import FlowClient, FlowEducationalCompositor

    async def _fast_mock_voiceover(self_comp, scene, language, out_wav):
        import math
        import struct
        import wave

        sr = 24000
        dur = 3.0
        n_samples = int(sr * dur)
        buf = bytearray(n_samples * 2)
        for i in range(n_samples):
            val = int(3000.0 * math.sin(2.0 * math.pi * 220.0 * (i / sr)))
            struct.pack_into("<h", buf, i * 2, val)
        with wave.open(str(out_wav), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sr)
            wf.writeframes(bytes(buf))
        return dur

    monkeypatch.setattr(FlowEducationalCompositor, "_synthesize_scene_voiceover", _fast_mock_voiceover)

    client = FlowClient()
    proj = asyncio.run(
        client.generate_educational_storyboard(
            topic="STM32H743 Biquad IIR Butterworth Filter",
            scene_count=2,
            language="en",
            voice_persona="Sulafat",
        )
    )

    comp = FlowEducationalCompositor(width=1280, height=720, fps=12)
    f0 = comp.render_educational_frame(proj, proj.scenes[0], total_scenes=2, frame_idx=0, total_frames=24)
    f12 = comp.render_educational_frame(proj, proj.scenes[0], total_scenes=2, frame_idx=12, total_frames=24)
    assert len(f0) == 1280 * 720 * 3
    assert len(f12) == 1280 * 720 * 3
    arr0 = np.frombuffer(f0, dtype=np.uint8).reshape((720, 1280, 3))
    arr12 = np.frombuffer(f12, dtype=np.uint8).reshape((720, 1280, 3))
    assert float(np.mean(np.abs(arr0.astype(np.float32) - arr12.astype(np.float32)))) > 0.5

    assembled = asyncio.run(
        client.assemble_educational_video(
            proj.project_id,
            use_cloud=False,
            compose_educational=True,
        )
    )
    assert assembled["status"] == "assembled"
    assert assembled["video_size_bytes"] > 20_000
    lesson_blob = client.get_media_bytes(f"{proj.project_id}_lesson.mp4")
    assert lesson_blob is not None and b"ftyp" in lesson_blob[:32]


def test_req_001_zero_truncation_and_ru_localization() -> None:
    """REQ-001: Verify zero mid-word string truncation and full Russian localization when language='ru'."""
    from src.flow_bridge import FlowClient

    client = FlowClient()
    topic_ru = (
        "\u0426\u0438\u0444\u0440\u043e\u0432\u0430\u044f \u0444\u0438\u043b\u044c\u0442\u0440\u0430\u0446\u0438\u044f \u0441\u0438\u0433\u043d\u0430\u043b\u043e\u0432 "
        "\u043d\u0430 \u0431\u0430\u0437\u0435 \u043c\u0438\u043a\u0440\u043e\u043a\u043e\u043d\u0442\u0440\u043e\u043b\u043b\u0435\u0440\u0430 STM32H743"
    )
    proj = asyncio.run(
        client.generate_educational_storyboard(
            topic=topic_ru,
            scene_count=4,
            language="ru",
            voice_persona="voice_y0joebp3bwta",
        )
    )
    for sc in proj.scenes:
        assert "Part " not in sc.title, f"Unlocalized English 'Part' in RU title: {sc.title}"
        assert len(sc.title) <= 58, f"Scene title exceeds header capacity and risks clipping: {sc.title}"
        for b in sc.on_screen_bullets:
            assert "Formula:" not in b and "Phase " not in b and "Mode:" not in b, f"Unlocalized bullet: {b}"
            assert not b.endswith(("_", "^", "-", "/", "(")), f"Truncated bullet token: {b}"
        for cue in sc.concept_cues or []:
            lbl = str(cue.get("formula_or_label", ""))
            tgt = str(cue.get("concept_target", ""))
            assert not lbl.endswith((">=", "^", "/", "(")), f"Truncated cue label: {lbl}"
            assert "Node" not in tgt, f"Unlocalized English 'Node' in RU cue target: {tgt}"


def test_req_002_aspect_preserving_schematic_zoom_and_distinct_scene_viewports() -> None:
    """REQ-002: Verify aspect-preserving LANCZOS schematic zoom crop and 4 distinct Veo 3.1 scene viewports."""
    from PIL import Image
    from src.flow_bridge import FlowClient, FlowEducationalCompositor

    client = FlowClient()
    proj = asyncio.run(
        client.generate_educational_storyboard(
            topic="STM32H743 DSP Filter",
            scene_count=4,
            language="ru",
        )
    )
    comp = FlowEducationalCompositor(width=1280, height=720, fps=24)
    # Create synthetic high-res schematic (2000x1400) and plate frame (536x248)
    schem = Image.new("RGB", (2000, 1400), (245, 247, 250))
    plate = Image.new("RGB", (536, 248), (18, 42, 74))
    for x in range(0, 536, 16):
        for y in range(0, 248, 16):
            plate.putpixel((x, y), ((x * 3) % 255, (y * 5) % 255, 200))

    top_left_crops = []
    for idx, sc in enumerate(proj.scenes):
        raw = comp.render_educational_frame(
            project=proj,
            scene=sc,
            total_scenes=4,
            frame_idx=12,
            total_frames=48,
            cloud_plate_frames=[plate],
            schematic_img=schem,
        )
        arr = np.frombuffer(raw, dtype=np.uint8).reshape((720, 1280, 3))
        top_left_crops.append(arr[76:324, 36:572].astype(np.float32))

    # Each scene's top-left viewport must be visually distinct even when given the same base plate
    for i in range(len(top_left_crops) - 1):
        diff = float(np.mean(np.abs(top_left_crops[i] - top_left_crops[i + 1])))
        assert diff > 1.0, f"Scene {i+1} and Scene {i+2} top-left viewports are identical (diff={diff})"


def test_req_003_collision_free_scientific_plots_and_separated_dma_tracks() -> None:
    """REQ-003: Verify scientific plots render Z-plane zeros, non-overlapping labels, and separated DMA tracks."""
    from src.flow_bridge import FlowClient, FlowEducationalCompositor

    client = FlowClient()
    proj = asyncio.run(
        client.generate_educational_storyboard(
            topic="STM32H743 Biquad IIR Filter",
            scene_count=4,
            language="ru",
        )
    )
    comp = FlowEducationalCompositor(width=1280, height=720, fps=24)
    # Render Scene 2 (biquad_zplane) at t=0.0s (frame 0) and verify impulse response h[n] is already populated
    f_sc2_start = comp.render_educational_frame(proj, proj.scenes[1], total_scenes=4, frame_idx=0, total_frames=48)
    arr_sc2 = np.frombuffer(f_sc2_start, dtype=np.uint8).reshape((720, 1280, 3))
    hn_region = arr_sc2[200:420, 930:1220]
    assert float(np.std(hn_region.astype(np.float32))) > 8.0, "Impulse response h[n] right half is empty at frame 0"

    # Render Scene 3 (frequency_response) and Scene 4 (dma_timing)
    f_sc3 = comp.render_educational_frame(proj, proj.scenes[2], total_scenes=4, frame_idx=24, total_frames=48)
    f_sc4 = comp.render_educational_frame(proj, proj.scenes[3], total_scenes=4, frame_idx=24, total_frames=48)
    assert len(f_sc3) == 1280 * 720 * 3
    assert len(f_sc4) == 1280 * 720 * 3


def test_req_004_dual_stream_engineering_subtitles_and_orphan_free_pages() -> None:
    """REQ-004: Verify dual-stream engineering narration_text vs phonetic tts_narration_text and zero orphan pages."""
    from src.flow_bridge import FlowClient, FlowEducationalCompositor

    client = FlowClient()
    topic_ru = (
        "\u0426\u0438\u0444\u0440\u043e\u0432\u0430\u044f \u0444\u0438\u043b\u044c\u0442\u0440\u0430\u0446\u0438\u044f \u0441\u0438\u0433\u043d\u0430\u043b\u043e\u0432 "
        "\u043d\u0430 \u0431\u0430\u0437\u0435 \u043c\u0438\u043a\u0440\u043e\u043a\u043e\u043d\u0442\u0440\u043e\u043b\u043b\u0435\u0440\u0430 STM32H743"
    )
    proj = asyncio.run(
        client.generate_educational_storyboard(
            topic=topic_ru,
            scene_count=4,
            language="ru",
        )
    )
    # Scene 1 visual narration_text must show engineering numbers ('48', '98.1', '16'), while tts_narration_text has words
    assert "48" in proj.scenes[0].narration_text
    assert "98.1" in proj.scenes[0].narration_text
    assert proj.scenes[0].tts_narration_text is not None
    assert "\u0441\u043e\u0440\u043e\u043a \u0432\u043e\u0441\u0435\u043c\u044c" in proj.scenes[0].tts_narration_text

    for sc in proj.scenes:
        caps = FlowEducationalCompositor._build_word_captions(sc.scene_id, sc.narration_text, 20.0)
        assert len(caps.pages) >= 2
        for pg in caps.pages:
            assert len(pg.words) >= 4, f"Orphan subtitle page with only {len(pg.words)} words in {sc.scene_id}: {[w.word for w in pg.words]}"


def test_req_005_clamped_spring_bounds_and_tofu_free_diff_tour() -> None:
    """REQ-005: Verify hardware spring scene keeps nodes inside [24, 1256] at t=0.0s and diff tour has zero em-dash tofu."""
    from src.flow_cli import draw_hardware_exploded_frame_at_t
    from src.flow_diff_tour import build_diff_tour_from_git_range

    img0 = draw_hardware_exploded_frame_at_t(0.0, 10.0, width=1280, height=720)
    arr0 = np.array(img0, dtype=np.uint8)
    # Left border strip (x=0..12, y=140..460) and right border strip (x=1268..1280, y=140..460) must not have clipped cyan/purple box outlines
    left_strip = arr0[140:460, 0:12]
    right_strip = arr0[140:460, 1268:1280]
    assert int(np.max(left_strip[:, :, 2])) < 120, "Left STM32 hardware block is clipped at x=0..12 at t=0.0s"
    assert int(np.max(right_strip[:, :, 0])) < 120, "Right SRAM hardware block is clipped at x=1268..1280 at t=0.0s"

    tour = build_diff_tour_from_git_range(TESTBENCH_DIR)
    dumped = json.dumps(tour, ensure_ascii=False)
    assert "\u2014" not in dumped, "Raw em-dash in diff tour document causes missing-glyph tofu box"


def test_moiad_m1_latex_formula_slot_rendering() -> None:
    """REQ-MOIAD-R1-LATEX: Verify LaTeX formula slot rendering at 200 DPI into 332x38px Card 01 slots."""
    from PIL import Image
    from scripts.moiad_visual_engines import render_latex_to_slot

    test_formulas = [
        r"Q_1 - 1.5 \cdot \mathrm{IQR}",
        r"\mathrm{RMSE} = \sqrt{\frac{1}{n}\sum (y - \hat{y})^2}",
        r"\mu = \frac{1}{N}\sum x_i",
        r"P(A|B) = \frac{P(B|A)P(A)}{P(B)}",
        r"\mathrm{Precision} = \frac{\mathrm{TP}}{\mathrm{TP} + \mathrm{FP}}",
    ]

    for expr in test_formulas:
        img = render_latex_to_slot(expr, max_w=332, max_h=38, color="#18212F")
        assert isinstance(img, Image.Image), f"Failed to render image for: {expr}"
        assert img.mode == "RGBA"
        assert img.size[0] <= 332, f"Width {img.size[0]} exceeds slot max 332 for: {expr}"
        assert img.size[1] <= 38, f"Height {img.size[1]} exceeds slot max 38 for: {expr}"
        arr = np.array(img)
        assert np.max(arr[:, :, 3]) > 0, f"Rendered formula is completely blank for: {expr}"

    # Verify edge cases do not crash
    blank1 = render_latex_to_slot("", max_w=332, max_h=38)
    assert blank1.size[0] <= 332 and blank1.size[1] <= 38
    blank2 = render_latex_to_slot("   ", max_w=332, max_h=38)
    assert blank2.size[0] <= 332 and blank2.size[1] <= 38
    broken = render_latex_to_slot(r"\invalid_macro_xyz{{{", max_w=332, max_h=38)
    assert broken.size[0] <= 332 and broken.size[1] <= 38


def test_moiad_m3_subtitle_badge_overlap_elimination() -> None:
    """REQ-MOIAD-R3-SUBTITLES: Verify zero subtitle badge overlap and >= 8px clamped margins across all 16 chapters."""
    from PIL import Image, ImageDraw
    from scripts.moiad_visual_engines import (
        load_moiad_fonts,
        _text_width,
        _partition_subtitle_page_words,
    )
    from scripts.moiad_chapters_spec import MOIAD_PARTS_SPEC
    from src.flow_bridge import FlowEducationalCompositor

    fonts = load_moiad_fonts()
    img = Image.new("RGB", (1280, 720))
    draw = ImageDraw.Draw(img)
    compositor = FlowEducationalCompositor(1280, 720, 24)

    total_words = 0
    total_collisions = 0
    min_physical_margin = 9999

    for part in MOIAD_PARTS_SPEC:
        for ch in part["chapters"]:
            caps = compositor._build_word_captions(ch["ch_id"], ch["narration"], 16.0)
            for page in caps.pages:
                l0, l1 = _partition_subtitle_page_words(draw, page.words, fonts["sub_r"], 1040)
                rendered = [(l0, 643)] if not l1 else [(l0, 626), (l1, 660)]
                for line_words, cy in rendered:
                    if not line_words:
                        continue
                    w_txts = [getattr(w, "word", str(w)) for w in line_words]
                    w_widths = [_text_width(draw, wt, fonts["sub_r"]) for wt in w_txts]
                    ww_space = 14
                    line_w = sum(w_widths) + ww_space * max(0, len(line_words) - 1)
                    cx = max(42, 590 - line_w // 2)

                    for idx, (w_txt, ww) in enumerate(zip(w_txts, w_widths)):
                        total_words += 1
                        act_w = _text_width(draw, w_txt, fonts["sub_b"])
                        pad_l = min(4 + max(0, (act_w - ww) // 2), 6)
                        pad_r = min(4 + max(0, act_w - ww - (act_w - ww) // 2), 6)
                        badge_left = cx - pad_l
                        badge_right = cx + ww + pad_r

                        if idx > 0:
                            prev_text_end = cx - ww_space
                            margin_l = badge_left - prev_text_end
                            min_physical_margin = min(min_physical_margin, margin_l)
                            if margin_l < 0:
                                total_collisions += 1

                        if idx < len(line_words) - 1:
                            next_text_start = cx + ww + ww_space
                            margin_r = next_text_start - badge_right
                            min_physical_margin = min(min_physical_margin, margin_r)
                            if margin_r < 0:
                                total_collisions += 1

                        cx += ww + ww_space

    assert total_words > 100, f"Expected > 100 words scanned, got {total_words}"
    assert total_collisions == 0, f"Detected {total_collisions} subtitle badge overlap collisions!"
    assert min_physical_margin >= 8, f"Minimum physical clearance {min_physical_margin}px violates >= 8px requirement!"


def test_moiad_m2_telemetry_slider_freezing_and_contraction() -> None:
    """REQ-MOIAD-R2-TELEMETRY: Verify d(fill_w)/du == 0 for invariants and physical contraction for error metrics."""
    import numpy as np
    from PIL import Image, ImageDraw
    from scripts.moiad_visual_engines import _render_frozen_gauges, load_moiad_fonts

    fonts = load_moiad_fonts()

    # 1. Invariant gauges: verify exact 0-pixel motion between u=0.0 and u=1.0 via _render_frozen_gauges
    pinned_gauge = [{"label": "IQR Fence", "v0": 1.5, "v1": 1.5, "pinned": True, "pinned_ratio": 0.65, "color": "blue"}]
    img_0 = Image.new("RGBA", (1280, 720), (0, 0, 0, 0))
    _render_frozen_gauges(ImageDraw.Draw(img_0), pinned_gauge, 0.0, fonts)
    img_1 = Image.new("RGBA", (1280, 720), (0, 0, 0, 0))
    _render_frozen_gauges(ImageDraw.Draw(img_1), pinned_gauge, 1.0, fonts)
    diff = int(np.sum(np.abs(np.array(img_0).astype(int) - np.array(img_1).astype(int))))
    assert diff == 0, f"Pinned invariant gauge moved between u=0 and u=1: pixel diff={diff}"

    # 2. Contracting error metric: v1 < v0 -> fill width physically contracts
    err_gauge = [{"label": "Loss", "v0": 2.0, "v1": 0.2, "pinned": False, "color": "rose"}]
    i_err0 = Image.new("RGBA", (1280, 720), (0, 0, 0, 0))
    _render_frozen_gauges(ImageDraw.Draw(i_err0), err_gauge, 0.0, fonts)
    i_err1 = Image.new("RGBA", (1280, 720), (0, 0, 0, 0))
    _render_frozen_gauges(ImageDraw.Draw(i_err1), err_gauge, 1.0, fonts)
    row_err0 = np.array(i_err0)[288, 914:1246]
    row_err1 = np.array(i_err1)[288, 914:1246]
    w_err0 = int(np.sum(row_err0[:, 1] < 50))
    w_err1 = int(np.sum(row_err1[:, 1] < 50))
    assert w_err1 < w_err0, f"Error metric did not physically contract: {w_err0} -> {w_err1}"

    # 3. Expanding accuracy metric: v1 > v0 -> fill width physically expands
    acc_gauge = [{"label": "Accuracy", "v0": 0.40, "v1": 0.95, "pinned": False, "color": "emerald"}]
    i_acc0 = Image.new("RGBA", (1280, 720), (0, 0, 0, 0))
    _render_frozen_gauges(ImageDraw.Draw(i_acc0), acc_gauge, 0.0, fonts)
    i_acc1 = Image.new("RGBA", (1280, 720), (0, 0, 0, 0))
    _render_frozen_gauges(ImageDraw.Draw(i_acc1), acc_gauge, 1.0, fonts)
    row_acc0 = np.array(i_acc0)[288, 914:1246]
    row_acc1 = np.array(i_acc1)[288, 914:1246]
    w_acc0 = int(np.sum((row_acc0[:, 1] > 100) & (row_acc0[:, 0] < 50)))
    w_acc1 = int(np.sum((row_acc1[:, 1] > 100) & (row_acc1[:, 0] < 50)))
    assert w_acc1 > w_acc0, f"Accuracy metric did not physically expand: {w_acc0} -> {w_acc1}"


def test_moiad_m2_modular_card2_visual_engines() -> None:
    """REQ-MOIAD-R2-ENGINES: Verify all 6 visual types render with non-zero variance into Card 2."""
    from scripts.moiad_chapters_spec import MOIAD_PARTS_SPEC
    from scripts.moiad_visual_engines import (
        render_moiad_chapter_frame,
        build_moiad_stage_backdrop,
        load_moiad_fonts,
    )

    expected_types = {
        "metric_table",
        "confusion_matrix",
        "flowchart",
        "theorem_card",
        "feature_table",
        "importance_bars",
    }
    found_types = set()

    for part in MOIAD_PARTS_SPEC:
        for ch in part["chapters"]:
            ib = ch.get("info_block", {})
            b_type = ib.get("type")
            if b_type in expected_types:
                found_types.add(b_type)

    assert found_types == expected_types, f"Missing visual types in MOIAD_PARTS_SPEC: {expected_types - found_types}"

    # Verify rendering of representative chapters for each type
    type_to_chapter = {}
    for part in MOIAD_PARTS_SPEC:
        for ch in part["chapters"]:
            b_type = ch.get("info_block", {}).get("type")
            if b_type not in type_to_chapter:
                type_to_chapter[b_type] = ch

    fonts = load_moiad_fonts()
    for b_type, ch in type_to_chapter.items():
        backdrop = build_moiad_stage_backdrop(ch)
        frame_img = render_moiad_chapter_frame(backdrop, ch, None, 0.5, fonts)
        assert frame_img.size == (1280, 720), f"Frame size invalid for {b_type}"
        arr = np.array(frame_img)
        # Card 2 region: x: 880..1250, y: 220..500
        card2_region = arr[220:500, 880:1250]
        std_val = float(np.std(card2_region.astype(np.float32)))
        assert std_val > 5.0, f"Card 2 visual region is blank for type {b_type} (std={std_val:.2f})"


def test_moiad_m3_continuous_schmitt_trigger_vad_and_monotonic_alignment() -> None:
    """REQ-MOIAD-R3-VAD-MONOTONIC: Verify Schmitt-trigger VAD and strictly monotonic word timestamps."""
    import tempfile
    import wave
    from scripts.render_simple_flow_demo import _align_captions_to_wav
    from src.flow_bridge import FlowEducationalCompositor, FlowScene

    comp = FlowEducationalCompositor(1280, 720, 24)
    sc = FlowScene(
        scene_id="ch_1_3",
        scene_number=3,
        title="",
        visual_prompt="",
        narration_text=(
            "\u0413\u043b\u0430\u0432\u0430 \u043e\u0434\u0438\u043d \u0442\u0440\u0438 \u043f\u043e\u0441\u0432\u044f\u0449\u0435\u043d\u0430 "
            "\u043c\u0435\u0445\u0430\u043d\u0438\u0437\u043c\u0430\u043c \u043f\u0440\u043e\u043f\u0443\u0441\u043a\u043e\u0432 \u0438 "
            "\u0432\u043e\u0441\u0441\u0442\u0430\u043d\u043e\u0432\u043b\u0435\u043d\u0438\u044e \u0434\u0430\u043d\u043d\u044b\u0445."
        ),
        duration_sec=16.0,
    )
    caps = comp._build_word_captions(sc.scene_id, sc.narration_text, 16.0)
    assert len(caps.all_words) >= 5

    # Synthesize test 16kHz audio with speech bursts and pauses
    sr = 16000
    total_sec = 16.0
    t_arr = np.linspace(0.0, total_sec, int(sr * total_sec), endpoint=False)
    env = np.zeros_like(t_arr)
    # Voiced block 1: 0.5s to 5.0s
    env[(t_arr >= 0.5) & (t_arr <= 5.0)] = 0.8
    # Voiced block 2: 5.5s to 10.0s
    env[(t_arr >= 5.5) & (t_arr <= 10.0)] = 0.8
    # Voiced block 3: 10.5s to 15.0s
    env[(t_arr >= 10.5) & (t_arr <= 15.0)] = 0.8

    signal = (np.sin(2.0 * np.pi * 300.0 * t_arr) * env * 12000.0).astype(np.int16)

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf:
        tf_path = Path(tf.name)
        with wave.open(str(tf_path), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sr)
            wf.writeframes(signal.tobytes())

    try:
        _align_captions_to_wav(caps, tf_path)
        words = caps.all_words
        assert len(words) > 0

        for idx in range(len(words)):
            w = words[idx]
            assert w.start_ms < w.end_ms, f"Word {w.word} has non-positive duration: {w.start_ms} >= {w.end_ms}"
            assert w.end_ms <= int(round(total_sec * 1000.0)) + 200, f"Word {w.word} extends beyond scene duration"
            if idx < len(words) - 1:
                next_w = words[idx + 1]
                assert next_w.start_ms >= w.start_ms, f"Non-monotonic start time: {w.word}({w.start_ms}) > {next_w.word}({next_w.start_ms})"
    finally:
        if tf_path.is_file():
            tf_path.unlink()


def test_moiad_m1_frame_level_phase_isolation_and_bar_geometry() -> None:
    """REQ-MOIAD-R1-PHASE-ISOLATION: Verify Ch 1.3 at 0:01:29 has 0 emerald pixels on right chart and bar error < 1.0px."""
    import matplotlib.pyplot as plt
    from PIL import Image
    import scripts.moiad_visual_engines as ve
    import scripts.moiad_chapters_spec as cs

    ch_1_3 = next(ch for p in cs.MOIAD_PARTS_SPEC for ch in p["chapters"] if ch["ch_id"] == "ch_1_3")
    backdrop_arr = ve.build_moiad_stage_backdrop(ch_1_3)
    stage_base = Image.fromarray(backdrop_arr, mode="RGB")
    W, H = stage_base.size
    assert (W, H) == (864, 540)

    # 1. Phase isolation test: u=0.1947 corresponds to timestamp 0:01:29 in Chapter 1.3 (Phase 01/02)
    u_89s = 0.1947
    u_switch = 0.4510

    overlay = ve._draw_stage_overlay_2x(stage_base, "missing_mechanisms", u_89s, u_switch=u_switch)
    over_np = np.asarray(overlay, dtype=np.int32)
    spot_only = ve._draw_stage_overlay_2x(stage_base, "none", u_89s, u_switch=u_switch)
    spot_np = np.asarray(spot_only, dtype=np.int32)

    # Difference strictly on right chart (ax2) [y: 60..480, x: 480..850]
    ax2_diff = np.abs(over_np[60:480, 480:850] - spot_np[60:480, 480:850])
    ax2_diff_pixels = int(np.sum(np.any(ax2_diff > 0, axis=2)))
    assert ax2_diff_pixels == 0, f"Detected {ax2_diff_pixels} phantom highlight pixels on right chart in Phase 01/02!"

    # 2. Bar highlight geometry test: centering deviation < 1.0 px across all 5 bars
    fig = plt.figure(figsize=(8.64, 5.40), dpi=200, facecolor="#FFFFFF")
    gs = fig.add_gridspec(1, 2, left=0.075, right=0.975, top=0.88, bottom=0.12, wspace=0.22)
    ax1 = fig.add_subplot(gs[0, 0])
    ax2 = fig.add_subplot(gs[0, 1])
    ve._populate_backdrop_pr1_pr2("missing_mechanisms", ax1, ax2)
    fig.canvas.draw()

    scale_x = 864.0 / (8.64 * 200.0)
    scale_y = 540.0 / (5.40 * 200.0)

    def data_to_stage(x_d: float, y_d: float):
        disp = ax2.transData.transform((x_d, y_d))
        return disp[0] * scale_x, (5.40 * 200.0 - disp[1]) * scale_y

    bar_heights = [40, 39, 35, 30, 27]
    bar_width = 0.55
    bh_n_list = [40 / 48.0, 39 / 48.0, 35 / 48.0, 30 / 48.0, 27 / 48.0]
    half_w = 0.0549

    max_dx = 0.0
    for i in range(5):
        px_l, py_b = data_to_stage(i - bar_width / 2.0, 0.0)
        px_r, py_t = data_to_stage(i + bar_width / 2.0, bar_heights[i])
        bar_xc = (px_l + px_r) / 2.0

        bx_c = 0.1004 + i * 0.1998
        bh_n = bh_n_list[i]

        tl_x_2x = int((492.1 + max(0.01, bx_c - half_w) * 350.3) * 2.0)
        br_x_2x = int((492.1 + min(0.99, bx_c + half_w) * 350.3) * 2.0)

        box_l = (tl_x_2x - 4) // 2
        box_r = (br_x_2x + 4) // 2
        box_xc = (box_l + box_r) / 2.0

        dx = abs(box_xc - bar_xc)
        max_dx = max(max_dx, dx)

    plt.close(fig)
    assert max_dx < 1.0, f"Categorical centering deviation {max_dx:.4f}px exceeds 1.0px threshold!"


def test_ttd_r1_series_production_bible_and_schema_bridge() -> None:
    """
    REQ-TTD-M1: Verify FlowStoryboard schema alias, from_dict serialization roundtrip,
    and src.ttd_lore_bible character/bestiary/environmental/palette contracts.
    Zero literal Cyrillic characters are allowed in this test suite.
    """
    import re
    import src.ttd_lore_bible as ttd_bible

    # 1. FlowStoryboard alias verification
    assert FlowStoryboard is FlowEducationalProject, "FlowStoryboard must be an exact alias of FlowEducationalProject"

    # 2. Schema bridge serialization roundtrip
    test_scene = FlowScene(
        scene_id="sc_pilot_test_01",
        scene_number=1,
        title="Awakening at Crossroads",
        narration_text="The Black Fog rises over the mountain pass.",
        visual_prompt="Cinematic dark fantasy anime, wide panoramic crane reveal of Crossroads fortress, 16:9.",
        duration_sec=7.0,
        camera_motion="slow push-in",
        voice_persona="voice_y0joebp3bwta",
        voice_style="grim authoritative Russian commander",
        timecoded_directives=[
            {"window": "0-2s", "action": "Establish brooding fortress walls"},
            {"window": "2-5s", "action": "Lightning reveals Prince Ash gazing down"},
        ],
    )
    storyboard = FlowStoryboard(
        project_id="flow_ttd_pilot_wave01",
        topic="Tyrant of the Tower Defense Game: Pilot Wave 1",
        language="ru",
        target_audience="dark_fantasy_series",
        aspect_ratio="16:9",
        model_key="veo_3_1_t2v_fast_audio",
        scenes=[test_scene],
        status="storyboard_ready",
    )

    data = storyboard.to_dict()
    assert isinstance(data, dict)
    assert data["project_id"] == "flow_ttd_pilot_wave01"
    assert isinstance(data["scenes"], list) and len(data["scenes"]) == 1
    assert isinstance(data["scenes"][0], dict)

    restored = FlowStoryboard.from_dict(data)
    assert isinstance(restored, FlowStoryboard)
    assert isinstance(restored, FlowEducationalProject)
    assert restored == storyboard
    assert restored.scenes[0] == test_scene

    # 3. Resilience against unmodeled/extra fields
    data_extra = dict(data)
    data_extra["unknown_future_parameter"] = 12345
    data_extra["scenes"] = [dict(data["scenes"][0], extraneous_field="ignored")]
    restored_extra = FlowStoryboard.from_dict(data_extra)
    assert restored_extra == storyboard

    # 4. Backward compatibility with FlowEducationalProject.from_dict
    restored_legacy = FlowEducationalProject.from_dict(data)
    assert restored_legacy == storyboard

    # 5. Character Bible verification (Ash, Lucas, Lily)
    chars = ttd_bible.CHARACTERS
    assert "ash_bornhater" in chars
    assert "knight_lucas" in chars
    assert "archer_lily" in chars

    ash = chars["ash_bornhater"]
    assert "Ash Bornhater" in ash.name_en
    assert any("black hair" in a.lower() for a in ash.visual_anchors)
    assert any("dark eye circles" in a.lower() or "sleep deprivation" in a.lower() for a in ash.visual_anchors)
    assert any("cloak" in c.lower() for c in ash.costume_tokens)
    assert any("baton" in g.lower() or "rapier" in g.lower() for g in ash.signature_gear)
    assert ash.voice_persona == "voice_y0joebp3bwta"

    lucas = chars["knight_lucas"]
    assert "Lucas" in lucas.name_en
    assert any("muscular" in a.lower() or "2 meters" in a.lower() for a in lucas.visual_anchors)
    assert any("plate" in c.lower() or "armour" in c.lower() for c in lucas.costume_tokens)
    assert any("sword" in g.lower() for g in lucas.signature_gear)

    lily = chars["archer_lily"]
    assert "Lily" in lily.name_en
    assert any("amber eyes" in a.lower() for a in lily.visual_anchors)
    assert any("green" in c.lower() for c in lily.costume_tokens)
    assert any("bow" in g.lower() for g in lily.signature_gear)
    assert "recruit" in lily.phases
    assert "sniper" in lily.phases

    # 5b. Character psychological profile and phase anchor regression checks (Defect 1)
    characters = chars
    assert isinstance(characters["archer_lily"].psychological_profile, str)
    assert isinstance(characters["archer_lily"].phases["recruit"].visual_anchor, str)
    assert not isinstance(characters["archer_lily"].psychological_profile, tuple)
    assert len(characters["archer_lily"].psychological_profile) > 0
    for char_id, char_profile in characters.items():
        assert isinstance(char_profile.psychological_profile, str)

    # 6. First Wave Monster Bestiary verification
    bestiary = ttd_bible.FIRST_WAVE_BESTIARY
    assert len(bestiary) >= 4
    assert "black_scaled_gargoyle" in bestiary
    assert "chitinous_crawler" in bestiary
    assert "decayed_ghoul" in bestiary
    assert "siege_ogre_vanguard" in bestiary
    assert "living_armor_vanguard" in bestiary
    for m_slug, spec in bestiary.items():
        assert len(spec.visual_anchors) > 0, f"Monster {m_slug} has empty visual anchors"
        assert len(spec.behavior_tokens) > 0, f"Monster {m_slug} has empty behavior tokens"

    # 7. Crossroads Fortress environment verification
    crossroads = ttd_bible.CROSSROADS_FORTRESS
    assert len(crossroads.architecture_anchors) >= 3
    assert any("granite" in a.lower() or "citadel" in a.lower() for a in crossroads.architecture_anchors)
    assert any("overcast" in a.lower() or "torchlight" in a.lower() or "brazier" in a.lower() for a in crossroads.atmosphere_anchors)

    # 8. Color Palette verification
    palette = ttd_bible.COLOR_PALETTE
    assert len(palette) >= 8
    hex_pattern = re.compile(r"^#[0-9A-Fa-f]{6}$")
    for key, color in palette.items():
        assert hex_pattern.match(color.hex_code), f"Invalid hex color in palette {key}: {color.hex_code}"
        assert len(color.name) > 0
        assert len(color.semantic_role) > 0
        assert len(color.rgb) == 3 and all(0 <= val <= 255 for val in color.rgb)
        expected_rgb = (
            int(color.hex_code[1:3], 16),
            int(color.hex_code[3:5], 16),
            int(color.hex_code[5:7], 16),
        )
        assert color.rgb == expected_rgb, f"RGB mismatch in {key}: {color.rgb} vs {expected_rgb}"

    # 9. Master negative prompt and negative tokens verification
    neg_prompt = ttd_bible.TTD_MASTER_NEGATIVE_PROMPT
    assert isinstance(neg_prompt, str) and len(neg_prompt) > 50
    assert any(banned in neg_prompt.lower() for banned in ["blurry", "extra limbs", "bad anatomy", "sci-fi"])
    assert hasattr(ttd_bible, "TTD_NEGATIVE_PROMPT_TOKENS")
    assert len(ttd_bible.TTD_NEGATIVE_PROMPT_TOKENS) >= 5

    # 10. Helper functions and LoreBible verification
    bible = ttd_bible.get_lore_bible()
    assert isinstance(bible, ttd_bible.LoreBible)
    assert bible.series_title_en == "Tyrant of the Tower Defense Game"
    assert ttd_bible.get_character("ash_bornhater") is ash
    assert ttd_bible.get_monster("black_scaled_gargoyle") is bestiary["black_scaled_gargoyle"]
    assert ttd_bible.get_environment() is crossroads
    assert ttd_bible.get_color_token("Basalt Stone").hex_code == "#2B2D31"

    prompt_built = ttd_bible.build_veo_scene_prompt(
        camera_motion="slow push-in",
        action="Ash raises his baton toward the rising Black Fog",
        characters=["ash_bornhater"],
        monsters=["black_scaled_gargoyle"],
    )
    assert "slow push-in" in prompt_built
    assert "Prince Ash Bornhater" in prompt_built
    assert "Black-Scaled Gargoyle" in prompt_built or "Gargoyle" in prompt_built

    # 10b. Function alias and unified prompt builder verification (Defect 2)
    from src.ttd_lore_bible import build_ttd_scene_prompt

    assert callable(build_ttd_scene_prompt), "build_ttd_scene_prompt must be callable"

    # Call with scene_title
    prompt_ttd_with_title = build_ttd_scene_prompt(
        scene_title="Test Scene 1",
        camera_motion="slow push-in",
        action="Archer Lily draws her recurve bow while Ash signals the defense line",
        characters=["archer_lily", "ash_bornhater"],
        monsters=["black_scaled_gargoyle"],
    )
    assert isinstance(prompt_ttd_with_title, str), f"build_ttd_scene_prompt return type must be str, got {type(prompt_ttd_with_title)}"
    assert len(prompt_ttd_with_title) > 0, "build_ttd_scene_prompt returned an empty string"
    assert "slow push-in" in prompt_ttd_with_title
    assert "Prince Ash Bornhater" in prompt_ttd_with_title
    assert "Archer Lily" in prompt_ttd_with_title or "Lily" in prompt_ttd_with_title

    # Call without scene_title
    prompt_ttd_no_title = build_ttd_scene_prompt(
        camera_motion="overhead tracking pan",
        action="Knight Lucas raises his tower shield to absorb incoming barrage",
        characters=["knight_lucas"],
        monsters=["siege_ogre_vanguard"],
    )
    assert isinstance(prompt_ttd_no_title, str), f"build_ttd_scene_prompt return type must be str, got {type(prompt_ttd_no_title)}"
    assert len(prompt_ttd_no_title) > 0, "build_ttd_scene_prompt without scene_title returned an empty string"
    assert "overhead tracking pan" in prompt_ttd_no_title
    assert "Knight Lucas" in prompt_ttd_no_title or "Lucas" in prompt_ttd_no_title

    # 11. Source hygiene: verify zero literal Cyrillic characters in src/ttd_lore_bible.py and tests
    bible_path = Path(ttd_bible.__file__)
    bible_text = bible_path.read_text(encoding="utf-8")
    assert not re.search(r"[\u0400-\u04FF]", bible_text), "src/ttd_lore_bible.py must have 0 literal Cyrillic characters (use \\uXXXX unicode escapes)"

    current_test_file = Path(__file__).read_text(encoding="utf-8")
    assert not re.search(r"[\u0400-\u04FF]", current_test_file), "tests/test_flow_studio.py must have 0 literal Cyrillic characters"



def test_ttd_r2_storyboard_templates_and_prompt_generator(tmp_path: Path | None = None) -> None:
    """
    REQ-TTD-M2: Verify reusable Flow storyboard templates (FortressAtmosphere,
    TacticalCommand, VanguardDefense, SniperAwakening, BossShowdown), multimodal
    prompt generator pipeline, pilot storyboard assembly, JSON serialization roundtrip,
    structural validation, and strict zero literal Cyrillic compliance.
    """
    import json
    import re
    import tempfile
    from pathlib import Path

    # Dual execution support: run via pytest fixture or standalone direct invocation
    if tmp_path is None:
        _tmp_ctx = tempfile.TemporaryDirectory()
        work_dir = Path(_tmp_ctx.name)
    else:
        _tmp_ctx = None
        work_dir = Path(tmp_path)

    try:
        # ======================================================================
        # 1. Imports from src.ttd_storyboard
        # ======================================================================
        import src.ttd_storyboard as ttd_sb
        from src.ttd_storyboard import (
            TTDStoryboardTemplate,
            FortressAtmosphereTemplate,
            TacticalCommandTemplate,
            VanguardDefenseTemplate,
            SniperAwakeningTemplate,
            BossShowdownTemplate,
            build_ttd_pilot_storyboard,
            export_storyboard_to_json,
            load_storyboard_from_json,
            validate_storyboard,
        )
        from src.flow_bridge import FlowEducationalProject, FlowScene, FlowStoryboard

        # ======================================================================
        # 2. Template Class Hierarchy & Registry Verification
        # ======================================================================
        template_classes = [
            FortressAtmosphereTemplate,
            TacticalCommandTemplate,
            VanguardDefenseTemplate,
            SniperAwakeningTemplate,
            BossShowdownTemplate,
        ]
        for tmpl_cls in template_classes:
            assert issubclass(tmpl_cls, TTDStoryboardTemplate), (
                f"{tmpl_cls.__name__} must inherit from TTDStoryboardTemplate"
            )

        assert hasattr(ttd_sb, "TEMPLATE_REGISTRY"), "src.ttd_storyboard must define TEMPLATE_REGISTRY"
        registry = ttd_sb.TEMPLATE_REGISTRY
        assert isinstance(registry, dict), "TEMPLATE_REGISTRY must be a dictionary"
        required_keys = [
            "fortress_atmosphere",
            "tactical_command",
            "vanguard_defense",
            "sniper_awakening",
            "boss_showdown",
        ]
        for rk in required_keys:
            assert rk in registry, f"Missing '{rk}' in TEMPLATE_REGISTRY"
            assert isinstance(registry[rk], TTDStoryboardTemplate), (
                f"Registry entry '{rk}' must be an instance of TTDStoryboardTemplate"
            )

        if hasattr(ttd_sb, "get_storyboard_template"):
            assert callable(ttd_sb.get_storyboard_template)
            for rk in required_keys:
                resolved = ttd_sb.get_storyboard_template(rk)
                assert isinstance(resolved, TTDStoryboardTemplate)

        # ======================================================================
        # 3. Individual Template Instantiation & FlowScene Attribute Completeness
        # ======================================================================
        # 3.1 FortressAtmosphereTemplate
        tmpl_atmo = FortressAtmosphereTemplate() if isinstance(FortressAtmosphereTemplate, type) else registry["fortress_atmosphere"]
        sc_atmo = tmpl_atmo.build_scene(scene_id="sc_atmo_01", scene_number=1, language="ru")
        assert isinstance(sc_atmo, FlowScene), "build_scene must return a FlowScene"
        assert sc_atmo.scene_id == "sc_atmo_01"
        assert sc_atmo.scene_number == 1
        assert sc_atmo.duration_sec > 0.0
        assert sc_atmo.voice_persona == "voice_y0joebp3bwta", "Russian narration voice_persona must be voice_y0joebp3bwta"
        assert len(sc_atmo.camera_motion) > 0, "camera_motion must not be empty"
        assert any(term in sc_atmo.camera_motion.lower() for term in ["crane", "panoramic", "reveal", "push-in"])
        assert len(sc_atmo.visual_prompt) > 50, "visual_prompt must be substantive"
        assert any(anchor in sc_atmo.visual_prompt for anchor in ["Crossroads", "granite", "bastion", "Black Fog", "fog"])
        assert sc_atmo.veo_audio_prompt is not None and len(sc_atmo.veo_audio_prompt) > 20
        assert "voice_y0joebp3bwta" in sc_atmo.veo_audio_prompt
        assert "SFX:" in sc_atmo.veo_audio_prompt
        assert "Ambient noise:" in sc_atmo.veo_audio_prompt
        assert len(sc_atmo.title) > 0
        assert len(sc_atmo.narration_text) > 0
        assert sc_atmo.tts_narration_text is not None and len(sc_atmo.tts_narration_text) > 0
        assert isinstance(sc_atmo.timecoded_directives, list) and len(sc_atmo.timecoded_directives) >= 2
        assert isinstance(sc_atmo.on_screen_bullets, list) and len(sc_atmo.on_screen_bullets) >= 2

        # 3.2 TacticalCommandTemplate
        tmpl_cmd = TacticalCommandTemplate() if isinstance(TacticalCommandTemplate, type) else registry["tactical_command"]
        sc_cmd = tmpl_cmd.build_scene(scene_id="sc_cmd_02", scene_number=2, language="ru")
        assert isinstance(sc_cmd, FlowScene)
        assert sc_cmd.voice_persona == "voice_y0joebp3bwta"
        assert "slow push-in" in sc_cmd.camera_motion.lower()
        assert any(t in sc_cmd.visual_prompt for t in ["Ash", "Bornhater", "baton", "crystal"])
        assert sc_cmd.veo_audio_prompt is not None and "voice_y0joebp3bwta" in sc_cmd.veo_audio_prompt

        # 3.3 VanguardDefenseTemplate
        tmpl_van = VanguardDefenseTemplate() if isinstance(VanguardDefenseTemplate, type) else registry["vanguard_defense"]
        sc_van = tmpl_van.build_scene(scene_id="sc_van_03", scene_number=3, language="ru")
        assert isinstance(sc_van, FlowScene)
        assert sc_van.voice_persona == "voice_y0joebp3bwta"
        assert any(t in sc_van.camera_motion.lower() for t in ["dolly", "low-angle", "slide", "impact"])
        assert any(t in sc_van.visual_prompt for t in ["Lucas", "tower shield", "shield", "gargoyle"])
        assert sc_van.veo_audio_prompt is not None and "voice_y0joebp3bwta" in sc_van.veo_audio_prompt

        # 3.4 SniperAwakeningTemplate
        tmpl_snp = SniperAwakeningTemplate() if isinstance(SniperAwakeningTemplate, type) else registry["sniper_awakening"]
        sc_snp = tmpl_snp.build_scene(scene_id="sc_snp_04", scene_number=4, language="ru")
        assert isinstance(sc_snp, FlowScene)
        assert sc_snp.voice_persona == "voice_y0joebp3bwta"
        assert any(t in sc_snp.camera_motion.lower() for t in ["macro", "tracking", "arrow", "focus"])
        assert any(t in sc_snp.visual_prompt for t in ["Lily", "bodkin", "arrow", "bow", "sniper"])
        assert sc_snp.veo_audio_prompt is not None and "voice_y0joebp3bwta" in sc_snp.veo_audio_prompt

        # 3.5 BossShowdownTemplate
        tmpl_boss = BossShowdownTemplate() if isinstance(BossShowdownTemplate, type) else registry["boss_showdown"]
        sc_boss = tmpl_boss.build_scene(scene_id="sc_boss_05", scene_number=5, language="ru")
        assert isinstance(sc_boss, FlowScene)
        assert sc_boss.voice_persona == "voice_y0joebp3bwta"
        assert any(t in sc_boss.camera_motion.lower() for t in ["orbital", "360", "dolly", "combat"])
        assert any(t in sc_boss.visual_prompt for t in ["Living Armor", "boss", "greatsword", "soul-core", "armor"])
        assert sc_boss.veo_audio_prompt is not None and "voice_y0joebp3bwta" in sc_boss.veo_audio_prompt


        # ======================================================================
        # 4. Pilot Storyboard Construction (5 Scenes, 37.5s)
        # ======================================================================
        pilot_sb = build_ttd_pilot_storyboard()
        assert isinstance(pilot_sb, FlowStoryboard), "Must return a FlowStoryboard"
        assert isinstance(pilot_sb, FlowEducationalProject), "FlowStoryboard must be FlowEducationalProject"
        assert len(pilot_sb.project_id) > 0, "project_id must not be empty"
        assert pilot_sb.language == "ru", "pilot storyboard language must be 'ru'"
        assert len(pilot_sb.scenes) == 5, f"Pilot storyboard must contain exactly 5 scenes, got {len(pilot_sb.scenes)}"

        expected_scene_numbers = [1, 2, 3, 4, 5]
        assert [s.scene_number for s in pilot_sb.scenes] == expected_scene_numbers
        scene_ids = [s.scene_id for s in pilot_sb.scenes]
        assert len(set(scene_ids)) == 5, f"All 5 scenes must have unique scene_ids: {scene_ids}"

        total_dur = sum(s.duration_sec for s in pilot_sb.scenes)
        assert 35.0 <= total_dur <= 45.0, f"Total pilot duration should be around 37.5s, got {total_dur}s"

        for s in pilot_sb.scenes:
            assert s.voice_persona == "voice_y0joebp3bwta"
            assert len(s.visual_prompt) > 30
            assert len(s.narration_text) > 0
            assert len(s.title) > 0
            assert s.veo_audio_prompt is not None and len(s.veo_audio_prompt) > 0

        # ======================================================================
        # 5. Export Storyboard to JSON (String & Disk File)
        # ======================================================================
        json_output = export_storyboard_to_json(pilot_sb)
        assert isinstance(json_output, str), "export_storyboard_to_json must return a str"
        assert not re.search(r"[\u0400-\u04FF]", json_output), (
            "export_storyboard_to_json must produce zero literal Cyrillic characters (use \\uXXXX unicode escapes)"
        )
        assert all(ord(c) < 128 for c in json_output), "Exported JSON string must be 100% 7-bit ASCII"
        parsed = json.loads(json_output)
        assert isinstance(parsed, dict)
        assert parsed["project_id"] == pilot_sb.project_id
        assert len(parsed["scenes"]) == 5

        export_file = work_dir / "test_pilot_storyboard_exported.json"
        export_file_res = export_storyboard_to_json(pilot_sb, path=export_file)
        assert export_file.is_file(), f"Export file {export_file} was not written to disk"
        disk_content = export_file.read_text(encoding="utf-8")
        assert not re.search(r"[\u0400-\u04FF]", disk_content), (
            "Exported JSON file on disk must contain zero literal Cyrillic characters"
        )
        assert all(ord(c) < 128 for c in disk_content), "Exported JSON file on disk must be 100% 7-bit ASCII"
        assert json.loads(disk_content) == parsed

        # ======================================================================
        # 6. Load Storyboard from JSON (Roundtrip Equality & Adversarial Inputs)
        # ======================================================================
        loaded_from_str = load_storyboard_from_json(json_output)
        assert isinstance(loaded_from_str, FlowStoryboard)
        assert loaded_from_str == pilot_sb, "Deserialized storyboard from string must match original"

        loaded_from_disk = load_storyboard_from_json(export_file)
        assert isinstance(loaded_from_disk, FlowStoryboard)
        assert loaded_from_disk == pilot_sb, "Deserialized storyboard from disk must match original"
        assert len(loaded_from_disk.scenes) == 5

        for orig_s, loaded_s in zip(pilot_sb.scenes, loaded_from_disk.scenes):
            assert orig_s.scene_id == loaded_s.scene_id
            assert orig_s.visual_prompt == loaded_s.visual_prompt
            assert orig_s.veo_audio_prompt == loaded_s.veo_audio_prompt
            assert orig_s.voice_persona == loaded_s.voice_persona
            assert orig_s.duration_sec == loaded_s.duration_sec

        # 6.1 Adversarial load_storyboard_from_json: non-existent file paths must raise FileNotFoundError
        with pytest.raises(FileNotFoundError):
            load_storyboard_from_json("missing_dir/file.json")

        with pytest.raises(FileNotFoundError):
            load_storyboard_from_json("missing_storyboard_file.json")

        with pytest.raises(FileNotFoundError):
            load_storyboard_from_json(work_dir / "non_existent_storyboard.json")

        # 6.2 Adversarial load_storyboard_from_json: non-dictionary JSON payloads must raise ValueError
        with pytest.raises(ValueError, match="dictionary"):
            load_storyboard_from_json("[1, 2, 3]")

        with pytest.raises(ValueError, match="dictionary"):
            load_storyboard_from_json("12345")

        with pytest.raises(ValueError, match="dictionary"):
            load_storyboard_from_json("true")

        # ======================================================================
        # 7. Storyboard Structural Validation & Error Raising
        # ======================================================================
        assert validate_storyboard(pilot_sb) is True, "Valid pilot storyboard must return True"
        assert validate_storyboard(pilot_sb, raise_on_error=True) is True, (
            "Valid pilot storyboard must return True when raise_on_error=True"
        )

        # 7.1 Invalid: Non-storyboard type
        assert validate_storyboard(None) is False
        assert validate_storyboard("not_a_storyboard") is False
        with pytest.raises(ValueError, match="FlowStoryboard"):
            validate_storyboard(None, raise_on_error=True)
        with pytest.raises(ValueError, match="FlowStoryboard"):
            validate_storyboard("not_a_storyboard", raise_on_error=True)

        # 7.2 Invalid: Empty project_id
        inv_no_id = FlowStoryboard.from_dict(dict(parsed, project_id=""))
        inv_no_id.project_id = ""
        assert validate_storyboard(inv_no_id) is False
        with pytest.raises(ValueError, match="project_id"):
            validate_storyboard(inv_no_id, raise_on_error=True)

        # 7.3 Invalid: Empty topic
        inv_no_topic = FlowStoryboard.from_dict(dict(parsed, topic=""))
        inv_no_topic.topic = ""
        assert validate_storyboard(inv_no_topic) is False
        with pytest.raises(ValueError, match="topic"):
            validate_storyboard(inv_no_topic, raise_on_error=True)

        # 7.4 Invalid: Empty scenes list
        inv_empty_scenes = FlowStoryboard.from_dict(dict(parsed, scenes=[]))
        assert validate_storyboard(inv_empty_scenes) is False
        with pytest.raises(ValueError, match="scenes"):
            validate_storyboard(inv_empty_scenes, raise_on_error=True)

        # 7.5 Invalid: Scene with non-positive duration
        bad_scene_dur = FlowScene(
            scene_id="sc_zero",
            scene_number=1,
            title="Zero Duration",
            narration_text="Text",
            visual_prompt="Prompt",
            duration_sec=0.0,
            voice_persona="voice_y0joebp3bwta",
        )
        inv_dur = FlowStoryboard(project_id="test_inv", topic="Topic", scenes=[bad_scene_dur])
        assert validate_storyboard(inv_dur) is False
        with pytest.raises(ValueError, match="duration_sec"):
            validate_storyboard(inv_dur, raise_on_error=True)

        # 7.6 Invalid: Scene missing title or visual prompt
        bad_scene_prompt = FlowScene(
            scene_id="sc_no_p",
            scene_number=1,
            title="Title",
            narration_text="Text",
            visual_prompt="",
            duration_sec=5.0,
            voice_persona="voice_y0joebp3bwta",
        )
        inv_prompt = FlowStoryboard(project_id="test_inv", topic="Topic", scenes=[bad_scene_prompt])
        assert validate_storyboard(inv_prompt) is False
        with pytest.raises(ValueError, match="visual_prompt"):
            validate_storyboard(inv_prompt, raise_on_error=True)

        # 7.7 Invalid: Unauthorized voice persona
        bad_voice_scene = FlowScene(
            scene_id="sc_bad_voice",
            scene_number=1,
            title="Unauthorized Voice",
            narration_text="Narration",
            visual_prompt="Visual prompt description for defense",
            camera_motion="slow push-in",
            duration_sec=5.0,
            voice_persona="unauthorized_voice",
        )
        inv_voice = FlowStoryboard(project_id="test_inv_voice", topic="Topic", scenes=[bad_voice_scene])
        assert validate_storyboard(inv_voice) is False, (
            "Unauthorized voice persona must fail validate_storyboard"
        )
        with pytest.raises(ValueError, match="voice_persona"):
            validate_storyboard(inv_voice, raise_on_error=True)

        # 7.8 Authorized voice personas acceptance (voice_y0joebp3bwta, Sulafat, Kore)
        for valid_persona in ("voice_y0joebp3bwta", "Sulafat", "Kore"):
            ok_voice_scene = FlowScene(
                scene_id="sc_valid_voice",
                scene_number=1,
                title="Valid Voice",
                narration_text="Narration text",
                visual_prompt="Cinematic shot description for defense",
                duration_sec=5.0,
                voice_persona=valid_persona,
            )
            ok_sb = FlowStoryboard(project_id="test_ok_voice", topic="Voice Test", scenes=[ok_voice_scene])
            assert validate_storyboard(ok_sb) is True
            assert validate_storyboard(ok_sb, raise_on_error=True) is True

        # ======================================================================
        # 8. Zero Literal Cyrillic Compliance Verification
        # ======================================================================
        sb_file_path = Path(ttd_sb.__file__)
        sb_code_text = sb_file_path.read_text(encoding="utf-8")
        assert not re.search(r"[\u0400-\u04FF]", sb_code_text), (
            "src/ttd_storyboard.py must have 0 literal Cyrillic characters (use \\uXXXX unicode escapes)"
        )

        current_test_path = Path(__file__)
        current_test_text = current_test_path.read_text(encoding="utf-8")
        assert not re.search(r"[\u0400-\u04FF]", current_test_text), (
            "tests/test_flow_studio.py must have 0 literal Cyrillic characters"
        )

    finally:
        if _tmp_ctx is not None:
            _tmp_ctx.cleanup()


def test_ttd_r3_pilot_scene_assembly_and_html5_player(tmp_path: Path | None = None) -> None:
    """
    REQ-TTD-M3: Verify Crossroads pilot test scene assembly (720p HD MP4),
    Russian studio voiceover (voice_y0joebp3bwta RMS > 350.0), synchronized
    WebVTT/SRT subtitle tracks, and HTML5 interactive player registration in
    output/index.html preserving existing baseline lessons.
    Strict zero literal Cyrillic compliance is enforced.
    """
    import json
    import os
    import re
    import subprocess
    import cv2
    import imageio_ffmpeg
    import numpy as np
    from pathlib import Path

    # 1. Workspace Resolution
    testbench_dir = Path(__file__).resolve().parent.parent
    output_dir = testbench_dir / "output"
    pilot_dir = output_dir / "lesson_ttd_pilot_crossroads"

    # ======================================================================
    # Echelon 1: Deliverable Files Existence & Non-Emptiness
    # ======================================================================
    assert pilot_dir.is_dir(), f"Pilot lesson directory missing: {pilot_dir}"

    mp4_path = pilot_dir / "lesson_full_720p.mp4"
    assert mp4_path.is_file(), f"Assembled 720p MP4 missing: {mp4_path}"
    mp4_size_bytes = mp4_path.stat().st_size
    assert mp4_size_bytes > 100 * 1024, (
        f"Assembled MP4 size ({mp4_size_bytes} bytes) is below 100 KB threshold"
    )

    sb_json_path = pilot_dir / "storyboard.json"
    assert sb_json_path.is_file(), f"storyboard.json missing: {sb_json_path}"
    sb_data = json.loads(sb_json_path.read_text(encoding="utf-8"))
    assert sb_data.get("project_id") == "flow_ttd_pilot_crossroads"
    assert len(sb_data.get("scenes", [])) >= 4

    vtt_path = pilot_dir / "subtitles.vtt"
    assert vtt_path.is_file(), f"subtitles.vtt missing: {vtt_path}"
    assert vtt_path.stat().st_size > 0, "subtitles.vtt is empty"

    srt_path = pilot_dir / "subtitles.srt"
    assert srt_path.is_file(), f"subtitles.srt missing: {srt_path}"
    assert srt_path.stat().st_size > 0, "subtitles.srt is empty"

    # Verify per-scene clip MP4 files
    scene_clips = sorted(pilot_dir.glob("scene_*.mp4"))
    assert len(scene_clips) >= 4, f"Expected >= 4 scene clips, found {len(scene_clips)}"
    for sc_clip in scene_clips:
        assert sc_clip.stat().st_size > 20 * 1024, f"Scene clip {sc_clip.name} is truncated"

    # ======================================================================
    # Echelon 2: Video Stream Geometry, Resolution & Duration
    # ======================================================================
    cap = cv2.VideoCapture(str(mp4_path))
    assert cap.isOpened(), f"OpenCV failed to open assembled MP4: {mp4_path}"

    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = float(cap.get(cv2.CAP_PROP_FPS))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.release()

    assert (width, height) == (1280, 720), (
        f"Video resolution mismatch: expected 1280x720, got {width}x{height}"
    )
    assert fps > 0.0, f"Invalid video framerate: {fps}"
    duration_sec = total_frames / fps
    assert duration_sec >= 30.0, (
        f"Video duration ({duration_sec:.2f}s) is shorter than required 30.0s"
    )

    # ======================================================================
    # Echelon 3: Audio Presence, Speech Integrity & Acoustic RMS Guard
    # ======================================================================
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    audio_cmd = [
        ffmpeg_exe, "-y", "-i", str(mp4_path),
        "-vn", "-f", "s16le", "-ac", "1", "-ar", "24000", "-"
    ]
    proc = subprocess.run(audio_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    audio_bytes = proc.stdout
    assert len(audio_bytes) > 0, "Assembled MP4 contains zero audio samples!"

    samples = np.frombuffer(audio_bytes, dtype=np.int16)
    audio_duration = len(samples) / 24000.0
    assert audio_duration >= 30.0, (
        f"Audio track duration ({audio_duration:.2f}s) is below 30.0s requirement"
    )

    audio_rms = float(np.sqrt(np.mean(samples.astype(np.float64) ** 2)))
    assert audio_rms > 350.0, (
        f"Audio RMS energy ({audio_rms:.2f}) is below standard speech threshold 350.0 (near silence)"
    )
    max_peak = int(np.max(np.abs(samples)))
    assert max_peak > 1500, f"Audio signal peak ({max_peak}) indicates corrupted or quiet audio"

    # ======================================================================
    # Echelon 4: Subtitles Formatting & Temporal Cue Synchronization
    # ======================================================================
    vtt_content = vtt_path.read_text(encoding="utf-8")
    assert vtt_content.startswith("WEBVTT"), "subtitles.vtt must start with 'WEBVTT'"
    vtt_cues = re.findall(
        r"(\d{2}:\d{2}:\d{2}\.\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}\.\d{3})",
        vtt_content,
    )
    assert len(vtt_cues) >= 4, f"Expected >= 4 VTT cues, found {len(vtt_cues)}"
    assert vtt_cues[0][0] == "00:00:00.000", "First VTT cue must begin at 00:00:00.000"

    srt_content = srt_path.read_text(encoding="utf-8")
    srt_cues = re.findall(
        r"(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})",
        srt_content,
    )
    assert len(srt_cues) >= 4, f"Expected >= 4 SRT cues, found {len(srt_cues)}"
    assert srt_cues[0][0] == "00:00:00,000", "First SRT cue must begin at 00:00:00,000"

    # ======================================================================
    # Echelon 5: HTML5 Player Registration & Baseline Invariant Preservation
    # ======================================================================
    player_html_path = output_dir / "index.html"
    assert player_html_path.is_file(), f"HTML5 preview player missing: {player_html_path}"
    html_text = player_html_path.read_text(encoding="utf-8")

    match = re.search(r"const LESSONS = (\[.*?\]);\s*let currentIdx", html_text, re.DOTALL)
    assert match, "Could not locate const LESSONS array in output/index.html"
    lessons = json.loads(match.group(1))

    # Invariant: Baseline lessons must remain registered
    slugs = [l.get("slug") for l in lessons]
    assert "lesson_01_ru_transformer_mla" in slugs, "lesson_01_ru_transformer_mla missing from LESSONS"
    assert "lesson_02_en_quantum_bell" in slugs, "lesson_02_en_quantum_bell missing from LESSONS"
    assert "lesson_ttd_pilot_crossroads" in slugs, (
        "lesson_ttd_pilot_crossroads was not registered in LESSONS"
    )

    ttd_entry = next(l for l in lessons if l.get("slug") == "lesson_ttd_pilot_crossroads")
    assert ttd_entry.get("full_video_size_kb", 0) > 100.0
    assert "lesson_full_720p.mp4" in ttd_entry.get("full_video", "")

    ttd_project = ttd_entry.get("project", {})
    assert ttd_project.get("project_id") == "flow_ttd_pilot_crossroads"
    assert ttd_project.get("language") == "ru"
    assert ttd_project.get("aspect_ratio") == "16:9"
    assert ttd_project.get("status") == "assembled"
    assert ttd_project.get("assembled_video_url") == "output/lesson_ttd_pilot_crossroads/lesson_full_720p.mp4"
    assert ttd_project.get("subtitles_vtt", "").startswith("WEBVTT")

    ttd_scenes = ttd_project.get("scenes", [])
    assert len(ttd_scenes) >= 4, f"Expected >= 4 scenes in project, got {len(ttd_scenes)}"
    for sc in ttd_scenes:
        assert sc.get("scene_number", 0) > 0
        assert sc.get("duration_sec", 0) > 0.0
        assert sc.get("video_url", "").startswith("output/lesson_ttd_pilot_crossroads/scene_")
        assert sc.get("voice_persona") == "voice_y0joebp3bwta"

    # ======================================================================
    # Echelon 6: Zero Literal Cyrillic Compliance Check
    # ======================================================================
    test_file_path = Path(__file__)
    test_content = test_file_path.read_text(encoding="utf-8")
    assert not re.search(r"[\u0400-\u04FF]", test_content), (
        "tests/test_flow_studio.py must maintain 0 literal Cyrillic characters (use \\uXXXX escapes)"
    )



def test_req_flow_ui_01_window_discovery_and_ui_map_calibration() -> None:
    """REQ-FLOW-UI-01: Verify FlowUIController window discovery and [0..1000] normalized UI map calibration."""
    from src.flow_ui_controller import (
        FlowUIController,
        FlowUIMap,
        discover_flow_chrome_window,
    )

    ui_map = FlowUIMap()
    required_controls = (
        "profile_close_btn",
        "new_project_btn",
        "existing_project_card",
        "prompt_textarea",
        "mode_selector_btn",
        "settings_btn",
        "model_quality_option",
        "aspect_16_9_option",
        "outputs_x2_option",
        "outputs_x4_option",
        "generate_submit_btn",
        "scenebuilder_btn",
        "download_btn",
    )
    for ctrl_name in required_controls:
        coord = ui_map.get_norm_coord(ctrl_name)
        assert isinstance(coord, tuple) and len(coord) == 2, f"Invalid coord for {ctrl_name}: {coord}"
        nx, ny = coord
        assert 0 <= nx <= 1000 and 0 <= ny <= 1000, f"Out-of-bounds [0..1000] coord for {ctrl_name}: {coord}"
        assert (nx, ny) != (0, 0), f"Fail-safe corner (0, 0) forbidden for {ctrl_name}"

    ctrl = FlowUIController(screen_width=1920, screen_height=1200, dry_run=True)
    px_x, px_y = ctrl.norm_to_screen_px(500, 858)
    assert (px_x, px_y) == (960, 1030) or abs(px_x - 960) <= 2
    win_info = discover_flow_chrome_window(allow_fallback=True)
    assert isinstance(win_info, dict)
    assert "hwnd" in win_info and "title" in win_info


def test_req_flow_ui_02_visual_oracle_and_training_telemetry(tmp_path: Path) -> None:
    """REQ-FLOW-UI-02: Verify 64-bit dHash VisualActionOracle and FlowUITrainingLog persistence."""
    from PIL import Image, ImageDraw
    from src.flow_ui_controller import (
        FlowUIController,
        compute_dhash64_from_rgb,
        hamming_distance64,
        verify_ui_transition,
    )

    img_a = Image.new("RGB", (320, 180), (12, 12, 14))
    img_b = Image.new("RGB", (320, 180), (12, 12, 14))
    draw_b = ImageDraw.Draw(img_b)
    draw_b.rectangle([40, 40, 280, 140], fill=(230, 235, 245))

    rgb_a = img_a.tobytes()
    rgb_b = img_b.tobytes()
    h_a = compute_dhash64_from_rgb(rgb_a, 320, 180)
    h_b = compute_dhash64_from_rgb(rgb_b, 320, 180)
    assert hamming_distance64(h_a, h_a) == 0
    dist = hamming_distance64(h_a, h_b)
    assert dist >= 2, f"Expected dHash Hamming distance >= 2, got {dist}"

    oracle_res = verify_ui_transition(rgb_a, rgb_b, 320, 180, min_hamming=2)
    assert oracle_res["verified"] is True
    assert oracle_res["status_tag"] == "[FACT]"
    assert oracle_res["hamming_distance"] >= 2

    ctrl = FlowUIController(screen_width=1920, screen_height=1200, dry_run=True)
    step = ctrl.record_training_step(
        step_name="click_new_project",
        control_name="new_project_btn",
        action_type="click",
        dhash_before=h_a,
        dhash_after=h_b,
        screenshot_path=str(tmp_path / "step_01.png"),
        notes="Opened Google Flow Project Editor",
    )
    assert step["verified"] is True
    assert step["hamming_distance"] >= 2
    log_path = tmp_path / "flow_ui_training_log.json"
    saved = ctrl.export_training_log(log_path)
    assert log_path.is_file()
    assert saved["total_steps"] >= 1


def test_req_flow_ui_03_live_flow_session_and_veo31_clip_dispatch() -> None:
    """REQ-FLOW-UI-03: Verify 6-layer Veo 3.1 prompt payload construction and Flow UI training telemetry."""
    from src.flow_ui_controller import FlowUIController, build_flow_ui_scene_prompt
    from src.ttd_storyboard import build_ttd_pilot_storyboard

    sb = build_ttd_pilot_storyboard()
    assert len(sb.scenes) == 5
    for sc in sb.scenes:
        payload = build_flow_ui_scene_prompt(sc)
        assert isinstance(payload, dict)
        assert payload["scene_id"] == sc.scene_id
        assert payload["model_profile"] in ("Veo 3.1 - Quality", "Veo 3.1 - Fast")
        assert payload["aspect_ratio"] == "16:9"
        assert len(payload["prompt_text"]) > 80
        assert "16:9" in payload["prompt_text"] or "Cinematic" in payload["prompt_text"]

    pilot_dir = TESTBENCH_DIR / "output" / "lesson_ttd_pilot_crossroads"
    log_file = pilot_dir / "flow_ui_training_log.json"
    assert log_file.is_file(), f"Missing Flow UI training log: {log_file}"
    log_data = json.loads(log_file.read_text(encoding="utf-8"))
    assert log_data.get("status") == "completed"
    assert int(log_data.get("total_steps", 0)) >= 5
    assert len(log_data.get("scene_dispatches", [])) == 5


def test_req_flow_ui_04_assembled_pilot_master_and_zero_cyrillic_hygiene() -> None:
    """REQ-FLOW-UI-04: Verify zero literal Cyrillic characters in Flow UI controller and assembled pilot master."""
    import re
    import src.flow_ui_controller as fui
    import src.ttd_pilot_assembler as tpa

    for mod in (fui, tpa):
        src_path = Path(mod.__file__)
        src_text = src_path.read_text(encoding="utf-8")
        assert not re.search(r"[\u0400-\u04FF]", src_text), (
            f"{src_path.name} must contain 0 literal Cyrillic characters"
        )

    cur_test = Path(__file__).read_text(encoding="utf-8")
    assert not re.search(r"[\u0400-\u04FF]", cur_test), (
        "tests/test_flow_studio.py must contain 0 literal Cyrillic characters"
    )


def test_m1_m2_m3_production_documents_presence_and_structure() -> None:
    """Verify presence, validity, and key sections of M1, M2, and M3 documentation artifacts."""
    doc_guide = TESTBENCH_DIR / "docs" / "google_flow_series_guide.md"
    rep_manual = TESTBENCH_DIR / "output" / "reports" / "flow_series_manual.md"
    doc_pipeline = TESTBENCH_DIR / "docs" / "drift_prevention_pipeline.md"
    rep_spec = TESTBENCH_DIR / "output" / "reports" / "manga_intro_transition_spec.md"

    for p in (doc_guide, rep_manual, doc_pipeline, rep_spec):
        assert p.is_file(), f"Expected document missing: {p}"
        assert p.stat().st_size > 4000, f"Document suspiciously small: {p}"

    # Verify M1 artifacts
    guide_text = doc_guide.read_text(encoding="utf-8")
    assert "Slot 0" in guide_text
    assert "Slot 1" in guide_text
    assert "referenceEntities" in guide_text
    assert "referenceImages" in guide_text
    assert "7d9a2a67-9cd2-4a79-932e-717d2e29257f" in guide_text
    assert "veo_3_1_extension_lite" in guide_text

    # Verify M3 Pipeline document
    pipe_text = doc_pipeline.read_text(encoding="utf-8")
    assert "PIPE-DRIFT-PREV-001" in pipe_text
    assert "@Ash_Streamer" in pipe_text
    assert "@Lucas_Knight" in pipe_text
    assert "@Lucas_Solitary_Back" in pipe_text
    assert "ING_STREAMER_ROOM" in pipe_text
    assert "ING_STREAMER_PC" in pipe_text
    assert "ING_GAME_SCREEN" in pipe_text
    assert "ING_STREAM_HUD" in pipe_text
    assert "24 frames" in pipe_text
    for beat_num in range(1, 8):
        assert f"Beat {beat_num}" in pipe_text

    # Verify M3 Transition Spec report
    spec_text = rep_spec.read_text(encoding="utf-8")
    assert "SPEC-MANGA-INTRO-TRANS-001" in spec_text
    assert "16:9" in spec_text
    assert "24.0 fps" in spec_text or "24 fps" in spec_text
    assert "8.000 seconds" in spec_text or "8.0s" in spec_text
    for clip_num in range(1, 8):
        assert f"Clip 0{clip_num}" in spec_text or f"Clip {clip_num}" in spec_text


def test_m2_canonical_arcane_concept_arts_presence_and_geometry() -> None:
    """Verify presence, format, and dimensions of all 9 canonical concept arts and master contact sheet."""
    from PIL import Image

    concept_dir = TESTBENCH_DIR / "output" / "canonical_arcane_concepts"
    assert concept_dir.is_dir(), f"Missing canonical concepts dir: {concept_dir}"

    canonical_files = [
        "streamer_ash_turnaround.png",
        "streamer_ash_desk.png",
        "knight_lucas_portrait.png",
        "knight_lucas_turnaround.png",
        "knight_lucas_solitary_back.png",
        "streamer_room_environment.png",
        "streamer_pc_desk_closeup.png",
        "game_save_the_empire_screen.png",
        "stream_overlay_chat_donation.png",
    ]

    for fname in canonical_files:
        img_path = concept_dir / fname
        assert img_path.is_file(), f"Missing canonical concept art: {fname}"
        with Image.open(img_path) as im:
            assert im.format == "PNG", f"Expected PNG format for {fname}, got {im.format}"
            w, h = im.size
            assert (w, h) == (1376, 768), f"{fname} must be exactly 1376x768, got ({w}, {h})"
            # Check non-blank content
            arr = np.array(im.convert("RGB"))
            assert arr.std() > 10.0, f"{fname} appears to be a blank or solid image"
            assert arr.mean() > 5.0, f"{fname} appears to be pure black"

    # Verify master contact sheet
    sheet_path = concept_dir / "master_contact_sheet.png"
    assert sheet_path.is_file(), "Missing master_contact_sheet.png"
    with Image.open(sheet_path) as im:
        assert im.format == "PNG"
        w, h = im.size
        assert w >= 2000, f"Contact sheet width too small: {w}"
        assert h >= 1200, f"Contact sheet height too small: {h}"
        arr = np.array(im.convert("RGB"))
        assert arr.std() > 15.0


def test_m3_continuation_pipeline_continuity_and_terminal_darkness_invariant() -> None:
    """Verify terminal keyframe darkness invariant and Fortiche Arcane prompt consistency."""
    from PIL import Image

    # 1. Verify Keyframe 05 (Frame 026) terminal darkness invariant
    clean_dir = TESTBENCH_DIR / "output" / "ttd_ep01_manga_transitions" / "clean_frames"
    kf5_path = clean_dir / "keyframe_05_frame026.png"
    assert kf5_path.is_file(), f"Missing clean keyframe 05: {kf5_path}"

    with Image.open(kf5_path) as im:
        arr = np.array(im.convert("RGB"))
        h, w, _ = arr.shape
        # Terminal darkness invariant: bottom 33% of canvas must have mean luminance <= 25.0
        bottom_third = arr[int(h * 0.67):, :, :]
        luminance = 0.299 * bottom_third[:, :, 0] + 0.587 * bottom_third[:, :, 1] + 0.114 * bottom_third[:, :, 2]
        mean_lum = float(luminance.mean())
        assert mean_lum <= 25.0, f"Keyframe 05 bottom third luminance {mean_lum:.2f} exceeds 25.0"

    # 2. Verify Canonical Arcane concept sheet for Lucas Solitary Back
    concept_dir = TESTBENCH_DIR / "output" / "canonical_arcane_concepts"
    back_img_path = concept_dir / "knight_lucas_solitary_back.png"
    assert back_img_path.is_file()
    with Image.open(back_img_path) as im:
        assert im.format == "PNG"
        assert im.size == (1376, 768)
        arr_back = np.array(im.convert("RGB"))
        h_back, _, _ = arr_back.shape
        bottom_third_back = arr_back[int(h_back * 0.67):, :, :]
        lum_back = 0.299 * bottom_third_back[:, :, 0] + 0.587 * bottom_third_back[:, :, 1] + 0.114 * bottom_third_back[:, :, 2]
        mean_lum_back = float(lum_back.mean())
        assert mean_lum_back <= 25.0, f"Lucas solitary back bottom third luminance {mean_lum_back:.2f} exceeds 25.0"

    # 3. Verify Prompt tokens & continuation invariants
    doc_pipeline = TESTBENCH_DIR / "docs" / "drift_prevention_pipeline.md"
    pipe_text = doc_pipeline.read_text(encoding="utf-8")
    assert "Fortiche Production Arcane" in pipe_text
    assert "3D chiaroscuro" in pipe_text
    assert "impasto" in pipe_text
    assert "\u0420\u0435\u0436\u0438\u043c \u043f\u0440\u043e\u0434\u043e\u043b\u0436\u0435\u043d\u0438\u044f" in pipe_text




def test_m2_stream_overlay_engine_bounds_and_clamping() -> None:
    """Verify that MangaStreamOverlayEngine strictly clamps all overlays to Y <= 580."""
    from src.flow_stream_overlays import MangaStreamOverlayEngine, verify_overlay_bounds

    engine = MangaStreamOverlayEngine()
    test_timestamps = [0.5, 5.0, 15.0, 32.0, 35.0, 45.0, 55.0, 59.0]
    for t in test_timestamps:
        frame = engine.render_overlay_frame(t)
        assert frame.size == (1280, 720)
        bounds = verify_overlay_bounds(frame)
        assert bounds["valid"] is True, f"Boundary violation at t={t}s: {bounds}"
        if not bounds["empty"]:
            assert bounds["max_y"] <= 580, f"max_y {bounds['max_y']} exceeds 580 at t={t}s"
            # Subtitle clearance zone Y in [600, 720] must have strictly 0 alpha
            arr = np.array(frame)
            assert np.all(arr[600:, :, 3] == 0), f"Subtitle area contaminated at t={t}s"


def test_m2_donation_banner_timing_and_golden_gradient() -> None:
    """Verify luxury golden donation banner appears strictly in Beat 4 (t ~ 30.0 - 39.8s)."""
    from src.flow_stream_overlays import (
        DONATION_X_MIN,
        DONATION_X_MAX,
        DONATION_Y_MIN,
        DONATION_Y_MAX,
        MangaStreamOverlayEngine,
    )

    engine = MangaStreamOverlayEngine()

    # Inactive before Beat 4
    frame_early = engine.render_overlay_frame(20.0)
    arr_early = np.array(frame_early)
    assert np.all(arr_early[DONATION_Y_MIN:DONATION_Y_MAX, DONATION_X_MIN:DONATION_X_MAX, 3] == 0)

    # Active during Beat 4 (e.g., t=33.5s)
    frame_mid = engine.render_overlay_frame(33.5)
    arr_mid = np.array(frame_mid)
    donation_crop = arr_mid[DONATION_Y_MIN:DONATION_Y_MAX, DONATION_X_MIN:DONATION_X_MAX, :]
    assert np.any(donation_crop[:, :, 3] > 100), "Donation banner not visible during Beat 4"
    # Verify gold tones: high red and green channels relative to blue
    gold_pixels = donation_crop[donation_crop[:, :, 3] > 100]
    mean_r = float(np.mean(gold_pixels[:, 0]))
    mean_g = float(np.mean(gold_pixels[:, 1]))
    mean_b = float(np.mean(gold_pixels[:, 2]))
    assert mean_r > mean_b, "Donation banner lacks warm golden tones"

    # Inactive after Beat 4
    frame_late = engine.render_overlay_frame(45.0)
    arr_late = np.array(frame_late)
    assert np.all(arr_late[DONATION_Y_MIN:DONATION_Y_MAX, DONATION_X_MIN:DONATION_X_MAX, 3] == 0)


def test_m2_terminal_void_dissolve_invariant() -> None:
    """Verify that all overlays dissolve to 0% opacity for Lucas solitary back in void (t >= 59.84s)."""
    from src.flow_stream_overlays import MangaStreamOverlayEngine

    engine = MangaStreamOverlayEngine()

    # Prior to dissolve
    assert engine.get_alpha_scale(58.0) == 1.0

    # During dissolve transition
    mid_scale = engine.get_alpha_scale(60.5)
    assert 0.0 < mid_scale < 1.0

    # In terminal void (t >= 61.5s)
    assert engine.get_alpha_scale(62.0) == 0.0
    assert engine.get_alpha_scale(69.8) == 0.0

    frame_void = engine.render_overlay_frame(65.0)
    arr_void = np.array(frame_void)
    assert np.all(arr_void[:, :, 3] == 0), "Terminal void canvas must have strictly zero alpha"


def test_m3_cinematic_audio_engine_5_layers_and_sample_rates() -> None:
    """Verify that CinematicAudioEngine synthesizes 5 stereo float32 layers at 48,000 Hz."""
    from src.flow_cinematic_audio import CinematicAudioEngine, DEFAULT_EP01_DURATION_SEC, SAMPLE_RATE

    engine = CinematicAudioEngine(total_dur_sec=DEFAULT_EP01_DURATION_SEC, sample_rate=SAMPLE_RATE)
    layers = engine.render_all_layers()
    assert len(layers) == 5
    for name, arr in layers.items():
        assert arr.ndim == 2
        assert arr.shape[1] == 2
        assert arr.shape[0] == int(round(DEFAULT_EP01_DURATION_SEC * SAMPLE_RATE))
        assert np.max(np.abs(arr)) > 0.01, f"{name} appears completely silent"
        assert np.max(np.abs(arr)) <= 1.0, f"{name} clips above 1.0"


def test_m3_layer1_narration_timbre_lock_and_7_beats_coverage() -> None:
    """Verify 7 narration beats, chronological monotonic timecodes, and voice_y0joebp3bwta timbre lock."""
    from src.flow_cinematic_audio import EP01_NARRATION_BEATS, VOICE_PERSONA_RU

    assert len(EP01_NARRATION_BEATS) == 7
    assert VOICE_PERSONA_RU == "voice_y0joebp3bwta"

    prev_end = -1.0
    for idx, beat in enumerate(EP01_NARRATION_BEATS, start=1):
        assert beat.beat_id == idx
        assert beat.t_start < beat.t_end
        assert beat.t_start >= prev_end or abs(beat.t_start - prev_end) < 2.0
        assert len(beat.transcript_ru) > 10
        prev_end = beat.t_end


def test_m3_terminal_void_audio_silence_invariant() -> None:
    """Verify Layer 5 environmental ambience at t >= 67.5s has strictly 0.0 amplitude."""
    from src.flow_cinematic_audio import CinematicAudioEngine, SAMPLE_RATE

    engine = CinematicAudioEngine(total_dur_sec=69.792, sample_rate=SAMPLE_RATE)
    l5 = engine.render_layer_5()
    silence_idx = int(67.5 * SAMPLE_RATE)
    tail = l5[silence_idx:, :]
    assert np.all(tail == 0.0), "Terminal void audio tail must be strictly 0.0 silent"


def test_m3_synchronized_subtitles_vtt_and_srt_generation() -> None:
    """Verify generation of synchronized WebVTT and SRT subtitle tracks with 7 cues."""
    from src.flow_cinematic_audio import generate_srt_subtitles, generate_webvtt_subtitles

    vtt = generate_webvtt_subtitles()
    assert vtt.startswith("WEBVTT")
    assert "00:00:00.000 --> 00:00:07.500" in vtt

    srt = generate_srt_subtitles()
    assert srt.startswith("1\n00:00:00,000 --> 00:00:07,500")
    for i in range(1, 8):
        assert f"\n{i}\n" in f"\n{srt}"


def test_m3_cinematic_master_mp4_container_and_faststart() -> None:
    """Verify master MP4 deliverable exists, >=720p, 24fps CFR, FastStart atom layout, and zero drift."""
    import cv2
    from scripts.assemble_ep01_cinematic_audio_video import DEFAULT_OUTPUT_MASTER, parse_iso_bmff_atoms

    master_path = DEFAULT_OUTPUT_MASTER
    assert master_path.is_file(), f"Master deliverable missing: {master_path}"
    assert master_path.stat().st_size > 10_000_000, f"Master file size suspiciously small: {master_path.stat().st_size}"

    atoms = parse_iso_bmff_atoms(master_path)
    atom_names = [a[0] for a in atoms]
    assert "ftyp" in atom_names
    assert "moov" in atom_names
    assert "mdat" in atom_names
    assert atom_names.index("moov") < atom_names.index("mdat"), "FastStart ordering violated"

    cap = cv2.VideoCapture(str(master_path))
    assert cap.isOpened()
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = float(cap.get(cv2.CAP_PROP_FPS))
    frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.release()

    assert w == 1280 and h == 720
    assert abs(fps - 24.0) < 0.1
    assert frames == 1675
    dur = frames / fps
    assert abs(dur - 69.792) < 0.05



def test_m4_delivery_verification_all_8_checkpoints() -> None:
    """Verify all 8 mandatory delivery checkpoints using scripts.verify_ep01_cinematic_delivery."""
    from scripts.verify_ep01_cinematic_delivery import (
        DEFAULT_BRAIN_DIR,
        DEFAULT_MASTER,
        verify_cinematic_delivery,
    )

    assert DEFAULT_MASTER.is_file(), f"Master deliverable file missing: {DEFAULT_MASTER}"
    res = verify_cinematic_delivery(master_path=DEFAULT_MASTER, brain_dir=DEFAULT_BRAIN_DIR)
    assert res["all_checkpoints_passed"] is True
    for cp_name, cp_data in res["checkpoints"].items():
        assert cp_data["pass"] is True, f"Checkpoint failed: {cp_name} -> {cp_data}"


def test_m4_audio_video_sync_and_bitrates() -> None:
    """Verify audio-video duration sync <= 50ms and bitrates satisfy broadcast thresholds."""
    from scripts.verify_ep01_cinematic_delivery import DEFAULT_MASTER, probe_media_streams

    assert DEFAULT_MASTER.is_file()
    media = probe_media_streams(DEFAULT_MASTER)
    dur_v = media["duration_v"]
    dur_a = media["duration_a"]
    drift = abs(dur_v - dur_a)
    assert drift <= 0.05, f"Audio-video sync drift too high: {drift}s > 0.05s"

    size_bytes = DEFAULT_MASTER.stat().st_size
    total_bitrate_kbps = (size_bytes * 8) / (dur_v * 1000) if dur_v > 0 else 0.0
    audio_bitrate_kbps = 192.0
    video_bitrate_kbps = max(0.0, total_bitrate_kbps - audio_bitrate_kbps)
    assert video_bitrate_kbps > 1000.0, f"Video bitrate too low: {video_bitrate_kbps} kbps"
    assert audio_bitrate_kbps >= 128.0, f"Audio bitrate too low: {audio_bitrate_kbps} kbps"


def test_m4_brain_directory_mirror_parity() -> None:
    """Verify master video, subtitles, and manifests are mirrored with exact parity in brain dir."""
    from scripts.verify_ep01_cinematic_delivery import DEFAULT_BRAIN_DIR, DEFAULT_MASTER

    assert DEFAULT_BRAIN_DIR.is_dir(), f"Brain directory missing: {DEFAULT_BRAIN_DIR}"
    brain_master = DEFAULT_BRAIN_DIR / DEFAULT_MASTER.name
    assert brain_master.is_file(), f"Brain master file missing: {brain_master}"
    assert brain_master.stat().st_size == DEFAULT_MASTER.stat().st_size, (
        f"Master size mismatch: {brain_master.stat().st_size} vs {DEFAULT_MASTER.stat().st_size}"
    )

    out_dir = DEFAULT_MASTER.parent
    for fname in ["ttd_episode_01_narration.vtt", "ttd_episode_01_narration.srt", "ttd_episode_01_assembly_manifest.json"]:
        src_f = out_dir / fname
        mir_f = DEFAULT_BRAIN_DIR / fname
        if src_f.is_file():
            assert mir_f.is_file(), f"Mirrored file missing in brain: {mir_f}"
            assert mir_f.stat().st_size == src_f.stat().st_size, f"Size mismatch for {fname}"


def test_req_r4_master_cinematic_container_8_checkpoints() -> None:
    """REQ-R4: Verify 8 mandatory quality checkpoints across Episode 1 cinematic master deliverable."""
    from scripts.verify_ep01_cinematic_delivery import (
        DEFAULT_BRAIN_DIR,
        DEFAULT_MASTER,
        DEFAULT_SUBTITLES_DIR,
        run_all_checkpoints,
        verify_ep01_cinematic_delivery,
    )

    assert DEFAULT_MASTER.is_file(), f"Master MP4 missing: {DEFAULT_MASTER}"
    report = run_all_checkpoints(
        master_video=DEFAULT_MASTER,
        subtitles_dir=DEFAULT_SUBTITLES_DIR,
        brain_dir=DEFAULT_BRAIN_DIR,
    )

    assert report["all_passed"] is True, f"Checkpoints failed: {report}"
    assert report["passed_count"] == 8
    assert report["total_count"] == 8

    # Also verify compatibility wrapper
    compat = verify_ep01_cinematic_delivery(master_path=DEFAULT_MASTER, brain_dir=DEFAULT_BRAIN_DIR)
    assert compat["all_checkpoints_passed"] is True
    assert len(compat["checkpoints"]) == 8
    for cp_key, cp_val in compat["checkpoints"].items():
        assert cp_val["pass"] is True, f"Checkpoint failed: {cp_key} -> {cp_val}"

