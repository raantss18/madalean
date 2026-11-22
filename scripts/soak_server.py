#!/usr/bin/env python3
"""Server soak (2.0): `madalean serve --demo` on spare ports for N minutes, driven like a busy day.

Load: ~6 dossiers running at any time (full plan, scripted models + simulated Lean), 5 WebSocket clients that
reconnect every 60 s, a PATCH burst on dossier titles every 30 s, and the read routes the UI polls.
Samples every 30 s: server RSS, open fds, threads, jobs known, WS events received, errors.
Writes the samples and a verdict (memory slope over the second hour) to --out.

Usage: soak_server.py --minutes 120 --out bench/soak_v2.json"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import random
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import aiohttp
import psutil

ROOT = Path(__file__).resolve().parent.parent
PORT, RPORT = 11600, 11601
BASE = f"http://127.0.0.1:{PORT}"
HDRS = {"Origin": BASE, "Sec-Fetch-Site": "same-origin"}
PROBLEMS = ["Montrer que la somme de deux entiers pairs est paire.",
            "Montrer que le produit de deux entiers impairs est impair.",
            "Montrer que pour tout entier n, n² + n est pair.",
            "Montrer que toute fonction continue sur un compact est bornée.",
            "Montrer que si n² est pair alors n est pair."]
STATS = {"jobs": 0, "ws_events": 0, "reconnects": 0, "errors": 0, "patches": 0, "reads": 0}
ERRS: list[str] = []


def err(what: str) -> None:
    STATS["errors"] += 1
    if len(ERRS) < 50:
        ERRS.append(f"{time.strftime('%H:%M:%S')} {what}")


async def wait_up(s: aiohttp.ClientSession) -> None:
    for _ in range(120):
        try:
            async with s.get(f"{BASE}/api/hello") as r:
                if r.status == 200:
                    return
        except aiohttp.ClientError:
            pass
        await asyncio.sleep(0.5)
    raise SystemExit("server did not start")


async def running(s) -> int:
    async with s.get(f"{BASE}/api/jobs", headers=HDRS) as r:
        data = await r.json()
    return len(data.get("active") or [])


REUSE = False


async def submitter(s, stop) -> None:
    ids: list[str] = []
    while not stop.is_set():
        try:
            if REUSE and len(ids) >= 6:
                if await running(s) < 6:
                    for did in ids:
                        async with s.post(f"{BASE}/api/dossiers/{did}/run", headers=HDRS,
                                          json={"plan": ["notes", "proof", "explanation"]}) as r:
                            if r.status == 202:
                                STATS["jobs"] += 1
                            elif r.status != 409:
                                err(f"run {r.status} {(await r.text())[:120]}")
            elif await running(s) < 6:
                async with s.post(f"{BASE}/api/dossiers", headers=HDRS,
                                  json={"problem": random.choice(PROBLEMS)}) as r:
                    if r.status == 201:
                        STATS["jobs"] += 1
                        ids.append((await r.json())["dossier"]["id"])
                        ids[:] = ids[-50:]
                    else:
                        err(f"create {r.status} {(await r.text())[:120]}")
        except Exception as e:  # noqa: BLE001
            err(f"submit {e!r}"[:200])
        await asyncio.sleep(1.0)
        if ids and random.random() < 0.05:
            await patch_burst(s, ids)


async def patch_burst(s, ids) -> None:
    for i in range(10):
        did = random.choice(ids)
        try:
            async with s.patch(f"{BASE}/api/dossiers/{did}", headers=HDRS, json={"title": f"soak {i} {time.time():.0f}"}) as r:
                STATS["patches"] += 1
                if r.status >= 400 and r.status != 409:
                    err(f"patch {r.status}")
        except Exception as e:  # noqa: BLE001
            err(f"patch {e!r}"[:200])


async def reader(s, stop) -> None:
    routes = ["/api/state", "/api/dossiers", "/api/library", "/api/projects", "/api/models", "/api/settings"]
    while not stop.is_set():
        for r_ in routes:
            try:
                async with s.get(BASE + r_, headers=HDRS) as r:
                    await r.read()
                    STATS["reads"] += 1
                    if r.status >= 500:
                        err(f"GET {r_} {r.status}")
            except Exception as e:  # noqa: BLE001
                err(f"GET {r_} {e!r}"[:200])
        await asyncio.sleep(5)


async def ws_client(s, stop, n: int) -> None:
    await asyncio.sleep(n)
    while not stop.is_set():
        try:
            async with s.ws_connect(f"ws://127.0.0.1:{PORT}/api/ws", headers=HDRS, heartbeat=20) as ws:
                end = time.monotonic() + 60 + random.uniform(-5, 5)
                while time.monotonic() < end and not stop.is_set():
                    try:
                        m = await ws.receive(timeout=max(0.1, end - time.monotonic()))
                    except asyncio.TimeoutError:
                        break
                    if m.type == aiohttp.WSMsgType.TEXT:
                        STATS["ws_events"] += 1
                    elif m.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                        err(f"ws{n} closed by server")
                        break
            STATS["reconnects"] += 1
        except Exception as e:  # noqa: BLE001
            err(f"ws{n} {e!r}"[:200])
            await asyncio.sleep(2)


def sample(proc: psutil.Process, t0: float) -> dict:
    with proc.oneshot():
        procs = [proc] + proc.children(recursive=True)
        rss = sum(p.memory_info().rss for p in procs if p.is_running())
        return {"t_min": round((time.time() - t0) / 60, 2), "rss_mb": round(proc.memory_info().rss / 2**20, 1),
                "tree_rss_mb": round(rss / 2**20, 1), "fds": proc.num_fds(), "threads": proc.num_threads(),
                "children": len(procs) - 1, **STATS}


def slope(xs, ys) -> float:
    n = len(xs)
    if n < 2:
        return 0.0
    mx, my = sum(xs) / n, sum(ys) / n
    den = sum((x - mx) ** 2 for x in xs) or 1
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / den


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--minutes", type=float, default=120)
    ap.add_argument("--reuse", action="store_true", help="6 dossiers re-run forever (no new dossier)")
    ap.add_argument("--out", default=str(ROOT / "bench" / "soak_v2.json"))
    a = ap.parse_args()
    global REUSE
    REUSE = a.reuse
    tmp = Path(tempfile.mkdtemp(prefix="madalean-soak-"))
    env = {**os.environ, "MADALEAN_CONFIG_DIR": str(tmp / "config"), "MADALEAN_CACHE_DIR": str(tmp / "cache"),
           "MADALEAN_DATA_DIR": str(tmp / "data")}
    log = open(tmp / "server.log", "w")
    srv = subprocess.Popen([sys.executable, "-m", "madalean", "serve", "--demo", "--no-migrate", "--port", str(PORT),
                            "--remote-port", str(RPORT), "--config-dir", str(tmp / "config"),
                            "--cache-dir", str(tmp / "cache")], cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
    proc = psutil.Process(srv.pid)
    t0 = time.time()
    samples: list[dict] = []
    stop = asyncio.Event()
    out = Path(a.out)
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as s:
            await wait_up(s)
            tasks = [asyncio.create_task(submitter(s, stop)), asyncio.create_task(reader(s, stop))]
            tasks += [asyncio.create_task(ws_client(s, stop, i)) for i in range(5)]
            while time.time() - t0 < a.minutes * 60:
                if srv.poll() is not None:
                    err(f"server exited {srv.returncode}")
                    break
                samples.append(sample(proc, t0))
                out.write_text(json.dumps({"running": True, "tmp": str(tmp), "samples": samples, "errors": ERRS},
                                          indent=1))
                await asyncio.sleep(30)
            stop.set()
            await asyncio.wait(tasks, timeout=15)
    finally:
        if srv.poll() is None:
            srv.send_signal(signal.SIGTERM)
            try:
                srv.wait(20)
            except subprocess.TimeoutExpired:
                srv.kill()
    half = [x for x in samples if x["t_min"] >= a.minutes / 2]
    verdict = {
        "minutes": a.minutes, "server_log": str(tmp / "server.log"), **STATS,
        "rss_first_mb": samples[0]["rss_mb"] if samples else None, "rss_last_mb": samples[-1]["rss_mb"] if samples else None,
        "rss_max_mb": max((x["rss_mb"] for x in samples), default=None),
        "rss_slope_second_half_mb_per_h": round(60 * slope([x["t_min"] for x in half], [x["rss_mb"] for x in half]), 2),
        "fds_range": [min((x["fds"] for x in samples), default=0), max((x["fds"] for x in samples), default=0)],
        "threads_range": [min((x["threads"] for x in samples), default=0), max((x["threads"] for x in samples), default=0)],
    }
    out.write_text(json.dumps({"running": False, "verdict": verdict, "samples": samples, "errors": ERRS}, indent=1))
    print(json.dumps(verdict, indent=1))


if __name__ == "__main__":
    asyncio.run(main())
