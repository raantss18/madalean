"""One kernel per Calcul document, shared with JupyterLab (session S-P, docs/CALCUL.md §Kernels).

A document's kernel is the kernel of the Jupyter *session* of its .ipynb path, in Madalean's own JupyterLab child:
- when JupyterLab already has the notebook open, Madalean attaches to that session's kernel (Jupyter sessions API)
  instead of starting another one;
- otherwise Madalean creates the session itself (`POST /api/sessions {path, type: notebook, kernel}`), so that
  opening the notebook in JupyterLab later reuses the same kernel — never two Sage processes for one document.

Only Madalean's sandboxed kernelspecs (`madalean-sage`, `madalean-python`: offline, bubblewrap, allow-listed
environment — sagebridge) are used. If the session runs another kernel (the user switched it in JupyterLab),
Madalean refuses to execute there (`kernel_not_sandboxed`) rather than running model code outside the sandbox.

Idle kernels are shut down after `calcul_idle_minutes` (default 30, user decision: warm kernels) of inactivity,
counted from both Madalean's runs and the kernel's own `last_activity` (JupyterLab use keeps it alive)."""
from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime

from .notebook import ENGINE_RE, NB_PREAMBLE, SPECS, VARS_RE
from .sagebridge import ExecResult

SANDBOXED = {v[0] for v in SPECS.values()}


class KernelError(Exception):
    def __init__(self, kind: str, status: int = 409, detail: str = ""):
        super().__init__(kind)
        self.kind, self.status, self.detail = kind, status, detail


def _ts(s: str) -> float:
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00")).timestamp()
    except (TypeError, ValueError):
        return 0.0


