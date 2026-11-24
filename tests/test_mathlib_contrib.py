"""« Préparer une contribution à Mathlib » (session S-BC, DECISIONS D61, docs/MATHLIB_CONTRIB.md).

- pure: names proposed on known statement shapes, every style rule positive and negative, renames / syntax port,
  Lean output parsing, the file and the PR texts, Mathlib.lean insertion;
- REAL Lean (skipped when the workspaces are not built here; `MADALEAN_TEST_TOOLCHAINS` adds a toolchain root):
  a known lemma is detected as already in Mathlib (stop), and a tiny proof from lean-prover49 with a renamed
  lemma is ported to lean-current, its imports shrunk, Mathlib's #lint run, the package generated;
- GitHub only against a FAKE GitHub API: nothing without the key, a plan shown first and sent once, the PR needs its
  own plan, host only."""
from __future__ import annotations

import asyncio
import base64
import contextlib
import os
import time
from pathlib import Path

import pytest
from aiohttp import web

from madalean import leancheck
from madalean import workspaces as W
from madalean.research import mathlib_contrib as MC
from madalean.research import publish
from madalean.workspaces import Workspace
from helpers import make_ctx, running, session


# ---------------------------------------------------------------- naming
@pytest.mark.parametrize("decl, full", [
    ("theorem t (a b : ℕ) (h : a ≤ b) : a + 0 ≤ b + 0 := by simp", "Nat.add_zero_le_add_zero_of_le"),
    ("theorem t (x : ℝ) : 0 ≤ x ^ 2 + 1 := by positivity", "Real.sq_add_one_nonneg"),
    ("theorem t (a b : ℝ) : a * b ≤ (a ^ 2 + b ^ 2) / 2 := by nlinarith", "Real.mul_le_sq_add_sq_div_two"),
    ("theorem t (n : ℕ) (hn : 0 < n) : n ! ≠ 0 := by positivity", "Nat.factorial_ne_zero_of_pos"),
    ("theorem t (a b : ℤ) (h : a ∣ b) : a ∣ b * 3 := by sorry", "Int.dvd_mul_three_of_dvd"),
    ("theorem t (x : ℝ) (hx : 0 < x) : Real.log x ≤ x - 1 := by sorry", "Real.log_le_sub_one_of_pos"),
    ("theorem t (n : ℕ) : ∑ i ∈ Finset.range n, (2 * i + 1) = n ^ 2 := by sorry",
     "Nat.sum_range_two_mul_add_one_eq_sq"),
    ("theorem t (n : ℕ) : Even (n * (n + 1)) := by sorry", "Nat.even_mul_add_one"),
    ("theorem t (x : ℝ) (n : ℕ) (h : x ≠ 0) : x ^ n ≠ 0 := by sorry", "pow_ne_zero_of_ne_zero"),
])
def test_names_follow_the_naming_guide(decl, full):
    s = MC.suggest_name(decl, "Titre")
    assert s["full"] == full, s
    assert not s["fallback"] and all(w["word"] for w in s["words"])


def test_name_fallback_and_explanation():
    s = MC.suggest_name("theorem t : True := by trivial", "Mon résultat")
    assert s["full"] and s["name"].replace("_", "").isalnum()
    s = MC.suggest_name("theorem t (x : ℝ) (h : 0 ≤ x) : 0 ≤ x ^ 3 := by positivity")
    assert s["full"] == "Real.pow_three_nonneg_of_nonneg"
    assert {"nonneg", "namespace"} <= set(s["rules"])
    assert [w["word"] for w in s["words"] if w["part"] == "hypothesis"] == ["of", "nonneg"]


# ---------------------------------------------------------------- style rules, each positive and negative
GOOD = """/-
Copyright (c) 2026 Ada Lovelace. All rights reserved.
Released under Apache 2.0 license as described in the file LICENSE.
Authors: Ada Lovelace
-/
module

public import Mathlib.Algebra.Order.Ring.Lemmas

/-!
# Squares

This file proves `foo_le`.
-/

public section

/-- If `a ≤ b`, then `a ≤ b + 0`. -/
theorem foo_le {a b : ℕ} (h : a ≤ b) : a ≤ b + 0 := by
  simp only [add_zero]
  exact h
"""


def _checks(text):
    decls = MC.split_decls(text[text.find("public section"):])
    return {c["id"]: c for c in MC.text_checks(text, decls)}


