"""
Unit and Integration Test Suite for the Four Domain Engineering Visualizers (Milestone 2).

Verifies:
1. WaveformVisualizer: 48 kHz multi-tone synthesis, ALU saturation clamping (SA=1),
   6-stage Direct Form II biquad cascade, L_infinity state bounds ||W_k||_inf <= 1.0,
   transient settling (22 samples, 0.46 ms), and 1024-point FFT spectrum analyzer.
2. ZPlaneVisualizer: 11 poles and 11 zeros placement, BIBO stability (r_max = 0.987815 < 1.0),
   phasor vector sweep z(omega) = exp(j*omega), notch evaluation at 11.2 kHz (-100 dB floor),
   and >= 45 px badge clearance outside the unit circle.
3. HardwareBusVisualizer: Harvard 6-bus matrix (240 MB/s), Dual-Access X-RAM (strict rejection
   of physical Y-memory), 0 Wait-States IS61LV6416 timing (19 ns < 25 ns, +6 ns margin),
   AD73322 12.288 MHz / 256 = 48 kHz clock verification, Sallen-Key f0=25.03 kHz, Q=0.736,
   and 5-shot camera zoom sequence.
4. AssemblyTraceVisualizer: Vector 15 strict IVT check at P:$001E (rejecting P:$0010),
   exact 23 instructions per biquad in hardware DO loop, symmetric LIFO stack push/pop,
   36-bit accumulator HUD, and 114/150 cycle real-time reserve (82..86.32% margin).
5. Mayer CTML & REQ-004 Cleanliness across all rendered frames and source files.
"""

from __future__ import annotations

