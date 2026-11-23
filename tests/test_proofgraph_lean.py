"""The problem graph with the REAL Lean (S-AY, D57 / D57b): a small graph searched end to end (a false lemma refuted
by Lean, true lemmas proved, the goal proved by combining them, stored as the dossier's strict proof), and the
lessons store measured on a repeated mistake (the second time, the lesson fixes it without a second model call)."""
import json
import re

from helpers import make_ctx, running, session, wait_idle
from madalean.brain.fake import FakeBrain, demo_responder
from madalean.research import graphsearch as GS
from madalean.research import lessons as LS

GOAL = "theorem T (a b : ℕ) (h : a ≤ b) : a * a ≤ b * b := by sorry"


def _real(ctx):
    ctx.settings.statement_check = False
    ctx.settings.mathlib_first = False
    ctx.settings.certificates = False
    ctx.settings.graph_viability_model = True


def _first(messages):
    return next((m["content"] for m in messages if m.get("role") == "user"), "")


def search_brain(role, messages, brain):
    first = _first(messages)
    if first.startswith(GS.MARK_EXPAND):
        return json.dumps({"idea": "passer par a * b", "combination": "exact le_trans (m1 a b h) (m2 a b h)",
                           "lemmas": [
                               {"name": "m1", "title": "a·a ≤ a·b", "statement": "", "why": "premier pas",
                                "lean": "theorem m1 (a b : ℕ) (h : a ≤ b) : a * a ≤ a * b := by sorry"},
                               {"name": "m2", "title": "a·b ≤ b·b", "statement": "", "why": "second pas",
                                "lean": "theorem m2 (a b : ℕ) (h : a ≤ b) : a * b ≤ b * b := by sorry"},
                               {"name": "bad", "title": "faux", "statement": "", "why": "piste fausse",
                                "lean": "theorem bad (n : ℕ) : n + 1 = n := by sorry"}]})
    if first.startswith(GS.MARK_VIABILITY):
        return json.dumps({"score": 0.6, "reason": "plausible"})
    if "Complete the following Lean 4 code" in first:
        brain.behaviour.setdefault("proofs", []).append(first)
        if re.search(r"theorem m[12]\b", first.split("```")[-2] if "```" in first else first):
            return "```lean4\ntheorem m1 (a b : ℕ) (h : a ≤ b) : a * a ≤ a * b := by\n  nlinarith [h]\n```"
        return "```lean4\ntheorem T (a b : ℕ) (h : a ≤ b) : a * a ≤ b * b := by\n  omega\n```"
    return demo_responder(role, messages, brain)


async def test_real_lean_small_graph_end_to_end(tmp_path, ws):
    brain = FakeBrain(search_brain)
    ctx = make_ctx(tmp_path, ws=ws, brain=brain)
    async with running(ctx) as (_s, L, _R), session() as s:
        _real(ctx)
        pid = (await (await s.post(L + "/api/projects", json={"title": "P", "workspace": ws.key})).json())["project"]["id"]
        d = (await (await s.post(L + "/api/dossiers", json={"statement": GOAL, "project_id": pid, "start": False,
                                                            "title": "Carrés", "workspace": ws.key})).json())["dossier"]
        base = L + f"/api/dossiers/{d['id']}/graph"
        r = await s.post(base + "/search", json={"budgets": {"max_attempts": 12}})
        assert r.status == 200, await r.text()
        summary = await ctx.research.graphs.wait(d["id"], 900)
        g = (await (await s.get(base)).json())["graph"]
        by = {n["title"]: n for n in g["nodes"].values()}
        assert summary["reason"] == "solved", (summary, [(n["title"], n["status"], n["reason"]) for n in by.values()], g["log"])
        assert by["faux"]["status"] == "refuted" and "negation" in by["faux"]["reason"]
        assert by["a·a ≤ a·b"]["status"] == "proved" and by["a·b ≤ b·b"]["status"] == "proved"
        root = g["nodes"][g["root"]]
        assert root["state"] == "verified" and root["how"] == "combination"
        # the dossier now has a strict, verified proof (no sorryAx)
        dd = ctx.repo.get(d["id"])
        assert dd.proof_is_current and "sorryAx" not in (dd.proofs[dd.cur_proof].meta.get("axioms") or [])
        # the account of the proof: path, lemmas, tactics — only recorded ones
        e = (await (await s.get(base + "/explain?lang=en")).json())["explanation"]
        assert {"nlinarith", "exact"} <= {t["name"] for t in e["tactics"]}
        assert "le_trans" not in [m["name"] for m in e["bibliography"]["mathlib"]]   # not a qualified name
        assert any(f["title"] == "faux" for f in e["failures"])
        await wait_idle(ctx, 60)


