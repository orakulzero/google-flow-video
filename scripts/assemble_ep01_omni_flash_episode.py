"""Assemble Episode 1 (Omni 1.1 Flash Edition) with multi-voice Russian role dubbing, BGM, subtitles, and audit grid."""

from __future__ import annotations

import asyncio
import base64
import hashlib
from pathlib import Path
import shutil
import subprocess
import sys

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import httpx
import imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFont

FFMPEG_EXE = shutil.which("ffmpeg") or imageio_ffmpeg.get_ffmpeg_exe()

from flow_testbench_runner import (
    TTS_CACHE_DIR,
    _detect_local_proxy,
    _is_valid_speech_wav,
    _probe_or_estimate_duration,
    _resolve_gemini_api_key,
    _wrap_pcm16_in_wav,
)
from src.flow_bridge import FlowScene, build_srt_subtitles, build_webvtt_subtitles

OUT_DIR = Path("output/ttd_ep01_omni_flash")
CLIPS_DIR = OUT_DIR / "clips"
AUDIO_DIR = OUT_DIR / "audio"
FRAMES_DIR = OUT_DIR / "audit_frames"
BGM_DIR = Path("output/ttd_arcane_characters/manga_refs")
BRAIN_DIR = Path(r"C:\Users\Orakul Grey\.gemini\antigravity\brain\94dd6a04-54e7-4e8c-9551-224cace4f85f")

# (scene_id, title_ru, speaker_label, gemini_voice, edge_voice, edge_rate, edge_pitch, style_prompt, dialogue_ru)
EP01_ROLE_SCRIPT = [
    (
        "scene_01",
        "Сцена 01: Прохождение «Защити Империю» и перенос",
        "Эш (Геймер)",
        "Alnilam",
        "ru-RU-DmitryNeural",
        "+6%",
        "+0Hz",
        "excited, breathless young male gamer celebrating victory then shocked by a sudden supernatural portal",
        "Есть! Спустя тысячи попыток я прошёл «Защити Империю» на Адской сложности! Погоди... «Добро пожаловать в настоящий ад»?!",
    ),
    (
        "scene_02",
        "Сцена 02: Пробуждение в теле принца Эша на горящей стене",
        "Принц Эш Эверблэк",
        "Alnilam",
        "ru-RU-DmitryNeural",
        "+2%",
        "-3Hz",
        "tense, battle-shocked young commander waking up under artillery fire",
        "Кровь, гарь и кислотные залпы... Это же нулевой этап! Учебный штурм Передового Форта, где принц Эш погибает в первой же главе!",
    ),
    (
        "scene_03",
        "Сцена 03: Прорыв Легиона Чёрных Пауков",
        "Система / Эш",
        "voice_y0joebp3bwta",
        "ru-RU-SvetlanaNeural",
        "+4%",
        "+0Hz",
        "urgent tactical system alert followed by tense battlefield realization",
        "Тревога: Легион Чёрных Пауков прорвал внешнюю стену! Чёрт, тело принца сковано ужасом — паук-штурмовик сейчас разорвёт меня!",
    ),
    (
        "scene_04",
        "Сцена 04: Золотой рассекающий удар Лукаса Макгрегора",
        "Лукас Макгрегор",
        "Orus",
        "ru-RU-DmitryNeural",
        "+4%",
        "-6Hz",
        "heroic, fiercely loyal knight roaring a battle cry while protecting his commander",
        "Назад, чудовище! Ваше Высочество, держитесь за моей спиной! Пока жив Лукас Макгрегор, ни одна тварь не коснётся моего командира!",
    ),
    (
        "scene_05",
        "Сцена 05: Пробуждение скрытого дара Лили «Огненная кожа»",
        "Лили и Эш",
        "Aoede",
        "ru-RU-SvetlanaNeural",
        "+6%",
        "+4Hz",
        "fiery, defiant female mage reacting to a sudden blade test",
        "Ваше Высочество, вы спятили — кидаться с кинжалом на своего мага?! Зато твой скрытый дар «Огненная кожа» сделает тебя неуязвимым танком!",
    ),
    (
        "scene_06",
        "Сцена 06: Смена класса: Дэмиен — снайпер, Кен — диверсант",
        "Дэмиен и Кен",
        "Fenrir",
        "ru-RU-DmitryNeural",
        "+8%",
        "+6Hz",
        "nervous young priest gaining supernatural sniper resolve",
        "Я всего лишь жрец низшего ранга, мои руки дрожат... Сними сутану и возьми мушкет, Дэмиен! Твоё «Всевидящее Око» бьёт без промаха!",
    ),
    (
        "scene_07",
        "Сцена 07: Рассвет 1 марта — Приказ перегрузить Мана-Пушку",
        "Командир Эш Эверблэк",
        "Alnilam",
        "ru-RU-DmitryNeural",
        "+4%",
        "-4Hz",
        "commanding, ruthless military tyrant ordering an all-in artillery overload",
        "Рассвет первого марта! Сорвать ограничитель с Древней Мана-Пушки! Вложите всю ману крепости в один залп — наводите по моей карте!",
    ),
    (
        "scene_08",
        "Сцена 08: Залп Древней Мана-Пушки по Чёрной Паучьей Королеве",
        "Дэмиен и Эш",
        "Alnilam",
        "ru-RU-DmitryNeural",
        "+3%",
        "-2Hz",
        "triumphant, coldly resolute commander as the mana cannon obliterates the boss",
        "Чёрная Паучья Королева на прицеле — огонь из Мана-Пушки! Мы пережили невозможный пролог. Теперь начинается настоящая оборонительная игра!",
    ),
]


