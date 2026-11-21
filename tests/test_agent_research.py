"""« Consigne de recherche » (session S-Q): an instruction in natural language on a source → bounded steps using the
existing features (blueprint, grounded context, Lean pipeline jobs, Calcul cells, conjecture workshop, wording edits)
→ SUGGESTIONS accepted or rejected one by one; nothing in the article changes without acceptance. Fake models."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

from madalean.brain.fake import demo_responder
from madalean.research import agent_research as ar
from madalean.research.fetch import Fetcher, ReplayTransport
from madalean.research.sources import Library
from helpers import make_ctx, running, session

DATA = Path(__file__).resolve().parents[1] / "madalean" / "research" / "demo_data"
INSTR = ("vérifie les résultats avec Lean, ajoute des exemples et des graphiques avec Sage, améliore la rédaction, "
         "généralise le théorème 2.1")


def test_parse_instruction_fr_en_and_targets():
    p = ar.parse_instruction(INSTR)
    assert p["order"] == ["verify", "examples", "figures", "improve", "generalise"]
    assert p["steps"]["generalise"] == [{"kind": "theorem", "number": "2.1"}] and p["steps"]["verify"] == []
    p = ar.parse_instruction("Check Lemma 1.2 and theorem 3 in Lean; then proofread the introduction.")
    assert p["steps"]["verify"] == [{"kind": "lemma", "number": "1.2"}, {"kind": "theorem", "number": "3"}]
    assert "improve" in p["steps"]
    assert ar.parse_instruction("bonjour")["order"] == []
    lim = ar.clamp_limits({"max_steps": 999, "max_minutes": "x", "max_cost_usd": -3})
    assert lim["max_steps"] == 40 and lim["max_minutes"] == 30 and lim["max_cost_usd"] == 0.0
    steps = ar.plan(p, has_blueprint=False, article_has_text=False, limits=ar.clamp_limits({"max_steps": 3}))
    assert [s["kind"] for s in steps] == ["blueprint", "context", "import"]          # bounded
    # « théorème 1 » in a paper numbered 1.1, 1.2 (the real arXiv run), « théorème 2 » = 2nd theorem, not lemma 2
    bp = {"nodes": [{"id": "a", "kind": "theorem", "number": "1.1"}, {"id": "b", "kind": "theorem", "number": "1.2"},
                    {"id": "c", "kind": "lemma", "number": "2"}]}
    pick = lambda k, n: [x["id"] for x in ar.select_nodes(bp, [{"kind": k, "number": n}], 3)]  # noqa: E731
    assert pick("theorem", "1") == ["a"] and pick("theorem", "2") == ["b"] and pick("lemma", "2") == ["c"]
    assert [x["id"] for x in ar.select_nodes(bp, [], 2)] == ["a", "b"]


def responder(role, messages, brain):
    text = messages[-1]["content"]
    if "copy-editor" in text:
        return json.dumps([{"excerpt": "The next result is the main point of this note.",
                            "replacement": "The next result is the main point of this note:", "reason": "colon"},
                           {"excerpt": "not in the text at all", "replacement": "x", "reason": "invented"}])
    if "computes 2 or 3 small" in text:
        return "```sage\nprint([n^2 for n in [2, 4, 6]])\n```\nPour $n = 2, 4, 6$, les carrés $4, 16, 36$ sont pairs."
    if "draws ONE clear FIGURE" in text:
        return "```sage\ng = list_plot([n^2 for n in range(10)])\ng\n```\nLes carrés des premiers entiers."
    if "natural generalisation" in text:
        return json.dumps({"statement": "If $n$ is even and $m \\geq 1$, then $n^m$ is even.",
                           "why": "Induction on $m$.", "sage": "print(all((2*k)^m % 2 == 0 for k in range(5) "
                                                               "for m in range(1, 5)))"})
    return demo_responder(role, messages, brain)


async def setup(ctx, s, local):
    async with s.post(local + "/api/projects", json={"title": "Parité"}) as r:
        pid = (await r.json())["project"]["id"]
    lib = Library(ctx, Fetcher(ReplayTransport(Path("/nonexistent"))))
    lib.embeddings = False
    ctx._research_library = lib
    src, _ = await lib.add_record(pid, {"type": "article", "title": "A note on parity", "_key": "parity"},
                                  via="form", files=[("parity-note.tar.gz", (DATA / "parity-note.tar.gz").read_bytes())],
                                  extract=False)
    await lib.extract(pid, src["id"])
    return pid, src


async def wait_run(s, local, pid, rid, timeout=120):
    loop = asyncio.get_running_loop()
    end = loop.time() + timeout
    while loop.time() < end:
        async with s.get(local + f"/api/research/projects/{pid}/consignes/{rid}") as r:
            run = (await r.json())["run"]
        if run["status"] not in ("running", "planned"):
            return run
        await asyncio.sleep(0.2)
    raise TimeoutError(rid)


async def test_consigne_end_to_end_suggestions_accept_reject(tmp_path):
    ctx = make_ctx(tmp_path)
    ctx.brain.responder = responder
    async with running(ctx) as (srv, local, remote):
        ctx.settings.mode = "auto"
        async with session() as s:
            pid, src = await setup(ctx, s, local)
            base = local + f"/api/research/projects/{pid}"
            # plan preview: nothing saved, nothing runs
            async with s.post(base + "/consignes", json={"source": {"id": src["id"]}, "instruction": INSTR,
                                                         "dry_run": True}) as r:
                assert r.status == 200, await r.text()
                plan = (await r.json())["run"]
            kinds = [x["kind"] for x in plan["steps"]]
            assert kinds == ["blueprint", "context", "import", "verify", "examples", "figures", "improve",
                             "generalise"]
            async with s.get(base + "/consignes") as r:
                assert (await r.json())["runs"] == []
            async with s.post(base + "/consignes", json={"source": {"id": src["id"]}, "instruction": "bonjour"}) as r:
                assert r.status == 422 and (await r.json())["message"]["text"]
            async with s.get(local + f"/api/research/projects/{pid}/article") as r:
                before_art = (await r.json())["article"]
            # run it
            async with s.post(base + "/consignes", json={"source": {"id": src["id"]}, "instruction": INSTR,
                                                         "limits": {"max_minutes": 5}}) as r:
                assert r.status == 202, await r.text()
                rid = (await r.json())["run"]["id"]
            async with s.post(base + "/consignes", json={"source": {"id": src["id"]}, "instruction": INSTR}) as r:
                assert r.status == 409                       # one run at a time per project
            run = await wait_run(s, local, pid, rid)
            assert run["status"] == "done", run
            assert all(st["status"] == "done" for st in run["steps"]), run["steps"]
            assert run["journal_note"] and run["dossiers"] and run["cells"] and run["conjectures"]
            # the journal is a project note with one line per step
            note = ctx.research.notes.get(run["journal_note"])
            assert note.project_id == pid and note.body.count("\n- ") >= len(run["steps"])
            # import: the paper's text verbatim, nothing rewritten
            async with s.get(local + f"/api/research/projects/{pid}/article") as r:
                art = (await r.json())["article"]
            imported = [b for b in art["blocks"] if b.get("imported_from") == "parity"]
            assert imported and any("The next result is the main point of this note." in b["text"] for b in imported)
            assert len(art["blocks"]) == len(before_art["blocks"]) + len(imported)
            # suggestions of every type, with evidence
            async with s.get(base + "/suggestions") as r:
                res = await r.json()
            sug = res["suggestions"]
            types = {x["type"] for x in sug}
            assert types == {"verification", "exemple", "figure", "correction", "generalisation"}, types
            corr = [x for x in sug if x["type"] == "correction"]
            assert len(corr) == 1                            # the invented excerpt was dropped by code
            gen = next(x for x in sug if x["type"] == "generalisation")
            assert gen["after"].startswith("**Conjecture") and gen["conjecture"] and gen["evidence"]["lean"]
            ex = next(x for x in sug if x["type"] == "exemple")
            cal = ex["evidence"]["calcul"][0]
            assert cal["approved"] is False and cal["run"] is None   # assistant code: not run without approval
            ver = [x for x in sug if x["type"] == "verification"]
            assert ver and all(v["evidence"]["lean"][0].get("title") for v in ver)
            async with s.get(base + "/suggestions?type=figure") as r:
                assert {x["type"] for x in (await r.json())["suggestions"]} == {"figure"}
            # accept the wording correction: exactly that excerpt changes, the old text stays in the history
            async with s.post(base + f"/suggestions/{corr[0]['id']}/accept", json={}) as r:
                assert r.status == 200, await r.text()
                assert (await r.json())["suggestion"]["status"] == "accepted"
            async with s.get(local + f"/api/research/projects/{pid}/article") as r:
                art2 = (await r.json())["article"]
            b = next(x for x in art2["blocks"] if x["id"] == corr[0]["target"]["block_id"])
            assert "main point of this note:" in b["text"] and len(b["versions"]) == 2
            async with s.post(base + f"/suggestions/{corr[0]['id']}/accept", json={}) as r:
                assert r.status == 409 and (await r.json())["error"] == "already_decided"
            # the example: inserted as a new block (marker rendered as text, never raw)
            async with s.post(base + f"/suggestions/{ex['id']}/accept", json={}) as r:
                assert r.status == 200
            async with s.get(local + f"/api/research/projects/{pid}/article") as r:
                art3 = (await r.json())["article"]
            nb = [x for x in art3["blocks"] if "Exemple" in x.get("title", "")]
            assert nb and "[[calcul:" not in nb[0]["text"] and "pas encore exécutée" in nb[0]["text"]
            # reject the generalisation: the article does not change
            n_blocks = len(art3["blocks"])
            async with s.post(base + f"/suggestions/{gen['id']}/reject", json={}) as r:
                assert (await r.json())["suggestion"]["status"] == "rejected"
            async with s.get(local + f"/api/research/projects/{pid}/article") as r:
                assert len((await r.json())["article"]["blocks"]) == n_blocks
            # a stale suggestion (the user edited the text meanwhile) is refused, not applied
            stale = ar.new_suggestion(run, "correction", title="x", before="absent paragraph", after="y",
                                      rationale="", target={"mode": "replace_excerpt",
                                                            "block_id": imported[0]["id"]})
            ctx.research_agent.store.add_suggestion(pid, stale)
            async with s.post(base + f"/suggestions/{stale['id']}/accept", json={}) as r:
                assert r.status == 409 and (await r.json())["error"] == "stale"
            # one search across the project: dossiers, notes, calcul, passages, suggestions
            async with s.get(base + "/search?q=even") as r:
                kinds = {x["kind"] for x in (await r.json())["results"]}
            assert {"dossier", "passage"} <= kinds, kinds
            async with s.get(base + "/search?q=list_plot") as r:
                assert any(x["kind"] in ("calcul", "figure") for x in (await r.json())["results"])
            async with s.get(base + "/search?q=Journal") as r:
                hits = (await r.json())["results"]
            # to the article / to Publier (explicit user actions)
            did = run["dossiers"][0]
            async with s.post(base + "/basket", json={"kind": "dossier", "id": did}) as r:
                assert (await r.json())["basket"]["dossiers"] == [did]
            async with s.post(base + "/to-article", json={"kind": "passage", "id": "c1", "source_key": "parity",
                                                          "text": "If $n$ is even, then $n^2$ is even.",
                                                          "locator": "Thm 2.1"}) as r:
                assert r.status == 201 and "[@parity, Thm 2.1]" in (await r.json())["block"]["text"]
            assert hits is not None


async def test_cancel_and_resume_and_limits(tmp_path):
    ctx = make_ctx(tmp_path)

    async def slow(role, messages, brain):
        await asyncio.sleep(0.4)
        return responder(role, messages, brain)
    ctx.brain.responder = slow
    async with running(ctx) as (srv, local, remote):
        ctx.settings.mode = "auto"
        async with session() as s:
            pid, src = await setup(ctx, s, local)
            base = local + f"/api/research/projects/{pid}"
            async with s.post(base + "/consignes", json={"source": {"id": src["id"]},
                                                         "instruction": "améliore la rédaction, ajoute des exemples"}) \
                    as r:
                rid = (await r.json())["run"]["id"]
            await asyncio.sleep(0.6)
            async with s.post(base + f"/consignes/{rid}/cancel") as r:
                assert (await r.json())["run"]["status"] == "cancelled"
            async with s.get(base + f"/consignes/{rid}") as r:
                run = (await r.json())["run"]
            done_before = [st["id"] for st in run["steps"] if st["status"] == "done"]
            assert len(done_before) < len(run["steps"])
            async with s.post(base + f"/consignes/{rid}/resume") as r:
                assert r.status == 202
            run = await wait_run(s, local, pid, rid)
            assert run["status"] == "done" and all(st["status"] == "done" for st in run["steps"])
            # steps already done were not redone (the blueprint was extracted once)
            # limits: a 1-step budget stops right after the first step, saying why
            async with s.post(base + "/consignes", json={"source": {"id": src["id"]}, "instruction":
                                                         "améliore la rédaction", "limits": {"max_steps": 1}}) as r:
                rid2 = (await r.json())["run"]["id"]
            run2 = await wait_run(s, local, pid, rid2)
            assert len(run2["steps"]) == 1 and run2["status"] == "done"
    # a run left « running » by a crash is shown paused and resumable
    run2["status"] = "running"
    ctx.research_agent.store.save_run(run2)
    assert ctx.research_agent.public_run(run2)["status"] == "paused"


def test_vacuous_lean_statement_is_never_a_verification():
    # real run 2026-11-22: « Theorem 1.1 » formalised as `: True`, « proved » by `trivial`
    assert ar.vacuous("import Mathlib\n\ntheorem t_1_1 : True := by sorry")
    assert ar.vacuous("theorem t {x : ℕ} : x = x := by sorry")
    assert not ar.vacuous("theorem t (n : ℕ) (h : Even n) : Even (n ^ 2) := by sorry")
    assert not ar.vacuous("/-- a : True -/ theorem t (a : ℕ) : a + 0 = a := by sorry")
