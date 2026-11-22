"""Catalogue of canonical code structures for the Calcul screen (session S-AG, DECISIONS D39).

For every mathematical object and operation that `intent.py` recognizes, ONE canonical construction per tool:

| object            | SageMath                          | Python (sympy / numpy / matplotlib)   | Lean 4 / Mathlib           |
|-------------------|-----------------------------------|---------------------------------------|----------------------------|
| F_q, q = p^k      | `F125.<a> = GF(5^3)`              | prime fields only: `modulus=p`        | `GaloisField 5 3`          |
| Z/nZ              | `Z12 = Zmod(12)`                  | integers mod n                        | `ZMod 12`                  |
| K[x], K[x, y]     | `R.<x> = PolynomialRing(K)`       | `Poly(f, x, modulus=p)` / `factor`    | `Polynomial K`, `MvPolynomial (Fin 2) K` |
| …                 |                                   |                                       |                            |

(the whole table: `entries()`, served by `GET /api/calcul/catalogue`). Naming conventions: a finite field is
`F<q>` with generator `a` (`b`, `c`… for the next ones), Z/nZ is `Z<n>`, the polynomial ring `R` (variables as
written in the request, lowercase when the formula is), a number field `K`, a matrix `M`, a group `G`, a curve `E`,
the polynomial `f` (`g` for the second one), symbolic variables declared explicitly (`x = var('x')` in Sage,
`x = symbols('x')` in Python: a cell never relies on a name an earlier cell may have changed). Python cells import
every name they use (explicit `from sympy import …`, sorted; `numpy as np`, `matplotlib.pyplot as plt`).

**Verified on this installation**: every entry has samples (a request in words + an assertion on the result) that are
analyzed, assembled and RUN with the installed Sage and the Python of the notebook kernel during a build (like the
syntax card, `syntaxcards.py`); Lean entries are compiled with each workspace's Lean (Lean 4.9 / Mathlib of Goedel
and the current Lean / Mathlib may name things differently: one construction per version). An entry whose sample
fails is not used (the model writes that part instead). Rebuilt when Sage, the kernel's Python packages, Lean or
Mathlib change (same hooks as the syntax card: server start, the update checkers' pass, a Mathlib update)."""
from __future__ import annotations

import asyncio
import hashlib
import json
import re
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

from .. import config
from ..logs import get
from . import intent as I

log = get("codecat")
CATALOGUE_VERSION = 1           # bump when an entry changes: every build is redone
_MEM: dict[str, tuple[float, dict | None]] = {}


# ================================================================ program assembly
@dataclass
class Prog:
    language: str
    imports: list[str] = field(default_factory=list)
    lines: list[str] = field(default_factory=list)
    names: dict[str, str] = field(default_factory=dict)        # name -> entry id
    entries: list[str] = field(default_factory=list)
    sympy: set[str] = field(default_factory=set)

    def use(self, eid: str) -> None:
        if eid not in self.entries:
            self.entries.append(eid)

    def line(self, text: str, eid: str = "", name: str = "") -> None:
        if text not in self.lines:
            self.lines.append(text)
        if eid:
            self.use(eid)
        if name:
            self.names[name] = eid

    def imp(self, line: str) -> None:
        if line not in self.imports:
            self.imports.append(line)

    def code(self) -> str:
        head = list(self.imports)
        if self.sympy:
            head.append("from sympy import " + ", ".join(sorted(self.sympy)))
        head = sort_imports(head)
        return "\n".join(head + self.lines).strip()


def sort_imports(lines: list[str]) -> list[str]:
    """`import a` lines first (sorted), then `from a import b, c` (sorted, names merged and sorted)."""
    plain, froms = set(), {}
    for l in lines:
        l = l.strip()
        m = re.fullmatch(r"from\s+([\w.]+)\s+import\s+(.+)", l)
        if m:
            names = [n.strip() for n in m.group(2).strip("() ").split(",") if n.strip()]
            froms.setdefault(m.group(1), set()).update(names)
        elif l:
            plain.add(l)
    out = sorted(plain)
    for mod in sorted(froms):
        star = "*" in froms[mod]
        out.append(f"from {mod} import " + ("*" if star else ", ".join(sorted(froms[mod]))))
    return out


@dataclass
class Assembly:
    code: str = ""
    full: bool = False
    prefix: str = ""               # canonical constructions of the recognized objects (mandatory start for a model)
    names: dict[str, str] = field(default_factory=dict)
    entries: list[str] = field(default_factory=list)
    reason: str = ""
    error: dict | None = None      # the request itself is wrong (F_12): explained, no code


class NotCovered(Exception):
    pass


# ---------------------------------------------------------------- objects
_GENS = "abcdeg"


def _obj_name(o: I.Obj) -> str:
    p = o.params
    return {"gf": lambda: f"F{p['p'] ** p['k']}", "zmod": lambda: f"Z{p['n']}", "poly": lambda: "R",
            "numfield": lambda: "K", "matrix": lambda: "M", "matspace": lambda: "MS" if p["group"] == "M" else "G",
            "group": lambda: "G", "ell": lambda: "E"}.get(o.kind, lambda: "")()


def _sage_ring(o: I.Obj | None, prog: Prog) -> str:
    """The Sage expression of a coefficient ring, its construction added to `prog`."""
    if o is None:
        return "QQ"
    if o.kind == "base":
        return "ZZ[I]" if o.params["ring"] == "ZZ[I]" else o.params["ring"]
    return _sage_obj(o, prog)


def _sage_obj(o: I.Obj, prog: Prog) -> str:
    p = o.params
    name = _obj_name(o)
    if name in prog.names:
        return name
    if o.kind == "gf":
        q = p["p"] ** p["k"]
        if p["k"] == 1:
            prog.line(f"{name} = GF({q})", "sage:gf_prime", name)
        else:
            used = sum(1 for n, e in prog.names.items() if e == "sage:gf")
            prog.line(f"{name}.<{_GENS[used % len(_GENS)]}> = GF({p['p']}^{p['k']})", "sage:gf", name)
        return name
    if o.kind == "zmod":
        prog.line(f"{name} = Zmod({p['n']})", "sage:zmod", name)
        return name
    if o.kind == "poly":
        ring = _sage_ring(o.ring, prog)
        vs = p["vars"]
        if len(vs) == 1:
            prog.line(f"R.<{vs[0]}> = PolynomialRing({ring})", "sage:poly", "R")
        else:
            prog.line(f"R.<{', '.join(vs)}> = PolynomialRing({ring})", "sage:mpoly", "R")
        return "R"
    if o.kind == "numfield":
        if "quad" in p:
            prog.line(f"K.<{p['gen']}> = QuadraticField({p['quad']})", "sage:quadfield", "K")
        elif "cyclo" in p:
            prog.line(f"K.<{p['gen']}> = CyclotomicField({p['cyclo']})", "sage:cyclofield", "K")
        else:
            prog.line("t = polygen(QQ, 't')", "sage:numfield")
            prog.line(f"K.<{p['gen']}> = NumberField({p['poly'].replace('x', 't')})", "sage:numfield", "K")
        return "K"
    if o.kind == "matrix":
        ring = _sage_ring(o.ring, prog) if o.ring is not None else "QQ"
        rows = "[" + ", ".join("[" + ", ".join(r) + "]" for r in p["rows"]) + "]"
        prog.line(f"M = matrix({ring}, {rows})", "sage:matrix", "M")
        return "M"
    if o.kind == "matspace":
        ring = _sage_ring(o.ring, prog)
        if p["group"] == "M":
            prog.line(f"MS = MatrixSpace({ring}, {p['n']})", "sage:matspace", "MS")
            return "MS"
        prog.line(f"G = {p['group']}({p['n']}, {ring})", "sage:lingroup", "G")
        return "G"
    if o.kind == "group":
        ctor = {"sym": "SymmetricGroup", "alt": "AlternatingGroup", "dih": "DihedralGroup",
                "cyc": "CyclicPermutationGroup"}[p["family"]]
        prog.line(f"G = {ctor}({p['n']})", f"sage:group_{p['family']}", "G")
        return "G"
    if o.kind == "ell":
        if "label" in p:
            prog.line(f"E = EllipticCurve('{p['label']}')", "sage:ell_label", "E")
        else:
            ring = _sage_ring(o.ring, prog) if o.ring is not None else "QQ"
            prog.line(f"E = EllipticCurve({ring}, [{', '.join(p['a'])}])", "sage:ell", "E")
        return "E"
    raise NotCovered(o.kind)


