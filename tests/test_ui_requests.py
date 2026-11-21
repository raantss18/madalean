"""Server side of docs/UI.md §8: manual versions, router « why », real key test, declaration lookup, model keys
never reprs, remote_url for pairing, examples, CSP header, assistant ordering, replay of streamed text."""
from __future__ import annotations

import asyncio
import json
import sys
import types

import aiohttp

from madalean.brain.api import ModelRef
from madalean.server.routes_work import create_dossier
from madalean.streams import StreamStore
from helpers import make_ctx, running, session, started, wait_idle

STMT = "theorem t (a b : ℕ) (ha : Even a) (hb : Even b) : Even (a + b) := by sorry"
GOOD = "theorem t (a b : ℕ) (ha : Even a) (hb : Even b) : Even (a + b) := by\n  exact Even.add ha hb"


async def test_manual_versions_fake_lean(tmp_path):
    ctx = make_ctx(tmp_path)
    async with running(ctx) as (srv, local, remote):
        async with session() as s:
            async with s.post(local + "/api/dossiers", json={"statement": STMT, "start": False}) as r:
                d = (await r.json())["dossier"]
            did, name = d["id"], d["theorem"]
            u = local + f"/api/dossiers/{did}/versions"
            async with s.post(u + "/proof", json={"code": GOOD.replace("theorem t", f"theorem {name}")}) as r:
                j = await r.json()
            dd = j["dossier"]
            assert j["check"]["ok"] and dd["current"]["proof_is_current"] and dd["status"] == "proved"
            v = dd["proofs"][-1]
            assert v["source"] == "user" and v["ok"] and v["meta"]["manual"] and v["model"] == ""
            assert dd["events"][-1]["kind"] == "proof" and "à la main" in dd["events"][-1]["text"]
            # a proof Lean refuses is kept but never counts as proven
            async with s.post(u + "/proof", json={"code": GOOD.replace("Even.add ha hb", "no_such ha hb")}) as r:
                j = await r.json()
            dd = j["dossier"]
            assert not j["check"]["ok"] and not dd["current"]["proof_is_current"] and dd["status"] == "draft"
            assert dd["proofs"][-1]["ok"] is False and dd["events"][-1]["kind"] == "error"
            # unchecked = unverified
            async with s.post(u + "/proof", json={"code": GOOD, "check": False}) as r:
                j = await r.json()
            assert j["check"] is None and not j["dossier"]["current"]["proof_is_current"]
            # the signature is pinned to the dossier's statement: a weaker theorem is not accepted as such
            async with s.post(u + "/proof", json={"code": "theorem t : True := by\n  trivial"}) as r:
                j = await r.json()
            assert f"theorem {name} (a b : ℕ)" in j["dossier"]["current"]["proof"]
            async with s.post(local + f"/api/dossiers/{did}/versions/proof/0/restore") as r:
                assert (await r.json())["dossier"]["current"]["proof_is_current"]
            for kind, field in (("explanation", "explanation"), ("informal", "informal_proof"),
                                ("notes", "statement_notes")):
                async with s.post(u + f"/{kind}", json={"code": f"Mon texte {kind}"}) as r:
                    dd = (await r.json())["dossier"]
                assert dd["current"][field] == f"Mon texte {kind}"
            assert dd["explanations"][-1]["source"] == "user" and dd["informal_proofs"][-1]["source"] == "user"
            async with s.post(u + "/statement", json={"code": "x"}) as r:
                assert r.status == 400
            async with s.post(u + "/proof", json={"code": ""}) as r:
                assert r.status == 400
            # the AI never rewrites a user version: an explanation run adds a new version, the user's stays
            ctx.orchestrator.submit(did, [{"stage": "explanation", "request": "plus court"}])
            await wait_idle(ctx)
            dd = ctx.repo.get(did)
            assert dd.explanations[-2].code == "Mon texte explanation" and dd.explanations[-2].source == "user"
            assert dd.explanations[-1].source == "ai" and dd.informal_proof == "Mon texte informal"


async def test_manual_proof_with_real_lean(tmp_path, ws):
    ctx = make_ctx(tmp_path, ws=ws)
    async with running(ctx) as (srv, local, remote):
        async with session() as s:
            async with s.post(local + "/api/dossiers", json={"statement": STMT, "start": False}) as r:
                did = (await r.json())["dossier"]["id"]
            async with s.post(local + f"/api/dossiers/{did}/versions/proof", json={"code": GOOD}) as r:
                j = await r.json()
            assert j["check"]["ok"] and j["dossier"]["proofs"][-1]["meta"]["axioms"] is not None
            async with s.post(local + f"/api/dossiers/{did}/versions/proof",
                              json={"code": GOOD.replace("Even.add ha hb", "ha")}) as r:
                j = await r.json()
            assert not j["check"]["ok"] and j["check"]["errors"] and not j["dossier"]["current"]["proof_is_current"]


