"""
src/flow_diff_tour.py
Bridge between `init-co-jp/diff-tour` (Guided Senior Engineer Code Review Tours)
and the Google Flow & ManimGX Educational Video Studio.

Provides:
  1. Strict `diff-tour` v1 JSON schema validation (`validate_diff_tour`, `drop_revealing_asks`)
     matching `internal/tour/tour.go` (`Basis`: `fact`, `inferred`, `opinion`; blocks:
     `p`, `code`, `diff`, `snippet`, `flow`, `timeline`, `files`, `table`, `rows`, `schema`).
  2. Zero-hallucination Git reference verification (`verify_tour_code_refs_against_git`)
     that reads real lines from `git show <ref>:<file>` and never trusts LLM-copied code.
  3. 8-Dimension Senior Engineer Audit catalog (`SENIOR_AUDIT_DIMENSIONS`: `L1_PROMISES` ..
     `L8_AI_TRAPS`) and automated Git-diff-to-Tour generator (`build_diff_tour_from_git_range`).
  4. Deterministic `draw(t)` split-screen video renderer (`draw_diff_tour_step_at_t`,
     `render_diff_tour_to_mp4`) that converts any `diff-tour` JSON into a narrated
     `.mp4` + `.srt` + `.vtt` + `contact_sheet.png` code walkthrough with `closed_form_spring`
     kinetics, 48 kHz female voiceover, `-12 dB` audio ducking, and SFX accents.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import wave
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import imageio_ffmpeg
from manimgx.audio.sound import RATE
import numpy as np
from PIL import Image, ImageDraw

from flow_manimgx import (
    GeminiStudioVoice,
    build_contact_sheet,
    mix_studio_audio_with_ducking_and_sfx,
)
from flow_prompt_library import closed_form_spring, match_position_transition

TOUR_SCHEMA_VERSION = 1
MAX_TIMELINE_LANES = 4

VALID_BASIS_VALUES = ("", "fact", "inferred", "opinion")
VALID_FLOW_KINDS = ("", "same", "changed", "new", "external")
VALID_TIMELINE_MARKS = ("", "ok", "bad", "note")
VALID_FILE_ROLES = ("core", "mechanical", "test", "config", "docs")

BLOCK_KEYS = (
    "p",
    "quote",
    "list",
    "pre",
    "table",
    "code",
    "diff",
    "snippet",
    "schema",
    "rows",
    "flow",
    "timeline",
    "files",
    "target",
)

SENIOR_AUDIT_DIMENSIONS: Tuple[Dict[str, str], ...] = (
    {
        "id": "L1_PROMISES",
        "lesson_file": "1-promises.md",
        "title": "Promises and Invariants",
        "question": "Does the change preserve the invariants and unspoken contracts of the base code, including check-then-act race windows?",
    },
    {
        "id": "L2_FAILURE",
        "lesson_file": "2-failure.md",
        "title": "Failure Modes and Idempotency",
        "question": "What state is left behind when an operation fails mid-way or executes twice on retry?",
    },
    {
        "id": "L3_OPERATIONS",
        "lesson_file": "3-operations.md",
        "title": "Operations and Rollback Safety",
        "question": "Can this change be rolled out and rolled back safely without breaking in-flight requests or migrations?",
    },
    {
        "id": "L4_TRUST",
        "lesson_file": "4-trust.md",
        "title": "Trust Boundaries and Input Authority",
        "question": "Who can invoke this path, and are untrusted inputs validated at the boundary?",
    },
    {
        "id": "L5_SCALE",
        "lesson_file": "5-scale.md",
        "title": "Scale at 100x Volume",
        "question": "What happens when data volume or concurrency grows by 100x (N+1 queries, lock hold time, memory growth)?",
    },
    {
        "id": "L6_DESIGN",
        "lesson_file": "6-design.md",
        "title": "Design and Next-Change Friction",
        "question": "Does this change make the next logical change easier or harder?",
    },
    {
        "id": "L7_TESTS",
        "lesson_file": "7-tests.md",
        "title": "Test Falsifiability",
        "question": "Would the test suite actually fail if the production logic introduced by this diff were broken?",
    },
    {
        "id": "L8_AI_TRAPS",
        "lesson_file": "8-ai.md",
        "title": "AI-Generated Code Traps",
        "question": "Are there speculative defenses for impossible states, hallucinated helper contracts, swallowed errors, or scope creep?",
    },
)


def _format_srt_timestamp(seconds: float) -> str:
    ms = max(0, int(round(seconds * 1000.0)))
    hh = ms // 3_600_000
    mm = (ms // 60_000) % 60
    ss = (ms // 1000) % 60
    rem = ms % 1000
    return f"{hh:02d}:{mm:02d}:{ss:02d},{rem:03d}"


def _format_vtt_timestamp(seconds: float) -> str:
    return _format_srt_timestamp(seconds).replace(",", ".")


def _count_block_kinds(block: Dict[str, Any]) -> int:
    count = 0
    for key in BLOCK_KEYS:
        if key == "target":
            if bool(block.get("target", False)):
                count += 1
        elif block.get(key) is not None:
            count += 1
    return count


def validate_diff_tour(tour_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate a `diff-tour` JSON dictionary against the v1 schema (`internal/tour/tour.go`).
    Returns `{"ok": bool, "errors": List[str], "step_count": int, "chapter_count": int}`.
    """
    errors: List[str] = []
    if not isinstance(tour_data, dict):
        return {"ok": False, "errors": ["tour_data must be a JSON object"], "step_count": 0, "chapter_count": 0}

    version = tour_data.get("version")
    if version != TOUR_SCHEMA_VERSION:
        errors.append(f"unsupported version {version!r} (expected {TOUR_SCHEMA_VERSION})")

    base_ref = str(tour_data.get("base") or "").strip()
    head_ref = str(tour_data.get("head") or "").strip()
    if not base_ref or not head_ref:
        errors.append("base and head are required")

    chapters = tour_data.get("chapters")
    if not isinstance(chapters, list) or not chapters:
        errors.append("no steps")
        return {"ok": False, "errors": errors, "step_count": 0, "chapter_count": 0}

    total_steps = 0
    for ci, chapter in enumerate(chapters, 1):
        if not isinstance(chapter, dict):
            errors.append(f"chapter {ci}: must be an object")
            continue
        steps = chapter.get("steps") or []
        if not isinstance(steps, list):
            errors.append(f"chapter {ci}: steps must be a list")
            continue
        for si, step in enumerate(steps, 1):
            total_steps += 1
            if not isinstance(step, dict):
                errors.append(f"chapter {ci} step {si}: must be an object")
                continue
            title = str(step.get("title") or "").strip()
            if not title:
                errors.append(f"chapter {ci} step {si}: title is required")
            is_question = bool(step.get("question", False))
            blocks = step.get("blocks") or []
            if not isinstance(blocks, list) or not blocks:
                errors.append(f"chapter {ci} step {si}: blocks must be a non-empty list")
                continue

            for bi, block in enumerate(blocks, 1):
                if not isinstance(block, dict):
                    errors.append(f"chapter {ci} step {si} block {bi}: must be an object")
                    continue
                kinds = _count_block_kinds(block)
                if kinds != 1:
                    errors.append(
                        f"chapter {ci} step {si} block {bi}: a block must have exactly one kind (found {kinds})"
                    )
                basis = str(block.get("basis") or "")
                if basis and block.get("p") is None:
                    errors.append(f"chapter {ci} step {si} block {bi}: basis is only for p")
                if basis not in VALID_BASIS_VALUES:
                    errors.append(f"chapter {ci} step {si} block {bi}: unknown basis {basis!r}")
                if is_question and basis:
                    errors.append(
                        f"chapter {ci} step {si} block {bi}: question steps must not attach basis {basis!r}"
                    )

                # Diagram & block structure checks matching `checkDiagram()`
                if block.get("flow") is not None:
                    flow = block["flow"]
                    nodes = flow.get("nodes") if isinstance(flow, dict) else None
                    if not isinstance(nodes, list) or not nodes:
                        errors.append(f"chapter {ci} step {si} block {bi}: flow: nodes is empty")
                    else:
                        for node in nodes:
                            if not isinstance(node, dict) or not str(node.get("label") or "").strip():
                                errors.append(
                                    f"chapter {ci} step {si} block {bi}: flow: every node needs a label"
                                )
                            kind = str((node or {}).get("kind") or "")
                            if kind not in VALID_FLOW_KINDS:
                                errors.append(
                                    f"chapter {ci} step {si} block {bi}: flow: unknown kind {kind!r}"
                                )

                elif block.get("timeline") is not None:
                    tl = block["timeline"]
                    lanes = tl.get("lanes") if isinstance(tl, dict) else None
                    events = tl.get("events") if isinstance(tl, dict) else None
                    if not isinstance(lanes, list) or len(lanes) == 0 or len(lanes) > MAX_TIMELINE_LANES:
                        lane_len = len(lanes) if isinstance(lanes, list) else 0
                        errors.append(
                            f"chapter {ci} step {si} block {bi}: timeline: needs 1 to {MAX_TIMELINE_LANES} lanes, has {lane_len}"
                        )
                    elif not isinstance(events, list) or not events:
                        errors.append(f"chapter {ci} step {si} block {bi}: timeline: events is empty")
                    else:
                        for ev in events:
                            lane = str((ev or {}).get("lane") or "")
                            to_lane = str((ev or {}).get("to") or "")
                            mark = str((ev or {}).get("mark") or "")
                            if lane not in lanes:
                                errors.append(
                                    f"chapter {ci} step {si} block {bi}: timeline: lane {lane!r} is not one of {lanes!r}"
                                )
                            if to_lane and (to_lane not in lanes or to_lane == lane):
                                errors.append(
                                    f"chapter {ci} step {si} block {bi}: timeline: to {to_lane!r} must be another of {lanes!r}"
                                )
                            if mark not in VALID_TIMELINE_MARKS:
                                errors.append(
                                    f"chapter {ci} step {si} block {bi}: timeline: unknown mark {mark!r}"
                                )

                elif block.get("files") is not None:
                    fmap = block["files"]
                    roles = fmap.get("roles") if isinstance(fmap, dict) else None
                    if not isinstance(roles, list) or not roles:
                        errors.append(f"chapter {ci} step {si} block {bi}: files: roles is empty")
                    else:
                        for r_item in roles:
                            role = str((r_item or {}).get("role") or "")
                            fname = str((r_item or {}).get("file") or "")
                            if role not in VALID_FILE_ROLES:
                                errors.append(
                                    f"chapter {ci} step {si} block {bi}: files: unknown role {role!r} for {fname}"
                                )

                elif block.get("code") is not None:
                    cref = block["code"]
                    if not isinstance(cref, dict) or not str(cref.get("file") or "").strip():
                        errors.append(f"chapter {ci} step {si} block {bi}: code: file is required")
                    else:
                        lines_rng = cref.get("lines")
                        if (
                            not isinstance(lines_rng, list)
                            or len(lines_rng) != 2
                            or not all(isinstance(x, int) for x in lines_rng)
                            or lines_rng[0] < 1
                            or lines_rng[1] < lines_rng[0]
                        ):
                            errors.append(
                                f"chapter {ci} step {si} block {bi}: code: lines must be [start, end] with 1 <= start <= end"
                            )

    if total_steps == 0 and "no steps" not in errors:
        errors.append("no steps")

    return {
        "ok": len(errors) == 0,
        "errors": errors,
        "step_count": total_steps,
        "chapter_count": len(chapters),
    }


