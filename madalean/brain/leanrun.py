"""Minimal Lean checker (strict verdict of leancheck.judge) for the brain's self-test and tests. The server has its
own (pooled, sandboxed) checker; this one only runs `lean --json` once per call."""
from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

from .. import leancheck, leansandbox


async def check_with_lean(ws, code: str, timeout: float = 400) -> dict:
    """{ok, feedback, summary} for `code` compiled in workspace `ws` (madalean.workspaces.Workspace)."""
    try:
        name = leancheck.theorem_name(code)
    except leancheck.StatementError as e:
        return {"ok": False, "feedback": str(e), "summary": str(e)}
    probe = leancheck.with_axiom_probe(code, name)
    risks = leancheck.exec_risks(code)
    if risks:
        return {"ok": False, "feedback": ", ".join(risks), "summary": ", ".join(risks)}
    with tempfile.TemporaryDirectory(prefix="madalean-check-") as d:
        f = Path(d) / "Check.lean"
        f.write_text(probe, encoding="utf-8")
        argv = leansandbox.wrap(ws, [str(ws.lean_bin), "--json", str(f)], [f])
        proc = await asyncio.create_subprocess_exec(
            *argv, cwd=str(ws.path), env=leansandbox.lean_env(ws),
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        try:
            out, _err = await asyncio.wait_for(proc.communicate(), timeout)
        except (asyncio.TimeoutError, asyncio.CancelledError):
            proc.kill()
            await proc.wait()
            raise
    msgs = leancheck.parse_lean_json(out.decode("utf-8", "replace"))
    v = leancheck.judge(probe, msgs, name, proc.returncode)
    fb = "" if v.ok else leancheck.errors_for_feedback(probe, v)
    return {"ok": v.ok, "feedback": fb, "summary": v.summary}


def workspace(key: str):
    from .rag import default_resolve
    w = default_resolve(key)
    if w is None or w.check():
        return None
    return w
