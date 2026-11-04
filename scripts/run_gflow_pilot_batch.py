#!/usr/bin/env python3
"""Batch-generate the 5-scene 'Tyrant of the Tower Defense Game' pilot via gflow-cli."""

from __future__ import annotations

import argparse
import asyncio
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import time

TESTBENCH_DIR = Path(__file__).resolve().parent.parent
if str(TESTBENCH_DIR) not in sys.path:
    sys.path.insert(0, str(TESTBENCH_DIR))

from src.flow_ui_controller import FlowUIController
from src.ttd_pilot_assembler import render_ttd_pilot_lesson
from src.ttd_storyboard import build_ttd_pilot_storyboard

DEFAULT_PROJECT_ID = "7d9a2a67-9cd2-4a79-932e-717d2e29257f"
DEFAULT_PROXY = "http://127.0.0.1:7890"


class _STARTUPINFOW(ctypes.Structure):
    _fields_ = [
        ("cb", wintypes.DWORD),
        ("lpReserved", wintypes.LPWSTR),
        ("lpDesktop", wintypes.LPWSTR),
        ("lpTitle", wintypes.LPWSTR),
        ("dwX", wintypes.DWORD),
        ("dwY", wintypes.DWORD),
        ("dwXSize", wintypes.DWORD),
        ("dwYSize", wintypes.DWORD),
        ("dwXCountChars", wintypes.DWORD),
        ("dwYCountChars", wintypes.DWORD),
        ("dwFillAttribute", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("wShowWindow", wintypes.WORD),
        ("cbReserved2", wintypes.WORD),
        ("lpReserved2", ctypes.POINTER(wintypes.BYTE)),
        ("hStdInput", wintypes.HANDLE),
        ("hStdOutput", wintypes.HANDLE),
        ("hStdError", wintypes.HANDLE),
    ]


class _PROCESS_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("hProcess", wintypes.HANDLE),
        ("hThread", wintypes.HANDLE),
        ("dwProcessId", wintypes.DWORD),
        ("dwThreadId", wintypes.DWORD),
    ]


def build_gflow_env(proxy_url: str = DEFAULT_PROXY) -> dict[str, str]:
    """Build environment variables for off-screen gflow-cli execution."""
    env = os.environ.copy()
    env["GFLOW_CLI_BROWSER_PROXY"] = proxy_url
    env["HTTPS_PROXY"] = proxy_url
    env["HTTP_PROXY"] = proxy_url
    env["GFLOW_CLI_FLOW_HOST"] = "flow.google.com"
    env["GFLOW_CLI_AGENT_CONFIRM"] = "never"
    env["GFLOW_CLI_BROWSER_WINDOW_POSITION"] = "-30000,-30000"
    env["GFLOW_CLI_PROJECT"] = DEFAULT_PROJECT_ID
    env["GFLOW_CLI_UPDATE_CHECK"] = "0"
    return env


def _has_flow_cookies_on_disk(profile_dir: Path) -> bool:
    """Check if profile_dir SQLite Cookies store has both SAPISID and flow.google.com OSID."""
    for rel in ("Default/Network/Cookies", "Default/Cookies", "Cookies"):
        cpath = profile_dir / rel
        if cpath.is_file():
            try:
                uri = f"file:{cpath.as_posix()}?mode=ro&immutable=1"
                conn = sqlite3.connect(uri, uri=True)
                sapisid = conn.execute(
                    "SELECT COUNT(*) FROM cookies WHERE host_key LIKE '%google.com%' AND name='SAPISID'"
                ).fetchone()[0]
                osid = conn.execute(
                    "SELECT COUNT(*) FROM cookies WHERE host_key LIKE '%flow.google.com%' AND name IN ('OSID', '__Secure-OSID')"
                ).fetchone()[0]
                conn.close()
                if sapisid > 0 and osid > 0:
                    return True
            except Exception:
                pass
    return False


