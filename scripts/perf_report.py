#!/usr/bin/env python3
"""Where does a proof spend its time? (TODO B9, docs/PERFORMANCE.md)

1. Stage durations read from real dossiers (event timestamps: time from the previous event to this one, grouped by
   event kind; gaps > 1 h and user-stopped runs are ignored).
2. `--lean`: cost of one `lean --json` check of a trivial Mathlib proof in every installed workspace, cold then warm
   (page cache), through the same sandbox as the server.

Usage: perf_report.py [--dossiers ~/.config/madalean/dossiers] [--lean] [--json out.json]"""
from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import sys
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

KINDS = {"understood": "compréhension", "statement": "traduction en Lean", "notes": "lecture guidée",
         "check": "vérification de l'énoncé", "proof": "preuve (jusqu'à la preuve vérifiée)",
         "explanation": "explication", "informal": "preuve rédigée"}

TRIVIAL = """import Mathlib
theorem perf_probe (a b : ℕ) (ha : Even a) (hb : Even b) : Even (a + b) := by
  exact ha.add hb
"""


def stages(folder: Path) -> dict:
    out: dict[str, list[float]] = defaultdict(list)
    proofs: list[dict] = []
    for f in sorted(folder.glob("*.json")):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        prev = None
        for e in d.get("events") or []:
            t = e.get("t") or 0
            if prev is not None and 0 <= t - prev <= 3600 and e.get("kind") in KINDS:
                out[e["kind"]].append(t - prev)
            prev = t
        for p in d.get("proofs") or []:
            m = p.get("meta") or {}
            if "seconds" in m:
                proofs.append({"strategy": m.get("strategy", ""), "attempts": m.get("attempts", 0),
                               "seconds": m["seconds"], "workspace": m.get("workspace", "")})
    table = {}
    for k, xs in out.items():
        table[k] = {"label": KINDS[k], "n": len(xs), "median_s": round(statistics.median(xs), 1),
                    "max_s": round(max(xs), 1)}
    return {"stages": table, "proofs": proofs}


async def lean_costs() -> dict:
    from madalean.brain import leanrun
    from madalean.workspaces import all_workspaces
    res = {}
    for w in all_workspaces():
        if w.check():
            continue
        times = []
        for _ in range(2):
            t = time.monotonic()
            r = await leanrun.check_with_lean(w, TRIVIAL)
            times.append(round(time.monotonic() - t, 2))
            if not r["ok"]:
                times.append(f"failed: {r['summary'][:80]}")
                break
        res[w.key] = {"toolchain": w.toolchain, "first_s": times[0], "warm_s": times[1] if len(times) > 1 else None}
    return res


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dossiers", default=str(Path.home() / ".config/madalean/dossiers"))
    ap.add_argument("--lean", action="store_true")
    ap.add_argument("--json")
    a = ap.parse_args()
    rep = stages(Path(a.dossiers).expanduser())
    print(f"{'étape':38} {'n':>3} {'médiane':>9} {'max':>8}")
    for k in KINDS:
        s = rep["stages"].get(k)
        if s:
            print(f"{s['label']:38} {s['n']:>3} {s['median_s']:>8}s {s['max_s']:>7}s")
    for p in rep["proofs"]:
        print(f"  preuve {p['strategy']:8} essais={p['attempts']:<3} {p['seconds']} s  ({p['workspace']})")
    if a.lean:
        rep["lean"] = asyncio.run(lean_costs())
        for k, v in rep["lean"].items():
            print(f"lean {k[:50]:50} 1er {v['first_s']} s, ensuite {v['warm_s']} s")
    if a.json:
        Path(a.json).write_text(json.dumps(rep, indent=1, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
