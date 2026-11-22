"""REST API + WebSocket bus end to end over HTTP (fake brain, fake Lean unless stated)."""
from __future__ import annotations

import asyncio
import json

import aiohttp

from madalean.server import bus as busmod
from helpers import make_ctx, running, session, wait_idle

PROBLEM = "Montrer que la somme de deux entiers pairs est paire."


async def ws_events(ws, until, timeout=30.0) -> list[dict]:
    out = []
    loop = asyncio.get_running_loop()
    end = loop.time() + timeout
    while loop.time() < end:
        try:
            m = await asyncio.wait_for(ws.receive(), end - loop.time())
        except asyncio.TimeoutError:
            break
        if m.type != aiohttp.WSMsgType.TEXT:
            break
        ev = json.loads(m.data)
        out.append(ev)
        if until(ev):
            break
    return out


async def test_projects_dossiers_full_flow_and_events(tmp_path):
    ctx = make_ctx(tmp_path, delay=0.001)
    async with running(ctx) as (srv, local, remote):
        async with session() as s, s.ws_connect(local + "/api/ws") as ws:
            hello = await ws.receive_json()
            assert hello["type"] == "hello" and hello["local"]
            async with s.post(local + "/api/projects", json={"title": "Chapitre 1", "description": "parité"}) as r:
                assert r.status == 201
                pid = (await r.json())["project"]["id"]
            assert (tmp_path / "config" / "projects" / pid / "project.json").exists()
            async with s.patch(local + f"/api/projects/{pid}", json={"title": "Chapitre 1 bis", "bogus": 1}) as r:
                assert r.status == 400
            async with s.patch(local + f"/api/projects/{pid}", json={"title": "Chapitre 1 bis"}) as r:
                assert (await r.json())["project"]["title"] == "Chapitre 1 bis"
            async with s.post(local + "/api/dossiers", json={"problem": PROBLEM, "project_id": pid}) as r:
                assert r.status == 201
                data = await r.json()
            did, jid = data["dossier"]["id"], data["job"]["id"]
            evs = await ws_events(ws, lambda e: e["type"] == "job.updated" and e["job"]["id"] == jid
                                  and e["job"]["state"] in ("done", "failed"))
            types = {e["type"] for e in evs}
            assert {"job.updated", "job.token", "dossier.updated"} <= types
            seqs = [e["seq"] for e in evs]
            assert seqs == sorted(seqs) and len(set(seqs)) == len(seqs)
            assert evs[-1]["job"]["state"] == "done"
            toks = [e for e in evs if e["type"] == "job.token"]
            assert {"job_id", "stage", "attempt", "text", "kind"} <= set(toks[0])
            async with s.get(local + f"/api/dossiers/{did}") as r:
                d = (await r.json())["dossier"]
            assert d["status"] == "proved" and d["current"]["proof_is_current"] and d["project_id"] == pid
            assert d["current"]["statement_notes"] and d["current"]["informal_proof"]
            async with s.get(local + f"/api/projects/{pid}") as r:
                assert [x["id"] for x in (await r.json())["dossiers"]] == [did]
            # follow-up message
            async with s.post(local + f"/api/dossiers/{did}/message", json={"text": "une preuve plus courte"}) as r:
                assert r.status == 202
                assert (await r.json())["stage"] == "auto"
            async with s.post(local + f"/api/dossiers/{did}/message", json={"text": "encore"}) as r:
                assert r.status == 409 and (await r.json())["error"] == "busy"
            await wait_idle(ctx)
            async with s.get(local + f"/api/dossiers/{did}/jobs") as r:
                jobs = (await r.json())["jobs"]
            assert len(jobs) == 2 and all(j["state"] == "done" for j in jobs)
            # versions
            async with s.post(local + f"/api/dossiers/{did}/versions/proof/0/restore") as r:
                assert r.status == 200 and (await r.json())["dossier"]["cur_proof"] == 0
            async with s.post(local + f"/api/dossiers/{did}/versions/proof/9/restore") as r:
                assert r.status == 404
            # run / stop
            async with s.post(local + f"/api/dossiers/{did}/run", json={"plan": ["bogus"]}) as r:
                assert r.status == 400
            async with s.post(local + f"/api/dossiers/{did}/run", json={"plan": ["proof", "explanation"]}) as r:
                assert r.status == 202
            async with s.post(local + f"/api/dossiers/{did}/stop") as r:
                assert (await r.json())["stopped"] is True
            # library
            async with s.get(local + "/api/library") as r:
                entries = (await r.json())["entries"]
            assert entries and entries[0]["dossier"] == did
            async with s.delete(local + f"/api/library/{entries[0]['name']}") as r:
                removed = (await r.json())["removed"]
            async with s.post(local + "/api/library/restore", json={"entry": removed}) as r:
                assert r.status == 200
            async with s.get(local + "/api/library/export") as r:
                assert removed["name"] in await r.text()
            # delete + undo
            async with s.delete(local + f"/api/dossiers/{did}") as r:
                assert r.status == 200
            async with s.get(local + f"/api/dossiers/{did}") as r:
                assert r.status == 404
            async with s.post(local + f"/api/dossiers/{did}/restore") as r:
                assert r.status == 200
            async with s.delete(local + f"/api/projects/{pid}") as r:
                assert r.status == 200
            async with s.post(local + f"/api/projects/{pid}/restore") as r:
                assert r.status == 200
            async with s.get(local + "/api/state") as r:
                st = await r.json()
            for k in ("settings", "projects", "dossiers", "jobs", "models", "system", "library", "updates", "jupyter"):
                assert k in st
            async with s.get(local + "/api/nope") as r:
                assert r.status == 404 and (await r.json())["error"] == "not_found"


