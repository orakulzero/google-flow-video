"""
tests/test_ttd_m2_challenger_stress.py
Empirical stress test suite authored by m2_challenger_ttd_2.
Validates 5 storyboard templates, custom parameter overrides, fuzzy slug lookup,
pilot storyboard assembly, JSON roundtrip, validation oracles, and zero Cyrillic hygiene.
"""
from __future__ import annotations

import json
from pathlib import Path
import re
import pytest

from src.flow_bridge import FlowEducationalProject, FlowScene, FlowStoryboard
import src.ttd_storyboard as ttd_sb


def test_empirical_all_5_templates_custom_overrides() -> None:
    """Stress-test build_scene parameter overrides across all 5 storyboard templates."""
    templates = [
        ttd_sb.FortressAtmosphereTemplate(),
        ttd_sb.TacticalCommandTemplate(),
        ttd_sb.VanguardDefenseTemplate(),
        ttd_sb.SniperAwakeningTemplate(),
        ttd_sb.BossShowdownTemplate(),
    ]

    for idx, tmpl in enumerate(templates, start=1):
        custom_dur = 11.25 + idx
        custom_cam = f"extreme test camera dynamic motion vector #{idx}"
        custom_persona = "voice_y0joebp3bwta"
        custom_style = f"urgent battle command phase {idx}"
        custom_act = f"Custom action directive executing stress condition {idx} on ramparts."
        custom_narr = f"\u0422\u0435\u0441\u0442\u043e\u0432\u0430\u044f \u0440\u0435\u043f\u043b\u0438\u043a\u0430 {idx}."
        custom_tts = f"\u0422\u0435\u0441\u0442+\u043e\u0432\u0430\u044f \u0440\u0435\u043f\u043b+\u0438\u043a\u0430 {idx}."

        sc = tmpl.build_scene(
            scene_id=f"sc_stress_{idx}",
            scene_number=idx,
            duration_sec=custom_dur,
            camera_motion=custom_cam,
            voice_persona=custom_persona,
            voice_style=custom_style,
            custom_action=custom_act,
            custom_narration=custom_narr,
            custom_tts_narration=custom_tts,
        )

        assert isinstance(sc, FlowScene), f"Template {tmpl.template_id} must return FlowScene"
        assert sc.duration_sec == custom_dur
        assert sc.camera_motion == custom_cam
        assert sc.voice_persona == custom_persona
        assert sc.voice_style == custom_style
        assert sc.narration_text == custom_narr
        assert sc.tts_narration_text == custom_tts
        assert custom_act in sc.visual_prompt
        assert custom_cam in sc.visual_prompt
        assert sc.native_veo_audio is True
        assert sc.veo_audio_prompt is not None
        assert custom_persona in sc.veo_audio_prompt
        assert custom_style in sc.veo_audio_prompt

        sb = FlowStoryboard(
            project_id=f"sb_stress_{idx}",
            topic=f"Stress Test Storyboard {idx}",
            scenes=[sc],
        )
        assert ttd_sb.validate_storyboard(sb) is True
        assert ttd_sb.validate_storyboard(sb, raise_on_error=True) is True


