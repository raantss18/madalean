"""Extended update checkers (S-G): safe ls-remote, lake-manifest packages on fixture git repositories (file://),
toolchains, system components per distro (notify + exact command), llama.cpp, Madalean releases, `mode=local`, the
generalised verify-then-switch installer with REAL lake (fixture workspace, Lean 4.9 toolchain), and the
re-verification flow after an update (regressions marked, never hidden)."""
import asyncio
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from helpers import make_ctx, running, session, started
from madalean import config, leancheck, updates
from madalean.update_checkers import common, installer, lean as lc, system as sysc

TC = "leanprover/lean4:v4.9.0-rc1"
LAKE = str(config.ELAN_BIN / "lake")


def git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True,
                   env={**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
                        "GIT_COMMITTER_EMAIL": "t@t"})


def make_repo(root: Path, name: str, versions: list[tuple[str, str]], branch_extra: bool = False) -> Path:
    """A local git repo of a tiny Lake package; versions = [(tag, Foo.lean content)]."""
    r = root / name
    r.mkdir(parents=True)
    git(r, "init", "-q", "-b", "main")
    (r / "lakefile.lean").write_text(f"import Lake\nopen Lake DSL\n\npackage {name}\n\n@[default_target]\n"
                                     f"lean_lib {name.capitalize()}\n")
    (r / "lean-toolchain").write_text(TC + "\n")
    for tag, content in versions:
        (r / f"{name.capitalize()}.lean").write_text(content)
        git(r, "add", "-A")
        git(r, "commit", "-q", "--allow-empty", "-m", tag)
        git(r, "tag", tag)
    if branch_extra:
        (r / "NOTES.md").write_text("more\n")
        git(r, "add", "-A")
        git(r, "commit", "-qm", "head moves")
    return r


def make_ws(root: Path, name: str, requires: list[tuple[str, Path, str]], body: str = "") -> Path:
    ws = root / name
    ws.mkdir(parents=True)
    (ws / "lean-toolchain").write_text(TC + "\n")
    req = "".join(f'require {n} from git\n  "file://{p}" @ "{rev}"\n\n' for n, p, rev in requires)
    (ws / "lakefile.lean").write_text(f"import Lake\nopen Lake DSL\n\npackage ws\n\n{req}@[default_target]\nlean_lib Ws\n")
    (ws / "Ws.lean").write_text(body or "\n".join(f"import {n.capitalize()}" for n, _p, _r in requires) + "\n")
    for cmd in (["update"], ["build"]):
        r = subprocess.run([LAKE, *cmd], cwd=ws, capture_output=True, text=True, timeout=600,
                           env={**os.environ, "PATH": f"{config.ELAN_BIN}:{os.environ['PATH']}"})
        assert r.returncode == 0, r.stdout + r.stderr
    return ws


needs_lake = pytest.mark.skipif(not Path(LAKE).exists() or not (Path.home() / ".elan/toolchains/leanprover--lean4---v4.9.0-rc1").is_dir(),
                                reason="lake / Lean 4.9.0-rc1 toolchain not installed")


# ---------------------------------------------------------------- safety
def test_safe_git_url_and_ls_remote_fixture(tmp_path):
    for bad in ("http://x/y", "ssh://git@x/y", "git@github.com:a/b", "-uhttps://x", "https://user:pw@x/y",
                "https://x/y z", "file:///etc", "ext::sh -c id"):
        with pytest.raises(common.CheckError):
            common.safe_git_url(bad)
    assert common.safe_git_url("https://github.com/leanprover-community/batteries")
    r = make_repo(tmp_path, "foo", [("v1.0.0", "def Foo.x := 2\n"), ("v1.1.0", "def Foo.x := 2\n"),
                                    ("v2.0.0-rc1", "def Foo.x := 3\n")], branch_extra=True)
    with pytest.raises(common.CheckError):
        common.ls_remote(f"file://{r}")                       # file:// refused unless explicitly allowed
    refs = common.ls_remote(f"file://{r}", ("https", "file"))
    assert set(refs["tags"]) == {"v1.0.0", "v1.1.0", "v2.0.0-rc1"} and "main" in refs["heads"]
    assert common.newest_version(refs["tags"], "v") == "v1.1.0" and common.newest_rc(refs["tags"]) == "v2.0.0-rc1"
    env = common.git_env()
    assert env["GIT_TERMINAL_PROMPT"] == "0" and env["GIT_CONFIG_GLOBAL"] == os.devnull


