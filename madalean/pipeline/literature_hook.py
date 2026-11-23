"""The `literature` stage of a proof (S-AX, D56): a few lines in `runner._proof_body`, everything else here.

Started beside Mathlib-first / certificates when the proof search starts (D38), as its own task and owner
`<job>#literature`; it never blocks the proof search (no racer waits for it, nothing waits for it before the job
ends but the optional stages' usual gather), is cancelled by « Arrêter », and is skipped when:
- the setting « Chercher dans la littérature » is off, or the job runs in Local mode (no request at all);
- the dossier is itself a cited lemma (`extra.cited_from`) — the loop guard: a search never starts a search;
- the proof is a refinement of an existing proof (the user asked for something precise).
Result: `dossier.extra["literature"]` (the LiteratureResult), one « literature » event in the thread with the
references, `job.literature_hint` for the provers (read at each new attempt, like `job.mathlib_hint`), and — when a
cited lemma (not proved in Lean) implies the statement — a conditional proof (`extra.conditional_proof`, never
« vérifiée »)."""
from __future__ import annotations

import asyncio

from ..i18n import language, msg
from ..logs import get

log = get("pipeline.literature")
MAX_HINT_ITEMS = 4
MAX_STORED_TEXT = 3000
BADGES = {"journal": "revue", "proceedings": "actes de conférence", "book": "livre", "preprint": "prépublication",
          "thesis": "thèse"}
STATUS_TEXT = {"proved": "prouvé en Lean", "to_prove": "énoncé Lean à prouver (preuve conditionnelle)",
               "in_mathlib": "dans Mathlib"}


def enabled(pipe, job, d, refine) -> bool:
    """May this job search the literature (network)?"""
    s = pipe.settings
    if not getattr(s, "literature", True) or job.mode == "local" or refine is not None:
        return False
    if isinstance(d.extra.get("cited_from"), dict):
        return False
    return True


def _provided(pipe, d) -> list:
    """The project's attachment digests (read once; no network, no model): « résultats fournis »."""
    if isinstance(d.extra.get("cited_from"), dict):
        return []
    try:
        from ..literature import attach
        return attach.provided_items(pipe.ctx, d)
    except Exception as e:  # noqa: BLE001
        log.info("provided results unavailable: %s", e)
        return []


def start(pipe, job, d, io, ws, refine) -> asyncio.Task | None:
    """Spawn the stage (or nothing). The task is added to `job.bg_tasks`, gathered / cancelled with the side stages.
    It runs when the job may search the literature, or when attachments of the project give « résultats fournis »
    (then without any request, in every mode)."""
    if refine is not None:
        return None
    if not enabled(pipe, job, d, refine) and not _provided(pipe, d):
        return None
    task = pipe._spawn(job, "literature", lambda: run(pipe, job, d, ws), track="literature")
    tasks = getattr(job, "bg_tasks", None)
    if tasks is None:
        tasks = job.bg_tasks = []
    tasks.append(task)
    return task


def stored(res) -> dict:
    """The result as kept in the dossier (texts trimmed around their quotes)."""
    data = res.to_dict()
    for it in data.get("items", []):
        for t in it.get("texts", []):
            if len(t.get("text", "")) > MAX_STORED_TEXT:
                t["text"] = t["text"][:MAX_STORED_TEXT]
        it["quotes"] = [q for q in it.get("quotes", []) if q.get("end", 0) <= MAX_STORED_TEXT] or it.get("quotes", [])
    return data


def hint(items) -> str:
    """For the provers: Mathlib names first (usable), then cited / provided results that are NOT available as
    lemmas. `items`: a LiteratureResult or a list of LiteratureItem."""
    items = list(getattr(items, "items", items) or [])
    lines: list[str] = []
    for it in items:
        if it.lean.status == "in_mathlib" and it.lean.mathlib_name:
            lines.append(f"- In Mathlib: `{it.lean.mathlib_name}` states a published result ({it.reference.short()}).")
        elif it.lean.status == "proved" and it.lean.library_name:
            lines.append(f"- In the library: `{it.lean.library_name}` ({it.reference.short()}).")
    cited = [it for it in items if it.is_cited_lemma][:MAX_HINT_ITEMS]
    if cited:
        lines.append("- Results NOT available in Lean (published or given by the user; you cannot cite them, prove "
                     "what you need inline):")
        for it in cited:
            decl = it.lean.statement.split("theorem", 1)[-1].strip()[:500]
            lines.append(f"  - ({it.reference.short()}) theorem {decl}")
    if not lines:
        return ""
    return "Related results (literature and attachments):\n" + "\n".join(lines)


