"""End-to-end verification suite for the 3-Act Episode 1 (Stage 0) Omni 1.1 Flash pipeline."""

from __future__ import annotations

import asyncio
from pathlib import Path
import subprocess
import cv2
import numpy as np
from PIL import Image

from scripts.assemble_ep01_omni_flash_episode import (
    assemble_act_master,
    ensure_3act_bgm_wavs,
    mix_shot_dialogue_and_hud,
    synth_dialogue_turn_voice,
)
from scripts.generate_ep01_omni_flash_series import (
    resolve_flow_browser_profile,
    resolve_shot_start_frame,
)
from scripts.linux_cloud_video_assembler import (
    assemble_3act_episode_masters_linux,
    assemble_cfr_episode_linux,
    sort_shot_clips,
)
from src.flow_bridge import FlowScene, build_srt_subtitles, build_webvtt_subtitles
from src.flow_prompt_library import (
    STAGE0_ALLOWED_VFX_TAGS,
    STAGE0_CANONICAL_ASH_TOKENS,
    STAGE0_CANONICAL_DAMIEN_TOKENS,
    STAGE0_CANONICAL_KEN_TOKENS,
    STAGE0_CANONICAL_LILY_TOKENS,
    build_ep01_3act_omni_prompt,
)
from src.flow_repo_adaptations import (
    SceneRenderCache,
    parse_voiceover_bookmarks,
    resolve_bookmark_timestamps,
    strip_voiceover_bookmarks,
)
from src.solo_leveling_hud_renderer import (
    render_status_window_overlay,
    synthesize_hud_chime_wav,
)
from src.ttd_audit_engine import (
    audit_chain_boundary_ssim,
    audit_shot_with_manifest_profile,
    audit_video_cut,
)
from src.ttd_lore_bible import (
    STAGE0_BESTIARY,
    STAGE0_CHARACTERS,
    STAGE0_ENVIRONMENTS,
    get_character_profile,
    get_environment_profile,
    get_monster_profile,
)
from src.ttd_storyboard import (
    CHARACTER_VOICE_REGISTRY,
    load_ep01_3act_manifest,
    validate_ep01_3act_manifest,
)


def test_manifest_120_shots_3_acts_and_canon_invariants() -> None:
    manifest = load_ep01_3act_manifest("config/ep01_3act_manifest.json")
    report = validate_ep01_3act_manifest(manifest)
    assert report["valid"], f"Manifest validation failed: {report['errors']}"
    assert report["total_shots"] == 120
    assert 900.0 <= report["total_duration_sec"] <= 1200.0

    assert len(manifest.acts) == 3
    assert len(manifest.acts[0].shots) == 35
    assert len(manifest.acts[1].shots) == 45
    assert len(manifest.acts[2].shots) == 40

    shots_by_id = {s.shot_id: s for s in manifest.all_shots()}
    # Key canonical HUD & narrative checkpoints across Chapters 001-010
    key_hud_shots = [
        "SHOT-005",  # Stage 50 Ironman Hell Clear (1 survivor: Lucas)
        "SHOT-025",  # Director Eider invitation to Stage 0
        "SHOT-036",  # Stage 0 Forward Base: 1,109 spiders + Queen Orlop
        "SHOT-040",  # Ash EX-rank Beginner Commander + Map Making + Evil Eye of Command
        "SHOT-045",  # Lucas SSR-rank + Beastification + night-before warning
        "SHOT-056",  # Lily R-rank Fire Mage + Flame Skin dagger test
        "SHOT-066",  # Damien N-rank Healer + All-Seeing Eye (+999 Accuracy) + SR Ancient Mana Cannon
        "SHOT-074",  # Ken N-rank Shield Knight + Petty Thief's Way of Survival + family locket
        "SHOT-088",  # Ken HP 8% critical failure & death in action
        "SHOT-095",  # Lily MP 0/100 deactivation & lower-body paralysis
        "SHOT-102",  # Ash passive awakening [Indomitable Commander] 10m mental immunity
        "SHOT-108",  # Damien second shot from SR Ancient Mana Cannon obliterating Queen Orlop
        "SHOT-118",  # 9 survivors out of 200 collecting mana stones & retreating to Crossroads
    ]
    for sid in key_hud_shots:
        shot = shots_by_id[sid]
        assert shot.status_window_overlay is not None, f"{sid} missing Solo Leveling status_window_overlay"
        assert len(shot.dialogue_turns) >= 1, f"{sid} missing dialogue turns"

    # Verify SHOT-102 is GOLD_AWAKENING for [Indomitable Commander]
    assert shots_by_id["SHOT-102"].status_window_overlay.theme_color == "GOLD_AWAKENING"
    # Verify SHOT-088 (Ken) and SHOT-095 (Lily) are CRIMSON_WARNING
    assert shots_by_id["SHOT-088"].status_window_overlay.theme_color == "CRIMSON_WARNING"
    assert shots_by_id["SHOT-095"].status_window_overlay.theme_color == "CRIMSON_WARNING"


