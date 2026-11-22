"""Tool rule cards and prompt compaction (session S-AI, DECISIONS D41).

« Chaque modèle responsable lit la règle de chaque outil utilisé » — one compact card per tool a model may write for:

- ``lean``     Lean 4 + Mathlib syntax, the entries of ``syntaxcards`` (S-AB) — the VERIFIED card of the workspace's
               toolchain + Mathlib when it is built, else the same entries marked « not checked here »;
- ``madalean`` Madalean's own conventions for Lean (fixed theorem name and header, forbidden constructs, faithful
               statements, Lean alone decides « vérifiée »);
- ``sage`` / ``python``  SageMath idioms (``syntaxcards.SAGE_ENTRIES`` or the verified Sage card) and plain Python;
- ``latex``    LaTeX / article conventions;
- ``explain``  how an explanation is written for the user (language, no jargon, the Lean proof is the reference).

Compaction: every rule is either *core* (always sent for the tool) or tagged with features (``sum``, ``induction``,
``real``…). A prompt is built from two parts:

1. the **stable block** — role text + the core rules of the role's tools, ordered and versioned, byte-identical for
   every request of that role on the same tool versions: it sits BEFORE the cache breakpoint (Anthropic
   ``cache_control``; identical prefixes for the implicit caches of other providers). Nothing volatile in it.
2. the **request block** — only the tagged rules whose features appear in the request (``features_of``), deduplicated
   across cards and cut to a token budget per role; after the breakpoint.

Token counts are estimates (≈ 3.5 characters per token, as ``spend.tokens_of``); no network."""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field

CARDS_VERSION = 1                 # bump when a rule text changes (the stable block's cache key changes with it)
CHARS_PER_TOKEN = 3.5


def estimate_tokens(text: str) -> int:
    return int(len(text or "") / CHARS_PER_TOKEN) + (1 if text else 0)


@dataclass(frozen=True)
class Rule:
    id: str
    text: str
    tags: frozenset = frozenset()
    core: bool = False


@dataclass
class Card:
    tool: str
    title: str                    # with the version it was checked against
    rules: list[Rule]
    verified: bool = False


# ---------------------------------------------------------------- features of a request
_FEATURES: list[tuple[str, re.Pattern]] = [(f, re.compile(p, re.I)) for f, p in [
    ("sum", r"[∑∏]|\bFinset\.(sum|prod)|\bsum_range|\bsomme|\bproduit des|\bsum\b|\bseries\b|s[ée]rie"),
    ("induction", r"r[ée]currence|induction|\bpour tout (entier )?n\b|∀\s*n\s*:\s*ℕ|\bNat\.rec"),
    ("real", r"ℝ|\bReal\b|\bRe?al\.|r[ée]el|\breal\b|√|\bsqrt|\bexp\b|\blog\b|\bsin\b|\bcos\b|\bπ|\bpi\b"),
    ("cast", r"ℕ.*ℝ|ℝ.*ℕ|ℤ.*ℝ|↑|\bcast\b|\bNat\.cast|soustraction|\b[a-z]\s*-\s*[a-z]\b.*ℕ"),
    ("arith", r"\bNat\.Prime|\bprime|premier|∣|\bdvd|divis|\bEven\b|\bOdd\b|\bpair\b|\bimpair|pgcd|\bgcd|modulo|%|≡"),
    ("set", r"\bSet\b|\bFinset\b|ensemble|∈|⊆|∪|∩|injecti|surjecti|bijecti|Function\."),
    ("ineq", r"[≤≥<>]|in[ée]galit|inequal|major|minor|\bmax\b|\bmin\b"),
    ("exists", r"∃|il existe|there exists|\bou\b|∨|\bet\b|∧|↔|[ée]quivalen"),
    ("contra", r"absurde|contradiction|¬|\bnot\b|\bne\b.*\bpas\b|irrationnel|irrational|infinit"),
    ("analysis", r"\bderiv|d[ée]riv|Tendsto|limite|\blimit|continu|int[ée]gr|∫|Cauchy|converg"),
    ("linalg", r"Matrix|matrice|LinearMap|lin[ée]aire|vectoriel|\bdet\b|d[ée]terminant|eigen|valeur propre|\brank\b"),
    ("calc", r"calc\b|cha[iî]ne d'[ée]galit|step by step|[ée]tapes? de calcul"),
    # Sage / Python / LaTeX features
    ("plot", r"trace|courbe|graphique|\bplot|dessin|draw|figure"),
    ("solve", r"r[ée]sou|\bsolve|racine|\broot|z[ée]ro"),
    ("symbolic", r"\bvar\(|symbol|formel|d[ée]velopp|simplifi|factori|expand"),
    ("graph", r"graphe|\bgraph\b|petersen|chromati|sommet|vertex"),
    ("assume", r"suppos|assum|param[èe]tre|entier n\b|integer"),
    ("numeric", r"num[ée]rique|numeric|approx|d[ée]cimal|float|\bN\("),
    ("table", r"tableau|\btable\b|tabular"),
    ("ref", r"r[ée]f[ée]rence|\\cite|\\ref|bibliograph|citation"),
]]


