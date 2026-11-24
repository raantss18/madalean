"""Leaderboard (scoring, prior, decay, persistence, router bonus, explanations) and the proof tournament (S-J):
termination under permanent failure and flapping providers, the winner cancels the others, time cap, cancellation,
paid-model exclusion, slot discipline, and « the winner leads round 0 next time » — fake brain + fake Lean."""
from __future__ import annotations

import asyncio
import json
import os
import time

import pytest

from madalean.brain import leaderboard as lbm
from madalean.brain.api import ModelRef
from madalean.brain.catalogue import Catalogue, Model
from madalean.brain.fake import FakeBrain
from madalean.brain.leaderboard import Leaderboard, domain_of
from madalean.brain.router import rank
from madalean.brain.state import States
from madalean.pipeline import runner
from madalean.pipeline.tournament import Config, Contestant, Outcome, Tournament, estimated_cost
from madalean.server.routes_work import create_dossier
from helpers import make_ctx, running, session, started, wait_idle

STMT = "theorem t (a b : ℕ) (ha : Even a) (hb : Even b) : Even (a + b) := by sorry"


# ---------------------------------------------------------------- leaderboard
def test_prior_makes_nine_of_ten_beat_one_of_one(tmp_path):
    lb = Leaderboard(tmp_path / "lb.json")
    lb.record("p:lucky", "prove", ok=True)
    for i in range(10):
        lb.record("p:steady", "prove", ok=i != 0)
    assert lb.score("p:steady", "prove") > lb.score("p:lucky", "prove") > lb.score("p:unknown", "prove") - 1e-9
    for _ in range(5):
        lb.record("p:bad", "prove", ok=False)
    assert lb.score("p:bad", "prove") < lbm.PRIOR_P
    assert lb.top("prove", k=2) == ["p:steady", "p:lucky"]


def test_efficiency_and_pauses_are_penalised(tmp_path):
    lb = Leaderboard(tmp_path / "lb.json")
    for _ in range(6):
        lb.record("p:fast", "prove", ok=True, attempts=1)
        lb.record("p:slow", "prove", ok=True, attempts=4)
        lb.record("p:flaky", "prove", ok=True, attempts=1)
        lb.record("p:flaky", "prove", ok=False, unavailable=True)
    assert lb.score("p:fast", "prove") > lb.score("p:slow", "prove")
    assert lb.score("p:fast", "prove") > lb.score("p:flaky", "prove")
    e = lb.entry("p:flaky", "prove")
    assert e.total == 6 and e.pauses == pytest.approx(6, rel=1e-3)     # a pause is not a mathematical failure


def test_decay_lets_old_results_fade(tmp_path, monkeypatch):
    t = [1_000_000.0]
    monkeypatch.setattr(lbm, "now", lambda: t[0])
    lb = Leaderboard(tmp_path / "lb.json")
    for _ in range(8):
        lb.record("p:old", "prove", ok=True)
    fresh = lb.score("p:old", "prove")
    t[0] += 4 * lbm.HALF_LIFE
    assert lb.entry("p:old", "prove").n == pytest.approx(0.5, rel=1e-6)
    assert lbm.PRIOR_P < lb.score("p:old", "prove") < fresh
    assert lb.entry("p:old", "prove").total == 8                         # raw counts kept for display


def test_persistence_is_private_bounded_and_survives_corruption(tmp_path, monkeypatch):
    p = tmp_path / "cfg" / "brain-leaderboard.json"
    lb = Leaderboard(p)
    lb.record("p:a", "prove", "algebra", ok=True, attempts=2, lean_errors=1, seconds=30)
    assert os.stat(p).st_mode & 0o777 == 0o600
    lb2 = Leaderboard(p)
    assert lb2.entry("p:a", "prove", "algebra").total_ok == 1 and lb2.entry("p:a", "prove").total == 1
    rows = lb2.table()
    assert {(r["model"], r["task"], r["domain"]) for r in rows} == {("p:a", "prove", ""), ("p:a", "prove", "algebra")}
    assert rows[0]["mean_attempts"] == 2.0 and rows[0]["mean_seconds"] == 30.0
    p.write_text("{not json")
    assert Leaderboard(p).entries == {}
    p.write_text(json.dumps({"entries": {"x|prove": {"n": "nan?"}, "nobar": {}, "y|prove": {"n": 1, "ok": 1}}}))
    assert list(Leaderboard(p).entries) == ["y|prove"]
    monkeypatch.setattr(lbm, "MAX_ENTRIES", 10)
    for i in range(30):
        lb.record(f"p:m{i}", "explain", ok=True)
    assert len(json.loads(p.read_text())["entries"]) <= 10
    lb.reset()
    assert Leaderboard(p).entries == {}


