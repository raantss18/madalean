"""S-AN (DECISIONS D46): the conductor corrects what the deterministic repairs cannot — a Calcul cell that failed when
run, a LaTeX article that does not compile — within the request's budget (cap question, fallback to the free chain,
then to today's behaviour); its code needs the same approval as any model code and its LaTeX change is a
suggestion checked by recompiling. A proof found before a « douteux » / « faux » verdict is kept aside and reused by
« Prouver quand même » after a fresh strict Lean check, dropped when the statement is corrected.

Scripted brains (no request leaves the process), fake kernels / Lean; the real XeLaTeX of a dev checkout for the
recompilation check when installed."""
from __future__ import annotations

import asyncio
import json
import shutil

import pytest

from helpers import make_ctx, running, session, wait_idle
from madalean.brain import conductor as C
from madalean.brain.fake_conductor import ConductedFakeBrain, demo_conductor
from madalean.research import conductorfix as cf
from madalean.research import texbuild as tb
from madalean.research import texproject as tp
from madalean.server.plugins import workbench as wbm
from test_calcul_notebook import FakeKernels


@pytest.fixture(autouse=True)
def _clean():
    cf.ASKS.clear()
    cf.REQUESTS.clear()
    cf._TEX_TRIED.clear()                                         # noqa: SLF001
    yield
    cf.ASKS.clear()
    cf.REQUESTS.clear()


def calc_responder(role, messages, brain):
    """The usual Calcul model: writes `print(totl)` (a typo) for « affiche totl »; its own repair is `print(total)`."""
    first = next((m["content"] for m in messages if m.get("role") == "user"), "")
    brain.behaviour["model_fix" if "The cell you wrote failed" in first else "model_write"] = \
        brain.behaviour.get("model_fix" if "The cell you wrote failed" in first else "model_write", 0) + 1
    if "The cell you wrote failed" in first:
        return "```python\nprint(total)\n```"
    return "```python\nprint(totl)\n```"


def _brain(tmp_path, **kw):
    return ConductedFakeBrain(tmp_path / "brain", responder=calc_responder, **kw)


async def _calcul(s, L):
    pid = (await (await s.post(L + "/api/projects", json={"title": "P"})).json())["project"]["id"]
    doc = (await (await s.post(L + f"/api/calcul/{pid}/docs", json={"title": "N", "language": "python"}))
           .json())["doc"]["id"]
    D = L + f"/api/calcul/{pid}/docs/{doc}"
    c1 = (await (await s.post(D + "/cells", json={"source": "total = sum(range(10))"})).json())["cell"]
    assert (await (await s.post(D + f"/cells/{c1['id']}/run")).json())["run"]["status"] == "ok"
    q = (await (await s.post(D + "/cells", json={"type": "ask", "prompt": "affiche totl"})).json())["cell"]
    q = (await (await s.post(D + f"/cells/{q['id']}/ask", json={})).json())["cell"]
    assert q["code"] == "print(totl)"
    assert (await s.post(D + f"/cells/{q['id']}/approve", json={"code_hash": q["code_hash"]})).status == 200
    return pid, doc, D, q


def _setup(ctx):
    ctx.settings.mode = "auto"
    ctx.settings.experiments_auto = False


