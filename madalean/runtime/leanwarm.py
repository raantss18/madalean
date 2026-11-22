"""Warm Lean checker (TODO B10, DECISIONS D37): one long-lived `lean --server` per workspace, Mathlib already loaded.

Every fresh `lean --json` check reloads Mathlib (2–3.5 s with the page cache warm, 10–34 s cold, ~3.4 GB). Lean's own
language server keeps the imports of a document loaded across `textDocument/didChange` as long as the header (the
`import` lines) is unchanged, and re-elaborates the rest: an attempt is then checked in a fraction of a second.

Protocol (the same on Lean v4.9.0-rc1 and v4.36.0, both measured):
- `lean --server` under `leansandbox.wrap` (D28: no network, read-only toolchain and workspace, private HOME,
  allow-listed environment), an `untitled:` document URI (Lean then never runs `lake setup-file`) and `LAKE` pointing
  nowhere; `dependencyBuildMode: never`.
- One document per worker, opened with the worker's « prefix »: the header plus the first character after it.
  Lean reuses the loaded imports only when the first difference between two versions lies strictly AFTER the
  header and its trailing whitespace (`isBeforeEditPos`, measured on v4.9: a header-only document costs a full
  re-import at every switch), hence that one shared character.
- Each attempt: the document is first reset to the prefix alone, then replaced by the whole attempt text; a version
  is complete when Lean reported it « done » and published its diagnostics (`LspClient.finished`; Lean's own
  `waitForDiagnostics` request hangs on v4.9). The reset means that nothing of a previous
  attempt can be reused (no command snapshot, no incremental tactic snapshot): every command after the header is
  elaborated from the header's environment, exactly like a fresh file.
- The attempt is sent verbatim: line numbers are the file's; LSP columns (UTF-16) are converted back to Lean's
  code-point columns; the full range is used; the result is rendered as `lean --json` lines, so `parse_lean_json`,
  `judge`, `errors_for_feedback` and the probe batches read exactly what a fresh run prints.

What this module does NOT decide: whether a warm verdict may be used. That is `runtime/lean.py` (warm results only
serve intermediate attempts; a warm acceptance of a strict check is always re-checked by a fresh `lean --json`)."""
from __future__ import annotations

import asyncio
import json
import os
import re
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from .. import leancheck, leansandbox
from ..logs import get
from . import guarded

log = get("lean.warm")

URI = "untitled:/madalean/Attempt.lean"
START_TIMEOUT = 900.0          # cold Mathlib on a slow disk
RESET_TIMEOUT = 30.0
WAIT_BUSY = 1.0                # a busy worker is waited for this long, then the check runs fresh
MAX_WORKERS = 2                # warm workspaces at once (~3.4 GB each); least recently used one is stopped
MISMATCH_RESTART = 3           # consecutive checks with another prefix: restart the worker on that prefix
RETRY_AFTER_FAILURE = 300.0    # a worker that could not start is not retried before this
AUDIT_EVERY = 20               # one warm verdict in N (and the first after each start) is re-checked fresh
REAPER_EVERY = 30.0
MAX_MEMORY_MB = 8192           # a worker above this (`exact?` caches its library index: ~6 GB) is recycled when idle

READY, LOADING, BUSY = "ready", "loading", "busy"


class WarmUnavailable(Exception):
    """The warm worker cannot give a trustworthy answer for this check (crash, lost answer…): check fresh."""


