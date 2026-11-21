"""Research workshop API (session S-G): linked notes, conjecture workshop, guided proof design, learning support,
extended update checkers. Reference: docs/RESEARCH_WORKSHOP.md. Plugin hook: docs/API.md §6."""
from __future__ import annotations

import asyncio
import datetime as _dt
import re
import time

from aiohttp import web

from ... import leancheck
from ...i18n import _, msg
from ...logs import get
from ...research.conjectures import ConjectureError, Workshop, public as conj_public
from ...research.learn import LearnError, LearnStore, Tutor
from ...research.notes import NoteError, NoteStore, build_graph, export_notes, lean_blocks, paragraphs
from ...research.proofplan import PlanError, Planner, PlanStore
from ...research.sagebridge import SageBridge
from ..common import body, ctx_of, error, host_only, ok, valid_id

log = get("research")
RW = web.AppKey("research_workshop", object)


class Research:
    def __init__(self, ctx):
        root = ctx.paths.config / "research"
        root.mkdir(parents=True, exist_ok=True)
        self.ctx = ctx
        self.notes = NoteStore(root)
        self.bridge = SageBridge(ctx)
        self.workshop = Workshop(ctx, self.bridge, self.notes)
        self.planner = Planner(ctx, PlanStore(root / "plans"))
        self.tutor = Tutor(ctx, LearnStore(root / "learn"))
        from ...update_checkers.recheck import Rechecker
        self.rechecker = Rechecker(ctx, root / "recheck.json")
        from ...update_checkers.selfupdate import SelfUpdater
        self.selfupdater = SelfUpdater()
        self.auto_tried: set[str] = set()
        self.note_locks: dict[str, asyncio.Lock] = {}
        self.tasks: set[asyncio.Task] = set()


def R(request) -> Research:
    return request.app[RW]


def device_of(request) -> str:
    dev = request["device"]
    return dev.id if dev is not None else "host"


def fail(e: Exception) -> web.Response:
    kind, status = getattr(e, "kind", "error"), getattr(e, "status", 400)
    data = dict(getattr(e, "data", {}) or getattr(e, "params", {}) or {})
    out: dict = {"error": kind, **data}
    key = getattr(e, "key", "")
    if key:
        out["message"] = msg(key, **(getattr(e, "params", {}) or {}))
    return web.json_response(out, status=status, dumps=__import__("json").dumps)


def _int(v, default=None):
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def exec_allowed(request) -> web.Response | None:
    """Experiments execute code on the host: from paired devices only when the host enabled it (host-only setting)."""
    if not request["local"] and not getattr(ctx_of(request).settings, "experiments_remote", False):
        return error(403, "experiments_host_only", "Les expériences exécutent du code sur l'ordinateur hôte : "
                                                   "autorisées seulement depuis l'hôte (réglage).")
    return None


# ================================================================ notes
async def notes_list(request):
    rs = R(request)
    pid = request.query.get("project")
    notes = await asyncio.to_thread(rs.notes.list, pid, request.query.get("trash") == "1", request.query.get("tag"))
    return ok({"notes": [n.summary() for n in notes]})


async def notes_create(request):
    rs, ctx = R(request), ctx_of(request)
    data = await body(request)
    pid = str(data.get("project_id", ""))
    if not pid or ctx.projects.get(pid) is None:
        return error(400, "bad_fields", "Champs refusés : {fields}.", fields="project_id")
    try:
        n = await asyncio.to_thread(rs.notes.create, pid, data.get("title", ""), str(data.get("body", "")),
                                    data.get("tags"), "note", device_of(request))
    except NoteError as e:
        return fail(e)
    ctx.publish("note.updated", {"note": n.to_dict(), "device": device_of(request)})
    return ok({"note": n.to_dict()}, status=201)


def _note(request, include_deleted=True):
    n = R(request).notes.get(valid_id(request.match_info["id"]), include_deleted)
    if n is None:
        raise web.HTTPNotFound(text='{"error":"not_found"}', content_type="application/json")
    return n


async def notes_get(request):
    rs = R(request)
    n = _note(request)
    return ok({"note": n.to_dict(), "backlinks": await asyncio.to_thread(rs.notes.backlinks, n),
               "attachments": await asyncio.to_thread(rs.notes.attachments, n.id)})


async def notes_patch(request):
    rs, ctx = R(request), ctx_of(request)
    n = _note(request)
    data = await body(request)
    bad = [k for k in data if k not in ("base_rev", "title", "body", "tags")]
    if bad:
        return error(400, "bad_fields", "Champs refusés : {fields}.", fields=", ".join(bad))
    dev = device_of(request)
    try:
        new, merged, old = await asyncio.to_thread(rs.notes.update, n.id, _int(data.get("base_rev")),
                                                   title=data.get("title"), body=data.get("body"),
                                                   tags=data.get("tags"), device=dev)
    except NoteError as e:
        return fail(e)
    renamed = []
    if old is not None:
        ctx.publish("note.updated", {"note": new.to_dict(), "device": dev, "merged": merged})
        if old.title != new.title:
            for nid, text in await asyncio.to_thread(rs.notes.rename_links, new.project_id, old.title, new.title,
                                                     new.id):
                other = rs.notes.get(nid)
                try:
                    o2, _m, _o = await asyncio.to_thread(rs.notes.update, nid, other.rev, body=text, device=dev,
                                                         reason="rename")
                except NoteError:
                    continue
                renamed.append(nid)
                ctx.publish("note.updated", {"note": o2.to_dict(), "device": dev, "reason": "rename"})
    return ok({"note": new.to_dict(), "merged": merged, "renamed_links_in": renamed})


async def notes_delete(request):
    rs, ctx = R(request), ctx_of(request)
    n = _note(request)
    if await asyncio.to_thread(rs.notes.delete, n.id) is None:
        return error(404, "not_found")
    ctx.publish("note.deleted", {"id": n.id, "project_id": n.project_id})
    return ok({"ok": True, "undo": f"/api/notes/{n.id}/restore"})


async def notes_restore(request):
    rs, ctx = R(request), ctx_of(request)
    n = await asyncio.to_thread(rs.notes.restore, valid_id(request.match_info["id"]))
    if n is None:
        return error(404, "not_found")
    ctx.publish("note.updated", {"note": n.to_dict(), "device": device_of(request), "reason": "restore"})
    return ok({"note": n.to_dict()})


async def notes_versions(request):
    n = _note(request)
    return ok({"versions": await asyncio.to_thread(R(request).notes.versions, n.id), "rev": n.rev})


async def notes_version(request):
    n = _note(request)
    v = await asyncio.to_thread(R(request).notes.version, n.id, _int(request.match_info["rev"], -1))
    return ok({"version": v}) if v else error(404, "not_found")


async def notes_version_restore(request):
    rs, ctx = R(request), ctx_of(request)
    n = _note(request)
    v = await asyncio.to_thread(rs.notes.version, n.id, _int(request.match_info["rev"], -1))
    if v is None:
        return error(404, "not_found")
    data = await body(request)
    try:
        new, merged, old = await asyncio.to_thread(rs.notes.update, n.id, _int(data.get("base_rev"), n.rev),
                                                   title=v["title"], body=v["body"], tags=v["tags"],
                                                   device=device_of(request), reason=f"restore {v['rev']}")
    except NoteError as e:
        return fail(e)
    ctx.publish("note.updated", {"note": new.to_dict(), "device": device_of(request), "reason": "restore"})
    return ok({"note": new.to_dict()})


async def notes_diff(request):
    from ...research.notes import diff_text
    rs = R(request)
    n = _note(request)
    a = _int(request.query.get("from"), max(1, n.rev - 1))
    b = _int(request.query.get("to"), n.rev)
    va, vb = rs.notes.version(n.id, a), rs.notes.version(n.id, b)
    if va is None or vb is None:
        return error(404, "not_found")
    return ok({"from": a, "to": b, "diff": diff_text(va["body"], vb["body"], f"rev {a}", f"rev {b}"),
               "title_changed": va["title"] != vb["title"], "titles": [va["title"], vb["title"]]})


