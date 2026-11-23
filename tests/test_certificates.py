"""Session S-AT (DECISIONS D52): « Sage calcule, Lean vérifie ».

- the reader of statements and the kinds (no Sage, no Lean);
- the fixed producer in the REAL installed Sage (marked `sage`);
- every kind end to end with the REAL Lean on each built workspace (lean-prover49, and lean-current when its
  toolchain is found: `MADALEAN_TEST_TOOLCHAINS=<dir of toolchains>` adds a place to look in, read only);
- a wrong witness is refused by Lean and reported as such; fakes for the flows without Sage;
- the proof pipeline (strategy « certificat », no model call), the prover agent's tool, the API and Calcul."""
from __future__ import annotations

import asyncio
import os
from pathlib import Path

import pytest

from madalean import leancheck, syntaxcards
from madalean import workspaces as W
from madalean.certs import corpus, engine, expr as E, fromcalcul, poly as Y, pratt, problem as PB, producer, render as RD
from madalean.pipeline import certificate as certstage
from madalean.runtime.lean import LeanRunner
from madalean.server.routes_work import create_dossier
from madalean.slots import Slots
from helpers import make_ctx, running, session, started, wait_idle

H = leancheck.GOEDEL_HEADER
QUICK = ["prime-97", "prime-m127", "composite-fermat5", "arith-modeq", "arith-factorial", "powmod-1e18",
         "identity-germain", "ideal-cubes", "ideal-power", "linear-bound", "linear-infeasible", "sos-three",
         "sos-hyps", "sos-nonneg-vars", "exists-bezout", "exists-inverse-nat", "exists-system", "cex-euler",
         "numeric-sqrt", "numeric-e-pi", "finite-two", "finite-growth", "false-finite", "false-identity"]


def st(tail: str, name: str = "t") -> str:
    return f"{H}theorem {name} {tail} := by sorry\n"


# ---------------------------------------------------------------- fixtures
@pytest.fixture(scope="module")
def sage():
    py = syntaxcards.sage_python()
    if py is None:
        pytest.skip("SageMath not installed")
    import tempfile
    return producer.SubprocessProducer(py, Path(tempfile.mkdtemp(prefix="madalean-cert-sage-")))


@pytest.fixture(scope="module")
def lean():
    import tempfile
    return LeanRunner(Slots({"lean": 3}), Path(tempfile.mkdtemp(prefix="madalean-cert-lean-")))


def _workspace(key: str):
    extra = [Path(p) for p in os.environ.get("MADALEAN_TEST_TOOLCHAINS", "").split(os.pathsep) if p]
    orig = W.toolchain_roots
    if extra:
        W.toolchain_roots = lambda: orig() + extra
    try:
        ws = next((w for w in W.all_workspaces(scan_user=False) if w.key == key and not w.problems), None)
        if ws is not None and extra:
            _ = ws.lean_bin                      # resolved now; keep the extra roots for the checks of this module
            return ws
        return ws
    finally:
        if not extra:
            W.toolchain_roots = orig


@pytest.fixture(scope="module", params=["lean-prover49", "lean-current"])
def anyws(request):
    ws = _workspace(request.param)
    if ws is None:
        pytest.skip(f"{request.param} not built here (or its Lean toolchain is not installed)")
    return ws


@pytest.fixture(scope="module")
def ws49():
    ws = _workspace("lean-prover49")
    if ws is None:
        pytest.skip("lean-prover49 not built")
    return ws


