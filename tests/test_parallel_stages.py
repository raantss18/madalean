"""S-AF (DECISIONS D38): once Lean accepts the statement, guided reading, statement check, Mathlib-first and the proof
search run together; a « faux » / « douteux » verdict cancels the proof work and keeps the user's choice; a Mathlib
success cancels the search; « Arrêter » stops every task; identical work is never redone (cache by statement and
Mathlib version). Scripted brain, simulated Lean, scripted statement checker and Mathlib search (their own logic is
tested with the real Lean in test_statement_check.py)."""
from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path

import pytest

from madalean.brain.fake import FakeBrain, demo_responder
from madalean.pipeline import runner as R
from madalean.pipeline.mathlib_first import MathlibResult
from madalean.pipeline.verify import CheckResult
from madalean.server.routes_work import create_dossier
from madalean.workspaces import Workspace
from helpers import make_ctx, started, wait_idle

STATEMENT = "theorem t (a b : ℕ) (ha : Even a) (hb : Even b) : Even (a + b) := by sorry"
PROBLEM = "Montrer que la somme de deux entiers pairs est paire."


class Script:
    """What the scripted checker / Mathlib search answer, and when."""

    def __init__(self):
        self.check_delay, self.verdict, self.check_proof = 0.6, "faithful", ""
        self.mathlib_delay, self.mathlib_ok = 0.3, False
        self.check_calls = self.mathlib_calls = 0
        self.check_cancelled = self.mathlib_cancelled = False


@pytest.fixture
def script(monkeypatch):
    sc = Script()

    class Checker:
        def __init__(self, io, mode, lean_real=True, use_model=True):
            self.io = io

        async def run(self, problem, understood, statement, ws, *, lang="fr", learn=False):
            sc.check_calls += 1
            try:
                await asyncio.sleep(sc.check_delay)
            except asyncio.CancelledError:
                sc.check_cancelled = True
                raise
            r = CheckResult(verdict=sc.verdict, summary="lecture", seconds=sc.check_delay, proof=sc.check_proof)
            if sc.verdict == "false":
                r.evidence = {"kind": "negation", "code": "intro h", "idea": ""}
                r.issues = [{"kind": "false_statement", "severity": "high", "explanation": "faux", "fix": "",
                             "checked": "lean"}]
            return r

    class Mathlib:
        def __init__(self, io, mode, retriever, lean_real=True, use_model=True):
            self.io = io

        async def run(self, statement, ws, texts, timeout_s, quick=None):
            sc.mathlib_calls += 1
            a = self.io.new_attempt("proof", "mathlib")
            a.model = "mathlib:search"
            try:
                await asyncio.sleep(sc.mathlib_delay)
            except asyncio.CancelledError:
                sc.mathlib_cancelled = True
                raise
            cands = [{"name": "Even.add", "signature": "Even m → Even n → Even (m + n)"}]
            if not sc.mathlib_ok:
                a.status = "rejected"
                return MathlibResult(False, candidates=cands, seconds=sc.mathlib_delay)
            a.status = "accepted"
            code = statement.replace("sorry", "exact Even.add ha hb")
            return MathlibResult(True, code, "Even.add", "exact Even.add ha hb", "template", axioms=["propext"],
                                 candidates=cands, seconds=sc.mathlib_delay)

    monkeypatch.setattr(R, "StatementChecker", Checker)
    monkeypatch.setattr(R, "MathlibFirst", Mathlib)
    return sc


def slow_prover(delay: float):
    """The prover model writes slowly (`delay` seconds before its answer); everything else answers at once."""
    def responder(role, messages, brain):
        if role == "prove":
            brain.behaviour["prove_calls"] = brain.behaviour.get("prove_calls", 0) + 1
            ans = demo_responder(role, messages, brain)
            return {"text": ans, "delay": delay}
        if role == "explain":
            return {"text": demo_responder(role, messages, brain), "delay": 0.4}
        return demo_responder(role, messages, brain)
    return responder


