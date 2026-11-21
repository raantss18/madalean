"""madalean.deps (session S-I): tool resolver, manifest + locks, verified download with resume, safe extraction,
atomic switch + rollback, env verification, workspace import by hard links, health, update checker, process guard.
No network, no real component: a fake prefix in a temp directory."""
from __future__ import annotations

import hashlib
import http.server
import io
import json
import os
import re
import signal
import subprocess
import sys
import tarfile
import threading
import time
import zipfile
from pathlib import Path

import pytest

from madalean import deps
from madalean.deps import checker, health, installer, manifest, workspaces_import


@pytest.fixture
def prefix(tmp_path, monkeypatch):
    p = tmp_path / "prefix"
    p.mkdir()
    monkeypatch.setenv("MADALEAN_HOME", str(p))
    return p


def _exe(path: Path, body: str = "#!/bin/sh\necho ok\n") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body)
    path.chmod(0o755)
    return path


def _installed(p: Path) -> None:
    _exe(p / "envs" / "main-x" / "bin" / "python3")
    (p / "envs" / "main-x" / "bin" / "python").symlink_to("python3")
    (p / "env").symlink_to("envs/main-x")


# ---------------------------------------------------------------- resolver
def test_home_defaults_and_env(monkeypatch, tmp_path):
    monkeypatch.delenv("MADALEAN_HOME", raising=False)
    assert deps.home() == Path.home() / ".local" / "share" / "madalean"
    monkeypatch.setenv("MADALEAN_HOME", str(tmp_path))
    assert deps.home() == tmp_path and deps.elan_home() == tmp_path / "elan"


def test_tool_prefix_first_and_never_system_for_managed(prefix, monkeypatch, tmp_path):
    sysbin = tmp_path / "sysbin"
    for n in ("jupyter-lab", "pdftotext", "setpriv", "git"):
        _exe(sysbin / n)
    monkeypatch.setenv("PATH", f"{sysbin}:/usr/bin:/bin")
    # dev mode (no env in the prefix): PATH fallback, flagged
    info = deps.tool_info("jupyter-lab")
    assert info["path"] == str(sysbin / "jupyter-lab") and info["source"] == "system-dev"
    _installed(prefix)
    _exe(prefix / "env" / "bin" / "jupyter-lab")
    assert deps.tool("jupyter-lab") == str(prefix / "env" / "bin" / "jupyter-lab")
    assert deps.tool_info("jupyter-lab")["source"] == "prefix"
    # managed tool missing from the prefix: never the system's
    assert deps.tool("pdftotext") is None and deps.tool("git") is None
    # allowed system tool: found, flagged
    assert deps.tool_info("setpriv") == {"name": "setpriv", "path": str(sysbin / "setpriv"), "source": "system",
                                         "component": ""}


def test_activate_puts_prefix_first(prefix, monkeypatch):
    env = {"PATH": "/usr/bin:/bin"}
    assert deps.activate(env) == {}                       # nothing installed: no change
    _installed(prefix)
    (prefix / "elan" / "bin").mkdir(parents=True)
    ch = deps.activate(env)
    parts = env["PATH"].split(":")
    assert parts[0] == str(prefix / "env" / "bin") and parts[1] == str(prefix / "elan" / "bin")
    assert parts[-2:] == ["/usr/bin", "/bin"]
    assert env["ELAN_HOME"] == str(prefix / "elan") and ch["TECTONIC_CACHE_DIR"] == str(prefix / "tectonic")
    deps.activate(env)
    assert env["PATH"].count(str(prefix / "env" / "bin")) == 1   # idempotent