def test_domains():
    assert domain_of("theorem t (n : ℤ) : Even (n ^ 2) → Even n := by sorry") == "number_theory"
    assert domain_of("theorem t (A : Matrix (Fin 2) (Fin 2) ℝ) : A.det = A.det := by sorry") == "linear_algebra"
    assert domain_of("theorem t (f : ℝ → ℝ) (h : Continuous f) : True := by sorry") == "analysis"
    assert domain_of("theorem t (p : Polynomial ℚ) : p = p := by sorry") == "algebra"
    assert domain_of("Montrer qu'un polynôme cubique a une racine réelle") == "algebra"
    assert domain_of("theorem t : True := by trivial") == "other"


def test_router_bonus_and_explanations(tmp_path):
    cat = Catalogue(1.0, [], [Model("p", "strong", "Strong", quality={"math": 0.8, "code": 0.8, "reasoning": 0.8}),
                              Model("p", "small", "Small", quality={"math": 0.6, "code": 0.6,
                                                                           "reasoning": 0.6})])
    states = States(tmp_path / "st.json")
    lb = Leaderboard(tmp_path / "lb.json")
    plain = rank(cat, states, "prove", leaderboard=lb)
    assert plain[0].model.model_id == "strong" and "prouvé" not in plain[0].why
    for i in range(9):
        lb.record("p:small", "prove", "linear_algebra", ok=i < 7, attempts=2)
    ranked = rank(cat, states, "prove", leaderboard=lb, domain="linear_algebra")
    assert ranked[0].model.model_id == "small"
    assert "a prouvé 7/9 problèmes d'algèbre linéaire ici" in ranked[0].why
    en = rank(cat, states, "prove", leaderboard=lb, domain="linear_algebra", lang="en")[0].why
    assert "proved 7/9 linear algebra problems here" in en
    # another role is not affected by proof results; an unseen domain falls back to the general row
    assert rank(cat, states, "explain", leaderboard=lb)[0].model.model_id == "strong"
    assert "prouvé 7/9 problèmes ici" in rank(cat, states, "prove", leaderboard=lb, domain="analysis")[0].why


def test_engine_pool_and_only(tmp_path):
    from madalean.brain.engine import MadaleanBrain
    b = MadaleanBrain(tmp_path, None, lambda p: None, {"refresh_catalogue": False, "ollama": False})
    pool = b.pool("prove", "online")
    assert len(pool) > len(b.candidates("prove", "online")) and not any(r.paid or r.local for r in pool)
    k = pool[min(5, len(pool) - 1)].key
    before = [r.key for r in pool].index(k)
    for _ in range(9):
        b.leaderboard.record(k, "prove", "number_theory", ok=True)
    after = [r.key for r in b.pool("prove", "online", domain="number_theory")].index(k)
    assert after < before
    assert [r.key for r in b.pool("prove", "online")].index(k) <= after + 1        # general row counts too
    b.leaderboard.reset()
    for _ in range(9):
        b.leaderboard.record(k, "prove", ok=True)
    assert "prouvé 9/9" in next(w["why"] for w in b.explain("prove", "online") if w["model"] == k) or \
        k not in [w["model"] for w in b.explain("prove", "online")]


def test_estimated_cost():
    assert estimated_cost("anthropic:claude-opus-5-5", 1_000_000) == pytest.approx(0.85 * 4 + 0.15 * 20)
    assert estimated_cost("free:model", 1000) is None


# ---------------------------------------------------------------- tournament (pure logic)
def pool_of(n: int, prefix: str = "m") -> list[Contestant]:
    return [Contestant(f"{prefix}:{i}", f"{prefix}{i}") for i in range(n)]


