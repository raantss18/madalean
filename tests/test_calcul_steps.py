"""Session S-AJ (DECISIONS D42): « Expliquer les étapes du calcul » — deterministic step probes run in real Sage
(factorisation over F_125, integrals, roots, determinant, solving), the request sent to the model (facts given and
marked, the cell's result, the request and what it was recognized as), the approval rule (model code that was not
approved never reaches a kernel, probe included), the cache and the streaming events."""
from __future__ import annotations

import asyncio
import json
import re
import shutil
import subprocess

import pytest

from helpers import make_ctx, running, session
from madalean import syntaxcards
from madalean.brain.fake import FakeBrain
from madalean.research import explain as ex
from madalean.research import steps
from madalean.research.sagebridge import ExecResult
from madalean.server.plugins import workbench as wbm


# ---------------------------------------------------------------- probes in the real Sage
def run_probes(cases: list[tuple[str, str]], tmp_path) -> list[dict]:
    """Each case's probe program, run by the installed Sage's Python with the kernel's names (sage.all + x)."""
    py = syntaxcards.sage_python()
    if py is None:
        pytest.skip("SageMath not installed")
    prog = "from sage.all import *\nx = SR.var('x')\n" + "\n".join(
        steps.program(code, "sage", steps.probe_op(op, code)) for code, op in cases)
    env = syntaxcards._sage_env(tmp_path / "work")
    p = subprocess.run([py, "-c", prog], capture_output=True, text=True, env=env, timeout=900)
    found = [steps.parse(line) for line in p.stdout.splitlines() if line.startswith(steps.MARK)]
    assert len(found) == len(cases), p.stderr[-2000:]
    return found


def by_key(d: dict) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for f in d["facts"]:
        out.setdefault(f["k"], []).append(f)
    return out


@pytest.mark.sage
def test_probes_compute_and_check_the_steps_in_real_sage(tmp_path):
    cases = [
        ("R.<x> = GF(125)[]\nf = x^6 - 1\nf.factor()", "factor"),                        # F_125[x], from the intent
        ("factor(2^32 + 1)", ""),                                                         # integers, from the code
        ("integrate(x*sin(x), x)", "integrate"),
        ("integral(exp(-x^2), x, -oo, oo)", ""),
        ("R.<x> = QQ[]\n(x^3 - 2).roots(QQbar)", "roots"),
        ("M = matrix(QQ, [[2, 1, 0], [1, 3, 1], [0, 1, 4]])\nM.det()", "det"),
        ("x, y = var('x y')\nsolve([x + y == 3, x - y == 1], x, y)", "solve"),
        ("A = matrix(QQ, [[1, 2], [3, 4]]); b = vector(QQ, [5, 6])\nA.solve_right(b)", ""),
        ("print(factor(360))", ""),
    ]
    gf, fermat, prim, gauss, roots, det, solve, lin, printed = run_probes(cases, tmp_path)
    # factorisation in F_125[x]: degree and field, every factor irreducible, product == f, degrees add up
    assert gf["op"] == "factor" and not gf.get("error")
    k = by_key(gf)
    assert k["poly"][0]["v"]["deg"] == "6" and k["field"][0]["v"]["q"] == "125" and k["field"][0]["v"]["p"] == "5"
    assert len(k["irreducible"]) >= 2 and all(f["ok"] is True for f in k["irreducible"])
    assert k["product"][0]["ok"] is True and k["product"][0]["v"]["deg"] == "6"
    # integers: each factor prime, product == n
    k = by_key(fermat)
    assert [f["v"]["p"] for f in k["prime"]] == ["641", "6700417"] and all(f["ok"] for f in k["prime"])
    assert k["product_int"][0]["ok"] is True and fermat["result"] == "641 * 6700417"
    # integrals: F' == f; definite: F(b) − F(a) == the result (limits at ±∞)
    assert by_key(prim)["antiderivative"][0]["ok"] is True
    k = by_key(gauss)
    assert k["antiderivative"][0]["ok"] is True and k["ftc"][0]["ok"] is True and "pi" in k["ftc"][0]["v"]["val"]
    # roots: f(r) == 0 and the minimal polynomial of each algebraic root
    k = by_key(roots)
    assert len(k["root"]) == 3 and all(f["ok"] is True for f in k["root"])
    assert all(f["v"]["minpoly"] == "x^{3} - 2" for f in k["root"]) and k["root_count"][0]["v"]["mult"] == "3"
    # determinant: triangular form, det(P) · product of the diagonal == det; rank
    k = by_key(det)
    assert det["result"] == "18" and k["triangular"][0]["ok"] is True and k["rank"][0]["v"]["r"] == "3"
    # solving: substitution; A x = b with a trivial kernel (unique solution)
    k = by_key(solve)
    assert k["substitution"][0]["ok"] is True and k["substitution"][0]["v"]["sol"] == "x = 2, y = 1"
    k = by_key(lin)
    assert k["linear_check"][0]["ok"] is True and k["kernel_dim"][0]["v"]["d"] == "0"
    assert printed["result"] == "2^3 * 3^2 * 5" and by_key(printed)["product_int"][0]["ok"] is True
    # the facts in words, LaTeX in $…$, both languages
    fr = steps.facts_view(gf["facts"], "fr")
    assert all(f["text"].count("$") % 2 == 0 and not re.search(r"(?<!\$)\$\d", f["text"]) for f in fr)
    assert any(f["status"] == "verified" and "irréductible" in f["text"] for f in fr)
    assert any("125" in f["text"] and f["status"] == "computed" for f in fr)
    assert any("irreducible" in f["text"] for f in steps.facts_view(gf["facts"], "en"))


