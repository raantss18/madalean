"""Apps vs browsers on the remote / LAN listeners (user decision 2026-11-21): apps pair once and reconnect
automatically (device token); a plain browser gets a temporary session (code at every visit, idle 2 h / absolute
12 h, gone on restart) that can never become a device token."""
from __future__ import annotations

import json
import socket

from madalean.security import BrowserSessions
from madalean.server.app import Server
from helpers import make_ctx, running, session


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


async def code_of(s, local) -> str:
    async with s.post(local + "/api/pairing/start") as r:
        return (await r.json())["code"]


def browser_headers(base: str, **extra) -> dict:
    return {"Origin": base, "Sec-Fetch-Site": "same-origin", "Sec-Fetch-Mode": "cors",
            "User-Agent": "Mozilla/5.0 Firefox/140.0", **extra}


async def test_browser_pairing_is_a_temporary_session(tmp_path):
    ctx = make_ctx(tmp_path)
    async with running(ctx) as (srv, local, remote):
        async with session() as s:
            code = await code_of(s, local)
            async with s.post(remote + "/api/pair", json={"code": code, "device_name": "", "client": "app-desktop"},
                              headers=browser_headers(remote, **{"X-Forwarded-Proto": "https"})) as r:
                assert r.status == 200
                d = await r.json()
                c = r.headers["Set-Cookie"]
            # a web page claiming to be an app still gets a browser session, never a token
            assert d["kind"] == "browser" and "token" not in d and d["device"]["id"].startswith("b-")
            assert d["device"]["name"] == "Firefox" and d["idle_minutes"] == 120
            assert "HttpOnly" in c and "SameSite=Strict" in c and "Secure" in c and "Path=/" in c
            assert "Max-Age" not in c and "expires" not in c.lower()                 # session cookie
            secret = c.split("madalean_token=", 1)[1].split(";", 1)[0]
            ck = {"Cookie": f"madalean_token={secret}"}
            async with s.get(remote + "/api/state", headers=ck) as r:
                st = await r.json()
            assert r.status == 200 and st["device"]["kind"] == "browser"
            # cannot be upgraded: not as a Bearer token, not into a session ticket / device token
            async with s.get(remote + "/api/state", headers={"Authorization": f"Bearer {secret}"}) as r:
                assert r.status == 401
            async with s.post(remote + "/api/session/ticket", headers={**ck, **browser_headers(remote)}) as r:
                assert r.status == 401
            async with s.post(remote + "/api/session/ticket", headers={"Authorization": f"Bearer {secret}"}) as r:
                assert r.status == 401
            dj = tmp_path / "config" / "devices.json"
            assert not dj.exists() or secret not in dj.read_text()      # memory only
            # the host sees it in a separate list and can revoke it
            async with s.get(local + "/api/devices") as r:
                lst = await r.json()
            assert lst["apps"] == [] and [b["id"] for b in lst["browsers"]] == [d["device"]["id"]]
            assert lst["browsers"][0]["expires_in"] > 7000
            async with s.delete(local + f"/api/devices/{d['device']['id']}") as r:
                assert r.status == 200
            async with s.get(remote + "/api/state", headers=ck) as r:
                assert r.status == 401
            # plain HTTP (no proxy): the cookie is not marked Secure, otherwise the browser would drop it
            code = await code_of(s, local)
            async with s.post(remote + "/api/pair", json={"code": code}, headers=browser_headers(remote)) as r:
                assert r.status == 200 and "Secure" not in r.headers["Set-Cookie"]
            # logout ends the browser session
            sec2 = r.headers["Set-Cookie"].split("madalean_token=", 1)[1].split(";", 1)[0]
            async with s.post(remote + "/api/logout", headers={"Cookie": f"madalean_token={sec2}",
                                                               **browser_headers(remote)}) as r:
                assert r.status == 200
            assert ctx.browser_sessions.list() == []


