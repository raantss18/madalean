"""A small reader for the arithmetic part of Lean statements (session S-AT, DECISIONS D52).

Only what the certificate kinds need: numerals, variables, `+ - * / % ^`, a few named functions, relations,
congruences, divisibility, `Nat.Prime`, `¬ ∧ ∨ → ↔`, `∃` / `∀` binders. Everything else raises `Unsupported` — the
statement then simply has no certificate kind and goes to the usual provers.

The result is a tree of tuples (JSON-serialisable). It is the ONLY thing that reaches Sage: the producer rebuilds
its objects from the tree, node by node; no text of the statement is ever evaluated as code.

    term  ("num", "12") | ("var", "x") | ("add"|"sub"|"mul"|"div"|"mod"|"pow", a, b) | ("neg", a)
          | ("call", name, [args]) | ("cast", type, a)
    prop  ("rel", op, a, b) with op in = != < <= > >= | ("modeq", "MOD"|"ZMOD", n, a, b) | ("dvd", a, b)
          | ("prime", a) | ("not", p) | ("and"|"or"|"imp"|"iff", p, q) | ("true",) | ("false",)
          | ("exists"|"forall", [(name, type)], p) | ("ball", name, type, bound_rel, bound_term, p)
"""
from __future__ import annotations

import re
from fractions import Fraction

from .evalcore import MAX_BITS, TooBig, Unsupported, evaluate, holds, is_prime, number  # noqa: F401

TYPES = {"ℕ": "N", "Nat": "N", "ℤ": "Z", "Int": "Z", "ℚ": "Q", "Rat": "Q", "ℝ": "R", "Real": "R"}
LEAN_TYPE = {"N": "ℕ", "Z": "ℤ", "Q": "ℚ", "R": "ℝ"}
# name in the statement -> (canonical name, number of arguments)
FUNCS = {"Nat.gcd": ("gcd", 2), "Int.gcd": ("gcd", 2), "gcd": ("gcd", 2), "Nat.lcm": ("lcm", 2), "Int.lcm": ("lcm", 2),
         "lcm": ("lcm", 2), "Nat.factorial": ("factorial", 1), "factorial": ("factorial", 1),
         "Nat.choose": ("choose", 2), "choose": ("choose", 2),
         "Real.sqrt": ("sqrt", 1), "sqrt": ("sqrt", 1), "√": ("sqrt", 1), "Real.exp": ("exp", 1), "rexp": ("exp", 1),
         "exp": ("exp", 1), "Real.log": ("log", 1), "log": ("log", 1)}
CONSTS = {"Real.pi": "pi", "π": "pi"}
PRIME = {"Nat.Prime", "Prime"}
REL = {"=": "=", "≠": "!=", "<": "<", "≤": "<=", "<=": "<=", ">": ">", "≥": ">=", ">=": ">="}
REAL_ONLY = {"sqrt", "exp", "log", "pi"}
MAX_LEN = 6000


_TOKEN = re.compile(
    r"\s*(?:(?P<num>\d+(?:\.\d+)?)"
    r"|(?P<modeq>\[\s*(?:MOD|ZMOD)\b)"
    r"|(?P<id>[^\W\d][\w'₀-₉]*(?:\.[^\W\d][\w'₀-₉]*)*)"
    r"|(?P<sym><=|>=|[-+*/^%():,=≠<≤>≥∣¬∧∨→↔∃∀≡\]√π!·]))", re.U)


def tokenize(text: str) -> list[tuple[str, str]]:
    if len(text) > MAX_LEN:
        raise Unsupported("too long")
    out, i, text = [], 0, text.rstrip()
    while i < len(text):
        m = _TOKEN.match(text, i)
        if not m:
            raise Unsupported(f"token at {text[i:i + 12]!r}")
        i = m.end()
        kind = m.lastgroup
        val = m.group(kind)
        if kind == "modeq":
            val = "ZMOD" if "ZMOD" in val else "MOD"
        elif kind == "sym" and val == "·":
            val = "*"
        elif kind == "id" and val in ("π",):
            kind = "sym"
        out.append((kind, val))
    return out


