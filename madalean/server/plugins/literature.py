"""« Littérature » API (session S-AX, DECISIONS D56, docs/LITERATURE.md).

    GET  /api/dossiers/{id}/literature                       {literature, running, enabled, depth, mode, conditional}
    POST /api/dossiers/{id}/literature        {depth?, refresh?}   202: search now (outside a job), `literature.updated`
    POST /api/dossiers/{id}/literature/stop                  cancel the running search
    POST /api/dossiers/{id}/literature/items/{item}/source   {shelf?} → add the reference to the Sources (project
                                                             shelf, else the global one) → {source, duplicate}
    POST /api/dossiers/{id}/literature/items/{item}/cite     add to the Sources AND to the dossier's references (so the
                                                             article's bibliography prints it) → {key, source}
    POST /api/dossiers/{id}/literature/items/{item}/prove    a lemma dossier with the cited Lean statement (normal
                                                             pipeline) → 201 {dossier, job}
    POST /api/dossiers/{id}/literature/conditional           try the conditional proof now → {conditional | null}
    POST /api/literature/search  {statement, text?, depth?, workspace?, project_id?}  → {result} (nothing stored)

A reference is added to the Sources from its retrieved record (never from a model); a dossier made from a cited
lemma is marked `extra.cited_from` and never searches the literature itself (loop guard). Local mode: no request
(`409 local_mode` for a search; the stored result stays readable)."""
from __future__ import annotations

import asyncio
import re
import time

from aiohttp import web

from ... import leancheck
from ...i18n import language, msg
from ...literature import Budget, LiteratureResult, formal, search
from ...logs import get
from ...pipeline import literature_hook
from ...repo import dossier_api
from ..common import body, ctx_of, error, ok, valid_id

log = get("literature")
TASKS = web.AppKey("literature_tasks", dict)
ITEM_RE = re.compile(r"^L[0-9a-f]{10}$")
MAX_STATEMENT = 20000
CELL_RE = re.compile(r"[A-Za-z0-9_-]{1,80}")


def _dossier(request):
    d = ctx_of(request).repo.get(valid_id(request.match_info["id"]))
    if d is None:
        raise web.HTTPNotFound(text='{"error":"not_found"}', content_type="application/json")
    return d


def _mode(ctx, d=None) -> str:
    from ...research.fetch import effective_mode
    proj = ctx.projects.get(d.project_id) if d is not None and d.project_id else None
    return effective_mode(ctx, proj)


def _result(d) -> LiteratureResult | None:
    raw = d.extra.get("literature")
    if not isinstance(raw, dict):
        return None
    try:
        return LiteratureResult.from_dict({k: v for k, v in raw.items() if k != "statement_index"})
    except Exception:  # noqa: BLE001
        return None


def _item(request, d):
    iid = request.match_info["item"]
    if not ITEM_RE.match(iid):
        raise web.HTTPBadRequest(text='{"error":"bad_id"}', content_type="application/json")
    res = _result(d)
    it = next((x for x in (res.items if res else []) if x.id == iid), None)
    if it is None:
        raise web.HTTPNotFound(text='{"error":"not_found"}', content_type="application/json")
    return res, it


def _public(app, ctx, d) -> dict:
    raw = d.extra.get("literature")
    cond = d.extra.get("conditional_proof")
    job = ctx.orchestrator.active_for(d.id)
    in_job = job is not None and "literature" in (getattr(job, "stages", None) or [])
    return {"literature": raw if isinstance(raw, dict) else None,
            "running": d.id in app[TASKS] or in_job,
            "enabled": bool(getattr(ctx.settings, "literature", True)),
            "depth": getattr(ctx.settings, "literature_depth", "quick"), "mode": _mode(ctx, d),
            "stale": isinstance(raw, dict) and raw.get("statement_index", d.cur_statement) != d.cur_statement,
            "conditional": cond if isinstance(cond, dict) and cond.get("source") == "literature" else None}


async def get_literature(request: web.Request) -> web.Response:
    ctx = ctx_of(request)
    return ok(_public(request.app, ctx, _dossier(request)))


