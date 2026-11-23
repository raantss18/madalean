"""Certificates API (session S-AT, DECISIONS D52): « Sage calcule, Lean vérifie ».

    GET  /api/certificates                    the kinds, whether SageMath is there, whether the strategy is on
    POST /api/certificates/check              {statement, workspace?} → the outcome (nothing is stored)
    POST /api/certificates/dossier            {statement | project_id + doc + cell_id, title?, workspace?}
                                              → certify, and when Lean accepts, a new dossier with the statement and
                                              the certificate proof (« Certifier avec Lean » in Calcul)

The computation is Madalean's fixed producer in Calcul's sandboxed Sage kernel: the same rule as every Calcul run
applies (from the host, or from a paired device when `experiments_remote` is on). Nothing is « vérifiée » without the
fresh strict Lean check made here. See docs/CERTIFICATES.md."""
from __future__ import annotations

import asyncio
import re
import secrets

from aiohttp import web

from ... import leancheck
from ...certs import engine, fromcalcul, producer
from ...i18n import msg
from ...logs import get
from ...pipeline import certificate as certstage
from ...runtime.lean import workspace_info
from ..common import body, ctx_of, error, ok, valid_id

log = get("certificates")
routes = web.RouteTableDef()
CHECK_TIMEOUT = 150
MAX_STATEMENT = 20000
LOCK = web.AppKey("certificates_lock", asyncio.Semaphore)


def _exec_allowed(request) -> web.Response | None:
    if not request["local"] and not getattr(ctx_of(request).settings, "experiments_remote", False):
        return error(403, "experiments_host_only", "Les expériences exécutent du code sur l'ordinateur hôte : "
                                                   "autorisées seulement depuis l'hôte (réglage).")
    return None


def _sage(ctx) -> bool:
    p = producer.for_ctx(ctx)
    try:
        return bool(p is not None and p.available())
    except Exception:  # noqa: BLE001
        return False


@routes.get("/api/certificates")
async def certificates_info(request: web.Request) -> web.Response:
    ctx = ctx_of(request)
    sage = await asyncio.to_thread(_sage, ctx)
    return ok({"enabled": bool(getattr(ctx.settings, "certificates", True)), "sage": sage,
               "kinds": [{"id": k, "title": msg(v["title"]), "sage": v["sage"], "checker": v["checker"]}
                         for k, v in engine.KINDS.items()]})


async def _certify(request, ctx, statement: str, ws) -> engine.Outcome:
    async def check(code: str, name: str):
        return await ctx.lean.check(code, ws, CHECK_TIMEOUT, name)        # always a fresh strict Lean
    async with request.app[LOCK]:
        return await engine.certify(statement, ws, check, producer.for_ctx(ctx),
                                    sage_seconds=certstage.SAGE_SECONDS)


def _workspace(ctx, data: dict):
    return ctx.workspace(str(data.get("workspace") or "") or ctx.settings.workspace)


def _prepared(text: str) -> str | None:
    text = text.strip()[:MAX_STATEMENT]
    if text.startswith(":") or text.startswith("("):          # only `BINDERS : PROP`
        text = f"theorem certificat {text} := by sorry"
    try:
        return leancheck.prepare_statement(text)
    except leancheck.StatementError:
        return None


@routes.post("/api/certificates/check")
async def certificates_check(request: web.Request) -> web.Response:
    ctx = ctx_of(request)
    denied = _exec_allowed(request)
    if denied is not None:
        return denied
    data = await body(request)
    st = _prepared(str(data.get("statement") or ""))
    if st is None:
        return error(400, "bad_statement", "Énoncé mal formé (il faut « theorem … := by sorry »).")
    ws = _workspace(ctx, data)
    if ws is None or await ctx.lean.problems(ws):
        return error(409, "workspace", "L'espace de travail Lean n'est pas prêt.")
    if ctx.demo:
        return ok({"status": "none", "kinds": engine.kinds_of(st)})
    o = await _certify(request, ctx, st, ws)
    return ok({**o.to_dict(), "kinds": [t["kind"] for t in o.tried], "workspace": ws.key})


def _cell_statement(ctx, data: dict) -> tuple[str, str, str] | web.Response:
    """(`: PROP`, description, default title) from a Calcul cell and its stored result (text only, no execution)."""
    wb = getattr(ctx, "workbench", None)
    if wb is None:
        return error(404, "not_found")
    pid, doc, cid = valid_id(str(data.get("project_id") or "")), str(data.get("doc") or ""), str(data.get("cell_id") or "")
    try:
        from ...research.notebook import DEFAULT_DOC
        c = wb.calc.cell_view(pid, doc or DEFAULT_DOC, cid)
    except Exception:  # noqa: BLE001 (unknown project / document / cell)
        return error(404, "not_found")
    if c.get("language") != "sage" or c.get("stale"):
        return error(400, "certificate_unsupported", "Ce résultat n'a pas de certificat pris en charge.")
    outs = c.get("outputs") or []
    if not outs or any(o.get("type") == "error" for o in outs):
        return error(400, "certificate_unsupported", "Ce résultat n'a pas de certificat pris en charge.")
    shown = "\n".join(str(o.get("text", "")) if o.get("type") == "stream" else
                      str((o.get("data") or {}).get("text/plain", "")) for o in outs).strip()
    got = fromcalcul.statement_for(str(c.get("code") or ""), shown)
    if got is None:
        return error(400, "certificate_unsupported", "Ce résultat n'a pas de certificat pris en charge.")
    return got[0], got[1], (str(c.get("code") or "").strip().split("\n")[-1])[:120]