async def notes_search(request):
    q = request.query.get("q", "")
    return ok({"results": await asyncio.to_thread(R(request).notes.search, q, request.query.get("project"))})


async def notes_attach(request):
    rs = R(request)
    n = _note(request, include_deleted=False)
    if not request.content_type.startswith("multipart/"):
        return error(400, "bad_fields", "Champs refusés : {fields}.", fields="file")
    reader = await request.multipart()
    from ...research.notes import MAX_ATTACHMENT
    async for part in reader:
        if part.name != "file":
            continue
        data = bytearray()
        while True:
            chunk = await part.read_chunk(65536)
            if not chunk:
                break
            data += chunk
            if len(data) > MAX_ATTACHMENT:
                return error(413, "too_large")
        try:
            meta = await asyncio.to_thread(rs.notes.add_attachment, n.id, part.filename or "file", bytes(data))
        except NoteError as e:
            return fail(e)
        return ok({"attachment": meta}, status=201)
    return error(400, "empty")


async def notes_attachments(request):
    n = _note(request)
    return ok({"attachments": await asyncio.to_thread(R(request).notes.attachments, n.id)})


async def attachment_get(request):
    got = await asyncio.to_thread(R(request).notes.attachment, request.match_info["aid"])
    if got is None:
        return error(404, "not_found")
    meta, path = got
    disp = "inline" if meta["mime"].startswith("image/") else "attachment"
    safe = re.sub(r"[^\w.\- ]", "_", meta["name"])[:80]
    return web.FileResponse(path, headers={
        "Content-Type": meta["mime"], "Content-Disposition": f'{disp}; filename="{safe}"',
        "X-Content-Type-Options": "nosniff", "Content-Security-Policy": "default-src 'none'; sandbox",
        "Cache-Control": "private, max-age=86400"})


async def attachment_delete(request):
    if not await asyncio.to_thread(R(request).notes.delete_attachment, request.match_info["aid"]):
        return error(404, "not_found")
    return ok({"ok": True, "undo": f"/api/attachments/{request.match_info['aid']}/restore"})


async def attachment_restore(request):
    if not await asyncio.to_thread(R(request).notes.restore_attachment, request.match_info["aid"]):
        return error(404, "not_found")
    return ok({"ok": True})


def _project_ws(ctx, pid: str):
    p = ctx.projects.get(pid)
    return ctx.workspace((p.workspace if p else "") or ctx.settings.workspace)


async def notes_lean_check(request):
    """Compile the note's ```lean blocks (or one: {block}) with the project's workspace; results stored per block."""
    rs, ctx = R(request), ctx_of(request)
    n = _note(request, include_deleted=False)
    data = await body(request)
    blocks = lean_blocks(n.body)
    if data.get("block") is not None:
        blocks = [b for b in blocks if b.index == _int(data.get("block"))]
    if not blocks:
        return error(409, "no_lean_block", "Cette note ne contient aucun bloc ```lean.")
    ws = _project_ws(ctx, n.project_id)
    if ws is None:
        return error(409, "no_workspace")
    lk = rs.note_locks.setdefault(n.id, asyncio.Lock())
    if lk.locked():
        return error(409, "busy", "Une vérification est déjà en cours pour cette note.")
    out = []
    async with lk:
        for b in blocks:
            code, offset = b.code, 0
            if not re.search(r"(?m)^\s*import\s", code) and ws.has_mathlib():
                code = leancheck.GOEDEL_HEADER + code
                offset = leancheck.GOEDEL_HEADER.count("\n")
            r = await ctx.lean.check(code, ws, ctx.settings.compile_timeout_s, None, owner=f"note-{n.id}")
            d = r.to_dict()
            res = {"ok": d["statement_ok"] and not d["has_sorry"], "statement_ok": d["statement_ok"],
                   "has_sorry": d["has_sorry"], "summary": d["summary"], "seconds": d["seconds"],
                   "errors": [{**e, "line": e["line"] - offset, "note_line": e["line"] - offset + b.start_line - 1}
                              for e in d["errors"]],
                   "timed_out": d["timed_out"], "infra_error": d["infra_error"], "workspace": ws.key,
                   "t": time.time(), "hash": b.hash, "index": b.index}
            await asyncio.to_thread(rs.notes.set_lean_result, n.id, b.hash, res)
            out.append(res)
    n2 = rs.notes.get(n.id)
    ctx.publish("note.updated", {"note": n2.to_dict(), "device": device_of(request), "reason": "lean"})
    return ok({"results": out, "note": n2.to_dict()})


async def notes_to_dossier(request):
    """Turn a Lean block ({block}) or a paragraph ({paragraph}) into a dossier; a link is added below it."""
    from ..routes_work import create_dossier
    from ...repo import dossier_api
    rs, ctx = R(request), ctx_of(request)
    n = _note(request, include_deleted=False)
    data = await body(request)
    statement, problem, anchor = "", "", ""
    if data.get("block") is not None:
        b = next((b for b in lean_blocks(n.body) if b.index == _int(data["block"])), None)
        if b is None:
            return error(404, "not_found")
        statement, anchor = b.code, b.code
        problem = str(data.get("problem", ""))
    elif data.get("paragraph") is not None:
        ps = paragraphs(n.body)
        i = _int(data["paragraph"], -1)
        if not 0 <= i < len(ps):
            return error(404, "not_found")
        problem, anchor = ps[i], ps[i]
    else:
        problem = str(data.get("text", "")).strip()
    if not (statement or problem):
        return error(400, "empty")
    kind = data.get("kind") if data.get("kind") in ("theorem", "lemma", "definition", "claim", "conjecture") \
        else "theorem"
    spec = {"problem": problem[:20000], "statement": statement, "project_id": n.project_id,
            "title": str(data.get("title", ""))[:200], "kind": kind, "start": bool(data.get("start", False)),
            "workspace": (_project_ws(ctx, n.project_id).key if _project_ws(ctx, n.project_id) else "")}
    if not re.search(r"(?m)^\s*(theorem|lemma|example)\b", statement or ""):
        spec["statement"] = ""
        spec["problem"] = (problem or statement)[:20000]
    try:
        d, job = await create_dossier(ctx, spec)
    except leancheck.StatementError as e:
        return web.json_response({"error": "bad_statement", "message": {"key": "", "params": {}, "text": str(e)}},
                                 status=400)
    d.extra["from_note"] = {"note": n.id, "rev": n.rev}
    await ctx.repo.save(d)
    note = n
    if data.get("link", True) and anchor:
        pos = n.body.find(anchor)
        end = n.body.find("\n```", pos + len(anchor) - 1) if data.get("block") is not None else pos + len(anchor)
        end = n.body.find("\n", end + 1) if data.get("block") is not None else end
        end = len(n.body) if end < 0 else end
        new_body = n.body[:end] + f"\n\n→ [[dossier:{d.id}|{d.title}]]\n" + n.body[end:]
        try:
            note, _m, _o = await asyncio.to_thread(rs.notes.update, n.id, n.rev, body=new_body,
                                                   device=device_of(request), reason="to-dossier")
            ctx.publish("note.updated", {"note": note.to_dict(), "device": device_of(request)})
        except NoteError:
            pass
    return ok({"dossier": dossier_api(d), "job": job.to_dict() if job else None, "note": note.to_dict()},
              status=201)


async def notes_export(request):
    rs, ctx = R(request), ctx_of(request)
    n = _note(request, include_deleted=False)
    return await _export(request, [n], n.title)


async def notebook_export(request):
    rs, ctx = R(request), ctx_of(request)
    pid = valid_id(request.match_info["pid"])
    p = ctx.projects.get(pid)
    if p is None:
        return error(404, "not_found")
    notes = await asyncio.to_thread(rs.notes.list, pid)
    if not notes:
        return error(409, "empty")
    return await _export(request, notes, p.title)