# ---------------------------------------------------------------- reader and kinds (pure)
def test_reader_follows_lean_conventions():
    assert E.parse_prop("x ^ 2 + y ^ 2 ≥ 2 * x * y")[0:2] == ("rel", ">=")
    assert E.parse_prop("-x ^ 2 = 0")[2] == ("neg", ("pow", ("var", "x"), ("num", "2")))
    assert E.parse_prop("∃ u v : ℤ, 6 * u + 4 * v = 2")[1] == [["u", "Z"], ["v", "Z"]]
    assert E.parse_prop("(17 * 2753 : ℕ) ≡ 1 [MOD 3120]")[0:2] == ("modeq", "MOD")
    assert E.parse_prop("√2 < Real.pi")[2] == ("call", "sqrt", [("num", "2")])
    assert E.holds(E.parse_prop("7 - 10 = 0"), "N") and E.holds(E.parse_prop("7 - 10 = -3"), "Z")
    assert E.holds(E.parse_prop("(-7) / 2 = -4 ∧ (-7) % 2 = 1"), "Z") and E.holds(E.parse_prop("7 / 0 = 0"), "N")
    assert E.holds(E.parse_prop("Nat.gcd (2 ^ 40 - 1) (2 ^ 30 - 1) = 1023 ∧ 5 ! = 120"), "N")
    for bad in ("f x = 2", "(n : ℝ) + 1 > 0 ∧ n = 2", "x⁻¹ = 1", "∑ i in Finset.range 3, i = 3", "∃ x, x = 1"):
        with pytest.raises(E.Unsupported):
            E.domain(E.parse_prop(bad), {"n": "N", "x": "R"})
    with pytest.raises(E.TooBig):
        E.evaluate(E.parse_term("2 ^ (2 ^ 40)"), "N")
    assert E.is_prime(2 ** 127 - 1) and not E.is_prime(2 ** 67 - 1)


def test_every_corpus_statement_has_its_kind_and_false_claims_are_refuted():
    assert len(corpus.CASES) >= 40 and {c.kind for c in corpus.CASES} == set(engine.KINDS)
    for c in corpus.CASES:
        pb = PB.read(corpus.statement(c))
        ts = PB.tasks(pb)
        assert ts and ts[0].kind == c.kind, (c.id, [t.kind for t in ts])
        assert bool(ts[0].refuted) == (c.expect == "refuted"), c.id
        assert (ts[0].request is not None) <= engine.KINDS[c.kind]["sage"], c.id
    refuted = {c.id: PB.tasks(PB.read(corpus.statement(c)))[0].refuted for c in corpus.CASES if c.expect == "refuted"}
    assert refuted["false-prime"] == "91 = 7 × 13" and refuted["false-finite"] == "n = 40"
    assert refuted["false-identity"] == "a = 1, b = 1"


def test_statements_outside_the_shapes_get_no_kind():
    for tail in ("(a b : ℕ) (ha : Even a) (hb : Even b) : Even (a + b)", "(f : ℝ → ℝ) (h : ∀ x, f x = 2 * x) : f 1 = 2",
                 "(n : ℕ) : (n : ℝ) + 1 > 0", "(x : ℝ) (h : 0 < x) : Real.log x ≤ x - 1", "(x : ℝ) : x / x = 1",
                 ": ∀ n : ℕ, n + 0 = n ∧ True", "(x y : ℝ) (h : x ≠ y) : x - y ≠ 0"):
        assert engine.kinds_of(st(tail)) in ([], ["identity"]) and "sos" not in engine.kinds_of(st(tail)), tail
    assert engine.kinds_of("not lean at all") == [] and engine.kinds_of(st(": Nat.Prime (2 ^ 521 - 1)")) == []   # too large
    assert engine.kinds_of(st("(x : ℤ) (h₁ : 2 * x ≥ 3) (h₂ : 2 * x ≤ 4) : x = 2")) == []      # needs integrality


def test_the_program_is_fixed_and_the_request_is_only_data():
    req = {"kind": "exists", "vars": [["x", "N"]], "dom": "N", "body": ["rel", "=", ["var", "x"], ["num", "1"]],
           "note": "__import__('os').system('true')"}
    prog = producer.program(req)
    assert "__import__('os')" not in prog and "exists" not in prog and prog.count("b64decode") == 2
    assert producer.program({"kind": "factor", "n": "15"}).split("'")[1] == prog.split("'")[1]   # same program text
    src = producer.source()
    assert "eval(" not in src.replace("evaluate(", "") and "exec(" not in src and "sage_eval" not in src
    assert producer.parse("noise\nMADALEAN_CERT {\"ok\": true, \"d\": \"3\"}\n") == {"ok": True, "d": "3"}
    assert producer.parse("nothing")["ok"] is False
    with pytest.raises(ValueError):
        producer.program({"x": "9" * 500_000})


