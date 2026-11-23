"""Branches of mathematics and the rules that tag a news item with them.

Evidence, strongest first: arXiv categories (`math.NT`), MSC 2020 codes (`11A41`, first two digits), MathOverflow
tags (`nt.number-theory` → `math.NT`), then keyword rules on the title and the abstract (English and French).
Category evidence is trusted as is; keywords need a word-boundary match and add at most MAX_KEYWORD branches, so a
single passing word does not scatter an item over every branch."""
from __future__ import annotations

import re
import unicodedata

# id, French name, English name
BRANCHES: list[tuple[str, str, str]] = [
    ("algebra", "Algèbre", "Algebra"),
    ("number-theory", "Théorie des nombres", "Number theory"),
    ("geometry", "Géométrie", "Geometry"),
    ("topology", "Topologie", "Topology"),
    ("analysis", "Analyse", "Analysis"),
    ("pde", "Équations aux dérivées partielles", "Partial differential equations"),
    ("probability", "Probabilités", "Probability"),
    ("statistics", "Statistique", "Statistics"),
    ("combinatorics", "Combinatoire", "Combinatorics"),
    ("logic", "Logique", "Logic"),
    ("category-theory", "Théorie des catégories", "Category theory"),
    ("numerical-analysis", "Analyse numérique", "Numerical analysis"),
    ("optimisation", "Optimisation", "Optimisation"),
    ("math-physics", "Physique mathématique", "Mathematical physics"),
    ("history-education", "Histoire et enseignement", "History and education"),
]
IDS = [b[0] for b in BRANCHES]

ARXIV: dict[str, str] = {
    "math.AC": "algebra", "math.GR": "algebra", "math.RA": "algebra", "math.RT": "algebra", "math.QA": "algebra",
    "math.KT": "algebra",
    "math.NT": "number-theory",
    "math.AG": "geometry", "math.DG": "geometry", "math.MG": "geometry", "math.SG": "geometry",
    "math.AT": "topology", "math.GT": "topology", "math.GN": "topology",
    "math.CA": "analysis", "math.CV": "analysis", "math.FA": "analysis", "math.OA": "analysis",
    "math.SP": "analysis", "math.DS": "analysis",
    "math.AP": "pde",
    "math.PR": "probability",
    "math.ST": "statistics", "stat.TH": "statistics", "stat.ME": "statistics", "stat.ML": "statistics",
    "stat.AP": "statistics", "stat.CO": "statistics", "stat.OT": "statistics",
    "math.CO": "combinatorics", "cs.DM": "combinatorics",
    "math.LO": "logic", "cs.LO": "logic",
    "math.CT": "category-theory",
    "math.NA": "numerical-analysis", "cs.NA": "numerical-analysis",
    "math.OC": "optimisation",
    "math-ph": "math-physics", "math.MP": "math-physics",
    "math.HO": "history-education",
}

# MSC 2020, two-digit classes
_MSC_RANGES: list[tuple[range, str]] = [
    (range(0, 2), "history-education"), (range(3, 4), "logic"), (range(5, 6), "combinatorics"),
    (range(6, 9), "algebra"), (range(11, 12), "number-theory"), (range(12, 14), "algebra"),
    (range(14, 15), "geometry"), (range(15, 18), "algebra"), (range(18, 19), "category-theory"),
    (range(19, 23), "algebra"), (range(26, 35), "analysis"), (range(35, 36), "pde"), (range(37, 48), "analysis"),
    (range(49, 50), "optimisation"), (range(51, 54), "geometry"), (range(54, 56), "topology"),
    (range(57, 59), "topology"), (range(60, 61), "probability"), (range(62, 63), "statistics"),
    (range(65, 66), "numerical-analysis"), (range(70, 87), "math-physics"), (range(90, 91), "optimisation"),
    (range(93, 94), "optimisation"), (range(97, 98), "history-education"),
]
_MSC = re.compile(r"\b(\d{2})(?:-(?:XX|\d{2})|[A-Z](?:\d{2}|xx))\b")
_MO_TAG = re.compile(r"^([a-z]{2})\.[a-z-]+$")

