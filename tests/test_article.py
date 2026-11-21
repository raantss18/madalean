"""Paper → blueprint (TeX and PDF), transitive verification status, explicit formalisation; Lean → article (blocks,
user edits never overwritten, one block regenerated alone, real compiled PDF with verification table)."""
from __future__ import annotations

import asyncio
import io
import json
import re
import shutil
import subprocess
import zipfile
from pathlib import Path

import aiohttp

from madalean.brain.fake import FakeBrain, demo_responder
from madalean.research import fulltext as ft
from madalean.research import papers
from madalean.research.fetch import Fetcher, ReplayTransport
from madalean.research.sources import Library
from helpers import make_ctx, running, session, started, wait_idle

DATA = Path(__file__).resolve().parents[1] / "madalean" / "research" / "demo_data"
SRC = {"id": "s-abcdef1234", "key": "example2026parity"}


def test_blueprint_from_tex():
    doc = ft.parse_tex((DATA / "parity-note.tex").read_text())
    bp = papers.blueprint_from_tex(doc, SRC)
    got = {(n["kind"], n["number"], n["label"]): sorted(u["to"] for u in n["uses"]) for n in bp["nodes"]}
    assert got == {("definition", "1.1", "def:even"): [], ("lemma", "1.2", "lem:sum"): ["n-def-even"],
                   ("theorem", "2.1", "thm:square"): ["n-def-even", "n-lem-sum"],
                   ("corollary", "2.2", "cor:fourth"): ["n-thm-square"], ("conjecture", "2.3", "conj:odd"): []}
    lem = next(n for n in bp["nodes"] if n["label"] == "lem:sum")
    assert lem["title"] == "Closure" and "a + b = 2(k + l)" in lem["proof"] and lem["quality"] == "high"
    assert lem["text"] == "If $a$ and $b$ are even, then $a + b$ is even."
    assert "Definition 1.1" in lem["proof"]                       # \ref resolved for display
    thm = next(n for n in bp["nodes"] if n["label"] == "thm:square")
    assert "\\mathbb" not in thm["text"] and thm["locator"] == "Theorem 2.1, §2"
    assert set(doc.bibitems) == {"euclid", "hardywright"}


def test_blueprint_from_pdf_text_layer():
    bp = papers.blueprint_from_blocks(papers.pdf_lines(DATA / "parity-note.pdf"), SRC)
    got = {(n["kind"], n["number"]): sorted(u["to"] for u in n["uses"]) for n in bp["nodes"]}
    assert got == {("definition", "1.1"): [], ("lemma", "1.2"): ["n-definition-1-1"],
                   ("theorem", "2.1"): ["n-definition-1-1", "n-lemma-1-2"], ("corollary", "2.2"): ["n-theorem-2-1"],
                   ("conjecture", "2.3"): []}
    assert all(n["quality"] == "medium" and "p. 1" in n["locator"] for n in bp["nodes"])
    assert "References" not in next(n for n in bp["nodes"] if n["kind"] == "conjecture")["text"]


def test_model_edges_are_only_between_existing_nodes():
    doc = ft.parse_tex((DATA / "parity-note.tex").read_text())
    bp = papers.blueprint_from_tex(doc, SRC)
    msgs = papers.uses_messages(bp)
    assert "<<<SOURCE_DATA n-lem-sum>>>" in msgs[0]["content"]
    n = papers.apply_model_uses(bp, '[{"from": "n-conj-odd", "to": "n-thm-square"}, {"from": "n-x", "to": '
                                    '"n-thm-square"}, {"from": "n-cor-fourth", "to": "n-cor-fourth"}, '
                                    '{"from": "n-cor-fourth", "to": "n-thm-square"}, "garbage"]')
    assert n == 1
    conj = next(x for x in bp["nodes"] if x["id"] == "n-conj-odd")
    assert conj["uses"] == [{"to": "n-thm-square", "via": "model", "proposed": True}]


# ---------------------------------------------------------------- status
def _proved(d, ok=True):
    d.add_statement(f"theorem {d.theorem} : True := by sorry")
    if ok:
        d.add_proof(f"theorem {d.theorem} : True := by\n  trivial", meta={"axioms": []})


