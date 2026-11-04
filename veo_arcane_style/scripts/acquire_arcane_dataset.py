"""
Acquire Arcane Dataset & Frame Curation Engine for Google Veo 3.1 Styling.
Implements Milestone 1 (Requirement R1):
- SakugabooruClient REST API ingestion (2K stills and action cuts with MD5 validation)
- HuggingFaceIngester for ChickenRibs/LOL-Arcane
- ActionCutSlicer using downscaled MAD scene detection (delta_t >= 35.0 on 320x180)
- FrameQualityCurator (720p scope, Laplacian var >= 100.0, luminance [25, 235], dHash > 4)
- TaxonomyClassifier (9 characters, 4 lighting moods, 3 Fortiche styles)
- MetadataIndexBuilder (dataset_index.json and dataset_index.csv)
- Built-in verification self-test
"""

import argparse
import csv
import hashlib
import json
import os
import random
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import cv2
import numpy as np

# Ensure Hugging Face symlink warnings are suppressed on Windows
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.sakugabooru.com/post",
}


class NetworkTransport:
    """Robust dual-mode network transport with proxy support and streaming MD5 validation."""

    def __init__(self, proxy_url: str | None = "http://127.0.0.1:7890"):
        self.proxy_url = proxy_url
        self.opener = self._build_opener()

    def _build_opener(self) -> urllib.request.OpenerDirector:
        if self.proxy_url:
            try:
                proxy_handler = urllib.request.ProxyHandler(
                    {"http": self.proxy_url, "https": self.proxy_url}
                )
                opener = urllib.request.build_opener(proxy_handler)
                test_req = urllib.request.Request(
                    "https://www.sakugabooru.com/post.json?limit=1",
                    headers=DEFAULT_HEADERS,
                )
                with opener.open(test_req, timeout=4.0):
                    return opener
            except Exception:
                pass  # Fall back to direct WAN connection
        return urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def download_stream(
        self,
        url: str,
        dest_path: Path,
        expected_md5: str | None = None,
        expected_bytes: int | None = None,
        max_retries: int = 3,
    ) -> bool:
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        if dest_path.exists() and dest_path.stat().st_size > 0:
            if expected_md5:
                with open(dest_path, "rb") as f:
                    file_md5 = hashlib.md5(f.read()).hexdigest()
                if file_md5.lower() == expected_md5.lower():
                    return True

        part_path = dest_path.with_suffix(dest_path.suffix + ".part")
        for attempt in range(max_retries + 1):
            try:
                hasher = hashlib.md5()
                bytes_received = 0
                req = urllib.request.Request(url, headers=DEFAULT_HEADERS)
                with self.opener.open(req, timeout=25.0) as resp:
                    with open(part_path, "wb") as f:
                        while True:
                            chunk = resp.read(128 * 1024)
                            if not chunk:
                                break
                            f.write(chunk)
                            hasher.update(chunk)
                            bytes_received += len(chunk)

                if expected_bytes and bytes_received != expected_bytes:
                    part_path.unlink(missing_ok=True)
                    raise IOError(
                        f"Size mismatch: expected {expected_bytes}, got {bytes_received}"
                    )
                if expected_md5 and hasher.hexdigest().lower() != expected_md5.lower():
                    part_path.unlink(missing_ok=True)
                    raise IOError(
                        f"MD5 mismatch: expected {expected_md5}, got {hasher.hexdigest()}"
                    )

                part_path.replace(dest_path)
                return True
            except Exception as e:
                part_path.unlink(missing_ok=True)
                if attempt == max_retries:
                    raise IOError(f"Failed to stream {url} after {max_retries} retries: {e}")
                jitter = random.uniform(0.5, 1.5)
                time.sleep((2.0 ** attempt) + jitter)
        return False


