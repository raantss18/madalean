"""From a surviving pattern to a precise conjecture (S-AW, DECISIONS D55, docs/CONJECTURES.md §4): the statement in
words + LaTeX (French and English), a Lean 4 statement when every sequence involved has a Lean term (the catalogue's
verified constructions; otherwise the formalizer of the pipeline writes it, as for any conjecture), the evidence and
an honest strength label — « vérifié pour n = 0 … 59 », « heuristique », never « vrai ».

Deterministic: the same finding on the same sequence gives the same text, the same Lean statement and the same
normalised key (used to detect duplicates)."""
from __future__ import annotations

import hashlib
import json
import math
import re
from fractions import Fraction as Fr

from . import cjcatalog as C
from .cjpatterns import parse_value, primitive

LEAN_KINDS = ("polynomial", "constant", "rational", "recurrence", "holonomic", "multiplicative", "periodic",
              "congruence", "all_prime", "all_square", "increasing", "equal", "inequality", "linear")


# ---------------------------------------------------------------- LaTeX helpers
def _frac_tex(x: Fr) -> str:
    if x.denominator == 1:
        return str(x.numerator)
    return ("-" if x < 0 else "") + f"\\frac{{{abs(x.numerator)}}}{{{x.denominator}}}"


def poly_tex(coeffs: list[Fr], var: str = "n") -> str:
    """Expanded polynomial, highest degree first: `2 n^{3} - \\frac{1}{2} n + 1`."""
    parts = []
    for k in range(len(coeffs) - 1, -1, -1):
        c = coeffs[k]
        if c == 0:
            continue
        mono = "" if k == 0 else (var if k == 1 else f"{var}^{{{k}}}")
        mag = abs(c)
        body = _frac_tex(mag) if (mag != 1 or not mono) else ""
        term = (body + (" " if body and mono else "") + mono).strip()
        parts.append(("- " if c < 0 else "+ ") + term)
    if not parts:
        return "0"
    s = " ".join(parts)
    return s[2:] if s.startswith("+ ") else "-" + s[2:]


def factored_tex(f: dict, coeffs: list[Fr]) -> str:
    """`\\frac{n (n + 1) (2 n + 1)}{6}` when small integer roots were found, else the expanded form."""
    roots, rest = f.get("roots") or [], [parse_value(c) for c in f.get("rest") or ["1"]]
    content = parse_value(f.get("content", "1")) or Fr(1)
    if not roots:
        if content.denominator != 1 and len(rest) > 1:
            body = poly_tex(rest)                                   # type: ignore[arg-type]
            num = body if content.numerator == 1 else f"{content.numerator}\\left({body}\\right)"
            return f"\\frac{{{num}}}{{{content.denominator}}}"
        return poly_tex(coeffs)
    facs: list[str] = []
    for r in sorted(set(roots), key=lambda r: (abs(r), -r)):
        base = "n" if r == 0 else f"(n {'-' if r > 0 else '+'} {abs(r)})"
        k = roots.count(r)
        facs.append(base if k == 1 else f"{base}^{{{k}}}")
    if rest != [Fr(1)]:
        facs.append(f"({poly_tex(rest)})" if len(rest) > 1 else _frac_tex(rest[0]))    # type: ignore[arg-type]
    num = " ".join(facs)
    if abs(content.numerator) != 1:
        num = f"{abs(content.numerator)} {num}"
    sign = "-" if content < 0 else ""
    return f"{sign}\\frac{{{num}}}{{{content.denominator}}}" if content.denominator != 1 else sign + num


def _lin_tex(terms: list[tuple[Fr, str]], const: Fr = Fr(0)) -> str:
    """c₁·t₁ + c₂·t₂ + const with signs handled."""
    parts = []
    for c, t in terms:
        if c == 0:
            continue
        mag = abs(c)
        parts.append(("- " if c < 0 else "+ ") + (f"{_frac_tex(mag)}\\," if mag != 1 else "") + t)
    if const != 0 or not parts:
        parts.append(("- " if const < 0 else "+ ") + _frac_tex(abs(const)))
    s = " ".join(parts)
    return s[2:] if s.startswith("+ ") else "-" + s[2:]


