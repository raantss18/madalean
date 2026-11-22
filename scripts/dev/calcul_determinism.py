#!/usr/bin/env python3
"""S-AG (DECISIONS D39): measure the deterministic code generation of Calcul on ~30 typical requests.

For each request, written in two notations (« F_125 » / « GF(5^3) », plain / LaTeX…):
- analysis + catalogue / best-version time (no model; a fake model that answers differently EVERY time stands in
  for the model path, so any non-determinism would show);
- identical output: the two notations, and « Réécrire » (the same request twice), byte for byte;
- with `--sage`: the produced Sage code is RUN in the installed Sage (one process), « ran OK » counted.

Usage: PYTHONPATH=. .venv/bin/python scripts/dev/calcul_determinism.py [--sage] [--json out.json]
Nothing is written outside a temporary directory; no network, no real model."""
from __future__ import annotations

import argparse
import asyncio
import json
import random
import statistics
import subprocess
import sys
import tempfile
import time
import types
from pathlib import Path

from madalean import syntaxcards
from madalean.brain.fake import FakeBrain
from madalean.research import codecat, codegen
from madalean.research.recipes import RecipeStore

PAIRS: list[tuple[str, str]] = [
    ("factorise x^5+4x-1 dans F_125[x]", "factorise x^5 + 4*x - 1 dans GF(5^3)[x]"),
    ("les racines dans F_16 de x^5+x^3+x+1", "racines de x^5+x^3+x+1 dans \\mathbb{F}_{2^4}"),
    ("liste les polynômes irréductibles de degré 2 de F_9[X]", "liste les polynomes irreductibles de degre 2 de F_{3^2}[x]"),
    ("x^4+x+1 est-il irréductible dans F_2[x] ?", "x^4 + x + 1 est-il irreductible dans GF(2)[x] ?"),
    ("factorise x^4+4 dans Q[x]", "factorise x⁴+4 dans ℚ[x]"),
    ("factorise x^4+4 sur Z[i]", "factorise x^4 + 4 sur ℤ[i]"),
    ("pgcd de x^4-1 et x^6-1 dans Q[x]", "PGCD de x^4 - 1 et x^6 - 1 dans QQ[x]"),
    ("factorise 2024", "factoriser 2024"),
    ("les diviseurs de 360", "diviseurs de 360"),
    ("est-ce que 97 est premier ?", "97 est-il premier ?"),
    ("les 10 premiers nombres premiers", "donne les 10 premiers nombres premiers"),
    ("inverse de 3 modulo 7", "calcule l'inverse de 3 modulo 7"),
    ("les éléments inversibles de Z/12Z", "les éléments inversibles de ℤ/12ℤ"),
    ("un générateur de F_9", "un generateur de GF(9)"),
    ("intégrale de x^2 sin(x) entre 0 et pi", "intégrale de x² sin(x) entre 0 et π"),
    ("primitive de 1/(1+x^2)", "primitive de \\frac{1}{1+x^2}"),
    ("dérivée de x^3 e^{2x}", "dérivée de x^3*exp(2*x)"),
    ("limite de sin(x)/x en 0", "limite de \\frac{\\sin(x)}{x} en 0"),
    ("limite de (1+1/x)^x quand x tend vers l'infini", "limite de (1+1/x)^x en +∞"),
    ("somme pour k de 1 à n de k^2", "\\sum_{k=1}^{n} k^2"),
    ("développement limité de exp(x) à l'ordre 5 en 0", "taylor de e^x à l'ordre 5 en 0"),
    ("résous x^2-2=0", "résoudre x² - 2 = 0"),
    ("simplifie (x^2-1)/(x-1)", "simplifie \\frac{x^2-1}{x-1}"),
    ("trace sin(x)/x sur [-10,10]", "trace sin(x)/x entre -10 et 10"),
    ("déterminant de [[1,2],[3,4]]", "déterminant de \\begin{pmatrix} 1 & 2 \\\\ 3 & 4 \\end{pmatrix}"),
    ("valeurs propres de [[2,1],[1,2]]", "valeurs propres de la matrice [[2, 1], [1, 2]]"),
    ("ordre du groupe symétrique S_5", "ordre de S_{5}"),
    ("nombre de points de la courbe elliptique y^2 = x^3 + x + 1 sur F_7",
     "nombre de points de la courbe elliptique y² = x³ + x + 1 sur GF(7)"),
    ("nombre de classes de Q(sqrt(-5))", "nombre de classes de ℚ(√-5)"),
    ("étudie les variations de f(x)=x*exp(-2x)+exp(x)", "étudie les variations de f(x) = x exp(-2x) + exp(x)"),
    ("la clôture algébrique de F_125 et ses automorphismes", "la cloture algebrique de F_{5^3} et ses automorphismes"),
]


