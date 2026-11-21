"""Memory and idle work (session S-Q, docs/PERFORMANCE.md): bounded event ring, bounded HTTP / embedding caches, one
shared embedder, a GPU monitor that idles when nobody looks, single-flight catalogue refresh, capped warm kernels, and
no shared Tailscale node started by a dev / test server."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

from madalean.research import fetch
from madalean.runtime.monitor import Monitor
from madalean.server.bus import EventBus


def test_event_ring_is_bounded_in_bytes_and_count():
    bus = EventBus(ring=100, ring_bytes=50_000)
    for i in range(50):
        bus.publish("article.updated", {"article": {"text": "x" * 5000}, "i": i})
    size = sum(len(json.dumps(e)) for e in bus.ring)
    assert size <= 50_000 + 6000 and len(bus.ring) < 50
    assert bus.since(bus.seq - 2) is not None and bus.since(1) is None       # too old → resync
    for i in range(300):
        bus.publish("toast", {"i": i})
    assert len(bus.ring) == 100 and bus.ring[-1]["seq"] == bus.seq


def test_fetch_cache_bounded_and_skips_large_bodies():
    f = fetch.Fetcher(fetch.ReplayTransport(Path("/nonexistent")))
    for i in range(fetch.CACHE_MAX_ITEMS + 50):
        f._remember(f"k{i}", fetch.Response(url=f"u{i}", status=200, body=b"x" * 1000))
    assert len(f._cache) == fetch.CACHE_MAX_ITEMS and "k0" not in f._cache
    for i in range(20):
        f._remember(f"big{i}", fetch.Response(url="u", status=200, body=b"y" * (fetch.CACHE_MAX_ITEM - 1)))
    assert sum(len(r.body) for _t, r in f._cache.values()) <= fetch.CACHE_MAX_BYTES


async def test_embedder_cache_is_lru_float32_and_shared():
    from madalean.brain import rag
    a = rag.shared_embedder("http://127.0.0.1:9")
    assert rag.shared_embedder("http://127.0.0.1:9") is a
    a.max_cached = 3
    a.model = "nomic-embed"

    class R:
        def __init__(self, n):
            self.n = n

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def json(self):
            return {"embeddings": [[0.5, 0.25]] * self.n}

    class S:
        closed = False
        _loop = asyncio.get_running_loop()

        def post(self, url, json):
            return R(len(json["input"]))
    a._session = S()
    await a.embed(["a", "b", "c", "d"], False)
    assert len(a._cache) == 3 and all(v.typecode == "f" for v in a._cache.values())
    assert await a.embed(["d"], False) == [[0.5, 0.25]]
    a._session = None
    rag._SHARED.clear()


async def test_monitor_idles_without_audience_and_wakes():
    m = Monitor([Path.home()], interval=0.05, idle_interval=30)
    polls = []

    async def fake_poll():
        polls.append(1)
    m.poll = fake_poll
    m.wanted = lambda: False
    m.start()
    await asyncio.sleep(0.4)
    assert len(polls) == 1                      # no audience: one poll, then the idle pace
    m.wanted = lambda: True
    m.wake()
    await asyncio.sleep(0.4)
    assert len(polls) >= 4                      # someone looks: fast pace again
    await m.stop()


async def test_system_status_only_with_clients_and_on_change(tmp_path):
    from helpers import make_ctx
    ctx = make_ctx(tmp_path)
    n0 = ctx.bus.seq
    ctx._system_status({})
    assert ctx.bus.seq == n0                    # nobody connected: nothing enters the ring
    ctx.bus.clients = 1
    ctx._system_status({})
    ctx._system_status({})
    assert ctx.bus.seq == n0 + 1                # unchanged snapshot: published once


async def test_catalogue_refresh_is_single_flight():
    from madalean.brain.engine import MadaleanBrain as Engine
    calls = []

    class Store:
        async def refresh(self, http, key, online=True, **kw):
            calls.append(1)
            await asyncio.sleep(0.1)

    class Http:
        async def online(self):
            return True
    e = Engine.__new__(Engine)
    e.settings, e.store, e.http, e.key = {"mode": "auto"}, Store(), Http(), lambda p: None
    e.endpoints, e.hub_url = {}, (lambda: "")
    await asyncio.gather(e.refresh(), e.refresh(), e.refresh())
    assert len(calls) == 1
    await e.refresh()
    assert len(calls) == 2


async def test_warm_kernels_are_capped(tmp_path):
    from madalean.research import sagebridge
    br = sagebridge.SageBridge.__new__(sagebridge.SageBridge)
    br.kernels, br._lock = {}, asyncio.Lock()
    started, stopped = [], []

    async def start_kernel(language):
        started.append(language)
        return f"k{len(started)}"

    async def shutdown(kid):
        stopped.append(kid)
        br.kernels = {k: v for k, v in br.kernels.items() if v["id"] != kid}
    br.start_kernel, br.shutdown = start_kernel, shutdown
    for i in range(sagebridge.MAX_WARM_KERNELS + 2):
        await br.kernel_for(f"calcul:p{i}", "sage")
        await asyncio.sleep(0.01)
    assert len(br.kernels) == sagebridge.MAX_WARM_KERNELS and stopped == ["k1", "k2"]
    assert sagebridge.KERNEL_IDLE_S >= 3600


def test_dev_or_test_server_never_autostarts_the_shared_tailscale_node(tmp_path, monkeypatch):
    from madalean.server.plugins.deps_net import shared_node_blocked
    monkeypatch.delenv("MADALEAN_NET", raising=False)
    assert shared_node_blocked(tmp_path / "config") in ("dev_checkout", "custom_config_dir")
    monkeypatch.setenv("MADALEAN_NET", "1")
    assert shared_node_blocked(tmp_path / "config") is None
