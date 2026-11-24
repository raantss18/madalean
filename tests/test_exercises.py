"""Verified exercises (D63) and the Malagasy fallback chain. Every seed solution is compiled by the real Lean."""
import importlib.util
import json
import re
from pathlib import Path

import pytest

from madalean import i18n, leancheck
from madalean.brain.fake import FakeBrain
from madalean.i18n_en import EN
from madalean.i18n_mg import MG
from madalean.teaching import exercises as X
from helpers import make_ctx, running, session

E = X.seed()


# ---------------------------------------------------------------- language
def test_malagasy_falls_back_to_french_never_english():
    try:
        i18n.set_language("mg")
        assert i18n.ui_language() == "mg" and i18n.language() == "fr"
        assert i18n.pick("fr", "en") == "fr"
        assert i18n._("Preuve acceptée par Lean ✔") == MG["Preuve acceptée par Lean ✔"]
        k = next(k for k in EN if k not in MG and EN[k] != k)
        assert i18n._(k) == k                                   # French, not EN[k]
        assert i18n.msg("Lean a trouvé {n} erreurs.", n=3)["text"] == "Nahita diso 3 i Lean."
        i18n.set_language("en")
        assert i18n._(k) == EN[k] and i18n.language() == "en"
    finally:
        i18n.set_language("fr")
    assert i18n.content_language("mg") == "fr"