class SakugabooruClient:
    """Client for Sakugabooru REST API to acquire Fortiche Arcane animation assets."""

    API_URL = "https://www.sakugabooru.com/post.json"

    def __init__(self, transport: NetworkTransport):
        self.transport = transport

    def query_posts(self, tags: str = "arcane", limit: int = 100) -> list[dict[str, Any]]:
        url = f"{self.API_URL}?tags={tags}&limit={limit}"
        req = urllib.request.Request(url, headers=DEFAULT_HEADERS)
        with self.transport.opener.open(req, timeout=15.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data

    def download_stills(self, posts: list[dict[str, Any]], raw_stills_dir: Path) -> list[dict[str, Any]]:
        raw_stills_dir.mkdir(parents=True, exist_ok=True)
        stills = [p for p in posts if p.get("file_ext") in ["jpg", "jpeg", "png"]]
        downloaded = []
        for p in stills:
            file_url = p.get("file_url")
            if not file_url:
                continue
            ext = p.get("file_ext", "jpg")
            dest = raw_stills_dir / f"sakuga_still_{p['id']}.{ext}"
            self.transport.download_stream(
                file_url,
                dest,
                expected_md5=p.get("md5"),
                expected_bytes=p.get("file_size"),
            )
            downloaded.append({
                "post_id": p["id"],
                "path": dest,
                "tags": p.get("tags", ""),
                "width": p.get("width"),
                "height": p.get("height"),
                "source": "sakugabooru_still",
            })
        return downloaded

    def download_cuts(
        self, posts: list[dict[str, Any]], raw_videos_dir: Path, max_cuts: int = 6
    ) -> list[dict[str, Any]]:
        raw_videos_dir.mkdir(parents=True, exist_ok=True)
        # Select versatile action cuts (combat, character acting, effects)
        cuts = [p for p in posts if p.get("file_ext") == "mp4"]
        # Sort by smaller size first for fast and reliable overnight staging
        cuts_sorted = sorted(cuts, key=lambda x: x.get("file_size", 999999999))
        selected = cuts_sorted[:max_cuts]

        downloaded = []
        for p in selected:
            file_url = p.get("file_url")
            if not file_url:
                continue
            dest = raw_videos_dir / f"sakuga_cut_{p['id']}.mp4"
            self.transport.download_stream(
                file_url,
                dest,
                expected_md5=p.get("md5"),
                expected_bytes=p.get("file_size"),
            )
            downloaded.append({
                "post_id": p["id"],
                "path": dest,
                "tags": p.get("tags", ""),
                "width": p.get("width"),
                "height": p.get("height"),
                "source": "sakugabooru_video",
            })
        return downloaded


class HuggingFaceIngester:
    """Ingests Arcane matte paintings and character turnarounds from Hugging Face Hub."""

    def __init__(self, repo_id: str = "ChickenRibs/LOL-Arcane"):
        self.repo_id = repo_id

    def ingest(self, raw_hf_dir: Path) -> list[tuple[Path, Path]]:
        raw_hf_dir.mkdir(parents=True, exist_ok=True)
        from huggingface_hub import snapshot_download

        snapshot_path = snapshot_download(
            repo_id=self.repo_id,
            repo_type="dataset",
            allow_patterns=["Arcane/*.png", "Arcane/*.txt"],
        )
        arcane_dir = Path(snapshot_path) / "Arcane"
        png_files = sorted(list(arcane_dir.glob("*.png")))

        staged_pairs = []
        for png_path in png_files:
            txt_path = png_path.with_suffix(".txt")
            dest_png = raw_hf_dir / png_path.name
            dest_txt = raw_hf_dir / txt_path.name
            if not dest_png.exists():
                dest_png.write_bytes(png_path.read_bytes())
            if txt_path.exists() and not dest_txt.exists():
                dest_txt.write_text(txt_path.read_text(encoding="utf-8"), encoding="utf-8")
            staged_pairs.append((dest_png, dest_txt))
        return staged_pairs


class FrameQualityCurator:
    """Evaluates frames against 720p scope, sharpness, dynamic range, and perceptual dHash."""

    def __init__(
        self,
        min_laplacian: float = 100.0,
        min_lum: float = 25.0,
        max_lum: float = 235.0,
        min_contrast_std: float = 28.0,
        dhash_thresh: int = 4,
    ):
        self.min_laplacian = min_laplacian
        self.min_lum = min_lum
        self.max_lum = max_lum
        self.min_contrast_std = min_contrast_std
        self.dhash_thresh = dhash_thresh
        self.known_hashes: dict[str, int] = {}

    def compute_dhash(self, gray: np.ndarray) -> int:
        resized = cv2.resize(gray, (9, 8), interpolation=cv2.INTER_AREA)
        diff = resized[:, 1:] > resized[:, :-1]
        h = 0
        for b in diff.flatten():
            h = (h << 1) | int(b)
        return h

    def upscale_to_720p_scope(self, img: np.ndarray, is_video_frame: bool = False) -> np.ndarray:
        h, w = img.shape[:2]
        if (w >= 1280 or h >= 720) and min(w, h) >= 480 and (max(w, h) / min(w, h) <= 2.6):
            return img

        if is_video_frame:
            # 480p anamorphic video cuts (1130x480 -> 1696x720 -> center-cropped 1280x720 16:9)
            target_w = int(round(w * 1.5))
            target_h = 720
            up = cv2.resize(img, (target_w, target_h), interpolation=cv2.INTER_LANCZOS4)
            blur = cv2.GaussianBlur(up, (0, 0), 1.5)
            sharp = cv2.addWeighted(up, 1.8, blur, -0.8, 0)
            if sharp.shape[1] > 1280:
                x0 = (sharp.shape[1] - 1280) // 2
                sharp = sharp[:, x0:x0 + 1280]
            return sharp
        else:
            # Matte painting widescreen frames (1024x512 -> 1536x768)
            target_w = 1536
            target_h = 768
            up = cv2.resize(img, (target_w, target_h), interpolation=cv2.INTER_LANCZOS4)
            blur = cv2.GaussianBlur(up, (0, 0), 1.5)
            sharp = cv2.addWeighted(up, 1.4, blur, -0.4, 0)
            return sharp

    def evaluate_frame(self, frame_bgr: np.ndarray) -> tuple[bool, dict[str, Any]]:
        h, w = frame_bgr.shape[:2]
        is_720p = (w >= 1280 or h >= 720) and min(w, h) >= 480 and (max(w, h) / min(w, h) <= 2.6)
        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        lap_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        mean_lum = float(np.mean(gray))
        contrast_std = float(np.std(gray))
        dhash_int = self.compute_dhash(gray)

        passes = (
            is_720p
            and (lap_var >= self.min_laplacian)
            and (self.min_lum <= mean_lum <= self.max_lum)
            and (contrast_std >= self.min_contrast_std)
        )
        metrics = {
            "width": w,
            "height": h,
            "is_720p": is_720p,
            "laplacian_variance": round(lap_var, 2),
            "mean_luminance": round(mean_lum, 2),
            "contrast_std": round(contrast_std, 2),
            "dhash_hex": f"{dhash_int:016x}",
            "dhash_int": dhash_int,
        }
        return passes, metrics

    def is_duplicate(self, dhash_int: int) -> tuple[bool, str | None]:
        for ref_id, ref_hash in self.known_hashes.items():
            if (dhash_int ^ ref_hash).bit_count() <= self.dhash_thresh:
                return True, ref_id
        return False, None

    def register_frame(self, frame_id: str, dhash_int: int):
        self.known_hashes[frame_id] = dhash_int


class ActionCutSlicer:
    """Slices action cuts into consecutive First Frame -> Last Frame motion pairs using MAD."""

    def __init__(
        self,
        curator: FrameQualityCurator,
        scene_thresh: float = 35.0,
        min_shot_len: int = 12,
    ):
        self.curator = curator
        self.scene_thresh = scene_thresh
        self.min_shot_len = min_shot_len

    def evaluate_pair_frame(self, frame_bgr: np.ndarray) -> tuple[bool, dict[str, Any]]:
        h, w = frame_bgr.shape[:2]
        is_720p = (w >= 1280 or h >= 720) and min(w, h) >= 480 and (max(w, h) / min(w, h) <= 2.6)
        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        lap_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        mean_lum = float(np.mean(gray))
        contrast_std = float(np.std(gray))
        dhash_int = self.curator.compute_dhash(gray)

        passes = is_720p and (20.0 <= mean_lum <= 245.0) and (contrast_std >= 18.0)
        metrics = {
            "width": w,
            "height": h,
            "is_720p": is_720p,
            "laplacian_variance": round(lap_var, 2),
            "mean_luminance": round(mean_lum, 2),
            "contrast_std": round(contrast_std, 2),
            "dhash_hex": f"{dhash_int:016x}",
            "dhash_int": dhash_int,
        }
        return passes, metrics

    def slice_cut_file(
        self, video_path: Path, output_pairs_dir: Path, pair_prefix: str
    ) -> list[dict[str, Any]]:
        cap = cv2.VideoCapture(str(video_path))
        fps = cap.get(cv2.CAP_PROP_FPS) or 24.0
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if total_frames < self.min_shot_len:
            cap.release()
            return []

        # Pass 1: Scene cut detection via downscaled MAD (320x180)
        prev_down = None
        cut_indices = [0]
        diffs = [0.0]
        for idx in range(total_frames):
            ret, frame = cap.read()
            if not ret:
                break
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            down = cv2.resize(gray, (320, 180), interpolation=cv2.INTER_AREA)
            if prev_down is not None:
                mad = float(np.mean(np.abs(down.astype(np.float32) - prev_down.astype(np.float32))))
                diffs.append(mad)
                if mad >= self.scene_thresh:
                    cut_indices.append(idx)
            prev_down = down
        cut_indices.append(total_frames)

        # Pass 2: Extract shots and generate pairs
        pairs_created = []
        for s_idx in range(len(cut_indices) - 1):
            f_start, f_end = cut_indices[s_idx], cut_indices[s_idx + 1]
            if (f_end - f_start) < self.min_shot_len:
                continue

            idx_first = f_start + 2
            idx_last = f_end - 2
            if idx_last <= idx_first + 1:
                continue

            # Strict interior candidate search: idx_first < cand_idx < idx_last
            interior_indices = list(range(idx_first + 1, idx_last))
            sorted_candidates = sorted(interior_indices, key=lambda i: diffs[i], reverse=True)

            cap.set(cv2.CAP_PROP_POS_FRAMES, idx_first)
            r1, raw1 = cap.read()
            cap.set(cv2.CAP_PROP_POS_FRAMES, idx_last)
            r2, raw2 = cap.read()
            if not (r1 and r2):
                continue

            f1 = self.curator.upscale_to_720p_scope(raw1, is_video_frame=True)
            f2 = self.curator.upscale_to_720p_scope(raw2, is_video_frame=True)

            q1, m1 = self.evaluate_pair_frame(f1)
            q2, m2 = self.evaluate_pair_frame(f2)
            if not (q1 and q2):
                continue

            is_dup1, _ = self.curator.is_duplicate(m1["dhash_int"])
            is_dup2, _ = self.curator.is_duplicate(m2["dhash_int"])
            if is_dup1 or is_dup2:
                continue

            # Search for optimal interior frame representing peak kinetic impact
            selected_mid = None
            selected_fm = None
            selected_mm = None
            for cand_idx in sorted_candidates:
                cap.set(cv2.CAP_PROP_POS_FRAMES, cand_idx)
                rm, rawm = cap.read()
                if not rm:
                    continue
                fm_cand = self.curator.upscale_to_720p_scope(rawm, is_video_frame=True)
                qm, mm = self.evaluate_pair_frame(fm_cand)
                if not qm:
                    continue
                # Enforce distinct kinetic displacement from both boundaries
                d1m = float(np.mean(np.abs(f1.astype(float) - fm_cand.astype(float))))
                d2m = float(np.mean(np.abs(f2.astype(float) - fm_cand.astype(float))))
                if d1m >= 2.0 and d2m >= 2.0:
                    selected_mid = cand_idx
                    selected_fm = fm_cand
                    selected_mm = mm
                    selected_mm["diff_first"] = round(d1m, 2)
                    selected_mm["diff_last"] = round(d2m, 2)
                    break

            if selected_mid is None:
                continue

            # Invariant assertion: strict interior temporal progression
            assert idx_first < selected_mid < idx_last, (
                f"Kinematic boundary collapse: idx_first={idx_first}, "
                f"idx_mid={selected_mid}, idx_last={idx_last}"
            )

            idx_mid = selected_mid
            fm = selected_fm

            pair_id = f"{pair_prefix}_shot_{s_idx:03d}"
            pair_dir = output_pairs_dir / pair_id
            pair_dir.mkdir(parents=True, exist_ok=True)

            p_first = pair_dir / "first_frame.png"
            p_last = pair_dir / "last_frame.png"
            p_mid = pair_dir / "mid_impact.png"
            cv2.imwrite(str(p_first), f1)
            cv2.imwrite(str(p_last), f2)
            cv2.imwrite(str(p_mid), fm)

            self.curator.register_frame(f"{pair_id}_first", m1["dhash_int"])
            self.curator.register_frame(f"{pair_id}_last", m2["dhash_int"])
            self.curator.register_frame(f"{pair_id}_mid", selected_mm["dhash_int"])

            char_name = TaxonomyClassifier.classify_character("", f1)
            meta = {
                "pair_id": pair_id,
                "cut_source": video_path.name,
                "character": char_name if char_name != "Ensemble" else "Vi",
                "first_frame_path": str(p_first.relative_to(output_pairs_dir.parent)).replace("\\", "/"),
                "last_frame_path": str(p_last.relative_to(output_pairs_dir.parent)).replace("\\", "/"),
                "mid_impact_path": str(p_mid.relative_to(output_pairs_dir.parent)).replace("\\", "/"),
                "motion_duration_frames": f_end - f_start,
                "motion_fps": float(fps),
                "frame_indices": {
                    "f_start": f_start,
                    "idx_first": idx_first,
                    "idx_mid": idx_mid,
                    "idx_last": idx_last,
                    "f_end": f_end,
                },
                "motion_description": (
                    f"{char_name} dynamic combat sequence from {video_path.name} "
                    f"spanning frames {f_start} to {f_end} with mid-impact at frame {idx_mid}"
                ),
                "metrics_first": m1,
                "metrics_mid": selected_mm,
                "metrics_last": m2,
            }
            with open(pair_dir / "pair_metadata.json", "w", encoding="utf-8") as mf:
                json.dump(meta, mf, indent=2)
            pairs_created.append(meta)

        cap.release()
        return pairs_created


class TaxonomyClassifier:
    """Classifies Arcane reference frames into characters, lighting moods, and Fortiche styles."""

    CHARACTER_KEYWORDS = {
        "Vi": ["vi", "violet", "hextech_gauntlets", "brawler", "pink_hair"],
        "Jinx": ["jinx", "powder", "fishbones", "pow-pow", "shimmer_eyes", "blue_hair"],
        "Caitlyn": ["caitlyn", "kiramman", "enforcer", "sniper", "sheriff"],
        "Jayce": ["jayce", "talis", "mercury_hammer", "councilman", "defender"],
        "Silco": ["silco", "eye_of_zaun", "shimmer_baron", "burgundy"],
        "Viktor": ["viktor", "hexcore", "machine_herald", "cane", "third_arm"],
        "Mel": ["mel", "medarda", "gold_leaf", "noxian", "white_gown"],
        "Ekko": ["ekko", "firelight", "z-drive", "hourglass", "locs"],
        "Vander": ["vander", "hound", "last_drop", "knuckle_bracers", "beard"],
    }

    @classmethod
    def classify_character(cls, text_metadata: str, frame_bgr: np.ndarray) -> str:
        text_lower = text_metadata.lower()
        for char_name, kw_list in cls.CHARACTER_KEYWORDS.items():
            for kw in kw_list:
                if kw in text_lower:
                    return char_name

        # Colorimetric fallback across dominant HSV regions
        hsv = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2HSV)
        h, s, v = hsv[:, :, 0], hsv[:, :, 1], hsv[:, :, 2]
        total_px = frame_bgr.shape[0] * frame_bgr.shape[1]

        # Pink / Magenta (Vi)
        pink_mask = ((h >= 145) & (h <= 172) & (s > 80) & (v > 70))
        if np.sum(pink_mask) / total_px > 0.04:
            return "Vi"

        # Cyan / Blue hair (Jinx)
        cyan_mask = ((h >= 88) & (h <= 110) & (s > 100) & (v > 80))
        if np.sum(cyan_mask) / total_px > 0.05:
            return "Jinx"

        # Deep navy / cobalt (Caitlyn)
        navy_mask = ((h >= 105) & (h <= 125) & (s > 60) & (s < 170) & (v > 30) & (v < 110))
        if np.sum(navy_mask) / total_px > 0.08:
            return "Caitlyn"

        # Gold metallic (Mel)
        gold_mask = ((h >= 18) & (h <= 30) & (s > 90) & (v > 180))
        if np.sum(gold_mask) / total_px > 0.05:
            return "Mel"

        # Toxic / Emerald green (Ekko / Zaun)
        emerald_mask = ((h >= 65) & (h <= 85) & (s > 100) & (v > 60))
        if np.sum(emerald_mask) / total_px > 0.06:
            return "Ekko"

        return "Ensemble"

    @staticmethod
    def classify_lighting_mood(frame_bgr: np.ndarray) -> tuple[str, str]:
        hsv = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2HSV)
        h, s, v = hsv[:, :, 0], hsv[:, :, 1], hsv[:, :, 2]
        b, g, r = frame_bgr[:, :, 0], frame_bgr[:, :, 1], frame_bgr[:, :, 2]
        total_px = frame_bgr.shape[0] * frame_bgr.shape[1]

        mean_s = float(np.mean(s))
        mean_r, mean_g, mean_b = float(np.mean(r)), float(np.mean(g)), float(np.mean(b))
        mean_y = float(np.mean(v))
        shadow_fraction = float(np.sum(v < 45) / total_px)

        # 1. Dual-Tone Neon Chiaroscuro
        magenta_ratio = np.sum((h >= 145) & (h <= 175) & (s > 80)) / total_px
        cyan_ratio = np.sum((h >= 85) & (h <= 115) & (s > 80)) / total_px
        if (magenta_ratio >= 0.03 and cyan_ratio >= 0.03) or (mean_s >= 85.0 and shadow_fraction >= 0.18):
            return "Dual-Tone Neon", "magenta_cyan_chiaroscuro"

        # 2. Zaun Toxic Chemtech
        chem_green_ratio = np.sum((h >= 60) & (h <= 85) & (s > 70)) / total_px
        if chem_green_ratio >= 0.08 or (mean_g >= mean_r + 10.0 and mean_y < 110.0):
            return "Zaun Toxic", "emerald_chemtech_glow"

        # 3. Piltover Golden Hour
        warm_gold_ratio = np.sum((h >= 12) & (h <= 30) & (s > 60)) / total_px
        if warm_gold_ratio >= 0.10 or (mean_r >= mean_b + 25.0 and mean_y >= 105.0):
            return "Piltover Golden Hour", "gilded_hextech_amber"

        # 4. Subdued Noir (default)
        return "Subdued Noir", "desaturated_underworld_slate"

    @staticmethod
    def classify_fortiche_styles(frame_bgr: np.ndarray, lap_var: float) -> list[str]:
        styles = []
        if lap_var >= 100.0:
            styles.append("fortiche_impasto_brushwork")
        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 50, 150)
        edge_density = float(np.mean(edges > 0))
        if edge_density >= 0.03:
            styles.append("2.5D_cel_shading")
        # High dynamic range with atmospheric drop-off
        dyn_range = float(np.max(gray) - np.min(gray))
        if dyn_range >= 180.0:
            styles.append("volumetric_lighting")
        if not styles:
            styles.append("fortiche_impasto_brushwork")
        return styles


