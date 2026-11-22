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
    monkeypatch.setattr(llama.ollama_share, "runner_pids", lambda: [])   # never this machine's real Ollama runners
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


# ---------------------------------------------------------------- S-AS (D51): never evict Ollama mid-generation
def busy_ollama(monkeypatch, states):
    """Ollama's activity as a sequence of busy flags (the last one repeats)."""
    seq = list(states)

    async def activity(base, util, sample=0.5):
        b = seq.pop(0) if len(seq) > 1 else seq[0]
        return {"reachable": True, "models": [{"name": "deepseek-r1:8b", "vram_mib": 4918}], "busy": b,
                "t": 0, "signals": {"runner_cpu_pct": 100 if b else 0}}
    monkeypatch.setattr(llama.ollama_share, "activity", activity)


async def test_waits_while_ollama_answers_then_lends(tmp_path, monkeypatch, ollama):
    monkeypatch.setattr(llama, "fitantanana_exe", lambda: None)
    rt, slots, log = setup(tmp_path, monkeypatch)
    rt.busy_poll = 0.01
    monkeypatch.setattr(llama, "full_gpu_need_mib", lambda m, s: 6000)
    short_gpu(rt, monkeypatch)
    busy_ollama(monkeypatch, [True, True, False])
    await rt.refresh_models()
    CURRENT_JOB.set("job-a")
    await rt.ensure("prove")
    assert [p[1]["model"] for p in ollama.posts] == ["deepseek-r1:8b", "nomic-embed-text:latest"]   # after it finished
    assert any("attend qu'il ait fini" in n for n in rt.notes) and rt.last_lend["ok"]
    rt.release()
    await rt.stop()


async def test_still_busy_cpu_fallback_never_unloads(tmp_path, monkeypatch, ollama):
    monkeypatch.setattr(llama, "fitantanana_exe", lambda: None)
    rt, slots, log = setup(tmp_path, monkeypatch)
    rt.busy_poll = 0.01
    rt.get_settings().gpu_share_busy_wait_s = 0
    monkeypatch.setattr(llama, "full_gpu_need_mib", lambda m, s: 6000)
    short_gpu(rt, monkeypatch)
    busy_ollama(monkeypatch, [True])
    await rt.refresh_models()
    CURRENT_JOB.set("job-a")
    await rt.ensure("prove")
    assert ollama.posts == [] and rt.last_lend["reason"] == "ollama_busy"
    assert any("ne l'interrompt pas" in n for n in rt.notes)
    assert rt.share_status()["ollama"]["busy"] and rt.share_status()["last_lend"]["reason"] == "ollama_busy"
    rt.release()
    await rt.stop()


async def test_still_busy_online_fallback_hands_over(tmp_path, monkeypatch, ollama):
    from madalean.brain.providers.base import ProviderError
    monkeypatch.setattr(llama, "fitantanana_exe", lambda: None)
    rt, slots, log = setup(tmp_path, monkeypatch)
    rt.busy_poll = 0.01
    rt.get_settings().gpu_share_busy_wait_s = 0
    rt.get_settings().gpu_share_busy_fallback = "online"
    monkeypatch.setattr(llama, "full_gpu_need_mib", lambda m, s: 6000)
    short_gpu(rt, monkeypatch)
    busy_ollama(monkeypatch, [True])
    await rt.refresh_models()
    CURRENT_JOB.set("job-a")
    with pytest.raises(ProviderError) as e:
        await rt.ensure("prove")
    assert e.value.kind == "unavailable" and ollama.posts == [] and launches(log) == []
    assert slots.holders["gpu"] == []                            # the GPU slot is given back for the next model


