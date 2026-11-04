"""Milestone 2 Empirical Challenger Adversarial Test Suite.

Probes VeoStylePipeline pair/frame resolution, parameter boundaries,
mock injection, and executes anti-cheat verification.
"""

from __future__ import annotations

import ast
import asyncio
import json
from pathlib import Path
import sys
from typing import Any, Dict, List
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from veo_arcane_style.src.veo_style_pipeline import VeoStylePipeline


def probe_dataset_pairs_and_frames(pipeline: VeoStylePipeline) -> Dict[str, Any]:
    """Probe all 11 pairs and 56 frames for physical existence and integrity."""
    pairs = pipeline.list_pairs()
    frames = pipeline.list_curated_frames()
    results: Dict[str, Any] = {
        "total_pairs_in_index": len(pairs),
        "total_frames_in_index": len(frames),
        "pairs_verified": [],
        "frames_verified": [],
        "invalid_pair_queries": {},
        "invalid_frame_queries": {},
    }

    # 1. Query all pairs via load_pair
    for p_info in pairs:
        pid = p_info["pair_id"]
        pair_data = pipeline.load_pair(pid)
        f_path: Path = pair_data["first_frame_path"]
        l_path: Path = pair_data["last_frame_path"]
        m_path: Path | None = pair_data.get("mid_impact_path")

        assert f_path.is_file(), f"First frame missing for {pid}: {f_path}"
        assert l_path.is_file(), f"Last frame missing for {pid}: {l_path}"
        if m_path:
            assert m_path.is_file(), f"Mid impact frame missing for {pid}: {m_path}"

        with Image.open(f_path) as im_f:
            f_w, f_h = im_f.size
        with Image.open(l_path) as im_l:
            l_w, l_h = im_l.size

        results["pairs_verified"].append({
            "pair_id": pid,
            "character": pair_data.get("character"),
            "first_frame_size": [f_w, f_h],
            "first_frame_bytes": f_path.stat().st_size,
            "last_frame_size": [l_w, l_h],
            "last_frame_bytes": l_path.stat().st_size,
            "has_mid_impact": m_path is not None,
        })

    # 2. Query all frames via load_curated_frame and load_reference
    for f_info in frames:
        fid = f_info["id"]
        frame_data = pipeline.load_curated_frame(fid)
        ref_data = pipeline.load_reference(fid)
        assert frame_data["file_path"] == ref_data["file_path"]
        assert frame_data["file_path"].is_file()

        results["frames_verified"].append({
            "id": fid,
            "filename": f_info.get("filename"),
            "exists": True,
            "bytes": frame_data["file_path"].stat().st_size,
        })

    # 3. Probe invalid pair IDs
    invalid_pids = ["non_existent_pair_999", "pair_fake_123", "", "   ", "PAIR_UPPERCASE_INVALID"]
    for inv in invalid_pids:
        try:
            pipeline.load_pair(inv)
            results["invalid_pair_queries"][inv] = "UNEXPECTED_SUCCESS"
        except KeyError as exc:
            results["invalid_pair_queries"][inv] = f"KeyError: {exc}"
        except Exception as exc:
            results["invalid_pair_queries"][inv] = f"{type(exc).__name__}: {exc}"

    # 4. Probe invalid frame IDs
    invalid_fids = ["non_existent_frame_999", "arcane_curated_999", "", "   ", "FRAME_INVALID"]
    for inv in invalid_fids:
        try:
            pipeline.load_curated_frame(inv)
            results["invalid_frame_queries"][inv] = "UNEXPECTED_SUCCESS"
        except KeyError as exc:
            results["invalid_frame_queries"][inv] = f"KeyError: {exc}"
        except Exception as exc:
            results["invalid_frame_queries"][inv] = f"{type(exc).__name__}: {exc}"

    return results


class MockValidFlowClient:
    """Mock Flow client simulating successful Google Flow execution."""

    def __init__(self) -> None:
        self.call_history: List[Dict[str, Any]] = []

    async def generate_start_and_end_clip(
        self,
        prompt: str,
        start_image: Path,
        end_image: Path,
        duration: int,
        out_path: Path,
    ) -> Dict[str, Any]:
        self.call_history.append({
            "prompt": prompt,
            "start_image": start_image,
            "end_image": end_image,
            "duration": duration,
            "out_path": out_path,
        })
        out_path.parent.mkdir(parents=True, exist_ok=True)
        # Write valid ISO MP4 header mock
        out_path.write_bytes(b"\x00\x00\x00\x20ftypisom" + b"\x00" * 512)
        return {
            "ok": True,
            "pair_id": "mock_pair",
            "prompt": prompt,
            "duration": duration,
            "first_frame": str(start_image),
            "last_frame": str(end_image),
            "output_path": str(out_path),
            "native_audio": True,
        }


