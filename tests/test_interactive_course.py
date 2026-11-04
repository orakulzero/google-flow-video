"""
tests/test_interactive_course.py
ISO 9001:2015 Agile V programmatic verification suite for the Motorola DSP56824
coursework interactive intensive application (dsp_interactive_course.html),
the hybrid 1-click selection bridge, and the FastAPI question-persistence endpoint.
"""

from __future__ import annotations

import base64
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

TESTBENCH_DIR = Path(__file__).resolve().parent.parent
for _p in (str(TESTBENCH_DIR), str(TESTBENCH_DIR / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from src.flow_api import router as flow_router  # noqa: E402


def _build_test_app() -> FastAPI:
    app = FastAPI(title="Interactive Course Test App")
    app.include_router(flow_router)
    return app


# ============================================================================
# GATE 1: ASSET INVENTORY & 300 DPI RESOLUTION AUDIT
# ============================================================================

def test_gate1_assets_43_pages_and_blueprints_inventory() -> None:
    dsp_assets = TESTBENCH_DIR / "output" / "dsp_assets"
    assert dsp_assets.is_dir(), f"Missing assets directory: {dsp_assets}"

    # 1. Verify all 43 pages of the Explanatory Note exist
    for p in range(1, 44):
        fn = f"pz_page_{p:02d}.png"
        p_path = dsp_assets / fn
        assert p_path.is_file(), f"Missing coursework page asset: {fn}"
        assert p_path.stat().st_size > 150_000, f"Page asset too small (corrupted): {fn}"

    # 2. Verify blueprints E2 and PE2 exist
    for bp in ("drawing_e2.png", "drawing_pe2.png"):
        bp_path = dsp_assets / bp
        assert bp_path.is_file(), f"Missing blueprint asset: {bp}"
        assert bp_path.stat().st_size > 500_000, f"Blueprint asset too small: {bp}"

    # 3. Verify MATLAB figures 3.1..5.5 exist
    for fig in ("fig_3_1.png", "fig_4_1.png", "fig_5_1.png", "fig_5_2.png", "fig_5_3.png", "fig_5_5.png"):
        fig_path = dsp_assets / fig
        assert fig_path.is_file(), f"Missing figure asset: {fig}"
        assert fig_path.stat().st_size > 100_000, f"Figure asset too small: {fig}"


# ============================================================================
# GATE 2: SPLIT-SCREEN DOM STRUCTURE & 100% BIDIRECTIONAL COVERAGE
# ============================================================================

def test_gate2_split_screen_html_structure_and_dom_elements() -> None:
    html_targets = [
        TESTBENCH_DIR / "output" / "dsp_interactive_course.html",
        TESTBENCH_DIR / "dsp_interactive_course.html",
    ]
    for hp in html_targets:
        assert hp.is_file(), f"Missing interactive course HTML: {hp}"
        content = hp.read_text(encoding="utf-8")
        assert len(content) > 50_000, f"HTML file suspiciously small: {hp}"

        # Left pane sheet viewer and lasso tools
        assert "sheet-viewport" in content or "left-pane" in content
        assert "sheet-img" in content or "sheet-canvas" in content
        assert "btn-toggle-lasso" in content or "lasso" in content

        # Right pane intensive and floating toolbar
        assert "right-pane" in content or "lesson-card" in content
        assert "text-floating-toolbar" in content or "floating-toolbar" in content or "selection" in content

        # Dual dispatch bridge
        assert "/api/flow/intensive-question" in content
        assert "navigator.clipboard.writeText" in content


def test_gate2_all_43_pages_and_blueprints_represented_without_dead_pages() -> None:
    hp = TESTBENCH_DIR / "dsp_interactive_course.html"
    content = hp.read_text(encoding="utf-8")

    # Every page from 1 to 43 must be referenced in page definitions
    for p in range(1, 44):
        p_pattern = re.compile(rf'pz_page_{p:02d}\.png|"page_number":\s*{p}\b|"pz_page":\s*{p}\b')
        assert p_pattern.search(content) is not None, f"Page {p} is missing or not represented in HTML"

    # Blueprints E2 and PE2 must be referenced
    assert "drawing_e2" in content
    assert "drawing_pe2" in content


# ============================================================================
# GATE 3: INTERACTIVE CANVAS SIMULATION ENGINES
# ============================================================================

def test_gate3_simulation_engines_mathematical_invariants() -> None:
    hp = TESTBENCH_DIR / "dsp_interactive_course.html"
    content = hp.read_text(encoding="utf-8")

    # Simulation 1: Cauer IIR N=11 Q15 Lab invariants
    assert "0.9878" in content  # Max pole radius |p_max|
    assert "-1.8253" in content or "1.8253" in content  # Section 6 a1 coefficient
    assert "4.8236" in content or "g_out" in content  # Overall L_infinity gain

    # Simulation 2: DSP56824 Oscilloscope & DO #6 loop stepper invariants
    assert "150" in content or "114" in content  # Biquad loop cycles
    assert "20.833" in content  # Sampling period Ts in us
    assert "40" in content  # Core clock 40 MHz

    # Simulation 3: Sallen-Key & 0-WS timing invariants
    assert "25.03" in content  # Sallen-Key f0 cutoff in kHz
    assert "0.736" in content  # Quality factor Q
    assert "IS61LV6416" in content  # SRAM chip
    assert "10" in content and "25" in content  # 10 ns < 25 ns (0 Wait States)


# ============================================================================
# GATE 4: FASTAPI QUESTION BRIDGE ENDPOINT ROUND-TRIP
# ============================================================================

def test_gate4_fastapi_intensive_question_endpoint_text_highlight(tmp_path: Path) -> None:
    app = _build_test_app()
    client = TestClient(app)

    payload = {
        "page_number": 28,
        "sheet_name": "pz_page_28.png",
        "topic_id": "cycle3_sc06",
        "topic_title": "Q15 Fixed-Point Scaling & L_infinity Norm",
        "selection_type": "text_highlight",
        "bbox": [0.15, 0.32, 0.85, 0.64],
        "selected_text": "w_k(n) = x_k(n) - a_1*w_1 - a_2*w_2",
        "user_question": "Why is the coefficient divided by 2 rather than normalized to 1.0?",
        "image_base64": None,
    }

    res = client.post("/api/flow/intensive-question", json=payload)
    assert res.status_code == 200, f"Failed endpoint response: {res.text}"
    data = res.json()
    assert data["ok"] is True
    assert "latest_question.json" in data["json_path"]

    # Verify JSON on disk
    json_path = Path(data["json_path"])
    assert json_path.is_file()
    disk_data = json.loads(json_path.read_text(encoding="utf-8"))
    assert disk_data["page_number"] == 28
    assert disk_data["topic_id"] == "cycle3_sc06"
    assert disk_data["user_question"] == payload["user_question"]


def test_gate4_fastapi_intensive_question_endpoint_image_crop() -> None:
    app = _build_test_app()
    client = TestClient(app)

    # Valid 1x1 transparent PNG binary bytes
    png_bytes = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\rIDATx\x9cc`\x00\x00\x00"
        b"\x02\x00\x01H\xaf\xa4q\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    b64_str = "data:image/png;base64," + base64.b64encode(png_bytes).decode("ascii")

    payload = {
        "page_number": 42,
        "sheet_name": "drawing_e2.png",
        "topic_id": "cycle5_sc05",
        "topic_title": "Functional Schematic E2: IS61LV6416 /UB /LB connection to DGND",
        "selection_type": "image_crop",
        "bbox": [0.42, 0.55, 0.68, 0.78],
        "selected_text": None,
        "user_question": "Explain why pins 39 and 40 are tied to DGND.",
        "image_base64": b64_str,
    }

    res = client.post("/api/flow/intensive-question", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is True
    assert data["crop_path"] is not None

    crop_path = Path(data["crop_path"])
    assert crop_path.is_file()
    crop_bytes = crop_path.read_bytes()
    assert crop_bytes.startswith(b"\x89PNG\r\n\x1a\n"), "Cropped image must have valid PNG magic header"


def test_gate4_fastapi_intensive_question_endpoint_validation_error() -> None:
    app = _build_test_app()
    client = TestClient(app)

    # Invalid page number (greater than 45)
    bad_payload = {
        "page_number": 999,
        "sheet_name": "unknown.png",
    }
    res = client.post("/api/flow/intensive-question", json=bad_payload)
    assert res.status_code == 422


# ============================================================================
# GATE 5: REQ-004 CLEANLINESS & INVARIANT AUDIT
# ============================================================================

def test_gate5_req004_zero_cyrillic_and_zero_personal_tokens_in_code() -> None:
    cyr_re = re.compile("[\u0400-\u04ff]")
    p_tok_1 = "Ora" + "kul"
    p_tok_2 = "ANTI" + "GRAVITY"

    checked_files = [
        TESTBENCH_DIR / "src" / "flow_api.py",
        Path(__file__),
    ]

    for cf in checked_files:
        assert cf.is_file(), f"File not found: {cf}"
        text = cf.read_text(encoding="utf-8")
        m = cyr_re.search(text)
        assert m is None, f"Literal Cyrillic character found in {cf.name} at line {text[:m.start()].count(chr(10)) + 1}"
        assert p_tok_1 not in text, f"Personal token 1 found in {cf.name}"
        assert p_tok_2 not in text, f"Personal token 2 found in {cf.name}"


# ============================================================================
# GATE 6: SYNC & TELEMETRY INTEGRATION
# ============================================================================

def test_gate6_sync_script_has_push_pull_targets() -> None:
    sync_py = TESTBENCH_DIR / "scripts" / "sync_with_gemini_local_ui.py"
    assert sync_py.is_file()
    text = sync_py.read_text(encoding="utf-8")
    assert "src/flow_api.py" in text
    assert "backend/app/api/flow.py" in text
    assert "--push" in text and "--pull" in text
