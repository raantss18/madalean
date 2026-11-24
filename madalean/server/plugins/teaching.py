"""Verified exercises API (DECISIONS D63, docs/API.md « Exercises », docs/TEACHING.md): the bank, the learner's flow
(answer in Lean or in words, hints after an attempt, verified solution) and the teacher's tools."""
from __future__ import annotations

import asyncio
import re
import time

from aiohttp import web

from ... import leancheck
from ...dossiers import slugify
from ...i18n import msg, ui_language
from ...teaching import exercises as X
from ..common import body, ctx_of, ok
from .conjecture_engine import device_of

BANK = web.AppKey("exercise_bank", object)
BUSY = web.AppKey("exercise_busy", set)


def _guard(fn):
    async def wrapped(request):
        try:
            return await fn(request)
        except X.ExerciseError as e:
            out: dict = {"error": e.kind, "where": e.where}
            if e.where and e.kind in ("bad_exercise", "bad_bank", "bad_statement"):
                out["message"] = msg("Exercice refusé : {where}.", where=e.where)
            return web.json_response(out, status=e.status)
    return wrapped


def _parts(request):
    bank: X.Bank = request.app[BANK]
    return ctx_of(request), bank, bank.get(request.match_info["eid"]), device_of(request)


async def _one_at_a_time(request, key: str, run):
    """One Lean / model check per learner and exercise at a time (a double click never starts two)."""
    busy: set = request.app[BUSY]
    if key in busy:
        raise X.ExerciseError("busy", 409)
    busy.add(key)
    try:
        return await run()
    finally:
        busy.discard(key)


@_guard
async def list_(request):
    bank = request.app[BANK]
    prog = bank.progress(device_of(request))
    return ok({"exercises": [X.public(e, prog.get(e["id"])) for e in bank.all()], "levels": X.LEVELS,
               "domains": X.DOMAINS})


@_guard
async def submit(request):
    """{kind: lean | words, text} → Lean's verdict (words: formalised first, then a review of the gaps)."""
    ctx, bank, e, dev = _parts(request)
    data = await body(request)
    text, owner = str(data.get("text") or ""), f"exercise-{e['id']}"
    words = data.get("kind") == "words"
    if not text.strip():
        raise X.ExerciseError("empty")

    async def run():
        if words:
            return await X.check_words(ctx, e, text, ui_language(), owner)
        r, _code = await X.check(ctx, e, text, owner)
        if r.infra_error:
            raise X.ExerciseError("no_workspace", 409)
        return {"ok": r.verdict.ok, "check": r.to_dict(), "lean": "", "review": ""}
    res = await _one_at_a_time(request, f"{dev}:{e['id']}", run)
    seen = (bank.progress(dev).get(e["id"]) or {}).get("seen")
    how = ("after_solution" if seen else "words" if words else "lean") if res["ok"] else ""
    return ok({**res, "progress": bank.mark(dev, e["id"], attempt=1, tried=True, solved=how)})


@_guard
async def hint(request):
    """{tried?, again?} → the next hint. The first one asks for an attempt (a submission, or a few words)."""
    _ctx, bank, e, dev = _parts(request)
    data = await body(request)
    p = bank.progress(dev).get(e["id"]) or {}
    if not p.get("tried"):
        if len(str(data.get("tried") or "").strip()) < 3:
            raise X.ExerciseError("attempt_first", 409)
        p = bank.mark(dev, e["id"], tried=True)
    n = p.get("hints", 0)
    if not data.get("again"):
        if n >= len(e["hints"]):
            raise X.ExerciseError("no_more_hints", 409)
        n += 1
        p = bank.mark(dev, e["id"], hints=n)
    return ok({"hints": e["hints"][:n], "progress": p})


@_guard
async def solution(request):
    """The last step of the ladder: after every hint (or once solved)."""
    ctx, bank, e, dev = _parts(request)
    p = bank.progress(dev).get(e["id"]) or {}
    if not p.get("solved") and (not p.get("tried") or p.get("hints", 0) < len(e["hints"])):
        raise X.ExerciseError("hints_first", 409)
    res = await _one_at_a_time(request, f"solution:{e['id']}", lambda: X.solution(ctx, bank, e, f"exercise-{e['id']}"))
    if not p.get("solved"):
        p = bank.mark(dev, e["id"], seen=True)
    return ok({**res, "progress": p})


async def _checked(ctx, e: dict) -> dict:
    """The exercise, once Lean read its statement; its solution is kept only if Lean accepts it."""
    ws = ctx.workspace(None)
    if ws is None:
        raise X.ExerciseError("no_workspace", 409)
    r = await ctx.lean.check(leancheck.GOEDEL_HEADER + e["lean"] + "\n", ws,
                             int(ctx.settings.compile_timeout_s or 180), owner="exercise-new")
    if r.infra_error:
        raise X.ExerciseError("no_workspace", 409)
    if not r.to_dict()["statement_ok"]:
        raise X.ExerciseError("bad_statement", 422)
    if e["solution"]:
        r, _c = await X.check(ctx, e, e["solution"], "exercise-new")
        if not r.verdict.ok:
            e = {**e, "solution": ""}
    return e


