"""src/ttd_shot_renderers_a.py
Full-frame painted scene renderers for SHOT-01 through SHOT-06.
Blends genuine Fortiche Arcane + anime studio painted scenes into canonical plates.
100% English-only source code (0 literal Cyrillic characters).
"""
from __future__ import annotations

from pathlib import Path
from typing import List, Tuple
import cv2
import numpy as np


def _blend_painted_scene(
    plate: np.ndarray,
    root_dir: Path,
    shot_num: int,
    ellipses: List[Tuple[Tuple[int, int], Tuple[int, int], float]],
    clean_sky: bool = False,
) -> np.ndarray:
    painted_p = root_dir / "output" / "ttd_ep01_painted_scenes" / f"shot_{shot_num:02d}_painted.png"
    painted = cv2.imread(str(painted_p))
    if painted is None:
        raise FileNotFoundError(f"Missing painted scene: {painted_p}")
    if painted.shape[:2] != (720, 1280):
        painted = cv2.resize(painted, (1280, 720), interpolation=cv2.INTER_LANCZOS4)

    mask = np.zeros((720, 1280), dtype=np.float32)
    for center, axes, angle in ellipses:
        cv2.ellipse(mask, center, axes, angle, 0, 360, 1.0, -1)
    if clean_sky:
        mask[:150, 350:900] = 0.0
    mask[:200, :300] = 0.0
    mask = cv2.GaussianBlur(mask, (0, 0), sigmaX=28.0, sigmaY=28.0)
    if clean_sky:
        mask[:150, 350:900] = 0.0
    mask[:200, :300] = 0.0
    mask = np.clip(mask, 0.0, 1.0)

    m3 = mask[:, :, np.newaxis]
    comp = (painted.astype(np.float32) * m3 + plate.astype(np.float32) * (1.0 - m3)).astype(np.uint8)
    return comp


def render_shot_01(plate: np.ndarray, root_dir: Path) -> np.ndarray:
    ellipses = [((540, 430), (460, 290), 0.0), ((640, 580), (540, 180), 0.0)]
    return _blend_painted_scene(plate, root_dir, 1, ellipses)


def render_shot_02(plate: np.ndarray, root_dir: Path) -> np.ndarray:
    ellipses = [((640, 220), (480, 180), 0.0)]
    return _blend_painted_scene(plate, root_dir, 2, ellipses)


def render_shot_03(plate: np.ndarray, root_dir: Path) -> np.ndarray:
    ellipses = [((700, 380), (340, 310), 6.0), ((740, 600), (440, 220), 5.0)]
    return _blend_painted_scene(plate, root_dir, 3, ellipses, clean_sky=True)


def render_shot_04(plate: np.ndarray, root_dir: Path) -> np.ndarray:
    ellipses = [((710, 290), (260, 270), 12.0), ((820, 610), (420, 220), 10.0)]
    return _blend_painted_scene(plate, root_dir, 4, ellipses, clean_sky=False)


def render_shot_05(plate: np.ndarray, root_dir: Path) -> np.ndarray:
    ellipses = [((560, 450), (460, 280), 0.0), ((640, 600), (540, 170), 0.0)]
    return _blend_painted_scene(plate, root_dir, 5, ellipses)


def render_shot_06(plate: np.ndarray, root_dir: Path) -> np.ndarray:
    ellipses = [((640, 420), (460, 300), -6.0), ((680, 590), (500, 190), -4.0)]
    return _blend_painted_scene(plate, root_dir, 6, ellipses)