# ---------------------------------------------------------------- manifest + locks
def test_manifest_pins_everything():
    comps = manifest.components()
    assert set(comps) >= {"micromamba", "env", "sage", "tex-bundle", "fonts", "elan", "llama.cpp", "madalean-net"}
    hexre = re.compile(r"^[0-9a-f]{64}$")
    for name, c in comps.items():
        assert c.get("version") and c.get("license") and c.get("need") in ("required", "optional", "on-demand"), name
        assert c.get("kind") in ("binary", "archive", "conda-env", "tectonic-bundle"), name
        urls = [c.get("url")] + [v.get("url") for v in c.get("variants", {}).values()] + \
               [v.get("extra_url") for v in c.get("variants", {}).values()] + [a["url"] for a in c.get("assets", [])]
        for u in filter(None, urls):
            assert u.startswith("https://"), (name, u)
        shas = [c.get("sha256")] + [v.get("sha256") for v in c.get("variants", {}).values()] + \
               [a["sha256"] for a in c.get("assets", [])]
        for s in filter(None, shas):
            assert hexre.match(s), (name, s)
        if c["kind"] in ("binary",):
            assert hexre.match(c["sha256"]) and c["size"] > 0
    assert comps["sage"]["need"] == "on-demand"


def test_locks_match_manifest_and_have_hashes():
    for name in ("env", "sage"):
        c = manifest.component(name)
        assert manifest.lock_hash(c) == c["sha256"], f"{name}: lock changed without updating the manifest"
        pkgs = manifest.read_lock(manifest.lock_path(c))
        assert len(pkgs) > 50
        assert all(re.match(r"^[0-9a-f]{64}$", p.sha256) for p in pkgs)
        assert all(p.url.startswith("https://conda.anaconda.org/conda-forge/") for p in pkgs)   # conda-forge only
    names = {p.name for p in manifest.read_lock(manifest.lock_path(manifest.component("env")))}
    assert {"python", "aiohttp", "jupyterlab", "ipykernel", "poppler", "tectonic", "git", "fontconfig"} <= names


def test_every_third_party_import_is_in_the_main_lock():
    """Inventory of the Python modules Madalean imports (outside the standard library) vs the locked env."""
    import ast
    root = Path(deps.__file__).resolve().parents[1]
    found = set()
    for p in root.rglob("*.py"):
        for n in ast.walk(ast.parse(p.read_text(encoding="utf-8"))):
            if isinstance(n, ast.Import):
                found |= {a.name.split(".")[0] for a in n.names}
            elif isinstance(n, ast.ImportFrom) and n.level == 0 and n.module:
                found.add(n.module.split(".")[0])
    local = {"madalean", "madasite"}                 # madasite = site/madasite, shipped with the app (S-F)
    third = {m for m in found if m not in sys.stdlib_module_names and m not in local}
    conda_name = {"PIL": "pillow", "fontTools": "fonttools"}
    locked = {p.name for p in manifest.read_lock(manifest.lock_path(manifest.component("env")))}
    missing = {m for m in third if conda_name.get(m, m).lower() not in locked}
    assert not missing, f"imported but not locked: {missing}"


# ---------------------------------------------------------------- download (resume + hash)
class _Handler(http.server.BaseHTTPRequestHandler):
    data = b""
    hits: list = []

    def do_GET(self):  # noqa: N802
        rng = self.headers.get("Range")
        _Handler.hits.append(rng)
        body, status = self.data, 200
        if rng:
            start = int(rng.split("=")[1].split("-")[0])
            body, status = self.data[start:], 206
        self.send_response(status)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


@pytest.fixture
def http_file():
    data = os.urandom(300_000)
    _Handler.data, _Handler.hits = data, []
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    th = threading.Thread(target=srv.serve_forever, daemon=True)
    th.start()
    yield f"http://127.0.0.1:{srv.server_address[1]}/blob.bin", data
    srv.shutdown()