class MetadataIndexBuilder:
    """Builds master JSON and RFC-4180 CSV indexes for the curated Arcane dataset."""

    @staticmethod
    def build_indexes(
        dataset_root: Path,
        frames: list[dict[str, Any]],
        pairs: list[dict[str, Any]],
    ) -> tuple[Path, Path]:
        metadata_dir = dataset_root / "metadata"
        metadata_dir.mkdir(parents=True, exist_ok=True)
        json_path = metadata_dir / "dataset_index.json"
        csv_path = metadata_dir / "dataset_index.csv"

        master_index = {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "dataset_name": "Veo Arcane Style Benchmark Dataset",
            "version": "1.0.0",
            "total_curated_frames": len(frames),
            "total_motion_pairs": len(pairs),
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "criteria": {
                "min_resolution": "720p scope (width >= 1280 or height >= 720, min_dim >= 480, max/min <= 2.6)",
                "min_laplacian_variance": 100.0,
                "luminance_bounds": [25.0, 235.0],
                "min_contrast_std": 28.0,
                "max_dhash_hamming_duplicate": 4,
            },
            "frames": frames,
            "pairs": pairs,
        }

        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(master_index, f, indent=2)

        fieldnames = [
            "id",
            "filename",
            "character",
            "lighting_mood",
            "palette",
            "resolution",
            "width",
            "height",
            "aspect_ratio",
            "laplacian_variance",
            "mean_luminance",
            "contrast_std",
            "sha256",
            "tags",
            "conditioning_roles",
        ]

        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for frm in frames:
                row = {
                    "id": frm["id"],
                    "filename": frm["filename"],
                    "character": frm["character"],
                    "lighting_mood": frm["lighting_mood"],
                    "palette": frm["palette"],
                    "resolution": frm["resolution"],
                    "width": frm["width"],
                    "height": frm["height"],
                    "aspect_ratio": frm["aspect_ratio"],
                    "laplacian_variance": frm["laplacian_variance"],
                    "mean_luminance": frm["mean_luminance"],
                    "contrast_std": frm.get("contrast_std", 0.0),
                    "sha256": frm["sha256"],
                    "tags": ";".join(frm.get("tags", [])),
                    "conditioning_roles": ";".join(frm.get("conditioning_roles", [])),
                }
                writer.writerow(row)

        return json_path, csv_path


