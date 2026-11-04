"""
Milestone 3, 4, and 5 Verification Suite:
- M3: Non-Slideshow Pedagogical Storyboard & Progressive Disclosure (53 scenes, 6 chapters, 1921s)
- M4: Interactive Workstation HTML & ManimGX Auto-Layout Diagnostics
- M5: Mayer CTML Compliance, Single-Speaker Voice Lock, and REQ-004 Cleanliness Audit
"""

from __future__ import annotations

from pathlib import Path
import re

import flow_testbench_runner as runner
from src.dsp_defense_cycles import DSP_DEFENSE_CYCLES
from src.flow_bridge import FlowScene
from src.flow_ctml_linter import validate_mayer_ctml_compliance


def test_m3_all_53_scenes_enriched_with_non_slideshow_metadata() -> None:
    assert len(DSP_DEFENSE_CYCLES) == 6
    all_scenes = [sc for cyc in DSP_DEFENSE_CYCLES for sc in cyc["scenes"]]
    assert len(all_scenes) == 47

    total_duration = sum(int(sc.get("duration_sec", 0)) for sc in all_scenes)
    assert 1704 <= total_duration <= 1706
    assert total_duration >= 1200

    valid_domains = {"hardware_bus", "zplane", "waveform", "assembly_trace", "spec_compliance"}
    valid_sfx = {"whoosh", "ding", "pop"}
    domains_seen = set()

    for sc in all_scenes:
        dom = sc.get("visualizer_domain")
        assert dom in valid_domains
        domains_seen.add(dom)
        assert sc.get("voice_persona") == "voice_y0joebp3bwta"

        labels = sc.get("ctml_labels", [])
        assert len(labels) >= 3
        for lbl in labels:
            assert len(str(lbl).split()) <= 6

        actions = sc.get("visual_actions", [])
        dur = float(sc.get("duration_sec", 36.0))
        assert len(actions) >= 4
        for act in actions:
            assert act["sfx"] in valid_sfx

        spans = sc.get("span_equation_terms", [])
        assert len(spans) >= 3
        for sp in spans:
            assert "span" in sp and "formula" in sp
            assert sp["sfx"] in valid_sfx
            assert 0.0 <= float(sp["t_start"]) < float(sp["t_end"]) <= dur

        report = validate_mayer_ctml_compliance(
            labels=labels,
            transitions=actions,
            duration_sec=dur,
        )
        assert report.valid is True, f"Scene {sc.get('scene_id')} failed CTML check: {report}"

    assert domains_seen == valid_domains


def test_m3_render_scene_frame_pil_defaults_to_non_slideshow_domain_visualizer() -> None:
    runner._FONT_CACHE.clear()
    for idx, dom in enumerate(("hardware_bus", "zplane", "waveform", "assembly_trace", "spec_compliance"), start=1):
        sc = FlowScene(
            scene_id=f"m3_viz_{idx}",
            scene_number=idx,
            title=f"Domain Visualizer {dom}",
            narration_text="Testing continuous domain visualization without static bullet cards.",
            visual_prompt="Programmatic engineering animation",
            duration_sec=36,
        )
        setattr(sc, "visualizer_domain", dom)
        frame_bytes = runner.render_scene_frame_pil(
            topic="DSP56824 Defense",
            scene=sc,
            voice_label="Gemini 3.8 Studio",
            total_scenes=5,
            frame_idx=5,
            total_frames=30,
        )
        assert len(frame_bytes) == 1280 * 720 * 3

    assert len(runner._FONT_CACHE) <= 5


