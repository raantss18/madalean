"""Orchestrator: parallel jobs across dossiers, resource slots (gpu=1, online=3, lean=2), cancel, priorities."""
from __future__ import annotations

import asyncio
import time

import pytest

from madalean.brain.fake import FakeBrain
from madalean.orchestrator import DossierBusy
from madalean.server.routes_work import create_dossier
from madalean.slots import Slots
from helpers import make_ctx, started, wait_idle

PROBLEM = "Montrer que la somme de deux entiers pairs est paire."


class Tracker:
    """Wraps FakeLean/FakeBrain timings to record intervals of activity."""

    def __init__(self):
        self.intervals: list[tuple[str, float, float]] = []


async def test_jobs_of_different_dossiers_really_overlap(tmp_path):
    ctx = await started(make_ctx(tmp_path, delay=0.01, lean_seconds=0.6))
    ctx.settings.mode = "online"                       # 3 online slots: model calls of several jobs at once
    t0 = time.monotonic()
    jobs = [(await create_dossier(ctx, {"problem": PROBLEM}))[1] for _i in range(3)]
    await wait_idle(ctx)
    total = time.monotonic() - t0
    assert all(j.state == "done" for j in jobs), [(j.state, j.error) for j in jobs]
    spans = [(j.started, j.ended) for j in jobs]
    assert max(s for s, _e in spans) < min(e for _s, e in spans)          # every pair of jobs overlapped
    one = max(e - s for s, e in spans)
    assert total < 2.2 * one                                               # not sequential (would be ~3x)
    assert ctx.brain.max_active >= 2 and ctx.slots.max_seen["online"] <= 3
    assert ctx.slots.max_seen["lean"] == 2                                 # two Lean checks at once, never three
    await ctx.stop()


async def test_gpu_slot_is_never_double_booked(tmp_path):
    ctx = await started(make_ctx(tmp_path, delay=0.005, lean_seconds=0.2, swap=0.05))
    assert ctx.settings.mode == "local"
    holders_seen = []
    orig = ctx.slots._grant

    def grant(resource, owner):
        orig(resource, owner)
        if resource == "gpu":
            holders_seen.append(list(ctx.slots.holders["gpu"]))
    ctx.slots._grant = grant
    jobs = [(await create_dossier(ctx, {"problem": PROBLEM}))[1] for _i in range(4)]
    await wait_idle(ctx)
    assert all(j.state == "done" for j in jobs), [(j.state, j.error, j.summary) for j in jobs]
    assert ctx.slots.max_seen["gpu"] == 1 and all(len(h) == 1 for h in holders_seen)
    assert len({h[0] for h in holders_seen}) == 4                         # every job got the GPU in turn
    assert ctx.local.loads >= 3                                            # models were swapped between roles
    assert ctx.slots.holders["gpu"] == [] and ctx.local._holder is None   # everything released
    await ctx.stop()


async def test_cancel_running_and_waiting_jobs(tmp_path):
    ctx = await started(make_ctx(tmp_path, delay=0.05, lean_seconds=0.5))
    a = (await create_dossier(ctx, {"problem": PROBLEM}))[1]
    b = (await create_dossier(ctx, {"problem": PROBLEM}))[1]
    for _i in range(200):
        if b.waiting == "gpu":
            break
        await asyncio.sleep(0.01)
    assert b.state == "queued" and b.waiting == "gpu"                     # waiting for the slot a holds
    assert await ctx.orchestrator.cancel(b.id)
    assert b.state == "cancelled" and "gpu" in ctx.slots.caps and ctx.slots.usage()["gpu"]["waiting"] == 0
    assert await ctx.orchestrator.cancel(a.id)
    assert a.state == "cancelled"
    d = ctx.repo.get(a.dossier_id)
    assert d.events[-1].kind == "info" and d.status in ("stopped", "draft")
    assert ctx.slots.holders == {"gpu": [], "online": [], "lean": []}
    hist = await ctx.orchestrator.history_for(a.dossier_id)
    assert hist and hist[-1].state == "cancelled"
    await ctx.stop()