def test_witnesses_from_the_sandbox_are_read_strictly():
    pb = PB.read(st(": ¬ Nat.Prime 15"))
    task = PB.tasks(pb)[0]
    for bad in ({"d": "3; #eval 1", "q": "5"}, {"d": 3.0, "q": 5}, {"d": True, "q": 5}, {"d": "9" * 5000, "q": "1"}, {}):
        with pytest.raises(RD.BadWitness):
            RD.render(pb, task, bad)
    assert "show 3 ∣ 15 from ⟨5, by norm_num⟩" in RD.render(pb, task, {"d": "3", "q": 5}).tactics[1]
    with pytest.raises(E.Unsupported):
        Y.from_wire([[1, 1, [1, "x"]]], 2)
    with pytest.raises(E.Unsupported):
        Y.from_wire([[1, 0, [1, 1]]], 2)
    with pytest.raises(pratt.BadCertificate):
        pratt.proof({"p": 1000003, "a": 2, "factors": [{"p": 2, "e": "x"}]})
    assert pratt.proof({"p": 97}) == ("", "(by norm_num)")
    for tac in (RD.CLOSE, RD.DECIDE, pratt.HELPERS):
        assert "native_decide" not in tac and not leancheck.exec_risks(tac) and not leancheck.forbidden_reasons(tac)


def test_calcul_cells_become_statements_from_their_text_only():
    f = fromcalcul.statement_for
    assert f("F5 = 2^32 + 1\nfactor(F5)", "641 * 6700417") == (": (((2 ^ 32) + 1) : ℕ) = 641 * 6700417", "product")
    assert f("factor(360)", "2^3 * 3^2 * 5")[0] == ": Nat.Prime 2 ∧ Nat.Prime 3 ∧ Nat.Prime 5 ∧ (360 : ℕ) = 2 ^ 3 * 3 ^ 2 * 5"
    assert f("n = 2**127 - 1\nis_prime(n)", "True")[0] == ": Nat.Prime ((2 ^ 127) - 1)"
    assert f("is_prime(91)", "False")[0] == ": ¬ Nat.Prime 91" and f("factor(97)", "97")[0] == ": Nat.Prime 97"
    assert f("xgcd(123456, 7890)", "(6, 409, -6400)")[0] == ": (123456 : ℤ) * (409) + 7890 * (-6400) = 6"
    assert f("print(power_mod(2, 10^18, 1000003))", "5")[0] == ": 2 ^ (10 ^ 18) % 1000003 = 5"
    assert f("inverse_mod(17, 3120)", "2753")[0] == ": 17 * 2753 % 3120 = 1"
    for code, out in (("integrate(x, x)", "1/2*x^2"), ("factor(x^2 - 1)", "(x - 1) * (x + 1)"), ("gcd(a, 4)", "2"),
                      ("factor(__import__('os').getpid())", "2"), ("is_prime(7)", "maybe"), ("3 - 5", "-2"), ("", "")):
        assert f(code, out) is None, code
    for code, out in (("factor(360)", "2^3 * 3^2 * 5"), ("xgcd(123456, 7890)", "(6, 409, -6400)"), ("2^64 - 1", str(2 ** 64 - 1))):
        assert engine.kinds_of(st(f(code, out)[0])) == ["arith"]


# ---------------------------------------------------------------- flows with fakes
class Accept:
    """A Lean that accepts everything (records the files)."""

    def __init__(self, ok=True):
        self.ok, self.codes = ok, []

    async def __call__(self, code, name):
        from madalean.runtime.lean import CompileResult
        self.codes.append(code)
        v = leancheck.Verdict(self.ok, "ok" if self.ok else "Lean a trouvé 1 erreur.", axioms=[])
        return CompileResult(v, code, 0.01, "")


async def test_engine_flows_without_sage_and_without_witness():
    ws = type("Ws", (), {"toolchain": "leanprover/lean4:v4.9.0-rc1", "key": "demo"})()
    o = await engine.certify(st(": ¬ Nat.Prime 15"), ws, Accept(), None)
    assert o.status == "unavailable" and o.kind == "composite" and not o.code
    o = await engine.certify(st("(x y : ℝ) : (x + y) ^ 2 = x ^ 2 + 2 * x * y + y ^ 2"), ws, Accept(), None)
    assert o.ok and o.kind == "identity" and o.code.rstrip().endswith("ring") and o.sage_seconds == 0

    async def none(req, seconds):
        return {"ok": False, "reason": "no witness found in the search range"}
    o = await engine.certify(st(": ∃ x : ℕ, x * x = 2"), ws, Accept(), none)
    assert o.status == "no_witness" and o.tried == [{"kind": "exists", "status": "no_witness",
                                                     "reason": "no witness found in the search range"}]

    async def garbage(req, seconds):
        return {"ok": True, "values": [["1; sorry", "1"]]}
    chk = Accept()
    o = await engine.certify(st(": ∃ x : ℕ, x * x = 4"), ws, chk, garbage)
    assert o.status == "rejected" and "bad witness" in o.reason and chk.codes == []      # never reaches Lean

    async def boom(req, seconds):
        raise producer.SageUnavailable("kernel died")
    o = await engine.certify(st(": ∃ x : ℕ, x * x = 4"), ws, Accept(), boom)
    assert o.status == "unavailable"
    o = await engine.certify(st("(a b : ℕ) (h : Even a) : Even (a * b)"), ws, Accept(), None)
    assert o.status == "none" and o.to_dict()["title"] is None
    o = await engine.certify(st(": Nat.gcd 12 18 = 4"), ws, Accept(), None)
    assert o.status == "refuted" and o.kind == "arith"


