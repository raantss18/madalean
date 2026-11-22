"""First-run latency of a Calcul notebook with the real sandboxed Sage kernel (S-AO, TODO B15, DECISIONS D47).

Measures, on a test server in a temporary directory (never the live server), the wall time of the first cell, the
first integral, the first plot and the first factorisation over GF(p^k) of a freshly opened Sage document, in three
situations:
  new      a new project (its kernel home is empty: Maxima / matplotlib caches absent)
  reopen   the same project reopened after its kernel stopped (caches present)
  other project   a second new project (its home is empty, but the first-use caches prepared once per Sage
                  version — `<experiments>/.home/.seed`, filled by a warm-up — are copied in at kernel start)
and, with `--warm`, the document is opened (GET, which starts the kernel ready in advance) and the script waits
until the kernel reports `ready` (the user reading / typing) before running the cells.

    .venv/bin/python scripts/dev/bench_calcul_first_run.py            # kernel started by the first run
    .venv/bin/python scripts/dev/bench_calcul_first_run.py --warm     # kernel ready in advance
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "tests")]

CELLS = [("first cell", "1 + 1"),
         ("first integral", "integrate(x*sin(x), x)"),
         ("first plot", "plot(sin(x), (x, 0, 2*pi))"),
         ("first GF(p^k) factorisation", "K.<a> = GF(3^4); R.<y> = K[]; (y^12 + a*y + 1).factor()")]


async def one(tmp: Path, warm: bool, rounds: tuple[str, ...], wait: bool = True) -> dict:
    from helpers import make_ctx, running, session
    ctx = make_ctx(tmp)
    out: dict = {}
    async with running(ctx) as (_srv, L, _R), session() as s:
        ctx.settings.experiments_auto = True              # the bench's own fixed code runs without approval
        ctx.settings.calcul_warm = warm                   # (after the start, which reads the settings file)
        async def new_doc() -> str:
            pid = (await (await s.post(L + "/api/projects", json={"title": "Bench"})).json())["project"]["id"]
            doc = (await (await s.post(L + f"/api/calcul/{pid}/docs", json={"title": "B", "language": "sage"}))
                   .json())["doc"]["id"]
            return L + f"/api/calcul/{pid}/docs/{doc}"
        D = await new_doc()
        for rnd in rounds:
            if rnd == "other project":
                D = await new_doc()
            row: dict = {}
            t_open = time.monotonic()
            await s.get(D)                                    # the user opens the document
            if warm and wait:
                while time.monotonic() - t_open < 300:
                    st = (await (await s.get(D)).json())["status"]
                    if (st.get("warm") or {}).get("state") in ("ready", "failed", "off"):
                        break
                    await asyncio.sleep(0.25)
                row["ready after open (s)"] = round(time.monotonic() - t_open, 2)
                row["warm"] = st.get("warm")
            ids = []
            for _label, src in CELLS:
                c = (await (await s.post(D + "/cells", json={"source": src})).json())["cell"]
                ids.append(c["id"])
            for (label, _src), cid in zip(CELLS, ids):
                t0 = time.monotonic()
                r = await (await s.post(D + f"/cells/{cid}/run", json={"timeout": 300})).json()
                row[label] = round(time.monotonic() - t0, 2)
                if r["run"]["status"] != "ok":
                    row[label + " status"] = r["run"]["status"] + " " + (r["run"].get("error") or "")[:200]
            out[rnd] = row
            await s.post(D + "/shutdown")
            await asyncio.sleep(1.0)
    await ctx.jupyter.stop()
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--warm", action="store_true")
    ap.add_argument("--now", action="store_true", help="with --warm: run the cells right after opening (no wait)")
    ap.add_argument("--keep", default="", help="use (and keep) this directory instead of a temporary one")
    a = ap.parse_args()
    if a.keep:
        Path(a.keep).mkdir(parents=True, exist_ok=True)
        res = asyncio.run(one(Path(a.keep), a.warm, ("new", "reopen", "other project"), not a.now))
    else:
        with tempfile.TemporaryDirectory(prefix="mdl-bench-") as d:
            res = asyncio.run(one(Path(d), a.warm, ("new", "reopen", "other project"), not a.now))
    print(json.dumps({"warm": a.warm, "wait": not a.now, **res}, indent=1))


if __name__ == "__main__":
    main()
