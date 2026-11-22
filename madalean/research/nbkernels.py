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

# S-AO (TODO B15, DECISIONS D47): « Calcul prêt d'avance ». Opening a document (or its project) starts its kernel in
# the background and runs these fixed first-use initialisations, outside the history (no `_`, no execution count, no
# output in the notebook, no user-visible name), each as its own execution so that a user's run waits at most for the
# current step: the warm-up stops as soon as the user runs something. Measured on Sage 10.10 (docs/PERFORMANCE.md):
# Maxima's first integral ≈ 7 s in a new home (compiles its linear-algebra share package), the first plot ≈ 0.7 s
# (matplotlib's font cache, backend), the first finite field ≈ 0.1 s.
SAGE_WARMUP = (
    ("integral", "def _madalean_w():\n"
                 "    t = SR.var('_madalean_t')\n"
                 "    integrate(t * sin(t), t); integrate(t ** 2 * cos(t), t, 0, 1); limit(sin(t) / t, t=0)\n"
                 "    latex(sqrt(2) * pi)\n"
                 "_madalean_w(); del _madalean_w"),
    ("plot", "def _madalean_w():\n"
             "    from io import BytesIO\n"
             "    from matplotlib.backends.backend_agg import FigureCanvasAgg\n"
             "    FigureCanvasAgg(plot(sin, (0, 1)).matplotlib()).print_png(BytesIO())\n"
             "_madalean_w(); del _madalean_w"),
    ("finite_field", "def _madalean_w():\n"
                     "    K = GF(3 ** 4, 'madalean_a'); R = PolynomialRing(K, 'madalean_y'); y = R.gen()\n"
                     "    (y ** 12 + K.gen() * y + 1).factor(); factor(2 ** 64 + 1)\n"
                     "_madalean_w(); del _madalean_w"),
)
PYTHON_WARMUP = (
    ("plot", "def _madalean_w():\n"
             "    try:\n"
             "        import matplotlib.font_manager  # noqa: F401  (builds the font cache once)\n"
             "    except ImportError:\n"
             "        pass\n"
             "_madalean_w(); del _madalean_w"),
)
WARM_MAX_UNUSED = 2          # kernels started in advance and not used yet (the oldest is stopped beyond that)
WARM_MIN_FREE_MB = 1500      # never start a kernel in advance when the machine has less memory available
WARM_STEP_TIMEOUT_S = 120.0
SEED_PATH = "calcul/.seed/seed.ipynb"   # the seed kernel's session (hidden directory, never a document; home
                                        # `warm-seed`, sagebridge.home_key)


