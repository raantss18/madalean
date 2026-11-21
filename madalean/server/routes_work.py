"""Projects, dossiers, jobs, library, free Lean check, .tex import, export, split into lemmas."""
from __future__ import annotations

import asyncio
import re
import time

from aiohttp import web

from .. import leancheck, texio
from ..i18n import msg
from ..orchestrator import DossierBusy
from ..pipeline.runner import STAGES, full_plan, parse_split, plan_for_message
from ..prompts import split_messages
from ..repo import dossier_api, dossier_summary
from .common import body, ctx_of, error, ok, valid_id
from .helpers import complete_once

routes = web.RouteTableDef()
PROJECT_FIELDS = {"title": str, "description": str, "workspace": str, "archived": bool, "refs_file": str,
                  "sources": list}
DOSSIER_FIELDS = {"title": str, "project_id": str, "archived": bool, "workspace": str, "kind": str, "refs": list,
                  "source": (dict, type(None)), "uses": list, "retry_parent": bool, "problem": str}
from ..dossiers import KINDS  # noqa: E402  (theorem lemma definition claim conjecture)


def _busy(e: DossierBusy) -> web.Response:
    return web.json_response({"error": "busy", "job": e.job.to_dict(),
                              "message": msg("Une opération est en cours : arrêtez-la d'abord (Échap).")}, status=409)


def _apply(obj, data: dict, fields: dict) -> list[str]:
    bad = []
    for k, v in data.items():
        if k not in fields:
            bad.append(k)
            continue
        if not isinstance(v, fields[k]):
            bad.append(k)
            continue
        setattr(obj, k, v.strip() if isinstance(v, str) and k == "title" else v)
    return bad


# ---------------------------------------------------------------- projects
@routes.get("/api/projects")
async def projects_list(request: web.Request) -> web.Response:
    return ok({"projects": [p.to_dict() for p in ctx_of(request).projects.list()]})


@routes.post("/api/projects")
async def projects_create(request: web.Request) -> web.Response:
    ctx = ctx_of(request)
    data = await body(request)
    title = str(data.get("title", "")).strip()
    if not title:
        return error(400, "title_required")
    p = ctx.projects.store.new(title[:200], str(data.get("description", ""))[:5000], str(data.get("workspace", "")))
    await ctx.projects.save(p)
    return ok({"project": p.to_dict()}, status=201)


def _project(request: web.Request):
    p = ctx_of(request).projects.get(valid_id(request.match_info["id"]))
    if p is None:
        raise web.HTTPNotFound(text='{"error":"not_found"}', content_type="application/json")
    return p


@routes.get("/api/projects/{id}")
async def projects_get(request: web.Request) -> web.Response:
    ctx = ctx_of(request)
    p = _project(request)
    return ok({"project": p.to_dict(), "dossiers": [dossier_summary(d) for d in ctx.repo.list(p.id)]})


@routes.patch("/api/projects/{id}")
async def projects_patch(request: web.Request) -> web.Response:
    ctx = ctx_of(request)
    p = _project(request)
    bad = _apply(p, await body(request), PROJECT_FIELDS)
    if bad:
        return error(400, "bad_fields", "Champs refusés : {fields}.", fields=", ".join(bad))
    await ctx.projects.save(p)
    return ok({"project": p.to_dict()})


@routes.delete("/api/projects/{id}")
async def projects_delete(request: web.Request) -> web.Response:
    ctx = ctx_of(request)
    p = _project(request)
    await ctx.projects.delete(p.id)
    return ok({"ok": True, "undo": f"/api/projects/{p.id}/restore"})


@routes.post("/api/projects/{id}/restore")
async def projects_restore(request: web.Request) -> web.Response:
    p = await ctx_of(request).projects.restore(valid_id(request.match_info["id"]))
    return ok({"project": p.to_dict()}) if p else error(404, "not_found")


# ---------------------------------------------------------------- dossiers
def _dossier(request: web.Request):
    d = ctx_of(request).repo.get(valid_id(request.match_info["id"]))
    if d is None:
        raise web.HTTPNotFound(text='{"error":"not_found"}', content_type="application/json")
    return d


