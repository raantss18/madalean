"""UI requests of docs/UI.md §8: manual versions, declaration lookup, examples, replay of a job's streamed text."""
from __future__ import annotations

import asyncio
import time

from aiohttp import web

from .. import leancheck
from ..examples import EXAMPLES
from ..i18n import language, msg
from ..i18n_en import EN
from ..repo import dossier_api
from ..runtime.lean import workspace_info
from .common import body, ctx_of, error, ok, valid_id

routes = web.RouteTableDef()
MANUAL = ("proof", "explanation", "informal", "notes")


# ---------------------------------------------------------------- manual versions (§8.1)
@routes.post("/api/dossiers/{id}/versions/{kind}")
async def manual_version(request: web.Request) -> web.Response:
    """{code, check?: true} → a new user version (`source:"user"`). A proof is pinned to the current statement and
    re-checked by Lean with the strict verdict: only then it counts as proven (`ok`). AI stages never rewrite a
    version: they add new ones, and only when the user asks for it."""
    ctx = ctx_of(request)
    d = ctx.repo.get(valid_id(request.match_info["id"]))
    if d is None:
        return error(404, "not_found")
    kind = request.match_info["kind"]
    if kind not in MANUAL:
        return error(400, "bad_kind")
    act = ctx.orchestrator.active_for(d.id)
    if act:
        return web.json_response({"error": "busy", "job": act.to_dict(),
                                  "message": msg("Une opération est en cours : arrêtez-la d'abord (Échap).")},
                                 status=409)
    data = await body(request)
    code = str(data.get("code", "")).strip()
    if not code or len(code) > 200_000:
        return error(400, "empty")
    check = None
    if kind == "proof":
        if not d.statement:
            return error(409, "no_statement")
        try:
            assembled = leancheck.assemble_proof(d.statement, code)
            name = leancheck.theorem_name(d.statement)
        except leancheck.StatementError as e:
            return web.json_response({"error": "bad_proof", "message": {"key": "", "params": {}, "text": str(e)}},
                                     status=400)
        ws = ctx.workspace(d.workspace or ctx.settings.workspace)
        verified = False
        meta: dict = {"manual": True}
        if data.get("check", True) and ws is not None:
            r = await ctx.lean.check(leancheck.with_axiom_probe(assembled, name), ws, ctx.settings.compile_timeout_s,
                                     name, owner=f"check-{d.id}")
            check = r.to_dict()
            verified = r.verdict.ok
            info = workspace_info(ws)
            meta.update({"axioms": r.verdict.axioms, "lean": info.get("lean", ""), "mathlib": info.get("mathlib", ""),
                         "workspace": ws.key, "seconds": round(r.seconds, 1), "checked": time.time()})
        idx = d.add_proof(assembled, note="", model="", meta=meta, source="user", ok=verified)
        if verified:
            m = msg("Preuve modifiée à la main : Lean l'accepte.")
            d.status = "proved"
            entry = await asyncio.to_thread(ctx.library.add_proof, assembled, d.title, ws.key, d.id, d.lemmas_used)
            if entry:
                ctx.publish("library.updated", {"added": entry.name})
        else:
            m = msg("Preuve modifiée à la main : pas vérifiée par Lean ({why}).",
                    why=(check or {}).get("summary") or msg("vérification non demandée")["text"])
            if d.status == "proved":
                d.status = "draft"
        d.add_event("proof" if verified else "error", m["text"], ref=idx, key=m["key"], params=m["params"])
    else:
        from ..dossiers import Version
        if kind == "explanation":
            d.explanations.append(Version(code, parent=d.cur_proof, source="user"))
            d.cur_explanation = len(d.explanations) - 1
            idx, ev, key = d.cur_explanation, "explanation", "Explication modifiée à la main."
        elif kind == "informal":
            d.informal_proofs.append(Version(code, parent=d.cur_proof, source="user"))
            idx, ev, key = len(d.informal_proofs) - 1, "informal", "Preuve en langage naturel modifiée à la main."
        else:
            d.statement_notes.append(Version(code, parent=d.cur_statement, source="user"))
            idx, ev, key = len(d.statement_notes) - 1, "notes", "Lecture de l'énoncé modifiée à la main."
        m = msg(key)
        d.add_event(ev, m["text"], ref=idx, key=m["key"])
    d.touch()
    await ctx.repo.save(d)
    return ok({"dossier": dossier_api(d), "check": check})


# ---------------------------------------------------------------- declarations (§8.4)
async def _lookup(ctx, workspace: str, fn: str, *args):
    r = ctx.retriever
    if r is None:
        return "unavailable", None
    ready = getattr(r, "ready", None)
    if callable(ready):
        try:
            if not ready(workspace):
                start = getattr(r, "start", None)
                if callable(start):
                    start(workspace)
                return "indexing", None
        except Exception:  # noqa: BLE001
            pass
    try:
        return "ok", await asyncio.wait_for(getattr(r, fn)(workspace, *args), 10)
    except asyncio.TimeoutError:
        return "indexing", None
    except Exception:  # noqa: BLE001
        return "unavailable", None


def _ws_key(request: web.Request) -> str:
    ctx = ctx_of(request)
    return request.match_info.get("workspace") or request.query.get("workspace") or ctx.settings.workspace


@routes.get("/api/declarations/search")
@routes.get("/api/lean/search")
async def declarations_search(request: web.Request) -> web.Response:
    ctx = ctx_of(request)
    q = request.query.get("q", "").strip()[:200]
    if not q:
        return error(400, "empty")
    ws = _ws_key(request)
    try:
        k = max(1, min(30, int(request.query.get("k", 8))))
    except ValueError:
        k = 8
    status, res = await _lookup(ctx, ws, "search", q, k)
    return ok({"workspace": ws, "status": status, "results": res or []})


@routes.get("/api/declarations/{workspace}/{name}")
@routes.get("/api/lean/declaration")
async def declaration(request: web.Request) -> web.Response:
    ctx = ctx_of(request)
    name = (request.match_info.get("name") or request.query.get("name", "")).strip()[:300]
    if not name:
        return error(400, "empty")
    ws = _ws_key(request)
    status, res = await _lookup(ctx, ws, "declaration", name)
    if status == "ok" and not res:
        status = "unknown"
    return ok({"workspace": ws, "name": name, "status": status, "declaration": res or None})


# ---------------------------------------------------------------- examples (§8.8)
@routes.get("/api/examples")
async def examples(request: web.Request) -> web.Response:
    lang = language()
    out = []
    for e in EXAMPLES:
        fr = {"title": e.title, "level": e.level, "blurb": e.blurb}
        en = {k: EN.get(v, v) for k, v in fr.items()}
        out.append({"key": e.key, "statement": e.statement, **(en if lang == "en" else fr), "fr": fr, "en": en})
    return ok({"examples": out})


# ---------------------------------------------------------------- replay of streamed text (§8.12)
@routes.get("/api/jobs/{id}/stream")
async def job_stream(request: web.Request) -> web.Response:
    ctx = ctx_of(request)
    jid = valid_id(request.match_info["id"])
    try:
        start = int(request.query.get("from", request.query.get("since", "0")) or 0)
    except ValueError:
        return error(400, "bad_offset")
    res = ctx.streams.read(jid, start)
    if res is None:
        return error(404, "not_found") if jid not in ctx.orchestrator.jobs else ok(
            {"job_id": jid, "start": start, "end": start, "truncated": False, "ended": True, "segments": []})
    return ok({"job_id": jid, **res})

