"""« Consigne de recherche » + « Suggestions » + one search across a project (session S-Q). Module:
`madalean/research/agent_research.py`. Prefix `/api/research/projects/{pid}`:

- `POST   /consignes {source: {shelf?, id}, instruction, limits?: {max_steps, max_minutes, max_cost_usd, max_targets,
          max_suggestions}, mode?, dry_run?}`  → dry_run: 200 {run} (the plan, nothing saved / run); else 202 {run}
- `GET    /consignes` → {runs} · `GET /consignes/{rid}` → {run}
- `POST   /consignes/{rid}/cancel` · `POST /consignes/{rid}/resume`
- `GET    /suggestions?type=&status=` → {suggestions, counts}
- `POST   /suggestions/{sid}/accept {after?}` (the user may edit the proposed text) · `POST /suggestions/{sid}/reject`
- `GET    /search?q=` → {results: [{kind: dossier|note|calcul|figure|passage|suggestion, id, title, snippet, …}]}
- `POST   /to-article {kind, id, …}` → {block} (explicit user action) · `GET|POST /basket {kind, id, remove?}` (what
          « Publier » preselects: dossiers, notes, calcul cells)
Events: `research.run {project_id, run}`, `research.suggestion {project_id, suggestion}`, plus the usual
`article.updated`, `note.updated`, `calcul.updated`, `job.*`."""
from __future__ import annotations

import asyncio

from aiohttp import web

from ...i18n import msg
from ...logs import get
from ...research.agent_research import TYPES, Agent, ResearchError
from ..common import CTX, body, error, ok, valid_id

log = get("research.agent")
AGENT = web.AppKey("research_agent", object)

MESSAGES = {
    "empty_instruction": "Écrivez une consigne (par exemple : « vérifie le théorème 2 avec Lean »).",
    "nothing_understood": "Consigne non comprise : demandez une vérification Lean, des exemples, des figures, une "
                          "amélioration de la rédaction ou une généralisation.",
    "busy": "Une consigne est déjà en cours dans ce projet : arrêtez-la ou attendez la fin.",
    "stale": "Le texte visé a changé depuis la suggestion : elle n'a pas été appliquée.",
    "already_decided": "Cette suggestion a déjà été traitée.",
    "not_found": "Introuvable.",
    "finished": "Cette consigne est terminée : lancez-en une nouvelle.",
    "already_there": "Déjà dans l'article.",
    "bad_fields": "Champs refusés : {fields}.",
}


class CalcAdapter:
    """The one integration point with « Calcul » (sessions S-M / S-P): cells are added as origin « assistant » and run
    only when the same rule as the Calcul screen allows it (approved code, or `experiments_auto` on the host)."""

    def __init__(self, app: web.Application, ctx):
        self.app, self.ctx = app, ctx

    def _wb(self):
        from .workbench import WB
        try:
            return self.app[WB]
        except KeyError:
            return None

    async def add_cell(self, pid: str, code: str, language: str, *, note: str = "", model: str = "") -> dict:
        wb = self._wb()
        if wb is None:
            raise ResearchError("calcul_unavailable")
        c = await asyncio.to_thread(wb.calc.add, pid, code, language, "assistant", note=note, model=model)
        self.ctx.publish("calcul.updated", {"project_id": pid, "cell": c})
        return c

    async def run_allowed(self, pid: str, cid: str, allow: bool = True) -> dict | None:
        wb = self._wb()
        if wb is None or not allow:
            return None
        # S-P: the notebook's own kernel (one per document, shared with JupyterLab), same approval rule
        return await wb.run_cell(pid, cid, "consigne")

    def cells(self, pid: str) -> list[dict]:
        wb = self._wb()
        return list(wb.calc.load(pid).get("cells", [])) if wb is not None else []

    def cell(self, pid: str, cid: str) -> dict | None:
        return next((c for c in self.cells(pid) if c["id"] == cid), None)

    @staticmethod
    def output_text(run: dict) -> str:
        from ...research.calcul import output_text
        return output_text(run)


def A(request) -> Agent:
    return request.app[AGENT]


def _fail(e: ResearchError) -> web.Response:
    out = {"error": e.kind, **{k: v for k, v in e.info.items() if isinstance(v, (str, int))}}
    if e.kind in MESSAGES:
        out["message"] = msg(MESSAGES[e.kind], **({"fields": e.info.get("fields", "")} if "{fields}" in
                                                  MESSAGES[e.kind] else {}))
    return web.json_response(out, status=e.status)


def _guard(handler):
    async def wrapped(request):
        from ...research.sources import SourceError
        try:
            return await handler(request)
        except ResearchError as e:
            return _fail(e)
        except SourceError as e:
            return web.json_response({"error": e.kind}, status=getattr(e, "status", 400))
    wrapped.__name__ = handler.__name__
    return wrapped


def _pid(request) -> str:
    pid = valid_id(request.match_info["pid"])
    if request.app[CTX].projects.get(pid) is None:
        raise web.HTTPNotFound(text='{"error":"not_found"}', content_type="application/json")
    return pid


# ================================================================ consignes
@_guard
async def consigne_start(request):
    from ...research.fetch import effective_mode
    ctx, ag = request.app[CTX], A(request)
    pid = _pid(request)
    data = await body(request)
    src = data.get("source") if isinstance(data.get("source"), dict) else {}
    mode = effective_mode(ctx, ctx.projects.get(pid))
    if data.get("mode") in ("local", "auto", "online") and mode != "local":
        mode = data["mode"]
    run = await asyncio.to_thread(ag.prepare, pid, src, str(data.get("instruction", "")), data.get("limits"), mode)
    # code runs on the host: from a paired device only when the host allows it (same rule as Calcul)
    run["allow_exec"] = bool(request["local"] or getattr(ctx.settings, "experiments_remote", False))
    if data.get("dry_run"):
        return ok({"run": run})
    ag.start(run)
    return ok({"run": ag.public_run(run)}, status=202)