# ================================================================ Calcul
async def test_calcul_conductor_corrects_needs_approval_then_best_version(tmp_path, monkeypatch):
    fake = FakeKernels()
    monkeypatch.setattr(wbm.Workbench, "kernels", lambda self: fake)
    b = _brain(tmp_path)
    ctx = make_ctx(tmp_path, brain=b)
    async with running(ctx) as (srv, L, _R), session() as s:
        _setup(ctx)
        pid, doc, D, q = await _calcul(s, L)
        j = await (await s.post(D + f"/cells/{q['id']}/run")).json()
        assert j["run"]["status"] == "error" and "totl" in j["run"]["error"]
        fixed = j["autofix"]
        # the conductor (Claude, chosen by its scoring) corrected it; nothing ran: approval first
        assert fixed["code"] == "print(total)" and fixed["approved"] is None and "reran" not in fixed
        af = fixed["autofix"]
        assert af["by"] == "conductor" and af["name"].startswith("Claude") and af["usd"] > 0 and af["what"]
        assert fixed["versions"][-1]["fix"]["by"] == "conductor" and fixed["versions"][-1]["fix"]["usd"] > 0
        assert "model_fix" not in b.behaviour                         # the usual model was not asked
        call = next(x for x in b.calls if x["kind"] == "fix_code")
        assert call["model"].startswith("anthropic:") and call["usd"] > 0
        assert call["messages"][0].get("stable") and "Python 3: print the results" in call["messages"][0]["content"]
        assert "print(totl)" in call["messages"][-1]["content"] and "NameError" in call["messages"][-1]["content"]
        assert call["extra"]["format"]["schema"] == C.FIX_CODE_SCHEMA                   # structured output
        n = len(fake.calls)
        r = await s.post(D + f"/cells/{q['id']}/run")                  # model code: the approval rule is unchanged
        assert r.status == 403 and (await r.json())["error"] == "not_approved" and len(fake.calls) == n
        assert (await s.post(D + f"/cells/{q['id']}/approve", json={"code_hash": fixed["code_hash"]})).status == 200
        j = await (await s.post(D + f"/cells/{q['id']}/run")).json()
        assert j["run"]["status"] == "ok" and j["run"]["stdout"] == "45\n" and fake.calls[-1] == "print(total)"
        # it ran: the best version of the request, the conductor's success measured, Claude never pinned for Calcul
        wb = srv.app[wbm.WB]
        cell = {c["id"]: c for c in (await (await s.get(D)).json())["cells"]}[q["id"]]
        best = wb.recipes.best(cell["intent_key"], "python", "", {"total"})
        assert best and best["code"] == "print(total)" and best["origin"] == "conductor"
        row = next(r for r in C.conductor_of(b).stats.table() if r["decision"] == "codefix")
        assert row["model"].startswith("anthropic:") and row["n"] == 1 and row["ok_rate"] == 1.0
        assert not any(m.startswith("anthropic:") for m in (wb.models.view().get("python") or {}).get("models", {}))
        assert b.ledger.scope_total(cf.calcul_scope(pid, doc, q["id"], "affiche totl")) == pytest.approx(af["usd"], abs=1e-5)


async def test_calcul_conductor_fix_reruns_only_when_model_code_runs_without_approval(tmp_path, monkeypatch):
    fake = FakeKernels()
    monkeypatch.setattr(wbm.Workbench, "kernels", lambda self: fake)
    ctx = make_ctx(tmp_path, brain=_brain(tmp_path))
    async with running(ctx) as (_srv, L, _R), session() as s:
        _setup(ctx)
        _pid, _doc, D, q = await _calcul(s, L)
        ctx.settings.experiments_auto = True
        j = await (await s.post(D + f"/cells/{q['id']}/run")).json()
        assert j["run"]["status"] == "ok" and j["run"]["stdout"] == "45\n"
        assert j["autofix"]["reran"] and j["autofix"]["autofix"]["by"] == "conductor"


