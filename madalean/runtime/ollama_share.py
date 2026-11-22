"""Is Ollama answering someone right now? (S-AS, DECISIONS D51)

Madalean borrows the GPU from Ollama (`llama.lend_gpu`, keep_alive 0) only when Ollama is idle: a model Ollama is
generating with belongs to another application (Sampana's guest through its socat bridge, mi-saina, L Katta…). Ollama
itself never cuts a generation on `keep_alive: 0` — it unloads when the request ends (measured, bench/gpu_share_*.json)
— so evicting "mid-generation" would mean waiting for an unknown time with the GPU slot held. We look first.

Signals, measured on the RTX 4060 with phi4-mini (idle loaded → generating): Ollama runner CPU 0 % → ~100 % (the
runner spins one core while the GPU computes), GPU utilisation 0 → 94 %, established connections to :11434 0 → 1.
`/api/ps` shows no difference (same `expires_at` while generating). Busy = runner CPU ≥ 25 %, or a connection from
another process while the GPU is computing (≥ 30 %). Connections opened by Madalean itself (Ollama models, embeddings)
are not counted. Only the local Ollama is examined (/proc); a remote Ollama has another GPU anyway."""
from __future__ import annotations

import asyncio
import os
import time
from pathlib import Path
from urllib.parse import urlsplit

import aiohttp

BUSY_CPU_PCT = 25.0
BUSY_GPU_UTIL = 30.0


def runner_pids(proc: Path = Path("/proc")) -> list[int]:
    """Ollama's model runners (`ollama runner …`): one process per loaded model."""
    out = []
    for d in proc.iterdir() if proc.is_dir() else []:
        if not d.name.isdigit():
            continue
        try:
            argv = (d / "cmdline").read_bytes().split(b"\0")
        except OSError:
            continue
        if "ollama" in Path(argv[0].decode("utf-8", "replace")).name and b"runner" in argv[1:3]:
            out.append(int(d.name))
    return out


def cpu_ticks(pids: list[int], proc: Path = Path("/proc")) -> int:
    tot = 0
    for pid in pids:
        try:
            s = (proc / str(pid) / "stat").read_text().rsplit(")", 1)[1].split()
            tot += int(s[11]) + int(s[12])
        except (OSError, IndexError, ValueError):
            continue
    return tot


def _own_socket_inodes() -> set[str]:
    out = set()
    try:
        for fd in os.listdir("/proc/self/fd"):
            try:
                t = os.readlink(f"/proc/self/fd/{fd}")
            except OSError:
                continue
            if t.startswith("socket:["):
                out.add(t[8:-1])
    except OSError:
        pass
    return out


def _tcp_rows(proc_net: Path) -> list[tuple[str, str, str, str]]:
    rows = []
    for f in ("tcp", "tcp6"):
        try:
            lines = (proc_net / f).read_text().splitlines()[1:]
        except OSError:
            continue
        for line in lines:
            p = line.split()
            if len(p) > 9:
                rows.append((p[1], p[2], p[3], p[9]))      # local, remote, state, inode
    return rows


def foreign_connections(port: int, proc_net: Path = Path("/proc/net"), own: set[str] | None = None) -> int:
    """Established connections to Ollama's port from processes other than this one."""
    own = _own_socket_inodes() if own is None else own
    hexport = f":{port:04X}"
    rows = _tcp_rows(proc_net)
    mine = {loc.rsplit(":", 1)[1] for loc, rem, st, ino in rows if st == "01" and rem.endswith(hexport) and ino in own}
    return sum(1 for loc, rem, st, _ino in rows
               if st == "01" and loc.endswith(hexport) and rem.rsplit(":", 1)[1] not in mine)


def _is_local(base: str) -> bool:
    return (urlsplit(base).hostname or "") in ("127.0.0.1", "localhost", "::1")


async def loaded_models(base: str, timeout: float = 2.0) -> list[dict] | None:
    """`GET /api/ps` → [{name, vram_mib}], None when Ollama does not answer."""
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=timeout)) as http:
            async with http.get(base + "/api/ps") as r:
                if r.status != 200:
                    return None
                ms = (await r.json(content_type=None)).get("models") or []
    except (aiohttp.ClientError, asyncio.TimeoutError, OSError, ValueError):
        return None
    return [{"name": m.get("name", "?"), "vram_mib": int((m.get("size_vram") or 0) / 2**20)} for m in ms]


async def activity(base: str, gpu_util: float | None = None, sample: float = 0.5) -> dict:
    """{reachable, models, busy, signals}. Never raises."""
    models = await loaded_models(base)
    out: dict = {"reachable": models is not None, "models": models or [], "busy": False, "t": time.time(),
                 "signals": {}}
    if models is None or not _is_local(base):
        return out
    pids = runner_pids()
    t0 = cpu_ticks(pids)
    await asyncio.sleep(sample)
    cpu = (cpu_ticks(pids) - t0) / (os.sysconf("SC_CLK_TCK") or 100) / sample * 100 if pids else 0.0
    port = urlsplit(base).port or 11434
    conns = await asyncio.to_thread(foreign_connections, port)
    util = float(gpu_util or 0)
    out["signals"] = {"runner_cpu_pct": round(cpu), "connections": conns, "gpu_util": util, "runners": len(pids)}
    out["busy"] = bool(pids) and (cpu >= BUSY_CPU_PCT or (conns > 0 and util >= BUSY_GPU_UTIL))
    return out
