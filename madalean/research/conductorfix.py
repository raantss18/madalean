"""The conductor's corrections outside a dossier job (session S-AN, DECISIONS D46, docs/BRAIN.md §18).

Two places where something Madalean ran failed and the deterministic repairs did not apply:

- **Calcul**: a cell's code failed at run time and `codefix` (missing import / name / earlier definition) found
  nothing. `fix_code` asks the conductor (Claude tier chosen by its scoring within the request's budget, then the best
  free model; None → the caller keeps today's path: the pinned Calcul model) with the Sage / Python tool cards and the
  catalogue's canonical constructions of the recognized request. The corrected code is model code like any other:
  same approval rules, same sandboxed kernel; a version that then runs OK becomes the « meilleure version » through
  the recipes ranking (`recipes.outcome`).
- **Article**: a compilation failed with an error Madalean has no one-click fix for. `fix_compile` asks for ONE local
  change (find → replace), recompiles the project with it in a separate sandboxed build (`texbuild.trial_compile`)
  and only a change that compiles is offered — as a suggestion of the article's suggestions panel (accept / refuse,
  never applied silently).

Budget: each user request has its own spending scope (`calcul:…` / `article:…`) with the conductor's per-request cap
(setting `conductor_cap_usd`) in `Ledger.scope_caps`; when a Claude decision does not fit, the user is asked
« Plafond atteint : continuer avec Claude (+0,50 $) ? » through the `conductor.ask` event and
`POST /api/conductor/asks/{id} {approve}` (no answer within ASK_TIMEOUT = no); a month with less than 0.50 $ left
never asks. Nothing here calls a model when no conductor can run (setting off, local mode, fake brains)."""
from __future__ import annotations

import asyncio
import time
import uuid
from collections import OrderedDict

from ..brain import conductor as cmod
from ..brain import spend, toolcards
from ..logs import get

log = get("conductorfix")
ASK_TIMEOUT = 300.0            # an interactive request (a run, a compilation) waits at most this long for the answer
DEADLINE = 120.0               # one correction decision, the whole fallback chain
MAX_TEX_FIX = 3                # proposals per failed compilation (each one recompiled)
MAX_REQUESTS = 200             # request scopes kept in memory (their caps)
ASKS: dict[str, dict] = {}     # ask id → {event, answer, info}
REQUESTS: "OrderedDict[str, dict]" = OrderedDict()     # scope → {cap, declined}
_TEX_TRIED: "OrderedDict[tuple, float]" = OrderedDict()


# ---------------------------------------------------------------- availability, budget, the cap question
def available(ctx, mode: str) -> cmod.Conductor | None:
    """The conductor when one can run for this mode (setting on, not local, a brain with the interface, and either a
    Claude key or a capable free model), else None."""
    try:
        if not getattr(ctx.settings, "conductor", True) or mode == "local":
            return None
        c = cmod.conductor_of(getattr(ctx, "brain", None))
        if c is None or not c.enabled(mode):
            return None
        if not c.claude_models(mode) and not c.free_conductors(mode):
            return None
        return c
    except Exception:  # noqa: BLE001 (a correction never breaks the caller)
        log.exception("conductor availability")
        return None


def _request(ctx, c: cmod.Conductor, scope: str) -> dict:
    r = REQUESTS.get(scope)
    if r is None:
        r = {"cap": float(getattr(ctx.settings, "conductor_cap_usd", 1.0) or 0.0), "declined": False}
        REQUESTS[scope] = r
        while len(REQUESTS) > MAX_REQUESTS:
            old, _v = REQUESTS.popitem(last=False)
            c.brain.ledger.scope_caps.pop(old, None)
    REQUESTS.move_to_end(scope)
    c.brain.ledger.scope_caps[scope] = r["cap"]
    return r


def answer(aid: str, approve: bool) -> bool:
    """The user's answer to a cap question (POST /api/conductor/asks/{id}); False when nothing waits for it."""
    a = ASKS.get(aid)
    if a is None or a["event"].is_set():
        return False
    a["answer"] = bool(approve)
    a["event"].set()
    return True