# ---------------------------------------------------------------- text helpers
def split_header(code: str) -> str | None:
    """The exact text of the file's header: everything before the first token that is not part of an `import`
    line (whitespace and plain comments in between included, so that Lean sees the same header syntax). None when
    the file has no import or starts with something the warm path does not handle (`prelude`, `module`…)."""
    i, n = 0, len(code)
    end_last_import = -1
    while i < n:
        c = code[i]
        if c.isspace():
            i += 1
            continue
        if code.startswith("--", i):
            j = code.find("\n", i)
            i = n if j < 0 else j + 1
            continue
        if code.startswith("/-", i) and not code.startswith(("/--", "/-!"), i):
            depth, j = 1, i + 2
            while j < n and depth:
                if code.startswith("/-", j):
                    depth, j = depth + 1, j + 2
                elif code.startswith("-/", j):
                    depth, j = depth - 1, j + 2
                else:
                    j += 1
            if depth:
                return None
            i = j
            continue
        m = re.match(r"import\s+([^\s]+)[ \t]*", code[i:])
        if m and re.fullmatch(r"[\w.'«»]+", m.group(1)):
            i += m.end()
            end_last_import = i
            continue
        break
    if end_last_import < 0 or i >= n:
        return None              # no import, or nothing but the header
    return code[:i]


def warm_prefix(code: str) -> str | None:
    """The key of a warm worker: the header and the first character after it (see the module docstring)."""
    h = split_header(code)
    return None if h is None else code[:len(h) + 1]


def utf16_to_cp(line: str, col16: int) -> int:
    """LSP column (UTF-16 code units) -> Lean column (code points) on `line`."""
    units = 0
    for k, ch in enumerate(line):
        if units >= col16:
            return k
        units += 2 if ord(ch) > 0xFFFF else 1
    return len(line) + max(0, col16 - units)


SEVERITY = {1: "error", 2: "warning", 3: "information", 4: "information"}


def diagnostics_to_messages(code: str, diags: list[dict]) -> list[leancheck.LeanMessage]:
    """LSP diagnostics of the attempt -> the LeanMessage list a fresh `lean --json` gives for the same file."""
    lines = code.split("\n")

    def pos(p: dict) -> tuple[int, int]:
        ln = int(p.get("line", 0))
        text = lines[ln] if 0 <= ln < len(lines) else ""
        return ln + 1, utf16_to_cp(text, int(p.get("character", 0)))

    out = []
    for d in diags:
        if d.get("isSilent"):
            continue
        rng = d.get("fullRange") or d.get("range") or {}
        sl, sc = pos(rng.get("start") or {})
        el, ec = pos(rng.get("end") or rng.get("start") or {})
        end_l, end_c = (None, None) if (el, ec) == (sl, sc) else (el, ec)
        msg = d.get("message", "")
        if isinstance(msg, dict):              # interactive diagnostics are never requested; be safe anyway
            msg = json.dumps(msg)
        out.append(leancheck.LeanMessage(SEVERITY.get(int(d.get("severity") or 1), "error"), sl, sc, end_l, end_c,
                                         str(msg)))
    return out


def messages_to_json(msgs: list[leancheck.LeanMessage], file_name: str = "Attempt.lean") -> str:
    """`lean --json` lines for `msgs` (what `parse_lean_json` and the probe batches read)."""
    rows = []
    for m in msgs:
        rows.append(json.dumps({"severity": m.severity, "pos": {"line": m.line, "column": m.col},
                                "endPos": None if m.end_line is None else {"line": m.end_line, "column": m.end_col},
                                "keepFullRange": False, "fileName": file_name, "data": m.text, "kind": m.kind},
                               ensure_ascii=False))
    return "\n".join(rows) + ("\n" if rows else "")


def fingerprint(ws) -> tuple:
    """Changes when the workspace's toolchain or Mathlib build changes (update, switch `ws.next` -> `ws`)."""
    def st(p: Path) -> tuple:
        try:
            s = p.stat()
            return (s.st_ino, s.st_mtime_ns)
        except OSError:
            return (0, 0)
    olean = next((p / "Mathlib.olean" for p in ws.lean_path() if (p / "Mathlib.olean").exists()), ws.path / "-")
    try:                       # the directory itself: identity only (a switch renames it; files come and go)
        ino = ws.path.stat().st_ino
    except OSError:
        ino = 0
    return (ws.toolchain, str(ws.lean_bin), ino, st(ws.path / "lake-manifest.json"), st(olean))