@needs_lake
def test_lake_manifest_candidates_on_fixture_repos(tmp_path):
    foo = make_repo(tmp_path / "up", "foo", [("v1.0.0", "def Foo.x : Nat := 2\n")])
    bar = make_repo(tmp_path / "up", "bar", [("v0.1.0", "def Bar.y : Nat := 1\n")])
    root = tmp_path / "workspaces"
    ws = make_ws(root, "lean-current", [("foo", foo, "v1.0.0"), ("bar", bar, "main")])
    p49 = make_ws(root, "lean-prover49", [("foo", foo, "v1.0.0")])
    del p49
    # upstream moves: foo gets v1.1.0 (tag), bar's main moves
    (foo / "Foo.lean").write_text("def Foo.x : Nat := 2\ndef Foo.y : Nat := 5\n")
    git(foo, "add", "-A")
    git(foo, "commit", "-qm", "v1.1")
    git(foo, "tag", "v1.1.0")
    (bar / "Bar.lean").write_text("def Bar.y : Nat := 1\ndef Bar.z : Nat := 2\n")
    git(bar, "add", "-A")
    git(bar, "commit", "-qm", "more")
    cands = lc.lake_checker(root, allow_schemes=("https", "file"))()
    by = {c.key: c for c in cands}
    c = by["lake:lean-current:foo"]
    assert c.installable and c.current == "v1.0.0" and c.latest == "v1.1.0" and c.spec["to_rev"] == "v1.1.0"
    assert c.spec["rebuild"] == ["lean-current"] and c.spec["release_notes"] and c.spec["risk"]
    b = by["lake:lean-current:bar"]
    assert b.installable and b.current.startswith("main@") and b.latest.startswith("main@")
    p = by["lake:lean-prover49:foo"]
    assert not p.installable and "Goedel" in p.note
    assert all(isinstance(x, updates.Candidate) for x in cands)
    # without file:// allowed (production rule) nothing is contacted
    with pytest.raises(common.CheckError):
        lc.lake_checker(root)()