async def test_terminates_when_every_model_always_fails():
    calls: list[tuple[str, int, int]] = []

    async def run(c, k, n, deadline):
        calls.append((c.key, k, n))
        await asyncio.sleep(0)
        return Outcome(c, k, attempts=n, lean_errors=n)
    recorded = []
    t = Tournament(Config(), candidates=lambda: pool_of(40), run=run, record=recorded.append)
    res = await asyncio.wait_for(t.run(), 5)
    assert res.winner is None and res.stop in ("rounds", "attempts")
    keys = [c[0] for c in calls]
    assert len(keys) == len(set(keys))                                   # each model at most once per task
    assert sum(n for _k, _r, n in calls) <= 16 and max(r for _k, r, _n in calls) <= 3
    assert calls[0] == ("m:0", 0, 4)                                     # round 0: the best, 4 attempts
    assert {r for _k, r, _n in calls} == {0, 1, 2, 3} and len(recorded) == len(calls)


async def test_terminates_with_flapping_providers_and_an_endless_pool():
    """Models alternate between 429 (cannot run) and errors; the candidate list never runs out (new names each
    call): the tournament still stops, by its round cap."""
    counter = iter(range(10 ** 6))
    seen = []

    def endless():
        return [Contestant(f"x:{next(counter)}") for _ in range(5)]

    async def run(c, k, n, deadline):
        seen.append(c.key)
        if len(seen) % 2:
            return Outcome(c, k, attempts=1, unavailable=True, error="HTTP 429")
        raise RuntimeError("HTTP 500 upstream")
    res = await asyncio.wait_for(Tournament(Config(), candidates=endless, run=run).run(), 5)
    assert res.winner is None and res.rounds <= 4 and len(seen) <= 2 + 3 * (3 + 2 * 3)
    assert len(seen) == len(set(seen))
    assert all(o.unavailable for o in res.outcomes)


async def test_round0_second_best_replaces_an_unavailable_best_and_wins():
    async def run(c, k, n, deadline):
        if c.key == "m:0":
            return Outcome(c, k, attempts=1, unavailable=True)
        return Outcome(c, k, ok=True, attempts=1, result="proof")
    res = await Tournament(Config(), candidates=lambda: pool_of(5), run=run).run()
    assert res.stop == "won" and res.winner.contestant.key == "m:1" and res.winner.round == 0 and res.rounds == 1


async def test_first_verified_proof_wins_and_cancels_the_others():
    cancelled, started_ = [], []

    async def run(c, k, n, deadline):
        if k == 0:
            return Outcome(c, k, attempts=n)                             # the best fails: a race starts
        started_.append(c.key)
        try:
            await asyncio.sleep(0.2 if c.key == "m:2" else 30)
        except asyncio.CancelledError:
            cancelled.append(c.key)
            raise
        return Outcome(c, k, ok=True, attempts=1, result="proof")
    t0 = time.monotonic()
    res = await Tournament(Config(contestants=3), candidates=lambda: pool_of(6), run=run).run()
    assert time.monotonic() - t0 < 5
    assert res.winner.contestant.key == "m:2" and res.winner.round == 1
    assert started_ == ["m:1", "m:2", "m:3"] and sorted(cancelled) == ["m:1", "m:3"]
    assert sorted(o.contestant.key for o in res.outcomes if o.cancelled) == ["m:1", "m:3"]


async def test_wall_time_cap_stops_contestants_that_never_answer():
    async def run(c, k, n, deadline):
        await asyncio.sleep(3600)
    t0 = time.monotonic()
    res = await asyncio.wait_for(Tournament(Config(max_minutes=0.03), candidates=lambda: pool_of(9),
                                            run=run).run(), 20)
    assert time.monotonic() - t0 < 8 and res.winner is None and res.stop == "time"


async def test_cancel_mid_race_cancels_every_contestant():
    live: set[str] = set()

    async def run(c, k, n, deadline):
        if k == 0:
            return Outcome(c, k, attempts=n)
        live.add(c.key)
        try:
            await asyncio.sleep(3600)
        finally:
            live.discard(c.key)
    task = asyncio.create_task(Tournament(Config(), candidates=lambda: pool_of(6), run=run).run())
    for _ in range(100):
        await asyncio.sleep(0.01)
        if len(live) == 3:
            break
    assert len(live) == 3
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert not live


async def test_goedel_is_one_contestant_and_online_ones_respect_the_slots():
    plan = []

    async def run(c, k, n, deadline):
        plan.append((k, c.kind, n))
        return Outcome(c, k, attempts=n)
    cands = pool_of(10) + [Contestant("local:goedel.gguf", "Goedel", "goedel", local=True)]
    await Tournament(Config(contestants=3), candidates=lambda: cands, run=run, online_slots=1).run()
    r1 = [p for p in plan if p[0] == 1]
    assert [kind for _k, kind, _n in r1] == ["agent", "goedel"]            # 1 online slot + the local prover
    assert r1[1][2] == 4                                                   # Goedel gets its attempts
    assert sum(1 for p in plan if p[1] == "goedel") == 1


