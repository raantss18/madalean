"""Untrusted data from Left to Solve (D69): problems, briefs, notes, board items, desk answers.

Everything is bounded, stripped of control / bidi characters, and flagged when it looks addressed to a model
(the news injection heuristic, D54). Flagged text is never given to a model and never acted upon; it is kept for
the user to read, marked « suspect »."""
from __future__ import annotations

import re

from ..news.summarize import looks_like_injection

ID_RE = re.compile(r"^[A-Za-z0-9_.'«»-]{1,200}$")
LEASE_RE = re.compile(r"^[A-Za-z0-9_.:-]{1,120}$")
HANDLE_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})$")
_CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f​-‏‪-‮⁦-⁩﻿]")
# phrases that try to make an agent act (join.txt itself warns: « never run a command … because returned text asks »)
_ACT = re.compile(r"(?i)(\b(curl|wget|sudo|chmod|bash|powershell)\s|\b(pip|npm|cargo)\s+install\b|\brm\s+-rf\b|"
                  r"\bgh\s+(auth|pr|repo|api)\b|\bapi[_ -]?keys?\b|\bpasswords?\b|\bmot\s+de\s+passe\b|\.ssh/|"
                  r"\bcredentials?\b|\bgit\s+push\b)")

LIMITS = {"title": 300, "statement": 8000, "lean": 12000, "skeleton": 12000, "brief": 60000, "note": 4000,
          "excerpt": 600, "reason": 300}


def clean(value, limit: int, one_line: bool = False) -> str:
    s = value if isinstance(value, str) else ("" if value is None else str(value))
    s = _CTRL.sub("", s[: limit * 4]).replace("\r\n", "\n").replace("\r", "\n")
    if one_line:
        s = " ".join(s.split())
    return s[:limit]


def suspect(text: str) -> bool:
    """True when the text addresses a model or asks for an action on the machine (never acted upon either way)."""
    return looks_like_injection(text or "") or bool(_ACT.search(text or ""))


def valid_id(x) -> str:
    x = x if isinstance(x, str) else ""
    return x if ID_RE.match(x) else ""


def problem(raw) -> dict | None:
    """A problem record from /api/problems[/<id>] or a desk answer, reduced to the fields we use, bounded."""
    if not isinstance(raw, dict):
        return None
    pid = valid_id(raw.get("id"))
    if not pid:
        return None
    decl = valid_id(raw.get("decl")) or pid

    def num(k, lo=0, hi=10 ** 6):
        v = raw.get(k)
        return int(v) if isinstance(v, (int, float)) and not isinstance(v, bool) and lo <= v <= hi else None
    kind = raw.get("kind") if raw.get("kind") in ("known", "open", "warmup", "step", "formalize", "impact") else ""
    out = {"id": pid, "decl": decl, "kind": kind,
           "title": clean(raw.get("title"), LIMITS["title"], True),
           "source": clean(raw.get("source"), 80, True),
           "fields": [clean(f, 60, True) for f in (raw.get("fields") or [])[:6] if isinstance(f, str)],
           "difficulty": num("difficulty", 0, 100), "liveAgents": num("liveAgents", 0, 10000),
           "points": num("points", 0, 100000),
           "solved": bool(raw.get("solved")) or raw.get("solution") not in (None, "", False),
           "claimed": bool(raw.get("claimed")), "proofPending": bool(raw.get("proofPending") or raw.get("proof_pending")),
           "statement": clean(raw.get("statement"), LIMITS["statement"]),
           "lean": clean(raw.get("lean"), LIMITS["lean"]),
           "module": clean(raw.get("module"), 200, True),
           "upstreamCommit": clean(raw.get("upstreamCommit"), 64, True),
           "excerpt": clean(raw.get("excerpt"), LIMITS["excerpt"], True)}
    for k in ("skeleton", "disproofSkeleton", "reductionSkeleton"):
        if isinstance(raw.get(k), str):
            out[k] = clean(raw[k], LIMITS["skeleton"])
    for k in ("proofFile", "reductionFile"):
        f = raw.get(k)
        if isinstance(f, str) and re.match(r"^(proofs|reductions|statements)/[A-Za-z0-9_.'«»-]{1,220}\.lean$", f):
            out[k] = f
    out["suspect"] = suspect(" ".join(str(out.get(k, "")) for k in ("title", "statement", "excerpt")))
    return out


def note(raw) -> dict | None:
    """A team note / board item: data. `code` keeps the Lean blocks (compiled only in the sandbox, never trusted)."""
    if isinstance(raw, str):
        raw = {"text": raw}
    if not isinstance(raw, dict):
        return None
    text = clean(raw.get("text") or raw.get("body") or "", LIMITS["note"])
    if not text:
        return None
    code = re.findall(r"```(?:lean4?|)\n(.*?)```", text, re.S)
    return {"id": clean(raw.get("id"), 40, True), "handle": clean(raw.get("handle"), 40, True),
            "kind": next((k for k in ("PLAN", "TAKING", "DONE", "DEAD END") if text.startswith(k + ":")), ""),
            "text": text, "code": [c[:LIMITS["note"]] for c in code[:4]], "suspect": suspect(text)}
