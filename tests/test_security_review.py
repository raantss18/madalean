"""S-H independent security review (docs/SECURITY.md): regression tests for every finding fixed in the review.

- F1 (critical) Lean exec gate bypass `attribute [command_elab …] f` + `#check` → deny list extended AND every Lean
  process sandboxed (bubblewrap: no network, no home, read-only)
- F2 (high) CSRF from any other web server of the machine (Origin = any loopback port was trusted) + cross-site
  GETs/no-cors requests (Fetch Metadata) on the trusted listener
- F3 (medium) paired device could point `model_path` at any file (llama.cpp GGUF parser on attacker bytes)
- F4 (high) D29 never implemented: automatic installs from a dev checkout / temp config dir / with ~/.elan"""
from __future__ import annotations

import re
import shutil
from pathlib import Path

import aiohttp
import pytest

from madalean import leancheck, leansandbox
from madalean.server.app import make_app
from helpers import make_ctx, running, session


# ---------------------------------------------------------------- F1: Lean code-execution gate
POC = '''import Mathlib
open Lean Elab Command in
def myElab : CommandElab := fun _ => do
  let s := "#eval (" ++ "I" ++ "O.FS.writeFile \\"/tmp/x\\" \\"x\\")"
  match Parser.runParserCategory (← getEnv) `command s with
  | .ok c => elabCommand c
  | .error e => throwError e
attribute [command_elab Lean.Parser.Command.check] myElab
#check 1
'''

BYPASSES = [
    POC,
    "import Mathlib\nattribute [command_elab Lean.Parser.Command.check] f\n#check 1",
    "import Mathlib\nattribute   [ local tactic Lean.Parser.Tactic.done ] f",
    "import Mathlib\nsimproc foo (Nat.succ _) := fun e => do return .continue",
    "import Mathlib\ndsimproc foo (Nat.succ _) := fun e => do return .continue",
    "import Mathlib\nopen Lean Meta in\ndef f : MetaM Unit := pure ()",
    "import Mathlib\ndef f := Lean.loadDynlib \"/tmp/x.so\"",
    "import Mathlib\ndef f := Lean.saveModuleData \"/tmp/x\" `x default",
    "import Mathlib\n#guard (match unsafeIO (pure ()) with | _ => true)",
    "import Mathlib\ndef f : Nat := unsafeCast ()",
    "import Mathlib\n@[norm_num _ + _] def ext := 0",
    "import Mathlib\n@[aesop safe tactic] def t := 0",
    "import Mathlib\nopen Lean Elab Tactic in\ndef t := evalTactic default",
    "import Mathlib\n#eval/- c -/ 1",                   # the comment ends the token: `#eval` is still seen
    "import Mathlib\n  #eval 1",
    "import  Lean.Elab\n",
    "import Mathlib\nimport\n  Lake\n",
]


@pytest.mark.parametrize("code", BYPASSES)
def test_exec_gate_refuses_known_bypasses(code):
    assert leancheck.exec_risks(code), code


@pytest.mark.parametrize("code", [
    "import Mathlib\ntheorem t (a b : ℕ) : a + b = b + a := by omega",
    "import Mathlib\nopen Real in\ntheorem t : Real.sqrt 4 = 2 := by\n  rw [show (4:ℝ) = 2 ^ 2 by norm_num]\n  simp",
    "import Mathlib\n@[simp] theorem t : (1 : ℕ) + 1 = 2 := rfl\nattribute [local simp] Nat.add_comm",
    "import Mathlib\n-- #eval in a comment\n/- elab, macro, IO -/\ntheorem t : \"IO\".length = 2 := by decide",
])
def test_exec_gate_keeps_ordinary_mathematics(code):
    assert leancheck.exec_risks(code) == []


class _FakeWs:
    def __init__(self, path: Path):
        self.path, self.sysroot = path, None

    def lean_path(self):
        return []

    def env(self):
        return {"LEAN_PATH": ""}


@pytest.mark.skipif(not leansandbox.bwrap(), reason="bubblewrap unavailable (user namespaces off?)")
def test_lean_sandbox_has_no_network_no_home_and_is_read_only(tmp_path):
    import subprocess
    ws = tmp_path / "ws"
    ws.mkdir()
    secret = tmp_path / "secret.json"
    secret.write_text("KEY")
    probe = ws / "probe.sh"
    probe.write_text(f"cat {secret} && echo LEAK; cat /proc/net/dev; touch {ws}/w && echo WROTE; "
                     f"ls {Path.home()}/.config >/dev/null 2>&1 && echo HOME\n")
    argv = leansandbox.wrap(_FakeWs(ws), ["/bin/sh", str(probe)], [probe])
    assert "--unshare-all" in argv and "--die-with-parent" in argv
    r = subprocess.run(argv, capture_output=True, text=True, timeout=30, env=leansandbox.lean_env(_FakeWs(ws)))
    out = r.stdout
    assert "LEAK" not in out and "WROTE" not in out and "HOME" not in out
    ifaces = [ln.split(":")[0].strip() for ln in out.splitlines() if ":" in ln and "|" not in ln]
    assert ifaces == ["lo"], out
    assert leansandbox.status()["network"] == "blocked"