def mistake_brain(role, messages, brain):
    first = _first(messages)
    if first.startswith(GS.MARK_VIABILITY) or first.startswith(GS.MARK_EXPAND):
        return "{}"
    if "Complete the following Lean 4 code" in first:
        m = re.search(r"theorem (\w+)", first.split("```")[1] if "```" in first else first)
        name = m.group(1) if m else "X"
        seen = brain.behaviour.setdefault("seen", {})
        seen[name] = seen.get(name, 0) + 1
        wrong = seen[name] == 1                     # the same known mistake, the first time on each statement
        lemma = "Nat.zero_le_wrong" if wrong else "Nat.zero_le"
        return f"```lean4\ntheorem {name} (x y : ℕ) (h : x ≤ y) : x * x ≤ x * y := by\n  nlinarith [{lemma} x, h]\n```"
    return demo_responder(role, messages, brain)


async def test_lessons_prevent_the_same_mistake_twice(tmp_path, ws):
    brain = FakeBrain(mistake_brain)
    ctx = make_ctx(tmp_path, ws=ws, brain=brain)
    async with running(ctx) as (_s, L, _R), session() as s:
        _real(ctx)
        ctx.settings.graph_viability_model = False
        pid = (await (await s.post(L + "/api/projects", json={"title": "P", "workspace": ws.key})).json())["project"]["id"]
        calls = []
        for name in ("A", "B"):
            st = f"theorem {name} (x y : ℕ) (h : x ≤ y) : x * x ≤ x * y := by sorry"
            d = (await (await s.post(L + "/api/dossiers", json={"statement": st, "project_id": pid, "start": False,
                                                                "title": name, "workspace": ws.key})).json())["dossier"]
            before = sum(brain.behaviour.get("seen", {}).values())
            r = await s.post(L + f"/api/dossiers/{d['id']}/graph/search", json={"budgets": {"max_attempts": 6}})
            assert r.status == 200, await r.text()
            summary = await ctx.research.graphs.wait(d["id"], 900)
            assert summary["reason"] == "solved", summary
            calls.append(sum(brain.behaviour.get("seen", {}).values()) - before)
            g = ctx.research.graphs.get(d["id"])
            if name == "B":
                assert g["nodes"][g["root"]]["how"] == "model+lesson"
        # before: two model proofs (the mistake, then the fix); after: one (the lesson repaired the mistake)
        assert calls == [2, 1], calls
        lessons = (await (await s.get(L + "/api/lessons")).json())["lessons"]
        rn = next(x for x in lessons if x["kind"] == "rename")
        assert rn["old"] == "Nat.zero_le_wrong" and rn["new"] == "Nat.zero_le" and rn["ok"] >= 2
        assert rn["evidence"] and rn["evidence"][0]["mathlib"] is not None
        # export / delete / import round trip
        exp = await (await s.get(L + "/api/lessons/export")).json()
        assert (await (await s.delete(L + f"/api/lessons/{rn['id']}")).json())["deleted"]
        assert (await (await s.post(L + "/api/lessons/import", json=exp)).json())["imported"] >= 1
        await wait_idle(ctx, 60)


def test_lessons_store_hygiene(tmp_path):
    st = LS.Lessons(tmp_path / "l.json")
    env = {"workspace": "w", "lean": "4.9", "mathlib": "m1"}
    st.learn_fix("exact Foo.barr x", "error: unknown identifier 'Foo.barr'", "theorem t := by\n  exact Foo.bar x",
                 "theorem t (x : ℕ) : x = x := by sorry", env, "d1")
    assert st.renames(env) and not st.renames({**env, "mathlib": "m2"})       # per Mathlib version
    code, used = st.apply_renames("exact Foo.barr x\nexact Foo.barr_ok", env)
    assert code == "exact Foo.bar x\nexact Foo.barr_ok" and used
    h1 = st.hint("theorem u (y : ℕ) : y = y := by sorry", env)
    assert "Foo.bar" in h1 and h1 == st.hint("theorem u (y : ℕ) : y = y := by sorry", env)
    lid = used[0]
    for _ in range(4):
        st.feedback(lid, False)                                               # stopped helping: dropped
    assert lid not in LS.Lessons(tmp_path / "l.json").items
    try:
        st.import_({"kind": "other"})
        raise AssertionError("accepted a foreign file")
    except ValueError:
        pass
    n = st.import_({"kind": "madalean-lessons", "lessons": [
        {"kind": "rename", "old": "a b; evil", "new": "x"}, {"kind": "rename", "old": "Ok.a", "new": "Ok.b",
                                                             "mathlib": "m1"}]})
    assert n == 1
    st.learn_strategy("theorem s (n : ℕ) : n ≤ n * n + 1 := by sorry", "graph", ["nlinarith"], env, "d2")
    assert "nlinarith" in st.hint("theorem s2 (k : ℕ) : k ≤ k * k + 1 := by sorry", env)
