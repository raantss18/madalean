"""The Left to Solve workspace: google-deepmind/formal-conjectures at the commit the site pins (D69).

- Created only after the user's consent to the download (« Préparer l'espace », about 5–10 GB: Lean, the Mathlib
  cache, formal-conjectures); that consent also covers later updates up to the size stated then.
- One folder per commit under `<workspaces>/formal-conjectures/<commit 12>`; a new pinned commit builds a new folder
  BESIDE the old one, which stays in use until the new one is ready (then `current` points to the new one; the old
  one is removed after the switch).
- Steps (each bounded, logged, shown as `step` / `progress`): git clone at the commit, the toolchain of its
  `lean-toolchain` (elan), `lake exe cache get` (Mathlib cache), `lake build FormalConjecturesUtil`. A problem's
  module is built on demand (`lake build <module>`) before its first check.
- What runs: git, elan and lake on the upstream project at the pinned commit (Apache-2.0, the code every Left to
  Solve agent builds); never a command taken from the site's text."""
from __future__ import annotations

import asyncio
import os
import re
import shutil
import time
from pathlib import Path

from .. import config
from ..logs import get
from ..workspaces import NOSCAN_MARKER, Workspace, toolchain_dir

log = get("attack.workspace")
REPO = "https://github.com/google-deepmind/formal-conjectures"
KEY = "formal-conjectures"
ESTIMATE_GB = 10.0
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
MODULE_RE = re.compile(r"^FormalConjectures(\.[A-Za-z0-9_«»]+)+$")
STEP_TIMEOUT = {"clone": 1800, "toolchain": 1800, "cache": 3600, "build": 3600, "module": 1800}


MEASURE_EVERY = 10.0


def _disk_bytes(path: Path) -> int:
    total = 0
    for dirpath, _dirs, files in os.walk(path):
        for f in files:
            try:
                total += os.lstat(os.path.join(dirpath, f)).st_size
            except OSError:
                pass
    return total


async def default_runner(argv: list[str], cwd: Path, timeout: float, env: dict) -> tuple[int, str]:
    proc = await asyncio.create_subprocess_exec(*argv, cwd=str(cwd), env=env, stdout=asyncio.subprocess.PIPE,
                                                stderr=asyncio.subprocess.STDOUT, start_new_session=True)
    try:
        out, _ = await asyncio.wait_for(proc.communicate(), timeout)
    except (asyncio.TimeoutError, asyncio.CancelledError):
        try:
            os.killpg(proc.pid, 9)
        except (ProcessLookupError, PermissionError):
            pass
        await proc.wait()
        raise
    return proc.returncode or 0, out.decode("utf-8", "replace")[-3000:]


def default_root() -> Path:
    return config.WORKSPACES_DIR / KEY


def current_workspace(root: Path | None = None) -> Workspace | None:
    """The ready workspace `current` points to (also listed by workspaces.builtin_workspaces)."""
    root = root or default_root()
    try:
        commit = (root / "current").read_text().strip()
    except OSError:
        return None
    if not COMMIT_RE.match(commit):
        return None
    d = root / commit[:12]
    if not (d / ".madalean-ready").exists():
        return None
    try:
        tc = (d / "lean-toolchain").read_text().strip()
    except OSError:
        tc = ""
    return Workspace(KEY, f"Left to Solve (formal-conjectures {commit[:12]})", d, tc, False,
                     "Énoncés de google-deepmind/formal-conjectures au commit épinglé par lefttosolve.com.")