def test_lean_env_carries_no_secret(monkeypatch, tmp_path):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-xxx")
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_xxx")
    e = leansandbox.lean_env(_FakeWs(tmp_path))
    assert "ANTHROPIC_API_KEY" not in e and "GITHUB_TOKEN" not in e and e["HOME"] == "/nonexistent"


async def test_checker_refuses_the_poc_before_compiling(tmp_path):
    from madalean.runtime.lean import LeanRunner
    from madalean.slots import Slots
    from madalean.workspaces import Workspace
    runner = LeanRunner(Slots({"lean": 1}), tmp_path)
    res = await runner.check(POC, Workspace("x", "x", tmp_path, "leanprover/lean4:v0", True))
    assert not res.verdict.ok and res.verdict.reasons and res.stdout == ""


# ---------------------------------------------------------------- F2: CSRF / Fetch Metadata on the trusted listener
def _routes(app):
    out = []
    for r in app.router.routes():
        info = r.resource.get_info() if r.resource else {}
        path = info.get("path") or info.get("formatter")
        if path:
            out.append((r.method, path))
    return out


def concrete(path: str) -> str:
    return re.sub(r"\{[^}]+\}", "x1", path.replace("{tail:.*}", "x1"))


async def test_every_state_changing_local_route_refuses_foreign_origins(tmp_path):
    ctx = make_ctx(tmp_path)
    routes = _routes(make_app(ctx))
    async with running(ctx) as (srv, local, _remote):
        port = srv.ports["local"]
        bad_origins = ["https://evil.example", "null", f"http://127.0.0.1:{port + 1}", "http://localhost:8888",
                       f"http://127.0.0.1.evil.example:{port}", f"http://[::1]:{port + 2}"]
        checked = 0
        async with session() as s:
            for method, path in routes:
                for m in (["POST", "PUT", "PATCH", "DELETE"] if method == "*" else [method]):
                    if m in ("GET", "HEAD", "OPTIONS"):
                        continue
                    for o in bad_origins:
                        for ct in ("application/json", "text/plain", "application/x-www-form-urlencoded"):
                            async with s.request(m, local + concrete(path), data=b"{}",
                                                 headers={"Origin": o, "Content-Type": ct}) as r:
                                assert r.status == 403, (m, path, o, r.status)
                            checked += 1
        assert checked > 1000


async def test_fetch_metadata_blocks_cross_site_subresources_but_not_navigation(tmp_path):
    static = tmp_path / "static"
    static.mkdir()
    (static / "index.html").write_text("<!doctype html><title>UI</title>")
    ctx = make_ctx(tmp_path)
    started = []

    async def no_start(*a, **k):
        started.append(1)
        return {}
    ctx.jupyter._ensure = no_start
    async with running(ctx, static_dir=static) as (srv, local, remote):
        async with session() as s:
            for site in ("cross-site", "same-site"):
                for path in ("/api/state", "/api/settings", "/jupyter/api/contents", "/api/library/export",
                             "/api/models"):
                    h = {"Sec-Fetch-Site": site, "Sec-Fetch-Mode": "no-cors", "Sec-Fetch-Dest": "image"}
                    async with s.get(local + path, headers=h) as r:
                        assert r.status == 403 and (await r.json())["error"] == "cross_site", (site, path)
                nav = {"Sec-Fetch-Site": site, "Sec-Fetch-Mode": "navigate", "Sec-Fetch-Dest": "document"}
                async with s.get(local + "/", headers=nav) as r:
                    assert r.status == 200                          # a link to the UI from elsewhere still works
                async with s.get(local + "/api/state", headers=nav) as r:
                    assert r.status == 403
                async with s.get(local + "/jupyter/lab", headers=nav) as r:
                    assert r.status == 403
                async with s.post(local + "/api/projects", json={"title": "x"},
                                  headers={**nav, "Origin": f"http://127.0.0.1:{srv.ports['local']}"}) as r:
                    assert r.status == 403
            assert started == []                                    # Jupyter was never started cross-site
            same = {"Sec-Fetch-Site": "same-origin", "Sec-Fetch-Mode": "cors",
                    "Origin": f"http://127.0.0.1:{srv.ports['local']}"}
            async with s.post(local + "/api/projects", json={"title": "x"}, headers=same) as r:
                assert r.status == 201
            async with s.get(local + "/api/state", headers={"Sec-Fetch-Site": "none"}) as r:
                assert r.status == 200
            # the shells open /api/session?ticket=… from their bundled (cross-site) page: a navigation
            async with s.get(remote + "/api/session?ticket=nope", allow_redirects=False,
                             headers={"Sec-Fetch-Site": "cross-site", "Sec-Fetch-Mode": "navigate"}) as r:
                assert r.status == 303