async def _run_search(request_app, ctx, d, depth: str, refresh: bool) -> None:
    tasks = request_app[TASKS]
    budget = Budget.for_depth(depth)
    tasks[d.id] = (asyncio.current_task(), budget)
    statement, cur = d.statement, d.cur_statement
    ws = ctx.workspace(d.workspace or ctx.settings.workspace)
    try:
        res = await search(statement, ctx, budget, text=d.understood or d.problem, depth=depth, mode=_mode(ctx, d),
                           project_id=d.project_id, ws=ws, owner=f"lit-{d.id}", lang=language(),
                           use_cache=not refresh)
        d2 = ctx.repo.get(d.id)
        if d2 is None or d2.statement != statement or d2.cur_statement != cur:
            return
        d2.extra["literature"] = literature_hook.stored(res) | {"statement_index": cur}
        m, detail = literature_hook.summary_event(res)
        d2.add_event("literature", m["text"] + ("\n" + detail if detail else ""), key=m["key"],
                     params={**m["params"], **({"detail": detail} if detail else {})})
        await ctx.repo.save(d2)
        cited = res.cited_lemmas()
        if cited and not d2.proof_is_current and ws is not None and not budget.over:
            io = formal.LitIO(ctx, _mode(ctx, d2), budget, owner=f"lit-{d.id}")
            found = await formal.try_conditional(ctx, io, statement, cited, ws, owner=f"lit-{d.id}")
            if found and formal.record_conditional(d2, found, ws.key):
                await ctx.repo.save(d2)
    except asyncio.CancelledError:
        pass
    except Exception:  # noqa: BLE001
        log.exception("literature search of %s", d.id)
    finally:
        tasks.pop(d.id, None)
        ctx.publish("literature.updated", {"dossier_id": d.id})


async def start_search(request: web.Request) -> web.Response:
    ctx = ctx_of(request)
    d = _dossier(request)
    data = await body(request)
    if not d.statement:
        return error(409, "no_statement", "Pas d'énoncé : écrivez ou traduisez d'abord l'énoncé.")
    if _mode(ctx, d) == "local":
        return error(409, "local_mode", "Mode local : aucune recherche n'est envoyée sur le réseau (changez de mode "
                                        "pour chercher dans la littérature).")
    if d.id in request.app[TASKS]:
        return error(409, "busy", "Une recherche dans la littérature est déjà en cours pour ce dossier.")
    depth = data.get("depth") if data.get("depth") in ("quick", "deep") else getattr(ctx.settings, "literature_depth",
                                                                                     "quick")
    request.app[TASKS][d.id] = (None, None)
    ctx.spawn(_run_search(request.app, ctx, d, depth, bool(data.get("refresh"))))
    ctx.publish("literature.updated", {"dossier_id": d.id, "running": True})
    return ok({"started": True, "depth": depth}, status=202)


async def stop_search(request: web.Request) -> web.Response:
    d = _dossier(request)
    cur = request.app[TASKS].get(d.id)
    stopped = False
    if cur:
        task, budget = cur
        if budget is not None:
            budget.cancel()
        if task is not None and not task.done():
            task.cancel()
        stopped = True
    job = ctx_of(request).orchestrator.active_for(d.id)
    b = getattr(job, "literature_budget", None) if job is not None else None
    if b is not None:
        b.cancel()                                    # the job's literature stage stops at its next step
        stopped = True
    return ok({"stopped": stopped})


def _shelf(ctx, d, data: dict) -> str:
    from ...research.sources import GLOBAL
    want = str(data.get("shelf") or "")
    if want == GLOBAL:
        return GLOBAL
    if d.project_id and ctx.projects.get(d.project_id) is not None:
        return d.project_id
    return GLOBAL


async def _add_source(ctx, d, it, shelf: str) -> tuple[dict, dict | None]:
    from ...research.sources import library
    lib = library(ctx)
    if it.reference.shelf and it.reference.source_id:           # already one of the user's Sources
        try:
            return lib.get(it.reference.shelf, it.reference.source_id), {"of": it.reference.source_id,
                                                                         "reason": "source"}
        except Exception:  # noqa: BLE001
            pass
    item = dict(it.reference.csl)
    item.setdefault("title", it.reference.title)
    if it.reference.msc and not item.get("msc"):
        item["msc"] = it.reference.msc
    src, dup = await lib.add_record(shelf, item, via=f"literature:{'+'.join(it.reference.providers)}", verified=True,
                                    oa=it.reference.oa, tags=["littérature"], extract=False)
    return src, dup


