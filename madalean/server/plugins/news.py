"""Plugin of session S-AV: « Actualités », the permanent mathematical watch (docs/NEWS.md, DECISIONS D54).

Routes (JSON; every one is available to paired devices — the store holds public information only):
- `GET   /api/news`                     ?q= &branch= (repeatable) &source= &group= &open=1 &projects=1|<project id>
                                        &unread=1 &saved=1 &mine=1 (the followed domains) &order=date|relevance
                                        &limit= &offset=  → {items, total, unread}
- `GET   /api/news/overview`            the Home card and the badge: unread counts, the three newest, last / next
                                        refresh, mode
- `GET   /api/news/sources`             the registry with terms and licence, each source's state, the user's feeds,
                                        the branches and the groups
- `GET   /api/news/settings`, `PATCH`   {enabled, interval_hours, branches, sources{id: bool}, feeds, summaries,
                                        badge, keep_days, max_items}
- `POST  /api/news/refresh`             {source?} → the report; 409 `local_mode`
- `POST  /api/news/feeds`               {url, title?} → adds an RSS / Atom feed after one test read (skipped in
                                        Local mode: the feed is saved and read later); `DELETE /api/news/feeds/{id}`
- `PATCH /api/news/items/{id}`          {read?, saved?}
- `POST  /api/news/read-all`            the same filters as the list → {marked}
- `POST  /api/news/items/{id}/summary`  short French summary by a free online model (cached); 409 `local_mode`,
                                        422 `rights` / `short` / `suspect`, 503 `no_model` / `failed`
Event: `news.updated` {unread, new} after a refresh that brought something (a badge, never a toast).
The refresh itself: `NewsService.tick` every TICK seconds from this plugin's own task (first after FIRST seconds)."""
from __future__ import annotations

import asyncio

from aiohttp import web

from ...logs import get
from ...news import summarize as summ
from ...news.service import DEMO_FEED, FEED_MAX_BYTES, NewsError, NewsService
from ...news import parsers
from ...research.fetch import FetchError
from ..common import body, ctx_of, error, ok

log = get("news")
NEWS = web.AppKey("news", NewsService)
FIRST = 90.0
TICK = 600.0


def _svc(request: web.Request) -> NewsService:
    return request.app[NEWS]


def _flag(q: dict, name: str) -> bool:
    return q.get(name) is True or str(q.get(name, "")).lower() in ("1", "true", "yes")


def _query(request: web.Request) -> dict:
    return {**request.query, "branch": request.query.getall("branch", [])}


def _filters(svc: NewsService, q: dict) -> dict:
    """The list's filters, from a query string or from a JSON body (same names)."""
    s = svc.settings()
    f: dict = {"sources_on": svc.enabled_ids(s)}
    b = q.get("branch")
    bs = [x for x in (b if isinstance(b, list) else [b]) if isinstance(x, str) and x][:20]
    if bs:
        f["branches"] = bs
    if _flag(q, "mine") and s["branches"]:
        f["followed"] = s["branches"]
    for k in ("source", "group"):
        v = q.get(k)
        if isinstance(v, str) and v:
            f[k] = v[:60]
    if _flag(q, "open"):
        f["open_"] = True
    p = q.get("projects")
    if _flag(q, "projects"):
        f["projects"] = True
    elif isinstance(p, str) and p:
        f["projects"] = p[:80]
    if _flag(q, "unread"):
        f["unread"] = True
    if _flag(q, "saved"):
        f["saved"] = True
    return f


def _int(v, default: int) -> int:
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


async def news_list(request: web.Request) -> web.Response:
    svc = _svc(request)
    q = _query(request)
    await svc.rescore()
    f = _filters(svc, q)
    res = await asyncio.to_thread(lambda: svc.store.query(
        q=str(q.get("q", ""))[:200], limit=_int(q.get("limit"), 40), offset=_int(q.get("offset"), 0),
        order="relevance" if q.get("order") == "relevance" else "date", **f))
    res["unread"] = svc.unread()
    return ok(res)


async def news_overview(request: web.Request) -> web.Response:
    svc = _svc(request)
    await svc.rescore()
    return ok(await asyncio.to_thread(svc.overview))


async def news_sources(request: web.Request) -> web.Response:
    return ok(await asyncio.to_thread(_svc(request).sources_view))


async def settings_get(request: web.Request) -> web.Response:
    return ok({"settings": _svc(request).settings()})


async def settings_patch(request: web.Request) -> web.Response:
    svc = _svc(request)
    try:
        s = await asyncio.to_thread(svc.patch_settings, await body(request))
    except NewsError as e:
        return web.json_response({"error": e.kind, "field": str(e)}, status=e.status)
    ctx_of(request).publish("news.updated", {"unread": svc.unread(), "new": 0})
    return ok({"settings": s})


async def news_refresh(request: web.Request) -> web.Response:
    svc = _svc(request)
    data = await body(request)
    if svc.mode() == "local" and not ctx_of(request).demo:
        return error(409, "local_mode")
    only = data.get("source")
    res = await svc.refresh(force=True, only=only if isinstance(only, str) and only else None)
    return ok(res)


