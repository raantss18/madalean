"""Session S-M/S-P plugin: the « Calcul » notebooks, the organised library of proven results, and the glossary's
links to the user's dossiers. Reference: docs/API.md §« Calcul, library catalogue, glossary », docs/CALCUL.md.

Calcul (S-P: notebooks — a document is a standard .ipynb sharing one kernel with JupyterLab, docs/CALCUL.md)
- `GET    /api/calcul/{pid}/docs`                         the project's documents (creates « calcul » on first use)
- `POST   /api/calcul/{pid}/docs {title, language}` · `PATCH …/docs/{doc} {title}` · `DELETE …/docs/{doc}`
- `GET    /api/calcul/{pid}/docs/{doc}`                   {doc, cells, trash, status} — never starts a kernel
- `GET    /api/calcul/{pid}/docs/{doc}/ipynb`             the notebook file (download)
- `POST   …/docs/{doc}/cells {type: code|ask|markdown|figure, source?, prompt?, figure?, svg?, after?|at?}`
- `PATCH  …/docs/{doc}/cells/{cid} {source?, prompt?, figure?, svg?, type?, collapsed?, outputs_hidden?, note?}`
- `DELETE …/cells/{cid}` · `POST …/cells/{cid}/restore` · `POST …/cells/{cid}/move {to}`
- `POST   …/cells/{cid}/approve {code_hash}`             approve model code (exact hash, host / experiments_remote)
- `POST   …/docs/{doc}/run {cells: [ids] | until: cid | all: true, timeout?}`   sequential, one kernel; stops at
                                                          the first error or unapproved cell (`stopped`)
- `POST   …/cells/{cid}/run {timeout?}`                  one cell
- `POST   …/cells/{cid}/ask {prompt, variant?}`          natural language → code (assistant, needs approval); S-AG:
                                                       the same request gives the same code (« Réécrire »);
                                                       `variant: true` = « Autre version »; S-AB:
                                                          fast role, streamed as `calcul.draft`, a new request
                                                          replaces the running one (409 `replaced` for the old)
- `POST   …/docs/{doc}/detect {text}`                     {kind: code|ask, why} — what a new cell's text is
- `POST   …/cells/{cid}/explain {mode: error|lines|steps}` « Expliquer l'erreur » (explanation + proposed fix) /
                                                          lines / S-AJ: steps of the computation (facts checked by
                                                          Sage, streamed as `calcul.steps`)
- `POST   …/cells/{cid}/suggestion {code, model?}`        apply a proposed fix (model code: approval needed)
- `POST   /api/code/explain {language: sage|python|lean, code, error?, mode}`   the same, generic (Lean: handled by
                                                          lean_explain.py, S-AM — checked correction, goal states)
- `GET    /api/calcul/recipes` · `DELETE /api/calcul/recipes/{id}`   learned recipes (docs/CALCUL.md §3.5)
- `GET    /api/calcul/catalogue`                       canonical code structures + verification (S-AG, §3.6)
- `POST   /api/calcul/analyze {text, language?}`       what a request is recognized as (S-AG), no model
- `POST   …/docs/{doc}/interrupt | restart | shutdown | clear`
- `GET    …/docs/{doc}/variables`                         names defined in the kernel (or read from the code)
- `POST   …/docs/{doc}/assist {action: explain|fix, cell_id, prompt?}`
- `POST   …/cells/{cid}/to {target: conjecture|note|dossier|article, text?, title?, png?, tikz?}`
- `GET    /api/calcul/assets/{aid}`                       an image by content address, restrictive CSP
Older S-M routes `/api/calcul/{pid}[/cells…|/assist|/interrupt]` act on the default document « calcul ».
Library catalogue
- `GET    /api/library/catalog`                        entries with domain, project, tags, status, model, uses/used-by
                                                       (+ conditional results of proof plans)
- `PATCH  /api/library/meta/{name} {domain?, tags?}`  manual classification (kept in <config>/library-meta.json)
- `GET    /api/library/catalog/export?format=md|json|lean&name=`
Glossary
- `GET    /api/glossary/uses?term=`                   dossiers whose current statement or proof uses the term"""
from __future__ import annotations

import ast
import asyncio
import base64
import json
import re
import time

from aiohttp import web

from ... import config
from ...i18n import language, msg
from ...i18n import language as language_ui
from ...logs import get
from ...research.calcul import CALC_PREAMBLE, CalcError, CalcStore, assist_messages, extract_code
from ...research.notebook import (DEFAULT_DOC, FIGURE_MIME, KINDS, NotebookStore, outputs_text,
                                  static_names)
from ..common import body, ctx_of, error, ok, valid_id
from ..helpers import complete_once
from ...research import codegen
from ...research.recipes import request_key
from ...brain.leaderboard import DOMAINS          # one list of domains: model rankings and the results library

log = get("workbench")
WB = web.AppKey("workbench", object)
TAG_RE = re.compile(r"^[\w .+-]{1,40}$", re.U)


class Workbench:
    def __init__(self, ctx):
        self.ctx = ctx
        root = ctx.paths.config / "research" / "calcul"
        self.legacy = CalcStore(root)                 # S-M worksheets: migrated on first use, old plot ids
        self.calc = NotebookStore(ctx.jupyter.root_dir, root, legacy=self.legacy)
        self.meta_path = ctx.paths.config / "library-meta.json"
        self.locks: dict[str, asyncio.Lock] = {}
        self.cancel: set[str] = set()
        self.gens = codegen.Generations()      # S-AB: one model generation per cell; a new one replaces the old
        from ...research.recipes import RecipeStore
        self.recipes = RecipeStore(ctx.paths.config / "research" / "recipes.json")
        self.models = codegen.ModelStats(ctx.paths.config / "research" / "codegen-models.json")   # S-AG: pinned
        self._bridge = None
        self._kernels = None
        self.steps_cache: dict[str, dict] = {}   # S-AJ: « étapes du calcul » per (code, output, language, UI lang)

    def bridge(self):
        rs = getattr(self.ctx, "research", None)          # the research workshop's bridge (one kernel manager)
        if rs is not None:
            return rs.bridge
        if self._bridge is None:
            from ...research.sagebridge import SageBridge
            self._bridge = SageBridge(self.ctx)
        return self._bridge

    def kernels(self):
        if self._kernels is None:
            from ...research.nbkernels import NotebookKernels
            from ...research.sagebridge import PREAMBLE
            self._kernels = NotebookKernels(self.ctx, self.bridge(), PREAMBLE + "\n" + CALC_PREAMBLE)
        return self._kernels

    def lock(self, key: str) -> asyncio.Lock:
        return self.locks.setdefault(key, asyncio.Lock())

    async def run_cell(self, pid: str, cid: str, device: str, doc: str = DEFAULT_DOC,
                       timeout: float | None = 60.0) -> dict | None:
        """For other plugins (S-Q's research agent): run one cell in its document's kernel under the approval rule
        (approved model code or `experiments_auto`); None when not allowed, busy, or nothing ran."""
        try:
            c = await asyncio.to_thread(self.calc.cell_view, pid, doc, cid)
        except CalcError:
            return None
        if not self.calc.may_run(c, bool(self.ctx.settings.experiments_auto)) or self.lock(f"{pid}/{doc}").locked():
            return None
        r = await _run_cells(self, self.ctx, device, True, pid, doc, [cid], timeout)
        return r["runs"].get(cid)

    def meta(self) -> dict:
        data, _bad = config.read_json(self.meta_path)
        return data if isinstance(data, dict) else {}

    def save_meta(self, m: dict) -> None:
        config.atomic_write_text(self.meta_path, json.dumps(m, ensure_ascii=False, indent=1))


def W(request) -> Workbench:
    return request.app[WB]


def device_of(request) -> str:
    dev = request["device"]
    return dev.id if dev is not None else "host"


def _busy() -> web.Response:
    """Cells are running in this notebook's kernel (not a dossier: the generic « busy » text says « dossier »)."""
    return error(409, "calcul_busy", "Des cellules sont en cours d'exécution : attendez la fin ou interrompez-les.")


def _calc_fail(e: CalcError) -> web.Response:
    return web.json_response({"error": e.kind}, status=e.status)


def _project(request) -> str:
    pid = valid_id(request.match_info["pid"])
    if ctx_of(request).projects.get(pid) is None:
        raise web.HTTPNotFound(text='{"error":"not_found"}', content_type="application/json")
    return pid


def _doc(request) -> str:
    return request.match_info.get("doc") or DEFAULT_DOC


def _exec_allowed(request) -> web.Response | None:
    if not request["local"] and not getattr(ctx_of(request).settings, "experiments_remote", False):
        return error(403, "experiments_host_only", "Les expériences exécutent du code sur l'ordinateur hôte : "
                                                   "autorisées seulement depuis l'hôte (réglage).")
    return None


def _ev(ctx, pid: str, doc: str, **kw) -> None:
    ctx.publish("calcul.updated", {"project_id": pid, "doc": doc, **kw})


async def _calc_status(request, wb: Workbench, pid: str, doc: str, path: str) -> dict:
    ctx = ctx_of(request)
    br = wb.bridge()
    try:
        avail = await asyncio.to_thread(br.available)
    except Exception:  # noqa: BLE001
        avail = {}
    try:
        kernel = await wb.kernels().status(path)
    except Exception:  # noqa: BLE001
        kernel = {"kernel": "", "state": "none"}
    return {"available": avail, "sandbox": br.sandbox_kind, "auto": bool(ctx.settings.experiments_auto),
            "remote_allowed": bool(ctx.settings.experiments_remote), "local": bool(request["local"]),
            "running": wb.lock(f"{pid}/{doc}").locked(), "kernel": kernel,
            "idle_minutes": int(getattr(ctx.settings, "calcul_idle_minutes", 30))}


# ================================================================ Calcul: documents
async def docs_list(request):
    wb = W(request)
    pid = _project(request)
    try:
        docs = await asyncio.to_thread(wb.calc.docs, pid)
    except CalcError as e:
        return _calc_fail(e)
    return ok({"docs": docs})


async def docs_create(request):
    wb, ctx = W(request), ctx_of(request)
    pid = _project(request)
    data = await body(request)
    try:
        await asyncio.to_thread(wb.calc.docs, pid)
        d = await asyncio.to_thread(wb.calc.create, pid, str(data.get("title", "") or "Calcul")[:200],
                                    str(data.get("language", "sage")))
    except CalcError as e:
        return _calc_fail(e)
    ctx.publish("calcul.docs", {"project_id": pid})
    return ok({"doc": d}, status=201)


