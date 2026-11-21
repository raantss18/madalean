"""Security of the two listeners: every route of the remote listener needs a token (enumerated from the router),
pairing codes (single use, expiry, lockout), revoked tokens, Origin/Host checks, WebSocket auth, path traversal."""
from __future__ import annotations

import re

import aiohttp

from madalean.security import Pairing, PairingError
from madalean.server.app import make_app
from helpers import make_ctx, running, session

PUBLIC = {("GET", "/api/hello"), ("POST", "/api/pair"), ("POST", "/api/logout"), ("GET", "/api/session")}


def concrete(path: str) -> str:
    return re.sub(r"\{[^}]+\}", "x1", path.replace("{tail:.*}", "x1"))


async def test_every_remote_route_needs_a_token(tmp_path):
    ctx = make_ctx(tmp_path)
    app = make_app(ctx)
    routes = []
    for r in app.router.routes():
        info = r.resource.get_info() if r.resource else {}
        path = info.get("path") or info.get("formatter")
        if path:
            routes.append((r.method, path))
    assert len(routes) > 60
    async with running(ctx) as (srv, local, remote):
        async with session() as s:
            checked = 0
            for method, path in routes:
                methods = ["GET", "POST", "PUT", "PATCH", "DELETE"] if method == "*" else [method]
                for m in methods:
                    if m == "HEAD":
                        continue
                    url = concrete(path)
                    if (m, url) in PUBLIC:
                        continue
                    for headers in ({}, {"Authorization": "Bearer nope"}, {"Cookie": "madalean_token=nope"}):
                        async with s.request(m, remote + url, headers=headers, data=b"{}") as r:
                            if path.startswith("/{tail") and m == "GET":
                                assert r.status in (200, 404), (m, url)        # static UI is public
                            else:
                                assert r.status == 401, (m, url, r.status, await r.text())
                        checked += 1
            assert checked > 150
            # the same routes on the local listener are not refused for lack of a token
            async with s.get(local + "/api/state") as r:
                assert r.status == 200


async def test_pairing_flow_cookie_bearer_revoke(tmp_path):
    ctx = make_ctx(tmp_path)
    async with running(ctx) as (srv, local, remote):
        async with session() as s:
            async with s.post(remote + "/api/pairing/start") as r:
                assert r.status == 401                            # host-only and unauthenticated
            async with s.post(local + "/api/pairing/start") as r:
                code = (await r.json())["code"]
            assert re.fullmatch(r"\d{6}", code)
            async with s.post(remote + "/api/pair", json={"code": code, "device_name": "phone",
                                                          "client": "app-android"}) as r:
                assert r.status == 200
                d = await r.json()
                token = d["token"]
                assert "Set-Cookie" not in r.headers and d["kind"] == "app"   # apps: token only (keystore)
            async with s.post(remote + "/api/pair", json={"code": code, "device_name": "again"}) as r:
                assert r.status == 403                            # single use
            raw = (tmp_path / "config" / "devices.json").read_text()
            assert token not in raw and oct((tmp_path / "config" / "devices.json").stat().st_mode)[-3:] == "600"
            h = {"Authorization": f"Bearer {token}"}
            async with s.get(remote + "/api/state", headers=h) as r:
                assert r.status == 200 and (await r.json())["device"]["name"] == "phone"
            async with s.get(remote + "/api/hello", headers=h) as r:
                j = await r.json()
                assert j["paired"] and not j["local"]
            async with s.get(remote + "/api/state", headers={"Cookie": f"madalean_token={token}"}) as r:
                assert r.status == 200
            # host-only routes stay closed to a paired device
            for m, p in (("POST", "/api/pairing/start"), ("GET", "/api/devices"), ("DELETE", "/api/devices/x"),
                         ("POST", "/api/system/repair/models")):
                async with s.request(m, remote + p, headers=h) as r:
                    assert r.status == 403, (m, p)
            async with s.patch(remote + "/api/settings", headers=h, json={"remote_jupyter": True}) as r:
                assert r.status == 403
            async with s.patch(remote + "/api/settings", headers=h, json={"profile": "étudiant L3"}) as r:
                assert r.status == 200
            async with s.get(remote + "/jupyter/api/status", headers=h) as r:
                assert r.status == 403                            # Jupyter is host-only unless the host allows it
            # revoke from the host
            async with s.get(local + "/api/devices") as r:
                did = (await r.json())["devices"][0]["id"]
            async with s.delete(local + f"/api/devices/{did}") as r:
                assert r.status == 200
            async with s.get(remote + "/api/state", headers=h) as r:
                assert r.status == 401


async def test_wrong_codes_lock_pairing(tmp_path):
    now = [1000.0]
    p = Pairing(clock=lambda: now[0])
    code, _ttl = p.start()
    wrong = "000000" if code != "000000" else "111111"
    for _i in range(4):
        try:
            p.consume(wrong)
        except PairingError as e:
            assert e.kind == "wrong"
    try:
        p.consume(wrong)
    except PairingError as e:
        assert e.kind == "locked" and e.retry_after == 600
    try:
        p.consume(code)                                           # even the right code is refused now
    except PairingError as e:
        assert e.kind == "locked"
    now[0] += 601
    try:
        p.consume(code)
    except PairingError as e:
        assert e.kind == "no_code"                                # the old code was burnt
    code2, _ = p.start()
    now[0] += 301
    try:
        p.consume(code2)
    except PairingError as e:
        assert e.kind == "expired"