async def test_sharing_disabled_never_touches_ollama(tmp_path, monkeypatch, ollama):
    monkeypatch.setattr(llama, "fitantanana_exe", lambda: None)
    rt, slots, log = setup(tmp_path, monkeypatch)
    rt.get_settings().gpu_share_ollama = False
    monkeypatch.setattr(llama, "full_gpu_need_mib", lambda m, s: 6000)
    short_gpu(rt, monkeypatch)
    await rt.refresh_models()
    CURRENT_JOB.set("job-a")
    await rt.ensure("prove")
    assert ollama.posts == [] and rt.last_lend["reason"] == "disabled" and not rt.share_status()["enabled"]
    rt.release()
    await rt.stop()


async def test_activity_reads_fake_ollama(ollama, monkeypatch):
    from madalean.runtime import ollama_share
    monkeypatch.setattr(ollama_share, "runner_pids", lambda: [])
    a = await ollama_share.activity(ollama.url, 0, sample=0.01)
    assert a["reachable"] and not a["busy"] and a["models"][0] == {"name": "deepseek-r1:8b", "vram_mib": 4918}
    down = await ollama_share.activity("http://127.0.0.1:9", 0, sample=0.01)
    assert not down["reachable"] and not down["busy"] and down["models"] == []


async def test_activity_busy_signals(ollama, monkeypatch):
    """Measured signals (bench/gpu_share_ollama.json): the runner spins a core while the GPU computes."""
    from madalean.runtime import ollama_share
    ticks = iter([0, 50, 0, 1, 0, 1])
    monkeypatch.setattr(ollama_share, "runner_pids", lambda: [4242])
    monkeypatch.setattr(ollama_share, "cpu_ticks", lambda pids: next(ticks))
    monkeypatch.setattr(ollama_share.os, "sysconf", lambda k: 100)
    monkeypatch.setattr(ollama_share, "foreign_connections", lambda port: 0)
    assert (await ollama_share.activity(ollama.url, 94, sample=0.5))["busy"]          # 100 % CPU
    assert not (await ollama_share.activity(ollama.url, 94, sample=0.5))["busy"]      # idle runner, no client
    monkeypatch.setattr(ollama_share, "foreign_connections", lambda port: 1)
    assert (await ollama_share.activity(ollama.url, 94, sample=0.5))["busy"]          # a client + GPU computing


def test_foreign_connections_skip_our_own(tmp_path):
    from madalean.runtime import ollama_share
    hdr = "  sl  local_address rem_address   st tx_queue rx_queue tr tm->when retrnsmt   uid  timeout inode\n"
    row = "   0: {l} {r} {st} 00000000:00000000 00:00000000 00000000  1000        0 {ino} 1\n"
    (tmp_path / "tcp").write_text(hdr + "".join(row.format(l=a, r=b, st=st, ino=i) for a, b, st, i in [
        ("0100007F:2CAA", "0100007F:A000", "01", "11"),     # Ollama's side of OUR connection
        ("0100007F:A000", "0100007F:2CAA", "01", "99"),     # our side (inode 99 is ours)
        ("0100007F:2CAA", "0100007F:B000", "01", "12"),     # another client (Sampana's bridge)
        ("0100007F:2CAA", "00000000:0000", "0A", "13"),     # the listening socket
        ("0100007F:2CAA", "0100007F:C000", "06", "14")]))   # TIME_WAIT
    assert ollama_share.foreign_connections(11434, tmp_path, own={"99"}) == 1
    assert ollama_share.foreign_connections(11434, tmp_path, own=set()) == 2


def test_runner_pids(tmp_path):
    from madalean.runtime import ollama_share
    for pid, argv in ((10, [b"/usr/local/bin/ollama", b"serve"]),
                      (11, [b"/usr/local/bin/ollama", b"runner", b"--model", b"x"]),
                      (12, [b"/usr/bin/socat", b"ollama", b"runner"])):
        (tmp_path / str(pid)).mkdir()
        (tmp_path / str(pid) / "cmdline").write_bytes(b"\0".join(argv) + b"\0")
    assert ollama_share.runner_pids(tmp_path) == [11]
