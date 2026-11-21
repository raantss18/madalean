"""Local llama-server manager with a FAKE llama-server executable (no GPU, no model): real child processes, health
polling, model swap per role, OOM fallback, never two servers, orphan cleanup through our own pid file only."""
from __future__ import annotations

import asyncio
import json
import os
import socket
import stat
import sys

import pytest

from madalean import config
from madalean.brain.api import BrainError
from madalean.runtime.llama import LocalLlama
from madalean.runtime.monitor import Monitor
from madalean.slots import CURRENT_JOB, Slots
from test_core import _gguf

FAKE = r'''#!PYTHON
import json, os, sys, http.server, threading
args = sys.argv[1:]
def arg(k): return args[args.index(k) + 1]
model, port, ctx, ngl = arg("-m"), int(arg("--port")), int(arg("-c")), int(arg("-ngl"))
with open(os.environ["FAKE_LOG"], "a") as f:
    f.write(json.dumps({"pid": os.getpid(), "model": os.path.basename(model), "ctx": ctx, "ngl": ngl}) + "\n")
if "oom" in model and ctx > 8192:
    print("ggml_cuda: cudaMalloc failed: out of memory", flush=True)
    sys.exit(1)
if "bad" in model:
    print("llama_model_load: error loading model: invalid magic", flush=True)
    sys.exit(1)
print(f"load_tensors: offloaded {ngl}/37 layers to GPU", flush=True)
class H(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_GET(self):
        self.send_response(200); self.end_headers(); self.wfile.write(b'{"status":"ok"}')
http.server.ThreadingHTTPServer(("127.0.0.1", port), H).serve_forever()
'''


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def setup(tmp_path, monkeypatch, names=("Goedel-Prover-V2-8B.Q4_K_M.gguf", "Goedel-Formalizer-V2-8B.Q4_K_M.gguf",
                                         "Qwen3-8B-Q4_K_M.gguf")):
    bindir, models = tmp_path / "bin", tmp_path / "models"
    bindir.mkdir()
    models.mkdir()
    exe = bindir / "llama-server"
    exe.write_text(FAKE.replace("PYTHON", sys.executable))
    exe.chmod(exe.stat().st_mode | stat.S_IEXEC)
    for n in names:
        _gguf(models / n)
    monkeypatch.setenv("FAKE_LOG", str(tmp_path / "launches.jsonl"))
    s = config.Settings()
    s.server.port = free_port()
    slots = Slots()
    mon = Monitor([])
    mon.gpu, mon.gpu_ok = {"name": "fake", "total": 8188, "used": 100, "free": 8088, "temp": 40, "util": 0,
                           "apps": {}}, True
    rt = LocalLlama(slots, mon, tmp_path / "llama-server.pid", lambda: s, models_dir=models, bin_dir=bindir,
                    load_timeout=30)
    return rt, slots, tmp_path / "launches.jsonl"


def launches(log):
    return [json.loads(x) for x in log.read_text().splitlines()] if log.exists() else []


def alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return not open(f"/proc/{pid}/stat").read().split()[2] == "Z"
    except (OSError, ProcessLookupError):
        return False


async def test_swap_per_role_and_single_server(tmp_path, monkeypatch):
    rt, slots, log = setup(tmp_path, monkeypatch)
    await rt.refresh_models()
    CURRENT_JOB.set("job-a")
    url = await rt.ensure("prove")
    assert url.endswith("/v1") and rt.state == "ready" and rt.model_path.name.startswith("Goedel-Prover")
    assert slots.holders["gpu"] == ["job-a"] and rt.offload == "99/37"
    assert await rt.ensure("prove") == url and rt.loads == 1                  # same model: no reload, reentrant
    first = rt.last_pid
    await rt.ensure("formalize")                                               # swap: the prover is stopped first
    assert rt.loads == 2 and rt.model_path.name.startswith("Goedel-Formalizer") and not alive(first)
    rt.release()
    assert slots.holders["gpu"] == []
    assert (tmp_path / "llama-server.pid").read_text().split()[0] == str(rt.last_pid)
    await rt.stop()
    assert not alive(rt.last_pid) and not (tmp_path / "llama-server.pid").exists()
    assert [x["model"][:14] for x in launches(log)] == ["Goedel-Prover-", "Goedel-Formali"]


async def test_gpu_slot_waits_for_the_other_job(tmp_path, monkeypatch):
    rt, slots, log = setup(tmp_path, monkeypatch)
    await rt.refresh_models()
    order = []

    async def job(name, role, hold):
        CURRENT_JOB.set(name)
        await rt.ensure(role)
        order.append((name, "in"))
        await asyncio.sleep(hold)
        order.append((name, "out"))
        rt.release()
    await asyncio.gather(job("a", "prove", 0.3), job("b", "explain", 0.0))
    assert order == [("a", "in"), ("a", "out"), ("b", "in"), ("b", "out")]
    assert slots.max_seen["gpu"] == 1
    await rt.stop()


async def test_oom_fallback_then_success(tmp_path, monkeypatch):
    rt, slots, log = setup(tmp_path, monkeypatch, names=("Goedel-Prover-V2-8B-oom.Q4_K_M.gguf",))
    await rt.refresh_models()
    CURRENT_JOB.set("j")
    await rt.ensure("prove")
    ctxs = [x["ctx"] for x in launches(log)]
    assert ctxs == [24576, 12288, 8192] and rt.state == "ready"
    assert any("contexte" in n for n in rt.notes)
    rt.release()
    await rt.stop()


async def test_bad_model_and_missing_binary_raise_and_release(tmp_path, monkeypatch):
    rt, slots, log = setup(tmp_path, monkeypatch, names=("Goedel-Prover-V2-8B-bad.Q4_K_M.gguf",))
    await rt.refresh_models()
    CURRENT_JOB.set("j")
    with pytest.raises(BrainError):
        await rt.ensure("prove")
    assert rt.last_error["kind"] == "bad_model" and slots.holders["gpu"] == []
    assert await rt.ensure("formalize") is None                                # no formalizer installed
    (tmp_path / "bin" / "llama-server").unlink()
    with pytest.raises(BrainError):
        await rt.ensure("prove")
    assert rt.last_error["kind"] == "no_binary" and slots.holders["gpu"] == []


async def test_orphan_from_our_pid_file_is_killed_but_nothing_else(tmp_path, monkeypatch):
    rt, slots, log = setup(tmp_path, monkeypatch)
    await rt.refresh_models()
    CURRENT_JOB.set("j")
    await rt.ensure("prove")
    orphan = rt.proc
    rt.proc = None                       # forget it, as after a crash of the server
    rt.state = "stopped"
    other = await asyncio.create_subprocess_exec("sleep", "30")
    (tmp_path / "unrelated.pid").write_text(str(other.pid))
    await rt.ensure("explain")           # new launch: the orphan named in OUR pid file is killed first
    await asyncio.wait_for(orphan.wait(), 5)
    assert orphan.returncode is not None and alive(other.pid)
    other.kill()
    await other.wait()
    rt.release()
    await rt.stop()
