"""
tests/test_flow_m5_m9_pipeline.py
End-to-end TDD verification suite for Milestones M5..M9:
  - M5: Local Reference Prompt Index (`src/flow_prompt_library.py`)
  - M6: Auto-Layout Healer & FFmpeg Contact Sheet Critic (`src/flow_manimgx.py`)
  - M7: 48 kHz Audio Mixer with -12 dB Auto-Ducking & SFX Accents (`whoosh`, `ding`/`pop`)
  - M8: Hybrid Pipeline (`src/flow_cli.py --engine manimgx`) stitching Scene 1 (`STM32H743` +
        `IS61LV6416` `closed_form_spring` `seek(t)`) + Scene 2 (`manimgx` H(z) & Z-plane)
  - M9: Zero Cyrillic & zero personal path tokens across all `src/` and `tests/` files
"""

from __future__ import annotations

from pathlib import Path
import re
import subprocess
import sys

import imageio_ffmpeg
import manimgx as m
import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from flow_cli import (  # noqa: E402
    draw_hardware_exploded_frame_at_t,
    render_hardware_spring_scene_to_mp4,
    render_hybrid_stm32_biquad_lesson,
    run_cli,
)
from flow_manimgx import (  # noqa: E402
    GeminiStudioVoice,
    build_contact_sheet,
    inspect_manimgx_scene,
    mix_studio_audio_with_ducking_and_sfx,
)
from flow_prompt_library import (  # noqa: E402
    GEMINI_ARGON_PROMPT_COUNT,
    GEMINI_ARGON_REPO,
    OPUS_PROMPT_COUNT,
    OPUS_REPO,
    SUPPORTED_CATEGORIES,
    SUPPORTED_TECH_TAGS,
    TOTAL_PROMPT_COUNT,
    FlowPromptLibrary,
    closed_form_spring,
    get_flow_prompt_library,
    match_position_transition,
    plan_semantic_beats,
    validate_deterministic_seek_contract,
    validate_semantic_beat_density,
)


# ============================================================================
# Milestone M5: Reference Prompt Library & Deterministic System Templates
# ============================================================================


def test_m5_prompt_library_counts_and_filtering() -> None:
    lib = get_flow_prompt_library()
    stats = lib.get_stats()

    assert stats["total_prompts"] == TOTAL_PROMPT_COUNT == 1007
    assert stats["by_repo"][OPUS_REPO] == OPUS_PROMPT_COUNT == 703
    assert stats["by_repo"][GEMINI_ARGON_REPO] == GEMINI_ARGON_PROMPT_COUNT == 304

    for cat in SUPPORTED_CATEGORIES:
        cat_hits = lib.search(category=cat)
        assert len(cat_hits) > 0
        assert all(p.category == cat for p in cat_hits)

    for tag in SUPPORTED_TECH_TAGS:
        tag_hits = lib.search(tech_tags=[tag])
        assert len(tag_hits) > 0
        assert all(tag in p.tech_tags for p in tag_hits)

    multi_hits = lib.search(
        category="3d",
        tech_tags=["threejs", "shader"],
        require_all_tags=True,
        limit=10,
    )
    assert 1 <= len(multi_hits) <= 10
    assert all(
        p.category == "3d" and "threejs" in p.tech_tags and "shader" in p.tech_tags
        for p in multi_hits
    )


def test_m5_deterministic_seek_contract_validator() -> None:
    clean_js = """
    function draw(t) {
        const x = closed_form_spring(t, 1.0, 12.0);
        ctx.fillRect(x * 100, 50, 40, 40);
    }
    window.seek = function(t) { draw(t); };
    """
    res_clean = validate_deterministic_seek_contract(clean_js)
    assert res_clean["ok"] is True
    assert res_clean["has_window_seek"] is True
    assert res_clean["has_draw_fn"] is True
    assert res_clean["forbidden_timers"] == []

    bad_js = """
    setInterval(() => { draw(); }, 16);
    """
    res_bad = validate_deterministic_seek_contract(bad_js)
    assert res_bad["ok"] is False
    assert "setInterval" in res_bad["forbidden_timers"]


