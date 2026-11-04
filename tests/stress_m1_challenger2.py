import sys
from pathlib import Path
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))

import time
import numpy as np
from PIL import Image
from flow_bridge import FlowScene, WordTiming, SubtitlePage, SceneCaptions
import flow_testbench_runner as runner


def test_font_cache_performance():
    print("--- [1] Font Cache Performance Test (10,000 queries) ---")
    # Warm up
    _ = runner.get_cached_font(21, bold=True)
    _ = runner.get_cached_font(16, bold=True)
    _ = runner.get_cached_font(24, bold=True)
    _ = runner.get_cached_font(18, bold=False)
    _ = runner.get_cached_font(11, bold=True)

    queries = [
        (21, True),
        (16, True),
        (24, True),
        (18, False),
        (11, True),
    ]

    t0 = time.perf_counter()
    instances = []
    for i in range(10000):
        key = queries[i % len(queries)]
        f = runner.get_cached_font(key[0], bold=key[1])
        if i < 5:
            instances.append(f)
    t1 = time.perf_counter()
    duration_ms = (t1 - t0) * 1000.0

    print(f"Time for 10,000 get_cached_font queries: {duration_ms:.3f} ms")
    assert duration_ms < 50.0, f"Font cache too slow: {duration_ms:.3f} ms >= 50 ms"

    # Verify identical instances
    for idx, key in enumerate(queries):
        f_again = runner.get_cached_font(key[0], bold=key[1])
        assert f_again is instances[idx], f"Font instance mismatch for key {key}"

    print("PASS: Font cache executed 10,000 queries in < 50ms and returned identical objects.")


def test_subtitle_text_overflow():
    print("--- [2] Subtitle Text Overflow Stress Test ---")
    
    # 2.1: 1,000 words narration text
    words_1000 = [f"word{i}" for i in range(1000)]
    text_1000 = " ".join(words_1000)
    dur_ms = 120000

    captions_1000 = runner.compute_scene_word_timings(
        scene_id="stress_1000",
        visual_text=text_1000,
        duration_ms=dur_ms,
    )
    assert len(captions_1000.all_words) == 1000, f"Expected 1000 words, got {len(captions_1000.all_words)}"
    assert len(captions_1000.pages) > 0, "Expected multiple subtitle pages"
    print(f"1000 words mapped to {len(captions_1000.pages)} subtitle pages successfully.")

    # Render frames for 1000 words scene
    scene_1000 = FlowScene(
        scene_id="sc_1000",
        scene_number=1,
        title="1000 Words Stress Scene",
        narration_text=text_1000,
        visual_prompt="test",
        on_screen_bullets=["Stress test with 1000 words in subtitles"],
    )

    frame_bytes = runner.render_scene_frame_pil(
        topic="Stress Topic",
        scene=scene_1000,
        voice_label="Gemini 3.8",
        total_scenes=1,
        frame_idx=150,  # 10s in
        total_frames=1800,
        width=1280,
        height=720,
        fps=15,
        audio_features={"rms": 0.5, "bands": [0.3]*18},
        captions=captions_1000,
    )
    assert len(frame_bytes) == 1280 * 720 * 3, f"Invalid frame buffer size: {len(frame_bytes)}"
    print("PASS: 1,000 words rendered frame without crash or buffer corruption.")

    # 2.2: Single huge word (200 characters without spaces)
    huge_word = "X" * 200
    captions_huge = runner.compute_scene_word_timings(
        scene_id="stress_huge",
        visual_text=huge_word,
        duration_ms=5000,
    )
    assert len(captions_huge.all_words) == 1
    assert captions_huge.all_words[0].word == huge_word
    print(f"Huge word (200 chars) measured width: {captions_huge.all_words[0].width} px")

    scene_huge = FlowScene(
        scene_id="sc_huge",
        scene_number=2,
        title="Huge Word Stress",
        narration_text=huge_word,
        visual_prompt="test",
        on_screen_bullets=["Single unbroken 200 char token"],
    )
    frame_huge = runner.render_scene_frame_pil(
        topic="Stress Topic",
        scene=scene_huge,
        voice_label="Gemini 3.8",
        total_scenes=1,
        frame_idx=15,
        total_frames=75,
        width=1280,
        height=720,
        fps=15,
        captions=captions_huge,
    )
    assert len(frame_huge) == 1280 * 720 * 3
    print("PASS: Huge word (200 chars) rendered without crash.")

    # 2.3: Empty narration text
    captions_empty = runner.compute_scene_word_timings(
        scene_id="stress_empty",
        visual_text="",
        duration_ms=5000,
    )
    assert len(captions_empty.all_words) == 0
    assert len(captions_empty.pages) == 0

    scene_empty = FlowScene(
        scene_id="sc_empty",
        scene_number=3,
        title="Empty Narration Scene",
        narration_text="",
        visual_prompt="test",
        on_screen_bullets=["Empty subtitles test"],
    )
    frame_empty = runner.render_scene_frame_pil(
        topic="Stress Topic",
        scene=scene_empty,
        voice_label="Gemini 3.8",
        total_scenes=1,
        frame_idx=10,
        total_frames=75,
        width=1280,
        height=720,
        fps=15,
        captions=captions_empty,
    )
    assert len(frame_empty) == 1280 * 720 * 3
    print("PASS: Empty narration text rendered without crash.")

    # 2.4: Whitespace and special symbols only
    special_text = "   \t\r\n   !@#$%^&*()_+=-~`{}[]|:;'<>,.?/   \n\t  "
    captions_special = runner.compute_scene_word_timings(
        scene_id="stress_special",
        visual_text=special_text,
        duration_ms=5000,
    )
    scene_special = FlowScene(
        scene_id="sc_special",
        scene_number=4,
        title="Special Symbols Scene",
        narration_text=special_text,
        visual_prompt="test",
        on_screen_bullets=["Special symbols only"],
    )
    frame_special = runner.render_scene_frame_pil(
        topic="Stress Topic",
        scene=scene_special,
        voice_label="Gemini 3.8",
        total_scenes=1,
        frame_idx=10,
        total_frames=75,
        width=1280,
        height=720,
        fps=15,
        captions=captions_special,
    )
    assert len(frame_special) == 1280 * 720 * 3
    print("PASS: Whitespace and special symbols handled cleanly.")


