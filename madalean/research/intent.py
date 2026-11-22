"""Request analysis for the Calcul screen (session S-AG, DECISIONS D39): a request in words (French / English, with
LaTeX or Unicode notation) → a normalized, deterministic **intent** — the operation, the mathematical objects with
canonical parameters, the expressions in one canonical spelling, the variables — without any model.

Why: the same request written « F_125 », « F_{5^3} », « \\mathbb{F}_{125} », « GF(125) » or « 𝔽₁₂₅ » must give the
same code every time (one canonical construction, `codecat.py`), and the « best version » of a request is stored
under its intent key, not under its words (`recipes.py`).

- Objects: finite fields (order factored: a non prime power is refused with a clear message), Z/nZ, base rings
  (Q, Z, R, C, Z[i]), polynomial rings K[x, y], number fields (Q(√d), Q(i), Q(ζ_n), Q(∛2)), matrices (literals,
  M_n(K)), groups (S_n, A_n, D_n, C_n), elliptic curves (Weierstrass equation or Cremona label), integers.
- Operations: factor, roots, solve, integrate, derivative, limit, sum, Taylor series, plot, simplify, expand, gcd,
  lcm, determinant, inverse, eigenvalues, rank, kernel, characteristic polynomial, order, elements, irreducibility,
  primes, divisors, Euler φ, …
- Expressions: own tokenizer (no sympy in the server's environment): implicit products (`4x`, `2(x+1)`, `x sin(x)`),
  `²`, `√`, `π`, `∞`, LaTeX (`\\frac`, `\\sqrt`, `\\sin`, `\\cdot`, `e^{x}`), one canonical spelling
  (`x^5 + 4*x - 1`).

`analyze(text, known)` never raises; `Intent.coverage` says whether the catalogue can write the whole cell ("full"),
only its objects ("partial": the model writes the rest after the canonical constructions) or nothing ("none")."""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass, field

INTENT_VERSION = 1            # bump when keys change: stored best versions are re-keyed by recipes.migrate

# ================================================================ small number theory (orders up to 10^12)


def factor_int(n: int) -> list[tuple[int, int]]:
    out, d = [], 2
    while d * d <= n:
        e = 0
        while n % d == 0:
            n //= d
            e += 1
        if e:
            out.append((d, e))
        d += 1 if d == 2 else 2
    if n > 1:
        out.append((n, 1))
    return out


def prime_power(q: int) -> tuple[int, int] | None:
    """q = p^k with p prime, k ≥ 1 → (p, k); otherwise None."""
    if q < 2 or q > 10 ** 12:
        return None
    f = factor_int(q)
    return f[0] if len(f) == 1 else None


def squarefree(d: int) -> int:
    """Squarefree part with sign: 8 → 2, -12 → -3, 9 → 1."""
    if d == 0:
        return 0
    s = 1
    for p, e in factor_int(abs(d)):
        if e % 2:
            s *= p
    return s if d > 0 else -s


def is_prime(n: int) -> bool:
    pp = prime_power(n)
    return pp is not None and pp[1] == 1


# ================================================================ text normalization
_SUP = str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹⁻⁺", "0123456789-+")
_SUB = str.maketrans("₀₁₂₃₄₅₆₇₈₉", "0123456789")
_SUP_RUN = re.compile(r"[⁰¹²³⁴⁵⁶⁷⁸⁹⁻⁺]+")
_SUB_RUN = re.compile(r"[₀₁₂₃₄₅₆₇₈₉]+")
_LATEX_BB = re.compile(r"\\(?:mathbb|mathbf|Bbb|mathrm|mathcal|mathfrak|mathsf|bf|rm)\s*\{\s*([A-Za-z])\s*\}"
                       r"|\\(?:mathbb|Bbb|mathfrak)\s+([A-Za-z])")


def normalize_text(text: str) -> str:
    """Unicode / LaTeX notation → plain ASCII-like notation, case kept (F vs f matters)."""
    t = text or ""
    t = _SUP_RUN.sub(lambda m: "^" + m.group(0).translate(_SUP) if len(m.group(0)) == 1
                     else "^(" + m.group(0).translate(_SUP) + ")", t)
    t = _SUB_RUN.sub(lambda m: "_{" + m.group(0).translate(_SUB) + "}", t)
    t = t.replace("𝔖", "S").replace("ℤ", "Z").replace("ℚ", "Q").replace("ℝ", "R").replace("ℂ", "C")
    t = t.replace("𝔽", "F").replace("ℕ", "N")
    t = unicodedata.normalize("NFKC", t)
    t = _LATEX_BB.sub(lambda m: m.group(1) or m.group(2), t)
    for a, b in (("−", "-"), ("–", "-"), ("×", "*"), ("·", "*"), ("÷", "/"), ("π", "pi"), ("∞", "oo"),
                 ("’", "'"), ("≤", "<="), ("≥", ">="), ("→", "->"), ("∈", " in "), ("ζ", "zeta"), ("∑", " sum "),
                 ("∫", " integral "), ("√", "sqrt")):
        t = t.replace(a, b)
    t = re.sub(r"\\(left|right|displaystyle|,|;|!|quad)", " ", t)
    t = re.sub(r"\\(sum|int|lim|prod)(?![A-Za-z])", lambda m: " " + {"int": "integral", "lim": "limit"}.get(
        m.group(1), m.group(1)) + " ", t)
    t = t.replace("\\{", "(").replace("\\}", ")")
    # LaTeX formulas: derivative operator, fractions, roots, products, named functions / constants
    t = re.sub(r"\\[dt]?frac\s*\{\s*d\s*\}\s*\{\s*d\s*([a-z])\s*\}|(?<![\w/])d\s*/\s*d([a-z])\b", " derivee ", t)
    for _ in range(4):
        t = re.sub(r"\\[dt]?frac\s*\{([^{}]*)\}\s*\{([^{}]*)\}", r"((\1)/(\2))", t)
        t = re.sub(r"\\sqrt\s*\[([^\]]*)\]\s*\{([^{}]*)\}", r"((\2)^(1/(\1)))", t)
        t = re.sub(r"\\sqrt\s*\{([^{}]*)\}", r"sqrt(\1)", t)
    t = re.sub(r"\\(cdot|times)(?![A-Za-z])", "*", t)
    t = re.sub(r"\\infty(?![A-Za-z])", "oo", t)
    t = re.sub(r"\\ln(?![A-Za-z])", "log", t)
    t = re.sub(r"\\(" + "|".join(sorted(FUNCS | {"pi"})) + r")(?![A-Za-z])", r"\1", t)
    return re.sub(r"[ \t]+", " ", t).strip()


def fold(s: str) -> str:
    """Lowercase, accents removed: for the words of the request."""
    s = unicodedata.normalize("NFKD", s)
    return "".join(ch for ch in s if not unicodedata.combining(ch)).lower()


# ================================================================ expressions
FUNCS = {"sin", "cos", "tan", "cot", "sec", "csc", "arcsin", "arccos", "arctan", "asin", "acos", "atan", "sinh",
         "cosh", "tanh", "arcsinh", "arccosh", "arctanh", "exp", "log", "ln", "sqrt", "abs", "floor", "ceil",
         "gamma", "zeta", "binomial", "factorial", "erf", "sign", "max", "min", "cbrt"}
CONSTS = {"pi", "e", "oo", "I", "i"}
VARS = set("xyztuvwnkmabcpqs")       # single letters that multiply when followed by « ( »
_TOK = re.compile(r"\s*(\d+(?:\.\d+)?|[A-Za-z_][A-Za-z_0-9]*|\*\*|==|<=|>=|!=|[-+*/^(),=<>!|])")


class ExprError(ValueError):
    pass


