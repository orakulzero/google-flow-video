"""Chrome DevTools Protocol (CDP) implementation of FlowApiClient for Cloud Linux VMs.

Drives `/usr/bin/google-chrome` via WebSocket CDP (`--remote-debugging-port`),
injects exported Google Flow cookies (`flow_session_cookies.json`), intercepts
`batchexecute` RPC responses (`bOKtO` / `as29s`), and uploads reference keyframes
via `DOM.setFileInputFiles`.
"""

from __future__ import annotations

import asyncio
import base64
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
from typing import Any, Callable, Optional

import httpx
import websockets

DEFAULT_FLOW_COOKIES_PATHS = (
    Path("/home/antigravity/FLOW_VIDEO_STUDIO_BRIDGE/04_flow_session_state/flow_session_cookies.json"),
    Path("output/flow_session_cookies.json"),
    Path("/tmp/flow_session_cookies.json"),
)


def resolve_chrome_binary() -> str:
    for name in ("google-chrome", "chromium", "chromium-browser"):
        found = shutil.which(name)
        if found:
            return found
    return "/usr/bin/google-chrome"


def load_flow_cookies_payload(cookies_json_path: Optional[Path] = None) -> dict[str, Any]:
    candidates = [Path(cookies_json_path)] if cookies_json_path else list(DEFAULT_FLOW_COOKIES_PATHS)
    for p in candidates:
        if p and p.is_file() and p.stat().st_size > 50:
            data = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return {"cookies": data, "local_storage": {}}
            if isinstance(data, dict):
                return data
    return {"cookies": [], "local_storage": {}}


class _CDPResponseEvent:
    def __init__(self, cdp_page: "CDPPage", request_id: str, url: str, status: int) -> None:
        self._page = cdp_page
        self.request_id = request_id
        self.url = url
        self.status = status

    async def text(self) -> str:
        res = await self._page.send("Network.getResponseBody", {"requestId": self.request_id})
        body = res.get("body", "")
        if res.get("base64Encoded"):
            return base64.b64decode(body).decode("utf-8", errors="replace")
        return str(body)


class _CDPFileChooser:
    def __init__(self, cdp_page: "CDPPage", backend_node_id: Optional[int] = None) -> None:
        self._page = cdp_page
        self.backend_node_id = backend_node_id

    async def set_files(self, file_spec: Any) -> None:
        if isinstance(file_spec, dict):
            tmp_dir = Path(tempfile.mkdtemp(prefix="flow_upload_"))
            fname = str(file_spec.get("name", "frame.png"))
            fpath = tmp_dir / fname
            fpath.write_bytes(file_spec["buffer"])
            files = [str(fpath)]
        elif isinstance(file_spec, (str, Path)):
            files = [str(file_spec)]
        else:
            files = [str(x) for x in file_spec]

        if self.backend_node_id:
            await self._page.send(
                "DOM.setFileInputFiles",
                {"files": files, "backendNodeId": self.backend_node_id},
            )
            return

        doc = await self._page.send("DOM.getDocument", {"depth": -1, "pierce": True})
        root_id = doc["root"]["nodeId"]
        q = await self._page.send(
            "DOM.querySelectorAll",
            {"nodeId": root_id, "selector": "input[type='file']"},
        )
        node_ids = q.get("nodeIds") or []
        if not node_ids:
            raise RuntimeError("No input[type='file'] found in DOM for file upload")
        await self._page.send(
            "DOM.setFileInputFiles",
            {"files": files, "nodeId": node_ids[-1]},
        )


class _CDPFileChooserContext:
    def __init__(self, cdp_page: "CDPPage", timeout: float = 15000.0) -> None:
        self._page = cdp_page
        self._timeout = timeout / 1000.0
        self.value: Optional[_CDPFileChooser] = None
        self._fut: Optional[asyncio.Future[int]] = None

    async def __aenter__(self) -> "_CDPFileChooserContext":
        loop = asyncio.get_running_loop()
        self._fut = loop.create_future()
        self._page._file_chooser_waiters.append(self._fut)
        self.value = _CDPFileChooser(self._page)
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self._fut and not self._fut.done():
            try:
                backend_id = await asyncio.wait_for(self._fut, timeout=min(2.5, self._timeout))
                if self.value:
                    self.value.backend_node_id = backend_id
            except Exception:
                pass
        if self._fut in self._page._file_chooser_waiters:
            self._page._file_chooser_waiters.remove(self._fut)