def _sage_vars(prog: Prog, names: list[str]) -> None:
    names = [n for n in names if n not in prog.names]
    if not names:
        return
    if len(names) == 1:
        prog.line(f"{names[0]} = var('{names[0]}')", "sage:var")
    else:
        prog.line(f"{', '.join(names)} = var('{' '.join(names)}')", "sage:var")
    for n in names:
        prog.names[n] = "sage:var"


def _syms(it: I.Intent, extra: list[str] = ()) -> list[str]:
    out: list[str] = []
    for e in it.exprs:
        for n in I.expr_names(e):
            if n not in out:
                out.append(n)
    for n in extra:
        if n and n not in out:
            out.append(n)
    if it.interval:
        for b in it.interval:
            for n in I.expr_names(b):
                if n not in out:
                    out.append(n)
    return sorted(out, key=lambda n: (n != it.var, n))


# ---------------------------------------------------------------- Sage operations
SYMBOLIC_OPS = {"integrate", "diff", "limit", "sum", "series", "plot", "solve", "simplify", "expand"}
INT_OPS = {"factor", "divisors", "is_prime", "totient", "next_prime", "primes_first", "primes_upto", "gcd", "lcm",
           "inverse_mod"}
DEFAULT_PLOT = ("-10", "10")
DEFAULT_TAYLOR = 5


def _ring_obj(it: I.Intent) -> I.Obj | None:
    poly = it.obj("poly")
    if poly is not None:
        return poly
    return next((o for o in it.objects if o.kind in ("gf", "zmod", "numfield", "base")), None)


def assemble_sage(it: I.Intent) -> Prog:
    prog = Prog("sage")
    op = it.op
    kinds = [o.kind for o in it.objects]
    main = next((o for o in it.objects if o.kind in ("ell", "matrix", "group", "matspace")), None)
    if main is not None:
        name = _sage_obj(main, prog)
        _sage_main_op(it, main, name, prog)
        return prog
    ring = _ring_obj(it)
    if op in ("factor", "roots", "is_irreducible", "gcd", "lcm", "irreducibles") and ring is not None and (
            it.exprs or op == "irreducibles"):
        _sage_poly_op(it, ring, prog)
        return prog
    if op in ("gcd", "lcm") and len(it.exprs) == 2 and ring is None:
        poly = I.Obj("poly", {"ring": "base{\"ring\":\"QQ\"}", "vars": [it.var]}, ring=I.Obj("base", {"ring": "QQ"}))
        _sage_poly_op(it, poly, prog)
        return prog
    if op in INT_OPS and not it.exprs and it.ints and not (kinds and op in ("gcd", "lcm")):
        _sage_int_op(it, prog)
        return prog
    if ring is not None and op in ("order", "elements", "generator", "units", "construct", "class_number",
                                   "discriminant", "degree", "integers_ring", "galois", "") and not it.exprs:
        name = _sage_obj(ring, prog) if ring.kind != "base" else _sage_ring(ring, prog)
        _sage_ring_op(it, ring, name, prog)
        return prog
    if op in SYMBOLIC_OPS and it.exprs and (ring is None or (ring.kind == "base" and op in ("solve", "plot", "limit",
                                                                                              "integrate", "diff"))):
        _sage_symbolic(it, prog)
        return prog
    if op == "factor" and it.exprs and ring is None:
        _sage_vars(prog, _syms(it))
        prog.line(f"factor({it.exprs[0]})", "sage:factor_sym")
        return prog
    if op == "roots" and it.exprs and ring is None:
        _sage_vars(prog, _syms(it))
        prog.line(f"solve({it.exprs[0]} == 0, {it.var})", "sage:roots_sym")
        return prog
    raise NotCovered(op or "no operation")


def _sage_poly_op(it: I.Intent, ring: I.Obj, prog: Prog) -> None:
    op = it.op
    if ring.kind != "poly":
        if op != "irreducibles" and any(len(I.expr_names(e)) > 1 for e in it.exprs):
            raise NotCovered("several variables")
        ring = I.Obj("poly", {"ring": ring.key(), "vars": [it.var or "x"]}, ring=ring)
    _sage_obj(ring, prog)
    vs = ring.params["vars"]
    for e in it.exprs:
        if not set(I.expr_names(e)) <= set(vs):
            raise NotCovered("formula not in the ring's variables")
    if op == "irreducibles":
        base = ring.ring
        if it.order is None or base is None or base.kind != "gf" or len(vs) != 1:
            raise NotCovered("irreducibles: degree and finite field needed")
        prog.line(f"[f for f in R.polynomials(of_degree={it.order}) if f.is_monic() and f.is_irreducible()]",
                 "sage:irreducibles")
        return
    prog.line(f"f = {it.exprs[0]}", "sage:polyelt", "f")
    if op == "factor":
        prog.line("f.factor()", "sage:factor_poly")
    elif op == "roots":
        prog.line("f.roots()", "sage:roots_poly")
    elif op == "is_irreducible":
        prog.line("f.is_irreducible()", "sage:irreducible")
    elif op in ("gcd", "lcm"):
        if len(it.exprs) != 2:
            raise NotCovered("gcd needs two polynomials")
        prog.line(f"g = {it.exprs[1]}", "sage:polyelt", "g")
        prog.line(f"{op}(f, g)", f"sage:{op}_poly")


def _sage_int_op(it: I.Intent, prog: Prog) -> None:
    n = it.ints
    op = it.op
    one = {"factor": "factor({0})", "divisors": "divisors({0})", "is_prime": "is_prime({0})",
           "totient": "euler_phi({0})", "next_prime": "next_prime({0})", "primes_first": "primes_first_n({0})",
           "primes_upto": "prime_range({0} + 1)"}
    if op in one:
        prog.line(one[op].format(n[0]), f"sage:int_{op}")
    elif op in ("gcd", "lcm") and len(n) >= 2:
        prog.line(f"{op}({n[0]}, {n[1]})", f"sage:int_{op}")
    elif op == "inverse_mod" and len(n) == 2:
        prog.line(f"Mod({n[0]}, {n[1]})^-1", "sage:inverse_mod")
    else:
        raise NotCovered(op)


def _sage_ring_op(it: I.Intent, ring: I.Obj, name: str, prog: Prog) -> None:
    op = it.op or "construct"
    k = ring.kind
    if op == "construct":
        prog.line(name)
    elif op == "order" and k in ("gf", "zmod"):
        prog.line(f"{name}.order()", "sage:ring_order")
    elif op == "elements" and k in ("gf", "zmod"):
        prog.line(f"list({name})", "sage:ring_elements")
    elif op == "generator" and k == "gf":
        prog.line(f"{name}.multiplicative_generator()", "sage:gf_generator")
    elif op in ("units", "elements") and k == "zmod":
        prog.line(f"[u for u in {name} if u.is_unit()]", "sage:zmod_units")
    elif k == "numfield" and op in ("class_number", "discriminant", "degree", "integers_ring", "galois", "units"):
        meth = {"class_number": "class_number()", "discriminant": "discriminant()", "degree": "degree()",
                "integers_ring": "ring_of_integers()", "galois": "galois_group()", "units": "unit_group()"}[op]
        prog.line(f"K.{meth}", f"sage:nf_{op}")
    else:
        raise NotCovered(f"{op} on {k}")
    if ring.params.get("units") and op == "construct":
        prog.lines[-1] = f"[u for u in {name} if u.is_unit()]"
        prog.use("sage:zmod_units")