# ---------------------------------------------------------------- Lean helpers
_RING = {"nat": "ℕ", "int": "ℤ", "rat": "ℚ"}
_ORDER = ("nat", "int", "rat")


def _up(*rings: str) -> str:
    return max(rings, key=_ORDER.index)


def _poly_lean(ints: list[int], ring: str, var: str = "n") -> str:
    """Integer polynomial as a Lean term of `ring` (ascending coefficients in, highest degree first out)."""
    v = var if ring == "nat" else f"({var} : {_RING[ring]})"
    parts = []
    for k in range(len(ints) - 1, -1, -1):
        c = ints[k]
        if c == 0:
            continue
        mono = "" if k == 0 else (v if k == 1 else f"{v} ^ {k}")
        mag = abs(c)
        term = mono if (mag == 1 and mono) else (f"{mag} * {mono}" if mono else str(mag))
        parts.append((" - " if c < 0 else " + ") + term)
    if not parts:
        return "0"
    s = "".join(parts)
    return s[3:] if s.startswith(" + ") else "-" + s[3:]


def _sides(terms: list[tuple[int, str]], const: int = 0) -> tuple[str, str]:
    """Σ cᵢ·tᵢ + const = 0 written with non-negative coefficients on both sides (stays in ℕ when it can)."""
    left = [(c, t) for c, t in terms if c > 0]
    right = [(-c, t) for c, t in terms if c < 0]
    if const > 0:
        left.append((const, ""))
    elif const < 0:
        right.append((-const, ""))

    def side(xs):
        if not xs:
            return "0"
        return " + ".join((t if c == 1 and t else (f"{c} * {t}" if t else str(c))) for c, t in xs)
    if not left:
        left, right = right, left
    return side(left), side(right)


class Ctx:
    """What a statement needs to know about the experiment: the sequences (catalogue definitions or anonymous
    data), the Lean flavour of the project's workspace and the language-independent names of the columns."""

    def __init__(self, intent: C.Intent | None, columns: list[str], flavor: str = "v4.9", origin: str = "catalogue",
                 terms: dict[str, list[str]] | None = None):
        self.intent, self.columns, self.flavor, self.origin = intent, columns, flavor, origin
        self.seqs = {s.name: s for s in (intent.seqs if intent and intent.kind == "sequence" else [])}
        self.family = intent.family if intent and intent.kind == "family" else ""
        self.terms = terms or {}

    def ring(self, col: str) -> str | None:
        s = self.seqs.get(col)
        return C.lean_ring(s.tree) if s else None

    def term(self, col: str, arg: str, ring: str) -> str:
        """The Lean term of column `col` at index `arg`, usable as an operand (parenthesised when composite)."""
        s = C.to_lean(self.seqs[col].tree, self.flavor, ring, {"n": arg})
        if re.fullmatch(r"[\w.]+", s):
            return s
        depth = 0
        for i, ch in enumerate(s):
            depth += ch == "("
            depth -= ch == ")"
            if depth == 0 and i < len(s) - 1:
                return f"({s})"
        return s

    def closed_form(self, col: str) -> bool:
        """The column is defined by an explicit formula in n (no named function, no sum): a polynomial fit or a
        recurrence only restates the definition."""
        s = self.seqs.get(col)
        return s is not None and all(x[0] in ("num", "var", "add", "sub", "mul", "div", "pow", "neg")
                                     for x in C.walk(s.tree))

    def definition(self, col: str, lang: str) -> str:
        s = self.seqs.get(col)
        if s is not None:
            tex = s.latex or C.to_latex(s.tree)
            words = s.fr if lang == "fr" else s.en
            extra = "" if words.startswith("$") else f" ({words})"
            return f"${col}(n) = {tex}${extra}"
        first = ", ".join((self.terms.get(col) or [])[:8])
        if self.origin == "data":
            return (f"${col}(n)$ la suite dont les premiers termes sont {first}, …" if lang == "fr" else
                    f"${col}(n)$ the sequence whose first terms are {first}, …")
        return (f"${col}(n)$ la suite calculée par l'expérience jointe (premiers termes : {first}, …)" if lang == "fr"
                else f"${col}(n)$ the sequence computed by the attached experiment (first terms: {first}, …)")

    def key(self, cols: list[str]) -> list[str]:
        out = []
        for c in cols:
            s = self.seqs.get(c)
            out.append(s.key if s else (f"family:{self.family}:{c}" if self.family else
                                        "terms:" + ",".join((self.terms.get(c) or [])[:24])))
        return out