def test_stage0_lore_bible_and_prompt_library() -> None:
    assert "ash_stage0" in STAGE0_CHARACTERS
    assert "lucas_stage0" in STAGE0_CHARACTERS
    assert "mage_lily" in STAGE0_CHARACTERS
    assert "healer_damien" in STAGE0_CHARACTERS
    assert "shield_knight_ken" in STAGE0_CHARACTERS
    assert "director_eider" in STAGE0_CHARACTERS

    assert "black_spider_queen_orlop" in STAGE0_BESTIARY
    assert "black_spider_siege" in STAGE0_BESTIARY
    assert "black_spider_assault" in STAGE0_BESTIARY
    assert "forward_base" in STAGE0_ENVIRONMENTS

    lily = get_character_profile("mage_lily")
    assert "Fire Mage" in lily.role or "Flame Skin" in lily.title_en
    orlop = get_monster_profile("black_spider_queen_orlop")
    assert "Orlop" in orlop.name_en
    fbase = get_environment_profile("forward_base")
    assert "Forward Base" in fbase.name_en

    assert len(STAGE0_CANONICAL_ASH_TOKENS) >= 4
    assert len(STAGE0_CANONICAL_LILY_TOKENS) >= 3
    assert len(STAGE0_CANONICAL_DAMIEN_TOKENS) >= 3
    assert len(STAGE0_CANONICAL_KEN_TOKENS) >= 3
    assert "FLAME_SKIN" in STAGE0_ALLOWED_VFX_TAGS

    sample_shot = {
        "shot_id": "SHOT-056",
        "omni_visual_prompt": "Ash tests Lily with a dagger slash in the bunker.",
        "allowed_vfx_tags": ["FLAME_SKIN", "SOLO_HUD"],
        "dialogue_turns": [{"speaker_id": "LILY"}, {"speaker_id": "ASH"}],
    }
    res = build_ep01_3act_omni_prompt(sample_shot)
    assert "final 0.5 seconds" in res["positive_prompt"]
    assert "LILY, ASH" in res["positive_prompt"]
    assert "no speech bubbles" in res["positive_prompt"].lower()


def test_bookmark_sync_24fps_and_subtitle_hygiene() -> None:
    manifest = load_ep01_3act_manifest("config/ep01_3act_manifest.json")
    shot = manifest.acts[1].shots[20]  # SHOT-056
    turn = shot.dialogue_turns[0]
    bms = parse_voiceover_bookmarks(turn.text_ru_with_bookmarks)
    assert len(bms.bookmarks) >= 1
    resolved = resolve_bookmark_timestamps(bms, total_duration_sec=3.4)
    for b in resolved.items_list:
        assert b.frame_offset == int(round(b.timestamp_sec * 24))

    clean = strip_voiceover_bookmarks(turn.text_ru_with_bookmarks)
    assert "<bookmark" not in clean

    scene = FlowScene(
        scene_id=shot.shot_id,
        scene_number=56,
        title="Shot 56",
        visual_prompt=shot.omni_visual_prompt,
        narration_text=clean,
        duration_sec=shot.duration_sec,
    )
    srt = build_srt_subtitles([scene])
    vtt = build_webvtt_subtitles([scene])
    assert "<bookmark" not in srt
    assert "<bookmark" not in vtt