def test_empirical_get_storyboard_template_slug_variants() -> None:
    """Verify exact, uppercase, hyphenated, and fuzzy template lookup."""
    expected_classes = {
        "fortress_atmosphere": ttd_sb.FortressAtmosphereTemplate,
        "tactical_command": ttd_sb.TacticalCommandTemplate,
        "vanguard_defense": ttd_sb.VanguardDefenseTemplate,
        "sniper_awakening": ttd_sb.SniperAwakeningTemplate,
        "boss_showdown": ttd_sb.BossShowdownTemplate,
    }

    # 1. Exact slugs
    for slug, cls in expected_classes.items():
        t = ttd_sb.get_storyboard_template(slug)
        assert isinstance(t, cls)

    # 2. Uppercase and mixed case
    for slug, cls in expected_classes.items():
        t_upper = ttd_sb.get_storyboard_template(slug.upper())
        assert isinstance(t_upper, cls)

    # 3. Hyphenated variations
    for slug, cls in expected_classes.items():
        hyphen_slug = slug.replace("_", "-")
        t_hyphen = ttd_sb.get_storyboard_template(hyphen_slug)
        assert isinstance(t_hyphen, cls)

    # 4. Whitespace and mixed punctuation
    for slug, cls in expected_classes.items():
        padded_slug = f"  \t{slug.replace('_', '-')}\n  "
        t_padded = ttd_sb.get_storyboard_template(padded_slug)
        assert isinstance(t_padded, cls)

    # 5. Fuzzy partial substrings
    fuzzy_map = {
        "fortress": ttd_sb.FortressAtmosphereTemplate,
        "atmosphere": ttd_sb.FortressAtmosphereTemplate,
        "command": ttd_sb.TacticalCommandTemplate,
        "tactical": ttd_sb.TacticalCommandTemplate,
        "vanguard": ttd_sb.VanguardDefenseTemplate,
        "defense": ttd_sb.VanguardDefenseTemplate,
        "sniper": ttd_sb.SniperAwakeningTemplate,
        "awakening": ttd_sb.SniperAwakeningTemplate,
        "boss": ttd_sb.BossShowdownTemplate,
        "showdown": ttd_sb.BossShowdownTemplate,
    }
    for sub, cls in fuzzy_map.items():
        assert isinstance(ttd_sb.get_storyboard_template(sub), cls)

    # 6. Invalid non-empty slug raises KeyError
    with pytest.raises(KeyError):
        ttd_sb.get_storyboard_template("non_existent_archetype_xyz")
    with pytest.raises(KeyError):
        ttd_sb.get_storyboard_template("invalid_template_slug")
    with pytest.raises(KeyError):
        ttd_sb.get_storyboard_template("random_text_123")

    # 7. Note empirical Challenger finding: empty string matches the first registry entry
    # because '' in key is True for any string key in Python dict.
    fallback = ttd_sb.get_storyboard_template("")
    assert isinstance(fallback, ttd_sb.FortressAtmosphereTemplate)


def test_empirical_build_ttd_pilot_storyboard_structure_and_anchors() -> None:
    """Verify 5-scene pilot storyboard, ~37.5s duration, anchors, and include_boss flag."""
    pilot = ttd_sb.build_ttd_pilot_storyboard(include_boss=True)
    assert isinstance(pilot, FlowStoryboard)
    assert isinstance(pilot, FlowEducationalProject)
    assert len(pilot.scenes) == 5

    total_dur = sum(s.duration_sec for s in pilot.scenes)
    assert abs(total_dur - 37.5) < 1e-4

    sc1, sc2, sc3, sc4, sc5 = pilot.scenes
    assert sc1.duration_sec == 7.5
    assert sc2.duration_sec == 7.0
    assert sc3.duration_sec == 7.0
    assert sc4.duration_sec == 7.5
    assert sc5.duration_sec == 8.5

    # Check sequential scene numbers and IDs
    for idx, sc in enumerate(pilot.scenes, start=1):
        assert sc.scene_number == idx
        assert sc.scene_id.startswith("sc_crossroads_")

    # Check character and monster anchors in prompts
    assert any(tok in sc2.visual_prompt for tok in ["Ash", "Bornhater", "signet ring"])
    assert any(tok in sc3.visual_prompt for tok in ["Lucas", "shield", "tower shield"])
    assert any(tok in sc3.visual_prompt for tok in ["gargoyle", "monster", "crawler"])
    assert any(tok in sc4.visual_prompt for tok in ["Lily", "arrow", "bodkin", "bow"])
    assert any(tok in sc5.visual_prompt for tok in ["Living Armor", "boss", "greatsword"])

    # Strict voice persona lock verification across all 5 scenes
    for sc in pilot.scenes:
        assert sc.voice_persona == "voice_y0joebp3bwta"
        assert sc.native_veo_audio is True
        assert sc.veo_audio_prompt and "voice_y0joebp3bwta" in sc.veo_audio_prompt

    # Test include_boss=False generates 4 scenes (29.0s)
    pilot_4sc = ttd_sb.build_ttd_pilot_storyboard(include_boss=False)
    assert len(pilot_4sc.scenes) == 4
    assert abs(sum(s.duration_sec for s in pilot_4sc.scenes) - 29.0) < 1e-4
    for idx, sc in enumerate(pilot_4sc.scenes, start=1):
        assert sc.scene_number == idx
        assert sc.voice_persona == "voice_y0joebp3bwta"
    assert ttd_sb.validate_storyboard(pilot_4sc, raise_on_error=True) is True


