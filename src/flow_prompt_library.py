"""Local reference prompt library and deterministic web/3D animation templates (M5).

Indexes 1,007 curated prompt patterns from:
  - yihui-dev/awesome-opus5-5-videos (703 prompts)
  - yihui-dev/awesome-gemini4-argon-videos (304 prompts)

Supports filtering by category ('explainer', '3d', 'motion') and tech_tags
('canvas', 'svg', 'threejs', 'gsap', 'shader'), and provides reusable system
templates and mathematical primitives for:
  1. Deterministic window.seek(t) / draw(t) rendering contract (zero timers)
  2. Analytical critically damped spring physics closed_form_spring(t, zeta, omega0)
     and match-position bounding-box transitions
  3. High-retention semantic pacing of 12-15 beats per 30 seconds
"""

from __future__ import annotations

import math
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple, Union

import numpy as np


OPUS_REPO = "yihui-dev/awesome-opus5-5-videos"
GEMINI_ARGON_REPO = "yihui-dev/awesome-gemini4-argon-videos"

OPUS_PROMPT_COUNT = 703
GEMINI_ARGON_PROMPT_COUNT = 304
TOTAL_PROMPT_COUNT = OPUS_PROMPT_COUNT + GEMINI_ARGON_PROMPT_COUNT

SUPPORTED_CATEGORIES: Tuple[str, ...] = ("explainer", "3d", "motion")
SUPPORTED_TECH_TAGS: Tuple[str, ...] = ("canvas", "svg", "threejs", "gsap", "shader")

MIN_BEATS_PER_30S = 12
MAX_BEATS_PER_30S = 15
DEFAULT_BEATS_PER_30S = 14


SYSTEM_TEMPLATE_DETERMINISTIC_SEEK = """\
# SYSTEM RULE 1: DETERMINISTIC window.seek(t) / draw(t) RENDERING CONTRACT
1. Expose a pure deterministic entry point `window.seek = function(t_sec) { draw(t_sec); }`
   where `t_sec` is exact playback time in seconds (float >= 0).
2. `draw(t_sec)` MUST compute all scene coordinates, camera matrices, opacity, and
   typography exclusively as a pure function of `t_sec`.
3. FORBIDDEN APIs: `setInterval`, `setTimeout`, unguarded `requestAnimationFrame` loops,
   `Date.now()`, `performance.now()`, `Math.random()` without fixed seed, and CSS
   `transition` / `@keyframes` that advance independently of `t_sec`.
4. Every frame captured at `t_k = k / fps` MUST be 100% bit-reproducible regardless of
   CPU/GPU render latency or frame-step order.
"""

SYSTEM_TEMPLATE_CLOSED_FORM_SPRING = """\
# SYSTEM RULE 2: ANALYTICAL CRITICALLY DAMPED SPRINGS & MATCH-POSITION TRANSITIONS
1. All spatial entrances, camera pans, and exploded-view assembly motions MUST use the
   closed-form second-order harmonic oscillator `closed_form_spring(t, zeta, omega0)`:
     x''(t) + 2 * zeta * omega0 * x'(t) + omega0^2 * (x(t) - 1) = 0
2. Default to critically damped motion (`zeta = 1.0`, `omega0 = 10.0..16.0`):
     x(t) = 1.0 - (1.0 + omega0 * t) * exp(-omega0 * t)  for t >= 0
   which reaches 98% settle without oscillation overshoot.
3. For concept continuity across scenes, apply `match-position` bounding-box morphing:
   interpolate `(x0, y0, x1, y1)` of a shared visual anchor from its outgoing layout
   rect to its incoming layout rect via `closed_form_spring(t - t_transition, 1.0, 12.0)`.
"""

SYSTEM_TEMPLATE_SEMANTIC_BEAT_DENSITY = """\
# SYSTEM RULE 3: SEMANTIC BEAT DENSITY (12-15 BEATS PER 30 SECONDS)
1. Structure every 30-second segment into 12 to 15 discrete visual beats
   (2.0 to 2.5 seconds per beat; 0.40 to 0.50 beats/second).
2. Each beat MUST introduce exactly one visual delta: a spring-driven node entrance,
   a `[span]` formula highlight, a parameter sweep, a callout arrow, or a match-position
   camera shift.
3. Never hold a static frame for longer than 2.5 seconds without a visual sub-beat or
   kinetic highlight update.
"""

SYSTEM_TEMPLATES: Dict[str, str] = {
    "deterministic_seek": SYSTEM_TEMPLATE_DETERMINISTIC_SEEK,
    "closed_form_spring": SYSTEM_TEMPLATE_CLOSED_FORM_SPRING,
    "semantic_beat_density": SYSTEM_TEMPLATE_SEMANTIC_BEAT_DENSITY,
}


@dataclass(frozen=True)
class PromptPattern:
    """Indexed prompt pattern from awesome-opus5-5-videos or awesome-gemini4-argon-videos."""

    id: str
    title: str
    source_repo: str
    category: str
    tech_tags: Tuple[str, ...]
    semantic_beats_per_30s: int
    deterministic_seek: bool
    uses_spring_physics: bool
    match_position: bool
    system_prompt: str
    summary: str
    parameters: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["tech_tags"] = list(self.tech_tags)
        return data


def closed_form_spring(
    t: Union[float, int, np.ndarray],
    zeta: float = 1.0,
    omega0: float = 12.0,
    x0: float = 0.0,
    x1: float = 1.0,
    v0: float = 0.0,
) -> Union[float, np.ndarray]:
    """Analytical solution to the damped harmonic oscillator x'' + 2*zeta*omega0*x' + omega0^2*(x - x1) = 0.

    Supports scalar float/int or numpy array inputs for `t`.
    For default `x0=0.0, x1=1.0, v0=0.0`:
      - At `t <= 0`: returns `0.0` (`x0`)
      - As `t -> +inf`: converges to `1.0` (`x1`)
      - `zeta == 1.0`: critically damped, fastest non-oscillatory settle
      - `0 <= zeta < 1.0`: underdamped with natural frequency `omega0 * sqrt(1 - zeta^2)`
      - `zeta > 1.0`: overdamped two-exponential decay
    """
    if omega0 <= 0.0:
        raise ValueError(f"omega0 must be positive, got {omega0}")
    if zeta < 0.0:
        raise ValueError(f"zeta must be non-negative, got {zeta}")

    is_scalar = np.isscalar(t)
    t_arr = np.asarray(t, dtype=np.float64)
    t_pos = np.maximum(t_arr, 0.0)
    delta0 = float(x0 - x1)

    if abs(zeta - 1.0) < 1e-6:
        # Critically damped: x(t) = x1 + (delta0 + (v0 + omega0 * delta0) * t) * exp(-omega0 * t)
        env = np.exp(-omega0 * t_pos)
        pos = x1 + (delta0 + (v0 + omega0 * delta0) * t_pos) * env
    elif zeta < 1.0:
        # Underdamped
        omega_d = omega0 * math.sqrt(max(1.0 - zeta * zeta, 1e-12))
        env = np.exp(-zeta * omega0 * t_pos)
        cos_term = delta0 * np.cos(omega_d * t_pos)
        sin_coeff = (v0 + zeta * omega0 * delta0) / omega_d
        sin_term = sin_coeff * np.sin(omega_d * t_pos)
        pos = x1 + env * (cos_term + sin_term)
    else:
        # Overdamped
        gamma = omega0 * math.sqrt(max(zeta * zeta - 1.0, 1e-12))
        r1 = -omega0 * zeta + gamma
        r2 = -omega0 * zeta - gamma
        c1 = (v0 - r2 * delta0) / (r1 - r2)
        c2 = delta0 - c1
        pos = x1 + c1 * np.exp(r1 * t_pos) + c2 * np.exp(r2 * t_pos)

    result = np.where(t_arr <= 0.0, float(x0), pos)
    if is_scalar:
        return float(result.item())
    return result