async def docs_patch(request):
    wb, ctx = W(request), ctx_of(request)
    pid, doc = _project(request), _doc(request)
    data = await body(request)
    try:
        d = await asyncio.to_thread(wb.calc.rename, pid, doc, str(data.get("title", "")))
    except CalcError as e:
        return _calc_fail(e)
    ctx.publish("calcul.docs", {"project_id": pid})
    return ok({"doc": d})


async def docs_delete(request):
    wb, ctx = W(request), ctx_of(request)
    pid, doc = _project(request), _doc(request)
    try:
        path = wb.calc.rel_path(pid, doc)
        if wb.kernels().known(path):
            await wb.kernels().shutdown(path)
        await asyncio.to_thread(wb.calc.delete_doc, pid, doc)
    except CalcError as e:
        return _calc_fail(e)
    ctx.publish("calcul.docs", {"project_id": pid})
    return ok({"removed": doc})


async def doc_get(request):
    wb = W(request)
    pid, doc = _project(request), _doc(request)
    try:
        if doc == DEFAULT_DOC:
            await asyncio.to_thread(wb.calc.docs, pid)
        path = wb.calc.rel_path(pid, doc)
        st = await _calc_status(request, wb, pid, doc, path)
        v = await asyncio.to_thread(wb.calc.view, pid, doc, wb.kernels().epoch(path) if st["kernel"].get("kernel")
                                    else "")
    except CalcError as e:
        return _calc_fail(e)
    return ok({**v, "status": st})


async def doc_ipynb(request):
    wb = W(request)
    pid, doc = _project(request), _doc(request)
    try:
        p = wb.calc.path(pid, doc)
    except CalcError as e:
        return _calc_fail(e)
    if not p.is_file():
        return error(404, "not_found")
    return web.FileResponse(p, headers={"Content-Type": "application/x-ipynb+json",
                                        "Content-Disposition": f'attachment; filename="{doc}.ipynb"',
                                        "X-Content-Type-Options": "nosniff"})


# ================================================================ Calcul: cells
def _cell_args(data: dict) -> dict:
    out = {}
    if "source" in data or "code" in data:
        out["code"] = str(data.get("source", data.get("code", "")))
    if "prompt" in data:
        out["prompt"] = str(data["prompt"])
    if "figure" in data:
        if not isinstance(data["figure"], dict):
            raise CalcError("bad_figure")
        out["figure"] = data["figure"]
        out["svg"] = str(data.get("svg", ""))[:3_000_000]
    return out


async def cell_add(request):
    wb, ctx = W(request), ctx_of(request)
    pid, doc = _project(request), _doc(request)
    data = await body(request)
    kind = str(data.get("type", "code"))
    if kind not in KINDS:
        return error(400, "bad_fields", "Champs refusés : {fields}.", fields="type")
    try:
        a = _cell_args(data)
        at = data.get("at")
        c = await asyncio.to_thread(
            wb.calc.add, pid, a.get("code", ""), str(data.get("language", "") or ""), "user", doc=doc, kind=kind,
            after=str(data.get("after", "") or ""), prompt=a.get("prompt", ""), figure=a.get("figure"),
            svg=a.get("svg", ""), at=int(at) if isinstance(at, int) else None)
    except CalcError as e:
        return _calc_fail(e)
    _ev(ctx, pid, doc, cell=c)
    return ok({"cell": c}, status=201)


async def cell_edit(request):
    wb, ctx = W(request), ctx_of(request)
    pid, doc = _project(request), _doc(request)
    data = await body(request)
    allowed = ("source", "code", "language", "note", "prompt", "figure", "svg", "type", "collapsed", "outputs_hidden")
    bad = [k for k in data if k not in allowed]
    if bad:
        return error(400, "bad_fields", "Champs refusés : {fields}.", fields=", ".join(bad))
    try:
        a = _cell_args(data)
        c = await asyncio.to_thread(
            wb.calc.edit, pid, request.match_info["cid"], doc=doc, by="user", code=a.get("code"),
            prompt=a.get("prompt"), figure=a.get("figure"), svg=a.get("svg", ""),
            language=str(data["language"]) if "language" in data else None,
            note=str(data["note"]) if "note" in data else None,
            kind=str(data["type"]) if "type" in data else None,
            collapsed=bool(data["collapsed"]) if "collapsed" in data else None,
            outputs_hidden=bool(data["outputs_hidden"]) if "outputs_hidden" in data else None)
    except CalcError as e:
        return _calc_fail(e)
    _ev(ctx, pid, doc, cell=c)
    return ok({"cell": c})


async def cell_delete(request):
    wb, ctx = W(request), ctx_of(request)
    pid, doc = _project(request), _doc(request)
    try:
        c = await asyncio.to_thread(wb.calc.delete, pid, request.match_info["cid"], doc)
    except CalcError as e:
        return _calc_fail(e)
    _ev(ctx, pid, doc, removed=c["id"])
    return ok({"removed": c["id"]})


async def cell_restore(request):
    wb, ctx = W(request), ctx_of(request)
    pid, doc = _project(request), _doc(request)
    try:
        c = await asyncio.to_thread(wb.calc.restore, pid, request.match_info["cid"], doc)
    except CalcError as e:
        return _calc_fail(e)
    _ev(ctx, pid, doc, cell=c)
    return ok({"cell": c})


async def cell_move(request):
    wb, ctx = W(request), ctx_of(request)
    pid, doc = _project(request), _doc(request)
    data = await body(request)
    try:
        order = await asyncio.to_thread(wb.calc.move, pid, request.match_info["cid"], int(data.get("to", 0)), doc)
    except (CalcError, ValueError, TypeError) as e:
        return _calc_fail(e) if isinstance(e, CalcError) else error(400, "bad_fields", "Champs refusés : {fields}.",
                                                                    fields="to")
    _ev(ctx, pid, doc, order=order)
    return ok({"order": order})


async def cell_approve(request):
    if (r := _exec_allowed(request)) is not None:
        return r
    wb, ctx = W(request), ctx_of(request)
    pid, doc = _project(request), _doc(request)
    data = await body(request)
    try:
        c = await asyncio.to_thread(wb.calc.approve, pid, request.match_info["cid"], str(data.get("code_hash", "")),
                                    device_of(request), doc)
    except CalcError as e:
        return _calc_fail(e)
    if c.get("type") == "ask" and c.get("intent_key") and c.get("origin") == "assistant":
        try:                              # S-AG: « approved by the user » ranks this version (after « ran OK »)
            v = await asyncio.to_thread(_tool_version, c["language"])
            await asyncio.to_thread(wb.recipes.approve, c["intent_key"], c["code"], c["language"], v)
        except Exception:  # noqa: BLE001
            log.exception("approval not recorded")
    _ev(ctx, pid, doc, cell=c)
    return ok({"cell": c})


# ================================================================ Calcul: execution
def _uexpr(res, name: str) -> str:
    """A string returned by one of Madalean's user_expressions, only when the cell displayed a result."""
    v = (getattr(res, "user_expressions", None) or {}).get(name, "")
    if not v or not any(o.get("output_type") == "execute_result" for o in getattr(res, "outputs", []) or []):
        return ""
    try:
        v = ast.literal_eval(v)
    except (ValueError, SyntaxError):
        return ""
    return v if isinstance(v, str) else ""


def _approx(res) -> str:
    tex = _uexpr(res, "latex")
    if tex:
        for o in res.outputs:
            if o.get("output_type") == "execute_result" and "text/latex" not in o.get("data", {}):
                o["data"]["text/latex"] = "$\\displaystyle " + tex + "$"
    return _uexpr(res, "approx")


async def _run_cells(wb: Workbench, ctx, device: str, live: bool, pid: str, doc: str, ids: list[str],
                     timeout: float | None, autofix: bool = True) -> dict:
    """Run cells in order in the document's one kernel (caller checked the device may execute). The automatic fix of a
    failed « ask » cell runs AFTER the kernel lock is released (S-AB: a model call never blocks the notebook) and
    is cancelled by a new request on that cell."""
    store, km = wb.calc, wb.kernels()
    path = store.rel_path(pid, doc)
    key = f"{pid}/{doc}"
    runs, stopped, fixed = {}, None, None
    pending = None
    wb.cancel.discard(key)
    async with wb.lock(key):
        for cid in ids:
            if key in wb.cancel:
                stopped = {"cell_id": cid, "reason": "interrupted"}
                break
            try:
                c = await asyncio.to_thread(store.cell_view, pid, doc, cid)
            except CalcError:
                continue
            if c["type"] not in ("code", "ask") or not c["code"].strip():
                continue
            if not store.may_run(c, bool(ctx.settings.experiments_auto)):
                stopped = {"cell_id": cid, "reason": "not_approved"}
                break
            up = await asyncio.to_thread(store.upstream_of, pid, doc, cid)
            to = timeout or (300.0 if c["language"] == "sage" else 60.0)

            def on_output(kind: str, text: str, cid=cid) -> None:
                ctx.publish("calcul.output", {"project_id": pid, "doc": doc, "cell_id": cid, "kind": kind,
                                              "text": text[:20000]})
            ctx.publish("calcul.running", {"project_id": pid, "doc": doc, "cell_id": cid})
            res = await km.execute(path, c["language"], c["code"], timeout=to, on_output=on_output)
            eng = (km.docs.get(path) or {}).get("engine")
            if eng:
                await asyncio.to_thread(store.set_engine, pid, doc, eng)
            run = await asyncio.to_thread(store.record_run, pid, cid, res, device, c["code_hash"],
                                          doc=doc, kernel=res.kernel, upstream=up, approx=_approx(res))
            runs[cid] = run
            _ev(ctx, pid, doc, cell_id=cid, run=run)
            if c["type"] == "ask" and c.get("origin") == "assistant" and c.get("prompt") and \
                    res.status in ("ok", "error"):
                await _learn(wb, pid, doc, c, res.status == "ok", run, ctx)   # S-AG: ran OK / failed → ranking
            if res.status != "ok":
                stopped = {"cell_id": cid, "reason": res.status}
                if (c["type"] == "ask" and autofix and res.status == "error"
                        and (c.get("autofix") or {}).get("n", 0) < AUTOFIX_MAX):
                    pending = (c, run)
                break
    wb.cancel.discard(key)
    if pending is not None:
        try:
            fixed = await wb.gens.run(f"{pid}/{doc}/{pending[0]['id']}",
                                      _autofix(wb, ctx, live, pid, doc, pending[0], pending[1]))
        except codegen.Replaced:
            fixed = None
        # S-AB (DECISIONS D35): the corrected code runs again by itself ONLY where model code needs no approval
        # (`experiments_auto`, host or allowed device); otherwise it waits for « Approuver et exécuter ». Bounded by
        # AUTOFIX_MAX corrections per request.
        if fixed is not None and wb.calc.may_run(fixed, bool(ctx.settings.experiments_auto)):
            again = await _run_cells(wb, ctx, device, live, pid, doc, [fixed["id"]], timeout)
            runs.update(again["runs"])
            stopped = again["stopped"]
            fixed = again["autofix"] or {**fixed, "reran": True}
    return {"runs": runs, "stopped": stopped, "autofix": fixed}