def _graph(col: str) -> tuple[str, str, str]:
    for sym, fr, en, tex in C.GRAPH_COLUMNS:
        if sym == col:
            return fr, en, tex
    return col, col, col


RESTATES = ("polynomial", "constant", "rational", "recurrence", "holonomic", "algebraic_gf", "growth", "increasing",
            "periodic")


def mark_trivial(findings: list[dict], ctx: "Ctx") -> list[dict]:
    """A fit that only restates the formula the user typed is not a conjecture: journalled as `definition`."""
    for f in findings:
        cols = f.get("columns") or []
        if f.get("status") == "kept" and f["kind"] in RESTATES and cols and all(ctx.closed_form(c) for c in cols):
            f["status"], f["reason"] = "discarded", "definition"
    return findings


# ---------------------------------------------------------------- one finding → one candidate
def candidate(finding: dict, ctx: Ctx) -> dict | None:
    """The conjecture of a kept finding: {id, kind, text {fr, en}, lean, shift, strength, norm, …}; None when the
    finding is not a statement (discarded ones stay in the journal)."""
    if finding.get("status") != "kept":
        return None
    kind, p, cols = finding["kind"], finding.get("params") or {}, finding.get("columns") or []
    tested = finding.get("tested") or {}
    n0 = int(tested.get("from", 0))
    family = bool(ctx.family)
    a = cols[0] if cols else "a"
    b = cols[1] if len(cols) > 1 else ""
    fr = en = ""
    lean: str | None = None
    shift = 0
    forall = {"fr": f"pour tout entier $n \\ge {n0}$", "en": f"for every integer $n \\ge {n0}$"}
    hyp = f" (hn : {n0} ≤ n)" if n0 > 0 else ""
    ring_a = ctx.ring(a) if not family else None

    def stmt(binders: str, body: str) -> str:
        return f"theorem conjecture {binders} :\n    {body} := by sorry"

    if family:
        f = C.GRAPH_FAMILIES[ctx.family]
        obj = {"fr": f"Pour tout graphe $G$ parmi les {f['fr']}", "en": f"For every graph $G$ among the {f['en']}"}
        names = {c: _graph(c) for c in cols}

        def g(c: str) -> str:
            return f"{names[c][2]}(G)" if c not in ("n", "m") else c
        legend = {"fr": " (" + ", ".join(f"${g(c)}$ : {names[c][0]}" for c in cols) + ")",
                  "en": " (" + ", ".join(f"${g(c)}$: {names[c][1]}" for c in cols) + ")"}
        if kind == "equal":
            rel = f"{g(a)} = {g(b)}"
        elif kind == "inequality":
            d = int(p.get("offset", 0))
            rel = f"{g(a)} \\le {g(b)}" + (f" + {d}" if d else "")
        elif kind == "linear":
            terms = [(Fr(int(k)), g(c)) for c, k in p["coeffs"].items()]
            pos = [(c, t) for c, t in terms if c > 0]
            neg = [(-c, t) for c, t in terms if c < 0]
            const = Fr(int(p["constant"]))
            rel = f"{_lin_tex(pos)} = {_lin_tex(neg, -const)}" if neg else f"{_lin_tex(pos)} = {_frac_tex(-const)}"
        else:
            return None
        fr, en = f"{obj['fr']} : ${rel}${legend['fr']}.", f"{obj['en']}: ${rel}${legend['en']}."
    else:
        defs = {"fr": "Soit " + " et ".join(ctx.definition(c, "fr") for c in cols) + ". ",
                "en": "Let " + " and ".join(ctx.definition(c, "en") for c in cols) + ". "}
        A = f"{a}(n)"
        if kind in ("polynomial", "constant"):
            coeffs = [parse_value(c) or Fr(0) for c in p["coeffs"]]
            tex = factored_tex(p.get("factored") or {}, coeffs)
            fr, en = f"Alors {forall['fr']} : ${A} = {tex}$.", f"Then {forall['en']}: ${A} = {tex}$."
            if ring_a:
                den = 1
                for c in coeffs:
                    den = den * c.denominator // math.gcd(den, c.denominator)
                ints = [int(c * den) for c in coeffs]
                ring = ring_a if (den == 1 and all(c >= 0 for c in ints)) or ring_a == "rat" else _up(ring_a, "int")
                lhs = ctx.term(a, "n", ring)
                lean = stmt(f"(n : ℕ){hyp}", (f"{den} * {lhs}" if den != 1 else lhs) + " = " + _poly_lean(ints, ring))
        elif kind == "rational":
            num, den = [parse_value(c) or Fr(0) for c in p["num"]], [parse_value(c) or Fr(0) for c in p["den"]]
            tex = f"\\frac{{{poly_tex(num)}}}{{{poly_tex(den)}}}"
            fr, en = f"Alors {forall['fr']} : ${A} = {tex}$.", f"Then {forall['en']}: ${A} = {tex}$."
            if ring_a:
                ring = "rat" if ring_a == "rat" else "int"
                lean = stmt(f"(n : ℕ){hyp}", f"({_poly_lean([int(c) for c in den], ring)}) * {ctx.term(a, 'n', ring)} = "
                                             f"{_poly_lean([int(c) for c in num], ring)}")
        elif kind == "recurrence":
            cf = [parse_value(c) or Fr(0) for c in p["coeffs"]]
            order = len(cf)
            tex = _lin_tex([(c, f"{a}(n-{i + 1})") for i, c in enumerate(cf)])
            gf = p.get("gf") or {}
            gnum = poly_tex([parse_value(c) or Fr(0) for c in gf.get("num", ["0"])], "x")
            gden = poly_tex([parse_value(c) or Fr(0) for c in gf.get("den", ["1"])], "x")
            ser = f"\\sum_{{n \\ge {n0}}} {a}(n)\\,x^{{n{'-' + str(n0) if n0 else ''}}} = \\frac{{{gnum}}}{{{gden}}}"
            fr = (f"Alors pour tout entier $n \\ge {n0 + order}$ : ${A} = {tex}$ ; de façon équivalente, "
                  f"${ser}$.")
            en = (f"Then for every integer $n \\ge {n0 + order}$: ${A} = {tex}$; equivalently, ${ser}$.")
            shift = order
            if ring_a:
                vec = primitive([Fr(1)] + [-c for c in cf])
                ring = ring_a
                left, right = _sides([(k, ctx.term(a, f"n + {order - i}" if order - i else "n", ring))
                                      for i, k in enumerate(vec)])
                lean = stmt(f"(n : ℕ){hyp}", f"{left} = {right}")
        elif kind == "holonomic":
            polys = [[int(c) for c in q] for q in p["polys"]]
            r = len(polys) - 1
            pos, neg = [], []
            for i, q in enumerate(polys):
                if not any(q):
                    continue
                lead = next(c for c in reversed(q) if c)
                t = f"{a}(n+{i})" if i else A
                (pos if lead > 0 else neg).append((q if lead > 0 else [-c for c in q], t, i))

            def tex_side(xs):
                if not xs:
                    return "0"
                out = []
                for q, t, _i in xs:
                    pt = poly_tex([Fr(c) for c in q])
                    out.append(t if pt == "1" else (f"({pt})\\,{t}" if sum(1 for c in q if c) > 1 else f"{pt}\\,{t}"))
                return " + ".join(out)
            fr = f"Alors {forall['fr']} : ${tex_side(pos)} = {tex_side(neg)}$."
            en = f"Then {forall['en']}: ${tex_side(pos)} = {tex_side(neg)}$."
            shift = r
            if ring_a:
                ring = _up(ring_a, "int")

                def lean_side(xs):
                    if not xs:
                        return "0"
                    out = []
                    for q, _t, i in xs:
                        pl = _poly_lean(q, ring)
                        term = ctx.term(a, f"n + {i}" if i else "n", ring)
                        out.append(term if pl == "1" else f"({pl}) * {term}")
                    return " + ".join(out)
                lean = stmt(f"(n : ℕ){hyp}", f"{lean_side(pos)} = {lean_side(neg)}")
        elif kind == "algebraic_gf":
            grid = [[int(c) for c in row] for row in p["coeffs"]]
            terms = []
            for j, row in enumerate(grid):
                if not any(row):
                    continue
                pt = poly_tex([Fr(c) for c in row], "x")
                y = "" if j == 0 else ("A(x)" if j == 1 else f"A(x)^{{{j}}}")
                multi = sum(1 for c in row if c) > 1
                if not y:
                    terms.append(pt)
                elif pt == "1":
                    terms.append(y)
                elif pt == "-1":
                    terms.append(f"-{y}")
                else:
                    terms.append((f"({pt})" if multi else pt) + f"\\,{y}")
            eq = " + ".join(reversed(terms)).replace("+ -", "- ")
            ser = f"A(x) = \\sum_{{n \\ge {n0}}} {a}(n)\\,x^{{n{'-' + str(n0) if n0 else ''}}}"
            fr = f"Alors la série génératrice ${ser}$ vérifie ${eq} = 0$."
            en = f"Then the generating function ${ser}$ satisfies ${eq} = 0$."
        elif kind == "multiplicative":
            full = bool(p.get("complete"))
            fr = (f"Alors ${a}$ est {'complètement ' if full else ''}multiplicative : ${a}(mn) = {a}(m)\\,{a}(n)$ pour "
                  f"tous entiers $m, n \\ge 1$" + ("." if full else " premiers entre eux."))
            en = (f"Then ${a}$ is {'completely ' if full else ''}multiplicative: ${a}(mn) = {a}(m)\\,{a}(n)$ for all "
                  f"integers $m, n \\ge 1$" + ("." if full else " that are coprime."))
            if ring_a:
                cop = "" if full else " (h : Nat.Coprime m n)"
                lean = stmt(f"(m n : ℕ) (hm : 1 ≤ m) (hn : 1 ≤ n){cop}",
                            f"{ctx.term(a, 'm * n', ring_a)} = {ctx.term(a, 'm', ring_a)} * {ctx.term(a, 'n', ring_a)}")
        elif kind == "periodic":
            per = int(p["period"])
            fr = f"Alors ${a}$ est périodique de période {per} : {forall['fr']}, ${a}(n+{per}) = {A}$."
            en = f"Then ${a}$ is periodic with period {per}: {forall['en']}, ${a}(n+{per}) = {A}$."
            if ring_a:
                lean = stmt(f"(n : ℕ){hyp}", f"{ctx.term(a, f'n + {per}', ring_a)} = {ctx.term(a, 'n', ring_a)}")
        elif kind == "congruence":
            g, r = int(p["modulus"]), int(p["residue"])
            if r == 0:
                fr, en = f"Alors {forall['fr']}, ${g}$ divise ${A}$.", f"Then {forall['en']}, ${g}$ divides ${A}$."
            else:
                fr = f"Alors {forall['fr']} : ${A} \\equiv {r} \\pmod{{{g}}}$."
                en = f"Then {forall['en']}: ${A} \\equiv {r} \\pmod{{{g}}}$."
            if ring_a in ("nat", "int"):
                lean = stmt(f"(n : ℕ){hyp}", f"{ctx.term(a, 'n', ring_a)} % {g} = {r}")
        elif kind == "residue_periodic":
            m, per = int(p["modulus"]), int(p["period"])
            vals = ", ".join(str(v) for v in p["values"])
            fr = (f"Alors la suite ${A} \\bmod {m}$ est périodique de période {per} (valeurs {vals}) : {forall['fr']}, "
                  f"${a}(n+{per}) \\equiv {A} \\pmod{{{m}}}$.")
            en = (f"Then the sequence ${A} \\bmod {m}$ is periodic with period {per} (values {vals}): {forall['en']}, "
                  f"${a}(n+{per}) \\equiv {A} \\pmod{{{m}}}$.")
            if ring_a in ("nat", "int"):
                lean = stmt(f"(n : ℕ){hyp}", f"{ctx.term(a, f'n + {per}', ring_a)} % {m} = {ctx.term(a, 'n', ring_a)} % {m}")
        elif kind == "all_prime":
            fr, en = f"Alors {forall['fr']}, ${A}$ est un nombre premier.", f"Then {forall['en']}, ${A}$ is prime."
            if ring_a == "nat":
                lean = stmt(f"(n : ℕ){hyp}", f"Nat.Prime {ctx.term(a, 'n', 'nat')}")
        elif kind == "all_square":
            fr = f"Alors {forall['fr']}, ${A}$ est un carré parfait."
            en = f"Then {forall['en']}, ${A}$ is a perfect square."
            if ring_a in ("nat", "int"):
                lean = stmt(f"(n : ℕ){hyp}", f"IsSquare {ctx.term(a, 'n', ring_a)}")
        elif kind == "increasing":
            fr = f"Alors ${a}$ est strictement croissante : {forall['fr']}, ${A} < {a}(n+1)$."
            en = f"Then ${a}$ is strictly increasing: {forall['en']}, ${A} < {a}(n+1)$."
            if ring_a:
                lean = stmt(f"(n : ℕ){hyp}", f"{ctx.term(a, 'n', ring_a)} < {ctx.term(a, 'n + 1', ring_a)}")
        elif kind == "growth":
            rate = p.get("rate")
            law = f"{p.get('constant')} \\cdot {rate}^{{n}}" if p.get("model") == "exponential" else \
                f"{p.get('constant')} \\cdot n^{{{rate}}}"
            fr = (f"Heuristique (ajustement numérique, pas un énoncé exact) : ${A}$ croît comme ${law}$ "
                  f"(coefficient de détermination {p.get('r2')}).")
            en = (f"Heuristic (numerical fit, not an exact statement): ${A}$ grows like ${law}$ "
                  f"(coefficient of determination {p.get('r2')}).")
        elif kind in ("equal", "inequality") and b:
            d = int(p.get("offset", 0))
            rel = "=" if kind == "equal" else "\\le"
            tex = f"{A} {rel} {b}(n)" + (f" + {d}" if d else "")
            fr, en = f"Alors {forall['fr']} : ${tex}$.", f"Then {forall['en']}: ${tex}$."
            ring_b = ctx.ring(b)
            if ring_a and ring_b:
                ring = _up(ring_a, ring_b)
                lean = stmt(f"(n : ℕ){hyp}", f"{ctx.term(a, 'n', ring)} {'=' if kind == 'equal' else '≤'} "
                                             f"{ctx.term(b, 'n', ring)}" + (f" + {d}" if d else ""))
        elif kind == "linear":
            terms = [(Fr(int(k)), f"{c}(n)") for c, k in p["coeffs"].items()]
            const = Fr(int(p["constant"]))
            tex = _lin_tex(terms, const) + " = 0"
            fr, en = f"Alors {forall['fr']} : ${tex}$.", f"Then {forall['en']}: ${tex}$."
            rings = [ctx.ring(c) for c in p["coeffs"]]
            if all(rings):
                ring = _up(*rings)                                         # type: ignore[arg-type]
                left, right = _sides([(int(k), ctx.term(c, "n", ring)) for c, k in p["coeffs"].items()],
                                     int(p["constant"]))
                lean = stmt(f"(n : ℕ){hyp}", f"{left} = {right}")
        else:
            return None
        fr, en = defs["fr"] + fr, defs["en"] + en
    norm = hashlib.sha256(json.dumps([kind, ctx.key(cols), p if kind != "growth" else {}, n0], sort_keys=True,
                                     default=str).encode()).hexdigest()[:24]
    return {"id": "c-" + norm[:12], "kind": kind, "columns": cols, "finding": finding, "text": {"fr": fr, "en": en},
            "lean": lean, "lean_ok": None, "lean_error": "", "shift": shift, "norm": norm,
            "strength": strength(finding, family), "status": "candidate", "conjecture_id": "", "duplicate_of": None,
            "counterexample": None, "hunt": None}