def _plan_arg(raw) -> list[dict] | None:
    if not isinstance(raw, list) or not raw:
        return None
    out = []
    for item in raw[:12]:
        st = item if isinstance(item, str) else item.get("stage") if isinstance(item, dict) else None
        if st not in STAGES:
            return None
        req = item.get("request", "") if isinstance(item, dict) else ""
        step = {"stage": st, "request": str(req)[:4000]}
        if isinstance(item, dict):           # « Prouver quand même » (skip the statement check), Learn mode (S-K)
            step.update({k: True for k in ("force", "learn") if item.get(k) is True})
        out.append(step)
    return out


def _opts(data: dict) -> dict:
    o = {}
    if data.get("mode") in ("local", "auto", "online"):
        o["mode"] = data["mode"]
    if data.get("strategy") in ("goedel", "agent", "auto"):
        o["strategy"] = data["strategy"]
    return o


@routes.get("/api/dossiers")
async def dossiers_list(request: web.Request) -> web.Response:
    ctx = ctx_of(request)
    pid = request.query.get("project")
    return ok({"dossiers": [dossier_summary(d) for d in ctx.repo.list(pid)]})


async def create_dossier(ctx, data: dict, user_event: bool = True) -> tuple[object, object]:
    """Shared by POST /dossiers and split. Returns (dossier, job | None)."""
    problem = str(data.get("problem", "")).strip()[:20000]
    statement = str(data.get("statement", "")).strip()[:100000]
    title = str(data.get("title", "")).strip()[:200]
    ws = str(data.get("workspace", "")) or ctx.settings.workspace
    d = ctx.repo.new(problem, ws, title or ("" if problem else msg("Énoncé écrit à la main")["text"]))
    pid = str(data.get("project_id", ""))
    if pid and ctx.projects.get(pid) is not None:
        d.project_id = pid
    if data.get("parent_id") and ctx.repo.get(str(data["parent_id"])) is not None:
        d.parent_id = str(data["parent_id"])
    if data.get("kind") in KINDS:
        d.kind = data["kind"]
    plan = None
    if statement:
        st = leancheck.prepare_statement(statement)
        # each dossier proves its own theorem name, so library entries never clash (D19)
        old = leancheck.theorem_name(st)
        if data.get("rename", True) and old != d.theorem:
            st = re.sub(rf"\btheorem\s+{re.escape(old)}\b", f"theorem {d.theorem}", st)
        if problem and user_event:
            d.add_event("user", problem, stage="auto")
        idx = d.add_statement(st, source="user")
        m = msg("Énoncé Lean fourni.")
        d.add_event("statement", m["text"], ref=idx, key=m["key"])
        plan = [{"stage": "notes"}, {"stage": "proof"}, {"stage": "explanation"}]
    elif problem:
        if user_event:
            d.add_event("user", problem, stage="auto")
        plan = full_plan()
    await ctx.repo.save(d)
    job = None
    if plan and data.get("start", True):
        job = ctx.orchestrator.submit(d.id, plan, **_opts(data))
    return d, job


@routes.post("/api/dossiers")
async def dossiers_create(request: web.Request) -> web.Response:
    ctx = ctx_of(request)
    data = await body(request)
    try:
        d, job = await create_dossier(ctx, data)
    except leancheck.StatementError as e:
        return web.json_response({"error": "bad_statement", "message": {"key": "", "params": {}, "text": str(e)}},
                                 status=400)
    return ok({"dossier": dossier_api(d), "job": job.to_dict() if job else None}, status=201)


@routes.get("/api/dossiers/{id}")
async def dossiers_get(request: web.Request) -> web.Response:
    ctx = ctx_of(request)
    d = _dossier(request)
    act = ctx.orchestrator.active_for(d.id)
    return ok({"dossier": dossier_api(d), "job": act.to_dict() if act else None,
               "children": [dossier_summary(c) for c in ctx.repo.children(d.id)]})


