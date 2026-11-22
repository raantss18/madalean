"""S-AG (DECISIONS D39): deterministic, structure-aware code generation for Calcul — request analysis (intent), the
catalogue of canonical constructions (verified in the real Sage / Python), reproducible generation (« Réécrire » gives
the same code), « retenir le meilleur », the missing-import fixer, the recipe migration and « Autre version »."""
import asyncio
import json
import random
import shutil
import types
from pathlib import Path

import pytest

from helpers import make_ctx, running, session
from madalean import syntaxcards
from madalean.brain.api import BrainError
from madalean.brain.fake import FakeBrain
from madalean.research import codecat, codefix, codegen
from madalean.research import intent as I
from madalean.research.recipes import RecipeStore, migrate, request_key
from madalean.server.plugins import workbench as wbm

from test_calcul_notebook import FakeKernels

GF125 = 'gf{"k":3,"p":5}'


# ---------------------------------------------------------------- 1. the request analysis
@pytest.mark.parametrize("text", [
    "factorise x^5+4x-1 dans F_125[x]", "factorise x^5+4x-1 dans F_{125}[x]", "factorise x^5+4x-1 dans F_{5^3}[x]",
    "factorise x^5+4x-1 dans \\mathbb{F}_{125}[x]", "factorise x^5+4x-1 dans \\mathbb F_{5^3}[X]",
    "factorise x^5+4x-1 dans GF(125)[x]", "factorise x^5 + 4*x - 1 dans GF(5^3)[x]",
    "factorise x⁵+4x-1 dans 𝔽₁₂₅[x]", "Factorise  x^5 + 4 x - 1  dans F125[x]", "factor x^5+4x-1 over F_125[x]",
])
def test_one_finite_field_whatever_the_notation(text):
    it = I.analyze(text)
    assert it.op == "factor" and it.exprs == ["x^5 + 4*x - 1"] and not it.errors
    assert it.objects[0].key() == GF125 and it.obj("poly").params["vars"] == ["x"]
    assert it.key() == I.analyze("factorise x^5+4x-1 dans F_125[x]").key()
    assert "F₁₂₅ = F_{5³}" in I.summary(it, "fr")


@pytest.mark.parametrize("text,q", [("corps F_12", 12), ("racines dans F_{6} de x^2+1", 6), ("GF(100)", 100),
                                    ("le corps fini à 10 éléments", 10), ("F_{2^2*3}", None)])
def test_not_a_prime_power_is_refused_with_a_reason(text, q):
    it = I.analyze(text)
    if q is None:
        assert not it.obj("gf")
        return
    assert it.errors and it.errors[0]["code"] == "not_prime_power" and it.errors[0]["q"] == q
    assert "puissance d'un nombre premier" in it.errors[0]["fr"] and "power of a prime" in it.errors[0]["en"]
    assert codecat.assemble(it, "sage").error["code"] == "not_prime_power"


