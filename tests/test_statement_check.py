"""« Vérifier l'énoncé » and « Chercher dans Mathlib d'abord » (S-K) with a scripted model and the REAL Lean 4.9
compiler + the real Mathlib index (lean-prover49). The user's real failures of 2026-11-21: a compact set without
« non vide » (false: Lean proves the negation with K = ∅), two subsequences converging without « same limit »
(false: the model's counterexample (-1)^n, checked by Lean), Cayley-Hamilton and E/ker f ≅ Im f (in Mathlib)."""
from __future__ import annotations

import asyncio
import json
import os
import tempfile
import time
from pathlib import Path

import pytest

from madalean.brain import rag
from madalean.brain.fake import FakeBrain, demo_responder
from madalean.pipeline import verify as V
from madalean.server.routes_work import create_dossier
from helpers import make_ctx, started, wait_idle

CACHE = Path(tempfile.gettempdir()) / f"madalean-brain-test-{os.getuid()}"     # shared with test_brain_rag

COMPACT = ("theorem t (K : Set ℝ) (hK : IsCompact K) (f : ℝ → ℝ) (hf : ContinuousOn f K) : "
           "BddAbove (f '' K) ∧ (∃ x ∈ K, ∀ y ∈ K, f y ≤ f x) := by sorry")
SUBSEQ = ("theorem t (u : ℕ → ℝ) (h1 : ∃ l, Filter.Tendsto (fun n => u (2 * n)) Filter.atTop (nhds l)) "
          "(h2 : ∃ l, Filter.Tendsto (fun n => u (2 * n + 1)) Filter.atTop (nhds l)) : "
          "∃ l, Filter.Tendsto u Filter.atTop (nhds l) := by sorry")
CAYLEY = ("theorem t {K V : Type*} [Field K] [AddCommGroup V] [Module K V] [FiniteDimensional K V] (f : V →ₗ[K] V) : "
          "Polynomial.aeval f (LinearMap.charpoly f) = 0 := by sorry")
QUOT = ("theorem t {K E F : Type*} [Field K] [AddCommGroup E] [Module K E] [AddCommGroup F] [Module K F] "
        "(f : E →ₗ[K] F) : Nonempty ((E ⧸ LinearMap.ker f) ≃ₗ[K] LinearMap.range f) := by sorry")
EASY = "theorem t (a b : ℕ) (ha : Even a) (hb : Even b) : Even (a + b) := by sorry"

SUBSEQ_CEX = """intro h
obtain ⟨l, hl⟩ := h (fun n => (-1 : ℝ) ^ n) ⟨1, by simp [pow_mul]⟩ ⟨-1, by simp [pow_succ, pow_mul]⟩
have e : Filter.Tendsto (fun n : ℕ => 2 * n) Filter.atTop Filter.atTop := (strictMono_mul_left_of_pos (by norm_num : 0 < 2)).tendsto_atTop
have o : Filter.Tendsto (fun n : ℕ => 2 * n + 1) Filter.atTop Filter.atTop := (strictMono_mul_left_of_pos (by norm_num : 0 < 2)).add_const 1 |>.tendsto_atTop
have a : l = 1 := tendsto_nhds_unique (hl.comp e) (by simp [Function.comp, pow_mul])
have b : l = -1 := tendsto_nhds_unique (hl.comp o) (by simp [Function.comp, pow_succ, pow_mul])
linarith"""


def responder(role, messages, brain):
    first = messages[0]["content"]
    if first.startswith("You check a formalization in Lean 4"):
        brain.behaviour.setdefault("fidelity_calls", 0)
        brain.behaviour["fidelity_calls"] += 1
        if brain.behaviour.get("fidelity_never"):
            return {"text": "{}", "delay": 3600}
        if "IsCompact K" in first:
            return json.dumps({"verdict": "false", "summary": "f est bornée et atteint son max sur K.", "issues": [
                {"kind": "missing_hypothesis", "severity": "high",
                 "explanation": "Si K est vide, il n'existe aucun x dans K : la conclusion est fausse.",
                 "fix": "Ajouter l'hypothèse : K est non vide (K.Nonempty)"}], "counterexamples": []})
        if "u (2 * n + 1)" in first:
            cex = [] if brain.behaviour.get("no_cex") else [{"idea": "u n = (-1)^n", "lean": SUBSEQ_CEX}]
            return "```json\n" + json.dumps({"verdict": "false", "summary": "…", "issues": [
                {"kind": "missing_hypothesis", "severity": "high",
                 "explanation": "Les deux limites doivent être égales : (-1)^n est un contre-exemple.",
                 "fix": "Ajouter l'hypothèse : les deux sous-suites ont la même limite"}],
                "counterexamples": cex}) + "\n```"
        return json.dumps({"verdict": "faithful", "summary": "OK", "issues": []})
    if first.startswith("Prove the following Lean 4 theorem (Mathlib)"):
        return "NONE"
    return demo_responder(role, messages, brain)


