#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
End-to-End 16-Chapter Machine Learning (`MOiAD`) Video Course Renderer
(1280x720 HD @ 24 fps, Almanac Editorial Daylight Style, Studio Female Narration).

Outputs & Mirrors to:
- `e:/ANTIGRAVITY/flow_video_testbench/output/moiad_video_course/`
- `E:/STUDY_NEW_GEN/\u041c\u041e\u0438\u0410\u0414/videos/`
- `E:/STUDY_NEW_GEN/\u041c\u041e\u0438\u0410\u0414/reports/release_final/videos/`
"""

from __future__ import annotations

import argparse
import asyncio
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List

import imageio_ffmpeg
from PIL import Image

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.moiad_chapters_spec import MOIAD_PARTS_SPEC
from scripts.moiad_visual_engines import (
    build_moiad_stage_backdrop,
    load_moiad_fonts,
    render_moiad_chapter_frame,
)
from scripts.render_simple_flow_demo import _align_captions_to_wav
from src.flow_bridge import (
    FlowEducationalCompositor,
    FlowScene,
    build_srt_subtitles,
    build_webvtt_subtitles,
)


async def render_all_moiad_videos(
    force: bool = False,
    target_part: int | None = None,
) -> Dict[str, Any]:
    out_dir = ROOT_DIR / "output" / "moiad_video_course"
    out_dir.mkdir(parents=True, exist_ok=True)

    compositor = FlowEducationalCompositor(width=1280, height=720, fps=24)
    fps = 24
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    fonts = load_moiad_fonts()

    parts_meta: List[Dict[str, Any]] = []
    all_master_scenes: List[FlowScene] = []
    all_part_mp4s: List[Path] = []
    master_keyframes: List[Image.Image] = []

    parts_to_run = (
        [p for p in MOIAD_PARTS_SPEC if p["part_num"] == target_part]
        if target_part is not None
        else MOIAD_PARTS_SPEC
    )

    for part in parts_to_run:
        part_id = part["part_id"]
        part_num = part["part_num"]
        part_scenes_flow: List[FlowScene] = []
        part_ch_mp4s: List[Path] = []
        part_keyframes: List[Image.Image] = []
        part_ch_summaries: List[Dict[str, Any]] = []

        for idx, ch_spec in enumerate(part["chapters"], start=1):
            ch_id = ch_spec["ch_id"]
            narration = ch_spec["narration"]
            flow_sc = FlowScene(
                scene_id=ch_id,
                scene_number=idx,
                title=f"{ch_spec['ch_num']} {ch_spec['title']}",
                visual_prompt=f"Almanac Editorial Daylight ML animation for {ch_id}",
                narration_text=narration,
                tts_narration_text=narration,
                duration_sec=14,
                voice_persona="voice_y0joebp3bwta",
            )

            backdrop_arr = build_moiad_stage_backdrop(ch_spec)
            ch_mp4 = out_dir / f"{ch_id}.mp4"
            ch_vtt = out_dir / f"{ch_id}.vtt"
            ch_srt = out_dir / f"{ch_id}.srt"
            kf_path = out_dir / f"keyframe_{ch_id}.png"

            with tempfile.TemporaryDirectory() as tmp_dir:
                tmp_path = Path(tmp_dir)
                voice_wav = tmp_path / "voiceover.wav"
                dur = await compositor._synthesize_scene_voiceover(
                    scene=flow_sc,
                    language="ru",
                    out_wav=voice_wav,
                )
                total_dur = float(max(dur, 6.0))
                flow_sc.duration_sec = total_dur
                flow_sc.captions = compositor._build_word_captions(
                    scene_id=flow_sc.scene_id,
                    narration_text=narration,
                    duration_sec=total_dur,
                )
                _align_captions_to_wav(flow_sc.captions, voice_wav)

                # Derive physical acoustic sentence boundaries [tau_0, tau_1, tau_2, tau_3, total_dur]
                all_words = getattr(flow_sc.captions, "all_words", []) or []
                sent_starts = [0.0]
                for idx, wt in enumerate(all_words[:-1]):
                    w_txt = wt.word.strip()
                    if w_txt.endswith((".", "!", "?")):
                        sent_starts.append(round(all_words[idx + 1].start_ms / 1000.0, 3))
                if len(sent_starts) >= 4:
                    sb = [0.0, sent_starts[1], sent_starts[2], sent_starts[3], round(total_dur, 3)]
                else:
                    curr = list(sent_starts)
                    while len(curr) < 4:
                        last = curr[-1]
                        step = (total_dur - last) / float(5 - len(curr))
                        curr.append(round(last + step, 3))
                    sb = curr + [round(total_dur, 3)]
                flow_sc.sentence_boundaries = sb
                setattr(flow_sc.captions, "sentence_boundaries", sb)
                part_scenes_flow.append(flow_sc)

                # Write standalone chapter WebVTT and SRT
                single_sc = FlowScene(
                    scene_id=ch_id,
                    scene_number=1,
                    title=flow_sc.title,
                    visual_prompt=flow_sc.visual_prompt,
                    narration_text=narration,
                    tts_narration_text=narration,
                    duration_sec=flow_sc.duration_sec,
                    captions=flow_sc.captions,
                    sentence_boundaries=flow_sc.sentence_boundaries,
                )
                ch_vtt.write_text(build_webvtt_subtitles([single_sc]), encoding="utf-8")
                ch_srt.write_text(build_srt_subtitles([single_sc]), encoding="utf-8")

                n_frames = max(48, int(round(total_dur * fps)))
                kf_step = int(n_frames * 0.65)
                if not force and ch_mp4.exists() and ch_mp4.stat().st_size > 200_000 and kf_path.exists():
                    kf_img = Image.open(kf_path).convert("RGB")
                    part_keyframes.append(kf_img)
                    master_keyframes.append(kf_img)
                else:
                    tmp_mp4 = out_dir / f"_{ch_id}_tmp.mp4"
                    cmd = [
                        ffmpeg_exe,
                        "-y",
                        "-loglevel",
                        "error",
                        "-f",
                        "rawvideo",
                        "-vcodec",
                        "rawvideo",
                        "-s",
                        "1280x720",
                        "-pix_fmt",
                        "rgb24",
                        "-r",
                        str(fps),
                        "-i",
                        "-",
                        "-i",
                        str(voice_wav),
                        "-c:v",
                        "libx264",
                        "-pix_fmt",
                        "yuv420p",
                        "-preset",
                        "ultrafast",
                        "-crf",
                        "18",
                        "-af",
                        f"apad=whole_dur={n_frames / fps:.4f}",
                        "-to",
                        f"{n_frames / fps:.4f}",
                        "-c:a",
                        "aac",
                        "-b:a",
                        "192k",
                        "-ar",
                        "48000",
                        "-ac",
                        "2",
                        "-shortest",
                        "-movflags",
                        "+faststart",
                        str(tmp_mp4),
                    ]
                    proc = subprocess.Popen(
                        cmd,
                        stdin=subprocess.PIPE,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                    assert proc.stdin is not None
                    for s_idx in range(n_frames):
                        u_prog = s_idx / float(max(1, n_frames - 1))
                        frame_rgb = render_moiad_chapter_frame(
                            backdrop_arr,
                            ch_spec,
                            flow_sc,
                            u_prog,
                            fonts,
                            sentence_boundaries=flow_sc.sentence_boundaries,
                        )
                        if s_idx == kf_step:
                            frame_rgb.save(kf_path, format="PNG")
                            part_keyframes.append(frame_rgb)
                            master_keyframes.append(frame_rgb)
                        proc.stdin.write(frame_rgb.tobytes())
                    proc.stdin.close()
                    proc.wait(timeout=180)
                    tmp_mp4.replace(ch_mp4)

            part_ch_mp4s.append(ch_mp4)
            master_sc = FlowScene(
                scene_id=f"master_{ch_id}",
                scene_number=len(all_master_scenes) + 1,
                title=flow_sc.title,
                visual_prompt=flow_sc.visual_prompt,
                narration_text=narration,
                tts_narration_text=narration,
                duration_sec=flow_sc.duration_sec,
                captions=flow_sc.captions,
                sentence_boundaries=flow_sc.sentence_boundaries,
            )
            all_master_scenes.append(master_sc)
            part_ch_summaries.append(
                {
                    "ch_id": ch_id,
                    "hb_id": ch_spec["hb_id"],
                    "ch_num": ch_spec["ch_num"],
                    "title": ch_spec["title"],
                    "duration": round(total_dur, 2),
                    "mp4": ch_mp4.name,
                    "vtt": ch_vtt.name,
                    "keyframe": kf_path.name,
                }
            )
            print(f"[MOIAD] Rendered {ch_id} ({total_dur:.2f}s) -> {ch_mp4.name}", flush=True)

        # Concatenate Part / PR video (`pr1_video.mp4` .. `pr4_video.mp4`)
        part_mp4 = out_dir / f"{part_id}.mp4"
        concat_txt = out_dir / f"{part_id}_concat.txt"
        concat_txt.write_text("\n".join(f"file '{p.name}'" for p in part_ch_mp4s), encoding="utf-8")
        subprocess.run(
            [
                ffmpeg_exe,
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(concat_txt),
                "-filter_complex",
                "[0:v]fps=fps=24.0,setpts=N/(24*TB)[v];[0:a]asetpts=PTS-STARTPTS[a]",
                "-map",
                "[v]",
                "-map",
                "[a]",
                "-c:v",
                "libx264",
                "-crf",
                "18",
                "-preset",
                "ultrafast",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                "-r",
                "24",
                "-vsync",
                "cfr",
                "-shortest",
                "-movflags",
                "+faststart",
                str(part_mp4),
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=180,
        )
        concat_txt.unlink(missing_ok=True)
        all_part_mp4s.append(part_mp4)

        part_vtt = out_dir / f"{part_id}.vtt"
        part_srt = out_dir / f"{part_id}.srt"
        part_vtt.write_text(build_webvtt_subtitles(part_scenes_flow), encoding="utf-8")
        part_srt.write_text(build_srt_subtitles(part_scenes_flow), encoding="utf-8")

        # 2x2 Part Contact Sheet
        cs_img = Image.new("RGB", (2 * 640, 2 * 360), (246, 248, 251))
        for k_i, kf in enumerate(part_keyframes[:4]):
            r_i, c_i = divmod(k_i, 2)
            cs_img.paste(kf.resize((640, 360), Image.Resampling.LANCZOS), (c_i * 640, r_i * 360))
        cs_path = out_dir / f"contact_sheet_pr{part_num}.png"
        cs_img.save(cs_path, format="PNG")

        p_dur = sum(s.duration_sec for s in part_scenes_flow)
        parts_meta.append(
            {
                "part_num": part_num,
                "part_id": part_id,
                "part_title": part["part_title"],
                "mp4": part_mp4.name,
                "vtt": part_vtt.name,
                "srt": part_srt.name,
                "contact_sheet": cs_path.name,
                "duration": round(p_dur, 2),
                "chapters": part_ch_summaries,
            }
        )
        print(f"[MOIAD] Completed Part {part_num}: {part_mp4.name} ({p_dur:.2f}s)", flush=True)

    if target_part is not None:
        moiad_root = Path("E:/STUDY_NEW_GEN/\u041c\u041e\u0438\u0410\u0414")
        if moiad_root.exists():
            for dst_dir in (moiad_root / "videos", moiad_root / "reports" / "release_final" / "videos"):
                dst_dir.mkdir(parents=True, exist_ok=True)
                for item in out_dir.iterdir():
                    if item.is_file():
                        shutil.copy2(item, dst_dir / item.name)
            print(f"[MOIAD] Mirrored Part {target_part} assets to {moiad_root / 'videos'} and release_final/videos", flush=True)
        return {
            "part_num": target_part,
            "part_id": parts_meta[0]["part_id"] if parts_meta else f"pr{target_part}_video",
            "duration": parts_meta[0]["duration"] if parts_meta else 0.0,
            "chapters": parts_meta[0]["chapters"] if parts_meta else [],
            "status": "completed",
        }

    # Concatenate Full Master Course Video
    master_mp4 = out_dir / "moiad_full_video_course.mp4"
    m_concat = out_dir / "master_concat.txt"
    m_concat.write_text("\n".join(f"file '{p.name}'" for p in all_part_mp4s), encoding="utf-8")
    subprocess.run(
        [
            ffmpeg_exe,
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(m_concat),
            "-filter_complex",
            "[0:v]fps=fps=24.0,setpts=N/(24*TB)[v];[0:a]asetpts=PTS-STARTPTS[a]",
            "-map",
            "[v]",
            "-map",
            "[a]",
            "-c:v",
            "libx264",
            "-crf",
            "18",
            "-preset",
            "ultrafast",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-r",
            "24",
            "-vsync",
            "cfr",
            "-shortest",
            "-movflags",
            "+faststart",
            str(master_mp4),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=240,
    )
    m_concat.unlink(missing_ok=True)
    (out_dir / "moiad_full_video_course.vtt").write_text(build_webvtt_subtitles(all_master_scenes), encoding="utf-8")
    (out_dir / "moiad_full_video_course.srt").write_text(build_srt_subtitles(all_master_scenes), encoding="utf-8")

    # 4x4 Master Contact Sheet
    grid_cs = Image.new("RGB", (4 * 480, 4 * 270), (246, 248, 251))
    for idx, kf in enumerate(master_keyframes[:16]):
        r_i, c_i = divmod(idx, 4)
        grid_cs.paste(kf.resize((480, 270), Image.Resampling.LANCZOS), (c_i * 480, r_i * 270))
    master_cs_path = out_dir / "moiad_master_contact_sheet.png"
    grid_cs.save(master_cs_path, format="PNG")

    manifest = {
        "course": "\u041c\u041e\u0438\u0410\u0414 \u2014 \u041f\u043e\u043b\u043d\u044b\u0439 16-\u0433\u043b\u0430\u0432\u043d\u044b\u0439 \u0432\u0438\u0434\u0435\u043e\u043a\u0443\u0440\u0441 (\u041f\u04201..\u041f\u04204)",
        "total_parts": len(parts_meta),
        "total_chapters": len(all_master_scenes),
        "total_duration_sec": round(sum(s.duration_sec for s in all_master_scenes), 2),
        "master_video": master_mp4.name,
        "master_contact_sheet": master_cs_path.name,
        "parts": parts_meta,
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    # Mirror to E:/STUDY_NEW_GEN/\u041c\u041e\u0438\u0410\u0414/videos and reports/release_final/videos
    moiad_root = Path("E:/STUDY_NEW_GEN/\u041c\u041e\u0438\u0410\u0414")
    if moiad_root.exists():
        for dst_dir in (moiad_root / "videos", moiad_root / "reports" / "release_final" / "videos"):
            dst_dir.mkdir(parents=True, exist_ok=True)
            for item in out_dir.iterdir():
                if item.is_file():
                    shutil.copy2(item, dst_dir / item.name)
        print(f"[MOIAD] Mirrored all video assets to {moiad_root / 'videos'} and release_final/videos", flush=True)

    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MOiAD 16-Chapter Video Course Renderer")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force re-rendering of all chapters bypassing cache check",
    )
    parser.add_argument(
        "--part",
        type=int,
        choices=[1, 2, 3, 4],
        default=None,
        help="Optional part number (1..4) to render individually",
    )
    args = parser.parse_args()

    res = asyncio.run(render_all_moiad_videos(force=args.force, target_part=args.part))
    print(json.dumps(res, ensure_ascii=False, indent=2), flush=True)