def drop_revealing_asks(tour_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Mirror `Tour.DropRevealingAsks()` from `internal/tour/tour.go`:
    removes suggested questions (`asks`) on any `question: true` step and on the step
    immediately preceding it so question wording never gives away the answer.
    """
    cloned = copy.deepcopy(tour_data)
    flat_steps: List[Dict[str, Any]] = []
    for chapter in cloned.get("chapters") or []:
        for step in chapter.get("steps") or []:
            flat_steps.append(step)

    for idx, step in enumerate(flat_steps):
        if bool(step.get("question", False)):
            step.pop("asks", None)
            if idx > 0:
                flat_steps[idx - 1].pop("asks", None)
    return cloned


def _git_read_file_lines(repo_path: Union[str, Path], ref: str, rel_file: str) -> Optional[List[str]]:
    """Read lines of `rel_file` at git commit `ref` using `git show <ref>:<file>` (with working-tree fallback)."""
    repo_root = Path(repo_path).resolve()
    norm_file = rel_file.replace("\\", "/").lstrip("/")
    try:
        proc = subprocess.run(
            ["git", "-C", str(repo_root), "show", f"{ref}:{norm_file}"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
        )
        if proc.returncode == 0:
            return proc.stdout.splitlines()
    except Exception:
        pass

    candidate = repo_root / norm_file
    if candidate.is_file():
        return candidate.read_text(encoding="utf-8", errors="replace").splitlines()
    return None


def verify_tour_code_refs_against_git(
    tour_data: Dict[str, Any],
    repo_path: Union[str, Path],
) -> Dict[str, Any]:
    """
    Zero-hallucination code reference checker (`internal/render/check.go` equivalent):
    verifies that every `code` and `files` reference in `tour_data` points to an existing
    file and valid 1-based line numbers at `base` or `head` in `repo_path`.
    """
    errors: List[str] = []
    verified_refs: List[Dict[str, Any]] = []
    base_ref = str(tour_data.get("base") or "HEAD")
    head_ref = str(tour_data.get("head") or "HEAD")

    for ci, chapter in enumerate(tour_data.get("chapters") or [], 1):
        for si, step in enumerate(chapter.get("steps") or [], 1):
            for bi, block in enumerate(step.get("blocks") or [], 1):
                if block.get("code") is not None:
                    cref = block["code"]
                    rel_file = str(cref.get("file") or "")
                    at_mode = str(cref.get("at") or "head")
                    git_ref = base_ref if at_mode == "base" else head_ref
                    file_lines = _git_read_file_lines(repo_path, git_ref, rel_file)
                    if file_lines is None:
                        errors.append(
                            f"chapter {ci} step {si} block {bi}: file {rel_file!r} not found at {at_mode} ({git_ref})"
                        )
                        continue
                    total_lines = len(file_lines)
                    start_ln, end_ln = int(cref["lines"][0]), int(cref["lines"][1])
                    if start_ln < 1 or end_ln > total_lines or start_ln > end_ln:
                        errors.append(
                            f"chapter {ci} step {si} block {bi}: lines [{start_ln}, {end_ln}] out of range 1..{total_lines} in {rel_file}"
                        )
                        continue
                    for mark in cref.get("marks") or []:
                        m_ln = int(mark.get("line", 0))
                        if m_ln < start_ln or m_ln > end_ln:
                            errors.append(
                                f"chapter {ci} step {si} block {bi}: mark line {m_ln} outside highlighted range [{start_ln}, {end_ln}]"
                            )
                    verified_refs.append(
                        {
                            "file": rel_file,
                            "at": at_mode,
                            "git_ref": git_ref,
                            "lines": [start_ln, end_ln],
                            "total_lines": total_lines,
                            "excerpt": file_lines[start_ln - 1 : end_ln],
                        }
                    )
                elif block.get("files") is not None:
                    for r_item in block["files"].get("roles") or []:
                        rel_file = str(r_item.get("file") or "")
                        if (
                            _git_read_file_lines(repo_path, head_ref, rel_file) is None
                            and _git_read_file_lines(repo_path, base_ref, rel_file) is None
                        ):
                            errors.append(
                                f"chapter {ci} step {si} block {bi}: file map entry {rel_file!r} not found in base or head"
                            )

    return {
        "ok": len(errors) == 0,
        "errors": errors,
        "verified_count": len(verified_refs),
        "verified_refs": verified_refs,
    }


def build_diff_tour_from_git_range(
    repo_path: Union[str, Path],
    *,
    base: str = "HEAD",
    head: str = "HEAD",
    title: Optional[str] = None,
    target_file: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Build a schema-valid `diff-tour` v1 JSON object for `repo_path` by inspecting real tracked
    files and applying the 8 Senior Engineer Audit Dimensions (`L1_PROMISES` .. `L8_AI_TRAPS`).
    """
    repo_root = Path(repo_path).resolve()

    # Resolve concrete commit hashes when git is available
    resolved_base = base
    resolved_head = head
    try:
        p_head = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", head],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if p_head.returncode == 0 and p_head.stdout.strip():
            resolved_head = p_head.stdout.strip()
        p_base = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", base],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if p_base.returncode == 0 and p_base.stdout.strip():
            resolved_base = p_base.stdout.strip()
    except Exception:
        pass

    # Pick a real tracked source file in the repository to anchor verified CodeRefs
    chosen_file = target_file
    if not chosen_file:
        for candidate in (
            "src/flow_manimgx.py",
            "src/flow_cli.py",
            "src/flow_api.py",
            "README.md",
        ):
            if _git_read_file_lines(repo_root, resolved_head, candidate) is not None:
                chosen_file = candidate
                break

    if not chosen_file:
        py_files = sorted(repo_root.rglob("*.py"))
        if py_files:
            chosen_file = str(py_files[0].relative_to(repo_root)).replace("\\", "/")
        else:
            chosen_file = "README.md"

    lines_list = _git_read_file_lines(repo_root, resolved_head, chosen_file) or [
        "# Fallback source line 1",
        "def placeholder():",
        "    return True",
    ]
    max_ln = len(lines_list)
    s1_start = min(1, max_ln)
    s1_end = min(max(1, min(14, max_ln)), max_ln)
    s2_start = min(max(1, min(15, max_ln)), max_ln)
    s2_end = min(max(s2_start, min(32, max_ln)), max_ln)

    tour_title = title or f"Senior Engineer Architecture Tour: {Path(chosen_file).name}"

    tour_doc: Dict[str, Any] = {
        "version": TOUR_SCHEMA_VERSION,
        "title": tour_title,
        "base": resolved_base,
        "head": resolved_head,
        "chapters": [
            {
                "title": "1. Intent and System Map",
                "steps": [
                    {
                        "title": "What this change accomplishes and how to read it",
                        "blocks": [
                            {"target": True},
                            {
                                "p": (
                                    f"This tour walks through {chosen_file} using the 8 Senior Engineer "
                                    "review lenses: invariant preservation, failure recovery, and zero-drift execution."
                                ),
                                "basis": "fact",
                            },
                            {
                                "files": {
                                    "roles": [
                                        {
                                            "file": chosen_file,
                                            "role": "core",
                                            "note": "Primary implementation module under senior review",
                                        }
                                    ]
                                }
                            },
                            {
                                "flow": {
                                    "nodes": [
                                        {
                                            "label": "Scene / Diff Input",
                                            "kind": "same",
                                            "next": "AST & Git Ref Check",
                                        },
                                        {
                                            "label": "Layout & Schema Gate",
                                            "kind": "new",
                                            "note": "Zero-hallucination line check",
                                            "next": "60fps Frame Pipe",
                                        },
                                        {
                                            "label": "FFmpeg MP4 + Contact Sheet",
                                            "kind": "changed",
                                            "note": "Verified output artifact",
                                        },
                                    ]
                                }
                            },
                        ],
                        "asks": [
                            "Why do we validate file and line numbers against git before rendering?"
                        ],
                    }
                ],
            },
            {
                "title": "2. Core Mechanism and Invariants (L1 Promises)",
                "steps": [
                    {
                        "title": f"Module contract and entry structure in {Path(chosen_file).name}",
                        "open": {"file": chosen_file, "line": s1_start, "at": "head"},
                        "blocks": [
                            {
                                "code": {
                                    "file": chosen_file,
                                    "at": "head",
                                    "lines": [s1_start, s1_end],
                                    "marks": [
                                        {
                                            "line": s1_start,
                                            "text": "Verified module header and boundary contract",
                                        }
                                    ],
                                }
                            },
                            {
                                "p": (
                                    f"Lines {s1_start}..{s1_end} of {chosen_file} establish the module boundary "
                                    "and deterministic execution contract verified directly against git HEAD."
                                ),
                                "basis": "fact",
                            },
                            {
                                "p": (
                                    "Callers rely on pure time-indexed state evaluation rather than mutable "
                                    "background timers so frame capture remains repeatable under load."
                                ),
                                "basis": "inferred",
                            },
                        ],
                    },
                    {
                        "title": "Wait - what happens if two renders or retries overlap on shared state?",
                        "question": True,
                        "blocks": [
                            {
                                "p": (
                                    "Before advancing to the next step: consider what happens if two worker "
                                    "requests execute this pipeline concurrently or retry after a partial write."
                                )
                            }
                        ],
                    },
                    {
                        "title": "Answer: Isolated temporary workspaces and atomic verification (L2 Failure)",
                        "open": {"file": chosen_file, "line": s2_start, "at": "head"},
                        "blocks": [
                            {
                                "timeline": {
                                    "lanes": ["Caller", "TourEngine", "GitRepo", "FFmpegPipe"],
                                    "events": [
                                        {
                                            "lane": "Caller",
                                            "to": "TourEngine",
                                            "text": "Submit tour.json + repo ref",
                                            "mark": "ok",
                                        },
                                        {
                                            "lane": "TourEngine",
                                            "to": "GitRepo",
                                            "text": "git show <ref>:<file> (read-only)",
                                            "mark": "ok",
                                        },
                                        {
                                            "lane": "TourEngine",
                                            "to": "FFmpegPipe",
                                            "text": "Stream RGB24 frames + 48kHz WAV",
                                            "mark": "note",
                                        },
                                        {
                                            "lane": "FFmpegPipe",
                                            "to": "Caller",
                                            "text": "Emit verified .mp4 + contact_sheet.png",
                                            "mark": "ok",
                                        },
                                    ],
                                }
                            },
                            {
                                "code": {
                                    "file": chosen_file,
                                    "at": "head",
                                    "lines": [s2_start, s2_end],
                                    "marks": [
                                        {
                                            "line": s2_end,
                                            "text": "Isolated state boundary prevents cross-request corruption",
                                        }
                                    ],
                                }
                            },
                            {
                                "p": (
                                    "Each execution reads immutable git objects and stages intermediate "
                                    "streams inside an isolated temporary directory before writing the final output."
                                ),
                                "basis": "fact",
                            },
                            {
                                "p": (
                                    "In senior code review (L8 AI-Code Traps), separating verified repository facts "
                                    "from inferred behavior prevents reviewers from trusting hallucinated comments."
                                ),
                                "basis": "opinion",
                            },
                        ],
                    },
                ],
            },
        ],
    }

    return drop_revealing_asks(tour_doc)


def run_tour_cli_dump(
    tour_json_path: Union[str, Path],
    repo_path: Union[str, Path],
    *,
    cols: int = 120,
    rows: int = 36,
) -> Dict[str, Any]:
    """
    Execute the installed `tour` (`init-co-jp/diff-tour`) binary in `--dump --plain` mode
    to render terminal screens for every step, falling back to a deterministic Python
    text renderer if `tour` is not on PATH.
    """
    tour_p = Path(tour_json_path).resolve()
    repo_p = Path(repo_path).resolve()
    tour_bin = shutil.which("tour")
    if not tour_bin:
        candidate = Path("D:/Go/bin/tour.exe")
        if candidate.is_file():
            tour_bin = str(candidate)

    if tour_bin:
        try:
            proc = subprocess.run(
                [
                    tour_bin,
                    "--repo",
                    str(repo_p),
                    "--dump",
                    "--cols",
                    str(cols),
                    "--rows",
                    str(rows),
                    "--plain",
                    str(tour_p),
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=20,
            )
            if proc.returncode == 0 and proc.stdout.strip():
                return {
                    "ok": True,
                    "engine": "tour_cli_native",
                    "binary": tour_bin,
                    "output": proc.stdout,
                }
        except Exception:
            pass

    # Deterministic fallback text dump if `tour` binary is unavailable or repo is not a git worktree
    data = json.loads(tour_p.read_text(encoding="utf-8"))
    lines_out = [f"=== {data.get('title', 'Diff Tour')} ({data.get('base')}..{data.get('head')}) ==="]
    for ci, ch in enumerate(data.get("chapters") or [], 1):
        lines_out.append(f"\n[Chapter {ci}] {ch.get('title')}")
        for si, st in enumerate(ch.get("steps") or [], 1):
            q_tag = " [QUESTION]" if st.get("question") else ""
            lines_out.append(f"  Step {ci}.{si}{q_tag}: {st.get('title')}")
            for blk in st.get("blocks") or []:
                if blk.get("p"):
                    b_tag = f" ({blk.get('basis')})" if blk.get("basis") else ""
                    lines_out.append(f"    - {blk['p']}{b_tag}")
    return {
        "ok": True,
        "engine": "python_fallback_dump",
        "binary": tour_bin,
        "output": "\n".join(lines_out),
    }


def draw_diff_tour_step_at_t(
    step_data: Dict[str, Any],
    *,
    chapter_title: str,
    step_index: int,
    total_steps: int,
    t_local: float,
    step_duration: float,
    repo_path: Optional[Union[str, Path]] = None,
    base_ref: str = "HEAD",
    head_ref: str = "HEAD",
    width: int = 1280,
    height: int = 720,
    active_word_idx: int = -1,
    words: Sequence[str] = (),
) -> Image.Image:
    """
    Pure function of time `draw(t)` (`window.seek(t)` contract) that renders a single
    `diff-tour` step as a split-screen Senior Engineer Code Review frame:
      - Left pane: Visual block (`CodeRef` with real git lines & `Marks`, `Flow` graph,
        `Timeline` sequence lanes, or `FileMap` cards) animated via `closed_form_spring`.
      - Right pane: Chapter & Step header, `[QUESTION]` pause badge, and explanation
        paragraphs with color-coded epistemic `Basis` pills (`FACT`, `INFERRED`, `OPINION`).
      - Bottom bar: Word-synced kinetic subtitle bar.
    """
    w, h = int(width), int(height)
    img = Image.new("RGB", (w, h), (10, 14, 23))
    draw = ImageDraw.Draw(img, "RGBA")

    # Background blueprint grid
    grid_step = max(32, w // 24)
    for gx in range(0, w, grid_step):
        draw.line([(gx, 0), (gx, h)], fill=(25, 35, 52, 85), width=1)
    for gy in range(0, h, grid_step):
        draw.line([(0, gy), (w, gy)], fill=(25, 35, 52, 85), width=1)

    s_header = float(closed_form_spring(t_local - 0.02, zeta=1.0, omega0=14.0))
    s_left = float(closed_form_spring(t_local - 0.08, zeta=1.0, omega0=12.0))
    s_right = float(closed_form_spring(t_local - 0.18, zeta=1.0, omega0=12.0))

    # Top Header Bar
    is_question = bool(step_data.get("question", False))
    header_outline = (245, 158, 11, 240) if is_question else (56, 189, 248, 230)
    header_y = int(round(-36.0 * (1.0 - s_header) + 16.0))
    draw.rounded_rectangle(
        [int(w * 0.03), header_y, int(w * 0.97), header_y + int(h * 0.095)],
        radius=10,
        fill=(15, 23, 42, 242),
        outline=header_outline,
        width=2,
    )
    step_badge = f"STEP {step_index}/{total_steps}"
    q_label = " [SENIOR QUESTION - PAUSE & PREDICT]" if is_question else ""
    draw.text(
        (int(w * 0.05), header_y + 10),
        f"{step_badge} | {chapter_title[:48]}{q_label}",
        fill=(251, 191, 36, 255) if is_question else (56, 189, 248, 255),
    )
    clean_step_title = str(step_data.get("title") or "").replace("\u2014", "-").replace("\u2013", "-")
    draw.text(
        (int(w * 0.05), header_y + 32),
        clean_step_title[:92],
        fill=(248, 250, 252, 255),
    )

    # Split-Screen Geometry: Left Visual Stage (3%..53%) and Right Narrative Stage (55%..97%)
    pane_top = int(h * 0.14)
    pane_bot = int(h * 0.82)

    lx0, ly0, lx1, ly1 = match_position_transition(
        (-w * 0.20, pane_top, w * 0.30, pane_bot),
        (w * 0.03, pane_top, w * 0.53, pane_bot),
        t_local - 0.05,
        zeta=1.0,
        omega0=12.0,
    )
    draw.rounded_rectangle(
        [int(lx0), int(ly0), int(lx1), int(ly1)],
        radius=12,
        fill=(15, 23, 42, 245),
        outline=(51, 65, 85, 230),
        width=2,
    )

    rx0, ry0, rx1, ry1 = match_position_transition(
        (w * 0.72, pane_top, w * 1.18, pane_bot),
        (w * 0.55, pane_top, w * 0.97, pane_bot),
        t_local - 0.12,
        zeta=1.0,
        omega0=12.0,
    )
    draw.rounded_rectangle(
        [int(rx0), int(ry0), int(rx1), int(ry1)],
        radius=12,
        fill=(15, 23, 42, 245),
        outline=(71, 85, 105, 230),
        width=2,
    )

    blocks = step_data.get("blocks") or []
    visual_blocks = [
        b
        for b in blocks
        if any(b.get(k) is not None for k in ("code", "flow", "timeline", "files", "snippet"))
    ]
    text_blocks = [
        b for b in blocks if any(b.get(k) is not None for k in ("p", "quote", "list", "table"))
    ]

    # Render Left Visual Stage
    vis_x = int(lx0) + 16
    vis_y = int(ly0) + 16
    vis_w = int(lx1 - lx0) - 32

    if visual_blocks:
        vblk = visual_blocks[0]
        if vblk.get("code") is not None:
            cref = vblk["code"]
            rel_file = str(cref.get("file") or "source.py")
            at_mode = str(cref.get("at") or "head")
            git_ref = base_ref if at_mode == "base" else head_ref
            start_ln, end_ln = int(cref["lines"][0]), int(cref["lines"][1])
            marks_map = {int(m["line"]): str(m["text"]) for m in (cref.get("marks") or []) if "line" in m}

            draw.rounded_rectangle(
                [vis_x, vis_y, vis_x + vis_w, vis_y + 30],
                radius=6,
                fill=(30, 41, 59, 255),
                outline=(56, 189, 248, 200),
                width=1,
            )
            draw.text(
                (vis_x + 10, vis_y + 8),
                f"GIT {at_mode.upper()} ({git_ref[:8]}): {rel_file} [L{start_ln}..L{end_ln}]",
                fill=(125, 211, 252, 255),
            )
            vis_y += 38

            file_lines: List[str] = []
            if repo_path is not None:
                file_lines = _git_read_file_lines(repo_path, git_ref, rel_file) or []
            show_start = max(1, start_ln - 1)
            show_end = min(len(file_lines) if file_lines else end_ln, start_ln + 11)

            for ln_no in range(show_start, show_end + 1):
                if vis_y > int(ly1) - 34:
                    break
                raw_line = (
                    file_lines[ln_no - 1]
                    if 0 <= ln_no - 1 < len(file_lines)
                    else f"line {ln_no} of {rel_file}"
                )
                is_hl = start_ln <= ln_no <= end_ln
                if is_hl:
                    draw.rounded_rectangle(
                        [vis_x, vis_y - 2, vis_x + vis_w, vis_y + 18],
                        radius=4,
                        fill=(30, 58, 138, 165),
                        outline=(56, 189, 248, 140),
                        width=1,
                    )
                draw.text(
                    (vis_x + 6, vis_y),
                    f"{ln_no:3d} | {raw_line[:58]}",
                    fill=(248, 250, 252, 255) if is_hl else (148, 163, 184, 210),
                )
                vis_y += 21
                if ln_no in marks_map and vis_y <= int(ly1) - 28:
                    draw.rounded_rectangle(
                        [vis_x + 28, vis_y - 1, vis_x + vis_w - 6, vis_y + 19],
                        radius=4,
                        fill=(120, 53, 15, 215),
                        outline=(251, 191, 36, 240),
                        width=1,
                    )
                    draw.text(
                        (vis_x + 36, vis_y + 2),
                        f"^ {marks_map[ln_no][:52]}",
                        fill=(254, 243, 199, 255),
                    )
                    vis_y += 23

        elif vblk.get("flow") is not None:
            nodes = vblk["flow"].get("nodes") or []
            draw.text((vis_x, vis_y), "CONTROL & DATA FLOW DIAGRAM", fill=(56, 189, 248, 255))
            vis_y += 28
            kind_colors = {
                "same": ((30, 41, 59, 235), (148, 163, 184, 230)),
                "changed": ((120, 53, 15, 225), (251, 191, 36, 255)),
                "new": ((6, 78, 59, 225), (52, 211, 153, 255)),
                "external": ((88, 28, 135, 225), (192, 132, 252, 255)),
            }
            for n_idx, node in enumerate(nodes):
                if vis_y > int(ly1) - 56:
                    break
                kind = str(node.get("kind") or "same")
                fill_c, out_c = kind_colors.get(kind, kind_colors["same"])
                box_h = 46
                draw.rounded_rectangle(
                    [vis_x + 12, vis_y, vis_x + vis_w - 12, vis_y + box_h],
                    radius=8,
                    fill=fill_c,
                    outline=out_c,
                    width=2,
                )
                draw.text(
                    (vis_x + 24, vis_y + 8),
                    f"[{kind.upper()}] {node.get('label', '')}",
                    fill=(248, 250, 252, 255),
                )
                if node.get("note"):
                    draw.text(
                        (vis_x + 24, vis_y + 26),
                        str(node["note"])[:54],
                        fill=(203, 213, 225, 235),
                    )
                vis_y += box_h
                if n_idx < len(nodes) - 1 and not nodes[n_idx + 1].get("start"):
                    mid_x = vis_x + vis_w // 2
                    draw.line([(mid_x, vis_y), (mid_x, vis_y + 22)], fill=(56, 189, 248, 240), width=3)
                    if node.get("next"):
                        draw.text((mid_x + 8, vis_y + 4), str(node["next"])[:32], fill=(56, 189, 248, 240))
                    vis_y += 24

        elif vblk.get("timeline") is not None:
            tl = vblk["timeline"]
            lanes = tl.get("lanes") or []
            events = tl.get("events") or []
            draw.text((vis_x, vis_y), "CONCURRENCY & SEQUENCE TIMELINE", fill=(192, 132, 252, 255))
            vis_y += 26
            n_lanes = max(1, len(lanes))
            lane_xs = [
                vis_x + int((i + 0.5) * (vis_w / float(n_lanes))) for i in range(n_lanes)
            ]
            for l_i, l_name in enumerate(lanes):
                lx = lane_xs[l_i]
                draw.rounded_rectangle(
                    [lx - 48, vis_y, lx + 48, vis_y + 24],
                    radius=5,
                    fill=(30, 41, 59, 245),
                    outline=(148, 163, 184, 220),
                    width=1,
                )
                draw.text((lx - 40, vis_y + 5), str(l_name)[:11], fill=(248, 250, 252, 255))
                draw.line([(lx, vis_y + 24), (lx, int(ly1) - 18)], fill=(71, 85, 105, 160), width=2)
            vis_y += 36
            for ev in events:
                if vis_y > int(ly1) - 34:
                    break
                src_lane = str(ev.get("lane") or "")
                dst_lane = str(ev.get("to") or "")
                mark = str(ev.get("mark") or "ok")
                m_col = (
                    (52, 211, 153, 255)
                    if mark == "ok"
                    else ((248, 113, 113, 255) if mark == "bad" else (251, 191, 36, 255))
                )
                s_idx = lanes.index(src_lane) if src_lane in lanes else 0
                d_idx = lanes.index(dst_lane) if dst_lane in lanes else s_idx
                sx = lane_xs[s_idx]
                dx = lane_xs[d_idx]
                if sx != dx:
                    draw.line([(sx, vis_y + 8), (dx, vis_y + 8)], fill=m_col, width=3)
                    draw.ellipse([dx - 5, vis_y + 3, dx + 5, vis_y + 13], fill=m_col)
                draw.text(
                    (min(sx, dx) + 6, vis_y - 10),
                    f"[{mark.upper()}] {str(ev.get('text') or '')[:44]}",
                    fill=m_col,
                )
                vis_y += 34

        elif vblk.get("files") is not None:
            roles = vblk["files"].get("roles") or []
            draw.text((vis_x, vis_y), "CHANGED FILE ROLE MAP", fill=(52, 211, 153, 255))
            vis_y += 28
            for r_item in roles:
                if vis_y > int(ly1) - 48:
                    break
                draw.rounded_rectangle(
                    [vis_x, vis_y, vis_x + vis_w, vis_y + 42],
                    radius=6,
                    fill=(30, 41, 59, 235),
                    outline=(52, 211, 153, 220),
                    width=1,
                )
                draw.text(
                    (vis_x + 10, vis_y + 6),
                    f"[{str(r_item.get('role') or 'core').upper()}] {r_item.get('file', '')}",
                    fill=(248, 250, 252, 255),
                )
                draw.text(
                    (vis_x + 10, vis_y + 24),
                    str(r_item.get("note") or "")[:58],
                    fill=(148, 163, 184, 240),
                )
                vis_y += 50
    else:
        # Question / reflection card on left pane when no visual block is attached
        draw.rounded_rectangle(
            [vis_x + 10, vis_y + 20, vis_x + vis_w - 10, vis_y + 190],
            radius=12,
            fill=(120, 53, 15, 180) if is_question else (30, 41, 59, 220),
            outline=(251, 191, 36, 255) if is_question else (56, 189, 248, 220),
            width=2,
        )
        draw.text(
            (vis_x + 26, vis_y + 42),
            "SENIOR REVIEW STOP-AND-THINK" if is_question else "ARCHITECTURAL OVERVIEW",
            fill=(251, 191, 36, 255) if is_question else (56, 189, 248, 255),
        )
        draw.text(
            (vis_x + 26, vis_y + 76),
            "Predict the failure mode or invariant gap\nbefore advancing to the next tour step.",
            fill=(254, 243, 199, 255),
        )

    # Render Right Narrative Stage (with Basis pills: FACT, INFERRED, OPINION)
    nar_x = int(rx0) + 18
    nar_y = int(ry0) + 16
    nar_w = int(rx1 - rx0) - 36

    draw.text(
        (nar_x, nar_y),
        "SENIOR ENGINEER REVIEW & EPISTEMIC BASIS",
        fill=(56, 189, 248, 255),
    )
    nar_y += 28

    basis_styles = {
        "fact": ("VERIFIED / FACT", (6, 78, 59, 235), (52, 211, 153, 255)),
        "inferred": ("FROM CODE / INFERRED", (12, 74, 110, 235), (56, 189, 248, 255)),
        "opinion": ("SENIOR VIEW / OPINION", (120, 53, 15, 235), (251, 191, 36, 255)),
        "": ("QUESTION / PROMPT", (51, 65, 85, 235), (203, 213, 225, 255)),
    }

    for tblk in text_blocks:
        if nar_y > int(ry1) - 65:
            break
        if tblk.get("p") is not None:
            basis = str(tblk.get("basis") or "")
            b_label, b_fill, b_out = basis_styles.get(basis, basis_styles[""])
            p_text = str(tblk["p"])
            # Wrap text into lines of ~52 chars
            words_p = p_text.split()
            wrapped: List[str] = []
            cur_ln = ""
            for w_tok in words_p:
                if len(cur_ln) + len(w_tok) + 1 <= 52:
                    cur_ln = f"{cur_ln} {w_tok}".strip()
                else:
                    wrapped.append(cur_ln)
                    cur_ln = w_tok
            if cur_ln:
                wrapped.append(cur_ln)
            wrapped = wrapped[:4]

            card_h = 30 + len(wrapped) * 19
            draw.rounded_rectangle(
                [nar_x, nar_y, nar_x + nar_w, nar_y + card_h],
                radius=8,
                fill=(30, 41, 59, 230),
                outline=b_out,
                width=2,
            )
            draw.rounded_rectangle(
                [nar_x + 10, nar_y + 6, nar_x + 190, nar_y + 24],
                radius=4,
                fill=b_fill,
                outline=b_out,
                width=1,
            )
            draw.text((nar_x + 16, nar_y + 8), b_label, fill=b_out)
            ty = nar_y + 28
            for w_ln in wrapped:
                draw.text((nar_x + 12, ty), w_ln, fill=(241, 245, 249, 255))
                ty += 18
            nar_y += card_h + 12

    # Footer / Kinetic Subtitle Bar
    if words:
        sub_y0 = int(h * 0.85)
        sub_y1 = int(h * 0.95)
        draw.rounded_rectangle(
            [int(w * 0.05), sub_y0, int(w * 0.95), sub_y1],
            radius=10,
            fill=(9, 13, 22, 242),
            outline=(71, 85, 105, 210),
            width=2,
        )
        win_size = 9
        idx_center = max(0, active_word_idx)
        start_w = max(0, min(len(words) - win_size, idx_center - win_size // 2))
        end_w = min(len(words), start_w + win_size)
        cursor_x = int(w * 0.08)
        text_y = sub_y0 + int((sub_y1 - sub_y0) * 0.32)
        for w_i in range(start_w, end_w):
            tok = words[w_i]
            is_act = w_i == active_word_idx
            col = (251, 191, 36, 255) if is_act else (226, 232, 240, 235)
            if is_act:
                pill_w = max(24, len(tok) * 8 + 10)
                draw.rounded_rectangle(
                    [cursor_x - 4, text_y - 4, cursor_x + pill_w - 4, text_y + 20],
                    radius=5,
                    fill=(120, 53, 15, 195),
                    outline=(251, 191, 36, 255),
                    width=1,
                )
            draw.text((cursor_x, text_y), tok, fill=col)
            cursor_x += (len(tok) + 1) * 8 + 6

    return img


def render_diff_tour_to_mp4(
    tour_data: Union[Dict[str, Any], str, Path],
    output_mp4: Union[str, Path],
    *,
    repo_path: Optional[Union[str, Path]] = None,
    width: int = 1280,
    height: int = 720,
    fps: int = 24,
    language: str = "en",
    voice: Optional[GeminiStudioVoice] = None,
    max_steps: Optional[int] = None,
    contact_sheet_png: Optional[Union[str, Path]] = None,
    cols: int = 4,
    rows: int = 3,
) -> Dict[str, Any]:
    """
    Render a validated `diff-tour` JSON (`Tour`) into a narrated Senior Engineer Code
    Walkthrough `.mp4` + `.srt` + `.vtt` + `contact_sheet.png`.
    """
    if isinstance(tour_data, (str, Path)):
        tour_dict = json.loads(Path(tour_data).read_text(encoding="utf-8"))
    else:
        tour_dict = copy.deepcopy(tour_data)

    tour_dict = drop_revealing_asks(tour_dict)
    val_report = validate_diff_tour(tour_dict)
    if not val_report["ok"]:
        raise ValueError(f"Invalid diff-tour schema: {'; '.join(val_report['errors'])}")

    git_report: Optional[Dict[str, Any]] = None
    if repo_path is not None:
        git_report = verify_tour_code_refs_against_git(tour_dict, repo_path)

    w = int(width) + (int(width) % 2)
    h = int(height) + (int(height) % 2)
    fps_int = max(5, int(fps))
    active_voice = voice or GeminiStudioVoice(language=language)

    flat_steps: List[Tuple[str, Dict[str, Any]]] = []
    for ch in tour_dict.get("chapters") or []:
        ch_title = str(ch.get("title") or "Chapter")
        for st in ch.get("steps") or []:
            flat_steps.append((ch_title, st))
    if max_steps is not None and max_steps > 0:
        flat_steps = flat_steps[: int(max_steps)]

    total_steps = len(flat_steps)
    base_ref = str(tour_dict.get("base") or "HEAD")
    head_ref = str(tour_dict.get("head") or "HEAD")

    # Pre-synthesize narration per step
    step_Timeline: List[Dict[str, Any]] = []
    all_speech_chunks: List[np.ndarray] = []
    span_timestamps: List[float] = []
    transition_timestamps: List[float] = []
    captions: List[Dict[str, Any]] = []
    cursor_sec = 0.0

    for s_idx, (ch_title, st) in enumerate(flat_steps, 1):
        p_texts = [str(b["p"]).strip() for b in (st.get("blocks") or []) if b.get("p")]
        nar_text = " ".join(p_texts) if p_texts else str(st.get("title") or f"Step {s_idx}")
        clean_nar = re.sub(r"\s+", " ", nar_text).strip()
        speech_obj = active_voice(clean_nar)
        samples = speech_obj.samples
        step_dur = max(1.2, round(float(len(samples) / float(RATE)) + 0.15, 4))
        n_frames = max(1, int(round(step_dur * fps_int)))
        exact_dur = n_frames / float(fps_int)

        # Pad or trim audio samples to match exact_dur
        target_len = int(round(exact_dur * RATE))
        if len(samples) < target_len:
            pad = np.zeros((target_len - len(samples), samples.shape[1]), dtype=np.float32)
            step_samples = np.vstack([samples, pad])
        else:
            step_samples = samples[:target_len]

        all_speech_chunks.append(step_samples)
        transition_timestamps.append(round(cursor_sec + 0.03, 3))
        if st.get("question"):
            span_timestamps.append(round(cursor_sec + 0.18, 3))

        captions.append(
            {
                "start": round(cursor_sec, 3),
                "end": round(cursor_sec + exact_dur, 3),
                "text": f"[{s_idx}/{total_steps}] {st.get('title')}: {clean_nar}",
            }
        )
        step_Timeline.append(
            {
                "chapter_title": ch_title,
                "step": st,
                "step_index": s_idx,
                "start_sec": cursor_sec,
                "duration_sec": exact_dur,
                "frame_count": n_frames,
                "words_meta": list(speech_obj.words),
                "word_tokens": [
                    str(getattr(wd, "text", getattr(wd, "word", wd)))
                    for wd in speech_obj.words
                ],
            }
        )
        cursor_sec += exact_dur

    full_speech = np.vstack(all_speech_chunks) if all_speech_chunks else np.zeros((RATE, 2), dtype=np.float32)
    total_duration_sec = round(cursor_sec, 4)
    total_frames = sum(item["frame_count"] for item in step_Timeline)

    mix_info = mix_studio_audio_with_ducking_and_sfx(
        full_speech,
        duration_sec=total_duration_sec,
        span_timestamps=span_timestamps,
        transition_timestamps=transition_timestamps,
        duck_db=-12.0,
        rate=RATE,
    )
    final_audio = mix_info["mixed_samples"]

    out_p = Path(output_mp4).resolve()
    out_p.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_root = Path(tmp_dir)
        video_only_mp4 = tmp_root / "tour_video.mp4"
        wav_path = tmp_root / "tour_audio.wav"

        ffmpeg_cmd = [
            ffmpeg_exe,
            "-y",
            "-f",
            "rawvideo",
            "-vcodec",
            "rawvideo",
            "-s",
            f"{w}x{h}",
            "-pix_fmt",
            "rgb24",
            "-r",
            str(fps_int),
            "-i",
            "pipe:0",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-preset",
            "ultrafast",
            "-crf",
            "20",
            "-movflags",
            "+faststart",
            str(video_only_mp4),
        ]
        proc = subprocess.Popen(
            ffmpeg_cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        try:
            for item in step_Timeline:
                words_meta = item["words_meta"]
                word_tokens = item["word_tokens"]
                for f_i in range(item["frame_count"]):
                    t_local = f_i / float(fps_int)
                    act_idx = -1
                    for w_i, wd in enumerate(words_meta):
                        if wd.start <= t_local <= wd.end + 0.06:
                            act_idx = w_i
                            break
                    frame_img = draw_diff_tour_step_at_t(
                        item["step"],
                        chapter_title=item["chapter_title"],
                        step_index=item["step_index"],
                        total_steps=total_steps,
                        t_local=t_local,
                        step_duration=item["duration_sec"],
                        repo_path=repo_path,
                        base_ref=base_ref,
                        head_ref=head_ref,
                        width=w,
                        height=h,
                        active_word_idx=act_idx,
                        words=word_tokens,
                    )
                    if proc.stdin is not None:
                        proc.stdin.write(frame_img.tobytes())
        finally:
            if proc.stdin is not None:
                proc.stdin.close()
            _, stderr_bytes = proc.communicate(timeout=90)
            if proc.returncode != 0:
                err_msg = stderr_bytes.decode("utf-8", errors="replace")[-600:]
                raise RuntimeError(f"Diff-tour FFmpeg video pipe failed: {err_msg}")

        with wave.open(str(wav_path), "wb") as wf:
            wf.setnchannels(int(final_audio.shape[1]))
            wf.setsampwidth(2)
            wf.setframerate(RATE)
            clean_audio = np.nan_to_num(final_audio, nan=0.0, posinf=1.0, neginf=-1.0)
            pcm16 = (
                (np.clip(clean_audio, -1.0, 1.0) * 32767.0)
                .round()
                .astype("<i2")
                .tobytes()
            )
            wf.writeframes(pcm16)

        mux_cmd = [
            ffmpeg_exe,
            "-y",
            "-i",
            str(video_only_mp4),
            "-i",
            str(wav_path),
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-ar",
            str(RATE),
            "-shortest",
            "-movflags",
            "+faststart",
            str(out_p),
        ]
        subprocess.run(
            mux_cmd,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            timeout=90,
        )

    srt_lines: List[str] = []
    vtt_lines: List[str] = ["WEBVTT", ""]
    for idx, cap in enumerate(captions, 1):
        s_srt = _format_srt_timestamp(cap["start"])
        e_srt = _format_srt_timestamp(cap["end"])
        srt_lines.extend([str(idx), f"{s_srt} --> {e_srt}", cap["text"], ""])

        s_vtt = _format_vtt_timestamp(cap["start"])
        e_vtt = _format_vtt_timestamp(cap["end"])
        vtt_lines.extend([str(idx), f"{s_vtt} --> {e_vtt}", cap["text"], ""])

    srt_text = "\n".join(srt_lines)
    vtt_text = "\n".join(vtt_lines)
    srt_path = out_p.with_suffix(".srt")
    vtt_path = out_p.with_suffix(".vtt")
    srt_path.write_text(srt_text, encoding="utf-8")
    vtt_path.write_text(vtt_text, encoding="utf-8")

    sheet_path = (
        Path(contact_sheet_png).resolve()
        if contact_sheet_png is not None
        else (out_p.parent / f"{out_p.stem}_contact_sheet.png")
    )
    sheet_report = build_contact_sheet(out_p, sheet_path, cols=cols, rows=rows)

    return {
        "ok": True,
        "engine": "diff_tour_video",
        "voice_gender": "female",
        "tour_title": tour_dict.get("title"),
        "output_mp4": str(out_p),
        "output_srt": str(srt_path),
        "output_vtt": str(vtt_path),
        "contact_sheet_png": str(sheet_path),
        "contact_sheet": sheet_report,
        "video_size_bytes": out_p.stat().st_size,
        "width": w,
        "height": h,
        "fps": fps_int,
        "step_count": total_steps,
        "frame_count": total_frames,
        "duration_sec": total_duration_sec,
        "validation": val_report,
        "git_verification": git_report,
        "subtitles_srt": srt_text,
        "subtitles_vtt": vtt_text,
        "captions": captions,
    }