async def test_calcul_cap_question_yes_keeps_claude_no_goes_free(tmp_path, monkeypatch):
    for approve in (True, False):
        fake = FakeKernels()
        monkeypatch.setattr(wbm.Workbench, "kernels", lambda self, f=fake: f)
        b = _brain(tmp_path / str(approve))
        ctx = make_ctx(tmp_path / str(approve), brain=b)
        async with running(ctx) as (_srv, L, _R), session() as s:
            _setup(ctx)
            ctx.settings.conductor_cap_usd = 0.0                      # the request's cap is used up at once
            _pid, _doc, D, q = await _calcul(s, L)
            run = asyncio.ensure_future(s.post(D + f"/cells/{q['id']}/run"))
            asks = []
            for _ in range(300):
                asks = (await (await s.get(L + "/api/conductor/asks")).json())["asks"]
                if asks:
                    break
                await asyncio.sleep(0.02)
            assert asks and asks[0]["kind"] == "calcul" and asks[0]["cell_id"] == q["id"] and asks[0]["step"] == 0.5
            aid = asks[0]["id"]
            assert (await s.post(L + f"/api/conductor/asks/{aid}", json={"approve": "yes"})).status == 400
            assert (await s.post(L + f"/api/conductor/asks/{aid}", json={"approve": approve})).status == 200
            assert (await s.post(L + f"/api/conductor/asks/{aid}", json={"approve": approve})).status == 409
            j = await (await run).json()
            af = j["autofix"]["autofix"]
            assert j["autofix"]["code"] == "print(total)" and af["by"] == "conductor"
            if approve:
                assert af["name"].startswith("Claude") and af["usd"] > 0
            else:
                assert not af["name"].startswith("Claude") and af["usd"] == 0      # the next best (free) model
                assert not [x for x in b.calls if x["model"].startswith("anthropic:")]


async def test_calcul_fallbacks_free_then_todays_model(tmp_path, monkeypatch):
    fake = FakeKernels()
    monkeypatch.setattr(wbm.Workbench, "kernels", lambda self: fake)

    b = _brain(tmp_path / "a")
    orig = b.call_model

    async def call_model(key, *a, **k):                # every Claude call is rate limited: the free chain answers
        if key.startswith("anthropic:"):
            from madalean.brain.providers.base import ProviderError
            raise ProviderError("http", "rate limited", 429)
        return await orig(key, *a, **k)
    b.call_model = call_model
    ctx = make_ctx(tmp_path / "a", brain=b)
    async with running(ctx) as (_srv, L, _R), session() as s:
        _setup(ctx)
        _pid, _doc, D, q = await _calcul(s, L)
        j = await (await s.post(D + f"/cells/{q['id']}/run")).json()
        af = j["autofix"]["autofix"]
        assert j["autofix"]["code"] == "print(total)" and af["by"] == "conductor" and af["tier"] == "free"
    # no conductor at all (no Claude key, no capable free model): exactly today's path, the usual model repairs it
    b2 = _brain(tmp_path / "b", claude_key=False, free=False)
    ctx = make_ctx(tmp_path / "b", brain=b2)
    async with running(ctx) as (_srv, L, _R), session() as s:
        _setup(ctx)
        _pid, _doc, D, q = await _calcul(s, L)
        j = await (await s.post(D + f"/cells/{q['id']}/run")).json()
        assert j["autofix"]["code"] == "print(total)" and "by" not in j["autofix"]["autofix"]
        assert b2.calls == [] and b2.behaviour.get("model_fix") == 1
    # local mode: never the conductor
    b3 = _brain(tmp_path / "c")
    ctx = make_ctx(tmp_path / "c", brain=b3)
    async with running(ctx) as (_srv, L, _R), session() as s:
        _setup(ctx)
        ctx.settings.mode = "local"
        _pid, _doc, D, q = await _calcul(s, L)
        j = await (await s.post(D + f"/cells/{q['id']}/run")).json()
        assert "by" not in j["autofix"]["autofix"] and b3.calls == []


async def test_calcul_invalid_conductor_code_falls_back_and_counts_as_a_failure(tmp_path, monkeypatch):
    fake = FakeKernels()
    monkeypatch.setattr(wbm.Workbench, "kernels", lambda self: fake)

    def broken(kind, messages, brain):
        if kind == "fix_code":
            return {"text": json.dumps({"code": "print(total", "what": "x"})}
        return demo_conductor(kind, messages, brain)
    b = _brain(tmp_path, conductor=broken)
    ctx = make_ctx(tmp_path, brain=b)
    async with running(ctx) as (_srv, L, _R), session() as s:
        _setup(ctx)
        _pid, _doc, D, q = await _calcul(s, L)
        j = await (await s.post(D + f"/cells/{q['id']}/run")).json()
        assert j["autofix"]["code"] == "print(total)" and "by" not in j["autofix"]["autofix"]
        assert b.behaviour.get("model_fix") == 1
        row = next(r for r in C.conductor_of(b).stats.table() if r["decision"] == "codefix")
        assert row["ok_rate"] == 0.0


