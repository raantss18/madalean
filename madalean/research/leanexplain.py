"""« Expliquer » for Lean (session S-AM, DECISIONS D45): the generic explain service (`research/explain.py`, fast
short-text path of docs/BRAIN.md §15) with a Lean-specific prompt, Lean's own goal states and a correction that Lean
checks before it is offered.

- `mode="error"`: what Lean refuses, in plain French, from Lean's messages (positions shown in the code; the goals
  quoted are those Lean printed — « unsolved goals … ⊢ … »), and a corrected file. The correction is compiled by the
  workspace's Lean BEFORE it is shown (warm Lean allowed, D37; a proof is pinned to the dossier's statement and
  judged strictly, axioms included); a refused correction goes back to the model once with Lean's errors, then is
  dropped: a correction Lean refused is never offered. It is labelled « acceptée par Lean (vérification rapide) »,
  never « vérifiée »: applying it creates a new version through the manual-edit path, whose fresh strict check
  decides.
- `mode="lines"`: tactic by tactic, one plain sentence per line, with the goal state AFTER each line when Lean gives
  it: the code is compiled once with `trace_state` inserted after each complete tactic (`instrument`), and Lean's
  information messages at those lines are the goals. The instrumented file is never shown or stored; when the
  insertion could change the meaning (an error at an inserted line), no goal is shown at all — nothing is invented.
  Header lines (`import`, `open`, `set_option`) get fixed glosses, without a model.
- Version-aware: the workspace's Lean / Mathlib versions, the verified syntax card (syntaxcards.py) and the verified
  catalogue constructions relevant to the code (codecat.py) are in the system prompt (Lean 4.9: `Fintype.card`,
  `∑ i in s`; current Mathlib: `Nat.card`, `∑ i ∈ s`)."""
from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass, field

from .. import leancheck, syntaxcards
from ..logs import get
from .explain import ExplainError, MAX_CODE, MAX_LINES, parse_error_answer, parse_lines
from .codegen import fast_complete

log = get("leanexplain")
MODES = ("error", "lines")
PARTS = ("statement", "proof", "block", "")
MAX_FIX_TRIES = 2                 # model answers whose correction Lean judges (the first + one repair)
MAX_GOAL_CHARS = 1500             # one goal state as shown / sent
MAX_GOALS_PROMPT = 6000           # all goal states sent to the model
MAX_INSTRUMENT_LINES = 400

SYSTEM = {
    "fr": "Tu expliques du Lean 4 / Mathlib à un mathématicien qui n'est pas programmeur. Français simple, phrases "
          "courtes ; nomme les tactiques et les résultats de Mathlib entre `…` et dis ce qu'ils font en mathématiques. "
          "Espace de travail : {ws} — Lean {lean}, Mathlib {mathlib}. {note} N'utilise que des noms qui existent dans "
          "cette version.",
    "en": "You explain Lean 4 / Mathlib code to a mathematician who is not a programmer. Plain English, short "
          "sentences; name tactics and Mathlib results in `…` and say what they do mathematically. Workspace: {ws} — "
          "Lean {lean}, Mathlib {mathlib}. {note} Only use names that exist in this version.",
}
VERSION_NOTE = {
    "v4.9": {"fr": "C'est Lean 4.9 avec la Mathlib de mi-2024 (celle de Goedel-Prover) : on y écrit `Fintype.card`, "
                   "`Nat.factors`, `∑ i in s, f i` ; des noms plus récents n'existent pas encore.",
             "en": "This is Lean 4.9 with the mid-2024 Mathlib (Goedel-Prover's): one writes `Fintype.card`, "
                   "`Nat.factors`, `∑ i in s, f i`; more recent names do not exist yet."},
    "default": {"fr": "C'est une Lean et une Mathlib récentes : on y écrit `Nat.card`, `Nat.primeFactorsList`, "
                      "`∑ i ∈ s, f i` ; d'anciens noms (`Nat.factors`, `∑ … in`) sont obsolètes ou supprimés.",
                "en": "This is a recent Lean and Mathlib: one writes `Nat.card`, `Nat.primeFactorsList`, "
                      "`∑ i ∈ s, f i`; older names (`Nat.factors`, `∑ … in`) are deprecated or removed."},
}
WHAT = {"statement": {"fr": "cet énoncé", "en": "this statement"}, "proof": {"fr": "cette preuve", "en": "this proof"},
        "block": {"fr": "ce bloc", "en": "this block"}, "": {"fr": "ce code", "en": "this code"}}
