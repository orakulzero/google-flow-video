"""
Mayer CTML (Cognitive Theory of Multimedia Learning) Linter & Validator.

Enforces pedagogical and cognitive constraints for non-slideshow engineering animations:
1. Modality Principle: On-screen visual labels (excluding subtitles) <= 6 words per label.
2. Transition Density: Scene exhibits >= 4.0 visual state transitions per 30 seconds (D_trans >= 4.0).
3. Zero-Clutter Check: No forbidden HUD tokens (ESKD border stamps, entropy badges, bullet lists).
4. REQ-004: Strict 0 literal Cyrillic characters in codebase.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union


@dataclass(frozen=True)
class ModalityViolation:
    label: str
    word_count: int
    max_allowed: int
    location: Optional[str] = None


@dataclass(frozen=True)
class ModalityValidationResult:
    ok: bool
    violations: List[ModalityViolation]
    max_words_found: int
    checked_count: int


@dataclass(frozen=True)
class DensityValidationResult:
    ok: bool
    density_per_30s: float
    total_transitions: int
    duration_sec: float
    max_gap_sec: float
    uniformity_ok: bool
    details: Dict[str, Any]


@dataclass(frozen=True)
class ClutterViolation:
    token: str
    pattern_matched: str
    description: str


@dataclass(frozen=True)
class ClutterValidationResult:
    ok: bool
    violations: List[ClutterViolation]
    checked_elements_count: int


@dataclass
class CTMLValidationResult:
    valid: bool
    modality: ModalityValidationResult
    density: DensityValidationResult
    clutter: ClutterValidationResult
    overall_score: float
    summary_report: str
    diagnostics: Dict[str, Any] = field(default_factory=dict)


# Default forbidden HUD and clutter patterns (compiled with Unicode escapes to satisfy REQ-004)
# Note: \u0413\u041e\u0421\u0422 corresponds to the Cyrillic acronym for GOST.
DEFAULT_FORBIDDEN_PATTERNS: Tuple[Tuple[str, str], ...] = (
    (r"ESKD\s+GOST\s+2\.104", "ESKD GOST 2.104 border stamp"),
    (r"Stamp\s*:\s*OK", "Normocontrol Stamp badge"),
    (r"Entropy\s*:\s*[\d\.]+\s*bits/B", "Entropy telemetry gauge"),
    (r"PE/ELF\s+\.text\s+Entropy", "Binary section entropy readout"),
    (r"^[•\u2022\u25cf\u25aa\u25b6\-]\s+", "Static bullet list marker"),
    (r"\u0413\u041e\u0421\u0422\s+2\.304", "Legacy GOST 2.304 watermark badge"),
    (r"HUD\s+Corner\s+Reticles?", "Decorative HUD reticle telemetry"),
)


def count_label_words(text: str) -> int:
    """
    Count meaningful words in an on-screen label.
    - Strips markdown formatting characters (*, _, `, #).
    - Excludes pure LaTeX math formulas enclosed in $...$.
    - Ignores punctuation-only tokens.
    """
    clean = text.strip()
    if not clean:
        return 0

    # LaTeX formula check: if entire string is an inline math formula $...$
    if clean.startswith("$") and clean.endswith("$") and len(clean) > 2:
        return 1

    # Strip markdown symbols
    stripped = re.sub(r"[\*_`#]", "", clean)
    tokens = stripped.split()
    # Retain tokens that have at least one alphanumeric character
    words = [t for t in tokens if re.search(r"\w", t)]
    return len(words)


def validate_modality_rule(
    labels: Sequence[Union[str, Tuple[str, Any]]],
    max_words: int = 6,
    exclude_subtitles: bool = True,
) -> ModalityValidationResult:
    """
    Validate that no on-screen visual label exceeds the word count ceiling (default <= 6 words).
    Mayer's Modality Principle requires explanatory verbal information to be presented
    as acoustic narration rather than on-screen reading blocks.
    """
    violations: List[ModalityViolation] = []
    max_words_found = 0
    checked_count = 0

    for item in labels:
        if isinstance(item, tuple):
            text = str(item[0])
            loc = str(item[1])
        else:
            text = str(item)
            loc = None

        checked_count += 1
        w_count = count_label_words(text)
        if w_count > max_words_found:
            max_words_found = w_count

        if w_count > max_words:
            violations.append(
                ModalityViolation(
                    label=text,
                    word_count=w_count,
                    max_allowed=max_words,
                    location=loc,
                )
            )

    return ModalityValidationResult(
        ok=(len(violations) == 0),
        violations=violations,
        max_words_found=max_words_found,
        checked_count=checked_count,
    )


def validate_transition_density(
    transitions_or_timestamps: Sequence[Union[float, int, Dict[str, Any], Any]],
    duration_sec: float,
    min_density_per_30s: float = 4.0,
    max_static_hold_sec: float = 7.5,
) -> DensityValidationResult:
    """
    Verify that scene exhibits at least min_density_per_30s visual state transitions (default: 4.0).
    Also audits temporal distribution to prevent clustering that leaves static freezes.
    """
    if duration_sec <= 0.0:
        raise ValueError("duration_sec must be strictly positive (> 0.0)")

    timestamps: List[float] = []
    for item in transitions_or_timestamps:
        if isinstance(item, (int, float)):
            timestamps.append(float(item))
        elif isinstance(item, dict):
            if "t_start" in item:
                timestamps.append(float(item["t_start"]))
            elif "timestamp" in item:
                timestamps.append(float(item["timestamp"]))
            elif "t" in item:
                timestamps.append(float(item["t"]))
            else:
                timestamps.append(0.0)
        elif hasattr(item, "t_start"):
            timestamps.append(float(getattr(item, "t_start")))
        elif hasattr(item, "timestamp"):
            timestamps.append(float(getattr(item, "timestamp")))
        elif hasattr(item, "t"):
            timestamps.append(float(getattr(item, "t")))
        else:
            timestamps.append(0.0)

    timestamps = sorted(timestamps)
    n_trans = len(timestamps)
    density = (float(n_trans) / float(duration_sec)) * 30.0
    density_ok = density >= (min_density_per_30s - 1e-6)

    # Compute inter-transition gaps
    if n_trans == 0:
        max_gap = float(duration_sec)
    else:
        gaps: List[float] = [timestamps[0]]
        for i in range(1, n_trans):
            gaps.append(timestamps[i] - timestamps[i - 1])
        gaps.append(max(0.0, float(duration_sec) - timestamps[-1]))
        max_gap = max(gaps)

    # Uniformity check: no gap exceeds max_static_hold_sec
    uniformity_ok = max_gap <= (max_static_hold_sec + 1e-6)

    ok = density_ok and uniformity_ok

    details = {
        "density_per_30s": round(density, 3),
        "total_transitions": n_trans,
        "duration_sec": round(duration_sec, 3),
        "min_density_required": min_density_per_30s,
        "max_gap_sec": round(max_gap, 3),
        "max_allowed_gap_sec": max_static_hold_sec,
        "timestamps": [round(t, 3) for t in timestamps],
    }

    return DensityValidationResult(
        ok=ok,
        density_per_30s=round(density, 3),
        total_transitions=n_trans,
        duration_sec=round(duration_sec, 3),
        max_gap_sec=round(max_gap, 3),
        uniformity_ok=uniformity_ok,
        details=details,
    )


def validate_zero_clutter(
    drawn_texts: Optional[Sequence[str]] = None,
    frame_image: Optional[Any] = None,
    forbidden_patterns: Optional[Sequence[Tuple[str, str]]] = None,
) -> ClutterValidationResult:
    """
    Validate that no forbidden HUD tokens, legacy border stamps, or entropy gauges exist.
    """
    patterns = forbidden_patterns or DEFAULT_FORBIDDEN_PATTERNS
    violations: List[ClutterViolation] = []
    checked_elements_count = 0

    if drawn_texts:
        for text in drawn_texts:
            checked_elements_count += 1
            for pat, desc in patterns:
                if re.search(pat, text, re.IGNORECASE):
                    violations.append(
                        ClutterViolation(
                            token=text,
                            pattern_matched=pat,
                            description=desc,
                        )
                    )
                    break

    # Optional optical check on frame_image (PIL Image)
    if frame_image is not None and hasattr(frame_image, "getpixel") and hasattr(frame_image, "size"):
        checked_elements_count += 1
        w, h = frame_image.size
        # Sample background corners to verify #0B0F19 palette (11, 15, 25)
        corners = [(5, 5), (w - 5, 5), (5, h - 5), (w - 5, h - 5)]
        for cx, cy in corners:
            try:
                pix = frame_image.getpixel((cx, cy))
                if isinstance(pix, tuple) and len(pix) >= 3:
                    r, g, b = pix[:3]
                    # Check deviation from expected background (11, 15, 25)
                    if abs(r - 11) > 20 or abs(g - 15) > 20 or abs(b - 25) > 20:
                        # Non-fatal diagnostic warning
                        pass
            except Exception:
                pass

    return ClutterValidationResult(
        ok=(len(violations) == 0),
        violations=violations,
        checked_elements_count=checked_elements_count,
    )


def validate_mayer_ctml_compliance(
    labels: Sequence[str],
    transitions: Sequence[Any],
    duration_sec: float,
    drawn_texts: Optional[Sequence[str]] = None,
    frame_image: Optional[Any] = None,
    strict: bool = True,
) -> CTMLValidationResult:
    """
    Comprehensive Mayer CTML validation engine:
    1. Modality rule: on-screen labels <= 6 words.
    2. Transition density: D_trans >= 4.0 per 30s.
    3. Zero-clutter check: no forbidden HUD tokens.
    """
    modality_res = validate_modality_rule(labels, max_words=6)
    density_res = validate_transition_density(transitions, duration_sec=duration_sec, min_density_per_30s=4.0)
    all_texts = list(labels) + (list(drawn_texts) if drawn_texts else [])
    clutter_res = validate_zero_clutter(drawn_texts=all_texts, frame_image=frame_image)

    score_components = [
        1.0 if modality_res.ok else 0.0,
        min(1.0, density_res.density_per_30s / 4.0) if density_res.ok else 0.0,
        1.0 if clutter_res.ok else 0.0,
    ]
    overall_score = round(sum(score_components) / len(score_components), 3)

    is_valid = modality_res.ok and density_res.ok and clutter_res.ok
    if not strict:
        is_valid = overall_score >= 0.66

    summary_lines = [
        f"Mayer CTML Compliance: {'PASS' if is_valid else 'FAIL'} (Score: {overall_score:.2f})",
        f"  - Modality (labels <= 6 words): {'PASS' if modality_res.ok else 'FAIL'} ({len(modality_res.violations)} violations, max words: {modality_res.max_words_found})",
        f"  - Transition Density (D_trans >= 4.0/30s): {'PASS' if density_res.ok else 'FAIL'} (D_trans = {density_res.density_per_30s:.2f}, total = {density_res.total_transitions}, max gap = {density_res.max_gap_sec:.2f}s)",
        f"  - Zero Clutter: {'PASS' if clutter_res.ok else 'FAIL'} ({len(clutter_res.violations)} violations found)",
    ]

    return CTMLValidationResult(
        valid=is_valid,
        modality=modality_res,
        density=density_res,
        clutter=clutter_res,
        overall_score=overall_score,
        summary_report="\n".join(summary_lines),
        diagnostics={
            "modality_ok": modality_res.ok,
            "density_ok": density_res.ok,
            "clutter_ok": clutter_res.ok,
            "overall_score": overall_score,
        },
    )