class Parser:
    def __init__(self, text: str):
        self.toks = tokenize(text)
        self.i = 0

    # ------------------------------------------------------------ helpers
    def peek(self, k: int = 0) -> tuple[str, str]:
        j = self.i + k
        return self.toks[j] if j < len(self.toks) else ("end", "")

    def next(self) -> tuple[str, str]:
        t = self.peek()
        self.i += 1
        return t

    def at(self, *syms: str) -> bool:
        k, v = self.peek()
        return k in ("sym", "modeq") and v in syms

    def eat(self, sym: str) -> None:
        if not self.at(sym):
            raise Unsupported(f"expected {sym!r}, got {self.peek()[1]!r}")
        self.i += 1

    def done(self) -> bool:
        return self.i >= len(self.toks)

    # ------------------------------------------------------------ propositions
    def prop(self):
        return self._iff()

    def _iff(self):
        a = self._imp()
        if self.at("↔"):
            self.next()
            return ("iff", a, self._imp())
        return a

    def _imp(self):
        a = self._or()
        if self.at("→"):
            self.next()
            return ("imp", a, self._imp())
        return a

    def _or(self):
        a = self._and()
        if self.at("∨"):
            self.next()
            return ("or", a, self._or())
        return a

    def _and(self):
        a = self._not()
        if self.at("∧"):
            self.next()
            return ("and", a, self._and())
        return a

    def _not(self):
        if self.at("¬"):
            self.next()
            return ("not", self._not())
        if self.at("∃", "∀"):
            return self._binder()
        return self._atom_prop()

    def _binder(self):
        q = "exists" if self.next()[1] == "∃" else "forall"
        groups: list[tuple[str, str]] = []
        bound = None
        while True:
            paren = self.at("(")
            if paren:
                self.next()
            names = []
            while self.peek()[0] == "id" and self.peek()[1] not in TYPES:
                names.append(self.next()[1])
            if not names:
                raise Unsupported("binder names")
            typ = ""
            if self.at(":"):
                self.next()
                k, v = self.next()
                if v not in TYPES:
                    raise Unsupported(f"binder type {v!r}")
                typ = TYPES[v]
            elif not paren and len(names) == 1 and self.at("<", "≤", "<=") and q == "forall":
                op = REL[self.next()[1]]
                bound = (names[0], op, self.term())      # ∀ n < 10, P n   (the type comes from the bound: ℕ)
            if paren:
                self.eat(")")
            groups += [(n, typ) for n in names]
            if self.at(","):
                self.next()
                break
            if bound is not None or not self.at("("):
                raise Unsupported("binder syntax")
        body = self.prop()
        if bound is not None:
            return ("ball", bound[0], "", bound[1], bound[2], body)
        if any(not t for _n, t in groups):
            # `∃ x y, …` without a type: Lean infers it; we only accept explicit types
            raise Unsupported("binder without a type")
        return (q, [list(g) for g in groups], body)

    def _atom_prop(self):
        k, v = self.peek()
        if k == "id" and v in ("True", "False"):
            self.next()
            return ("true",) if v == "True" else ("false",)
        if k == "id" and v in PRIME:
            self.next()
            return ("prime", self._arg())
        if self.at("("):
            # a parenthesised proposition or the start of a term: try the proposition first
            save = self.i
            try:
                self.next()
                p = self.prop()
                self.eat(")")
                if not (self.at("+", "-", "*", "/", "^", "%", "=", "≠", "<", "≤", ">", "≥", "<=", ">=", "∣", "≡", "!")
                        or self.peek()[0] in ("num", "id")) and p[0] in PROP_HEADS:
                    return p
            except Unsupported:
                pass
            self.i = save
        a = self.term()
        if self.at("∣"):
            self.next()
            return ("dvd", a, self.term())
        if self.at("≡"):
            self.next()
            b = self.term()
            k, v = self.next()
            if k != "modeq":
                raise Unsupported("congruence")
            n = self.term()
            self.eat("]")
            return ("modeq", v, n, a, b)
        k, v = self.peek()
        if k == "sym" and v in REL:
            self.next()
            b = self.term()
            if self.peek()[0] == "sym" and self.peek()[1] in REL:
                raise Unsupported("chained relation")
            return ("rel", REL[v], a, b)
        raise Unsupported(f"not a proposition near {v!r}")

    # ------------------------------------------------------------ terms
    def term(self):
        a = self._mul()
        while self.at("+", "-"):
            op = self.next()[1]
            a = ("add" if op == "+" else "sub", a, self._mul())
        return a

    def _mul(self):
        a = self._unary()
        while self.at("*", "/", "%"):
            op = self.next()[1]
            a = ({"*": "mul", "/": "div", "%": "mod"}[op], a, self._unary())
        return a

    def _unary(self):
        if self.at("-"):
            self.next()
            return ("neg", self._unary())
        return self._pow()

    def _pow(self):
        a = self._postfix()
        if self.at("^"):
            self.next()
            return ("pow", a, self._unary())       # right associative; `2 ^ -1` is refused later
        return a

    def _postfix(self):
        a = self._app()
        while self.at("!"):
            self.next()
            a = ("call", "factorial", [a])
        return a

    def _app(self):
        k, v = self.peek()
        if k == "sym" and v == "√":
            self.next()
            return ("call", "sqrt", [self._arg()])
        if k == "id" and v in FUNCS:
            name, n = FUNCS[v]
            self.next()
            return ("call", name, [self._arg() for _ in range(n)])
        return self._arg()

    def _arg(self):
        k, v = self.next()
        if k == "num":
            return ("num", v)
        if k == "sym" and v == "π":
            return ("call", "pi", [])
        if k == "id":
            if v in CONSTS:
                return ("call", CONSTS[v], [])
            if v in FUNCS or v in PRIME or v in TYPES or "." in v:
                raise Unsupported(f"name {v!r}")
            return ("var", v)
        if k == "sym" and v == "(":
            a = self.term()
            if self.at(":"):
                self.next()
                tk, tv = self.next()
                if tv not in TYPES:
                    raise Unsupported(f"type {tv!r}")
                a = ("cast", TYPES[tv], a)
            self.eat(")")
            return a
        raise Unsupported(f"unexpected {v!r}")


