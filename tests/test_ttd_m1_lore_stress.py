"""tests/test_ttd_m1_lore_stress.py
Milestone 1 Empirical Stress Test & Adversarial Verification Suite
for Tyrant of the Tower Defense Game Universe Lore Bible and Atlas.
Enforces 100% English-only rules, negative prompt rigor, and mechanical consistency.
"""

from __future__ import annotations

from pathlib import Path
import re
import pytest

DOCS_DIR = Path("docs")
LORE_BIBLE_PATH = DOCS_DIR / "ttd_universe_lore_bible.md"
ATLAS_PATH = DOCS_DIR / "ttd_world_locations_atlas.md"
SRC_LORE_PATH = Path("src/ttd_lore_bible.py")

FORBIDDEN_GLOW_TOKENS = [
    "glowing eyes",
    "glowing eye",
    "laser pupils",
    "laser pupil",
    "arcade sparks",
    "arcade spark",
    "floating magic sparks",
    "floating magic spark",
    "magic sparks",
    "magic spark",
    "blade glow",
    "electric blue lightning",
    "flaming magical runes",
    "neon lighting",
    "neon lights",
]

NEGATIVE_CONTEXT_KEYWORDS = [
    "zero",
    "prohibit",
    "negative",
    "eliminate",
    "reject",
    "forbidden",
    "banned",
    "anti-cheat",
    "strictly",
    "without",
    "no ",
    "not ",
]


def test_lore_documents_exist_and_non_empty():
    """Verify primary M1 deliverable files exist and have substantial content."""
    assert LORE_BIBLE_PATH.is_file(), f"Missing {LORE_BIBLE_PATH}"
    assert ATLAS_PATH.is_file(), f"Missing {ATLAS_PATH}"

    lore_text = LORE_BIBLE_PATH.read_text(encoding="utf-8")
    atlas_text = ATLAS_PATH.read_text(encoding="utf-8")

    assert len(lore_text.strip().splitlines()) >= 200, "Lore bible must have at least 200 lines"
    assert len(atlas_text.strip().splitlines()) >= 200, "World atlas must have at least 200 lines"


def test_forbidden_glowing_tokens_strictly_in_negative_contexts():
    """Empirical probe verifying glowing/arcade tokens are NEVER used affirmatively."""
    lore_text = LORE_BIBLE_PATH.read_text(encoding="utf-8")
    lines = lore_text.splitlines()

    violations = []
    for line_idx, line in enumerate(lines, start=1):
        line_lower = line.lower()
        for token in FORBIDDEN_GLOW_TOKENS:
            if token in line_lower:
                # Check surrounding context (current line or section heading)
                has_negative_cue = any(neg in line_lower for neg in NEGATIVE_CONTEXT_KEYWORDS)
                if not has_negative_cue:
                    # Also check previous 2 lines in case of list under a prohibition heading
                    prev_lines = " ".join(lines[max(0, line_idx - 3):line_idx]).lower()
                    if not any(neg in prev_lines for neg in NEGATIVE_CONTEXT_KEYWORDS):
                        violations.append(f"Line {line_idx}: '{token}' in positive context: '{line}'")

    assert not violations, f"Forbidden glowing tokens found in affirmative contexts:\n" + "\n".join(violations)


