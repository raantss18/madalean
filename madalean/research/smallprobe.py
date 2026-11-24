"""Small-instance counterexample probes for the problem graph (session S-BA, DECISIONS D59).

Before a new lemma is expanded or attempted, its statement is evaluated on small values when it is decidable there:
number variables over ℕ / ℤ (a box of small values), polynomial relations over ℚ / ℝ in a few variables (small and
seeded pseudo-random rationals), hypotheses checked first. Everything here is Madalean's own deterministic code —
the certificates' reader and exact evaluator (`certs/problem.py`, `certs/evalcore.py`: the same Lean conventions as
the `finite` and `counterexample` certificate kinds); no model-written code runs. A point that violates the statement
is only a *candidate*: `lean_tactics` turns it into a proof of the negation that Lean must accept (strictly) before
the lemma is called refuted. When nothing is found, the tested ranges are kept on the node as evidence for its
viability (« testé sur … »). Budgeted in time and points, and cancellable through `should_stop`."""
from __future__ import annotations

import itertools
import random
import time
from fractions import Fraction

from ..certs import expr as E
from ..certs import problem as C
from ..pipeline import probes as P

MAX_POINTS = 20000
MAX_VARS = 4
INT_RADIUS = 12                    # ℕ: 0..12, ℤ: −12..12 (shrunk with more variables)
RAT_SMALL = [Fraction(v) for v in (0, 1, -1, 2, -2, 3, -3)] + [Fraction(1, 2), Fraction(-1, 2), Fraction(1, 3),
                                                               Fraction(-1, 3), Fraction(3, 2), Fraction(-3, 2)]
RAT_RANDOM = 400                   # seeded random rational points after the small grid (ℚ / ℝ)


def _values(dom: str, nvars: int) -> list:
    if dom in ("N", "Z"):
        r = max(2, min(INT_RADIUS, int(MAX_POINTS ** (1 / max(1, nvars))) // (1 if dom == "N" else 2)))
        vals = list(range(0, r + 1)) if dom == "N" else sorted(range(-r, r + 1), key=lambda v: (abs(v), v < 0))
        return vals
    k = max(3, min(len(RAT_SMALL), int(MAX_POINTS ** (1 / max(1, nvars)))))
    return RAT_SMALL[:k]


def _range_text(dom: str, vals: list) -> str:
    if dom in ("N", "Z"):
        return f"{min(vals)}..{max(vals)}"
    return f"{len(vals)} small rationals"


def search(statement: str, *, seconds: float = 2.0, should_stop=None, seed: int = 0) -> dict | None:
    """Evaluate `statement` (a full `theorem … := by sorry` with its header) on small instances.
    Returns None when it is not decidable that way; else {"found": bool, "witness": {var: value} (when found),
    "dom", "points", "tested": human-readable ranges, "complete": bool (the whole box was covered)}."""
    pb = C.read(statement)
    if pb is None or pb.unread or not pb.vars or len(pb.vars) > MAX_VARS:
        return None
    props = [h.prop for h in pb.hyps] + [pb.goal]
    try:
        for p in props:
            list(C._atoms(p))                           # quantifier-free after the intros
        doms = {E.domain(p, pb.vars, next(iter(pb.vars.values()))) for p in props if p[0] not in ("true", "false")}
    except (E.Unsupported, RecursionError):
        return None
    if len(set(pb.vars.values())) != 1 or len(doms) > 1:
        return None
    dom = next(iter(pb.vars.values()))
    if doms and doms != {dom}:
        return None
    if any(E.calls(p) & E.REAL_ONLY for p in props):
        return None
    names = list(pb.vars)
    vals = _values(dom, len(names))
    deadline = time.monotonic() + max(0.05, seconds)
    stop = should_stop or (lambda: False)
    points, complete = 0, True

    def check(env: dict) -> bool | None:
        """True: a counterexample; False: fine (or hypotheses false); None: not evaluable here."""
        try:
            if not all(E.holds(h.prop, dom, env) for h in pb.hyps):
                return False
            return not E.holds(pb.goal, dom, env)
        except (E.TooBig, ZeroDivisionError, OverflowError, ValueError):
            return False
        except E.Unsupported:
            return None

    grid = sorted(itertools.product(vals, repeat=len(names)), key=lambda t: sum(abs(x) for x in t))
    if len(grid) > MAX_POINTS:
        grid = grid[:MAX_POINTS]
        complete = False
    extra: list = []
    if dom in ("Q", "R"):
        rnd = random.Random(seed or 1729)
        extra = [tuple(Fraction(rnd.randint(-40, 40), rnd.randint(1, 12)) for _ in names) for _ in range(RAT_RANDOM)]
    for k, point in enumerate(grid + extra):
        if k % 64 == 0 and (time.monotonic() > deadline or stop()):
            complete = False
            break
        env = dict(zip(names, point))
        r = check(env)
        points += 1
        if r is None:
            return None
        if r:
            return {"found": True, "witness": env, "dom": dom, "points": points, "names": names,
                    "intros": list(pb.intros), "tested": _tested_text(names, dom, vals, len(extra), points)}
    return {"found": False, "dom": dom, "points": points, "complete": complete and dom in ("N", "Z"),
            "tested": _tested_text(names, dom, vals, len(extra), points)}


def _tested_text(names: list[str], dom: str, vals: list, nrand: int, points: int) -> str:
    rng = _range_text(dom, vals)
    s = ", ".join(f"{n} ∈ {rng}" for n in names)
    if nrand:
        s += f" + {nrand} random rationals"
    return s + f" ({points})"


def lean_tactics(statement: str, found: dict) -> list[str]:
    """Tactic scripts proving `¬ (∀ BINDERS, GOAL)` from the witness: specialise the statement at the witness, each
    hypothesis discharged by `decide` / `norm_num`, then the false instance closed. Lean has the last word."""
    sig = P.split_statement(statement)
    if sig is None:
        return []
    w = found["witness"]
    dom = found["dom"]
    from .proofgraph import binder_groups
    parsed = binder_groups(sig.binders + " : True")
    if parsed is None:
        return []
    named, positional = [], []
    disc = "(by first | decide | norm_num | positivity | omega)"
    for bracket, ns, _typ in parsed[0]:
        if bracket == "[":
            continue
        for n in ns:
            if n in w:
                if bracket == "(":
                    positional.append(E.lean_number(w[n], dom))
                else:
                    named.append(f"({n} := {E.lean_number(w[n], dom)})")
            elif bracket == "(":
                positional.append(disc)
            else:
                return []                                # an implicit binder that is not a number variable
    for n in found.get("intros") or []:
        positional.append(E.lean_number(w[n], dom) if n in w else disc)
    app = " ".join(named + positional)
    close = "first\n  | (norm_num at this; done)\n  | (simp at this; done)\n  | omega\n  | exact absurd this (by decide)"
    return [f"intro h\nhave := h {app}\n{close}" if app else f"intro h\nhave := h\n{close}"]


def witness_text(found: dict) -> str:
    return ", ".join(f"{n} = {v}" for n, v in found["witness"].items())
