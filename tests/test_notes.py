"""Research notes (S-G): links, backlinks, graph, versions, trash, FTS, attachments, Lean blocks, export, and live
editing by several devices (optimistic concurrency + three-way merge)."""
import asyncio
import io
import json

import pytest

from helpers import make_ctx, running, session
from madalean.research.notes import (diff_text, lean_blocks, merge3, parse_links, parse_tags, sniff,
                                     validate_image)


# ---------------------------------------------------------------- pure functions
def test_merge3_non_overlapping_overlapping_identical():
    base = "a\nb\nc\nd\n"
    assert merge3(base, "A\nb\nc\nd\n", "a\nb\nc\nD\n") == ("A\nb\nc\nD\n", [])
    assert merge3(base, "a\nB\nc\nd\n", "a\nb\nC\nd\n") == ("a\nB\nC\nd\n", [])     # adjacent lines merge
    assert merge3(base, "a\nX\nc\nd\n", "a\nX\nc\nd\n")[0] == "a\nX\nc\nd\n"           # same edit on both sides
    m, conf = merge3(base, "a\nX\nc\nd\n", "a\nY\nc\nd\n")
    assert m is None and conf[0]["mine"] == "X\n" and conf[0]["theirs"] == "Y\n" and conf[0]["base"] == "b\n"
    m, conf = merge3(base, "a\nb\nnew1\nc\nd\n", "a\nb\nnew2\nc\nd\n")                # two inserts, same place
    assert m is None and len(conf) == 1
    assert merge3(base, "a\nb\nc\nd\ne\n", "z\na\nb\nc\nd\n") == ("z\na\nb\nc\nd\ne\n", [])
    assert merge3("x", "x", "y") == ("y", []) and merge3("x", "y", "x") == ("y", [])


def test_links_tags_blocks():
    body = ("See [[Foo]] and [[Foo|the foo]], [[dossier:abc|x]], [[@knuth#p12]], [[lib:Even.add]], "
            "[[passage:ch-1]] `[[no]]`\n```lean\ntheorem t : 1 = 1 := rfl -- [[ignored]]\n```\n# Heading\n#algebra "
            "#Nat-theory and C# no")
    links = parse_links(body)
    assert [(ln.kind, ln.ref, ln.locator) for ln in links] == [
        ("note", "Foo", ""), ("dossier", "abc", ""), ("source", "knuth", "p12"), ("lib", "Even.add", ""),
        ("passage", "ch-1", "")]
    assert parse_tags(body) == ["algebra", "nat-theory"]
    bl = lean_blocks(body)
    assert len(bl) == 1 and bl[0].code.startswith("theorem t") and bl[0].start_line == 3
    assert "-x" in diff_text("x\n", "y\n") and "+y" in diff_text("x\n", "y\n")


def _png() -> bytes:
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (4, 4), (255, 0, 0)).save(buf, "PNG")
    return buf.getvalue()


def test_sniff_refuses_executable_types():
    assert sniff(_png()) == "image/png" and validate_image(_png(), "image/png")
    for bad in (b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>',
                b"<!doctype html><script>x</script>", b"GIF89a<script>", b"\x89PNG\r\n\x1a\n<html>"):
        t = sniff(bad)
        assert t is None or not validate_image(bad, t)


# ---------------------------------------------------------------- API
async def _setup(tmp_path):
    ctx = make_ctx(tmp_path)
    return ctx


async def _ws_events(url, out: list, stop: asyncio.Event):
    async with session() as s, s.ws_connect(url + "/api/ws") as ws:
        while not stop.is_set():
            try:
                m = await ws.receive(timeout=0.2)
            except asyncio.TimeoutError:
                continue
            if m.type.name == "TEXT":
                out.append(json.loads(m.data))


