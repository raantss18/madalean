"""Revocation, logout, self-forget and browser-session expiry close that credential's open WebSockets with code 4401
(within 1 s) and cancel the streaming it started."""
from __future__ import annotations

import asyncio
import time

import aiohttp

from helpers import make_ctx, running, session


async def closed_code(ws, timeout: float = 1.0):
    t0 = time.monotonic()
    while time.monotonic() - t0 < timeout:
        m = await asyncio.wait_for(ws.receive(), timeout - (time.monotonic() - t0))
        if m.type in (aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.CLOSING, aiohttp.WSMsgType.CLOSED):
            return ws.close_code
    return None


def brw(base: str) -> dict:
    return {"Origin": base, "Sec-Fetch-Site": "same-origin", "Sec-Fetch-Mode": "cors"}


async def pair_browser(s, local, remote) -> str:
    async with s.post(local + "/api/pairing/start") as r:
        code = (await r.json())["code"]
    async with s.post(remote + "/api/pair", json={"code": code}, headers=brw(remote)) as r:
        return r.headers["Set-Cookie"].split("madalean_token=", 1)[1].split(";", 1)[0]


async def test_revoking_an_app_closes_its_websockets_and_streaming(tmp_path):
    async def slow(role, messages, brain):
        await asyncio.sleep(30)
        return "late"
    from madalean.brain.fake import FakeBrain
    ctx = make_ctx(tmp_path, brain=FakeBrain(slow))
    async with running(ctx) as (srv, local, remote):
        dev, token = ctx.devices.add("phone", "app-android")
        other, token2 = ctx.devices.add("laptop", "app-desktop")
        h = {"Authorization": f"Bearer {token}"}
        async with session() as s, s.ws_connect(remote + "/api/ws", headers=h) as ws, \
                s.ws_connect(remote + "/api/ws", headers={"Authorization": f"Bearer {token2}"}) as ws2:
            assert (await ws.receive_json())["type"] == "hello"
            await ws2.receive_json()
            async with s.post(remote + "/api/assistant", headers=h,
                              json={"messages": [{"role": "user", "content": "x"}]}) as r:
                assert r.status == 202
            task = next(iter(ctx.bus.owned[dev.id]))
            async with s.delete(local + f"/api/devices/{dev.id}") as r:
                assert r.status == 200
            assert await closed_code(ws) == 4401
            await asyncio.sleep(0.05)
            assert task.cancelled() or task.done()
            assert not ws2.closed                                       # other devices keep their socket


async def test_logout_and_self_forget_close_websockets(tmp_path):
    ctx = make_ctx(tmp_path)
    async with running(ctx) as (srv, local, remote):
        async with session() as s:
            secret = await pair_browser(s, local, remote)
            ck = {"Cookie": f"madalean_token={secret}", **brw(remote)}
            async with s.ws_connect(remote + "/api/ws", headers=ck) as ws:
                await ws.receive_json()
                async with s.post(remote + "/api/logout", headers=ck) as r:
                    assert r.status == 200
                assert await closed_code(ws) == 4401
            dev, token = ctx.devices.add("tablet", "app-android")
            h = {"Authorization": f"Bearer {token}"}
            async with s.ws_connect(remote + "/api/ws", headers=h) as ws:
                await ws.receive_json()
                async with s.post(remote + "/api/devices/self/forget", headers=h) as r:
                    assert r.status == 204
                assert await closed_code(ws) == 4401


async def test_browser_session_expiry_closes_websockets(tmp_path):
    ctx = make_ctx(tmp_path)
    async with running(ctx) as (srv, local, remote):
        now = [time.monotonic()]
        ctx.browser_sessions.clock = lambda: now[0]
        async with session() as s:
            secret = await pair_browser(s, local, remote)
            ck = {"Cookie": f"madalean_token={secret}", **brw(remote)}
            async with s.ws_connect(remote + "/api/ws", headers=ck) as ws:
                await ws.receive_json()
                now[0] += 2 * 3600 + 1                                  # idle for more than 2 h
                ctx.browser_sessions.sweep()                            # what the periodic sweeper does
                assert await closed_code(ws) == 4401
            async with s.get(remote + "/api/state", headers=ck) as r:
                assert r.status == 401
