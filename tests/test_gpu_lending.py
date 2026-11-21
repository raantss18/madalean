"""GPU lending with Ollama (S-N): before loading a model that does not fit, Madalean asks Ollama to unload its
models — through `fitantanana gpu lend` when installed, else with Ollama's documented API directly — then plans the
offload with the freed memory; after `local_idle_unload_minutes` without use it stops llama-server (GPU given back).
Fake Ollama API, fake llama-server, fake fitantanana: no GPU needed."""
from __future__ import annotations

import asyncio
import json
import stat
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from madalean.runtime import llama
from madalean.slots import CURRENT_JOB
from test_llama import launches, setup


class FakeOllama:
    def __init__(self, models):
        self.models, self.posts = list(models), []
        fake = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _send(self, obj):
                b = json.dumps(obj).encode()
                self.send_response(200)
                self.send_header("Content-Length", str(len(b)))
                self.end_headers()
                self.wfile.write(b)

            def do_GET(self):
                self._send({"models": fake.models} if self.path == "/api/ps" else {})

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                fake.posts.append((self.path, body))
                if body.get("keep_alive") == 0:
                    fake.models = [m for m in fake.models if m["name"] != body["model"]]
                self._send({"done": True, "done_reason": "unload"})
        self.srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.url = f"http://127.0.0.1:{self.srv.server_address[1]}"
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    def close(self):
        self.srv.shutdown()
        self.srv.server_close()


@pytest.fixture
def ollama(monkeypatch):
    o = FakeOllama([{"name": "deepseek-r1:8b", "size_vram": 4918 * 2**20},
                    {"name": "nomic-embed-text:latest", "size_vram": 567 * 2**20},
                    {"name": "on-cpu", "size_vram": 0}])
    monkeypatch.setenv("OLLAMA_HOST", o.url)
    yield o
    o.close()


def short_gpu(rt, monkeypatch, free_after=7900):
    """GPU nearly full (Ollama holds it); after lending, the next monitor poll sees the memory freed."""
    rt.monitor.gpu.update({"used": 7888, "free": 300, "apps": {424242: 5400}})
    monkeypatch.setattr(rt, "_ollama_holds_gpu", lambda: True)

    async def poll():
        rt.monitor.gpu.update({"used": rt.monitor.gpu["total"] - free_after, "free": free_after, "apps": {}})
    monkeypatch.setattr(rt.monitor, "poll", poll)


async def test_builtin_lending_unloads_ollama_then_full_offload(tmp_path, monkeypatch, ollama):
    monkeypatch.setattr(llama, "fitantanana_exe", lambda: None)
    rt, slots, log = setup(tmp_path, monkeypatch)
    monkeypatch.setattr(llama, "full_gpu_need_mib", lambda m, s: 6000)
    short_gpu(rt, monkeypatch)
    await rt.refresh_models()
    CURRENT_JOB.set("job-a")
    await rt.ensure("prove")
    # only the documented unload request, largest model first, never the CPU-only one
    assert ollama.posts == [("/api/generate", {"model": "deepseek-r1:8b", "keep_alive": 0, "stream": False}),
                            ("/api/generate", {"model": "nomic-embed-text:latest", "keep_alive": 0, "stream": False})]
    assert rt.last_lend["via"] == "builtin" and rt.last_lend["ok"]
    assert launches(log)[-1]["ngl"] == 99                      # planned with the freed memory: all on GPU
    assert any("Ollama" in n for n in rt.notes)
    rt.release()
    await rt.stop()


