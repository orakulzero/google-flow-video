"""
scripts/empirical_ttd_stress_challenger2.py
Empirical stress-testing and contract verification suite for src/ttd_lore_bible.py.
Part 1 of 2: Contract verification, Cyrillic audit, and JSON serialization.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

REPO_ROOT = Path("e:/ANTIGRAVITY/flow_video_testbench").resolve()
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import src.ttd_lore_bible as ttd_bible


def test_contracts() -> Dict[str, Any]:
    results = {}
    
    # 1. Prince Ash Bornhater
    ash = ttd_bible.get_character("ash_bornhater")
    ash_tokens = " ".join(ash.visual_anchors + ash.costume_tokens + ash.signature_gear + [ash.master_visual_anchor, ash.costume_and_armor, ash.psychological_profile]).lower()
    
    results["ash_name"] = ash.name_en == "Prince Ash Bornhater"
    results["ash_cold_persona"] = any(k in ash.psychological_profile.lower() or k in " ".join(ash.personality_traits).lower() for k in ["calculating", "cold", "ruthless"])
    results["ash_signet_ring"] = "signet ring" in ash_tokens or "signet" in ash_tokens
    results["ash_trenchcoat"] = any(k in ash_tokens for k in ["greatcoat", "trench coat", "cloak"])
    results["ash_visual_tokens"] = all(k in ash_tokens for k in ["black hair", "eye circles", "gorget"])
    results["ash_voice"] = ash.voice_persona == "voice_y0joebp3bwta"

    # 2. Knight Lucas
    lucas = ttd_bible.get_character("knight_lucas")
    lucas_tokens = " ".join(lucas.visual_anchors + lucas.costume_tokens + lucas.signature_gear + [lucas.master_visual_anchor, lucas.costume_and_armor, lucas.psychological_profile]).lower()
    
    results["lucas_name"] = lucas.name_en == "Knight Lucas"
    results["lucas_shield_knight"] = "shield" in lucas_tokens and "knight" in lucas.archetype.lower()
    results["lucas_plate_armor"] = "plate" in lucas_tokens
    results["lucas_tower_shield"] = "tower shield" in lucas_tokens
    results["lucas_broadsword"] = "broadsword" in lucas_tokens or "bastard sword" in lucas_tokens
    results["lucas_chivalric_guardian"] = any(k in lucas_tokens for k in ["guardian", "defensive", "honor", "living shield"])

    # 3. Archer Lily
    lily = ttd_bible.get_character("archer_lily")
    results["lily_name"] = lily.name_en == "Archer Lily"
    results["lily_recruit_phase"] = "recruit" in lily.phases
    results["lily_sniper_phase"] = "sniper" in lily.phases
    results["lily_composite_bow"] = any("composite" in g.lower() and "bow" in g.lower() for g in lily.weapons_and_artifacts + lily.signature_gear)
    
    # Lily psychological profile type check
    results["lily_psychological_profile_type_is_str"] = isinstance(lily.psychological_profile, str)
    lily_psy_str = lily.psychological_profile if isinstance(lily.psychological_profile, str) else " ".join(lily.psychological_profile)
    
    # Transition trigger
    results["lily_transition_trigger"] = (
        "awakening" in lily_psy_str.lower() or
        "awakening" in lily.phases["sniper"].description.lower() or
        "mental grounding" in lily.phases["sniper"].description.lower()
    )

    # 4. First Wave Bestiary (5 species)
    bestiary = ttd_bible.FIRST_WAVE_BESTIARY
    required_species = [
        "black_scaled_gargoyle",
        "chitinous_crawler",
        "decayed_ghoul",
        "siege_ogre_vanguard",
        "living_armor_vanguard",
    ]
    results["bestiary_5_species_present"] = all(s in bestiary for s in required_species)
    results["bestiary_boss_tier"] = "boss" in bestiary["living_armor_vanguard"].tier.lower()
    results["bestiary_threat_ratings"] = all(bool(spec.tier) for spec in bestiary.values())
    results["bestiary_visual_anchors"] = all(len(spec.visual_anchors) >= 3 for spec in bestiary.values())

    # 5. Crossroads Fortress
    fort = ttd_bible.CROSSROADS_FORTRESS
    fort_text = " ".join(fort.architecture_anchors + fort.atmosphere_anchors + [fort.architecture, fort.weather_and_atmosphere, fort.master_visual_anchor]).lower()
    results["fortress_granite_citadel"] = "granite" in fort_text and "citadel" in fort_text
    results["fortress_heavy_rain"] = "rain" in fort_text
    results["fortress_braziers"] = "brazier" in fort_text
    results["fortress_black_fog"] = "black fog" in fort_text

    # 6. Color palette (10 tokens)
    palette = ttd_bible.COLOR_PALETTE
    results["palette_count_10"] = len(palette) == 10
    hex_re = re.compile(r"^#[0-9A-Fa-f]{6}$")
    palette_valid = True
    palette_rgb_match = True
    for tid, tok in palette.items():
        if not hex_re.match(tok.hex_code):
            palette_valid = False
        calc_rgb = (int(tok.hex_code[1:3], 16), int(tok.hex_code[3:5], 16), int(tok.hex_code[5:7], 16))
        if calc_rgb != tok.rgb:
            palette_rgb_match = False
    results["palette_hex_format_valid"] = palette_valid
    results["palette_rgb_match"] = palette_rgb_match

    # 7. Master negative prompt
    neg = ttd_bible.TTD_MASTER_NEGATIVE_PROMPT
    results["negative_prompt_non_empty"] = bool(neg and len(neg) > 20)
    results["negative_suppresses_cartoon"] = any(k in neg.lower() for k in ["cartoon", "plastic skin", "3d cgi doll", "chibi"])

    return results


def test_source_hygiene() -> Dict[str, Any]:
    cyrillic_re = re.compile(r"[\u0400-\u04FF]")
    src_hits = []
    test_hits = []

    for p in Path(REPO_ROOT / "src").rglob("*.py"):
        txt = p.read_text(encoding="utf-8")
        matches = cyrillic_re.findall(txt)
        if matches:
            src_hits.append({"file": str(p.relative_to(REPO_ROOT)), "count": len(matches), "chars": list(set(matches))})

    for p in Path(REPO_ROOT / "tests").rglob("*.py"):
        txt = p.read_text(encoding="utf-8")
        matches = cyrillic_re.findall(txt)
        if matches:
            test_hits.append({"file": str(p.relative_to(REPO_ROOT)), "count": len(matches), "chars": list(set(matches))})

    return {
        "src_cyrillic_hits": src_hits,
        "src_cyrillic_count": sum(h["count"] for h in src_hits),
        "tests_cyrillic_hits": test_hits,
        "tests_cyrillic_count": sum(h["count"] for h in test_hits),
        "total_cyrillic_zero": (len(src_hits) == 0 and len(test_hits) == 0),
    }


def test_prompt_synthesis_stress() -> Dict[str, Any]:
    stress_results = {}

    # Check for build_ttd_scene_prompt alias
    has_ttd_prompt = hasattr(ttd_bible, "build_ttd_scene_prompt")
    has_veo_prompt = hasattr(ttd_bible, "build_veo_scene_prompt")
    stress_results["has_build_ttd_scene_prompt"] = has_ttd_prompt
    stress_results["has_build_veo_scene_prompt"] = has_veo_prompt

    # Target prompt builder
    func = getattr(ttd_bible, "build_ttd_scene_prompt", getattr(ttd_bible, "build_veo_scene_prompt", None))
    if not func:
        stress_results["prompt_function_available"] = False
        return stress_results
    stress_results["prompt_function_available"] = True

    # Case 1: Standard nominal input
    p_norm = func(
        camera_motion="slow push-in",
        action="Ash looks over the ramparts",
        characters=["ash_bornhater"],
        character_phases={"ash_bornhater": "recruit"}, # Ash has no recruit phase -> should fallback to master
        monsters=["black_scaled_gargoyle"],
    )
    stress_results["nominal_prompt_len"] = len(p_norm)
    stress_results["nominal_contains_ash"] = "Prince Ash Bornhater" in p_norm
    stress_results["nominal_contains_gargoyle"] = "Gargoyle" in p_norm

    # Case 2: Empty camera motion & empty action
    try:
        p_empty = func(camera_motion="", action="")
        stress_results["empty_input_handled"] = True
        stress_results["empty_input_result_non_empty"] = len(p_empty) > 20
    except Exception as e:
        stress_results["empty_input_handled"] = False
        stress_results["empty_input_error"] = str(e)

    # Case 3: Extreme whitespace & punctuation
    try:
        p_space = func(
            camera_motion="   extreme low-angle dutch tilt....   ",
            action="   ...slashing through the horde!....   ",
            lighting="   harsh rim lightning!!!...   ",
            style_suffix="   masterpiece dark anime....   ",
        )
        stress_results["whitespace_handling_clean"] = not p_space.endswith("..")
    except Exception as e:
        stress_results["whitespace_handling_clean"] = False

    # Case 4: Invalid / unknown character ID
    try:
        func(camera_motion="pan", action="run", characters=["nonexistent_hero"])
        stress_results["unknown_character_raises_keyerror"] = False
    except KeyError:
        stress_results["unknown_character_raises_keyerror"] = True
    except Exception as e:
        stress_results["unknown_character_raises_keyerror"] = False
        stress_results["unknown_character_unexpected_err"] = str(e)

    # Case 5: Invalid / unknown monster ID
    try:
        func(camera_motion="pan", action="run", monsters=["godzilla_boss"])
        stress_results["unknown_monster_raises_keyerror"] = False
    except KeyError:
        stress_results["unknown_monster_raises_keyerror"] = True
    except Exception as e:
        stress_results["unknown_monster_raises_keyerror"] = False

    # Case 6: Unknown environment ID
    try:
        p_env = func(camera_motion="pan", action="run", environment="unknown_biome")
        # In ttd_lore_bible.py: get_environment_anchor always returns CROSSROADS_FORTRESS.master_visual_anchor
        stress_results["unknown_env_falls_back_gracefully"] = "Fortress of Crossroads" in p_env
    except Exception as e:
        stress_results["unknown_env_falls_back_gracefully"] = False

    # Case 7: High volume stress (100 character references, 100 monster references)
    try:
        p_huge = func(
            camera_motion="orbital rotation",
            action="grand clash",
            characters=["ash", "lucas", "lily"] * 33,
            monsters=["gargoyle", "crawler", "ghoul", "siege_ogre"] * 25,
        )
        stress_results["high_volume_stress_len"] = len(p_huge)
        stress_results["high_volume_stress_passed"] = len(p_huge) > 10000
    except Exception as e:
        stress_results["high_volume_stress_passed"] = False
        stress_results["high_volume_stress_error"] = str(e)

    # Case 8: Adversarial string injection (SQL, HTML tags, Quotes, Unicode, Null-escapes)
    try:
        adversarial_action = "Ash casts <script>alert(1)</script> and DROP TABLE fortress; \"'\\ \U0001F480 \u2620"
        p_adv = func(camera_motion="dolly zoom", action=adversarial_action)
        stress_results["adversarial_injection_safe"] = adversarial_action.strip().rstrip(".") in p_adv
    except Exception as e:
        stress_results["adversarial_injection_safe"] = False

    # Case 9: Lily dual-phase prompt variations
    p_lily_recruit = func(
        camera_motion="macro close-up",
        action="drawing bowstring with shaking hands",
        characters=["archer_lily"],
        character_phases={"archer_lily": "recruit"},
    )
    p_lily_sniper = func(
        camera_motion="macro close-up",
        action="dead-eye locked on boss core",
        characters=["archer_lily"],
        character_phases={"archer_lily": "sniper"},
    )
    stress_results["lily_recruit_differs_from_sniper"] = p_lily_recruit != p_lily_sniper
    stress_results["lily_recruit_has_recruit_tokens"] = "terror" in p_lily_recruit.lower() or "fear" in p_lily_recruit.lower() or "trembling" in p_lily_recruit.lower()
    stress_results["lily_sniper_has_sniper_tokens"] = "sniper" in p_lily_sniper.lower() or "predator" in p_lily_sniper.lower() or "calm" in p_lily_sniper.lower()

    return stress_results


def test_serialization() -> Dict[str, Any]:
    bible = ttd_bible.get_lore_bible()
    d = bible.to_dict()
    json_bytes = json.dumps(d, ensure_ascii=False)
    parsed = json.loads(json_bytes)
    return {
        "bible_json_serializable": True,
        "bible_json_size_bytes": len(json_bytes),
        "characters_serialized_count": len(parsed["characters"]),
        "bestiary_serialized_count": len(parsed["bestiary"]),
        "palette_serialized_count": len(parsed["color_palette"]),
    }


def main():
    report = {
        "contracts": test_contracts(),
        "source_hygiene": test_source_hygiene(),
        "prompt_synthesis": test_prompt_synthesis_stress(),
        "serialization": test_serialization(),
    }
    print("--- CHALLENGER RESULTS JSON BEGIN ---")
    print(json.dumps(report, indent=2))
    print("--- CHALLENGER RESULTS JSON END ---")


if __name__ == "__main__":
    main()
