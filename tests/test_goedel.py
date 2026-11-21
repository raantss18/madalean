"""Prove loop + formalizer (1.1.4 behaviour) on asyncio, with a scripted brain and the REAL Lean compiler."""
from __future__ import annotations

import pytest

from madalean import config, names
from madalean.brain.api import BrainError
from madalean.brain.fake import FakeBrain
from madalean.jobs import Job
from madalean.pipeline.goedel import Formalizer, GoedelProver
from madalean.pipeline.runner import JobIO
from helpers import make_ctx

WRONG = "<think>easy</think>\nPlan.\n```lean4\ntheorem t (a b : ℕ) (h : a = b) : b = a := by\n  exact h\n```"
RIGHT = "<think>fix</think>\nCorrected.\n```lean4\ntheorem t (a b : ℕ) (h : a = b) : b = a := by\n  exact h.symm\n```"
STMT = "theorem t (a b : ℕ) (h : a = b) : b = a := by sorry"
GOOD_STMT = ("<think>translate</think>\nHere:\n```lean4\nimport Mathlib\n\ntheorem mon_probleme (a b : ℕ) (ha : Even a) "
             "(hb : Even b) : Even (a + b) := by sorry\n```")
BAD_STMT = "```lean4\ntheorem mon_probleme (a b : ℕ) (ha : Even a : Even (a + b) := by sorry\n```"
LOOP_TEXT = "<think>" + ("-- We will use the fact that the determinant is non-negative.\n-- However, A is invertible.\n" * 90)


def scripted(items: list):
    def responder(role, messages, brain):
        it = items.pop(0)
        if it == "ctx_error":
            return BrainError("error", "the request exceeds the available context size")
        return it
    return responder


def setup(tmp_path, ws, items):
    brain = FakeBrain(scripted(items))
    ctx = make_ctx(tmp_path, ws=ws, brain=brain)
    job = Job.new("d", [], "local", "goedel")
    return ctx, brain, JobIO(ctx, job), job


def lengths(brain):
    return [len(r["messages"]) for r in brain.requests]


async def test_wrong_then_corrected_with_context_overflow_retry(tmp_path, ws):
    ctx, brain, io, job = setup(tmp_path, ws, ["ctx_error", WRONG, RIGHT])
    p = GoedelProver(io)
    # first request has a correction history so the context-overflow retry path is exercised
    orig = p._fit_messages

    def fit_once():
        if not getattr(p, "_seeded", False):
            p._seeded = True
            p.messages = p.messages + [{"role": "assistant", "content": "old"}, {"role": "user", "content": "old feedback"}]
        return orig()
    p._fit_messages = fit_once
    res = await p.run(STMT, ws, 4, config.SamplingSettings(), 240, 16384)
    assert res.ok, [(a.status, a.summary, a.errors_text[:200]) for a in job.attempts]
    assert [a.status for a in job.attempts] == ["rejected", "accepted"]   # the context error used no attempt
    assert "exact h.symm" in res.code and res.axioms is not None
    last_user = brain.requests[-1]["messages"][-1]["content"]
    assert last_user.startswith("The proof (Round 0) is not correct.") and "<error>" in last_user
    assert brain.requests[-1]["messages"][-2]["role"] == "assistant"
    assert all(r["role"] == "prove" and r["mode"] == "local" for r in brain.requests)
    assert job.attempts[-1].model.startswith("local:")


async def test_statement_cannot_be_weakened(tmp_path, ws):
    cheat = "```lean4\ntheorem t (a b : ℕ) (h : a = b) : True := by\n  trivial\n```"
    ctx, brain, io, job = setup(tmp_path, ws, [cheat])
    res = await GoedelProver(io).run(STMT, ws, 1, config.SamplingSettings(), 240, 16384)
    assert not res.ok and job.attempts[0].status == "rejected"


async def test_sorry_answer_rejected(tmp_path, ws):
    ctx, brain, io, job = setup(tmp_path, ws, ["```lean4\ntheorem t (a b : ℕ) (h : a = b) : b = a := by\n  sorry\n```"])
    res = await GoedelProver(io).run(STMT, ws, 1, config.SamplingSettings(), 240, 16384)
    assert not res.ok and "sorry" in job.attempts[0].summary


async def test_formalizer_retries_until_lean_accepts(tmp_path, ws):
    ctx, brain, io, job = setup(tmp_path, ws, [LOOP_TEXT, BAD_STMT, GOOD_STMT])
    f = await Formalizer(io).run("Montrer que la somme de deux entiers pairs est paire.", ws, 4, 240)
    assert f.ok, [(a.status, a.summary, a.errors_text[:120]) for a in job.attempts]
    assert [a.status for a in job.attempts] == ["rejected", "rejected", "accepted"]
    assert "tournait en rond" in job.attempts[0].summary and "Lean refuse" in job.attempts[1].summary
    assert f.statement.rstrip().endswith("Even (a + b) := by sorry")
    assert f.statement.startswith("import Mathlib\nimport Aesop")
    first = brain.requests[0]["messages"][0]["content"]
    assert first.startswith("Please autoformalize the following natural language problem statement in Lean 4.")
    assert "Montrer que la somme de deux entiers pairs est paire.Think before you provide the lean statement." in first
    assert brain.requests[0]["extra"]["top_k"] == 20 and brain.requests[0]["role"] == "formalize"


async def test_formalizer_gives_up_but_keeps_last_statement(tmp_path, ws):
    ctx, brain, io, job = setup(tmp_path, ws, [BAD_STMT, BAD_STMT])
    f = await Formalizer(io).run("n'importe quoi", ws, 2, 240)
    assert not f.ok and f.statement and f.errors
    assert "corrigez-la" in f.summary["text"]


