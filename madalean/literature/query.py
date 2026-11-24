"""Search queries from a statement — deterministic first (Lean constants, LaTeX commands, a bilingual glossary,
an MSC guess); a fast free model may add search terms (never references), filtered to plain words."""
from __future__ import annotations

import json
import re
import unicodedata

from .types import QueryPlan

# Lean / Mathlib constant (last component, lower-cased) → English search terms
LEAN_TERMS = {
    "prime": "prime", "primes": "prime", "coprime": "coprime", "gcd": "greatest common divisor", "lcm": "lcm",
    "factorial": "factorial", "choose": "binomial coefficient", "totient": "Euler totient", "divisors": "divisors",
    "fib": "Fibonacci", "sqrt": "square root", "irrational": "irrational", "transcendental": "transcendental",
    "deriv": "derivative", "derivwithin": "derivative", "integral": "integral", "intervalintegral": "integral",
    "continuous": "continuous", "continuouson": "continuous", "differentiable": "differentiable",
    "tendsto": "limit", "cauchyseq": "Cauchy sequence", "summable": "series", "tsum": "series", "hassum": "series",
    "iscompact": "compact", "isopen": "open set", "isclosed": "closed set", "connectedspace": "connected",
    "polynomial": "polynomial", "roots": "roots", "degree": "degree", "natdegree": "degree", "eval": "polynomial",
    "aeval": "polynomial", "charpoly": "characteristic polynomial", "det": "determinant", "matrix": "matrix",
    "rank": "rank", "finrank": "dimension", "linearmap": "linear map", "eigenvalue": "eigenvalue",
    "haseigenvalue": "eigenvalue", "inner": "inner product", "norm": "norm", "dist": "metric",
    "subgroup": "subgroup", "normal": "normal subgroup", "orderof": "order of an element", "card": "cardinality",
    "zmod": "modular arithmetic", "modeq": "congruence", "legendresym": "Legendre symbol",
    "jacobisym": "Jacobi symbol", "padicvalnat": "p-adic valuation", "padicvalint": "p-adic valuation",
    "ideal": "ideal", "isprincipal": "principal ideal", "field": "field", "galois": "Galois",
    "measure": "measure", "volume": "Lebesgue measure", "ae": "almost everywhere", "probability": "probability",
    "simplegraph": "graph", "chromaticnumber": "chromatic number", "cliquefree": "clique", "hamiltonian": "Hamiltonian",
    "finset": "finite set", "sum": "sum", "prod": "product", "exp": "exponential", "log": "logarithm",
    "sin": "sine", "cos": "cosine", "pi": "pi", "complex": "complex numbers", "abs": "absolute value",
    "even": "even", "odd": "odd", "squarefree": "squarefree", "perfect": "perfect number", "convex": "convex",
    "convexon": "convex function", "inequality": "inequality", "am_gm": "AM-GM inequality",
}
LATEX_TERMS = {
    "sqrt": "square root", "sum": "sum", "prod": "product", "int": "integral", "lim": "limit", "binom": "binomial",
    "log": "logarithm", "ln": "logarithm", "exp": "exponential", "sin": "sine", "cos": "cosine", "tan": "tangent",
    "gcd": "greatest common divisor", "det": "determinant", "infty": "infinity", "pi": "pi", "zeta": "zeta",
    "phi": "", "mathbb": "", "frac": "", "le": "", "ge": "", "leq": "", "geq": "", "cdot": "", "left": "",
    "right": "", "mid": "divides", "equiv": "congruence", "pmod": "congruence", "bmod": "congruence",
}
# French (and a few English variants) → English search terms
GLOSSARY = {
    "premier": "prime", "premiers": "prime", "entier": "integer", "entiers": "integer", "naturel": "natural number",
    "irrationnel": "irrational", "irrationnelle": "irrational", "rationnel": "rational", "réel": "real",
    "reel": "real", "suite": "sequence", "suites": "sequence", "série": "series", "serie": "series",
    "convergente": "convergent", "converge": "convergent", "limite": "limit", "dérivée": "derivative",
    "derivee": "derivative", "intégrale": "integral", "integrale": "integral", "continue": "continuous",
    "polynôme": "polynomial", "polynome": "polynomial", "racine": "root", "racines": "roots",
    "nombre chromatique": "chromatic number", "coloration": "coloring", "plan euclidien": "Euclidean plane",
    "matrice": "matrix", "déterminant": "determinant", "valeur propre": "eigenvalue", "groupe": "group",
    "sous-groupe": "subgroup", "anneau": "ring", "corps": "field", "idéal": "ideal", "graphe": "graph",
    "sommet": "vertex", "sommets": "vertices", "arête": "edge", "arêtes": "edges", "inégalité": "inequality",
    "inegalite": "inequality", "triangle": "triangle", "cercle": "circle", "carré": "square", "carre": "square",
    "cube": "cube", "parfait": "perfect", "pair": "even", "impair": "odd", "diviseur": "divisor",
    "diviseurs": "divisors", "divisible": "divisible", "congruence": "congruence", "modulo": "congruence",
    "somme": "sum", "produit": "product", "fonction": "function", "compact": "compact", "ouvert": "open set",
    "fermé": "closed set", "mesure": "measure", "probabilité": "probability", "binomial": "binomial coefficient",
    "factorielle": "factorial", "fibonacci": "Fibonacci", "infinité": "infinitely many", "infinite": "infinitely many",
    "infinitely": "infinitely many", "bertrand": "Bertrand postulate", "fermat": "Fermat", "euler": "Euler",
    "wilson": "Wilson theorem", "gauss": "Gauss", "cauchy": "Cauchy", "schwarz": "Schwarz", "riemann": "Riemann",
    "dirichlet": "Dirichlet", "chebyshev": "Chebyshev", "tchebychev": "Chebyshev", "hilbert": "Hilbert",
    "sylow": "Sylow", "lagrange": "Lagrange", "erdős": "Erdős", "erdos": "Erdős", "ramsey": "Ramsey",
}
ENGLISH_KEEP = {
    "prime", "primes", "integer", "integers", "irrational", "rational", "polynomial", "sequence", "series",
    "convergent", "derivative", "integral", "continuous", "matrix", "determinant", "eigenvalue", "group",
    "subgroup", "ring", "field", "ideal", "graph", "vertex", "edge", "inequality", "triangle", "circle", "square",
    "divisor", "divisible", "congruence", "sum", "product", "compact", "measure", "probability", "factorial",
    "binomial", "perfect", "even", "odd", "bound", "theorem", "conjecture", "lemma", "zeta", "modular", "cyclic",
    "abelian", "finite", "infinite", "dimension", "linear", "convex", "metric", "norm", "number", "numbers",
    "partition", "permutation", "coloring", "colouring", "chromatic", "hamiltonian", "planar", "tree", "trees",
}
# keyword → MSC 2020 top-level class (a guess, used to filter and to explain, never to reject)
MSC_OF = {
    "prime": "11", "integer": "11", "divisor": "11", "divisors": "11", "congruence": "11", "irrational": "11",
    "greatest common divisor": "11", "Euler totient": "11", "Legendre symbol": "11", "p-adic valuation": "11",
    "modular arithmetic": "11", "Bertrand postulate": "11", "Fermat": "11", "perfect number": "11",
    "polynomial": "12", "roots": "12", "Galois": "12", "field": "12",
    "ideal": "13", "ring": "13",
    "matrix": "15", "determinant": "15", "eigenvalue": "15", "characteristic polynomial": "15", "linear map": "15",
    "group": "20", "subgroup": "20", "normal subgroup": "20", "order of an element": "20", "Sylow": "20",
    "derivative": "26", "continuous": "26", "integral": "26", "inequality": "26", "convex function": "26",
    "measure": "28", "Lebesgue measure": "28", "almost everywhere": "28",
    "series": "40", "sequence": "40", "limit": "40", "Cauchy sequence": "40",
    "compact": "54", "open set": "54", "closed set": "54", "connected": "54",
    "probability": "60",
    "graph": "05", "chromatic number": "05", "clique": "05", "Hamiltonian": "05", "binomial coefficient": "05",
    "partition": "05", "permutation": "05", "Ramsey": "05", "Erdős": "05",
    "triangle": "51", "circle": "51",
}
STOP = {"the", "that", "for", "all", "every", "and", "with", "then", "there", "exists", "show", "prove", "let",
        "such", "any", "one", "two", "has", "are", "its", "this", "from", "into", "than", "which", "where", "when",
        "montrer", "prouver", "démontrer", "que", "tout", "tous", "toute", "pour", "avec", "alors", "existe", "soit",
        "dans", "est", "sont", "une", "des", "les", "par", "sur", "qui", "nombre", "nombres"}
