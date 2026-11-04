"""
scripts/verify_m2_challenger_empirical.py
Empirical stress-testing verification harness for Milestone 2 Iteration 2.
Authors: m2_challenger_ttd_iter2_1
"""
import sys
import re
import tempfile
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.flow_bridge import FlowEducationalProject, FlowScene, FlowStoryboard
import src.ttd_storyboard as ttd_sb

def main() -> None:
    print("=== START EMPIRICAL STRESS TESTS ===")

    # -------------------------------------------------------------
    # DEFECT 1: validate_storyboard(sb, raise_on_error=True)
    # -------------------------------------------------------------
    print("\n--- 1. Testing Defect 1: validate_storyboard raise_on_error and failure modes ---")
    pilot = ttd_sb.build_ttd_pilot_storyboard()
    assert ttd_sb.validate_storyboard(pilot) is True, "Pilot must validate True"
    assert ttd_sb.validate_storyboard(pilot, raise_on_error=True) is True, "Pilot must validate True with raise_on_error=True"
    print("PASS: Valid pilot storyboard returns True for both raise_on_error=False and True")

    invalid_cases = []

    # Missing project_id
    sb_bad = ttd_sb.build_ttd_pilot_storyboard()
    sb_bad.project_id = ""
    invalid_cases.append(("missing project_id (empty)", sb_bad, "project_id"))
    sb_bad2 = ttd_sb.build_ttd_pilot_storyboard()
    sb_bad2.project_id = "   "
    invalid_cases.append(("missing project_id (whitespace)", sb_bad2, "project_id"))

    # Missing topic
    sb_bad = ttd_sb.build_ttd_pilot_storyboard()
    sb_bad.topic = ""
    invalid_cases.append(("missing topic (empty)", sb_bad, "topic"))
    sb_bad2 = ttd_sb.build_ttd_pilot_storyboard()
    sb_bad2.topic = "   "
    invalid_cases.append(("missing topic (whitespace)", sb_bad2, "topic"))

    # Empty scenes
    sb_bad = ttd_sb.build_ttd_pilot_storyboard()
    sb_bad.scenes = []
    invalid_cases.append(("empty scenes", sb_bad, "scenes"))

    # Invalid scenes container
    sb_bad = ttd_sb.build_ttd_pilot_storyboard()
    sb_bad.scenes = "not_a_list"
    invalid_cases.append(("non-list scenes", sb_bad, "scenes"))

    # Non-FlowScene in scenes
    sb_bad = ttd_sb.build_ttd_pilot_storyboard()
    sb_bad.scenes = [{"not": "a scene"}]
    invalid_cases.append(("non-FlowScene element", sb_bad, "FlowScene"))

    # Scene missing scene_id
    sb_bad = ttd_sb.build_ttd_pilot_storyboard()
    sb_bad.scenes[0].scene_id = ""
    invalid_cases.append(("missing scene_id", sb_bad, "scene_id"))

    # Scene missing title
    sb_bad = ttd_sb.build_ttd_pilot_storyboard()
    sb_bad.scenes[0].title = ""
    invalid_cases.append(("missing title", sb_bad, "title"))

    # Scene missing narration_text
    sb_bad = ttd_sb.build_ttd_pilot_storyboard()
    sb_bad.scenes[0].narration_text = ""
    invalid_cases.append(("missing narration_text", sb_bad, "narration_text"))

    # Scene missing visual_prompt
    sb_bad = ttd_sb.build_ttd_pilot_storyboard()
    sb_bad.scenes[0].visual_prompt = ""
    invalid_cases.append(("missing visual_prompt", sb_bad, "visual_prompt"))

    # Scene missing camera_motion
    sb_bad = ttd_sb.build_ttd_pilot_storyboard()
    sb_bad.scenes[0].camera_motion = ""
    invalid_cases.append(("missing camera_motion", sb_bad, "camera_motion"))

    # Scene invalid duration
    sb_bad = ttd_sb.build_ttd_pilot_storyboard()
    sb_bad.scenes[0].duration_sec = 0.0
    invalid_cases.append(("zero duration_sec", sb_bad, "duration_sec"))
    sb_bad2 = ttd_sb.build_ttd_pilot_storyboard()
    sb_bad2.scenes[0].duration_sec = -3.5
    invalid_cases.append(("negative duration_sec", sb_bad2, "duration_sec"))
    sb_bad3 = ttd_sb.build_ttd_pilot_storyboard()
    sb_bad3.scenes[0].duration_sec = None
    invalid_cases.append(("None duration_sec", sb_bad3, "duration_sec"))

    # Non-storyboard type
    invalid_cases.append(("None storyboard", None, "FlowStoryboard"))
    invalid_cases.append(("string storyboard", "not_a_storyboard", "FlowStoryboard"))

    for label, bad_sb, expected_token in invalid_cases:
        res = ttd_sb.validate_storyboard(bad_sb, raise_on_error=False)
        assert res is False, f"Expected False for {label}, got {res}"
        try:
            ttd_sb.validate_storyboard(bad_sb, raise_on_error=True)
            assert False, f"Expected ValueError for {label}, but no exception was raised"
        except ValueError as e:
            msg = str(e)
            assert expected_token.lower() in msg.lower(), f"Expected token {expected_token} in msg: {msg}"

    print(f"PASS: All {len(invalid_cases)} invalid cases correctly returned False and raised descriptive ValueError")

    # -------------------------------------------------------------
    # DEFECT 2: export_storyboard_to_json 0 Cyrillic characters
    # -------------------------------------------------------------
    print("\n--- 2. Testing Defect 2: export_storyboard_to_json Cyrillic-clean and ASCII ---")
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir) / "test_pilot.json"
        json_str = ttd_sb.export_storyboard_to_json(pilot, path=tmp_path)
        
        # Check JSON string
        cyrillic_in_str = re.findall(r"[\u0400-\u04FF]", json_str)
        assert len(cyrillic_in_str) == 0, f"Found {len(cyrillic_in_str)} Cyrillic chars in json_str"
        assert all(ord(c) < 128 for c in json_str), "json_str has characters with ord >= 128"
        
        # Check disk file
        disk_content = tmp_path.read_text(encoding="utf-8")
        cyrillic_in_disk = re.findall(r"[\u0400-\u04FF]", disk_content)
        assert len(cyrillic_in_disk) == 0, f"Found {len(cyrillic_in_disk)} Cyrillic chars in disk_content"
        assert all(ord(c) < 128 for c in disk_content), "disk_content has characters with ord >= 128"
        
        # Check roundtrip
        restored_str = ttd_sb.load_storyboard_from_json(json_str)
        restored_disk = ttd_sb.load_storyboard_from_json(tmp_path)
        assert restored_str == pilot, "String roundtrip does not match original pilot"
        assert restored_disk == pilot, "Disk roundtrip does not match original pilot"
        
        # Verify Russian characters are restored intact in Python memory
        assert any(re.search(r"[\u0400-\u04FF]", sc.narration_text) for sc in restored_str.scenes), "Restored storyboard lost Cyrillic narration!"
        print("PASS: export_storyboard_to_json is 100% 7-bit ASCII on disk and in memory, and perfectly restores Unicode in Python objects")

    # -------------------------------------------------------------
    # DEFECT 3: load_storyboard_from_json path and type discrimination
    # -------------------------------------------------------------
    print("\n--- 3. Testing Defect 3: load_storyboard_from_json path vs literal discrimination ---")

    # Non-existent paths
    missing_paths = [
        "missing_dir/file.json",
        "missing.json",
        "non_existent_folder\\sub\\file.json",
        Path("another_missing_file.json"),
    ]
    for p in missing_paths:
        try:
            ttd_sb.load_storyboard_from_json(p)
            assert False, f"Expected FileNotFoundError for {p}"
        except FileNotFoundError:
            pass

    # Non-dictionary JSON literals
    invalid_json_literals = [
        ("[1, 2, 3]", "list"),
        ("12345", "int"),
        ("true", "bool"),
        ('"a string literal"', "str"),
        ("3.14159", "float"),
    ]
    for lit, type_name in invalid_json_literals:
        try:
            ttd_sb.load_storyboard_from_json(lit)
            assert False, f"Expected ValueError for non-dict JSON literal {lit}"
        except ValueError as e:
            assert "dictionary" in str(e).lower(), f"Expected 'dictionary' in ValueError message, got: {e}"

    print("PASS: All missing paths raised FileNotFoundError and non-dict JSON literals raised ValueError")

    # -------------------------------------------------------------
    # DEFECT 4: Voice persona authorization
    # -------------------------------------------------------------
    print("\n--- 4. Testing Defect 4: Voice persona authorization ---")
    # Unauthorized voice
    sb_unauth = ttd_sb.build_ttd_pilot_storyboard()
    sb_unauth.scenes[0].voice_persona = "unauthorized_male_voice"

    assert ttd_sb.validate_storyboard(sb_unauth) is False, "Unauthorized voice must return False"
    try:
        ttd_sb.validate_storyboard(sb_unauth, raise_on_error=True)
        assert False, "Unauthorized voice must raise ValueError with raise_on_error=True"
    except ValueError as e:
        msg = str(e)
        assert "unauthorized voice_persona" in msg.lower(), f"Expected unauthorized voice_persona in message, got: {msg}"
        assert "unauthorized_male_voice" in msg
        print(f"PASS: Unauthorized voice rejected with ValueError: {msg}")

    # Empty voice persona
    sb_empty_voice = ttd_sb.build_ttd_pilot_storyboard()
    sb_empty_voice.scenes[0].voice_persona = ""
    assert ttd_sb.validate_storyboard(sb_empty_voice) is False
    try:
        ttd_sb.validate_storyboard(sb_empty_voice, raise_on_error=True)
        assert False
    except ValueError as e:
        assert "voice_persona" in str(e).lower()

    # Test each authorized voice persona
    for auth_voice in ["voice_y0joebp3bwta", "Sulafat", "Kore"]:
        sb_auth = ttd_sb.build_ttd_pilot_storyboard()
        for sc in sb_auth.scenes:
            sc.voice_persona = auth_voice
        assert ttd_sb.validate_storyboard(sb_auth) is True, f"Authorized voice {auth_voice} failed validation"
        assert ttd_sb.validate_storyboard(sb_auth, raise_on_error=True) is True, f"Authorized voice {auth_voice} failed validation with raise_on_error=True"
        print(f"PASS: Authorized persona {auth_voice} validated successfully")

    print("\n=== ALL 4 EMPIRICAL TESTS PASSED WITH ZERO ERRORS ===")

if __name__ == "__main__":
    main()