@routes.patch("/api/dossiers/{id}")
async def dossiers_patch(request: web.Request) -> web.Response:
    ctx = ctx_of(request)
    d = _dossier(request)
    data = await body(request)
    if "kind" in data and data["kind"] not in KINDS:
        return error(400, "bad_fields", "Champs refusés : {fields}.", fields="kind")
    if data.get("project_id") and ctx.projects.get(str(data["project_id"])) is None:
        return error(400, "bad_fields", "Champs refusés : {fields}.", fields="project_id")
    bad = _apply(d, data, DOSSIER_FIELDS)
    if bad:
        return error(400, "bad_fields", "Champs refusés : {fields}.", fields=", ".join(bad))
    d.touch()
    await ctx.repo.save(d)
    return ok({"dossier": dossier_api(d)})


@routes.delete("/api/dossiers/{id}")
async def dossiers_delete(request: web.Request) -> web.Response:
    ctx = ctx_of(request)
    d = _dossier(request)
    act = ctx.orchestrator.active_for(d.id)
    if act:
        return _busy(DossierBusy(act))
    await ctx.repo.delete(d.id)
    return ok({"ok": True, "undo": f"/api/dossiers/{d.id}/restore"})


@routes.post("/api/dossiers/{id}/restore")
async def dossiers_restore(request: web.Request) -> web.Response:
    d = await ctx_of(request).repo.restore(valid_id(request.match_info["id"]))
    return ok({"dossier": dossier_api(d)}) if d else error(404, "not_found")


def _route_available(ctx, mode: str) -> bool:
    try:
        return bool(ctx.brain.candidates("route", mode)) and bool(ctx.brain.candidates("formalize", mode))
    except Exception:  # noqa: BLE001
        return False


@routes.post("/api/dossiers/{id}/message")
async def dossiers_message(request: web.Request) -> web.Response:
    ctx = ctx_of(request)
    d = _dossier(request)
    data = await body(request)
    text = str(data.get("text", "")).strip()[:20000]
    stage = data.get("stage", "auto")
    if not text:
        return error(400, "empty")
    if stage not in ("auto", "statement", "proof", "explanation"):
        return error(400, "bad_stage")
    act = ctx.orchestrator.active_for(d.id)
    if act:
        return _busy(DossierBusy(act))
    opts = _opts(data)
    plan, shown = plan_for_message(d, text, stage, _route_available(ctx, opts.get("mode", ctx.settings.mode)))
    d.add_event("user", text, stage=shown)
    await ctx.repo.save(d)
    job = ctx.orchestrator.submit(d.id, plan, **opts)
    return ok({"job": job.to_dict(), "stage": shown}, status=202)


@routes.post("/api/dossiers/{id}/statement")
async def dossiers_statement(request: web.Request) -> web.Response:
    """The user edited the Lean statement by hand. {code, check?: bool}"""
    ctx = ctx_of(request)
    d = _dossier(request)
    data = await body(request)
    if ctx.orchestrator.active_for(d.id):
        return _busy(DossierBusy(ctx.orchestrator.active_for(d.id)))
    try:
        st = leancheck.prepare_statement(str(data.get("code", "")))
    except leancheck.StatementError as e:
        return web.json_response({"error": "bad_statement", "message": {"key": "", "params": {}, "text": str(e)}},
                                 status=400)
    result = None
    if data.get("check", True):
        ws = ctx.workspace(d.workspace or ctx.settings.workspace)
        if ws is not None:
            r = await ctx.lean.check(st, ws, ctx.settings.compile_timeout_s, None, owner=f"check-{d.id}")
            result = r.to_dict()
    idx = d.add_statement(st, source="user", ok=bool(result is None or result["statement_ok"]))
    m = msg("Énoncé modifié à la main.")
    d.add_event("statement", m["text"], ref=idx, key=m["key"])
    await ctx.repo.save(d)
    return ok({"dossier": dossier_api(d), "check": result})