async def test_two_devices_edit_same_note_live(tmp_path):
    ctx = await _setup(tmp_path)
    async with running(ctx) as (_srv, L, _R):
        events, stop = [], asyncio.Event()
        watcher = asyncio.create_task(_ws_events(L, events, stop))
        async with session() as a, session() as b:
            p = (await (await a.post(L + "/api/projects", json={"title": "P"})).json())["project"]
            r = await a.post(L + "/api/notes", json={"project_id": p["id"], "title": "Shared",
                                                     "body": "line 1\nline 2\nline 3\nline 4\n"})
            assert r.status == 201
            n = (await r.json())["note"]
            nid, rev = n["id"], n["rev"]
            # both devices start from rev 1 and edit concurrently
            ra, rb = await asyncio.gather(
                a.patch(L + f"/api/notes/{nid}", json={"base_rev": rev, "body": "LINE 1\nline 2\nline 3\nline 4\n"}),
                b.patch(L + f"/api/notes/{nid}", json={"base_rev": rev, "body": "line 1\nline 2\nline 3\nLINE 4\n"}))
            ja, jb = await ra.json(), await rb.json()
            assert ra.status == 200 and rb.status == 200, (ja, jb)
            final = (await (await a.get(L + f"/api/notes/{nid}")).json())["note"]
            assert final["body"] == "LINE 1\nline 2\nline 3\nLINE 4\n" and final["rev"] == 3
            assert ja["merged"] or jb["merged"]
            # an overlapping edit from a stale revision: 409 with a clear conflict payload
            r = await b.patch(L + f"/api/notes/{nid}", json={"base_rev": rev, "body": "other 1\nline 2\nline 3\n"
                                                                                       "line 4\n"})
            assert r.status == 409
            c = await r.json()
            assert c["error"] == "conflict" and c["current"]["rev"] == 3 and c["base_rev"] == 1
            assert c["conflicts"][0]["mine"] == "other 1\n" and c["conflicts"][0]["theirs"] == "LINE 1\n"
            # title edited on both sides differently → conflict on the field
            r1 = await a.patch(L + f"/api/notes/{nid}", json={"base_rev": 3, "title": "T1"})
            r2 = await b.patch(L + f"/api/notes/{nid}", json={"base_rev": 3, "title": "T2"})
            assert r1.status == 200 and r2.status == 409 and (await r2.json())["fields"] == ["title"]
            # missing / bad base_rev
            assert (await b.patch(L + f"/api/notes/{nid}", json={"body": "x"})).status == 400
            assert (await b.patch(L + f"/api/notes/{nid}", json={"base_rev": 99, "body": "x"})).status == 400
        await asyncio.sleep(0.3)
        stop.set()
        await watcher
        upd = [e for e in events if e["type"] == "note.updated" and e["note"]["id"] == nid]
        assert [e["note"]["rev"] for e in upd] == [1, 2, 3, 4]
        assert any(e.get("merged") for e in upd)