CONSTRAINT = {
    "proof": {"fr": " — garde l'énoncé du théorème EXACTEMENT tel quel (même nom, mêmes hypothèses, même conclusion) : "
                    "seule la preuve change ; jamais `sorry`, `admit` ni `native_decide`",
              "en": " — keep the theorem's statement EXACTLY as is (same name, hypotheses and conclusion): only the "
                    "proof changes; never `sorry`, `admit` or `native_decide`"},
    "statement": {"fr": " — un énoncé fidèle à l'intention, qui se termine par `:= by sorry`",
                  "en": " — a statement faithful to the intent, ending with `:= by sorry`"},
}
TASK_ERROR = {
    "fr": "Lean refuse {what}. Explique l'erreur en 2 à 5 phrases simples : ce que Lean signale, pourquoi (en termes "
          "mathématiques), comment corriger. Les buts que tu cites doivent venir des messages de Lean ci-dessous : "
          "n'en invente aucun. Puis donne le code corrigé COMPLET dans un seul bloc ```lean{constraint}. Rien après "
          "le bloc.\n\nCode :\n```lean\n{code}\n```\n\nMessages de Lean (<error>…</error> marque l'endroit) :\n{errors}",
    "en": "Lean refuses {what}. Explain the error in 2 to 5 plain sentences: what Lean reports, why (mathematically), "
          "how to fix it. Any goal you quote must come from Lean's messages below: invent none. Then give the COMPLETE "
          "corrected code in one ```lean block{constraint}. Nothing after the block.\n\nCode:\n```lean\n{code}\n```"
          "\n\nLean's messages (<error>…</error> marks the place):\n{errors}",
}
TASK_REPAIR = {
    "fr": "Lean refuse aussi ta correction :\n{errors}\nDonne de nouveau le code corrigé COMPLET dans un seul bloc "
          "```lean{constraint}. Rien d'autre.",
    "en": "Lean also refuses your correction:\n{errors}\nGive the COMPLETE corrected code again in one ```lean block"
          "{constraint}. Nothing else.",
}
TASK_LINES = {
    "fr": "Explique ce code Lean ligne par ligne, tactique par tactique. Pour chaque ligne numérotée, écris exactement "
          "une ligne « N: explication » (N = le numéro donné) : ce que fait la ligne, en français simple, et l'idée "
          "mathématique (pour une tactique : ce qu'elle change au but ; pour un résultat de Mathlib : ce qu'il dit). "
          "{goals_rule} Rien d'autre.\n\n{numbered}{goals}",
    "en": "Explain this Lean code line by line, tactic by tactic. For each numbered line write exactly one line « N: "
          "explanation » (N = the given number): what the line does, in plain words, and the mathematical idea (for a "
          "tactic: how it changes the goal; for a Mathlib result: what it says). {goals_rule} Nothing else.\n\n"
          "{numbered}{goals}",
}
GOALS_RULE = {
    True: {"fr": "Les états du but ci-dessous viennent de Lean : appuie-toi dessus pour dire ce qui reste à prouver.",
           "en": "The goal states below come from Lean: use them to say what remains to be proved."},
    False: {"fr": "Lean n'a pas donné l'état du but : ne décris aucun but précis que tu ne vois pas dans le code.",
            "en": "Lean gave no goal state: do not describe any precise goal you cannot see in the code."},
}
GOALS_HEAD = {"fr": "\n\nÉtats du but donnés par Lean (après la ligne N) :\n",
              "en": "\n\nGoal states given by Lean (after line N):\n"}
HEADER_GLOSS = [
    (re.compile(r"^\s*import\s+Mathlib\s*$"), {"fr": "Charge Mathlib, la bibliothèque mathématique de Lean.",
                                              "en": "Loads Mathlib, Lean's mathematical library."}),
    (re.compile(r"^\s*import\s+Aesop\s*$"), {"fr": "Charge Aesop, une tactique qui cherche des preuves simples.",
                                            "en": "Loads Aesop, a tactic that searches for simple proofs."}),
    (re.compile(r"^\s*import\s+(\S+)"), {"fr": "Charge le module {0}.", "en": "Loads the module {0}."}),
    (re.compile(r"^\s*set_option\s+maxHeartbeats\s+(\d+)"),
     {"fr": "Donne plus de temps de calcul à Lean (limite de {0} unités).",
      "en": "Gives Lean more computing time (limit of {0} units)."}),
    (re.compile(r"^\s*open\s+(.+?)\s*$"),
     {"fr": "Ouvre les espaces de noms {0} : on écrit par exemple `sqrt` au lieu de `Real.sqrt`.",
      "en": "Opens the namespaces {0}: one writes e.g. `sqrt` instead of `Real.sqrt`."}),
]