async def test_verified_is_computed_transitively(tmp_path):
    ctx = await started(make_ctx(tmp_path))
    p = ctx.projects.store.new("P")
    await ctx.projects.save(p)
    nodes = []
    for nid, kind in (("n-a", "theorem"), ("n-b", "lemma"), ("n-c", "lemma"), ("n-d", "definition"),
                      ("n-e", "lemma"), ("n-f", "lemma")):
        nodes.append({"id": nid, "kind": kind, "name": kind, "number": nid[-1], "label": "", "title": "", "text": "x",
                      "proof": "", "locator": "", "uses": [], "dossier_id": "", "cites": []})
    use = {"n-a": ["n-b"], "n-b": ["n-c"], "n-e": ["n-d"], "n-f": ["n-f2"]}
    for n in nodes:
        n["uses"] = [{"to": t, "via": "proof_ref", "proposed": False} for t in use.get(n["id"], [])]
    nodes[-1]["uses"] = [{"to": "n-e", "via": "proof_ref", "proposed": False}]
    nodes[4]["uses"].append({"to": "n-f", "via": "model", "proposed": True})        # cycle e ⇄ f (proposed)
    bp = {"source_id": "s-abcdef1234", "paper_key": "k", "nodes": nodes}
    ds = {}
    for n in nodes:
        d = ctx.repo.new("x", "demo", n["id"])
        d.project_id, d.kind = p.id, ("definition" if n["kind"] == "definition" else "lemma")
        n["dossier_id"] = d.id
        ds[n["id"]] = d
        ctx.repo.cache[d.id] = d
    _proved(ds["n-a"]), _proved(ds["n-b"]), _proved(ds["n-c"], ok=False), _proved(ds["n-e"]), _proved(ds["n-f"])
    ds["n-d"].add_statement("theorem d : True := by sorry", ok=False)
    st = lambda: {v["node_id"]: v for v in papers.node_states(ctx, [bp]).values()}  # noqa: E731
    s = st()
    assert s["n-c"]["state"] == "statement" and not s["n-c"]["verified"]
    assert s["n-a"]["state"] == "proved" and not s["n-a"]["verified"] and s["n-a"]["unverified_uses"] == ["n-b"]
    assert s["n-b"]["state"] == "proved" and not s["n-b"]["verified"]
    assert s["n-e"]["state"] == "proved" and not s["n-e"]["verified"]       # definition d not accepted + cycle
    assert s["n-d"]["state"] == "stated"
    d = ds["n-c"]
    d.add_proof(f"theorem {d.theorem} : True := by\n  trivial")
    s = st()
    assert s["n-a"]["verified"] and s["n-b"]["verified"] and s["n-c"]["state"] == "verified"
    ds["n-d"].statements[-1].ok = True
    s = st()
    assert s["n-d"]["state"] == "verified" and not s["n-e"]["verified"]      # still in a cycle with f
    nodes[4]["uses"][-1]["rejected"] = True                                  # the user rejects the proposed edge
    s = st()
    assert s["n-e"]["verified"] and s["n-f"]["verified"]
    ds["n-b"].add_statement("theorem changed : False := by sorry")           # b's proof no longer proves its statement
    s = st()
    assert not s["n-a"]["verified"] and s["n-b"]["state"] == "statement"
    # blocked: a node that uses a definition without an accepted Lean statement
    ds["n-d"].statements[-1].ok = False
    nodes[4]["uses"] = [{"to": "n-d", "via": "proof_ref", "proposed": False}]
    ds["n-e"].add_statement("theorem e2 : True := by sorry")
    assert st()["n-e"]["state"] == "blocked" and st()["n-e"]["missing_definitions"] == ["n-d"]


# ---------------------------------------------------------------- HTTP flow
def responder(role, messages, brain):
    first = messages[0]["content"]
    if first.startswith("Here are the numbered results of a mathematical paper"):
        return '[{"from": "n-conj-odd", "to": "n-thm-square"}, {"from": "invented", "to": "n-lem-sum"}]'
    return demo_responder(role, messages, brain)


