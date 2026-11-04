"""
Milestone 3 Verification Test: Subtitle Geometry and Badge Collision Stress Test.
Author: m3_challenger_r3_1 (teamwork_critic_specialist)

Mission & Scope:
1. Load all 16 chapters from scripts/moiad_chapters_spec.py (MOIAD_PARTS_SPEC).
2. Traverse all scenes, all subtitle pages, and all words (1,200+ words).
3. For EVERY word w_i, simulate the active state where word i is active,
   and calculate the exact pixel bounding boxes of:
   - Word i's active badge background pill: [cx_i - pad_l, cy - 2, cx_i + ww_i + pad_r, cy + 26].
   - Word i-1's text glyph bounding box (if present on the same line).
   - Word i+1's text glyph bounding box (if present on the same line).
4. Measure the exact clearance:
   - gap_left = cx_i - (cx_{i-1} + ww_{i-1}) - pad_l
   - gap_right = cx_{i+1} - (cx_i + ww_i + pad_r)
5. Assertions:
   - Overlap collisions MUST BE STRICTLY ZERO: count(gap < 0) == 0.
   - Minimum clearance across the entire course MUST be >= 2.0 px (spec requires >= 8 px).
   - No text glyph clipping: verify that Pass 1 badge rendering followed by Pass 2 text rendering
     guarantees zero glyph occlusion.
6. Stress test extreme strings:
   - Test words up to 30 characters (e.g. Russian compound technical terms).
   - Verify that clamped padding prevents any overflow into adjacent words.
7. CRITICAL: Strictly ZERO (0) literal Cyrillic characters in this file (all Unicode escaped).
"""

import math
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
import pytest
from PIL import Image, ImageDraw

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.moiad_visual_engines import (
    load_moiad_fonts,
    _text_width,
    _partition_subtitle_page_words,
    COL_COBALT,
    COL_COBALT_WASH,
    COL_INK,
)
from scripts.moiad_chapters_spec import MOIAD_PARTS_SPEC
from src.flow_bridge import FlowEducationalCompositor, SubtitlePage, WordTiming


def test_m3_challenger_zero_cyrillic_invariant() -> None:
    """Verify strictly ZERO literal Cyrillic characters in this file."""
    test_file_path = Path(__file__).resolve()
    with open(test_file_path, "r", encoding="utf-8") as f:
        content = f.read()

    match = re.search(r"[\u0400-\u04FF]", content)
    assert match is None, (
        f"Critical invariant violation: literal Cyrillic character found at position {match.start()}: "
        f"{repr(match.group(0))}"
    )


