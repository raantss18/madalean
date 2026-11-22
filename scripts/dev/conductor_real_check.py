#!/usr/bin/env python3
"""Real validation of the conductor's Claude calls (S-AI, D41) — SPENDS MONEY (a few cents).

    conductor_real_check.py [--decisions plan,plan,fix_statement,final] [--cap 1.0]

The Anthropic key is read through Madalean's own key store (read-only: `KeyStore.get`, never printed or logged);
everything else (catalogue, states, spend ledger) lives in a throw-away directory, so nothing is written to the
user's configuration. The throw-away ledger's monthly cap is `--cap` USD: the app's own budget check refuses any call
beyond it. Prints, per decision: the model the conductor chose, wall seconds, tokens (in / out / cache read / cache
write), the real cost from the API's usage, and whether the answer validated against the schema."""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from madalean import paths as paths_mod  # noqa: E402
from madalean.brain import conductor as C, create_brain, spend, toolcards  # noqa: E402
from madalean.keys import KeyStore  # noqa: E402

PROBLEM = ("Soit $n$ un entier naturel. Montrer que $n^3 - n$ est divisible par 6.")
BAD = ("theorem real_check_t (n : ℕ) : 6 ∣ n ^ 3 - n := by sorry\n-- attempt 2:\n"
       "theorem real_check_t (n : ℤ) : 6 ∣ n^3 - n ∧ := by sorry")
LEAN_ERR = "line 3: unexpected token ':='; expected term"


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--decisions", default="plan,plan,fix_statement,final")
    ap.add_argument("--cap", type=float, default=1.0)
    ap.add_argument("--difficulty", default="medium", choices=("easy", "medium", "hard"))
    a = ap.parse_args()
    real = paths_mod.Paths.default() if hasattr(paths_mod.Paths, "default") else None
    cfg = Path(real.config if real else Path.home() / ".config" / "madalean")
    store = KeyStore(cfg / "keys.json")
    if store.get("anthropic") is None:
        sys.exit("no Anthropic key in Madalean's key store")
    tmp = Path(tempfile.mkdtemp(prefix="madalean-conductor-real-"))
    brain = create_brain(tmp, None, lambda p: store.get(p) if p == "anthropic" else None,
                         {"refresh_catalogue": False, "ollama": False, "mode": "online",
                          "claude_cap_month_usd": a.cap, "claude_cap_proof_usd": a.cap, "conductor": True})
    c = C.Conductor(brain)
    print("Claude models usable:", c.claude_models("online"))
    feats = toolcards.features_of(PROBLEM)
    users = {
        "plan": (f"Problem (user's words): {PROBLEM}\nStages to run: understand, statement, proof, explanation\n"
                 "Domain: number_theory; estimated difficulty: medium; interface language: fr\n"
                 "Candidates per kind: formalize: auto; prove: auto; explain: auto"),
        "fix_statement": f"Theorem name: real_check_t\nProblem: {PROBLEM}\n\nRejected translations:\n```lean4\n{BAD}\n```\n"
                         f"Lean errors:\n{LEAN_ERR}",
        "final": (f"User's problem: {PROBLEM}\n\nLean statement:\n```lean4\ntheorem real_check_t (n : ℤ) : 6 ∣ n ^ 3 - n "
                  ":= by sorry\n```\nNo verified proof.\n\nExplanation given to the user:\nOn écrit n^3 - n = (n-1)n(n+1), "
                  "produit de trois entiers consécutifs : l'un est pair, l'un est multiple de 3, donc 6 divise."),
    }
    schemas = {"plan": C.PLAN_SCHEMA, "fix_statement": C.FIX_STATEMENT_SCHEMA, "final": C.FINAL_SCHEMA}
    total = 0.0
    tok = spend.SPEND_SCOPE.set("real-check")
    brain.ledger.scope_caps["real-check"] = a.cap
    try:
        for kind in a.decisions.split(","):
            decision = "fix" if kind.startswith("fix") else kind
            t0 = time.monotonic()
            try:
                r = await c.ask(decision, kind=kind, user=users[kind], schema=schemas[kind], difficulty=a.difficulty,
                                mode="online", scope="real-check", features=feats, claude=True)
            except C.NoConductor as e:
                print(f"{kind:14} no conductor: {e.tried}")
                continue
            total += r.usd
            ok = kind != "plan" or C.validate_plan(r.data, {}) is not None
            print(f"{kind:14} {r.name:14} {time.monotonic() - t0:5.1f} s  in {r.tokens_in:6d}  out {r.tokens_out:5d}  "
                  f"cache read {r.cache_read:5d} write {r.cache_write:5d}  {r.usd:.5f} $  valid={ok}  "
                  f"tried={r.tried}")
            if kind == "fix_statement":
                print("   →", json.dumps(r.data, ensure_ascii=False)[:300])
            if kind == "final":
                print("   →", json.dumps(r.data, ensure_ascii=False)[:300])
    finally:
        spend.SPEND_SCOPE.reset(tok)
        await brain.close()
    print(f"TOTAL real spend: {total:.5f} $ (ledger: {brain.ledger.month_total():.5f} $)")


if __name__ == "__main__":
    asyncio.run(main())