async def test_blueprint_dossiers_and_explicit_formalisation(tmp_path):
    ctx = make_ctx(tmp_path, brain=FakeBrain(responder))
    async with running(ctx) as (srv, local, remote):
        lib = Library(ctx, Fetcher(ReplayTransport(Path("/nonexistent"))))
        lib.embeddings = False
        ctx._research_library = lib
        async with session() as s, s.ws_connect(local + "/api/ws") as ws:
            await ws.receive_json()
            async with s.post(local + "/api/projects", json={"title": "Parité"}) as r:
                pid = (await r.json())["project"]["id"]
            form = aiohttp.FormData()
            form.add_field("file", (DATA / "parity-note.tar.gz").read_bytes(), filename="note.tar.gz")
            async with s.post(local + f"/api/research/shelves/{pid}/sources", data=form) as r:
                src = (await r.json())["source"]
            assert src["verified"] is False and src["csl"]["title"] == "A note on parity"     # from \title
            async with s.post(local + f"/api/research/projects/{pid}/blueprints",
                              json={"source_id": src["id"], "model_pass": True}) as r:
                assert r.status == 201
                data = await r.json()
            bp, rid = data["blueprint"], data["request_id"]
            assert bp["method"] == "tex" and len(bp["nodes"]) == 5 and rid
            for _ in range(200):
                async with s.get(local + f"/api/research/projects/{pid}/blueprints/{src['id']}") as r:
                    got = await r.json()
                if got["blueprint"].get("model_pass"):
                    break
                await asyncio.sleep(0.05)
            assert got["blueprint"]["model_pass"]["added"] == 1
            assert set(v["state"] for v in got["status"].values()) == {"not_created"}
            # create dossiers for two nodes: nothing starts
            async with s.post(local + f"/api/research/projects/{pid}/blueprints/{src['id']}/dossiers",
                              json={"nodes": ["n-lem-sum", "n-def-even"]}) as r:
                assert r.status == 201
                made = {d["extra_node"] if "extra_node" in d else d["blueprint"]["node_id"]: d
                        for d in (await r.json())["dossiers"]}
            assert ctx.orchestrator.active() == []
            lem, dfn = made["n-lem-sum"], made["n-def-even"]
            assert lem["kind"] == "lemma" and dfn["kind"] == "definition"
            assert lem["source"]["paper_key"] == src["key"] and lem["source"]["locator"] == "Lemma 1.2, §1"
            assert "\\begin" not in lem["problem"] and "Lemma 1.2 (Closure)." in lem["problem"]
            assert "(Definition 1.1) An integer" in lem["problem"]                  # the definition it uses
            assert lem["uses"] == [dfn["id"]] and lem["refs"][0] == {"key": src["key"], "locator": "Lemma 1.2",
                                                                      "note": ""}
            # the rest later: uses are re-linked to the new dossiers
            async with s.post(local + f"/api/research/projects/{pid}/blueprints/{src['id']}/dossiers", json={}) as r:
                rest = {d["blueprint"]["node_id"]: d for d in (await r.json())["dossiers"]}
            assert set(rest) == {"n-thm-square", "n-cor-fourth", "n-conj-odd"}
            assert set(rest["n-thm-square"]["uses"]) == {lem["id"], dfn["id"]}
            assert rest["n-conj-odd"]["kind"] in ("claim", "conjecture")
            # explicit formalisation: normal jobs, paper proof as hint to Goedel only
            async with s.post(local + f"/api/research/projects/{pid}/formalise",
                              json={"dossier_ids": [lem["id"], dfn["id"]], "mode": "local"}) as r:
                assert r.status == 202
                jobs = (await r.json())["jobs"]
            assert len(jobs) == 2
            jl = next(j for j in jobs if j["dossier_id"] == lem["id"])
            assert jl["strategy"] == "goedel"
            hint = next(st for st in jl["plan"] if st["stage"] == "proof")["request"]
            assert "<<<SOURCE_DATA proof from" in hint and "2(k + l)" in hint
            async with s.post(local + f"/api/research/projects/{pid}/formalise",
                              json={"dossier_ids": [lem["id"]]}) as r:
                assert r.status == 409 and (await r.json())["error"] == "busy"
            await wait_idle(ctx)
            prove_prompts = [q["messages"][0]["content"] for q in ctx.brain.requests
                             if q["messages"][0]["content"].startswith("Complete the following Lean 4 code")]
            assert any("2(k + l)" in p for p in prove_prompts)
            async with s.get(local + f"/api/research/projects/{pid}/blueprint-status") as r:
                st = {v["node_id"]: v for v in (await r.json())["nodes"]}
            assert st["n-lem-sum"]["state"] in ("proved", "verified")
            assert st["n-def-even"]["state"] in ("defined", "verified", "stated")
            assert st["n-thm-square"]["state"] == "stated" and not st["n-thm-square"]["verified"]
            assert st["n-lem-sum"]["verified"] == (st["n-def-even"]["state"] == "verified")
            # edges are curated by the user and follow into the dossiers
            async with s.post(local + f"/api/research/projects/{pid}/blueprints/{src['id']}/edges",
                              json={"from": "n-thm-square", "to": "n-lem-sum", "action": "remove"}) as r:
                assert r.status == 200
            assert ctx.repo.get(rest["n-thm-square"]["id"]).uses == [dfn["id"]]
            async with s.post(local + f"/api/research/projects/{pid}/blueprints/{src['id']}/edges",
                              json={"from": "n-thm-square", "to": "../../x", "action": "add"}) as r:
                assert r.status == 400