def test_toolchains_system_llama_madalean_candidates():
    tags = ["v4.34.1", "v4.35.0", "v4.36.0-rc1", "v4.9.0", "nightly-2026"]
    c = lc.toolchain_candidates(tags, ["v4.9.0-rc1", "v4.34.1"], {"v4.34.1": ["lean-current"]})
    assert len(c) == 1 and c[0].latest == "v4.35.0" and not c[0].installable
    assert c[0].spec["release_candidate"] == "v4.36.0-rc1" and "lean-current" in c[0].spec["used_by"]
    assert lc.toolchain_candidates(tags, ["v4.35.0"], {}) == []
    inst = {"sage": {"version": "10.10"}, "jupyterlab": {"version": "4.6.6"}, "poppler": {"version": "25.10.0"},
            "texlive": {"version": "2025"}}
    up = {"sage": "10.11", "jupyterlab": "4.6.6", "poppler": "25.11.0"}
    owners = {"sage": "sagemath", "jupyterlab": "", "poppler": "poppler"}
    repo = {"sage": "10.10-1", "poppler": "25.11.0-1"}
    out = {x.key: x for x in sysc.system_candidates(inst, up, "arch", owners, repo)}
    assert set(out) == {"system:sage", "system:poppler"}
    assert out["system:poppler"].spec["command"].startswith("sudo pacman -Syu") and not out["system:poppler"].installable
    assert out["system:sage"].spec["command"] == "" and "sagemath" in out["system:sage"].note    # wait for the package
    deb = sysc.system_candidates({"poppler": {"version": "22.02.0"}}, {}, "debian", {"poppler": "poppler-utils"},
                                 {"poppler": "22.12.0-2"})
    assert deb[0].spec["command"] == "sudo apt update && sudo apt install --only-upgrade poppler-utils"
    pip = sysc.system_candidates({"jupyterlab": {"version": "4.0.0"}}, {"jupyterlab": "4.6.6"}, "fedora", {}, {})
    assert pip[0].spec["command"] == "python3 -m pip install --user --upgrade jupyterlab"
    assert common.distro_family({"ID": "endeavouros", "ID_LIKE": "arch"}) == "arch"
    assert common.distro_family({"ID": "ubuntu", "ID_LIKE": "debian"}) == "debian"
    ll = sysc.llama_candidates("b4000-12-g436f6f8", ["b3999", "b4100", "v1"])
    assert ll and ll[0].latest == "b4100" and not ll[0].installable and "pinned" == ll[0].spec["risk"]
    assert sysc.llama_candidates("b4100", ["b4100"]) == []
    m = sysc.madalean_candidates({"tag_name": "v2.0.0", "html_url": "https://x", "assets": [
        {"name": "SHA256SUMS"}, {"name": "SHA256SUMS.minisig"}]}, "2.0.0.dev0")
    assert m and m[0].spec["signed"] and not m[0].installable and "./install.sh" in m[0].spec["steps"]
    assert sysc.madalean_candidates({"tag_name": "v1.9.0"}, "2.0.0.dev0") == []


async def test_checkers_registered_and_silent_in_local_mode(tmp_path, monkeypatch):
    ctx = make_ctx(tmp_path)
    async with running(ctx):
        names = [n for n, _f in updates.CHECKERS]
        for n in ("Lean (elan)", "Lake", "llama.cpp", "Madalean", "Système", "Catalogue"):
            assert n in names
        assert "lake-package" in updates.INSTALL_ARGS and "lake-add" in updates.INSTALL_ARGS
        ctx.settings.mode = "local"
        mine = [(n, f) for n, f in updates.CHECKERS if n in ("Lean (elan)", "Lake", "llama.cpp", "Madalean",
                                                             "Système", "Catalogue")]
        called = []
        monkeypatch.setattr(common.subprocess, "run", lambda *a, **k: called.append(a) or (_ for _ in ()).throw(
            AssertionError("network/process in local mode")))
        st = updates.check_all(tmp_path / "u.json", mine)
        assert st["candidates"] == [] and st["errors"] == [] and called == []