async def test_idle_and_absolute_expiry():
    now = [0.0]
    bs = BrowserSessions(lambda: 7200.0, clock=lambda: now[0])
    s1, k1 = bs.add("Firefox")
    now[0] = 7199
    assert bs.check(k1) is s1                                   # used: idle timer restarts
    now[0] = 7199 + 7201
    assert bs.check(k1) is None and bs.list() == []             # idle for more than 2 h
    s2, k2 = bs.add("Chrome")
    for _i in range(13):                                         # active every hour…
        now[0] += 3600
        alive = bs.check(k2)
    assert alive is None                                         # …but never more than 12 h
    idle = [60.0]
    bs3 = BrowserSessions(lambda: idle[0], clock=lambda: now[0])
    s3, k3 = bs3.add("x")
    now[0] += 61
    assert bs3.check(k3) is None                                 # the setting is read at each check


async def test_app_token_survives_restart_browser_session_does_not(tmp_path):
    ctx = make_ctx(tmp_path)
    async with running(ctx) as (srv, local, remote):
        async with session() as s:
            async with s.post(remote + "/api/pair", json={"code": await code_of(s, local), "device_name": "Pixel",
                                                          "client": "app-android"}) as r:
                token = (await r.json())["token"]
            async with s.post(remote + "/api/pair", json={"code": await code_of(s, local)},
                              headers=browser_headers(remote)) as r:
                secret = r.headers["Set-Cookie"].split("madalean_token=", 1)[1].split(";", 1)[0]
            async with s.get(local + "/api/devices") as r:
                lst = await r.json()
            assert lst["apps"][0]["client"] == "app-android" and lst["apps"][0]["kind"] == "app"
            assert len(lst["browsers"]) == 1
    ctx2 = make_ctx(tmp_path)                                    # same config directory: a server restart
    async with running(ctx2) as (srv, local, remote):
        async with session() as s:
            async with s.get(remote + "/api/hello", headers={"Authorization": f"Bearer {token}"}) as r:
                assert (await r.json())["paired"] is True
            async with s.post(remote + "/api/session/ticket", headers={"Authorization": f"Bearer {token}"}) as r:
                assert r.status == 200                          # the app reconnects by itself
            async with s.get(remote + "/api/state", headers={"Cookie": f"madalean_token={secret}"}) as r:
                assert r.status == 401                          # the browser needs a new code


async def test_lan_listener_same_rules(tmp_path):
    ctx = make_ctx(tmp_path)
    lan_port = free_port()
    (tmp_path / "config").mkdir(parents=True, exist_ok=True)
    (tmp_path / "config" / "settings.json").write_text(json.dumps({"lan_port": lan_port}))
    srv = Server(ctx, 0, 0, lan=True)
    await srv.start()
    try:
        local, lan = f"http://127.0.0.1:{srv.ports['local']}", f"http://127.0.0.1:{srv.ports['lan']}"
        async with session() as s:
            async with s.get(lan + "/api/state") as r:
                assert r.status == 401
            async with s.post(lan + "/api/pair", json={"code": await code_of(s, local)},
                              headers=browser_headers(lan)) as r:
                d = await r.json()
                secret = r.headers["Set-Cookie"].split("madalean_token=", 1)[1].split(";", 1)[0]
            assert d["kind"] == "browser"
            async with s.get(lan + "/api/state", headers={"Cookie": f"madalean_token={secret}"}) as r:
                assert r.status == 200
            async with s.patch(lan + "/api/settings", json={"browser_session_idle_minutes": 600},
                               headers={"Cookie": f"madalean_token={secret}", **browser_headers(lan)}) as r:
                assert r.status == 403                          # host-only setting
            async with s.patch(local + "/api/settings", json={"browser_session_idle_minutes": 30}) as r:
                assert r.status == 200
            async with s.get(local + "/api/devices") as r:
                assert (await r.json())["browser_idle_minutes"] == 30
    finally:
        await srv.stop()