# ---------------------------------------------------------------- article
WILES = {"type": "article-journal", "title": "Modular elliptic curves and Fermat's Last Theorem",
         "author": [{"family": "Wiles", "given": "Andrew"}], "container-title": "Annals of Mathematics",
         "volume": "141", "page": "443-551", "issued": {"date-parts": [[1995]]}, "DOI": "10.2307/2118559"}


def art_responder(role, messages, brain):
    first = messages[0]["content"]
    if first.startswith(("Write the abstract", "Write the introduction", "Write a short")):
        return ("<think>x</think>## Heading\nWe prove that sums of even numbers are even, as in [@wiles1995modular] "
                "and [@fake2020]; the square result is only stated.")
    return demo_responder(role, messages, brain)


async def test_article_blocks_drafts_and_compiled_pdf(tmp_path):
    ctx = make_ctx(tmp_path, brain=FakeBrain(art_responder))
    async with running(ctx) as (srv, local, remote):
        lib = Library(ctx, Fetcher(ReplayTransport(Path("/nonexistent"))))
        lib.embeddings = False
        ctx._research_library = lib
        async with session() as s, s.ws_connect(local + "/api/ws") as ws:
            await ws.receive_json()
            async with s.post(local + "/api/projects", json={"title": "Parité"}) as r:
                pid = (await r.json())["project"]["id"]
            await lib.add_record(pid, WILES, via="form", extract=False)
            async with s.post(local + "/api/dossiers", json={"problem": "Montrer que la somme de deux entiers pairs "
                                                             "est paire.", "project_id": pid}) as r:
                proved_id = (await r.json())["dossier"]["id"]
            await wait_idle(ctx)
            async with s.post(local + "/api/dossiers", json={"problem": "Tout carré impair est congru à 1 modulo 8.",
                                                             "project_id": pid, "start": False}) as r:
                open_id = (await r.json())["dossier"]["id"]
            async with s.get(local + f"/api/research/projects/{pid}/article") as r:
                art = (await r.json())["article"]
            kinds = [b["kind"] for b in art["blocks"]]
            assert kinds == ["intro", "dossier", "dossier"] and art["title"] == "Parité"
            intro = art["blocks"][0]
            # user writes the introduction: an AI draft never overwrites it
            async with s.patch(local + f"/api/research/projects/{pid}/article/blocks/{intro['id']}",
                               json={"text": "Mon introduction, écrite à la main [@wiles1995modular, Thm 0.4]."}) as r:
                assert (await r.json())["block"]["source"] == "user"
            async with s.post(local + f"/api/research/projects/{pid}/article/blocks/{intro['id']}/generate",
                              json={}) as r:
                assert r.status == 409 and (await r.json())["error"] == "user_edited"
            # regenerate the abstract only
            async with s.patch(local + f"/api/research/projects/{pid}/article",
                               json={"title": "Sommes paires, vérifiées", "authors": [{"name": "A. Auteur"}],
                                     "options": {"lang": "en"}}) as r:
                assert r.status == 200
            async with s.post(local + f"/api/research/projects/{pid}/article/blocks/abstract/generate",
                              json={"mode": "local"}) as r:
                rid = (await r.json())["request_id"]
            while True:
                ev = json.loads((await asyncio.wait_for(ws.receive(), 30)).data)
                if ev["type"] in ("article.done", "article.error") and ev.get("request_id") == rid:
                    break
            assert ev["type"] == "article.done" and ev["removed_citations"] == ["fake2020"]
            async with s.get(local + f"/api/research/projects/{pid}/article") as r:
                art2 = (await r.json())["article"]
            assert art2["blocks"][0]["text"].startswith("Mon introduction") and art2["blocks"][0]["source"] == "user"
            ab = art2["abstract"]
            assert ab["source"] == "ai" and "fake2020" not in ab["text"] and "##" not in ab["text"]
            assert "[@wiles1995modular]" in ab["text"] and ab["versions"][-1]["model"]
            # restore an earlier version, add/delete/undo a block, reorder
            async with s.post(local + f"/api/research/projects/{pid}/article/blocks/{intro['id']}/versions/0/restore") as r:
                assert (await r.json())["block"]["text"] == ""
            async with s.post(local + f"/api/research/projects/{pid}/article/blocks/{intro['id']}/versions/1/restore") as r:
                assert (await r.json())["block"]["source"] == "user"
            async with s.post(local + f"/api/research/projects/{pid}/article/blocks",
                              json={"kind": "section", "title": "Open questions", "after": art2["blocks"][1]["id"]}) as r:
                sec = (await r.json())["block"]
            async with s.delete(local + f"/api/research/projects/{pid}/article/blocks/{sec['id']}") as r:
                undo = (await r.json())["undo"]
            async with s.post(local + undo) as r:
                order = [b["id"] for b in (await r.json())["article"]["blocks"]]
            assert order[2] == sec["id"]
            if not shutil.which("xelatex"):
                return
            async with s.get(local + f"/api/research/projects/{pid}/article/export?format=pdf") as r:
                assert r.headers["Content-Type"] == "application/pdf" and r.headers["X-Madalean-Fallback"] == "", \
                    await r.text()
                pdf = await r.read()
            p = tmp_path / "a.pdf"
            p.write_bytes(pdf)
            text = re.sub(r"-\n\s*", "", subprocess.run(["pdftotext", "-layout", str(p), "-"], capture_output=True,
                                                        text=True).stdout)
            assert "SOMMES PAIRES" in text.upper() and "Abstract" in text
            assert re.search(r"Theorem 1\b|Lemma 1\b|Proposition 1\b", text)               # verified → theorem-like
            assert re.search(r"Claim 2.*not verified by Lean", text, re.S)                   # never a theorem
            assert "Formal verification" in text and "yes" in text and "no" in text
            assert "References" in text and "Wil95" in text and "Modular elliptic curves" in text
            assert "Lean code" in text and "Even.add" in text
            async with s.get(local + f"/api/research/projects/{pid}/article/export?format=zip") as r:
                names = zipfile.ZipFile(io.BytesIO(await r.read())).namelist()
            assert any(n.endswith(".tex") for n in names) and any(n.endswith("refs.bib") for n in names)
            assert any(n.endswith(".pdf") for n in names) and sum(n.endswith(".lean") for n in names) == 1
            async with s.get(local + f"/api/research/projects/{pid}/article/export?format=tex") as r:
                tex = await r.text()
            assert "\\begin{claim}" in tex and "\\MLunverified" in tex and "\\begin{thebibliography}" in tex
            assert ctx.repo.get(open_id).proof_is_current is False and ctx.repo.get(proved_id).proof_is_current
