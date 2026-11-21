"""Madalean self-update (ARCHITECTURE §16) against a local fake release server: a good release (signed, health-checked
for real by starting it in demo mode, switched, rolled back), a tampered one, an unsigned one, one signed by another
key; Ed25519 (pure Python and `cryptography` agree with openssl); automatic updates only at a quiet moment; the
« Installer » action for system packages builds the terminal command without opening anything."""
import asyncio
import base64
import hashlib
import io
import json
import os
import shutil
import subprocess
import tarfile
from pathlib import Path

import pytest
from aiohttp import web

from helpers import make_ctx, running, session
from madalean import config, updates
from madalean.update_checkers import selfupdate as su
from madalean.update_checkers import system as sysc

ROOT = config.STATION_DIR


def keypair(tmp: Path) -> tuple[Path, bytes]:
    key = tmp / "k.pem"
    subprocess.run(["openssl", "genpkey", "-algorithm", "ed25519", "-out", str(key)], check=True, capture_output=True)
    der = subprocess.run(["openssl", "pkey", "-in", str(key), "-pubout", "-outform", "DER"], check=True,
                         capture_output=True).stdout
    return key, der[-32:]


def sign(key: Path, data: bytes, tmp: Path) -> str:
    f = tmp / "msg"
    f.write_bytes(data)
    sig = subprocess.run(["openssl", "pkeyutl", "-sign", "-inkey", str(key), "-rawin", "-in", str(f)], check=True,
                         capture_output=True).stdout
    return base64.b64encode(sig).decode() + "\n"


def build_release(tmp: Path, version: str) -> bytes:
    """A real Madalean tree (this checkout's package) whose version is `version`."""
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as t:
        for p in (ROOT / "madalean").rglob("*"):
            if "__pycache__" in p.parts or not p.is_file():
                continue
            arc = f"madalean-{version}/" + str(p.relative_to(ROOT))
            if p == ROOT / "madalean" / "__init__.py":
                data = p.read_bytes().replace(b'__version__ = "2.0.0.dev0"', f'__version__ = "{version}"'.encode())
                ti = tarfile.TarInfo(arc)
                ti.size = len(data)
                t.addfile(ti, io.BytesIO(data))
            else:
                t.add(p, arcname=arc)
    return buf.getvalue()


def test_ed25519_implementations_agree_with_openssl(tmp_path):
    key, pub = keypair(tmp_path)
    msg = b"abc  madalean-9.9.9.tar.gz\n"
    sig_b64 = sign(key, msg, tmp_path)
    sig = base64.b64decode(sig_b64)
    assert su.ed25519_verify_pure(pub, msg, sig) and su.ed25519_verify(pub, msg, sig)
    assert not su.ed25519_verify_pure(pub, msg + b"x", sig) and not su.ed25519_verify(pub, msg + b"x", sig)
    bad = bytes([sig[0] ^ 1]) + sig[1:]
    assert not su.ed25519_verify_pure(pub, msg, bad)
    assert su.signature_valid(pub, msg, sig_b64) and not su.signature_valid(su.PUBLIC_KEY, msg, sig_b64)
    assert not su.signature_valid(pub, msg, "not base64!") and not su.signature_valid(pub, msg, "")
    sums = "0" * 64 + "  madalean-9.9.9.tar.gz\n" + "1" * 64 + " *other\n"
    assert su.expected_sha(sums, "madalean-9.9.9.tar.gz") == "0" * 64 and su.expected_sha(sums, "madalean") is None
    assert su.newer("v2.0.0", "2.0.0.dev0") and su.newer("2.0.1", "2.0.0") and not su.newer("2.0.0.dev0", "2.0.0")
    assert len(su.PUBLIC_KEY) == 32


def test_sign_release_script_uses_private_key_outside_git(tmp_path):
    key, pub = keypair(tmp_path)
    d = tmp_path / "rel"
    d.mkdir()
    (d / "madalean-9.9.9.tar.gz").write_bytes(b"x")
    r = subprocess.run([str(ROOT / "scripts" / "sign_release.sh"), str(d)], capture_output=True, text=True,
                       env={**os.environ, "MADALEAN_RELEASE_KEY": str(key)})
    # signed with a key that is not the embedded one: the script itself refuses it
    assert r.returncode == 1 and "does NOT match" in r.stdout
    assert su.signature_valid(pub, (d / "SHA256SUMS").read_bytes(), (d / "SHA256SUMS.sig").read_text())
    assert ".config/madalean/release-keys" in (ROOT / "scripts" / "sign_release.sh").read_text()
    out = subprocess.run(["git", "-C", str(ROOT), "ls-files", "*.pem"], capture_output=True, text=True).stdout
    assert out.strip() == ""                                   # no private key in git


