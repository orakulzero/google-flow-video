"""Unit and architectural tests for Milestone 2 Episode 1 Storyboard & Shot Matrix (M2).

Verifies:
1. docs/ttd_ep01_pilot_bible.md existence, 12 scenes, model sheets, and Climax sequence.
2. docs/ttd_ep01_shot_matrix.json 12-shot schema validity and canonical tokens.
3. Canonical golden background plates geometry and existence (1280x720 16:9).
4. Zero Cyrillic characters in src/flow_prompt_library.py and prompt outputs.
5. Fortiche 6-stage prompt engine formulas and validation oracle.
"""

import json
from pathlib import Path
from PIL import Image
import pytest

from src.flow_prompt_library import (
    EP01_CANONICAL_ASH_TOKENS,
    EP01_CANONICAL_LILY_TOKENS,
    EP01_CANONICAL_LUCAS_HAIR,
    EP01_CANONICAL_LUCAS_ZERO_SPARKS,
    build_fortiche_arcane_6stage_prompt,
    build_lucas_climax_roaring_prompt,
    load_ep01_shot_matrix,
    validate_ep01_canonical_prompts,
)


def test_ep01_pilot_bible_presence_and_structure():
    """Verify docs/ttd_ep01_pilot_bible.md exists and covers all required narrative sections."""
    bible_path = Path("docs/ttd_ep01_pilot_bible.md")
    assert bible_path.is_file(), "docs/ttd_ep01_pilot_bible.md must exist"

    text = bible_path.read_text(encoding="utf-8")
    assert len(text) > 10000, "Bible content must be comprehensive"

    # Verify all 12 scenes
    for i in range(1, 13):
        scene_tag = f"Scene {i:02d}:"
        assert scene_tag in text, f"Missing {scene_tag} in pilot bible"

    # Verify character model sheets
    assert "Master Character Model Sheet: Knight Lucas MacGregor" in text
    assert "Master Character Model Sheet: Prince Ash Bornhater" in text
    assert "Lily" in text and "Blind Wind Sniper" in text

    # Verify Climax Sequence
    assert "SHOT CL-01" in text
    assert "SHOT CL-02" in text
    assert "SHOT CL-03" in text
    assert "SHOT CL-04" in text

    # Verify canonical invariants mentioned
    assert "dirty-blonde" in text.lower()
    assert "zero glowing eyes" in text.lower()


def test_ep01_shot_matrix_schema_and_integrity():
    """Verify docs/ttd_ep01_shot_matrix.json contains 12 compliant shots."""
    shots = load_ep01_shot_matrix("docs/ttd_ep01_shot_matrix.json")
    assert len(shots) == 12

    required_keys = {
        "shot_id", "scene_title", "duration_seconds", "camera", "lighting",
        "characters", "background_anchor", "positive_prompt", "negative_prompt"
    }
    for shot in shots:
        assert required_keys.issubset(set(shot.keys())), f"Missing keys in {shot.get('shot_id')}"
        assert shot["duration_seconds"] > 0
        assert len(shot["positive_prompt"]) > 40
        assert len(shot["negative_prompt"]) > 20

    val = validate_ep01_canonical_prompts(shots)
    assert val["valid"] is True, f"Canonical validation failed: {val['errors']}"


def test_canonical_background_plates_presence_and_geometry():
    """Verify the 3 golden background plates exist at exact 1280x720 16:9 resolution."""
    plates_dir = Path("output/canonical_plates")
    assert plates_dir.is_dir()

    expected_plates = [
        "bg_crossroads_ramparts_night.png",
        "bg_cathedral_boss_arena.png",
        "bg_streamer_room_night.png",
    ]

    for fname in expected_plates:
        p = plates_dir / fname
        assert p.is_file(), f"Plate {fname} missing"
        with Image.open(p) as img:
            assert img.size == (1280, 720), f"Plate {fname} size {img.size} != (1280, 720)"
            assert img.mode in ("RGB", "RGBA"), f"Plate {fname} unexpected mode {img.mode}"


def test_zero_cyrillic_hygiene_in_library_and_matrix():
    """Enforce 100% English-only characters in Python code and JSON matrix."""
    py_text = Path("src/flow_prompt_library.py").read_text(encoding="utf-8")
    cyr_py = [c for c in py_text if "\u0400" <= c <= "\u04FF"]
    assert len(cyr_py) == 0, f"Detected {len(cyr_py)} Cyrillic characters in src/flow_prompt_library.py"

    json_text = Path("docs/ttd_ep01_shot_matrix.json").read_text(encoding="utf-8")
    cyr_json = [c for c in json_text if "\u0400" <= c <= "\u04FF"]
    assert len(cyr_json) == 0, f"Detected {len(cyr_json)} Cyrillic characters in docs/ttd_ep01_shot_matrix.json"


def test_fortiche_6stage_climax_roaring_prompt_generation():
    """Verify build_lucas_climax_roaring_prompt complies with 6-stage formula and canonical tokens."""
    prompt = build_lucas_climax_roaring_prompt(push_in_pct=15, dutch_tilt_deg=12, is_video=True)
    pos = prompt.compose_positive()
    neg = prompt.compose_negative()

    assert "dirty-blonde" in pos
    assert "zero glowing eyes" in pos
    assert "glowing eyes" in neg
    assert "sparks on armor" in neg
    assert "Omni 1.1 Flash" in pos
    assert "12-degree Dutch tilt" in pos