def _latex_expr(s: str) -> str:
    """LaTeX math → plain notation (best effort, then the tokenizer validates)."""
    s = s.replace("$", " ")
    for _ in range(4):                                  # nested \frac / \sqrt
        s = re.sub(r"\\[dt]?frac\s*\{([^{}]*)\}\s*\{([^{}]*)\}", r"((\1)/(\2))", s)
        s = re.sub(r"\\sqrt\s*\[([^\]]*)\]\s*\{([^{}]*)\}", r"((\2)^(1/(\1)))", s)
        s = re.sub(r"\\sqrt\s*\{([^{}]*)\}", r"sqrt(\1)", s)
        s = re.sub(r"\^\s*\{([^{}]*)\}", r"^(\1)", s)
    s = re.sub(r"\\(cdot|times)", "*", s)
    s = re.sub(r"\\(infty)", "oo", s)
    s = re.sub(r"\\(pi)\b", "pi", s)
    s = re.sub(r"\\(ln)\b", "log", s)
    s = re.sub(r"\\([A-Za-z]+)", r"\1", s)
    return s.replace("{", "(").replace("}", ")")


def tokens(s: str) -> list[str]:
    s = _latex_expr(s.replace("√", "sqrt").replace("π", "pi").replace("∞", "oo").replace("−", "-"))
    s = re.sub(r"\|([^|]+)\|", r"abs(\1)", s)
    s = re.sub(r"\bsqrt\s*(\d+(?:\.\d+)?|[A-Za-z])(?![\w(])", r"sqrt(\1)", s)    # √2, √x
    out, pos = [], 0
    while pos < len(s):
        if s[pos:].strip() == "":
            break
        m = _TOK.match(s, pos)
        if not m:
            raise ExprError(f"unexpected {s[pos:pos + 10]!r}")
        out.append(m.group(1))
        pos = m.end()
    return out


def _atom_end(t: str) -> bool:
    return bool(re.fullmatch(r"\d+(?:\.\d+)?|[A-Za-z_]\w*", t)) or t in (")", "!")


def _atom_start(t: str) -> bool:
    return bool(re.fullmatch(r"\d+(?:\.\d+)?|[A-Za-z_]\w*", t)) or t == "("


def _match(toks: list[str], i: int) -> int:
    depth = 0
    for j in range(i, len(toks)):
        depth += toks[j] == "("
        depth -= toks[j] == ")"
        if depth == 0:
            return j
    return -1


def _strip_parens(toks: list[str]) -> list[str]:
    """Redundant parentheses: around one atom (`(1)/(2)` → `1/2`, not a call's) and around the whole formula."""
    out = list(toks)
    i = 0
    while i < len(out) - 2:
        prev = out[i - 1] if i else ""
        if out[i] == "(" and not re.fullmatch(r"[A-Za-z_]\w*", prev or "-") and prev != "^":
            j = _match(out, i)
            inner = out[i + 1:j]
            atom = len(inner) == 1 and re.fullmatch(r"\d+(?:\.\d+)?|[A-Za-z_]\w*", inner[0])
            call = len(inner) >= 3 and re.fullmatch(r"[A-Za-z_]\w*", inner[0]) and inner[1] == "(" and \
                _match(inner, 1) == len(inner) - 1
            if j > 0 and (atom or call):
                out = out[:i] + inner + out[j + 1:]
                i = max(i - 1, 0)
                continue
        i += 1
    while len(out) > 2 and out[0] == "(" and _match(out, 0) == len(out) - 1:
        out = out[1:-1]
    return out


def normalize_expr(s: str, known: set[str] | frozenset = frozenset()) -> str:
    """One canonical spelling of a formula (Sage syntax: `^`, explicit `*`, ` + ` / ` - ` spaced at every level,
    `==` for equations). Raises ExprError when it is not a formula."""
    toks = tokens(s)
    if not toks:
        raise ExprError("empty")
    toks = ["^" if t == "**" else t for t in toks]
    toks = ["log" if t == "ln" else t for t in toks]
    # sin^2(x) → sin(x)^2
    fixed: list[str] = []
    i = 0
    while i < len(toks):
        t = toks[i]
        if t in FUNCS and i + 3 < len(toks) and toks[i + 1] == "^" and re.fullmatch(r"\d+", toks[i + 2]) \
                and toks[i + 3] == "(":
            depth, j = 0, i + 3
            while j < len(toks):
                depth += toks[j] == "("
                depth -= toks[j] == ")"
                if depth == 0:
                    break
                j += 1
            fixed += [t] + toks[i + 3:j + 1] + ["^", toks[i + 2]]
            i = j + 1
            continue
        fixed.append(t)
        i += 1
    toks = fixed
    out: list[str] = []
    for i, t in enumerate(toks):
        if out:
            prev = out[-1]
            call = prev in FUNCS or prev in ("f", "g", "h") or (prev in known and prev not in VARS) or (
                re.fullmatch(r"[A-Za-z_]\w*", prev or "") and prev not in VARS and prev not in CONSTS
                and len(prev) > 1)
            if _atom_end(prev) and _atom_start(t) and not (t == "(" and call):
                if not (re.fullmatch(r"[A-Za-z_]\w*", prev) and prev in FUNCS):
                    out.append("*")
        out.append(t)
    depth = 0
    for t in out:
        depth += t == "("
        depth -= t == ")"
        if depth < 0:
            raise ExprError("unbalanced")
    if depth:
        raise ExprError("unbalanced")
    if out[-1] in "+-*/^(,=<>" or out[0] in "*/^),=<>":
        raise ExprError("dangling operator")
    if any(a in "+-*/^" and b in "*/^)" or a in "*/^" and b == "+" for a, b in zip(out, out[1:])):
        raise ExprError("operator sequence")
    out = _strip_parens(out)
    # `e^(…)` → exp(…), `e^x` → exp(x)
    res: list[str] = []
    i = 0
    while i < len(out):
        if out[i] == "e" and i + 1 < len(out) and out[i + 1] == "^" and (i == 0 or out[i - 1] != "."):
            if out[i + 2] == "(":
                depth, j = 0, i + 2
                while j < len(out):
                    depth += out[j] == "("
                    depth -= out[j] == ")"
                    if depth == 0:
                        break
                    j += 1
                res += ["exp"] + out[i + 2:j + 1]
                i = j + 1
                continue
            j = i + 2
            if out[j] == "-":
                j += 1
            res += ["exp", "("] + out[i + 2:j + 1] + [")"]
            i = j + 1
            continue
        res.append(out[i])
        i += 1
    # spacing
    s2 = ""
    for i, t in enumerate(res):
        prev = res[i - 1] if i else ""
        if t in ("+", "-") and i and prev not in "(,^*/=<>" and prev not in ("+", "-", "==", "<=", ">=", "!="):
            s2 += f" {t} "
        elif t in ("=", "==", "<", ">", "<=", ">=", "!="):
            s2 += " == " if t in ("=", "==") else f" {t} "
        elif t == ",":
            s2 += ", "
        else:
            s2 += t
    return re.sub(r"\s+", " ", s2).strip()


def expr_names(e: str) -> list[str]:
    """Free symbols of a canonical expression (no functions, no constants), sorted."""
    names = set(re.findall(r"(?<![\w.])([A-Za-z_]\w*)\b(?!\s*\()", e))
    return sorted(n for n in names if n not in FUNCS and n not in CONSTS and n not in ("oo",))


def to_python(e: str) -> str:
    """A canonical (Sage-syntax) expression → sympy syntax."""
    s = e.replace("^", "**")
    s = re.sub(r"(?<![\w.])e(?![\w(])", "E", s)
    s = re.sub(r"(?<![\w.])i(?![\w(])", "I", s)
    return s


# ================================================================ objects
@dataclass
class Obj:
    kind: str                       # gf, zmod, base, poly, numfield, matrix, matspace, group, ell, int
    params: dict
    span: tuple[int, int] = (0, 0)
    ring: "Obj | None" = None       # the coefficient ring of a poly / matrix space / curve (also in params by key)

    def key(self) -> str:
        return self.kind + json.dumps(self.params, sort_keys=True, separators=(",", ":"))


BASES = {"Q": "QQ", "QQ": "QQ", "Z": "ZZ", "ZZ": "ZZ", "R": "RR", "RR": "RR", "C": "CC", "CC": "CC"}


