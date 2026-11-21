"""Proof decomposition as a mind map (S-L): bounded analysis (depth, nodes, alternatives), the loop guard (a lemma
equal/equivalent to its parent is refused), the Lean gate of the combination, the automatic run (obvious lemmas,
combination with the real lemma proofs under the strict verdict), the failure options (another track, a hole →
CONDITIONAL, never verified)."""
import asyncio
import json

from helpers import make_ctx, running, session, wait_idle
from madalean.brain.fake import FakeBrain, demo_responder
from madalean.research import proofplan as pp

PARITY = "theorem T (a b : ℕ) (ha : Even a) (hb : Even b) : Even (a + b) := by sorry"


def _first(messages):
    return next((m["content"] for m in messages if m.get("role") == "user"), "")


def forever(role, messages, brain):
    """A brain that always wants to split further: every analysis proposes 3 tracks of `lemmas` fresh lemmas."""
    first = _first(messages)
    if first.startswith(pp.MARK):
        brain.behaviour["n"] = brain.behaviour.get("n", 0) + 1
        k, n = brain.behaviour["n"], brain.behaviour.get("lemmas", 6)
        tracks = [{"idea": f"idée {k}.{j}", "combination": "theorem X : True := by\n  trivial",
                   "lemmas": [{"name": f"s{k}_{j}_{i}", "title": f"étape {i}", "statement": f"Étape {i}.",
                               "why": "aide", "uses": [],
                               "lean": f"theorem s{k}_{j}_{i} (n : ℕ) : n + {100 * k + 10 * j + i} = "
                                       f"{100 * k + 10 * j + i} + n := by sorry"} for i in range(n)]}
                  for j in range(3)]
        return json.dumps({"tracks": tracks})
    return demo_responder(role, messages, brain)


async def _setup(s, L, statement=PARITY, ws_key=None):
    body = {"title": "P"} if ws_key is None else {"title": "P", "workspace": ws_key}
    pid = (await (await s.post(L + "/api/projects", json=body)).json())["project"]["id"]
    r = await s.post(L + "/api/dossiers", json={"statement": statement, "project_id": pid, "start": False,
                                                "title": "Parent"})
    d = (await r.json())["dossier"]
    return d, L + f"/api/dossiers/{d['id']}/plan"


async def _split_until_stopped(s, base, max_rounds=20):
    nid, errors, depths = None, [], []
    for _ in range(max_rounds):
        r = await s.post(base + "/analyse", json={"node": nid} if nid else {})
        j = await r.json()
        if r.status != 200:
            errors.append((r.status, j.get("error")))
            break
        p = j["plan"]
        target = nid or p["root"]
        nid = p["nodes"][target]["children"][0]
        depths.append(p["nodes"][nid]["depth"])
    return errors, depths


async def test_infinite_splitting_stops_at_the_node_and_depth_limits(tmp_path):
    for lemmas, limit_error in ((6, "too_many_nodes"), (2, "too_deep")):
        brain = FakeBrain(forever)
        brain.behaviour["lemmas"] = lemmas
        ctx = make_ctx(tmp_path / str(lemmas), brain=brain)
        async with running(ctx) as (_s, L, _R), session() as s:
            assert ctx.research.planner.max_depth == 3
            _d, base = await _setup(s, L)
            errors, depths = await _split_until_stopped(s, base)
            p = (await (await s.get(base)).json())["plan"]
            assert errors and errors[0] == (409, "too_deep"), errors
            assert len(p["nodes"]) <= pp.MAX_NODES and max(n["depth"] for n in p["nodes"].values()) <= 3
            assert all(len(t["lemmas"]) <= pp.MAX_LEMMAS for n in p["nodes"].values() for t in n["tracks"])
            assert all(len(n["tracks"]) <= 1 + pp.MAX_ALTS for n in p["nodes"].values())
            # bounded model calls: at most GATE_TRIES per analysis, and no call for the refused one
            analyses = len(depths)
            assert brain.behaviour["n"] <= pp.GATE_TRIES * analyses
            if limit_error == "too_many_nodes":
                assert len(p["nodes"]) == pp.MAX_NODES          # the budget truncated the last split
                other = p["nodes"][p["root"]]["children"][1]
                r = await s.post(base + "/analyse", json={"node": other})
                assert r.status == 409 and (await r.json())["error"] == "too_many_nodes"
                r = await s.post(base + "/nodes", json={"base_rev": p["rev"], "parent": other, "title": "x"})
                assert r.status == 409
            if limit_error == "too_deep":
                assert depths[-1] == 3 and p["summary"]["depth"] == 3
            # the root summary is computed from statuses only
            assert p["summary"]["next"] == "validate" and p["summary"]["nodes"] == len(p["nodes"])


