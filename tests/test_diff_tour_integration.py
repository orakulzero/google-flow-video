"""
tests/test_diff_tour_integration.py
Integration tests for the `init-co-jp/diff-tour` Senior Engineer Code Walkthrough
bridge (`src/flow_diff_tour.py`), CLI (`--engine diff-tour`), and FastAPI endpoints
(`/api/flow/diff-tour/validate`, `/api/flow/diff-tour/render`).
"""

from __future__ import annotations

from pathlib import Path
import sys

from fastapi.testclient import TestClient

ROOT_DIR = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from flow_api import app
from flow_cli import run_cli
from flow_diff_tour import (
    SENIOR_AUDIT_DIMENSIONS,
    build_diff_tour_from_git_range,
    draw_diff_tour_step_at_t,
    drop_revealing_asks,
    render_diff_tour_to_mp4,
    run_tour_cli_dump,
    validate_diff_tour,
    verify_tour_code_refs_against_git,
)


def test_senior_audit_dimensions_cover_all_8_lessons() -> None:
    assert len(SENIOR_AUDIT_DIMENSIONS) == 8
    ids = [d["id"] for d in SENIOR_AUDIT_DIMENSIONS]
    assert ids == [
        "L1_PROMISES",
        "L2_FAILURE",
        "L3_OPERATIONS",
        "L4_TRUST",
        "L5_SCALE",
        "L6_DESIGN",
        "L7_TESTS",
        "L8_AI_TRAPS",
    ]


def test_validate_diff_tour_and_drop_revealing_asks() -> None:
    tour_doc = build_diff_tour_from_git_range(ROOT_DIR, target_file="src/flow_manimgx.py")
    val = validate_diff_tour(tour_doc)
    assert val["ok"] is True, val["errors"]
    assert val["chapter_count"] == 2
    assert val["step_count"] == 4

    # Verify drop_revealing_asks strips asks on the step before a question step
    raw_tour = {
        "version": 1,
        "title": "Ask Strip Test",
        "base": "HEAD",
        "head": "HEAD",
        "chapters": [
            {
                "title": "Ch1",
                "steps": [
                    {
                        "title": "Step 1",
                        "asks": ["Should be removed because Step 2 is a question"],
                        "blocks": [{"p": "Setup context.", "basis": "fact"}],
                    },
                    {
                        "title": "Step 2 Question",
                        "question": True,
                        "asks": ["Should also be removed"],
                        "blocks": [{"p": "What happens on duplicate request?"}],
                    },
                    {
                        "title": "Step 3 Answer",
                        "asks": ["Kept on answer step"],
                        "blocks": [{"p": "Idempotency key guards it.", "basis": "fact"}],
                    },
                ],
            }
        ],
    }
    cleaned = drop_revealing_asks(raw_tour)
    steps = cleaned["chapters"][0]["steps"]
    assert "asks" not in steps[0]
    assert "asks" not in steps[1]
    assert steps[2].get("asks") == ["Kept on answer step"]


def test_validate_diff_tour_rejects_invalid_blocks_and_basis() -> None:
    bad_tour = {
        "version": 2,
        "title": "Invalid Tour",
        "base": "HEAD",
        "head": "HEAD",
        "chapters": [
            {
                "title": "Ch1",
                "steps": [
                    {
                        "title": "Question with illegal basis",
                        "question": True,
                        "blocks": [
                            {"p": "Question text", "basis": "fact"},
                            {
                                "timeline": {
                                    "lanes": ["A", "B", "C", "D", "E"],
                                    "events": [{"lane": "A", "to": "B", "text": "msg"}],
                                }
                            },
                        ],
                    }
                ],
            }
        ],
    }
    val = validate_diff_tour(bad_tour)
    assert val["ok"] is False
    joined = " | ".join(val["errors"])
    assert "unsupported version" in joined
    assert "question steps must not attach basis" in joined
    assert "timeline: needs 1 to 4 lanes" in joined


def test_verify_tour_code_refs_against_git_and_native_cli_dump(tmp_path: Path) -> None:
    tour_doc = build_diff_tour_from_git_range(ROOT_DIR, target_file="src/flow_manimgx.py")
    git_rep = verify_tour_code_refs_against_git(tour_doc, ROOT_DIR)
    assert git_rep["ok"] is True, git_rep["errors"]
    assert git_rep["verified_count"] >= 2

    tour_json = tmp_path / "sample_tour.json"
    import json

    tour_json.write_text(json.dumps(tour_doc, indent=2), encoding="utf-8")
    dump_res = run_tour_cli_dump(tour_json, ROOT_DIR, cols=110, rows=34)
    assert dump_res["ok"] is True
    assert "flow_manimgx.py" in dump_res["output"]


def test_draw_and_render_diff_tour_to_mp4(tmp_path: Path) -> None:
    tour_doc = build_diff_tour_from_git_range(ROOT_DIR, target_file="src/flow_manimgx.py")
    first_step = tour_doc["chapters"][0]["steps"][0]
    frame = draw_diff_tour_step_at_t(
        first_step,
        chapter_title="1. Intent and System Map",
        step_index=1,
        total_steps=4,
        t_local=0.5,
        step_duration=2.0,
        repo_path=ROOT_DIR,
        width=640,
        height=360,
        active_word_idx=1,
        words=["Senior", "engineer", "tour"],
    )
    assert frame.size == (640, 360)

    out_mp4 = tmp_path / "tour_walkthrough.mp4"
    res = render_diff_tour_to_mp4(
        tour_doc,
        out_mp4,
        repo_path=ROOT_DIR,
        width=480,
        height=270,
        fps=10,
        max_steps=2,
        cols=2,
        rows=2,
    )
    assert res["ok"] is True
    assert out_mp4.is_file()
    header = out_mp4.read_bytes()[:32]
    assert b"ftyp" in header
    assert Path(res["output_srt"]).is_file()
    assert Path(res["output_vtt"]).is_file()
    assert Path(res["contact_sheet_png"]).is_file()
    assert res["contact_sheet"]["ok"] is True


def test_diff_tour_fastapi_endpoints_and_cli(tmp_path: Path) -> None:
    client = TestClient(app)
    val_resp = client.post(
        "/api/flow/diff-tour/validate",
        json={"repo_path": str(ROOT_DIR), "title": "API Diff Tour Check"},
    )
    assert val_resp.status_code == 200
    val_data = val_resp.json()
    assert val_data["ok"] is True
    assert len(val_data["audit_dimensions"]) == 8

    ren_resp = client.post(
        "/api/flow/diff-tour/render",
        json={
            "repo_path": str(ROOT_DIR),
            "title": "API Diff Tour Render",
            "width": 480,
            "height": 270,
            "fps": 10,
            "max_steps": 1,
        },
    )
    assert ren_resp.status_code == 200
    ren_data = ren_resp.json()
    assert ren_data["ok"] is True
    assert ren_data["video_size_bytes"] > 1000

    cli_dry = run_cli(
        [
            "--engine",
            "diff-tour",
            "--output-dir",
            str(tmp_path / "cli_tour"),
            "--dry-run",
        ]
    )
    assert cli_dry["engine"] == "diff-tour"
    assert cli_dry["validation"]["ok"] is True
    assert cli_dry["git_verification"]["ok"] is True