async def test_links_backlinks_graph_after_rename_delete_restore(tmp_path):
    ctx = await _setup(tmp_path)
    async with running(ctx) as (_srv, L, _R), session() as s:
        p = (await (await s.post(L + "/api/projects", json={"title": "P"})).json())["project"]
        pid = p["id"]
        d = (await (await s.post(L + "/api/dossiers", json={"problem": "x", "project_id": pid, "start": False})).json())[
            "dossier"]

        async def mk(title, body):
            r = await s.post(L + "/api/notes", json={"project_id": pid, "title": title, "body": body})
            assert r.status == 201, await r.text()
            return (await r.json())["note"]
        b = await mk("Beta", "target note #tagb")
        a = await mk("Alpha", f"see [[Beta]] and [[beta|B]] and [[dossier:{d['id']}]] cite [[@key1#p3]]")
        assert (await s.post(L + "/api/notes", json={"project_id": pid, "title": "beta"})).status == 409
        g = await (await s.get(L + f"/api/projects/{pid}/graph")).json()
        kinds = {(e["kind"], e["source"], e["target"]) for e in g["edges"]}
        assert ("link", f"note:{a['id']}", f"note:{b['id']}") in kinds
        assert ("link", f"note:{a['id']}", f"dossier:{d['id']}") in kinds
        assert ("cites", f"note:{a['id']}", "source:key1") in kinds
        assert any(n["id"] == "source:key1" and n["missing"] for n in g["nodes"])     # S-E absent: tolerated
        bl = (await (await s.get(L + f"/api/notes/{b['id']}")).json())["backlinks"]
        assert [x["id"] for x in bl] == [a["id"]]
        assert [n["id"] for n in (await (await s.get(L + f"/api/dossiers/{d['id']}/notes")).json())["notes"]] == [a["id"]]
        # rename: links in other notes are rewritten (new revision), backlinks + graph still right
        r = await s.patch(L + f"/api/notes/{b['id']}", json={"base_rev": 1, "title": "Gamma"})
        assert r.status == 200 and (await r.json())["renamed_links_in"] == [a["id"]]
        a2 = (await (await s.get(L + f"/api/notes/{a['id']}")).json())["note"]
        assert "[[Gamma]]" in a2["body"] and "[[Gamma|B]]" in a2["body"] and a2["rev"] == 2
        bl = (await (await s.get(L + f"/api/notes/{b['id']}")).json())["backlinks"]
        assert [x["id"] for x in bl] == [a["id"]]
        # delete: the link becomes dangling (missing node), the note goes to the trash
        assert (await s.delete(L + f"/api/notes/{b['id']}")).status == 200
        g = await (await s.get(L + f"/api/projects/{pid}/graph")).json()
        assert not any(e["target"] == f"note:{b['id']}" for e in g["edges"])
        assert any(n.get("missing") and n["ref"] == "Gamma" for n in g["nodes"])
        trash = (await (await s.get(L + f"/api/notes?project={pid}&trash=1")).json())["notes"]
        assert [n["id"] for n in trash] == [b["id"]]
        assert (await (await s.get(L + "/api/notes/search?q=target")).json())["results"] == []
        # restore: everything comes back
        assert (await s.post(L + f"/api/notes/{b['id']}/restore")).status == 200
        g = await (await s.get(L + f"/api/projects/{pid}/graph")).json()
        assert ("link", f"note:{a['id']}", f"note:{b['id']}") in {(e["kind"], e["source"], e["target"])
                                                                  for e in g["edges"]}
        # filters
        g = await (await s.get(L + f"/api/projects/{pid}/graph?kinds=note&edges=link&orphans=0")).json()
        assert {n["kind"] for n in g["nodes"]} == {"note"}
        g = await (await s.get(L + f"/api/projects/{pid}/graph?tag=tagb")).json()
        assert [n["ref"] for n in g["nodes"] if n["kind"] == "note" and not n.get("missing")] == [b["id"]]
        tags = (await (await s.get(L + f"/api/projects/{pid}/tags")).json())["tags"]
        assert {"tag": "tagb", "count": 1} in tags


