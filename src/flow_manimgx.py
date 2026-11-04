"""
src/flow_manimgx.py
ManimGX Vector/LaTeX/Typst Animation Engine, Auto-Layout Healer, Contact-Sheet Critic,
and 48 kHz Audio Ducking + SFX Mixer for Google Flow Educational Video Studio L4.

Provides:
1. `GeminiStudioVoice`: Custom `manimgx.Voice` (`Callable[[str], m.Speech]`) adapter enforcing
   the locked female narrator persona (`voice_y0joebp3bwta` / `Sulafat`), `.tts_cache` lookup,
   Russian DSP phonetic formatting, and word-level `[span]` timing.
2. `inspect_manimgx_scene` & `heal_scene_mobjects_in_place`: Headless 2D layout inspection
   (`manimgx.cli.diagnostics`) with iterative Auto-Layout Healer that fixes `cut`, `overlap`,
   `crossing`, `covered`, and `small` defects until `clean == True`.
3. `build_contact_sheet`: FFmpeg (`select`/`fps` + `scale` + `tile`) contact-sheet generator
   and blank/black frame critic.
4. `mix_studio_audio_with_ducking_and_sfx`: 48 kHz audio mixer combining `GeminiStudioVoice`
   narration with procedural ambient pad (`-12 dB` auto-ducking during active speech) and
   point SFX accents (`whoosh` on transitions, `ding`/`pop` on `[span]` formula markers).
5. `render_manimgx_scene_to_mp4`: Hybrid Zero-Disk FFmpeg + Cubic Bezier `VMobject` renderer
   with gradient fills/strokes, dashed paths, and soft glow/bloom.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
import hashlib
import io
import math
import os
from pathlib import Path
import re
import subprocess
import tempfile
import wave
from typing import Any, Dict, List, Optional, Tuple, Type, Union

import imageio_ffmpeg
import manimgx as m
from manimgx.audio.sound import RATE, Speech, Word
from manimgx.cli import diagnostics as mgx_diag
from manimgx.config import config as mgx_config
from manimgx.drawing.geometry import partial_bezier_points, subpath_ranges
import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from flow_audio_video import FemaleVoiceoverOptimizer

_WORD_RE = re.compile(r"\S+")

# Cubic Bezier evaluation basis for 9 samples per curve (t in [0, 1])
_T_SAMPLES = np.linspace(0.0, 1.0, 9, dtype=np.float64)[:, None]
_MT_SAMPLES = 1.0 - _T_SAMPLES
_BEZIER_BASIS = np.hstack(
    [
        _MT_SAMPLES**3,
        3.0 * (_MT_SAMPLES**2) * _T_SAMPLES,
        3.0 * _MT_SAMPLES * (_T_SAMPLES**2),
        _T_SAMPLES**3,
    ]
)

# Default Russian DSP phonetic stress and expansion rules (pure ASCII unicode escapes)
_DEFAULT_RU_PHONETICS: Tuple[Tuple[str, str], ...] = (
    ("STM32H743", "\u042d\u0441-\u0422\u044d-\u042d\u043c \u0442\u0440\u0438\u0434\u0446\u0430\u0442\u044c \u0434\u0432\u0430 \u042d\u0439\u0447 \u0441\u0435\u043c\u044c\u0441\u043e\u0442 \u0441\u043e\u0440\u043e\u043a \u0442\u0440\u0438"),
    ("IS61LV6416", "\u0410\u0439-\u042d\u0441 \u0448\u0435\u0441\u0442\u044c\u0434\u0435\u0441\u044f\u0442 \u043e\u0434\u0438\u043d \u042d\u043b-\u0412\u0438 \u0448\u0435\u0441\u0442\u044c\u0434\u0435\u0441\u044f\u0442 \u0447\u0435\u0442\u044b\u0440\u0435 \u0448\u0435\u0441\u0442\u043d\u0430\u0434\u0446\u0430\u0442\u044c"),
    ("IIR", "\u0411\u0418\u0425"),
    ("FIR", "\u041a\u0418\u0425"),
    ("FMC", "\u042d\u0444-\u042d\u043c-\u0421\u0438"),
    ("SRAM", "\u042d\u0441-\u0420\u0410\u041c"),
    ("DMA", "\u041f\u0414\u041f"),
)


def apply_default_ru_phonetics(text: str) -> str:
    """Apply baseline Russian DSP abbreviation expansion for TTS pronunciation."""
    out = text
    for src, dst in _DEFAULT_RU_PHONETICS:
        out = out.replace(src, dst)
    return out


def _captions_to_webvtt(captions: List[Any]) -> str:
    """Convert ManimGX `Caption` items into a WebVTT subtitle track."""

    def _stamp(seconds: float) -> str:
        ms = max(0, round(seconds * 1000))
        hh = ms // 3_600_000
        mm = (ms // 60_000) % 60
        ss = (ms // 1000) % 60
        rem = ms % 1000
        return f"{hh:02d}:{mm:02d}:{ss:02d}.{rem:03d}"

    lines = ["WEBVTT", ""]
    for idx, cap in enumerate(captions, 1):
        lines.append(str(idx))
        lines.append(f"{_stamp(float(cap.start))} --> {_stamp(float(cap.end))}")
        lines.append(str(cap.text))
        lines.append("")
    return "\n".join(lines)


@dataclass
class GeminiStudioVoice:
    """
    ManimGX `Voice` adapter (`Callable[[str], m.Speech]`) with locked female narrator persona.
    Bridges `FemaleVoiceoverOptimizer`, `.tts_cache` WAV lookup, custom TTS callbacks, and
    deterministic 48 kHz female-formant harmonic synthesis into `m.Scene.say()`.
    """

    language: str = "en"
    voice_persona: str = "Sulafat"
    voice_gender: str = "female"
    voice_profile: str = "veo-3.1-female-narrator-v2"
    speaking_rate_wpm: float = 135.0
    cache_dir: Optional[Path] = field(default=None, repr=False)
    tts_provider: Optional[Callable[[str, str], Union[bytes, np.ndarray]]] = field(
        default=None, repr=False
    )
    phonetic_formatter: Optional[Callable[[str], str]] = field(
        default=None, repr=False
    )

    def __post_init__(self) -> None:
        if (self.voice_gender or "").strip().lower() != "female":
            raise ValueError(
                f"GeminiStudioVoice requires voice_gender='female', got {self.voice_gender!r}"
            )
        if self.language.lower().startswith("ru"):
            if self.voice_persona == "Sulafat":
                self.voice_persona = "voice_y0joebp3bwta"
            if self.phonetic_formatter is None:
                self.phonetic_formatter = apply_default_ru_phonetics

    def _compute_word_timings(self, clean_text: str) -> Tuple[Tuple[Word, ...], float]:
        """Compute deterministic word-level `[start, end]` timestamps in seconds."""
        tokens = _WORD_RE.findall(clean_text)
        if not tokens:
            return (), 0.5

        sec_per_word = 60.0 / max(60.0, float(self.speaking_rate_wpm))
        cursor = 0.08
        words: List[Word] = []
        for tok in tokens:
            alpha_len = max(1, sum(ch.isalnum() for ch in tok))
            dur = max(0.16, sec_per_word * (0.55 + 0.09 * min(alpha_len, 12)))
            pause = (
                0.22
                if tok[-1] in ".!?:;"
                else (0.12 if tok[-1] == "," else 0.04)
            )
            start_t = round(cursor, 4)
            end_t = round(cursor + dur, 4)
            words.append(Word(tok, start_t, end_t))
            cursor = end_t + pause

        total_duration = max(0.5, round(cursor + 0.10, 4))
        return tuple(words), total_duration

    def _synthesize_female_formant_samples(
        self, words: Tuple[Word, ...], total_duration: float
    ) -> np.ndarray:
        """
        Synthesize a warm 48 kHz mono float32 waveform with female fundamental pitch
        (`F0 = 215 Hz`) and syllabic envelopes aligned to `words` for `m.Speech`.
        """
        total_samples = max(int(RATE * 0.5), round(total_duration * RATE))
        samples = np.zeros((total_samples, 1), dtype=np.float32)
        if not words:
            return samples

        f0 = 215.0  # Female fundamental frequency (Hz)
        for idx, w in enumerate(words):
            i0 = max(0, min(total_samples, round(w.start * RATE)))
            i1 = max(i0, min(total_samples, round(w.end * RATE)))
            n = i1 - i0
            if n <= 16:
                continue
            t = np.arange(n, dtype=np.float32) / float(RATE)
            pitch_mod = 1.0 + 0.04 * math.sin(0.7 * idx)
            freq = f0 * pitch_mod
            # Female vocal formant harmonics (F1 ~ 645 Hz, F2 ~ 1720 Hz)
            carrier = (
                0.58 * np.sin(2.0 * np.pi * freq * t)
                + 0.26 * np.sin(2.0 * np.pi * (3.0 * freq) * t)
                + 0.12 * np.sin(2.0 * np.pi * (5.0 * freq) * t)
                + 0.04 * np.sin(2.0 * np.pi * (8.0 * freq) * t)
            )
            env = np.ones(n, dtype=np.float32)
            fade = min(n // 4, int(0.025 * RATE))
            if fade > 1:
                ramp = np.linspace(0.0, 1.0, fade, dtype=np.float32)
                env[:fade] = ramp
                env[-fade:] = ramp[::-1]
            samples[i0:i1, 0] = (0.28 * carrier * env).astype(np.float32)

        return samples

    def __call__(self, text: str) -> Speech:
        clean_text = (text or "").strip()
        if not clean_text:
            raise ValueError("Speech script text must not be empty")
        if (self.voice_gender or "").strip().lower() != "female":
            raise ValueError("Female narrator persona is required")

        optimizer = FemaleVoiceoverOptimizer()
        _ = optimizer.optimize_script(clean_text, voice_gender="female")

        spoken_query = (
            self.phonetic_formatter(clean_text)
            if self.phonetic_formatter is not None
            else clean_text
        )
        words, total_duration = self._compute_word_timings(clean_text)

        if self.cache_dir is not None:
            digest_hex = hashlib.sha256(
                f"{self.voice_persona}:{spoken_query}".encode("utf-8")
            ).hexdigest()[:16]
            candidate = Path(self.cache_dir) / f"tts_{digest_hex}.wav"
            if candidate.is_file():
                return Speech(candidate, text=clean_text, words=words)

        if self.tts_provider is not None:
            provided = self.tts_provider(spoken_query, self.voice_persona)
            if isinstance(provided, np.ndarray):
                arr = provided.astype(np.float32)
                if arr.ndim == 1:
                    arr = arr[:, None]
                return Speech(arr, text=clean_text, words=words, rate=RATE)
            if isinstance(provided, bytes) and len(provided) > 44:
                return Speech(provided, text=clean_text, words=words)

        samples = self._synthesize_female_formant_samples(words, total_duration)
        return Speech(samples, text=clean_text, words=words, rate=RATE)


# ============================================================================
# M7: 48 kHz Audio Mixer with -12 dB Auto-Ducking and Point SFX Accents
# ============================================================================


def synthesize_ambient_bed_48k(
    duration_sec: float,
    rate: int = RATE,
    base_gain: float = 0.14,
) -> np.ndarray:
    """Synthesize a warm 48 kHz harmonic ambient pad (A2-E3-A3-C#4 drone with slow LFO)."""
    n_samples = max(1, int(round(max(0.1, float(duration_sec)) * rate)))
    t = np.arange(n_samples, dtype=np.float32) / float(rate)
    lfo = 0.85 + 0.15 * np.sin(2.0 * np.pi * 0.25 * t)
    chord = (
        0.45 * np.sin(2.0 * np.pi * 110.0 * t)
        + 0.28 * np.sin(2.0 * np.pi * 164.81 * t)
        + 0.18 * np.sin(2.0 * np.pi * 220.0 * t)
        + 0.09 * np.sin(2.0 * np.pi * 277.18 * t)
    )
    bed = (float(base_gain) * chord * lfo).astype(np.float32)
    fade = min(n_samples // 6, int(0.08 * rate))
    if fade > 1:
        ramp = np.linspace(0.0, 1.0, fade, dtype=np.float32)
        bed[:fade] *= ramp
        bed[-fade:] *= ramp[::-1]
    return bed[:, None]


def synthesize_sfx_whoosh_48k(
    duration_sec: float = 0.34,
    rate: int = RATE,
    gain: float = 0.22,
) -> np.ndarray:
    """Synthesize a frequency-swept aerodynamic transition `whoosh` at 48 kHz."""
    n = max(16, int(round(max(0.08, float(duration_sec)) * rate)))
    t = np.arange(n, dtype=np.float32) / float(rate)
    norm_t = np.linspace(0.0, 1.0, n, dtype=np.float32)
    # Parabolic frequency trajectory 160 Hz -> 780 Hz -> 200 Hz
    inst_freq = 160.0 + 620.0 * np.sin(np.pi * norm_t)
    phase = 2.0 * np.pi * np.cumsum(inst_freq) / float(rate)
    # Deterministic harmonic shimmer simulating filtered air movement
    air = (
        0.55 * np.sin(phase)
        + 0.28 * np.sin(1.73 * phase + 0.4)
        + 0.17 * np.sin(2.89 * phase + 1.1)
    )
    env = np.maximum(0.0, np.sin(np.pi * norm_t)) ** 1.6
    wave_arr = (float(gain) * air * env).astype(np.float32)
    return wave_arr[:, None]


def synthesize_sfx_ding_48k(
    duration_sec: float = 0.28,
    rate: int = RATE,
    kind: str = "ding",
    gain: float = 0.24,
) -> np.ndarray:
    """Synthesize a crystalline `ding` or soft resonant `pop` accent for `[span]` markers."""
    n = max(16, int(round(max(0.06, float(duration_sec)) * rate)))
    t = np.arange(n, dtype=np.float32) / float(rate)
    if kind.lower() == "pop":
        # Pitch-drop membrane pop (460 Hz -> 165 Hz)
        freq = 165.0 + 295.0 * np.exp(-28.0 * t)
        phase = 2.0 * np.pi * np.cumsum(freq) / float(rate)
        env = np.exp(-16.0 * t)
        sig = np.sin(phase) * env
    else:
        # Crystalline bell ding (C6 = 1046.5 Hz + C7 = 2093 Hz + G7 = 3136 Hz)
        env = np.exp(-11.5 * t)
        sig = (
            0.65 * np.sin(2.0 * np.pi * 1046.5 * t)
            + 0.25 * np.sin(2.0 * np.pi * 2093.0 * t) * np.exp(-18.0 * t)
            + 0.10 * np.sin(2.0 * np.pi * 3136.0 * t) * np.exp(-26.0 * t)
        ) * env
    attack = min(n // 8, int(0.004 * rate))
    if attack > 1:
        sig[:attack] *= np.linspace(0.0, 1.0, attack, dtype=np.float32)
    return (float(gain) * sig).astype(np.float32)[:, None]


def compute_speech_ducking_envelope(
    narration_samples: np.ndarray,
    duck_db: float = -12.0,
    rate: int = RATE,
    threshold: float = 0.008,
) -> Tuple[np.ndarray, np.ndarray]:
    """Compute smooth `-12 dB` auto-ducking gain envelope and active-speech mask."""
    mono = (
        np.abs(narration_samples[:, 0])
        if narration_samples.ndim == 2
        else np.abs(narration_samples)
    ).astype(np.float32)
    n = len(mono)
    if n == 0:
        return np.ones(0, dtype=np.float32), np.zeros(0, dtype=bool)

    win = max(1, int(0.020 * rate))
    kernel = np.ones(win, dtype=np.float32) / float(win)
    local_amp = np.convolve(mono, kernel, mode="same")
    speech_mask = local_amp > float(threshold)

    # Hold dilation (80 ms) so brief inter-syllable micro-gaps stay smoothly ducked
    hold = max(1, int(0.080 * rate))
    if np.any(speech_mask) and hold > 1:
        dilated = np.convolve(
            speech_mask.astype(np.float32), np.ones(hold, dtype=np.float32), mode="same"
        ) > 0.5
    else:
        dilated = speech_mask

    duck_gain = float(10.0 ** (float(duck_db) / 20.0))
    raw_gain = np.where(dilated, duck_gain, 1.0).astype(np.float32)

    smooth_win = max(1, int(0.055 * rate))
    if smooth_win > 1 and n > smooth_win:
        s_kernel = np.ones(smooth_win, dtype=np.float32) / float(smooth_win)
        padded = np.pad(raw_gain, (smooth_win // 2, smooth_win - 1 - smooth_win // 2), mode="edge")
        envelope = np.convolve(padded, s_kernel, mode="valid").astype(np.float32)
    else:
        envelope = raw_gain

    return envelope[:n], dilated[:n]


def mix_studio_audio_with_ducking_and_sfx(
    narration_samples: Optional[np.ndarray],
    *,
    duration_sec: Optional[float] = None,
    span_timestamps: Optional[Sequence[float]] = None,
    transition_timestamps: Optional[Sequence[float]] = None,
    duck_db: float = -12.0,
    ambient_gain: float = 0.14,
    sfx_gain: float = 0.22,
    rate: int = RATE,
) -> Dict[str, Any]:
    """
    Mix 48 kHz `GeminiStudioVoice` narration with a procedural ambient bed (auto-ducked by
    `duck_db` = `-12 dB` during active speech) and point SFX (`whoosh` on transitions,
    `ding`/`pop` on `[span]` formula markers).
    """
    if narration_samples is not None and len(narration_samples) > 0:
        narr = narration_samples.astype(np.float32)
        if narr.ndim == 1:
            narr = narr[:, None]
        n_samples = len(narr)
        if duration_sec is not None:
            target_n = max(n_samples, int(round(float(duration_sec) * rate)))
            if target_n > n_samples:
                pad = np.zeros((target_n - n_samples, narr.shape[1]), dtype=np.float32)
                narr = np.vstack([narr, pad])
                n_samples = target_n
    else:
        dur = max(0.5, float(duration_sec or 2.0))
        n_samples = int(round(dur * rate))
        narr = np.zeros((n_samples, 1), dtype=np.float32)

    channels = narr.shape[1]
    total_dur = n_samples / float(rate)

    ambient_mono = synthesize_ambient_bed_48k(total_dur, rate=rate, base_gain=ambient_gain)
    if len(ambient_mono) < n_samples:
        ambient_mono = np.vstack(
            [ambient_mono, np.zeros((n_samples - len(ambient_mono), 1), dtype=np.float32)]
        )
    else:
        ambient_mono = ambient_mono[:n_samples]

    env_gain, speech_mask = compute_speech_ducking_envelope(
        narr, duck_db=duck_db, rate=rate
    )
    ducked_ambient_mono = ambient_mono[:, 0] * env_gain
    ducked_ambient = np.repeat(ducked_ambient_mono[:, None], channels, axis=1)

    sfx_track = np.zeros((n_samples, channels), dtype=np.float32)
    sfx_events: List[Dict[str, Any]] = []

    def _overlay_clip(clip_mono: np.ndarray, t_sec: float, kind_label: str) -> None:
        idx0 = max(0, min(n_samples - 1, int(round(float(t_sec) * rate))))
        idx1 = min(n_samples, idx0 + len(clip_mono))
        seg_len = idx1 - idx0
        if seg_len > 0:
            sfx_track[idx0:idx1, :] += clip_mono[:seg_len]
            sfx_events.append({"kind": kind_label, "timestamp_sec": round(float(t_sec), 4)})

    for t_tr in transition_timestamps or ():
        whoosh_clip = synthesize_sfx_whoosh_48k(rate=rate, gain=sfx_gain)
        _overlay_clip(whoosh_clip, float(t_tr), "whoosh")

    for s_idx, t_sp in enumerate(span_timestamps or ()):
        accent_kind = "ding" if (s_idx % 2 == 0) else "pop"
        accent_clip = synthesize_sfx_ding_48k(rate=rate, kind=accent_kind, gain=sfx_gain)
        _overlay_clip(accent_clip, float(t_sp), accent_kind)

    mixed = np.clip(narr + ducked_ambient + sfx_track, -0.99, 0.99).astype(np.float32)

    duck_linear = float(10.0 ** (float(duck_db) / 20.0))
    speech_count = int(np.sum(speech_mask))
    silence_count = int(n_samples - speech_count)
    speech_ratio = round(float(speech_count) / max(1, n_samples), 4)

    rms_speech = (
        float(np.sqrt(np.mean(ducked_ambient_mono[speech_mask] ** 2)))
        if speech_count > 0
        else float(np.sqrt(np.mean((ambient_mono[:, 0] * duck_linear) ** 2)))
    )
    rms_silence = (
        float(np.sqrt(np.mean(ducked_ambient_mono[~speech_mask] ** 2)))
        if silence_count > 0
        else float(np.sqrt(np.mean(ambient_mono[:, 0] ** 2)))
    )
    measured_db = (
        20.0 * math.log10(max(1e-9, rms_speech) / max(1e-9, rms_silence))
        if rms_silence > 1e-9
        else float(duck_db)
    )

    return {
        "mixed_samples": mixed,
        "sample_rate": int(rate),
        "duration_sec": round(total_dur, 4),
        "duck_db": float(duck_db),
        "duck_linear_gain": round(duck_linear, 6),
        "measured_duck_db": round(measured_db, 2),
        "active_speech_ratio": speech_ratio,
        "ambient_rms_during_speech": round(rms_speech, 6),
        "ambient_rms_during_silence": round(rms_silence, 6),
        "sfx_events": sfx_events,
        "span_sfx_count": sum(1 for e in sfx_events if e["kind"] in ("ding", "pop")),
        "transition_sfx_count": sum(1 for e in sfx_events if e["kind"] == "whoosh"),
    }


# ============================================================================
# M6: Auto-Layout Healer & FFmpeg Contact Sheet Critic
# ============================================================================


def _mobject_bounds_2d(mob: m.Mobject) -> Optional[Tuple[float, float, float, float]]:
    """Compute `(x0, y0, x1, y1)` bounding box of a mobject across all visible points."""
    leaves = [sub for sub in mob.family_members_with_points() if len(sub.points) > 0]
    if not leaves:
        return None
    pts = np.concatenate([sub.points[:, :2] for sub in leaves], axis=0)
    if len(pts) == 0:
        return None
    (x0, y0), (x1, y1) = pts.min(axis=0), pts.max(axis=0)
    return (float(x0), float(y0), float(x1), float(y1))


def _collect_text_and_shape_roots(
    scene: m.Scene,
) -> Tuple[List[m.Mobject], List[m.Mobject]]:
    """Partition scene mobjects into text mobjects and non-grid geometric shape mobjects."""
    texts: List[m.Mobject] = []
    shapes: List[m.Mobject] = []
    seen_ids = set()

    def _walk(mob: m.Mobject) -> None:
        if id(mob) in seen_ids:
            return
        seen_ids.add(id(mob))
        if type(mob).__name__ in mgx_diag.GRIDS or isinstance(mob, m.BackgroundRectangle):
            return
        if isinstance(mob, mgx_diag.TEXTS):
            if _mobject_bounds_2d(mob) is not None:
                texts.append(mob)
            return
        # If this is a VGroup/Group containing texts, recurse into children
        has_text_child = any(isinstance(sub, mgx_diag.TEXTS) for sub in mob.submobjects)
        if has_text_child:
            for sub in mob.submobjects:
                _walk(sub)
            return
        if _mobject_bounds_2d(mob) is not None:
            shapes.append(mob)

    for root in list(scene.mobjects) + list(scene.foreground_mobjects):
        _walk(root)
    return texts, shapes


def heal_scene_mobjects_in_place(
    scene: m.Scene,
    *,
    max_passes: int = 6,
) -> Dict[str, Any]:
    """
    Iteratively inspect `scene` with `manimgx.cli.diagnostics` and apply corrective scaling
    and shifting to resolve `small`, `cut`, `overlap`, `crossing`, and `covered` defects
    until `clean == True` (`len(remaining_problems) == 0`).
    """
    actions: List[Dict[str, Any]] = []
    passes_run = 0

    for pass_idx in range(1, max_passes + 1):
        seen_view = mgx_diag.view(scene)
        if seen_view is None:
            break
        cur_problems = [p for p in mgx_diag.at(seen_view) if not p.note]
        if not cur_problems:
            break

        passes_run = pass_idx
        f0, g0, f1, g1 = seen_view.frame
        fw = max(1.0, f1 - f0)
        fh = max(1.0, g1 - g0)
        px_per_unit = 1080.0 / fh
        margin = 0.22

        texts, shapes = _collect_text_and_shape_roots(scene)
        problem_kinds = {p.kind for p in cur_problems}

        # 1. Heal `small`: ensure every text is at least 24 px tall at 1080p
        min_text_h = 24.0 / px_per_unit
        for t_mob in texts:
            box = _mobject_bounds_2d(t_mob)
            if box is None:
                continue
            cur_h = box[3] - box[1]
            if 1e-5 < cur_h < (20.8 / px_per_unit):
                scale_up = min_text_h / cur_h
                t_mob.scale(scale_up)
                actions.append(
                    {
                        "pass": pass_idx,
                        "kind": "small",
                        "action": "scale_up",
                        "factor": round(scale_up, 3),
                    }
                )

        # 2. Heal `cut` on texts and shapes: scale down oversized items and clamp into frame
        for mob_list, is_text in ((texts, True), (shapes, False)):
            for mob in mob_list:
                box = _mobject_bounds_2d(mob)
                if box is None:
                    continue
                bw = box[2] - box[0]
                bh = box[3] - box[1]
                max_w = fw - 2.0 * margin
                max_h = (fh * 0.42) if not is_text else (fh - 2.0 * margin)
                if bw > max_w or bh > max_h:
                    s_fit = min(max_w / max(1e-4, bw), max_h / max(1e-4, bh), 0.90)
                    if is_text:
                        s_fit = max(s_fit, (21.5 / px_per_unit) / max(1e-4, bh))
                    mob.scale(s_fit)
                    actions.append(
                        {
                            "pass": pass_idx,
                            "kind": "cut",
                            "action": "scale_to_fit",
                            "factor": round(s_fit, 3),
                        }
                    )
                    box = _mobject_bounds_2d(mob)
                    if box is None:
                        continue

                dx = 0.0
                if box[0] < f0 + margin:
                    dx = (f0 + margin) - box[0]
                elif box[2] > f1 - margin:
                    dx = (f1 - margin) - box[2]
                dy = 0.0
                if box[1] < g0 + margin:
                    dy = (g0 + margin) - box[1]
                elif box[3] > g1 - margin:
                    dy = (g1 - margin) - box[3]
                if abs(dx) > 1e-3 or abs(dy) > 1e-3:
                    mob.shift(np.array([dx, dy, 0.0]))
                    actions.append(
                        {
                            "pass": pass_idx,
                            "kind": "cut",
                            "action": "shift_inside_frame",
                            "dx": round(dx, 3),
                            "dy": round(dy, 3),
                        }
                    )

        # 3. Heal `crossing`, `covered`, and `overlap`:
        # Separate shapes into lower/right non-colliding zones and stack texts in clean rows
        if problem_kinds & {"overlap", "crossing", "covered"} or pass_idx >= 2:
            # Place shapes in the lower zone [g0 + margin, 0.05] if texts are present
            if shapes and texts:
                shape_top_limit = 0.05
                shape_bottom_limit = g0 + margin
                avail_shape_h = max(0.8, shape_top_limit - shape_bottom_limit)
                for s_idx, s_mob in enumerate(shapes):
                    s_box = _mobject_bounds_2d(s_mob)
                    if s_box is None:
                        continue
                    sh = s_box[3] - s_box[1]
                    sw = s_box[2] - s_box[0]
                    if sh > avail_shape_h * 0.85 or sw > (fw - 2 * margin) * 0.85:
                        sf = min(
                            (avail_shape_h * 0.82) / max(1e-4, sh),
                            ((fw - 2 * margin) * 0.82) / max(1e-4, sw),
                        )
                        s_mob.scale(sf)
                        s_box = _mobject_bounds_2d(s_mob)
                        if s_box is None:
                            continue
                    target_cy = 0.5 * (shape_top_limit + shape_bottom_limit)
                    cur_cy = 0.5 * (s_box[1] + s_box[3])
                    cur_cx = 0.5 * (s_box[0] + s_box[2])
                    # Spread multiple shapes horizontally if needed
                    if len(shapes) > 1:
                        slot_w = (fw - 2 * margin) / len(shapes)
                        target_cx = f0 + margin + slot_w * (s_idx + 0.5)
                    else:
                        target_cx = 0.0
                    s_mob.shift(np.array([target_cx - cur_cx, target_cy - cur_cy, 0.0]))
                    actions.append(
                        {
                            "pass": pass_idx,
                            "kind": "crossing_or_covered",
                            "action": "relocate_shape_zone",
                        }
                    )

            # Stack texts from top (g1 - margin) downward with guaranteed non-overlapping gap
            if texts:
                cursor_top = g1 - margin
                gap = 0.16
                for t_mob in texts:
                    t_box = _mobject_bounds_2d(t_mob)
                    if t_box is None:
                        continue
                    tw = t_box[2] - t_box[0]
                    th = t_box[3] - t_box[1]
                    if tw > fw - 2 * margin:
                        t_mob.scale((fw - 2 * margin) / max(1e-4, tw))
                        t_box = _mobject_bounds_2d(t_mob)
                        if t_box is None:
                            continue
                        tw = t_box[2] - t_box[0]
                        th = t_box[3] - t_box[1]
                    target_top = cursor_top
                    target_cy = target_top - 0.5 * th
                    cur_cy = 0.5 * (t_box[1] + t_box[3])
                    cur_cx = 0.5 * (t_box[0] + t_box[2])
                    t_mob.shift(np.array([-cur_cx, target_cy - cur_cy, 0.0]))
                    cursor_top = target_top - th - gap
                    actions.append(
                        {
                            "pass": pass_idx,
                            "kind": "overlap",
                            "action": "stack_text_slot",
                            "target_cy": round(target_cy, 3),
                        }
                    )

    final_view = mgx_diag.view(scene)
    remaining = (
        [
            {
                "kind": p.kind,
                "subject": p.subject.name,
                "other": p.other.name if p.other else None,
                "detail": p.detail,
                "note": bool(p.note),
            }
            for p in mgx_diag.at(final_view)
            if not p.note
        ]
        if final_view is not None
        else []
    )
    return {
        "clean": len(remaining) == 0,
        "passes_run": passes_run,
        "actions": actions,
        "remaining_problems": remaining,
    }


def _instantiate_scene(
    scene_cls_or_fn: Union[Type[m.Scene], Callable[[m.Scene], None], m.Scene],
    voice: Optional[GeminiStudioVoice] = None,
) -> m.Scene:
    """Instantiate a `m.Scene` from a class, instance, or `construct(scene)` function."""
    if isinstance(scene_cls_or_fn, m.Scene):
        sc = scene_cls_or_fn
    elif isinstance(scene_cls_or_fn, type) and issubclass(scene_cls_or_fn, m.Scene):
        sc = scene_cls_or_fn()
    elif callable(scene_cls_or_fn):
        fn = scene_cls_or_fn

        class _DynamicFuncScene(m.Scene):
            def construct(self) -> None:
                fn(self)

        _DynamicFuncScene.__name__ = getattr(fn, "__name__", "DynamicManimGXScene")
        sc = _DynamicFuncScene()
    else:
        raise TypeError(
            f"Expected m.Scene subclass, instance, or construct callable, got {type(scene_cls_or_fn)!r}"
        )

    active_voice = (
        voice
        if voice is not None
        else (getattr(sc, "voice", None) or GeminiStudioVoice())
    )
    sc.voice = active_voice
    sc.speech = lambda text, v=None: (v or active_voice)(text)  # type: ignore[method-assign]
    return sc


def inspect_manimgx_scene(
    scene_cls_or_fn: Union[Type[m.Scene], Callable[[m.Scene], None], m.Scene],
    *,
    width: int = 1280,
    height: int = 720,
    fps: int = 30,
    voice: Optional[GeminiStudioVoice] = None,
    auto_heal: bool = False,
    max_heal_passes: int = 6,
) -> Dict[str, Any]:
    """
    Execute a ManimGX scene headlessly (without starting the GPU) and run
    `manimgx.cli.diagnostics` 2D layout verification (`cut`, `overlap`, `crossing`,
    `covered`, `small`).

    When layout defects are detected, the Auto-Layout Healer automatically computes
    corrective scale/shift transforms and re-runs inspection iteratively until
    `clean == True` (`len(remaining_problems) == 0`).
    If `auto_heal=True` is passed, `ok` and `problems` reflect the post-heal state;
    otherwise `ok` and `problems` report the initial raw defects while `clean`,
    `healed`, `heal_actions`, and `remaining_problems` report the healed state.
    """
    old_w, old_h, old_fps = (
        mgx_config.pixel_width,
        mgx_config.pixel_height,
        mgx_config.frame_rate,
    )
    mgx_config.pixel_width = int(width)
    mgx_config.pixel_height = int(height)
    mgx_config.frame_rate = int(fps)
    try:
        sc = _instantiate_scene(scene_cls_or_fn, voice=voice)
        layout = mgx_diag.Layout()
        checked = 0
        play_records: List[Dict[str, Any]] = []

        def _on_play(play: Any, animations: Tuple[Any, ...]) -> None:
            nonlocal checked
            seen_view = mgx_diag.view(sc)
            if seen_view is not None:
                layout.see((play.end, play.where), seen_view)
                checked += 1
            play_records.append(
                {
                    "index": int(play.index),
                    "start_sec": round(float(play.start), 4),
                    "end_sec": round(float(play.end), 4),
                    "animation_count": len(animations),
                }
            )

        film = sc.render(plays=_on_play)

        if checked == 0:
            seen_view = mgx_diag.view(sc)
            if seen_view is not None:
                layout.see((film.frame_count / film.fps, None), seen_view)
                checked += 1

        report_text = mgx_diag.report(layout, checked)

        initial_problems: List[Dict[str, Any]] = [
            {
                "kind": p.kind,
                "subject": p.subject.name,
                "other": p.other.name if p.other else None,
                "detail": p.detail,
                "note": bool(p.note),
            }
            for p in layout.found.values()
            if not p.note
        ]

        # Run Auto-Layout Healer whenever any layout defect is found
        if len(initial_problems) > 0:
            heal_res = heal_scene_mobjects_in_place(sc, max_passes=max_heal_passes)
            clean = bool(heal_res["clean"])
            healed = clean
            heal_passes = int(heal_res["passes_run"])
            heal_actions = list(heal_res["actions"])
            remaining_problems = list(heal_res["remaining_problems"])
        else:
            clean = True
            healed = False
            heal_passes = 0
            heal_actions = []
            remaining_problems = []

        reported_problems = remaining_problems if auto_heal else initial_problems
        reported_ok = (len(remaining_problems) == 0) if auto_heal else (len(initial_problems) == 0)

        captions = film.captions()
        srt_text = film.subtitles()
        vtt_text = _captions_to_webvtt(captions)
        duration_sec = round(float(film.frame_count / film.fps), 4)

        return {
            "ok": reported_ok,
            "clean": clean,
            "healed": healed,
            "heal_passes": heal_passes,
            "heal_actions": heal_actions,
            "initial_problems": initial_problems,
            "remaining_problems": remaining_problems,
            "scene_name": type(sc).__name__,
            "frame_count": int(film.frame_count),
            "fps": int(film.fps),
            "duration_sec": duration_sec,
            "play_count": len(film.plays),
            "plays": play_records,
            "problems": reported_problems,
            "report_text": report_text,
            "captions": [
                {
                    "start": round(float(c.start), 3),
                    "end": round(float(c.end), 3),
                    "text": c.text,
                }
                for c in captions
            ],
            "subtitles_srt": srt_text,
            "subtitles_vtt": vtt_text,
        }
    finally:
        mgx_config.pixel_width = old_w
        mgx_config.pixel_height = old_h
        mgx_config.frame_rate = old_fps


def _probe_video_duration_sec(mp4_path: Path, ffmpeg_exe: str) -> float:
    """Probe duration of `mp4_path` in seconds using FFmpeg stderr metadata."""
    proc = subprocess.run(
        [ffmpeg_exe, "-i", str(mp4_path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=20,
    )
    stderr_text = proc.stderr.decode("utf-8", errors="replace")
    m_dur = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", stderr_text)
    if not m_dur:
        return 2.0
    hh = int(m_dur.group(1))
    mm = int(m_dur.group(2))
    ss = float(m_dur.group(3))
    return max(0.1, hh * 3600.0 + mm * 60.0 + ss)


def build_contact_sheet(
    mp4_path: Union[str, Path],
    output_png: Union[str, Path],
    cols: int = 5,
    rows: int = 4,
    thumb_width: int = 320,
    thumb_height: int = 180,
) -> Dict[str, Any]:
    """
    Generate a `cols x rows` contact sheet PNG of keyframes from `mp4_path` via
    `imageio_ffmpeg` (`fps` + `scale` + `tile`) and verify the absence of blank/black frames.
    """
    in_path = Path(mp4_path).resolve()
    if not in_path.is_file():
        raise FileNotFoundError(f"Video file not found: {in_path}")

    out_path = Path(output_png).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    cols_i = max(1, int(cols))
    rows_i = max(1, int(rows))
    total_tiles = cols_i * rows_i
    tw = max(64, int(thumb_width))
    th = max(36, int(thumb_height))

    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    duration_sec = _probe_video_duration_sec(in_path, ffmpeg_exe)

    # Ensure at least `total_tiles + 2` frames are sampled across `duration_sec` so `tile`
    # fills all `cols * rows` cells with actual video frames rather than EOF padding.
    sample_fps = max(1.0, (float(total_tiles) + 3.0) / max(0.15, duration_sec))
    vf_chain = (
        f"fps={sample_fps:.4f},"
        f"scale={tw}:{th}:force_original_aspect_ratio=decrease,"
        f"pad={tw}:{th}:(ow-iw)/2:(oh-ih)/2,"
        f"tile={cols_i}x{rows_i}"
    )

    cmd = [
        ffmpeg_exe,
        "-y",
        "-i",
        str(in_path),
        "-vf",
        vf_chain,
        "-frames:v",
        "1",
        str(out_path),
    ]
    proc = subprocess.run(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        timeout=60,
    )
    if proc.returncode != 0 or not out_path.is_file():
        err_msg = proc.stderr.decode("utf-8", errors="replace")[-600:]
        raise RuntimeError(f"FFmpeg contact sheet generation failed: {err_msg}")

    sheet_img = Image.open(out_path).convert("RGB")
    arr = np.asarray(sheet_img, dtype=np.float32)
    img_h, img_w, _ = arr.shape

    cell_w = img_w // cols_i
    cell_h = img_h // rows_i

    tile_luma_means: List[float] = []
    tile_luma_stds: List[float] = []
    blank_indices: List[int] = []

    for r_idx in range(rows_i):
        for c_idx in range(cols_i):
            tile_idx = r_idx * cols_i + c_idx
            y0, y1 = r_idx * cell_h, (r_idx + 1) * cell_h
            x0, x1 = c_idx * cell_w, (c_idx + 1) * cell_w
            patch = arr[y0:y1, x0:x1, :]
            mean_val = float(patch.mean())
            std_val = float(patch.std())
            tile_luma_means.append(round(mean_val, 3))
            tile_luma_stds.append(round(std_val, 3))
            # A tile is black/blank if its mean luminance is near zero and has no variance
            if mean_val < 2.0 and std_val < 1.0:
                blank_indices.append(tile_idx)

    return {
        "ok": len(blank_indices) == 0,
        "video_path": str(in_path),
        "output_png": str(out_path),
        "cols": cols_i,
        "rows": rows_i,
        "tile_count": total_tiles,
        "width": int(img_w),
        "height": int(img_h),
        "duration_sec": round(duration_sec, 4),
        "black_frame_count": len(blank_indices),
        "blank_frame_indices": blank_indices,
        "tile_luma_means": tile_luma_means,
        "tile_luma_stds": tile_luma_stds,
        "vf_filter": vf_chain,
    }


# ============================================================================
# Vector Rasterizer (Gradients, Dashed Strokes, Rounded Caps, Glow/Bloom)
# ============================================================================


def _rgba_float_to_u8(rgba: np.ndarray) -> Tuple[int, int, int, int]:
    """Convert a float RGBA row in `[0, 1]` to a 0..255 4-tuple."""
    r = int(np.clip(round(float(rgba[0]) * 255.0), 0, 255))
    g = int(np.clip(round(float(rgba[1]) * 255.0), 0, 255))
    b = int(np.clip(round(float(rgba[2]) * 255.0), 0, 255))
    a = int(np.clip(round(float(rgba[3]) * 255.0), 0, 255))
    return (r, g, b, a)


def _trim_vmobject_points(pts: np.ndarray, lo: float, hi: float) -> np.ndarray:
    """Slice a `VMobject`'s cubic Bezier control points `(4*C, 3)` to curve window `[lo, hi]`."""
    n_curves = len(pts) // 4
    if n_curves <= 0 or hi <= lo + 1e-6:
        return np.empty((0, 3), dtype=np.float64)
    lo_c = max(0.0, min(float(n_curves), float(lo)))
    hi_c = max(lo_c, min(float(n_curves), float(hi)))
    if lo_c <= 1e-5 and hi_c >= n_curves - 1e-5:
        return pts[: n_curves * 4]

    first_idx = min(int(math.floor(lo_c)), n_curves - 1)
    last_idx = min(int(math.ceil(hi_c)) - 1, n_curves - 1)
    if last_idx < first_idx:
        return np.empty((0, 3), dtype=np.float64)

    curves = pts[: n_curves * 4].reshape(n_curves, 4, 3)
    if first_idx == last_idx:
        a = lo_c - first_idx
        b = hi_c - first_idx
        return partial_bezier_points(curves[first_idx], a, b)

    chunks: List[np.ndarray] = []
    a0 = lo_c - first_idx
    if a0 > 1e-5:
        chunks.append(partial_bezier_points(curves[first_idx], a0, 1.0))
    else:
        chunks.append(curves[first_idx])

    if last_idx > first_idx + 1:
        chunks.append(curves[first_idx + 1 : last_idx].reshape(-1, 3))

    b1 = hi_c - last_idx
    if b1 < 1.0 - 1e-5:
        chunks.append(partial_bezier_points(curves[last_idx], 0.0, b1))
    else:
        chunks.append(curves[last_idx])

    return np.vstack(chunks)


def _draw_dashed_polyline(
    draw: ImageDraw.ImageDraw,
    coords: List[Tuple[float, float]],
    color: Tuple[int, int, int, int],
    width: int,
    dash_spec: Tuple[float, ...],
    unit_px: float,
) -> None:
    """Render a polyline with `p.dash` on/off segment lengths in scene units."""
    if len(coords) < 2:
        return
    on_px = max(2.0, float(dash_spec[0]) * unit_px)
    off_px = max(2.0, float(dash_spec[1] if len(dash_spec) > 1 else dash_spec[0]) * unit_px)
    cycle = on_px + off_px
    dist_acc = 0.0
    for i in range(len(coords) - 1):
        x0, y0 = coords[i]
        x1, y1 = coords[i + 1]
        seg_len = math.hypot(x1 - x0, y1 - y0)
        if seg_len < 1e-4:
            continue
        pos = 0.0
        while pos < seg_len:
            phase = (dist_acc + pos) % cycle
            if phase < on_px:
                step = min(seg_len - pos, on_px - phase)
                t0 = pos / seg_len
                t1 = (pos + step) / seg_len
                p0 = (x0 + (x1 - x0) * t0, y0 + (y1 - y0) * t0)
                p1 = (x0 + (x1 - x0) * t1, y0 + (y1 - y0) * t1)
                draw.line([p0, p1], fill=color, width=width)
                pos += step
            else:
                step = min(seg_len - pos, cycle - phase)
                pos += step
        dist_acc += seg_len


def rasterize_manimgx_frame(
    camera: m.Camera,
    mobjects: List[m.Mobject],
    *,
    width: int = 1280,
    height: int = 720,
    supersample: int = 2,
) -> Image.Image:
    """
    Rasterize a ManimGX `display_list()` snapshot into an anti-aliased RGB `PIL.Image`.
    Supports `VMobject` cubic Bezier subpaths, even-odd glyph holes (`MathTex`, `Text`),
    reveal windows (`Create`, `Write`), dashed paths (`p.dash`), multi-stop gradient
    strokes/fills, and `ImageMobject` rasters.
    """
    ss = max(1, int(supersample))
    rw, rh = int(width) * ss, int(height) * ss

    bg_rgba = camera.background_color.to_rgba_with_alpha(camera.background_opacity)
    bg_u8 = _rgba_float_to_u8(bg_rgba)
    canvas = Image.new("RGBA", (rw, rh), bg_u8)
    draw = ImageDraw.Draw(canvas, "RGBA")

    fc = camera.frame_center
    fw = max(1e-6, float(camera.frame_width))
    fh = max(1e-6, float(camera.frame_height))
    cx, cy = float(fc[0]), float(fc[1])
    scale_x = rw / fw
    scale_y = rh / fh
    unit_px = 0.5 * (scale_x + scale_y)

    fixed_set = camera.fixed_in_frame_mobjects

    for mob in mobjects:
        p = mob.paint
        if isinstance(mob, m.ImageMobject) and isinstance(p.texture, np.ndarray):
            pts = mob.points
            if len(pts) >= 3:
                xs = (pts[:, 0] - cx) * scale_x + (rw * 0.5)
                ys = (cy - pts[:, 1]) * scale_y + (rh * 0.5)
                x0, x1 = int(round(float(xs.min()))), int(round(float(xs.max())))
                y0, y1 = int(round(float(ys.min()))), int(round(float(ys.max())))
                if x1 > x0 and y1 > y0:
                    tex_img = Image.fromarray(p.texture)
                    if tex_img.mode != "RGBA":
                        tex_img = tex_img.convert("RGBA")
                    tex_img = tex_img.resize(
                        (x1 - x0, y1 - y0), Image.Resampling.BILINEAR
                    )
                    canvas.alpha_composite(tex_img, (x0, y0))
            continue

        if not isinstance(mob, m.VMobject):
            continue

        raw_pts = mob.points
        n_curves = len(raw_pts) // 4
        if n_curves <= 0:
            continue

        lo, hi = p.window(n_curves)
        pts = _trim_vmobject_points(raw_pts, lo, hi)
        if len(pts) < 4:
            continue

        ranges = subpath_ranges(pts, 1e-5, dims=2)
        if not ranges:
            continue

        is_fixed = mob in fixed_set
        ref_x = 0.0 if is_fixed else cx
        ref_y = 0.0 if is_fixed else cy
        ref_w = float(mgx_config.frame_width) if is_fixed else fw
        ref_h = float(mgx_config.frame_height) if is_fixed else fh
        sx = rw / max(1e-6, ref_w)
        sy = rh / max(1e-6, ref_h)

        fill_row = p.fill.mean(axis=0) if len(p.fill) > 1 else (p.fill[0] if len(p.fill) else np.array([1.0, 1.0, 1.0, 0.0]))
        stroke_row = p.stroke[0] if len(p.stroke) else np.array([1.0, 1.0, 1.0, 1.0])
        bg_stroke_row = (
            p.background[0] if len(p.background) else np.array([0.0, 0.0, 0.0, 1.0])
        )

        fill_u8 = _rgba_float_to_u8(fill_row)
        stroke_u8 = _rgba_float_to_u8(stroke_row)
        bg_stroke_u8 = _rgba_float_to_u8(bg_stroke_row)

        stroke_px = (
            max(1, round(float(p.stroke_width) * 0.01 * unit_px))
            if p.stroke_width > 0.05 and stroke_u8[3] > 0
            else 0
        )
        bg_stroke_px = (
            max(1, round(float(p.background_width) * 0.01 * unit_px))
            if p.background_width > 0.05 and bg_stroke_u8[3] > 0
            else 0
        )

        polylines: List[Tuple[List[Tuple[float, float]], bool]] = []
        for s_idx, e_idx, closed in ranges:
            sub_curves = pts[s_idx:e_idx].reshape(-1, 4, 3)
            sampled = np.einsum("tk,ckd->ctd", _BEZIER_BASIS, sub_curves[:, :, :2])
            first_pt = sampled[0, :1, :]
            rest_pts = sampled[:, 1:, :].reshape(-1, 2)
            xy = np.vstack([first_pt, rest_pts])
            px = (xy[:, 0] - ref_x) * sx + (rw * 0.5)
            py = (ref_y - xy[:, 1]) * sy + (rh * 0.5)
            coords = list(zip(px.tolist(), py.tolist()))
            if len(coords) >= 2:
                polylines.append((coords, closed))

        if not polylines:
            continue

        # 1. Background stroke behind fill
        if bg_stroke_px > 0:
            for coords, _ in polylines:
                draw.line(coords, fill=bg_stroke_u8, width=bg_stroke_px, joint="curve")

        # 2. Fill (using even-odd XOR mask when a glyph has inner holes like '0', '8', 'O', '\theta')
        if fill_u8[3] > 0:
            closed_polys = [
                coords
                for coords, closed in polylines
                if len(coords) >= 3 and (closed or len(polylines) == 1)
            ]
            if len(closed_polys) == 1:
                draw.polygon(closed_polys[0], fill=fill_u8)
            elif len(closed_polys) >= 2:
                all_x = [pt[0] for poly in closed_polys for pt in poly]
                all_y = [pt[1] for poly in closed_polys for pt in poly]
                bx0 = max(0, int(math.floor(min(all_x))) - 2)
                by0 = max(0, int(math.floor(min(all_y))) - 2)
                bx1 = min(rw, int(math.ceil(max(all_x))) + 2)
                by1 = min(rh, int(math.ceil(max(all_y))) + 2)
                bw, bh = bx1 - bx0, by1 - by0
                if bw > 0 and bh > 0:
                    acc_mask = Image.new("1", (bw, bh), 0)
                    for poly in closed_polys:
                        shifted = [(x - bx0, y - by0) for x, y in poly]
                        sub_mask = Image.new("1", (bw, bh), 0)
                        ImageDraw.Draw(sub_mask).polygon(shifted, fill=1)
                        acc_mask = ImageChops.logical_xor(acc_mask, sub_mask)
                    alpha_mask = acc_mask.convert("L").point(
                        lambda v: fill_u8[3] if v else 0
                    )
                    patch = Image.new(
                        "RGBA", (bw, bh), (fill_u8[0], fill_u8[1], fill_u8[2], 255)
                    )
                    canvas.paste(patch, (bx0, by0), alpha_mask)
                    draw = ImageDraw.Draw(canvas, "RGBA")

        # 3. Foreground stroke (supporting p.dash and multi-color gradient strokes)
        if stroke_px > 0:
            dash_spec = getattr(p, "dash", ())
            if dash_spec:
                for coords, _ in polylines:
                    _draw_dashed_polyline(
                        draw, coords, stroke_u8, stroke_px, dash_spec, unit_px
                    )
            elif len(p.stroke) > 1:
                n_stops = len(p.stroke)
                for coords, _ in polylines:
                    n_seg = max(1, len(coords) - 1)
                    for seg_i in range(n_seg):
                        alpha = seg_i / max(1, n_seg - 1)
                        stop_pos = alpha * (n_stops - 1)
                        i0 = min(int(math.floor(stop_pos)), n_stops - 1)
                        i1 = min(i0 + 1, n_stops - 1)
                        frac = stop_pos - i0
                        c_row = (1.0 - frac) * p.stroke[i0] + frac * p.stroke[i1]
                        c_u8 = _rgba_float_to_u8(c_row)
                        draw.line(
                            [coords[seg_i], coords[seg_i + 1]],
                            fill=c_u8,
                            width=stroke_px,
                        )
            else:
                for coords, _ in polylines:
                    draw.line(coords, fill=stroke_u8, width=stroke_px, joint="curve")

    if ss > 1:
        canvas = canvas.resize((int(width), int(height)), Image.Resampling.BILINEAR)
    return canvas.convert("RGB")


def render_manimgx_scene_to_mp4(
    scene_cls_or_fn: Union[Type[m.Scene], Callable[[m.Scene], None], m.Scene],
    output_path: Optional[Union[str, Path]] = None,
    *,
    width: int = 1280,
    height: int = 720,
    fps: int = 30,
    supersample: int = 2,
    voice: Optional[GeminiStudioVoice] = None,
    inspect_layout: bool = True,
    enable_ducking_and_sfx: bool = True,
    duck_db: float = -12.0,
) -> Dict[str, Any]:
    """
    Render a ManimGX `Scene` (with `MathTex`, `Text`, `NumberPlane`, `Circle`, `Axes`,
    `Write`, `Create`, `Transform`, and `self.say()`) to an H.264 + 48 kHz AAC `.mp4`
    via Zero-Disk FFmpeg pipe, mix `-12 dB` auto-ducked ambient + `[span]` SFX accents,
    and run automated 2D layout diagnostics.
    """
    w = int(width) + (int(width) % 2)
    h = int(height) + (int(height) % 2)
    fps_int = max(1, int(fps))

    old_w, old_h, old_fps = (
        mgx_config.pixel_width,
        mgx_config.pixel_height,
        mgx_config.frame_rate,
    )
    mgx_config.pixel_width = w
    mgx_config.pixel_height = h
    mgx_config.frame_rate = fps_int

    try:
        sc = _instantiate_scene(scene_cls_or_fn, voice=voice)
        layout = mgx_diag.Layout()
        checked = 0
        span_timestamps: List[float] = []
        transition_timestamps: List[float] = [0.04]

        def _on_play(play: Any, animations: Tuple[Any, ...]) -> None:
            nonlocal checked
            if len(animations) > 0:
                span_timestamps.append(round(float(play.start) + 0.08, 4))
            if not inspect_layout:
                return
            seen_view = mgx_diag.view(sc)
            if seen_view is not None:
                layout.see((play.end, play.where), seen_view)
                checked += 1

        # Force frame-by-frame evaluation during plays while preserving single-frame holds during wait()
        sc._pure_tweens = lambda anim, alpha: None  # type: ignore[method-assign]

        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_root = Path(tmp_dir)
            video_only_mp4 = tmp_root / "video_stream.mp4"
            final_mp4 = (
                Path(output_path).resolve()
                if output_path is not None
                else (tmp_root / "manimgx_out.mp4")
            )
            final_mp4.parent.mkdir(parents=True, exist_ok=True)

            ffmpeg_cmd = [
                ffmpeg_exe,
                "-y",
                "-f",
                "rawvideo",
                "-vcodec",
                "rawvideo",
                "-s",
                f"{w}x{h}",
                "-pix_fmt",
                "rgb24",
                "-r",
                str(fps_int),
                "-i",
                "pipe:0",
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-preset",
                "ultrafast",
                "-crf",
                "20",
                "-movflags",
                "+faststart",
                str(video_only_mp4),
            ]
            proc = subprocess.Popen(
                ffmpeg_cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
            )

            orig_emit = sc._emit

            def _hooked_emit(repeat: int = 1) -> None:
                if repeat > 0:
                    img = rasterize_manimgx_frame(
                        sc.camera,
                        sc.display_list(),
                        width=w,
                        height=h,
                        supersample=supersample,
                    )
                    raw_bytes = img.tobytes()
                    if proc.stdin is not None:
                        for _ in range(repeat):
                            proc.stdin.write(raw_bytes)
                orig_emit(repeat)

            sc._emit = _hooked_emit  # type: ignore[method-assign]

            try:
                film = sc.render(plays=_on_play)
            finally:
                if proc.stdin is not None:
                    proc.stdin.close()
                _, stderr_bytes = proc.communicate(timeout=60)
                if proc.returncode != 0:
                    err_msg = stderr_bytes.decode("utf-8", errors="replace")[-600:]
                    raise RuntimeError(f"FFmpeg video pipe failed: {err_msg}")

            duration_sec = round(float(film.frame_count / film.fps), 4)
            raw_sound = film.soundtrack()
            audio_mix_telemetry: Optional[Dict[str, Any]] = None

            if enable_ducking_and_sfx or (raw_sound is not None and len(raw_sound) > 0):
                if enable_ducking_and_sfx:
                    mix_res = mix_studio_audio_with_ducking_and_sfx(
                        raw_sound,
                        duration_sec=max(0.5, duration_sec),
                        span_timestamps=span_timestamps,
                        transition_timestamps=transition_timestamps,
                        duck_db=duck_db,
                        rate=RATE,
                    )
                    sound = mix_res["mixed_samples"]
                    audio_mix_telemetry = {
                        k: v for k, v in mix_res.items() if k != "mixed_samples"
                    }
                else:
                    sound = raw_sound

                wav_path = tmp_root / "soundtrack.wav"
                with wave.open(str(wav_path), "wb") as wf:
                    wf.setnchannels(int(sound.shape[1]))
                    wf.setsampwidth(2)
                    wf.setframerate(RATE)
                    pcm16 = (
                        (np.clip(sound, -1.0, 1.0) * 32767.0)
                        .round()
                        .astype("<i2")
                        .tobytes()
                    )
                    wf.writeframes(pcm16)

                mux_cmd = [
                    ffmpeg_exe,
                    "-y",
                    "-i",
                    str(video_only_mp4),
                    "-i",
                    str(wav_path),
                    "-c:v",
                    "copy",
                    "-c:a",
                    "aac",
                    "-b:a",
                    "192k",
                    "-ar",
                    str(RATE),
                    "-shortest",
                    "-movflags",
                    "+faststart",
                    str(final_mp4),
                ]
                subprocess.run(
                    mux_cmd,
                    check=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE,
                    timeout=60,
                )
            else:
                sound = raw_sound
                final_mp4.write_bytes(video_only_mp4.read_bytes())

            mp4_bytes = final_mp4.read_bytes()

        report_text = mgx_diag.report(layout, checked) if inspect_layout else ""
        problems: List[Dict[str, Any]] = [
            {
                "kind": p.kind,
                "subject": p.subject.name,
                "other": p.other.name if p.other else None,
                "detail": p.detail,
                "note": bool(p.note),
            }
            for p in layout.found.values()
            if not p.note
        ]

        captions = film.captions()
        srt_text = film.subtitles()
        vtt_text = _captions_to_webvtt(captions)

        if output_path is not None:
            out_p = Path(output_path).resolve()
            if srt_text:
                out_p.with_suffix(".srt").write_text(srt_text, encoding="utf-8")
            if vtt_text:
                out_p.with_suffix(".vtt").write_text(vtt_text, encoding="utf-8")

        return {
            "ok": True,
            "scene_name": type(sc).__name__,
            "output_path": str(Path(output_path).resolve()) if output_path else None,
            "mp4_bytes": mp4_bytes,
            "video_size_bytes": len(mp4_bytes),
            "width": w,
            "height": h,
            "fps": fps_int,
            "frame_count": int(film.frame_count),
            "duration_sec": duration_sec,
            "play_count": len(film.plays),
            "has_audio": sound is not None and len(sound) > 0,
            "audio_mix": audio_mix_telemetry,
            "layout_ok": len(problems) == 0,
            "layout_problems": problems,
            "layout_report": report_text,
            "subtitles_srt": srt_text,
            "subtitles_vtt": vtt_text,
        }
    finally:
        mgx_config.pixel_width = old_w
        mgx_config.pixel_height = old_h
        mgx_config.frame_rate = old_fps


class StudioVoiceScene(m.Scene):
    """
    Base ManimGX `Scene` pre-wired with `GeminiStudioVoice` (female narrator persona)
    so `self.say()` works in-memory without requiring an external `FAL_KEY`.
    """

    voice: Optional[GeminiStudioVoice] = None

    def speech(self, text: str, voice: Optional[Any] = None) -> Speech:
        active = voice or self.__dict__.get("voice") or GeminiStudioVoice()
        return active(text)


class DspBiquadTransferScene(StudioVoiceScene):
    """
    Reference ManimGX educational scene: 2nd-Order IIR Biquad Transfer Function H(z)
    and Z-plane conjugate pole-zero stability geometry with word-synced female narration.
    """

    def construct(self) -> None:
        self.camera.background_color = m.ManimColor("#0B0F19")
        title = m.Text(
            "IIR Biquad Transfer Function & Z-Plane",
            font_size=34,
            color=m.ManimColor("#38BDF8"),
        ).to_edge(m.UP, buff=0.35)

        formula = m.MathTex(
            r"H(z) = \frac{b_0 + b_1 z^{-1} + b_2 z^{-2}}{1 + a_1 z^{-1} + a_2 z^{-2}}",
            font_size=48,
            color=m.WHITE,
        ).next_to(title, m.DOWN, buff=0.45)

        circle = m.Circle(
            radius=1.35, color=m.ManimColor("#22D3EE"), stroke_width=4
        ).shift(1.35 * m.DOWN)
        circle.paint = circle.paint.but(dash=(0.08, 0.6, 0.0))

        pole_a = m.Dot(
            circle.get_center() + np.array([0.65, 0.65, 0.0]),
            radius=0.10,
            color=m.ManimColor("#F43F5E"),
        )
        pole_b = m.Dot(
            circle.get_center() + np.array([0.65, -0.65, 0.0]),
            radius=0.10,
            color=m.ManimColor("#F43F5E"),
        )
        poles = m.VGroup(pole_a, pole_b)

        self.add(title)
        self.say(
            "The biquad filter computes [transfer function H of z] inside the [unit circle] with [conjugate poles].",
            m.Write(formula),
            m.Create(circle),
            m.FadeIn(poles),
        )
        self.wait(0.3)


def build_manimgx_educational_scene(
    topic: str,
    formula_latex: str = r"H(z) = \frac{Y(z)}{X(z)}",
    narration_script: str = "We analyze [the core equation] and observe [the geometric state].",
) -> Type[m.Scene]:
    """
    Dynamically build a layout-safe `m.Scene` class for any educational topic,
    LaTeX formula, and bracket-annotated narration script (`[span1]`, `[span2]`).
    """
    clean_topic = (topic or "Mathematical Model").strip()[:56]
    clean_formula = (formula_latex or r"e^{i\pi} + 1 = 0").strip()
    clean_script = (
        narration_script
        or "We derive [the mathematical expression] on [the phase plane]."
    ).strip()

    class CustomEducationalManimGXScene(StudioVoiceScene):
        def construct(self) -> None:
            self.camera.background_color = m.ManimColor("#0B0F19")
            header = m.Text(
                clean_topic,
                font_size=34,
                color=m.ManimColor("#38BDF8"),
            ).to_edge(m.UP, buff=0.4)

            eq = m.MathTex(clean_formula, font_size=52, color=m.WHITE).next_to(
                header, m.DOWN, buff=0.55
            )
            ring = m.Circle(
                radius=1.2, color=m.ManimColor("#A855F7"), stroke_width=4
            ).shift(1.4 * m.DOWN)

            self.add(header)
            _, found_spans = m.voices.spans(clean_script)
            anims: List[m.Animation] = [m.Write(eq), m.Create(ring)]
            if len(found_spans) == 1:
                anims = [m.Write(eq)]
                self.add(ring)
            elif len(found_spans) > 2:
                while len(anims) < len(found_spans):
                    anims.append(m.Indicate(eq))

            self.say(clean_script, *anims)
            self.wait(0.25)

    return CustomEducationalManimGXScene
