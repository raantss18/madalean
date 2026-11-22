"""First-run assistant « Premiers pas » (S-AQ, D49): /api/setup/wizard, /api/setup/reuse, /api/setup/models.

Fakes only: the model download is a small Python script writing tiny files into a temporary models dir; system Sage
and TeX Live are fake kernel specs / scripts in temporary dirs. Nothing is downloaded or installed."""
from __future__ import annotations

import asyncio
import json
import sys

import aiohttp

from madalean import config
from madalean.server.plugins import setup_api

from helpers import make_ctx, running


async def _json(r):
    return r.status, await r.json()


async def test_wizard_progress_host_only_and_persisted(tmp_path, monkeypatch):
    monkeypatch.setenv("MADALEAN_NO_NET", "1")
    ctx = make_ctx(tmp_path)
    async with running(ctx) as (_srv, local, remote):
        async with aiohttp.ClientSession() as s:
            st, w = await _json(await s.get(local + "/api/setup/wizard"))
            assert st == 200 and w["schema"] == "madalean-first-run/1"
            assert w["step"] == "welcome" and w["visited"] == [] and w["auto"] is True and w["done"] is False
            assert w["steps"][0] == "welcome" and w["steps"][-1] == "done"
            for path in ("/api/setup/wizard",):
                async with s.get(remote + path) as r:
                    assert r.status in (401, 403)
                async with s.patch(remote + path, json={"step": "keys"}) as r:
                    assert r.status in (401, 403)
            for bad in ({"step": "nope"}, {"visited": ["keys", "x"]}, {"done": "yes"}, {"models": "huge"}, {"x": 1}):
                async with s.patch(local + "/api/setup/wizard", json=bad) as r:
                    assert r.status == 400, bad
            st, w = await _json(await s.patch(local + "/api/setup/wizard",
                                              json={"step": "keys", "visited": ["tools", "welcome"], "models": "prover"}))
            assert st == 200 and w["step"] == "keys" and w["visited"] == ["welcome", "tools"] and w["models"] == "prover"
            st, w = await _json(await s.patch(local + "/api/setup/wizard", json={"visited": ["local"]}))
            assert w["visited"] == ["welcome", "tools", "local"]                 # merged, in step order
            # « Plus tard »: never opens by itself again, the Home card stays until it is finished
            st, w = await _json(await s.patch(local + "/api/setup/wizard", json={"done": True}))
            assert w["done"] is True and w["auto"] is False and w["completed"] is False and w["reminder"] is True
            assert ctx.settings.wizard_done is True
            assert json.loads((tmp_path / "config" / "settings.json").read_text())["wizard_done"] is True
            st, d = await _json(await s.get(local + "/api/setup"))
            assert d["wizard"]["step"] == "keys" and d["prefs"]["wizard_done"] is True
            assert {f["key"] for f in d["models"]["files"]} == {"Q4_K_M", "formalizer", "explainer"}
    # a restart resumes where the user stopped
    ctx2 = make_ctx(tmp_path)
    async with running(ctx2) as (_srv, local, _remote):
        async with aiohttp.ClientSession() as s:
            st, w = await _json(await s.get(local + "/api/setup/wizard"))
            assert w["step"] == "keys" and w["models"] == "prover" and w["done"] is True
            st, w = await _json(await s.patch(local + "/api/setup/wizard", json={"done": False}))
            assert w["auto"] is True                                            # resumable from the start again
            st, w = await _json(await s.patch(local + "/api/setup/wizard", json={"completed": True, "step": "done"}))
            assert w["completed"] is True and w["done"] is True and w["auto"] is False


async def test_update_with_existing_work_does_not_open_by_itself(tmp_path, monkeypatch):
    monkeypatch.setenv("MADALEAN_NO_NET", "1")
    ctx = make_ctx(tmp_path)
    async with running(ctx):
        d = ctx.repo.new("Montrer que 1 + 1 = 2.", "demo")
        await ctx.repo.save(d)
    ctx2 = make_ctx(tmp_path)                                    # a 2.0.0 user updating: their dossiers are there
    async with running(ctx2) as (_srv, local, _remote):
        async with aiohttp.ClientSession() as s:
            st, w = await _json(await s.get(local + "/api/setup/wizard"))
            assert st == 200 and w["auto"] is False and w["done"] is False and w["completed"] is False


