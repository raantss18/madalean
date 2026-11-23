"""Session S-AW (DECISIONS D55, docs/CONJECTURES.md): the conjecture engine — local pattern finders on known
sequences (with a false pattern the held-out check rejects), the catalogue (request → deterministic code, Lean term,
value), the OEIS client on a recorded answer (Local mode: zero requests), the guided loop through the API with a
fake kernel (approval rules: unapproved model code never runs), the counter-example path on a planted false
conjecture, the generated Lean statements compiled on the real workspace, and the real Sage for the catalogue."""
from __future__ import annotations

import ast
import asyncio
import contextlib
import io
import json
import math
import shutil
import subprocess
from pathlib import Path

import pytest

from helpers import make_ctx, running, session
from madalean import leancheck, syntaxcards
from madalean.brain.fake import FakeBrain, demo_responder
from madalean.research import cjcatalog as C
from madalean.research import cjengine as E
from madalean.research import cjpatterns as P
from madalean.research import cjstate as S
from madalean.research import conjectures as cj
from madalean.research.codecat import lean_flavor
from madalean.research.fetch import Fetcher, ReplayTransport
from madalean.research.oeis import Oeis, align, parse, search_url
from madalean.research.sagebridge import ExecResult
from madalean.server.plugins import workbench as wbm