async def probe_parameter_boundaries_and_mock(pipeline: VeoStylePipeline, tmp_dir: Path) -> Dict[str, Any]:
    """Test boundary conditions for prompt overrides, durations, and mock injection."""
    results: Dict[str, Any] = {}
    test_pair = pipeline.load_pair("pair_170629_shot_000")

    # 1. Prompt override tests
    p_default = pipeline.build_i2v_prompt(test_pair)
    p_custom = pipeline.build_i2v_prompt(test_pair, prompt_override="Fortiche Custom Style Override")
    p_whitespace = pipeline.build_i2v_prompt(test_pair, prompt_override="    ")
    p_empty = pipeline.build_i2v_prompt(test_pair, prompt_override="")
    p_empty_pair = pipeline.build_i2v_prompt({})

    results["prompt_tests"] = {
        "default_contains_character": "Vi" in p_default,
        "custom_override_used": p_custom == "Fortiche Custom Style Override",
        "whitespace_falls_back": p_whitespace == p_default,
        "empty_falls_back": p_empty == p_default,
        "empty_pair_handled_gracefully": len(p_empty_pair) > 50,
    }

    # 2. Duration boundary probe via mock client
    mock_client = MockValidFlowClient()
    duration_probes = [-10, 0, 4, 8, 15, 100]
    duration_results: Dict[int, Any] = {}

    for d in duration_probes:
        out_clip = tmp_dir / f"test_clip_d{d}.mp4"
        res = await pipeline.generate_i2v_clip(
            pair_id="pair_170629_shot_000",
            duration=d,
            client=mock_client,
            output_path=out_clip,
        )
        duration_results[d] = {
            "returned_duration": res.get("duration"),
            "file_written": out_clip.is_file(),
            "file_size": out_clip.stat().st_size if out_clip.is_file() else 0,
        }
    results["duration_probes"] = duration_results

    # 3. Reference frames in _dispatch_generate
    try:
        await pipeline._dispatch_generate(
            prompt="Test",
            reference_frames=[],
            mode="i2v",
            duration=4,
            out_path=tmp_dir / "dispatch_test.mp4",
        )
        results["empty_reference_frames_test"] = "UNEXPECTED_SUCCESS"
    except ValueError as exc:
        results["empty_reference_frames_test"] = f"ValueError: {exc}"
    except Exception as exc:
        results["empty_reference_frames_test"] = f"{type(exc).__name__}: {exc}"

    # 4. Probe generate_clip synchronous wrapper vulnerability
    import threading
    sync_thread_res: Dict[str, str] = {}
    def call_sync():
        try:
            pipeline.generate_clip(prompt="Test", reference_frames=[Path("fake.png")])
            sync_thread_res["status"] = "UNEXPECTED_SUCCESS"
        except Exception as exc:
            sync_thread_res["status"] = f"{type(exc).__name__}: {exc}"

    t = threading.Thread(target=call_sync)
    t.start()
    t.join(timeout=3.0)
    results["generate_clip_sync_thread_probe"] = sync_thread_res.get("status", "TIMEOUT_DEADLOCK")

    return results


def probe_anti_cheat_compliance(pipeline_src_path: Path, conditioning_src_path: Path) -> Dict[str, Any]:
    """Perform static AST and lexical audit for fake video / zoom / pan anti-cheat rules."""
    banned_tokens = [
        "cv2.resize",
        "cv2.warpAffine",
        "moviepy",
        "numpy.sin",
        "Ken-Burns",
        "ffmpeg -an",
        "zoom_pan",
        "Image.resize",
        "ImageDraw",
    ]
    findings: Dict[str, Any] = {}

    for label, src_path in [("pipeline", pipeline_src_path), ("conditioning", conditioning_src_path)]:
        content = src_path.read_text(encoding="utf-8")
        parsed = ast.parse(content, filename=str(src_path))
        token_hits = [tok for tok in banned_tokens if tok in content]

        # Audit imports
        imports = []
        for node in ast.walk(parsed):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.append(node.module)

        findings[label] = {
            "source_file": str(src_path),
            "banned_token_hits": token_hits,
            "has_banned_tokens": len(token_hits) > 0,
            "all_imports": sorted(list(set(imports))),
            "mentions_anti_cheat": "anti-cheat" in content.lower(),
        }

    return findings


async def main() -> None:
    pipeline = VeoStylePipeline()
    repo_root = Path(__file__).resolve().parent.parent
    output_dir = repo_root / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    tmp_test_dir = output_dir / "challenger_tmp"
    tmp_test_dir.mkdir(parents=True, exist_ok=True)

    print("=== [1/3] Probing Dataset Pairs and Curated Frames ===")
    dataset_res = probe_dataset_pairs_and_frames(pipeline)
    print(f"Total pairs verified on disk: {len(dataset_res['pairs_verified'])} / {dataset_res['total_pairs_in_index']}")
    print(f"Total curated frames verified on disk: {len(dataset_res['frames_verified'])} / {dataset_res['total_frames_in_index']}")

    print("\n=== [2/3] Probing Parameter Boundaries & Mock Client ===")
    param_res = await probe_parameter_boundaries_and_mock(pipeline, tmp_test_dir)
    print("Prompt tests:", param_res["prompt_tests"])
    print("Duration probes:", param_res["duration_probes"])
    print("Empty reference frames:", param_res["empty_reference_frames_test"])

    print("\n=== [3/3] Probing Anti-Cheat Compliance ===")
    pipe_path = repo_root / "veo_arcane_style" / "src" / "veo_style_pipeline.py"
    cond_path = repo_root / "veo_arcane_style" / "src" / "flow_conditioning.py"
    anti_cheat_res = probe_anti_cheat_compliance(pipe_path, cond_path)
    print("Anti-cheat hits in pipeline:", anti_cheat_res["pipeline"]["banned_token_hits"])
    print("Anti-cheat hits in conditioning:", anti_cheat_res["conditioning"]["banned_token_hits"])

    final_report = {
        "status": "COMPLETED",
        "dataset_probe": dataset_res,
        "parameter_boundaries": param_res,
        "anti_cheat_audit": anti_cheat_res,
    }

    report_path = output_dir / "m2_challenger_empirical_report.json"
    report_path.write_text(json.dumps(final_report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nFinal report saved to: {report_path}")


if __name__ == "__main__":
    asyncio.run(main())