async def test_reuse_checked_against_the_machine(tmp_path, monkeypatch):
    from madalean.research import sagebridge
    monkeypatch.setenv("MADALEAN_NO_NET", "1")
    own, sysd = tmp_path / "own", tmp_path / "sys"
    own.mkdir()
    sysd.mkdir()
    monkeypatch.setattr(sagebridge, "PREFIX_KERNELS", str(own))
    monkeypatch.setattr(sagebridge, "KERNEL_DIRS", [str(own), str(sysd)])
    monkeypatch.setattr(setup_api, "_DETECTED", {"tools": {}})
    bindir = tmp_path / "bin"
    bindir.mkdir()
    monkeypatch.setenv("PATH", str(bindir))                     # no xelatex, no tectonic
    ctx = make_ctx(tmp_path)
    try:
        async with running(ctx) as (_srv, local, remote):
            async with aiohttp.ClientSession() as s:
                async with s.post(remote + "/api/setup/reuse", json={"sage_source": "auto"}) as r:
                    assert r.status in (401, 403)
                for bad in ({}, {"sage_source": "auto", "mode": "local"}):
                    async with s.post(local + "/api/setup/reuse", json=bad) as r:
                        assert r.status == 400
                st, e = await _json(await s.post(local + "/api/setup/reuse", json={"sage_source": "system"}))
                assert st == 409 and e["reason"] == "no_system_sage" and ctx.settings.sage_source == "auto"
                st, e = await _json(await s.post(local + "/api/setup/reuse", json={"tex_engine": "system"}))
                assert st == 409 and e["reason"] == "no_system_tex"
                st, e = await _json(await s.post(local + "/api/setup/reuse", json={"tex_engine": "tectonic"}))
                assert st == 409 and e["reason"] == "no_tectonic"
                st, e = await _json(await s.post(local + "/api/setup/reuse", json={"sage_source": "bogus"}))
                assert st == 409 and e["reason"] == "invalid"
                # a system Sage with its kernel, and a system XeLaTeX: accepted and saved
                (sysd / "sagemath").mkdir()
                (sysd / "sagemath" / "kernel.json").write_text(json.dumps({"argv": ["/usr/bin/sage-python"]}))
                xe = bindir / "xelatex"
                xe.write_text("#!/bin/sh\nexit 0\n")
                xe.chmod(0o755)
                st, d = await _json(await s.post(local + "/api/setup/reuse",
                                                 json={"sage_source": "system", "tex_engine": "system"}))
                assert st == 200 and d["prefs"]["sage_source"] == "system" and d["prefs"]["tex_engine"] == "system"
                assert d["reuse"]["sage"]["preference"] == "system"
                saved = json.loads((tmp_path / "config" / "settings.json").read_text())
                assert saved["sage_source"] == "system" and saved["tex_engine"] == "system"
                # a system Sage that is too old is refused even with a kernel
                setup_api._DETECTED["tools"] = {"sage": {"found": True, "version": "9.5", "compatible": False}}
                st, e = await _json(await s.post(local + "/api/setup/reuse", json={"sage_source": "system"}))
                assert st == 409 and e["reason"] == "system_sage_too_old"
                st, d = await _json(await s.post(local + "/api/setup/reuse", json={"sage_source": "own"}))
                assert st == 200 and ctx.settings.sage_source == "own"
    finally:
        config.publish_preferences(config.Settings())


