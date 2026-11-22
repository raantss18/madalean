#!/usr/bin/env python3
"""Conductor (S-AI, D41) vs the current pipeline, on `madalean serve --demo` servers with scripted models and a
simulated Lean (no network, no key, no GPU), temporary config / cache directories, ports 12100+.

    conductor_bench.py --root <source tree> [--port 12100] [--runs 3] [--scale 20] [--json out.json]

Scenarios (the scripted workers of the demo, `brain.fake.demo_responder`):
  ok            the sum of two even numbers: every stage succeeds
  bad_statement the formalizer writes a statement Lean rejects (3 times)
  hard_proof    the provers fail unless they get a hint (a conductor's plan carries one)
  hard_nohint   the same, but the plan carries no hint: the conductor must correct a failed proof
Variants: off (conductor setting false = the current pipeline), claude (Claude directs, scripted), free (no
Anthropic key: the best free model directs). Workers answer after the real median time of their stage
(docs/PERFORMANCE.md, S-AF) / SCALE; the conductor's calls after the latency measured in the real validation
(fake_conductor.LATENCY) / SCALE; Lean takes 2 s / SCALE. Reported times are multiplied back by SCALE (≈ real s).
Costs are the conductor's Claude calls priced at list prices from estimated tokens (stable prefix cached after the
first call of a model, as Anthropic's cache would)."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

PROBLEM = "Montrer que la somme de deux entiers pairs est paire."
MEDIANS = {"understand": 4.7, "formalize": 34.7, "notes": 48.8, "fidelity": 39.6, "prove": 15.0,
           "explanation": 21.0, "informal": 2.8}
LAUNCHER = r'''
import json, sys
from pathlib import Path
import madalean.brain.fake as F
import madalean.brain.fake_conductor as FC
import madalean.demo as D
scale, med, variant, scenario, stats_path = float(sys.argv[1]), json.loads(sys.argv[2]), sys.argv[3], sys.argv[4], Path(sys.argv[5])
orig = F.demo_responder

def kind(role, first):
    if first.startswith("You check a formalization"): return "fidelity"
    if first.startswith("You prepare a mathematics problem"): return "understand"
    if first.startswith(("Tu aides un étudiant", "You help a student")): return "notes"
    if first.startswith(("Tu es un professeur de mathématiques. Voici un théorème et une preuve",
                         "You are a mathematics teacher. Here is a theorem and a Lean 4 proof")): return "informal"
    if role in ("formalize", "prove"): return role
    if role == "explain": return "explanation"
    return ""

def responder(role, messages, brain):
    first = next((m.get("content", "") for m in messages if m.get("role") == "user"), "")
    k = kind(role, first)
    ans = json.dumps({"verdict": "faithful", "summary": "OK", "issues": [], "counterexamples": []}) \
        if k == "fidelity" else orig(role, messages, brain)
    d = ans if isinstance(ans, dict) else {"text": ans}
    return {**d, "delay": med.get(k, 0.0) / scale}

F.demo_responder = responder

def conductor(k, messages, brain):
    ans = FC.demo_conductor(k, messages, brain)
    if k == "plan" and scenario == "hard_nohint":
        p = json.loads(ans["text"])
        for t in p["tasks"]:
            t["hint"] = ""
        ans = {"text": json.dumps(p)}
    return ans

stats = {"worker": 0, "conductor": 0, "usd": 0.0, "tokens_in": 0, "tokens_out": 0, "cache_read": 0, "kinds": []}
def dump():
    stats_path.write_text(json.dumps(stats))

class Brain(FC.ConductedFakeBrain):
    async def complete(self, *a, **kw):
        stats["worker"] += 1; dump()
        return await super().complete(*a, **kw)
    async def call_model(self, *a, **kw):
        r = await super().call_model(*a, **kw)
        c = self.calls[-1]
        stats["conductor"] += 1; stats["usd"] += c["usd"]; stats["tokens_in"] += c["tokens_in"]
        stats["tokens_out"] += c["tokens_out"]; stats["cache_read"] += c["cache_read"]; stats["kinds"].append(c["kind"])
        dump()
        return r

_dc = D.demo_context
def ctx_(paths, **kw):
    ctx = _dc(paths, **{"lean_seconds": 2.0 / scale, "swap_seconds": 0.0, **kw})
    b = Brain(paths.config / "cond", conductor=conductor, claude_key=(variant == "claude"), time_scale=1.0 / scale,
              local=ctx.local, delay=0.0)
    b.behaviour.update({"bad_statement": scenario == "bad_statement",
                        "fail_unless_hint": scenario in ("hard_proof", "hard_nohint")})
    ctx.brain = b
    return ctx
D.demo_context = ctx_
dump()
from madalean.cli import main
sys.exit(main(sys.argv[6:]))
'''


def call(base: str, method: str, path: str, body: dict | None = None) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(base + path, data=data, method=method, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read() or b"{}")


def one(root: Path, port: int, variant: str, scenario: str, runs: int, scale: float) -> list[dict]:
    tmp = Path(tempfile.mkdtemp(prefix="madalean-conductor-bench-"))
    env = {**os.environ, "PYTHONPATH": str(root.resolve()),
           "MADALEAN_CONFIG_DIR": str(tmp / "config"), "MADALEAN_CACHE_DIR": str(tmp / "cache"),
           "MADALEAN_NO_UPDATE_CHECK": "1", "MADALEAN_NO_SELFTEST": "1", "MADALEAN_NO_SYNTAX_BUILD": "1",
           "MADALEAN_NO_KEYRING": "1"}
    stats = tmp / "stats.json"
    args = ["serve", "--demo", "--port", str(port), "--remote-port", str(port + 1), "--no-migrate",
            "--config-dir", str(tmp / "config"), "--cache-dir", str(tmp / "cache")]
    log = open(tmp / "server.log", "w")
    proc = subprocess.Popen([sys.executable, "-c", LAUNCHER, str(scale), json.dumps(MEDIANS), variant, scenario,
                             str(stats), *args], cwd=str(root), env=env, stdout=log, stderr=subprocess.STDOUT)
    base = f"http://127.0.0.1:{port}"
    out = []
    try:
        for _ in range(300):
            try:
                call(base, "GET", "/api/hello")
                break
            except OSError:
                time.sleep(0.1)
        call(base, "PATCH", "/api/settings", {"conductor": variant != "off", "prove_attempts": 2,
                                              "prove_strategy": "goedel"})
        for _ in range(runs):
            before = json.loads(stats.read_text())
            r = call(base, "POST", "/api/dossiers", {"problem": PROBLEM})
            jid, did = r["job"]["id"], r["dossier"]["id"]
            while True:
                j = call(base, "GET", f"/api/jobs/{jid}")["job"]
                if j["state"] not in ("queued", "running"):
                    break
                time.sleep(0.05)
            d = call(base, "GET", f"/api/dossiers/{did}")["dossier"]
            after = json.loads(stats.read_text())
            proved = any(e["kind"] == "proof" for e in d.get("events") or [] if e.get("job") == jid)
            out.append({"variant": variant, "scenario": scenario, "state": j["state"], "proved": proved,
                        "job_s": round((j["ended"] - j["started"]) * scale, 1),
                        "worker_calls": after["worker"] - before["worker"],
                        "conductor_calls": after["conductor"] - before["conductor"],
                        "usd": round(after["usd"] - before["usd"], 5),
                        "tokens_in": after["tokens_in"] - before["tokens_in"],
                        "cache_read": after["cache_read"] - before["cache_read"],
                        "kinds": after["kinds"][len(before["kinds"]):],
                        "by": (j.get("conductor") or {}).get("name", "")})
    except Exception:
        log.flush()
        print((tmp / "server.log").read_text(errors="replace")[-3000:], file=sys.stderr)
        raise
    finally:
        proc.terminate()
        try:
            proc.wait(10)
        except subprocess.TimeoutExpired:
            proc.kill()
        shutil.rmtree(tmp, ignore_errors=True)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True, type=Path)
    ap.add_argument("--port", type=int, default=12100)
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--scale", type=float, default=20.0)
    ap.add_argument("--scenarios", default="ok,bad_statement,hard_proof,hard_nohint")
    ap.add_argument("--variants", default="off,claude,free")
    ap.add_argument("--json")
    a = ap.parse_args()
    rows = []
    port = a.port
    for sc in a.scenarios.split(","):
        for v in a.variants.split(","):
            rows += one(a.root, port, v, sc, a.runs, a.scale)
            port += 2
    print(f"{'scenario':14} {'variant':7} {'proved':>6} {'job s':>7} {'workers':>7} {'cond.':>5} {'USD':>8} "
          f"{'tok in':>7} {'cached':>7}  by / decisions")
    for sc in a.scenarios.split(","):
        for v in a.variants.split(","):
            rs = [r for r in rows if r["scenario"] == sc and r["variant"] == v]
            med = lambda k: statistics.median(r[k] for r in rs)  # noqa: E731
            print(f"{sc:14} {v:7} {sum(r['proved'] for r in rs):>3}/{len(rs):<2} {med('job_s'):>7.1f} "
                  f"{med('worker_calls'):>7.0f} {med('conductor_calls'):>5.0f} {med('usd'):>8.4f} "
                  f"{med('tokens_in'):>7.0f} {med('cache_read'):>7.0f}  {rs[-1]['by']} {rs[-1]['kinds']}")
    if a.json:
        Path(a.json).write_text(json.dumps(rows, indent=1))


if __name__ == "__main__":
    main()
