"""Shell endpoints (docs/SHELLS.md « Required server endpoints »): one-time ticket → HttpOnly cookie page,
self-forget. Ticket single use / expiry / Bearer only, open-redirect attempts, cookie attributes, no query in logs."""
from __future__ import annotations

import logging

import aiohttp

from madalean.security import Tickets
from madalean.server.routes_core import safe_next
from helpers import make_ctx, running, session


async def paired(ctx, name="laptop"):
    dev, token = ctx.devices.add(name)
    return dev, token


def cookie_of(resp) -> str:
    return resp.headers.get("Set-Cookie", "")


async def test_ticket_to_cookie_and_single_use(tmp_path):
    ctx = make_ctx(tmp_path)
    async with running(ctx) as (srv, local, remote):
        dev, token = await paired(ctx)
        bearer = {"Authorization": f"Bearer {token}"}
        async with session() as s:
            async with s.post(remote + "/api/session/ticket", headers=bearer) as r:
                assert r.status == 200 and r.headers["Cache-Control"] == "no-store"
                t = await r.json()
            assert t["expires_in"] == 60 and len(t["ticket"]) >= 32          # 192 bits urlsafe
            async with s.get(remote + f"/api/session?ticket={t['ticket']}&next=/dossiers/x?tab=lean",
                             allow_redirects=False) as r:
                assert r.status == 200 and r.content_type == "text/html"
                body = await r.text()
                c = cookie_of(r)
                assert r.headers["Cache-Control"] == "no-store" and r.headers["Referrer-Policy"] == "no-referrer"
                csp = r.headers["Content-Security-Policy"]
                assert "script-src 'none'" in csp and "default-src 'none'" in csp
            assert 'content="0;url=/dossiers/x?tab=lean"' in body and "<script" not in body
            assert "madalean_token=" in c and "HttpOnly" in c and "SameSite=Strict" in c and "Path=/" in c
            assert "Secure" not in c                                         # plain http on loopback
            secret = c.split("madalean_token=", 1)[1].split(";", 1)[0]
            assert secret != token                                           # a session secret, not the token
            async with s.get(remote + "/api/state", headers={"Cookie": f"madalean_token={secret}"}) as r:
                assert r.status == 200 and (await r.json())["device"]["id"] == dev.id
            assert token not in (tmp_path / "config" / "devices.json").read_text()
            assert secret not in (tmp_path / "config" / "devices.json").read_text()
            # single use
            async with s.get(remote + f"/api/session?ticket={t['ticket']}&next=/", allow_redirects=False) as r:
                assert r.status == 303 and r.headers["Location"] == "/pair?reason=ticket"
                assert "madalean_token" not in cookie_of(r)
            # the session cookie dies with the device
            ctx.devices.revoke(dev.id)
            async with s.get(remote + "/api/state", headers={"Cookie": f"madalean_token={secret}"}) as r:
                assert r.status == 401


async def test_ticket_needs_a_bearer_device_token(tmp_path):
    ctx = make_ctx(tmp_path)
    async with running(ctx) as (srv, local, remote):
        dev, token = await paired(ctx)
        sec = ctx.devices.add_session(dev.id)
        async with session() as s:
            for url, h in ((remote, {}), (remote, {"Authorization": "Bearer wrong"}),
                           (remote, {"Cookie": f"madalean_token={sec}"}),            # cookie is not enough
                           (local, {}), (local, {"Authorization": "Bearer wrong"})):
                async with s.post(url + "/api/session/ticket", headers=h) as r:
                    assert r.status == 401, (url, h)
            async with s.post(local + "/api/session/ticket", headers={"Authorization": f"Bearer {token}"}) as r:
                assert r.status == 200                                       # also on the local listener
            for bad in ("", "nope", "x" * 300):
                async with s.get(remote + f"/api/session?ticket={bad}", allow_redirects=False) as r:
                    assert r.status == 303 and "madalean_token" not in cookie_of(r)


async def test_ticket_expiry_and_binding():
    now = [100.0]
    t = Tickets(ttl=60, clock=lambda: now[0])
    a = t.issue("d-1")
    b = t.issue("d-2")
    assert a != b and t.consume(b) == "d-2"
    now[0] += 61
    assert t.consume(a) is None                                                # expired
    c = t.issue("d-1")
    assert t.consume(c) == "d-1" and t.consume(c) is None                      # single use