def varying(role, messages, brain):
    n = random.randint(0, 10 ** 9)
    return f"```\nr_{n} = {n}\nr_{n}\n```"


async def main(args) -> dict:
    tmp = Path(tempfile.mkdtemp(prefix="calcul-det-"))
    syntaxcards.configure(Path.home() / ".cache" / "madalean") if args.user_cache else syntaxcards.configure(tmp)
    if args.build:
        codecat.build("sage")
    ctx = types.SimpleNamespace(brain=FakeBrain(varying), settings=types.SimpleNamespace(mode="online", prefer={}),
                                local=types.SimpleNamespace(release_owner=lambda o: None), spawn=lambda c: None)
    store = RecipeStore(tmp / "recipes.json")
    rows = []
    for a, b in PAIRS:
        times = []
        outs = []
        for text in (a, a, b):          # first ask, « Réécrire », the other notation
            t0 = time.perf_counter()
            r = await codegen.transcribe(ctx, language=args.language, prompt=text, names=[], context="", owner="m",
                                         recipes=store)
            times.append(time.perf_counter() - t0)
            outs.append(r)
        rows.append({"request": a, "other": b, "origin": outs[0]["origin"], "coverage": outs[0]["coverage"],
                     "recognized": (outs[0]["recognized"] or {}).get("fr", ""),
                     "same_rewrite": outs[0]["code"] == outs[1]["code"],
                     "same_notation": outs[0]["code"] == outs[2]["code"],
                     "seconds": [round(t, 3) for t in times], "code": outs[0]["code"]})
    models = len(ctx.brain.requests)
    ran = None
    if args.sage and args.language == "sage":
        py = syntaxcards.sage_python()
        req = {"samples": [[f"m{i}", r["code"], "True"] for i, r in enumerate(rows) if r["code"]], "timeout": 60}
        p = subprocess.run([py, "-I", "-c", codecat._RUN_SAGE], input=json.dumps(req), capture_output=True, text=True,
                           timeout=900, env=syntaxcards._sage_env(tmp / "work"))
        res = json.loads(p.stdout.split("MADALEAN_CODECAT ", 1)[1])
        for i, r in enumerate(rows):
            r["ran"] = res.get(f"m{i}", "skipped")
        ran = sum(1 for r in rows if r.get("ran") == "")
    first = [r["seconds"][0] for r in rows]
    again = [r["seconds"][1] for r in rows]
    summary = {
        "requests": len(rows), "catalogue_full": sum(r["coverage"] == "full" for r in rows),
        "partial": sum(r["coverage"] == "partial" for r in rows), "model_calls": models,
        "identical_rewrite": sum(r["same_rewrite"] for r in rows),
        "identical_other_notation": sum(r["same_notation"] for r in rows),
        "first_median_ms": round(statistics.median(first) * 1000, 1), "first_max_ms": round(max(first) * 1000, 1),
        "rewrite_median_ms": round(statistics.median(again) * 1000, 1), "ran_ok_in_sage": ran,
    }
    return {"summary": summary, "rows": rows}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--sage", action="store_true", help="run the produced code in the installed Sage")
    ap.add_argument("--build", action="store_true", help="build the catalogue first (verified entries only)")
    ap.add_argument("--user-cache", action="store_true", help="read the syntax card / catalogue from ~/.cache")
    ap.add_argument("--json", default="")
    ap.add_argument("--language", default="sage", choices=["sage", "python"])
    a = ap.parse_args()
    out = asyncio.run(main(a))
    for r in out["rows"]:
        print(f"{r['coverage']:8} {r['origin']:9} rew={'=' if r['same_rewrite'] else '≠'} "
              f"not={'=' if r['same_notation'] else '≠'} {r['seconds']} {r.get('ran', '')!s:.40} | {r['request'][:60]}")
    print(json.dumps(out["summary"], indent=1))
    if a.json:
        Path(a.json).write_text(json.dumps(out, ensure_ascii=False, indent=1))
    sys.exit(0)
