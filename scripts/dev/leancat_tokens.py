#!/usr/bin/env python3
"""Prompt tokens before / after the verified catalogue entries (session S-AM, DECISIONS D45).

For typical requests (problem in words + Lean statement), on each built Lean workspace, the estimated tokens
(≈ 3.5 characters per token, as toolcards / spend) of: the Goedel loop's first message, the formalizer's message,
the agent's task message and the conductor's `fix_proof` request block — without and with the catalogue block.
Reads the catalogue builds of a cache directory (default: the user's, read-only); writes nothing.

    MADALEAN_WORKSPACES_DIR=… .venv/bin/python scripts/dev/leancat_tokens.py [--cache ~/.cache/madalean]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from madalean import leancheck, syntaxcards  # noqa: E402
from madalean.brain import toolcards  # noqa: E402
from madalean.pipeline import leancat  # noqa: E402
from madalean.research import codecat  # noqa: E402
from madalean.workspaces import all_workspaces  # noqa: E402

H = leancheck.GOEDEL_HEADER
REQUESTS = [
    ("Montrer que la somme des n premiers entiers impairs vaut n^2",
     {"v4.9": "theorem odd_sum (n : ℕ) : ∑ i in Finset.range n, (2 * i + 1) = n ^ 2 := by sorry",
      "default": "theorem odd_sum (n : ℕ) : ∑ i ∈ Finset.range n, (2 * i + 1) = n ^ 2 := by sorry"}),
    ("Le corps fini F_125 a 125 éléments",
     {"v4.9": "theorem f125 [Fact (Nat.Prime 5)] : Fintype.card (GaloisField 5 3) = 125 := by sorry",
      "default": "theorem f125 [Fact (Nat.Prime 5)] : Nat.card (GaloisField 5 3) = 125 := by sorry"}),
    ("Si p est premier et p divise ab alors p divise a ou b",
     {"*": "theorem euclid (p a b : ℕ) (hp : Nat.Prime p) (h : p ∣ a * b) : p ∣ a ∨ p ∣ b := by sorry"}),
    ("Le pgcd de 12 et 18 vaut 6", {"*": "theorem g : Nat.gcd 12 18 = 6 := by sorry"}),
    ("Le déterminant de [[1,2],[3,4]] vaut -2",
     {"*": "theorem d2 : Matrix.det !![(1 : ℚ), 2; 3, 4] = -2 := by sorry"}),
    ("Pour tout réel x, x^2 + 1 > 0", {"*": "theorem pos (x : ℝ) : x ^ 2 + 1 > 0 := by sorry"}),
]


def tok(s: str) -> int:
    return toolcards.estimate_tokens(s)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", default=str(Path.home() / ".cache" / "madalean"))
    a = ap.parse_args()
    syntaxcards.configure(Path(a.cache).expanduser())
    wss = [w for w in all_workspaces(scan_user=False) if not w.problems]
    print("| workspace | request | entries | Goedel 1st msg | formalizer | agent task | conductor fix_proof request |")
    print("|---|---|---|---|---|---|---|")
    for ws in wss:
        st = codecat.lean_status(ws)
        flavor = codecat.lean_flavor(ws.toolchain)
        for problem, stmts in REQUESTS:
            stmt = H + (stmts.get(flavor) or stmts.get("*") or stmts["default"])
            block, ids = leancat.block_for(ws, "prove", problem, stmt)
            fblock, _f = leancat.block_for(ws, "formalize", problem, stmt)
            goedel = leancheck.initial_prompt(stmt)
            form = leancheck.formalize_prompt(problem)
            agent = f"Prove this theorem (workspace {ws.key}):\n\n```lean\n{stmt}\n```\n\nStart with your plan."
            c0 = toolcards.compact("fix_proof", toolcards.features_of(problem, stmt), ws)
            c1 = toolcards.compact("fix_proof", toolcards.features_of(problem, stmt), ws, intent_text=problem + stmt)

            def pair(base: str, extra: str) -> str:
                b = tok(base)
                return f"{b} → {tok(base + ('\n\n' + extra if extra else ''))}"
            print(f"| {ws.key} ({'built' if st else 'not built'}) | {problem[:40]} | {', '.join(ids) or '—'} | "
                  f"{pair(goedel, block)} | {pair(form, fblock)} | {pair(agent, block)} | "
                  f"{c0.tokens_request} → {c1.tokens_request} (stable {c0.tokens_stable} = {c1.tokens_stable}) |")


if __name__ == "__main__":
    main()