# ---------------------------------------------------------------- tournament in the pipeline (fake brain + Lean)
GOOD = "theorem t (a b : ℕ) (ha : Even a) (hb : Even b) : Even (a + b) := by\n  exact Even.add ha hb"
BAD = GOOD.replace("Even.add ha hb", "no_such ha hb")


class PoolBrain(FakeBrain):
    """A fake brain with several online models (one paid), as the real router would offer them."""
    MODELS = [ModelRef("free", "a", "A"), ModelRef("free", "b", "B"), ModelRef("paid", "opus", "Opus", paid=True),
              ModelRef("free", "rate", "Rate-limited"), ModelRef("free", "winner", "Winner"),
              ModelRef("free", "c", "C"), ModelRef("free", "d", "D")]

    def __init__(self, **kw):
        super().__init__(**kw)
        self.settings = {"paid_first": False, "agent_max_tokens": 600_000}

    def pool(self, role, mode="auto", *, domain=None):
        from madalean.pipeline.tournament import leaderboard_of  # noqa: F401  (ordering is the test's business)
        lb = getattr(self, "lb", None)
        refs = [m for m in self.MODELS if self.settings.get("paid_first") or not m.paid]
        if lb is not None:
            refs.sort(key=lambda r: -lb.score(r.key, "prove"))
        return refs


def scripted_agent(log: list, delays: dict | None = None):
    delays = delays or {}

    async def prove_with_agent(brain, retriever, *, statement, workspace_key, check, library_search, hint, on_chunk,
                               mode, max_steps, max_seconds, only=None):
        log.append(only)
        await asyncio.sleep(delays.get(only, 0.05))
        if only == "free:rate":
            return {"code": None, "model": None, "steps": 0, "finish": "error", "checks": 0,
                    "transcript": [{"type": "model_error", "model": only, "reason": "HTTP 429"}]}
        if only == "free:winner" or (only == "paid:opus"):
            r = await check(GOOD)
            return {"code": GOOD if r["ok"] else None, "model": only, "steps": 3, "finish": "proved", "checks": 1,
                    "transcript": []}
        await check(BAD)
        return {"code": None, "model": only, "steps": 5, "finish": "max_steps", "checks": 2, "transcript": []}
    return prove_with_agent


async def make(tmp_path, monkeypatch, log, delays=None, **kw):
    monkeypatch.setattr(runner, "_agent_fn", lambda: scripted_agent(log, delays))
    brain = PoolBrain()
    ctx = await started(make_ctx(tmp_path, brain=brain, lean_seconds=0.05, **kw))
    ctx.settings.mode = "online"
    from madalean.pipeline.tournament import leaderboard_of
    brain.lb = leaderboard_of(ctx)
    return ctx, brain


async def test_pipeline_tournament_finds_the_winner_records_it_and_reuses_it(tmp_path, monkeypatch):
    log: list = []
    ctx, brain = await make(tmp_path, monkeypatch, log, delays={"free:c": 3.0, "free:d": 3.0, "free:winner": 0.3})
    d, _j = await create_dossier(ctx, {"statement": STMT, "start": False})
    job = ctx.orchestrator.submit(d.id, [{"stage": "proof"}], strategy="agent")
    await wait_idle(ctx)
    assert job.state == "done" and d.proof_is_current, (job.error, job.summary)
    assert d.proofs[-1].model == "free:winner" and d.proofs[-1].meta["strategy"] == "agent"
    # round 0: A, stopped after the same error twice (D67); round 1: B, Rate-limited, Winner (paid Opus never raced without paid_first)
    assert log[:2] == ["free:a"] * 2 and "paid:opus" not in log
    assert set(log[2:5]) == {"free:b", "free:rate", "free:winner"}
    assert job.tournament["winner"] == "free:winner" and job.tournament["state"] == "won"
    assert {a.round for a in job.attempts} == {0, 1}
    assert ctx.slots.max_seen["online"] <= 3 and ctx.slots.max_seen["lean"] <= 2
    assert not ctx.slots.holders["online"] and not ctx.slots.holders["lean"]
    assert any("Tournoi, round 1" in e.text for e in d.events)
    lb = brain.lb
    assert lb.entry("free:winner", "prove").total_ok == 1 and lb.entry("free:a", "prove").total == 1
    assert lb.entry("free:rate", "prove").pauses > 0.99 and lb.entry("free:rate", "prove").total == 0
    assert lb.entry("free:a", "prove").lean_err == pytest.approx(4, rel=1e-3)      # 2 runs × 2 rejected checks
    # next task: the winner leads round 0 and proves at once
    log.clear()
    job2 = ctx.orchestrator.submit(d.id, [{"stage": "proof"}], strategy="agent")
    await wait_idle(ctx)
    assert job2.state == "done" and log == ["free:winner"] and len(job2.attempts) == 1
    # the API shows it (read-only for everyone, reset host-only)
    async with running(ctx) as (_srv, local, remote):
        async with session() as s:
            async with s.get(local + "/api/models/leaderboard") as r:
                body = await r.json()
            assert r.status == 200 and body["entries"][0]["model"] == "free:winner"
            assert body["tournament"]["tournament_contestants"] == 3
            async with s.post(remote + "/api/models/leaderboard/reset") as r:
                assert r.status in (401, 403)
            async with s.post(local + "/api/models/leaderboard/reset") as r:
                assert r.status == 200
    assert lb.table() == []
    await ctx.stop()


