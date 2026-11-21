"""Assistant (streamed over the WebSocket), Jupyter endpoints + proxy, WebSocket bus, static UI."""
from __future__ import annotations

import asyncio
import json
import mimetypes
import uuid
from pathlib import Path

from aiohttp import WSMsgType, web

from ..brain.api import BrainError, Chunk
from ..i18n import language
from ..logs import get
from ..prompts import assistant_messages
from .common import body, ctx_of, error, ok
from .helpers import complete_once

log = get("routes")
routes = web.RouteTableDef()
ASSIST = web.AppKey("assistant_tasks", dict)
RID_RE = __import__("re").compile(r"^[A-Za-z0-9_-]{8,64}$")
# Same policy as the <meta> of web/index.html, plus what only a header can carry (frame-ancestors).
UI_CSP = ("default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' blob:; "
          "font-src 'self'; connect-src 'self'; frame-src 'self'; worker-src 'self'; object-src 'none'; "
          "base-uri 'none'; form-action 'self'; frame-ancestors 'self'")
UI_HEADERS = {"Content-Security-Policy": UI_CSP, "X-Content-Type-Options": "nosniff",
              "Referrer-Policy": "no-referrer",
              "Permissions-Policy": "camera=(), microphone=(), geolocation=(), payment=(), usb=(), "
                                    "interest-cohort=()"}
STATIC_DIR = web.AppKey("static_dir", Path)


# ---------------------------------------------------------------- assistant
@routes.post("/api/assistant")
async def assistant(request: web.Request) -> web.Response:
    """{messages:[{role,content}], context?: {lean?, notebook?, cell?, cell_type?, cells?, text?, dossier_id?},
    mode?} → {request_id}; the answer streams as `assistant.token` then `assistant.done` / `assistant.error`."""
    ctx = ctx_of(request)
    data = await body(request)
    msgs = data.get("messages")
    if not isinstance(msgs, list) or not msgs or not all(isinstance(m, dict) for m in msgs):
        return error(400, "bad_messages")
    context = data.get("context") if isinstance(data.get("context"), dict) else {}
    if context.get("dossier_id"):
        d = ctx.repo.get(str(context["dossier_id"]))
        if d is not None and not context.get("lean"):
            context = {**context, "lean": d.proof or d.statement}
    mode = data.get("mode") if data.get("mode") in ("local", "auto", "online") else ctx.settings.mode
    rid = data.get("request_id")
    if rid is not None and not (isinstance(rid, str) and RID_RE.match(rid)):
        return error(400, "bad_request_id")
    if rid in request.app[ASSIST]:
        return error(409, "request_id_in_use")
    rid = rid or "a-" + uuid.uuid4().hex[:10]
    full = assistant_messages(msgs[-40:], context, language())

    def on_chunk(ch: Chunk) -> None:
        if ch.kind in ("text", "thinking"):
            ctx.publish("assistant.token", {"request_id": rid, "kind": ch.kind, "text": ch.text})

    async def run() -> None:
        try:
            c = await complete_once(ctx, "assistant", full, mode, owner=rid, on_chunk=on_chunk, max_tokens=3000,
                                    temperature=0.4)
            ctx.publish("assistant.done", {"request_id": rid, "text": c.text, "model": c.model.key,
                                           "finish": c.finish})
        except asyncio.CancelledError:
            ctx.publish("assistant.done", {"request_id": rid, "text": "", "model": "", "finish": "cancelled"})
        except BrainError as e:
            ctx.publish("assistant.error", {"request_id": rid, "error": e.kind, "text": str(e)[:500]})
        except Exception as e:  # noqa: BLE001
            log.exception("assistant failed")
            ctx.publish("assistant.error", {"request_id": rid, "error": "internal", "text": str(e)[:500]})
        finally:
            request.app[ASSIST].pop(rid, None)

    # the 202 is written to the socket BEFORE the task can publish its first assistant.* event
    resp = ok({"request_id": rid}, status=202)
    resp.headers.update({"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff",
                         "Referrer-Policy": "no-referrer"})
    await resp.prepare(request)
    await resp.write_eof()
    task = request.app[ASSIST][rid] = ctx.spawn(run())
    if request["device"] is not None:
        owned = ctx.bus.owned.setdefault(request["device"].id, set())
        owned.add(task)
        task.add_done_callback(owned.discard)
    return resp


