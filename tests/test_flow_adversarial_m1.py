"""
tests/test_flow_adversarial_m1.py
Empirical adversarial challenger suite for src/flow_bridge.py
Covers:
1. Strict schema alias verification (FlowStoryboard is FlowEducationalProject)
2. Adversarial garbage injection (root and scene levels)
3. Missing/None/falsy optional fields resilience
4. Mixed scene lists (FlowScene, dict, invalid types)
5. Deep roundtrip idempotence (N-cycle to_dict <-> from_dict)
6. Complex scene mutation and re-serialization
7. JSON wire-format serialization compatibility (json.dumps / json.loads)
8. Multilingual, math, emoji, and quote-heavy payloads
9. Alternative keyword argument calling conventions for from_dict
10. High-volume stress (500 scenes)
"""

import json
import uuid
import pytest
from src.flow_bridge import FlowStoryboard, FlowEducationalProject, FlowScene


class TestFlowBridgeAdversarial:

    def test_01_alias_strict_identity(self):
        """Verify FlowStoryboard is exactly FlowEducationalProject and type checks match."""
        assert FlowStoryboard is FlowEducationalProject
        proj = FlowStoryboard(project_id="test_alias_01", topic="Alias Verification")
        assert isinstance(proj, FlowEducationalProject)
        assert isinstance(proj, FlowStoryboard)
        assert type(proj) is FlowEducationalProject

    def test_02_garbage_injection_root_and_scenes(self):
        """Construct payloads with arbitrary unmodeled keys, malicious keys, and nested junk."""
        garbage_payload = {
            "project_id": "proj_garbage_root",
            "topic": "Garbage Resistance Test",
            "__malicious_injected__": "DROP TABLE projects;",
            "random_int": 999999999,
            "nested_junk": {"a": [1, 2, 3], "b": {"c": "d"}},
            "unsupported_flag": True,
            "scenes": [
                {
                    "scene_id": "sc_junk_1",
                    "scene_number": 1,
                    "title": "Scene with Junk",
                    "narration_text": "Narration text",
                    "visual_prompt": "Visual prompt",
                    "unknown_scene_key": "some_value",
                    "extra_nested_dict": {"foo": "bar"},
                    "unrecognized_bool": False,
                },
                {
                    "scene_id": "sc_junk_2",
                    "scene_number": 2,
                    "title": "Second Scene",
                    "narration_text": "Narration text 2",
                    "visual_prompt": "Visual prompt 2",
                    "__proto__": "prototype pollution simulation",
                }
            ]
        }
        sb = FlowStoryboard.from_dict(garbage_payload)
        assert sb.project_id == "proj_garbage_root"
        assert sb.topic == "Garbage Resistance Test"
        assert len(sb.scenes) == 2
        assert sb.scenes[0].scene_id == "sc_junk_1"
        assert sb.scenes[1].scene_id == "sc_junk_2"
        assert not hasattr(sb, "__malicious_injected__")
        assert not hasattr(sb.scenes[0], "unknown_scene_key")

        # Re-serialization should cleanly exclude the garbage
        exported = sb.to_dict()
        assert "__malicious_injected__" not in exported
        assert "unknown_scene_key" not in exported["scenes"][0]
        assert "nested_junk" not in exported

    def test_03_missing_optional_fields_and_defaults(self):
        """Test minimal/empty payloads, missing project_id, missing topic, missing scenes."""
        # 1. Completely empty dict
        sb_empty = FlowStoryboard.from_dict({})
        assert isinstance(sb_empty.project_id, str) and len(sb_empty.project_id) > 0
        assert sb_empty.project_id.startswith("flow_")
        assert sb_empty.topic == ""
        assert sb_empty.scenes == []
        assert sb_empty.status == "storyboard_ready"
        assert sb_empty.language == "en"

        # 2. None payload
        sb_none = FlowStoryboard.from_dict(None)
        assert isinstance(sb_none.project_id, str)
        assert sb_none.topic == ""

        # 3. Minimal scene dict missing optional scene fields
        minimal_scene_dict = {
            "scene_id": "sc_min_01",
            "scene_number": 1,
            "title": "Minimal Scene",
            "narration_text": "Minimal Narration",
            "visual_prompt": "Minimal Visual",
        }
        sb_minimal = FlowStoryboard.from_dict({
            "project_id": "proj_min",
            "topic": "Minimal",
            "scenes": [minimal_scene_dict]
        })
        sc = sb_minimal.scenes[0]
        assert sc.duration_sec == 5.0
        assert sc.camera_motion == "slow push-in"
        assert sc.voice_persona == "voice_y0joebp3bwta"
        assert sc.timecoded_directives == []
        assert sc.on_screen_bullets == []
        assert sc.diagram_spec is None

        # 4. Scene dict missing even required fields -> from_dict should provide fallbacks
        sparse_scene_dict = {}
        sc_sparse = FlowScene.from_dict(sparse_scene_dict)
        assert sc_sparse.scene_id == "sc_01"
        assert sc_sparse.scene_number == 1
        assert sc_sparse.title == ""
        assert sc_sparse.narration_text == ""
        assert sc_sparse.visual_prompt == ""

    def test_04_mixed_scene_lists_and_filtering(self):
        """Test mixed scene lists: pre-instantiated FlowScene, dicts, and invalid types."""
        scene_obj = FlowScene(
            scene_id="sc_obj_1",
            scene_number=1,
            title="Pre-instantiated Scene Object",
            narration_text="Object narration",
            visual_prompt="Object visual",
            duration_sec=8.5,
        )
        scene_dict = {
            "scene_id": "sc_dict_2",
            "scene_number": 2,
            "title": "Dict Scene",
            "narration_text": "Dict narration",
            "visual_prompt": "Dict visual",
            "duration_sec": 6.0,
        }
        invalid_entries = [
            "invalid_string_scene",
            12345,
            None,
            ["nested_list_scene"],
            {"not_a_scene_no_id": True},
        ]

        payload = {
            "project_id": "proj_mixed",
            "topic": "Mixed Scenes Test",
            "scenes": [scene_obj, scene_dict] + invalid_entries
        }

        sb = FlowStoryboard.from_dict(payload)
        # Invalid entries (string, int, None, list) must be filtered out,
        # dict with no id gets fallback id, valid dict and obj preserved
        valid_scenes = sb.scenes
        assert len(valid_scenes) == 3
        assert valid_scenes[0] is scene_obj
        assert isinstance(valid_scenes[1], FlowScene)
        assert valid_scenes[1].scene_id == "sc_dict_2"
        assert valid_scenes[1].duration_sec == 6.0
        assert isinstance(valid_scenes[2], FlowScene)
        assert valid_scenes[2].scene_id == "sc_01"

    def test_05_deep_nested_roundtrip_idempotence(self):
        """Verify N-cycle roundtrip idempotence: to_dict -> from_dict -> to_dict -> from_dict."""
        original_scene = FlowScene(
            scene_id="sc_pilot_01",
            scene_number=1,
            title="Crossroads Under Attack",
            narration_text="The first wave approaches the outer ramparts.",
            visual_prompt="Volumetric fog, fortress battlements, dark fantasy anime 16:9.",
            duration_sec=7.5,
            camera_motion="orbital pan",
            on_screen_bullets=["Defense Phase 1", "Wave Imminent", "Lucas on Wall"],
            timecoded_directives=[
                {"window": "0-2s", "action": "Establish wall torches flickering in mist"},
                {"window": "2-5s", "action": "Ash raises hand, Lucas draws blade"},
                {"window": "5-7.5s", "action": "Gargoyle screech echoes through fog"},
            ],
            concept_cues=[{"time_ms": 1500, "cue": "torchlight"}, {"time_ms": 4000, "cue": "blade_draw"}],
            diagram_spec={"type": "radar_grid", "targets": 4},
            pedagogical_phase="Climax & Resolution",
            learning_objective="Tactical wave defense coordination",
            sentence_boundaries=[0.0, 3.2, 7.5],
        )

        original_sb = FlowStoryboard(
            project_id="proj_roundtrip_master",
            topic="Tyrant Tower Defense Wave 1",
            language="ru",
            target_audience="dark_fantasy",
            aspect_ratio="16:9",
            model_key="veo_3_1_t2v_fast_audio",
            scenes=[original_scene],
            status="storyboard_ready",
            source_context="Chapter 1: The Crossroads Garrison",
        )

        curr_sb = original_sb
        dict_history = []

        for cycle in range(5):
            d = curr_sb.to_dict()
            dict_history.append(d)
            curr_sb = FlowStoryboard.from_dict(d)

        # Verify all serialized dicts are identical across all cycles
        for i in range(len(dict_history) - 1):
            assert dict_history[i] == dict_history[i + 1], f"Serialization divergence at cycle {i}"

        # Verify restored instance matches original attributes
        assert curr_sb.project_id == original_sb.project_id
        assert curr_sb.topic == original_sb.topic
        assert curr_sb.language == original_sb.language
        assert len(curr_sb.scenes) == 1
        assert curr_sb.scenes[0] == original_scene

    def test_06_modifying_and_reserializing_complex_scene_properties(self):
        """Modify nested lists, dicts, timecodes on scenes and re-serialize."""
        scene = FlowScene(
            scene_id="sc_mutable_01",
            scene_number=1,
            title="Initial Title",
            narration_text="Initial Narration",
            visual_prompt="Initial Visual",
            timecoded_directives=[{"window": "0-2s", "action": "Act 1"}],
            diagram_spec={"nodes": ["Ash", "Lucas"]},
        )
        sb = FlowStoryboard(project_id="proj_mutate", topic="Mutation Test", scenes=[scene])

        # Mutate nested fields
        scene.title = "Updated Defense Title"
        scene.timecoded_directives.append({"window": "2-5s", "action": "Act 2 - Arrow volley"})
        scene.diagram_spec["nodes"].append("Lily")
        scene.on_screen_bullets = ["Volley Ready", "Aim High"]

        d = sb.to_dict()
        assert d["scenes"][0]["title"] == "Updated Defense Title"
        assert len(d["scenes"][0]["timecoded_directives"]) == 2
        assert d["scenes"][0]["diagram_spec"]["nodes"] == ["Ash", "Lucas", "Lily"]
        assert d["scenes"][0]["on_screen_bullets"] == ["Volley Ready", "Aim High"]

        sb_restored = FlowStoryboard.from_dict(d)
        assert sb_restored.scenes[0].title == "Updated Defense Title"
        assert len(sb_restored.scenes[0].timecoded_directives) == 2
        assert sb_restored.scenes[0].diagram_spec["nodes"] == ["Ash", "Lucas", "Lily"]

    def test_07_json_wire_format_compatibility(self):
        """Ensure to_dict output is 100% compliant with standard json.dumps and json.loads."""
        scene = FlowScene(
            scene_id="sc_json_01",
            scene_number=1,
            title="JSON Wire Test",
            narration_text="Narration with \"quotes\" and 'single' and \n newlines.",
            visual_prompt="Visual with \\ backslashes and unicode \u2728 sparkles.",
            duration_sec=5.0,
            timecoded_directives=[{"window": "0-2s", "action": "Action \"quoted\""}],
            diagram_spec={"key": "value", "list": [1, 2, 3]},
        )
        sb = FlowStoryboard(
            project_id="flow_json_test",
            topic="JSON Integrity",
            scenes=[scene],
            assembled_video_url=None,
            subtitles_vtt="WEBVTT\n\n00:00.000 --> 00:05.000\nSubtitle cue",
        )

        d = sb.to_dict()
        json_str = json.dumps(d, ensure_ascii=False, indent=2)
        assert isinstance(json_str, str)

        parsed_dict = json.loads(json_str)
        assert parsed_dict == d

        restored_sb = FlowStoryboard.from_dict(parsed_dict)
        assert restored_sb == sb

    def test_08_multilingual_math_and_special_payloads(self):
        """Stress-test Unicode Cyrillic escapes, emoji, LaTeX math, zero-width chars."""
        cyrillic_narration = (
            "\u041f\u0440\u0438\u043d\u0446 \u042d\u0448 \u0441\u043c\u043e\u0442\u0440\u0438\u0442 "
            "\u043d\u0430 \u043f\u0440\u0438\u0431\u043b\u0438\u0436\u0430\u044e\u0449\u0443\u044e\u0441\u044f "
            "\u043e\u0440\u0434\u0443 \u0441 \u0432\u044b\u0441\u043e\u0442\u044b \u044e\u0436\u043d\u043e\u0439 "
            "\u0441\u0442\u0435\u043d\u044b."
        )
        latex_formula = r"\int_{-\infty}^{\infty} e^{-x^2} dx = \sqrt{\pi}"
        emoji_prompt = "Dark anime battle \U0001F3F0, glowing red gargoyle eyes \U0001F987, stormy sky \u26a1."
        
        scene = FlowScene(
            scene_id="sc_special_01",
            scene_number=1,
            title="\u0421\u0442\u0435\u043d\u0430 \u041f\u0435\u0440\u0435\u043a\u0440\u0451\u0441\u0442\u043a\u0430",
            narration_text=cyrillic_narration,
            visual_prompt=emoji_prompt,
            formula_expression=latex_formula,
        )
        sb = FlowStoryboard(
            project_id="flow_special_chars",
            topic="\u0422\u0435\u0441\u0442\u043e\u0432\u044b\u0439 \u043f\u0440\u043e\u0435\u043a\u0442 \u043d\u0430 \u0440\u0443\u0441\u0441\u043a\u043e\u043c \u044f\u0437\u044b\u043a\u0435",
            scenes=[scene],
        )

        d = sb.to_dict()
        restored = FlowStoryboard.from_dict(d)
        assert restored.scenes[0].narration_text == cyrillic_narration
        assert restored.scenes[0].formula_expression == latex_formula
        assert restored.scenes[0].visual_prompt == emoji_prompt
        assert restored.topic == "\u0422\u0435\u0441\u0442\u043e\u0432\u044b\u0439 \u043f\u0440\u043e\u0435\u043a\u0442 \u043d\u0430 \u0440\u0443\u0441\u0441\u043a\u043e\u043c \u044f\u0437\u044b\u043a\u0435"

    def test_09_kwargs_unpacking_variants(self):
        """Test alternative invocation styles for FlowStoryboard.from_dict."""
        base_dict = {"project_id": "proj_kw", "topic": "Kwargs Test"}

        # 1. d=dict
        sb1 = FlowStoryboard.from_dict(d=base_dict)
        assert sb1.project_id == "proj_kw"

        # 2. data=dict
        sb2 = FlowStoryboard.from_dict(data=base_dict)
        assert sb2.project_id == "proj_kw"

        # 3. direct kwargs without dict
        sb3 = FlowStoryboard.from_dict(project_id="proj_direct", topic="Direct Topic")
        assert sb3.project_id == "proj_direct"
        assert sb3.topic == "Direct Topic"

        # 4. dict with overriding kwargs
        sb4 = FlowStoryboard.from_dict(base_dict, topic="Overridden Topic", model_key="veo_2_0_t2v")
        assert sb4.project_id == "proj_kw"
        assert sb4.topic == "Overridden Topic"
        assert sb4.model_key == "veo_2_0_t2v"

    def test_10_high_volume_stress(self):
        """Test performance and serialization stability with 500 scenes."""
        scenes = [
            FlowScene(
                scene_id=f"sc_vol_{i:04d}",
                scene_number=i,
                title=f"Tactical Segment {i}",
                narration_text=f"Wave segment {i} command coordination details.",
                visual_prompt=f"Crossroads defense angle {i % 10}, dynamic lighting.",
                duration_sec=4.0 + (i % 5),
            )
            for i in range(1, 501)
        ]
        sb = FlowStoryboard(
            project_id="proj_stress_500",
            topic="Massive Battle Simulation",
            scenes=scenes,
        )

        d = sb.to_dict()
        assert len(d["scenes"]) == 500

        restored = FlowStoryboard.from_dict(d)
        assert len(restored.scenes) == 500
        assert restored.scenes[249].scene_id == "sc_vol_0250"
        assert restored.scenes[499].scene_id == "sc_vol_0500"

    def test_11_deep_mutation_isolation(self):
        """Verify modifying to_dict output does not mutate the source dataclass."""
        scene = FlowScene(
            scene_id="sc_iso_01",
            scene_number=1,
            title="Iso Test",
            narration_text="Narration",
            visual_prompt="Visual",
            timecoded_directives=[{"window": "0-2s", "action": "Original Action"}],
            diagram_spec={"nodes": ["Root"]},
        )
        sb = FlowStoryboard(project_id="proj_iso", topic="Isolation Test", scenes=[scene])

        d = sb.to_dict()
        d["scenes"][0]["timecoded_directives"][0]["action"] = "Tampered Action"
        d["scenes"][0]["diagram_spec"]["nodes"].append("Tampered Node")

        # Source scene must remain untampered
        assert scene.timecoded_directives[0]["action"] == "Original Action"
        assert scene.diagram_spec["nodes"] == ["Root"]

    def test_12_non_dict_inputs_graceful_handling(self):
        """Pass invalid types as the root data argument (int, list, str, bool, float)."""
        for invalid_input in [123, [1, 2, 3], "string_payload", 45.67, True, False]:
            sb = FlowStoryboard.from_dict(invalid_input)
            assert isinstance(sb, FlowStoryboard)
            assert isinstance(sb.project_id, str) and len(sb.project_id) > 0
            assert sb.topic == ""
            assert sb.scenes == []

    def test_13_generator_and_set_scenes_resilience(self):
        """Pass tuples, sets, or generators as 'scenes' and ensure no crashes."""
        gen = (FlowScene(scene_id=f"g_{i}", scene_number=i, title="t", narration_text="n", visual_prompt="v") for i in range(3))
        sb_gen = FlowStoryboard.from_dict({"scenes": gen})
        # Generator is not a list, so it safely defaults to empty list
        assert sb_gen.scenes == []

        sb_set = FlowStoryboard.from_dict({"scenes": {1, 2, 3}})
        assert sb_set.scenes == []

        sb_tuple = FlowStoryboard.from_dict({"scenes": (1, 2, 3)})
        assert sb_tuple.scenes == []

    def test_14_legacy_alias_cross_assignability(self):
        """Ensure FlowStoryboard and FlowEducationalProject are fully interchangeable."""
        def consume_project(p: FlowEducationalProject) -> str:
            return f"Project: {p.project_id} | Topic: {p.topic}"

        def consume_storyboard(sb: FlowStoryboard) -> str:
            return f"Storyboard: {sb.project_id} | Scenes: {len(sb.scenes)}"

        proj = FlowEducationalProject(project_id="cross_01", topic="Cross Assignability")
        sb = FlowStoryboard(project_id="cross_02", topic="Cross Storyboard")

        assert consume_project(sb) == "Project: cross_02 | Topic: Cross Storyboard"
        assert consume_storyboard(proj) == "Storyboard: cross_01 | Scenes: 0"
        assert FlowStoryboard.from_dict == FlowEducationalProject.from_dict

    def test_15_immutability_of_input_payload(self):
        """Assert from_dict never mutates caller's input dictionary."""
        original_dict = {
            "project_id": "immutable_test",
            "topic": "No In-Place Mutation",
            "scenes": [
                {"scene_id": "sc_imm_1", "scene_number": 1, "title": "T1", "narration_text": "N1", "visual_prompt": "V1"}
            ],
            "extra_key": "will_be_ignored"
        }
        import copy
        dict_snapshot = copy.deepcopy(original_dict)

        FlowStoryboard.from_dict(original_dict)
        assert original_dict == dict_snapshot

