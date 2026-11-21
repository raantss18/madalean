"""S-H review, robustness (ARCHITECTURE §15): crash-safe storage under kill -9 / disk full / file-size limit,
oversized bodies, many WebSockets and slow (slow-loris) clients, a Lean child killed with -9 mid-check."""
from __future__ import annotations

import asyncio
import errno
import json
import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

import aiohttp
import pytest

from madalean import config
from helpers import make_ctx, running, session

REPO = Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------- storage
def test_atomic_write_survives_disk_full(tmp_path, monkeypatch):
    f = tmp_path / "settings.json"
    config.atomic_write_text(f, json.dumps({"v": 1}))

    def full(fd):
        raise OSError(errno.ENOSPC, "No space left on device")
    monkeypatch.setattr(os, "fsync", full)
    with pytest.raises(OSError):
        config.atomic_write_text(f, json.dumps({"v": 2, "big": "x" * 100000}))
    assert json.loads(f.read_text()) == {"v": 1}
    assert [p.name for p in tmp_path.iterdir()] == ["settings.json"]          # no temp file left behind


def test_atomic_write_under_rlimit_fsize(tmp_path):
    """A real EFBIG from the kernel (RLIMIT_FSIZE, no root needed) in the middle of a write."""
    f = tmp_path / "dossier.json"
    config.atomic_write_text(f, json.dumps({"v": "old"}))
    code = ("import json, resource, signal, sys\n"
            "signal.signal(signal.SIGXFSZ, signal.SIG_IGN)\n"
            "resource.setrlimit(resource.RLIMIT_FSIZE, (4096, 4096))\n"
            f"sys.path.insert(0, {str(REPO)!r})\n"
            "from madalean import config\n"
            "try:\n"
            f"    config.atomic_write_text(__import__('pathlib').Path({str(f)!r}), json.dumps({{'v': 'x' * 100000}}))\n"
            "except OSError as e:\n    print('ERR', e.errno)\n")
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=60)
    assert "ERR" in r.stdout, r.stdout + r.stderr
    assert json.loads(f.read_text()) == {"v": "old"}
    assert [p.name for p in tmp_path.iterdir()] == ["dossier.json"]


def test_kill_9_during_writes_never_leaves_a_torn_file(tmp_path):
    f = tmp_path / "state.json"
    code = ("import json, sys, itertools\n"
            f"sys.path.insert(0, {str(REPO)!r})\n"
            "from pathlib import Path\nfrom madalean import config\n"
            f"p = Path({str(f)!r})\n"
            "for i in itertools.count():\n"
            "    config.atomic_write_text(p, json.dumps({'i': i, 'pad': 'y' * (i % 50000)}))\n")
    for k in range(12):
        proc = subprocess.Popen([sys.executable, "-c", code])
        time.sleep(0.3 + 0.07 * k)
        proc.send_signal(signal.SIGKILL)
        proc.wait()
        d = json.loads(f.read_text())                      # always a complete document (old or new)
        assert isinstance(d["i"], int)
    leftovers = [p for p in tmp_path.iterdir() if p.name != "state.json"]
    assert len(leftovers) <= 12                            # at most one orphan temp per kill, never the target


# ---------------------------------------------------------------- HTTP / WebSocket load
async def test_oversized_bodies_are_refused(tmp_path):
    ctx = make_ctx(tmp_path)
    async with running(ctx) as (srv, local, remote):
        async with session() as s:
            big = b'{"title": "' + b"x" * (5 * 1024 * 1024) + b'"}'
            async with s.post(local + "/api/projects", data=big, headers={"Content-Type": "application/json"}) as r:
                assert r.status == 413
            huge = b"x" * (17 * 1024 * 1024)
            async with s.post(local + "/api/projects", data=huge) as r:
                assert r.status == 413
            async with s.post(remote + "/api/pair", data=huge) as r:           # unauthenticated: same cap
                assert r.status in (403, 413, 429)
            async with s.get(local + "/api/hello") as r:
                assert r.status == 200


async def test_many_websockets_and_a_slow_loris_do_not_block_others(tmp_path):
    ctx = make_ctx(tmp_path)
    async with running(ctx) as (srv, local, remote):
        dev, token = ctx.devices.add("tablet")
        base = len(ctx.bus.subscribers)                          # internal subscribers of the server itself
        socks = []
        loop = asyncio.get_running_loop()
        for port in (srv.ports["local"], srv.ports["remote"]):
            for _ in range(150):                                # half-sent request lines, never finished
                so = socket.socket()
                so.setblocking(False)
                await loop.sock_connect(so, ("127.0.0.1", port))
                await loop.sock_sendall(so, b"GET /api/hello HTTP/1.1\r\nHost: 127.0.0.1\r\nX-a: ")
                socks.append(so)
        async with session(connector=aiohttp.TCPConnector(limit=0)) as s:     # > 100 sockets at once
            wss = []
            for i in range(200):
                url = (local if i % 2 else remote) + "/api/ws"
                h = {} if i % 2 else {"Authorization": f"Bearer {token}"}
                wss.append(await s.ws_connect(url, headers=h))
            for w in wss[:5]:
                assert (await w.receive_json(timeout=5))["type"] == "hello"
            t0 = time.monotonic()
            for _ in range(50):
                ctx.publish("toast", {"level": "info", "text": "burst"})
            async with s.post(local + "/api/projects", json={"title": "still alive"}) as r:
                assert r.status == 201
            assert time.monotonic() - t0 < 5
            got = 0
            for w in wss[-10:]:
                while True:
                    m = await w.receive_json(timeout=5)
                    if m["type"] == "project.updated" or m["type"] == "toast":
                        got += 1
                        break
            assert got == 10
            for w in wss:
                await w.close()
        for so in socks:
            so.close()
        await asyncio.sleep(0.2)
        for _ in range(50):
            if len(ctx.bus.subscribers) <= base:
                break
            await asyncio.sleep(0.1)
        assert len(ctx.bus.subscribers) == base                 # every closed socket unsubscribed


# ---------------------------------------------------------------- children killed with -9
async def test_lean_child_killed_with_9_gives_a_failed_check_not_a_crash(tmp_path):
    from madalean.runtime import lean as lean_rt
    from madalean.slots import Slots
    from madalean.workspaces import Workspace
    sysroot = tmp_path / "tc"
    (sysroot / "bin").mkdir(parents=True)
    fake = sysroot / "bin" / "lean"
    fake.write_text("#!/bin/sh\nsleep 60\n")
    fake.chmod(0o755)

    class W(Workspace):
        @property
        def sysroot(self):
            return sysroot
    ws = W("w", "w", tmp_path, "x", True)
    ws.check = lambda: []
    runner = lean_rt.LeanRunner(Slots({"lean": 1}), tmp_path)
    task = asyncio.create_task(runner.check("theorem t : True := trivial", ws, timeout_s=30))
    for _ in range(100):
        if runner.running:
            break
        await asyncio.sleep(0.05)
    pid = next(iter(runner.running.values()))["pid"]
    os.kill(pid, signal.SIGKILL)
    res = await asyncio.wait_for(task, 20)
    assert not res.verdict.ok and runner.running == {} and runner.procs == {}
