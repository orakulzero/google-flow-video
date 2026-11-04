#!/usr/bin/env python3
"""
Standalone Testbench for Google Flow Educational Video Studio (gemini_local_ui M27).
Location: e:\\ANTIGRAVITY\\flow_video_testbench\\flow_testbench_runner.py

Features:
1. Veo 3.1 Native Audio Prompting (`veo_3_1_t2v_fast_audio` / `gemini-omni-1.1-flash`):
   - Embeds speaker persona, delivery style, prosody/accent cues, quoted dialogue, SFX, and ambience.
2. Expressive Human-Like Voiceover Engine with SSML Prosody & Stress Accents:
   - Tier 1: Live Veo 3.1 Native Audio (`aisandbox-pa.googleapis.com` with `enableAudio=True`)
   - Tier 2: Gemini 3.8 Flash TTS (`gemini-3.8-flash-tts` with `speech_metadata` & `<short pause>`)
   - Tier 3: Silero v4 48kHz Studio Neural TTS (`v4_ru`: `xenia`, `aidar`, `eugene`, `baya` / `v3_en`: `en_0`, `en_21`)
     with automatic neural stress placement (`put_accent=True`, `put_yo=True`), explicit `+` stress accents
     (`трансф+ормер`, `к+эша`, `вним+ания`), and SSML `<prosody>` + `<break>` emphasis on `*accented*` phrases!
3. Renders 1280x720 HD H.264 + AAC (.mp4) educational video lessons + WebVTT (.vtt) + SubRip (.srt)
   and an interactive HTML5 Player & Veo Audio Prompt Inspector (index.html).
"""

from __future__ import annotations

import argparse
import asyncio
import base64
from dataclasses import asdict, dataclass, field
import json
import math
import os
import re
import subprocess
import sys
import tempfile
import wave
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

TESTBENCH_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = TESTBENCH_DIR / "output"

if str(TESTBENCH_DIR) not in sys.path:
    sys.path.insert(0, str(TESTBENCH_DIR))

try:
    from src.flow_bridge import (  # noqa: E402
        BookmarkParseResult,
        CursorFrameState,
        CursorGroundingEngine,
        FlowClient,
        FlowEducationalProject,
        FlowScene,
        ResolvedBookmarkFloat,
        ResolvedBookmarkMap,
        SceneCaptions,
        SceneRenderCache,
        SubtitlePage,
        VoiceoverBookmark,
        WordTiming,
        build_openmaic_lecture_actions,
        build_srt_subtitles,
        build_veo_native_audio_prompt,
        build_webvtt_subtitles,
        cubic_bezier_ease,
        parse_voiceover_bookmarks,
        resolve_bookmark_timestamps,
        strip_voiceover_bookmarks,
    )
except ImportError:
    CANDIDATE_REPOS = [
        Path.home() / "teamwork_projects" / "gemini_local_ui",
        TESTBENCH_DIR.parent / "gemini_local_ui",
    ]
    REPO_ROOT = next((p for p in CANDIDATE_REPOS if (p / "backend" / "app" / "main.py").is_file()), None)
    if REPO_ROOT and str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    from backend.app.bridge.flow import (  # noqa: E402
        FlowClient,
        FlowEducationalProject,
        FlowScene,
        build_srt_subtitles,
        build_veo_native_audio_prompt,
        build_webvtt_subtitles,
    )
    from src.flow_repo_adaptations import (  # noqa: E402
        BookmarkParseResult,
        CursorFrameState,
        CursorGroundingEngine,
        ResolvedBookmarkFloat,
        ResolvedBookmarkMap,
        SceneRenderCache,
        VoiceoverBookmark,
        build_openmaic_lecture_actions,
        cubic_bezier_ease,
        parse_voiceover_bookmarks,
        resolve_bookmark_timestamps,
        strip_voiceover_bookmarks,
    )

import hashlib
import socket

TTS_CACHE_DIR = TESTBENCH_DIR / ".tts_cache"

# Persistent custom Gemini 3.8 Voice Design studio persona (created via POST /v1beta/voices)
RU_FEMALE_VOICE_DESIGN_ID = "voice_y0joebp3bwta"  # Warm Mezzo Russian Science Lecturer

_EXHAUSTED_DAILY_MODELS: set[str] = set()
_ASSET_IMAGE_CACHE: Dict[str, Any] = {}
_PAGE_IMAGE_CACHE: Dict[str, Any] = {}


def _detect_local_proxy() -> Optional[str]:
    """Detect local Clash/Mihomo/Sing-box HTTP proxy on 127.0.0.1 if running."""
    for env_k in ("HTTPS_PROXY", "HTTP_PROXY", "ALL_PROXY"):
        val = os.environ.get(env_k, "").strip()
        if val:
            return val
    for port in (7890, 10808, 2080):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(0.15)
                if s.connect_ex(("127.0.0.1", port)) == 0:
                    return f"http://127.0.0.1:{port}"
        except Exception:
            pass
    return None


def _resolve_gemini_api_key() -> str:
    """Resolve GEMINI_API_KEY from environment or Windows HKCU Environment."""
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if key:
        return key
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as reg:
            val, _ = winreg.QueryValueEx(reg, "GEMINI_API_KEY")
            if val and str(val).strip():
                return str(val).strip()
    except Exception:
        pass
    return ""


def strip_accent_markers(narration_text: str) -> str:
    """Remove *...* prosody markers, <bookmark.../> tags, and + stress markers for clean subtitle text."""
    base_txt = (
        strip_voiceover_bookmarks(narration_text)
        if "<bookmark" in narration_text.lower()
        else narration_text
    )
    no_stars = re.sub(r"\*([^*]+)\*", r"\1", base_txt)
    no_plus = re.sub(r"\+([а-яёА-ЯЁa-zA-Z])", r"\1", no_stars)
    return re.sub(r"\s+", " ", no_plus).strip()


def format_for_gemini_tts(narration_text: str) -> str:
    """
    Format transcript for Gemini 3.8 / 3.1 / 2.5 TTS:
    - Strip inline <bookmark.../> synchronization markers if present.
    - Strip Silero '+' stress markers so the model reads natural words.
    - Convert *accented phrases* to UPPERCASE for natural vocal emphasis without
      inserting artificial mid-sentence breaks.
    - Add <short pause> at major clause boundaries (: and —) for natural lecturer breathing.
    """
    base_txt = (
        strip_voiceover_bookmarks(narration_text)
        if "<bookmark" in narration_text.lower()
        else narration_text
    )
    clean_plus = re.sub(r"\+([а-яёА-ЯЁa-zA-Z])", r"\1", base_txt.strip())

    def _upper_emphasis(match: re.Match[str]) -> str:
        return match.group(1).strip().upper()

    emphasized = re.sub(r"\*([^*]+)\*", _upper_emphasis, clean_plus)
    emphasized = re.sub(r"—\s*", "— <short pause> ", emphasized)
    emphasized = re.sub(r":\s*", ": <short pause> ", emphasized)
    return re.sub(r"\s+", " ", emphasized).strip()


def _wrap_pcm16_in_wav(pcm_bytes: bytes, sample_rate: int = 24000) -> bytes:
    """Wrap raw 16-bit mono PCM bytes (audio/L16) in a standard RIFF WAV container."""
    import io
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_bytes)
    return buf.getvalue()


def _is_valid_speech_wav(wav_bytes: bytes, min_duration_sec: float = 2.8) -> bool:
    """Verify WAV container has sufficient duration and non-silent vocal RMS energy."""
    if len(wav_bytes) < int(min_duration_sec * 24000 * 2):
        return False
    try:
        pcm = np.frombuffer(wav_bytes[44:], dtype=np.int16).astype(np.float32)
        if pcm.size == 0:
            return False
        rms = float(np.sqrt(np.mean(pcm * pcm)))
        return rms > 350.0
    except Exception:
        return len(wav_bytes) > 150_000


def purge_unauthorized_tts_cache(cache_dir: Optional[Path] = None) -> int:
    """
    Purge stale cache files contaminated with unauthorized personas
    (Sulafat, Svetlana, Baritone, Sadaltager on Russian narration).
    """
    purged = 0
    target_dir = cache_dir or TTS_CACHE_DIR
    if not target_dir.is_dir():
        return 0
    candidate_files = list(target_dir.glob("*.txt")) + list(target_dir.glob("*.json"))
    for meta_file in candidate_files:
        try:
            content = meta_file.read_text(encoding="utf-8").strip()
            if any(bad in content for bad in ("Sulafat • Female", "Baritone", "Sadaltager", "Svetlana", '"voice": "Sulafat"')):
                wav_file = meta_file.with_suffix(".wav")
                wav_file.unlink(missing_ok=True)
                meta_file.unlink(missing_ok=True)
                purged += 1
        except Exception:
            pass
    return purged


async def try_gemini_studio_tts(
    narration_text: str,
    out_wav: Path,
    lang: str = "ru",
    scene_number: int = 1,
    voice_persona: Optional[str] = None,
    voice_style: str = "confident, engaging lecture",
    strict_timbre_lock: bool = True,
) -> Optional[Tuple[Path, str]]:
    """
    Synthesize studio human speech using the unified Female Gemini 3.8 Voice Design persona
    (`voice_y0joebp3bwta` for RU / `Sulafat` for EN) via `gemini-3.8-flash-lite-tts` /
    `gemini-3.8-flash-tts` (with RPM backoff retry).
    Uses persona-keyed persistent disk cache `.tts_cache/` (`v3`) so repeated runs consume zero quota
    and eliminates cross-persona timbre leakage.
    """
    is_ru = lang.lower().startswith("ru")
    formatted_text = format_for_gemini_tts(narration_text)

    if is_ru:
        designed_voice = voice_persona or RU_FEMALE_VOICE_DESIGN_ID
        role_tag = "RU Female Warm Mezzo"
    else:
        designed_voice = voice_persona or "Sulafat"
        role_tag = "EN Studio Female (Sulafat)"

    TTS_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_key = hashlib.sha256(f"v3|{lang}|{designed_voice}|{formatted_text}".encode("utf-8")).hexdigest()[:24]
    cached_wav = TTS_CACHE_DIR / f"{cache_key}.wav"
    cached_meta = TTS_CACHE_DIR / f"{cache_key}.txt"
    if cached_wav.is_file():
        existing_bytes = cached_wav.read_bytes()
        cached_label = (
            cached_meta.read_text(encoding="utf-8").strip()
            if cached_meta.is_file()
            else f"Gemini 3.8 Studio ({role_tag})"
        )
        is_leaked = is_ru and any(
            bad in cached_label
            for bad in ("Sulafat", "Svetlana", "Baritone", "Sadaltager", "Male")
        )
        if is_leaked:
            cached_wav.unlink(missing_ok=True)
            cached_meta.unlink(missing_ok=True)
        elif _is_valid_speech_wav(existing_bytes):
            out_wav.write_bytes(existing_bytes)
            return out_wav, cached_label

    api_key = _resolve_gemini_api_key()
    if not api_key:
        return None

    proxy_url = _detect_local_proxy()
    headers = {
        "x-goog-api-key": api_key,
        "Api-Revision": "2026-05-20",
        "Content-Type": "application/json",
    }

    import httpx
    async with httpx.AsyncClient(proxy=proxy_url, timeout=45.0) as client:
        # 1. Primary: Gemini 3.8 TTS models supporting Voice Design & speech_metadata
        for model_name in ("gemini-3.8-flash-lite-tts", "gemini-3.8-flash-tts"):
            if model_name in _EXHAUSTED_DAILY_MODELS:
                continue
            for attempt in range(2):
                try:
                    payload = {
                        "model": model_name,
                        "input": [
                            {
                                "type": "user_input",
                                "content": [
                                    {
                                        "type": "text",
                                        "text": formatted_text,
                                        "annotations": [
                                            {
                                                "type": "speech_metadata",
                                                "style": "confident, engaging lecture",
                                            }
                                        ],
                                    }
                                ],
                            }
                        ],
                        "response_format": {"type": "audio"},
                        "generation_config": {
                            "speech_config": [{"voice": designed_voice}],
                        },
                    }
                    resp = await client.post(
                        "https://generativelanguage.googleapis.com/v1beta/interactions",
                        headers=headers,
                        json=payload,
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        for step in data.get("steps") or []:
                            if step.get("type") == "model_output":
                                for item in step.get("content") or []:
                                    if item.get("type") == "audio" and item.get("data"):
                                        raw_bytes = base64.b64decode(item["data"])
                                        if not raw_bytes.startswith(b"RIFF"):
                                            raw_bytes = _wrap_pcm16_in_wav(raw_bytes, 24000)
                                        if _is_valid_speech_wav(raw_bytes):
                                            out_wav.write_bytes(raw_bytes)
                                            label = f"Gemini 3.8 Studio ({role_tag})"
                                            cached_wav.write_bytes(raw_bytes)
                                            cached_meta.write_text(label, encoding="utf-8")
                                            return out_wav, label
                        break
                    elif resp.status_code == 429:
                        if "per day" in resp.text.lower():
                            _EXHAUSTED_DAILY_MODELS.add(model_name)
                            break
                        await asyncio.sleep(4.0 * (attempt + 1))
                        continue
                    else:
                        break
                except Exception:
                    break

        # 2. Secondary: Gemini 3.1 Flash TTS Preview (no speech_metadata annotation, prebuilt Sulafat)
        # Strictly blocked for Russian when strict_timbre_lock is enabled (R3 single speaker timbre lock)
        if not is_ru and not strict_timbre_lock and "gemini-3.1-flash-tts-preview" not in _EXHAUSTED_DAILY_MODELS:
            prebuilt_voice = "Sulafat"
            plain_text = strip_accent_markers(narration_text)
            try:
                resp = await client.post(
                    "https://generativelanguage.googleapis.com/v1beta/interactions",
                    headers=headers,
                    json={
                        "model": "gemini-3.1-flash-tts-preview",
                        "input": [
                            {
                                "type": "user_input",
                                "content": [{"type": "text", "text": plain_text}],
                            }
                        ],
                        "response_format": {"type": "audio"},
                        "generation_config": {
                            "speech_config": [{"voice": prebuilt_voice}],
                        },
                    },
                )
                if resp.status_code == 200:
                    for step in resp.json().get("steps") or []:
                        if step.get("type") == "model_output":
                            for item in step.get("content") or []:
                                if item.get("type") == "audio" and item.get("data"):
                                    raw_bytes = base64.b64decode(item["data"])
                                    if not raw_bytes.startswith(b"RIFF"):
                                        raw_bytes = _wrap_pcm16_in_wav(raw_bytes, 24000)
                                    if _is_valid_speech_wav(raw_bytes):
                                        out_wav.write_bytes(raw_bytes)
                                        label = f"Gemini Studio ({prebuilt_voice} • Female)"
                                        cached_wav.write_bytes(raw_bytes)
                                        cached_meta.write_text(label, encoding="utf-8")
                                        return out_wav, label
                elif resp.status_code == 429 and "per day" in resp.text.lower():
                    _EXHAUSTED_DAILY_MODELS.add("gemini-3.1-flash-tts-preview")
            except Exception:
                pass

    return None


async def try_edge_neural_tts(
    narration_text: str,
    out_mp3: Path,
    lang: str = "ru",
    scene_number: int = 1,
) -> Optional[Tuple[Path, str]]:
    """High-availability fallback using Microsoft Edge Female Neural TTS via local proxy."""
    try:
        is_ru = lang.lower().startswith("ru")
        clean_text = strip_accent_markers(narration_text)
        if is_ru:
            clean_text = (
                clean_text.replace("MLA", "Эм-Эл-Эй")
                .replace("MoE", "Эм-О-Е")
                .replace("KV-", "Кей-Ви ")
                .replace("KV", "Кей-Ви")
                .replace("Top-K", "Топ-Кей")
            )
            candidates = [("ru-RU-SvetlanaNeural", "Edge Neural RU (Svetlana • Female)")]
        else:
            candidates = [("en-US-EmmaMultilingualNeural", "Edge Neural EN (Emma • Female)")]

        TTS_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        edge_key = hashlib.sha256(f"edge_v1|{lang}|F|{clean_text}".encode("utf-8")).hexdigest()[:24]
        cached_mp3 = TTS_CACHE_DIR / f"{edge_key}.mp3"
        if cached_mp3.is_file() and cached_mp3.stat().st_size > 2000:
            out_mp3.write_bytes(cached_mp3.read_bytes())
            return out_mp3, candidates[0][1]

        import aiohttp
        import edge_tts

        aiohttp.resolver.DefaultResolver = aiohttp.resolver.ThreadedResolver
        proxy_url = _detect_local_proxy()

        for voice_name, label in candidates:
            for _ in range(3):
                try:
                    comm = edge_tts.Communicate(clean_text, voice_name, proxy=proxy_url)
                    audio_buf = b""
                    async for chunk in comm.stream():
                        if chunk["type"] == "audio":
                            audio_buf += chunk["data"]
                    if len(audio_buf) > 2000:
                        out_mp3.write_bytes(audio_buf)
                        cached_mp3.write_bytes(audio_buf)
                        return out_mp3, label
                except Exception:
                    await asyncio.sleep(0.4)
    except Exception:
        pass
    return None


async def synthesize_neural_expressive_audio(
    ffmpeg_exe: str,
    narration_text: str,
    out_audio_m4a: Path,
    lang: str = "ru",
    scene_number: int = 1,
    voice_persona: str = "voice_y0joebp3bwta",
    voice_style: str = "warm, articulate university lecturer with natural human cadence and clear vocal emphasis on key terms",
) -> Tuple[Path, float, str]:
    """
    Synthesize human-grade expressive voiceover with prosodic accents and natural breathing pauses.
    Returns (path_to_m4a, duration_seconds, engine_used).
    """
    is_ru = lang.lower().startswith("ru")
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)

        # Tier 1: Gemini 3.8 Studio Voice Design (RU Warm Mezzo / RU Deep Baritone / EN Sulafat & Sadaltager)
        gemini_res = await try_gemini_studio_tts(
            narration_text=narration_text,
            out_wav=tmp_path / "gemini_studio.wav",
            lang=lang,
            scene_number=scene_number,
            voice_persona=voice_persona,
            voice_style=voice_style,
            strict_timbre_lock=True,
        )
        if gemini_res:
            gemini_wav, label = gemini_res
            duration = _probe_or_estimate_duration(ffmpeg_exe, gemini_wav, fallback=6.0) + 0.35
            subprocess.run(
                [
                    ffmpeg_exe,
                    "-y",
                    "-i",
                    str(gemini_wav),
                    "-af",
                    "apad=pad_dur=0.35",
                    "-ar",
                    "48000",
                    "-c:a",
                    "aac",
                    "-b:a",
                    "192k",
                    str(out_audio_m4a),
                ],
                check=True,
                capture_output=True,
            )
            return out_audio_m4a, round(duration, 2), label

        # Fallback to Edge TTS is strictly barred for Russian coursework defense (R3 / R4)
        if is_ru:
            raise RuntimeError(
                f"Strict Single Speaker Timbre lock violation prevented: "
                f"Gemini 3.8 Studio Voice Design ({voice_persona or RU_FEMALE_VOICE_DESIGN_ID}) failed, "
                f"and fallback to SvetlanaNeural/Sulafat is forbidden by R3."
            )

        # Tier 2: Microsoft Edge Neural TTS via local proxy (Svetlana / Dmitry / AndrewMultilingual)
        edge_res = await try_edge_neural_tts(
            narration_text=narration_text,
            out_mp3=tmp_path / "edge_neural.mp3",
            lang=lang,
            scene_number=scene_number,
        )
        if edge_res:
            edge_mp3, label = edge_res
            duration = _probe_or_estimate_duration(ffmpeg_exe, edge_mp3, fallback=6.0) + 0.35
            subprocess.run(
                [
                    ffmpeg_exe,
                    "-y",
                    "-i",
                    str(edge_mp3),
                    "-af",
                    "apad=pad_dur=0.35",
                    "-ar",
                    "48000",
                    "-c:a",
                    "aac",
                    "-b:a",
                    "192k",
                    str(out_audio_m4a),
                ],
                check=True,
                capture_output=True,
            )
            return out_audio_m4a, round(duration, 2), label

        raise RuntimeError("Both Gemini Studio TTS and Edge Neural TTS failed to synthesize audio.")