class FakeGitHub:
    def __init__(self, tmp: Path):
        self.tmp, self.files, self.release, self.channel = tmp, {}, {}, {}

    def publish(self, version: str, key: Path | None, tamper: bool = False):
        name = f"madalean-{version}.tar.gz"
        tar = build_release(self.tmp, version)
        self.good = tar
        sums = f"{hashlib.sha256(tar).hexdigest()}  {name}\n".encode()
        self.files = {name: tar, "SHA256SUMS": sums}
        if key is not None:
            self.files["SHA256SUMS.sig"] = sign(key, sums, self.tmp).encode()
        if tamper:
            self.files[name] = tar[:-10] + b"\x00" * 10                # modified after signing
        self.release = {"tag_name": f"v{version}", "html_url": "https://example/release", "body": "notes",
                        "assets": [{"name": n, "browser_download_url": f"{self.base}/dl/{n}"} for n in self.files]}

    def publish_manifest(self, version: str, key: Path, tamper_archive=False, bad_sig_key=None, min_version="2.0.0"):
        """The signed channel stable.json (+ .sig) pointing at the release asset (as scripts/sign_release.sh)."""
        self.publish(version, key, tamper=tamper_archive)
        name = f"madalean-{version}.tar.gz"
        good = self.good
        m = {"version": version, "published": "2026-11-21T00:00:00+00:00", "notes_url": "https://x",
             "min_version": min_version, "files": [{"name": name, "url": f"{self.base}/dl/{name}",
                                                    "sha256": hashlib.sha256(good).hexdigest(), "size": len(good),
                                                    "kind": "server"}]}
        raw = json.dumps(m).encode()
        self.channel = {"stable.json": raw, "stable.json.sig": sign(bad_sig_key or key, raw, self.tmp).encode()}
        self.manifest = self.base + "/updates/stable.json"

    async def start(self):
        app = web.Application()
        async def latest(r):
            return web.json_response(self.release)

        async def dl(r):
            return web.Response(body=self.files[r.match_info["name"]])

        async def chan(r):
            n = r.match_info["name"]
            return web.Response(body=self.channel[n]) if n in self.channel else web.Response(status=404)
        app.router.add_get("/repos/x/releases/latest", latest)
        app.router.add_get("/dl/{name}", dl)
        app.router.add_get("/updates/{name}", chan)
        self.runner = web.AppRunner(app)
        await self.runner.setup()
        site = web.TCPSite(self.runner, "127.0.0.1", 0)
        await site.start()
        self.base = f"http://127.0.0.1:{self.runner.addresses[0][1]}"
        self.api = self.base + "/repos/x/releases/latest"