async def test_settings_keys_models_system(tmp_path):
    ctx = make_ctx(tmp_path)
    async with running(ctx) as (srv, local, remote):
        async with session() as s:
            async with s.patch(local + "/api/settings", json={"mode": "bogus"}) as r:
                assert r.status == 400
            async with s.patch(local + "/api/settings", json={"prove_attempts": 0}) as r:
                assert r.status == 400
            async with s.patch(local + "/api/settings", json={"language": "en", "mode": "auto",
                                                              "sampling": {"temperature": 0.7}}) as r:
                st = (await r.json())["settings"]
            assert st["language"] == "en" and st["mode"] == "auto" and st["sampling"]["temperature"] == 0.7
            assert st["sampling"]["top_p"] == 0.95
            saved = json.loads((tmp_path / "config" / "settings.json").read_text())
            assert saved["mode"] == "auto"
            async with s.post(local + "/api/dossiers/x/message", json={}) as r:
                assert r.status == 404
            async with s.post(local + "/api/models/keys", json={"provider": "anthropic", "key": "sk-ant-SECRET123456"}) as r:
                assert (await r.json()) == {"provider": "anthropic", "set": True, "backend": "file", "unpaused": 0,
                                            "testing": True}
            f = tmp_path / "config" / "keys.json"
            assert oct(f.stat().st_mode)[-3:] == "600"
            for path in ("/api/models", "/api/state", "/api/settings", "/api/system"):
                async with s.get(local + path) as r:
                    assert "SECRET123456" not in await r.text(), path
            async with s.get(local + "/api/models") as r:
                m = await r.json()
            assert m["keys"] == {"anthropic": True} and "prove" in m["roles"]
            async with s.delete(local + "/api/models/keys/anthropic") as r:
                assert (await r.json())["set"] is False
            log = (tmp_path / "config" / "logs")
            assert not any("SECRET123456" in p.read_text() for p in log.glob("*")) if log.exists() else True
            async with s.get(local + "/api/system") as r:
                sysd = await r.json()
            assert {c["id"] for c in sysd["checks"]} >= {"workspace", "tex", "jupyter", "disk", "brain"}
            assert sysd["slots"]["gpu"]["capacity"] == 1
            async with s.post(local + "/api/system/repair/bogus") as r:
                assert r.status == 404
            async with s.post(local + "/api/system/repair/workspaces") as r:
                assert r.status == 200
            async with s.get(local + "/api/updates") as r:
                assert "candidates" in await r.json()
            async with s.post(local + "/api/updates/install", json={"key": "nothing"}) as r:
                assert r.status == 404
    from madalean import i18n
    i18n.set_language("fr")