async def _export(request, notes, title):
    ctx = ctx_of(request)
    fmt = request.query.get("format", "md")
    if fmt not in ("md", "html", "pdf"):
        return error(400, "bad_format")
    ex = await export_notes(notes, title, fmt, ctx.settings.language, ctx.paths.exports)
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", ex.filename)[:120] or "notes"
    return web.Response(body=ex.data, content_type=ex.content_type.split(";")[0],
                        headers={"Content-Disposition": f'attachment; filename="{safe}"',
                                 "X-Madalean-Fallback": ex.fallback or ""})


async def project_graph(request):
    rs, ctx = R(request), ctx_of(request)
    pid = valid_id(request.match_info["pid"])
    if ctx.projects.get(pid) is None:
        return error(404, "not_found")
    q = request.query
    kinds = set(q.get("kinds", "note,dossier,source").split(",")) & {"note", "dossier", "source"}
    edges = set(q.get("edges", "link,uses,cites").split(",")) & {"link", "uses", "cites"}
    sources = []
    try:
        from ...research import sources as src_mod     # session S-E (optional)
        for fn in ("list_sources", "sources_for_project", "list"):
            f = getattr(src_mod, fn, None)
            if callable(f):
                res = f(ctx, pid)
                res = await res if asyncio.iscoroutine(res) else res
                sources = [s if isinstance(s, dict) else getattr(s, "__dict__", {}) for s in (res or [])]
                break
    except Exception:  # noqa: BLE001 (sources library absent: cited keys appear as `missing` nodes)
        sources = []
    g = await asyncio.to_thread(build_graph, rs.notes, pid, ctx.repo.list(pid), sources, ctx.library, kinds or None,
                                edges or None, q.get("tag") or None, q.get("orphans", "1") != "0")
    return ok(g)


async def project_daily(request):
    rs, ctx = R(request), ctx_of(request)
    pid = valid_id(request.match_info["pid"])
    if ctx.projects.get(pid) is None:
        return error(404, "not_found")
    data = await body(request)
    try:
        day = _dt.date.fromisoformat(str(data.get("date") or _dt.date.today().isoformat()))
    except ValueError:
        return error(400, "bad_fields", "Champs refusés : {fields}.", fields="date")
    title = _("Journal de recherche — {date}").format(date=day.isoformat())
    n = rs.notes.by_title(pid, title)
    created = False
    if n is None:
        t0 = time.mktime(day.timetuple())
        touched = [d for d in ctx.repo.list(pid) if t0 <= d.updated < t0 + 86400]
        lines = [f"## {day.isoformat()}", "", _("Objectif du jour :"), "", "- ", "", _("Dossiers travaillés :"), ""]
        lines += [f"- [[dossier:{d.id}|{d.title}]] — {d.status}" for d in touched] or ["- "]
        lines += ["", _("Idées, questions :"), "", "- ", "", "#journal"]
        n = await asyncio.to_thread(rs.notes.create, pid, title, "\n".join(lines) + "\n", ["journal"], "daily",
                                    device_of(request))
        created = True
        ctx.publish("note.updated", {"note": n.to_dict(), "device": device_of(request)})
    return ok({"note": n.to_dict(), "created": created}, status=201 if created else 200)


async def project_tags(request):
    rs = R(request)
    pid = valid_id(request.match_info["pid"])
    counts: dict[str, int] = {}
    for n in await asyncio.to_thread(rs.notes.list, pid):
        for t in n.all_tags:
            counts[t] = counts.get(t, 0) + 1
    return ok({"tags": [{"tag": t, "count": c} for t, c in sorted(counts.items(), key=lambda x: (-x[1], x[0]))]})


async def dossier_notes(request):
    did = valid_id(request.match_info["id"])
    notes = await asyncio.to_thread(R(request).notes.referencing, "dossier", did)
    return ok({"notes": [n.summary() for n in notes]})


# ================================================================ conjectures
def _conj(request):
    try:
        return R(request).workshop.get(valid_id(request.match_info["id"]))
    except ConjectureError as e:
        raise web.HTTPNotFound(text='{"error":"not_found"}', content_type="application/json") from e


async def conj_list(request):
    ctx = ctx_of(request)
    from ...research.conjectures import is_conjecture
    pid = request.query.get("project")
    return ok({"conjectures": [conj_public(d) for d in ctx.repo.list(pid) if is_conjecture(d)]})


async def conj_generate(request):
    rs, ctx = R(request), ctx_of(request)
    pid = valid_id(request.match_info["pid"])
    if ctx.projects.get(pid) is None:
        return error(404, "not_found")
    data = await body(request)

    def lst(k):
        v = data.get(k) or []
        return [str(x) for x in v][:20] if isinstance(v, list) else []
    try:
        res = await rs.workshop.generate(pid, note_ids=lst("note_ids"), dossier_ids=lst("dossier_ids"),
                                         library=lst("library"), source_keys=lst("source_keys"),
                                         n=_int(data.get("n"), 5), mode=data.get("mode") if data.get("mode") in
                                         ("local", "auto", "online") else None)
    except Exception as e:  # noqa: BLE001
        log.exception("conjecture generation failed")
        return error(503, "no_model", "Aucun modèle disponible ({err}).", err=str(e)[:200])
    return ok(res)


async def conj_create(request):
    rs, ctx = R(request), ctx_of(request)
    data = await body(request)
    try:
        d = await rs.workshop.create(str(data.get("project_id", "")), str(data.get("statement", "")),
                                     motivation=str(data.get("motivation", "")), lean=str(data.get("lean") or ""),
                                     title=str(data.get("title", "")), origin=data.get("origin")
                                     if isinstance(data.get("origin"), dict) else {}, model=str(data.get("model", "")),
                                     device=device_of(request))
    except ConjectureError as e:
        return fail(e)
    except leancheck.StatementError as e:
        return web.json_response({"error": "bad_statement", "message": {"key": "", "params": {}, "text": str(e)}},
                                 status=400)
    return ok({"conjecture": conj_public(d)}, status=201)


async def conj_get(request):
    return ok({"conjecture": conj_public(_conj(request))})


async def conj_lean(request):
    rs = R(request)
    d = _conj(request)
    data = await body(request)
    if ctx_of(request).orchestrator.active_for(d.id):
        return error(409, "busy")
    try:
        res = await rs.workshop.set_lean(d, str(data.get("code", "")))
    except leancheck.StatementError as e:
        return web.json_response({"error": "bad_statement", "message": {"key": "", "params": {}, "text": str(e)}},
                                 status=400)
    return ok({"conjecture": conj_public(d), "check": res})


async def conj_run_pipeline(request, plan):
    from ...orchestrator import DossierBusy
    ctx = ctx_of(request)
    d = _conj(request)
    data = await body(request)
    o = {}
    if data.get("mode") in ("local", "auto", "online"):
        o["mode"] = data["mode"]
    if data.get("strategy") in ("goedel", "agent", "auto"):
        o["strategy"] = data["strategy"]
    if plan[0]["stage"] == "understand" and not d.problem:
        d.problem = rs_statement(d)
    try:
        job = ctx.orchestrator.submit(d.id, plan, **o)
    except DossierBusy as e:
        return web.json_response({"error": "busy", "job": e.job.to_dict()}, status=409)
    return ok({"job": job.to_dict()}, status=202)


def rs_statement(d) -> str:
    from ...research.conjectures import data_of
    return data_of(d)["statement_nl"]


async def conj_formalize(request):
    return await conj_run_pipeline(request, [{"stage": "understand"}, {"stage": "statement"}])


async def conj_prove(request):
    d = _conj(request)
    if not d.statement:
        return error(409, "no_statement")
    return await conj_run_pipeline(request, [{"stage": "proof"}, {"stage": "explanation"}])


async def exp_draft(request):
    rs = R(request)
    d = _conj(request)
    data = await body(request)
    try:
        exp = await rs.workshop.draft_experiment(d, kind=str(data.get("kind", "counterexample")),
                                                 language=str(data.get("language", "sage")),
                                                 mode=data.get("mode") if data.get("mode") in
                                                 ("local", "auto", "online") else None,
                                                 code=str(data.get("code") or ""), device=device_of(request))
    except ConjectureError as e:
        return fail(e)
    except Exception as e:  # noqa: BLE001
        return error(503, "no_model", "Aucun modèle disponible ({err}).", err=str(e)[:200])
    return ok({"experiment": exp, "approval_required": not ctx_of(request).settings.experiments_auto}, status=201)