@pytest.mark.parametrize("text,expect", [
    ("les racines dans F_16 de x^5+x^3+x+1", {"op": "roots", "objects": ['gf{"k":4,"p":2}'],
                                              "exprs": ["x^5 + x^3 + x + 1"]}),
    ("racines de x^5+x^3+x+1 dans F_{2^4}", {"op": "roots", "objects": ['gf{"k":4,"p":2}']}),
    ("les éléments inversibles de Z/12Z", {"op": "units", "objects": ['zmod{"n":12}']}),
    ("les éléments inversibles de ℤ/12ℤ", {"op": "units", "objects": ['zmod{"n":12}']}),
    ("ordre de \\mathbb{Z}/12\\mathbb{Z}", {"op": "order", "objects": ['zmod{"n":12}']}),
    ("factorise x^2+y^2 dans F_7[x,y]", {"op": "factor", "exprs": ["x^2 + y^2"]}),
    ("pgcd de x^4-1 et x^6-1 dans Q[x]", {"op": "gcd", "exprs": ["x^4 - 1", "x^6 - 1"]}),
    ("factorise x^4+4 sur Z[i]", {"op": "factor", "objects": ['base{"ring":"ZZ[I]"}']}),
    ("nombre de classes de Q(sqrt(-5))", {"op": "class_number", "objects": ['numfield{"gen":"a","quad":-5}']}),
    ("discriminant de Q(√8)", {"op": "discriminant", "objects": ['numfield{"gen":"a","quad":2}']}),
    ("degré du corps cyclotomique Q(ζ_7)", {"op": "degree", "objects": ['numfield{"cyclo":7,"gen":"z"}']}),
    ("déterminant de [[1,2],[3,4]]", {"op": "det", "objects": ['matrix{"rows":[["1","2"],["3","4"]]}']}),
    ("valeurs propres de \\begin{pmatrix} 2 & 1 \\\\ 1 & 2 \\end{pmatrix}",
     {"op": "eigenvalues", "objects": ['matrix{"rows":[["2","1"],["1","2"]]}']}),
    ("ordre du groupe symétrique S_5", {"op": "order", "objects": ['group{"family":"sym","n":5}']}),
    ("sous-groupes de D_4", {"op": "subgroups", "objects": ['group{"family":"dih","n":4}']}),
    ("le groupe A_4 est-il abélien ?", {"op": "is_abelian", "objects": ['group{"family":"alt","n":4}']}),
    ("nombre de points de la courbe elliptique y^2 = x^3 + x + 1 sur F_7",
     {"op": "points", "objects": ['gf{"k":1,"p":7}', 'ell{"a":["0","0","0","1","1"],"ring":"gf{\\"k\\":1,\\"p\\":7}"}']}),
    ("rang de la courbe elliptique y^2 = x^3 - x", {"op": "ell_rank"}),
    ("trace sin(x)/x sur [-10,10]", {"op": "plot", "exprs": ["sin(x)/x"], "interval": ("-10", "10")}),
    ("intégrale de x^2 sin(x) entre 0 et π", {"op": "integrate", "exprs": ["x^2*sin(x)"], "interval": ("0", "pi")}),
    ("∫ 1/(1+x²)", {"op": "integrate", "exprs": ["1/(1 + x^2)"]}),
    ("dérivée seconde de sin(x)", {"op": "diff", "order": 2}),
    ("dérivée de x^3 e^{2x}", {"op": "diff", "exprs": ["x^3*exp(2*x)"]}),
    ("\\frac{d}{dx} (x^2+1)", {"exprs": ["x^2 + 1"]}),
    ("limite de sin(x)/x en 0", {"op": "limit", "point": "0"}),
    ("limite de 1/x en 0 à droite", {"op": "limit", "point": "0", "side": "+"}),
    ("limite de (1+1/x)^x quand x tend vers l'infini", {"op": "limit", "point": "oo"}),
    ("somme pour k de 1 à n de k^2", {"op": "sum", "sumvar": "k", "interval": ("1", "n")}),
    ("\\sum_{k=1}^{n} k^3", {"op": "sum", "sumvar": "k", "exprs": ["k^3"]}),
    ("développement limité de exp(x) à l'ordre 5 en 0", {"op": "series", "order": 5, "point": "0"}),
    ("résous x^2-2=0", {"op": "solve", "exprs": ["x^2 - 2 == 0"]}),
    ("factorise 2024", {"op": "factor", "ints": [2024]}),
    ("pgcd de 12 et 18", {"op": "gcd", "ints": [12, 18]}),
    ("inverse de 3 modulo 7", {"op": "inverse_mod", "ints": [3, 7]}),
    ("les 10 premiers nombres premiers", {"op": "primes_first", "ints": [10]}),
    ("simplifie \\frac{x^2-1}{x-1}", {"op": "simplify", "exprs": ["(x^2 - 1)/(x - 1)"]}),
    ("étudie les variations de f(x)=x*exp(-2x)+exp(x)", {"op": "study", "exprs": ["x*exp(-2*x) + exp(x)"]}),
])
def test_intent_table(text, expect):
    it = I.analyze(text)
    for k, v in expect.items():
        got = [o.key() for o in it.objects] if k == "objects" else getattr(it, k)
        assert got == v, (text, k, got)


def test_expression_spelling_is_canonical():
    n = I.normalize_expr
    assert n("x^5+4x-1") == n("x^5 + 4*x - 1") == n("x**5+4 x-1") == "x^5 + 4*x - 1"
    assert n("2(x+1)") == "2*(x + 1)" and n("x sin(x)") == "x*sin(x)" and n("sin^2(x)") == "sin(x)^2"
    assert n("e^{-x^2}") == "exp(-x^2)" and n("√2 x") == "sqrt(2)*x" and n("|x-1|") == "abs(x - 1)"
    assert n("\\sqrt{x}+\\frac{1}{2}") == "sqrt(x) + (1/2)" and n("f(x)") == "f(x)"
    with pytest.raises(I.ExprError):
        n("x^ + 1")