def _lean_of(code: str, name: str) -> tuple[str, str]:
    """(statement ending in sorry, tactic block) of the theorem `name` in a dossier's or the library's code."""
    code = leancheck.remove_comments(code)
    m = re.search(r"(?m)^\s*(?:theorem|lemma)\s+" + re.escape(name) + r"(?=[\s:({\[⦃])([\s\S]*?):=\s*by\b", code)
    if m is None:
        raise X.ExerciseError("bad_statement", 422)
    lean = f"theorem {name}{m.group(1).rstrip()} := by sorry"
    X.check_signature(lean)
    try:
        return lean, X.clean_answer(code[m.end():])
    except X.ExerciseError:
        return lean, ""


@_guard
async def create(request):
    """« En faire un exercice »: {dossier | library, level, domain, statement: {fr, mg?, en?}, title?, hints?}."""
    ctx, bank = ctx_of(request), request.app[BANK]
    data = await body(request)
    if data.get("library"):
        ent = next((x for x in ctx.library.entries if x.name == data["library"]), None)
        if ent is None:
            raise X.ExerciseError("not_found", 404)
        code, name, title = ent.code, ent.name, ent.title
    else:
        d = ctx.repo.get(str(data.get("dossier") or ""))
        if d is None:
            raise X.ExerciseError("not_found", 404)
        code, title = (d.proof if d.proof_is_current else d.statement), d.title
        if not code:
            raise X.ExerciseError("no_statement", 409)
        name = leancheck.theorem_name(d.statement)
    lean, sol = _lean_of(code, name)
    t = data.get("title") or re.sub(r"\s+", " ", title).strip()[:200]
    slug = re.sub(r"[^a-z0-9]+", "-", slugify(title).lower()).strip("-")[:40] or "exercice"
    e = X.validate({"id": f"{slug}-{int(time.time()) % 100000}", "level": data.get("level"), "domain": data.get("domain"),
                    "title": t if isinstance(t, dict) else {"fr": t}, "statement": data.get("statement"), "lean": lean,
                    "hints": data.get("hints") or [], "solution": sol})
    e = await _one_at_a_time(request, "create", lambda: _checked(ctx, e))
    eid = bank.add([e], "own")[0]
    return ok({"exercise": X.public(bank.get(eid), None)}, 201)


@_guard
async def import_(request):
    """{text: the bank file}: refused as a whole if one exercise is not valid. Lean reads each statement and each
    solution when it is used (nothing is shown as verified before)."""
    data = await body(request)
    ex = await asyncio.to_thread(X.parse_bank, data.get("text"))
    return ok({"ids": request.app[BANK].add(ex, "import")}, 201)


@_guard
async def export(request):
    return web.Response(text=X.bank_json(list(request.app[BANK].own.values())), content_type="application/json",
                        headers={"Content-Disposition": 'attachment; filename="madalean-exercices.json"'})


@_guard
async def delete(request):
    _ctx, bank, e, _dev = _parts(request)
    bank.remove(e["id"])
    return ok({})


@_guard
async def worksheet(request):
    """?ids=a,b&title&lang&solutions=1&lean=1&format=pdf|tex|md → the file (a GET like the other exports: the Android
    shell downloads it again with its token). A solution Lean does not accept here is left out
    (X-Madalean-Left-Out: how many)."""
    from ...research.notes import export_markdown
    ctx, bank = ctx_of(request), request.app[BANK]
    data = request.query
    ids, fmt = [i for i in data.get("ids", "").split(",") if i], data.get("format", "pdf")
    lang = data.get("lang") if data.get("lang") in X.LANGS else "fr"
    if fmt not in ("tex", "pdf", "md") or not 0 < len(ids) <= 60:
        raise X.ExerciseError("bad_fields")
    items = [dict(bank.get(i)) for i in ids]
    title = X._text(data.get("title") or {"fr": "Feuille d'exercices", "mg": "Fanazaran-tena", "en": "Worksheet"}[lang],
                    "title", 200)
    left = 0
    if data.get("solutions"):
        for e in items:
            if e["solution"]:
                try:
                    await X.solution(ctx, bank, e, "worksheet")
                except X.ExerciseError:
                    e["solution"], left = "", left + 1
    md = X.worksheet_markdown(items, title, lang, bool(data.get("solutions")), bool(data.get("lean")))
    ex = await export_markdown(md, title, fmt, lang, ctx.paths.exports)
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", ex.filename)[:120]
    return web.Response(body=ex.data, content_type=ex.content_type.split(";")[0],
                        headers={"Content-Disposition": f'attachment; filename="{safe}"',
                                 "X-Madalean-Fallback": ex.fallback or "", "X-Madalean-Left-Out": str(left)})


def register(app: web.Application, ctx) -> None:
    app[BANK] = X.Bank(ctx.paths.config / "teaching")
    app[BUSY] = set()
    a = app.router
    a.add_get("/api/exercises", list_)
    a.add_post("/api/exercises", create)
    a.add_post("/api/exercises/import", import_)
    a.add_get("/api/exercises/export", export)
    a.add_get("/api/exercises/worksheet", worksheet)
    a.add_post("/api/exercises/{eid}/submit", submit)
    a.add_post("/api/exercises/{eid}/hint", hint)
    a.add_post("/api/exercises/{eid}/solution", solution)
    a.add_delete("/api/exercises/{eid}", delete)