async def test_secure_cookie_behind_https_proxy_and_revoked_device(tmp_path):
    ctx = make_ctx(tmp_path)
    async with running(ctx) as (srv, local, remote):
        dev, token = await paired(ctx)
        async with session() as s:
            tk = ctx.tickets.issue(dev.id)
            async with s.get(remote + f"/api/session?ticket={tk}", headers={"X-Forwarded-Proto": "https"},
                             allow_redirects=False) as r:
                assert r.status == 200 and "Secure" in cookie_of(r)
                assert 'content="0;url=/"' in await r.text()                 # missing next → /
            tk = ctx.tickets.issue(dev.id)
            ctx.devices.revoke(dev.id)
            async with s.get(remote + f"/api/session?ticket={tk}", allow_redirects=False) as r:
                assert r.status == 303 and "madalean_token" not in cookie_of(r)


def test_next_open_redirect_attempts():
    good = {"/": "/", "/dossiers/a-1": "/dossiers/a-1", "/x?y=//z": "/x?y=//z"}
    for k, v in good.items():
        assert safe_next(k) == v
    for bad in ("//evil.example", "///evil.example", "/\\evil.example", "\\\\evil", "https://evil.example",
                "evil.example", "javascript:alert(1)", "/a//b", " /x", "/x\ny", "/x\ty", "", None, "/" + "a" * 3000):
        assert safe_next(bad) == "/", bad


async def test_next_is_validated_and_escaped_over_http(tmp_path):
    ctx = make_ctx(tmp_path)
    async with running(ctx) as (srv, local, remote):
        dev, token = await paired(ctx)
        async with session() as s:
            for nxt, want in (("%2F%2Fevil.example", "/"), ("/%5Cevil.example", "/"), ("https://evil.example", "/"),
                              ('/a"><script>alert(1)</script>', '/a&quot;&gt;&lt;script&gt;alert(1)&lt;/script&gt;')):
                tk = ctx.tickets.issue(dev.id)
                async with s.get(remote + f"/api/session?ticket={tk}&next={nxt}", allow_redirects=False) as r:
                    body = await r.text()
                assert f'content="0;url={want}"' in body, (nxt, body)
                assert "<script>" not in body


async def test_query_string_is_never_logged(tmp_path):
    class Grab(logging.Handler):
        def __init__(self):
            super().__init__(logging.DEBUG)
            self.lines = []

        def emit(self, record):
            self.lines.append(record.getMessage())
    g = Grab()
    loggers = [logging.getLogger(n) for n in ("aiohttp.access", "aiohttp.server", "aiohttp.web", "madalean", "")]
    old = [(lg, lg.level) for lg in loggers]
    for lg in loggers:
        lg.addHandler(g)
        lg.setLevel(logging.DEBUG)
    try:
        ctx = make_ctx(tmp_path)
        async with running(ctx) as (srv, local, remote):
            dev, token = await paired(ctx)
            async with session() as s:
                tk = ctx.tickets.issue(dev.id)
                async with s.get(remote + f"/api/session?ticket={tk}&next=/", allow_redirects=False) as r:
                    assert r.status == 200
                async with s.get(remote + f"/api/session?ticket={tk}&next=/", allow_redirects=False) as r:
                    assert r.status == 303
                async with s.get(remote + "/api/session?ticket=abc", headers={"Origin": "https://evil.example"},
                                 allow_redirects=False) as r:
                    pass
        text = "\n".join(g.lines)
        assert tk not in text and "ticket=" not in text and token not in text
    finally:
        for lg, lvl in old:
            lg.removeHandler(g)
            lg.setLevel(lvl)


async def test_device_forgets_itself(tmp_path):
    ctx = make_ctx(tmp_path)
    async with running(ctx) as (srv, local, remote):
        dev, token = await paired(ctx)
        other, token2 = await paired(ctx, "phone")
        async with session() as s:
            async with s.post(remote + "/api/devices/self/forget") as r:
                assert r.status == 401
            async with s.post(remote + "/api/devices/self/forget", headers={"Authorization": f"Bearer {token}"}) as r:
                assert r.status == 204
            async with s.get(remote + "/api/hello", headers={"Authorization": f"Bearer {token}"}) as r:
                assert (await r.json())["paired"] is False
            async with s.get(remote + "/api/state", headers={"Authorization": f"Bearer {token2}"}) as r:
                assert r.status == 200                                         # other devices unaffected
            async with s.post(local + "/api/devices/self/forget") as r:
                assert r.status == 401                                         # the host is not a device