def header_gloss(line: str, lang: str) -> str | None:
    for rx, txt in HEADER_GLOSS:
        m = rx.match(line)
        if m:
            return txt[lang].format(*m.groups())
    return None


# ---------------------------------------------------------------- context: workspace and versions
@dataclass
class Ctx:
    """What the explanation knows of where the code lives."""
    part: str = ""                # statement | proof | block | ''
    statement: str = ""           # the dossier's statement (a proof correction is pinned to it)
    ws: object = None             # madalean.workspaces.Workspace, None when Lean is not available
    header_offset: int = 0        # lines prepended before compiling (a note's block without imports)
    header: str = ""
    info: dict = field(default_factory=dict)   # {workspace, lean, mathlib}


def version_info(ws) -> dict:
    from ..runtime.lean import workspace_info
    try:
        return workspace_info(ws) if ws is not None else {}
    except Exception:  # noqa: BLE001
        return {}


def system_prompt(c: Ctx, lang: str, code: str) -> str:
    from . import codecat
    flavor = codecat.lean_flavor(getattr(c.ws, "toolchain", "")) if c.ws is not None else "default"
    info = c.info or {}
    note = VERSION_NOTE[flavor][lang] if c.ws is not None else ""
    s = SYSTEM[lang].format(ws=info.get("workspace") or "?", lean=info.get("lean") or "?",
                            mathlib=(info.get("mathlib") or "?").split(" @ ")[0], note=note)
    if c.ws is not None:
        try:
            card = syntaxcards.lean_card(c.ws)
        except Exception:  # noqa: BLE001
            card = ""
        if card:
            s += "\n\n" + card
        try:
            block, _ids = codecat.lean_prompt_block(c.ws, code, budget=200, lang=lang)
        except Exception:  # noqa: BLE001
            block = ""
        if block:
            s += "\n\n" + block
    return s


# ---------------------------------------------------------------- goal states: trace_state after each tactic
_OPENS = re.compile(r"(?:\bby|=>|\bdo)\s*$")
_CONTINUES = re.compile(r"(?:,|\(|\[|⟨|\{|<;>|\bfun|←|\||\bthen|\belse|\bwith|\bat|\busing|:=|[+\-*/^=<>≤≥≠∧∨→↔·∘∣%]|"
                        r"\\|\bfrom)\s*$")
_CONT_START = re.compile(r"^\s*(?:_(?:\s|$)|\||<;>|\)|\]|⟩|\}|\bat\b|\bwith\b|\busing\b|\belse\b|\bthen\b|\.\.|"
                         r"[+\-*/^=<>≤≥≠∧∨→↔∘])")
_DECL = re.compile(r"^\s*(?:@\[[^\]]*\]\s*)?(?:private\s+|protected\s+|noncomputable\s+)*(?:theorem|lemma|example|"
                   r"def|instance|abbrev)\b")


def _code_part(line: str) -> str:
    """The line without its `--` comment (strings are rare in proofs; a `--` inside one only hides a few goals)."""
    i = line.find("--")
    return line if i < 0 else line[:i]


@dataclass
class _Tac:
    start: int
    level: int
    end: int
    bullet: bool = False