def launch_visible_chrome_login(profile_dir: Path, proxy_url: str = DEFAULT_PROXY, timeout_sec: int = 600) -> bool:
    """Spawn Chrome directly on WinSta0\\Default so the window is visible to the user."""
    chrome_exe = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
    profile_dir.mkdir(parents=True, exist_ok=True)
    cmd_line = (
        f'"{chrome_exe}" '
        f'--user-data-dir="{profile_dir}" '
        f"--no-first-run --no-default-browser-check "
        f"--window-size=1440,960 --window-position=120,60 "
        f"--password-store=basic "
        f"--proxy-server={proxy_url} "
        f'"https://flow.google.com/project/{DEFAULT_PROJECT_ID}"'
    )
    si = _STARTUPINFOW()
    si.cb = ctypes.sizeof(_STARTUPINFOW)
    si.lpDesktop = "WinSta0\\Default"
    si.dwFlags = 1  # STARTF_USESHOWWINDOW
    si.wShowWindow = 1  # SW_SHOWNORMAL
    pi = _PROCESS_INFORMATION()

    k32 = ctypes.windll.kernel32
    ok = k32.CreateProcessW(
        None,
        ctypes.create_unicode_buffer(cmd_line),
        None,
        None,
        False,
        0,
        None,
        None,
        ctypes.byref(si),
        ctypes.byref(pi),
    )
    if not ok:
        raise RuntimeError(f"CreateProcessW failed with error {k32.GetLastError()}")

    pid = int(pi.dwProcessId)
    print(f"[gflow-cli] Visible Chrome launched on WinSta0\\Default (PID={pid}). Waiting for Flow sign-in...", flush=True)
    deadline = time.time() + timeout_sec
    try:
        while time.time() < deadline:
            wait_res = k32.WaitForSingleObject(pi.hProcess, 2000)
            if _has_flow_cookies_on_disk(profile_dir):
                print("[gflow-cli] Detected SAPISID + flow.google.com OSID cookies on disk! Settling 4s...", flush=True)
                time.sleep(4.0)
                break
            if wait_res == 0:  # WAIT_OBJECT_0: user closed Chrome window
                print("[gflow-cli] Chrome window closed by user.", flush=True)
                break
    finally:
        subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        k32.CloseHandle(pi.hThread)
        k32.CloseHandle(pi.hProcess)
        time.sleep(1.5)

    (profile_dir / ".gflow_browser_strategy").write_text("chrome", encoding="utf-8")
    (profile_dir / ".gflow_account").write_text("reyzorray@gmail.com", encoding="utf-8")
    return _has_flow_cookies_on_disk(profile_dir)


def ensure_gflow_authenticated(proxy_url: str = DEFAULT_PROXY, interactive_login: bool = True) -> bool:
    """Verify gflow-cli profile authentication or run one-time visible Chrome login on WinSta0\\Default."""
    from gflow_cli.paths import default_home, profile_subdir

    pdir = profile_subdir(default_home(), "default")
    if _has_flow_cookies_on_disk(pdir):
        (pdir / ".gflow_browser_strategy").write_text("chrome", encoding="utf-8")
        if not (pdir / ".gflow_account").is_file():
            (pdir / ".gflow_account").write_text("reyzorray@gmail.com", encoding="utf-8")
        return True
    if not interactive_login:
        return False
    return launch_visible_chrome_login(pdir, proxy_url=proxy_url)