async def test_pair_endpoint_lockout_and_rate_limit(tmp_path):
    from madalean.server import routes_core
    routes_core.PAIR_LIMIT.hits.clear()
    routes_core.PAIR_GLOBAL.hits.clear()
    ctx = make_ctx(tmp_path)
    async with running(ctx) as (srv, local, remote):
        async with session() as s:
            async with s.post(local + "/api/pairing/start") as r:
                code = (await r.json())["code"]
            bad = "999999" if code != "999999" else "888888"
            statuses = []
            for _i in range(5):
                async with s.post(remote + "/api/pair", json={"code": bad, "device_name": "x"}) as r:
                    statuses.append(r.status)
            assert statuses == [403, 403, 403, 403, 429]
            async with s.post(remote + "/api/pair", json={"code": code, "device_name": "x"}) as r:
                assert r.status == 429 and (await r.json())["error"] == "locked"
            for _i in range(10):
                async with s.post(remote + "/api/pair", json={"code": bad}) as r:
                    last = r.status
            assert last == 429
    routes_core.PAIR_LIMIT.hits.clear()
    routes_core.PAIR_GLOBAL.hits.clear()


async def test_websocket_needs_a_token_and_a_good_origin(tmp_path):
    ctx = make_ctx(tmp_path)
    async with running(ctx) as (srv, local, remote):
        async with session() as s:
            for url, headers in ((remote + "/api/ws", {}), (remote + "/api/ws", {"Authorization": "Bearer bad"}),
                                 (local + "/api/ws", {"Origin": "https://evil.example"})):
                try:
                    async with s.ws_connect(url, headers=headers):
                        raise AssertionError(f"connected to {url}")
                except aiohttp.WSServerHandshakeError as e:
                    assert e.status in (401, 403)
            ctx.pairing.start()
            dev, token = ctx.devices.add("tablet")
            async with s.ws_connect(remote + "/api/ws", headers={"Authorization": f"Bearer {token}"}) as ws:
                hello = await ws.receive_json()
                assert hello["type"] == "hello" and not hello["local"]
            # cookie auth from a browser on the tailnet name: Origin must match the Host
            hdr = {"Cookie": f"madalean_token={token}", "Host": "pc.tail1234.ts.net:10500",
                   "Origin": "https://pc.tail1234.ts.net:10500"}
            async with s.ws_connect(remote + "/api/ws", headers=hdr) as ws:
                assert (await ws.receive_json())["type"] == "hello"
            try:
                async with s.ws_connect(remote + "/api/ws", headers={**hdr, "Origin": "https://evil.example"}):
                    raise AssertionError("cross-site websocket accepted")
            except aiohttp.WSServerHandshakeError as e:
                assert e.status == 403


async def test_local_listener_refuses_rebinding_and_cross_site_posts(tmp_path):
    ctx = make_ctx(tmp_path)
    async with running(ctx) as (srv, local, remote):
        async with session() as s:
            async with s.get(local + "/api/state", headers={"Host": "evil.example:11500"}) as r:
                assert r.status == 403 and (await r.json())["error"] == "bad_host"
            async with s.post(local + "/api/projects", json={"title": "x"},
                              headers={"Origin": "https://evil.example"}) as r:
                assert r.status == 403
            async with s.post(local + "/api/projects", json={"title": "x"},
                              headers={"Origin": f"http://127.0.0.1:{srv.ports['local']}"}) as r:
                assert r.status == 201
            async with s.post(local + "/api/projects", json={"title": "x"}) as r:     # CLI / no browser
                assert r.status == 201
            async with s.post(local + "/api/projects", json={"title": "x"}, headers={"Origin": "null"}) as r:
                assert r.status == 403


async def test_static_and_export_path_traversal(tmp_path):
    static = tmp_path / "static"
    (static / "assets").mkdir(parents=True)
    (static / "index.html").write_text("<!doctype html><title>UI</title>")
    (static / "assets" / "app.js").write_text("console.log(1)")
    (tmp_path / "secret.txt").write_text("SECRET")
    ctx = make_ctx(tmp_path)
    async with running(ctx, static_dir=static) as (srv, local, remote):
        async with session() as s:
            async with s.get(remote + "/assets/app.js") as r:
                assert r.status == 200 and "immutable" in r.headers["Cache-Control"]
            async with s.get(remote + "/some/client/route") as r:
                assert r.status == 200 and "UI" in await r.text()          # SPA fallback
            for p in ("/../secret.txt", "/%2e%2e/secret.txt", "/assets/..%2f..%2fsecret.txt", "/..%2fsecret.txt",
                      "/%2e%2e%2fsecret.txt", "/.hidden", "/assets/%00x"):
                async with s.get(remote + p) as r:
                    assert "SECRET" not in await r.text(), p
            async with s.get(local + "/api/dossiers/..%2f..%2fsecret/export?format=pdf") as r:
                assert r.status in (400, 404)
            async with s.get(local + "/api/dossiers/../../secret/export?format=pdf") as r:
                assert "SECRET" not in await r.text()
            async with s.post(local + "/api/dossiers", json={"statement": "theorem t : 1 = 1 := by sorry",
                                                             "start": False}) as r:
                did = (await r.json())["dossier"]["id"]
            async with s.get(local + f"/api/dossiers/{did}/export?format=../../etc/passwd") as r:
                assert r.status == 400
            async with s.get(local + "/api/jupyter/notebook?path=../../etc/passwd") as r:
                assert r.status in (400, 503)
