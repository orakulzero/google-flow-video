import sys
sys.path.insert(0, ".")
import os
import subprocess
import tempfile
import numpy as np
from pathlib import Path
from PIL import Image

import imageio_ffmpeg
from src.flow_bridge import FlowScene
from src.dsp_defense_cycles import DSP_DEFENSE_CYCLES
from flow_testbench_runner import (
    render_scene_frame_pil,
    extract_audio_spectrum_features,
    compute_scene_word_timings,
    get_cached_font,
    OUTPUT_DIR,
)

ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()

# Pick Cycle 1 Scene 1
cycle_data = DSP_DEFENSE_CYCLES[0]
raw_sc = cycle_data["scenes"][0]
src_mp4 = OUTPUT_DIR / cycle_data["slug"] / "scene_01.mp4"
assert src_mp4.is_file(), f"Source mp4 missing: {src_mp4}"

with tempfile.TemporaryDirectory() as tmpdir:
    tmp = Path(tmpdir)
    extracted_audio = tmp / "audio.m4a"
    # Extract audio stream from existing mp4
    cmd_ext = [
        ffmpeg_exe, "-y", "-i", str(src_mp4),
        "-vn", "-c:a", "copy", str(extracted_audio)
    ]
    subprocess.run(cmd_ext, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    # Read duration
    import re
    res = subprocess.run([ffmpeg_exe, "-i", str(extracted_audio)], capture_output=True, text=True, errors="replace")
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", res.stderr)
    duration_sec = float(m.group(1))*3600 + float(m.group(2))*60 + float(m.group(3))
    print(f"Extracted audio duration: {duration_sec:.2f}s")
    
    fps = 15
    total_frames = int(duration_sec * fps)
    
    # Audio features
    audio_features_list = extract_audio_spectrum_features(
        ffmpeg_exe=ffmpeg_exe,
        audio_path=extracted_audio,
        fps=fps,
        total_frames=total_frames,
        num_bands=18,
    )
    
    # Captions
    f_caption = get_cached_font(21, bold=True)
    captions = compute_scene_word_timings(
        scene_id=raw_sc["scene_id"],
        visual_text=raw_sc["narration_text"],
        duration_ms=int(total_frames * 1000 / fps),
        font_caption=f_caption,
        audio_path=extracted_audio,
        ffmpeg_exe=ffmpeg_exe,
    )
    
    sc_obj = FlowScene(
        scene_id=raw_sc["scene_id"],
        scene_number=1,
        title=raw_sc["title"],
        narration_text=raw_sc["narration_text"],
        visual_prompt=raw_sc["visual_prompt"],
        duration_sec=int(duration_sec),
        camera_motion=raw_sc["camera_motion"],
        on_screen_bullets=raw_sc["on_screen_bullets"],
    )
    setattr(sc_obj, "pz_page", raw_sc.get("pz_page", 1))
    setattr(sc_obj, "concept_cues", raw_sc.get("concept_cues", []))
    setattr(sc_obj, "captions", captions)
    
    test_out_mp4 = OUTPUT_DIR / "test_render_scene_01.mp4"
    
    cmd_encode = [
        ffmpeg_exe,
        "-y",
        "-f", "rawvideo",
        "-pix_fmt", "rgb24",
        "-s", "1280x720",
        "-r", str(fps),
        "-i", "pipe:0",
        "-i", str(extracted_audio),
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "18",
        "-pix_fmt", "yuv420p",
        "-c:a", "copy",
        "-shortest",
        "-movflags", "+faststart",
        str(test_out_mp4),
    ]
    
    proc = subprocess.Popen(cmd_encode, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    for f_idx in range(total_frames):
        feat = audio_features_list[f_idx] if f_idx < len(audio_features_list) else None
        frame_bytes = render_scene_frame_pil(
            topic=cycle_data["topic"],
            scene=sc_obj,
            voice_label="Gemini 3.8 Studio (voice_y0joebp3bwta)",
            total_scenes=4,
            frame_idx=f_idx,
            total_frames=total_frames,
            width=1280,
            height=720,
            audio_features=feat,
            fps=fps,
            captions=captions,
        )
        proc.stdin.write(frame_bytes)
    proc.stdin.close()
    _, stderr = proc.communicate()
    assert proc.returncode == 0, f"Encoding failed: {stderr.decode(errors='replace')}"
    
    print(f"Successfully rendered {test_out_mp4} ({test_out_mp4.stat().st_size:,} bytes)")
    
    # Verify dynamics
    cmd_f1 = [ffmpeg_exe, "-ss", str(duration_sec * 0.15), "-i", str(test_out_mp4), "-vframes", "1", "-f", "image2pipe", "-vcodec", "rawvideo", "-pix_fmt", "rgb24", "-"]
    cmd_f2 = [ffmpeg_exe, "-ss", str(duration_sec * 0.85), "-i", str(test_out_mp4), "-vframes", "1", "-f", "image2pipe", "-vcodec", "rawvideo", "-pix_fmt", "rgb24", "-"]
    p1 = subprocess.run(cmd_f1, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    p2 = subprocess.run(cmd_f2, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    a1 = np.frombuffer(p1.stdout, dtype=np.uint8).reshape((720, 1280, 3)).astype(float)
    a2 = np.frombuffer(p2.stdout, dtype=np.uint8).reshape((720, 1280, 3)).astype(float)
    
    diff_l = np.mean(np.abs(a1[66:594, 24:584] - a2[66:594, 24:584]))
    diff_r = np.mean(np.abs(a1[66:594, 596:1256] - a2[66:594, 596:1256]))
    print(f"Verified dynamics: Left diff={diff_l:.2f}, Right diff={diff_r:.2f}")
    assert diff_l > 4.0 and diff_r > 4.0
    print("TEST SCENE RENDER VERIFIED OK!")