def features_of(*texts: str) -> frozenset:
    t = "\n".join(x for x in texts if x)
    return frozenset(f for f, rx in _FEATURES if rx.search(t))


# ---------------------------------------------------------------- cards
_LEAN_TAGS = {"lean4": None, "names": None, "auto": None, "bigop": {"sum"}, "bigop_in": {"sum"},
              "destruct": {"exists", "set"}, "induction": {"induction"}, "cast": {"cast", "real"},
              "calc": {"ineq", "calc", "real"}, "contra": {"contra"}, "preds": {"arith", "set"},
              "real": {"real", "analysis"}}

MADALEAN_RULES = [
    Rule("m-name", "Keep the theorem name and the statement exactly as given; Madalean adds the header "
                   "(`import Mathlib`, `import Aesop`, `open BigOperators Real Nat Topology Rat`): never add imports "
                   "or `set_option`.", core=True),
    Rule("m-forbid", "Never write `sorry`, `admit`, `axiom`, `apply?`/`exact?`, `#exit`, `native_decide`, `#eval` or "
                     "meta-programming: Madalean refuses such proofs before compiling.", core=True),
    Rule("m-verdict", "Only Lean's strict verdict makes a proof « vérifiée »; a model never says a proof is checked.",
         core=True),
    Rule("m-faithful", "A Lean statement keeps every hypothesis of the problem (non-empty, positive, finite "
                       "dimension…) and states its real content (never `True`, `x = x`).",
         frozenset({"set", "ineq", "analysis", "linalg"}), core=True),
    Rule("m-mathlib", "When a result is in Mathlib, use its exact name (check the namespace) instead of reproving it.",
         frozenset({"analysis", "linalg", "arith", "sum"})),
]

PYTHON_RULES = [
    Rule("py-print", "Python 3: print the results you need; no `input()`, no network, no files outside the "
                     "working directory.", core=True),
    Rule("py-exact", "Exact arithmetic: `fractions.Fraction`, integers; floats only for numerical approximations.",
         frozenset({"numeric", "arith"})),
    Rule("py-sympy", "Symbolic work in plain Python: `sympy.symbols`, `sympy.simplify`, `sympy.solve`.",
         frozenset({"symbolic", "solve"})),
]

LATEX_RULES = [
    Rule("tex-env", "Use amsthm environments `theorem`, `lemma`, `proof`, `definition`; amsmath `align*` for "
                    "multi-line computations; no `\\usepackage` inside a fragment.", core=True),
    Rule("tex-math", "Inline math `$…$`, display `\\[…\\]` (never `$$…$$`); sets `\\mathbb{N}`, `\\mathbb{R}`; "
                     "functions `\\sin`, `\\log`, `\\operatorname{rg}`.", core=True),
    Rule("tex-fr", "French text: « guillemets » (`\\og … \\fg{}`), non-breaking space before `:` `;` `?` `!`, "
                   "decimal comma `{,}` in math.", core=True),
    Rule("tex-ref", "Cite only keys that exist (`\\cite{key}` from the bibliography given); label every numbered "
                    "result `\\label{thm:…}` and refer with `\\ref`.", frozenset({"ref"})),
    Rule("tex-table", "Tables: `tabular` with `booktabs` rules (`\\toprule`, `\\midrule`, `\\bottomrule`).",
         frozenset({"table"})),
]

EXPLAIN_RULES = [
    Rule("ex-lang", "Write in the user's language (French by default), for a student: plain words, define each "
                    "notation once, no Lean jargon unless asked.", core=True),
    Rule("ex-ref", "The Lean proof is the reference: follow its steps, name the Mathlib results it uses in "
                   "backticks, never claim more than it proves.", core=True),
    Rule("ex-math", "Formulas in LaTeX `$…$`; short paragraphs; the key idea first, then the steps.", core=True),
    Rule("ex-cite", "No invented references: cite only the sources given.", frozenset({"ref"})),
    Rule("ex-ind", "For an induction: state the base case and the inductive step separately.",
         frozenset({"induction"})),
    Rule("ex-ineq", "For inequalities: say which known inequality is used and why its hypotheses hold.",
         frozenset({"ineq"})),
]