def test_fetch_resumes_and_verifies(prefix, http_file):
    url, data = http_file
    sha = hashlib.sha256(data).hexdigest()
    dl = deps.downloads_dir()
    dl.mkdir(parents=True)
    (dl / "blob.bin.part").write_bytes(data[:100_000])          # interrupted download
    events = []
    p = installer.fetch(url, sha, len(data), events.append, "t")
    assert p.read_bytes() == data and _Handler.hits == ["bytes=100000-"]
    assert installer.fetch(url, sha, len(data)) == p and len(_Handler.hits) == 1       # cached, verified
    p.unlink()
    with pytest.raises(installer.InstallError) as e:
        installer.fetch(url, "0" * 64, len(data))
    assert e.value.key == "bad_hash" and not (dl / "blob.bin").exists() and not (dl / "blob.bin.part").exists()
    with pytest.raises(installer.InstallError):
        installer.fetch(url, "", 0)                                # never without a pinned hash
    with pytest.raises(installer.InstallError) as e:
        installer.fetch(url, sha, len(data), offline=True)
    assert e.value.key == "offline_missing"


def test_fetch_from_offline_dir(prefix, tmp_path):
    off = tmp_path / "export"
    off.mkdir()
    (off / "x.bin").write_bytes(b"hello")
    sha = hashlib.sha256(b"hello").hexdigest()
    p = installer.fetch("https://invalid.example/x.bin", sha, 5, offline_dirs=[off], offline=True)
    assert p.read_bytes() == b"hello"


# ---------------------------------------------------------------- extraction
def _tar(path: Path, members: dict, links: dict | None = None) -> Path:
    with tarfile.open(path, "w:gz") as t:
        for name, data in members.items():
            ti = tarfile.TarInfo(name)
            ti.size = len(data)
            t.addfile(ti, io.BytesIO(data))
        for name, target in (links or {}).items():
            ti = tarfile.TarInfo(name)
            ti.type, ti.linkname = tarfile.SYMTYPE, target
            t.addfile(ti)
    return path


def test_safe_extract_strips_top_and_keeps_inner_links(tmp_path):
    a = _tar(tmp_path / "a.tar.gz", {"top/bin/x": b"1", "top/lib.so.1": b"2"}, {"top/lib.so": "lib.so.1"})
    d = installer.safe_extract(a, tmp_path / "out")
    assert (d / "bin" / "x").read_bytes() == b"1" and os.readlink(d / "lib.so") == "lib.so.1"


@pytest.mark.parametrize("members,links", [({"../evil": b"x"}, None), ({"/abs": b"x"}, None),
                                           ({"top/a": b"x"}, {"top/l": "/etc/passwd"}),
                                           ({"top/a": b"x"}, {"top/l": "../../outside"})])
def test_safe_extract_refuses_escapes(tmp_path, members, links):
    a = _tar(tmp_path / "bad.tar.gz", members, links)
    with pytest.raises(Exception):
        installer.safe_extract(a, tmp_path / "out")
    assert not (tmp_path / "evil").exists() and not (tmp_path / "outside").exists()


def test_safe_extract_zip_keep(tmp_path):
    z = tmp_path / "f.zip"
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr("Font/ttf/A.ttf", b"a")
        zf.writestr("Font/otf/A.otf", b"b")
        zf.writestr("../escape", b"c")
    with pytest.raises(installer.InstallError):
        installer.safe_extract(z, tmp_path / "o1")
    z2 = tmp_path / "g.zip"
    with zipfile.ZipFile(z2, "w") as zf:
        zf.writestr("Font/ttf/A.ttf", b"a")
        zf.writestr("Font/otf/A.otf", b"b")
    d = installer.safe_extract(z2, tmp_path / "o2", keep=["Font/ttf/A.ttf"], strip_single_top=False)
    assert [p.name for p in d.iterdir()] == ["A.ttf"]


# ---------------------------------------------------------------- install, switch, rollback
def _bin_component(tmp_path: Path, version: str, body: str) -> tuple[dict, Path]:
    f = _exe(tmp_path / f"src-{version}" / "madalean-net-linux-amd64", body)
    sha = hashlib.sha256(f.read_bytes()).hexdigest()
    return {"version": version, "file": "madalean-net", "sha256": sha, "size": f.stat().st_size,
            "url": "https://invalid.example/madalean-net-linux-amd64"}, f