def pending() -> list[dict]:
    return [dict(a["info"]) for a in ASKS.values() if not a["event"].is_set()]


async def _ask_cap(ctx, c: cmod.Conductor, scope: str, req: dict, where: dict, est: float) -> bool:
    """« Plafond atteint : continuer avec Claude (+0,50 $) ? » for a request outside a job."""
    if req["declined"]:
        return False
    if c.month_room() < cmod.CAP_STEP:
        req["declined"] = True
        return False
    aid = "ca-" + uuid.uuid4().hex[:12]
    info = {"id": aid, **where, "spent": round(c.brain.ledger.scope_total(scope), 4), "cap": req["cap"],
            "step": cmod.CAP_STEP, "estimate": round(est, 4), "t": time.time()}
    box = {"event": asyncio.Event(), "answer": None, "info": info}
    ASKS[aid] = box
    ctx.publish("conductor.ask", info)
    try:
        await asyncio.wait_for(box["event"].wait(), ASK_TIMEOUT)
    except asyncio.TimeoutError:
        box["answer"] = False
    finally:
        ASKS.pop(aid, None)
        ctx.publish("conductor.ask", {"id": aid, **where, "done": True})
    if box["answer"]:
        req["cap"] = round(req["cap"] + cmod.CAP_STEP, 2)
        c.brain.ledger.scope_caps[scope] = req["cap"]
        return True
    req["declined"] = True                       # this request goes on without Claude (the free chain, or none)
    return False


async def decide(ctx, *, kind: str, decision: str, user: str, schema: dict, scope: str, where: dict, mode: str,
                 features: frozenset = frozenset(), attempt: int = 0) -> cmod.Reply | None:
    """One correction decision within the request's budget; None when no conductor could answer."""
    c = available(ctx, mode)
    if c is None:
        return None
    req = _request(ctx, c, scope)
    tok = spend.SPEND_SCOPE.set(scope)
    try:
        return await c.ask(decision, kind=kind, user=user, schema=schema, difficulty="medium", mode=mode,
                           scope=scope, features=features, attempt=attempt, claude=not req["declined"],
                           deadline=time.monotonic() + DEADLINE,
                           on_cap=lambda est: _ask_cap(ctx, c, scope, req, where, est))
    except cmod.NoConductor as e:
        log.info("no conductor for %s: %s", kind, "; ".join(e.tried)[:300])
        return None
    except asyncio.CancelledError:
        raise
    except Exception:  # noqa: BLE001
        log.exception("conductor decision %s failed", kind)
        return None
    finally:
        spend.SPEND_SCOPE.reset(tok)


def record(ctx, model: str, decision: str, ok: bool, seconds: float = 0.0, usd: float = 0.0) -> None:
    """A correction's outcome (the cell ran / the recompilation passed) — the conductor's measured success."""
    c = cmod.conductor_of(getattr(ctx, "brain", None))
    if c is not None and model:
        try:
            c.stats.record(model, decision, ok, seconds, usd)
        except Exception:  # noqa: BLE001
            log.exception("conductor stats")


def spent(ctx, scope: str) -> float:
    c = cmod.conductor_of(getattr(ctx, "brain", None))
    return round(c.brain.ledger.scope_total(scope), 5) if c is not None else 0.0


# ---------------------------------------------------------------- Calcul
def calcul_scope(pid: str, doc: str, cid: str, prompt: str) -> str:
    import hashlib
    return f"calcul:{pid}:{doc}:{cid}:{hashlib.sha256((prompt or '').encode()).hexdigest()[:10]}"