def test_malagasy_server_catalogue():
    spec = importlib.util.spec_from_file_location("k", Path(__file__).parents[1] / "scripts/dev/madalean_i18n_keys.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    known = m.keys() | set(EN)
    ph = lambda s: sorted(re.findall(r"\{[^}]*\}", s))  # noqa: E731
    for k, v in MG.items():
        assert k in known and v.strip() and ph(k) == ph(v), k


# ---------------------------------------------------------------- bank
def test_seed_bank():
    assert len(E) >= 20 and {e["level"] for e in E} == set(X.LEVELS) and len({e["domain"] for e in E}) >= 6
    for e in E:
        assert all(set(e[k]) == set(X.LANGS) for k in ("title", "statement")) and e["solution"] and e["hints"]
        assert e["source"] and e["licence"]


async def test_every_seed_exercise_is_accepted_by_lean(ws, tmp_path):
    ctx = make_ctx(tmp_path, ws=ws)
    H = leancheck.GOEDEL_HEADER
    r = await ctx.lean.check(H + "\n".join(e["lean"] for e in E), ws, 500)
    assert r.to_dict()["statement_ok"], r.verdict.errors
    names = [X.check_signature(e["lean"]) for e in E]
    code = H + "\n".join(X.assemble(e["lean"], e["solution"])[len(H):] for e in E)
    r = await ctx.lean.check(code + "\n" + "\n".join(f"#print axioms {n}" for n in names), ws, 500)
    assert not r.verdict.errors and not r.verdict.has_sorry
    texts = [json.loads(x).get("data", "") for x in r.stdout.splitlines() if x.startswith("{")]
    for n in names:      # strict: the axioms of each one
        out = next(x for x in texts if x.startswith(f"'{n}' "))
        m = re.search(r"\[([^\]]*)\]", out)
        assert set(re.findall(r"[\w.]+", m.group(1) if m else "")) <= leancheck.ALLOWED_AXIOMS, n


async def test_submit_with_real_lean(ws, tmp_path):
    ctx = make_ctx(tmp_path, ws=ws)
    e = E[0]
    for answer, good in (("exact ha.add hb", True), ("exact ha", False),
                         ("```lean4\ntheorem other : True := by\n  trivial\n```", False)):    # the statement is pinned
        r, _ = await X.check(ctx, e, answer, "t")
        assert r.verdict.ok is good, answer


@pytest.mark.parametrize("answer", ["sorry", "trivial\ntheorem x : True := trivial", "trivial namespace Z",
                                    "  #eval 1", "macro \"x\" : tactic => `(tactic| rfl)", "open Nat in trivial",
                                    "run_tac pure ()", "admit", "native_decide", "simp\nset_option debug.skipKernelTC true", "-- only"])
def test_hostile_answers(answer):
    with pytest.raises(X.ExerciseError):
        X.clean_answer(answer)


def _doc(**kw):
    return json.dumps({"format": X.FORMAT, "exercises": [{**E[0], **kw}]})


@pytest.mark.parametrize("kw", [
    {"id": "../x"}, {"id": "A b"}, {"id": 3}, {"level": "maternelle"}, {"level": []}, {"domain": "x"}, {"extra": 1},
    {"statement": {"en": "only English"}}, {"statement": "text"}, {"statement": {"fr": "x" * 5000}},
    {"statement": {"fr": "<script>alert(1)</script>"}}, {"statement": {"fr": "<img src=x onerror=y>"}},
    {"statement": {"fr": "![x](http://e.org/a.png)"}}, {"statement": {"fr": "[x](javascript:alert(1))"}},
    {"statement": {"fr": r"$\input{secret}$"}}, {"statement": {"fr": r"^^5cinput{x}"}},
    {"statement": {"fr": r"\write18{ls}"}}, {"title": {"fr": "a‮b"}}, {"hints": [{"fr": "x"}] * 9},
    {"lean": "theorem x : True := by trivial"}, {"lean": "import Lean\ntheorem x : True := by sorry"},
    {"lean": "#eval 1\ntheorem x : True := by sorry"}, {"lean": "axiom a : False\ntheorem x : True := by sorry"},
    {"lean": "theorem x : True := by sorry\ntheorem y : True := by sorry"},
    {"lean": "theorem x (h : by sorry) : True := by sorry"}, {"lean": 4}, {"solution": "sorry"},
    {"solution": "exact foo\n#eval IO.println 1"}, {"solution": "trivial\naxiom z : False"}])
def test_hostile_imports(kw):
    with pytest.raises(X.ExerciseError):
        X.parse_bank(_doc(**kw))


def test_bank_files(tmp_path):
    for bad in ("", "[]", "{", '{"format": "x", "exercises": [1]}', json.dumps({"format": X.FORMAT, "exercises": []}),
                "x" * (X.MAX_BYTES + 1), "[" * 100_000, None, json.dumps({"format": X.FORMAT, "exercises": [E[0], E[0]]})):
        with pytest.raises(X.ExerciseError):
            X.parse_bank(bad)
    b = X.Bank(tmp_path)
    assert b.add([E[0]], "import") == [E[0]["id"]] and not b.own          # already there
    ids = b.add(X.parse_bank(_doc(statement={"fr": "a < b et $x<y$"})), "import")
    assert ids != [E[0]["id"]] and X.Bank(tmp_path).get(ids[0])["origin"] == "import"
    assert [e["id"] for e in X.parse_bank(X.bank_json(list(b.own.values())))] == ids
    b.remove(ids[0])
    with pytest.raises(X.ExerciseError):
        b.remove(E[0]["id"])                                              # the seed stays


# ---------------------------------------------------------------- server
def brain(role, messages, b):
    text = messages[0]["content"]
    assert X.MARK in text
    if role == "explain":
        return "Pourquoi a = x + x ?"
    b.behaviour["n"] = b.behaviour.get("n", 0) + 1
    if "mauvaise" in text:
        return "NO_PROOF"
    if "refused by Lean" in text:
        return "```lean4\ntheorem ex_pair_somme (a b : ℕ) (ha : Even a) (hb : Even b) : Even (a + b) := by\n  exact ha.add hb\n```"
    return "```lean4\ntheorem ex_pair_somme (a b : ℕ) : False := by\n  exact no_such\n```"


async def test_learner_flow(tmp_path):
    ctx = make_ctx(tmp_path, brain=FakeBrain(brain))
    async with running(ctx) as (_s, L, R), session() as s:
        u = L + "/api/exercises"
        j = await (await s.get(u)).json()
        assert len(j["exercises"]) == len(E) and "solution" not in j["exercises"][0] and j["exercises"][0]["hints"] == 3
        assert (await s.get(R + "/api/exercises")).status in (401, 403)
        x = u + "/pair-somme"
        assert (await s.post(u + "/nope/hint", json={})).status == 404
        assert (await (await s.post(x + "/hint", json={})).json())["error"] == "attempt_first"
        assert (await (await s.post(x + "/solution", json={})).json())["error"] == "hints_first"
        h = await (await s.post(x + "/hint", json={"tried": "écrire a = 2k"})).json()
        assert len(h["hints"]) == 1 and h["progress"]["hints"] == 1
        r = await (await s.post(x + "/submit", json={"kind": "lean", "text": "exact no_such"})).json()
        assert r["ok"] is False and r["check"]["errors"] and r["progress"]["attempts"] == 1
        assert (await s.post(x + "/submit", json={"kind": "lean", "text": "sorry"})).status == 400
        for _ in range(2):
            h = await (await s.post(x + "/hint", json={})).json()
        assert len(h["hints"]) == 3 and (await s.post(x + "/hint", json={})).status == 409
        assert len((await (await s.post(x + "/hint", json={"again": True})).json())["hints"]) == 3
        # in words: a first formalisation refused by Lean, the second accepted; then the review
        r = await (await s.post(x + "/submit", json={"kind": "words", "text": "a et b sont des doubles, donc a + b aussi"})).json()
        assert r["ok"] and "ha.add hb" in r["lean"] and r["review"] and ctx.brain.behaviour["n"] == 2
        assert r["progress"]["solved"] and r["progress"]["how"] == "words"
        sol = await (await s.post(x + "/solution", json={})).json()
        assert sol["verified"] and "obtain" in sol["code"]
        # another exercise: an argument that proves nothing
        r = await (await s.post(u + "/carre-somme/submit", json={"kind": "words", "text": "une mauvaise idée ici"})).json()
        assert r["ok"] is False and r["lean"] == "" and r["review"]
    assert X.Bank(ctx.paths.config / "teaching").progress("host")["pair-somme"]["solved"]


async def test_teacher_tools(tmp_path):
    ctx = make_ctx(tmp_path, brain=FakeBrain(brain))
    async with running(ctx) as (_s, L, _R), session() as s:
        u = L + "/api/exercises"
        d = ctx.repo.new("", ctx.settings.workspace, "Un résultat")
        d.add_statement(leancheck.prepare_statement("theorem mien (n : ℕ) : n + 0 = n := by sorry"))
        await ctx.repo.save(d)
        bad = await s.post(u, json={"dossier": d.id, "level": "x", "domain": "autre", "statement": {"fr": "n"}})
        assert bad.status == 400
        e = (await (await s.post(u, json={"dossier": d.id, "level": "lycee", "domain": "autre",
                                          "statement": {"fr": "Montrer que $n+0=n$."}})).json())["exercise"]
        assert e["origin"] == "own" and e["lean"] == "theorem mien (n : ℕ) : n + 0 = n := by sorry" and not e["has_solution"]
        ctx.library.add_proof(leancheck.GOEDEL_HEADER + "theorem lib (n : ℕ) : n = n := by\n  rfl\n", "Réflexivité",
                              ctx.settings.workspace)
        j = await (await s.post(u, json={"library": "lib", "level": "licence", "domain": "autre",
                                         "statement": {"fr": "Montrer que $n=n$."}})).json()
        assert j["exercise"]["has_solution"]
        assert len(X.parse_bank(await (await s.get(u + "/export")).text())) == 2
        r = await s.post(u + "/import", json={"text": _doc(id="autre", statement={"fr": "Autre."})})
        assert r.status == 201
        r = await s.post(u + "/import", json={"text": _doc(id="y", lean="#eval 1")})
        assert r.status == 400 and (await r.json())["message"]["text"]
        r = await s.get(u + "/worksheet", params={"ids": ",".join(["pair-somme", e["id"]]), "lang": "mg", "format": "tex",
                                                 "solutions": "1", "lean": "1"})
        tex = await r.text()
        assert r.status == 200 and r"\begin{document}" in tex and "Porofoy" in tex and "obtain" in tex
        tex = await (await s.get(u + "/worksheet", params={"ids": ",".join(["pair-somme"]), "lang": "fr", "format": "tex"})).text()
        assert "Montrer" in tex and "obtain" not in tex and "omega" not in tex
        assert (await s.get(u + "/worksheet", params={"ids": ",".join(["nope"]), "format": "tex"})).status == 404
        assert (await s.get(u + "/worksheet", params={"ids": ",".join(["pair-somme"]), "format": "tex",
                                                     "title": r"\input{x}"})).status == 400
        r = await s.get(u + "/worksheet", params={"ids": ",".join(["pair-somme"]), "format": "pdf"})
        assert (await r.read())[:4] == b"%PDF" or r.headers["X-Madalean-Fallback"] == "html"
        assert (await s.delete(u + "/" + e["id"])).status == 200 and (await s.delete(u + "/pair-somme")).status == 404