GENERIC = {"square root", "integer", "real", "natural number", "function", "number", "numbers", "sum", "product", "finite set",
           "absolute value", "rational", "sequence"}
MAX_KEYWORDS = 10
REFERENCE_LIKE = re.compile(r"10\.\d{4,}/|arxiv|https?:|www\.|\b(19|20)\d\d\b|\d{4}\.\d{4,5}|"
                            r"[\"“”«»@/\\<>{}\[\]]", re.I)
MAX_EXTRA = 6


def _fold(s: str) -> str:
    return unicodedata.normalize("NFKC", s or "")


def lean_names(statement: str) -> list[str]:
    """Mathlib constants of a Lean statement (`Nat.Prime`, `Real.sqrt`, `Finset.sum`, `deriv` …), first seen first."""
    body = re.sub(r"(?m)^\s*(import|open|set_option)\b.*$", "", statement or "")
    body = re.sub(r"--.*|/-.*?-/", "", body, flags=re.S)
    names = re.findall(r"(?<![\w.'])([A-Z][\w']*(?:\.[\w']+)+|[a-z][a-zA-Z]+(?:\.[\w']+)+|"
                       r"deriv|Irrational|Continuous|Differentiable|Tendsto|Summable|IsCompact|Polynomial|Matrix|"
                       r"Finset|ZMod|Real\.sqrt|Nat\.Prime|Prime|Even|Odd|Squarefree|Convex|ConvexOn|"
                       r"Complex|SimpleGraph|MeasureTheory)(?![\w'])", body)
    out: list[str] = []
    for n in names:
        if n not in out and not n.startswith(("by.", "fun.")):
            out.append(n)
    return out[:20]


