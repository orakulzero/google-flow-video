"""Adversarial stress testing and empirical challenge of Milestone 1 Atlas & Boundaries.

Validates exact physical dimensions, structural boundaries, geopolitical entities,
byte-for-byte PROJECT.md synchronization, and encoding hygiene.
"""

import hashlib
from pathlib import Path
import re
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = REPO_ROOT / "docs"
ATLAS_PATH = DOCS_DIR / "ttd_world_locations_atlas.md"
LORE_PATH = DOCS_DIR / "ttd_universe_lore_bible.md"
ROOT_PROJECT = REPO_ROOT / "PROJECT.md"
TEAMWORK_PROJECT = REPO_ROOT / ".agents" / "teamwork" / "PROJECT.md"


def test_project_md_byte_for_byte_synchronization():
    assert ROOT_PROJECT.exists(), "Root PROJECT.md missing"
    assert TEAMWORK_PROJECT.exists(), ".agents/teamwork/PROJECT.md missing"

    root_bytes = ROOT_PROJECT.read_bytes()
    teamwork_bytes = TEAMWORK_PROJECT.read_bytes()

    assert len(root_bytes) == len(teamwork_bytes), (
        f"Size mismatch: root={len(root_bytes)} vs teamwork={len(teamwork_bytes)}"
    )

    root_sha = hashlib.sha256(root_bytes).hexdigest()
    teamwork_sha = hashlib.sha256(teamwork_bytes).hexdigest()
    assert root_sha == teamwork_sha, f"SHA-256 mismatch: {root_sha} vs {teamwork_sha}"
    assert root_bytes == teamwork_bytes, "PROJECT.md files are not identical"


def test_crossroads_fortress_structural_boundaries():
    assert ATLAS_PATH.exists(), "Atlas document missing"
    atlas = ATLAS_PATH.read_text(encoding="utf-8")

    # 1. Outer Wall Dimensions
    assert "30 meters high" in atlas or "30-meter" in atlas
    assert "12 meters thick" in atlas
    assert "20-meter battered base" in atlas
    assert "volcanic basalt" in atlas
    assert "#2B2D31" in atlas

    # 2. Kill-Zone Moat
    assert "50-meter-wide dry kill-zone moat" in atlas or "50-meter-wide" in atlas
    assert "charred wooden stakes" in atlas
    assert "iron caltrops" in atlas
    assert "scorched black" in atlas

    # 3. Layered Gatehouse Defense
    assert "Outer Portcullis" in atlas
    assert "15 cm thickness" in atlas
    assert "Murder Run" in atlas or "murder holes" in atlas
    assert "Inner Iron-Plated Oak Doors" in atlas

    # 4. Command Spire & Dungeon
    assert "Commander's Spire" in atlas or "Command Spire" in atlas
    assert "60 meters above" in atlas
    assert "360-degree" in atlas
    assert "Subterranean Dungeon" in atlas
    assert "dungeon core" in atlas


def test_black_fog_and_miasma_boundaries():
    atlas = ATLAS_PATH.read_text(encoding="utf-8")

    # 1. Boundary distance
    assert "300 meters south" in atlas or "300m" in atlas
    assert "#090A0D" in atlas
    assert "supernatural" in atlas

    # 2. Physics & Supernatural Attributes
    assert "consumes photons" in atlas or "Absolute Light Devouring" in atlas
    assert "Toxicity" in atlas or "hemorrhaging" in atlas
    assert "Scrying" in atlas and "Nullification" in atlas
    assert "zero early-warning radar" in atlas or "zero early-warning" in atlas


def test_new_terra_and_imperial_hierarchy():
    atlas = ATLAS_PATH.read_text(encoding="utf-8")

    assert "New Terra" in atlas
    assert "White Marble & Golden Spires" in atlas or "white marble" in atlas
    assert "Imperial Palace of Dragons" in atlas
    assert "36 recognized royal princes" in atlas or "36 Heirs" in atlas
    assert "penal colony" in atlas or "vulgar, barbaric wasteland" in atlas


def test_sunken_lake_kingdom_and_sleepless_princess():
    atlas = ATLAS_PATH.read_text(encoding="utf-8")

    assert "Sunken Lake Kingdom" in atlas or "Lake Kingdom" in atlas
    assert "Zones 5 through 10" in atlas or "Zones 5-10" in atlas
    assert "perpetual twilight" in atlas
    assert "Curse of Endless Drowning" in atlas
    assert "Sleepless Princess of the Lake" in atlas or "Nameless One" in atlas


def test_evergreen_and_shadow_squad():
    atlas = ATLAS_PATH.read_text(encoding="utf-8")

    # Evergreen
    assert "Evergreen" in atlas
    assert "ironwood World Trees" in atlas
    assert "Sacred Mana Springs" in atlas
    assert "Isolationism" in atlas

    # Shadow Squad
    assert "Shadow Squad" in atlas
    assert "Godhand" in atlas
    assert "Body Bag" in atlas
    assert "Old Girl" in atlas
    assert "Skull" in atlas
    assert "Burnout" in atlas
    assert "penal black-ops" in atlas or "death-row convicts" in atlas
    assert "300-meter dead zone" in atlas


def test_lore_bible_lucas_mechanics_and_negative_invariants():
    assert LORE_PATH.exists(), "Lore bible missing"
    lore = LORE_PATH.read_text(encoding="utf-8")

    # 1. Gamer & Campaign Invariants
    assert "Lee Tae-Seok" in lore
    assert "1,056" in lore or "1056" in lore
    assert "Hell Mode" in lore
    assert "Stage 50" in lore

    # 2. Lucas Unique Mechanics
    assert "Man of Steel" in lore
    assert "1 HP" in lore
    assert "Strike of Will" in lore
    assert "Step of Tenacity" in lore

    # 3. Transmigration & Vessel
    assert "Ash Bornhater Everblack" in lore or "Ash Everblack" in lore
    assert "36th Imperial Prince" in lore
    assert "Stage 0" in lore

    # 4. Adversarial Negative Invariants (Sparks strictly banned)
    assert "Zero glowing eye sparks" in lore or "zero glowing eye sparks" in lore
    assert "zero laser pupils" in lore
    assert "zero electric blue lightning arcs" in lore
    assert "zero flaming magical runes" in lore
    assert "Zero-Glow Rule" in lore


def test_encoding_hygiene_zero_cyrillic_in_test_script():
    test_script_path = Path(__file__).resolve()
    raw_bytes = test_script_path.read_bytes()

    non_ascii_chars = [
        (idx, b, chr(b) if b < 128 else f"\\x{b:02x}")
        for idx, b in enumerate(raw_bytes)
        if b >= 128
    ]
    assert len(non_ascii_chars) == 0, (
        f"Found {len(non_ascii_chars)} non-ASCII bytes in test script: {non_ascii_chars[:10]}"
    )
