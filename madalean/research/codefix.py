"""Deterministic canonicalization and repair of Calcul cells (session S-AG, DECISIONS D39) — no model involved.

- **Imports at the top, deduplicated, ordered** (`import a` lines sorted, then `from a import b, c` merged and sorted;
  `from __future__` first). Only top-level imports move; the rest of the cell is left byte for byte.
- **Missing imports / library loads added** from a static analysis of the names the cell uses (Python: `ast`; Sage: a
  light preparse to Python, then `ast`) against: the usual aliases (`np`, `plt`, `sp`, `math`, `Fraction`…), the
  names sympy exports (from the catalogue build of the kernel's Python), Madalean's naming conventions of the
  catalogue (`F125` → `F125.<a> = GF(5^3)`, `Z12` → `Zmod(12)`), and the single-line definitions of earlier cells
  (`prev`: name → line), so a cell never « forgets » what it relies on.
- **After a run error**: `NameError: name 'np' is not defined` & co. → the same fixer, before any model is asked."""
from __future__ import annotations

import ast
import builtins
import re

from . import codecat
from . import intent as I

ALIASES: dict[str, str] = {
    "np": "import numpy as np", "numpy": "import numpy", "plt": "import matplotlib.pyplot as plt",
    "mpl": "import matplotlib as mpl", "matplotlib": "import matplotlib", "sp": "import sympy as sp",
    "sympy": "import sympy", "scipy": "import scipy", "pd": "import pandas as pd", "math": "import math",
    "cmath": "import cmath", "random": "import random", "itertools": "import itertools",
    "functools": "import functools", "fractions": "import fractions", "collections": "import collections",
    "time": "import time", "re": "import re", "json": "import json", "decimal": "import decimal",
    "statistics": "import statistics", "operator": "import operator", "string": "import string",
    "Fraction": "from fractions import Fraction", "Decimal": "from decimal import Decimal",
    "product": "from itertools import product", "combinations": "from itertools import combinations",
    "permutations": "from itertools import permutations", "accumulate": "from itertools import accumulate",
    "reduce": "from functools import reduce", "lru_cache": "from functools import lru_cache",
    "cache": "from functools import cache", "Counter": "from collections import Counter",
    "defaultdict": "from collections import defaultdict", "deque": "from collections import deque",
    "comb": "from math import comb", "perm": "from math import perm", "isqrt": "from math import isqrt",
}
# names that belong to sympy (fallback when the catalogue of the kernel's Python is not built yet)
SYMPY_BASE = {
    "symbols", "Symbol", "Function", "Eq", "solve", "solveset", "nsolve", "simplify", "expand", "factor", "factorint",
    "factor_list", "integrate", "diff", "limit", "summation", "series", "Matrix", "eye", "zeros", "ones", "Rational",
    "Integer", "Poly", "roots", "nroots", "sqrt", "sin", "cos", "tan", "exp", "log", "pi", "E", "I", "oo", "Abs",
    "gcd", "lcm", "isprime", "primerange", "prime", "nextprime", "divisors", "totient", "mod_inverse", "binomial",
    "factorial", "lambdify", "latex", "N", "Sum", "Integral", "Derivative", "Limit", "dsolve", "apart", "together",
    "cancel", "collect", "trigsimp", "Piecewise", "floor", "ceiling", "atan", "asin", "acos", "sinh", "cosh",
    "tanh", "plot", "Interval", "S", "Float", "nsimplify", "re", "im", "conjugate", "arg", "GF", "FiniteField",
    "ZZ", "QQ", "RR", "CC", "minimal_polynomial", "Product", "product", "subsets", "Max", "Min", "zeta", "gamma"}
_GF_NAME = re.compile(r"F(\d+)")
_ZMOD_NAME = re.compile(r"Z(\d+)")


def sympy_names() -> set[str]:
    st = codecat.status("python") or {}
    names = set(st.get("sympy_names") or ())
    return names or SYMPY_BASE


def convention_line(name: str, language: str) -> str:
    """The catalogue's canonical construction of a conventional name (`F125`, `F7`, `Z12`) — '' otherwise."""
    if language != "sage":
        return ""
    m = _GF_NAME.fullmatch(name)
    if m:
        pp = I.prime_power(int(m.group(1)))
        if pp:
            return f"{name} = GF({pp[0]})" if pp[1] == 1 else f"{name}.<a> = GF({pp[0]}^{pp[1]})"
    m = _ZMOD_NAME.fullmatch(name)
    if m and int(m.group(1)) >= 2:
        return f"{name} = Zmod({m.group(1)})"
    return ""


