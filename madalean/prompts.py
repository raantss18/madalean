"""Prompts added in 2.0 (the 1.1.4 prompts stay in `leancheck`, verbatim). The Goedel prompts are never changed."""
from __future__ import annotations

NOTES_PROMPTS = {
    "fr": (
        "Tu aides un étudiant qui apprend Lean 4. Voici un énoncé Lean (sans preuve) :\n"
        "```lean4\n{code}\n```\n"
        "{nl}"
        "Explique-le EN FRANÇAIS, ligne par ligne, pour quelqu'un qui découvre Lean : pour chaque morceau de la "
        "signature (variables, hypothèses entre parenthèses, conclusion après les deux-points), donne le morceau de "
        "code entre accents graves puis sa signification mathématique (types ℕ, ℝ, notations ∀ ∃ → ↑, crochets "
        "d'instances…). Termine par une phrase « En résumé : … » qui énonce le théorème en langage courant.\n"
        "Règles : liste à puces, formules en LaTeX entre $...$, pas de preuve, n'invente rien qui n'est pas dans le code."),
    "en": (
        "You help a student who is learning Lean 4. Here is a Lean statement (without proof):\n"
        "```lean4\n{code}\n```\n"
        "{nl}"
        "Explain it IN ENGLISH, line by line, for someone new to Lean: for each piece of the signature (variables, "
        "hypotheses in parentheses, conclusion after the colon), give the piece of code in backticks then its "
        "mathematical meaning (types ℕ, ℝ, notations ∀ ∃ → ↑, instance brackets…). End with one sentence "
        "« In short: … » stating the theorem in plain language.\n"
        "Rules: bullet list, formulas in LaTeX between $...$, no proof, do not invent anything that is not in the code."),
}

INFORMAL_PROMPTS = {
    "fr": (
        "Tu es un professeur de mathématiques. Voici un théorème et une preuve en Lean 4 que Lean a vérifiée.\n"
        "Rédige EN FRANÇAIS la démonstration mathématique correspondante, comme dans un manuel : un paragraphe "
        "d'énoncé (« Théorème. … »), puis « Démonstration. » suivie d'un raisonnement continu en langage "
        "mathématique, sans parler de Lean ni de tactiques, qui suit fidèlement les étapes de la preuve vérifiée. "
        "Formules en LaTeX entre $...$. Termine par « □ ».\n"
        "{nl}\n```lean4\n{code}\n```"),
    "en": (
        "You are a mathematics teacher. Here is a theorem and a Lean 4 proof that Lean has verified.\n"
        "Write IN ENGLISH the corresponding mathematical proof, as in a textbook: one paragraph stating the result "
        "(« Theorem. … »), then « Proof. » followed by continuous mathematical reasoning, without mentioning Lean or "
        "tactics, that faithfully follows the steps of the verified proof. Formulas in LaTeX between $...$. "
        "End with « □ ».\n"
        "{nl}\n```lean4\n{code}\n```"),
}

SPLIT_PROMPT = (
    "Here is a Lean 4 theorem that has not been proved yet:\n```lean4\n{code}\n```\n"
    "Split its proof into at most {n} intermediate lemmas that are each easier to prove and that together make the "
    "theorem easy. Write each lemma as a complete Lean 4 statement `theorem <name> … := by sorry` using only "
    "Mathlib, with distinct names in snake_case. Answer with ONE ```lean4 code block containing only the lemmas "
    "(no imports, no proofs), each preceded by a comment line `-- <one-sentence description>`."
)

ASSISTANT_SYSTEM = {
    "fr": ("Tu es l'assistant de Madalean, un atelier de preuves en Lean 4 (avec Mathlib), Python et SageMath. "
           "Réponds en français, précisément et brièvement. Formules en LaTeX entre $...$, code dans des blocs "
           "```lean4, ```python ou ```sage. N'affirme jamais qu'un énoncé est prouvé si Lean ne l'a pas vérifié."),
    "en": ("You are the assistant of Madalean, a workshop for proofs in Lean 4 (with Mathlib), Python and SageMath. "
           "Answer in English, precisely and briefly. Formulas in LaTeX between $...$, code in ```lean4, ```python "
           "or ```sage blocks. Never claim that a statement is proved unless Lean verified it."),
}


def _nl(text: str, lang: str) -> str:
    if not text.strip():
        return ""
    return (f"Énoncé d'origine, en langage naturel : {text.strip()}\n" if lang != "en" else
            f"Original statement, in natural language: {text.strip()}\n")


def _body(code: str) -> str:
    code = code.strip()
    k = code.find("theorem")
    return code[k:] if k > 0 else code


def notes_messages(statement: str, nl_statement: str = "", lang: str = "fr") -> list[dict]:
    p = NOTES_PROMPTS["en" if lang == "en" else "fr"]
    return [{"role": "user", "content": p.format(code=_body(statement), nl=_nl(nl_statement, lang))}]


def informal_messages(proof: str, nl_statement: str = "", lang: str = "fr") -> list[dict]:
    p = INFORMAL_PROMPTS["en" if lang == "en" else "fr"]
    return [{"role": "user", "content": p.format(code=_body(proof), nl=_nl(nl_statement, lang))}]


def split_messages(statement: str, n: int = 4) -> list[dict]:
    return [{"role": "user", "content": SPLIT_PROMPT.format(code=_body(statement), n=n)}]


def assistant_messages(messages: list[dict], context: dict | None, lang: str = "fr") -> list[dict]:
    """System prompt + optional context (dossier, notebook cell) + the conversation."""
    sys_txt = ASSISTANT_SYSTEM["en" if lang == "en" else "fr"]
    ctx = context or {}
    parts = []
    if ctx.get("lean"):
        parts.append(f"Current Lean code:\n```lean4\n{str(ctx['lean'])[:12000]}\n```")
    if ctx.get("notebook"):
        parts.append(f"Open notebook: {str(ctx['notebook'])[:200]}")
    if ctx.get("cell"):
        parts.append(f"Current cell ({ctx.get('cell_type', 'code')}):\n```\n{str(ctx['cell'])[:12000]}\n```")
    if ctx.get("cells"):
        parts.append("Other cells:\n" + "\n---\n".join(str(c)[:2000] for c in list(ctx["cells"])[:20]))
    if ctx.get("text"):
        parts.append(str(ctx["text"])[:8000])
    if parts:
        sys_txt += "\n\nContext:\n" + "\n\n".join(parts)
    conv = [{"role": m.get("role", "user"), "content": str(m.get("content", ""))}
            for m in messages if m.get("role") in ("user", "assistant")]
    return [{"role": "system", "content": sys_txt}, *conv]
