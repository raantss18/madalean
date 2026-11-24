"""« Mémoire » (D62): memory bundles — export with choices, host-only import with a dry-run preview and Lean
re-verification, read-only references, scheduled local backups, the training-dataset export. Reference:
docs/MEMORY.md, docs/API.md « Memory »."""
from __future__ import annotations

import asyncio
import re
import time

from aiohttp import web

from ... import memory as M
from ...logs import get
from ..common import body, ctx_of, error, host_only, ok

log = get("memory")
MEM = web.AppKey("memory", object)
TICK = 3600.0                         # backup schedule checked every hour
MAX_SESSIONS = 3
SESSION_TTL = 3600.0


class MemoryService:
    def __init__(self, ctx):
        self.ctx = ctx
        self.sessions: dict[str, dict] = {}       # token → {bundle, preview, state, progress, report, t}
        self.lock = asyncio.Lock()                # one import / re-verification at a time

    def _gc(self) -> None:
        now = time.time()
        for k, s in list(self.sessions.items()):
            if now - s["t"] > SESSION_TTL and s["state"] != "running":
                self.sessions.pop(k, None)
        while len(self.sessions) >= MAX_SESSIONS:
            old = min((s for s in self.sessions.items() if s[1]["state"] != "running"), key=lambda s: s[1]["t"],
                      default=None)
            if old is None:
                break
            self.sessions.pop(old[0], None)

    def new_session(self, bundle, preview: dict | None) -> str:
        self._gc()
        tok = M.new_token()
        self.sessions[tok] = {"bundle": bundle, "preview": preview, "state": "ready", "progress": {}, "report": None,
                              "t": time.time()}
        return tok

    def start(self, tok: str, work) -> None:
        s = self.sessions[tok]
        s["state"] = "running"

        def progress(p: dict) -> None:
            s["progress"] = p
            self.ctx.publish("memory.import", {"token": tok, **p})

        async def run() -> None:
            try:
                async with self.lock:
                    s["report"] = await work(progress)
                s["state"] = "done"
            except Exception as e:  # noqa: BLE001
                log.exception("memory import failed")
                s["state"], s["report"] = "error", {"error": str(e)[:300]}
            s["bundle"] = None                    # the bytes are not kept once applied
            self.ctx.publish("memory.import", {"token": tok, "stage": s["state"]})
        self.ctx.spawn(run())


def S(request) -> MemoryService:
    return request.app[MEM]


def _public(s: dict) -> dict:
    return {"state": s["state"], "progress": s["progress"], "report": s["report"], "preview": s["preview"]}


async def mem_status(request):
    return ok(await asyncio.to_thread(M.status, ctx_of(request)))


def export_options(q) -> dict:
    """Query → options: parts=a,b · projects=id1,id2 (absent = all projects) · include_copyrighted=1 ·
    include_files=1. A real URL (not a blob), so that the Android shell can download it with its token."""
    data: dict = {"include_copyrighted": q.get("include_copyrighted") == "1",
                  "include_files": q.get("include_files") == "1"}
    if "parts" in q:
        data["parts"] = [p for p in q["parts"].split(",") if p]
    if "projects" in q:
        data["projects"] = [p for p in q["projects"].split(",") if p]
    return data


async def mem_export(request):
    """GET ?parts&projects&include_copyrighted&include_files → the .madalean-memory file."""
    data = export_options(request.query)
    blob, info = await asyncio.to_thread(M.export_bundle, ctx_of(request), data)
    name = "madalean-memory-" + time.strftime("%Y%m%d-%H%M%S") + M.EXT
    return web.Response(body=blob, content_type="application/zip", headers={
        "Content-Disposition": f'attachment; filename="{name}"', "X-Madalean-Excluded": str(len(info["excluded"])),
        "Cache-Control": "no-store"})


async def _read_upload(request) -> bytes:
    if request.content_length and request.content_length > M.MAX_BUNDLE:
        raise M.BundleError("too_large")
    out = bytearray()
    async for chunk in request.content.iter_chunked(1 << 16):
        out += chunk
        if len(out) > M.MAX_BUNDLE:
            raise M.BundleError("too_large")
    return bytes(out)


@host_only
async def mem_inspect(request):
    """The raw bundle as the body → {token, preview}. Nothing is written."""
    ctx = ctx_of(request)
    try:
        data = await _read_upload(request)
        b = await asyncio.to_thread(M.read_bundle, data)
        preview = await asyncio.to_thread(M.plan_import, ctx, b)
    except M.BundleError as e:
        return web.json_response({"error": e.kind, "detail": e.detail}, status=413 if e.kind == "too_large" else 400)
    tok = S(request).new_session(b, preview)
    return ok({"token": tok, "preview": preview})