AUTOFIX_MAX = 3


async def _learn(wb: Workbench, pid: str, doc: str, c: dict, ok_: bool = True, run: dict | None = None,
                 ctx=None) -> None:
    """S-AG (D39): the run of a request cell ranks its code version (ran OK > approved > faster; a version that only
    failed is never preferred again) and the model that wrote it (pinned model per language)."""
    try:
        v = await asyncio.to_thread(_tool_version, c["language"])
        key = c.get("intent_key") or request_key(c["prompt"], set(c.get("uses") or []))
        secs = (run or {}).get("seconds")
        model = c.get("model") or ""
        af = c.get("autofix") or {}
        by_conductor = af.get("by") == "conductor" and af.get("code_hash") == c.get("code_hash")
        await asyncio.to_thread(wb.recipes.outcome, key, c["code"], c["language"], v, ok=ok_,
                                seconds=float(secs) if isinstance(secs, (int, float)) else None,
                                error=((run or {}).get("error") or "")[-300:], request=c["prompt"],
                                uses=c.get("uses") or [], model=model,
                                origin="conductor" if by_conductor else
                                model if model in ("catalogue", "fix", "recipe") else (c.get("gen") or "model"))
        if by_conductor:
            # S-AN (D46): a conductor's correction succeeds when it runs; it never pins Claude as the Calcul model
            from ...research import conductorfix
            if not af.get("measured") and ctx is not None:
                conductorfix.record(ctx, model, "codefix", ok_, float(af.get("seconds") or 0),
                                    float(af.get("usd") or 0))
                await asyncio.to_thread(wb.calc.set_autofix, pid, doc, c["id"], {**af, "measured": True})
        elif model:
            await asyncio.to_thread(wb.models.ran, "sage" if c["language"] == "sage" else "python", model, ok_)
    except Exception:  # noqa: BLE001 (learning never breaks a run)
        log.exception("recipe not recorded")


def _tool_version(lang_: str) -> str:
    from ...research import codecat
    return codecat.tool_version("sage") if lang_ == "sage" else ""   # Python recipes: no version (S-AB)


async def _autofix(wb: Workbench, ctx, live: bool, pid: str, doc: str, c: dict, run: dict) -> dict | None:
    """An « ask » cell failed: the error goes back to the model for a corrected proposal (AUTOFIX_MAX per request;
    each correction is a version of the cell, « corrigé automatiquement », the user can go back)."""
    names = await _names(wb, live, pid, doc, c["id"], c["language"])
    n = (c.get("autofix") or {}).get("n", 0) + 1
    # S-AN (D46): the conductor corrects after the deterministic fixer, within this request's budget
    from ...research import conductorfix
    cond = {"scope": conductorfix.calcul_scope(pid, doc, c["id"], c.get("prompt", "")), "attempt": n - 1,
            "where": {"kind": "calcul", "project_id": pid, "doc": doc, "cell_id": c["id"]}}
    try:
        prev = await _prev_defs(wb, pid, doc, c["id"])
        r = await codegen.transcribe(ctx, language=c["language"], prompt=c.get("prompt", ""), names=names,
                                     context="", owner=f"calcul-{pid}", lang=language(), fix_code=c["code"],
                                     fix_error=(run.get("error") or run.get("stderr") or "")[-3000:],
                                     stats=wb.models, prev=prev, conductor=cond)
    except Exception:  # noqa: BLE001
        return None
    code, model = r["code"], r["model"]
    cf = r.get("conductor") or None
    if not code or code == c["code"]:
        return None
    try:
        cur = await asyncio.to_thread(wb.calc.cell_view, pid, doc, c["id"])
    except CalcError:
        return None
    if cur.get("code_hash") != c.get("code_hash"):
        return None                     # the cell changed meanwhile (rewritten, edited): never overwrite it
    for att in r.get("attempts") or []:           # versions that did not even compile: kept in the history
        await asyncio.to_thread(wb.calc.edit, pid, c["id"], doc=doc, code=att["code"], by="assistant", model=model)
    vinfo = {"by": "conductor", "name": cf["name"], "usd": cf["usd"], "what": cf["what"]} if cf else None
    new = await asyncio.to_thread(wb.calc.edit, pid, c["id"], doc=doc, code=code, by="assistant", model=model,
                                  vinfo=vinfo)
    fix = {"t": time.time(), "model": model, "n": n, "max": AUTOFIX_MAX,
           "error": (run.get("error") or "").strip().splitlines()[-1:][0][:200] if run.get("error") else ""}
    if cf:                               # « Corrigé par Claude Sonnet · 0,004 $ » (its run outcome is measured)
        fix.update(by="conductor", name=cf["name"], tier=cf["tier"], usd=cf["usd"], what=cf["what"],
                   seconds=cf["seconds"], request_usd=cf["request_usd"], code_hash=new.get("code_hash", ""))
    await asyncio.to_thread(wb.calc.set_autofix, pid, doc, c["id"], fix)
    await asyncio.to_thread(wb.calc.set_side, pid, doc, c["id"], uses=r.get("uses") or [])
    new["autofix"] = fix
    _ev(ctx, pid, doc, cell=new)
    return new


async def doc_run(request):
    if (r := _exec_allowed(request)) is not None:
        return r
    wb = W(request)
    pid, doc = _project(request), _doc(request)
    data = await body(request)
    try:
        v = await asyncio.to_thread(wb.calc.view, pid, doc)
    except CalcError as e:
        return _calc_fail(e)
    order = [c["id"] for c in v["cells"]]
    if isinstance(data.get("cells"), list):
        ids = [str(x) for x in data["cells"] if str(x) in order]
    elif data.get("until"):
        u = str(data["until"])
        if u not in order:
            return error(404, "not_found")
        ids = order[: order.index(u) + 1]
    elif data.get("from"):
        f = str(data["from"])
        if f not in order:
            return error(404, "not_found")
        ids = order[order.index(f):]
    else:
        ids = order
    if wb.lock(f"{pid}/{doc}").locked():
        return _busy()
    timeout = max(1.0, min(float(data["timeout"]), 600.0)) if data.get("timeout") else None
    return ok(await _run_cells(W(request), ctx_of(request), device_of(request), True, pid, doc, ids, timeout))


async def cell_run(request):
    if (r := _exec_allowed(request)) is not None:
        return r
    wb, ctx = W(request), ctx_of(request)
    pid, doc = _project(request), _doc(request)
    cid = request.match_info["cid"]
    data = await body(request)
    try:
        c = await asyncio.to_thread(wb.calc.cell_view, pid, doc, cid)
    except CalcError as e:
        return _calc_fail(e)
    if c["type"] not in ("code", "ask"):
        return error(400, "bad_fields", "Champs refusés : {fields}.", fields="type")
    if not wb.calc.may_run(c, bool(ctx.settings.experiments_auto)):
        return error(403, "not_approved", "Ce code a été écrit par l'assistant : relisez-le et approuvez-le d'abord.")
    if wb.lock(f"{pid}/{doc}").locked():
        return _busy()
    timeout = max(1.0, min(float(data["timeout"]), 600.0)) if data.get("timeout") else None
    r = await _run_cells(wb, ctx, device_of(request), True, pid, doc, [cid], timeout)
    run = r["runs"].get(cid)
    if run is None:
        return error(409, "not_run", "Rien à exécuter.")
    return ok({"run": run, "autofix": r["autofix"]})


async def doc_interrupt(request):
    wb = W(request)
    pid, doc = _project(request), _doc(request)
    wb.cancel.add(f"{pid}/{doc}")
    done = await wb.kernels().interrupt(wb.calc.rel_path(pid, doc))
    return ok({"interrupted": done})


async def doc_restart(request):
    if (r := _exec_allowed(request)) is not None:
        return r
    wb, ctx = W(request), ctx_of(request)
    pid, doc = _project(request), _doc(request)
    if wb.lock(f"{pid}/{doc}").locked():
        return _busy()
    try:
        v = await asyncio.to_thread(wb.calc.view, pid, doc)
        kid = await wb.kernels().restart(wb.calc.rel_path(pid, doc), v["doc"]["language"])
    except CalcError as e:
        return _calc_fail(e)
    except Exception as e:  # noqa: BLE001
        return error(503, "kernel_unavailable", "Noyau indisponible ({err}).", err=str(e)[:200])
    _ev(ctx, pid, doc, restarted=True)
    return ok({"kernel": kid})


async def doc_shutdown(request):
    wb, ctx = W(request), ctx_of(request)
    pid, doc = _project(request), _doc(request)
    await wb.kernels().shutdown(wb.calc.rel_path(pid, doc))
    _ev(ctx, pid, doc, restarted=True)
    return ok({"stopped": True})


async def doc_clear(request):
    wb, ctx = W(request), ctx_of(request)
    pid, doc = _project(request), _doc(request)
    try:
        await asyncio.to_thread(wb.calc.clear_outputs, pid, doc)
    except CalcError as e:
        return _calc_fail(e)
    _ev(ctx, pid, doc, cleared=True)
    return ok({"cleared": True})


NAMES_WAIT = 3.0


async def _names(wb: Workbench, live: bool, pid: str, doc: str, cid: str, lang_: str) -> list:
    """Defined names: asked to the running kernel (Madalean's helper, `live` = the device may execute), else read
    from the code above."""
    names = None
    # S-AB: never wait for a busy kernel (the query would queue behind the running cell): static names instead
    if live and not wb.lock(f"{pid}/{doc}").locked():
        try:
            names = await asyncio.wait_for(wb.kernels().variables(wb.calc.rel_path(pid, doc), lang_), NAMES_WAIT)
        except Exception:  # noqa: BLE001 (timeout included)
            names = None
    if names is None:
        v = await asyncio.to_thread(wb.calc.view, pid, doc)
        src = []
        for c in v["cells"]:
            if c["id"] == cid:
                break
            if c["type"] in ("code", "ask"):
                src.append(c["code"])
        names = static_names(src)
    return names


