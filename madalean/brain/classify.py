"""Kind of request (code, math, writing…) from weighted keywords, ported from L Katta's moteur.rs `classify`, and
the mapping from Madalean roles to quality categories."""
from __future__ import annotations

import contextvars
import re
from contextlib import contextmanager

_RULES: list[tuple[str, re.Pattern, float]] = [(c, re.compile(p, re.I), w) for c, p, w in [
    ("code", r"```", 3.0),
    ("code", r"\b(sage|sagemath|pari|gp|numpy|sympy|jupyter)\b|sage:", 2.0),
    ("code", r"\b(python|javascript|typescript|java|rust|golang|kotlin|dart|flutter|c\+\+|sql|bash|regex|html|css|react|django|fastapi|docker)\b", 2.0),
    ("code", r"\b(code|coder|fonction|function|bug|d[ée]bogue|debug|compile|script|classe|m[ée]thode|api|refactor|stack ?trace|exception|traceback)\b", 1.5),
    ("code", r"(def |class |import |#include|console\.log|public static)", 3.0),
    ("math", r"\$[^$]+\$|\\\(|\\\[|\\frac|\\int|\\sum|\\sqrt", 3.0),
    ("math", r"\b([ée]quation|int[ée]grale|d[ée]riv[ée]e|th[ée]or[èe]me|d[ée]montre|d[ée]monstration|matrice|probabilit[ée]|limite|polyn[ôo]me|calcule|r[ée]sous|lemme)\b", 2.0),
    ("math", r"\b(equation|integral|derivative|theorem|lemma|prove|proof|matrix|probability|solve|calculate|compute)\b", 2.0),
    ("math", r"\d+\s*[-+*/^]\s*\d+", 1.0),
    ("math", r"\b(lean|mathlib|tactic|tactique|alg[èe]bre|latex)\b|[∀∃ℕℤℝ≤≥∑∏]", 2.0),
    ("translation", r"\b(tradui[st]|traduction|traduire|en anglais|en fran[çc]ais|translate|translation)\b", 4.0),
    ("writing", r"\b(r[ée]dige|[ée]cris|po[èe]me|lettre|histoire|article|discours|dissertation|r[ée]sum[ée]|courriel|e-?mail|write|poem|letter|story|essay|explique|explain)\b", 2.0),
    ("writing", r"\b(dossier|manuel|cours|rapport|m[ée]moire|document|chapitres?)\b", 1.5),
    ("search", r"\b(actualit[ée]s?|aujourd'hui|derni[èe]res? (nouvelles|infos)|cette semaine|m[ée]t[ée]o|news|today|latest|weather)\b", 3.0),
    ("reasoning", r"\b(pourquoi|analyse|compare|raisonne|logique|[ée]nigme|strat[ée]gie|[ée]tape par [ée]tape|why|analy[sz]e|reason|step by step)\b", 1.5),
]]


def classify(text: str) -> str:
    scores: dict[str, float] = {}
    for cat, rx, w in _RULES:
        if rx.search(text):
            scores[cat] = scores.get(cat, 0.0) + w
    best = max(((c, s) for c, s in scores.items() if s >= 1.5), key=lambda x: x[1], default=None)
    return best[0] if best else "chat"


# role -> (main category, weight of the main category, secondary category, wants a fast model)
ROLE_CATEGORIES: dict[str, tuple[str, str, bool]] = {
    "prove": ("lean", "reasoning", False),
    "formalize": ("lean", "math", False),
    "explain": ("writing", "math", False),
    "understand": ("math", "chat", True),
    "route": ("chat", "reasoning", True),
}


# Kind of work of a call, set by the caller around `brain.complete` (session S-U): Sage / Python code goes to code
# models (Codestral, Qwen Coder, gpt-oss…), LaTeX writing to strong writing models — whatever the role says (the roles
# of api.Role are fixed). Formal roles (prove / formalize) are never overridden.
#     with classify.task("sage"):
#         await brain.complete("explain", msgs)
TASKS: dict[str, tuple[str, str, bool]] = {
    "code": ("code", "math", False), "sage": ("code", "math", False), "python": ("code", "math", False),
    "latex": ("writing", "math", False), "writing": ("writing", "chat", False), "search": ("search", "chat", True),
    # S-AB: short interactive transcription (Calcul « Demander »: a request → one Sage cell). Code models, ranked with
    # their MEASURED latency, thinking capped, staggered parallel start (engine.MadaleanBrain._race), short timeouts
    "transcribe": ("code", "math", True),
}
FAST_TASKS = ("transcribe",)
TASK_HINT: contextvars.ContextVar[str | None] = contextvars.ContextVar("madalean_brain_task", default=None)


@contextmanager
def task(kind: str | None):
    token = TASK_HINT.set(kind if kind in TASKS else None)
    try:
        yield
    finally:
        TASK_HINT.reset(token)


def role_categories(role: str, messages: list[dict] | None = None) -> tuple[str, str, bool]:
    hint = TASK_HINT.get()
    if hint and role not in ("prove", "formalize"):
        return TASKS[hint]
    if role in ROLE_CATEGORIES:
        return ROLE_CATEGORIES[role]
    last = ""
    for m in reversed(messages or []):
        if m.get("role") == "user":
            c = m.get("content")
            last = c if isinstance(c, str) else " ".join(b.get("text", "") for b in c if isinstance(b, dict))
            break
    cat = classify(last)
    return (cat, "chat", False)


# S-AF (DECISIONS D38): the short text stages of a dossier job (understand, route, guided reading, statement check,
# explanation, informal proof) take the same latency-first path as the transcription — measured latency in the
# ranking, staggered race, minimal thinking, short timeouts, local models only when no online model could answer —
# but keep their role's quality categories (an explanation is still ranked as French mathematical writing).
SHORT_STAGE: contextvars.ContextVar[bool] = contextvars.ContextVar("madalean_brain_short_stage", default=False)


@contextmanager
def short_stage(on: bool = True):
    token = SHORT_STAGE.set(bool(on))
    try:
        yield
    finally:
        SHORT_STAGE.reset(token)


def short_stage_active() -> bool:
    return SHORT_STAGE.get()


def fast_task() -> bool:
    """The current call is a short interactive one (Calcul transcription, D35) or a short text stage of a dossier
    (D38): latency first."""
    return TASK_HINT.get() in FAST_TASKS or SHORT_STAGE.get()
