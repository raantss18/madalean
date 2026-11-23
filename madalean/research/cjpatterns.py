"""Local pattern finders of the conjecture engine (S-AW, DECISIONS D55, docs/CONJECTURES.md §3).

Pure Python over exact rationals (`fractions.Fraction`), no network, no model, bounded sizes. Every finder fits on
a first part of the data and is VALIDATED on held-out terms it never saw; a fit that fails there is reported as
`discarded` with the first failing term (the journal keeps it). Nothing found here is a theorem: a finding carries
the range it was tested on, never « true ».

A table is `{"columns": [name, …], "rows": [[value, …], …]}`; values are integers, "p/q" strings or decimal
strings of integers (large integers travel as strings). A sequence is a table whose first column is the index
(consecutive integers) and whose other columns are values.

Finders (sequence): polynomial (finite differences + interpolation), rational function, linear recurrence with
constant coefficients (Berlekamp–Massey over ℚ) and its rational generating function, recurrence with polynomial
coefficients, algebraic generating function, multiplicativity, periodicity, congruences, primes / squares /
monotony, growth (floating point: marked heuristic). Finders (several columns): equalities, linear relations,
inequalities (tight ones first)."""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from fractions import Fraction as Fr

MAX_TERMS = 240                 # finders look at this many terms at most
MAX_BITS = 6000                 # … and skip the heavy linear algebra beyond this size of the entries
MIN_TERMS = 8
SURPLUS = 3                     # equations beyond the unknowns that a fit must satisfy before it is believed
EXACT = ("polynomial", "rational", "recurrence", "holonomic", "periodic", "constant")


# ---------------------------------------------------------------- values
def parse_value(v) -> Fr | None:
    """Exact rational of a cell (int, "12", "-3/4"); None for anything else (floats and symbols are not data)."""
    if isinstance(v, bool):
        return None
    if isinstance(v, int):
        return Fr(v)
    if isinstance(v, Fr):
        return v
    if isinstance(v, str):
        s = v.strip()
        if len(s) > 20000:
            return None
        try:
            if "/" in s:
                a, b = s.split("/", 1)
                return Fr(int(a), int(b))
            return Fr(int(s))
        except (ValueError, ZeroDivisionError):
            return None
    return None


def show(x: Fr) -> str:
    return str(x.numerator) if x.denominator == 1 else f"{x.numerator}/{x.denominator}"


def _bits(vals) -> int:
    return max((max(abs(x.numerator), x.denominator).bit_length() for x in vals), default=0)


@dataclass
class Seq:
    name: str
    n0: int
    vals: list[Fr]

    @property
    def n1(self) -> int:
        return self.n0 + len(self.vals) - 1

    def integral(self) -> bool:
        return all(x.denominator == 1 for x in self.vals)


@dataclass
class Finding:
    kind: str
    status: str = "kept"                    # kept | discarded
    columns: list[str] = field(default_factory=list)
    params: dict = field(default_factory=dict)
    tested: dict = field(default_factory=dict)   # {from, to, cases, fit, held_out}
    reason: str = ""                        # discarded: held_out | redundant | not_tight …
    detail: dict = field(default_factory=dict)
    heuristic: bool = False

    def to_dict(self) -> dict:
        return {"kind": self.kind, "status": self.status, "columns": self.columns, "params": self.params,
                "tested": self.tested, "reason": self.reason, "detail": self.detail, "heuristic": self.heuristic}


def table_columns(table: dict) -> dict[str, list[Fr | None]]:
    cols = [str(c) for c in table.get("columns") or []]
    out: dict[str, list[Fr | None]] = {c: [] for c in cols}
    for row in table.get("rows") or []:
        for i, c in enumerate(cols):
            out[c].append(parse_value(row[i]) if i < len(row) else None)
    return out


def sequences(table: dict) -> list[Seq]:
    """The value columns of a table indexed by consecutive integers (first column); [] when it is not one."""
    cols = table_columns(table)
    names = list(cols)
    if len(names) < 2:
        return []
    idx = cols[names[0]]
    if len(idx) < 2 or any(x is None or x.denominator != 1 for x in idx):
        return []
    if any(idx[i + 1] - idx[i] != 1 for i in range(len(idx) - 1)):
        return []
    out = []
    for c in names[1:]:
        v = cols[c]
        if all(x is not None for x in v):
            out.append(Seq(c, int(idx[0]), list(v)[:MAX_TERMS]))      # type: ignore[arg-type]
    return out


