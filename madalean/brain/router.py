"""Router: which models to try for a role, best first, with a human-readable reason. Ported from L Katta's
moteur.rs (`route`, `composer`): quality for the request's category (75 %) + observed reliability (25 %), paused
models skipped, paid models only when chosen or with « paid first », local models last in `auto`; plus Madalean
roles → categories and a Lean bonus (catalogue.LEAN_FAMILIES)."""
from __future__ import annotations

import re
from dataclasses import dataclass

from .catalogue import Catalogue, Model, lean_bonus, unfit_reason
from .classify import role_categories
from .leaderboard import ROLE_TASK, Leaderboard
from .state import States

_FAST = re.compile(r"flash|mini|small|fast|lite|haiku|nano|turbo|instant|-8b|-9b|7b|3b", re.I)
_SLOW = re.compile(r"opus|fable|-r1|thinking|reasoner|405b|397b|550b|ultra", re.I)


FORMAL_ROLES = ("prove", "formalize", "route")


@dataclass
class Candidate:
    model: Model
    score: float
    why: str


def score_model(m: Model, cat: str, cat2: str, fast: bool, states: States, paid_first: bool) -> tuple[float, str]:
    q1, q2 = m.score(cat), m.score(cat2)
    q = 0.7 * q1 + 0.3 * q2
    rel = states.reliability(m.key)
    s = 0.75 * q + 0.25 * rel
    parts = [f"{cat} {q1:.2f}"]
    if m.est:
        parts.append(f"(estimated: {m.est})")
    if cat == "lean" and "lean" not in m.quality:
        b, why = lean_bonus(m)
        if b:
            parts.append(f"(+{b:.2f}: {why})")
    parts.append(f"{cat2} {q2:.2f}, reliability {rel:.2f}")
    name = f"{m.model_id} {m.name}"
    if fast:
        if _FAST.search(name):
            s += 0.05
            parts.append("fast model +0.05")
        elif _SLOW.search(name):
            s -= 0.05
            parts.append("slow model -0.05")
    if m.local:
        s -= 0.25
        parts.append("local -0.25")
    if m.paid:
        if paid_first:
            s += 1.0
            parts.append("paid first +1")
        else:
            parts.append("paid (only when chosen)")
    else:
        parts.append("free")
    return s, ", ".join(parts)


def rank(cat_: Catalogue, states: States, role: str, *, messages: list[dict] | None = None, prefer: str | None = None,
         paid_first: bool = False, need_tools: bool = False, local_models: list[Model] | None = None,
         allow_online: bool = True, allow_local: bool = True, leaderboard: Leaderboard | None = None,
         domain: str | None = None, lang: str = "fr") -> list[Candidate]:
    """`leaderboard`: observed results on this machine (session S-J) add a bonus for the role's task (prove /
    formalize / explain), per problem `domain` when known."""
    cat, cat2, fast = role_categories(role, messages)
    task = ROLE_TASK.get(role)

    def chosen(m: Model) -> bool:
        return bool(prefer) and prefer != "auto" and (m.key == prefer or m.model_id == prefer)

    out: list[Candidate] = []
    pool = [m for m in cat_.models if not m.local] if allow_online else []
    if allow_local:
        pool += [m for m in cat_.models if m.local] + list(local_models or [])
    for m in pool:
        if need_tools and not m.tools and not m.local:
            continue
        if states.pause_of(m.key) and not chosen(m):
            continue
        if m.paid and not (paid_first or chosen(m)):
            continue
        if m.provider == "huggingface" and not (chosen(m) and role in ("prove", "formalize")):
            continue                          # Goedel specialists (S-T): only pinned, with Goedel's own prompts
        s, why = score_model(m, cat, cat2, fast, states, paid_first)
        if role in FORMAL_ROLES and not chosen(m):
            unfit = unfit_reason(m)
            if unfit and role != "route":
                continue                      # never a prover / formaliser (still usable when the user picks it)
            if unfit:
                s -= 0.3
                why += f", {unfit} -0.30"
        if leaderboard is not None and task:
            b, bwhy = leaderboard.bonus(m.key, task, domain, lang)
            if bwhy:
                s += b
                why += ", " + bwhy
        if m.provider == "local":
            s += 0.1                          # the server's own model for this role beats Ollama's
            why += ", Madalean's local model for this role"
        if chosen(m):
            s += 100
            why = "chosen by the user; " + why
        out.append(Candidate(m, s, why))
    out.sort(key=lambda c: c.score, reverse=True)
    return out


def compose(ranked: list[Candidate], max_chain: int = 5) -> list[Candidate]:
    """At most 2 paid models first, then free online models (at least 3, up to `max_chain` in total), then the local
    models as the offline fallback (never a chain made only of paid models). A model chosen by the user stays first."""
    online = [c for c in ranked if not c.model.local]
    local = [c for c in ranked if c.model.local]
    head = [c for c in online if c.score >= 100]
    rest = [c for c in online if c.score < 100]
    paid = [c for c in rest if c.model.paid][:2]
    free = [c for c in rest if not c.model.paid]
    n_free = max(max_chain - len(head) - len(paid), 3)
    chain = head + paid + free[:n_free]
    lhead = [c for c in local if c.score >= 100]
    return lhead + chain + [c for c in local if c not in lhead][:2] if lhead else chain + local[:2]