async def test_one_active_job_per_dossier(tmp_path):
    ctx = await started(make_ctx(tmp_path, delay=0.02))
    d, j = await create_dossier(ctx, {"problem": PROBLEM})
    with pytest.raises(DossierBusy):
        ctx.orchestrator.submit(d.id, [{"stage": "proof"}])
    await wait_idle(ctx)
    j2 = ctx.orchestrator.submit(d.id, [{"stage": "explanation"}])
    await wait_idle(ctx)
    assert j.state == "done" and j2.state == "done" and len(d.explanations) == 2
    await ctx.stop()


async def test_user_jobs_are_served_before_automatic_ones():
    slots = Slots({"gpu": 1, "online": 3, "lean": 2})
    order = []
    await slots.acquire("gpu", "holder", 0)

    async def want(owner, prio):
        await slots.acquire("gpu", owner, prio)
        order.append(owner)
        await asyncio.sleep(0.01)
        slots.release("gpu", owner)
    tasks = [asyncio.create_task(want("auto1", 1)), asyncio.create_task(want("auto2", 1))]
    await asyncio.sleep(0.01)
    tasks.append(asyncio.create_task(want("user1", 0)))
    await asyncio.sleep(0.01)
    slots.release("gpu", "holder")
    await asyncio.gather(*tasks)
    assert order == ["user1", "auto1", "auto2"]                          # priority, then FIFO
    assert slots.max_seen["gpu"] == 1


async def test_failed_model_reports_a_clear_error(tmp_path):
    from madalean.brain.api import BrainError
    brain = FakeBrain(lambda role, m, b: BrainError("no_model", "nothing"))
    ctx = await started(make_ctx(tmp_path, brain=brain))
    d, j = await create_dossier(ctx, {"statement": "theorem t : 1 = 1 := by sorry"})
    await wait_idle(ctx)
    assert j.state == "failed" and j.error == "no_model" and d.events[-1].kind == "error"
    assert "modèle nécessaire" in d.events[-1].text
    await ctx.stop()


async def test_agent_result_is_always_rechecked(tmp_path, monkeypatch):
    """Strategy agent: the code returned by prove_with_agent is re-checked by the server; a bad one is refused and
    (strategy auto) the goedel loop takes over."""
    from madalean.pipeline import runner
    calls = []

    def fake_agent(code):
        async def prove_with_agent(brain, retriever, *, statement, workspace_key, check, library_search, hint,
                                   on_chunk, mode, max_steps, max_seconds):
            calls.append((statement, mode, max_steps))
            r = await check(code)                       # the agent may call the server's checker as a tool
            return {"code": code, "model": "fake:agent", "steps": 3, "transcript": [{"content": str(r["ok"])}]}
        return prove_with_agent
    good = "theorem t (a b : ℕ) (ha : Even a) (hb : Even b) : Even (a + b) := by\n  exact Even.add ha hb"
    monkeypatch.setattr(runner, "_agent_fn", lambda: fake_agent(good.replace("theorem t", "theorem x")))
    ctx = await started(make_ctx(tmp_path))
    ctx.settings.mode = "online"
    d, j = await create_dossier(ctx, {"statement": good.split(":= by")[0] + ":= by sorry", "start": False})
    job = ctx.orchestrator.submit(d.id, [{"stage": "proof"}], strategy="agent")
    await wait_idle(ctx)
    assert job.state == "done" and d.proof_is_current and d.proofs[-1].model == "fake:agent"
    assert [a.kind for a in job.attempts] == ["agent"] and job.attempts[0].status == "accepted"
    assert d.proofs[-1].meta["strategy"] == "agent" and calls[0][1] == "online"
    # a proof the server's Lean check refuses is never accepted; with strategy auto, goedel takes over
    monkeypatch.setattr(runner, "_agent_fn", lambda: fake_agent(good.replace("Even.add ha hb", "no_such ha hb")))
    job2 = ctx.orchestrator.submit(d.id, [{"stage": "proof"}], strategy="auto")
    await wait_idle(ctx)
    kinds = [(a.kind, a.status) for a in job2.attempts]
    assert kinds[0] == ("agent", "rejected") and kinds[-1][1] == "accepted" and kinds[-1][0] != "agent"
    assert d.proofs[-1].meta["strategy"] == "goedel"
    await ctx.stop()
