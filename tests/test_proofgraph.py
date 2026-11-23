"""The problem graph (S-AY, D57): persistence and migration from proof plans, statement-key dedupe, cycle refusal,
budgets that stop a runaway search, no-progress detection, abandoned branches not retried unless something changed,
conditional status propagation, explanations built only from recorded facts, sub-dossiers rolling up."""
import json
import re

from helpers import make_ctx, running, session, wait_idle
from madalean.brain.fake import FakeBrain, demo_responder
from madalean.research import graphsearch as GS
from madalean.research import proofgraph as G

PARITY = "theorem T (a b : ℕ) (ha : Even a) (hb : Even b) : Even (a + b) := by sorry"


def lemma(title, lean, status="open", **kw):
    return G.new_node("lemma", title, lean=lean, status=status, **kw)


# ---------------------------------------------------------------- pure model
def test_keys_dedupe_and_cycles():
    a = G.statement_key("theorem foo (n : ℕ) : n + 0 = n := by sorry")
    b = G.statement_key("lemma   bar (n : ℕ) :\n  n + 0 = n := by\n  simp -- other proof")
    assert a == b and a.startswith("lean:")
    assert G.statement_key("theorem foo (n : ℕ) : 0 + n = n := by sorry") != a
    g = G.new_graph("d1", "p1", "Goal", PARITY)
    x, created = G.add_node(g, lemma("x", "theorem x (n : ℕ) : n + 0 = n := by sorry"), parent=g["root"])
    y, created2 = G.add_node(g, lemma("y (same statement)", "theorem y (n : ℕ) : n + 0 = n := by sorry"),
                             parent=g["root"])
    assert created and not created2 and y["id"] == x["id"] and len(g["nodes"]) == 2
    z, _ = G.add_node(g, lemma("z", "theorem z : True := by sorry"), parent=x["id"])
    # z uses the goal → cycle (goal uses x uses z): refused and logged
    assert not G.add_edge(g, z["id"], "uses", g["root"])
    assert not G.add_edge(g, z["id"], "uses", z["id"])
    assert any(e["kind"] == "cycle_refused" for e in g["log"])
    assert G.reaches(g, g["root"], z["id"]) and not G.reaches(g, z["id"], g["root"])


def test_conditional_propagation():
    g = G.new_graph("d1", "p1", "Goal", PARITY)
    cited = G.cited_node({"title": "Théorème de X", "lean": "theorem cx (n : ℕ) : n ≤ n * n + 1 := by sorry",
                          "citation": {"title": "On X", "author": [{"family": "Euler", "given": "L."}],
                                       "issued": {"date-parts": [[1750]]}, "verified": True, "quote": "Every n..."}})
    c, _ = G.add_node(g, cited, parent=g["root"])
    G.set_status(g, g["root"], "proved", self_contained=False)       # proved with cx stated with sorry
    e = G.effective(g, g["root"])
    assert e["state"] == "conditional" and e["rests_on"] == [c["id"]]
    assert G.effective(g, c["id"])["state"] == "conditional"
    # Lean proves the cited lemma later: the goal becomes verified (composition of Lean-checked proofs)
    c["proof"] = "theorem cx (n : ℕ) : n ≤ n * n + 1 := by\n  nlinarith"
    G.set_status(g, c["id"], "proved", self_contained=True)
    e = G.effective(g, g["root"])
    assert e["state"] == "verified" and e["composed"]
    # an admitted hole deeper down makes everything above it conditional again
    h, _ = G.add_node(g, lemma("hole", "theorem h0 : 1 = 1 := by sorry"), parent=c["id"])
    h["admitted"] = True
    G.set_status(g, c["id"], "proved", self_contained=False)
    assert G.effective(g, g["root"])["state"] == "conditional"
    assert G.effective(g, g["root"])["rests_on"] == [h["id"]]