async def add_source(request: web.Request) -> web.Response:
    ctx = ctx_of(request)
    d = _dossier(request)
    data = await body(request)
    _res, it = _item(request, d)
    try:
        src, dup = await _add_source(ctx, d, it, _shelf(ctx, d, data))
    except Exception as e:  # noqa: BLE001
        kind = getattr(e, "kind", "error")
        return error(getattr(e, "status", 400) if isinstance(getattr(e, "status", None), int) else 400, kind)
    return ok({"source": src, "duplicate": dup}, status=200 if dup else 201)


async def cite(request: web.Request) -> web.Response:
    """Sources + the dossier's references: the article's bibliography (research/article.py) prints the key."""
    ctx = ctx_of(request)
    d = _dossier(request)
    data = await body(request)
    _res, it = _item(request, d)
    try:
        src, _dup = await _add_source(ctx, d, it, _shelf(ctx, d, data))
    except Exception as e:  # noqa: BLE001
        return error(400, getattr(e, "kind", "error"))
    key = src.get("key", "")
    q = it.quotes[0] if it.quotes else None
    if key and not any(isinstance(r, dict) and r.get("key") == key for r in d.refs):
        d.refs.append({"key": key, "locator": q.location if q else "", "note": "literature"})
        m = msg("Référence ajoutée à la bibliographie : {ref}.", ref=key)
        d.add_event("info", m["text"], key=m["key"], params=m["params"])
        await ctx.repo.save(d)
    return ok({"key": key, "source": src, "refs": d.refs})


async def prove_item(request: web.Request) -> web.Response:
    """A lemma dossier for a cited Lean statement: normal pipeline (Mathlib first, provers), budgeted like any job.
    Its theorem keeps the cited name, so that when it is proved the library holds `cited_…` and the conditional
    proof of the parent can be upgraded (strict check)."""
    from ..routes_work import create_dossier
    ctx = ctx_of(request)
    d = _dossier(request)
    res, it = _item(request, d)
    if not it.lean.statement or not it.lean.compiled:
        return error(409, "not_formalized", "Ce résultat n'a pas d'énoncé Lean qui compile : rien à prouver.")
    if it.lean.status != "to_prove":
        return error(409, "nothing_to_prove", "Ce résultat est déjà prouvé (Mathlib ou bibliothèque).")
    child = next((c for c in ctx.repo.children(d.id) if (c.extra.get("cited_from") or {}).get("item") == it.id), None)
    if child is not None:
        return ok({"dossier": dossier_api(child), "job": None, "existing": True})
    q = it.quotes[0] if it.quotes else None
    problem = (f"« {q.text} » — {it.reference.short()}, {it.reference.title} ({q.location})" if q else
               it.reference.title)
    spec = {"title": f"{it.reference.short()} — {it.reference.title}"[:200], "statement": it.lean.statement,
            "problem": problem[:4000], "project_id": d.project_id, "workspace": d.workspace, "parent_id": d.id,
            "kind": "lemma", "start": False, "rename": False}
    try:
        child, _job = await create_dossier(ctx, spec)
    except leancheck.StatementError as e:
        return error(400, "bad_statement", "{why}", why=str(e))
    try:
        child.theorem = leancheck.theorem_name(child.statement)
    except leancheck.StatementError:
        pass
    child.extra["cited_from"] = {"dossier": d.id, "item": it.id, "ref": it.reference.id, "title": it.reference.title,
                                 "short": it.reference.short(), "t": time.time()}
    await ctx.repo.save(child)
    raw = d.extra.get("literature") or {}
    for x in raw.get("items", []):
        if x.get("id") == it.id:
            x.setdefault("lean", {})["child_dossier"] = child.id
    m = msg("Lemme cité confié aux prouveurs : {title}.", title=it.reference.short())
    d.add_event("info", m["text"], key=m["key"], params=m["params"])
    await ctx.repo.save(d)
    job = ctx.orchestrator.submit(child.id, [{"stage": "notes"}, {"stage": "proof"}])
    return ok({"dossier": dossier_api(child), "job": job.to_dict()}, status=201)