def _sage_main_op(it: I.Intent, o: I.Obj, name: str, prog: Prog) -> None:
    op = it.op or "construct"
    if op == "construct":
        prog.line(name)
        return
    table = {
        "matrix": {"det": "M.det()", "rank": "M.rank()", "kernel": "M.right_kernel()", "inverse": "M.inverse()",
                   "eigenvalues": "M.eigenvalues()", "eigenvectors": "M.eigenvectors_right()",
                   "charpoly": "M.charpoly()", "minpoly": "M.minpoly()", "trace_mat": "M.trace()",
                   "jordan": "M.jordan_form()"},
        "group": {"order": "G.order()", "elements": "G.list()", "subgroups": "G.subgroups()",
                  "conj_classes": "G.conjugacy_classes_representatives()", "center": "G.center()",
                  "is_abelian": "G.is_abelian()", "char_table": "G.character_table()", "cayley": "G.cayley_table()"},
        "matspace": {"order": f"{name}.order()", "elements": f"{name}.list()"},
        "ell": {"ell_rank": "E.rank()", "points": "E.points()", "npoints": "E.cardinality()",
                "order": "E.cardinality()", "torsion": "E.torsion_subgroup()", "j_invariant": "E.j_invariant()",
                "discriminant": "E.discriminant()", "conductor": "E.conductor()", "plot": "E.plot()"},
    }[o.kind]
    if o.kind == "ell":
        over_q = "label" in o.params or o.ring is None
        if op == "points" and re.search(r"nombre|combien|how many|number of|cardinal", I.fold(it.text)):
            op = "npoints"
        if op in ("ell_rank", "conductor", "torsion") and not over_q:
            raise NotCovered(f"{op} needs a curve over Q")
        if op in ("points", "npoints", "order") and over_q:
            raise NotCovered("points of a curve over Q")
    if op not in table:
        raise NotCovered(f"{op} on {o.kind}")
    prog.line(table[op], f"sage:{o.kind}_{op}")


def _sage_symbolic(it: I.Intent, prog: Prog) -> None:
    op = it.op
    e = it.exprs[0]
    v = it.var or "x"
    if op == "sum":
        if not it.interval or not it.sumvar:
            raise NotCovered("sum bounds")
        _sage_vars(prog, _syms(it, [it.sumvar]))
        prog.line(f"sum({e}, {it.sumvar}, {it.interval[0]}, {it.interval[1]})", "sage:sum")
        return
    if op == "plot":
        if any(len(I.expr_names(x)) != 1 or "==" in x for x in it.exprs):
            raise NotCovered("plot of several variables")
        if len({I.expr_names(x)[0] for x in it.exprs}) != 1:
            raise NotCovered("plot: one variable")
        v = I.expr_names(it.exprs[0])[0]
        lo, hi = it.interval or DEFAULT_PLOT
        _sage_vars(prog, _syms(it))
        fs = it.exprs[0] if len(it.exprs) == 1 else "[" + ", ".join(it.exprs) + "]"
        prog.line(f"plot({fs}, ({v}, {lo}, {hi}))", "sage:plot")
        return
    if len(it.exprs) != 1 and op != "solve":
        raise NotCovered("several formulas")
    _sage_vars(prog, _syms(it))
    if op == "integrate":
        if it.interval:
            prog.line(f"integral({e}, {v}, {it.interval[0]}, {it.interval[1]})", "sage:integral_def")
        else:
            prog.line(f"integral({e}, {v})", "sage:integral")
    elif op == "diff":
        prog.line(f"diff({e}, {v}, {it.order})" if it.order and it.order > 1 else f"diff({e}, {v})", "sage:diff")
    elif op == "limit":
        if not it.point:
            raise NotCovered("limit point")
        side = f", dir='{'plus' if it.side == '+' else 'minus'}'" if it.side else ""
        prog.line(f"limit({e}, {v}={it.point}{side})", "sage:limit")
    elif op == "series":
        prog.line(f"taylor({e}, {v}, {it.point or 0}, {it.order or DEFAULT_TAYLOR})", "sage:taylor")
    elif op == "solve":
        eqs = [x if "==" in x else f"{x} == 0" for x in it.exprs]
        syms = _syms(it)
        if len(eqs) == 1:
            prog.line(f"solve({eqs[0]}, {v})", "sage:solve")
        else:
            prog.line(f"solve([{', '.join(eqs)}], {', '.join(syms)})", "sage:solve_system")
    elif op == "simplify":
        prog.line(f"({e}).simplify_full()", "sage:simplify")
    elif op == "expand":
        prog.line(f"({e}).expand()", "sage:expand")
    else:
        raise NotCovered(op)


# ---------------------------------------------------------------- Python (sympy / numpy / matplotlib)
_SYMPY_FUNCS = {"sin", "cos", "tan", "cot", "sec", "csc", "asin", "acos", "atan", "sinh", "cosh", "tanh", "exp",
                "log", "sqrt", "Abs", "floor", "ceiling", "gamma", "zeta", "binomial", "factorial", "erf", "sign",
                "pi", "E", "I", "oo", "Max", "Min", "cbrt", "asinh", "acosh", "atanh"}
_PY_RENAME = {"arcsin": "asin", "arccos": "acos", "arctan": "atan", "arcsinh": "asinh", "arccosh": "acosh",
              "arctanh": "atanh", "abs": "Abs", "ceil": "ceiling", "max": "Max", "min": "Min"}


def _py_expr(e: str, prog: Prog) -> str:
    s = I.to_python(e)
    s = re.sub(r"\b(" + "|".join(_PY_RENAME) + r")\b(?=\s*\()", lambda m: _PY_RENAME[m.group(1)], s)
    for n in set(re.findall(r"(?<![\w.])([A-Za-z_]\w*)", s)):
        if n in _SYMPY_FUNCS:
            prog.sympy.add(n)
    return s


def _py_eq(e: str, prog: Prog) -> str:
    if "==" not in e:
        return _py_expr(e, prog)
    lhs, rhs = e.split(" == ", 1)
    prog.sympy.add("Eq")
    return f"Eq({_py_expr(lhs, prog)}, {_py_expr(rhs, prog)})"


def _py_syms(prog: Prog, names: list[str]) -> None:
    names = [n for n in names if n not in prog.names]
    if not names:
        return
    prog.sympy.add("symbols")
    if len(names) == 1:
        prog.line(f"{names[0]} = symbols('{names[0]}')", "python:symbols")
    else:
        prog.line(f"{', '.join(names)} = symbols('{' '.join(names)}')", "python:symbols")
    for n in names:
        prog.names[n] = "python:symbols"


def assemble_python(it: I.Intent) -> Prog:
    prog = Prog("python")
    op = it.op
    main = next((o for o in it.objects if o.kind in ("ell", "matrix", "group", "matspace", "numfield")), None)
    if main is not None:
        _py_main(it, main, prog)
        return prog
    ring = _ring_obj(it)
    if ring is not None and ring.kind == "poly":
        if len(ring.params["vars"]) != 1:
            raise NotCovered("python: several polynomial variables")
        it_var = ring.params["vars"][0]
        ring = ring.ring
    else:
        it_var = it.var or "x"
    if ring is not None and ring.kind == "gf" and ring.params["k"] > 1:
        raise NotCovered("python: sympy only knows prime fields F_p")
    if ring is not None and ring.kind == "zmod" and not I.is_prime(ring.params["n"]) and it.exprs:
        raise NotCovered("python: polynomials over Z/nZ, n not prime")
    mod = (ring.params["p"] if ring is not None and ring.kind == "gf" else
           ring.params["n"] if ring is not None and ring.kind == "zmod" else None)
    base = ring.params["ring"] if ring is not None and ring.kind == "base" else None
    if base == "ZZ[I]":
        raise NotCovered("python: Gaussian integers")
    if op in INT_OPS and not it.exprs and it.ints:
        _py_int_op(it, prog)
        return prog
    if ring is not None and not it.exprs and ring.kind in ("gf", "zmod") and op in ("order", "elements", "units",
                                                                                     "construct", ""):
        n = mod
        if op == "order":
            prog.line(f"{n}", "python:ring_order")
        elif op == "units" or ring.params.get("units"):
            prog.sympy.add("gcd")
            prog.line(f"[a for a in range(1, {n}) if gcd(a, {n}) == 1]", "python:zmod_units")
        else:
            prog.line(f"list(range({n}))", "python:ring_elements")
        return prog
    if op in ("factor", "roots", "is_irreducible", "gcd", "lcm", "irreducibles") and (it.exprs or op == "irreducibles"):
        _py_syms(prog, [it_var])
        if op == "irreducibles":
            if mod is None or it.order is None:
                raise NotCovered("irreducibles: degree and prime field")
            prog.imp("from itertools import product")
            prog.sympy.update({"Poly"})
            prog.line(f"[Poly([1, *c], {it_var}, modulus={mod}).as_expr() for c in product(range({mod}), "
                     f"repeat={it.order}) if Poly([1, *c], {it_var}, modulus={mod}).is_irreducible]",
                     "python:irreducibles")
            return prog
        f = _py_expr(it.exprs[0], prog)
        if any(set(I.expr_names(e)) - {it_var} for e in it.exprs):
            raise NotCovered("python: formula in other variables")
        if op in ("gcd", "lcm"):
            if len(it.exprs) != 2:
                raise NotCovered("gcd of two")
            g = _py_expr(it.exprs[1], prog)
            prog.sympy.add(op)
            prog.line(f"{op}({f}, {g}" + (f", modulus={mod})" if mod else ")"), f"python:{op}_poly")
            return prog
        if mod is not None:
            prog.sympy.add("Poly")
            prog.line(f"f = Poly({f}, {it_var}, modulus={mod})", "python:poly_mod", "f")
            if op == "factor":
                prog.line("f.factor_list()", "python:factor_mod")
            elif op == "roots":
                prog.line(f"[a for a in range({mod}) if f.eval(a) % {mod} == 0]", "python:roots_mod")
            else:
                prog.line("f.is_irreducible", "python:irreducible_mod")
            return prog
        if op == "factor":
            prog.sympy.add("factor")
            prog.line(f"factor({f}" + (", extension=I)" if base == "ZZ[I]" else ")"), "python:factor")
        elif op == "roots":
            if base is None:
                prog.sympy.update({"solve"})
                prog.line(f"solve({f}, {it_var})", "python:roots_sym")
            else:
                prog.sympy.update({"Poly", "roots"})
                flt = {"QQ": "Q", "ZZ": "Z", "RR": "R", "CC": "C"}[base]
                prog.line(f"roots(Poly({f}, {it_var}), filter='{flt}')", "python:roots_ring")
        elif op == "is_irreducible":
            prog.sympy.add("Poly")
            prog.line(f"Poly({f}, {it_var}).is_irreducible", "python:irreducible")
        return prog
    if op in SYMBOLIC_OPS and it.exprs and (ring is None or ring.kind == "base"):
        _py_symbolic(it, prog)
        return prog
    raise NotCovered(op or "no operation")


