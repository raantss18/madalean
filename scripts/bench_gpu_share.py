#!/usr/bin/env python3
"""GPU sharing bench (S-AS, D51): Ollama vs Madalean's llama-server on this GPU, and the lending sequence.

Never stops Ollama: models are unloaded with Ollama's documented request (`keep_alive: 0`). Uses only models already
present (an Ollama model's blob is a GGUF that llama-server can read in place; Goedel from ~/models). Prints JSON.

    scripts/bench_gpu_share.py [ollama] [llama] [lend]      # default: all three
"""
import glob
import json
import os
import subprocess
import sys
import threading
import time
import urllib.request

O = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
BIN = os.path.expanduser(os.environ.get("MADALEAN_LLAMA_BIN", "~/.local/share/madalean/components/llama.cpp/current"))
SMALL = os.environ.get("BENCH_SMALL_MODEL", "phi4-mini:latest")
BIG = os.environ.get("BENCH_BIG_MODEL", "qwen3.5:9b")
GOEDEL = os.path.expanduser(os.environ.get("BENCH_GGUF", "~/models/Goedel-Prover-V2-8B.Q4_K_M.gguf"))
R: dict = {}


def smi() -> dict:
    o = subprocess.run(["nvidia-smi", "--query-gpu=memory.used,memory.free,utilization.gpu",
                        "--format=csv,noheader,nounits"], capture_output=True, text=True).stdout.strip().split(",")
    return {"used": float(o[0]), "free": float(o[1]), "util": float(o[2])}


def req(path, body=None, base=O, timeout=600):
    r = urllib.request.Request(base + path, data=json.dumps(body).encode() if body is not None else None,
                               headers={"Content-Type": "application/json"})
    return urllib.request.urlopen(r, timeout=timeout)


def ps() -> list:
    return json.load(req("/api/ps"))["models"]


def blob_of(name: str) -> str:
    repo, _, tag = name.partition(":")
    m = os.path.expanduser(f"~/.ollama/models/manifests/registry.ollama.ai/library/{repo}/{tag or 'latest'}")
    d = json.load(open(m))
    dig = next(lay["digest"] for lay in d["layers"] if lay["mediaType"].endswith(".model"))
    return os.path.expanduser("~/.ollama/models/blobs/" + dig.replace(":", "-"))


def unload_all() -> float:
    t0 = time.time()
    for m in ps():
        req("/api/generate", {"model": m["name"], "keep_alive": 0}).read()
    while ps() and time.time() - t0 < 60:
        time.sleep(0.1)
    return round(time.time() - t0, 2)


def wait_free(min_free: float, t: float = 30) -> float:
    t0 = time.time()
    while smi()["free"] < min_free and time.time() - t0 < t:
        time.sleep(0.1)
    return round(time.time() - t0, 2)


def ollama_gen(model, prompt, n=32, keep="5m") -> dict:
    t0, first = time.time(), None
    with req("/api/generate", {"model": model, "prompt": prompt, "stream": True, "keep_alive": keep,
                               "options": {"num_predict": n, "temperature": 0}}) as r:
        for line in r:
            d = json.loads(line)
            if d.get("response") and first is None:
                first = time.time() - t0
            if d.get("done"):
                return {"first_token_s": round(first or -1, 2), "total_s": round(time.time() - t0, 2),
                        "load_s": round(d.get("load_duration", 0) / 1e9, 2), "tokens": d.get("eval_count"),
                        "eval_tok_s": round(d.get("eval_count", 0) / max(d.get("eval_duration", 1) / 1e9, 1e-9), 1)}
    return {}


def tcp_established(port=11434) -> int:
    n, hexport = 0, f":{port:04X}"
    for f in ("/proc/net/tcp", "/proc/net/tcp6"):
        for line in open(f).read().splitlines()[1:]:
            p = line.split()
            if p[3] == "01" and p[1].endswith(hexport):
                n += 1
    return n


def runner_ticks() -> int:
    tot = 0
    for d in glob.glob("/proc/[0-9]*"):
        try:
            cmd = open(d + "/cmdline", "rb").read()
            if b"ollama" in cmd and b"runner" in cmd:
                s = open(d + "/stat").read().rsplit(")", 1)[1].split()
                tot += int(s[11]) + int(s[12])
        except OSError:
            pass
    return tot


