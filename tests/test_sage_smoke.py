"""S-AC: the sandboxed kernels get a real, private, short, writable home (root cause of « Read-only file system:
'/nonexistent' » in Maxima, 2026-11-22), and the Sage / Python subsystems a mathematician uses all work in the real
sandboxed kernel — item by item (madalean/research/sagesmoke.py). Plus the same principle for Lean and TeX, and the
health self-test that runs the fast subset after each update (madalean/update_checkers/selftest.py)."""
from __future__ import annotations

import asyncio
import errno
import os
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

from madalean import leansandbox
from madalean.research import sagebridge as sb
from madalean.research import sagesmoke
from helpers import make_ctx

HAVE_SAGE = bool(shutil.which("sage") and shutil.which("jupyter-lab"))
HAVE_PY = bool(shutil.which("jupyter-lab"))
HAVE_BWRAP = bool(shutil.which("bwrap"))
REAL_HOME = os.path.expanduser("~")
DIR_VARS = ("TMPDIR", "XDG_CACHE_HOME", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_STATE_HOME", "XDG_RUNTIME_DIR",
            "DOT_SAGE", "MAXIMA_USERDIR", "MAXIMA_TEMPDIR", "IPYTHONDIR", "MPLCONFIGDIR", "NUMBA_CACHE_DIR",
            "CYTHON_CACHE_DIR", "PYTHONUSERBASE", "TEXMFVAR", "TEXMFCONFIG", "PIP_CACHE_DIR")


# ---------------------------------------------------------------- the kernel's home (launcher, no kernel)
def test_kernel_env_has_a_short_private_home_and_every_cache_inside_it(tmp_path):
    env = {"PATH": "/usr/bin", "OPENAI_API_KEY": "sk-leak", "GITHUB_TOKEN": "ghp_leak", "HOME": REAL_HOME,
           "XDG_CONFIG_HOME": REAL_HOME + "/.config", "JPY_SESSION_NAME": "/x/calcul/p1/calcul.ipynb"}
    cfg = {"workdir": str(tmp_path), "bwrap": "/usr/bin/bwrap", "mem_bytes": 1 << 30, "fsize_bytes": 1 << 29}
    e = sb.launcher_env(cfg, env)
    assert e["HOME"] == sb.SANDBOX_HOME == "/tmp/h"
    assert len(e["HOME"]) + len("/.gap/") < 78                        # GAP's line breaking (see GAP test below)
    for k in DIR_VARS:
        assert e[k].startswith(e["HOME"] + "/"), k
    assert "OPENAI_API_KEY" not in e and "GITHUB_TOKEN" not in e and REAL_HOME not in e.values()
    assert "PYTHONPYCACHEPREFIX" not in e                              # would recompile Sage at every start
    assert e["MADALEAN_SANDBOX"] == "bwrap" and e["MADALEAN_MEM_MB"] == "1024" and e["MADALEAN_FSIZE_MB"] == "512"


def test_home_key_is_per_calcul_project_else_shared():
    assert sb.home_key({"JPY_SESSION_NAME": "/home/u/Documents/Madalean/notebooks/calcul/p-12_a/calcul.ipynb"}) == "p-p-12_a"
    assert sb.home_key({"JPY_SESSION_NAME": "calcul/abc/doc2.ipynb"}) == "p-abc"
    assert sb.home_key({"JPY_SESSION_NAME": "/x/calcul/../../etc/a.ipynb"}) == "shared"
    assert sb.home_key({"JPY_SESSION_NAME": "/x/other.ipynb"}) == "shared" and sb.home_key({}) == "shared"


def test_bwrap_binds_only_the_experiments_dir_and_the_home_inside_it(tmp_path):
    cfg = {"workdir": str(tmp_path), "bwrap": "bwrap", "hide": [], "home_dir": str(tmp_path / ".home" / "shared")}
    argv = sb.bwrap_argv(cfg, ["k"], isolate_net=True)
    binds = [(argv[i + 1], argv[i + 2]) for i, a in enumerate(argv) if a == "--bind"]
    assert binds == [(str(tmp_path), str(tmp_path)), (str(tmp_path / ".home" / "shared"), "/tmp/h")]
    assert argv.index("--tmpfs", argv.index("/run")) < argv.index("/tmp/h")    # mounted after the empty /tmp
    assert "--unshare-net" in argv and argv[argv.index("--ro-bind") + 1:argv.index("--ro-bind") + 3] == ["/", "/"]