def split(n: int) -> tuple[int, int]:
    """(terms used to fit, terms held out): a quarter of the data, at least 3 terms, is never shown to a fit."""
    hold = max(3, n // 4)
    return n - hold, hold


# ---------------------------------------------------------------- exact linear algebra and polynomials
def nullspace(rows: list[list[Fr]], ncols: int) -> list[list[Fr]]:
    """Basis of {x : rows · x = 0} over ℚ (reduced row echelon form)."""
    m = [list(r) for r in rows]
    piv: list[int] = []
    r = 0
    for c in range(ncols):
        p = next((i for i in range(r, len(m)) if m[i][c] != 0), None)
        if p is None:
            continue
        m[r], m[p] = m[p], m[r]
        inv = 1 / m[r][c]
        m[r] = [x * inv for x in m[r]]
        for i in range(len(m)):
            if i != r and m[i][c] != 0:
                f = m[i][c]
                m[i] = [a - f * b for a, b in zip(m[i], m[r])]
        piv.append(c)
        r += 1
        if r == len(m):
            break
    free = [c for c in range(ncols) if c not in piv]
    basis = []
    for f in free:
        v = [Fr(0)] * ncols
        v[f] = Fr(1)
        for i, c in enumerate(piv):
            v[c] = -m[i][f]
        basis.append(v)
    return basis


def primitive(v: list[Fr]) -> list[int]:
    """The same vector up to a positive rational factor, with coprime integer entries."""
    den = 1
    for x in v:
        den = den * x.denominator // math.gcd(den, x.denominator)
    ints = [int(x * den) for x in v]
    g = 0
    for x in ints:
        g = math.gcd(g, x)
    return [x // g for x in ints] if g else ints


def poly_eval(coeffs, x):
    """Σ coeffs[k] · x^k (Horner)."""
    acc = Fr(0)
    for c in reversed(coeffs):
        acc = acc * x + c
    return acc


def poly_mul(a: list[Fr], b: list[Fr]) -> list[Fr]:
    out = [Fr(0)] * (len(a) + len(b) - 1) if a and b else []
    for i, x in enumerate(a):
        if x:
            for j, y in enumerate(b):
                out[i + j] += x * y
    return out


def poly_trim(a: list[Fr]) -> list[Fr]:
    a = list(a)
    while len(a) > 1 and a[-1] == 0:
        a.pop()
    return a


def interpolate(n0: int, vals: list[Fr]) -> list[Fr]:
    """Coefficients (in n, ascending) of the polynomial through (n0 + i, vals[i]) — Newton forward differences."""
    diffs, lead = list(vals), []
    while diffs:
        lead.append(diffs[0])
        diffs = [b - a for a, b in zip(diffs, diffs[1:])]
    out = [Fr(0)]
    basis = [Fr(1)]                                     # C(n - n0, k) as a polynomial in n
    for k, d in enumerate(lead):
        if d:
            out = [a + b for a, b in zip(out + [Fr(0)] * (len(basis) - len(out)),
                                         [d * c for c in basis] + [Fr(0)] * (len(out) - len(basis)))]
        basis = poly_mul(basis, [Fr(-(n0 + k), k + 1), Fr(1, k + 1)])
    return poly_trim(out)


def factor_linear(coeffs: list[Fr]) -> dict:
    """Content and small integer roots of a polynomial: {"content": "1/6", "roots": [0, -1], "rest": [...]} with
    p(n) = content · ∏ (n − r) · rest(n), rest primitive with integer coefficients."""
    ints = primitive(coeffs)
    lead = next((c for c in reversed(coeffs) if c), Fr(1))
    ilead = next((c for c in reversed(ints) if c), 1)
    content = lead / ilead
    rest, roots = [Fr(x) for x in ints], []
    for r in (0, -1, 1, -2, 2, -3, 3):
        while len(rest) > 1 and poly_eval(rest, Fr(r)) == 0:
            q, acc = [], Fr(0)                          # synthetic division by (n − r)
            for c in reversed(rest):
                acc = acc * r + c
                q.append(acc)
            q.pop()
            rest = list(reversed(q))
            roots.append(r)
    return {"content": show(content), "roots": roots, "rest": [show(x) for x in rest]}


# ---------------------------------------------------------------- sequence finders
def _tested(seq: Seq, fit: int, cases: int | None = None) -> dict:
    n = len(seq.vals)
    return {"from": seq.n0, "to": seq.n1, "cases": n if cases is None else cases, "fit": fit, "held_out": n - fit}


def _held_out_failure(seq: Seq, fit: int, predicted) -> dict | None:
    """First held-out index where `predicted(i)` (i = position) differs from the data."""
    for i in range(fit, len(seq.vals)):
        p = predicted(i)
        if p is None or p != seq.vals[i]:
            return {"n": seq.n0 + i, "expected": show(p) if p is not None else "", "got": show(seq.vals[i])}
    return None


def find_polynomial(seq: Seq, max_degree: int = 8) -> Finding | None:
    n = len(seq.vals)
    fit, _hold = split(n)
    diffs, d = seq.vals[:fit], 0
    while any(diffs):
        diffs = [b - a for a, b in zip(diffs, diffs[1:])]
        d += 1
    degree = max(d - 1, 0)
    if len(diffs) < SURPLUS or degree > max_degree:
        return None
    coeffs = interpolate(seq.n0, seq.vals[:degree + 1])
    kind = "constant" if degree == 0 else "polynomial"
    f = Finding(kind, columns=[seq.name], tested=_tested(seq, fit),
                params={"degree": degree, "coeffs": [show(c) for c in coeffs], "factored": factor_linear(coeffs)})
    bad = _held_out_failure(seq, fit, lambda i: poly_eval(coeffs, Fr(seq.n0 + i)))
    if bad:
        f.status, f.reason, f.detail = "discarded", "held_out", bad
    return f


def find_rational(seq: Seq) -> Finding | None:
    n = len(seq.vals)
    fit, _hold = split(n)
    for total in range(1, 5):
        for dq in range(1, total + 1):
            dp = total - dq
            unknowns = dp + dq + 2
            if fit < unknowns + SURPLUS:
                return None
            rows = []
            for i in range(fit):
                x = Fr(seq.n0 + i)
                rows.append([x ** e for e in range(dp + 1)] + [-seq.vals[i] * x ** e for e in range(dq + 1)])
            ns = nullspace(rows, unknowns)
            if len(ns) != 1:
                continue
            v = primitive(ns[0])
            p, q = [Fr(c) for c in v[:dp + 1]], [Fr(c) for c in v[dp + 1:]]
            if not any(q[1:]) or not any(p):
                continue
            if poly_trim(q)[-1] < 0:
                p, q = [-c for c in p], [-c for c in q]

            def pred(i, p=p, q=q):
                x = Fr(seq.n0 + i)
                den = poly_eval(q, x)
                return None if den == 0 else poly_eval(p, x) / den
            if any(pred(i) != seq.vals[i] for i in range(fit)):
                continue
            f = Finding("rational", columns=[seq.name], tested=_tested(seq, fit),
                        params={"num": [show(c) for c in poly_trim(p)], "den": [show(c) for c in poly_trim(q)]})
            bad = _held_out_failure(seq, fit, pred)
            if bad:
                f.status, f.reason, f.detail = "discarded", "held_out", bad
            return f
    return None


def berlekamp_massey(s: list[Fr]) -> list[Fr]:
    """Shortest connection polynomial C (C[0] = 1) with Σ_{i=0..L} C[i]·s[n−i] = 0 for all L ≤ n < len(s)."""
    c, b = [Fr(1)], [Fr(1)]
    length, m, bd = 0, 1, Fr(1)
    for n in range(len(s)):
        d = s[n] + sum((c[i] * s[n - i] for i in range(1, length + 1) if i < len(c)), Fr(0))
        if d == 0:
            m += 1
            continue
        t = list(c)
        coef = d / bd
        c = c + [Fr(0)] * (len(b) + m - len(c))
        for i, x in enumerate(b):
            c[i + m] -= coef * x
        if 2 * length <= n:
            length, b, bd, m = n + 1 - length, t, d, 1
        else:
            m += 1
    c = c + [Fr(0)] * (length + 1 - len(c))
    return c[:length + 1]


def find_recurrence(seq: Seq, max_order: int = 12) -> Finding | None:
    """a(n) = c₁ a(n−1) + … + c_L a(n−L) with constant rational coefficients, and the generating function P/Q."""
    n = len(seq.vals)
    fit, _hold = split(n)
    c = berlekamp_massey(seq.vals[:fit])
    order = len(c) - 1
    if order == 0 or order > max_order or 2 * order + SURPLUS > fit:
        return None
    coefs = [-x for x in c[1:]]                          # a(n) = Σ coefs[i-1] · a(n−i)
    q = poly_trim(list(c))
    p = poly_trim(poly_mul(q, seq.vals[:order])[:order]) if order else [Fr(0)]
    f = Finding("recurrence", columns=[seq.name], tested=_tested(seq, fit),
                params={"order": order, "coeffs": [show(x) for x in coefs],
                        "gf": {"num": [show(x) for x in p], "den": [show(x) for x in q], "offset": seq.n0}})

    def pred(i):
        return sum((coefs[k] * seq.vals[i - 1 - k] for k in range(order)), Fr(0))
    bad = _held_out_failure(seq, fit, pred)
    if bad:
        f.status, f.reason, f.detail = "discarded", "held_out", bad
    return f


HOLONOMIC_SHAPES = ((1, 1), (1, 2), (2, 1), (2, 2), (3, 1))


def find_holonomic(seq: Seq) -> Finding | None:
    """Σ_{i=0..r} p_i(n) · a(n+i) = 0 with polynomial coefficients of degree ≤ d (smallest shape first)."""
    n = len(seq.vals)
    fit, _hold = split(n)
    for r, d in HOLONOMIC_SHAPES:
        unknowns = (r + 1) * (d + 1)
        if fit - r < unknowns + SURPLUS:
            continue
        rows = []
        for j in range(fit - r):
            x = Fr(seq.n0 + j)
            rows.append([x ** e * seq.vals[j + i] for i in range(r + 1) for e in range(d + 1)])
        ns = nullspace(rows, unknowns)
        if len(ns) != 1:
            continue
        v = primitive(ns[0])
        polys = [v[i * (d + 1):(i + 1) * (d + 1)] for i in range(r + 1)]
        if not any(polys[r]) or not any(polys[0]):
            continue
        lead = next(c for c in reversed(polys[r]) if c)
        if lead < 0:
            polys = [[-c for c in p] for p in polys]
        f = Finding("holonomic", columns=[seq.name], tested=_tested(seq, fit),
                    params={"order": r, "degree": d, "polys": [[str(c) for c in p] for p in polys]})
        for j in range(fit - r, n - r):
            x = Fr(seq.n0 + j)
            if sum((poly_eval([Fr(c) for c in polys[i]], x) * seq.vals[j + i] for i in range(r + 1)), Fr(0)) != 0:
                f.status, f.reason = "discarded", "held_out"
                f.detail = {"n": seq.n0 + j + r, "expected": "", "got": show(seq.vals[j + r])}
                break
        return f
    return None


ALGEBRAIC_SHAPES = ((2, 1), (2, 2), (3, 1), (3, 2))


def find_algebraic_gf(seq: Seq) -> Finding | None:
    """P(x, A(x)) = 0 for the ordinary generating function A(x) = Σ a(n0 + k) x^k, degree in A ≥ 2."""
    n = len(seq.vals)
    fit, _hold = split(n)

    def powers(m: int, dy: int) -> list[list[Fr]]:
        s = seq.vals[:m]
        out = [[Fr(1)] + [Fr(0)] * (m - 1)]
        for _ in range(dy):
            out.append(poly_mul(out[-1], s)[:m])
        return out
    for dy, dx in ALGEBRAIC_SHAPES:
        unknowns = (dy + 1) * (dx + 1)
        if fit < unknowns + SURPLUS:
            continue
        pw = powers(fit, dy)
        rows = [[(pw[j][t - i] if t >= i else Fr(0)) for j in range(dy + 1) for i in range(dx + 1)]
                for t in range(fit)]
        ns = nullspace(rows, unknowns)
        if len(ns) != 1:
            continue
        v = primitive(ns[0])
        grid = [v[j * (dx + 1):(j + 1) * (dx + 1)] for j in range(dy + 1)]      # grid[j][i]: coefficient of x^i y^j
        if not any(any(g) for g in grid[2:]):
            continue                                                             # rational: Berlekamp–Massey's job
        f = Finding("algebraic_gf", columns=[seq.name], tested=_tested(seq, fit),
                    params={"coeffs": [[str(c) for c in g] for g in grid], "offset": seq.n0})
        pw = powers(n, dy)
        for t in range(fit, n):
            if sum((grid[j][i] * pw[j][t - i] for j in range(dy + 1) for i in range(dx + 1) if t >= i), Fr(0)) != 0:
                f.status, f.reason = "discarded", "held_out"
                f.detail = {"n": seq.n0 + t, "expected": "", "got": show(seq.vals[t])}
                break
        return f
    return None


def find_multiplicative(seq: Seq) -> Finding | None:
    """a(mn) = a(m)·a(n) for coprime m, n ≥ 2 (index from 1); `complete` when it holds for every pair."""
    at = {seq.n0 + i: v for i, v in enumerate(seq.vals) if seq.n0 + i >= 1}
    top = max(at, default=0)
    if at.get(1) != 1 or top < 12:
        return None
    pairs = [(m, k) for m in range(2, top // 2 + 1) for k in range(m, top // m + 1)]
    cop = [(m, k) for m, k in pairs if math.gcd(m, k) == 1]
    if len(cop) < 6:
        return None
    f = Finding("multiplicative", columns=[seq.name],
                tested={"from": 1, "to": top, "cases": len(cop), "fit": 0, "held_out": len(cop)})
    for m, k in cop:
        if at[m * k] != at[m] * at[k]:
            f.status, f.reason = "discarded", "counterexample"
            f.detail = {"m": m, "n": k, "expected": show(at[m] * at[k]), "got": show(at[m * k])}
            return f
    f.params = {"complete": all(at[m * k] == at[m] * at[k] for m, k in pairs)}
    return f


def find_periodic(seq: Seq) -> Finding | None:
    n = len(seq.vals)
    for p in range(1, n // 3 + 1):
        if all(seq.vals[i] == seq.vals[i + p] for i in range(n - p)):
            if p == 1:
                return None                              # constant: the polynomial finder says it
            return Finding("periodic", columns=[seq.name], tested=_tested(seq, 2 * p),
                           params={"period": p, "values": [show(x) for x in seq.vals[:p]]})
    return None


def find_congruence(seq: Seq) -> Finding | None:
    """All terms congruent modulo g: g = gcd of the differences (the strongest such statement)."""
    if not seq.integral() or len(seq.vals) < MIN_TERMS:
        return None
    a0 = int(seq.vals[0])
    g = 0
    for x in seq.vals[1:]:
        g = math.gcd(g, int(x) - a0)
    if g < 2:
        return None
    return Finding("congruence", columns=[seq.name], tested=_tested(seq, 0),
                   params={"modulus": g, "residue": a0 % g})


def find_residue_period(seq: Seq, moduli=(2, 3, 4, 5)) -> list[Finding]:
    out = []
    if not seq.integral():
        return out
    n = len(seq.vals)
    for m in moduli:
        res = [int(x) % m for x in seq.vals]
        if len(set(res)) < 2:
            continue
        for p in range(2, min(12, n // 3) + 1):
            if all(res[i] == res[i + p] for i in range(n - p)):
                out.append(Finding("residue_periodic", columns=[seq.name], tested=_tested(seq, 2 * p),
                                   params={"modulus": m, "period": p, "values": res[:p]}))
                break
        if len(out) == 2:
            break
    return out


_MR_BASES = (2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37)


def is_prime(n: int) -> bool | None:
    """Deterministic Miller–Rabin below 3.3·10²⁴; None beyond (not decided here)."""
    if n < 2:
        return False
    for p in _MR_BASES:
        if n % p == 0:
            return n == p
    if n >= 3317044064679887385961981:
        return None
    d, s = n - 1, 0
    while d % 2 == 0:
        d //= 2
        s += 1
    for a in _MR_BASES:
        x = pow(a, d, n)
        if x in (1, n - 1):
            continue
        for _ in range(s - 1):
            x = x * x % n
            if x == n - 1:
                break
        else:
            return False
    return True


def find_properties(seq: Seq, exact: bool) -> list[Finding]:
    out = []
    n = len(seq.vals)
    if seq.integral() and n >= MIN_TERMS:
        ints = [int(x) for x in seq.vals]
        if len(set(ints)) > 2 and all(is_prime(x) is True for x in ints):
            out.append(Finding("all_prime", columns=[seq.name], tested=_tested(seq, 0)))
        if not exact and len(set(ints)) > 2 and all(x >= 0 and math.isqrt(x) ** 2 == x for x in ints):
            out.append(Finding("all_square", columns=[seq.name], tested=_tested(seq, 0)))
    if not exact and n >= MIN_TERMS:
        if all(a < b for a, b in zip(seq.vals, seq.vals[1:])):
            out.append(Finding("increasing", columns=[seq.name], tested=_tested(seq, 0, n - 1),
                               params={"strict": True}))
    return out


def find_growth(seq: Seq) -> Finding | None:
    """Heuristic (floating point, least squares on the second half): a(n) ≈ C·rⁿ or a(n) ≈ C·n^α."""
    n = len(seq.vals)
    if n < 12 or any(x <= 0 for x in seq.vals):
        return None
    pts = [(seq.n0 + i, x) for i, x in enumerate(seq.vals)][n // 2:]
    if any(i <= 0 for i, _x in pts):
        return None

    def logf(x: Fr) -> float:
        return math.log(x.numerator) - math.log(x.denominator)

    def fit(xs: list[float], ys: list[float]) -> tuple[float, float, float]:
        k = len(xs)
        mx, my = sum(xs) / k, sum(ys) / k
        sxx = sum((x - mx) ** 2 for x in xs)
        syy = sum((y - my) ** 2 for y in ys)
        if sxx == 0 or syy == 0:
            return 0.0, my, 0.0
        slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx
        r2 = (slope * slope * sxx) / syy
        return slope, my - slope * mx, r2
    ys = [logf(x) for _i, x in pts]
    exp = fit([float(i) for i, _x in pts], ys)
    pw = fit([math.log(i) for i, _x in pts], ys)
    best, model = (exp, "exponential") if exp[2] >= pw[2] else (pw, "power")
    if best[2] < 0.9995 or abs(best[0]) < 1e-9:
        return None
    rate = math.exp(best[0]) if model == "exponential" else best[0]
    return Finding("growth", columns=[seq.name], heuristic=True, tested=_tested(seq, n - len(pts)),
                   params={"model": model, "rate": round(rate, 4), "constant": round(math.exp(best[1]), 4),
                           "r2": round(best[2], 6)})


def analyze_sequence(seq: Seq) -> list[Finding]:
    """Every finder on one sequence, in a fixed order; later finders are told what the exact ones found (a
    recurrence that only restates a polynomial is `discarded: redundant`, not hidden)."""
    out: list[Finding] = []
    if len(seq.vals) < MIN_TERMS:
        return out
    heavy = _bits(seq.vals) <= MAX_BITS
    poly = find_polynomial(seq)
    if poly:
        out.append(poly)
    have_poly = bool(poly and poly.status == "kept")
    rat = None
    if not have_poly and heavy:
        rat = find_rational(seq)
        if rat:
            out.append(rat)
    per = find_periodic(seq) if not have_poly else None
    if per:
        out.append(per)
    rec = find_recurrence(seq) if heavy else None
    if rec:
        if have_poly and rec.status == "kept":
            rec.status, rec.reason = "discarded", "redundant"
        elif per and rec.status == "kept":
            rec.status, rec.reason = "discarded", "redundant"
        out.append(rec)
    c_finite = have_poly or bool(per) or bool(rec and rec.status == "kept" and rec.reason == "")
    exact = c_finite or bool(rat and rat.status == "kept")
    if not exact and heavy:
        hol = find_holonomic(seq)
        if hol:
            out.append(hol)
        alg = find_algebraic_gf(seq)
        if alg:
            out.append(alg)
        exact = bool(hol and hol.status == "kept")
    mult = find_multiplicative(seq)
    if mult:
        monomial = have_poly and sum(1 for c in poly.params["coeffs"] if c != "0") <= 1       # type: ignore[union-attr]
        if monomial and mult.status == "kept":                  # n^k is multiplicative: nothing to conjecture
            mult.status, mult.reason = "discarded", "redundant"
        out.append(mult)
    if not per:
        cong = find_congruence(seq)
        if cong and not (have_poly and poly.kind == "constant"):                               # type: ignore[union-attr]
            out.append(cong)
    if not exact:
        out.extend(find_residue_period(seq))
    out.extend(find_properties(seq, exact))
    if not c_finite:
        g = find_growth(seq)
        if g:
            out.append(g)
    return out


# ---------------------------------------------------------------- several columns
def find_relations(table: dict, skip_first: bool = False, max_columns: int = 8) -> list[Finding]:
    """Equalities, linear relations and inequalities between the numeric columns of a table (every row is a case).
    `skip_first`: the first column is the index of a sequence (not a quantity to compare)."""
    cols = table_columns(table)
    names = [c for c in cols if all(x is not None for x in cols[c])]
    if skip_first and names and names[0] == (table.get("columns") or [""])[0]:
        names = names[1:]
    names = names[:max_columns]
    rows = len(next(iter(cols.values()), []))
    out: list[Finding] = []
    if len(names) < 2 or rows < MIN_TERMS:
        return out
    data = {c: cols[c] for c in names}
    fit, _hold = split(rows)
    varying = [c for c in names if len(set(data[c])) > 1]
    equal: set[frozenset] = set()
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            if data[a] == data[b]:
                equal.add(frozenset((a, b)))
                out.append(Finding("equal", columns=[a, b],
                                   tested={"from": 0, "to": rows - 1, "cases": rows, "fit": 0, "held_out": rows}))
    # exact linear relations c0 + Σ c_i·col_i = 0 (fitted on the first part, checked on the rest)
    lin_cols = [c for c in varying if not any(c in e and c != sorted(e)[0] for e in equal)][:6]
    if len(lin_cols) >= 2 and fit >= len(lin_cols) + 1 + SURPLUS:
        mat = [[Fr(1)] + [data[c][r] for c in lin_cols] for r in range(fit)]            # type: ignore[list-item]
        for v in nullspace(mat, len(lin_cols) + 1):
            ints = primitive(v)
            used = [c for c, k in zip(lin_cols, ints[1:]) if k]
            if len(used) < 2 or frozenset(used) in equal:
                continue
            if next(k for k in ints[1:] if k) < 0:
                ints = [-k for k in ints]
            f = Finding("linear", columns=used, tested={"from": 0, "to": rows - 1, "cases": rows, "fit": fit,
                                                        "held_out": rows - fit},
                        params={"constant": ints[0], "coeffs": {c: k for c, k in zip(lin_cols, ints[1:]) if k}})
            for r in range(fit, rows):
                if ints[0] + sum(k * data[c][r] for c, k in zip(lin_cols, ints[1:])) != 0:     # type: ignore[operator]
                    f.status, f.reason, f.detail = "discarded", "held_out", {"row": r}
                    break
            out.append(f)
    # inequalities a ≤ b + d, d ∈ {0, 1}; the tight ones (equality reached) are kept, the others journalled
    le: dict[tuple[str, str], int] = {}
    for a in varying:
        for b in varying:
            if a == b or frozenset((a, b)) in equal:
                continue
            gaps = [data[a][r] - data[b][r] for r in range(rows)]                         # type: ignore[operator]
            if len(set(gaps)) == 1:
                continue                                                                   # b = a + constant: linear
            d = max(gaps)
            if d in (0, 1) and all(g.denominator == 1 for g in gaps):
                le[(a, b)] = int(d)
    for (a, b), d in le.items():
        if d == 1 and (b, a) in le:
            continue
        if d == 0 and any(le.get((a, c)) == 0 and le.get((c, b)) == 0 for c in varying if c not in (a, b)):
            out.append(Finding("inequality", "discarded", [a, b], {"offset": d}, reason="redundant",
                               tested={"from": 0, "to": rows - 1, "cases": rows, "fit": 0, "held_out": rows}))
            continue
        tight = sum(1 for r in range(rows) if data[a][r] - data[b][r] == d)               # type: ignore[operator]
        strict = d == 0 and tight == 0
        out.append(Finding("inequality", columns=[a, b],
                           params={"offset": d, "tight": tight, "strict": strict},
                           tested={"from": 0, "to": rows - 1, "cases": rows, "fit": 0, "held_out": rows}))
    return out


def analyze(table: dict) -> list[dict]:
    """All findings of a table, kept and discarded, as JSON-able dicts."""
    out: list[Finding] = []
    seqs = sequences(table)
    for s in seqs:
        out.extend(analyze_sequence(s))
    if seqs:
        if len(seqs) >= 2:
            out.extend(find_relations(table, skip_first=True))
    else:
        out.extend(find_relations(table))
    return [f.to_dict() for f in out]


# ---------------------------------------------------------------- re-checking a finding on new data (the hunt)
def hunt_indices(kind: str, params: dict, lo: int, hi: int, seed: int = 0, budget: int = 400) -> list[int]:
    """Where to look for a counter-example of a sequence finding beyond the tested range: a block right after the
    tested range, then structured indices (powers of two, primes, highly divisible numbers) and random ones, each
    with the neighbours a recurrence needs. Deterministic for a given seed."""
    rng = random.Random(seed)
    width = {"recurrence": int(params.get("order", 1)), "holonomic": int(params.get("order", 1)),
             "increasing": 1}.get(kind, 0)
    picks: set[int] = set(range(lo, min(hi, lo + budget // 2) + 1))
    if kind == "multiplicative":
        base = [m for m in range(2, max(3, math.isqrt(hi)) + 1)]
        rng.shuffle(base)
        for m in base[:40]:
            for k in rng.sample(range(2, max(3, hi // m) + 1), min(6, max(1, hi // m - 1))):
                if m * k <= hi:
                    picks.update((m, k, m * k))
        return sorted(p for p in picks if 1 <= p <= hi)[:budget * 2]
    structured = [2 ** k for k in range(1, 40)] + [2 ** k - 1 for k in range(2, 40)] + \
                 [math.factorial(k) for k in range(2, 12)] + [p for p in range(lo, hi + 1) if is_prime(p)][:30]
    rand = [rng.randint(lo, hi) for _ in range(budget // 4)] if hi > lo else []
    for c in structured + rand:
        if lo <= c <= hi:
            picks.update(range(c, min(hi, c + width) + 1))
        if len(picks) >= budget:
            break
    return sorted(picks)[:budget + width]


def check(finding: dict, values: dict[str, dict[int, Fr]]) -> tuple[int, dict | None]:
    """Test a sequence finding on `values[column][n]` (any set of indices). Returns (cases tested, first violation
    or None). A violation is {"n": …, "expected": …, "got": …} (or m, n for multiplicativity)."""
    kind, p = finding["kind"], finding.get("params") or {}
    cols = finding.get("columns") or []
    a = values.get(cols[0], {}) if cols else {}
    cases = 0
    if kind in ("polynomial", "constant"):
        cf = [parse_value(c) for c in p["coeffs"]]
        for n in sorted(a):
            cases += 1
            e = poly_eval(cf, Fr(n))
            if a[n] != e:
                return cases, {"n": n, "expected": show(e), "got": show(a[n])}
    elif kind == "rational":
        num, den = [parse_value(c) for c in p["num"]], [parse_value(c) for c in p["den"]]
        for n in sorted(a):
            cases += 1
            d = poly_eval(den, Fr(n))
            e = None if d == 0 else poly_eval(num, Fr(n)) / d
            if e is None or a[n] != e:
                return cases, {"n": n, "expected": show(e) if e is not None else "", "got": show(a[n])}
    elif kind == "recurrence":
        cf = [parse_value(c) for c in p["coeffs"]]
        for n in sorted(a):
            if all(n - i in a for i in range(1, len(cf) + 1)):
                cases += 1
                e = sum((cf[i - 1] * a[n - i] for i in range(1, len(cf) + 1)), Fr(0))
                if a[n] != e:
                    return cases, {"n": n, "expected": show(e), "got": show(a[n])}
    elif kind == "holonomic":
        polys = [[Fr(int(c)) for c in q] for q in p["polys"]]
        r = len(polys) - 1
        for n in sorted(a):
            if all(n + i in a for i in range(r + 1)):
                cases += 1
                if sum((poly_eval(polys[i], Fr(n)) * a[n + i] for i in range(r + 1)), Fr(0)) != 0:
                    return cases, {"n": n + r, "expected": "", "got": show(a[n + r])}
    elif kind == "periodic":
        per, vals = int(p["period"]), [parse_value(v) for v in p["values"]]
        n0 = int(finding.get("tested", {}).get("from", 0))
        for n in sorted(a):
            cases += 1
            e = vals[(n - n0) % per]
            if a[n] != e:
                return cases, {"n": n, "expected": show(e), "got": show(a[n])}
    elif kind == "congruence":
        g, res = int(p["modulus"]), int(p["residue"])
        for n in sorted(a):
            cases += 1
            if a[n].denominator != 1 or int(a[n]) % g != res:
                return cases, {"n": n, "expected": f"{res} (mod {g})", "got": show(a[n])}
    elif kind == "residue_periodic":
        m, per, vals = int(p["modulus"]), int(p["period"]), p["values"]
        n0 = int(finding.get("tested", {}).get("from", 0))
        for n in sorted(a):
            cases += 1
            if a[n].denominator != 1 or int(a[n]) % m != vals[(n - n0) % per]:
                return cases, {"n": n, "expected": f"{vals[(n - n0) % per]} (mod {m})", "got": show(a[n])}
    elif kind == "multiplicative":
        for m in sorted(a):
            for k in sorted(a):
                if 2 <= m <= k and m * k in a and (p.get("complete") or math.gcd(m, k) == 1):
                    cases += 1
                    if a[m * k] != a[m] * a[k]:
                        return cases, {"m": m, "n": k, "expected": show(a[m] * a[k]), "got": show(a[m * k])}
    elif kind == "all_prime":
        for n in sorted(a):
            cases += 1
            if a[n].denominator != 1 or is_prime(int(a[n])) is False:
                return cases, {"n": n, "expected": "", "got": show(a[n])}
    elif kind == "all_square":
        for n in sorted(a):
            cases += 1
            x = a[n]
            if x.denominator != 1 or x < 0 or math.isqrt(int(x)) ** 2 != int(x):
                return cases, {"n": n, "expected": "", "got": show(x)}
    elif kind == "increasing":
        for n in sorted(a):
            if n + 1 in a:
                cases += 1
                if not a[n] < a[n + 1]:
                    return cases, {"n": n, "expected": "", "got": show(a[n + 1])}
    elif kind in ("equal", "inequality") and len(cols) == 2:
        b = values.get(cols[1], {})
        d = int(p.get("offset", 0))
        for n in sorted(a):
            if n in b:
                cases += 1
                okay = a[n] == b[n] if kind == "equal" else a[n] <= b[n] + d
                if not okay:
                    return cases, {"n": n, "expected": show(b[n]), "got": show(a[n])}
    return cases, None


def check_rows(finding: dict, table: dict) -> tuple[int, dict | None]:
    """Test a relation between columns (equal / linear / inequality) on every row of a table of objects."""
    kind, p = finding["kind"], finding.get("params") or {}
    cols = table_columns(table)
    names = finding.get("columns") or []
    if any(c not in cols for c in names):
        return 0, None
    rows = len(cols[names[0]]) if names else 0
    for r in range(rows):
        vals = [cols[c][r] for c in names]
        if any(v is None for v in vals):
            continue
        if kind == "equal":
            okay = vals[0] == vals[1]
        elif kind == "inequality":
            okay = vals[0] <= vals[1] + int(p.get("offset", 0))                     # type: ignore[operator]
        elif kind == "linear":
            okay = int(p["constant"]) + sum(int(k) * cols[c][r] for c, k in p["coeffs"].items()) == 0   # type: ignore
        else:
            return 0, None
        if not okay:
            return r + 1, {"row": r, "values": {c: show(v) for c, v in zip(names, vals)},      # type: ignore[arg-type]
                           "object": str((table.get("rows") or [])[r][-1]) if table.get("labels") else ""}
    return rows, None
