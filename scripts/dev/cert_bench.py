#!/usr/bin/env python3
"""Certificates benchmark (session S-AT, DECISIONS D52): the corpus of madalean/certs/corpus.py, with the installed
SageMath producing the witnesses and a fresh strict Lean checking them, on every built workspace.

    PYTHONPATH=. .venv/bin/python scripts/dev/cert_bench.py [--only prime,sos] [--json out.json] [--toolchains DIR]

Measured per statement: outcome, Sage seconds, Lean seconds, number of lines of the checked proof. The table of
docs/PERFORMANCE.md « Certificats (S-AT) » is this script's output. Runs no model and touches no server. The
producer runs here WITHOUT the sandbox (its own statements only); in the server it runs in Calcul's sandboxed
kernel. `--toolchains` adds a directory of Lean toolchains to look in (read only), for a checkout whose Lean lives
in an installed prefix."""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import statistics
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
_TMP = Path(tempfile.mkdtemp(prefix="madalean-certbench-"))
os.environ.setdefault("MADALEAN_CONFIG_DIR", str(_TMP / "config"))
os.environ.setdefault("MADALEAN_CACHE_DIR", str(_TMP / "cache"))


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    ap.add_argument("--json", default="")
    ap.add_argument("--toolchains", default="")
    ap.add_argument("--workspaces", default="")
    args = ap.parse_args()
    from madalean import syntaxcards, workspaces as W
    from madalean.certs import corpus
    from madalean.certs.producer import SubprocessProducer
    from madalean.runtime.lean import LeanRunner
    from madalean.slots import Slots
    if args.toolchains:
        orig = W.toolchain_roots
        W.toolchain_roots = lambda: orig() + [Path(args.toolchains)]
    py = syntaxcards.sage_python()
    produce = SubprocessProducer(py, _TMP / "sage") if py else None
    if produce is None:
        print("SageMath not found: only the kinds that need no witness will pass", file=sys.stderr)
    only = {k for k in args.only.split(",") if k}
    cases = [c for c in corpus.CASES if not only or c.kind in only or c.id in only]
    lean = LeanRunner(Slots({"lean": 3}), _TMP / "lean")
    wanted = {k for k in args.workspaces.split(",") if k}
    out: dict = {}
    for ws in W.all_workspaces(scan_user=False):
        if ws.problems or (wanted and ws.key not in wanted):
            continue
        rows = []
        for c, o in await corpus.run(cases, ws, lean, produce):
            rows.append({"id": c.id, "kind": c.kind, "expect": c.expect, "status": o.status, "got_kind": o.kind,
                         "sage_s": round(o.sage_seconds, 2), "lean_s": round(o.lean_seconds, 2),
                         "total_s": round(o.seconds, 2), "lines": len(o.code.splitlines()) if o.ok else 0,
                         "bytes": len(o.code.encode()) if o.ok else 0, "reason": o.reason,
                         "errors": o.errors[:600]})
        out[ws.key] = rows
        good = [r for r in rows if r["status"] == r["expect"]]
        ver = [r for r in rows if r["status"] == "verified"]
        print(f"\n## {ws.key} ({ws.toolchain}) — {len(good)}/{len(rows)} as expected, {len(ver)} verified")
        print("| statement | kind | outcome | Sage s | Lean s | proof lines |")
        print("|---|---|---|---|---|---|")
        for r in rows:
            mark = "" if r["status"] == r["expect"] else f" (expected {r['expect']}: {r['reason'] or r['errors'][:200]})"
            print(f"| {r['id']} | {r['kind']} | {r['status']}{mark} | {r['sage_s']:.2f} | {r['lean_s']:.1f} | "
                  f"{r['lines'] or ''} |")
        kinds = sorted({r["kind"] for r in rows})
        print("\n| kind | verified | median Sage s | median Lean s | median proof lines |")
        print("|---|---|---|---|---|")
        for k in kinds:
            rs = [r for r in rows if r["kind"] == k and r["expect"] == "verified"]
            okr = [r for r in rs if r["status"] == "verified"]
            if not rs:
                continue
            med = lambda f: statistics.median([r[f] for r in okr]) if okr else 0  # noqa: E731
            print(f"| {k} | {len(okr)}/{len(rs)} | {med('sage_s'):.2f} | {med('lean_s'):.1f} | {med('lines'):.0f} |")
    if args.json:
        Path(args.json).write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