def test_lucas_mechanics_consistency():
    """Verify Lucas's 3 skills are codified with exact game mechanics."""
    lore_text = LORE_BIBLE_PATH.read_text(encoding="utf-8")

    # Skill 1: Man of Steel
    assert "Man of Steel" in lore_text, "Missing 'Man of Steel' skill name"
    assert "1 HP" in lore_text, "Missing '1 HP' lethal nullification specification"
    assert re.search(r"lethal damage nullification", lore_text, re.IGNORECASE), "Missing lethal damage nullification"

    # Skill 2: Strike of Will
    assert "Strike of Will" in lore_text, "Missing 'Strike of Will' skill name"
    assert re.search(r"infinitely stacking", lore_text, re.IGNORECASE), "Missing infinite stacking mechanic"

    # Skill 3: Step of Tenacity
    assert "Step of Tenacity" in lore_text, "Missing 'Step of Tenacity' skill name"
    assert re.search(r"spatial intercept", lore_text, re.IGNORECASE), "Missing spatial intercept mechanic"

    # Verify Stage 50 climax scenario explicitly mentions all three
    stage_50_section = lore_text[lore_text.find("## 2. Stage 50"):lore_text.find("## 3. Master Character Profile")]
    assert "Man of Steel" in stage_50_section
    assert "Strike of Will" in stage_50_section
    assert "Step of Tenacity" in stage_50_section


def test_character_profile_consistency():
    """Verify Knight Lucas master character specifications conform to prompt invariant rules."""
    lore_text = LORE_BIBLE_PATH.read_text(encoding="utf-8")

    # Age 22-25
    assert re.search(r"Age:\s*22\s*to\s*25", lore_text, re.IGNORECASE), "Missing age 22-25 in profile"

    # 3/4 Low Angle Framing
    assert re.search(r"three-quarter low-angle perspective", lore_text, re.IGNORECASE), "Missing 3/4 low-angle framing"
    assert re.search(r"Yaw 25-35 deg", lore_text), "Missing yaw angle spec"
    assert re.search(r"Pitch \+8 to \+12 deg", lore_text), "Missing pitch angle spec"

    # Weathered tan skin
    assert re.search(r"weathered bronze-tan skin", lore_text, re.IGNORECASE), "Missing weathered tan skin attribute"

    # Left cheek claw scar
    assert re.search(r"left cheek claw scar", lore_text, re.IGNORECASE), "Missing left cheek claw scar attribute"

    # Natural steel-gray eyes
    assert re.search(r"steel-gray irises", lore_text, re.IGNORECASE), "Missing steel-gray eyes specification"


def test_world_locations_atlas_consistency():
    """Verify world locations atlas contains all required geopolitical and spatial landmarks."""
    atlas_text = ATLAS_PATH.read_text(encoding="utf-8")

    # Crossroads fortress geometry
    assert "30 meters high" in atlas_text or "30-meter" in atlas_text, "Missing 30m basalt wall specification"
    assert "50-meter" in atlas_text or "50-meter-wide dry kill-zone moat" in atlas_text, "Missing 50m moat"

    # Black Fog properties
    assert "300 meters south" in atlas_text or "300-meter" in atlas_text, "Missing 300m Black Fog boundary"
    assert "consumes photons" in atlas_text or "Light Devouring" in atlas_text, "Missing light absorption property"

    # Core landmarks
    assert "New Terra" in atlas_text, "Missing New Terra imperial capital"
    assert "Sunken Lake Kingdom" in atlas_text or "The Sunken Realm" in atlas_text, "Missing Sunken Lake Kingdom"
    assert "Sleepless Princess" in atlas_text, "Missing Sleepless Princess"
    assert "Evergreen" in atlas_text, "Missing Evergreen elven forest"
    assert "Shadow Squad" in atlas_text, "Missing Shadow Squad"


def test_zero_cyrillic_in_python_sources():
    """Enforce ISO 9001 zero Cyrillic rule across all python files in tests/ and src/."""
    cyrillic_pattern = re.compile(r"[\u0400-\u04FF]")
    py_files = list(Path("src").glob("*.py")) + list(Path("tests").glob("*.py"))

    violations = []
    for py_file in py_files:
        content = py_file.read_text(encoding="utf-8")
        matches = cyrillic_pattern.findall(content)
        if matches:
            violations.append(f"{py_file}: contains {len(matches)} literal Cyrillic characters")

    assert not violations, f"Zero Cyrillic rule violated in python sources:\n" + "\n".join(violations)
