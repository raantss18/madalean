"""« Préparer une contribution à Mathlib » (TODO « Stratégie 2.1 » item 7, session S-BC, DECISIONS D61).

From a verified result (a library entry, or a dossier's current verified proof), build a contribution package the
user reviews; nothing leaves the machine unless the user clicks twice (docs/MATHLIB_CONTRIB.md):

1. **Port** — contributions target current Mathlib: the result is re-checked by a fresh strict Lean in
   `lean-current`. A proof from `lean-prover49` is ported first, without a model: names the old Lean itself reports
   as deprecated, the lessons store's exact renames for the target Mathlib (D57b), a small verified table of renames
   (`BUILTIN_RENAMES`, each entry checked in both workspaces) and syntax changes (`∑ x in s` → `∑ x ∈ s`). When that
   is not enough, the user may relaunch the normal proof pipeline in `lean-current` with the old proof as a hint
   (`reprove`); only a fresh strict verdict in `lean-current` counts.
2. **Already in Mathlib?** D56's `MathlibFirst` without a model (index candidates under short templates, then
   `exact?`), on `lean-current`. A named lemma that closes the statement stops the preparation (no duplicate).
3. **Style** — deterministic, documented rules (`CHECKS`), Mathlib's own `#lint` and standard linter set run on the
   final file, a name proposed from the statement's shape (Mathlib naming guide) and checked to be free, the import
   set shrunk with Mathlib's `#min_imports` and re-checked.
4. **Package** — the file (copyright line, `module`, imports, module docstring, docstrings), the target path, the PR
   title / description (English) and an explanation for the user (French / English), the checklist.

The GitHub part (fork + branch + commit, then a draft PR) lives in `github_*` below; it is host-only, needs the key
saved in Réglages → Clés, shows exactly what will be sent, and never runs without the user's confirmation of that
exact plan."""
from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import re
import secrets
import time
from dataclasses import dataclass
from pathlib import Path

from .. import config, leancheck
from ..logs import get

log = get("research.mathlib_contrib")

TARGET_WS = "lean-current"
UPSTREAM = "leanprover-community/mathlib4"
UPSTREAM_BRANCH = "master"
# the same name as Réglages → À propos (web/src/screens/settings/About.svelte); editable in the panel
DEFAULT_AUTHOR = "RANIRIAMANJAKA Antsa"
LINKS = [
    {"id": "contribute", "url": "https://leanprover-community.github.io/contribute/index.html"},
    {"id": "naming", "url": "https://leanprover-community.github.io/contribute/naming.html"},
    {"id": "style", "url": "https://leanprover-community.github.io/contribute/style.html"},
    {"id": "doc", "url": "https://leanprover-community.github.io/contribute/doc.html"},
    {"id": "commit", "url": "https://leanprover-community.github.io/contribute/commit.html"},
]
CHECK_TIMEOUT = 240
MAX_LINE = 100
PLAN_TTL = 900

HEADER_CURRENT = "import Mathlib\n\nopen BigOperators Real Nat Topology Rat\n\n"
# Mathlib v4.9 (Goedel's fork) → v4.36 renames, each checked with `#check` in both workspaces (2026-11-24). The old
# name is unknown to lean-current and the new one has the same statement; aliases deprecated in between included.
BUILTIN_RENAMES = {
    "Finset.card_le_of_subset": "Finset.card_le_card",
    "pow_lt_pow": "pow_lt_pow_right₀",
    "pow_lt_pow_right": "pow_lt_pow_right₀",
    "pow_le_pow_right": "pow_le_pow_right₀",
    "Real.rpow_nat_cast": "Real.rpow_natCast",
    "Int.coe_nat_dvd": "Int.natCast_dvd_natCast",
    "Int.coe_nat_pow": "Int.natCast_pow",
    "Int.coe_natAbs": "Int.natCast_natAbs",
    "div_le_div_of_le_left": "div_le_div_of_nonneg_left",
    "Nat.mul_le_mul_of_nonneg_left": "Nat.mul_le_mul_left",
    "zpow_coe_nat": "zpow_natCast",
}
# big operators: `∑ x in s, f x` became `∑ x ∈ s, f x` (the old form is a parse error in lean-current)
SYNTAX_RENAMES = [(re.compile(r"([∑∏]\s*[^,∈\n]+?)\s+in\s+"), r"\1 ∈ ", "∑ x in s → ∑ x ∈ s")]
# tactics whose module `#min_imports` may not list (it reads the syntax and the constants of the proof term)
TACTIC_MODULES = {
    "positivity": "Mathlib.Tactic.Positivity", "nlinarith": "Mathlib.Tactic.Linarith",
    "linarith": "Mathlib.Tactic.Linarith", "norm_num": "Mathlib.Tactic.NormNum", "ring": "Mathlib.Tactic.Ring",
    "ring_nf": "Mathlib.Tactic.Ring", "field_simp": "Mathlib.Tactic.FieldSimp", "gcongr": "Mathlib.Tactic.GCongr",
    "interval_cases": "Mathlib.Tactic.IntervalCases", "bound": "Mathlib.Tactic.Bound", "abel": "Mathlib.Tactic.Abel",
    "contrapose": "Mathlib.Tactic.Contrapose", "push_neg": "Mathlib.Tactic.Push", "zify": "Mathlib.Tactic.Zify",
    "qify": "Mathlib.Tactic.Qify", "rify": "Mathlib.Tactic.Rify", "lift": "Mathlib.Tactic.Lift",
    "use": "Mathlib.Tactic.Use", "choose": "Mathlib.Tactic.Choose", "tauto": "Mathlib.Tactic.Tauto",
    "by_contra!": "Mathlib.Tactic.ByContra", "set": "Mathlib.Tactic.Set",
}
STEPS = ("port", "mathlib", "name", "imports", "final", "lint")
_DECL_START = re.compile(r"(?m)^(?=(?:@\[[^\]]*\]\s*)?(?:private\s+|protected\s+|noncomputable\s+)*"
                         r"(?:theorem|lemma|def|abbrev|instance)\s)")
_DECL_HEAD = re.compile(r"(theorem|lemma|def|abbrev|instance)\s+([^\s:({\[⦃]+)")
DEPRECATED_RE = re.compile(r"`([^`\s]+)` has been deprecated[^`]*?use `([^`\s]+)` instead")
DOC_RE = re.compile(r"/--(.*?)-/\s*$", re.S)


class ContribError(Exception):
    def __init__(self, code: str, status: int = 400, **params):
        super().__init__(code)
        self.code, self.status, self.params = code, status, params


# ---------------------------------------------------------------- declarations
@dataclass
class Decl:
    kind: str
    name: str
    text: str            # the declaration (no docstring), as in the proof
    doc: str = ""


def split_decls(body: str) -> list[Decl]:
    """Top-level declarations of a header-free proof body, in order. A `/-- … -/` docstring belongs to the next
    declaration; `-- …` comment lines between declarations are dropped."""
    out, pending = [], ""
    for block in _DECL_START.split(body):
        tail_doc = ""
        dm = DOC_RE.search(block)
        if dm:
            tail_doc, block = " ".join(dm.group(1).split()), block[:dm.start()]
        lines = block.rstrip().split("\n")
        while lines and lines[-1].lstrip().startswith("--"):
            lines.pop()
        block = "\n".join(lines).strip("\n")
        m = _DECL_HEAD.search(block)
        if m and block.strip():
            start = block.index("@[") if block.lstrip().startswith("@[") else m.start()
            out.append(Decl(m.group(1), m.group(2), block[start:].rstrip(), pending))
        pending = tail_doc
    return out