async def exp_edit(request):
    d = _conj(request)
    data = await body(request)
    try:
        exp = await R(request).workshop.edit_experiment(d, request.match_info["eid"], str(data.get("code", "")))
    except ConjectureError as e:
        return fail(e)
    return ok({"experiment": exp})


async def exp_approve(request):
    if (r := exec_allowed(request)) is not None:
        return r
    d = _conj(request)
    data = await body(request)
    try:
        exp = await R(request).workshop.approve(d, request.match_info["eid"], str(data.get("code_hash", "")),
                                                device_of(request))
    except ConjectureError as e:
        return fail(e)
    return ok({"experiment": exp})


async def exp_reject(request):
    d = _conj(request)
    try:
        exp = await R(request).workshop.reject(d, request.match_info["eid"])
    except ConjectureError as e:
        return fail(e)
    return ok({"experiment": exp})


async def exp_run(request):
    if (r := exec_allowed(request)) is not None:
        return r
    rs, ctx = R(request), ctx_of(request)
    d = _conj(request)
    data = await body(request)
    eid = request.match_info["eid"]
    try:
        exp = rs.workshop._exp(d, eid)
    except ConjectureError as e:
        return fail(e)
    if not rs.workshop.may_run(exp):
        return error(403, "not_approved", "Cette expérience exécute du code sur l'ordinateur hôte : relisez-la et "
                                          "approuvez-la d'abord.")
    if rs.workshop.lock(d.id).locked():
        return error(409, "busy", "Une opération est en cours : arrêtez-la d'abord (Échap).")
    timeout = max(1.0, min(float(data.get("timeout") or 60), 1800.0))

    async def run():
        try:
            await rs.workshop.run_experiment(d, eid, timeout=timeout, device=device_of(request))
        except ConjectureError as e:
            ctx.publish("toast", {"level": "warn", **msg("Expérience refusée : {why}.", why=e.kind)})
        except Exception as e:  # noqa: BLE001
            log.exception("experiment failed")
            ctx.publish("toast", {"level": "error", **msg("Erreur interne : {err}", err=str(e)[:300])})
    t = ctx.spawn(run())
    rs.workshop.running[d.id] = t
    return ok({"started": True, "experiment_id": eid}, status=202)


async def exp_status(request):
    ctx = ctx_of(request)
    br = R(request).bridge
    return ok({"available": await asyncio.to_thread(br.available), "sandbox": br.sandbox_kind,
               "auto": bool(ctx.settings.experiments_auto), "remote_allowed": bool(ctx.settings.experiments_remote),
               "jupyter": ctx.jupyter.status()["state"], "workdir": str(br.workroot)})


async def conj_lean_cases(request):
    d = _conj(request)
    data = await body(request)
    cases = data.get("cases") if isinstance(data.get("cases"), list) else None
    try:
        entry = await R(request).workshop.lean_cases(d, cases, _int(data.get("bounded"), 0) or 0,
                                                     device=device_of(request))
    except ConjectureError as e:
        return fail(e)
    return ok({"entry": entry, "conjecture": conj_public(d)})


async def conj_refute_lean(request):
    """Lean check of a witness: ¬ statement closed at {witness} (no kernel involved)."""
    d = _conj(request)
    data = await body(request)
    w = data.get("witness")
    if not isinstance(w, dict) or not d.statement:
        return error(400, "bad_fields", "Champs refusés : {fields}.", fields="witness")
    return ok(await R(request).workshop.lean_refute(d, w))


async def conj_literature(request):
    d = _conj(request)
    return ok({"result": await R(request).workshop.literature(d, device_of(request))})


async def conj_promote(request):
    d = _conj(request)
    try:
        d = await R(request).workshop.promote(d, device_of(request))
    except ConjectureError as e:
        return fail(e)
    return ok({"conjecture": conj_public(d)})


# ================================================================ proof plans
def _dossier(request):
    d = ctx_of(request).repo.get(valid_id(request.match_info["id"]))
    if d is None:
        raise web.HTTPNotFound(text='{"error":"not_found"}', content_type="application/json")
    return d


async def plan_get(request):
    d = _dossier(request)
    p = R(request).planner.public(d.id)
    return ok({"plan": p}) if p else error(404, "no_plan")


async def plan_create(request):
    d = _dossier(request)
    return ok({"plan": R(request).planner.create_empty(d, device_of(request))}, status=201)


async def _plan_call(request, fn):
    try:
        res = fn()
        res = await res if asyncio.iscoroutine(res) else res
    except PlanError as e:
        return fail(e)
    return ok({"plan": res} if "nodes" in (res or {}) else res)


async def plan_draft(request):
    d = _dossier(request)
    data = await body(request)
    mode = data.get("mode") if data.get("mode") in ("local", "auto", "online") else None
    try:
        p = await R(request).planner.draft(d, hint=str(data.get("hint", ""))[:4000],
                                           sketch=str(data.get("sketch", ""))[:20000], mode=mode,
                                           force=bool(data.get("force")), device=device_of(request))
    except PlanError as e:
        return fail(e)
    except Exception as e:  # noqa: BLE001
        log.exception("plan draft failed")
        return error(503, "no_model", "Aucun modèle disponible ({err}).", err=str(e)[:200])
    return ok({"plan": p}, status=201)


async def plan_node_add(request):
    d = _dossier(request)
    data = await body(request)
    return await _plan_call(request, lambda: R(request).planner.add_node(
        d.id, str(data.get("parent", "")), data, data.get("index"), _int(data.get("base_rev")), device_of(request)))


async def plan_node_edit(request):
    d = _dossier(request)
    data = await body(request)
    base = _int(data.pop("base_rev", None))
    return await _plan_call(request, lambda: R(request).planner.edit_node(
        d.id, request.match_info["nid"], data, base, device_of(request)))


async def plan_node_delete(request):
    d = _dossier(request)
    return await _plan_call(request, lambda: R(request).planner.delete_node(
        d.id, request.match_info["nid"], _int(request.query.get("base_rev")), device_of(request)))


async def plan_node_move(request):
    d = _dossier(request)
    data = await body(request)
    return await _plan_call(request, lambda: R(request).planner.move_node(
        d.id, request.match_info["nid"], str(data.get("parent", "")), data.get("index"), _int(data.get("base_rev")),
        device_of(request)))


async def plan_accept(request, status="accepted"):
    d = _dossier(request)
    data = await body(request)
    nodes = [str(x) for x in data.get("nodes") or []] if isinstance(data.get("nodes"), list) else []
    return await _plan_call(request, lambda: R(request).planner.set_status(d.id, nodes, status,
                                                                          _int(data.get("base_rev")),
                                                                          device_of(request)))


async def plan_reject(request):
    return await plan_accept(request, "rejected")


async def plan_submit(request):
    d = _dossier(request)
    data = await body(request)
    nodes = [str(x) for x in data["nodes"]] if isinstance(data.get("nodes"), list) else None
    mode = data.get("mode") if data.get("mode") in ("local", "auto", "online") else None
    return await _plan_call(request, lambda: R(request).planner.submit(d.id, nodes, _int(data.get("base_rev")),
                                                                      device_of(request), mode))


async def plan_cancel(request):
    d = _dossier(request)
    return await _plan_call(request, lambda: R(request).planner.cancel(d.id, request.match_info["nid"],
                                                                      device_of(request)))


async def plan_replan(request):
    d = _dossier(request)
    data = await body(request)
    try:
        p = await R(request).planner.replan(d.id, request.match_info["nid"], hint=str(data.get("hint", ""))[:4000],
                                            base_rev=_int(data.get("base_rev")), device=device_of(request))
    except PlanError as e:
        return fail(e)
    except Exception as e:  # noqa: BLE001
        return error(503, "no_model", "Aucun modèle disponible ({err}).", err=str(e)[:200])
    return ok({"plan": p})


