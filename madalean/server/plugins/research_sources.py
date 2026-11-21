"""Research layer, session S-E: sources library, literature search, grounded answers, paper → blueprint, Lean →
article. Routes under `/api/research/…` (reference: docs/RESEARCH_SOURCES.md). Authentication, Origin checks and the
host-only rule come from the server's middleware like every other route."""
from __future__ import annotations

import asyncio
import json
import re
import uuid

from aiohttp import web

from ...i18n import language, msg
from ...logs import get
from ...research import article as art_mod
from ...research import biblio, litsearch, papers, qa
from ...research.fetch import FetchError, effective_mode
from ...research.safety import MAX_UPLOAD
from ...research.sources import GLOBAL, MATHLIB, SourceError, library, summary
from ..common import CTX, body, error, ok, valid_id
from ..helpers import complete_once

log = get("research")
TASKS = web.AppKey("research_tasks", dict)
ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$")
SID_RE = re.compile(r"^s-[0-9a-z]{6,24}$")


# ================================================================ helpers
def _ctx(request):
    return request.app[CTX]


def _lib(request):
    return library(_ctx(request))


def _shelf_id(request) -> str:
    sh = request.match_info["shelf"]
    if sh not in (GLOBAL, MATHLIB):
        valid_id(sh)
    return sh


def _sid(request) -> str:
    sid = request.match_info["sid"]
    if not SID_RE.match(sid) and not re.match(r"^m-[0-9a-f]{10}$", sid):
        raise web.HTTPBadRequest(text='{"error":"bad_id"}', content_type="application/json")
    return sid


def _project(request, name: str = "pid"):
    p = _ctx(request).projects.get(valid_id(request.match_info[name]))
    if p is None:
        raise web.HTTPNotFound(text='{"error":"not_found"}', content_type="application/json")
    return p


def _mode(ctx, data: dict, project=None) -> str:
    mode = effective_mode(ctx, project)
    if data.get("mode") in ("local", "auto", "online") and mode != "local":
        mode = data["mode"]
    return mode


MESSAGES = {
    "not_found": "Introuvable.",
    "local_mode": "Mode local : aucune requête n'est envoyée sur le réseau (changez de mode pour chercher en ligne).",
    "blocked": "Adresse refusée par la sécurité (seuls les services savants publics en https sont contactés).",
    "busy": "Une opération est déjà en cours sur cet élément.",
    "readonly": "Étagère en lecture seule (références de Mathlib).",
    "user_edited": "Ce bloc a été modifié à la main : confirmez pour le régénérer (votre version reste dans "
                   "l'historique).",
    "too_large": "Fichier trop volumineux.",
    "bad_type": "Type de fichier non pris en charge.",
    "bad_archive": "Archive refusée (chemins dangereux, liens ou taille excessive).",
    "unknown_identifier": "Identifiant non reconnu (DOI, arXiv, ISBN, zbMATH, OpenAlex ou adresse web).",
    "no_result": "Aucune notice trouvée pour cet identifiant.",
    "network": "Le service n'a pas répondu ({why}). Réessayez plus tard.",
}


def _err(e: Exception) -> web.Response:
    if isinstance(e, SourceError):
        key = MESSAGES.get(e.kind, "")
        resp = error(e.status, e.kind, key) if key else error(e.status, e.kind)
        if e.info:
            data = json.loads(resp.body)
            data.update({k: v for k, v in e.info.items() if isinstance(v, (str, int, list, dict))})
            return web.json_response(data, status=e.status)
        return resp
    if isinstance(e, art_mod.ArticleError):
        return error(e.status, e.kind, MESSAGES.get(e.kind, "")) if MESSAGES.get(e.kind) else error(e.status, e.kind)
    if isinstance(e, FetchError):
        if e.kind == "local_mode":
            return error(409, "local_mode", MESSAGES["local_mode"])
        if e.kind == "blocked":
            return error(400, "blocked", MESSAGES["blocked"])
        if e.status == 404:
            return error(404, "no_result", MESSAGES["no_result"])
        return error(502, "network", MESSAGES["network"], why=f"{e.kind}{' ' + str(e.status) if e.status else ''}")
    if isinstance(e, litsearch.NotFound):
        return error(404, "no_result", MESSAGES["no_result"])
    raise e


def _guard(handler):
    async def wrapped(request):
        try:
            return await handler(request)
        except (SourceError, art_mod.ArticleError, FetchError, litsearch.NotFound) as e:
            return _err(e)
    wrapped.__name__ = handler.__name__
    for attr in ("__madalean_host_only__",):
        if hasattr(handler, attr):
            setattr(wrapped, attr, getattr(handler, attr))
    return wrapped


async def _read_upload(request) -> tuple[str, bytes, dict]:
    """multipart: field `file` (+ other small fields) → (filename, bytes, fields)."""
    reader = await request.multipart()
    name, data, fields = "", b"", {}
    async for part in reader:
        if part.name == "file":
            name = part.filename or "upload"
            buf = bytearray()
            while True:
                chunk = await part.read_chunk(65536)
                if not chunk:
                    break
                buf += chunk
                if len(buf) > MAX_UPLOAD:
                    raise SourceError("too_large", 413)
            data = bytes(buf)
        elif part.name:
            fields[part.name] = (await part.read(decode=True))[:2000].decode("utf-8", "replace")
    if not data:
        raise SourceError("empty")
    return name, data, fields


def _spawn_request(request, rid: str, coro) -> None:
    tasks = request.app[TASKS]
    t = _ctx(request).spawn(coro)
    tasks[rid] = t
    t.add_done_callback(lambda _t: tasks.pop(rid, None))


