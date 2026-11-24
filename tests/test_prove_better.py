"""Prove better and learn from failed attempts (S-BI, D67): split without a model, blackboard, progress-based stopping,
open problems, pool quality, fading lessons, final report. Scripted models; the fixtures with the real Lean print their
measures (`MEASURE …`): they are fixtures, not a success rate."""
from __future__ import annotations

import asyncio
import time

import pytest

from helpers import make_ctx, running, started, wait_idle
from madalean import leancheck
from madalean.brain.api import ModelRef
from madalean.brain.fake import FakeBrain, demo_responder
from madalean.brain.leaderboard import Leaderboard
from madalean.pipeline import blackboard as BB, decompose as DC, proofsteps, runner, tournament as T
from madalean.research import graphsearch as GS
from madalean.research.lessons import FADE_AFTER, Lessons
from madalean.server.routes_work import _plan_arg, create_dossier


# ---------------------------------------------------------------- splitting (text)
@pytest.mark.parametrize("stmt, pattern, n", [
    ("theorem t (a b : ℕ) (h : a ≤ b) : a ≤ b + 1 ∧ a * 1 = a ∧ b ≤ b := by sorry", "and", 3),
    ("theorem t (n : ℕ) : n = 0 ↔ n + n = 0 := by sorry", "iff", 2),
    ("theorem t : ∀ n : ℕ, 0 < n → (1 ≤ n ∧ n ≠ 0) := by sorry", "and", 2),
    ("theorem t {α : Type*} [Fintype α] (n : ℕ) (h : n = 1 ∨ n = 2 ∨ n = 3) : n ≤ 3 := by sorry", "cases", 3),
    ("theorem t (p q : Prop) : (p ∧ q) → (q ∧ p) := by sorry", "and", 2)])
def test_split_shapes(stmt, pattern, n):
    sp = DC.split(stmt)
    assert sp.pattern == pattern and len(sp.parts) == n


@pytest.mark.parametrize("stmt", [
    "theorem t (a : ℕ) : a = a := by sorry",
    "theorem t : ∃ n : ℕ, 0 < n ∧ n < 2 := by sorry",              # the binder swallows the conjunction
    "theorem t (p q : Prop) (h : p) : p ∨ q ∧ p := by sorry",       # ∨ binds less than ∧
    "theorem t (_ : 1 = 1) : 1 = 1 ∧ 2 = 2 := by sorry",             # an argument that cannot be named
    "theorem t (s : Set ℕ) : s = {x | x ∈ s ∧ x = x} := by sorry", "not lean"])
def test_no_split(stmt):
    assert DC.split(stmt) is None


def test_looks_large():
    assert DC.looks_large("theorem t : ∀ ε : ℝ, ∃ δ : ℝ, ∀ x : ℝ, ∃ y : ℝ, x < y := by sorry")
    assert not DC.looks_large("theorem t (a : ℕ) : a = a := by sorry")


# ---------------------------------------------------------------- blackboard (text)
ST = "theorem t (a b : ℕ) (h : a ≤ b) : a * a ≤ b * b := by sorry"
TRY = """theorem t (a b : ℕ) (h : a ≤ b) : a * a ≤ b * b := by
  have h1 : a * a ≤ a * b := by
    exact Nat.mul_le_mul_left a h
  have h2 : a * b ≤ b * b := Nat.mul_le_mul_right b h
  have bad : a = b := by omega
  have h3 : a * a ≤ a * b + 1 := Nat.le_succ_of_le h1
  nope h1 h2"""


def test_candidates_are_standalone_and_bounded():
    c = BB.candidates(ST, TRY)
    assert [x["head"].rsplit(" : ", 1)[1] for x in c] == ["a * a ≤ a * b", "a * b ≤ b * b", "a = b", "a * a ≤ a * b + 1"]
    assert "have h1" in c[3]["tactic"] and "have h2" not in c[3]["tactic"]      # only what it mentions
    assert len({x["name"] for x in c}) == 4
    assert BB.candidates(ST, TRY.replace("by omega", "by sorry"))[2]["head"].endswith("a * b + 1")   # never a sorry


