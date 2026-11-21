"""Fallback addresses of the pairing QR code (`POST /api/pairing/start` → `addresses`, docs/SHELLS.md)."""
from __future__ import annotations

import json
import socket

from madalean.server import routes_core
from madalean.server.app import Server
from helpers import make_ctx, running, session


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class FakeNet:
    def status(self):
        return {"state": "running", "dns_name": "madalean.tail1234.ts.net.",
                "ips": ["fd7a:115c:a1e0::1", "100.74.179.13"]}


def test_address_classes():
    assert routes_core._is_tailnet_ipv4("100.74.179.13")
    assert not routes_core._is_tailnet_ipv4("192.168.1.2")
    assert not routes_core._is_tailnet_ipv4("fd7a:115c:a1e0::1")
    for ip in ("192.168.1.20", "10.0.0.5", "172.20.3.4"):
        assert routes_core._is_lan_ipv4(ip)
    for ip in ("127.0.0.1", "100.74.179.13", "169.254.1.1", "8.8.8.8", "172.32.0.1", "nope"):
        assert not routes_core._is_lan_ipv4(ip)


async def test_no_tailnet_no_lan(tmp_path):
    ctx = make_ctx(tmp_path)
    async with running(ctx) as (srv, local, remote):
        async with session() as s:
            async with s.post(local + "/api/pairing/start") as r:
                d = await r.json()
    assert d["addresses"] == {"host": None, "ip": None, "lan": []}


async def test_tailnet_name_ip_and_lan(tmp_path, monkeypatch):
    ctx = make_ctx(tmp_path)
    lan_port = free_port()
    (tmp_path / "config").mkdir(parents=True, exist_ok=True)
    (tmp_path / "config" / "settings.json").write_text(json.dumps({"lan_port": lan_port}))
    monkeypatch.setattr(routes_core, "lan_ipv4", lambda: "192.168.1.20")
    srv = Server(ctx, 0, 0, lan=True)
    await srv.start()
    ctx.net = FakeNet()                 # the net plugin installs the real node at start-up
    try:
        async with session() as s:
            async with s.post(f"http://127.0.0.1:{srv.ports['local']}/api/pairing/start") as r:
                d = await r.json()
            # host-only: a LAN client gets nothing (no token), let alone the addresses
            async with s.post(f"http://127.0.0.1:{srv.ports['lan']}/api/pairing/start") as r:
                assert r.status == 401
    finally:
        await srv.stop()
    assert d["remote_url"] == "https://madalean.tail1234.ts.net"
    assert d["addresses"] == {"host": "madalean.tail1234.ts.net", "ip": "100.74.179.13",
                              "lan": [f"192.168.1.20:{srv.ports['lan']}"]}


async def test_lan_address_only_while_listener_open(tmp_path, monkeypatch):
    ctx = make_ctx(tmp_path)
    monkeypatch.setattr(routes_core, "lan_ipv4", lambda: "192.168.1.20")
    async with running(ctx) as (srv, local, remote):
        async with session() as s:
            async with s.post(local + "/api/pairing/start") as r:
                d = await r.json()
    assert d["addresses"]["lan"] == []


def test_lan_ipv4_is_private_or_none():
    ip = routes_core.lan_ipv4()
    assert ip is None or routes_core._is_lan_ipv4(ip)