def strength(finding: dict, family: bool = False, hunt: dict | None = None) -> dict:
    """The honest label of a candidate: what was tested, never more."""
    t = finding.get("tested") or {}
    lo, hi, cases, held = t.get("from", 0), t.get("to", 0), int(t.get("cases", 0)), int(t.get("held_out", 0))
    if hunt and hunt.get("cases"):
        cases += int(hunt["cases"])
        hi = max(hi, int(hunt.get("to", hi)))
    if finding.get("heuristic"):
        return {"kind": "heuristic", "from": lo, "to": hi, "cases": cases,
                "fr": f"heuristique : ajustement numérique sur n = {lo} … {hi}, pas une vérification",
                "en": f"heuristic: numerical fit on n = {lo} … {hi}, not a verification"}
    if family:
        return {"kind": "tested", "from": lo, "to": hi, "cases": cases,
                "fr": f"vérifié sur {cases} objets, pas démontré", "en": f"checked on {cases} objects, not proved"}
    fit = int(t.get("fit", 0))
    extra_fr = f", dont {held} gardés à part pour valider la formule" if fit and held else ""
    extra_en = f", {held} of them held out to validate the formula" if fit and held else ""
    top = int(hunt.get("max", hi)) if hunt and hunt.get("sparse") else hi
    return {"kind": "tested", "from": lo, "to": hi, "cases": cases,
            "fr": (f"vérifié jusqu'à n = {hi} ({cases} cas{extra_fr})" +
                   (f", et par sondage jusqu'à n = {top}" if top > hi else "") + ", pas démontré"),
            "en": (f"checked up to n = {hi} ({cases} cases{extra_en})" +
                   (f", and by sampling up to n = {top}" if top > hi else "") + ", not proved")}