# ---------------------------------------------------------------- the producer in the real Sage
@pytest.mark.sage
def test_producer_answers_in_real_sage(sage):
    def ask(tail):
        t = PB.tasks(PB.read(st(tail)))[0]
        return t, sage.run(dict(t.request, digits=RD.digits("old")), 40)
    t, a = ask(": Nat.Prime (2 ^ 61 - 1)")
    assert a["ok"] and a["cert"]["p"] == str(2 ** 61 - 1) and pratt.validate(RD._cert(a["cert"])) > 3
    t, a = ask(": ¬ Nat.Prime (2 ^ 67 - 1)")
    assert a["ok"] and int(a["d"]) * int(a["q"]) == 2 ** 67 - 1 and a["d"] == "193707721"
    t, a = ask("(x y : ℝ) (h₀ : x + y = 3) (h₁ : x * y = 2) : x ^ 2 + y ^ 2 = 5")
    assert a["ok"] and a["exp"] == 1 and len(a["cof"]) == 2
    t, a = ask("(x y : ℝ) (h₀ : (x - y) ^ 2 = 0) : x = y")
    assert a["ok"] and a["exp"] == 2
    t, a = ask("(x y : ℝ) (h₀ : x + y = 3) : x * y = 2")
    assert not a["ok"] and a["reason"] == "not in the ideal"
    t, a = ask("(x y z : ℝ) (h₁ : x + 2 * y ≤ 4) (h₂ : y - z ≤ 1) (h₃ : 3 * z ≤ 2) : x + 3 * y ≤ 17 / 3")
    assert a["ok"] and a["multipliers"] == [[["1", "1"], ["1", "1"], ["1", "3"]]]
    t, a = ask("(x y : ℝ) (h₁ : x + y ≤ 1) : x ≤ 1")
    assert not a["ok"] and a["reason"] == "no linear certificate"
    t, a = ask("(a b c : ℝ) : a ^ 2 + b ^ 2 + c ^ 2 ≥ a * b + b * c + c * a")
    assert a["ok"] and a["blocks"] and a["blocks"][0][0] == -1
    t, a = ask("(x y : ℝ) : x ^ 2 * y ^ 2 + 1 ≥ 3 * x * y")            # false at x = y = 1
    assert not a["ok"]
    t, a = ask(": ∃ u v : ℤ, 123456 * u + 7890 * v = 6")
    assert a["ok"] and 123456 * int(a["values"][0][0]) + 7890 * int(a["values"][1][0]) == 6
    t, a = ask(": ∃ x : ℚ, x * x = 2")
    assert not a["ok"]
    t, a = ask(": Real.sqrt 2 + Real.sqrt 3 < 3.15")
    assert a["ok"] and len(a["bounds"]) == 2
    t, a = ask(": Real.pi < 3.14")
    assert not a["ok"] and a["reason"] == "false"
    assert sage.run({"kind": "nope"})["reason"] == "unknown kind"
    assert sage.run({"kind": "factor", "n": "__import__('os')"})["reason"] == "error"