async def doc_variables(request):
    wb = W(request)
    pid, doc = _project(request), _doc(request)
    try:
        v = await asyncio.to_thread(wb.calc.view, pid, doc)
    except CalcError as e:
        return _calc_fail(e)
    names = await _names(wb, _exec_allowed(request) is None, pid, doc, "", v["doc"]["language"])
    return ok({"names": [{"name": n, "type": t, "value": r} for n, t, r in names]})


async def cell_ask(request):
    pid, doc = _project(request), _doc(request)
    data = await body(request)
    return await _do_ask(request, pid, doc, request.match_info["cid"], str(data.get("prompt", "")),
                         variant=bool(data.get("variant")))


async def _prev_defs(wb: Workbench, pid: str, doc: str, cid: str) -> dict[str, str]:
    """Single-line definitions of the cells above `cid` (S-AG: the fixer may copy one a cell relies on)."""
    from ...research.codefix import prev_definitions
    try:
        v = await asyncio.to_thread(wb.calc.view, pid, doc)
    except CalcError:
        return {}
    src = []
    for c in v["cells"]:
        if c["id"] == cid:
            break
        if c["type"] in ("code", "ask"):
            src.append(c["code"])
    return prev_definitions(src, v["doc"]["language"])


async def _do_ask(request, pid: str, doc: str, cid: str, prompt: str, variant: bool = False):
    """Natural language → Sage: the model writes the code of an « ask » cell from the request and the notebook's
    current names (a compact summary, never full outputs); the code runs only once approved (or auto, host).
    S-AB: fast transcription (research/codegen.py), the code streams into the cell (`calcul.draft` events), and a
    new request for the same cell replaces the one still running (« Réécrire » is always possible)."""
    wb, ctx = W(request), ctx_of(request)
    try:
        c = await asyncio.to_thread(wb.calc.cell_view, pid, doc, cid)
    except CalcError as e:
        return _calc_fail(e)
    if c["type"] != "ask":
        return error(400, "bad_fields", "Champs refusés : {fields}.", fields="type")
    prompt = (prompt or c.get("prompt", "")).strip()[:4000]
    if not prompt:
        return error(400, "bad_fields", "Champs refusés : {fields}.", fields="prompt")
    try:
        return await wb.gens.run(f"{pid}/{doc}/{cid}", _ask_job(request, wb, ctx, pid, doc, c, prompt, variant))
    except codegen.Replaced:
        return error(409, "replaced", "Une demande plus récente a remplacé celle-ci.")


async def _ask_job(request, wb: Workbench, ctx, pid: str, doc: str, c: dict, prompt: str, variant: bool = False):
    cid = c["id"]
    names = await _names(wb, _exec_allowed(request) is None, pid, doc, cid, c["language"])
    context = await asyncio.to_thread(wb.calc.context, pid, doc, cid)
    prev = await _prev_defs(wb, pid, doc, cid)
    ctx.publish("calcul.draft", {"project_id": pid, "doc": doc, "cell_id": cid, "code": "", "state": "start"})

    def on_code(part: str) -> None:
        ctx.publish("calcul.draft", {"project_id": pid, "doc": doc, "cell_id": cid, "code": part[:20000],
                                     "state": "writing"})
    try:
        r = await codegen.transcribe(ctx, language=c["language"], prompt=prompt, names=names, context=context,
                                     owner=f"calcul-{pid}", lang=language(), on_code=on_code, recipes=wb.recipes,
                                     variant=variant, stats=wb.models, prev=prev)
    except asyncio.CancelledError:
        raise
    except Exception as e:  # noqa: BLE001
        ctx.publish("calcul.draft", {"project_id": pid, "doc": doc, "cell_id": cid, "code": "", "state": "error"})
        return error(503, "no_model", "Aucun modèle disponible ({err}).", err=str(e)[:200])
    ctx.publish("calcul.draft", {"project_id": pid, "doc": doc, "cell_id": cid, "code": "", "state": "done"})
    code, model = r["code"], r["model"]
    side = {"intent_key": r.get("key") or "", "recognized": r.get("recognized"), "gen": r.get("origin") or ""}
    if r.get("request_error"):
        # S-AG: the request itself is wrong (F_12): explained at once, no code, the cell keeps its request
        await asyncio.to_thread(wb.calc.set_side, pid, doc, cid, **side)
        e = r["request_error"]
        return error(422, "bad_request_math", "{text}", text=e["fr"] if language() == "fr" else e["en"])
    if not code:
        return error(502, "no_code", "Le modèle n'a pas proposé de code ; reformulez la demande.")
    try:
        for att in r.get("attempts") or []:        # versions corrected before showing: kept in the history
            await asyncio.to_thread(wb.calc.edit, pid, cid, doc=doc, code=att["code"], by="assistant", model=model,
                                    prompt=prompt)
        new = await asyncio.to_thread(wb.calc.edit, pid, cid, doc=doc, code=code, by="assistant", model=model,
                                      prompt=prompt)
        await asyncio.to_thread(wb.calc.set_side, pid, doc, cid, uses=r.get("uses") or [], **side)
        new = await asyncio.to_thread(wb.calc.cell_view, pid, doc, cid)
    except CalcError as e:
        return _calc_fail(e)
    _ev(ctx, pid, doc, cell=new)
    log.info("calcul ask: %s (%s, %s) in %.1f s (first code %.1f s%s%s)", model, r.get("origin"), r.get("coverage"),
             r["seconds"], r["first_s"], ", cached" if r["cached"] else "",
             ", repaired before showing" if r["fixed"] else "")
    return ok({"cell": new, "model": model, "approval_required": not ctx.settings.experiments_auto,
               "timing": {"seconds": r["seconds"], "first_s": r["first_s"], "cached": r["cached"]},
               "checked": {"valid": r["valid"], "fixed": r["fixed"], "error": r["error"]},
               "recipe": r.get("recipe") or "", "uses": r.get("uses") or [], "origin": r.get("origin") or "",
               "coverage": r.get("coverage") or "none", "recognized": r.get("recognized"),
               "key": r.get("key") or ""}, status=201)


async def doc_assist(request):
    """explain (Markdown answer) · fix (rewrite a failed cell as assistant code). Older « write » = ask cell."""
    wb, ctx = W(request), ctx_of(request)
    pid, doc = _project(request), _doc(request)
    data = await body(request)
    action = str(data.get("action", "write"))
    if action not in ("write", "fix", "explain"):
        return error(400, "bad_fields", "Champs refusés : {fields}.", fields="action")
    try:
        v = await asyncio.to_thread(wb.calc.view, pid, doc)
    except CalcError as e:
        return _calc_fail(e)
    cell = next((x for x in v["cells"] if x["id"] == str(data.get("cell_id", ""))), None)
    if action == "write":
        try:
            c = await asyncio.to_thread(wb.calc.add, pid, "", "", "assistant", doc=doc, kind="ask",
                                        after=str(data.get("after", "") or ""), prompt=str(data.get("prompt", "")))
        except CalcError as e:
            return _calc_fail(e)
        return await _do_ask(request, pid, doc, c["id"], str(data.get("prompt", "")))
    if cell is None or cell["type"] not in ("code", "ask"):
        return error(404, "not_found")
    outs = outputs_text([_raw(o) for o in cell.get("outputs") or []], 6000)
    err = next((f"{o['ename']}: {o['evalue']}\n{o['traceback'][-3000:]}" for o in cell.get("outputs") or []
                if o["type"] == "error"), "")
    msgs = assist_messages(action, cell["language"], language(), str(data.get("prompt", "")), cell["code"], err, outs)
    try:
        r = await complete_once(ctx, "assistant", msgs, ctx.settings.mode, owner=f"calcul-{pid}", max_tokens=3000,
                                temperature=0.2)
    except Exception as e:  # noqa: BLE001
        return error(503, "no_model", "Aucun modèle disponible ({err}).", err=str(e)[:200])
    model = getattr(r.model, "key", "") or ""
    if action == "explain":
        return ok({"text": r.text, "model": model})
    code = extract_code(r.text)
    if not code:
        return error(502, "no_code", "Le modèle n'a pas proposé de code ; reformulez la demande.")
    try:
        new = await asyncio.to_thread(wb.calc.edit, pid, cell["id"], doc=doc, code=code, by="assistant", model=model)
    except CalcError as e:
        return _calc_fail(e)
    _ev(ctx, pid, doc, cell=new)
    return ok({"cell": new, "model": model, "approval_required": not ctx.settings.experiments_auto}, status=201)


def _raw(o: dict) -> dict:
    """A view output back to the nbformat shape (for outputs_text)."""
    if o["type"] == "stream":
        return {"output_type": "stream", "name": o.get("name"), "text": o.get("text", "")}
    if o["type"] == "error":
        return {"output_type": "error", "ename": o.get("ename"), "evalue": o.get("evalue")}
    return {"output_type": "display_data", "data": {k: (v if isinstance(v, str) else "") for k, v in
                                                    o.get("data", {}).items()}}


# ================================================================ Calcul: one-click connections
def _cell_text(cell: dict) -> str:
    return outputs_text([_raw(o) for o in cell.get("outputs") or []], 6000)


def _fact_text(cell: dict) -> str:
    out = _cell_text(cell)
    lead = f"> {cell['prompt']}\n\n" if cell.get("type") == "ask" and cell.get("prompt") else ""
    return lead + f"```{cell['language']}\n{cell['code']}\n```\n\n" + (f"```\n{out}\n```\n" if out else "")


def _latex_of(cell: dict) -> list[str]:
    return [o["data"]["text/latex"] for o in cell.get("outputs") or [] if o["type"] in ("result", "display")
            and "text/latex" in o["data"]]


def _verbatim(code: str) -> str:
    return "\\begin{verbatim}\n" + code.replace("\\end{verbatim}", "\\end {verbatim}") + "\n\\end{verbatim}"