class _CDPResponseExpectContext:
    def __init__(self, cdp_page: "CDPPage", predicate: Callable[[_CDPResponseEvent], bool], timeout: float = 45000.0) -> None:
        self._page = cdp_page
        self._predicate = predicate
        self._timeout = timeout / 1000.0
        self._fut: Optional[asyncio.Future[_CDPResponseEvent]] = None

    async def __aenter__(self) -> "_CDPResponseExpectContext":
        loop = asyncio.get_running_loop()
        self._fut = loop.create_future()
        self._page._response_waiters.append((self._predicate, self._fut))
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if exc_type is None and self._fut:
            try:
                await asyncio.wait_for(self._fut, timeout=self._timeout)
            finally:
                self._page._response_waiters = [
                    w for w in self._page._response_waiters if w[1] is not self._fut
                ]


class CDPLocator:
    def __init__(self, page: "CDPPage", selector: str, index_mode: str = "all", nth_idx: int = 0) -> None:
        self._page = page
        self._selector = selector
        self._index_mode = index_mode
        self._nth_idx = nth_idx

    @property
    def first(self) -> "CDPLocator":
        return CDPLocator(self._page, self._selector, index_mode="first", nth_idx=0)

    @property
    def last(self) -> "CDPLocator":
        return CDPLocator(self._page, self._selector, index_mode="last", nth_idx=-1)

    def nth(self, idx: int) -> "CDPLocator":
        return CDPLocator(self._page, self._selector, index_mode="nth", nth_idx=idx)

    def locator(self, sub_selector: str) -> "CDPLocator":
        return CDPLocator(self._page, f"{self._selector} {sub_selector}", index_mode="all", nth_idx=0)

    def _js_resolve_Expr(self) -> str:
        sel_json = json.dumps(self._selector)
        return f"""(() => {{
            const raw = {sel_json};
            let nodes = [];
            try {{
                nodes = Array.from(document.querySelectorAll(raw));
            }} catch (e) {{
                const clean = raw.replace(/:has\\([^)]*\\)/g, '').replace(/:text-is\\([^)]*\\)/g, '').trim() || '*';
                nodes = Array.from(document.querySelectorAll(clean));
            }}
            return nodes;
        }})()"""

    async def count(self) -> int:
        val = await self._page.evaluate(f"() => {self._js_resolve_Expr()}.length")
        return int(val or 0)

    async def is_visible(self) -> bool:
        idx_js = "0" if self._index_mode == "first" else ("nodes.length - 1" if self._index_mode == "last" else str(self._nth_idx))
        val = await self._page.evaluate(
            f"""() => {{
                const nodes = {self._js_resolve_Expr()};
                const el = nodes[{idx_js}];
                if (!el) return false;
                const r = el.getBoundingClientRect();
                return r.width > 0 && r.height > 0;
            }}"""
        )
        return bool(val)

    async def wait_for(self, state: str = "visible", timeout: float = 15000.0) -> None:
        deadline = asyncio.get_running_loop().time() + (timeout / 1000.0)
        while asyncio.get_running_loop().time() < deadline:
            if state == "visible" and await self.is_visible():
                return
            if state != "visible" and (await self.count()) > 0:
                return
            await asyncio.sleep(0.4)
        raise TimeoutError(f"Locator {self._selector} wait_for({state}) timed out")

    async def click(self, timeout: float = 8000.0, position: Optional[dict[str, int]] = None, force: bool = False) -> None:
        idx_js = "0" if self._index_mode == "first" else ("nodes.length - 1" if self._index_mode == "last" else str(self._nth_idx))
        await self._page.evaluate(
            f"""() => {{
                const nodes = {self._js_resolve_Expr()};
                const el = nodes[{idx_js}];
                if (!el) throw new Error('Element not found: ' + {json.dumps(self._selector)});
                el.scrollIntoView({{block: 'center'}});
                el.click();
            }}"""
        )

    async def hover(self, timeout: float = 5000.0) -> None:
        idx_js = "0" if self._index_mode == "first" else ("nodes.length - 1" if self._index_mode == "last" else str(self._nth_idx))
        await self._page.evaluate(
            f"""() => {{
                const nodes = {self._js_resolve_Expr()};
                const el = nodes[{idx_js}];
                if (el) el.dispatchEvent(new MouseEvent('mouseenter', {{bubbles: true}}));
            }}"""
        )

    async def inner_text(self) -> str:
        idx_js = "0" if self._index_mode == "first" else ("nodes.length - 1" if self._index_mode == "last" else str(self._nth_idx))
        val = await self._page.evaluate(
            f"""() => {{
                const nodes = {self._js_resolve_Expr()};
                const el = nodes[{idx_js}];
                return el ? (el.innerText || el.textContent || '') : '';
            }}"""
        )
        return str(val or "")

    async def press_sequentially(self, text: str, delay: float = 4.0) -> None:
        idx_js = "0" if self._index_mode == "first" else ("nodes.length - 1" if self._index_mode == "last" else str(self._nth_idx))
        await self._page.evaluate(
            f"""(txt) => {{
                const nodes = {self._js_resolve_Expr()};
                const el = nodes[{idx_js}];
                if (!el) throw new Error('Editor element not found');
                el.focus();
                if ('value' in el) {{
                    el.value = txt;
                    el.dispatchEvent(new Event('input', {{bubbles: true}}));
                }} else {{
                    el.textContent = txt;
                    el.dispatchEvent(new InputEvent('input', {{bubbles: true, data: txt, inputType: 'insertText'}}));
                }}
            }}""",
            text,
        )