async def test_websocket_from_another_local_port_is_refused(tmp_path):
    ctx = make_ctx(tmp_path)
    async with running(ctx) as (srv, local, _remote):
        async with session() as s:
            for o in (f"http://127.0.0.1:{srv.ports['local'] + 1}", "http://localhost:3000"):
                try:
                    async with s.ws_connect(local + "/api/ws", headers={"Origin": o}):
                        raise AssertionError("connected")
                except aiohttp.WSServerHandshakeError as e:
                    assert e.status == 403
            async with s.ws_connect(local + "/api/ws",
                                    headers={"Origin": f"http://127.0.0.1:{srv.ports['local']}"}) as ws:
                assert (await ws.receive_json())["type"] == "hello"


async def test_no_cors_headers_and_preflight_gets_nothing(tmp_path):
    ctx = make_ctx(tmp_path)
    async with running(ctx) as (srv, local, remote):
        async with session() as s:
            for base in (local, remote):
                async with s.options(base + "/api/projects", headers={
                        "Origin": "https://evil.example", "Access-Control-Request-Method": "POST",
                        "Access-Control-Request-Private-Network": "true"}) as r:
                    assert not any(k.lower().startswith("access-control-") for k in r.headers)


async def test_remote_forwarded_headers_do_not_grant_local_or_origin(tmp_path):
    ctx = make_ctx(tmp_path)
    async with running(ctx) as (srv, local, remote):
        dev, token = ctx.devices.add("phone")
        async with session() as s:
            h = {"X-Forwarded-For": "127.0.0.1", "X-Real-IP": "127.0.0.1", "X-Forwarded-Host": "127.0.0.1:11500",
                 "Host": "127.0.0.1"}
            async with s.post(remote + "/api/pairing/start", headers=h) as r:
                assert r.status == 401
            async with s.post(remote + "/api/pairing/start", headers={**h, "Authorization": f"Bearer {token}"}) as r:
                assert r.status == 403 and (await r.json())["error"] == "host_only"
            async with s.patch(remote + "/api/settings", json={"agent_exec": True},
                               headers={"Authorization": f"Bearer {token}"}) as r:
                assert r.status == 403
            # X-Forwarded-Host is never an Origin allow-list on the local listener
            async with s.post(local + "/api/projects", json={"title": "x"},
                              headers={"Origin": "https://evil.example", "X-Forwarded-Host": "evil.example"}) as r:
                assert r.status == 403


async def test_paired_device_reaches_no_host_only_route(tmp_path):
    """Every route marked host-only, and every host-only setting, answers 403 to a valid device token."""
    from madalean.context import HOST_ONLY_SETTINGS
    ctx = make_ctx(tmp_path)
    app = make_app(ctx)
    host_only = [(r.method, (r.resource.get_info().get("path") or r.resource.get_info().get("formatter")))
                 for r in app.router.routes()
                 if getattr(r.handler, "__madalean_host_only__", False)]
    assert len(host_only) >= 15
    names = {p for _m, p in host_only}
    for must in ("/api/updates/install", "/api/selfupdate/install", "/api/net/start", "/api/net/stop",
                 "/api/pairing/start", "/api/devices"):
        assert must in names, must
    async with running(ctx) as (srv, local, remote):
        dev, token = ctx.devices.add("phone")
        h = {"Authorization": f"Bearer {token}"}
        async with session() as s:
            for m, p in host_only:
                async with s.request(m, remote + concrete(p), data=b"{}", headers=h) as r:
                    assert r.status == 403, (m, p, r.status)
            for k in sorted(HOST_ONLY_SETTINGS):
                async with s.patch(remote + "/api/settings", json={k: True}, headers=h) as r:
                    assert r.status in (400, 403), k
            for p in ("/api/jupyter/start", "/jupyter/api/contents", "/api/conjectures/x1/experiments/x1/run"):
                async with s.post(remote + p, data=b"{}", headers=h) as r:
                    assert r.status in (403, 404), (p, r.status)