def test_codefix_decision_prefers_opus_on_the_third_try_and_uses_the_sage_card(tmp_path):
    b = ConductedFakeBrain(tmp_path / "cfg")
    c = C.Conductor(b)
    first = c.choose("codefix", "medium", mode="auto", scope=None, prompt_tokens=1500)
    assert first[0].tier != "opus" and first[0].paid
    third = c.choose("codefix", "medium", mode="auto", scope=None, prompt_tokens=1500, attempt=2)
    assert third[0].tier == "opus"
    comp = C.toolcards.compact("fix_sage", frozenset({"plot"}))
    assert "SageMath" in comp.stable and "Python 3" in comp.stable


@pytest.mark.sage
async def test_sage_correction_checked_by_the_installed_sage_and_run_in_it(tmp_path, monkeypatch):
    """The conductor's Sage answer goes through the installed Sage's preparser before it is shown (an invalid one
    falls back to the usual model), and the accepted correction really runs in Sage."""
    import subprocess
    from madalean import syntaxcards
    from madalean.research import codegen
    py = syntaxcards.sage_python()
    if py is None:
        pytest.skip("SageMath not installed")
    monkeypatch.setenv("MADALEAN_NO_SYNTAX_BUILD", "1")
    old = dict(syntaxcards._DIR)                                                    # noqa: SLF001
    syntaxcards.configure(tmp_path / "cache")
    answers = ["R.<x = QQ[]\n(x^4 + 4).factor()", "R.<x> = QQ[]\n(x^4 + 4).factor()"]

    def sage_fix(kind, messages, brain):
        if kind == "fix_code":
            return {"text": json.dumps({"code": answers.pop(0), "what": "anneau de polynômes déclaré."})}
        return demo_conductor(kind, messages, brain)

    def model(role, messages, brain):
        brain.behaviour["model_fix"] = brain.behaviour.get("model_fix", 0) + 1
        return "```sage\nR.<x> = QQ[]\n(x^4 + 4).factor()\n```"
    try:
        b = ConductedFakeBrain(tmp_path / "brain", responder=model, conductor=sage_fix)
        ctx = make_ctx(tmp_path, brain=b)
        ctx.settings.mode = "auto"
        bad = "(x^4 + 4).factor()"
        err = "AttributeError: 'sage.symbolic.expression.Expression' object has no attribute 'factor'"
        kw = dict(language="sage", prompt="factorise x^4+4 sur Q", names=[], context="", owner="t", fix_code=bad,
                  fix_error=err)
        cond = {"scope": "calcul:t", "where": {"kind": "calcul"}, "attempt": 0}
        r = await codegen.transcribe(ctx, **kw, conductor=cond)
        assert r["origin"] != "conductor" and b.behaviour["model_fix"] == 1     # the preparser refused the answer
        r = await codegen.transcribe(ctx, **kw, conductor=cond)
        assert r["origin"] == "conductor" and r["conductor"]["name"].startswith("Claude") and r["valid"]
        src = r["code"].rsplit("\n", 1)
        src = src[0] + "\nprint(" + src[1] + ")"
        p = subprocess.run([py, "-c", "from sage.all import *\nexec(preparse(" + repr(src) + "))"],
                           capture_output=True, text=True,
                           env=syntaxcards._sage_env(tmp_path / "w"), timeout=600)              # noqa: SLF001
        assert "(x^2 - 2*x + 2) * (x^2 + 2*x + 2)" in p.stdout, p.stderr[-1500:]
    finally:
        syntaxcards._DIR.update(old)                                                # noqa: SLF001