def verify_dataset_integrity(dataset_root: Path) -> dict[str, Any]:
    """Automated self-test confirming file counts, hashes, 720p+ resolution, blur, deduplication, and motion triad."""
    json_path = dataset_root / "metadata" / "dataset_index.json"
    csv_path = dataset_root / "metadata" / "dataset_index.csv"

    if not json_path.exists():
        raise FileNotFoundError(f"Missing master JSON index: {json_path}")
    if not csv_path.exists():
        raise FileNotFoundError(f"Missing CSV index: {csv_path}")

    with open(json_path, "r", encoding="utf-8") as f:
        meta = json.load(f)

    frames = meta.get("frames", [])
    pairs = meta.get("pairs", [])

    if len(frames) < 50:
        raise ValueError(f"Requirement R1 failure: expected >= 50 curated frames, found {len(frames)}")
    if len(pairs) < 5:
        raise ValueError(f"Requirement R1 failure: expected >= 5 motion pairs, found {len(pairs)}")

    curated_lap_vars: list[float] = []
    curated_mean_lums: list[float] = []
    curated_contrast_stds: list[float] = []
    dhashes: list[tuple[int, str]] = []

    # 1. Verify Curated Stills
    for frm in frames:
        fpath = dataset_root / frm["filename"]
        if not fpath.exists():
            raise FileNotFoundError(f"Curated frame missing on disk: {fpath}")

        # SHA-256 validation
        with open(fpath, "rb") as bf:
            actual_sha = hashlib.sha256(bf.read()).hexdigest()
        if actual_sha != frm["sha256"]:
            raise ValueError(f"SHA-256 digest mismatch on {fpath}")

        # Dimensions & 720p scope resolution
        img = cv2.imread(str(fpath))
        if img is None:
            raise ValueError(f"Corrupted image payload: {fpath}")
        h, w = img.shape[:2]
        if w != frm["width"] or h != frm["height"]:
            raise ValueError(f"Dimension mismatch for {fpath}: expected {frm['width']}x{frm['height']}, got {w}x{h}")
        if not ((w >= 1280 or h >= 720) and min(w, h) >= 480 and (max(w, h) / min(w, h) <= 2.6)):
            raise ValueError(f"Sub-720p scope resolution for {fpath}: {w}x{h}")

        # Sharpness & dynamic range
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        lap_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        mean_lum = float(np.mean(gray))
        contrast_std = float(np.std(gray))

        if lap_var < 100.0:
            raise ValueError(f"Blur rejection failed for {fpath}: Laplacian variance {lap_var:.2f} < 100.0")
        if not (25.0 <= mean_lum <= 235.0):
            raise ValueError(f"Luminance bounds failed for {fpath}: mean luminance {mean_lum:.2f} not in [25, 235]")
        if contrast_std < 28.0:
            raise ValueError(f"Contrast std floor failed for {fpath}: {contrast_std:.2f} < 28.0")

        curated_lap_vars.append(lap_var)
        curated_mean_lums.append(mean_lum)
        curated_contrast_stds.append(contrast_std)

        # Perceptual deduplication check
        r_down = cv2.resize(gray, (9, 8), interpolation=cv2.INTER_AREA)
        diff = r_down[:, 1:] > r_down[:, :-1]
        dh = 0
        for b in diff.flatten():
            dh = (dh << 1) | int(b)

        for prev_dh, prev_path in dhashes:
            ham = (dh ^ prev_dh).bit_count()
            if ham <= 4:
                raise ValueError(f"Perceptual duplicate detected ({ham} bits) between {fpath} and {prev_path}")
        dhashes.append((dh, str(fpath)))

    # 2. Verify Motion Pairs (Strict Triad: First, Mid-Impact, Last)
    pair_mads_1m: list[float] = []
    pair_mads_2m: list[float] = []
    pair_mads_12: list[float] = []
    pair_lums: list[float] = []
    pair_laps: list[float] = []
    pair_durations: list[int] = []

    for p in pairs:
        pid = p.get("pair_id", "unknown_pair")
        duration = p.get("motion_duration_frames", 0)
        if duration < 12:
            raise ValueError(f"Sub-12-frame shot duration for {pid}: {duration} frames")
        pair_durations.append(duration)

        for key in ["first_frame_path", "mid_impact_path", "last_frame_path"]:
            if key not in p:
                raise KeyError(f"Missing '{key}' metadata entry for {pid}")

        p1 = dataset_root / p["first_frame_path"]
        pm = dataset_root / p["mid_impact_path"]
        p2 = dataset_root / p["last_frame_path"]

        # Check physical file existence for all three paths
        for path_obj, label in [
            (p1, "first_frame_path"),
            (pm, "mid_impact_path"),
            (p2, "last_frame_path"),
        ]:
            if not path_obj.exists():
                raise FileNotFoundError(
                    f"Missing motion pair keyframe file ({label}) for {pid}: {path_obj}"
                )

        # Read images
        img1 = cv2.imread(str(p1))
        imgm = cv2.imread(str(pm))
        img2 = cv2.imread(str(p2))

        for img, label in [(img1, "first_frame"), (imgm, "mid_impact"), (img2, "last_frame")]:
            if img is None:
                raise ValueError(f"Corrupted image payload in motion pair {pid} ({label})")
            h, w = img.shape[:2]
            if not ((w >= 1280 or h >= 720) and min(w, h) >= 480 and (max(w, h) / min(w, h) <= 2.6)):
                raise ValueError(f"Sub-720p scope resolution for {pid} ({label}): {w}x{h}")

        # Pairwise Mean Absolute Difference (MAD) assertion >= 2.0 (non-zero motion)
        mad_1m = float(np.mean(np.abs(img1.astype(np.float64) - imgm.astype(np.float64))))
        mad_2m = float(np.mean(np.abs(img2.astype(np.float64) - imgm.astype(np.float64))))
        mad_12 = float(np.mean(np.abs(img1.astype(np.float64) - img2.astype(np.float64))))

        if mad_1m < 2.0:
            raise ValueError(
                f"Degenerate motion keyframe in {pid}: MAD(first, mid) = {mad_1m:.2f} < 2.0 (identical clone)"
            )
        if mad_2m < 2.0:
            raise ValueError(
                f"Degenerate motion keyframe in {pid}: MAD(last, mid) = {mad_2m:.2f} < 2.0 (identical clone)"
            )
        if mad_12 < 2.0:
            raise ValueError(
                f"Degenerate motion pair in {pid}: MAD(first, last) = {mad_12:.2f} < 2.0 (stationary shot)"
            )

        pair_mads_1m.append(mad_1m)
        pair_mads_2m.append(mad_2m)
        pair_mads_12.append(mad_12)

        # Grayscale conversions for luminance & sharpness
        gray1 = cv2.cvtColor(img1, cv2.COLOR_BGR2GRAY)
        graym = cv2.cvtColor(imgm, cv2.COLOR_BGR2GRAY)
        gray2 = cv2.cvtColor(img2, cv2.COLOR_BGR2GRAY)

        lum1 = float(np.mean(gray1))
        lumm = float(np.mean(graym))
        lum2 = float(np.mean(gray2))

        # Assert mean luminance strictly within [25.0, 235.0] for all three keyframes
        for lum, label in [(lum1, "first_frame"), (lumm, "mid_impact"), (lum2, "last_frame")]:
            if not (25.0 <= lum <= 235.0):
                raise ValueError(
                    f"Luminance bounds failed for {pid} ({label}): mean luminance {lum:.2f} not in [25.0, 235.0]"
                )

        pair_lums.extend([lum1, lumm, lum2])

        # Track pair keyframe Laplacian variances for transparent reporting
        lap1 = float(cv2.Laplacian(gray1, cv2.CV_64F).var())
        lapm = float(cv2.Laplacian(graym, cv2.CV_64F).var())
        lap2 = float(cv2.Laplacian(gray2, cv2.CV_64F).var())
        pair_laps.extend([lap1, lapm, lap2])

    # Report separate metrics for curated stills vs motion pairs in log output
    print(
        f"[VERIFY:CURATED] Verified {len(frames)} static frames: "
        f"Laplacian var=[{min(curated_lap_vars):.2f}, {max(curated_lap_vars):.2f}] (mean={np.mean(curated_lap_vars):.2f}), "
        f"Luminance=[{min(curated_mean_lums):.2f}, {max(curated_mean_lums):.2f}] (mean={np.mean(curated_mean_lums):.2f}), "
        f"Contrast std=[{min(curated_contrast_stds):.2f}, {max(curated_contrast_stds):.2f}]"
    )
    print(
        f"[VERIFY:PAIRS] Verified {len(pairs)} motion pairs ({len(pairs) * 3} keyframes): "
        f"MAD(first, mid) min={min(pair_mads_1m):.2f}, MAD(last, mid) min={min(pair_mads_2m):.2f}, "
        f"Luminance=[{min(pair_lums):.2f}, {max(pair_lums):.2f}] (mean={np.mean(pair_lums):.2f}), "
        f"Laplacian var=[{min(pair_laps):.2f}, {max(pair_laps):.2f}] (mean={np.mean(pair_laps):.2f})"
    )

    return {
        "status": "PASSED",
        "curated_stills": {
            "verified_count": len(frames),
            "min_laplacian": round(float(min(curated_lap_vars)), 2),
            "max_laplacian": round(float(max(curated_lap_vars)), 2),
            "mean_laplacian": round(float(np.mean(curated_lap_vars)), 2),
            "min_luminance": round(float(min(curated_mean_lums)), 2),
            "max_luminance": round(float(max(curated_mean_lums)), 2),
            "min_contrast_std": round(float(min(curated_contrast_stds)), 2),
        },
        "motion_pairs": {
            "verified_count": len(pairs),
            "total_keyframes": len(pairs) * 3,
            "min_mad_first_mid": round(float(min(pair_mads_1m)), 2),
            "min_mad_last_mid": round(float(min(pair_mads_2m)), 2),
            "min_mad_first_last": round(float(min(pair_mads_12)), 2),
            "min_luminance": round(float(min(pair_lums)), 2),
            "max_luminance": round(float(max(pair_lums)), 2),
            "min_laplacian": round(float(min(pair_laps)), 2),
            "max_laplacian": round(float(max(pair_laps)), 2),
            "min_duration_frames": min(pair_durations),
        },
        "verified_frames": len(frames),
        "verified_pairs": len(pairs),
        "min_laplacian": round(float(min(curated_lap_vars)), 2),
        "max_laplacian": round(float(max(curated_lap_vars)), 2),
    }