async def test_versions_diff_restore_search_daily_export(tmp_path):
    ctx = await _setup(tmp_path)
    async with running(ctx) as (_srv, L, _R), session() as s:
        pid = (await (await s.post(L + "/api/projects", json={"title": "Carnet"})).json())["project"]["id"]
        n = (await (await s.post(L + "/api/notes", json={"project_id": pid, "title": "N", "body": "v1 théorème\n"})).json())["note"]
        await s.patch(L + f"/api/notes/{n['id']}", json={"base_rev": 1, "body": "v2 lemme de Zorn\n"})
        vs = (await (await s.get(L + f"/api/notes/{n['id']}/versions")).json())["versions"]
        assert [v["rev"] for v in vs] == [2, 1]
        diff = (await (await s.get(L + f"/api/notes/{n['id']}/diff?from=1&to=2")).json())["diff"]
        assert "-v1" in diff and "+v2" in diff
        r = await s.post(L + f"/api/notes/{n['id']}/versions/1/restore", json={"base_rev": 2})
        assert (await r.json())["note"]["body"] == "v1 théorème\n" and (await r.json())["note"]["rev"] == 3
        res = (await (await s.get(L + "/api/notes/search?q=theoreme")).json())["results"]
        assert [x["id"] for x in res] == [n["id"]] and "[" in res[0]["snippet"]
        assert (await (await s.get(L + "/api/notes/search?q=%22%29%28*")).json())["results"] == []   # no FTS crash
        r = await s.post(L + f"/api/projects/{pid}/notes/daily", json={"date": "2026-11-21"})
        assert r.status == 201 and "2026-11-21" in (await r.json())["note"]["title"]
        r = await s.post(L + f"/api/projects/{pid}/notes/daily", json={"date": "2026-11-21"})
        assert r.status == 200 and not (await r.json())["created"]
        r = await s.get(L + f"/api/notes/{n['id']}/export?format=md")
        assert r.status == 200 and "# N" in await r.text()
        r = await s.get(L + f"/api/projects/{pid}/notebook/export?format=html")
        assert r.status == 200 and "<html" in await r.text()
        assert (await s.get(L + f"/api/notes/{n['id']}/export?format=exe")).status == 400


async def test_note_pdf_export_real_tex(tmp_path):
    import shutil
    if not shutil.which("xelatex"):
        pytest.skip("no TeX")
    ctx = await _setup(tmp_path)
    async with running(ctx) as (_srv, L, _R), session() as s:
        pid = (await (await s.post(L + "/api/projects", json={"title": "P"})).json())["project"]["id"]
        n = (await (await s.post(L + "/api/notes", json={"project_id": pid, "title": "Euler", "body":
                                                       "## Idée\n\n$n^2+n+41$ et [[Autre]].\n\n```lean\ntheorem t (n : ℕ) : n + 0 = n := by simp\n```\n"})).json())["note"]
        r = await s.get(L + f"/api/notes/{n['id']}/export?format=pdf")
        data = await r.read()
        assert r.status == 200 and (data[:5] == b"%PDF-" or r.headers["X-Madalean-Fallback"] == "html")


async def test_attachments_safe_types_and_traversal(tmp_path):
    import aiohttp
    ctx = await _setup(tmp_path)
    async with running(ctx) as (_srv, L, _R), session() as s:
        pid = (await (await s.post(L + "/api/projects", json={"title": "P"})).json())["project"]["id"]
        n = (await (await s.post(L + "/api/notes", json={"project_id": pid, "title": "N"})).json())["note"]

        async def up(name, data, ctype="application/octet-stream"):
            fd = aiohttp.FormData()
            fd.add_field("file", data, filename=name, content_type=ctype)
            return await s.post(L + f"/api/notes/{n['id']}/attachments", data=fd)
        r = await up("../../evil.svg.png", _png(), "image/svg+xml")
        assert r.status == 201
        a = (await r.json())["attachment"]
        assert a["mime"] == "image/png" and "/" not in a["name"] and a["name"].endswith(".png")
        g = await s.get(L + a["url"])
        assert g.status == 200 and g.headers["Content-Type"] == "image/png"
        assert g.headers["X-Content-Type-Options"] == "nosniff" and "sandbox" in g.headers["Content-Security-Policy"]
        for name, data in (("x.svg", b'<svg xmlns="http://www.w3.org/2000/svg" onload="alert(1)"/>'),
                           ("x.html", b"<html><script>alert(1)</script></html>"), ("x.png", b"\x89PNG\r\n\x1a\nnope")):
            assert (await up(name, data, "image/png")).status == 415
        for bad in ("../../config/keys.json", "..%2F..%2Fkeys.json", "a-0123456789abcdef/../x", "%2e%2e",
                    "a-zzzzzzzzzzzzzzzz"):
            assert (await s.get(L + "/api/attachments/" + bad)).status == 404
        # delete is undoable
        assert (await s.delete(L + a["url"])).status == 200 and (await s.get(L + a["url"])).status == 404
        assert (await s.post(L + a["url"] + "/restore")).status == 200 and (await s.get(L + a["url"])).status == 200
        for bad in ("..", "a/b", "x" * 100):
            assert (await s.get(L + f"/api/notes/{bad}")).status in (400, 404)


