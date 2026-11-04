#!/usr/bin/env python3
"""
scripts/sync_with_gemini_local_ui.py
Synchronizes the standalone Google Flow & Veo 3.1 Studio modules in
`e:\\ANTIGRAVITY\\flow_video_testbench` with `gemini_local_ui`:
- `src/flow_bridge.py` <-> `backend/app/bridge/flow.py`
- `src/flow_api.py`    <-> `backend/app/api/flow.py`
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, Optional

TESTBENCH_DIR = Path(__file__).resolve().parent.parent


def _find_gemini_local_ui_root() -> Optional[Path]:
    candidates = [
        Path.home() / "teamwork_projects" / "gemini_local_ui",
        TESTBENCH_DIR.parent / "gemini_local_ui",
    ]
    return next((p for p in candidates if (p / "backend" / "app" / "main.py").is_file()), None)


def sync_files(direction: str = "push") -> Dict[str, str]:
    repo_root = _find_gemini_local_ui_root()
    if not repo_root:
        raise FileNotFoundError("Could not locate gemini_local_ui repository.")

    local_bridge = TESTBENCH_DIR / "src" / "flow_bridge.py"
    remote_bridge = repo_root / "backend" / "app" / "bridge" / "flow.py"

    local_adapt = TESTBENCH_DIR / "src" / "flow_repo_adaptations.py"
    remote_adapt = repo_root / "backend" / "app" / "bridge" / "flow_repo_adaptations.py"

    local_api = TESTBENCH_DIR / "src" / "flow_api.py"
    remote_api = repo_root / "backend" / "app" / "api" / "flow.py"

    if direction == "push":
        if local_adapt.is_file():
            remote_adapt.write_text(local_adapt.read_text(encoding="utf-8"), encoding="utf-8")

        bridge_text = (
            local_bridge.read_text(encoding="utf-8")
            .replace(
                "src/flow_bridge.py (synchronized with gemini_local_ui/backend/app/bridge/flow.py)",
                "backend/app/bridge/flow.py",
            )
            .replace(
                "from src.flow_repo_adaptations import (",
                "from backend.app.bridge.flow_repo_adaptations import (",
            )
        )
        remote_bridge.write_text(bridge_text, encoding="utf-8")

        api_text = (
            local_api.read_text(encoding="utf-8")
            .replace(
                "src/flow_api.py (synchronized with gemini_local_ui/backend/app/api/flow.py)",
                "backend/app/api/flow.py",
            )
            .replace("from src.flow_bridge import (", "from backend.app.bridge.flow import (")
        )
        remote_api.write_text(api_text, encoding="utf-8")
        return {
            "direction": "push (flow_video_testbench -> gemini_local_ui)",
            "bridge": str(remote_bridge),
            "api": str(remote_api),
        }
    else:
        bridge_text = remote_bridge.read_text(encoding="utf-8")
        local_bridge.write_text(bridge_text, encoding="utf-8")

        api_text = remote_api.read_text(encoding="utf-8").replace(
            "from backend.app.bridge.flow import (", "from src.flow_bridge import ("
        )
        local_api.write_text(api_text, encoding="utf-8")
        return {
            "direction": "pull (gemini_local_ui -> flow_video_testbench)",
            "bridge": str(local_bridge),
            "api": str(local_api),
        }


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync Flow Video Studio with gemini_local_ui.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--push", action="store_true", help="Push changes from testbench to gemini_local_ui")
    group.add_argument("--pull", action="store_true", help="Pull latest files from gemini_local_ui to testbench")
    args = parser.parse_args()

    res = sync_files("push" if args.push else "pull")
    print(json.dumps(res, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