# ---------------------------------------------------------------- Sage → parseable Python (for name analysis)
def sage_to_py(code: str) -> str:
    """A light Sage preparse, enough for `ast` (generators `R.<x> = …`, `^`, `[a..b]`, `f(x) = …`)."""
    s = re.sub(r"(?m)^(\s*)([A-Za-z_]\w*)\.<([\w\s,]+)>\s*=", lambda m: f"{m.group(1)}{m.group(2)}, ({m.group(3)},) = ",
               code)
    s = re.sub(r"(?m)^(\s*)([A-Za-z_]\w*)\(([\w\s,]+)\)\s*=(?!=)", lambda m: f"{m.group(1)}{m.group(2)} = lambda "
               f"{m.group(3)}: ", s)
    s = re.sub(r"\[([^\[\]]+?)\.\.([^\[\]]+?)\]", r"[\1, \2]", s)
    return s.replace("^", "**")


def _names(tree: ast.AST) -> tuple[set[str], set[str]]:
    loads, stores = set(), set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Name):
            (loads if isinstance(n.ctx, ast.Load) else stores).add(n.id)
        elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            stores.add(n.name)
        elif isinstance(n, ast.arg):
            stores.add(n.arg)
        elif isinstance(n, (ast.Import, ast.ImportFrom)):
            stores.update((a.asname or a.name).split(".")[0] for a in n.names)
        elif isinstance(n, ast.ExceptHandler) and n.name:
            stores.add(n.name)
        elif isinstance(n, ast.alias):
            pass
    return loads, stores


def used_undefined(code: str, language: str, known: set[str] | None = None,
                   sage_names: set[str] | None = None) -> list[str] | None:
    """Names the cell reads but nothing defines (cell, builtins, earlier cells / kernel `known`, Sage's global
    namespace `sage_names` for Sage). None when the cell does not parse."""
    src = sage_to_py(code) if language == "sage" else code
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return None
    loads, stores = _names(tree)
    defined = stores | set(known or ()) | set(dir(builtins)) | {"display", "get_ipython", "tex", "fig", "report",
                                                                  "show", "In", "Out", "_", "__", "___"}
    if language == "sage":
        defined |= set(sage_names or ()) | {"x"}
    return sorted(n for n in loads if n not in defined and not n.startswith("_"))


# ---------------------------------------------------------------- imports at the top
def _split_imports(code: str, language: str) -> tuple[list[str], list[str]] | None:
    """(top-level import lines, the other lines) — None when the cell does not parse."""
    src = sage_to_py(code) if language == "sage" else code
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return None
    lines = code.split("\n")
    take: set[int] = set()
    imps: list[str] = []
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            a, b = node.lineno - 1, (node.end_lineno or node.lineno) - 1
            seg = "\n".join(lines[a:b + 1])
            if ";" in seg or seg.strip().startswith("#") or len(seg.split("\n")) > 1 and "(" not in seg:
                continue                    # `import a; b = 1`: left where it is
            take.update(range(a, b + 1))
            if isinstance(node, ast.Import):
                for al in node.names:
                    imps.append(f"import {al.name}" + (f" as {al.asname}" if al.asname else ""))
            else:
                mod = "." * (node.level or 0) + (node.module or "")
                for al in node.names:
                    imps.append(f"from {mod} import {al.name}" + (f" as {al.asname}" if al.asname else ""))
    rest = [l for i, l in enumerate(lines) if i not in take]
    return imps, rest


def _sorted_imports(imps: list[str]) -> list[str]:
    fut = sorted({l for l in imps if l.startswith("from __future__")})
    plain = sorted({l for l in imps if l.startswith("import ")})
    froms: dict[str, list[str]] = {}
    for l in imps:
        m = re.fullmatch(r"from\s+(\S+)\s+import\s+(.+)", l)
        if m and m.group(1) != "__future__":
            froms.setdefault(m.group(1), [])
            if m.group(2) not in froms[m.group(1)]:
                froms[m.group(1)].append(m.group(2))
    out = fut + plain
    for mod in sorted(froms):
        names = froms[mod]
        out.append(f"from {mod} import " + ("*" if "*" in names else ", ".join(sorted(names, key=str.lower))))
    return out


