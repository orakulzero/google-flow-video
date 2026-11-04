"""
Automated pytest suite for ManimGX integration (`src/flow_manimgx.py` & `/api/flow/manimgx/*`)
in Google Flow Educational Video Studio L4.
"""

from __future__ import annotations

from pathlib import Path
import re
import sys

from fastapi.testclient import TestClient
import manimgx as m
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"
for _p in (str(REPO_ROOT), str(SRC_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)


def test_gemini_studio_voice_enforces_female_persona() -> None:
    from flow_manimgx import GeminiStudioVoice

    voice_en = GeminiStudioVoice(language="en")
    assert voice_en.voice_gender == "female"
    assert voice_en.voice_persona == "Sulafat"

    voice_ru = GeminiStudioVoice(language="ru")
    assert voice_ru.voice_gender == "female"
    assert voice_ru.voice_persona == "voice_y0joebp3bwta"

    with pytest.raises(ValueError, match="female"):
        GeminiStudioVoice(voice_gender="male")


def test_gemini_studio_voice_generates_timed_48khz_speech() -> None:
    from flow_manimgx import GeminiStudioVoice

    voice = GeminiStudioVoice(language="en")
    speech = voice("The transfer function H of z has two conjugate poles.")
    assert isinstance(speech, m.Speech)
    assert speech.duration > 1.0
    assert speech.samples.shape[1] == 1
    assert len(speech.words) == 10
    assert speech.words[0].text == "The"
    assert speech.words[-1].text == "poles."
    assert speech.words[-1].end <= speech.duration


def test_inspect_manimgx_scene_passes_clean_layout() -> None:
    from flow_manimgx import DspBiquadTransferScene, inspect_manimgx_scene

    diag = inspect_manimgx_scene(
        DspBiquadTransferScene, width=640, height=360, fps=15
    )
    assert diag["ok"] is True
    assert diag["problems"] == []
    assert "no problems" in diag["report_text"]
    assert diag["play_count"] >= 2
    assert diag["duration_sec"] > 1.0
    assert "00:00:" in diag["subtitles_srt"]
    assert diag["subtitles_vtt"].startswith("WEBVTT")


def test_inspect_manimgx_scene_detects_overlapping_text_defect() -> None:
    from flow_manimgx import StudioVoiceScene, inspect_manimgx_scene

    class OverlappingDefectScene(StudioVoiceScene):
        def construct(self) -> None:
            t1 = m.Text("First overlapping label", font_size=48)
            t2 = m.Text("Second overlapping label", font_size=48).shift(0.05 * m.UP)
            self.play(m.FadeIn(t1), m.FadeIn(t2), run_time=0.5)

    diag = inspect_manimgx_scene(
        OverlappingDefectScene, width=640, height=360, fps=15
    )
    assert diag["ok"] is False
    assert len(diag["problems"]) >= 1
    assert any(p["kind"] == "overlap" for p in diag["problems"])


def test_render_manimgx_scene_to_mp4_produces_h264_aac_and_subtitles(
    tmp_path: Path,
) -> None:
    from flow_manimgx import DspBiquadTransferScene, render_manimgx_scene_to_mp4

    out_mp4 = tmp_path / "biquad_lesson.mp4"
    res = render_manimgx_scene_to_mp4(
        DspBiquadTransferScene,
        output_path=out_mp4,
        width=480,
        height=270,
        fps=12,
        supersample=1,
    )
    assert res["ok"] is True
    assert res["layout_ok"] is True
    assert res["has_audio"] is True
    assert res["video_size_bytes"] > 2000
    assert res["mp4_bytes"][4:8] == b"ftyp"
    assert out_mp4.is_file()
    assert out_mp4.with_suffix(".srt").is_file()
    assert out_mp4.with_suffix(".vtt").is_file()


def test_fastapi_manimgx_inspect_and_render_endpoints() -> None:
    from flow_api import app

    with TestClient(app) as client:
        resp_insp = client.post(
            "/api/flow/manimgx/inspect",
            json={
                "topic": "Discrete Fourier Transform",
                "formula_latex": r"X[k] = \sum_{n=0}^{N-1} x[n] e^{-i 2\pi k n / N}",
                "narration_script": "We evaluate [the DFT sum] on [the unit circle].",
                "width": 480,
                "height": 270,
                "fps": 12,
            },
        )
        assert resp_insp.status_code == 200
        insp_data = resp_insp.json()
        assert insp_data["ok"] is True
        assert insp_data["engine"] == "manimgx"
        assert insp_data["voice_gender"] == "female"

        resp_rnd = client.post(
            "/api/flow/manimgx/render",
            json={
                "topic": "Discrete Fourier Transform",
                "formula_latex": r"X[k] = \sum_{n=0}^{N-1} x[n] e^{-i 2\pi k n / N}",
                "narration_script": "We evaluate [the DFT sum] on [the unit circle].",
                "width": 320,
                "height": 180,
                "fps": 10,
                "supersample": 1,
            },
        )
        assert resp_rnd.status_code == 200
        rnd_data = resp_rnd.json()
        assert rnd_data["ok"] is True
        assert rnd_data["engine"] == "manimgx"
        assert rnd_data["voice_gender"] == "female"
        assert rnd_data["video_size_bytes"] > 1000
        assert rnd_data["has_audio"] is True
        assert rnd_data["layout_ok"] is True


def test_manimgx_files_zero_cyrillic_and_zero_personal_tokens() -> None:
    cyrillic_re = re.compile("[\u0400-\u04ff]")
    tok_a = ("Ora" + "kul").lower()
    tok_b = ("ANTI" + "GRAVITY").lower()

    for path in (
        REPO_ROOT / "src" / "flow_manimgx.py",
        REPO_ROOT / "tests" / "test_manimgx_integration.py",
    ):
        content = path.read_text(encoding="utf-8")
        assert cyrillic_re.search(content) is None, f"Cyrillic found in {path.name}"
        lowered = content.lower()
        assert tok_a not in lowered, f"Personal token found in {path.name}"
        assert tok_b not in lowered, f"Workspace token found in {path.name}"