# ---------------------------------------------------------------- 2. the catalogue (assembly + real execution)
def test_catalogue_assembly_follows_the_conventions():
    a = codecat.assemble(I.analyze("factorise x^5+4x-1 dans F_{5^3}[X]"), "sage")
    assert a.full and a.code == "F125.<a> = GF(5^3)\nR.<x> = PolynomialRing(F125)\nf = x^5 + 4*x - 1\nf.factor()"
    a = codecat.assemble(I.analyze("intégrale de x^2 sin(x) entre 0 et pi"), "python")
    assert a.full and a.code.split("\n")[0] == "from sympy import integrate, pi, sin, symbols"
    a = codecat.assemble(I.analyze("trace sin(x) et cos(x) entre 0 et 2pi"), "python")
    assert a.code.startswith("import matplotlib.pyplot as plt\nimport numpy as np\nfrom sympy import")
    # Python only knows prime fields: no wrong code, the model writes it (with the objects it can name)
    a = codecat.assemble(I.analyze("factorise x^5+4x-1 dans F_125[x]"), "python")
    assert not a.full and "sympy only knows prime fields" in a.reason
    # partial: unknown words → the objects' constructions are the model's mandatory start
    a = codecat.assemble(I.analyze("la clôture algébrique de F_125 et ses automorphismes"), "sage")
    assert not a.full and a.prefix == "F125.<a> = GF(5^3)"
    # a template that fails on this installation is not used
    it = I.analyze("factorise 2024")
    assert codecat.assemble(it, "sage", {"failed": {"sage:int_factor": "x"}}).full is False


def test_every_sample_is_assembled_or_refused():
    for lang in ("sage", "python"):
        progs = codecat.sample_programs(lang)
        bad = [(sid, code) for sid, code, chk, _e in progs if code.startswith("raise")]
        assert not bad, bad
    assert len(codecat.sample_programs("sage")) >= 50 and len(codecat.sample_programs("python")) >= 35
    data = codecat.entries()
    assert data["samples"][0]["sage"].startswith("F125.<a> = GF(5^3)")
    assert data["lean"]["int_factor"]["default"] != data["lean"]["int_factor"]["v4.9"]   # Lean 4.9 names differ


@pytest.fixture(scope="module")
def built_catalogue(tmp_path_factory):
    d = tmp_path_factory.mktemp("cat")
    old = dict(syntaxcards._DIR)
    syntaxcards.configure(d)
    yield d
    syntaxcards._DIR.update(old)


@pytest.mark.sage
def test_catalogue_runs_in_the_real_sage(built_catalogue):
    if syntaxcards.sage_python() is None:
        pytest.skip("SageMath not installed")
    data = codecat.build("sage")
    assert data and data["version"] == syntaxcards.sage_version()
    assert data["failed"] == {}, data["failed"]                     # every Sage entry ran with its assertion
    assert len(data["verified"]) >= 50 and not any(data["samples"].values())
    assert codecat.status("sage")["verified"] == data["verified"]


@pytest.mark.sage
def test_catalogue_runs_in_the_kernel_python(built_catalogue):
    if codecat._interp("python") is None:
        pytest.skip("no python3 kernel")
    data = codecat.build("python")
    if data is None or data["versions"].get("sympy") in ("", None):
        pytest.skip("sympy not installed for the kernel's Python")
    assert data["failed"] == {}, data["failed"]
    assert "symbols" in data["sympy_names"] and len(data["verified"]) >= 35