async def setup(tmp_path, prove_delay=0.0, ws=None, mode="auto"):
    ctx = make_ctx(tmp_path, ws=ws, fake_lean=True, brain=FakeBrain(slow_prover(prove_delay)), lean_seconds=0.05)
    ctx = await started(ctx)
    ctx.settings.mode = mode
    ctx.settings.prove_strategy = "goedel"        # the local Goedel loop on the scripted brain: no agent involved
    ctx.settings.statement_check = ctx.settings.mathlib_first = True
    ctx.lean.seconds = 0.05
    return ctx


async def submit(ctx, plan=None, statement=STATEMENT, problem=PROBLEM):
    d, _ = await create_dossier(ctx, {"statement": statement, "problem": problem, "start": False})
    job = ctx.orchestrator.submit(d.id, plan or [{"stage": "notes"}, {"stage": "proof"}, {"stage": "explanation"}])
    return d, job


def rows(job, stage):
    return [r for r in job.timings if r["stage"] == stage]


def job_tasks(job):
    return [t for t in asyncio.all_tasks() if t.get_name().startswith(job.id + "-") and not t.done()]


def slots_free(ctx):
    return all(v["used"] == 0 and v["waiting"] == 0 for v in ctx.slots.usage().values())


async def test_stages_run_together_and_the_first_attempt_starts_at_once(tmp_path, script):
    script.check_delay = 1.0
    ctx = await setup(tmp_path, prove_delay=0.3)
    d, job = await submit(ctx)
    seen_stages: set[tuple] = set()
    while job.active:
        if len(job.stages) > 1:
            seen_stages.add(tuple(sorted(job.stages)))
        await asyncio.sleep(0.02)
    await wait_idle(ctx)
    assert job.state == "done" and d.status == "proved" and d.proof_is_current, (job.error, job.summary)
    # several stages at once, the main one shown first
    assert any({"notes", "proof", "verify"} <= set(s) for s in seen_stages), seen_stages
    first_try = min(a.t for a in job.attempts if a.stage == "proof" and a.kind != "mathlib")
    check = rows(job, "verify")[0]
    assert first_try < check["end"] - 0.5           # the prover started long before the check ended
    assert rows(job, "notes")[0]["start"] < check["end"] and rows(job, "mathlib")
    # timings: one closed row per stage, seconds in the result events
    assert {r["stage"] for r in job.timings} >= {"notes", "proof", "verify", "mathlib", "explanation", "informal"}
    assert all(r["end"] is not None and r["seconds"] >= 0 for r in job.timings)
    kinds = [e.kind for e in d.events]
    assert kinds.index("check") < kinds.index("proof") < kinds.index("explanation") < kinds.index("informal")
    for k in ("notes", "proof", "explanation", "informal", "check"):
        ev = next(e for e in d.events if e.kind == k)
        assert isinstance(ev.params.get("seconds"), (int, float)), k
    # explanation and informal proof were written together
    ex, inf = rows(job, "explanation")[0], rows(job, "informal")[0]
    assert inf["start"] < ex["end"]
    assert job.stages == [] and job.stage == "" and not job_tasks(job) and slots_free(ctx)
    # the history keeps the timings (scripts/perf_report.py reads them)
    hist = json.loads((ctx.paths.jobs / f"{d.id}.json").read_text())
    assert {r["stage"] for r in hist[-1]["timings"]} >= {"proof", "verify", "notes"}
    await ctx.stop()


async def test_false_statement_cancels_the_proof_search_and_the_user_decides(tmp_path, script):
    script.verdict, script.check_delay = "false", 0.4
    ctx = await setup(tmp_path, prove_delay=3.0)
    d, job = await submit(ctx)
    await wait_idle(ctx)
    assert job.error == "statement_false" and d.status == "draft" and not d.proofs
    assert not any(e.kind == "proof" for e in d.events)
    assert any(e.kind == "check" and e.params.get("verdict") == "false" for e in d.events)
    assert not any(e.kind == "explanation" for e in d.events)
    assert all(a.status not in ("generating", "compiling") for a in job.attempts)
    assert any(a.status == "cancelled" for a in job.attempts if a.stage == "proof")
    assert not job_tasks(job) and slots_free(ctx)
    took = job.ended - job.started
    assert took < 2.5, took                           # the 3 s prover answer was not waited for
    # « Prouver quand même »: the user's choice, the verdict is not asked again
    calls = script.check_calls
    job2 = ctx.orchestrator.submit(d.id, [{"stage": "proof", "force": True}])
    await wait_idle(ctx)
    assert job2.state == "done" and d.status == "proved" and script.check_calls == calls
    await ctx.stop()