def main_signature(text: str) -> tuple[str, str] | None:
    """(binders, conclusion) of a theorem declaration: the first top-level `:` ends the binders."""
    m = re.match(r"\s*(?:theorem|lemma)\s+[^\s:({\[⦃]+(.*?):=", text, re.S)
    if not m:
        return None
    sig = m.group(1)
    depth = 0
    for i, ch in enumerate(sig):
        if ch in "([{⦃⟨":
            depth += 1
        elif ch in ")]}⦄⟩":
            depth = max(0, depth - 1)
        elif ch == ":" and depth == 0:
            return " ".join(sig[:i].split()), " ".join(sig[i + 1:].split())
    return None


def binder_groups(binders: str) -> list[dict]:
    """`(a b : ℕ) {x : ℝ} [Foo α] (h : a ≤ b)` → [{bracket, names, type}] (top-level groups only)."""
    out, depth, start = [], 0, -1
    for i, ch in enumerate(binders):
        if ch in "([{⦃":
            if depth == 0:
                start = i
            depth += 1
        elif ch in ")]}⦄":
            depth -= 1
            if depth == 0 and start >= 0:
                inner = binders[start + 1:i]
                names, _, typ = inner.partition(":")
                if not typ:                      # `[Foo α]`
                    names, typ = "", inner
                out.append({"bracket": binders[start], "names": names.split(), "type": typ.strip()})
                start = -1
    return out


_PROP_RE = re.compile(r"[≤<≥>=≠∣¬∧∨↔→∀∃∈∉⊆]|\b(Prime|Even|Odd|IsSquare|Nat\.Prime|Irrational|Continuous|Monotone|"
                      r"StrictMono|Injective|Surjective|Bijective|Squarefree|Coprime)\b")


def is_hypothesis(g: dict) -> bool:
    return g["bracket"] in "({" and bool(g["names"]) and bool(_PROP_RE.search(g["type"])) and \
        g["type"].strip() not in ("Prop", "Type", "Type*")


# ---------------------------------------------------------------- port helpers (pure)
def deprecations(messages) -> dict[str, str]:
    """{old: new} from Lean's « `old` has been deprecated, use `new` instead » warnings."""
    out = {}
    for m in messages:
        for a, b in DEPRECATED_RE.findall(getattr(m, "text", "") or ""):
            out[a] = b
    return out


def rename_idents(code: str, table: dict[str, str]) -> tuple[str, list[dict]]:
    """Whole-identifier renames, chained (a → b → c); returns the code and [{old, new}] actually applied."""
    used = []
    for old in sorted(table, key=len, reverse=True):
        new = table[old]
        seen = {old}
        while new in table and table[new] not in seen:      # follow a chain of renames to its end
            seen.add(new)
            new = table[new]
        pat = re.compile(r"(?<![\w.'₀-₉])" + re.escape(old) + r"(?![\w'₀-₉])")
        if new != old and pat.search(leancheck.lean_code_only(code)):
            code = pat.sub(new, code)
            used.append({"old": old, "new": new})
    return code, used


def syntax_port(code: str) -> tuple[str, list[str]]:
    used = []
    for pat, rep, label in SYNTAX_RENAMES:
        new = pat.sub(rep, code)
        if new != code:
            code, _ = new, used.append(label)
    return code, used


# ---------------------------------------------------------------- naming (Mathlib naming guide)
OPS = [("⁻¹", "inv"), ("≤", "le"), ("<", "lt"), ("≥", "ge"), (">", "gt"), ("≠", "ne"), ("=", "eq"), ("+", "add"),
       ("*", "mul"), ("/", "div"), ("^", "pow"), ("%", "mod"), ("∣", "dvd"), ("¬", "not"), ("∧", "and"),
       ("∨", "or"), ("↔", "iff"), ("∑", "sum"), ("∏", "prod"), ("√", "sqrt"), ("!", "factorial"), ("•", "smul"),
       ("∈", "mem"), ("∉", "not_mem"), ("⊆", "subset"), ("∩", "inter"), ("∪", "union"), ("∘", "comp"),
       ("→", "imp"), ("↑", "cast")]
NUMS = {"0": "zero", "1": "one", "2": "two", "3": "three"}
_SKIP_IDENTS = {"fun", "by", "in", "at", "with", "then", "else", "if", "let", "have", "show", "from", "Finset",
                "Set", "ℕ", "ℤ", "ℚ", "ℝ", "ℂ", "Real", "Nat", "Int", "Rat", "Complex", "Type", "Prop", "∀", "∃"}
NAMESPACES = {"ℕ": "Nat", "ℤ": "Int", "ℝ": "Real", "ℚ": "Rat", "ℂ": "Complex"}
BIGOP_BINDER = r"([∑∏])\s*\(?\s*(?:\w+\s*)+(?::\s*[^)∈,]*)?\)?\s*(?:∈|in)\s*"
_TOKEN = re.compile(r"⁻¹|[≤<≥>≠=+*/^%∣¬∧∨↔∑∏√!•∈∉⊆∩∪∘→↑|-]|[A-Za-zα-ωΑ-Ω_][\w'.₀-₉]*|\d+|[(),:]")


def _strip_ascriptions(expr: str) -> str:
    """`(x : ℝ)` → `↑x` (a cast, as Mathlib names it); other `( … : T)` type ascriptions dropped."""
    expr = re.sub(r"\(\s*(\w+)\s*:\s*[ℕℤℚℝℂ]\s*\)", r"↑\1", expr)
    return re.sub(r":\s*[ℕℤℚℝℂ]\b", "", expr)


def expr_words(expr: str, variables: set[str]) -> list[tuple[str, str]]:
    """Reading-order (token, word) pairs of an expression; bound variables are not part of a name."""
    out: list[tuple[str, str]] = []
    expr = _strip_ascriptions(expr)
    expr = re.sub(BIGOP_BINDER, r"\1 ", expr)                  # `∑ i ∈ s, f i` is read `sum s f`
    expr = re.sub(r"\^\s*2(?![\d.])", " SQ ", expr)              # `x ^ 2` is `sq` in Mathlib's names
    prev = ""
    abs_open = False
    for tok in _TOKEN.findall(expr):
        word = ""
        if tok == "-":
            word = "neg" if prev in ("", "(", ",", ":") or prev in dict(OPS) else "sub"
        elif tok == "|":
            if not abs_open:
                word = "abs"
            abs_open = not abs_open
        elif tok in dict(OPS):
            word = dict(OPS)[tok]
        elif tok == "SQ":
            word = "sq"
        elif tok.isdigit():
            word = NUMS.get(tok, "")
        elif tok not in variables and tok not in _SKIP_IDENTS and tok not in "(),:":
            last = tok.rsplit(".", 1)[-1]
            if last and not last.startswith("h"):
                word = last[0].lower() + last[1:]
        if word and not (out and out[-1][1] == word == "cast"):
            out.append((tok, word))
        prev = tok
    return out