async def fix_code(ctx, *, language: str, prompt: str, code: str, error: str, names: list, prefix: str = "",
                   recognized: str = "", version: str = "", scope: str, where: dict, attempt: int = 0,
                   mode: str | None = None) -> dict | None:
    """The conductor's corrected cell → {code, what, model, name, tier, usd, seconds, request_usd} or None (no
    conductor, or no usable answer: the caller keeps its usual model path)."""
    from .calcul import extract_code
    mode = mode or ctx.settings.mode
    sage = language == "sage"
    tag = "sage" if sage else "python"
    ns = "\n".join(f"- {n} : {t}" + (f" = {str(r)[:60]}" if r else "") for n, t, r in (names or [])[:40]) or "- (none)"
    lines = [f"Request (the user's words): {prompt[:3000]}",
             f"Language: {'SageMath ' + (version or '') if sage else 'Python 3'}".rstrip()]
    if recognized:
        lines.append(f"Madalean recognized: {recognized[:400]}")
    if prefix:
        lines.append(f"Canonical constructions (Madalean's verified catalogue; keep these lines first, unchanged):\n"
                     f"```{tag}\n{prefix[:2000]}\n```")
    lines.append(f"Names already defined in the notebook:\n{ns}")
    lines.append(f"Code that failed:\n```{tag}\n{code[:12000]}\n```")
    lines.append(f"Error (end of the traceback):\n```\n{error[-2500:]}\n```")
    features = toolcards.features_of(prompt, code, error)
    r = await decide(ctx, kind="fix_sage" if sage else "fix_python", decision="codefix", user="\n\n".join(lines),
                     schema=cmod.FIX_CODE_SCHEMA, scope=scope, where=where, mode=mode, features=features,
                     attempt=attempt)
    if r is None:
        return None
    raw = str(r.data.get("code") or "")
    new = (extract_code(raw) if "```" in raw else raw).strip("\n")
    if not new.strip() or new.strip() == code.strip():
        record(ctx, r.key, "codefix", False, r.seconds, r.usd)
        return None
    return {"code": new, "what": str(r.data.get("what") or "")[:300], "model": r.key, "name": r.name,
            "tier": r.tier, "usd": round(r.usd, 5), "seconds": round(r.seconds, 2),
            "request_usd": spent(ctx, scope)}


# ---------------------------------------------------------------- article compilation
def _numbered(text: str, line: int, span: int = 20) -> tuple[str, int, int]:
    rows = text.split("\n")
    if line <= 0:
        lo, hi = 0, min(len(rows), 2 * span + 20)
    else:
        lo, hi = max(0, line - 1 - span), min(len(rows), line + span)
    return "\n".join(f"{i + 1:>5}| {rows[i]}" for i in range(lo, hi)), lo, hi


def _positions(text: str, find: str) -> list[int]:
    out, start = [], 0
    while True:
        i = text.find(find, start)
        if i < 0:
            return out
        out.append(i)
        start = i + 1                                # as texproject.anchor counts occurrences


def fixable(res: dict, pid: str = "") -> list[dict]:
    """Errors of a compilation that ran and for which Madalean has no one-click fix (and not already tried for this
    exact source when `pid` is given)."""
    if res.get("ok") or not res.get("ran"):
        return []
    if pid and (pid, res.get("hash") or "") in _TEX_TRIED:
        return []
    return [d for d in res.get("diagnostics") or [] if d.get("severity") == "error" and not d.get("fix")]


