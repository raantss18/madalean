"""S-AO (TODO B15, DECISIONS D47): « Calcul prêt d'avance » — opening a Calcul document (or its project) starts its
sandboxed kernel in the background and runs the first-use initialisations (Maxima, plots, finite fields) outside the
history; the user's first run stops the warm-up at its current step; first-use caches are prepared once per Sage
version (`<experiments>/.home/.seed`); bounded (≤ WARM_MAX_UNUSED unused kernels, memory floor), a setting, a
health row. The real-Sage test (marker `sage`) measures the first integral after the warm-up."""
from __future__ import annotations

import asyncio
import os
import shutil
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from helpers import make_ctx, running, session
from madalean.research import nbkernels as nk
from madalean.research import sagebridge as sb
from madalean.research.sagebridge import ExecResult
from madalean.server.plugins import workbench as wbm


# ---------------------------------------------------------------- the seed of first-use caches
def _touch(p: Path, data: bytes = b"x", t: float | None = None) -> Path:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(data)
    if t is not None:
        os.utime(p, (t, t))
    return p


def test_harvest_copies_only_new_seed_files_and_seed_home_fills_what_is_missing(tmp_path):
    a, b = tmp_path / ".home" / "p-a", tmp_path / ".home" / "p-b"
    since = time.time() - 5
    _touch(a / ".sage/maxima/binary/5_50_0/ecl/26/share/lu.fas", b"fas")
    _touch(a / ".sage/maxima/test-directory-cached/5_50_0", b"")
    _touch(a / ".sage/cache/abc-lazy_import_cache.pickle", b"pk")
    _touch(a / ".config/matplotlib/fontlist-v3.11.0.json", b"{}")
    _touch(a / ".sage/maxima/binary/5_50_0/old.fas", b"old", t=since - 100)     # existed before the warm-up
    _touch(a / ".cache/madalean-smoke", b"user")                               # not a seed pattern
    _touch(a / ".sage/init.sage", b"print('user')")                            # never copied
    os.symlink("/etc/passwd", a / ".sage/maxima/binary/5_50_0/link.fas")       # never followed
    assert sb.harvest_seed(str(a), since) == 4
    seed = tmp_path / ".home" / ".seed"
    assert sb.seed_dir(str(a)) == str(seed)
    got = sorted(str(p.relative_to(seed)) for p in seed.rglob("*") if p.is_file())
    assert got == [".config/matplotlib/fontlist-v3.11.0.json", ".sage/cache/abc-lazy_import_cache.pickle",
                   ".sage/maxima/binary/5_50_0/ecl/26/share/lu.fas", ".sage/maxima/test-directory-cached/5_50_0"]
    assert sb.harvest_seed(str(a), since) == 0                                 # idempotent
    _touch(b / ".config/matplotlib/fontlist-v3.11.0.json", b"mine")            # what a home has is kept
    assert sb.seed_home(str(b)) == 3
    assert (b / ".config/matplotlib/fontlist-v3.11.0.json").read_bytes() == b"mine"
    assert (b / ".sage/maxima/binary/5_50_0/ecl/26/share/lu.fas").read_bytes() == b"fas"
    assert not (b / ".sage/init.sage").exists() and not (b / ".cache/madalean-smoke").exists()
    assert sb.seed_home(str(b)) == 0


def test_seed_is_size_capped_and_refuses_a_symlinked_seed(tmp_path, monkeypatch):
    a = tmp_path / ".home" / "p-a"
    for i in range(5):
        _touch(a / f".sage/maxima/binary/v/f{i}.fas", b"1" * 100)
    monkeypatch.setattr(sb, "SEED_MAX_BYTES", 250)
    assert sb.harvest_seed(str(a), 0) == 2
    other = tmp_path / "elsewhere"
    other.mkdir()
    shutil.rmtree(tmp_path / ".home" / ".seed")
    os.symlink(other, tmp_path / ".home" / ".seed")
    assert sb.harvest_seed(str(a), 0) == 0 and sb.seed_home(str(tmp_path / ".home" / "p-b")) == 0
    assert not any(other.iterdir())