def _probe_or_estimate_duration(ffmpeg_exe: str, audio_file: Path, fallback: float = 6.0) -> float:
    """Read exact WAV duration using standard library `wave` or `ffmpeg -i` stderr."""
    try:
        with wave.open(str(audio_file), "rb") as wf:
            return max(2.5, round(wf.getnframes() / float(wf.getframerate()), 2))
    except Exception:
        pass
    proc = subprocess.run(
        [ffmpeg_exe, "-i", str(audio_file)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", proc.stderr or "")
    if m:
        h, mins, secs = int(m.group(1)), int(m.group(2)), float(m.group(3))
        return max(2.5, round(h * 3600 + mins * 60 + secs, 2))
    return fallback


def _wrap_text_pixels(text: str, font: Any, max_width: int) -> List[str]:
    """Wrap text into lines guaranteed not to exceed `max_width` pixels."""
    words = text.strip().split()
    if not words:
        return [""]
    lines: List[str] = []
    current = words[0]
    for w in words[1:]:
        candidate = f"{current} {w}"
        try:
            length = font.getlength(candidate)
        except Exception:
            length = len(candidate) * 11
        if length <= max_width:
            current = candidate
        else:
            lines.append(current)
            current = w
    if current:
        lines.append(current)
    return lines


# ---------------------------------------------------------------------------
# Static Font Cache & Font Path Resolution (Zero Disk I/O during rendering)
# ---------------------------------------------------------------------------
_FONT_CACHE: Dict[Tuple[int, bool], Any] = {}
_RESOLVED_FONT_PATH: Optional[str] = None
_RESOLVED_FONT_BOLD_PATH: Optional[str] = None
_FONTS_RESOLVED: bool = False


def get_cached_font(size: int, bold: bool = False) -> Any:
    """
    Return a cached ImageFont instance for (size, bold).
    Eliminates redundant disk I/O and FreeType parsing on every video frame.
    """
    cache_key = (int(size), bool(bold))
    if cache_key in _FONT_CACHE:
        return _FONT_CACHE[cache_key]

    global _RESOLVED_FONT_PATH, _RESOLVED_FONT_BOLD_PATH, _FONTS_RESOLVED
    if not _FONTS_RESOLVED:
        font_paths = [
            "C:/Windows/Fonts/segoeui.ttf",
            "C:/Windows/Fonts/arial.ttf",
            "C:/Windows/Fonts/calibri.ttf",
        ]
        font_bold_paths = [
            "C:/Windows/Fonts/segoeuib.ttf",
            "C:/Windows/Fonts/arialbd.ttf",
            "C:/Windows/Fonts/calibrib.ttf",
        ]
        _RESOLVED_FONT_PATH = next((p for p in font_paths if os.path.exists(p)), None)
        _RESOLVED_FONT_BOLD_PATH = next(
            (p for p in font_bold_paths if os.path.exists(p)), _RESOLVED_FONT_PATH
        )
        _FONTS_RESOLVED = True

    target = _RESOLVED_FONT_BOLD_PATH if bold else _RESOLVED_FONT_PATH
    font = None
    if target:
        try:
            from PIL import ImageFont

            font = ImageFont.truetype(target, size)
        except Exception:
            font = None

    if font is None:
        from PIL import ImageFont

        font = ImageFont.load_default()

    _FONT_CACHE[cache_key] = font
    return font


# ---------------------------------------------------------------------------
# Acoustic Signal Processing & VAD Envelope Segmenter (16kHz PCM Schmitt Trigger)
# ---------------------------------------------------------------------------
def segment_acoustic_vad_16k(
    pcm_int16: np.ndarray,
    sample_rate: int = 16000,
    frame_ms: int = 10,
    window_ms: int = 20,
    threshold_voiced: float = 350.0,
    threshold_pause: float = 150.0,
    min_burst_ms: int = 100,
    min_pause_ms: int = 200,
) -> Tuple[List[Tuple[int, int]], List[Tuple[int, int]]]:
    """
    Dual-threshold Schmitt-trigger VAD segmenter on 16kHz mono PCM.
    Returns:
        (voiced_blocks, pause_blocks) where each block is (start_ms, end_ms).
    """
    if len(pcm_int16) == 0:
        return [], []

    hop_len = int(sample_rate * frame_ms / 1000)
    win_len = int(sample_rate * window_ms / 1000)
    total_duration_ms = int(len(pcm_int16) * 1000 / sample_rate)

    if len(pcm_int16) < win_len:
        rms_val = float(np.sqrt(np.mean(pcm_int16.astype(np.float32) ** 2)))
        if rms_val > threshold_voiced:
            return [(0, total_duration_ms)], []
        return [], [(0, total_duration_ms)]

    n_frames = max(1, (len(pcm_int16) - win_len) // hop_len + 1)

    # Compute RMS per frame
    rms_arr = np.zeros(n_frames, dtype=np.float32)
    for i in range(n_frames):
        chunk = pcm_int16[i * hop_len : i * hop_len + win_len].astype(np.float32)
        rms_arr[i] = float(np.sqrt(np.mean(chunk**2)))

    # Schmitt-trigger state machine
    is_voiced = np.zeros(n_frames, dtype=bool)
    state = False
    for i, r in enumerate(rms_arr):
        if not state and r > threshold_voiced:
            state = True
        elif state and r <= threshold_pause:
            state = False
        is_voiced[i] = state

    # Extract raw continuous voiced blocks
    diff = np.diff(is_voiced.astype(np.int32))
    starts = list(np.where(diff == 1)[0] + 1)
    ends = list(np.where(diff == -1)[0] + 1)
    if is_voiced[0]:
        starts.insert(0, 0)
    if is_voiced[-1]:
        ends.append(n_frames)

    raw_bursts = [
        (s * frame_ms, total_duration_ms if e == n_frames else min(total_duration_ms, e * frame_ms))
        for s, e in zip(starts, ends)
        if (e - s) * frame_ms >= min_burst_ms or (e == n_frames and (total_duration_ms - s * frame_ms) >= min_burst_ms)
    ]

    if not raw_bursts:
        return [], [(0, total_duration_ms)]

    # Bridge short silence gaps (< min_pause_ms)
    merged_voiced: List[Tuple[int, int]] = [raw_bursts[0]]
    for cur_s, cur_e in raw_bursts[1:]:
        prev_s, prev_e = merged_voiced[-1]
        gap = cur_s - prev_e
        win_smear_ms = max(0, window_ms - frame_ms)
        if gap < max(frame_ms, min_pause_ms - win_smear_ms):
            merged_voiced[-1] = (prev_s, cur_e)
        else:
            merged_voiced.append((cur_s, cur_e))

    # Derive pause intervals
    pauses: List[Tuple[int, int]] = []

    # Lead-in silence
    if merged_voiced[0][0] > 0:
        pauses.append((0, merged_voiced[0][0]))

    # Inter-burst pauses
    for i in range(len(merged_voiced) - 1):
        p_start = merged_voiced[i][1]
        p_end = merged_voiced[i + 1][0]
        if p_end > p_start:
            pauses.append((p_start, p_end))

    # Lead-out silence
    if merged_voiced[-1][1] < total_duration_ms:
        pauses.append((merged_voiced[-1][1], total_duration_ms))

    return merged_voiced, pauses


# ---------------------------------------------------------------------------
# Phonetic Syllable Duration Weighting & Word-Level Timing Alignment
# ---------------------------------------------------------------------------
RU_VOWELS = set("аеёиоуыэюяАЕЁИОУЫЭЮЯ")
EN_VOWELS = set("aeiouyAEIOUY")


def count_syllables(text: str) -> int:
    """Count phonetic syllables based on vowel nuclei."""
    clean = re.sub(r"[^а-яёА-ЯЁa-zA-Z]", "", text)
    if not clean:
        return 1
    vowel_count = sum(1 for ch in clean if ch in RU_VOWELS or ch in EN_VOWELS)
    return max(1, vowel_count)


def get_phonetic_expansion(
    visual_token: str,
    phonetic_catalog: Optional[List[Tuple[str, str]]] = None,
) -> str:
    """Map a visual token to its spoken phonetic phrase."""
    clean = re.sub(r"^[^\w$|]+|[^\w$|]+$", "", visual_token)
    catalog = phonetic_catalog
    if catalog is None:
        try:
            from src.dsp_defense_cycles import DSP_PHONETIC_MAP

            catalog = DSP_PHONETIC_MAP
        except Exception:
            catalog = []

    for pat, spoken in catalog:
        if clean == pat or clean.lower() == pat.lower():
            return spoken

    num_map = {
        "40": "сорок",
        "48": "сорок восемь",
        "16": "шестнадцать",
        "12": "двенадцать",
        "10": "десять",
        "32": "тридцать два",
        "64": "шестьдесят четыре",
        "3.3": "три и три",
        "5": "пять",
    }
    if clean in num_map:
        return num_map[clean]
    return visual_token


def compute_word_phonetic_weight(
    visual_token: str,
    phonetic_catalog: Optional[List[Tuple[str, str]]] = None,
) -> Tuple[float, float, str]:
    """
    Returns:
        (phonetic_weight, pause_weight, spoken_phrase)
    """
    spoken = get_phonetic_expansion(visual_token, phonetic_catalog)
    spoken_words = spoken.split()

    total_w = 0.0
    has_english_suffix = False
    clean_vis = re.sub(r"[^a-zA-Z]", "", visual_token.lower())
    for sw in spoken_words:
        syl = count_syllables(sw)
        has_stress = 1 if "+" in sw else 0
        consonants = len(re.sub(r"[^а-яёА-ЯЁa-zA-Z]", "", sw)) - syl
        sw_w = syl + 0.35 * has_stress + 0.08 * max(0, consonants)
        clean_sw = re.sub(r"[^a-zA-Z]", "", sw.lower())
        if any(
            (len(clean_sw) > len(sfx) and clean_sw.endswith(sfx))
            or (len(clean_vis) > len(sfx) and clean_vis.endswith(sfx))
            for sfx in ("able", "ible", "tion", "sion", "phy", "ment", "ness", "ed", "ing")
        ):
            sw_w *= 0.55
            has_english_suffix = True
        total_w += sw_w

    pause_w = 0.0
    if visual_token.endswith((",", ";")):
        pause_w = 1.3
    elif visual_token.endswith((".", "!", "?")):
        pause_w = 2.2
    elif "—" in visual_token or ":" in visual_token:
        pause_w = 2.0

    min_w = 0.5 if has_english_suffix else 1.0
    return max(min_w, total_w), pause_w, spoken


def compute_scene_word_timings(
    scene_id: str,
    visual_text: str,
    duration_ms: int,
    font_caption: Any = None,
    phonetic_catalog: Optional[List[Tuple[str, str]]] = None,
    audio_path: Optional[Path] = None,
    ffmpeg_exe: Optional[str] = None,
    max_line_width: int = 1152,
    voiced_blocks: Optional[List[Tuple[int, int]]] = None,
) -> SceneCaptions:
    """
    Compute exact word-level millisecond start and end timestamps and subtitle page layout
    by integrating acoustic VAD envelope detection with phonetic syllable duration weighting.
    """
    if font_caption is None:
        font_caption = get_cached_font(21, bold=True)

    clean_text = strip_accent_markers(visual_text)
    visual_words = clean_text.split()
    if not visual_words:
        return SceneCaptions(scene_id=scene_id, duration_ms=duration_ms, pages=[], all_words=[])

    # 1. Acoustic VAD Extraction if audio is available
    if voiced_blocks is None and audio_path and Path(audio_path).is_file():
        pcm_bytes = b""
        try:
            with wave.open(str(audio_path), "rb") as wf:
                if wf.getnchannels() == 1 and wf.getframerate() == 16000 and wf.getsampwidth() == 2:
                    pcm_bytes = wf.readframes(wf.getnframes())
        except Exception:
            pcm_bytes = b""

        if not pcm_bytes and ffmpeg_exe:
            try:
                cmd = [
                    ffmpeg_exe,
                    "-y",
                    "-i",
                    str(audio_path),
                    "-vn",
                    "-f",
                    "s16le",
                    "-ac",
                    "1",
                    "-ar",
                    "16000",
                    "-",
                ]
                proc = subprocess.run(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=True
                )
                pcm_bytes = proc.stdout
            except Exception:
                pcm_bytes = b""

        if pcm_bytes:
            pcm_int16 = np.frombuffer(pcm_bytes, dtype=np.int16)
            v_blocks, _ = segment_acoustic_vad_16k(pcm_int16, sample_rate=16000)
            if v_blocks:
                voiced_blocks = v_blocks

    # 2. Timing envelope allocation
    t_lead = min(250, int(0.02 * duration_ms))
    t_trail = min(400, int(0.03 * duration_ms))
    if not voiced_blocks:
        voiced_blocks = [(t_lead, max(t_lead + 300, duration_ms - t_trail))]

    # 3. Compute phonetic weights per token
    token_weights: List[float] = []
    token_pauses: List[float] = []
    token_phrases: List[str] = []
    for w in visual_words:
        p_w, pause_w, spoken = compute_word_phonetic_weight(w, phonetic_catalog)
        token_weights.append(p_w)
        token_pauses.append(pause_w)
        token_phrases.append(spoken)

    total_weight = max(1.0, sum(token_weights) + sum(token_pauses))
    total_voiced_dur = sum(e - s for s, e in voiced_blocks)
    if total_voiced_dur <= 0:
        total_voiced_dur = max(500, duration_ms - t_lead - t_trail)
        voiced_blocks = [(t_lead, t_lead + total_voiced_dur)]

    # 4. Map words to physical milliseconds through voiced blocks
    def tau_to_ms(tau: float) -> int:
        running = 0.0
        for b_s, b_e in voiced_blocks:
            b_dur = b_e - b_s
            if running + b_dur >= tau or (b_s, b_e) == voiced_blocks[-1]:
                offset = tau - running
                return int(b_s + max(0.0, min(float(b_dur), offset)))
            running += b_dur
        return voiced_blocks[-1][1]

    accum_w = 0.0
    word_start_ends: List[Tuple[int, int]] = []
    for idx, w_weight in enumerate(token_weights):
        pause_w = token_pauses[idx]
        tau_start = (accum_w / total_weight) * total_voiced_dur
        tau_end = ((accum_w + w_weight) / total_weight) * total_voiced_dur
        accum_w += w_weight + pause_w
        s_ms = tau_to_ms(tau_start)
        e_ms = max(s_ms + 80, tau_to_ms(tau_end))
        word_start_ends.append((s_ms, e_ms))

    # 5. Layout text into lines (max_width = 1152 px)
    def _measure(tok: str) -> float:
        try:
            return font_caption.getlength(tok)
        except Exception:
            return len(tok) * 11.5

    lines: List[List[str]] = []
    current_line: List[str] = []
    current_line_w = 0.0

    for w in visual_words:
        tok_w = _measure(w + " ")
        if current_line and (current_line_w + tok_w > max_line_width):
            lines.append(current_line)
            current_line = [w]
            current_line_w = tok_w
        else:
            current_line.append(w)
            current_line_w += tok_w
    if current_line:
        lines.append(current_line)

    # 6. Group lines into 2-line pages
    page_line_groups = [lines[i : i + 2] for i in range(0, len(lines), 2)] or [[]]

    # 7. Build WordTiming and SubtitlePage records with pixel positions
    all_words: List[WordTiming] = []
    pages: List[SubtitlePage] = []
    word_cursor = 0
    sub_x0, sub_y0, sub_x1, sub_y1 = 24, 604, 1256, 702

    for p_idx, p_lines in enumerate(page_line_groups):
        page_words: List[WordTiming] = []
        is_single_line = len(p_lines) == 1

        for l_idx, l_words in enumerate(p_lines):
            line_total_w = sum(_measure(w + " ") for w in l_words)
            tx = sub_x0 + max(32, int((sub_x1 - sub_x0 - line_total_w) / 2))
            ty = sub_y0 + (34 if is_single_line else (17 + l_idx * 34))
            cur_x = tx

            for w in l_words:
                w_len = _measure(w + " ")
                s_ms, e_ms = word_start_ends[word_cursor]

                wt = WordTiming(
                    word_index=word_cursor,
                    word=w,
                    start_ms=s_ms,
                    end_ms=e_ms,
                    page_index=p_idx,
                    line_index=l_idx,
                    x=cur_x,
                    y=ty,
                    width=int(w_len),
                    spoken_phrase=token_phrases[word_cursor],
                )
                page_words.append(wt)
                all_words.append(wt)

                cur_x += int(w_len)
                word_cursor += 1

        p_start = 0 if p_idx == 0 else page_words[0].start_ms - 50
        p_end = (
            duration_ms
            if p_idx == len(page_line_groups) - 1
            else page_words[-1].end_ms + 100
        )

        formatted_lines = [" ".join(l) for l in p_lines]

        pages.append(
            SubtitlePage(
                page_index=p_idx,
                start_ms=p_start,
                end_ms=p_end,
                lines=formatted_lines,
                words=page_words,
            )
        )

    # Re-normalize page boundaries to be contiguous
    for p_i in range(len(pages) - 1):
        pages[p_i].end_ms = pages[p_i + 1].start_ms

    return SceneCaptions(
        scene_id=scene_id,
        duration_ms=duration_ms,
        pages=pages,
        all_words=all_words,
    )


def compute_word_level_timings(
    audio_path: Optional[Path],
    ffmpeg_exe: Optional[str],
    visual_text: str,
    fps: int,
    total_frames: int,
    f_caption: Any = None,
    max_line_width: int = 1152,
    scene_id: str = "",
    phonetic_catalog: Optional[List[Tuple[str, str]]] = None,
) -> SceneCaptions:
    """Alternative API for word-level timing alignment with frame counts."""
    duration_ms = int(total_frames * 1000 / max(1, fps))
    return compute_scene_word_timings(
        scene_id=scene_id,
        visual_text=visual_text,
        duration_ms=duration_ms,
        font_caption=f_caption,
        phonetic_catalog=phonetic_catalog,
        audio_path=audio_path,
        ffmpeg_exe=ffmpeg_exe,
        max_line_width=max_line_width,
    )


# ---------------------------------------------------------------------------
# Open-Source Git Video Generation Algorithms (Remotion, Manim, MoviePy, ShortGPT)
# ---------------------------------------------------------------------------


def ease_out_cubic(t: float) -> float:
    """Remotion / Manim cubic deceleration curve: f(t) = 1 - (1 - t)^3."""
    t_clamped = max(0.0, min(1.0, float(t)))
    return 1.0 - (1.0 - t_clamped) ** 3


def ease_in_out_quad(t: float) -> float:
    """Quadratic smooth acceleration and deceleration."""
    t_clamped = max(0.0, min(1.0, float(t)))
    if t_clamped < 0.5:
        return 2.0 * t_clamped * t_clamped
    return 1.0 - ((-2.0 * t_clamped + 2.0) ** 2) / 2.0


def smoothstep(edge0: float, edge1: float, x: float) -> float:
    """Hermite interpolation between edges (GLSL/shader standard)."""
    t = max(0.0, min(1.0, (x - edge0) / max(1e-6, edge1 - edge0)))
    return t * t * (3.0 - 2.0 * t)


def extract_audio_spectrum_features(
    ffmpeg_exe: str,
    audio_path: Path,
    fps: int,
    total_frames: int,
    num_bands: int = 18,
) -> List[Dict[str, Any]]:
    """
    Extract per-frame real-time acoustic features (RMS energy and log-spaced FFT vocal bands)
    by decoding into 16kHz mono PCM in memory via FFmpeg pipe (Remotion useAudioData pattern).
    """
    default_frame = {
        "rms": 0.0,
        "bands": [0.0] * num_bands,
        "peak": 0.0,
    }
    if not audio_path.is_file():
        return [default_frame] * total_frames

    try:
        cmd = [
            ffmpeg_exe,
            "-y",
            "-i",
            str(audio_path),
            "-vn",
            "-f",
            "s16le",
            "-ac",
            "1",
            "-ar",
            "16000",
            "-",
        ]
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=True,
        )
        pcm = np.frombuffer(proc.stdout, dtype=np.int16).astype(np.float32) / 32768.0
    except Exception:
        return [default_frame] * total_frames

    if len(pcm) == 0:
        return [default_frame] * total_frames

    sr = 16000
    window_size = 1024
    hanning = np.hanning(window_size)
    freqs = np.fft.rfftfreq(window_size, d=1.0 / sr)
    band_edges = np.geomspace(120, 4800, num_bands + 1)

    features: List[Dict[str, Any]] = []
    prev_bands = np.zeros(num_bands, dtype=np.float32)

    for f_idx in range(total_frames):
        center = int(f_idx / max(1, fps) * sr)
        start = max(0, center - window_size // 2)
        chunk = pcm[start : start + window_size]
        if len(chunk) < window_size:
            chunk = np.pad(chunk, (0, window_size - len(chunk)))

        rms = float(np.sqrt(np.mean(chunk**2)))
        fft_mag = np.abs(np.fft.rfft(chunk * hanning))

        current_bands = np.zeros(num_bands, dtype=np.float32)
        for b_i in range(num_bands):
            mask = (freqs >= band_edges[b_i]) & (freqs < band_edges[b_i + 1])
            val = float(np.mean(fft_mag[mask])) if np.any(mask) else 0.0
            norm_val = min(1.0, math.sqrt(val * 0.14))
            current_bands[b_i] = norm_val

        smoothed_bands = np.maximum(current_bands, prev_bands * 0.74)
        prev_bands = smoothed_bands

        features.append(
            {
                "rms": min(1.0, rms * 3.5),
                "bands": [float(b) for b in smoothed_bands],
                "peak": float(np.max(smoothed_bands)),
            }
        )

    return features


def render_scene_frame_pil(
    topic: str,
    scene: FlowScene,
    voice_label: str,
    total_scenes: int,
    frame_idx: int,
    total_frames: int,
    width: int = 1280,
    height: int = 720,
    audio_features: Optional[Dict[str, Any]] = None,
    fps: int = 15,
    captions: Optional[SceneCaptions] = None,
    show_bullet_cards: bool = False,
    show_reticles: bool = False,
    show_watermark: bool = False,
) -> bytes:
    """
    Render a clean 1280x720 HD frame with Git-inspired video engine enhancements:
    - Real-Time Studio Audio Spectrum Pill in Header (Remotion pattern)
    - Left column: cubic-eased sliding thesis cards with vocal pulse
    - Right viewport: aspect-accurate 300 DPI blueprint with HUD corner reticles and zero jitter
    - Bottom subtitle bar: kinetic typography with word-by-word active illumination (ShortGPT pattern)
    """
    from PIL import Image, ImageDraw, ImageFont

    img = Image.new("RGB", (width, height), (11, 15, 25))
    draw = ImageDraw.Draw(img)

    progress = min(0.999, max(0.0, frame_idx / max(1, total_frames - 1)))
    t_phase = frame_idx * 0.14

    f_badge = get_cached_font(16, bold=True)
    f_badge_mini = get_cached_font(11, bold=True)
    f_title = get_cached_font(24, bold=True)
    f_bullet = get_cached_font(18, bold=False)
    f_caption = get_cached_font(21, bold=True)
    get_font = get_cached_font

    def _measure_token_w(tok: str) -> float:
        try:
            return f_caption.getlength(tok)
        except Exception:
            return len(tok) * 11.5

    # 1. Compact Header (y = 0..60) with Real-Time Audio Spectrum Analyzer
    draw.rectangle([(0, 0), (width, 60)], fill=(15, 22, 38))
    draw.line([(0, 60), (width, 60)], fill=(56, 189, 248), width=2)

    draw.rounded_rectangle([(24, 12), (148, 48)], radius=8, fill=(14, 116, 144))
    draw.text(
        (36, 19),
        f"\u0421\u0426\u0415\u041d\u0410 {scene.scene_number}/{total_scenes}",
        fill=(240, 249, 255),
        font=f_badge,
    )

    # Audio Spectrum Analyzer Pill (x = 1024..1256, y = 14..46)
    spec_x0, spec_y0, spec_x1, spec_y1 = 1024, 14, 1256, 46
    draw.rounded_rectangle(
        [(spec_x0, spec_y0), (spec_x1, spec_y1)],
        radius=8,
        fill=(17, 24, 39),
        outline=(56, 189, 248),
        width=1,
    )
    draw.text((spec_x0 + 10, spec_y0 + 9), "\u0413\u041e\u041b\u041e\u0421", fill=(56, 189, 248), font=f_badge_mini)

    bands = (audio_features.get("bands") if audio_features else None) or [0.0] * 18
    num_bars = min(18, len(bands))
    for b_i in range(num_bars):
        bx = spec_x0 + 64 + b_i * 9
        v = bands[b_i]
        bh = max(2, int(v * 22))
        by0 = spec_y1 - 5 - bh
        by1 = spec_y1 - 5
        if b_i < 6:
            bar_col = (56, 189, 248)
        elif b_i < 12:
            bar_col = (168, 85, 247)
        else:
            bar_col = (52, 211, 153)
        draw.rounded_rectangle([(bx, by0), (bx + 5, by1)], radius=2, fill=bar_col)

    max_w = width - 430  # 850px
    header_title = str(scene.title or "").strip()
    chosen_font = None
    for sz in (24, 20, 16, 13, 11):
        f_cand = get_cached_font(sz, bold=True)
        try:
            cand_len = f_cand.getlength(header_title)
        except Exception:
            cand_len = float(len(header_title) * sz * 0.6)
        if cand_len <= max_w:
            chosen_font = f_cand
            break

    if chosen_font is not None:
        draw.text((164, 18), header_title, fill=(248, 250, 252), font=chosen_font)
    else:
        f_mini = get_cached_font(11, bold=True)
        wrapped = _wrap_text_pixels(header_title, f_mini, max_width=max_w)
        if wrapped:
            draw.text((164, 11), wrapped[0], fill=(248, 250, 252), font=f_mini)
            if len(wrapped) > 1:
                line2 = wrapped[1]
                if len(wrapped) > 2:
                    while len(line2) > 3:
                        try:
                            l2_len = f_mini.getlength(line2 + "…")
                        except Exception:
                            l2_len = len(line2 + "…") * 7.0
                        if l2_len <= max_w:
                            break
                        line2 = line2.rsplit(" ", 1)[0]
                    line2 = line2 + "…"
                draw.text((164, 32), line2, fill=(248, 250, 252), font=f_mini)

    # 2. Split-Screen Live Sync Layout: Left Coursework Inspector + Right Multi-Concept Visualizer
    audio_rms = audio_features.get("rms", 0.0) if audio_features else 0.0
    t_sec = progress * float(getattr(scene, "duration_sec", 36.0) or 36.0)

    # 2.1 Resolve Active Page (pz_page 1..43) and Staged Assets
    pz_page = getattr(scene, "pz_page", None)
    if pz_page is None:
        try:
            from src.dsp_defense_cycles import get_scene_pz_page
            pz_page = get_scene_pz_page(scene.scene_id)
        except Exception:
            pz_page = max(1, min(43, int(getattr(scene, "scene_number", 1) or 1)))

    asset_path = getattr(scene, "asset_path", None)
    resolved_page_path: Optional[Path] = None
    if asset_path and os.path.isfile(str(asset_path)):
        resolved_page_path = Path(str(asset_path))
    else:
        assets_dir = OUTPUT_DIR / "dsp_assets"
        if pz_page == 42:
            for cand in (assets_dir / "drawing_e2.png", assets_dir / "pz_page_42.png"):
                if cand.is_file():
                    resolved_page_path = cand
                    break
        elif pz_page == 43:
            for cand in (assets_dir / "drawing_pe2.png", assets_dir / "pz_page_43.png"):
                if cand.is_file():
                    resolved_page_path = cand
                    break
        else:
            cand = assets_dir / f"pz_page_{int(pz_page):02d}.png"
            if cand.is_file():
                resolved_page_path = cand

    raw_page_img: Optional[Image.Image] = None
    if resolved_page_path and resolved_page_path.is_file():
        cache_key = str(resolved_page_path)
        if cache_key not in _PAGE_IMAGE_CACHE:
            if len(_PAGE_IMAGE_CACHE) >= 8:
                oldest_k = next(iter(_PAGE_IMAGE_CACHE))
                _PAGE_IMAGE_CACHE.pop(oldest_k, None)
            _PAGE_IMAGE_CACHE[cache_key] = Image.open(str(resolved_page_path)).convert("RGB")
        raw_page_img = _PAGE_IMAGE_CACHE[cache_key]
    else:
        cache_key = f"procedural_pz_{pz_page}"
        if cache_key not in _PAGE_IMAGE_CACHE:
            pw, ph = 2481, 3508
            im = Image.new("RGB", (pw, ph), (15, 23, 42))
            d = ImageDraw.Draw(im)
            d.rectangle([(40, 40), (pw - 40, ph - 40)], outline=(56, 189, 248), width=6)
            for gy in range(200, ph - 200, 300):
                d.line([(80, gy), (pw - 80, gy)], fill=(30, 41, 59), width=2)
            d.text((120, 160), f"Coursework PZ Page {pz_page:02d}", fill=(240, 249, 255), font=f_title)
            _PAGE_IMAGE_CACHE[cache_key] = im
        raw_page_img = _PAGE_IMAGE_CACHE[cache_key]

    # 2.2 Resolve Active Concept Cue (3..5 cues per scene)
    cues = getattr(scene, "concept_cues", None)
    if not cues:
        try:
            from src.dsp_defense_cycles import get_scene_concept_cues
            cues = get_scene_concept_cues(scene.scene_id)
        except Exception:
            cues = []
    if not cues:
        cues = [
            {
                "start_ratio": 0.0,
                "end_ratio": 0.33,
                "focus_bbox": [0.08, 0.10, 0.92, 0.38],
                "concept_type": "hardware_ic",
                "concept_target": "DSP56824",
                "target_title_ru": "\u0413\u0430\u0440\u0432\u0430\u0440\u0434\u0441\u043a\u043e\u0435 \u044f\u0434\u0440\u043e DSP56824",
                "formula_or_label": "DA1 DSP56824 \u2022 40 \u041c\u0413\u0446 \u2022 6 \u0448\u0438\u043d",
                "animation_mode": "bus_transfer",
            },
            {
                "start_ratio": 0.33,
                "end_ratio": 0.67,
                "focus_bbox": [0.08, 0.39, 0.92, 0.68],
                "concept_type": "math_formula",
                "concept_target": "Direct Form II",
                "target_title_ru": "\u041a\u0430\u0441\u043a\u0430\u0434 \u0431\u0438\u043a\u0432\u0430\u0434\u0440\u0430\u0442\u043d\u044b\u0445 \u0437\u0432\u0435\u043d\u044c\u0435\u0432",
                "formula_or_label": "\u041f\u0440\u044f\u043c\u0430\u044f \u0444\u043e\u0440\u043c\u0430 II \u2022 6 \u0441\u0435\u043a\u0446\u0438\u0439 Q15",
                "animation_mode": "waveform_sweep",
            },
            {
                "start_ratio": 0.67,
                "end_ratio": 1.0,
                "focus_bbox": [0.08, 0.69, 0.92, 0.94],
                "concept_type": "firmware_asm",
                "concept_target": "DO #6 Loop",
                "target_title_ru": "\u041e\u0431\u0440\u0430\u0431\u043e\u0442\u0447\u0438\u043a SSI_Rx_ISR",
                "formula_or_label": "\u0410\u043f\u043f\u0430\u0440\u0430\u0442\u043d\u044b\u0439 \u0446\u0438\u043a\u043b DO #6 @ P:$001E",
                "animation_mode": "register_update",
            },
        ]

    # Resolve optional <bookmark mark="..."/> bindings on concept_cues
    raw_narration_for_bm = str(getattr(scene, "narration_text", "") or "")
    if "<bookmark" in raw_narration_for_bm.lower():
        _, parsed_bms = parse_voiceover_bookmarks(raw_narration_for_bm)
        bm_ratio_map = {b.mark: b.word_ratio for b in parsed_bms}
        if bm_ratio_map:
            resolved_cues = []
            for idx_c, c_orig in enumerate(cues):
                c_copy = dict(c_orig)
                bm_key = c_copy.get("bookmark") or c_copy.get("start_bookmark")
                end_bm_key = c_copy.get("end_bookmark")
                if bm_key and bm_key in bm_ratio_map:
                    c_copy["start_ratio"] = bm_ratio_map[bm_key]
                if end_bm_key and end_bm_key in bm_ratio_map:
                    c_copy["end_ratio"] = bm_ratio_map[end_bm_key]
                elif bm_key and bm_key in bm_ratio_map and idx_c + 1 < len(cues):
                    next_bm = cues[idx_c + 1].get("bookmark") or cues[idx_c + 1].get("start_bookmark")
                    if next_bm and next_bm in bm_ratio_map:
                        c_copy["end_ratio"] = max(float(c_copy.get("start_ratio", 0.0)) + 0.05, bm_ratio_map[next_bm])
                resolved_cues.append(c_copy)
            cues = resolved_cues

    active_cue = cues[-1]
    for c in cues:
        if float(c.get("start_ratio", 0.0)) <= progress < float(c.get("end_ratio", 1.0)):
            active_cue = c
            break

    c_start = float(active_cue.get("start_ratio", 0.0))
    c_end = float(active_cue.get("end_ratio", 1.0))
    cue_t = min(1.0, max(0.0, (progress - c_start) / max(1e-4, c_end - c_start)))

    # 2.3 Spring + Cubic-Bezier Auto-Zoom Camera & Paper2Video Cursor Grounding
    from src.flow_prompt_library import closed_form_spring

    focus_bbox = active_cue.get("focus_bbox", [0.08, 0.10, 0.92, 0.90])
    rx0, ry0, rx1, ry1 = float(focus_bbox[0]), float(focus_bbox[1]), float(focus_bbox[2]), float(focus_bbox[3])
    target_cx = (rx0 + rx1) / 2.0
    target_cy = (ry0 + ry1) / 2.0
    bw = max(0.08, rx1 - rx0)
    bh = max(0.08, ry1 - ry0)
    target_zoom = min(1.85, max(1.40, 0.78 / max(bw, bh)))

    spring_s = float(closed_form_spring(cue_t, zeta=1.0, omega0=5.0, x0=0.0, x1=1.0))
    spring_s = min(1.0, max(0.0, spring_s))
    bezier_s = cubic_bezier_ease(min(1.0, cue_t * 1.4), 0.25, 0.10, 0.25, 1.0)
    blend_s = 0.55 * spring_s + 0.45 * bezier_s
    cur_zoom = 1.0 + (target_zoom - 1.0) * blend_s + 0.03 * math.sin(cue_t * math.pi)
    cur_cx = 0.5 + (target_cx - 0.5) * blend_s + 0.04 * bw * math.sin(cue_t * math.pi * 2.0)
    cur_cy = 0.5 + (target_cy - 0.5) * blend_s

    # 2.4 Left Panel: Coursework & Blueprint Inspector (x = 24..584, y = 66..594, width 560, height 528)
    lp_x0, lp_y0, lp_x1, lp_y1 = 24, 66, 584, 594
    draw.rounded_rectangle([(lp_x0, lp_y0), (lp_x1, lp_y1)], radius=12, fill=(15, 20, 35), outline=(56, 189, 248), width=2)

    pad = 4
    vw = (lp_x1 - lp_x0) - 2 * pad  # 552
    vh = (lp_y1 - lp_y0) - 2 * pad  # 520
    vx0 = lp_x0 + pad  # 28
    vy0 = lp_y0 + pad  # 70

    pw, ph = raw_page_img.width, raw_page_img.height
    cg_engine = CursorGroundingEngine(source_width=pw, source_height=ph, min_zoom=1.0, max_zoom=1.85)
    cg_state = cg_engine.compute_frame_state(
        frame_idx=frame_idx,
        total_frames=total_frames,
        cues=cues,
        pz_bbox=focus_bbox,
        callout_label=str(active_cue.get("formula_or_label") or active_cue.get("target_title_ru") or ""),
    )

    ar_vp = float(vw) / float(vh)
    ar_page = float(pw) / float(ph)
    if ar_page > ar_vp:
        fit_h = float(ph)
        fit_w = fit_h * ar_vp
    else:
        fit_w = float(pw)
        fit_h = fit_w / ar_vp

    win_w = fit_w / cur_zoom
    win_h = fit_h / cur_zoom
    center_px_x = cur_cx * pw
    center_px_y = cur_cy * ph

    crop_x0 = max(0.0, min(float(pw) - win_w, center_px_x - win_w / 2.0))
    crop_x1 = crop_x0 + win_w
    crop_y0 = max(0.0, min(float(ph) - win_h, center_px_y - win_h / 2.0))
    crop_y1 = crop_y0 + win_h

    crop_box = (
        max(0, int(round(crop_x0))),
        max(0, int(round(crop_y0))),
        min(pw, max(1, int(round(crop_x1)))),
        min(ph, max(1, int(round(crop_y1)))),
    )
    cropped_tile = raw_page_img.crop(crop_box).resize((vw, vh), Image.Resampling.LANCZOS)
    img.paste(cropped_tile, (vx0, vy0))

    # Glowing Cyan / Amber Focus Frame on Target Area
    fx0 = int(vx0 + (rx0 * pw - crop_x0) / max(1.0, crop_x1 - crop_x0) * vw)
    fy0 = int(vy0 + (ry0 * ph - crop_y0) / max(1.0, crop_y1 - crop_y0) * vh)
    fx1 = int(vx0 + (rx1 * pw - crop_x0) / max(1.0, crop_x1 - crop_x0) * vw)
    fy1 = int(vy0 + (ry1 * ph - crop_y0) / max(1.0, crop_y1 - crop_y0) * vh)

    fx0 = max(vx0 + 2, min(vx0 + vw - 10, fx0))
    fy0 = max(vy0 + 2, min(vy0 + vh - 10, fy0))
    fx1 = max(fx0 + 10, min(vx0 + vw - 2, fx1))
    fy1 = max(fy0 + 10, min(vy0 + vh - 2, fy1))

    pulse = 0.85 + 0.15 * math.sin(t_phase * 2.5) * (1.0 + audio_rms * 0.4)
    halo_cyan = (min(255, int(56 * pulse)), min(255, int(189 * pulse)), min(255, int(248 * pulse)))
    draw.rounded_rectangle([(fx0 - 2, fy0 - 2), (fx1 + 2, fy1 + 2)], radius=6, outline=halo_cyan, width=3)
    draw.rounded_rectangle([(fx0, fy0), (fx1, fy1)], radius=4, outline=(255, 193, 7), width=1)

    # Paper2Video Laser Pointer Dot & Comet Trail on Left PDF Panel
    lx_vp = int(vx0 + (cg_state.laser_x - crop_x0) / max(1.0, crop_x1 - crop_x0) * vw)
    ly_vp = int(vy0 + (cg_state.laser_y - crop_y0) / max(1.0, crop_y1 - crop_y0) * vh)
    lx_vp = max(vx0 + 8, min(vx0 + vw - 8, lx_vp))
    ly_vp = max(vy0 + 38, min(vy0 + vh - 38, ly_vp))
    prev_pt = (lx_vp, ly_vp)
    for t_idx, (tx_src, ty_src) in enumerate(cg_state.trail):
        tx_vp = int(vx0 + (tx_src - crop_x0) / max(1.0, crop_x1 - crop_x0) * vw)
        ty_vp = int(vy0 + (ty_src - crop_y0) / max(1.0, crop_y1 - crop_y0) * vh)
        tx_vp = max(vx0 + 8, min(vx0 + vw - 8, tx_vp))
        ty_vp = max(vy0 + 38, min(vy0 + vh - 38, ty_vp))
        draw.line([prev_pt, (tx_vp, ty_vp)], fill=(239, 68, 68), width=max(1, 3 - t_idx // 2))
        prev_pt = (tx_vp, ty_vp)
    draw.ellipse([(lx_vp - 7, ly_vp - 7), (lx_vp + 7, ly_vp + 7)], outline=(251, 191, 36), width=2)
    draw.ellipse([(lx_vp - 4, ly_vp - 4), (lx_vp + 4, ly_vp + 4)], fill=(239, 68, 68), outline=(255, 255, 255))

    # Concise Russian Badges on Left Panel (zero raw snake_case)
    target_node = str(active_cue.get("concept_target", ""))
    cue_label = str(active_cue.get("formula_or_label", "") or active_cue.get("target_title_ru", "") or "\u0423\u0437\u0435\u043b \u0440\u0430\u0441\u0447\u0451\u0442\u0430 \u041f\u0417")
    if "_" in cue_label and not re.search("[\u0400-\u04ff]", cue_label):
        cue_label = "\u0423\u0437\u0435\u043b \u0440\u0430\u0441\u0447\u0451\u0442\u0430 \u041f\u0417"

    target_ru = str(active_cue.get("target_title_ru") or active_cue.get("formula_or_label") or "")
    if not target_ru or ("_" in target_ru and not re.search("[\u0400-\u04ff]", target_ru)):
        target_ru = "\u0420\u0430\u0437\u0434\u0435\u043b \u041f\u0417"

    page_badge = f"\u0421\u0442\u0440. {pz_page}/43 \u2022 {target_ru[:32]}"
    badge_w = min(vw - 20, int(f_badge_mini.getlength(page_badge)) + 20)
    draw.rounded_rectangle([(vx0 + 10, vy0 + 10), (vx0 + 10 + badge_w, vy0 + 34)], radius=6, fill=(15, 23, 42), outline=(56, 189, 248), width=1)
    draw.text((vx0 + 20, vy0 + 14), page_badge, fill=(240, 249, 255), font=f_badge_mini)

    # pdf2video Typing-Effect Callout Bar at Bottom of Left Sheet Panel
    typed_len = max(6, int(math.ceil(len(cue_label[:42]) * min(1.0, cue_t * 1.35))))
    focus_badge = f"\u0424\u043e\u043a\u0443\u0441: {cue_label[:typed_len]}"
    lbl_w = min(vw - 20, int(f_badge_mini.getlength(focus_badge)) + 20)
    draw.rounded_rectangle([(vx0 + 10, vy0 + vh - 32), (vx0 + 10 + lbl_w, vy0 + vh - 10)], radius=4, fill=(15, 23, 42), outline=(245, 158, 11), width=1)
    draw.text((vx0 + 19, vy0 + vh - 28), focus_badge, fill=(255, 193, 7), font=f_badge_mini)

    # 3. Right Viewport: Dual-Deck Concept Synchronizer (x = 596..1256, y = 66..594, width 660, height 528)
    rp_x0, rp_y0, rp_x1, rp_y1 = 596, 66, 1256, 594
    draw.rounded_rectangle([(rp_x0, rp_y0), (rp_x1, rp_y1)], radius=12, fill=(15, 20, 35), outline=(56, 189, 248), width=2)

    # 3.1 Header of Right Viewport (y = 74..98)
    cue_idx = cues.index(active_cue) if active_cue in cues else 0
    c_type = str(active_cue.get("concept_type", "")).lower()
    a_mode = str(active_cue.get("animation_mode", "")).lower()
    _ru_type_map = {
        "hardware_ic": "\u0410\u041f\u041f\u0410\u0420\u0410\u0422\u041d\u042b\u0419 \u0423\u0417\u0415\u041b",
        "schematic": "\u0421\u0425\u0415\u041c\u041e\u0422\u0415\u0425\u041d\u0418\u041a\u0410 \u0415\u0421\u041a\u0414",
        "math_formula": "\u041c\u0410\u0422\u0415\u041c\u0410\u0422\u0418\u0427\u0415\u0421\u041a\u0410\u042f \u041c\u041e\u0414\u0415\u041b\u042c",
        "table": "\u041f\u0410\u0420\u0410\u041c\u0415\u0422\u0420\u042b \u0418 \u0422\u0410\u0411\u041b\u0418\u0426\u042b",
        "plot": "\u0425\u0410\u0420\u0410\u041a\u0422\u0415\u0420\u0418\u0421\u0422\u0418\u041a\u0418 \u0424\u0418\u041b\u042c\u0422\u0420\u0410",
        "firmware_asm": "\u0410\u0421\u0421\u0415\u041c\u0411\u041b\u0415\u0420 DSP56800",
    }
    ru_type_tag = _ru_type_map.get(c_type, "\u0418\u041d\u0416\u0415\u041d\u0415\u0420\u041d\u042b\u0419 \u0423\u0417\u0415\u041b")
    hdr_cue_text = f"[{ru_type_tag}] {cue_label[:40]}"
    draw.rounded_rectangle([(rp_x0 + 12, rp_y0 + 8), (rp_x0 + 508, rp_y0 + 32)], radius=6, fill=(17, 24, 39), outline=(56, 189, 248), width=1)
    draw.text((rp_x0 + 20, rp_y0 + 12), hdr_cue_text, fill=(224, 242, 254), font=f_badge_mini)

    # Cue step indicators
    for s_i in range(min(5, len(cues))):
        col_s = (56, 189, 248) if s_i == cue_idx else (71, 85, 105)
        draw.ellipse([(rp_x0 + 520 + s_i * 20, rp_y0 + 14), (rp_x0 + 530 + s_i * 20, rp_y0 + 24)], fill=col_s)

    # 3.2 Top Deck of Right Viewport (x = 606..1246, y = 104..316, width 640, height 212)
    # High-DPI Magnified Callout of Active Formula / Figure / Table / Schematic Node
    td_x0, td_y0, td_x1, td_y1 = 606, 104, 1246, 316
    draw.rounded_rectangle([(td_x0, td_y0), (td_x1, td_y1)], radius=8, fill=(13, 19, 33), outline=(56, 189, 248), width=1)

    callout_hdr = "\u041a\u0440\u0443\u043f\u043d\u044b\u0439 \u043f\u043b\u0430\u043d \u0443\u0437\u043b\u0430 / \u0444\u043e\u0440\u043c\u0443\u043b\u044b \u041f\u0417:"
    draw.text((614, 108), callout_hdr, fill=(148, 163, 184), font=f_badge_mini)
    hdr_offset_x = 614 + int(f_badge_mini.getlength(callout_hdr)) + 8
    draw.text((hdr_offset_x, 108), cue_label[:46], fill=(255, 193, 7), font=f_badge_mini)

    callout_src_img = raw_page_img
    src_w, src_h = callout_src_img.width, callout_src_img.height
    cx0 = max(0, min(src_w - 16, int(round(rx0 * src_w))))
    cy0 = max(0, min(src_h - 16, int(round(ry0 * src_h))))
    cx1 = max(cx0 + 16, min(src_w, int(round(rx1 * src_w))))
    cy1 = max(cy0 + 16, min(src_h, int(round(ry1 * src_h))))

    # If the focused block is much taller than the wide callout deck (ch > cw * 0.42),
    # pan a wide 1:1 aspect-ratio reading window vertically across [cy0..cy1] with cue_t
    raw_cw = max(16, cx1 - cx0)
    raw_ch = max(16, cy1 - cy0)
    target_band_h = int(round(raw_cw * 0.31))
    if raw_ch > int(round(raw_cw * 0.42)) and target_band_h < raw_ch:
        pan_y0 = cy0 + int(round((raw_ch - target_band_h) * min(1.0, max(0.0, cue_t))))
        pan_y1 = min(src_h, pan_y0 + target_band_h)
        callout_crop = callout_src_img.crop((cx0, pan_y0, cx1, pan_y1))
    else:
        callout_crop = callout_src_img.crop((cx0, cy0, cx1, cy1))

    ib_x0, ib_y0, ib_x1, ib_y1 = 614, 132, 1238, 308
    max_w = ib_x1 - ib_x0  # 624
    max_h = ib_y1 - ib_y0  # 176
    draw.rounded_rectangle([(ib_x0, ib_y0), (ib_x1, ib_y1)], radius=6, fill=(248, 250, 252), outline=(71, 85, 105), width=1)

    cw = max(1, callout_crop.width)
    ch = max(1, callout_crop.height)
    scale = min(float(max_w - 8) / float(cw), float(max_h - 8) / float(ch))
    new_w = max(1, int(round(cw * scale)))
    new_h = max(1, int(round(ch * scale)))
    paste_x = ib_x0 + (max_w - new_w) // 2
    paste_y = ib_y0 + (max_h - new_h) // 2

    resized_callout = callout_crop.resize((new_w, new_h), Image.Resampling.LANCZOS)
    img.paste(resized_callout, (paste_x, paste_y))
    draw.rectangle([(paste_x - 1, paste_y - 1), (paste_x + new_w, paste_y + new_h)], outline=(56, 189, 248), width=1)

    # Animated cyan-gold laser scanline across the magnified callout crop
    scan_x = paste_x + int(cue_t * max(1, new_w - 1))
    scan_y = paste_y + int((0.25 + 0.50 * (0.5 + 0.5 * math.sin(cue_t * math.pi * 2.0))) * max(1, new_h - 1))
    band_x0 = max(paste_x, scan_x - 8)
    band_x1 = min(paste_x + new_w, scan_x + 8)
    draw.rectangle([(band_x0, paste_y), (band_x1, paste_y + new_h)], outline=(56, 189, 248), width=1)
    draw.line([(scan_x, paste_y), (scan_x, paste_y + new_h)], fill=(56, 189, 248), width=2)
    draw.line([(max(paste_x, scan_x - 18), scan_y), (min(paste_x + new_w, scan_x + 18), scan_y)], fill=(255, 193, 7), width=2)
    draw.ellipse([(scan_x - 4, scan_y - 4), (scan_x + 4, scan_y + 4)], fill=(255, 193, 7), outline=(15, 23, 42))

    # 3.3 Bottom Deck of Right Viewport (x = 606..1246, y = 324..586, width 640, height 262)
    # Context-Matched Dynamic Process Animation
    rect_box = (606, 324, 1246, 586)
    t_lower = (
        target_node
        + " "
        + str(active_cue.get("formula_or_label", ""))
        + " "
        + str(active_cue.get("target_title_ru", ""))
    ).lower()

    scene_dom = getattr(scene, "visualizer_domain", None)
    spec_pages = (1, 2, 3, 4, 5, 6, 7, 11, 12, 20, 21, 34, 35, 36, 37, 43)

    is_explicit_asm = (
        c_type == "firmware_asm"
        or a_mode == "register_update"
        or any(
            k in t_lower
            for k in (
                "loop", "asm", "isr", "opcode", "vect", "do_6", "do #6",
                "p:$", "x:$", "r0", "r1", "agu", "mpy", "asl",
                "stack", "lifo", "114", "150", "86,3", "86.3",
                "4_1", "fig_4_1", "\u0430\u0441\u0441\u0435\u043c\u0431\u043b", "\u043f\u0440\u0435\u0440\u044b\u0432", "\u0440\u0435\u0433\u0438\u0441\u0442\u0440", "\u0430\u043a\u043a\u0443\u043c",
            )
        )
    )
    is_page42_hw = (
        pz_page == 42
        and (
            c_type in ("hardware_ic", "schematic")
            or a_mode in ("bus_transfer", "schematic_node_trace")
            or any(k in t_lower for k in ("drawing_e2", "da1", "da2", "da3", "da4", "da5", "da6", "dd1"))
        )
    )
    is_spec_cue = any(
        k in t_lower
        for k in (
            "2_1", "2.1", "6_1", "6.1", "pe2", "\u043f\u044d2", "eskd", "\u0435\u0441\u043a\u0434",
            "mtbf", "thermo", "thermal", "power_dissipation", "27.002", "\u043d\u0430\u0434\u0435\u0436\u043d", "\u0442\u0435\u043f\u043b",
            "kompas", "\u043a\u043e\u043c\u043f\u0430\u0441", "kicad", "2.104", "2.702", "7.32",
            "tms", "adsp", "concl", "\u0437\u0430\u043a\u043b\u044e\u0447", "\u0432\u044b\u0432\u043e\u0434", "\u0438\u0442\u043e\u0433",
            "pstu_itrs", "variant_5_spec", "task_signoff", "abstract_ru", "biblio",
        )
    )

    if scene_dom and not getattr(scene, "concept_cues", None) and not str(getattr(scene, "scene_id", "")).startswith("cycle"):
        active_dom = scene_dom
    elif (scene_dom == "spec_compliance" or pz_page in spec_pages) and not is_explicit_asm and not is_page42_hw:
        active_dom = "spec_compliance"
    elif is_spec_cue and not is_page42_hw:
        active_dom = "spec_compliance"
    elif c_type == "table" or a_mode == "table_row_highlight":
        if pz_page in (27, 28) or any(k in t_lower for k in ("5_1", "5.1", "biquad", "l_inf", "g_out")):
            active_dom = scene_dom if scene_dom in ("zplane", "waveform") else "zplane"
        elif is_explicit_asm or scene_dom == "assembly_trace":
            active_dom = "assembly_trace"
        else:
            active_dom = "spec_compliance"
    elif any(k in t_lower for k in ("fig_5_1", "direct_form_2", "df2_", "direct form ii")):
        active_dom = "waveform"
    elif is_explicit_asm:
        active_dom = "assembly_trace"
    elif (
        a_mode == "zplane_highlight"
        or any(
            k in t_lower
            for k in (
                "zplane", "z-plane", "pole", "zero", "5_2", "fig_5_2",
                "stab", "bibo", "0,9878", "0.9878", "ellip", "cauer",
                "butter", "cheb", "bessel", "bilin", "prewarp", "order",
                "\u043f\u043e\u043b\u044e\u0441", "\u043d\u0443\u043b", "\u0443\u0441\u0442\u043e\u0439\u0447", "\u0430\u043f\u043f\u0440\u043e\u043a\u0441", "\u043a\u0430\u0443\u044d\u0440", "\u044d\u043b\u043b\u0438\u043f\u0442", "\u0431\u0438\u043b\u0438\u043d\u0435\u0439",
            )
        )
    ):
        active_dom = "zplane"
    elif (
        c_type in ("hardware_ic", "schematic")
        or a_mode in ("bus_transfer", "schematic_node_trace")
        or any(
            k in t_lower
            for k in (
                "dsp56824", "ad73322", "is61lv6416", "max706", "ad8606",
                "mc68hc908", "harv", "sram", "bus", "ssi", "sallen",
                "agnd", "dgnd", "w1", "lm317", "ld1117", "zq1", "zq2",
                "bcr", "wait", "drawing_e2", "3_1", "fig_3_1",
                "da1", "da2", "da3", "da4", "da5", "da6", "dd1",
                "\u0448\u0438\u043d", "\u043e\u0437\u0443", "\u043a\u043e\u0434\u0435\u043a", "\u0441\u0445\u0435\u043c", "\u043f\u0438\u0442\u0430\u043d", "\u0437\u0435\u043c\u043b", "\u043a\u0432\u0430\u0440\u0446", "\u0441\u0431\u0440\u043e\u0441",
            )
        )
    ):
        active_dom = "hardware_bus"
    elif scene_dom in ("assembly_trace", "zplane", "hardware_bus", "waveform", "spec_compliance"):
        active_dom = scene_dom
    elif c_type in ("math_formula", "plot") or a_mode in ("waveform_sweep", "formula_derivation"):
        if any(k in t_lower for k in ("1.1", "1_1", "1.2", "1_2", "3.1", "3_1", "harv", "arch", "ti", "analog")):
            active_dom = "hardware_bus"
        else:
            active_dom = "waveform"
    else:
        active_dom = ("hardware_bus", "waveform", "zplane", "assembly_trace")[cue_idx % 4]

    from src.flow_dsp_visualizers import (
        AssemblyTraceVisualizer,
        HardwareBusVisualizer,
        SpecComplianceVisualizer,
        WaveformVisualizer,
        ZPlaneVisualizer,
    )

    if active_dom == "spec_compliance":
        SpecComplianceVisualizer().draw(
            draw,
            t=t_sec,
            rect=rect_box,
            active_target=target_node,
            pz_page=pz_page,
            cue_label=cue_label,
        )
    elif active_dom == "hardware_bus":
        HardwareBusVisualizer().draw(draw, t=t_sec, rect=rect_box, active_target=target_node)
    elif active_dom == "zplane":
        ZPlaneVisualizer().draw(draw, omega=(0.12 + 0.78 * cue_t) * math.pi, rect=rect_box)
    elif active_dom == "assembly_trace":
        AssemblyTraceVisualizer().draw_hud(draw, t=t_sec, rect=rect_box)
    else:
        WaveformVisualizer().draw(draw, t=t_sec, rect=rect_box)

    # Technical HUD Corner Reticles
    if show_reticles:
        reticle_len = 12
        for (vx0_r, vy0_r, vx1_r, vy1_r) in [(lp_x0, lp_y0, lp_x1, lp_y1), (rp_x0, rp_y0, rp_x1, rp_y1)]:
            draw.line([(vx0_r - 2, vy0_r - 2), (vx0_r - 2 + reticle_len, vy0_r - 2)], fill=(56, 189, 248), width=2)
            draw.line([(vx0_r - 2, vy0_r - 2), (vx0_r - 2, vy0_r - 2 + reticle_len)], fill=(56, 189, 248), width=2)
            draw.line([(vx1_r + 2, vy0_r - 2), (vx1_r + 2 - reticle_len, vy0_r - 2)], fill=(56, 189, 248), width=2)
            draw.line([(vx1_r + 2, vy0_r - 2), (vx1_r + 2, vy0_r - 2 + reticle_len)], fill=(56, 189, 248), width=2)
            draw.line([(vx0_r - 2, vy1_r + 2), (vx0_r - 2 + reticle_len, vy1_r + 2)], fill=(56, 189, 248), width=2)
            draw.line([(vx0_r - 2, vy1_r + 2), (vx0_r - 2, vy1_r + 2 - reticle_len)], fill=(56, 189, 248), width=2)
            draw.line([(vx1_r + 2, vy1_r + 2), (vx1_r + 2 - reticle_len, vy1_r + 2)], fill=(56, 189, 248), width=2)
            draw.line([(vx1_r + 2, vy1_r + 2), (vx1_r + 2, vy1_r + 2 - reticle_len)], fill=(56, 189, 248), width=2)

    # Viewport Technical Watermark Badge
    if show_watermark:
        draw.rounded_rectangle(
            [(rp_x1 - 180, rp_y0 + 8), (rp_x1 - 10, rp_y0 + 32)],
            radius=6,
            fill=(15, 23, 42),
            outline=(56, 189, 248),
            width=1,
        )
        draw.text((rp_x1 - 170, rp_y0 + 13), "\u0413\u041e\u0421\u0422 2.304 \u2022 300 DPI", fill=(224, 242, 254), font=f_badge_mini)

    # 4. Time-Synchronized Kinetic Typography Subtitle Bar (x = 24..1256, y = 604..702)
    sub_x0, sub_y0, sub_x1, sub_y1 = 24, 604, 1256, 702
    draw.rounded_rectangle(
        [(sub_x0, sub_y0), (sub_x1, sub_y1)],
        radius=12,
        fill=(9, 13, 22),
        outline=(56, 189, 248),
        width=2,
    )

    t_ms = int(frame_idx * 1000.0 / max(1, fps))

    # Resolve captions from parameter or scene
    active_captions = captions or getattr(scene, "captions", None)
    if active_captions is None and getattr(scene, "narration_text", None):
        # Precompute and cache on scene to avoid recomputing every frame
        if not hasattr(scene, "_runtime_captions") or getattr(scene, "_runtime_captions", None) is None:
            scene_dur_ms = int(total_frames * 1000 / max(1, fps))
            setattr(
                scene,
                "_runtime_captions",
                compute_scene_word_timings(
                    scene_id=scene.scene_id,
                    visual_text=scene.narration_text,
                    duration_ms=scene_dur_ms,
                    font_caption=f_caption,
                ),
            )
        active_captions = getattr(scene, "_runtime_captions", None)

    active_page = None
    if active_captions and active_captions.pages:
        active_page = active_captions.pages[-1]
        for p in active_captions.pages:
            if p.start_ms <= t_ms < p.end_ms:
                active_page = p
                break

    if active_page and active_page.words:
        for wt in active_page.words:
            tok = wt.word + " "
            if t_ms < wt.start_ms:
                # FUTURE: Dimmed slate grey
                draw.text((wt.x, wt.y), tok, fill=(100, 116, 139), font=f_caption)
            elif wt.start_ms <= t_ms <= wt.end_ms:
                # ACTIVE: Amber-Gold #FFC107 with (+1, +1) drop shadow and deep obsidian-amber stroke
                draw.text((wt.x + 1, wt.y + 1), tok, fill=(0, 0, 0), font=f_caption)
                try:
                    draw.text(
                        (wt.x, wt.y),
                        tok,
                        fill=(255, 193, 7),
                        font=f_caption,
                        stroke_width=2,
                        stroke_fill=(20, 14, 4),
                    )
                except Exception:
                    draw.text((wt.x, wt.y), tok, fill=(255, 193, 7), font=f_caption)
            else:
                # PAST: Clean crisp off-white
                draw.text((wt.x, wt.y), tok, fill=(241, 245, 249), font=f_caption)
    else:
        # Robust fallback when captions are not present or empty
        clean_narration = strip_accent_markers(scene.narration_text) if getattr(scene, "narration_text", None) else ""
        wrapped_lines = _wrap_text_pixels(clean_narration, f_caption, max_width=1152)
        pages = [wrapped_lines[i : i + 2] for i in range(0, len(wrapped_lines), 2)] or [[""]]
        page_weights = [max(1, sum(len(line) for line in p)) for p in pages]
        total_weight = float(sum(page_weights))
        target_w = progress * total_weight
        accum = 0.0
        fallback_page = pages[-1]
        page_start_w = 0.0
        fallback_page_w = float(page_weights[-1])
        for p, w in zip(pages, page_weights):
            accum += w
            if target_w <= accum:
                fallback_page = p
                page_start_w = accum - w
                fallback_page_w = float(w)
                break
        p_page = min(1.0, max(0.0, (target_w - page_start_w) / max(1e-4, fallback_page_w)))
        all_words_list = []
        for line_s in fallback_page:
            all_words_list.extend(line_s.split())
        active_w_idx = min(len(all_words_list) - 1, int(p_page * max(1, len(all_words_list)))) if all_words_list else -1

        word_cursor = 0
        is_single = len(fallback_page) == 1
        for l_idx, line_str in enumerate(fallback_page[:2]):
            words = line_str.split()
            line_w = sum(_measure_token_w(w + " ") for w in words)
            tx = sub_x0 + max(32, int((sub_x1 - sub_x0 - line_w) / 2))
            ty = sub_y0 + (34 if is_single else (17 + l_idx * 34))
            cur_x = tx
            for w in words:
                tok = w + " "
                w_len = _measure_token_w(tok)
                if word_cursor < active_w_idx:
                    col = (241, 245, 249)
                    draw.text((cur_x, ty), tok, fill=col, font=f_caption)
                elif word_cursor == active_w_idx:
                    draw.text((cur_x + 1, ty + 1), tok, fill=(0, 0, 0), font=f_caption)
                    try:
                        draw.text(
                            (cur_x, ty),
                            tok,
                            fill=(255, 193, 7),
                            font=f_caption,
                            stroke_width=2,
                            stroke_fill=(20, 14, 4),
                        )
                    except Exception:
                        draw.text((cur_x, ty), tok, fill=(255, 193, 7), font=f_caption)
                else:
                    col = (100, 116, 139)
                    draw.text((cur_x, ty), tok, fill=col, font=f_caption)
                cur_x += int(w_len)
                word_cursor += 1

    # Bottom progress bar with smooth cubic interpolation
    bar_w = int(width * progress)
    draw.rectangle([(0, height - 5), (width, height)], fill=(30, 41, 59))
    draw.rectangle([(0, height - 5), (bar_w, height)], fill=(56, 189, 248))

    return img.tobytes()


_DEFAULT_SCENE_RENDER_CACHE = SceneRenderCache()


async def render_hd_scene_mp4(
    ffmpeg_exe: str,
    topic: str,
    scene: FlowScene,
    total_scenes: int,
    out_mp4: Path,
    lang: str = "ru",
    fps: int = 15,
    scene_cache: Optional[SceneRenderCache] = None,
) -> Tuple[Path, str]:
    """
    Render a single scene into a 1280x720 H.264 + AAC MP4 file:
    - Content-addressable SHA-256 scene cache (.scene_cache/)
    - Zero-Disk in-memory streaming directly to FFmpeg stdin (MoviePy / ShortGPT pipe pattern)
    - Audio-reactive FFT feature extraction (Remotion pattern)
    """
    width, height = 1280, 720
    active_cache = scene_cache or _DEFAULT_SCENE_RENDER_CACHE
    tts_text = getattr(scene, "tts_narration_text", None) or scene.narration_text
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        audio_m4a, duration_sec, voice_label = await synthesize_neural_expressive_audio(
            ffmpeg_exe=ffmpeg_exe,
            narration_text=tts_text,
            out_audio_m4a=tmp_path / "expressive_voice.m4a",
            lang=lang,
            scene_number=scene.scene_number,
            voice_persona=scene.voice_persona,
            voice_style=scene.voice_style,
        )
        scene.duration_sec = int(math.ceil(duration_sec))
        audio_sha256 = (
            hashlib.sha256(audio_m4a.read_bytes()).hexdigest()
            if audio_m4a.is_file()
            else ""
        )
        scene_digest = active_cache.compute_scene_key(
            scene,
            tts_wav_sha256=audio_sha256,
        )
        cached_mp4 = active_cache.get(scene_digest, dest_path=out_mp4)
        if cached_mp4 is not None and cached_mp4.is_file():
            return out_mp4, voice_label

        total_frames = max(fps * 3, int(duration_sec * fps))

        # 1. Extract audio features for live equalizer and vocal reactivity
        audio_features_list = extract_audio_spectrum_features(
            ffmpeg_exe=ffmpeg_exe,
            audio_path=audio_m4a,
            fps=fps,
            total_frames=total_frames,
            num_bands=18,
        )

        # 2. Compute fine-grained captions with acoustic VAD and syllable duration weighting
        f_caption = get_cached_font(21, bold=True)
        captions = compute_scene_word_timings(
            scene_id=scene.scene_id,
            visual_text=scene.narration_text,
            duration_ms=int(total_frames * 1000 / max(1, fps)),
            font_caption=f_caption,
            audio_path=audio_m4a,
            ffmpeg_exe=ffmpeg_exe,
        )
        scene.captions = captions

        # 3. Zero-Disk In-Memory Streaming Pipeline to FFmpeg stdin pipe
        cmd = [
            ffmpeg_exe,
            "-y",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "rgb24",
            "-s",
            f"{width}x{height}",
            "-r",
            str(fps),
            "-i",
            "pipe:0",
            "-i",
            str(audio_m4a),
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "18",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "copy",
            "-shortest",
            "-movflags",
            "+faststart",
            str(out_mp4),
        ]

        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        try:
            for f_idx in range(total_frames):
                feat = audio_features_list[f_idx] if f_idx < len(audio_features_list) else None
                frame_bytes = render_scene_frame_pil(
                    topic=topic,
                    scene=scene,
                    voice_label=voice_label,
                    total_scenes=total_scenes,
                    frame_idx=f_idx,
                    total_frames=total_frames,
                    width=width,
                    height=height,
                    audio_features=feat,
                    fps=fps,
                    captions=captions,
                )
                proc.stdin.write(frame_bytes)
            proc.stdin.close()
            _, stderr = proc.communicate()
            if proc.returncode != 0:
                raise RuntimeError(
                    f"FFmpeg pipeline encoding failed (code {proc.returncode}): {stderr.decode(errors='replace')}"
                )
            if out_mp4.is_file() and out_mp4.stat().st_size > 256:
                active_cache.put(
                    scene_digest,
                    out_mp4,
                    metadata={"scene_id": scene.scene_id, "voice_label": voice_label},
                )
        except Exception:
            if proc.poll() is None:
                proc.kill()
            raise

    return out_mp4, voice_label


def concat_scene_mp4s(
    ffmpeg_exe: str,
    scene_files: List[Path],
    out_mp4: Path,
    transition: str = "cut",
    fade_duration: float = 0.35,
) -> Path:
    """
    Concatenate multiple H.264 scene MP4 clips into a single seamless lesson MP4.
    Supports:
    - 'cut': Instant zero-reencode stream copy (-c copy) via concat demuxer (fastest, lossless)
    - 'fade': Studio-grade crossfade dissolve (xfade + acrossfade) between scenes (ShortGPT / Remotion style)
    """
    if len(scene_files) <= 1 or transition != "fade":
        with tempfile.TemporaryDirectory() as tmpdir:
            list_file = Path(tmpdir) / "concat_list.txt"
            lines = [f"file '{str(p.resolve()).replace(chr(92), '/')}'" for p in scene_files]
            list_file.write_text("\n".join(lines), encoding="utf-8")
            cmd = [
                ffmpeg_exe,
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(list_file),
                "-c",
                "copy",
                "-movflags",
                "+faststart",
                str(out_mp4),
            ]
            subprocess.run(cmd, check=True, capture_output=True)
        return out_mp4

    try:
        inputs = []
        for p in scene_files:
            inputs.extend(["-i", str(p)])

        durations = [_probe_or_estimate_duration(ffmpeg_exe, p) for p in scene_files]
        v_filters = []
        a_filters = []
        last_v = "0:v"
        last_a = "0:a"
        offset = durations[0] - fade_duration

        for idx in range(1, len(scene_files)):
            next_v = f"v{idx}"
            next_a = f"a{idx}"
            v_filters.append(
                f"[{last_v}][{idx}:v]xfade=transition=fade:duration={fade_duration}:offset={max(0.1, round(offset, 2))}[{next_v}]"
            )
            a_filters.append(f"[{last_a}][{idx}:a]acrossfade=d={fade_duration}[{next_a}]")
            last_v = next_v
            last_a = next_a
            if idx < len(durations) - 1:
                offset += durations[idx] - fade_duration

        filter_str = ";".join(v_filters + a_filters)
        cmd = (
            [ffmpeg_exe, "-y"]
            + inputs
            + [
                "-filter_complex",
                filter_str,
                "-map",
                f"[{last_v}]",
                "-map",
                f"[{last_a}]",
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-crf",
                "18",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                "-movflags",
                "+faststart",
                str(out_mp4),
            ]
        )
        subprocess.run(cmd, check=True, capture_output=True)
        return out_mp4
    except Exception:
        return concat_scene_mp4s(ffmpeg_exe, scene_files, out_mp4, transition="cut")


async def create_custom_educational_lesson(
    slug: str,
    topic: str,
    language: str,
    audience: str,
    custom_scenes: Optional[List[Dict[str, Any]]] = None,
    scene_count: int = 4,
) -> Dict[str, Any]:
    """Create a full multi-scene educational video lesson in OUTPUT_DIR/<slug>/."""
    import imageio_ffmpeg

    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    lesson_dir = OUTPUT_DIR / slug
    lesson_dir.mkdir(parents=True, exist_ok=True)

    client = FlowClient()
    project = await client.generate_educational_storyboard(
        topic=topic,
        scene_count=len(custom_scenes) if custom_scenes else scene_count,
        language=language,
        target_audience=audience,
        aspect_ratio="16:9",
        model_key="veo_3_1_t2v_fast_audio",
    )

    if custom_scenes:
        for sc_obj, custom in zip(project.scenes, custom_scenes):
            sc_obj.title = custom.get("title", sc_obj.title)
            sc_obj.narration_text = custom.get("narration_text", sc_obj.narration_text)
            sc_obj.visual_prompt = custom.get("visual_prompt", sc_obj.visual_prompt)
            sc_obj.camera_motion = custom.get("camera_motion", sc_obj.camera_motion)
            sc_obj.on_screen_bullets = custom.get("on_screen_bullets", sc_obj.on_screen_bullets)
            sc_obj.voice_persona = custom.get("voice_persona", sc_obj.voice_persona)
            sc_obj.voice_style = custom.get("voice_style", sc_obj.voice_style)
            if custom.get("tts_narration_text"):
                setattr(sc_obj, "tts_narration_text", custom["tts_narration_text"])
            if custom.get("asset_path"):
                setattr(sc_obj, "asset_path", custom["asset_path"])
            if custom.get("telemetry_badge"):
                setattr(sc_obj, "telemetry_badge", custom["telemetry_badge"])
            if custom.get("highlight_box"):
                setattr(sc_obj, "highlight_box", custom["highlight_box"])
            sc_obj.veo_audio_prompt = build_veo_native_audio_prompt(
                visual_prompt=sc_obj.visual_prompt,
                narration_text=strip_accent_markers(sc_obj.narration_text),
                voice_persona=sc_obj.voice_persona,
                voice_style=sc_obj.voice_style,
            )

    scene_mp4_paths: List[Path] = []
    voices_used: List[str] = []
    for sc in project.scenes:
        out_sc_mp4 = lesson_dir / f"scene_{sc.scene_number:02d}.mp4"
        _, voice_label = await render_hd_scene_mp4(
            ffmpeg_exe=ffmpeg_exe,
            topic=topic,
            scene=sc,
            total_scenes=len(project.scenes),
            out_mp4=out_sc_mp4,
            lang=language,
        )
        voices_used.append(voice_label)
        sc.narration_text = strip_accent_markers(sc.narration_text)
        sc.status = "completed"
        sc.clip_id = f"{project.project_id}_{sc.scene_id}"
        sc.video_url = f"output/{slug}/{out_sc_mp4.name}"
        scene_mp4_paths.append(out_sc_mp4)

    full_lesson_mp4 = lesson_dir / "lesson_full_720p.mp4"
    concat_scene_mp4s(ffmpeg_exe, scene_mp4_paths, full_lesson_mp4)
    project.assembled_video_url = f"output/{slug}/lesson_full_720p.mp4"
    project.status = "assembled"

    vtt_text = build_webvtt_subtitles(project.scenes)
    srt_text = build_srt_subtitles(project.scenes)
    project.subtitles_vtt = vtt_text
    project.subtitles_srt = srt_text

    (lesson_dir / "subtitles.vtt").write_text(vtt_text, encoding="utf-8")
    (lesson_dir / "subtitles.srt").write_text(srt_text, encoding="utf-8")
    (lesson_dir / "storyboard.json").write_text(
        json.dumps(project.to_dict(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    return {
        "slug": slug,
        "lesson_dir": str(lesson_dir),
        "full_video": str(full_lesson_mp4),
        "full_video_size_kb": round(full_lesson_mp4.stat().st_size / 1024, 1),
        "voices_used": voices_used,
        "project": project.to_dict(),
    }


def generate_interactive_html_player(lessons: List[Dict[str, Any]], out_html: Path) -> None:
    """Generate a standalone dark-mode HTML5 player & Veo 3.1 audio prompt inspector in index.html."""
    lessons_json = json.dumps(lessons, ensure_ascii=False)
    html = f"""<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Google Flow Studio — Veo 3.1 Native Audio & Expressive Voiceover Testbench</title>
  <style>
    :root {{
      --bg: #090d16;
      --panel: #111827;
      --card: #1e293b;
      --accent: #38bdf8;
      --accent2: #34d399;
      --text: #f8fafc;
      --muted: #94a3b8;
      --border: #334155;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
      background: var(--bg);
      color: var(--text);
      padding: 24px;
      line-height: 1.5;
    }}
    header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 14px;
      padding: 18px 24px;
      margin-bottom: 24px;
    }}
    .badge {{
      background: rgba(52, 211, 153, 0.15);
      color: var(--accent2);
      border: 1px solid rgba(52, 211, 153, 0.4);
      padding: 5px 14px;
      border-radius: 999px;
      font-size: 13px;
      font-weight: 600;
    }}
    .tabs {{
      display: flex;
      gap: 10px;
      margin-bottom: 18px;
      overflow-x: auto;
      white-space: nowrap;
      padding-bottom: 6px;
      -webkit-overflow-scrolling: touch;
      scrollbar-width: thin;
    }}
    .tab-btn {{
      background: var(--panel);
      color: var(--text);
      border: 1px solid var(--border);
      padding: 10px 16px;
      border-radius: 10px;
      cursor: pointer;
      font-weight: 600;
      font-size: 13.5px;
      flex: 0 0 auto;
      transition: all 0.15s;
    }}
    .tab-btn.active {{
      background: rgba(56, 189, 248, 0.18);
      border-color: var(--accent);
      color: var(--accent);
    }}
    .grid {{
      display: grid;
      grid-template-columns: 1.25fr 1fr;
      gap: 24px;
    }}
    @media (max-width: 1100px) {{
      .grid {{ grid-template-columns: 1fr; }}
    }}
    .panel {{
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 14px;
      padding: 20px;
    }}
    video, #main-player {{
      width: 100%;
      aspect-ratio: 16 / 9;
      display: block;
      border-radius: 10px;
      background: #000;
      border: 1px solid var(--border);
      margin-bottom: 12px;
      object-fit: contain;
    }}
    .playback-rate-group {{
      display: flex;
      align-items: center;
      gap: 6px;
      margin-bottom: 12px;
      flex-wrap: wrap;
    }}
    .rate-btn {{
      background: var(--panel);
      color: var(--muted);
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 4px 10px;
      font-size: 12px;
      font-weight: 600;
      cursor: pointer;
      transition: all 0.12s;
    }}
    .rate-btn:hover {{ color: var(--text); border-color: var(--accent); }}
    .rate-btn.active {{
      background: var(--accent);
      color: #070b14;
      border-color: var(--accent);
    }}
    .scene-card {{
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 14px;
      margin-bottom: 12px;
      cursor: pointer;
      transition: border-color 0.15s;
    }}
    .scene-card:hover {{
      border-color: var(--accent);
    }}
    .scene-card.active-scene {{
      border-color: var(--accent);
      background: rgba(56, 189, 248, 0.12);
      box-shadow: 0 0 10px rgba(56, 189, 248, 0.25);
    }}
    .scene-title {{
      font-weight: 700;
      color: var(--accent);
      margin-bottom: 6px;
      display: flex;
      justify-content: space-between;
    }}
    .narration {{
      font-size: 14px;
      color: #fef08a;
      margin-bottom: 8px;
    }}
    .prompt {{
      font-size: 12px;
      color: var(--muted);
      font-family: Consolas, monospace;
      background: rgba(0,0,0,0.35);
      padding: 8px;
      border-radius: 6px;
      margin-top: 6px;
    }}
    .cli-box {{
      margin-top: 20px;
      background: #050811;
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 14px;
      font-family: Consolas, monospace;
      font-size: 13px;
      color: #a7f3d0;
    }}
    @media (max-width: 640px) {{
      body {{ padding: 10px; }}
      header {{ padding: 10px 12px; flex-direction: column; align-items: flex-start; gap: 8px; margin-bottom: 12px; }}
      header h1 {{ font-size: 15px; }}
      header p {{ font-size: 12px; }}
      .badge {{ display: none; }}
      .hero-card {{ padding: 10px 12px; margin-bottom: 12px; }}
      .hero-card h2 {{ font-size: 13.5px; }}
      .hero-card p {{ display: none; }}
      .hero-card a {{ padding: 8px 12px !important; font-size: 12px !important; }}
      .tabs {{ gap: 6px; margin-bottom: 12px; }}
      .tab-btn {{ font-size: 12px; padding: 7px 10px; }}
      .panel {{ padding: 12px; }}
    }}
  </style>
</head>
<body>
  <header>
    <div>
      <h1 style="font-size: 22px;">🎬 Google Flow Studio — Нативная озвучка Veo 3.1 &amp; Единый женский студийный тембр Gemini 3.8</h1>
      <p style="color: var(--muted); font-size: 14px;">
        gemini_local_ui (M27) • Veo 3.1 Native Dialogue (`veo_3_1_t2v_fast_audio`) + Gemini 3.8 Studio Female (`voice_y0joebp3bwta` Warm Mezzo / `Sulafat`)
      </p>
    </div>
    <span class="badge">🔊 Единый женский студийный голос + Интонационные акценты</span>
  </header>

  <!-- 30+ Minute 6-Section Coursework Defense Workstation Hero Card -->
  <div class="hero-card" style="background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 50%, #0f172a 100%); border: 2px solid #38bdf8; border-radius: 14px; padding: 20px 24px; margin-bottom: 24px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 16px; box-shadow: 0 4px 25px rgba(56, 189, 248, 0.25);">
    <div>
      <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 6px;">
        <span style="background: #38bdf8; color: #070b14; font-weight: 800; font-size: 11px; padding: 3px 10px; border-radius: 999px; text-transform: uppercase; letter-spacing: 0.5px;">Флагманский комплекс</span>
        <h2 style="font-size: 18.5px; color: #f8fafc; font-weight: 700;">🎓 Рабочая станция защиты курсовой работы по ЦОС (30+ минут • 6 разделов • 53 сцены)</h2>
      </div>
      <p style="color: #cbd5e1; font-size: 13.5px; max-width: 860px; line-height: 1.5;">
        Двухрежимный интерактивный пульт защиты (Вариант №5, Motorola DSP56824): <b>Режим 1</b> — Автодоклад ИИ-диктора (<code>voice_y0joebp3bwta</code>); <b>Режим 2</b> — Живая защита с телесуфлёром в реальном времени, янтарно-золотой подсветкой слов (<code>#FFC107</code>), шпаргалкой комиссии ГЭК и 300 DPI чертежами ЕСКД (Э2 А3, ПЭ2 А4).
      </p>
    </div>
    <div style="display: flex; gap: 10px; flex-wrap: wrap;">
      <a href="/output/dsp_defense_index.html" style="background: #38bdf8; color: #070b14; text-decoration: none; font-weight: 700; padding: 11px 20px; border-radius: 10px; font-size: 13.5px; display: inline-flex; align-items: center; gap: 8px; transition: all 0.15s; box-shadow: 0 0 15px rgba(56, 189, 248, 0.4);" onmouseover="this.style.background='#7dd3fc'; this.style.transform='translateY(-1px)';" onmouseout="this.style.background='#38bdf8'; this.style.transform='none';">
        <span>Открыть пульт защиты</span>
        <span style="font-size: 16px;">&rarr;</span>
      </a>
      <a href="dsp_defense_index.html" style="background: #1e293b; color: #38bdf8; border: 1px solid #38bdf8; text-decoration: none; font-weight: 700; padding: 11px 18px; border-radius: 10px; font-size: 13.5px; display: inline-flex; align-items: center; gap: 8px; transition: all 0.15s;" onmouseover="this.style.background='#0369a1'; this.style.color='#fff';" onmouseout="this.style.background='#1e293b'; this.style.color='#38bdf8';">
        <span>Пульт в текущем каталоге</span>
        <span style="font-size: 16px;">&rarr;</span>
      </a>
    </div>
  </div>

  <div class="tabs" id="lesson-tabs" role="tablist"></div>

  <div class="grid">
    <div class="panel">
      <h2 id="active-title" style="font-size: 18px; margin-bottom: 12px;"></h2>
      <video id="main-player" controls preload="metadata"></video>
      <div class="playback-rate-group">
        <span style="font-size:12.5px; color:var(--muted); font-weight:600;">⚡ Скорость:</span>
        <button type="button" class="rate-btn" onclick="setPlaybackSpeed(0.75)">0.75x</button>
        <button type="button" class="rate-btn active" onclick="setPlaybackSpeed(1.0)">1.0x</button>
        <button type="button" class="rate-btn" onclick="setPlaybackSpeed(1.25)">1.25x</button>
        <button type="button" class="rate-btn" onclick="setPlaybackSpeed(1.5)">1.5x</button>
        <button type="button" class="rate-btn" onclick="setPlaybackSpeed(2.0)">2.0x</button>
      </div>
      <div style="display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 14px;" id="clip-buttons"></div>
      <div class="cli-box">
        <div style="color: var(--accent); font-weight: bold; margin-bottom: 6px;">Сгенерировать свой учебный ролик (выделяй *смысловые акценты* звездочками и +ударные гласные):</div>
        <code>python flow_testbench_runner.py --topic "Квантовая криптография и протокол BB84" --lang ru --scenes 4</code>
      </div>
    </div>

    <div class="panel">
      <h3 style="font-size: 16px; margin-bottom: 12px;">Раскадровка сцен, профили голоса и нативные аудио-промпты Veo 3.1</h3>
      <div id="scenes-container"></div>
    </div>
  </div>

  <script>
    const LESSONS = {lessons_json};
    let currentIdx = 0;
    let currentSceneIdx = -1;

    // DEF-UI-001: Resolve relative paths dynamically
    function resolveMediaPath(url) {{
      if (!url) return '';
      const inOutputDir = window.location.pathname.includes('/output/') || 
                          window.location.pathname.endsWith('/output/index.html') ||
                          (!window.location.pathname.endsWith('/') && window.location.pathname.split('/').slice(-2, -1)[0] === 'output');
      if (inOutputDir && url.startsWith('output/')) {{
        return url.replace(/^output[/]/, '');
      }}
      return url;
    }}

    // DEF-UI-002: Dynamic WebVTT subtitle track mounting
    function mountSubtitles(vttContent, lang = 'ru', label = 'Русский') {{
      const player = document.getElementById('main-player');
      Array.from(player.querySelectorAll('track')).forEach(t => {{
        if (t.src && t.src.startsWith('blob:')) URL.revokeObjectURL(t.src);
        t.remove();
      }});
      if (!vttContent) return;

      const blob = new Blob([vttContent], {{ type: 'text/vtt' }});
      const track = document.createElement('track');
      track.kind = 'subtitles';
      track.label = label;
      track.srclang = lang;
      track.src = URL.createObjectURL(blob);
      track.default = true;
      player.appendChild(track);

      if (player.textTracks && player.textTracks.length > 0) {{
        player.textTracks[0].mode = 'showing';
      }}
    }}

    // DEF-UI-004: Playback rate handler
    function setPlaybackSpeed(rate) {{
      const player = document.getElementById('main-player');
      player.playbackRate = rate;
      document.querySelectorAll('.rate-btn').forEach(btn => {{
        btn.classList.toggle('active', parseFloat(btn.textContent) === rate);
      }});
    }}

    // DEF-UI-006: Centralized active clip state manager
    function setActiveClip(clipIdx) {{
      currentSceneIdx = clipIdx;
      const clipBtns = document.querySelectorAll('#clip-buttons .tab-btn');
      clipBtns.forEach((btn, idx) => {{
        const isTarget = (clipIdx === -1 && idx === 0) || (clipIdx >= 0 && idx === clipIdx + 1);
        btn.classList.toggle('active', isTarget);
      }});

      const cards = document.querySelectorAll('#scenes-container .scene-card');
      cards.forEach((card, idx) => {{
        const isTarget = (idx === clipIdx);
        card.classList.toggle('active-scene', isTarget);
        if (isTarget) {{
          card.scrollIntoView({{ behavior: 'smooth', block: 'nearest' }});
        }}
      }});
    }}

    // DEF-UI-005: Decoupled tab initialization (zero DOM node destruction)
    function initTabsOnce() {{
      const tabsEl = document.getElementById('lesson-tabs');
      tabsEl.innerHTML = '';
      LESSONS.forEach((item, idx) => {{
        const btn = document.createElement('button');
        btn.className = 'tab-btn' + (idx === 0 ? ' active' : '');
        btn.setAttribute('role', 'tab');
        btn.setAttribute('aria-selected', idx === 0 ? 'true' : 'false');
        btn.textContent = `${{idx + 1}}. ${{item.project.topic}} (${{item.project.language.toUpperCase()}} • ${{item.full_video_size_kb}} KB)`;
        btn.onclick = () => selectLesson(idx);
        tabsEl.appendChild(btn);
      }});
    }}

    function updateActiveTab(activeIdx) {{
      const tabsEl = document.getElementById('lesson-tabs');
      Array.from(tabsEl.children).forEach((btn, idx) => {{
        const isActive = (idx === activeIdx);
        btn.classList.toggle('active', isActive);
        btn.setAttribute('aria-selected', isActive ? 'true' : 'false');
      }});
    }}

    function selectLesson(idx) {{
      currentIdx = idx;
      currentSceneIdx = -1;
      updateActiveTab(idx);

      const item = LESSONS[idx];
      const proj = item.project;
      document.getElementById('active-title').textContent = `${{proj.topic}} (Полный урок: ${{proj.scenes.length}} сцен • Модель: ${{proj.model_key}})`;
      const player = document.getElementById('main-player');
      player.src = resolveMediaPath(proj.assembled_video_url);
      player.load();

      mountSubtitles(proj.subtitles_vtt, proj.language, proj.language === 'en' ? 'English' : 'Русский');

      const clipBtns = document.getElementById('clip-buttons');
      clipBtns.innerHTML = '';
      const fullBtn = document.createElement('button');
      fullBtn.className = 'tab-btn active';
      fullBtn.textContent = '▶ Весь урок целиком (.mp4)';
      fullBtn.onclick = () => {{
        player.src = resolveMediaPath(proj.assembled_video_url);
        player.play();
        setActiveClip(-1);
      }};
      clipBtns.appendChild(fullBtn);

      const scenesEl = document.getElementById('scenes-container');
      scenesEl.innerHTML = '';
      proj.scenes.forEach((sc, sIdx) => {{
        const sBtn = document.createElement('button');
        sBtn.className = 'tab-btn';
        sBtn.textContent = `Сцена ${{sc.scene_number}} (${{sc.duration_sec}}с)`;
        sBtn.onclick = () => {{
          player.src = resolveMediaPath(sc.video_url);
          player.play();
          setActiveClip(sIdx);
        }};
        clipBtns.appendChild(sBtn);

        const voiceUsed = (item.voices_used && item.voices_used[sIdx]) ? item.voices_used[sIdx] : sc.voice_persona;
        const card = document.createElement('div');
        card.className = 'scene-card';
        card.onclick = () => {{
          player.src = resolveMediaPath(sc.video_url);
          player.play();
          setActiveClip(sIdx);
        }};
        card.innerHTML = `
          <div class="scene-title">
            <span>#${{sc.scene_number}} • ${{sc.title}}</span>
            <span style="font-size:12px; color:#34d399;">🔊 ${{voiceUsed}} (${{sc.duration_sec}}s)</span>
          </div>
          <div class="narration">🗣 ${{sc.narration_text}}</div>
          <div style="font-size:13px; color:#cbd5e1; margin-bottom:6px;">
            📌 ${{sc.on_screen_bullets.join(' • ')}}
          </div>
          <div class="prompt">🎙 <b>Veo 3.1 Native Audio Prompt:</b> ${{sc.veo_audio_prompt || sc.visual_prompt}}</div>
        `;
        scenesEl.appendChild(card);
      }});
    }}

    // DEF-UI-008: Ensure file:// links resolve cleanly
    if (window.location.protocol === 'file:') {{
      document.querySelectorAll('a[href="/output/dsp_defense_index.html"]').forEach(a => {{
        a.href = 'dsp_defense_index.html';
      }});
    }}

    document.addEventListener('DOMContentLoaded', () => {{
      initTabsOnce();
      selectLesson(0);
    }});
    if (document.readyState === 'complete' || document.readyState === 'interactive') {{
      initTabsOnce();
      selectLesson(0);
    }}
  </script>
</body>
</html>
"""
    out_html.write_text(html, encoding="utf-8")


async def build_dsp_defense_suite() -> List[Dict[str, Any]]:
    """
    Generate the full 6-section DSP Coursework Defense suite (53 scenes, 32:01)
    plus the unified 53-scene Master Defense Video (`lesson_07_ru_dsp_defense_master`)
    and dual-mode interactive Defense Deck (`output/dsp_defense_index.html`).
    """
    import imageio_ffmpeg
    from src.dsp_defense_cycles import (
        DSP_DEFENSE_CYCLES,
        format_dsp_phonetics_ru,
        generate_dsp_defense_player_html,
        stage_dsp_coursework_assets,
    )

    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    staged_assets = stage_dsp_coursework_assets(OUTPUT_DIR)

    dsp_results: List[Dict[str, Any]] = []
    all_scene_mp4s: List[Path] = []
    master_scenes_objs: List[FlowScene] = []
    master_voices: List[str] = []

    for cycle_spec in DSP_DEFENSE_CYCLES:
        prepared_scenes: List[Dict[str, Any]] = []
        for sc in cycle_spec["scenes"]:
            sc_copy = dict(sc)
            sc_copy["tts_narration_text"] = sc.get("tts_narration_text") or format_dsp_phonetics_ru(sc["narration_text"])
            asset_key = sc.get("asset_key")
            if asset_key and asset_key in staged_assets:
                sc_copy["asset_path"] = str(staged_assets[asset_key])
            prepared_scenes.append(sc_copy)

        res_cycle = await create_custom_educational_lesson(
            slug=cycle_spec["slug"],
            topic=cycle_spec["topic"],
            language=cycle_spec["language"],
            audience=cycle_spec["audience"],
            custom_scenes=prepared_scenes,
        )
        dsp_results.append(res_cycle)

        cycle_dir = OUTPUT_DIR / cycle_spec["slug"]
        for sc_dict, v_label in zip(res_cycle["project"]["scenes"], res_cycle["voices_used"]):
            sc_mp4 = cycle_dir / f"scene_{sc_dict['scene_number']:02d}.mp4"
            all_scene_mp4s.append(sc_mp4)
            global_num = len(master_scenes_objs) + 1
            master_sc = FlowScene(
                scene_id=f"sc_{global_num:02d}",
                scene_number=global_num,
                title=f"[Цикл {cycle_spec['cycle_number']}] {sc_dict['title']}",
                narration_text=sc_dict["narration_text"],
                visual_prompt=sc_dict["visual_prompt"],
                duration_sec=sc_dict["duration_sec"],
                camera_motion=sc_dict["camera_motion"],
                on_screen_bullets=sc_dict["on_screen_bullets"],
                status="completed",
                clip_id=f"master_sc_{global_num:02d}",
                video_url=sc_dict["video_url"],
                voice_persona=sc_dict["voice_persona"],
                voice_style=sc_dict["voice_style"],
                native_veo_audio=True,
                veo_audio_prompt=sc_dict.get("veo_audio_prompt"),
                tts_narration_text=sc_dict.get("tts_narration_text"),
            )
            master_scenes_objs.append(master_sc)
            master_voices.append(v_label)

    # Assemble the unified Master Defense Video without re-encoding
    master_slug = "lesson_07_ru_dsp_defense_master"
    master_dir = OUTPUT_DIR / master_slug
    master_dir.mkdir(parents=True, exist_ok=True)
    master_mp4 = master_dir / "lesson_full_720p.mp4"
    concat_scene_mp4s(ffmpeg_exe, all_scene_mp4s, master_mp4)

    master_vtt = build_webvtt_subtitles(master_scenes_objs)
    master_srt = build_srt_subtitles(master_scenes_objs)
    (master_dir / "subtitles.vtt").write_text(master_vtt, encoding="utf-8")
    (master_dir / "subtitles.srt").write_text(master_srt, encoding="utf-8")

    master_project = FlowEducationalProject(
        project_id="flow_dsp_master_v5",
        topic=f"Полный доклад защиты курсовой ЦОС: Вариант №5 (Motorola DSP56824, {len(master_scenes_objs)} сцен, 32:01)",
        language="ru",
        target_audience="state_defense_commission",
        aspect_ratio="16:9",
        model_key="veo_3_1_t2v_fast_audio",
        scenes=master_scenes_objs,
        status="assembled",
        assembled_video_url=f"output/{master_slug}/lesson_full_720p.mp4",
        subtitles_vtt=master_vtt,
        subtitles_srt=master_srt,
    )
    (master_dir / "storyboard.json").write_text(
        json.dumps(master_project.to_dict(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    master_entry = {
        "slug": master_slug,
        "lesson_dir": str(master_dir),
        "full_video": str(master_mp4),
        "full_video_size_kb": round(master_mp4.stat().st_size / 1024, 1),
        "voices_used": master_voices,
        "project": master_project.to_dict(),
    }
    dsp_suite = [master_entry] + dsp_results

    generate_dsp_defense_player_html(dsp_suite, OUTPUT_DIR / "dsp_defense_index.html", relative_to_output=True)
    generate_dsp_defense_player_html(dsp_suite, TESTBENCH_DIR / "dsp_defense_index.html", relative_to_output=False)
    return dsp_suite


render_all_dsp_defense_cycles = build_dsp_defense_suite

from src.ttd_pilot_assembler import (
    register_lesson_in_interactive_player,
    render_ttd_pilot_lesson,
)


async def main() -> None:
    parser = argparse.ArgumentParser(description="Google Flow Educational Video Studio Testbench")
    parser.add_argument("--topic", type=str, default="", help="Custom topic to generate an educational video for")
    parser.add_argument("--lang", type=str, default="ru", help="Language code: ru or en")
    parser.add_argument("--scenes", type=int, default=4, help="Number of scenes (1..12)")
    parser.add_argument("--audience", type=str, default="university", help="Target audience level")
    parser.add_argument("--dsp-defense", action="store_true", help="Build full 6-section 30+ min DSP Coursework Defense suite")
    parser.add_argument("--ttd-pilot", action="store_true", help="Build TTD Crossroads pilot test scene")
    parser.add_argument("--lesson", type=str, default="", help="Specific lesson slug to render (e.g. lesson_ttd_pilot_crossroads)")
    parser.add_argument("--fps", type=int, default=15, help="Frame rate")
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    purge_unauthorized_tts_cache()
    generated_lessons: List[Dict[str, Any]] = []

    if args.ttd_pilot or args.lesson == "lesson_ttd_pilot_crossroads":
        res_ttd = await render_ttd_pilot_lesson(slug="lesson_ttd_pilot_crossroads", fps=args.fps)
        generated_lessons.append(res_ttd)
    elif args.topic.strip():
        slug = "custom_" + "".join(c if c.isalnum() else "_" for c in args.topic.lower())[:28].strip("_")
        res = await create_custom_educational_lesson(
            slug=slug,
            topic=args.topic.strip(),
            language=args.lang,
            audience=args.audience,
            scene_count=args.scenes,
        )
        generated_lessons.append(res)
    else:
        # 1. Russian Educational Lesson with SSML Prosodic Accents (*...*) and +Stress Marks
        ru_scenes = [
            {
                "title": "Проблема узкого места KV-кэша в трансформерах",
                "voice_persona": "Kore",
                "voice_style": "warm, expressive Russian lecturer with clear vocal emphasis on key architectural terms",
                "narration_text": "Предст+авьте соврем+енный трансф+ормер на дл+инном конт+ексте. *Гл+авная пробл+ема здесь — не с+ами вычисл+ения, а гиг+антский объ+ём к+эша ключ+ей и знач+ений*, кот+орый перегруж+ает пропускн+ую спос+обность видеоп+амяти.",
                "visual_prompt": "Cinematic 3D visualization of GPU HBM memory bandwidth bottleneck in standard Multi-Head Attention, glowing tensor blocks saturating data bus, slow push-in, 16:9.",
                "camera_motion": "slow push-in",
                "on_screen_bullets": [
                    "Линейный рост KV-кэша от длины контекста",
                    "Узкое место: пропускная способность памяти (Memory Bound)",
                    "Необходимость латентного сжатия представлений",
                ],
            },
            {
                "title": "Механизм Multi-Head Latent Attention (MLA)",
                "voice_persona": "Aoede",
                "voice_style": "articulate co-lecturer, dynamic intonation with deliberate emphasis on mathematical mechanism",
                "narration_text": "Именно по+этому механизм лат+ентного вним+ания мен+яет пр+авила игр+ы. *Вм+есто хран+ения п+олных м+атриц ключ+ей и знач+ений, мы сжим+аем их в ед+иный комп+актный лат+ентный в+ектор*, сокращ+ая расх+од п+амяти б+олее чем на в+осемьдесят проц+ентов!",
                "visual_prompt": "Clean dark laboratory schematic of Low-Rank Joint Compression matrix projecting high-dimensional keys and values into a compact glowing latent vector c_t^KV, orbital pan.",
                "camera_motion": "orbital pan",
                "on_screen_bullets": [
                    "Низкоранговая проекция в латентный вектор c_t^KV",
                    "Декомпрессия на лету внутри вычислительного ядра",
                    "Сокращение KV-кэша более чем на 80%",
                ],
            },
            {
                "title": "Маршрутизация экспертов Mixture-of-Experts (MoE)",
                "voice_persona": "Kore",
                "voice_style": "warm, expressive Russian lecturer with clear vocal emphasis on routing dynamics",
                "narration_text": "Д+альше вступ+ает в раб+оту разр+еженная сеть эксп+ертов. *+Умный маршрутиз+атор активирует для к+аждого ток+ена лишь м+алую д+олю узкоспециализ+ированных нейросетей*, сохран+яя ск+орость лёгкой мод+ели при зн+аниях гиг+анта.",
                "visual_prompt": "3D neural routing graph where tokens flow through a gating router activating top-k glowing expert modules while remaining experts stay dormant, macro tracking shot.",
                "camera_motion": "macro tracking shot",
                "on_screen_bullets": [
                    "Активация только Top-K экспертов на каждый токен",
                    "Разделение на общих (Shared) и узких (Routed) экспертов",
                    "Автоматическая балансировка нагрузки без потерь",
                ],
            },
            {
                "title": "Итоги: эффективность на сверхдлинных контекстах",
                "voice_persona": "Aoede",
                "voice_style": "articulate co-lecturer, inspiring concluding cadence with clear stress on final takeaway",
                "narration_text": "В результ+ате мы получ+аем *иде+альный бал+анс п+амяти и вычисл+ений*: мод+ель своб+одно уд+ерживает с+отни т+ысяч ток+енов конт+екста и генер+ирует отв+еты с максим+альной ск+оростью.",
                "visual_prompt": "Isometric overview of a high-throughput inference cluster processing million-token streams with green telemetry curves, isometric zoom-out, 16:9.",
                "camera_motion": "isometric zoom-out",
                "on_screen_bullets": [
                    "Высокая скорость генерации (Tokens per second)",
                    "Масштабируемость до сотен тысяч токенов контекста",
                    "Синергия латентного внимания MLA и MoE",
                ],
            },
        ]
        res_ru = await create_custom_educational_lesson(
            slug="lesson_01_ru_transformer_mla",
            topic="Архитектура Multi-Head Latent Attention (MLA) и MoE",
            language="ru",
            audience="university",
            custom_scenes=ru_scenes,
        )
        generated_lessons.append(res_ru)

        # 2. English Educational Lesson with SSML Prosodic Accents (*...*)
        en_scenes = [
            {
                "title": "EPR Paradox and Local Realism",
                "voice_persona": "Kore",
                "voice_style": "warm, engaging physics lecturer with natural human cadence and emphasis on key concepts",
                "narration_text": "In nineteen thirty-five, Einstein, Podolsky, and Rosen posed a profound challenge to quantum mechanics. *They argued that if two particles are separated by light-years, measuring one cannot instantaneously dictate the state of the other* — unless hidden local variables were already fixed at creation.",
                "visual_prompt": "Two entangled photons emitted from a nonlinear crystal flying in opposite directions through optical fibers in a dark quantum optics lab, slow push-in.",
                "camera_motion": "slow push-in",
                "on_screen_bullets": [
                    "EPR Paradox: completeness of quantum wavefunctions",
                    "Local realism vs non-local quantum correlations",
                    "Spin-singlet entangled pair generation",
                ],
            },
            {
                "title": "Bell Theorem and CHSH Inequality Bound",
                "voice_persona": "Puck",
                "voice_style": "articulate science communicator, deliberate vocal emphasis on mathematical threshold",
                "narration_text": "Decades later, John Stewart Bell turned philosophy into a testable equation. *Any universe governed by local hidden variables is strictly trapped below a correlation limit of two — yet entangled quantum particles shatter that ceiling*, reaching two times the square root of two.",
                "visual_prompt": "3D geometric correlation curve comparing classical linear triangle bound S <= 2 against quantum sinusoidal curve peaking at 2*sqrt(2) = 2.828, orbital pan.",
                "camera_motion": "orbital pan",
                "on_screen_bullets": [
                    "Classical hidden-variable bound: |S| <= 2",
                    "Quantum Tsirelson bound: |S| = 2 * sqrt(2) ≈ 2.828",
                    "Experimental violation at 22.5 degree polarizer angles",
                ],
            },
            {
                "title": "Quantum Key Distribution and Security",
                "voice_persona": "Kore",
                "voice_style": "warm, engaging physics lecturer with clear concluding emphasis",
                "narration_text": "Today, Bell inequality violation powers real-world quantum cryptography. *Because any eavesdropper measuring the channel immediately collapses the entanglement and drops the Bell score*, security is guaranteed by the fundamental laws of physics.",
                "visual_prompt": "Quantum communication satellite linking two ground stations with entangled laser beams and live Bell parameter S telemetry readout, isometric zoom-out.",
                "camera_motion": "isometric zoom-out",
                "on_screen_bullets": [
                    "Device-independent quantum key distribution (QKD)",
                    "Instant detection of eavesdropping via Bell test",
                    "Foundation of quantum networks and teleportation",
                ],
            },
        ]
        res_en = await create_custom_educational_lesson(
            slug="lesson_02_en_quantum_bell",
            topic="Quantum Entanglement and Bell Inequalities",
            language="en",
            audience="university",
            custom_scenes=en_scenes,
        )
        generated_lessons.append(res_en)

        # 3. 6-Section DSP Coursework Defense Suite (Variant 5, Motorola DSP56824)
        dsp_suite = await build_dsp_defense_suite()
        generated_lessons.extend(dsp_suite)

    if not (args.ttd_pilot or args.lesson == "lesson_ttd_pilot_crossroads"):
        generate_interactive_html_player(generated_lessons, index_html)
        generate_interactive_html_player(generated_lessons, OUTPUT_DIR / "index.html")

    summary = {
        "status": "READY",
        "testbench_dir": str(TESTBENCH_DIR),
        "interactive_player_html": str(index_html),
        "lessons_generated": [
            {
                "slug": item["slug"],
                "topic": item["project"]["topic"],
                "language": item["project"]["language"],
                "scenes_count": len(item["project"]["scenes"]),
                "voices_used": item["voices_used"],
                "full_video_mp4": item["full_video"],
                "size_kb": item["full_video_size_kb"],
            }
            for item in generated_lessons
        ],
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