def test_install_binary_switch_and_rollback(prefix, tmp_path):
    c1, f1 = _bin_component(tmp_path, "0.1.0", "#!/bin/sh\necho v1\n")
    c2, f2 = _bin_component(tmp_path, "0.2.0", "#!/bin/sh\necho v2\n")
    installer.install_binary("madalean-net", c1, lambda e: None, local_files=[f1])
    link = prefix / "components" / "madalean-net" / "current"
    assert link.is_symlink() and not os.path.isabs(os.readlink(link))
    assert subprocess.run([deps.tool("madalean-net")], capture_output=True, text=True).stdout == "v1\n"
    installer.install_binary("madalean-net", c2, lambda e: None, local_files=[f2])
    assert subprocess.run([deps.tool("madalean-net")], capture_output=True, text=True).stdout == "v2\n"
    st = installer.load_state()["madalean-net"]
    assert st["version"] == "0.2.0" and st["previous"]["version"] == "0.1.0"
    installer.rollback("madalean-net")
    assert subprocess.run([deps.tool("madalean-net")], capture_output=True, text=True).stdout == "v1\n"
    assert installer.load_state()["madalean-net"]["previous"]["version"] == "0.2.0"
    # a wrong local file is never used; without network the install fails and changes nothing
    c3, _f = _bin_component(tmp_path, "0.3.0", "#!/bin/sh\necho v3\n")
    with pytest.raises(installer.InstallError):
        installer.install_binary("madalean-net", c3, lambda e: None, offline=True, local_files=[f1])
    assert subprocess.run([deps.tool("madalean-net")], capture_output=True, text=True).stdout == "v1\n"


def test_broken_binary_is_not_switched(prefix, tmp_path):
    c1, f1 = _bin_component(tmp_path, "0.1.0", "#!/bin/sh\necho v1\n")
    installer.install_binary("madalean-net", c1, lambda e: None, local_files=[f1])
    cb, fb = _bin_component(tmp_path, "0.9.0", "#!/bin/sh\nexit 3\n")
    with pytest.raises(installer.InstallError):
        installer.install_binary("madalean-net", cb, lambda e: None, local_files=[fb])
    assert subprocess.run([deps.tool("madalean-net")], capture_output=True, text=True).stdout == "v1\n"


def test_verify_env_against_lock(tmp_path):
    lock = [manifest.LockedPackage("a", "1", "https://conda.anaconda.org/conda-forge/noarch/a-1-0.conda", "1" * 64, "m"),
            manifest.LockedPackage("b", "2", "https://conda.anaconda.org/conda-forge/noarch/b-2-0.tar.bz2", "2" * 64, "n")]
    meta = tmp_path / "conda-meta"
    meta.mkdir()
    (meta / "a-1-0.json").write_text(json.dumps({"sha256": "1" * 64, "size": 10}))
    assert installer.verify_env(tmp_path, lock) == ["b (missing)"]
    (meta / "b-2-0.json").write_text(json.dumps({"sha256": "f" * 64, "size": 5}))
    assert installer.verify_env(tmp_path, lock) == ["b"]
    (meta / "b-2-0.json").write_text(json.dumps({"sha256": "2" * 64, "size": 5}))
    assert installer.verify_env(tmp_path, lock) == [] and installer.env_bytes(tmp_path) == 15


def test_read_lock_minimal(tmp_path):
    f = tmp_path / "x.conda-lock.yml"
    f.write_text("version: 1\npackage:\n- name: zlib\n  version: '1.3'\n  manager: conda\n  platform: linux-64\n"
                 "  dependencies:\n    libgcc: '>=13'\n  url: https://conda.anaconda.org/conda-forge/linux-64/zlib-1.3-h1.conda\n"
                 "  hash:\n    md5: abc\n    sha256: " + "a" * 64 + "\n  category: main\n  optional: false\n"
                 "- name: zlib\n  version: '1.3'\n  manager: conda\n  platform: osx-64\n"
                 "  url: https://conda.anaconda.org/conda-forge/osx-64/zlib-1.3-h1.conda\n  hash:\n    md5: x\n"
                 "    sha256: " + "b" * 64 + "\n")
    pk = manifest.read_lock(f)
    assert len(pk) == 1 and pk[0].sha256 == "a" * 64 and pk[0].dist == "zlib-1.3-h1" and pk[0].md5 == "abc"