@routes.post("/api/dossiers/{id}/check")
async def dossiers_check(request: web.Request) -> web.Response:
    """Re-check the current statement ({what:"statement"}) or proof ({what:"proof"}, strict verdict) with Lean."""
    ctx = ctx_of(request)
    d = _dossier(request)
    data = await body(request)
    what = data.get("what", "proof" if d.proof_is_current else "statement")
    ws = ctx.workspace(d.workspace or ctx.settings.workspace)
    if ws is None:
        return error(409, "no_workspace")
    if what == "proof":
        if not d.proof:
            return error(409, "no_proof")
        name = leancheck.theorem_name(d.proof)
        r = await ctx.lean.check(leancheck.with_axiom_probe(d.proof, name), ws, ctx.settings.compile_timeout_s, name,
                                 owner=f"check-{d.id}")
    else:
        if not d.statement:
            return error(409, "no_statement")
        r = await ctx.lean.check(d.statement, ws, ctx.settings.compile_timeout_s, None, owner=f"check-{d.id}")
    return ok({"what": what, "check": r.to_dict()})


@routes.post("/api/dossiers/{id}/run")
async def dossiers_run(request: web.Request) -> web.Response:
    ctx = ctx_of(request)
    d = _dossier(request)
    data = await body(request)
    plan = _plan_arg(data.get("plan"))
    if plan is None:
        return error(400, "bad_plan")
    try:
        job = ctx.orchestrator.submit(d.id, plan, **_opts(data))
    except DossierBusy as e:
        return _busy(e)
    return ok({"job": job.to_dict()}, status=202)


@routes.post("/api/dossiers/{id}/verify")
async def dossiers_verify(request: web.Request) -> web.Response:
    """« Vérifier l'énoncé » on demand: {learn?: bool, mode?}. The verdict arrives as a `check` event (S-K)."""
    ctx = ctx_of(request)
    d = _dossier(request)
    data = await body(request)
    if not d.statement:
        return error(409, "no_statement")
    try:
        job = ctx.orchestrator.submit(d.id, [{"stage": "verify", "learn": data.get("learn") is True}], **_opts(data))
    except DossierBusy as e:
        return _busy(e)
    return ok({"job": job.to_dict()}, status=202)


@routes.post("/api/dossiers/{id}/stop")
async def dossiers_stop(request: web.Request) -> web.Response:
    ctx = ctx_of(request)
    d = _dossier(request)
    return ok({"stopped": await ctx.orchestrator.cancel_dossier(d.id)})


@routes.post("/api/dossiers/{id}/versions/{kind}/{index}/restore")
async def dossiers_version_restore(request: web.Request) -> web.Response:
    ctx = ctx_of(request)
    d = _dossier(request)
    kind = request.match_info["kind"]
    try:
        index = int(request.match_info["index"])
    except ValueError:
        return error(400, "bad_index")
    seq = {"statement": d.statements, "proof": d.proofs, "explanation": d.explanations}.get(kind)
    if seq is None or not 0 <= index < len(seq):
        return error(404, "not_found")
    act = ctx.orchestrator.active_for(d.id)
    if act:
        return _busy(DossierBusy(act))
    d.restore(kind, index)
    d.status = "proved" if d.proof_is_current else ("draft" if d.status == "proved" else d.status)
    what = {"statement": "énoncé", "proof": "preuve", "explanation": "explication"}[kind]
    m = msg("Retour à la version {n} de la {what}.", n=index + 1, what=msg(what)["text"])
    d.add_event("info", m["text"], key=m["key"], params=m["params"])
    await ctx.repo.save(d)
    return ok({"dossier": dossier_api(d)})


@routes.get("/api/dossiers/{id}/jobs")
async def dossiers_jobs(request: web.Request) -> web.Response:
    ctx = ctx_of(request)
    d = _dossier(request)
    jobs = await ctx.orchestrator.history_for(d.id)
    return ok({"jobs": [j.to_dict(raw="raw" in request.query) for j in jobs]})


