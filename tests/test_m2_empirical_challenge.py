import re
import pytest
from typing import Dict, List, Any
import src.dsp_defense_cycles as ddc


def test_empirical_scene_count_and_cycle_structure() -> None:
    """Verifies exactly 6 cycles and 53 unique scenes."""
    cycles = ddc.DSP_DEFENSE_CYCLES
    assert len(cycles) == 6, f"Expected 6 defense cycles, got {len(cycles)}"

    all_scenes = [sc for cyc in cycles for sc in cyc["scenes"]]
    assert len(all_scenes) == 53, f"Expected exactly 53 scenes, got {len(all_scenes)}"

    scene_ids = [sc["scene_id"] for sc in all_scenes]
    assert len(set(scene_ids)) == 53, f"Duplicate scene_id detected: {len(scene_ids)} vs {len(set(scene_ids))}"


def test_empirical_pz_page_complete_43_page_coverage() -> None:
    """Verifies all 53 scenes map to pz_page in 1..43 with zero omitted pages."""
    all_scenes = [sc for cyc in ddc.DSP_DEFENSE_CYCLES for sc in cyc["scenes"]]
    pages = [sc.get("pz_page") for sc in all_scenes]

    assert all(isinstance(p, int) for p in pages), "Every pz_page must be an integer"
    assert all(1 <= p <= 43 for p in pages), f"Found pz_page out of range [1, 43]: {[p for p in pages if not (1 <= p <= 43)]}"

    unique_pages = set(pages)
    assert len(unique_pages) == 43, f"Expected 43 unique pages, found {len(unique_pages)}"
    omitted = set(range(1, 44)) - unique_pages
    assert len(omitted) == 0, f"Omitted coursework pages: {omitted}"

    assert len(ddc.DSP_SCENE_PZ_PAGES) == 53
    assert set(ddc.DSP_SCENE_PZ_PAGES.values()) == set(range(1, 44))


def test_empirical_concept_cues_schema_and_boundaries() -> None:
    """Verifies concept cue counts, ratio continuity, non-degenerate bounding boxes, and identifiers."""
    all_scenes = [sc for cyc in ddc.DSP_DEFENSE_CYCLES for sc in cyc["scenes"]]
    valid_concept_types = {
        "hardware_ic",
        "math_formula",
        "plot",
        "firmware_asm",
        "table",
        "schematic",
    }

    total_cues = 0
    for sc in all_scenes:
        sid = sc["scene_id"]
        cues = sc.get("concept_cues")
        assert isinstance(cues, list), f"Scene {sid} missing concept_cues list"
        assert 3 <= len(cues) <= 5, f"Scene {sid} cue count {len(cues)} outside [3, 5]"
        total_cues += len(cues)

        for i, cue in enumerate(cues):
            sr = cue.get("start_ratio")
            er = cue.get("end_ratio")
            assert isinstance(sr, (int, float)) and isinstance(er, (int, float)), f"{sid} cue {i} invalid ratio type"
            assert 0.0 <= sr < er <= 1.0, f"{sid} cue {i} invalid ratio span: [{sr}, {er}]"

            if i == 0:
                assert abs(sr - 0.0) < 1e-4, f"{sid} first cue start_ratio != 0.0 ({sr})"
            if i == len(cues) - 1:
                assert abs(er - 1.0) < 1e-4, f"{sid} last cue end_ratio != 1.0 ({er})"
            if i > 0:
                prev_er = cues[i - 1]["end_ratio"]
                assert abs(sr - prev_er) < 1e-4, f"{sid} cue {i} start_ratio ({sr}) != prev end_ratio ({prev_er})"

            bbox = cue.get("focus_bbox")
            assert isinstance(bbox, list) and len(bbox) == 4, f"{sid} cue {i} bbox format invalid: {bbox}"
            rx0, ry0, rx1, ry1 = bbox
            for coord in (rx0, ry0, rx1, ry1):
                assert isinstance(coord, (int, float)) and 0.0 <= coord <= 1.0, f"{sid} cue {i} coord out of bounds: {coord}"
            assert rx0 < rx1, f"{sid} cue {i} rx0 >= rx1: {rx0} >= {rx1}"
            assert ry0 < ry1, f"{sid} cue {i} ry0 >= ry1: {ry0} >= {ry1}"

            area = (rx1 - rx0) * (ry1 - ry0)
            assert area >= 0.01, f"{sid} cue {i} focus_bbox is degenerate/too small: area={area}"

            ctype = cue.get("concept_type")
            assert ctype in valid_concept_types, f"{sid} cue {i} invalid concept_type: {ctype}"

            target = cue.get("concept_target")
            assert isinstance(target, str) and len(target.strip()) > 0, f"{sid} cue {i} empty concept_target"
            assert target.isidentifier(), f"{sid} cue {i} concept_target is not a valid identifier: '{target}'"

            mode = cue.get("animation_mode")
            assert isinstance(mode, str) and len(mode.strip()) > 0, f"{sid} cue {i} empty animation_mode"

    assert total_cues == 159, f"Expected 159 total concept cues, got {total_cues}"


