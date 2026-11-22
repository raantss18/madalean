"""Self-extracting graphical installer (S-AL, D44): build, integrity check, local wizard server, dry run.

Nothing is installed: the embedded install.sh is a fake that prints install.sh-like steps."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tarfile
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FAKE_INSTALL = """#!/usr/bin/env bash
# fake install.sh: prints the step lines the wizard parses, records its arguments
echo "ARGS $*" > "$(dirname "$0")/args.txt"
for i in 1 2 3; do echo "==> $i/3 étape $i"; echo "ligne $i"; done
[ -n "${FAKE_FAIL:-}" ] && { echo "boom"; exit 7; }
exit 0
"""


def make_tarball(tmp: Path, fail: bool = False) -> Path:
    src = tmp / "tree" / "madalean"
    for rel in ("madalean/__init__.py", "madalean/deps/__init__.py", "madalean/deps/assistant.py",
                "packaging/installer/server.py", "packaging/installer/web/index.html",
                "packaging/installer/web/wizard.css", "packaging/installer/web/wizard.js",
                "packaging/installer/web/wordmark.svg", "packaging/installer/web/wordmark-dark.svg",
                "packaging/installer/web/icon.svg"):
        (src / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / rel, src / rel)
    (src / "install.sh").write_text(FAKE_INSTALL)
    (src / "install.sh").chmod(0o755)
    out = tmp / "madalean-server.tar.gz"
    with tarfile.open(out, "w:gz") as t:
        t.add(src, arcname="madalean")
    return out


def build(tmp: Path) -> Path:
    tb = make_tarball(tmp)
    r = subprocess.run(["bash", str(ROOT / "scripts" / "build_installer.sh"), "--tarball", str(tb), "--out",
                        str(tmp / "out")], capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr + r.stdout
    run = tmp / "out" / "Madalean-installer.run"
    assert run.is_file() and os.access(run, os.X_OK)
    return run


def test_build_check_and_tampered_payload_refused(tmp_path):
    run = build(tmp_path)
    r = subprocess.run([str(run), "--check"], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0 and "OK" in r.stdout
    # extract: the sources come out, the fake install.sh included
    r = subprocess.run([str(run), "--extract", str(tmp_path / "x")], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0 and (tmp_path / "x" / "install.sh").is_file()
    assert (tmp_path / "x" / "packaging" / "installer" / "server.py").is_file()
    # flip one byte of the payload: refused before anything is unpacked
    data = bytearray(run.read_bytes())
    data[-100] ^= 0xFF
    bad = tmp_path / "bad.run"
    bad.write_bytes(bytes(data))
    bad.chmod(0o755)
    r = subprocess.run([str(bad), "--extract", str(tmp_path / "y")], capture_output=True, text=True, timeout=60)
    assert r.returncode != 0 and "SHA-256" in r.stderr
    assert not (tmp_path / "y").exists()
    # truncated download
    short = tmp_path / "short.run"
    short.write_bytes(run.read_bytes()[:-5000])
    short.chmod(0o755)
    assert subprocess.run([str(short), "--check"], capture_output=True, timeout=60).returncode != 0


def test_yes_mode_runs_install_sh_non_interactively(tmp_path):
    run = build(tmp_path)
    r = subprocess.run([str(run), "--yes", "--prefix", "/nowhere"], capture_output=True, text=True, timeout=60,
                       stdin=subprocess.DEVNULL)
    assert r.returncode == 0, r.stderr
    assert "==> 3/3" in r.stdout


def _req(url, token=None, data=None, host=None, origin=None):
    h = {}
    if token:
        h["X-Install-Token"] = token
    if host:
        h["Host"] = host
    if origin:
        h["Origin"] = origin
    body = None
    if data is not None:
        body = json.dumps(data).encode()
        h["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=body, headers=h, method="POST" if data is not None else "GET")
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def start_server(tmp: Path, *args: str, fail: bool = False):
    run = build(tmp)
    x = tmp / "src"
    subprocess.run([str(run), "--extract", str(x)], check=True, capture_output=True, timeout=60)
    url_file = tmp / "url.txt"
    env = {**os.environ, "MADALEAN_SETUP_KERNEL_DIRS": str(tmp / "nokernels")}
    if fail:
        env["FAKE_FAIL"] = "1"
    p = subprocess.Popen([sys.executable, "-I", str(x / "packaging" / "installer" / "server.py"), "--src", str(x),
                          "--no-browser", "--url-file", str(url_file), *args, "--", "--prefix", str(tmp / "pfx")],
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env)
    for _ in range(100):
        if url_file.exists() and url_file.read_text():
            break
        time.sleep(0.1)
    url = url_file.read_text()
    base, token = url.split("/?t=")
    return p, base, token, x


def test_wizard_server_token_loopback_install_and_quit(tmp_path):
    p, base, token, x = start_server(tmp_path)
    try:
        assert base.startswith("http://127.0.0.1:")
        port = int(base.rsplit(":", 1)[1])
        # bound to loopback only
        out = subprocess.run(["ss", "-ltnH", f"sport = :{port}"], capture_output=True, text=True).stdout \
            if shutil.which("ss") else f"LISTEN 0 5 127.0.0.1:{port} 0.0.0.0:*"
        locals_ = [line.split()[3] for line in out.splitlines() if line.strip()]
        assert locals_ == [f"127.0.0.1:{port}"]
        assert _req(base + "/")[0] == 403                                  # page without the token
        assert _req(base + "/?t=wrong")[0] == 403
        st, body = _req(base + f"/?t={token}")
        assert st == 200 and b"wizard.js" in body
        assert _req(base + "/wizard.js")[0] == 200
        assert _req(base + "/api/state")[0] == 401                         # API without the token
        assert _req(base + "/api/state", token, host="evil.example:80")[0] == 403   # DNS rebinding
        for _ in range(100):
            st, body = _req(base + "/api/state", token)
            d = json.loads(body)
            if d["state"] == "ready":
                break
            time.sleep(0.1)
        assert d["state"] == "ready" and set(d["recommendation"]) == {"fr", "en"}
        assert d["madalean_url"] == "http://127.0.0.1:11500/"
        plan = d["recommendation"]["fr"]["plan"]
        assert _req(base + "/api/install", token, {"plan": {"models": "bogus"}})[0] == 400
        assert _req(base + "/api/install", token, {"plan": plan}, origin="http://evil.example")[0] == 403
        assert _req(base + "/api/install", "nope", {"plan": plan})[0] == 401
        st, _ = _req(base + "/api/install", token, {"plan": plan})
        assert st == 202
        for _ in range(100):
            pr = json.loads(_req(base + "/api/progress?since=0", token)[1])
            if pr["state"] != "running":
                break
            time.sleep(0.1)
        assert pr["state"] == "done" and pr["percent"] == 100 and pr["step"] == 3 and pr["total"] == 3
        assert any("ligne 3" in line for line in pr["lines"])
        args = (x / "args.txt").read_text()
        assert "--plan" in args and "--prefix" in args
        assert _req(base + "/api/quit", token, {})[0] == 200
        assert p.wait(timeout=10) == 0
    finally:
        p.kill()


def test_wizard_failure_is_reported_and_retry_allowed(tmp_path):
    p, base, token, _ = start_server(tmp_path, fail=True)
    try:
        for _ in range(100):
            d = json.loads(_req(base + "/api/state", token)[1])
            if d["state"] == "ready":
                break
            time.sleep(0.1)
        plan = d["default_plan"]
        assert _req(base + "/api/install", token, {"plan": plan})[0] == 202
        for _ in range(100):
            pr = json.loads(_req(base + "/api/progress", token)[1])
            if pr["state"] != "running":
                break
            time.sleep(0.1)
        assert pr["state"] == "failed" and pr["rc"] == 7 and pr["lines"][-1] == "boom"
        assert _req(base + "/api/install", token, {"plan": plan})[0] == 202      # « Réessayer »
    finally:
        p.kill()


def test_wizard_idle_shutdown(tmp_path):
    p, base, token, _ = start_server(tmp_path, "--idle", "1")
    try:
        assert p.wait(timeout=20) == 0
        with pytest.raises(OSError):
            urllib.request.urlopen(base + "/wizard.css", timeout=2)
    finally:
        p.kill()
