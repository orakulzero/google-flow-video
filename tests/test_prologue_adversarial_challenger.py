"""Empirical adversarial challenger verification for Prologue Micro-Shot Matrix (R1 & R2).

Automated verification of:
1. Programmatic matrix validator execution (validate_prologue_matrix -> valid: True, 0 errors).
2. Markdown matrix (output/prologue_microshot_prompt_matrix.md) and Python library parity.
3. Streamer facial stabilization, forward gaze pinning, catchlights, and anti-drift negatives.
4. Lucas dual-style segregation (MS-06A 2D tactical card vs MS-06B/07A-C Arcane 3D void).
"""

import re
from pathlib import Path
import pytest
from src.flow_prompt_library import (
    BANNED_QUALITY_BOOSTERS,
    PROLOGUE_MICRO_SHOTS,
    get_micro_shot_by_id,
    get_prologue_micro_shots,
    validate_prologue_matrix,
)


def test_validator_returns_valid_zero_errors():
    """Verify that validate_prologue_matrix() executes and returns valid: True with 0 errors."""
    res = validate_prologue_matrix()
    assert res["valid"] is True
    assert res["errors"] == []
    assert res["total_shots"] == 18
    assert res["total_duration_sec"] == 41.0
    assert res["streamer_shot_count"] == 9
    assert res["lucas_shot_count"] == 5


def test_markdown_and_python_library_parity():
    """Verify 100% text parity between output/prologue_microshot_prompt_matrix.md and PROLOGUE_MICRO_SHOTS."""
    md_file = Path("output/prologue_microshot_prompt_matrix.md")
    assert md_file.exists()
    content = md_file.read_text(encoding="utf-8")

    shots = get_prologue_micro_shots()
    assert len(shots) == 18

    for shot in shots:
        pattern = rf"### Micro-Shot {re.escape(shot.id)}:.*?(?=### Micro-Shot|\n## 3\.|\Z)"
        match = re.search(pattern, content, re.DOTALL)
        assert match is not None, f"Shot {shot.id} missing from markdown specification"
        block = match.group(0)

        pos_match = re.search(r"\*\*Positive Prompt.*?\*\*:\s*```text\s*(.*?)\s*```", block, re.DOTALL)
        neg_match = re.search(r"\*\*Negative Prompt\*\*:\s*```text\s*(.*?)\s*```", block, re.DOTALL)
        assert pos_match is not None, f"Positive prompt missing in {shot.id}"
        assert neg_match is not None, f"Negative prompt missing in {shot.id}"

        pos_md = " ".join(pos_match.group(1).strip().split())
        pos_py = " ".join(shot.compose_positive_prompt().split())
        assert pos_md == pos_py, f"Positive prompt text mismatch in {shot.id}"

        neg_md = " ".join(neg_match.group(1).strip().split())
        neg_py = " ".join(shot.negative_prompt.split())
        assert neg_md == neg_py, f"Negative prompt text mismatch in {shot.id}"


def test_streamer_face_stabilization_and_gaze_lock():
    """Audit streamer shots for forward gaze constraints and anti-gaze-drift negative tokens."""
    streamer_ids = ["MS-01B", "MS-01C", "MS-02B", "MS-03B", "MS-04A", "MS-04B", "MS-04C", "MS-05A", "MS-05C"]
    
    for sid in streamer_ids:
        shot = get_micro_shot_by_id(sid)
        assert shot is not None
        pos = shot.compose_positive_prompt().lower()
        neg = shot.negative_prompt.lower()
        gaze = shot.gaze_lock.lower()

        # Invariant 1: Forward-facing gaze & alignment in gaze lock or positive prompt
        has_forward_gaze = any(
            token in gaze or token in pos
            for token in ["facing", "aligned", "forward", "webcam", "locked", "eye level", "facing front", "eyes"]
        )
        assert has_forward_gaze, f"{sid} lacks forward-facing gaze directive"

        # Invariant 2: Negative prompt bans head turns / gaze drift
        has_anti_drift = any(
            token in neg
            for token in ["turning head", "head rotation", "head twisting", "looking away", "side glance", "wandering eyes", "turning around"]
        )
        assert has_anti_drift, f"{sid} lacks anti-gaze-drift negative tokens"


def test_lucas_domain_separation_and_void_tokens():
    """Audit Lucas shots for 2D tactical card vs Fortiche Arcane 3D void segregation."""
    card_shot = get_micro_shot_by_id("MS-06A")
    assert card_shot is not None
    assert "DOMAIN 1" in card_shot.style_domain
    assert "2D Tactical" in card_shot.style_domain
    card_pos = card_shot.compose_positive_prompt()
    assert "2D tactical RPG" in card_pos
    assert "golden laurel wreath" in card_pos.lower()
    assert "3D CGI impasto" in card_shot.negative_prompt

    cinematic_ids = ["MS-06B", "MS-07A", "MS-07B", "MS-07C"]
    for sid in cinematic_ids:
        shot = get_micro_shot_by_id(sid)
        assert shot is not None
        assert "DOMAIN 2" in shot.style_domain
        assert "Arcane" in shot.style_domain
        # All Domain 2 shots must forbid modern/streamer room elements
        assert any(t in shot.negative_prompt.lower() for t in ["modern room", "streamer", "modern objects", "bright colors"])

    # Verify 2D card is explicitly banned in transition shots
    assert "2D anime card" in get_micro_shot_by_id("MS-06B").negative_prompt
    assert "2D anime card" in get_micro_shot_by_id("MS-07A").negative_prompt

    # MS-07C must explicitly feature pitch-black void tokens
    climax_shot = get_micro_shot_by_id("MS-07C")
    assert climax_shot is not None
    climax_pos = climax_shot.compose_positive_prompt()
    assert "#000000" in climax_pos
    assert "pitch-black void" in climax_pos.lower()
    assert "25.0" in climax_pos
    assert "pure blackness" in climax_pos.lower()


def test_adversarial_banned_buzzword_oracle():
    """Stress test: verify all 18 positive prompts are cleanly stripped of 13 banned buzzwords."""
    shots = get_prologue_micro_shots()
    for shot in shots:
        pos = shot.compose_positive_prompt().lower()
        for booster in BANNED_QUALITY_BOOSTERS:
            assert not re.search(rf"\b{re.escape(booster)}\b", pos), (
                f"Banned booster '{booster}' detected in {shot.id}"
            )