def _rel_words(expr: str, variables: set[str]) -> tuple[list[tuple[str, str]], str]:
    """Words of a proposition with Mathlib's special forms: `0 ≤ e` → e_nonneg, `0 < e` → e_pos, `e ≠ 0` →
    e_ne_zero, `e ≤ 0` → e_nonpos, `e < 0` → e_neg. Returns (pairs, rule id or '')."""
    e = expr.strip()
    for pat, word, rule in ((r"^0\s*≤\s*(.+)$", "nonneg", "nonneg"), (r"^(.+?)\s*≥\s*0$", "nonneg", "nonneg"),
                            (r"^0\s*<\s*(.+)$", "pos", "pos"), (r"^(.+?)\s*>\s*0$", "pos", "pos"),
                            (r"^(.+?)\s*≠\s*0$", "ne_zero", "ne_zero"), (r"^(.+?)\s*≤\s*0$", "nonpos", "nonpos"),
                            (r"^(.+?)\s*<\s*0$", "neg", "neg")):
        m = re.match(pat, e)
        if m and not re.search(r"[≤<≥>=≠]", m.group(1)):
            return expr_words(m.group(1), variables) + [("0", word)], rule
    return expr_words(e, variables), ""


def suggest_name(decl_text: str, title: str = "") -> dict:
    """A Mathlib-style name for a theorem from its statement's shape (docs/MATHLIB_CONTRIB.md §3):
    the conclusion read left to right (`+` add, `≤` le, `0 ≤ e` e_nonneg …), then `_of_` each hypothesis (two at
    most), variables left out; the namespace from the functions used or the type of all variables.
    → {name, namespace, full, words: [{token, word, part}], rules: [ids], fallback: bool}."""
    sig = main_signature(decl_text)
    if sig is None:
        base = re.sub(r"[^a-z0-9]+", "_", (title or "result").lower()).strip("_")[:40] or "result"
        return {"name": base, "namespace": "", "full": base, "words": [], "rules": ["fallback"], "fallback": True}
    binders, concl = sig
    groups = binder_groups(binders)
    variables = {n for g in groups if not is_hypothesis(g) for n in g["names"]}
    for bound in re.findall(r"[∀∃∑∏]\s*\(?([\w\s]+?)\s*[,:∈)]", concl):     # bound by ∀ ∃ ∑ ∏
        variables |= set(bound.split())
    rules = []
    concl_core = re.sub(r"^[∀∃][^,]*,\s*", "", concl)
    pairs, rule = _rel_words(concl_core, variables)
    if rule:
        rules.append(rule)
    words = [{"token": t, "word": w, "part": "conclusion"} for t, w in pairs]
    hyps = [g for g in groups if is_hypothesis(g)]
    for g in hyps[:2]:
        hp, hr = _rel_words(g["type"], variables)
        if not hp:
            continue
        if hr:
            rules.append(hr)
        words.append({"token": "", "word": "of", "part": "hypothesis"})
        words += [{"token": t, "word": w, "part": "hypothesis"} for t, w in hp]
    if len(hyps) > 2:
        rules.append("hyps_trimmed")
    concl_words = [w for w in words if w["part"] == "conclusion"]
    if len(concl_words) > 10 or not concl_words:
        base = re.sub(r"[^a-z0-9]+", "_", (title or "result").lower()).strip("_")[:40] or "result"
        return {"name": base, "namespace": _namespace(binders, concl), "full": base, "words": words,
                "rules": rules + ["fallback"], "fallback": True}
    while len(words) > 12 and any(w["part"] == "hypothesis" for w in words):
        last_of = max(i for i, w in enumerate(words) if w["word"] == "of")
        words = words[:last_of]
        rules.append("hyps_trimmed")
    name = "_".join(w["word"] for w in words)
    name = re.sub(r"_+", "_", name).strip("_")
    ns = _namespace(binders, concl)
    if ns:
        rules.append("namespace")
    return {"name": name, "namespace": ns, "full": f"{ns}.{name}" if ns else name, "words": words,
            "rules": list(dict.fromkeys(rules)), "fallback": False}


def _namespace(binders: str, concl: str) -> str:
    qual = re.findall(r"\b(Nat|Int|Real|Rat|Complex)\.[a-z]\w*", concl)
    if qual:
        return max(set(qual), key=qual.count)
    types = [g["type"] for g in binder_groups(binders) if not is_hypothesis(g)]
    kinds = {NAMESPACES.get(t.strip()) for t in types}
    if len(kinds) == 1 and None not in kinds:
        return kinds.pop()
    return ""


# ---------------------------------------------------------------- style checks (each documented)
CHECKS = {
    # id: (severity when it fails, documented rule — docs/MATHLIB_CONTRIB.md §4)
    "lean_current": ("error", "a fresh strict Lean in lean-current accepts the file"),
    "no_sorry_axioms": ("error", "no sorry / admit / new axiom; only propext, Classical.choice, Quot.sound"),
    "not_in_mathlib": ("error", "no Mathlib lemma already closes the statement"),
    "name_free": ("error", "the proposed name is not already a Mathlib declaration"),
    "name_snake_case": ("warning", "theorem names are snake_case (lowerCamelCase only inside, for a function name)"),
    "copyright_header": ("error", "the file starts with the copyright / Apache 2.0 / Authors header"),
    "module_docstring": ("error", "a /-! … -/ module docstring with a # title follows the imports"),
    "docstrings": ("warning", "every theorem has a /-- … -/ docstring: a sentence ending with a period"),
    "line_length": ("error", "no line longer than 100 characters"),
    "whitespace": ("warning", "no tab, no trailing space"),
    "max_heartbeats": ("warning", "no set_option maxHeartbeats (or a justified `set_option … in`)"),
    "non_terminal_simp": ("warning", "no simp (without only) followed by other tactics on the same goal"),
    "ge_gt": ("warning", "statements use ≤ and <, not ≥ and >"),
    "implicit_args": ("warning", "variables determined by a later hypothesis are implicit {…}"),
    "deprecated": ("warning", "no deprecated Mathlib name"),
    "lint": ("error", "Mathlib's #lint passes on the new declarations"),
    "mathlib_linters": ("warning", "Mathlib's standard linter set reports nothing"),
    "imports_minimal": ("warning", "the imports are shrunk from `import Mathlib` to the modules needed"),
}


def check(cid: str, ok: bool | None, **params) -> dict:
    """One checklist line: ok (True), failed (False, with the rule's severity) or not run (None, « unknown »)."""
    sev = "ok" if ok else ("unknown" if ok is None else CHECKS[cid][0])
    return {"id": cid, "ok": ok, "severity": sev, "params": params}