# ================================================================ shelves & sources
async def shelves(request):
    ctx = _ctx(request)
    lib = _lib(request)
    out = [{"id": GLOBAL, "title": msg("Étagère commune")["text"], "count": len(lib.shelf(GLOBAL).cache),
            "readonly": False}]
    for p in ctx.projects.list():
        out.append({"id": p.id, "title": p.title, "count": len(lib.shelf(p.id).cache), "readonly": False,
                    "project": True})
    m = lib.mathlib()
    if m:
        out.append({"id": MATHLIB, "title": msg("Références de Mathlib")["text"], "count": len(m), "readonly": True})
    return ok({"shelves": out})


@_guard
async def sources_list(request):
    lib = _lib(request)
    sh = _shelf_id(request)
    items = lib.mathlib() if sh == MATHLIB else lib.shelf(sh).list()
    q = request.query.get("q", "").strip().lower()
    tag, coll, status = request.query.get("tag"), request.query.get("collection"), request.query.get("status")
    out = []
    for s in items:
        if tag and tag not in s.get("tags", []):
            continue
        if coll and coll not in s.get("collections", []):
            continue
        if status and s.get("status") != status:
            continue
        sm = summary(s)
        if q and q not in (sm["title"] + " " + sm["authors"] + " " + sm["key"] + " " + str(sm["year"] or "")).lower():
            continue
        out.append(sm)
    limit = min(int(request.query.get("limit", "2000") or 2000), 5000)
    return ok({"shelf": sh, "sources": out[:limit], "total": len(out)})


@_guard
async def sources_add(request):
    """JSON {identifier | csl | text (BibTeX/RIS/CSL-JSON), force?, files?} or multipart `file` (PDF, TeX, archive,
    .bib, .ris, .json, .rdf, Zotero export zip)."""
    ctx = _ctx(request)
    lib = _lib(request)
    sh = _shelf_id(request)
    lib.shelf(sh)
    project = ctx.projects.get(sh) if sh != GLOBAL else None
    if request.content_type.startswith("multipart/"):
        name, data, fields = await _read_upload(request)
        res = await lib.add_upload(sh, name, data, mode=_mode(ctx, fields, project), force=fields.get("force") == "1")
        return ok(res, status=201 if res.get("added") else 200)
    data = await body(request)
    force = bool(data.get("force"))
    if data.get("identifier"):
        ident = str(data["identifier"])[:500]
        kind, _x = litsearch.detect_identifier(ident)
        if not kind:
            return error(400, "unknown_identifier", MESSAGES["unknown_identifier"])
        src, dup = await lib.add_identifier(sh, ident, mode=_mode(ctx, data, project),
                                            files=data.get("files", True) is not False, force=force)
        return ok({"source": src, "duplicate": dup}, status=200 if dup else 201)
    if isinstance(data.get("csl"), dict):
        item = biblio.clean_csl(data["csl"])
        if not item.get("title"):
            return error(400, "bad_fields", "Champs refusés : {fields}.", fields="title")
        if data.get("key"):
            item["_key"] = str(data["key"])
        src, dup = await lib.add_record(sh, item, via="form", force=force)
        return ok({"source": src, "duplicate": dup}, status=200 if dup else 201)
    if isinstance(data.get("text"), str) and data["text"].strip():
        res = await lib.import_text(sh, data["text"].encode("utf-8")[:MAX_UPLOAD], str(data.get("format", "")),
                                    force=force)
        return ok(res, status=201 if res["added"] else 200)
    return error(400, "empty")


@_guard
async def source_get(request):
    return ok({"source": _lib(request).get(_shelf_id(request), _sid(request))})


@_guard
async def source_patch(request):
    src = await _lib(request).patch(_shelf_id(request), _sid(request), await body(request))
    return ok({"source": src})


@_guard
async def source_delete(request):
    sh, sid = _shelf_id(request), _sid(request)
    await _lib(request).delete(sh, sid)
    return ok({"ok": True, "undo": f"/api/research/shelves/{sh}/sources/{sid}/restore"})


@_guard
async def source_restore(request):
    return ok({"source": await _lib(request).restore(_shelf_id(request), _sid(request))})


@_guard
async def source_copy(request):
    data = await body(request)
    dst = str(data.get("to", ""))
    if dst != GLOBAL:
        valid_id(dst)
    src, dup = await _lib(request).copy_to(_shelf_id(request), _sid(request), dst)
    return ok({"source": src, "duplicate": dup}, status=200 if dup else 201)


@_guard
async def source_attach(request):
    name, data, _f = await _read_upload(request)
    return ok({"source": await _lib(request).attach(_shelf_id(request), _sid(request), name, data)})


FILE_TYPES = {"pdf": "application/pdf", "tex": "text/plain; charset=utf-8", "archive": "application/gzip",
              "epub": "application/epub+zip"}


@_guard
async def source_file(request):
    lib = _lib(request)
    sh, sid = _shelf_id(request), _sid(request)
    sha = request.match_info["sha"]
    src = lib.get(sh, sid)
    f = next((x for x in src.get("files", []) if x["sha256"] == sha), None)
    if f is None:
        return error(404, "not_found")
    path = lib.shelf(sh).blob(sha)
    data = await asyncio.to_thread(path.read_bytes)
    disp = "inline" if f["kind"] == "pdf" and "download" not in request.query else "attachment"
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", f["name"])[:120] or "file"
    return web.Response(body=data, content_type=FILE_TYPES.get(f["kind"], "application/octet-stream").split(";")[0],
                        charset="utf-8" if f["kind"] == "tex" else None,
                        headers={"Content-Disposition": f'{disp}; filename="{safe}"',
                                 "Content-Security-Policy": "sandbox; default-src 'none'",
                                 "Cache-Control": "private, max-age=3600"})