import math
import re
import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image, ImageDraw

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"
for _p in (str(REPO_ROOT), str(SRC_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from src.flow_ctml_linter import validate_modality_rule, validate_zero_clutter
from src.flow_dsp_visualizers import (
    AssemblyTraceVisualizer,
    BIQUAD_COEFFS_DIV2,
    HardwareBusVisualizer,
    L_INF_OUTPUT_GAIN,
    L_INF_SECTION_GAINS,
    WaveformVisualizer,
    ZPlaneVisualizer,
)


# ============================================================================
# Section 1: WaveformVisualizer Tests
# ============================================================================


def test_waveform_multitone_synthesis_and_alu_saturation() -> None:
    vis = WaveformVisualizer(f1_hz=2500.0, f2_hz=15000.0, a1=0.8, a2=0.6, saturate_alu=True)
    sig, saturated = vis.synthesize_multitone(0.0, num_samples=1024)
    assert saturated is True
    assert len(sig) == 1024
    assert float(np.max(sig)) <= 0.999969
    assert float(np.min(sig)) >= -1.0


def test_waveform_df2_cascade_linf_state_bounds_at_resonance() -> None:
    # Edge Case 2: High-frequency input at 10.04 kHz (resonance of Section 6, Q=41.5)
    vis = WaveformVisualizer(f1_hz=10040.0, f2_hz=15000.0, a1=0.707, a2=0.2, noise_sigma=0.0)
    sig, _ = vis.synthesize_multitone(0.0, num_samples=1024, include_noise=False)
    res = vis.filter_cascade_df2(sig, active_stages=6)
    assert res["active_stages"] == 6
    assert res["all_states_bounded"] is True
    assert all(pk <= 1.0 for pk in res["state_peaks"])
    assert len(L_INF_SECTION_GAINS) == 6
    assert pytest.approx(L_INF_OUTPUT_GAIN, 1e-4) == 4.8236


def test_waveform_progressive_stages_and_fft_suppression() -> None:
    vis = WaveformVisualizer(noise_sigma=0.01)
    st_raw = vis.evaluate(t=2.0, active_stages=0)
    st_full = vis.evaluate(t=25.0, active_stages=6)

    assert st_raw["active_stages"] == 0
    assert st_full["active_stages"] == 6
    assert st_full["settling_samples"] == 22
    assert pytest.approx(st_full["settling_time_ms"], 0.01) == 0.46
    # Stopband 15 kHz component must be strongly attenuated after 6 stages compared to stage 0
    assert st_full["stopband_15k_db"] < st_raw["stopband_15k_db"] - 15.0
    assert np.all(st_full["spectrum_db"] >= -100.0)


def test_waveform_draw_ctml_compliance() -> None:
    vis = WaveformVisualizer()
    img = Image.new("RGB", (1280, 720), (11, 15, 25))
    draw = ImageDraw.Draw(img)
    labels = vis.draw(draw, t=12.0)
    assert len(labels) >= 4
    mod_res = validate_modality_rule(labels, max_words=6)
    assert mod_res.ok is True, f"Modality violations: {mod_res.violations}"
    clutter_res = validate_zero_clutter(drawn_texts=labels)
    assert clutter_res.ok is True


# ============================================================================
# Section 2: ZPlaneVisualizer Tests
# ============================================================================


def test_zplane_poles_zeros_and_bibo_stability() -> None:
    zp = ZPlaneVisualizer()
    assert len(zp.poles) == 11
    assert len(zp.zeros) == 11
    assert pytest.approx(zp.max_pole_radius, 1e-5) == 0.987815
    assert zp.max_pole_radius < 1.0
    assert pytest.approx(zp.stability_margin_pct, 0.05) == 1.22


def test_zplane_phasor_sweep_passband_cutoff_and_notch() -> None:
    zp = ZPlaneVisualizer()
    # DC / Passband (omega = 0)
    ev_dc = zp.evaluate(0.0)
    assert ev_dc["bibo_stable"] is True
    assert abs(ev_dc["magnitude_db"]) <= 1.0

    # Near Section 6 pole at 75.3 deg (10.04 kHz)
    omega_pole6 = math.radians(75.3)
    ev_p6 = zp.evaluate(omega_pole6)
    assert pytest.approx(ev_p6["min_pole_distance"], 1e-3) == (1.0 - 0.987815)
    assert math.isfinite(ev_p6["magnitude_db"])

    # Exact transmission zero at 84.0 deg (11.20 kHz) -> clamped at -100 dB floor
    omega_zero6 = math.radians(84.0)
    ev_z6 = zp.evaluate(omega_zero6)
    assert ev_z6["min_zero_distance"] < 1e-6
    assert ev_z6["magnitude_db"] == -100.0


def test_zplane_draw_badge_clearance_and_ctml() -> None:
    zp = ZPlaneVisualizer()
    img = Image.new("RGB", (1280, 720), (11, 15, 25))
    draw = ImageDraw.Draw(img)
    out = zp.draw(draw, omega=math.radians(75.3))
    assert out["badge_clearance_px"] >= 45.0, f"Badge clearance {out['badge_clearance_px']} < 45 px"
    mod_res = validate_modality_rule(out["labels"], max_words=6)
    assert mod_res.ok is True
    assert validate_zero_clutter(drawn_texts=out["labels"]).ok is True


# ============================================================================
# Section 3: HardwareBusVisualizer Tests
# ============================================================================


def test_hardware_bus_harvard_matrix_and_no_y_memory() -> None:
    hw = HardwareBusVisualizer()
    assert len(hw.HARVARD_BUSES) == 6
    assert hw.has_physical_y_memory is False
    assert hw.matrix_bandwidth_mbps == 240.0

    # Valid Dual-Access X-RAM transfers
    hw.set_active_transfer("X:$0100", "Y0", "XDB1", 0x24A5)
    hw.set_active_transfer("X:$0200", "Y1", "XDB2", 0x4000)
    assert len(hw.active_transfers) == 2

    # Illegal Y-memory reference must raise ValueError
    with pytest.raises(ValueError, match="no physical Y-memory"):
        hw.set_active_transfer("Y:$0100", "Y0", "XDB1", 0x1234)


def test_hardware_sram_zero_wait_states_and_sallen_key() -> None:
    hw = HardwareBusVisualizer()
    assert hw.sram_setup_ns + hw.sram_access_ns + hw.sram_hold_ns == 19.0
    assert hw.sram_total_ns < hw.cycle_time_ns
    assert hw.sram_margin_ns == 6.0
    assert hw.wait_states == 0
    assert hw.bus_bcr_hex == "$0000"

    sk = hw.compute_sallen_key_params()
    assert pytest.approx(sk["f0_khz"], 0.05) == 25.03
    assert pytest.approx(sk["q_factor"], 0.01) == 0.736
    assert sk["v_bias_v"] == 1.65

    # Codec clock check: 12.288 MHz valid, 16.384 MHz rejected
    clk_ok = hw.verify_codec_clock(12_288_000)
    assert clk_ok["valid"] is True
    assert clk_ok["divider"] == 256

    clk_bad = hw.verify_codec_clock(16_384_000)
    assert clk_bad["valid"] is False


def test_hardware_camera_zoom_director_and_draw() -> None:
    hw = HardwareBusVisualizer()
    c_macro = hw.get_camera_for_time(1.0)
    c_ssi = hw.get_camera_for_time(8.0)
    c_core = hw.get_camera_for_time(16.0)
    c_sram = hw.get_camera_for_time(25.0)

    assert pytest.approx(c_macro.zoom, 0.05) == 1.0
    assert c_ssi.zoom > 2.0
    assert c_core.zoom > 3.0
    assert c_sram.cx > 800.0

    img = Image.new("RGB", (1280, 720), (11, 15, 25))
    draw = ImageDraw.Draw(img)
    labels = hw.draw(draw, t=15.0)
    assert validate_modality_rule(labels, max_words=6).ok is True
    assert validate_zero_clutter(drawn_texts=labels).ok is True


# ============================================================================
# Section 4: AssemblyTraceVisualizer Tests
# ============================================================================


def test_assembly_trace_ivt_loop_and_stack_symmetry() -> None:
    asm = AssemblyTraceVisualizer(expanded_mode=False)
    assert asm.verify_ivt_address("P:$001E") is True
    assert asm.verify_ivt_address("P:$0010") is False
    assert asm.biquad_loop_instruction_count == 23
    assert asm.verify_stack_symmetry() is True

    # Canonical 114-cycle timing
    assert asm.total_cycles == 114
    assert pytest.approx(asm.exec_time_us, 0.01) == 2.85
    assert pytest.approx(asm.cpu_load_pct, 0.05) == 13.68
    assert pytest.approx(asm.idle_margin_pct, 0.05) == 86.32

    # Expanded 150-cycle timing
    asm_exp = AssemblyTraceVisualizer(expanded_mode=True)
    assert asm_exp.total_cycles == 150
    assert pytest.approx(asm_exp.exec_time_us, 0.01) == 3.75
    assert pytest.approx(asm_exp.cpu_load_pct, 0.05) == 18.0
    assert pytest.approx(asm_exp.idle_margin_pct, 0.05) == 82.0


def test_assembly_trace_stepping_and_hud_draw() -> None:
    asm = AssemblyTraceVisualizer()
    st0 = asm.step_instruction(0)
    st22 = asm.step_instruction(22)
    assert st0["ivt_vector"] == "P:$001E"
    assert st0["section"] == 1
    assert st22["instruction_index"] == 22
    assert "A2" in st0["acc_a"] or "a2" in st0["acc_a"]

    img = Image.new("RGB", (1280, 720), (11, 15, 25))
    draw = ImageDraw.Draw(img)
    labels = asm.draw_hud(draw, t=4.0)
    assert validate_modality_rule(labels, max_words=6).ok is True
    assert validate_zero_clutter(drawn_texts=labels).ok is True


# ============================================================================
# Section 5: REQ-004 Cleanliness Verification
# ============================================================================


def test_req004_zero_cyrillic_and_personal_tokens_m2() -> None:
    cyrillic_re = re.compile(r"[\u0400-\u04ff]")
    tok_a = ("ora" + "kul").lower()
    tok_b = ("anti" + "gravity").lower()

    for p in (REPO_ROOT / "src" / "flow_dsp_visualizers.py", Path(__file__).resolve()):
        txt = p.read_text(encoding="utf-8")
        assert cyrillic_re.search(txt) is None, f"Cyrillic found in {p.name}"
        low = txt.lower()
        assert tok_a not in low, f"Personal token found in {p.name}"
        assert tok_b not in low, f"Workspace token found in {p.name}"
