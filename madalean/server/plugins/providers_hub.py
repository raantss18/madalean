"""Plugin of session S-U: the providers hub (Réglages → Fournisseurs) and Internet search.

Routes (JSON; docs/PROVIDERS.md):
- `GET  /api/providers`        cards grouped by use (what it is good for, free tier « vérifié le … », privacy, key
                               link), with live state: key set, turned off, models usable now, search usage this month
- `POST /api/search/web`       {query, k?, lang?, providers?} → {query, provider, results[{n,title,url,snippet,source}],
                               tried[]} ; 409 `local_mode` / `disabled`, 503 `no_provider`
- `POST /api/search/test`      {provider} → {ok, reason, results, latency_s} (one tiny real search; key never echoed)
Keys are stored with the existing `POST /api/models/keys` (any provider id, keyring); a provider is turned off with
`PATCH /api/settings {"providers_disabled": [...]}`, Internet search with `{"web_search": false}`.

`ctx.websearch` (brain.websearch.WebSearch) is the interface for the research orchestrator (S-Q):
`await ctx.websearch.search(query, k, mode=job_mode)` and `brain.websearch.tool_spec(ctx.websearch, mode=…)` for an
agent's `web_search` tool."""
from __future__ import annotations

import asyncio

from aiohttp import web

from ...brain import hub
from ...brain.websearch import KEYED_IDS, SearchError, WebSearch
from ...logs import get
from ..common import body, ctx_of, error, ok

log = get("providers_hub")
WEBSEARCH = web.AppKey("websearch", WebSearch)


def _settings(ctx) -> dict:
    s = ctx.settings
    return {"mode": getattr(s, "mode", "auto"), "web_search": bool(getattr(s, "web_search", True)),
            "providers_disabled": list(getattr(s, "providers_disabled", []) or [])}


async def providers_get(request: web.Request) -> web.Response:
    ctx = ctx_of(request)
    ws: WebSearch = request.app[WEBSEARCH]
    keys = set(await asyncio.to_thread(ctx.keys.providers))
    st = _settings(ctx)
    off = set(st["providers_disabled"])
    live: dict[str, dict] = {}
    fn = getattr(ctx.brain, "status", None)
    if fn is not None:
        try:
            bst = await asyncio.wait_for(fn(), 6)
            live = {p["id"]: p for p in bst.get("providers") or [] if isinstance(p, dict) and p.get("id")}
        except Exception:  # noqa: BLE001 (the hub still shows the cards)
            live = {}
    usage = {u["id"]: u for u in ws.status()}
    cards = []
    for c in hub.cards():
        k = c["key"]
        c["key_set"] = (k in keys) if k else None
        c["disabled"] = (k or c["id"]) in off
        p = live.get(k or "")
        if p is not None and c["kind"] == "llm":
            c["state"] = {"models": int(p.get("models") or 0), "ok": bool(p.get("ok")),
                          "paused_until": p.get("paused_until"), "reason": str(p.get("reason") or "")}
        if c["id"] in usage:
            u = usage[c["id"]]
            c["usage"] = {"units": u["units"], "searches": u["searches"], "unit": u["unit"], "free_month": u["free_month"]}
        cards.append(c)
    return ok({"checked": hub.CHECKED, "groups": [{"id": g, "fr": fr, "en": en} for g, fr, en in hub.GROUPS],
               "starter": hub.STARTER, "cards": cards, "ocr": hub.OCR_NOTE, "web_search": st["web_search"],
               "mode": st["mode"]})


async def search_web(request: web.Request) -> web.Response:
    ctx = ctx_of(request)
    ws: WebSearch = request.app[WEBSEARCH]
    data = await body(request)
    q = data.get("query")
    if not isinstance(q, str) or not q.strip() or len(q) > 2000:
        return error(400, "bad_query")
    provs = data.get("providers")
    provs = [str(p) for p in provs][:4] if isinstance(provs, list) else None
    lang = data.get("lang") if data.get("lang") in ("fr", "en") else "en"
    try:
        k = int(data.get("k") or 6)
    except (TypeError, ValueError):
        k = 6
    try:
        res = await ws.search(q, k, mode=str(data.get("mode") or "auto"), providers=provs, lang=lang)
    except SearchError as e:
        status = 409 if e.kind in ("local_mode", "disabled") else (400 if e.kind == "http" else 503)
        return web.json_response({"error": e.kind, "message": e.message}, status=status)
    return ok(res)


async def search_test(request: web.Request) -> web.Response:
    ws: WebSearch = request.app[WEBSEARCH]
    data = await body(request)
    provider = str(data.get("provider", ""))[:41]
    if provider not in KEYED_IDS and provider != "wikipedia":
        return error(400, "bad_provider")
    try:
        res = await asyncio.wait_for(ws.test(provider), 40)
    except asyncio.TimeoutError:
        res = {"ok": False, "reason": "timeout"}
    return ok({"provider": provider, **res})


def register(app: web.Application, ctx) -> None:
    r = app.router
    r.add_get("/api/providers", providers_get)
    r.add_post("/api/search/web", search_web)
    r.add_post("/api/search/test", search_test)
    ws = WebSearch(ctx.keys.get, lambda: _settings(ctx), config_dir=ctx.paths.config,
                   endpoints=getattr(ctx, "_search_endpoints", None))
    app[WEBSEARCH] = ws
    ctx.websearch = ws

    async def close(_app) -> None:
        await ws.close()
    app.on_cleanup.append(close)