def test_prepare_home_is_private_and_cleans_old_temporary_files(tmp_path):
    real = tmp_path / ".home" / "shared"
    sb.prepare_home(str(real))
    assert stat.S_IMODE(real.stat().st_mode) == 0o700
    for d in sb.HOME_SUBDIRS:
        assert (real / d).is_dir(), d
    startup = real / ".ipython/profile_default/startup/00-madalean.py"
    assert startup.read_text() == sb.STARTUP_PY
    old, new = real / ".tmp" / "old", real / ".tmp" / "new"
    old.write_text("x")
    new.write_text("y")
    os.utime(old, (1, 1))
    sb.prepare_home(str(real))
    assert not old.exists() and new.exists()


def test_rlimits_mode_home_is_short_alias_of_the_real_home(tmp_path):
    deep = tmp_path / ("d" * 60) / "experiments"
    real = sb.home_dir({"workdir": str(deep)}, {})
    sb.prepare_home(real)
    h = sb.kernel_home({"workdir": str(deep), "bwrap": ""}, real)
    assert len(h) <= sb.GAP_HOME_MAX and os.path.realpath(h) == os.path.realpath(real)
    st = os.lstat(os.path.dirname(h))
    assert stat.S_ISDIR(st.st_mode) and st.st_uid == os.getuid() and not st.st_mode & 0o077
    assert sb.kernel_home({"workdir": str(deep), "bwrap": ""}, real) == h        # stable
    e = sb.launcher_env({"workdir": str(deep), "bwrap": "", "home": h}, {"PATH": "/usr/bin"})
    assert e["HOME"] == h and e["MAXIMA_USERDIR"].startswith(h) and e["MADALEAN_SANDBOX"] == "rlimits"


def test_group_leftovers_finds_what_a_kernel_left_in_its_process_group():
    """rlimits mode: the launcher kills what the kernel left in its group (Sage's terminate_async helper)."""
    import signal
    p = subprocess.Popen(["sh", "-c", "sleep 30 & sleep 30"], start_new_session=True)
    try:
        import time
        for _ in range(50):
            left = sb.group_leftovers(p.pid, p.pid)
            if len(left) >= 2:
                break
            time.sleep(0.05)
        assert len(left) >= 2 and p.pid not in left and os.getpid() not in left
    finally:
        os.killpg(p.pid, signal.SIGKILL)
        p.wait()


@pytest.mark.skipif(not shutil.which("gap"), reason="gap not installed")
def test_gap_probe_gives_one_line_with_the_short_home_and_would_break_with_a_long_one(tmp_path):
    kinfo = Path("/usr/lib") .glob("python3*/site-packages/sage/ext_data/gap/kernel-info.g")
    f = next(iter(kinfo), None)
    if f is None:
        pytest.skip("sage's kernel-info.g not found")

    def roots(home):
        r = subprocess.run(["gap", "--systemfile", str(f)], env={"PATH": "/usr/bin:/bin", "HOME": home},
                           capture_output=True, text=True, timeout=60)
        return r.stdout.strip().split("\n")
    for home in (sb.SANDBOX_HOME, "/tmp/" + "a" * (sb.GAP_HOME_MAX - 5)):
        out = roots(home)
        assert len(out) == 3 and out[2].startswith(home + "/.gap/;") and "\\" not in out[2], out
    assert len(roots("/tmp/" + "a" * 90)) > 3                         # the bug the short home avoids