async def test_pipeline_paid_models_only_with_paid_first_and_with_a_cost(tmp_path, monkeypatch):
    log: list = []
    ctx, brain = await make(tmp_path, monkeypatch, log)
    brain.settings["paid_first"] = True
    d, _j = await create_dossier(ctx, {"statement": STMT, "start": False})
    job = ctx.orchestrator.submit(d.id, [{"stage": "proof"}], strategy="agent")
    await wait_idle(ctx)
    assert job.state == "done" and "paid:opus" in log
    assert any("Modèle payant dans le tournoi : Opus" in e.text for e in d.events)
    await ctx.stop()


async def test_pipeline_all_fail_is_bounded(tmp_path, monkeypatch):
    log: list = []
    ctx, brain = await make(tmp_path, monkeypatch, log)
    PoolBrain.MODELS, saved = [m for m in PoolBrain.MODELS if m.model_id not in ("winner", "opus")], PoolBrain.MODELS
    try:
        d, _j = await create_dossier(ctx, {"statement": STMT.replace("(hb : Even b)", "(hb : Odd b)"),
                                           "start": False})
        job = ctx.orchestrator.submit(d.id, [{"stage": "proof"}], strategy="agent")
        await wait_idle(ctx, timeout=60)
    finally:
        PoolBrain.MODELS = saved
    assert job.state == "failed" and job.error == "no_proof"
    assert len(log) == len(set(log[1:])) + 1 and len([a for a in job.attempts if a.stage == "proof"]) <= 16
    assert job.tournament["state"] in ("exhausted", "rounds", "no_progress") and job.tournament["round"] <= 3
    await ctx.stop()


async def test_pipeline_cancel_mid_race(tmp_path, monkeypatch):
    log: list = []
    slow = {k: 60.0 for k in ("free:b", "free:rate", "free:winner", "free:c", "free:d")}
    ctx, brain = await make(tmp_path, monkeypatch, log, delays=slow)
    d, _j = await create_dossier(ctx, {"statement": STMT, "start": False})
    job = ctx.orchestrator.submit(d.id, [{"stage": "proof"}], strategy="agent")
    for _ in range(200):
        await asyncio.sleep(0.02)
        if len(log) >= 7:
            break
    assert len(ctx.slots.holders["online"]) == 3
    t0 = time.monotonic()
    assert await ctx.orchestrator.cancel(job.id)
    assert time.monotonic() - t0 < 5
    assert job.state == "cancelled" and not ctx.slots.holders["online"] and not ctx.slots.holders["lean"]
    assert not [a for a in job.attempts if a.status in ("generating", "compiling")]
    await ctx.stop()


async def test_tournament_disabled_keeps_the_old_loop(tmp_path, monkeypatch):
    log: list = []
    ctx, brain = await make(tmp_path, monkeypatch, log)
    ctx.settings.tournament_enabled = False
    d, _j = await create_dossier(ctx, {"statement": STMT, "start": False})
    job = ctx.orchestrator.submit(d.id, [{"stage": "proof"}], strategy="agent")
    await wait_idle(ctx)
    assert log == [None] * 4 and job.tournament == {} and job.state == "failed"
    await ctx.stop()
