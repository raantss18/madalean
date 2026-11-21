"""Sources library, literature search and grounded answers over HTTP + WebSocket (fake brain, recorded API answers
from tests/data/research/http — recorded once by tests/test_sources_online.py)."""
from __future__ import annotations

import asyncio
import io
import json
import re
import zipfile
from pathlib import Path

import aiohttp

from madalean.brain.fake import FakeBrain, demo_responder
from madalean.research.fetch import Fetcher, ReplayTransport
from madalean.research.sources import Library
from helpers import make_ctx, running, session

FIX = Path(__file__).parent / "data" / "research" / "http"
DATA = Path(__file__).resolve().parents[1] / "madalean" / "research" / "demo_data"


def research_ctx(tmp_path, responder=None):
    ctx = make_ctx(tmp_path, brain=FakeBrain(responder) if responder else None)
    t = ReplayTransport(FIX, loose=True)          # same endpoint, other parameters → recorded answer
    t.add("https://arxiv.org/src/2603.29335", (DATA / "parity-note.tar.gz").read_bytes(), content_type="application/gzip")
    t.add("https://arxiv.org/pdf/2603.29335", (DATA / "parity-note.pdf").read_bytes(), content_type="application/pdf")
    lib = Library(ctx, Fetcher(t))
    lib.embeddings = False
    ctx._research_library = lib
    return ctx, t


async def new_project(s, local, title="Projet"):
    async with s.post(local + "/api/projects", json={"title": title}) as r:
        return (await r.json())["project"]["id"]


async def wait_fulltext(s, url, timeout=60):
    for _ in range(int(timeout / 0.1)):
        async with s.get(url) as r:
            src = (await r.json())["source"]
        if src["fulltext"].get("state") not in (None, "none"):
            return src
        await asyncio.sleep(0.1)
    raise TimeoutError(url)


async def ws_until(ws, pred, timeout=30.0):
    loop = asyncio.get_running_loop()
    end = loop.time() + timeout
    out = []
    while loop.time() < end:
        m = await asyncio.wait_for(ws.receive(), end - loop.time())
        ev = json.loads(m.data)
        out.append(ev)
        if pred(ev):
            return out
    raise TimeoutError


async def test_add_by_identifiers_dedup_and_files(tmp_path):
    ctx, t = research_ctx(tmp_path)
    async with running(ctx) as (srv, local, remote):
        async with session() as s, s.ws_connect(local + "/api/ws") as ws:
            await ws.receive_json()
            pid = await new_project(s, local)
            base = local + f"/api/research/shelves/{pid}/sources"
            async with s.post(base, json={"identifier": "https://doi.org/10.2307/2118559"}) as r:
                assert r.status == 201, await r.text()
                doi = (await r.json())["source"]
            assert doi["csl"]["title"] == "Modular Elliptic Curves and Fermat's Last Theorem"
            assert doi["key"] == "wiles1995modular" and doi["verified"] and doi["files"] == []
            assert doi["oa"]["is_oa"] is False                     # closed access: no PDF fetched
            assert not any("jstor" in u for u in t.requests)
            evs = await ws_until(ws, lambda e: e["type"] == "sources.updated")
            assert evs[-1]["shelf"] == pid and evs[-1]["source"]["id"] == doi["id"]
            async with s.post(base, json={"identifier": "doi:10.2307/2118559"}) as r:
                d = await r.json()
                assert r.status == 200 and d["duplicate"] == {"of": doi["id"], "reason": "doi"}
            # arXiv: metadata + e-print source + PDF, then full text
            async with s.post(base, json={"identifier": "arXiv:2603.29335"}) as r:
                assert r.status == 201
                ax = (await r.json())["source"]
            assert ax["csl"]["arxiv"] == "2603.29335" and {f["kind"] for f in ax["files"]} == {"archive", "pdf"}
            ax = await wait_fulltext(s, f"{base}/{ax['id']}")
            assert ax["fulltext"]["state"] == "ok" and ax["fulltext"]["method"] == "tex" and ax["fulltext"]["chunks"] > 5
            # ISBN and zbMATH
            async with s.post(base, json={"identifier": "ISBN 978-0-19-853171-5"}) as r:
                book = (await r.json())["source"]
            assert book["csl"]["type"] == "book" and book["key"].startswith("hardy")
            async with s.post(base, json={"identifier": "Zbl 0965.11001"}) as r:
                zb = (await r.json())["source"]
            assert zb["csl"]["msc"][0] == "11-02" and zb["csl"]["zbl"] == "0965.11001"
            async with s.post(base, json={"identifier": "not an id"}) as r:
                assert r.status == 400 and (await r.json())["error"] == "unknown_identifier"
            async with s.get(base) as r:
                lst = (await r.json())["sources"]
            assert len(lst) == 4 and len({x["key"] for x in lst}) == 4
            # local mode: nothing is fetched, a clear refusal
            n_before = len(t.requests)
            async with s.patch(local + "/api/settings", json={"mode": "local"}) as r:
                assert r.status == 200
            async with s.post(base, json={"identifier": "10.1000/xyz"}) as r:
                assert r.status == 409 and (await r.json())["error"] == "local_mode"
            async with s.post(local + "/api/research/litsearch", json={"query": "parity"}) as r:
                assert r.status == 409
            assert len(t.requests) == n_before