def test_board_is_deduplicated_and_cheats_are_no_progress():
    b = BB.Board(ST)
    fb = "Error 1:\n\nError Message: unknown constant 'Nat.foo'\n"
    b.record(TRY, fb, "p:a")
    m = b.mark()
    b.record(TRY.replace("omega", "simp"), fb, "p:b")
    b.record("theorem t : True := by sorry", "Error Message: something new", "p:c")
    assert b.mark() == m and b.cheats == 1
    assert "`Nat.foo`" in b.view("p:d")
    b2 = BB.Board(ST)
    b2.cheat("p:c")
    assert "counts for nothing" in b2.view("p:c") and b2.view("p:c") == ""      # told once
    for i in range(60):
        b.record(TRY, f"Error Message: kind{chr(97 + i % 26)} {'x' * (i // 26 + 1)}\n⊢ g{i} = 1\n", "p:a")
    assert len(b.approaches) <= BB.MAX_APPROACHES and len(b.goals) <= BB.MAX_GOALS and len(b.view()) <= BB.VIEW_CHARS


def test_board_belongs_to_the_exact_statement_and_mathlib():
    class D:
        extra: dict = {}
    env = {"workspace": "w", "lean": "1", "mathlib": "m"}
    b = BB.Board(ST, env)
    b.add_lemma("mad_1", "(a : ℕ) : a = a", "theorem mad_1 (a : ℕ) : a = a := by rfl")
    b.store(D)
    assert "mad_1" in BB.Board.load(D, ST, env).lemmas
    assert not BB.Board.load(D, ST.replace("a ≤ b)", "b ≤ a)"), env).lemmas
    assert not BB.Board.load(D, ST, {**env, "mathlib": "n"}).lemmas
    code = "theorem t (a b : ℕ) (h : a ≤ b) : a * a ≤ b * b := by\n  exact mad_1 a"
    assert b.include(code).count("theorem mad_1") == 1 and b.include(b.include(code)) == b.include(code)
    D.extra = {"board": {"key": BB.Board.key_of(ST), "env": b.env, "lemmas": "junk", "approaches": 3}}
    assert BB.Board.load(D, ST, env).lemmas == {}


# ---------------------------------------------------------------- tournament: progress, families, decomposition
def pool(n):
    return [T.Contestant(f"p:{x}-{i}", f"{x}{i}") for i in range(n) for x in ("qwen", "llama")]


async def test_stops_without_progress_and_provider_errors_do_not_count():
    n = []

    async def run(c, k, a, deadline):
        n.append(k)
        return T.Outcome(c, k, attempts=1, lean_errors=1)
    r = await T.Tournament(T.Config(), candidates=lambda: pool(20), run=run, progress=lambda: (0, 0)).run()
    assert r.stop == "no_progress" and max(n) == 1
    n.clear()
    weak = iter(range(1000))                              # every round: only new kinds of errors
    r = await T.Tournament(T.Config(), candidates=lambda: pool(20), run=run, progress=lambda: (0, next(weak))).run()
    assert r.stop == "no_progress" and max(n) == 2
    n.clear()
    r = await T.Tournament(T.Config(), candidates=lambda: pool(20), run=run, progress=lambda: (next(weak), 0)).run()
    assert r.stop == "rounds" and max(n) == 3             # new lemmas: goes on to the hard caps

    async def down(c, k, a, deadline):
        return T.Outcome(c, k, unavailable=True)
    r = await T.Tournament(T.Config(), candidates=lambda: pool(40), run=down, progress=lambda: (0, 0)).run()
    assert r.stop == "rounds"


async def test_decomposition_comes_after_one_failure_and_families_differ():
    seen = []

    async def run(c, k, a, deadline):
        seen.append((k, c.key))
        return T.Outcome(c, k, attempts=1)

    async def between(left):
        seen.append(("split", left > 0))
        return None
    await T.Tournament(T.Config(contestants=2), candidates=lambda: [T.Contestant(f"p:{x}") for x in (
        "qwen-1", "qwen-2", "qwen-3", "llama-1")], run=run, between=between, progress=lambda: (0, 0),
        family=lambda c: c.key[2:].split("-")[0]).run()
    assert seen[0] == (0, "p:qwen-1") and seen[1] == ("split", True)
    assert {k for r, k in seen[2:]} == {"p:qwen-2", "p:llama-1"}

    async def solved(left):
        return T.Outcome(T.Contestant("madalean:decompose", kind="split"), 0, ok=True, result="p")
    rec = []
    r = await T.Tournament(T.Config(), candidates=lambda: pool(5), run=run, between=solved, record=rec.append).run()
    assert r.stop == "won" and r.winner.result == "p" and len(rec) == 1         # not a model: not in the leaderboard