@pytest.mark.sage
def test_probe_never_rebinds_the_kernels_names_and_reports_its_errors(tmp_path):
    cases = [("a = 5\nfactor(a * 6)", ""), ("1 + 1", ""), ("a = 2", "")]
    py = syntaxcards.sage_python()
    if py is None:
        pytest.skip("SageMath not installed")
    prog = ("from sage.all import *\na = 7\n" + "\n".join(steps.program(c, "sage", steps.probe_op(o, c))
                                                         for c, o in cases)
            + "\nprint('A_AFTER', a, '_madalean_steps' in globals(), '_madalean_req' in globals())")
    p = subprocess.run([py, "-c", prog], capture_output=True, text=True, env=syntaxcards._sage_env(tmp_path / "w"),
                       timeout=600)
    found = [steps.parse(line) for line in p.stdout.splitlines() if line.startswith(steps.MARK)]
    assert found[0]["result"] == "2 * 3 * 5" and by_key(found[0])["product_int"][0]["ok"] is True
    assert found[1].get("error") == "no_probe" and found[2].get("error") == "no_final_expression"
    assert "A_AFTER 7 False False" in p.stdout                     # the user's `a` untouched, helpers removed


# ---------------------------------------------------------------- pure helpers
def test_probe_op_from_the_intent_else_the_code():
    assert steps.probe_op("factor", "whatever") == "factor"
    assert steps.probe_op("", "R.<x> = GF(125)[]\n(x^5 + 4*x - 1).factor()") == "factor"
    assert steps.probe_op("", "M = matrix([[1, 2], [3, 4]])\nprint(M.det())  ") == "det"
    assert steps.probe_op("", "integrate(sin(x), x, 0, pi)") == "integrate"
    assert steps.probe_op("", "A.solve_right(b)") == "solve" and steps.probe_op("plot", "plot(sin)") == ""
    assert steps.probe_op("", "# only a comment") == ""


def test_program_carries_the_code_only_as_data():
    code = "print('''x''')\n__import__('os')"
    prog = steps.program(code, "sage", "factor")
    first = prog.split("\n", 1)[0]
    assert first.startswith("_madalean_req = ") and json.loads(eval(first.split(" = ", 1)[1]))["code"] == code
    assert prog.split("\n", 1)[1] == steps.PROBE                   # the rest is Madalean's fixed program


