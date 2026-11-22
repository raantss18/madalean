"""« Expliquer » for Lean (session S-AM, DECISIONS D45): `POST /api/lean/explain`, also reached through the generic
`POST /api/code/explain` with `language: lean` (workbench.py).

Body: {mode: error | lines, code?, dossier?, part?: statement | proof, note?, block?, workspace?, errors?, error?,
stream?}. The place gives the workspace (the dossier's, the note's project's, or `workspace` / the default) and the
rules of the correction: a proof is pinned to the dossier's statement and judged strictly; a statement must compile
(`sorry` allowed); a note's block is compiled with the header it is checked with. `code` defaults to the dossier's
statement / proof or the note's block. Lean's messages: `errors` ([{line, col, text, severity}], as shown on screen),
or `error` (text), else the server compiles the code itself (warm Lean allowed).

Answer, mode error: {explanation, fix, fix_status: accepted | rejected | none | unchecked, fix_check, fix_tries,
no_error?, workspace, lean, model, cached}. `fix` is non-empty ONLY when Lean accepted it (status accepted); applying it
is a manual edit (new version, fresh strict check). Mode lines: {lines: [{line, code, text, goal}], goals: lean | none,
…}: `goal` = the goal state Lean printed after that line (null when Lean gave none).
Streaming: `lean.explain` events {stream, text, state: start | writing | checking | repairing | done | error} when the
body carries `stream` (a client-chosen id). Answers are cached in memory (same code, place, Lean version, language)."""
from __future__ import annotations

import asyncio
import hashlib
import json
import re
import time

from aiohttp import web

from ... import leancheck
from ...i18n import language as language_ui
from ...logs import get
from ...research import leanexplain as LX
from ...research.explain import ExplainError
from ..common import body, ctx_of, error, ok, valid_id

log = get("lean.explain")
CACHE = web.AppKey("lean_explain_cache", dict)
CACHE_MAX = 200
CHECK_TIMEOUT = 120
_STREAM = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


class _Place:
    def __init__(self, c: LX.Ctx, code: str, key: str):
        self.c, self.code, self.key = c, code, key


def _place(request, ctx, data: dict) -> _Place | web.Response:
    part = str(data.get("part") or "")
    code = str(data.get("code") or "")
    c = LX.Ctx(part=part)
    key = "free"
    if data.get("dossier"):
        d = ctx.repo.get(valid_id(str(data["dossier"])))
        if d is None:
            return error(404, "not_found")
        if part not in ("statement", "proof"):
            return error(400, "bad_fields", "Champs refusés : {fields}.", fields="part")
        if not code:
            code = d.statement if part == "statement" else d.proof
        c.statement = d.statement
        c.ws = ctx.workspace(d.workspace or ctx.settings.workspace)
        key = f"dossier:{d.id}:{part}"
    elif data.get("note"):
        from .research_workshop import R, _project_ws
        from ...research.notes import lean_blocks
        n = R(request).notes.get(valid_id(str(data["note"])), False)
        if n is None:
            return error(404, "not_found")
        c.part = "block"
        c.ws = _project_ws(ctx, n.project_id)
        if not code:
            try:
                idx = int(data.get("block", -1))
            except (TypeError, ValueError):
                idx = -1
            b = next((b for b in lean_blocks(n.body) if b.index == idx), None)
            if b is None:
                return error(409, "no_lean_block", "Cette note ne contient aucun bloc ```lean.")
            code = b.code
        key = f"note:{n.id}"
    else:
        if part not in ("", "statement", "proof"):
            return error(400, "bad_fields", "Champs refusés : {fields}.", fields="part")
        c.ws = ctx.workspace(str(data.get("workspace") or "") or None)
        if part == "proof":
            c.statement = code
    if c.part in ("block", "") and c.ws is not None and not re.search(r"(?m)^\s*import\s", code):
        try:
            if c.ws.has_mathlib():          # the header a note's block is checked with (research_workshop)
                c.header = leancheck.GOEDEL_HEADER
                c.header_offset = c.header.count("\n")
        except Exception:  # noqa: BLE001
            pass
    c.info = LX.version_info(c.ws)
    return _Place(c, code, key)


