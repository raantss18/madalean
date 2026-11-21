"""Lean checks as asyncio child processes: job ids, timeout, kill on cancel, `lean` slot (2 at a time).

Port of 1.1.4 `LeanCompiler`: same command (`lean --json` with the workspace environment, never `lake`), same
infrastructure-error detection, same strict verdict (`leancheck.judge`)."""
from __future__ import annotations

import asyncio
import itertools
import json
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path

from .. import leancheck, leansandbox
from ..i18n import _
from ..logs import get
from ..slots import Slots, current_owner
from ..workspaces import Workspace
from . import guarded

log = get("lean")


@dataclass
class CompileResult:
    verdict: leancheck.Verdict
    code: str
    seconds: float
    stdout: str
    timed_out: bool = False
    cancelled: bool = False
    infra_error: str = ""      # non-empty: the check could not run (workspace broken…)
    job: int = 0

    def to_dict(self) -> dict:
        v = self.verdict
        return {"ok": v.ok, "summary": v.summary, "errors": [{"line": m.line, "col": m.col, "text": m.text,
                                                              "severity": m.severity} for m in v.errors],
                "axioms": v.axioms, "has_sorry": v.has_sorry, "reasons": v.reasons, "seconds": round(self.seconds, 2),
                "timed_out": self.timed_out, "cancelled": self.cancelled, "infra_error": self.infra_error,
                # a statement (with `sorry`) is valid when Lean reports no error (1.1.4 formalizer rule)
                "statement_ok": not v.errors and not self.timed_out and not self.infra_error}


def workspace_info(ws: Workspace | None) -> dict:
    """{workspace, lean, mathlib}: versions written in the verification stamp."""
    if ws is None:
        return {}
    info = {"workspace": ws.key, "lean": ws.toolchain.split(":")[-1] if ws.toolchain else "", "mathlib": ""}
    try:
        man = json.loads((ws.path / "lake-manifest.json").read_text(encoding="utf-8"))
        for p in man.get("packages", []):
            if p.get("name") == "mathlib":
                info["mathlib"] = (p.get("inputRev") or "") + (" @ " if p.get("inputRev") else "") + (p.get("rev") or "")[:12]
                break
    except (OSError, ValueError, AttributeError):
        pass
    if not info["mathlib"] and _is_mathlib_checkout(ws.path):
        # the workspace IS a Mathlib checkout (lean-prover49: Goedel's Mathlib fork): its manifest lists only
        # Mathlib's own dependencies; the revision is the checkout's git HEAD (read from .git, no `git` process)
        rev = git_head(ws.path)
        info["mathlib"] = (rev[:12] + " (checkout)") if rev else ""
    return info


def _is_mathlib_checkout(path: Path) -> bool:
    try:
        lf = (path / "lakefile.lean").read_text(encoding="utf-8", errors="replace")
    except OSError:
        lf = ""
    try:
        lf += (path / "lakefile.toml").read_text(encoding="utf-8", errors="replace")
    except OSError:
        pass
    return bool(re.search(r"(?m)^\s*package\s+«?mathlib»?\b|^\s*name\s*=\s*\"mathlib\"", lf)) \
        and (path / "Mathlib.lean").is_file()


def git_head(path: Path) -> str:
    """Commit of HEAD of the git checkout at `path` (detached HEAD, loose ref or packed-refs); "" when unknown."""
    g = path / ".git"
    try:
        if g.is_file():                       # worktree / submodule: « gitdir: … »
            t = g.read_text(encoding="utf-8").strip()
            if t.startswith("gitdir:"):
                g = (path / t.split(":", 1)[1].strip()).resolve()
        head = (g / "HEAD").read_text(encoding="utf-8").strip()
        if not head.startswith("ref:"):
            return head if all(ch in "0123456789abcdef" for ch in head.lower()) and len(head) >= 7 else ""
        ref = head.split(":", 1)[1].strip()
        loose = g / ref
        if loose.is_file():
            return loose.read_text(encoding="utf-8").strip()
        for line in (g / "packed-refs").read_text(encoding="utf-8").splitlines():
            parts = line.split()
            if len(parts) == 2 and parts[1] == ref:
                return parts[0]
    except OSError:
        pass
    return ""