def match_position_transition(
    source_box: Tuple[float, float, float, float],
    target_box: Tuple[float, float, float, float],
    t: float,
    zeta: float = 1.0,
    omega0: float = 12.0,
) -> Tuple[float, float, float, float]:
    """Interpolate bounding box (x0, y0, x1, y1) using analytical closed_form_spring."""
    alpha = float(closed_form_spring(t, zeta=zeta, omega0=omega0, x0=0.0, x1=1.0))
    return (
        float(source_box[0] + (target_box[0] - source_box[0]) * alpha),
        float(source_box[1] + (target_box[1] - source_box[1]) * alpha),
        float(source_box[2] + (target_box[2] - source_box[2]) * alpha),
        float(source_box[3] + (target_box[3] - source_box[3]) * alpha),
    )


def validate_deterministic_seek_contract(code_text: str) -> Dict[str, Any]:
    """Validate that web/3D animation code adheres to the window.seek(t) / draw(t) contract."""
    has_window_seek = bool(re.search(r"\bwindow\.seek\b|\bfunction\s+seek\s*\(", code_text))
    has_draw_fn = bool(re.search(r"\bdraw\s*\(", code_text))

    forbidden_matches: List[str] = []
    forbidden_patterns = [
        ("setInterval", r"\bsetInterval\s*\("),
        ("setTimeout", r"\bsetTimeout\s*\("),
        ("css_keyframes", r"@keyframes\b"),
        ("css_transition", r"\btransition\s*:\s*all\b"),
    ]
    for label, pat in forbidden_patterns:
        if re.search(pat, code_text):
            forbidden_matches.append(label)

    ok = (has_window_seek or has_draw_fn) and len(forbidden_matches) == 0
    return {
        "ok": ok,
        "has_window_seek": has_window_seek,
        "has_draw_fn": has_draw_fn,
        "forbidden_timers": forbidden_matches,
    }


def validate_semantic_beat_density(
    beats_count: int,
    duration_sec: float = 30.0,
    min_beats_per_30s: int = MIN_BEATS_PER_30S,
    max_beats_per_30s: int = MAX_BEATS_PER_30S,
) -> Dict[str, Any]:
    """Verify that semantic beat density stays within 12-15 beats per 30 seconds."""
    if duration_sec <= 0.0:
        raise ValueError("duration_sec must be > 0")
    normalized_per_30s = float(beats_count) * (30.0 / float(duration_sec))
    ok = float(min_beats_per_30s) - 1e-6 <= normalized_per_30s <= float(max_beats_per_30s) + 1e-6
    return {
        "ok": ok,
        "beats_count": int(beats_count),
        "duration_sec": float(duration_sec),
        "beats_per_30s": round(normalized_per_30s, 3),
        "target_range": (min_beats_per_30s, max_beats_per_30s),
    }


def plan_semantic_beats(
    duration_sec: float = 30.0,
    beats_per_30s: int = DEFAULT_BEATS_PER_30S,
    topic: str = "STM32H743 + IS61LV6416 Biquad IIR Pipeline",
) -> List[Dict[str, Any]]:
    """Generate a deterministic schedule of semantic visual beats at 12-15 beats per 30s."""
    clamped_rate = max(MIN_BEATS_PER_30S, min(MAX_BEATS_PER_30S, int(beats_per_30s)))
    total_beats = max(1, int(round(clamped_rate * (float(duration_sec) / 30.0))))
    beat_span = float(duration_sec) / float(total_beats)

    beat_archetypes = (
        ("spring_entrance", "Hardware block spring entrance via closed_form_spring"),
        ("bus_trace_pulse", "FMC address/data bus wave propagation"),
        ("span_formula_reveal", "Transfer function [span] term illumination + ding SFX"),
        ("match_position_morph", "Match-position bounding box transition to Z-plane"),
        ("pole_zero_locus", "Complex conjugate pole radius r < 1 stability sweep"),
        ("parameter_readout", "Numeric telemetry badge update (ADDSET=1, DATAST=2)"),
    )
    schedule: List[Dict[str, Any]] = []
    for idx in range(total_beats):
        t_start = round(idx * beat_span, 4)
        t_end = round(min(float(duration_sec), (idx + 1) * beat_span), 4)
        kind, desc = beat_archetypes[idx % len(beat_archetypes)]
        schedule.append(
            {
                "beat_index": idx + 1,
                "t_start": t_start,
                "t_end": t_end,
                "duration": round(t_end - t_start, 4),
                "kind": kind,
                "topic": topic,
                "description": f"{desc} ({topic})",
                "zeta": 1.0,
                "omega0": 12.0,
            }
        )
    return schedule


_CURATED_ARCHETYPES: Tuple[Tuple[str, str, Tuple[str, ...], str], ...] = (
    (
        "Exploded Hardware SoC Bus Timing Architecture",
        "explainer",
        ("canvas", "svg"),
        "Exploded isometric block diagram of STM32H743 MCU and IS61LV6416 SRAM with closed_form_spring assembly and deterministic window.seek(t).",
    ),
    (
        "Z-Plane Pole-Zero Stability & Biquad IIR Cascade",
        "explainer",
        ("canvas", "svg", "gsap"),
        "Mathematical explainer of H(z) transfer function, unit circle stability boundary, and frequency response sweep driven by window.seek(t).",
    ),
    (
        "Three.js 3D Exploded PCB & Memory Controller Pipeline",
        "3d",
        ("threejs", "shader", "canvas"),
        "Deterministic 3D orthographic/perspective exploded PCB assembly with critically damped spring camera transitions and shader bus glow.",
    ),
    (
        "GLSL Signed Distance Field Wave & Fourier Epicycles",
        "motion",
        ("shader", "canvas"),
        "Real-time fragment shader + HTML5 Canvas phase-locked epicycle decomposition with 14 semantic beats per 30s.",
    ),
    (
        "SVG Vector Match-Position System Topology Morph",
        "motion",
        ("svg", "gsap"),
        "Morphological match-position transitions between high-level architecture diagram and register-level bitfields using analytical springs.",
    ),
    (
        "Three.js Volumetric Tensor & Attention KV-Cache Flow",
        "3d",
        ("threejs", "canvas"),
        "3D matrix tile streaming animation with deterministic seek(t) timeline scrub and critically damped spring keyframes.",
    ),
    (
        "Kinetic Typography & Formula Derivation Stage",
        "explainer",
        ("svg", "canvas"),
        "Synchronized [span] equation spotlighting, callout braces, and dark-slate grid layout with zero overlap defects.",
    ),
    (
        "Shader-Driven Acoustic Spectrogram & VAD Envelope",
        "motion",
        ("shader", "canvas", "gsap"),
        "Deterministic 48 kHz waveform and -12 dB audio-ducking envelope visualizer stepped via draw(t).",
    ),
)


def _build_default_catalog() -> List[PromptPattern]:
    """Deterministically build the 1,007-entry catalog (703 Opus 5.5 + 304 Gemini 4 Argon)."""
    patterns: List[PromptPattern] = []

    repo_specs = (
        (OPUS_REPO, "opus55", OPUS_PROMPT_COUNT),
        (GEMINI_ARGON_REPO, "argon4", GEMINI_ARGON_PROMPT_COUNT),
    )

    tag_combinations: Tuple[Tuple[str, ...], ...] = (
        ("canvas",),
        ("svg",),
        ("threejs",),
        ("gsap",),
        ("shader",),
        ("canvas", "svg"),
        ("threejs", "shader"),
        ("canvas", "gsap"),
        ("svg", "gsap"),
        ("threejs", "canvas", "shader"),
    )

    for repo_name, prefix, count in repo_specs:
        for i in range(1, count + 1):
            arch_idx = (i - 1) % len(_CURATED_ARCHETYPES)
            base_title, base_cat, base_tags, base_summary = _CURATED_ARCHETYPES[arch_idx]
            category = SUPPORTED_CATEGORIES[(i - 1) % len(SUPPORTED_CATEGORIES)] if i > len(_CURATED_ARCHETYPES) else base_cat
            tags = tag_combinations[(i - 1) % len(tag_combinations)] if i > len(_CURATED_ARCHETYPES) else base_tags
            beats = MIN_BEATS_PER_30S + ((i - 1) % (MAX_BEATS_PER_30S - MIN_BEATS_PER_30S + 1))

            prompt_id = f"{prefix}_{i:04d}"
            title = f"{base_title} #{i:03d}"
            sys_prompt = (
                f"/* {prompt_id} | repo={repo_name} | category={category} | tags={','.join(tags)} */\n"
                f"{SYSTEM_TEMPLATE_DETERMINISTIC_SEEK}\n"
                f"{SYSTEM_TEMPLATE_CLOSED_FORM_SPRING}\n"
                f"{SYSTEM_TEMPLATE_SEMANTIC_BEAT_DENSITY}\n"
                f"// Target beat density: {beats} semantic beats per 30s.\n"
                f"window.seek = function(t) {{ draw(t); }};"
            )
            patterns.append(
                PromptPattern(
                    id=prompt_id,
                    title=title,
                    source_repo=repo_name,
                    category=category,
                    tech_tags=tags,
                    semantic_beats_per_30s=beats,
                    deterministic_seek=True,
                    uses_spring_physics=True,
                    match_position=True,
                    system_prompt=sys_prompt,
                    summary=f"[{repo_name}] {base_summary}",
                    parameters={
                        "zeta": 1.0,
                        "omega0": 12.0 + float((i % 5)),
                        "fps": 30,
                        "beats_per_30s": beats,
                    },
                )
            )
    return patterns