# ---------------------------------------------------------------- installer (real lake)
@needs_lake
def test_installer_bump_verify_switch_and_regression(tmp_path):
    up = tmp_path / "up"
    foo = make_repo(up, "foo", [("v1.0.0", "def Foo.x : Nat := 2\n"),
                                ("v1.1.0", "def Foo.x : Nat := 2\ndef Foo.y : Nat := 5\n"),
                                ("v2.0.0", "def Foo.x : Nat := 3\n")])
    root = tmp_path / "workspaces"
    ws = make_ws(root, "lean-current", [("foo", foo, "v1.0.0")], "import Foo\n")
    proofs = [{"name": "dep_t", "dossier": "d1", "code": "import Foo\n\ntheorem dep_t : Foo.x = 2 := by rfl\n"}]
    base = {"workspace_path": str(ws), "workspace_key": "lean-current", "package": "foo", "allow_any_root": True,
            "allow_file_urls": True, "test_lean": "import Foo\n#check Foo.x\n", "proofs": proofs, "lake": LAKE}
    marker = ws / "MARKER"
    marker.write_text("old")
    steps = []
    # compatible bump: copy → update → build → verify → switch → delete old
    res = installer.install({**base, "rev": "v1.1.0"}, lambda k, d="": steps.append(k))
    assert steps == ["copy", "deps", "build", "verify", "switch", "cleanup"]
    assert res["package"] == "foo" and res["rev"] == "v1.1.0" and res["checked"] == 1
    man = json.loads((ws / "lake-manifest.json").read_text())
    assert man["packages"][0]["inputRev"] == "v1.1.0"
    assert not (root / "lean-current.next").exists() and not (root / "lean-current.old").exists()
    assert marker.read_text() == "old"                       # the workspace was copied, not rebuilt from scratch
    # incompatible bump: the proven dossier regresses → nothing switches, the copy is deleted
    before = (ws / "lake-manifest.json").read_text()
    with pytest.raises(installer.Fail) as e:
        installer.install({**base, "rev": "v2.0.0"})
    assert e.value.key == "regression" and "dep_t" in e.value.detail
    assert (ws / "lake-manifest.json").read_text() == before and not (root / "lean-current.next").exists()
    # user projects (outside the managed root) are refused
    with pytest.raises(installer.Fail) as e:
        installer.install({**base, "allow_any_root": False, "rev": "v1.1.0"})
    assert e.value.key == "not_managed"
    # add a library (verify-then-switch), through scripts/updater.py and its progress protocol
    bar = make_repo(up, "bar", [("v0.1.0", "def Bar.y : Nat := 1\n")])
    spec = tmp_path / "spec.json"
    spec.write_text(json.dumps({**base, "package": "bar", "rev": "v0.1.0", "url": f"file://{bar}", "proofs": []}))
    r = subprocess.run([sys.executable, str(config.STATION_DIR / "scripts" / "updater.py"), "add-library", str(spec)],
                       capture_output=True, text=True, timeout=600)
    assert r.returncode == 0, r.stdout + r.stderr
    lines = r.stdout.splitlines()
    assert "STEP switch" in lines and lines[-1].startswith("DONE ")
    assert json.loads(lines[-1][5:])["op"] == "add"
    assert "bar" in [p["name"] for p in json.loads((ws / "lake-manifest.json").read_text())["packages"]]
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({**base, "package": "evil", "rev": "v1", "url": "https://user:pw@evil/x",
                               "allow_file_urls": False}))
    r = subprocess.run([sys.executable, str(config.STATION_DIR / "scripts" / "updater.py"), "add-library", str(bad)],
                       capture_output=True, text=True, timeout=60)
    assert r.returncode == 1 and r.stdout.strip().startswith("FAIL bad_url")


def test_edit_lakefile_toml(tmp_path):
    (tmp_path / "lakefile.toml").write_text('name = "W"\n\n[[require]]\nname = "mathlib"\ngit = "https://x/m"\n'
                                            'rev = "v4.34.1"\n\n[[require]]\nname = "foo"\ngit = "https://x/foo"\n'
                                            'rev = "v1.0.0"\n')
    installer.edit_lakefile(tmp_path, "foo", "v1.2.0")
    t = (tmp_path / "lakefile.toml").read_text()
    assert 'rev = "v1.2.0"' in t and 'rev = "v4.34.1"' in t
    installer.edit_lakefile(tmp_path, "bar", "main", "https://x/bar", add=True)
    assert 'name = "bar"' in (tmp_path / "lakefile.toml").read_text()
    for bad in (("foo", 'v1"; evil'), ("../x", "v1")):
        with pytest.raises(installer.Fail):
            installer.edit_lakefile(tmp_path, *bad)
    with pytest.raises(installer.Fail):
        installer.edit_lakefile(tmp_path, "nothere", "v1")


# ---------------------------------------------------------------- re-verification after an update
class RegressingLean:
    """Lean stand-in whose verdict depends on the installed « library version »: proofs using `old_api` stop
    compiling after the update."""

    def __init__(self, slots):
        from madalean.brain.fake import FakeLean
        self.inner = FakeLean(slots, 0.01)
        self.updated = False
        self.running = {}

    async def problems(self, ws):
        return []

    async def check(self, code, ws, timeout_s=180, strict_name=None, owner=None):
        if self.updated and "old_api" in code:
            code = code.replace("old_api", "no_such_old_api")
        return await self.inner.check(code, ws, timeout_s, strict_name, owner)

    def kill_all(self):
        pass


