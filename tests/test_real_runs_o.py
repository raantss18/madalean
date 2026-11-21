"""Session S-O: defects seen on the user's real runs of 2026-11-21 (no Lean, no network: fake servers and fake IO).
The real-Lean Riesz regression lives in test_statement_check.py."""
from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path

import pytest

from madalean.brain.catalogue import Catalogue, CatalogueStore, Model, Provider, dedupe_aliases, is_text_chat
from madalean.pipeline import mathlib_first as MF
from madalean.pipeline import tournament as T
from test_brain_fakes import FakeServer, free_provider, make_brain, model, oa_stream, run, write_catalogue


# ---------------------------------------------------------------- 1. Mathlib-first: multi-line templates
def test_mathlib_template_proof_indents_every_line():
    tac = MF.TEMPLATES[4].format(n="FiniteDimensional.of_isCompact_closedBall₀")
    txt = MF.proof_text("riesz", tac)
    assert txt.split("\n")[0] == "theorem riesz := by"
    assert all(line.startswith("  ") for line in txt.split("\n")[1:]), txt
    assert "\n  all_goals try assumption\n  all_goals try norm_num" in txt


class _A:
    def __init__(self):
        self.model = self.summary = self.errors_text = self.status = self.code = self.raw = self.finish = ""
        self.gen_seconds = self.compile_seconds = 0.0
        self.tokens = 0


class _Verdict:
    def __init__(self, ok):
        self.ok, self.axioms, self.summary, self.errors, self.reasons = ok, [], "", [], []


class _R:
    def __init__(self, ok, stdout=""):
        self.verdict, self.seconds, self.stdout = _Verdict(ok), 0.1, stdout
        self.timed_out, self.infra_error, self.code = False, "", ""


RIESZ = ("theorem je_veux_que_tu_demontres_2035 (X : Type*) [NormedAddCommGroup X] [NormedSpace ℝ X] [CompleteSpace X] "
         "(h : IsCompact (Metric.closedBall (0 : X) 1)) : FiniteDimensional ℝ X := by sorry")


class _IO:
    """Batch: every `apply` template closes its probe (as real Lean 4.9 did); strict check: accepts a file only when
    every tactic line is indented (Lean's real behaviour on the column-0 lines)."""

    def __init__(self, hang_model=False):
        self.attempts, self.checked, self.hang_model = [], [], hang_model

    def new_attempt(self, stage, kind):
        a = _A()
        self.attempts.append(a)
        return a

    def update_attempt(self, a):
        pass

    async def check(self, code, ws, timeout_s, name):
        if name is None:                       # the batch: answer by JSON messages, one error per non-apply probe
            out = []
            for i, line in enumerate(code.split("\n"), 1):
                if line.startswith("theorem madalean_") and "apply" not in code.split("\n")[i]:
                    out.append(json.dumps({"severity": "error", "pos": {"line": i + 1, "column": 2},
                                           "endPos": None, "data": "type mismatch", "caption": ""}))
            return _R(False, "\n".join(out))
        self.checked.append(code)
        body = code.split(":= by\n", 1)[1].split("#print", 1)[0].strip("\n")
        return _R(all(l.startswith("  ") for l in body.split("\n") if l.strip()))

    async def complete(self, *a, **k):
        if self.hang_model:
            a[2].model = "gemini:gemini-3.8-flash"      # what runner.JobIO.complete records from the « model » event
            await asyncio.sleep(3600)
        raise AssertionError("no model call expected")


class _Retriever:
    async def declaration(self, ws, n):
        return {"name": n, "signature": "{r : ℝ} (rpos : 0 < r) …", "kind": "theorem"}

    async def premises(self, ws, st, k):
        return [{"name": "FiniteDimensional.proper", "kind": "theorem"},
                {"name": "FiniteDimensional", "kind": "structure"}]

    async def search(self, ws, t, k):
        return []


class _WS:
    key = "lean-prover49"


