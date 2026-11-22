"""« Expliquer » on demand (session S-AB): plain-language explanations of code for a mathematician — generic over the
language (`sage`, `python`, `lean`) so the Lean proofs screen can reuse it (HTTP: `POST /api/code/explain`).

- `mode="error"`: what went wrong, in plain words (no jargon), and a proposed fix — a SUGGESTION: the caller shows it
  and the user applies it explicitly; applied model code still needs the usual approval before it runs.
- `mode="lines"`: one short explanation per line of code (shown next to / under each line).
- `mode="steps"` (S-AJ, D42): the mathematical steps of a computation that ran — how a mathematician would obtain
  the result by hand, ending on the cell's actual result; for what cannot be done by hand, the method and its key
  facts. Facts computed by Sage (research/steps.py) are given to the model, which must not invent other
  intermediate values; without facts the answer is marked « explication sans vérification » by the caller.

Fast code role (research/codegen.py: `classify.task("transcribe")`, no job slot) and the syntax card of the installed
version (syntaxcards.py: Sage card / Lean+Mathlib card) in the system prompt."""
from __future__ import annotations

import asyncio
import re

from .. import syntaxcards
from . import steps
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
TASK_STEPS = {
    "fr": "Explique les ÉTAPES MATHÉMATIQUES de ce calcul, comme un mathématicien le ferait à la main (pas le code). "
          "Écris une liste numérotée courte (3 à 7 étapes), une ou deux phrases par étape, formules en LaTeX entre "
          "$…$. La dernière étape donne le résultat exact de la cellule. Si le calcul est trop gros pour être fait "
          "à la main, explique la méthode (l'algorithme) et ses faits clés. N'invente AUCUNE valeur intermédiaire : "
          "n'utilise que les faits vérifiés ci-dessous et le résultat ; sans fait, décris la méthode sans chiffres "
          "inventés. Rien avant ni après la liste.\n\n{request}Code :\n```{tag}\n{code}\n```\n\n"
          "Résultat de la cellule :\n{output}\n\n{facts}",
    "en": "Explain the MATHEMATICAL STEPS of this computation, as a mathematician would do it by hand (not the code). "
          "Write a short numbered list (3 to 7 steps), one or two sentences per step, formulas in LaTeX between "
          "$…$. The last step gives the cell's exact result. If the computation is too big to do by hand, explain "
          "the method (the algorithm) and its key facts. Do NOT invent any intermediate value: only use the "
          "verified facts below and the result; without a fact, describe the method without made-up numbers. "
          "Nothing before or after the list.\n\n{request}Code:\n```{tag}\n{code}\n```\n\n"
          "Cell result:\n{output}\n\n{facts}",
}
FACTS_HEAD = {"fr": "Faits vérifiés par Sage (à utiliser tels quels) :", "en": "Facts verified by Sage (use them as is):"}
NO_FACTS = {"fr": "Aucun fait vérifié par Sage n'est disponible.", "en": "No fact verified by Sage is available."}
MAX_OUTPUT = 3000
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


def clip_output(text: str, limit: int = MAX_OUTPUT) -> str:
    """A long output keeps its start and its end (the result is usually last)."""
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    half = limit // 2
    return text[:half] + f"\n[… {len(text) - limit} …]\n" + text[-half:]


def steps_messages(language: str, code: str, output: str, lang: str, card: str, *, request: str = "",
                   intent: str = "", facts: list[str] | None = None) -> list[dict]:
    if language not in ("sage", "python"):
        raise ExplainError("bad_language")
    if not code.strip() or len(code) > MAX_CODE:
        raise ExplainError("bad_code")
    if not output.strip():
        raise ExplainError("no_output")
    lang = lang if lang in SYSTEM else "en"
    fr = lang == "fr"
    system = SYSTEM[lang].format(name=LANGS[language]) + (f"\n\n{card}" if card else "")
    head = ""
    if request.strip():
        head += ("Demande : " if fr else "Request: ") + request.strip()[:2000] + "\n"
    if intent.strip():
        head += ("Reconnu : " if fr else "Recognized: ") + intent.strip()[:500] + "\n"
    fx = (FACTS_HEAD[lang] + "\n" + "\n".join(f"- {f}" for f in facts)) if facts else NO_FACTS[lang]
    user = TASK_STEPS[lang].format(request=head + ("\n" if head else ""), tag=TAGS[language], code=code,
                                   output=clip_output(output), facts=fx)
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


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


def clean_steps(text: str) -> str:
    """The numbered derivation as Markdown (a stray code fence or preamble from the model is dropped)."""
    t = re.sub(r"```.*?(```|$)", "", text or "", flags=re.S).strip()
    m = re.search(r"^\s*1[.)]\s", t, re.M)
    return steps.inline_delims((t[m.start():] if m else t).strip())


async def explain_steps(ctx, *, language: str, code: str, output: str, lang: str = "fr", request: str = "",
                        intent: str = "", facts: list[str] | None = None, owner: str = "explain",
                        on_text=None) -> dict:
    """→ {text (Markdown, numbered steps, LaTeX in $…$), model}. `on_text(text so far)` streams the answer."""
    card = await asyncio.to_thread(card_for, language, ctx)
    msgs = steps_messages(language, code, output, lang, card, request=request, intent=intent, facts=facts)
    buf: list[str] = []

    def on_chunk(ch) -> None:
        if ch.kind == "info" and (ch.data or {}).get("event") == "restart":
            buf.clear()
            return
        if ch.kind == "text" and ch.text:
            buf.append(ch.text)
            if on_text is not None:
                on_text(clean_steps("".join(buf)))
    r = await fast_complete(ctx, msgs, owner, on_chunk, 1500)
    return {"text": clean_steps(r.text), "model": getattr(r.model, "key", "") or ""}
