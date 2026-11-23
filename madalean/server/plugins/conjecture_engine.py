"""« Moteur de conjectures » API (session S-AW, DECISIONS D55): the guided loop Explore → Recognise → State →
Attack → Journal behind the « Explorer » button of the Conjectures screen. Reference: docs/CONJECTURES.md,
docs/API.md §Conjecture engine. The conjecture API of the research workshop (`/api/conjectures…`) is unchanged: a
kept candidate is created through `Workshop.create`, like a conjecture written by hand.

Execution: an exploration's experiment is a cell of the project's Calcul notebook « explorations »; this plugin
never executes code itself — it asks the Calcul workbench, which applies the approval rule (model code runs only
once this exact code was approved on this host, or with `experiments_auto`) — and only for a device allowed to
execute (the host, or paired devices when the host enabled `experiments_remote`)."""
from __future__ import annotations

import asyncio

from aiohttp import web

from ...logs import get
from ...research import cjengine as E
from ..common import body, ctx_of, error, ok, valid_id

log = get("explore")
EX = web.AppKey("conjecture_engine", object)


def eng(request) -> E.Engine:
    e = request.app[EX]
    ctx = ctx_of(request)
    if e._wb is None or e._rs is None:           # the two other plugins register in any order: bound on first use
        e.bind(getattr(ctx, "workbench", None), getattr(ctx, "research", None))
    return e


def device_of(request) -> str:
    dev = request["device"]
    return dev.id if dev is not None else "host"


def fail(e: E.ExploreError) -> web.Response:
    return web.json_response({"error": e.kind, **{k: v for k, v in e.data.items() if k != "job"}}, status=e.status)


def exec_allowed(request) -> bool:
    """Experiments execute code on the host: from paired devices only when the host enabled it (the same rule and
    the same setting as Calcul and the conjecture experiments)."""
    return bool(request["local"]) or bool(getattr(ctx_of(request).settings, "experiments_remote", False))


def _project(request) -> str:
    pid = valid_id(request.match_info["pid"])
    if ctx_of(request).projects.get(pid) is None:
        raise web.HTTPNotFound(text='{"error":"not_found"}', content_type="application/json")
    return pid


def _x(request) -> dict:
    try:
        return eng(request).get(valid_id(request.match_info["xid"]))
    except E.ExploreError as e:
        raise web.HTTPNotFound(text='{"error":"not_found"}', content_type="application/json") from e


async def _view(request, x: dict) -> dict:
    """The exploration plus what the screen needs to show the approval prompt (never trusted for running: the
    workbench checks the notebook itself at run time)."""
    e = eng(request)
    cell = None
    try:
        c = await e.cell_view(x)
    except E.ExploreError:
        c = None
    if c is not None and c.get("type") in ("code", "ask"):
        auto = bool(ctx_of(request).settings.experiments_auto)
        cell = {"doc": x["cell"]["doc"], "id": c["id"], "code": c["code"], "code_hash": c["code_hash"],
                "origin": c["origin"], "model": c.get("model", ""), "approved": bool(
                    (c.get("approved") or {}).get("hash") == c["code_hash"]),
                "may_run": e.wb.calc.may_run(c, auto), "language": c["language"]}
    return {"exploration": E.public(x), "cell": cell, "running": e.running(x["id"]),
            "exec_allowed": exec_allowed(request) or x["origin"] == "data" or bool(ctx_of(request).demo)}


async def status(request):
    pid = request.query.get("project", "")
    try:
        st = await eng(request).status(pid if pid and ctx_of(request).projects.get(pid) is not None else "")
    except E.ExploreError as e:
        return fail(e)
    st["local"] = bool(request["local"])
    return ok(st)


async def list_(request):
    pid = _project(request)
    return ok({"explorations": [E.public(x, brief=True) for x in eng(request).store.list(pid)]})


async def create(request):
    pid = _project(request)
    data = await body(request)
    try:
        x = await eng(request).create(pid, str(data.get("question", "")), language=str(data.get("language", "")),
                                      device=device_of(request))
    except E.ExploreError as e:
        return fail(e)
    return ok(await _view(request, x), status=201)


async def get_(request):
    return ok(await _view(request, _x(request)))


async def delete(request):
    e, x = eng(request), _x(request)
    if e.running(x["id"]):
        return error(409, "busy")
    e.delete(x)
    return ok({"deleted": True})


async def patch(request):
    e, x = eng(request), _x(request)
    data = await body(request)
    if "code" not in data:
        return error(400, "bad_fields")
    try:
        await e.set_code(x, str(data.get("code") or ""), device_of(request))
    except E.ExploreError as err:
        return fail(err)
    return ok(await _view(request, x))


async def run(request):
    e, x = eng(request), _x(request)
    needs_exec = x["origin"] != "data" and not ctx_of(request).demo
    if needs_exec and not exec_allowed(request):
        return error(403, "experiments_host_only")
    if e.running(x["id"]):
        return error(409, "busy")
    if x["origin"] != "data" and not await e.may_run(x):
        # said at once, before anything starts: this code was written by a model and is not approved
        x["steps"]["explore"].update({"state": "awaiting_approval", "error": "not_approved"})
        e.save(x)
        return error(403, "not_approved")
    try:
        e.start(x, e.run(x, device_of(request)))
    except E.ExploreError as err:
        return fail(err)
    return ok({"started": True, **(await _view(request, x))}, status=202)


async def stop(request):
    e, x = eng(request), _x(request)
    await e.stop(x)
    await asyncio.sleep(0)
    return ok(await _view(request, x))