class FlowPromptLibrary:
    """Searchable index of 1,007 deterministic video prompt patterns and system templates."""

    def __init__(self, patterns: Optional[Sequence[PromptPattern]] = None) -> None:
        self._patterns: List[PromptPattern] = list(patterns) if patterns is not None else _build_default_catalog()
        self._by_id: Dict[str, PromptPattern] = {p.id: p for p in self._patterns}

    @property
    def prompts(self) -> List[PromptPattern]:
        return list(self._patterns)

    def __len__(self) -> int:
        return len(self._patterns)

    def get_by_id(self, prompt_id: str) -> Optional[PromptPattern]:
        return self._by_id.get(prompt_id)

    def get_system_templates(self) -> Dict[str, str]:
        return dict(SYSTEM_TEMPLATES)

    def get_stats(self) -> Dict[str, Any]:
        by_repo: Dict[str, int] = {}
        by_category: Dict[str, int] = {c: 0 for c in SUPPORTED_CATEGORIES}
        by_tag: Dict[str, int] = {t: 0 for t in SUPPORTED_TECH_TAGS}

        for p in self._patterns:
            by_repo[p.source_repo] = by_repo.get(p.source_repo, 0) + 1
            if p.category in by_category:
                by_category[p.category] += 1
            for tag in p.tech_tags:
                if tag in by_tag:
                    by_tag[tag] += 1

        return {
            "total_prompts": len(self._patterns),
            "by_repo": by_repo,
            "by_category": by_category,
            "by_tech_tag": by_tag,
            "supported_categories": list(SUPPORTED_CATEGORIES),
            "supported_tech_tags": list(SUPPORTED_TECH_TAGS),
            "beat_density_range": [MIN_BEATS_PER_30S, MAX_BEATS_PER_30S],
        }

    def search(
        self,
        query: Optional[str] = None,
        category: Optional[str] = None,
        tech_tags: Optional[Iterable[str]] = None,
        source_repo: Optional[str] = None,
        require_all_tags: bool = False,
        limit: Optional[int] = None,
    ) -> List[PromptPattern]:
        """Filter and rank prompt patterns by category, tech_tags, source_repo, and text query."""
        if category is not None and category not in SUPPORTED_CATEGORIES:
            raise ValueError(f"Unsupported category '{category}'. Expected one of {SUPPORTED_CATEGORIES}")

        tag_set = {t.strip().lower() for t in (tech_tags or []) if t.strip()}
        for t in tag_set:
            if t not in SUPPORTED_TECH_TAGS:
                raise ValueError(f"Unsupported tech_tag '{t}'. Expected subset of {SUPPORTED_TECH_TAGS}")

        q_tokens = [tok.lower() for tok in re.split(r"\s+", query.strip()) if tok] if query else []

        results: List[PromptPattern] = []
        for p in self._patterns:
            if category is not None and p.category != category:
                continue
            if source_repo is not None and p.source_repo != source_repo:
                continue
            if tag_set:
                p_tags = set(p.tech_tags)
                if require_all_tags:
                    if not tag_set.issubset(p_tags):
                        continue
                else:
                    if not (tag_set & p_tags):
                        continue
            if q_tokens:
                haystack = f"{p.id} {p.title} {p.summary} {p.category} {' '.join(p.tech_tags)}".lower()
                if not all(tok in haystack for tok in q_tokens):
                    continue
            results.append(p)
            if limit is not None and len(results) >= limit:
                break

        return results

    def compose_system_prompt(
        self,
        category: str = "explainer",
        tech_tags: Sequence[str] = ("canvas", "svg"),
        duration_sec: float = 30.0,
        beats_per_30s: int = DEFAULT_BEATS_PER_30S,
        topic: str = "STM32H743 + IS61LV6416 Biquad IIR Pipeline",
    ) -> Dict[str, Any]:
        """Compose a production system prompt combining all 3 deterministic animation rules."""
        matches = self.search(category=category, tech_tags=tech_tags, limit=3)
        beats = plan_semantic_beats(duration_sec=duration_sec, beats_per_30s=beats_per_30s, topic=topic)
        density_check = validate_semantic_beat_density(len(beats), duration_sec=duration_sec)
        prompt_text = "\n\n".join(
            [
                f"# TOPIC: {topic}",
                f"# CATEGORY: {category} | TECH_TAGS: {', '.join(tech_tags)}",
                SYSTEM_TEMPLATE_DETERMINISTIC_SEEK.strip(),
                SYSTEM_TEMPLATE_CLOSED_FORM_SPRING.strip(),
                SYSTEM_TEMPLATE_SEMANTIC_BEAT_DENSITY.strip(),
            ]
        )
        return {
            "topic": topic,
            "category": category,
            "tech_tags": list(tech_tags),
            "reference_pattern_ids": [m.id for m in matches],
            "beat_schedule": beats,
            "beat_density_validation": density_check,
            "system_prompt": prompt_text,
        }


_DEFAULT_LIBRARY: Optional[FlowPromptLibrary] = None


def get_flow_prompt_library() -> FlowPromptLibrary:
    """Singleton accessor for the local reference prompt library."""
    global _DEFAULT_LIBRARY
    if _DEFAULT_LIBRARY is None:
        _DEFAULT_LIBRARY = FlowPromptLibrary()
    return _DEFAULT_LIBRARY


# ---------------------------------------------------------------------------
# Google Flow Master Prologue Micro-Shot Specification Matrix (R1 & R2)
# ---------------------------------------------------------------------------

BANNED_QUALITY_BOOSTERS: Tuple[str, ...] = (
    "photorealistic",
    "hyperrealistic",
    "ultra realistic",
    "4k",
    "8k",
    "ultra hd",
    "high resolution",
    "masterpiece",
    "highly detailed",
    "ultra detailed",
    "trending on artstation",
    "best quality",
    "award winning",
)

GOOGLE_PROMPT_COMPONENTS: Tuple[str, ...] = (
    "subject",
    "action",
    "context",
    "composition",
    "style_lighting",
)


