"""Polynomials with rational coefficients as plain dictionaries {exponents: Fraction} (session S-AT).

Used on the server side to read the arithmetic trees of a statement (degree, linearity) and to print the witnesses
that come back from Sage as Lean terms. The wire format between the server and the producer is
[[numerator, denominator, [e1, …, en]], …] with integers only."""
from __future__ import annotations

from fractions import Fraction

from .expr import LEAN_TYPE, Unsupported, evaluate, number

MAX_TERMS = 4000
MAX_DEGREE = 40

Poly = dict  # {tuple[int, ...]: Fraction}


def const(c, n: int) -> Poly:
    c = Fraction(c)
    return {(0,) * n: c} if c else {}


def var(i: int, n: int) -> Poly:
    return {tuple(1 if j == i else 0 for j in range(n)): Fraction(1)}


def add(a: Poly, b: Poly, sign: int = 1) -> Poly:
    out = dict(a)
    for m, c in b.items():
        v = out.get(m, 0) + sign * c
        if v:
            out[m] = v
        else:
            out.pop(m, None)
    return out


def mul(a: Poly, b: Poly) -> Poly:
    out: Poly = {}
    if len(a) * len(b) > MAX_TERMS * 4:
        raise Unsupported("polynomial too large")
    for m1, c1 in a.items():
        for m2, c2 in b.items():
            m = tuple(x + y for x, y in zip(m1, m2))
            v = out.get(m, 0) + c1 * c2
            if v:
                out[m] = v
            else:
                out.pop(m, None)
    if len(out) > MAX_TERMS:
        raise Unsupported("polynomial too large")
    return out


def power(a: Poly, k: int) -> Poly:
    if k < 0 or k > MAX_DEGREE:
        raise Unsupported("exponent out of range")
    n = len(next(iter(a))) if a else 0
    out = {(0,) * n: Fraction(1)} if a or k == 0 else {}
    if not a:
        return out if k == 0 else {}
    for _ in range(k):
        out = mul(out, a)
    return out


def scale(a: Poly, c) -> Poly:
    c = Fraction(c)
    return {m: v * c for m, v in a.items()} if c else {}


def degree(a: Poly) -> int:
    return max((sum(m) for m in a), default=0)


def is_const(a: Poly) -> bool:
    return all(not any(m) for m in a)


def constant(a: Poly) -> Fraction:
    return next((c for m, c in a.items() if not any(m)), Fraction(0))


def of_term(e, names: list[str], dom: str) -> Poly:
    """The polynomial of an arithmetic tree in the variables `names`. Refused: truncated subtraction (ℕ), integer
    division, `%`, division by anything but a non-zero constant, named functions, variable exponents."""
    n = len(names)

    def go(x) -> Poly:
        h = x[0]
        if h == "num":
            v = number(x[1])
            if dom in ("N", "Z") and v.denominator != 1:
                raise Unsupported("decimal in an integer type")
            return const(v, n)
        if h == "var":
            if x[1] not in names:
                raise Unsupported(f"unknown name {x[1]!r}")
            return var(names.index(x[1]), n)
        if h == "cast":
            return go(x[2])
        if h == "neg":
            if dom == "N":
                raise Unsupported("negation in ℕ")
            return scale(go(x[1]), -1)
        if h == "add":
            return add(go(x[1]), go(x[2]))
        if h == "sub":
            if dom == "N":
                raise Unsupported("subtraction in ℕ")
            return add(go(x[1]), go(x[2]), -1)
        if h == "mul":
            return mul(go(x[1]), go(x[2]))
        if h == "pow":
            return power(go(x[1]), int(evaluate(x[2], "N")))
        if h == "div":
            if dom not in ("Q", "R"):
                raise Unsupported("integer division")
            d = go(x[2])
            if not is_const(d) or not d:
                raise Unsupported("division by a non-constant")
            return scale(go(x[1]), 1 / constant(d))
        raise Unsupported(f"not a polynomial ({h})")
    return go(e)