def test_empirical_source_hygiene_zero_literal_cyrillic() -> None:
    """Verify zero literal Cyrillic characters exist across all Python files in src/ and tests/."""
    base_dirs = [Path("src"), Path("tests")]
    cyrillic_pattern = re.compile(r"[\u0400-\u04FF]")
    violations = []

    for base in base_dirs:
        for py_path in base.rglob("*.py"):
            text = py_path.read_text(encoding="utf-8")
            matches = list(cyrillic_pattern.finditer(text))
            if matches:
                violations.append((str(py_path), len(matches), matches[0].start()))

    assert not violations, f"Literal Cyrillic characters found in Python files: {violations}"


def test_empirical_storyboard_serialization_roundtrip_and_validation(tmp_path: Path) -> None:
    """Verify JSON export/load roundtrip, file handling, and negative validation oracles."""
    pilot = ttd_sb.build_ttd_pilot_storyboard()
    json_path = tmp_path / "roundtrip_pilot.json"

    # Export to disk and string
    json_str = ttd_sb.export_storyboard_to_json(pilot, path=json_path)
    assert not re.search(r"[\u0400-\u04FF]", json_str), "export_storyboard_to_json emitted literal Cyrillic characters"
    assert all(ord(c) < 128 for c in json_str), "Exported JSON must be pure 7-bit ASCII"

    disk_str = json_path.read_text(encoding="utf-8")
    assert not re.search(r"[\u0400-\u04FF]", disk_str), "Exported JSON file on disk contains literal Cyrillic characters"
    assert all(ord(c) < 128 for c in disk_str), "Exported JSON file on disk must be pure 7-bit ASCII"

    loaded_from_disk = ttd_sb.load_storyboard_from_json(json_path)
    loaded_from_str = ttd_sb.load_storyboard_from_json(json_str)

    assert loaded_from_disk == pilot
    assert loaded_from_str == pilot

    # Non-existent file paths (Path and string)
    with pytest.raises(FileNotFoundError):
        ttd_sb.load_storyboard_from_json(tmp_path / "does_not_exist.json")

    with pytest.raises(FileNotFoundError):
        ttd_sb.load_storyboard_from_json("missing_dir/file.json")

    with pytest.raises(FileNotFoundError):
        ttd_sb.load_storyboard_from_json("missing_storyboard_file.json")

    # Non-dictionary JSON payloads
    with pytest.raises(ValueError, match="dictionary"):
        ttd_sb.load_storyboard_from_json("[1, 2, 3]")

    with pytest.raises(ValueError, match="dictionary"):
        ttd_sb.load_storyboard_from_json("12345")

    with pytest.raises(ValueError, match="dictionary"):
        ttd_sb.load_storyboard_from_json("true")

    # Positive validation checks
    assert ttd_sb.validate_storyboard(pilot) is True
    assert ttd_sb.validate_storyboard(pilot, raise_on_error=True) is True

    # Negative validation checks
    assert ttd_sb.validate_storyboard(None) is False
    assert ttd_sb.validate_storyboard("not_a_storyboard") is False
    with pytest.raises(ValueError, match="FlowStoryboard"):
        ttd_sb.validate_storyboard(None, raise_on_error=True)

    corrupt_dict = pilot.to_dict()
    corrupt_dict["project_id"] = "   "
    assert ttd_sb.validate_storyboard(FlowStoryboard.from_dict(corrupt_dict)) is False
    with pytest.raises(ValueError, match="project_id"):
        ttd_sb.validate_storyboard(FlowStoryboard.from_dict(corrupt_dict), raise_on_error=True)

    corrupt_dict = pilot.to_dict()
    corrupt_dict["scenes"] = []
    assert ttd_sb.validate_storyboard(FlowStoryboard.from_dict(corrupt_dict)) is False
    with pytest.raises(ValueError, match="scenes"):
        ttd_sb.validate_storyboard(FlowStoryboard.from_dict(corrupt_dict), raise_on_error=True)

    corrupt_dict = pilot.to_dict()
    corrupt_dict["scenes"][0]["duration_sec"] = -5.0
    assert ttd_sb.validate_storyboard(FlowStoryboard.from_dict(corrupt_dict)) is False
    with pytest.raises(ValueError, match="duration_sec"):
        ttd_sb.validate_storyboard(FlowStoryboard.from_dict(corrupt_dict), raise_on_error=True)

    corrupt_dict = pilot.to_dict()
    corrupt_dict["scenes"][0]["duration_sec"] = 0.0
    assert ttd_sb.validate_storyboard(FlowStoryboard.from_dict(corrupt_dict)) is False
    with pytest.raises(ValueError, match="duration_sec"):
        ttd_sb.validate_storyboard(FlowStoryboard.from_dict(corrupt_dict), raise_on_error=True)

    corrupt_dict = pilot.to_dict()
    corrupt_dict["scenes"][0]["visual_prompt"] = ""
    assert ttd_sb.validate_storyboard(FlowStoryboard.from_dict(corrupt_dict)) is False
    with pytest.raises(ValueError, match="visual_prompt"):
        ttd_sb.validate_storyboard(FlowStoryboard.from_dict(corrupt_dict), raise_on_error=True)

    corrupt_dict = pilot.to_dict()
    corrupt_dict["scenes"][0]["voice_persona"] = "unauthorized_voice"
    assert ttd_sb.validate_storyboard(FlowStoryboard.from_dict(corrupt_dict)) is False
    with pytest.raises(ValueError, match="voice_persona"):
        ttd_sb.validate_storyboard(FlowStoryboard.from_dict(corrupt_dict), raise_on_error=True)