def tree_rss_mb(pid: int) -> int:
    """Memory of a process and its descendants (MB): proportional set size (shared Mathlib .olean pages counted once
    across processes, as docs/PERFORMANCE.md measures), resident size when PSS is unreadable; 0 when unknown."""
    total, todo, seen = 0, [pid], set()
    while todo:
        p = todo.pop()
        if p in seen:
            continue
        seen.add(p)
        try:
            try:
                with open(f"/proc/{p}/smaps_rollup") as f:
                    total += next(int(ln.split()[1]) for ln in f if ln.startswith("Pss:")) * 1024
            except (OSError, StopIteration, ValueError):
                with open(f"/proc/{p}/statm") as f:
                    total += int(f.read().split()[1]) * os.sysconf("SC_PAGE_SIZE")
            for t in os.listdir(f"/proc/{p}/task"):
                with open(f"/proc/{p}/task/{t}/children") as f:
                    todo += [int(x) for x in f.read().split()]
        except (OSError, ValueError):
            continue
    return total // (1 << 20)


def _summary(msg: dict) -> str:
    p = msg.get("params") or {}
    td = p.get("textDocument") or {}
    v = p.get("version", td.get("version"))
    extra = ""
    if msg.get("method") == "textDocument/publishDiagnostics":
        extra = f" n={len(p.get('diagnostics') or [])}"
    elif msg.get("method") == "$/lean/fileProgress":
        extra = f" processing={[(x.get('range', {}).get('start', {}).get('line'), x.get('kind')) for x in p.get('processing') or []]}"
    return f"{msg.get('method', 'response')} id={msg.get('id')} v={v}{extra}"