def test_mathlib_first_accepts_riesz_with_a_multiline_template():
    io = _IO()
    res = asyncio.run(MF.MathlibFirst(io, "auto", _Retriever(), use_model=False).run(
        RIESZ, _WS(), ["Riesz : boule unité compacte, espace de Banach de dimension finie"], 90))
    assert res.ok, [a.summary for a in io.attempts]
    assert res.lemma.startswith("FiniteDimensional.of_isCompact_closedBall") and res.source == "template"
    assert "\n  all_goals try assumption" in res.code


def test_mathlib_adapt_timeout_says_why(monkeypatch):
    monkeypatch.setattr(MF, "ADAPT_TIMEOUT", 0.2)
    io = _IO(hang_model=True)
    res = MF.MathlibResult()
    asyncio.run(MF.MathlibFirst(io, "auto", None)._adapt(res, RIESZ, "t", _WS(), [{"name": "X.y"}], 90))
    a = io.attempts[-1]
    assert a.status == "error" and "0.2 s" in a.summary and "gemini:gemini-3.8-flash" in a.errors_text
    assert a.summary != "La génération a échoué."


# ---------------------------------------------------------------- 2. non-chat models, 400 « Live API only »
def test_non_text_models_are_never_candidates(tmp_path):
    for mid in ("gemini-3.1-flash-live-preview", "gemini-3.8-live", "gemini-3.8-live-extended-thinking", "aqa",
                "gemini-2.5-flash-native-audio-preview", "gemini-2.5-flash-preview-tts", "gemini-2.5-flash-image",
                "gemini-embedding-001", "gemini-2.5-computer-use-preview-10-2025", "gemini-robotics-er-2-preview",
                "deep-research-preview-04-2026", "genie-4", "antigravity-preview-latest", "imagen-4.0-generate-001"):
        assert not is_text_chat(mid), mid
    for mid in ("gemini-3.5-flash", "gemini-flash-latest", "gemini-3.1-pro-preview-customtools", "mistral-medium-latest",
                "deliver-1", "olive-7b"):
        assert is_text_chat(mid), mid
    # a catalogue saved by an older version still holding them: filtered when read
    write_catalogue(tmp_path, [free_provider("gemini", "http://127.0.0.1:9")],
                    [model("gemini", "gemini-3.1-flash-live-preview", 0.99), model("gemini", "gemini-3.5-flash", 0.6)])
    st = CatalogueStore(tmp_path / "brain-catalogue.json")
    assert [m.model_id for m in st.with_keys(lambda p: True).models if m.provider == "gemini"] == ["gemini-3.5-flash"]


def test_live_api_400_marks_the_model_unusable_for_months(tmp_path):
    async def main():
        live = {"status": 400, "body": {"error": {"message": (
            "models/gemini-x-preview only supports real-time bidirectional streaming via WebSocket "
            "(bidiGenerateContent). Please use the Gemini Live API (bidiGenerateContent via WebSocket) instead of "
            "generateContent.")}}}
        s1 = await FakeServer([live]).start()
        s2 = await FakeServer([oa_stream("ok")]).start()
        write_catalogue(tmp_path, [free_provider("f1", s1.url), free_provider("f2", s2.url)],
                        [model("f1", "gemini-x-preview", 0.9), model("f2", "m2", 0.5)])
        b = make_brain(tmp_path)
        try:
            c = await b.complete("prove", [{"role": "user", "content": "x"}])
        finally:
            await b.close(); await s1.stop(); await s2.stop()
        assert c.model.key == "f2:m2" and "unusable" in c.fallbacks[0]
        until, why = b.states.pause_of("f1:gemini-x-preview")
        assert why == "unsupported" and until - time.time() > 60 * 86400
        assert "f1:gemini-x-preview" not in [r.key for r in b.pool("prove")]
    run(main())


# ---------------------------------------------------------------- 3. aliases: one contestant per model
def _m(mid, name):
    return Model("mistral", mid, name, True, False, {"chat": 0.6})