async def test_doubtful_verdict_after_the_proof_was_found_still_stops_it(tmp_path, script):
    script.verdict, script.check_delay = "doubtful", 1.0
    ctx = await setup(tmp_path, prove_delay=0.0)
    d, job = await submit(ctx)
    await wait_idle(ctx)
    # the search found a proof before the verdict: it is not recorded (« preuve non lancée », as before)
    assert job.error == "statement_doubtful" and not d.proofs and d.status == "draft"
    await ctx.stop()


async def test_mathlib_success_cancels_the_search_and_waits_for_the_check(tmp_path, script):
    script.mathlib_ok, script.mathlib_delay, script.check_delay = True, 0.3, 0.8
    ctx = await setup(tmp_path, prove_delay=5.0)
    d, job = await submit(ctx)
    await wait_idle(ctx)
    assert job.state == "done" and d.status == "proved", (job.error, job.summary)
    meta = d.proofs[d.cur_proof].meta
    assert meta["strategy"] == "mathlib" and meta["mathlib_lemma"] == "Even.add"
    cancelled = [a for a in job.attempts if a.stage == "proof" and a.status == "cancelled"]
    assert cancelled and all("autrement" in a.summary for a in cancelled)
    kinds = [e.kind for e in d.events]
    assert kinds.index("check") < kinds.index("proof")      # recorded once the check let it through
    assert job.ended - job.started < 4.0
    assert not job_tasks(job) and slots_free(ctx)
    await ctx.stop()


async def test_quick_proof_found_by_the_check_wins(tmp_path, script):
    script.check_delay, script.check_proof, script.mathlib_delay = 0.2, "exact Even.add ha hb", 3.0
    ctx = await setup(tmp_path, prove_delay=5.0)
    d, job = await submit(ctx)
    await wait_idle(ctx)
    assert d.status == "proved" and d.proofs[d.cur_proof].meta["strategy"] == "mathlib"
    assert d.proofs[d.cur_proof].meta["mathlib_source"] == "check" and script.mathlib_cancelled
    await ctx.stop()


async def test_user_stop_cancels_every_task(tmp_path, script):
    script.check_delay, script.mathlib_delay = 10.0, 10.0
    ctx = await setup(tmp_path, prove_delay=10.0)
    d, job = await submit(ctx)
    t0 = time.monotonic()
    while len(job.stages) < 3 and time.monotonic() - t0 < 5:
        await asyncio.sleep(0.02)
    assert {"proof", "verify", "mathlib"} <= set(job.stages), job.stages
    assert await ctx.orchestrator.cancel(job.id)
    await wait_idle(ctx)
    assert job.state == "cancelled" and d.status == "stopped" and not d.proofs
    assert script.check_cancelled and script.mathlib_cancelled
    assert not job_tasks(job) and slots_free(ctx)
    assert job.stages == [] and all(r["end"] is not None for r in job.timings)
    assert all(a.status not in ("generating", "compiling") for a in job.attempts)
    await asyncio.sleep(0.3)
    n = len(d.events)
    await asyncio.sleep(0.3)
    assert len(d.events) == n                          # nothing keeps writing after « Arrêter »
    await ctx.stop()


async def test_local_mode_keeps_one_stage_after_the_other(tmp_path, script):
    ctx = await setup(tmp_path, mode="local")
    d, job = await submit(ctx)
    await wait_idle(ctx)
    assert d.status == "proved"
    main = [r for r in job.timings if r["stage"] in ("notes", "proof", "explanation", "informal")]
    for a, b in zip(main, main[1:]):
        assert a["end"] <= b["start"] + 1e-3, (a, b)
    await ctx.stop()


def lake_ws(tmp_path: Path, rev: str) -> Workspace:
    root = tmp_path / "ws"
    root.mkdir(exist_ok=True)
    (root / "lake-manifest.json").write_text(json.dumps({"packages": [
        {"name": "mathlib", "inputRev": "v4.9.0", "rev": rev}]}))
    return Workspace("cachews", "Cache WS", root, "leanprover/lean4:v4.9.0-rc1", True)


