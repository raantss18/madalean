"""Shared builders for the server tests (contexts with fakes, running servers, waiting for jobs)."""
from __future__ import annotations

import asyncio
import contextlib
import time
from pathlib import Path

import aiohttp

from madalean.brain.fake import FakeBrain, FakeLean, FakeLocal, FakeRetriever
from madalean.context import ServerContext
from madalean.paths import Paths


def make_ctx(tmp: Path, ws=None, brain=None, fake_lean: bool = False, caps=None, swap: float = 0.0, delay: float = 0.0,
             lean_seconds: float = 0.05, legacy_dir=None, **kw) -> ServerContext:
    from madalean.workspaces import Workspace
    paths = Paths(tmp / "config", tmp / "cache")
    if ws is None:
        ws = Workspace("demo", "Demo", tmp / "nows", "leanprover/lean4:v4.9.0-rc1", True)
        fake_lean = True
    ctx = ServerContext(paths, workspaces=[ws], caps=caps, legacy_dir=legacy_dir, jupyter_root=tmp / "notebooks",
                        use_keyring=False, **kw)
    ctx.local = FakeLocal(ctx.slots, swap)
    if fake_lean:
        ctx.lean = FakeLean(ctx.slots, lean_seconds)
    ctx.brain = brain or FakeBrain(local=ctx.local, delay=delay)
    if getattr(ctx.brain, "local", "x") is None:
        ctx.brain.local = ctx.local
    ctx.retriever = FakeRetriever()
    ctx.brain_kind = "fake"
    ctx.settings.workspace = ws.key
    ctx.settings.mode = "local"            # tests describe the local (Goedel) path unless they set a mode themselves
    # the statement check and the Mathlib-first search (S-K) add model calls and Lean probes: tests of the older
    # chain keep their exact sequences; tests/test_statement_check.py turns them on
    ctx.settings.statement_check = False
    ctx.settings.mathlib_first = False
    ctx.settings.certificates = False    # S-AT: tests/test_certificates.py turns it on
    ctx.settings.literature = False      # S-AX: never a network search from a test; tests/test_literature.py turns it on
    return ctx


async def started(ctx: ServerContext) -> ServerContext:
    key, mode = ctx.settings.workspace, ctx.settings.mode
    sk = (ctx.settings.statement_check, ctx.settings.mathlib_first, ctx.settings.certificates,
          ctx.settings.literature)
    await ctx.start()
    ctx.settings.workspace, ctx.settings.mode = key, mode
    (ctx.settings.statement_check, ctx.settings.mathlib_first, ctx.settings.certificates,
     ctx.settings.literature) = sk
    return ctx


async def wait_job(ctx: ServerContext, job_id: str, timeout: float = 300) -> dict:
    t0 = time.monotonic()
    while time.monotonic() - t0 < timeout:
        j = ctx.orchestrator.jobs.get(job_id)
        if j is not None and not j.active and job_id in ctx.orchestrator.tasks and ctx.orchestrator.tasks[job_id].done():
            return j.to_dict()
        await asyncio.sleep(0.05)
    raise TimeoutError(job_id)


async def wait_idle(ctx: ServerContext, timeout: float = 300) -> None:
    t0 = time.monotonic()
    while time.monotonic() - t0 < timeout:
        if not any(not t.done() for t in ctx.orchestrator.tasks.values()):
            return
        await asyncio.sleep(0.05)
    raise TimeoutError("jobs still running")


@contextlib.asynccontextmanager
async def running(ctx: ServerContext, static_dir: Path | None = None):
    """Server on random ports. Yields (server, local_url, remote_url)."""
    from madalean.server.app import Server
    key = ctx.settings.workspace
    srv = Server(ctx, 0, 0, static_dir)
    await srv.start()
    ctx.settings.workspace = key
    try:
        yield srv, f"http://127.0.0.1:{srv.ports['local']}", f"http://127.0.0.1:{srv.ports['remote']}"
    finally:
        await srv.stop()


def session(**kw) -> aiohttp.ClientSession:
    return aiohttp.ClientSession(trust_env=False, **kw)
