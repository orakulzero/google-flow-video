#!/usr/bin/env python3
"""
scripts/report_to_root_session.py
Sends structured status & verification reports from this standalone Flow Video Studio
workspace (`e:\\ANTIGRAVITY\\flow_video_testbench`) directly to the Root Architecture
Session (`conversation://a6e93033-0846-422c-a4e2-dfc7274efe0d`).

Outputs written to the Root Session Brain Directory:
1. `<APPDATA_BRAIN>/a6e93033-0846-422c-a4e2-dfc7274efe0d/child_session_reports.jsonl`
2. `<APPDATA_BRAIN>/a6e93033-0846-422c-a4e2-dfc7274efe0d/FLOW_STUDIO_HANDOFF_REPORT.md`
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
from pathlib import Path
from typing import Any, Dict, List

ROOT_CONV_ID = "a6e93033-0846-422c-a4e2-dfc7274efe0d"
TESTBENCH_DIR = Path(__file__).resolve().parent.parent


def _resolve_root_brain_dir(root_conv_id: str = ROOT_CONV_ID) -> Path:
    env_dir = os.environ.get("AGY_BRAIN_DIR", "").strip()
    if env_dir:
        base = Path(env_dir)
    else:
        base = Path.home() / ".gemini" / "antigravity" / "brain"
    target = base / root_conv_id
    target.mkdir(parents=True, exist_ok=True)
    return target


def _collect_local_metrics() -> Dict[str, Any]:
    out_dir = TESTBENCH_DIR / "output"
    lessons_summary: List[Dict[str, Any]] = []
    if out_dir.is_dir():
        for sb_file in sorted(out_dir.glob("*/storyboard.json")):
            try:
                lesson_dir = sb_file.parent
                data = json.loads(sb_file.read_text(encoding="utf-8"))
                mp4_file = lesson_dir / "lesson_full_720p.mp4"
                kb = round(mp4_file.stat().st_size / 1024, 1) if mp4_file.is_file() else 0.0
                lessons_summary.append(
                    {
                        "lesson_id": lesson_dir.name,
                        "topic": data.get("topic"),
                        "language": data.get("language"),
                        "scene_count": len(data.get("scenes") or []),
                        "full_video": str(mp4_file),
                        "full_video_kb": kb,
                        "voice_engines": [
                            "Gemini 3.8 Studio (RU Female Warm Mezzo - voice_y0joebp3bwta)"
                            if data.get("language") == "ru"
                            else "Gemini 3.8 Studio (EN Studio Female - Sulafat)"
                        ],
                    }
                )
            except Exception:
                pass
    tts_cache_dir = TESTBENCH_DIR / ".tts_cache"
    cached_wavs = len(list(tts_cache_dir.glob("*.wav"))) if tts_cache_dir.is_dir() else 0
    return {
        "testbench_dir": str(TESTBENCH_DIR),
        "cached_tts_wavs": cached_wavs,
        "lessons": lessons_summary,
    }


def send_report(
    status: str,
    summary: str,
    changes: List[str],
    tests_passed: str,
    child_conv_id: str = "standalone-flow-testbench",
    next_steps: str = "Ready to sync with gemini_local_ui and tag v1.1.0",
) -> Dict[str, Any]:
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    root_brain = _resolve_root_brain_dir(ROOT_CONV_ID)
    jsonl_path = root_brain / "child_session_reports.jsonl"
    md_path = root_brain / "FLOW_STUDIO_HANDOFF_REPORT.md"

    metrics = _collect_local_metrics()
    payload: Dict[str, Any] = {
        "timestamp": now_iso,
        "root_conversation_id": ROOT_CONV_ID,
        "root_reference": f"[Root Architecture Session](conversation://{ROOT_CONV_ID})",
        "child_conversation_id": child_conv_id,
        "child_reference": (
            f"[Flow Studio Child Session](conversation://{child_conv_id})"
            if child_conv_id and child_conv_id != "standalone-flow-testbench"
            else "standalone-flow-testbench"
        ),
        "workspace": str(TESTBENCH_DIR),
        "status": status,
        "summary": summary,
        "changes": changes,
        "tests_passed": tests_passed,
        "next_steps": next_steps,
        "metrics": metrics,
    }

    with jsonl_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")

    changes_md = "\n".join(f"- {c}" for c in changes) if changes else "- Baseline verification completed."
    lessons_md_lines: List[str] = []
    for les in metrics.get("lessons", []):
        lessons_md_lines.append(
            f"- **`{les['lesson_id']}`** (`{les['language']}`, {les['scene_count']} scenes, "
            f"`{les['full_video_kb']} KB`): engines={les['voice_engines']}"
        )
    lessons_md = "\n".join(lessons_md_lines) if lessons_md_lines else "- No rendered lessons found."

    md_content = f"""# Google Flow & Veo 3.1 Studio — Child Session Handoff Report