@_guard
async def source_extract(request):
    lib = _lib(request)
    sh, sid = _shelf_id(request), _sid(request)
    lib.get(sh, sid)
    if not lib.schedule_extract(sh, sid):
        return error(409, "busy", MESSAGES["busy"])
    return ok({"started": True}, status=202)


@_guard
async def source_chunks(request):
    page = request.query.get("page")
    chunks = await asyncio.to_thread(_lib(request).chunks_of, _shelf_id(request), _sid(request),
                                     int(page) if page and page.isdigit() else None)
    return ok({"chunks": chunks})


@_guard
async def annotation_add(request):
    src = await _lib(request).annotate(_shelf_id(request), _sid(request), await body(request))
    return ok({"source": src, "annotation": src["annotations"][-1]}, status=201)


@_guard
async def annotation_patch(request):
    aid = request.match_info["aid"]
    src = await _lib(request).annotate(_shelf_id(request), _sid(request), await body(request), aid)
    return ok({"source": src})


@_guard
async def annotation_delete(request):
    aid = request.match_info["aid"]
    src = await _lib(request).annotate(_shelf_id(request), _sid(request), {}, aid, delete=True)
    return ok({"source": src})


@_guard
async def source_propose(request):
    """Ask the brain (role « understand ») to propose metadata from the first page — stored as `proposed`."""
    ctx = _ctx(request)
    lib = _lib(request)
    sh, sid = _shelf_id(request), _sid(request)
    src = lib.get(sh, sid)
    pdf = next((f for f in src.get("files", []) if f["kind"] == "pdf"), None)
    if pdf is None:
        return error(409, "no_pdf")
    from ...research.sources import first_page_text
    text = await asyncio.to_thread(first_page_text, lib.shelf(sh).blob(pdf["sha256"]), 1)
    data = await body(request)
    if not lib.schedule_propose(sh, sid, _mode(ctx, data, ctx.projects.get(sh)), text):
        return error(409, "busy", MESSAGES["busy"])
    return ok({"started": True}, status=202)


@_guard
async def shelf_export(request):
    sh = _shelf_id(request)
    fmt = request.query.get("format", "bib")
    ids = [x for x in request.query.get("ids", "").split(",") if x]
    text, ctype = await asyncio.to_thread(_lib(request).export, sh, fmt, ids or None)
    ext = {"bib": "bib", "ris": "ris", "csljson": "json"}[fmt]
    return web.Response(text=text, content_type=ctype,
                        headers={"Content-Disposition": f'attachment; filename="madalean-{sh}.{ext}"'})


@_guard
async def shelf_search(request):
    data = await body(request)
    q = str(data.get("query", "")).strip()[:1000]
    if not q:
        return error(400, "empty")
    sh = _shelf_id(request)
    if sh == MATHLIB:
        return ok({"hits": []})
    srcs = [s for s in data.get("sources") or [] if isinstance(s, str)] or None
    hits = await _lib(request).search([sh], q, int(data.get("k", 12) or 12), srcs, data.get("semantic"))
    return ok({"hits": hits})


@_guard
async def resolve_preview(request):
    """GET ?id=… → what an identifier resolves to, without adding it."""
    ctx = _ctx(request)
    ident = request.query.get("id", "")[:500]
    if not litsearch.detect_identifier(ident)[0]:
        return error(400, "unknown_identifier", MESSAGES["unknown_identifier"])
    found = await litsearch.resolve(_lib(request).fetcher, ident, effective_mode(ctx))
    return ok({"csl": found.item, "via": found.via, "oa": found.oa, "eprint": found.eprint})


# ================================================================ literature search
@_guard
async def lit_search(request):
    ctx = _ctx(request)
    data = await body(request)
    q = str(data.get("query", "")).strip()[:500]
    if not q:
        return error(400, "empty")
    provs = [p for p in data.get("providers") or [] if p in litsearch.PROVIDERS] or None
    res = await litsearch.search(_lib(request).fetcher, q, _mode(ctx, data), provs, min(int(data.get("n", 10) or 10),
                                                                                        25))
    return ok(res)


@_guard
async def lit_related(request):
    ctx = _ctx(request)
    data = await body(request)
    how = data.get("how", "related")
    if how not in ("related", "cited_by", "references"):
        return error(400, "bad_fields", "Champs refusés : {fields}.", fields="how")
    ident = str(data.get("id", "")).strip()
    ident = re.sub(r"^(doi:|openalex:)", "", ident)
    if not ident:
        return error(400, "empty")
    res = await litsearch.related(_lib(request).fetcher, ident, how, _mode(ctx, data),
                                  max(1, min(int(data.get("n", 20) or 20), 50)))
    return ok({"results": res})


async def reading_list(request):
    ctx = _ctx(request)
    data = await body(request)
    question = str(data.get("question", "")).strip()[:2000]
    if not question:
        return error(400, "empty")
    mode = _mode(ctx, data)
    if mode == "local":
        return error(409, "local_mode", MESSAGES["local_mode"])
    rid = "l-" + uuid.uuid4().hex[:10]
    lib = _lib(request)

    async def complete(role, messages):
        return await complete_once(ctx, role, messages, mode, owner=rid, max_tokens=1500, temperature=0.2)

    async def run():
        try:
            res = await litsearch.reading_list(lib.fetcher, complete, question, mode,
                                               k=min(int(data.get("k", 8) or 8), 15),
                                               on_progress=lambda step, kw: ctx.publish(
                                                   "litsearch.progress", {"request_id": rid, "step": step, **kw}))
            ctx.publish("litsearch.done", {"request_id": rid, "result": res})
        except asyncio.CancelledError:
            ctx.publish("litsearch.error", {"request_id": rid, "error": "cancelled"})
        except Exception as e:  # noqa: BLE001
            log.exception("reading list failed")
            ctx.publish("litsearch.error", {"request_id": rid, "error": getattr(e, "kind", "internal"),
                                            "text": str(e)[:300]})
    _spawn_request(request, rid, run())
    return ok({"request_id": rid}, status=202)