def test_lean_catalogue_build_marks_failures(tmp_path, monkeypatch):
    from madalean import leancheck
    syntaxcards.configure(tmp_path)
    ws = types.SimpleNamespace(key="lean-current", path=tmp_path / "w", toolchain="leanprover/lean4:v4.36.0",
                               has_mathlib=lambda: True, problems=[])
    monkeypatch.setattr("madalean.runtime.lean.workspace_info", lambda w: {"lean": "v4.36.0", "mathlib": "abc"})

    class Lean:
        async def check(self, code, ws, timeout_s=0, owner=None):
            self.code = code
            line = next(i + 1 for i, l in enumerate(code.split("\n")) if l == "-- int_factor") + 1
            err = leancheck.LeanMessage("error", line, 0, None, None, "unknown identifier 'Nat.primeFactorsList'")
            return types.SimpleNamespace(verdict=leancheck.Verdict(False, "x", errors=[err]), stdout="",
                                         infra_error="", timed_out=False)
    lean = Lean()
    data = asyncio.run(codecat.build_lean(types.SimpleNamespace(lean=lean), ws))
    assert data["flavor"] == "default" and "int_factor" in data["failed"] and "gf" in data["verified"]
    assert "Nat.card F125" in lean.code                              # the current Mathlib's GaloisField.card
    ws49 = types.SimpleNamespace(**{**vars(ws), "key": "lean-prover49", "toolchain": "leanprover/lean4:v4.9.0-rc1"})
    asyncio.run(codecat.build_lean(types.SimpleNamespace(lean=lean), ws49))
    assert "Nat.factors 2024" in lean.code and "∑ i in Finset.range 4" in lean.code


# ---------------------------------------------------------------- 3. determinism with a model that varies
def varying_responder(role, messages, brain):
    """Answers differently every time (like a model at temperature > 0 or a race between models)."""
    user = next(m["content"] for m in messages if m["role"] == "user")
    if "The cell you wrote failed" in user:
        return "```python\nprint('fixed')\n```"
    n = random.randint(0, 10 ** 6)
    return f"```python\nvalue_{n} = {n}\nvalue_{n}\n```"


def _ctx(tmp_path, responder=varying_responder):
    ctx = types.SimpleNamespace(brain=FakeBrain(responder), settings=types.SimpleNamespace(mode="online", prefer={}),
                                local=types.SimpleNamespace(release_owner=lambda o: None), spawn=lambda c: None)
    return ctx


def test_same_request_same_code_even_when_the_model_varies(tmp_path):
    ctx = _ctx(tmp_path)
    store = RecipeStore(tmp_path / "recipes.json")

    async def ask(prompt, **kw):
        return await codegen.transcribe(ctx, language="python", prompt=prompt, names=[], context="", owner="t",
                                        recipes=store, **kw)
    # a request the catalogue covers: no model at all, byte-identical
    a = asyncio.run(ask("intégrale de x^2 sin(x) entre 0 et pi"))
    b = asyncio.run(ask("integrale de  x^2*sin(x)  entre 0 et π"))
    assert a["origin"] == "catalogue" and b["origin"] == "best" and a["code"] == b["code"] and not ctx.brain.requests
    assert a["recognized"]["fr"].startswith("intégrale de x^2*sin(x)")
    # a request the model writes: the first valid version is kept, « Réécrire » returns it (no second call)
    c = asyncio.run(ask("écris un petit poème en Python"))
    d = asyncio.run(ask("écris un petit poème en Python"))
    e = asyncio.run(ask("Écris un petit poème en python ?"))
    assert c["origin"] == "model" and d["origin"] == e["origin"] == "best"
    assert c["code"] == d["code"] == e["code"] and len(ctx.brain.requests) == 1
    assert ctx.brain.requests[0]["temperature"] == 0.0 and ctx.brain.requests[0]["extra"] == {"seed": codegen.SEED}
    # « Autre version »: a different code on purpose, higher temperature and another seed; the best is unchanged
    v = asyncio.run(ask("écris un petit poème en Python", variant=True))
    assert v["origin"] == "variant" and v["code"] != c["code"] and ctx.brain.requests[-1]["temperature"] > 0
    assert ctx.brain.requests[-1]["extra"]["seed"] != codegen.SEED
    assert asyncio.run(ask("écris un petit poème en Python"))["code"] == c["code"]