# ---------------------------------------------------------------- F3: model_path
def test_model_path_outside_the_scanned_models_is_ignored(tmp_path):
    from madalean.gguf import GGUFInfo
    from madalean.runtime.llama import pick_model
    good = tmp_path / "Goedel-Prover-V2-8B.Q4_K_M.gguf"
    good.write_bytes(b"x")
    evil = tmp_path / "upload.bin"
    evil.write_bytes(b"GGUF")
    ms = [GGUFInfo(good, 1, good.name, "qwen3", "Q4_K_M", 1, 1, 1, 1, 1)]
    assert pick_model("prover", ms, str(evil)) == good
    assert pick_model("prover", ms, "/etc/passwd") == good
    assert pick_model("prover", ms, str(good)) == good


# ---------------------------------------------------------------- F4: D29
def test_d29_no_automatic_install_from_a_dev_checkout_or_temp_config(tmp_path, monkeypatch):
    from madalean import config, deps
    from madalean.runtime import updates_mgr as um
    assert um.auto_install_blocked(tmp_path / "config") in ("dev_checkout", "custom_config_dir")
    # an installed layout, but a non-default config dir: still blocked
    home = tmp_path / "prefix"
    (home / "versions" / "2.0.1").mkdir(parents=True)
    (home / "elan" / "bin").mkdir(parents=True)
    (home / "elan" / "bin" / "elan").write_text("")
    monkeypatch.setenv("MADALEAN_HOME", str(home))
    monkeypatch.setattr(config, "STATION_DIR", home / "versions" / "2.0.1")
    monkeypatch.setattr(config, "ELAN_HOME", deps.elan_home())
    assert um.auto_install_blocked(tmp_path / "config") == "custom_config_dir"
    assert um.auto_install_blocked(Path.home() / ".config" / "madalean") is None
    # the prefix elan missing → config.ELAN_HOME falls back to ~/.elan → never automatic, never installable
    monkeypatch.setattr(config, "ELAN_HOME", Path.home() / ".elan")
    assert um.auto_install_blocked(Path.home() / ".config" / "madalean") == "no_prefix_elan"
    assert not um.prefix_elan_ok()


async def test_d29_lean_installs_never_use_home_elan(tmp_path, monkeypatch):
    from madalean import config, updates
    from madalean.runtime.updates_mgr import UpdatesManager
    monkeypatch.setattr(config, "ELAN_HOME", Path.home() / ".elan")
    spawned = []

    async def fake_exec(*a, **k):
        spawned.append(a)
        raise AssertionError("must not start the updater")
    monkeypatch.setattr("asyncio.create_subprocess_exec", fake_exec)
    m = UpdatesManager(tmp_path / "u.json", lambda *a: None, lambda *a: None, lambda: False)
    for kind in ("mathlib", "toolchain", "lake-package"):
        c = updates.Candidate(kind, f"k:{kind}", "x", "1", "2", True, "", 0, {})
        m.state["candidates"] = [c.__dict__]
        assert await m.install(c.key) == "no_prefix_elan"
    assert spawned == []
    assert shutil.which  # keep import used


# ---------------------------------------------------------------- F6: experiment kernels have no network
@pytest.mark.skipif(not (shutil.which("jupyter-lab") and shutil.which("bwrap")), reason="jupyter-lab / bwrap missing")
async def test_experiment_kernel_cannot_reach_the_trusted_listener_or_the_network(tmp_path):
    from madalean.research.sagebridge import SageBridge
    ctx = make_ctx(tmp_path)
    async with running(ctx) as (srv, local, _remote):
        b = SageBridge(ctx)
        if not b.available().get("python"):
            pytest.skip("no python3 kernelspec")
        port = srv.ports["local"]
        jtok = ctx.jupyter.runtime_dir
        code = ("import socket, os, glob\n"
                f"s = socket.socket()\ns.settimeout(3)\n"
                f"try:\n    s.connect(('127.0.0.1', {port})); print('REACHED')\n"
                "except OSError as e:\n    print('BLOCKED', type(e).__name__)\n"
                "print('IFACES', sorted(l.split(':')[0].strip() for l in open('/proc/net/dev') if ':' in l))\n"
                f"print('JUP', os.path.exists({str(jtok / 'config' / 'jupyter_server_config.json')!r}))\n"
                "print('RUN', os.listdir('/run'))\n"
                "report('holds', cases=0)\n")
        try:
            r = await b.run("c", "python", code, timeout=60)
            assert r.status == "ok", (r.status, r.error, r.stdout)
            assert "REACHED" not in r.stdout and "BLOCKED" in r.stdout, r.stdout
            assert "IFACES ['lo']" in r.stdout and "JUP False" in r.stdout and "RUN []" in r.stdout, r.stdout
        finally:
            await b.close()