def test_startup_hints_explain_sandbox_errors_in_french(monkeypatch):
    shown = []

    class Shell:
        def _showtraceback(self, etype, evalue, stb):
            shown.append(stb)
    sh = Shell()
    monkeypatch.setenv("MADALEAN_SANDBOX", "bwrap")
    monkeypatch.setenv("MADALEAN_WORKDIR", "/w")
    monkeypatch.setenv("MADALEAN_MEM_MB", "4096")
    exec(compile(sb.STARTUP_PY, "00-madalean.py", "exec"), {"get_ipython": lambda: sh})
    import socket
    import urllib.error

    def hint(exc):
        shown.clear()
        sh._showtraceback(type(exc), exc, ["Traceback…"])
        return shown[0][-1] if len(shown[0]) > 1 else ""
    assert "écriture impossible" in hint(OSError(errno.EROFS, "Read-only file system", "/nonexistent"))
    assert "pas d'accès au réseau" in hint(urllib.error.URLError(socket.gaierror(-3, "Temporary failure")))
    assert "pas d'accès au réseau" in hint(ConnectionRefusedError(errno.ECONNREFUSED, "refused"))
    assert "4096 Mo" in hint(MemoryError())
    assert "python-pkgconfig" in hint(ModuleNotFoundError("No module named 'pkgconfig'", name="pkgconfig"))
    assert "512" not in hint(OSError(errno.EFBIG, "File too large")) and "fichier trop gros" in hint(
        OSError(errno.EFBIG, "File too large"))
    try:                                                               # a cascade: the root cause is found
        try:
            raise OSError(errno.EROFS, "Read-only file system", "/nonexistent")
        except OSError as inner:
            raise SystemError("error return without exception set") from inner
    except SystemError as outer:
        assert "écriture impossible" in hint(outer)
    assert hint(ZeroDivisionError("x")) == "" and hint(OSError(errno.EACCES, "denied", "/w/a")) == ""


# ---------------------------------------------------------------- Lean and TeX: private writable homes
class _Ws:
    def __init__(self, p):
        self.path, self.sysroot = p, None

    def lean_path(self):
        return []

    def env(self):
        return {}


def test_lean_and_tex_get_a_private_home_never_the_users(tmp_path):
    e = leansandbox.lean_env(_Ws(tmp_path))
    assert e["HOME"] != REAL_HOME and not e["HOME"].startswith(REAL_HOME + "/")
    assert all(e[k].startswith(e["HOME"] + "/") for k in ("XDG_CACHE_HOME", "XDG_CONFIG_HOME", "XDG_DATA_HOME"))
    from madalean import export
    env = {"HOME": REAL_HOME, "PATH": "/usr/bin"}
    export.tex_confine(["/usr/bin/true"], tmp_path, env)
    assert env["HOME"] == leansandbox.private_home("tex") != REAL_HOME
    assert env["TEXMFVAR"].startswith(env["HOME"] + "/") and env["XDG_CACHE_HOME"].startswith(env["HOME"] + "/")


@pytest.mark.skipif(not leansandbox.bwrap(), reason="bubblewrap unavailable")
def test_lean_and_tex_sandboxes_have_a_writable_home_and_still_no_network_nor_user_home(tmp_path):
    from madalean import export
    probe = ('mkdir -p "$XDG_CACHE_HOME/x" && touch "$XDG_CACHE_HOME/x/f" && echo HOME_W; '
             'touch /usr/madalean-probe 2>/dev/null && echo WROTE; '
             f'ls {REAL_HOME}/.config >/dev/null 2>&1 && echo SEES; grep -c : /proc/net/dev')
    ws = tmp_path / "ws"
    ws.mkdir()
    argv = leansandbox.wrap(_Ws(ws), ["/bin/sh", "-c", probe + f"; touch {ws}/w 2>/dev/null && echo WROTE"], [])
    assert "--dir" in argv and argv[argv.index("--dir") + 1] == "/tmp/home"
    out = subprocess.run(argv, env=leansandbox.lean_env(_Ws(ws)), capture_output=True, text=True, timeout=30).stdout
    assert "HOME_W" in out and "WROTE" not in out and "SEES" not in out and "\n1\n" in "\n" + out, out
    work = tmp_path / "texwork"
    work.mkdir()
    env = export.tex_env()
    cmd = export.tex_confine(["/bin/sh", "-c", probe + '; mkdir -p "$TEXMFVAR" && echo TEXMF_W'], work, env)
    out = subprocess.run(cmd, env=env, cwd=work, capture_output=True, text=True, timeout=30).stdout
    assert "HOME_W" in out and "TEXMF_W" in out and "WROTE" not in out and "SEES" not in out, out
    assert "\n1\n" in "\n" + out, out                                  # only lo