async def plan_admit(request, admit=True):
    d = _dossier(request)
    data = await body(request)
    pl = R(request).planner
    fn = pl.admit if admit else pl.unadmit
    return await _plan_call(request, lambda: fn(d.id, request.match_info["nid"], _int(data.get("base_rev")),
                                                device_of(request)))


async def plan_unadmit(request):
    return await plan_admit(request, False)


async def plan_prove_modulo(request):
    d = _dossier(request)
    data = await body(request)
    try:
        res = await R(request).planner.prove_modulo(d.id, str(data["node"]) if data.get("node") else None,
                                                    attempts=_int(data.get("attempts"), 4) or 4,
                                                    code=str(data["code"]) if data.get("code") else None)
    except PlanError as e:
        return fail(e)
    return ok({**res, "plan": R(request).planner.public(d.id)})


async def plan_analyse(request):
    """« Découper ce théorème » (root) / « Redécouper » (a node): tracks drafted by the model, gated by Lean (S-L)."""
    d = _dossier(request)
    data = await body(request)
    mode = data.get("mode") if data.get("mode") in ("local", "auto", "online") else None
    try:
        p = await R(request).planner.analyse(d.id, str(data["node"]) if data.get("node") else None,
                                             hint=str(data.get("hint", ""))[:4000],
                                             sketch=str(data.get("sketch", ""))[:20000], mode=mode,
                                             base_rev=_int(data.get("base_rev")), force=bool(data.get("force")),
                                             device=device_of(request))
    except PlanError as e:
        return fail(e)
    except Exception as e:  # noqa: BLE001
        log.exception("plan analysis failed")
        return error(503, "no_model", "Aucun modèle disponible ({err}).", err=str(e)[:200])
    return ok({"plan": p})


async def plan_validate(request):
    d = _dossier(request)
    data = await body(request)
    return await _plan_call(request, lambda: R(request).planner.validate(d.id, _int(data.get("base_rev")),
                                                                        device_of(request)))


async def plan_prove(request):
    d = _dossier(request)
    data = await body(request)
    mode = data.get("mode") if data.get("mode") in ("local", "auto", "online") else None
    return await _plan_call(request, lambda: R(request).planner.prove(d.id, _int(data.get("base_rev")),
                                                                     device_of(request), mode))


async def plan_track(request):
    d = _dossier(request)
    data = await body(request)
    return await _plan_call(request, lambda: R(request).planner.switch_track(
        d.id, request.match_info["nid"], str(data["track"]) if data.get("track") else None,
        _int(data.get("base_rev")), device_of(request)))


async def plan_recheck(request):
    d = _dossier(request)
    data = await body(request)
    return await _plan_call(request, lambda: R(request).planner.recheck(
        d.id, request.match_info["nid"], _int(data.get("base_rev")), device_of(request)))


async def plan_version_restore(request):
    d = _dossier(request)
    return await _plan_call(request, lambda: R(request).planner.restore_version(
        d.id, _int(request.match_info["rev"], -1), device_of(request)))


# ================================================================ learn
async def _learn(request, coro_fn):
    try:
        res = coro_fn()
        res = await res if asyncio.iscoroutine(res) else res
    except LearnError as e:
        return fail(e)
    return ok(res)


async def learn_ladder(request):
    did = valid_id(request.match_info["id"])
    return await _learn(request, lambda: R(request).tutor.ladder_state(did, device_of(request)))


async def learn_attempt(request):
    did = valid_id(request.match_info["id"])
    data = await body(request)
    return await _learn(request, lambda: {"entry": R(request).tutor.attempt(
        did, device_of(request), str(data.get("text", "")), _int(data.get("confidence")))})


async def learn_hint(request):
    did = valid_id(request.match_info["id"])
    data = await body(request)
    return await _learn(request, lambda: R(request).tutor.hint(did, _int(data.get("level"), 0) or 0,
                                                               device_of(request), str(data.get("reflection", ""))))


async def learn_token(request):
    q = request.query
    return await _learn(request, lambda: R(request).tutor.explain_token(q.get("name", ""), q.get("workspace")))


async def learn_explain_back(request):
    did = valid_id(request.match_info["id"])
    data = await body(request)
    return await _learn(request, lambda: R(request).tutor.explain_back(did, device_of(request),
                                                                       str(data.get("text", "")),
                                                                       _int(data.get("confidence"))))


async def learn_faded(request):
    did = valid_id(request.match_info["id"])
    data = await body(request)
    return await _learn(request, lambda: R(request).tutor.faded(did, _int(data.get("k"), 1) or 1,
                                                                device_of(request)))


async def learn_erroneous(request):
    did = valid_id(request.match_info["id"])
    return await _learn(request, lambda: R(request).tutor.erroneous(did, device_of(request)))


async def learn_exercise(request):
    did = valid_id(request.match_info["id"])
    t = R(request).tutor
    return await _learn(request, lambda: t.public_exercise(t.exercise(did, request.match_info["eid"])))


async def learn_submit(request):
    did = valid_id(request.match_info["id"])
    data = await body(request)
    fills = data.get("fills") if isinstance(data.get("fills"), list) else None
    return await _learn(request, lambda: R(request).tutor.submit(did, request.match_info["eid"], device_of(request),
                                                                 fills, str(data.get("code", "")),
                                                                 str(data.get("diagnosis", ""))))


UI_LEVELS = {"nudge": 1, "strategy": 2, "lemma": 3, "step": 4, "full": 5}


async def ui_hint(request):
    """Shape used by the web UI (web/src/lib/learn/tutor.ts): {level: nudge|strategy|lemma|step|full, tried, help,
    reflections[]}. `tried` satisfies the retrieve-first gate, the last reflection the reflection gate."""
    did = valid_id(request.match_info["id"])
    data = await body(request)
    lv = data.get("level")
    level = UI_LEVELS.get(lv) if isinstance(lv, str) else _int(lv, 0)
    t = R(request).tutor
    dev = device_of(request)
    refl = [str(x) for x in data.get("reflections") or [] if str(x).strip()] if isinstance(data.get("reflections"),
                                                                                           list) else []
    try:
        st = t.ladder_state(did, dev)
        tried = str(data.get("tried", "")).strip()
        if not st["attempted"] and tried:
            t.attempt(did, dev, (tried + (f"\n[{data.get('help')}]" if data.get("help") else ""))[:4000],
                      _int(data.get("confidence")))
        res = await t.hint(did, level or 0, dev, refl[-1] if refl else "")
    except LearnError as e:
        return fail(e)
    return ok({**res, "level_name": next((k for k, v in UI_LEVELS.items() if v == res["level"]), "")})


async def ui_explain_back(request):
    """UI shape: {target: statement|proof, text, previous[]} → grading + `text` (feedback to display)."""
    did = valid_id(request.match_info["id"])
    data = await body(request)
    target = "statement" if data.get("target") == "statement" else "proof"
    prev = [str(x) for x in data.get("previous") or []] if isinstance(data.get("previous"), list) else []
    return await _learn(request, lambda: R(request).tutor.explain_back(did, device_of(request), str(data.get("text", "")),
                                                                       _int(data.get("confidence")), target, prev))


async def learn_progress(request):
    dev = device_of(request)
    return ok({"device": dev, "entries": R(request).tutor.store.progress(dev, request.query.get("dossier"))})


# ================================================================ updates (re-verification, libraries)
async def recheck_get(request):
    return ok(R(request).rechecker.status())


async def recheck_start(request):
    ctx = ctx_of(request)
    data = await body(request)
    ws = str(data.get("workspace") or ctx.settings.workspace)
    if ctx.workspace(ws) is None:
        return error(409, "no_workspace")
    R(request).rechecker.start(ws, str(data.get("reason") or "manual")[:100])
    return ok({"started": True, "workspace": ws}, status=202)


async def workspace_packages(request):
    from pathlib import Path
    from ...update_checkers.lean import dependents, direct_requires, read_manifest
    ctx = ctx_of(request)
    ws = ctx.workspace(request.match_info["key"])
    if ws is None:
        return error(404, "not_found")
    p = Path(ws.path)
    direct = set(direct_requires(p))
    return ok({"workspace": ws.key, "readonly": ws.readonly, "packages": [
        {"name": x.get("name"), "url": x.get("url"), "rev": x.get("rev"), "input_rev": x.get("inputRev"),
         "direct": x.get("name") in direct, "dependents": dependents(p, x.get("name", ""))}
        for x in read_manifest(p)]})


