"""Guided proof design (S-G): plan drafting and editing (versions, optimistic concurrency), submission into
sub-dossiers, scheduling under a concurrency limit, subtree cancellation, and the « proved modulo admitted lemmas »
invariant with real Lean: never verified until the admitted lemma has a real sorry-free proof."""
import asyncio
import re

from helpers import make_ctx, running, session, wait_idle
from madalean.brain.fake import FakeBrain, demo_responder
from madalean.research import proofplan as pp


def responder(role, messages, brain):
    first = next((m["content"] for m in messages if m.get("role") == "user"), "")
    if first.startswith(pp.MARK):
        return pp.demo_answer(first)
    if brain.behaviour.get("lemma_fails") and first.startswith("Complete the following Lean 4 code") \
            and ": Even (a + b) := by sorry" in first:
        sig = re.search(r"```lean4\n(.*?)```", first, re.S).group(1)
        sig = sig[sig.rindex("theorem"):].replace(":= by sorry", ":= by")
        return f"```lean4\n{sig}\n  exact no_such_lemma ha hb\n```"
    return demo_responder(role, messages, brain)


async def _dossier(s, L, pid, statement):
    r = await s.post(L + "/api/dossiers", json={"statement": statement, "project_id": pid, "start": False,
                                                "title": "Parent"})
    return (await r.json())["dossier"]


async def test_plan_draft_edit_versions_conflicts(tmp_path):
    ctx = make_ctx(tmp_path, brain=FakeBrain(responder))
    async with running(ctx) as (_s, L, _R), session() as s:
        pid = (await (await s.post(L + "/api/projects", json={"title": "P"})).json())["project"]["id"]
        d = await _dossier(s, L, pid, "theorem t (a b : ℕ) (ha : Even a) (hb : Even b) : Even (a + b) := by sorry")
        base = L + f"/api/dossiers/{d['id']}/plan"
        assert (await s.get(base)).status == 404
        r = await s.post(base + "/draft", json={"sketch": "Écrire a = 2k, b = 2l (preuve du papier)."})
        p = (await r.json())["plan"]
        assert r.status == 201 and p["rev"] == 1 and p["source"] == "sketch"
        root = p["nodes"][p["root"]]
        # the analysis (S-L): a main track of 2 lemmas + 1 alternative track, both gated by (fake) Lean
        assert len(root["children"]) == 2 and root["dossier_id"] == d["id"] and len(root["tracks"]) == 2
        assert root["tracks"][0]["check"]["state"] == "ok" and root["active_track"] == root["tracks"][0]["id"]
        assert "preuve du papier" in ctx.brain.requests[-1]["messages"][0]["content"] or \
            "preuve du papier" in str(ctx.brain.requests[-1])
        k1, k2 = root["children"]
        alt = root["tracks"][1]["lemmas"][0]
        assert p["nodes"][alt]["ui"] == "alternative" and p["nodes"][k1]["ui"] == "to_validate"
        # manual edit (new version), stale edit refused
        r = await s.patch(base + f"/nodes/{k1}", json={"base_rev": 1, "why": "Plus clair.", "title": "a = k + k"})
        p = (await r.json())["plan"]
        assert p["rev"] == 2 and p["nodes"][k1]["edited"] and p["nodes"][k1]["title"] == "a = k + k"
        r = await s.patch(base + f"/nodes/{k2}", json={"base_rev": 1, "why": "x"})
        assert r.status == 409 and (await r.json())["current"]["rev"] == 2
        assert (await s.patch(base + f"/nodes/{k2}", json={"base_rev": 2, "status": "x"})).status == 400
        # add / move / cycle / delete
        r = await s.post(base + "/nodes", json={"base_rev": 2, "parent": k2, "title": "sous-lemme",
                                                "lean": "theorem sub (k : ℕ) : k + k = 2 * k := by sorry"})
        p = (await r.json())["plan"]
        sub = p["nodes"][k2]["children"][0]
        assert (await s.post(base + f"/nodes/{k2}/move", json={"base_rev": 3, "parent": sub})).status == 400
        r = await s.post(base + f"/nodes/{sub}/move", json={"base_rev": 3, "parent": p["root"], "index": 0})
        p = (await r.json())["plan"]
        assert p["nodes"][p["root"]]["children"][0] == sub and p["rev"] == 4
        assert p["nodes"][p["root"]]["tracks"][0]["lemmas"] == p["nodes"][p["root"]]["children"]
        assert p["nodes"][p["root"]]["tracks"][0]["check"]["state"] == "unchecked"     # edited: « à vérifier »
        r = await s.delete(base + f"/nodes/{k2}?base_rev=4")
        p = (await r.json())["plan"]
        assert k2 not in p["nodes"] and len(p["versions"]) == 5
        # re-drafting would overwrite manual edits: asks first
        r = await s.post(base + "/draft", json={})
        assert r.status == 409 and (await r.json())["error"] == "would_overwrite"
        r = await s.post(base + "/draft", json={"force": True})
        assert r.status == 201 and (await r.json())["plan"]["rev"] == 6
        r = await s.post(base + "/versions/4/restore")
        p = (await r.json())["plan"]
        assert p["rev"] == 7 and sub in p["nodes"] and k2 in p["nodes"]