def test_every_text_rule_passes_on_a_good_file():
    cs = _checks(GOOD)
    assert all(c["ok"] for c in cs.values()), [c for c in cs.values() if not c["ok"]]
    assert set(cs) == {"line_length", "whitespace", "copyright_header", "module_docstring", "no_sorry_axioms",
                       "max_heartbeats", "name_snake_case", "docstrings", "non_terminal_simp", "ge_gt",
                       "implicit_args"}


@pytest.mark.parametrize("rule, mutate", [
    ("line_length", lambda t: t.replace("exact h", "exact h -- " + "x" * 100)),
    ("whitespace", lambda t: t.replace("exact h", "exact h  ")),
    ("copyright_header", lambda t: t.replace("All rights reserved.", "")),
    ("module_docstring", lambda t: t.replace("/-!\n# Squares", "/-\n# Squares")),
    ("no_sorry_axioms", lambda t: t.replace("exact h", "sorry")),
    ("max_heartbeats", lambda t: t.replace("public section\n", "public section\n\nset_option maxHeartbeats 400000\n")),
    ("name_snake_case", lambda t: t.replace("foo_le", "FooLe")),
    ("docstrings", lambda t: t.replace("/-- If `a ≤ b`, then `a ≤ b + 0`. -/\n", "")),
    ("docstrings", lambda t: t.replace("then `a ≤ b + 0`.", "then `a ≤ b + 0`")),
    ("non_terminal_simp", lambda t: t.replace("simp only [add_zero]", "simp")),
    ("non_terminal_simp", lambda t: t.replace("simp only [add_zero]\n  exact h", "simp <;> exact h")),
    ("ge_gt", lambda t: t.replace("(h : a ≤ b) : a ≤ b + 0", "(h : b ≥ a) : a ≤ b + 0")),
    ("implicit_args", lambda t: t.replace("{a b : ℕ}", "(a b : ℕ)")),
])
def test_each_rule_fails_on_its_violation(rule, mutate):
    bad = mutate(GOOD)
    assert bad != GOOD
    cs = _checks(bad)
    assert cs[rule]["ok"] is False and cs[rule]["severity"] == MC.CHECKS[rule][0], cs[rule]
    # a terminal `simp` is fine; `simpa` and `simp only` are never flagged
    assert not MC.simp_lines("  simp\n") and not MC.simp_lines("  simpa using h\n  exact h\n")


def test_lint_and_imports_parsing():
    msg = leancheck.LeanMessage
    ok, _ = MC.lint_result([msg("information", 1, 0, None, None, "-- Found 0 errors in 2 declarations\n"
                                "-- All linting checks passed!")])
    assert ok is True
    bad, text = MC.lint_result([msg("information", 1, 0, None, None, "-- Found 1 error in 1 declarations\n#check x")])
    assert bad is False and "Found 1 error" in text
    assert MC.lint_result([])[0] is None
    mods = MC.min_imports([msg("information", 3, 0, None, None, "public import Mathlib.A.B\npublic import Mathlib.C"),
                           msg("information", 9, 0, None, None, "import Mathlib.A.B")])
    assert mods == ["Mathlib.A.B", "Mathlib.C"]
    assert MC.tactic_modules("  positivity\n  nlinarith [sq_nonneg x]") == ["Mathlib.Tactic.Linarith",
                                                                            "Mathlib.Tactic.Positivity"]
    dep = MC.deprecations([msg("warning", 2, 0, None, None,
                               "`Finset.card_le_of_subset` has been deprecated, use `Finset.card_le_card` instead")])
    assert dep == {"Finset.card_le_of_subset": "Finset.card_le_card"}


def test_renames_syntax_and_single_lemma():
    code, used = MC.rename_idents("exact pow_lt_pow h; exact Foo.pow_lt_pow; -- pow_lt_pow", MC.BUILTIN_RENAMES)
    assert code.startswith("exact pow_lt_pow_right₀ h; exact Foo.pow_lt_pow;")     # chained, whole names only
    assert used == [{"old": "pow_lt_pow", "new": "pow_lt_pow_right₀"}]
    assert MC.syntax_port("∑ i in Finset.range n, f i")[0] == "∑ i ∈ Finset.range n, f i"
    assert MC.single_lemma("apply Even.add\nall_goals try assumption", "Even.add")
    assert MC.single_lemma("exact Even.add hm hn", "Even.add")
    assert not MC.single_lemma("exact Nat.mul_le_mul (Finset.card_le_card h) hx", "Nat.mul_le_mul")


