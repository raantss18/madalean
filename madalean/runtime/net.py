"""Manager of `madalean-net`, the embedded Tailscale node (ARCHITECTURE §18) — session S-I.

The sidecar joins the user's tailnet as `<hostname>` (default "madalean"), serves HTTPS with the Tailscale
certificate of `<hostname>.<tailnet>.ts.net` and proxies to the server's remote listener (127.0.0.1, token
required). It prints one JSON status object per line on stdout; this manager keeps the last one, publishes it as the
WebSocket event `net.status` ({"net": status}) and restarts the sidecar if it crashes (backoff, 5 tries).
The first start of a new node has `state == "needs_login"` and an `auth_url` the UI shows: the user opens it and
approves the device in their Tailscale account (Madalean never approves anything itself). No Funnel, ever.

The child is started through `guarded` (PR_SET_PDEATHSIG) with `--parent-pid`, so it also exits after `kill -9` of
the server; the host's tailscaled (if any) is never used nor touched."""
from __future__ import annotations

import asyncio
import json
import os
import re
import signal
import time
from pathlib import Path
from typing import Callable

from .. import deps
from ..logs import get
from . import guarded

log = get("net")
HOSTNAME_RE = re.compile(r"^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$")


class NetManager:
    def __init__(self, publish: Callable[[str, dict], None], state_dir: Path | None = None,
                 hostname: str = "madalean", exe: str | None = None, run_dir: Path | None = None,
                 extra_args: list[str] | None = None, max_restarts: int = 5):
        self.publish = publish
        self.state_dir = Path(state_dir or deps.tailscale_dir())
        self.run_dir = Path(run_dir or self.state_dir)
        self.hostname = hostname if HOSTNAME_RE.match(hostname or "") else "madalean"
        self.exe = exe or deps.tool("madalean-net")
        self.extra_args = list(extra_args or [])
        self.max_restarts = max_restarts
        self.proc: asyncio.subprocess.Process | None = None
        self.target = ""
        self.status_: dict = {"state": "stopped", "available": bool(self.exe)}
        self.on_change: list[Callable[[dict], None]] = []
        self._reader: asyncio.Task | None = None
        self._stopping = False
        self._restarts = 0
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------ status
    def status(self) -> dict:
        st = dict(self.status_)
        st["available"] = bool(self.exe)
        st["running"] = self.proc is not None and self.proc.returncode is None
        st["hostname"] = st.get("hostname") or self.hostname
        return st

    def _set(self, st: dict) -> None:
        self.status_ = {**st, "available": bool(self.exe)}
        payload = self.status()
        for cb in list(self.on_change):
            try:
                cb(payload)
            except Exception:  # noqa: BLE001
                log.exception("net listener failed")
        try:
            self.publish("net.status", {"net": payload})
        except Exception:  # noqa: BLE001
            log.exception("publish failed")

    @property
    def socket_path(self) -> Path:
        return self.run_dir / "net.sock"

    # ------------------------------------------------------------ lifecycle
    async def start(self, remote_port: int) -> dict:
        async with self._lock:
            if self.proc is not None and self.proc.returncode is None:
                return self.status()
            if not self.exe:
                self._set({"state": "unavailable", "error": "madalean-net not installed"})
                return self.status()
            self._stopping = False
            self.target = f"127.0.0.1:{int(remote_port)}"
            self.state_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
            os.chmod(self.state_dir, 0o700)
            args = ["--state-dir", str(self.state_dir / "state"), "--hostname", self.hostname,
                    "--target", self.target, "--status-socket", str(self.socket_path),
                    "--log-file", str(self.state_dir / "tsnet.log"), "--parent-pid", str(os.getpid()),
                    *self.extra_args]
            env = {k: v for k, v in os.environ.items() if not k.startswith(("TS_", "TAILSCALE_"))}
            env["TS_NO_LOGS_NO_SUPPORT"] = "true"
            try:
                self.proc = await asyncio.create_subprocess_exec(
                    *guarded(self.exe, args), stdin=asyncio.subprocess.DEVNULL, stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.STDOUT, env=env)
            except OSError as e:
                self._set({"state": "error", "error": str(e)})
                return self.status()
            self._set({"state": "starting", "target": self.target, "pid": self.proc.pid})
            self._reader = asyncio.create_task(self._read(self.proc, remote_port))
            return self.status()

    async def _read(self, proc: asyncio.subprocess.Process, remote_port: int) -> None:
        assert proc.stdout is not None
        while True:
            line = await proc.stdout.readline()
            if not line:
                break
            text = line.decode("utf-8", "replace").strip()
            if not text.startswith("{"):
                if text:
                    log.info("madalean-net: %s", text[:300])
                continue
            try:
                st = json.loads(text)
            except ValueError:
                continue
            if isinstance(st, dict) and st.get("event") == "status":
                st.pop("event", None)
                if st.get("state") == "running":
                    self._restarts = 0
                self._set(st)
        rc = await proc.wait()
        if proc is not self.proc:
            return
        if self._stopping:
            self._set({**self.status_, "state": "stopped", "auth_url": ""})
            return
        log.warning("madalean-net exited (rc=%s)", rc)
        if self._restarts < self.max_restarts:
            self._restarts += 1
            self._set({**self.status_, "state": "restarting", "error": f"exited rc={rc}"})
            await asyncio.sleep(min(30, 2 ** self._restarts))
            if not self._stopping:
                self.proc = None
                await self.start(remote_port)
        else:
            self._set({**self.status_, "state": "error", "error": f"exited rc={rc} ({self._restarts} restarts)"})

    async def stop(self) -> None:
        async with self._lock:
            self._stopping = True
            proc, self.proc = self.proc, None
            if proc is not None and proc.returncode is None:
                try:
                    proc.send_signal(signal.SIGTERM)
                    await asyncio.wait_for(proc.wait(), 10)
                except (ProcessLookupError, asyncio.TimeoutError):
                    try:
                        proc.kill()
                        await proc.wait()
                    except ProcessLookupError:
                        pass
            if self._reader is not None:
                try:
                    await asyncio.wait_for(self._reader, 2)
                except (asyncio.TimeoutError, asyncio.CancelledError, Exception):  # noqa: BLE001
                    self._reader.cancel()
                self._reader = None
            self._set({**self.status_, "state": "stopped", "auth_url": "", "t": time.time()})

    def forget(self) -> None:
        """Delete the node's state (the device must then be approved again). Only while stopped."""
        if self.proc is not None and self.proc.returncode is None:
            raise RuntimeError("stop the node first")
        import shutil
        shutil.rmtree(self.state_dir / "state", ignore_errors=True)