def test_empirical_6layer_prompt_pipeline_and_lighting_permutations() -> None:
    """Stress-test 6-layer prompt generator across diverse lighting models and layer overrides."""
    lighting_presets = [
        ttd_sb.LIGHTING_ROARING_TORCHLIGHT,
        ttd_sb.LIGHTING_BLOOD_MOON_VOLUMETRIC,
        ttd_sb.LIGHTING_ARCANE_CYAN_DISPATCH,
        ttd_sb.LIGHTING_WITCH_FIRE_CHIAROSCURO,
        ttd_sb.LIGHTING_STORMY_TEMPEST,
        "custom hyper-stylized volumetric chiaroscuro with pulsing neon runes",
    ]

    for idx, light in enumerate(lighting_presets, start=1):
        cfg = ttd_sb.Prompt6LayerConfig(
            camera_motion=f"crane overhead orbital vector {idx}",
            camera_framing="fluid dynamic steadicam",
            focal_depth="macro depth-of-field",
            lighting_model=light,
            color_tokens=["pitch_amber", "arterial_crimson", "arcane_cyan"],
            environment_id="crossroads_fortress",
            environment_zone="battlements",
            characters=["ash_bornhater", "archer_lily"],
            character_phases={"archer_lily": "sniper"},
            monsters=["black_scaled_gargoyle"],
            action=f"Test action directive sequence #{idx} executing tactical convergence.",
            motion_dynamics=ttd_sb.MOTION_TORRENTIAL_RAIN,
            timecoded_actions=[
                {"window": "0-2s", "action": "Defenders assume positions."},
                {"window": "2-4s", "action": "Monsters breach outer ramparts."},
            ],
            composition_and_style="8k cinematic anime render, sharp focal details",
            narration_text=f"\u0422\u0435\u0441\u0442\u043e\u0432\u0430\u044f \u043d\u0430\u0440\u0440\u0430\u0446\u0438\u044f #{idx}",
            voice_persona="voice_y0joebp3bwta",
            voice_style="authoritative commander",
            sound_effects="Resonant clang of steel shields",
            ambient_audio="Nocturnal thunderstorm",
        )

        visual_prompt = ttd_sb.build_6layer_visual_prompt(cfg)
        audio_prompt = ttd_sb.build_veo31_native_audio_prompt(cfg, visual_prompt=visual_prompt)
        vis_p, aud_p, neg_p = ttd_sb.build_ttd_flow_prompt(cfg)

        assert visual_prompt == vis_p
        assert audio_prompt == aud_p
        assert "crane overhead orbital vector" in visual_prompt
        assert "Fortress of Crossroads" in visual_prompt or "Crossroads" in visual_prompt
        assert "Ash Bornhater" in visual_prompt
        assert "Archer Lily" in visual_prompt
        assert "black_scaled_gargoyle" in visual_prompt or "gargoyle" in visual_prompt.lower()
        assert "Timeline: [0-2s] Defenders assume positions. [2-4s] Monsters breach outer ramparts." in visual_prompt
        assert "voice_y0joebp3bwta" in audio_prompt
        assert "Resonant clang of steel shields" in audio_prompt
        assert len(neg_p) > 20

        scene = ttd_sb.create_ttd_flow_scene(
            config=cfg,
            scene_id=f"sc_test_layer_{idx}",
            scene_number=idx,
            title=f"Scene Layer Test {idx}",
            duration_sec=6.5,
        )
        assert isinstance(scene, FlowScene)
        assert scene.duration_sec == 6.5
        assert scene.voice_persona == "voice_y0joebp3bwta"
        assert scene.native_veo_audio is True