def to_wire(a: Poly) -> list:
    return [[c.numerator, c.denominator, list(m)] for m, c in sorted(a.items(), reverse=True)]


def from_wire(data, n: int, max_terms: int = 400, max_digits: int = 400) -> Poly:
    """Strict reader of a polynomial sent back by the sandbox: integers only, bounded sizes."""
    if not isinstance(data, list) or len(data) > max_terms:
        raise Unsupported("bad polynomial")
    out: Poly = {}
    for t in data:
        if not (isinstance(t, list) and len(t) == 3 and isinstance(t[2], list) and len(t[2]) == n):
            raise Unsupported("bad polynomial term")
        num, den, exps = integer(t[0], max_digits), integer(t[1], max_digits), [integer(e, 3) for e in t[2]]
        if den <= 0 or any(e < 0 or e > MAX_DEGREE for e in exps):
            raise Unsupported("bad polynomial term")
        if num:
            m = tuple(exps)
            out[m] = out.get(m, 0) + Fraction(num, den)
    return {m: c for m, c in out.items() if c}


def integer(x, max_digits: int = 400) -> int:
    """An integer from untrusted JSON (an int, or a decimal string for big values); anything else is refused."""
    if isinstance(x, bool):
        raise Unsupported("bad integer")
    if isinstance(x, int):
        v = x
    elif isinstance(x, str) and len(x) <= max_digits + 1 and x.lstrip("-").isdigit() and x.count("-") <= 1 \
            and (x[0] == "-" or "-" not in x):
        v = int(x)
    else:
        raise Unsupported("bad integer")
    if len(str(abs(v))) > max_digits:
        raise Unsupported("integer too large")
    return v


def fraction(x, max_digits: int = 400) -> Fraction:
    """A rational from untrusted JSON: [numerator, denominator]."""
    if not (isinstance(x, list) and len(x) == 2):
        raise Unsupported("bad rational")
    num, den = integer(x[0], max_digits), integer(x[1], max_digits)
    if den <= 0:
        raise Unsupported("bad rational")
    return Fraction(num, den)


def lean_const(c: Fraction, dom: str) -> str:
    """A non-negative constant as a typed Lean term."""
    t = LEAN_TYPE[dom]
    return f"({c.numerator} : {t})" if c.denominator == 1 else f"(({c.numerator} : {t}) / {c.denominator})"


def lean(a: Poly, names: list[str], dom: str) -> str:
    """The polynomial as a Lean term of the domain, e.g. `(3 : ℝ) * x ^ 2 * y - ((1 : ℝ) / 2) * y + (5 : ℝ)`."""
    if not a:
        return f"(0 : {LEAN_TYPE[dom]})"
    parts = []
    for m, c in sorted(a.items(), reverse=True):
        mono = " * ".join((names[i] if e == 1 else f"{names[i]} ^ {e}") for i, e in enumerate(m) if e)
        k = lean_const(abs(c), dom)
        body = k if not mono else (mono if abs(c) == 1 else f"{k} * {mono}")
        parts.append((c < 0, body))
    out = ("-" if parts[0][0] else "") + parts[0][1]
    for neg, body in parts[1:]:
        out += (" - " if neg else " + ") + body
    return out


def text(a: Poly, names: list[str]) -> str:
    """Plain text for the witness shown to the user: `3*x^2*y - 1/2*y + 5`."""
    if not a:
        return "0"
    parts = []
    for m, c in sorted(a.items(), reverse=True):
        mono = "*".join((names[i] if e == 1 else f"{names[i]}^{e}") for i, e in enumerate(m) if e)
        k = str(abs(c))
        body = k if not mono else (mono if abs(c) == 1 else f"{k}*{mono}")
        parts.append((c < 0, body))
    out = ("-" if parts[0][0] else "") + parts[0][1]
    for neg, body in parts[1:]:
        out += (" - " if neg else " + ") + body
    return out