async def test_import_tex_check_statement_and_assistant(tmp_path):
    ctx = make_ctx(tmp_path)
    async with running(ctx) as (srv, local, remote):
        async with session() as s, s.ws_connect(local + "/api/ws") as ws:
            await ws.receive_json()
            form = aiohttp.FormData()
            form.add_field("file", b"\\begin{theorem}[Euclide]Il y a une infinit\xc3\xa9 de nombres premiers.\\end{theorem}",
                           filename="a.tex", content_type="application/x-tex")
            async with s.post(local + "/api/import/tex", data=form) as r:
                st = (await r.json())["statements"]
            assert st[0]["title"].endswith("Euclide") and "infinité" in st[0]["body"]
            async with s.post(local + "/api/import/tex", json={"tex": ""}) as r:
                assert r.status == 400
            async with s.post(local + "/api/dossiers", json={"statement": "lemma foo : 1 = 1 := by sorry",
                                                             "start": False}) as r:
                d = (await r.json())["dossier"]
            assert f"theorem {d['theorem']}" in d["current"]["statement"]
            async with s.post(local + f"/api/dossiers/{d['id']}/statement", json={"code": "nothing"}) as r:
                assert r.status == 400
            async with s.post(local + f"/api/dossiers/{d['id']}/statement",
                              json={"code": f"theorem {d['theorem']} : 2 = 2 := by sorry"}) as r:
                j = await r.json()
            assert j["check"]["statement_ok"] and not j["check"]["ok"] and len(j["dossier"]["statements"]) == 2
            assert j["dossier"]["statements"][-1]["ok"]
            async with s.post(local + "/api/assistant", json={"messages": [{"role": "user", "content": "simp ?"}],
                                                              "context": {"cell": "x = 1", "notebook": "a.ipynb"}}) as r:
                rid = (await r.json())["request_id"]
            evs = await ws_events(ws, lambda e: e["type"] in ("assistant.done", "assistant.error"))
            done = evs[-1]
            assert done["type"] == "assistant.done" and done["request_id"] == rid and "simp" in done["text"]
            assert any(e["type"] == "assistant.token" for e in evs) and done["model"]
            sent = ctx.brain.requests[-1]["messages"]
            assert sent[0]["role"] == "system" and "x = 1" in sent[0]["content"]


async def test_free_check_and_export_with_real_lean(tmp_path, ws):
    ctx = make_ctx(tmp_path, ws=ws)
    async with running(ctx) as (srv, local, remote):
        async with session() as s:
            ok_code = "import Mathlib\n\ntheorem t (a b : ℕ) (h : a = b) : b = a := by\n  exact h.symm\n"
            async with s.post(local + "/api/check", json={"code": ok_code, "strict": True}) as r:
                c = (await r.json())["check"]
            assert c["ok"] and c["axioms"] is not None
            async with s.post(local + "/api/check", json={"code": ok_code.replace("h.symm", "h"), "strict": True}) as r:
                c = (await r.json())["check"]
            assert not c["ok"] and c["errors"]
            async with s.post(local + "/api/dossiers", json={"problem": PROBLEM}) as r:
                did = (await r.json())["dossier"]["id"]
            await wait_idle(ctx)
            async with s.post(local + f"/api/dossiers/{did}/check", json={"what": "proof"}) as r:
                assert (await r.json())["check"]["ok"]
            sizes = {}
            for fmt in ("pdf", "tex", "lean", "md", "zip", "html"):
                async with s.get(local + f"/api/dossiers/{did}/export?format={fmt}") as r:
                    assert r.status == 200, fmt
                    body = await r.read()
                    sizes[fmt] = len(body)
                    assert "attachment" in r.headers["Content-Disposition"]
                    if fmt == "pdf":
                        assert body[:4] == b"%PDF" and r.headers["X-Madalean-Fallback"] == ""
            assert all(v > 100 for v in sizes.values())


async def test_websocket_resume_and_resync(tmp_path, monkeypatch):
    ctx = make_ctx(tmp_path)
    async with running(ctx) as (srv, local, remote):
        async with session() as s:
            async with s.ws_connect(local + "/api/ws") as ws:
                hello = await ws.receive_json()
            start = hello["seq"]
            for i in range(5):
                ctx.publish("toast", {"text": f"t{i}"})
            async with s.ws_connect(local + "/api/ws") as ws:
                h2 = await ws.receive_json()
                await ws.send_json({"type": "resume", "seq": start, "boot": h2["boot"]})
                evs = [await ws.receive_json() for _i in range(5)]
                assert [e["text"] for e in evs] == [f"t{i}" for i in range(5)]
                assert [e["seq"] for e in evs] == list(range(start + 1, start + 6))
                ctx.publish("toast", {"text": "live"})
                live = await ws.receive_json()
                assert live["text"] == "live" and live["seq"] == start + 6      # no duplicate after the replay
                await ws.send_json({"type": "ping", "t": 1})
                assert (await ws.receive_json())["type"] == "pong"
            # too old (left the ring buffer) or another boot: resync
            small = busmod.EventBus(ring=3)
            for i in range(10):
                small.publish("toast", {"i": i})
            assert small.since(2) is None and [e["i"] for e in small.since(8)] == [8, 9] and small.since(10) == []
            async with s.ws_connect(local + "/api/ws") as ws:
                await ws.receive_json()
                await ws.send_json({"type": "resume", "seq": 1, "boot": 12345})
                assert (await ws.receive_json())["type"] == "resync"