PROP_HEADS = {"rel", "modeq", "dvd", "prime", "not", "and", "or", "imp", "iff", "true", "false", "exists", "forall",
              "ball"}


def parse_prop(text: str):
    p = Parser(text)
    out = p.prop()
    if not p.done():
        raise Unsupported(f"trailing {p.peek()[1]!r}")
    return out


def parse_term(text: str):
    p = Parser(text)
    out = p.term()
    if not p.done():
        raise Unsupported(f"trailing {p.peek()[1]!r}")
    return out


# ---------------------------------------------------------------- walking
def is_term(e) -> bool:
    return e[0] in ("num", "var", "add", "sub", "mul", "div", "mod", "pow", "neg", "call", "cast")


def children(e) -> list:
    h = e[0]
    if h in ("num", "var", "true", "false"):
        return []
    if h == "call":
        return list(e[2])
    if h == "cast":
        return [e[2]]
    if h == "rel":
        return [e[2], e[3]]
    if h == "modeq":
        return [e[2], e[3], e[4]]
    if h in ("exists", "forall"):
        return [e[2]]
    if h == "ball":
        return [e[4], e[5]]
    return list(e[1:])


def walk(e):
    yield e
    for c in children(e):
        yield from walk(c)


def variables(e) -> list[str]:
    """Free variables, in order of first appearance."""
    out: list[str] = []

    def go(x, bound: frozenset):
        if x[0] == "var":
            if x[1] not in bound and x[1] not in out:
                out.append(x[1])
        elif x[0] in ("exists", "forall"):
            go(x[2], bound | {n for n, _t in x[1]})
        elif x[0] == "ball":
            go(x[4], bound)
            go(x[5], bound | {x[1]})
        else:
            for c in children(x):
                go(c, bound)
    go(e, frozenset())
    return out


def heads(e) -> set[str]:
    return {x[0] for x in walk(e)}


def calls(e) -> set[str]:
    return {x[1] for x in walk(e) if x[0] == "call"}


def casts(e) -> set[str]:
    return {x[1] for x in walk(e) if x[0] == "cast"}


def strip_casts(e):
    """The same tree without type ascriptions (used once the domain is known)."""
    if e[0] == "cast":
        return strip_casts(e[2])
    if e[0] in ("num", "var", "true", "false"):
        return e
    if e[0] == "call":
        return ("call", e[1], [strip_casts(a) for a in e[2]])
    if e[0] == "rel":
        return ("rel", e[1], strip_casts(e[2]), strip_casts(e[3]))
    if e[0] == "modeq":
        return ("modeq", e[1], strip_casts(e[2]), strip_casts(e[3]), strip_casts(e[4]))
    if e[0] in ("exists", "forall"):
        return (e[0], e[1], strip_casts(e[2]))
    if e[0] == "ball":
        return ("ball", e[1], e[2], e[3], strip_casts(e[4]), strip_casts(e[5]))
    return (e[0], *[strip_casts(c) for c in e[1:]])