@pytest.fixture(scope="module")
def retr49():
    from madalean.brain.leanrun import workspace
    if workspace("lean-prover49") is None:
        pytest.skip("lean-prover49 workspace not installed")
    r = rag.LeanRetriever(CACHE, embeddings=False)
    assert asyncio.run(r.ensure("lean-prover49", timeout=900)), r.errors
    return r


async def setup(tmp_path, ws, retriever=None, check=True, mathlib=True):
    ctx = make_ctx(tmp_path, ws=ws, brain=FakeBrain(responder))
    ctx.settings.statement_check, ctx.settings.mathlib_first = check, mathlib
    ctx = await started(ctx)
    ctx.settings.statement_notes = ctx.settings.informal_proof = False
    if retriever is not None:
        ctx.retriever = retriever
    return ctx


async def prove(ctx, statement, problem="", plan=None):
    d, _ = await create_dossier(ctx, {"statement": statement, "problem": problem, "start": False})
    job = ctx.orchestrator.submit(d.id, plan or [{"stage": "proof"}, {"stage": "explanation"}])
    await wait_idle(ctx)
    return d, job


def check_events(d):
    return [e for e in d.events if e.kind == "check"]


def roles(ctx):
    return [r["role"] for r in ctx.brain.requests]


async def test_compact_without_nonempty_is_false_by_lean_with_the_empty_set(tmp_path, ws):
    ctx = await setup(tmp_path, ws)
    t0 = time.monotonic()
    d, job = await prove(ctx, COMPACT, "fonction continue sur un compact de ℝ : bornée et atteint ses bornes")
    ev = check_events(d)
    assert len(ev) == 1 and ev[0].params["verdict"] == "false", [(e.kind, e.text) for e in d.events]
    assert ev[0].params["evidence"]["kind"] == "counterexample" and "∅" in ev[0].params["evidence"]["code"]
    assert ev[0].params["fix"].startswith("Ajouter l'hypothèse : K est non vide")
    assert "prove" not in roles(ctx) and not d.proof and job.error == "statement_false"
    chk = d.statements[d.cur_statement].meta["check"]
    assert chk["verdict"] == "false" and chk["issues"][0]["checked"] == "lean"
    assert time.monotonic() - t0 < 240
    # the automatic chain stops again, without re-checking; « Prouver quand même » goes on
    n = ctx.brain.behaviour["fidelity_calls"]
    job2 = ctx.orchestrator.submit(d.id, [{"stage": "proof"}])
    await wait_idle(ctx)
    assert job2.error == "statement_false" and ctx.brain.behaviour["fidelity_calls"] == n
    job3 = ctx.orchestrator.submit(d.id, [{"stage": "proof", "force": True}])
    await wait_idle(ctx)
    assert job3.error != "statement_false" and any(a.stage == "proof" for a in job3.attempts)
    await ctx.stop()


async def test_subsequences_false_with_the_models_counterexample_checked_by_lean(tmp_path, ws):
    ctx = await setup(tmp_path, ws, mathlib=False)
    d, job = await prove(ctx, SUBSEQ, "si (U2n+1) et (U2n) convergent alors (Un) converge")
    ev = check_events(d)[-1]
    assert ev.params["verdict"] == "false" and "(-1 : ℝ) ^ n" in ev.params["evidence"]["code"], ev.text
    assert "même limite" in ev.params["fix"] and job.error == "statement_false"
    # without a valid counterexample from the model, the same answer only makes the statement « douteux »
    ctx.brain.behaviour["no_cex"] = True
    d2, job2 = await prove(ctx, SUBSEQ, "si (U2n+1) et (U2n) convergent alors (Un) converge")
    assert check_events(d2)[-1].params["verdict"] == "doubtful" and job2.error == "statement_doubtful"
    await ctx.stop()