@dataclass
class Intent:
    text: str = ""
    op: str = ""
    objects: list[Obj] = field(default_factory=list)
    exprs: list[str] = field(default_factory=list)        # canonical formulas (equations contain « == »)
    ints: list[int] = field(default_factory=list)
    var: str = ""
    interval: tuple[str, str] | None = None
    point: str = ""                                       # limit point / expansion point
    side: str = ""                                        # limit: "+" or "-"
    order: int | None = None                              # derivative / Taylor order / degree
    sumvar: str = ""
    fname: str = ""                                       # « f(x) = … »: the function's name
    errors: list[dict] = field(default_factory=list)      # {code, fr, en}
    rest: list[str] = field(default_factory=list)         # significant words not understood

    # ---------------------------------------------------------------- derived
    def field_obj(self) -> Obj | None:
        return next((o for o in self.objects if o.kind in ("gf", "zmod", "base", "numfield")), None)

    def obj(self, kind: str) -> Obj | None:
        return next((o for o in self.objects if o.kind == kind), None)

    @property
    def recognized(self) -> bool:
        return bool(self.op or self.objects or self.exprs)

    def canonical(self) -> dict:
        return {"v": INTENT_VERSION, "op": self.op, "objects": [o.key() for o in self.objects],
                "exprs": self.exprs, "ints": self.ints, "var": self.var,
                "interval": list(self.interval) if self.interval else None, "point": self.point, "side": self.side,
                "order": self.order, "sumvar": self.sumvar, "fname": self.fname, "rest": sorted(set(self.rest))}

    def key(self) -> str:
        """Same intent ⇔ same key (F_125, F_{5^3}, GF(125) → one key). Unrecognized words stay in the key, so two
        requests that only share their objects are not confused."""
        raw = json.dumps(self.canonical(), sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        return hashlib.sha256(raw.encode()).hexdigest()[:20]

    def to_dict(self) -> dict:
        return {"op": self.op, "objects": [{"kind": o.kind, **o.params} for o in self.objects],
                "exprs": self.exprs, "ints": self.ints, "var": self.var,
                "interval": list(self.interval) if self.interval else None, "point": self.point,
                "order": self.order, "errors": self.errors, "key": self.key(),
                "summary": {"fr": summary(self, "fr"), "en": summary(self, "en")}}


# ================================================================ object recognition
def _span_free(spans: list[tuple[int, int]], a: int, b: int) -> bool:
    return all(b <= x or a >= y for x, y in spans)


_GF_PATTERNS = [
    # GF(5^3), GF(125), GF(5**3), Fq(…)
    re.compile(r"(?<![\w\\])(?:GF|FiniteField)\s*\(\s*(\d+)\s*(?:(?:\^|\*\*)\s*(\d+))?\s*(?:,[^)]*)?\)"),
    # F_{5^3}, F_{125}, F_{(5^3)}
    re.compile(r"(?<![\w\\])F\s*_\s*\{\s*\(?\s*(\d+)\s*(?:\^\s*\(?\s*(\d+)\s*\)?)?\s*\)?\s*\}"),
    # F_125 (not F_5^3: that is F_5 cubed), F_(125)
    re.compile(r"(?<![\w\\])F\s*_\s*\(?(\d+)\)?(?!\s*\^)(?![\d.])"),
    # F125, F9 (only when a prime power: otherwise it is a name)
    re.compile(r"(?<![\w\\])F(\d{1,7})(?![\w.(])"),
]
_GF_WORDS = re.compile(r"(?:corps (?:fini )?(?:a|de|ayant|avec) |finite field (?:with |of order |of size |of )?)"
                       r"(\d+)(?:\s*\^\s*(\d+))?(?: elements?)?", re.I)
_ZMOD_PATTERNS = [
    re.compile(r"(?<![\w\\])Z\s*/\s*\(?\s*(\d+)\s*\)?\s*Z(?![\w])"),
    re.compile(r"(?<![\w\\])Z\s*/\s*\(\s*(\d+)\s*\)"),
    re.compile(r"(?<![\w\\])Z\s*/\s*(\d+)(?![\w\d])"),
    re.compile(r"(?<![\w.])(?:Zmod|Integers|IntegerModRing)\s*\(\s*(\d+)\s*\)"),
    re.compile(r"(?<![\w\\])Z_\{?(\d+)\}?(?![\w\d^])"),
]
_ZMOD_WORDS = re.compile(r"\b(?:entiers|integers) (?:modulo|mod) (\d+)\b", re.I)
_NUMFIELD = [
    (re.compile(r"(?<![\w\\])Q\s*\(\s*sqrt\s*\(?\s*(-?\d+)\s*\)?\s*\)"), "quad"),
    (re.compile(r"(?<![\w\\])Q\s*\(\s*i\s*\)"), "gauss"),
    (re.compile(r"(?<![\w\\])Q\s*\(\s*zeta\s*_?\s*\{?\s*(\d+)\s*\}?\s*\)"), "cyclo"),
    (re.compile(r"(?<![\w\\])Q\s*\(\s*(?:cbrt\s*\(\s*(\d+)\s*\)|\(?(\d+)\)?\s*\^\s*\(\s*1\s*/\s*(\d+)\s*\))\s*\)"),
     "root"),
]
_NF_WORDS = re.compile(r"(?:corps de nombres?|number field)\s*(?:defini par|defined by|de|of)?\s*(?:le polynome |the "
                       r"polynomial )?", re.I)
_GROUPS = [
    (re.compile(r"(?<![\w\\])(?:S|mathfrak S|SymmetricGroup\s*\()\s*_?\s*\{?\s*(\d{1,2})\s*\}?\)?(?![\w\d(^])"), "sym"),
    (re.compile(r"(?<![\w\\])(?:A|AlternatingGroup\s*\()\s*_\s*\{?\s*(\d{1,2})\s*\}?\)?(?![\w\d(^])"), "alt"),
    (re.compile(r"(?<![\w\\])AlternatingGroup\s*\(\s*(\d{1,2})\s*\)"), "alt"),
    (re.compile(r"(?<![\w\\])(?:D|DihedralGroup\s*\()\s*_\s*\{?\s*(\d{1,3})\s*\}?\)?(?![\w\d(^])"), "dih"),
    (re.compile(r"(?<![\w\\])DihedralGroup\s*\(\s*(\d{1,3})\s*\)"), "dih"),
    (re.compile(r"(?<![\w\\])C\s*_\s*\{?\s*(\d{1,4})\s*\}?(?![\w\d(^])"), "cyc"),
]
_GROUP_WORDS = [
    (re.compile(r"groupe symetrique (?:s_?\{?)?(?:de degre |d'ordre |sur |a )?(\d{1,2})|symmetric group "
                r"(?:s_?\{?)?(?:of degree |on )?(\d{1,2})", re.I), "sym"),
    (re.compile(r"groupe alterne (?:a_?\{?)?(?:de degre )?(\d{1,2})|alternating group (?:a_?\{?)?(?:of degree )?"
                r"(\d{1,2})", re.I), "alt"),
    (re.compile(r"groupe (?:diedral|dihedral) (?:d_?\{?)?(\d{1,3})|dihedral group (?:d_?\{?)?(\d{1,3})", re.I), "dih"),
    (re.compile(r"groupe cyclique (?:c_?\{?|z/)?(?:d'ordre |a )?(\d{1,4})|cyclic group (?:c_?\{?)?(?:of order )?"
                r"(\d{1,4})", re.I), "cyc"),
]
_MATSPACE = re.compile(r"(?<![\w\\])(M|GL|SL)\s*_\s*\{?\s*(\d{1,2})\s*\}?\s*\(\s*([^()]{1,20})\s*\)")
_MATRIX_LIT = re.compile(r"\[\s*\[[-\d\s,/./]+\](?:\s*,\s*\[[-\d\s,/./]+\])+\s*\]")
_PMATRIX = re.compile(r"\\begin\s*\{\s*[pbvB]?matrix\s*\}(.*?)\\end\s*\{\s*[pbvB]?matrix\s*\}", re.S)
_ELL_LABEL = re.compile(r"(?<![\w])(\d{1,6}[a-z]{1,3}\d{0,3})(?![\w])")
_INTERVAL = re.compile(r"(?:(?<![\w\])])\[\s*([^\[\],;]{1,30}?)\s*[,;]\s*([^\[\],;]{1,30}?)\s*\]"
                       r"|\]\s*([^\[\],;]{1,30}?)\s*[,;]\s*([^\[\],;]{1,30}?)\s*\[)")
_BETWEEN = re.compile(r"(?:(?:\bentre|\bbetween)\s+(-?[\w.^()/*+]+?)\s+(?:et|and)\s+(-?[\w.^()/*+]+?)"
                      r"|(?:\bde|\bfrom|\bpour (?:x|t) (?:allant )?de)\s+(-?[\w.^()/*+]+?)\s+(?:a|à|to)\s+"
                      r"(-?[\w.^()/*+]+?))(?=$|[\s,.;:!?])", re.I)
_RING_TOKEN = re.compile(r"(?<![\w\\])(QQ|ZZ|RR|CC|Q|Z|R|C)(?![\w'(/_])")


def _vars_list(s: str) -> list[str]:
    return [v.strip() for v in s.split(",") if v.strip()]


def _find_objects(t: str, known: set[str], it: Intent, spans: list[tuple[int, int]]) -> None:
    """Fill it.objects (in text order) and mark the spans they cover."""
    found: list[Obj] = []

    def add(kind: str, params: dict, a: int, b: int) -> Obj | None:
        if not _span_free(spans, a, b):
            return None
        o = Obj(kind, params, (a, b))
        spans.append((a, b))
        found.append(o)
        return o

    def gf(q: int, a: int, b: int, explicit: bool, raw: str) -> None:
        pp = prime_power(q)
        if pp is None:
            if explicit:
                spans.append((a, b))
                f = factor_int(q) if q >= 2 else []
                fs = " × ".join(f"{p}^{e}" if e > 1 else str(p) for p, e in f) or str(q)
                it.errors.append({"code": "not_prime_power", "q": q,
                                  "fr": f"Il n'existe pas de corps fini à {q} éléments : {q} = {fs} n'est pas une "
                                        f"puissance d'un nombre premier (un corps fini a p^k éléments, p premier).",
                                  "en": f"There is no finite field with {q} elements: {q} = {fs} is not a power of a "
                                        f"prime (a finite field has p^k elements, p prime)."})
            return
        add("gf", {"p": pp[0], "k": pp[1]}, a, b)

    for i, rx in enumerate(_GF_PATTERNS):
        for m in rx.finditer(t):
            if not _span_free(spans, m.start(), m.end()):
                continue
            base, exp = int(m.group(1)), (int(m.group(2)) if m.lastindex and m.lastindex >= 2 and m.group(2) else 1)
            if i == 3 and (m.group(0) in known or prime_power(base) is None):
                continue                            # « F12 » is a name, not a field
            q = base ** exp
            if exp > 1 and not is_prime(base):
                if prime_power(q) is None:
                    gf(q, m.start(), m.end(), True, m.group(0))
                    continue
            gf(q, m.start(), m.end(), True, m.group(0))
    for m in _GF_WORDS.finditer(fold(t)):
        q = int(m.group(1)) ** (int(m.group(2)) if m.group(2) else 1)
        gf(q, m.start(), m.end(), True, m.group(0))
    for rx in _ZMOD_PATTERNS:
        for m in rx.finditer(t):
            if _span_free(spans, m.start(), m.end()) and int(m.group(1)) >= 2:
                units = bool(re.match(r"\s*\)?\s*\^\s*(\*|×|x\b|\(\*\))", t[m.end():m.end() + 6]))
                add("zmod", {"n": int(m.group(1))} | ({"units": True} if units else {}), m.start(), m.end())
    for m in _ZMOD_WORDS.finditer(fold(t)):
        add("zmod", {"n": int(m.group(1))}, m.start(), m.end())
    for rx, how in _NUMFIELD:
        for m in rx.finditer(t):
            if how == "quad":
                d = squarefree(int(m.group(1)))          # Q(√8) = Q(√2): one field, one construction
                if d == 1:
                    add("base", {"ring": "QQ"}, m.start(), m.end())
                    continue
                add("numfield", {"quad": d, "gen": "i" if d == -1 else "a"}, m.start(), m.end())
            elif how == "gauss":
                add("numfield", {"quad": -1, "gen": "i"}, m.start(), m.end())
            elif how == "cyclo":
                add("numfield", {"cyclo": int(m.group(1)), "gen": "z"}, m.start(), m.end())
            else:
                num = int(m.group(1) or m.group(2))
                deg = 3 if m.group(1) else int(m.group(3))
                add("numfield", {"poly": f"x^{deg} - {num}", "gen": "a"}, m.start(), m.end())
    m = _NF_WORDS.search(fold(t))
    if m:
        rest = t[m.end():]
        mm = re.match(r"\s*([-+*/^()\w\s]+?)(?=$|[,;.]|\s(?:et|and|puis|then|calcule|compute)\b)", rest)
        if mm:
            try:
                e = normalize_expr(mm.group(1), known)
                if expr_names(e) == ["x"]:
                    add("numfield", {"poly": e, "gen": "a"}, m.start(), m.end() + mm.end())
            except ExprError:
                pass
    for m in _MATSPACE.finditer(t):
        inner = m.group(3).strip()
        sub = Intent()
        _find_objects(inner, known, sub, [])
        ring = sub.objects[0] if sub.objects else (Obj("base", {"ring": BASES[inner]}) if inner in BASES else None)
        if ring is not None:
            add("matspace", {"group": m.group(1), "n": int(m.group(2)), "ring": ring.key()}, m.start(), m.end())
            found[-1].ring = ring
    for m in _PMATRIX.finditer(t):
        rows = [r.strip() for r in re.split(r"\\\\", m.group(1)) if r.strip()]
        lit = "[" + ", ".join("[" + ", ".join(c.strip() for c in r.split("&")) + "]" for r in rows) + "]"
        _matrix(lit, m.start(), m.end(), add)
    for m in _MATRIX_LIT.finditer(t):
        _matrix(m.group(0), m.start(), m.end(), add)
    ft = fold(t)
    for rx, kind in _GROUP_WORDS:
        for m in rx.finditer(ft):
            n = int(m.group(1) or m.group(2))
            add("group", {"family": kind, "n": n}, m.start(), m.end())
    group_ctx = bool(re.search(r"groupe|group|permutation|sous-groupe|subgroup|conjug|abelien|abelian|ordre|order|"
                               r"cayley|caractere|character", ft))
    for rx, kind in _GROUPS:
        for m in rx.finditer(t):
            n = int(m.group(1))
            if kind == "cyc" and not group_ctx:
                continue
            if kind == "sym" and n > 12 or n < 1:
                continue
            if kind in ("sym", "alt", "dih") and m.group(0).strip()[:1] in "SAD" and "_" not in m.group(0) \
                    and not group_ctx:
                continue                             # « S5 » outside any group context: a name
            add("group", {"family": kind, "n": n}, m.start(), m.end())
    # polynomial rings K[x, y]: a ring object (or a base ring token) immediately followed by [vars]
    for o in list(found):
        if o.kind in ("gf", "zmod", "numfield"):
            mm = re.match(r"\s*\[\s*([A-Za-z](?:\s*,\s*[A-Za-z])*)\s*\]", t[o.span[1]:])
            if mm:
                a, b = o.span[0], o.span[1] + mm.end()
                spans.append((a, b))
                found.append(Obj("poly", {"ring": o.key(), "vars": _vars_list(mm.group(1))}, (a, b)))
                found[-1].ring = o
    for m in re.finditer(r"(?<![\w\\])(QQ|ZZ|RR|CC|Q|Z|R|C)\s*(\[\s*[iI]\s*\])?\s*\[\s*([A-Za-z](?:\s*,\s*[A-Za-z])*)"
                         r"\s*\]", t):
        if not _span_free(spans, m.start(), m.end()):
            continue
        if not m.group(2) and m.group(3).strip() in ("i", "I"):
            continue                                    # Z[i]: the Gaussian integers, not a ring in « i »
        ring = Obj("base", {"ring": "ZZ[I]" if m.group(2) and BASES[m.group(1)] == "ZZ" else BASES[m.group(1)]})
        add("poly", {"ring": ring.key(), "vars": _vars_list(m.group(3))}, m.start(), m.end())
        found[-1].ring = ring
    for m in re.finditer(r"(?<![\w\\])(?:Z|ZZ)\s*\[\s*[iI]\s*\]", t):
        add("base", {"ring": "ZZ[I]"}, m.start(), m.end())
    # « dans Q », « sur R », « over C », « in Z »: base rings after a preposition
    for m in re.finditer(r"\b(?:dans|sur|over|in|de|en)\s+(?:le corps |the field |l'anneau )?(QQ|ZZ|RR|CC|Q|Z|R|C)"
                         r"(?![\w'(/_\[])", t):
        add("base", {"ring": BASES[m.group(1)]}, m.start(1), m.end(1))
    for m in re.finditer(r"\b(?:les |des |the )?(?:reels|reals|rationnels|rationals|complexes|complex numbers|entiers "
                         r"relatifs|integers)\b", ft):
        w = m.group(0).split()[-1] if "entiers" not in m.group(0) else "entiers"
        ring = {"reels": "RR", "reals": "RR", "rationnels": "QQ", "rationals": "QQ", "complexes": "CC",
                "numbers": "CC", "entiers": "ZZ", "integers": "ZZ"}.get(w)
        if ring and re.search(r"\b(dans|sur|over|in)\s+(les |the )?$", ft[max(0, m.start() - 12):m.start()]):
            add("base", {"ring": ring}, m.start(), m.end())
    found.sort(key=lambda o: o.span)
    it.objects.extend(found)


def _matrix(lit: str, a: int, b: int, add) -> None:
    try:
        rows = json.loads(re.sub(r"(?<![\d.])(-?\d+)/(\d+)", r'"\1/\2"', lit))
    except ValueError:
        return
    if not rows or any(not isinstance(r, list) or len(r) != len(rows[0]) for r in rows):
        return
    norm = [[str(x) for x in r] for r in rows]
    add("matrix", {"rows": norm}, a, b)


# ================================================================ operations
# (op, regex on the folded text) — first match wins, so the more specific come first
OPS: list[tuple[str, str]] = [
    ("irreducibles", r"(?:liste|enumere|tous|toutes|list|all)\b.*irreductib|irreducible polynomials|polynomes "
                     r"irreductibles"),
    ("is_irreducible", r"irreductib|irreducib"),
    ("charpoly", r"polynome caracteristique|characteristic polynomial|charpoly"),
    ("minpoly", r"polynome minimal|minimal polynomial"),
    ("eigenvectors", r"vecteurs? propres?|eigenvectors?"),
    ("eigenvalues", r"valeurs? propres?|eigenvalues?|spectre|spectrum"),
    ("det", r"determinant|\bdet\b"),
    ("rank", r"\brang\b|\brank\b"),
    ("kernel", r"\bnoyau\b|\bkernel\b|null ?space"),
    ("trace_mat", r"\btrace de (?:la )?matrice|\btrace of\b"),
    ("jordan", r"jordan"),
    ("inverse_mod", r"inverse (?:de )?-?\d+ (?:modulo|mod)|inverse of -?\d+ mod"),
    ("inverse", r"\binverse\b|\binverser\b|\binvert\b"),
    ("series", r"taylor|developpement limite|\bdl\b|series expansion|serie entiere|power series expansion|"
               r"developpement en serie"),
    ("limit", r"\blimite?s?\b|tend vers|tends to"),
    ("integrate", r"integr|primitive|antideriv"),
    ("diff", r"deriv|differenti"),
    ("sum", r"\bsomme\b|\bsum\b|\bsommes\b"),
    ("plot", r"\btrace\b|\btracer\b|\btrace[rz]?\b|courbe|dessine|\bplot\b|\bdraw\b|graph of|graphe de la fonction|"
             r"represente|representation graphique"),
    ("gcd", r"\bpgcd\b|\bgcd\b|plus grand commun diviseur|greatest common divisor"),
    ("lcm", r"\bppcm\b|\blcm\b|plus petit commun multiple|least common multiple"),
    ("primes_first", r"\b\d+ premiers nombres premiers|first \d+ primes|\d+ premiers premiers"),
    ("primes_upto", r"nombres premiers (?:inferieurs|plus petits|jusqu|<|<=|entre)|primes (?:up to|below|less than|"
                    r"under)|premiers inferieurs"),
    ("next_prime", r"premier (?:nombre premier )?(?:apres|suivant|superieur)|next prime"),
    ("is_prime", r"est[- ]il premier|est premier|\bprimalite|is (?:it )?prime|primality|premier \?"),
    ("divisors", r"diviseurs|divisors"),
    ("totient", r"indicatrice|totient|\bphi\b|euler"),
    ("roots", r"racines?|\broots?\b|zeros? (?:de|du|of)"),
    ("solve", r"resou|resolution|\bsolve\b|equation"),
    ("factor", r"factori|\bfactor|decompos"),
    ("expand", r"\bdevelopp|\bexpand"),
    ("simplify", r"simplifi"),
    ("subgroups", r"sous-groupes?|subgroups?"),
    ("conj_classes", r"classes? de conjugaison|conjugacy class"),
    ("center", r"\bcentre\b|\bcenter\b"),
    ("is_abelian", r"abelien|abelian|commutatif"),
    ("char_table", r"table des caracteres|character table"),
    ("cayley", r"table de (?:cayley|multiplication)|cayley table|multiplication table"),
    ("generator", r"generateur|element primitif|primitive element|\bgenerator\b"),
    ("units", r"inversibles|groupe des unites|unit group|\bunits\b"),
    ("class_number", r"nombre de classes|class number"),
    ("discriminant", r"discriminant"),
    ("conductor", r"conducteur|conductor"),
    ("torsion", r"torsion"),
    ("j_invariant", r"j-invariant|invariant j|j invariant"),
    ("ell_rank", r"\brang\b|\brank\b"),
    ("points", r"\bpoints?\b"),
    ("galois", r"groupe de galois|galois group"),
    ("integers_ring", r"anneau des entiers|ring of integers"),
    ("degree", r"\bdegre\b|\bdegree\b"),
    ("elements", r"elements|liste (?:les )?elements|list (?:the )?elements|enumere"),
    ("order", r"\bordre\b|\border\b|cardinal|nombre d'elements|number of elements|combien d'elements|how many "
              r"elements"),
    ("construct", r"construi|construct|defini|define|\bcree\b|\bcreate\b|\bsoit\b|\blet\b"),
]
OP_SETS = {          # which ops make sense with which main object (others are ignored for that object)
    "matrix": {"det", "rank", "kernel", "inverse", "eigenvalues", "eigenvectors", "charpoly", "minpoly",
               "trace_mat", "jordan", "construct"},
    "group": {"order", "elements", "subgroups", "conj_classes", "center", "is_abelian", "char_table", "cayley",
              "construct"},
    "ell": {"ell_rank", "points", "order", "torsion", "j_invariant", "discriminant", "conductor", "plot",
            "construct"},
}
_ELL_WORDS = re.compile(r"courbe elliptique|elliptic curve|ellipti", re.I)


def _which_op(ft: str, allowed: set[str] | None = None) -> str:
    for op, rx in OPS:
        if allowed is not None and op not in allowed:
            continue
        if re.search(rx, ft):
            return op
    return ""


# words that carry no meaning for the code (kept out of the intent key)
_FILLER = set("""
le la les l de des du d un une et a au aux en dans sur pour avec par sans que qui quoi ce cet cette ces son sa ses
leur leurs puis aussi donc alors ici moi je tu il elle on nous vous ils me te se y ne pas plus tres bien peux peut
pouvez voudrais veux merci svp stp s'il plait calcule calculer calculez donne donner donnez montre montrer montrez
affiche afficher affichez trouve trouver trouvez determine determiner determinez fais faire faites ecris ecrire
ecrivez cherche chercher quel quelle quels quelles est sont etre the of and a an in on for with to by from is are be
est-il est-elle a-t-il over into via using utilise utiliser avec compute calculate give show find display determine write make please what which its it this that these those
explicitement explicit valeur value valeurs values resultat result exacte exact forme form fonction function
polynome polynomial polynomes polynomials expression corps field anneau ring element elements groupe group
matrice matrix courbe curve nombre number nombres numbers entier entiers integer suite comme as tout tous toute
toutes all every chaque each x y z t n k entre between allant going jusqu up quand when vers toward towards
""".split())


_OP_WORDS = {w for _op, rx in OPS for w in re.findall(r"[a-z]{3,}", rx)} | {
    "liste", "lister", "modulo", "mod", "premier", "premiers", "prime", "primes", "classes", "elliptique",
    "elliptic", "propre", "propres", "symetrique", "symmetric", "alterne", "alternating", "diedral", "dihedral",
    "cyclique", "cyclic", "fini", "finite", "quadratique", "quadratic", "cyclotomique", "cyclotomic", "nombres",
    "est-ce", "seconde", "second", "troisieme", "third", "limite", "point", "points", "reels", "reals",
    "rationnels", "complexes", "relatifs", "fonction", "infini", "infinity", "ordre", "droite", "gauche", "right",
    "left", "irreductibles", "inferieurs", "jusqu", "suivant", "apres", "voisinage", "autour", "near", "around"}


def _rest_words(ft: str) -> list[str]:
    out = []
    for w in re.findall(r"[a-z][a-z'-]{2,}", ft):
        w = w.split("'")[-1].strip("-")
        if len(w) < 3 or w in _FILLER or w in _OP_WORDS or w in FUNCS:
            continue
        if any(re.search(rx, w) for _op, rx in OPS):
            continue
        out.append(w)
    return out


# ================================================================ main
_WORD_MATH = re.compile(r"[\d^*/+=()<>!|\\]|^(?:sqrt|pi|oo|e)$")


def _expressions(t: str, known: set[str]) -> list[str]:
    """Formulas written in the request (objects already blanked out)."""
    words = re.split(r"(\s+)", t)
    groups: list[list[str]] = []
    cur: list[str] = []

    def mathy(w: str, nxt: str, prv: str) -> bool:
        w0 = w.strip(".,;:!?")
        if not w0:
            return False
        if w0 in ("-", "+", "*", "/", "^", "=", "==", "<", ">"):
            return True
        if re.fullmatch(r"[A-Za-z]", w0):
            if w0 in ("x", "t", "z") or w0 in known:
                return True
            return bool(_WORD_MATH.search(nxt or "") or _WORD_MATH.search(prv or "")) and w0 not in ("a", "y") \
                or (w0 == "y" and bool(re.search(r"[=^]", (nxt or "") + (prv or ""))))
        if re.fullmatch(r"[A-Za-z_]\w*", w0):
            return w0 in FUNCS or w0 in known and len(w0) > 1 and bool(re.match(r"[(\[]", nxt or ""))
        if re.search(r"[A-Za-zÀ-ÿ]{3,}", w0) and not re.search(r"(?:" + "|".join(sorted(FUNCS)) + r")\s*\(", w0) \
                and not re.fullmatch(r"[\w]*\(.*\)[\w^*/+\-()]*", w0):
            return False
        return bool(re.search(r"[\d^*/+=()|\\]", w0)) and not re.search(r"[à-ÿ]", w0)

    toks = [w for w in words if w.strip()]
    for i, w in enumerate(toks):
        nxt = toks[i + 1] if i + 1 < len(toks) else ""
        prv = toks[i - 1] if i else ""
        if mathy(w, nxt, prv) and "⟦" not in w:
            cur.append(w)
            if re.search(r"[,;:!?]$", w) and not re.search(r"\([^)]*$", " ".join(cur)):
                groups.append(cur)
                cur = []
        else:
            if cur:
                groups.append(cur)
            cur = []
    if cur:
        groups.append(cur)
    out = []
    for g in groups:
        s = " ".join(g).strip(" .,;:!?")
        if not s:
            continue
        try:
            e = normalize_expr(s, known)
        except ExprError:
            continue
        out.append(e)
    return out


_POINT = re.compile(r"(?:\ben\b|\bat\b|\bquand x tend vers\b|\bwhen x tends to\b|\bx\s*->\s*|\bx tend vers\b|"
                    r"\bas x\s*->\s*|\bau voisinage de\b|\bnear\b|\baround\b|\bautour de\b)\s*"
                    r"(\+\s*oo|-\s*oo|oo|l'infini|plus l'infini|moins l'infini|infinity|-?\d+(?:\.\d+)?|pi|-?pi/\d+)"
                    r"\s*(\+|-|\^\+|\^-|a droite|a gauche|from the right|from the left)?", re.I)


def analyze(text: str, known: set[str] | None = None) -> Intent:
    """Deterministic analysis of a Calcul request (never raises)."""
    known = set(known or ())
    it = Intent(text=(text or "").strip())
    try:
        _analyze(it, known)
    except Exception as e:  # noqa: BLE001 (an analysis bug must never break the request)
        it.rest.append(f"error:{type(e).__name__}")
    return it


def _analyze(it: Intent, known: set[str]) -> None:
    t = normalize_text(it.text)
    ft = fold(t)
    spans: list[tuple[int, int]] = []
    # elliptic curves first: their equation must not be read as a plain formula
    ell_words = bool(_ELL_WORDS.search(ft))
    _find_objects(t, known, it, spans)
    blank = list(t)
    for a, b in spans:
        for i in range(a, b):
            blank[i] = " "
        if b > a:
            blank[a] = "⟦"
    tb = "".join(blank)
    # sums: \sum_{k=1}^{n} f(k), « somme pour k de 1 à n de f(k) »
    msum = re.search(r"sum\s*_\s*[({]?\s*([a-z])\s*=\s*(-?\w+)\s*[)}]?\s*\^\s*[({]?\s*([\w+\-]+|oo)\s*[)}]?", tb)
    if msum:
        it.sumvar = msum.group(1)
        it.interval = (normalize_expr(msum.group(2)), normalize_expr(msum.group(3)))
        tb = tb[:msum.start()] + " sum " + tb[msum.end():]
    else:
        msum = re.search(r"\b(?:pour|for)\s+([a-z])\s*(?:=|allant de|de|from|in)\s*(-?\w+)\s*(?:a|à|to|\.\.)\s*"
                         r"(-?\w+|oo|l'infini|infinity)", fold(tb))
        if msum:
            hi = msum.group(3)
            hi = "oo" if hi in ("l'infini", "infinity", "oo") else hi
            try:
                it.interval = (normalize_expr(msum.group(2)), normalize_expr(hi))
                it.sumvar = msum.group(1)
                tb = tb[:msum.start()] + " " * (msum.end() - msum.start()) + tb[msum.end():]
            except ExprError:
                pass
    # intervals [a, b] / ]a, b[ / entre a et b
    for m in _INTERVAL.finditer(tb if it.interval is None else ""):
        lo, hi = (m.group(1), m.group(2)) if m.group(1) is not None else (m.group(3), m.group(4))
        try:
            it.interval = (normalize_expr(lo, known), normalize_expr(hi, known))
        except ExprError:
            continue
        tb = tb[:m.start()] + " " * (m.end() - m.start()) + tb[m.end():]
        break
    if it.interval is None:
        for m in _BETWEEN.finditer(tb):
            try:
                g = (m.group(1), m.group(2)) if m.group(1) is not None else (m.group(3), m.group(4))
                lo, hi = normalize_expr(g[0], known), normalize_expr(g[1], known)
            except ExprError:
                continue
            if re.search(r"[A-Za-z]{2,}", lo + hi) and not re.fullmatch(r"-?(pi|oo)|.*pi.*", lo + hi):
                continue
            it.interval = (lo, hi)
            tb = tb[:m.start()] + " " * (m.end() - m.start()) + tb[m.end():]
            break
    # limit / expansion point
    mp = _POINT.search(fold(tb))
    if mp:
        p = mp.group(1).replace(" ", "")
        p = {"l'infini": "oo", "plusl'infini": "oo", "infinity": "oo", "+oo": "oo", "moinsl'infini": "-oo"}.get(p, p)
        it.point = p
        sd = (mp.group(2) or "").strip()
        it.side = "+" if sd in ("+", "^+", "a droite", "from the right") else "-" if sd in (
            "-", "^-", "a gauche", "from the left") else ""
        tb = tb[:mp.start()] + " " * (mp.end() - mp.start()) + tb[mp.end():]
    # orders: « à l'ordre 5 », « dérivée seconde », « de degré 2 »
    mo = re.search(r"(?:a l'ordre|order|ordre|degre|degree|de degre)\s*(\d+)", fold(tb))
    if mo:
        it.order = int(mo.group(1))
        tb = tb[:mo.start()] + " " * (mo.end() - mo.start()) + tb[mo.end():]
    elif re.search(r"derivee seconde|second derivative", ft):
        it.order = 2
    elif re.search(r"derivee troisieme|third derivative", ft):
        it.order = 3
    exprs = _expressions(tb, known)
    # elliptic curve given by its Weierstrass equation (or a Cremona label)
    rest_extra: list[str] = []
    if ell_words:
        ring = it.field_obj()
        for e in exprs:
            if e.startswith("y^2") and "==" in e:
                coeffs = _weierstrass(e)
                if coeffs is not None:
                    o = Obj("ell", {"a": coeffs, "ring": ring.key() if ring else "QQ"}, ring=ring)
                    it.objects.append(o)
                    exprs = [x for x in exprs if x != e]
                    if ring is not None and ring.kind == "base" and ring.params["ring"] != "QQ":
                        rest_extra.append("ring:" + ring.params["ring"])
                    break
        else:
            lab = _ELL_LABEL.search(tb)
            if lab:
                it.objects.append(Obj("ell", {"label": lab.group(1)}))
                exprs = [x for x in exprs if x != lab.group(1)]
        if not it.obj("ell"):
            rest_extra.append("elliptic")
    # f(x) = …: a function definition, the formula is its right-hand side
    for i, e in enumerate(exprs):
        m = re.fullmatch(r"([fghFGH])\((\w)\) == (.+)", e)
        if m:
            exprs[i] = m.group(3)
            it.fname = m.group(1)
    ints = []
    for e in exprs:
        if re.fullmatch(r"-?\d+", e):
            ints.append(int(e))
        else:
            it.exprs.append(e)
    it.ints = ints
    # variable
    names: list[str] = []
    for e in it.exprs:
        for n in expr_names(e):
            if n not in names and n not in known:
                names.append(n)
    poly = it.obj("poly")
    if poly is not None:
        pv = poly.params["vars"]
        lower = [v.lower() for v in pv]
        # « F_125[X] » with a formula in x: the formula's case wins (one ring variable name per cell)
        if all(len(v) == 1 for v in pv) and len(set(lower)) == len(lower):
            poly.params["vars"] = lower                 # F_9[X] = F_9[x]: one spelling of the ring
        it.var = poly.params["vars"][0]
    elif it.sumvar:
        it.var = it.sumvar
    else:
        it.var = "x" if "x" in names or not names else ("t" if "t" in names else names[0])
    # operation
    main = it.objects[0].kind if it.objects else ""
    kinds = {o.kind for o in it.objects}
    allowed = None
    for k in ("ell", "matrix", "group"):
        if k in kinds:
            allowed = OP_SETS[k]
            break
    if "matspace" in kinds and not it.exprs:
        allowed = {"order", "construct", "elements"}
    # the words that NAME an object are not an operation (« courbe elliptique » is no « courbe » to plot)
    fo = re.sub(r"courbes? elliptiques?|elliptic curves?|groupe (?:symetrique|alterne|diedral|cyclique)|"
                r"(?:symmetric|alternating|dihedral|cyclic) group|corps (?:fini|de nombres|quadratique|cyclotomique)|"
                r"(?:finite|number|quadratic|cyclotomic) field", " ", ft)
    it.op = _which_op(fo, allowed)
    if not it.op and re.search(r"variations|etudie|etude de la fonction|study", fo):
        it.op = "study"
    if it.op == "trace_mat" and "matrix" not in kinds:
        it.op = "plot"
    if it.op in ("ell_rank",) and "ell" not in kinds:
        it.op = ""
    if it.op == "order" and main == "" and it.exprs:
        it.op = ""
    if it.op == "" and it.exprs and any("==" in e for e in it.exprs) and "ell" not in kinds:
        it.op = "solve"
    if it.op in ("primes_first", "primes_upto", "next_prime", "is_prime", "divisors", "totient", "factor", "gcd",
                 "lcm") and not it.exprs and not it.ints:
        m = re.search(r"\d+", tb)
        if m:
            it.ints = [int(m.group(0))]
    if it.op in ("primes_first",):
        m = re.search(r"(\d+) premiers|first (\d+)", ft)
        if m:
            it.ints = [int(m.group(1) or m.group(2))]
    if it.op == "inverse_mod":
        m = re.search(r"inverse (?:de |of )?(-?\d+) (?:modulo|mod) (\d+)", ft)
        if m:
            it.ints = [int(m.group(1)), int(m.group(2))]
            it.objects = [o for o in it.objects if o.kind != "zmod"]
    it.rest = sorted(set(_rest_words(fold(re.sub(r"⟦", " ", tb)))) | set(rest_extra))


def _weierstrass(eq: str) -> list[str] | None:
    """`y^2 + a1 xy + a3 y = x^3 + a2 x^2 + a4 x + a6` → [a1, a2, a3, a4, a6] (integers / rationals) or None."""
    try:
        lhs, rhs = eq.split("==", 1) if "==" in eq else eq.split("=", 1)
        lt, rt = _monomials(normalize_expr(lhs)), _monomials(normalize_expr(rhs))
    except (ExprError, ValueError):
        return None
    if lt is None or rt is None:
        return None
    if lt.pop((0, 2), None) != "1" or rt.pop((3, 0), None) != "1":
        return None
    a1, a3 = lt.pop((1, 1), "0"), lt.pop((0, 1), "0")
    a2, a4, a6 = rt.pop((2, 0), "0"), rt.pop((1, 0), "0"), rt.pop((0, 0), "0")
    if lt or rt:
        return None
    return [a1, a2, a3, a4, a6]


def _monomials(e: str) -> dict[tuple[int, int], str] | None:
    """A sum of monomials c*x^i*y^j with integer / rational c → {(i, j): c}."""
    out: dict[tuple[int, int], str] = {}
    s = e.replace(" ", "")
    if not s.startswith("-"):
        s = "+" + s
    for sign, body in re.findall(r"([+-])([^+-]+)", s):
        c, i, j = 1, 0, 0
        num = "1"
        for f in body.split("*"):
            m = re.fullmatch(r"(\d+)(?:/(\d+))?", f)
            if m:
                num = f
                continue
            m = re.fullmatch(r"([xy])(?:\^(\d+))?", f)
            if not m:
                return None
            k = int(m.group(2) or 1)
            if m.group(1) == "x":
                i += k
            else:
                j += k
        del c
        val = ("-" if sign == "-" else "") + num
        if (i, j) in out:
            return None
        out[(i, j)] = val
    return out


# ================================================================ « Reconnu : … »
_SUBS = str.maketrans("0123456789", "₀₁₂₃₄₅₆₇₈₉")
_SUPS = str.maketrans("0123456789", "⁰¹²³⁴⁵⁶⁷⁸⁹")
RING_FR = {"QQ": "ℚ", "ZZ": "ℤ", "RR": "ℝ", "CC": "ℂ", "ZZ[I]": "ℤ[i]"}


def obj_text(o: Obj, lang: str = "fr") -> str:
    fr = lang == "fr"
    p = o.params
    if o.kind == "gf":
        q = p["p"] ** p["k"]
        if p["k"] == 1:
            return (f"corps fini F{str(q).translate(_SUBS)}" if fr else f"finite field F{str(q).translate(_SUBS)}")
        return (f"corps fini F{str(q).translate(_SUBS)} = F_{{{p['p']}{str(p['k']).translate(_SUPS)}}}" if fr else
                f"finite field F{str(q).translate(_SUBS)} = F_{{{p['p']}{str(p['k']).translate(_SUPS)}}}")
    if o.kind == "zmod":
        base = f"ℤ/{p['n']}ℤ"
        return (f"groupe des inversibles de {base}" if fr else f"unit group of {base}") if p.get("units") else (
            f"anneau {base}" if fr else f"ring {base}")
    if o.kind == "base":
        return RING_FR.get(p["ring"], p["ring"])
    if o.kind == "poly":
        r = o.ring
        rt = _ring_short(r) if r is not None else "?"
        return (f"anneau de polynômes {rt}[{', '.join(p['vars'])}]" if fr else
                f"polynomial ring {rt}[{', '.join(p['vars'])}]")
    if o.kind == "numfield":
        if "quad" in p:
            d = p["quad"]
            return (f"corps ℚ(i)" if d == -1 else f"corps quadratique ℚ(√{d})") if fr else (
                "field ℚ(i)" if d == -1 else f"quadratic field ℚ(√{d})")
        if "cyclo" in p:
            return (f"corps cyclotomique ℚ(ζ{str(p['cyclo']).translate(_SUBS)})" if fr else
                    f"cyclotomic field ℚ(ζ{str(p['cyclo']).translate(_SUBS)})")
        return f"corps de nombres ℚ[x]/({p['poly']})" if fr else f"number field ℚ[x]/({p['poly']})"
    if o.kind == "matrix":
        n, m = len(p["rows"]), len(p["rows"][0])
        return f"matrice {n}×{m}" if fr else f"{n}×{m} matrix"
    if o.kind == "matspace":
        return f"{p['group']}{str(p['n']).translate(_SUBS)}({_ring_short(o.ring)})"
    if o.kind == "group":
        n = p["n"]
        fam = p["family"]
        if fam == "sym":
            return f"groupe symétrique S{str(n).translate(_SUBS)}" if fr else f"symmetric group S{str(n).translate(_SUBS)}"
        if fam == "alt":
            return f"groupe alterné A{str(n).translate(_SUBS)}" if fr else f"alternating group A{str(n).translate(_SUBS)}"
        if fam == "dih":
            return (f"groupe diédral D{str(n).translate(_SUBS)} ({2 * n} éléments)" if fr else
                    f"dihedral group D{str(n).translate(_SUBS)} ({2 * n} elements)")
        return f"groupe cyclique C{str(n).translate(_SUBS)}" if fr else f"cyclic group C{str(n).translate(_SUBS)}"
    if o.kind == "ell":
        if "label" in p:
            return f"courbe elliptique {p['label']}" if fr else f"elliptic curve {p['label']}"
        return (f"courbe elliptique [{', '.join(p['a'])}] sur {_ring_short(o.ring) if o.ring else 'ℚ'}"
                if fr else
                f"elliptic curve [{', '.join(p['a'])}] over {_ring_short(o.ring) if o.ring else 'ℚ'}")
    return o.kind


def _ring_short(o: Obj | None) -> str:
    if o is None:
        return "?"
    if o.kind == "gf":
        return "F" + str(o.params["p"] ** o.params["k"]).translate(_SUBS)
    if o.kind == "zmod":
        return f"ℤ/{o.params['n']}ℤ"
    if o.kind == "base":
        return RING_FR.get(o.params["ring"], o.params["ring"])
    if o.kind == "numfield":
        return obj_text(o).split(" ")[-1]
    return o.kind


OP_TEXT = {
    "fr": {"factor": "factorisation", "roots": "racines", "solve": "résolution", "integrate": "intégrale",
           "diff": "dérivée", "limit": "limite", "sum": "somme", "series": "développement de Taylor",
           "plot": "tracé", "simplify": "simplification", "expand": "développement", "gcd": "PGCD", "lcm": "PPCM",
           "det": "déterminant", "inverse": "inverse", "eigenvalues": "valeurs propres",
           "eigenvectors": "vecteurs propres", "rank": "rang", "kernel": "noyau", "charpoly":
               "polynôme caractéristique", "minpoly": "polynôme minimal", "trace_mat": "trace", "jordan":
               "forme de Jordan", "order": "ordre", "elements": "éléments", "irreducibles":
               "polynômes irréductibles", "is_irreducible": "irréductibilité", "primes_first": "nombres premiers",
           "primes_upto": "nombres premiers", "next_prime": "nombre premier suivant", "is_prime": "primalité",
           "divisors": "diviseurs", "totient": "indicatrice d'Euler", "inverse_mod": "inverse modulaire",
           "subgroups": "sous-groupes", "conj_classes": "classes de conjugaison", "center": "centre",
           "is_abelian": "commutativité", "char_table": "table des caractères", "cayley": "table de Cayley",
           "generator": "générateur", "units": "inversibles", "class_number": "nombre de classes",
           "discriminant": "discriminant", "conductor": "conducteur", "torsion": "torsion",
           "j_invariant": "invariant j", "ell_rank": "rang", "points": "points", "galois": "groupe de Galois",
           "integers_ring": "anneau des entiers", "degree": "degré", "construct": "construction",
           "study": "étude de la fonction"},
    "en": {"factor": "factorization", "roots": "roots", "solve": "solving", "integrate": "integral",
           "diff": "derivative", "limit": "limit", "sum": "sum", "series": "Taylor expansion", "plot": "plot",
           "simplify": "simplification", "expand": "expansion", "gcd": "gcd", "lcm": "lcm",
           "det": "determinant", "inverse": "inverse", "eigenvalues": "eigenvalues", "eigenvectors": "eigenvectors",
           "rank": "rank", "kernel": "kernel", "charpoly": "characteristic polynomial",
           "minpoly": "minimal polynomial", "trace_mat": "trace", "jordan": "Jordan form", "order": "order",
           "elements": "elements", "irreducibles": "irreducible polynomials", "is_irreducible": "irreducibility",
           "primes_first": "primes", "primes_upto": "primes", "next_prime": "next prime", "is_prime": "primality",
           "divisors": "divisors", "totient": "Euler's totient", "inverse_mod": "modular inverse",
           "subgroups": "subgroups", "conj_classes": "conjugacy classes", "center": "center",
           "is_abelian": "commutativity", "char_table": "character table", "cayley": "Cayley table",
           "generator": "generator", "units": "units", "class_number": "class number",
           "discriminant": "discriminant", "conductor": "conductor", "torsion": "torsion",
           "j_invariant": "j-invariant", "ell_rank": "rank", "points": "points", "galois": "Galois group",
           "integers_ring": "ring of integers", "degree": "degree", "construct": "construction",
           "study": "study of the function"},
}


def summary(it: Intent, lang: str = "fr") -> str:
    """What was recognized, in plain words (« corps fini F₁₂₅ = F_{5³} · factorisation de x^5 + 4*x - 1 »)."""
    lang = "fr" if lang == "fr" else "en"
    parts = []
    shown = set()
    for o in it.objects:
        if o.kind == "poly" and o.ring is not None and o.ring.kind != "gf":
            shown.add(id(o.ring))           # a finite field stays visible: « corps fini F₁₂₅ = F_{5³} »
    for o in it.objects:
        if id(o) in shown:
            continue
        parts.append(obj_text(o, lang))
    if it.op:
        w = OP_TEXT[lang].get(it.op, it.op)
        if it.exprs and it.op not in ("plot",):
            w += (" de " if lang == "fr" else " of ") + it.exprs[0]
        elif it.exprs:
            w += (" de " if lang == "fr" else " of ") + ", ".join(it.exprs[:3])
        if it.interval:
            w += f" sur [{it.interval[0]}, {it.interval[1]}]" if lang == "fr" else \
                f" on [{it.interval[0]}, {it.interval[1]}]"
        if it.point:
            w += (" en " if lang == "fr" else " at ") + it.point.replace("oo", "∞")
        parts.append(w)
    elif it.exprs:
        parts.append(", ".join(it.exprs[:3]))
    return " · ".join(parts)