async def _to_article(ctx, wb: Workbench, pid: str, doc: str, cell: dict, text: str, title: str, png: bytes | None,
                      engine: dict | None) -> dict:
    """Figure, table or computation → the project's article. With the LaTeX project (docs/ARTICLE.md, S-R), a
    figure is a `figure` environment over a content-addressed image, a computation is its result (formula or
    verbatim output) plus its code in a « Computations » section at the end (the appendix of computations)."""
    from ...research import article as art_mod
    from ...research import texproject as tp
    fr = language() == "fr"
    eng = (engine or {}).get("name", "SageMath") + (" " + engine["version"] if (engine or {}).get("version") else "")
    label = "calc:" + re.sub(r"[^A-Za-z0-9]", "", cell["id"])
    if png is not None:
        await asyncio.to_thread(tp.ensure, ctx, pid)
        rel = await asyncio.to_thread(tp.add_figure, ctx, pid, png)
        cap = tp.texio_plain(text or title or ("Figure" if not fr else "Figure"))
        body_ = ("\\begin{figure}[ht]\n\\centering\n\\includegraphics[width=0.8\\linewidth]{" + rel + "}\n"
                 "\\caption{" + cap + "}\\label{fig:" + label[5:] + "}\n\\end{figure}")
        blocks = [art_mod.new_block("prose", "", body_, "user")]
    else:
        latex = _latex_of(cell)
        if text:
            main = text
        elif latex:
            main = "\n".join(latex)
        else:
            out = _cell_text(cell)
            if not out:
                raise CalcError("no_output", 409)
            main = "```\n" + out[:20000] + "\n```"
        if tp.exists(ctx, pid):
            if not text and not latex:
                main = _verbatim(_cell_text(cell)[:20000])
            main += ("\n\n{\\footnotesize " + ("Calcul " if fr else "Computation ") + "\\ref{" + label + "} ("
                     + tp.texio_plain(eng) + ").}")
            appendix = ("\\paragraph{" + ("Calcul" if fr else "Computation") + " \\label{" + label + "}"
                        + tp.texio_plain(title or "") + "}\n" + _verbatim(cell["code"]))
        else:
            main += "\n\n*" + (f"Calcul ({eng}), code en annexe." if fr else f"Computation ({eng}), code in the appendix.") + "*"
            appendix = f"**{title or ('Calcul' if fr else 'Computation')}**\n\n```{cell['language']}\n{cell['code']}\n```"
        blocks = [art_mod.new_block("prose", title or msg("Résultat de calcul")["text"], main, "user")]
        blocks[0]["calcul_appendix"] = appendix
    art = await asyncio.to_thread(art_mod.load, ctx, pid)
    sec_title = "Calculs (SageMath)" if fr else "Computations (SageMath)"
    sec = next((i for i, b in enumerate(art["blocks"]) if b["kind"] == "section" and b.get("title") == sec_title), None)
    for b in blocks:
        appendix = b.pop("calcul_appendix", None)
        b["calcul_origin"] = {"kind": "calcul", "project_id": pid, "doc": doc, "cell_id": cell["id"]}
        if sec is None:
            art["blocks"].append(b)
        else:
            art["blocks"].insert(sec, b)
            sec += 1
        if appendix:
            if sec is None:
                art["blocks"].append(art_mod.new_block("section", sec_title, "", "user"))
                sec = len(art["blocks"]) - 1
            art["blocks"].append(art_mod.new_block("prose", "", appendix, "user"))
    await asyncio.to_thread(art_mod.save, ctx, pid, art)
    ctx.publish("article.updated", {"project_id": pid})
    return blocks[0]


async def cell_to(request):
    """One-click actions on a result: → conjecture, → note, → Lean dossier, → article (figure, formula, table)."""
    wb, ctx = W(request), ctx_of(request)
    pid, doc = _project(request), _doc(request)
    cid = request.match_info["cid"]
    data = await body(request)
    target = str(data.get("target", ""))
    try:
        v = await asyncio.to_thread(wb.calc.view, pid, doc)
    except CalcError as e:
        return _calc_fail(e)
    cell = next((x for x in v["cells"] if x["id"] == cid), None)
    if cell is None:
        return error(404, "not_found")
    text = str(data.get("text", "")).strip()[:20000]
    title = str(data.get("title", "")).strip()[:200]
    origin = {"kind": "calcul", "project_id": pid, "doc": doc, "cell_id": cid,
              "run_id": ((cell.get("runs") or [{}])[-1] or {}).get("id", "")}
    is_code = cell["type"] in ("code", "ask")
    rs = getattr(ctx, "research", None)
    if target == "conjecture":
        if rs is None or not text:
            return error(400, "bad_fields", "Champs refusés : {fields}.", fields="text")
        from ...research.conjectures import ConjectureError, public as conj_public
        try:
            d = await rs.workshop.create(pid, text, motivation=_fact_text(cell) if is_code else cell["source"],
                                         title=title, origin=origin, device=device_of(request))
        except ConjectureError as e:
            return web.json_response({"error": e.kind}, status=getattr(e, "status", 400))
        return ok({"target": "conjecture", "conjecture": conj_public(d)}, status=201)
    if target == "note":
        if rs is None:
            return error(503, "unavailable")
        from ...research.notes import NoteError
        if is_code:
            md = (text + "\n\n" if text else "") + _fact_text(cell)
            for x in _latex_of(cell):
                md += "\n" + x + "\n"
        else:
            md = (text + "\n\n" if text else "") + (cell["source"] if cell["type"] == "markdown" else
                                                    "```json\n" + json.dumps(cell.get("figure"), ensure_ascii=False)[:20000] + "\n```")
        name = title or msg("Calcul du {d}", d=time.strftime("%d/%m/%Y %H:%M"))["text"]
        try:
            n = await asyncio.to_thread(rs.notes.create, pid, name, md, ["calcul"], "note", device_of(request))
        except NoteError as e:
            return web.json_response({"error": e.kind}, status=getattr(e, "status", 400))
        ctx.publish("note.updated", {"note": n.to_dict(), "device": device_of(request)})
        return ok({"target": "note", "note": n.to_dict()}, status=201)
    if target == "dossier":
        if not text:
            return error(400, "bad_fields", "Champs refusés : {fields}.", fields="text")
        from ..routes_work import create_dossier
        d, _job = await create_dossier(ctx, {"problem": text, "title": title, "project_id": pid, "start": False})
        d.extra["calcul_origin"] = origin
        await ctx.repo.save(d)
        return ok({"target": "dossier", "dossier": {"id": d.id, "title": d.title}}, status=201)
    if target == "article":
        png = None
        if data.get("png"):
            try:
                png = base64.b64decode(str(data["png"]).split(",", 1)[-1], validate=False)
            except ValueError:
                png = None
            from ...research.calcul import PNG_MAGIC
            if not png or not png.startswith(PNG_MAGIC) or len(png) > 15 * 1024 * 1024:
                return error(400, "bad_fields", "Champs refusés : {fields}.", fields="png")
        elif data.get("asset"):
            hit = await asyncio.to_thread(wb.calc.asset, str(data["asset"]))
            if hit is None or hit[1] != "image/png":
                return error(415, "bad_type", "Image PNG attendue.")
            png = hit[0]
        if png is None and not is_code:
            return error(400, "bad_fields", "Champs refusés : {fields}.", fields="png")
        try:
            b = await _to_article(ctx, wb, pid, doc, cell, text, title, png, v["doc"].get("engine"))
        except CalcError as e:
            return web.json_response({"error": e.kind, "message": msg("Exécutez d'abord la cellule.")["text"]},
                                     status=e.status)
        return ok({"target": "article", "block": b}, status=201)
    return error(400, "bad_fields", "Champs refusés : {fields}.", fields="target")


async def calc_asset(request):
    wb = W(request)
    hit = await asyncio.to_thread(wb.calc.asset, request.match_info["aid"])
    if hit is None:
        return error(404, "not_found")
    raw, mime = hit
    if mime == "image/svg+xml":                   # sanitised again: notebooks may have been saved by JupyterLab
        from ...research.calcul import sanitize_svg
        try:
            raw = sanitize_svg(raw.decode("utf-8", "replace")).encode()
        except CalcError:
            return error(415, "bad_type")
    return web.Response(body=raw, headers={
        "Content-Type": mime, "X-Content-Type-Options": "nosniff", "Cache-Control": "private, max-age=31536000, immutable",
        "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; img-src data:; sandbox"})


# ================================================================ Calcul: S-M compatibility (default document)
async def calc_get(request):
    """The S-M shape {sheet: {cells, rev}, trash, status} of the default document."""
    wb = W(request)
    pid = _project(request)
    try:
        await asyncio.to_thread(wb.calc.docs, pid)
        path = wb.calc.rel_path(pid, DEFAULT_DOC)
        st = await _calc_status(request, wb, pid, DEFAULT_DOC, path)
        v = await asyncio.to_thread(wb.calc.view, pid, DEFAULT_DOC)
    except CalcError as e:
        return _calc_fail(e)
    return ok({"sheet": {"project_id": pid, "cells": v["cells"], "rev": v["doc"]["rev"]},
               "trash": [{"id": t["id"], "code": t["source"]} for t in v["trash"]], "status": st, "doc": v["doc"]})


async def calc_interrupt(request):
    return await doc_interrupt(request)


async def calc_assist(request):
    return await doc_assist(request)


# ================================================================ S-AB: code or request, explanations on demand
async def doc_detect(request):
    """{text} → {kind: code|ask, why}: what was typed in a new cell is code (run it) or a request (the model writes
    the code). The UI shows the guess as a chip the user can switch in one click."""
    wb = W(request)
    pid, doc = _project(request), _doc(request)
    data = await body(request)
    text = str(data.get("text", ""))[:4000]
    try:
        v = await asyncio.to_thread(wb.calc.view, pid, doc)
    except CalcError as e:
        return _calc_fail(e)
    known = {n for n, _t, _r in static_names([c["code"] for c in v["cells"] if c["type"] in ("code", "ask")])}
    r = await asyncio.to_thread(codegen.detect, text, v["doc"]["language"], known)
    return ok({"kind": r["kind"], "why": r["why"]})


async def _explain(request, language: str, code: str, err: str, mode: str, owner: str):
    from ...research import explain as ex
    ctx = ctx_of(request)
    try:
        r = await ex.explain(ctx, language=language, code=code, error=err, mode=mode, lang=language_ui(),
                             owner=owner)
    except ex.ExplainError as e:
        return error(400, "bad_fields", "Champs refusés : {fields}.", fields=str(e))
    except Exception as e:  # noqa: BLE001
        return error(503, "no_model", "Aucun modèle disponible ({err}).", err=str(e)[:200])
    return ok(r)