@_guard
async def consigne_list(request):
    pid = _pid(request)
    return ok({"runs": await asyncio.to_thread(A(request).runs, pid)})


@_guard
async def consigne_get(request):
    pid = _pid(request)
    run = await asyncio.to_thread(A(request).store.run, pid, request.match_info["rid"])
    if run is None:
        raise ResearchError("not_found", 404)
    return ok({"run": A(request).public_run(run)})


@_guard
async def consigne_cancel(request):
    pid = _pid(request)
    return ok({"run": await A(request).cancel(pid, request.match_info["rid"])})


@_guard
async def consigne_resume(request):
    pid = _pid(request)
    data = await body(request)
    run = A(request).resume(pid, request.match_info["rid"], data.get("limits") if isinstance(data, dict) else None)
    return ok({"run": A(request).public_run(run)}, status=202)


# ================================================================ suggestions
@_guard
async def suggestions_list(request):
    pid = _pid(request)
    t = request.query.get("type", "")
    st = request.query.get("status", "")
    if t and t not in TYPES:
        raise ResearchError("bad_fields", fields="type")
    lst = await asyncio.to_thread(A(request).suggestions, pid, t, st)
    allx = await asyncio.to_thread(A(request).store.suggestions, pid)
    counts: dict[str, int] = {}
    for s in allx:
        if s["status"] == "proposed":
            counts[s["type"]] = counts.get(s["type"], 0) + 1
    return ok({"suggestions": lst, "counts": counts})


@_guard
async def suggestion_accept(request):
    from .research_sources import ART_LOCKS
    ctx, ag = request.app[CTX], A(request)
    pid = _pid(request)
    data = await body(request)
    edited = data.get("after") if isinstance(data.get("after"), str) else None
    lock = request.app[ART_LOCKS].setdefault(pid, asyncio.Lock()) if ART_LOCKS in request.app else ag.art_lock(pid)
    async with lock:
        try:
            s, art = await asyncio.to_thread(ag.accept, pid, request.match_info["sid"], edited)
        except ResearchError as e:
            if e.kind == "stale":
                cur = next((x for x in ag.store.suggestions(pid) if x["id"] == request.match_info["sid"]), None)
                if cur:
                    ag.publish_suggestion(cur)
            raise
    ctx.publish("article.updated", {"project": pid, "article": art})
    ag.publish_suggestion(s)
    return ok({"suggestion": ag.resolve(s)})


@_guard
async def suggestion_reject(request):
    pid = _pid(request)
    s = await asyncio.to_thread(A(request).reject, pid, request.match_info["sid"])
    A(request).publish_suggestion(s)
    return ok({"suggestion": s})


# ================================================================ search, to article, basket
@_guard
async def project_search(request):
    pid = _pid(request)
    return ok({"results": await A(request).search(pid, request.query.get("q", ""))})


@_guard
async def to_article(request):
    from .research_sources import ART_LOCKS
    ctx, ag = request.app[CTX], A(request)
    pid = _pid(request)
    data = await body(request)
    kind, item = str(data.get("kind", "")), str(data.get("id", ""))
    lock = request.app[ART_LOCKS].setdefault(pid, asyncio.Lock()) if ART_LOCKS in request.app else ag.art_lock(pid)
    async with lock:
        res = await asyncio.to_thread(ag.to_article, pid, kind, item, data)
    ctx.publish("article.updated", {"project": pid, "article": res["article"]})
    return ok({"block": res["block"]}, status=201)


@_guard
async def basket_get(request):
    pid = _pid(request)
    return ok({"basket": await asyncio.to_thread(A(request).store.basket, pid)})


@_guard
async def basket_post(request):
    pid = _pid(request)
    data = await body(request)
    kind = {"dossier": "dossiers", "note": "notes", "calcul": "calcul", "figure": "calcul"}.get(str(data.get("kind")))
    item = str(data.get("id", ""))
    if kind is None or not item:
        raise ResearchError("bad_fields", fields="kind, id")
    valid_id(item)
    b = await asyncio.to_thread(A(request).store.basket_add, pid, kind, item, bool(data.get("remove")))
    request.app[CTX].publish("publish.basket", {"project": pid, "basket": b})
    return ok({"basket": b})


def register(app: web.Application, ctx) -> None:
    agent = Agent(ctx, calc=CalcAdapter(app, ctx))
    app[AGENT] = agent
    ctx.research_agent = agent
    r = app.router
    base = "/api/research/projects/{pid}"
    r.add_post(base + "/consignes", consigne_start)
    r.add_get(base + "/consignes", consigne_list)
    r.add_get(base + "/consignes/{rid}", consigne_get)
    r.add_post(base + "/consignes/{rid}/cancel", consigne_cancel)
    r.add_post(base + "/consignes/{rid}/resume", consigne_resume)
    r.add_get(base + "/suggestions", suggestions_list)
    r.add_post(base + "/suggestions/{sid}/accept", suggestion_accept)
    r.add_post(base + "/suggestions/{sid}/reject", suggestion_reject)
    r.add_get(base + "/search", project_search)
    r.add_post(base + "/to-article", to_article)
    r.add_get(base + "/basket", basket_get)
    r.add_post(base + "/basket", basket_post)

    async def cleanup(_app):
        await agent.shutdown()
    app.on_cleanup.append(cleanup)