@routes.post("/api/dossiers/{id}/split")
async def dossiers_split(request: web.Request) -> web.Response:
    """Split into lemmas: {lemmas?: [{title?, statement? | problem?}], n?: int, start?: bool, mode?}. Without
    `lemmas`, a model proposes them (role "prove"). Children run in parallel; when they are finished and at least
    one is proven, the parent is retried with them as library lemmas."""
    ctx = ctx_of(request)
    parent = _dossier(request)
    data = await body(request)
    lemmas = data.get("lemmas")
    model = ""
    if not lemmas:
        if not parent.statement:
            return error(409, "no_statement")
        mode = _opts(data).get("mode", ctx.settings.mode)
        try:
            c = await complete_once(ctx, "prove", split_messages(parent.statement, int(data.get("n", 4) or 4)), mode,
                                    owner=f"split-{parent.id}", max_tokens=4000, temperature=0.6)
        except Exception as e:  # noqa: BLE001
            return error(503, "no_model", "Aucun modèle disponible pour découper l'énoncé ({err}).", err=str(e)[:200])
        lemmas, model = parse_split(c.text), c.model.key
        if not lemmas:
            return error(422, "no_lemmas", "Le modèle n'a proposé aucun lemme utilisable.")
    if not isinstance(lemmas, list) or len(lemmas) > 12:
        return error(400, "bad_lemmas")
    kids, jobs = [], []
    for i, lem in enumerate(lemmas):
        if not isinstance(lem, dict):
            continue
        spec = {"title": str(lem.get("title") or f"{parent.title} — lemme {i + 1}")[:200],
                "statement": lem.get("statement", ""), "problem": lem.get("problem", ""),
                "project_id": parent.project_id, "workspace": parent.workspace, "parent_id": parent.id,
                "kind": "lemma", "start": data.get("start", True), **_opts(data)}
        try:
            d, job = await create_dossier(ctx, spec)
        except leancheck.StatementError:
            continue
        kids.append(d)
        if job:
            jobs.append(job)
    if not kids:
        return error(422, "no_lemmas", "Le modèle n'a proposé aucun lemme utilisable.")
    parent.retry_parent = True
    m = msg("Énoncé découpé en {n} lemmes, prouvés en parallèle ; la preuve sera relancée avec eux.", n=len(kids))
    parent.add_event("info", m["text"], key=m["key"], params=m["params"], model=model)
    await ctx.repo.save(parent)
    return ok({"children": [dossier_api(k) for k in kids], "jobs": [j.to_dict() for j in jobs]}, status=201)


@routes.get("/api/dossiers/{id}/export")
async def dossiers_export(request: web.Request) -> web.StreamResponse:
    from ..export import FORMATS, export_dossier
    from ..runtime.lean import workspace_info
    ctx = ctx_of(request)
    d = _dossier(request)
    fmt = request.query.get("format", "pdf")
    if fmt not in FORMATS:
        return error(400, "bad_format")
    try:                       # references cited by the dossier (research layer, S-E); never blocks the export
        from ..research.biblio import dossier_bibliography
        bib = await asyncio.to_thread(dossier_bibliography, ctx, d)
    except Exception:  # noqa: BLE001
        bib = []
    ex = await export_dossier(d, fmt, lang=ctx.settings.language, ws_info=workspace_info(ctx.workspace(d.workspace)),
                              tmp_root=ctx.paths.exports, bib_entries=bib)
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", ex.filename)[:120] or "export"
    headers = {"Content-Disposition": f'attachment; filename="{safe}"', "X-Madalean-Fallback": ex.fallback or ""}
    return web.Response(body=ex.data, content_type=ex.content_type.split(";")[0], headers=headers)


# ---------------------------------------------------------------- jobs
@routes.get("/api/jobs")
async def jobs_list(request: web.Request) -> web.Response:
    o = ctx_of(request).orchestrator
    return ok({"active": [j.to_dict() for j in o.active()], "recent": [j.to_dict() for j in o.recent(50)]})


@routes.get("/api/jobs/{id}")
async def jobs_get(request: web.Request) -> web.Response:
    j = ctx_of(request).orchestrator.jobs.get(valid_id(request.match_info["id"]))
    return ok({"job": j.to_dict(raw=True)}) if j else error(404, "not_found")


