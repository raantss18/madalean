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
STATUS_TEXT = {"proved": "prouvé en Lean", "to_prove": "énoncé Lean à prouver (preuve conditionnelle)"}


def enabled(pipe, job, d, refine) -> bool:
    s = pipe.settings
    if not getattr(s, "literature", True) or job.mode == "local" or refine is not None:
        return False
    if isinstance(d.extra.get("cited_from"), dict):
        return False
    return True


def start(pipe, job, d, io, ws, refine) -> asyncio.Task | None:
    """Spawn the stage (or nothing). The task is added to `job.bg_tasks`, gathered / cancelled with the side stages."""
    if not enabled(pipe, job, d, refine):
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


def hint(res) -> str:
    """For the provers: Mathlib names first (usable), then cited results that are NOT available as lemmas."""
    lines: list[str] = []
    for it in res.items:
        if it.lean.status == "in_mathlib" and it.lean.mathlib_name:
            lines.append(f"- In Mathlib: `{it.lean.mathlib_name}` states a published result ({it.reference.short()}).")
        elif it.lean.status == "proved" and it.lean.library_name:
            lines.append(f"- In the library: `{it.lean.library_name}` ({it.reference.short()}).")
    cited = [it for it in res.items if it.is_cited_lemma][:MAX_HINT_ITEMS]
    if cited:
        lines.append("- Published results NOT available in Lean (you cannot cite them; prove what you need inline):")
        for it in cited:
            decl = it.lean.statement.split("theorem", 1)[-1].strip()[:500]
            lines.append(f"  - ({it.reference.short()}) theorem {decl}")
    if not lines:
        return ""
    return "Related results found in the literature:\n" + "\n".join(lines)


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
    try:
        res = await literature.search(statement, ctx, budget, text=d.understood or d.problem, depth=depth,
                                      mode=job.mode, project_id=d.project_id, ws=ws, owner=f"{job.id}#literature",
                                      lang=language())
    except asyncio.CancelledError:
        raise
    except Exception as e:  # noqa: BLE001 (the literature never fails a job)
        log.warning("literature stage of %s failed: %s", job.id, e)
        return
    if d.statement != statement or d.cur_statement != cur:
        return                         # the statement changed meanwhile: this search is about the old one
    d.extra["literature"] = stored(res) | {"statement_index": cur}
    job.literature_hint = hint(res)
    m, detail = summary_event(res)
    await pipe.event(d, job, "literature", m["key"], detail=detail, **m["params"], cached=res.cached,
                     seconds=res.seconds)
    ctx.publish("literature.updated", {"dossier_id": d.id})
    cited = res.cited_lemmas()
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