# ---------------------------------------------------------------- JSON-RPC over stdio
class LspClient:
    """Minimal LSP client: requests with futures, diagnostics and progress per document version."""

    def __init__(self, proc: asyncio.subprocess.Process):
        self.proc = proc
        self._ids = 0
        self._pending: dict[int, asyncio.Future] = {}
        self.diags: dict[int, list[dict]] = {}
        self.done: dict[int, float] = {}            # version -> monotonic time Lean reported « nothing in progress »
        self.fatal: set[int] = set()
        self.events = asyncio.Event()               # set at every message (waiters re-check their condition)
        self.closed = asyncio.Event()
        self.stderr: deque[str] = deque(maxlen=40)
        self.initialized = False
        self.trace: list | None = None              # debugging: (time, direction, summary) of every message
        self._held: list = []                       # server requests received before `initialized`
        self._tasks = [asyncio.create_task(self._read()), asyncio.create_task(self._read_err())]

    def _write(self, obj: dict) -> None:
        if self.closed.is_set() or self.proc.stdin is None:
            raise WarmUnavailable("Lean server closed")
        b = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        if self.trace is not None:
            self.trace.append((time.monotonic(), ">", _summary(obj)))
        try:
            self.proc.stdin.write(b"Content-Length: %d\r\n\r\n" % len(b) + b)
        except (BrokenPipeError, ConnectionResetError, RuntimeError) as e:
            raise WarmUnavailable(f"Lean server closed ({e})") from e

    def notify(self, method: str, params: dict) -> None:
        self._write({"jsonrpc": "2.0", "method": method, "params": params})

    def request(self, method: str, params: dict) -> asyncio.Future:
        self._ids += 1
        fut = asyncio.get_running_loop().create_future()
        self._pending[self._ids] = fut
        self._write({"jsonrpc": "2.0", "id": self._ids, "method": method, "params": params})
        return fut

    def mark_initialized(self) -> None:
        self.initialized = True
        for rid in self._held:
            self._write({"jsonrpc": "2.0", "id": rid, "result": None})
        self._held.clear()

    async def _read(self) -> None:
        out = self.proc.stdout
        try:
            while True:
                n = -1
                while True:
                    line = await out.readline()
                    if not line:
                        return
                    line = line.strip()
                    if not line:
                        break
                    k, _, v = line.partition(b":")
                    if k.strip().lower() == b"content-length":
                        n = int(v.strip())
                if n < 0:
                    continue
                msg = json.loads(await out.readexactly(n))
                if self.trace is not None:
                    self.trace.append((time.monotonic(), "<", _summary(msg)))
                self._dispatch(msg)
                self.events.set()
        except (asyncio.IncompleteReadError, ValueError, ConnectionResetError) as e:
            log.info("warm Lean: stream ended (%s)", e)
        finally:
            self.closed.set()
            self.events.set()
            for f in self._pending.values():
                if not f.done():
                    f.set_exception(WarmUnavailable("Lean server closed"))
            self._pending.clear()

    def _dispatch(self, msg: dict) -> None:
        if "id" in msg and "method" not in msg:                     # answer to one of our requests
            f = self._pending.pop(msg["id"], None)
            if f is not None and not f.done():
                if "error" in msg:
                    f.set_exception(WarmUnavailable(f"LSP error: {msg['error']}"))
                else:
                    f.set_result(msg.get("result"))
            return
        method = msg.get("method", "")
        params = msg.get("params") or {}
        if "id" in msg:                                             # server -> client request: acknowledge
            if self.initialized:
                try:
                    self._write({"jsonrpc": "2.0", "id": msg["id"], "result": None})
                except WarmUnavailable:
                    pass
            else:                     # Lean v4.9 expects `initialized` before anything else from the client
                self._held.append(msg["id"])
            return
        if method == "textDocument/publishDiagnostics" and params.get("uri") == URI:
            v = params.get("version")
            v = int(v) if v is not None else max(self.diags, default=0)
            if params.get("isIncremental"):
                self.diags.setdefault(v, []).extend(params.get("diagnostics") or [])
            else:
                self.diags[v] = list(params.get("diagnostics") or [])
        elif method == "$/lean/fileProgress":
            td = params.get("textDocument") or {}
            v = td.get("version")
            if td.get("uri") != URI or v is None:
                return
            proc = params.get("processing") or []
            if not proc:
                self.done.setdefault(int(v), time.monotonic())
            elif any(int(p.get("kind") or 1) == 2 for p in proc):      # LeanFileProgressKind.fatalError
                self.fatal.add(int(v))

    async def _read_err(self) -> None:
        try:
            async for raw in self.proc.stderr:
                self.stderr.append(raw.decode("utf-8", "replace").rstrip()[:500])
        except (ValueError, ConnectionResetError):
            pass

    def finished(self, version: int) -> bool:
        """Lean's file worker reports a version in this order (`reportSnapshots`, v4.9 and v4.36 alike): the
        diagnostics as soon as it first waits on a command (then every new one), the « nothing in progress »
        notification at the very end, and — only when it never had to wait — one final publishDiagnostics right
        after it. So the version is complete once both its « done » and at least one publishDiagnostics arrived."""
        return version in self.done and version in self.diags

    async def wait_version(self, version: int, timeout: float) -> bool:
        """True when Lean finished elaborating `version`, False on timeout. Raises WarmUnavailable when the
        server died or reported a fatal error.

        `textDocument/waitForDiagnostics` is NOT used: on Lean v4.9 its handler loops forever on a task-pool thread
        when the request reaches the worker before the new version (measured: the first edit after opening)."""
        deadline = time.monotonic() + timeout
        while True:
            if version in self.fatal:
                raise WarmUnavailable(f"Lean reported a fatal error on version {version}")
            if self.finished(version):
                return True
            if self.closed.is_set():
                raise WarmUnavailable("Lean server closed")
            now = time.monotonic()
            if now >= deadline:
                return False
            self.events.clear()
            if self.finished(version) or version in self.fatal:
                continue
            try:
                await asyncio.wait_for(self.events.wait(), deadline - now)
            except asyncio.TimeoutError:
                pass

    async def close(self) -> None:
        for t in self._tasks:
            t.cancel()


# ---------------------------------------------------------------- one warm worker
@dataclass
class WarmOutcome:
    messages: list[leancheck.LeanMessage]
    seconds: float
    timed_out: bool = False