def test_visual_pixel_verification():
    print("--- [3] Visual Pixel RGB Verification Test ---")
    
    # 3-word test sentence: "Alpha Beta Gamma"
    # Duration: 3000 ms. 15 fps => 45 frames (frame_idx 0 to 44)
    # Frame 0 (0 ms): Alpha is active, Beta is future, Gamma is future
    # Frame 22 (1466 ms): Beta is active, Alpha is past, Gamma is future
    # Frame 37 (2466 ms): Gamma is active, Alpha is past, Beta is past
    
    visual_text = "Alpha Beta Gamma"
    dur_ms = 3000
    fps = 15
    total_frames = 45

    captions = runner.compute_scene_word_timings(
        scene_id="pixel_test",
        visual_text=visual_text,
        duration_ms=dur_ms,
    )
    print("Word timings:")
    for wt in captions.all_words:
        print(f"  {wt.word}: start={wt.start_ms}ms, end={wt.end_ms}ms, x={wt.x}, y={wt.y}, w={wt.width}")

    scene = FlowScene(
        scene_id="sc_pixel",
        scene_number=5,
        title="Pixel Color Verification",
        narration_text=visual_text,
        visual_prompt="test",
        on_screen_bullets=["Verify exact RGB values"],
    )

    # Frame 1: inside Word 0 active interval
    t0_ms = (captions.all_words[0].start_ms + captions.all_words[0].end_ms) // 2
    f_idx_0 = int(round(t0_ms * fps / 1000.0))
    raw_0 = runner.render_scene_frame_pil(
        topic="Pixel Test",
        scene=scene,
        voice_label="Gemini 3.8",
        total_scenes=1,
        frame_idx=f_idx_0,
        total_frames=total_frames,
        width=1280,
        height=720,
        fps=fps,
        captions=captions,
    )
    img_0 = Image.frombytes("RGB", (1280, 720), raw_0)
    arr_0 = np.array(img_0)

    # Subtitle bar background check: obsidian (9, 13, 22)
    # Box is (24, 604) to (1256, 702). Sample (50, 620)
    sub_bg = arr_0[620, 50]
    print(f"Subtitle bar background sampled at (50, 620): RGB={tuple(sub_bg)}")
    assert tuple(sub_bg) == (9, 13, 22), f"Expected obsidian background (9, 13, 22), got {tuple(sub_bg)}"

    # Check for presence of Amber-Gold (255, 193, 7)
    amber_gold = np.array([255, 193, 7], dtype=np.uint8)
    sub_region_0 = arr_0[604:702, 24:1256]
    mask_active_0 = np.all(sub_region_0 == amber_gold, axis=-1)
    active_count_0 = np.sum(mask_active_0)
    print(f"Active amber-gold pixels in frame {f_idx_0} (Word 0 active): {active_count_0}")
    assert active_count_0 > 10, f"Expected amber-gold pixels for active word, found {active_count_0}"

    # Check future words: slate gray (100, 116, 139)
    slate_gray = np.array([100, 116, 139], dtype=np.uint8)
    mask_future_0 = np.all(sub_region_0 == slate_gray, axis=-1)
    future_count_0 = np.sum(mask_future_0)
    print(f"Future slate-gray pixels in frame {f_idx_0}: {future_count_0}")
    assert future_count_0 > 10, f"Expected slate-gray pixels for future words, found {future_count_0}"

    # Frame 2: inside Word 1 active interval
    t1_ms = (captions.all_words[1].start_ms + captions.all_words[1].end_ms) // 2
    f_idx_1 = int(round(t1_ms * fps / 1000.0))
    raw_1 = runner.render_scene_frame_pil(
        topic="Pixel Test",
        scene=scene,
        voice_label="Gemini 3.8",
        total_scenes=1,
        frame_idx=f_idx_1,
        total_frames=total_frames,
        width=1280,
        height=720,
        fps=fps,
        captions=captions,
    )
    img_1 = Image.frombytes("RGB", (1280, 720), raw_1)
    arr_1 = np.array(img_1)
    sub_region_1 = arr_1[604:702, 24:1256]

    # In Frame 2:
    # Word 0 is past -> off-white (241, 245, 249)
    # Word 1 is active -> amber-gold (255, 193, 7)
    # Word 2 is future -> slate-gray (100, 116, 139)
    off_white = np.array([241, 245, 249], dtype=np.uint8)
    mask_past_1 = np.all(sub_region_1 == off_white, axis=-1)
    past_count_1 = np.sum(mask_past_1)
    print(f"Past off-white pixels in frame {f_idx_1} (Word 0 past): {past_count_1}")
    assert past_count_1 > 10, f"Expected off-white pixels for past word, found {past_count_1}"

    mask_active_1 = np.all(sub_region_1 == amber_gold, axis=-1)
    active_count_1 = np.sum(mask_active_1)
    print(f"Active amber-gold pixels in frame {f_idx_1} (Word 1 active): {active_count_1}")
    assert active_count_1 > 10, f"Expected amber-gold pixels for active word, found {active_count_1}"

    mask_future_1 = np.all(sub_region_1 == slate_gray, axis=-1)
    future_count_1 = np.sum(mask_future_1)
    print(f"Future slate-gray pixels in frame {f_idx_1} (Word 2 future): {future_count_1}")
    assert future_count_1 > 10, f"Expected slate-gray pixels for future word, found {future_count_1}"

    print("PASS: Pixel RGB verification confirmed amber-gold, obsidian, off-white, and slate-gray.")