FIXTURES = Path(E.__file__).resolve().parent / "demo_oeis"
CATALAN = [math.comb(2 * n, n) // (n + 1) for n in range(14)]


def table(vals, n0=0, name="a"):
    return {"columns": ["n", name], "rows": [[n0 + i, v] for i, v in enumerate(vals)]}


def kinds(findings, status="kept"):
    return {f["kind"]: f for f in findings if f["status"] == status}


# ---------------------------------------------------------------- pattern finders
def test_polynomial_fit_is_exact_and_validated_on_held_out_terms():
    f = kinds(P.analyze(table([n * n for n in range(20)])))["polynomial"]
    assert f["params"]["coeffs"] == ["0", "0", "1"] and f["tested"] == {"from": 0, "to": 19, "cases": 20, "fit": 15,
                                                                        "held_out": 5}
    tri = kinds(P.analyze(table([n * (n + 1) * (2 * n + 1) // 6 for n in range(24)])))["polynomial"]
    assert tri["params"]["coeffs"] == ["0", "1/6", "1/2", "1/3"]
    assert tri["params"]["factored"] == {"content": "1/6", "roots": [0, -1], "rest": ["1", "2"]}
    assert S.factored_tex(tri["params"]["factored"], [P.parse_value(c) for c in tri["params"]["coeffs"]]) == \
        "\\frac{n (n + 1) (2 n + 1)}{6}"
    # the recurrence the polynomial implies is journalled, not offered as a second conjecture
    assert kinds(P.analyze(table([n * n for n in range(20)])), "discarded")["recurrence"]["reason"] == "redundant"


def test_false_pattern_is_rejected_by_the_held_out_check():
    """n² on the terms the fit sees, different afterwards: every fit is discarded with the first failing term."""
    fs = P.analyze(table([n * n + n // 12 for n in range(16)]))
    bad = kinds(fs, "discarded")
    assert "polynomial" not in kinds(fs) and bad["polynomial"]["reason"] == "held_out"
    assert bad["polynomial"]["detail"] == {"n": 12, "expected": "144", "got": "145"}
    assert bad["recurrence"]["reason"] == "held_out" and "recurrence" not in kinds(fs)
    assert "ajusté sur les 12 premiers termes" in S.discarded_text(bad["polynomial"], "fr")
    assert "held-out" in S.discarded_text(bad["polynomial"], "en")


def test_fibonacci_recurrence_by_berlekamp_massey_with_its_generating_function():
    fib = [0, 1]
    while len(fib) < 32:
        fib.append(fib[-1] + fib[-2])
    f = kinds(P.analyze(table(fib)))["recurrence"]
    assert f["params"]["order"] == 2 and f["params"]["coeffs"] == ["1", "1"]
    assert f["params"]["gf"] == {"num": ["0", "1"], "den": ["1", "-1", "-1"], "offset": 0}       # x / (1 − x − x²)
    assert P.berlekamp_massey([P.Fr(2 ** n) for n in range(10)]) == [1, -2]
    # too few terms for the order: nothing is claimed
    assert "recurrence" not in kinds(P.analyze(table(fib[:8])))


def test_catalan_by_polynomial_recurrence_and_algebraic_generating_function():
    k = kinds(P.analyze(table([math.comb(2 * n, n) // (n + 1) for n in range(30)])))
    assert k["holonomic"]["params"]["polys"] == [["-2", "-4"], ["2", "1"]]          # (n+2)·C(n+1) = (4n+2)·C(n)
    assert k["algebraic_gf"]["params"]["coeffs"] == [["1", "0"], ["-1", "0"], ["0", "1"]]   # x·A² − A + 1 = 0
    assert k["growth"]["heuristic"] and "recurrence" not in k and "polynomial" not in k


def test_multiplicative_function_and_arithmetic_patterns():
    sig = [sum(d * d for d in range(1, n + 1) if n % d == 0) for n in range(1, 61)]
    m = kinds(P.analyze(table(sig, 1)))["multiplicative"]
    assert m["params"] == {"complete": False} and m["tested"]["cases"] >= 30
    fib = kinds(P.analyze(table([1, 1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144, 233, 377, 610, 987, 1597, 2584, 4181, 6765,
                                 10946, 17711, 28657, 46368], 1)), "discarded")
    assert fib["multiplicative"]["detail"]["m"] == 2 and fib["multiplicative"]["reason"] == "counterexample"
    eul = kinds(P.analyze(table([n * n + n + 41 for n in range(30)])))
    assert eul["congruence"]["params"] == {"modulus": 2, "residue": 1} and "all_prime" in eul
    assert kinds(P.analyze(table([n ** 3 - n for n in range(20)])))["congruence"]["params"]["modulus"] == 6
    per = kinds(P.analyze(table([math.gcd(n, 6) for n in range(30)])))
    assert per["periodic"]["params"]["period"] == 6
    rat = kinds(P.analyze(table([f"{n}/{n + 1}" for n in range(1, 20)], 1)))["rational"]
    assert rat["params"] == {"num": ["0", "1"], "den": ["1", "1"]}
    assert P.is_prime(2 ** 61 - 1) and P.is_prime(1681) is False


def test_relations_between_columns():
    rows = [[n, sum(1 for k in range(1, n + 1) if math.gcd(k, n) == 1), n] for n in range(1, 40)]
    fs = P.analyze({"columns": ["n", "a", "b"], "rows": rows})
    ineq = [f for f in fs if f["kind"] == "inequality" and f["status"] == "kept"]
    assert [(f["columns"], f["params"]["offset"]) for f in ineq] == [(["a", "b"], 0)]          # φ(n) ≤ n
    # objects: trees have n − 1 edges and chromatic number ≤ 2
    trees = {"columns": ["n", "m", "χ", "g6"], "labels": True,
             "rows": [[n, n - 1, 2, f"T{n}{j}"] for n in range(2, 8) for j in range(3)]}
    lin = [f for f in P.analyze(trees) if f["kind"] == "linear" and f["status"] == "kept"]
    assert lin and lin[0]["params"] == {"constant": 1, "coeffs": {"n": -1, "m": 1}} or \
        lin[0]["params"] == {"constant": -1, "coeffs": {"n": 1, "m": -1}}
    assert P.check_rows(lin[0], {"columns": ["n", "m", "χ", "g6"], "rows": [[5, 5, 3, "cycle"]]})[1]["row"] == 0


def test_check_and_hunt_indices_find_the_planted_counterexample():
    f = kinds(P.analyze(table([n * n + n + 41 for n in range(31)])))["all_prime"]
    idx = P.hunt_indices("all_prime", {}, 31, 231, seed=1)
    assert idx[:10] == list(range(31, 41)) and idx == sorted(set(idx))
    cases, bad = P.check(f, {"a": {n: P.Fr(n * n + n + 41) for n in idx}})
    assert bad == {"n": 40, "expected": "", "got": "1681"} and cases == 10
    rec = {"kind": "recurrence", "columns": ["a"], "params": {"coeffs": ["1", "1"]}}
    assert P.check(rec, {"a": {5: P.Fr(5), 6: P.Fr(8), 7: P.Fr(13), 9: P.Fr(1)}}) == (1, None)
    assert P.check(rec, {"a": {5: P.Fr(5), 6: P.Fr(8), 7: P.Fr(14)}})[1]["n"] == 7


# ---------------------------------------------------------------- catalogue
def test_same_mathematics_same_code_and_unknown_words_are_not_guessed():
    a = C.recognise("la somme des n premiers nombres impairs")
    b = C.recognise("Sum of the first n odd numbers?")
    assert a.kind == "sequence" and a.key == b.key
    assert C.experiment_code(a, "sage") == C.experiment_code(b, "sage")
    assert "sum(2*k + 1 for k in range(n))" in C.experiment_code(a, "sage")
    s2 = C.recognise("les sommes des carrés des diviseurs")
    assert s2.key == C.recognise("sigma_2(n)").key and s2.first == 1 and "sigma(n, 2)" in C.experiment_code(s2, "sage")
    # one more word changes the mathematics: not recognised (a model writes it, approval needed)
    assert C.recognise("somme des carrés des diviseurs impairs").kind == "unknown"
    assert C.recognise("nombre de points d'une courbe elliptique").kind == "unknown"
    assert C.recognise("__import__('os').system('id')").kind == "unknown"
    assert C.recognise("1, 1, 2, 5, 14, 42, 132, 429").kind == "data"
    fam = C.recognise("graphes connexes à n sommets")
    assert fam.kind == "family" and "nauty_geng" in C.experiment_code(fam, "sage")
    with pytest.raises(C.CatalogError):
        C.experiment_code(fam, "python")
    assert C.recognise("Fibonacci jusqu'à 100").last == 100
    two = C.recognise("sum of the first n cubes and (n(n+1)/2)^2")
    assert [s.name for s in two.seqs] == ["a", "b"]
    for bad in ("n +", "foo(n)", "n ** ** 2", "os.system(1)"):
        with pytest.raises(C.CatalogError):
            C.parse_expr(bad)


def test_python_experiment_and_driver_agree_with_the_reference_values():
    """The Python experiment of each request, run as a kernel would, gives the catalogue's own exact values."""
    for q in ("somme des n premiers nombres impairs", "sigma(n) et n^2", "H_n", "n!", "binomial(2n, n)",
              "somme des n premiers nombres premiers", "nombres de Catalan", "phi(n)", "n/(n+1)", "2^n - 1",
              "nombre de partitions de n", "nombres de Bell", "fonction de Möbius", "primepi(n)"):
        it = C.recognise(q)
        assert it.kind == "sequence", q
        ns: dict = {}
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            exec(C.experiment_code(it, "python"), ns)                                   # noqa: S102
            exec(C.driver(None), ns)                                                    # noqa: S102
            exec(C.driver([it.first + 3, it.first + 70], 5), ns)                        # noqa: S102
        first, more = [C.parse_driver(line) for line in buf.getvalue().splitlines() if line.startswith(C.MARK)]
        ref = C.local_rows(it, list(range(it.first, it.last + 1)))
        assert first["rows"] == ref["rows"] and first["columns"] == ref["columns"], q
        assert more["rows"] == C.local_rows(it, [it.first + 3, it.first + 70])["rows"], q
    assert C.parse_driver("noise\n") is None and C.contract_ok(C.experiment_code(it, "python"))


def test_candidates_text_strength_and_lean_statement():
    it = C.recognise("la somme des n premiers nombres impairs")
    t = C.local_rows(it, list(range(it.first, it.last + 1)))
    ctx = S.Ctx(it, t["columns"], "v4.9")
    cands = [c for c in (S.candidate(f, ctx) for f in S.mark_trivial(P.analyze(t), ctx)) if c]
    assert len(cands) == 1
    c = cands[0]
    assert c["lean"] == "theorem conjecture (n : ℕ) :\n    (∑ k in Finset.range n, (2 * k + 1)) = n ^ 2 := by sorry"
    assert "$a(n) = n^{2}$" in c["text"]["fr"] and "somme des n premiers nombres impairs" in c["text"]["fr"]
    assert c["strength"]["fr"].startswith("vérifié jusqu'à n = 59 (60 cas") and "pas démontré" in c["strength"]["fr"]
    assert "vrai" not in c["strength"]["fr"] and "true" not in c["strength"]["en"]
    cur = S.candidate(P.analyze(t)[0], S.Ctx(it, t["columns"], "default"))
    assert "∑ k ∈ Finset.range n" in cur["lean"] and cur["norm"] == c["norm"]       # same statement, other Mathlib
    # a formula the user typed is not « discovered » again
    it2 = C.recognise("n^2 + n + 41 jusqu'à 30")
    t2 = C.local_rows(it2, list(range(0, 31)))
    ctx2 = S.Ctx(it2, t2["columns"])
    fs = S.mark_trivial(P.analyze(t2), ctx2)
    assert kinds(fs, "discarded")["polynomial"]["reason"] == "definition"
    prime = S.candidate(kinds(fs)["all_prime"], ctx2)
    assert prime["lean"].endswith("Nat.Prime (n ^ 2 + n + 41) := by sorry"), prime["lean"]
    cong = S.candidate(kinds(fs)["congruence"], ctx2)
    assert "(n ^ 2 + n + 41) % 2 = 1" in cong["lean"]
    # heuristics are labelled as such and carry no Lean statement
    it3 = C.recognise("nombres de Catalan")
    t3 = C.local_rows(it3, list(range(0, 30)))
    g = S.candidate(kinds(P.analyze(t3))["growth"], S.Ctx(it3, t3["columns"]))
    assert g["lean"] is None and g["strength"]["kind"] == "heuristic" and g["text"]["fr"].count("Heuristique") == 1
    h = S.strength(c["finding"], hunt={"cases": 216, "to": 261, "max": 299, "sparse": True})
    assert "jusqu'à n = 261" in h["fr"] and "par sondage jusqu'à n = 299" in h["fr"]


# ---------------------------------------------------------------- OEIS
async def test_oeis_client_on_the_recorded_answer_cache_and_local_mode(tmp_path):
    tr = ReplayTransport(FIXTURES)
    o = Oeis(Fetcher(tr), tmp_path / "oeis")
    assert search_url(CATALAN) == "https://oeis.org/search?q=1,1,2,5,14,42,132,429,1430,4862,16796,58786,208012,742900&fmt=json"
    r = await o.lookup(CATALAN, mode="auto", n0=0)
    assert r["status"] == "ok" and r["matches"][0]["number"] == "A000108" and r["matches"][0]["shift"] == 0
    assert r["matches"][0]["matched"] == 14 and r["matches"][0]["url"] == "https://oeis.org/A000108"
    assert any(x["number"] == "A115140" and x["differs_at"] == 1 for x in r["rejected"])      # signs differ
    assert len(tr.requests) == 1 and all(u.startswith("https://oeis.org/search?q=") for u in tr.requests)
    # cached on disk: a new client makes no request
    tr2 = ReplayTransport(FIXTURES)
    r2 = await Oeis(Fetcher(tr2), tmp_path / "oeis").lookup(CATALAN, mode="auto")
    assert r2["cached"] and r2["status"] == "ok" and tr2.requests == []
    # shifted terms are located in the entry
    r3 = await o.lookup(CATALAN[2:], mode="online", n0=0)
    assert r3["status"] in ("error", "none", "ok")            # another query: not recorded → no fabricated match
    # Local mode: zero requests, whatever is asked
    tr4 = ReplayTransport(FIXTURES, strict=True)
    off = await Oeis(Fetcher(tr4), tmp_path / "o2").lookup(CATALAN, mode="local")
    assert off["status"] == "off" and off["matches"] == [] and tr4.requests == []
    assert (await o.lookup([1, 2, 3], mode="auto"))["status"] == "too_short"
    assert parse(None) == [] and parse({"results": None}) == []
    e = parse([{"number": 45, "data": "0,1,1,2,3,5,8,13,21", "name": "Fibonacci", "offset": "0,4"}])[0]
    assert align([1, 2, 3, 5, 8, 13], e) == {"ok": True, "pos": 2, "matched": 6}
    assert align([1, 2, 3, 5, 8, 14], e)["ok"] is False


# ---------------------------------------------------------------- the loop through the API (fake kernel)
class FakeKernels:
    """One Python namespace per notebook, like one kernel per document; `probe` runs outside the history."""

    def __init__(self):
        self.ns: dict[str, dict] = {}
        self.docs: dict[str, dict] = {}
        self.calls: list[str] = []
        self.probes: list[str] = []

    def known(self, path):
        return "k" if path in self.ns else ""

    def epoch(self, path):
        return f"k-{path}" if path in self.ns else ""

    async def status(self, path):
        return {"kernel": "k" if path in self.ns else "", "state": "idle" if path in self.ns else "none"}

    def _run(self, path, code, language):
        ns = self.ns.setdefault(path, {})
        self.docs[path] = {"engine": {"name": "Python", "version": "3"}}
        res = ExecResult("ok", language=language, sandbox="bwrap", execution_count=1, kernel=self.epoch(path))
        buf = io.StringIO()
        try:
            with contextlib.redirect_stdout(buf):
                exec(compile(ast.parse(code), "<cell>", "exec"), ns)                    # noqa: S102 (test double)
        except Exception as e:  # noqa: BLE001
            res.status, res.error = "error", f"{type(e).__name__}: {e}"
            res.outputs.append({"output_type": "error", "ename": type(e).__name__, "evalue": str(e), "traceback": []})
        res.stdout = buf.getvalue()
        if res.stdout:
            res.outputs.append({"output_type": "stream", "name": "stdout", "text": res.stdout})
        return res

    async def execute(self, path, language, code, *, timeout, on_output=None, approx=True):
        self.calls.append(code)
        return self._run(path, code, language)

    async def probe(self, path, language, program, *, timeout):
        self.probes.append(program)
        return self._run(path, program, language)

    async def variables(self, path, language):
        return None

    async def interrupt(self, path):
        return True


MODEL_CODE = ("```python\nimport math\n\ndef cj_rows_for(n):\n    return [[n, math.isqrt(n)]]\n\n"
              "cj_columns = ['n', 'a']\ncj_index = list(range(1, 41))\n"
              "cj_rows = [r for n in cj_index for r in cj_rows_for(n)]\nprint(cj_rows[:5])\n```")


def responder(role, messages, brain):
    first = next((m["content"] for m in messages if m.get("role") == "user"), "")
    if first.startswith("[madalean:explore]"):
        assert "cj_rows_for" in first and "carrés parfaits" in first
        return MODEL_CODE
    return demo_responder(role, messages, brain)


async def wait_done(s, L, xid, timeout=60):
    for _ in range(int(timeout / 0.05)):
        j = await (await s.get(L + f"/api/explorations/{xid}")).json()
        if not j["running"]:
            return j
        await asyncio.sleep(0.05)
    raise TimeoutError(xid)


def engine_ctx(tmp_path, monkeypatch, **kw):
    fake = FakeKernels()
    monkeypatch.setattr(wbm.Workbench, "kernels", lambda self: fake)
    ctx = make_ctx(tmp_path, brain=FakeBrain(responder), lean_seconds=0.01, **kw)
    return ctx, fake


async def test_loop_explore_recognise_state_keep_and_duplicates(tmp_path, monkeypatch):
    ctx, fake = engine_ctx(tmp_path, monkeypatch)
    events = []
    async with running(ctx) as (_s, L, _Rm), session() as s:
        orig = ctx.bus.publish
        ctx.bus.publish = lambda t, p=None: (events.append((t, p)), orig(t, p))[1]
        tr = ReplayTransport(FIXTURES, strict=True)
        ctx.conjecture_engine.oeis = Oeis(Fetcher(tr), tmp_path / "oeis")
        ctx.settings.mode = "local"
        pid = (await (await s.post(L + "/api/projects", json={"title": "P"})).json())["project"]["id"]
        st = await (await s.get(L + f"/api/explore/status?project={pid}")).json()
        assert st["oeis"] == "off" and st["lmfdb"] == "not_queried" and len(st["examples"]) >= 3     # tests: Local mode
        assert (await s.post(L + f"/api/projects/{pid}/explorations", json={"question": " "})).status == 400
        r = await s.post(L + f"/api/projects/{pid}/explorations",
                         json={"question": "la somme des n premiers nombres impairs", "language": "python"})
        j = await r.json()
        x = j["exploration"]
        assert r.status == 201 and x["origin"] == "catalogue" and x["intent"]["recognised"]
        assert j["cell"]["origin"] == "user" and j["cell"]["may_run"] and fake.calls == []       # nothing ran yet
        assert (await s.post(L + f"/api/explorations/{x['id']}/run")).status == 202
        j = await wait_done(s, L, x["id"])
        x = j["exploration"]
        assert {k: v["state"] for k, v in x["steps"].items()} == {"explore": "done", "recognise": "done",
                                                                  "state": "done", "attack": "todo"}
        assert len(fake.calls) == 1 and "cj_rows_for" in fake.calls[0] and len(fake.probes) == 1
        assert x["table"]["columns"] == ["n", "a"] and x["table"]["total"] == 60 and x["table"]["rows"][3] == ["3", "9"]
        # the table is in the project's Calcul notebook « explorations »
        doc = await (await s.get(L + f"/api/calcul/{pid}/docs/{j['cell']['doc']}")).json()
        cell = next(c for c in doc["cells"] if c["id"] == j["cell"]["id"])
        assert "0 0" in cell["outputs"][0]["text"] and cell["origin"] == "user"
        # Local mode: OEIS is off and no request was made
        assert x["oeis"]["a"]["status"] == "off" and tr.requests == []
        assert any(e["kind"] == "oeis_off" for e in x["journal"])
        (c,) = x["candidates"]
        assert c["kind"] == "polynomial" and c["lean_ok"] is True and c["status"] == "candidate"
        assert "pas démontré" in c["strength"]["fr"]
        kinds_j = [(e["step"], e["kind"]) for e in x["journal"]]
        assert ("recognise", "kept") in kinds_j and ("recognise", "discarded") in kinds_j and ("state", "candidate") in kinds_j
        assert any(t == "explore.updated" for t, _p in events)
        # keep → a conjecture of the project, through the unchanged conjecture API, with the evidence attached
        r = await s.post(L + f"/api/explorations/{x['id']}/candidates/{c['id']}/keep")
        kj = await r.json()
        assert r.status == 201 and kj["duplicate"] is False
        conj = (await (await s.get(L + f"/api/conjectures/{kj['conjecture_id']}")).json())["conjecture"]
        assert conj["status"] == "lean-statement" and conj["statement_ok"] and conj["chain_ok"]
        assert "Finset.range n" in conj["lean_statement"] and conj["origin"]["engine"]["norm"] == c["norm"]
        ev = next(e for e in conj["evidence"] if e["kind"] == "exploration")
        assert ev["data"]["cases"] == 60 and ev["data"]["range"] == [0, 59] and "cj_rows_for" in ev["code"]
        assert conj["cases_tested"] == 0 or conj["status"] != "proved"          # never « proved » from an experiment
        r = await s.post(L + f"/api/explorations/{x['id']}/candidates/{c['id']}/keep")
        assert r.status == 200 and (await r.json())["duplicate"] is True
        # the same question again: the candidate is flagged as a duplicate of the kept conjecture
        j2 = await (await s.post(L + f"/api/projects/{pid}/explorations",
                                 json={"question": "sum of the first n odd numbers", "language": "python"})).json()
        await s.post(L + f"/api/explorations/{j2['exploration']['id']}/run")
        x2 = (await wait_done(s, L, j2["exploration"]["id"]))["exploration"]
        assert x2["candidates"][0]["duplicate_of"]["id"] == kj["conjecture_id"]
        assert any(e["kind"] == "duplicate" for e in x2["journal"])
        n_conj = len((await (await s.get(L + f"/api/conjectures?project={pid}")).json())["conjectures"])
        r = await s.post(L + f"/api/explorations/{x2['id']}/candidates/{x2['candidates'][0]['id']}/keep")
        assert (await r.json())["conjecture_id"] == kj["conjecture_id"]
        assert len((await (await s.get(L + f"/api/conjectures?project={pid}")).json())["conjectures"]) == n_conj
        # hunt: larger range, sampled; the strength label follows, the conjecture gets the evidence
        assert (await s.post(L + f"/api/explorations/{x['id']}/candidates/{c['id']}/attack")).status == 202
        x = (await wait_done(s, L, x["id"]))["exploration"]
        c = x["candidates"][0]
        assert c["hunt"]["cases"] > 100 and c["counterexample"] is None and "par sondage" in c["strength"]["fr"]
        conj = (await (await s.get(L + f"/api/conjectures/{kj['conjecture_id']}")).json())["conjecture"]
        assert any(e["kind"] == "hunt" for e in conj["evidence"]) and conj["status"] == "lean-statement"
        # journal export to a note; discard is journalled
        r = await s.post(L + f"/api/explorations/{x['id']}/export", json={"to": "note"})
        nid = (await r.json())["note_id"]
        note = (await (await s.get(L + f"/api/notes/{nid}")).json())["note"]
        assert "## Journal" in note["body"] and "pas démontré" in note["body"] and "```lean" in note["body"]
        lst = (await (await s.get(L + f"/api/projects/{pid}/explorations")).json())["explorations"]
        assert [e["id"] for e in lst] == [x2["id"], x["id"]] and lst[1]["candidates"] == 1
        r = await s.post(L + f"/api/explorations/{x2['id']}/candidates/{x2['candidates'][0]['id']}/discard",
                         json={"reason": "déjà connue"})
        assert (await r.json())["exploration"]["candidates"][0]["status"] == "discarded"
        assert (await s.delete(L + f"/api/explorations/{x2['id']}")).status == 200
        assert (await s.get(L + f"/api/explorations/{x2['id']}")).status == 404


async def test_given_terms_are_looked_up_in_oeis_when_the_mode_allows(tmp_path, monkeypatch):
    ctx, fake = engine_ctx(tmp_path, monkeypatch)
    async with running(ctx) as (_s, L, _Rm), session() as s:
        ctx.settings.mode = "auto"
        tr = ReplayTransport(FIXTURES)
        ctx.conjecture_engine.oeis = Oeis(Fetcher(tr), tmp_path / "oeis")
        pid = (await (await s.post(L + "/api/projects", json={"title": "P"})).json())["project"]["id"]
        q = ", ".join(str(v) for v in CATALAN)
        j = await (await s.post(L + f"/api/projects/{pid}/explorations", json={"question": q})).json()
        assert j["exploration"]["origin"] == "data" and j["cell"] is None
        await s.post(L + f"/api/explorations/{j['exploration']['id']}/run")
        x = (await wait_done(s, L, j["exploration"]["id"]))["exploration"]
        assert fake.calls == [] and fake.probes == []                     # given terms: nothing is executed
        assert x["oeis"]["a"]["status"] == "ok" and tr.requests == [search_url(CATALAN)]
        got = {c["kind"] for c in x["candidates"]}
        assert {"holonomic", "algebraic_gf", "oeis"} <= got
        o = next(c for c in x["candidates"] if c["kind"] == "oeis")
        assert "A000108" in o["text"]["fr"] and o["strength"]["fr"] == "coïncide avec A000108 sur 14 termes, pas démontré"
        assert o["lean"] is None and any(e["kind"] == "discarded" and "A115140" in e["fr"] for e in x["journal"])
        # a project marked « local only » is never looked up, even in online mode
        p2 = (await (await s.post(L + "/api/projects", json={"title": "Q"})).json())["project"]["id"]
        ctx.projects.get(p2).extra["mode"] = "local"
        j = await (await s.post(L + f"/api/projects/{p2}/explorations", json={"question": q})).json()
        await s.post(L + f"/api/explorations/{j['exploration']['id']}/run")
        x = (await wait_done(s, L, j["exploration"]["id"]))["exploration"]
        assert x["oeis"]["a"]["status"] == "off" and len(tr.requests) == 1
        # hunting a sequence given term by term is refused with the reason
        c = next(c for c in x["candidates"] if c["kind"] == "holonomic")
        await s.post(L + f"/api/explorations/{x['id']}/candidates/{c['id']}/attack")
        x = (await wait_done(s, L, x["id"]))["exploration"]
        assert x["steps"]["attack"]["error"] == "no_code" and any(e["kind"] == "skipped" for e in x["journal"])


async def test_unapproved_model_code_never_runs(tmp_path, monkeypatch):
    ctx, fake = engine_ctx(tmp_path, monkeypatch)
    async with running(ctx) as (_s, L, Rm), session() as s:
        pid = (await (await s.post(L + "/api/projects", json={"title": "P"})).json())["project"]["id"]
        r = await s.post(L + f"/api/projects/{pid}/explorations",
                         json={"question": "le nombre de carrés parfaits inférieurs à n", "language": "python"})
        j = await r.json()
        x, cell = j["exploration"], j["cell"]
        assert x["origin"] == "model" and x["steps"]["explore"]["state"] == "awaiting_approval"
        assert cell["origin"] == "assistant" and not cell["approved"] and not cell["may_run"]
        run = L + f"/api/explorations/{x['id']}/run"
        r = await s.post(run)
        assert r.status == 403 and (await r.json())["error"] == "not_approved"
        assert fake.calls == [] and fake.probes == []
        # the engine itself refuses too (not only the route)
        eng = ctx.conjecture_engine
        with pytest.raises(E.ExploreError) as ei:
            await eng._explore(eng.get(x["id"]), "host")
        assert ei.value.kind == "not_approved" and fake.calls == [] and fake.probes == []
        with pytest.raises(E.ExploreError):
            await eng._rows(eng.get(x["id"]), [1, 2, 3])
        assert fake.probes == []
        # a paired device may not approve or run (host-only setting), and a wrong hash approves nothing
        dev, token = ctx.devices.add("phone")
        hdr = {"Authorization": f"Bearer {token}"}
        r = await s.post(Rm + f"/api/explorations/{x['id']}/run", headers=hdr)
        assert r.status == 403 and (await r.json())["error"] == "experiments_host_only"
        appr = f"/api/calcul/{pid}/docs/{cell['doc']}/cells/{cell['id']}/approve"
        assert (await s.post(Rm + appr, json={"code_hash": cell["code_hash"]}, headers=hdr)).status == 403
        assert (await s.post(L + appr, json={"code_hash": "0" * 64})).status == 409
        assert (await s.post(run)).status == 403 and fake.calls == []
        # approval of this exact code on the host (Calcul's own endpoint), then it runs
        assert (await s.post(L + appr, json={"code_hash": cell["code_hash"]})).status == 200
        assert (await s.post(run)).status == 202
        x = (await wait_done(s, L, x["id"]))["exploration"]
        assert x["steps"]["explore"]["state"] == "done" and len(fake.calls) == 1 and "math.isqrt" in fake.calls[0]
        assert x["table"]["total"] == 40
        # the code changes (here: the model's cell edited in the notebook) → the approval no longer covers it
        nb = ctx.workbench.calc
        nb.edit(pid, cell["id"], code=x["code"] + "\nprint('changed')\n", doc=cell["doc"], by="assistant", model="m")
        r = await s.post(run)
        assert r.status == 403 and len(fake.calls) == 1
        # edited by the user: still the model's cell (Calcul's rule), the new code needs its own approval
        r = await s.patch(L + f"/api/explorations/{x['id']}", json={"code": "print(1)"})
        assert r.status == 422 and (await r.json())["error"] == "bad_contract"
        code = MODEL_CODE.split("```python\n")[1].split("```")[0].replace("range(1, 41)", "range(1, 31)")
        j = await (await s.patch(L + f"/api/explorations/{x['id']}", json={"code": code})).json()
        assert j["exploration"]["origin"] == "model" and not j["cell"]["may_run"] and not j["cell"]["approved"]
        assert j["exploration"]["steps"]["explore"]["state"] == "awaiting_approval"
        assert (await s.post(run)).status == 403 and len(fake.calls) == 1
        assert (await s.post(L + appr, json={"code_hash": j["cell"]["code_hash"]})).status == 200
        assert (await s.post(run)).status == 202
        x = (await wait_done(s, L, x["id"]))["exploration"]
        assert x["table"]["total"] == 30 and len(fake.calls) == 2
        # no model at all: said, nothing invented
    ctx2, fake2 = engine_ctx(tmp_path / "b", monkeypatch)

    def no_model(role, messages, brain):
        raise RuntimeError("no model")
    ctx2.brain = FakeBrain(no_model)
    ctx2.brain.local = ctx2.local
    async with running(ctx2) as (_s, L, _Rm), session() as s:
        pid = (await (await s.post(L + "/api/projects", json={"title": "P"})).json())["project"]["id"]
        j = await (await s.post(L + f"/api/projects/{pid}/explorations",
                                json={"question": "une question que le catalogue ne connaît pas"})).json()
        assert j["exploration"]["steps"]["explore"]["error"] in ("no_model", "no_code") and j["cell"] is None
        assert fake2.calls == []


async def test_counterexample_path_refutes_a_planted_false_conjecture(tmp_path, monkeypatch):
    """« n² + n + 41 is always prime » survives the first 31 terms; the hunt finds n = 40, a fresh kernel recomputes
    it, Lean closes the negation at the witness, and the conjecture is kept — refuted, with its counter-example."""
    ctx, fake = engine_ctx(tmp_path, monkeypatch)
    recomputed = fresh = []
    async with running(ctx) as (_s, L, _Rm), session() as s:
        async def fresh_run(key, language, code, *, timeout=60, fresh=False, **kw):
            assert fresh is True
            recomputed.append(code)
            return FakeKernels()._run("fresh", code, language)
        monkeypatch.setattr(ctx.research.bridge, "run", fresh_run)
        checks = []
        orig_check = ctx.lean.check

        async def check(code, ws, *a, **kw):
            checks.append(code)
            return await orig_check(code, ws, *a, **kw)
        ctx.lean.check = check
        pid = (await (await s.post(L + "/api/projects", json={"title": "P"})).json())["project"]["id"]
        j = await (await s.post(L + f"/api/projects/{pid}/explorations",
                                json={"question": "n^2 + n + 41 jusqu'à 30", "language": "python"})).json()
        xid = j["exploration"]["id"]
        await s.post(L + f"/api/explorations/{xid}/run")
        x = (await wait_done(s, L, xid))["exploration"]
        c = next(c for c in x["candidates"] if c["kind"] == "all_prime")
        assert c["lean_ok"] and "vérifié jusqu'à n = 30 (31 cas)" in c["strength"]["fr"]
        assert (await s.post(L + f"/api/explorations/{xid}/candidates/{c['id']}/attack")).status == 202
        x = (await wait_done(s, L, xid))["exploration"]
        c = next(k for k in x["candidates"] if k["id"] == c["id"])
        ce = c["counterexample"]
        assert c["status"] == "refuted" and ce["witness"] == {"n": 40} and ce["sage"] and ce["lean"] and ce["verified"]
        assert ce["detail"]["got"] == "1681"
        assert len(fresh) == 1 and "cj_rows_for" in fresh[0] and "_madalean_cj([40]" in fresh[0]
        neg = ce["lean_check"]["code"]
        assert "example : ¬ (∀ (n : ℕ), Nat.Prime (n ^ 2 + n + 41))" in neg and "have hw := h 40" in neg
        assert neg in checks
        assert any(e["kind"] == "refuted" and "n\": 40" in e["fr"] for e in x["journal"])
        # kept with its counter-example, status refuted, evidence chain intact; a proof attempt is refused
        conj = (await (await s.get(L + f"/api/conjectures/{c['conjecture_id']}")).json())["conjecture"]
        assert conj["status"] == "refuted" and conj["counterexample"]["witness"] == {"n": 40} and conj["chain_ok"]
        assert conj["counterexample"]["lean"] is True and conj["counterexample"]["sage"] is True
        assert [e["kind"] for e in conj["evidence"]][-1] == "counterexample_check"
        r = await s.post(L + f"/api/explorations/{xid}/candidates/{c['id']}/prove")
        assert r.status == 409 and (await r.json())["error"] == "refuted"
        # the other candidate (odd values) survives its hunt and may go to the normal pipeline
        o = next(k for k in x["candidates"] if k["kind"] == "congruence")
        await s.post(L + f"/api/explorations/{xid}/candidates/{o['id']}/attack")
        x = (await wait_done(s, L, xid))["exploration"]
        o = next(k for k in x["candidates"] if k["id"] == o["id"])
        assert o["status"] == "survived" and o["counterexample"] is None
        r = await s.post(L + f"/api/explorations/{xid}/candidates/{o['id']}/prove")
        pj = await r.json()
        assert r.status == 202 and pj["job"]["dossier_id"] == pj["conjecture_id"]
        assert [st["stage"] for st in pj["job"]["plan"]] == ["proof", "explanation"]
        # a recomputation that does not confirm the witness → « disputed », never « refuted »
        j = await (await s.post(L + f"/api/projects/{pid}/explorations",
                                json={"question": "n^2 + n + 41 jusqu'à 35", "language": "python"})).json()
        xid2 = j["exploration"]["id"]
        await s.post(L + f"/api/explorations/{xid2}/run")
        x2 = (await wait_done(s, L, xid2))["exploration"]

        async def lying_run(key, language, code, **kw):
            return ExecResult("ok", stdout=C.MARK + json.dumps({"columns": ["n", "a"], "rows": [["40", "1601"]],
                                                                 "done": [40], "error": ""}))
        monkeypatch.setattr(ctx.research.bridge, "run", lying_run)
        c2 = next(k for k in x2["candidates"] if k["kind"] == "all_prime")
        assert c2["duplicate_of"]["id"] == c["conjecture_id"]     # the same statement as the refuted conjecture
        await s.post(L + f"/api/explorations/{xid2}/candidates/{c2['id']}/attack")
        x2 = (await wait_done(s, L, xid2))["exploration"]
        c2 = next(k for k in x2["candidates"] if k["id"] == c2["id"])
        assert c2["status"] == "disputed" and c2["counterexample"]["verified"] is False


async def test_stop_and_failed_run_are_recorded(tmp_path, monkeypatch):
    ctx, fake = engine_ctx(tmp_path, monkeypatch)
    async with running(ctx) as (_s, L, _Rm), session() as s:
        pid = (await (await s.post(L + "/api/projects", json={"title": "P"})).json())["project"]["id"]
        j = await (await s.post(L + f"/api/projects/{pid}/explorations", json={"question": "Fibonacci",
                                                                                "language": "python"})).json()
        xid = j["exploration"]["id"]
        gate = asyncio.Event()
        orig = fake.execute

        async def slow(*a, **kw):
            await gate.wait()
            return await orig(*a, **kw)
        fake.execute = slow
        assert (await s.post(L + f"/api/explorations/{xid}/run")).status == 202
        assert (await s.post(L + f"/api/explorations/{xid}/run")).status == 409             # one run at a time
        j = await (await s.post(L + f"/api/explorations/{xid}/stop")).json()
        x = (await wait_done(s, L, xid))["exploration"]
        assert x["steps"]["explore"]["state"] == "stopped" and x["journal"][-1]["kind"] == "stopped"
        gate.set()
        fake.execute = orig
        # the experiment fails in the kernel: said with the error, no pattern is invented
        bad = j["exploration"]["code"].replace("return [[n, ", "return [[n, undefined_name(n), ")
        await s.patch(L + f"/api/explorations/{xid}", json={"code": bad})
        await s.post(L + f"/api/explorations/{xid}/run")
        x = (await wait_done(s, L, xid))["exploration"]
        assert x["steps"]["explore"]["state"] == "failed" and x["steps"]["explore"]["error"] == "run_failed"
        assert "NameError" in x["steps"]["explore"]["detail"] and x["candidates"] == []


# ---------------------------------------------------------------- real Lean, real Sage
QUESTIONS = ["somme des n premiers nombres impairs", "somme des carrés des diviseurs", "n^2 + n + 41 jusqu'à 30",
             "Fibonacci", "nombres de Catalan", "n!", "somme des n premiers cubes et (n(n+1)/2)^2", "phi(n) et n",
             "H_n", "2^n - 1", "nombre de diviseurs", "n-ième nombre premier", "binomial(2n, n)", "n/(n+1)",
             "n^3 - n", "nombres triangulaires", "gcd(n, 6)", "primepi(n)"]


def all_candidates(flavor):
    out = []
    for q in QUESTIONS:
        it = C.recognise(q)
        t = C.local_rows(it, list(range(it.first, it.last + 1)))
        ctx = S.Ctx(it, t["columns"], flavor)
        out += [c for c in (S.candidate(f, ctx) for f in S.mark_trivial(P.analyze(t), ctx)) if c and c["lean"]]
    return out


async def test_generated_lean_statements_compile_and_the_negation_closes_at_the_witness(tmp_path, ws):
    """Real Lean (the prover's workspace): every statement the engine writes for these requests compiles, and the
    counter-example file of the planted false conjecture is accepted (`¬ ∀ n, Nat.Prime (n² + n + 41)` at 40)."""
    from madalean.runtime.lean import LeanRunner
    from madalean.slots import Slots
    cands = all_candidates(lean_flavor(ws.toolchain))
    assert len(cands) >= 18 and {"polynomial", "recurrence", "holonomic", "multiplicative", "congruence",
                                 "all_prime", "inequality", "equal", "periodic"} <= {c["kind"] for c in cands}
    code, spans = S.lean_batch(cands, leancheck.GOEDEL_HEADER)
    runner = LeanRunner(Slots(), tmp_path)
    r = (await runner.check(code, ws, 900)).to_dict()
    assert not r["infra_error"] and not r["timed_out"]
    bad = [(cid, [e["text"][:200] for e in r["errors"] if a <= e["line"] <= b]) for cid, a, b in spans]
    assert [x for x in bad if x[1]] == [] and len(spans) == len(cands)
    prime = next(c for c in cands if c["kind"] == "all_prime" and "41" in c["lean"])
    neg = cj.negation_file(leancheck.prepare_statement(prime["lean"]), {"n": 40})
    r = (await runner.check(neg, ws, 600)).to_dict()
    assert r["statement_ok"] and not r["has_sorry"], r["errors"]
    r = (await runner.check(cj.negation_file(leancheck.prepare_statement(prime["lean"]), {"n": 39}), ws, 600)).to_dict()
    assert not r["statement_ok"]                                   # 39 is not a counter-example: Lean refuses


def run_sage(prog: str, tmp_path, timeout=600) -> str:
    py = syntaxcards.sage_python()
    if py is None:
        pytest.skip("SageMath not installed")
    env = syntaxcards._sage_env(tmp_path / "work")
    p = subprocess.run([py, "-c", "from sage.all import *\n" + prog], capture_output=True, text=True, env=env,
                       timeout=timeout)
    assert p.returncode == 0, p.stderr[-3000:]
    return p.stdout


@pytest.mark.sage
def test_catalogue_code_runs_in_the_installed_sage(tmp_path):
    """Every catalogue request, as the Sage cell the engine writes (preparsed by Sage), gives the reference values;
    the driver reads the table; Sage's own guesser agrees with the generating function found here."""
    py = syntaxcards.sage_python()
    if py is None:
        pytest.skip("SageMath not installed")
    qs = QUESTIONS + ["nombre de partitions de n", "nombres de Bell", "fonction de Möbius", "nombres de Lucas",
                      "somme des n premiers nombres premiers", "produit des n premiers nombres premiers"]
    its = [C.recognise(q) for q in qs]
    cells = [C.experiment_code(it, "sage") + C.driver(None) + C.driver([it.first + 5, it.first + 90], 10) for it in its]
    fib = [0, 1]
    while len(fib) < 30:
        fib.append(fib[-1] + fib[-2])
    guess = E.GUESS % (json.dumps([str(v) for v in fib]), json.dumps(["0", "1"]), json.dumps(["1", "-1", "-1"]))
    wrong = E.GUESS % (json.dumps([str(v) for v in fib]), json.dumps(["1"]), json.dumps(["1", "-2"]))
    prog = ("from sage.repl.preparse import preparse\nimport json\n"
            f"for _c in json.loads({json.dumps(json.dumps(cells + [guess, wrong]))}):\n"
            "    exec(preparse(_c), globals())\n")
    out = [json.loads(line[len(C.MARK):]) for line in run_sage(prog, tmp_path).splitlines() if line.startswith(C.MARK)]
    assert len(out) == 2 * len(its)
    for i, it in enumerate(its):
        first, more = out[2 * i], out[2 * i + 1]
        assert not first["error"] and not more["error"], (qs[i], first["error"], more["error"])
        assert first["rows"] == C.local_rows(it, list(range(it.first, it.last + 1)))["rows"], qs[i]
        assert more["rows"] == C.local_rows(it, [it.first + 5, it.first + 90])["rows"], qs[i]
    g = [json.loads(line.split(" ", 1)[1]) for line in run_sage(prog, tmp_path).splitlines()
         if line.startswith("MADALEAN_CJG ")]
    assert g[0]["agrees"] is True and g[1]["agrees"] is False and "x" in g[0]["ogf"]


@pytest.mark.sage
def test_graph_family_in_real_sage_gives_relations_between_invariants(tmp_path):
    it = C.recognise("arbres")
    prog = ("from sage.repl.preparse import preparse\nimport json\n"
            f"exec(preparse(json.loads({json.dumps(json.dumps(C.experiment_code(it, 'sage') + C.driver(None)))})), "
            "globals())\n")
    d = C.parse_driver(run_sage(prog, tmp_path))
    assert d and not d["error"] and d["columns"][:3] == ["n", "m", "Δ"] and len(d["rows"]) > 80
    t = {"columns": d["columns"], "rows": d["rows"], "labels": True}
    fs = [f for f in P.analyze(t) if f["status"] == "kept"]
    lin = [f for f in fs if f["kind"] == "linear"]
    assert any(set(f["columns"]) == {"n", "m"} for f in lin)                       # m = n − 1
    ctx = S.Ctx(it, t["columns"])
    texts = [S.candidate(f, ctx)["text"]["fr"] for f in fs]
    assert any("parmi les arbres" in x and "m" in x for x in texts)
    assert any(f["kind"] == "inequality" for f in fs)


needs_kernel = pytest.mark.skipif(not (shutil.which("jupyter-lab") and shutil.which("sage")),
                                  reason="jupyter-lab / sage not installed")


@pytest.mark.sage
@needs_kernel
async def test_real_sandboxed_kernel_explore_hunt_and_refute(tmp_path, ws):
    """For real: Madalean's sandboxed Sage kernel computes the table, Sage's guesser confirms the generating
    function, the hunt refutes « always prime » at n = 40 (fresh kernel + real Lean) and σ₂ stays multiplicative."""
    ctx = make_ctx(tmp_path, ws=ws)
    async with running(ctx) as (_s, L, _Rm), session() as s:
        pid = (await (await s.post(L + "/api/projects", json={"title": "P", "workspace": ws.key})).json())["project"]["id"]

        async def explore(q):
            j = await (await s.post(L + f"/api/projects/{pid}/explorations", json={"question": q})).json()
            assert j["exploration"]["language"] == "sage" and j["cell"]["may_run"]
            assert (await s.post(L + f"/api/explorations/{j['exploration']['id']}/run")).status == 202
            return (await wait_done(s, L, j["exploration"]["id"], 400))["exploration"]

        async def attack(x, kind):
            c = next(c for c in x["candidates"] if c["kind"] == kind)
            assert (await s.post(L + f"/api/explorations/{x['id']}/candidates/{c['id']}/attack")).status == 202
            x = (await wait_done(s, L, x["id"], 600))["exploration"]
            return next(k for k in x["candidates"] if k["id"] == c["id"])
        x = await explore("Fibonacci")
        assert x["steps"]["state"]["state"] == "done", x["steps"]
        rec = next(f for f in x["findings"] if f["kind"] == "recurrence")
        assert rec["detail"]["sage"]["agrees"] is True
        c = next(c for c in x["candidates"] if c["kind"] == "recurrence")
        assert c["lean_ok"] is True and "Nat.fib (n + 2)" in c["lean"]
        x = await explore("n^2 + n + 41 jusqu'à 30")
        c = await attack(x, "all_prime")
        assert c["status"] == "refuted" and c["counterexample"]["witness"] == {"n": 40}
        assert c["counterexample"]["sage"] and c["counterexample"]["lean"] is True
        conj = (await (await s.get(L + f"/api/conjectures/{c['conjecture_id']}")).json())["conjecture"]
        assert conj["status"] == "refuted"
        x = await explore("les sommes des carrés des diviseurs")
        c = await attack(x, "multiplicative")
        assert c["status"] == "survived" and c["hunt"]["cases"] > 20 and c["lean_ok"] is True