@dataclass
class WarmWorker:
    ws: object
    prefix: str                     # header + first character after it (warm_prefix)
    fp: tuple
    state: str = LOADING
    proc: asyncio.subprocess.Process | None = None
    client: LspClient | None = None
    version: int = 0
    started: float = field(default_factory=time.time)
    ready_at: float = 0.0
    load_seconds: float = 0.0
    last_used: float = field(default_factory=time.monotonic)
    checks: int = 0
    since_audit: int = 0
    audits: int = 0
    mismatch: int = 0
    error: str = ""
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    task: asyncio.Task | None = None

    @property
    def key(self) -> str:
        return self.ws.key

    def alive(self) -> bool:
        return self.proc is not None and self.proc.returncode is None and self.client is not None \
            and not self.client.closed.is_set()

    async def start(self) -> None:
        ws = self.ws
        t0 = time.monotonic()
        args = ["--server", "-Dserver.reportDelayMs=0"]     # no 200 ms « anti-flicker » delay (made for editors)
        argv = leansandbox.wrap(ws, [str(ws.lean_bin), *args], [])          # D28: the same boundary
        env = leansandbox.lean_env(ws)
        env["LAKE"] = "/nonexistent/lake"           # belt and braces: never `lake setup-file` (untitled URI already)
        cmd = guarded(argv[0], argv[1:])
        self.proc = await asyncio.create_subprocess_exec(
            *cmd, cwd=str(ws.path), env=env, stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE, start_new_session=True, limit=1 << 26)
        self.client = c = LspClient(self.proc)
        await asyncio.wait_for(c.request("initialize", {
            "processId": None, "rootUri": None, "capabilities": {},
            "initializationOptions": {"editDelay": 0, "hasWidgets": False}}), 120)
        c.notify("initialized", {})
        c.mark_initialized()
        self.version = 1
        c.notify("textDocument/didOpen", {"textDocument": {"uri": URI, "languageId": "lean4", "version": 1,
                                                           "text": self.prefix},
                                          "dependencyBuildMode": "never"})
        if not await c.wait_version(1, START_TIMEOUT):
            raise WarmUnavailable("header not loaded in time")
        hdr_lines = self.prefix.count("\n")
        bad = [m for m in diagnostics_to_messages(self.prefix, c.diags.get(1, []))
               if m.severity == "error" and m.line <= hdr_lines]
        if bad:
            raise WarmUnavailable("header: " + bad[0].text[:300])
        self.load_seconds = time.monotonic() - t0
        self.ready_at = time.time()
        self.last_used = time.monotonic()
        self.state = READY
        log.info("warm Lean ready for %s in %.1f s", ws.key, self.load_seconds)

    def _change(self, text: str) -> int:
        self.version += 1
        self.client.notify("textDocument/didChange", {"textDocument": {"uri": URI, "version": self.version},
                                                      "contentChanges": [{"text": text}]})
        return self.version

    async def check(self, code: str, timeout_s: float) -> WarmOutcome:
        """Elaborate `code` (same prefix) in a clean state. Caller holds `lock`."""
        if not self.alive():
            raise WarmUnavailable("Lean server not running")
        c = self.client
        self.state = BUSY
        try:
            # 1. reset to the prefix alone: no snapshot of the previous attempt can be reused
            v0 = self._change(self.prefix)
            if not await c.wait_version(v0, RESET_TIMEOUT):
                raise WarmUnavailable("reset not acknowledged")
            # 2. the attempt itself
            t0 = time.monotonic()
            v = self._change(code)
            finished = await c.wait_version(v, max(5.0, float(timeout_s)))
            secs = time.monotonic() - t0
            msgs = diagnostics_to_messages(code, c.diags.get(v, []))
            hdr_lines = self.prefix.count("\n")
            if any(m.severity == "error" and m.line <= hdr_lines for m in msgs):
                raise WarmUnavailable("error in the header")      # imports broken: never judge on that
            for old in [k for k in list(c.diags) + list(c.done) if k < v]:
                c.diags.pop(old, None)
                c.done.pop(old, None)
            self.checks += 1
            self.since_audit += 1
            return WarmOutcome(msgs, secs, timed_out=not finished)
        finally:
            self.last_used = time.monotonic()
            if self.state == BUSY:
                self.state = READY

    def kill(self, why: str = "") -> None:
        if why:
            log.info("warm Lean for %s stopped: %s", self.key, why)
        self.state = "stopped"
        if self.task is not None and not self.task.done():
            self.task.cancel()
        p = self.proc
        if p is not None and p.returncode is None:
            try:
                os.killpg(p.pid, 9)
            except (ProcessLookupError, PermissionError):
                try:
                    p.kill()
                except ProcessLookupError:
                    pass
        if self.client is not None:
            for t in self.client._tasks:
                t.cancel()

    def status(self) -> dict:
        return {"workspace": self.key, "state": self.state, "checks": self.checks,
                "load_seconds": round(self.load_seconds, 1), "since": self.ready_at or self.started,
                "idle_seconds": round(time.monotonic() - self.last_used), "error": self.error,
                "pid": self.proc.pid if self.proc else None,
                "rss_mb": tree_rss_mb(self.proc.pid) if self.proc and self.proc.returncode is None else 0}


