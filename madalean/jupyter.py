"""On-demand JupyterLab child (python3 + sagemath kernels) behind Madalean's own authentication (ARCHITECTURE §8).

The child listens on 127.0.0.1:<random port> with base URL /jupyter/ and a random token that never leaves the
server: the reverse proxy (`proxy`) injects it on every HTTP request and WebSocket upgrade, rewrites Host/Origin to
the child's address, and strips the client's Cookie / Authorization headers (they carry Madalean's token).

Lean 4 kernel: not installed. The only candidates (`lean4_jupyter` 0.0.x on PyPI, a wrapper around the Lean REPL
that must be built per toolchain; `xeus-lean` prototypes) are experimental, unmaintained, and tied to one Lean
version, so they cannot be installed reliably here; Lean stays in Madalean's own editor/checker."""
from __future__ import annotations

import asyncio
import json
import os
import re
import secrets
import signal
import socket
import time
from pathlib import Path, PurePosixPath
from typing import Callable

import aiohttp
from aiohttp import web

from . import deps
from .logs import get
from .runtime import SETPRIV, guarded

log = get("jupyter")

LEAN_KERNEL_NOTE = ("No Lean 4 Jupyter kernel is installed: the existing ones (lean4_jupyter 0.0.x on PyPI, which "
                    "drives a Lean REPL that must be built for each toolchain; xeus-lean prototypes) are experimental "
                    "and tied to one Lean version, so they cannot be installed reliably. Use Madalean's Lean editor "
                    "and checker; notebooks offer python3 and sagemath.")
HOP = {"connection", "keep-alive", "proxy-authenticate", "proxy-authorization", "te", "trailers",
       "transfer-encoding", "upgrade", "host", "content-length", "cookie", "authorization", "origin", "referer"}
RESP_DROP = {"connection", "keep-alive", "transfer-encoding", "content-length", "content-encoding", "set-cookie",
             "server"}


def safe_path(path: str, allow_empty: bool = True) -> str:
    """Relative notebook path, POSIX, without '..' — else ValueError."""
    if not isinstance(path, str) or "\x00" in path or "\\" in path:
        raise ValueError("bad path")
    p = path.strip()
    if not p:
        if allow_empty:
            return ""
        raise ValueError("empty path")
    if p.startswith("/") or p.startswith("~"):
        raise ValueError("absolute path")
    parts = PurePosixPath(p).parts
    if any(x in ("..", ".") for x in parts) or any(x.startswith(".") for x in parts):
        raise ValueError("bad path")
    return "/".join(parts)


# Environment variables that may carry credentials: never inherited by jupyter-lab nor its kernels (they run user
# and model-generated code). API keys of Madalean itself live in the keyring / keys.json, never in the environment.
SECRET_ENV_RE = re.compile(r"(KEY|TOKEN|SECRET|PASSW|PASSPHRASE|CREDENTIAL|COOKIE|AUTH|SESSION|PRIVATE)", re.I)


def scrub_env(env: dict[str, str]) -> dict[str, str]:
    return {k: v for k, v in env.items() if not SECRET_ENV_RE.search(k) and not k.startswith("JUPYTER_")
            and not k.startswith("MADALEAN_")}


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _text(src) -> str:
    return "".join(src) if isinstance(src, list) else str(src or "")


