"""From a Lean statement to certificate tasks (session S-AT, DECISIONS D52).

`read` splits `theorem n BINDERS : GOAL := by sorry` into number variables, hypotheses and a goal, when all of it is
in the small arithmetic language of expr.py. `tasks` then lists the certificate kinds whose shape matches, in the
order they are tried. A task carries the request for the Sage producer (None for the kinds Lean checks directly)
and what the renderer needs. Statements outside these shapes give no task: they go to the usual provers."""
from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from fractions import Fraction

from ..pipeline import probes as P
from . import expr as E
from . import poly as Y
from . import pratt

MAX_VARS = 8
MAX_HYPS = 12
SOS_MAX_VARS, SOS_MAX_DEGREE = 4, 8
IDEAL_MAX_DEGREE = 12
FINITE_MAX_POINTS = 4000
SEARCH_BOX = 2_000_000           # points tried at most by the producer's bounded search
NUMERIC_DIGITS = {"sqrt": 9, "exp1": 9, "log2": 9}


@dataclass
class Hyp:
    name: str
    prop: tuple


@dataclass
class Problem:
    name: str
    vars: dict[str, str]                 # variable -> domain (N, Z, Q, R), binders first, then introduced ones
    hyps: list[Hyp]
    goal: tuple                          # after `intro`: no leading ∀ / →
    goal0: tuple                         # as written
    intros: list[str] = field(default_factory=list)
    outer: int = 0                       # number of variables that come from the theorem's binders
    unread: int = 0                      # binders that were not understood (never used; no refutation then)


@dataclass
class Task:
    kind: str
    request: dict | None = None          # for the producer (Sage); None: nothing to compute
    data: dict = field(default_factory=dict)
    refuted: str = ""                    # the claim is false: a witness in plain text (no proof is attempted)


def read(statement: str) -> Problem | None:
    sig = P.split_statement(statement)
    if sig is None:
        return None
    vars_: dict[str, str] = {}
    hyps: list[Hyp] = []
    unread = 0
    for name, typ in P.explicit_binders(sig.binders):
        t = typ.strip()
        if t in E.TYPES:
            vars_[name] = E.TYPES[t]
            continue
        try:
            hyps.append(Hyp(name, E.parse_prop(t)))
        except E.Unsupported:
            unread += 1                  # a binder we do not read (a type, a function…): simply not used
    try:
        goal0 = E.parse_prop(sig.concl)
    except (E.Unsupported, RecursionError):
        return None
    outer = len(vars_)
    goal, intros, k = goal0, [], 0
    while goal[0] in ("forall", "imp"):
        if goal[0] == "forall":
            for n, t in goal[1]:
                if n in vars_ or any(h.name == n for h in hyps):
                    return None          # shadowing: not worth the risk
                vars_[n] = t
                intros.append(n)
            goal = goal[2]
        else:
            k += 1
            name = f"hc{k}"
            while name in vars_ or any(h.name == name for h in hyps):
                name += "'"
            hyps.append(Hyp(name, goal[1]))
            intros.append(name)
            goal = goal[2]
    if len(vars_) > 3 * MAX_VARS or len(hyps) > 4 * MAX_HYPS:
        return None
    return Problem(sig.name, vars_, hyps, goal, goal0, intros, outer, unread)


# ---------------------------------------------------------------- helpers
def _atoms(p):
    """Atomic propositions of a quantifier-free proposition."""
    if p[0] in ("not",):
        yield from _atoms(p[1])
    elif p[0] in ("and", "or", "imp", "iff"):
        yield from _atoms(p[1])
        yield from _atoms(p[2])
    elif p[0] in ("exists", "forall", "ball"):
        raise E.Unsupported("nested quantifier")
    else:
        yield p


def _uniform(p, env: dict[str, str]) -> str:
    """The single number domain of a quantifier-free proposition (each atom is checked); '' when it has none."""
    doms = set()
    default = next(iter(set(env.values())), "N") if len(set(env.values())) == 1 else "N"
    for a in _atoms(p):
        if a[0] in ("true", "false"):
            continue
        doms.add(E.domain(a, env, default))
    if len(doms) > 1:
        raise E.Unsupported("mixed number types")
    return doms.pop() if doms else default


