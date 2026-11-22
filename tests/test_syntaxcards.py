"""S-AB (DECISIONS D35): the version-aware syntax catalogue — Sage card checked by the installed Sage, signatures
and names from the installed version, the pre-run validator; Lean card checked by the workspace's Lean and its
declaration index; automatic rebuild on a version change."""
import asyncio
import json
import types
from pathlib import Path

import pytest

from madalean import leancheck, syntaxcards as sc
from madalean.research.codegen import partial_code

needs_sage = pytest.mark.skipif(sc.sage_python() is None, reason="SageMath not installed")


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    if sc.sage_python() is None:
        pytest.skip("SageMath not installed")
    d = tmp_path_factory.mktemp("cards")
    old = dict(sc._DIR)
    sc.configure(d)
    bad = ("bogus", "a rule whose snippet fails in this version", "this_function_does_not_exist_in_sage(1)")
    entries = sc.SAGE_ENTRIES
    sc.SAGE_ENTRIES = entries + [bad]
    try:
        card = sc.build_sage()
    finally:
        sc.SAGE_ENTRIES = entries
    yield card, d
    sc._DIR.update(old)


@needs_sage
def test_sage_card_is_checked_against_the_installed_version(built):
    card, d = built
    v = sc.sage_version()
    assert v and card["version"] == v and (d / "syntax" / f"sage-{v}.json").is_file()
    kept = {e["id"] for e in card["entries"]}
    assert kept == {e[0] for e in sc.SAGE_ENTRIES}                   # every real entry runs on this Sage…
    assert "bogus" in card["dropped"] and "NameError" in card["dropped"]["bogus"]   # …a failing one is dropped
    text, verified = sc.sage_card(v)
    assert verified and text.startswith(f"SageMath {v}") and "assume(n, 'integer')" in text
    assert "bogus" not in text and len(text) < 7000                  # small: ≈ 1.5 k tokens
    assert "integral" in card["names"] and "fourier_series_partial_sum" not in card["names"]
    # another version installed (update): no card for it yet → the built-in rules, marked unverified
    text2, verified2 = sc.sage_card("99.0")
    assert not verified2 and "SageMath 99.0" in text2


@needs_sage
def test_signatures_of_the_functions_the_request_needs(built):
    s = sc.sage_signatures("la série de Fourier de x² sur [0,2pi]")
    assert "fourier_series_partial_sum(N, L=None)" in s and "parameters" not in s
    s2 = sc.sage_signatures("rien", code="r = integral(x^2, x, 0, 1)")
    assert s2.startswith("- integral(")
    assert sc.sage_signatures("x", version="99.0") == ""


@needs_sage
def test_validator_preparses_compiles_and_finds_undefined_names(built):
    ok = sc.validate_sage("f(x) = x^2\nR.<t> = QQ[]\nn = var('n')\nintegral(f(x), x, 0, 1) + total", known={"total"})
    assert ok["ok"] and ok["checked"]
    bad = sc.validate_sage("for k in range(3:\n    pass")
    assert not bad["ok"] and bad["error"].startswith("SyntaxError")
    unk = sc.validate_sage("a = integrale(x^2, x)")
    assert not unk["ok"] and unk["unknown"] == ["integrale"] and "integral" in unk["error"]
    assert sc.validate_python("print(1") ["ok"] is False and sc.validate_python("1 + 1")["ok"]


def test_partial_code_for_streaming():
    assert partial_code("Voici :\n```sage\nf = x^2\nplot(f") == "f = x^2\nplot(f"
    assert partial_code("```python\n1 + 1\n```\nfin") == "1 + 1"
    assert partial_code("pas encore de code") == ""


class FakeLean:
    """Answers like `lean --json`: errors at given entries, a deprecation warning at another."""

    def __init__(self, fail: str, deprecated: str):
        self.fail, self.deprecated, self.code = fail, deprecated, ""

    async def check(self, code, ws, timeout_s=180, strict_name=None, owner=None):
        self.code = code
        lines = code.split("\n")
        def line_of(eid):
            return next(i + 2 for i, l in enumerate(lines) if l == f"-- {eid}")
        err = leancheck.LeanMessage("error", line_of(self.fail), 0, None, None, "unexpected token 'in'")
        warn = {"severity": "warning", "pos": {"line": line_of(self.deprecated), "column": 0},
                "data": "`Nat.cast_le` has been deprecated, use `Nat.cast_le_cast` instead"}
        v = leancheck.Verdict(False, "x", errors=[err])
        return types.SimpleNamespace(verdict=v, stdout=json.dumps(warn) + "\n", infra_error="", timed_out=False)