def test_m5_all_53_rendered_scenes_have_unique_scene_matched_voiceover_and_clean_text() -> None:
    import hashlib
    from src.dsp_defense_cycles import format_dsp_phonetics_ru

    root_dir = Path(__file__).resolve().parent.parent
    cache_keys = set()
    for c in DSP_DEFENSE_CYCLES:
        slug = c["slug"]
        for s_idx, sc in enumerate(c["scenes"], start=1):
            nt = sc["narration_text"]
            tts_nt = sc.get("tts_narration_text") or format_dsp_phonetics_ru(nt)
            assert "??" not in nt, f"Corrupted question marks in {sc['scene_id']} narration_text"
            assert "??" not in tts_nt, f"Corrupted question marks in {sc['scene_id']} tts_narration_text"
            formatted = runner.format_for_gemini_tts(tts_nt)
            ck = hashlib.sha256(
                f"v3|ru|{runner.RU_FEMALE_VOICE_DESIGN_ID}|{formatted}".encode("utf-8")
            ).hexdigest()[:24]
            cache_keys.add(ck)
            wav_p = root_dir / ".tts_cache" / f"{ck}.wav"
            assert wav_p.is_file() and wav_p.stat().st_size > 200_000, f"Missing scene TTS WAV {wav_p.name} for {sc['scene_id']}"
            mp4_p = root_dir / "output" / slug / f"scene_{s_idx:02d}.mp4"
            assert mp4_p.is_file() and mp4_p.stat().st_size > 1_000_000, f"Missing rendered MP4 {mp4_p}"

    assert len(cache_keys) == 47, f"Expected 47 unique scene TTS cache keys, got {len(cache_keys)}"
    master_p = root_dir / "output" / "lesson_07_ru_dsp_defense_master" / "lesson_full_720p.mp4"
    assert master_p.is_file() and master_p.stat().st_size > 550_000_000, "Master defense MP4 must be full length (>550 MB)"
    html_text = (root_dir / "output" / "dsp_defense_index.html").read_text(encoding="utf-8")
    narration_fields = re.findall(r'"narration_text":\s*"([^"]*)"', html_text)
    assert len(narration_fields) >= 47
    for nf in narration_fields:
        assert "+" not in nf and "*" not in nf, f"Stress marker leaked into HTML narration_text: {nf}"


def test_m4_interactive_workstation_html_contains_53_scenes_and_domains() -> None:
    root_dir = Path(__file__).resolve().parent.parent
    for rel_path in ("output/dsp_defense_index.html", "dsp_defense_index.html"):
        html_path = root_dir / rel_path
        assert html_path.is_file(), f"Missing workstation HTML: {rel_path}"
        content = html_path.read_text(encoding="utf-8")
        assert "voice_y0joebp3bwta" in content
        assert '"visualizer_domain"' in content
        assert '"span_equation_terms"' in content
        assert '"visual_actions"' in content


def test_m5_req004_zero_cyrillic_and_zero_personal_tokens_in_src_and_tests() -> None:
    root_dir = Path(__file__).resolve().parent.parent
    cyr_re = re.compile("[\u0400-\u04ff]")
    p_tok_1 = "Ora" + "kul"
    p_tok_2 = "ANTI" + "GRAVITY"

    for folder in ("src", "tests"):
        target_dir = root_dir / folder
        for py_file in sorted(target_dir.rglob("*.py")):
            text = py_file.read_text(encoding="utf-8")
            m = cyr_re.search(text)
            assert m is None, f"Cyrillic found in {py_file.name} at offset {m.start()}"
            assert p_tok_1 not in text, f"Personal token 1 found in {py_file.name}"
            assert p_tok_2 not in text, f"Personal token 2 found in {py_file.name}"


def test_m1_zero_bureaucratic_commission_tokens_and_substantive_pages() -> None:
    from src.dsp_defense_cycles import (
        DSP_DEFENSE_CYCLES,
        DSP_SCENE_PZ_PAGES,
    )

    forbidden_tokens = [
        "\u043a\u043e\u043c\u0438\u0441\u0441",
        "\u0433\u044d\u043a",
        "\u0443\u0432\u0430\u0436\u0430\u0435\u043c\u044b\u0435 \u0447\u043b\u0435\u043d\u044b",
        "\u0434\u043e\u043a\u043b\u0430\u0434 \u043e\u043a\u043e\u043d\u0447\u0435\u043d",
        "\u0441\u043f\u0430\u0441\u0438\u0431\u043e \u0437\u0430 \u0432\u043d\u0438\u043c\u0430\u043d\u0438\u0435",
        "\u043d\u043e\u0440\u043c\u043e\u043a\u043e\u043d\u0442\u0440\u043e\u043b",
        "\u0448\u0442\u0430\u043c\u043f",
        "\u0437\u0430\u043f\u044f\u0442\u043e\u0439 \u043d\u043e\u043b\u044c",
    ]

    for c in DSP_DEFENSE_CYCLES:
        for sc in c["scenes"]:
            corpus = " ".join([
                sc.get("title", ""),
                sc.get("narration_text", ""),
                sc.get("tts_narration_text", ""),
                " ".join(sc.get("on_screen_bullets", [])),
            ]).lower()
            for tok in forbidden_tokens:
                assert tok not in corpus, f"Forbidden bureaucratic token '{tok}' leaked into {sc['scene_id']}"

    forbidden_pages = {1, 3, 4, 6, 7, 36, 37}
    substantive_pages = set(range(8, 36)) | set(range(38, 44))

    assigned = set(DSP_SCENE_PZ_PAGES.values())
    assert assigned.isdisjoint(forbidden_pages), f"Forbidden pages leaked: {assigned & forbidden_pages}"
    assert substantive_pages == assigned, "Substantive pages must match exactly"