_SAGE_TAGS = {"var": None, "pow": None, "exact": None, "func": {"symbolic", "analysis"},
              "integral": {"analysis"}, "assume": {"assume"}, "sum": {"sum"}, "plot": {"plot"}, "plot2": {"plot"},
              "latex": {"ref", "table"}, "graphs": {"graph"}, "print": None}


def _lean_entries(ws) -> tuple[list[tuple[str, str]], str, bool]:
    """(entries [(id, text)], title, verified) — the verified card of this workspace when built (syntaxcards)."""
    from .. import syntaxcards
    if ws is not None:
        try:
            d = json.loads(syntaxcards._lean_file(ws).read_text(encoding="utf-8"))   # noqa: SLF001 (read-only)
            if d.get("entries"):
                title = f"Lean {d.get('lean') or '4'}, Mathlib {d.get('mathlib') or '?'} (checked on this workspace)"
                return [(e["id"], e["text"]) for e in d["entries"]], title, True
        except (OSError, ValueError, KeyError, TypeError):
            pass
    # not built yet: the same entries, one big-operator variant (current Mathlib: `∑ i ∈ s`), not checked here
    return [(e[0], e[1]) for e in syntaxcards.LEAN_ENTRIES if e[0] != "bigop_in"], "Lean 4 + Mathlib (not checked " \
        "on this workspace yet)", False


def _sage_entries() -> tuple[list[tuple[str, str]], str, bool]:
    from .. import syntaxcards
    try:
        v = syntaxcards.sage_version() if syntaxcards.sage_python() else ""
        d = syntaxcards.sage_card_data(v) if v else None
    except Exception:  # noqa: BLE001
        d, v = None, ""
    if d:
        return [(e["id"], e["text"]) for e in d["entries"]], f"SageMath {d['version']} (checked here)", True
    return [(e[0], e[1]) for e in syntaxcards.SAGE_ENTRIES], f"SageMath {v or '10'} (usual idioms)", False


def card(tool: str, ws=None) -> Card:
    if tool == "lean":
        entries, title, ok = _lean_entries(ws)
        rules = []
        for eid, text in entries:
            tags = _LEAN_TAGS.get(eid, set())
            rules.append(Rule(f"lean-{eid}", text, frozenset(tags or ()), core=tags is None))
        return Card("lean", title, rules, ok)
    if tool == "sage":
        entries, title, ok = _sage_entries()
        rules = []
        for eid, text in entries:
            tags = _SAGE_TAGS.get(eid, set())
            rules.append(Rule(f"sage-{eid}", text, frozenset(tags or ()), core=tags is None))
        return Card("sage", title, rules, ok)
    fixed = {"madalean": ("Madalean conventions for Lean", MADALEAN_RULES),
             "python": ("Python 3", PYTHON_RULES), "latex": ("LaTeX (article)", LATEX_RULES),
             "explain": ("Explanations for the user", EXPLAIN_RULES)}
    title, rules = fixed[tool]
    return Card(tool, title, list(rules), True)


TOOLS = ("madalean", "lean", "sage", "python", "latex", "explain")

# which tools each responsible model writes for, and the token budget of its request block
ROLE_TOOLS: dict[str, tuple[str, ...]] = {
    "formalize": ("madalean", "lean"), "prove": ("madalean", "lean"), "explain": ("explain",),
    "understand": ("explain",), "route": (), "sage": ("sage", "python"), "python": ("python",),
    "latex": ("latex", "explain"),
    # the conductor's own decisions
    "plan": ("madalean", "lean", "explain"), "fix_statement": ("madalean", "lean"),
    "fix_proof": ("madalean", "lean"), "final": ("madalean", "explain"),
    # S-AN (D46): corrections outside a job — a failed Calcul cell, a failed article compilation
    "fix_sage": ("sage", "python"), "fix_python": ("python",), "fix_latex": ("latex",),
}
ROLE_BUDGET = {"formalize": 450, "prove": 450, "explain": 200, "understand": 120, "route": 0, "sage": 450,
               "python": 150, "latex": 250, "plan": 350, "fix_statement": 450, "fix_proof": 500, "final": 200,
               "fix_sage": 450, "fix_python": 150, "fix_latex": 250}