async def test_true_easy_statement_passes_untouched(tmp_path, ws):
    ctx = await setup(tmp_path, ws, mathlib=False)
    d, job = await prove(ctx, EASY, "la somme de deux pairs est paire")
    ev = check_events(d)
    assert ev and ev[-1].params["verdict"] == "faithful" and not job.error, (job.error, [e.text for e in d.events])
    assert d.proof_is_current and "prove" in roles(ctx)
    await ctx.stop()


async def test_mathlib_first_cayley_hamilton_and_first_isomorphism(tmp_path, ws, retr49):
    ctx = await setup(tmp_path, ws, retriever=retr49, check=False)
    d, job = await prove(ctx, CAYLEY, "théorème de Cayley-Hamilton")
    assert d.proof_is_current, [(a.kind, a.summary, a.errors_text[:300]) for a in job.attempts]
    p = d.proofs[d.cur_proof]
    assert p.model == "mathlib:LinearMap.aeval_self_charpoly" and p.meta["mathlib_lemma"] == "LinearMap.aeval_self_charpoly"
    assert "prove" not in roles(ctx)
    assert any("Ce théorème est dans Mathlib sous le nom « LinearMap.aeval_self_charpoly »" in e.text for e in d.events)
    expl = [r for r in ctx.brain.requests if r["role"] == "explain"][-1]["messages"][-1]["content"]
    assert "LinearMap.aeval_self_charpoly" in expl
    d2, job2 = await prove(ctx, QUOT, "E/ker f ≅ Im f, premier théorème d'isomorphisme")
    assert d2.proof_is_current and d2.proofs[-1].meta["mathlib_lemma"] == "LinearMap.quotKerEquivRange", \
        [(a.kind, a.summary) for a in job2.attempts]
    await ctx.stop()


async def test_formalizer_gets_the_mathlib_statement_as_reference(tmp_path, ws, retr49):
    ctx = await setup(tmp_path, ws, retriever=retr49, check=False, mathlib=True)
    d, job = await create_dossier(ctx, {"problem": "Démontrer le théorème de Cayley-Hamilton.", "start": False})
    ctx.orchestrator.submit(d.id, [{"stage": "statement"}])
    await wait_idle(ctx)
    form = [r for r in ctx.brain.requests if r["role"] == "formalize"][0]["messages"][0]["content"]
    assert "LinearMap.aeval_self_charpoly" in form and "aeval f f.charpoly = 0" in form
    await ctx.stop()


async def test_time_caps_model_that_never_answers(tmp_path, ws, monkeypatch):
    monkeypatch.setattr(V, "MODEL_TIMEOUT", 3)
    ctx = await setup(tmp_path, ws, mathlib=False)
    ctx.brain.behaviour["fidelity_never"] = True
    t0 = time.monotonic()
    d, job = await prove(ctx, COMPACT, "compact", plan=[{"stage": "verify"}])
    assert check_events(d)[-1].params["verdict"] == "false"         # Lean alone still decides
    assert time.monotonic() - t0 < 120 and not ctx.slots.holders["lean"] and not ctx.slots.holders["online"]
    await ctx.stop()


def test_probe_helpers():
    from madalean.pipeline import probes as P
    s = P.split_statement("theorem foo (n : ℕ) (h : 0 < n) : ∀ m : ℕ, m + n > m := by sorry")
    assert s.binders == "(n : ℕ) (h : 0 < n)" and s.concl.startswith("∀ m : ℕ")
    assert s.negation() == "¬ (∀ (n : ℕ) (h : 0 < n), ∀ m : ℕ, m + n > m)"
    assert P.split_statement("theorem bar : 1 + 1 = 2 := by sorry").negation() == "¬ (1 + 1 = 2)"
    assert P.explicit_binders("{α : Type*} (K L : Set α) [Fintype α] (f : α → ℝ)")[1:] == [
        ("K", "Set α"), ("L", "Set α"), ("f", "α → ℝ")]
    assert V.parse_json_answer('<think>x</think>```json\n{"verdict": "doubtful", "issues": [],}\n```')["verdict"] == "doubtful"
    assert V.clean_tactics("```lean4\ntheorem x : ¬ P := by\n  intro h\n  simp at h\n```") == "intro h\nsimp at h"


def test_fix_from_the_degenerate_instance():
    assert V.degenerate_fix("K = ∅, f = fun _ => 0") == "Ajouter l'hypothèse : K est non vide (K.Nonempty)"
    assert V.degenerate_fix("n = 0", "en") == "Add the hypothesis: n ≠ 0"
    assert V.degenerate_fix("u n = (-1)^n") == ""