def _checker(ctx, c: LX.Ctx, owner: str):
    if c.ws is None:
        return None

    async def check(unit: str, strict: str | None):
        return await ctx.lean.check(unit, c.ws, min(CHECK_TIMEOUT, int(ctx.settings.compile_timeout_s or CHECK_TIMEOUT)),
                                    strict, owner=owner, warm=True)
    return check


def _client_errors(data: dict) -> list[dict]:
    out = []
    for e in (data.get("errors") or [])[:40]:
        if isinstance(e, dict) and str(e.get("text") or "").strip():
            out.append({"line": e.get("line") or 1, "col": e.get("col") or 0, "text": str(e["text"])[:2000],
                        "severity": str(e.get("severity") or "error")})
    return out


async def handle(request, data: dict) -> web.Response:
    ctx = ctx_of(request)
    mode = str(data.get("mode") or "error")
    p = _place(request, ctx, data)
    if isinstance(p, web.Response):
        return p
    c, code = p.c, p.code
    try:
        LX.check_args(mode, code, c.part)
    except ExplainError as e:
        return error(400, "bad_fields", "Champs refusés : {fields}.", fields=str(e))
    lang = language_ui()
    lang = lang if lang in LX.SYSTEM else "en"
    stream = str(data.get("stream") or "")
    stream = stream if _STREAM.match(stream) else ""
    owner = f"explain-{p.key.replace(':', '-')}"[:80]
    errors = _client_errors(data)
    raw_error = str(data.get("error") or "")[-4000:]
    info = c.info or {}
    ck = hashlib.sha256(json.dumps([mode, code, c.part, c.statement if c.part == "proof" else "", c.header,
                                    getattr(c.ws, "key", ""), info.get("lean", ""), info.get("mathlib", ""), lang,
                                    errors, raw_error], ensure_ascii=False).encode()).hexdigest()
    cache: dict = request.app[CACHE]
    base = {"workspace": getattr(c.ws, "key", ""), "lean": info.get("lean", "")}
    last = [0.0]

    def publish(text: str, state: str) -> None:
        if stream:
            ctx.publish("lean.explain", {"stream": stream, "text": text[:20000], "state": state})

    hit = cache.get(ck)
    if hit is not None:
        cache[ck] = cache.pop(ck)                  # LRU
        publish("", "done")
        return ok({**hit, "cached": True})

    def on_text(text: str) -> None:
        now = time.monotonic()
        if now - last[0] > 0.12:
            last[0] = now
            publish(text, "writing")
    check = _checker(ctx, c, owner)
    publish("", "start")
    try:
        if mode == "error":
            out = await _error_mode(ctx, c, code, errors, raw_error, lang, owner, check, on_text, publish)
        else:
            out = await _lines_mode(ctx, c, code, lang, owner, check)
    except ExplainError as e:
        publish("", "error")
        return error(400, "bad_fields", "Champs refusés : {fields}.", fields=str(e))
    except asyncio.CancelledError:
        raise
    except Exception as e:  # noqa: BLE001
        log.exception("lean explain")
        publish("", "error")
        return error(503, "no_model", "Aucun modèle disponible ({err}).", err=str(e)[:200])
    out = {**base, **out}
    publish(out.get("explanation", ""), "done")
    if out.get("fix_status") in ("accepted", "none", None):     # a refused / unchecked fix: asking again may help
        cache[ck] = out
        while len(cache) > CACHE_MAX:
            cache.pop(next(iter(cache)))
    return ok({**out, "cached": False})