def _flatten(p, head: str) -> tuple[list[tuple[str, str]], tuple]:
    groups: list[tuple[str, str]] = []
    while p[0] == head:
        groups += [(n, t) for n, t in p[1]]
        p = p[2]
    return groups, p


def _closed(e) -> bool:
    return not E.variables(e)


# ---------------------------------------------------------------- tasks
def tasks(pb: Problem) -> list[Task]:
    out: list[Task] = []
    for fn in (_closed_tasks, _finite_task, _open_tasks):
        try:
            out += fn(pb)
        except (E.Unsupported, RecursionError, ZeroDivisionError, OverflowError):
            continue
    if pb.hyps or pb.unread:             # a claim under hypotheses is never called false from its conclusion alone
        out = [t for t in out if not t.refuted]
    return out


def _closed_tasks(pb: Problem) -> list[Task]:
    g = pb.goal0
    if E.variables(g) or g[0] in ("true", "false"):
        return []
    h = g[0]
    if h == "prime":
        n = E.evaluate(g[1], E.domain(g, {}))
        if not E.is_prime(n):
            d = next((k for k in range(2, 100000) if n % k == 0), 0) if n > 1 else 0
            return [Task("prime", refuted=f"{n} = {d} × {n // d}" if d and d < n else f"{n}")]
        if n < pratt.SMALL:
            return [Task("prime", None, {"n": n, "expr": g[1]})]
        if n.bit_length() > pratt.MAX_BITS:
            return []
        return [Task("prime", {"kind": "pratt", "n": str(n), "small": pratt.SMALL}, {"n": n, "expr": g[1]})]
    if h == "not" and g[1][0] == "prime":
        n = E.evaluate(g[1][1], E.domain(g[1], {}))
        if n < 2:
            return [Task("arith", None, {})]
        if E.is_prime(n):
            return []
        return [Task("composite", {"kind": "factor", "n": str(n)}, {"n": n, "expr": g[1][1]})]
    if h == "exists":
        groups, body = _flatten(g, "exists")
        return _search_task("exists", groups, body)
    if h == "not" and g[1][0] == "forall":
        groups, body = _flatten(g[1], "forall")
        return _search_task("counterexample", groups, ("not", body))
    if h in ("forall", "ball"):
        return []
    dom = _uniform(g, {})
    if E.calls(g) & E.REAL_ONLY:
        return _numeric_task(g)
    pm = _powmod(g)
    if pm is not None:
        return [pm]
    try:
        ok = E.holds(g, dom)
    except E.TooBig:
        return []
    if not ok:
        return [Task("arith", refuted="false")]
    return [Task("arith", None, {})]


def _powmod(g) -> Task | None:
    """`a ^ e % n = r` and `a ^ e ≡ r [MOD n]` in ℕ, when a ^ e is too large to be computed."""
    if g[0] == "rel" and g[1] == "=" and g[2][0] == "mod" and g[2][1][0] == "pow":
        base, e, n, r, form = g[2][1][1], g[2][1][2], g[2][2], g[3], "mod"
    elif g[0] == "modeq" and g[1] == "MOD" and g[3][0] == "pow":
        base, e, n, r, form = g[3][1], g[3][2], g[2], g[4], "modeq"
    else:
        return None
    if E.domain(g, {}) != "N" or base[0] != "num" or n[0] != "num" or E.casts(g):
        return None
    a, m = int(base[1]), int(n[1])
    ev = E.evaluate(e, "N")
    if m < 1 or ev < 1 or ev.bit_length() > 4000 or ev * max(1, a.bit_length()) <= 200:
        return None                      # small powers: plain arithmetic
    rv = E.evaluate(r, "N")
    val = pow(a, ev, m)
    if (rv % m if form == "modeq" else rv) != val:
        return Task("powmod", refuted=f"{a}^{ev} mod {m} = {val}")
    return Task("powmod", None, {"a": a, "e": e, "ev": ev, "n": m, "r": val, "form": form})


def _search_task(kind: str, groups: list[tuple[str, str]], body) -> list[Task]:
    if not groups or len(groups) > 4 or len({n for n, _t in groups}) != len(groups):
        return []
    env = dict(groups)
    dom = _uniform(body, env)
    if set(env.values()) != {dom} or (E.calls(body) & E.REAL_ONLY):
        return []
    return [Task(kind, {"kind": "exists", "vars": [[n, t] for n, t in groups], "dom": dom,
                        "body": E.strip_casts(body), "box": SEARCH_BOX},
                 {"vars": groups, "dom": dom})]