@routes.post("/api/assistant/{id}/stop")
async def assistant_stop(request: web.Request) -> web.Response:
    t = request.app[ASSIST].get(request.match_info["id"])
    if t is None:
        return ok({"stopped": False})
    t.cancel()
    return ok({"stopped": True})


# ---------------------------------------------------------------- jupyter
def _jupyter_allowed(request: web.Request) -> web.Response | None:
    if not request["local"] and not ctx_of(request).settings.remote_jupyter:
        return error(403, "jupyter_host_only", "Jupyter n'est accessible que depuis l'ordinateur hôte (réglage).")
    return None


@routes.get("/api/jupyter")
async def jupyter_status(request: web.Request) -> web.Response:
    return ok(ctx_of(request).jupyter.status())


@routes.post("/api/jupyter/start")
async def jupyter_start(request: web.Request) -> web.Response:
    if (r := _jupyter_allowed(request)) is not None:
        return r
    return ok(await ctx_of(request).jupyter.start())


@routes.post("/api/jupyter/stop")
async def jupyter_stop(request: web.Request) -> web.Response:
    if (r := _jupyter_allowed(request)) is not None:
        return r
    await ctx_of(request).jupyter.stop()
    return ok(ctx_of(request).jupyter.status())


@routes.get("/api/jupyter/notebooks")
async def jupyter_notebooks(request: web.Request) -> web.Response:
    if (r := _jupyter_allowed(request)) is not None:
        return r
    try:
        return ok({"notebooks": await ctx_of(request).jupyter.list_notebooks(request.query.get("path", ""))})
    except ValueError:
        return error(400, "bad_path")


@routes.get("/api/jupyter/notebook")
async def jupyter_notebook(request: web.Request) -> web.Response:
    if (r := _jupyter_allowed(request)) is not None:
        return r
    try:
        return ok(await ctx_of(request).jupyter.read_notebook(request.query.get("path", "")))
    except ValueError:
        return error(400, "bad_path")


@routes.post("/api/jupyter/notebook")
async def jupyter_notebook_create(request: web.Request) -> web.Response:
    if (r := _jupyter_allowed(request)) is not None:
        return r
    data = await body(request)
    try:
        return ok(await ctx_of(request).jupyter.create_notebook(str(data.get("path", "")),
                                                                str(data.get("kernel", "python3"))), status=201)
    except ValueError:
        return error(400, "bad_path")


@routes.post("/api/jupyter/cells")
async def jupyter_append_cell(request: web.Request) -> web.Response:
    if (r := _jupyter_allowed(request)) is not None:
        return r
    data = await body(request)
    ct = data.get("cell_type", "code")
    if ct not in ("code", "markdown", "raw"):
        return error(400, "bad_cell_type")
    try:
        return ok(await ctx_of(request).jupyter.append_cell(str(data.get("path", "")), str(data.get("source", "")), ct))
    except ValueError:
        return error(400, "bad_path")


async def jupyter_proxy(request: web.Request) -> web.StreamResponse:
    if (r := _jupyter_allowed(request)) is not None:
        return r
    return await ctx_of(request).jupyter.proxy(request)