def test_package_pieces():
    decls = [("If `a ≤ b`, then `a ≤ b + 0`.", "theorem foo_le {a b : ℕ} (h : a ≤ b) : a ≤ b + 0 := by\n  omega")]
    text = MC.build_file(author="Ada Lovelace", year=2026, title="Squares", summary="This file proves `Nat.foo_le`.",
                         imports=["Mathlib.Order.Basic"], opens=[], namespace="Nat", decls=decls,
                         main_full="Nat.foo_le")
    assert "namespace Nat" in text and text.rstrip().endswith("end Nat")
    cs = _checks(text)
    assert all(c["ok"] for c in cs.values()), [c for c in cs.values() if not c["ok"]]
    tp = MC.target_path(["Mathlib.Order.Basic", "Mathlib.Order.Basic", "Mathlib.Tactic.Ring", "Mathlib.Data.X"],
                        "Nat.foo_le")
    assert tp == {"closest": "Mathlib.Order.Basic", "module": "Mathlib.Order.FooLe",
                  "path": "Mathlib/Order/FooLe.lean", "closest_path": "Mathlib/Order/Basic.lean"}
    # the file's own minimal imports come first; the index's votes only choose among them
    assert MC.target_path(["Mathlib.Algebra.Group.Nat.Even"], "card_mul_three_le_card_mul",
                          ["Mathlib.Data.Finset.Card", "Mathlib.Tactic.Ring"])["path"] == \
        "Mathlib/Data/Finset/CardMulThreeLe.lean"
    long_ = ("theorem card_mul_three_le_card_mul_of_subset_of_three_le (s t : Finset ℕ) (h : s ⊆ t) (x : ℕ) "
             "(hx : 3 ≤ x) : s.card * 3 ≤ t.card * x := by\n  omega")
    wrapped = MC.wrap_signature(long_)
    assert all(len(line) <= 100 for line in wrapped.split("\n")) and wrapped.endswith(":= by\n  omega")
    assert " ".join(wrapped.split()) == " ".join(long_.split()) and wrapped.split("\n")[1].startswith("    ")
    assert MC.wrap_signature("theorem a (x : ℕ) : x = x := by\n  rfl") == "theorem a (x : ℕ) : x = x := by\n  rfl"
    pr = MC.pr_texts(full="Nat.foo_le", path=tp["path"], doc="If `a ≤ b`, then `a ≤ b + 0`.", lean="v4.36.0",
                     mathlib="0123456789abcdef", closest=tp["closest_path"], title="Squares")
    assert pr["title"] == "feat(Order): add `Nat.foo_le`" and "Madalean" in pr["body"] and pr["explain"]["fr"]
    assert MC.mathlib_lean_insert("public import Mathlib.A\npublic import Mathlib.C\n", "Mathlib.B") == \
        "public import Mathlib.A\npublic import Mathlib.B\npublic import Mathlib.C\n"


def test_public_import_is_checked_like_import():
    assert leancheck.exec_risks("module\npublic import Evil.Thing\n")
    assert leancheck.exec_risks("meta import Evil\n")
    assert not leancheck.exec_risks("module\npublic import Mathlib.Order.Basic\n")


# ---------------------------------------------------------------- real Lean
@pytest.fixture(scope="module", autouse=True)
def extra_toolchains():
    extra = [Path(p) for p in os.environ.get("MADALEAN_TEST_TOOLCHAINS", "").split(os.pathsep) if p]
    orig = W.toolchain_roots
    if extra:
        W.toolchain_roots = lambda: orig() + extra
    yield
    W.toolchain_roots = orig


def _ws(key):
    return next((w for w in W.all_workspaces(scan_user=False) if w.key == key and not w.problems), None)


@pytest.fixture(scope="module")
def both():
    cur, old = _ws("lean-current"), _ws("lean-prover49")
    if cur is None or old is None:
        pytest.skip("lean-current and lean-prover49 are not both built here")
    return old, cur


async def _wait(s, url, timeout=900):
    t0 = time.monotonic()
    while time.monotonic() - t0 < timeout:
        st = await (await s.get(url)).json()
        if not st["running"] and st["package"] and st["package"]["state"] != "running":
            return st
        await asyncio.sleep(0.3)
    raise TimeoutError(url)


