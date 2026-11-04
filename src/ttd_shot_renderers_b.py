"""src/ttd_shot_renderers_b.py
Full-frame painted scene renderers for SHOT-07 through SHOT-12.
Blends genuine Fortiche Arcane + anime studio painted scenes into canonical plates.
100% English-only source code (0 literal Cyrillic characters).
"""
from __future__ import annotations

from pathlib import Path
from typing import List, Tuple
import cv2
import numpy as np

from src.ttd_shot_renderers_a import _blend_painted_scene


def render_shot_07(plate: np.ndarray, root_dir: Path) -> np.ndarray:
    ellipses = [((640, 400), (480, 310), 0.0), ((640, 590), (520, 190), 0.0)]
    return _blend_painted_scene(plate, root_dir, 7, ellipses)


def render_shot_08(plate: np.ndarray, root_dir: Path) -> np.ndarray:
    ellipses = [((640, 420), (480, 300), 4.0), ((680, 600), (520, 190), 0.0)]
    return _blend_painted_scene(plate, root_dir, 8, ellipses, clean_sky=True)


def render_shot_09(plate: np.ndarray, root_dir: Path) -> np.ndarray:
    ellipses = [((640, 380), (460, 290), 0.0)]
    return _blend_painted_scene(plate, root_dir, 9, ellipses)


def render_shot_10(plate: np.ndarray, root_dir: Path) -> np.ndarray:
    ellipses = [((600, 500), (520, 240), 0.0), ((640, 610), (580, 160), 0.0)]
    return _blend_painted_scene(plate, root_dir, 10, ellipses)


def render_shot_11(plate: np.ndarray, root_dir: Path) -> np.ndarray:
    ellipses = [((680, 420), (480, 300), -8.0), ((700, 600), (520, 190), -6.0)]
    return _blend_painted_scene(plate, root_dir, 11, ellipses, clean_sky=True)


def render_shot_12(plate: np.ndarray, root_dir: Path) -> np.ndarray:
    ellipses = [((640, 430), (500, 300), 6.0), ((680, 600), (540, 190), 4.0)]
    return _blend_painted_scene(plate, root_dir, 12, ellipses, clean_sky=True)