class _CDPKeyboard:
    def __init__(self, page: "CDPPage") -> None:
        self._page = page

    async def press(self, key: str) -> None:
        await self._page.send("Input.dispatchKeyEvent", {"type": "keyDown", "key": key})
        await self._page.send("Input.dispatchKeyEvent", {"type": "keyUp", "key": key})


class _CDPMouse:
    def __init__(self, page: "CDPPage") -> None:
        self._page = page

    async def move(self, x: int, y: int) -> None:
        await self._page.send("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": x, "y": y})


class _CDPHTTPResp:
    def __init__(self, status: int, content: bytes) -> None:
        self.status = status
        self._content = content

    async def body(self) -> bytes:
        return self._content


class _CDPRequestClient:
    async def get(self, url: str, timeout: float = 180000.0, max_redirects: int = 5) -> _CDPHTTPResp:
        async with httpx.AsyncClient(follow_redirects=True, timeout=timeout / 1000.0) as client:
            r = await client.get(url)
            return _CDPHTTPResp(r.status_code, r.content)


class CDPPage:
    def __init__(self, ws: Any) -> None:
        self._ws = ws
        self._msg_id = 1
        self._pending: dict[int, asyncio.Future[dict[str, Any]]] = {}
        self._response_listeners: list[Callable[[_CDPResponseEvent], Any]] = []
        self._response_waiters: list[tuple[Callable[[_CDPResponseEvent], bool], asyncio.Future[_CDPResponseEvent]]] = []
        self._file_chooser_waiters: list[asyncio.Future[int]] = []
        self.url = "about:blank"
        self.keyboard = _CDPKeyboard(self)
        self.mouse = _CDPMouse(self)
        self.request = _CDPRequestClient()
        self._reader_task = asyncio.create_task(self._reader_loop())

    async def _reader_loop(self) -> None:
        try:
            async for raw in self._ws:
                msg = json.loads(raw)
                if "id" in msg:
                    fut = self._pending.pop(msg["id"], None)
                    if fut and not fut.done():
                        fut.set_result(msg.get("result") or {})
                else:
                    method = msg.get("method", "")
                    params = msg.get("params") or {}
                    if method == "Network.responseReceived":
                        resp = params.get("response") or {}
                        ev = _CDPResponseEvent(
                            self,
                            request_id=str(params.get("requestId", "")),
                            url=str(resp.get("url", "")),
                            status=int(resp.get("status", 0)),
                        )
                        for cb in list(self._response_listeners):
                            asyncio.create_task(self._invoke_listener(cb, ev))
                        for pred, wfut in list(self._response_waiters):
                            try:
                                if not wfut.done() and pred(ev):
                                    wfut.set_result(ev)
                            except Exception:
                                pass
                    elif method == "Page.fileChooserOpened":
                        bid = int(params.get("backendNodeId", 0))
                        for f_wait in list(self._file_chooser_waiters):
                            if not f_wait.done():
                                f_wait.set_result(bid)
        except Exception:
            pass

    async def _invoke_listener(self, cb: Callable[[_CDPResponseEvent], Any], ev: _CDPResponseEvent) -> None:
        try:
            res = cb(ev)
            if asyncio.iscoroutine(res):
                await res
        except Exception:
            pass

    async def send(self, method: str, params: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        cid = self._msg_id
        self._msg_id += 1
        fut = asyncio.get_running_loop().create_future()
        self._pending[cid] = fut
        await self._ws.send(json.dumps({"id": cid, "method": method, "params": params or {}}))
        return await asyncio.wait_for(fut, timeout=60.0)

    def on(self, event_name: str, callback: Callable[[Any], Any]) -> None:
        if event_name == "response":
            self._response_listeners.append(callback)

    def locator(self, selector: str) -> CDPLocator:
        return CDPLocator(self, selector)

    def expect_file_chooser(self, timeout: float = 15000.0) -> _CDPFileChooserContext:
        return _CDPFileChooserContext(self, timeout=timeout)

    def expect_response(self, predicate: Callable[[_CDPResponseEvent], bool], timeout: float = 45000.0) -> _CDPResponseExpectContext:
        return _CDPResponseExpectContext(self, predicate=predicate, timeout=timeout)

    async def goto(self, url: str, wait_until: str = "domcontentloaded", timeout: float = 60000.0) -> None:
        await self.send("Page.navigate", {"url": url})
        await asyncio.sleep(3.5)
        self.url = str(await self.evaluate("() => location.href"))

    async def evaluate(self, expression: str, arg: Any = None) -> Any:
        expr = expression.strip()
        if expr.startswith("(") or expr.startswith("async") or "=>" in expr[:40]:
            arg_json = json.dumps(arg) if arg is not None else ""
            call_expr = f"({expr})({arg_json})"
        else:
            call_expr = expr
        res = await self.send(
            "Runtime.evaluate",
            {"expression": call_expr, "awaitPromise": True, "returnByValue": True},
        )
        val = (res.get("result") or {}).get("value")
        return val


class CloudCDPFlowClient:
    """Drop-in replacement for FlowApiClient on Linux Cloud VMs using /usr/bin/google-chrome + CDP."""

    def __init__(
        self,
        profile_dir: Optional[Path] = None,
        cookies_json_path: Optional[Path] = None,
        debug_port: int = 9242,
    ) -> None:
        self.profile_dir = Path(profile_dir) if profile_dir else Path("/tmp/flow_cdp_chrome_profile")
        self.cookies_json_path = cookies_json_path
        self.debug_port = debug_port
        self._proc: Optional[subprocess.Popen[bytes]] = None
        self._ws: Any = None
        self._page: Optional[CDPPage] = None

    async def __aenter__(self) -> "CloudCDPFlowClient":
        self.profile_dir.mkdir(parents=True, exist_ok=True)
        chrome_bin = resolve_chrome_binary()
        self._proc = subprocess.Popen(
            [
                chrome_bin,
                "--headless=new",
                "--no-sandbox",
                "--disable-gpu",
                "--ignore-certificate-errors",
                "--window-size=1440,960",
                f"--user-data-dir={self.profile_dir}",
                f"--remote-debugging-port={self.debug_port}",
                "about:blank",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        ws_url = ""
        for _ in range(25):
            await asyncio.sleep(0.3)
            try:
                targets = httpx.get(f"http://127.0.0.1:{self.debug_port}/json/list", trust_env=False, timeout=2.0).json()
                for t in targets:
                    if t.get("type") == "page" and t.get("webSocketDebuggerUrl"):
                        ws_url = t["webSocketDebuggerUrl"]
                        break
                if ws_url:
                    break
            except Exception:
                pass
        if not ws_url:
            raise RuntimeError("Failed to connect to headless Chrome CDP endpoint")

        self._ws = await websockets.connect(ws_url, max_size=25_000_000)
        self._page = CDPPage(self._ws)
        await self._page.send("Network.enable")
        await self._page.send("Page.enable")
        await self._page.send("DOM.enable")
        await self._page.send("Page.setInterceptFileChooserDialog", {"enabled": True})

        payload = load_flow_cookies_payload(self.cookies_json_path)
        cookies = payload.get("cookies") or []
        if cookies:
            cdp_cookies = []
            for c in cookies:
                if not c.get("name") or c.get("value") is None:
                    continue
                entry: dict[str, Any] = {
                    "name": str(c["name"]),
                    "value": str(c["value"]),
                    "domain": str(c.get("domain") or ".google.com"),
                    "path": str(c.get("path") or "/"),
                    "secure": bool(c.get("secure", True)),
                    "httpOnly": bool(c.get("httpOnly", False)),
                }
                if c.get("sameSite") in ("Strict", "Lax", "None"):
                    entry["sameSite"] = c["sameSite"]
                if isinstance(c.get("expires"), (int, float)) and c["expires"] > 0:
                    entry["expires"] = float(c["expires"])
                cdp_cookies.append(entry)
            if cdp_cookies:
                await self._page.send("Network.setCookies", {"cookies": cdp_cookies})

        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self._ws:
            try:
                await self._ws.close()
            except Exception:
                pass
        if self._proc:
            try:
                self._proc.terminate()
            except Exception:
                pass
