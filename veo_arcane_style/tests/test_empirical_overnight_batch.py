"""Empirical Adversarial Test Suite for Overnight Batch Runner (Milestone 3).

Adversarially challenges:
1. AtomicCheckpoint crash-consistency and corrupted JSON handling.
2. --resume idempotency, fast exit, and zero redundant renders.
3. Boundary inputs: invalid durations, non-existent pairs, proxy formats.
4. Signal interception (SIGINT/SIGTERM/SIGBREAK) graceful checkpointing.
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from typing import Any, Dict
from unittest.mock import AsyncMock, patch

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from veo_arcane_style.scripts.run_overnight_batch import (
    AtomicCheckpoint,
    BatchStage,
    OvernightBatchRunner,
    build_arg_parser,
)


class TestAtomicCheckpointAdversarial:
    """Adversarial stress-testing of AtomicCheckpoint crash-consistency."""

    def test_interrupted_write_preserves_original_checkpoint(self, tmp_path: Path) -> None:
        ckpt_path = tmp_path / "checkpoint.json"
        ckpt = AtomicCheckpoint(ckpt_path)
        ckpt.data["overall_status"] = "stable_completed"
        ckpt.data["completed_stages"] = [BatchStage.STAGE_1_DATASET.value]
        ckpt.save_atomic()

        assert ckpt_path.is_file()
        original_bytes = ckpt_path.read_bytes()

        # Simulate power failure / crash during write: corrupted .tmp left behind
        tmp_file = ckpt_path.with_suffix(ckpt_path.suffix + ".tmp")
        tmp_file.write_text('{"truncated_json": true, "corrupted": ', encoding="utf-8")

        # Verify load still recovers intact original file
        reloaded = AtomicCheckpoint(ckpt_path)
        assert reloaded.load() is True
        assert reloaded.data["overall_status"] == "stable_completed"
        assert reloaded.data["completed_stages"] == [BatchStage.STAGE_1_DATASET.value]
        assert ckpt_path.read_bytes() == original_bytes

    def test_corrupted_json_fallback_and_warning(self, tmp_path: Path) -> None:
        ckpt_path = tmp_path / "corrupted_checkpoint.json"
        ckpt_path.write_text("{this is definitely not valid json 12345!@#$%", encoding="utf-8")

        ckpt = AtomicCheckpoint(ckpt_path)
        assert ckpt.load() is False
        assert ckpt.data["overall_status"] == "initialized"
        assert ckpt.data["version"] == "1.0.0"

    def test_malformed_json_partial_tokens(self, tmp_path: Path) -> None:
        ckpt_path = tmp_path / "empty_or_broken.json"
        for broken_content in ["", "   ", "null", "[]", '{"no_version": true}']:
            ckpt_path.write_text(broken_content, encoding="utf-8")
            ckpt = AtomicCheckpoint(ckpt_path)
            assert ckpt.load() is False, f"Failed on content: {broken_content!r}"

    def test_directory_auto_creation_on_atomic_save(self, tmp_path: Path) -> None:
        deep_path = tmp_path / "nested" / "sub" / "dir" / "deep_ckpt.json"
        ckpt = AtomicCheckpoint(deep_path)
        ckpt.save_atomic()
        assert deep_path.is_file()
        assert deep_path.stat().st_size > 0


class TestResumeIdempotencyAdversarial:
    """Stress-test --resume idempotency, zero redundant renders, and fast exit."""

    @pytest.mark.asyncio
    async def test_resume_fully_completed_batch_zero_api_calls(self, tmp_path: Path) -> None:
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

        # First run: execute full batch
        runner1 = OvernightBatchRunner(cfg)
        res1 = await runner1.run_batch()
        assert res1["overall_status"] == "completed"

        # Record clip modified times and contents
        clip1 = out_dir / "arcane_clip_01_zaun_duel_720p.mp4"
        clip2 = out_dir / "arcane_clip_02_piltover_hextech_720p.mp4"
        assert clip1.is_file()
        assert clip2.is_file()
        mtime1 = clip1.stat().st_mtime_ns
        mtime2 = clip2.stat().st_mtime_ns

        # Second run: execute with resume=True
        cfg["resume"] = True
        runner2 = OvernightBatchRunner(cfg)

        with patch.object(runner2.pipeline, "generate_i2v_clip", new_callable=AsyncMock) as mock_gen:
            t0 = time.perf_counter()
            res2 = await runner2.run_batch()
            elapsed = time.perf_counter() - t0

            # Must have zero calls to generate_i2v_clip
            assert mock_gen.call_count == 0, f"Expected 0 calls to generate_i2v_clip, got {mock_gen.call_count}"
            # Runtime should be near-instantaneous (under 1.0 second)
            assert elapsed < 1.0, f"Resume took {elapsed:.2f}s, expected < 1.0s"
            # Output files untouched
            assert clip1.stat().st_mtime_ns == mtime1
            assert clip2.stat().st_mtime_ns == mtime2
            assert res2["overall_status"] == "completed"

    @pytest.mark.asyncio
    async def test_resume_partial_generation_renders_only_remaining(self, tmp_path: Path) -> None:
        out_dir = tmp_path / "out"
        mirror_dir = tmp_path / "mirror"
        ckpt_file = out_dir / "overnight_checkpoint.json"

        cfg = {
            "output_dir": out_dir,
            "mirror_dir": mirror_dir,
            "checkpoint_file": ckpt_file,
            "log_file": out_dir / "logs" / "batch.log",
            "mock": True,
            "clips": "2",
            "duration": 4,
            "resume": True,
        }

        runner = OvernightBatchRunner(cfg)
        runner.stage_1_dataset()
        runner.stage_2_prompt_matrix()

        # Artificially mark clip 1 as completed with a valid file
        matrix = runner.checkpoint.data["prompt_matrix"]
        clip1_path = Path(matrix[0]["target_output_path"])
        clip1_path.parent.mkdir(parents=True, exist_ok=True)
        clip1_path.write_bytes(b"\x00\x00\x00\x20ftypisom" + b"\x55" * 60000)

        runner.checkpoint.data["clips"][matrix[0]["pair_id"]] = {
            "status": "completed",
            "output_path": str(clip1_path),
            "duration": 4,
            "native_audio": True,
        }
        runner.checkpoint.save_atomic()

        # Run stage 3: clip 1 must be skipped, only clip 2 generated
        with patch.object(runner.pipeline, "generate_i2v_clip", wraps=runner.pipeline.generate_i2v_clip) as spy_gen:
            await runner.stage_3_generation()
            # Exactly 1 generation call for the remaining clip
            assert spy_gen.call_count == 1
            call_pair_id = spy_gen.call_args[1]["pair_id"]
            assert call_pair_id == matrix[1]["pair_id"]


class TestBoundaryInputsAdversarial:
    """Stress-test edge cases, boundary inputs, and parameter rejection."""

    @pytest.mark.parametrize("invalid_duration", [0, -5, 1, 2, 3, 5, 6, 7, 9, 10, 100])
    def test_cli_rejects_invalid_duration_choices(self, invalid_duration: int) -> None:
        parser = build_arg_parser()
        with pytest.raises(SystemExit) as exc_info:
            parser.parse_args(["--duration", str(invalid_duration)])
        # argparse exits with code 2 on invalid choice
        assert exc_info.value.code == 2

    def test_cli_rejects_non_existent_pair_id(self, tmp_path: Path) -> None:
        cfg = {
            "output_dir": tmp_path / "out",
            "checkpoint_file": tmp_path / "ckpt.json",
            "log_file": tmp_path / "test.log",
            "clips": "nonexistent_pair_999",
        }
        runner = OvernightBatchRunner(cfg)
        with pytest.raises((ValueError, KeyError)) as exc_info:
            runner.stage_2_prompt_matrix()
        assert "nonexistent_pair_999" in str(exc_info.value)

    def test_cli_comma_separated_with_one_invalid_pair(self, tmp_path: Path) -> None:
        cfg = {
            "output_dir": tmp_path / "out",
            "checkpoint_file": tmp_path / "ckpt.json",
            "log_file": tmp_path / "test.log",
            "clips": "pair_170629_shot_000,invalid_pair_ghost",
        }
        runner = OvernightBatchRunner(cfg)
        with pytest.raises(KeyError) as exc_info:
            runner.stage_2_prompt_matrix()
        assert "invalid_pair_ghost" in str(exc_info.value)

    def test_whitespace_clips_string_rejected_with_value_error(self, tmp_path: Path) -> None:
        cfg = {
            "output_dir": tmp_path / "out",
            "checkpoint_file": tmp_path / "ckpt.json",
            "log_file": tmp_path / "test.log",
            "clips": "   ",
        }
        runner = OvernightBatchRunner(cfg)
        with pytest.raises(ValueError, match="Invalid --clips argument"):
            runner.stage_2_prompt_matrix()

    def test_omitted_or_none_clips_falls_back_to_default_count(self, tmp_path: Path) -> None:
        cfg = {
            "output_dir": tmp_path / "out",
            "checkpoint_file": tmp_path / "ckpt.json",
            "log_file": tmp_path / "test.log",
            "clips": None,
        }
        runner = OvernightBatchRunner(cfg)
        matrix = runner.stage_2_prompt_matrix()
        assert len(matrix) == 2

    def test_zero_clips_yields_empty_matrix_without_crash(self, tmp_path: Path) -> None:
        cfg = {
            "output_dir": tmp_path / "out",
            "checkpoint_file": tmp_path / "ckpt.json",
            "log_file": tmp_path / "test.log",
            "clips": "0",
        }
        runner = OvernightBatchRunner(cfg)
        matrix = runner.stage_2_prompt_matrix()
        assert len(matrix) == 0

    def test_custom_proxy_url_injection(self, tmp_path: Path) -> None:
        custom_proxy = "http://10.20.30.40:8888"
        cfg = {
            "output_dir": tmp_path / "out",
            "checkpoint_file": tmp_path / "ckpt.json",
            "log_file": tmp_path / "test.log",
            "proxy": custom_proxy,
        }
        runner = OvernightBatchRunner(cfg)
        assert runner.pipeline.proxy_url == custom_proxy


class TestSignalHandlingAdversarial:
    """Stress-test signal interception, graceful checkpointing, and status persistence."""

    def test_sigint_handler_persists_interrupted_checkpoint(self, tmp_path: Path) -> None:
        ckpt_file = tmp_path / "sig_ckpt.json"
        cfg = {
            "output_dir": tmp_path / "out",
            "checkpoint_file": ckpt_file,
            "log_file": tmp_path / "test.log",
        }
        runner = OvernightBatchRunner(cfg)
        runner.stage_1_dataset()

        # Find registered signal handler for SIGINT
        sig_handler = signal.getsignal(signal.SIGINT)
        assert callable(sig_handler), "SIGINT handler must be callable"

        # Trigger signal handler directly
        with pytest.raises(SystemExit) as exc_info:
            sig_handler(signal.SIGINT, None)

        assert exc_info.value.code == 130
        assert runner.shutdown_requested is True
        assert runner.checkpoint.data["overall_status"] == "interrupted"

        # Verify disk checkpoint was atomically flushed and reloadable
        reloaded = AtomicCheckpoint(ckpt_file)
        assert reloaded.load() is True
        assert reloaded.data["overall_status"] == "interrupted"
        assert reloaded.is_stage_completed(BatchStage.STAGE_1_DATASET) is True

    def test_sigterm_handler_persists_interrupted_checkpoint(self, tmp_path: Path) -> None:
        ckpt_file = tmp_path / "sigterm_ckpt.json"
        cfg = {
            "output_dir": tmp_path / "out",
            "checkpoint_file": ckpt_file,
            "log_file": tmp_path / "test.log",
        }
        runner = OvernightBatchRunner(cfg)

        sig_handler = signal.getsignal(signal.SIGTERM)
        if callable(sig_handler):
            with pytest.raises(SystemExit) as exc_info:
                sig_handler(signal.SIGTERM, None)
            assert exc_info.value.code == 130
            assert runner.checkpoint.data["overall_status"] == "interrupted"
