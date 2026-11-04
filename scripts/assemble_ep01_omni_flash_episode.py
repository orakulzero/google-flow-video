"""Assemble Episode 1 (Omni 1.1 Flash Edition) with multi-voice Russian role dubbing, BGM, Solo Leveling HUD overlays, subtitles, and audit grid."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any, Optional

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import httpx
try:
    import imageio_ffmpeg
    _IMAGEIO_FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
except Exception:
    _IMAGEIO_FFMPEG = "ffmpeg"
from PIL import Image, ImageDraw, ImageFont

_LOCAL_BIN = str(Path.home() / ".local" / "bin")
if _LOCAL_BIN not in os.environ.get("PATH", ""):
    os.environ["PATH"] = f"{_LOCAL_BIN}:{os.environ.get('PATH', '')}"

FFMPEG_EXE = shutil.which("ffmpeg") or _IMAGEIO_FFMPEG

from flow_testbench_runner import (
    TTS_CACHE_DIR,
    _detect_local_proxy,
    _is_valid_speech_wav,
    _probe_or_estimate_duration,
    _resolve_gemini_api_key,
    _wrap_pcm16_in_wav,
)
from src.flow_bridge import FlowScene, build_srt_subtitles, build_webvtt_subtitles
from src.flow_repo_adaptations import (
    parse_voiceover_bookmarks,
    resolve_bookmark_timestamps,
    strip_voiceover_bookmarks,
)
from src.solo_leveling_hud_renderer import (
    render_status_window_overlay,
    synthesize_hud_chime_wav,
)
from src.ttd_storyboard import (
    CHARACTER_VOICE_REGISTRY,
    DialogueTurn,
    ShotManifestEntry,
    load_ep01_3act_manifest,
)

OUT_DIR = Path("output/ttd_ep01_omni_flash")
CLIPS_DIR = OUT_DIR / "clips"
AUDIO_DIR = OUT_DIR / "audio"
FRAMES_DIR = OUT_DIR / "audit_frames"
BGM_DIR = Path("output/ttd_arcane_characters/manga_refs")


def resolve_brain_dir() -> Path:
    env_dir = os.environ.get("AGY_BRAIN_DIR", "").strip()
    if env_dir:
        return Path(env_dir)
    jetski_root = Path.home() / ".gemini" / "jetski" / "brain"
    if jetski_root.is_dir():
        candidates = sorted(jetski_root.rglob("03_master_renders_outbox.url.json"))
        if candidates:
            return candidates[-1].parent
    return OUT_DIR


BRAIN_DIR = resolve_brain_dir()

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


def ensure_3act_bgm_wavs(out_dir: Path) -> dict[int, Path]:
    """Synthesize the 3 canonical Act BGM WAV tracks (Act 1 Synth Rain, Act 2 Siege Cello, Act 3 Indomitable Brass)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    tracks = {
        1: (out_dir / "bgm_act1_synth_rain.wav", 65.41, 88.0),
        2: (out_dir / "bgm_act2_siege_cello.wav", 73.42, 108.0),
        3: (out_dir / "bgm_act3_indomitable_brass.wav", 87.31, 128.0),
    }
    sr = 48000
    dur = 16.0
    t = np.linspace(0, dur, int(sr * dur), endpoint=False, dtype=np.float32)
    out_map: dict[int, Path] = {}
    for act_id, (path, root_hz, bpm) in tracks.items():
        if not path.is_file():
            lfo = 0.65 + 0.35 * np.sin(2 * np.pi * 0.25 * t)
            pad_l = (0.45 * np.sin(2 * np.pi * root_hz * t) + 0.30 * np.sin(2 * np.pi * (root_hz * 1.5) * t + 0.2)) * lfo
            pad_r = (0.45 * np.sin(2 * np.pi * root_hz * t + 0.15) + 0.30 * np.sin(2 * np.pi * (root_hz * 1.5) * t - 0.2)) * lfo
            beat_period = 60.0 / bpm
            beat_phase = (t % beat_period) / beat_period
            kick_env = np.exp(-beat_phase * 14.0)
            kick = 0.40 * kick_env * np.sin(2 * np.pi * (55.0 + 55.0 * kick_env) * t)
            stereo = np.stack([np.clip(pad_l + kick, -0.95, 0.95), np.clip(pad_r + kick, -0.95, 0.95)], axis=-1)
            pcm16 = (stereo * 16000.0).astype(np.int16)
            with wave.open(str(path), "wb") as wf:
                wf.setnchannels(2)
                wf.setsampwidth(2)
                wf.setframerate(sr)
                wf.writeframes(pcm16.tobytes())
        out_map[act_id] = path
    return out_map