def loop_brain(role, messages, brain):
    first = _first(messages)
    if first.startswith(pp.MARK):
        same = {"name": "again", "title": "le théorème lui-même", "statement": "", "why": "", "uses": [],
                "lean": "theorem again (a b : ℕ) (ha : Even a) (hb : Even b) : Even (a + b) := by sorry"}
        other = {"name": "fine", "title": "autre", "statement": "", "why": "", "uses": [],
                 "lean": "theorem fine (n : ℕ) : n + 0 = n := by sorry"}
        tracks = [{"idea": "boucle", "lemmas": [same, other], "combination": "theorem T := by\n  exact again a b ha hb"}]
        if not brain.behaviour.get("all_loops"):
            tracks.append({"idea": "vraie piste", "lemmas": [other, {**other, "name": "fine2"}],
                           "combination": "theorem T := by\n  exact Even.add ha hb"})
        return json.dumps({"tracks": tracks})
    return demo_responder(role, messages, brain)


async def test_a_child_equal_to_its_parent_is_refused(tmp_path):
    brain = FakeBrain(loop_brain)
    ctx = make_ctx(tmp_path, brain=brain)
    async with running(ctx) as (_s, L, _R), session() as s:
        _d, base = await _setup(s, L)
        r = await s.post(base + "/analyse", json={})
        p = (await r.json())["plan"]
        root = p["nodes"][p["root"]]
        (good,) = root["tracks"]                         # the looping track is never installed…
        assert root["refused_tracks"][0]["reason"] == "same_text" and root["refused_tracks"][0]["lemmas"]
        assert root["active_track"] == good["id"] and root["children"] == good["lemmas"]
        assert len(p["nodes"]) == 3                      # …and costs no node
        # no other track to switch to (the refused one never comes back)
        r = await s.post(base + f"/nodes/{p['root']}/track", json={"base_rev": p["rev"]})
        assert r.status == 409 and (await r.json())["error"] == "no_alternative"
        # once the plan runs, a lemma dossier is split inside THIS plan only (one tree, one set of limits)
        r = await s.post(base + "/prove", json={"base_rev": p["rev"]})
        p = (await r.json())["plan"]
        child = p["nodes"][good["lemmas"][0]]["dossier_id"]
        assert child
        r = await s.post(L + f"/api/dossiers/{child}/plan/analyse", json={})
        assert r.status == 409 and (await r.json())["error"] == "in_plan"
        await wait_idle(ctx, 60)
        # every track loops → nothing is installed
        brain.behaviour["all_loops"] = True
        r = await s.post(base + "/analyse", json={"force": True})
        assert r.status == 422 and (await r.json())["error"] == "loop_refused"


def _parity_brain(failing: set[str]):
    def responder(role, messages, brain):
        first = _first(messages)
        if first.startswith(pp.MARK):
            return pp.demo_answer(first)
        if first.startswith("Complete the following Lean 4 code") and any(f in first for f in failing):
            sig = first.split("```lean4\n", 1)[1].split("```", 1)[0]
            sig = sig[sig.rindex("theorem"):].replace(":= by sorry", ":= by")
            return f"```lean4\n{sig}\n  exact no_such_lemma\n```"
        return demo_responder(role, messages, brain)
    return responder


