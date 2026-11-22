#!/usr/bin/env python3
"""Time to the first proof attempt, measured on a `madalean serve --demo` server (scripted models, simulated Lean)
started from a given source tree with throw-away config / cache directories (S-AF, docs/PERFORMANCE.md).

    perf_stages_demo.py --root <source tree> --port 11800 [--runs 5] [--set parallel_stages=false] [--json out.json]

For each run: a new dossier from the same problem, then from the job record: statement accepted → first proof
attempt, → proof verified, and the whole job. Works with servers that do not write `timings` (older code): the
times come from the attempts and the thread events."""
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

# `--realistic SCALE`: the scripted models answer after the MEDIAN time measured per stage on the user's real dossiers
# (bench/perf_baseline_2.0.json, docs/PERFORMANCE.md), divided by SCALE; the simulated Lean takes 2 s / SCALE per
# check (warm lean-prover49). The statement check's model says « fidèle ». Works with any source tree: the launcher
# only wraps the demo's scripted responder before the server starts.
MEDIANS = {"understand": 4.7, "formalize": 34.7, "notes": 48.8, "fidelity": 39.6, "prove": 15.0,
           "explanation": 21.0, "informal": 2.8}
LAUNCHER = r'''
import json, sys
import madalean.brain.fake as F
import madalean.demo as D
scale = float(sys.argv[1])
med = json.loads(sys.argv[2])
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
    if k == "fidelity":
        ans = json.dumps({"verdict": "faithful", "summary": "OK", "issues": [], "counterexamples": []})
    else:
        ans = orig(role, messages, brain)
    d = ans if isinstance(ans, dict) else {"text": ans}
    return {**d, "delay": med.get(k, 0.0) / scale}

F.demo_responder = responder
try:      # older trees: the Calcul demo answered the guided-reading prompt with an empty text (fixed by S-AF)
    import madalean.server.plugins.workbench as W
    _da = W.demo_answer
    W.demo_answer = lambda first: (lambda r: None if r == "" else r)(_da(first))
except Exception:
    pass
_dc = D.demo_context
D.demo_context = lambda paths, **kw: _dc(paths, **{"lean_seconds": 2.0 / scale, "swap_seconds": 0.0, **kw})
from madalean.cli import main
sys.exit(main(sys.argv[3:]))
'''


def call(base: str, method: str, path: str, body: dict | None = None) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(base + path, data=data, method=method, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read() or b"{}")


def measure(job: dict, dossier: dict) -> dict:
    atts = job.get("attempts") or []
    ev = [e for e in dossier.get("events") or [] if e.get("job") == job["id"]]
    # statement accepted = its thread event (same clock for every version of the server)
    t_stmt = next((e["t"] for e in ev if e["kind"] == "statement"), job["started"])
    first = min((a["t"] for a in atts if a["stage"] == "proof"), default=None)
    proof_t = next((e["t"] for e in ev if e["kind"] == "proof"), None)
    return {"first_attempt_s": round(first - t_stmt, 2) if first else None,
            "proof_verified_s": round(proof_t - t_stmt, 2) if proof_t else None,
            "job_s": round(job["ended"] - job["started"], 2), "state": job["state"],
            "done_stages": job.get("done_stages"),
            "thread": [e["kind"] for e in dossier.get("events") or []],
            "timeline": sorted([(round(e["t"] - t_stmt, 2), "event", e["kind"]) for e in ev] +
                               [(round(x["t"] - t_stmt, 2), "attempt", f"{x['stage']}/{x['kind']}") for x in atts]),
            "stages_at_once": max((len(set(x)) for x in [[r["stage"] for r in job.get("timings") or []
                                                         if r["start"] <= t <= (r["end"] or t)]
                                                        for t in [r["start"] for r in job.get("timings") or []]]),
                                  default=1)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True, type=Path)
    ap.add_argument("--port", type=int, default=11800)
    ap.add_argument("--runs", type=int, default=5)
    ap.add_argument("--set", action="append", default=[], help="setting=value (JSON value) patched before the runs")
    ap.add_argument("--realistic", type=float, default=0.0, metavar="SCALE",
                    help="scripted models answer after the real median per stage / SCALE")
    ap.add_argument("--json")
    a = ap.parse_args()
    tmp = Path(tempfile.mkdtemp(prefix="madalean-perf-demo-"))
    env = {**os.environ, "PYTHONPATH": str(a.root.resolve())}
    # set here, not only by --config-dir: the launcher imports madalean before the command line is read
    env["MADALEAN_CONFIG_DIR"], env["MADALEAN_CACHE_DIR"] = str(tmp / "config"), str(tmp / "cache")
    log = open(tmp / "server.log", "w")
    args = ["serve", "--demo", "--port", str(a.port), "--remote-port", str(a.port + 1), "--no-migrate",
            "--config-dir", str(tmp / "config"), "--cache-dir", str(tmp / "cache")]
    cmd = [sys.executable, "-c", LAUNCHER, str(a.realistic), json.dumps(MEDIANS), *args] if a.realistic \
        else [sys.executable, "-m", "madalean", *args]
    proc = subprocess.Popen(cmd, cwd=str(a.root), env=env, stdout=log, stderr=subprocess.STDOUT)
    base = f"http://127.0.0.1:{a.port}"
    out = []
    try:
        for _ in range(200):
            try:
                call(base, "GET", "/api/hello")
                break
            except OSError:
                time.sleep(0.1)
        patch = {}
        for kv in a.set:
            k, v = kv.split("=", 1)
            patch[k] = json.loads(v)
        if patch:
            call(base, "PATCH", "/api/settings", patch)
        for _ in range(a.runs):
            r = call(base, "POST", "/api/dossiers", {"problem": PROBLEM})
            jid, did = r["job"]["id"], r["dossier"]["id"]
            while True:
                j = call(base, "GET", f"/api/jobs/{jid}")["job"]
                if j["state"] not in ("queued", "running"):
                    break
                time.sleep(0.1)
            d = call(base, "GET", f"/api/dossiers/{did}")["dossier"]
            out.append(measure(j, d))
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
    for k in ("first_attempt_s", "proof_verified_s", "job_s"):
        xs = [x[k] for x in out if x[k] is not None]
        print(f"{k:18} median {statistics.median(xs):6.2f} s   runs {xs}")
    print("states", [x["state"] for x in out], "stages at once", [x["stages_at_once"] for x in out])
    if a.json:
        Path(a.json).write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