async def code_explain(request):
    """Generic (Calcul now, Lean proofs later): {language: sage|python|lean, code, error?, mode: error|lines}.
    S-AJ: `mode: steps` with {output, request?}: the mathematical steps, model only (no kernel here: unverified)."""
    data = await body(request)
    mode = str(data.get("mode", "error"))
    if str(data.get("language", "")) == "lean" and mode in ("error", "lines"):
        from .lean_explain import handle      # S-AM (D45): Lean-specific prompt, goal states, checked correction
        return await handle(request, data)
    if mode == "steps":
        return await _steps_answer(request, str(data.get("language", "")), str(data.get("code", "")),
                                   str(data.get("output", ""))[:20000], str(data.get("request", ""))[:4000],
                                   None, "explain")
    return await _explain(request, str(data.get("language", "")), str(data.get("code", "")),
                          str(data.get("error", "")), mode, "explain")


# ---------------------------------------------------------------- S-AJ (D42): « Expliquer les étapes du calcul »
STEPS_CACHE_MAX = 200
STEPS_PROBE_TIMEOUT = 60.0
# the demo has no kernel: the seeded F5 cell gets the facts the real probe computes (docs/CALCUL.md §3.7)
DEMO_STEPS_FACTS = [{"k": "integer", "ok": None, "v": {"n": "4294967297"}},
                    {"k": "prime", "ok": True, "v": {"p": "641", "e": "1"}},
                    {"k": "prime", "ok": True, "v": {"p": "6700417", "e": "1"}},
                    {"k": "product_int", "ok": True, "v": {"prod": "641 \\cdot 6700417", "n": "4294967297"}}]


def _ok_output(cell: dict) -> str:
    """The text of a successful output ('' when the cell failed or shows nothing)."""
    outs = cell.get("outputs") or []
    if not outs or any(o["type"] == "error" for o in outs):
        return ""
    return _cell_text(cell)


def _shown_plain(cell: dict) -> str:
    """What the cell shows as plain text (printed text and text/plain results): the probe's recomputed value must
    be found in it."""
    parts = []
    for o in cell.get("outputs") or []:
        if o["type"] == "stream":
            parts.append(o.get("text", ""))
        elif o["type"] in ("result", "display"):
            parts.append(str((o.get("data") or {}).get("text/plain", "")))
    return "\n".join(parts)


async def _steps_facts(request, wb: Workbench, ctx, pid: str, doc: str, c: dict, op: str) -> tuple[list[dict], str]:
    """(raw facts computed by Sage, reason when there are none). Runs ONLY Madalean's fixed probe around the cell's
    own code, and only when that code may run here (the approval rule of every run, D35) and the device may
    execute; never while the notebook is running."""
    from ...research import steps
    if c["language"] != "sage":
        return [], "language"
    if not op:
        return [], "no_probe"
    if ctx.demo:
        return (DEMO_STEPS_FACTS, "") if op == "factor" and "2^32" in c["code"] else ([], "no_kernel")
    if _exec_allowed(request) is not None:
        return [], "host_only"
    if not wb.calc.may_run(c, bool(ctx.settings.experiments_auto)):
        return [], "not_approved"
    if c.get("stale"):
        return [], "stale"
    km = wb.kernels()
    if not hasattr(km, "probe"):
        return [], "no_kernel"
    key = f"{pid}/{doc}"
    if wb.lock(key).locked():
        return [], "busy"
    async with wb.lock(key):
        res = await km.probe(wb.calc.rel_path(pid, doc), c["language"], steps.program(c["code"], c["language"], op),
                             timeout=STEPS_PROBE_TIMEOUT)
    if res.status != "ok":
        return [], "probe_failed"
    d = steps.parse(res.stdout)
    if d.get("error") or not d.get("facts"):
        log.info("steps probe (%s): %s", op, d.get("error") or "no fact")
        return [], "probe_failed"
    if not steps.matches_output(d.get("result", ""), _shown_plain(c)):
        return [], "differs"
    return d["facts"], ""


async def _steps_answer(request, language: str, code: str, output: str, req_text: str, cell: tuple | None,
                        owner: str):
    """The explanation of the steps; `cell` = (wb, pid, doc, cell view) when it comes from a notebook cell (probes,
    streaming as `calcul.steps`), None for the generic endpoint (model only)."""
    import hashlib
    from ...research import explain as ex, intent as I, steps
    ctx = ctx_of(request)
    lang = language_ui()
    it = I.analyze(req_text) if req_text.strip() else None
    op = steps.probe_op(it.op if it is not None else "", code)
    ck = hashlib.sha256(json.dumps([language, code, output, req_text, lang, cell is not None]).encode()).hexdigest()
    wb = cell[0] if cell else W(request)
    hit = wb.steps_cache.get(ck)
    if hit is not None:
        return ok({**hit, "cached": True})
    if cell:
        _wb, pid, doc, c = cell
        raw, reason = await _steps_facts(request, wb, ctx, pid, doc, c, op)
    else:
        raw, reason = [], "no_kernel"
    facts = steps.facts_view(raw, lang)
    trusted = [f["text"] for f in facts if f["status"] != "failed"]
    last = [0.0]

    def publish(text: str, state: str) -> None:
        if cell:
            ctx.publish("calcul.steps", {"project_id": cell[1], "doc": cell[2], "cell_id": cell[3]["id"],
                                         "text": text[:20000], "state": state})

    def on_text(text: str) -> None:
        now = time.monotonic()
        if now - last[0] > 0.12:
            last[0] = now
            publish(text, "writing")
    publish("", "start")
    try:
        r = await ex.explain_steps(ctx, language=language, code=code, output=output, lang=lang, request=req_text,
                                   intent=I.summary(it, lang) if it is not None and it.recognized else "",
                                   facts=trusted, owner=owner, on_text=on_text)
    except ex.ExplainError as e:
        publish("", "error")
        return error(400, "bad_fields", "Champs refusés : {fields}.", fields=str(e))
    except asyncio.CancelledError:
        raise
    except Exception as e:  # noqa: BLE001
        publish("", "error")
        return error(503, "no_model", "Aucun modèle disponible ({err}).", err=str(e)[:200])
    publish("", "done")
    out = {"text": r["text"], "facts": facts, "verified": bool(trusted), "reason": reason, "op": op,
           "model": r["model"]}
    if r["text"] and reason in ("", "language", "no_probe", "no_kernel"):     # never cache a passing state (busy…)
        wb.steps_cache[ck] = out
        while len(wb.steps_cache) > STEPS_CACHE_MAX:
            wb.steps_cache.pop(next(iter(wb.steps_cache)))
    return ok({**out, "cached": False})


def _cell_error(cell: dict) -> str:
    return next((f"{o.get('ename', '')}: {o.get('evalue', '')}\n{(o.get('traceback') or '')[-2500:]}"
                 for o in cell.get("outputs") or [] if o["type"] == "error"), "")


async def cell_explain(request):
    """{mode: error|lines} on a cell: « Expliquer l'erreur » (explanation + a proposed fix, never applied by
    itself) or « Expliquer ligne par ligne »."""
    wb = W(request)
    pid, doc = _project(request), _doc(request)
    data = await body(request)
    try:
        c = await asyncio.to_thread(wb.calc.cell_view, pid, doc, request.match_info["cid"])
    except CalcError as e:
        return _calc_fail(e)
    if c["type"] not in ("code", "ask"):
        return error(400, "bad_fields", "Champs refusés : {fields}.", fields="type")
    mode = str(data.get("mode", "error"))
    key = f"{pid}/{doc}/{c['id']}:explain:{mode}"
    if mode == "steps":
        # S-AJ (D42): only a cell whose current code ran successfully (its output is the code's result)
        output = _ok_output(c)
        if not output or not c.get("last") or (c["last"].get("code_hash") and c["last"]["code_hash"] != c["code_hash"]):
            return error(409, "no_result", "Exécutez d'abord la cellule : il faut un résultat à expliquer.")
        req_text = c.get("prompt", "") if c["type"] == "ask" else ""
        try:
            return await wb.gens.run(key, _steps_answer(request, c["language"], c["code"], output, req_text,
                                                        (wb, pid, doc, c), f"calcul-{pid}"))
        except codegen.Replaced:
            return error(409, "replaced", "Une demande plus récente a remplacé celle-ci.")
    try:
        return await wb.gens.run(key, _explain(request, c["language"], c["code"], _cell_error(c), mode,
                                               f"calcul-{pid}"))
    except codegen.Replaced:
        return error(409, "replaced", "Une demande plus récente a remplacé celle-ci.")


async def cell_suggestion(request):
    """{code, model?}: the user applies a proposed fix. It is model code: it runs only once approved (unchanged
    rule), like every code a model wrote."""
    wb, ctx = W(request), ctx_of(request)
    pid, doc = _project(request), _doc(request)
    data = await body(request)
    code = str(data.get("code", ""))
    if not code.strip():
        return error(400, "bad_fields", "Champs refusés : {fields}.", fields="code")
    try:
        new = await asyncio.to_thread(wb.calc.edit, pid, request.match_info["cid"], doc=doc, code=code,
                                      by="assistant", model=str(data.get("model", ""))[:200])
    except CalcError as e:
        return _calc_fail(e)
    _ev(ctx, pid, doc, cell=new)
    return ok({"cell": new, "approval_required": not ctx.settings.experiments_auto})


async def recipes_list(request):
    """S-AB: the learned recipes of this host (request, code, version), newest first."""
    return ok({"recipes": [{k: r.get(k) for k in ("id", "request", "code", "language", "version", "uses", "t",
                                                   "hits")} for r in await asyncio.to_thread(W(request).recipes.list)]})


async def recipes_delete(request):
    if not await asyncio.to_thread(W(request).recipes.delete, request.match_info["rid"]):
        return error(404, "not_found")
    return ok({"removed": request.match_info["rid"]})


async def catalogue_get(request):
    """S-AG: the catalogue of canonical code structures, and what is verified on this installation."""
    from ...research import codecat
    ctx = ctx_of(request)
    data = await asyncio.to_thread(codecat.entries)
    data["status"] = {}
    for lang_ in ("sage", "python"):
        st = await asyncio.to_thread(codecat.status, lang_)
        data["status"][lang_] = ({k: st.get(k) for k in ("version", "built", "verified", "failed", "versions")}
                                 if st else None)
    for ws in list(getattr(ctx, "workspaces", None) or []):
        st = await asyncio.to_thread(codecat.lean_status, ws)
        data["status"][f"lean:{ws.key}"] = ({k: st.get(k) for k in ("flavor", "lean", "mathlib", "built", "verified",
                                                                      "failed")} if st else None)
    return ok(data)