async def test_prover_restarts_after_a_loop(tmp_path, ws):
    ctx, brain, io, job = setup(tmp_path, ws, [LOOP_TEXT, RIGHT])
    res = await GoedelProver(io).run(STMT, ws, 4, config.SamplingSettings(), 240, 16384)
    assert res.ok
    assert "tournait en rond" in job.attempts[0].summary and job.attempts[0].finish == "loop"
    assert len(brain.requests[1]["messages"]) == 1             # restarted from the original task


async def test_loop_reported_by_the_brain_is_handled_the_same(tmp_path, ws):
    ctx, brain, io, job = setup(tmp_path, ws, [{"text": "blah", "finish": "loop"}, RIGHT])
    res = await GoedelProver(io).run(STMT, ws, 4, config.SamplingSettings(), 240, 16384)
    assert res.ok and job.attempts[0].status == "rejected" and lengths(brain) == [1, 1]


def _wrong(tactic: str, pad: str = "") -> str:
    return f"<think>{pad}</think>\nPlan.\n```lean4\ntheorem t (a b : ℕ) (h : a = b) : b = a := by\n  {tactic}\n```"


async def test_same_error_twice_restarts_from_a_fresh_sample(tmp_path, ws):
    ctx, brain, io, job = setup(tmp_path, ws, [WRONG, WRONG, RIGHT])
    res = await GoedelProver(io).run(STMT, ws, 4, config.SamplingSettings(), 240, 24576)
    assert res.ok and lengths(brain) == [1, 3, 1]


async def test_at_most_two_corrections_per_line_of_attack(tmp_path, ws):
    ctx, brain, io, job = setup(tmp_path, ws, [_wrong("exact h"), _wrong("rfl"), _wrong("simp"), RIGHT])
    res = await GoedelProver(io).run(STMT, ws, 5, config.SamplingSettings(), 240, 24576)
    assert res.ok, [(a.status, a.errors_text[:100]) for a in job.attempts]
    assert lengths(brain) == [1, 3, 5, 1]
    rounds = [r["messages"][-1]["content"][:22] for r in brain.requests[1:3]]
    assert rounds == ["The proof (Round 0) is", "The proof (Round 1) is"]


async def test_correction_never_starved_of_tokens(tmp_path, ws):
    ctx, brain, io, job = setup(tmp_path, ws, [_wrong("exact h", pad="x" * 30000), RIGHT])
    res = await GoedelProver(io).run(STMT, ws, 3, config.SamplingSettings(), 240, 16384)
    assert res.ok and lengths(brain) == [1, 1]
    assert all(r["max_tokens"] >= 8192 for r in brain.requests)


async def test_invented_names_are_recalled_in_fresh_samples(tmp_path, ws):
    invented = _wrong("exact my_invented_symm_lemma h")
    ctx, brain, io, job = setup(tmp_path, ws, [invented, invented, RIGHT])
    res = await GoedelProver(io).run(STMT, ws, 4, config.SamplingSettings(), 240, 24576)
    assert res.ok and lengths(brain) == [1, 3, 1]
    first = brain.requests[2]["messages"][0]["content"]
    assert first.startswith("Complete the following Lean 4 code")
    assert "do not use them: `my_invented_symm_lemma`" in first
    assert "do not use them" not in brain.requests[0]["messages"][0]["content"]


async def test_reusing_a_rejected_name_starts_a_fresh_sample(tmp_path, ws):
    a = _wrong("exact my_invented_symm_lemma h")
    b = _wrong("exact (my_invented_symm_lemma h).trans rfl")
    ctx, brain, io, job = setup(tmp_path, ws, [a, b, RIGHT])
    res = await GoedelProver(io).run(STMT, ws, 4, config.SamplingSettings(), 240, 24576)
    assert res.ok and lengths(brain) == [1, 3, 1]
    assert "do not use them: `my_invented_symm_lemma`" in brain.requests[2]["messages"][0]["content"]


async def test_hint_is_the_only_addition_to_the_goedel_prompt(tmp_path, ws):
    ctx, brain, io, job = setup(tmp_path, ws, [RIGHT])
    res = await GoedelProver(io).run(STMT, ws, 1, config.SamplingSettings(), 240, 24576, hint="use Eq.symm")
    p = brain.requests[0]["messages"][0]["content"]
    assert res.ok and p.endswith("\n\nThe user gives this hint for the proof (follow it if it helps): use Eq.symm")


async def test_prover_feedback_names_existing_lemmas(tmp_path, ws):
    """With the real names index: the correction prompt lists real names for an invented one (D25)."""
    import asyncio
    if ws.key != "lean-prover49":
        pytest.skip("names test calibrated on lean-prover49")
    assert await asyncio.to_thread(names.get, ws, True) is not None
    ctx, brain, io, job = setup(tmp_path, ws, [_wrong("exact Eq.symm_of_eq_reversed h"), RIGHT])
    res = await GoedelProver(io).run(STMT, ws, 3, config.SamplingSettings(), 240, 24576)
    assert res.ok
    correction = brain.requests[1]["messages"][-1]["content"]
    assert "Note on unknown names:" in correction and "`Eq.symm_of_eq_reversed` does not exist" in correction


async def test_tokens_are_streamed_on_the_bus(tmp_path, ws):
    ctx, brain, io, job = setup(tmp_path, ws, [RIGHT])
    await GoedelProver(io).run(STMT, ws, 1, config.SamplingSettings(), 240, 24576)
    ctx.bus._flush_tokens()
    toks = [e for e in ctx.bus.ring if e["type"] == "job.token"]
    assert toks and "".join(e["text"] for e in toks) == RIGHT and toks[0]["stage"] == "proof"