async def test_manual_import_export_patch_annotations_undo(tmp_path):
    ctx, _t = research_ctx(tmp_path)
    async with running(ctx) as (srv, local, remote):
        async with session() as s:
            pid = await new_project(s, local)
            base = local + f"/api/research/shelves/{pid}/sources"
            bib = ("@article{knuth84, author={Knuth, Donald E.}, title={Literate Programming}, journal={The Computer "
                   "Journal}, volume=27, number=2, pages={97--111}, year=1984, doi={10.1093/comjnl/27.2.97}}\n"
                   "@book{hw79, author={Hardy, G. H. and Wright, E. M.}, title={An introduction to the theory of "
                   "numbers}, publisher={Clarendon Press}, year={1979}, file={Hardy:files/hw.pdf:application/pdf}}")
            async with s.post(base, json={"text": bib}) as r:
                res = await r.json()
            assert r.status == 201 and [a["key"] for a in res["added"]] == ["knuth84", "hw79"]
            assert res["unattached_files"] == ["files/hw.pdf"]           # never read from an arbitrary path
            async with s.post(base, json={"text": bib}) as r:            # same file again: duplicates
                res = await r.json()
            assert res["added"] == [] and len(res["duplicates"]) == 2
            ris = "TY  - JOUR\nAU  - Euler, Leonhard\nTI  - Solutio problematis ad geometriam situs pertinentis\nPY  - 1741\nER  - \n"
            async with s.post(base, json={"text": ris}) as r:
                assert (await r.json())["added"][0]["key"] == "euler1741solutio"
            async with s.post(base, json={"csl": {"title": "Handmade notes", "type": "manuscript",
                                                  "author": [{"family": "Moi", "given": "A."}]}}) as r:
                hand = (await r.json())["source"]
            # Zotero export folder zipped: metadata + attached PDF inside the archive
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, "w") as z:
                z.writestr("export/My Library.json", json.dumps([{"id": "parity", "type": "article", "title":
                                                                  "A note on parity", "file": "files/12/note.pdf"}]))
                z.writestr("export/files/12/note.pdf", (DATA / "parity-note.pdf").read_bytes())
            form = aiohttp.FormData()
            form.add_field("file", buf.getvalue(), filename="zotero.zip")
            async with s.post(base, data=form) as r:
                res = await r.json()
            assert res["added"][0]["key"] == "parity" and res["unattached_files"] == []
            async with s.get(f"{base}/{res['added'][0]['id']}") as r:
                z_src = (await r.json())["source"]
            assert z_src["files"][0]["kind"] == "pdf"
            # patch, key conflict, annotations, delete + undo
            async with s.patch(f"{base}/{hand['id']}", json={"tags": ["à lire"], "status": "reading",
                                                             "notes": "voir §2", "collections": ["Chap. 1"]}) as r:
                src = (await r.json())["source"]
            assert src["status"] == "reading" and src["tags"] == ["à lire"]
            async with s.patch(f"{base}/{hand['id']}", json={"key": "knuth84"}) as r:
                assert r.status == 400 and (await r.json())["fields"] == ["key"]
            async with s.patch(f"{base}/{hand['id']}", json={"status": "bogus", "tags": ["x"]}) as r:
                assert r.status == 400
            async with s.post(f"{base}/{z_src['id']}/annotations", json={"page": 1, "quads": [[1, 2, 3, 4, 1, 5, 3, 6]],
                                                                         "note": "def", "color": "green"}) as r:
                assert r.status == 201
                ann = (await r.json())["annotation"]
            async with s.post(f"{base}/{z_src['id']}/annotations", json={"note": "no anchor"}) as r:
                assert r.status == 400
            async with s.patch(f"{base}/{z_src['id']}/annotations/{ann['id']}", json={"note": "définition"}) as r:
                assert (await r.json())["source"]["annotations"][0]["note"] == "définition"
            async with s.delete(f"{base}/{z_src['id']}/annotations/{ann['id']}") as r:
                assert (await r.json())["source"]["annotations"] == []
            async with s.delete(f"{base}/{hand['id']}") as r:
                undo = (await r.json())["undo"]
            async with s.get(f"{base}/{hand['id']}") as r:
                assert r.status == 404
            async with s.post(local + undo) as r:
                assert (await r.json())["source"]["key"] == hand["key"]
            # copy to the shared shelf, exports round-trip
            async with s.post(f"{base}/{hand['id']}/copy", json={"to": "global"}) as r:
                assert r.status == 201
            for fmt in ("bib", "ris", "csljson"):
                async with s.get(local + f"/api/research/shelves/{pid}/export?format={fmt}") as r:
                    text = await r.text()
                    assert r.status == 200 and "Literate" in text and "Programming" in text
                pid2 = await new_project(s, local, f"copie {fmt}")
                async with s.post(local + f"/api/research/shelves/{pid2}/sources", json={"text": text}) as r:
                    res = await r.json()
                assert len(res["added"]) == 5, (fmt, res)
            async with s.get(local + f"/api/research/projects/{pid}/keys") as r:
                keys = {k["key"]: k for k in (await r.json())["keys"]}
            assert keys["knuth84"]["label"] == "Knu84" and "parity" in keys