def test_seed_kernel_has_its_own_home():
    assert sb.home_key({"JPY_SESSION_NAME": "/n/calcul/.seed/seed.ipynb"}) == "warm-seed"
    assert sb.home_key({"JPY_SESSION_NAME": nk.SEED_PATH}) == "warm-seed"
    assert sb.home_key({"JPY_SESSION_NAME": "/n/calcul/p1/.seed.ipynb"}) == "p-p1"


def test_kernelspec_carries_the_seed_switch(tmp_path):
    import json
    ctx = make_ctx(tmp_path)
    b = sb.SageBridge(ctx)
    if not b.install_specs():
        pytest.skip("no kernel installed")
    d = Path(ctx.jupyter.share_dir) / "kernels"
    ctx.settings.calcul_warm = False
    b.install_specs()
    cfg = json.loads(next(d.glob("*/launcher.json")).read_text())
    assert cfg["seed"] is False                         # the setting off: no seeded caches either
    ctx.settings.calcul_warm = True
    b.install_specs()
    assert json.loads(next(d.glob("*/launcher.json")).read_text())["seed"] is True


def test_mem_available(tmp_path):
    f = tmp_path / "meminfo"
    f.write_text("MemTotal: 32000000 kB\nMemAvailable:    2048000 kB\n")
    assert nk.mem_available_mb(str(f)) == 2000
    assert nk.mem_available_mb(str(tmp_path / "none")) is None


# ---------------------------------------------------------------- the warm-up logic (fake kernel)
class FakeBridge:
    sandbox_kind = "bwrap"

    def __init__(self, root: Path, step_s: float = 0.05):
        self.workroot = root
        self.step_s = step_s
        self.calls: list[tuple] = []

    async def execute(self, kid, code, *, timeout, language="", store_history=False, kill_on_limit=True, **kw):
        self.calls.append((kid, code, store_history))
        await asyncio.sleep(self.step_s)
        return ExecResult("ok", language=language)

    async def shutdown(self, kid):
        pass


def _kernels(tmp_path, step_s=0.05):
    k = nk.NotebookKernels(SimpleNamespace(jupyter=SimpleNamespace(root_dir=tmp_path / "nb")),
                           FakeBridge(tmp_path / "exp", step_s))
    starts = []

    async def session_for(path):
        return None

    async def ensure(path, language):
        if path not in k.docs:
            starts.append(path)
            await asyncio.sleep(0.01)
            k.docs[path] = {"kid": "k-" + path, "ready": "k-" + path, "language": language, "last": time.time(),
                            "engine": {"name": "SageMath", "version": "10.10"}}
        return k.docs[path]["kid"]

    async def shutdown(path):
        k.docs.pop(path, None)
        k.warm.pop(path, None)
        t = k._warm_tasks.pop(path, None)
        if t is not None and not t.done() and t is not asyncio.current_task():
            t.cancel()
    k.session_for, k.ensure, k.shutdown = session_for, ensure, shutdown
    return k, starts


async def _until(cond, timeout=5.0):
    t0 = time.monotonic()
    while not cond():
        assert time.monotonic() - t0 < timeout, "timeout"
        await asyncio.sleep(0.01)


async def test_prewarm_runs_every_step_outside_the_history_and_is_idempotent(tmp_path, monkeypatch):
    monkeypatch.setattr(nk, "mem_available_mb", lambda: 8000)
    k, starts = _kernels(tmp_path)
    monkeypatch.setattr(k, "_prepare_seed", lambda: asyncio.sleep(0))
    st = k.prewarm("calcul/p/a.ipynb", "sage")
    assert st["state"] == "starting"
    assert k.prewarm("calcul/p/a.ipynb", "sage")["state"] == "starting"            # one task per document
    await _until(lambda: k.warm_status("calcul/p/a.ipynb")["state"] == "ready")
    w = k.warm_status("calcul/p/a.ipynb")
    assert list(w["steps"]) == [n for n, _ in nk.SAGE_WARMUP] and not w["used"] and "error" not in w
    assert starts == ["calcul/p/a.ipynb"]
    assert all(store is False for _kid, _code, store in k.bridge.calls)             # outside the history
    assert all("_madalean_w" in code and "del _madalean_w" in code for _k, code, _s in k.bridge.calls)
    n = len(k.bridge.calls)
    k.prewarm("calcul/p/a.ipynb", "sage")
    await asyncio.sleep(0.1)
    assert len(k.bridge.calls) == n                                               # ready: nothing again
    py = k.prewarm("calcul/p/b.ipynb", "python")
    await _until(lambda: k.warm_status("calcul/p/b.ipynb")["state"] == "ready")
    assert py and list(k.warm_status("calcul/p/b.ipynb")["steps"]) == [n for n, _ in nk.PYTHON_WARMUP]
    summary = k.warm_summary()
    assert summary["live"] == 2 and summary["loading"] == 0 and len(summary["last"]) == 2


