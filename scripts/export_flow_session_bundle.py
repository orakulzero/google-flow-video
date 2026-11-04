#!/usr/bin/env python3
"""Export and import Google Flow browser session cookies (flow.google.com + .google.com).

Usage on Windows (where gflow-cli and profile_default live):
    python scripts/export_flow_session_bundle.py

Usage on Cloud Linux VM (to import from Google Drive 04_flow_session_state and verify in headless Chrome):
    python3 scripts/export_flow_session_bundle.py --import-cloud
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from typing import Any

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

PROJECT_ID = "7d9a2a67-9cd2-4a79-932e-717d2e29257f"
PROJECT_URL = f"https://flow.google.com/project/{PROJECT_ID}"
DRIVE_FLOW_STATE_FOLDER_ID = "1HL31E1_L8yDQSYS7iIh2YWRa-XuZl_Iz"
DEFAULT_PROXY = "http://127.0.0.1:7890"
COOKIES_FILENAME = "flow_session_cookies.json"


def resolve_windows_profile_dir() -> Path:
    local_appdata = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local")))
    return local_appdata / "ffroliva" / "gflow-cli" / "profile_default"


def _has_authenticated_flow_cookies(cookies: list[dict[str, Any]]) -> bool:
    has_google_sid = any(
        c.get("name") in ("SID", "__Secure-1PSID", "SAPISID") and "google.com" in str(c.get("domain", ""))
        for c in cookies
    )
    has_flow_osid = any(
        c.get("name") in ("OSID", "__Secure-OSID", "__Secure-1PSID", "SID")
        and ("flow.google.com" in str(c.get("domain", "")) or ".google.com" in str(c.get("domain", "")))
        for c in cookies
    )
    return has_google_sid and has_flow_osid


async def export_from_windows_gflow_profile(
    profile_dir: Path,
    out_json_path: Path,
    proxy_url: str = DEFAULT_PROXY,
) -> dict[str, Any]:
    """Open profile_default via FlowApiClient (patchright) or Chrome CDP and dump all Flow cookies."""
    os.environ.setdefault("GFLOW_CLI_BROWSER_ENGINE", "patchright")
    if proxy_url:
        os.environ.setdefault("GFLOW_CLI_BROWSER_PROXY", proxy_url)
        os.environ.setdefault("HTTPS_PROXY", proxy_url)
        os.environ.setdefault("HTTP_PROXY", proxy_url)

    cookies: list[dict[str, Any]] = []
    local_storage_data: dict[str, str] = {}
    final_url = ""

    from gflow_cli.api.client import FlowApiClient

    async with FlowApiClient(profile_dir) as flow_client:
        page = flow_client._page
        await page.goto(PROJECT_URL, wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(5.0)

        for wait_step in range(36):
            final_url = page.url
            if "/project/" in final_url and "/about" not in final_url and "accounts.google.com" not in final_url:
                break
            if wait_step == 0:
                print(
                    f"[Flow Export] Browser redirected to {final_url}. "
                    "Please complete Google sign-in in the opened browser window (waiting up to 180s)...",
                    flush=True,
                )
            await asyncio.sleep(5.0)

        ctx_cookies = await page.context.cookies()
        cookies.extend(ctx_cookies)

        try:
            cdp = await page.context.new_cdp_session(page)
            cdp_res = await cdp.send("Network.getAllCookies")
            cdp_list = cdp_res.get("cookies") or []
            seen = {(c.get("name"), c.get("domain"), c.get("path")) for c in cookies}
            for c in cdp_list:
                key = (c.get("name"), c.get("domain"), c.get("path"))
                if key not in seen:
                    cookies.append(c)
                    seen.add(key)
        except Exception:
            pass

        try:
            ls_raw = await page.evaluate(
                "() => { const o = {}; for (let i=0; i<localStorage.length; i++) { const k = localStorage.key(i); o[k] = localStorage.getItem(k); } return o; }"
            )
            if isinstance(ls_raw, dict):
                local_storage_data = {str(k): str(v) for k, v in ls_raw.items()}
        except Exception:
            pass

    payload = {
        "version": 1,
        "exported_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "project_url": PROJECT_URL,
        "final_url": final_url,
        "cookie_count": len(cookies),
        "cookies": cookies,
        "local_storage": local_storage_data,
    }
    out_json_path.parent.mkdir(parents=True, exist_ok=True)
    out_json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return payload


def push_session_to_drive_or_bridge(local_json: Path) -> list[str]:
    """Upload or copy flow_session_cookies.json to Google Drive 04_flow_session_state (1HL31E1_L8yDQSYS7iIh2YWRa-XuZl_Iz)."""
    delivered: list[str] = []

    # 1. Try gdrive CLI if installed
    gdrive_bin = shutil.which("gdrive")
    if gdrive_bin:
        res = subprocess.run(
            [gdrive_bin, "mutate", "upload", str(local_json), "--parent", DRIVE_FLOW_STATE_FOLDER_ID],
            capture_output=True,
            text=True,
            check=False,
        )
        if res.returncode == 0:
            delivered.append(f"gdrive:{DRIVE_FLOW_STATE_FOLDER_ID}/{local_json.name}")

    # 2. Check mounted Google Drive Desktop / local bridge directories
    candidate_dirs = [
        Path.home() / "FLOW_VIDEO_STUDIO_BRIDGE" / "04_flow_session_state",
        ROOT_DIR / "FLOW_VIDEO_STUDIO_BRIDGE" / "04_flow_session_state",
    ]
    for drive_letter in ("G", "H", "D", "C"):
        for sub in ("My Drive", "\u041c\u043e\u0439 \u0434\u0438\u0441\u043a"):
            p = Path(f"{drive_letter}:/{sub}/FLOW_VIDEO_STUDIO_BRIDGE/04_flow_session_state")
            candidate_dirs.append(p)

    for d in candidate_dirs:
        if d.is_dir():
            dst = d / COOKIES_FILENAME
            shutil.copy2(local_json, dst)
            delivered.append(str(dst))

    return delivered


def fetch_flow_cookies_from_drive(dest_json: Path) -> Path | None:
    """Download flow_session_cookies.json from Google Drive 04_flow_session_state on the Cloud VM."""
    gdrive_bin = shutil.which("gdrive") or "/opt/antigravity/bin/gdrive"
    res = subprocess.run(
        [gdrive_bin, "readonly", "ls", DRIVE_FLOW_STATE_FOLDER_ID, "--json"],
        capture_output=True,
        text=True,
        check=False,
    )
    if res.returncode == 0 and res.stdout.strip():
        try:
            items = json.loads(res.stdout)
            for item in items:
                name = str(item.get("name", ""))
                fid = str(item.get("id", ""))
                if name in (COOKIES_FILENAME, "cookies.json", "flow_cookies.json") and fid:
                    dest_json.parent.mkdir(parents=True, exist_ok=True)
                    subprocess.run(
                        [gdrive_bin, "readonly", "download", fid, "--out", str(dest_json)],
                        check=False,
                        capture_output=True,
                    )
                    if dest_json.is_file() and dest_json.stat().st_size > 100:
                        return dest_json
        except Exception:
            pass
    if dest_json.is_file() and dest_json.stat().st_size > 100:
        return dest_json
    return None


async def verify_cloud_chrome_session(cookies_json: Path) -> dict[str, Any]:
    """Verify inside the Cloud Linux VM that /usr/bin/google-chrome opens the authenticated Flow project."""
    from src.cloud_cdp_flow_client import CloudCDPFlowClient

    async with CloudCDPFlowClient(cookies_json_path=cookies_json) as client:
        page = client._page
        await page.goto(PROJECT_URL, wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(6.0)
        info = await page.evaluate(
            """() => ({
                url: location.href,
                title: document.title,
                hasPromptBox: !!document.querySelector('flow-creative-agent-prompt-box, div.ProseMirror, div[contenteditable="true"]'),
                bodySnippet: document.body ? document.body.innerText.slice(0, 300) : ''
            })"""
        )
        return {
            "authenticated": bool(
                isinstance(info, dict)
                and "/project/" in str(info.get("url", ""))
                and "/about" not in str(info.get("url", ""))
            ),
            "page_info": info,
        }


def main() -> int:
    parser = argparse.ArgumentParser(description="Export/Import Google Flow browser session for Cloud VM")
    parser.add_argument("--profile-dir", type=Path, default=resolve_windows_profile_dir())
    parser.add_argument(
        "--out",
        type=Path,
        default=ROOT_DIR / "output" / COOKIES_FILENAME,
        help="Output path for exported flow_session_cookies.json",
    )
    parser.add_argument("--proxy", type=str, default=os.environ.get("GFLOW_CLI_BROWSER_PROXY", DEFAULT_PROXY))
    parser.add_argument("--import-cloud", action="store_true", help="Import cookies from Drive and verify on Cloud VM")
    args = parser.parse_args()

    if args.import_cloud:
        bridge_target = Path("/home/antigravity/FLOW_VIDEO_STUDIO_BRIDGE/04_flow_session_state") / COOKIES_FILENAME
        fetched = fetch_flow_cookies_from_drive(bridge_target) or (args.out if args.out.is_file() else None)
        if not fetched:
            print(
                json.dumps(
                    {
                        "status": "MISSING_FLOW_COOKIES",
                        "message": f"Upload {COOKIES_FILENAME} to Google Drive folder 04_flow_session_state ({DRIVE_FLOW_STATE_FOLDER_ID})",
                        "drive_folder_url": f"https://drive.google.com/drive/folders/{DRIVE_FLOW_STATE_FOLDER_ID}",
                    },
                    indent=2,
                )
            )
            return 2
        res = asyncio.run(verify_cloud_chrome_session(fetched))
        print(json.dumps(res, indent=2, ensure_ascii=False))
        return 0 if res.get("authenticated") else 1

    payload = asyncio.run(export_from_windows_gflow_profile(args.profile_dir, args.out, proxy_url=args.proxy))
    delivered = push_session_to_drive_or_bridge(args.out)
    print(
        json.dumps(
            {
                "status": "EXPORTED",
                "output_file": str(args.out),
                "cookie_count": payload["cookie_count"],
                "final_url": payload["final_url"],
                "delivered_to": delivered,
                "drive_folder_url": f"https://drive.google.com/drive/folders/{DRIVE_FLOW_STATE_FOLDER_ID}",
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