class LeanRunner:
    def __init__(self, slots: Slots, tmp_dir: Path):
        self.slots = slots
        self.tmp_dir = Path(tmp_dir)
        self._ids = itertools.count(1)
        self.procs: dict[int, asyncio.subprocess.Process] = {}
        self.running: dict[int, dict] = {}

    async def problems(self, ws: Workspace) -> list[str]:
        return await asyncio.to_thread(ws.check)

    async def check(self, code: str, ws: Workspace, timeout_s: int = 180, strict_name: str | None = None,
                    owner: str | None = None) -> CompileResult:
        """Compile `code` (with the axiom probe already appended when `strict_name` is given)."""
        job = next(self._ids)
        owner = owner or current_owner()
        risks = leancheck.exec_risks(code.rsplit("#print axioms", 1)[0] if strict_name else code)
        if risks:          # never compile code that could run on the host (DECISIONS D28), whoever wrote it
            why = _("Refusé avant compilation : {why}.").format(why=", ".join(risks))
            # a positioned error too: every caller that looks at `errors` (statement checks…) must see a failure
            v = leancheck.Verdict(False, why, errors=[leancheck.LeanMessage("error", 1, 0, None, None, why)],
                                  reasons=risks)
            return CompileResult(v, code, 0.0, "", job=job)
        problems = await asyncio.to_thread(ws.check)
        if problems:
            return CompileResult(leancheck.Verdict(False, problems[0]), code, 0.0, "", infra_error=problems[0], job=job)
        async with self.slots.hold("lean", owner):
            return await self._run(job, code, ws, timeout_s, strict_name)

    async def _run(self, job: int, code: str, ws: Workspace, timeout_s: int, strict_name: str | None) -> CompileResult:
        f = self.tmp_dir / f"check_{os.getpid()}_{job}_{int(time.time() * 1000)}.lean"
        await asyncio.to_thread(self._write, f, code)
        t0 = time.monotonic()
        argv = leansandbox.wrap(ws, [str(ws.lean_bin), "--json", str(f)], [f])     # D28: the boundary
        cmd = guarded(argv[0], argv[1:])
        try:
            proc = await asyncio.create_subprocess_exec(*cmd, cwd=str(ws.path), env=leansandbox.lean_env(ws),
                                                        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
                                                        start_new_session=True)
        except OSError as e:
            await asyncio.to_thread(self._unlink, f)
            v = leancheck.Verdict(False, _("Lean n'a pas pu démarrer."))
            return CompileResult(v, code, 0.0, "", infra_error=str(e), job=job)
        self.procs[job] = proc
        self.running[job] = {"pid": proc.pid, "workspace": ws.key, "started": time.time()}
        timed_out = False
        try:
            try:
                out_b, err_b = await asyncio.wait_for(proc.communicate(), timeout=max(5, timeout_s))
            except asyncio.TimeoutError:
                timed_out = True
                self._kill(proc)
                out_b, err_b = await proc.communicate()
        except asyncio.CancelledError:
            self._kill(proc)
            try:
                await asyncio.shield(proc.wait())
            except BaseException:  # noqa: BLE001
                pass
            raise
        finally:
            self.procs.pop(job, None)
            self.running.pop(job, None)
            await asyncio.shield(asyncio.to_thread(self._unlink, f))
        secs = time.monotonic() - t0
        out = out_b.decode("utf-8", "replace")
        err = err_b.decode("utf-8", "replace")
        if timed_out:
            v = leancheck.Verdict(False, _("Lean a dépassé le délai ({s} s).").format(s=int(secs)),
                                  feedback_en="Compilation timed out. Use simpler, faster tactics (avoid heavy nlinarith/simp searches).")
            return CompileResult(v, code, secs, out, timed_out=True, job=job)
        return await asyncio.to_thread(self._verdict, job, code, out, err, proc.returncode, secs, strict_name)

    @staticmethod
    def _verdict(job: int, code: str, out: str, err: str, rc: int | None, secs: float,
                 strict_name: str | None) -> CompileResult:
        msgs = leancheck.parse_lean_json(out)
        infra = ""
        if any("object file" in m.text and "does not exist" in m.text for m in msgs) or (
                "unknown package" in out and "Mathlib" in out):
            infra = _("Mathlib introuvable ou non compilé dans cet espace.")
        if not msgs and rc != 0:
            infra = (err or out).strip()[-2000:] or f"exit code {rc}"
        v = leancheck.judge(code, msgs, strict_name, rc)
        return CompileResult(v, code, secs, out + err, infra_error=infra, job=job)

    @staticmethod
    def _write(f: Path, code: str) -> None:
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(code, encoding="utf-8")

    @staticmethod
    def _unlink(f: Path) -> None:
        try:
            f.unlink()
        except OSError:
            pass

    @staticmethod
    def _kill(proc: asyncio.subprocess.Process) -> None:
        try:
            os.killpg(proc.pid, 9)
        except (ProcessLookupError, PermissionError):
            try:
                proc.kill()
            except ProcessLookupError:
                pass

    def kill_all(self) -> None:
        for p in list(self.procs.values()):
            self._kill(p)

