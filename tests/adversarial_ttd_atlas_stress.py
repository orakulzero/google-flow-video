"""Empirical Adversarial Stress Harness & Oracle for TTD Atlas & Structural Boundaries.

Stress-tests dimensional invariants, negative visual constraints, and topological
consistency against deliberate counter-examples and corrupted mutations.
"""

from pathlib import Path
import re
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = REPO_ROOT / "docs"
ATLAS_PATH = DOCS_DIR / "ttd_world_locations_atlas.md"
LORE_PATH = DOCS_DIR / "ttd_universe_lore_bible.md"


def test_oracle_rejects_hallucinated_crossroads_dimensions():
    atlas_text = ATLAS_PATH.read_text(encoding="utf-8")

    # Strict regex dimension extraction
    wall_match = re.search(r"(\d+)-meter.*?curtain wall", atlas_text, re.IGNORECASE)
    assert wall_match is not None, "Failed to match curtain wall height"
    assert int(wall_match.group(1)) == 30, f"Wall height must be 30m, got {wall_match.group(1)}"

    moat_match = re.search(r"(\d+)-meter-wide dry kill-zone moat", atlas_text, re.IGNORECASE)
    assert moat_match is not None, "Failed to match moat width"
    assert int(moat_match.group(1)) == 50, f"Moat width must be 50m, got {moat_match.group(1)}"

    spire_match = re.search(r"towers (\d+) meters above", atlas_text, re.IGNORECASE)
    assert spire_match is not None, "Failed to match spire height"
    assert int(spire_match.group(1)) == 60, f"Spire height must be 60m, got {spire_match.group(1)}"

    fog_match = re.search(r"\*{0,2}(\d+)\s*meters\s*south\*{0,2}\s*of\s*the\s*Crossroads", atlas_text, re.IGNORECASE)
    assert fog_match is not None, "Failed to match fog perimeter"
    assert int(fog_match.group(1)) == 300, f"Fog distance must be 300m, got {fog_match.group(1)}"


def test_oracle_strictly_bans_arcade_sparks_in_lore_and_atlas():
    lore_text = LORE_PATH.read_text(encoding="utf-8")
    atlas_text = ATLAS_PATH.read_text(encoding="utf-8")

    # Positive confirmation of prohibitions
    negative_markers = [
        "zero glowing eye sparks",
        "zero laser pupils",
        "zero electric blue lightning arcs",
        "zero flaming magical runes",
        "zero-glow rule",
    ]
    for marker in negative_markers:
        assert marker in lore_text.lower(), f"Missing required negative invariant: {marker}"

    # Fuzzing check: ensure no affirmative arcade effects exist
    corrupted_claims = [
        "laser pupils activate",
        "eyes glowing blue",
        "lightning arcs around his sword",
        "flaming runes ignite his armor",
    ]
    for claim in corrupted_claims:
        assert claim not in lore_text.lower(), f"Detected forbidden arcade trope in lore: {claim}"
        assert claim not in atlas_text.lower(), f"Detected forbidden arcade trope in atlas: {claim}"


def test_topological_cardinal_consistency():
    atlas_text = ATLAS_PATH.read_text(encoding="utf-8")

    # Geographical constraints:
    # New Terra -> North
    # Crossroads -> Southern Gorge
    # Black Fog -> South of Crossroads
    # Evergreen -> East
    # House Cross -> West
    # Sunken Lake Kingdom -> South (Zones 5-10)

    assert "[ NORTH: THE CIVILIZED REALM ]" in atlas_text
    assert "Imperial Capital: New Terra" in atlas_text
    assert "[ SOUTHERN GORGE: CROSSROADS ]" in atlas_text
    assert "[ EAST: EVERGREEN ]" in atlas_text
    assert "[ WEST: HOUSE CROSS ]" in atlas_text
    assert "[ SOUTH: THE MONSTER WORLD ]" in atlas_text
    assert "Sunken Abyssal Lake Kingdom" in atlas_text


def test_shadow_squad_composition_completeness():
    atlas_text = ATLAS_PATH.read_text(encoding="utf-8")

    required_members = {
        "Godhand": "mechanical traps",
        "Body Bag": "muscular enforcer",
        "Old Girl": "veteran sniper",
        "Skull": "espionage",
        "Burnout": "alchemical sapper",
    }
    for name, role in required_members.items():
        assert name in atlas_text, f"Missing Shadow Squad member: {name}"
        assert role in atlas_text.lower(), f"Missing role description for {name}: {role}"


def test_zero_cyrillic_in_adversarial_stress_script():
    script_bytes = Path(__file__).resolve().read_bytes()
    non_ascii = [b for b in script_bytes if b >= 128]
    assert len(non_ascii) == 0, f"Found {len(non_ascii)} non-ASCII bytes in stress script"