async def warm(request):
    """D47: opening an exploration whose experiment may run prepares its kernel in the background."""
    e, x = eng(request), _x(request)
    ctx = ctx_of(request)
    if ctx.demo or not x.get("cell") or not x["cell"].get("code_hash") or not exec_allowed(request) \
            or not getattr(ctx.settings, "calcul_warm", True):
        return ok({"warm": None})
    import os
    if os.environ.get("MADALEAN_NO_CALCUL_WARM") == "1":
        return ok({"warm": None})
    km = e.wb.kernels()
    if not hasattr(km, "prewarm"):
        return ok({"warm": None})
    return ok({"warm": km.prewarm(e.wb.calc.rel_path(x["project_id"], x["cell"]["doc"]), x["language"])})


def _cid(request) -> str:
    return str(request.match_info["cid"])[:40]


async def cand_keep(request):
    e, x = eng(request), _x(request)
    try:
        c = e._cand(x, _cid(request))
        existed = bool(c.get("conjecture_id"))
        d = await e.keep(x, c["id"], device_of(request))
    except E.ExploreError as err:
        return fail(err)
    except Exception as err:  # noqa: BLE001 (StatementError, ConjectureError: said as they are)
        log.info("keep failed: %s", err)
        return error(422, "keep_failed")
    return ok({"conjecture_id": d.id, "duplicate": existed, **(await _view(request, x))}, status=200 if existed else 201)


async def cand_discard(request):
    e, x = eng(request), _x(request)
    data = await body(request)
    try:
        await e.discard(x, _cid(request), str(data.get("reason", "")))
    except E.ExploreError as err:
        return fail(err)
    return ok(await _view(request, x))


async def cand_attack(request):
    e, x = eng(request), _x(request)
    if x["origin"] != "data" and not ctx_of(request).demo and not exec_allowed(request):
        return error(403, "experiments_host_only")
    if e.running(x["id"]):
        return error(409, "busy")
    try:
        c = e._cand(x, _cid(request))
        e.start(x, e.attack(x, c["id"], device_of(request)))
    except E.ExploreError as err:
        return fail(err)
    return ok({"started": True, **(await _view(request, x))}, status=202)


async def cand_prove(request):
    e, x = eng(request), _x(request)
    data = await body(request)
    try:
        res = await e.prove(x, _cid(request), device_of(request), str(data.get("mode", "")))
    except E.ExploreError as err:
        if err.kind == "busy" and err.data.get("job"):
            return web.json_response({"error": "busy", "job": err.data["job"]}, status=409)
        return fail(err)
    except Exception as err:  # noqa: BLE001
        log.info("prove failed: %s", err)
        return error(422, "keep_failed")
    return ok({**res, **(await _view(request, x))}, status=202)


async def export(request):
    e, x = eng(request), _x(request)
    data = await body(request)
    try:
        res = await e.export(x, str(data.get("to", "note")), device_of(request))
    except E.ExploreError as err:
        return fail(err)
    return ok({**res, **(await _view(request, x))})


# ---------------------------------------------------------------- demo (scripted brain, recorded OEIS answer)
DEMO_CODE = ("```sage\n# nombre de carrés parfaits ≤ n\ndef cj_rows_for(n):\n    n = ZZ(n)\n"
             "    return [[n, isqrt(n)]]\n\ncj_columns = ['n', 'a']\ncj_index = list(range(1, 61))\n"
             "cj_rows = [r for n in cj_index for r in cj_rows_for(n)]\ntable(cj_rows[:30], header_row=cj_columns)\n```")


def demo_answer(first: str) -> str | None:
    return DEMO_CODE if first.startswith("[madalean:explore]") else None


def _demo(ctx, engine: E.Engine) -> None:
    from pathlib import Path

    from ...research.fetch import Fetcher, ReplayTransport
    from ...research.oeis import Oeis
    engine.oeis = Oeis(Fetcher(ReplayTransport(Path(E.__file__).resolve().parent / "demo_oeis")), None)
    br = ctx.brain
    if not hasattr(br, "responder"):
        return
    base = br.responder

    def responder(role, messages, brain):
        first = next((m.get("content", "") for m in messages if m.get("role") == "user"), "")
        ans = demo_answer(first)
        return ans if ans is not None else base(role, messages, brain)
    br.responder = responder


def register(app: web.Application, ctx) -> None:
    engine = E.Engine(ctx)
    app[EX] = engine
    ctx.conjecture_engine = engine
    a = app.router
    a.add_get("/api/explore/status", status)
    a.add_get("/api/projects/{pid}/explorations", list_)
    a.add_post("/api/projects/{pid}/explorations", create)
    x = "/api/explorations/{xid}"
    a.add_get(x, get_)
    a.add_patch(x, patch)
    a.add_delete(x, delete)
    a.add_post(x + "/run", run)
    a.add_post(x + "/stop", stop)
    a.add_post(x + "/warm", warm)
    a.add_post(x + "/export", export)
    a.add_post(x + "/candidates/{cid}/keep", cand_keep)
    a.add_post(x + "/candidates/{cid}/discard", cand_discard)
    a.add_post(x + "/candidates/{cid}/attack", cand_attack)
    a.add_post(x + "/candidates/{cid}/prove", cand_prove)

    async def startup(_app):
        if ctx.demo:
            _demo(ctx, engine)

    async def cleanup(_app):
        await engine.close()
    app.on_startup.append(startup)
    app.on_cleanup.append(cleanup)