# ================================================================ article
def _tex_conductor(kind, messages, brain):
    """First answer: a change that does not fix the error; then the right one."""
    if kind != "fix_latex":
        return demo_conductor(kind, messages, brain)
    brain.behaviour["tex"] = brain.behaviour.get("tex", 0) + 1
    if brain.behaviour["tex"] == 1:
        return {"text": json.dumps({"find": "La valeur", "replace": "Le nombre", "what": "reformulé"})}
    return {"text": json.dumps({"find": "valeur x_1 est", "replace": "valeur $x_1$ est",
                                "what": "formule mise entre $…$."})}


async def _article(s, L):
    pid = (await (await s.post(L + "/api/projects", json={"title": "Article"})).json())["project"]["id"]
    base = L + f"/api/research/projects/{pid}/texproject"
    st = await (await s.get(base)).json()
    return pid, base, st["order"][0]


async def test_article_fix_is_a_suggestion_checked_by_a_recompilation(tmp_path, monkeypatch):
    trials = []

    async def trial(ctx, pid, overrides, timeout=150.0):
        trials.append(dict(overrides))
        text = next(iter(overrides.values()))
        return {"ok": "$x_1$" in text, "diagnostics": [] if "$x_1$" in text else
                [{"severity": "error", "path": "x", "line": 3, "message": "Missing $ inserted"}], "engine": "fake"}
    monkeypatch.setattr(tb, "trial_compile", trial)
    b = ConductedFakeBrain(tmp_path / "brain", conductor=_tex_conductor)
    ctx = make_ctx(tmp_path, brain=b)
    async with running(ctx) as (_srv, L, _R), session() as s:
        ctx.settings.mode = "auto"
        pid, base, path = await _article(s, L)
        src = tp.read_files(ctx, pid)[path] + "\nLa valeur x_1 est positive.\n"
        tp.write_file(ctx, pid, path, src)
        line = src.split("\n").index("La valeur x_1 est positive.") + 1
        res = {"ok": False, "ran": True, "hash": "h1", "diagnostics": [
            {"severity": "error", "path": path, "line": line, "message": "Missing $ inserted.", "fix": None,
             "plain": {"text": "Une formule est hors des $…$"}}]}
        sug = await cf.fix_compile(ctx, pid, res, mode="auto")
        assert sug and sug["kind"] == "compile_fix" and sug["state"] == "pending" and sug["origin"] == "assistant"
        assert sug["find"] == "valeur x_1 est" and sug["replace"] == "valeur $x_1$ est"
        assert sug["meta"]["verified"] == "recompiled" and sug["meta"]["usd"] > 0
        assert sug["meta"]["conductor"].startswith("Claude")
        assert len(trials) == 2 and "Le nombre" in next(iter(trials[0].values()))     # each proposal recompiled
        second = [x for x in b.calls if x["kind"] == "fix_latex"][1]["messages"][-1]["content"]
        assert "still fails" in second                                   # the failure went back to the conductor
        assert tp.read_files(ctx, pid)[path] == src                     # never applied silently
        lst = (await (await s.get(base + "/suggestions?state=pending")).json())["suggestions"]
        assert [x["id"] for x in lst] == [sug["id"]]
        # same source again: not asked twice
        assert await cf.fix_compile(ctx, pid, res, mode="auto") is None
        r = await s.post(base + f"/suggestions/{sug['id']}/accept", json={})
        assert r.status == 200 and "valeur $x_1$ est" in tp.read_files(ctx, pid)[path]
        # an error with a one-click fix, or a build that did not run: no model call
        n = len(b.calls)
        assert not cf.fixable({"ok": False, "ran": True, "diagnostics": [{"severity": "error", "fix": {"kind": "x"}}]})
        assert not cf.fixable({"ok": False, "ran": False, "diagnostics": [{"severity": "error", "fix": None}]})
        assert len(b.calls) == n


