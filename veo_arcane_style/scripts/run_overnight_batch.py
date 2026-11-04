"""Autonomous Overnight Batch Runner for Google Veo 3.1 Arcane Style Generation.

Implements Milestone 3 (Requirement R3):
- 5-stage sequential progression state machine
- Atomic crash-consistent checkpointing (overnight_checkpoint.json)
- Unbuffered dual logging with stage formatting
- Graceful signal handling (SIGINT/SIGTERM/SIGBREAK)
- Target video generation for pair_170629_shot_000 (Vi) and pair_270000_shot_015 (Caitlyn)
- Programmatic media validation (ISO-BMFF, 720p+, H.264, AAC audio)
- Visual contact sheet comparison generator
- Mirroring to brain directory
- Anti-cheat compliance: strictly 0 OpenCV zoom/pan fallbacks, 0 audio stream stripping
"""

from __future__ import annotations

import argparse
import asyncio
import datetime
import enum
import json
import logging
import os
from pathlib import Path
import random
import shutil
import signal
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np

try:
    import imageio_ffmpeg
except ImportError:
    imageio_ffmpeg = None  # type: ignore[assignment]

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from veo_arcane_style.src.arcane_prompt_engine import ArcanePromptEngine
from veo_arcane_style.src.veo_style_pipeline import VeoStylePipeline

# Ensure unbuffered stream output
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(line_buffering=True)

DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"
DEFAULT_DATASET_DIR = Path(__file__).resolve().parent.parent / "dataset"
DEFAULT_BRAIN_DIR = Path(
    r"C:\Users\Orakul Grey\.gemini\antigravity\brain\94dd6a04-54e7-4e8c-9551-224cace4f85f"
)
DEFAULT_PROXY = "http://127.0.0.1:7890"

CANONICAL_CLIP_NAMES: Dict[str, str] = {
    "pair_170629_shot_000": "arcane_clip_01_zaun_duel_720p.mp4",
    "pair_270000_shot_015": "arcane_clip_02_piltover_hextech_720p.mp4",
}


class BatchStage(str, enum.Enum):
    """5-stage progression state machine enums."""

    STAGE_1_DATASET = "STAGE_1_DATASET"
    STAGE_2_PROMPT_MATRIX = "STAGE_2_PROMPT_MATRIX"
    STAGE_3_GENERATION = "STAGE_3_GENERATION"
    STAGE_4_VERIFICATION = "STAGE_4_VERIFICATION"
    STAGE_5_MIRRORING = "STAGE_5_MIRRORING"
    COMPLETED = "COMPLETED"


class AtomicCheckpoint:
    """Crash-consistent atomic checkpoint manager."""

    def __init__(self, filepath: Path, force: bool = False, auto_load: bool = True) -> None:
        self.filepath = Path(filepath)
        self.force = force
        self.data: Dict[str, Any] = self._default_state()
        if auto_load and self.filepath.is_file() and not self.force:
            self.load()

    def _default_state(self) -> Dict[str, Any]:
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        return {
            "version": "1.0.0",
            "created_at": now,
            "updated_at": now,
            "overall_status": "initialized",
            "current_stage": BatchStage.STAGE_1_DATASET.value,
            "completed_stages": [],
            "config": {},
            "dataset_status": {},
            "prompt_matrix": [],
            "clips": {},
            "verification_report": {},
            "mirror_status": {},
        }

    def load(self) -> bool:
        """Load state from disk if checkpoint exists and is valid JSON."""
        if not self.filepath.is_file():
            return False
        try:
            content = self.filepath.read_text(encoding="utf-8")
            loaded = json.loads(content)
            if isinstance(loaded, dict) and "version" in loaded:
                self.data = loaded
                return True
        except Exception as exc:
            logging.getLogger("overnight_batch").warning(
                f"Failed to read existing checkpoint {self.filepath}: {exc}"
            )
        return False

    def save_atomic(self, force: Optional[bool] = None) -> None:
        """Write checkpoint to temporary file, flush to disk, and atomic replace."""
        allow_force = self.force if force is None else force
        if self.filepath.is_file() and not allow_force:
            try:
                on_disk = json.loads(self.filepath.read_text(encoding="utf-8"))
                if isinstance(on_disk, dict):
                    on_disk_stages = len(on_disk.get("completed_stages", []))
                    in_mem_stages = len(self.data.get("completed_stages", []))
                    on_disk_status = on_disk.get("overall_status")
                    in_mem_status = self.data.get("overall_status")
                    on_disk_is_mock = bool(
                        on_disk.get("config", {}).get("mock")
                        or on_disk.get("config", {}).get("dry_run")
                    )

                    # Refuse to overwrite completed/in-progress genuine work with uninitialized default state
                    if (
                        on_disk_status in ("completed", "in_progress")
                        and in_mem_status == "initialized"
                        and not on_disk_is_mock
                    ):
                        raise PermissionError(
                            f"Safety Guard: Refusing to overwrite active {on_disk_status} checkpoint "
                            f"at {self.filepath} with an uninitialized state. Pass force=True to override."
                        )
                    # Refuse to regress completed stages count for genuine checkpoints
                    if on_disk_stages > in_mem_stages and not on_disk_is_mock:
                        raise PermissionError(
                            f"Safety Guard: Refusing to downgrade checkpoint stages ({on_disk_stages} -> {in_mem_stages}) "
                            f"without force=True."
                        )
            except PermissionError:
                raise
            except Exception:
                pass

        self.filepath.parent.mkdir(parents=True, exist_ok=True)
        self.data["updated_at"] = datetime.datetime.now(
            datetime.timezone.utc
        ).isoformat()
        tmp_path = self.filepath.with_suffix(self.filepath.suffix + ".tmp")
        payload = json.dumps(self.data, indent=2)
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(payload)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, self.filepath)

    def is_stage_completed(self, stage: BatchStage) -> bool:
        """Check if stage is marked completed in checkpoint."""
        return stage.value in self.data.get("completed_stages", [])

    def mark_stage_completed(self, stage: BatchStage) -> None:
        """Mark stage completed and persist atomically."""
        completed = self.data.setdefault("completed_stages", [])
        if stage.value not in completed:
            completed.append(stage.value)
        self.data["current_stage"] = stage.value
        self.save_atomic()


