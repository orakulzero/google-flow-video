"""
Virtual 2D Camera & Core Animation Canvas.

Provides deterministic C1 continuous virtual camera motion via closed_form_spring,
zero-disk in-memory PIL/RGB24 frame rendering at 1280x720 HD on dark palette #0B0F19 (11, 15, 25),
and coordinate projection between world space and viewport screen space.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple, Union

import numpy as np
from PIL import Image, ImageDraw

CANVAS_BG_COLOR: Tuple[int, int, int] = (11, 15, 25)  # #0B0F19 dark canvas background
CANVAS_GRID_COLOR: Tuple[int, int, int, int] = (30, 41, 59, 70)  # Subtle dark slate grid


@dataclass
class CameraState:
    cx: float = 640.0
    cy: float = 360.0
    zoom: float = 1.0

    def clone(self) -> CameraState:
        return CameraState(cx=float(self.cx), cy=float(self.cy), zoom=float(self.zoom))

    def as_tuple(self) -> Tuple[float, float, float]:
        return (float(self.cx), float(self.cy), float(self.zoom))


@dataclass
class CameraTransition:
    t_start: float
    duration_sec: float
    target: CameraState
    zeta: float = 1.0
    omega0: float = 12.0
    start_state: Optional[CameraState] = None


@dataclass
class CanvasLayer:
    name: str
    render_fn: Callable[[AnimationCanvas, ImageDraw.ImageDraw, float], None]
    z_index: int = 0
    enabled: bool = True


class AnimationCanvas:
    def __init__(
        self,
        width: int = 1280,
        height: int = 720,
        bg_color: Tuple[int, int, int] = CANVAS_BG_COLOR,
        show_grid: bool = True,
        grid_step: int = 64,
    ) -> None:
        self.width = int(width)
        self.height = int(height)
        self.bg_color = bg_color
        self.show_grid = show_grid
        self.grid_step = int(grid_step)
        self.initial_camera = CameraState(cx=self.width / 2.0, cy=self.height / 2.0, zoom=1.0)
        self._transitions: List[CameraTransition] = []
        self._layers: Dict[str, CanvasLayer] = {}

    def set_camera(
        self,
        target: CameraState,
        duration_sec: float = 1.0,
        zeta: float = 1.0,
        omega0: float = 12.0,
        t_start: Optional[float] = None,
    ) -> None:
        if t_start is None:
            if not self._transitions:
                t_start = 0.0
            else:
                last = self._transitions[-1]
                t_start = last.t_start + last.duration_sec
        prev_state = self.get_camera_at_t(t_start)
        self._transitions.append(
            CameraTransition(
                t_start=float(t_start),
                duration_sec=max(1e-4, float(duration_sec)),
                target=target.clone(),
                zeta=float(zeta),
                omega0=float(omega0),
                start_state=prev_state.clone(),
            )
        )
        self._transitions.sort(key=lambda tr: tr.t_start)

    def get_camera_at_t(self, t: float) -> CameraState:
        from src.flow_prompt_library import closed_form_spring

        if not self._transitions or t <= self._transitions[0].t_start:
            return self.initial_camera.clone()

        active = self._transitions[0]
        for tr in self._transitions:
            if tr.t_start <= t:
                active = tr
            else:
                break

        tau = max(0.0, t - active.t_start)
        s0 = active.start_state or self.initial_camera
        s1 = active.target
        cx = float(closed_form_spring(tau, active.zeta, active.omega0, x0=s0.cx, x1=s1.cx))
        cy = float(closed_form_spring(tau, active.zeta, active.omega0, x0=s0.cy, x1=s1.cy))
        zoom = float(closed_form_spring(tau, active.zeta, active.omega0, x0=s0.zoom, x1=s1.zoom))
        return CameraState(cx=cx, cy=cy, zoom=max(1e-4, zoom))

    def world_to_screen(self, wx: float, wy: float, t: float) -> Tuple[float, float]:
        cam = self.get_camera_at_t(t)
        sx = (self.width / 2.0) + (float(wx) - cam.cx) * cam.zoom
        sy = (self.height / 2.0) + (float(wy) - cam.cy) * cam.zoom
        return (float(sx), float(sy))

    def world_to_screen_np(self, pts: np.ndarray, t: float) -> np.ndarray:
        cam = self.get_camera_at_t(t)
        pts_arr = np.asarray(pts, dtype=np.float64)
        out = np.empty_like(pts_arr)
        out[..., 0] = (self.width / 2.0) + (pts_arr[..., 0] - cam.cx) * cam.zoom
        out[..., 1] = (self.height / 2.0) + (pts_arr[..., 1] - cam.cy) * cam.zoom
        return out

    def screen_to_world(self, sx: float, sy: float, t: float) -> Tuple[float, float]:
        cam = self.get_camera_at_t(t)
        wx = cam.cx + (float(sx) - (self.width / 2.0)) / cam.zoom
        wy = cam.cy + (float(sy) - (self.height / 2.0)) / cam.zoom
        return (float(wx), float(wy))

    def world_rect_to_screen(
        self, rect: Tuple[float, float, float, float], t: float
    ) -> Tuple[float, float, float, float]:
        x0, y0 = self.world_to_screen(rect[0], rect[1], t)
        x1, y1 = self.world_to_screen(rect[2], rect[3], t)
        return (min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))

    def world_scale_to_screen(self, length: float, t: float) -> float:
        cam = self.get_camera_at_t(t)
        return float(length) * cam.zoom

    def add_layer(
        self,
        name: str,
        render_fn: Callable[[AnimationCanvas, ImageDraw.ImageDraw, float], None],
        z_index: int = 0,
    ) -> None:
        self._layers[name] = CanvasLayer(name=name, render_fn=render_fn, z_index=z_index)

    def remove_layer(self, name: str) -> None:
        self._layers.pop(name, None)

    def render_frame_at_t(self, t: float) -> Image.Image:
        img = Image.new("RGB", (self.width, self.height), self.bg_color)
        draw = ImageDraw.Draw(img, "RGBA")
        if self.show_grid:
            self._draw_grid(draw, t)
        sorted_layers = sorted(self._layers.values(), key=lambda l: l.z_index)
        for layer in sorted_layers:
            if layer.enabled:
                layer.render_fn(self, draw, t)
        return img

    def _draw_grid(self, draw: ImageDraw.ImageDraw, t: float) -> None:
        step = self.grid_step
        x_min, y_min = self.screen_to_world(0.0, 0.0, t)
        x_max, y_max = self.screen_to_world(float(self.width), float(self.height), t)
        gx_start = int(math.floor(min(x_min, x_max) / step)) * step
        gx_end = int(math.ceil(max(x_min, x_max) / step)) * step
        gy_start = int(math.floor(min(y_min, y_max) / step)) * step
        gy_end = int(math.ceil(max(y_min, y_max) / step)) * step
        grid_col = CANVAS_GRID_COLOR
        for gx in range(gx_start, gx_end + step, step):
            sx0, sy0 = self.world_to_screen(float(gx), min(y_min, y_max), t)
            sx1, sy1 = self.world_to_screen(float(gx), max(y_min, y_max), t)
            draw.line([(sx0, sy0), (sx1, sy1)], fill=grid_col, width=1)
        for gy in range(gy_start, gy_end + step, step):
            sx0, sy0 = self.world_to_screen(min(x_min, x_max), float(gy), t)
            sx1, sy1 = self.world_to_screen(max(x_min, x_max), float(gy), t)
            draw.line([(sx0, sy0), (sx1, sy1)], fill=grid_col, width=1)

    def render_frame_bytes(self, t: float) -> bytes:
        img = self.render_frame_at_t(t)
        return img.tobytes()

    @staticmethod
    def validate_label_word_count(label: str, max_words: int = 6) -> bool:
        from src.flow_ctml_linter import count_label_words

        return count_label_words(label) <= max_words

    def get_transition_density(self, window_sec: float = 30.0) -> float:
        if window_sec <= 0.0:
            return 0.0
        return float(len(self._transitions)) * (30.0 / float(window_sec))
