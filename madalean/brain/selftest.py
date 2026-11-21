"""Manual end-to-end test of one provider with a real key (costs a few cents with a paid provider).

    python -m madalean.brain.selftest --provider anthropic        # key from $ANTHROPIC_API_KEY
    python -m madalean.brain.selftest --provider gemini           # $GEMINI_API_KEY
    python -m madalean.brain.selftest --provider openrouter       # $OPENROUTER_API_KEY
    python -m madalean.brain.selftest --provider free             # keyless free providers

Runs: one short completion, one tool-use round, one prove_with_agent run on
`theorem t (a b : ℕ) (ha : Even a) (hb : Even b) : Even (a + b)` against the real Lean of the workspace.
Prints model, tokens, seconds and (Anthropic) an estimated cost. Nothing is written outside a temporary directory
except the RAG index (--cache, default ~/.cache/madalean)."""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import tempfile
import time
from pathlib import Path

from . import create_brain, create_retriever
from .api import Chunk, ToolSpec
from .catalogue import ANTHROPIC_MODELS

# $ per million tokens (input, output) — claude-api skill, cached 2026-11-03
PRICES = {"claude-opus-5-5": (4.0, 20.0), "claude-sonnet-5-5": (2.0, 10.0), "claude-haiku-5-5": (0.10, 0.50)}
ENV = {"anthropic": "ANTHROPIC_API_KEY", "gemini": "GEMINI_API_KEY", "openrouter": "OPENROUTER_API_KEY"}
STATEMENT = "theorem t (a b : ℕ) (ha : Even a) (hb : Even b) : Even (a + b) := by sorry"


def cost(model: str, tin: int, tout: int) -> str:
    p = PRICES.get(model)
    return f" ≈ ${(tin * p[0] + tout * p[1]) / 1e6:.4f}" if p else ""


async def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="python -m madalean.brain.selftest")
    ap.add_argument("--provider", required=True, help="anthropic | gemini | openrouter | free")
    ap.add_argument("--model", default="", help="model id (default: the router's choice for this provider)")
    ap.add_argument("--workspace", default="lean-prover49")
    ap.add_argument("--cache", default=str(Path.home() / ".cache" / "madalean"))
    ap.add_argument("--max-steps", type=int, default=16)
    ap.add_argument("--skip-prove", action="store_true")
    ap.add_argument("--only-prove", action="store_true")
    ap.add_argument("--transcript", default="", help="write the agent transcript (JSON) to this file")
    args = ap.parse_args(argv)
    prov = args.provider
    key = os.environ.get(ENV.get(prov, ""), "") if prov != "free" else ""
    if prov in ENV and not key:
        print(f"Set {ENV[prov]} first.")
        return 2
    conf = Path(tempfile.mkdtemp(prefix="madalean-selftest-"))
    brain = create_brain(conf, None, lambda p: key if p == prov else None, {"mode": "online", "paid_first": True})
    try:
        await brain.refresh()
        cands = [c for c in brain.candidates("prove", "online") if prov == "free" and not c.paid or c.provider == prov]
        if args.model:
            prefer = f"{prov}:{args.model}"
        elif prov == "anthropic":
            prefer = "anthropic:" + ANTHROPIC_MODELS[0][0]
        else:
            prefer = cands[0].key if cands else None
        print(f"provider {prov}, model {prefer}")
        print("ranking (prove):")
        for r in brain.explain("prove", "online")[:6]:
            print(f"  {r['score']:.3f} {r['model']}: {r['why']}")
        if args.only_prove:
            return await _prove(brain, args)
        # 1. completion
        t0 = time.monotonic()
        c = await brain.complete("explain", [{"role": "user", "content": "Reply with exactly the word: OK"}],
                                 mode="online", prefer=prefer, max_tokens=2000)
        print(f"\n[1] completion by {c.model.key}: {c.text.strip()[:80]!r} — {c.tokens_in} in / {c.tokens_out} out, "
              f"{time.monotonic() - t0:.1f} s{cost(c.model.model_id, c.tokens_in, c.tokens_out)}; fallbacks {c.fallbacks}")
        # 2. one tool round
        calls = []

        async def add(a: dict) -> str:
            calls.append(a)
            return str(int(a["a"]) + int(a["b"]))
        t0 = time.monotonic()
        r = await brain.run_agent("assistant", "Use the tools to answer. Answer with the number only.",
                                  "What is 1234 + 4321? Use the `add` tool.",
                                  [ToolSpec("add", "Add two integers.", {"type": "object", "properties": {
                                      "a": {"type": "integer"}, "b": {"type": "integer"}}, "required": ["a", "b"]}, add)],
                                  mode="online", prefer=prefer, max_steps=4, max_seconds=180)
        print(f"[2] tool round by {r.model.key}: tool calls {calls}, answer {r.final_text.strip()[:60]!r}, "
              f"steps {r.steps}, finish {r.finish}, {time.monotonic() - t0:.1f} s")
        if args.skip_prove:
            return 0
        return await _prove(brain, args)
    finally:
        await brain.close()


async def _prove(brain, args) -> int:
    if True:
        # 3. agentic proof with the real Lean
        from .leanrun import check_with_lean, workspace
        from .prover_agent import prove_with_agent
        ws = workspace(args.workspace)
        if ws is None:
            print(f"[3] workspace {args.workspace} not ready: skipped")
            return 0
        retr = create_retriever(Path(args.cache), embeddings=False)
        print(f"[3] RAG index ready: {await retr.ensure(args.workspace, timeout=900)}")
        log: list[str] = []

        def on_chunk(ch: Chunk) -> None:
            if ch.kind in ("tool_call", "tool_result", "info"):
                log.append(f"{ch.kind}: {ch.text[:120]!r}")
                print("   ", log[-1])
        t0 = time.monotonic()
        res = await prove_with_agent(brain, retr, statement=STATEMENT, workspace_key=args.workspace,
                                     check=lambda code: check_with_lean(ws, code), on_chunk=on_chunk, mode="online",
                                     max_steps=args.max_steps, max_seconds=900, )
        m = res["model"]
        print(f"[3] prove_with_agent: finish {res['finish']}, steps {res['steps']}, Lean checks {res['checks']}, "
              f"{time.monotonic() - t0:.0f} s, model {m.key if m else None}")
        if res["code"]:
            print(res["code"])
        if args.transcript:
            Path(args.transcript).write_text(json.dumps(res["transcript"], ensure_ascii=False, indent=1, default=str))
        await retr.close()
        return 0 if res["code"] else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1:])))