async def test_recheck_marks_regressions_after_update(tmp_path):
    ctx = make_ctx(tmp_path)
    ctx.lean = RegressingLean(ctx.slots)
    events = []
    async with running(ctx) as (_s, L, _R), session() as s:
        orig = ctx.bus.publish
        ctx.bus.publish = lambda t, p=None: (events.append((t, p)), orig(t, p))[1]
        ids = {}
        for name, tac in (("good", "exact Even.add ha hb"), ("fragile", "exact old_api ha hb")):
            d = ctx.repo.new(name, ctx.settings.workspace, name)
            st = leancheck.prepare_statement(f"theorem {name}_t (a b : ℕ) (ha : Even a) (hb : Even b) : Even (a + b) := by sorry")
            d.add_statement(st)
            d.add_proof(st.replace(":= by sorry", f":= by\n  {tac}"), meta={"axioms": ["propext"]})
            d.status = "proved"
            await ctx.repo.save(d)
            ids[name] = d.id
        ctx.lean.updated = True
        ctx.updates.on_applied({"kind": "lake-package", "workspace": ctx.settings.workspace, "package": "foo",
                                "rev": "v2.0.0", "removed": []})
        for _ in range(200):
            st = await (await s.get(L + "/api/updates/recheck")).json()
            if st["report"].get("ended"):
                break
            await asyncio.sleep(0.05)
        rep = st["report"]
        assert rep["total"] == 2 and rep["ok"] == 1 and [x["dossier"] for x in rep["regressed"]] == [ids["fragile"]]
        f, g = ctx.repo.get(ids["fragile"]), ctx.repo.get(ids["good"])
        assert f.extra["recheck"]["state"] == "regressed" and g.extra["recheck"]["state"] == "ok"
        assert f.events[-1].kind == "error" and "foo v2.0.0" in f.events[-1].text
        assert any(t == "updates.recheck" and "item" in p and not p["item"]["ok"] for t, p in events)
        assert any(t == "toast" and p["level"] == "warn" for t, p in events)
        # pending state is published before the checks (« à revérifier »)
        pend = [p for t, p in events if t == "dossier.updated" and p["dossier"]["id"] == ids["good"]]
        assert any((p["dossier"].get("recheck") or {}).get("state") == "pending" for p in pend)


async def test_add_library_route_is_host_only_and_guarded(tmp_path):
    ctx = make_ctx(tmp_path)
    async with running(ctx) as (_s, L, Rm), session() as s:
        dev, token = ctx.devices.add("phone")
        r = await s.post(Rm + "/api/workspaces/demo/libraries", json={"name": "x", "url": "https://a/b", "rev": "v1"},
                         headers={"Authorization": f"Bearer {token}"})
        assert r.status == 403 and (await r.json())["error"] == "host_only"
        r = await s.post(L + "/api/workspaces/demo/libraries", json={"name": "x", "url": "https://a/b", "rev": "v1"})
        assert r.status == 409 and (await r.json())["error"] == "readonly_workspace"
        assert (await s.post(L + "/api/workspaces/nope/libraries", json={})).status == 404


@pytest.mark.online
def test_real_online_check_once():
    """Real upstream queries (network): toolchains, Lake packages of the real workspaces, system, llama.cpp,
    Madalean. Prints what it found; only structural assertions."""
    found, errors = [], []
    for name, fn in (("toolchains", lc.toolchain_checker()), ("lake", lc.lake_checker()),
                     ("system", sysc.system_checker()), ("llama", sysc.llama_checker()),
                     ("madalean", sysc.madalean_checker())):
        try:
            cs = fn()
            found += [(name, c.key, c.current, c.latest, c.installable) for c in cs]
        except Exception as e:  # noqa: BLE001
            errors.append(f"{name}: {e}")
    print(json.dumps({"found": found, "errors": errors}, indent=1, ensure_ascii=False))
    assert len(errors) < 5