def _numeric_task(g) -> list[Task]:
    """A closed real inequality between rational expressions of √q, π, exp 1 and log 2."""
    if g[0] != "rel" or g[1] in ("=", "!="):
        return []
    atoms: list[tuple] = []
    for x in E.walk(g):
        if x[0] == "call" and x[1] in E.REAL_ONLY and x not in atoms:
            atoms.append(x)
    spec = []
    for a in atoms:
        if a[1] == "pi":
            spec.append({"f": "pi"})
            continue
        arg = a[2][0]
        if E.calls(arg) or E.variables(arg):
            raise E.Unsupported("nested function")
        v = E.evaluate(E.strip_casts(arg), "R")
        if a[1] == "sqrt" and v >= 0:
            spec.append({"f": "sqrt", "arg": [v.numerator, v.denominator]})
        elif a[1] == "exp" and v == 1:
            spec.append({"f": "exp1"})
        elif a[1] == "log" and v == 2:
            spec.append({"f": "log2"})
        else:
            raise E.Unsupported("function value without a known bound")
    if not atoms or len(atoms) > 6:
        return []
    return [Task("numeric", {"kind": "numeric", "prop": _abstract(E.strip_casts(g), [E.strip_casts(a) for a in atoms]),
                             "atoms": spec}, {"atoms": atoms})]


def _abstract(e, atoms: list):
    """The proposition with each function value replaced by a variable `t<i>` (the producer bounds them)."""
    if e in atoms:
        return ("var", f"t{atoms.index(e)}")
    if e[0] in ("num", "var"):
        return e
    if e[0] == "call":
        return ("call", e[1], [_abstract(a, atoms) for a in e[2]])
    if e[0] == "rel":
        return ("rel", e[1], _abstract(e[2], atoms), _abstract(e[3], atoms))
    return (e[0], *[_abstract(c, atoms) for c in e[1:]])


def _finite_task(pb: Problem) -> list[Task]:
    """∀ over natural numbers below explicit bounds: checked here point by point first (a false claim is reported
    with its counterexample), then by Lean's `decide`."""
    g = pb.goal0
    if pb.outer or g[0] not in ("ball", "forall"):
        return []
    bounds: list[tuple[str, int]] = []
    form = "ball" if g[0] == "ball" else "imp"
    if form == "ball":
        while g[0] == "ball":
            hi = E.evaluate(g[4], "N")
            bounds.append((g[1], hi if g[3] == "<" else hi + 1))
            g = g[5]
    else:
        groups, g = _flatten(g, "forall")
        if any(t != "N" for _n, t in groups):
            return []
        names = [n for n, _t in groups]
        found: dict[str, int] = {}
        while g[0] == "imp" and len(found) < len(names):
            a = g[1]
            if not (a[0] == "rel" and a[1] in ("<", "<=") and a[2][0] == "var" and a[2][1] in names
                    and a[2][1] not in found and _closed(a[3])):
                break
            hi = E.evaluate(a[3], "N")
            found[a[2][1]] = hi if a[1] == "<" else hi + 1
            g = g[2]
        if set(found) != set(names):
            return []
        bounds = [(n, found[n]) for n in names]
    if not bounds or len(bounds) > 3:
        return []
    env = {n: "N" for n, _ in bounds}
    if _uniform(g, env) != "N" or set(E.variables(g)) - set(env):
        return []
    points = 1
    for _n, hi in bounds:
        points *= max(1, hi)
    if points > FINITE_MAX_POINTS:
        return []
    names = [n for n, _ in bounds]
    for vals in itertools.product(*[range(hi) for _n, hi in bounds]):
        if not E.holds(g, "N", dict(zip(names, vals))):
            return [Task("finite", refuted=", ".join(f"{n} = {v}" for n, v in zip(names, vals)))]
    return [Task("finite", None, {"bounds": bounds, "form": form, "points": points})]