def test_output_match_and_facts_text():
    assert steps.matches_output("641 * 6700417", "641 * 6700417\n")
    assert not steps.matches_output("12", "641 * 6700417") and not steps.matches_output("", "x")
    v = steps.facts_view([{"k": "prime", "ok": True, "v": {"p": "641", "e": "1"}},
                          {"k": "product_int", "ok": False, "v": {"prod": "2", "n": "3"}},
                          {"k": "nope", "ok": True, "v": {}},
                          {"k": "kernel_dim", "ok": None, "v": {"d": "1"}}], "fr")
    assert [f["status"] for f in v] == ["verified", "failed", "computed"]
    assert "infinité" in v[2]["text"]


def test_steps_messages_shape():
    m = ex.steps_messages("sage", "factor(F5)", "641 * 6700417", "fr", "CARD", request="factorise F_5",
                          intent="entier · factorisation", facts=["$641$ est premier."])
    assert m[0]["role"] == "system" and "CARD" in m[0]["content"]
    u = m[1]["content"]
    assert "ÉTAPES MATHÉMATIQUES" in u and "Demande : factorise F_5" in u and "Reconnu : entier" in u
    assert "641 * 6700417" in u and "Faits vérifiés par Sage" in u and "- $641$ est premier." in u
    u = ex.steps_messages("python", "1+1", "2", "en", "")[1]["content"]
    assert "MATHEMATICAL STEPS" in u and "No fact verified by Sage" in u and "Request:" not in u
    long = "a" * 5000 + "RESULT"
    assert ex.clip_output(long).endswith("RESULT") and len(ex.clip_output(long)) < 3100
    for bad in (("lean", "x", "1"), ("sage", "", "1"), ("sage", "x", " ")):
        with pytest.raises(ex.ExplainError):
            ex.steps_messages(bad[0], bad[1], bad[2], "fr", "")
    assert ex.clean_steps("Voici :\n1. a\n2. b\n```sage\nx\n```") == "1. a\n2. b"
    # « $641$ » would be read as money by the Markdown renderer: an empty group first; display maths untouched
    assert steps.inline_delims("$641$ divise $F_5$ ; $ x $ ; $$1+x^2$$") == "${}641$ divise $F_5$ ; $x$ ; $$1+x^2$$"


# ---------------------------------------------------------------- through the server, fake model and kernel
class ProbeKernels:
    """Records every program that would run; answers the probe with canned facts."""

    def __init__(self, result: str = "641 * 6700417"):
        self.calls: list[str] = []
        self.result = result

    async def status(self, path):
        return {"kernel": "", "state": "none"}

    async def probe(self, path, language, program, *, timeout):
        self.calls.append(program)
        out = {"op": "factor", "result": self.result, "facts": [
            {"k": "prime", "ok": True, "v": {"p": "641", "e": "1"}},
            {"k": "prime", "ok": True, "v": {"p": "6700417", "e": "1"}},
            {"k": "product_int", "ok": True, "v": {"prod": "641 \\cdot 6700417", "n": "4294967297"}}]}
        return ExecResult("ok", stdout=steps.MARK + json.dumps(out) + "\n", language=language)

    async def execute(self, *a, **kw):
        raise AssertionError("no cell runs in this test")


def steps_responder(role, messages, brain):
    first = next(m["content"] for m in messages if m["role"] == "user")
    assert "ÉTAPES MATHÉMATIQUES" in first or "MATHEMATICAL STEPS" in first
    return "Voici les étapes.\n1. On cherche un diviseur.\n2. $641$ divise $F_5$.\n3. $F_5 = 641 \\cdot 6700417$."


def record(st, pid, doc, cid, text, *, error=False):
    c = st.cell_view(pid, doc, cid)
    up = st.upstream_of(pid, doc, cid)
    outs = ([{"output_type": "error", "ename": "NameError", "evalue": "x", "traceback": []}] if error else
            [{"output_type": "execute_result", "execution_count": 1, "metadata": {}, "data": {"text/plain": text}}])
    st.record_run(pid, cid, ExecResult("error" if error else "ok", language="sage", execution_count=1, outputs=outs),
                  "host", c["code_hash"], doc=doc, upstream=up)