async def test_submit_schedules_within_limit_and_cancel_subtree(tmp_path):
    ctx = make_ctx(tmp_path, brain=FakeBrain(responder, delay=0.002), lean_seconds=0.3)
    async with running(ctx) as (_s, L, _R), session() as s:
        ctx.research.planner.limit = 2
        pid = (await (await s.post(L + "/api/projects", json={"title": "P"})).json())["project"]["id"]
        d = await _dossier(s, L, pid, "theorem t (a b : ℕ) (ha : Even a) (hb : Even b) : Even (a + b) := by sorry")
        base = L + f"/api/dossiers/{d['id']}/plan"
        p = (await (await s.post(base)).json())["plan"]
        rev = p["rev"]
        for i in range(5):
            p = (await (await s.post(base + "/nodes", json={"base_rev": rev, "parent": p["root"], "title": f"L{i}",
                                                            "lean": f"theorem l{i} (n : ℕ) : n + {i} = {i} + n := by sorry"})).json())["plan"]
            rev = p["rev"]
        kids = p["nodes"][p["root"]]["children"]
        p = (await (await s.post(base + "/accept", json={"base_rev": rev, "nodes": kids})).json())["plan"]
        assert (await s.post(base + "/submit", json={"base_rev": 1})).status == 409        # stale
        peak = 0
        r = await s.post(base + "/submit", json={"base_rev": p["rev"]})
        j = await r.json()
        assert r.status == 200 and len(j["submitted"]) == 5, j
        child_ids = [j["plan"]["nodes"][k]["dossier_id"] for k in kids]
        parent = ctx.repo.get(d["id"])
        assert set(parent.uses) == set(child_ids) and parent.retry_parent
        assert all(ctx.repo.get(c).parent_id == d["id"] and ctx.repo.get(c).kind == "lemma" for c in child_ids)
        for _ in range(600):
            act = sum(1 for c in child_ids if ctx.orchestrator.active_for(c))
            peak = max(peak, act)
            if all(ctx.repo.get(c).proof_is_current for c in child_ids):
                break
            await asyncio.sleep(0.02)
        assert peak == 2, peak
        await wait_idle(ctx, 60)
        await asyncio.sleep(0.3)
        pub = (await (await s.get(base)).json())["plan"]
        assert all(pub["nodes"][k]["state"] == "proved" for k in kids)
        assert pub["root_state"] == "proved" and pub["verdict"]["verified"]       # parent retried by the orchestrator

        # cancellation of a subtree: queued leaves never start, running ones are stopped
        d2 = await _dossier(s, L, pid, "theorem u (n : ℕ) : n + 0 = n := by sorry")
        base2 = L + f"/api/dossiers/{d2['id']}/plan"
        p = (await (await s.post(base2)).json())["plan"]
        rev = p["rev"]
        for i in range(4):
            p = (await (await s.post(base2 + "/nodes", json={"base_rev": rev, "parent": p["root"], "title": f"M{i}",
                                                             "lean": f"theorem m{i} (n : ℕ) : n * {i} = {i} * n := by sorry"})).json())["plan"]
            rev = p["rev"]
        kids = p["nodes"][p["root"]]["children"]
        p = (await (await s.post(base2 + "/accept", json={"base_rev": rev, "nodes": kids})).json())["plan"]
        ctx.research.planner.limit = 1
        ctx.brain.delay = 0.05
        j = await (await s.post(base2 + "/submit", json={"base_rev": p["rev"]})).json()
        await asyncio.sleep(0.3)
        r = await s.post(base2 + f"/nodes/{p['root']}/cancel")
        pub = (await r.json())["plan"]
        assert pub["queued"] == [] and all(pub["nodes"][k]["state"] in ("stopped", "proved") for k in kids)
        await wait_idle(ctx, 60)
        started = [k for k in kids if ctx.repo.get(j["plan"]["nodes"][k]["dossier_id"]).events and
                   any(e.kind == "proof" for e in ctx.repo.get(j["plan"]["nodes"][k]["dossier_id"]).events)]
        assert len(started) <= 1