async def test_the_users_run_stops_the_warm_up_at_its_current_step(tmp_path, monkeypatch):
    monkeypatch.setattr(nk, "mem_available_mb", lambda: 8000)
    k, _ = _kernels(tmp_path, step_s=0.3)
    seeds = []
    monkeypatch.setattr(k, "_prepare_seed", lambda: seeds.append(1) or asyncio.sleep(0))
    k.prewarm("calcul/p/a.ipynb", "sage")
    await _until(lambda: k.bridge.calls)                                          # the first step is running
    k._mark_used("calcul/p/a.ipynb")                                              # what execute() / probe() do
    await _until(lambda: k.warm_status("calcul/p/a.ipynb")["state"] == "ready")
    w = k.warm_status("calcul/p/a.ipynb")
    assert len(k.bridge.calls) == 1 and list(w["steps"]) == ["integral"] and w["used"]
    assert "seeded" not in w                                  # never harvested from a kernel the user used …
    assert seeds == [1]                                       # … the seed is prepared aside instead, once
    k.warm.pop("calcul/p/a.ipynb")
    k.docs.pop("calcul/p/a.ipynb")
    k.prewarm("calcul/p/a.ipynb", "sage")
    await _until(lambda: k.warm_status("calcul/p/a.ipynb")["state"] == "ready")
    assert seeds == [1]


async def test_execute_marks_the_document_used(tmp_path):
    k, _ = _kernels(tmp_path)
    k.warm["calcul/p/a.ipynb"] = {"state": "warming", "used": False, "steps": {}, "t0": time.time()}

    async def ensure(path, language):
        raise nk.KernelError("kernel_unavailable", 503)
    k.ensure = ensure
    await k.execute("calcul/p/a.ipynb", "sage", "1+1", timeout=5)
    assert k.warm["calcul/p/a.ipynb"]["used"] is True


async def test_unused_kernels_are_bounded_and_memory_floor_respected(tmp_path, monkeypatch):
    monkeypatch.setattr(nk, "mem_available_mb", lambda: 8000)
    k, _ = _kernels(tmp_path, step_s=0.0)
    monkeypatch.setattr(k, "_prepare_seed", lambda: asyncio.sleep(0))
    for i in range(nk.WARM_MAX_UNUSED + 1):
        k.prewarm(f"calcul/p/d{i}.ipynb", "python")
        await _until(lambda: k.warm_status(f"calcul/p/d{i}.ipynb")["state"] == "ready")
    assert "calcul/p/d0.ipynb" not in k.docs                                     # the oldest unused one stopped
    assert len(k.docs) == nk.WARM_MAX_UNUSED
    k._mark_used("calcul/p/d1.ipynb")                                            # used kernels are not counted
    k.prewarm("calcul/p/d9.ipynb", "python")
    await _until(lambda: k.warm_status("calcul/p/d9.ipynb")["state"] == "ready")
    assert {"calcul/p/d1.ipynb", "calcul/p/d2.ipynb", "calcul/p/d9.ipynb"} <= set(k.docs)
    k.prewarm("calcul/p/d10.ipynb", "python")
    await _until(lambda: k.warm_status("calcul/p/d10.ipynb")["state"] == "ready")
    assert "calcul/p/d1.ipynb" in k.docs and "calcul/p/d2.ipynb" not in k.docs
    monkeypatch.setattr(nk, "mem_available_mb", lambda: 500)
    k.prewarm("calcul/p/low.ipynb", "sage")
    await _until(lambda: k.warm_status("calcul/p/low.ipynb")["state"] == "skipped")
    assert "calcul/p/low.ipynb" not in k.docs and "500 MB" in k.warm_status("calcul/p/low.ipynb")["error"]


