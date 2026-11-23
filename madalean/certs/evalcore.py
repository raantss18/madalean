"""Exact evaluation of closed arithmetic trees (see expr.py for the tree format), with Lean's conventions.

Self-contained on purpose (standard library only, no `from __future__`): this file is also the first part of the
program that Madalean runs in the Sage sandbox (producer.py), so that Sage and the server agree on what a statement
means. Nothing here is trusted for a verdict: Lean decides."""
from fractions import Fraction


class Unsupported(ValueError):
    pass


MAX_BITS = 20000          # no closed value larger than this is computed here (≈ 6000 digits)


class TooBig(Unsupported):
    pass


def _check(v):
    n = v.numerator if isinstance(v, Fraction) else v
    d = v.denominator if isinstance(v, Fraction) else 1
    if abs(n).bit_length() > MAX_BITS or d.bit_length() > MAX_BITS:
        raise TooBig("number too large")
    return v


def number(text: str) -> Fraction:
    return Fraction(text)


def evaluate(e, dom: str, env: dict | None = None):
    """Exact value of a closed term with Lean's conventions for the domain: ℕ has truncated subtraction and floor
    division; ℤ has Euclidean division; x / 0 = 0 and x % 0 = x. Returns int (ℕ, ℤ) or Fraction (ℚ, ℝ). Terms with
    sqrt / exp / log / π are not closed for this function."""
    env = env or {}
    exact = dom in ("N", "Z")

    def ev(x):
        h = x[0]
        if h == "num":
            v = number(x[1])
            if exact:
                if v.denominator != 1:
                    raise Unsupported("decimal in an integer type")
                return int(v)
            return v
        if h == "var":
            if x[1] not in env:
                raise Unsupported("not closed")
            return env[x[1]]
        if h == "cast":
            return ev(x[2])
        if h == "neg":
            if dom == "N":
                raise Unsupported("negation in ℕ")
            return -ev(x[1])
        if h == "pow":
            b = ev(x[1])
            n = evaluate(x[2], "N", env)
            if n < 0:
                raise Unsupported("negative exponent")
            if b not in (0, 1, -1) and n * max(1, abs(b.numerator if isinstance(b, Fraction) else b).bit_length()) \
                    > MAX_BITS:
                raise TooBig("power too large")
            return _check(b ** n)
        if h in ("add", "sub", "mul", "div", "mod"):
            a, b = ev(x[1]), ev(x[2])
            if h == "add":
                return _check(a + b)
            if h == "mul":
                return _check(a * b)
            if h == "sub":
                return max(0, a - b) if dom == "N" else a - b
            if h == "div":
                if b == 0:
                    return 0 if exact else Fraction(0)
                if exact:
                    q = a // abs(b)
                    return q if b > 0 else -q
                return _check(a / b)
            if not exact:
                raise Unsupported("% outside ℕ and ℤ")
            return a if b == 0 else a % abs(b)
        if h == "call":
            args = [ev(a) for a in x[2]]
            if x[1] in ("gcd", "lcm") and exact:
                import math
                return math.gcd(*args) if x[1] == "gcd" else math.lcm(*args)
            if x[1] == "factorial" and dom == "N":
                import math
                if args[0] > 2000:
                    raise TooBig("factorial too large")
                return math.factorial(args[0])
            if x[1] == "choose" and dom == "N":
                import math
                if args[0] > 5000:
                    raise TooBig("binomial too large")
                return math.comb(args[0], args[1])
        raise Unsupported(f"cannot evaluate {h}")
    return ev(e)


def holds(p, dom: str, env: dict | None = None) -> bool:
    """Truth of a closed, quantifier-free proposition (same conventions as `evaluate`)."""
    h = p[0]
    if h == "true":
        return True
    if h == "false":
        return False
    if h == "not":
        return not holds(p[1], dom, env)
    if h == "and":
        return holds(p[1], dom, env) and holds(p[2], dom, env)
    if h == "or":
        return holds(p[1], dom, env) or holds(p[2], dom, env)
    if h == "imp":
        return (not holds(p[1], dom, env)) or holds(p[2], dom, env)
    if h == "iff":
        return holds(p[1], dom, env) == holds(p[2], dom, env)
    if h == "rel":
        a, b = evaluate(p[2], dom, env), evaluate(p[3], dom, env)
        return {"=": a == b, "!=": a != b, "<": a < b, "<=": a <= b, ">": a > b, ">=": a >= b}[p[1]]
    if h == "dvd":
        a, b = evaluate(p[1], dom, env), evaluate(p[2], dom, env)
        return b == 0 if a == 0 else b % a == 0
    if h == "modeq":
        d = "Z" if p[1] == "ZMOD" else "N"
        n, a, b = (evaluate(x, d, env) for x in p[2:5])
        return a == b if n == 0 else (a - b) % n == 0
    if h == "prime":
        n = evaluate(p[1], "N", env)
        if n.bit_length() > 4096:
            raise TooBig("number too large for a primality test")
        return is_prime(n)
    raise Unsupported(f"cannot decide {h}")


def is_prime(n: int) -> bool:
    """Deterministic Miller-Rabin for n < 3.3e24, plain trial division below 10^6 (only a pre-filter: Lean decides)."""
    if n < 2:
        return False
    small = (2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41)
    for q in small:
        if n % q == 0:
            return n == q
    d, s = n - 1, 0
    while d % 2 == 0:
        d, s = d // 2, s + 1
    for a in small:
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
