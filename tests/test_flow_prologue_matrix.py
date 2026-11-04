"""Unit and architectural tests for the Prologue Micro-Shot Specification Matrix (R1 & R2).

Verifies:
1. 18 discrete micro-shots (MS-01A to MS-07C) covering Frames 001 to 032.
2. Micro-shot duration scaling (1.5s to 3.0s per shot; total duration ~41.0s).
3. Zero banned quality boosters across all positive prompts.
4. Rigid face-lock and webcam gaze invariants for Streamer Ash across all streamer scenes.
5. Strict visual domain segregation for Knight Lucas (2D tactical UI card vs Arcane cinematic 3D).
6. Presence and non-trivial length of the publication-grade guide and spec matrix.
"""

from pathlib import Path
from src.flow_prompt_library import (
    BANNED_QUALITY_BOOSTERS,
    PROLOGUE_MICRO_SHOTS,
    compose_flow_micro_shot_payload,
    get_micro_shot_by_id,
    get_prologue_micro_shots,
    validate_prologue_matrix,
)


def test_prologue_micro_shots_count_and_ids():
    """Verify exactly 18 micro-shots with canonical sequential IDs."""
    shots = get_prologue_micro_shots()
    assert len(shots) == 18

    expected_ids = [
        "MS-01A", "MS-01B", "MS-01C",
        "MS-02A", "MS-02B",
        "MS-03A", "MS-03B",
        "MS-04A", "MS-04B", "MS-04C",
        "MS-05A", "MS-05B", "MS-05C",
        "MS-06A", "MS-06B",
        "MS-07A", "MS-07B", "MS-07C",
    ]
    actual_ids = [s.id for s in shots]
    assert actual_ids == expected_ids


def test_prologue_micro_shots_duration_bounds():
    """Verify each micro-shot is clamped between 1.5s and 3.0s, and total duration is ~41.0s."""
    shots = get_prologue_micro_shots()
    total_sec = sum(s.duration_sec for s in shots)

    for shot in shots:
        assert 1.5 <= shot.duration_sec <= 3.0, f"{shot.id} duration {shot.duration_sec}s out of bounds"

    assert 38.0 <= total_sec <= 45.0
    assert round(total_sec, 1) == 41.0


def test_prologue_matrix_validation_passes():
    """Verify the automated architectural validator returns valid with zero errors."""
    res = validate_prologue_matrix(PROLOGUE_MICRO_SHOTS)
    assert res["valid"] is True
    assert res["errors"] == []
    assert res["total_shots"] == 18
    assert res["streamer_shot_count"] == 9
    assert res["lucas_shot_count"] == 5


def test_streamer_face_lock_and_webcam_gaze_invariants():
    """Verify all 9 streamer shots strictly mandate face and gaze lock with zero head turning."""
    streamer_shot_ids = [
        "MS-01B", "MS-01C", "MS-02B", "MS-03B",
        "MS-04A", "MS-04B", "MS-04C", "MS-05A", "MS-05C",
    ]

    for shot_id in streamer_shot_ids:
        shot = get_micro_shot_by_id(shot_id)
        assert shot is not None
        gaze = shot.gaze_lock.lower()
        neg = shot.negative_prompt.lower()

        # Must mention locked face/gaze/position
        assert any(term in gaze for term in ("locked", "gaze", "eyes", "facing")), (
            f"Shot {shot_id} missing face/gaze lock: {shot.gaze_lock}"
        )
        # Negative prompt must forbid turning head away
        assert "turning head" in neg or "head rotation" in neg, (
            f"Shot {shot_id} negative prompt missing head turn restriction"
        )


def test_lucas_dual_style_segregation():
    """Verify strict segregation: 2D tactical card on monitor vs Fortiche Arcane cinematic 3D."""
    # Domain 1: 2D Tactical Card on monitor
    card_shot = get_micro_shot_by_id("MS-06A")
    assert card_shot is not None
    assert "DOMAIN 1" in card_shot.style_domain
    assert "2D Tactical" in card_shot.style_domain
    assert "2D tactical RPG" in card_shot.subject
    assert "3D CGI impasto" in card_shot.negative_prompt

    # Domain 2: Arcane 3D / Void
    cinematic_shot_ids = ["MS-06B", "MS-07A", "MS-07B", "MS-07C"]
    for sid in cinematic_shot_ids:
        shot = get_micro_shot_by_id(sid)
        assert shot is not None
        assert "DOMAIN 2" in shot.style_domain
        assert "Arcane" in shot.style_domain


def test_zero_banned_quality_boosters():
    """Verify that none of the 13 banned quality boosters exist in any positive prompt."""
    shots = get_prologue_micro_shots()
    for shot in shots:
        prompt = shot.compose_positive_prompt().lower()
        for booster in BANNED_QUALITY_BOOSTERS:
            assert booster.lower() not in prompt, f"Banned booster '{booster}' found in {shot.id}"


def test_payload_composition():
    """Verify compose_flow_micro_shot_payload outputs valid JSON schema structure."""
    shot = get_micro_shot_by_id("MS-04A")
    assert shot is not None
    payload = compose_flow_micro_shot_payload(shot, aspect="16:9", model="veo_3_1_extension_lite")
    assert payload["micro_shot_id"] == "MS-04A"
    assert payload["aspect_ratio"] == "16:9"
    assert payload["model"] == "veo_3_1_extension_lite"
    assert "@Ash_Streamer" in payload["reference_bindings"]
    assert "FOXY 300,000 KRW" in payload["positive_prompt"]


def test_guide_and_spec_documents_exist_and_non_empty():
    """Verify publication-grade guide and micro-shot spec files exist and exceed minimum line thresholds."""
    guide_out = Path("output/flow_community_tools_guide.md")
    guide_doc = Path("docs/flow_community_tools_guide.md")
    spec_matrix = Path("output/prologue_microshot_prompt_matrix.md")

    assert guide_out.exists() and guide_out.stat().st_size > 10000
    assert guide_doc.exists() and guide_doc.stat().st_size > 10000
    assert spec_matrix.exists() and spec_matrix.stat().st_size > 15000