def test_keep_the_best_ranking_and_failures(tmp_path):
    st = RecipeStore(tmp_path / "r.json")
    key = request_key("factorise x^5+4x-1 dans F_125[x]")
    assert key == request_key("factorise x^5+4x-1 dans GF(5^3)[x]")
    st.record(key, "r", "A", "sage", "10.10", origin="model")
    st.record(key, "r", "B", "sage", "10.10", origin="variant")
    assert st.best(key, "sage", "10.10")["code"] == "A"              # first valid version
    st.outcome(key, "B", "sage", "10.10", ok=True, seconds=1.0)
    assert st.best(key, "sage", "10.10")["code"] == "B"              # ran OK > never run
    st.outcome(key, "A", "sage", "10.10", ok=True, seconds=0.9)
    assert st.best(key, "sage", "10.10")["code"] == "B"              # not clearly faster: no flapping
    st.approve(key, "A", "sage", "10.10")
    assert st.best(key, "sage", "10.10")["code"] == "A"              # ran OK and approved > ran OK
    st.record(key, "r", "C", "sage", "10.10")
    st.outcome(key, "C", "sage", "10.10", ok=False, error="NameError")
    assert st.failed_codes(key, "sage", "10.10") == [{"code": "C", "error": "NameError"}]
    st2 = RecipeStore(tmp_path / "r2.json")
    st2.record(key, "r", "X", "sage", "10.10")
    st2.outcome(key, "X", "sage", "10.10", ok=False, error="boom")
    assert st2.best(key, "sage", "10.10") is None                   # a version that only failed: never preferred
    st2.record(key, "r", "X", "sage", "10.10")
    assert st2.best(key, "sage", "10.10") is None
    st2.record(key, "r", "Y", "sage", "10.10")
    assert st2.best(key, "sage", "10.10")["code"] == "Y"


def test_failed_versions_are_shown_to_the_model_and_the_prefix_is_enforced(tmp_path):
    seen = []

    def responder(role, messages, brain):
        user = next(m["content"] for m in messages if m["role"] == "user")
        seen.append(user)
        return "```sage\nF = GF(125, 'b')\nF125 = GF(125, 'c')\nR.<x> = F125[]\n(x^5 + 4*x - 1).roots(F125.algebraic_closure())\n```"
    ctx = _ctx(tmp_path, responder)
    store = RecipeStore(tmp_path / "recipes.json")
    prompt = "racines de x^5+4x-1 dans la clôture algébrique de F_125"
    key = request_key(prompt)
    store.record(key, prompt, "bad_code()", "sage", syntaxcards.sage_version() or "", origin="model")
    store.outcome(key, "bad_code()", "sage", syntaxcards.sage_version() or "", ok=False, error="NameError: bad_code")
    r = asyncio.run(codegen.transcribe(ctx, language="sage", prompt=prompt, names=[], context="", owner="t",
                                       recipes=store))
    assert "FAILED when run" in seen[0] and "bad_code()" in seen[0]
    assert "MUST start with exactly these lines" in seen[0] and "F125.<a> = GF(5^3)" in seen[0]
    lines = r["code"].split("\n")
    assert lines[0] == "F125.<a> = GF(5^3)" and "F125 = GF(125, 'c')" not in lines   # the catalogue's wins
    assert r["coverage"] == "partial" and r["recognized"]["fr"].startswith("corps fini F₁₂₅ = F_{5³}")


def test_pinned_model_first_race_only_as_fallback(tmp_path):
    calls = []

    class Brain(FakeBrain):
        def ranking(self, role, mode="auto", **kw):
            return [types.SimpleNamespace(model=types.SimpleNamespace(key=k, local=False))
                    for k in ("fake:fake-assistant", "other:m2")]

        async def complete(self, role, messages, **kw):
            calls.append(kw.get("only"))
            return await super().complete(role, messages, **kw)
    ctx = _ctx(tmp_path)
    ctx.brain = Brain(varying_responder)
    stats = codegen.ModelStats(tmp_path / "models.json")
    r = asyncio.run(codegen.transcribe(ctx, language="python", prompt="un poème", names=[], context="", owner="t",
                                       stats=stats))
    assert calls == ["fake:fake-assistant"] and r["pinned"] == "fake:fake-assistant" and not r["raced"]
    # measured success decides (not the first to answer): another model clearly better → pinned
    for _ in range(6):
        stats.ran("python", "other:m2", True)
    for _ in range(4):
        stats.ran("python", "fake:fake-assistant", False)
    assert stats.pinned("python", ["fake:fake-assistant", "other:m2"]) == "other:m2"
    # the pinned model fails → the race (no `only`) answers, and two misses in a row unpin it
    calls.clear()
    r = asyncio.run(codegen.transcribe(ctx, language="python", prompt="un autre poème", names=[], context="",
                                       owner="t", stats=stats))
    assert calls == ["other:m2", None] and r["raced"] and r["code"]
    asyncio.run(codegen.transcribe(ctx, language="python", prompt="un troisième poème", names=[], context="",
                                   owner="t", stats=stats))
    assert stats.view()["python"]["pinned"] != "other:m2"