# ---------------------------------------------------------------- end to end: real Sage, real Lean, each workspace
@pytest.mark.sage
async def test_every_kind_is_verified_by_real_lean_on_each_workspace(anyws, sage, lean):
    full = os.environ.get("MADALEAN_CERT_FULL") == "1"
    cases = [c for c in corpus.CASES if full or c.id in QUICK]
    res = await corpus.run(cases, anyws, lean, sage)
    bad = [(c.id, o.status, o.reason, o.errors[:300]) for c, o in res if o.status != c.expect or o.kind != c.kind]
    assert not bad, bad
    for c, o in res:
        if o.ok:
            assert o.axioms is not None and set(o.axioms) <= leancheck.ALLOWED_AXIOMS, (c.id, o.axioms)
            assert "native_decide" not in o.code and "sorry" not in leancheck.remove_comments(o.code)
            assert o.witness and o.checker and leancheck.theorem_name(o.code).startswith("cert_")
    kinds = {c.kind for c, o in res if o.ok}
    assert kinds == set(engine.KINDS), set(engine.KINDS) - kinds


@pytest.mark.sage
async def test_a_wrong_witness_is_refused_by_lean_and_reported(ws49, lean):
    """The computation is not trusted: each of these witnesses has the right shape and is mathematically wrong."""
    wrong = {
        ": ¬ Nat.Prime 1000001": {"d": "3", "q": "333334"},                         # 3 does not divide it
        ": ∃ x : ℕ, 65537 * x % 1000000007 = 1": {"values": [["12345", "1"]]},
        ": ¬ ∀ n : ℕ, Nat.Prime (n ^ 2 + n + 41)": {"values": [["39", "1"]]},      # 39 gives 1601, a prime
        "(x y : ℝ) (h₀ : x + y = 3) (h₁ : x * y = 2) : x ^ 2 + y ^ 2 = 5":
            {"exp": 1, "cof": [[["1", "1", [1, 0]]], [["2", "1", [0, 0]]]]},
        "(x y : ℝ) : x ^ 2 + y ^ 2 ≥ 3 * x * y": {"c": ["0", "1"], "mults": [],       # false inequality
                                                   "blocks": [[-1, [[["1", "1"], [["1", "1", [1, 0]], ["-1", "1", [0, 1]]]]]]]},
        ": Real.sqrt 2 < 1.4": {"bounds": [[["13", "10"], ["139", "100"]]]},        # √2 < 1.39 is false
        ": Nat.Prime 1000000007": {"cert": {"p": "1000000007", "a": "4", "factors": [   # 4 is a square: not primitive
            {"p": 2, "e": 1}, {"p": "500000003", "e": 1, "a": "2", "factors": [
                {"p": 2, "e": 1}, {"p": 41, "e": 2}, {"p": "148721", "e": 1, "a": "6", "factors": [
                    {"p": 2, "e": 4}, {"p": 5, "e": 1}, {"p": 11, "e": 1}, {"p": 13, "e": 2}]}]}]}},
    }

    async def check(code, name):
        return await lean.check(code, ws49, 180, name)

    async def one(tail, ans):
        async def produce(req, seconds):
            return dict(ans, ok=True)
        return tail, await engine.certify(st(tail), ws49, check, produce)
    for tail, o in await asyncio.gather(*[one(t, a) for t, a in wrong.items()]):
        assert o.status == "rejected" and not o.ok, (tail, o.status)
        assert o.errors and "Lean" in o.reason and o.code, tail
        assert o.to_dict()["status"] == "rejected"


# ---------------------------------------------------------------- pipeline, agent tool, API, Calcul
@pytest.mark.sage
async def test_pipeline_proves_by_certificate_without_any_model(tmp_path, ws49, sage):
    ctx = make_ctx(tmp_path, ws=ws49)
    ctx.settings.certificates = True
    ctx.cert_producer = sage
    ctx = await started(ctx)
    d, _job = await create_dossier(ctx, {"statement": st("(a b c : ℝ) : a ^ 2 + b ^ 2 + c ^ 2 ≥ a * b + b * c + c * a")})
    await wait_idle(ctx)
    assert d.status == "proved", [(e.kind, e.text) for e in d.events]
    v = d.proofs[d.cur_proof]
    assert v.model == "certificat:sos" and v.meta["strategy"] == "certificate" and v.meta["certificate"] == "sos"
    assert v.meta["axioms"] is not None and v.meta["certificate_witness"]
    ev = [e for e in d.events if e.kind == "certificate"]
    assert len(ev) == 1 and "témoin calculé par Sage, vérifié par Lean" in ev[0].text and "somme de carrés" in ev[0].text
    assert "prove" not in [r["role"] for r in ctx.brain.requests]            # no prover model was called
    job = ctx.history.load(d.id)[-1]
    att = [a for a in job.attempts if a.kind == "certificate"]
    assert len(att) == 1 and att[0].status == "accepted" and att[0].model == "certificat:sos"
    assert [e.name for e in ctx.library.entries] == [d.theorem]
    # a statement with no certificate kind: the strategy is silent, the usual prover works
    d2, _ = await create_dossier(ctx, {"statement": st("(a b : ℕ) (ha : Even a) (hb : Even b) : Even (a + b)")})
    await wait_idle(ctx)
    assert d2.status == "proved" and not [e for e in d2.events if e.kind == "certificate"]
    assert not [a for a in ctx.history.load(d2.id)[-1].attempts if a.kind == "certificate"]
    # a false claim: reported, never proved by the certificate
    d3, _ = await create_dossier(ctx, {"statement": st(": ∀ n < 50, Nat.Prime (n ^ 2 + n + 41)")})
    await wait_idle(ctx)
    assert any("l'énoncé est faux" in e.text and "n = 40" in e.text for e in d3.events), [e.text for e in d3.events]
    assert not any(p.model.startswith("certificat") for p in d3.proofs)
    await ctx.stop()