def test_a_model_that_always_stalls(tmp_path):
    lb = Leaderboard(tmp_path / "l.json")
    for _ in range(3):
        lb.record("p:mute", "prove", ok=False, lean_errors=0)
        lb.record("p:tries", "prove", ok=False, lean_errors=2)
    assert lb.stalls("p:mute", "prove") and not lb.stalls("p:tries", "prove") and not lb.stalls("p:new", "prove")


# ---------------------------------------------------------------- lessons
def test_useless_lessons_fade_and_splits_are_learned(tmp_path):
    st = Lessons(tmp_path / "l.json")
    st.learn_split("theorem t (n : ℕ) : n = 0 ↔ n + n = 0 := by sorry", "iff", ["theorem a (n : ℕ) : n = 0 := by sorry"],
                   {}, "d")
    q = "theorem u (m : ℕ) : m = 0 ↔ m + m = 0 := by sorry"
    ids: list = []
    assert "proved by a split (iff)" in st.hint(q, {}, ids=ids) and len(ids) == 1
    v = st.value(st.items[ids[0]])
    for _ in range(FADE_AFTER):
        st.outcome(ids, False)
    assert st.value(st.items[ids[0]]) < v and st.hint(q, {}) == ""              # no longer given
    for _ in range(FADE_AFTER):
        st.outcome(ids, False)
    assert ids[0] not in Lessons(tmp_path / "l.json").items                     # then dropped
    st.learn_split(q, "iff", [], {}, "d")
    for _ in range(10):
        st.outcome(ids, True)
    assert "proved by a split" in st.hint(q, {})


def test_budget_of_a_step():
    assert _plan_arg([{"stage": "proof", "budget_minutes": 9999}])[0]["budget_minutes"] == 240
    assert "budget_minutes" not in _plan_arg([{"stage": "proof", "budget_minutes": True}])[0]


# ---------------------------------------------------------------- pipeline fixtures
class Pool(FakeBrain):
    MODELS = [ModelRef("free", f"{f}-{i}", f"{f}-{i}") for i in range(4) for f in ("qwen", "llama", "gemini", "kimi", "glm")]

    def __init__(self, responder=demo_responder):
        super().__init__(responder)
        self.settings = {"paid_first": False}

    def pool(self, role, mode="auto", *, domain=None):
        return list(self.MODELS)


def use_agent(monkeypatch, answer, log):
    """`answer(model, hint, check)` → code or None."""
    async def prove_with_agent(brain, retriever, *, statement, workspace_key, check, library_search, hint, on_chunk,
                               mode, max_steps, max_seconds, only=None):
        log.append((only, hint))
        code = await answer(only, hint, check)
        return {"code": code, "model": only, "steps": 3, "finish": "proved" if code else "max_steps", "checks": 1,
                "transcript": []}
    monkeypatch.setattr(runner, "_agent_fn", lambda: prove_with_agent)


def before(monkeypatch):
    """The behaviour before S-BI: no split, no search, no blackboard, no progress stop."""
    async def none(*a, **k):
        return None
    monkeypatch.setattr(proofsteps, "split_first", none)
    monkeypatch.setattr(proofsteps, "reasoned", none)
    monkeypatch.setattr(proofsteps, "can_search", lambda *a: False)
    monkeypatch.setattr(proofsteps, "search_allowed", lambda *a: True)
    monkeypatch.setattr(BB.Board, "view", lambda self, model="": "")
    monkeypatch.setattr(BB.Board, "mark", lambda self: (time.monotonic(), 0))
    monkeypatch.setattr(BB.Board, "harvest", none)


async def prove(ctx, statement, meaning=None, plan=None):
    ctx.settings.mode = "online"
    ctx.settings.literature = ctx.settings.mathlib_first = ctx.settings.statement_check = ctx.settings.certificates = False
    d, _j = await create_dossier(ctx, {"statement": statement, "start": False, "workspace": ctx.settings.workspace})
    if meaning:
        d.extra["meaning"] = meaning
    t0 = time.monotonic()
    job = ctx.orchestrator.submit(d.id, plan or [{"stage": "proof"}], strategy="agent")
    await wait_idle(ctx, 900)
    return d, job, time.monotonic() - t0


def measure(name, when, d, job, seconds, log):
    print(f"MEASURE {name} {when}: proved={d.proof_is_current} model_runs={len(log)} "
          f"seconds={seconds:.0f} stop={(job.tournament or {}).get('state', '-')}")


async def check_bad(check, body="nope_tactic", head="theorem t"):
    return await check(f"{head} := by\n  {body}")