def test_viability_signals_and_memory():
    g = G.new_graph("d1", "p1", "Goal", PARITY)
    env = {"workspace": "w", "lean": "4.9", "mathlib": "m1"}
    g["env"] = env
    x, _ = G.add_node(g, lemma("x", "theorem x (n : ℕ) : n * 2 = n + n := by sorry"), parent=g["root"])
    G.set_status(g, x["id"], "abandoned", "omega failed twice", env=env)
    # the same statement proposed again: skipped while nothing changed …
    v = G.viability_signals(g, x["id"], env=env)
    assert v["skip"] and v["score"] == 0 and v["signals"][0]["code"] == "failed_before"
    assert "omega failed twice" in G.reason_text(v, "en")
    # … retried when Mathlib changed, or when a new lemma was proved
    v = G.viability_signals(g, x["id"], env={**env, "mathlib": "m2"})
    assert not v["skip"] and v["signals"][0]["code"] == "changed_since"
    y, _ = G.add_node(g, lemma("y", "theorem y : (2 : ℕ) = 1 + 1 := by sorry", status="proved"), parent=g["root"])
    v = G.viability_signals(g, x["id"], env=env)
    assert not v["skip"] and "new_lemma" in v["signals"][0]["params"]["what"]
    # known in another dossier of the project / in the library
    z, _ = G.add_node(g, lemma("z", "theorem z (k : ℕ) : k ≤ k := by sorry"), parent=g["root"])
    rows = [{"key": z["key"], "status": "proved", "title": "z ailleurs", "dossier_id": "d2"}]
    v = G.viability_signals(g, z["id"], project=rows)          # offered for reuse, never merged silently
    assert v["signals"][0]["code"] == "known_project" and not v["skip"] and z["status"] == "open"
    assert G.viability_signals(g, z["id"], library_keys={z["key"]: "Lib.z"})["signals"][0]["code"] == "in_library"
    # digest: bounded, deterministic, mentions what failed and what is proved
    dg = G.digest(g, rows, max_tokens=200)
    assert "omega failed twice" in dg and "(2 : ℕ) = 1 + 1" in dg and len(dg) <= 200 * G.CHARS_PER_TOKEN
    assert dg == G.digest(g, list(reversed(rows)), max_tokens=200)
    assert G.digest(G.new_graph("d", "p")) == ""
    lines = dg.split("\n")
    assert lines[1].startswith("Cible / Target:") and "Even (a + b)" in lines[1]
    order = [i for i, ln in enumerate(lines) if ln.startswith(("Connu", "À prouver"))]
    assert order == sorted(order) and lines[order[0]].startswith("Connu")


def test_identity_dag_and_provided_results():
    g = G.new_graph("d1", "p1", "Goal", PARITY)
    a, _ = G.add_node(g, lemma("A", "theorem la (n : ℕ) : n ≤ n * n + 1 := by sorry"), parent=g["root"])
    b, _ = G.add_node(g, lemma("B", "theorem lb (n : ℕ) : 1 ≤ n * n + 1 := by sorry"), parent=g["root"])
    # a shared sub-lemma: ONE node, used by both A and B (a DAG, not a tree)
    s1, c1 = G.add_node(g, lemma("S", "theorem s (n : ℕ) : 0 ≤ n * n := by sorry"), parent=a["id"])
    s2, c2 = G.add_node(g, lemma("S again", "theorem s_bis (n : ℕ) : 0 ≤ n * n := by sorry"), parent=b["id"])
    assert c1 and not c2 and s1["id"] == s2["id"] and set(G.users_of(g, s1["id"])) == {a["id"], b["id"]}
    # near-duplicate with a different hypothesis: a different statement, a different node
    s3, c3 = G.add_node(g, lemma("S si n>0", "theorem s3 (n : ℕ) (h : 0 < n) : 0 ≤ n * n := by sorry"),
                        parent=b["id"])
    assert c3 and s3["id"] != s1["id"]
    # proved once, both users see it
    G.set_status(g, s1["id"], "proved")
    G.set_status(g, a["id"], "proved", self_contained=False)
    assert G.effective(g, a["id"])["state"] == "verified"
    G.set_status(g, s3["id"], "proved")
    G.set_status(g, b["id"], "proved", self_contained=False)
    assert G.effective(g, b["id"])["state"] == "verified"
    # a provided result (attachment / literature) says « proved »: kept as cited, never promoted without Lean
    p = G.cited_node({"title": "Fourni", "lean": "theorem f (n : ℕ) : n = n := by sorry", "status": "proved",
                      "origin": "attachment", "citation": {"title": "pièce jointe", "verified": True}})
    assert p["status"] == "cited" and p["claimed"] == "proved" and p["source"]["kind"] == "attachment"
    pn, _ = G.add_node(g, p, parent=g["root"])
    assert G.effective(g, pn["id"])["state"] == "conditional"
    dg = G.digest(g)
    assert "attachment" in dg and "NOT proved in Lean" in dg