def text_checks(file_text: str, decls: list[Decl]) -> list[dict]:
    """The checks that read the file only (no Lean)."""
    lines = file_text.split("\n")
    out = []
    long_ = [i + 1 for i, l in enumerate(lines) if len(l) > MAX_LINE]
    out.append(check("line_length", not long_, lines=long_[:10]))
    ws = [i + 1 for i, l in enumerate(lines) if "\t" in l or l != l.rstrip()]
    out.append(check("whitespace", not ws, lines=ws[:10]))
    head = "\n".join(lines[:6])
    out.append(check("copyright_header", bool(re.match(
        r"/-\nCopyright \(c\) \d{4} [^\n]+\. All rights reserved\.\nReleased under Apache 2\.0 license as described in "
        r"the file LICENSE\.\nAuthors: [^\n]+\n-/", head))))
    out.append(check("module_docstring", bool(re.search(r"(?m)^/-!\s*\n#\s+\S", file_text))))
    code = leancheck.lean_code_only(file_text)
    out.append(check("no_sorry_axioms", not leancheck.forbidden_reasons(file_text),
                     reasons=leancheck.forbidden_reasons(file_text)))
    hb = re.findall(r"set_option\s+maxHeartbeats\s+\d+(\s+in)?", code)
    out.append(check("max_heartbeats", not hb, scoped=all(bool(x) for x in hb) if hb else True))
    bad_names = [d.name for d in decls if not re.fullmatch(r"[a-z][a-z0-9_'₀-₉]*(?:[A-Z][A-Za-z0-9]*[a-z0-9_'₀-₉]*)*",
                                                            d.name.rsplit(".", 1)[-1]) and d.kind in ("theorem", "lemma")]
    out.append(check("name_snake_case", not bad_names, names=bad_names))
    no_doc = [d.name for d in decls if not _doc_ok(file_text, d.name)]
    out.append(check("docstrings", not no_doc, names=no_doc))
    simp = simp_lines(file_text)
    out.append(check("non_terminal_simp", not simp, lines=simp))
    ge = [d.name for d in decls if (s := main_signature(d.text)) and re.search(r"[≥>]", leancheck.lean_code_only(
        s[0] + " : " + s[1]).replace("->", "→").replace("=>", ""))]
    out.append(check("ge_gt", not ge, names=ge))
    imp = implicit_suggestions(decls)
    out.append(check("implicit_args", not imp, items=imp))
    return out


def _doc_ok(file_text: str, name: str) -> bool:
    short = re.escape(name.rsplit(".", 1)[-1])
    m = re.search(r"/--\s*(.*?)\s*-/\s*\n\s*(?:@\[[^\]]*\]\s*)?(?:theorem|lemma)\s+(?:[\w.]+\.)?" + short + r"\b",
                  file_text, re.S)
    if not m:
        return False
    doc = m.group(1).strip()
    return len(doc) >= 8 and doc.endswith((".", "`.", ".)")) and (doc[0].isupper() or doc[0] in "`$(")


def simp_lines(file_text: str) -> list[int]:
    """Lines with a `simp` / `simp_all` (not `simp only`, `simpa`, `simp?`) that another tactic follows on the same
    goal (same or deeper indentation, or `<;>`): Mathlib's « non-terminal simp »."""
    lines = file_text.split("\n")
    flagged = []
    for i, line in enumerate(lines):
        s = leancheck.lean_code_only(line).strip().lstrip("·").strip()
        if not re.match(r"simp(_all)?(?![\w?'!])", s) or re.match(r"simp(_all)?\s+only\b", s):
            continue
        if "<;>" in s:
            flagged.append(i + 1)
            continue
        ind = len(line) - len(line.lstrip())
        for nxt in lines[i + 1:]:
            if not nxt.strip() or nxt.strip().startswith("--"):
                continue
            if len(nxt) - len(nxt.lstrip()) >= ind and \
                    not re.match(r"\s*(theorem|lemma|end|namespace|/--|#|@\[)", nxt):
                flagged.append(i + 1)
            break
    return flagged


def implicit_suggestions(decls: list[Decl]) -> list[dict]:
    """Explicit variables that a later explicit hypothesis determines: Mathlib makes them implicit."""
    out = []
    for d in decls:
        sig = main_signature(d.text)
        if sig is None:
            continue
        groups = binder_groups(sig[0])
        for i, g in enumerate(groups):
            if g["bracket"] != "(" or is_hypothesis(g):
                continue
            later = [h for h in groups[i + 1:] if h["bracket"] == "(" and is_hypothesis(h)]
            names = [n for n in g["names"]
                     if any(re.search(rf"(?<![\w.']){re.escape(n)}(?![\w'])", h["type"]) for h in later)]
            if names:
                out.append({"decl": d.name, "names": names})
    return out


# ---------------------------------------------------------------- file, path, PR texts
def module_name(full: str) -> str:
    """UpperCamelCase file name from the first four words of the declaration name."""
    parts = [p for p in re.split(r"[_.']", full.rsplit(".", 1)[-1]) if p][:4]
    return "".join(p[:1].upper() + p[1:] for p in parts)[:40] or "Result"


def target_path(votes: list[str], full: str, imports: list[str] | None = None) -> dict:
    """`closest`: among the file's minimal imports (non-tactic), the one the index's premises vote for most (else
    the first); without imports, the most voted module. `path`: a new file in the same folder."""
    def real(ms):
        return [m for m in ms if m.startswith("Mathlib.") and ".Tactic." not in m and m != "Mathlib"]
    votes, imps = real(votes), real(imports or [])
    pool = imps or votes
    if pool:
        closest = max(pool, key=lambda m: (votes.count(m), -pool.index(m)))
    else:
        closest = "Mathlib.Data.Nat.Basic"
    folder = closest.rsplit(".", 1)[0]
    new = f"{folder}.{module_name(full)}"
    return {"closest": closest, "module": new, "path": new.replace(".", "/") + ".lean",
            "closest_path": closest.replace(".", "/") + ".lean"}


def opens_for(body: str) -> list[str]:
    """The namespaces the proof's unqualified names / notations need (Goedel's header opened them all)."""
    code = leancheck.lean_code_only(body)
    out = []
    if re.search(r"π|(?<![\w.])(sqrt|exp|log|cos|sin|tan|rpow|arctan)\b", code):
        out.append("Real")
    if re.search(r"\w!|(?<![\w.])(choose|succ|factorial|totient|digits|divisors|primeFactors)\b|φ", code):
        out.append("Nat")
    if re.search(r"𝓝|atTop", code):
        out.append("Topology")
    return out


def build_file(*, author: str, year: int, title: str, summary: str, imports: list[str], opens: list[str],
               namespace: str, decls: list[tuple[str, str]], main_full: str) -> str:
    """decls: [(docstring, declaration text)] with the main theorem last."""
    out = ["/-", f"Copyright (c) {year} {author}. All rights reserved.",
           "Released under Apache 2.0 license as described in the file LICENSE.", f"Authors: {author}", "-/",
           "module", ""]
    out += [f"public import {m}" for m in imports]
    out += ["", "/-!", f"# {title}", "", summary, "", "## Main statements", "",
            f"* `{main_full}`: {summary_line(decls[-1][0])}", "-/", "", "public section", ""]
    if opens:
        out += [f"open {' '.join(opens)}", ""]
    if namespace:
        out += [f"namespace {namespace}", ""]
    for doc, text in decls:
        out += [f"/-- {doc} -/", text.rstrip(), ""]
    if namespace:
        out += [f"end {namespace}", ""]
    return "\n".join(_wrap_doc(line) for line in out).rstrip() + "\n"


def summary_line(doc: str) -> str:
    return doc.rstrip(".") + "." if doc else "the main result."