# (a) a conjunction that no scripted model proves in one go; automation and one model prove the parts
CONJ = ("theorem t (a b : ℕ) (h : a ≤ b) (x y : ℝ) : (a * a ≤ b * b) ∧ (2 * (x * y) ≤ x ^ 2 + y ^ 2) ∧ "
        "(a + 0 = a) := by sorry")


def conj_brain(role, messages, brain):
    first = next((m["content"] for m in messages if m.get("role") == "user"), "")
    if first.startswith(GS.MARK_VIABILITY):
        return '{"score": 0.6, "reason": "ok"}'
    if "Complete the following Lean 4 code" in first:
        brain.behaviour["parts"] = brain.behaviour.get("parts", 0) + 1
        head = "theorem t_part1 (a b : ℕ) (h : a ≤ b) (x y : ℝ) : a * a ≤ b * b := by\n  exact Nat.mul_le_mul h h"
        if "t_part1" in first:
            return f"```lean4\n{head}\n```"
        return ("```lean4\ntheorem t_part2 (a b : ℕ) (h : a ≤ b) (x y : ℝ) : 2 * (x * y) ≤ x ^ 2 + y ^ 2 := by\n"
                "  nlinarith [sq_nonneg (x - y)]\n```")
    return demo_responder(role, messages, brain)


@pytest.mark.parametrize("old", [True, False])
async def test_a_conjunction_needs_decomposition(tmp_path, ws, monkeypatch, old):
    log: list = []

    async def answer(model, hint, check):
        r = await check("theorem t (a b : ℕ) (h : a ≤ b) (x y : ℝ) : (a * a ≤ b * b) ∧ (2 * (x * y) ≤ x ^ 2 + y ^ 2) ∧ "
                        f"(a + 0 = a) := by\n  exact ⟨by omega, by positivity, by {model.split('-')[0].split(':')[1]}⟩")
        assert not r["ok"]
        return None
    use_agent(monkeypatch, answer, log)
    if old:
        before(monkeypatch)
    ctx = make_ctx(tmp_path, ws=ws, brain=Pool(conj_brain))
    async with running(ctx):
        d, job, s = await prove(ctx, CONJ)
        measure("conjunction", "before" if old else "after", d, job, s, log)
        assert d.proof_is_current is not old, [(e.kind, e.text) for e in d.events]
        if not old:
            meta = d.proofs[-1].meta
            assert meta["strategy"] == "graph" and set(meta["axioms"]) <= leancheck.ALLOWED_AXIOMS
            assert len(log) <= 1
            assert any(x["kind"] == "split" and x["pattern"] == "and" for x in ctx._lessons.items.values())


# (b) attempt 2 (another model) uses the `have` that Lean accepted from attempt 1
HARD = "theorem t (a b c : ℕ) (h : a ≤ b) : a * a * c ≤ b * b * c + 0 := by sorry"
HEAD = HARD.rsplit(" := ", 1)[0]


@pytest.mark.parametrize("old", [True, False])
async def test_attempt_two_reuses_an_accepted_have(tmp_path, ws, monkeypatch, old):
    log: list = []

    async def answer(model, hint, check):
        mine = [w for w in hint.replace("(", " ").split() if w.startswith("mad_")]
        if mine:
            code = f"{HEAD} := by\n  have k := {mine[0]} a b c h\n  exact Nat.mul_le_mul k (le_refl c)"
            r = await check(code)
            assert r["ok"], r["feedback"]
            return code
        await check(f"{HEAD} := by\n  have key : a * a ≤ b * b := Nat.mul_le_mul h h\n"
                    f"  exact wrong_{model.split(':')[1].replace('-', '_')} key")
        return None
    use_agent(monkeypatch, answer, log)
    if old:
        before(monkeypatch)
    else:
        async def none(*a, **k):
            return None
        monkeypatch.setattr(proofsteps, "reasoned", none)      # the blackboard alone
    ctx = make_ctx(tmp_path, ws=ws, brain=Pool())
    async with running(ctx):
        d, job, s = await prove(ctx, HARD)
        measure("reuse", "before" if old else "after", d, job, s, log)
        assert d.proof_is_current is not old, [(e.kind, e.text) for e in d.events]
        if not old:
            assert len(log) == 2 and "mad_" in d.proofs[-1].code
            assert set(d.proofs[-1].meta["axioms"]) <= leancheck.ALLOWED_AXIOMS
            g = ctx.research.graphs.get(d.id)
            assert g is None or all(n["status"] != "proved" or n.get("proof") for n in g["nodes"].values())