def test_explanation_uses_only_recorded_facts():
    g = G.new_graph("d1", "p1", "Somme de pairs", PARITY)
    a, _ = G.add_node(g, lemma("a est un double", "theorem la (a : ℕ) (ha : Even a) : ∃ k, a = 2 * k := by sorry",
                               why="réécrire a"), parent=g["root"])
    a["proof"] = "theorem la (a : ℕ) (ha : Even a) : ∃ k, a = 2 * k := by\n  obtain ⟨r, hr⟩ := ha\n  exact ⟨r, by omega⟩"
    G.set_status(g, a["id"], "proved")
    a["viability"] = {"score": 0.8, "signals": [{"code": "depth", "params": {"n": 1}}], "model": None}
    cited = G.cited_node({"title": "Lemme de Gauss", "lean": "theorem gauss (n : ℕ) : n ∣ n := by sorry",
                          "citation": {"title": "Disquisitiones", "author": [{"family": "Gauss", "given": "C. F."}],
                                       "issued": {"date-parts": [[1801]]}, "verified": True,
                                       "quote": "Si un nombre premier divise un produit"}})
    c, _ = G.add_node(g, cited, parent=g["root"])
    bad, _ = G.add_node(g, lemma("piste morte", "theorem pm (a : ℕ) : a = a + 1 := by sorry"))
    G.set_status(g, bad["id"], "refuted", "Lean proved the negation")
    g["nodes"][g["root"]]["proof"] = ("theorem T (a b : ℕ) (ha : Even a) (hb : Even b) : Even (a + b) := by\n"
                                      "  exact Even.add ha hb")
    G.set_status(g, g["root"], "proved", self_contained=False)
    e = G.explain(g, lang="fr")
    assert e["conditional"] and [r["title"] for r in e["rests_on"]] == ["Lemme de Gauss"]
    assert {t["name"] for t in e["tactics"]} == {"exact", "obtain"}
    assert [m["name"] for m in e["bibliography"]["mathlib"]] == ["Even.add"]
    assert e["bibliography"]["works"][0]["verified"] and "@" in e["bibliography"]["bibtex"]
    assert "Conditionnel" in e["text"] and "Lean proved the negation" in e["text"]
    # every backticked name and every title-like mention comes from the record
    allowed = G.record_text_tokens(e)
    for name in re.findall(r"`([^`\n]+)`", re.sub(r"```.*?```", "", e["text"], flags=re.S)):
        assert name in allowed, name
    for tac in G.TACTICS:
        if tac not in {t["name"] for t in e["tactics"]}:
            assert f"`{tac}`" not in e["text"], tac           # no tactic absent from the record
    assert "omega" not in {t["name"] for t in e["tactics"]}     # `by omega` inside a term is not a tactic line
    lx = G.explanation_latex(e)
    key = e["bibliography"]["works"][0]["key"]
    assert f"\\cite{{{key}}}" in lx["latex"] and key in lx["bibtex"]
    en = G.explain(g, lang="en")
    assert "Conditional" in en["text"] and "Lemme de Gauss" in en["text"]