def _py_int_op(it: I.Intent, prog: Prog) -> None:
    n = it.ints
    op = it.op
    one = {"factor": ("factorint", "factorint({0})"), "divisors": ("divisors", "divisors({0})"),
           "is_prime": ("isprime", "isprime({0})"), "totient": ("totient", "totient({0})"),
           "next_prime": ("nextprime", "nextprime({0})"),
           "primes_first": ("prime", "[prime(i) for i in range(1, {0} + 1)]"),
           "primes_upto": ("primerange", "list(primerange({0} + 1))")}
    if op in one:
        prog.sympy.add(one[op][0])
        prog.line(one[op][1].format(n[0]), f"python:int_{op}")
    elif op in ("gcd", "lcm") and len(n) >= 2:
        prog.sympy.add(op)
        prog.line(f"{op}({n[0]}, {n[1]})", f"python:int_{op}")
    elif op == "inverse_mod" and len(n) == 2:
        prog.sympy.add("mod_inverse")
        prog.line(f"mod_inverse({n[0]}, {n[1]})", "python:inverse_mod")
    else:
        raise NotCovered(op)


def _py_main(it: I.Intent, o: I.Obj, prog: Prog) -> None:
    op = it.op or "construct"
    if o.kind == "matrix":
        if o.ring is not None and not (o.ring.kind == "base" and o.ring.params["ring"] in ("QQ", "ZZ")):
            raise NotCovered("python: matrices over other rings")
        prog.sympy.add("Matrix")
        rows = "[" + ", ".join("[" + ", ".join(_py_num(x, prog) for x in r) + "]" for r in o.params["rows"]) + "]"
        prog.line(f"M = Matrix({rows})", "python:matrix", "M")
        ops = {"det": "M.det()", "rank": "M.rank()", "kernel": "M.nullspace()", "inverse": "M.inv()",
               "eigenvalues": "M.eigenvals()", "eigenvectors": "M.eigenvects()", "trace_mat": "M.trace()",
               "jordan": "M.jordan_form()", "construct": "M"}
        if op == "charpoly":
            _py_syms(prog, ["x"])
            prog.line("M.charpoly(x).as_expr()", "python:matrix_charpoly")
            return
        if op not in ops:
            raise NotCovered(op)
        prog.line(ops[op], f"python:matrix_{op}")
        return
    if o.kind == "group":
        ctor = {"sym": "SymmetricGroup", "alt": "AlternatingGroup", "dih": "DihedralGroup",
                "cyc": "CyclicGroup"}[o.params["family"]]
        prog.imp(f"from sympy.combinatorics.named_groups import {ctor}")
        prog.line(f"G = {ctor}({o.params['n']})", f"python:group_{o.params['family']}", "G")
        ops = {"order": "G.order()", "elements": "list(G.elements)", "is_abelian": "G.is_abelian",
               "center": "G.center()", "conj_classes": "G.conjugacy_classes()", "construct": "G"}
        if op not in ops:
            raise NotCovered(op)
        prog.line(ops[op], f"python:group_{op}")
        return
    raise NotCovered(f"python: {o.kind}")


def _py_num(x: str, prog: Prog) -> str:
    if "/" in x:
        prog.sympy.add("Rational")
        a, b = x.split("/")
        return f"Rational({a}, {b})"
    return x


def _py_symbolic(it: I.Intent, prog: Prog) -> None:
    op = it.op
    v = it.var or "x"
    if op == "plot":
        if any(len(I.expr_names(x)) != 1 or "==" in x for x in it.exprs) or \
                len({I.expr_names(x)[0] for x in it.exprs}) != 1:
            raise NotCovered("plot: one variable")
        v = I.expr_names(it.exprs[0])[0]
        _py_syms(prog, [v])
        lo, hi = it.interval or DEFAULT_PLOT
        prog.imp("import matplotlib.pyplot as plt")
        prog.imp("import numpy as np")
        prog.sympy.add("lambdify")
        lo_p, hi_p = _py_expr(lo, prog), _py_expr(hi, prog)
        if re.search(r"[A-Za-z]", lo_p + hi_p):
            prog.sympy.add("N")
            lo_p, hi_p = f"float(N({lo_p}))", f"float(N({hi_p}))"
        prog.line(f"xs = np.linspace({lo_p}, {hi_p}, 400)", "python:plot")
        for e in it.exprs:
            prog.line(f"plt.plot(xs, lambdify({v}, {_py_expr(e, prog)}, 'numpy')(xs), label='${e}$')", "python:plot")
        prog.line("plt.legend()", "python:plot")
        prog.line("plt.show()", "python:plot")
        return
    syms = _syms(it, [it.sumvar] if op == "sum" else [])
    _py_syms(prog, syms)
    e = _py_expr(it.exprs[0], prog)
    if op == "integrate":
        prog.sympy.add("integrate")
        if it.interval:
            a, b = (_py_expr(x, prog) for x in it.interval)
            prog.line(f"integrate({e}, ({v}, {a}, {b}))", "python:integral_def")
        else:
            prog.line(f"integrate({e}, {v})", "python:integral")
    elif op == "diff":
        prog.sympy.add("diff")
        prog.line(f"diff({e}, {v}, {it.order})" if it.order and it.order > 1 else f"diff({e}, {v})", "python:diff")
    elif op == "limit":
        if not it.point:
            raise NotCovered("limit point")
        prog.sympy.add("limit")
        pt = _py_expr(it.point, prog)
        prog.line(f"limit({e}, {v}, {pt}" + (f", '{it.side}')" if it.side else ")"), "python:limit")
    elif op == "sum":
        if not it.interval or not it.sumvar:
            raise NotCovered("sum bounds")
        prog.sympy.add("summation")
        a, b = (_py_expr(x, prog) for x in it.interval)
        prog.line(f"summation({e}, ({it.sumvar}, {a}, {b}))", "python:sum")
    elif op == "series":
        prog.sympy.add("series")
        pt = _py_expr(it.point or "0", prog)
        prog.line(f"series({e}, {v}, {pt}, {(it.order or DEFAULT_TAYLOR) + 1}).removeO()", "python:taylor")
    elif op == "solve":
        prog.sympy.add("solve")
        eqs = [_py_eq(x, prog) for x in it.exprs]
        if len(eqs) == 1:
            prog.line(f"solve({eqs[0]}, {v})", "python:solve")
        else:
            prog.line(f"solve([{', '.join(eqs)}], [{', '.join(syms)}])", "python:solve_system")
    elif op == "simplify":
        prog.sympy.add("simplify")
        prog.line(f"simplify({e})", "python:simplify")
    elif op == "expand":
        prog.sympy.add("expand")
        prog.line(f"expand({e})", "python:expand")
    else:
        raise NotCovered(op)
    if len(it.exprs) != 1 and op != "solve":
        raise NotCovered("several formulas")