async def _wait_plan(s, base, pred, timeout=240):
    for _ in range(int(timeout / 0.25)):
        p = (await (await s.get(base)).json())["plan"]
        if pred(p):
            return p
        await asyncio.sleep(0.25)
    raise AssertionError(json.dumps({k: (v["title"], v["ui"], v["state"]) for k, v in p["nodes"].items()},
                                    ensure_ascii=False))


def _real(ctx):
    ctx.settings.prove_attempts = 1
    ctx.settings.mathlib_first = False
    ctx.settings.statement_check = False


async def test_gate_obvious_lemma_failure_switch_track_then_proved(tmp_path, ws):
    """Real Lean: a + b even. The gate checks both combinations; T_a1 is obvious (closers), T_a2 fails in the
    pipeline → « autre piste » → the divisibility track (both lemmas obvious) → combination with the real lemma
    proofs under the strict verdict → the theorem is proved."""
    ctx = make_ctx(tmp_path, ws=ws, brain=FakeBrain(_parity_brain({"(k l : ℕ)"})))
    _real(ctx)
    async with running(ctx) as (_s, L, _R), session() as s:
        _real(ctx)
        d, base = await _setup(s, L, ws_key=ws.key)
        r = await s.post(base + "/analyse", json={})
        assert r.status == 200, await r.text()
        p = (await r.json())["plan"]
        root = p["nodes"][p["root"]]
        ta, tb = root["tracks"]
        assert ta["check"]["state"] == "ok" and tb["check"]["state"] == "ok", (ta["check"], tb["check"])
        a1, a2 = ta["lemmas"]
        assert p["nodes"][a1]["obvious"] and p["nodes"][a1]["ui"] == "proved"       # closed by a cheap closer
        assert not p["nodes"][a2]["obvious"] and p["nodes"][a2]["ui"] == "to_validate"
        assert all(p["nodes"][x]["obvious"] for x in tb["lemmas"]) and p["nodes"][tb["lemmas"][0]]["ui"] == "alternative"
        # obvious nodes are never split
        r = await s.post(base + "/analyse", json={"node": a1})
        assert r.status == 409 and (await r.json())["error"] == "obvious"
        # the user validates the plan, then Madalean proves it
        r = await s.post(base + "/prove", json={"base_rev": p["rev"], "mode": "local"})
        assert r.status == 200, await r.text()
        p = await _wait_plan(s, base, lambda p: p["nodes"][a2]["ui"] == "failed")
        assert p["nodes"][a1]["ui"] == "proved" and p["nodes"][a1]["proved"]
        assert p["summary"]["next"] == "fix" and p["summary"]["attention"] == [a2]
        assert not ctx.repo.get(d["id"]).proof_is_current
        # (a) another track
        r = await s.post(base + f"/nodes/{p['root']}/track", json={"base_rev": p["rev"]})
        assert r.status == 200, await r.text()
        p = await _wait_plan(s, base, lambda p: p["verdict"]["state"] == "proved")
        assert p["verdict"]["verified"] and p["summary"]["next"] == "done"
        assert all(p["nodes"][x]["ui"] == "abandoned" for x in ta["lemmas"])
        parent = ctx.repo.get(d["id"])
        meta = parent.proofs[parent.cur_proof].meta
        assert parent.proof_is_current and meta["strategy"] == "plan" and "sorryAx" not in (meta["axioms"] or [])
        await wait_idle(ctx, 60)