@host_only
async def workspace_add_library(request):
    """Add a Lean library (git https URL + rev) to a MANAGED workspace: copy → build → verify → switch (installer)."""
    from ...update_checkers import add_library_candidate
    from ...update_checkers.common import CheckError, safe_git_url
    from ... import config
    from pathlib import Path
    ctx = ctx_of(request)
    ws = ctx.workspace(request.match_info["key"])
    if ws is None:
        return error(404, "not_found")
    if ws.readonly or config.WORKSPACES_DIR.resolve() not in Path(ws.path).resolve().parents:
        return error(409, "readonly_workspace", "Cet espace de travail n'est pas géré par Madalean (lecture seule).")
    if ws.key == "lean-prover49":
        return error(409, "pinned", "Épinglé volontairement : Goedel-Prover-V2 a été entraîné sur exactement cette "
                                    "version de Lean et de Mathlib ; la changer dégraderait le prouveur.")
    data = await body(request)
    name, url, rev = str(data.get("name", "")), str(data.get("url", "")), str(data.get("rev", ""))
    if not re.fullmatch(r"[A-Za-z_][\w\-]{0,60}", name) or not re.fullmatch(r"[\w.\-/+]{1,100}", rev):
        return error(400, "bad_fields", "Champs refusés : {fields}.", fields="name, rev")
    try:
        safe_git_url(url)
    except CheckError:
        return error(400, "bad_url")
    c = add_library_candidate(ws, name, url, rev)
    st = ctx.updates.state
    st["candidates"] = [x for x in st.get("candidates", []) if x.get("key") != c.key] + [c.__dict__]
    err = await ctx.updates.install(c.key)
    if err:
        st["candidates"] = [x for x in st.get("candidates", []) if x.get("key") != c.key]
        return error(409 if err in ("busy", "jobs_running") else 404, err)
    return ok(ctx.updates.status(), status=202)


# ================================================================ automatic updates, self-update, system terminal
AUTO_KINDS = ("mathlib", "model", "lake-package")


def quiet(ctx) -> bool:
    """A quiet moment: no job in the orchestrator, no update running."""
    return not ctx.orchestrator.active() and not ctx.updates.busy


async def auto_step(ctx, rs: "Research") -> str | None:
    """One step of the automatic updater (called every minute). Returns what it started, if anything.
    Policy (ARCHITECTURE §16): only with `updates_auto` (default on), only at a quiet moment, one install at a time
    through the verify-then-switch path, each candidate version tried once (a failure changes nothing; the
    manager's toast + last_result tell the user); lean-prover49 is never installable (pinned)."""
    if not getattr(ctx.settings, "updates_auto", True) or ctx.demo or not quiet(ctx):
        return None
    from ...runtime.updates_mgr import auto_install_blocked
    if auto_install_blocked(ctx.paths.config):     # D29: dev checkout / temp config dir / no prefix elan
        return None
    for c in ctx.updates.candidates:
        tag = f"{c.key}:{c.latest}"
        if not c.installable or c.kind not in AUTO_KINDS or tag in rs.auto_tried:
            continue
        if c.spec.get("workspace") == "lean-prover49":
            continue
        rs.auto_tried.add(tag)
        err = await ctx.updates.install(c.key)
        ctx.publish("updates.auto", {"key": c.key, "latest": c.latest, "started": err is None, "error": err or ""})
        return None if err else c.key
    su = rs.selfupdater
    rel = su.state.get("available")
    if rel and running_from(su) and f"madalean:{rel.get('version')}" not in rs.auto_tried and not su.busy:
        rs.auto_tried.add(f"madalean:{rel.get('version')}")
        ctx.spawn(_self_install(ctx, rs, rel, auto=True))
        return "madalean"
    if su.state.get("pending_restart") and running_from(su):
        ctx.publish("selfupdate.status", {"selfupdate": selfupdate_status(rs), "restarting": True})
        await asyncio.sleep(1)
        su.restart()
        return "restart"
    return None


def running_from(su) -> bool:
    """True when this server runs from the self-update layout (<root>/versions/<v>), not from a git checkout."""
    from ... import config
    try:
        return su.versions_dir.resolve() in config.STATION_DIR.resolve().parents
    except OSError:
        return False


def selfupdate_status(rs) -> dict:
    return {**rs.selfupdater.status(), "managed_install": running_from(rs.selfupdater),
            "public_key": rs.selfupdater.public_key.hex()}


async def _self_install(ctx, rs, rel=None, auto=False) -> None:
    from ...update_checkers.selfupdate import UpdateError
    ctx.publish("selfupdate.status", {"selfupdate": selfupdate_status(rs), "installing": True})
    try:
        res = await asyncio.to_thread(rs.selfupdater.install, rel)
        ctx.toast("Madalean {v} est installé et vérifié ; redémarrage au prochain moment calme.", "ok",
                  v=res["version"])
    except UpdateError as e:
        ctx.toast("Mise à jour de Madalean refusée ({why}) : rien n'a changé.", "warn", why=e.kind)
    except Exception as e:  # noqa: BLE001
        log.exception("self-update failed")
        ctx.toast("Mise à jour de Madalean refusée ({why}) : rien n'a changé.", "warn", why=str(e)[:200])
    ctx.publish("selfupdate.status", {"selfupdate": selfupdate_status(rs)})


async def selfupdate_get(request):
    return ok(selfupdate_status(R(request)))


@host_only
async def selfupdate_check(request):
    rs, ctx = R(request), ctx_of(request)
    if ctx.settings.mode == "local":
        return error(409, "local_mode")
    try:
        await asyncio.to_thread(rs.selfupdater.check)
    except Exception as e:  # noqa: BLE001
        return error(503, "check_failed", "Vérification impossible (pas d'Internet ?).", detail=str(e)[:200])
    return ok(selfupdate_status(rs))


@host_only
async def selfupdate_install(request):
    rs, ctx = R(request), ctx_of(request)
    if rs.selfupdater.busy:
        return error(409, "busy")
    if not rs.selfupdater.state.get("available"):
        return error(409, "up_to_date")
    ctx.spawn(_self_install(ctx, rs))
    return ok({"started": True}, status=202)


@host_only
async def selfupdate_rollback(request):
    from ...update_checkers.selfupdate import UpdateError
    rs = R(request)
    try:
        res = await asyncio.to_thread(rs.selfupdater.rollback)
    except UpdateError as e:
        return error(409, e.kind)
    ctx_of(request).publish("selfupdate.status", {"selfupdate": selfupdate_status(rs)})
    return ok({**res, "selfupdate": selfupdate_status(rs)})


@host_only
async def selfupdate_restart(request):
    rs, ctx = R(request), ctx_of(request)
    if not quiet(ctx):
        return error(409, "jobs_running")
    return ok({"restarting": rs.selfupdater.restart()})


@host_only
async def system_terminal(request):
    """« Installer » a system component: open the user's terminal on the exact command (never run by Madalean)."""
    from ...update_checkers import system as sysc
    ctx = ctx_of(request)
    key = "system:" + request.match_info["comp"]
    c = next((c for c in ctx.updates.candidates if c.key == key), None)
    if c is None or not c.spec.get("command"):
        return error(404, "not_found")
    argv = sysc.terminal_argv(c.spec["command"])
    if argv is None:
        return error(409, "no_terminal", "Aucun terminal trouvé : copiez la commande et lancez-la vous-même.",
                     command=c.spec["command"])
    opened = await asyncio.to_thread(sysc.open_terminal, c.spec["command"], _POPEN["fn"])
    return ok({"opened": opened, "command": c.spec["command"], "terminal": argv[0]})


_POPEN = {"fn": __import__("subprocess").Popen}      # replaced by tests: never open a window on the user's screen


