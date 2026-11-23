"""What the conjecture engine explores, recognised without a model (S-AW, DECISIONS D55; same idea as D39's
request analysis for Calcul, for sequences and families of objects).

`recognise(text)` turns a question in words or a formula into an `Intent`:
- `sequence`: one to three integer / rational sequences given by an expression tree in `n` (named arithmetic
  functions, « somme des n premiers … », « somme des carrés des diviseurs », a formula such as `n^2 + n + 41`);
- `data`: the terms themselves (« 1, 1, 2, 5, 14, 42, 132 »): nothing to compute;
- `family`: small objects with their invariants (graphs: Sage's generators and graph invariants);
- `unknown`: not recognised — a model writes the experiment and the user approves it before it runs.

From the same tree come, deterministically: the experiment's code (Sage, or Python with explicit definitions), the
value at any `n` computed in this process (demo mode and tests: exact rationals, no `eval`), the LaTeX of the
definition and the Lean term of each flavour (`∑ … in` for the prover's Lean 4.9 workspace, `∑ … ∈` for the current
Mathlib). Words that are not understood make the request `unknown` (two different questions never share a code).

Every experiment — written here or by a model — defines the same three names: `cj_columns`, `cj_index` and
`cj_rows_for(n)` (the rows of the table at index n). The engine's fixed driver (`driver`) reads the table through
them, outside the notebook's history."""
from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass, field
from fractions import Fraction as Fr

from . import intent as I

MARK = "MADALEAN_CJ "
DEFAULT_TERMS = 60
MAX_TERMS = 2000
MAX_ROWS = 4000
MAX_EVAL_BITS = 200_000


class CatalogError(ValueError):
    pass