def test_m5_closed_form_spring_and_match_position() -> None:
    # Critically damped (zeta = 1.0)
    assert closed_form_spring(-0.5, zeta=1.0, omega0=12.0) == pytest.approx(0.0)
    assert closed_form_spring(0.0, zeta=1.0, omega0=12.0) == pytest.approx(0.0)
    mid_val = float(closed_form_spring(0.25, zeta=1.0, omega0=12.0))
    assert 0.70 < mid_val < 1.0
    assert closed_form_spring(3.0, zeta=1.0, omega0=12.0) == pytest.approx(1.0, abs=1e-5)

    # Underdamped (zeta = 0.3) exhibits controlled overshoot > 1.0
    t_grid = np.linspace(0.0, 1.5, 150)
    under = closed_form_spring(t_grid, zeta=0.3, omega0=12.0)
    assert isinstance(under, np.ndarray)
    assert float(under.max()) > 1.02
    assert float(under[-1]) == pytest.approx(1.0, abs=0.02)

    # Overdamped (zeta = 1.8) stays monotonic in [0, 1]
    over = closed_form_spring(t_grid, zeta=1.8, omega0=12.0)
    assert float(over.max()) <= 1.0
    assert np.all(np.diff(over) >= -1e-9)

    # Match-position bounding box interpolation
    box_a = (0.0, 0.0, 100.0, 50.0)
    box_b = (200.0, 100.0, 400.0, 250.0)
    assert match_position_transition(box_a, box_b, 0.0) == pytest.approx(box_a)
    assert match_position_transition(box_a, box_b, 4.0) == pytest.approx(box_b, abs=1e-3)


def test_m5_semantic_beat_density_12_to_15_per_30s() -> None:
    beats = plan_semantic_beats(duration_sec=30.0, beats_per_30s=14)
    assert len(beats) == 14
    check = validate_semantic_beat_density(len(beats), duration_sec=30.0)
    assert check["ok"] is True
    assert 12.0 <= check["beats_per_30s"] <= 15.0

    sparse_check = validate_semantic_beat_density(5, duration_sec=30.0)
    assert sparse_check["ok"] is False


# ============================================================================
# Milestone M6: Auto-Layout Healer & FFmpeg Contact Sheet Critic
# ============================================================================


def test_m6_auto_layout_healer_fixes_cut_overlap_crossing_covered_small() -> None:
    class MultiDefectScene(m.Scene):
        def construct(self) -> None:
            # 1. `small` text (< 20 px at 1080p)
            tiny_txt = m.Text("Tiny Sub-Threshold Caption", font_size=9)
            # 2. `overlap` between two texts at origin
            overlap_a = m.Text("Primary Biquad Transfer Header", font_size=36)
            overlap_b = m.Text("Colliding Secondary Header", font_size=36)
            # 3. `cut` mobject extending past frame right/top edge
            cut_rect = m.Rectangle(width=4.0, height=2.5).shift(6.8 * m.RIGHT + 3.6 * m.UP)
            # 4. `crossing` & `covered`: opaque filled shape drawn over text
            cover_box = m.Rectangle(
                width=5.0,
                height=1.8,
                fill_color=m.BLUE,
                fill_opacity=0.85,
                stroke_width=4,
            )
            self.add(tiny_txt, overlap_a, overlap_b, cut_rect, cover_box)

    diag = inspect_manimgx_scene(
        MultiDefectScene,
        width=640,
        height=360,
        fps=15,
        auto_heal=True,
    )
    assert len(diag["initial_problems"]) >= 2
    initial_kinds = {p["kind"] for p in diag["initial_problems"]}
    assert len(initial_kinds & {"small", "overlap", "cut", "crossing", "covered"}) >= 2
    assert diag["clean"] is True
    assert diag["healed"] is True
    assert diag["ok"] is True
    assert diag["remaining_problems"] == []
    assert diag["problems"] == []


