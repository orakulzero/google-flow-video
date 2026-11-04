"""
src/flow_cinematic_audio.py
Comprehensive 5-Layer Cinematic Audio Engine & Russian Studio Narration for Episode 1.
Features:
- 48,000 Hz 16-bit stereo PCM procedural DSP engine using NumPy, scipy, and wave.
- Layer 1: Single-speaker Russian studio narration timbre-locked to voice_y0joebp3bwta.
- Layer 2: Combat SFX (metallic shield clashes, resonant bell decay, blade slashes, spark crackle, mana shockwave).
- Layer 3: Victory Fanfare (major brass triad chords at t ~ 20.0s - 29.8s + crystalline chime arpeggios).
- Layer 4: Stream Ambiance (mechanical keyboard/mouse clicks + luxury donation chime at t = 30.0s).
- Layer 5: Environmental Ambience (dark cello fifths, 40-60 Hz war drums, fortress storm, 42 Hz void drone fading to silence).
- Subtitle generators: WebVTT (.vtt) and SubRip (.srt).
- 100% English-only source code and comments (0 literal Cyrillic characters; Russian text strictly unicode escaped).
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
import hashlib
import io
import math
import os
from pathlib import Path
import struct
from typing import Any, Dict, List, Optional, Tuple
import wave

import numpy as np
from scipy import signal

SAMPLE_RATE: int = 48000
CHANNELS: int = 2
DEFAULT_EP01_DURATION_SEC: float = 69.792  # 1675 frames @ 24.0 fps
VOICE_PERSONA_RU: str = "voice_y0joebp3bwta"


@dataclass(frozen=True)
class NarrationBeat:
    beat_id: int
    t_start: float
    t_end: float
    transcript_ru: str
    english_meaning: str


# 7 Chronological narration beats matching Episode 1 storyline (Unicode escaped)
EP01_NARRATION_BEATS: List[NarrationBeat] = [
    NarrationBeat(
        beat_id=1,
        t_start=0.0,
        t_end=7.5,
        transcript_ru=(
            "\u0421\u043e\u0442\u044b\u0439 \u044d\u0442\u0430\u0436 \u0446\u0438\u0442\u0430\u0434\u0435\u043b\u0438. "
            "\u041d\u0435\u043f\u0440\u043e\u0445\u043e\u0434\u0438\u043c\u044b\u0439 \u0444\u0438\u043d\u0430\u043b: "
            "\u0422\u0435\u043d\u0435\u0432\u043e\u0439 \u0411\u043e\u0441\u0441 \u043f\u0440\u043e\u0442\u0438\u0432 "
            "\u043f\u043e\u0441\u043b\u0435\u0434\u043d\u0435\u0433\u043e \u0440\u0443\u0431\u0435\u0436\u0430 \u0438\u043c\u043f\u0435\u0440\u0438\u0438."
        ),
        english_meaning="100th floor citadel. Impossible climax: Shadow Boss against the empire's last defense.",
    ),
    NarrationBeat(
        beat_id=2,
        t_start=9.92,
        t_end=17.5,
        transcript_ru=(
            "\u042f\u0440\u043e\u0441\u0442\u044c \u0431\u0435\u0437\u0434\u043d\u044b! "
            "\u0420\u044b\u0446\u0430\u0440\u044c \u041b\u0443\u043a\u0430\u0441 \u043f\u0440\u0438\u043d\u0438\u043c\u0430\u0435\u0442 "
            "\u0443\u0434\u0430\u0440 \u043d\u0430 \u043a\u0440\u0443\u0433\u043b\u044b\u0439 \u0449\u0438\u0442, "
            "\u0432\u044b\u0441\u0435\u043a\u0430\u044f \u0441\u043d\u043e\u043f \u043e\u0441\u043b\u0435\u043f\u0438\u0442\u0435\u043b\u044c\u043d\u044b\u0445 \u0438\u0441\u043a\u0440."
        ),
        english_meaning="Abyssal fury! Knight Lucas parries the colossal blow with his round shield, showering sparks.",
    ),
    NarrationBeat(
        beat_id=3,
        t_start=19.88,
        t_end=28.5,
        transcript_ru=(
            "\u0420\u0435\u0448\u0430\u044e\u0449\u0438\u0439 \u0432\u044b\u043f\u0430\u0434! "
            "\u0417\u0430\u043a\u0430\u043b\u0451\u043d\u043d\u044b\u0439 \u043a\u043b\u0438\u043d\u043e\u043a "
            "\u043f\u0440\u043e\u043d\u0437\u0430\u0435\u0442 \u044f\u0434\u0440\u043e \u0431\u043e\u0441\u0441\u0430. "
            "\u0412\u0441\u043f\u044b\u0448\u043a\u0430 \u0437\u043e\u043b\u043e\u0442\u043e\u0433\u043e \u0441\u0432\u0435\u0442\u0430 "
            "\u2014 \u043f\u043e\u0431\u0435\u0434\u0430!"
        ),
        english_meaning="Decisive thrust! Hardened steel pierces the core. Golden light erupts: victory!",
    ),
    NarrationBeat(
        beat_id=4,
        t_start=29.92,
        t_end=38.0,
        transcript_ru=(
            "\u0414\u0432\u043e\u0439\u043d\u044b\u0435 \u043c\u043e\u043d\u0438\u0442\u043e\u0440\u044b "
            "\u0432\u0441\u043f\u044b\u0445\u0438\u0432\u0430\u044e\u0442 \u0437\u043e\u043b\u043e\u0442\u043e\u043c. "
            "\u0427\u0430\u0442 \u0432\u0437\u0440\u044b\u0432\u0430\u0435\u0442\u0441\u044f, "
            "\u0430 \u0434\u043e\u043d\u0430\u0442 \u043e\u0442 \u0424\u043e\u043a\u0441\u0438 "
            "\u043e\u0437\u0430\u0440\u044f\u0435\u0442 \u0442\u0440\u0430\u043d\u0441\u043b\u044f\u0446\u0438\u044e."
        ),
        english_meaning="Dual monitors flare gold. Chat explodes, and Foxy's luxury donation illuminates the broadcast.",
    ),
    NarrationBeat(
        beat_id=5,
        t_start=39.84,
        t_end=48.0,
        transcript_ru=(
            "\u0420\u0430\u043d\u0433 \u042d\u0441-\u042d\u0441-\u042d\u0440. "
            "\u0413\u043b\u0430\u0432\u043d\u044b\u0439 \u0433\u0435\u0440\u043e\u0439 \u0444\u0438\u043d\u0430\u043b\u0430 "
            "\u2014 \u041b\u0443\u043a\u0430\u0441. "
            "\u0415\u0434\u0438\u043d\u0441\u0442\u0432\u0435\u043d\u043d\u044b\u0439, \u043a\u0442\u043e "
            "\u0432\u044b\u0436\u0438\u043b \u0432 \u044d\u0442\u043e\u0439 \u043c\u044f\u0441\u043e\u0440\u0443\u0431\u043a\u0435."
        ),
        english_meaning="SSR Rank. Stage MVP: Lucas. The sole survivor who stood until the very end.",
    ),
    NarrationBeat(
        beat_id=6,
        t_start=49.80,
        t_end=58.5,
        transcript_ru=(
            "\u0420\u0430\u0437\u0440\u0443\u0448\u0435\u043d\u043d\u044b\u0439 \u0442\u0440\u043e\u043d\u043d\u044b\u0439 \u0437\u0430\u043b. "
            "\u041f\u0430\u0432\u0448\u0438\u0439 \u0431\u043e\u0441\u0441 \u043e\u0431\u0440\u0430\u0449\u0430\u0435\u0442\u0441\u044f \u0432 \u043f\u0440\u0430\u0445. "
            "\u041d\u043e \u043a\u0430\u043a\u0443\u044e \u0446\u0435\u043d\u0443 \u043f\u0440\u0438\u0448\u043b\u043e\u0441\u044c \u0437\u0430\u043f\u043b\u0430\u0442\u0438\u0442\u044c?"
        ),
        english_meaning="Ruined throne hall. The fallen boss crumbles to dust. But at what cost?",
    ),
    NarrationBeat(
        beat_id=7,
        t_start=59.84,
        t_end=67.5,
        transcript_ru=(
            "\u0422\u0438\u0448\u0438\u043d\u0430. "
            "\u0422\u044c\u043c\u0430 \u043f\u043e\u0433\u043b\u043e\u0449\u0430\u0435\u0442 \u0437\u0430\u043b. "
            "\u041b\u0438\u0448\u044c \u043e\u0434\u0438\u043d\u043e\u043a\u0430\u044f \u0441\u043f\u0438\u043d\u0430 "
            "\u0440\u044b\u0446\u0430\u0440\u044f \u0440\u0430\u0441\u0442\u0432\u043e\u0440\u044f\u0435\u0442\u0441\u044f \u0432 \u0431\u0435\u0437\u0434\u043d\u0435."
        ),
        english_meaning="Silence. Darkness consumes the hall. Only the knight's solitary back fades into the void.",
    ),
]


def format_webvtt_timecode(seconds: float) -> str:
    """Format seconds into HH:MM:SS.mmm format for WebVTT."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60.0
    return f"{h:02d}:{m:02d}:{s:06.3f}"