# ================================================================ wiring
def register(app: web.Application, ctx) -> None:
    rs = Research(ctx)
    app[RW] = rs
    ctx.research = rs
    a = app.router
    # notes
    a.add_get("/api/notes", notes_list)
    a.add_post("/api/notes", notes_create)
    a.add_get("/api/notes/search", notes_search)
    a.add_get("/api/notes/{id}", notes_get)
    a.add_patch("/api/notes/{id}", notes_patch)
    a.add_delete("/api/notes/{id}", notes_delete)
    a.add_post("/api/notes/{id}/restore", notes_restore)
    a.add_get("/api/notes/{id}/versions", notes_versions)
    a.add_get("/api/notes/{id}/versions/{rev}", notes_version)
    a.add_post("/api/notes/{id}/versions/{rev}/restore", notes_version_restore)
    a.add_get("/api/notes/{id}/diff", notes_diff)
    a.add_post("/api/notes/{id}/attachments", notes_attach)
    a.add_get("/api/notes/{id}/attachments", notes_attachments)
    a.add_post("/api/notes/{id}/lean-check", notes_lean_check)
    a.add_post("/api/notes/{id}/to-dossier", notes_to_dossier)
    a.add_get("/api/notes/{id}/export", notes_export)
    a.add_get("/api/attachments/{aid}", attachment_get)
    a.add_delete("/api/attachments/{aid}", attachment_delete)
    a.add_post("/api/attachments/{aid}/restore", attachment_restore)
    a.add_get("/api/projects/{pid}/graph", project_graph)
    a.add_post("/api/projects/{pid}/notes/daily", project_daily)
    a.add_get("/api/projects/{pid}/tags", project_tags)
    a.add_get("/api/projects/{pid}/notebook/export", notebook_export)
    a.add_get("/api/dossiers/{id}/notes", dossier_notes)
    # conjectures
    a.add_get("/api/conjectures", conj_list)
    a.add_post("/api/conjectures", conj_create)
    a.add_post("/api/projects/{pid}/conjectures/generate", conj_generate)
    a.add_get("/api/experiments/status", exp_status)
    a.add_get("/api/conjectures/{id}", conj_get)
    a.add_post("/api/conjectures/{id}/lean", conj_lean)
    a.add_post("/api/conjectures/{id}/formalize", conj_formalize)
    a.add_post("/api/conjectures/{id}/prove", conj_prove)
    a.add_post("/api/conjectures/{id}/experiments", exp_draft)
    a.add_patch("/api/conjectures/{id}/experiments/{eid}", exp_edit)
    a.add_post("/api/conjectures/{id}/experiments/{eid}/approve", exp_approve)
    a.add_post("/api/conjectures/{id}/experiments/{eid}/reject", exp_reject)
    a.add_post("/api/conjectures/{id}/experiments/{eid}/run", exp_run)
    a.add_post("/api/conjectures/{id}/lean-cases", conj_lean_cases)
    a.add_post("/api/conjectures/{id}/refute-lean", conj_refute_lean)
    a.add_post("/api/conjectures/{id}/literature", conj_literature)
    a.add_post("/api/conjectures/{id}/promote", conj_promote)
    # proof plans
    a.add_get("/api/dossiers/{id}/plan", plan_get)
    a.add_post("/api/dossiers/{id}/plan", plan_create)
    a.add_post("/api/dossiers/{id}/plan/draft", plan_draft)
    a.add_post("/api/dossiers/{id}/plan/nodes", plan_node_add)
    a.add_patch("/api/dossiers/{id}/plan/nodes/{nid}", plan_node_edit)
    a.add_delete("/api/dossiers/{id}/plan/nodes/{nid}", plan_node_delete)
    a.add_post("/api/dossiers/{id}/plan/nodes/{nid}/move", plan_node_move)
    a.add_post("/api/dossiers/{id}/plan/nodes/{nid}/cancel", plan_cancel)
    a.add_post("/api/dossiers/{id}/plan/nodes/{nid}/replan", plan_replan)
    a.add_post("/api/dossiers/{id}/plan/nodes/{nid}/admit", plan_admit)
    a.add_post("/api/dossiers/{id}/plan/nodes/{nid}/unadmit", plan_unadmit)
    a.add_post("/api/dossiers/{id}/plan/accept", plan_accept)
    a.add_post("/api/dossiers/{id}/plan/reject", plan_reject)
    a.add_post("/api/dossiers/{id}/plan/submit", plan_submit)
    a.add_post("/api/dossiers/{id}/plan/prove-modulo", plan_prove_modulo)
    a.add_post("/api/dossiers/{id}/plan/versions/{rev}/restore", plan_version_restore)
    a.add_post("/api/dossiers/{id}/plan/analyse", plan_analyse)
    a.add_post("/api/dossiers/{id}/plan/validate", plan_validate)
    a.add_post("/api/dossiers/{id}/plan/prove", plan_prove)
    a.add_post("/api/dossiers/{id}/plan/nodes/{nid}/track", plan_track)
    a.add_post("/api/dossiers/{id}/plan/nodes/{nid}/recheck", plan_recheck)
    # learn
    a.add_post("/api/dossiers/{id}/hint", ui_hint)
    a.add_post("/api/dossiers/{id}/explain-back", ui_explain_back)
    a.add_get("/api/learn/token", learn_token)
    a.add_get("/api/learn/progress", learn_progress)
    a.add_get("/api/learn/{id}/ladder", learn_ladder)
    a.add_post("/api/learn/{id}/attempt", learn_attempt)
    a.add_post("/api/learn/{id}/hint", learn_hint)
    a.add_post("/api/learn/{id}/explain-back", learn_explain_back)
    a.add_post("/api/learn/{id}/exercises/faded", learn_faded)
    a.add_post("/api/learn/{id}/exercises/erroneous", learn_erroneous)
    a.add_get("/api/learn/{id}/exercises/{eid}", learn_exercise)
    a.add_post("/api/learn/{id}/exercises/{eid}/submit", learn_submit)
    # updates
    a.add_get("/api/updates/recheck", recheck_get)
    a.add_post("/api/updates/recheck", recheck_start)
    a.add_get("/api/workspaces/{key}/packages", workspace_packages)
    a.add_post("/api/workspaces/{key}/libraries", workspace_add_library)
    a.add_get("/api/selfupdate", selfupdate_get)
    a.add_post("/api/selfupdate/check", selfupdate_check)
    a.add_post("/api/selfupdate/install", selfupdate_install)
    a.add_post("/api/selfupdate/rollback", selfupdate_rollback)
    a.add_post("/api/selfupdate/restart", selfupdate_restart)
    a.add_post("/api/updates/system/{comp}/terminal", system_terminal)

    # update checkers + re-verification after any Lean library update
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    from ... import update_checkers
    update_checkers.register(ctx, loop)
    orig = ctx.updates.on_applied

    def on_applied(res: dict) -> None:
        orig(res)
        if res.get("kind") in ("mathlib", "lake-package"):
            ws = res.get("workspace") or "lean-current"
            reason = (f"Mathlib {res.get('tag', '')}" if res.get("kind") == "mathlib"
                      else f"{res.get('package')} {res.get('rev')}")

            async def later():
                await asyncio.sleep(0.5)               # let refresh_workspaces run first
                await ctx.refresh_workspaces()
                await rs.rechecker.run(ws, reason)
            ctx.spawn(later())
    ctx.updates.on_applied = on_applied

    if ctx.demo:
        _demo_brain(ctx)

    async def startup(_app):
        rs.tasks.add(asyncio.create_task(_watch_jobs(ctx, rs)))
        rs.tasks.add(asyncio.create_task(_periodic(ctx, rs)))
        if ctx.demo:
            try:
                await seed_demo(ctx, rs)
            except Exception:  # noqa: BLE001
                log.exception("demo seed (research) failed")

    async def cleanup(_app):
        for t in rs.tasks:
            t.cancel()
        try:
            await rs.bridge.close()
        except Exception:  # noqa: BLE001
            pass
        rs.notes.close()
    app.on_startup.append(startup)
    app.on_cleanup.append(cleanup)


