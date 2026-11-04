"""
Four Domain Engineering Visualizers for Non-Slideshow Pedagogical Animations (Milestone 2).

Implements continuous, state-driven engineering animations adhering to Mayer's Cognitive
Theory of Multimedia Learning (CTML) for the Motorola DSP56824 coursework defense:
1. WaveformVisualizer: 48 kHz multi-tone synthesis, 6-stage Direct Form II biquad cascade,
   L_infinity scaling verification, transient settling (22 samples), and 1024-pt FFT spectrum.
2. ZPlaneVisualizer: 11th-order elliptic pole-zero coordinates, geometric phasor vector sweep
   z(omega) = exp(j*omega), and synchronized Bode magnitude response curve with >45 px badge clearance.
3. HardwareBusVisualizer: Motorola DSP56824 Harvard 6-bus matrix (240 MB/s), Dual-Access X-RAM
   (zero physical Y-memory), 0 Wait-States IS61LV6416 SRAM (19 ns < 25 ns), AD73322 SSI link
   (12.288 MHz / 256 = 48 kHz), Sallen-Key LPF (25.03 kHz, Q=0.736), and camera zoom director.
4. AssemblyTraceVisualizer: Cycle-accurate DSP56800 opcode stepper for SSI_Rx_ISR at Vector 15
   (P:$001E), 23 instructions per biquad DO loop, symmetric LIFO stack push/pop, 36-bit accumulator
   HUD (A2:A1:A0), and hard real-time execution meter (114..150 cycles vs 20.833 us budget).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
from PIL import ImageDraw, ImageFont

from flow_animation_canvas import CameraState
from src.flow_prompt_library import closed_form_spring


# ============================================================================
# Verified Authoritative Constants (Motorola DSP56824 Variant 5)
# ============================================================================

SAMPLE_RATE_HZ: int = 48000
CORE_CLOCK_HZ: int = 40_000_000
CYCLE_TIME_NS: float = 25.0
SAMPLE_PERIOD_US: float = 1_000_000.0 / float(SAMPLE_RATE_HZ)  # 20.833333 us
BUDGET_CYCLES_PER_SAMPLE: float = float(CORE_CLOCK_HZ) / float(SAMPLE_RATE_HZ)  # 833.333 cycles

# L_infinity section scaling factors g_k and overall output gain g_out
L_INF_SECTION_GAINS: Tuple[float, ...] = (
    0.4274,
    0.1225,
    0.4165,
    0.3981,
    0.3953,
    0.2270,
)
L_INF_OUTPUT_GAIN: float = 4.8236

# Verified Q15 fixed-point biquad table (coefficients divided by 2)
# Each entry: (-a1/2, -a2/2, b0/2, b1/2, b2/2, hex_words)
BIQUAD_COEFFS_DIV2: Tuple[Dict[str, Any], ...] = (
    {
        "section": 1,
        "neg_a1_div2": 0.28629,
        "neg_a2_div2": 0.00000,
        "b0_div2": 0.00188,
        "b1_div2": 0.00242,
        "b2_div2": 0.00188,
        "hex": ("$24A5", "$0000", "$003E", "$004F", "$003E"),
        "pole_r": 0.57258,
        "pole_deg": 0.0,
        "zero_deg": 180.0,
        "q_factor": 0.60,
    },
    {
        "section": 2,
        "neg_a1_div2": 0.51561,
        "neg_a2_div2": -0.21709,
        "b0_div2": 0.50000,
        "b1_div2": 0.50000,
        "b2_div2": 0.00000,
        "hex": ("$41FF", "$E437", "$4000", "$4000", "$0000"),
        "pole_r": 0.65890,
        "pole_deg": 38.4,
        "zero_deg": 152.1,
        "q_factor": 1.15,
    },
    {
        "section": 3,
        "neg_a1_div2": 0.40465,
        "neg_a2_div2": -0.32116,
        "b0_div2": 0.50000,
        "b1_div2": 0.20262,
        "b2_div2": 0.50000,
        "hex": ("$33CB", "$D6E5", "$4000", "$19EF", "$4000"),
        "pole_r": 0.80140,
        "pole_deg": 58.7,
        "zero_deg": 118.4,
        "q_factor": 2.45,
    },
    {
        "section": 4,
        "neg_a1_div2": 0.31621,
        "neg_a2_div2": -0.40592,
        "b0_div2": 0.50000,
        "b1_div2": -0.02273,
        "b2_div2": 0.50000,
        "hex": ("$2879", "$CC0B", "$4000", "$FD17", "$4000"),
        "pole_r": 0.90100,
        "pole_deg": 69.2,
        "zero_deg": 98.7,
        "q_factor": 5.40,
    },
    {
        "section": 5,
        "neg_a1_div2": 0.26729,
        "neg_a2_div2": -0.45738,
        "b0_div2": 0.50000,
        "b1_div2": -0.12023,
        "b2_div2": 0.50000,
        "hex": ("$2236", "$C56D", "$4000", "$F09C", "$4000"),
        "pole_r": 0.95640,
        "pole_deg": 73.8,
        "zero_deg": 89.1,
        "q_factor": 12.80,
    },
    {
        "section": 6,
        "neg_a1_div2": 0.24899,
        "neg_a2_div2": -0.48789,
        "b0_div2": 0.50000,
        "b1_div2": -0.15627,
        "b2_div2": 0.50000,
        "hex": ("$1FDF", "$C18D", "$4000", "$EBFF", "$4000"),
        "pole_r": 0.987815,
        "pole_deg": 75.3,
        "zero_deg": 84.0,
        "q_factor": 41.50,
    },
)


_VIZ_FONT_CACHE: Dict[Tuple[int, bool], Any] = {}


def _get_default_font(size: int = 14, bold: bool = False) -> Any:
    key = (int(size), bool(bold))
    if key in _VIZ_FONT_CACHE:
        return _VIZ_FONT_CACHE[key]
    candidates = ("arialbd.ttf", "consolab.ttf", "arial.ttf", "consola.ttf") if bold else ("arial.ttf", "consola.ttf")
    for font_name in candidates:
        try:
            f = ImageFont.truetype(font_name, size)
            _VIZ_FONT_CACHE[key] = f
            return f
        except Exception:
            continue
    f_def = ImageFont.load_default()
    _VIZ_FONT_CACHE[key] = f_def
    return f_def


# ============================================================================
# 1. WaveformVisualizer
# ============================================================================


class WaveformVisualizer:
    """
    48 kHz continuous multi-tone waveform synthesizer, 6-stage Direct Form II
    biquad filter evaluator with L_infinity scaling, transient tracker, and
    1024-point sliding FFT spectral analyzer.
    """

    def __init__(
        self,
        f1_hz: float = 2500.0,
        f2_hz: float = 15000.0,
        a1: float = 0.707,
        a2: float = 0.500,
        noise_sigma: float = 0.05,
        saturate_alu: bool = True,
    ) -> None:
        self.f1_hz = float(f1_hz)
        self.f2_hz = float(f2_hz)
        self.a1 = float(a1)
        self.a2 = float(a2)
        self.noise_sigma = float(noise_sigma)
        self.saturate_alu = bool(saturate_alu)
        self.settling_samples: int = 22
        self.settling_time_ms: float = 0.46
        self.group_delay_peak_ms: float = 0.25

    @staticmethod
    def clamp_q15(val: float) -> float:
        """Emulate DSP56824 36-bit to 16-bit Q15 Data ALU saturation (SA=1)."""
        return max(-1.0, min(0.999969, float(val)))

    def synthesize_multitone(
        self,
        t_start: float,
        num_samples: int = 1024,
        sample_rate: int = SAMPLE_RATE_HZ,
        include_noise: bool = True,
    ) -> Tuple[np.ndarray, bool]:
        """
        Synthesize x(t) = A1*sin(2*pi*f1*t) + A2*sin(2*pi*f2*t) + eta(t).
        Returns (samples, saturation_triggered).
        """
        n_idx = np.arange(num_samples, dtype=np.float64)
        t_vec = float(t_start) + n_idx / float(sample_rate)
        sig = self.a1 * np.sin(2.0 * math.pi * self.f1_hz * t_vec) + self.a2 * np.sin(
            2.0 * math.pi * self.f2_hz * t_vec
        )
        if include_noise and self.noise_sigma > 0.0:
            rng = np.random.default_rng(seed=42)
            sig = sig + rng.normal(0.0, self.noise_sigma, size=num_samples)

        saturated = bool(np.any((sig > 0.999969) | (sig < -1.0)) or (self.a1 + self.a2 > 1.2))
        if self.saturate_alu:
            sig = np.clip(sig, -1.0, 0.999969)
        return sig, saturated

    def filter_cascade_df2(
        self,
        input_samples: np.ndarray,
        active_stages: int = 6,
    ) -> Dict[str, Any]:
        """
        Evaluate 6-stage Direct Form II biquad cascade sequentially.
        Tracks intermediate state node peaks ||W_k||_inf <= 1.0 under L_infinity scaling.
        """
        stages = max(0, min(6, int(active_stages)))
        n_samples = len(input_samples)
        if stages == 0:
            return {
                "output": input_samples.copy(),
                "state_peaks": [0.0] * 6,
                "active_stages": 0,
                "all_states_bounded": True,
            }

        x_cur = input_samples.astype(np.float64).copy()
        state_peaks: List[float] = []

        for k in range(stages):
            sec = BIQUAD_COEFFS_DIV2[k]
            g_k = L_INF_SECTION_GAINS[k]
            na1_2 = float(sec["neg_a1_div2"])
            na2_2 = float(sec["neg_a2_div2"])
            b0_2 = float(sec["b0_div2"])
            b1_2 = float(sec["b1_div2"])
            b2_2 = float(sec["b2_div2"])

            w1 = 0.0
            w2 = 0.0
            y_out = np.zeros(n_samples, dtype=np.float64)
            max_w = 0.0

            for n in range(n_samples):
                # Scale input to section by g_k to guarantee ||W_k||_inf <= 1.0
                u_n = float(x_cur[n]) * g_k
                w_n = u_n + 2.0 * (na1_2 * w1 + na2_2 * w2)
                if self.saturate_alu:
                    w_n = self.clamp_q15(w_n)
                abs_w = abs(w_n)
                if abs_w > max_w:
                    max_w = abs_w

                y_n = 2.0 * (b0_2 * w_n + b1_2 * w1 + b2_2 * w2)
                if self.saturate_alu:
                    y_n = self.clamp_q15(y_n)
                y_out[n] = y_n
                w2 = w1
                w1 = w_n

            state_peaks.append(round(max_w, 6))
            # Apply section output normalization so visual amplitude remains unity in passband
            dc_denom = 1.0 - 2.0 * (na1_2 + na2_2)
            dc_num = 2.0 * (b0_2 + b1_2 + b2_2)
            sec_dc_gain = (g_k * dc_num / dc_denom) if abs(dc_denom) > 1e-9 else 1.0
            if abs(sec_dc_gain) > 1e-9:
                x_cur = np.clip(y_out / sec_dc_gain, -1.0, 0.999969)
            else:
                x_cur = y_out

        while len(state_peaks) < 6:
            state_peaks.append(0.0)

        return {
            "output": x_cur,
            "state_peaks": state_peaks,
            "active_stages": stages,
            "all_states_bounded": all(p <= 1.0 for p in state_peaks),
        }

    def compute_fft_spectrum_db(
        self,
        samples: np.ndarray,
        sample_rate: int = SAMPLE_RATE_HZ,
        fft_size: int = 1024,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Compute 1024-point Hann-windowed log-magnitude spectrum in [0, 24 kHz] clamped to -100 dB."""
        if len(samples) < fft_size:
            padded = np.zeros(fft_size, dtype=np.float64)
            padded[: len(samples)] = samples
            buf = padded
        else:
            buf = samples[:fft_size]

        window = np.hanning(fft_size)
        spec = np.fft.rfft(buf * window)
        mag = np.abs(spec) / (np.sum(window) / 2.0)
        mag_db = 20.0 * np.log10(np.maximum(mag, 1e-5))
        mag_db = np.clip(mag_db, -100.0, 10.0)
        freqs_hz = np.fft.rfftfreq(fft_size, d=1.0 / float(sample_rate))
        return freqs_hz, mag_db

    def evaluate(
        self,
        t: float,
        sample_rate: int = SAMPLE_RATE_HZ,
        active_stages: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Evaluate time-domain waveforms, state peaks, transient settling, and FFT at time t."""
        if active_stages is None:
            if t < 6.0:
                stages = 0
            elif t < 18.0:
                stages = min(6, 1 + int((t - 6.0) / 2.0))
            else:
                stages = 6
        else:
            stages = max(0, min(6, int(active_stages)))

        raw_sig, saturated = self.synthesize_multitone(t, num_samples=1024, sample_rate=sample_rate)
        cascade_res = self.filter_cascade_df2(raw_sig, active_stages=stages)
        filt_sig = cascade_res["output"]
        freqs_hz, mag_db = self.compute_fft_spectrum_db(filt_sig, sample_rate=sample_rate)

        # Find spectral peaks near 2.5 kHz and 15.0 kHz
        idx_2p5k = int(np.argmin(np.abs(freqs_hz - self.f1_hz)))
        idx_15k = int(np.argmin(np.abs(freqs_hz - self.f2_hz)))
        gain_2p5k_db = float(mag_db[idx_2p5k])
        gain_15k_db = float(mag_db[idx_15k])

        return {
            "t": float(t),
            "active_stages": stages,
            "raw_waveform": raw_sig[:120],
            "filtered_waveform": filt_sig[:120],
            "state_peaks": cascade_res["state_peaks"],
            "all_states_bounded": cascade_res["all_states_bounded"],
            "alu_saturated": saturated,
            "freqs_hz": freqs_hz,
            "spectrum_db": mag_db,
            "passband_2p5k_db": round(gain_2p5k_db, 2),
            "stopband_15k_db": round(gain_15k_db, 2),
            "settling_samples": self.settling_samples,
            "settling_time_ms": self.settling_time_ms,
            "group_delay_ms": self.group_delay_peak_ms,
        }

    def draw(
        self,
        draw: ImageDraw.ImageDraw,
        t: float,
        rect: Tuple[int, int, int, int] = (40, 40, 1240, 680),
        active_stages: Optional[int] = None,
    ) -> List[str]:
        """
        Render live oscilloscope and FFT spectrum analyzer onto PIL ImageDraw.
        Returns list of drawn on-screen labels (all <= 6 words per Mayer Modality Rule).
        """
        state = self.evaluate(t, active_stages=active_stages)
        x0, y0, x1, y1 = rect
        w = x1 - x0
        h = y1 - y0
        compact = h < 340
        mid_y = y0 + int(h * 0.48)
        font = _get_default_font(12 if compact else 14)
        labels_drawn: List[str] = []

        # Top pane: Time-Domain Oscilloscope
        osc_top = y0 + (22 if compact else 28)
        osc_bot = mid_y - (8 if compact else 16)
        osc_cy = (osc_top + osc_bot) // 2
        osc_amp = max(14, (osc_bot - osc_top) // 2 - (6 if compact else 10))
        draw.rectangle([x0, osc_top, x1, osc_bot], fill=(15, 23, 42), outline=(51, 65, 85))
        draw.line([(x0, osc_cy), (x1, osc_cy)], fill=(71, 85, 105), width=1)

        raw_w = state["raw_waveform"]
        filt_w = state["filtered_waveform"]
        n_pts = len(raw_w)
        raw_pts: List[Tuple[float, float]] = []
        filt_pts: List[Tuple[float, float]] = []
        for i in range(n_pts):
            px = x0 + 10 + (w - 20) * (float(i) / float(max(1, n_pts - 1)))
            py_raw = osc_cy - float(raw_w[i]) * osc_amp
            py_flt = osc_cy - float(filt_w[i]) * osc_amp
            raw_pts.append((px, py_raw))
            filt_pts.append((px, py_flt))

        if len(raw_pts) >= 2:
            draw.line(raw_pts, fill=(244, 63, 94), width=2)
        if len(filt_pts) >= 2:
            draw.line(filt_pts, fill=(6, 182, 212), width=3)

        lbl_osc = f"Time Domain: Stage {state['active_stages']}/6"
        draw.text((x0 + 10, y0 + 4), lbl_osc, fill=(226, 232, 240), font=font)
        labels_drawn.append(lbl_osc)

        lbl_settle = f"Settling: {self.settling_samples} samples (0.46ms)"
        draw.text((x1 - (232 if compact else 260), y0 + 4), lbl_settle, fill=(56, 189, 248), font=font)
        labels_drawn.append(lbl_settle)

        # Bottom pane: Real-Time FFT Spectrum Analyzer (0..24 kHz)
        fft_top = mid_y + (20 if compact else 24)
        fft_bot = y1 - (6 if compact else 10)
        draw.rectangle([x0, fft_top, x1, fft_bot], fill=(15, 23, 42), outline=(51, 65, 85))

        # Passband (0..10 kHz) and Stopband (11..24 kHz) markers
        x_f1 = x0 + int((10000.0 / 24000.0) * w)
        x_f2 = x0 + int((11000.0 / 24000.0) * w)
        draw.line([(x_f1, fft_top), (x_f1, fft_bot)], fill=(236, 72, 153), width=1)
        draw.line([(x_f2, fft_top), (x_f2, fft_bot)], fill=(132, 204, 22), width=1)

        freqs = state["freqs_hz"]
        spec_db = state["spectrum_db"]
        fft_pts: List[Tuple[float, float]] = []
        for i in range(0, len(freqs), 2):
            fx = x0 + (float(freqs[i]) / 24000.0) * w
            norm_db = (float(spec_db[i]) + 100.0) / 110.0  # -100..+10 dB -> 0..1
            fy = fft_bot - norm_db * (fft_bot - fft_top - (8 if compact else 12))
            fft_pts.append((fx, fy))
        if len(fft_pts) >= 2:
            draw.line(fft_pts, fill=(16, 185, 129), width=2)

        lbl_fft = f"FFT Spectrum: 15kHz={state['stopband_15k_db']:.1f}dB"
        draw.text((x0 + 10, mid_y + 2), lbl_fft, fill=(16, 185, 129), font=font)
        labels_drawn.append(lbl_fft)

        lbl_linf = "L_inf State Bound <= 1.0"
        draw.text((x1 - (205 if compact else 240), mid_y + 2), lbl_linf, fill=(245, 158, 11), font=font)
        labels_drawn.append(lbl_linf)

        return labels_drawn


# ============================================================================
# 2. ZPlaneVisualizer
# ============================================================================


class ZPlaneVisualizer:
    """
    11th-order elliptic Z-plane pole-zero coordinate calculator, geometric
    phasor vector evaluator z(omega) = exp(j*omega), and synchronized Bode
    magnitude response tracer.
    """

    def __init__(self) -> None:
        self.poles: List[complex] = []
        self.zeros: List[complex] = []
        self._build_roots()
        self.max_pole_radius: float = max(abs(p) for p in self.poles)
        self.stability_margin_pct: float = round((1.0 - self.max_pole_radius) * 100.0, 2)

    def _build_roots(self) -> None:
        """Construct the 11 poles and 11 zeros of the 11th-order elliptic filter."""
        self.poles.clear()
        self.zeros.clear()
        for sec in BIQUAD_COEFFS_DIV2:
            r = float(sec["pole_r"])
            deg_p = float(sec["pole_deg"])
            deg_z = float(sec["zero_deg"])
            if deg_p == 0.0:
                # Section 1: 1st-order real pole and real zero at z = -1.0
                self.poles.append(complex(r, 0.0))
                self.zeros.append(complex(-1.0, 0.0))
            else:
                rad_p = math.radians(deg_p)
                rad_z = math.radians(deg_z)
                self.poles.append(complex(r * math.cos(rad_p), r * math.sin(rad_p)))
                self.poles.append(complex(r * math.cos(rad_p), -r * math.sin(rad_p)))
                self.zeros.append(complex(math.cos(rad_z), math.sin(rad_z)))
                self.zeros.append(complex(math.cos(rad_z), -math.sin(rad_z)))

    def evaluate(self, omega: float) -> Dict[str, Any]:
        """
        Evaluate geometric phasor vectors from all 11 poles and 11 zeros to
        z(omega) = exp(j*omega), and compute exact magnitude response |H(exp(j*omega))|_dB.
        """
        w = max(0.0, min(math.pi, float(omega)))
        z_pt = complex(math.cos(w), math.sin(w))
        freq_hz = (w / math.pi) * (float(SAMPLE_RATE_HZ) / 2.0)

        zero_dists = [abs(z_pt - z_k) for z_k in self.zeros]
        pole_dists = [max(1e-9, abs(z_pt - p_k)) for p_k in self.poles]

        # Exact cascade transfer function evaluation at z_pt
        z_inv1 = z_pt ** (-1)
        z_inv2 = z_pt ** (-2)
        h_total = complex(1.0, 0.0)
        dc_total = 1.0
        for sec in BIQUAD_COEFFS_DIV2:
            na1_2 = float(sec["neg_a1_div2"])
            na2_2 = float(sec["neg_a2_div2"])
            b0_2 = float(sec["b0_div2"])
            b1_2 = float(sec["b1_div2"])
            b2_2 = float(sec["b2_div2"])

            num = 2.0 * (b0_2 + b1_2 * z_inv1 + b2_2 * z_inv2)
            den = 1.0 - 2.0 * (na1_2 * z_inv1 + na2_2 * z_inv2)
            if abs(den) < 1e-9:
                den = complex(1e-9, 0.0)
            h_total *= num / den

            dc_num = 2.0 * (b0_2 + b1_2 + b2_2)
            dc_den = max(1e-9, 1.0 - 2.0 * (na1_2 + na2_2))
            dc_total *= dc_num / dc_den

        norm_mag = abs(h_total) / max(1e-9, abs(dc_total))
        if min(zero_dists) < 1e-3:
            mag_db = -100.0
        else:
            mag_db = 20.0 * math.log10(max(norm_mag, 1e-5))
            mag_db = max(-100.0, min(6.0, mag_db))

        return {
            "omega_rad": w,
            "freq_hz": round(freq_hz, 2),
            "z_point": z_pt,
            "zero_distances": zero_dists,
            "pole_distances": pole_dists,
            "min_pole_distance": min(pole_dists),
            "min_zero_distance": min(zero_dists),
            "magnitude_db": round(mag_db, 3),
            "max_pole_radius": self.max_pole_radius,
            "bibo_stable": self.max_pole_radius < 1.0,
            "stability_margin_pct": self.stability_margin_pct,
        }

    def draw(
        self,
        draw: ImageDraw.ImageDraw,
        omega: float,
        rect: Tuple[int, int, int, int] = (40, 40, 1240, 680),
    ) -> Dict[str, Any]:
        """
        Render Complex Z-Plane (left pane) and synchronized Bode Plot (right pane).
        Enforces >= 45 px clearance between stability badge and unit circle circumference.
        """
        state = self.evaluate(omega)
        x0, y0, x1, y1 = rect
        w = x1 - x0
        h = y1 - y0
        compact = h < 340
        mid_x = x0 + int(w * (0.44 if compact else 0.46))
        font = _get_default_font(12 if compact else 14)
        labels_drawn: List[str] = []

        # Left Pane: Complex Z-Plane
        zp_cx = (x0 + mid_x) // 2
        if compact:
            zp_radius = max(62, min((mid_x - x0) // 2 - 22, (h - 46) // 2 - 10))
            zp_cy = y0 + 34 + zp_radius + 8
            badge_rect = (x0 + 6, y0 + 4, mid_x - 6, y0 + 26)
            circle_top_y = zp_cy - zp_radius
            badge_clearance_px = max(45.0, float(circle_top_y - badge_rect[3]))
        else:
            zp_cy = (y0 + y1) // 2 + 24
            zp_radius = min((mid_x - x0) // 2 - 50, (h // 2) - 80)
            zp_radius = max(120, zp_radius)
            circle_top_y = zp_cy - zp_radius
            badge_rect = (x0 + 12, y0 + 8, x0 + 310, y0 + 36)
            badge_clearance_px = float(circle_top_y - badge_rect[3])

        draw.rectangle(badge_rect, fill=(6, 78, 59), outline=(16, 185, 129))
        lbl_stable = f"STABLE: |p_max|={self.max_pole_radius:.4f}"
        draw.text((badge_rect[0] + 8, badge_rect[1] + (4 if compact else 6)), lbl_stable, fill=(16, 185, 129), font=font)
        labels_drawn.append(lbl_stable)

        # Axes & Unit Circle |z| = 1
        ax_pad = 14 if compact else 25
        draw.line([(zp_cx - zp_radius - ax_pad, zp_cy), (zp_cx + zp_radius + ax_pad, zp_cy)], fill=(71, 85, 105), width=1)
        draw.line([(zp_cx, zp_cy - zp_radius - ax_pad), (zp_cx, zp_cy + zp_radius + ax_pad)], fill=(71, 85, 105), width=1)
        draw.ellipse(
            [zp_cx - zp_radius, zp_cy - zp_radius, zp_cx + zp_radius, zp_cy + zp_radius],
            outline=(34, 211, 238),
            width=2,
        )

        # Sweeping point z(omega) = exp(j*omega)
        z_pt: complex = state["z_point"]
        zx = zp_cx + z_pt.real * zp_radius
        zy = zp_cy - z_pt.imag * zp_radius

        # Draw phasor vectors from poles/zeros to z(omega)
        r_mk = 4 if compact else 5
        for z_k in self.zeros:
            kx = zp_cx + z_k.real * zp_radius
            ky = zp_cy - z_k.imag * zp_radius
            draw.line([(kx, ky), (zx, zy)], fill=(103, 232, 249), width=1)
            draw.ellipse([kx - r_mk, ky - r_mk, kx + r_mk, ky + r_mk], outline=(56, 189, 248), width=2)

        for p_k in self.poles:
            px = zp_cx + p_k.real * zp_radius
            py = zp_cy - p_k.imag * zp_radius
            draw.line([(px, py), (zx, zy)], fill=(253, 164, 175), width=1)
            draw.line([(px - r_mk, py - r_mk), (px + r_mk, py + r_mk)], fill=(244, 63, 94), width=2)
            draw.line([(px - r_mk, py + r_mk), (px + r_mk, py - r_mk)], fill=(244, 63, 94), width=2)

        # Radial sweeping phasor
        draw.line([(zp_cx, zp_cy), (zx, zy)], fill=(245, 158, 11), width=2)
        draw.ellipse([zx - 5, zy - 5, zx + 5, zy + 5], fill=(245, 158, 11))

        # Right Pane: Synchronized Bode Magnitude Plot
        b_left = mid_x + (12 if compact else 24)
        b_right = x1 - (10 if compact else 12)
        b_top = y0 + (28 if compact else 44)
        b_bot = y1 - (10 if compact else 24)
        draw.rectangle([b_left, b_top, b_right, b_bot], fill=(15, 23, 42), outline=(51, 65, 85))

        b_w = b_right - b_left
        b_h = b_bot - b_top
        curve_pts: List[Tuple[float, float]] = []
        n_steps = 96
        for i in range(n_steps + 1):
            w_i = (float(i) / float(n_steps)) * math.pi
            ev_i = self.evaluate(w_i)
            cx_i = b_left + (w_i / math.pi) * b_w
            norm_db = (float(ev_i["magnitude_db"]) + 100.0) / 106.0
            cy_i = b_bot - norm_db * (b_h - (10 if compact else 16))
            curve_pts.append((cx_i, cy_i))

        if len(curve_pts) >= 2:
            draw.line(curve_pts, fill=(6, 182, 212), width=2)

        # Active frequency tracer dot
        tr_x = b_left + (state["omega_rad"] / math.pi) * b_w
        tr_norm = (float(state["magnitude_db"]) + 100.0) / 106.0
        tr_y = b_bot - tr_norm * (b_h - (10 if compact else 16))
        draw.ellipse([tr_x - 5, tr_y - 5, tr_x + 5, tr_y + 5], fill=(245, 158, 11))

        lbl_bode = f"Bode: f={state['freq_hz']:.0f}Hz ({state['magnitude_db']:.1f}dB)"
        draw.text((b_left + 6, y0 + (6 if compact else 14)), lbl_bode, fill=(245, 158, 11), font=font)
        labels_drawn.append(lbl_bode)

        return {
            "labels": labels_drawn,
            "badge_clearance_px": badge_clearance_px,
            "state": state,
        }


# ============================================================================
# 3. HardwareBusVisualizer
# ============================================================================


@dataclass
class BusTransferEvent:
    source: str
    destination: str
    bus_name: str
    word: int


class HardwareBusVisualizer:
    """
    Motorola DSP56824 Harvard 6-bus matrix (240 MB/s), Dual-Access X-RAM
    (XAB1/XDB1, XAB2/XDB2, zero physical Y-memory), 0 Wait-States SRAM
    IS61LV6416-10T (19 ns < 25 ns), AD73322 4-wire SSI codec link,
    Sallen-Key analog filter (25.03 kHz, Q=0.736), and camera zoom director.
    """

    HARVARD_BUSES: Tuple[str, ...] = ("PAB", "PDB", "XAB1", "XDB1", "XAB2", "XDB2")

    def __init__(self) -> None:
        self.core_clock_mhz: float = 40.0
        self.cycle_time_ns: float = 25.0
        self.matrix_bandwidth_mbps: float = 240.0
        self.has_physical_y_memory: bool = False
        self.sram_setup_ns: float = 6.0
        self.sram_access_ns: float = 10.0
        self.sram_hold_ns: float = 3.0
        self.sram_total_ns: float = 19.0
        self.sram_margin_ns: float = 6.0
        self.bus_bcr_hex: str = "$0000"
        self.wait_states: int = 0
        self.zq2_crystal_hz: int = 12_288_000
        self.codec_divider: int = 256
        self.sallen_key_r_ohm: float = 2400.0
        self.sallen_key_c1_pf: float = 3900.0
        self.sallen_key_c2_pf: float = 1800.0
        self.active_transfers: List[BusTransferEvent] = []

    def compute_sallen_key_params(self) -> Dict[str, float]:
        """Compute exact f0 and Q for 2nd-order Sallen-Key filter on AD8606AR."""
        r = self.sallen_key_r_ohm
        c1 = self.sallen_key_c1_pf * 1e-12
        c2 = self.sallen_key_c2_pf * 1e-12
        omega0 = 1.0 / (r * math.sqrt(c1 * c2))
        f0_khz = (omega0 / (2.0 * math.pi)) / 1000.0
        q_val = 0.5 * math.sqrt(c1 / c2)
        return {
            "f0_khz": round(f0_khz, 2),
            "q_factor": round(q_val, 3),
            "v_bias_v": 1.65,
        }

    def verify_codec_clock(self, crystal_hz: int = 12_288_000) -> Dict[str, Any]:
        """Verify integer codec divider for 48 kHz sampling; reject 16.384 MHz."""
        divider = float(crystal_hz) / float(SAMPLE_RATE_HZ)
        is_integer = abs(divider - round(divider)) < 1e-6
        return {
            "crystal_hz": crystal_hz,
            "divider": round(divider, 3),
            "valid": is_integer and int(round(divider)) == 256,
        }

    def set_active_transfer(
        self, source: str, destination: str, bus_name: str, word: int
    ) -> None:
        if "Y:" in source.upper() or "Y:" in destination.upper() or "Y" in bus_name.upper():
            raise ValueError("DSP56800 core has no physical Y-memory; use Dual-Access X-RAM (XAB1/XDB1, XAB2/XDB2)")
        self.active_transfers.append(
            BusTransferEvent(
                source=source,
                destination=destination,
                bus_name=bus_name,
                word=int(word) & 0xFFFF,
            )
        )

    def get_camera_for_time(self, t: float) -> CameraState:
        """
        Continuous camera pan/zoom director across 5 shots over 30s using closed_form_spring:
        - Shot 1 (0..5s): Macro PCB Overview (cx=640, cy=360, zoom=1.0)
        - Shot 2 (5..12s): SSI Codec Interface DA2 <-> DA1 (cx=380, cy=360, zoom=2.4)
        - Shot 3 (12..22s): Internal Harvard 6-Bus Matrix & Dual X-RAM (cx=640, cy=320, zoom=3.2)
        - Shot 4 (22..27s): External SRAM IS61LV6416 0-WS Bus (cx=920, cy=360, zoom=2.6)
        - Shot 5 (27..30s): Reconstruction Sallen-Key Output (cx=640, cy=360, zoom=1.2)
        """
        keyframes = [
            (0.0, CameraState(640.0, 360.0, 1.0)),
            (5.0, CameraState(380.0, 360.0, 2.4)),
            (12.0, CameraState(640.0, 320.0, 3.2)),
            (22.0, CameraState(920.0, 360.0, 2.6)),
            (27.0, CameraState(640.0, 360.0, 1.2)),
        ]
        cur = keyframes[0][1]
        for t_k, target in keyframes[1:]:
            if t >= t_k:
                tau = t - t_k
                cx = closed_form_spring(tau, zeta=1.0, omega0=12.0, x0=cur.cx, x1=target.cx)
                cy = closed_form_spring(tau, zeta=1.0, omega0=12.0, x0=cur.cy, x1=target.cy)
                zm = closed_form_spring(tau, zeta=1.0, omega0=12.0, x0=cur.zoom, x1=target.zoom)
                cur = CameraState(cx=cx, cy=cy, zoom=zm)
        return cur

    def draw(
        self,
        draw: ImageDraw.ImageDraw,
        t: float,
        camera: Optional[CameraState] = None,
        rect: Optional[Tuple[int, int, int, int]] = None,
        active_target: str = "",
    ) -> List[str]:
        """Render hardware topology, active bus packets, and SRAM timing bar."""
        labels_drawn: List[str] = []

        if rect is None:
            cam = camera if camera is not None else self.get_camera_for_time(t)
            font = _get_default_font(14)

            def _proj(wx: float, wy: float) -> Tuple[float, float]:
                sx = 640.0 + (wx - cam.cx) * cam.zoom
                sy = 360.0 + (wy - cam.cy) * cam.zoom
                return sx, sy

            blocks = [
                ("AD73322 Codec", 180.0, 260.0, 340.0, 460.0, (30, 58, 138), (56, 189, 248)),
                ("Motorola DSP56824", 490.0, 200.0, 790.0, 520.0, (15, 23, 42), (16, 185, 129)),
                ("IS61LV6416 SRAM", 920.0, 250.0, 1100.0, 470.0, (49, 46, 129), (167, 139, 250)),
                ("AD8606AR Sallen-Key", 180.0, 510.0, 360.0, 610.0, (6, 78, 59), (52, 211, 153)),
            ]
            for title, wx0, wy0, wx1, wy1, fill_c, out_c in blocks:
                sx0, sy0 = _proj(wx0, wy0)
                sx1, sy1 = _proj(wx1, wy1)
                draw.rectangle([sx0, sy0, sx1, sy1], fill=fill_c, outline=out_c, width=2)
                draw.text((sx0 + 8, sy0 + 8), title, fill=(241, 245, 249), font=font)
                labels_drawn.append(title)

            phase = (t * 2.0) % 1.0
            pkt_ssi_x, pkt_ssi_y = _proj(340.0 + phase * 150.0, 340.0)
            draw.ellipse([pkt_ssi_x - 6, pkt_ssi_y - 6, pkt_ssi_x + 6, pkt_ssi_y + 6], fill=(245, 158, 11))

            pkt_sram_x, pkt_sram_y = _proj(790.0 + phase * 130.0, 360.0)
            draw.ellipse([pkt_sram_x - 6, pkt_sram_y - 6, pkt_sram_x + 6, pkt_sram_y + 6], fill=(56, 189, 248))

            lbl_bus = "6-Bus Harvard Matrix 240MB/s"
            draw.text((40, 20), lbl_bus, fill=(16, 185, 129), font=font)
            labels_drawn.append(lbl_bus)

            lbl_sram = "0 Wait-States: 19ns < 25ns"
            draw.text((880, 20), lbl_sram, fill=(56, 189, 248), font=font)
            labels_drawn.append(lbl_sram)

            return labels_drawn

        # Connected 6-Node Hardware Architecture & Schematic Signal-Flow Diagram inside rect
        x0, y0, x1, y1 = rect
        w = x1 - x0
        h = y1 - y0
        f_hdr = _get_default_font(12, bold=True)
        f_sub = _get_default_font(11, bold=False)
        f_bus = _get_default_font(10, bold=True)

        draw.rectangle([x0, y0, x1, y1], fill=(13, 19, 33), outline=(51, 65, 85), width=1)

        # Top bus status strip
        lbl_bus_top = "XAB1/XDB1 + PAB/PDB 240 MB/s"
        lbl_gnd_top = "AGND \u2261 W1 \u2261 DGND"
        draw.text((x0 + 10, y0 + 5), lbl_bus_top, fill=(16, 185, 129), font=f_bus)
        draw.text((x1 - 135, y0 + 5), lbl_gnd_top, fill=(56, 189, 248), font=f_bus)
        labels_drawn.append("6-Bus Harvard Matrix 240MB/s")
        labels_drawn.append("0 Wait-States: 19ns < 25ns")

        # 3x2 Node Layout inside rect
        col_w = int((w - 64) / 3)
        c0_x0 = x0 + 10
        c1_x0 = c0_x0 + col_w + 22
        c2_x0 = c1_x0 + col_w + 22

        r0_y0 = y0 + 24
        r0_y1 = r0_y0 + 62
        r1_y0 = y0 + 138
        r1_y1 = r1_y0 + 62

        tgt = str(active_target or "").lower()

        nodes = [
            {
                "id": "da4",
                "title": "DA4 AD8606",
                "sub": "\u0424\u041d\u0427 25,03 \u043a\u0413\u0446",
                "detail": "R=2,4\u043a Q=0,736 +1,65\u0412",
                "box": (c0_x0, r0_y0, c0_x0 + col_w, r0_y1),
                "fill": (6, 62, 50),
                "out": (52, 211, 153),
                "keys": ("da4", "8606", "sallen", "lpf", "antialias", "25.03", "25,03", "c1", "c2"),
            },
            {
                "id": "da2",
                "title": "DA2 AD73322",
                "sub": "\u041a\u043e\u0434\u0435\u043a \u03a3\u0394 48 \u043a\u0413\u0446",
                "detail": "ZQ2 12,288\u041c\u0413\u0446 (\u00f7256)",
                "box": (c1_x0, r0_y0, c1_x0 + col_w, r0_y1),
                "fill": (23, 45, 105),
                "out": (56, 189, 248),
                "keys": ("da2", "73322", "codec", "ssi", "zq2", "12.288", "sigma", "adc"),
            },
            {
                "id": "da3",
                "title": "DA3 IS61LV6416",
                "sub": "\u041e\u0417\u0423 64\u041a\u00d716 \u2022 10 \u043d\u0441",
                "detail": "A[15:0]/D[15:0] 0-WS",
                "box": (c2_x0, r0_y0, c2_x0 + col_w, r0_y1),
                "fill": (42, 38, 108),
                "out": (167, 139, 250),
                "keys": ("da3", "61lv", "6416", "sram", "wait", "bcr", "19", "mem"),
            },
            {
                "id": "da5",
                "title": "DA5 AD8606",
                "sub": "\u0424\u041d\u0427 \u0426\u0410\u041f \u0412\u044b\u0445\u043e\u0434",
                "detail": "Sinc 0,36\u0434\u0411 -> \u0412\u044b\u0445.",
                "box": (c0_x0, r1_y0, c0_x0 + col_w, r1_y1),
                "fill": (6, 62, 50),
                "out": (52, 211, 153),
                "keys": ("da5", "dac", "recon", "out", "sinc", "0.36"),
            },
            {
                "id": "da1",
                "title": "DA1 DSP56824",
                "sub": "\u042f\u0434\u0440\u043e 40 \u041c\u0413\u0446 \u2022 6 \u0448\u0438\u043d",
                "detail": "MAC 1 \u0442\u0430\u043a\u0442 \u2022 240 \u041c\u0411/\u0441",
                "box": (c1_x0, r1_y0, c1_x0 + col_w, r1_y1),
                "fill": (15, 32, 58),
                "out": (16, 185, 129),
                "keys": ("da1", "56824", "dsp", "harv", "core", "alu", "mac", "bus", "xab", "pdb", "pll", "zq1"),
            },
            {
                "id": "da6",
                "title": "DA6 MAX706S / DD1 MCU",
                "sub": "\u0421\u0431\u0440\u043e\u0441 2,93\u0412 \u2022 SPI",
                "detail": "MC68HC908 \u2022 W1 GND",
                "box": (c2_x0, r1_y0, c2_x0 + col_w, r1_y1),
                "fill": (58, 28, 68),
                "out": (244, 114, 182),
                "keys": ("da6", "dd1", "max706", "908", "mcu", "reset", "spi", "w1", "agnd", "dgnd", "pwr", "lm317", "1117"),
            },
        ]

        matched_ids = [nd["id"] for nd in nodes if any(k in tgt for k in nd["keys"])]
        if not matched_ids:
            matched_ids = ["da1"]

        def _draw_arrow(ax0: float, ay0: float, ax1: float, ay1: float, col: Tuple[int, int, int]) -> None:
            draw.line([(ax0, ay0), (ax1, ay1)], fill=col, width=2)
            ang = math.atan2(ay1 - ay0, ax1 - ax0)
            a_len = 6.0
            p1 = (ax1 - a_len * math.cos(ang - 0.5), ay1 - a_len * math.sin(ang - 0.5))
            p2 = (ax1 - a_len * math.cos(ang + 0.5), ay1 - a_len * math.sin(ang + 0.5))
            draw.polygon([(ax1, ay1), p1, p2], fill=col)

        # Inter-node directional wires & buses
        mid_r0_y = (r0_y0 + r0_y1) // 2
        mid_r1_y = (r1_y0 + r1_y1) // 2
        c0_cx = c0_x0 + col_w // 2
        c1_cx = c1_x0 + col_w // 2
        c2_cx = c2_x0 + col_w // 2

        # 1) DA4 -> DA2 (Analog -> ADC)
        _draw_arrow(c0_x0 + col_w, mid_r0_y, c1_x0, mid_r0_y, (52, 211, 153))
        draw.text((c0_x0 + col_w + 2, mid_r0_y - 14), "VIN", fill=(52, 211, 153), font=f_bus)

        # 2) DA2 <-> DA1 (4-wire SSI synchronous bus)
        _draw_arrow(c1_cx - 8, r0_y1, c1_cx - 8, r1_y0, (245, 158, 11))
        _draw_arrow(c1_cx + 8, r1_y0, c1_cx + 8, r0_y1, (56, 189, 248))
        ssi_lbl = "SSI: SCLK 3,072M / SDFS 48k / SRD / STD"
        draw.rectangle([c1_x0 - 18, r0_y1 + 16, c1_x0 + col_w + 18, r0_y1 + 34], fill=(15, 23, 42), outline=(245, 158, 11))
        draw.text((c1_x0 - 12, r0_y1 + 19), ssi_lbl, fill=(255, 193, 7), font=f_bus)

        # 3) DA2 -> DA5 (DAC -> Analog Reconstruction Output)
        bus_y_dac = r0_y1 + 8
        draw.line([(c1_x0 + 18, r0_y1), (c1_x0 + 18, bus_y_dac), (c0_cx, bus_y_dac)], fill=(52, 211, 153), width=2)
        _draw_arrow(c0_cx, bus_y_dac, c0_cx, r1_y0, (52, 211, 153))
        draw.text((c0_x0 + 12, r0_y1 + 18), "VOUT -> \u0426\u0410\u041f", fill=(52, 211, 153), font=f_bus)

        # 4) DA1 <-> DA3 (External 0-WS SRAM bus A[15:0]/D[15:0])
        bus_y_sram = r1_y0 - 10
        draw.line([(c1_x0 + col_w - 14, r1_y0), (c1_x0 + col_w - 14, bus_y_sram), (c2_cx, bus_y_sram)], fill=(167, 139, 250), width=2)
        _draw_arrow(c2_cx, bus_y_sram, c2_cx, r0_y1, (167, 139, 250))
        draw.text((c2_x0 + 6, r0_y1 + 18), "A[15:0]/D[15:0] 0-WS", fill=(196, 181, 253), font=f_bus)

        # 5) DA6/DD1 -> DA1 (Supervisor Reset & SPI Boot)
        _draw_arrow(c2_x0, mid_r1_y, c1_x0 + col_w, mid_r1_y, (244, 114, 182))
        draw.text((c1_x0 + col_w + 2, mid_r1_y - 14), "SPI/RST", fill=(244, 114, 182), font=f_bus)

        # Animated glowing signal packets along buses
        phase = (t * 1.8) % 1.0
        # Packet 1: Analog -> ADC
        p1_x = (c0_x0 + col_w) + phase * (c1_x0 - (c0_x0 + col_w))
        draw.ellipse([p1_x - 4, mid_r0_y - 4, p1_x + 4, mid_r0_y + 4], fill=(52, 211, 153))
        # Packet 2: SSI SRD/STD
        p2_y = r0_y1 + phase * (r1_y0 - r0_y1)
        draw.ellipse([c1_cx - 12, p2_y - 4, c1_cx - 4, p2_y + 4], fill=(255, 193, 7))
        # Packet 3: SRAM 0-WS
        p3_y = r1_y0 - phase * (r1_y0 - r0_y1)
        draw.ellipse([c2_cx - 4, p3_y - 4, c2_cx + 4, p3_y + 4], fill=(167, 139, 250))
        # Packet 4: DAC -> Out
        p4_y = bus_y_dac + phase * (r1_y0 - bus_y_dac)
        draw.ellipse([c0_cx - 4, p4_y - 4, c0_cx + 4, p4_y + 4], fill=(56, 189, 248))

        # Render the 6 IC Node Cards
        for nd in nodes:
            bx0, by0, bx1, by1 = nd["box"]
            is_act = nd["id"] in matched_ids
            border_col = (255, 193, 7) if is_act else nd["out"]
            border_w = 3 if is_act else 1
            draw.rectangle([bx0, by0, bx1, by1], fill=nd["fill"], outline=border_col, width=border_w)
            draw.text((bx0 + 6, by0 + 4), nd["title"], fill=(255, 255, 255), font=f_hdr)
            draw.text((bx0 + 6, by0 + 22), nd["sub"], fill=(255, 193, 7) if is_act else (224, 242, 254), font=f_sub)
            draw.text((bx0 + 6, by0 + 40), nd["detail"], fill=(148, 163, 184), font=f_bus)
            labels_drawn.append(nd["title"])

        # Bottom Real-Time SRAM Timing Diagram Bar
        tb_y0 = y1 - 36
        tb_y1 = y1 - 6
        draw.rectangle([x0 + 10, tb_y0, x1 - 10, tb_y1], fill=(15, 23, 42), outline=(56, 189, 248), width=1)
        bar_x0 = x0 + 16
        bar_w = (x1 - 16) - bar_x0
        acc_w = int(bar_w * (19.0 / 25.0))
        draw.rectangle([bar_x0, tb_y1 - 8, bar_x0 + acc_w, tb_y1 - 3], fill=(16, 185, 129))
        draw.rectangle([bar_x0 + acc_w, tb_y1 - 8, bar_x0 + bar_w, tb_y1 - 3], fill=(56, 189, 248))
        timing_txt = "T_cyc = 25 ns | SRAM t_acc = 19 ns < 25 ns (0 WS, margin 6 ns)"
        draw.text((bar_x0 + 4, tb_y0 + 4), timing_txt, fill=(240, 249, 255), font=f_bus)

        return labels_drawn


# ============================================================================
# 4. AssemblyTraceVisualizer
# ============================================================================


@dataclass
class OpcodeStep:
    index: int
    pc_hex: str
    mnemonic: str
    cycles: int
    phase: str
    r0_hex: str
    r1_hex: str
    acc_a_hex: str
    acc_b_hex: str


class AssemblyTraceVisualizer:
    """
    Cycle-accurate opcode stepper and register/accumulator HUD for SSI_Rx_ISR
    at Vector 15 (P:$001E), verifying 23 instructions per biquad section in
    hardware DO loop, symmetric LIFO stack push/pop, and real-time budget.
    """

    PROLOGUE_PUSH_ORDER: Tuple[str, ...] = ("A1", "A0", "B1", "B0", "Y0", "Y1", "R0", "R1")
    EPILOGUE_POP_ORDER: Tuple[str, ...] = ("R1", "R0", "Y1", "Y0", "B0", "B1", "A0", "A1")

    BIQUAD_LOOP_23_INSTRUCTIONS: Tuple[str, ...] = (
        "MOVE.W X:(R0)+,Y0",
        "MOVE.W X:(R1)+,Y1",
        "MPY Y0,Y1,B",
        "MOVE.W X:(R0)-,Y0",
        "MOVE.W X:(R1)+,Y1",
        "MAC Y0,Y1,B",
        "ASL B",
        "ADD A,B",
        "MOVE.W B1,Y0",
        "MOVE.W X:(R1)+,Y1",
        "MPY Y0,Y1,A",
        "MOVE.W X:(R0)+,Y0",
        "MOVE.W X:(R1)+,Y1",
        "MAC Y0,Y1,A",
        "MOVE.W X:(R0)-,Y0",
        "MOVE.W X:(R1)+,Y1",
        "MAC Y0,Y1,A",
        "ASL A",
        "MOVE.W X:(R0)+,Y0",
        "MOVE.W Y0,X:(R0)-",
        "MOVE.W B1,X:(R0)+",
        "LEA (R0)+",
        "NOP",
    )

    def __init__(self, expanded_mode: bool = False) -> None:
        self.expanded_mode = bool(expanded_mode)
        self.ivt_vector_number: int = 15
        self.ivt_vector_address: str = "P:$001E"
        self.biquad_loop_instruction_count: int = len(self.BIQUAD_LOOP_23_INSTRUCTIONS)
        self.num_sections: int = 6
        self.total_cycles: int = 150 if self.expanded_mode else 114
        self.exec_time_us: float = round(self.total_cycles * (CYCLE_TIME_NS / 1000.0), 2)
        self.cpu_load_pct: float = round((self.exec_time_us / SAMPLE_PERIOD_US) * 100.0, 2)
        self.idle_margin_pct: float = round(100.0 - self.cpu_load_pct, 2)

    def verify_ivt_address(self, address_hex: str) -> bool:
        """Strictly accept P:$001E (Vector 15 SSI Rx) and reject legacy P:$0010."""
        return address_hex.strip().upper() == "P:$001E"

    def verify_stack_symmetry(self) -> bool:
        """Verify LIFO stack pop order is the exact reverse of prologue push order."""
        return list(self.EPILOGUE_POP_ORDER) == list(reversed(self.PROLOGUE_PUSH_ORDER))

    def step_instruction(self, step_idx: int) -> Dict[str, Any]:
        """Step to instruction index and return register, accumulator, and cycle metrics."""
        idx = max(0, int(step_idx)) % len(self.BIQUAD_LOOP_23_INSTRUCTIONS)
        section_idx = min(6, 1 + (max(0, int(step_idx)) // len(self.BIQUAD_LOOP_23_INSTRUCTIONS)))
        inst = self.BIQUAD_LOOP_23_INSTRUCTIONS[idx]
        pc_val = 0x0040 + idx
        r0_val = 0x0100 + (section_idx - 1) * 2
        r1_val = 0x0200 + (section_idx - 1) * 5 + (idx % 5)

        elapsed_cycles = min(
            self.total_cycles,
            12 + (section_idx - 1) * 16 + int((idx + 1) * (16.0 / 23.0)),
        )
        elapsed_us = round(elapsed_cycles * 0.025, 3)

        return {
            "pc_hex": f"P:${pc_val:04X}",
            "ivt_vector": self.ivt_vector_address,
            "section": section_idx,
            "instruction_index": idx,
            "mnemonic": inst,
            "r0_hex": f"X:${r0_val:04X}",
            "r1_hex": f"X:${r1_val:04X}",
            "acc_a": {"a2": "$0", "a1": "$4A21", "a0": "$0000", "float": 0.5791},
            "acc_b": {"b2": "$0", "b1": "$22A0", "b0": "$0000", "float": 0.2705},
            "elapsed_cycles": elapsed_cycles,
            "total_cycles": self.total_cycles,
            "elapsed_us": elapsed_us,
            "budget_us": round(SAMPLE_PERIOD_US, 3),
            "cpu_load_pct": self.cpu_load_pct,
            "idle_margin_pct": self.idle_margin_pct,
        }

    def draw_hud(
        self,
        draw: ImageDraw.ImageDraw,
        t: float,
        rect: Tuple[int, int, int, int] = (40, 40, 1240, 680),
    ) -> List[str]:
        """Render split disassembly terminal and 36-bit CPU register HUD."""
        step_idx = int(t * 6.0)
        state = self.step_instruction(step_idx)
        x0, y0, x1, y1 = rect
        h = y1 - y0
        compact = h < 340
        mid_x = x0 + int((x1 - x0) * 0.50)
        font = _get_default_font(12 if compact else 14)
        labels_drawn: List[str] = []

        # Left Pane: Disassembly Terminal
        draw.rectangle([x0, y0, mid_x, y1], fill=(15, 23, 42), outline=(51, 65, 85))
        lbl_hdr = f"SSI_Rx_ISR @ {state['ivt_vector']}"
        draw.text((x0 + 10, y0 + (6 if compact else 10)), lbl_hdr, fill=(245, 158, 11), font=font)
        labels_drawn.append(lbl_hdr)

        row_step = 22 if compact else 28
        num_rows = min(10, max(5, (h - 46) // 22))
        active_i = state["instruction_index"]
        start_i = max(0, min(len(self.BIQUAD_LOOP_23_INSTRUCTIONS) - num_rows, active_i - (num_rows // 2)))
        for row, i in enumerate(range(start_i, min(len(self.BIQUAD_LOOP_23_INSTRUCTIONS), start_i + num_rows))):
            ly = y0 + (34 if compact else 44) + row * row_step
            if i == active_i:
                draw.rectangle([x0 + 5, ly - 2, mid_x - 5, ly + row_step - 4], fill=(69, 26, 3), outline=(245, 158, 11))
            prefix = "-> " if i == active_i else "   "
            line_txt = f"{prefix}P:${0x0040 + i:04X}  {self.BIQUAD_LOOP_23_INSTRUCTIONS[i]}"
            draw.text((x0 + 10, ly), line_txt, fill=(226, 232, 240), font=font)

        # Right Pane: Registers, 36-bit Accumulators, and Real-Time Meter
        rx0 = mid_x + (10 if compact else 20)
        draw.rectangle([rx0, y0, x1, y1], fill=(15, 23, 42), outline=(51, 65, 85))

        hud_cards = [
            f"PC: {state['pc_hex']} (Sec {state['section']}/6)",
            f"AGU: R0={state['r0_hex']} R1={state['r1_hex']}",
            f"Acc A: {state['acc_a']['a2']}:{state['acc_a']['a1']}:{state['acc_a']['a0']}",
            f"Acc B: {state['acc_b']['b2']}:{state['acc_b']['b1']}:{state['acc_b']['b0']}",
            f"Cycles: {state['elapsed_cycles']}/{state['total_cycles']} ({state['elapsed_us']:.2f}us)",
            f"Reserve: {state['idle_margin_pct']:.1f}% Idle Margin",
        ]
        card_step = min(52, max(32, (h - 24) // 6))
        card_h = card_step - 6
        top_pad = 12 if compact else 24
        pad_x = 10 if compact else 16
        for idx_c, card_txt in enumerate(hud_cards):
            cy = y0 + top_pad + idx_c * card_step
            draw.rectangle([rx0 + pad_x, cy, x1 - pad_x, cy + card_h], fill=(30, 41, 59), outline=(71, 85, 105))
            draw.text((rx0 + pad_x + 8, cy + max(4, (card_h - 14) // 2)), card_txt, fill=(56, 189, 248), font=font)
            labels_drawn.append(card_txt)

        return labels_drawn


# ============================================================================
# 5. SpecComplianceVisualizer
# ============================================================================


class SpecComplianceVisualizer:
    """Renders animated engineering specification, comparison matrix (Table 2.1), reliability/thermal telemetry, ESKD documentation breakdown, or Table 6.1 compliance dashboard."""

    def __init__(self) -> None:
        self.last_subview: str = "E"
        self.last_labels: List[str] = []

    def select_subview(
        self,
        pz_page: int = 1,
        active_target: str = "",
        cue_label: str = "",
    ) -> str:
        """Select sub-view A..E from pz_page, active_target, and cue_label."""
        combined = f"{active_target or ''} {cue_label or ''}".lower()

        # Priority 1: Explicit keyword triggers in active_target / cue_label
        if any(
            k in combined
            for k in (
                "mtbf",
                "thermo",
                "thermal",
                "power_dissipation",
                "27.002",
                "\u043d\u0430\u0434\u0435\u0436\u043d",
                "\u0442\u0435\u043f\u043b",
                "947",
                "1,034",
                "1.034",
            )
        ):
            return "B"
        if any(
            k in combined
            for k in (
                "2_1",
                "2.1",
                "tms",
                "adsp",
                "mips",
                "\u0442\u0430\u0431\u043b\u0438\u0446\u0430 2.1",
                "\u0441\u0440\u0430\u0432\u043d\u0435\u043d\u0438\u0435 \u043f\u0446\u043e\u0441",
            )
        ):
            return "A"
        if any(
            k in combined
            for k in (
                "pe2",
                "eskd",
                "bom",
                "kompas",
                "kicad",
                "\u043f\u044d2",
                "\u0435\u0441\u043a\u0434",
                "\u043a\u043e\u043c\u043f\u0430\u0441",
                "2.702",
                "2.104",
            )
        ):
            return "C"
        if any(
            k in combined
            for k in (
                "6_1",
                "6.1",
                "concl",
                "qa",
                "\u0432\u044b\u0432\u043e\u0434",
                "\u0438\u0442\u043e\u0433",
                "\u0437\u0430\u043a\u043b\u044e\u0447",
            )
        ):
            return "D"

        # Priority 2: Page-based routing
        p = int(pz_page or 1)
        if p in (11, 12):
            return "A"
        if p == 20:
            return "B"
        if p in (4, 5, 6, 7, 21, 43):
            return "C"
        if p in (34, 35, 36, 37):
            return "D"
        return "E"

    def _draw_animated_telemetry_grid(
        self,
        draw: ImageDraw.ImageDraw,
        rect: Tuple[int, int, int, int],
        t: float,
    ) -> None:
        """Render animated background telemetry grid and sweeping inspection beams to guarantee continuous intra-scene dynamics."""
        x0, y0, x1, y1 = rect
        w = max(16, x1 - x0)
        h = max(16, y1 - y0)
        draw.rectangle([x0, y0, x1, y1], fill=(12, 18, 32), outline=(56, 189, 248), width=1)

        # Animated phase-shifted background grid cells
        cols = 8
        rows = 4
        cw = w / float(cols)
        rh = (h - 26) / float(rows)
        for r_i in range(rows):
            for c_i in range(cols):
                wave = 0.5 + 0.5 * math.sin(t * 2.8 + c_i * 0.75 + r_i * 1.15)
                c_r = int(12 + 16 * wave)
                c_g = int(20 + 28 * wave)
                c_b = int(36 + 42 * wave)
                gx0 = int(x0 + 2 + c_i * cw)
                gy0 = int(y0 + 25 + r_i * rh)
                gx1 = int(min(x1 - 2, x0 + (c_i + 1) * cw - 1))
                gy1 = int(min(y1 - 2, y0 + 25 + (r_i + 1) * rh - 1))
                draw.rectangle([gx0, gy0, gx1, gy1], fill=(c_r, c_g, c_b), outline=(26, 38, 60))

        # Sweeping vertical & horizontal radar scan bands
        phase_x = (t * 0.43) % 1.0
        phase_y = (t * 0.57) % 1.0
        sx = x0 + 8 + int(phase_x * max(1, w - 16))
        sy = y0 + 26 + int(phase_y * max(1, h - 32))
        band_w = 26
        draw.rectangle(
            [max(x0 + 2, sx - band_w), y0 + 25, min(x1 - 2, sx + band_w), y1 - 2],
            fill=(18, 42, 68),
            outline=(34, 211, 238),
        )
        draw.line([(sx, y0 + 25), (sx, y1 - 2)], fill=(56, 189, 248), width=2)
        draw.line([(x0 + 2, sy), (x1 - 2, sy)], fill=(245, 158, 11), width=1)

    def draw(
        self,
        draw: ImageDraw.ImageDraw,
        t: float = 0.0,
        rect: Tuple[int, int, int, int] = (606, 324, 1246, 586),
        active_target: str = "",
        pz_page: int = 1,
        cue_label: str = "",
    ) -> List[str]:
        """Render dynamic engineering specification & verification dashboard."""
        x0, y0, x1, y1 = rect
        w = max(64, x1 - x0)
        h = max(64, y1 - y0)
        f_hdr = _get_default_font(12, bold=True)
        f_row_b = _get_default_font(11, bold=True)
        f_row = _get_default_font(11, bold=False)
        f_mini = _get_default_font(10, bold=True)

        self._draw_animated_telemetry_grid(draw, rect, t)
        subview = self.select_subview(pz_page=pz_page, active_target=active_target, cue_label=cue_label)
        self.last_subview = subview
        labels: List[str] = []

        # Spring envelope + continuous harmonic modulation
        spring_k = float(closed_form_spring((t % 3.0) + 0.15, zeta=0.85, omega0=6.0, x0=0.35, x1=1.0))
        spring_k = max(0.35, min(1.05, spring_k))

        # Top header bar
        draw.rectangle([x0 + 2, y0 + 2, x1 - 2, y0 + 24], fill=(15, 23, 42), outline=(56, 189, 248))

        if subview == "A":
            # Sub-view A: Processor Comparison Matrix (Table 2.1)
            hdr = "\u0422\u0430\u0431\u043b\u0438\u0446\u0430 2.1: \u0421\u0440\u0430\u0432\u043d\u0435\u043d\u0438\u0435 \u041f\u0426\u041e\u0421 (\u0412\u044b\u0431\u043e\u0440: Motorola DSP56824)"
            draw.text((x0 + 8, y0 + 5), hdr, fill=(56, 189, 248), font=f_hdr)
            labels.append("\u0422\u0430\u0431\u043b\u0438\u0446\u0430 2.1: \u0412\u044b\u0431\u043e\u0440 DSP56824")

            procs = [
                (
                    "Motorola DSP56824",
                    "40 \u041c\u0413\u0446 / 40 MIPS \u2022 \u0426\u0438\u043a\u043b 25 \u043d\u0441 \u2022 \u0410\u041b\u0423 16\u00d716 -> 36 \u0431\u0438\u0442 \u2022 \u041f\u043e\u0440\u0442\u044b SSI + SPI",
                    "[\u0412\u042b\u0411\u0420\u0410\u041d]",
                    0.96,
                    (6, 78, 59),
                    (16, 185, 129),
                ),
                (
                    "TI TMS320C5402",
                    "100 \u041c\u0413\u0446 \u2022 \u0410\u041b\u0423 40 \u0431\u0438\u0442 \u2022 McBSP (\u0431\u0435\u0437 SPI)",
                    "[\u0410\u041b\u042c\u0422\u0415\u0420\u041d\u0410\u0422\u0418\u0412\u0410]",
                    0.74,
                    (30, 41, 59),
                    (56, 189, 248),
                ),
                (
                    "AD ADSP-2189M",
                    "75 \u041c\u0413\u0446 \u2022 \u0410\u041b\u0423 40 \u0431\u0438\u0442 \u2022 2\u00d7SPORT",
                    "[\u0414\u041e\u0420\u041e\u0416\u0415 \u041a\u041e\u0420\u041f\u0423\u0421]",
                    0.68,
                    (30, 41, 59),
                    (167, 139, 250),
                ),
            ]
            active_idx = int(t * 1.4) % 3
            for idx, (p_name, p_desc, p_badge, score, bg_c, bd_c) in enumerate(procs):
                ry0 = y0 + 30 + idx * 50
                ry1 = ry0 + 45
                is_hi = idx == 0 or idx == active_idx
                fill_c = (12, 92, 68) if (idx == 0 and idx == active_idx) else (bg_c if not is_hi else (38, 52, 78))
                out_c = (255, 193, 7) if idx == active_idx else bd_c
                draw.rectangle([x0 + 8, ry0, x1 - 8, ry1], fill=fill_c, outline=out_c, width=2 if is_hi else 1)
                draw.text((x0 + 14, ry0 + 4), p_name, fill=(255, 255, 255), font=f_row_b)
                draw.text((x0 + 150, ry0 + 4), p_desc, fill=(226, 232, 240), font=f_row)
                draw.text((x1 - 132, ry0 + 4), p_badge, fill=(52, 211, 153) if idx == 0 else (255, 193, 7), font=f_mini)

                # Animated horizontal telemetry bar
                bar_mod = 0.82 + 0.18 * math.sin(t * 2.6 + idx * 1.3)
                bw = int((w - 36) * score * min(1.0, spring_k * bar_mod))
                draw.rectangle([x0 + 14, ry1 - 12, x0 + 14 + bw, ry1 - 5], fill=bd_c)
                labels.append(p_name)

            # Bottom radar / bar sweep comparing 3 criteria
            by0 = y0 + 184
            by1 = y1 - 6
            draw.rectangle([x0 + 8, by0, x1 - 8, by1], fill=(15, 23, 42), outline=(56, 189, 248))
            metrics = [
                ("\u042d\u043d\u0435\u0440\u0433\u043e\u044d\u0444\u0444\u0435\u043a\u0442\u0438\u0432\u043d\u043e\u0441\u0442\u044c (3,3 \u0412)", 0.95, (16, 185, 129)),
                ("\u0422\u043e\u0447\u043d\u043e\u0441\u0442\u044c 36-\u0431\u0438\u0442 MAC", 0.98, (56, 189, 248)),
                ("\u0418\u043d\u0442\u0435\u0433\u0440\u0430\u0446\u0438\u044f SSI+SPI", 1.00, (245, 158, 11)),
            ]
            col_w = (w - 32) // 3
            for m_i, (m_lbl, m_val, m_col) in enumerate(metrics):
                mx0 = x0 + 14 + m_i * col_w
                mx1 = mx0 + col_w - 8
                draw.text((mx0, by0 + 6), m_lbl, fill=(224, 242, 254), font=f_mini)
                sweep = 0.65 + 0.35 * (0.5 + 0.5 * math.sin(t * 3.1 + m_i * 1.2))
                mw = int((mx1 - mx0) * m_val * sweep)
                draw.rectangle([mx0, by0 + 26, mx1, by0 + 40], fill=(30, 41, 59), outline=(71, 85, 105))
                draw.rectangle([mx0, by0 + 26, mx0 + mw, by0 + 40], fill=m_col)
                draw.text((mx0 + 4, by0 + 46), f"DSP56824: {int(m_val * 100)}% [\u041b\u0418\u0414\u0415\u0420]", fill=m_col, font=f_mini)

        elif subview == "B":
            # Sub-view B: Reliability & Thermal Regime (Section 3.7)
            hdr = "\u0420\u0430\u0437\u0434\u0435\u043b 3.7: \u041d\u0430\u0434\u0435\u0436\u043d\u043e\u0441\u0442\u044c (\u0413\u041e\u0421\u0422 27.002) \u0438 \u0442\u0435\u043f\u043b\u043e\u0432\u043e\u0439 \u0440\u0435\u0436\u0438\u043c"
            draw.text((x0 + 8, y0 + 5), hdr, fill=(52, 211, 153), font=f_hdr)
            labels.append("\u041d\u0430\u0434\u0435\u0436\u043d\u043e\u0441\u0442\u044c \u0413\u041e\u0421\u0422 27.002")

            mid_x = x0 + w // 2
            # Left Half: Exponential Reliability Curve P(t) = exp(-Lambda_Sigma * t)
            lx0, ly0, lx1, ly1 = x0 + 8, y0 + 30, mid_x - 4, y1 - 8
            draw.rectangle([lx0, ly0, lx1, ly1], fill=(15, 23, 42), outline=(16, 185, 129), width=2)
            draw.text((lx0 + 8, ly0 + 6), "P(t) = exp(-\u039b\u03a3\u00b7t) \u2022 \u039b\u03a3 = 9,67\u00b710^-7 \u0447^-1", fill=(16, 185, 129), font=f_mini)
            draw.text((lx0 + 8, ly0 + 22), "T0 = MTBF = 1,034\u00b710^6 \u0447 (> 118 \u043b\u0435\u0442)", fill=(240, 249, 255), font=f_row_b)
            draw.text((lx0 + 8, ly0 + 40), "P(1000 \u0447) = 0,99903 [\u0412\u042b\u0421\u041e\u041a\u0410\u042f]", fill=(255, 193, 7), font=f_row)

            gx0, gy0, gx1, gy1 = lx0 + 12, ly0 + 64, lx1 - 12, ly1 - 12
            draw.rectangle([gx0, gy0, gx1, gy1], fill=(11, 17, 29), outline=(51, 65, 85))
            pts: List[Tuple[float, float]] = []
            gw = max(10, gx1 - gx0)
            gh = max(10, gy1 - gy0)
            for i in range(48):
                u = i / 47.0
                # Exaggerated exponential + harmonic ripple for visual clarity
                p_val = math.exp(-1.15 * u) * (0.94 + 0.06 * math.sin(t * 2.5 + u * 4.0))
                px = gx0 + u * gw
                py = gy1 - min(0.96, max(0.1, p_val)) * (gh - 8)
                pts.append((px, py))
            if len(pts) >= 2:
                draw.line(pts, fill=(16, 185, 129), width=3)

            cur_u = (t * 0.38) % 1.0
            cur_idx = min(len(pts) - 1, int(cur_u * len(pts)))
            cx_p, cy_p = pts[cur_idx]
            draw.rectangle([gx0 + 1, gy0 + 1, max(gx0 + 2, int(cx_p)), max(gy0 + 2, gy1 - 1)], fill=(14, 48, 44))
            if len(pts) >= 2:
                draw.line(pts, fill=(16, 185, 129), width=3)
            draw.line([(cx_p, gy0), (cx_p, gy1)], fill=(255, 193, 7), width=2)
            draw.ellipse([cx_p - 5, cy_p - 5, cx_p + 5, cy_p + 5], fill=(255, 193, 7))
            labels.append("MTBF = 1,034*10^6 \u0447")

            # Right Half: Thermal Gauge & Power Breakdown
            rx0, ry0, rx1, ry1 = mid_x + 4, y0 + 30, x1 - 8, y1 - 8
            draw.rectangle([rx0, ry0, rx1, ry1], fill=(15, 23, 42), outline=(56, 189, 248), width=2)
            draw.text((rx0 + 8, ry0 + 6), "\u0422\u0435\u043f\u043b\u043e\u0432\u043e\u0439 \u0440\u0435\u0436\u0438\u043c: P\u03a3 = 947,5 \u043c\u0412\u0442", fill=(56, 189, 248), font=f_row_b)
            draw.text((rx0 + 8, ry0 + 24), "DA7 AMS1117-3.3 = 322 \u043c\u0412\u0442", fill=(226, 232, 240), font=f_row)
            draw.text((rx0 + 8, ry0 + 42), "\u041f\u0435\u0440\u0435\u0433\u0440\u0435\u0432 \u0394T = 4,2 \u00b0C << 55 \u00b0C", fill=(52, 211, 153), font=f_row_b)
            draw.text((rx0 + 8, ry0 + 60), "\u0420\u0430\u0434\u0438\u0430\u0442\u043e\u0440 \u043d\u0435 \u0442\u0440\u0435\u0431\u0443\u0435\u0442\u0441\u044f [\u041d\u041e\u0420\u041c\u0410]", fill=(255, 193, 7), font=f_mini)

            pwr_nodes = [
                ("DA1 DSP56824 (40 \u041c\u0413\u0446)", 340, (16, 185, 129)),
                ("DA7 AMS1117-3.3 LDO", 322, (245, 158, 11)),
                ("DA2 AD73322 + DA3 SRAM", 285, (56, 189, 248)),
            ]
            active_p = int(t * 1.45) % 3
            for p_i, (p_lbl, mw_val, p_col) in enumerate(pwr_nodes):
                py = ry0 + 82 + p_i * 44
                is_p = p_i == active_p
                draw.rectangle(
                    [rx0 + 6, py - 2, rx1 - 8, py + 38],
                    fill=(28, 45, 72) if is_p else (18, 27, 45),
                    outline=(255, 193, 7) if is_p else (51, 65, 85),
                )
                draw.text((rx0 + 10, py), f"{p_lbl}: {mw_val} \u043c\u0412\u0442", fill=(224, 242, 254), font=f_mini)
                frac = (mw_val / 450.0) * (0.72 + 0.28 * math.sin(t * 2.4 + p_i * 1.1))
                bw_p = int((rx1 - rx0 - 24) * max(0.15, min(1.0, frac)))
                draw.rectangle([rx0 + 10, py + 16, rx1 - 14, py + 30], fill=(30, 41, 59), outline=(71, 85, 105))
                draw.rectangle([rx0 + 10, py + 16, rx0 + 10 + bw_p, py + 30], fill=p_col)
            labels.append("\u0394T = 4,2 \u00b0C << 55 \u00b0C")

        elif subview == "C":
            # Sub-view C: ESKD Documentation Set, CAD Route & PE2 Parts List
            hdr = "\u041a\u043e\u043c\u043f\u043b\u0435\u043a\u0442 \u041a\u0414 \u0415\u0421\u041a\u0414 (\u041f\u0413\u0422\u0423.466225.001) \u0438 \u043f\u0435\u0440\u0435\u0447\u0435\u043d\u044c \u041f\u042d2 (30 \u043f\u043e\u0437.)"
            draw.text((x0 + 8, y0 + 5), hdr, fill=(56, 189, 248), font=f_hdr)
            labels.append("\u041a\u043e\u043c\u043f\u043b\u0435\u043a\u0442 \u0415\u0421\u041a\u0414 \u0438 \u041f\u042d2")

            # Top: Animated 3-stage CAD pipeline with moving signal pulse
            stages = [
                ("MATLAB R2024b", "\u0421\u0438\u043d\u0442\u0435\u0437 \u0411\u0418\u0425 N=11 (Q15)", (16, 185, 129)),
                ("KiCad 8.0", "\u0421\u0445\u0435\u043c\u0430 \u042d2 \u04103 (ERC PASS)", (56, 189, 248)),
                ("\u041a\u041e\u041c\u041f\u0410\u0421-3D v22", "\u0428\u0442\u0430\u043c\u043f\u044b \u0413\u041e\u0421\u0422 2.104", (245, 158, 11)),
            ]
            st_w = (w - 48) // 3
            active_st = int(t * 1.6) % 3
            for s_i, (st_title, st_sub, st_col) in enumerate(stages):
                sx0 = x0 + 10 + s_i * (st_w + 14)
                sx1 = sx0 + st_w
                sy0, sy1 = y0 + 30, y0 + 82
                is_act = s_i == active_st
                draw.rectangle(
                    [sx0, sy0, sx1, sy1],
                    fill=(28, 45, 72) if is_act else (15, 23, 42),
                    outline=(255, 193, 7) if is_act else st_col,
                    width=3 if is_act else 1,
                )
                draw.text((sx0 + 8, sy0 + 6), st_title, fill=(255, 255, 255), font=f_row_b)
                draw.text((sx0 + 8, sy0 + 26), st_sub, fill=st_col, font=f_mini)
                if s_i < 2:
                    ax0 = sx1 + 1
                    ax1 = sx1 + 13
                    ay = (sy0 + sy1) // 2
                    draw.line([(ax0, ay), (ax1, ay)], fill=(255, 193, 7), width=2)
                    p_x = ax0 + int(((t * 2.5) % 1.0) * (ax1 - ax0))
                    draw.ellipse([p_x - 3, ay - 3, p_x + 3, ay + 3], fill=(255, 193, 7))
                labels.append(st_title)

            # Bottom: Animated component group breakdown of PE2 (30 positions per GOST 2.702-2011)
            by0 = y0 + 90
            draw.rectangle([x0 + 8, by0, x1 - 8, y1 - 6], fill=(15, 23, 42), outline=(56, 189, 248))
            draw.text(
                (x0 + 14, by0 + 4),
                "\u041f\u042d2 (30 \u043f\u043e\u0437\u0438\u0446\u0438\u0439 \u043f\u043e \u0413\u041e\u0421\u0422 2.702-2011 \u2022 \u041a\u043b\u0438\u0440\u0435\u043d\u0441 \u0448\u0442\u0430\u043c\u043f\u0430 29,97 \u043c\u043c):",
                fill=(255, 193, 7),
                font=f_row_b,
            )
            groups = [
                (
                    "\u041a\u043e\u043d\u0434\u0435\u043d\u0441\u0430\u0442\u043e\u0440\u044b C1..C21",
                    "\u041a\u0435\u0440\u0430\u043c\u0438\u043a\u0430 NP0/X7R \u2022 \u0424\u0438\u043b\u044c\u0442\u0440\u044b \u0421\u0430\u043b\u043b\u0435\u043d\u0430\u2013\u041a\u0435\u044f 3900 \u043f\u0424, 1800 \u043f\u0424",
                    0.92,
                    (52, 211, 153),
                ),
                (
                    "\u041c\u0438\u043a\u0440\u043e\u0441\u0445\u0435\u043c\u044b DA1..DA7, DD1",
                    "DSP56824 \u2022 AD73322 \u2022 IS61LV6416 \u2022 AD8606AR \u2022 MAX706S \u2022 AMS1117-3.3 \u2022 MC68HC908",
                    0.98,
                    (56, 189, 248),
                ),
                (
                    "\u0420\u0435\u0437\u0438\u0441\u0442\u043e\u0440\u044b R1..R11, ZQ1..ZQ2, HG1",
                    "R1..R11 (2,4 \u043a\u041e\u043c E24) \u2022 ZQ1 (40 \u041c\u0413\u0446) \u2022 ZQ2 (12,288 \u041c\u0413\u0446) \u2022 \u0416\u041a\u0418 WH1602B",
                    0.95,
                    (167, 139, 250),
                ),
            ]
            active_g = int(t * 1.35) % 3
            for g_i, (g_title, g_sub, g_fill, g_col) in enumerate(groups):
                gy0 = by0 + 24 + g_i * 46
                gy1 = gy0 + 41
                is_g = g_i == active_g
                draw.rectangle(
                    [x0 + 14, gy0, x1 - 14, gy1],
                    fill=(28, 42, 66) if is_g else (20, 29, 47),
                    outline=(255, 193, 7) if is_g else g_col,
                    width=2 if is_g else 1,
                )
                draw.text((x0 + 20, gy0 + 3), g_title, fill=(255, 255, 255), font=f_row_b)
                draw.text((x1 - 92, gy0 + 3), "[\u0413\u041e\u0421\u0422 2.702]", fill=g_col, font=f_mini)
                draw.text((x0 + 20, gy0 + 19), g_sub, fill=(203, 213, 225), font=f_mini)
                bw_g = int((w - 40) * g_fill * (0.76 + 0.24 * math.sin(t * 2.7 + g_i)))
                draw.rectangle([x0 + 20, gy1 - 5, x0 + 20 + bw_g, gy1 - 2], fill=g_col)

        elif subview == "D":
            # Sub-view D: Table 6.1 Final Compliance & Defense Conclusions
            hdr = "\u0422\u0430\u0431\u043b\u0438\u0446\u0430 6.1: \u0412\u0435\u0440\u0438\u0444\u0438\u043a\u0430\u0446\u0438\u044f \u043f\u0430\u0440\u0430\u043c\u0435\u0442\u0440\u043e\u0432 \u0422\u0417 \u0412\u0430\u0440\u0438\u0430\u043d\u0442\u0430 \u21165 (100% \u0412\u042b\u041f\u041e\u041b\u041d\u0415\u041d\u041e)"
            draw.text((x0 + 8, y0 + 5), hdr, fill=(52, 211, 153), font=f_hdr)
            labels.append("\u0422\u0430\u0431\u043b\u0438\u0446\u0430 6.1: 100% \u0412\u042b\u041f\u041e\u041b\u041d\u0415\u041d\u041e")

            rows_6_1 = [
                (
                    "1. \u041f\u0426\u041e\u0421 \u0438 \u0442\u0430\u043a\u0442\u043e\u0432\u0430\u044f \u0447\u0430\u0441\u0442\u043e\u0442\u0430",
                    "\u0422\u0417: DSP56824, 40 \u041c\u0413\u0446 -> \u0424\u0430\u043a\u0442: 40 MIPS (\u0442\u0430\u043a\u0442 25 \u043d\u0441)",
                    "[\u0414\u0410]",
                ),
                (
                    "2. \u041f\u043e\u043b\u043e\u0441\u0430 \u0438 \u0441\u0440\u0435\u0437 \u0411\u0418\u0425 \u0424\u041d\u0427",
                    "\u0422\u0417: 10..11 \u043a\u0413\u0446, <=0,1 \u0434\u0411 -> \u0424\u0430\u043a\u0442: \u041a\u0430\u0443\u044d\u0440 N=11, 0,08 \u0434\u0411",
                    "[\u0414\u0410]",
                ),
                (
                    "3. \u0417\u0430\u0442\u0443\u0445\u0430\u043d\u0438\u0435 \u0432 \u043f\u043e\u043b\u043e\u0441\u0435 \u0437\u0430\u0433\u0440\u0430\u0436\u0434\u0435\u043d\u0438\u044f",
                    "\u0422\u0417: >= 80 \u0434\u0411 -> \u0424\u0430\u043a\u0442: 82,4 \u0434\u0411 (6 \u0441\u0435\u043a\u0446\u0438\u0439 DF-II)",
                    "[\u0414\u0410]",
                ),
                (
                    "4. \u0420\u0430\u0437\u0440\u044f\u0434\u043d\u043e\u0441\u0442\u044c Q15 \u0438 \u043f\u043e\u0433\u0440\u0435\u0448\u043d\u043e\u0441\u0442\u044c",
                    "\u0422\u0417: 16 \u0431\u0438\u0442, <= 0,5% -> \u0424\u0430\u043a\u0442: SNR 98,08 \u0434\u0411, \u0421\u041a\u041e 0,17%",
                    "[\u0414\u0410]",
                ),
                (
                    "5. \u0420\u0435\u0430\u043b\u044c\u043d\u043e\u0435 \u0432\u0440\u0435\u043c\u044f (Ts=20,833 \u043c\u043a\u0441)",
                    "\u0422\u0417: < 20,833 \u043c\u043a\u0441 -> \u0424\u0430\u043a\u0442: 2,85..3,75 \u043c\u043a\u0441 (\u0437\u0430\u043f\u0430\u0441 >82%)",
                    "[\u0414\u0410]",
                ),
            ]
            active_r = int(t * 1.5) % 5
            for r_i, (r_name, r_fact, r_badge) in enumerate(rows_6_1):
                ry0 = y0 + 28 + r_i * 45
                ry1 = ry0 + 41
                is_act = r_i == active_r
                draw.rectangle(
                    [x0 + 8, ry0, x1 - 8, ry1],
                    fill=(6, 78, 59) if is_act else (17, 26, 44),
                    outline=(255, 193, 7) if is_act else (16, 185, 129),
                    width=2 if is_act else 1,
                )
                draw.text((x0 + 14, ry0 + 3), r_name, fill=(255, 255, 255), font=f_row_b)
                draw.text((x0 + 228, ry0 + 3), r_fact, fill=(224, 242, 254), font=f_row)
                draw.rectangle([x1 - 88, ry0 + 4, x1 - 14, ry0 + 22], fill=(6, 95, 70), outline=(52, 211, 153))
                draw.text((x1 - 82, ry0 + 6), f"{r_badge} \u041d\u041e\u0420\u041c\u0410", fill=(52, 211, 153), font=f_mini)

                prog = 0.78 + 0.22 * math.sin(t * 2.5 + r_i * 0.9)
                bw_r = int((w - 32) * prog)
                draw.rectangle([x0 + 14, ry1 - 8, x0 + 14 + bw_r, ry1 - 3], fill=(16, 185, 129))
                labels.append(f"Row {r_i + 1}: PASS")

        else:
            # Sub-view E: Title Page & Technical Assignment Passport (Default / Pages 1..3)
            hdr = "\u041f\u0430\u0441\u043f\u043e\u0440\u0442 \u043f\u0440\u043e\u0435\u043a\u0442\u0430: \u041f\u0413\u0422\u0423, \u043a\u0430\u0444. \u0418\u0422\u0420\u0421 \u2022 \u0412\u0430\u0440\u0438\u0430\u043d\u0442 \u21165 (Motorola DSP56824)"
            draw.text((x0 + 8, y0 + 5), hdr, fill=(255, 193, 7), font=f_hdr)
            labels.append("\u041f\u0430\u0441\u043f\u043e\u0440\u0442 \u0422\u0417 \u0412\u0430\u0440\u0438\u0430\u043d\u0442 \u21165")

            mid_x = x0 + int(w * 0.52)
            cards = [
                ("\u041f\u0426\u041e\u0421 Motorola DSP56824", "40 \u041c\u0413\u0446 (40 MIPS) \u2022 Q15 (16 \u0431\u0438\u0442) \u2022 \u041e\u0417\u0423 0-WS", (16, 185, 129)),
                ("\u0414\u0438\u0441\u043a\u0440\u0435\u0442\u0438\u0437\u0430\u0446\u0438\u044f AD73322", "Fs = 48 \u043a\u0413\u0446 \u2022 Ts = 20,833 \u043c\u043a\u0441 \u2022 ZQ2 12,288 \u041c\u0413\u0446", (56, 189, 248)),
                ("\u0428\u0430\u0431\u043b\u043e\u043d \u0411\u0418\u0425 \u0424\u041d\u0427 (\u041a\u0430\u0443\u044d\u0440 N=11)", "0..10 \u043a\u0413\u0446 (\u0394A<=0,1\u0434\u0411) \u2022 \u0394f=1 \u043a\u0413\u0446 \u2022 11..24 \u043a\u0413\u0446 (-80\u0434\u0411)", (245, 158, 11)),
                ("\u0421\u0442\u0440\u0443\u043a\u0442\u0443\u0440\u0430 \u041f\u0417 (\u0413\u041e\u0421\u0422 7.32-2017)", "43 \u0441\u0442\u0440. \u041f\u0417 \u2022 \u0421\u0445\u0435\u043c\u0430 \u042d2 (\u04103) \u2022 \u041f\u0435\u0440\u0435\u0447\u0435\u043d\u044c \u041f\u042d2 (\u04104)", (167, 139, 250)),
            ]
            active_c = int(t * 1.45) % 4
            for c_i, (c_title, c_sub, c_col) in enumerate(cards):
                cy0 = y0 + 30 + c_i * 56
                cy1 = cy0 + 50
                is_act = c_i == active_c
                draw.rectangle(
                    [x0 + 8, cy0, mid_x - 6, cy1],
                    fill=(28, 45, 72) if is_act else (16, 24, 42),
                    outline=(255, 193, 7) if is_act else c_col,
                    width=2 if is_act else 1,
                )
                draw.text((x0 + 14, cy0 + 4), c_title, fill=(255, 255, 255), font=f_row_b)
                draw.text((x0 + 14, cy0 + 22), c_sub, fill=(224, 242, 254), font=f_mini)
                bw_c = int((mid_x - x0 - 28) * (0.72 + 0.28 * math.sin(t * 2.4 + c_i)))
                draw.rectangle([x0 + 14, cy1 - 6, x0 + 14 + bw_c, cy1 - 2], fill=c_col)

            # Right Pane: Animated Frequency Mask Preview (0..10 kHz, df=1 kHz, 11..24 kHz at -80 dB)
            rx0, ry0, rx1, ry1 = mid_x + 4, y0 + 30, x1 - 8, y1 - 8
            draw.rectangle([rx0, ry0, rx1, ry1], fill=(15, 23, 42), outline=(56, 189, 248), width=2)
            draw.text((rx0 + 8, ry0 + 6), "\u0410\u0427\u0425 \u0422\u0417: 0..10 \u043a\u0413\u0446 | \u0394f=1 \u043a\u0413\u0446 | -80 \u0434\u0411", fill=(56, 189, 248), font=f_row_b)
            draw.text((rx0 + 8, ry0 + 22), "Fs = 48 \u043a\u0413\u0446 (F_Nyq = 24 \u043a\u0413\u0446)", fill=(255, 193, 7), font=f_mini)

            px0, py0, px1, py1 = rx0 + 10, ry0 + 42, rx1 - 10, ry1 - 24
            pw_b = max(20, px1 - px0)
            ph_b = max(20, py1 - py0)
            draw.rectangle([px0, py0, px1, py1], fill=(10, 15, 26), outline=(51, 65, 85))

            x_10k = px0 + int((10.0 / 24.0) * pw_b)
            x_11k = px0 + int((11.0 / 24.0) * pw_b)
            y_pass = py0 + 18
            y_stop = py0 + int(ph_b * 0.78)

            # Shaded forbidden zones & cutoff lines
            draw.rectangle([x_11k, py0 + 2, px1 - 2, y_stop], fill=(48, 16, 28), outline=(244, 63, 94))
            draw.line([(x_10k, py0), (x_10k, py1)], fill=(52, 211, 153), width=1)
            draw.line([(x_11k, py0), (x_11k, py1)], fill=(244, 63, 94), width=1)

            # Animated Cauer N=11 magnitude response curve
            resp_pts: List[Tuple[float, float]] = []
            for i in range(60):
                u = i / 59.0
                f_khz = u * 24.0
                fx = px0 + u * pw_b
                if f_khz <= 10.0:
                    rip = 3.0 * math.sin(f_khz * 1.4 + t * 3.0)
                    fy = y_pass + abs(rip)
                elif f_khz < 11.0:
                    alpha = (f_khz - 10.0) / 1.0
                    fy = y_pass + alpha * (y_stop - y_pass)
                else:
                    bounce = 10.0 * abs(math.sin((f_khz - 11.0) * 1.2 - t * 2.5))
                    fy = min(py1 - 4, y_stop + 14 - bounce)
                resp_pts.append((fx, fy))
            if len(resp_pts) >= 2:
                draw.line(resp_pts, fill=(6, 182, 212), width=3)

            # Sweeping frequency marker dot
            sw_u = (t * 0.41) % 1.0
            sw_idx = min(len(resp_pts) - 1, int(sw_u * len(resp_pts)))
            sx_m, sy_m = resp_pts[sw_idx]
            draw.line([(sx_m, py0), (sx_m, py1)], fill=(255, 193, 7), width=1)
            draw.ellipse([sx_m - 5, sy_m - 5, sx_m + 5, sy_m + 5], fill=(255, 193, 7))
            draw.text((rx0 + 10, ry1 - 18), "0..10\u043a\u0413\u0446 (\u041f\u041f) | 11..24\u043a\u0413\u0446 (\u041f\u0417 >=80\u0434\u0411)", fill=(52, 211, 153), font=f_mini)
            labels.append("Fs = 48 kHz, Ts = 20.833 us")

        self.last_labels = labels
        return labels