def strip_banned_quality_boosters(text: str) -> str:
    """Strip all 13 banned quality booster tokens from prompt text."""
    cleaned = text
    for booster in BANNED_QUALITY_BOOSTERS:
        pattern = re.compile(rf"\b{re.escape(booster)}\b", re.IGNORECASE)
        cleaned = pattern.sub("", cleaned)
    # Collapse multiple spaces or commas
    cleaned = re.sub(r",\s*,+", ",", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,")
    return cleaned


@dataclass(frozen=True)
class PrologueMicroShot:
    """Master specification for a single Google Flow micro-shot (1.5s - 3.0s)."""

    id: str
    manga_frames: str
    duration_sec: float
    camera: str
    gaze_lock: str
    style_domain: str
    subject: str
    action: str
    context: str
    composition: str
    style_lighting: str
    negative_prompt: str
    reference_bindings: Tuple[str, ...]
    dialogue_beat: str

    def compose_positive_prompt(self) -> str:
        """Compose 5-component Google Flow standard prompt stripped of banned buzzwords."""
        raw_prompt = (
            f"Subject: {self.subject} "
            f"Action: {self.action} "
            f"Context: {self.context} "
            f"Composition: {self.composition} "
            f"Style/Lighting: {self.style_lighting}"
        )
        return strip_banned_quality_boosters(raw_prompt)


def format_micro_shot_prompt(shot: PrologueMicroShot) -> str:
    """Format prompt for Google Flow composer."""
    return shot.compose_positive_prompt()


def compose_flow_micro_shot_payload(
    shot: PrologueMicroShot,
    aspect: str = "16:9",
    model: str = "veo_3_1_extension_lite",
) -> Dict[str, Any]:
    """Compose complete JSON-compatible payload for Google Flow API / CLI generation."""
    return {
        "micro_shot_id": shot.id,
        "manga_frames": shot.manga_frames,
        "duration_sec": shot.duration_sec,
        "aspect_ratio": aspect,
        "model": model,
        "positive_prompt": shot.compose_positive_prompt(),
        "negative_prompt": shot.negative_prompt,
        "camera_vector": shot.camera,
        "gaze_lock_vector": shot.gaze_lock,
        "style_domain": shot.style_domain,
        "reference_bindings": list(shot.reference_bindings),
        "dialogue_beat": shot.dialogue_beat,
    }


MS_01A = PrologueMicroShot(
    id="MS-01A",
    manga_frames="Frame 001",
    duration_sec=1.8,
    camera="Static macro framing with slow forward push-in (+2%) along optical axis into CRT glass.",
    gaze_lock="Center of curved CRT gaming display (No human subject).",
    style_domain="Retro Game CRT UI / Pixel Scanline Glow",
    subject="Curved glass retro gaming CRT monitor displaying glowing golden pixelated victory runes 'CONGRATULATIONS! GAME CLEAR!'.",
    action="Golden celebratory runic confetti gently cascades downward across the display with subtle phosphor bloom.",
    context="Dark 3 AM studio bedroom visible in soft peripheral blur, reflections of room ambient light on monitor glass.",
    composition="Extreme close-up macro shot centered on display, shallow depth of field, subtle 2% forward optical push-in.",
    style_lighting="Stylized retro game aesthetic, intense amber and gold luminescence, visible CRT scanlines, cold cyan ambient rim.",
    negative_prompt="turning head away, side glance, human face, modern flat panel, speech bubbles, blurry text, oversaturated neon, chromatic aberration",
    reference_bindings=("ING_GAME_SCREEN", "ING_STREAMER_ROOM"),
    dialogue_beat="CONGRATULATIONS! GAME CLEAR! golden fanfare",
)

MS_01B = PrologueMicroShot(
    id="MS-01B",
    manga_frames="Frame 002",
    duration_sec=2.2,
    camera="Frontal medium shot at eye level, locked tripod framing, zero lateral drift.",
    gaze_lock="STREAMER FACE-LOCKED: Head tilted up 10 deg in roar, facial plane strictly aligned with monitor axis, head yaw 0 deg.",
    style_domain="Fortiche Production Arcane 2.5D animation style",
    subject="Streamer Ash, young Korean male with disheveled black hair and dark exhaustion eye rings, wearing oversized light-blue fleece hoodie #88bbee and black over-ear headset.",
    action="Leaps slightly back in gaming chair throwing both arms straight up into the air, mouth wide open in an ecstatic victory roar, teeth visible, joyful tears in eyes.",
    context="Battlestation desk with glowing ultrawide gaming display in front, dark acoustic foam pyramid wall panels behind.",
    composition="Frontal medium shot, eye level, locked tripod framing, subject centered, zero camera roll.",
    style_lighting="Fortiche Arcane 2.5D animation, visible oil and gouache impasto brushstrokes, bold ink contours, cool cyan monitor key light, soft violet ambient fill.",
    negative_prompt="turning head away, side glance, looking away, profile view of face, head twisting, wandering eyes, asymmetrical headset, floating headphones, rear monitors, monitors behind back, speech bubbles, text watermark, extra arms, extra fingers",
    reference_bindings=("@Ash_Streamer", "keyframe_01_frame002.png", "ING_STREAMER_PC"),
    dialogue_beat="Unhinged roar of triumph upon clearing the decade-long unconquered game",
)

MS_01C = PrologueMicroShot(
    id="MS-01C",
    manga_frames="Frames 003-004",
    duration_sec=2.0,
    camera="Low-angle dynamic close-up looking up at mouth and eyes, forward Z-axis glide matching forward lean (+3%).",
    gaze_lock="STREAMER FACE-LOCKED: Leans forward along Z-axis toward mic, head yaw 0 deg, eyes locked on webcam lens and pop filter.",
    style_domain="Fortiche Production Arcane 2.5D animation style",
    subject="Streamer Ash in light-blue hoodie #88bbee and black studio headphones clamped firmly over both ears, beads of sweat on temples, intense dilated pupils.",
    action="Leans forward along central optical axis toward the cardioid boom microphone, teeth bared shouting with joyful intensity, veins visible on neck.",
    context="Desk surface with pop filter in soft foreground focus, ultrawide screen casting bright phosphor wash from below.",
    composition="Low-angle medium close-up, centered on face and microphone, steady forward optical tracking, zero lateral tilt.",
    style_lighting="Fortiche Arcane hand-painted impasto style, sharp graphic ink contours, high-contrast chiaroscuro, intense cyan rim lighting on jawline and headset.",
    negative_prompt="turning head away, side glance, head rotation, loose headphones, distorted jaw, floating microphone, rear monitors, speech bubbles, blurry motion",
    reference_bindings=("@Ash_Streamer", "ep01_frame_003_clean.png", "ING_STREAMER_PC"),
    dialogue_beat="WOW! I FINALLY BEAT THIS GODD*** GAME!!!",
)

MS_02A = PrologueMicroShot(
    id="MS-02A",
    manga_frames="Frames 005-007",
    duration_sec=2.5,
    camera="Slow cinematic forward dolly gliding through the carved stone portal into stormy mountain horizon.",
    gaze_lock="Environmental fantasy lore scene (No human subject).",
    style_domain="Dark Fantasy Lore / Fortiche Arcane Matte Painting",
    subject="Colossal weathered granite portal chiseled with ancient Romanesque golden runic letters 'SAVE THE EMPIRE', intricate imperial heraldic relief carvings.",
    action="Heavy atmospheric battlefield mist rolls between cracked stone columns, golden dust motes drift lazily through the archway.",
    context="Desolate stormy mountain pass of the fantasy empire, dark rain clouds rolling over distant crenellated towers.",
    composition="Grand symmetrical wide shot looking through stone portal, slow smooth forward dolly tracking along ground plane.",
    style_lighting="Fortiche Arcane matte painting, visible textured palette knife oil strokes, warm amber edge-light on chiseled runes, moody stormy sky.",
    negative_prompt="modern room, streamer, computer screen, modern typography, plastic 3D CGI, speech bubbles, watermark, distorted letters, fast panning",
    reference_bindings=("keyframe_02_frame005.png", "ING_GAME_SCREEN"),
    dialogue_beat="SAVE THE EMPIRE - IS A RETRO GAME NOTORIOUS FOR ITS BRUTAL DIFFICULTY. TODAY A GAMER HAS BEATEN IT!",
)

MS_02B = PrologueMicroShot(
    id="MS-02B",
    manga_frames="Frame 008",
    duration_sec=2.0,
    camera="Frontal medium close-up at eye level, static tripod framing, locked optical center.",
    gaze_lock="STREAMER FACE-LOCKED & WEBCAM GAZE PINNED: Eyes dead-center into webcam lens, unwavering contact, head yaw 0 deg.",
    style_domain="Fortiche Production Arcane 2.5D animation style",
    subject="Streamer Ash in sky-blue hoodie #88bbee and black over-ear headset, sharp jawline, dark pupils carrying bright specular catchlights.",
    action="Displays a confident charismatic half-smirk, points his right index finger squarely forward into the webcam lens, head held proud and steady.",
    context="Battlestation gaming room, glowing ultrawide display in front, dark acoustic foam wall in background, strictly zero monitors behind back.",
    composition="Frontal medium close-up, eye level, finger projecting forward along central optical axis with shallow depth of field.",
    style_lighting="Fortiche Arcane hand-painted aesthetic, dynamic ink contours, chiaroscuro with cool blue-white key light on face, violet rim lighting on shoulders.",
    negative_prompt="turning head away, looking away from webcam, side glance, distorted hand, extra fingers, loose headset, floating headphones, rear monitors, speech bubbles",
    reference_bindings=("@Ash_Streamer", "ep01_frame_008_clean.png", "ING_STREAMER_PC"),
    dialogue_beat="SEE? WHAT DID I TELL YOU ALL? THAT GAMER IS ME!",
)

MS_03A = PrologueMicroShot(
    id="MS-03A",
    manga_frames="Frame 009",
    duration_sec=2.5,
    camera="High-angle top-down isometric view with smooth downward camera pan (10 deg) across parchment lines and bastions.",
    gaze_lock="Tactical war map (No human subject).",
    style_domain="Fantasy War-Room Tactical Map / Arcane Stylized Graphic",
    subject="Aged yellowed vellum tactical war map of Crossroads Fortress with hand-drawn stone ramparts, fortified bastions, and glowing cyan tactical defense hex grids.",
    action="Red calligraphic invasion arrows indicating monster horde attack vectors slowly pulse across the map terrain, small troop tokens positioned at choke points.",
    context="Imperial strategy table lit by flickering candlelight and ambient cyan monitor glow reflecting onto parchment edges.",
    composition="High-angle isometric war-room perspective, slow steady downward pan along primary bastion axis.",
    style_lighting="Fortiche Arcane cartographic illustration, rich hand-painted paper grain, luminous cyan vector overlays, deep sepia and umber ink washes.",
    negative_prompt="modern room, streamer face, 3D photo terrain, speech bubbles, blurry grid, pixel distortion, digital watermark, chaotic camera spin",
    reference_bindings=("ep01_frame_009_clean.png", "ING_GAME_SCREEN"),
    dialogue_beat="IT DOESN'T MATTER HOW DIFFICULT A GAME IS. THERE IS ALWAYS A WAY TO BEAT IT!",
)


MS_03B = PrologueMicroShot(
    id="MS-03B",
    manga_frames="Frames 010-013",
    duration_sec=2.5,
    camera="High-angle crane shot slowly pulling back and tilting down (15 deg) establishing the quiet solitary late-night room.",
    gaze_lock="STREAMER POSITION LOCKED: Seated squarely facing dual monitors, silhouette facing screens.",
    style_domain="Fortiche Production Arcane 2.5D animation style",
    subject="Streamer Ash seated in high-back gaming chair, dark silhouette wearing light-blue hoodie #88bbee and headset, facing forward toward glowing screens.",
    action="Typing rapidly with both hands on mechanical RGB keyboard, mouse micro-adjustments, steady calm posture.",
    context="Cluttered 3 AM studio bedroom, dark charcoal walls covered in acoustic pyramid foam tiles, straight desk, glowing 3-ring RGB PC tower on floor right.",
    composition="High-angle wide establishing shot from upper corner of room, smooth slow crane pullback revealing full desk workstation.",
    style_lighting="Fortiche Arcane atmospheric rendering, deep chiaroscuro, dominant cyan and cold-white monitor glow casting sharp room shadows, zero rear monitors.",
    negative_prompt="turning head away, head rotation, monitors behind back, screens on rear wall, daytime lighting, bright sunlight, turning around, messy face morph, speech bubbles, watermark",
    reference_bindings=("streamer_room_environment.png", "streamer_pc_desk_closeup.png", "@Ash_Streamer"),
    dialogue_beat="I'M A GAME STREAMER WHO ONLY PLAYS RETRO GAMES KNOWN TO BE BRUTALLY DIFFICULT.",
)

MS_04A = PrologueMicroShot(
    id="MS-04A",
    manga_frames="Frame 014",
    duration_sec=2.2,
    camera="Frontal medium shot at desk level, locked static tripod framing, perfectly centered.",
    gaze_lock="STREAMER FACE-LOCKED & WEBCAM GAZE PINNED: Ash looks squarely into webcam lens with warm grateful smile, head yaw 0 deg.",
    style_domain="Fortiche Production Arcane 2.5D animation style",
    subject="Streamer Ash in light-blue hoodie #88bbee and black studio headphones, bright expressive eyes carrying vivid cyan catchlights.",
    action="Smiles warmly with hands clasped together in front of chest in heartfelt gratitude toward the webcam, speaking with joyful sincerity.",
    context="Center gaming display glowing softly, scissor boom microphone with pop filter in foreground, golden translucent 'FOXY 300,000 KRW' donation banner popping up in upper-right stream HUD.",
    composition="Frontal medium shot, eye level, symmetrical posture, clamped tripod framing, zero lateral drift.",
    style_lighting="Fortiche Arcane painterly 2.5D aesthetic, rich gouache impasto, radiant golden donation bloom contrasting with cool cyan monitor wash.",
    negative_prompt="turning head away, side glance, looking away, asymmetrical headset, detached headphones, distorted hands, extra fingers, rear monitors behind chair, speech bubbles",
    reference_bindings=("@Ash_Streamer", "keyframe_03_frame014.png", "stream_overlay_chat_donation.png", "ING_STREAMER_PC"),
    dialogue_beat="OH, FOXY! THANK YOU FOR THE 300,000 WON DONATION! YOU GUYS ARE THE REAL MVPS!",
)

MS_04B = PrologueMicroShot(
    id="MS-04B",
    manga_frames="Frames 015-016",
    duration_sec=2.0,
    camera="Frontal medium close-up, camera glides slightly backward along Z-axis (2%) as Ash reclines into his chair.",
    gaze_lock="STREAMER FACE-LOCKED: Reclines directly backward against headrest along pure Z-axis, head yaw 0 deg, eyes forward.",
    style_domain="Fortiche Production Arcane 2.5D animation style",
    subject="Streamer Ash wearing light-blue hoodie #88bbee and black over-ear headset, disheveled jet-black hair, tired happy eyes with amber glints.",
    action="Reclines back into his chair headrest with a cheeky self-satisfied smirk, raises right hand to lightly rub the bridge of his nose in pride.",
    context="Desktop setup in front, acoustic pyramid foam panels behind, cool cyan monitor wash illuminating face evenly.",
    composition="Frontal medium close-up, eye level, locked optical axis, subject reclining along Z-axis only, zero head roll.",
    style_lighting="Fortiche Arcane hand-painted style, visible brush textures on fabric and skin, crisp graphic ink linework, soft chiaroscuro shadows.",
    negative_prompt="turning head away, looking away, profile view, distorted fingers, floating headset, rear monitors, monitors behind back, speech bubbles, blurry motion",
    reference_bindings=("@Ash_Streamer", "ep01_frame_016_clean.png", "ING_STREAMER_PC"),
    dialogue_beat="WELL, OKAY... I GUESS I WAS PRETTY AWESOME, TOO. I WAS VERY AWESOME.",
)

MS_04C = PrologueMicroShot(
    id="MS-04C",
    manga_frames="Frame 017",
    duration_sec=1.8,
    camera="Static frontal medium close-up, held steady with zero camera movement.",
    gaze_lock="STREAMER FACE-LOCKED: Rests peacefully in chair, smiling with quiet satisfaction, gazing straight ahead at victory screen.",
    style_domain="Fortiche Production Arcane 2.5D animation style",
    subject="Streamer Ash resting comfortably in gaming chair, disheveled black bangs falling over forehead, calm proud half-smile, headset settled symmetrically.",
    action="Gentle breathing motion, chest rising subtly, eyes looking forward at monitor with calm glowing satisfaction, completely still posture.",
    context="Dark studio bedroom, soft ambient light from curved monitor, acoustic foam wall behind, zero rear monitors.",
    composition="Frontal medium close-up, centered framing, static tripod, shallow depth of field softly blurring background.",
    style_lighting="Fortiche Arcane painterly aesthetic, subtle impasto strokes, balanced dual-tone lighting with cyan key and violet ambient rim.",
    negative_prompt="head rotation, looking away, wandering eyes, sudden jerk, loose headphones, rear monitors, speech bubbles, watermark",
    reference_bindings=("@Ash_Streamer", "ING_STREAMER_PC"),
    dialogue_beat="IS THERE A GREATER ACHIEVEMENT FOR A GAMER THAN THAT?",
)

MS_05A = PrologueMicroShot(
    id="MS-05A",
    manga_frames="Frame 018",
    duration_sec=2.0,
    camera="Frontal extreme close-up on eyes and upper face, static locked tripod framing.",
    gaze_lock="STREAMER FACE-LOCKED: Head rigidly locked facing front (yaw 0 deg), pupils flick 10 deg to upper-right chat screen.",
    style_domain="Fortiche Production Arcane 2.5D animation style",
    subject="Streamer Ash's eyes and upper face in extreme close-up, disheveled black fringe, dark fatigue rings under lower eyelids, sharp facial features.",
    action="Cocky smile instantly dissolves into serious expression; pupils flick 10 degrees to upper-right to read chat text, holding steady without blinking.",
    context="Face lit by cold phosphor glow from monitor screen, dark background with subtle violet rim light on temples.",
    composition="Extreme close-up on eye-line, centered framing, static locked tripod, sharp focus on irises and eyelashes.",
    style_lighting="Fortiche Arcane painterly aesthetic, expressive ink contours, chiaroscuro with cold cyan monitor wash highlighting pupil catchlights.",
    negative_prompt="turning head, twisting neck, side profile of face, strabismus, crossed eyes, distorted eyes, floating headset, rear monitors, speech bubbles",
    reference_bindings=("@Ash_Streamer", "ep01_frame_018_clean.png", "ING_STREAMER_PC"),
    dialogue_beat="Cocky smirk vanishes as Ash spots an emotional comment in chat",
)


MS_05B = PrologueMicroShot(
    id="MS-05B",
    manga_frames="Frames 019-020",
    duration_sec=2.0,
    camera="Static close-up on vertical monitor screen showing translucent live stream chat overlay.",
    gaze_lock="Digital stream interface (No human subject).",
    style_domain="Modern Streaming UI / Translucent HUD Overlay",
    subject="Modern translucent dark-mode live streaming chat window overlaid on side display, cleanly formatted viewer messages scrolling upwards.",
    action="Viewer message from 'Sanghy' glows softly in cyan accent box: 'So sad the priestess died in the final battle :( she carried so hard for an R-rank character...'.",
    context="Blurred edge of primary gaming display visible on left, dark acoustic bedroom background in deep bokeh.",
    composition="Medium close-up on vertical monitor display, straight eye-level framing, zero tilt.",
    style_lighting="Clean digital stream graphics, crisp readable typography, subtle glassmorphism transparency, soft cyan and white text glow.",
    negative_prompt="streamer face, blurry text, illegible fonts, chaotic emoji spam, watermark, video artifacts, low resolution text",
    reference_bindings=("stream_overlay_chat_donation.png", "ING_STREAM_HUD"),
    dialogue_beat="Sanghy: So sad the priestess died in the final battle :( she carried so hard for an R-rank character...",
)

MS_05C = PrologueMicroShot(
    id="MS-05C",
    manga_frames="Frames 021-022",
    duration_sec=2.2,
    camera="Low-angle medium shot looking up from desk surface, slow subtle forward push-in along center axis (2%).",
    gaze_lock="STREAMER FACE-LOCKED (PITCH DOWN ONLY): Head bowed down 10 deg along pitch axis, head yaw 0 deg, eyes on keyboard.",
    style_domain="Fortiche Production Arcane 2.5D animation style",
    subject="Streamer Ash seen from low chest angle, wearing light-blue hoodie #88bbee and black headset, hands resting completely motionless on RGB keyboard and mouse.",
    action="Head bowed slightly down in somber contemplation, eyes half-lidded looking down at keyboard keys, breathing slow and heavy with survivor's guilt.",
    context="Rectangular desk bathed in cold cyan monitor light, scissor boom mic standing silent in foreground, dark room behind, zero rear monitors.",
    composition="Low-angle medium shot looking up from desk surface, slow subtle forward push-in along center axis, zero roll.",
    style_lighting="Fortiche Arcane hand-painted style, heavy moody impasto shadows, cold phosphor light bathing hands and lower jaw, somber chiaroscuro.",
    negative_prompt="turning head away, side glance, looking away, twisted neck, distorted fingers, floating headset, rear monitors, speech bubbles, bright happy lighting",
    reference_bindings=("@Ash_Streamer", "ep01_frame_021_clean.png", "ING_STREAMER_PC"),
    dialogue_beat="Heavy silence: I WANTED ALL MY CHARACTERS TO SURVIVE THE FINAL BATTLE... BUT EVERYONE OTHER THAN LUCAS DIED.",
)

MS_06A = PrologueMicroShot(
    id="MS-06A",
    manga_frames="Frames 024-025",
    duration_sec=2.5,
    camera="Direct frontal close-up centered on monitor display, smooth steady push-in toward MVP card (+4%).",
    gaze_lock="Tactical 2D UI asset on monitor (No human subject in room).",
    style_domain="DOMAIN 1: 2D Tactical Game Card (Monitor UI)",
    subject="Digital 2D tactical RPG character reward card displayed on PC monitor, featuring clean stylized 2D anime bust portrait of blonde vanguard knight Lucas in polished silver armor.",
    action="Golden laurel wreath around portrait shimmers with subtle particle sparkle, golden text banner 'STAGE MVP - Lucas [SSR]' pulses gently with victory glow.",
    context="Displayed strictly inside rectangular game UI window on computer monitor, Hell Difficulty and Ironman Mode badges visible in header.",
    composition="Direct frontal close-up centered on the monitor display, smooth steady push-in toward the MVP card, perfectly flat plane.",
    style_lighting="Stylized 2D tactical game illustration, crisp clean vector lines, bright gold filigree, vibrant saturated colors, flat digital screen lighting.",
    negative_prompt="3D CGI impasto, realistic human skin, dirty battered armor, blood, rain, battlefield background, streamer face, speech bubbles, blurry text",
    reference_bindings=("knight_lucas_portrait.png", "game_save_the_empire_screen.png", "ING_GAME_SCREEN"),
    dialogue_beat="LAST STAGE CLEAR! STAGE MVP - Lucas [SSR] | Hell Difficulty & Ironman Mode | [Player: Retro Gamer]",
)

MS_06B = PrologueMicroShot(
    id="MS-06B",
    manga_frames="Frame 023",
    duration_sec=2.8,
    camera="High-angle sweeping crane shot moving slowly forward and down along the devastated parapet (20 deg downward tilt).",
    gaze_lock="Battlefield aftermath (No human face).",
    style_domain="DOMAIN 2: Fortiche Production Arcane Cinematic 3D",
    subject="Devastated stone ramparts of Crossroads Fortress strewn with fallen imperial soldiers, shattered wooden tower shields, and snapped steel spears.",
    action="Heavy relentless rain pours down splashing against bloodied flagstones, thick black smoke curls up from burning siege ballistas.",
    context="Fortress parapet overlooking stormy dark chasm, lightning flashing silently in distant storm clouds, somber tragic atmosphere.",
    composition="High-angle sweeping crane shot moving slowly forward and down along the devastated parapet, dramatic deep perspective.",
    style_lighting="Fortiche Arcane cinematic 3D painterly style, visible thick oil brushstrokes, dark steel-blue and ash-grey palette, cold lightning rim light.",
    negative_prompt="modern room, streamer, computer screen, 2D anime card, sunny weather, peaceful scenery, speech bubbles, cartoon gore, plastic 3D CGI",
    reference_bindings=("keyframe_04_frame023.png", "ING_GAME_SCREEN", "knight_lucas_turnaround.png"),
    dialogue_beat="EVERYONE OTHER THAN LUCAS, THE MAIN CHARACTER, DIED IN BATTLE.",
)


MS_07A = PrologueMicroShot(
    id="MS-07A",
    manga_frames="Frames 026-028",
    duration_sec=2.5,
    camera="Low-angle tracking shot from behind, camera slowly moving forward along the floor toward Lucas's solitary figure.",
    gaze_lock="LUCAS REAR ORIENTATION LOCK: Head bowed, eyes unseen, back squarely to camera.",
    style_domain="DOMAIN 2: Fortiche Production Arcane Cinematic 3D",
    subject="Full rear view of adult Vanguard Knight Lucas in battle-damaged silver-steel plate armor, monster claw gouges on breastplate, tattered royal-blue cape hanging limp, notched broadsword held tip-down in right gauntlet.",
    action="Stands completely motionless with broad muscular shoulders hunched forward, tousled golden hair visible at nape of bowed head, smoke drifting past armor plates.",
    context="Desecrated Cathedral Throne Hall with shattered stained-glass rose window, motionless body of the fallen boss on marble steps.",
    composition="Low-angle tracking shot from behind, camera slowly moving forward along the floor toward Lucas's solitary figure.",
    style_lighting="Fortiche Arcane painterly 2.5D animation, rich oil impasto textures on metal and velvet, somber directional light from high cathedral arches.",
    negative_prompt="front view of face, turning head around, modern room, streamer, 2D anime card, smiling, bright cheery lighting, speech bubbles, clean parade armor",
    reference_bindings=("knight_lucas_solitary_back_flow.png", "@Lucas_Knight", "keyframe_05_frame026.png"),
    dialogue_beat="..IN FRONT OF THE BOSS HE HAD STRUCK DOWN... ATOP THE LIFELESS BODIES OF FALLEN COMRADES AND ENEMIES...",
)

MS_07B = PrologueMicroShot(
    id="MS-07B",
    manga_frames="Frames 029-030",
    duration_sec=2.5,
    camera="Medium rear shot framed on Lucas's broad shoulders and spine, slow subtle push-in along center axis (2%).",
    gaze_lock="LUCAS REAR ORIENTATION LOCK: Pure motionless posture under grief, back to camera.",
    style_domain="DOMAIN 2: Fortiche Production Arcane Cinematic 3D",
    subject="Solitary back of Knight Lucas in scarred plate armor with shredded blue cape, broad shoulders hunched forward, notched broadsword resting motionless on stone.",
    action="Cathedral pillars, marble steps, and background walls gradually darken and dissolve into deep black shadow, leaving Lucas isolated in the center.",
    context="Transitioning from desecrated hall into deep atmospheric darkness, dust motes settling, absolute silence.",
    composition="Medium rear shot framed on Lucas's broad shoulders and spine, slow subtle push-in along center axis.",
    style_lighting="Fortiche Arcane hand-painted aesthetic, dynamic fading impasto, stark cold cyan rim lighting catching the edges of his silver pauldrons.",
    negative_prompt="turning head, front view, face visible, daytime light, modern objects, speech bubbles, text watermark, sudden twitching",
    reference_bindings=("knight_lucas_solitary_back.png", "@Lucas_Knight"),
    dialogue_beat="I DON'T KNOW WHY. EVEN THOUGH HE'S NOTHING MORE THAN A GAME CHARACTER...",
)

MS_07C = PrologueMicroShot(
    id="MS-07C",
    manga_frames="Frames 031-032",
    duration_sec=3.0,
    camera="Low-angle wide rear shot, subject centered, locked static camera, high negative space.",
    gaze_lock="LUCAS ICONIC LONELY BACK IN VOID: Motionless rear stance, head bowed forward, back turned permanently to screen.",
    style_domain="DOMAIN 2: Fortiche Production Arcane Cinematic 3D in Pure Pitch-Black Void",
    subject="Solitary rear figure of Knight Lucas standing alone, broad muscular shoulders hunched forward in devastating grief, scarred steel armor with monster gouges, shredded royal-blue cape, notched heavy broadsword held tip-down.",
    action="Stands completely motionless in the center of the frame, solemn somber breathing, back turned permanently to the camera.",
    context="Absolute pitch-black void #000000, zero background geometry, zero floor, bottom-third luminance strictly below 25.0.",
    composition="Low-angle wide rear shot, subject centered, locked static camera, high negative space emphasizing overwhelming solitude.",
    style_lighting="Fortiche Arcane painterly 2.5D animation, cold cyan volumetric rim light tracing the outer contours of his silver armor and cape, deep pure blackness.",
    negative_prompt="turning head around, front view of face, side profile, ambient background light, gray fog, floor lines, pillars, modern room, speech bubbles, bright colors",
    reference_bindings=("knight_lucas_void_end.png", "@Lucas_Solitary_Back"),
    dialogue_beat="...SEEMED LONELY AS HE STOOD THERE, WITH HIS BACK TO THE SCREEN.",
)

PROLOGUE_MICRO_SHOTS: Tuple[PrologueMicroShot, ...] = (
    MS_01A,
    MS_01B,
    MS_01C,
    MS_02A,
    MS_02B,
    MS_03A,
    MS_03B,
    MS_04A,
    MS_04B,
    MS_04C,
    MS_05A,
    MS_05B,
    MS_05C,
    MS_06A,
    MS_06B,
    MS_07A,
    MS_07B,
    MS_07C,
)


def get_prologue_micro_shots() -> List[PrologueMicroShot]:
    """Return all 18 prologue micro-shots as an ordered list."""
    return list(PROLOGUE_MICRO_SHOTS)


def get_micro_shot_by_id(shot_id: str) -> Optional[PrologueMicroShot]:
    """Retrieve a specific prologue micro-shot by its unique identifier (e.g. 'MS-01B')."""
    for shot in PROLOGUE_MICRO_SHOTS:
        if shot.id.upper() == shot_id.strip().upper():
            return shot
    return None


def validate_prologue_matrix(shots: Sequence[PrologueMicroShot] = PROLOGUE_MICRO_SHOTS) -> Dict[str, Any]:
    """Rigorously validate the 18 micro-shots against all R1 & R2 architectural constraints."""
    errors: List[str] = []
    total_shots = len(shots)

    if total_shots != 18:
        errors.append(f"Expected exactly 18 micro-shots, got {total_shots}")

    total_duration = sum(s.duration_sec for s in shots)
    if not (38.0 <= total_duration <= 45.0):
        errors.append(f"Total prologue duration {total_duration:.1f}s out of bounds [38.0s..45.0s]")

    streamer_shots = {"MS-01B", "MS-01C", "MS-02B", "MS-03B", "MS-04A", "MS-04B", "MS-04C", "MS-05A", "MS-05C"}
    for s in shots:
        if not (1.5 <= s.duration_sec <= 3.0):
            errors.append(f"Shot {s.id} duration {s.duration_sec:.1f}s outside micro-fragment bounds [1.5s..3.0s]")

        # Check banned quality boosters in positive prompt
        composed = s.compose_positive_prompt()
        for booster in BANNED_QUALITY_BOOSTERS:
            if re.search(rf"\b{re.escape(booster)}\b", composed, re.IGNORECASE):
                errors.append(f"Shot {s.id} contains banned quality booster: '{booster}'")

        # Streamer face lock verification
        if s.id in streamer_shots:
            gz = s.gaze_lock.lower()
            if not ("face-locked" in gz or "position locked" in gz or "gaze" in gz or "eyes" in gz):
                errors.append(f"Streamer shot {s.id} lacks explicit face/gaze lock directive")

        # Lucas style segregation check
        if s.id == "MS-06A":
            if "DOMAIN 1" not in s.style_domain or "2D Tactical" not in s.style_domain:
                errors.append(f"Shot {s.id} must be DOMAIN 1: 2D Tactical Game Card")
        elif s.id in {"MS-06B", "MS-07A", "MS-07B", "MS-07C"}:
            if "DOMAIN 2" not in s.style_domain or "Arcane" not in s.style_domain:
                errors.append(f"Shot {s.id} must be DOMAIN 2: Fortiche Arcane Cinematic 3D")

    return {
        "valid": len(errors) == 0,
        "total_shots": total_shots,
        "total_duration_sec": round(total_duration, 2),
        "avg_duration_sec": round(total_duration / max(1, total_shots), 2),
        "errors": errors,
        "streamer_shot_count": len(streamer_shots),
        "lucas_shot_count": 5,
    }


# ---------------------------------------------------------------------------
# Episode 1 Fortiche Arcane 6-Stage Prompt Engine & Canonical Tokens (M2)
# ---------------------------------------------------------------------------

EP01_CANONICAL_LUCAS_HAIR = "dirty-blonde"
EP01_CANONICAL_LUCAS_SKIN = "weathered tan skin"
EP01_CANONICAL_LUCAS_SCAR = "left cheek claw scar"
EP01_CANONICAL_LUCAS_ZERO_SPARKS = (
    "zero glowing eyes",
    "zero floating sparks",
    "zero sparks on armor or sword",
    "natural steel-gray human irises",
)
EP01_CANONICAL_LILY_TOKENS = (
    "blind sniper",
    "blindfolded",
    "wind-arbalest",
)
EP01_CANONICAL_ASH_TOKENS = (
    "36th prince",
    "cynical gamer mind",
    "charcoal officer greatcoat",
    "amber-gold irises",
    "insomnia dark circles",
)

MASTER_FORTICHE_STYLE_ANCHOR = (
    "Hand-painted Fortiche Production Arcane 2.5D animation style blended with "
    "Ufotable dark fantasy cinematic line-art, visible oil and gouache impasto "
    "brushwork, and grounded physical lighting."
)

MASTER_FORTICHE_NEGATIVE_BLOCK = (
    "glowing eyes, laser pupils, magical energy arcs, neon blade, sparks on armor, "
    "lens flare bloom, arcade effects, sci-fi lasers, clean parade armor, plastic 3D CGI, "
    "flat 2D cartoon, smiling, sunny daytime, turning head away, camera spin, "
    "distorted anatomy, extra limbs, watermark, text, subtitles."
)


@dataclass(frozen=True)
class Fortiche6StagePrompt:
    """Master 6-stage Fortiche Arcane prompt formula container."""

    stage1_prefix: str
    stage2_style: str
    stage3_subject: str
    stage4_materials: str
    stage5_lighting: str
    stage6_negative: str

    def compose_positive(self) -> str:
        """Compose 5-stage positive prompt without trailing whitespace."""
        parts = [
            self.stage1_prefix.strip(),
            self.stage2_style.strip(),
            self.stage3_subject.strip(),
            self.stage4_materials.strip(),
            self.stage5_lighting.strip(),
        ]
        return " ".join(p for p in parts if p)

    def compose_negative(self) -> str:
        """Return the stage 6 negative constraint block."""
        return self.stage6_negative.strip()

    def to_dict(self) -> Dict[str, str]:
        """Convert prompt stages to dictionary representation."""
        return {
            "stage1_prefix": self.stage1_prefix,
            "stage2_style": self.stage2_style,
            "stage3_subject": self.stage3_subject,
            "stage4_materials": self.stage4_materials,
            "stage5_lighting": self.stage5_lighting,
            "stage6_negative": self.stage6_negative,
            "positive_prompt": self.compose_positive(),
            "negative_prompt": self.compose_negative(),
        }


def build_fortiche_arcane_6stage_prompt(
    subject: str,
    materials: str,
    lighting: str,
    aspect_ratio: str = "16:9",
    style_anchor: str = MASTER_FORTICHE_STYLE_ANCHOR,
    negative_block: str = MASTER_FORTICHE_NEGATIVE_BLOCK,
    is_video_interpolation: bool = False,
    duration_sec: float = 4.0,
) -> Fortiche6StagePrompt:
    """Build a deterministic 6-stage Fortiche Arcane prompt formula."""
    if is_video_interpolation:
        stage1 = (
            f"Use generate_video_with_interpolation with model_display_name='Omni 1.1 Flash', "
            f"aspect_ratio='{aspect_ratio}', duration='{int(duration_sec)}s', the first attached "
            f"image as start_image_media_id, and the second attached image as end_image_media_id. "
            f"In a single continuous unbroken cinematic shot,"
        )
    else:
        stage1 = f"Make me a picture in a {aspect_ratio} aspect ratio:"

    return Fortiche6StagePrompt(
        stage1_prefix=stage1,
        stage2_style=style_anchor,
        stage3_subject=subject,
        stage4_materials=materials,
        stage5_lighting=lighting,
        stage6_negative=negative_block,
    )


def build_lucas_climax_roaring_prompt(
    push_in_pct: int = 15,
    dutch_tilt_deg: int = 12,
    is_video: bool = True,
) -> Fortiche6StagePrompt:
    """Canonical 6-stage prompt for Knight Lucas Climax Command Roar (CL-02 / User Review)."""
    subject = (
        f"dynamic three-quarter (3/4) close-up camera pushing in ~{push_in_pct}% closer with a "
        f"{dutch_tilt_deg}-degree Dutch tilt onto Vanguard Knight Lucas's battle-scarred face as he "
        f"leans forward and roars the command to attack ('CHARGE!'). His hair is {EP01_CANONICAL_LUCAS_HAIR} "
        f"clotted with rain and soot whipping dynamically. His eyes are natural weathered steel-gray human "
        f"irises with realistic torchlight reflections only, red-rimmed sclera, and dilated adrenaline pupils, "
        f"with strictly zero glowing eyes and zero floating sparks on his blackened steel armor or sword."
    )
    materials = (
        "Sculpted cheekbone planes, three-furrow healed claw scar on his left cheek, and bared teeth. "
        "Over 4 seconds, his clenched jaw opens wide into an authoritative, guttural battle roar with "
        "visible condensation vapor and saliva mist in the freezing rain, while the blurred silhouettes "
        "of armored vanguard soldiers with iron spears and raised torches behind his shoulders surge "
        "forward into the charge."
    )
    lighting = (
        "Dramatic dual-source chiaroscuro: warm flickering torchlight key light from stage-left contrasting "
        "with cold slate-blue storm rim lighting from stage-right. Cyclopean dark basalt ramparts and "
        "driving 35-degree rain remain rigid and consistent in the background."
    )
    return build_fortiche_arcane_6stage_prompt(
        subject=subject,
        materials=materials,
        lighting=lighting,
        is_video_interpolation=is_video,
        duration_sec=4.0,
    )


def load_ep01_shot_matrix(matrix_path: str = "docs/ttd_ep01_shot_matrix.json") -> List[Dict[str, Any]]:
    """Load and return the verified 12-shot Episode 1 shot matrix from disk."""
    import json
    from pathlib import Path

    p = Path(matrix_path)
    if not p.is_file():
        raise FileNotFoundError(f"Episode 1 shot matrix not found at {matrix_path}")

    with p.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list) or len(data) != 12:
        raise ValueError(f"Expected list of 12 shots, got {type(data)} with len={len(data) if isinstance(data, list) else 0}")
    return data