def mem_available_mb(meminfo: str = "/proc/meminfo") -> int | None:
    try:
        with open(meminfo, encoding="ascii") as f:
            for line in f:
                if line.startswith("MemAvailable:"):
                    return int(line.split()[1]) // 1024
    except (OSError, ValueError, IndexError):
        return None
    return None


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
        # S-AO: kernels prepared in advance, per path: {state: starting|warming|ready|failed, language, t0, t1,
        # start_s, steps: {name: seconds | "error"}, used: bool, error, seeded}
        self.warm: dict[str, dict] = {}
        self._warm_tasks: dict[str, asyncio.Task] = {}
        self.warm_log: list[dict] = []            # the last warm-ups (health row, PERFORMANCE.md)
        self._seed_task: asyncio.Task | None = None
        self._seed_tried: set[str] = set()
        self.seed_log: dict = {}

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

    # ------------------------------------------------------------ S-AO: ready in advance
    def warm_status(self, path: str) -> dict:
        w = self.warm.get(path)
        if w is None:
            return {"state": "none"}
        return {k: w[k] for k in ("state", "start_s", "steps", "used", "error", "seconds", "seeded") if k in w}

    def warm_summary(self) -> dict:
        """For the health row: kernels prepared in advance now, and the last warm-ups."""
        live = {p: w for p, w in self.warm.items()
                if w["state"] in ("starting", "warming", "ready") and p in self.docs and p != SEED_PATH}
        return {"live": len(live), "loading": sum(1 for w in live.values() if w["state"] != "ready"),
                "unused": sum(1 for w in live.values() if not w.get("used")),
                # the latest warm-up decides (a failed step of an older one is not shown forever)
                "failed": [self.warm_log[-1]["error"]] if self.warm_log and self.warm_log[-1].get("error") else [],
                "skipped": [w.get("error", "") for w in self.warm.values() if w["state"] == "skipped"],
                "last": self.warm_log[-5:], "seed": dict(self.seed_log),
                "seeding": self._seed_task is not None and not self._seed_task.done()}

    def prewarm(self, path: str, language: str) -> dict:
        """Start (or attach to) the document's kernel in the background and run the first-use initialisations.
        Idempotent; returns the current warm status. Never blocks the caller."""
        w = self.warm.get(path)
        t = self._warm_tasks.get(path)
        if t is not None and not t.done():
            return self.warm_status(path)
        d = self.docs.get(path)
        if w is not None and w["state"] == "ready" and d is not None and d.get("ready") == d.get("kid"):
            return self.warm_status(path)
        if d is not None and d.get("ready") == d.get("kid") and d.get("kid"):
            return self.warm_status(path)                 # already running (a run started it): nothing to prepare
        self.warm[path] = {"state": "starting", "language": language, "t0": time.time(), "steps": {},
                           "used": False}
        self._warm_tasks[path] = asyncio.ensure_future(self._prewarm(path, language))
        return self.warm_status(path)

    async def _make_room(self, path: str) -> None:
        unused = sorted((w["t0"], p) for p, w in self.warm.items()
                        if p not in (path, SEED_PATH) and p in self.docs and not w.get("used")
                        and w["state"] in ("starting", "warming", "ready"))
        while len(unused) >= WARM_MAX_UNUSED:
            _t, p = unused.pop(0)
            await self.shutdown(p)

    async def _steps(self, path: str, language: str, w: dict) -> None:
        """Run the warm-up steps in the document's kernel; stop at the user's first run."""
        for name, code in (SAGE_WARMUP if language == "sage" else PYTHON_WARMUP):
            if w["used"] or path not in self.docs:
                break
            t1 = time.monotonic()
            res = await self.bridge.execute(self.docs[path]["kid"], code, timeout=WARM_STEP_TIMEOUT_S,
                                            language=language, store_history=False, kill_on_limit=False)
            w["steps"][name] = round(time.monotonic() - t1, 2) if res.status == "ok" else "error"
            if res.status != "ok":
                w.setdefault("error", f"{name}: {res.status} {(res.error or res.stderr)[-300:]}".strip())
                if res.status in ("died", "timeout", "output_limit"):
                    break

    def _home(self, path: str) -> str:
        from . import sagebridge
        return sagebridge.home_dir({"workdir": str(self.bridge.workroot.resolve())}, {"JPY_SESSION_NAME": path})

    def _seed_marker(self, path: str) -> str:
        """`<experiments>/.home/.seed/.done-<Sage version>`: the seed holds this version's first-use caches."""
        import os
        import re
        from . import sagebridge
        ver = str(((self.docs.get(path) or {}).get("engine") or {}).get("version") or "")
        ver = re.sub(r"[^\w.+-]", "_", ver)[:40]
        return os.path.join(sagebridge.seed_dir(self._home(path)), f".done-{ver}") if ver else ""

    async def _harvest(self, path: str, since: float) -> int:
        """Copy what an undisturbed warm-up created into the seed, and mark the seed done for this Sage version."""
        from . import sagebridge
        marker = self._seed_marker(path)
        try:
            n = await asyncio.to_thread(sagebridge.harvest_seed, self._home(path), since)
            if marker and n:
                await asyncio.to_thread(lambda: open(marker, "w", encoding="utf-8").write(str(n)))
            return n
        except OSError:
            return 0

    async def _prewarm(self, path: str, language: str) -> None:
        import os
        w = self.warm[path]
        try:
            free = mem_available_mb()
            if free is not None and free < WARM_MIN_FREE_MB:
                w.update(state="skipped", error=f"memory: {free} MB available")
                return
            await self._make_room(path)
            fresh = await self.session_for(path) is None   # a session JupyterLab opened may have run user code
            t0 = time.monotonic()
            await self.ensure(path, language)
            w["start_s"] = round(time.monotonic() - t0, 2)
            w["state"] = "warming"
            if fresh:
                await self._steps(path, language, w)
            marker = self._seed_marker(path) if language == "sage" else ""
            if fresh and not w["used"] and path in self.docs and "error" not in w:
                w["seeded"] = await self._harvest(path, w["t0"])
            if marker and marker not in self._seed_tried and not w.get("error") \
                    and not await asyncio.to_thread(os.path.exists, marker):
                # the user ran a cell first, or this home already had its caches: the first-use caches of this Sage
                # version are prepared once, aside (≈ 12 s, one kernel), for the next new projects
                self._seed_tried.add(marker)
                if self._seed_task is None or self._seed_task.done():
                    self._seed_task = asyncio.ensure_future(self._prepare_seed())
            w["state"] = "ready" if path in self.docs else "none"
        except KernelError as e:
            w.update(state="failed", error=f"{e.kind}: {e.detail}"[:300])
        except asyncio.CancelledError:
            w["state"] = "none"
            raise
        except Exception as e:  # noqa: BLE001
            w.update(state="failed", error=str(e)[:300])
        finally:
            w["seconds"] = round(time.time() - w["t0"], 2)
            if w["state"] in ("ready", "failed", "skipped"):
                self.warm_log.append({"path": path, "language": language, "state": w["state"],
                                      "start_s": w.get("start_s"), "steps": dict(w["steps"]),
                                      "seconds": w["seconds"], "used": w["used"], "t": time.time(),
                                      "error": w.get("error", ""), "seeded": w.get("seeded", 0)})
                del self.warm_log[:-20]

    async def _prepare_seed(self) -> None:
        """Once per Sage version: a kernel that only ever runs Madalean's warm-up (its own home `warm-seed`) fills
        the seed, then stops."""
        path = SEED_PATH
        free = mem_available_mb()
        if free is not None and free < WARM_MIN_FREE_MB:
            return
        try:            # Jupyter derives the kernel's JPY_SESSION_NAME (hence its home) from an existing directory
            (self.ctx.jupyter.root_dir / "calcul" / ".seed").mkdir(parents=True, exist_ok=True)
        except OSError:
            return
        w = {"state": "starting", "language": "sage", "t0": time.time(), "steps": {}, "used": False}
        self.warm[path] = w
        try:
            await self.ensure(path, "sage")
            w["state"] = "warming"
            await self._steps(path, "sage", w)
            if path in self.docs and "error" not in w and not w["used"]:
                w["seeded"] = await self._harvest(path, w["t0"])
        except Exception:  # noqa: BLE001
            pass
        finally:
            self.seed_log = {k: w.get(k) for k in ("steps", "seeded", "error")} | {
                "seconds": round(time.time() - w["t0"], 2)}
            await self.shutdown(path)

    def _mark_used(self, path: str) -> None:
        w = self.warm.get(path)
        if w is not None:
            w["used"] = True

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
        self._mark_used(path)                     # a restart is the user's: no warm-up step runs after it
        await self._req("POST", f"api/kernels/{kid}/restart")
        if path in self.docs:
            self.docs[path]["ready"] = ""
        # a restarted kernel keeps its id: Madalean marks every output as from a previous session by epoch
        self.docs.setdefault(path, {"kid": kid, "sid": s.get("id", ""), "language": language, "last": time.time(),
                                    "ready": "", "engine": None})["epoch"] = time.time()
        return await self.ensure(path, language)

    async def shutdown(self, path: str) -> None:
        d = self.docs.pop(path, None)
        self.warm.pop(path, None)
        t = self._warm_tasks.pop(path, None)
        if t is not None and not t.done() and t is not asyncio.current_task():
            t.cancel()
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
        for t in [*self._warm_tasks.values(), self._seed_task]:
            if t is not None:
                t.cancel()
        for path in list(self.docs):
            await self.shutdown(path)

    def epoch(self, path: str) -> str:
        """Identifies the kernel's current state (changes on restart): stored with each run, for « fresh »."""
        d = self.docs.get(path) or {}
        return f"{d.get('kid', '')}@{int(d.get('epoch', 0))}" if d.get("kid") else ""

    # ------------------------------------------------------------ execution
    async def execute(self, path: str, language: str, code: str, *, timeout: float, on_output=None,
                      approx: bool = True) -> ExecResult:
        self._mark_used(path)                     # S-AO: a warm-up in progress stops at its current step
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

    async def probe(self, path: str, language: str, program: str, *, timeout: float) -> ExecResult:
        """S-AJ (D42): run one of Madalean's fixed step probes (research/steps.py) in the document's kernel, outside
        the history (no `_`, no execution count, no outputs recorded in the notebook). The caller holds the
        document's run lock and checked that the cell may run."""
        self._mark_used(path)
        try:
            kid = await self.ensure(path, language)
        except KernelError as e:
            return ExecResult("unavailable", error=f"{e.kind}: {e.detail}"[:1500], language=language,
                              sandbox=self.bridge.sandbox_kind)
        self.docs[path]["last"] = time.time()
        res = await self.bridge.execute(kid, program, timeout=timeout, language=language, store_history=False,
                                        kill_on_limit=False)
        if res.status in ("timeout", "output_limit") and not await self.bridge.wait_ready(kid, timeout=15):
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