def test_migration_from_a_proof_plan():
    g = G.new_graph("d1", "p1", "Goal", PARITY)
    plan = {"rev": 4, "root": "pn-r", "model": "fake", "nodes": {
        "pn-r": {"id": "pn-r", "parent": None, "children": ["pn-a", "pn-b"], "title": "T", "ui": "running",
                 "tracks": [{"id": "a", "idea": "doubles", "lemmas": ["pn-a", "pn-b"], "check": {"state": "ok"}},
                            {"id": "b", "idea": "divisibilité", "lemmas": ["pn-c"], "abandoned": True,
                             "refused": "equivalent", "check": {"state": "failed", "why": "loop"}}],
                 "active_track": "a", "lean": "", "statement_nl": "", "why": ""},
        "pn-a": {"id": "pn-a", "parent": "pn-r", "children": [], "title": "A", "ui": "proved", "obvious": True,
                 "obvious_proof": "theorem A : 1 = 1 := by\n  rfl\n", "lean": "theorem A : 1 = 1 := by sorry",
                 "statement_nl": "", "why": "w", "dossier_id": ""},
        "pn-b": {"id": "pn-b", "parent": "pn-r", "children": [], "title": "B", "ui": "hole",
                 "lean": "theorem B : 2 = 2 := by sorry", "statement_nl": "", "why": "", "dossier_id": "x"},
        "pn-c": {"id": "pn-c", "parent": "pn-r", "children": [], "title": "C", "ui": "abandoned",
                 "lean": "theorem C : 3 = 3 := by sorry", "statement_nl": "", "why": "", "dossier_id": ""}}}
    assert G.sync_from_plan(g, plan) > 0
    by = {n["plan_node"]: n for n in g["nodes"].values()}
    assert by["pn-a"]["status"] == "proved" and by["pn-a"]["tactics"] == ["rfl"]
    assert by["pn-b"]["admitted"] and G.effective(g, by["pn-b"]["id"])["state"] == "conditional"
    assert by["pn-c"]["status"] == "abandoned" and by["pn-c"]["reason"] == "equivalent"
    assert set(G.uses_of(g, g["root"])) == {by["pn-a"]["id"], by["pn-b"]["id"]}
    rev = g["rev"]
    assert G.sync_from_plan(g, plan) == 0 and g["rev"] == rev               # idempotent
    tr = g["nodes"][g["root"]]["tracks"]
    assert tr[0]["active"] and tr[1]["abandoned"]


def test_subdossier_rollup_pure():
    parent = G.new_graph("p", "p1", "Parent", PARITY)
    x, _ = G.add_node(parent, lemma("L", "theorem L : 1 = 1 := by sorry"), parent=parent["root"])
    child = G.new_graph("c", "p1", "L", "theorem L : 1 = 1 := by sorry")
    cit, _ = G.add_node(child, G.cited_node({"title": "Cité", "lean": "theorem q : 2 = 2 := by sorry"}),
                        parent=child["root"])
    G.set_status(child, child["root"], "proved", self_contained=False)
    assert G.rollup(parent, x["id"], child, False)
    assert G.effective(parent, x["id"])["state"] == "conditional" and x["rests_external"] == ["Cité"]
    assert G.rollup(parent, x["id"], child, True)
    assert G.effective(parent, x["id"])["state"] == "verified"


# ---------------------------------------------------------------- the engine with fake operations
class FakeOps(GS.Ops):
    """Always proposes more lemmas; never proves anything (a runaway brain)."""

    def __init__(self, prove=lambda g, n: False, error="unsolved goals"):
        self.k, self.prove, self.error, self.calls = 0, prove, error, {"expand": 0, "attempt": 0}
        self.env_ = {"workspace": "w", "lean": "4.9", "mathlib": "m1"}

    def env(self):
        return dict(self.env_)

    async def expand(self, g, nid, digest):
        self.calls["expand"] += 1
        self.k += 1
        return GS.Expansion(idea=f"idée {self.k}", model="fake", tokens=100, lemmas=[
            {"title": f"L{self.k}.{i}", "lean": f"theorem l{self.k}_{i} (n : ℕ) : n + {self.k * 10 + i} = "
                                                  f"{self.k * 10 + i} + n := by sorry"} for i in range(3)])

    async def attempt(self, g, nid, digest):
        self.calls["attempt"] += 1
        if self.prove(g, g["nodes"][nid]):
            return GS.Attempt(True, proof="theorem x : True := by\n  trivial", how="closers")
        return GS.Attempt(False, error=self.error, how="closers", tokens=50)