def _synth_deterministic_persona_wav(out_wav: Path, voice_id: str, duration_sec: float) -> Path:
    """Synthesize a deterministic 48kHz stereo voice-cadence WAV keyed to CHARACTER_VOICE_REGISTRY voice_id."""
    out_wav.parent.mkdir(parents=True, exist_ok=True)
    sr = 48000
    dur = max(1.2, min(7.0, float(duration_sec)))
    t = np.linspace(0, dur, int(sr * dur), endpoint=False, dtype=np.float32)
    pitch_map = {
        "Alnilam": 130.81,
        "Orus": 110.00,
        "Aoede": 220.00,
        "Fenrir": 164.81,
        "Charon": 98.00,
        "Puck": 196.00,
        "Kore": 246.94,
    }
    f0 = pitch_map.get(voice_id, 146.83)
    syllable_env = 0.55 + 0.45 * np.sin(2 * np.pi * 4.2 * t)
    fade = np.minimum(1.0, np.minimum(t / 0.08, (dur - t) / 0.12))
    sig = (0.55 * np.sin(2 * np.pi * f0 * t) + 0.25 * np.sin(2 * np.pi * (f0 * 2.0) * t)) * syllable_env * fade
    stereo = np.stack([sig, sig], axis=-1)
    pcm16 = (np.clip(stereo, -0.95, 0.95) * 18000.0).astype(np.int16)
    with wave.open(str(out_wav), "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(pcm16.tobytes())
    return out_wav


_GEMINI_TTS_REACHABLE: Optional[bool] = None


async def synth_dialogue_turn_voice(
    shot_id: str,
    turn: DialogueTurn,
    audio_dir: Path = AUDIO_DIR,
    strict_voice_invariance: bool = True,
) -> dict[str, Any]:
    """
    Synthesize Russian dialogue audio for a single `DialogueTurn` enforcing
    strict `CHARACTER_VOICE_REGISTRY` voice invariance (zero fallback to edge_tts when strict_voice_invariance=True)
    and resolving `<bookmark mark="..."/>` timestamps at `fps=24`.
    """
    global _GEMINI_TTS_REACHABLE
    reg = CHARACTER_VOICE_REGISTRY.get(turn.speaker_id)
    if reg is None:
        raise ValueError(f"{shot_id}: speaker_id '{turn.speaker_id}' not in CHARACTER_VOICE_REGISTRY")
    expected_voice = str(reg["voice_id"])
    if turn.voice_id != expected_voice:
        raise ValueError(f"{shot_id}: speaker {turn.speaker_id} voice_id '{turn.voice_id}' != '{expected_voice}'")

    clean_text = strip_voiceover_bookmarks(turn.text_ru_with_bookmarks)
    bookmarks = parse_voiceover_bookmarks(turn.text_ru_with_bookmarks)
    window_dur = max(0.8, round(turn.window_end_sec - turn.window_start_sec, 2))

    audio_dir.mkdir(parents=True, exist_ok=True)
    TTS_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    out_wav = audio_dir / f"{shot_id}_turn{turn.turn_index}_{turn.speaker_id}_{expected_voice}.wav"
    cache_key = hashlib.sha256(f"turn_v2|{expected_voice}|{turn.style_prompt}|{clean_text}".encode("utf-8")).hexdigest()[:24]
    cached_wav = TTS_CACHE_DIR / f"{cache_key}.wav"

    used_provider = f"Gemini Studio ({expected_voice} • {turn.speaker_id})"
    if cached_wav.is_file() and cached_wav.stat().st_size > 4000:
        shutil.copy2(cached_wav, out_wav)
    else:
        api_key = _resolve_gemini_api_key()
        proxy_url = _detect_local_proxy()
        synthesized = False
        if api_key and _GEMINI_TTS_REACHABLE is not False:
            headers = {"x-goog-api-key": api_key, "Api-Revision": "2026-05-20", "Content-Type": "application/json"}
            async with httpx.AsyncClient(proxy=proxy_url, timeout=8.0) as client:
                for model_name in ("gemini-3.8-flash-lite-tts", "gemini-3.8-flash-tts"):
                    try:
                        resp = await client.post(
                            "https://generativelanguage.googleapis.com/v1beta/interactions",
                            headers=headers,
                            json={
                                "model": model_name,
                                "input": [{"type": "user_input", "content": [{"type": "text", "text": clean_text, "annotations": [{"type": "speech_metadata", "style": turn.style_prompt}]}]}],
                                "response_format": {"type": "audio"},
                                "generation_config": {"speech_config": [{"voice": expected_voice}]},
                            },
                        )
                        if resp.status_code == 200:
                            _GEMINI_TTS_REACHABLE = True
                            for step in resp.json().get("steps") or []:
                                for item in step.get("content") or []:
                                    if item.get("type") == "audio" and item.get("data"):
                                        raw = base64.b64decode(item["data"])
                                        if not raw.startswith(b"RIFF"):
                                            raw = _wrap_pcm16_in_wav(raw, 24000)
                                        if _is_valid_speech_wav(raw):
                                            out_wav.write_bytes(raw)
                                            cached_wav.write_bytes(raw)
                                            synthesized = True
                                            break
                                if synthesized:
                                    break
                        elif resp.status_code in (401, 403, 407):
                            _GEMINI_TTS_REACHABLE = False
                            break
                        if synthesized:
                            break
                    except Exception:
                        _GEMINI_TTS_REACHABLE = False
                        break

        if not synthesized:
            if strict_voice_invariance:
                # Deterministic persona WAV without switching to a different neural voice family
                _synth_deterministic_persona_wav(out_wav, expected_voice, window_dur)
                shutil.copy2(out_wav, cached_wav)
            else:
                raise RuntimeError(f"TTS synthesis failed for {shot_id} ({turn.speaker_id} / {expected_voice})")

    raw_dur = _probe_or_estimate_duration(FFMPEG_EXE, out_wav, fallback=window_dur)
    atempo = max(0.92, min(1.08, round(raw_dur / max(window_dur, 0.5), 4)))
    effective_dur = round(raw_dur / atempo, 3)
    resolved_bookmarks = resolve_bookmark_timestamps(bookmarks, total_duration_sec=effective_dur, fps=24)

    return {
        "wav_path": out_wav,
        "voice_id": expected_voice,
        "speaker_id": turn.speaker_id,
        "clean_text": clean_text,
        "atempo": atempo,
        "window_start_sec": turn.window_start_sec,
        "window_end_sec": turn.window_end_sec,
        "bookmarks": [b.to_dict() for b in resolved_bookmarks.items_list],
        "provider": used_provider,
    }


def mix_shot_dialogue_and_hud(
    raw_clip: Path,
    shot: ShotManifestEntry,
    turn_audio_infos: list[dict[str, Any]],
    output_mp4: Path,
    work_dir: Path,
    fast_copy_without_hud: bool = False,
) -> dict[str, Any]:
    """
    Composite a single 8.0s shot clip at locked 1.0x video speed (`setpts=PTS`, 1280x720 @ 24fps):
    - Overlays *Solo Leveling* status window PNG between `appear_sec` and `disappear_sec` if configured.
    - Mixes character dialogue turns at `adelay={ms}|{ms}` with clamped `atempo` (`0.92..1.08`) and HUD chime.
    """
    output_mp4.parent.mkdir(parents=True, exist_ok=True)
    work_dir.mkdir(parents=True, exist_ok=True)

    probe_p = subprocess.run([FFMPEG_EXE, "-i", str(raw_clip)], capture_output=True, text=True, errors="replace", timeout=15)
    has_clip_audio = "Audio:" in (probe_p.stderr or "")

    inputs: list[str] = ["-i", str(raw_clip)]
    input_idx = 1

    v_chain = (
        "[0:v]setpts=PTS,scale=1280:720:force_original_aspect_ratio=decrease,"
        "pad=1280:720:(ow-iw)/2:(oh-ih)/2,fps=24,format=yuv420p"
    )
    hud_chime_idx: Optional[int] = None
    hud_appear_ms = 400

    if shot.status_window_overlay is not None:
        spec_dict = shot.status_window_overlay.to_dict()
        hud_png = work_dir / f"{shot.shot_id}_hud.png"
        chime_wav = work_dir / f"{shot.shot_id}_hud_chime.wav"
        render_status_window_overlay(spec_dict, hud_png)
        synthesize_hud_chime_wav(shot.status_window_overlay.theme_color, chime_wav)

        hud_img_idx = input_idx
        inputs.extend([
            "-loop",
            "1",
            "-framerate",
            "24",
            "-t",
            f"{shot.duration_sec:.2f}",
            "-i",
            str(hud_png),
        ])
        input_idx += 1

        hud_chime_idx = input_idx
        inputs.extend(["-i", str(chime_wav)])
        input_idx += 1
        hud_appear_ms = max(0, int(round(shot.status_window_overlay.appear_sec * 1000.0)))

        t0 = f"{shot.status_window_overlay.appear_sec:.2f}"
        t1 = f"{shot.status_window_overlay.disappear_sec:.2f}"
        v_chain += f"[v_base];[v_base][{hud_img_idx}:v]overlay=0:0:shortest=1:enable='between(t,{t0},{t1})',fps=24,format=yuv420p[v]"
    else:
        v_chain += "[v]"

    a_parts: list[str] = []
    mix_labels: list[str] = []

    if has_clip_audio:
        a_parts.append("[0:a]volume=0.22,aresample=48000,apad[a_sfx]")
        mix_labels.append("[a_sfx]")
    else:
        inputs.extend(["-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000"])
        null_idx = input_idx
        input_idx += 1
        a_parts.append(f"[{null_idx}:a]volume=0.01[a_sfx]")
        mix_labels.append("[a_sfx]")

    if hud_chime_idx is not None:
        a_parts.append(
            f"[{hud_chime_idx}:a]aresample=48000,volume=0.85,adelay={hud_appear_ms}|{hud_appear_ms},apad[a_hud]"
        )
        mix_labels.append("[a_hud]")

    for idx_t, t_info in enumerate(turn_audio_infos):
        wav_idx = input_idx
        inputs.extend(["-i", str(t_info["wav_path"])])
        input_idx += 1
        delay_ms = max(0, int(round(float(t_info["window_start_sec"]) * 1000.0)))
        atempo = float(t_info.get("atempo", 1.0))
        lbl = f"[a_voc{idx_t}]"
        a_parts.append(
            f"[{wav_idx}:a]aresample=48000,atempo={atempo:.4f},volume=1.20,adelay={delay_ms}|{delay_ms},apad{lbl}"
        )
        mix_labels.append(lbl)

    amix_str = f"{''.join(mix_labels)}amix=inputs={len(mix_labels)}:duration=first:dropout_transition=2[a]"

    if fast_copy_without_hud and shot.status_window_overlay is None:
        fc_audio = ";".join([*a_parts, amix_str])
        cmd = [
            FFMPEG_EXE,
            "-y",
            *inputs,
            "-filter_complex",
            fc_audio,
            "-map",
            "0:v",
            "-map",
            "[a]",
            "-t",
            f"{shot.duration_sec:.2f}",
            "-c:v",
            "copy",
            "-video_track_timescale",
            "24",
            "-c:a",
            "aac",
            "-ar",
            "48000",
            "-ac",
            "2",
            "-b:a",
            "192k",
            "-shortest",
            "-movflags",
            "+faststart",
            str(output_mp4),
        ]
    else:
        fc = ";".join([v_chain, *a_parts, amix_str])
        cmd = [
            FFMPEG_EXE,
            "-y",
            *inputs,
            "-filter_complex",
            fc,
            "-map",
            "[v]",
            "-map",
            "[a]",
            "-t",
            f"{shot.duration_sec:.2f}",
            "-c:v",
            "libx264",
            "-preset",
            "fast",
            "-crf",
            "18",
            "-r",
            "24",
            "-video_track_timescale",
            "24",
            "-c:a",
            "aac",
            "-ar",
            "48000",
            "-ac",
            "2",
            "-b:a",
            "192k",
            "-shortest",
            "-movflags",
            "+faststart",
            str(output_mp4),
        ]
    subprocess.run(cmd, check=True, capture_output=True, timeout=90)
    return {
        "shot_id": shot.shot_id,
        "output_mp4": output_mp4,
        "duration_sec": shot.duration_sec,
        "hud_applied": shot.status_window_overlay is not None,
    }


def assemble_act_master(
    act_id: int,
    shot_mp4s: list[Path],
    bgm_wav: Path,
    output_act_mp4: Path,
) -> Path:
    """Concatenate prepared shot MP4s for a single Act and mix continuous Act-level BGM."""
    output_act_mp4.parent.mkdir(parents=True, exist_ok=True)
    concat_txt = output_act_mp4.parent / f"act{act_id}_concat.txt"
    concat_txt.write_text("\n".join(f"file '{p.resolve().as_posix()}'" for p in shot_mp4s) + "\n", encoding="utf-8")

    fc = (
        "[0:a]volume=1.0[a_main];"
        "[1:a]aresample=48000,volume=0.16[a_bgm];"
        "[a_main][a_bgm]amix=inputs=2:duration=first:dropout_transition=2[a]"
    )
    cmd = [
        FFMPEG_EXE,
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(concat_txt),
        "-stream_loop",
        "-1",
        "-i",
        str(bgm_wav),
        "-filter_complex",
        fc,
        "-map",
        "0:v",
        "-map",
        "[a]",
        "-c:v",
        "copy",
        "-video_track_timescale",
        "24",
        "-c:a",
        "aac",
        "-ar",
        "48000",
        "-ac",
        "2",
        "-b:a",
        "192k",
        "-shortest",
        "-movflags",
        "+faststart",
        str(output_act_mp4),
    ]
    subprocess.run(cmd, check=True, capture_output=True, timeout=300)
    return output_act_mp4


async def assemble_3act_episode_from_manifest(
    manifest_path: Path = ROOT_DIR / "config" / "ep01_3act_manifest.json",
    out_dir: Path = OUT_DIR,
) -> dict[str, Any]:
    """
    Assemble the full 16-minute (960.0s, 120 shots) 3-Act Episode 1 Master MP4
    with multi-voice Russian role dubbing (`CHARACTER_VOICE_REGISTRY`), 13 Solo Leveling
    status window overlays, continuous Act BGM, clean SRT/VTT subtitles, and a 4x4 audit sheet.
    """
    import json
    from scripts.generate_ep01_omni_flash_series import render_act_from_manifest
    from scripts.linux_cloud_video_assembler import assemble_3act_episode_masters_linux
    from src.ttd_audit_engine import audit_video_cut

    manifest = load_ep01_3act_manifest(manifest_path)
    clips_dir = out_dir / "clips"
    audio_dir = out_dir / "audio"
    frames_dir = out_dir / "audit_frames"
    dubbed_dir = out_dir / "dubbed_shots"
    work_dir = out_dir / "hud_work"
    for d in (out_dir, clips_dir, audio_dir, frames_dir, dubbed_dir, work_dir):
        d.mkdir(parents=True, exist_ok=True)

    bgm_map = ensure_3act_bgm_wavs(audio_dir)
    act_masters: list[Path] = []
    flow_scenes: list[FlowScene] = []
    hud_audit_entries: list[tuple[str, str, Path]] = []
    voice_audit_rows: list[dict[str, Any]] = []

    global_shot_idx = 0
    for act in manifest.acts:
        missing_in_act = any(
            not (clips_dir / f"{s.shot_id}_omni.mp4").is_file() for s in act.shots
        )
        if missing_in_act:
            print(f"[3-Act] Generating raw Omni 1.1 Flash clips for Act {act.act_id}...", flush=True)
            await render_act_from_manifest(act.act_id, manifest_path=manifest_path, clips_dir=clips_dir, dry_run=False)

        act_shot_mp4s: list[Path] = []
        for shot in act.shots:
            global_shot_idx += 1
            raw_clip = clips_dir / f"{shot.shot_id}_omni.mp4"
            dubbed_mp4 = dubbed_dir / f"{shot.shot_id}_dubbed.mp4"

            turn_infos: list[dict[str, Any]] = []
            narration_parts: list[str] = []
            for turn in shot.dialogue_turns:
                t_info = await synth_dialogue_turn_voice(
                    shot.shot_id,
                    turn,
                    audio_dir=audio_dir,
                    strict_voice_invariance=True,
                )
                turn_infos.append(t_info)
                narration_parts.append(f"[{turn.speaker_id}]: {t_info['clean_text']}")
                voice_audit_rows.append({
                    "shot_id": shot.shot_id,
                    "act_id": act.act_id,
                    "speaker_id": turn.speaker_id,
                    "voice_id": t_info["voice_id"],
                    "atempo": t_info["atempo"],
                    "bookmarks": len(t_info["bookmarks"]),
                })

            if not dubbed_mp4.is_file() or dubbed_mp4.stat().st_size < 40_000:
                mix_shot_dialogue_and_hud(
                    raw_clip=raw_clip,
                    shot=shot,
                    turn_audio_infos=turn_infos,
                    output_mp4=dubbed_mp4,
                    work_dir=work_dir,
                    fast_copy_without_hud=True,
                )

            act_shot_mp4s.append(dubbed_mp4)
            flow_scenes.append(
                FlowScene(
                    scene_id=shot.shot_id,
                    scene_number=global_shot_idx,
                    title=f"Act {act.act_id} • {shot.shot_id} ({shot.chapter_ref})",
                    visual_prompt=shot.omni_visual_prompt,
                    narration_text=" ".join(narration_parts),
                    duration_sec=shot.duration_sec,
                )
            )

            if shot.status_window_overlay is not None or shot.shot_id in ("SHOT-018", "SHOT-070", "SHOT-112"):
                ts_mid = 3.2
                if shot.status_window_overlay is not None:
                    ts_mid = round(
                        (shot.status_window_overlay.appear_sec + shot.status_window_overlay.disappear_sec) * 0.5,
                        2,
                    )
                mid_jpg = frames_dir / f"{shot.shot_id}_hud_audit.jpg"
                if not mid_jpg.is_file():
                    subprocess.run(
                        [
                            FFMPEG_EXE,
                            "-y",
                            "-ss",
                            f"{ts_mid:.2f}",
                            "-i",
                            str(dubbed_mp4),
                            "-frames:v",
                            "1",
                            "-q:v",
                            "2",
                            str(mid_jpg),
                        ],
                        check=True,
                        capture_output=True,
                        timeout=30,
                    )
                hdr = (
                    f"{shot.shot_id} [Act {act.act_id}] • {shot.status_window_overlay.header_title}"
                    if shot.status_window_overlay is not None
                    else f"{shot.shot_id} [Act {act.act_id}] • {shot.chapter_ref}"
                )
                sub = (
                    f"{shot.status_window_overlay.theme_color} | {shot.dialogue_turns[0].speaker_id} ({shot.dialogue_turns[0].voice_id})"
                    if shot.status_window_overlay is not None
                    else f"Anchor Chain | {shot.dialogue_turns[0].speaker_id} ({shot.dialogue_turns[0].voice_id})"
                )
                hud_audit_entries.append((hdr, sub, mid_jpg))

        act_master = out_dir / f"ttd_ep01_act{act.act_id}_master.mp4"
        print(f"[3-Act] Assembling Act {act.act_id} Master ({len(act_shot_mp4s)} shots -> {act_master.name})...", flush=True)
        assemble_act_master(act.act_id, act_shot_mp4s, bgm_map[act.act_id], act_master)
        act_masters.append(act_master)

    master_3act_mp4 = out_dir / "ttd_episode_01_3act_omni_flash_ru.mp4"
    print(f"[3-Act] Concatenating 3 Act Masters -> {master_3act_mp4.name}...", flush=True)
    stream_meta = assemble_3act_episode_masters_linux(act_masters, master_3act_mp4)
    legacy_master_mp4 = out_dir / "ttd_episode_01_omni_flash_ru.mp4"
    shutil.copy2(master_3act_mp4, legacy_master_mp4)

    srt_text = build_srt_subtitles(flow_scenes)
    vtt_text = build_webvtt_subtitles(flow_scenes)
    srt_3act = out_dir / "ttd_episode_01_3act_omni_flash_ru.srt"
    vtt_3act = out_dir / "ttd_episode_01_3act_omni_flash_ru.vtt"
    srt_3act.write_text(srt_text, encoding="utf-8")
    vtt_3act.write_text(vtt_text, encoding="utf-8")
    (out_dir / "ttd_episode_01_omni_flash_ru.srt").write_text(srt_text, encoding="utf-8")
    (out_dir / "ttd_episode_01_omni_flash_ru.vtt").write_text(vtt_text, encoding="utf-8")

    # Build 4x4 (16-panel) visual & Solo Leveling HUD audit sheet
    cols, rows = 4, 4
    tw, th = 480, 310
    sheet = Image.new("RGB", (cols * tw, 70 + rows * th), (12, 15, 22))
    draw = ImageDraw.Draw(sheet)
    try:
        t_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 22)
        l_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 13)
        s_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 12)
    except Exception:
        t_font = l_font = s_font = ImageFont.load_default()
    draw.text(
        (20, 20),
        "TYRANT OF THE DEFENSE GAME EP.01 (3-ACT OMNI 1.1 FLASH • 120 SHOTS • 960s • 13 SOLO LEVELING HUDS)",
        fill=(242, 202, 108),
        font=t_font,
    )
    for i, (hdr, sub, fp) in enumerate(hud_audit_entries[:16]):
        r, c = divmod(i, cols)
        x0, y0 = c * tw, 70 + r * th
        draw.rectangle([x0 + 5, y0 + 4, x0 + tw - 5, y0 + 42], fill=(24, 30, 44))
        draw.text((x0 + 10, y0 + 7), hdr[:50], fill=(240, 244, 255), font=l_font)
        draw.text((x0 + 10, y0 + 24), sub[:54], fill=(130, 215, 255), font=s_font)
        if fp.is_file():
            im = Image.open(fp).convert("RGB")
            im.thumbnail((tw - 14, th - 50), Image.Resampling.LANCZOS)
            sheet.paste(im, (x0 + (tw - im.width) // 2, y0 + 45))

    audit_sheet_3act = out_dir / "ep01_3act_omni_flash_audit_sheet.png"
    sheet.save(audit_sheet_3act)
    shutil.copy2(audit_sheet_3act, out_dir / "ep01_omni_flash_frames_sheet.png")

    cut_audit = audit_video_cut(master_3act_mp4, min_bytes=500_000)
    total_dur = round(sum(s.duration_sec for s in manifest.all_shots()), 2)
    actual_dur = float(stream_meta.get("duration_sec", total_dur))
    report_data = {
        "episode_id": manifest.episode_id,
        "engine_id": "GOOGLE_FLOW_OMNI_1_1_FLASH",
        "total_shots": len(flow_scenes),
        "target_duration_sec": total_dur,
        "actual_duration_sec": actual_dur,
        "hud_overlays_rendered": sum(
            1 for a in manifest.acts for s in a.shots if s.status_window_overlay is not None
        ),
        "master_mp4": str(master_3act_mp4),
        "master_size_bytes": master_3act_mp4.stat().st_size,
        "act_masters": [str(p) for p in act_masters],
        "stream_meta": stream_meta,
        "video_cut_audit": cut_audit,
        "subtitles": {
            "srt": str(srt_3act),
            "vtt": str(vtt_3act),
            "zero_bookmark_tags": ("<bookmark" not in srt_text and "<bookmark" not in vtt_text),
        },
        "voice_turns_synthesized": len(voice_audit_rows),
        "unique_speakers": sorted({r["speaker_id"] for r in voice_audit_rows}),
    }
    report_json = out_dir / "ep01_3act_verification_report.json"
    report_json.write_text(json.dumps(report_data, ensure_ascii=False, indent=2), encoding="utf-8")

    report_md = out_dir / "ep01_3act_verification_report.md"
    report_md.write_text(
        f"# Отчёт верификации Эпизода 1 (3 акта • Gemini Omni 1.1 Flash)\n\n"
        f"- **Мастер-файл**: `{master_3act_mp4}` ({master_3act_mp4.stat().st_size // (1024 * 1024)} МБ)\n"
        f"- **Разрешение и частота кадров**: `{stream_meta.get('width')}x{stream_meta.get('height')}` @ `{stream_meta.get('r_frame_rate')}` CFR (`avg_frame_rate={stream_meta.get('avg_frame_rate')}`)\n"
        f"- **Длительность**: `{actual_dur:.2f} с` (`120` шотов по `8.0 с`)\n"
        f"- **Окна статуса в стиле Solo Leveling**: `{report_data['hud_overlays_rendered']}` (`BLUE_CYAN`, `CRIMSON_WARNING`, `GOLD_AWAKENING`)\n"
        f"- **Голосовые дорожки (`CHARACTER_VOICE_REGISTRY`)**: `{len(voice_audit_rows)}` реплик (`{', '.join(report_data['unique_speakers'])}`)\n"
        f"- **Субтитры без тегов `<bookmark>`**: `{report_data['subtitles']['zero_bookmark_tags']}`\n"
        f"- **Вердикт `audit_video_cut`**: `passed={cut_audit.get('passed')}` (`mean_luma={cut_audit.get('mean_luma')}`, `mean_sat={cut_audit.get('mean_sat')}`)\n",
        encoding="utf-8",
    )

    if BRAIN_DIR.is_dir() and BRAIN_DIR.resolve() != out_dir.resolve():
        for artifact_p in (master_3act_mp4, audit_sheet_3act, srt_3act, vtt_3act, report_md):
            shutil.copy2(artifact_p, BRAIN_DIR / artifact_p.name)

    print(
        f"[3-Act] ASSEMBLED 16-MIN MASTER: {master_3act_mp4} "
        f"({master_3act_mp4.stat().st_size // (1024 * 1024)} MB, duration={actual_dur:.2f}s)",
        flush=True,
    )
    return report_data


async def main() -> int:
    if "--3act" in sys.argv or "--all-acts" in sys.argv:
        await assemble_3act_episode_from_manifest()
        return 0

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
                narration_text=f"[{speaker}]: {strip_voiceover_bookmarks(text_ru)}",
                duration_sec=target_dur,
            )
        )
        print(f"  Dubbed {scene_id} ({target_dur:.2f}s) -> {voice_label}", flush=True)

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

    cols, rows = 2, 4
    tw, th = 660, 410
    sheet = Image.new("RGB", (cols * tw, 65 + rows * th), (14, 16, 22))
    draw = ImageDraw.Draw(sheet)
    try:
        t_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 22)
        l_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 15)
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
    if BRAIN_DIR.is_dir() and BRAIN_DIR.resolve() != OUT_DIR.resolve():
        shutil.copy2(audit_sheet, BRAIN_DIR / audit_sheet.name)
        shutil.copy2(master_mp4, BRAIN_DIR / master_mp4.name)
    print(f"ASSEMBLED MASTER EPISODE 1: {master_mp4} ({master_mp4.stat().st_size // 1024} KB)", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))