class StageLogFilter(logging.Filter):
    """Logging filter attaching current execution stage to log records."""

    def __init__(self, stage: str = "BATCH") -> None:
        super().__init__()
        self.stage = stage

    def filter(self, record: logging.LogRecord) -> bool:
        record.stage = self.stage
        return True


def setup_dual_logging(
    log_file: Path, stage_filter: StageLogFilter
) -> logging.Logger:
    """Configure unbuffered stream and persistent file logging."""
    log_file.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("overnight_batch")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(stage)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setLevel(logging.INFO)
    stream_handler.setFormatter(formatter)
    stream_handler.addFilter(stage_filter)
    logger.addHandler(stream_handler)

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)
    file_handler.addFilter(stage_filter)
    logger.addHandler(file_handler)

    return logger


class MediaValidator:
    """Programmatic validator for generated video deliverables."""

    @staticmethod
    def get_ffmpeg_exe() -> str:
        """Resolve bundled or system ffmpeg executable."""
        if imageio_ffmpeg is not None:
            try:
                exe = imageio_ffmpeg.get_ffmpeg_exe()
                if exe and Path(exe).is_file():
                    return str(exe)
            except Exception:
                pass
        system_exe = shutil.which("ffmpeg")
        if system_exe:
            return system_exe
        raise RuntimeError("No ffmpeg executable discovered on system")

    @classmethod
    def check_faststart(cls, video_path: Path) -> bool:
        """Check ISO-BMFF FastStart layout (moov box before mdat)."""
        if not video_path.is_file() or video_path.stat().st_size < 100:
            return False
        header = video_path.read_bytes()[:262144]  # Read first 256KB
        moov_idx = header.find(b"moov")
        mdat_idx = header.find(b"mdat")
        if moov_idx != -1 and (mdat_idx == -1 or moov_idx < mdat_idx):
            return True
        return False

    @classmethod
    def inspect_streams_ffmpeg(cls, video_path: Path) -> Dict[str, Any]:
        """Inspect video and audio stream codecs using ffmpeg output."""
        ffmpeg_exe = cls.get_ffmpeg_exe()
        cmd = [ffmpeg_exe, "-hide_banner", "-i", str(video_path)]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        stderr = res.stderr.lower()

        has_h264 = "h264" in stderr or "avc1" in stderr
        has_aac = "aac" in stderr

        return {
            "has_video": "video:" in stderr,
            "has_h264": has_h264,
            "has_audio": "audio:" in stderr,
            "has_aac": has_aac,
            "raw_stream_output": stderr,
        }

    @classmethod
    def validate_deliverable(cls, video_path: Path) -> Dict[str, Any]:
        """Complete programmatic verification of container, video, and audio."""
        if not video_path.is_file():
            return {"valid": False, "error": f"File does not exist: {video_path}"}
        size_bytes = video_path.stat().st_size
        if size_bytes < 50000:
            return {
                "valid": False,
                "error": f"File size too small: {size_bytes} bytes",
            }

        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            return {"valid": False, "error": "OpenCV cannot open video container"}

        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        cap.release()

        duration = (frame_count / fps) if fps > 0 else 0.0
        faststart = cls.check_faststart(video_path)

        streams = cls.inspect_streams_ffmpeg(video_path)
        is_hd = height >= 720 or width >= 1280
        valid = (
            is_hd
            and streams["has_h264"]
            and streams["has_aac"]
            and duration >= 3.0
            and faststart
        )

        return {
            "valid": valid,
            "file_size_bytes": size_bytes,
            "width": width,
            "height": height,
            "fps": fps,
            "frame_count": frame_count,
            "duration": round(duration, 2),
            "faststart": faststart,
            "video_codec_h264": streams["has_h264"],
            "audio_codec_aac": streams["has_aac"],
            "native_audio": streams["has_aac"],
        }