async def test_models_why_and_real_key_test(tmp_path):
    ctx = make_ctx(tmp_path)
    ctx.brain.explain = lambda role, mode: [{"model": c.key, "name": c.name, "score": 0.9, "why": "best for " + role}
                                            for c in ctx.brain.candidates(role, mode)]
    async with running(ctx) as (srv, local, remote):
        async with session() as s:
            async with s.get(local + "/api/models") as r:
                m = await r.json()
            c = m["roles"]["prove"]["candidates"][0]
            assert c["why"] == "best for prove" and c["score"] == 0.9
            ctx.settings.mode = "local"
            async with s.post(local + "/api/models/test", json={"provider": "fake"}) as r:
                assert (await r.json())["reason"] == "local_mode"
            async with s.patch(local + "/api/settings", json={"mode": "online"}) as r:
                assert r.status == 200
            async with s.post(local + "/api/models/keys", json={"provider": "fake", "key": "sk-SECRET-KEY-123456"}):
                pass
            async with s.post(local + "/api/models/test", json={"provider": "fake"}) as r:
                text = await r.text()
                t = json.loads(text)
            assert t["ok"] is True and t["model"] == "fake:fake-explain" and t["models"] >= 1
            assert t["latency_s"] >= 0 and "SECRET" not in text
            assert ctx.brain.requests[-1]["max_tokens"] == 16
            async with s.post(local + "/api/models/test", json={"provider": "anthropic"}) as r:
                t = await r.json()
            assert t["ok"] is False and t["reason"] == "no_model"


async def test_declaration_lookup(tmp_path):
    ctx = make_ctx(tmp_path)
    async with running(ctx) as (srv, local, remote):
        async with session() as s:
            async with s.get(local + "/api/declarations/demo/Even.add") as r:
                d = await r.json()
            assert d["status"] == "ok" and d["declaration"]["module"].startswith("Mathlib")
            async with s.get(local + "/api/lean/declaration", params={"name": "Nat.nope", "workspace": "user:/x/y"}) as r:
                d = await r.json()
            assert d["status"] == "unknown" and d["declaration"] is None and d["workspace"] == "user:/x/y"
            async with s.get(local + "/api/declarations/search", params={"q": "even add"}) as r:
                d = await r.json()
            assert d["status"] == "ok" and d["results"][0]["name"] == "Even.add"
            async with s.get(local + "/api/lean/search") as r:
                assert r.status == 400
            ctx.retriever.ready = lambda k: False
            ctx.retriever.start = lambda k: None
            async with s.get(local + "/api/declarations/demo/Even.add") as r:
                assert (await r.json())["status"] == "indexing"


async def test_agent_model_is_a_key_not_a_repr(tmp_path, monkeypatch):
    from madalean.pipeline import runner
    from madalean.pipeline.runner import model_key
    assert model_key(ModelRef("fake", "fake-prove")) == "fake:fake-prove" and model_key("a:b") == "a:b"

    async def agent(brain, retriever, *, statement, check, **kw):
        return {"code": statement.replace(":= by sorry", ":= by\n  exact Even.add ha hb"),
                "model": ModelRef("fake", "fake-prove"), "steps": 1, "transcript": []}
    monkeypatch.setattr(runner, "_agent_fn", lambda: agent)
    ctx = await started(make_ctx(tmp_path))
    ctx.settings.mode = "online"
    d, j = await create_dossier(ctx, {"statement": STMT})
    await wait_idle(ctx)
    models = [a.model for a in j.attempts] + [v.model for v in d.proofs] + [e.model for e in d.events]
    assert all("ModelRef" not in m and (m == "" or ":" in m) for m in models), models
    assert "fake:fake-prove" in models
    await ctx.stop()