class NotebookKernels:
    def __init__(self, ctx, bridge, preamble: str = ""):
        self.ctx = ctx
        self.bridge = bridge                      # sagebridge.SageBridge: kernelspecs, websocket execution
        self.preamble = preamble                  # sagebridge.PREAMBLE + calcul.CALC_PREAMBLE (report, tex)
        self.docs: dict[str, dict] = {}           # path -> {kid, sid, language, last, ready: kid, engine}
        self._locks: dict[str, asyncio.Lock] = {}

    def lock(self, path: str) -> asyncio.Lock:
        return self._locks.setdefault(path, asyncio.Lock())

    # ------------------------------------------------------------ Jupyter REST
    async def _req(self, method: str, path: str, payload: dict | None = None):
        jm = self.ctx.jupyter
        await jm._ensure()
        async with jm._http().request(method, jm.url + jm.base_url + path, headers=jm._headers(),
                                      json=payload if payload is not None else None) as r:
            body = await r.read()
            if r.status == 404:
                return None
            if r.status >= 400:
                raise KernelError("jupyter", 502, f"{r.status}: {body[:300]!r}")
            return json.loads(body) if body else {}

    async def sessions(self) -> list[dict]:
        return list(await self._req("GET", "api/sessions") or [])

    async def session_for(self, path: str) -> dict | None:
        for s in await self.sessions():
            if (s.get("path") or (s.get("notebook") or {}).get("path")) == path and s.get("kernel"):
                return s
        return None

    # ------------------------------------------------------------ lifecycle
    def known(self, path: str) -> str:
        """The kernel id Madalean knows for this document ('' = none, nothing is started)."""
        return (self.docs.get(path) or {}).get("kid", "")

    async def ensure(self, path: str, language: str) -> str:
        """The document's kernel: the existing session's (JupyterLab's or ours), else a new session."""
        spec = SPECS[language][0]
        async with self.lock(path):
            s = await self.session_for(path)
            if s is None:
                specs = await asyncio.to_thread(self.bridge.install_specs)
                if language not in specs:
                    raise KernelError("kernel_unavailable", 503, f"no {language} kernel installed")
                s = await self._req("POST", "api/sessions", {"path": path, "type": "notebook",
                                                             "name": path.rsplit("/", 1)[-1],
                                                             "kernel": {"name": spec}})
                if not s or not s.get("kernel"):
                    raise KernelError("kernel_unavailable", 503, "the session has no kernel")
            k = s["kernel"]
            if k.get("name") not in SANDBOXED:
                raise KernelError("kernel_not_sandboxed", 409, str(k.get("name")))
            kid = k["id"]
            d = self.docs.get(path)
            if d is None or d.get("kid") != kid:
                d = {"kid": kid, "sid": s.get("id", ""), "language": language, "last": time.time(), "ready": "",
                     "engine": None}
                self.docs[path] = d
            d["last"] = time.time()
            if d["ready"] == kid:
                # restarted from JupyterLab (same id, fresh state)? then the helpers are gone: new epoch, preamble
                probe = await self.bridge.execute(kid, "print('_madalean_vars' in globals())", timeout=20,
                                                  language=language, kill_on_limit=False)
                if probe.status == "ok" and "False" in probe.stdout:
                    d["ready"], d["epoch"] = "", time.time()
            if d["ready"] != kid:
                if not await self.bridge.wait_ready(kid):
                    await self.shutdown(path)
                    raise KernelError("kernel_died", 503, "\n".join(self.ctx.jupyter._tail[-15:]))
                pre = await self.bridge.execute(kid, self.preamble + "\n" + NB_PREAMBLE, timeout=180,
                                                language=language, kill_on_limit=False)
                if pre.status != "ok":
                    raise KernelError("kernel_died", 503, (pre.error or pre.stderr)[-1500:])
                m = ENGINE_RE.search(pre.stdout)
                if m:
                    try:
                        d["engine"] = json.loads(m.group(1))
                    except ValueError:
                        pass
                d["ready"] = kid
            return kid

    async def status(self, path: str) -> dict:
        """Kernel state without starting anything."""
        d = self.docs.get(path)
        out = {"kernel": "", "state": "none", "shared": False, "engine": (d or {}).get("engine"), "name": ""}
        if self.ctx.jupyter.state != "ready":
            return out
        try:
            s = await self.session_for(path)
        except Exception:  # noqa: BLE001
            return out
        if s is None:
            return out
        k = s["kernel"]
        out.update(kernel=k.get("id", ""), state=k.get("execution_state", "unknown"), name=k.get("name", ""),
                   sandboxed=k.get("name") in SANDBOXED, connections=int(k.get("connections") or 0),
                   last_activity=_ts(k.get("last_activity", "")))
        # a connection that is not one of Madalean's short-lived ones = JupyterLab has the notebook open
        out["shared"] = out["connections"] > 0
        return out

    async def interrupt(self, path: str) -> bool:
        kid = self.known(path) or ((await self.session_for(path)) or {}).get("kernel", {}).get("id", "")
        if kid:
            await self.bridge.interrupt(kid)
        return bool(kid)

    async def restart(self, path: str, language: str) -> str:
        s = await self.session_for(path)
        if s is None:
            return await self.ensure(path, language)
        kid = s["kernel"]["id"]
        await self._req("POST", f"api/kernels/{kid}/restart")
        if path in self.docs:
            self.docs[path]["ready"] = ""
        # a restarted kernel keeps its id: Madalean marks every output as from a previous session by epoch
        self.docs.setdefault(path, {"kid": kid, "sid": s.get("id", ""), "language": language, "last": time.time(),
                                    "ready": "", "engine": None})["epoch"] = time.time()
        return await self.ensure(path, language)

    async def shutdown(self, path: str) -> None:
        d = self.docs.pop(path, None)
        try:
            s = await self.session_for(path)
        except Exception:  # noqa: BLE001
            s = None
        if s is not None:
            try:
                await self._req("DELETE", f"api/sessions/{s['id']}")
            except KernelError:
                pass
        elif d and d.get("kid"):
            await self.bridge.shutdown(d["kid"])

    async def reap(self, idle_s: float) -> list[str]:
        """Shut down the Calcul kernels idle for more than idle_s (ours and JupyterLab's, under calcul/)."""
        if self.ctx.jupyter.state != "ready" or idle_s <= 0:
            return []
        out = []
        for s in await self.sessions():
            path = s.get("path") or ""
            k = s.get("kernel") or {}
            if not path.startswith("calcul/") or k.get("name") not in SANDBOXED:
                continue
            last = max(_ts(k.get("last_activity", "")), (self.docs.get(path) or {}).get("last", 0))
            if k.get("execution_state") == "busy" or time.time() - last < idle_s:
                continue
            await self.shutdown(path)
            out.append(path)
        return out

    async def close(self) -> None:
        for path in list(self.docs):
            await self.shutdown(path)

    def epoch(self, path: str) -> str:
        """Identifies the kernel's current state (changes on restart): stored with each run, for « fresh »."""
        d = self.docs.get(path) or {}
        return f"{d.get('kid', '')}@{int(d.get('epoch', 0))}" if d.get("kid") else ""

    # ------------------------------------------------------------ execution
    async def execute(self, path: str, language: str, code: str, *, timeout: float, on_output=None,
                      approx: bool = True) -> ExecResult:
        try:
            kid = await self.ensure(path, language)
        except KernelError as e:
            return ExecResult("unavailable", error=f"{e.kind}: {e.detail}"[:1500], language=language,
                              sandbox=self.bridge.sandbox_kind)
        self.docs[path]["last"] = time.time()
        res = await self.bridge.execute(kid, code, timeout=timeout, on_output=on_output, language=language,
                                        store_history=True, nb_outputs=True, kill_on_limit=False,
                                        user_expressions={"approx": "_madalean_approx(_)", "latex": "_madalean_latex(_)"}
                                        if approx else None)
        res.kernel = self.epoch(path)
        self.docs[path]["last"] = time.time()
        if res.status in ("timeout", "output_limit"):
            # interrupted by the bridge; a kernel that does not come back is shut down (never left spinning)
            if not await self.bridge.wait_ready(kid, timeout=15):
                await self.shutdown(path)
                res.killed = True
        elif res.status == "died":
            self.docs.pop(path, None)
        return res

    async def variables(self, path: str, language: str) -> list | None:
        """Names defined in the running kernel (Madalean's own helper; never starts a kernel)."""
        d = self.docs.get(path)
        if not d or d.get("ready") != d.get("kid"):
            return None
        res = await self.bridge.execute(d["kid"], "_madalean_vars()", timeout=20, language=language,
                                        kill_on_limit=False)
        m = VARS_RE.search(res.stdout or "")
        if not m:
            return None
        try:
            return json.loads(m.group(1))
        except ValueError:
            return None