async def test_budgets_stop_a_runaway_search():
    g = G.new_graph("d1", "p1", "Goal", PARITY)
    ops = FakeOps()
    b = GS.Budgets(max_depth=2, max_nodes=10, max_attempts=15, branch_attempts=6, max_expansions=1, no_progress=50)
    s = GS.ReasonedSearch(g, ops, b)
    out = await s.run()
    assert out["reason"] in ("budget_attempts", "exhausted"), out
    assert s.spent.nodes <= 10 and s.spent.attempts <= 15
    assert max(n["depth"] for n in g["nodes"].values()) <= 2
    # every abandoned node says why
    assert all(n["reason"] for n in g["nodes"].values() if n["status"] == "abandoned")
    assert out["tried"] and all(t["reason"] for t in out["tried"])
    # a tiny wall-time budget stops at once
    g2 = G.new_graph("d2", "p1", "Goal", PARITY)
    out2 = await GS.ReasonedSearch(g2, FakeOps(), GS.Budgets(wall_s=0)).run()
    assert out2["reason"] == "budget_time" and out2["steps"] == 0
    # tokens
    g3 = G.new_graph("d3", "p1", "Goal", PARITY)
    out3 = await GS.ReasonedSearch(g3, FakeOps(), GS.Budgets(tokens=120, no_progress=50)).run()
    assert out3["reason"] == "budget_tokens"


async def test_no_progress_and_known_statements():
    # the same Lean error twice on the goal → no more direct attempts; expansion proposes only known statements
    class Known(FakeOps):
        async def expand(self, g, nid, digest):
            self.calls["expand"] += 1
            return GS.Expansion(idea="encore", model="fake", lemmas=[{"title": "le but", "lean": PARITY}])
    g = G.new_graph("d1", "p1", "Goal", PARITY)
    ops = Known()
    s = GS.ReasonedSearch(g, ops, GS.Budgets(max_expansions=2, no_progress=4))
    out = await s.run()
    assert ops.calls["attempt"] == 2                          # stuck after the repeated error
    assert out["reason"] in ("no_progress", "exhausted"), out
    assert any(e["kind"] == "cycle_refused" for e in g["log"])  # the goal cannot use itself
    assert any(e["kind"] == "no_progress" for e in g["log"])
    assert len(g["nodes"]) == 1


async def test_abandoned_branch_not_retried_unless_something_changed():
    g = G.new_graph("d1", "p1", "Goal", PARITY)
    ops = FakeOps()
    await GS.ReasonedSearch(g, ops, GS.Budgets(max_depth=1, max_expansions=1, no_progress=50)).run()
    dead = [n for n in g["nodes"].values() if n["status"] == "abandoned"]
    assert dead and g["nodes"][g["root"]]["status"] == "abandoned"
    calls = dict(ops.calls)
    out = await GS.ReasonedSearch(g, ops, GS.Budgets(max_depth=1, max_expansions=1, no_progress=50)).run()
    assert out["reason"] == "exhausted" and ops.calls == calls        # nothing redone blindly
    ops.env_["mathlib"] = "m2"                                        # a new Mathlib: worth another try
    out = await GS.ReasonedSearch(g, ops, GS.Budgets(max_depth=1, max_expansions=1, no_progress=50)).run()
    assert out["reopened"] and ops.calls["attempt"] > calls["attempt"]


async def test_search_solves_by_combining_lemmas_and_reports_conditional():
    # lemmas are proved directly; the goal only after its lemmas (combination)
    def prove(g, n):
        return n["kind"] == "lemma" or bool(G.uses_of(g, n["id"]))
    g = G.new_graph("d1", "p1", "Goal", PARITY)
    out = await GS.ReasonedSearch(g, FakeOps(prove=prove), GS.Budgets(no_progress=50)).run()
    assert out["reason"] == "solved" and out["root_state"] == "verified"
    # a cited lemma used by the goal: the search can only reach « conditional »
    g = G.new_graph("d2", "p1", "Goal", PARITY)
    c, _ = G.add_node(g, G.cited_node({"title": "Cité", "lean": "theorem q : 2 = 2 := by sorry"}), parent=g["root"])

    class Cond(FakeOps):
        async def attempt(self, g, nid, digest):
            self.calls["attempt"] += 1
            return GS.Attempt(True, proof="theorem T := by\n  exact q", how="combination", self_contained=False)
    out = await GS.ReasonedSearch(g, Cond(), GS.Budgets(no_progress=50)).run()
    assert out["reason"] == "conditional" and out["rests_on"] == [c["id"]]