def test_aliases_collapse_in_the_catalogue():
    ms = [_m("mistral-medium-latest", "mistral-medium-latest"), _m("mistral-medium", "mistral-medium-latest"),
          _m("mistral-medium-2604", "mistral-medium-latest"), _m("mistral-small-latest", "mistral-small-2603"),
          _m("mistral-small-2603", "mistral-small-2603"), _m("codestral-2508", "codestral-2508"),
          Model("gemini", "gemini-3.5-flash", "Gemini 3.5 Flash", True, False, {}),
          Model("gemini", "gemini-3.6-flash", "Gemini 3.6 Flash", True, False, {})]
    assert [m.model_id for m in dedupe_aliases(ms)] == ["mistral-medium-latest", "mistral-small-2603",
                                                         "codestral-2508", "gemini-3.5-flash", "gemini-3.6-flash"]


def test_tournament_round_never_lists_the_same_model_twice():
    pool = [T.Contestant("gemini:gemini-3.1-flash-lite", "Gemini 3.1 Flash Lite"),
            T.Contestant("mistral:mistral-medium-latest", "mistral-medium-latest"),
            T.Contestant("mistral:mistral-medium-latest", "mistral-medium-latest"),
            T.Contestant("mistral:mistral-medium-3", "mistral-medium-latest"),
            T.Contestant("mistral:mistral-small-2603", "mistral-small-2603")]
    rounds: list[list[str]] = []

    async def run_one(c, k, n, deadline):
        return T.Outcome(c, k, attempts=1, error="no proof")

    cfg = T.Config(contestants=3, max_rounds=3, max_minutes=5)
    t = T.Tournament(cfg, candidates=lambda: list(pool), run=run_one,
                     on_round=lambda k, cs: rounds.append([c.name for c in cs]))
    res = asyncio.run(t.run())
    assert all(len(r) == len(set(r)) for r in rounds), rounds        # no round lists a model twice
    assert "mistral:mistral-medium-3" not in res.tried                # an alias of a model already raced
    assert res.tried.count("mistral:mistral-medium-latest") == 1


# ---------------------------------------------------------------- 4. Gemini thinking: effort + first byte
def test_gemini_gets_a_reasoning_effort_and_a_longer_first_byte(tmp_path, monkeypatch):
    from madalean.brain import engine, guards
    seen = {}
    real = engine.openai_compat.stream_chat

    async def spy(*a, **k):
        seen.setdefault("first", []).append(k["first_byte"])
        return await real(*a, **k)
    monkeypatch.setattr(engine.openai_compat, "stream_chat", spy)

    async def main():
        def first(body):
            if body.get("reasoning_effort") == "medium" and body["model"] == "gemini-3.1-pro-preview":
                return {"status": 400, "body": {"error": {"message": "Invalid value for reasoning_effort"}}}
            return oa_stream("ok")
        s = await FakeServer([first, first, first, first]).start()
        write_catalogue(tmp_path, [free_provider("gemini", s.url)],
                        [model("gemini", "gemini-3.5-flash", 0.9), model("gemini", "gemma-4-31b-it", 0.1)])
        b = make_brain(tmp_path)
        try:
            await b._generate(Model("gemini", "gemini-3.5-flash", "g"), "prove", mode="auto",
                              messages=[{"role": "user", "content": "x"}])
            await b._generate(Model("gemini", "gemini-3.5-flash", "g"), "route", mode="auto",
                              messages=[{"role": "user", "content": "x"}])
            await b._generate(Model("gemini", "gemma-4-31b-it", "g"), "prove", mode="auto",
                              messages=[{"role": "user", "content": "x"}])
            await b._generate(Model("gemini", "gemini-3.1-pro-preview", "g"), "prove", mode="auto",
                              messages=[{"role": "user", "content": "x"}])
        finally:
            await b.close(); await s.stop()
        bodies = [r.body for r in s.requests]
        assert bodies[0]["reasoning_effort"] == "medium" and bodies[1]["reasoning_effort"] == "low"
        assert "reasoning_effort" not in bodies[2]                       # Gemma: no thinking parameter
        assert bodies[3]["reasoning_effort"] == "medium" and "reasoning_effort" not in bodies[4]   # refused → dropped
        assert seen["first"][0] == guards.FIRST_BYTE_REASONING > guards.FIRST_BYTE_ONLINE
        assert seen["first"][2] == guards.FIRST_BYTE_ONLINE
    run(main())