@host_only
async def mem_apply(request):
    svc, ctx = S(request), ctx_of(request)
    s = svc.sessions.get(request.match_info["token"])
    if s is None or s["bundle"] is None:
        return error(404, "not_found")
    if s["state"] != "ready":
        return error(409, "already_started")
    if svc.lock.locked():
        return error(409, "busy")
    b = s["bundle"]
    svc.start(request.match_info["token"], lambda p: M.apply_import(ctx, b, p))
    return ok({"started": True})


async def mem_session(request):
    s = S(request).sessions.get(request.match_info["token"])
    return ok(_public(s)) if s is not None else error(404, "not_found")


async def unverified_list(request):
    rows = await asyncio.to_thread(M.pending_of(ctx_of(request)).list)
    return ok({"entries": [{k: r.get(k) for k in ("name", "title", "statement", "workspace", "reason", "detail",
                                                  "t_import")} for r in rows]})


@host_only
async def unverified_verify(request):
    svc, ctx = S(request), ctx_of(request)
    if svc.lock.locked():
        return error(409, "busy")
    tok = svc.new_session(None, None)
    svc.start(tok, lambda p: M.reverify_pending(ctx, p))
    return ok({"token": tok})


@host_only
async def unverified_delete(request):
    return ok({"deleted": await asyncio.to_thread(M.pending_of(ctx_of(request)).drop, request.match_info["name"])})


async def refs_list(request):
    return ok(await asyncio.to_thread(M.references, ctx_of(request)))


@host_only
async def refs_delete(request):
    done = await asyncio.to_thread(M.delete_reference, ctx_of(request), request.match_info["kind"],
                                   request.match_info["rid"])
    return ok({"deleted": done}) if done else error(404, "not_found")


@host_only
async def backups_patch(request):
    data = await body(request)
    try:
        s = await asyncio.to_thread(M.set_backup_settings, ctx_of(request), data)
    except M.BundleError as e:
        return web.json_response({"error": e.kind, "field": e.detail}, status=400)
    return ok({"backups": s})


@host_only
async def backups_run(request):
    try:
        r = await asyncio.to_thread(M.run_backup, ctx_of(request))
    except OSError as e:
        return error(500, "backup_failed", "{why}", why=str(e)[:200])
    return ok(r)


async def dataset(request):
    text = await asyncio.to_thread(M.dataset_jsonl, ctx_of(request))
    return web.Response(text=text, content_type="application/x-ndjson", charset="utf-8", headers={
        "Content-Disposition": 'attachment; filename="madalean-dataset.jsonl"', "Cache-Control": "no-store",
        "X-Madalean-Rows": str(text.count("\n"))})


def register(app: web.Application, ctx) -> None:
    svc = MemoryService(ctx)
    app[MEM] = svc
    ctx.memory = svc
    r = app.router
    r.add_get("/api/memory", mem_status)
    r.add_get("/api/memory/export", mem_export)
    r.add_post("/api/memory/import", mem_inspect)
    r.add_post("/api/memory/import/{token}", mem_apply)
    r.add_get("/api/memory/import/{token}", mem_session)
    r.add_get("/api/memory/unverified", unverified_list)
    r.add_post("/api/memory/unverified/verify", unverified_verify)
    r.add_delete("/api/memory/unverified/{name}", unverified_delete)
    r.add_get("/api/memory/references", refs_list)
    r.add_delete("/api/memory/references/{kind}/{rid}", refs_delete)
    r.add_patch("/api/memory/backups", backups_patch)
    r.add_post("/api/memory/backups/run", backups_run)
    r.add_get("/api/memory/dataset", dataset)
    tasks: set[asyncio.Task] = set()

    async def loop() -> None:
        await asyncio.sleep(60)
        while True:
            try:
                if await asyncio.to_thread(M.backup_due, ctx):
                    res = await asyncio.to_thread(M.run_backup, ctx)
                    log.info("memory backup written: %s", res["name"])
            except Exception as e:  # noqa: BLE001 (a full disk never stops the server)
                log.warning("memory backup failed: %s", e)
                try:
                    _note_error(ctx, str(e))
                except Exception:  # noqa: BLE001
                    pass
            await asyncio.sleep(TICK)

    async def startup(_app) -> None:
        if not getattr(ctx, "demo", False):
            tasks.add(asyncio.create_task(loop()))

    async def cleanup(_app) -> None:
        for t in tasks:
            t.cancel()
    app.on_startup.append(startup)
    app.on_cleanup.append(cleanup)


def _note_error(ctx, why: str) -> None:
    import json
    from ... import config
    s = M.backup_settings(ctx)
    s["last_error"] = re.sub(r"\s+", " ", why)[:300]
    s["last"] = time.time()                     # retried at the next period, not every hour
    config.atomic_write_text(M.memory_dir(ctx) / "backups.json", json.dumps(s, indent=1))


__all__ = ["register", "MEM"]