# ================================================================ pure implementations (this process)
def _divisors(n: int) -> list[int]:
    out = []
    for d in range(1, math.isqrt(n) + 1):
        if n % d == 0:
            out.append(d)
            if d * d != n:
                out.append(n // d)
    return out


def _sigma(n: int, k: int = 1) -> int:
    return sum(d ** k for d in _divisors(n))


def _phi(n: int) -> int:
    out, m, p = n, n, 2
    while p * p <= m:
        if m % p == 0:
            while m % p == 0:
                m //= p
            out -= out // p
        p += 1
    return out - out // m if m > 1 else out


def _fib(n: int) -> int:
    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
    return a


def _lucas(n: int) -> int:
    a, b = 2, 1
    for _ in range(n):
        a, b = b, a + b
    return a


def _is_prime(n: int) -> bool:
    return n > 1 and all(n % p for p in range(2, math.isqrt(n) + 1))


_PRIMES: list[int] = [2]


def _prime(n: int) -> int:
    c = _PRIMES[-1] + 1
    while len(_PRIMES) < n:
        if all(c % p for p in _PRIMES if p * p <= c):
            _PRIMES.append(c)
        c += 1
    return _PRIMES[n - 1]


def _primepi(n: int) -> int:
    return sum(1 for k in range(2, n + 1) if _is_prime(k))


def _omega(n: int, mult: bool = False) -> int:
    c, p = 0, 2
    while p * p <= n:
        if n % p == 0:
            c += 1
            n //= p
            while n % p == 0:
                n //= p
                c += 1 if mult else 0
        p += 1
    return c + (1 if n > 1 else 0)


def _moebius(n: int) -> int:
    if n == 1:
        return 1
    p, k = 2, 0
    while p * p <= n:
        if n % p == 0:
            n //= p
            if n % p == 0:
                return 0
            k += 1
        p += 1
    return (-1) ** (k + (1 if n > 1 else 0))


def _partitions(n: int) -> int:
    p = [1] + [0] * n
    for k in range(1, n + 1):
        for j in range(k, n + 1):
            p[j] += p[j - k]
    return p[n]


def _bell(n: int) -> int:
    row = [1]
    for _ in range(n):
        new = [row[-1]]
        for x in row:
            new.append(new[-1] + x)
        row = new
    return row[0]


def _harmonic(n: int) -> Fr:
    return sum((Fr(1, k) for k in range(1, n + 1)), Fr(0))


# Python source of the helpers (emitted into a Python-kernel experiment only when used; explicit, no import magic)
PY_DEFS = {
    "_divisors": "def _divisors(n):\n    return [d for d in range(1, n + 1) if n % d == 0]\n",
    "sigma": "def sigma(n, k=1):\n    return sum(d ** k for d in range(1, n + 1) if n % d == 0)\n",
    "tau": "def tau(n):\n    return sum(1 for d in range(1, n + 1) if n % d == 0)\n",
    "euler_phi": "def euler_phi(n):\n    return sum(1 for k in range(1, n + 1) if math.gcd(k, n) == 1)\n",
    "fibonacci": "def fibonacci(n):\n    a, b = 0, 1\n    for _ in range(n):\n        a, b = b, a + b\n    return a\n",
    "lucas": "def lucas(n):\n    a, b = 2, 1\n    for _ in range(n):\n        a, b = b, a + b\n    return a\n",
    "is_prime": "def is_prime(n):\n    return n > 1 and all(n % p for p in range(2, math.isqrt(n) + 1))\n",
    "nth_prime": ("def nth_prime(n):\n    c, k = 1, 0\n    while k < n:\n        c += 1\n        if all(c % p for p in "
                  "range(2, math.isqrt(c) + 1)):\n            k += 1\n    return c\n"),
    "prime_pi": ("def prime_pi(n):\n    return sum(1 for k in range(2, n + 1) if all(k % p for p in "
                 "range(2, math.isqrt(k) + 1)))\n"),
    "catalan": "def catalan(n):\n    return math.comb(2 * n, n) // (n + 1)\n",
    "partitions": ("def partitions(n):\n    p = [1] + [0] * n\n    for k in range(1, n + 1):\n        for j in "
                   "range(k, n + 1):\n            p[j] += p[j - k]\n    return p[n]\n"),
    "bell": ("def bell(n):\n    row = [1]\n    for _ in range(n):\n        new = [row[-1]]\n        for x in row:\n"
             "            new.append(new[-1] + x)\n        row = new\n    return row[0]\n"),
    "harmonic": "def harmonic(n):\n    return sum((Fraction(1, k) for k in range(1, n + 1)), Fraction(0))\n",
    "omega": ("def omega(n):\n    return sum(1 for p in range(2, n + 1) if n % p == 0 and all(p % q for q in "
              "range(2, math.isqrt(p) + 1)))\n"),
    "moebius": ("def moebius(n):\n    k, p = 0, 2\n    while p * p <= n:\n        if n % p == 0:\n            n //= p\n"
                "            if n % p == 0:\n                return 0\n            k += 1\n        p += 1\n"
                "    return (-1) ** (k + (1 if n > 1 else 0))\n"),
}

# name → arity, this-process implementation, Sage / Python call, Lean term per flavour ({0}, {1}: arguments as ℕ
# terms; None: no Lean term, the formalizer writes the statement), result type, LaTeX, first valid index
FN: dict[str, dict] = {
    "sigma": {"arity": (1, 2), "py": lambda n, k=1: _sigma(n, k), "sage": "sigma({0}, {1})", "python": "sigma({0}, {1})",
              "defs": ["sigma"], "lean": {"v4.9": "(∑ d in Nat.divisors {0}, d ^ {1})",
                                         "default": "(∑ d ∈ Nat.divisors {0}, d ^ {1})"},
              "latex": "\\sigma_{{{1}}}({0})", "n0": 1},
    "tau": {"arity": (1, 1), "py": lambda n: len(_divisors(n)), "sage": "number_of_divisors({0})", "python": "tau({0})",
            "defs": ["tau"], "lean": {"default": "(Nat.divisors {0}).card"}, "latex": "\\tau({0})", "n0": 1},
    "phi": {"arity": (1, 1), "py": _phi, "sage": "euler_phi({0})", "python": "euler_phi({0})", "defs": ["euler_phi"],
            "lean": {"default": "Nat.totient {0}"}, "latex": "\\varphi({0})", "n0": 1},
    "factorial": {"arity": (1, 1), "py": math.factorial, "sage": "factorial({0})", "python": "math.factorial({0})",
                  "defs": [], "lean": {"default": "Nat.factorial {0}"}, "latex": "{0}!", "n0": 0},
    "fib": {"arity": (1, 1), "py": _fib, "sage": "fibonacci({0})", "python": "fibonacci({0})", "defs": ["fibonacci"],
            "lean": {"default": "Nat.fib {0}"}, "latex": "F_{{{0}}}", "n0": 0},
    "lucas": {"arity": (1, 1), "py": _lucas, "sage": "lucas_number2({0}, 1, -1)", "python": "lucas({0})",
              "defs": ["lucas"], "lean": None, "latex": "L_{{{0}}}", "n0": 0},
    "prime": {"arity": (1, 1), "py": _prime, "sage": "nth_prime({0})", "python": "nth_prime({0})", "defs": ["nth_prime"],
              "lean": {"default": "Nat.nth Nat.Prime ({0} - 1)"}, "latex": "p_{{{0}}}", "n0": 1},
    "primepi": {"arity": (1, 1), "py": _primepi, "sage": "prime_pi({0})", "python": "prime_pi({0})",
                "defs": ["prime_pi"], "lean": {"default": "Nat.primeCounting {0}"}, "latex": "\\pi({0})", "n0": 1},
    "catalan": {"arity": (1, 1), "py": lambda n: math.comb(2 * n, n) // (n + 1), "sage": "catalan_number({0})",
                "python": "catalan({0})", "defs": ["catalan"], "lean": {"default": "catalan {0}"},
                "latex": "C_{{{0}}}", "n0": 0},
    "binomial": {"arity": (2, 2), "py": lambda a, b: math.comb(a, b) if 0 <= b <= a else 0,
                 "sage": "binomial({0}, {1})", "python": "math.comb({0}, {1})", "defs": [],
                 "lean": {"default": "Nat.choose {0} {1}"}, "latex": "\\binom{{{0}}}{{{1}}}", "n0": 0},
    "partitions": {"arity": (1, 1), "py": _partitions, "sage": "number_of_partitions({0})",
                   "python": "partitions({0})", "defs": ["partitions"], "lean": None, "latex": "p({0})", "n0": 0},
    "bell": {"arity": (1, 1), "py": _bell, "sage": "bell_number({0})", "python": "bell({0})", "defs": ["bell"],
             "lean": None, "latex": "B_{{{0}}}", "n0": 0},
    "harmonic": {"arity": (1, 1), "py": _harmonic, "sage": "harmonic_number({0})", "python": "harmonic({0})",
                 "defs": ["harmonic"], "lean": {"default": "harmonic {0}"}, "ltype": "rat",
                 "latex": "H_{{{0}}}", "n0": 1},
    "omega": {"arity": (1, 1), "py": _omega, "sage": "len(prime_divisors({0}))", "python": "omega({0})",
              "defs": ["omega"], "lean": None, "latex": "\\omega({0})", "n0": 1},
    "moebius": {"arity": (1, 1), "py": _moebius, "sage": "moebius({0})", "python": "moebius({0})", "defs": ["moebius"],
                "lean": None, "latex": "\\mu({0})", "n0": 1},
    "gcd": {"arity": (2, 2), "py": math.gcd, "sage": "gcd({0}, {1})", "python": "math.gcd({0}, {1})", "defs": [],
            "lean": {"default": "Nat.gcd {0} {1}"}, "latex": "\\gcd({0}, {1})", "n0": 0},
}
ALIASES = {"sigma": "sigma", "tau": "tau", "d": "tau", "phi": "phi", "euler_phi": "phi", "totient": "phi",
           "varphi": "phi", "factorial": "factorial", "fact": "factorial", "fib": "fib", "fibonacci": "fib",
           "F": "fib", "lucas": "lucas", "prime": "prime", "nth_prime": "prime", "p": "prime", "primepi": "primepi",
           "prime_pi": "primepi", "pi": "primepi", "catalan": "catalan", "binomial": "binomial", "binom": "binomial",
           "C": "binomial", "choose": "binomial", "partitions": "partitions", "bell": "bell", "harmonic": "harmonic",
           "H": "harmonic", "omega": "omega", "moebius": "moebius", "mobius": "moebius", "mu": "moebius",
           "gcd": "gcd", "pgcd": "gcd"}

# families « the first n … »: k-th element for k = 0, 1, … (0-based, so that the Lean sum is over Finset.range n)
K = ("var", "k")
K1 = ("add", K, ("num", 1))
FAMILIES: dict[str, dict] = {
    "odd": {"ast": ("add", ("mul", ("num", 2), K), ("num", 1)), "latex": "(2k-1)", "fr": "nombres impairs",
            "en": "odd numbers", "re": r"(nombres? |entiers? )?impairs?|odd( numbers?| integers?)?"},
    "even": {"ast": ("add", ("mul", ("num", 2), K), ("num", 2)), "latex": "2k", "fr": "nombres pairs",
             "en": "even numbers", "re": r"(nombres? |entiers? )?pairs?|even( numbers?| integers?)?"},
    "squares": {"ast": ("pow", K1, ("num", 2)), "latex": "k^2", "fr": "carrés", "en": "squares",
                "re": r"carres( parfaits)?|(perfect )?squares"},
    "cubes": {"ast": ("pow", K1, ("num", 3)), "latex": "k^3", "fr": "cubes", "en": "cubes", "re": r"cubes"},
    "primes": {"ast": ("call", "prime", [K1]), "latex": "p_k", "fr": "nombres premiers", "en": "primes",
               "re": r"nombres? premiers?|primes?( numbers?)?"},
    "fibonacci": {"ast": ("call", "fib", [K1]), "latex": "F_k", "fr": "nombres de Fibonacci", "en": "Fibonacci numbers",
                  "re": r"(nombres? de |termes? de (la suite de )?)?fibonacci( numbers?)?"},
    "triangular": {"ast": ("call", "binomial", [("add", K, ("num", 2)), ("num", 2)]), "latex": "\\tfrac{k(k+1)}{2}",
                   "fr": "nombres triangulaires", "en": "triangular numbers",
                   "re": r"(nombres? )?triangulaires?|triangular( numbers?)?"},
    "factorials": {"ast": ("call", "factorial", [K1]), "latex": "k!", "fr": "factorielles", "en": "factorials",
                   "re": r"factorielles?|factorials?"},
    "powers2": {"ast": ("pow", ("num", 2), K), "latex": "2^{k-1}", "fr": "puissances de 2", "en": "powers of 2",
                "re": r"puissances? de (2|deux)|powers? of (2|two)"},
    "integers": {"ast": K1, "latex": "k", "fr": "entiers", "en": "positive integers",
                 "re": r"(nombres? )?entiers?( naturels?)?( non nuls?)?|(positive |natural )?(integers?|numbers?)"},
}
_ORD = {"carres": 2, "squares": 2, "cubes": 3}
N = ("var", "n")
# named sequences in words (folded text): (regex, tree in n, first index, French, English)
NAMED: list[tuple[str, tuple, int, str, str]] = [
    (r"sommes? des (carres|cubes|puissances? (\d+)\s?-?(i?emes?|es?)?) des diviseurs|"
     r"sum of (the )?(squares|cubes|(\d+)\s?-?(st|nd|rd|th) powers?) of (the |its )?divisors", ("sigma_k",), 1,
     "somme des puissances {k}-ièmes des diviseurs de n", "sum of the {k}-th powers of the divisors of n"),
    (r"sommes? des diviseurs|sum of (the |its )?divisors|sigma\s?\(n\)", ("call", "sigma", [N, ("num", 1)]), 1,
     "somme des diviseurs de n", "sum of the divisors of n"),
    (r"nombres? de diviseurs|number of divisors|tau\s?\(n\)", ("call", "tau", [N]), 1,
     "nombre de diviseurs de n", "number of divisors of n"),
    (r"indicatrice d'?\s?euler|(euler'?s? )?totient( function)?|euler'?s? phi|phi\s?\(n\)", ("call", "phi", [N]), 1,
     "indicatrice d'Euler de n", "Euler's totient of n"),
    (r"nombres? de partitions?( d'un entier| de n)?|number of partitions?( of n| of an integer)?|partition numbers?",
     ("call", "partitions", [N]), 0, "nombre de partitions de n", "number of partitions of n"),
    (r"nombres? de catalan|catalan numbers?", ("call", "catalan", [N]), 0, "nombres de Catalan", "Catalan numbers"),
    (r"nombres? de bell|bell numbers?", ("call", "bell", [N]), 0, "nombres de Bell", "Bell numbers"),
    (r"nombres? de lucas|lucas numbers?", ("call", "lucas", [N]), 0, "nombres de Lucas", "Lucas numbers"),
    (r"(nombres? de |suite de )?fibonacci( numbers?| sequence)?", ("call", "fib", [N]), 0, "nombres de Fibonacci",
     "Fibonacci numbers"),
    (r"nombres? harmoniques?|harmonic numbers?", ("call", "harmonic", [N]), 1, "nombres harmoniques",
     "harmonic numbers"),
    (r"coefficients? binomia(l|ux) centra(l|ux)|central binomial coefficients?",
     ("call", "binomial", [("mul", ("num", 2), N), N]), 0, "coefficients binomiaux centraux",
     "central binomial coefficients"),
    (r"nombres? de (nombres? )?premiers? (inferieurs?|plus petits?) ou egaux a n|number of primes (up to|at most|"
     r"not exceeding|less than or equal to) n|prime counting function", ("call", "primepi", [N]), 1,
     "nombre de premiers inférieurs ou égaux à n", "number of primes up to n"),
    (r"(n-?i?emes? )?nombres? premiers?|(n-?th )?primes?( numbers?)?", ("call", "prime", [N]), 1,
     "n-ième nombre premier", "n-th prime"),
    (r"fonction de mo?e?bius|mo?e?bius function", ("call", "moebius", [N]), 1, "fonction de Möbius", "Möbius function"),
    (r"factorielles?|factorials?", ("call", "factorial", [N]), 0, "factorielle de n", "factorial of n"),
    (r"nombres? triangulaires?|triangular numbers?", ("call", "binomial", [("add", N, ("num", 1)), ("num", 2)]), 0,
     "nombres triangulaires", "triangular numbers"),
    (r"carres( parfaits)?|(perfect )?squares", ("pow", N, ("num", 2)), 0, "carrés", "squares"),
    (r"puissances? de (2|deux)|powers? of (2|two)", ("pow", ("num", 2), N), 0, "puissances de 2", "powers of 2"),
]
STOP = set("""le la les l un une des de du d a au aux en et ou pour tout tous toute toutes chaque entier entiers
naturel naturels n suite suites sequence sequences nombre nombres number numbers etudier etudie explorer explore
regarder que dire sur quelle quelles est sont formule formula the of for all every each integer integers natural
study look at what about is are a an on in terme termes term terms valeurs values valeur value calculer compute
trouver find conjecture conjectures pattern patterns motif motifs regularite regularites donne donnee donnees with
avec jusqu jusqua up to premiers premier first when quand positif positifs positive non nul nuls nonzero general
generale closed forme fermee s il y t elle elles ils on me moi je j veux voudrais want would like i please svp
stp merci fonction function""".split())

GRAPH_COLUMNS = [("n", "nombre de sommets", "number of vertices", "n"), ("m", "nombre d'arêtes", "number of edges", "m"),
                 ("Δ", "degré maximal", "maximum degree", "\\Delta"), ("δ", "degré minimal", "minimum degree", "\\delta"),
                 ("χ", "nombre chromatique", "chromatic number", "\\chi"),
                 ("ω", "taille de la plus grande clique", "clique number", "\\omega"),
                 ("α", "taille du plus grand stable", "independence number", "\\alpha"),
                 ("diam", "diamètre", "diameter", "\\operatorname{diam}")]
GRAPH_FAMILIES = {
    "connected": {"re": r"graphes? connexes?|connected graphs?", "fr": "graphes connexes", "en": "connected graphs",
                  "gen": 'graphs.nauty_geng("%d -c" % n)', "exhaust": 7,
                  "rand": "graphs.RandomGNP(n, 0.2 + 0.6 * random(), seed=1000 * n + j)", "keep": "G.is_connected()"},
    "trees": {"re": r"arbres?|trees?", "fr": "arbres", "en": "trees", "gen": "graphs.trees(n)", "exhaust": 11,
              "rand": "graphs.RandomTree(n, seed=1000 * n + j)", "keep": "True"},
    "bipartite": {"re": r"graphes? bipartis?( connexes?)?|(connected )?bipartite graphs?",
                  "fr": "graphes bipartis connexes", "en": "connected bipartite graphs",
                  "gen": 'graphs.nauty_geng("%d -c -b" % n)', "exhaust": 8,
                  "rand": "graphs.RandomBipartite(n // 2, n - n // 2, 0.5, seed=1000 * n + j)",
                  "keep": "G.is_connected()"},
}


# ================================================================ expression trees
_TOKEN = re.compile(r"\s*(\d+|[A-Za-z_][A-Za-z_0-9]*|\*\*|[-+*/^(),!])")


def parse_expr(text: str) -> tuple:
    """A formula in `n` → tree. Strict: only integers, `n`, + − * / ^ !, parentheses and the catalogue's functions."""
    s = I.normalize_text(text).replace("{", "(").replace("}", ")")
    s = re.sub(r"\b(H|F|C|p|L|B)_\(?n\)?(?!\s*\()", r"\1(n)", s)                 # H_n, F_n: the n-th term
    s = re.sub(r"\bsigma_\(?(\d+)\)?\s*\(", lambda m: f"sigma__{m.group(1)}(", s)
    toks, pos = [], 0
    while pos < len(s):
        if s[pos].isspace():
            pos += 1
            continue
        m = _TOKEN.match(s, pos)
        if not m:
            raise CatalogError(f"unexpected {s[pos]!r}")
        toks.append("^" if m.group(1) == "**" else m.group(1))
        pos = m.end()
    if not toks or len(toks) > 200:
        raise CatalogError("empty")
    i = 0

    def peek():
        return toks[i] if i < len(toks) else ""

    def take(t=None):
        nonlocal i
        if i >= len(toks) or (t is not None and toks[i] != t):
            raise CatalogError(f"expected {t or 'a term'}")
        i += 1
        return toks[i - 1]

    def expr():
        left = term()
        while peek() in ("+", "-"):
            op = take()
            left = ("add" if op == "+" else "sub", left, term())
        return left

    def term():
        left = unary()
        while True:
            t = peek()
            if t in ("*", "/"):
                take()
                left = ("mul" if t == "*" else "div", left, unary())
            elif t and (t[0].isalnum() or t[0] == "_" or t == "("):
                left = ("mul", left, power())                  # implicit product: 2n, n(n+1)
            else:
                return left

    def unary():
        if peek() == "-":
            take()
            return ("neg", unary())
        return power()

    def power():
        base = postfix()
        if peek() == "^":
            take()
            return ("pow", base, unary())
        return base

    def postfix():
        a = atom()
        while peek() == "!":
            take()
            a = ("call", "factorial", [a])
        return a

    def atom():
        t = take()
        if t.isdigit():
            return ("num", int(t))
        if t == "(":
            e = expr()
            take(")")
            return e
        if t == "n":
            return N
        name, _, sub = t.partition("__")
        fn = ALIASES.get(name)
        if fn is None or peek() != "(":
            raise CatalogError(f"unknown name {t!r}")
        take("(")
        args = [expr()]
        while peek() == ",":
            take()
            args.append(expr())
        take(")")
        if sub:
            args.append(("num", int(sub)))
        if fn == "sigma" and len(args) == 1:
            args.append(("num", 1))
        lo, hi = FN[fn]["arity"]
        if not lo <= len(args) <= hi:
            raise CatalogError(f"{name}: wrong number of arguments")
        return ("call", fn, args)
    tree = expr()
    if i != len(toks):
        raise CatalogError(f"unexpected {toks[i]!r}")
    return tree


def walk(t: tuple):
    yield t
    for x in t[1:]:
        if isinstance(x, tuple):
            yield from walk(x)
        elif isinstance(x, list):
            for y in x:
                yield from walk(y)


def uses_n(t: tuple) -> bool:
    return any(x == N for x in walk(t))


def evaluate(t: tuple, env: dict[str, int]) -> Fr:
    """Exact value of a tree in this process (bounded; integer arguments for the named functions)."""
    op = t[0]
    if op == "num":
        return Fr(t[1])
    if op == "var":
        return Fr(env[t[1]])
    if op == "neg":
        return -evaluate(t[1], env)
    if op in ("add", "sub", "mul", "div"):
        a, b = evaluate(t[1], env), evaluate(t[2], env)
        if op == "div":
            if b == 0:
                raise CatalogError("division by zero")
            return a / b
        return a + b if op == "add" else a - b if op == "sub" else a * b
    if op == "pow":
        a, b = evaluate(t[1], env), evaluate(t[2], env)
        if b.denominator != 1 or abs(b) > 100_000:
            raise CatalogError("exponent")
        if abs(b) * max(abs(a.numerator), a.denominator).bit_length() > MAX_EVAL_BITS:
            raise CatalogError("too large")
        if b < 0 and a == 0:
            raise CatalogError("division by zero")
        return a ** int(b)
    if op == "call":
        args = [evaluate(x, env) for x in t[2]]
        if any(x.denominator != 1 or x < 0 or x > 10 ** 7 for x in args):
            raise CatalogError("argument")
        ints = [int(x) for x in args]
        if ints and ints[0] < FN[t[1]]["n0"]:
            raise CatalogError("argument")
        return Fr(FN[t[1]]["py"](*ints))
    if op in ("sum", "prod"):
        count = evaluate(t[2], env)
        if count.denominator != 1 or not 0 <= count <= 100_000:
            raise CatalogError("range")
        acc = Fr(0) if op == "sum" else Fr(1)
        for k in range(int(count)):
            v = evaluate(t[3], {**env, t[1]: k})
            acc = acc + v if op == "sum" else acc * v
        return acc
    raise CatalogError(op)


_PREC = {"add": 1, "sub": 1, "neg": 2, "mul": 3, "div": 3, "pow": 4}


def _paren(s: str, inner: tuple, outer: int, right: bool = False) -> str:
    p = _PREC.get(inner[0], 9)
    return f"({s})" if p < outer or (right and p == outer) else s


def to_code(t: tuple, language: str, env: dict[str, str] | None = None) -> str:
    """Sage (exact by itself) or Python (Fractions for divisions, explicit helper functions)."""
    env = env or {}
    op = t[0]
    if op == "num":
        return str(t[1])
    if op == "var":
        return env.get(t[1], t[1])
    if op == "neg":
        return "-" + _paren(to_code(t[1], language, env), t[1], 3)
    if op in ("add", "sub", "mul"):
        sym = {"add": " + ", "sub": " - ", "mul": "*"}[op]
        return _paren(to_code(t[1], language, env), t[1], _PREC[op]) + sym + \
            _paren(to_code(t[2], language, env), t[2], _PREC[op], right=op != "add")
    if op == "div":
        a, b = to_code(t[1], language, env), to_code(t[2], language, env)
        if language == "python":
            return f"Fraction({a}) / Fraction({b})"
        return _paren(a, t[1], 3) + "/" + _paren(b, t[2], 3, right=True)
    if op == "pow":
        sym = "^" if language == "sage" else "**"
        return _paren(to_code(t[1], language, env), t[1], 5) + sym + _paren(to_code(t[2], language, env), t[2], 5)
    if op == "call":
        args = [to_code(x, language, env) for x in t[2]]
        return FN[t[1]]["sage" if language == "sage" else "python"].format(*args)
    if op in ("sum", "prod"):
        body = to_code(t[3], language, env)
        rng = f"range({to_code(t[2], language, env)})"
        return f"sum({body} for {t[1]} in {rng})" if op == "sum" else f"prod({body} for {t[1]} in {rng})"
    raise CatalogError(op)


def python_defs(trees: list[tuple]) -> str:
    names: list[str] = []
    for t in trees:
        for x in walk(t):
            if x[0] == "call":
                for d in FN[x[1]]["defs"]:
                    if d not in names:
                        names.append(d)
    return "".join(PY_DEFS[d] + "\n" for d in names)


def to_latex(t: tuple, env: dict[str, str] | None = None) -> str:
    env = env or {}
    op = t[0]
    if op == "num":
        return str(t[1])
    if op == "var":
        return env.get(t[1], t[1])
    if op == "neg":
        return "-" + _paren(to_latex(t[1], env), t[1], 3)
    if op in ("add", "sub"):
        return to_latex(t[1], env) + (" + " if op == "add" else " - ") + _paren(to_latex(t[2], env), t[2], 1,
                                                                                right=op == "sub")
    if op == "mul":
        a, b = _paren(to_latex(t[1], env), t[1], 3), _paren(to_latex(t[2], env), t[2], 3)
        return f"{a} \\cdot {b}" if b[:1].isdigit() else f"{a}\\,{b}"
    if op == "div":
        return f"\\frac{{{to_latex(t[1], env)}}}{{{to_latex(t[2], env)}}}"
    if op == "pow":
        a = to_latex(t[1], env)
        return ("{" + a + "}" if t[1][0] in ("num", "var") else f"\\left({a}\\right)") + "^{" + to_latex(t[2], env) + "}"
    if op == "call":
        args = [to_latex(x, env) for x in t[2]]
        if t[1] == "factorial" and t[2][0][0] not in ("num", "var"):
            return f"\\left({args[0]}\\right)!"
        if t[1] == "sigma" and t[2][1] == ("num", 1):
            return f"\\sigma({args[0]})"
        return FN[t[1]]["latex"].format(*args)
    if op in ("sum", "prod"):
        sym = "\\sum" if op == "sum" else "\\prod"
        top = to_latex(("sub", t[2], ("num", 1)), env)
        return f"{sym}_{{{t[1]}=0}}^{{{top}}} " + _paren(to_latex(t[3], env), t[3], 3)
    raise CatalogError(op)


def lean_ring(t: tuple) -> str | None:
    """The ring of the Lean term: 'nat' (no subtraction, no division), 'int', 'rat'; None when a part has no Lean
    term (the formalizer writes the statement then)."""
    ring = "nat"

    def up(r: str) -> None:
        nonlocal ring
        ring = max(ring, r, key=("nat", "int", "rat").index)

    def nat_only(x: tuple) -> bool:
        return all(y[0] in ("num", "var", "add", "mul", "pow", "call") and
                   (y[0] != "call" or (FN[y[1]]["lean"] and FN[y[1]].get("ltype", "nat") == "nat")) for y in walk(x))

    def visit(x: tuple) -> bool:
        op = x[0]
        if op in ("sub", "neg"):
            up("int")
        elif op == "div":
            up("rat")
        elif op == "pow":
            return visit(x[1]) and nat_only(x[2])
        elif op == "call":
            f = FN[x[1]]
            if not f["lean"] or not all(nat_only(a) for a in x[2]):
                return False
            up(f.get("ltype", "nat"))
            return True
        elif op in ("sum", "prod"):
            return nat_only(x[2]) and visit(x[3])
        return all(visit(y) for y in x[1:] if isinstance(y, tuple))
    return ring if visit(t) else None


_RING = {"nat": "ℕ", "int": "ℤ", "rat": "ℚ"}


def to_lean(t: tuple, flavor: str, ring: str, env: dict[str, str] | None = None) -> str:
    """Lean 4 term of the tree in `ring` (leaves are cast, so the whole term elaborates in that ring). `env` maps
    a variable to the ℕ term that replaces it (`n` ↦ `(n + 1)`)."""
    env = env or {}

    def wrap(s: str) -> str:
        if re.fullmatch(r"[\w.]+", s):
            return s
        depth = 0
        for i, ch in enumerate(s):
            depth += ch == "("
            depth -= ch == ")"
            if depth == 0 and i < len(s) - 1:
                return f"({s})"
        return s if s.startswith("(") else f"({s})"

    def go(x: tuple, r: str) -> str:
        op = x[0]
        if op == "num":
            return str(x[1]) if r == "nat" else f"({x[1]} : {_RING[r]})"
        if op == "var":
            v = wrap(env.get(x[1], x[1]))
            return v if r == "nat" else f"({v} : {_RING[r]})"
        if op == "neg":
            return "-" + _paren(go(x[1], r), x[1], 3)
        if op in ("add", "sub", "mul", "div"):
            sym = {"add": " + ", "sub": " - ", "mul": " * ", "div": " / "}[op]
            return _paren(go(x[1], r), x[1], _PREC[op]) + sym + _paren(go(x[2], r), x[2], _PREC[op], right=op != "add")
        if op == "pow":
            return _paren(go(x[1], r), x[1], 5) + " ^ " + _paren(go(x[2], "nat"), x[2], 5)
        if op == "call":
            f = FN[x[1]]
            src = f["lean"].get(flavor) or f["lean"]["default"]
            args = [wrap(go(a, "nat")) for a in x[2]]
            s = src.format(*args)
            if x[1] == "sigma" and x[2][1] == ("num", 1):
                s = s.replace(", d ^ 1)", ", d)")
            own = f.get("ltype", "nat")
            return wrap(s) if own == r else f"(({s} : {_RING[own]}) : {_RING[r]})"
        if op in ("sum", "prod"):
            sym, mem = ("∑" if op == "sum" else "∏"), ("in" if flavor == "v4.9" else "∈")
            count = wrap(go(x[2], "nat"))
            return f"({sym} {x[1]} {mem} Finset.range {count}, {_paren(go(x[3], r), x[3], 2)})"
        raise CatalogError(op)
    return go(t, ring)


# ================================================================ intents
@dataclass
class SeqDef:
    name: str                       # column name: a, b, c
    tree: tuple
    n0: int
    fr: str
    en: str
    latex: str = ""                 # definition at n (nicer than the tree's when a family provides one)

    @property
    def key(self) -> str:
        return json.dumps(self.tree, separators=(",", ":"), default=list)


@dataclass
class Intent:
    kind: str                       # sequence | data | family | unknown
    text: str = ""
    seqs: list[SeqDef] = field(default_factory=list)
    family: str = ""
    table: dict | None = None       # kind == data
    first: int = 0                  # index range of the first experiment
    last: int = 0

    @property
    def recognised(self) -> bool:
        return self.kind != "unknown"

    @property
    def key(self) -> str:
        """Same mathematics, same key (the words around do not count)."""
        if self.kind == "sequence":
            body = [s.key for s in self.seqs]
        elif self.kind == "family":
            body = [self.family]
        elif self.kind == "data":
            body = [json.dumps((self.table or {}).get("rows"))]
        else:
            body = [" ".join(I.fold(I.normalize_text(self.text)).split())]
        return hashlib.sha256(json.dumps([self.kind, body]).encode()).hexdigest()[:20]

    def summary(self, lang: str = "fr") -> str:
        if self.kind == "sequence":
            return " ; ".join(f"{s.name}(n) = " + (to_code(s.tree, "sage") if s.fr.startswith("$") else
                                                   (s.fr if lang == "fr" else s.en)) for s in self.seqs)
        if self.kind == "family":
            f = GRAPH_FAMILIES[self.family]
            return (f"{f['fr']} et leurs invariants" if lang == "fr" else f"{f['en']} and their invariants")
        if self.kind == "data":
            k = len((self.table or {}).get("rows") or [])
            return f"{k} termes donnés" if lang == "fr" else f"{k} given terms"
        return ""

    def to_dict(self, lang: str = "fr") -> dict:
        return {"kind": self.kind, "key": self.key, "recognised": self.recognised, "summary": self.summary(lang),
                "family": self.family, "first": self.first, "last": self.last,
                "sequences": [{"name": s.name, "n0": s.n0, "fr": s.fr, "en": s.en, "latex": s.latex or
                               to_latex(s.tree), "lean": lean_ring(s.tree) is not None} for s in self.seqs]}


def _residue_ok(folded: str) -> bool:
    words = re.findall(r"[a-z]+", folded)
    return all(w in STOP or len(w) == 1 for w in words) and not re.search(r"\d", folded)


def _range(folded: str) -> tuple[str, int | None]:
    m = re.search(r"(?:jusqu'?\s?a|up to|pour n (?:<=?|≤|inferieur a)|for n (?:<=?|up to))\s*(?:n\s*=\s*)?(\d{1,5})\b",
                  folded)
    if not m:
        return folded, None
    return folded[:m.start()] + " " + folded[m.end():], int(m.group(1))


def _named(folded: str) -> tuple[tuple, int, str, str, str] | None:
    """(tree, first index, fr, en, latex) of a request in words, or None."""
    # « somme / produit des n premiers … »
    m = re.search(r"\b(sommes?|sum|produits?|product)\b(.*)", folded)
    if m:
        op = "sum" if m.group(1).startswith(("som", "sum")) else "prod"
        rest = m.group(2)
        first = re.search(r"\b(n premiers?|n premieres?|premiers? n|first n|n first)\b", rest)
        if first:
            tail = rest[:first.start()] + " " + rest[first.end():]
            for fid, fam in FAMILIES.items():
                fm = re.search(r"\b(" + fam["re"] + r")\b", tail)
                if fm and fm.group(0).strip() and _residue_ok(folded[:m.start()] + tail[:fm.start()] + tail[fm.end():]):
                    sym = "\\sum" if op == "sum" else "\\prod"
                    word = ("somme" if op == "sum" else "produit", "sum" if op == "sum" else "product")
                    return ((op, "k", N, fam["ast"]), 0, f"{word[0]} des n premiers {fam['fr']}",
                            f"{word[1]} of the first n {fam['en']}", f"{sym}_{{k=1}}^{{n}} {fam['latex']}")
    for pat, tree, n0, fr, en in NAMED:
        nm = re.search(r"(?<![a-z])(" + pat + r")(?![a-z])", folded)
        if not nm or not _residue_ok(folded[:nm.start()] + " " + folded[nm.end():]):
            continue
        if tree == ("sigma_k",):
            g = nm.group(0)
            dm = re.search(r"\d+", g)
            k = int(dm.group(0)) if dm else (3 if "cube" in g else 2)
            if not 1 <= k <= 12:
                return None
            tree = ("call", "sigma", [N, ("num", k)])
            name = {2: ("carrés", "squares"), 3: ("cubes", "cubes")}.get(k)
            fr = f"somme des {name[0]} des diviseurs de n" if name else fr.format(k=k)
            en = f"sum of the {name[1]} of the divisors of n" if name else en.format(k=k)
        return tree, n0, fr, en, ""
    return None


def _one(part: str) -> tuple[tuple, int, str, str, str] | None:
    folded = I.fold(I.normalize_text(part)).replace("’", "'")
    folded = re.sub(r"[?!.:;«»\"]+", " ", folded)
    named = _named(folded)
    if named:
        return named
    # a formula: « n^2 + n + 41 », « a(n) = 2^n - 1 », « la suite n(n+1)/2 »
    body = re.sub(r"^\s*(?:[a-z]\s*\(\s*n\s*\)|[a-z]_\{?n\}?)\s*=", " ", I.normalize_text(part))
    cut = _FORMULA_START.search(body)
    if cut is None:
        return None
    lead, expr = body[:cut.start()], body[cut.start():].strip().rstrip(".? ")
    if not _residue_ok(I.fold(lead)):
        return None
    try:
        tree = parse_expr(expr)
    except CatalogError:
        return None
    if not uses_n(tree):
        return None
    n0 = max([FN[x[1]]["n0"] for x in walk(tree) if x[0] == "call"] + [0])
    if any(x[0] == "div" for x in walk(tree)):
        try:
            evaluate(tree, {"n": n0})
        except CatalogError:
            n0 += 1
    tex = to_latex(tree)
    return tree, n0, f"${tex}$", f"${tex}$", tex


_FORMULA_START = re.compile(r"(?<![A-Za-z_])(?:[-(]|\d|n(?![A-Za-z_])|(?:" + "|".join(
    sorted(map(re.escape, ALIASES), key=len, reverse=True)) + r")\s*[(_])")


def _data(text: str) -> dict | None:
    s = I.normalize_text(text).strip().rstrip(".…, ")
    s = re.sub(r"^[^-\d]*?(?=-?\d)", "", s) if re.match(r"^[^\d]{0,40}?-?\d", s) else s
    parts = [p for p in re.split(r"[,;\s]+", s) if p]
    if len(parts) < 6 or not all(re.fullmatch(r"-?\d+(/\d+)?", p) for p in parts):
        return None
    if len(parts) > 400 or any(len(p) > 4000 for p in parts):
        return None
    return {"columns": ["n", "a"], "rows": [[i, p] for i, p in enumerate(parts)]}


def recognise(text: str) -> Intent:
    text = (text or "").strip()[:4000]
    it = Intent("unknown", text)
    if not text:
        return it
    table = _data(text)
    if table is not None:
        it.kind, it.table, it.first, it.last = "data", table, 0, len(table["rows"]) - 1
        return it
    folded, upto = _range(I.fold(I.normalize_text(text)))
    for fid, fam in GRAPH_FAMILIES.items():
        m = re.search(r"\b(" + fam["re"] + r")\b", folded)
        if m and _residue_ok(re.sub(r"\b(invariants?|a n sommets|with n vertices|on n vertices|petits?|small|sommets|"
                                    r"vertices|relations? entre|relations? between|leurs?|their)\b", " ",
                                    folded[:m.start()] + " " + folded[m.end():])):
            it.kind, it.family, it.first = "family", fid, 2
            it.last = max(3, min(upto or (6 if fid != "trees" else 9), fam["exhaust"]))
            return it
    # the range is cut from the original text too (same regex on a folded copy keeps positions only approximately)
    plain = re.sub(r"(?i)(?:jusqu['’]?\s?[aà]|up to|pour n (?:<=?|≤)|for n (?:<=?|up to))\s*(?:n\s*=\s*)?\d{1,5}\b", " ",
                   text) if upto is not None else text
    parts = [p for p in re.split(r"\s+(?:et|and|vs\.?|versus|contre)\s+|\s*;\s*", plain) if p.strip()]
    found = []
    for p in (parts if 1 < len(parts) <= 3 else [plain]):
        one = _one(p)
        if one is None:
            found = []
            break
        found.append(one)
    if not found and len(parts) > 1:
        one = _one(plain)
        found = [one] if one else []
    if not found:
        return it
    it.kind = "sequence"
    for name, (tree, n0, fr, en, tex) in zip("abc", found):
        it.seqs.append(SeqDef(name, tree, n0, fr, en, tex))
    it.first = max(s.n0 for s in it.seqs)
    it.last = min(upto, MAX_TERMS) if upto else it.first + DEFAULT_TERMS - 1
    if it.last < it.first + 7:
        it.last = it.first + 7
    return it


# ================================================================ code of the experiment, driver, local evaluation
def experiment_code(it: Intent, language: str, lang: str = "fr") -> str:
    """The deterministic cell of a recognised request: same request, same code."""
    title = ("# Moteur de conjectures — " if lang == "fr" else "# Conjecture engine — ") + it.summary(lang)
    if it.kind == "family":
        if language != "sage":
            raise CatalogError("family_needs_sage")
        f = GRAPH_FAMILIES[it.family]
        cols = [c[0] for c in GRAPH_COLUMNS] + ["graph6"]
        return (f"{title}\ndef cj_invariants(G):\n"
                "    return [G.order(), G.size(), max(G.degree()), min(G.degree()), G.chromatic_number(),\n"
                "            G.clique_number(), len(G.independent_set()), G.diameter(), G.graph6_string()]\n\n"
                "def cj_rows_for(n):\n"
                f"    if n <= {f['exhaust']}:\n"
                f"        return [cj_invariants(G) for G in {f['gen']}]\n"
                "    rows = []\n"
                "    for j in range(60):\n"
                f"        G = {f['rand']}\n"
                f"        if G.order() == n and {f['keep']}:\n"
                "            rows.append(cj_invariants(G))\n"
                "    return rows\n\n"
                f"cj_columns = {cols!r}\n"
                f"cj_index = list(range({it.first}, {it.last + 1}))\n"
                "cj_rows = [r for n in cj_index for r in cj_rows_for(n)]\n"
                "table(cj_rows[:30], header_row=cj_columns)\n")
    if it.kind != "sequence":
        raise CatalogError("no_code")
    env = {"n": "n"}
    exprs = [to_code(s.tree, language, env) for s in it.seqs]
    cols = ["n"] + [s.name for s in it.seqs]
    head = ""
    if language == "python":
        head = "import math\nfrom fractions import Fraction\n\n" + python_defs([s.tree for s in it.seqs])
    conv = "    n = ZZ(n)\n" if language == "sage" else "    n = int(n)\n"
    show = ("table(cj_rows[:30], header_row=cj_columns)\n" if language == "sage" else
            "print(*cj_columns)\nfor r in cj_rows[:30]:\n    print(*r)\n")
    return (f"{title}\n{head}def cj_rows_for(n):\n{conv}    return [[n, {', '.join(exprs)}]]\n\n"
            f"cj_columns = {cols!r}\n"
            f"cj_index = list(range({it.first}, {it.last + 1}))\n"
            "cj_rows = [r for n in cj_index for r in cj_rows_for(n)]\n" + show)


DRIVER = r'''
def _madalean_cj(_idx, _budget, _max_rows):
    import json as _json, time as _time
    _t0 = _time.time()
    def _s(v):
        if isinstance(v, bool):
            return str(v)
        try:
            if v == int(v) and not isinstance(v, float):
                return str(int(v))
        except Exception:
            pass
        return str(v)[:4000]
    _rows, _done, _err = [], [], ""
    try:
        if _idx is None:
            _rows = [[_s(v) for v in r] for r in list(cj_rows)[:_max_rows]]
            _done = [int(n) for n in cj_index]
        else:
            for n in _idx:
                if _time.time() - _t0 > _budget or len(_rows) >= _max_rows:
                    break
                for r in cj_rows_for(n):
                    _rows.append([_s(v) for v in r])
                _done.append(int(n))
        _cols = [str(c) for c in cj_columns]
    except Exception as _e:
        _cols, _err = [], type(_e).__name__ + ": " + str(_e)[:500]
    print("MADALEAN_CJ " + _json.dumps({"columns": _cols, "rows": _rows, "done": _done, "error": _err,
                                         "seconds": float(_time.time() - _t0)}))
_madalean_cj(%s, %s, %s)
del _madalean_cj
'''


def driver(indices: list[int] | None, budget_s: float = 20.0, max_rows: int = MAX_ROWS) -> str:
    """Madalean's fixed program that reads the experiment's table (`indices` None: the rows the cell computed; a
    list: `cj_rows_for` at those indices, within a time budget). Only integers enter it."""
    idx = "None" if indices is None else json.dumps([int(i) for i in indices[:20000]])
    return DRIVER % (idx, float(budget_s), int(max_rows))


def parse_driver(stdout: str) -> dict | None:
    for line in reversed((stdout or "").splitlines()):
        if line.startswith(MARK):
            try:
                d = json.loads(line[len(MARK):])
            except ValueError:
                return None
            if isinstance(d, dict) and isinstance(d.get("rows"), list) and isinstance(d.get("columns"), list):
                return d
    return None


def local_rows(it: Intent, indices: list[int]) -> dict:
    """The table of a recognised sequence computed in this process (demo mode; reference for the tests)."""
    rows, done = [], []
    for n in indices:
        try:
            row = [str(n)]
            for s in it.seqs:
                v = evaluate(s.tree, {"n": n})
                row.append(str(v.numerator) if v.denominator == 1 else f"{v.numerator}/{v.denominator}")
        except (CatalogError, ValueError, OverflowError, ZeroDivisionError):
            break
        rows.append(row)
        done.append(n)
    return {"columns": ["n"] + [s.name for s in it.seqs], "rows": rows, "done": done, "error": "", "seconds": 0.0}


CONTRACT = (
    "Write ONE {lang} cell that produces a table of exact data for the question below. The cell MUST define:\n"
    "- `cj_columns`: the list of column names (strings); for a sequence use ['n', 'a'];\n"
    "- `cj_rows_for(n)`: a function returning the LIST of rows of the table for the integer index n (one row "
    "[n, a(n)] for a sequence; one row per object of size n for a family of objects), exact values only "
    "(integers or rationals, no floating point);\n"
    "- `cj_index`: the list of indices of the first experiment (about 40 to 60 for a sequence; small sizes for "
    "objects), keeping the run under 20 seconds;\n"
    "- `cj_rows = [r for n in cj_index for r in cj_rows_for(n)]`, then display the first rows.\n"
    "No file, network or shell access. Answer with one fenced code block only.\n\nQuestion: {question}")


def model_messages(question: str, language: str) -> list[dict]:
    name = "SageMath" if language == "sage" else "Python 3 (standard library only)"
    return [{"role": "user", "content": "[madalean:explore] task=experiment language=" + language + "\n" +
             CONTRACT.format(lang=name, question=question[:3000])}]


def contract_ok(code: str) -> bool:
    return bool(re.search(r"(?m)^def cj_rows_for\s*\(", code) and re.search(r"(?m)^cj_columns\s*=", code)
                and re.search(r"(?m)^cj_index\s*=", code))