def _rel_poly(prop, names: list[str], dom: str):
    """(op, g) with the relation written `g op 0`, op in >=, >, =; None when it is not a polynomial relation."""
    if prop[0] != "rel" or prop[1] == "!=":
        return None
    try:
        a, b = Y.of_term(prop[2], names, dom), Y.of_term(prop[3], names, dom)
    except E.Unsupported:
        return None
    op = prop[1]
    if op in ("<", "<="):
        return (">" if op == "<" else ">="), Y.add(b, a, -1)
    return op, Y.add(a, b, -1)


def _open_tasks(pb: Problem) -> list[Task]:
    g = pb.goal
    if not pb.vars or g[0] not in ("rel", "false"):
        return []
    used = E.variables(g)
    for h in pb.hyps:
        for v in E.variables(h.prop):
            if v not in used:
                used.append(v)
    names = [v for v in pb.vars if v in used]
    if not names or len(names) > MAX_VARS or any(v not in pb.vars for v in used):
        return []
    doms = {pb.vars[v] for v in names}
    if len(doms) != 1:
        return []
    dom = doms.pop()
    env = {v: dom for v in names}
    if g[0] == "rel" and E.domain(g, env, dom) != dom:
        return []
    hyps = []                            # (hyp, op, poly) for the hypotheses that are polynomial relations
    for h in pb.hyps[:4 * MAX_HYPS]:
        try:
            if h.prop[0] != "rel" or E.domain(h.prop, env, dom) != dom:
                continue
        except E.Unsupported:
            continue
        r = _rel_poly(h.prop, names, dom)
        if r is not None:
            hyps.append((h, r[0], r[1]))
    hyps = hyps[:MAX_HYPS]
    n = len(names)
    out: list[Task] = []
    goal = _rel_poly(g, names, dom) if g[0] == "rel" else None
    if g[0] == "rel" and goal is None:
        return []
    base = {"names": names, "dom": dom}
    if goal is not None and goal[0] == "=":
        if not goal[1]:
            return [Task("identity", None, base)]
        eqs = [(h, p) for h, op, p in hyps if op == "=" and p]
        if eqs and dom in ("Z", "Q", "R") and max(Y.degree(p) for _h, p in eqs + [(None, goal[1])]) <= IDEAL_MAX_DEGREE:
            out.append(Task("ideal", {"kind": "ideal", "ring": "ZZ" if dom == "Z" else "QQ", "n": n,
                                      "gens": [Y.to_wire(p) for _h, p in eqs], "target": Y.to_wire(goal[1])},
                            {**base, "hyps": [h.name for h, _p in eqs]}))
        if not out and not hyps and dom != "N":
            point = _refute_identity(goal[1], names)
            if point:
                out.append(Task("identity", refuted=point))
        return out
    rel = [(h, op, p) for h, op, p in hyps if p]
    degs = [Y.degree(p) for _h, _op, p in rel] + ([Y.degree(goal[1])] if goal else [])
    if goal is None and not rel:
        return []
    if max(degs, default=0) <= 1:
        out.append(Task("linear", {"kind": "linear", "n": n,
                                   "hyps": [{"op": op, "poly": Y.to_wire(p)} for _h, op, p in rel],
                                   "goal": {"op": goal[0], "poly": Y.to_wire(goal[1])} if goal else None},
                        {**base, "hyps": [h.name for h, _op, _p in rel]}))
    elif goal is not None and dom in ("R", "Q") and n <= SOS_MAX_VARS and max(degs) <= SOS_MAX_DEGREE:
        ineq = [(h, op, p) for h, op, p in rel if op in (">=", ">")][:6]
        out.append(Task("sos", {"kind": "sos", "n": n, "target": Y.to_wire(goal[1]), "strict": goal[0] == ">",
                                "hyps": [Y.to_wire(p) for _h, _op, p in ineq]},
                        {**base, "hyps": [(h.name, h.prop) for h, _op, _p in ineq], "goal": g}))
    return out


def _refute_identity(p: Y.Poly, names: list[str]) -> str:
    """A point where a non-zero polynomial does not vanish (a polynomial that is not zero is not an identity)."""
    for vals in itertools.product((1, 2, 0, -1, 3), repeat=len(names)):
        v = Fraction(0)
        for m, c in p.items():
            t = c
            for x, e in zip(vals, m):
                t *= Fraction(x) ** e
            v += t
        if v:
            return ", ".join(f"{n} = {x}" for n, x in zip(names, vals))
    return ""