async def test_self_update_good_tampered_unsigned_wrong_key_and_rollback(tmp_path):
    key, pub = keypair(tmp_path)
    other, _pub2 = keypair(tmp_path / "o") if (tmp_path / "o").mkdir() is None else (None, None)
    gh = FakeGitHub(tmp_path)
    await gh.start()
    root = tmp_path / "install"
    restarted = []
    u = su.SelfUpdater(root, gh.api, pub, current="2.0.0", restart_cmd=["true"], manifest="")
    try:
        # up to date
        gh.publish("2.0.0", key)
        assert await asyncio.to_thread(u.check) is None
        # unsigned: refused before downloading anything
        gh.publish("2.0.1", None)
        rel = await asyncio.to_thread(u.check)
        assert rel and not rel["signed"]
        with pytest.raises(su.UpdateError) as e:
            await asyncio.to_thread(u.install, rel)
        assert e.value.kind == "unsigned" and not (root / "current").exists()
        # tampered archive: signature fine, checksum refused
        gh.publish("2.0.1", key, tamper=True)
        with pytest.raises(su.UpdateError) as e:
            await asyncio.to_thread(u.install, await asyncio.to_thread(u.check))
        assert e.value.kind == "bad_checksum" and not (root / "current").exists()
        assert not (root / "versions" / "2.0.1").exists() and not (root / "staging").exists()
        # signed with another key (e.g. a compromised GitHub account): refused
        gh.publish("2.0.1", other)
        with pytest.raises(su.UpdateError) as e:
            await asyncio.to_thread(u.install, await asyncio.to_thread(u.check))
        assert e.value.kind == "bad_signature"
        assert u.status()["last"]["ok"] is False
        # good release: verified, extracted, health-checked for real (serve --demo on spare ports), switched
        gh.publish("2.0.1", key)
        res = await asyncio.to_thread(u.install, await asyncio.to_thread(u.check))
        assert res["version"] == "2.0.1"
        cur = root / "current"
        assert cur.is_symlink() and os.readlink(cur).endswith("versions/2.0.1")
        assert (cur / "madalean" / "__init__.py").read_text().count('"2.0.1"') == 1
        st = u.status()
        assert st["installed"] == "2.0.1" and st["pending_restart"] and st["last"]["ok"]
        # a second good release; the previous one is kept for rollback, older ones are pruned
        u.current_version = "2.0.1"
        gh.publish("2.0.2", key)
        await asyncio.to_thread(u.install, await asyncio.to_thread(u.check))
        assert sorted(p.name for p in (root / "versions").iterdir()) == ["2.0.1", "2.0.2"]
        r = u.rollback()
        assert r["version"] == "2.0.1" and os.readlink(cur).endswith("versions/2.0.1")
        assert u.status()["previous"].endswith("2.0.2")
        assert u.restart() is True and not u.status()["pending_restart"]
        restarted.append(True)
    finally:
        await gh.runner.cleanup()


def test_safe_extract_refuses_escapes(tmp_path):
    for name, kind in (("../evil", tarfile.REGTYPE), ("/abs", tarfile.REGTYPE), ("x/link", tarfile.SYMTYPE)):
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w:gz") as t:
            ti = tarfile.TarInfo(name)
            ti.type = kind
            ti.linkname = "/etc/passwd" if kind == tarfile.SYMTYPE else ""
            t.addfile(ti, io.BytesIO(b""))
        f = tmp_path / f"{abs(hash(name))}.tgz"
        f.write_bytes(buf.getvalue())
        with pytest.raises(su.UpdateError):
            su.safe_extract(f, tmp_path / f"out{abs(hash(name))}")


def test_terminal_command_construction():
    which = {"konsole": "/usr/bin/konsole", "xterm": "/usr/bin/xterm"}.get
    argv = sysc.terminal_argv("sudo pacman -Syu", which)
    assert argv[:4] == ["/usr/bin/konsole", "--hold", "-e", "bash"] and "&& sudo pacman -Syu;" in argv[-1]
    argv = sysc.terminal_argv("sudo apt update && sudo apt install --only-upgrade poppler-utils",
                              {"gnome-terminal": "/usr/bin/gnome-terminal"}.get)
    assert argv[:3] == ["/usr/bin/gnome-terminal", "--", "bash"]
    assert sysc.terminal_argv("sudo pacman -Syu", lambda n: None) is None
    for bad in ("x\nrm -rf ~", "a # b", ""):
        assert sysc.terminal_argv(bad, which) is None
    calls = []
    assert sysc.open_terminal("sudo dnf upgrade sagemath", popen=lambda argv, **kw: calls.append((argv, kw)))
    assert calls and calls[0][1]["start_new_session"] and "sudo" not in calls[0][0][0]
    assert not any("KEY" in k or "TOKEN" in k for k in calls[0][1]["env"])