@pytest.mark.skipif(not (shutil.which("xelatex") and shutil.which("latexmk")), reason="no system XeLaTeX (dev)")
async def test_article_fix_with_a_real_recompilation(tmp_path):
    b = ConductedFakeBrain(tmp_path / "brain", conductor=_tex_conductor)
    ctx = make_ctx(tmp_path, brain=b)
    events = []
    orig = ctx.publish

    def publish(t, p=None):
        if t in ("article.fix", "article.suggestion"):
            events.append((t, p))
        return orig(t, p)
    ctx.publish = publish
    async with running(ctx) as (_srv, L, _R), session() as s:
        ctx.settings.mode = "auto"
        pid, base, path = await _article(s, L)
        src = tp.read_files(ctx, pid)[path] + "\nLa valeur x_1 est positive.\n"
        tp.write_file(ctx, pid, path, src)
        res = await (await s.post(base + "/compile", json={})).json()
        assert not res["ok"] and res["fixing"] is True
        err = next(d for d in res["diagnostics"] if d["severity"] == "error")
        assert err["fix"] is None and err["path"] == path
        for _ in range(600):
            if any(t == "article.fix" and p.get("state") in ("proposed", "none") for t, p in events):
                break
            await asyncio.sleep(0.1)
        done = next(p for t, p in events if t == "article.fix" and p.get("state") in ("proposed", "none"))
        assert done["state"] == "proposed", events
        assert tp.read_files(ctx, pid)[path] == src                     # the source is untouched
        assert tb.pdf_path(ctx, pid) is None                             # the trial build left no PDF behind
        assert not [p for p in (tb.build_dir(ctx, pid)).iterdir() if p.name.startswith("trial-")]
        sid = done["suggestion"]
        assert (await s.post(base + f"/suggestions/{sid}/accept", json={})).status == 200
        res = await (await s.post(base + "/compile", json={})).json()
        assert res["ok"], res["diagnostics"]


async def test_article_fix_not_started_without_a_conductor(tmp_path):
    ctx = make_ctx(tmp_path)                                             # FakeBrain: no conductor interface
    async with running(ctx) as (_srv, L, _R), session() as s:
        ctx.settings.mode = "auto"
        pid, base, path = await _article(s, L)
        assert cf.available(ctx, "auto") is None
        res = {"ok": False, "ran": True, "hash": "h", "diagnostics": [{"severity": "error", "fix": None,
                                                                      "path": path, "line": 1, "message": "x"}]}
        assert await cf.fix_compile(ctx, pid, res, mode="auto") is None


# ================================================================ a proof kept aside before the verdict
async def _pending_setup(tmp_path, monkeypatch, verdict):
    import test_parallel_stages as tps
    from madalean.pipeline import runner as R
    from madalean.pipeline.verify import CheckResult
    sc = tps.Script()
    sc.verdict, sc.check_delay = verdict, 0.8

    class Checker:
        def __init__(self, io, mode, lean_real=True, use_model=True):
            pass

        async def run(self, problem, understood, statement, ws, *, lang="fr", learn=False):
            sc.check_calls += 1
            await asyncio.sleep(sc.check_delay)
            return CheckResult(verdict=sc.verdict, summary="lecture", seconds=sc.check_delay)
    monkeypatch.setattr(R, "StatementChecker", Checker)
    ctx = await tps.setup(tmp_path, prove_delay=0.0)
    ctx.settings.mathlib_first = False
    warm_calls: list = []
    orig = ctx.lean.check

    async def check(code, ws, timeout_s=180, strict_name=None, owner=None, warm=False):
        warm_calls.append(warm)
        return await orig(code, ws, timeout_s, strict_name, owner=owner, warm=warm)
    ctx.lean.check = check
    return ctx, sc, warm_calls, tps


