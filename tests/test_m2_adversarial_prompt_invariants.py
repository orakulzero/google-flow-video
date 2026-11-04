"""Adversarial stress test suite for Milestone 2 prompt invariants and spark exclusions.

REQ-M2-STRESS-01: Exclusion of glowing eyes, laser pupils, arcade sparks, and blade sparks.
REQ-M2-STRESS-02: Mandatory Lucas character model invariants (hair, skin, scar, zero-sparks).
REQ-M2-STRESS-03: Hex lighting key format, camera angle validity, and negative prompt coverage.
REQ-M2-STRESS-04: Adversarial casing, boundary injection, and validation oracle robustness.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List
import pytest

from src.flow_prompt_library import (
    EP01_CANONICAL_LUCAS_HAIR,
    EP01_CANONICAL_LUCAS_ZERO_SPARKS,
    PROLOGUE_MICRO_SHOTS,
    build_fortiche_arcane_6stage_prompt,
    build_lucas_climax_roaring_prompt,
    load_ep01_shot_matrix,
    validate_ep01_canonical_prompts,
)

HEX_COLOR_REGEX = re.compile(r"^#[0-9A-Fa-f]{6}$")

FORBIDDEN_SPARK_TROPES = (
    "glowing eyes",
    "laser pupils",
    "arcade sparks",
    "magic blade sparks",
    "laser eyes",
    "magical energy arcs",
    "neon blade",
)


def _has_unnegated_forbidden_token(text: str, forbidden_tokens: tuple[str, ...]) -> List[str]:
    """Find any forbidden token that is not explicitly negated by 'zero' or 'strictly zero'."""
    lower_text = text.lower()
    violations = []
    for token in forbidden_tokens:
        matches = [m.start() for m in re.finditer(re.escape(token), lower_text)]
        for start_idx in matches:
            prefix = lower_text[max(0, start_idx - 25):start_idx]
            if not ("zero" in prefix or "strictly zero" in prefix or "without" in prefix or "no " in prefix):
                violations.append(f"Un-negated '{token}' found with prefix '{prefix.strip()}'")
    return violations


def test_no_unnegated_forbidden_spark_tokens_in_shot_matrix_positive_prompts():
    """REQ-M2-STRESS-01: Probe every positive prompt in docs/ttd_ep01_shot_matrix.json for un-negated spark tokens."""
    shots = load_ep01_shot_matrix("docs/ttd_ep01_shot_matrix.json")
    assert len(shots) == 12

    failures = {}
    for shot in shots:
        sid = shot["shot_id"]
        pos = shot["positive_prompt"]
        violations = _has_unnegated_forbidden_token(pos, FORBIDDEN_SPARK_TROPES)
        if violations:
            failures[sid] = violations

    assert not failures, f"Forbidden un-negated spark tropes detected in positive prompts: {failures}"


def test_no_unnegated_forbidden_spark_tokens_in_flow_prompt_library():
    """REQ-M2-STRESS-01: Probe flow_prompt_library generated positive prompts for forbidden tokens."""
    # Test prologue micro-shots
    for shot in PROLOGUE_MICRO_SHOTS:
        pos = shot.compose_positive_prompt()
        violations = _has_unnegated_forbidden_token(pos, FORBIDDEN_SPARK_TROPES)
        assert not violations, f"Shot {shot.id} in PROLOGUE_MICRO_SHOTS has forbidden tokens: {violations}"

    # Test master 6-stage roaring prompt
    roaring_prompt = build_lucas_climax_roaring_prompt(is_video=True)
    pos_roaring = roaring_prompt.compose_positive()
    violations_roaring = _has_unnegated_forbidden_token(pos_roaring, FORBIDDEN_SPARK_TROPES)
    assert not violations_roaring, f"Roaring prompt positive field has forbidden tokens: {violations_roaring}"


def test_shot_matrix_lighting_hex_camera_angles_and_negatives():
    """REQ-M2-STRESS-03: Verify all 12 shots have valid hex colors, camera angles, and negative prompts."""
    shots = load_ep01_shot_matrix("docs/ttd_ep01_shot_matrix.json")
    for shot in shots:
        sid = shot["shot_id"]
        lighting = shot.get("lighting", {})
        assert HEX_COLOR_REGEX.match(lighting.get("key", "")), f"{sid} invalid key light: {lighting.get('key')}"
        assert HEX_COLOR_REGEX.match(lighting.get("rim", "")), f"{sid} invalid rim light: {lighting.get('rim')}"
        assert HEX_COLOR_REGEX.match(lighting.get("ambient", "")), f"{sid} invalid ambient light: {lighting.get('ambient')}"

        camera = shot.get("camera", {})
        angle = camera.get("angle", "")
        assert isinstance(angle, str) and len(angle.strip()) > 3, f"{sid} camera angle missing or too short: {angle}"

        neg = shot.get("negative_prompt", "")
        assert isinstance(neg, str) and len(neg.strip()) >= 20, f"{sid} negative prompt too short: {len(neg)}"


def test_lucas_character_invariants_empirical_audit():
    """REQ-M2-STRESS-02: Stress test every shot featuring Lucas for mandatory character model invariants."""
    shots = load_ep01_shot_matrix("docs/ttd_ep01_shot_matrix.json")
    lucas_shots = [s for s in shots if any("lucas" in c.lower() for c in s.get("characters", []))]
    assert len(lucas_shots) == 5, f"Expected 5 shots featuring Lucas, found {len(lucas_shots)}"

    defects = []
    for s in lucas_shots:
        sid = s["shot_id"]
        pos = s["positive_prompt"].lower()
        neg = s["negative_prompt"].lower()

        # Invariant 1: dirty-blonde hair
        if "dirty-blonde" not in pos:
            defects.append(f"{sid}: Missing canonical hair token 'dirty-blonde'")

        # Invariant 2: weathered tan skin
        if not ("weathered tan" in pos or "weathered bronze-tan" in pos):
            defects.append(f"{sid}: Missing canonical skin token 'weathered tan skin'")

        # Invariant 3: left cheek claw scar
        if not ("left cheek claw scar" in pos or "claw scar on left cheek" in pos):
            defects.append(f"{sid}: Missing canonical facial scar 'left cheek claw scar'")

        # Invariant 4: zero-sparks tokens
        if not any(t in pos for t in ["zero glowing eyes", "zero sparks", "zero floating sparks", "realistic torchlight reflections only"]):
            defects.append(f"{sid}: Missing canonical zero-sparks / natural reflection token in positive prompt")

        # Invariant 5: negative prompt bans glowing eyes and sparks
        if "glowing eyes" not in neg:
            defects.append(f"{sid}: Negative prompt missing 'glowing eyes' ban")
        if "sparks" not in neg:
            defects.append(f"{sid}: Negative prompt missing 'sparks' ban")

    # We record all defects found for reporting
    assert not defects, f"Lucas character invariant defects detected:\n" + "\n".join(defects)
