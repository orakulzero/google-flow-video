"""Comprehensive Test Suite for Autonomous Overnight Batch Runner (Milestone 3).

Verifies:
- CLI argument parsing and defaults
- Atomic checkpointing and crash-consistent resumption
- 5-stage sequential progression (Dataset -> Matrix -> Gen -> Verify -> Mirror)
- MediaValidator programmatic validation (FastStart, 720p+, H.264, AAC)
- Visual comparison contact sheet generator
- Mirroring file copy integrity and parity
- Anti-cheat compliance (zero OpenCV zoom fallbacks, zero ffmpeg -an stripping)
"""

from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any, Dict
import pytest

# Ensure project root in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from veo_arcane_style.scripts.run_overnight_batch import (
    AtomicCheckpoint,
    BatchStage,
    ContactSheetGenerator,
    MediaValidator,
    MockFlowClient,
    OvernightBatchRunner,
    build_arg_parser,
)


class TestCliParsing:
    """Verify CLI arguments and default options."""

    def test_parser_defaults(self) -> None:
        parser = build_arg_parser()
        args = parser.parse_args([])
        assert args.resume is False
        assert args.dry_run is False
        assert args.mock is False
        assert args.clips == "2"
        assert args.duration == 4
        assert args.proxy == "http://127.0.0.1:7890"
        assert args.max_retries == 3
        assert args.force is False

    def test_parser_custom_flags(self, tmp_path: Path) -> None:
        parser = build_arg_parser()
        custom_out = tmp_path / "custom_out"
        custom_ckpt = tmp_path / "custom.json"
        args = parser.parse_args([
            "--resume",
            "--dry-run",
            "--mock",
            "--clips", "pair_170629_shot_000,pair_270000_shot_015",
            "--duration", "8",
            "--output-dir", str(custom_out),
            "--checkpoint-file", str(custom_ckpt),
            "--max-retries", "5",
            "--force",
        ])
        assert args.resume is True
        assert args.dry_run is True
        assert args.mock is True
        assert args.clips == "pair_170629_shot_000,pair_270000_shot_015"
        assert args.duration == 8
        assert args.output_dir == custom_out
        assert args.checkpoint_file == custom_ckpt
        assert args.max_retries == 5
        assert args.force is True


class TestAtomicCheckpoint:
    """Verify atomic checkpoint persistence, recovery, and stage tracking."""

    def test_checkpoint_initial_state_and_defaults(self, tmp_path: Path) -> None:
        ckpt_path = tmp_path / "test_ckpt.json"
        ckpt = AtomicCheckpoint(ckpt_path)
        assert ckpt.data["version"] == "1.0.0"
        assert ckpt.data["overall_status"] == "initialized"
        assert ckpt.data["completed_stages"] == []
        assert ckpt.is_stage_completed(BatchStage.STAGE_1_DATASET) is False

    def test_checkpoint_atomic_save_and_reload(self, tmp_path: Path) -> None:
        ckpt_path = tmp_path / "test_ckpt.json"
        ckpt = AtomicCheckpoint(ckpt_path)
        ckpt.data["overall_status"] = "in_progress"
        ckpt.mark_stage_completed(BatchStage.STAGE_1_DATASET)
        assert ckpt_path.is_file()

        # Reload in a fresh instance
        reloaded = AtomicCheckpoint(ckpt_path)
        assert reloaded.load() is True
        assert reloaded.data["overall_status"] == "in_progress"
        assert reloaded.is_stage_completed(BatchStage.STAGE_1_DATASET) is True
        assert reloaded.is_stage_completed(BatchStage.STAGE_2_PROMPT_MATRIX) is False

    def test_checkpoint_load_non_existent_file(self, tmp_path: Path) -> None:
        ckpt_path = tmp_path / "does_not_exist.json"
        ckpt = AtomicCheckpoint(ckpt_path)
        assert ckpt.load() is False