# ---------------------------------------------------------------- the prefix alone (partial coverage)
def prefix_sage(it: I.Intent) -> Prog:
    prog = Prog("sage")
    for o in it.objects:
        if o.kind == "base":
            continue
        try:
            _sage_obj(o, prog)
        except NotCovered:
            pass
    if it.exprs and not it.obj("poly"):
        _sage_vars(prog, [n for n in _syms(it) if n not in prog.names])
    return prog


def prefix_python(it: I.Intent) -> Prog:
    prog = Prog("python")
    for o in it.objects:
        try:
            if o.kind == "matrix" and (o.ring is None or o.ring.kind == "base"):
                prog.sympy.add("Matrix")
                rows = "[" + ", ".join("[" + ", ".join(_py_num(x, prog) for x in r) + "]"
                                       for r in o.params["rows"]) + "]"
                prog.line(f"M = Matrix({rows})", "python:matrix", "M")
            elif o.kind == "group":
                p = Prog("python")
                _py_main(I.Intent(op="construct"), o, p)
                prog.imports += [x for x in p.imports if x not in prog.imports]
                prog.line(p.lines[0], p.entries[0], "G")
        except NotCovered:
            pass
    if it.exprs:
        _py_syms(prog, _syms(it))
    return prog


# ---------------------------------------------------------------- entry point
def assemble(it: I.Intent, language: str, verified: dict | None = None) -> Assembly | None:
    """The canonical cell for this intent: `full` when the catalogue writes it entirely (every entry used is not known
    to fail on this installation), else the canonical constructions of its objects as `prefix` for the model.
    None when nothing was recognized."""
    if it.errors:
        return Assembly(error=it.errors[0], reason="request error")
    if not it.recognized:
        return None
    lang = "sage" if language == "sage" else "python"
    full = None
    reason = ""
    if not it.rest:
        try:
            full = assemble_sage(it) if lang == "sage" else assemble_python(it)
        except NotCovered as e:
            reason = str(e)
            full = None
        except Exception as e:  # noqa: BLE001 (a template bug never breaks a request: the model writes it)
            log.exception("catalogue assembly")
            reason = f"internal: {type(e).__name__}"
            full = None
    else:
        reason = "words not understood: " + ", ".join(it.rest[:5])
    bad = (verified or {}).get("failed") or {}
    if full is not None:
        failing = [e for e in full.entries if e in bad]
        if failing:
            reason = "not verified on this installation: " + ", ".join(failing)
            full = None
    if full is not None:
        return Assembly(code=full.code(), full=True, prefix="", names=dict(full.names), entries=list(full.entries))
    pre = prefix_sage(it) if lang == "sage" else prefix_python(it)
    pre_entries = [e for e in pre.entries if e not in bad]
    if len(pre_entries) != len(pre.entries):
        pre = Prog(lang)
    return Assembly(code="", full=False, prefix=pre.code(), names=dict(pre.names), entries=list(pre.entries),
                    reason=reason or "partial")


# ================================================================ Lean / Mathlib (constructions per version)
# id -> {"default": code, "v4.9": code for Lean 4.9 / Goedel's Mathlib}: what the code generators and the Lean
# screens may cite. `{p}`, `{k}`… are filled from the sample parameters for the compiled check.
LEAN_ENTRIES: dict[str, dict] = {
    "gf": {"doc": "finite field F_{p^k}", "sample": {"p": 5, "k": 3, "q": 125},
           "default": "instance : Fact (Nat.Prime {p}) := ⟨by norm_num⟩\nabbrev F{q} := GaloisField {p} {k}\n"
                      "example : Nat.card F{q} = {p} ^ {k} := GaloisField.card {p} {k} (by norm_num)",
           "v4.9": "instance : Fact (Nat.Prime {p}) := ⟨by norm_num⟩\nabbrev F{q} := GaloisField {p} {k}\n"
                   "example : Fintype.card F{q} = {p} ^ {k} := GaloisField.card {p} {k} (by norm_num)"},
    "gf_prime": {"doc": "prime field F_p", "sample": {"p": 7},
                 "default": "instance : Fact (Nat.Prime {p}) := ⟨by norm_num⟩\nabbrev F{p} := ZMod {p}\n"
                            "example : Fintype.card F{p} = {p} := ZMod.card {p}"},
    "zmod": {"doc": "Z/nZ", "sample": {"n": 12}, "default": "abbrev Z{n} := ZMod {n}\n#check (3 : Z{n})"},
    "poly": {"doc": "K[x]", "sample": {}, "default": "open Polynomial\n#check ((X ^ 2 - 2 : ℚ[X]))"},
    "mpoly": {"doc": "K[x, y]", "sample": {}, "default": "#check (MvPolynomial (Fin 2) (ZMod 7))"},
    "gauss": {"doc": "Z[i]", "sample": {}, "default": "#check (GaussianInt)"},
    "quadfield": {"doc": "Q(√d)", "sample": {}, "default":
                  "open Polynomial\nabbrev K := AdjoinRoot (X ^ 2 + 5 : ℚ[X])\n#check (AdjoinRoot.root (X ^ 2 + 5 : ℚ[X]))"},
    "cyclofield": {"doc": "Q(ζ_n)", "sample": {}, "default": "#check (CyclotomicField 5 ℚ)"},
    "matrix": {"doc": "matrix literal", "sample": {},
               "default": "def M : Matrix (Fin 2) (Fin 2) ℚ := !![1, 2; 3, 4]\nexample : M.det = -2 := by\n"
                          "  simp [M, Matrix.det_fin_two]\n  norm_num"},
    "matspace": {"doc": "M_n(K), GL_n(K), SL_n(K)", "sample": {},
                 "default": "#check (Matrix (Fin 2) (Fin 2) ℚ)\n#check (GL (Fin 2) ℚ)\n"
                            "#check (Matrix.SpecialLinearGroup (Fin 2) ℤ)"},
    "group_sym": {"doc": "S_n", "sample": {}, "default":
                  "example : Fintype.card (Equiv.Perm (Fin 5)) = 120 := by\n  rw [Fintype.card_perm, Fintype.card_fin]\n  rfl"},
    "group_alt": {"doc": "A_n", "sample": {}, "default": "#check (alternatingGroup (Fin 5))"},
    "group_dih": {"doc": "D_n (2n elements)", "sample": {}, "default":
                  "example : Fintype.card (DihedralGroup 4) = 8 := DihedralGroup.card"},
    "group_cyc": {"doc": "C_n", "sample": {}, "default": "#check (Multiplicative (ZMod 6))"},
    "ell": {"doc": "Weierstrass curve", "sample": {},
            "default": "def E : WeierstrassCurve ℚ := ⟨0, 0, 0, -1, 0⟩\n#check E.Δ"},
    "int_gcd": {"doc": "gcd", "sample": {}, "default": "example : Nat.gcd 12 18 = 6 := by decide"},
    "int_totient": {"doc": "Euler φ", "sample": {}, "default": "example : Nat.totient 10 = 4 := by decide"},
    "int_is_prime": {"doc": "primality", "sample": {}, "default": "example : Nat.Prime 97 := by norm_num"},
    "int_factor": {"doc": "prime factors (list)", "sample": {},
                   "default": "#eval Nat.primeFactorsList 2024", "v4.9": "#eval Nat.factors 2024"},
    "int_divisors": {"doc": "divisors", "sample": {}, "default": "example : Nat.divisors 6 = {1, 2, 3, 6} := by decide"},
    "sum_range": {"doc": "finite sum", "sample": {},
                  "default": "example : ∑ i ∈ Finset.range 4, i ^ 2 = 14 := by decide",
                  "v4.9": "example : ∑ i in Finset.range 4, i ^ 2 = 14 := by decide"},
}


def lean_flavor(toolchain: str) -> str:
    """'v4.9' for the prover's Lean 4.9 workspace (Goedel's Mathlib), 'default' otherwise."""
    m = re.search(r"v4\.(\d+)", toolchain or "")
    return "v4.9" if m and int(m.group(1)) < 12 else "default"


def lean_code(eid: str, flavor: str) -> str:
    e = LEAN_ENTRIES[eid]
    code = e.get(flavor) or e["default"]
    return code.format(**e.get("sample", {})) if e.get("sample") else code