@routes.post("/api/certificates/dossier")
async def certificates_dossier(request: web.Request) -> web.Response:
    from ..routes_work import create_dossier, dossier_api
    ctx = ctx_of(request)
    denied = _exec_allowed(request)
    if denied is not None:
        return denied
    data = await body(request)
    name = "certificat_" + secrets.token_hex(4)
    title = str(data.get("title") or "").strip()[:200]
    words = ""
    if data.get("cell_id"):
        got = _cell_statement(ctx, data)
        if isinstance(got, web.Response):
            return got
        tail, words, default_title = got
        st = _prepared(f"theorem {name} {tail} := by sorry")
        title = title or msg("Certificat : {what}", what=default_title)["text"]
    else:
        st = _prepared(str(data.get("statement") or ""))
        if st is not None:
            st = st.replace(f"theorem {leancheck.theorem_name(st)}", f"theorem {name}", 1) \
                if leancheck.theorem_name(st) == "certificat" else st
    if st is None:
        return error(400, "bad_statement", "Énoncé mal formé (il faut « theorem … := by sorry »).")
    if data.get("dry"):                       # what would be certified, without running anything
        return ok({"statement": st, "kinds": engine.kinds_of(st), "what": words})
    ws = _workspace(ctx, data)
    if ws is None or await ctx.lean.problems(ws):
        return error(409, "workspace", "L'espace de travail Lean n'est pas prêt.")
    if ctx.demo:
        return error(409, "demo", "Indisponible dans la démonstration.")
    if not engine.kinds_of(st):
        return error(400, "certificate_unsupported", "Ce résultat n'a pas de certificat pris en charge.")
    o = await _certify(request, ctx, st, ws)
    out = {**o.to_dict(), "statement": st, "workspace": ws.key, "dossier": None}
    if not o.ok:
        return ok(out)
    d, _job = await create_dossier(ctx, {"statement": st, "title": title or msg("Certificat")["text"],
                                         "workspace": ws.key, "project_id": str(data.get("project_id") or ""),
                                         "start": False}, user_event=False)
    old = leancheck.theorem_name(st)
    if d.theorem != old:
        # the dossier proves its own theorem name (D19): the proof is renamed, then judged again by a fresh strict
        # Lean — what is stored is exactly what was checked
        code = re.sub(rf"(?<![\w.]){re.escape(old)}(?![\w'])", d.theorem, o.code)
        r = await ctx.lean.check(leancheck.with_axiom_probe(code, d.theorem), ws, CHECK_TIMEOUT, d.theorem)
        if not r.verdict.ok:
            await ctx.repo.delete(d.id)
            return ok({**out, "status": "rejected", "reason": r.verdict.summary})
        o.code, o.axioms = code, r.verdict.axioms
        out.update(code=code, statement=d.statement)
    info = workspace_info(ws)
    title_k = msg(engine.KINDS[o.kind]["title"])["text"]
    idx = d.add_proof(o.code, model=f"certificat:{o.kind}", meta={
        "axioms": o.axioms, "lean": info.get("lean", ""), "mathlib": info.get("mathlib", ""), "workspace": ws.key,
        "seconds": round(o.seconds, 1), "strategy": "certificate", "attempts": 1, "certificate": o.kind,
        "certificate_checker": o.checker, "certificate_witness": [w["text"] for w in o.witness][:20]})
    d.status = "proved"
    m = msg("Preuve trouvée et vérifiée par Lean (essai {i}, {s:.0f} s).", i=1, s=o.seconds)
    d.add_event("proof", m["text"], ref=idx, model=f"certificat:{o.kind}", key=m["key"], params=m["params"])
    key = ("Certificat ({title}) : témoin calculé par Sage, vérifié par Lean." if o.sage_seconds else
           "Certificat ({title}) : vérifié par Lean par un calcul direct.")
    m = msg(key, title=title_k)
    detail = "\n".join("- " + w["text"] for w in o.witness)
    d.add_event("certificate", m["text"] + ("\n" + detail if detail else ""), ref=idx, key=m["key"],
                params={**m["params"], "detail": detail, "cert_kind": o.kind, "checker": o.checker})
    await ctx.repo.save(d)
    try:
        entry = await asyncio.to_thread(ctx.library.add_proof, o.code, d.title, ws.key, d.id, [])
        if entry:
            ctx.bus.publish("library.updated", {"added": entry.name})
    except Exception as e:  # noqa: BLE001
        log.warning("library: %s", e)
    out["dossier"] = dossier_api(d)
    return ok(out, status=201)


def register(app: web.Application, ctx) -> None:
    app[LOCK] = asyncio.Semaphore(2)
    app.add_routes(routes)