def canonicalize(code: str, language: str, known: set[str] | None = None, prev: dict[str, str] | None = None,
                 sage_names: set[str] | None = None, check_missing: bool = True) -> dict:
    """→ {code, added: [lines], missing: [names still undefined]}. Never raises; the cell is returned unchanged
    when it does not parse."""
    code = (code or "").strip("\n")
    parts = _split_imports(code, language)
    if parts is None:
        return {"code": code, "added": [], "missing": []}
    imps, rest = parts
    body = "\n".join(rest).strip("\n")
    missing = (used_undefined(code, language, known, sage_names) or []) if check_missing else []
    added: list[str] = []
    defs: list[str] = []
    star_sympy = any(l == "from sympy import *" for l in imps)
    sy = sympy_names() if language == "python" else set()
    left = []
    for n in missing:
        line = ALIASES.get(n)
        if line:
            imps.append(line)
            added.append(line)
            continue
        if language == "python" and n in sy and not star_sympy:
            imps.append(f"from sympy import {n}")
            added.append(f"from sympy import {n}")
            continue
        conv = convention_line(n, language)
        if conv:
            defs.append(conv)
            added.append(conv)
            continue
        if prev and n in prev:
            defs.append(prev[n])
            added.append(prev[n])
            continue
        left.append(n)
    head = _sorted_imports(imps)
    out = "\n".join(head + defs + ([body] if body else [])).strip("\n")
    return {"code": out, "added": added, "missing": left}


_NAME_ERR = re.compile(r"NameError: (?:global )?name '([A-Za-z_]\w*)' is not defined")
_MOD_ERR = re.compile(r"(?:ModuleNotFoundError|ImportError): No module named '([\w.]+)'")


def fix_error(code: str, error: str, language: str, known: set[str] | None = None,
              prev: dict[str, str] | None = None, sage_names: set[str] | None = None) -> dict | None:
    """A deterministic repair of a run error (missing import / library load / earlier definition) → {code, added}
    or None when this error is not of that kind (then a model repairs it)."""
    m = _NAME_ERR.search(error or "")
    if not m:
        return None
    name = m.group(1)
    res = canonicalize(code, language, (known or set()) - {name}, prev, sage_names)
    if res["added"] and name not in res["missing"] and res["code"] != code.strip("\n"):
        return {"code": res["code"], "added": res["added"]}
    return None


def prev_definitions(sources: list[str], language: str) -> dict[str, str]:
    """name → its single-line definition in earlier cells (the last one wins): `F9.<a> = GF(3^2)`, `f = x^2 + 1`.
    Only simple top-level assignments without other names of the cell (safe to copy)."""
    out: dict[str, str] = {}
    for src in sources:
        for line in (src or "").split("\n"):
            if not line or line[0].isspace() or line.lstrip().startswith("#"):
                continue
            m = re.match(r"([A-Za-z_]\w*)(?:\.<[\w\s,]+>)?\s*=(?!=)\s*(.+)$", line)
            if not m or ";" in line:
                continue
            rhs = m.group(2)
            if re.search(r"\b(input|open|exec|eval|__import__)\s*\(", rhs):
                continue
            out[m.group(1)] = line.strip()
    return out


def enforce_prefix(code: str, prefix: str) -> str:
    """The canonical constructions first; the model's own (re)definitions of the same names are dropped, so the
    structure is the catalogue's every time (« F125.<a> = GF(5^3) », never « GF(125, 'b') » one day and « F » the
    next)."""
    if not prefix.strip():
        return code
    pre_lines = [l for l in prefix.split("\n") if l.strip()]
    pre_names = set()
    for l in pre_lines:
        m = re.match(r"([\w\s,]+?)(?:\.<[\w\s,]+>)?\s*=(?!=)", l)
        if m:
            pre_names |= {x.strip() for x in m.group(1).split(",") if x.strip()}
        m = re.match(r"[A-Za-z_]\w*\.<([\w\s,]+)>", l)
        if m:
            pre_names |= {x.strip() for x in m.group(1).split(",")}
    pre_imports = [l for l in pre_lines if re.match(r"(import|from)\s", l)]
    pre_defs = [l for l in pre_lines if l not in pre_imports]
    keep = []
    for l in code.split("\n"):
        s = l.strip()
        if s in pre_lines:
            continue
        m = re.match(r"([\w\s,]+?)(?:\.<([\w\s,]+)>)?\s*=(?!=)", l)
        if m and not l[:1].isspace():
            lhs = {x.strip() for x in m.group(1).split(",") if x.strip()}
            gens = {x.strip() for x in (m.group(2) or "").split(",") if x.strip()}
            if lhs and lhs <= pre_names and (not gens or gens <= pre_names or lhs & {"R", "K"} or
                                              any(re.fullmatch(r"F\d+|Z\d+", n) for n in lhs)):
                continue                # the model redefined a canonical object: the catalogue's wins
        keep.append(l)
    body = "\n".join(keep).strip("\n")
    return "\n".join(pre_imports + pre_defs + ([body] if body else []))
