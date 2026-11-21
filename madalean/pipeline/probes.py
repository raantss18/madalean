"""Many small Lean attempts in ONE compilation (S-K): statement checks and the Mathlib-first search.

A statement `theorem n BINDERS : CONCL := by sorry` is split into its binders and conclusion; each probe is a
separate declaration (`set_option maxHeartbeats … in theorem probe_k …`) so that a failing probe never hides another
one. Lean's messages are mapped back to the probes by line. Nothing found here is trusted on its own: a probe that
closes its goal is compiled again, alone, with the strict verdict (`#print axioms`, forbidden constructs, D28 gate)
before it is reported."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .. import leancheck

PROBE_HEARTBEATS = 20000          # ≈ 1–2 s of elaboration per probe on this machine
TRY_THIS = re.compile(r"Try this:\s*(.+)", re.S)


@dataclass
class Sig:
    preamble: str                 # header + everything before the target theorem (library lemmas, defs)
    name: str
    binders: str                  # "(a b : ℕ) (ha : Even a)" (may be empty)
    concl: str                    # "Even (a + b)"

    def negation(self) -> str:
        """The proposition « the statement is false », as Lean text: ¬ (∀ BINDERS, CONCL)."""
        return f"¬ (∀ {self.binders}, {self.concl})" if self.binders.strip() else f"¬ ({self.concl})"


def split_statement(statement: str) -> Sig | None:
    """Binders and conclusion of the target (= last) theorem; None when the shape is not understood."""
    try:
        st = leancheck.prepare_statement(statement)
    except leancheck.StatementError:
        return None
    code = leancheck.remove_comments(st)
    starts = [m.start(1) for m in re.finditer(r"(?:^|\s)(theorem)\s", code)]
    if not starts:
        return None
    tail = code[starts[-1]:]
    m = re.match(r"theorem\s+([^\s:({\[⦃]+)(.*?):=\s*by\s*sorry\s*$", tail, re.S)
    if not m:
        return None
    name, sig = m.group(1), m.group(2)
    depth, cut = 0, -1
    for i, ch in enumerate(sig):            # the FIRST top-level ':' ends the binders (∀ x : T in the goal is later)
        if ch in "([{⦃⟨":
            depth += 1
        elif ch in ")]}⦄⟩":
            depth = max(0, depth - 1)
        elif ch == ":" and depth == 0 and not sig.startswith(":=", i):
            cut = i
            break
    if cut < 0:
        return None
    binders, concl = sig[:cut].strip(), sig[cut + 1:].strip()
    if not concl or not _balanced_groups(binders):     # only bracketed binders before the colon
        return None
    return Sig(code[:starts[-1]].rstrip() + "\n", name, " ".join(binders.split()), concl)


def _balanced_groups(binders: str) -> bool:
    depth = 0
    for ch in binders:
        if ch in "([{⦃":
            depth += 1
        elif ch in ")]}⦄":
            depth -= 1
            if depth < 0:
                return False
        elif depth == 0 and not ch.isspace():
            return False
    return depth == 0


def explicit_binders(binders: str) -> list[tuple[str, str]]:
    """[(name, type)] of the `(x y : T)` and `{x : T}` binders (top level only; named arguments `h (x := v)` work
    for both). Type binders (`{α : Type*}`) are returned too but get no degenerate value."""
    out: list[tuple[str, str]] = []
    depth, start = 0, -1
    for i, ch in enumerate(binders):
        if ch in "([{⦃":
            if depth == 0 and ch in "({":
                start = i
            depth += 1
        elif ch in ")]}⦄":
            depth -= 1
            if depth == 0 and start >= 0 and ch in ")}":
                inner = binders[start + 1:i]
                if ":" in inner:
                    names, typ = inner.split(":", 1)
                    for n in names.split():
                        if re.fullmatch(r"[^\W\d][\w'₀-₉]*", n):
                            out.append((n, typ.strip()))
                start = -1
    return out


def degenerate_value(typ: str) -> list[str]:
    """Values worth trying for a binder of type `typ` when looking for a degenerate counterexample."""
    t = typ.strip()
    if re.match(r"(Set|Finset)\b", t):
        return ["∅"]
    if t in ("ℕ", "ℤ", "ℚ", "ℝ", "ℂ", "Nat", "Int", "Rat", "Real", "Complex"):
        return ["0", "1"]
    if "→" in t and not t.startswith(("∀", "(")):
        return ["fun _ => 0"]
    return []


@dataclass
class Probe:
    name: str
    code: str                     # the full declaration (with its `set_option … in` lines)
    kind: str = ""                # neg | cex | pos | mathlib | exact? …
    meta: dict = field(default_factory=dict)
    ok: bool = False              # closed its goal in the batch (still to be re-checked strictly)
    errors: list[str] = field(default_factory=list)
    suggestion: str = ""          # `exact?`: the « Try this » tactic


def decl(name: str, head: str, tactic: str, heartbeats: int = PROBE_HEARTBEATS) -> str:
    """`head` = "BINDERS : CONCL" (or ": PROP"); tactic lines are indented under `by`."""
    body = "\n".join("  " + line for line in tactic.strip().split("\n"))
    return (f"set_option autoImplicit false in\nset_option maxHeartbeats {heartbeats} in\n"
            f"theorem {name} {head} := by\n{body}\n")


def batch_file(preamble: str, probes: list[Probe]) -> tuple[str, list[tuple[Probe, int, int]]]:
    lines = preamble.rstrip("\n").split("\n") + [""]
    spans = []
    for p in probes:
        start = len(lines) + 1
        block = p.code.rstrip("\n").split("\n")
        lines += block + [""]
        spans.append((p, start, start + len(block) - 1))
    return "\n".join(lines) + "\n", spans


def read_batch(stdout: str, spans: list[tuple[Probe, int, int]], timed_out: bool = False) -> None:
    """Mark each probe ok / failed from Lean's messages (by line)."""
    msgs = leancheck.parse_lean_json(stdout)
    for p, a, b in spans:
        mine = [m for m in msgs if a <= m.line <= b]
        errs = [m.text for m in mine if m.severity == "error"]
        sorry = any(m.kind == "hasSorry" or leancheck.SORRY_RE.search(m.text) for m in mine)
        p.errors = errs
        for m in mine:
            mm = TRY_THIS.search(m.text) if m.severity != "error" else None
            if mm and not p.suggestion:
                p.suggestion = mm.group(1).strip().split("\n")[0].strip()
        # a timed-out batch leaves the last probes unreported: never count silence as success
        p.ok = not errs and not sorry and not timed_out
    if timed_out:
        last = max((m.line for m in msgs), default=0)
        for p, a, b in spans:
            if b < last:
                mine = [m for m in msgs if a <= m.line <= b]
                p.ok = not any(m.severity == "error" for m in mine) and not any(
                    leancheck.SORRY_RE.search(m.text) for m in mine)


async def run_batch(io, ws, preamble: str, probes: list[Probe], timeout_s: int) -> float:
    """Compile all probes in one file; returns the seconds spent. Probes are updated in place."""
    if not probes:
        return 0.0
    code, spans = batch_file(preamble, probes)
    r = await io.check(code, ws, timeout_s, None)
    if r.infra_error and not r.verdict.errors:
        for p in probes:
            p.ok, p.errors = False, [r.infra_error[:300]]
        return r.seconds
    if r.verdict.reasons and not r.stdout:            # refused before compilation (D28)
        for p in probes:
            p.ok, p.errors = False, list(r.verdict.reasons)
        return r.seconds
    read_batch(r.stdout, spans, r.timed_out)
    return r.seconds


async def strict(io, ws, preamble: str, p: Probe, timeout_s: int):
    """Re-check one probe alone with the strict verdict. Returns the CompileResult."""
    code = preamble.rstrip("\n") + "\n\n" + p.code.rstrip("\n") + "\n"
    return await io.check(leancheck.with_axiom_probe(code, p.name), ws, timeout_s, p.name)