async def conditional_now(request: web.Request) -> web.Response:
    ctx = ctx_of(request)
    d = _dossier(request)
    res = _result(d)
    cited = res.cited_lemmas() if res else []
    if not cited:
        return error(409, "no_cited_lemma", "Aucun résultat cité n'a d'énoncé Lean à utiliser.")
    if d.proof_is_current:
        return error(409, "already_proved", "Le dossier a déjà une preuve vérifiée.")
    ws = ctx.workspace(d.workspace or ctx.settings.workspace)
    if ws is None:
        return error(409, "no_workspace")
    budget = Budget(seconds=240, requests=0, model_calls=0, lean_checks=6).start()
    io = formal.LitIO(ctx, _mode(ctx, d), budget, owner=f"lit-cond-{d.id}")
    found = await formal.try_conditional(ctx, io, d.statement, cited, ws, owner=f"lit-cond-{d.id}")
    if found and formal.record_conditional(d, found, ws.key):
        await ctx.repo.save(d)
        ctx.publish("literature.updated", {"dossier_id": d.id})
    return ok({"conditional": d.extra.get("conditional_proof") if found else None})


async def plain_search(request: web.Request) -> web.Response:
    """A search for any statement (nothing stored). Local mode: only the local Sources and Mathlib are searched."""
    from ...research.fetch import effective_mode
    ctx = ctx_of(request)
    data = await body(request)
    text = str(data.get("statement") or "").strip()[:MAX_STATEMENT]
    if not text:
        return error(400, "no_statement")
    try:
        statement = leancheck.prepare_statement(text)
    except leancheck.StatementError as e:
        return error(400, "bad_statement", "{why}", why=str(e))
    depth = data.get("depth") if data.get("depth") in ("quick", "deep") else "quick"
    ws = ctx.workspace(str(data.get("workspace") or "") or ctx.settings.workspace)
    pid = str(data.get("project_id") or "")
    proj = ctx.projects.get(pid) if pid else None
    res = await search(statement, ctx, Budget.for_depth(depth), text=str(data.get("text") or "")[:4000], depth=depth,
                       mode=effective_mode(ctx, proj), project_id=pid if proj else "", ws=ws,
                       owner="lit-api", lang=language())
    return ok({"result": res.to_dict()})


async def _watch_jobs(app, ctx) -> None:
    """A cited lemma's dossier was proved → upgrade the parent's conditional proof (strict check); a dossier proved
    by its own search → its literature conditional proof is superseded."""
    q = ctx.bus.subscribe()
    try:
        while True:
            ev = await q.get()
            if ev is None:
                q = ctx.bus.subscribe()
                continue
            if ev.get("type") != "job.updated":
                continue
            job = ev.get("job") or {}
            if job.get("state") not in ("done", "failed", "cancelled"):
                continue
            try:
                await _on_job_end(ctx, job)
            except Exception:  # noqa: BLE001
                log.exception("literature job watcher")
    except asyncio.CancelledError:
        pass
    finally:
        ctx.bus.unsubscribe(q)


async def _on_job_end(ctx, job: dict) -> None:
    d = ctx.repo.get(job.get("dossier_id", ""))
    if d is None:
        return
    if formal.supersede(d):
        await ctx.repo.save(d)
    src = d.extra.get("cited_from")
    if isinstance(src, dict) and d.proof_is_current:
        parent = ctx.repo.get(src.get("dossier", ""))
        if parent is None:
            return
        raw = parent.extra.get("literature") or {}
        for x in raw.get("items", []):
            if x.get("id") == src.get("item"):
                lean = x.setdefault("lean", {})
                if lean.get("name") and ctx.library.get(lean["name"]) is not None:
                    lean["status"], lean["library_name"] = "proved", lean["name"]
        await ctx.repo.save(parent)
        cond = parent.extra.get("conditional_proof")
        if isinstance(cond, dict) and cond.get("source") == "literature" and cond.get("verdict") == "proved_modulo":
            await formal.upgrade(ctx, parent)
        ctx.publish("literature.updated", {"dossier_id": parent.id})


# ---------------------------------------------------------------- attachments (read once, D56)
def _attachment_view(ctx, d, a: dict) -> dict:
    from ...literature import attach
    dig = attach.load_digest(ctx, a.get("shelf", ""), a.get("sha", "")) or {}
    return {**a, "state": dig.get("state", "reading"), "verified": bool((dig.get("record") or {}).get("verified")),
            "reference": dig.get("reference"), "transcription": dig.get("transcription"),
            "items": dig.get("items") or [], "version": dig.get("version", "")}


async def list_attachments(request: web.Request) -> web.Response:
    ctx = ctx_of(request)
    d = _dossier(request)
    return ok({"attachments": [_attachment_view(ctx, d, a) for a in d.extra.get("attachments") or []]})