# ================================================================ grounded answers
def _scope(ctx, lib, data: dict) -> tuple[list[str], list[str] | None, object]:
    pid = str(data.get("project", "") or "")
    project = ctx.projects.get(pid) if pid else None
    scope = data.get("scope") if isinstance(data.get("scope"), dict) else {}
    shelves = [s for s in scope.get("shelves") or [] if isinstance(s, str)]
    if not shelves:
        shelves = ([pid] if project else []) + [GLOBAL]
    for s in shelves:
        lib.shelf(s)                                # validates
    srcs = [s for s in scope.get("sources") or [] if isinstance(s, str) and SID_RE.match(s)] or None
    return shelves, srcs, project


def _qa_runner(request, rid: str, kind: str, mode: str, gather, question: str, general: bool, task: str = ""):
    ctx = _ctx(request)

    async def complete(role, messages, phase):
        def on_chunk(ch):
            if ch.kind in ("text", "thinking"):
                ctx.publish("qa.token", {"request_id": rid, "kind": ch.kind, "phase": phase, "text": ch.text})
        return await complete_once(ctx, role, messages, mode, owner=rid, on_chunk=on_chunk, max_tokens=2500,
                                   temperature=0.2)

    async def run():
        try:
            hits = await gather()
            res = await qa.grounded(complete, question, hits, lang=language(), general=general, task=task)
            res["kind"] = kind
            ctx.publish("qa.done", {"request_id": rid, "result": res})
        except asyncio.CancelledError:
            ctx.publish("qa.error", {"request_id": rid, "error": "cancelled"})
        except Exception as e:  # noqa: BLE001
            log.exception("qa failed")
            ctx.publish("qa.error", {"request_id": rid, "error": getattr(e, "kind", "internal"), "text": str(e)[:300]})
    _spawn_request(request, rid, run())


@_guard
async def ask(request):
    ctx = _ctx(request)
    lib = _lib(request)
    data = await body(request)
    question = str(data.get("question", "")).strip()[:2000]
    if not question:
        return error(400, "empty")
    shelves_, srcs, project = _scope(ctx, lib, data)
    mode = _mode(ctx, data, project)
    k = min(int(data.get("k", 8) or 8), 16)
    rid = "q-" + uuid.uuid4().hex[:10]

    async def gather():
        hits = await lib.search(shelves_, question, k, srcs)
        return [h for h in hits if h["score"] > qa.MIN_SCORE]
    _qa_runner(request, rid, "ask", mode, gather, question, bool(data.get("general")))
    return ok({"request_id": rid}, status=202)


@_guard
async def summarize(request):
    ctx = _ctx(request)
    lib = _lib(request)
    data = await body(request)
    sh, sid = str(data.get("shelf", "")), str(data.get("source", ""))
    src = lib.get(sh, sid)
    mode = _mode(ctx, data, ctx.projects.get(sh))
    rid = "q-" + uuid.uuid4().hex[:10]
    task = qa.TASKS["summary"]["en" if language() == "en" else "fr"]

    async def gather():
        chunks = await asyncio.to_thread(lib.chunks_of, sh, sid)
        for c in chunks:
            c["shelf"], c["source_key"] = sh, src["key"]
        return qa.source_overview_hits(chunks)
    _qa_runner(request, rid, "summary", mode, gather, task, False, task)
    return ok({"request_id": rid}, status=202)