async def fix_compile(ctx, pid: str, res: dict, *, mode: str) -> dict | None:
    """A failed compilation → at most ONE suggestion (find → replace) checked by recompiling the project with it;
    publishes `article.fix {project, state: working|proposed|none, …}`. Never applies anything."""
    from . import texbuild, texproject as tp
    errs = fixable(res)
    if not errs:
        return None
    key = (pid, res.get("hash") or "")
    if key in _TEX_TRIED:                            # the same source: proposed (or tried) once already
        return None
    if available(ctx, mode) is None:
        return None
    _TEX_TRIED[key] = time.time()
    while len(_TEX_TRIED) > MAX_REQUESTS:
        _TEX_TRIED.popitem(last=False)
    scope = f"article:{pid}:{res.get('hash') or uuid.uuid4().hex[:8]}"
    where = {"kind": "article", "project": pid}
    d0 = errs[0]
    files = await asyncio.to_thread(tp.read_files, ctx, pid)
    path = d0.get("path") if d0.get("path") in files else "main.tex"
    text = files.get(path, "")
    if not text:
        return None
    ctx.publish("article.fix", {"project": pid, "state": "working", "path": path, "line": d0.get("line", 0)})
    excerpt, lo, hi = _numbered(text, int(d0.get("line") or 0))
    plain = (d0.get("plain") or {}).get("text", "") if isinstance(d0.get("plain"), dict) else ""
    features = toolcards.features_of(excerpt)
    feedback = ""
    for i in range(MAX_TEX_FIX):
        user = (f"File: {path}\nLaTeX error (line {d0.get('line') or '?'}): {str(d0.get('message', ''))[:400]}\n"
                + (f"Madalean's reading of it: {plain[:300]}\n" if plain else "")
                + f"\nExcerpt of {path}, lines {lo + 1}–{hi} (the numbers and `| ` on the left are NOT part of the "
                f"text):\n{excerpt}" + feedback)
        r = await decide(ctx, kind="fix_latex", decision="texfix", user=user, schema=cmod.FIX_LATEX_SCHEMA,
                         scope=scope, where=where, mode=mode, features=features, attempt=i)
        if r is None:
            break
        find, rep = str(r.data.get("find") or ""), str(r.data.get("replace") or "")
        cur = (await asyncio.to_thread(tp.read_files, ctx, pid)).get(path, "")
        if cur != text:
            break                                    # the author edited the file meanwhile: this error may be gone
        pos = [p for p in _positions(text, find) if lo <= text.count("\n", 0, p) <= hi] if find else []
        bad = texbuild.guard_ai(rep) if pos else []
        if not pos or find == rep or bad:
            record(ctx, r.key, "texfix", False, r.seconds, r.usd)
            feedback += ("\n\nYour previous answer was unusable: " + (
                "`find` is not an exact substring of the excerpt." if not pos else
                "the replacement uses refused constructions: " + ", ".join(bad) if bad else "nothing changed.")
                + " Copy `find` exactly from the excerpt.")
            continue
        line = int(d0.get("line") or 0)
        at = min(pos, key=lambda p: abs(text.count("\n", 0, p) + 1 - line)) if line else pos[0]
        new_text = text[:at] + rep + text[at + len(find):]
        trial = await texbuild.trial_compile(ctx, pid, {path: new_text})
        ok = bool(trial.get("ok"))
        record(ctx, r.key, "texfix", ok, r.seconds, r.usd)
        if not ok:
            e2 = next((d for d in trial.get("diagnostics") or [] if d.get("severity") == "error"), {})
            feedback += (f"\n\nYour change {find!r} → {rep!r} was compiled: it still fails"
                         + (f" (line {e2.get('line')}: {str(e2.get('message', ''))[:300]})" if e2 else "") + ".")
            continue
        usd = spent(ctx, scope)
        try:
            sug = await asyncio.to_thread(lambda: tp.add_suggestion(
                ctx, pid, find=find, replace=rep, path=path, at="replace", occurrence=pos.index(at),
                kind="compile_fix", origin="assistant", rationale=str(r.data.get("what") or "")[:400], model=r.key,
                meta={"conductor": r.name, "tier": r.tier, "usd": usd, "verified": "recompiled",
                      "error": str(d0.get("message", ""))[:300], "line": d0.get("line", 0)}))
        except tp.TexProjectError as e:
            log.info("compile fix not offered: %s", e.kind)
            break
        ctx.publish("article.suggestion", {"project": pid, "suggestion": sug})
        ctx.publish("article.fix", {"project": pid, "state": "proposed", "suggestion": sug["id"], "name": r.name,
                                    "usd": usd})
        return sug
    ctx.publish("article.fix", {"project": pid, "state": "none", "usd": spent(ctx, scope)})
    return None