async def analyze_request(request):
    """S-AG: what a request is recognized as (objects, operation, canonical code when fully covered). No model."""
    from ...research import codecat, intent as I
    data = await body(request)
    text = str(data.get("text", ""))[:4000]
    lang_ = "python" if data.get("language") == "python" else "sage"
    it = I.analyze(text)
    st = await asyncio.to_thread(codecat.status, lang_)
    a = codecat.assemble(it, lang_, st)
    return ok({"intent": it.to_dict(), "recognized": {"fr": I.summary(it, "fr"), "en": I.summary(it, "en")},
               "coverage": "full" if a and a.full else ("partial" if a and a.prefix else "none"),
               "code": a.code if a and a.full else "", "prefix": a.prefix if a else "",
               "error": it.errors[0] if it.errors else None})


def _revalidate_recipes(wb: Workbench, version: str) -> None:
    from ... import syntaxcards
    res = wb.recipes.revalidate("sage", version, lambda r: syntaxcards.validate_sage(
        r["code"], set(r.get("uses") or []), version)["ok"])
    log.info("recipes re-checked for Sage %s: %s", version, res)


def _register_calcul(a) -> None:
    a.add_post("/api/code/explain", code_explain)
    a.add_get("/api/calcul/recipes", recipes_list)
    a.add_get("/api/calcul/catalogue", catalogue_get)
    a.add_post("/api/calcul/analyze", analyze_request)
    a.add_delete("/api/calcul/recipes/{rid}", recipes_delete)
    a.add_get("/api/calcul/assets/{aid}", calc_asset)
    a.add_get("/api/calcul/{pid}/docs", docs_list)
    a.add_post("/api/calcul/{pid}/docs", docs_create)
    d = "/api/calcul/{pid}/docs/{doc}"
    a.add_get(d, doc_get)
    a.add_patch(d, docs_patch)
    a.add_delete(d, docs_delete)
    a.add_get(d + "/ipynb", doc_ipynb)
    a.add_get(d + "/variables", doc_variables)
    a.add_post(d + "/run", doc_run)
    a.add_post(d + "/interrupt", doc_interrupt)
    a.add_post(d + "/restart", doc_restart)
    a.add_post(d + "/shutdown", doc_shutdown)
    a.add_post(d + "/clear", doc_clear)
    a.add_post(d + "/assist", doc_assist)
    a.add_post(d + "/detect", doc_detect)
    a.add_post(d + "/cells/{cid}/explain", cell_explain)
    a.add_post(d + "/cells/{cid}/suggestion", cell_suggestion)
    for base in (d, "/api/calcul/{pid}"):
        a.add_post(base + "/cells", cell_add)
        a.add_patch(base + "/cells/{cid}", cell_edit)
        a.add_delete(base + "/cells/{cid}", cell_delete)
        a.add_post(base + "/cells/{cid}/restore", cell_restore)
        a.add_post(base + "/cells/{cid}/move", cell_move)
        a.add_post(base + "/cells/{cid}/approve", cell_approve)
        a.add_post(base + "/cells/{cid}/run", cell_run)
        a.add_post(base + "/cells/{cid}/ask", cell_ask)
        a.add_post(base + "/cells/{cid}/to", cell_to)
    a.add_get("/api/calcul/{pid}", calc_get)
    a.add_post("/api/calcul/{pid}/interrupt", calc_interrupt)
    a.add_post("/api/calcul/{pid}/assist", calc_assist)


async def _reaper(ctx, wbench: Workbench) -> None:
    """Idle Calcul kernels (ours and JupyterLab's under calcul/) stop after `calcul_idle_minutes` (0 = never)."""
    while True:
        await asyncio.sleep(60)
        if wbench._kernels is None:
            continue
        try:
            minutes = float(getattr(ctx.settings, "calcul_idle_minutes", 30) or 0)
            await wbench._kernels.reap(minutes * 60)
        except Exception:  # noqa: BLE001
            log.exception("calcul kernel reaper")


# ================================================================ library catalogue
def _status(d) -> tuple[str, list]:
    if d is None:
        return "verified", []
    cond = (d.extra or {}).get("conditional_proof")
    if d.proof_is_current or d.status == "proved":
        return "verified", []
    if cond:
        return "conditional", list(cond.get("admitted") or [])
    return "verified", []


def catalog(ctx, meta: dict) -> list[dict]:
    from ...brain.leaderboard import domain_of
    projects = {p.id: p.title for p in ctx.projects.list()}
    lib = ctx.library.entries
    used_by: dict[str, list[str]] = {}
    for e in lib:
        for dep in e.deps:
            used_by.setdefault(dep, []).append(e.name)
    out = []
    names = set()
    for e in lib:
        d = ctx.repo.get(e.dossier) if e.dossier else None
        nl = (d.understood_display or d.understood or d.problem) if d is not None else ""
        auto = domain_of(e.statement + "\n" + nl)
        m = meta.get(e.name) or {}
        pv = d.proofs[d.cur_proof] if d is not None and 0 <= d.cur_proof < len(d.proofs) else None
        status, admitted = _status(d)
        names.add(e.name)
        out.append({"name": e.name, "title": e.title, "statement": e.statement, "nl": nl, "code": e.code,
                    "workspace": e.workspace, "dossier": e.dossier, "t": e.t,
                    "project_id": d.project_id if d is not None else "",
                    "project": projects.get(d.project_id, "") if d is not None else "",
                    "domain": m.get("domain") or auto, "domain_auto": auto, "domain_manual": bool(m.get("domain")),
                    "tags": list(m.get("tags") or []), "status": status, "admitted": admitted,
                    "model": (pv.model if pv is not None else "") or "", "by_user": pv is not None and pv.source == "user",
                    "axioms": (pv.meta.get("axioms") if pv is not None else None),
                    "uses": list(e.deps), "used_by": sorted(used_by.get(e.name, []))})
    for d in ctx.repo.list():                         # conditional results (proof plans): never in the library
        cond = (getattr(d, "extra", None) or {}).get("conditional_proof")
        if not cond or d.proof_is_current or d.theorem in names:
            continue
        nl = d.understood_display or d.understood or d.problem
        auto = domain_of(d.statement + "\n" + nl)
        m = meta.get(d.theorem) or {}
        out.append({"name": d.theorem, "title": d.title, "statement": re.sub(r"\s+", " ", d.statement)[:2000],
                    "nl": nl, "code": "", "workspace": d.workspace, "dossier": d.id, "t": d.updated,
                    "project_id": d.project_id, "project": projects.get(d.project_id, ""),
                    "domain": m.get("domain") or auto, "domain_auto": auto, "domain_manual": bool(m.get("domain")),
                    "tags": list(m.get("tags") or []), "status": "conditional",
                    "admitted": list(cond.get("admitted") or []), "model": "", "by_user": False,
                    "axioms": cond.get("axioms"), "uses": [], "used_by": []})
    return out


async def library_catalog(request):
    wb, ctx = W(request), ctx_of(request)
    meta = await asyncio.to_thread(wb.meta)
    items = await asyncio.to_thread(catalog, ctx, meta)
    return ok({"entries": items, "domains": list(DOMAINS)})


async def library_meta_patch(request):
    wb, ctx = W(request), ctx_of(request)
    name = request.match_info["name"][:200]
    data = await body(request)
    known = {e.name for e in ctx.library.entries} | {d.theorem for d in ctx.repo.list()}
    if name not in known:
        return error(404, "not_found")
    meta = await asyncio.to_thread(wb.meta)
    m = dict(meta.get(name) or {})
    if "domain" in data:
        dom = data.get("domain") or ""
        if dom and dom not in DOMAINS:
            return error(400, "bad_fields", "Champs refusés : {fields}.", fields="domain")
        m["domain"] = dom
    if "tags" in data:
        tags = data.get("tags")
        if not isinstance(tags, list) or not all(isinstance(t, str) and TAG_RE.match(t.strip()) for t in tags):
            return error(400, "bad_fields", "Champs refusés : {fields}.", fields="tags")
        m["tags"] = sorted({t.strip() for t in tags})[:30]
    meta[name] = m
    await asyncio.to_thread(wb.save_meta, meta)
    ctx.publish("library.updated", {"meta": name})
    return ok({"name": name, "meta": m})


async def library_catalog_export(request):
    wb, ctx = W(request), ctx_of(request)
    fmt = request.query.get("format", "md")
    only = request.query.get("name", "")
    items = await asyncio.to_thread(catalog, ctx, await asyncio.to_thread(wb.meta))
    if only:
        items = [i for i in items if i["name"] == only]
        if not items:
            return error(404, "not_found")
    if fmt == "json":
        text, ctype, ext = json.dumps(items, ensure_ascii=False, indent=1), "application/json", "json"
    elif fmt == "lean":
        from ...dossiers import closure
        lib = ctx.library
        entries = [lib.get(i["name"]) for i in items if lib.get(i["name"])]
        blocks = [f"-- {e.title}\n{e.code.strip()}\n" for e in closure(lib, entries)]
        text, ctype, ext = "import Mathlib\n\n" + "\n".join(blocks), "text/plain", "lean"
    else:
        lines = ["# " + msg("Bibliothèque de résultats")["text"], ""]
        for i in items:
            st = msg("vérifié par Lean")["text"] if i["status"] == "verified" else \
                msg("conditionnel (lemmes admis : {a})", a=", ".join(i["admitted"]) or "?")["text"]
            lines += [f"## {i['title'] or i['name']}", "", f"- `{i['name']}` — {st}",
                      f"- {i['domain']}" + (f" · {i['project']}" if i["project"] else "") +
                      (" · " + ", ".join(i["tags"]) if i["tags"] else ""), ""]
            if i["nl"]:
                lines += [i["nl"], ""]
            lines += ["```lean", i["statement"], "```", ""]
        text, ctype, ext = "\n".join(lines), "text/markdown", "md"
    name = (only or "bibliotheque") + "." + ext
    return web.Response(text=text, content_type=ctype, charset="utf-8",
                        headers={"Content-Disposition": f'attachment; filename="{re.sub(r"[^A-Za-z0-9_.-]", "_", name)}"'})


# ================================================================ glossary
async def glossary_uses(request):
    ctx = ctx_of(request)
    term = request.query.get("term", "").strip()[:80]
    if not term:
        return ok({"term": term, "dossiers": []})
    rx = re.compile(r"(?<![\w.])" + re.escape(term) + r"(?![\w])", re.U) if re.match(r"^[\w.'?!]+$", term) \
        else re.compile(re.escape(term))
    out = []
    for d in ctx.repo.list():
        hay = d.statement + "\n" + d.proof
        if hay.strip() and rx.search(hay):
            out.append({"id": d.id, "title": d.title, "project_id": d.project_id, "status": d.status,
                        "in": "proof" if rx.search(d.proof or "") else "statement"})
        if len(out) >= 30:
            break
    return ok({"term": term, "dossiers": out})