# ---------------------------------------------------------------- the service through the API (fake Lean)
def graph_brain(role, messages, brain):
    first = next((m["content"] for m in messages if m.get("role") == "user"), "")
    if first.startswith(GS.MARK_EXPAND):
        brain.behaviour["expand"] = brain.behaviour.get("expand", 0) + 1
        k = brain.behaviour["expand"]
        return json.dumps({"idea": f"idée {k}", "combination": "", "lemmas": [
            {"name": f"s{k}_{i}", "title": f"étape {k}.{i}", "statement": "", "why": "aide",
             "lean": f"theorem s{k}_{i} (n : ℕ) : n + {k * 10 + i} = {k * 10 + i} + n := by sorry"} for i in range(2)]})
    if first.startswith(GS.MARK_VIABILITY):
        return json.dumps({"score": 0.7, "reason": "plausible"})
    return demo_responder(role, messages, brain)


async def _dossier(s, L, statement=PARITY, **extra):
    pid = (await (await s.post(L + "/api/projects", json={"title": "P"})).json())["project"]["id"]
    r = await s.post(L + "/api/dossiers", json={"statement": statement, "project_id": pid, "start": False,
                                                "title": "Parent", **extra})
    return (await r.json())["dossier"], pid


async def test_api_graph_views_actions_and_persistence(tmp_path):
    brain = FakeBrain(graph_brain)
    ctx = make_ctx(tmp_path, brain=brain)
    async with running(ctx) as (_s, L, _R), session() as s:
        d, pid = await _dossier(s, L, "theorem T (n : ℕ) : n = no_such_f n := by sorry")   # fake Lean refuses it
        base = L + f"/api/dossiers/{d['id']}/graph"
        r = await s.get(base)
        assert r.status == 200, await r.text()
        g = (await r.json())["graph"]
        assert g["nodes"][g["root"]]["state"] == "open" and g["budgets"]["usd"] <= 1.0
        # cited lemmas (S-AX interface): conditional, deduplicated
        item = {"title": "Lemme cité", "lean": "theorem c1 (n : ℕ) : n ≤ n := by sorry",
                "citation": {"title": "Un article", "author": [{"family": "Noether"}], "verified": True,
                             "issued": {"date-parts": [[1921]]}, "quote": "…"}}
        r = await s.post(base + "/cited", json={"items": [item, item]})
        j = await r.json()
        assert r.status == 200 and [a["created"] for a in j["added"]] == [True, False]
        cid = j["added"][0]["node"]
        assert j["graph"]["nodes"][cid]["state"] == "conditional"
        # the search runs within its budgets, then stops with a summary
        r = await s.post(base + "/search", json={"budgets": {"max_attempts": 6, "max_depth": 2}})
        assert r.status == 200, await r.text()
        summary = await ctx.research.graphs.wait(d["id"], 120)
        assert summary["reason"] in ("budget_attempts", "exhausted", "no_progress"), summary
        assert summary["spent"]["attempts"] <= 6
        g = (await (await s.get(base)).json())["graph"]
        assert g["runs"] and g["runs"][-1]["reason"] == summary["reason"]
        lem = next(n for n in g["nodes"].values() if n["kind"] == "lemma")
        # « Pourquoi cette piste ? » — the recorded reason
        w = await (await s.get(base + f"/nodes/{lem['id']}/why?lang=en")).json()
        assert w["viability"] and "viability" in w["reason_text"]
        # « Arrêter cette piste » / « Reprendre » (a proved lemma cannot be stopped)
        if lem["status"] == "proved":
            r = await s.post(base + f"/nodes/{lem['id']}/abandon", json={})
            assert r.status == 409 and (await r.json())["error"] == "already_proved"
        r = await s.post(base + f"/nodes/{cid}/abandon", json={"reason": "pas utile"})
        g = (await r.json())["graph"]
        assert g["nodes"][cid]["status"] == "abandoned" and "pas utile" in g["nodes"][cid]["reason"]
        r = await s.post(base + f"/nodes/{cid}/resume", json={})
        g = (await r.json())["graph"]
        assert g["nodes"][cid]["status"] == "open"
        # explanation + exports
        e = (await (await s.get(base + "/explain?lang=fr")).json())["explanation"]
        assert e["title"] == "Parent" and "Explication" in e["text"]
        r = await s.post(base + "/export", json={"format": "note"})
        assert r.status == 200 and (await r.json())["note"]["title"].startswith("Explication")
        r = await s.post(base + "/export", json={"format": "latex"})
        assert "\\subsection*" in (await r.json())["latex"]
        # the literature package is not installed here: said, nothing invented
        r = await s.post(base + "/literature", json={})
        assert (await r.json())["available"] is False
        await wait_idle(ctx, 30)
    # persistence: the graph is in the plan file of the dossier, reloaded by a new server
    ctx2 = make_ctx(tmp_path, brain=FakeBrain(graph_brain))
    async with running(ctx2) as (_s, L, _R), session() as s:
        g2 = (await (await s.get(L + f"/api/dossiers/{d['id']}/graph")).json())["graph"]
        assert g2["rev"] >= g["rev"] and cid in g2["nodes"] and g2["runs"]