async def test_known_lemma_is_already_in_mathlib(tmp_path, both):
    old, cur = both
    ctx = make_ctx(tmp_path, ws=cur)
    ctx._fixed_workspaces = ctx.workspaces = [old, cur]
    proof = (leancheck.GOEDEL_HEADER + "theorem even_sum_bc {m n : ℕ} (hm : Even m) (hn : Even n) : Even (m + n) := by"
             "\n  obtain ⟨a, rfl⟩ := hm\n  obtain ⟨b, rfl⟩ := hn\n  exact ⟨a + b, by ring⟩\n")
    async with running(ctx) as (_s, L, _R), session() as s:
        e = ctx.library.add_proof(proof, "Somme de pairs", cur.key)
        r = await s.post(L + "/api/mathlib/contrib", json={"kind": "library", "id": e.name})
        assert r.status == 200, await r.text()
        st = await _wait(s, L + f"/api/mathlib/contrib?kind=library&id={e.name}")
        p = st["package"]
        assert p["state"] == "in_mathlib", p
        assert p["in_mathlib"]["lemma"] == "Even.add" and p["port"]["ok"] and not p["port"]["renames"]
        assert p["file"] is None and p["pr"] is None
        assert [x["state"] for x in p["steps"]][:2] == ["ok", "fail"]


async def test_port_from_prover49_shrinks_imports_and_builds_the_package(tmp_path, both):
    old, cur = both
    ctx = make_ctx(tmp_path, ws=old)
    ctx._fixed_workspaces = ctx.workspaces = [old, cur]
    proof = (leancheck.GOEDEL_HEADER +
             "theorem card_port_bc (s t : Finset ℕ) (h : s ⊆ t) (x : ℕ) (hx : 3 ≤ x) :\n"
             "    s.card * 3 ≤ t.card * x := by\n"
             "  have h1 := Finset.card_le_of_subset h\n"
             "  exact Nat.mul_le_mul h1 hx\n")
    async with running(ctx) as (_s, L, _R), session() as s:
        e = ctx.library.add_proof(proof, "Cardinal et sous-ensemble", old.key)
        assert e is not None
        r = await s.post(L + "/api/mathlib/contrib", json={"kind": "library", "id": e.name, "author": "Ada Lovelace"})
        assert r.status == 200
        st = await _wait(s, L + f"/api/mathlib/contrib?kind=library&id={e.name}")
        p = st["package"]
        assert p["state"] == "ready", p
        assert {"old": "Finset.card_le_of_subset", "new": "Finset.card_le_card"} in p["port"]["renames"]
        assert p["port"]["from"] == "lean-prover49" and p["port"]["to"] == "lean-current"
        assert p["in_mathlib"] is None or not p["in_mathlib"]["lemma"]
        text = p["file"]["text"]
        assert "Finset.card_le_card" in text and "card_le_of_subset" not in text
        assert "public import Mathlib\n" not in text and "public import Mathlib." in text, text
        assert text.startswith("/-\nCopyright (c) ") and "Authors: Ada Lovelace" in text
        assert p["name"]["full"] in text and p["name"]["free"] is True
        cs = {c["id"]: c for c in p["checks"]}
        for must in ("lean_current", "no_sorry_axioms", "not_in_mathlib", "name_free", "copyright_header",
                     "module_docstring", "docstrings", "imports_minimal"):
            assert cs[must]["ok"] is True, cs[must]
        assert cs["lint"]["ok"] is True, cs["lint"]
        assert cs["implicit_args"]["ok"] is False          # s, t, x are fixed by h and hx: Mathlib wants them implicit
        assert p["target"]["path"].startswith("Mathlib/") and p["pr"]["title"].startswith("feat(")
        # a fresh strict Lean accepts the downloaded file as is
        dl = await s.get(L + f"/api/mathlib/contrib/file?kind=library&id={e.name}")
        assert dl.status == 200 and "attachment" in dl.headers["Content-Disposition"]
        assert await dl.text() == text
        res = await ctx.lean.check(leancheck.with_axiom_probe(text, p["name"]["full"]), cur, 240, p["name"]["full"])
        assert res.verdict.ok, res.verdict.summary


# ---------------------------------------------------------------- fake Lean: sources, reprove; fake GitHub
def _fake_ctx(tmp_path):
    ctx = make_ctx(tmp_path)
    ctx.workspaces.append(Workspace("lean-current", "cur", tmp_path / "nocur", "leanprover/lean4:v4.36.0", True))
    ctx._fixed_workspaces = list(ctx.workspaces)
    return ctx