async def test_a_step_error_is_reported_and_nothing_harvested(tmp_path, monkeypatch):
    monkeypatch.setattr(nk, "mem_available_mb", lambda: 8000)
    k, _ = _kernels(tmp_path)
    monkeypatch.setattr(k, "_prepare_seed", lambda: asyncio.sleep(0))

    async def execute(kid, code, **kw):
        return ExecResult("error", error="ValueError: boom" if "integrate" in code else "")
    k.bridge.execute = execute
    k.prewarm("calcul/p/a.ipynb", "sage")
    await _until(lambda: k.warm_status("calcul/p/a.ipynb")["state"] == "ready")
    w = k.warm_status("calcul/p/a.ipynb")
    assert w["steps"]["integral"] == "error" and "boom" in w["error"] and "seeded" not in w
    assert "boom" in k.warm_summary()["failed"][0]


# ---------------------------------------------------------------- server: GET opens, POST /warm, setting, health
class WarmFake:
    def __init__(self):
        self.calls: list[tuple] = []

    def known(self, path):
        return ""

    def epoch(self, path):
        return ""

    async def status(self, path):
        return {"kernel": "", "state": "none"}

    def warm_status(self, path):
        return {"state": "ready" if any(p == path for p, _ in self.calls) else "none"}

    def prewarm(self, path, language):
        self.calls.append((path, language))
        return {"state": "starting"}

    def warm_summary(self):
        return {"live": len(self.calls), "loading": 0, "unused": 0, "failed": [], "skipped": [], "last": [],
                "seed": {}, "seeding": False}


async def test_opening_a_document_or_its_project_prepares_the_kernel(tmp_path, monkeypatch):
    fake = WarmFake()
    monkeypatch.setattr(wbm.Workbench, "kernels", lambda self: fake)
    monkeypatch.setattr(sb.SageBridge, "available", lambda self: {"sage": True, "python": True})
    monkeypatch.delenv("MADALEAN_NO_CALCUL_WARM")
    ctx = make_ctx(tmp_path)
    async with running(ctx) as (srv, L, R), session() as s:
        ctx.settings.calcul_warm = False
        pid = (await (await s.post(L + "/api/projects", json={"title": "P"})).json())["project"]["id"]
        empty = (await (await s.post(L + "/api/projects", json={"title": "Q"})).json())["project"]["id"]
        # a project without Calcul: nothing created, nothing started
        j = await (await s.post(L + f"/api/calcul/{empty}/warm", json={})).json()
        assert j == {"warm": {"state": "none"}, "doc": None}
        assert not (ctx.jupyter.root_dir / "calcul" / empty).exists()
        a = (await (await s.post(L + f"/api/calcul/{pid}/docs", json={"title": "A", "language": "python"}))
             .json())["doc"]["id"]
        # the setting is off: nothing starts
        v = await (await s.get(L + f"/api/calcul/{pid}/docs/{a}")).json()
        assert v["status"]["warm"] == {"state": "off"} and fake.calls == []
        ctx.settings.calcul_warm = True
        v = await (await s.get(L + f"/api/calcul/{pid}/docs/{a}")).json()
        assert v["status"]["warm"]["state"] == "starting"
        assert fake.calls == [(f"calcul/{pid}/{a}.ipynb", "python")]
        b = (await (await s.post(L + f"/api/calcul/{pid}/docs", json={"title": "B", "language": "sage"}))
             .json())["doc"]["id"]
        os.utime(ctx.jupyter.root_dir / "calcul" / pid / f"{b}.ipynb", (time.time() + 10, time.time() + 10))
        r = await s.post(L + f"/api/calcul/{pid}/warm", json={})
        assert r.status == 202 and (await r.json())["doc"] == b                  # the most recently changed one
        assert fake.calls[-1] == (f"calcul/{pid}/{b}.ipynb", "sage")
        r = await s.post(L + f"/api/calcul/{pid}/warm", json={"doc": a})
        assert (await r.json())["doc"] == a
        # a paired device that may not run cells does not start kernels
        n = len(fake.calls)
        r = await s.post(R + f"/api/calcul/{pid}/warm", json={})
        assert r.status in (200, 401, 403) and len(fake.calls) == n
        # health row
        sysj = await (await s.get(L + "/api/system")).json()
        row = next(c for c in sysj["checks"] if c["id"] == "calcul_warm")
        assert row["ok"] and "prêt" in row["message"]["text"]
        ctx.settings.calcul_warm = False
        sysj = await (await s.get(L + "/api/system")).json()
        row = next(c for c in sysj["checks"] if c["id"] == "calcul_warm")
        assert "désactivé" in row["message"]["text"]