# ---------------------------------------------------------------- 5. formalizer: Goedel's header opens nothing else
def test_formalizer_input_says_which_namespaces_are_open():
    from madalean import leancheck
    t = leancheck.formalize_input("Théorème de Cayley-Hamilton")
    assert "open Polynomial" in t and "`Polynomial R` (never `R[X]`)" in t and "Filter.atTop" in t
    p = leancheck.formalize_prompt(t, "ch")
    assert p.startswith("Please autoformalize") and p.endswith("Think before you provide the lean statement.")


# ---------------------------------------------------------------- 6. PDF export
def test_workspace_info_reads_the_mathlib_checkout_head(tmp_path):
    from madalean.runtime.lean import git_head, workspace_info
    from madalean.workspaces import Workspace
    ws = tmp_path / "lean-prover49"
    (ws / ".git" / "refs" / "heads").mkdir(parents=True)
    (ws / "lakefile.lean").write_text("import Lake\nopen Lake DSL\n\npackage mathlib where\n")
    (ws / "Mathlib.lean").write_text("import Mathlib.Init\n")
    (ws / "lake-manifest.json").write_text(json.dumps({"packages": [{"name": "batteries", "rev": "42b5ddd"}]}))
    (ws / ".git" / "HEAD").write_text("2f65ba7f1a9144b20c8e7358513548e317d26de1\n")
    w = Workspace("lean-prover49", "x", ws, "leanprover/lean4:v4.9.0-rc1", False)
    assert workspace_info(w)["mathlib"] == "2f65ba7f1a91 (checkout)"
    (ws / ".git" / "HEAD").write_text("ref: refs/heads/master\n")
    (ws / ".git" / "packed-refs").write_text("# pack-refs\nabcdef0123456789abcdef0123456789abcdef01 refs/heads/master\n")
    assert git_head(ws) == "abcdef0123456789abcdef0123456789abcdef01"
    # a project that depends on Mathlib keeps reading its manifest
    (ws / "lakefile.lean").write_text("package foo\n")
    assert workspace_info(w)["mathlib"] == ""


def test_informal_proof_without_the_restated_theorem():
    from madalean.export import strip_restated_theorem as st
    assert st("**Théorème.** Soit $K$ compact.\n\n**Démonstration.** Puisque $K$ est compact…") == \
        "Puisque $K$ est compact…"
    assert st("Théorème. Soit u.\n\nDémonstration. Soit ε > 0.") == "Soit ε > 0."
    assert st("### Theorem\nLet x.\n\n### Proof\nTake y.") == "Take y."
    assert st("Preuve : évident.") == "Preuve : évident."           # nothing restated: untouched
    assert st("On applique la Démonstration de X.") == "On applique la Démonstration de X."
    assert st("Soit x.\n\n**Preuve.** du lemme") == "Soit x.\n\n**Preuve.** du lemme"     # not a restatement


def test_annex_numbering_is_continuous():
    from madalean import texio
    md = ("### 3. Commentaire des étapes\n\n1. **`rw`** : a\n\n2. **`intro`** : b\n   - sous-point\n   - autre\n\n"
          "3. **`obtain`** : c\n\nUn paragraphe.\n\n4. **`exact`** : d")
    tex = texio.sanitize_markdown(md)
    assert tex.count("\\begin{enumerate}") == 2 and tex.count("\\item") == 6
    assert "\\begin{itemize}" in tex and tex.index("\\begin{itemize}") < tex.index("obtain")
    assert "\\setcounter{enumi}{3}" in tex
    html = texio.markdown_to_html("1. a\n\n2. b\n\ntexte\n\n3. c")
    assert html.count("<ol") == 2 and '<ol start="3">' in html