def test_m6_build_contact_sheet_5x4_and_black_frame_critic(tmp_path: Path) -> None:
    hw_mp4 = tmp_path / "sample_hw.mp4"
    render_hardware_spring_scene_to_mp4(
        hw_mp4,
        width=320,
        height=180,
        fps=12,
        narration_script="Short [spring hardware] test clip.",
    )
    sheet_png = tmp_path / "contact_sheet.png"
    report = build_contact_sheet(hw_mp4, sheet_png, cols=5, rows=4, thumb_width=160, thumb_height=90)

    assert report["ok"] is True
    assert sheet_png.is_file()
    assert report["cols"] == 5
    assert report["rows"] == 4
    assert report["tile_count"] == 20
    assert report["black_frame_count"] == 0
    assert len(report["tile_luma_means"]) == 20
    assert all(m_val > 5.0 for m_val in report["tile_luma_means"])

    # Verify black-frame critic catches an all-black video
    black_mp4 = tmp_path / "all_black.mp4"
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    subprocess.run(
        [
            ffmpeg_exe,
            "-y",
            "-f",
            "lavfi",
            "-i",
            "color=c=black:s=160x90:r=10:d=1.0",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(black_mp4),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    black_sheet_png = tmp_path / "black_sheet.png"
    black_report = build_contact_sheet(
        black_mp4, black_sheet_png, cols=5, rows=4, thumb_width=80, thumb_height=45
    )
    assert black_report["ok"] is False
    assert black_report["black_frame_count"] == 20


# ============================================================================
# Milestone M7: Audio Mixer with -12 dB Auto-Ducking and Point SFX Accents
# ============================================================================


def test_m7_audio_mixer_auto_ducking_minus_12db_and_sfx_accents() -> None:
    voice_en = GeminiStudioVoice(language="en")
    speech_en = voice_en("We derive [transfer function H of z] inside [the unit circle].")

    # Add a 1.0s trailing silence window so both speech and silence windows are substantial
    padded = np.vstack([speech_en.samples, np.zeros((48000, 1), dtype=np.float32)])
    mix = mix_studio_audio_with_ducking_and_sfx(
        padded,
        span_timestamps=[0.35, 1.15],
        transition_timestamps=[0.05],
        duck_db=-12.0,
    )

    assert mix["sample_rate"] == 48000
    assert mix["duck_db"] == pytest.approx(-12.0)
    assert mix["duck_linear_gain"] == pytest.approx(10.0 ** (-12.0 / 20.0), rel=1e-4)
    assert mix["ambient_rms_during_speech"] < mix["ambient_rms_during_silence"] * 0.5
    assert -14.5 <= mix["measured_duck_db"] <= -8.5
    assert mix["transition_sfx_count"] == 1
    assert mix["span_sfx_count"] == 2
    kinds = [e["kind"] for e in mix["sfx_events"]]
    assert "whoosh" in kinds
    assert "ding" in kinds
    assert "pop" in kinds

    # Verify Russian persona & phonetic formatter
    voice_ru = GeminiStudioVoice(language="ru")
    assert voice_ru.voice_persona == "voice_y0joebp3bwta"
    speech_ru = voice_ru("STM32H743 \u0438 IS61LV6416 \u0432 \u043a\u0430\u0441\u043a\u0430\u0434\u0435 IIR.")
    assert len(speech_ru.samples) > 24000


# ============================================================================
# Milestone M8: Hybrid Pipeline & CLI (--engine manimgx)
# ============================================================================


def test_m8_cli_engine_manimgx_and_hybrid_multi_scene_stitch(tmp_path: Path) -> None:
    out_dir = tmp_path / "hybrid_out"
    res = run_cli(
        [
            "--engine",
            "manimgx",
            "--topic",
            "STM32H743 + IS61LV6416 Biquad IIR Pipeline",
            "--output-dir",
            str(out_dir),
            "--width",
            "320",
            "--height",
            "180",
            "--fps",
            "10",
            "--cols",
            "5",
            "--rows",
            "4",
            "--assemble",
        ]
    )

    assert res["ok"] is True
    assert res["engine"] == "manimgx"
    assert res["scene_count"] == 2
    assert Path(res["output_mp4"]).is_file()
    assert Path(res["output_srt"]).is_file()
    assert Path(res["output_vtt"]).is_file()
    assert Path(res["contact_sheet_png"]).is_file()
    assert res["contact_sheet"]["ok"] is True
    assert res["contact_sheet"]["black_frame_count"] == 0
    assert len(res["captions"]) >= 2


def test_cloud_veo_prompt_and_turn_extractor() -> None:
    from flow_bridge import (
        build_cloud_veo_prompt,
        extract_cloud_video_from_turns,
        sanitize_cloud_veo_narration,
    )

    raw_ru = "[\u0424\u0438\u043b\u044c\u0442\u0440] *\u043f\u043e\u0434\u0430\u0432\u043b\u044f\u0435\u0442* \u0432\u044b\u0441\u043e\u043a\u043e\u0447\u0430\u0441\u0442\u043e\u0442\u043d\u044b\u0435 +\u043f\u043e\u043c\u0435\u0445\u0438."
    clean_ru = sanitize_cloud_veo_narration(raw_ru)
    assert "\u043f\u043e\u0434\u0430\u0432\u043b\u044f\u0435\u0442" not in clean_ru
    assert "\u043f\u043e\u043c\u0435\u0445\u0438" not in clean_ru
    assert "\u0441\u0433\u043b\u0430\u0436\u0438\u0432\u0430\u0435\u0442" in clean_ru
    assert "\u043a\u043e\u043b\u0435\u0431\u0430\u043d\u0438\u044f" in clean_ru

    prompt = build_cloud_veo_prompt(
        visual_prompt="A glowing 3D microchip STM32H743 on a dark PCB",
        narration_text=raw_ru,
        language="ru",
    )
    assert prompt.startswith("Generate a short 5-second video:")
    assert "with a female voice saying in Russian:" in prompt

    mock_turns = [
        [
            [
                ["c_test", "r_test"],
                None,
                [["prompt"]],
                [
                    [
                        [
                            "rc_test",
                            ["Your video is ready!"],
                            None,
                            None,
                            None,
                            None,
                            None,
                            None,
                            [2],
                            "en",
                            None,
                            None,
                            [
                                {
                                    "60": [
                                        [
                                            [
                                                [
                                                    [
                                                        None,
                                                        2,
                                                        "video.mp4",
                                                        None,
                                                        None,
                                                        "tok",
                                                        None,
                                                        [
                                                            "https://lh3.googleusercontent.com/gg/thumb",
                                                            "https://contribution.usercontent.google.com/download?filename=video.mp4",
                                                        ],
                                                        2,
                                                        None,
                                                        "video/mp4",
                                                    ]
                                                ],
                                                [
                                                    "prompt",
                                                    None,
                                                    [None, None, "models/omni_1p2_pro_gemini_app"],
                                                    None,
                                                    None,
                                                    None,
                                                    None,
                                                    ["[00:00.000] Scene", None, "", "Speaker A: Test"],
                                                ],
                                            ]
                                        ]
                                    ]
                                }
                            ],
                        ]
                    ]
                ],
            ]
        ]
    ]
    parsed = extract_cloud_video_from_turns(mock_turns)
    assert parsed is not None
    assert parsed["status"] == "completed"
    assert parsed["model"] == "models/omni_1p2_pro_gemini_app"
    assert len(parsed["urls"]) == 2
    assert parsed["transcript"] == "Speaker A: Test"


# ============================================================================
# Milestone M9: Cleanliness Gate (Zero Cyrillic & Zero Personal Path Tokens)
# ============================================================================


def test_m9_zero_cyrillic_and_zero_personal_tokens_across_all_src_and_tests() -> None:
    cyrillic_re = re.compile("[\u0400-\u04ff]")
    tok_a = ("Ora" + "kul").lower()
    tok_b = ("ANTI" + "GRAVITY").lower()

    py_files = sorted(list((REPO_ROOT / "src").glob("*.py")) + list((REPO_ROOT / "tests").glob("*.py")))
    assert len(py_files) >= 8

    for path in py_files:
        content = path.read_text(encoding="utf-8")
        assert cyrillic_re.search(content) is None, f"Cyrillic found in {path.name}"
        lowered = content.lower()
        assert tok_a not in lowered, f"Personal token found in {path.name}"
        assert tok_b not in lowered, f"Workspace token found in {path.name}"