def _terms_of_lean(names: list[str]) -> list[str]:
    out: list[str] = []
    for n in names:
        for part in reversed(n.split(".")):
            t = LEAN_TERMS.get(part.lower())
            if t:
                if t not in out:
                    out.append(t)
                break
    return out


def _terms_of_latex(text: str) -> list[str]:
    out: list[str] = []
    for cmd in re.findall(r"\\([A-Za-z]+)", text or ""):
        t = LATEX_TERMS.get(cmd)
        if t and t not in out:
            out.append(t)
    return out


def _terms_of_words(text: str) -> list[str]:
    plain = re.sub(r"\$[^$]*\$|\\\(.*?\\\)|\\\[.*?\\\]", " ", _fold(text), flags=re.S)
    plain = re.sub(r"\\[A-Za-z]+", " ", plain)
    low = plain.lower()
    out: list[str] = []
    for fr, en in GLOSSARY.items():
        if " " in fr and fr in low and en not in out:
            out.append(en)
    for w in re.findall(r"[^\W\d_][\w'-]*", low):
        w = w.strip("'-")
        if len(w) < 3 or w in STOP:
            continue
        en = GLOSSARY.get(w) or (w if w in ENGLISH_KEEP else "")
        if en and en not in out:
            out.append(en)
    return out


def msc_guess(keywords: list[str]) -> list[str]:
    counts: dict[str, int] = {}
    for k in keywords:
        c = MSC_OF.get(k) or MSC_OF.get(k.rstrip("s"))
        if c:
            counts[c] = counts.get(c, 0) + 1
    return [c for c, _n in sorted(counts.items(), key=lambda x: -x[1])][:2]


def clean_terms(x: list, k: int, words: int = 4) -> list[str]:
    """Search terms proposed by a model → plain words only (anything that looks like a reference is dropped)."""
    out: list[str] = []
    for s in x:
        if not isinstance(s, str):
            continue
        s = re.sub(r"\s+", " ", re.sub(r"[‐–—]", "-", _fold(s))).strip()
        if not s or len(s) > 60 or len(s.split()) > words or REFERENCE_LIKE.search(s) \
                or not re.fullmatch(r"[^\W_][\w' -]*", s) or s.lower() in (o.lower() for o in out):
            continue
        out.append(s)
        if len(out) >= k:
            break
    return out