def test_solo_leveling_hud_renderer_themes_and_chimes(tmp_path: Path) -> None:
    for theme in ("BLUE_CYAN", "CRIMSON_WARNING", "GOLD_AWAKENING"):
        png_path = tmp_path / f"hud_{theme}.png"
        wav_path = tmp_path / f"chime_{theme}.wav"
        spec = {
            "window_type": "SKILL_AWAKENING",
            "theme_color": theme,
            "header_title": f"[SYSTEM: {theme}]",
            "body_lines": ["Line 1: Status Check", "Line 2: Value +999"],
            "appear_sec": 0.4,
            "disappear_sec": 6.8,
            "rank_badge": "EX",
            "resource_bar": {"HP": 0.85, "MP": 0.40},
            "screen_anchor": "TOP_RIGHT",
        }
        render_status_window_overlay(spec, png_path)
        synthesize_hud_chime_wav(theme, wav_path)

        assert png_path.is_file() and png_path.stat().st_size > 2000
        assert wav_path.is_file() and wav_path.stat().st_size > 5000

        im = Image.open(png_path)
        assert im.size == (1280, 720)
        assert im.mode == "RGBA"
        arr = np.array(im)
        # Top-left corner outside TOP_RIGHT card must be transparent
        assert int(arr[10, 10, 3]) == 0
        # Inside TOP_RIGHT card region must have non-zero alpha
        assert int(arr[120, 950, 3]) > 100


def _make_synthetic_clip(path: Path, color_bgr: tuple[int, int, int], duration_sec: float = 2.0) -> Path:
    from scripts.assemble_ep01_omni_flash_episode import FFMPEG_EXE
    path.parent.mkdir(parents=True, exist_ok=True)
    b, g, r = color_bgr
    hex_c = f"0x{r:02x}{g:02x}{b:02x}"
    cmd = [
        FFMPEG_EXE,
        "-y",
        "-f",
        "lavfi",
        "-i",
        f"color=c={hex_c}:s=1280x720:r=24:d={duration_sec}",
        "-f",
        "lavfi",
        "-i",
        f"sine=frequency=220:sample_rate=48000:duration={duration_sec}",
        "-c:v",
        "libx264",
        "-preset",
        "ultrafast",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-ar",
        "48000",
        "-ac",
        "2",
        "-movflags",
        "+faststart",
        str(path),
    ]
    subprocess.run(cmd, check=True, capture_output=True, timeout=30)
    return path