async def synth_role_voice(
    scene_id: str,
    speaker: str,
    gemini_voice: str,
    edge_voice: str,
    edge_rate: str,
    edge_pitch: str,
    style: str,
    text: str,
) -> tuple[Path, str]:
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    TTS_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    out_wav = AUDIO_DIR / f"{scene_id}_voice.wav"
    key = hashlib.sha256(f"role_v1|{gemini_voice}|{edge_pitch}|{text}".encode("utf-8")).hexdigest()[:24]
    cached_wav = TTS_CACHE_DIR / f"{key}.wav"
    if cached_wav.is_file() and cached_wav.stat().st_size > 4000:
        shutil.copy2(cached_wav, out_wav)
        return out_wav, f"Gemini Studio ({gemini_voice} • {speaker})"

    api_key = _resolve_gemini_api_key()
    proxy_url = _detect_local_proxy()
    if api_key:
        headers = {"x-goog-api-key": api_key, "Api-Revision": "2026-05-20", "Content-Type": "application/json"}
        async with httpx.AsyncClient(proxy=proxy_url, timeout=40.0) as client:
            for model_name in ("gemini-3.8-flash-lite-tts", "gemini-3.8-flash-tts"):
                try:
                    resp = await client.post(
                        "https://generativelanguage.googleapis.com/v1beta/interactions",
                        headers=headers,
                        json={
                            "model": model_name,
                            "input": [{"type": "user_input", "content": [{"type": "text", "text": text, "annotations": [{"type": "speech_metadata", "style": style}]}]}],
                            "response_format": {"type": "audio"},
                            "generation_config": {"speech_config": [{"voice": gemini_voice}]},
                        },
                    )
                    if resp.status_code == 200:
                        for step in resp.json().get("steps") or []:
                            for item in step.get("content") or []:
                                if item.get("type") == "audio" and item.get("data"):
                                    raw = base64.b64decode(item["data"])
                                    if not raw.startswith(b"RIFF"):
                                        raw = _wrap_pcm16_in_wav(raw, 24000)
                                    if _is_valid_speech_wav(raw):
                                        out_wav.write_bytes(raw)
                                        cached_wav.write_bytes(raw)
                                        return out_wav, f"Gemini 3.8 Studio ({gemini_voice} • {speaker})"
                except Exception:
                    pass

    import edge_tts
    mp3_p = AUDIO_DIR / f"{scene_id}_edge.mp3"
    comm = edge_tts.Communicate(text, edge_voice, rate=edge_rate, pitch=edge_pitch, proxy=proxy_url)
    await comm.save(str(mp3_p))
    subprocess.run([FFMPEG_EXE, "-y", "-i", str(mp3_p), "-ar", "48000", "-ac", "2", str(out_wav)], check=True, capture_output=True, timeout=30)
    shutil.copy2(out_wav, cached_wav)
    return out_wav, f"Neural Role Dub ({edge_voice} {edge_pitch} • {speaker})"


import wave
import numpy as np