async def test_pdf_upload_metadata_proposal_needs_confirmation(tmp_path):
    def responder(role, messages, brain):
        first = messages[0]["content"]
        if first.startswith("Below is the first page"):
            assert "<<<SOURCE_DATA first page>>>" in first
            return '{"title": "A note on parity", "authors": ["Ada Example"], "year": 2026, "journal": "", ' \
                   '"doi": "10.9999/invented", "arxiv": ""}'
        return demo_responder(role, messages, brain)
    ctx, _t = research_ctx(tmp_path, responder)
    async with running(ctx) as (srv, local, remote):
        async with session() as s:
            pid = await new_project(s, local)
            base = local + f"/api/research/shelves/{pid}/sources"
            form = aiohttp.FormData()
            form.add_field("file", (DATA / "parity-note.pdf").read_bytes(), filename="scan.pdf")
            async with s.post(base, data=form) as r:
                src = (await r.json())["source"]
            assert src["verified"] is False and src["csl"]["title"]      # heuristics: first line of the page
            for _ in range(100):
                async with s.get(f"{base}/{src['id']}") as r:
                    src = (await r.json())["source"]
                if src.get("proposed") and src["fulltext"]["state"] != "none":
                    break
                await asyncio.sleep(0.05)
            prop = src["proposed"]
            assert prop["title"] == "A note on parity" and prop["author"][0]["family"] == "Example"
            assert "DOI" not in prop                     # an identifier that is not on the page is not kept
            assert src["verified"] is False and src["proposed_by"].startswith(("local:", "fake:"))
            async with s.patch(f"{base}/{src['id']}", json={"verified": True}) as r:
                src = (await r.json())["source"]
            assert src["verified"] and src["csl"]["title"] == "A note on parity" and src["proposed"] is None
            assert src["fulltext"]["method"] == "pdf" and src["fulltext"]["pages"] == 1
            async with s.get(f"{base}/{src['id']}/chunks?page=1") as r:
                chunks = (await r.json())["chunks"]
            assert all(c["page"] == 1 and len(c["bbox"]) == 4 for c in chunks)
            assert any(c["text"].startswith("Lemma 1.2 (Closure)") for c in chunks)