def instrument(code: str) -> tuple[str, dict[int, int]] | None:
    """(code with `trace_state` after each complete tactic, {inserted line (1-based) → original line (1-based)}), or
    None when there is no tactic block. A `trace_state` is a no-op that makes Lean print the goals at that point; it
    is inserted only at a tactic level (after a line ending with `by` / `=>`, or a bullet), after the whole tactic
    (its continuation lines and nested blocks), never before a line that continues it (`_ …` calc steps, `| …`
    alternatives, `<;>`, closing brackets). The first tactic of a declaration's block also gets one before it (the
    goal to prove, mapped to the declaration's line)."""
    lines = code.split("\n")
    if len(lines) > MAX_INSTRUMENT_LINES:
        return None
    sig = [(j, len(l) - len(l.lstrip(" ")), _code_part(l)) for j, l in enumerate(lines)
           if _code_part(l).strip() and not l.lstrip().startswith(("/-", "-/"))]
    stack: list[list] = []           # [level, current _Tac | None]
    done: list[_Tac] = []
    starts: list[tuple[int, int, int]] = []      # (first tactic line, level, declaration line): the goal to prove
    pending: tuple[int, int, bool] | None = None   # (opener line, indent a block must exceed, top-level block)
    decl = (0, 0)                                  # (line, indent) of the last top-level declaration
    for j, ind, s in sig:
        st = s.strip()
        if pending is not None and ind > pending[1]:
            if pending[2]:
                starts.append((j, ind, decl[0]))
            stack.append([ind, None])
        else:
            while stack and ind < stack[-1][0]:
                lv = stack.pop()
                if lv[1] is not None:
                    done.append(lv[1])
        pending = None
        if not stack and _DECL.match(s):
            decl = (j, ind)
        if stack and ind == stack[-1][0] and not _CONT_START.match(st):
            if stack[-1][1] is not None:
                done.append(stack[-1][1])
            stack[-1][1] = _Tac(j, ind, j, st.startswith("·"))
        for lv in stack:                        # every enclosing tactic spans this line
            if lv[1] is not None:
                lv[1].end = j
        if _OPENS.search(s.rstrip()) or (st.startswith("·") and stack and ind == stack[-1][0]):
            # a top-level `by` (the declaration's proof, maybe after a multi-line signature) opens a block deeper
            # than the declaration; a nested one, deeper than its own line
            pending = (j, decl[1], True) if not stack else (j, ind, False)
    for lv in reversed(stack):
        if lv[1] is not None:
            done.append(lv[1])
    if not done:
        return None
    nxt = {a[0]: (b[0] if b else None) for a, b in zip(sig, sig[1:] + [None])}
    text_of = {j: s for j, _i, s in sig}
    after: dict[int, list[tuple[int, int]]] = {}   # original line (0-based) → [(level, mapped line)] to insert after
    for t in done:
        if text_of[t.start].strip().startswith("|"):
            continue
        last = text_of[t.end].rstrip()
        if _CONTINUES.search(last) or _OPENS.search(last):
            continue
        k = nxt.get(t.end)
        if k is not None and _CONT_START.match(text_of[k]):
            continue
        if k is not None and len(lines[k]) - len(lines[k].lstrip(" ")) > t.level:
            continue                                  # the next line continues it (deeper, not a block)
        after.setdefault(t.end, []).append((t.level, t.start))
    before = {j: (lv, d) for j, lv, d in starts}
    out: list[str] = []
    mapping: dict[int, int] = {}
    for j, line in enumerate(lines):
        if j in before:
            lv, d = before[j]
            out.append(" " * lv + "trace_state")
            mapping[len(out)] = d + 1
        out.append(line)
        for lv, start in sorted(after.get(j, []), reverse=True):     # innermost first
            out.append(" " * lv + "trace_state")
            mapping[len(out)] = start + 1
    if not mapping:
        return None
    return "\n".join(out), mapping


def statement_probe(code: str) -> tuple[str, dict[int, int]] | None:
    """A statement ending with `:= by sorry` on one line: the goal Lean must prove, mapped to the theorem's line."""
    lines = code.rstrip("\n").split("\n")
    for j in range(len(lines) - 1, -1, -1):
        m = re.search(r":=\s*by\s+sorry\s*$", _code_part(lines[j]))
        if m:
            decl = next((i for i in range(j, -1, -1) if _DECL.match(lines[i])), j)
            ind = len(lines[decl]) - len(lines[decl].lstrip(" "))
            head = lines[j][:m.start()] + ":= by"
            new = lines[:j] + [head, " " * (ind + 2) + "trace_state", " " * (ind + 2) + "sorry"] + lines[j + 1:]
            return "\n".join(new), {j + 2: decl + 1}
    return None


