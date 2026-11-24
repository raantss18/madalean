"""« Préparer pour Mathlib » API (session S-BC, DECISIONS D61, docs/MATHLIB_CONTRIB.md).

    GET  /api/mathlib/contrib?kind=library|dossier&id=…   the last package of that result (or null), whether a
                                                          preparation runs, whether a GitHub key is saved
    POST /api/mathlib/contrib            {kind, id, author?}  start (or restart) the preparation → the package
    GET  /api/mathlib/contrib/file?kind&id                 the Lean file, as a download
    POST /api/mathlib/contrib/reprove    {kind, id}        the port failed: a new dossier in lean-current with the
                                                          statement, proved by the normal pipeline, old proof as hint
    POST /api/mathlib/contrib/github/plan {kind, id, step: branch|pr}   (host) exactly what would be sent
    POST /api/mathlib/contrib/github/send {kind, id, plan}             (host) send that confirmed plan, once

Nothing is sent to GitHub without a plan the user saw and confirmed; the PR needs its own plan and confirmation."""
from __future__ import annotations

import asyncio
import re
import time

from aiohttp import web

from ...logs import get
from ...research import mathlib_contrib as MC
from ..common import body, ctx_of, host_only, ok

log = get("mathlib_contrib")
routes = web.RouteTableDef()
TASKS = web.AppKey("mathlib_contrib_tasks", dict)
PLANS = web.AppKey("mathlib_contrib_plans", dict)
LOCK = web.AppKey("mathlib_contrib_lock", asyncio.Semaphore)
ID_RE = re.compile(r"^[\w.'₀-₉-]{1,200}$")


def _fail(status: int, code: str, **params) -> web.Response:
    return web.json_response({"error": code, "params": params}, status=status)


def _source(data) -> tuple[str, str] | None:
    kind, ident = str(data.get("kind", "")), str(data.get("id", ""))
    if kind not in ("library", "dossier") or not ID_RE.match(ident):
        return None
    return kind, ident


def _github_configured(ctx) -> bool:
    try:
        tok = ctx.keys.get("github") if hasattr(ctx, "keys") else None
    except Exception:  # noqa: BLE001
        tok = None
    return bool(tok and tok.strip())


def _state(request, kind: str, ident: str) -> dict:
    ctx = ctx_of(request)
    key = MC.source_key(kind, ident)
    task = request.app[TASKS].get(key)
    return {"package": MC.load(ctx, key), "running": bool(task and not task.done()),
            "github": {"configured": _github_configured(ctx), "host": bool(request["local"])},
            "default_author": MC.DEFAULT_AUTHOR}


@routes.get("/api/mathlib/contrib")
async def contrib_get(request: web.Request) -> web.Response:
    src = _source(request.query)
    if src is None:
        return _fail(400, "bad_source")
    return ok(_state(request, *src))


@routes.post("/api/mathlib/contrib")
async def contrib_start(request: web.Request) -> web.Response:
    ctx = ctx_of(request)
    data = await body(request)
    src = _source(data)
    if src is None:
        return _fail(400, "bad_source")
    try:
        s = await asyncio.to_thread(MC.source_of, ctx, *src)
    except MC.ContribError as e:
        return _fail(e.status, e.code, **e.params)
    key = MC.source_key(*src)
    tasks = request.app[TASKS]
    if key in tasks and not tasks[key].done():
        return _fail(409, "running")
    author = " ".join(str(data.get("author") or MC.DEFAULT_AUTHOR).split())[:120] or MC.DEFAULT_AUTHOR
    prep = MC.Preparation(ctx, s, author, on_change=lambda p: ctx.publish("mathlib.contrib",
                                                                          {"key": p["key"], "state": p["state"]}))
    MC.save(ctx, prep.pkg)

    async def run():
        async with request.app[LOCK]:
            return await prep.run()
    tasks[key] = asyncio.create_task(run(), name=f"mathlib-contrib-{key}")
    return ok(_state(request, *src))


@routes.get("/api/mathlib/contrib/file")
async def contrib_file(request: web.Request) -> web.Response:
    src = _source(request.query)
    if src is None:
        return _fail(400, "bad_source")
    pkg = MC.load(ctx_of(request), MC.source_key(*src))
    if not pkg or not pkg.get("file"):
        return _fail(404, "no_file")
    name = re.sub(r"[^A-Za-z0-9_.-]", "_", pkg["file"]["path"].rsplit("/", 1)[-1])
    return web.Response(text=pkg["file"]["text"], content_type="text/plain", charset="utf-8",
                        headers={"Content-Disposition": f'attachment; filename="{name}"'})