async def test_proved_modulo_admitted_is_never_verified(tmp_path, ws):
    brain = FakeBrain(responder)
    brain.behaviour["lemma_fails"] = True
    ctx = make_ctx(tmp_path, ws=ws, brain=brain)
    ctx.settings.prove_attempts = 1
    async with running(ctx) as (_s, L, _R), session() as s:
        ctx.settings.prove_attempts = 1
        ctx.settings.mathlib_first = False            # Mathlib would close lemA at once (Even.add): keep it failing
        ctx.settings.statement_check = False
        pid = (await (await s.post(L + "/api/projects", json={"title": "P", "workspace": ws.key})).json())["project"]["id"]
        d = await _dossier(s, L, pid, "theorem par (a b : ℕ) (ha : Even a) (hb : Even b) : Even (a + b + 0) := by sorry")
        base = L + f"/api/dossiers/{d['id']}/plan"
        p = (await (await s.post(base)).json())["plan"]
        p = (await (await s.post(base + "/nodes", json={"base_rev": p["rev"], "parent": p["root"], "title": "lemA",
                                                        "lean": "theorem lemA (a b : ℕ) (ha : Even a) (hb : Even b) : Even (a + b) := by sorry"})).json())["plan"]
        k = p["nodes"][p["root"]]["children"][0]
        p = (await (await s.post(base + "/accept", json={"base_rev": p["rev"], "nodes": [k]})).json())["plan"]
        j = await (await s.post(base + "/submit", json={"base_rev": p["rev"], "mode": "local"})).json()
        child_id = j["plan"]["nodes"][k]["dossier_id"]
        await wait_idle(ctx, 300)
        await asyncio.sleep(0.3)
        child = ctx.repo.get(child_id)
        assert not child.proof_is_current and child.status == "failed"
        # admit the failed leaf, then prove the parent modulo it
        p = (await (await s.get(base)).json())["plan"]
        r = await s.post(base + f"/nodes/{k}/admit", json={"base_rev": p["rev"]})
        assert r.status == 200 and (await r.json())["plan"]["nodes"][k]["state"] == "admitted"
        parent = ctx.repo.get(d["id"])
        parent.retry_parent = False                       # exercise the upgrade path, not the orchestrator retry
        code = (f"theorem {parent.theorem} (a b : ℕ) (ha : Even a) (hb : Even b) : Even (a + b + 0) := by\n"
                f"  simpa using {child.theorem} a b ha hb\n")
        r = await s.post(base + "/prove-modulo", json={"code": code})
        res = await r.json()
        assert r.status == 200 and res["ok"], res
        cond = res["conditional"]
        assert cond["verdict"] == "proved_modulo" and cond["admitted"] == [child.theorem]
        assert "sorryAx" in cond["axioms"] and cond["strict_ok"] is False
        assert "sorry" in cond["strict_summary"].lower() or "axiom" in cond["strict_summary"].lower()
        # the invariant, in data: not verified anywhere
        parent = ctx.repo.get(d["id"])
        assert not parent.proof_is_current and parent.status != "proved" and parent.proofs == []
        summ = next(x for x in (await (await s.get(L + "/api/dossiers")).json())["dossiers"] if x["id"] == d["id"])
        assert summ["proved"] is False
        assert res["plan"]["verdict"] == {"state": "proved_modulo", "verified": False, "admitted": 1,
                                          "admitted_names": [child.theorem]}
        assert all(e.name != parent.theorem for e in ctx.library.entries)
        # a proof using `sorry` itself is refused even in conditional mode
        bad = code.replace(f"simpa using {child.theorem} a b ha hb", "sorry")
        ctx.research.planner.store.cache.clear()
        r = await s.post(base + "/prove-modulo", json={"code": bad})
        assert (await r.json())["ok"] is False
        # the admitted lemma gets a real proof → the parent is re-checked with the strict verdict, then proved
        brain.behaviour["lemma_fails"] = False
        r = await s.post(L + f"/api/dossiers/{child_id}/run", json={"plan": ["proof"], "mode": "local"})
        assert r.status == 202
        for _ in range(600):
            parent = ctx.repo.get(d["id"])
            if parent.proof_is_current:
                break
            await asyncio.sleep(0.1)
        assert ctx.repo.get(child_id).proof_is_current
        assert parent.proof_is_current and parent.status == "proved"
        meta = parent.proofs[parent.cur_proof].meta
        assert "sorryAx" not in (meta["axioms"] or []) and meta["strategy"] == "plan"
        assert parent.extra["conditional_proof"]["verdict"] == "superseded"
        pub = (await (await s.get(base)).json())["plan"]
        assert pub["verdict"]["state"] == "proved" and pub["verdict"]["verified"] is True
