"""
ISO 9001:2015 Agile V Test Suite for Google Flow Educational Video Studio L4 (BL-20261023-FLOW-L4).
Covers:
- REQ-001: flow_audio_video (FemaleVoiceoverOptimizer & MultiSceneVideoAssembler)
- REQ-002: flow_live_rpc (FlowLiveRPCBridge for labs.google/fx/tools/flow)
- REQ-003: flow_api & flow_studio_ui (Standalone L4 Web UI, /api/flow/render-lesson, /api/flow/batch, /api/flow/report-to-root)
- REQ-004: Zero Cyrillic & Zero Personal Paths in all flow_video_testbench source & test files
"""

from __future__ import annotations

import json
from pathlib import Path
import re
import sys
from typing import Any, Dict, List

from fastapi.testclient import TestClient
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"
for _p in (str(REPO_ROOT), str(SRC_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)


# ============================================================================
# REQ-001: flow_audio_video (Female Voiceover Accent Profiler & Multi-Scene MP4)
# ============================================================================


def test_req001_female_voiceover_optimizer_enforces_female_gender() -> None:
    from flow_audio_video import FemaleVoiceoverOptimizer

    optimizer = FemaleVoiceoverOptimizer()
    assert getattr(optimizer, "VOICE_GENDER", "female") == "female"

    with pytest.raises(ValueError, match="female"):
        optimizer.optimize_script(
            "Attention weights scale dot products across token representations.",
            voice_gender="male",
        )


def test_req001_female_voiceover_optimizer_rejects_empty_narration() -> None:
    from flow_audio_video import FemaleVoiceoverOptimizer

    optimizer = FemaleVoiceoverOptimizer()
    with pytest.raises(ValueError):
        optimizer.optimize_script("   ", voice_gender="female")


def test_req001_female_voiceover_optimizer_prosody_and_metrics() -> None:
    from flow_audio_video import FemaleVoiceoverOptimizer

    optimizer = FemaleVoiceoverOptimizer()
    sample_text = (
        "In phase one, we examine multi-head attention geometry. "
        "Next, we project queries and keys into a lower-dimensional latent subspace."
    )
    result = optimizer.optimize_script(sample_text, voice_gender="female")

    assert result["voice_gender"] == "female"
    assert result["voice_profile"] == "veo-3.1-female-narrator-v2"
    annotated = result["annotated_script"]
    assert isinstance(annotated, str) and len(annotated) > len(sample_text)
    assert any(marker in annotated for marker in ("[breath]", "[emphasis]", "[pause]"))
    assert isinstance(result["estimated_duration_sec"], float)
    assert result["estimated_duration_sec"] > 0.0
    assert isinstance(result["word_count"], int)
    assert result["word_count"] >= 18
    assert isinstance(result["speaking_rate_wpm"], float)
    assert result["speaking_rate_wpm"] > 0.0


def test_req001_multi_scene_video_assembler_rejects_empty_clips() -> None:
    from flow_audio_video import MultiSceneVideoAssembler

    assembler = MultiSceneVideoAssembler()
    with pytest.raises(ValueError):
        assembler.concat_scene_mp4_clips([], title="Empty Lesson")


def test_req001_multi_scene_video_assembler_concatenates_mp4_clips() -> None:
    from flow_audio_video import MultiSceneVideoAssembler
    from flow_bridge import synthesize_minimal_mp4

    clip_a = synthesize_minimal_mp4(title="Scene 1", duration_sec=4)
    clip_b = synthesize_minimal_mp4(title="Scene 2", duration_sec=6)
    clip_c = synthesize_minimal_mp4(title="Scene 3", duration_sec=5)

    assembler = MultiSceneVideoAssembler()
    out = assembler.concat_scene_mp4_clips(
        [clip_a, clip_b, clip_c],
        title="Assembled Transformer Lesson",
    )

    assert isinstance(out, dict)
    mp4_bytes = out["mp4_bytes"]
    assert isinstance(mp4_bytes, bytes)
    assert mp4_bytes[4:8] == b"ftyp"
    assert len(mp4_bytes) > 64
    assert out["scene_count"] == 3
    assert out["total_bytes"] == len(mp4_bytes)
    assert out["engine"] in ("ffmpeg", "iso_bmff_concat")


# ============================================================================
# REQ-002: flow_live_rpc (FlowLiveRPCBridge for labs.google/fx/tools/flow)
# ============================================================================


def test_req002_flow_live_rpc_build_veo_scene_payload() -> None:
    from flow_live_rpc import FlowLiveRPCBridge

    bridge = FlowLiveRPCBridge()
    payload = bridge.build_veo_scene_payload(
        scene_title="Part 1: Query-Key Dot Product",
        visual_prompt="3D glowing tensor grid showing attention matrix weights",
        narration="Each query vector attends to all key vectors across the sequence.",
        aspect_ratio="16:9",
        duration_sec=8,
    )

    assert payload["rpc_id"] == "VideoFXGenerateSceneClip"
    assert payload["model"] == "veo-3.1-flow"
    assert payload["aspect_ratio"] == "16:9"
    assert payload["duration_sec"] == 8
    voice_cfg = payload["voice_config"]
    assert voice_cfg["gender"] == "female"
    assert voice_cfg["profile"] == "veo-3.1-female-narrator-v2"
    assert isinstance(voice_cfg["annotated_narration"], str)
    assert len(voice_cfg["annotated_narration"]) > 10


def test_req002_flow_live_rpc_render_scene_with_mock_transport() -> None:
    from flow_bridge import synthesize_minimal_mp4
    from flow_live_rpc import FlowLiveRPCBridge

    captured_payloads: List[Dict[str, Any]] = []
    mock_clip = synthesize_minimal_mp4(title="Mock Live Clip", duration_sec=8)

    def _mock_transport(payload: Dict[str, Any]) -> Dict[str, Any]:
        captured_payloads.append(payload)
        return {
            "ok": True,
            "mp4_bytes": mock_clip,
            "operation_id": "op_live_veo_001",
        }

    bridge = FlowLiveRPCBridge(
        cookie_header="SAPISID=test_cookie_value",
        transport=_mock_transport,
    )
    res = bridge.render_scene(
        scene_title="Scene 1: Attention Scaling",
        visual_prompt="Cinematic 3D visualization of scaled dot-product attention",
        narration="Dividing by the square root of dimension stabilizes gradients.",
        aspect_ratio="16:9",
        duration_sec=8,
    )

    assert len(captured_payloads) == 1
    assert captured_payloads[0]["rpc_id"] == "VideoFXGenerateSceneClip"
    assert res["ok"] is True
    assert res["mode"] == "live_rpc"
    assert res["voice_gender"] == "female"
    assert res["mp4_bytes"][4:8] == b"ftyp"
    assert isinstance(res["annotated_narration"], str)


def test_req002_flow_live_rpc_render_scene_offline_fallback() -> None:
    from flow_live_rpc import FlowLiveRPCBridge

    bridge = FlowLiveRPCBridge(cookie_header=None, transport=None)
    res = bridge.render_scene(
        scene_title="Scene 2: Softmax Normalization",
        visual_prompt="3D probability simplex with glowing attention weights",
        narration="Softmax converts raw logits into normalized probability weights.",
        aspect_ratio="16:9",
        duration_sec=6,
    )

    assert res["ok"] is True
    assert res["mode"] == "local_synth"
    assert res["voice_gender"] == "female"
    assert isinstance(res["mp4_bytes"], bytes)
    assert res["mp4_bytes"][4:8] == b"ftyp"
    assert len(res["mp4_bytes"]) > 64


# ============================================================================
# REQ-003: flow_api & flow_studio_ui (Standalone L4 Web UI, Batch & Reporting)
# ============================================================================


def test_req003_studio_ui_root_get_contains_required_testids() -> None:
    from flow_api import app

    with TestClient(app) as client:
        resp = client.get("/")
        assert resp.status_code == 200
        assert "text/html" in resp.headers.get("content-type", "")
        html = resp.text
        assert 'data-testid="flow-l4-studio"' in html
        assert 'data-testid="flow-topic-input"' in html
        assert 'data-testid="flow-female-voice-badge"' in html
        assert 'data-testid="flow-render-all-btn"' in html
        assert 'data-testid="flow-report-root-btn"' in html


def test_req003_post_render_lesson_end_to_end() -> None:
    from flow_api import app

    with TestClient(app) as client:
        resp = client.post(
            "/api/flow/render-lesson",
            json={
                "topic": "Transformer Attention Mechanism",
                "scene_count": 3,
                "audience": "Engineers",
                "style": "3D technical animation",
                "duration_per_scene_sec": 6,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["video_size_bytes"] > 64
        assert data["subtitles_vtt"].startswith("WEBVTT")
        assert "00:00:00,000 -->" in data["subtitles_srt"]

        proj = data["project"]
        assert proj["status"] == "assembled"
        assert proj["voice_gender"] == "female"
        assert len(proj["scenes"]) == 3
        for sc in proj["scenes"]:
            assert sc.get("annotated_narration")
            assert sc.get("status") == "completed"


def test_req003_post_batch_lessons_queue() -> None:
    from flow_api import app

    with TestClient(app) as client:
        resp = client.post(
            "/api/flow/batch",
            json={
                "topics": ["Lesson 1: Qubits", "Lesson 2: Quantum Gates"],
                "scene_count": 2,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["batch_count"] == 2
        assert len(data["projects"]) == 2
        for proj in data["projects"]:
            assert proj["status"] == "assembled"
            assert proj["voice_gender"] == "female"


def test_req003_post_batch_rejects_empty_topics() -> None:
    from flow_api import app

    with TestClient(app) as client:
        resp = client.post("/api/flow/batch", json={"topics": [], "scene_count": 2})
        assert resp.status_code == 400


def test_req003_post_report_to_root_writes_jsonl_and_markdown(tmp_path: Path) -> None:
    from flow_api import app

    with TestClient(app) as client:
        resp = client.post(
            "/api/flow/report-to-root",
            json={
                "status": "PASS",
                "summary": "L4 testbench render verified",
                "metrics": {"lessons": 1, "scenes": 3},
                "root_brain_dir": str(tmp_path),
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True

        jsonl_file = tmp_path / "child_session_reports.jsonl"
        md_file = tmp_path / "FLOW_STUDIO_HANDOFF_REPORT.md"
        assert jsonl_file.is_file()
        assert md_file.is_file()

        lines = [ln for ln in jsonl_file.read_text(encoding="utf-8").splitlines() if ln.strip()]
        assert len(lines) >= 1
        record = json.loads(lines[-1])
        assert record["status"] == "PASS"
        assert "L4 testbench render verified" in record["summary"]
        assert "L4 testbench render verified" in md_file.read_text(encoding="utf-8")


# ============================================================================
# REQ-004: Zero Cyrillic & Zero Personal Paths in Source & Test Files
# ============================================================================


def _target_testbench_files() -> List[Path]:
    return [
        REPO_ROOT / "src" / "flow_bridge.py",
        REPO_ROOT / "src" / "flow_api.py",
        REPO_ROOT / "src" / "flow_audio_video.py",
        REPO_ROOT / "src" / "flow_live_rpc.py",
        REPO_ROOT / "src" / "flow_studio_ui.py",
        REPO_ROOT / "tests" / "test_flow_studio.py",
        REPO_ROOT / "tests" / "test_flow_l4_studio.py",
    ]


def test_req004_zero_cyrillic_in_source_and_test_files() -> None:
    cyrillic_re = re.compile("[\u0400-\u04ff]")
    for path in _target_testbench_files():
        assert path.is_file(), f"Missing expected file: {path.name}"
        content = path.read_text(encoding="utf-8")
        match = cyrillic_re.search(content)
        assert match is None, f"Cyrillic character found in {path.name} at pos {match.start()}"


def test_req004_zero_personal_tokens_in_source_and_test_files() -> None:
    tok_a = ("Ora" + "kul").lower()
    tok_b = ("kuro" + "ora" + "kul" + "grey").lower()
    tok_c = ("ANTI" + "GRAVITY").lower()

    for path in _target_testbench_files():
        assert path.is_file(), f"Missing expected file: {path.name}"
        lowered = path.read_text(encoding="utf-8").lower()
        assert tok_a not in lowered, f"Forbidden personal token A in {path.name}"
        assert tok_b not in lowered, f"Forbidden personal token B in {path.name}"
        assert tok_c not in lowered, f"Forbidden workspace path token C in {path.name}"