async def _error_mode(ctx, c: LX.Ctx, code: str, errors: list[dict], raw_error: str, lang: str, owner: str, check,
                      on_text, publish) -> dict:
    if not errors and not raw_error.strip():
        if check is None:
            raise ExplainError("no_error")
        publish("", "checking")
        try:
            unit, name = LX.compile_unit(c, code)
        except leancheck.StatementError as e:
            raw_error = str(e)
        else:
            r = await check(unit, name)
            if LX.accepted(c, r, code, code) and not r.verdict.errors:
                return {"no_error": True, "explanation": "", "fix": "", "fix_status": "none", "fix_check": None,
                        "fix_tries": 0, "model": ""}
            if c.part in ("block", ""):           # positions in the block (the header is not shown)
                errors = [{**_msg(m), "line": max(1, m.line - c.header_offset)} for m in r.verdict.errors]
            else:                                 # the file Lean compiled: the pinned proof / the prepared statement
                code = unit.rsplit("\n\n#print axioms", 1)[0].rstrip() + "\n" if name else unit
                errors = [_msg(m) for m in r.verdict.errors]
            if not errors:
                raw_error = r.verdict.summary + ("\n" + "; ".join(r.verdict.reasons) if r.verdict.reasons else "")
    return await LX.explain_error(ctx, c, code=code, errors=errors, raw_error=raw_error, lang=lang, owner=owner,
                                  on_text=on_text, on_state=lambda s: publish("", s), check=check)


def _msg(m) -> dict:
    return {"line": m.line, "col": m.col, "end_line": m.end_line, "end_col": m.end_col, "text": m.text,
            "severity": m.severity}


async def _lines_mode(ctx, c: LX.Ctx, code: str, lang: str, owner: str, check) -> dict:
    task = None
    if check is not None and not getattr(ctx, "demo", False):
        ins = LX.instrument(code) or LX.statement_probe(code)
        if ins is not None:
            icode, mapping = ins

            async def goals():
                r = await ctx.lean.check(c.header + icode, c.ws, CHECK_TIMEOUT, None, owner=owner, warm=True)
                if r.timed_out or r.infra_error:
                    return None
                return LX.goals_from(r.stdout, mapping, c.header_offset)
            task = asyncio.ensure_future(goals())
    try:
        return await LX.explain_lines(ctx, c, code=code, lang=lang, owner=owner, goals_task=task)
    finally:
        if task is not None and not task.done():
            task.cancel()


async def lean_explain(request):
    return await handle(request, await body(request))


# ---------------------------------------------------------------- demo answers (`serve --demo`, e2e)
def demo_answer(first: str) -> str | None:
    """Scripted answers for the Lean explanations in the demo: the error names the unknown lemma and the correction
    replaces it (the demo's Lean accepts it); the lines are glossed generically."""
    if first.startswith(("Lean refuse ", "Lean refuses ")):
        m = re.search(r"```lean\n(.*?)\n```", first, re.S)
        code = m.group(1) if m else ""
        fixed = re.sub(r"\bno_such_lemma\b", "Nat.le_refl", code)
        if first.startswith("Lean refuse "):
            return ("Lean ne connaît pas le nom `no_such_lemma` : ce résultat n'existe pas dans Mathlib. Il faut citer "
                    "un résultat qui existe, ici `Nat.le_refl` (tout entier est inférieur ou égal à lui-même).\n\n"
                    f"```lean\n{fixed}\n```")
        return ("Lean does not know the name `no_such_lemma`: this result does not exist in Mathlib. Cite an existing "
                f"one, here `Nat.le_refl` (every natural number is at most itself).\n\n```lean\n{fixed}\n```")
    if first.startswith(("Explique ce code Lean", "Explain this Lean code")):
        nums = re.findall(r"^(\d+): (.*)$", first, re.M)
        fr = first.startswith("Explique")
        return "\n".join(f"{n}: " + (f"Cette ligne dit à Lean « {c.strip()[:50]} »." if fr else
                                       f"This line tells Lean « {c.strip()[:50]} ».") for n, c in nums if c.strip())
    return None


def _demo_brain(ctx) -> None:
    br = ctx.brain
    if not hasattr(br, "responder"):
        return
    base = br.responder

    def responder(role, messages, brain):
        first = next((m.get("content", "") for m in messages if m.get("role") == "user"), "")
        last = next((m.get("content", "") for m in reversed(messages) if m.get("role") == "user"), "")
        ans = demo_answer(first) if last == first else None
        return ans if ans is not None else base(role, messages, brain)
    br.responder = responder


def register(app: web.Application, ctx) -> None:
    app[CACHE] = {}
    app.router.add_post("/api/lean/explain", lean_explain)
    if getattr(ctx, "demo", False):
        async def startup(_app):
            _demo_brain(ctx)
        app.on_startup.append(startup)