# ---------------------------------------------------------------- Lean entries for a request (S-AM, D45)
# What the provers / formalizer / explanations get: the entries relevant to the request's recognized intent (words,
# via intent.py) and to the Lean already written (names in the statement), only those VERIFIED on the workspace.
_OBJ_LEAN = {"zmod": ["zmod"], "matrix": ["matrix"], "matspace": ["matspace"], "ell": ["ell"]}
_GROUP_LEAN = {"sym": "group_sym", "alt": "group_alt", "dih": "group_dih", "cyc": "group_cyc"}
_OP_LEAN = {"gcd": "int_gcd", "totient": "int_totient", "is_prime": "int_is_prime", "divisors": "int_divisors",
            "sum": "sum_range", "det": "matrix"}
_LEAN_NAMES: list[tuple[str, re.Pattern]] = [(e, re.compile(p)) for e, p in [
    ("gf", r"\bGaloisField\b"), ("gf_prime", r"Fact\s*\(\s*Nat\.Prime"),
    ("zmod", r"\bZMod\b"), ("mpoly", r"\bMvPolynomial\b"), ("poly", r"\bPolynomial\b|\[X\]|\bX\s*\^"),
    ("gauss", r"\bGaussianInt\b|ℤ\[i\]"), ("quadfield", r"\bAdjoinRoot\b|\bQuadraticAlgebra\b"),
    ("cyclofield", r"\bCyclotomicField\b"), ("matrix", r"!!\[|\bMatrix\.det\b|\.det\b"),
    ("matspace", r"\bMatrix\s*\(Fin|\bGL\s*\(|\bSpecialLinearGroup\b"),
    ("group_sym", r"\bEquiv\.Perm\b|\bPerm\s*\(Fin"), ("group_alt", r"\balternatingGroup\b"),
    ("group_dih", r"\bDihedralGroup\b"), ("group_cyc", r"\bMultiplicative\s*\(ZMod|\bIsCyclic\b"),
    ("ell", r"\bWeierstrassCurve\b|\bEllipticCurve\b"), ("int_gcd", r"\bNat\.gcd\b|\bInt\.gcd\b|\bgcd\b"),
    ("int_totient", r"\btotient\b|\bφ\b"), ("int_is_prime", r"\bNat\.Prime\b|\.Prime\b|\bPrime\s"),
    ("int_factor", r"\bprimeFactorsList\b|\bNat\.factors\b|\bfactorization\b"),
    ("int_divisors", r"\bdivisors\b"), ("sum_range", r"∑|\bFinset\.sum\b|\bFinset\.range\b"),
]]


def lean_relevant(*texts: str) -> list[str]:
    """Catalogue entries relevant to `texts` (the request in words, the Lean statement…), in catalogue order (stable:
    the same request gives the same list, so the prompt block is byte-identical)."""
    found: set[str] = set()
    words = "\n".join(t for t in texts if t)
    try:
        it = I.analyze(words[:4000])
    except Exception:  # noqa: BLE001 (the analysis never breaks a prompt)
        it = None
    if it is not None:
        for o in it.objects:
            if o.kind == "gf":
                found.add("gf_prime" if o.params.get("k") == 1 else "gf")
            elif o.kind == "poly":
                found.add("mpoly" if len(o.params.get("vars") or []) > 1 else "poly")
            elif o.kind == "numfield":
                p = o.params
                found.add("cyclofield" if "cyclo" in p else "gauss" if p.get("quad") == -1 else
                          "quadfield" if "quad" in p else "poly")
            elif o.kind == "base" and o.params.get("ring") == "ZZ[I]":
                found.add("gauss")
            elif o.kind == "group" and o.params.get("family") in _GROUP_LEAN:
                found.add(_GROUP_LEAN[o.params["family"]])
            else:
                found.update(_OBJ_LEAN.get(o.kind, []))
        if it.op in _OP_LEAN:
            found.add(_OP_LEAN[it.op])
        if it.op == "factor" and not any(o.kind == "poly" for o in it.objects):
            found.add("int_factor")
    no_fact = re.sub(r"Fact\s*\(\s*Nat\.Prime\s+\w+\s*\)", "", words)   # `Fact (Nat.Prime 5)`: a field, not primality
    for eid, rx in _LEAN_NAMES:
        if rx.search(no_fact if eid == "int_is_prime" else words):
            found.add(eid)
    if "gf" in found:
        found.discard("gf_prime")                  # the F_{p^k} entry already shows the `Fact` instance
    return [e for e in LEAN_ENTRIES if e in found]


def lean_prompt_block(ws, *texts: str, budget: int = 220, lang: str = "en") -> tuple[str, list[str]]:
    """(text, entry ids): the relevant Lean constructions verified on `ws`, compact, for a prompt. '' when the
    workspace's catalogue is not built or nothing is relevant (an entry that failed — or was never checked — on this
    workspace is never given). `budget`: estimated tokens (≈ 3.5 characters each); entries past it are dropped."""
    if ws is None:
        return "", []
    st = lean_status(ws)
    if not st:
        return "", []
    ok = set(st.get("verified") or []) - set((st.get("failed") or {}).keys())
    ids = [e for e in lean_relevant(*texts) if e in ok]
    if not ids:
        return "", []
    flavor = st.get("flavor") or lean_flavor(getattr(ws, "toolchain", ""))
    head = (f"Verified Lean constructions (compiled on this workspace: Lean {st.get('lean') or '?'}, this Mathlib) — "
            "use these exact spellings:") if lang == "en" else (
        f"Constructions Lean vérifiées (compilées sur cet espace : Lean {st.get('lean') or '?'}, cette Mathlib) — "
        "écrire exactement ainsi :")
    out, used, kept = [head], int(len(head) / 3.5), []
    for eid in ids:
        item = f"- {LEAN_ENTRIES[eid]['doc']}:\n" + "\n".join("    " + l for l in lean_code(eid, flavor).split("\n"))
        t = int(len(item) / 3.5) + 1
        if used + t > budget:
            continue
        out.append(item)
        used += t
        kept.append(eid)
    return ("\n".join(out), kept) if kept else ("", [])


def lean_source(flavor: str) -> tuple[str, list[tuple[str, int, int]]]:
    """One file with every Lean entry (after the Goedel header), and the line span of each entry."""
    from .. import leancheck
    body = leancheck.GOEDEL_HEADER
    spans = []
    for eid in LEAN_ENTRIES:
        start = body.count("\n") + 1
        body += f"\nsection S_{eid}\n-- {eid}\n{lean_code(eid, flavor)}\nend S_{eid}\n"
        spans.append((eid, start, body.count("\n")))
    return body, spans