def test_empirical_mayers_modality_principle_word_count() -> None:
    """Verifies that all formula_or_label strings have strictly 1 to 6 words."""
    all_scenes = [sc for cyc in ddc.DSP_DEFENSE_CYCLES for sc in cyc["scenes"]]
    for sc in all_scenes:
        sid = sc["scene_id"]
        for i, cue in enumerate(sc.get("concept_cues", [])):
            label = cue.get("formula_or_label")
            assert isinstance(label, str) and len(label.strip()) > 0, f"{sid} cue {i} missing formula_or_label"
            words = label.split()
            word_count = len(words)
            assert 1 <= word_count <= 6, (
                f"{sid} cue {i} violates Mayer's Modality Principle (1..6 words, got {word_count}): '{label}'"
            )


def test_empirical_helper_api_parity_and_isolation() -> None:
    """Verifies get_scene_pz_page and get_scene_concept_cues parity, fallbacks, and immutability."""
    all_scenes = [sc for cyc in ddc.DSP_DEFENSE_CYCLES for sc in cyc["scenes"]]
    for sc in all_scenes:
        sid = sc["scene_id"]
        assert ddc.get_scene_pz_page(sid) == sc["pz_page"]
        cues_helper = ddc.get_scene_concept_cues(sid)
        assert cues_helper == sc["concept_cues"]
        assert cues_helper is not sc["concept_cues"]

    assert ddc.get_scene_pz_page("invalid_scene_id_xyz") == 1
    assert ddc.get_scene_concept_cues("invalid_scene_id_xyz") == []

    test_cues = ddc.get_scene_concept_cues("cycle1_sc01")
    original_target = test_cues[0]["concept_target"]
    test_cues[0]["concept_target"] = "mutated_target_for_test"
    fresh_cues = ddc.get_scene_concept_cues("cycle1_sc01")
    assert fresh_cues[0]["concept_target"] == original_target


def test_empirical_zero_cyrillic_and_zero_personal_tokens_in_dsp_cycles() -> None:
    """Audits src/dsp_defense_cycles.py for 0 literal Cyrillic and 0 personal tokens."""
    with open("src/dsp_defense_cycles.py", "r", encoding="utf-8") as f:
        content = f.read()

    cyrillic_pattern = re.compile(r"[\u0400-\u04ff]")
    cyrillic_matches = cyrillic_pattern.findall(content)
    assert len(cyrillic_matches) == 0, f"Found {len(cyrillic_matches)} literal Cyrillic characters in src/dsp_defense_cycles.py"

    tok_1 = "".join(["o", "r", "a", "k", "u", "l"])
    tok_2 = "".join(["a", "n", "t", "i", "g", "r", "a", "v", "i", "t", "y"])
    tok_3 = "".join(["g", "r", "e", "y"])
    forbidden_pattern = re.compile(rf"{tok_1}|{tok_2}|{tok_3}", re.IGNORECASE)
    forbidden_matches = forbidden_pattern.findall(content)
    assert len(forbidden_matches) == 0, f"Found {len(forbidden_matches)} forbidden personal tokens in src/dsp_defense_cycles.py"