async def feed_add(request: web.Request) -> web.Response:
    svc = _svc(request)
    data = await body(request)
    try:
        url = svc.check_feed_url(str(data.get("url") or ""))
    except NewsError as e:
        return web.json_response({"error": e.kind, "detail": str(e)}, status=400)
    s = svc.settings()
    if any(f["url"] == url for f in s["feeds"]):
        return error(409, "duplicate")
    title = parsers.clean_text(str(data.get("title") or ""), 80, one_line=True)
    tested, count = False, 0
    ctx = ctx_of(request)
    if svc.mode() != "local" and not ctx.demo:
        try:                               # one read, to refuse an address that is not a feed
            r = await svc._get(url, hosts=None, max_bytes=FEED_MAX_BYTES)
            count = len(await asyncio.to_thread(parsers.parse_feed, r.body))
            tested = True
        except FetchError as e:
            return web.json_response({"error": "unreachable", "detail": e.kind, "http": e.status}, status=502)
        except parsers.ParseError:
            return error(422, "not_a_feed")
    try:
        s = await asyncio.to_thread(svc.patch_settings, {"feeds": [*s["feeds"], {"url": url, "title": title}]})
    except NewsError as e:
        return web.json_response({"error": e.kind, "field": str(e)}, status=e.status)
    if tested:
        ctx.spawn(svc.refresh(force=True, only=s["feeds"][-1]["id"]))
    return ok({"settings": s, "feed": s["feeds"][-1], "tested": tested, "entries": count}, status=201)


async def feed_delete(request: web.Request) -> web.Response:
    svc = _svc(request)
    fid = request.match_info["id"]
    s = svc.settings()
    if not any(f["id"] == fid for f in s["feeds"]):
        return error(404, "not_found")
    s = await asyncio.to_thread(svc.patch_settings, {"feeds": [f for f in s["feeds"] if f["id"] != fid]})
    return ok({"settings": s})


def _item_id(request: web.Request) -> int:
    try:
        return int(request.match_info["id"])
    except ValueError:
        raise web.HTTPNotFound(text='{"error": "not_found"}', content_type="application/json")


async def item_patch(request: web.Request) -> web.Response:
    svc = _svc(request)
    data = await body(request)
    flags = {k: data[k] for k in ("read", "saved") if isinstance(data.get(k), bool)}
    if not flags:
        return error(400, "bad_value")
    iid = _item_id(request)
    it = await asyncio.to_thread(lambda: svc.store.set_flags(iid, **flags))
    if it is None:
        return error(404, "not_found")
    return ok({"item": it, "unread": svc.unread()})


async def read_all(request: web.Request) -> web.Response:
    svc = _svc(request)
    f = _filters(svc, await body(request))
    f.pop("unread", None)
    n = await asyncio.to_thread(lambda: svc.store.mark_read(**f))
    return ok({"marked": n, "unread": svc.unread()})


async def item_summary(request: web.Request) -> web.Response:
    svc = _svc(request)
    if svc.mode() == "local":
        return error(409, "local_mode")
    try:
        it = await svc.summarize(_item_id(request))
    except NewsError as e:
        return error(e.status, e.kind)
    except summ.SummaryError as e:
        status = {"local_mode": 409, "short": 422, "suspect": 422, "rights": 422}.get(e.kind, 503)
        return web.json_response({"error": e.kind}, status=status)
    return ok({"item": it})


def register(app: web.Application, ctx) -> None:
    svc = NewsService(ctx, transport=getattr(ctx, "_news_transport", None))
    app[NEWS] = svc
    ctx.news = svc
    r = app.router
    r.add_get("/api/news", news_list)
    r.add_get("/api/news/overview", news_overview)
    r.add_get("/api/news/sources", news_sources)
    r.add_get("/api/news/settings", settings_get)
    r.add_patch("/api/news/settings", settings_patch)
    r.add_post("/api/news/refresh", news_refresh)
    r.add_post("/api/news/feeds", feed_add)
    r.add_delete("/api/news/feeds/{id}", feed_delete)
    r.add_patch("/api/news/items/{id}", item_patch)
    r.add_post("/api/news/items/{id}/summary", item_summary)
    r.add_post("/api/news/read-all", read_all)
    tasks: set[asyncio.Task] = set()

    async def loop() -> None:
        await asyncio.sleep(FIRST)
        while True:
            await svc.tick()
            await asyncio.sleep(TICK)

    async def startup(_app) -> None:
        if ctx.demo:
            try:
                # synchronous on purpose (≈ 50 ms, demo only): yielding here would let the other plugins' demo
                # seeds run in a different order (research_workshop seeds « the most recent project »)
                svc.seed_demo()
            except Exception:  # noqa: BLE001
                log.exception("demo seed (news) failed")
        else:
            tasks.add(asyncio.create_task(loop()))

    async def cleanup(_app) -> None:
        for t in tasks:
            t.cancel()
        await svc.close()
    app.on_startup.append(startup)
    app.on_cleanup.append(cleanup)


__all__ = ["register", "NEWS", "DEMO_FEED"]