# ---------------------------------------------------------------- the real kernels: every item
async def _suite(tmp: Path, language: str, sandbox: bool, fast: bool = False) -> dict:
    ctx = make_ctx(tmp)
    b = sb.SageBridge(ctx, sandbox=sandbox)
    try:
        rep = await sagesmoke.run(b, language, sagesmoke.items_for(language, fast, b.sandbox_kind))
        rep["workroot"] = str(b.workroot)
        return rep
    finally:
        await ctx.jupyter.stop()


@pytest.fixture(scope="module")
def sage_report(tmp_path_factory):
    if not HAVE_SAGE:
        pytest.skip("sage / jupyter-lab not installed")
    return asyncio.run(_suite(tmp_path_factory.mktemp("sage"), "sage", sandbox=True))


@pytest.fixture(scope="module")
def python_report(tmp_path_factory):
    if not HAVE_PY:
        pytest.skip("jupyter-lab not installed")
    return asyncio.run(_suite(tmp_path_factory.mktemp("py"), "python", sandbox=True))


def _row(rep: dict, iid: str) -> dict:
    assert not rep["error"], rep["error"]
    row = next((r for r in rep["items"] if r["id"] == iid), None)
    assert row is not None, f"{iid} did not run: {[r['id'] for r in rep['items']]}"
    return row


@pytest.mark.sage
@pytest.mark.parametrize("iid", [i.id for i in sagesmoke.SAGE])
def test_sage_subsystem_in_the_sandboxed_kernel(sage_report, iid):
    if sage_report["sandbox"] != "bwrap" and next(i for i in sagesmoke.SAGE if i.id == iid).sandbox_only:
        pytest.skip("needs bubblewrap")
    row = _row(sage_report, iid)
    assert row["ok"], row


@pytest.mark.sage
@pytest.mark.parametrize("iid", [i.id for i in sagesmoke.PYTHON])
def test_python_subsystem_in_the_sandboxed_kernel(python_report, iid):
    if python_report["sandbox"] != "bwrap" and next(i for i in sagesmoke.PYTHON if i.id == iid).sandbox_only:
        pytest.skip("needs bubblewrap")
    row = _row(python_report, iid)
    assert row["ok"], row


@pytest.mark.sage
def test_kernel_home_is_persistent_under_the_experiments_dir(sage_report):
    home = Path(sage_report["workroot"]) / ".home" / "shared"
    assert (home / ".cache" / "madalean-smoke").read_text() == "ok"     # written by the « home » item as ~/.cache
    assert (home / ".sage" / "maxima").is_dir()                        # Maxima's cache survives restarts
    assert stat.S_IMODE(home.stat().st_mode) == 0o700


@pytest.mark.sage
@pytest.mark.skipif(not HAVE_SAGE, reason="sage / jupyter-lab not installed")
async def test_rlimits_only_mode_is_as_consistent(tmp_path):
    """Without bubblewrap (accepted risk R-3) the kernel still gets a writable private home at a short path."""
    rep = await _suite(tmp_path, "sage", sandbox=False, fast=True)
    assert rep["sandbox"] == "rlimits"
    assert rep["ok"], [r for r in rep["items"] if not r["ok"]] or rep["error"]


# ---------------------------------------------------------------- health self-test
def test_selftest_health_lines(tmp_path):
    from madalean.update_checkers import selftest
    ctx = make_ctx(tmp_path)
    st = selftest.SelfTest(ctx, tmp_path / "selftest.json")
    lines = {c["id"]: c for c in st.health()}
    assert set(lines) == {f"selftest_{p}" for p in selftest.PARTS} and all(c["ok"] for c in lines.values())
    assert "pas encore lancé" in lines["selftest_sage"]["message"]["text"]
    st.report = {"parts": {"sage": {"state": "failed", "items": [{"id": "fourier", "label": "Série de Fourier",
                                                                  "ok": False}]},
                           "python": {"state": "ok", "items": [{"ok": True}], "seconds": 3, "t": 1},
                           "lean": {"state": "absent"}, "tex": {"state": "failed", "error": "boom\nmore"}}}
    lines = {c["id"]: c for c in st.health()}
    assert not lines["selftest_sage"]["ok"] and "Série de Fourier" in lines["selftest_sage"]["message"]["text"]
    assert lines["selftest_python"]["ok"] and "1 essais réussis" in lines["selftest_python"]["message"]["text"]
    assert lines["selftest_lean"]["ok"] and "non installé" in lines["selftest_lean"]["message"]["text"]
    assert not lines["selftest_tex"]["ok"] and "(boom)" in lines["selftest_tex"]["message"]["text"]
    fp = selftest.fingerprint(ctx)
    assert fp == selftest.fingerprint(ctx) and "madalean" in fp