class TestStage1Dataset:
    """Verify Stage 1 Dataset Staging and validation rules."""

    def test_stage_1_dataset_verification_success(self, tmp_path: Path) -> None:
        runner = OvernightBatchRunner({
            "output_dir": tmp_path / "out",
            "checkpoint_file": tmp_path / "ckpt.json",
            "log_file": tmp_path / "test.log",
            "mirror_dir": tmp_path / "mirror",
        })
        status = runner.stage_1_dataset()
        assert status["valid"] is True
        assert status["total_frames"] >= 50
        assert status["total_pairs"] >= 5
        assert runner.checkpoint.is_stage_completed(BatchStage.STAGE_1_DATASET) is True

    def test_stage_1_dataset_insufficient_frames_raises_error(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        runner = OvernightBatchRunner({
            "output_dir": tmp_path / "out",
            "checkpoint_file": tmp_path / "ckpt.json",
            "log_file": tmp_path / "test.log",
            "mirror_dir": tmp_path / "mirror",
        })
        monkeypatch.setattr(runner.pipeline, "load_dataset_index", lambda: {"frames": [{"id": "f1"}], "pairs": []})
        with pytest.raises(ValueError, match="threshold 50"):
            runner.stage_1_dataset()


class TestStage2PromptMatrix:
    """Verify Stage 2 Prompt Matrix formulation and selection."""

    def test_stage_2_prompt_matrix_default_pairs(self, tmp_path: Path) -> None:
        runner = OvernightBatchRunner({
            "output_dir": tmp_path / "out",
            "checkpoint_file": tmp_path / "ckpt.json",
            "log_file": tmp_path / "test.log",
            "mirror_dir": tmp_path / "mirror",
            "clips": "2",
        })
        matrix = runner.stage_2_prompt_matrix()
        assert len(matrix) == 2
        assert matrix[0]["pair_id"] == "pair_170629_shot_000"
        assert matrix[0]["target_output_name"] == "arcane_clip_01_zaun_duel_720p.mp4"
        assert matrix[1]["pair_id"] == "pair_270000_shot_015"
        assert matrix[1]["target_output_name"] == "arcane_clip_02_piltover_hextech_720p.mp4"

        for entry in matrix:
            prompt = entry["prompt"]
            assert prompt.startswith("Make me a video in a 16:9 aspect ratio: ")
            assert "Hand-painted Fortiche Production Arcane 2.5D animation style." in prompt
            assert "Strictly avoid photorealism" in prompt

        assert runner.checkpoint.is_stage_completed(BatchStage.STAGE_2_PROMPT_MATRIX) is True

    def test_stage_2_prompt_matrix_comma_separated_selection(self, tmp_path: Path) -> None:
        runner = OvernightBatchRunner({
            "output_dir": tmp_path / "out",
            "checkpoint_file": tmp_path / "ckpt.json",
            "log_file": tmp_path / "test.log",
            "mirror_dir": tmp_path / "mirror",
            "clips": "pair_270000_shot_015",
        })
        matrix = runner.stage_2_prompt_matrix()
        assert len(matrix) == 1
        assert matrix[0]["pair_id"] == "pair_270000_shot_015"

    def test_stage_2_prompt_matrix_unknown_pair_raises_key_error(self, tmp_path: Path) -> None:
        runner = OvernightBatchRunner({
            "output_dir": tmp_path / "out",
            "checkpoint_file": tmp_path / "ckpt.json",
            "log_file": tmp_path / "test.log",
            "mirror_dir": tmp_path / "mirror",
            "clips": "unknown_pair_999",
        })
        with pytest.raises(Exception):
            runner.stage_2_prompt_matrix()


class TestMockFlowClient:
    """Verify MockFlowClient test media creation."""

    @pytest.mark.asyncio
    async def test_mock_client_generates_compliant_media(self, tmp_path: Path) -> None:
        client = MockFlowClient()
        start_img = PROJECT_ROOT / "veo_arcane_style" / "dataset" / "pairs" / "pair_170629_shot_000" / "first_frame.png"
        end_img = PROJECT_ROOT / "veo_arcane_style" / "dataset" / "pairs" / "pair_170629_shot_000" / "last_frame.png"
        target_out = tmp_path / "mock_test.mp4"

        res = await client.generate_start_and_end_clip(
            prompt="Test prompt",
            start_image=start_img,
            end_image=end_img,
            duration=4,
            out_path=target_out,
        )
        assert res["ok"] is True
        assert res["native_audio"] is True
        assert target_out.is_file()
        assert target_out.stat().st_size > 50000

        # Programmatic check
        v = MediaValidator.validate_deliverable(target_out)
        assert v["valid"] is True
        assert v["width"] >= 1280
        assert v["height"] >= 720
        assert v["video_codec_h264"] is True
        assert v["audio_codec_aac"] is True
        assert v["faststart"] is True


class TestStage4MediaValidatorAndSheets:
    """Verify Stage 4 Media Validation and Visual Contact Sheets."""

    def test_media_validator_missing_and_tiny_files(self, tmp_path: Path) -> None:
        missing = tmp_path / "missing.mp4"
        v1 = MediaValidator.validate_deliverable(missing)
        assert v1["valid"] is False
        assert "does not exist" in v1["error"]

        tiny = tmp_path / "tiny.mp4"
        tiny.write_bytes(b"\x00" * 200)
        v2 = MediaValidator.validate_deliverable(tiny)
        assert v2["valid"] is False
        assert "too small" in v2["error"]

    def test_media_validator_faststart_detection(self, tmp_path: Path) -> None:
        fs_file = tmp_path / "fs.mp4"
        fs_file.write_bytes(b"\x00\x00\x00\x20ftypisom" + b"\x00" * 100 + b"moov" + b"\x00" * 100 + b"mdat")
        assert MediaValidator.check_faststart(fs_file) is True

        non_fs = tmp_path / "non_fs.mp4"
        non_fs.write_bytes(b"\x00\x00\x00\x20ftypisom" + b"\x00" * 100 + b"mdat" + b"\x00" * 100 + b"moov")
        assert MediaValidator.check_faststart(non_fs) is False

    @pytest.mark.asyncio
    async def test_contact_sheet_generator(self, tmp_path: Path) -> None:
        out_dir = tmp_path / "out"
        client = MockFlowClient()
        pair_dir = PROJECT_ROOT / "veo_arcane_style" / "dataset" / "pairs" / "pair_170629_shot_000"
        vid_file = out_dir / "test_clip.mp4"

        await client.generate_start_and_end_clip(
            prompt="Test",
            start_image=pair_dir / "first_frame.png",
            end_image=pair_dir / "last_frame.png",
            duration=4,
            out_path=vid_file,
        )

        pair_info = {
            "pair_id": "pair_170629_shot_000",
            "character": "Vi",
            "palette": "magenta_cyan_chiaroscuro",
            "first_frame_path": str(pair_dir / "first_frame.png"),
            "mid_impact_path": str(pair_dir / "mid_impact.png"),
            "last_frame_path": str(pair_dir / "last_frame.png"),
        }

        sheet_path = out_dir / "contact_sheets" / "comparison_pair_170629_shot_000.png"
        res_sheet = ContactSheetGenerator.create_clip_comparison(pair_info, vid_file, sheet_path)
        assert res_sheet.is_file()
        assert res_sheet.stat().st_size > 20000

        master_path = out_dir / "master_verification_sheet.png"
        res_master = ContactSheetGenerator.create_master_sheet([res_sheet], master_path)
        assert res_master.is_file()
        assert res_master.stat().st_size > 20000


class TestStage5Mirroring:
    """Verify Stage 5 Brain Directory Mirroring parity."""

    def test_mirroring_preserves_bytes_and_directory_structure(self, tmp_path: Path) -> None:
        out_dir = tmp_path / "out"
        mirror_dir = tmp_path / "mirror"
        runner = OvernightBatchRunner({
            "output_dir": out_dir,
            "mirror_dir": mirror_dir,
            "checkpoint_file": out_dir / "overnight_checkpoint.json",
            "log_file": out_dir / "logs" / "test.log",
        })

        test_mp4 = out_dir / "arcane_clip_01_zaun_duel_720p.mp4"
        test_mp4.parent.mkdir(parents=True, exist_ok=True)
        test_mp4.write_bytes(b"\x00\x00\x00\x20ftypisom" + b"\xAA" * 60000)

        status = runner.stage_5_mirroring()
        assert status["status"] == "completed"
        assert status["copied_count"] >= 1

        mirrored_file = mirror_dir / "arcane_clip_01_zaun_duel_720p.mp4"
        assert mirrored_file.is_file()
        assert mirrored_file.stat().st_size == test_mp4.stat().st_size
        assert runner.checkpoint.is_stage_completed(BatchStage.STAGE_5_MIRRORING) is True

    def test_mirroring_mock_to_default_brain_dir_rejected(self, tmp_path: Path) -> None:
        out_dir = tmp_path / "out"
        runner = OvernightBatchRunner({
            "output_dir": out_dir,
            "checkpoint_file": out_dir / "overnight_checkpoint.json",
            "log_file": out_dir / "logs" / "test.log",
            "mock": True,
        })
        with pytest.raises(PermissionError, match="Refusing to mirror mock or dry-run artifacts to production brain directory"):
            runner.stage_5_mirroring()


class TestEndToEndOvernightBatch:
    """Verify End-to-End multi-stage pipeline orchestration."""

    @pytest.mark.asyncio
    async def test_end_to_end_mock_batch_execution(self, tmp_path: Path) -> None:
        out_dir = tmp_path / "out"
        mirror_dir = tmp_path / "mirror"
        runner = OvernightBatchRunner({
            "output_dir": out_dir,
            "mirror_dir": mirror_dir,
            "checkpoint_file": out_dir / "overnight_checkpoint.json",
            "log_file": out_dir / "logs" / "batch.log",
            "mock": True,
            "clips": "2",
            "duration": 4,
            "force": True,
        })

        result = await runner.run_batch()
        assert result["overall_status"] == "completed"
        assert len(result["completed_stages"]) == 5
        assert BatchStage.STAGE_1_DATASET.value in result["completed_stages"]
        assert BatchStage.STAGE_5_MIRRORING.value in result["completed_stages"]

        # Check deliverables exist
        assert (out_dir / "arcane_clip_01_zaun_duel_720p.mp4").is_file()
        assert (out_dir / "arcane_clip_02_piltover_hextech_720p.mp4").is_file()
        assert (out_dir / "master_verification_sheet.png").is_file()
        assert (out_dir / "verification_report.json").is_file()
        assert (mirror_dir / "arcane_clip_01_zaun_duel_720p.mp4").is_file()

    @pytest.mark.asyncio
    async def test_end_to_end_resume_idempotency(self, tmp_path: Path) -> None:
        out_dir = tmp_path / "out"
        mirror_dir = tmp_path / "mirror"
        cfg = {
            "output_dir": out_dir,
            "mirror_dir": mirror_dir,
            "checkpoint_file": out_dir / "overnight_checkpoint.json",
            "log_file": out_dir / "logs" / "batch.log",
            "mock": True,
            "clips": "2",
            "duration": 4,
        }

        runner1 = OvernightBatchRunner(cfg)
        res1 = await runner1.run_batch()
        assert res1["overall_status"] == "completed"

        # Second runner with resume=True
        cfg["resume"] = True
        runner2 = OvernightBatchRunner(cfg)
        res2 = await runner2.run_batch()
        assert res2["overall_status"] == "completed"
        assert res2["completed_stages"] == res1["completed_stages"]

    @pytest.mark.asyncio
    async def test_resume_mock_checkpoint_rejected_in_live_run(self, tmp_path: Path) -> None:
        out_dir = tmp_path / "out"
        mirror_dir = tmp_path / "mirror"
        ckpt_file = out_dir / "overnight_checkpoint.json"

        # First write a checkpoint simulating completed mock run
        runner_mock = OvernightBatchRunner({
            "output_dir": out_dir,
            "mirror_dir": mirror_dir,
            "checkpoint_file": ckpt_file,
            "log_file": out_dir / "logs" / "mock.log",
            "mock": True,
            "clips": "2",
            "duration": 4,
        })
        await runner_mock.run_batch()
        assert runner_mock.checkpoint.is_stage_completed(BatchStage.STAGE_3_GENERATION) is True

        # Now instantiate a live runner (mock=False, dry_run=False) with resume=True
        runner_live = OvernightBatchRunner({
            "output_dir": out_dir,
            "mirror_dir": mirror_dir,
            "checkpoint_file": ckpt_file,
            "log_file": out_dir / "logs" / "live.log",
            "mock": False,
            "dry_run": False,
            "resume": True,
            "clips": "2",
            "duration": 4,
        })
        # Check mock rejection directly
        runner_live.checkpoint.load()
        runner_live.enforce_mock_rejection()
        assert runner_live.checkpoint.is_stage_completed(BatchStage.STAGE_3_GENERATION) is False
        assert runner_live.checkpoint.is_stage_completed(BatchStage.STAGE_4_VERIFICATION) is False
        assert runner_live.checkpoint.is_stage_completed(BatchStage.STAGE_5_MIRRORING) is False
        assert runner_live.checkpoint.data["clips"] == {}


class TestAntiCheatCompliance:
    """Verify anti-cheat invariants and code hygiene."""

    def test_zero_prohibited_tokens_in_batch_runner(self) -> None:
        script_path = PROJECT_ROOT / "veo_arcane_style" / "scripts" / "run_overnight_batch.py"
        content = script_path.read_text(encoding="utf-8")

        # Must not contain audio stripping
        assert "-an" not in content

        # Must not synthesize fake sine waves
        assert "np.sin" not in content
        assert "numpy.sin" not in content

        # Must not contain OpenCV zoom fallbacks
        assert "warpAffine" not in content
        assert "zoom_pan" not in content

    def test_zero_cyrillic_characters_in_batch_files(self) -> None:
        targets = [
            PROJECT_ROOT / "veo_arcane_style" / "scripts" / "run_overnight_batch.py",
            PROJECT_ROOT / "veo_arcane_style" / "tests" / "test_overnight_batch.py",
        ]
        for target in targets:
            content = target.read_text(encoding="utf-8")
            non_ascii = [c for c in content if ord(c) > 127]
            assert len(non_ascii) == 0, f"Found non-ASCII characters in {target.name}: {non_ascii[:5]}"
