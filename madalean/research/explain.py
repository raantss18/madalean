"""« Expliquer » on demand (session S-AB): plain-language explanations of code for a mathematician — generic over the
language (`sage`, `python`, `lean`) so the Lean proofs screen can reuse it (HTTP: `POST /api/code/explain`).

- `mode="error"`: what went wrong, in plain words (no jargon), and a proposed fix — a SUGGESTION: the caller shows it
  and the user applies it explicitly; applied model code still needs the usual approval before it runs.
- `mode="lines"`: one short explanation per line of code (shown next to / under each line).

Fast code role (research/codegen.py: `classify.task("transcribe")`, no job slot) and the syntax card of the installed
version (syntaxcards.py: Sage card / Lean+Mathlib card) in the system prompt."""
from __future__ import annotations

import asyncio
import re

from .. import syntaxcards
from .calcul import extract_code
from .codegen import fast_complete, validate

LANGS = {"sage": "SageMath", "python": "Python 3", "lean": "Lean 4 / Mathlib"}
TAGS = {"sage": "sage", "python": "python", "lean": "lean"}
MAX_CODE = 20000
MAX_LINES = 200

SYSTEM = {
    "fr": "Tu expliques du code {name} à un mathématicien qui n'est pas programmeur. Français simple, phrases "
          "courtes, aucun jargon informatique (pas de « stack trace », « exception », « parser ») : dis ce que "
          "fait le calcul et, pour une erreur, ce qui ne va pas et comment le corriger.",
    "en": "You explain {name} code to a mathematician who is not a programmer. Plain English, short sentences, no "
          "programming jargon (no « stack trace », « exception », « parser »): say what the computation does and, "
          "for an error, what is wrong and how to fix it.",
}
TASK_ERROR = {
    "fr": "Cette cellule a échoué. Explique l'erreur en 2 à 5 phrases (ce qui ne va pas, pourquoi), puis donne la "
          "cellule corrigée COMPLÈTE dans un seul bloc ```{tag} (même intention). Rien après le bloc.\n\n"
          "Code :\n```{tag}\n{code}\n```\n\nErreur :\n{error}",
    "en": "This cell failed. Explain the error in 2 to 5 sentences (what is wrong, why), then give the COMPLETE "
          "corrected cell in one ```{tag} block (same intent). Nothing after the block.\n\n"
          "Code:\n```{tag}\n{code}\n```\n\nError:\n{error}",
}
TASK_LINES = {
    "fr": "Explique ce code ligne par ligne. Pour chaque ligne numérotée non vide, écris exactement une ligne "
          "« N: explication » (N = le numéro donné, une phrase courte en français). Rien d'autre.\n\n{numbered}",
    "en": "Explain this code line by line. For each numbered non-empty line, write exactly one line « N: "
          "explanation » (N = the given number, one short sentence). Nothing else.\n\n{numbered}",
}
_LINE = re.compile(r"^\s*(?:L(?:igne|ine)?\s*)?(\d{1,4})\s*[:|.)\-–]\s*(.+?)\s*$", re.I)


class ExplainError(ValueError):
    pass


def card_for(language: str, ctx=None) -> str:
    if language == "sage":
        return syntaxcards.sage_card()[0]
    if language == "lean" and ctx is not None:
        try:
            return syntaxcards.lean_card(ctx.workspace())
        except Exception:  # noqa: BLE001
            return ""
    return ""


def messages(language: str, code: str, error: str, mode: str, lang: str, card: str) -> list[dict]:
    if language not in LANGS:
        raise ExplainError("bad_language")
    if mode not in ("error", "lines"):
        raise ExplainError("bad_mode")
    if not code.strip() or len(code) > MAX_CODE:
        raise ExplainError("bad_code")
    lang = lang if lang in SYSTEM else "en"
    system = SYSTEM[lang].format(name=LANGS[language]) + (f"\n\n{card}" if card else "")
    if mode == "error":
        if not error.strip():
            raise ExplainError("no_error")
        user = TASK_ERROR[lang].format(tag=TAGS[language], code=code, error=error[-3000:])
    else:
        lines = code.split("\n")[:MAX_LINES]
        user = TASK_LINES[lang].format(numbered="\n".join(f"{i + 1}: {l}" for i, l in enumerate(lines)))
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def parse_error_answer(text: str) -> tuple[str, str]:
    """(explanation, proposed code or '')."""
    m = re.search(r"```", text or "")
    expl = (text[:m.start()] if m else text or "").strip()
    return expl, extract_code(text or "")


def parse_lines(text: str, code: str) -> list[dict]:
    """[{line, code, text}] for every line of `code` (text '' where the model said nothing)."""
    got: dict[int, str] = {}
    for raw in (text or "").splitlines():
        m = _LINE.match(raw)
        if m:
            n = int(m.group(1))
            got.setdefault(n, m.group(2).strip())
    out = []
    for i, l in enumerate(code.split("\n")[:MAX_LINES]):
        out.append({"line": i + 1, "code": l, "text": got.get(i + 1, "") if l.strip() else ""})
    return out


async def explain(ctx, *, language: str, code: str, error: str = "", mode: str = "error", lang: str = "fr",
                  owner: str = "explain") -> dict:
    """→ mode error: {explanation, fix, fix_valid, model}; mode lines: {lines: [{line, code, text}], model}."""
    card = await asyncio.to_thread(card_for, language, ctx)
    msgs = messages(language, code, error, mode, lang, card)
    r = await fast_complete(ctx, msgs, owner, None, 2500)
    model = getattr(r.model, "key", "") or ""
    if mode == "lines":
        return {"lines": parse_lines(r.text, code), "model": model}
    expl, fix = parse_error_answer(r.text)
    valid = True
    if fix and language in ("sage", "python"):
        chk = await asyncio.to_thread(validate, fix, language, set())
        valid = chk["ok"] or bool(chk.get("unknown"))       # compiles (names may come from earlier cells)
    if fix.strip() == code.strip():
        fix = ""
    return {"explanation": expl, "fix": fix, "fix_valid": valid, "model": model}