def _wrap_doc(line: str) -> str:
    """Docstring lines longer than 100 characters are wrapped (the declaration lines are left to the user)."""
    if len(line) <= MAX_LINE or not line.startswith(("/-- ", "* ")):
        return line
    words, cur, rows = line.split(" "), "", []
    for w in words:
        if cur and len(cur) + 1 + len(w) > MAX_LINE:
            rows.append(cur)
            cur = "  " + w
        else:
            cur = f"{cur} {w}" if cur else w
    rows.append(cur)
    return "\n".join(rows)


def docstring_for(decl_text: str, main: bool, main_full: str = "") -> str:
    """A deterministic English docstring from the statement (to be reread: shown as such in the panel)."""
    if not main:
        return f"Auxiliary lemma for `{main_full}`."
    sig = main_signature(decl_text)
    if sig is None:
        return "The main result."
    hyps = [g["type"] for g in binder_groups(sig[0]) if is_hypothesis(g)]
    concl = sig[1]
    if hyps:
        return "If " + " and ".join(f"`{h}`" for h in hyps) + f", then `{concl}`."
    return f"For all values of the variables, `{concl}`." if binder_groups(sig[0]) else f"`{concl}`."


def pr_texts(*, full: str, path: str, doc: str, lean: str, mathlib: str, closest: str, title: str) -> dict:
    area = path.removeprefix("Mathlib/").rsplit("/", 1)[0]
    pr_title = f"feat({area}): add `{full}`"
    body = (f"This PR adds `{full}`: {doc}\n\n"
            f"It goes in the new file `{path}` (the closest existing file is `{closest}`; reviewers may prefer the "
            "declaration to be moved there).\n\n"
            "---\n\n"
            f"The statement and proof were found with the help of Madalean (AI-assisted theorem proving) and checked "
            f"by Lean {lean} with Mathlib `{mathlib[:40] or 'unknown'}` (no `sorry`, standard axioms only). The "
            "proof may still need golfing to Mathlib's standards.\n")
    fr = (f"Cette demande ajoute à Mathlib le résultat « {title} » sous le nom `{full}`, dans un nouveau fichier "
          f"`{path}`. Les relecteurs de Mathlib vérifieront le nom, la place du résultat (le fichier existant le plus "
          f"proche est `{closest}` : ils peuvent demander de l'y déplacer), la généralité de l'énoncé et la "
          "concision de la preuve. Le texte de la demande est en anglais, comme l'exige Mathlib.")
    en = (f"This request adds the result « {title} » to Mathlib as `{full}`, in a new file `{path}`. Mathlib's "
          f"reviewers will check the name, where the result belongs (the closest existing file is `{closest}`: they "
          "may ask to move it there), how general the statement is and how short the proof is. The request text is "
          "in English, as Mathlib requires.")
    return {"title": pr_title, "body": body, "explain": {"fr": fr, "en": en}}


# ---------------------------------------------------------------- Lean output parsing
def min_imports(messages) -> list[str]:
    out = []
    for m in messages:
        for line in (m.text or "").split("\n"):
            mm = re.match(r"\s*(?:public\s+)?import\s+([\w.]+)\s*$", line)
            if mm:
                out.append(mm.group(1))
    return list(dict.fromkeys(out))


def tactic_modules(body: str) -> list[str]:
    code = leancheck.lean_code_only(body)
    return sorted({mod for tac, mod in TACTIC_MODULES.items()
                   if re.search(r"(?<![\w.])" + re.escape(tac) + r"(?![\w'?])", code)})


def lint_result(messages) -> tuple[bool | None, str]:
    for m in messages:
        if "linting checks passed" in (m.text or "") or re.search(r"Found \d+ errors? in", m.text or ""):
            ok = "All linting checks passed" in m.text
            return ok, "" if ok else m.text[:2000]
    return None, ""


def single_lemma(tactic: str, lemma: str) -> bool:
    """True when `tactic` uses `lemma` and no other named lemma (only hypotheses, variables, `_`, tactics)."""
    code = leancheck.lean_code_only(tactic)
    if not re.search(r"(?<![\w.])" + re.escape(lemma) + r"(?![\w'])", code):
        return False
    code = re.sub(r"(?<![\w.])" + re.escape(lemma) + r"(?![\w'])", " ", code)
    tactics = {"exact", "apply", "simpa", "using", "intros", "intro", "all_goals", "try", "assumption", "norm_num",
               "first", "refine", "fun"}
    others = [t for t in re.findall(r"[A-Za-z_][\w'.]*", code)
              if t not in tactics and ("." in t or re.search(r"[a-z]_[a-z]", t))]
    return not others


# ---------------------------------------------------------------- state
def source_key(kind: str, ident: str) -> str:
    return f"{kind}:{ident}"


def _file(ctx, key: str) -> Path:
    return ctx.paths.config / "research" / "mathlib_contrib" / (hashlib.sha256(key.encode()).hexdigest()[:20] + ".json")