@routes.post("/api/jobs/{id}/cancel")
async def jobs_cancel(request: web.Request) -> web.Response:
    return ok({"cancelled": await ctx_of(request).orchestrator.cancel(valid_id(request.match_info["id"]))})


# ---------------------------------------------------------------- library
@routes.get("/api/library")
async def library_list(request: web.Request) -> web.Response:
    from dataclasses import asdict
    ctx = ctx_of(request)
    return ok({"entries": [asdict(e) for e in ctx.library.entries]})


@routes.delete("/api/library/{name}")
async def library_delete(request: web.Request) -> web.Response:
    from dataclasses import asdict
    ctx = ctx_of(request)
    e = await asyncio.to_thread(ctx.library.remove, request.match_info["name"])
    if e is None:
        return error(404, "not_found")
    ctx.publish("library.updated", {"removed": e.name})
    return ok({"removed": asdict(e)})


@routes.post("/api/library/restore")
async def library_restore(request: web.Request) -> web.Response:
    from ..dossiers import LibEntry
    ctx = ctx_of(request)
    data = await body(request)
    try:
        e = LibEntry(**{k: v for k, v in (data.get("entry") or {}).items() if k in LibEntry.__dataclass_fields__})
    except TypeError:
        return error(400, "bad_entry")
    if ctx.library.get(e.name):
        return error(409, "exists")
    await asyncio.to_thread(ctx.library.restore, e)
    ctx.publish("library.updated", {"added": e.name})
    return ok({"ok": True})


@routes.get("/api/library/export")
async def library_export(request: web.Request) -> web.Response:
    """All results of one workspace as a single Lean file (dependencies first)."""
    from ..dossiers import closure
    ctx = ctx_of(request)
    ws = request.query.get("workspace") or ctx.settings.workspace
    entries = closure(ctx.library, [e for e in ctx.library.entries if e.workspace == ws])
    parts = [leancheck.GOEDEL_HEADER.rstrip(), f"-- Madalean library export — workspace {ws} — "
             f"{time.strftime('%Y-%m-%d')}", ""]
    for e in entries:
        parts += [f"-- {e.title}", e.code.strip(), ""]
    return web.Response(text="\n".join(parts), content_type="text/plain",
                        headers={"Content-Disposition": f'attachment; filename="madalean-library-{re.sub(r"[^A-Za-z0-9_-]", "_", ws)}.lean"'})


# ---------------------------------------------------------------- free check / import
@routes.post("/api/check")
async def free_check(request: web.Request) -> web.Response:
    """{code, workspace?, strict?: bool}: compile a Lean file as is (strict = proof mode with the axiom probe)."""
    ctx = ctx_of(request)
    data = await body(request)
    code = str(data.get("code", ""))
    if not code.strip():
        return error(400, "empty")
    ws = ctx.workspace(str(data.get("workspace", "")) or None)
    if ws is None:
        return error(409, "no_workspace")
    name = None
    if data.get("strict"):
        try:
            name = leancheck.theorem_name(code)
        except leancheck.StatementError:
            return error(400, "no_theorem")
        code = leancheck.with_axiom_probe(code, name)
    r = await ctx.lean.check(code, ws, min(int(data.get("timeout", ctx.settings.compile_timeout_s)), 1800), name)
    return ok({"check": r.to_dict(), "workspace": ws.key})


@routes.post("/api/import/tex")
async def import_tex(request: web.Request) -> web.Response:
    """multipart (field `file`) or JSON {tex}: candidate statements of a .tex file."""
    tex = ""
    if request.content_type.startswith("multipart/"):
        reader = await request.multipart()
        async for part in reader:
            if part.name == "file":
                raw = await part.read(decode=False)
                if len(raw) > 5 * 1024 * 1024:
                    return error(413, "too_large")
                tex = raw.decode("utf-8", "replace")
                break
    else:
        tex = str((await body(request)).get("tex", ""))
    if not tex.strip():
        return error(400, "empty")
    stmts = await asyncio.to_thread(texio.extract_statements, tex)
    return ok({"statements": [{"title": s.title, "body": s.body} for s in stmts]})