CATALOGUE_BUDGET = 220            # S-AM: tokens of verified catalogue constructions in a Lean-writing request block


def _norm(text: str) -> str:
    return re.sub(r"[\W_]+", " ", text.lower()).strip()


@dataclass
class Compacted:
    stable: str                       # versioned block before the cache breakpoint ('' when the role has no tool)
    request: str                      # rules selected for this request, after the breakpoint
    stable_hash: str
    tokens_full: int                  # every rule of every card of the role's tools (no selection)
    tokens_all_cards: int             # every card of every tool (what a naive prompt would carry)
    tokens_stable: int
    tokens_request: int
    selected: list[str] = field(default_factory=list)
    dropped: list[str] = field(default_factory=list)

    @property
    def tokens(self) -> int:
        return self.tokens_stable + self.tokens_request


def _render(c: Card, rules: list[Rule]) -> str:
    return f"## {c.title}\n" + "\n".join(f"- {r.text}" for r in rules)


def compact(role: str, features: frozenset | set = frozenset(), ws=None, budget: int | None = None,
            tools: tuple[str, ...] | None = None, intent_text: str = "") -> Compacted:
    """The rule cards of `role`'s tools, compacted for one request: core rules in the stable block, feature rules in
    the request block (deduplicated across cards, cut to `budget` tokens, lowest priority = last in card order).
    `intent_text` (S-AM, D45): for a role that writes Lean, the code catalogue's constructions relevant to it and
    verified on `ws` are added to the request block (after the cache breakpoint: the stable block is unchanged)."""
    tools = ROLE_TOOLS.get(role, ()) if tools is None else tools
    budget = ROLE_BUDGET.get(role, 300) if budget is None else budget
    cards = [card(t, ws) for t in tools]
    seen: list[str] = []

    def dup(r: Rule) -> bool:
        n = _norm(r.text)
        if any(n == s or (len(n) > 40 and n in s) for s in seen):
            return True
        seen.append(n)
        return False

    stable_parts, extra, dropped = [], [], []
    for c in cards:
        core = [r for r in c.rules if r.core and not dup(r)]
        if core:
            stable_parts.append(_render(c, core))
    for c in cards:
        for r in c.rules:
            if r.core:
                continue
            if r.tags & set(features) and not dup(r):
                extra.append((c, r))
            else:
                dropped.append(r.id)
    stable = ""
    if stable_parts:
        stable = (f"# Tool rules (Madalean cards v{CARDS_VERSION}) — follow them exactly\n"
                  + "\n\n".join(stable_parts))
    picked: list[tuple[Card, Rule]] = []
    used = 0
    for c, r in extra:
        t = estimate_tokens(r.text) + 2
        if used + t > budget:
            dropped.append(r.id)
            continue
        picked.append((c, r))
        used += t
    req = ""
    if picked:
        by: dict[str, list[Rule]] = {}
        for c, r in picked:
            by.setdefault(c.title, []).append(r)
        req = "# Rules for this request\n" + "\n".join(f"- {r.text}" for rs in by.values() for r in rs)
    if intent_text and "lean" in tools and ws is not None:
        try:
            from ..research import codecat
            cat, ids = codecat.lean_prompt_block(ws, intent_text, budget=CATALOGUE_BUDGET)
        except Exception:  # noqa: BLE001 (no catalogue: the cards as before)
            cat, ids = "", []
        if cat:
            req = (req + "\n\n" + cat) if req else cat
            picked += [(None, Rule(f"cat-{i}", "")) for i in ids]      # listed in `selected` (measured)
    full ="\n".join(_render(c, c.rules) for c in cards)
    all_cards = "\n".join(_render(c, c.rules) for c in (card(t, ws) for t in TOOLS))
    return Compacted(stable, req, hashlib.sha256(stable.encode()).hexdigest()[:12], estimate_tokens(full),
                     estimate_tokens(all_cards), estimate_tokens(stable), estimate_tokens(req),
                     [r.id for _c, r in picked], dropped)


def worker_messages(messages: list[dict], role: str, features: frozenset, ws=None) -> tuple[list[dict], Compacted]:
    """The messages of a worker call with its tool cards in front: a stable system block (cache breakpoint after it)
    then the request's rules, then the original messages unchanged. Roles without tools: unchanged."""
    c = compact(role, features, ws)
    if not c.stable and not c.request:
        return messages, c
    head = []
    if c.stable:
        head.append({"role": "system", "content": c.stable, "stable": True})
    if c.request:
        head.append({"role": "system", "content": c.request})
    return head + list(messages), c