@pytest.mark.parametrize("verdict", ["doubtful", "false"])
async def test_proof_found_before_the_verdict_is_reused_by_prove_anyway(tmp_path, monkeypatch, verdict):
    ctx, sc, warm, tps = await _pending_setup(tmp_path, monkeypatch, verdict)
    d, job = await tps.submit(ctx)
    await wait_idle(ctx)
    assert job.error == f"statement_{verdict}" and not d.proofs and d.status == "draft"
    p = d.extra["pending_proof"]
    assert p["code"] and p["statement"] == d.statement and p["verdict"] == verdict
    assert not ctx.library.entries                                  # never « vérifiée », never in the library
    assert any(e.params.get("pending") for e in d.events)
    assert d.to_dict()["pending_proof"]["code"] == p["code"]                # saved with the dossier
    prove_calls = ctx.brain.behaviour.get("prove_calls", 0)
    warm.clear()
    job2 = ctx.orchestrator.submit(d.id, [{"stage": "proof", "force": True}])
    await wait_idle(ctx)
    assert job2.state == "done" and d.status == "proved" and d.proof_is_current
    assert ctx.brain.behaviour.get("prove_calls", 0) == prove_calls        # no new search
    meta = d.proofs[d.cur_proof].meta
    assert meta["pending_reused"] and meta["verdict_overridden"] == verdict and meta["axioms"]
    assert warm[0] is False                                         # the re-check is a FRESH strict Lean
    assert "pending_proof" not in d.extra and ctx.library.entries
    assert any(e.kind == "proof" and "mise de côté" in e.text for e in d.events)
    await ctx.stop()


async def test_pending_proof_refused_by_fresh_lean_searches_again(tmp_path, monkeypatch):
    ctx, sc, warm, tps = await _pending_setup(tmp_path, monkeypatch, "doubtful")
    d, job = await tps.submit(ctx)
    await wait_idle(ctx)
    d.extra["pending_proof"]["code"] += "\n#check no_such_lemma"              # Lean will refuse it now
    prove_calls = ctx.brain.behaviour.get("prove_calls", 0)
    job2 = ctx.orchestrator.submit(d.id, [{"stage": "proof", "force": True}])
    await wait_idle(ctx)
    assert job2.state == "done" and d.proof_is_current
    assert not d.proofs[d.cur_proof].meta.get("pending_reused")
    assert ctx.brain.behaviour.get("prove_calls", 0) > prove_calls             # searched again
    assert any(a.kind == "pending" and a.status == "rejected" for a in job2.attempts)
    await ctx.stop()


async def test_pending_proof_dropped_when_the_statement_is_corrected(tmp_path, monkeypatch):
    ctx, sc, warm, tps = await _pending_setup(tmp_path, monkeypatch, "doubtful")
    d, job = await tps.submit(ctx)
    await wait_idle(ctx)
    assert "pending_proof" in d.extra
    async with running(ctx) as (_srv, L, _R), session() as s:
        new = tps.STATEMENT.replace("(hb : Even b)", "(hb : Even b) (hc : 0 < a)")
        r = await s.post(L + f"/api/dossiers/{d.id}/statement", json={"code": new, "check": False})
        assert r.status == 200
        d = ctx.repo.get(d.id)
        assert "pending_proof" not in d.extra and "pending_proof" not in (await (await s.get(
            L + f"/api/dossiers/{d.id}")).json())["dossier"]
    # a stale candidate (statement changed some other way) is never used either
    d.extra["pending_proof"] = {"code": "x", "statement": "theorem other : True := by sorry",
                                "statement_index": d.cur_statement}
    from madalean.pipeline.runner import DossierPipeline
    assert DossierPipeline._pending(d) is None and "pending_proof" not in d.extra     # noqa: SLF001
    await ctx.stop()


async def test_explicit_request_and_faithful_verdict_keep_nothing_aside(tmp_path, monkeypatch):
    ctx, sc, warm, tps = await _pending_setup(tmp_path, monkeypatch, "faithful")
    d, job = await tps.submit(ctx)
    await wait_idle(ctx)
    assert job.state == "done" and d.proof_is_current and "pending_proof" not in d.extra
    await ctx.stop()