async def test_pipeline_setting_off_and_sage_missing(tmp_path, ws49):
    ctx = make_ctx(tmp_path, ws=ws49)
    assert ctx.settings.certificates is False                              # the other suites keep their sequences
    ctx.settings.certificates = True
    ctx = await started(ctx)                                               # no Sage producer on this context
    d, _ = await create_dossier(ctx, {"statement": st("(a b : ℤ) : (a + b) * (a - b) = a ^ 2 - b ^ 2")})
    await wait_idle(ctx)
    v = d.proofs[d.cur_proof]
    assert d.status == "proved" and v.model == "certificat:identity"       # needs no Sage: Lean's `ring`
    assert any("vérifié par Lean par un calcul direct" in e.text for e in d.events if e.kind == "certificate")
    await ctx.stop()


@pytest.mark.sage
async def test_agent_tool_returns_only_lean_accepted_proofs(tmp_path, ws49, sage, lean):
    ctx = type("Ctx", (), {"cert_producer": sage})()

    async def check(code, name):
        return await lean.check(code, ws49, 180, name)
    main = st("(x y : ℝ) (h : 0 ≤ x) : x ^ 3 + y ^ 2 ≥ 0")
    a = await certstage.tool_answer(ctx, main, "(a b : ℝ) : a ^ 2 + b ^ 2 ≥ 2 * a * b", ws49, check)
    assert "ACCEPTED by Lean" in a and "theorem madalean_witness" in a and "positivity" in a and "import" not in a
    b = await certstage.tool_answer(ctx, main, ": Nat.Prime 91", ws49, check)
    assert "FALSE" in b and "7 × 13" in b
    c = await certstage.tool_answer(ctx, main, "(s : Set ℕ) : s ⊆ s", ws49, check)
    assert c.startswith("No certificate kind matches")
    d = await certstage.tool_answer(ctx, main, "theorem foo : ∃ x : ℚ, x * x = 2 := by\n  #eval 1", ws49, check)
    assert d.startswith("No witness found")


