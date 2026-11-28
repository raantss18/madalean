"""« Attaque » API (session S-BJ, DECISIONS D69, docs/ATTACK.md, docs/API.md §6n).

    GET   /api/attack                          state, today's counters, workspace, current problems, queue
    POST  /api/attack/start · /api/attack/stop (host) start / stop the background loop (stop releases the leases)
    POST  /api/attack/workspace {accept: true} (host) consent to the download (≈ 10 GB; covers updates up to that)
    GET   /api/attack/submissions              prepared files, their checks and exact GitHub plans
    POST  /api/attack/submissions/{id}/send    (host) {plan: <plan id>} — the one click that opens the pull request
    POST  /api/attack/submissions/{id}/discard (host)
    GET   /api/attack/history
    PATCH /api/attack/settings                 (host) attack_* settings

Events: `attack.state`, `attack.submission`."""
from __future__ import annotations

import re

from aiohttp import web

from ...attack.engine import Attack
from ...attack.submit import SubmitError
from ...attack.workspace import ESTIMATE_GB
from ...logs import get
from ..common import body, ctx_of, host_only, ok

log = get("attack.api")
ATTACK = web.AppKey("attack", object)
SID_RE = re.compile(r"^s-\d{8}-[0-9a-f]{8}$")
SETTINGS = ("attack_enabled", "attack_kinds", "attack_usd_per_day", "attack_parallel", "attack_max_difficulty_open",
            "attack_post_notes")


def _fail(status: int, code: str, **params) -> web.Response:
    return web.json_response({"error": code, "params": params}, status=status)


def _attack(request) -> Attack:
    return request.app[ATTACK]


async def get_state(request: web.Request) -> web.Response:
    return ok(_attack(request).public())


@host_only
async def start(request: web.Request) -> web.Response:
    return ok(await _attack(request).start())


@host_only
async def stop(request: web.Request) -> web.Response:
    return ok(await _attack(request).stop())


@host_only
async def workspace(request: web.Request) -> web.Response:
    data = await body(request)
    if data.get("accept") is not True:
        return _fail(400, "accept_required", size_gb=ESTIMATE_GB)
    ctx = ctx_of(request)
    await ctx.patch_settings({"attack_download_max_gb": max(ESTIMATE_GB, float(ctx.settings.attack_download_max_gb))},
                             True)
    a = _attack(request)
    a.wake()
    return ok(a.public())


async def submissions(request: web.Request) -> web.Response:
    return ok(_attack(request).subs.public())


@host_only
async def send(request: web.Request) -> web.Response:
    from ...research import publish
    a, sid = _attack(request), request.match_info["id"]
    if not SID_RE.match(sid) or a.subs.get(sid) is None:
        return _fail(404, "not_found")
    ctx = ctx_of(request)
    tok = ctx.keys.get("github") if hasattr(ctx, "keys") else None
    if a.github is not None:
        gh = a.github
    elif not tok or not tok.strip():
        return _fail(409, "no_github_key")
    else:
        gh = publish.GitHub(re.sub(r"\s+", "", tok))
    data = await body(request)
    try:
        sub = await a.send(sid, str(data.get("plan") or ""), gh)
    except SubmitError as e:
        return _fail(e.status, e.code, **e.params)
    except publish.PublishError as e:
        return _fail(e.status, e.kind, **{k: v for k, v in e.info.items() if k != "log"})
    log.info("attack submission %s sent: %s", sid, sub.get("pr_url"))
    return ok({"submission": a.subs.item(sub)})


@host_only
async def discard(request: web.Request) -> web.Response:
    a, sid = _attack(request), request.match_info["id"]
    if not SID_RE.match(sid) or a.subs.get(sid) is None:
        return _fail(404, "not_found")
    sub = await a.discard(sid)
    return ok({"submission": a.subs.item(sub)})


async def history(request: web.Request) -> web.Response:
    return ok(list(reversed(_attack(request).history)))


@host_only
async def settings(request: web.Request) -> web.Response:
    data = await body(request)
    patch = {k: v for k, v in data.items() if k in SETTINGS}
    if "attack_kinds" in patch:
        kinds = patch["attack_kinds"]
        if not isinstance(kinds, list) or any(k not in ("known", "counterexample", "open") for k in kinds):
            return _fail(400, "invalid", key="attack_kinds")
    if set(data) - set(SETTINGS):
        return _fail(400, "unknown", keys=sorted(set(data) - set(SETTINGS))[:10])
    ctx = ctx_of(request)
    _s, errors = await ctx.patch_settings(patch, True)
    if errors:
        return _fail(400, "invalid", errors=errors)
    a = _attack(request)
    a.wake()
    return ok({k: getattr(ctx.settings, k) for k in SETTINGS})


def register(app: web.Application, ctx) -> None:
    a = getattr(ctx, "attack", None) or Attack(ctx)      # a test may prepare its own (fake desk, workspace)
    app[ATTACK] = a
    ctx.attack = a
    r = app.router
    r.add_get("/api/attack", get_state)
    r.add_post("/api/attack/start", start)
    r.add_post("/api/attack/stop", stop)
    r.add_post("/api/attack/workspace", workspace)
    r.add_get("/api/attack/submissions", submissions)
    r.add_post("/api/attack/submissions/{id}/send", send)
    r.add_post("/api/attack/submissions/{id}/discard", discard)
    r.add_get("/api/attack/history", history)
    r.add_patch("/api/attack/settings", settings)

    async def startup(_app) -> None:
        if not ctx.demo:
            a.start_loop()

    async def cleanup(_app) -> None:
        await a.shutdown()
    app.on_startup.append(startup)
    app.on_cleanup.append(cleanup)