# ================================================================ verification samples
# (request, Sage assertion on `_`, Python assertion on `_`) — `None`: the language does not cover it (checked too:
# the assembly must refuse it, never write wrong code)
SAMPLES: list[tuple[str, str | None, str | None]] = [
    ("factorise x^5+4x-1 dans F_125[x]", "len(_) == 1 and _[0][0] == _.expand()", None),
    ("les racines dans F_16 de x^5+x^3+x+1", "len(_) == 5 and all(m == 1 for r, m in _)", None),
    ("factorise x^2+1 dans F_7[x]", "len(_) == 1", "_[1][0][1] == 1 and len(_[1]) == 1"),
    ("racines de x^2-2 dans F_7", "sorted(r for r, m in _) == [3, 4]", "_ == [3, 4]"),
    ("liste les polynomes irreductibles de degre 2 de F_3[x]", "len(_) == 3", "len(_) == 3"),
    ("liste les polynomes irreductibles de degre 2 de F_4[x]", "len(_) == 6", None),
    ("x^4+x+1 est-il irreductible dans F_2[x] ?", "_ == True", "_ == True"),
    ("factorise x^4+4 dans Q[x]", "len(_) == 2", "_ == (x**2 - 2*x + 2)*(x**2 + 2*x + 2)"),
    ("factorise x^4+4 sur Z[i]", "len(_) == 4", None),
    ("racines de x^3-2 dans R", "len(_) == 1", "len(_) == 1"),
    ("pgcd de x^4-1 et x^6-1 dans Q[x]", "_ == x^2 - 1", "_ == x**2 - 1"),
    ("factorise x^2+y^2 dans F_5[x,y]", "len(_) == 2", None),
    ("factorise 2024", "str(_) == '2^3 * 11 * 23'", "_ == {2: 3, 11: 1, 23: 1}"),
    ("les diviseurs de 12", "_ == [1, 2, 3, 4, 6, 12]", "_ == [1, 2, 3, 4, 6, 12]"),
    ("est-ce que 97 est premier ?", "_ == True", "_ == True"),
    ("indicatrice d'Euler de 10", "_ == 4", "_ == 4"),
    ("les 10 premiers nombres premiers", "_[-1] == 29 and len(_) == 10", "_[-1] == 29 and len(_) == 10"),
    ("nombres premiers inferieurs a 20", "_ == [2, 3, 5, 7, 11, 13, 17, 19]", "_ == [2, 3, 5, 7, 11, 13, 17, 19]"),
    ("pgcd de 12 et 18", "_ == 6", "_ == 6"),
    ("inverse de 3 modulo 7", "_ == 5", "_ == 5"),
    ("les elements inversibles de Z/12Z", "len(_) == 4", "_ == [1, 5, 7, 11]"),
    ("ordre de F_{2^8}", "_ == 256", None),
    ("un generateur de F_9", "_.multiplicative_order() == 8", None),
    ("integrale de x^2 sin(x) entre 0 et pi", "bool(_ == pi^2 - 4)", "_ == pi**2 - 4"),
    ("primitive de 1/(1+x^2)", "bool(_ == arctan(x))", "_ == atan(x)"),
    ("derivee de x^3 e^{2x}", "bool((_ - (3*x^2*exp(2*x) + 2*x^3*exp(2*x))).simplify_full() == 0)",
     "simplify(_ - (3*x**2*exp(2*x) + 2*x**3*exp(2*x))) == 0"),
    ("derivee seconde de sin(x)", "bool(_ == -sin(x))", "_ == -sin(x)"),
    ("limite de sin(x)/x en 0", "_ == 1", "_ == 1"),
    ("limite de (1+1/x)^x quand x tend vers l'infini", "bool(_ == e)", "_ == E"),
    ("limite de 1/x en 0 a droite", "_ == +Infinity", "_ == oo"),
    ("somme pour k de 1 a n de k^2", "bool((_ - n*(n+1)*(2*n+1)/6).expand() == 0)",
     "simplify(_ - n*(n+1)*(2*n+1)/6) == 0"),
    ("\\sum_{k=1}^{oo} 1/k^2", "bool(_ == pi^2/6)", "_ == pi**2/6"),
    ("developpement limite de exp(x) a l'ordre 3 en 0", "bool(_ == 1 + x + x^2/2 + x^3/6)",
     "_ == 1 + x + x**2/2 + x**3/6"),
    ("resous x^2-2=0", "len(_) == 2", "len(_) == 2"),
    ("simplifie (x^2-1)/(x-1)", "bool(_ == x + 1)", "_ == x + 1"),
    ("developpe (x+1)^3", "bool(_ == x^3 + 3*x^2 + 3*x + 1)", "_ == x**3 + 3*x**2 + 3*x + 1"),
    ("trace sin(x)/x sur [-10,10]", "isinstance(_, sage.plot.graphics.Graphics)", "_ is None"),
    ("trace sin(x) et cos(x) entre 0 et 2pi", "isinstance(_, sage.plot.graphics.Graphics)", "_ is None"),
    ("determinant de [[1,2],[3,4]]", "_ == -2", "_ == -2"),
    ("inverse de la matrice [[1,2],[3,4]]", "_ * matrix(QQ, [[1,2],[3,4]]) == 1", "_ * M == eye(2)"),
    ("valeurs propres de [[2,1],[1,2]]", "sorted(_) == [1, 3]", "_ == {3: 1, 1: 1}"),
    ("rang de [[1,2],[2,4]]", "_ == 1", "_ == 1"),
    ("polynome caracteristique de [[2,1],[1,2]]", "str(_) == 'x^2 - 4*x + 3'", "_ == x**2 - 4*x + 3"),
    ("ordre du groupe symetrique S_5", "_ == 120", "_ == 120"),
    ("sous-groupes de D_4", "len(_) == 10", None),
    ("le groupe A_4 est-il abelien ?", "_ == False", "_ == False"),
    ("classes de conjugaison de S_4", "len(_) == 5", "len(_) == 5"),
    ("nombre de points de la courbe elliptique y^2 = x^3 + x + 1 sur F_7", "_ == 5", None),
    ("rang de la courbe elliptique y^2 = x^3 - x", "_ == 0", None),
    ("j-invariant de la courbe elliptique y^2 + y = x^3 - x", "_ == 110592/37", None),
    ("nombre de classes de Q(sqrt(-5))", "_ == 2", None),
    ("discriminant de Q(sqrt(8))", "_ == 8", None),
    ("degre du corps cyclotomique Q(zeta_7)", "_ == 6", None),
    ("factorise x^2+1 dans Q(i)[x]", "len(_) == 2", None),
]


_RUN_SAGE = r'''
import json, sys, signal, io, contextlib
req = json.loads(sys.stdin.read())
from sage.all import *
import sage.all
from sage.repl.preparse import preparse_file, preparse
out = {}
def _alarm(*a):
    raise TimeoutError("sample timeout")
signal.signal(signal.SIGALRM, _alarm)
base = dict(sage.all.__dict__)
for sid, code, check in req["samples"]:
    ns = dict(base)
    lines = code.rstrip().split("\n")
    lines[-1] = "_ = " + lines[-1]
    signal.alarm(int(req.get("timeout", 60)))
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            exec(compile(preparse_file("\n".join(lines)), "<" + sid + ">", "exec"), ns)
            ok = eval(compile(preparse(check), "<check>", "eval"), ns)
        out[sid] = "" if ok else "assertion failed: " + check + " (got " + repr(ns.get("_"))[:200] + ")"
    except BaseException as e:
        out[sid] = (type(e).__name__ + ": " + str(e))[:300]
    finally:
        signal.alarm(0)
print("MADALEAN_CODECAT " + json.dumps(out))
'''

_RUN_PY = r'''
import json, sys, signal, io, contextlib, os
os.environ.setdefault("MPLBACKEND", "Agg")
req = json.loads(sys.stdin.read())
out = {"_versions": {}}
for mod in ("sympy", "numpy", "matplotlib"):
    try:
        out["_versions"][mod] = __import__(mod).__version__
    except Exception:
        out["_versions"][mod] = ""
out["_versions"]["python"] = sys.version.split()[0]
try:
    import sympy as _sy
    out["_sympy"] = sorted(n for n in dir(_sy) if not n.startswith("_"))
except Exception:
    out["_sympy"] = []
def _alarm(*a):
    raise TimeoutError("sample timeout")
signal.signal(signal.SIGALRM, _alarm)
for sid, code, check in req["samples"]:
    ns = {}
    lines = code.rstrip().split("\n")
    lines[-1] = "_ = " + lines[-1]
    signal.alarm(int(req.get("timeout", 60)))
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            exec(compile("\n".join(lines), "<" + sid + ">", "exec"), ns)
            import sympy
            env = dict(vars(sympy))
            env.update(ns)
            ok = eval(check, env)
        out[sid] = "" if ok else "assertion failed: " + check + " (got " + repr(ns.get("_"))[:200] + ")"
    except BaseException as e:
        out[sid] = (type(e).__name__ + ": " + str(e))[:300]
    finally:
        signal.alarm(0)
print("MADALEAN_CODECAT " + json.dumps(out))
'''


def sample_programs(language: str) -> list[tuple[str, str, str, list[str]]]:
    """(sample id, assembled code, check, entries) for the samples this language covers. A sample the language
    marks None must NOT be fully assembled (else: it is reported as a refusal failure)."""
    out = []
    for i, (req, sage_chk, py_chk) in enumerate(SAMPLES):
        chk = sage_chk if language == "sage" else py_chk
        it = I.analyze(req)
        a = assemble(it, language)
        sid = f"s{i:02d}"
        if chk is None:
            if a is not None and a.full:
                out.append((sid, "raise RuntimeError('should not be covered')", "False", a.entries))
            continue
        if a is None or not a.full:
            out.append((sid, f"raise RuntimeError('not assembled: {(a.reason if a else 'not recognized')[:80]}')",
                        "False", []))
            continue
        out.append((sid, a.code, chk, a.entries))
    return out


def _interp(language: str) -> str | None:
    from .sagebridge import find_kernelspec
    from .. import syntaxcards
    if language == "sage":
        return syntaxcards.sage_python()
    spec = find_kernelspec("python3")
    return spec["argv"][0] if spec else None