@pytest.mark.sage
async def test_api_and_certify_a_calcul_cell(tmp_path, ws49, sage):
    from madalean.research.sagebridge import ExecResult
    from madalean.server.plugins import workbench as wbm
    ctx = make_ctx(tmp_path, ws=ws49)
    ctx.cert_producer = sage
    async with running(ctx) as (srv, L, R), session() as s:
        j = await (await s.get(L + "/api/certificates")).json()
        assert j["sage"] is True and {k["id"] for k in j["kinds"]} == set(engine.KINDS) and j["kinds"][0]["title"]["text"]
        r = await s.post(L + "/api/certificates/check", json={"statement": ": ∃ u v : ℤ, 123456 * u + 7890 * v = 6"})
        j = await r.json()
        assert r.status == 200 and j["status"] == "verified" and j["kind"] == "exists" and "Témoin" in j["witness"][0]["text"]
        assert j["lines"] > 5 and j["axioms"] is not None
        j = await (await s.post(L + "/api/certificates/check", json={"statement": ": Nat.gcd 12 18 = 4"})).json()
        assert j["status"] == "refuted"
        assert (await s.post(L + "/api/certificates/check", json={"statement": "garbage"})).status == 400
        assert (await s.post(R + "/api/certificates/check", json={"statement": ": 1 + 1 = 2"})).status in (401, 403)
        # « Certifier avec Lean » on a Calcul cell: statement from the cell's text, dossier with the checked proof
        pid = (await (await s.post(L + "/api/projects", json={"title": "P"})).json())["project"]["id"]
        doc = (await (await s.post(L + f"/api/calcul/{pid}/docs", json={"title": "N", "language": "sage"}))
               .json())["doc"]["id"]
        cells = L + f"/api/calcul/{pid}/docs/{doc}/cells"
        calc = srv.app[wbm.WB].calc

        async def cell(src, out):
            c = (await (await s.post(cells, json={"source": src})).json())["cell"]
            v = calc.cell_view(pid, doc, c["id"])
            outs = [{"output_type": "execute_result", "execution_count": 1, "metadata": {}, "data": {"text/plain": out}}]
            await asyncio.to_thread(calc.record_run, pid, c["id"], ExecResult("ok", language="sage", execution_count=1,
                                    outputs=outs), "host", v["code_hash"], doc=doc, upstream=calc.upstream_of(pid, doc, c["id"]))
            return c["id"]
        cid = await cell("n = 2^61 - 1\nis_prime(n)", "True")
        ref = {"project_id": pid, "doc": doc, "cell_id": cid}
        j = await (await s.post(L + "/api/certificates/dossier", json={**ref, "dry": True})).json()
        assert j["kinds"] == ["prime"] and "Nat.Prime ((2 ^ 61) - 1)" in j["statement"]
        r = await s.post(L + "/api/certificates/dossier", json=ref)
        j = await r.json()
        assert r.status == 201 and j["status"] == "verified" and j["kind"] == "prime", j
        d = ctx.repo.get(j["dossier"]["id"])
        assert d.status == "proved" and d.project_id == pid and d.proofs[d.cur_proof].model == "certificat:prime"
        assert "lucas_primality" in d.proof and d.proofs[d.cur_proof].meta["certificate"] == "prime"
        assert [e.kind for e in d.events] == ["statement", "proof", "certificate"] and "Pratt" in d.events[-1].text
        fresh = await ctx.lean.check(leancheck.with_axiom_probe(d.proof, d.theorem), ws49, 180, d.theorem)
        assert fresh.verdict.ok and fresh.via == "fresh" and leancheck.theorem_name(d.proof) == d.theorem
        cid2 = await cell("integrate(x^2, x)", "1/3*x^3")
        r = await s.post(L + "/api/certificates/dossier", json={"project_id": pid, "doc": doc, "cell_id": cid2})
        assert r.status == 400 and (await r.json())["error"] == "certificate_unsupported"
        r = await s.post(L + "/api/certificates/dossier", json={"statement": ": ∃ x : ℚ, x * x = 2"})
        j = await r.json()
        assert r.status == 200 and j["status"] == "no_witness" and j["dossier"] is None
    await ctx.stop()


@pytest.mark.sage
@pytest.mark.skipif(not __import__("shutil").which("jupyter-lab"), reason="jupyter-lab missing")
async def test_the_producer_runs_in_the_sandboxed_sage_kernel(tmp_path, ws49):
    """The production path: Calcul's sandboxed kernel (preparser on) runs the same fixed program."""
    from madalean.research.sagebridge import SageBridge
    ctx = await started(make_ctx(tmp_path, ws=ws49))
    br = SageBridge(ctx)
    if not br.available().get("sage"):
        pytest.skip("no Sage kernel")
    p = producer.BridgeProducer(br)
    try:
        a = await p({"kind": "factor", "n": str(2 ** 32 + 1)}, 30)
        assert a == {"ok": True, "d": "641", "q": "6700417", "seconds": a["seconds"]}, a
        t = PB.tasks(PB.read(st("(x y : ℝ) (h₀ : 0 ≤ x) (h₁ : x ≤ y) : x ^ 2 ≤ y ^ 2")))[0]
        b = await p(t.request, 30)
        assert b["ok"] and "blocks" in b, b

        async def check(code, name):
            return await ctx.lean.check(code, ws49, 180, name)
        o = await engine.certify(st(": ¬ Nat.Prime (2 ^ 32 + 1)"), ws49, check, p)
        assert o.ok and o.kind == "composite" and o.sage_seconds > 0
    finally:
        await br.close()
        await ctx.stop()