async def test_system_install_action_and_auto_policy(tmp_path, monkeypatch):
    from madalean.server.plugins import research_workshop as rw
    ctx = make_ctx(tmp_path)
    opened = []
    monkeypatch.setattr(rw, "_POPEN", {"fn": lambda argv, **kw: opened.append(argv)})
    monkeypatch.setattr(sysc.shutil, "which", lambda n: "/usr/bin/konsole" if n == "konsole" else None)
    async with running(ctx) as (_s, L, Rm), session() as s:
        cands = [updates.Candidate("system", "system:poppler", "Poppler", "25.10.0", "25.11.0", False, "n", 0,
                                   {"command": "sudo pacman -Syu"}),
                 updates.Candidate("lake-package", "lake:lean-current:foo", "foo", "v1", "v2", True, "", 0,
                                   {"workspace": "lean-current"}),
                 updates.Candidate("lake-package", "lake:lean-prover49:bar", "bar", "v1", "v2", False, "pinned", 0,
                                   {"workspace": "lean-prover49"})]
        ctx.updates.state["candidates"] = [c.__dict__ for c in cands]
        dev, token = ctx.devices.add("phone")
        r = await s.post(Rm + "/api/updates/system/poppler/terminal", headers={"Authorization": f"Bearer {token}"})
        assert r.status == 403
        r = await s.post(L + "/api/updates/system/poppler/terminal")
        j = await r.json()
        assert r.status == 200 and j["opened"] and j["command"] == "sudo pacman -Syu" and opened[0][0] == "/usr/bin/konsole"
        assert (await s.post(L + "/api/updates/system/nope/terminal")).status == 404
        # automatic installs: only with updates_auto, only when quiet, each version tried once, never pinned
        rs = ctx.research
        started = []

        async def fake_install(key):
            started.append(key)
            return None
        monkeypatch.setattr(ctx.updates, "install", fake_install)
        ctx.demo = False
        ctx.settings.updates_auto = False
        assert await rw.auto_step(ctx, rs) is None and started == []
        ctx.settings.updates_auto = True
        monkeypatch.setattr(ctx.orchestrator, "active", lambda: [object()])        # a job runs: not now
        assert await rw.auto_step(ctx, rs) is None and started == []
        monkeypatch.setattr(ctx.orchestrator, "active", lambda: [])
        assert await rw.auto_step(ctx, rs) == "lake:lean-current:foo"
        assert await rw.auto_step(ctx, rs) is None and started == ["lake:lean-current:foo"]   # tried once
        st = await (await s.get(L + "/api/selfupdate")).json()
        assert st["managed_install"] is False and len(st["public_key"]) == 64
        for path in ("check", "install", "rollback", "restart"):
            r = await s.post(Rm + f"/api/selfupdate/{path}", headers={"Authorization": f"Bearer {token}"})
            assert r.status == 403
        ctx.demo = True


async def test_self_update_signed_manifest_channel(tmp_path):
    key, pub = keypair(tmp_path)
    (tmp_path / "o").mkdir()
    other, _p = keypair(tmp_path / "o")
    gh = FakeGitHub(tmp_path)
    await gh.start()
    root = tmp_path / "install"
    try:
        gh.publish_manifest("2.1.0", key)
        u = su.SelfUpdater(root, gh.api, pub, current="2.0.0", restart_cmd=[], manifest=gh.manifest)
        rel = await asyncio.to_thread(u.check)
        assert rel["source"] == "manifest" and rel["version"] == "2.1.0" and len(rel["sha256"]) == 64
        # the manifest is signed but the asset was replaced afterwards: refused by the signed sha256
        gh.publish_manifest("2.1.0", key, tamper_archive=True)
        with pytest.raises(su.UpdateError) as e:
            await asyncio.to_thread(u.install, await asyncio.to_thread(u.check))
        assert e.value.kind == "bad_checksum" and not (root / "current").exists()
        # a manifest signed by another key is refused (no silent fallback to the Releases API)
        gh.publish_manifest("2.1.0", key, bad_sig_key=other)
        with pytest.raises(su.UpdateError) as e:
            await asyncio.to_thread(u.check)
        assert e.value.kind == "bad_signature"
        # too old to update directly: manual step required
        gh.publish_manifest("2.1.0", key, min_version="2.0.5")
        rel = await asyncio.to_thread(u.check)
        assert rel["manual"]
        with pytest.raises(su.UpdateError) as e:
            await asyncio.to_thread(u.install, rel)
        assert e.value.kind == "manual"
        # good: installed through the manifest (no SHA256SUMS needed), health-checked, switched
        gh.publish_manifest("2.1.0", key)
        res = await asyncio.to_thread(u.install, await asyncio.to_thread(u.check))
        assert res["version"] == "2.1.0" and os.readlink(root / "current").endswith("versions/2.1.0")
        # channel unreachable → fallback to the GitHub Releases API (SHA256SUMS + .sig)
        gh.channel = {}
        u2 = su.SelfUpdater(tmp_path / "i2", gh.api, pub, current="2.0.0", restart_cmd=[], manifest=gh.manifest)
        rel = await asyncio.to_thread(u2.check)
        assert rel and rel.get("source") != "manifest" and rel["signed"] and rel["sums"]
    finally:
        await gh.runner.cleanup()
