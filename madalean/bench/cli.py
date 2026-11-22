"""`madalean bench …` (docs/BENCH.md).

  madalean bench sets                          the problem sets, their pinned sources and licences
  madalean bench fetch minif2f|putnam          download a set at its pinned commit into the cache (outside the source)
  madalean bench check SET --workspace W       which statements does this Lean / Mathlib accept
  madalean bench run SET --strategy S …        run (or resume) a benchmark; free and no-model strategies only unless
                                               --paid-budget USD is given
  madalean bench report DIR… [--publish]       print the summary of runs; --publish copies it to bench/results/
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import tempfile
from pathlib import Path

RESULTS = Path(__file__).resolve().parents[2] / "bench" / "results"


def add_parser(sub) -> None:
    b = sub.add_parser("bench", help="reproducible benchmark of the proof pipeline (docs/BENCH.md)",
                       description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    bs = b.add_subparsers(dest="bench_cmd", required=True)
    bs.add_parser("sets", help="list the problem sets")
    f = bs.add_parser("fetch", help="download a set at its pinned commit")
    f.add_argument("set", choices=["minif2f", "putnam"])
    f.add_argument("--force", action="store_true")
    f.add_argument("--allow-unpinned", action="store_true", help="accept content that differs from the pinned hash")

    def selection(p):
        p.add_argument("set", help="smoke | minif2f | putnam")
        p.add_argument("--workspace", default="lean-prover49")
        p.add_argument("--split", default="", help="miniF2F: valid | test")
        p.add_argument("--sample", type=int, default=0, help="seeded random sample of this size (0 = all)")
        p.add_argument("--seed", type=int, default=0)
        p.add_argument("--limit", type=int, default=0, help="first N of the (sampled) selection")
        p.add_argument("--id", action="append", default=[], help="only these problems (repeatable)")
    c = bs.add_parser("check", help="which statements compile in a workspace")
    selection(c)
    c.add_argument("--json", action="store_true")
    r = bs.add_parser("run", help="run or resume a benchmark")
    selection(r)
    r.add_argument("--strategy", default="mathlib",
                   help="mathlib | single | tournament | conductor | goedel-local | certificate")
    r.add_argument("--model", default="", help="single: provider:model_id")
    r.add_argument("--providers", default="", help="model set: comma-separated provider ids (default: every free one)")
    r.add_argument("--attempts", type=int, default=4)
    r.add_argument("--rounds", type=int, default=1, help="tournament exploration rounds after round 0")
    r.add_argument("--contestants", type=int, default=3)
    r.add_argument("--time-per-problem", type=float, default=240.0, metavar="SECONDS")
    r.add_argument("--time-budget", type=float, default=0.0, metavar="MINUTES", help="whole run (0 = none)")
    r.add_argument("--paid-budget", type=float, default=0.0, metavar="USD",
                   help="allow paid models up to this amount for the whole run (default 0: no paid call at all)")
    r.add_argument("--jobs", type=int, default=2)
    r.add_argument("--compile-timeout", type=int, default=120)
    r.add_argument("--no-mathlib-first", action="store_true")
    r.add_argument("--label", default="")
    r.add_argument("--out", type=Path, help="run directory (default: <cache>/runs/<set>-<config>-<workspace>…)")
    r.add_argument("--keys-from", type=Path, help="configuration directory whose key store is read (default: yours)")
    r.add_argument("--no-seed", action="store_true",
                   help="do not copy the model catalogue / measured rankings / Mathlib index of your Madalean")
    r.add_argument("--publish", action="store_true", help="copy the summary to bench/results/ when the run ends")
    p = bs.add_parser("report", help="summaries of run directories")
    p.add_argument("dirs", nargs="+", type=Path)
    p.add_argument("--publish", action="store_true")
    for x in (f, c, r):
        x.add_argument("--cache-dir", type=Path, help="benchmark cache (default ~/.cache/madalean-bench)")


def _select(args):
    from . import sets as S
    ps = S.load(args.set, args.cache_dir, split=args.split)
    total = len(ps)
    ps = S.select(ps, sample=args.sample, seed=args.seed, ids=args.id, limit=args.limit)
    sel = {"split": args.split, "set_size": total, "sample": args.sample if args.sample and args.sample < total else 0,
           "seed": args.seed if args.sample and args.sample < total else None, "limit": args.limit,
           "ids": bool(args.id), "count": len(ps)}
    return ps, sel


def result_name(summary: dict) -> str:
    import re
    sel = summary.get("selection") or {}
    part = (f"-{sel['split']}" if sel.get("split") else "") + (f"-n{sel['count']}" if sel.get("count") != sel.get(
        "set_size") else "") + (f"-seed{sel['seed']}" if sel.get("seed") is not None else "")
    raw = f"{summary['set']}{part}__{summary['config']}__{summary['workspace']}"
    return re.sub(r"[^\w.+=-]+", "-", raw) + ".json"


def publish(summary: dict, results: Path = RESULTS) -> Path:
    """Copy a summary into the committed results (no proof, no prompt: counts, times, costs and ids only)."""
    results.mkdir(parents=True, exist_ok=True)
    out = results / result_name(summary)
    out.write_text(json.dumps(summary, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return out


def resummarise(run_dir: Path) -> dict:
    """The summary of a run directory rebuilt from its rows (the rows are the record; the summary is derived)."""
    from . import runner as R
    old = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    run = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    rows = R.final_rows(R.read_rows(run_dir / "rows.jsonl"))
    cfg = R.BenchConfig(**run["config"])
    known = json.loads((run_dir / "statements.json").read_text(encoding="utf-8"))
    ids = sorted(set(known.get("ok", [])) | set(known.get("bad", {})) | set(rows))
    new = R.summarise(cfg, run["set"], run.get("source") or {}, run.get("selection") or {},
                      {"workspace": old.get("workspace"), "lean": old.get("lean"), "mathlib": old.get("mathlib")},
                      rows, ids, stop=old.get("stop", "done"), started=0, elapsed=old.get("elapsed_s", 0.0))
    for k in ("date", "madalean", "commit", "selected", "complete"):
        new[k] = old.get(k, new[k])
    return new


def line(s: dict) -> str:
    cpv = s.get("cost_per_verified_usd")
    return (f"{s['set']:<8} {s['config']:<28} {s['workspace']:<14} {s['solved']:>3}/{s['attempted']:<3}"
            f" (selected {s['selected']}, not compiling {s['statement_errors']})"
            f"  median {s.get('median_wall_s_solved') if s.get('median_wall_s_solved') is not None else '—'} s"
            f"  cost {s.get('cost_usd', 0):.4f} $"
            f"  per proof {('%.4f $' % cpv) if cpv is not None else '—'}  [{s.get('stop')}]")


def main(args) -> int:
    from . import runner as R
    from . import sets as S
    cmd = args.bench_cmd
    try:
        if cmd == "sets":
            for name in S.SET_NAMES:
                if name == "smoke":
                    print(f"smoke     built-in, {len(S.SMOKE)} statements, Apache-2.0 (Madalean)")
                    continue
                src = S.SOURCES[name]
                try:
                    m = S.source_meta(name)
                    state = f"cached: {m['problems']} problems, content sha256 {m['content_sha256'][:16]}…"
                except S.SetError:
                    state = "not fetched"
                print(f"{name:<9} {src.repo}@{src.commit[:12]}  {src.licence}  ({src.lean})  {state}")
            return 0
        if cmd == "fetch":
            m = S.fetch(args.set, args.cache_dir, force=args.force, allow_unpinned=args.allow_unpinned)
            print(json.dumps(m, indent=1))
            return 0
        if cmd == "report":
            for d in args.dirs:
                s = resummarise(d)
                print(line(s))
                if args.publish:
                    print("  ->", publish(s))
            return 0
        problems, sel = _select(args)
        if not problems:
            print("no problem selected", file=sys.stderr)
            return 2
        source = S.source_meta(args.set, args.cache_dir)
        if cmd == "check":
            return asyncio.run(_check(args, problems))
        cfg = R.BenchConfig(strategy=args.strategy, workspace=args.workspace, model=args.model,
                            providers=[p for p in args.providers.split(",") if p], attempts=args.attempts,
                            rounds=args.rounds, contestants=args.contestants, time_per_problem=args.time_per_problem,
                            time_budget=args.time_budget * 60.0, paid_budget=max(0.0, args.paid_budget),
                            jobs=args.jobs, compile_timeout=args.compile_timeout,
                            mathlib_first=not args.no_mathlib_first, label=args.label)
        R.settings_for(cfg)                       # refuse a bad configuration before anything starts
        tag = f"{args.set}{'-' + args.split if args.split else ''}-n{len(problems)}" + (
            f"-seed{args.seed}" if sel["seed"] is not None else "")
        out = args.out or S.cache_root(args.cache_dir) / "runs" / f"{tag}__{cfg.name.replace(':', '_').replace('/', '_')}__{cfg.workspace}"
        from .. import config
        summary = asyncio.run(R.run_bench(
            cfg, args.set, problems, out, source=source, selection=sel, keys_from=args.keys_from,
            seed_from=None if args.no_seed else config.CONFIG_DIR,
            seed_cache=None if args.no_seed else config.CACHE_DIR,
            progress=lambda s: print(s, flush=True)))
        print(line(summary))
        print(f"rows: {out / 'rows.jsonl'}\nsummary: {out / 'summary.json'}")
        if args.publish:
            print("published:", publish(summary))
        return 0 if summary["stop"] != "paid_call_without_budget" else 3
    except (S.SetError, R.BenchError) as e:
        print(f"madalean bench: {e}", file=sys.stderr)
        return 2


async def _check(args, problems) -> int:
    from . import runner as R
    from . import sets as S
    cfg = R.BenchConfig(strategy="mathlib", workspace=args.workspace)
    with tempfile.TemporaryDirectory(prefix="madalean-bench-check-") as tmp:
        ctx = R.build_context(Path(tmp), cfg)
        try:
            await R.start_context(ctx, cfg)
            ws = ctx.workspace(args.workspace)
            if ws is None or await ctx.lean.problems(ws):
                raise R.BenchError(f"workspace {args.workspace} is not ready")
            from ..runtime.lean import workspace_info
            info = workspace_info(ws)
            c = await R.check_statements(ctx, ws, problems, progress=None if args.json else
                                         (lambda s: print(s, file=sys.stderr, flush=True)))
        finally:
            await ctx.stop()
    rep = {"set": args.set, "split": args.split, "workspace": args.workspace, "lean": info.get("lean"),
           "mathlib": info.get("mathlib"), "checked": len(problems), "compiling": len(c.ok),
           "not_compiling": len(c.bad), "errors": c.bad}
    if args.set in S.SOURCES:
        f = S.set_dir(args.set, args.cache_dir) / f"compile-{args.workspace}{'-' + args.split if args.split else ''}.json"
        if len(problems) == len(S.load(args.set, args.cache_dir, split=args.split)):
            f.write_text(json.dumps(rep, indent=1, ensure_ascii=False), encoding="utf-8")
    if args.json:
        print(json.dumps(rep, indent=1, ensure_ascii=False))
    else:
        print(f"{args.set}{' ' + args.split if args.split else ''} in {args.workspace} (Lean {info.get('lean')}, "
              f"Mathlib {info.get('mathlib')}): {len(c.ok)}/{len(problems)} statements compile, "
              f"{len(c.bad)} do not")
        for pid, why in sorted(c.bad.items())[:40]:
            print(f"  {pid}: {why[:160]}")
    return 0