def _ready_pkg(ctx, name):
    pkg = MC.new_package({"kind": "library", "id": name, "title": "T", "workspace": "lean-current", "main": name,
                          "dossier": ""}, "Ada")
    pkg.update(state="ready", name={"full": "Nat.foo_le", "name": "foo_le", "namespace": "Nat"},
               file={"path": "Mathlib/Order/FooLe.lean", "text": "-- the file\n"},
               target={"module": "Mathlib.Order.FooLe", "path": "Mathlib/Order/FooLe.lean"},
               pr={"title": "feat(Order): add `Nat.foo_le`", "body": "This PR adds it.", "explain": {}})
    MC.save(ctx, pkg)
    return pkg


async def test_sources_and_reprove(tmp_path):
    ctx = _fake_ctx(tmp_path)
    async with running(ctx) as (_s, L, _R), session() as s:
        assert (await s.get(L + "/api/mathlib/contrib?kind=nope&id=x")).status == 400
        r = await s.post(L + "/api/mathlib/contrib", json={"kind": "library", "id": "missing"})
        assert r.status == 404
        d = ctx.repo.new("p", "demo", "Sans preuve")
        await ctx.repo.save(d)
        r = await s.post(L + "/api/mathlib/contrib", json={"kind": "dossier", "id": d.id})
        assert r.status == 409 and (await r.json())["error"] == "not_verified"
        proof = leancheck.GOEDEL_HEADER + "theorem old_bc (s t : Finset ℕ) (h : s ⊆ t) : s.card ≤ t.card := by\n" \
                                          "  exact Finset.card_le_of_subset h\n"
        e = ctx.library.add_proof(proof, "Ancien", "demo")
        assert (await s.post(L + "/api/mathlib/contrib/reprove", json={"kind": "library", "id": e.name})).status == 409
        pkg = MC.new_package(MC.source_of(ctx, "library", e.name), "Ada")
        pkg["state"] = "port_failed"
        MC.save(ctx, pkg)
        plans = []
        submit = ctx.orchestrator.submit
        ctx.orchestrator.submit = lambda did, plan, **kw: (plans.append(plan), submit(did, plan, **kw))[1]
        r = await s.post(L + "/api/mathlib/contrib/reprove", json={"kind": "library", "id": e.name})
        assert r.status == 200, await r.text()
        nd = ctx.repo.get((await r.json())["dossier"])
        assert nd.workspace == "lean-current" and "(s t : Finset ℕ) (h : s ⊆ t) : s.card ≤ t.card" in nd.statement
        assert nd.statement.rstrip().endswith("sorry")
        # the normal pipeline, with the old proof as the user's hint
        assert plans[0][0]["stage"] == "proof" and "Finset.card_le_of_subset h" in plans[0][0]["request"]


def fake_github(state: dict) -> web.Application:
    app = web.Application()

    def log(request):
        state["calls"].append((request.method, request.path_qs))
        if request.headers.get("Authorization") != "Bearer ghp_fake":
            return web.json_response({"message": "Bad credentials"}, status=401)
        return None

    async def user(request):
        return log(request) or web.json_response({"login": "ada"}, headers={"X-OAuth-Scopes": "public_repo"})

    async def forks(request):
        return log(request) or web.json_response({"full_name": "ada/mathlib4"}, status=202)

    async def repo(request):
        return log(request) or web.json_response({"full_name": "ada/mathlib4"})

    async def ref(request):
        return log(request) or web.json_response({"object": {"sha": "abc123"}})

    async def refs(request):
        if (r := log(request)) is not None:
            return r
        state["ref"] = await request.json()
        return web.json_response({}, status=201)

    async def contents(request):
        if (r := log(request)) is not None:
            return r
        path = request.match_info["p"]
        if request.method == "GET":
            return web.json_response({"sha": "m1", "content": base64.b64encode(
                b"public import Mathlib.A\npublic import Mathlib.Z\n").decode()})
        data = await request.json()
        state["files"][path] = base64.b64decode(data["content"]).decode()
        return web.json_response({"content": {"path": path}}, status=201)

    async def pulls(request):
        if (r := log(request)) is not None:
            return r
        state["pr"] = await request.json()
        return web.json_response({"number": 7, "html_url": "https://github.com/x/pull/7"}, status=201)
    app.router.add_get("/user", user)
    app.router.add_post("/repos/leanprover-community/mathlib4/forks", forks)
    app.router.add_get("/repos/ada/mathlib4", repo)
    app.router.add_get("/repos/leanprover-community/mathlib4/git/ref/heads/master", ref)
    app.router.add_post("/repos/ada/mathlib4/git/refs", refs)
    app.router.add_route("*", "/repos/ada/mathlib4/contents/{p:.+}", contents)
    app.router.add_post("/repos/leanprover-community/mathlib4/pulls", pulls)
    return app