async def test_failed_lemma_left_as_a_hole_makes_the_parent_conditional(tmp_path, ws):
    ctx = make_ctx(tmp_path, ws=ws, brain=FakeBrain(_parity_brain({"(k l : ℕ)"})))
    _real(ctx)
    async with running(ctx) as (_s, L, _R), session() as s:
        _real(ctx)
        d, base = await _setup(s, L, ws_key=ws.key)
        p = (await (await s.post(base + "/analyse", json={})).json())["plan"]
        a1, a2 = p["nodes"][p["root"]]["children"]
        r = await s.post(base + "/prove", json={"base_rev": p["rev"], "mode": "local"})
        p = await _wait_plan(s, base, lambda p: p["nodes"][a2]["ui"] == "failed")
        # (c) leave it as a hole
        r = await s.post(base + f"/nodes/{a2}/admit", json={"base_rev": p["rev"]})
        assert r.status == 200, await r.text()
        p = await _wait_plan(s, base, lambda p: p["verdict"]["state"] == "proved_modulo")
        assert p["verdict"]["verified"] is False and p["verdict"]["admitted"] == 1
        assert p["nodes"][a2]["ui"] == "hole" and p["nodes"][p["root"]]["ui"] == "conditional"
        assert p["summary"]["holes"] == 1 and p["summary"]["next"] == "conditional"
        parent = ctx.repo.get(d["id"])
        assert not parent.proof_is_current and parent.proofs == []
        cond = parent.extra["conditional_proof"]
        assert "sorryAx" in cond["axioms"] and cond["strict_ok"] is False and cond["holes"] == 1
        summ = next(x for x in (await (await s.get(L + "/api/dossiers")).json())["dossiers"] if x["id"] == d["id"])
        assert summ["proved"] is False
        await wait_idle(ctx, 60)


def test_pure_helpers():
    ctx, name, sig = pp.split_decl("import Mathlib\nopen Real\n\ndef f (x : ℕ) : ℕ := x\n\n"
                                   "theorem foo (a : ℕ) (h : 0 < a) : f a = a := by sorry")
    assert ctx == "def f (x : ℕ) : ℕ := x" and name == "foo" and sig == "(a : ℕ) (h : 0 < a) : f a = a"
    assert pp.split_decl("theorem bad := by sorry") is None
    assert pp.rename_refs("exact foo' a (foo a) foo_bar", {"foo": "X"}) == "exact foo' a (X a) foo_bar"
    assert pp.body_of("theorem T (a : ℕ) : a = a := by\n  rfl", "T").strip() == "rfl"
    code, spans = pp.gate_file("", "T", "(a : ℕ) : a = a", [{"lemmas": [{"name": "T_a1", "sig": ": True"}],
                                                             "combination": "rfl"}], equiv=True)
    lines = code.split("\n")
    for kind, _ti, _li, a, b in spans:
        assert lines[a - 1].startswith(("theorem", "set_option")), (kind, lines[a - 1])
        assert lines[b - 1].strip()
    t = pp.parse_tracks(json.dumps({"claims": [{"title": "x", "lean": "theorem x : True := by sorry"}]}))
    assert len(t) == 1 and t[0]["combination"] == ""


def bad_lean_brain(role, messages, brain):
    first = _first(messages)
    if first.startswith(pp.MARK):
        brain.behaviour["n"] = brain.behaviour.get("n", 0) + 1
        lm = [{"name": f"b{i}", "title": "x", "statement": "", "why": "", "uses": [],
               "lean": f"theorem b{i} (n : ℕ) : n = no_such_{i} n := by sorry"} for i in range(2)]
        return json.dumps({"tracks": [{"idea": "invalide", "lemmas": lm, "combination": "theorem T := by\n  simp"}]})
    return demo_responder(role, messages, brain)


async def test_a_split_whose_statements_lean_rejects_is_not_installed(tmp_path):
    brain = FakeBrain(bad_lean_brain)
    ctx = make_ctx(tmp_path, brain=brain)
    async with running(ctx) as (_s, L, _R), session() as s:
        _d, base = await _setup(s, L)
        r = await s.post(base + "/analyse", json={})
        j = await r.json()
        assert r.status == 422 and j["error"] == "lean_rejected" and "b0" not in str(j.get("plan", ""))
        assert brain.behaviour["n"] == pp.GATE_TRIES                     # regenerated once with Lean's errors
        assert "rejected by Lean" in ctx.brain.requests[-1]["messages"][0]["content"] or \
            "rejected by Lean" in str(ctx.brain.requests[-1])
        assert (await s.get(base)).status == 404                         # nothing installed