async def _read_bg(ctx, d, a: dict, mode: str, force: bool = False) -> None:
    from ...literature import attach
    try:
        await attach.read(ctx, a["shelf"], a["sha"], mode=mode, force=force, lang=language())
    except Exception:  # noqa: BLE001
        log.exception("reading attachment %s", a.get("name"))
    finally:
        ctx.publish("literature.updated", {"dossier_id": d.id, "attachment": a.get("n")})


async def add_attachment(request: web.Request) -> web.Response:
    """multipart `file` (image / PDF / LaTeX / BibTeX, + `cell`) or JSON {url, cell?} → 201 {attachment, read}.
    A file the project already read is linked only (`read: false`): nothing is read twice."""
    from ...literature import attach
    from ...research.sources import SourceError
    ctx = ctx_of(request)
    d = _dossier(request)
    mode = _mode(ctx, d)
    try:
        if request.content_type.startswith("multipart/"):
            from .research_sources import _read_upload
            name, data, fields = await _read_upload(request)
            entry, fresh = await attach.attach_file(ctx, d, name, data, mode=mode, cell=fields.get("cell", "")[:80])
        else:
            data = await body(request)
            url = str(data.get("url") or "").strip()
            if not re.match(r"^https://\S+$", url):
                return error(400, "bad_url")
            entry, fresh = await attach.attach_url(ctx, d, url, mode=mode, cell=str(data.get("cell") or "")[:80])
    except attach.AttachError as e:
        return error(e.status, e.kind)
    except SourceError as e:
        return error(getattr(e, "status", 400), e.kind)
    m = msg("Pièce jointe {n} : {name}.", n=entry["n"], name=entry["name"][:120])
    d.add_event("info", m["text"], key=m["key"], params=m["params"])
    await ctx.repo.save(d)
    if fresh:
        ctx.spawn(_read_bg(ctx, d, entry, mode))
    ctx.publish("literature.updated", {"dossier_id": d.id, "attachment": entry["n"]})
    return ok({"attachment": _attachment_view(ctx, d, entry), "read": fresh}, status=201)


async def reread_attachment(request: web.Request) -> web.Response:
    """« Relire » : the only way an attachment is read again (new extractor version, better model…)."""
    ctx = ctx_of(request)
    d = _dossier(request)
    try:
        n = int(request.match_info["n"])
    except ValueError:
        return error(400, "bad_id")
    a = next((x for x in d.extra.get("attachments") or [] if x.get("n") == n), None)
    if a is None:
        return error(404, "not_found")
    ctx.spawn(_read_bg(ctx, d, a, _mode(ctx, d), force=True))
    return ok({"started": True}, status=202)


# ---------------------------------------------------------------- Calcul « Demande » attachments (project, D59)
def _project_holder(request):
    from ...literature import attach
    ctx = ctx_of(request)
    pid = valid_id(request.match_info["pid"])
    if ctx.projects.get(pid) is None:
        raise web.HTTPNotFound(text='{"error":"not_found"}', content_type="application/json")
    return attach.ProjectNotebook(ctx, pid)


async def list_project_attachments(request: web.Request) -> web.Response:
    ctx, h = ctx_of(request), _project_holder(request)
    cell = request.query.get("cell", "")
    atts = [a for a in h.extra["attachments"] if not cell or cell in (a.get("cells") or [])]
    return ok({"attachments": [_attachment_view(ctx, h, a) for a in atts]})


async def _read_project_bg(ctx, h, a: dict, mode: str, force: bool = False) -> None:
    from ...literature import attach
    try:
        await attach.read(ctx, a["shelf"], a["sha"], mode=mode, force=force, lang=language())
    except Exception:  # noqa: BLE001
        log.exception("reading attachment %s", a.get("name"))
    finally:
        ctx.publish("calcul.attachments", {"project_id": h.project_id, "attachment": a.get("n")})