async def test_subdossiers_open_rollup_bound_and_delete(tmp_path):
    ctx = make_ctx(tmp_path, brain=FakeBrain(graph_brain))
    async with running(ctx) as (_s, L, _R), session() as s:
        ctx.settings.plan_max_depth = 2
        d, pid = await _dossier(s, L)
        base = L + f"/api/dossiers/{d['id']}/graph"
        g = (await (await s.get(base)).json())["graph"]
        gs = ctx.research.graphs
        gg = gs.ensure(d["id"])
        n, _ = G.add_node(gg, lemma("Un lemme", "theorem lem1 (n : ℕ) : n + 0 = n := by sorry"), parent=gg["root"])
        gs.save(d["id"])
        r = await s.post(base + f"/nodes/{n['id']}/open", json={})
        j = await r.json()
        assert r.status == 200 and j["created"], j
        cid = j["dossier_id"]
        child = ctx.repo.get(cid)
        assert child.parent_id == d["id"] and child.kind == "lemma" and child.extra["graph"]["node"] == n["id"]
        assert (await (await s.post(base + f"/nodes/{n['id']}/open", json={})).json())["dossier_id"] == cid
        # lists: the child is listed with its parent id (the UI nests it under the parent)
        ds = (await (await s.get(L + f"/api/dossiers?project={pid}")).json())["dossiers"]
        assert next(x for x in ds if x["id"] == cid)["parent_id"] == d["id"]
        # recursion bound: a grandchild is allowed (depth 2), not a great-grandchild
        cg = gs.ensure(cid)
        n2, _ = G.add_node(cg, lemma("Sous-lemme", "theorem lem2 (n : ℕ) : 0 + n = n := by sorry"), parent=cg["root"])
        gs.save(cid)
        gc = (await (await s.post(L + f"/api/dossiers/{cid}/graph/nodes/{n2['id']}/open", json={})).json())
        gcid = gc["dossier_id"]
        ggc = gs.ensure(gcid)
        n3, _ = G.add_node(ggc, lemma("trop profond", "theorem lem3 : 1 = 1 := by sorry"), parent=ggc["root"])
        gs.save(gcid)
        r = await s.post(L + f"/api/dossiers/{gcid}/graph/nodes/{n3['id']}/open", json={})
        assert r.status == 409 and (await r.json())["error"] == "too_deep"
        # roll-up: the grandchild proved → the child's node proved; the child conditional → the parent conditional
        gcd = ctx.repo.get(gcid)
        gcd.add_proof(gcd.statement.replace("sorry", "simp"), meta={"strategy": "test"})
        gcd.status = "proved"
        await ctx.repo.save(gcd)
        gs.rollup(gcd)
        assert gs.get(cid)["nodes"][n2["id"]]["status"] == "proved"
        cgraph = gs.get(cid)
        c2, _ = G.add_node(cgraph, G.cited_node({"title": "Cité", "lean": "theorem q : 2 = 2 := by sorry"}),
                           parent=cgraph["root"])
        G.set_status(cgraph, cgraph["root"], "proved", self_contained=False)
        gs.save(cid)
        gs.rollup(ctx.repo.get(cid))
        pg = (await (await s.get(base)).json())["graph"]
        assert pg["nodes"][n["id"]]["state"] == "conditional"
        assert pg["nodes"][pg["root"]]["state"] == "open"
        # archive / delete the parent: the family follows, and comes back together
        r = await s.patch(L + f"/api/dossiers/{d['id']}", json={"archived": True})
        assert r.status == 200 and ctx.repo.get(cid).archived and ctx.repo.get(gcid).archived
        await s.patch(L + f"/api/dossiers/{d['id']}", json={"archived": False})
        r = await s.delete(L + f"/api/dossiers/{d['id']}")
        j = await r.json()
        assert set(j["children"]) == {cid, gcid}
        assert ctx.repo.get(cid) is None and ctx.repo.get(gcid) is None
        r = await s.post(L + f"/api/dossiers/{d['id']}/restore")
        assert r.status == 200 and ctx.repo.get(cid) is not None and ctx.repo.get(gcid) is not None
        await wait_idle(ctx, 30)