def oeis_candidate(match: dict, ctx: Ctx, col: str, n0: int, terms: int) -> dict:
    """« a(n) is the OEIS sequence A…» as a candidate (words only: OEIS entries have no Lean definition)."""
    num, name, shift = match["number"], match.get("name", ""), int(match.get("shift", 0))
    idx = "n" if shift == 0 else (f"n + {shift}" if shift > 0 else f"n - {-shift}")
    k = int(match.get("matched", terms))
    fr = (f"Soit {ctx.definition(col, 'fr')}. Alors pour tout entier $n \\ge {n0}$, ${col}(n)$ est le terme d'indice "
          f"${idx}$ de la suite {num} de l'OEIS (« {name} »).")
    en = (f"Let {ctx.definition(col, 'en')}. Then for every integer $n \\ge {n0}$, ${col}(n)$ is the term of index "
          f"${idx}$ of the OEIS sequence {num} (“{name}”).")
    norm = hashlib.sha256(json.dumps(["oeis", ctx.key([col]), num, shift]).encode()).hexdigest()[:24]
    finding = {"kind": "oeis", "status": "kept", "columns": [col], "params": {"number": num, "name": name,
                                                                                "shift": shift, "url": match.get("url", "")},
               "tested": {"from": n0, "to": n0 + k - 1, "cases": k, "fit": 0, "held_out": k}, "reason": "",
               "detail": {}, "heuristic": False}
    return {"id": "c-" + norm[:12], "kind": "oeis", "columns": [col], "finding": finding, "text": {"fr": fr, "en": en},
            "lean": None, "lean_ok": None, "lean_error": "", "shift": 0, "norm": norm,
            "strength": {"kind": "oeis", "from": n0, "to": n0 + k - 1, "cases": k,
                         "fr": f"coïncide avec {num} sur {k} termes, pas démontré",
                         "en": f"agrees with {num} on {k} terms, not proved"},
            "status": "candidate", "conjecture_id": "", "duplicate_of": None, "counterexample": None, "hunt": None}