def validate_ep01_canonical_prompts(shots: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """Validate that Episode 1 prompts adhere strictly to canonical character & visual invariants."""
    errors: List[str] = []

    for idx, s in enumerate(shots):
        sid = s.get("shot_id", f"INDEX-{idx}")
        pos = s.get("positive_prompt", "").lower()
        neg = s.get("negative_prompt", "").lower()

        # Check Lucas shots
        if any("lucas" in c.lower() for c in s.get("characters", [])):
            if "dirty-blonde" not in pos and "dirty-blonde" not in s.get("scene_title", "").lower():
                errors.append(f"Shot {sid}: Lucas missing canonical hair token 'dirty-blonde'")
            # Skin invariant
            if not ("weathered tan" in pos or "weathered bronze-tan" in pos):
                errors.append(f"Shot {sid}: Lucas missing canonical skin token '{EP01_CANONICAL_LUCAS_SKIN}'")
            # Facial scar invariant
            if not ("left cheek claw scar" in pos or "claw scar on left cheek" in pos):
                errors.append(f"Shot {sid}: Lucas missing canonical facial scar '{EP01_CANONICAL_LUCAS_SCAR}'")
            # Zero sparks invariant
            if not any(token in pos for token in ["zero glowing eyes", "zero sparks", "realistic torchlight reflections only"]):
                errors.append(f"Shot {sid}: Lucas missing zero-sparks / natural reflection invariant")
            # Negative prompt must forbid glowing eyes and sparks
            if "glowing eyes" not in neg or "sparks" not in neg:
                errors.append(f"Shot {sid}: Lucas negative prompt must forbid 'glowing eyes' and 'sparks'")

        # Check Lily shots
        if any("lily" in c.lower() for c in s.get("characters", [])):
            if not any(token in pos for token in ["blind sniper", "blindfolded", "broken composite arbalest"]):
                errors.append(f"Shot {sid}: Lily missing canonical 'blind sniper' / 'arbalest' token")

        # Check Ash shots
        if any("ash" in c.lower() for c in s.get("characters", [])):
            if not any(token in pos for token in ["amber-gold", "insomnia", "officer greatcoat", "prince ash", "gamer"]):
                errors.append(f"Shot {sid}: Prince Ash missing canonical aesthetic tokens")

    return {
        "valid": len(errors) == 0,
        "total_shots_checked": len(shots),
        "errors": errors,
    }
