#!/usr/bin/env python3
"""Records the independent verification of a published Madalean project (run by verify-and-publish.yml).

Inputs: the `lake build` log, the output of `lake env lean Verify.lean` (one `#print axioms` per result the site calls
verified) and site/verification/expected.json (written by Madalean when publishing). Writes
site/verification/result.json and site/verification/badge.svg. Exit code 0 even on failure (the badge says it); the
workflow fails afterwards when --strict is given and the verdict is not "verified".

Verdict:
  verified  build OK, every expected result printed its axioms, all within the allowed (standard) axioms
  sorry     build OK but some declaration uses `sorry` (results the site does NOT call verified may)
  failed    build failed, an expected result is missing, or uses a non-standard axiom (incl. sorryAx)
Python 3.8+ stdlib only."""
import argparse
import datetime
import json
import re
import sys
from html import escape
from pathlib import Path

COLORS = {"verified": "#1a7246", "sorry": "#8a5200", "failed": "#b42318"}
TEXT = {"verified": "verified", "sorry": "builds, with sorry", "failed": "failing"}


def badge_svg(left, right, color):
    lw, rw = 8 + 7 * len(left), 8 + 7 * len(right)
    w = lw + rw
    return ('<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="20" role="img" aria-label="%s: %s">'
            '<title>%s: %s</title><rect width="%d" height="20" fill="#3b4252"/><rect x="%d" width="%d" height="20" fill="%s"/>'
            '<g fill="#fff" font-family="DejaVu Sans,Verdana,sans-serif" font-size="11">'
            '<text x="%s" y="14" text-anchor="middle">%s</text><text x="%s" y="14" text-anchor="middle">%s</text></g></svg>\n'
            % (w, escape(left), escape(right), escape(left), escape(right), lw, lw, rw, color, lw / 2, escape(left),
               lw + rw / 2, escape(right)))


def parse_axioms(text):
    """{name: [axioms]} from `#print axioms` output (Lean 4)."""
    out = {}
    for m in re.finditer(r"'([^']+)' depends on axioms: \[([^\]]*)\]", text):
        out[m.group(1)] = [a.strip() for a in m.group(2).split(",") if a.strip()]
    for m in re.finditer(r"'([^']+)' does not depend on any axioms", text):
        out[m.group(1)] = []
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", required=True)
    ap.add_argument("--build-outcome", required=True, help="success | failure")
    ap.add_argument("--build-log", required=True)
    ap.add_argument("--axioms-log", required=True)
    ap.add_argument("--toolchain", default="")
    ap.add_argument("--commit", default="")
    ap.add_argument("--run-url", default="")
    ap.add_argument("--strict", action="store_true")
    a = ap.parse_args()
    site = Path(a.site)
    vdir = site / "verification"
    vdir.mkdir(parents=True, exist_ok=True)
    expected = json.loads((vdir / "expected.json").read_text(encoding="utf-8"))
    log = Path(a.build_log).read_text(encoding="utf-8", errors="replace") if Path(a.build_log).exists() else ""
    axlog = Path(a.axioms_log).read_text(encoding="utf-8", errors="replace") if Path(a.axioms_log).exists() else ""
    sorry = len(re.findall(r"declaration uses 'sorry'", log))
    axioms = parse_axioms(axlog)
    allowed = set(expected.get("allowed_axioms") or ["propext", "Classical.choice", "Quot.sound"])
    problems = []
    for name in expected.get("verified", []):
        if name not in axioms:
            problems.append("%s: no axiom report (missing or does not compile)" % name)
        elif not set(axioms[name]) <= allowed:
            problems.append("%s: non-standard axioms %s" % (name, sorted(set(axioms[name]) - allowed)))
    if a.build_outcome != "success":
        verdict = "failed"
        problems.insert(0, "lake build failed")
    elif problems:
        verdict = "failed"
    elif sorry:
        verdict = "sorry"
    else:
        verdict = "verified"
    result = {
        "schema": "madalean-verification-result/1", "verdict": verdict,
        "checked_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "toolchain": a.toolchain.strip(), "commit": a.commit, "run_url": a.run_url,
        "sorry_warnings": sorry, "expected_verified": expected.get("verified", []), "axioms": axioms,
        "problems": problems,
    }
    (vdir / "result.json").write_text(json.dumps(result, indent=1) + "\n", encoding="utf-8")
    (vdir / "badge.svg").write_text(badge_svg("lake build", TEXT[verdict], COLORS[verdict]), encoding="utf-8")
    print("verdict: %s; %d sorry warning(s); %d problem(s)" % (verdict, sorry, len(problems)))
    for p in problems:
        print("  " + p)
    return 1 if (a.strict and verdict == "failed") else 0


if __name__ == "__main__":
    sys.exit(main())
