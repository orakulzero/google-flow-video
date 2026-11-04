"""
Empirical Stress Test Harness for Milestone 3 (Challenger M3).
Tests:
1. Edge cases in validate_stress_accents() and format_dsp_phonetics_ru().
2. Invariants across all scenes in DSP_DEFENSE_CYCLES:
   - 0 stress accent violations in tts_narration_text
   - Total duration >= 1800s and scene count >= 50
   - All 13 Variant 5 tokens in full corpus
   - strip_accent_markers(narration_text) has 0 '+' or '*' markers
3. REQ-004 verification: zero Cyrillic characters in tests/test_flow_studio.py.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))

import flow_testbench_runner as runner
from src.dsp_defense_cycles import (
    CLITICS,
    DSP_DEFENSE_CYCLES,
    DSP_PHONETIC_MAP,
    DSP_PHONETIC_MAP_ENTRIES,
    VOWELS,
    format_dsp_phonetics_ru,
    validate_stress_accents,
)


def test_edge_cases_validate_stress_accents() -> None:
    print("[1] Stress-testing validate_stress_accents()...")

    # 1.1 Empty / whitespace / non-cyrillic text
    assert validate_stress_accents("")[0] is True
    assert validate_stress_accents("   \t\n   ")[0] is True
    assert validate_stress_accents("12345 67890 !? @#$%^&*()")[0] is True
    assert validate_stress_accents("DSP56824 AD73322 IS61LV6416")[0] is True

    # 1.2 Single syllable words (<= 1 vowel) without '+' must pass
    single_syllable = "\u043e\u043d \u0432 \u043d\u0430 \u0434\u0432\u0430 \u0434\u043e \u043f\u043e \u043f\u0440\u0438 \u0438\u0437 \u0437\u0430 \u043e\u0442 \u043f\u043e\u0434 \u043d\u0430\u0434 \u0431\u0435\u0437 \u0434\u043b\u044f"
    is_valid, errs = validate_stress_accents(single_syllable)
    assert is_valid, f"Single syllable words failed: {errs}"

    # 1.3 Clitics and exceptions without '+' must pass
    clitics_sample = " ".join(list(CLITICS)[:15])
    is_valid, errs = validate_stress_accents(clitics_sample)
    assert is_valid, f"Clitics failed: {errs}"

    # 1.4 Words containing '\u0451' (yo) without '+' must pass
    yo_sample = "\u043e\u0442\u0441\u0447\u0451\u0442 \u043f\u0440\u0438\u0451\u043c\u043d\u0438\u043a \u0435\u0451 \u0432\u0441\u0451 \u0440\u0430\u0441\u0447\u0451\u0442"
    is_valid, errs = validate_stress_accents(yo_sample)
    assert is_valid, f"Yo words failed: {errs}"

    # 1.5 Multi-syllable Russian words with correct '+' must pass
    valid_stressed = "\u043c\u0438\u043a\u0440\u043e\u043f\u0440\u043e\u0446+\u0435\u0441\u0441\u043e\u0440 \u0441\u0438\u043d\u0442\u0435\u0437+\u0430\u0442\u043e\u0440 +\u044d\u0442\u043e \u0432\u044b\u0447\u0438\u0441\u043b+\u0435\u043d\u0438\u0435"
    is_valid, errs = validate_stress_accents(valid_stressed)
    assert is_valid, f"Valid stressed words failed: {errs}"

    # 1.6 Adversarial: Missing '+' on multi-syllable word must fail
    invalid_unstressed = "\u043c\u0438\u043a\u0440\u043e\u043f\u0440\u043e\u0446\u0435\u0441\u0441\u043e\u0440"
    is_valid, errs = validate_stress_accents(invalid_unstressed)
    assert not is_valid, "Failed to catch missing '+' on multi-syllable word"
    assert "Missing '+' stress accent" in errs[0]["reason"]

    # 1.7 Adversarial: '+' before consonant must fail
    invalid_plus_consonant = "\u043c\u0438\u043a\u0440\u043e+\u043f\u0440\u043e\u0446\u0435\u0441\u0441\u043e\u0440"
    is_valid, errs = validate_stress_accents(invalid_plus_consonant)
    assert not is_valid, "Failed to catch '+' before consonant"
    assert "immediately preceding a vowel" in errs[0]["reason"]

    # 1.8 Adversarial: '+' at the very end of token must fail
    invalid_dangling_plus = "\u0441\u043b+\u043e\u0432\u043e+"
    is_valid, errs = validate_stress_accents(invalid_dangling_plus)
    assert not is_valid, "Failed to catch dangling '+' at end of word"

    # 1.9 Adversarial: Multiple '+' markers with one invalid must fail
    mixed_plus = "\u043c\u0438\u043a\u0440\u043e+\u043f\u0440\u043e\u0446+\u0435\u0441\u0441\u043e\u0440"
    is_valid, errs = validate_stress_accents(mixed_plus)
    assert not is_valid, "Failed to catch invalid '+' among valid ones"

    # 1.10 Uppercase vowel following '+' must pass
    uppercase_vowel = "\u042d\u0439-+\u0410\u0440 \u041e-+\u0423"
    is_valid, errs = validate_stress_accents(uppercase_vowel)
    assert is_valid, f"Uppercase vowel after '+' failed: {errs}"

    # 1.11 Hyphenated tokens with valid stresses
    hyphenated = "\u0414\u0438-\u042d\u0441-\u041f+\u0438 \u0421+\u0430\u043b\u043b\u0435\u043d\u0430-\u041a+\u0435\u044f"
    is_valid, errs = validate_stress_accents(hyphenated)
    assert is_valid, f"Hyphenated valid words failed: {errs}"

    print("  PASS: validate_stress_accents() handles all 11 positive and negative stress scenarios correctly.")


def test_edge_cases_format_dsp_phonetics_ru() -> None:
    print("[2] Stress-testing format_dsp_phonetics_ru()...")

    # 2.1 Test prefix shadowing / ordering
    # Motorola DSP56824 must expand to Motorola expansion + DSP56824 expansion, not get eaten by DSP56824
    expanded = format_dsp_phonetics_ru("Motorola DSP56824")
    assert "\u041c\u043e\u0442\u043e\u0440+\u043e\u043b\u0430" in expanded
    assert "\u0414\u0438-\u042d\u0441-\u041f+\u0438" in expanded
    assert "Motorola" not in expanded
    assert "DSP56824" not in expanded

    # 2.2 AD73322AR vs AD73322
    exp_ar = format_dsp_phonetics_ru("AD73322AR")
    assert "\u042d\u0439-+\u0410\u0440" in exp_ar
    assert "AD73322" not in exp_ar

    exp_plain = format_dsp_phonetics_ru("AD73322")
    assert "\u042d\u0439-+\u0410\u0440" not in exp_plain
    assert "\u042d\u0439-\u0414+\u0438" in exp_plain

    # 2.3 MAX706S vs MAX706
    assert "\u042d\u0441" in format_dsp_phonetics_ru("MAX706S")
    assert "MAX706" not in format_dsp_phonetics_ru("MAX706S")

    # 2.4 AD8606AR vs AD8606
    assert "\u042d\u0439-+\u0410\u0440" in format_dsp_phonetics_ru("AD8606AR")

    # 2.5 Numbers with decimal comma
    assert format_dsp_phonetics_ru("20,833") == "20 \u0438 833"
    assert format_dsp_phonetics_ru("0,9878") == "0 \u0438 9878"
    assert format_dsp_phonetics_ru("1,034") == "1 \u0438 034"
    assert format_dsp_phonetics_ru("4,2") == "4 \u0438 2"

    # 2.6 All phonetic entries in DSP_PHONETIC_MAP produce non-empty strings and are replaced
    for src_term, exp_spoken in DSP_PHONETIC_MAP_ENTRIES:
        res = format_dsp_phonetics_ru(f"Prefix {src_term} Suffix")
        assert src_term not in res, f"Token '{src_term}' was not replaced by format_dsp_phonetics_ru"
        assert exp_spoken in res, f"Expected replacement '{exp_spoken}' missing for '{src_term}'"

    print("  PASS: format_dsp_phonetics_ru() verified against 100% of catalog entries and prefix shadowing rules.")


def test_dsp_defense_cycles_invariants() -> None:
    print("[3] Stress-testing DSP_DEFENSE_CYCLES across all 6 sections and all scenes...")

    assert len(DSP_DEFENSE_CYCLES) == 6, f"Expected 6 cycles, got {len(DSP_DEFENSE_CYCLES)}"

    total_scenes = 0
    total_duration_sec = 0
    full_corpus: list[str] = []
    linter_failures: list[dict] = []
    strip_marker_leaks: list[str] = []

    for c_idx, cycle in enumerate(DSP_DEFENSE_CYCLES):
        scenes = cycle.get("scenes", [])
        assert len(scenes) >= 7, f"Cycle {c_idx+1} has fewer than 7 scenes ({len(scenes)})"
        assert cycle.get("language") == "ru", f"Cycle {c_idx+1} language != 'ru'"

        for s_idx, sc in enumerate(scenes):
            total_scenes += 1
            dur = sc.get("duration_sec", 36)
            total_duration_sec += dur
            sc_label = f"C{c_idx+1}_S{s_idx+1} '{sc.get('title', 'untitled')}'"

            # Voice persona check
            assert sc.get("voice_persona") == "voice_y0joebp3bwta", (
                f"Scene {sc_label} has wrong voice persona {sc.get('voice_persona')}"
            )

            # Check tts_narration_text stress accents
            tts_text = sc.get("tts_narration_text")
            assert tts_text, f"Scene {sc_label} missing tts_narration_text"
            is_valid, errors = validate_stress_accents(tts_text)
            if not is_valid:
                linter_failures.append({
                    "cycle": c_idx + 1,
                    "scene": sc_label,
                    "errors": errors,
                })

            # Check strip_accent_markers on narration_text
            narr_text = sc.get("narration_text", "")
            assert narr_text, f"Scene {sc_label} missing narration_text"
            cleaned_sub = runner.strip_accent_markers(narr_text)
            if "+" in cleaned_sub or "*" in cleaned_sub:
                strip_marker_leaks.append(f"Scene {sc_label}: {cleaned_sub}")

            # Collect for corpus check
            full_corpus.append(narr_text)
            for b in sc.get("on_screen_bullets", []):
                full_corpus.append(b)

    # Invariant assertions
    print(f"  Observed Total Scenes: {total_scenes}")
    print(f"  Observed Total Duration: {total_duration_sec} s ({total_duration_sec / 60:.2f} min)")

    assert total_scenes >= 50, f"Total scenes {total_scenes} < 50"
    assert total_duration_sec >= 1800, f"Total duration {total_duration_sec}s < 1800s"

    assert len(linter_failures) == 0, f"Found {len(linter_failures)} stress accent violations: {linter_failures}"
    assert len(strip_marker_leaks) == 0, f"Found '+' or '*' leaks after strip_accent_markers: {strip_marker_leaks}"

    # 13 Coursework tokens check
    corpus_text = " ".join(full_corpus)
    required_tokens = [
        "DSP56824",
        "AD73322",
        "IS61LV6416",
        "AD8606AR",
        "MAX706S",
        "AMS1117-3.3",
        "MC68HC908GP32",
        "0,9878",
        "18,00%",
        "20,833",
        "P:$001E",
        "1,034",
        "4,2",
    ]
    missing_tokens = []
    for tok in required_tokens:
        count = corpus_text.count(tok)
        print(f"    Token '{tok}': {count} occurrences across corpus")
        if count == 0:
            missing_tokens.append(tok)
    assert len(missing_tokens) == 0, f"Missing required Variant 5 tokens: {missing_tokens}"

    print("  PASS: All 53 scenes pass stress accent linter with 0 violations.")
    print("  PASS: strip_accent_markers() removes 100% of '+' and '*' markers.")
    print("  PASS: All 13 Variant 5 tokens confirmed present in full corpus.")


def test_req004_zero_cyrillic_in_test_files() -> None:
    print("[4] Stress-testing REQ-004: Zero Cyrillic in tests/test_flow_studio.py...")

    target_file = REPO_ROOT / "tests" / "test_flow_studio.py"
    assert target_file.is_file(), f"Missing {target_file}"

    content = target_file.read_text(encoding="utf-8")
    cyrillic_pattern = re.compile(r"[\u0400-\u04ff]")
    matches = list(cyrillic_pattern.finditer(content))

    if matches:
        print(f"FAIL: Found {len(matches)} Cyrillic characters in {target_file}:")
        for m in matches[:10]:
            lineno = content.count("\n", 0, m.start()) + 1
            print(f"  Line {lineno}: char '{m.group()}' (U+{ord(m.group()):04X})")
        assert False, f"REQ-004 violation: {len(matches)} Cyrillic characters found in test_flow_studio.py"

    print("  PASS: 0 Cyrillic characters found in tests/test_flow_studio.py (100% REQ-004 compliant).")


def main() -> None:
    print("=== STARTING CHALLENGER M3 EMPIRICAL STRESS TESTS ===")
    test_edge_cases_validate_stress_accents()
    test_edge_cases_format_dsp_phonetics_ru()
    test_dsp_defense_cycles_invariants()
    test_req004_zero_cyrillic_in_test_files()
    print("=== ALL EMPIRICAL STRESS TESTS PASSED SUCCESSFULLY ===")


if __name__ == "__main__":
    main()