def domain(e, env: dict[str, str], default: str = "N") -> str:
    """The one number type of an arithmetic expression or atomic proposition: the type of its variables and
    ascribed numerals (Lean unifies both sides of an operation). Mixed types mean coercions: refused. Exponents
    are natural numbers of their own."""
    found: set[str] = set()

    def go(x, top: bool = False):
        h = x[0]
        if h == "var":
            if x[1] not in env:
                raise Unsupported(f"unknown name {x[1]!r}")
            found.add(env[x[1]])
        elif h == "cast":
            inner = set()
            _collect(x[2], env, inner)
            if inner - {x[1]}:
                raise Unsupported("coercion between number types")
            found.add(x[1])
            go(x[2])
        elif h == "pow":
            go(x[1])
            exp_types: set[str] = set()
            _collect(x[2], env, exp_types)
            if exp_types - {"N"}:
                raise Unsupported("exponent that is not a natural number")
        elif h == "call":
            if x[1] in REAL_ONLY:
                found.add("R")
            for a in x[2]:
                go(a)
        elif h == "modeq":
            found.add("Z" if x[1] == "ZMOD" else "N")
            for c in children(x):
                go(c)
        elif h == "prime":
            found.add("N")
            go(x[1])
        else:
            for c in children(x):
                go(c)
    go(e, True)
    if len(found) > 1:
        raise Unsupported("mixed number types")
    return found.pop() if found else default


def _collect(e, env, acc: set) -> None:
    for x in walk(e):
        if x[0] == "var" and x[1] in env:
            acc.add(env[x[1]])
        elif x[0] == "cast":
            acc.add(x[1])
        elif x[0] == "call" and x[1] in REAL_ONLY:
            acc.add("R")


# ---------------------------------------------------------------- back to Lean text
def lean_number(v, dom: str) -> str:
    """A value as a Lean term of the domain, parenthesised when needed."""
    t = LEAN_TYPE[dom]
    if isinstance(v, Fraction) and v.denominator != 1:
        return f"(({v.numerator} : {t}) / {v.denominator})"
    n = int(v)
    return f"({n} : {t})" if n >= 0 else f"(({n}) : {t})"


def lean(e, top: bool = True) -> str:
    """The term / proposition as Lean text (fully parenthesised; types are those of the original binders)."""
    h = e[0]
    if h == "num":
        return e[1]
    if h == "var":
        return e[1]
    if h == "cast":
        return f"({lean(e[2])} : {LEAN_TYPE[e[1]]})"
    if h == "neg":
        return f"(-{lean(e[1], False)})"
    if h in ("add", "sub", "mul", "div", "mod", "pow"):
        op = {"add": "+", "sub": "-", "mul": "*", "div": "/", "mod": "%", "pow": "^"}[h]
        s = f"{lean(e[1], False)} {op} {lean(e[2], False)}"
        return s if top else f"({s})"
    if h == "call":
        name = {"gcd": "Nat.gcd", "lcm": "Nat.lcm", "factorial": "Nat.factorial", "choose": "Nat.choose",
                "sqrt": "Real.sqrt", "exp": "Real.exp", "log": "Real.log", "pi": "Real.pi"}[e[1]]
        s = " ".join([name] + [lean(a, False) for a in e[2]])
        return s if top or not e[2] else f"({s})"
    if h == "rel":
        op = {"=": "=", "!=": "≠", "<": "<", "<=": "≤", ">": ">", ">=": "≥"}[e[1]]
        s = f"{lean(e[2])} {op} {lean(e[3])}"
        return s if top else f"({s})"
    if h == "dvd":
        s = f"{lean(e[1])} ∣ {lean(e[2])}"
        return s if top else f"({s})"
    if h == "modeq":
        s = f"{lean(e[3])} ≡ {lean(e[4])} [{e[1]} {lean(e[2])}]"
        return s if top else f"({s})"
    if h == "prime":
        s = f"Nat.Prime {lean(e[1], False)}"
        return s if top else f"({s})"
    if h == "not":
        return f"¬ {lean(e[1], False)}"
    if h in ("and", "or", "imp", "iff"):
        op = {"and": "∧", "or": "∨", "imp": "→", "iff": "↔"}[h]
        s = f"{lean(e[1], False)} {op} {lean(e[2], False)}"
        return s if top else f"({s})"
    if h in ("true", "false"):
        return h.capitalize()
    raise Unsupported(f"cannot print {h}")