async def test_steps_through_the_server_facts_marked_approval_and_cache(tmp_path, monkeypatch):
    km = ProbeKernels()
    monkeypatch.setattr(wbm.Workbench, "kernels", lambda self: km)
    brain = FakeBrain(steps_responder)
    ctx = make_ctx(tmp_path, brain=brain)
    events: list[dict] = []
    real_publish = ctx.publish

    def publish(t, payload=None):
        if t == "calcul.steps":
            events.append(dict(payload or {}))
        return real_publish(t, payload)
    ctx.publish = publish
    async with running(ctx) as (srv, L, _R), session() as s:
        pid = (await (await s.post(L + "/api/projects", json={"title": "P"})).json())["project"]["id"]
        doc = (await (await s.post(L + f"/api/calcul/{pid}/docs", json={"title": "N", "language": "sage"}))
               .json())["doc"]["id"]
        D = L + f"/api/calcul/{pid}/docs/{doc}"
        st = srv.app[wbm.WB].calc
        # 1. a user cell that ran: the probe runs (Madalean's program around the cell's code), facts are given to
        #    the model and come back marked
        c = (await (await s.post(D + "/cells", json={"source": "F5 = 2^32 + 1\nfactor(F5)"})).json())["cell"]
        await asyncio.to_thread(record, st, pid, doc, c["id"], "641 * 6700417")
        j = await (await s.post(D + f"/cells/{c['id']}/explain", json={"mode": "steps"})).json()
        assert j["verified"] and j["reason"] == "" and j["op"] == "factor" and not j["cached"]
        assert [f["status"] for f in j["facts"]] == ["verified"] * 3 and "${}641$ est premier" in j["facts"][0]["text"]
        assert j["text"].startswith("1. On cherche") and j["text"].endswith("6700417$.") and "${}641$ divise" in j["text"]
        assert len(km.calls) == 1 and km.calls[0].endswith(steps.PROBE) and "factor(F5)" in km.calls[0]
        user = brain.requests[-1]["messages"][1]["content"]
        assert "Faits vérifiés par Sage" in user and "${}6700417$ est premier" in user and "641 * 6700417" in user
        assert [e["state"] for e in events][0] == "start" and events[-1]["state"] == "done"
        assert all(e["cell_id"] == c["id"] for e in events)
        # 2. the same cell again: cached, no model call, no probe
        n = len(brain.requests)
        j2 = await (await s.post(D + f"/cells/{c['id']}/explain", json={"mode": "steps"})).json()
        assert j2["cached"] and j2["text"] == j["text"] and len(brain.requests) == n and len(km.calls) == 1
        # 3. model code that was NOT approved (a request cell with an output): never sent to a kernel, the
        #    explanation is model-only (unverified), with the request and what it was recognized as
        q = await asyncio.to_thread(st.add, pid, "R.<x> = GF(125)[]\n(x^6 - 1).factor()", "", "assistant",
                                    kind="ask", prompt="factorise x^6-1 dans F_125[x]", doc=doc)
        await asyncio.to_thread(record, st, pid, doc, q["id"], "(x + 1) * (x + 4) * (x^2 + x + 1) * (x^2 + 4*x + 1)")
        j = await (await s.post(D + f"/cells/{q['id']}/explain", json={"mode": "steps"})).json()
        assert not j["verified"] and j["reason"] == "not_approved" and j["facts"] == [] and j["op"] == "factor"
        assert len(km.calls) == 1                                      # nothing ran
        user = brain.requests[-1]["messages"][1]["content"]
        assert "Demande : factorise x^6-1" in user and "Reconnu :" in user and "F₁₂₅" in user
        assert "Aucun fait vérifié" in user
        # …approved: the probe runs (but its recomputed value differs from the output here: facts dropped)
        qv = await asyncio.to_thread(st.cell_view, pid, doc, q["id"])
        await s.post(D + f"/cells/{q['id']}/approve", json={"code_hash": qv["code_hash"]})
        j = await (await s.post(D + f"/cells/{q['id']}/explain", json={"mode": "steps"})).json()
        assert len(km.calls) == 2 and j["reason"] == "differs" and not j["verified"]
        # 4. no successful result: refused; an edited cell (output of older code): refused
        e = (await (await s.post(D + "/cells", json={"source": "foo(1)"})).json())["cell"]
        await asyncio.to_thread(record, st, pid, doc, e["id"], "", error=True)
        r = await s.post(D + f"/cells/{e['id']}/explain", json={"mode": "steps"})
        assert r.status == 409 and (await r.json())["error"] == "no_result"
        await s.patch(D + f"/cells/{c['id']}", json={"source": "factor(2^64 + 1)"})
        r = await s.post(D + f"/cells/{c['id']}/explain", json={"mode": "steps"})
        assert r.status == 409
        # 5. the generic endpoint: model only, never a kernel
        j = await (await s.post(L + "/api/code/explain", json={"language": "sage", "code": "factor(6)",
                                                               "output": "2 * 3", "mode": "steps"})).json()
        assert j["reason"] == "no_kernel" and not j["verified"] and j["text"].startswith("1.")
        assert len(km.calls) == 2
        r = await s.post(L + "/api/code/explain", json={"language": "sage", "code": "factor(6)", "mode": "steps"})
        assert r.status == 400                                         # no output to explain