# ---------------------------------------------------------------- 4. canonical imports, missing-import fixer
def test_imports_on_top_deduplicated_and_missing_ones_added():
    r = codefix.canonicalize("x = np.linspace(0, 1)\nimport math\nplt.plot(x, np.sin(x))\nimport numpy as np\n"
                             "import math\ny = symbols('y')\nFraction(1, 3)", "python")
    assert r["code"].split("\n")[:5] == ["import math", "import matplotlib.pyplot as plt", "import numpy as np",
                                         "from fractions import Fraction", "from sympy import symbols"]
    assert r["code"].endswith("x = np.linspace(0, 1)\nplt.plot(x, np.sin(x))\ny = symbols('y')\nFraction(1, 3)")
    # Sage: a conventional name an earlier cell defined (or not) is constructed the catalogue's way
    r = codefix.canonicalize("R.<x> = PolynomialRing(F9)\n[p for p in R.polynomials(2) if p.is_irreducible()]",
                             "sage", sage_names={"PolynomialRing"})
    assert r["code"].startswith("F9.<a> = GF(3^2)\nR.<x> = PolynomialRing(F9)")
    # untouched when nothing is missing; unparsable code is returned as is
    assert codefix.canonicalize("1 + 1", "python")["code"] == "1 + 1"
    assert codefix.canonicalize("print(", "python")["code"] == "print("


def test_run_error_fixed_without_a_model():
    fx = codefix.fix_error("y = np.arange(3)\ny", "Traceback …\nNameError: name 'np' is not defined", "python")
    assert fx["code"] == "import numpy as np\ny = np.arange(3)\ny"
    fx = codefix.fix_error("g = f^2\ng", "NameError: name 'f' is not defined", "sage", prev={"f": "f = x^2 + 1"},
                           sage_names=set())
    assert fx["code"] == "f = x^2 + 1\ng = f^2\ng"
    assert codefix.fix_error("1/0", "ZeroDivisionError: division by zero", "python") is None
    prev = codefix.prev_definitions(["F9.<a> = GF(3^2)\nfor i in range(3):\n    z = i", "f = x^2 + 1"], "sage")
    assert prev == {"F9": "F9.<a> = GF(3^2)", "f": "f = x^2 + 1"}


def test_autofix_uses_the_fixer_before_the_model(tmp_path):
    ctx = _ctx(tmp_path)
    r = asyncio.run(codegen.transcribe(ctx, language="python", prompt="tableau", names=[], context="", owner="t",
                                       fix_code="np.arange(3)", fix_error="NameError: name 'np' is not defined"))
    assert r["model"] == "fix" and r["code"] == "import numpy as np\nnp.arange(3)" and not ctx.brain.requests


# ---------------------------------------------------------------- 5. recipes of S-AB migrated to intent keys
V1 = {"recipes": [
    {"id": "a1", "request": "factorise x^5+4x-1 dans la cloture algebrique de F_125[X]", "template": "t",
     "params": [], "code": "F125 = GF(125, 'b')\nR.<x> = PolynomialRing(F125)\nf = x^5 + 4*x - 1\nf.factor()",
     "language": "sage", "version": "10.10", "uses": [], "t": 1.0, "hits": 0},
    {"id": "a2", "request": "les racines dans F_16 de x^5+x^3+x+1", "template": "t", "params": [],
     "code": "F.<a> = GF(16)\nR.<x> = F[]\n(x^5+x^3+x+1).roots()", "language": "sage", "version": "10.10",
     "uses": [], "t": 2.0, "hits": 3},
    {"id": "a3", "request": "racines de x^5+x^3+x+1 dans F_{2^4}", "template": "t", "params": [],
     "code": "K.<b> = GF(2^4)\nS.<x> = K[]\n(x^5+x^3+x+1).roots()", "language": "sage", "version": "10.10",
     "uses": [], "t": 3.0, "hits": 1}]}


def test_recipes_file_of_s_ab_is_migrated(tmp_path):
    p = tmp_path / "recipes.json"
    p.write_text(json.dumps(V1), encoding="utf-8")
    st = RecipeStore(p)
    items = st.list()
    assert len(items) == 2                                           # F_16 and F_{2^4}: one intent, merged
    merged = next(r for r in items if "F_16" in r["request"])
    assert len(merged["versions"]) == 2 and merged["code"].startswith("K.<b> = GF(2^4)") and merged["hits"] == 4
    assert merged["key"] == request_key("racines de x^5+x^3+x+1 dans GF(16)")
    data = json.loads(p.read_text())
    assert data["schema"] == 2 and (tmp_path / "recipes.v1.json").is_file()
    assert st.best(merged["key"], "sage", "10.10")["code"] == merged["code"]
    assert migrate(data["recipes"]) == data["recipes"]               # idempotent