# (c) an unprovable target: stops early, with an honest report
UNPROVABLE = "theorem t (n : ℕ) : n * n + n + 41 < 100 ∨ n < 50 := by sorry"


@pytest.mark.parametrize("old", [True, False])
async def test_an_unprovable_target_stops_early(tmp_path, ws, monkeypatch, old):
    log: list = []

    async def answer(model, hint, check):
        await check(f"theorem t (n : ℕ) : n * n + n + 41 < 100 ∨ n < 50 := by\n"
                    f"  have pos : 0 ≤ n := Nat.zero_le n\n  {'omega' if 'qwen' in model else 'left; nlinarith'}")
        return None
    use_agent(monkeypatch, answer, log)
    if old:
        before(monkeypatch)
    ctx = make_ctx(tmp_path, ws=ws, brain=Pool(lambda r, m, b: "{}"))
    async with running(ctx):
        d, job, s = await prove(ctx, UNPROVABLE)
        measure("unprovable", "before" if old else "after", d, job, s, log)
        assert not d.proof_is_current and job.error == "no_proof"
        if not old:
            assert len(log) <= 5 and job.tournament["state"] == "no_progress"
            e = [e for e in d.events if e.kind == "error"][-1]
            rep = e.params["report"]
            assert rep["tried"] and rep["goal"] and rep["actions"] and rep["cause"] == "unknown"
            assert any("0 ≤ n" in m["statement"] for m in rep["lemmas"])
            assert e.key.startswith("Aucune preuve trouvée") and "Où cela bloque" in e.text
            g = ctx.research.graphs.get(d.id)
            assert all(g["nodes"][m["node"]]["status"] == "proved" for m in rep["lemmas"])
            assert d.extra["board"]["approaches"]


async def test_open_problem_no_one_shot_without_a_budget(tmp_path, monkeypatch):
    log: list = []

    async def answer(model, hint, check):
        return None
    use_agent(monkeypatch, answer, log)
    ctx = await started(make_ctx(tmp_path, brain=Pool(), lean_seconds=0.0))
    meaning = {"known_status": "open", "status_confidence": "model_only"}
    d, job, _s = await prove(ctx, "theorem t (n : ℕ) : n < n + 1 := by sorry", meaning)
    assert log == [] and job.error == "open_problem" and d.status == "draft"
    e = [e for e in d.events if e.kind == "error"][-1]
    assert e.params["report"]["cause"] == "open" and {"id": "budget", "minutes": 10} in e.params["report"]["actions"]
    job = ctx.orchestrator.submit(d.id, [{"stage": "proof", "budget_minutes": 5}], strategy="agent")
    await wait_idle(ctx)
    assert log and job.error == "no_proof"
    await ctx.stop()


async def test_providers_down_is_not_a_mathematical_failure(tmp_path, monkeypatch):
    async def down(brain, retriever, *, only=None, **kw):
        return {"code": None, "model": None, "steps": 0, "finish": "error", "checks": 0,
                "transcript": [{"type": "model_error", "reason": "HTTP 429"}]}
    monkeypatch.setattr(runner, "_agent_fn", lambda: down)
    monkeypatch.setattr(runner.DossierPipeline, "_legacy_fallback", lambda self: False)
    ctx = await started(make_ctx(tmp_path, brain=Pool(), lean_seconds=0.0))
    ctx.settings.prove_strategy = "agent"
    d, job, _s = await prove(ctx, "theorem t (n : ℕ) : n < n + 1 := by sorry")
    e = [e for e in d.events if e.kind == "error"][-1]
    assert e.params["report"]["cause"] == "providers" and "approaches" not in d.extra.get("board", {})
    await ctx.stop()


async def test_real_lean_accepts_the_splits(tmp_path, ws):
    ctx = await started(make_ctx(tmp_path, ws=ws))
    for st in ("theorem t (n : ℕ) : n = 0 ↔ n + n = 0 := by sorry",
               "theorem t : ∀ n : ℕ, 0 < n → (1 ≤ n ∧ n ≠ 0) := by sorry",
               "theorem t {α : Type} [Fintype α] (n : ℕ) (h : n = 1 ∨ n = 2) : n ≤ 3 := by sorry"):
        s = leancheck.prepare_statement(st)
        r = await ctx.lean.check(DC.gate_code(s, DC.split(s)), ws, 180, None, owner="t")
        assert not r.verdict.errors, (st, [m.text for m in r.verdict.errors])
    await ctx.stop()
