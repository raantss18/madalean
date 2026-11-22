"""Verified Lean constructions of the code catalogue in the formalizer's and the provers' prompts (session S-AM, D45).

S-AG's catalogue (`research/codecat.py`) compiles one construction per object / operation with each workspace's
Lean (Lean 4.9 of the prover: `Fintype.card`, `∑ i in s`; current Mathlib: `Nat.card`, `∑ i ∈ s`). The entries
relevant to the request's recognized intent (the problem in words, via `intent.py`) and to the Lean already written
(names of the statement), and verified on the dossier's workspace, are given to every model that writes Lean for a
job: the formalizer, the Goedel loop, Mathlib-first, the tournament's contestants (all through `JobIO.complete`), the
agent (its task message, `brain/prover_agent.py`) and the conductor's corrections (`toolcards.compact`).

Placement keeps provider prompt caching: the block is appended to the END of the first user message, which is the
same for every round of a job (the Goedel prompt, then the corrections appended after it), so the cached prefix of a
round is the previous round. Nothing is added when the workspace's catalogue is not built, when an entry failed
there, or when nothing is relevant (the prompt is then byte-identical to before)."""
from __future__ import annotations

from ..logs import get

log = get("leancat")
ROLES = ("prove", "formalize")
BUDGET = {"prove": 220, "formalize": 160}            # estimated tokens of the block (≈ 3 entries)
_MEMO: dict[tuple, tuple[str, list[str]]] = {}
MARK = "\n\n"


def block_for(ws, role: str, *texts: str) -> tuple[str, list[str]]:
    """(block, entry ids) for a model call of `role` on workspace `ws` about `texts`; memoized per job content."""
    from ..research import codecat
    st = codecat.lean_status(ws) if ws is not None else None
    key = (getattr(ws, "key", ""), (st or {}).get("built"), role, texts)
    hit = _MEMO.get(key)
    if hit is not None:
        return hit
    try:
        out = codecat.lean_prompt_block(ws, *texts, budget=BUDGET.get(role, 200))
    except Exception:  # noqa: BLE001 (never breaks a model call)
        log.exception("lean catalogue block")
        out = ("", [])
    if len(_MEMO) > 256:
        _MEMO.clear()
    _MEMO[key] = out
    return out


def append_block(messages: list[dict], block: str) -> list[dict]:
    """`messages` with `block` appended to the first user message (a copy; unchanged when there is none)."""
    if not block:
        return messages
    out = [dict(m) for m in messages]
    for m in out:
        if m.get("role") == "user" and isinstance(m.get("content"), str):
            if block not in m["content"]:
                m["content"] = m["content"].rstrip() + MARK + block
            return out
    return messages


def job_texts(d) -> tuple[str, ...]:
    """What the request is about: the problem in words, what was understood, the Lean statement."""
    return tuple(t for t in (getattr(d, "problem", ""), getattr(d, "understood", ""), getattr(d, "statement", ""))
                 if t)


def inject(ctx, job, role: str, messages: list[dict]) -> list[dict]:
    """The catalogue block for a pipeline model call (JobIO.complete). Never raises."""
    if role not in ROLES:
        return messages
    try:
        d = ctx.repo.get(job.dossier_id)
        if d is None:
            return messages
        ws = ctx.workspace(d.workspace or ctx.settings.workspace)
        block, ids = block_for(ws, role, *job_texts(d))
        if ids:
            cat = getattr(job, "leancat", None)
            if cat is None:
                try:
                    job.leancat = cat = []
                except AttributeError:
                    cat = []
            for i in ids:
                if i not in cat:
                    cat.append(i)
        return append_block(messages, block)
    except Exception:  # noqa: BLE001
        log.exception("lean catalogue injection")
        return messages