def test_real_recipes_file_migrates(tmp_path):
    real = Path.home() / ".config" / "madalean" / "research" / "recipes.json"
    if not real.is_file():
        pytest.skip("no recipes file on this host")
    p = tmp_path / "recipes.json"
    shutil.copy(real, p)                                             # a copy: the user's file is never touched
    old = json.loads(p.read_text())
    st = RecipeStore(p)
    items = st.list()
    n_old = len(old.get("recipes") or [])
    assert 0 < len(items) <= n_old and all(r["versions"] and r["code"] for r in items)
    assert sum(len(r["versions"]) for r in items) == len({(r["request"], r["code"]) for r in old["recipes"]}) or \
        sum(len(r["versions"]) for r in items) <= n_old


# ---------------------------------------------------------------- 6. through the server: F_12, recognized, variant
async def test_server_ask_recognized_rewrite_variant_and_request_errors(tmp_path, monkeypatch):
    fake = FakeKernels()
    monkeypatch.setattr(wbm.Workbench, "kernels", lambda self: fake)
    brain = FakeBrain(varying_responder)
    ctx = make_ctx(tmp_path, brain=brain)
    async with running(ctx) as (srv, L, _R), session() as s:
        pid = (await (await s.post(L + "/api/projects", json={"title": "P"})).json())["project"]["id"]
        doc = (await (await s.post(L + f"/api/calcul/{pid}/docs", json={"title": "N", "language": "python"}))
               .json())["doc"]["id"]
        D = L + f"/api/calcul/{pid}/docs/{doc}"
        q = (await (await s.post(D + "/cells", json={"type": "ask", "prompt": "corps F_12"})).json())["cell"]
        r = await s.post(D + f"/cells/{q['id']}/ask", json={})
        j = await r.json()
        assert r.status == 422 and j["error"] == "bad_request_math" and "12 = 2^2 × 3" in j["message"]["text"] and not brain.requests
        q = (await (await s.post(D + "/cells", json={"type": "ask", "prompt": "dérivée de x^3 e^{2x}"})).json())["cell"]
        j1 = await (await s.post(D + f"/cells/{q['id']}/ask", json={})).json()
        assert j1["origin"] == "catalogue" and j1["coverage"] == "full" and not brain.requests
        assert j1["cell"]["recognized"]["fr"] == "dérivée de x^3*exp(2*x)" and j1["cell"]["gen"] == "catalogue"
        j2 = await (await s.post(D + f"/cells/{q['id']}/ask", json={})).json()          # « Réécrire »
        assert j2["cell"]["code"] == j1["cell"]["code"] and j2["cell"]["code_hash"] == j1["cell"]["code_hash"]
        j3 = await (await s.post(D + f"/cells/{q['id']}/ask", json={"variant": True})).json()   # « Autre version »
        assert j3["origin"] == "variant" and j3["cell"]["code"] != j1["cell"]["code"] and len(brain.requests) == 1
        # the variant runs OK, the catalogue version was never run: the variant becomes the best
        await s.post(D + f"/cells/{q['id']}/approve", json={"code_hash": j3["cell"]["code_hash"]})
        assert (await (await s.post(D + f"/cells/{q['id']}/run")).json())["run"]["status"] == "ok"
        j4 = await (await s.post(D + f"/cells/{q['id']}/ask", json={})).json()
        assert j4["cell"]["code"] == j3["cell"]["code"] and j4["origin"] == "best"
        # analysis endpoint and catalogue listing (no model)
        a = await (await s.post(L + "/api/calcul/analyze", json={"text": "racines de x^2-2 dans F_{7}",
                                                                 "language": "sage"})).json()
        assert a["coverage"] == "full" and a["code"].startswith("F7 = GF(7)") and "F₇" in a["recognized"]["fr"]
        cat = await (await s.get(L + "/api/calcul/catalogue")).json()
        assert cat["samples"] and "sage" in cat["status"] and cat["lean"]["gf"]["v4.9"]