class JupyterManager:
    def __init__(self, root_dir: Path, runtime_dir: Path, publish: Callable[[str, dict], None],
                 base_url: str = "/jupyter/", exe: str | None = None):
        self.root_dir = Path(root_dir)
        self.runtime_dir = Path(runtime_dir)
        self.share_dir = self.runtime_dir / "share"     # JUPYTER_PATH: Madalean's own kernelspecs (sagebridge)
        self.publish = publish
        self.base_url = "/" + base_url.strip("/") + "/"
        self.exe = exe or deps.tool("jupyter-lab")
        self.state = "stopped"
        self.port: int | None = None
        self.error = ""
        self.kernels: list[str] = []
        self.proc: asyncio.subprocess.Process | None = None
        self._token = ""
        self._session: aiohttp.ClientSession | None = None
        self._lock = asyncio.Lock()
        self._log_task: asyncio.Task | None = None
        self._tail: list[str] = []

    # ------------------------------------------------------------ status
    def status(self) -> dict:
        return {"state": self.state, "port": self.port, "root_dir": str(self.root_dir), "kernels": list(self.kernels),
                "error": self.error, "available": bool(self.exe),
                "lean_kernel": {"available": "lean4" in self.kernels or "lean" in self.kernels,
                                "note": LEAN_KERNEL_NOTE}}

    def _changed(self) -> None:
        try:
            self.publish("jupyter.status", {"jupyter": self.status()})
        except Exception:  # noqa: BLE001
            log.exception("publish failed")

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def _headers(self) -> dict:
        return {"Authorization": f"token {self._token}"}

    def _http(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(auto_decompress=False, cookie_jar=aiohttp.DummyCookieJar(),
                                                  timeout=aiohttp.ClientTimeout(total=None, sock_connect=10))
        return self._session

    # ------------------------------------------------------------ lifecycle
    async def start(self) -> dict:
        async with self._lock:
            if self.state == "ready" and self.proc and self.proc.returncode is None:
                return self.status()
            if not self.exe:
                self.state, self.error = "failed", "jupyter-lab not found"
                self._changed()
                return self.status()
            await self._stop_proc()
            self.root_dir.mkdir(parents=True, exist_ok=True)
            self.runtime_dir.mkdir(parents=True, exist_ok=True)
            self._token = secrets.token_urlsafe(32)
            self.port = _free_port()
            args = ["--no-browser", "--ServerApp.ip=127.0.0.1", f"--ServerApp.port={self.port}",
                    "--ServerApp.port_retries=0", f"--ServerApp.base_url={self.base_url}",
                    f"--ServerApp.root_dir={self.root_dir}", "--ServerApp.open_browser=False",
                    "--ServerApp.allow_remote_access=False", "--LabApp.news_url=None",
                    "--LabApp.check_for_updates_class=jupyterlab.NeverCheckForUpdate"]
            # own config dir: the user's ~/.jupyter config (e.g. `token = ''` for their own server) must never apply
            cfg_dir = self.runtime_dir / "config"
            cfg_dir.mkdir(parents=True, exist_ok=True)
            cfg = cfg_dir / "jupyter_server_config.json"
            fd = os.open(cfg, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, "w") as f:
                json.dump({"IdentityProvider": {"token": self._token}, "ServerApp": {"token": self._token,
                                                                                     "password": ""}}, f)
            env = scrub_env(dict(os.environ))
            self.share_dir.mkdir(parents=True, exist_ok=True)
            self._guard_kernelspecs()
            env.update({"JUPYTER_CONFIG_DIR": str(cfg_dir), "JUPYTER_RUNTIME_DIR": str(self.runtime_dir / "runtime"),
                        "JUPYTER_PATH": str(self.share_dir), "PYTHONUNBUFFERED": "1"})
            self.state, self.error, self._tail = "starting", "", []
            self._changed()
            try:
                self.proc = await asyncio.create_subprocess_exec(
                    *guarded(self.exe, args), cwd=str(self.root_dir), env=env, stdin=asyncio.subprocess.DEVNULL,
                    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT, start_new_session=True)
            except OSError as e:
                self.state, self.error = "failed", str(e)
                self._changed()
                return self.status()
            self._log_task = asyncio.create_task(self._drain(self.proc))
            t0 = time.monotonic()
            while time.monotonic() - t0 < 60:
                if self.proc.returncode is not None:
                    self.state = "failed"
                    self.error = "jupyter-lab exited: " + "\n".join(self._tail[-10:])
                    self._changed()
                    return self.status()
                try:
                    async with self._http().get(self.url + self.base_url + "api/status", headers=self._headers(),
                                                timeout=aiohttp.ClientTimeout(total=2)) as r:
                        if r.status == 200:
                            break
                except (aiohttp.ClientError, asyncio.TimeoutError, OSError):
                    pass
                await asyncio.sleep(0.3)
            else:
                await self._stop_proc()
                self.state, self.error = "failed", "jupyter-lab did not answer within 60 s"
                self._changed()
                return self.status()
            # safety: the child must refuse requests without the token
            try:
                async with self._http().get(self.url + self.base_url + "api/contents") as r:
                    open_door = r.status < 400
            except aiohttp.ClientError:
                open_door = True
            if open_door:
                await self._stop_proc()
                self.state, self.error = "failed", "jupyter-lab started without authentication: refused"
                log.error(self.error)
                self._changed()
                return self.status()
            try:
                async with self._http().get(self.url + self.base_url + "api/kernelspecs",
                                            headers=self._headers()) as r:
                    self.kernels = sorted((await r.json(content_type=None)).get("kernelspecs", {}))
            except (aiohttp.ClientError, ValueError):
                self.kernels = []
            self.state = "ready"
            log.info("jupyter-lab ready on port %s (%.1f s)", self.port, time.monotonic() - t0)
            self._changed()
            return self.status()

    def _guard_kernelspecs(self) -> None:
        """Kernels are started by jupyter-lab in their own session, so killing jupyter-lab's process group (or
        jupyter-lab dying with the server through PR_SET_PDEATHSIG) does not stop them. Madalean's JUPYTER_PATH
        therefore overrides the `python3` kernelspec with the same kernel started through `guarded` (setpriv
        --pdeathsig KILL): a kernel dies with its jupyter-lab, which dies with the server."""
        py = Path(self.exe).resolve().parent / "python3" if self.exe else None
        if py is None or not py.exists():
            py = Path(deps.tool("python") or "")
        if not py or not py.exists():
            return
        d = self.share_dir / "kernels" / "python3"
        try:
            d.mkdir(parents=True, exist_ok=True)
            spec = {"argv": guarded(str(py), ["-m", "ipykernel_launcher", "-f", "{connection_file}"]),
                    "display_name": "Python 3 (ipykernel)", "language": "python",
                    "metadata": {"debugger": True, "madalean_guarded": bool(SETPRIV)}}
            (d / "kernel.json").write_text(json.dumps(spec, indent=1), encoding="utf-8")
        except OSError:
            log.exception("cannot write the guarded python3 kernelspec")

    async def _drain(self, proc: asyncio.subprocess.Process) -> None:
        assert proc.stdout is not None
        while True:
            b = await proc.stdout.readline()
            if not b:
                break
            line = b.decode("utf-8", "replace").rstrip()
            if self._token:
                line = line.replace(self._token, "***")
            self._tail = (self._tail + [line])[-80:]
        await proc.wait()
        if proc is self.proc and self.state == "ready":
            self.state, self.error = "failed", "jupyter-lab exited unexpectedly"
            self._changed()

    async def _stop_proc(self) -> None:
        proc, self.proc = self.proc, None
        if proc is None or proc.returncode is not None:
            return
        for sig, wait in ((signal.SIGTERM, 8.0), (signal.SIGKILL, 5.0)):
            try:
                os.killpg(proc.pid, sig)
            except (ProcessLookupError, PermissionError):
                try:
                    proc.send_signal(sig)
                except ProcessLookupError:
                    break
            try:
                await asyncio.wait_for(proc.wait(), wait)
                break
            except asyncio.TimeoutError:
                continue
        try:
            os.killpg(proc.pid, signal.SIGKILL)       # kernels started by jupyter share its process group
        except (ProcessLookupError, PermissionError):
            pass

    async def stop(self) -> None:
        async with self._lock:
            await self._stop_proc()
            if self._log_task:
                self._log_task.cancel()
                self._log_task = None
            if self._session is not None:
                await self._session.close()
                self._session = None
            self._token = ""
            self.state, self.port = "stopped", None
            self._changed()

    async def _ensure(self) -> None:
        if not (self.state == "ready" and self.proc and self.proc.returncode is None):
            st = await self.start()
            if st["state"] != "ready":
                raise RuntimeError(st["error"] or "jupyter unavailable")

    # ------------------------------------------------------------ contents API
    async def _contents(self, method: str, path: str, **kw):
        await self._ensure()
        url = self.url + self.base_url + "api/contents/" + path
        async with self._http().request(method, url, headers=self._headers(), **kw) as r:
            body = await r.read()
            if r.status >= 400:
                raise FileNotFoundError(path) if r.status == 404 else RuntimeError(f"jupyter {r.status}: {body[:200]!r}")
            return json.loads(body) if body else {}

    async def list_notebooks(self, path: str = "") -> list[dict]:
        path = safe_path(path)
        d = await self._contents("GET", path, params={"content": "1"})
        out = []
        for it in d.get("content") or []:
            if it["name"].startswith("."):
                continue
            if it["type"] == "notebook":
                out.append({k: it.get(k) for k in ("name", "path", "type", "last_modified")})
            elif it["type"] == "directory":
                out.append({k: it.get(k) for k in ("name", "path", "type", "last_modified")})
                try:
                    sub = await self._contents("GET", it["path"], params={"content": "1"})
                except (RuntimeError, FileNotFoundError):
                    continue
                out += [{k: s.get(k) for k in ("name", "path", "type", "last_modified")}
                        for s in sub.get("content") or [] if s["type"] == "notebook" and not s["name"].startswith(".")]
        return out

    async def create_notebook(self, path: str, kernel: str = "python3") -> dict:
        path = safe_path(path, allow_empty=False)
        if not path.endswith(".ipynb"):
            raise ValueError("not a notebook")
        nb = {"cells": [], "metadata": {"kernelspec": {"name": kernel, "display_name": kernel, "language":
                                                       "sage" if kernel == "sagemath" else "python"}},
              "nbformat": 4, "nbformat_minor": 5}
        parts = path.split("/")[:-1]
        for i in range(len(parts)):
            d = "/".join(parts[: i + 1])
            try:
                await self._contents("GET", d, params={"content": "0"})
            except FileNotFoundError:
                await self._contents("PUT", d, json={"type": "directory"})
        await self._contents("PUT", path, json={"type": "notebook", "format": "json", "content": nb})
        return {"path": path}

    async def read_notebook(self, path: str) -> dict:
        path = safe_path(path, allow_empty=False)
        d = await self._contents("GET", path, params={"content": "1", "type": "notebook"})
        nb = d.get("content") or {}
        cells = []
        for i, c in enumerate(nb.get("cells") or []):
            outs = []
            for o in c.get("outputs") or []:
                if "text" in o:
                    outs.append(_text(o["text"]))
                elif "data" in o and "text/plain" in o["data"]:
                    outs.append(_text(o["data"]["text/plain"]))
                elif o.get("output_type") == "error":
                    outs.append(f"{o.get('ename')}: {o.get('evalue')}")
            cells.append({"index": i, "cell_type": c.get("cell_type"), "source": _text(c.get("source")),
                          "outputs_text": "\n".join(outs)})
        ks = (nb.get("metadata") or {}).get("kernelspec") or {}
        return {"path": path, "cells": cells, "kernel": ks.get("name")}

    async def append_cell(self, path: str, source: str, cell_type: str = "code") -> dict:
        path = safe_path(path, allow_empty=False)
        if cell_type not in ("code", "markdown", "raw"):
            raise ValueError("bad cell type")
        d = await self._contents("GET", path, params={"content": "1", "type": "notebook"})
        nb = d.get("content") or {}
        cell = {"cell_type": cell_type, "metadata": {}, "source": source, "id": secrets.token_hex(4)}
        if cell_type == "code":
            cell.update(outputs=[], execution_count=None)
        nb.setdefault("cells", []).append(cell)
        await self._contents("PUT", path, json={"type": "notebook", "format": "json", "content": nb})
        return {"path": path, "index": len(nb["cells"]) - 1}

    # ------------------------------------------------------------ reverse proxy
    def _upstream_headers(self, request: web.Request) -> dict:
        h = {k: v for k, v in request.headers.items() if k.lower() not in HOP and not k.lower().startswith("sec-websocket")}
        h["Authorization"] = f"token {self._token}"
        h["Host"] = f"127.0.0.1:{self.port}"
        if "Origin" in request.headers:
            h["Origin"] = self.url
        return h

    async def proxy(self, request: web.Request) -> web.StreamResponse:
        try:
            await self._ensure()
        except Exception as e:  # noqa: BLE001
            return web.json_response({"error": "jupyter_unavailable", "details": str(e)[:500]}, status=503)
        tail = request.match_info.get("tail", "")
        url = self.url + self.base_url + tail
        if request.query_string:
            url += "?" + request.query_string
        if request.headers.get("Upgrade", "").lower() == "websocket":
            return await self._proxy_ws(request, url)
        headers = self._upstream_headers(request)
        data = request.content if request.body_exists else None
        try:
            async with self._http().request(request.method, url, headers=headers, data=data,
                                            allow_redirects=False) as up:
                resp = web.StreamResponse(status=up.status, reason=up.reason)
                for k, v in up.headers.items():
                    if k.lower() not in RESP_DROP:
                        resp.headers.add(k, v)
                if "Content-Encoding" in up.headers:
                    resp.headers["Content-Encoding"] = up.headers["Content-Encoding"]
                ctype = up.headers.get("Content-Type", "")
                if ("text/html" in ctype or "json" in ctype) and "Content-Encoding" not in up.headers \
                        and (up.content_length or 0) < 5_000_000:
                    # pages embed the server token (page_config): it must never reach a client
                    body = (await up.read()).replace(self._token.encode(), b"")
                    resp.content_length = len(body)
                    await resp.prepare(request)
                    await resp.write(body)
                    await resp.write_eof()
                    return resp
                await resp.prepare(request)
                async for chunk in up.content.iter_any():
                    await resp.write(chunk)
                await resp.write_eof()
                return resp
        except aiohttp.ClientError as e:
            return web.json_response({"error": "jupyter_unreachable", "details": str(e)[:300]}, status=502)

    async def _proxy_ws(self, request: web.Request, url: str) -> web.StreamResponse:
        protocols = [p.strip() for p in request.headers.get("Sec-WebSocket-Protocol", "").split(",") if p.strip()]
        headers = self._upstream_headers(request)
        try:
            up = await self._http().ws_connect(url.replace("http://", "ws://", 1), headers=headers,
                                               protocols=protocols, max_msg_size=0, autoping=True)
        except (aiohttp.ClientError, aiohttp.WSServerHandshakeError) as e:
            return web.json_response({"error": "jupyter_ws_failed", "details": str(e)[:300]}, status=502)
        ws = web.WebSocketResponse(protocols=[up.protocol] if up.protocol else (), max_msg_size=0, autoping=True)
        await ws.prepare(request)

        async def pump(src, dst) -> None:
            async for m in src:
                if m.type == aiohttp.WSMsgType.TEXT:
                    await dst.send_str(m.data)
                elif m.type == aiohttp.WSMsgType.BINARY:
                    await dst.send_bytes(m.data)
                elif m.type in (aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.ERROR):
                    break

        t1 = asyncio.create_task(pump(ws, up))
        t2 = asyncio.create_task(pump(up, ws))
        try:
            await asyncio.wait({t1, t2}, return_when=asyncio.FIRST_COMPLETED)
        finally:
            for t in (t1, t2):
                t.cancel()
            await up.close()
            await ws.close()
        return ws