async def test_literature_search_merged_and_related(tmp_path):
    ctx, _t = research_ctx(tmp_path)
    async with running(ctx) as (srv, local, remote):
        async with session() as s:
            async with s.post(local + "/api/research/litsearch", json={"query": "Hilton-Milner theorem short proof",
                                                                     "n": 6}) as r:
                res = await r.json()
            assert set(res["providers"]) == {"arxiv", "zbmath", "crossref", "openalex", "semanticscholar"}
            assert all(p["ok"] for p in res["providers"].values())
            ids = [x["id"] for x in res["results"]]
            assert len(ids) == len(set(ids))
            top = res["results"][0]
            assert "hilton" in top["title"].lower() and len(top["providers"]) >= 2
            assert all(set(x) >= {"title", "authors", "year", "abstract", "oa", "msc", "csl", "score"}
                       for x in res["results"])
            async with s.post(local + "/api/research/litsearch/related", json={"id": "doi:10.2307/2118559",
                                                                             "how": "references", "n": 5}) as r:
                rel = (await r.json())["results"]
            assert len(rel) == 5 and all(x["title"] for x in rel)


async def test_reading_list_never_returns_an_invented_reference(tmp_path):
    def responder(role, messages, brain):
        first = messages[0]["content"]
        if first.startswith("You help a mathematician find literature"):
            return '["Hilton-Milner theorem short proof"]'
        if first.startswith("You help a mathematician build a short reading list"):
            r1 = re.search(r"R1\. (.+?) —", first).group(1)
            assert r1 and "<<<SOURCE_DATA candidate R1>>>" in first
            return ('[{"id": "R99", "why": "Smith, A fake paper (2020)."}, {"id": "R1", "why": "Main result; see '
                    'also doi:10.1234/invented and [@fake2020]."}, {"id": "Fake2020", "why": "x"}, '
                    '{"title": "Invented paper", "doi": "10.1/fake"}]')
        return demo_responder(role, messages, brain)
    ctx, _t = research_ctx(tmp_path, responder)
    ctx.settings.mode = "auto"
    async with running(ctx) as (srv, local, remote):
        async with session() as s, s.ws_connect(local + "/api/ws") as ws:
            await ws.receive_json()
            async with s.post(local + "/api/research/litsearch/reading-list",
                              json={"question": "short proofs of the Hilton-Milner theorem"}) as r:
                rid = (await r.json())["request_id"]
            evs = await ws_until(ws, lambda e: e["type"] in ("litsearch.done", "litsearch.error")
                                 and e.get("request_id") == rid)
            assert evs[-1]["type"] == "litsearch.done", evs[-1]
            res = evs[-1]["result"]
            assert len(res["items"]) == 1 and res["rejected"] == 3
            item = res["items"][0]
            assert "hilton" in item["title"].lower() and item["providers"]
            assert "invented" not in item["why"] and "fake2020" not in item["why"]
            assert any(e["type"] == "litsearch.progress" for e in evs)