# ---------------------------------------------------------------- websocket
@routes.get("/api/ws")
async def ws_handler(request: web.Request) -> web.WebSocketResponse:
    ctx = ctx_of(request)
    bus = ctx.bus
    ws = web.WebSocketResponse(heartbeat=30, max_msg_size=1 << 20)
    await ws.prepare(request)
    cred = request["device"].id if request["device"] is not None else None
    if cred:
        bus.sockets.setdefault(cred, set()).add(ws)
    q = bus.subscribe()
    bus.clients += 1
    ctx.monitor.wake()                             # fresh GPU / disk status for the new client, fast pace again
    state = {"last": bus.seq}
    lock = asyncio.Lock()

    async def send(ev: dict) -> None:
        async with lock:
            if ev.get("seq", 0) <= state["last"] and ev["type"] not in ("hello", "resync", "pong"):
                return
            if "seq" in ev and ev["type"] not in ("hello", "resync", "pong"):
                state["last"] = ev["seq"]
            await ws.send_str(json.dumps(ev, ensure_ascii=False, default=str))

    async def writer() -> None:
        while True:
            ev = await q.get()
            if ev is None:
                await ws.close(code=4000, message=b"too slow, resume")
                return
            await send(ev)

    await send({"type": "hello", "seq": bus.seq, "boot": bus.boot, "version": ctx.version, "local": request["local"]})
    wtask = asyncio.create_task(writer())
    try:
        async for m in ws:
            if m.type != WSMsgType.TEXT:
                continue
            try:
                data = json.loads(m.data)
            except ValueError:
                continue
            t = data.get("type") if isinstance(data, dict) else None
            if t == "resume":
                seq = data.get("seq")
                missed = bus.since(int(seq)) if isinstance(seq, int) and data.get("boot", bus.boot) == bus.boot else None
                if missed is None:
                    async with lock:
                        state["last"] = bus.seq
                        await ws.send_str(json.dumps({"type": "resync", "seq": bus.seq, "boot": bus.boot}))
                else:
                    async with lock:
                        state["last"] = int(seq)
                    for ev in missed:
                        await send(ev)
            elif t == "ping":
                await ws.send_str(json.dumps({"type": "pong", "t": data.get("t")}))
    finally:
        wtask.cancel()
        bus.unsubscribe(q)
        bus.clients = max(0, bus.clients - 1)
        if cred and cred in bus.sockets:
            bus.sockets[cred].discard(ws)
            if not bus.sockets[cred]:
                del bus.sockets[cred]
    return ws


# ---------------------------------------------------------------- static UI
PLACEHOLDER = """<!doctype html><html lang="fr"><head><meta charset="utf-8"><meta name="viewport"
content="width=device-width,initial-scale=1"><title>Madalean</title><style>:root{color-scheme:light dark}
body{font:16px/1.5 system-ui,sans-serif;max-width:40rem;margin:3rem auto;padding:0 1rem}code{font-size:.9em}
</style></head><body><h1>Madalean</h1><p>Le serveur fonctionne. L'interface web n'est pas encore installée
(<code>madalean/static/</code> est vide).</p><p lang="en">The server is running. The web interface is not built yet.
API: <a href="/api/hello">/api/hello</a>.</p></body></html>"""


async def static_handler(request: web.Request) -> web.StreamResponse:
    root: Path = request.app[STATIC_DIR].resolve()
    rel = request.match_info.get("tail", "")
    if "\x00" in rel or "\\" in rel:
        return error(400, "bad_path")
    target = (root / rel).resolve() if rel else root / "index.html"
    try:
        target.relative_to(root)
    except ValueError:
        return error(404, "not_found")
    if any(part.startswith(".") for part in target.relative_to(root).parts):
        return error(404, "not_found")
    if target.is_file():
        ct, _enc = mimetypes.guess_type(target.name)
        headers = {"Cache-Control": "public, max-age=31536000, immutable" if "/assets/" in f"/{rel}"
                   else "no-cache"}
        extra = UI_HEADERS if target.suffix == ".html" else {}
        return web.FileResponse(target, headers={**headers, **extra, **({"Content-Type": ct} if ct else {})})
    index = root / "index.html"
    if Path(rel).suffix and rel:                       # a missing asset: 404, not the SPA page
        return error(404, "not_found")
    if index.is_file():
        return web.FileResponse(index, headers={"Cache-Control": "no-cache", **UI_HEADERS})
    return web.Response(text=PLACEHOLDER, content_type="text/html", headers={"Cache-Control": "no-cache", **UI_HEADERS})