async def test_steps_from_another_device_never_probe(tmp_path, monkeypatch):
    km = ProbeKernels()
    monkeypatch.setattr(wbm.Workbench, "kernels", lambda self: km)
    ctx = make_ctx(tmp_path, brain=FakeBrain(steps_responder))
    monkeypatch.setattr(wbm, "_exec_allowed", lambda request: wbm.error(403, "experiments_host_only"))
    async with running(ctx) as (srv, L, _R), session() as s:
        pid = (await (await s.post(L + "/api/projects", json={"title": "P"})).json())["project"]["id"]
        doc = (await (await s.post(L + f"/api/calcul/{pid}/docs", json={"title": "N", "language": "sage"}))
               .json())["doc"]["id"]
        D = L + f"/api/calcul/{pid}/docs/{doc}"
        c = (await (await s.post(D + "/cells", json={"source": "factor(2^32 + 1)"})).json())["cell"]
        await asyncio.to_thread(record, srv.app[wbm.WB].calc, pid, doc, c["id"], "641 * 6700417")
        j = await (await s.post(D + f"/cells/{c['id']}/explain", json={"mode": "steps"})).json()
        assert j["reason"] == "host_only" and km.calls == []


@pytest.mark.sage
@pytest.mark.skipif(not (shutil.which("sage") and shutil.which("jupyter-lab")), reason="sage / jupyter-lab missing")
async def test_steps_in_the_real_sandboxed_sage_kernel(tmp_path):
    """The production path: the cell runs in the sandboxed Sage kernel, the probe runs in the same kernel outside
    its history (the user's `_` and names are unchanged), facts reach the model."""
    brain = FakeBrain(steps_responder)
    ctx = make_ctx(tmp_path, brain=brain)
    async with running(ctx) as (_s, L, _R), session() as s:
        pid = (await (await s.post(L + "/api/projects", json={"title": "P"})).json())["project"]["id"]
        doc = (await (await s.post(L + f"/api/calcul/{pid}/docs", json={"title": "S", "language": "sage"}))
               .json())["doc"]["id"]
        D = L + f"/api/calcul/{pid}/docs/{doc}"
        await ctx.jupyter.start()
        ctx.research.bridge.install_specs()
        c = (await (await s.post(D + "/cells", json={"source": "R.<x> = GF(125)[]\nf = x^6 - 1\nf.factor()"}))
             .json())["cell"]
        j = await (await s.post(D + "/run", json={"all": True, "timeout": 300})).json()
        assert j["stopped"] is None, j
        j = await (await s.post(D + f"/cells/{c['id']}/explain", json={"mode": "steps"})).json()
        assert j["verified"] and j["reason"] == "", j
        keys = [f["key"] for f in j["facts"]]
        assert keys[:2] == ["poly", "field"] and keys.count("irreducible") >= 2 and keys[-1] == "product"
        assert all(f["status"] in ("verified", "computed") for f in j["facts"])
        assert "Faits vérifiés par Sage" in brain.requests[-1]["messages"][1]["content"]
        c2 = (await (await s.post(D + "/cells", json={"source": "print(_ is not None, f.degree())"})).json())["cell"]
        r = (await (await s.post(D + f"/cells/{c2['id']}/run")).json())["run"]
        assert "True 6" in r["stdout"], r
        await s.post(D + "/shutdown")