async def test_fitantanana_is_preferred(tmp_path, monkeypatch, ollama):
    calls = tmp_path / "calls.jsonl"
    exe = tmp_path / "fitantanana"
    exe.write_text(f"#!{sys.executable}\nimport json, sys\nopen({str(calls)!r}, 'a').write(json.dumps(sys.argv[1:]) + '\\n')\n"
                   "print(json.dumps({'ok': True, 'reason': 'freed', 'unloaded': ['deepseek-r1:8b'], "
                   "'free_before': 300, 'free_after': 7900, 'need_mib': 6000}))\n")
    exe.chmod(exe.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("MADALEAN_FITANTANANA", str(exe))
    rt, slots, log = setup(tmp_path, monkeypatch)
    monkeypatch.setattr(llama, "full_gpu_need_mib", lambda m, s: 6000)
    short_gpu(rt, monkeypatch)
    await rt.refresh_models()
    CURRENT_JOB.set("job-a")
    await rt.ensure("prove")
    argv = json.loads(calls.read_text().splitlines()[0])
    assert argv[:6] == ["gpu", "lend", "--to", "madalean", "--need", "6000"] and "--json" in argv
    assert rt.last_lend["via"] == "fitantanana" and ollama.posts == []     # the tool did it, not us
    rt.release()
    await rt.stop()


async def test_no_lending_when_it_fits_or_ollama_absent(tmp_path, monkeypatch, ollama):
    monkeypatch.setattr(llama, "fitantanana_exe", lambda: None)
    rt, slots, log = setup(tmp_path, monkeypatch)
    await rt.refresh_models()
    CURRENT_JOB.set("job-a")
    await rt.ensure("prove")                                   # 8088 MiB free: fits
    assert ollama.posts == [] and rt.last_lend is None
    await rt.stop()
    rt.monitor.gpu.update({"free": 300, "apps": {}})            # short, but Ollama holds nothing
    monkeypatch.setattr(llama, "full_gpu_need_mib", lambda m, s: 6000)
    await rt.ensure("formalize")
    assert ollama.posts == [] and rt.last_lend is None
    rt.release()
    await rt.stop()


async def test_ollama_unreachable_still_loads(tmp_path, monkeypatch):
    monkeypatch.setattr(llama, "fitantanana_exe", lambda: None)
    monkeypatch.setenv("OLLAMA_HOST", "127.0.0.1:9")
    rt, slots, log = setup(tmp_path, monkeypatch)
    monkeypatch.setattr(llama, "full_gpu_need_mib", lambda m, s: 6000)
    short_gpu(rt, monkeypatch, free_after=300)
    await rt.refresh_models()
    CURRENT_JOB.set("job-a")
    await rt.ensure("prove")
    assert rt.state == "ready" and rt.last_lend["reason"] == "ollama_unreachable"
    rt.release()
    await rt.stop()


async def test_idle_unload_gives_gpu_back(tmp_path, monkeypatch):
    calls = tmp_path / "calls.jsonl"
    exe = tmp_path / "fitantanana"
    exe.write_text(f"#!{sys.executable}\nimport json, sys\nopen({str(calls)!r}, 'a').write(json.dumps(sys.argv[1:]) + '\\n')\n"
                   "print('{}')\n")
    exe.chmod(exe.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("MADALEAN_FITANTANANA", str(exe))
    rt, slots, log = setup(tmp_path, monkeypatch)
    rt.idle_poll = 0.05
    await rt.refresh_models()
    CURRENT_JOB.set("job-a")
    await rt.ensure("prove")
    await asyncio.sleep(0.2)
    assert rt.state == "ready"                                  # held by a job: never unloaded
    rt.release()
    rt.get_settings().local_idle_unload_minutes = 1
    rt.last_used -= 30
    await asyncio.sleep(0.2)
    assert rt.state == "ready"                                  # idle 30 s < 1 min
    rt.last_used -= 60
    for _i in range(40):
        if rt.state == "stopped":
            break
        await asyncio.sleep(0.05)
    assert rt.state == "stopped" and rt.proc is None
    await asyncio.sleep(0.3)
    assert ["gpu", "return", "--from", "madalean", "--json"] in [json.loads(x) for x in calls.read_text().splitlines()]
    assert any("min sans utilisation" in n for n in rt.notes)


async def test_idle_unload_disabled(tmp_path, monkeypatch):
    monkeypatch.setattr(llama, "fitantanana_exe", lambda: None)
    rt, slots, log = setup(tmp_path, monkeypatch)
    rt.idle_poll = 0.05
    rt.get_settings().local_idle_unload_minutes = 0
    await rt.refresh_models()
    CURRENT_JOB.set("job-a")
    await rt.ensure("prove")
    rt.release()
    rt.last_used -= 10**6
    await asyncio.sleep(0.3)
    assert rt.state == "ready"
    await rt.stop()


def test_gpu_share_names_holders(monkeypatch):
    cmd = {1: "/usr/local/bin/ollama runner --model x", 2: "/usr/bin/kwin_wayland", 3: "/x/llama-server -m y"}
    monkeypatch.setattr(llama, "_proc_cmdline", lambda pid: cmd.get(pid, ""))
    sh = llama.gpu_share({"free": 2362, "total": 8188, "apps": {"1": 4780, 2: 11, 3: 100}}, None)
    assert sh["holders"] == [{"app": "Ollama", "mib": 4780}, {"app": "Madalean", "mib": 100},
                             {"app": "kwin_wayland", "mib": 11}]
    assert llama.gpu_share(None, None) is None