async def test_pairing_remote_url_examples_and_csp(tmp_path, monkeypatch):
    static = tmp_path / "static"
    static.mkdir()
    (static / "index.html").write_text("<!doctype html><title>UI</title>")
    ctx = make_ctx(tmp_path)
    async with running(ctx, static_dir=static) as (srv, local, remote):
        async with session() as s:
            async with s.post(local + "/api/pairing/start") as r:
                assert (await r.json())["remote_url"] is None
            ctx.settings.host_name = "pc.tail1234.ts.net"
            async with s.post(local + "/api/pairing/start") as r:
                assert (await r.json())["remote_url"] == "https://pc.tail1234.ts.net:10500"
            net = types.ModuleType("madalean.runtime.net")
            net.remote_url = lambda ctx: "https://nitro.tail9.ts.net:10500"
            monkeypatch.setitem(sys.modules, "madalean.runtime.net", net)
            import madalean.runtime as rt
            monkeypatch.setattr(rt, "net", net, raising=False)
            async with s.post(local + "/api/pairing/start") as r:
                assert (await r.json())["remote_url"] == "https://nitro.tail9.ts.net:10500"
            async with s.get(local + "/api/examples") as r:
                ex = (await r.json())["examples"]
            assert len(ex) >= 8 and ex[1]["key"] == "pairs" and ex[1]["fr"]["title"] == "Somme de deux nombres pairs"
            assert ex[1]["en"]["title"] != ex[1]["fr"]["title"] and ex[1]["statement"].endswith(":= by sorry")
            for path in ("/", "/some/route"):
                async with s.get(remote + path) as r:
                    h = r.headers
                    assert "frame-ancestors 'self'" in h["Content-Security-Policy"]
                    assert "script-src 'self'" in h["Content-Security-Policy"]
                    assert h["X-Content-Type-Options"] == "nosniff" and h["Referrer-Policy"] == "no-referrer"
                    assert "camera=()" in h["Permissions-Policy"]


async def test_assistant_ordering_and_client_request_id(tmp_path):
    ctx = make_ctx(tmp_path)
    async with running(ctx) as (srv, local, remote):
        async with session() as s, s.ws_connect(local + "/api/ws") as ws:
            await ws.receive_json()
            body = {"messages": [{"role": "user", "content": "simp ?"}], "request_id": "ui-12345678"}
            async with s.post(local + "/api/assistant", json=body) as r:
                assert r.status == 202 and (await r.json())["request_id"] == "ui-12345678"
            evs = []
            while True:
                ev = await asyncio.wait_for(ws.receive_json(), 10)
                evs.append(ev)
                if ev["type"] in ("assistant.done", "assistant.error"):
                    break
            assert all(e["request_id"] == "ui-12345678" for e in evs if e["type"].startswith("assistant."))
            assert evs[-1]["type"] == "assistant.done"
            async with s.post(local + "/api/assistant", json={**body, "request_id": "bad id!"}) as r:
                assert r.status == 400


async def test_job_stream_replay(tmp_path):
    ctx = make_ctx(tmp_path)
    async with running(ctx) as (srv, local, remote):
        async with session() as s:
            async with s.post(local + "/api/dossiers", json={"problem": "Montrer que la somme de deux entiers "
                                                                        "pairs est paire."}) as r:
                jid = (await r.json())["job"]["id"]
            await wait_idle(ctx)
            async with s.get(local + f"/api/jobs/{jid}/stream") as r:
                st = await r.json()
            stages = [g["stage"] for g in st["segments"]]
            assert {"understand", "statement", "notes", "proof", "explanation", "informal"} <= set(stages)
            assert st["ended"] and not st["truncated"] and st["start"] == 0
            whole = "".join(g["text"] for g in st["segments"])
            assert len(whole) == st["end"]
            mid = st["end"] // 2
            async with s.get(local + f"/api/jobs/{jid}/stream?from={mid}") as r:
                tail = await r.json()
            assert "".join(g["text"] for g in tail["segments"]) == whole[mid:]
            async with s.get(local + "/api/jobs/j-nothere/stream") as r:
                assert r.status == 404


def test_stream_store_is_bounded_and_expires():
    now = [0.0]
    st = StreamStore(per_job=100, max_jobs=3, keep_s=60, clock=lambda: now[0])
    for i in range(30):
        st.record("j1", "proof", i // 10, "text", "0123456789")
    r = st.read("j1", 0)
    assert r["truncated"] and r["end"] == 300 and sum(len(g["text"]) for g in r["segments"]) == 100
    st.record("j2", "proof", 0, "text", "x" * 500)
    assert sum(len(g["text"]) for g in st.read("j2")["segments"]) == 100
    st.finish("j1")
    now[0] = 61
    assert st.read("j1") is None and st.read("j2") is not None
    for j in ("a", "b", "c", "d"):
        st.record(j, "s", 0, "text", "t")
    assert len(st.jobs) <= 3