def test_fallback_rendering_rgb_verification():
    print("--- [4] Fallback Rendering (captions=None) RGB Verification ---")
    visual_text = "Alpha Beta Gamma Delta Epsilon"
    scene = FlowScene(
        scene_id="sc_fallback_rgb",
        scene_number=6,
        title="Fallback RGB Verification",
        narration_text=visual_text,
        visual_prompt="test",
        on_screen_bullets=["Fallback typography test"],
    )

    # Frame 15 of 30: middle of scene -> should have past, active, future
    raw_fb = runner.render_scene_frame_pil(
        topic="Fallback Test",
        scene=scene,
        voice_label="Gemini 3.8",
        total_scenes=1,
        frame_idx=15,
        total_frames=30,
        width=1280,
        height=720,
        fps=15,
        captions=None,
    )
    img_fb = Image.frombytes("RGB", (1280, 720), raw_fb)
    arr_fb = np.array(img_fb)
    sub_region = arr_fb[604:702, 24:1256]

    amber_gold = np.array([255, 193, 7], dtype=np.uint8)
    obsidian = (9, 13, 22)
    off_white = np.array([241, 245, 249], dtype=np.uint8)
    slate_gray = np.array([100, 116, 139], dtype=np.uint8)

    sub_bg = arr_fb[620, 50]
    assert tuple(sub_bg) == obsidian, f"Expected obsidian background (9, 13, 22), got {tuple(sub_bg)}"

    active_cnt = np.sum(np.all(sub_region == amber_gold, axis=-1))
    past_cnt = np.sum(np.all(sub_region == off_white, axis=-1))
    future_cnt = np.sum(np.all(sub_region == slate_gray, axis=-1))

    print(f"Fallback frame 15/30: active amber={active_cnt}, past white={past_cnt}, future gray={future_cnt}")
    assert active_cnt > 10, f"Expected active amber-gold in fallback, got {active_cnt}"
    assert past_cnt > 10, f"Expected past off-white in fallback, got {past_cnt}"
    assert future_cnt > 10, f"Expected future slate-gray in fallback, got {future_cnt}"
    print("PASS: Fallback rendering path adheres to identical RGB visual palette.")


