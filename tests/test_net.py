"""Embedded Tailscale node (session S-I): NetManager with a FAKE sidecar (no network, no tailnet), the host-only
/api/net routes, the remote Host allow-list, and — when the real binary is built — its version and the absence of
Funnel. A real tailnet login needs the user's approval and is never done by tests."""
from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from helpers import make_ctx, running, session
from madalean.runtime.net import NetManager

ROOT = Path(__file__).resolve().parents[1]
FAKE = r'''#!{py}
import json, os, signal, sys, time
args = sys.argv[1:]
def arg(k):
    return args[args.index(k) + 1]
mode = os.environ.get("FAKE_NET_MODE", "login")
def out(**kw):
    print(json.dumps({{"event": "status", "pid": os.getpid(), **kw}}), flush=True)
signal.signal(signal.SIGTERM, lambda *a: (out(state="stopped"), sys.exit(0)))
open(os.path.join(os.path.dirname(arg("--status-socket")), "argv.json"), "w").write(json.dumps(args))
out(state="starting", hostname=arg("--hostname"), target=arg("--target"))
if mode == "crash":
    sys.exit(3)
out(state="needs_login", auth_url="https://login.tailscale.com/a/fake123", hostname=arg("--hostname"))
if mode == "run":
    time.sleep(0.2)
    out(state="running", dns_name="madalean.tail1234.ts.net", url="https://madalean.tail1234.ts.net/",
        ips=["100.64.0.7"], cert_ok=True, tailnet="example.org")
while True:
    time.sleep(1)
'''


@pytest.fixture
def fake_net(tmp_path):
    p = tmp_path / "fake-madalean-net"
    p.write_text(FAKE.format(py=sys.executable))
    p.chmod(0o755)
    return p


async def _wait(cond, timeout=10):
    t0 = asyncio.get_running_loop().time()
    while not cond():
        if asyncio.get_running_loop().time() - t0 > timeout:
            raise TimeoutError
        await asyncio.sleep(0.05)


async def test_manager_login_url_and_stop(tmp_path, fake_net, monkeypatch):
    monkeypatch.setenv("FAKE_NET_MODE", "login")
    monkeypatch.setenv("TS_AUTHKEY", "tskey-should-not-leak")
    events = []
    nm = NetManager(lambda t, p: events.append((t, p)), state_dir=tmp_path / "ts", exe=str(fake_net))
    st = await nm.start(11501)
    assert st["running"]
    await _wait(lambda: nm.status().get("auth_url"))
    assert nm.status()["state"] == "needs_login"
    assert any(t == "net.status" and p["net"].get("auth_url") for t, p in events)
    argv = json.loads((tmp_path / "ts" / "argv.json").read_text())
    assert argv[argv.index("--target") + 1] == "127.0.0.1:11501"
    assert argv[argv.index("--hostname") + 1] == "madalean"
    assert int(argv[argv.index("--parent-pid") + 1]) == os.getpid()
    assert oct((tmp_path / "ts").stat().st_mode & 0o777) == "0o700"
    environ = Path(f"/proc/{nm.proc.pid}/environ").read_bytes()
    assert b"TS_AUTHKEY" not in environ and b"TS_NO_LOGS_NO_SUPPORT=true" in environ
    pid = nm.proc.pid
    await nm.stop()
    assert nm.status()["state"] == "stopped" and not nm.status()["running"]
    assert not Path(f"/proc/{pid}").exists() or Path(f"/proc/{pid}/stat").read_text().split()[2] == "Z"


async def test_manager_running_and_restart_after_crash(tmp_path, fake_net, monkeypatch):
    monkeypatch.setenv("FAKE_NET_MODE", "crash")
    nm = NetManager(lambda t, p: None, state_dir=tmp_path / "ts", exe=str(fake_net), max_restarts=1)
    await nm.start(11501)
    monkeypatch.setenv("FAKE_NET_MODE", "run")       # the restarted child works
    await _wait(lambda: nm.status().get("state") == "running", timeout=15)
    st = nm.status()
    assert st["dns_name"] == "madalean.tail1234.ts.net" and st["cert_ok"] and st["ips"] == ["100.64.0.7"]
    await nm.stop()


async def test_manager_without_binary(tmp_path, monkeypatch):
    monkeypatch.setenv("MADALEAN_HOME", str(tmp_path / "none"))
    monkeypatch.setenv("PATH", "/nonexistent")
    nm = NetManager(lambda t, p: None, state_dir=tmp_path / "ts")
    st = await nm.start(11501)
    assert st["state"] == "unavailable" and not st["available"]


def test_hostname_is_validated(tmp_path):
    assert NetManager(lambda t, p: None, state_dir=tmp_path, exe="x", hostname="Bad Name!").hostname == "madalean"
    assert NetManager(lambda t, p: None, state_dir=tmp_path, exe="x", hostname="maths-pc").hostname == "maths-pc"


async def test_net_routes_host_only_and_remote_host_allow_list(tmp_path, monkeypatch):
    monkeypatch.setenv("MADALEAN_NO_NET", "1")
    ctx = make_ctx(tmp_path)
    async with running(ctx) as (srv, local, remote):
        async with session() as s:
            async with s.get(local + "/api/net") as r:
                assert r.status == 200
                d = await r.json()
                assert d["settings"] == {"enabled": True, "hostname": "madalean"} and d["state"] in ("stopped",)
            async with s.patch(local + "/api/net", json={"hostname": "bad name"}) as r:
                assert r.status == 400
            async with s.patch(local + "/api/net", json={"hostname": "maths-pc", "enabled": False}) as r:
                assert r.status == 200 and (await r.json())["settings"]["hostname"] == "maths-pc"
            assert json.loads((ctx.paths.config / "net.json").read_text())["enabled"] is False
            async with s.get(local + "/api/deps") as r:
                d = await r.json()
                assert r.status == 200 and {c["component"] for c in d["components"]} >= {"env", "madalean-net"}
            # remote listener: host-only routes refused, foreign Host refused (DNS rebinding), tailnet names accepted
            async with s.get(remote + "/api/net") as r:
                assert r.status in (401, 403)
            async with s.get(remote + "/api/hello", headers={"Host": "evil.example"}) as r:
                assert r.status == 403 and (await r.json())["error"] == "bad_host"
            for h in ("madalean.tail1234.ts.net", f"127.0.0.1:{srv.ports['remote']}"):
                async with s.get(remote + "/api/hello", headers={"Host": h}) as r:
                    assert r.status == 200, h
            async with s.post(local + "/api/deps/sage/rollback") as r:
                assert r.status == 409
            async with s.post(remote + "/api/deps/sage/install", headers={"Host": "madalean.x.ts.net"}) as r:
                assert r.status in (401, 403)


@pytest.mark.skipif(not (ROOT / "dist" / "madalean-net" / "madalean-net-linux-amd64").exists(),
                    reason="madalean-net not built (net/build.sh)")
def test_real_binary_version_and_static():
    exe = ROOT / "dist" / "madalean-net" / "madalean-net-linux-amd64"
    out = subprocess.run([str(exe), "version"], capture_output=True, text=True, timeout=30).stdout
    assert out.startswith("madalean-net ") and "tailscale 1." in out
    if shutil.which("file"):
        assert "statically linked" in subprocess.run(["file", str(exe)], capture_output=True, text=True).stdout
    assert b"ListenFunnel(" not in (ROOT / "net" / "main.go").read_bytes()