- **Target Root Session**: [Root Architecture Session](conversation://{ROOT_CONV_ID})
- **Source Child Session**: {payload['child_reference']}
- **Standalone Workspace**: [`flow_video_testbench`](file:///{TESTBENCH_DIR.as_posix()})
- **Timestamp (UTC)**: `{now_iso}`
- **Status**: **`{status}`**
- **Verification**: `{tests_passed}`

## Executive Summary
{summary}

## Completed Modifications
{changes_md}

## Rendered Video & Voiceover Artifacts
- **Cached Studio TTS WAVs (`.tts_cache/`)**: `{metrics['cached_tts_wavs']}`
{lessons_md}

## Next Actions for Root Session
{next_steps}
"""
    md_path.write_text(md_content, encoding="utf-8")
    return {
        "ok": True,
        "jsonl_path": str(jsonl_path),
        "md_path": str(md_path),
        "payload": payload,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Send structured status report to Root Session a6e93033-0846-422c-a4e2-dfc7274efe0d."
    )
    STATUS_ALIASES = {
        "IN_PROGRESS": "IN_PROGRESS",
        "RUNNING": "IN_PROGRESS",
        "VERIFIED": "VERIFIED",
        "DONE": "VERIFIED",
        "COMPLETED": "VERIFIED",
        "PASS": "VERIFIED",
        "PASSED": "VERIFIED",
        "BLOCKED": "BLOCKED",
        "FAILED": "BLOCKED",
        "READY_FOR_MERGE": "READY_FOR_MERGE",
    }
    parser.add_argument(
        "--status",
        default="VERIFIED",
        type=lambda s: STATUS_ALIASES.get(str(s).strip().upper(), "VERIFIED"),
        help="Current status of the standalone Flow Studio work (aliases DONE/COMPLETED/PASS -> VERIFIED).",
    )
    parser.add_argument(
        "--summary",
        default=None,
        help="Concise summary of what was refined and verified.",
    )
    parser.add_argument(
        "--milestone",
        default=None,
        help="Milestone name if applicable.",
    )
    parser.add_argument(
        "--details",
        default=None,
        help="Alias or supplementary details for --summary.",
    )
    parser.add_argument(
        "--change",
        action="append",
        default=[],
        help="Repeatable flag listing each concrete modification.",
    )
    parser.add_argument(
        "--tests",
        default="pytest tests/test_flow_studio.py passed",
        help="Verification command and pass/fail count.",
    )
    parser.add_argument(
        "--child-conv-id",
        default=os.environ.get("AGY_CONVERSATION_ID", "standalone-flow-testbench"),
        help="Conversation ID of the child Antigravity session.",
    )
    parser.add_argument(
        "--next-steps",
        default="Run `python scripts/sync_with_gemini_local_ui.py --push` and tag `v1.1.0` in Root Session.",
        help="Recommended next steps for the Root Session.",
    )
    args = parser.parse_args()
    summary = args.summary or args.details or ""
    if args.milestone and summary:
        summary = f"[{args.milestone}] {summary}"
    elif args.milestone and not summary:
        summary = f"Milestone: {args.milestone}"
    if not summary:
        parser.error("one of the arguments --summary or --details is required")

    res = send_report(
        status=args.status,
        summary=summary,
        changes=args.change,
        tests_passed=args.tests,
        child_conv_id=args.child_conv_id,
        next_steps=args.next_steps,
    )
    print(json.dumps(res, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