def test_lean_card_drops_what_fails_or_is_deprecated_and_follows_the_version(tmp_path, monkeypatch):
    sc.configure(tmp_path)
    ws = types.SimpleNamespace(key="w", path=tmp_path / "w", toolchain="leanprover/lean4:v4.36.0",
                               has_mathlib=lambda: True, problems=[])
    info = {"lean": "v4.36.0", "mathlib": "v4.36.0 @ abc"}
    monkeypatch.setattr("madalean.runtime.lean.workspace_info", lambda w: dict(info))
    idx = {"Nat.succ_le_iff", "Finset.prod_range_succ", "sq_nonneg", "Nat.cast_le", "Nat.Prime", "Real.sqrt_sq"}
    monkeypatch.setattr("madalean.names.get", lambda w, wait=False: idx)
    lean = FakeLean("bigop_in", "cast")
    card = asyncio.run(sc.build_lean(types.SimpleNamespace(lean=lean), ws))
    ids = {e["id"] for e in card["entries"]}
    assert "bigop_in" not in ids and "cast" not in ids and "bigop" in ids and "lean4" in ids
    assert card["dropped"]["real"] == "name not in this Mathlib"      # Real.pi_pos is not in the index
    assert "-- real" not in lean.code                               # …so it was not even compiled
    assert lean.code.startswith(leancheck.GOEDEL_HEADER)
    text = sc.lean_card(ws)
    assert text.startswith("Lean v4.36.0, Mathlib v4.36.0 @ abc") and "∑ i ∈ Finset.range n" in text
    # Mathlib updated: another key → no card until it is rebuilt (never a card of another version)
    info["mathlib"] = "v4.37.0 @ def"
    assert sc.lean_card(ws) == ""
    assert asyncio.run(sc.ensure_lean(types.SimpleNamespace(lean=lean, workspace=lambda: ws), ws)) is True
    assert sc.lean_card(ws).startswith("Lean v4.36.0, Mathlib v4.37.0 @ def")


def test_update_checkers_pass_schedules_the_rebuild(monkeypatch):
    from madalean import update_checkers, updates
    calls = []
    monkeypatch.setattr(sc, "schedule", lambda ctx, loop=None: calls.append(ctx))
    ctx = types.SimpleNamespace(settings=types.SimpleNamespace(mode="local"))
    monkeypatch.setattr(update_checkers, "_CTX", {"ctx": lambda: ctx, "loop": None})
    assert update_checkers.syntax_checker()() == [] and calls == [ctx]   # also in « local » mode: no network
    class Ctx:                                                  # register keeps a weak reference
        settings = ctx.settings
    update_checkers.register(Ctx())
    assert "Syntaxe" in [n for n, _f in updates.CHECKERS]


def test_recipes_shortcut_example_version_and_safety(tmp_path):
    from madalean.research.recipes import RecipeStore, template
    st = RecipeStore(tmp_path / "recipes.json")
    st.add("Les racines dans F_16 de x^5+x^3+x+1", "F.<a> = GF(16)\nR.<x> = F[]\n(x^5+x^3+x+1).roots()", "sage", "10.10")
    m = st.match("les racines dans F_8 de x^3+x+1", "sage", "10.10", set())
    assert m["kind"] == "shortcut" and m["code"] == "F.<a> = GF(8)\nR.<x> = F[]\n(x^3+x+1).roots()"
    assert template("Les racines dans F_16 de x^5+x^3+x+1") == "les racines dans # de #"
    # a parameter seen twice in the code is not substituted blindly: example for the model instead
    st.add("les 5 premiers nombres premiers", "primes_first_n(5)  # 5", "sage", "10.10")
    assert st.match("les 7 premiers nombres premiers", "sage", "10.10", set())["kind"] == "example"
    # relied on earlier cells: only when those names exist again
    st.add("les racines de f dans F", "f.roots(F)", "sage", "10.10", uses=["F", "f"])
    assert st.match("les racines de f dans F", "sage", "10.10", set()) is None or \
        st.match("les racines de f dans F", "sage", "10.10", set())["kind"] == "example"
    assert st.match("les racines de f dans F", "sage", "10.10", {"F", "f"})["kind"] == "shortcut"
    # another Sage version: nothing until re-checked; re-check keeps what compiles and drops the rest
    assert st.match("les racines dans F_8 de x^3+x+1", "sage", "10.11", set()) is None
    res = st.revalidate("sage", "10.11", lambda r: "primes_first_n" not in r["code"])
    assert res["dropped"] == 1 and {r["version"] for r in st.list()} == {"10.11"}
    assert (tmp_path / "recipes.json").stat().st_mode & 0o077 == 0
    rid = st.list()[0]["id"]
    assert st.delete(rid) and not st.delete(rid)