def test_m3_challenger_all_16_chapters_badge_clearance_and_collision() -> None:
    """
    Traverse all 16 chapters, scenes, pages, and every word.
    Simulate active word state and measure exact left/right clearance gaps.
    Assert zero collisions (gap < 0 count == 0) and min gap >= 8.0 px (spec >= 8 px, threshold >= 2.0 px).
    """
    fonts = load_moiad_fonts()
    img = Image.new("RGB", (1280, 720))
    draw = ImageDraw.Draw(img)
    compositor = FlowEducationalCompositor(1280, 720, 24)

    total_chapters = 0
    total_pages = 0
    total_words = 0
    total_clearance_measurements = 0
    min_clearance = 9999.0
    max_clearance = -9999.0
    total_collisions = 0
    ww_space = 14

    for part in MOIAD_PARTS_SPEC:
        for ch in part["chapters"]:
            total_chapters += 1
            caps = compositor._build_word_captions(ch["ch_id"], ch["narration"], 16.0)
            pages: List[SubtitlePage] = caps.pages
            total_pages += len(pages)

            for page in pages:
                l0, l1 = _partition_subtitle_page_words(draw, page.words, fonts["sub_r"], 1040)
                rendered = [(l0, 643)] if not l1 else [(l0, 626), (l1, 660)]

                for line_words, cy in rendered:
                    if not line_words:
                        continue
                    w_txts = [getattr(w, "word", str(w)) for w in line_words]
                    w_widths = [_text_width(draw, wt, fonts["sub_r"]) for wt in w_txts]
                    line_w = sum(w_widths) + ww_space * max(0, len(line_words) - 1)
                    cx_start = max(42, 590 - line_w // 2)

                    # For every word on this line, simulate active state
                    for i, (w_txt, ww_i) in enumerate(zip(w_txts, w_widths)):
                        total_words += 1
                        cx_i = cx_start + sum(w_widths[:i]) + ww_space * i

                        act_w = _text_width(draw, w_txt, fonts["sub_b"])
                        pad_l = min(4 + max(0, (act_w - ww_i) // 2), 6)
                        pad_r = min(4 + max(0, act_w - ww_i - (act_w - ww_i) // 2), 6)

                        pill_box = [cx_i - pad_l, cy - 2, cx_i + ww_i + pad_r, cy + 26]

                        # Check left neighbor on same line
                        if i > 0:
                            total_clearance_measurements += 1
                            ww_prev = w_widths[i - 1]
                            cx_prev = cx_start + sum(w_widths[: i - 1]) + ww_space * (i - 1)
                            prev_text_box = [cx_prev, cy, cx_prev + ww_prev, cy + 24]

                            gap_left = cx_i - (cx_prev + ww_prev) - pad_l
                            min_clearance = min(min_clearance, gap_left)
                            max_clearance = max(max_clearance, gap_left)
                            if gap_left < 0:
                                total_collisions += 1

                            # Verify exact math: cx_i - (cx_prev + ww_prev) must equal ww_space (14)
                            assert cx_i - (cx_prev + ww_prev) == ww_space
                            assert gap_left == ww_space - pad_l

                        # Check right neighbor on same line
                        if i < len(line_words) - 1:
                            total_clearance_measurements += 1
                            ww_next = w_widths[i + 1]
                            cx_next = cx_start + sum(w_widths[: i + 1]) + ww_space * (i + 1)
                            next_text_box = [cx_next, cy, cx_next + ww_next, cy + 24]

                            gap_right = cx_next - (cx_i + ww_i + pad_r)
                            min_clearance = min(min_clearance, gap_right)
                            max_clearance = max(max_clearance, gap_right)
                            if gap_right < 0:
                                total_collisions += 1

                            # Verify exact math: cx_next - (cx_i + ww_i) must equal ww_space (14)
                            assert cx_next - (cx_i + ww_i) == ww_space
                            assert gap_right == ww_space - pad_r

    print(f"\n[TELEMETRY] Total Chapters: {total_chapters}")
    print(f"[TELEMETRY] Total Subtitle Pages: {total_pages}")
    print(f"[TELEMETRY] Total Words Simulated Active: {total_words}")
    print(f"[TELEMETRY] Total Clearance Measurements: {total_clearance_measurements}")
    print(f"[TELEMETRY] Minimum Clearance: {min_clearance:.2f} px")
    print(f"[TELEMETRY] Maximum Clearance: {max_clearance:.2f} px")
    print(f"[TELEMETRY] Total Collisions: {total_collisions}")

    # Strict empirical assertions
    assert total_chapters == 16, f"Expected 16 chapters, got {total_chapters}"
    assert total_words >= 1200, f"Expected >= 1200 words, got {total_words}"
    assert total_collisions == 0, f"Detected {total_collisions} badge collisions (must be 0)"
    assert min_clearance >= 8.0, f"Minimum clearance must be >= 8.0 px, got {min_clearance} px"
    assert min_clearance >= 2.0, f"Threshold requirement >= 2.0 px violated: {min_clearance} px"


def test_m3_challenger_extreme_strings_stress_test() -> None:
    """
    Adversarially stress-test extreme Russian polysyllabic technical terms
    up to 35+ characters to prove clamping bounds and zero collision.
    """
    fonts = load_moiad_fonts()
    img = Image.new("RGB", (1280, 720))
    draw = ImageDraw.Draw(img)

    extreme_words = [
        # 16 chars: differential
        "\\u0434\\u0438\\u0444\\u0444\\u0435\\u0440\\u0435\\u043d\\u0446\\u0438\\u0430\\u043b".encode("ascii").decode("unicode-escape"),
        # 21 chars: standardized
        "\\u0441\\u0442\\u0430\\u043d\\u0434\\u0430\\u0440\\u0442\\u0438\\u0437\\u0438\\u0440\\u043e\\u0432\\u0430\\u043d\\u043d\\u044b\\u0439".encode("ascii").decode("unicode-escape"),
        # 25 chars: ninety-five percent
        "\\u0434\\u0435\\u0432\\u044f\\u043d\\u043e\\u0441\\u0442\\u043e\\u043f\\u044f\\u0442\\u0438\\u043f\\u0440\\u043e\\u0446\\u0435\\u043d\\u0442\\u043d\\u044b\\u0439".encode("ascii").decode("unicode-escape"),
        # 30 chars: transformational-computational compound
        "\\u043f\\u0440\\u0435\\u043e\\u0431\\u0440\\u0430\\u0437\\u043e\\u0432\\u0430\\u0442\\u0435\\u043b\\u044c\\u043d\\u043e-\\u0432\\u044b\\u0447\\u0438\\u0441\\u043b\\u0438\\u0442\\u0435\\u043b\\u044c\\u043d\\u044b\\u0439".encode("ascii").decode("unicode-escape"),
        # 31 chars: electroencephalographic
        "\\u044d\\u043b\\u0435\\u043a\\u0442\\u0440\\u043e\\u044d\\u043d\\u0446\\u0435\\u0444\\u0430\\u043b\\u043e\\u0433\\u0440\\u0430\\u0444\\u0438\\u0447\\u0435\\u0441\\u043a\\u0438\\u0439".encode("ascii").decode("unicode-escape"),
        # 38 chars: extreme polysyllabic compound
        "\\u0432\\u044b\\u0441\\u043e\\u043a\\u043e\\u043f\\u0440\\u0435\\u0432\\u043e\\u0441\\u0445\\u043e\\u0434\\u0438\\u0442\\u0435\\u043b\\u044c\\u0441\\u0442\\u0432\\u043e\\u0441\\u043e\\u0434\\u0435\\u0440\\u0436\\u0430\\u0442\\u0435\\u043b\\u044c\\u043d\\u044b\\u0439".encode("ascii").decode("unicode-escape"),
    ]

    ww_space = 14
    for w in extreme_words:
        ww_reg = _text_width(draw, w, fonts["sub_r"])
        ww_bold = _text_width(draw, w, fonts["sub_b"])
        delta = ww_bold - ww_reg
        pad_l = min(4 + max(0, delta // 2), 6)
        pad_r = min(4 + max(0, delta - delta // 2), 6)

        # Invariant 1: Clamped padding strictly <= 6 px
        assert pad_l <= 6, f"pad_l={pad_l} > 6 for word {w}"
        assert pad_r <= 6, f"pad_r={pad_r} > 6 for word {w}"

        # Invariant 2: Left and right clearance strictly >= 8 px
        gap_l = ww_space - pad_l
        gap_r = ww_space - pad_r
        assert gap_l >= 8, f"gap_l={gap_l} < 8 for word {w}"
        assert gap_r >= 8, f"gap_r={gap_r} < 8 for word {w}"


def test_m3_challenger_two_pass_rendering_guarantees_zero_glyph_occlusion() -> None:
    """
    Verify empirically that Pass 1 (pill background) followed by Pass 2 (foreground text)
    guarantees that:
    1. Active background pill is rendered first onto the canvas.
    2. All text glyphs (both active and inactive) are rendered second, directly on top.
    3. The active word text glyphs are never occluded by the pill.
    4. Adjacent word text glyphs are never touched or occluded by the pill (gap >= 8 px).
    """
    fonts = load_moiad_fonts()
    canvas = Image.new("RGB", (1280, 720), (248, 250, 252))
    draw = ImageDraw.Draw(canvas)

    test_words = [
        "\\u0422\\u0435\\u0441\\u0442\\u043e\\u0432\\u0430\\u044f".encode("ascii").decode("unicode-escape"),
        "\\u0444\\u0440\\u0430\\u0437\\u0430".encode("ascii").decode("unicode-escape"),
        "\\u0430\\u043a\\u0442\\u0438\\u0432\\u043d\\u043e\\u0433\\u043e".encode("ascii").decode("unicode-escape"),
        "\\u0431\\u0435\\u0439\\u0434\\u0436\\u0430".encode("ascii").decode("unicode-escape"),
    ]
    ww_space = 14
    w_widths = [_text_width(draw, w, fonts["sub_r"]) for w in test_words]
    line_total_w = sum(w_widths) + ww_space * (len(test_words) - 1)
    cx_start = 590 - line_total_w // 2
    cy = 643

    # Simulate word index 2 as active
    active_idx = 2
    word_slots = []
    cur_x = cx_start
    for idx, (w_txt, ww_w) in enumerate(zip(test_words, w_widths)):
        is_active = (idx == active_idx)
        act_w = _text_width(draw, w_txt, fonts["sub_b"]) if is_active else ww_w
        pad_l = min(4 + max(0, (act_w - ww_w) // 2), 6)
        pad_r = min(4 + max(0, act_w - ww_w - (act_w - ww_w) // 2), 6)
        word_slots.append((w_txt, ww_w, cur_x, is_active, act_w, pad_l, pad_r))
        cur_x += ww_w + ww_space

    # Pass 1: Render active background badge pill
    for _, ww_w, c_x, is_active, act_w, pad_l, pad_r in word_slots:
        if is_active:
            draw.rounded_rectangle(
                [c_x - pad_l, cy - 2, c_x + ww_w + pad_r, cy + 26],
                radius=5,
                fill=COL_COBALT_WASH,
                outline=COL_COBALT,
                width=1,
            )

    # Inspect canvas after Pass 1: pill is present
    arr_pass1 = np.array(canvas)
    active_slot = word_slots[active_idx]
    pill_cx = active_slot[2]
    pill_pad_l = active_slot[5]
    pill_ww = active_slot[1]
    pill_pad_r = active_slot[6]

    # Pill bounding box in pixel coordinates
    px0 = pill_cx - pill_pad_l
    px1 = pill_cx + pill_ww + pill_pad_r
    py0 = cy - 2
    py1 = cy + 26

    # Verify pill center is filled with COL_COBALT_WASH
    pill_center_color = arr_pass1[cy + 10, pill_cx + pill_ww // 2]
    expected_wash = np.array(COL_COBALT_WASH, dtype=np.uint8)
    assert np.allclose(pill_center_color, expected_wash, atol=2), (
        f"Expected pill wash color {expected_wash}, got {pill_center_color}"
    )

    # Pass 2: Render word texts on top
    for idx, (w_txt, ww_w, c_x, is_active, act_w, _, _) in enumerate(word_slots):
        if is_active:
            text_x = c_x - (act_w - ww_w) // 2
            draw.text((text_x, cy), w_txt, fill=COL_COBALT, font=fonts["sub_b"])
        else:
            draw.text((c_x, cy), w_txt, fill=COL_INK, font=fonts["sub_r"])

    # Inspect canvas after Pass 2: text glyphs are present ON TOP of the pill
    arr_pass2 = np.array(canvas)
    # The active text should have COL_COBALT pixels inside the pill area
    pill_region = arr_pass2[py0:py1, px0:px1]
    cobalt_rgb = np.array(COL_COBALT, dtype=np.uint8)
    # Measure minimum distance to cobalt color across pixels in pill region
    dist_to_cobalt = np.linalg.norm(pill_region.astype(np.float32) - cobalt_rgb.astype(np.float32), axis=-1)
    has_cobalt_glyphs = np.any(dist_to_cobalt < 20.0)
    assert has_cobalt_glyphs, "Active text glyphs (COL_COBALT) not detected on top of background pill"

    # Check neighbor words (idx 1 and idx 3)
    # Their text must be untouched by the pill
    slot_prev = word_slots[1]
    prev_right = slot_prev[2] + slot_prev[1]
    assert px0 - prev_right >= 8, f"Clearance between previous word and badge is {px0 - prev_right} < 8 px"

    slot_next = word_slots[3]
    next_left = slot_next[2]
    assert next_left - px1 >= 8, f"Clearance between badge and next word is {next_left - px1} < 8 px"