def build(statement: str, text: str = "", names: list[str] | None = None) -> QueryPlan:
    """Deterministic query plan from the problem's own words / LaTeX and the classical `names` of the problem (D65);
    1–3 queries, most specific first. Lean constants are used only when there are no words at all (a statement given
    without any text), never beside the problem's words."""
    classical = clean_terms(list(names or []), 4, 6)
    lean = lean_names(statement)
    kw: list[str] = []
    has_words = bool((text or "").strip()) or bool(classical)
    for t in _terms_of_words(text) + _terms_of_latex(text) + ([] if has_words else _terms_of_lean(lean)):
        if t and t not in kw and not any(t != o and t in o.split() for o in kw):
            kw.append(t)
    kw = ([k for k in kw if k not in GENERIC] + [k for k in kw if k in GENERIC])[:MAX_KEYWORDS]
    specific = [k for k in kw if k not in GENERIC]
    queries: list[str] = list(classical[:2])
    named = [k for k in kw if k[:1].isupper()]            # named results (« Bertrand postulate », « Sylow ») first
    main = specific if len(specific) >= 2 else kw
    if main:
        queries.append(" ".join((named + [k for k in main if k not in named])[:5]))
    if named and len(kw) > 1:
        queries.append(" ".join(named[:2] + ["theorem"]))
    elif len(kw) > 2:
        queries.append(" ".join(kw[:3]))
    queries = list(dict.fromkeys(q.strip() for q in queries if q.strip()))[:3]
    return QueryPlan(keywords=classical + [k for k in kw if k not in classical], lean_names=lean, msc=msc_guess(kw),
                     queries=queries, names=classical)


def _plain(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s.lower()) if not unicodedata.combining(c))


def relevant(plan: QueryPlan, title: str, body: str, matched: list[str]) -> bool:
    """Deterministic relevance floor (D65): a work is kept when it holds a classical name of the problem, or one
    specific keyword made of several words, or two specific keywords. « square root », « number » are not specific."""
    flat = _plain(f"{title} {body}")
    for n in plan.names:
        ws = [w for w in re.findall(r"[a-z]{3,}", _plain(n))
              if w not in ("problem", "theorem", "conjecture", "the", "lemma")]
        if ws and all(w in flat for w in ws):
            return True
    good = [m for m in matched if m not in GENERIC and m not in plan.names]
    asked = [k for k in plan.keywords + plan.extra_keywords if k not in GENERIC and k not in plan.names]
    if not plan.names and len(asked) <= 1:
        return bool(good) or not asked
    return any(" " in m or m[:1].isupper() for m in good) or len(good) >= 2


KEYWORDS_PROMPT = (
    "You help search mathematical databases (zbMATH, arXiv). Give at most {n} extra English search keywords (standard "
    "terminology, names of classical theorems) for the statement below. Keywords only: no titles, no authors, no "
    "references, no sentences. Answer ONLY with a JSON list of strings.\n\nStatement (Lean 4):\n{lean}\n\n"
    "In words:\n{text}")


def parse_extra(answer: str, known: list[str]) -> list[str]:
    """Model answer → plain search words (≤ 4 words each, letters/digits/hyphens only; anything that looks like a
    reference — a DOI, an arXiv id, a year, a URL — is dropped)."""
    from ..research.litsearch import parse_json_block
    data = parse_json_block(answer or "")
    if not isinstance(data, list):
        return []
    out: list[str] = []
    low = {k.lower() for k in known}
    for x in data:
        if not isinstance(x, str):
            continue
        s = re.sub(r"\s+", " ", _fold(x)).strip()
        if not s or len(s) > 48 or len(s.split()) > 4:
            continue
        if REFERENCE_LIKE.search(s):
            continue
        if not re.fullmatch(r"[^\W_][\w' -]*", s):
            continue
        if s.lower() in low:
            continue
        low.add(s.lower())
        out.append(s)
        if len(out) >= MAX_EXTRA:
            break
    return out


def with_extra(plan: QueryPlan, extra: list[str]) -> QueryPlan:
    plan.extra_keywords = extra
    if extra:
        q = " ".join((extra[:2] + plan.keywords[:2]))
        if q and q not in plan.queries:
            plan.queries = (plan.queries + [q])[:4]
    return plan


def dumps(plan: QueryPlan) -> str:
    return json.dumps({"keywords": plan.keywords, "msc": plan.msc, "queries": plan.queries}, ensure_ascii=False)