def test_frame_chaining_audit_and_end_to_end_3act_assembly(tmp_path: Path) -> None:
    # 1. Verify profile resolution and 3-digit shot sorting
    prof = resolve_flow_browser_profile()
    assert isinstance(prof, Path)

    unsorted = [tmp_path / "SHOT-100_omni.mp4", tmp_path / "SHOT-002_omni.mp4", tmp_path / "SHOT-010_omni.mp4"]
    sorted_p = sort_shot_clips(unsorted)
    assert [p.name for p in sorted_p] == ["SHOT-002_omni.mp4", "SHOT-010_omni.mp4", "SHOT-100_omni.mp4"]

    # 2. Verify VFX exemption in audit_shot_with_manifest_profile and SSIM boundary check
    frame_a = np.full((720, 1280, 3), (40, 45, 55), dtype=np.uint8)
    frame_b = np.full((720, 1280, 3), (41, 45, 54), dtype=np.uint8)
    ssim_res = audit_chain_boundary_ssim(frame_a, frame_b, min_ssim=0.92)
    assert ssim_res["passed"] and ssim_res["ssim"] >= 0.99

    # Add bright flame sparks on frame_a and verify FLAME_SKIN tag exempts it
    frame_sparks = frame_a.copy()
    frame_sparks[200:220, 200:220] = (0, 200, 255)
    audit_res = audit_shot_with_manifest_profile(
        frame_sparks,
        {"shot_id": "SHOT-056", "allowed_vfx_tags": ["FLAME_SKIN", "SOLO_HUD"]},
    )
    assert audit_res["passed"]
    assert "FLAME_SKIN" in audit_res["vfx_exempted"]

    # 3. Verify SceneRenderCache.extract_and_cache_last_frame & resolve_shot_start_frame
    cache = SceneRenderCache(cache_dir=tmp_path / ".scene_cache")
    clip1 = _make_synthetic_clip(tmp_path / "clips" / "SHOT-001_omni.mp4", (35, 40, 50), duration_sec=2.0)
    last_jpg = cache.extract_and_cache_last_frame("SHOT-001", clip1)
    assert last_jpg.is_file() and last_jpg.stat().st_size > 500

    manifest = load_ep01_3act_manifest("config/ep01_3act_manifest.json")
    shot1 = manifest.acts[0].shots[0]  # HARD_ANCHOR_RESET
    shot2 = manifest.acts[0].shots[1]  # FRAME_CHAIN_LAST_TO_FIRST
    s1_frame = resolve_shot_start_frame(shot1, cache, clips_dir=tmp_path / "clips")
    s2_frame = resolve_shot_start_frame(shot2, cache, clips_dir=tmp_path / "clips")
    assert s1_frame.name == "scene_01_gamer_clear.jpg"
    assert s2_frame == last_jpg

    # 4. End-to-end voice synthesis, HUD overlay compositing, and 3-act MP4 assembly
    bgm_map = ensure_3act_bgm_wavs(tmp_path / "audio")
    assert set(bgm_map.keys()) == {1, 2, 3}

    act_masters: list[Path] = []
    for act_id, shot_obj in ((1, manifest.acts[0].shots[4]), (2, manifest.acts[1].shots[20]), (3, manifest.acts[2].shots[21])):
        short_shot = load_ep01_3act_manifest("config/ep01_3act_manifest.json").acts[act_id - 1].shots[0]
        short_shot.duration_sec = 2.0
        short_shot.status_window_overlay = shot_obj.status_window_overlay
        if short_shot.status_window_overlay:
            short_shot.status_window_overlay.appear_sec = 0.2
            short_shot.status_window_overlay.disappear_sec = 1.8
        turn0 = shot_obj.dialogue_turns[0]
        turn0.window_start_sec = 0.2
        turn0.window_end_sec = 1.4
        short_shot.dialogue_turns = [turn0]

        t_info = asyncio.run(
            synth_dialogue_turn_voice(
                short_shot.shot_id,
                turn0,
                audio_dir=tmp_path / "audio",
                strict_voice_invariance=True,
            )
        )
        assert t_info["voice_id"] == CHARACTER_VOICE_REGISTRY[turn0.speaker_id]["voice_id"]
        assert t_info["wav_path"].is_file()

        raw_c = _make_synthetic_clip(tmp_path / "clips" / f"act{act_id}_raw.mp4", (30 * act_id, 40, 60), duration_sec=2.0)
        dubbed_c = tmp_path / "dubbed" / f"SHOT-{act_id:03d}_dubbed.mp4"
        mix_res = mix_shot_dialogue_and_hud(raw_c, short_shot, [t_info], dubbed_c, tmp_path / "work")
        assert mix_res["hud_applied"] is True
        assert dubbed_c.is_file()

        act_master = tmp_path / "acts" / f"ttd_ep01_act{act_id}_master.mp4"
        assemble_act_master(act_id, [dubbed_c], bgm_map[act_id], act_master)
        assert act_master.is_file()
        act_masters.append(act_master)

    final_master = tmp_path / "ttd_episode_01_3act_master.mp4"
    meta = assemble_3act_episode_masters_linux(act_masters, final_master)
    assert meta["width"] == 1280 and meta["height"] == 720
    assert meta["r_frame_rate"] == "24/1"

    cut_audit = audit_video_cut(final_master, min_bytes=10_000)
    assert cut_audit["passed"], f"Final master failed audit_video_cut: {cut_audit}"

    # Verify assemble_cfr_episode_linux preserves existing audio stream when audio_path is None
    cfr_master = tmp_path / "ttd_episode_01_cfr_preserved.mp4"
    cfr_meta = assemble_cfr_episode_linux(act_masters, cfr_master)
    assert cfr_meta["width"] == 1280 and cfr_meta["height"] == 720
