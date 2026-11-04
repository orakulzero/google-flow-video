"""Empirical Challenger Test Suite: Anti-Downgrade & Scratch Isolation.

Stress-tests:
1. Anti-downgrade guard: refusing to overwrite completed genuine checkpoints with uninitialized state.
2. Anti-downgrade guard: refusing to regress stage counts without force=True.
3. Force override: force=True successfully overwriting existing checkpoints.
4. Scratch isolation: mock mode defaults binding strictly to _mock_scratch.
5. Inviolability of production output/overnight_checkpoint.json.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from veo_arcane_style.scripts.run_overnight_batch import (
    DEFAULT_OUTPUT_DIR,
    AtomicCheckpoint,
    BatchStage,
    OvernightBatchRunner,
)


def _compute_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class TestAntiDowngradeGuard:
    """Stress-test anti-downgrade protection against accidental overwrite/regression."""

    @pytest.fixture
    def completed_genuine_checkpoint(self, tmp_path: Path) -> Path:
        ckpt_path = tmp_path / "genuine_completed_checkpoint.json"
        data = {
            "version": "1.0.0",
            "created_at": "2026-11-03T00:00:00Z",
            "updated_at": "2026-11-03T00:00:00Z",
            "overall_status": "completed",
            "current_stage": "COMPLETED",
            "completed_stages": [
                BatchStage.STAGE_1_DATASET.value,
                BatchStage.STAGE_2_PROMPT_MATRIX.value,
                BatchStage.STAGE_3_GENERATION.value,
                BatchStage.STAGE_4_VERIFICATION.value,
                BatchStage.STAGE_5_MIRRORING.value,
            ],
            "config": {
                "mock": False,
                "dry_run": False,
            },
        }
        ckpt_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return ckpt_path

    def test_uninitialized_checkpoint_cannot_overwrite_completed(
        self, completed_genuine_checkpoint: Path
    ) -> None:
        """Calling save_atomic() on uninitialized state must raise PermissionError."""
        original_hash = _compute_sha256(completed_genuine_checkpoint)

        uninit = AtomicCheckpoint(completed_genuine_checkpoint, auto_load=False)
        assert uninit.data["overall_status"] == "initialized"
        assert len(uninit.data["completed_stages"]) == 0

        with pytest.raises(PermissionError, match="Safety Guard: Refusing to overwrite active completed checkpoint"):
            uninit.save_atomic()

        assert _compute_sha256(completed_genuine_checkpoint) == original_hash

    def test_regressing_stage_count_raises_permission_error(
        self, completed_genuine_checkpoint: Path
    ) -> None:
        """Attempting to save fewer stages than existing on-disk must raise PermissionError."""
        original_hash = _compute_sha256(completed_genuine_checkpoint)

        partial = AtomicCheckpoint(completed_genuine_checkpoint, auto_load=False)
        partial.data["overall_status"] = "in_progress"
        partial.data["completed_stages"] = [
            BatchStage.STAGE_1_DATASET.value,
            BatchStage.STAGE_2_PROMPT_MATRIX.value,
        ]

        with pytest.raises(PermissionError, match=r"Safety Guard: Refusing to downgrade checkpoint stages \(5 -> 2\)"):
            partial.save_atomic()

        assert _compute_sha256(completed_genuine_checkpoint) == original_hash

    def test_force_true_allows_overwrite_and_downgrade(
        self, completed_genuine_checkpoint: Path
    ) -> None:
        """Explicit force=True allows overwriting genuine completed checkpoints."""
        uninit = AtomicCheckpoint(completed_genuine_checkpoint, auto_load=False)
        uninit.data["overall_status"] = "reset_via_force"
        uninit.data["completed_stages"] = []

        uninit.save_atomic(force=True)

        reloaded = AtomicCheckpoint(completed_genuine_checkpoint)
        assert reloaded.load() is True
        assert reloaded.data["overall_status"] == "reset_via_force"
        assert len(reloaded.data["completed_stages"]) == 0


class TestScratchIsolationGuard:
    """Stress-test scratch isolation preventing mock contamination of production."""

    def test_mock_runner_binds_to_mock_scratch_by_default(self) -> None:
        """OvernightBatchRunner({'mock': True}) must bind output_dir to _mock_scratch."""
        prod_ckpt = DEFAULT_OUTPUT_DIR / "overnight_checkpoint.json"
        has_prod = prod_ckpt.is_file()
        prod_hash_before = _compute_sha256(prod_ckpt) if has_prod else None

        runner = OvernightBatchRunner({"mock": True})

        assert runner.output_dir == DEFAULT_OUTPUT_DIR / "_mock_scratch"
        assert runner.output_dir.resolve() != DEFAULT_OUTPUT_DIR.resolve()
        assert runner.checkpoint_file == DEFAULT_OUTPUT_DIR / "_mock_scratch" / "mock_checkpoint.json"
        assert runner.checkpoint_file.resolve() != prod_ckpt.resolve()

        if has_prod:
            prod_hash_after = _compute_sha256(prod_ckpt)
            assert prod_hash_after == prod_hash_before, "Production overnight_checkpoint.json was modified!"

    def test_mock_runner_redirects_even_if_default_output_dir_passed(self) -> None:
        """Explicitly passing production output_dir in mock mode still redirects to _mock_scratch."""
        runner = OvernightBatchRunner({
            "mock": True,
            "output_dir": str(DEFAULT_OUTPUT_DIR),
        })

        assert runner.output_dir == DEFAULT_OUTPUT_DIR / "_mock_scratch"
        assert runner.checkpoint_file == DEFAULT_OUTPUT_DIR / "_mock_scratch" / "mock_checkpoint.json"

    def test_mock_runner_honors_explicit_custom_scratch_dir(self, tmp_path: Path) -> None:
        """Custom output_dir outside of production directory is honored."""
        custom_dir = tmp_path / "isolated_scratch"
        runner = OvernightBatchRunner({
            "mock": True,
            "output_dir": custom_dir,
        })

        assert runner.output_dir == custom_dir
        assert runner.checkpoint_file == custom_dir / "mock_checkpoint.json"