# ---------------------------------------------------------------- the pool (one worker per workspace in use)
class WarmPool:
    def __init__(self, settings: Callable[[], object] | None = None):
        self._settings = settings
        self.workers: dict[str, WarmWorker] = {}
        self.distrusted: dict[str, str] = {}      # workspace -> why (warm and fresh disagreed): fresh only
        self.retry_at: dict[str, float] = {}
        self.failures: dict[str, str] = {}
        self.stats = {"warm": 0, "fresh_fallback": 0, "confirmed": 0, "audits": 0, "disagreements": 0,
                      "restarts": 0, "timeouts": 0}
        self._reaper: asyncio.Task | None = None

    # settings
    def enabled(self) -> bool:
        s = self._settings() if self._settings else None
        return bool(getattr(s, "lean_warm", True)) and os.environ.get("MADALEAN_LEAN_WARM", "1") != "0"

    def idle_seconds(self) -> float:
        s = self._settings() if self._settings else None
        return max(60.0, float(getattr(s, "lean_warm_idle_minutes", 10) or 10) * 60.0)

    # acquisition
    async def take(self, ws, code: str) -> WarmWorker | None:
        """A ready worker for `ws` with `code`'s prefix (header), its lock held (call `give_back`), or None (check fresh).
        Starts (or restarts) the worker in the background when needed: this check then runs fresh."""
        if not self.enabled():
            if self.workers:
                self.stop_all("disabled")
            return None
        prefix = warm_prefix(code)
        if prefix is None or ws.key in self.distrusted or ws.lean_bin is None:
            return None
        w = self.workers.get(ws.key)
        if w is not None and (w.state in ("stopped", "failed") or (w.state != LOADING and not w.alive())
                              or w.fp != fingerprint(ws)):
            self._drop(w, "workspace changed" if w.fp != fingerprint(ws) else "not running")
            if w.state != "failed":
                self.stats["restarts"] += 1
            w = None
        if w is not None and w.prefix != prefix:
            w.mismatch += 1
            if w.mismatch < MISMATCH_RESTART or w.lock.locked():
                return None
            self._drop(w, "other header")
            w = None
        if w is None:
            if time.monotonic() < self.retry_at.get(ws.key, 0.0):
                return None
            self._spawn(ws, prefix)
            return None
        w.mismatch = 0
        if w.state not in (READY, BUSY):
            return None
        try:
            await asyncio.wait_for(w.lock.acquire(), WAIT_BUSY)
        except asyncio.TimeoutError:
            return None
        if w.state != READY or not w.alive():
            w.lock.release()
            return None
        return w

    def give_back(self, w: WarmWorker) -> None:
        if w.lock.locked():
            w.lock.release()

    def _spawn(self, ws, prefix: str) -> None:
        while len(self.workers) >= MAX_WORKERS:
            idle = [x for x in self.workers.values() if not x.lock.locked() and x.state != LOADING]
            if not idle:
                return                       # all busy: this workspace stays on fresh checks for now
            self._drop(min(idle, key=lambda x: x.last_used), "another workspace needs the room")
        w = WarmWorker(ws, prefix, fingerprint(ws))
        self.workers[ws.key] = w

        async def run():
            try:
                await w.start()
                self.failures.pop(ws.key, None)
            except asyncio.CancelledError:
                w.kill()
                raise
            except Exception as e:  # noqa: BLE001 (a warm worker that cannot start only means fresh checks)
                tail = " | ".join(list(w.client.stderr)[-3:]) if w.client else ""
                w.error = f"{e}" + (f" ({tail})" if tail else "")
                log.warning("warm Lean for %s could not start: %s", ws.key, w.error)
                self.failures[ws.key] = w.error
                self.retry_at[ws.key] = time.monotonic() + RETRY_AFTER_FAILURE
                w.kill()
                w.state = "failed"
                if self.workers.get(ws.key) is w:
                    self.workers.pop(ws.key, None)
        w.task = asyncio.create_task(run())
        self._ensure_reaper()

    def _drop(self, w: WarmWorker, why: str) -> None:
        w.kill(why)
        if self.workers.get(w.key) is w:
            self.workers.pop(w.key, None)

    def discard(self, w: WarmWorker, why: str) -> None:
        """A check went wrong on this worker (timeout, cancel, crash): stop it; the next check starts a new one."""
        self._drop(w, why)

    def distrust(self, ws_key: str, why: str) -> None:
        self.stats["disagreements"] += 1
        self.distrusted[ws_key] = why
        w = self.workers.get(ws_key)
        if w is not None:
            self._drop(w, "disagreement with a fresh check")
        log.warning("warm Lean disabled for %s: %s", ws_key, why)

    def audit_due(self, w: WarmWorker) -> bool:
        if w.audits == 0 or w.since_audit >= AUDIT_EVERY:
            w.audits += 1
            w.since_audit = 0
            self.stats["audits"] += 1
            return True
        return False

    def stop_all(self, why: str = "shutdown") -> None:
        for w in list(self.workers.values()):
            self._drop(w, why)

    def reset(self) -> None:
        """Settings toggled: forget past failures and disagreements."""
        self.stop_all("settings changed")
        self.distrusted.clear()
        self.retry_at.clear()
        self.failures.clear()

    def forget_changed(self, workspaces) -> None:
        """After a workspace refresh/update: stop workers whose workspace changed or disappeared."""
        current = {w.key: w for w in workspaces or []}
        for w in list(self.workers.values()):
            ws = current.get(w.key)
            if ws is None or fingerprint(ws) != w.fp:
                self._drop(w, "workspace changed")
                self.distrusted.pop(w.key, None)

    def _ensure_reaper(self) -> None:
        if self._reaper is None or self._reaper.done():
            self._reaper = asyncio.create_task(self._reap())

    async def _reap(self) -> None:
        while self.workers:
            await asyncio.sleep(REAPER_EVERY)
            self.reap_once()

    def reap_once(self) -> None:
        now = time.monotonic()
        idle = self.idle_seconds()
        on = self.enabled()
        for w in list(self.workers.values()):
            if w.lock.locked() or w.state == LOADING:
                continue
            if not on:
                self._drop(w, "disabled")
            elif now - w.last_used > idle:
                self._drop(w, f"idle for {int(now - w.last_used)} s")
            elif w.fp != fingerprint(w.ws):
                self._drop(w, "workspace changed")
            elif not w.alive():
                self._drop(w, "exited")
            elif w.proc is not None and tree_rss_mb(w.proc.pid) > MAX_MEMORY_MB:
                self._drop(w, "memory above the cap")

    def status(self) -> dict:
        return {"enabled": self.enabled(), "idle_minutes": round(self.idle_seconds() / 60),
                "workers": [w.status() for w in self.workers.values()],
                "distrusted": dict(self.distrusted), "failures": dict(self.failures), "stats": dict(self.stats)}