async def _watch_jobs(ctx, rs: Research) -> None:
    q = ctx.bus.subscribe()
    try:
        while True:
            ev = await q.get()
            if ev is None:
                q = ctx.bus.subscribe()
                continue
            if ev.get("type") == "job.updated":
                try:
                    await rs.planner.on_job(ev["job"])
                except Exception:  # noqa: BLE001
                    log.exception("plan watcher")
    finally:
        ctx.bus.unsubscribe(q)


async def _periodic(ctx, rs: Research) -> None:
    """Weekly update check while the server runs for weeks (the manager itself checks at start), kernel reaper."""
    import os
    n = 0
    while True:
        await asyncio.sleep(60)
        n += 1
        if os.environ.get("MADALEAN_NO_UPDATE_CHECK") == "1" or ctx.demo:
            continue
        if n % 10 == 0:
            try:
                await rs.bridge.reap()
                await ctx.updates.maybe_check(ctx.settings.check_updates)
                if ctx.settings.mode != "local" and time.time() - float(rs.selfupdater.state.get("checked") or 0) \
                        > 7 * 86400:
                    await asyncio.to_thread(rs.selfupdater.check)
            except Exception:  # noqa: BLE001
                log.exception("periodic update check")
        try:
            await auto_step(ctx, rs)
        except Exception:  # noqa: BLE001
            log.exception("automatic update step")


# ================================================================ demo mode
def _demo_brain(ctx) -> None:
    from ...research import conjectures, learn, proofplan
    br = ctx.brain
    if not hasattr(br, "responder"):
        return
    base = br.responder

    def responder(role, messages, brain):
        first = next((m.get("content", "") for m in messages if m.get("role") == "user"), "")
        for mod in (conjectures, proofplan, learn):
            ans = mod.demo_answer(first)
            if ans is not None:
                return ans
        return base(role, messages, brain)
    br.responder = responder


async def seed_demo(ctx, rs: Research) -> None:
    """Notes with links, a conjecture with an evidence log (incl. a refuted one), a proof plan tree, a hint ladder."""
    from ...research import conjectures as cj
    projects = ctx.projects.list()
    if not projects or rs.notes.list(projects[0].id):
        return
    p = projects[0]
    proved = next((d for d in ctx.repo.list(p.id) if d.proof_is_current), None)
    draft = next((d for d in ctx.repo.list(p.id) if not d.proof_is_current), None)
    lib = ctx.library.entries[0].name if ctx.library.entries else "Even.add"
    n1 = rs.notes.create(p.id, "Parité — idées", (
        "# Parité\n\nUn entier $n$ est pair s'il existe $k$ tel que $n = 2k$. Voir [[Somme et produit]] et le "
        f"dossier [[dossier:{proved.id if proved else 'x'}|somme de deux pairs]], prouvé (résultat [[lib:{lib}]]).\n\n"
        "Référence : [[@hardy-wright#p12|Hardy & Wright, p. 12]].\n\n```lean\nexample (a b : ℕ) (ha : Even a) "
        "(hb : Even b) : Even (a + b) := Even.add ha hb\n```\n\n#parité #arithmétique\n"), ["démo"])
    rs.notes.create(p.id, "Somme et produit", (
        "Le produit d'un pair par n'importe quel entier est pair ; retour à [[Parité — idées]].\n\nConjecture "
        "testée : [[Polynôme d'Euler]].\n\n#parité\n"))
    rs.notes.create(p.id, "Polynôme d'Euler", "Euler : $n^2 + n + 41$ semble premier… jusqu'à $n = 40$.\n")
    del n1
    # conjectures: one refuted (with a re-verified witness), one tested
    d = await rs.workshop.create(p.id, "Pour tout entier naturel $n$, $n^2 + n + 41$ est premier.",
                                 motivation="Euler, 1772 : premier pour $n = 0, \\dots, 39$.",
                                 title="Polynôme d'Euler", model="local:Qwen3-8B-Q4_K_M.gguf")
    st = leancheck.prepare_statement("theorem euler_poly (n : ℕ) : Nat.Prime (n ^ 2 + n + 41) := by sorry")
    st = st.replace("euler_poly", d.theorem)
    idx = d.add_statement(st, source="user", ok=True)
    d.add_event("statement", "Énoncé Lean de la conjecture.", ref=idx)
    code = cj.demo_answer(cj.MARK + " task=experiment").split("```python\n")[1].split("```")[0]
    import hashlib
    eid = "x-demo0001"
    cj.data_of(d)["experiments"][eid] = {
        "id": eid, "kind": "counterexample", "language": "python", "code": code,
        "predicate": code.split("# SEARCH")[0], "code_hash": hashlib.sha256(code.encode()).hexdigest(),
        "source": "ai", "model": "local:Qwen3-8B-Q4_K_M.gguf", "status": "done",
        "approved": {"hash": hashlib.sha256(code.encode()).hexdigest(), "t": time.time(), "device": "host"},
        "created": time.time(), "runs": [{"t": time.time(), "status": "ok", "verdict": "counterexample",
                                          "seconds": 0.4}], "device": "host"}
    cj.add_evidence(d, "lean_cases", msg("Lean : {k} cas sur {n} vérifiés.", k=10, n=10), verdict="holds",
                    language="lean", data={"proved": 10, "total": 10, "cases": [{"case": {"n": i}, "proved": True,
                                                                                 "errors": []} for i in range(10)]})
    cj.add_evidence(d, "experiment", msg("Expérience ({lang}) : {verdict}.", lang="python", verdict="counterexample"),
                    verdict="counterexample", code=code, language="python",
                    output='MADALEAN_RESULT {"verdict": "counterexample", "witness": {"n": 40}, "cases": 41}\n',
                    data={"experiment_id": eid, "status": "ok", "witness": {"n": 40}, "cases": 41, "sandbox": "bwrap"})
    e = cj.add_evidence(d, "counterexample_check", msg("Contre-exemple {w} : {verdict}.", w='{"n": 40}',
                                                       verdict="refuted"), verdict="refuted", language="python",
                        output="MADALEAN_CHECK False\n",
                        data={"witness": {"n": 40}, "kernel": {"fresh": True, "predicate_false": True},
                              "lean": {"ok": True, "code": cj.negation_file(st, {"n": 40})}})
    cj.data_of(d)["counterexample"] = {"witness": {"n": 40}, "verified": True, "sage": True, "lean": True,
                                       "evidence": e["id"], "t": time.time()}
    await ctx.repo.save(d, publish=False)
    d2 = await rs.workshop.create(p.id, "Pour tout entier naturel $n$, $n^2 + n$ est pair.",
                                  motivation="Produit de deux entiers consécutifs.", title="n² + n est pair")
    cj.add_evidence(d2, "lean_cases", msg("Lean : {k} cas sur {n} vérifiés.", k=10, n=10), verdict="holds",
                    language="lean", data={"proved": 10, "total": 10})
    await ctx.repo.save(d2, publish=False)
    # proof plan tree on the draft dossier
    target = draft or proved
    if target is not None:
        from ...research.proofplan import demo_plan
        rs.planner.store.push(target.id, demo_plan(target), source="ai", model="fake:fake-prove")
    # hint ladder (levels 1-2 cached and revealed for the host)
    if proved is not None:
        from ...research.learn import demo_answer as learn_demo, MARK as LM
        doc = rs.tutor.store.doc(proved.id)
        doc["hints"][str(proved.cur_proof)] = {str(lv): {"text": learn_demo(f"{LM} task=hint level={lv}"),
                                                         "model": "local:Qwen3-8B-Q4_K_M.gguf", "source": "ai",
                                                         "redacted": False, "t": time.time()} for lv in (1, 2)}
        rs.tutor.store.save_doc(proved.id)
        rs.tutor.store.log("host", {"dossier": proved.id, "kind": "attempt", "text": "J'ai essayé omega.",
                                    "confidence": 40})
        for lv in (1, 2):
            rs.tutor.store.log("host", {"dossier": proved.id, "kind": "hint", "level": lv, "proof": proved.cur_proof})


def proofplan_mark() -> str:
    from ...research.proofplan import MARK
    return MARK