async def test_shared_subdossier_rolls_up_to_every_parent(tmp_path):
    ctx = make_ctx(tmp_path, brain=FakeBrain(graph_brain))
    async with running(ctx) as (_s, L, _R), session() as s:
        d, pid = await _dossier(s, L)
        gs = ctx.research.graphs
        g = gs.ensure(d["id"])
        a, _ = G.add_node(g, lemma("A", "theorem la (n : ℕ) : n ≤ n * n + 1 := by sorry"), parent=g["root"])
        b, _ = G.add_node(g, lemma("B", "theorem lb (n : ℕ) : 1 ≤ n * n + 1 := by sorry"), parent=g["root"])
        gs.save(d["id"])
        ja = await (await s.post(L + f"/api/dossiers/{d['id']}/graph/nodes/{a['id']}/open", json={})).json()
        jb = await (await s.post(L + f"/api/dossiers/{d['id']}/graph/nodes/{b['id']}/open", json={})).json()
        # both sub-dossiers need the same sub-lemma: it is created once, under the first parent
        S = "theorem s (n : ℕ) : 0 ≤ n * n := by sorry"
        out = []
        for j in (ja, jb):
            cg = gs.ensure(j["dossier_id"])
            n, _ = G.add_node(cg, lemma("S", S), parent=cg["root"])
            gs.save(j["dossier_id"])
            out.append((j["dossier_id"], n["id"], (await (await s.post(
                L + f"/api/dossiers/{j['dossier_id']}/graph/nodes/{n['id']}/open", json={})).json())))
        (da, na, ra), (db, nb, rb) = out
        assert ra["created"] and rb["shared"] and rb["dossier_id"] == ra["dossier_id"]
        sd = ctx.repo.get(ra["dossier_id"])
        assert sd.parent_id == da and sd.extra["graph_also"] == [{"graph_dossier": db, "node": nb}]
        # near-duplicate with another hypothesis: its own sub-dossier
        cgb = gs.get(db)
        n2, _ = G.add_node(cgb, lemma("S'", "theorem s2 (n : ℕ) (h : 0 < n) : 0 ≤ n * n := by sorry"),
                           parent=cgb["root"])
        gs.save(db)
        r2 = await (await s.post(L + f"/api/dossiers/{db}/graph/nodes/{n2['id']}/open", json={})).json()
        assert r2["created"] and r2["dossier_id"] != sd.id
        # proved once: both users updated
        sd.add_proof(sd.statement.replace("sorry", "positivity"), meta={"strategy": "test"})
        sd.status = "proved"
        await ctx.repo.save(sd)
        gs.rollup(sd)
        assert gs.get(da)["nodes"][na]["status"] == "proved" and gs.get(db)["nodes"][nb]["status"] == "proved"
        await wait_idle(ctx, 30)