def load(ctx, key: str) -> dict | None:
    try:
        return json.loads(_file(ctx, key).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def save(ctx, pkg: dict) -> None:
    f = _file(ctx, pkg["key"])
    f.parent.mkdir(parents=True, exist_ok=True)
    config.atomic_write_text(f, json.dumps(pkg, ensure_ascii=False, indent=1))


def source_of(ctx, kind: str, ident: str) -> dict:
    """{kind, id, title, workspace, body (header-free code), main, dossier} of a verified result."""
    from ..dossiers import closure, strip_header
    if kind == "library":
        lib = ctx.library
        e = lib.get(ident)
        if e is None:
            raise ContribError("not_found", 404)
        parts = [x.code for x in closure(lib, [e])]
        return {"kind": kind, "id": ident, "title": e.title or e.name, "workspace": e.workspace,
                "body": "\n\n".join(parts), "main": e.name, "dossier": e.dossier}
    if kind == "dossier":
        d = ctx.repo.get(ident)
        if d is None:
            raise ContribError("not_found", 404)
        if not d.proof_is_current:
            raise ContribError("not_verified", 409)
        body = strip_header(d.proof)
        body = re.sub(r"(?m)^#print axioms.*$", "", body).strip()
        try:
            main = leancheck.theorem_name(body)
        except leancheck.StatementError:
            raise ContribError("not_verified", 409)
        return {"kind": kind, "id": ident, "title": d.title or main, "workspace": d.workspace, "body": body,
                "main": main, "dossier": d.id}
    raise ContribError("bad_source", 400)


def new_package(src: dict, author: str) -> dict:
    return {"key": source_key(src["kind"], src["id"]), "state": "running", "t": time.time(),
            "source": {k: src[k] for k in ("kind", "id", "title", "workspace", "main", "dossier")},
            "author": author, "steps": [{"id": s, "state": "pending", "params": {}} for s in STEPS],
            "port": None, "in_mathlib": None, "name": None, "checks": [], "imports": [], "file": None, "pr": None,
            "target": None, "links": LINKS, "error": ""}


# ---------------------------------------------------------------- the preparation
class Preparation:
    """Runs the steps on `ctx.lean` (fresh checks only) and keeps `pkg` up to date (saved after each step)."""

    def __init__(self, ctx, src: dict, author: str, on_change=None):
        self.ctx, self.src, self.on_change = ctx, src, on_change
        self.pkg = new_package(src, author)

    def step(self, sid: str, state: str, **params) -> None:
        for s in self.pkg["steps"]:
            if s["id"] == sid:
                s["state"], s["params"] = state, params
        save(self.ctx, self.pkg)
        if self.on_change:
            self.on_change(self.pkg)

    async def lean(self, code: str, ws, name: str | None = None):
        if name:
            code = leancheck.with_axiom_probe(code, name)
        r = await self.ctx.lean.check(code, ws, CHECK_TIMEOUT, name)
        return r, leancheck.parse_lean_json(r.stdout or "")

    async def run(self) -> dict:
        try:
            await self._run()
        except asyncio.CancelledError:
            self.pkg["state"] = "stopped"
            save(self.ctx, self.pkg)
            raise
        except Exception as e:  # noqa: BLE001 — the panel shows the failure, the log the details
            log.exception("mathlib contribution of %s", self.pkg["key"])
            self.pkg["state"], self.pkg["error"] = "failed", type(e).__name__
            for s in self.pkg["steps"]:
                if s["state"] == "running":
                    s["state"] = "fail"
        save(self.ctx, self.pkg)
        if self.on_change:
            self.on_change(self.pkg)
        return self.pkg

    async def _run(self) -> None:
        ctx, src, pkg = self.ctx, self.src, self.pkg
        tgt = ctx.workspace(TARGET_WS)
        if tgt is None and getattr(ctx, "demo", False):      # the demo has one simulated Lean: nothing to port
            tgt = ctx.workspace(src["workspace"])
        if tgt is None or await ctx.lean.problems(tgt):
            self.step("port", "fail", code="target_missing")
            pkg["state"] = "failed"
            return
        # ---- 1. port to lean-current
        self.step("port", "running")
        body, renames, syntax = src["body"], [], []
        if src["workspace"] != tgt.key:
            table: dict[str, str] = {}
            old = ctx.workspace(src["workspace"])
            if old is not None and not await ctx.lean.problems(old):
                _r, msgs = await self.lean(leancheck.GOEDEL_HEADER + body, old)
                table.update(deprecations(msgs))
            table.update(self._lesson_renames(tgt))
            table.update(BUILTIN_RENAMES)
            body, renames = rename_idents(body, table)
            body, syntax = syntax_port(body)
        main = src["main"]
        r, msgs = await self.lean(HEADER_CURRENT + body, tgt, main)
        dep = deprecations(msgs)
        if dep:                       # lean-current's own deprecations: the new names, then one more fresh check
            body2, more = rename_idents(body, dep)
            r2, msgs2 = await self.lean(HEADER_CURRENT + body2, tgt, main)
            if r2.verdict.ok or not r.verdict.ok:
                body, r, msgs, renames = body2, r2, msgs2, renames + more
        pkg["port"] = {"from": src["workspace"], "to": tgt.key, "renames": renames, "syntax": syntax,
                       "ok": bool(r.verdict.ok), "axioms": r.verdict.axioms,
                       "errors": leancheck.errors_for_feedback(r.code, r.verdict)[:3000] if not r.verdict.ok else "",
                       "lean": self._env(tgt)}
        if not r.verdict.ok:
            self.step("port", "fail", code="port_failed")
            pkg["state"] = "port_failed"
            return
        self.step("port", "ok", renames=len(renames), ported=src["workspace"] != tgt.key)
        decls = split_decls(body)
        main_decl = next((d for d in decls if d.name == main), None)
        if main_decl is None or main_decl is not decls[-1]:
            pkg["state"], pkg["error"] = "failed", "main_not_last"
            return
        # ---- 2. already in Mathlib?
        self.step("mathlib", "running")
        found = await self._in_mathlib(main_decl, tgt, decls)
        pkg["in_mathlib"] = found
        if found and found.get("lemma"):
            self.step("mathlib", "fail", name=found["lemma"])
            pkg["state"] = "in_mathlib"
            return
        self.step("mathlib", "warn" if found else "ok", **({"tactic": found["tactic"]} if found else {}))
        # ---- 3. name
        self.step("name", "running")
        sugg = suggest_name(main_decl.text, src["title"])
        sugg["original"] = main
        pkg["name"] = sugg
        # ---- 4. probe run: is the name free, which imports
        self.step("imports", "running")
        free, mods = await self._probe(decls, main, sugg, tgt)
        sugg["free"] = free
        if free is False:
            sugg["taken"] = sugg["full"]
            sugg["name"] += "_of_madalean" if sugg["fallback"] else "'"
            sugg["full"] = f"{sugg['namespace']}.{sugg['name']}" if sugg["namespace"] else sugg["name"]
        self.step("name", "ok" if free is not False else "warn", full=sugg["full"])
        # ---- 5. the file: smallest variant that a fresh strict Lean accepts
        final = await self._final(decls, main, sugg, mods, tgt)
        if final is None:
            self.step("imports", "fail")
            self.step("final", "fail", code="final_failed")
            pkg["state"] = "failed"
            return
        text, imports, minimal, res = final
        voted = await self._voted_modules(main_decl, tgt)
        pkg["target"] = target_path(voted, sugg["full"], mods)
        pkg["imports"], pkg["file"] = imports, {"path": pkg["target"]["path"], "text": text}
        self.step("imports", "ok" if minimal else "warn", n=len(imports))
        self.step("final", "ok", axioms=res.verdict.axioms)
        # ---- 6. lint (Mathlib's #lint and linter set) and the checklist
        self.step("lint", "running")
        lint_ok, lint_text, linters, deprecated = await self._lint(text, tgt)
        self.step("lint", "ok" if lint_ok else ("warn" if lint_ok is None else "fail"))
        file_decls = split_decls(text[text.find("public section"):])
        checks = [check("lean_current", True, lean=pkg["port"]["lean"].get("lean", ""),
                        mathlib=pkg["port"]["lean"].get("mathlib", "")[:12]),
                  check("not_in_mathlib", True, **({"tactic": found["tactic"]} if found else {})),
                  check("name_free", free is not False if free is not None else None,
                        **({"taken": sugg.get("taken")} if free is False else {}))]
        checks += text_checks(text, file_decls)
        for c in checks:
            if c["id"] == "no_sorry_axioms":
                c["ok"] = c["ok"] and set(res.verdict.axioms or []) <= leancheck.ALLOWED_AXIOMS
                c["params"]["axioms"] = res.verdict.axioms
            if c["id"] == "non_terminal_simp" and any(k == "linter.flexible" for k, _l in linters):
                c["ok"] = False
        checks.append(check("deprecated", not deprecated, names=deprecated))
        checks.append(check("lint", lint_ok, text=lint_text))
        checks.append(check("mathlib_linters", (not linters) if lint_ok is not None else None,
                            items=[{"kind": k, "line": ln} for k, ln in linters[:20]]))
        checks.append(check("imports_minimal", minimal, imports=imports))
        for c in checks:                    # severity follows the final verdict of each check
            c["severity"] = "ok" if c["ok"] else ("unknown" if c["ok"] is None else CHECKS[c["id"]][0])
        pkg["checks"] = checks
        main_doc = docstring_for(main_decl.text, True)
        env = pkg["port"]["lean"]
        pkg["pr"] = pr_texts(full=sugg["full"], path=pkg["target"]["path"], doc=main_doc, lean=env.get("lean", ""),
                             mathlib=env.get("mathlib", ""), closest=pkg["target"]["closest_path"], title=src["title"])
        pkg["state"] = "ready"

    # -- helpers
    def _env(self, ws) -> dict:
        from ..runtime.lean import workspace_info
        try:
            info = workspace_info(ws)
        except Exception:  # noqa: BLE001
            info = {}
        return {"workspace": ws.key, "lean": str(info.get("lean", "")), "mathlib": str(info.get("mathlib", ""))}

    def _lesson_renames(self, tgt) -> dict[str, str]:
        from .lessons import store_of
        try:
            st = store_of(self.ctx)
            return {old: new for old, (new, _lid) in st.renames(self._env(tgt)).items()} if st else {}
        except Exception:  # noqa: BLE001
            return {}

    async def _in_mathlib(self, main: Decl, tgt, decls: list[Decl]) -> dict | None:
        if any(d.kind in ("def", "abbrev", "instance") for d in decls):
            return None                              # the statement uses the result's own definitions
        sig = main_signature(main.text)
        if sig is None:
            return None
        from ..literature.formal import LitIO, _lean_real
        from ..literature.types import Budget
        from ..pipeline.mathlib_first import MathlibFirst
        statement = f"{HEADER_CURRENT}theorem {main.name} {sig[0]} : {sig[1]} := by sorry\n"
        io = LitIO(self.ctx, "local", Budget(seconds=300, lean_checks=10, model_calls=0).start(), owner="mathlib")
        mf = MathlibFirst(io, "local", getattr(self.ctx, "retriever", None), lean_real=_lean_real(self.ctx),
                          use_model=False)
        try:
            res = await mf.run(statement, tgt, [self.src["title"]], 120)
        except Exception as e:  # noqa: BLE001 (no index, budget: not found)
            log.info("mathlib search: %s", e)
            return None
        if not res.ok:
            return None
        single = bool(res.lemma) and single_lemma(res.tactic or res.code.split(":= by", 1)[-1], res.lemma)
        # one Mathlib lemma applied to the hypotheses = already in Mathlib (stop); a short combination of lemmas or
        # automation = a warning only (the result may still be worth contributing)
        return {"lemma": res.lemma if single else "", "tactic": res.tactic, "source": res.source,
                "used": res.lemma}

    async def _probe(self, decls: list[Decl], main: str, sugg: dict, tgt) -> tuple[bool | None, list[str]]:
        """One Lean run: `#check @<proposed name>` (free when unknown) and `#min_imports in` each declaration."""
        parts = [HEADER_CURRENT.rstrip(), "", f"#check @{sugg['full']}", ""]
        for d in decls:
            parts += ["#min_imports in", d.text, ""]
        code = "\n".join(parts) + "\n"
        check_line = code.split("\n").index(f"#check @{sugg['full']}") + 1
        r, msgs = await self.lean(code, tgt)
        free = None
        for m in msgs:
            if m.line == check_line:
                if m.severity == "error" and re.search(r"(?i)unknown (constant|identifier)", m.text):
                    free = True
                elif m.severity == "information":
                    free = False
        return free, min_imports(msgs)

    async def _voted_modules(self, main: Decl, tgt) -> list[str]:
        ret = getattr(self.ctx, "retriever", None)
        if ret is None:
            return []
        try:
            ds = await asyncio.wait_for(ret.premises(tgt.key, HEADER_CURRENT + main.text, 8), 60)
        except Exception:  # noqa: BLE001
            return []
        return [d.get("module", "") for d in ds or [] if d.get("module")]

    async def _final(self, decls: list[Decl], main: str, sugg: dict, mods: list[str], tgt):
        """Variants from the smallest: (namespace, minimal imports, needed opens) … (no namespace, Mathlib, all
        Goedel opens). The first that a fresh strict Lean accepts is the file."""
        body = "\n\n".join(d.text for d in decls)
        minimal = sorted(set(mods) | set(tactic_modules(body)))
        opens = opens_for(body)
        ns = sugg["namespace"]
        variants = []
        if minimal:
            variants.append((ns, minimal, opens, True))
        variants += [(ns, ["Mathlib"], opens, False), ("", ["Mathlib"], ["Real", "Nat", "Topology"], False)]
        author, year = self.pkg["author"], time.gmtime().tm_year
        seen = set()
        for v_ns, imports, v_opens, is_min in variants:
            if (v_ns, tuple(imports), tuple(v_opens)) in seen:
                continue
            seen.add((v_ns, tuple(imports), tuple(v_opens)))
            name = sugg["name"] if v_ns else sugg["full"]
            items = []
            for d in decls:
                text = d.text
                if d.name == main:
                    text = re.sub(rf"^(\s*(?:theorem|lemma)\s+){re.escape(main)}(?=[\s:({{\[⦃])", rf"\g<1>{name}",
                                  text, count=1)
                    if text.lstrip().startswith("lemma"):
                        text = text.replace("lemma", "theorem", 1)
                items.append((d.doc if d.doc and d.name != main else
                              docstring_for(d.text, d.name == main, sugg["full"]), wrap_signature(text)))
            text = build_file(author=author, year=year, title=f"`{sugg['full']}`",
                              summary=f"This file proves `{sugg['full']}`.",
                              imports=imports, opens=v_opens, namespace=v_ns, decls=items, main_full=sugg["full"])
            res, _msgs = await self.lean(text, tgt, sugg["full"])
            if res.verdict.ok:
                return text, imports, is_min, res
        return None

    async def _lint(self, text: str, tgt) -> tuple[bool | None, str, list[tuple[str, int]], list[str]]:
        marker = "public section\n"
        i = text.find(marker)
        if i < 0:
            return None, "", [], []
        extra = "set_option linter.mathlibStandardSet true\nset_option linter.hashCommand false\n"
        code = text[:i + len(marker)] + extra + text[i + len(marker):] + "\n#lint\n"
        r, msgs = await self.lean(code, tgt)
        ok, out = lint_result(msgs)
        shift = extra.count("\n")
        cut = text[:i + len(marker)].count("\n") + 1
        linters = [(m.kind, m.line - shift if m.line > cut else m.line) for m in msgs
                   if m.severity == "warning" and m.kind.startswith("linter.")]
        deprecated = sorted({a for a, _b in DEPRECATED_RE.findall("\n".join(m.text for m in msgs))})
        return ok, out, linters, deprecated


def wrap_signature(text: str) -> str:
    """A declaration whose header (up to `:= by`) has a line over 100 characters is re-flowed at its binder groups,
    continuation lines indented by 4 (Mathlib style); whitespace only, the proof is untouched."""
    m = re.search(r":=\s*by\b|:=", text)
    if not m:
        return text
    head, rest = text[:m.start()], text[m.start():]
    if all(len(line) <= MAX_LINE for line in (head + rest.split("\n", 1)[0]).split("\n")):
        return text
    hm = re.match(r"\s*((?:theorem|lemma)\s+\S+)\s*(.*)$", head, re.S)
    sig = main_signature(text)
    if not hm or sig is None:
        return text
    pieces = [g for g in _group_texts(sig[0])] + [":", sig[1]]
    lines, cur = [], hm.group(1)
    for p in pieces:
        add = (" " if cur.strip() else "") + p
        if len(cur) + len(add) > MAX_LINE and cur.strip():
            lines.append(cur)
            cur = "    " + p
        else:
            cur += add
    first_rest = rest.split("\n", 1)
    cur += " " + first_rest[0].strip()
    lines.append(cur)
    return "\n".join(lines) + ("\n" + first_rest[1] if len(first_rest) > 1 else "")


def _group_texts(binders: str) -> list[str]:
    out, depth, start = [], 0, -1
    for i, ch in enumerate(binders):
        if ch in "([{⦃":
            if depth == 0:
                start = i
            depth += 1
        elif ch in ")]}⦄":
            depth -= 1
            if depth == 0 and start >= 0:
                out.append(binders[start:i + 1])
    return out


# ---------------------------------------------------------------- GitHub (host only, the user's key, two clicks)
def _fork_name(login: str) -> str:
    return f"{login}/{UPSTREAM.split('/')[1]}"


def branch_name(pkg: dict) -> str:
    return "madalean/" + re.sub(r"[^A-Za-z0-9._-]+", "-", pkg["name"]["full"]).strip("-")[:60]


def mathlib_lean_insert(text: str, module: str) -> str:
    """`Mathlib.lean` with `public import <module>` inserted in sorted place (what `lake exe mk_all` would do)."""
    lines = text.split("\n")
    new = f"public import {module}"
    if new in lines:
        return text
    idx = [i for i, l in enumerate(lines) if l.startswith("public import Mathlib.")]
    pos = next((i for i in idx if lines[i] > new), (idx[-1] + 1) if idx else len(lines))
    lines.insert(pos, new)
    return "\n".join(lines)


def plan_branch(pkg: dict, login: str) -> dict:
    """Exactly what « Créer une branche sur mon fork » sends (shown before sending)."""
    fork, branch, path = _fork_name(login), branch_name(pkg), pkg["file"]["path"]
    msg = f"feat: add `{pkg['name']['full']}`"
    return {"id": secrets.token_urlsafe(12), "kind": "branch", "expires": time.time() + PLAN_TTL, "login": login,
            "fork": fork, "branch": branch, "path": path, "module": pkg["target"]["module"], "message": msg,
            "content": pkg["file"]["text"],
            "requests": [
                {"method": "POST", "url": f"/repos/{UPSTREAM}/forks", "body": {"default_branch_only": True}},
                {"method": "GET", "url": f"/repos/{UPSTREAM}/git/ref/heads/{UPSTREAM_BRANCH}"},
                {"method": "POST", "url": f"/repos/{fork}/git/refs", "body": {"ref": f"refs/heads/{branch}",
                                                                              "sha": "<upstream master>"}},
                {"method": "PUT", "url": f"/repos/{fork}/contents/{path}",
                 "body": {"message": msg, "branch": branch, "content": "<the file above, base64>"}},
                {"method": "GET", "url": f"/repos/{fork}/contents/Mathlib.lean?ref={branch}"},
                {"method": "PUT", "url": f"/repos/{fork}/contents/Mathlib.lean",
                 "body": {"message": "chore: add the new file to Mathlib.lean", "branch": branch,
                          "content": f"<Mathlib.lean + « public import {pkg['target']['module']} »>"}},
            ]}


def plan_pr(pkg: dict, login: str) -> dict:
    fork, branch = _fork_name(login), branch_name(pkg)
    body = {"title": pkg["pr"]["title"], "head": f"{login}:{branch}", "base": UPSTREAM_BRANCH,
            "body": pkg["pr"]["body"], "draft": True, "maintainer_can_modify": True}
    return {"id": secrets.token_urlsafe(12), "kind": "pr", "expires": time.time() + PLAN_TTL, "login": login,
            "fork": fork, "branch": branch,
            "requests": [{"method": "POST", "url": f"/repos/{UPSTREAM}/pulls", "body": body}]}


async def github_login(gh) -> str:
    from .publish import gh_failure
    status, data = await gh.call("GET", "/user")
    if status != 200 or not data.get("login"):
        raise gh_failure(gh, status, data, "identity", "")
    return str(data["login"])


async def github_branch(gh, pkg: dict, plan: dict) -> dict:
    """Fork (or reuse the fork), branch from upstream master, commit the file and the Mathlib.lean import."""
    from .publish import gh_failure
    fork, branch = plan["fork"], plan["branch"]
    status, data = await gh.call("POST", f"/repos/{UPSTREAM}/forks", {"default_branch_only": True})
    if status not in (200, 202):
        raise gh_failure(gh, status, data, "fork", "")
    if data.get("full_name") and data["full_name"] != fork:     # not the repository the user was shown: stop
        raise ContribError("github_fork_name", 409, fork=str(data["full_name"])[:200])
    for _ in range(10):                         # a new fork takes a few seconds to exist
        status, _d = await gh.call("GET", f"/repos/{fork}")
        if status == 200:
            break
        await asyncio.sleep(2)
    else:
        raise ContribError("github_fork_pending", 504)
    status, data = await gh.call("GET", f"/repos/{UPSTREAM}/git/ref/heads/{UPSTREAM_BRANCH}")
    sha = ((data or {}).get("object") or {}).get("sha", "")
    if status != 200 or not sha:
        raise gh_failure(gh, status, data, "ref", "")
    status, data = await gh.call("POST", f"/repos/{fork}/git/refs", {"ref": f"refs/heads/{branch}", "sha": sha})
    if status == 422:
        raise ContribError("github_branch_exists", 409, branch=branch)
    if status != 201:
        raise gh_failure(gh, status, data, "branch", "")
    content = base64.b64encode(plan["content"].encode()).decode()
    status, data = await gh.call("PUT", f"/repos/{fork}/contents/{plan['path']}",
                                 {"message": plan["message"], "content": content, "branch": branch})
    if status not in (200, 201):
        raise gh_failure(gh, status, data, "commit", "")
    status, data = await gh.call("GET", f"/repos/{fork}/contents/Mathlib.lean?ref={branch}")
    if status == 200 and data.get("content") and data.get("sha"):
        old = base64.b64decode(data["content"]).decode("utf-8", "replace")
        new = mathlib_lean_insert(old, plan["module"])
        if new != old:
            status, data = await gh.call("PUT", f"/repos/{fork}/contents/Mathlib.lean",
                                         {"message": "chore: add the new file to Mathlib.lean", "branch": branch,
                                          "sha": data["sha"], "content": base64.b64encode(new.encode()).decode()})
            if status not in (200, 201):
                raise gh_failure(gh, status, data, "commit", "")
    return {"fork": fork, "branch": branch, "branch_url": f"https://github.com/{fork}/tree/{branch}",
            "compare_url": f"https://github.com/{UPSTREAM}/compare/{UPSTREAM_BRANCH}...{plan['login']}:{branch}"}


async def github_pr(gh, plan: dict) -> dict:
    from .publish import gh_failure
    req = plan["requests"][0]
    status, data = await gh.call("POST", req["url"], req["body"])
    if status != 201:
        raise gh_failure(gh, status, data, "pr", "")
    return {"number": data.get("number"), "url": data.get("html_url", "")}