class WorkspaceManager:
    def __init__(self, root: Path | None = None, runner=None, on_change=None):
        self.root = root or default_root()
        self.runner = runner or default_runner
        self.on_change = on_change or (lambda st: None)
        self.task: asyncio.Task | None = None
        self.state: dict = {"state": "none", "commit": "", "size": f"≈ {ESTIMATE_GB:.0f} Go", "percent": 0,
                            "step": "", "error": "", "building": ""}
        ws = current_workspace(self.root)
        if ws is not None:
            self.state.update(state="ready", commit=(self.root / "current").read_text().strip())
        self._modules: set[str] = set()
        self._done = 0

    def workspace(self) -> Workspace | None:
        return current_workspace(self.root)

    def public(self) -> dict:
        """`progress = {done_bytes, total_bytes}`: bytes really on disk in the folder being built (measured every
        MEASURE_EVERY s; the toolchain, kept by elan, is not counted) against the stated estimate (`estimated`)."""
        total = int(ESTIMATE_GB * 1e9)
        done = total if self.state["state"] == "ready" and not self.state.get("building") else self._done
        return {**self.state, "progress": {"done_bytes": min(done, total), "total_bytes": total, "estimated": True}}

    async def _measure(self, path: Path) -> None:
        while True:
            self._done = await asyncio.to_thread(_disk_bytes, path)
            self.on_change(self.public())
            await asyncio.sleep(MEASURE_EVERY)

    def _set(self, **kw) -> None:
        self.state.update(kw)
        self.on_change(self.public())

    @property
    def busy(self) -> bool:
        return self.task is not None and not self.task.done()

    def ensure(self, commit: str, allowed_gb: float) -> str:
        """Start building `commit` when needed and allowed. Returns ready | building | consent | error."""
        if not COMMIT_RE.match(commit or ""):
            return "error"
        cur = self.workspace()
        if cur is not None and self.state.get("commit") == commit:
            return "ready"
        if self.busy:
            return "building"
        if allowed_gb < ESTIMATE_GB:
            if cur is None:
                self._set(state="none", step="consent", error="")
            return "consent"
        self.task = asyncio.create_task(self._build(commit), name=f"attack-workspace-{commit[:12]}")
        return "building"

    async def _run(self, step: str, argv: list[str], cwd: Path, env: dict) -> None:
        rc, out = await self.runner(argv, cwd, STEP_TIMEOUT[step], env)
        if rc != 0:
            raise RuntimeError(f"{step}: {out.strip()[-400:] or rc}")

    def _env(self) -> dict:
        e = {k: v for k, v in os.environ.items() if not k.startswith(("LEAN", "LAKE"))}
        e["ELAN_HOME"] = str(config.ELAN_HOME)
        e["PATH"] = f"{config.ELAN_HOME / 'bin'}:{e.get('PATH', '')}"
        e["GIT_TERMINAL_PROMPT"] = "0"
        return e

    async def _build(self, commit: str) -> None:
        final = self.root / commit[:12]
        tmp = self.root / (commit[:12] + ".partial")
        keep = self.workspace()
        self._done = 0
        meter = asyncio.create_task(self._measure(tmp))
        try:
            self.root.mkdir(parents=True, exist_ok=True)
            (self.root / NOSCAN_MARKER).touch()
            if tmp.exists():
                await asyncio.to_thread(shutil.rmtree, tmp, True)
            env = self._env()
            self._set(state="downloading" if keep is None else self.state["state"], building=commit, step="clone",
                      percent=5, error="")
            git = shutil.which("git") or "git"
            await self._run("clone", [git, "clone", "--filter=blob:none", "--no-checkout", REPO, str(tmp)],
                            self.root, env)
            await self._run("clone", [git, "-c", "advice.detachedHead=false", "checkout", commit], tmp, env)
            tc = (tmp / "lean-toolchain").read_text().strip() if (tmp / "lean-toolchain").exists() else ""
            if not re.match(r"^[\w./:-]{1,80}$", tc):
                raise RuntimeError("lean-toolchain illisible")
            self._set(step="toolchain", percent=20)
            if toolchain_dir(tc) is None:
                elan = str(config.ELAN_HOME / "bin" / "elan") if (config.ELAN_HOME / "bin" / "elan").exists() \
                    else (shutil.which("elan") or "elan")
                await self._run("toolchain", [elan, "toolchain", "install", tc], tmp, env)
            sysroot = toolchain_dir(tc)
            lake = str(sysroot / "bin" / "lake") if sysroot else (shutil.which("lake") or "lake")
            self._set(step="cache", percent=35)
            await self._run("cache", [lake, "exe", "cache", "get"], tmp, env)
            self._set(state="building" if keep is None else self.state["state"], step="build", percent=70)
            await self._run("build", [lake, "build", "FormalConjecturesUtil"], tmp, env)
            (tmp / ".madalean-ready").write_text(time.strftime("%Y-%m-%d %H:%M:%S"))
            if final.exists():
                await asyncio.to_thread(shutil.rmtree, final, True)
            tmp.rename(final)
            (self.root / "current").write_text(commit)
            self._modules.clear()
            self._set(state="ready", commit=commit, step="", percent=100, building="")
            if keep is not None and keep.path != final:      # the old one served until now: removed after the switch
                await asyncio.to_thread(shutil.rmtree, keep.path, True)
            log.info("attack workspace ready at %s", commit[:12])
        except asyncio.CancelledError:
            self._set(state="ready" if keep else "none", building="", step="")
            raise
        except Exception as e:  # noqa: BLE001
            log.warning("attack workspace %s failed: %s", commit[:12], e)
            self._set(state="ready" if keep else "error", error=str(e)[:400], building="", step="")
        finally:
            meter.cancel()

    async def build_module(self, module: str) -> tuple[bool, str]:
        """`lake build <module>` in the ready workspace, once per module (oleans the checks import)."""
        ws = self.workspace()
        if ws is None or not MODULE_RE.match(module or ""):
            return False, "module"
        if module in self._modules:
            return True, ""
        lake = str(ws.sysroot / "bin" / "lake") if ws.sysroot else "lake"
        try:
            await self._run("module", [lake, "build", module], ws.path, self._env())
        except (RuntimeError, OSError, asyncio.TimeoutError) as e:
            return False, str(e)[:300]
        self._modules.add(module)
        return True, ""