async def test_selftest_repair_moves_homes_aside_and_maybe_run_follows_the_fingerprint(tmp_path, monkeypatch):
    from madalean.update_checkers import selftest
    ctx = make_ctx(tmp_path)
    st = selftest.SelfTest(ctx, tmp_path / "selftest.json")
    runs = []

    async def fake_part(*a):
        runs.append(a)
        return {"state": "ok", "items": [], "seconds": 0}
    monkeypatch.setattr(st, "_kernel", fake_part)
    monkeypatch.setattr(st, "_lean", fake_part)
    monkeypatch.setattr(st, "_tex", fake_part)
    home = st.bridge().workroot / ".home" / "shared"
    home.mkdir(parents=True)
    (home / "broken").write_text("x")
    rep = await st.repair()
    assert not home.exists() and (st.bridge().workroot / ".home.old" / "shared" / "broken").exists()
    assert rep["reason"] == "repair" and len(runs) == 4 and (tmp_path / "selftest.json").exists()
    assert await st.maybe_run() is False                       # same fingerprint: nothing to do
    st.report["fingerprint"] = {"madalean": "old"}
    assert await st.maybe_run() is True
    await st.running
    assert len(runs) == 8


@pytest.mark.sage
@pytest.mark.skipif(not (HAVE_SAGE and HAVE_BWRAP), reason="sage / jupyter-lab / bwrap missing")
async def test_selftest_end_to_end_with_the_real_tools(tmp_path):
    from madalean.server.routes_core import health
    from madalean.update_checkers import selftest
    ctx = make_ctx(tmp_path)
    st = selftest.install(ctx)
    try:
        rep = await st.run("test", parts=("sage", "python", "tex"))
    finally:
        await ctx.jupyter.stop()
    for part in ("sage", "python"):
        assert rep["parts"][part]["state"] == "ok", rep["parts"][part]
    assert rep["parts"]["tex"]["state"] in ("ok", "absent"), rep["parts"]["tex"]
    checks = {c["id"]: c for c in await health(ctx)}
    assert checks["selftest_sage"]["ok"] and checks["selftest_sage"]["repair"] == "selftest_run"
    assert checks["selftest_sage"]["rerun"] is True


@pytest.mark.skipif(not leansandbox.bwrap(), reason="bubblewrap unavailable")
async def test_selftest_lean_part_with_the_real_workspace(tmp_path, ws):
    from madalean.update_checkers import selftest
    ctx = make_ctx(tmp_path, ws=ws)
    st = selftest.SelfTest(ctx, tmp_path / "selftest.json")
    res = await st._lean()
    assert res["state"] == "ok", res
    assert [i["id"] for i in res["items"]] == ["compile", "sandbox"]


def test_kernel_env_caps_compute_threads_and_address_space(monkeypatch):
    """2026-11-23 regression: 16 OpenBLAS threads pushed `import sage.all` over the 4 GB RLIMIT_AS cap (the kernel
    died at start). The kernel gets at most MAX_COMPUTE_THREADS BLAS/OpenMP threads, and the cap keeps a margin for
    reserved-but-unused address space."""
    from madalean.research import sagebridge as sb
    monkeypatch.setattr(sb.os, "cpu_count", lambda: 16)
    env = sb.launcher_env({"workdir": "/tmp/w", "bwrap": None, "home": "/tmp/h"}, {"OPENBLAS_NUM_THREADS": "64"})
    for k in sb.THREAD_VARS:
        assert env[k] == str(sb.MAX_COMPUTE_THREADS)          # the server's own value never reaches the kernel
    monkeypatch.setattr(sb.os, "cpu_count", lambda: 2)
    assert sb.launcher_env({"workdir": "/tmp/w", "bwrap": None, "home": "/tmp/h"}, {})["OMP_NUM_THREADS"] == "2"
    assert sb.address_space_limit(4 << 30) == (4 << 30) + sb.AS_MARGIN_BYTES and sb.address_space_limit(0) == 0