async def test_same_statement_is_not_checked_or_searched_twice(tmp_path, script):
    script.mathlib_ok = True
    ws = lake_ws(tmp_path, "a" * 40)
    ctx = await setup(tmp_path, ws=ws, prove_delay=3.0)
    d1, _ = await submit(ctx)
    await wait_idle(ctx)
    assert d1.status == "proved" and script.check_calls == 1 and script.mathlib_calls == 1
    # another dossier, same statement (another theorem name, other spacing): reused, with visible events
    d2, job2 = await submit(ctx, statement=STATEMENT.replace("(a b : ℕ)", "(a  b : ℕ)"))
    await wait_idle(ctx)
    assert d2.theorem != d1.theorem and d2.status == "proved"
    assert script.check_calls == 1 and script.mathlib_calls == 1
    texts = [e.text for e in d2.events]
    assert any("déjà vérifié" in t.lower() for t in texts) and any("Déjà trouvé dans Mathlib" in t for t in texts)
    chk = next(e for e in d2.events if e.kind == "check")
    assert chk.params.get("cached") and chk.params["verdict"] == "faithful"
    # the reused Mathlib proof was judged again by Lean, for THIS dossier's theorem
    assert d2.theorem in d2.proof and d2.proofs[d2.cur_proof].meta["strategy"] == "mathlib"
    # another wording of the problem: fidelity is judged against the user's words → checked again
    await submit(ctx, problem="Prouver que a + b est pair si a et b le sont.")
    await wait_idle(ctx)
    assert script.check_calls == 2 and script.mathlib_calls == 1
    # Mathlib updated in the workspace: nothing older is reused
    (ws.path / "lake-manifest.json").write_text(json.dumps({"packages": [
        {"name": "mathlib", "inputRev": "v4.9.0", "rev": "b" * 40}]}))
    await submit(ctx)
    await wait_idle(ctx)
    assert script.check_calls == 3 and script.mathlib_calls == 2
    await ctx.stop()


async def test_cached_mathlib_proof_that_lean_now_refuses_is_dropped(tmp_path, script):
    script.mathlib_ok = True
    ctx = await setup(tmp_path, prove_delay=1.5)
    d1, _ = await submit(ctx)
    await wait_idle(ctx)
    cache = ctx.orchestrator.pipeline._cache()
    for e in cache.data["mathlib"].values():
        e["value"]["tactic"] = "exact no_such_lemma ha hb"         # the simulated Lean refuses `no_such`
    d2, _ = await submit(ctx)
    await wait_idle(ctx)
    assert script.mathlib_calls == 2 and d2.status == "proved"      # searched again as usual
    assert "no_such" not in d2.proof
    await ctx.stop()


def test_cache_key_normalization():
    from madalean.pipeline.stagecache import make_key, normalize_statement
    v = {"workspace": "w", "lean": "v4.9", "mathlib": "x"}
    a = "theorem foo (a b : ℕ) (ha : Even a) : Even (a + b) := by sorry"
    b = "-- a comment\ntheorem   bar (a b : ℕ)\n  (ha : Even a) : Even (a + b) := by sorry"
    assert normalize_statement(a) == normalize_statement(b)
    assert make_key(a, v) == make_key(b, v)
    assert make_key(a, v) != make_key(a, {**v, "mathlib": "y"}) != make_key(a, {**v, "workspace": "z"})
    assert make_key(a, v) != make_key(a.replace("Even (a + b)", "Even (a * b)"), v)


async def test_job_waits_only_when_every_working_stage_waits(tmp_path):
    ctx = await started(make_ctx(tmp_path))
    from madalean.jobs import Job
    job = Job.new("d", [], "auto", "auto")
    job.state = "running"
    ctx.orchestrator.jobs[job.id] = job
    job.live = {job.id + "#search", job.id + "#notes"}
    ctx.orchestrator._on_wait(job.id + "#notes", "gpu", True)
    assert job.state == "running" and job.waiting == ""          # the search still works
    ctx.orchestrator._on_wait(job.id + "#search", "online", True)
    assert job.state == "queued" and job.waiting in ("gpu", "online")
    ctx.orchestrator._on_wait(job.id + "#notes", "gpu", False)
    assert job.state == "running" and job.waiting == ""
    await ctx.stop()
