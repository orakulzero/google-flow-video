"""Comprehensive Test Suite for Arcane Prompt Engine & Veo Style Conditioning Pipeline (Milestone 2).

Verifies Fortiche 6-stage lexical tuning, palette substitutions, dataset index resolution,
curated frame and motion pair lookups, and mock/offline client dispatch.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Dict
import pytest

from veo_arcane_style.src.arcane_prompt_engine import ArcanePromptEngine
from veo_arcane_style.src.veo_style_pipeline import VeoStylePipeline


class TestArcanePromptEngine:
    """Unit tests for Fortiche 6-stage lexical prompt engine."""

    def test_prompt_engine_6_stages_and_aspect_prefix(self) -> None:
        engine = ArcanePromptEngine()
        assert engine.ASPECT_PREFIX == "Make me a video in a 16:9 aspect ratio: "
        assert engine.STYLE_ANCHOR == "Hand-painted Fortiche Production Arcane 2.5D animation style. "
        assert "textured digital brushwork" in engine.TEXTURE_BRUSHWORK
        assert "tactile gouache and oil impasto strokes" in engine.TEXTURE_BRUSHWORK
        assert "Extreme chiaroscuro contrast" in engine.LIGHTING_TEMPLATE
        assert "Cinematic sweeping camera tracking" in engine.CAMERA_DIRECTION
        assert "Strictly avoid photorealism" in engine.NEGATIVE_CONSTRAINTS
        assert "avoid uncanny valley wax skin" in engine.NEGATIVE_CONSTRAINTS

    def test_prompt_engine_palette_mapping_for_moods(self) -> None:
        engine = ArcanePromptEngine()
        assert engine.get_palette_for_mood("combat") == "magenta_cyan_chiaroscuro"
        assert engine.get_palette_for_mood("piltover") == "gilded_hextech_amber"
        assert engine.get_palette_for_mood("zaun") == "toxic_chemtech_green"
        assert engine.get_palette_for_mood("noir") == "desaturated_underworld_slate"
        assert engine.get_palette_for_mood("unknown_mood") == "magenta_cyan_chiaroscuro"

    def test_prompt_engine_build_i2v_prompt_structure(self) -> None:
        engine = ArcanePromptEngine()
        prompt = engine.build_i2v_prompt(
            action_description="Vi delivers a high-impact gauntlet strike against Sevika",
            character="Vi",
            palette="magenta_cyan_chiaroscuro",
            mood="combat",
        )
        assert prompt.startswith(engine.ASPECT_PREFIX)
        assert engine.STYLE_ANCHOR in prompt
        assert "Featuring Vi, Vi delivers a high-impact gauntlet strike against Sevika." in prompt
        assert "dramatic dual-tone rim lighting (magenta_cyan_chiaroscuro)" in prompt
        assert prompt.endswith(engine.NEGATIVE_CONSTRAINTS)

    def test_prompt_engine_build_r2v_prompt_with_tags(self) -> None:
        engine = ArcanePromptEngine()
        prompt = engine.build_r2v_prompt(
            scene_description="Piltover council chambers with golden sunlight through art-deco windows",
            style_tags=["gilded_hextech", "volumetric_haze", "matte_concept_art"],
            palette="gilded_hextech_amber",
        )
        assert prompt.startswith(engine.ASPECT_PREFIX)
        assert "Visual elements: gilded_hextech, volumetric_haze, matte_concept_art." in prompt
        assert "dramatic dual-tone rim lighting (gilded_hextech_amber)" in prompt
        assert prompt.endswith(engine.NEGATIVE_CONSTRAINTS)


class TestVeoStylePipeline:
    """Unit and integration tests for VeoStylePipeline."""

    @pytest.fixture
    def pipeline(self) -> VeoStylePipeline:
        return VeoStylePipeline()

    def test_pipeline_dataset_index_loads_successfully(self, pipeline: VeoStylePipeline) -> None:
        idx = pipeline.load_dataset_index()
        assert idx.get("dataset_name") == "Veo Arcane Style Benchmark Dataset"
        assert len(idx.get("frames", [])) >= 50
        assert len(idx.get("pairs", [])) >= 10

    def test_pipeline_load_curated_frame_and_reference_alias(self, pipeline: VeoStylePipeline) -> None:
        frame = pipeline.load_curated_frame("arcane_curated_001")
        assert frame["id"] == "arcane_curated_001"
        assert frame["character"] == "Vi"
        assert frame["file_path"].is_file()

        # Verify load_reference alias
        ref = pipeline.load_reference("arcane_curated_001")
        assert ref["id"] == frame["id"]
        assert ref["file_path"] == frame["file_path"]

        with pytest.raises(KeyError):
            pipeline.load_curated_frame("non_existent_frame_id_999")

    def test_pipeline_load_pair_and_paths(self, pipeline: VeoStylePipeline) -> None:
        pair = pipeline.load_pair("pair_170629_shot_000")
        assert pair["pair_id"] == "pair_170629_shot_000"
        assert pair["character"] == "Vi"
        assert pair["first_frame_path"].is_file()
        assert pair["last_frame_path"].is_file()

        with pytest.raises(KeyError):
            pipeline.load_pair("non_existent_pair_id_999")

    def test_pipeline_list_curated_frames_and_pairs(self, pipeline: VeoStylePipeline) -> None:
        frames = pipeline.list_curated_frames()
        pairs = pipeline.list_pairs()
        assert len(frames) >= 50
        assert len(pairs) >= 10

    def test_pipeline_build_i2v_prompt_from_pair(self, pipeline: VeoStylePipeline) -> None:
        pair = pipeline.load_pair("pair_170629_shot_000")
        prompt = pipeline.build_i2v_prompt(pair)
        assert prompt.startswith(ArcanePromptEngine.ASPECT_PREFIX)
        assert pair["character"] in prompt

        # Test prompt override
        override = "Custom Arcane Prompt Override for Test Verification."
        res = pipeline.build_i2v_prompt(pair, prompt_override=override)
        assert res == override

    @pytest.mark.asyncio
    async def test_pipeline_generate_i2v_clip_with_mock_client(
        self,
        pipeline: VeoStylePipeline,
        tmp_path: Path,
    ) -> None:
        class MockFlowClient:
            def __init__(self) -> None:
                self.calls: list[dict[str, Any]] = []

            async def generate_start_and_end_clip(
                self,
                prompt: str,
                start_image: Path,
                end_image: Path,
                duration: int,
                out_path: Path,
            ) -> dict[str, Any]:
                self.calls.append({
                    "prompt": prompt,
                    "start_image": start_image,
                    "end_image": end_image,
                    "duration": duration,
                    "out_path": out_path,
                })
                # Create valid mock mp4 deliverable for testing
                out_path.write_bytes(b"\x00\x00\x00\x20ftypisom" + b"\x00" * 200)
                return {
                    "ok": True,
                    "pair_id": "pair_170629_shot_000",
                    "prompt": prompt,
                    "duration": duration,
                    "first_frame": str(start_image),
                    "last_frame": str(end_image),
                    "output_path": str(out_path),
                    "native_audio": True,
                }

        mock = MockFlowClient()
        target_out = tmp_path / "mock_test_clip.mp4"
        result = await pipeline.generate_i2v_clip(
            pair_id="pair_170629_shot_000",
            duration=4,
            client=mock,
            output_path=target_out,
        )

        assert result["ok"] is True
        assert result["pair_id"] == "pair_170629_shot_000"
        assert result["native_audio"] is True
        assert len(mock.calls) == 1
        assert mock.calls[0]["start_image"].is_file()
        assert mock.calls[0]["end_image"].is_file()
        assert target_out.is_file()



class TestEp01LucasArcaneVerticalSlice:
    """Verification tests for the Episode 1 Knight Lucas 4.00s Omni 1.1 Flash vertical slice."""

    def test_canonical_knight_lucas_source_preserved_1376x768(self) -> None:
        from PIL import Image

        src = Path("output/canonical_arcane_concepts/knight_lucas_portrait.png")
        assert src.is_file(), f"Missing canonical source: {src}"
        with Image.open(src) as im:
            assert im.size == (1376, 768), f"Canonical asset mutated: {im.size}"

    def test_lucas_pair_preflight_and_postflight_gates(self) -> None:
        import json

        pipeline = VeoStylePipeline()
        pair = pipeline.load_pair("pair_ttd_ep01_lucas_001")
        assert pair["character"] == "Knight Lucas"
        assert pair["first_frame_path"].is_file()
        assert pair["last_frame_path"].is_file()

        pair_dir = pair["first_frame_path"].parent
        preflight = json.loads((pair_dir / "preflight_pair_audit.json").read_text(encoding="utf-8"))
        assert preflight["gate_passed"] is True
        assert preflight["width"] == 1280 and preflight["height"] == 720
        assert 5.0 <= preflight["mae_bg"] <= 65.0
        assert 8.0 <= preflight["mae_roi"] <= 65.0

        mp4 = Path("veo_arcane_style/output/omni_clip_03_lucas_interpolation_720p.mp4")
        assert mp4.is_file() and mp4.stat().st_size > 500_000
        postflight = json.loads((pair_dir / "postflight_video_audit.json").read_text(encoding="utf-8"))
        assert postflight["width"] == 1280 and postflight["height"] == 720
        assert postflight["frames"] == 96
        assert postflight["duration_s"] == 4.0
        assert postflight["faststart"] is True
        assert postflight["min_start_mae"] <= 18.0
        assert postflight["min_end_mae"] <= 40.0