def goals_from(stdout: str, mapping: dict[int, int], offset: int = 0) -> dict[int, str] | None:
    """{original line → goal state after it} from the instrumented compilation's messages; None when an error sits on
    an inserted line (the insertion may have changed the meaning: no goal is shown at all). `offset`: lines that were
    prepended before compiling (removed from the returned line numbers)."""
    msgs = leancheck.parse_lean_json(stdout or "")
    inserted = {ln + offset for ln in mapping}
    if any(m.severity == "error" and m.line in inserted for m in msgs):
        return None
    out: dict[int, str] = {}
    for m in msgs:
        if m.severity in ("information", "info") and m.line in inserted:
            g = (m.text or "").strip()
            g = g if g else "no goals"
            out[mapping[m.line - offset]] = g[:MAX_GOAL_CHARS]
    return out


def goals_prompt(goals: dict[int, str], lang: str) -> str:
    if not goals:
        return ""
    parts, used = [], 0
    for n in sorted(goals):
        g = goals[n]
        g = ("(aucun but : cette branche est terminée)" if lang == "fr" else "(no goals: this branch is done)") \
            if g == "no goals" else g
        piece = f"{n}:\n{g}\n"
        if used + len(piece) > MAX_GOALS_PROMPT:
            break
        parts.append(piece)
        used += len(piece)
    return GOALS_HEAD[lang] + "\n".join(parts)


# ---------------------------------------------------------------- prompts
def numbered(code: str, lang: str) -> tuple[str, dict[int, str]]:
    """(numbered lines for the model, {line → fixed gloss} for header lines)."""
    fixed, rows = {}, []
    for i, l in enumerate(code.split("\n")[:MAX_LINES]):
        if not l.strip():
            continue
        g = header_gloss(l, lang)
        if g is not None:
            fixed[i + 1] = g
            continue
        rows.append(f"{i + 1}: {l}")
    return "\n".join(rows), fixed


def errors_text(code: str, errors: list[dict], raw: str = "") -> str:
    """Lean's messages in Goedel's format (code around each error, `<error>` marks); `raw` when no position."""
    if errors:
        conv = [{"pos": {"line": int(e.get("line") or 1), "column": int(e.get("col") or 0)},
                 "endPos": ({"line": int(e["end_line"]), "column": int(e.get("end_col") or 0)}
                            if e.get("end_line") else None),
                 "data": str(e.get("text") or "")} for e in errors if (e.get("severity") or "error") == "error"]
        if conv:
            return leancheck.get_error_str(code, conv)[:6000]
    return (raw or "").strip()[-3000:]


def error_messages(c: Ctx, code: str, errs: str, lang: str) -> list[dict]:
    return [{"role": "system", "content": system_prompt(c, lang, code)},
            {"role": "user", "content": TASK_ERROR[lang].format(
                what=WHAT[c.part][lang], constraint=CONSTRAINT.get(c.part, {}).get(lang, ""), code=code,
                errors=errs or "-")}]


def lines_messages(c: Ctx, code: str, goals: dict[int, str], lang: str) -> tuple[list[dict], dict[int, str]]:
    rows, fixed = numbered(code, lang)
    user = TASK_LINES[lang].format(goals_rule=GOALS_RULE[bool(goals)][lang], numbered=rows,
                                   goals=goals_prompt(goals, lang))
    return [{"role": "system", "content": system_prompt(c, lang, code)}, {"role": "user", "content": user}], fixed


def check_args(mode: str, code: str, part: str) -> None:
    if mode not in MODES:
        raise ExplainError("bad_mode")
    if part not in PARTS:
        raise ExplainError("bad_part")
    if not code.strip() or len(code) > MAX_CODE:
        raise ExplainError("bad_code")


# ---------------------------------------------------------------- Lean checks of the context
def compile_unit(c: Ctx, code: str) -> tuple[str, str | None]:
    """(file to compile, strict theorem name or None) for `code` in its context (a proof is pinned to the dossier's
    statement and judged strictly; a note's block gets the header it is checked with)."""
    if c.part == "proof":
        st = c.statement or code
        assembled = leancheck.assemble_proof(st, code)
        name = leancheck.theorem_name(st)
        return leancheck.with_axiom_probe(assembled, name), name
    if c.part == "statement":
        return leancheck.prepare_statement(code), None
    return c.header + code, None


