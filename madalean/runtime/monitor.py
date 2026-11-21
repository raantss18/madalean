"""GPU (nvidia-smi) and disk monitor, polled without blocking the event loop."""
from __future__ import annotations

import asyncio
import shutil
import time
from pathlib import Path
from typing import Callable

from ..logs import get

log = get("monitor")


async def _run(*args: str, timeout: float = 8.0) -> str | None:
    try:
        p = await asyncio.create_subprocess_exec(*args, stdout=asyncio.subprocess.PIPE,
                                                 stderr=asyncio.subprocess.DEVNULL)
        out, _e = await asyncio.wait_for(p.communicate(), timeout)
        return out.decode(errors="replace") if p.returncode == 0 else None
    except (OSError, asyncio.TimeoutError):
        return None


def parse_gpu(out: str, apps_out: str | None) -> dict | None:
    try:
        name, total, used, temp, util = [x.strip() for x in out.strip().splitlines()[0].split(",")]
        d = {"name": name, "total": int(total), "used": int(used), "free": int(total) - int(used),
             "temp": int(temp), "util": int(util), "apps": {}}
    except (ValueError, IndexError):
        return None
    for line in (apps_out or "").splitlines():
        try:
            pid, mem = [int(x.strip()) for x in line.split(",")[:2]]
            d["apps"][pid] = d["apps"].get(pid, 0) + mem
        except ValueError:
            continue
    return d


class Monitor:
    def __init__(self, disk_paths: list[Path], interval: float = 3.0):
        self.disk_paths = disk_paths
        self.interval = interval
        self.gpu: dict | None = None
        self.gpu_ok: bool | None = None      # None until the first poll answered (D9: never plan without it)
        self.gpu_error = ""
        self.disk: list[dict] = []
        self.t = 0.0
        self.listeners: list[Callable[[dict], None]] = []
        self._task: asyncio.Task | None = None
        self._first = asyncio.Event()

    def snapshot(self) -> dict:
        gpu = dict(self.gpu) if self.gpu else None
        if gpu:
            gpu["apps"] = {str(k): v for k, v in gpu["apps"].items()}
        return {"gpu": gpu, "gpu_ok": self.gpu_ok, "gpu_error": self.gpu_error, "disk": self.disk, "t": self.t}

    async def poll(self) -> None:
        exe = shutil.which("nvidia-smi")
        if not exe:
            self.gpu, self.gpu_ok, self.gpu_error = None, False, "nvidia-smi not found"
        else:
            out = await _run(exe, "--query-gpu=name,memory.total,memory.used,temperature.gpu,utilization.gpu",
                             "--format=csv,noheader,nounits")
            apps = await _run(exe, "--query-compute-apps=pid,used_memory", "--format=csv,noheader,nounits") if out else None
            d = parse_gpu(out or "", apps)
            self.gpu, self.gpu_ok, self.gpu_error = d, d is not None, "" if d else (out or "nvidia-smi failed")[:200]
        self.disk = await asyncio.to_thread(self._disk)
        self.t = time.time()
        self._first.set()
        for cb in list(self.listeners):
            try:
                cb(self.snapshot())
            except Exception:  # noqa: BLE001
                log.exception("monitor listener failed")

    def _disk(self) -> list[dict]:
        out, seen = [], set()
        for p in self.disk_paths:
            q = p if p.exists() else Path.home()
            try:
                u = shutil.disk_usage(q)
            except OSError:
                continue
            key = (u.total, u.free)
            if key in seen:
                continue
            seen.add(key)
            out.append({"path": str(p), "total_gb": round(u.total / 1e9, 1), "free_gb": round(u.free / 1e9, 1)})
        return out

    async def first_snapshot(self, timeout: float = 3.0) -> None:
        """Wait for a GPU snapshot (or a definitive 'no GPU'), 3 s max (DECISIONS D9)."""
        if self.gpu_ok is None:
            if self._task is None:
                await self.poll()
                return
            try:
                await asyncio.wait_for(self._first.wait(), timeout)
            except asyncio.TimeoutError:
                pass

    def free_excluding(self, pid: int | None) -> int | None:
        """Free VRAM (MiB) as if process `pid` (our own llama-server) had released its memory."""
        d = self.gpu
        if not d:
            return None
        return d["free"] + (d["apps"].get(pid, 0) if pid else 0)

    def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._loop(), name="monitor")

    async def _loop(self) -> None:
        while True:
            try:
                await self.poll()
            except Exception:  # noqa: BLE001
                log.exception("monitor poll failed")
            await asyncio.sleep(self.interval)

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except BaseException:  # noqa: BLE001
                pass
            self._task = None