FAKE_FETCH = r'''
import os, sys, time
d = os.environ["MADALEAN_MODELS_DIR"]
names = {"Q4_K_M": "Goedel-Prover-V2-8B.Q4_K_M.gguf", "formalizer": "Goedel-Formalizer-V2-8B.Q4_K_M.gguf",
         "explainer": "Qwen3-8B-Q4_K_M.gguf"}
for k in sys.argv[1:]:
    for i in (1, 2):
        print(f"{i}/2 segments  {i * 2.5:.2f}/5.00 GB  100.00 MB/s", flush=True)
        time.sleep(0.05)
    open(os.path.join(d, names[k]), "wb").write(b"gguf")
    print("OK", names[k], "1s", flush=True)
print("DL DONE", flush=True)
'''


async def test_local_model_download(tmp_path, monkeypatch):
    monkeypatch.setenv("MADALEAN_NO_NET", "1")
    models = tmp_path / "models"
    models.mkdir()
    (models / "Goedel-Prover-V2-8B.Q4_K_M.gguf").write_bytes(b"x" * 10)          # already there: reused
    monkeypatch.setattr(config, "MODELS_DIR", models)
    script = tmp_path / "fake_fetch.py"
    script.write_text(FAKE_FETCH)
    monkeypatch.setattr(setup_api, "fetch_argv", lambda keys: [sys.executable, str(script), *keys])
    setup_api._FETCH.clear()
    ctx = make_ctx(tmp_path)
    events: list[dict] = []
    orig = ctx.publish
    ctx.publish = lambda t, d: (events.append({"type": t, **d}) if t == "setup.models" else None, orig(t, d))[1]
    async with running(ctx) as (_srv, local, remote):
        async with aiohttp.ClientSession() as s:
            async with s.post(remote + "/api/setup/models", json={"models": "all"}) as r:
                assert r.status in (401, 403)
            async with s.post(local + "/api/setup/models", json={"models": "none"}) as r:
                assert r.status == 400
            ctx.settings.mode = "local"                                         # nothing leaves the machine
            st, e = await _json(await s.post(local + "/api/setup/models", json={"models": "all"}))
            assert st == 409 and e["error"] == "local_mode"
            ctx.settings.mode = "auto"
            st, d = await _json(await s.get(local + "/api/setup"))
            assert d["models"]["download_bytes"] == {"all": 10 ** 10, "prover": 0, "none": 0}
            st, d = await _json(await s.post(local + "/api/setup/models", json={"models": "prover"}))
            assert st == 200 and d["started"] is False                          # nothing missing
            st, d = await _json(await s.post(local + "/api/setup/models", json={"models": "all"}))
            assert st == 202 and d["started"] is True and d["models"]["fetch"]["keys"] == ["formalizer", "explainer"]
            st, e = await _json(await s.post(local + "/api/setup/models", json={"models": "all"}))
            assert st == 409 and e["error"] == "busy"
            for _ in range(200):
                if setup_api._FETCH.get("running") is False:
                    break
                await asyncio.sleep(0.05)
            assert setup_api._FETCH["phase"] == "done" and setup_api._FETCH["ok"] is True
            st, d = await _json(await s.get(local + "/api/setup"))
            assert all(f["present"] for f in d["models"]["files"]) and d["models"]["download_bytes"]["all"] == 0
    assert any(e["fetch"].get("total_gb") == 5.0 for e in events)                 # live progress
    assert events[-1]["fetch"]["phase"] == "done"
    setup_api._FETCH.clear()


async def test_model_download_refused_in_the_demo(tmp_path, monkeypatch):
    monkeypatch.setenv("MADALEAN_NO_NET", "1")
    monkeypatch.setattr(config, "MODELS_DIR", tmp_path / "models")
    setup_api._FETCH.clear()
    ctx = make_ctx(tmp_path)
    ctx.demo = True
    async with running(ctx) as (_srv, local, _remote):
        ctx.settings.mode = "auto"
        async with aiohttp.ClientSession() as s:
            st, e = await _json(await s.post(local + "/api/setup/models", json={"models": "prover"}))
            assert st == 409 and e["error"] == "demo"
            st, w = await _json(await s.get(local + "/api/setup/wizard"))
            assert w["auto"] is True                                            # the demo's examples do not count