async def test_split_endpoint_creates_children(tmp_path):
    ctx = make_ctx(tmp_path)
    ctx.settings.prove_attempts = 1
    async with running(ctx) as (srv, local, remote):
        async with session() as s:
            async with s.post(local + "/api/dossiers", json={
                    "statement": "theorem big (a b : ℕ) (ha : Even a) (hb : Even b) : Even (a + b + 0) := by sorry",
                    "start": False}) as r:
                pid = (await r.json())["dossier"]["id"]
            async with s.post(local + f"/api/dossiers/{pid}/split", json={}) as r:
                assert r.status == 201
                out = await r.json()
            kids = out["children"]
            assert len(kids) == 2 and all(k["parent_id"] == pid and k["kind"] == "lemma" for k in kids)
            await wait_idle(ctx)
            await asyncio.sleep(0.2)
            await wait_idle(ctx)
            async with s.get(local + f"/api/dossiers/{pid}") as r:
                d = await r.json()
            assert len(d["children"]) == 2
            assert any("lemmes" in e["text"].lower() for e in d["dossier"]["events"])


async def test_plugins_can_add_routes_and_events(tmp_path):
    from aiohttp import web

    from madalean.server.app import make_app
    from madalean.server.common import CTX

    def plugin(app, ctx):
        async def h(request):
            request.app[CTX].publish("bib.updated", {"n": 1})
            return web.json_response({"ok": True})
        app.router.add_get("/api/bib/ping", h)
    ctx = make_ctx(tmp_path)
    app = make_app(ctx, extra_plugins=[plugin])
    assert any(getattr(r.resource, "canonical", "") == "/api/bib/ping" for r in app.router.routes())


async def test_extra_fields_round_trip_and_migration(tmp_path):
    """1.x data copied (never modified), unknown fields kept, research fields tolerated."""
    import shutil
    legacy = tmp_path / "legacy"
    (legacy / "dossiers").mkdir(parents=True)
    old = {"id": "20261001-120000-abcd", "title": "Vieux", "problem": "p", "theorem": "vieux_abcd",
           "events": [{"kind": "user", "text": "p", "t": 1.0, "ref": None, "stage": "auto"}],
           "statements": [{"code": "theorem vieux_abcd : True := by sorry", "t": 1.0, "source": "ai", "ok": True,
                           "parent": None, "note": ""}], "cur_statement": 0, "cur_proof": -1, "cur_explanation": -1,
           "proofs": [], "explanations": [], "lemmas_used": [], "future_field": {"x": 1}}
    (legacy / "dossiers" / "20261001-120000-abcd.json").write_text(json.dumps(old))
    (legacy / "settings.json").write_text(json.dumps({"language": "en", "offline": False, "prove_attempts": 5,
                                                     "workspace": "lean-prover49"}))
    (legacy / "library.json").write_text("[]")
    before = {p: p.read_bytes() for p in legacy.rglob("*") if p.is_file()}
    ctx = make_ctx(tmp_path, legacy_dir=legacy)
    await ctx.start()
    assert ctx.migration["dossiers"] == 1 and ctx.migration["settings"] and ctx.migration["library"]
    assert ctx.settings.language == "en" and ctx.settings.mode == "auto" and ctx.settings.prove_attempts == 5
    d = ctx.repo.get("20261001-120000-abcd")
    assert d.project_id and ctx.projects.get(d.project_id).title == "Lean AI Station 1.x"
    assert d.status == "draft" and d.kind == "theorem" and d.extra == {"future_field": {"x": 1}}
    d.refs = [{"key": "euclid", "locator": "I.20"}]
    d.source = {"paper_key": "euclid", "locator": "IX.20", "original_text": "..."}
    d.uses = ["other"]
    await ctx.repo.save(d)
    saved = json.loads((tmp_path / "config" / "dossiers" / f"{d.id}.json").read_text())
    assert saved["future_field"] == {"x": 1} and saved["refs"][0]["key"] == "euclid" and "extra" not in saved
    assert {p: p.read_bytes() for p in legacy.rglob("*") if p.is_file()} == before       # never modified
    from madalean.migrate import migrate
    assert migrate(legacy, ctx.paths) == {"skipped": "already"}
    pj = tmp_path / "config" / "projects" / d.project_id / "project.json"
    data = json.loads(pj.read_text())
    data["blueprint"] = {"nodes": 3}
    pj.write_text(json.dumps(data))
    from madalean.projects import ProjectStore
    st = ProjectStore(tmp_path / "config" / "projects")
    p = st.load(d.project_id)
    st.save(p)
    assert json.loads(pj.read_text())["blueprint"] == {"nodes": 3}
    await ctx.stop()
    from madalean import i18n
    i18n.set_language("fr")
    shutil.rmtree(legacy)
