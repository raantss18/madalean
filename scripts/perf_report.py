#!/usr/bin/env python3
"""Where does a proof spend its time? (TODO B9, docs/PERFORMANCE.md)

1. Stage durations read from real dossiers: the exact `seconds` param of each result event when the server wrote
   it (S-AF, D38), else the time from the previous event to this one (grouped by event kind; gaps > 1 h ignored).
2. Job timings (`<jobs>/<dossier>.json`, field `timings`: one row per stage run, start/end; D38) and, for every job,
   the time from the accepted statement (or the job start) to the first proof attempt.
3. `--lean`: cost of one `lean --json` check of a trivial Mathlib proof in every installed workspace, cold then warm
   (page cache), through the same sandbox as the server.

Usage: perf_report.py [--dossiers ~/.config/madalean/dossiers] [--jobs ~/.config/madalean/jobs] [--lean]
                      [--json out.json]"""
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
EVENT_STAGE = {"understood": "understand", "statement": "statement", "notes": "notes", "check": "verify",
               "proof": "proof", "explanation": "explanation", "informal": "informal"}

TRIVIAL = """import Mathlib
theorem perf_probe (a b : ℕ) (ha : Even a) (hb : Even b) : Even (a + b) := by
  exact ha.add hb
"""


def stages(folder: Path) -> dict:
    out: dict[str, list[float]] = defaultdict(list)
    exact: dict[str, int] = defaultdict(int)
    proofs: list[dict] = []
    for f in sorted(folder.glob("*.json")):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        prev = None
        for e in d.get("events") or []:
            t = e.get("t") or 0
            secs = (e.get("params") or {}).get("seconds")
            if e.get("kind") in KINDS and isinstance(secs, (int, float)) and secs > 0 \
                    and not (e.get("params") or {}).get("cached"):
                out[e["kind"]].append(float(secs))         # exact, written by the server (D38)
                exact[e["kind"]] += 1
            elif prev is not None and 0 <= t - prev <= 3600 and e.get("kind") in KINDS:
                out[e["kind"]].append(t - prev)
            prev = t
        for p in d.get("proofs") or []:
            m = p.get("meta") or {}
            if "seconds" in m:
                proofs.append({"strategy": m.get("strategy", ""), "attempts": m.get("attempts", 0),
                               "seconds": m["seconds"], "workspace": m.get("workspace", "")})
    table = {}
    for k, xs in out.items():
        table[k] = {"label": KINDS[k], "n": len(xs), "exact": exact[k], "median_s": round(statistics.median(xs), 1),
                    "max_s": round(max(xs), 1)}
    return {"stages": table, "proofs": proofs}


def first_attempt_delay(job: dict) -> float | None:
    """Seconds from the accepted statement (or the job start when the statement was given) to the first proof
    attempt of the job (Mathlib-first included), None when the job never reached the proof."""
    rows = job.get("timings") or []
    t0 = next((r.get("end") for r in rows if r.get("stage") == "statement" and r.get("end")), None)
    if t0 is None:
        st = [a for a in job.get("attempts") or [] if a.get("stage") == "statement" and a.get("status") == "accepted"]
        if st:
            a = st[-1]
            t0 = a.get("t", 0) + a.get("gen_seconds", 0) + a.get("compile_seconds", 0)
    if t0 is None:
        t0 = job.get("started")
    first = min((a.get("t", 0) for a in job.get("attempts") or [] if a.get("stage") == "proof"), default=None)
    if t0 is None or first is None or first < t0 - 1:
        return None
    return first - t0


def jobs(folder: Path) -> dict:
    per: dict[str, list[float]] = defaultdict(list)
    delays: list[float] = []
    for f in sorted(folder.glob("*.json")):
        try:
            hist = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for j in hist if isinstance(hist, list) else []:
            for r in j.get("timings") or []:
                if isinstance(r.get("seconds"), (int, float)):
                    per[r["stage"]].append(float(r["seconds"]))
            x = first_attempt_delay(j)
            if x is not None and j.get("state") in ("done", "failed"):
                delays.append(x)
    table = {k: {"n": len(xs), "median_s": round(statistics.median(xs), 1), "max_s": round(max(xs), 1)}
             for k, xs in per.items()}
    first = {"n": len(delays), "median_s": round(statistics.median(delays), 1) if delays else None,
             "max_s": round(max(delays), 1) if delays else None}
    return {"timings": table, "first_proof_attempt": first}


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
    ap.add_argument("--jobs", default=str(Path.home() / ".config/madalean/jobs"))
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
    rep["jobs"] = jobs(Path(a.jobs).expanduser())
    if rep["jobs"]["timings"]:
        print("chronométrage des tâches (début → fin de chaque étape, D38) :")
        for k, v in sorted(rep["jobs"]["timings"].items()):
            print(f"  {k:36} {v['n']:>3} {v['median_s']:>8}s {v['max_s']:>7}s")
    fa = rep["jobs"]["first_proof_attempt"]
    if fa["n"]:
        print(f"premier essai de preuve après l'énoncé accepté : médiane {fa['median_s']} s, max {fa['max_s']} s "
              f"(n = {fa['n']})")
    if a.lean:
        rep["lean"] = asyncio.run(lean_costs())
        for k, v in rep["lean"].items():
            print(f"lean {k[:50]:50} 1er {v['first_s']} s, ensuite {v['warm_s']} s")
    if a.json:
        Path(a.json).write_text(json.dumps(rep, indent=1, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