@contextlib.asynccontextmanager
async def fake_gh(monkeypatch):
    state = {"calls": [], "files": {}}
    runner = web.AppRunner(fake_github(state))
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    monkeypatch.setattr(publish, "GITHUB_API", f"http://127.0.0.1:{site._server.sockets[0].getsockname()[1]}")
    yield state
    await runner.cleanup()


async def test_github_branch_then_pr_against_a_fake_github(tmp_path, monkeypatch):
    ctx = _fake_ctx(tmp_path)
    async with fake_gh(monkeypatch) as gh, running(ctx) as (_s, L, R), session() as s:
        pkg = _ready_pkg(ctx, "foo_le")
        src = {"kind": "library", "id": "foo_le"}
        st = await (await s.get(L + "/api/mathlib/contrib?kind=library&id=foo_le")).json()
        assert st["github"] == {"configured": False, "host": True}
        r = await s.post(L + "/api/mathlib/contrib/github/plan", json={**src, "step": "branch"})
        assert r.status == 409 and (await r.json())["error"] == "no_github_key" and not gh["calls"]
        ctx.keys.set("github", "ghp_fake")
        assert (await (await s.get(L + "/api/mathlib/contrib?kind=library&id=foo_le")).json())["github"]["configured"]
        # from a paired device: refused before anything is sent
        assert (await s.post(R + "/api/mathlib/contrib/github/plan", json=src)).status in (401, 403)
        # the PR needs a branch first
        assert (await s.post(L + "/api/mathlib/contrib/github/plan", json={**src, "step": "pr"})).status == 409
        r = await s.post(L + "/api/mathlib/contrib/github/plan", json={**src, "step": "branch"})
        plan = (await r.json())["plan"]
        assert gh["calls"] == [("GET", "/user")]                     # planning is read-only
        assert plan["fork"] == "ada/mathlib4" and plan["branch"] == "madalean/Nat.foo_le"
        assert plan["content"] == pkg["file"]["text"] and [q["method"] for q in plan["requests"]] == \
            ["POST", "GET", "POST", "PUT", "GET", "PUT"]
        assert (await s.post(L + "/api/mathlib/contrib/github/send", json={**src, "plan": "forged"})).status == 409
        r = await s.post(L + "/api/mathlib/contrib/github/send", json={**src, "plan": plan["id"]})
        assert r.status == 200, await r.text()
        res = (await r.json())["result"]
        assert res["branch"] == "madalean/Nat.foo_le" and "compare" in res["compare_url"]
        assert gh["ref"] == {"ref": "refs/heads/madalean/Nat.foo_le", "sha": "abc123"}
        assert gh["files"]["Mathlib/Order/FooLe.lean"] == "-- the file\n"
        assert "public import Mathlib.Order.FooLe\n" in gh["files"]["Mathlib.lean"]
        assert "pulls" not in str(gh["calls"])                       # no PR without its own confirmation
        # a confirmed plan is sent at most once
        assert (await s.post(L + "/api/mathlib/contrib/github/send", json={**src, "plan": plan["id"]})).status == 409
        r = await s.post(L + "/api/mathlib/contrib/github/plan", json={**src, "step": "pr"})
        pr_plan = (await r.json())["plan"]
        assert pr_plan["requests"][0]["body"]["draft"] is True
        assert pr_plan["requests"][0]["body"]["head"] == "ada:madalean/Nat.foo_le"
        r = await s.post(L + "/api/mathlib/contrib/github/send", json={**src, "plan": pr_plan["id"]})
        assert r.status == 200 and (await r.json())["result"]["number"] == 7
        assert gh["pr"]["title"] == "feat(Order): add `Nat.foo_le`" and gh["pr"]["base"] == "master"
        assert MC.load(ctx, "library:foo_le")["github"]["pr"]["number"] == 7
