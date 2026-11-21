"""`python -m madalean serve --demo` as a real process: pair/status commands, single instance, graceful SIGTERM,
and children (jupyter-lab) killed even when the server itself is killed with SIGKILL."""
from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def start(tmp_path: Path, *extra: str) -> tuple[subprocess.Popen, dict]:
    env = {**os.environ, "MADALEAN_NO_KEYRING": "1", "HOME": os.environ["HOME"]}
    p = subprocess.Popen([sys.executable, "-m", "madalean", "serve", "--demo", "--port", "0", "--remote-port", "0",
                          "--config-dir", str(tmp_path / "cfg"), "--cache-dir", str(tmp_path / "cache"), *extra],
                         cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    info = tmp_path / "cfg" / "server.json"
    for _i in range(300):
        if info.exists():
            return p, json.loads(info.read_text())
        if p.poll() is not None:
            raise AssertionError(p.stdout.read())
        time.sleep(0.05)
    p.kill()
    raise AssertionError("server did not start")


def cli(tmp_path, *args) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-m", "madalean", *args, "--config-dir", str(tmp_path / "cfg")], cwd=ROOT,
                          capture_output=True, text=True, timeout=60)


def get(url, method="GET", data=None):
    req = urllib.request.Request(url, method=method, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(req, timeout=60) as r:
        return json.loads(r.read())


def test_demo_server_pair_status_and_sigterm(tmp_path):
    p, info = start(tmp_path)
    try:
        r = cli(tmp_path, "pair")
        assert r.returncode == 0 and "pairing code" in r.stdout
        code = r.stdout.split(":")[1].split()[0]
        assert len(code) == 6 and code.isdigit()
        r = cli(tmp_path, "status")
        assert r.returncode == 0 and "(demo)" in r.stdout
        n = int(r.stdout.split("dossiers: ", 1)[1].split(",")[0])
        assert n >= 2                     # demo seeds; other sessions (research workshop) seed more
        second = subprocess.run([sys.executable, "-m", "madalean", "serve", "--demo", "--port", "0", "--remote-port",
                                 "0", "--config-dir", str(tmp_path / "cfg")], cwd=ROOT, capture_output=True, text=True,
                                timeout=60)
        assert second.returncode == 2 and "another server" in second.stderr
        st = get(f"http://127.0.0.1:{info['local']}/api/state")
        assert st["demo"] and len(st["projects"]) >= 1
        d = get(f"http://127.0.0.1:{info['local']}/api/dossiers", "POST",
                json.dumps({"problem": "Montrer que la somme de deux entiers pairs est paire."}).encode())
        assert d["job"]["state"] in ("queued", "running")
        time.sleep(1.0)
    finally:
        p.send_signal(signal.SIGTERM)
        out, _e = p.communicate(timeout=30)
    assert p.returncode == 0, out
    assert not (tmp_path / "cfg" / "server.json").exists()
    assert (tmp_path / "cfg" / "logs" / "server.log").exists()


@pytest.mark.skipif(not shutil.which("jupyter-lab"), reason="jupyter-lab not installed")
def test_children_die_with_a_killed_server(tmp_path):
    p, info = start(tmp_path)
    try:
        st = get(f"http://127.0.0.1:{info['local']}/api/jupyter/start", "POST", b"{}")
        assert st["state"] == "ready", st
        pid = None
        for proc in Path("/proc").iterdir():
            if proc.name.isdigit():
                try:
                    stat = (proc / "stat").read_text()
                except OSError:
                    continue
                if int(stat.rsplit(")", 1)[1].split()[1]) == p.pid and "jupyter" in (proc / "cmdline").read_bytes().decode(errors="replace"):
                    pid = int(proc.name)
        assert pid, "jupyter-lab child not found"
    finally:
        p.kill()
        p.wait(timeout=10)
    for _i in range(100):
        if not Path(f"/proc/{pid}").exists() or "Z" in Path(f"/proc/{pid}/stat").read_text().split()[2]:
            break
        time.sleep(0.1)
    else:
        os.kill(pid, signal.SIGKILL)
        raise AssertionError("jupyter-lab survived the server")