async def add_project_attachment(request: web.Request) -> web.Response:
    """Calcul « Demande » paperclip: multipart `file` (+ `cell`) or JSON {url, cell} → 201 {attachment, read}. The
    file becomes a Source of the project and is read once (same digest as a dossier's attachment, SHA-256 +
    extractor version); the cell is linked to it. A cell's request naming « pièce jointe N » gets its quotes."""
    from ...literature import attach
    from ...research.sources import SourceError
    ctx, h = ctx_of(request), _project_holder(request)
    mode = effective_mode_of(ctx, h.project_id)
    try:
        if request.content_type.startswith("multipart/"):
            from .research_sources import _read_upload
            name, data, fields = await _read_upload(request)
            cell = fields.get("cell", "")[:80]
            if cell and not CELL_RE.fullmatch(cell):
                return error(400, "bad_fields", "Champs refusés : {fields}.", fields="cell")
            entry, fresh = await attach.attach_file(ctx, h, name, data, mode=mode)
        else:
            data = await body(request)
            url = str(data.get("url") or "").strip()
            cell = str(data.get("cell") or "")[:80]
            if not re.match(r"^https://\S+$", url):
                return error(400, "bad_url")
            if cell and not CELL_RE.fullmatch(cell):
                return error(400, "bad_fields", "Champs refusés : {fields}.", fields="cell")
            entry, fresh = await attach.attach_url(ctx, h, url, mode=mode)
    except attach.AttachError as e:
        return error(e.status, e.kind)
    except SourceError as e:
        return error(getattr(e, "status", 400), e.kind)
    h.link_cell(entry, cell)
    h.save()
    if fresh:
        ctx.spawn(_read_project_bg(ctx, h, entry, mode))
    ctx.publish("calcul.attachments", {"project_id": h.project_id, "attachment": entry["n"]})
    return ok({"attachment": _attachment_view(ctx, h, entry), "read": fresh}, status=201)


async def unlink_project_attachment(request: web.Request) -> web.Response:
    """Remove the link between a cell and an attachment (the Source and its digest stay in the project)."""
    ctx, h = ctx_of(request), _project_holder(request)
    try:
        n = int(request.match_info["n"])
    except ValueError:
        return error(400, "bad_id")
    a = next((x for x in h.extra["attachments"] if x.get("n") == n), None)
    if a is None:
        return error(404, "not_found")
    cell = request.query.get("cell", "")
    if cell in (a.get("cells") or []):
        a["cells"].remove(cell)
        h.save()
    ctx.publish("calcul.attachments", {"project_id": h.project_id, "attachment": n})
    return ok({"attachment": _attachment_view(ctx, h, a)})


async def reread_project_attachment(request: web.Request) -> web.Response:
    ctx, h = ctx_of(request), _project_holder(request)
    try:
        n = int(request.match_info["n"])
    except ValueError:
        return error(400, "bad_id")
    a = next((x for x in h.extra["attachments"] if x.get("n") == n), None)
    if a is None:
        return error(404, "not_found")
    ctx.spawn(_read_project_bg(ctx, h, a, effective_mode_of(ctx, h.project_id), force=True))
    return ok({"started": True}, status=202)


def effective_mode_of(ctx, pid: str) -> str:
    from ...research.fetch import effective_mode
    return effective_mode(ctx, ctx.projects.get(pid))


def register(app: web.Application, ctx) -> None:
    app[TASKS] = {}
    r = app.router
    r.add_get("/api/calcul/{pid}/attachments", list_project_attachments)
    r.add_post("/api/calcul/{pid}/attachments", add_project_attachment)
    r.add_delete("/api/calcul/{pid}/attachments/{n}", unlink_project_attachment)
    r.add_post("/api/calcul/{pid}/attachments/{n}/reread", reread_project_attachment)
    r.add_get("/api/dossiers/{id}/attachments", list_attachments)
    r.add_post("/api/dossiers/{id}/attachments", add_attachment)
    r.add_post("/api/dossiers/{id}/attachments/{n}/reread", reread_attachment)
    base = "/api/dossiers/{id}/literature"
    r.add_get(base, get_literature)
    r.add_post(base, start_search)
    r.add_post(base + "/stop", stop_search)
    r.add_post(base + "/conditional", conditional_now)
    r.add_post(base + "/items/{item}/source", add_source)
    r.add_post(base + "/items/{item}/cite", cite)
    r.add_post(base + "/items/{item}/prove", prove_item)
    r.add_post("/api/literature/search", plain_search)
    watch: dict = {}

    async def startup(_app):
        watch["task"] = asyncio.create_task(_watch_jobs(app, ctx), name="literature-watch")

    async def cleanup(_app):
        t = watch.get("task")
        if t is not None:
            t.cancel()
            await asyncio.gather(t, return_exceptions=True)
        for task, budget in list(app[TASKS].values()):
            if budget is not None:
                budget.cancel()
            if task is not None and not task.done():
                task.cancel()
    app.on_startup.append(startup)
    app.on_cleanup.append(cleanup)