@_guard
async def compare(request):
    ctx = _ctx(request)
    lib = _lib(request)
    data = await body(request)
    items = [x for x in data.get("sources") or [] if isinstance(x, dict)][:4]
    if len(items) < 2:
        return error(400, "bad_fields", "Champs refusés : {fields}.", fields="sources")
    pairs = [(str(x.get("shelf", "")), str(x.get("id", ""))) for x in items]
    srcs = [lib.get(sh, sid) for sh, sid in pairs]
    mode = _mode(ctx, data)
    rid = "q-" + uuid.uuid4().hex[:10]
    task = qa.TASKS["compare"]["en" if language() == "en" else "fr"]

    async def gather():
        out = []
        for (sh, sid), src in zip(pairs, srcs):
            chunks = await asyncio.to_thread(lib.chunks_of, sh, sid)
            for c in chunks:
                c["shelf"], c["source_key"] = sh, src["key"]
            out += qa.source_overview_hits(chunks, budget=12000 // len(pairs))
        return out
    _qa_runner(request, rid, "compare", mode, gather, task, False, task)
    return ok({"request_id": rid}, status=202)


async def request_stop(request):
    t = request.app[TASKS].get(request.match_info["rid"])
    if t is None:
        return ok({"stopped": False})
    t.cancel()
    return ok({"stopped": True})


# ================================================================ bibliography helpers
@_guard
async def project_keys(request):
    ctx = _ctx(request)
    p = _project(request)
    lib = _lib(request)
    entries = lib.project_entries(p.id)
    labels = biblio.labels_for(entries)
    return ok({"keys": [{"key": k, "title": it.get("title", ""), "label": labels[k], "authors":
                         biblio.short_author(it), "year": biblio.year_of(it)} for k, it in entries],
               "mathlib": len(lib.mathlib()) if ctx.workspaces else 0})


@_guard
async def project_bib(request):
    p = _project(request)
    lib = _lib(request)
    entries = lib.project_entries(p.id)
    text = "".join(biblio.item_to_bibtex(it, k) + "\n" for k, it in entries)
    return web.Response(text=text, content_type="application/x-bibtex",
                        headers={"Content-Disposition": f'attachment; filename="{p.id}-refs.bib"'})


@_guard
async def check_cites(request):
    data = await body(request)
    pid = str(data.get("project", "") or "") or None
    known = _lib(request).all_entries(pid)
    res = biblio.check_citations(str(data.get("text", ""))[:200000], known)
    return ok({"text": res.text, "cited": res.cited, "unknown": res.unknown})


# ================================================================ blueprint
def _bp_publish(ctx, pid: str, bp: dict | None, source_id: str, removed: bool = False) -> None:
    payload = {"project": pid, "source_id": source_id}
    if bp is not None:
        payload["blueprint"] = bp
    if removed:
        payload["removed"] = True
    ctx.publish("blueprint.updated", payload)


@_guard
async def bp_create(request):
    """{source_id, shelf?: <pid>|global, model_pass?: bool} → extract the blueprint of a source of the project."""
    ctx = _ctx(request)
    p = _project(request)
    lib = _lib(request)
    data = await body(request)
    sid = str(data.get("source_id", ""))
    shelf = str(data.get("shelf", "") or p.id)
    if shelf not in (p.id, GLOBAL):
        return error(400, "bad_fields", "Champs refusés : {fields}.", fields="shelf")
    src = lib.get(shelf, sid)
    sh = lib.shelf(shelf)
    bp = await asyncio.to_thread(papers.extract, sh, src)
    old = await asyncio.to_thread(papers.load, ctx, p.id, sid)
    if old:                                          # keep the links to existing dossiers
        prev = {(n["kind"], n["number"], n.get("label", "")): n.get("dossier_id", "") for n in old.get("nodes", [])}
        for n in bp["nodes"]:
            n["dossier_id"] = prev.get((n["kind"], n["number"], n.get("label", "")), "")
    bp["shelf"] = shelf
    await asyncio.to_thread(papers.save, ctx, p.id, bp)
    _bp_publish(ctx, p.id, bp, sid)
    rid = ""
    if data.get("model_pass") and bp["nodes"]:
        mode = _mode(ctx, data, p)
        rid = "b-" + uuid.uuid4().hex[:10]

        async def run():
            try:
                c = await complete_once(ctx, "understand", papers.uses_messages(bp), mode, owner=rid, max_tokens=2500,
                                        temperature=0.1)
                cur = await asyncio.to_thread(papers.load, ctx, p.id, sid) or bp
                n = papers.apply_model_uses(cur, c.text)
                cur["model_pass"] = {"model": c.model.key, "added": n}
                await asyncio.to_thread(papers.save, ctx, p.id, cur)
                _bp_publish(ctx, p.id, cur, sid)
            except Exception as e:  # noqa: BLE001
                log.warning("blueprint model pass failed: %s", e)
                ctx.publish("blueprint.updated", {"project": p.id, "source_id": sid, "error": "model_pass"})
        _spawn_request(request, rid, run())
    return ok({"blueprint": bp, "request_id": rid}, status=201)


@_guard
async def bp_list(request):
    ctx = _ctx(request)
    p = _project(request)
    bps = await asyncio.to_thread(papers.list_blueprints, ctx, p.id)
    return ok({"blueprints": [{"source_id": b["source_id"], "paper_key": b["paper_key"], "method": b["method"],
                               "nodes": len(b["nodes"]), "created": b.get("created"), "warnings": b.get("warnings", [])}
                              for b in bps]})


@_guard
async def bp_get(request):
    ctx = _ctx(request)
    p = _project(request)
    sid = _sid(request)
    bp = await asyncio.to_thread(papers.load, ctx, p.id, sid)
    if bp is None:
        return error(404, "not_found")
    states = papers.node_states(ctx, [bp])
    return ok({"blueprint": bp, "status": {v["node_id"]: v for v in states.values()}})


@_guard
async def bp_delete(request):
    ctx = _ctx(request)
    p = _project(request)
    sid = _sid(request)
    path = papers.bp_path(ctx, p.id, sid)
    if not path.exists():
        return error(404, "not_found")
    trash = path.parent / ".trash"
    trash.mkdir(exist_ok=True)
    path.replace(trash / path.name)
    _bp_publish(ctx, p.id, None, sid, removed=True)
    return ok({"ok": True, "undo": f"/api/research/projects/{p.id}/blueprints/{sid}/restore"})


@_guard
async def bp_restore(request):
    ctx = _ctx(request)
    p = _project(request)
    sid = _sid(request)
    path = papers.bp_path(ctx, p.id, sid)
    src = path.parent / ".trash" / path.name
    if not src.exists() or path.exists():
        return error(404, "not_found")
    src.replace(path)
    bp = await asyncio.to_thread(papers.load, ctx, p.id, sid)
    _bp_publish(ctx, p.id, bp, sid)
    return ok({"blueprint": bp})


@_guard
async def bp_edge(request):
    """{from, to, action: add | remove | accept | reject}: the user curates the dependency graph."""
    ctx = _ctx(request)
    p = _project(request)
    sid = _sid(request)
    data = await body(request)
    bp = await asyncio.to_thread(papers.load, ctx, p.id, sid)
    if bp is None:
        return error(404, "not_found")
    nodes = {n["id"]: n for n in bp["nodes"]}
    a, b, action = str(data.get("from", "")), str(data.get("to", "")), data.get("action")
    if a not in nodes or b not in nodes or a == b or action not in ("add", "remove", "accept", "reject"):
        return error(400, "bad_fields", "Champs refusés : {fields}.", fields="from, to, action")
    uses = nodes[a]["uses"]
    e = next((u for u in uses if u["to"] == b), None)
    if action == "add" and e is None:
        uses.append({"to": b, "via": "user", "proposed": False})
    elif action == "remove" and e is not None:
        uses.remove(e)
    elif action == "accept" and e is not None:
        e["accepted"], e["rejected"] = True, False
    elif action == "reject" and e is not None:
        e["rejected"], e["accepted"] = True, False
    await asyncio.to_thread(papers.save, ctx, p.id, bp)
    # dossier uses follow the graph
    did = nodes[a].get("dossier_id")
    d = ctx.repo.get(did) if did else None
    if d is not None:
        d.uses = [nodes[u["to"]]["dossier_id"] for u in uses if not u.get("rejected") and nodes[u["to"]].get(
            "dossier_id")]
        d.touch()
        await ctx.repo.save(d)
    _bp_publish(ctx, p.id, bp, sid)
    return ok({"blueprint": bp})


@_guard
async def bp_dossiers(request):
    """{nodes?: [node ids]} → draft dossiers (never started)."""
    ctx = _ctx(request)
    p = _project(request)
    sid = _sid(request)
    data = await body(request)
    bp = await asyncio.to_thread(papers.load, ctx, p.id, sid)
    if bp is None:
        return error(404, "not_found")
    ids = data.get("nodes")
    if ids is not None and not (isinstance(ids, list) and all(isinstance(x, str) for x in ids)):
        return error(400, "bad_fields", "Champs refusés : {fields}.", fields="nodes")
    known = _lib(request).all_entries(p.id)
    created = await papers.create_dossiers(ctx, p.id, bp, ids, known)
    _bp_publish(ctx, p.id, bp, sid)
    from ...repo import dossier_api
    return ok({"dossiers": [dossier_api(d) for d in created], "blueprint": bp}, status=201)


@_guard
async def bp_formalise(request):
    """{dossier_ids:[…], mode?, use_paper_proof?: true} → normal pipeline jobs (explicit user action only)."""
    from ...orchestrator import DossierBusy
    ctx = _ctx(request)
    p = _project(request)
    data = await body(request)
    ids = [x for x in data.get("dossier_ids") or [] if isinstance(x, str)][:50]
    if not ids:
        return error(400, "empty")
    bps = await asyncio.to_thread(papers.list_blueprints, ctx, p.id)
    jobs, busy, skipped = [], [], []
    opts = {"mode": data["mode"]} if data.get("mode") in ("local", "auto", "online") else {}
    planned = set()
    for bp in bps:
        for did, plan, strategy in papers.formalise_plans(bp, ctx, [i for i in ids if i not in planned],
                                                          data.get("use_paper_proof", True) is not False):
            planned.add(did)
            if not plan:
                skipped.append(did)
                continue
            try:
                job = ctx.orchestrator.submit(did, plan, **opts, **({"strategy": strategy} if strategy else {}))
                jobs.append(job.to_dict())
            except DossierBusy as e:
                busy.append({"dossier_id": did, "job": e.job.to_dict()})
    skipped += [i for i in ids if i not in planned]
    if not jobs and busy:
        return web.json_response({"error": "busy", "busy": busy, "message": msg(MESSAGES["busy"])}, status=409)
    return ok({"jobs": jobs, "busy": busy, "skipped": skipped}, status=202)


@_guard
async def bp_status(request):
    ctx = _ctx(request)
    p = _project(request)
    bps = await asyncio.to_thread(papers.list_blueprints, ctx, p.id)
    states = papers.node_states(ctx, bps)
    counts: dict[str, int] = {}
    for v in states.values():
        counts[v["state"]] = counts.get(v["state"], 0) + 1
    return ok({"nodes": list(states.values()), "counts": counts})


# ================================================================ article
ART_LOCKS = web.AppKey("research_article_locks", dict)


def _art_lock(request, pid: str) -> asyncio.Lock:
    return request.app[ART_LOCKS].setdefault(pid, asyncio.Lock())


async def _art_save(request, pid: str, art: dict) -> None:
    ctx = _ctx(request)
    art.pop("_pid", None)
    await asyncio.to_thread(art_mod.save, ctx, pid, art)
    ctx.publish("article.updated", {"project": pid, "article": art})


@_guard
async def article_get(request):
    ctx = _ctx(request)
    p = _project(request)
    art = await asyncio.to_thread(art_mod.load, ctx, p.id)
    return ok({"article": art, "generating": [k.split(":", 1)[1] for k in request.app[TASKS]
                                              if k.startswith(f"art:{p.id}:")]})


@_guard
async def article_patch(request):
    ctx = _ctx(request)
    p = _project(request)
    data = await body(request)
    async with _art_lock(request, p.id):
        art = await asyncio.to_thread(art_mod.load, ctx, p.id)
        bad = art_mod.patch_meta(art, data)
        if bad:
            return error(400, "bad_fields", "Champs refusés : {fields}.", fields=", ".join(bad))
        await _art_save(request, p.id, art)
    return ok({"article": art})


@_guard
async def article_sync(request):
    """Add a block for every dossier of the project that the article does not show yet."""
    ctx = _ctx(request)
    p = _project(request)
    async with _art_lock(request, p.id):
        art = await asyncio.to_thread(art_mod.load, ctx, p.id)
        have = {b.get("dossier_id") for b in art["blocks"]}
        added = 0
        for d in sorted(ctx.repo.list(p.id), key=lambda x: x.created):
            if d.id not in have and not d.archived and not d.parent_id:
                art["blocks"].append(art_mod.new_block("dossier", "", "", "dossier", d.id))
                added += 1
        await _art_save(request, p.id, art)
    return ok({"article": art, "added": added})


@_guard
async def block_add(request):
    ctx = _ctx(request)
    p = _project(request)
    data = await body(request)
    kind = data.get("kind")
    if kind not in art_mod.BLOCK_KINDS:
        return error(400, "bad_fields", "Champs refusés : {fields}.", fields="kind")
    did = str(data.get("dossier_id", "") or "")
    if kind == "dossier" and (not did or ctx.repo.get(did) is None or ctx.repo.get(did).project_id != p.id):
        return error(400, "bad_fields", "Champs refusés : {fields}.", fields="dossier_id")
    async with _art_lock(request, p.id):
        art = await asyncio.to_thread(art_mod.load, ctx, p.id)
        b = art_mod.new_block(kind, str(data.get("title", ""))[:300], str(data.get("text", ""))[:200000],
                              "dossier" if kind == "dossier" else "user", did)
        after = data.get("after")
        idx = next((i + 1 for i, x in enumerate(art["blocks"]) if x["id"] == after), len(art["blocks"]))
        art["blocks"].insert(idx, b)
        await _art_save(request, p.id, art)
    return ok({"article": art, "block": b}, status=201)


@_guard
async def block_patch(request):
    """The user edits a block: new version with source "user" (an AI draft never overwrites it)."""
    ctx = _ctx(request)
    p = _project(request)
    bid = request.match_info["bid"]
    data = await body(request)
    if not set(data) <= {"text", "title"} or not all(isinstance(v, str) for v in data.values()):
        return error(400, "bad_fields", "Champs refusés : {fields}.", fields=", ".join(data))
    async with _art_lock(request, p.id):
        art = await asyncio.to_thread(art_mod.load, ctx, p.id)
        b = art_mod.find_block(art, bid)
        art_mod.set_text(b, data.get("text", b.get("text", ""))[:200000], "user", title=data.get("title"))
        await _art_save(request, p.id, art)
    return ok({"article": art, "block": b})


@_guard
async def block_delete(request):
    ctx = _ctx(request)
    p = _project(request)
    bid = request.match_info["bid"]
    async with _art_lock(request, p.id):
        art = await asyncio.to_thread(art_mod.load, ctx, p.id)
        b = art_mod.find_block(art, bid)
        if bid == "abstract":
            return error(400, "bad_id")
        idx = art["blocks"].index(b)
        art["blocks"].remove(b)
        art.setdefault("trash", []).append({"block": b, "index": idx})
        art["trash"] = art["trash"][-50:]
        await _art_save(request, p.id, art)
    return ok({"ok": True, "undo": f"/api/research/projects/{p.id}/article/blocks/{bid}/restore"})


@_guard
async def block_restore(request):
    ctx = _ctx(request)
    p = _project(request)
    bid = request.match_info["bid"]
    async with _art_lock(request, p.id):
        art = await asyncio.to_thread(art_mod.load, ctx, p.id)
        t = next((x for x in art.get("trash", []) if x["block"]["id"] == bid), None)
        if t is None:
            return error(404, "not_found")
        art["trash"].remove(t)
        art["blocks"].insert(min(t["index"], len(art["blocks"])), t["block"])
        await _art_save(request, p.id, art)
    return ok({"article": art})


@_guard
async def block_version_restore(request):
    ctx = _ctx(request)
    p = _project(request)
    bid = request.match_info["bid"]
    try:
        i = int(request.match_info["index"])
    except ValueError:
        return error(400, "bad_index")
    async with _art_lock(request, p.id):
        art = await asyncio.to_thread(art_mod.load, ctx, p.id)
        b = art_mod.find_block(art, bid)
        if not 0 <= i < len(b["versions"]):
            return error(404, "not_found")
        v = b["versions"][i]
        b["text"], b["source"], b["title"] = v["text"], v["source"], v.get("title", b.get("title", ""))
        b["updated"] = __import__("time").time()
        await _art_save(request, p.id, art)
    return ok({"article": art, "block": b})


@_guard
async def block_generate(request):
    """{force?, instructions?, mode?} → AI draft of one block (others untouched). 409 user_edited / busy."""
    ctx = _ctx(request)
    p = _project(request)
    bid = request.match_info["bid"]
    data = await body(request)
    tkey = f"art:{p.id}:{bid}"
    if tkey in request.app[TASKS]:
        return error(409, "busy", MESSAGES["busy"])
    art = await asyncio.to_thread(art_mod.load, ctx, p.id)
    b = art_mod.find_block(art, bid)
    if b["kind"] == "dossier" and bid != "abstract":
        kind = "prose"
    else:
        kind = "abstract" if bid == "abstract" else b["kind"]
    if b.get("source") == "user" and b.get("text", "").strip() and not data.get("force"):
        return error(409, "user_edited", MESSAGES["user_edited"])
    mode = _mode(ctx, data, p)
    art["_pid"] = p.id
    msgs, keys = art_mod.draft_messages(ctx, art, b, kind, str(data.get("instructions", "")))
    rid = "w-" + uuid.uuid4().hex[:10]

    def on_chunk(ch):
        if ch.kind == "text":
            ctx.publish("article.token", {"project": p.id, "block_id": bid, "request_id": rid, "text": ch.text})

    async def run():
        try:
            c = await complete_once(ctx, "explain", msgs, mode, owner=rid, on_chunk=on_chunk, max_tokens=2500,
                                    temperature=0.5)
            text, unknown = art_mod.clean_draft(c.text, keys)
            async with _art_lock(request, p.id):
                cur = await asyncio.to_thread(art_mod.load, ctx, p.id)
                blk = art_mod.find_block(cur, bid)
                if blk.get("source") == "user" and blk.get("text", "").strip() and blk is not None and \
                        not data.get("force"):
                    return                                    # the user typed meanwhile: keep their text
                art_mod.set_text(blk, text, "ai", c.model.key, str(data.get("instructions", "")))
                if unknown:
                    blk["versions"][-1]["removed_citations"] = unknown
                await _art_save(request, p.id, cur)
            ctx.publish("article.done", {"project": p.id, "block_id": bid, "request_id": rid, "model": c.model.key,
                                         "removed_citations": unknown})
        except asyncio.CancelledError:
            ctx.publish("article.error", {"project": p.id, "block_id": bid, "request_id": rid, "error": "cancelled"})
        except Exception as e:  # noqa: BLE001
            log.exception("article draft failed")
            ctx.publish("article.error", {"project": p.id, "block_id": bid, "request_id": rid,
                                          "error": getattr(e, "kind", "internal"), "text": str(e)[:300]})
    tasks = request.app[TASKS]
    t = ctx.spawn(run())
    tasks[tkey] = t
    tasks[rid] = t
    t.add_done_callback(lambda _t: (tasks.pop(tkey, None), tasks.pop(rid, None)))
    return ok({"request_id": rid}, status=202)


@_guard
async def article_export(request):
    ctx = _ctx(request)
    p = _project(request)
    fmt = request.query.get("format", "pdf")
    if fmt not in ("pdf", "tex", "zip", "md"):
        return error(400, "bad_format")
    art = await asyncio.to_thread(art_mod.load, ctx, p.id)
    name, ctype, data, fallback = await art_mod.export(ctx, p.id, art, fmt, ctx.paths.exports)
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", name)[:120]
    return web.Response(body=data, content_type=ctype.split(";")[0],
                        headers={"Content-Disposition": f'attachment; filename="{safe}"',
                                 "X-Madalean-Fallback": fallback})


# ================================================================ registration
def register(app: web.Application, ctx) -> None:
    app[TASKS] = {}
    app[ART_LOCKS] = {}
    r = app.router
    base = "/api/research"
    shelf = base + "/shelves/{shelf}"
    src = shelf + "/sources/{sid}"
    r.add_get(base + "/shelves", shelves)
    r.add_get(shelf + "/sources", sources_list)
    r.add_post(shelf + "/sources", sources_add)
    r.add_get(shelf + "/export", shelf_export)
    r.add_post(shelf + "/search", shelf_search)
    r.add_get(src, source_get)
    r.add_patch(src, source_patch)
    r.add_delete(src, source_delete)
    r.add_post(src + "/restore", source_restore)
    r.add_post(src + "/copy", source_copy)
    r.add_post(src + "/files", source_attach)
    r.add_get(src + "/files/{sha:[0-9a-f]{64}}", source_file)
    r.add_post(src + "/extract", source_extract)
    r.add_get(src + "/chunks", source_chunks)
    r.add_post(src + "/annotations", annotation_add)
    r.add_patch(src + "/annotations/{aid}", annotation_patch)
    r.add_delete(src + "/annotations/{aid}", annotation_delete)
    r.add_post(src + "/propose", source_propose)
    r.add_get(base + "/resolve", resolve_preview)
    r.add_post(base + "/litsearch", lit_search)
    r.add_post(base + "/litsearch/related", lit_related)
    r.add_post(base + "/litsearch/reading-list", reading_list)
    r.add_post(base + "/ask", ask)
    r.add_post(base + "/summarize", summarize)
    r.add_post(base + "/compare", compare)
    r.add_post(base + "/requests/{rid}/stop", request_stop)
    r.add_post(base + "/check-citations", check_cites)
    proj = base + "/projects/{pid}"
    r.add_get(proj + "/keys", project_keys)
    r.add_get(proj + "/bibliography", project_bib)
    r.add_get(proj + "/blueprints", bp_list)
    r.add_post(proj + "/blueprints", bp_create)
    r.add_get(proj + "/blueprints/{sid}", bp_get)
    r.add_delete(proj + "/blueprints/{sid}", bp_delete)
    r.add_post(proj + "/blueprints/{sid}/restore", bp_restore)
    r.add_post(proj + "/blueprints/{sid}/edges", bp_edge)
    r.add_post(proj + "/blueprints/{sid}/dossiers", bp_dossiers)
    r.add_post(proj + "/formalise", bp_formalise)
    r.add_get(proj + "/blueprint-status", bp_status)
    r.add_get(proj + "/article", article_get)
    r.add_patch(proj + "/article", article_patch)
    r.add_post(proj + "/article/sync", article_sync)
    r.add_post(proj + "/article/blocks", block_add)
    r.add_patch(proj + "/article/blocks/{bid}", block_patch)
    r.add_delete(proj + "/article/blocks/{bid}", block_delete)
    r.add_post(proj + "/article/blocks/{bid}/restore", block_restore)
    r.add_post(proj + "/article/blocks/{bid}/generate", block_generate)
    r.add_post(proj + "/article/blocks/{bid}/versions/{index}/restore", block_version_restore)
    r.add_get(proj + "/article/export", article_export)

    async def cleanup(_app):
        lib = getattr(ctx, "_research_library", None)
        if lib is not None:
            await lib.fetcher.close()
    app.on_cleanup.append(cleanup)
    if getattr(ctx, "demo", False):
        from ...research.demo_seed import install
        install(ctx)