async def test_grounded_answers_cite_real_passages_or_say_nothing_found(tmp_path):
    def responder(role, messages, brain):
        first = messages[0]["content"]
        if "passages below" in first or "passages ci-dessous" in first:
            m = re.search(r"\[P(\d+)\] \([^)]*\)\n(.*?)\n<<<END_SOURCE_DATA>>>", first, re.S)
            text = re.sub(r"\s+", " ", m.group(2)).strip()
            words = text.split()
            quote = " ".join(words[:8])
            return (f"La source traite de parité [P{m.group(1)}: \"{quote}\"]. "
                    f"Elle prouve aussi le grand théorème de Fermat [P{m.group(1)}: \"Fermat's last theorem holds\"].")
        if first.startswith(("Answer briefly", "Réponds brièvement")):
            return "En général, un carré pair est divisible par 4 [@hardy1979]."
        return demo_responder(role, messages, brain)
    ctx, _t = research_ctx(tmp_path, responder)
    async with running(ctx) as (srv, local, remote):
        async with session() as s, s.ws_connect(local + "/api/ws") as ws:
            await ws.receive_json()
            pid = await new_project(s, local)
            base = local + f"/api/research/shelves/{pid}/sources"
            form = aiohttp.FormData()
            form.add_field("file", (DATA / "parity-note.tar.gz").read_bytes(), filename="parity.tar.gz")
            async with s.post(base, data=form) as r:
                src = (await r.json())["source"]
            await wait_fulltext(s, f"{base}/{src['id']}")
            async with s.post(local + f"/api/research/shelves/{pid}/search", json={"query": "square even"}) as r:
                hits = (await r.json())["hits"]
            assert hits and hits[0]["source_id"] == src["id"]
            assert any(h["locator"] == "Theorem 2.1" for h in hits)
            async with s.post(local + "/api/research/ask", json={"question": "Is the square of an even number even?",
                                                                 "project": pid, "general": True}) as r:
                rid = (await r.json())["request_id"]
            evs = await ws_until(ws, lambda e: e["type"] in ("qa.done", "qa.error") and e["request_id"] == rid)
            res = evs[-1]["result"]
            assert any(e["type"] == "qa.token" for e in evs)
            s1, s2 = res["sentences"]
            assert s1["supported"] and s1["citations"][0]["source_id"] == src["id"] and s1["citations"][0]["match"] >= 0.85
            c = s1["citations"][0]
            assert c["span"][1] > c["span"][0] and c["locator"]
            assert not s2["supported"] and res["dropped"] == 1           # « Fermat » is not in the passage
            assert res["general"] and all(g["general"] for g in res["general"])
            assert "hardy1979" not in res["general"][0]["text"]
            # nothing relevant: the model is not asked
            n = len(ctx.brain.requests)
            async with s.post(local + "/api/research/ask", json={"question": "Riemann zeta zeros hypothesis",
                                                                 "project": pid}) as r:
                rid = (await r.json())["request_id"]
            evs = await ws_until(ws, lambda e: e["type"] in ("qa.done", "qa.error") and e["request_id"] == rid)
            res = evs[-1]["result"]
            assert res["status"] == "no_passages" and len(ctx.brain.requests) == n
            # summary of one source
            async with s.post(local + "/api/research/summarize", json={"shelf": pid, "source": src["id"]}) as r:
                rid = (await r.json())["request_id"]
            evs = await ws_until(ws, lambda e: e["type"] in ("qa.done", "qa.error") and e["request_id"] == rid)
            assert evs[-1]["type"] == "qa.done" and evs[-1]["result"]["kind"] == "summary"
            assert evs[-1]["result"]["sentences"][0]["supported"]