@routes.post("/api/mathlib/contrib/reprove")
async def contrib_reprove(request: web.Request) -> web.Response:
    """The automatic port failed: the normal proof pipeline in lean-current, the old proof as the user's hint."""
    from ...dossiers import main_signature
    from ..routes_work import create_dossier
    ctx = ctx_of(request)
    data = await body(request)
    src = _source(data)
    if src is None:
        return _fail(400, "bad_source")
    pkg = MC.load(ctx, MC.source_key(*src))
    if not pkg or pkg.get("state") != "port_failed":
        return _fail(409, "not_port_failed")
    try:
        s = await asyncio.to_thread(MC.source_of, ctx, *src)
    except MC.ContribError as e:
        return _fail(e.status, e.code, **e.params)
    decls = MC.split_decls(s["body"])
    main = next((d for d in decls if d.name == s["main"]), None)
    sig = main_signature(main.text, main.name) if main else ""
    if not sig or ctx.workspace(MC.TARGET_WS) is None:
        return _fail(409, "no_statement")
    statement = MC.HEADER_CURRENT + sig + " by sorry\n"
    statement, _r = MC.rename_idents(statement, MC.BUILTIN_RENAMES)
    statement, _s = MC.syntax_port(statement)
    d, _job = await create_dossier(ctx, {"statement": statement, "title": s["title"], "workspace": MC.TARGET_WS,
                                         "start": False, "rename": True,
                                         "project_id": getattr(ctx.repo.get(s["dossier"]), "project_id", "")
                                         if s.get("dossier") else ""})
    hint = ("A proof of this statement was verified with an older Mathlib (Lean 4.9); names may have changed "
            "since. Adapt it:\n```lean4\n" + s["body"][:6000] + "\n```")
    job = ctx.orchestrator.submit(d.id, [{"stage": "proof", "request": hint}])
    return ok({"dossier": d.id, "job": job.id})


async def _token_and_pkg(request, data):
    ctx = ctx_of(request)
    src = _source(data)
    if src is None:
        return None, None, _fail(400, "bad_source")
    if not _github_configured(ctx):
        return None, None, _fail(409, "no_github_key")
    pkg = MC.load(ctx, MC.source_key(*src))
    if not pkg or pkg.get("state") != "ready" or not pkg.get("file"):
        return None, None, _fail(409, "not_ready")
    return re.sub(r"\s+", "", ctx.keys.get("github")), pkg, None


@routes.post("/api/mathlib/contrib/github/plan")
@host_only
async def contrib_github_plan(request: web.Request) -> web.Response:
    """Read-only: who the key belongs to (GET /user), then the exact requests a confirmation would send."""
    from ...research import publish
    data = await body(request)
    token, pkg, err = await _token_and_pkg(request, data)
    if err:
        return err
    step = str(data.get("step", "branch"))
    if step == "pr" and not pkg.get("github", {}).get("branch"):
        return _fail(409, "no_branch")
    gh = publish.GitHub(token)
    try:
        login = await MC.github_login(gh)
    except publish.PublishError as e:
        return _fail(e.status, e.kind, **{k: v for k, v in e.info.items() if k != "log"})
    plan = MC.plan_pr(pkg, login) if step == "pr" else MC.plan_branch(pkg, login)
    plan["key"] = pkg["key"]
    plans = request.app[PLANS]
    for pid in [p for p, v in plans.items() if v["expires"] < time.time()]:
        plans.pop(pid, None)
    plans[plan["id"]] = plan
    return ok({"plan": plan})


@routes.post("/api/mathlib/contrib/github/send")
@host_only
async def contrib_github_send(request: web.Request) -> web.Response:
    from ...research import publish
    ctx = ctx_of(request)
    data = await body(request)
    token, pkg, err = await _token_and_pkg(request, data)
    if err:
        return err
    plan = request.app[PLANS].pop(str(data.get("plan", "")), None)       # a plan is sent at most once
    if plan is None or plan["key"] != pkg["key"] or plan["expires"] < time.time():
        return _fail(409, "plan_expired")
    gh = publish.GitHub(token)
    try:
        if plan["kind"] == "branch":
            res = await MC.github_branch(gh, pkg, plan)
            pkg.setdefault("github", {})["branch"] = res
        else:
            res = await MC.github_pr(gh, plan)
            pkg.setdefault("github", {})["pr"] = res
    except publish.PublishError as e:
        return _fail(e.status, e.kind, **{k: v for k, v in e.info.items() if k != "log"})
    except MC.ContribError as e:
        return _fail(e.status, e.code, **e.params)
    MC.save(ctx, pkg)
    log.info("mathlib contribution %s: GitHub %s done", pkg["key"], plan["kind"])
    return ok({"result": res, "package": pkg})


def register(app: web.Application, ctx) -> None:
    app[TASKS] = {}
    app[PLANS] = {}
    app[LOCK] = asyncio.Semaphore(1)
    app.add_routes(routes)