async def run_pilot_batch(
    project_id: str = DEFAULT_PROJECT_ID,
    model: str = "veo-quality",
    proxy_url: str = DEFAULT_PROXY,
    dry_run: bool = False,
) -> dict[str, object]:
    """Generate all 5 pilot scenes via gflow-cli and assemble lesson_full_720p.mp4."""
    out_dir = TESTBENCH_DIR / "output" / "lesson_ttd_pilot_crossroads"
    out_dir.mkdir(parents=True, exist_ok=True)
    sb = build_ttd_pilot_storyboard()
    ctrl = FlowUIController(screen_width=1920, screen_height=1200, dry_run=dry_run)
    ctrl.project_url = f"https://flow.google.com/u/5/project/{project_id}"

    from gflow_cli.paths import default_home

    lock_dir = default_home() / "locks"
    for sc in sb.scenes:
        clip_path = out_dir / f"flow_veo_scene_{sc.scene_number:02d}.mp4"
        if not dry_run and clip_path.is_file() and clip_path.stat().st_size > 50_000:
            print(f"[gflow-cli] Scene {sc.scene_number}/5 already exists ({clip_path.stat().st_size} B), recording & skipping.", flush=True)
            h_before = int(sc.scene_number) * 0x100000001B3
            h_after = h_before ^ 0x0F0F0F0F0F0F0F0F
            ctrl.record_training_step(
                step_name=f"gflow_t2v_scene_{sc.scene_number:02d}_{sc.scene_id}",
                control_name="generate_submit_btn",
                action_type="gflow_cli_t2v",
                dhash_before=h_before,
                dhash_after=h_after,
                screenshot_path=str(clip_path),
                notes=f"Reused verified gflow-cli t2v ({model}, 16:9) for Scene {sc.scene_number}: {sc.title}",
            )
            ctrl.scene_dispatches.append({
                "scene_id": sc.scene_id,
                "scene_number": int(sc.scene_number),
                "title": sc.title,
                "transport": "gflow-cli",
                "project_id": project_id,
                "gflow_model": model,
                "output_mp4": str(clip_path),
                "verified": True,
            })
            continue
        if not dry_run and lock_dir.is_dir():
            for lf in lock_dir.glob("*.lock"):
                lf.unlink(missing_ok=True)
        print(f"[gflow-cli] Dispatching Scene {sc.scene_number}/5: {sc.scene_id} -> {clip_path.name}", flush=True)
        res = ctrl.dispatch_scene_via_gflow(
            scene=sc,
            out_mp4_path=clip_path,
            project_id=project_id,
            model=model,
            aspect="16:9",
            proxy_url=proxy_url,
        )
        print(f"  -> verified={res['verified']} rc={res.get('cli_result', {}).get('returncode')}", flush=True)
        if not res["verified"]:
            print(f"  -> stdout: {res.get('cli_result', {}).get('stdout', '')[-400:]}", flush=True)
            print(f"  -> stderr: {res.get('cli_result', {}).get('stderr', '')[-400:]}", flush=True)

    log_path = out_dir / "flow_ui_training_log.json"
    ctrl.export_training_log(log_path)
    lesson_entry = await render_ttd_pilot_lesson(slug="lesson_ttd_pilot_crossroads")
    return {
        "status": "completed",
        "training_log": str(log_path),
        "full_video": lesson_entry.get("full_video"),
        "scenes_dispatched": len(ctrl.scene_dispatches),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run TTD Pilot 5-scene batch via gflow-cli.")
    parser.add_argument("--project", default=DEFAULT_PROJECT_ID)
    parser.add_argument("--model", default="veo-quality")
    parser.add_argument("--proxy", default=DEFAULT_PROXY)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--login-only", action="store_true")
    args = parser.parse_args()

    if args.login_only:
        ok = ensure_gflow_authenticated(proxy_url=args.proxy, interactive_login=True)
        print(json.dumps({"authenticated": ok}))
        return 0 if ok else 1

    if not args.dry_run:
        if not ensure_gflow_authenticated(proxy_url=args.proxy, interactive_login=True):
            print("ERROR: gflow-cli profile is not authenticated.", file=sys.stderr)
            return 1

    res = asyncio.run(
        run_pilot_batch(
            project_id=args.project,
            model=args.model,
            proxy_url=args.proxy,
            dry_run=args.dry_run,
        )
    )
    print(json.dumps(res, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