async def test_calcul_warm_is_a_host_only_setting(tmp_path):
    from madalean.context import HOST_ONLY_SETTINGS
    assert "calcul_warm" in HOST_ONLY_SETTINGS
    from madalean import config
    assert config.Settings().calcul_warm is True


# ---------------------------------------------------------------- real Sage
HAVE_SAGE = bool(shutil.which("sage") and shutil.which("jupyter-lab"))


@pytest.mark.sage
@pytest.mark.skipif(not HAVE_SAGE, reason="sage / jupyter-lab not installed")
async def test_real_sage_kernel_ready_in_advance_and_caches_prepared_once(tmp_path, monkeypatch):
    monkeypatch.delenv("MADALEAN_NO_CALCUL_WARM")
    ctx = make_ctx(tmp_path)
    async with running(ctx) as (srv, L, _R), session() as s:
        ctx.settings.calcul_warm = True
        ctx.settings.experiments_auto = True
        async def new_doc():
            pid = (await (await s.post(L + "/api/projects", json={"title": "P"})).json())["project"]["id"]
            doc = (await (await s.post(L + f"/api/calcul/{pid}/docs", json={"title": "S", "language": "sage"}))
                   .json())["doc"]["id"]
            return pid, L + f"/api/calcul/{pid}/docs/{doc}"

        async def wait_ready(D):
            t0 = time.monotonic()
            while time.monotonic() - t0 < 300:
                st = (await (await s.get(D)).json())["status"]["warm"]
                if st["state"] in ("ready", "failed", "skipped"):
                    return st
                await asyncio.sleep(0.3)
            raise TimeoutError

        async def run(D, src):
            c = (await (await s.post(D + "/cells", json={"source": src})).json())["cell"]
            t0 = time.monotonic()
            r = (await (await s.post(D + f"/cells/{c['id']}/run", json={"timeout": 300})).json())["run"]
            return r, time.monotonic() - t0

        pid, D = await new_doc()
        st = await wait_ready(D)
        assert st["state"] == "ready" and "error" not in st, st
        assert set(st["steps"]) == {"integral", "plot", "finite_field"} and st["seeded"] > 0
        r, dt = await run(D, "integrate(x*sin(x), x)")
        assert r["status"] == "ok" and "sin(x)" in r["outputs"][0]["data"]["text/plain"] and dt < 3.0, (r, dt)
        import json
        ipynb = json.loads(await (await s.get(D + "/ipynb")).read())
        assert [c["execution_count"] for c in ipynb["cells"] if c["cell_type"] == "code"] == [1]   # outside history
        r, _ = await run(D, "_madalean_w")
        assert r["status"] == "error" and "NameError" in r["error"]           # no name left behind
        seed = srv.app[wbm.WB].bridge().workroot / ".home" / ".seed"
        assert any(seed.glob(".done-*")) and any(seed.glob(".sage/maxima/binary/*"))
        # a second new project: its home is seeded at kernel start, its integral warm-up is short
        _pid2, D2 = await new_doc()
        st2 = await wait_ready(D2)
        assert st2["state"] == "ready" and st2["steps"]["integral"] < st["steps"]["integral"] / 2, (st, st2)
        sysj = await (await s.get(L + "/api/system")).json()
        row = next(c for c in sysj["checks"] if c["id"] == "calcul_warm")
        assert row["ok"] and "2 noyau" in row["message"]["text"], row
    await ctx.jupyter.stop()