def format_srt_timecode(seconds: float) -> str:
    """Format seconds into HH:MM:SS,mmm format for SubRip (SRT)."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int(round((seconds - int(seconds)) * 1000.0))
    if ms >= 1000:
        ms = 999
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def generate_webvtt_subtitles(beats: Optional[List[NarrationBeat]] = None) -> str:
    """Generate RFC-compliant WebVTT subtitle track string."""
    active_beats = beats or EP01_NARRATION_BEATS
    lines = ["WEBVTT", ""]
    for idx, b in enumerate(active_beats, start=1):
        t0 = format_webvtt_timecode(b.t_start)
        t1 = format_webvtt_timecode(b.t_end)
        lines.append(f"{idx}")
        lines.append(f"{t0} --> {t1}")
        lines.append(b.transcript_ru)
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def generate_srt_subtitles(beats: Optional[List[NarrationBeat]] = None) -> str:
    """Generate standard SubRip (.srt) subtitle track string."""
    active_beats = beats or EP01_NARRATION_BEATS
    lines = []
    for idx, b in enumerate(active_beats, start=1):
        t0 = format_srt_timecode(b.t_start)
        t1 = format_srt_timecode(b.t_end)
        lines.append(f"{idx}")
        lines.append(f"{t0} --> {t1}")
        lines.append(b.transcript_ru)
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def create_empty_stereo(duration_sec: float, sample_rate: int = SAMPLE_RATE) -> np.ndarray:
    """Create zeroed stereo buffer of shape (n_samples, 2) in float32."""
    n_samples = int(round(duration_sec * sample_rate))
    return np.zeros((n_samples, 2), dtype=np.float32)


def safe_add_clip(buffer: np.ndarray, clip: np.ndarray, start_idx: int) -> None:
    """Safely add a clip into a master buffer with boundary clamping."""
    n_total = buffer.shape[0]
    if start_idx >= n_total or start_idx < 0:
        return
    end_idx = min(n_total, start_idx + clip.shape[0])
    insert_len = end_idx - start_idx
    if insert_len > 0:
        buffer[start_idx:end_idx, :] += clip[:insert_len, :]



def resample_wav_to_stereo_48k(wav_path: Path, target_sr: int = SAMPLE_RATE) -> np.ndarray:
    """Read a RIFF WAV file and resample to float32 stereo at 48,000 Hz."""
    with wave.open(str(wav_path), "rb") as wf:
        n_ch = wf.getnchannels()
        sampwidth = wf.getsampwidth()
        src_sr = wf.getframerate()
        n_frames = wf.getnframes()
        raw_bytes = wf.readframes(n_frames)

    if sampwidth == 2:
        raw_samples = np.frombuffer(raw_bytes, dtype=np.int16).astype(np.float32) / 32768.0
    elif sampwidth == 4:
        raw_samples = np.frombuffer(raw_bytes, dtype=np.int32).astype(np.float32) / 2147483648.0
    else:
        raw_samples = np.frombuffer(raw_bytes, dtype=np.uint8).astype(np.float32) / 128.0 - 1.0

    if n_ch == 1:
        mono = raw_samples
    else:
        mono = raw_samples.reshape(-1, n_ch).mean(axis=1)

    if src_sr != target_sr:
        gcd = math.gcd(src_sr, target_sr)
        up = target_sr // gcd
        down = src_sr // gcd
        resampled_mono = signal.resample_poly(mono, up, down).astype(np.float32)
    else:
        resampled_mono = mono.astype(np.float32)

    # Convert mono to center-panned stereo (N, 2)
    return np.column_stack((resampled_mono, resampled_mono))


def synthesize_layer1_narration(
    total_dur_sec: float = DEFAULT_EP01_DURATION_SEC,
    beats: Optional[List[NarrationBeat]] = None,
    tts_cache_dir: Optional[Path] = None,
    sample_rate: int = SAMPLE_RATE,
) -> np.ndarray:
    """
    Synthesize Layer 1: Russian Studio Narration strictly locked to voice_y0joebp3bwta.
    Loads cached studio WAV files or synthesizes through Gemini 3.8 Studio TTS client.
    Returns (n_samples, 2) float32 array normalized to speech loudness.
    """
    active_beats = beats or EP01_NARRATION_BEATS
    cache_dir = tts_cache_dir or (Path(__file__).resolve().parent.parent / ".tts_cache")
    buffer = create_empty_stereo(total_dur_sec, sample_rate)
    total_samples = buffer.shape[0]

    for b in active_beats:
        cached_named = cache_dir / f"ep01_beat_{b.beat_id:02d}.wav"
        if not cached_named.is_file():
            # Check v3 hash cache key
            cache_key = hashlib.sha256(f"v3|ru|{VOICE_PERSONA_RU}|{b.transcript_ru}".encode("utf-8")).hexdigest()[:24]
            cached_hash = cache_dir / f"{cache_key}.wav"
            if cached_hash.is_file():
                cached_named = cached_hash

        if cached_named.is_file():
            speech_stereo = resample_wav_to_stereo_48k(cached_named, target_sr=sample_rate)
        else:
            # Fallback: synthesize inline via runner
            import flow_testbench_runner as runner
            out_tmp = cache_dir / f"ep01_beat_{b.beat_id:02d}.wav"
            res = asyncio.run(
                runner.try_gemini_studio_tts(
                    narration_text=b.transcript_ru,
                    out_wav=out_tmp,
                    lang="ru",
                    scene_number=b.beat_id,
                    voice_persona=VOICE_PERSONA_RU,
                    strict_timbre_lock=True,
                )
            )
            if not res:
                raise RuntimeError(f"Failed to synthesize narration for Beat {b.beat_id}")
            speech_stereo = resample_wav_to_stereo_48k(res[0], target_sr=sample_rate)

        start_idx = int(round(b.t_start * sample_rate))
        clip_len = speech_stereo.shape[0]
        end_idx = min(total_samples, start_idx + clip_len)
        insert_len = end_idx - start_idx
        if insert_len > 0:
            buffer[start_idx:end_idx, :] += speech_stereo[:insert_len, :]

    return np.clip(buffer, -1.0, 1.0)


def procedural_metallic_impact(
    duration_sec: float = 1.2,
    base_freq: float = 840.0,
    sample_rate: int = SAMPLE_RATE,
    ring_decay: float = 0.8,
) -> np.ndarray:
    """Synthesize metallic shield parry impact with multi-harmonic bell modal decay."""
    n_samples = int(duration_sec * sample_rate)
    t = np.linspace(0.0, duration_sec, n_samples, endpoint=False, dtype=np.float32)

    # Sharp strike transient (high-passed noise burst)
    strike_len = int(0.04 * sample_rate)
    noise = np.random.uniform(-1.0, 1.0, strike_len).astype(np.float32)
    noise_env = np.exp(-t[:strike_len] / 0.008)
    b_hp, a_hp = signal.butter(2, 2500.0 / (sample_rate / 2.0), btype="highpass")
    strike = signal.lfilter(b_hp, a_hp, noise * noise_env) * 0.8

    # Resonant metal bell modal harmonics
    modal_ratios = [1.0, 1.52, 2.38, 3.14, 4.22]
    modal_gains = [0.45, 0.35, 0.25, 0.18, 0.12]
    ring = np.zeros(n_samples, dtype=np.float32)
    for ratio, gain in zip(modal_ratios, modal_gains):
        freq = base_freq * ratio
        ring += gain * np.sin(2.0 * np.pi * freq * t) * np.exp(-t / (ring_decay / ratio))

    combined = ring
    combined[:strike_len] += strike
    # Stereo enhancement with 0.8ms Haas delay
    haas_samples = int(0.0008 * sample_rate)
    left = combined
    right = np.pad(combined[:-haas_samples], (haas_samples, 0)) if haas_samples > 0 else combined
    return np.column_stack((left, right))


def procedural_blade_slash(
    duration_sec: float = 0.35,
    sample_rate: int = SAMPLE_RATE,
) -> np.ndarray:
    """Synthesize dynamic blade swing whoosh with sweeping bandpass noise."""
    n_samples = int(duration_sec * sample_rate)
    t = np.linspace(0.0, duration_sec, n_samples, endpoint=False, dtype=np.float32)
    noise = np.random.uniform(-1.0, 1.0, n_samples).astype(np.float32)
    # Swept resonant filter from 600 Hz -> 2600 Hz -> 800 Hz
    cf = 600.0 + 2000.0 * np.sin(np.pi * (t / duration_sec))
    b_bp, a_bp = signal.butter(2, [800.0 / (sample_rate / 2.0), 3200.0 / (sample_rate / 2.0)], btype="bandpass")
    whoosh = signal.lfilter(b_bp, a_bp, noise)
    env = np.sin(np.pi * (t / duration_sec)) ** 2
    stereo = np.column_stack((whoosh * env * 0.6, whoosh * env * 0.85))
    return stereo.astype(np.float32)


def procedural_mana_shockwave(
    duration_sec: float = 2.5,
    sample_rate: int = SAMPLE_RATE,
) -> np.ndarray:
    """Synthesize explosive mana burst with descending sub-bass sweep and expanding reverb."""
    n_samples = int(duration_sec * sample_rate)
    t = np.linspace(0.0, duration_sec, n_samples, endpoint=False, dtype=np.float32)
    # Exponential frequency drop: 95 Hz down to 32 Hz
    freq_sweep = 32.0 + 63.0 * np.exp(-t / 0.5)
    phase = 2.0 * np.pi * np.cumsum(freq_sweep) / sample_rate
    sub_bass = np.sin(phase) * np.exp(-t / 1.1)

    # High frequency mana fizzle
    noise = np.random.uniform(-1.0, 1.0, n_samples).astype(np.float32)
    b_hp, a_hp = signal.butter(2, 3500.0 / (sample_rate / 2.0), btype="highpass")
    fizzle = signal.lfilter(b_hp, a_hp, noise) * np.exp(-t / 0.7) * 0.35

    left = (sub_bass * 0.85 + fizzle * 0.4).astype(np.float32)
    right = (sub_bass * 0.85 + fizzle * 0.6).astype(np.float32)
    return np.column_stack((left, right))


def synthesize_layer2_combat_sfx(
    total_dur_sec: float = DEFAULT_EP01_DURATION_SEC,
    sample_rate: int = SAMPLE_RATE,
) -> np.ndarray:
    """Synthesize Layer 2: Combat sound effects (clashes, parries, slashes, mana burst)."""
    buffer = create_empty_stereo(total_dur_sec, sample_rate)

    # Beat 1: Initial monster arrival / distant clashes
    c1 = procedural_blade_slash(0.4, sample_rate) * 0.4
    safe_add_clip(buffer, c1, int(3.5 * sample_rate))

    # Beat 2: Heavy round shield parry & spark burst (t = 10.2s)
    parry1 = procedural_metallic_impact(1.6, base_freq=820.0, sample_rate=sample_rate, ring_decay=1.1) * 0.95
    safe_add_clip(buffer, parry1, int(10.2 * sample_rate))

    # Second parry / deflection (t = 13.8s)
    parry2 = procedural_metallic_impact(1.2, base_freq=1140.0, sample_rate=sample_rate, ring_decay=0.8) * 0.8
    safe_add_clip(buffer, parry2, int(13.8 * sample_rate))

    # Counter-slash broadsword swing (t = 16.5s)
    slash1 = procedural_blade_slash(0.38, sample_rate) * 0.85
    safe_add_clip(buffer, slash1, int(16.5 * sample_rate))

    # Beat 3: Decisive broadsword cleave piercing boss core (t = 20.0s)
    slash_heavy = procedural_blade_slash(0.5, sample_rate) * 1.0
    safe_add_clip(buffer, slash_heavy, int(20.0 * sample_rate))

    mana_burst = procedural_mana_shockwave(3.0, sample_rate) * 0.9
    safe_add_clip(buffer, mana_burst, int(20.25 * sample_rate))

    # Core shattering resonance (t = 22.0s)
    core_shatter = procedural_metallic_impact(2.0, base_freq=1680.0, sample_rate=sample_rate, ring_decay=1.4) * 0.65
    safe_add_clip(buffer, core_shatter, int(22.0 * sample_rate))

    return np.clip(buffer, -1.0, 1.0)


def synthesize_brass_chord(
    frequencies: List[float],
    duration_sec: float,
    sample_rate: int = SAMPLE_RATE,
    attack_sec: float = 0.08,
    release_sec: float = 0.35,
) -> np.ndarray:
    """Synthesize warm orchestral brass chord with rich harmonic overtones."""
    n_samples = int(duration_sec * sample_rate)
    t = np.linspace(0.0, duration_sec, n_samples, endpoint=False, dtype=np.float32)
    chord = np.zeros(n_samples, dtype=np.float32)

    # Brass envelope: smooth attack and natural decay
    env = np.ones(n_samples, dtype=np.float32)
    att_samples = max(1, int(attack_sec * sample_rate))
    rel_samples = max(1, int(release_sec * sample_rate))
    env[:att_samples] = np.sin(np.linspace(0, np.pi / 2, att_samples)) ** 2
    env[-rel_samples:] = np.cos(np.linspace(0, np.pi / 2, rel_samples)) ** 2

    # Slight vibrato at 5.2 Hz
    vibrato = 1.0 + 0.006 * np.sin(2.0 * np.pi * 5.2 * t)

    harmonic_weights = [1.0, 0.65, 0.45, 0.28, 0.18, 0.10, 0.05]
    for f in frequencies:
        for h_idx, weight in enumerate(harmonic_weights, start=1):
            chord += (weight / math.sqrt(len(frequencies))) * np.sin(
                2.0 * np.pi * (f * h_idx) * t * vibrato
            )

    # Warm lowpass formant filter at 1800 Hz
    b_lp, a_lp = signal.butter(2, 1800.0 / (sample_rate / 2.0), btype="lowpass")
    filtered = signal.lfilter(b_lp, a_lp, chord * env) * 0.3
    return np.column_stack((filtered, filtered)).astype(np.float32)


def synthesize_crystalline_chime(
    freq: float,
    duration_sec: float = 1.8,
    sample_rate: int = SAMPLE_RATE,
    pan: float = 0.0,  # -1.0 left, +1.0 right
) -> np.ndarray:
    """Synthesize sparkling glockenspiel crystalline chime with bell overtones."""
    n_samples = int(duration_sec * sample_rate)
    t = np.linspace(0.0, duration_sec, n_samples, endpoint=False, dtype=np.float32)

    # Chime modal ratios
    partials = [1.0, 2.76, 5.40, 8.93]
    gains = [0.65, 0.28, 0.12, 0.05]
    chime = np.zeros(n_samples, dtype=np.float32)
    for p, g in zip(partials, gains):
        chime += g * np.sin(2.0 * np.pi * (freq * p) * t) * np.exp(-t / (0.8 / math.sqrt(p)))

    # Stereo panning
    left_gain = math.cos((pan + 1.0) * math.pi / 4.0)
    right_gain = math.sin((pan + 1.0) * math.pi / 4.0)
    return np.column_stack((chime * left_gain, chime * right_gain)).astype(np.float32)


def synthesize_layer3_victory_fanfare(
    total_dur_sec: float = DEFAULT_EP01_DURATION_SEC,
    sample_rate: int = SAMPLE_RATE,
) -> np.ndarray:
    """Synthesize Layer 3: Major brass triad chords & sparkling crystalline glockenspiel arpeggio."""
    buffer = create_empty_stereo(total_dur_sec, sample_rate)

    # Major brass triads during victory fanfare sequence (t ~ 20.0s - 29.8s)
    # Chord 1: D Major (D3, F#3, A3, D4)
    chord1 = synthesize_brass_chord([146.83, 185.00, 220.00, 293.66], 2.4, sample_rate) * 0.8
    safe_add_clip(buffer, chord1, int(20.5 * sample_rate))

    # Chord 2: G Major (G3, B3, D4, G4)
    chord2 = synthesize_brass_chord([196.00, 246.94, 293.66, 392.00], 2.2, sample_rate) * 0.85
    safe_add_clip(buffer, chord2, int(22.8 * sample_rate))

    # Chord 3: A Major (A3, C#4, E4, A4)
    chord3 = synthesize_brass_chord([220.00, 277.18, 329.63, 440.00], 1.8, sample_rate) * 0.88
    safe_add_clip(buffer, chord3, int(24.8 * sample_rate))

    # Chord 4: Triumphant D Major resolution (D3, A3, D4, F#4, A4)
    chord4 = synthesize_brass_chord([146.83, 220.00, 293.66, 369.99, 440.00], 3.2, sample_rate, release_sec=0.8) * 0.95
    safe_add_clip(buffer, chord4, int(26.5 * sample_rate))

    # Sparkling crystalline chime arpeggios (D5, F#5, A5, D6, F#6, A6)
    arpeggio_pitches = [587.33, 739.99, 880.00, 1174.66, 1479.98, 1760.00]
    arp_start = 21.0
    for idx, pitch in enumerate(arpeggio_pitches):
        t_note = int((arp_start + idx * 0.22) * sample_rate)
        pan = -0.7 + (1.4 * idx / (len(arpeggio_pitches) - 1))
        chime = synthesize_crystalline_chime(pitch, duration_sec=1.6, sample_rate=sample_rate, pan=pan) * 0.6
        safe_add_clip(buffer, chime, t_note)

    # Second descending glockenspiel run at resolution (t = 27.2s)
    arp2_start = 27.2
    for idx, pitch in enumerate(reversed(arpeggio_pitches)):
        t_note = int((arp2_start + idx * 0.18) * sample_rate)
        pan = 0.7 - (1.4 * idx / (len(arpeggio_pitches) - 1))
        chime = synthesize_crystalline_chime(pitch, duration_sec=1.4, sample_rate=sample_rate, pan=pan) * 0.55
        safe_add_clip(buffer, chime, t_note)

    return np.clip(buffer, -1.0, 1.0)


def synthesize_mechanical_click(sample_rate: int = SAMPLE_RATE) -> np.ndarray:
    """Synthesize Cherry MX Blue style mechanical tactile keyboard click with bottom-out thud."""
    dur_sec = 0.028
    n_samples = int(dur_sec * sample_rate)
    t = np.linspace(0.0, dur_sec, n_samples, endpoint=False, dtype=np.float32)

    # Switch click (high-pitched resonant click at 3.4 kHz)
    switch_len = int(0.008 * sample_rate)
    click_noise = np.random.uniform(-1.0, 1.0, switch_len).astype(np.float32)
    b_click, a_click = signal.butter(2, [2800.0 / (sample_rate / 2.0), 4500.0 / (sample_rate / 2.0)], btype="bandpass")
    switch_click = signal.lfilter(b_click, a_click, click_noise) * np.exp(-t[:switch_len] / 0.002)

    # Bottom-out plastic thud at 480 Hz
    thud_start = int(0.006 * sample_rate)
    thud_len = n_samples - thud_start
    t_thud = t[:thud_len]
    thud = np.sin(2.0 * np.pi * 480.0 * t_thud) * np.exp(-t_thud / 0.006) * 0.7

    out = np.zeros(n_samples, dtype=np.float32)
    out[:switch_len] += switch_click * 0.9
    out[thud_start:] += thud * 0.6
    pan_rnd = np.random.uniform(-0.35, 0.35)
    lg = math.cos((pan_rnd + 1.0) * math.pi / 4.0)
    rg = math.sin((pan_rnd + 1.0) * math.pi / 4.0)
    return np.column_stack((out * lg, out * rg)).astype(np.float32)


def synthesize_mouse_click(sample_rate: int = SAMPLE_RATE) -> np.ndarray:
    """Synthesize crisp Omron mouse switch micro-click."""
    dur_sec = 0.012
    n_samples = int(dur_sec * sample_rate)
    t = np.linspace(0.0, dur_sec, n_samples, endpoint=False, dtype=np.float32)
    click = np.sin(2.0 * np.pi * 4200.0 * t) * np.exp(-t / 0.0018) * 0.8
    return np.column_stack((click, click)).astype(np.float32)


def synthesize_foxy_donation_chime(sample_rate: int = SAMPLE_RATE) -> np.ndarray:
    """Synthesize bright luxury golden donation chime cascade (C6 -> E6 -> G6 -> C7)."""
    dur_sec = 4.2
    n_samples = int(dur_sec * sample_rate)
    buffer = np.zeros((n_samples, 2), dtype=np.float32)

    notes = [
        (0.00, 1046.50, -0.4),  # C6
        (0.12, 1318.51, -0.1),  # E6
        (0.24, 1567.98, 0.2),   # G6
        (0.38, 2093.00, 0.5),   # C7
    ]
    for t_offset, freq, pan in notes:
        chime = synthesize_crystalline_chime(freq, duration_sec=3.6, sample_rate=sample_rate, pan=pan) * 0.95
        idx = int(t_offset * sample_rate)
        rem = min(n_samples - idx, chime.shape[0])
        if rem > 0:
            buffer[idx : idx + rem, :] += chime[:rem, :]

    return buffer


def synthesize_layer4_stream_ambiance(
    total_dur_sec: float = DEFAULT_EP01_DURATION_SEC,
    sample_rate: int = SAMPLE_RATE,
) -> np.ndarray:
    """Synthesize Layer 4: Stream room ambiance (mechanical typing, mouse clicks, luxury donation chime)."""
    buffer = create_empty_stereo(total_dur_sec, sample_rate)
    n_total = buffer.shape[0]
    np.random.seed(42)

    # Frantic gameplay typing during Beat 1 & 2 (combat hotkeys Q, W, E, R, Space, 1, 2)
    typing_intervals = [
        (1.2, 5.0, 14),   # Boss positioning inputs
        (9.5, 12.0, 18),  # Frantic shield brace spam
        (14.0, 17.0, 16), # Counter-attack preparation
        (19.2, 21.0, 20), # Final strike cleave spam clicking
        (30.0, 39.0, 24), # Post-clear relaxed chat typing
        (43.0, 48.0, 10), # Stats inspection typing
    ]
    for start_t, end_t, count in typing_intervals:
        click_times = np.sort(np.random.uniform(start_t, end_t, count))
        for ct in click_times:
            click = synthesize_mechanical_click(sample_rate) * 0.45
            idx = int(ct * sample_rate)
            if idx + click.shape[0] <= n_total:
                buffer[idx : idx + click.shape[0], :] += click

    # Mouse clicks
    mouse_times = [
        0.8, 2.1, 3.4, 4.2, 10.1, 10.4, 13.7, 19.8, 19.9, 20.1,
        29.9, 31.2, 33.5, 35.8, 41.2, 44.5, 52.0
    ]
    for mt in mouse_times:
        mclick = synthesize_mouse_click(sample_rate) * 0.5
        idx = int(mt * sample_rate)
        if idx + mclick.shape[0] <= n_total:
            buffer[idx : idx + mclick.shape[0], :] += mclick

    # Luxury golden donation chime at t = 30.0s ("FOXY 300,000 KRW")
    donation_chime = synthesize_foxy_donation_chime(sample_rate) * 0.95
    t_dc = int(30.0 * sample_rate)
    if t_dc + donation_chime.shape[0] <= n_total:
        buffer[t_dc : t_dc + donation_chime.shape[0], :] += donation_chime

    return np.clip(buffer, -1.0, 1.0)


def synthesize_war_drum(sample_rate: int = SAMPLE_RATE) -> np.ndarray:
    """Synthesize 48 Hz deep fortress war drum hit with exponential sub-bass decay."""
    dur_sec = 1.2
    n_samples = int(dur_sec * sample_rate)
    t = np.linspace(0.0, dur_sec, n_samples, endpoint=False, dtype=np.float32)
    # Pitch drop 85 Hz -> 45 Hz
    f_inst = 45.0 + 40.0 * np.exp(-t / 0.08)
    phase = 2.0 * np.pi * np.cumsum(f_inst) / sample_rate
    drum = np.sin(phase) * np.exp(-t / 0.35)
    return np.column_stack((drum, drum)).astype(np.float32)


def synthesize_thunder_roll(duration_sec: float = 3.5, sample_rate: int = SAMPLE_RATE) -> np.ndarray:
    """Synthesize low rumble thunderstorm roll inside gothic fortress."""
    n_samples = int(duration_sec * sample_rate)
    t = np.linspace(0.0, duration_sec, n_samples, endpoint=False, dtype=np.float32)
    noise = np.random.uniform(-1.0, 1.0, n_samples).astype(np.float32)
    b_lp, a_lp = signal.butter(2, 120.0 / (sample_rate / 2.0), btype="lowpass")
    rumble = signal.lfilter(b_lp, a_lp, noise)
    env = (np.sin(np.pi * (t / duration_sec)) ** 1.5) * (1.0 + 0.3 * np.sin(2.0 * np.pi * 3.0 * t))
    return np.column_stack((rumble * env * 0.7, rumble * env * 0.75)).astype(np.float32)


def synthesize_layer5_environmental_ambience(
    total_dur_sec: float = DEFAULT_EP01_DURATION_SEC,
    sample_rate: int = SAMPLE_RATE,
) -> np.ndarray:
    """
    Synthesize Layer 5: Dark cello fifths, 40-60 Hz war drums, fortress storm,
    and 42 Hz void drone with shimmer fading to pure silence at t >= 59.84s.
    """
    buffer = create_empty_stereo(total_dur_sec, sample_rate)
    n_total = buffer.shape[0]
    t_full = np.linspace(0.0, total_dur_sec, n_total, endpoint=False, dtype=np.float32)

    # Low dark cello fifths (C2=65.41 Hz, G2=98.00 Hz) during combat tension (t = 0.0 - 19.88s)
    t_combat = np.clip(t_full[: int(20.0 * sample_rate)], 0.0, 20.0)
    cello_c2 = np.sin(2.0 * np.pi * 65.41 * t_combat) + 0.35 * np.sin(2.0 * np.pi * 130.82 * t_combat)
    cello_g2 = np.sin(2.0 * np.pi * 98.00 * t_combat) + 0.30 * np.sin(2.0 * np.pi * 196.00 * t_combat)
    cello_drone = (cello_c2 + cello_g2) * 0.22
    buffer[: len(cello_drone), 0] += cello_drone
    buffer[: len(cello_drone), 1] += cello_drone

    # War drum hits during combat (heartbeat cadence: t = 1.0, 2.8, 4.6, 6.4, 10.0, 11.8, 13.6, 15.4, 17.2)
    drum_times = [1.0, 2.8, 4.6, 6.4, 10.0, 11.8, 13.6, 15.4, 17.2]
    for dt in drum_times:
        drum = synthesize_war_drum(sample_rate) * 0.65
        idx = int(dt * sample_rate)
        if idx + drum.shape[0] <= n_total:
            buffer[idx : idx + drum.shape[0], :] += drum

    # Fortress thunderstorm rumble
    thunder1 = synthesize_thunder_roll(4.0, sample_rate) * 0.5
    t_th1 = int(2.5 * sample_rate)
    if t_th1 + thunder1.shape[0] <= n_total:
        buffer[t_th1 : t_th1 + thunder1.shape[0], :] += thunder1

    thunder2 = synthesize_thunder_roll(4.5, sample_rate) * 0.6
    t_th2 = int(12.0 * sample_rate)
    if t_th2 + thunder2.shape[0] <= n_total:
        buffer[t_th2 : t_th2 + thunder2.shape[0], :] += thunder2

    # Mournful cello fifths returning in aftermath (D2=73.42 Hz, A2=110.00 Hz, t = 49.80 - 59.84s)
    idx_aft_0 = int(49.80 * sample_rate)
    idx_aft_1 = int(59.84 * sample_rate)
    if idx_aft_0 < n_total:
        idx_aft_1 = min(n_total, idx_aft_1)
        t_aft = np.linspace(0.0, (idx_aft_1 - idx_aft_0) / sample_rate, idx_aft_1 - idx_aft_0, endpoint=False)
        aft_cello = (np.sin(2.0 * np.pi * 73.42 * t_aft) + 0.3 * np.sin(2.0 * np.pi * 110.00 * t_aft)) * 0.25
        buffer[idx_aft_0:idx_aft_1, 0] += aft_cello
        buffer[idx_aft_0:idx_aft_1, 1] += aft_cello

    # Terminal Void Sequence (t >= 59.84s):
    # Sub-bass 42 Hz pitch-black void drone with high-frequency shimmer fading to pure silence at t >= 67.5s
    idx_void_0 = int(59.84 * sample_rate)
    idx_void_silence = int(67.50 * sample_rate)
    if idx_void_0 < n_total:
        idx_void_silence = min(n_total, idx_void_silence)
        n_void = idx_void_silence - idx_void_0
        if n_void > 0:
            t_void = np.linspace(0.0, n_void / sample_rate, n_void, endpoint=False, dtype=np.float32)
            drone_42 = np.sin(2.0 * np.pi * 42.0 * t_void) + 0.25 * np.sin(2.0 * np.pi * 84.0 * t_void)
            shimmer = (
                np.sin(2.0 * np.pi * 6200.0 * t_void) * 0.5
                + np.sin(2.0 * np.pi * 6215.0 * t_void) * 0.5
            ) * 0.12
            fade_env = 0.5 * (1.0 + np.cos(np.pi * (t_void / t_void[-1])))
            void_audio = (drone_42 * 0.55 + shimmer) * fade_env
            buffer[idx_void_0:idx_void_silence, 0] += void_audio
            buffer[idx_void_0:idx_void_silence, 1] += void_audio

    # Strictly 0.0 pure silence for t >= 67.5s (absolute black void)
    if idx_void_silence < n_total:
        buffer[idx_void_silence:, :] = 0.0

    return np.clip(buffer, -1.0, 1.0)


def export_wav_stereo(audio_stereo: np.ndarray, out_wav_path: Path, sample_rate: int = SAMPLE_RATE) -> Path:
    """Export float32 stereo array as standard 16-bit PCM stereo RIFF WAV."""
    out_wav_path.parent.mkdir(parents=True, exist_ok=True)
    clipped = np.clip(audio_stereo, -1.0, 1.0)
    pcm16 = (clipped * 32767.0).astype(np.int16)
    with wave.open(str(out_wav_path), "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm16.tobytes())
    return out_wav_path


class CinematicAudioEngine:
    """
    High-fidelity 5-layer procedural cinematic audio engine for Episode 1.
    Renders and mixes:
    - Layer 1: Studio Russian Narration (voice_y0joebp3bwta)
    - Layer 2: Combat SFX (shield parries, blade clashes, spark crackle, mana burst)
    - Layer 3: Victory Fanfare (major brass triads + crystalline glockenspiel)
    - Layer 4: Stream Ambiance (Cherry MX typing, mouse clicks, luxury donation chime)
    - Layer 5: Environmental Ambience (dark cello, war drums, fortress storm, 42 Hz void drone)
    """

    def __init__(
        self,
        total_dur_sec: float = DEFAULT_EP01_DURATION_SEC,
        sample_rate: int = SAMPLE_RATE,
        tts_cache_dir: Optional[Path] = None,
    ) -> None:
        self.total_dur_sec = total_dur_sec
        self.sample_rate = sample_rate
        self.tts_cache_dir = tts_cache_dir or (Path(__file__).resolve().parent.parent / ".tts_cache")

    def render_layer_1(self) -> np.ndarray:
        return synthesize_layer1_narration(self.total_dur_sec, tts_cache_dir=self.tts_cache_dir, sample_rate=self.sample_rate)

    def render_layer_2(self) -> np.ndarray:
        return synthesize_layer2_combat_sfx(self.total_dur_sec, sample_rate=self.sample_rate)

    def render_layer_3(self) -> np.ndarray:
        return synthesize_layer3_victory_fanfare(self.total_dur_sec, sample_rate=self.sample_rate)

    def render_layer_4(self) -> np.ndarray:
        return synthesize_layer4_stream_ambiance(self.total_dur_sec, sample_rate=self.sample_rate)

    def render_layer_5(self) -> np.ndarray:
        return synthesize_layer5_environmental_ambience(self.total_dur_sec, sample_rate=self.sample_rate)

    def render_all_layers(self) -> Dict[str, np.ndarray]:
        return {
            "layer1_narration": self.render_layer_1(),
            "layer2_combat_sfx": self.render_layer_2(),
            "layer3_victory_fanfare": self.render_layer_3(),
            "layer4_stream_ambiance": self.render_layer_4(),
            "layer5_environmental_ambience": self.render_layer_5(),
        }

    def mix_layers(
        self,
        layers: Dict[str, np.ndarray],
        speech_gain: float = 1.0,
        sfx_gain: float = 0.82,
        fanfare_gain: float = 0.75,
        stream_gain: float = 0.55,
        ambience_gain: float = 0.65,
    ) -> np.ndarray:
        """Mix all 5 stereo layers with broadcast-balanced relative levels."""
        n_samples = int(round(self.total_dur_sec * self.sample_rate))
        master = np.zeros((n_samples, 2), dtype=np.float32)

        master += layers["layer1_narration"] * speech_gain
        master += layers["layer2_combat_sfx"] * sfx_gain
        master += layers["layer3_victory_fanfare"] * fanfare_gain
        master += layers["layer4_stream_ambiance"] * stream_gain
        master += layers["layer5_environmental_ambience"] * ambience_gain

        # Soft broadcast peak limiting to prevent digital clipping
        peak = float(np.max(np.abs(master)))
        if peak > 0.95:
            master = master * (0.95 / peak)

        return np.clip(master, -1.0, 1.0)