KIND_NAMES = {
    "polynomial": ("formule close", "closed formula"), "constant": ("suite constante", "constant sequence"),
    "rational": ("fraction rationnelle", "rational function"), "recurrence": ("récurrence linéaire",
                                                                              "linear recurrence"),
    "holonomic": ("récurrence à coefficients polynomiaux", "recurrence with polynomial coefficients"),
    "algebraic_gf": ("série génératrice algébrique", "algebraic generating function"),
    "multiplicative": ("multiplicativité", "multiplicativity"), "periodic": ("périodicité", "periodicity"),
    "congruence": ("congruence", "congruence"), "residue_periodic": ("résidus périodiques", "periodic residues"),
    "all_prime": ("toujours premier", "always prime"), "all_square": ("toujours un carré", "always a square"),
    "increasing": ("croissance stricte", "strictly increasing"), "growth": ("ordre de grandeur", "order of growth"),
    "equal": ("égalité", "equality"), "inequality": ("inégalité", "inequality"),
    "linear": ("relation linéaire", "linear relation"), "oeis": ("identification OEIS", "OEIS identification")}


def kind_name(kind: str, lang: str) -> str:
    fr, en = KIND_NAMES.get(kind, (kind, kind))
    return fr if lang == "fr" else en


def discarded_text(finding: dict, lang: str) -> str:
    """Why a pattern was dropped, in one sentence (journal)."""
    kind, reason, d = finding["kind"], finding.get("reason", ""), finding.get("detail") or {}
    t = finding.get("tested") or {}
    col = (finding.get("columns") or ["a"])[0]
    if reason == "held_out":
        where = f"n = {d.get('n')}" if "n" in d else f"ligne {d.get('row')}" if lang == "fr" else f"row {d.get('row')}"
        exp = d.get("expected")
        if lang == "fr":
            return (f"ajusté sur les {t.get('fit')} premiers termes, faux sur un terme gardé à part ({where}"
                    + (f" : la formule donne {exp}, la valeur est {d.get('got')}" if exp else "") + ")")
        return (f"fitted on the first {t.get('fit')} terms, wrong on a held-out term ({where}"
                + (f": the formula gives {exp}, the value is {d.get('got')}" if exp else "") + ")")
    if reason == "counterexample" and kind == "multiplicative":
        m, n = d.get("m"), d.get("n")
        return (f"{col}({m}·{n}) = {d.get('got')} ≠ {col}({m})·{col}({n}) = {d.get('expected')}")
    if reason == "definition":
        return "ne fait que redire la formule de départ" if lang == "fr" else "only restates the formula you gave"
    if reason == "redundant":
        return "conséquence d'un motif plus simple" if lang == "fr" else "follows from a simpler pattern"
    return reason


def lean_batch(cands: list[dict], header: str) -> tuple[str, list[tuple[str, int, int]]]:
    """All Lean statements of the candidates in ONE file (one compilation); spans = (candidate id, first line,
    last line), to map Lean's messages back."""
    lines = header.rstrip("\n").split("\n") + [""]
    spans = []
    for i, c in enumerate(cands):
        if not c.get("lean"):
            continue
        src = re.sub(r"\btheorem conjecture\b", f"theorem conjecture_{i}", c["lean"])
        start = len(lines) + 1
        lines += src.split("\n") + [""]
        spans.append((c["id"], start, len(lines) - 1))
    return "\n".join(lines) + "\n", spans


def norm_lean(statement: str) -> str:
    """A Lean statement without its header, name and spacing (duplicate detection)."""
    m = list(re.finditer(r"(?m)^\s*theorem\s+\S+", statement or ""))
    if not m:
        return ""
    body = statement[m[-1].end():]
    body = re.split(r":=\s*by\s+sorry", body)[0]
    return re.sub(r"\s+", " ", body).strip()