def test_llama_variant_choice(monkeypatch):
    c = manifest.component("llama.cpp")
    monkeypatch.setattr(installer, "cuda_driver_version", lambda: (13, 5))
    assert installer.pick_llama_variant(c) == "cuda13"
    monkeypatch.setattr(installer, "cuda_driver_version", lambda: (12, 9))
    assert installer.pick_llama_variant(c) == "cuda12"
    monkeypatch.setattr(installer, "cuda_driver_version", lambda: (12, 2))
    assert installer.pick_llama_variant(c) == "cpu"
    monkeypatch.setattr(installer, "cuda_driver_version", lambda: None)
    assert installer.pick_llama_variant(c) == "cpu" and installer.pick_llama_variant(c, "cuda12") == "cuda12"
    with pytest.raises(installer.InstallError):
        installer.pick_llama_variant(c, "metal")


# ---------------------------------------------------------------- workspaces
def test_import_workspace_by_hard_links(prefix, tmp_path):
    src = tmp_path / "old" / "workspaces" / "lean-current"
    lib = src / ".lake" / "packages" / "mathlib" / ".lake" / "build" / "lib" / "lean"
    lib.mkdir(parents=True)
    (lib / "Mathlib.olean").write_bytes(b"olean")
    (src / "lean-toolchain").write_text("leanprover/lean4:v4.34.1\n")
    tcs = tmp_path / "elan" / "toolchains"
    _exe(tcs / "leanprover--lean4---v4.34.1" / "bin" / "lean")
    found = workspaces_import.candidates([tmp_path / "old" / "workspaces"], defaults=False)
    assert found == {"lean-current": src}
    r = workspaces_import.import_workspace(src, "lean-current", tcs)
    dst = prefix / "workspaces" / "lean-current"
    assert r["method"] == "hardlink" and r["toolchain_method"] == "hardlink"
    olean = dst / ".lake" / "packages" / "mathlib" / ".lake" / "build" / "lib" / "lean" / "Mathlib.olean"
    assert olean.stat().st_ino == (lib / "Mathlib.olean").stat().st_ino
    assert (prefix / "elan" / "toolchains" / "leanprover--lean4---v4.34.1" / "bin" / "lean").exists()
    assert workspaces_import.import_workspace(src, "lean-current", tcs)["method"] == "already"
    import shutil
    shutil.rmtree(tmp_path / "old")                     # the old checkout disappears: the prefix copy still works
    assert olean.read_bytes() == b"olean"


# ---------------------------------------------------------------- health + checker
def test_health_states(prefix, tmp_path):
    rep = health.report()
    by = {c["component"]: c for c in rep["components"]}
    assert by["sage"]["state"] in ("on_demand", "dev") and by["sage"]["ok"]
    assert by["madalean-net"]["state"] in ("missing", "dev")
    c1, f1 = _bin_component(tmp_path, manifest.component("madalean-net")["version"], "#!/bin/sh\necho v\n")
    installer.install_binary("madalean-net", c1, lambda e: None, local_files=[f1])
    by = {c["component"]: c for c in health.components()}
    assert by["madalean-net"]["state"] == "ok" and by["madalean-net"]["source"] == "prefix"
    st = installer.load_state()
    st["madalean-net"]["version"] = "0.0.1"              # installed older than the pin (a release brought a new one)
    installer.save_state(st)
    by = {c["component"]: c for c in health.components()}
    assert by["madalean-net"]["state"] == "outdated" and by["madalean-net"]["repair"] == "dep_madalean-net"