def tool_version(language: str) -> str:
    """Sage version, or the kernel Python + sympy/numpy/matplotlib versions (the build key)."""
    from .. import syntaxcards
    if language == "sage":
        return syntaxcards.sage_version()
    py = _interp("python")
    if not py:
        return ""
    k = f"pyver:{py}"
    hit = _MEM.get(k)
    if hit and time.monotonic() - hit[0] < 600:
        return str(hit[1])
    try:
        p = subprocess.run([py, "-I", "-c", "import sys\nv=[sys.version.split()[0]]\nfor m in ('sympy','numpy',"
                            "'matplotlib'):\n    try: v.append(__import__(m).__version__)\n    except Exception: "
                            "v.append('-')\nprint('-'.join(v))"], capture_output=True, text=True, timeout=60)
        v = p.stdout.strip().splitlines()[-1] if p.stdout.strip() else ""
    except (OSError, subprocess.SubprocessError):
        v = ""
    v = v if re.fullmatch(r"[\w.+-]{1,80}", v or "") else ""
    _MEM[k] = (time.monotonic(), v)  # type: ignore[assignment]
    return v


def _file(language: str, version: str) -> Path:
    from .. import syntaxcards
    return syntaxcards.cache_dir() / f"codecat-{language}-{re.sub(r'[^\w.+-]', '_', version)}.json"


def build(language: str, timeout: float = 900) -> dict | None:
    """Run every sample with the installed tool; an entry is `failed` when one of its samples fails. Blocking."""
    from .. import syntaxcards
    py = _interp(language)
    if not py:
        return None
    version = tool_version(language)
    if not version:
        return None
    progs = sample_programs(language)
    req = {"samples": [[sid, code, chk] for sid, code, chk, _e in progs], "timeout": 60}
    t0 = time.monotonic()
    env = syntaxcards._sage_env(syntaxcards.cache_dir() / "work")
    env["MPLBACKEND"] = "Agg"
    try:
        p = subprocess.run([py, "-I", "-c", _RUN_SAGE if language == "sage" else _RUN_PY], input=json.dumps(req),
                           capture_output=True, text=True, timeout=timeout, env=env)
        out = p.stdout
    except (OSError, subprocess.SubprocessError) as e:
        log.info("catalogue build failed: %s", e)
        return None
    m = re.search(r"^MADALEAN_CODECAT (\{.*\})\s*$", out, re.M)
    if not m:
        log.warning("catalogue build (%s): no result", language)
        return None
    raw = json.loads(m.group(1))
    failed: dict[str, str] = {}
    passed: set[str] = set()
    samples = {}
    for sid, code, _chk, entries in progs:
        err = raw.get(sid, "missing")
        samples[sid] = err
        for e in entries:
            if err:
                failed.setdefault(e, f"{sid}: {err}"[:300])
            else:
                passed.add(e)
    data = {"tool": language, "version": version, "catalogue_version": CATALOGUE_VERSION, "built": time.time(),
            "seconds": round(time.monotonic() - t0, 1), "verified": sorted(passed - set(failed)),
            "failed": failed, "samples": samples, "versions": raw.get("_versions") or {}}
    if language == "python":
        data["sympy_names"] = raw.get("_sympy") or []
    f = _file(language, version)
    f.parent.mkdir(parents=True, exist_ok=True)
    config.atomic_write_text(f, json.dumps(data, ensure_ascii=False))
    _MEM.pop(f"cat:{language}:{version}", None)
    bad = [s for s, e in samples.items() if e]
    if bad:
        log.info("catalogue %s %s: %d sample(s) failed (%s)", language, version, len(bad), ", ".join(bad))
    return data


def status(language: str, version: str | None = None) -> dict | None:
    """The build of the installed tool version ({verified, failed, …}) or None when it is not built yet."""
    version = version if version is not None else tool_version(language)
    if not version:
        return None
    k = f"cat:{language}:{version}"
    hit = _MEM.get(k)
    if hit and time.monotonic() - hit[0] < 300:
        return hit[1]
    try:
        d = json.loads(_file(language, version).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        d = None
    if d is not None and (d.get("catalogue_version") != CATALOGUE_VERSION or d.get("version") != version):
        d = None
    _MEM[k] = (time.monotonic(), d)
    return d


# ---------------------------------------------------------------- Lean build
def _lean_file(ws) -> Path:
    from .. import syntaxcards
    return syntaxcards.cache_dir() / f"codecat-lean-{syntaxcards.lean_key(ws)}.json"


async def build_lean(ctx, ws) -> dict | None:
    """Compile every Lean entry (the flavor of this workspace's toolchain) in one file; an entry with an error is
    marked failed for this workspace."""
    from .. import leancheck
    from ..runtime.lean import workspace_info
    if ws is None or not ws.has_mathlib():
        return None
    flavor = lean_flavor(getattr(ws, "toolchain", ""))
    body, spans = lean_source(flavor)
    t0 = time.monotonic()
    res = await ctx.lean.check(body, ws, timeout_s=900, owner="code-catalogue")
    if res.infra_error or res.timed_out:
        log.info("Lean catalogue not built: %s", res.infra_error or "timeout")
        return None
    bad: dict[str, str] = {}
    msgs = list(res.verdict.errors) + [m for m in leancheck.parse_lean_json(res.stdout or "")
                                       if "deprecated" in (m.text or "")]
    for m in msgs:
        for eid, a, b in spans:
            if a <= (m.line or 0) <= b:
                bad.setdefault(eid, (m.text or "")[:200])
    info = workspace_info(ws) or {}
    data = {"tool": "lean", "workspace": ws.key, "flavor": flavor, "lean": info.get("lean", ""),
            "mathlib": info.get("mathlib", ""), "catalogue_version": CATALOGUE_VERSION, "built": time.time(),
            "seconds": round(time.monotonic() - t0, 1),
            "verified": sorted(e for e in LEAN_ENTRIES if e not in bad), "failed": bad}
    f = _lean_file(ws)
    f.parent.mkdir(parents=True, exist_ok=True)
    config.atomic_write_text(f, json.dumps(data, ensure_ascii=False))
    return data


def lean_status(ws) -> dict | None:
    try:
        d = json.loads(_lean_file(ws).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return d if d.get("catalogue_version") == CATALOGUE_VERSION else None


# ---------------------------------------------------------------- automatic builds (same hooks as syntaxcards)
_BUILDING: set[str] = set()


async def ensure(ctx=None) -> list[str]:
    """Build what is missing for the installed versions (Sage, kernel Python, each Lean workspace). Never raises."""
    done = []
    for lang in ("sage", "python"):
        try:
            v = await asyncio.to_thread(tool_version, lang)
            if not v or status(lang, v) is not None or f"{lang}:{v}" in _BUILDING:
                continue
            _BUILDING.add(f"{lang}:{v}")
            try:
                if await asyncio.to_thread(build, lang) is not None:
                    done.append(lang)
            finally:
                _BUILDING.discard(f"{lang}:{v}")
        except Exception:  # noqa: BLE001
            log.exception("code catalogue build (%s)", lang)
    if ctx is not None:
        try:
            for ws in list(getattr(ctx, "workspaces", None) or []):
                if ws.has_mathlib() and not ws.problems and lean_status(ws) is None and \
                        f"lean:{ws.key}" not in _BUILDING:
                    _BUILDING.add(f"lean:{ws.key}")
                    try:
                        if await build_lean(ctx, ws) is not None:
                            done.append(f"lean:{ws.key}")
                    finally:
                        _BUILDING.discard(f"lean:{ws.key}")
        except Exception:  # noqa: BLE001
            log.exception("code catalogue build (lean)")
    return done


def entries() -> dict:
    """The catalogue as data (for `GET /api/calcul/catalogue` and the docs): each sample's request, the code it
    assembles in Sage / Python, and the Lean constructions per flavor."""
    rows = []
    for req, sc, pc in SAMPLES:
        it = I.analyze(req)
        a_s = assemble(it, "sage")
        a_p = assemble(it, "python")
        rows.append({"request": req, "summary": I.summary(it, "fr"), "key": it.key(),
                     "sage": a_s.code if a_s and a_s.full else None,
                     "python": a_p.code if a_p and a_p.full else None})
    lean = {eid: {"doc": e["doc"], "default": lean_code(eid, "default"), "v4.9": lean_code(eid, "v4.9")}
            for eid, e in LEAN_ENTRIES.items()}
    return {"version": CATALOGUE_VERSION, "intent_version": I.INTENT_VERSION, "samples": rows, "lean": lean,
            "hash": hashlib.sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest()[:12]}