def ensure_cinematic_bgm_wavs(out_dir: Path) -> tuple[Path, Path]:
    """Synthesize rich 48kHz stereo dark-fantasy Arcane cello + war-drum BGM tracks."""
    out_dir.mkdir(parents=True, exist_ok=True)
    battle_wav = out_dir / "bgm_arcane_battle.wav"
    climax_wav = out_dir / "bgm_arcane_climax.wav"
    if battle_wav.is_file() and climax_wav.is_file():
        return battle_wav, climax_wav

    sr = 48000
    dur = 24.0
    t = np.linspace(0, dur, int(sr * dur), endpoint=False, dtype=np.float32)

    for idx, (path, root_hz, tempo_bpm) in enumerate(((battle_wav, 73.42, 100.0), (climax_wav, 87.31, 124.0))):
        # D-minor / F-minor dark cello & brass fifths + octave + slow LFO swell
        lfo = 0.65 + 0.35 * np.sin(2 * np.pi * 0.25 * t)
        pad_l = (
            0.40 * np.sin(2 * np.pi * root_hz * t)
            + 0.28 * np.sin(2 * np.pi * (root_hz * 1.5) * t + 0.3)
            + 0.18 * np.sin(2 * np.pi * (root_hz * 1.2) * t)
            + 0.14 * np.sin(2 * np.pi * (root_hz * 2.0) * t)
        ) * lfo
        pad_r = (
            0.40 * np.sin(2 * np.pi * root_hz * t + 0.15)
            + 0.28 * np.sin(2 * np.pi * (root_hz * 1.5) * t - 0.2)
            + 0.18 * np.sin(2 * np.pi * (root_hz * 1.2) * t + 0.4)
            + 0.14 * np.sin(2 * np.pi * (root_hz * 2.0) * t - 0.1)
        ) * lfo
        # War-drum pulse on every beat
        beat_period = 60.0 / tempo_bpm
        beat_phase = (t % beat_period) / beat_period
        kick_env = np.exp(-beat_phase * 14.0)
        kick = 0.45 * kick_env * np.sin(2 * np.pi * (55.0 + 60.0 * kick_env) * t)

        stereo = np.stack([np.clip(pad_l + kick, -0.95, 0.95), np.clip(pad_r + kick, -0.95, 0.95)], axis=-1)
        pcm16 = (stereo * 18000.0).astype(np.int16)
        with wave.open(str(path), "wb") as wf:
            wf.setnchannels(2)
            wf.setsampwidth(2)
            wf.setframerate(sr)
            wf.writeframes(pcm16.tobytes())
    return battle_wav, climax_wav