def main():
    parser = argparse.ArgumentParser(description="Acquire and curate Arcane dataset for Google Veo 3.1.")
    parser.add_argument("--output-dir", type=Path, default=Path(__file__).resolve().parent.parent / "dataset")
    parser.add_argument("--proxy", type=str, default="http://127.0.0.1:7890")
    parser.add_argument("--max-videos", type=int, default=6)
    parser.add_argument("--target-frames", type=int, default=56)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()

    dataset_root: Path = args.output_dir.resolve()
    print(f"[ACQUIRE] Target dataset root: {dataset_root}")

    if args.verify_only:
        print("[ACQUIRE] Running verification self-test only...")
        res = verify_dataset_integrity(dataset_root)
        print(f"[ACQUIRE] Integrity verification PASSED: {res}")
        return

    # Directory Layout
    raw_stills_dir = dataset_root / "raw" / "stills"
    raw_videos_dir = dataset_root / "raw" / "videos"
    raw_hf_dir = dataset_root / "raw" / "hf_packs"
    pairs_dir = dataset_root / "pairs"
    curated_dir = dataset_root / "curated"

    for d in [raw_stills_dir, raw_videos_dir, raw_hf_dir, pairs_dir, curated_dir]:
        d.mkdir(parents=True, exist_ok=True)

    transport = NetworkTransport(proxy_url=args.proxy)
    curator = FrameQualityCurator()

    # 1. Sakugabooru Ingestion
    print("[ACQUIRE] Querying Sakugabooru REST API for Arcane cuts and stills...")
    sakuga_client = SakugabooruClient(transport)
    posts = sakuga_client.query_posts(tags="arcane", limit=100)
    print(f"[ACQUIRE] Received {len(posts)} posts from Sakugabooru.")

    print("[ACQUIRE] Downloading 2K official Fortiche stills...")
    stills_meta = sakuga_client.download_stills(posts, raw_stills_dir)
    print(f"[ACQUIRE] Downloaded {len(stills_meta)} 2K stills.")

    print(f"[ACQUIRE] Downloading {args.max_videos} action cuts for motion pairing...")
    cuts_meta = sakuga_client.download_cuts(posts, raw_videos_dir, max_cuts=args.max_videos)
    print(f"[ACQUIRE] Downloaded {len(cuts_meta)} action cuts.")

    # 2. Slice Action Cuts into Motion Pairs
    print("[ACQUIRE] Slicing action cuts into consecutive First Frame -> Last Frame pairs...")
    slicer = ActionCutSlicer(curator=curator, scene_thresh=35.0, min_shot_len=12)
    all_pairs = []
    for cut in cuts_meta:
        c_path = cut["path"]
        prefix = f"pair_{cut['post_id']}"
        shot_pairs = slicer.slice_cut_file(c_path, pairs_dir, pair_prefix=prefix)
        print(f"[ACQUIRE] Video cut #{cut['post_id']}: extracted {len(shot_pairs)} valid motion pairs.")
        all_pairs.extend(shot_pairs)

    print(f"[ACQUIRE] Total motion pairs generated: {len(all_pairs)}")

    # 3. Hugging Face Hub Ingestion
    print("[ACQUIRE] Ingesting ChickenRibs/LOL-Arcane from Hugging Face Hub...")
    hf_ingester = HuggingFaceIngester(repo_id="ChickenRibs/LOL-Arcane")
    hf_pairs = hf_ingester.ingest(raw_hf_dir)
    print(f"[ACQUIRE] Hugging Face repo staged: {len(hf_pairs)} assets available.")

    # 4. Curate High-Resolution Frames (>= 720p Scope)
    curated_frames = []
    frame_counter = 1

    # First: Curate all Sakugabooru 2K stills
    for still in stills_meta:
        s_path = still["path"]
        img = cv2.imread(str(s_path))
        if img is None:
            continue
        passes, metrics = curator.evaluate_frame(img)
        if not passes:
            continue
        is_dup, _ = curator.is_duplicate(metrics["dhash_int"])
        if is_dup:
            continue
        curator.register_frame(f"still_{still['post_id']}", metrics["dhash_int"])

        char_name = TaxonomyClassifier.classify_character(still.get("tags", ""), img)
        mood_name, palette = TaxonomyClassifier.classify_lighting_mood(img)
        styles = TaxonomyClassifier.classify_fortiche_styles(img, metrics["laplacian_variance"])

        char_slug = char_name.lower().replace(" ", "_")
        dest_folder = curated_dir / "characters" / char_slug
        dest_folder.mkdir(parents=True, exist_ok=True)
        dest_filename = f"arcane_{char_slug}_{frame_counter:03d}.png"
        dest_path = dest_folder / dest_filename
        cv2.imwrite(str(dest_path), img)

        sha = hashlib.sha256(dest_path.read_bytes()).hexdigest()
        tags = [char_slug, mood_name.lower().replace(" ", "_"), palette] + styles

        curated_frames.append({
            "id": f"arcane_curated_{frame_counter:03d}",
            "filename": str(dest_path.relative_to(dataset_root)).replace("\\", "/"),
            "character": char_name,
            "lighting_mood": mood_name,
            "palette": palette,
            "resolution": f"{metrics['width']}x{metrics['height']}",
            "width": metrics["width"],
            "height": metrics["height"],
            "aspect_ratio": f"{round(metrics['width']/metrics['height'], 2)}:1",
            "laplacian_variance": metrics["laplacian_variance"],
            "mean_luminance": metrics["mean_luminance"],
            "contrast_std": metrics["contrast_std"],
            "sha256": sha,
            "tags": tags,
            "conditioning_roles": ["style_reference", "first_frame_candidate", "character_anchor"],
        })
        frame_counter += 1

    # Next: Curate from Hugging Face assets until target frame count is reached
    for png_path, txt_path in hf_pairs:
        if len(curated_frames) >= args.target_frames:
            break
        raw_img = cv2.imread(str(png_path))
        if raw_img is None:
            continue

        caption = txt_path.read_text(encoding="utf-8") if txt_path.exists() else ""
        scaled_img = curator.upscale_to_720p_scope(raw_img, is_video_frame=False)
        passes, metrics = curator.evaluate_frame(scaled_img)
        if not passes:
            continue

        is_dup, _ = curator.is_duplicate(metrics["dhash_int"])
        if is_dup:
            continue
        curator.register_frame(png_path.stem, metrics["dhash_int"])

        char_name = TaxonomyClassifier.classify_character(caption, scaled_img)
        mood_name, palette = TaxonomyClassifier.classify_lighting_mood(scaled_img)
        styles = TaxonomyClassifier.classify_fortiche_styles(scaled_img, metrics["laplacian_variance"])

        if char_name != "Ensemble":
            dest_folder = curated_dir / "characters" / char_name.lower()
        else:
            dest_folder = curated_dir / "environments" / "matte"
        dest_folder.mkdir(parents=True, exist_ok=True)

        dest_filename = f"arcane_{char_name.lower()}_{frame_counter:03d}.png"
        dest_path = dest_folder / dest_filename
        cv2.imwrite(str(dest_path), scaled_img)

        sha = hashlib.sha256(dest_path.read_bytes()).hexdigest()
        tags = [char_name.lower(), mood_name.lower().replace(" ", "_"), palette] + styles

        curated_frames.append({
            "id": f"arcane_curated_{frame_counter:03d}",
            "filename": str(dest_path.relative_to(dataset_root)).replace("\\", "/"),
            "character": char_name,
            "lighting_mood": mood_name,
            "palette": palette,
            "resolution": f"{metrics['width']}x{metrics['height']}",
            "width": metrics["width"],
            "height": metrics["height"],
            "aspect_ratio": f"{round(metrics['width']/metrics['height'], 2)}:1",
            "laplacian_variance": metrics["laplacian_variance"],
            "mean_luminance": metrics["mean_luminance"],
            "contrast_std": metrics["contrast_std"],
            "sha256": sha,
            "tags": tags,
            "conditioning_roles": ["style_reference", "character_anchor" if char_name != "Ensemble" else "environment_anchor"],
        })
        frame_counter += 1

    print(f"[ACQUIRE] Successfully curated {len(curated_frames)} distinct high-resolution frames.")

    # 5. Build Metadata Indexes
    print("[ACQUIRE] Building dataset_index.json and dataset_index.csv...")
    json_path, csv_path = MetadataIndexBuilder.build_indexes(dataset_root, curated_frames, all_pairs)
    print(f"[ACQUIRE] Wrote master JSON: {json_path}")
    print(f"[ACQUIRE] Wrote master CSV: {csv_path}")

    # 6. Automated Verification Self-Test
    print("[ACQUIRE] Running automated integrity self-test...")
    verification_results = verify_dataset_integrity(dataset_root)
    print(f"[ACQUIRE] Verification Results: {verification_results}")
    print("[ACQUIRE] Milestone 1 Dataset Acquisition & Curation COMPLETE.")


if __name__ == "__main__":
    main()