def signals() -> dict:
    c0 = runner_ticks()
    time.sleep(0.5)
    c1 = runner_ticks()
    return {"tcp_established_11434": tcp_established(), "gpu_util": smi()["util"],
            "runner_cpu_pct": round((c1 - c0) / os.sysconf("SC_CLK_TCK") / 0.5 * 100),
            "ps": [(m["name"], m.get("expires_at")) for m in ps()]}


def llama_server(model, ctx, port=8799) -> dict:
    env = dict(os.environ, LD_LIBRARY_PATH=BIN)
    args = [BIN + "/llama-server", "-m", model, "--host", "127.0.0.1", "--port", str(port), "-ngl", "99", "-c", str(ctx),
            "-b", "2048", "-ub", "512", "-fa", "on", "-ctk", "q8_0", "-ctv", "q8_0", "-t", "8", "-np", "1", "--jinja",
            "--no-webui", "--fit", "off", "-cram", "1024"]
    free0 = smi()["free"]
    t0 = time.time()
    p = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env)
    base = f"http://127.0.0.1:{port}"
    try:
        while True:
            try:
                if urllib.request.urlopen(base + "/health", timeout=1).status == 200:
                    break
            except Exception:  # noqa: BLE001
                pass
            if p.poll() is not None:
                return {"error": "exited"}
            time.sleep(0.1)
        load = time.time() - t0
        vram = free0 - smi()["free"]
        t1, first = time.time(), None
        with req("/v1/chat/completions", {"messages": [{"role": "user", "content": "Say hello in five words."}],
                                          "max_tokens": 32, "temperature": 0, "stream": True}, base=base) as r:
            for line in r:
                if line.startswith(b"data:") and b'"content":"' in line and first is None:
                    first = time.time() - t1
        total = time.time() - t1
    finally:
        p.terminate()
        p.wait()
    t2 = time.time()
    wait_free(free0 - 200)
    return {"load_s": round(load, 2), "vram_mib": vram, "first_token_s": round(first or -1, 2),
            "total_32tok_s": round(total, 2), "release_s": round(time.time() - t2, 2)}


def main(what):
    R["baseline"] = smi()
    R["initial_unload_s"] = unload_all()
    if "ollama" in what:
        f0 = smi()["free"]
        R["ollama_small_cold"] = ollama_gen(SMALL, "Say hello in five words.")
        R["ollama_small_vram_api_mib"] = [round(m["size_vram"] / 2**20) for m in ps()]
        R["ollama_small_vram_smi_mib"] = f0 - smi()["free"]
        R["ollama_small_warm"] = ollama_gen(SMALL, "Say hello in five words.")
        R["signals_loaded_idle"] = signals()
        th = threading.Thread(target=lambda: R.__setitem__(
            "ollama_long", ollama_gen(SMALL, "Count from 1 to 400, one number per line.", n=600)))
        th.start()
        time.sleep(1.5)
        R["signals_generating"] = [signals() for _ in range(2)]
        t0 = time.time()
        req("/api/generate", {"model": SMALL, "keep_alive": 0}).read()
        R["unload_request_while_generating_returns_s"] = round(time.time() - t0, 2)
        th.join()
        R["long_generation_result"] = R.pop("ollama_long", None)
        t0 = time.time()
        while ps() and time.time() - t0 < 30:
            time.sleep(0.1)
        R["unloaded_after_generation_end_s"] = round(time.time() - t0, 2)
        R["unload_to_vram_free_s"] = wait_free(f0 - 200)
        R["signals_unloaded"] = signals()
    if "llama" in what:
        R["llama_small_blob_ctx8192"] = llama_server(blob_of(SMALL), 8192)
        R["llama_goedel_q4_ctx24576"] = llama_server(GOEDEL, 24576)
    if "lend" in what:
        f0 = smi()["free"]
        R["ollama_big_cold"] = ollama_gen(BIG, "Say hello.", n=8)
        R["ollama_big_vram_smi_mib"] = f0 - smi()["free"]
        R["ollama_big_vram_api_mib"] = [round(m["size_vram"] / 2**20) for m in ps()]
        t0 = time.time()
        unload_all()
        wait_free(f0 - 200)
        R["lend_big_unload_to_free_s"] = round(time.time() - t0, 2)
        R["llama_goedel_after_lend"] = llama_server(GOEDEL, 24576)
        R["ollama_big_reload_after_return"] = ollama_gen(BIG, "Say hello.", n=8, keep=0)
        wait_free(f0 - 200)
    R["end"] = smi()
    print(json.dumps(R, indent=1))


if __name__ == "__main__":
    main(sys.argv[1:] or ["ollama", "llama", "lend"])