async def test_lean_blocks_checked_and_turned_into_dossier(tmp_path):
    ctx = await _setup(tmp_path)            # fake Lean: rejects `no_such`, flags sorry
    async with running(ctx) as (_srv, L, _R), session() as s:
        pid = (await (await s.post(L + "/api/projects", json={"title": "P"})).json())["project"]["id"]
        body = ("Idée.\n\n```lean\ntheorem ok1 (a b : ℕ) (ha : Even a) (hb : Even b) : Even (a + b) := by sorry\n```\n\n"
                "Second paragraph: the square of an even number is even.\n\n```lean\nexample : 1 = 1 := no_such\n```\n")
        n = (await (await s.post(L + "/api/notes", json={"project_id": pid, "title": "N", "body": body})).json())["note"]
        r = await s.post(L + f"/api/notes/{n['id']}/lean-check")
        res = (await r.json())["results"]
        assert r.status == 200 and len(res) == 2
        assert res[0]["statement_ok"] and res[0]["has_sorry"] and not res[0]["ok"]
        assert not res[1]["statement_ok"] and res[1]["errors"][0]["note_line"] >= 1
        stored = (await (await s.get(L + f"/api/notes/{n['id']}")).json())["note"]["lean_blocks"]
        assert stored[0]["result"]["hash"] == stored[0]["hash"]
        r = await s.post(L + f"/api/notes/{n['id']}/to-dossier", json={"block": 0})
        assert r.status == 201
        j = await r.json()
        assert j["dossier"]["project_id"] == pid and j["dossier"]["current"]["statement"]
        assert f"[[dossier:{j['dossier']['id']}" in j["note"]["body"] and j["note"]["rev"] == 2
        r = await s.post(L + f"/api/notes/{n['id']}/to-dossier", json={"paragraph": 1, "kind": "conjecture"})
        assert r.status == 201 and (await r.json())["dossier"]["kind"] == "conjecture"


async def test_note_blocks_real_lean(tmp_path, ws):
    ctx = make_ctx(tmp_path, ws=ws)
    async with running(ctx) as (_srv, L, _R), session() as s:
        pid = (await (await s.post(L + "/api/projects", json={"title": "P", "workspace": ws.key})).json())["project"]["id"]
        body = "```lean\ntheorem t1 (n : ℕ) : n + 0 = n := by simp\n```\n\n```lean\ntheorem t2 : (2 : ℕ) + 2 = 5 := by norm_num\n```\n"
        n = (await (await s.post(L + "/api/notes", json={"project_id": pid, "title": "N", "body": body})).json())["note"]
        res = (await (await s.post(L + f"/api/notes/{n['id']}/lean-check")).json())["results"]
        assert res[0]["ok"] is True and res[1]["ok"] is False and res[1]["errors"]
        assert res[1]["errors"][0]["line"] == 1 and res[1]["errors"][0]["note_line"] == 6


async def test_research_routes_need_token_remotely(tmp_path):
    ctx = await _setup(tmp_path)
    async with running(ctx) as (srv, _L, Rm), session() as s:
        routes = [(r.method, r.resource.canonical) for r in srv.app.router.routes()
                  if r.resource is not None and any(x in r.resource.canonical for x in
                                                    ("/notes", "/conjectures", "/plan", "/learn", "/attachments",
                                                     "/experiments", "/recheck", "/workspaces", "/graph"))]
        assert len(routes) > 60
        for method, path in routes:
            url = Rm + re.sub(r"\{[^}]+\}", "x1", path)
            r = await s.request(method, url, json={})
            assert r.status == 401, (method, path, r.status)


import re  # noqa: E402
