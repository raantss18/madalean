"""« Certifier avec Lean » in Calcul (session S-AT, DECISIONS D52): from a Sage cell and its result to a Lean
statement that a certificate kind can prove.

Only the TEXT of the cell and of its output is read here (a strict reader of integer expressions): nothing is
executed. The statement says what the cell computed — `factor(n)` → n is prime / n = p₁^e₁ · … (with the primality
of the factors when they are small), `is_prime`, `gcd`, `lcm`, `xgcd`, `power_mod`, `inverse_mod`, `factorial`,
`binomial`, or a plain integer expression. Other cells are not supported (the caller says so)."""
from __future__ import annotations

import re

from . import expr as E
from . import pratt

OPS = ("factor", "is_prime", "is_pseudoprime", "gcd", "lcm", "xgcd", "power_mod", "inverse_mod", "factorial",
       "binomial", "next_prime")
_ASSIGN = re.compile(r"^([A-Za-z_]\w*)\s*=\s*([-+*/^()\d\s]+)$")
_CALL = re.compile(r"^([A-Za-z_]\w*)\s*\((.*)\)$", re.S)
_PRINT = re.compile(r"^(?:print|show|pretty_print)\s*\((.*)\)$", re.S)
_INTEXPR = re.compile(r"^[-+*^()\d\s]+$")
_FACTORS = re.compile(r"^\s*(-1\s*\*\s*)?\d+(\^\d+)?(\s*\*\s*\d+(\^\d+)?)*\s*$")


def _lines(code: str) -> list[str]:
    return [ln.strip() for ln in (code or "").split("\n") if ln.strip() and not ln.lstrip().startswith("#")]


def _term(text: str, env: dict):
    """An integer expression of the cell (digits, + - * ^ and names assigned earlier) as a tree; None otherwise."""
    t = text.strip().replace("**", "^")
    for name, val in env.items():
        t = re.sub(rf"\b{re.escape(name)}\b", f"({val})", t)
    if not t or not _INTEXPR.match(t) or len(t) > 600:
        return None
    try:
        return E.parse_term(t)
    except E.Unsupported:
        return None


def _split_args(text: str) -> list[str]:
    out, depth, cur = [], 0, ""
    for ch in text:
        if ch == "," and depth == 0:
            out.append(cur)
            cur = ""
            continue
        depth += ch == "("
        depth -= ch == ")"
        cur += ch
    return out + [cur] if cur.strip() else out


def _nat(e) -> int | None:
    try:
        v = E.evaluate(e, "Z")
    except E.Unsupported:
        return None
    return v


def statement_for(code: str, output: str) -> tuple[str, str] | None:
    """(`: PROPOSITION` to put after a theorem name, short description in words) or None when unsupported."""
    lines = _lines(code)
    if not lines or len(code) > 20000:
        return None
    env: dict[str, str] = {}
    for ln in lines[:-1]:
        m = _ASSIGN.match(ln)
        if m and _term(m.group(2), env) is not None:
            env[m.group(1)] = m.group(2).strip().replace("**", "^")
    last = lines[-1]
    pm = _PRINT.match(last)
    if pm:
        last = pm.group(1).strip()
    out = " ".join((output or "").split())
    m = _CALL.match(last)
    if m and m.group(1) in OPS:
        op = m.group(1)
        args = [_term(a, env) for a in _split_args(m.group(2))]
        if not args or any(a is None for a in args):
            return None
        vals = [_nat(a) for a in args]
        if any(v is None or v < 0 for v in vals):
            return None
        txt = [E.lean(a, False) for a in args]
        if op in ("is_prime", "is_pseudoprime") and len(args) == 1 and out in ("True", "False"):
            return (f": Nat.Prime {txt[0]}", "prime") if out == "True" else (f": ¬ Nat.Prime {txt[0]}", "composite")
        if op == "factor" and len(args) == 1 and _FACTORS.match(out) and vals[0] > 1 and not out.startswith("-"):
            fs = [(int(a), int(b or 1)) for a, b in re.findall(r"(\d+)(?:\^(\d+))?", out)]
            if len(fs) == 1 and fs[0][1] == 1:
                return f": Nat.Prime {txt[0]}", "prime"
            prod = " * ".join(f"{p} ^ {k}" if k > 1 else str(p) for p, k in fs)
            small = all(p < pratt.SMALL for p, _k in fs)
            primes = "".join(f"Nat.Prime {p} ∧ " for p, _k in fs) if small else ""
            return f": {primes}({txt[0]} : ℕ) = {prod}", "factorisation" if small else "product"
        if op in ("gcd", "lcm") and len(args) == 2 and out.isdigit():
            return f": Nat.{op} {txt[0]} {txt[1]} = {out}", op
        if op == "factorial" and len(args) == 1 and out.isdigit() and vals[0] <= 400:
            return f": Nat.factorial {txt[0]} = {out}", op
        if op == "binomial" and len(args) == 2 and out.isdigit() and vals[0] <= 2000:
            return f": Nat.choose {txt[0]} {txt[1]} = {out}", op
        if op == "power_mod" and len(args) == 3 and out.isdigit() and args[0][0] == "num" and args[2][0] == "num":
            return f": {txt[0]} ^ {txt[1]} % {txt[2]} = {out}", op
        if op == "inverse_mod" and len(args) == 2 and out.isdigit():
            return f": {txt[0]} * {out} % {txt[1]} = 1", op
        if op == "next_prime" and len(args) == 1 and out.isdigit():
            return f": Nat.Prime {out}", "prime"
        if op == "xgcd" and len(args) == 2:
            mm = re.fullmatch(r"\(\s*(-?\d+)\s*,\s*(-?\d+)\s*,\s*(-?\d+)\s*\)", out)
            if mm:
                g, s, t = mm.groups()
                return f": ({txt[0]} : ℤ) * ({s}) + {txt[1]} * ({t}) = {g}", op
        return None
    e = _term(last, env)
    if e is not None and re.fullmatch(r"\d+", out) and E.heads(e) - {"num"}:
        try:
            if E.evaluate(e, "N") != int(out):          # ℕ and Sage disagree (a negative intermediate value)
                return None
        except E.Unsupported:
            return None
        return f": ({E.lean(e)} : ℕ) = {out}", "value"
    return None