def test_adversarial_boundary_conditions():
    print("--- [5] Adversarial Boundary Conditions Test ---")
    scene = FlowScene(
        scene_id="sc_boundary",
        scene_number=7,
        title="Boundary Test",
        narration_text="Quick test narration",
        visual_prompt="test",
        on_screen_bullets=["Edge cases"],
    )

    # 5.1: Negative frame index
    raw_neg = runner.render_scene_frame_pil(
        topic="Boundary",
        scene=scene,
        voice_label="Gemini 3.8",
        total_scenes=1,
        frame_idx=-5,
        total_frames=30,
    )
    assert len(raw_neg) == 1280 * 720 * 3
    print("PASS: Negative frame_idx handled gracefully.")

    # 5.2: Frame index beyond total_frames
    raw_over = runner.render_scene_frame_pil(
        topic="Boundary",
        scene=scene,
        voice_label="Gemini 3.8",
        total_scenes=1,
        frame_idx=100,
        total_frames=30,
    )
    assert len(raw_over) == 1280 * 720 * 3
    print("PASS: Overshot frame_idx handled gracefully.")

    # 5.3: Single frame duration
    raw_single = runner.render_scene_frame_pil(
        topic="Boundary",
        scene=scene,
        voice_label="Gemini 3.8",
        total_scenes=1,
        frame_idx=0,
        total_frames=1,
    )
    assert len(raw_single) == 1280 * 720 * 3
    print("PASS: Single frame total_frames=1 handled gracefully.")

    # 5.4: Tiny duration in compute_scene_word_timings
    cap_tiny = runner.compute_scene_word_timings(
        scene_id="tiny_dur",
        visual_text="Short duration test",
        duration_ms=1,
    )
    assert len(cap_tiny.all_words) == 3
    assert cap_tiny.duration_ms == 1
    print("PASS: duration_ms=1 handled without zero division.")


if __name__ == "__main__":
    test_font_cache_performance()
    test_subtitle_text_overflow()
    test_visual_pixel_verification()
    test_fallback_rendering_rgb_verification()
    test_adversarial_boundary_conditions()
    print("\nALL ADVERSARIAL STRESS TESTS COMPLETED SUCCESSFULLY!")
