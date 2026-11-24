"""Splitting a target without any model (S-BI, D67): conjunctions, equivalences, case hypotheses. Pure text work: the
pieces AND the combination are only candidates, one Lean compile accepts or refuses them (`gate_code`). What the
syntax does not understand is simply not split here (the reasoned search of D57 may still ask a model)."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .. import leancheck
from . import probes as P

MAX_PARTS = 6
_OPEN, _CLOSE = "([{⦃⟨", ")]}⦄⟩"
_BINDERS = re.compile(r"∀|∃|λ|∑|∏|∫|⋃|⋂|⨆|⨅|(?<![\w.])(?:fun|let|if|match|show|by)(?![\w'])|<\||\$")
_NAME = r"[^\W\d][\w'₀-₉]*"


@dataclass
class Split:
    pattern: str                                       # and | iff | cases
    parts: list[dict] = field(default_factory=list)    # [{name, title, lean}]
    combination: str = ""                              # tactic proof of the target from the parts


def _depth(s: str, pos: int) -> int:
    return sum((c in _OPEN) - (c in _CLOSE) for c in s[:pos])


def strip_parens(s: str) -> str:
    s = s.strip()
    while s.startswith("(") and s.endswith(")"):
        depth = 0
        for i, ch in enumerate(s):
            depth += (ch in _OPEN) - (ch in _CLOSE)
            if depth == 0 and i < len(s) - 1:
                return s
        inner = s[1:-1].strip()
        if not inner.startswith(("∀", "∃")) and any(
                inner[i] == ":" and _depth(inner, i) == 0 for i in range(len(inner))):
            return s                               # a type ascription, not a grouping
        s = inner
    return s


def top_split(s: str, op: str) -> list[str]:
    """`s` cut at every top-level `op`; a binder swallows everything to its right."""
    stop = next((m.start() for m in _BINDERS.finditer(s) if _depth(s, m.start()) == 0), len(s))
    out, depth, start, i = [], 0, 0, 0
    while i < stop:
        depth += (s[i] in _OPEN) - (s[i] in _CLOSE)
        if depth == 0 and s.startswith(op, i):
            out.append(s[start:i].strip())
            start = i = i + len(op)
            continue
        i += 1
    return out + [s[start:].strip()]


def _comma(s: str) -> int:
    return next((i for i, ch in enumerate(s) if ch == "," and _depth(s, i) == 0), -1)


def peel(binders: str, concl: str, names: list[str] | None = None) -> tuple[str, str, list[str]]:
    """Leading ∀ / → of the conclusion moved into the binders. `names`: the names an `intro` gave them (then at most
    that many are peeled). Returns (binders, conclusion, introduced names)."""
    intro: list[str] = []
    b, c = binders, strip_parens(concl)
    while names is None or len(intro) < len(names):
        if c.startswith("∀"):
            j = _comma(c)
            head, rest = (c[1:j].strip(), c[j + 1:].strip()) if j > 0 else ("", "")
            m = re.fullmatch(rf"((?:{_NAME}\s+)*{_NAME})\s*:\s*(.+)", head, re.S)
            if m:
                group = [(x, m.group(2)) for x in m.group(1).split()]
            elif head.startswith("(") and P._balanced_groups(head) and "{" not in head and "[" not in head:
                group = P.explicit_binders(head)
            else:
                break
            if not group or (names is not None and [g[0] for g in group] != names[len(intro):len(intro) + len(group)]):
                break                              # renamed by the model: not followed here
            b = (b + " " + " ".join(f"({x} : {t})" for x, t in group)).strip()
            intro += [x for x, _t in group]
            c = strip_parens(rest)
            continue
        if len(top_split(c, "↔")) > 1:
            break
        parts = top_split(c, "→")
        if len(parts) < 2:
            break
        name = names[len(intro)] if names is not None else f"hs{len(intro) + 1}"
        b = f"{b} ({name} : {parts[0]})".strip()
        intro.append(name)
        c = strip_parens(" → ".join(parts[1:]))
    return b, c, intro


def call_args(binders: str) -> str | None:
    """Arguments that apply a lemma with the same binders; None when one has no usable name."""
    out, depth, start = [], 0, 0
    for i, ch in enumerate(binders):
        if ch in "([{⦃":
            if depth == 0:
                start = i
            depth += 1
        elif ch in ")]}⦄":
            depth -= 1
            inner, kind = binders[start + 1:i], binders[start]
            if depth or kind == "[":
                continue
            if ":=" in inner:
                return None
            for n in inner.split(":", 1)[0].split():
                if not re.fullmatch(_NAME, n) or n == "_":
                    return None
                out.append(n if kind == "(" else f"({n} := {n})")
    return " ".join(out)


def split(statement: str) -> Split | None:
    sig = P.split_statement(statement)
    if sig is None:
        return None
    binders, c, intro = peel(sig.binders, sig.concl)
    ident = re.sub(r"[^A-Za-z0-9_]", "_", sig.name)
    iff = top_split(c, "↔")
    plain = len(iff) == 1 and len(top_split(c, "∨")) == 1 and len(top_split(c, "→")) == 1
    ands = top_split(c, "∧") if plain else [c]
    case = None
    if len(iff) == 2:
        goals, pattern, bs = [f"({iff[0]}) → ({iff[1]})", f"({iff[1]}) → ({iff[0]})"], "iff", [binders] * 2
    elif 2 <= len(ands) <= MAX_PARTS and all(ands):
        goals, pattern, bs = ands, "and", [binders] * len(ands)
    else:
        for h, t in P.explicit_binders(binders):
            alts = top_split(strip_parens(t), "∨")
            if 2 <= len(alts) <= MAX_PARTS and all(alts) and len(top_split(t, "→")) == 1 \
                    and len(top_split(t, "↔")) == 1 and f"({h} : {t})" in binders:
                case = (h, t, alts)
                break
        if case is None:
            return None
        h, t, alts = case
        goals, pattern = [c] * len(alts), "cases"
        bs = [binders.replace(f"({h} : {t})", f"({h} : {a})", 1) for a in alts]
    args = call_args(binders)
    if args is None:
        return None
    names = [f"{ident}_part{k + 1}" for k in range(len(goals))]
    uses = [f"{n} {args}".strip() for n in names]
    comb = [f"intro {' '.join(intro)}"] if intro else []
    if case is not None:
        comb += [f"rcases {case[0]} with {' | '.join([case[0]] * len(goals))}"] + [f"· exact {u}" for u in uses]
    else:
        comb.append("exact ⟨" + ", ".join(uses) + "⟩")
    parts = [{"name": n, "title": " ".join(g.split())[:120], "lean": f"theorem {n} {b} : {g} := by sorry"}
             for n, g, b in zip(names, goals, bs)]
    return Split(pattern, parts, "\n".join(comb))


def target(statement: str, sp: Split) -> str:
    sig = P.split_statement(statement)
    body = "\n".join("  " + ln for ln in sp.combination.split("\n"))
    return f"theorem {sig.name} {sig.binders} : {sig.concl} := by\n{body}\n"


def gate_code(statement: str, sp: Split) -> str:
    """Parts with `sorry`, then the target from them: Lean says whether the cut is right."""
    pre = P.split_statement(statement).preamble.rstrip()
    return pre + "\n\n" + "\n\n".join(p["lean"] for p in sp.parts) + "\n\n" + target(statement, sp)


def combined(statement: str, sp: Split, proofs: dict[str, str]) -> str:
    """The target's proof from the proved parts ({name: declaration}); to be checked strictly like any proof."""
    return "\n\n".join(proofs[p["name"]].strip() for p in sp.parts) + "\n\n" + target(statement, sp)


def looks_large(statement: str) -> bool:
    """Deterministic: many quantifiers / connectives in the conclusion, or a very long one."""
    sig = P.split_statement(statement)
    if sig is None:
        return False
    c = leancheck.remove_comments(sig.concl)
    return len(re.findall(r"[∀∃]", c)) >= 4 or len(re.findall(r"[∧↔→]", c)) >= 4 or len(c) > 300