def provided_event(d, provided) -> tuple[dict, str]:
    """Target first, then the results already known / provided, each with its origin — never merged."""
    target = (d.understood_display or d.understood or d.problem or "").strip().split("\n")[0][:400]
    m = msg("À prouver : {target}. Résultats fournis (pièces jointes, Sources du projet) : {n}.", target=target or
            d.theorem, n=len(provided))
    lines = []
    for it in provided[:8]:
        q = it.quotes[0] if it.quotes else None
        st = msg(STATUS_TEXT.get(it.lean.status, "non formalisé"))["text"]
        lines.append(f"- {it.label or ''} {it.reference.title} ({q.location if q else ''}) — {st}\n"
                     f"  > « {q.text if q else ''} »")
    return m, "\n".join(lines)


def summary_event(res) -> tuple[dict, str]:
    """(message, detail Markdown) of the thread event."""
    if res.local_mode:
        return msg("Littérature : mode local, aucune recherche en ligne."), ""
    with_quote = [it for it in res.items if it.quotes]
    if not with_quote:
        return msg("Littérature : rien de fiable trouvé pour cet énoncé (aucune référence avec un énoncé cité)."), ""
    peer = sum(1 for it in with_quote if it.reference.peer_reviewed)
    pre = sum(1 for it in with_quote if it.reference.kind == "preprint")
    m = msg("Littérature : {n} référence(s) avec un énoncé cité mot pour mot ({peer} publiée(s) dans une revue, "
            "{pre} prépublication(s)).", n=len(with_quote), peer=peer, pre=pre)
    lines = []
    for it in with_quote[:6]:
        r, q = it.reference, it.quotes[0]
        badge = msg(BADGES.get(r.kind, "type inconnu"))["text"]
        venue = f", *{r.venue}*" if r.venue else ""
        status = ""
        if it.lean.status == "in_mathlib":
            status = " — " + msg("dans Mathlib : {name}", name=f"`{it.lean.mathlib_name}`")["text"]
        elif it.lean.status in ("proved", "to_prove"):
            status = " — " + msg(STATUS_TEXT[it.lean.status])["text"]
        quote = q.text.replace("\n", " ")
        lines.append(f"- **{r.title}** — {', '.join(r.authors[:3])}{' et al.' if len(r.authors) > 3 else ''} "
                     f"({r.year or '—'}){venue} [{badge}]{status}\n  > « {quote} » ({q.location})")
    return m, "\n".join(lines)


async def run(pipe, job, d, ws) -> None:
    from .. import literature
    from ..literature import formal
    ctx = pipe.ctx
    s = pipe.settings
    depth = getattr(s, "literature_depth", "quick")
    budget = literature.Budget.for_depth(depth)
    job.literature_budget = budget
    statement, cur = d.statement, d.cur_statement
    provided = _provided(pipe, d)
    if provided:                       # C: what is to be proved, then what is already given — kept apart
        m, detail = provided_event(d, provided)
        await pipe.event(d, job, "literature", m["key"], detail=detail, **m["params"], provided=len(provided))
    res = None
    if enabled(pipe, job, d, None):
        try:
            res = await literature.search(statement, ctx, budget, text=d.understood or d.problem, depth=depth,
                                          mode=job.mode, project_id=d.project_id, ws=ws,
                                          owner=f"{job.id}#literature", lang=language())
        except asyncio.CancelledError:
            raise
        except Exception as e:  # noqa: BLE001 (the literature never fails a job)
            log.warning("literature stage of %s failed: %s", job.id, e)
    if d.statement != statement or d.cur_statement != cur:
        return                         # the statement changed meanwhile: this search is about the old one
    found_items = list(res.items) if res is not None else []
    job.literature_hint = hint(found_items + provided)
    if res is not None:
        d.extra["literature"] = stored(res) | {"statement_index": cur}
        m, detail = summary_event(res)
        await pipe.event(d, job, "literature", m["key"], detail=detail, **m["params"], cached=res.cached,
                         seconds=res.seconds)
        ctx.publish("literature.updated", {"dossier_id": d.id})
    cited = [it for it in found_items + provided if it.is_cited_lemma]
    if cited and not d.proof_is_current and not budget.over:
        io = formal.LitIO(ctx, job.mode, budget, owner=f"{job.id}#literature", warm=True)
        try:
            found = await formal.try_conditional(ctx, io, statement, cited, ws, owner=f"{job.id}#literature")
        except asyncio.CancelledError:
            raise
        except Exception as e:  # noqa: BLE001
            log.info("conditional proof attempt failed: %s", e)
            found = None
        if found and d.statement == statement and formal.record_conditional(d, found, ws.key):
            await ctx.repo.save(d)
            ctx.publish("literature.updated", {"dossier_id": d.id})


def after_proof(d) -> bool:
    """Called when a verified proof was recorded: a literature conditional proof becomes history."""
    from ..literature import formal
    return formal.supersede(d)