# keyword rules: lower-case, accents removed, matched on word boundaries (a trailing * allows any ending)
KEYWORDS: dict[str, list[str]] = {
    "algebra": ["group theory", "finite group*", "abelian group*", "ring", "rings", "module*", "lie algebra*",
                "representation theory", "galois", "commutative algebra", "homological", "algebre", "groupe*",
                "anneau*", "polynomial identit*", "linear algebra", "matrix", "matrices"],
    "number-theory": ["number theory", "prime", "primes", "prime number*", "diophantine", "modular form*",
                      "elliptic curve*", "zeta function*", "riemann hypothesis", "l-function*", "arithmetic",
                      "additive combinatorics", "sieve", "theorie des nombres", "nombres premiers", "congruence*",
                      "integer sequence*", "divisor*", "pythagorean", "primitive root*", "covering system*"],
    "geometry": ["algebraic geometry", "differential geometry", "manifold*", "riemannian", "curvature", "variety",
                 "varieties", "scheme", "schemes", "convex", "polytope*", "geometrie", "variete*", "courbure",
                 "moduli space*", "symplectic", "euclidean geometry", "triangle*", "discrete geometry"],
    "topology": ["topology", "topological", "homotopy", "homology", "cohomology", "knot*", "3-manifold*",
                 "topologie", "homotopie", "noeud*", "fundamental group"],
    "analysis": ["functional analysis", "harmonic analysis", "complex analysis", "real analysis", "banach",
                 "hilbert space*", "operator*", "fourier", "measure theory", "dynamical system*", "ergodic",
                 "inequalit*", "analyse", "espace* de banach", "integral*", "series", "asymptotic*"],
    "pde": ["partial differential equation*", "pde", "pdes", "navier-stokes", "schrodinger equation*",
            "wave equation*", "heat equation*", "elliptic equation*", "parabolic", "hyperbolic equation*",
            "equations aux derivees partielles", "well-posedness", "weak solution*"],
    "probability": ["probability", "random walk*", "martingale*", "stochastic", "brownian", "percolation",
                    "random matri*", "markov", "probabilite*", "aleatoire*", "large deviation*"],
    "statistics": ["statistic*", "estimator*", "regression", "bayesian", "hypothesis test*", "inference",
                   "statistique*", "estimateur*", "sample complexity"],
    "combinatorics": ["combinatoric*", "graph theory", "graph", "graphs", "hypergraph*", "ramsey", "extremal",
                      "permutation*", "partition*", "enumerat*", "matroid*", "combinatoire", "graphe*", "coloring*",
                      "colouring*", "chromatic", "sidon", "arithmetic progression*", "latin square*"],
    "logic": ["logic", "set theory", "model theory", "proof theory", "computability", "forcing", "type theory",
              "proof assistant*", "theorem prov*", "formal proof*", "formaliz*", "formalis*", "lean 4", "lean4",
              "mathlib", "coq", "isabelle", "logique", "theorie des ensembles", "autoformaliz*", "decidab*"],
    "category-theory": ["category theory", "categories", "functor*", "topos", "toposes", "infinity-categor*",
                        "monoidal", "operad*", "theorie des categories", "foncteur*", "adjunction*"],
    "numerical-analysis": ["numerical analysis", "numerical method*", "finite element*", "discretization",
                           "discretisation", "numerical scheme*", "convergence rate*", "analyse numerique",
                           "elements finis", "preconditioner*", "quadrature"],
    "optimisation": ["optimization", "optimisation", "optimal control", "convex optimization", "gradient descent",
                     "linear programming", "semidefinite", "variational", "controle optimal", "minimization",
                     "minimisation", "sum of squares"],
    "math-physics": ["mathematical physics", "quantum", "statistical mechanics", "gauge theor*", "field theor*",
                     "string theory", "integrable system*", "physique mathematique", "quantique", "relativity"],
    "history-education": ["history of mathematics", "mathematics education", "teaching", "biography", "obituary",
                          "histoire des mathematiques", "enseignement", "pedagog*", "didactique", "prize", "medal",
                          "prix", "medaille", "laureat*"],
}
MAX_KEYWORD = 2


def fold(text: str) -> str:
    """Lower case without accents (« Théorème » → « theoreme »)."""
    return "".join(c for c in unicodedata.normalize("NFKD", text or "") if not unicodedata.combining(c)).lower()


def _compile(words: list[str]) -> re.Pattern:
    parts = []
    for w in sorted(words, key=len, reverse=True):
        stem = re.escape(w.rstrip("*")).replace(r"\ ", r"\s+")
        parts.append(stem + (r"\w*" if w.endswith("*") else ""))
    return re.compile(r"(?<![\w-])(?:" + "|".join(parts) + r")(?![\w-])")


_RULES = {b: _compile(ws) for b, ws in KEYWORDS.items()}


def msc_branch(code: str) -> str | None:
    try:
        n = int(code[:2])
    except ValueError:
        return None
    return next((b for r, b in _MSC_RANGES if n in r), None)


def category_of(tag: str) -> str | None:
    """arXiv category, or a MathOverflow tag written like one (`nt.number-theory` → `math.NT`)."""
    if tag in ARXIV:
        return tag
    m = _MO_TAG.match(tag)
    if m:
        c = "math." + m.group(1).upper()
        return c if c in ARXIV else None
    return None


def tag(title: str, summary: str = "", cats: list[str] | None = None) -> list[str]:
    """Branches of an item, in the order of BRANCHES."""
    found: set[str] = set()
    for c in cats or []:
        k = category_of(str(c))
        if k:
            found.add(ARXIV[k])
        elif (m := _MSC.fullmatch(str(c).strip())) is not None and (b := msc_branch(m.group(1))):
            found.add(b)
    text = fold(f"{title}\n{summary}")
    for m in _MSC.finditer(f"{title}\n{summary}"):
        if "msc" in text and (b := msc_branch(m.group(1))):
            found.add(b)
    hits = []
    for b, rx in _RULES.items():
        n = len(rx.findall(text))
        in_title = bool(rx.search(fold(title)))
        if n:
            hits.append((n + (2 if in_title else 0), b))
    hits.sort(reverse=True)
    # a keyword branch needs two hits, or one in the title; three points when categories already place the item
    need = 2 if not found else 3
    for score, b in hits[:MAX_KEYWORD]:
        if score >= need:
            found.add(b)
    return [b for b in IDS if b in found]


def arxiv_categories(branches: list[str]) -> list[str]:
    """arXiv math categories of the given branches (for the documentation and the settings screen)."""
    return sorted(c for c, b in ARXIV.items() if b in branches)