# ================================================================ demo mode
DEMO_SVG = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 180" width="320" height="180" '
            'font-family="sans-serif" font-size="11"><rect width="320" height="180" fill="#fff"/>'
            '<path d="M40 150H300M40 150V20" stroke="#333" fill="none"/>'
            '<path d="M40 150 L66 137 L92 128 L118 120 L144 113 L170 107 L196 100 L222 95 L248 89 L274 84 L300 79" '
            'stroke="#2c46ad" stroke-width="2" fill="none"/>'
            '<path d="M40 150 L66 139 L92 131 L118 124 L144 118 L170 112 L196 107 L222 102 L248 97 L274 93 L300 89" '
            'stroke="#b44a26" stroke-width="2" stroke-dasharray="5 3" fill="none"/>'
            '<text x="170" y="172" text-anchor="middle">x (0 … 1000)</text><text x="230" y="70" fill="#2c46ad">π(x)</text>'
            '<text x="230" y="118" fill="#b44a26">x / ln x</text></svg>')


def demo_answer(first: str) -> str | None:
    if "Translate the request into ONE short" in first:
        if "Petersen" in first:
            return "```sage\nG = graphs.PetersenGraph()\nprint(G.chromatic_number())\nG\n```"
        if "sin(x)/x" in first:
            return "```sage\nplot(sin(x)/x, (x, -10, 10))\n```"
        return "```sage\n# twin primes below 200\n[p for p in primes(200) if is_prime(p + 2)]\n```"
    if "Write one code cell" in first:
        return "```sage\n# twin primes below 200\n[p for p in primes(200) if is_prime(p + 2)]\n```"
    if "This cell failed" in first or "Cette cellule a échoué" in first:
        return ("Le nom utilisé n'existe pas dans Sage : la fonction s'appelle « factor ».\n\n"
                "```sage\nprint(factor(2^32 + 1))\n```")
    if "ÉTAPES MATHÉMATIQUES" in first or "MATHEMATICAL STEPS" in first:
        if "MATHEMATICAL STEPS" in first:
            return ("1. We look for the prime factors of $F_5 = 2^{32} + 1 = 4294967297$.\n"
                    "2. Euler's remark: every prime factor has the form $64k + 1$; $k = 10$ gives $641$, which "
                    "divides $F_5$.\n3. The quotient $6700417$ is prime.\n"
                    "4. Result: $F_5 = 641 \\cdot 6700417$.")
        return ("1. On cherche les facteurs premiers de $F_5 = 2^{32} + 1 = 4294967297$.\n"
                "2. Remarque d'Euler : tout facteur premier est de la forme $64k + 1$ ; $k = 10$ donne $641$, qui "
                "divise $F_5$.\n3. Le quotient $6700417$ est premier.\n"
                "4. Résultat : $F_5 = 641 \\cdot 6700417$.")
    nums = re.findall(r"^(\d+): (.*)$", first, re.M)
    if ("ligne par ligne" in first or "line by line" in first) and nums:
        # (numbered lines only: the guided reading of a Lean statement also says « ligne par ligne » and got an
        # empty answer in the demo, so no reading was ever shown there — S-AF)
        return "\n".join(f"{n}: Cette ligne calcule « {code.strip()[:40]} »." for n, code in nums if code.strip())
    if "Explain what this cell computes" in first:
        return ("The cell factors $2^{32}+1$, the fifth Fermat number $F_5$: $F_5 = 641 \\times 6700417$, so $F_5$ "
                "is not prime (Euler, 1732). This computation proves that this one number is composite; it says "
                "nothing about other Fermat numbers.")
    return None


SYNTAX_START_DELAY = 90.0


async def _syntax_cards_later(ctx) -> None:
    """S-AB: a while after the start (never during it), build the syntax cards of the installed Sage / Lean+Mathlib
    versions when they are missing or outdated (docs/CALCUL.md §3)."""
    import os
    if os.environ.get("MADALEAN_NO_SYNTAX_BUILD") == "1":      # the tests build their own cards
        return
    await asyncio.sleep(SYNTAX_START_DELAY)
    from ... import syntaxcards
    await syntaxcards.ensure_all(ctx)


async def seed_demo(ctx, wbench: Workbench) -> None:
    """Demo: a short Sage notebook (outputs recorded as if run, no kernel needed)."""
    from ...research.sagebridge import ExecResult
    projects = ctx.projects.list()
    if not projects:
        return
    pid = projects[0].id
    st = wbench.calc
    docs = await asyncio.to_thread(st.docs, pid)
    if any(d["cells"] for d in docs):
        return

    def out(*o):
        return list(o)
    await asyncio.to_thread(st.add, pid, "## Nombres de Fermat\nLe cinquième, $F_5 = 2^{32}+1$, n'est pas premier "
                            "(Euler, 1732).", kind="markdown")
    c1 = await asyncio.to_thread(st.add, pid, "F5 = 2^32 + 1\nfactor(F5)")
    up = await asyncio.to_thread(st.upstream_of, pid, DEFAULT_DOC, c1["id"])
    await asyncio.to_thread(st.record_run, pid, c1["id"], ExecResult(
        "ok", seconds=0.4, language="sage", sandbox="bwrap", execution_count=1, outputs=out(
            {"output_type": "execute_result", "execution_count": 1, "metadata": {},
             "data": {"text/plain": "641 * 6700417", "text/latex": "641 \\cdot 6700417"}})),
        "host", c1["code_hash"], upstream=up)
    c2 = await asyncio.to_thread(st.add, pid, "sqrt(2) * pi")
    up = await asyncio.to_thread(st.upstream_of, pid, DEFAULT_DOC, c2["id"])
    await asyncio.to_thread(st.record_run, pid, c2["id"], ExecResult(
        "ok", seconds=0.1, language="sage", sandbox="bwrap", execution_count=2, outputs=out(
            {"output_type": "execute_result", "execution_count": 2, "metadata": {},
             "data": {"text/plain": "sqrt(2)*pi", "text/latex": "\\sqrt{2} \\pi"}})),
        "host", c2["code_hash"], upstream=up, approx="4.44288293815837")
    c3 = await asyncio.to_thread(st.add, pid, "P = plot(prime_pi, 0, 1000, legend_label='π(x)')\n"
                                 "P += plot(x / log(x), 2, 1000, linestyle='--', legend_label='x / ln x')\nP")
    up = await asyncio.to_thread(st.upstream_of, pid, DEFAULT_DOC, c3["id"])
    await asyncio.to_thread(st.record_run, pid, c3["id"], ExecResult(
        "ok", seconds=1.2, language="sage", sandbox="bwrap", execution_count=3, outputs=out(
            {"output_type": "display_data", "metadata": {},
             "data": {"image/svg+xml": DEMO_SVG, "text/plain": "Graphics object consisting of 2 graphics primitives"}})),
        "host", c3["code_hash"], upstream=up)
    roots = ("[(1, 1), (a^3 + 1, 1), (a^3 + a + 1, 1), (a^3 + a^2 + 1, 1), (a^3 + a^2 + a + 1, 1), "
             "(a^2 + a, 1), (a^2 + a + 1, 1)]")
    c4 = await asyncio.to_thread(st.add, pid, "F.<a> = GF(16)\nR.<x> = F[]\n(x^5 + x^3 + x + 1).roots()")
    up = await asyncio.to_thread(st.upstream_of, pid, DEFAULT_DOC, c4["id"])
    await asyncio.to_thread(st.record_run, pid, c4["id"], ExecResult(          # a long formula (phones: scrolls)
        "ok", seconds=0.2, language="sage", sandbox="bwrap", execution_count=4, outputs=out(
            {"output_type": "execute_result", "execution_count": 4, "metadata": {},
             "data": {"text/plain": roots, "text/latex": "\\left[\\left(1, 1\\right), \\left(a^{3} + 1, 1\\right), "
                      "\\left(a^{3} + a + 1, 1\\right), \\left(a^{3} + a^{2} + 1, 1\\right), "
                      "\\left(a^{3} + a^{2} + a + 1, 1\\right), \\left(a^{2} + a, 1\\right), "
                      "\\left(a^{2} + a + 1, 1\\right)\\right]"}})),
        "host", c4["code_hash"], upstream=up)
    await asyncio.to_thread(st.add, pid, "[p for p in primes(200) if is_prime(p + 2)]", "", "assistant", kind="ask",
                            prompt="les nombres premiers jumeaux inférieurs à 200", model="fake:fake-assistant")
    await asyncio.to_thread(st.add, pid, "", kind="figure", figure={
        "v": 1, "title": "Cercle et tangente", "view": {"xmin": -5, "xmax": 5, "ymin": -3.5, "ymax": 3.5},
        "curves": [{"id": "c0", "expr": "sin(x)/x"}],
        "objects": [{"id": "o1", "name": "O", "kind": "point", "parents": [], "x": 0, "y": 0},
                    {"id": "o2", "name": "A", "kind": "point", "parents": [], "x": 2, "y": 1},
                    {"id": "o3", "name": "c", "kind": "circle_center_point", "parents": ["o1", "o2"]},
                    {"id": "o4", "name": "r", "kind": "distance", "parents": ["o1", "o2"]}]})


def _demo_brain(ctx) -> None:
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
    app[WB] = Workbench(ctx)
    if ctx.demo:
        async def startup(_app):
            _demo_brain(ctx)
            try:
                await seed_demo(ctx, app[WB])
            except Exception:  # noqa: BLE001
                log.exception("demo seed (workbench) failed")
        app.on_startup.append(startup)
    a = app.router
    _register_calcul(a)

    async def reaper_start(_app):
        ctx.spawn(_reaper(ctx, app[WB]))
        if not ctx.demo:
            ctx.spawn(_syntax_cards_later(ctx))
    app.on_startup.append(reaper_start)
    from ... import syntaxcards
    syntaxcards.configure(ctx.paths.cache)
    syntaxcards.ON_SAGE_BUILT.append(lambda v: _revalidate_recipes(app[WB], v))
    a.add_get("/api/library/catalog", library_catalog)
    a.add_get("/api/library/catalog/export", library_catalog_export)
    a.add_patch("/api/library/meta/{name}", library_meta_patch)
    a.add_get("/api/glossary/uses", glossary_uses)
