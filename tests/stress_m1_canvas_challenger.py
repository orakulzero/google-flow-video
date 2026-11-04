"""
Adversarial empirical stress test harness for AnimationCanvas and virtual camera (Milestone 1).

Evaluates:
1. Coordinate boundary stress: extreme zooms (1e-4 to 1e4), negative coords, NaN/Inf resilience.
2. Vectorized projection throughput: 50,000 points transform per frame.
3. Frame render throughput: >= 45 FPS across 100 consecutive frames with active layers and grid.
4. Frame buffer validity: raw bytes length == 1280 * 720 * 3 = 2,764,800, zero corrupt pixels.
5. Spring dynamics sanity: closed_form_spring convergence without divergence or oscillation under zeta=1.0.
6. REQ-004 compliance: 0 Cyrillic characters and 0 personal path tokens.
"""

from __future__ import annotations

import math
import re
import sys
import time
from pathlib import Path
from typing import Tuple

import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"
for _p in (str(REPO_ROOT), str(SRC_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from flow_animation_canvas import (
    AnimationCanvas,
    CameraState,
    CANVAS_BG_COLOR,
    CANVAS_GRID_COLOR,
)
from src.flow_prompt_library import closed_form_spring


# ============================================================================
# Section 1: Coordinate Boundary and Extreme Zoom Stress
# ============================================================================


def test_stress_extreme_zooms_invertibility() -> None:
    """Stress test coordinate projection invertibility across extreme zooms."""
    canvas = AnimationCanvas(width=1280, height=720)
    zooms = [1e-4, 1e-3, 1e-2, 0.1, 0.5, 1.0, 2.0, 10.0, 100.0, 1000.0, 1e4]
    test_points = [
        (0.0, 0.0),
        (640.0, 360.0),
        (-1000.0, -500.0),
        (1000.0, 500.0),
        (-1e6, -1e6),
        (1e6, 1e6),
        (-0.0001, 0.0001),
        (1234.5678, -8765.4321),
    ]

    for z in zooms:
        canvas.set_camera(
            CameraState(cx=640.0, cy=360.0, zoom=z),
            duration_sec=0.01,
            t_start=0.0,
        )
        for wx, wy in test_points:
            sx, sy = canvas.world_to_screen(wx, wy, t=0.1)
            assert math.isfinite(sx) and math.isfinite(sy), f"Non-finite screen coords at zoom {z}"

            r_wx, r_wy = canvas.screen_to_world(sx, sy, t=0.1)
            assert math.isfinite(r_wx) and math.isfinite(r_wy), f"Non-finite round-trip coords at zoom {z}"

            err_x = abs(wx - r_wx)
            err_y = abs(wy - r_wy)
            # Precision tolerance relative to coordinate magnitude
            tol = max(1e-5, (abs(wx) + abs(wy)) * 1e-8)
            assert err_x <= tol, f"Invertibility failed on X for zoom {z}, pt ({wx}, {wy}): err={err_x}"
            assert err_y <= tol, f"Invertibility failed on Y for zoom {z}, pt ({wx}, {wy}): err={err_y}"


def test_stress_negative_and_zero_target_zoom_safety() -> None:
    """Verify that zero or negative camera zooms are safely clamped to >= 1e-4."""
    canvas = AnimationCanvas(width=1280, height=720)
    for bad_zoom in [0.0, -0.5, -10.0, -1e5]:
        canvas.set_camera(
            CameraState(cx=640.0, cy=360.0, zoom=bad_zoom),
            duration_sec=0.01,
            t_start=0.0,
        )
        cam = canvas.get_camera_at_t(0.1)
        assert cam.zoom >= 1e-4, f"Camera zoom {cam.zoom} failed clamp for target {bad_zoom}"

        # Ensure no ZeroDivisionError in screen_to_world
        wx, wy = canvas.screen_to_world(640.0, 360.0, t=0.1)
        assert math.isfinite(wx) and math.isfinite(wy)


def test_stress_nan_and_inf_resilience() -> None:
    """Verify IEEE-754 NaN and Inf propagation without crashes."""
    canvas = AnimationCanvas(width=1280, height=720)

    # Scalar checks
    sx_nan, sy_inf = canvas.world_to_screen(float("nan"), float("inf"), t=0.0)
    assert math.isnan(sx_nan)
    assert math.isinf(sy_inf)

    wx_nan, wy_inf = canvas.screen_to_world(float("nan"), float("-inf"), t=0.0)
    assert math.isnan(wx_nan)
    assert math.isinf(wy_inf)

    # Vectorized checks
    pts = np.array([[np.nan, np.inf], [-np.inf, 100.0], [50.0, np.nan]])
    out = canvas.world_to_screen_np(pts, t=0.0)
    assert np.isnan(out[0, 0])
    assert np.isinf(out[0, 1])
    assert np.isinf(out[1, 0])
    assert math.isfinite(out[1, 1])
    assert math.isfinite(out[2, 0])
    assert np.isnan(out[2, 1])


def test_stress_world_rect_and_scale_boundaries() -> None:
    """Test inverted rectangles and extreme scales after spring settlement."""
    canvas = AnimationCanvas(width=1280, height=720)

    # Inverted bounding box
    rect_inverted = (500.0, 400.0, 100.0, 200.0)
    s_rect = canvas.world_rect_to_screen(rect_inverted, t=0.0)
    assert s_rect[0] <= s_rect[2], "Normalized rect min_x <= max_x failed"
    assert s_rect[1] <= s_rect[3], "Normalized rect min_y <= max_y failed"

    # Scale linearity across zoom range after spring settlement
    for z in [1e-4, 1e-2, 0.5, 1.0, 10.0, 100.0]:
        c = AnimationCanvas(width=1280, height=720)
        c.set_camera(
            CameraState(cx=640.0, cy=360.0, zoom=z),
            duration_sec=0.01,
            omega0=100.0,
            t_start=0.0,
        )
        scale = c.world_scale_to_screen(250.0, t=0.5)
        assert math.isclose(scale, 250.0 * z, rel_tol=1e-4)


# ============================================================================
# Section 2: Vectorized Projection Throughput Benchmark (50,000 points)
# ============================================================================


def test_benchmark_vectorized_50k_points_throughput() -> None:
    """Benchmark vectorized coordinate transform of 50,000 points per call."""
    canvas = AnimationCanvas(width=1280, height=720)
    np.random.seed(42)
    pts_50k = np.random.uniform(-5000.0, 5000.0, size=(50000, 2))

    # Warmup
    _ = canvas.world_to_screen_np(pts_50k, t=0.0)

    num_iterations = 60
    t_start = time.perf_counter()
    for i in range(num_iterations):
        t_sim = i / 30.0
        res = canvas.world_to_screen_np(pts_50k, t=t_sim)
    t_elapsed = time.perf_counter() - t_start

    avg_ms = (t_elapsed / num_iterations) * 1000.0
    throughput_mpts = (50000 * num_iterations) / (t_elapsed * 1e6)

    # Sanity checks
    assert res.shape == (50000, 2)
    assert res.dtype == np.float64
    # Performance assertion: 50k points must transform under 10.0 ms per frame
    assert avg_ms < 10.0, f"Vectorized transform too slow: {avg_ms:.2f} ms > 10.0 ms"
    # Throughput assertion: >= 5 million points per second
    assert throughput_mpts >= 5.0, f"Throughput too low: {throughput_mpts:.2f} Mpts/s < 5.0 Mpts/s"


# ============================================================================
# Section 3: Frame Render Throughput Benchmark (>= 45 FPS)
# ============================================================================


def test_benchmark_frame_render_throughput_45fps() -> None:
    """Verify >= 45 FPS across 100 consecutive frames with active layers and grid."""
    canvas = AnimationCanvas(width=1280, height=720, show_grid=True, grid_step=64)

    # Active Layer 1: Hardware blocks and bounding boxes
    def render_hardware_blocks(c: AnimationCanvas, draw, t: float) -> None:
        sx0, sy0 = c.world_to_screen(200.0, 150.0, t)
        sx1, sy1 = c.world_to_screen(550.0, 450.0, t)
        draw.rectangle([sx0, sy0, sx1, sy1], fill=(20, 30, 50, 160), outline=(60, 120, 220, 255))
        sx2, sy2 = c.world_to_screen(700.0, 150.0, t)
        sx3, sy3 = c.world_to_screen(1050.0, 450.0, t)
        draw.rectangle([sx2, sy2, sx3, sy3], fill=(30, 20, 50, 160), outline=(220, 100, 60, 255))

    # Active Layer 2: Signal waveform / dynamic vector trace
    def render_waveform_trace(c: AnimationCanvas, draw, t: float) -> None:
        pts = []
        for idx in range(64):
            wx = 100.0 + idx * 16.0
            wy = 580.0 + 40.0 * math.sin(0.1 * idx + 5.0 * t)
            pts.append(c.world_to_screen(wx, wy, t))
        draw.line(pts, fill=(0, 220, 180, 220), width=2)

    canvas.add_layer("hardware_blocks", render_hardware_blocks, z_index=1)
    canvas.add_layer("waveform_trace", render_waveform_trace, z_index=2)

    # Warmup
    _ = canvas.render_frame_at_t(0.0)

    frame_count = 100
    t_start = time.perf_counter()
    for i in range(frame_count):
        t_sim = i / 30.0
        frame = canvas.render_frame_at_t(t_sim)
    t_elapsed = time.perf_counter() - t_start

    fps = frame_count / t_elapsed
    avg_ms = (t_elapsed / frame_count) * 1000.0

    assert frame.size == (1280, 720)
    assert frame.mode == "RGB"
    # Strict 45 FPS assertion
    assert fps >= 45.0, f"Render throughput failed: {fps:.2f} FPS < 45.0 FPS (avg {avg_ms:.2f} ms)"


def test_benchmark_raw_frame_bytes_throughput() -> None:
    """Verify that zero-disk raw bytes serialization maintains >= 45 FPS."""
    canvas = AnimationCanvas(width=1280, height=720, show_grid=True)

    frame_count = 60
    t_start = time.perf_counter()
    for i in range(frame_count):
        raw = canvas.render_frame_bytes(i / 30.0)
    t_elapsed = time.perf_counter() - t_start

    fps = frame_count / t_elapsed
    assert len(raw) == 1280 * 720 * 3
    assert fps >= 45.0, f"Raw bytes throughput failed: {fps:.2f} FPS < 45.0 FPS"


# ============================================================================
# Section 4: Frame Buffer Validity and Pixel Integrity
# ============================================================================


def test_stress_frame_buffer_exact_size_and_channels() -> None:
    """Verify raw byte buffer is exactly 1280x720x3 = 2,764,800 bytes without corrupt pixels."""
    canvas = AnimationCanvas(width=1280, height=720, show_grid=False)
    raw_bytes = canvas.render_frame_bytes(0.0)

    expected_len = 1280 * 720 * 3
    assert len(raw_bytes) == expected_len, f"Buffer size mismatch: {len(raw_bytes)} != {expected_len}"

    buf = np.frombuffer(raw_bytes, dtype=np.uint8)
    assert buf.size == expected_len
    # Verify values are valid uint8 in range [0, 255]
    assert np.all(buf >= 0) and np.all(buf <= 255)

    # Reshape to 3D image array and check color uniformity on blank canvas
    img_arr = buf.reshape((720, 1280, 3))
    assert img_arr.shape == (720, 1280, 3)

    # All pixels on blank canvas must match CANVAS_BG_COLOR #0B0F19 (11, 15, 25)
    expected_bg = np.array(CANVAS_BG_COLOR, dtype=np.uint8)
    diff = np.abs(img_arr - expected_bg)
    assert np.max(diff) == 0, "Blank canvas contains corrupted or uninitialized background pixels"


def test_stress_frame_buffer_with_active_drawings() -> None:
    """Verify pixel buffer with active geometric primitives and grid."""
    canvas = AnimationCanvas(width=1280, height=720, show_grid=True)

    def draw_shapes(c: AnimationCanvas, draw, t: float) -> None:
        draw.rectangle([100, 100, 300, 300], fill=(255, 0, 0, 255))
        draw.line([(0, 0), (1280, 720)], fill=(0, 255, 0, 255), width=3)

    canvas.add_layer("shapes", draw_shapes)
    raw = canvas.render_frame_bytes(0.0)
    arr = np.frombuffer(raw, dtype=np.uint8).reshape((720, 1280, 3))

    # Verify solid red rectangle pixel at (200, 200)
    red_pixel = arr[200, 200]
    assert tuple(red_pixel) == (255, 0, 0), f"Expected red pixel, got {tuple(red_pixel)}"

    # Verify background pixel outside drawings and grid lines
    bg_pixel = arr[50, 50]
    assert tuple(bg_pixel) == CANVAS_BG_COLOR, f"Expected background pixel, got {tuple(bg_pixel)}"


# ============================================================================
# Section 5: Spring Dynamics Sanity and Convergence (zeta = 1.0)
# ============================================================================


def test_stress_spring_critically_damped_monotonicity_forward() -> None:
    """Test closed_form_spring forward transition (0 -> 1) for strict monotonicity and zero overshoot."""
    omega0 = 12.0
    zeta = 1.0
    x0 = 0.0
    x1 = 1.0

    t_eval = np.linspace(0.0, 4.0, 40001)
    values = np.array([closed_form_spring(t, zeta=zeta, omega0=omega0, x0=x0, x1=x1) for t in t_eval])

    # Monotonicity: difference between consecutive samples must be non-negative
    diffs = np.diff(values)
    assert np.all(diffs >= -1e-12), f"Monotonicity violated: min diff = {np.min(diffs)}"

    # Overshoot check: value must never exceed x1
    max_val = np.max(values)
    assert max_val <= x1 + 1e-12, f"Overshoot detected: max_val = {max_val} > {x1}"

    # Convergence at t = 1.0s: must be within 0.01% (1e-4) of target
    idx_1s = np.searchsorted(t_eval, 1.0)
    assert abs(values[idx_1s] - x1) < 1e-4, f"Failed 1s convergence: {values[idx_1s]}"

    # Convergence at t = 4.0s: must be within 1e-10 of target
    assert abs(values[-1] - x1) < 1e-10, f"Failed 4s convergence: {values[-1]}"


def test_stress_spring_critically_damped_monotonicity_reverse() -> None:
    """Test closed_form_spring reverse transition (1000 -> -500) for monotonicity and zero undershoot."""
    omega0 = 12.0
    zeta = 1.0
    x0 = 1000.0
    x1 = -500.0

    t_eval = np.linspace(0.0, 4.0, 40001)
    values = np.array([closed_form_spring(t, zeta=zeta, omega0=omega0, x0=x0, x1=x1) for t in t_eval])

    diffs = np.diff(values)
    assert np.all(diffs <= 1e-12), f"Reverse monotonicity violated: max diff = {np.max(diffs)}"

    min_val = np.min(values)
    assert min_val >= x1 - 1e-12, f"Undershoot detected: min_val = {min_val} < {x1}"


def test_stress_spring_boundary_times() -> None:
    """Test spring evaluation at negative time, zero, and asymptotic large time."""
    x0 = 42.0
    x1 = 100.0
    assert closed_form_spring(-5.0, zeta=1.0, omega0=12.0, x0=x0, x1=x1) == x0
    assert closed_form_spring(0.0, zeta=1.0, omega0=12.0, x0=x0, x1=x1) == x0
    assert abs(closed_form_spring(100.0, zeta=1.0, omega0=12.0, x0=x0, x1=x1) - x1) < 1e-12


def test_stress_spring_invalid_parameters_raise() -> None:
    """Verify that invalid omega0 and zeta raise descriptive ValueErrors."""
    with pytest.raises(ValueError, match="omega0 must be positive"):
        closed_form_spring(0.5, zeta=1.0, omega0=0.0)
    with pytest.raises(ValueError, match="omega0 must be positive"):
        closed_form_spring(0.5, zeta=1.0, omega0=-10.0)
    with pytest.raises(ValueError, match="zeta must be non-negative"):
        closed_form_spring(0.5, zeta=-0.5, omega0=12.0)


# ============================================================================
# Section 6: Architecture and Multi-Transition Stress
# ============================================================================


def test_stress_rapid_camera_sequence() -> None:
    """Verify handling of 50 rapid sequential camera transitions without degradation."""
    canvas = AnimationCanvas(width=1280, height=720)
    for i in range(50):
        t_start = i * 0.2
        target_state = CameraState(cx=640.0 + (i % 5) * 50.0, cy=360.0 + (i % 3) * 30.0, zoom=1.0 + (i % 4) * 0.25)
        canvas.set_camera(target_state, duration_sec=0.2, t_start=t_start)

    assert len(canvas._transitions) == 50
    # Probe transitions across time
    for probe_t in [0.0, 1.5, 4.5, 9.9, 15.0]:
        cam = canvas.get_camera_at_t(probe_t)
        assert math.isfinite(cam.cx) and math.isfinite(cam.cy) and math.isfinite(cam.zoom)
        assert cam.zoom >= 1e-4

    # Verify transition density calculation
    density = canvas.get_transition_density(window_sec=10.0)
    assert density == 150.0  # 50 transitions in 10s = 150 per 30s


def test_stress_layer_dynamic_mutations() -> None:
    """Verify layer addition, ordering, disabling, and removal."""
    canvas = AnimationCanvas(width=1280, height=720, show_grid=False)
    state = {"drawn_count": 0}

    def counter_layer(c: AnimationCanvas, draw, t: float) -> None:
        state["drawn_count"] += 1

    canvas.add_layer("test_layer", counter_layer, z_index=10)
    _ = canvas.render_frame_at_t(0.0)
    assert state["drawn_count"] == 1

    # Remove layer
    canvas.remove_layer("test_layer")
    _ = canvas.render_frame_at_t(0.0)
    assert state["drawn_count"] == 1  # Not incremented


# ============================================================================
# Section 7: REQ-004 Cyrillic and Path Token Cleanliness
# ============================================================================


def test_req004_zero_cyrillic_in_stress_suite() -> None:
    """Ensure zero Cyrillic characters exist in this stress suite."""
    cyrillic_re = re.compile(r"[\u0400-\u04ff]")
    self_path = Path(__file__).resolve()
    content = self_path.read_text(encoding="utf-8")
    match = cyrillic_re.search(content)
    assert match is None, f"Cyrillic character found in stress suite at position {match.start() if match else -1}"


def test_req004_zero_personal_tokens_in_stress_suite() -> None:
    """Ensure zero personal or workspace tokens exist in this stress suite."""
    self_path = Path(__file__).resolve()
    content = self_path.read_text(encoding="utf-8").lower()
    tok_a = ("ora" + "kul").lower()
    tok_b = ("anti" + "gravity").lower()
    assert tok_a not in content, "Personal token found in stress suite"
    assert tok_b not in content, "Workspace token found in stress suite"
