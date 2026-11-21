#!/usr/bin/env python3
"""Memory of a process tree (RSS and PSS from /proc/<pid>/smaps_rollup), grouped by command — used for
docs/PERFORMANCE.md. Usage: memtree.py <root pid> [--watch SECONDS --every S] (prints the peak when watching)."""
from __future__ import annotations

import sys
import time
from pathlib import Path


def children(pid: int) -> list[int]:
    out = []
    for t in Path(f"/proc/{pid}/task").glob("*"):
        try:
            out += [int(x) for x in (t / "children").read_text().split()]
        except OSError:
            pass
    return out


def tree(pid: int) -> list[int]:
    seen, stack = [], [pid]
    while stack:
        p = stack.pop()
        if p in seen:
            continue
        seen.append(p)
        stack += children(p)
    return seen


def mem(pid: int) -> tuple[int, int, str]:
    rss = pss = 0
    try:
        for line in Path(f"/proc/{pid}/smaps_rollup").read_text().splitlines():
            if line.startswith("Rss:"):
                rss = int(line.split()[1])
            elif line.startswith("Pss:"):
                pss = int(line.split()[1])
        cmd = Path(f"/proc/{pid}/cmdline").read_bytes().replace(b"\0", b" ").decode(errors="replace")
    except OSError:
        return 0, 0, ""
    return rss, pss, cmd


def label(cmd: str) -> str:
    for key in ("madalean serve", "llama-server", "madalean-net", "ipykernel", "sage", "jupyter-lab", "jupyter",
                "repl", "/lean ", "lean --json", "bwrap", "git", "python"):
        if key in cmd:
            return key.strip()
    return cmd.split(" ")[0].rsplit("/", 1)[-1][:30]


def snapshot(root: int) -> dict:
    groups: dict[str, list[int]] = {}
    for p in tree(root):
        rss, pss, cmd = mem(p)
        if not cmd:
            continue
        g = groups.setdefault(label(cmd), [0, 0, 0])
        g[0] += rss
        g[1] += pss
        g[2] += 1
    return groups


def main() -> None:
    root = int(sys.argv[1])
    if "--watch" in sys.argv:
        dur = float(sys.argv[sys.argv.index("--watch") + 1])
        every = float(sys.argv[sys.argv.index("--every") + 1]) if "--every" in sys.argv else 1.0
        peak: dict[str, list[int]] = {}
        peak_total = 0
        end = time.time() + dur
        while time.time() < end:
            s = snapshot(root)
            tot = sum(v[1] for v in s.values())
            if tot > peak_total:
                peak_total, peak = tot, s
            time.sleep(every)
        s = peak
        print(f"peak PSS total: {peak_total / 1024:.0f} MiB")
    else:
        s = snapshot(root)
    for k, (rss, pss, n) in sorted(s.items(), key=lambda kv: -kv[1][1]):
        print(f"{k:16s} n={n:2d} RSS {rss / 1024:8.0f} MiB  PSS {pss / 1024:8.0f} MiB")
    print(f"{'TOTAL':16s}       RSS {sum(v[0] for v in s.values()) / 1024:8.0f} MiB  PSS "
          f"{sum(v[1] for v in s.values()) / 1024:8.0f} MiB")


if __name__ == "__main__":
    main()