def accepted(c: Ctx, r, original: str, fix: str) -> bool:
    """Lean's verdict on a correction, by the rule of its place: a proof — strict (no error, no sorry, standard
    axioms); a statement — no error; a block — no error, and no `sorry` unless the original had one."""
    v = r.verdict
    if r.timed_out or r.infra_error:
        return False
    if c.part == "proof":
        return bool(v.ok)
    if v.errors:
        return False
    if c.part == "statement":
        return True
    if leancheck.exec_risks(fix):
        return False
    return not (v.has_sorry and not re.search(r"\bsorry\b", leancheck.remove_comments(original)))


async def explain_error(ctx, c: Ctx, *, code: str, errors: list[dict], raw_error: str, lang: str, owner: str,
                        on_text=None, on_state=None, check=None) -> dict:
    """{explanation, fix, fix_status: accepted | rejected | none | unchecked, fix_check, fix_tries, model}.
    `check(code_to_compile, strict_name) -> CompileResult` compiles in the context's workspace (None: no Lean)."""
    errs = errors_text(code, errors, raw_error)
    msgs = error_messages(c, code, errs, lang)
    buf: list[str] = []

    def on_chunk(ch) -> None:
        if ch.kind == "info" and (ch.data or {}).get("event") == "restart":
            buf.clear()
            return
        if ch.kind == "text" and ch.text:
            buf.append(ch.text)
            if on_text is not None:
                on_text(parse_error_answer("".join(buf))[0])
    r = await fast_complete(ctx, msgs, owner, on_chunk, 3000)
    model = getattr(r.model, "key", "") or ""
    expl, fix = parse_error_answer(r.text)
    out = {"explanation": expl, "fix": "", "fix_status": "none", "fix_check": None, "fix_tries": 0, "model": model}
    tries = 0
    while fix.strip() and fix.strip() != code.strip():
        if check is None:
            out["fix_status"] = "unchecked"           # never offered: nothing could check it
            return out
        tries += 1
        out["fix_tries"] = tries
        if on_state is not None:
            on_state("checking")
        try:
            unit, name = compile_unit(c, fix)
            res = await check(unit, name)
            ok = accepted(c, res, code, fix)
            fb = "" if ok else leancheck.errors_for_feedback(res.code, res.verdict)
            summary = res.verdict.summary
        except leancheck.StatementError as e:
            ok, fb, summary, res = False, str(e), str(e), None
        if ok:
            out.update(fix=fix, fix_status="accepted", fix_check={"summary": summary, "via": res.via,
                                                                    "seconds": round(res.seconds, 1)})
            return out
        out["fix_status"] = "rejected"
        out["fix_check"] = {"summary": summary}
        if tries >= MAX_FIX_TRIES:
            break
        if on_state is not None:
            on_state("repairing")
        msgs = msgs + [{"role": "assistant", "content": r.text},
                       {"role": "user", "content": TASK_REPAIR[lang].format(
                           errors=fb[:3000] or summary, constraint=CONSTRAINT.get(c.part, {}).get(lang, ""))}]
        r = await fast_complete(ctx, msgs, owner, None, 3000)
        fix = parse_error_answer(r.text)[1] or ""
    return out


async def explain_lines(ctx, c: Ctx, *, code: str, lang: str, owner: str, goals_task=None,
                        goal_wait: float = 4.0) -> dict:
    """{lines: [{line, code, text, goal}], goals: 'lean' | 'none', model}. `goals_task`: an asyncio task computing the
    goal states (`goals_from`); the model waits for it at most `goal_wait` s (latency first) — goals that arrive later
    are still attached to the lines, only the prompt goes without them."""
    goals: dict[int, str] | None = None
    if goals_task is not None:
        try:
            goals = await asyncio.wait_for(asyncio.shield(goals_task), goal_wait)
        except asyncio.TimeoutError:
            goals = None
        except Exception:  # noqa: BLE001
            goals = None
    msgs, fixed = lines_messages(c, code, goals or {}, lang)
    r = await fast_complete(ctx, msgs, owner, None, 3000)
    rows = parse_lines(r.text, code)
    if goals is None and goals_task is not None:
        try:
            goals = await asyncio.wait_for(goals_task, 120)
        except Exception:  # noqa: BLE001
            goals = None
    for row in rows:
        if row["line"] in fixed:
            row["text"] = fixed[row["line"]]
        row["goal"] = (goals or {}).get(row["line"])
    return {"lines": rows, "goals": "lean" if goals else "none", "model": getattr(r.model, "key", "") or ""}