def test_checker_candidates(prefix, tmp_path):
    c1, f1 = _bin_component(tmp_path, "0.0.1", "#!/bin/sh\necho v\n")
    installer.install_binary("madalean-net", c1, lambda e: None, local_files=[f1])

    def fake_get(url):
        if "tailscale" in url:
            return {"tag_name": "v9.9.9"}
        if "api.github.com" in url:
            return {"tag_name": "v0.0.1"}
        return {"latest_version": "0.0.1"}
    cands = checker.candidates(get=fake_get)
    kinds = {(c.kind, c.key) for c in cands}
    assert ("deps", "deps:madalean-net") in kinds
    up = [c for c in cands if c.kind == "deps-upstream"]
    assert [c.spec["item"] for c in up] == ["tailscale"] and not up[0].installable
    inst = [c for c in cands if c.kind == "deps"][0]
    assert inst.installable and checker.install_args(inst) == ["deps-install", "madalean-net"]
    assert all(c.kind == "deps" for c in checker.candidates(get=fake_get, online=False))
    inst.spec["component"] = "../../x"
    with pytest.raises(ValueError):
        checker.install_args(inst)


def test_export_uses_system_tex_only_as_fallback(prefix):
    from madalean import export
    assert export.tectonic_cmd() is None            # no prefix tectonic: system XeLaTeX (if any) stays the engine
    _installed(prefix)
    _exe(prefix / "env" / "bin" / "tectonic")
    assert export.tectonic_cmd() is None            # bundle not installed yet
    (prefix / "tectonic" / "files").mkdir(parents=True)
    cmd = export.tectonic_cmd()
    assert cmd[0] == str(prefix / "env" / "bin" / "tectonic") and "--untrusted" in cmd and "--only-cached" in cmd
    assert export._engines()[0] == cmd and export.bib_backend() == "bibtex"


# ---------------------------------------------------------------- process guard (PR_SET_PDEATHSIG)
@pytest.mark.parametrize("use_setpriv", [True, False])
def test_guarded_child_dies_with_parent(monkeypatch, use_setpriv, tmp_path):
    from madalean import runtime
    if use_setpriv and not runtime.SETPRIV:
        pytest.skip("no setpriv")
    argv = runtime.guarded("sleep", ["300"]) if use_setpriv else \
        [sys.executable, "-I", "-c", runtime._TRAMPOLINE, "sleep", "300"]
    pidf = tmp_path / "pid"
    parent = subprocess.Popen([sys.executable, "-c",
                               "import subprocess,sys,time;p=subprocess.Popen(sys.argv[2:]);"
                               "open(sys.argv[1],'w').write(str(p.pid));time.sleep(300)", str(pidf), *argv],
                              start_new_session=True)
    for _i in range(100):
        if pidf.exists() and pidf.read_text():
            break
        time.sleep(0.05)
    child = int(pidf.read_text())
    time.sleep(0.3)
    assert Path(f"/proc/{child}").exists()
    os.kill(parent.pid, signal.SIGKILL)
    parent.wait()
    for _i in range(50):
        try:
            st = Path(f"/proc/{child}/stat").read_text().split()[2]
        except OSError:
            break
        if st == "Z":
            break
        time.sleep(0.05)
    else:
        os.kill(child, signal.SIGKILL)
        pytest.fail("child survived the parent")


def test_parse_cuda_version_banners():
    assert installer.parse_cuda_version("| NVIDIA-SMI 570.1   Driver Version: 570.1   CUDA Version: 12.8 |") == (12, 8)
    assert installer.parse_cuda_version("| NVIDIA-SMI 620.70.06  KMD Version: 620.70.06  CUDA UMD Version: 13.5 |") == (13, 5)
    assert installer.parse_cuda_version("no gpu") is None


def test_llama_pin_is_not_vulnerable():
    """Security review F11: llama.cpp < b12556 has CVE-2026-133710 / CVE-2026-107183."""
    c = manifest.component("llama.cpp")
    assert int(c["version"].lstrip("b")) >= 12556
    for v in c["variants"].values():
        assert c["version"] in v["url"] and (not v.get("extra_url") or c["version"] in v["extra_url"])


def test_tests_never_use_the_real_prefix():
    assert deps.home() != Path.home() / ".local" / "share" / "madalean"