class ContactSheetGenerator:
    """Generates side-by-side visual comparison contact sheets."""

    PANEL_W = 640
    PANEL_H = 360

    @classmethod
    def extract_clip_triad(
        cls, video_path: Path
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Extract start, mid-point, and final frames from video."""
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            raise RuntimeError(f"Cannot open video for frame extraction: {video_path}")
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 1)

        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
        ret0, f0 = cap.read()

        cap.set(cv2.CAP_PROP_POS_FRAMES, max(0, frame_count // 2))
        ret_mid, f_mid = cap.read()

        cap.set(cv2.CAP_PROP_POS_FRAMES, max(0, frame_count - 1))
        ret_end, f_end = cap.read()
        cap.release()

        f0 = f0 if ret0 else np.zeros((720, 1280, 3), dtype=np.uint8)
        f_mid = f_mid if ret_mid else np.zeros((720, 1280, 3), dtype=np.uint8)
        f_end = f_end if ret_end else np.zeros((720, 1280, 3), dtype=np.uint8)
        return f0, f_mid, f_end

    @classmethod
    def _render_labeled_panel(cls, img: np.ndarray, label: str) -> np.ndarray:
        resized = cv2.resize(img, (cls.PANEL_W, cls.PANEL_H))
        overlay = resized.copy()
        cv2.rectangle(overlay, (0, 0), (cls.PANEL_W, 36), (20, 20, 20), -1)
        cv2.addWeighted(overlay, 0.7, resized, 0.3, 0, resized)
        cv2.putText(
            resized,
            label,
            (15, 25),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )
        return resized

    @classmethod
    def create_clip_comparison(
        cls, pair: Dict[str, Any], video_path: Path, out_sheet: Path
    ) -> Path:
        """Create 2x3 comparison sheet: Top=Arcane Ground Truth, Bottom=Veo Generated."""
        f1_path = Path(pair["first_frame_path"])
        f2_path = Path(pair.get("mid_impact_path") or pair["first_frame_path"])
        f3_path = Path(pair["last_frame_path"])

        gt1 = cv2.imread(str(f1_path))
        gt2 = cv2.imread(str(f2_path)) if f2_path.is_file() else gt1
        gt3 = cv2.imread(str(f3_path))

        p_gt1 = cls._render_labeled_panel(gt1, "Arcane GT: First Frame")
        p_gt2 = cls._render_labeled_panel(gt2, "Arcane GT: Mid Impact")
        p_gt3 = cls._render_labeled_panel(gt3, "Arcane GT: Last Frame")
        top_row = np.hstack([p_gt1, p_gt2, p_gt3])

        vf0, vf_mid, vf_end = cls.extract_clip_triad(video_path)
        p_vf0 = cls._render_labeled_panel(vf0, "Veo 3.1: Start (0.0s)")
        p_vf_mid = cls._render_labeled_panel(vf_mid, "Veo 3.1: Mid Phase")
        p_vf_end = cls._render_labeled_panel(vf_end, "Veo 3.1: Final Frame")
        bot_row = np.hstack([p_vf0, p_vf_mid, p_vf_end])

        header = np.full((60, cls.PANEL_W * 3, 3), 15, dtype=np.uint8)
        title = (
            f"Arcane Style Conditioning: {pair.get('pair_id')} | "
            f"Character: {pair.get('character')} | Palette: {pair.get('palette')}"
        )
        cv2.putText(
            header,
            title,
            (25, 40),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.85,
            (0, 215, 255),
            2,
            cv2.LINE_AA,
        )

        sheet = np.vstack([header, top_row, bot_row])
        out_sheet.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(out_sheet), sheet)
        return out_sheet

    @classmethod
    def create_master_sheet(
        cls, comparison_sheets: List[Path], out_master: Path
    ) -> Path:
        """Compose master contact sheet combining all comparison sheets."""
        images = [cv2.imread(str(p)) for p in comparison_sheets if p.is_file()]
        if not images:
            raise ValueError("No comparison sheets available to assemble master")
        master = np.vstack(images)
        out_master.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(out_master), master)
        return out_master


class MockFlowClient:
    """Mock Google Flow client generating compliant test media for offline testing."""

    def __init__(self, logger: Optional[logging.Logger] = None) -> None:
        self.logger = logger or logging.getLogger("overnight_batch")

    async def generate_start_and_end_clip(
        self,
        prompt: str,
        start_image: Path,
        end_image: Path,
        duration: int,
        out_path: Path,
    ) -> Dict[str, Any]:
        """Generate compliant 720p H.264 video with native AAC audio and FastStart."""
        out_path.parent.mkdir(parents=True, exist_ok=True)
        ffmpeg_exe = MediaValidator.get_ffmpeg_exe()

        cmd = [
            ffmpeg_exe,
            "-y",
            "-loop",
            "1",
            "-i",
            str(start_image),
            "-f",
            "lavfi",
            "-i",
            "anullsrc=channel_layout=stereo:sample_rate=44100",
            "-c:v",
            "libx264",
            "-t",
            str(duration),
            "-pix_fmt",
            "yuv420p",
            "-vf",
            (
                "scale=1280:720:force_original_aspect_ratio=decrease,"
                "pad=1280:720:(ow-iw)/2:(oh-ih)/2"
            ),
            "-c:a",
            "aac",
            "-shortest",
            "-movflags",
            "+faststart",
            str(out_path),
        ]

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(
                f"Mock ffmpeg generation failed (code {proc.returncode}): {stderr.decode('utf-8', errors='replace')}"
            )

        return {
            "ok": True,
            "prompt": prompt,
            "duration": duration,
            "first_frame": str(start_image),
            "last_frame": str(end_image),
            "output_path": str(out_path),
            "native_audio": True,
        }


class OvernightBatchRunner:
    """Autonomous 5-stage overnight batch runner for Google Veo 3.1 styling."""

    def __init__(self, config: Dict[str, Any]) -> None:
        self.config = config
        is_mock_or_dry = bool(config.get("mock") or config.get("dry_run"))

        if is_mock_or_dry:
            # Never allow mock or dry-run to default to production paths
            if not config.get("output_dir") or Path(config["output_dir"]).resolve() == DEFAULT_OUTPUT_DIR.resolve():
                self.output_dir = DEFAULT_OUTPUT_DIR / "_mock_scratch"
            else:
                self.output_dir = Path(config["output_dir"])
            self.output_dir.mkdir(parents=True, exist_ok=True)

            if not config.get("checkpoint_file"):
                self.checkpoint_file = self.output_dir / "mock_checkpoint.json"
            else:
                self.checkpoint_file = Path(config["checkpoint_file"])
        else:
            self.output_dir = Path(config.get("output_dir") or DEFAULT_OUTPUT_DIR)
            self.output_dir.mkdir(parents=True, exist_ok=True)

            checkpoint_path = config.get("checkpoint_file")
            self.checkpoint_file = (
                Path(checkpoint_path)
                if checkpoint_path
                else self.output_dir / "overnight_checkpoint.json"
            )

        force_flag = bool(config.get("force"))
        self.checkpoint = AtomicCheckpoint(self.checkpoint_file, force=force_flag, auto_load=True)
        if self.checkpoint_file.is_file() and not force_flag:
            self.checkpoint.load()

        log_path = config.get("log_file")
        self.log_file = (
            Path(log_path)
            if log_path
            else self.output_dir / "logs" / "overnight_batch.log"
        )
        self.stage_filter = StageLogFilter("INIT")
        self.logger = setup_dual_logging(self.log_file, self.stage_filter)

        self.dataset_dir = Path(config.get("dataset_dir") or DEFAULT_DATASET_DIR)
        self.mirror_dir = Path(config.get("mirror_dir") or DEFAULT_BRAIN_DIR)
        self.pipeline = VeoStylePipeline(
            dataset_dir=self.dataset_dir,
            output_dir=self.output_dir,
            proxy_url=config.get("proxy") or DEFAULT_PROXY,
        )

        self.shutdown_requested = False
        self._register_signals()

    def _register_signals(self) -> None:
        def _handle_sig(sig: int, _frame: Any) -> None:
            self.logger.warning(
                f"Received termination signal {sig}. Intercepting for graceful checkpoint..."
            )
            self.shutdown_requested = True
            self.checkpoint.data["overall_status"] = "interrupted"
            self.checkpoint.save_atomic()
            sys.exit(130)

        for sig_name in ("SIGINT", "SIGTERM", "SIGBREAK"):
            sig_enum = getattr(signal, sig_name, None)
            if sig_enum is not None:
                try:
                    signal.signal(sig_enum, _handle_sig)
                except (ValueError, OSError):
                    pass

    def _set_stage(self, stage: BatchStage) -> None:
        self.stage_filter.stage = stage.value
        self.checkpoint.data["current_stage"] = stage.value

    def stage_1_dataset(self) -> Dict[str, Any]:
        """Stage 1: Verify dataset inventory and integrity."""
        self._set_stage(BatchStage.STAGE_1_DATASET)
        self.logger.info("Starting Stage 1: Dataset Staging & Integrity Audit...")

        if self.checkpoint.is_stage_completed(BatchStage.STAGE_1_DATASET) and not self.config.get("force"):
            self.logger.info("Stage 1 already marked completed in checkpoint. Skipping.")
            return self.checkpoint.data.get("dataset_status", {})

        idx = self.pipeline.load_dataset_index()
        frames = idx.get("frames", [])
        pairs = idx.get("pairs", [])

        if len(frames) < 50:
            raise ValueError(f"Dataset frames count {len(frames)} < required threshold 50")
        if len(pairs) < 5:
            raise ValueError(f"Dataset motion pairs count {len(pairs)} < required threshold 5")

        status = {
            "valid": True,
            "total_frames": len(frames),
            "total_pairs": len(pairs),
            "dataset_name": idx.get("dataset_name"),
            "verified_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }
        self.checkpoint.data["dataset_status"] = status
        self.checkpoint.mark_stage_completed(BatchStage.STAGE_1_DATASET)
        self.logger.info(f"Stage 1 Complete: Verified {len(frames)} curated frames and {len(pairs)} pairs.")
        return status

    def stage_2_prompt_matrix(self) -> List[Dict[str, Any]]:
        """Stage 2: Formulate 6-stage Fortiche lexical conditioning matrix."""
        self._set_stage(BatchStage.STAGE_2_PROMPT_MATRIX)
        self.logger.info("Starting Stage 2: Lexical Conditioning Matrix Generation...")

        if self.checkpoint.is_stage_completed(BatchStage.STAGE_2_PROMPT_MATRIX) and not self.config.get("force"):
            self.logger.info("Stage 2 already marked completed in checkpoint. Skipping.")
            return self.checkpoint.data.get("prompt_matrix", [])

        all_pairs = self.pipeline.list_pairs()
        pair_dict = {p["pair_id"]: p for p in all_pairs}

        clips_arg = str(self.config.get("clips") or "2").strip()
        selected_pairs: List[Dict[str, Any]] = []

        if "," in clips_arg:
            req_ids = [cid.strip() for cid in clips_arg.split(",") if cid.strip()]
            for cid in req_ids:
                if cid in pair_dict:
                    selected_pairs.append(pair_dict[cid])
                else:
                    raise KeyError(f"Requested pair '{cid}' not found in dataset index")
        else:
            try:
                count = int(clips_arg)
                # Ensure canonical pair_170629_shot_000 and pair_270000_shot_015 are prioritized
                preferred = ["pair_170629_shot_000", "pair_270000_shot_015"]
                for pref_id in preferred:
                    if pref_id in pair_dict and len(selected_pairs) < count:
                        selected_pairs.append(pair_dict[pref_id])
                for p in all_pairs:
                    if len(selected_pairs) >= count:
                        break
                    if p["pair_id"] not in [sp["pair_id"] for sp in selected_pairs]:
                        selected_pairs.append(p)
            except ValueError:
                if clips_arg in pair_dict:
                    selected_pairs.append(pair_dict[clips_arg])
                else:
                    raise ValueError(f"Invalid --clips argument: {clips_arg}")

        matrix: List[Dict[str, Any]] = []
        for pair in selected_pairs:
            pair_id = pair["pair_id"]
            loaded = self.pipeline.load_pair(pair_id)
            prompt = self.pipeline.build_i2v_prompt(loaded)
            out_name = CANONICAL_CLIP_NAMES.get(pair_id, f"arcane_clip_{pair_id}_720p.mp4")
            out_file = self.output_dir / out_name

            entry = {
                "pair_id": pair_id,
                "character": pair.get("character", "Vi"),
                "palette": pair.get("palette", "magenta_cyan_chiaroscuro"),
                "first_frame_path": str(loaded["first_frame_path"]),
                "last_frame_path": str(loaded["last_frame_path"]),
                "mid_impact_path": str(loaded.get("mid_impact_path") or ""),
                "prompt": prompt,
                "target_output_name": out_name,
                "target_output_path": str(out_file),
            }
            matrix.append(entry)

        prompt_matrix_path = self.output_dir / "prompt_matrix.json"
        prompt_matrix_path.write_text(json.dumps(matrix, indent=2), encoding="utf-8")

        self.checkpoint.data["prompt_matrix"] = matrix
        self.checkpoint.mark_stage_completed(BatchStage.STAGE_2_PROMPT_MATRIX)
        self.logger.info(f"Stage 2 Complete: Synthesized prompt matrix for {len(matrix)} clips.")
        return matrix


    def enforce_mock_rejection(self) -> None:
        """Reject mock or simulated checkpoints when current execution is live."""
        current_is_mock = bool(self.config.get("mock") or self.config.get("dry_run"))
        if current_is_mock:
            return

        ckpt_config = self.checkpoint.data.get("config", {})
        was_mock = ckpt_config.get("mock") is True or ckpt_config.get("dry_run") is True

        clips_data = self.checkpoint.data.get("clips", {})
        has_mock_clips = any(
            c.get("status") in ("simulated", "mock") or c.get("mock") is True
            for c in clips_data.values()
        )

        completed_stages = self.checkpoint.data.get("completed_stages", [])
        has_later_stages = any(
            s in completed_stages
            for s in (
                BatchStage.STAGE_3_GENERATION.value,
                BatchStage.STAGE_4_VERIFICATION.value,
                BatchStage.STAGE_5_MIRRORING.value,
                BatchStage.COMPLETED.value,
            )
        )

        if was_mock or has_mock_clips or (has_later_stages and not clips_data):
            self.logger.warning(
                "Strict Mock Rejection: Checkpoint contains mock/dry-run configuration or simulated clips, "
                "but current execution is LIVE (mock=False). Resetting Stage 3, Stage 4, Stage 5 and clips "
                "to force genuine live generation."
            )
            self.checkpoint.data["completed_stages"] = [
                s for s in completed_stages
                if s not in (
                    BatchStage.STAGE_3_GENERATION.value,
                    BatchStage.STAGE_4_VERIFICATION.value,
                    BatchStage.STAGE_5_MIRRORING.value,
                    BatchStage.COMPLETED.value,
                )
            ]
            self.checkpoint.data["clips"] = {}
            self.checkpoint.data["verification_report"] = {}
            self.checkpoint.data["mirror_status"] = {}
            if self.checkpoint.data.get("overall_status") in ("completed", "failed"):
                self.checkpoint.data["overall_status"] = "in_progress"
            self.checkpoint.save_atomic(force=True)

    async def stage_3_generation(self) -> Dict[str, Any]:
        """Stage 3: Execute reference-conditioned video generation for clips."""
        self._set_stage(BatchStage.STAGE_3_GENERATION)
        self.logger.info("Starting Stage 3: Reference Conditioning Video Generation...")

        # Enforce strict mock rejection before checking completion
        self.enforce_mock_rejection()

        if self.checkpoint.is_stage_completed(BatchStage.STAGE_3_GENERATION) and not self.config.get("force"):
            self.logger.info("Stage 3 already marked completed in checkpoint. Skipping.")
            return self.checkpoint.data.get("clips", {})

        matrix = self.checkpoint.data.get("prompt_matrix") or self.stage_2_prompt_matrix()
        clips_state = self.checkpoint.data.setdefault("clips", {})
        duration = int(self.config.get("duration") or 4)
        dry_run = bool(self.config.get("dry_run"))
        mock_mode = bool(self.config.get("mock"))
        max_retries = int(self.config.get("max_retries") or 3)

        mock_client = MockFlowClient(self.logger) if mock_mode else None

        for entry in matrix:
            pair_id = entry["pair_id"]
            out_file = Path(entry["target_output_path"])
            clip_rec = clips_state.get(pair_id, {})

            # Idempotency check: Skip if completed and file valid on disk
            # In live mode, verify file size is genuine (>= 200KB) and not a mock clip
            is_genuine = (
                not mock_mode
                and not dry_run
                and out_file.is_file()
                and out_file.stat().st_size >= 200000
                and clip_rec.get("status") == "completed"
                and clip_rec.get("mock") is not True
            )
            is_mock_valid = (
                (mock_mode or dry_run)
                and out_file.is_file()
                and out_file.stat().st_size >= 50000
                and clip_rec.get("status") in ("completed", "simulated")
            )

            if (is_genuine or is_mock_valid) and not self.config.get("force"):
                self.logger.info(f"Clip {pair_id} ({out_file.name}) already completed. Skipping.")
                continue

            if dry_run:
                self.logger.info(f"[DRY-RUN] Simulated generation for {pair_id} -> {out_file.name}")
                clips_state[pair_id] = {
                    "status": "simulated",
                    "output_path": str(out_file),
                    "duration": duration,
                    "prompt": entry["prompt"],
                    "completed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                }
                self.checkpoint.save_atomic()
                continue

            # Generation loop with jittered exponential backoff
            success = False
            last_err: Optional[str] = None
            for attempt in range(1, max_retries + 1):
                self.logger.info(f"Generating clip {pair_id} (Attempt {attempt}/{max_retries})...")
                try:
                    res = await self.pipeline.generate_i2v_clip(
                        pair_id=pair_id,
                        prompt_override=entry["prompt"],
                        duration=duration,
                        client=mock_client,
                        output_path=out_file,
                    )
                    success = True
                    clips_state[pair_id] = {
                        "status": "completed",
                        "attempts": attempt,
                        "output_path": str(out_file),
                        "duration": duration,
                        "native_audio": res.get("native_audio", True),
                        "error": None,
                        "completed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    }
                    self.checkpoint.save_atomic()
                    self.logger.info(f"Successfully generated clip {pair_id} -> {out_file.name}")
                    break
                except Exception as exc:
                    last_err = str(exc)
                    self.logger.warning(f"Clip generation failed on attempt {attempt}: {exc}")
                    if attempt < max_retries:
                        backoff = min(60.0, 4.0 * (2 ** (attempt - 1))) + random.uniform(0.0, 2.0)
                        self.logger.info(f"Waiting {backoff:.2f}s before retry...")
                        await asyncio.sleep(backoff)

            if not success:
                clips_state[pair_id] = {
                    "status": "failed",
                    "attempts": max_retries,
                    "output_path": str(out_file),
                    "duration": duration,
                    "error": last_err,
                }
                self.checkpoint.save_atomic()
                raise RuntimeError(f"Clip generation permanently failed for {pair_id}: {last_err}")

        self.checkpoint.mark_stage_completed(BatchStage.STAGE_3_GENERATION)
        self.logger.info("Stage 3 Complete: All configured clips processed.")
        return clips_state

    def stage_4_verification(self) -> Dict[str, Any]:
        """Stage 4: Programmatic media validation and visual contact sheets."""
        self._set_stage(BatchStage.STAGE_4_VERIFICATION)
        self.logger.info("Starting Stage 4: Dual Verification Suite...")

        if self.checkpoint.is_stage_completed(BatchStage.STAGE_4_VERIFICATION) and not self.config.get("force"):
            self.logger.info("Stage 4 already marked completed in checkpoint. Skipping.")
            return self.checkpoint.data.get("verification_report", {})

        clips_state = self.checkpoint.data.get("clips", {})
        matrix = self.checkpoint.data.get("prompt_matrix", [])
        matrix_map = {m["pair_id"]: m for m in matrix}
        dry_run = bool(self.config.get("dry_run"))

        details: List[Dict[str, Any]] = []
        comparison_sheets: List[Path] = []
        all_passed = True

        for pair_id, cinfo in clips_state.items():
            out_file = Path(cinfo.get("output_path", ""))
            if dry_run or cinfo.get("status") == "simulated":
                details.append({"pair_id": pair_id, "status": "simulated_pass", "valid": True})
                continue

            v_res = MediaValidator.validate_deliverable(out_file)
            v_res["pair_id"] = pair_id

            # Anti-mock validation in live mode: genuine 4s 720p Veo 3.1 clips are >= 200 KB
            if not dry_run and not bool(self.config.get("mock")) and v_res["valid"]:
                if v_res.get("file_size_bytes", 0) < 200000:
                    v_res["valid"] = False
                    v_res["error"] = (
                        f"File size {v_res.get('file_size_bytes')} bytes is suspiciously small for genuine "
                        f"Veo 3.1 720p clip (minimum 200,000 bytes required). Suspected mock deliverable."
                    )

            details.append(v_res)
            if not v_res["valid"]:
                all_passed = False
                self.logger.error(f"Verification FAILED for {pair_id}: {v_res.get('error')}")
            else:
                self.logger.info(f"Verification PASSED for {pair_id} ({v_res['width']}x{v_res['height']}, {v_res['duration']}s, AAC={v_res['audio_codec_aac']})")

            # Generate side-by-side comparison sheet
            if pair_id in matrix_map and out_file.is_file():
                sheet_path = self.output_dir / "contact_sheets" / f"comparison_{pair_id}.png"
                ContactSheetGenerator.create_clip_comparison(matrix_map[pair_id], out_file, sheet_path)
                comparison_sheets.append(sheet_path)
                self.logger.info(f"Rendered comparison sheet: {sheet_path.name}")

        master_sheet_path: Optional[Path] = None
        if comparison_sheets:
            master_sheet_path = self.output_dir / "master_verification_sheet.png"
            ContactSheetGenerator.create_master_sheet(comparison_sheets, master_sheet_path)
            self.logger.info(f"Rendered master verification sheet: {master_sheet_path.name}")

        report = {
            "all_passed": all_passed,
            "total_clips": len(details),
            "verified_clips": sum(1 for d in details if d.get("valid")),
            "details": details,
            "contact_sheets": [str(p) for p in comparison_sheets],
            "master_contact_sheet": str(master_sheet_path) if master_sheet_path else None,
            "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }

        # Save verification report JSON & Markdown
        (self.output_dir / "verification_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        md_lines = [
            "# Veo 3.1 Arcane Video Verification Report",
            f"- Generated: {report['generated_at']}",
            f"- Overall Status: {'PASS' if all_passed else 'FAIL'}",
            f"- Verified Clips: {report['verified_clips']} / {report['total_clips']}",
            "\n## Deliverable Details",
        ]
        for d in details:
            md_lines.append(f"- **{d.get('pair_id')}**: valid={d.get('valid')}, size={d.get('file_size_bytes', 0)} bytes, duration={d.get('duration')}s")
        (self.output_dir / "verification_report.md").write_text("\n".join(md_lines), encoding="utf-8")

        self.checkpoint.data["verification_report"] = report
        if all_passed:
            self.checkpoint.mark_stage_completed(BatchStage.STAGE_4_VERIFICATION)
            self.logger.info("Stage 4 Complete: Verification status ALL PASSED.")
        else:
            self.logger.error("Stage 4 Incomplete: Verification status FAIL.")
        return report


    def stage_5_mirroring(self) -> Dict[str, Any]:
        """Stage 5: Mirror deliverables to persistent brain repository."""
        self._set_stage(BatchStage.STAGE_5_MIRRORING)
        self.logger.info(f"Starting Stage 5: Mirroring Deliverables to {self.mirror_dir}...")

        # Strict protection against mock/dry-run pollution of production brain directory
        is_mock_or_dry = bool(self.config.get("mock") or self.config.get("dry_run"))
        is_default_brain = self.mirror_dir.resolve() == DEFAULT_BRAIN_DIR.resolve()
        if is_mock_or_dry and is_default_brain:
            raise PermissionError(
                f"Refusing to mirror mock or dry-run artifacts to production brain directory ({DEFAULT_BRAIN_DIR}). "
                "Only genuine live deliverables may be mirrored to production brain. Pass an explicit non-default "
                "--mirror-dir for test runs."
            )

        if self.checkpoint.is_stage_completed(BatchStage.STAGE_5_MIRRORING) and not self.config.get("force"):
            self.logger.info("Stage 5 already marked completed in checkpoint. Skipping.")
            return self.checkpoint.data.get("mirror_status", {})

        self.mirror_dir.mkdir(parents=True, exist_ok=True)
        copied: List[str] = []

        # Collect deliverables to mirror (excluding checkpoint file from bulk loop)
        files_to_mirror: List[Path] = []
        for ext in ("*.mp4", "*.json", "*.md"):
            for f in self.output_dir.glob(ext):
                if f.name != self.checkpoint_file.name:
                    files_to_mirror.append(f)

        # Include contact sheets
        cs_dir = self.output_dir / "contact_sheets"
        if cs_dir.is_dir():
            files_to_mirror.extend(cs_dir.glob("*.png"))
        files_to_mirror.extend(self.output_dir.glob("*.png"))

        # Include log file
        if self.log_file.is_file():
            files_to_mirror.append(self.log_file)

        # Mirror each file
        for src in set(files_to_mirror):
            if not src.is_file():
                continue
            rel = src.relative_to(self.output_dir) if self.output_dir in src.parents else Path(src.name)
            dest = self.mirror_dir / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)

            # Validate copy parity
            if dest.stat().st_size != src.stat().st_size:
                raise IOError(f"Mirror copy mismatch for {src.name}: {src.stat().st_size} != {dest.stat().st_size}")
            copied.append(str(dest))
            self.logger.info(f"Mirrored: {src.name} -> {dest}")

        # Finalize status metadata before copying checkpoint to brain directory
        dest_ckpt = self.mirror_dir / self.checkpoint_file.name
        copied.append(str(dest_ckpt))
        status = {
            "status": "completed",
            "destination": str(self.mirror_dir),
            "copied_count": len(copied),
            "copied_files": copied,
            "mirrored_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }
        self.checkpoint.data["mirror_status"] = status
        self.checkpoint.mark_stage_completed(BatchStage.STAGE_5_MIRRORING)
        self._set_stage(BatchStage.COMPLETED)
        self.checkpoint.data["overall_status"] = "completed"
        self.checkpoint.save_atomic()

        # Copy finalized checkpoint to brain directory
        if self.checkpoint_file.is_file():
            shutil.copy2(self.checkpoint_file, dest_ckpt)
            if dest_ckpt.stat().st_size != self.checkpoint_file.stat().st_size:
                raise IOError(
                    f"Mirror checkpoint copy mismatch: {self.checkpoint_file.stat().st_size} != {dest_ckpt.stat().st_size}"
                )

        self.logger.info(f"Stage 5 Complete: Successfully mirrored {len(copied)} files.")
        return status

    async def run_batch(self) -> Dict[str, Any]:
        """Execute full 5-stage sequential progression."""
        self.logger.info("=== Starting Autonomous Overnight Batch Pipeline ===")

        # If resume enabled, try loading checkpoint
        if self.config.get("resume") and not self.config.get("force"):
            if self.checkpoint.load():
                self.enforce_mock_rejection()
                self.logger.info(
                    f"Resuming existing checkpoint: {len(self.checkpoint.data.get('completed_stages', []))} stages already completed."
                )

        self.checkpoint.data["config"] = {
            k: str(v) if isinstance(v, Path) else v for k, v in self.config.items()
        }
        self.checkpoint.data["overall_status"] = "in_progress"
        self.checkpoint.save_atomic()

        # Step through stages sequentially
        self.stage_1_dataset()
        self.stage_2_prompt_matrix()
        await self.stage_3_generation()
        self.stage_4_verification()
        self.stage_5_mirroring()

        self._set_stage(BatchStage.COMPLETED)
        self.checkpoint.data["overall_status"] = "completed"
        self.checkpoint.save_atomic()

        # Synchronize finalized checkpoint to brain directory if mirror_dir exists
        dest_ckpt = self.mirror_dir / self.checkpoint_file.name
        if self.mirror_dir.is_dir() and self.checkpoint_file.is_file():
            shutil.copy2(self.checkpoint_file, dest_ckpt)

        self.logger.info("=== Autonomous Overnight Batch Pipeline COMPLETED Successfully ===")
        return self.checkpoint.data


def build_arg_parser() -> argparse.ArgumentParser:
    """Build command-line interface arguments parser."""
    parser = argparse.ArgumentParser(
        description="Autonomous Overnight Batch Execution Runner for Veo 3.1 Arcane Styling."
    )
    parser.add_argument("--resume", action="store_true", help="Resume from existing checkpoint file.")
    parser.add_argument("--dry-run", action="store_true", help="Simulate generation without invoking models or mock.")
    parser.add_argument("--mock", action="store_true", help="Use offline mock client generating compliant test media.")
    parser.add_argument("--clips", type=str, default="2", help="Clip count or comma-separated pair IDs.")
    parser.add_argument("--duration", type=int, choices=[4, 8], default=4, help="Clip duration in seconds.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help="Working output directory.")
    parser.add_argument("--checkpoint-file", type=Path, default=None, help="Custom checkpoint file path.")
    parser.add_argument("--log-file", type=Path, default=None, help="Custom log file path.")
    parser.add_argument("--mirror-dir", type=Path, default=DEFAULT_BRAIN_DIR, help="Mirror destination directory.")
    parser.add_argument("--proxy", type=str, default=DEFAULT_PROXY, help="HTTP proxy address.")
    parser.add_argument("--max-retries", type=int, default=3, help="Maximum generation retry attempts.")
    parser.add_argument("--force", action="store_true", help="Force overwrite checkpoint and re-run all stages.")
    return parser


def main() -> int:
    """CLI execution entrypoint."""
    parser = build_arg_parser()
    args = parser.parse_args()
    config = vars(args)

    runner = OvernightBatchRunner(config)
    try:
        asyncio.run(runner.run_batch())
        return 0
    except KeyboardInterrupt:
        runner.logger.warning("Pipeline aborted by user.")
        return 130
    except Exception as exc:
        runner.logger.error(f"Pipeline failed with unhandled exception: {exc}", exc_info=True)
        runner.checkpoint.data["overall_status"] = "failed"
        runner.checkpoint.save_atomic()
        return 1


if __name__ == "__main__":
    sys.exit(main())