async def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    FRAMES_DIR.mkdir(parents=True, exist_ok=True)
    dubbed_DIR = OUT_DIR / "dubbed_scenes"
    dubbed_DIR.mkdir(parents=True, exist_ok=True)

    bgm_battle, bgm_victory = ensure_cinematic_bgm_wavs(AUDIO_DIR)

    flow_scenes: list[FlowScene] = []
    dubbed_mp4s: list[Path] = []
    audit_entries: list[tuple[str, str, Path]] = []

    for idx, (scene_id, title_ru, speaker, g_voice, e_voice, e_rate, e_pitch, style, text_ru) in enumerate(EP01_ROLE_SCRIPT, 1):
        raw_clip = CLIPS_DIR / f"{scene_id}_omni.mp4"
        if not raw_clip.is_file():
            raise FileNotFoundError(f"Missing Omni 1.1 Flash clip: {raw_clip}")

        voice_wav, voice_label = await synth_role_voice(
            scene_id, speaker, g_voice, e_voice, e_rate, e_pitch, style, text_ru
        )
        voice_dur = _probe_or_estimate_duration(FFMPEG_EXE, voice_wav, fallback=7.5)
        clip_dur = _probe_or_estimate_duration(FFMPEG_EXE, raw_clip, fallback=8.0)
        target_dur = max(clip_dur, round(voice_dur + 0.6, 2))

        # Extract mid-point frame from the raw Omni 1.1 Flash clip for visual audit
        mid_frame = FRAMES_DIR / f"{scene_id}_mid.jpg"
        subprocess.run(
            [
                FFMPEG_EXE,
                "-y",
                "-ss",
                f"{min(clip_dur * 0.5, 3.5):.2f}",
                "-i",
                str(raw_clip),
                "-frames:v",
                "1",
                "-q:v",
                "2",
                str(mid_frame),
            ],
            check=True,
            capture_output=True,
            timeout=30,
        )
        audit_entries.append((f"{idx:02d}. {title_ru} [{speaker}]", voice_label, mid_frame))

        bgm_file = bgm_victory if idx >= 7 else bgm_battle
        dubbed_mp4 = dubbed_DIR / f"{scene_id}_dubbed.mp4"

        # Time-stretch or loop video smoothly to match target_dur, mix BGM + role_voice (+ clip SFX if present)
        stretch = max(1.0, target_dur / max(clip_dur, 1.0))
        probe_p = subprocess.run([FFMPEG_EXE, "-i", str(raw_clip)], capture_output=True, text=True, errors="replace", timeout=15)
        has_clip_audio = "Audio:" in (probe_p.stderr or "")
        if has_clip_audio:
            fc = (
                f"[0:v]setpts={stretch:.4f}*PTS,scale=1280:720:force_original_aspect_ratio=decrease,"
                f"pad=1280:720:(ow-iw)/2:(oh-ih)/2,fps=24,format=yuv420p[v];"
                f"[0:a]volume=0.25,apad[a_sfx];"
                f"[1:a]volume=0.20[a_bgm];"
                f"[2:a]volume=1.15,adelay=250|250,apad[a_voc];"
                f"[a_sfx][a_bgm][a_voc]amix=inputs=3:duration=first:dropout_transition=2[a]"
            )
        else:
            fc = (
                f"[0:v]setpts={stretch:.4f}*PTS,scale=1280:720:force_original_aspect_ratio=decrease,"
                f"pad=1280:720:(ow-iw)/2:(oh-ih)/2,fps=24,format=yuv420p[v];"
                f"[1:a]volume=0.22[a_bgm];"
                f"[2:a]volume=1.20,adelay=250|250,apad[a_voc];"
                f"[a_bgm][a_voc]amix=inputs=2:duration=first:dropout_transition=2[a]"
            )
        subprocess.run(
            [
                FFMPEG_EXE,
                "-y",
                "-i",
                str(raw_clip),
                "-stream_loop",
                "-1",
                "-i",
                str(bgm_file),
                "-i",
                str(voice_wav),
                "-filter_complex",
                fc,
                "-map",
                "[v]",
                "-map",
                "[a]",
                "-t",
                f"{target_dur:.2f}",
                "-c:v",
                "libx264",
                "-preset",
                "fast",
                "-crf",
                "19",
                "-c:a",
                "aac",
                "-ar",
                "48000",
                "-b:a",
                "192k",
                str(dubbed_mp4),
            ],
            check=True,
            capture_output=True,
            timeout=90,
        )
        dubbed_mp4s.append(dubbed_mp4)
        flow_scenes.append(
            FlowScene(
                scene_id=scene_id,
                scene_number=idx,
                title=f"{title_ru} ({speaker})",
                visual_prompt=f"Omni 1.1 Flash ({raw_clip.name})",
                narration_text=f"[{speaker}]: {text_ru}",
                duration_sec=target_dur,
            )
        )
        print(f"  Dubbed {scene_id} ({target_dur:.2f}s) -> {voice_label}", flush=True)

    # Concatenate all 8 dubbed clips into Episode 1 Master MP4
    concat_txt = OUT_DIR / "concat_list.txt"
    concat_txt.write_text("\n".join(f"file '{p.resolve().as_posix()}'" for p in dubbed_mp4s), encoding="utf-8")
    master_mp4 = OUT_DIR / "ttd_episode_01_omni_flash_ru.mp4"
    subprocess.run(
        [
            FFMPEG_EXE,
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_txt),
            "-c:v",
            "libx264",
            "-preset",
            "fast",
            "-crf",
            "18",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-movflags",
            "+faststart",
            str(master_mp4),
        ],
        check=True,
        capture_output=True,
        timeout=120,
    )

    vtt_p = OUT_DIR / "ttd_episode_01_omni_flash_ru.vtt"
    srt_p = OUT_DIR / "ttd_episode_01_omni_flash_ru.srt"
    vtt_p.write_text(build_webvtt_subtitles(flow_scenes), encoding="utf-8")
    srt_p.write_text(build_srt_subtitles(flow_scenes), encoding="utf-8")

    # Build 8-Scene Omni 1.1 Flash Visual Audit Sheet
    cols, rows = 2, 4
    tw, th = 660, 410
    sheet = Image.new("RGB", (cols * tw, 65 + rows * th), (14, 16, 22))
    draw = ImageDraw.Draw(sheet)
    try:
        t_font = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", 22)
        l_font = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", 15)
    except Exception:
        t_font = l_font = ImageFont.load_default()
    draw.text((20, 18), "EPISODE 1 OMNI 1.1 FLASH: RENDERED VIDEO KEYFRAMES AUDIT (8 SCENES)", fill=(240, 198, 105), font=t_font)
    for i, (hdr, v_lbl, fp) in enumerate(audit_entries):
        r, c = divmod(i, cols)
        x0, y0 = c * tw, 65 + r * th
        draw.rectangle([x0 + 6, y0 + 4, x0 + tw - 6, y0 + 32], fill=(28, 32, 46))
        draw.text((x0 + 12, y0 + 8), hdr[:62], fill=(240, 240, 248), font=l_font)
        if fp.is_file():
            im = Image.open(fp).convert("RGB")
            im.thumbnail((tw - 16, th - 44), Image.Resampling.LANCZOS)
            sheet.paste(im, (x0 + (tw - im.width) // 2, y0 + 36))

    audit_sheet = OUT_DIR / "ep01_omni_flash_frames_sheet.png"
    sheet.save(audit_sheet)
    shutil.copy2(audit_sheet, BRAIN_DIR / audit_sheet.name)
    shutil.copy2(master_mp4, BRAIN_DIR / master_mp4.name)
    print(f"ASSEMBLED MASTER EPISODE 1: {master_mp4} ({master_mp4.stat().st_size // 1024} KB)", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
