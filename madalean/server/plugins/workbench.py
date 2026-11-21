"""Session S-M plugin: the « Calcul » compute workspace, the organised library of proven results, and the glossary's
links to the user's dossiers. Reference: docs/API.md §« Calcul, library catalogue, glossary » and
docs/RESEARCH_WORKSHOP.md §« Calcul ».

Calcul
- `GET    /api/calcul/{pid}`                          worksheet {cells, rev} + kernel status (sage/python available,
                                                       sandbox, auto, remote_allowed, local)
- `POST   /api/calcul/{pid}/cells {code, language, after?}`           a cell typed by the user (origin « user »)
- `PATCH  /api/calcul/{pid}/cells/{cid} {code?, language?, note?}`     edit (an assistant cell loses its approval)
- `DELETE /api/calcul/{pid}/cells/{cid}` · `POST …/cells/{cid}/restore` · `POST …/cells/{cid}/move {to}`
- `POST   /api/calcul/{pid}/cells/{cid}/approve {code_hash}`           approve an assistant cell (exact code)
- `POST   /api/calcul/{pid}/cells/{cid}/run {timeout?}`               run in the sandboxed offline kernel; output
                                                                       streamed as `calcul.output`, run returned
- `POST   /api/calcul/{pid}/assist {action: write|fix|explain, cell_id?, prompt?, language?}`
- `POST   /api/calcul/{pid}/cells/{cid}/to {target: conjecture|note|dossier|article, text?, title?}`
- `GET    /api/calcul/assets/{aid}`                   a plot (PNG / sanitised SVG), restrictive CSP
Library catalogue
- `GET    /api/library/catalog`                        entries with domain, project, tags, status, model, uses/used-by
                                                       (+ conditional results of proof plans)
- `PATCH  /api/library/meta/{name} {domain?, tags?}`  manual classification (kept in <config>/library-meta.json)
- `GET    /api/library/catalog/export?format=md|json|lean&name=`
Glossary
- `GET    /api/glossary/uses?term=`                   dossiers whose current statement or proof uses the term"""
from __future__ import annotations

import asyncio
import json
import re
import time

from aiohttp import web

from ... import config
from ...i18n import language, msg
from ...logs import get
from ...research.calcul import (CALC_PREAMBLE, CalcError, CalcStore, LANGS, assist_messages, extract_code,
                                output_text)
from ..common import body, ctx_of, error, ok, valid_id
from ..helpers import complete_once

log = get("workbench")
WB = web.AppKey("workbench", object)
DOMAINS = ("linear_algebra", "analysis", "combinatorics", "number_theory", "algebra", "geometry", "logic", "other")
TAG_RE = re.compile(r"^[\w .+-]{1,40}$", re.U)


class Workbench:
    def __init__(self, ctx):
        self.ctx = ctx
        self.calc = CalcStore(ctx.paths.config / "research" / "calcul")
        self.meta_path = ctx.paths.config / "library-meta.json"
        self.locks: dict[str, asyncio.Lock] = {}
        self._bridge = None

    def bridge(self):
        rs = getattr(self.ctx, "research", None)          # the research workshop's bridge (one kernel manager)
        if rs is not None:
            return rs.bridge
        if self._bridge is None:
            from ...research.sagebridge import SageBridge
            self._bridge = SageBridge(self.ctx)
        return self._bridge

    def lock(self, pid: str) -> asyncio.Lock:
        return self.locks.setdefault(pid, asyncio.Lock())

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


def _calc_fail(e: CalcError) -> web.Response:
    return web.json_response({"error": e.kind}, status=e.status)


def _project(request) -> str:
    pid = valid_id(request.match_info["pid"])
    if ctx_of(request).projects.get(pid) is None:
        raise web.HTTPNotFound(text='{"error":"not_found"}', content_type="application/json")
    return pid


def _exec_allowed(request) -> web.Response | None:
    if not request["local"] and not getattr(ctx_of(request).settings, "experiments_remote", False):
        return error(403, "experiments_host_only", "Les expériences exécutent du code sur l'ordinateur hôte : "
                                                   "autorisées seulement depuis l'hôte (réglage).")
    return None


# ================================================================ Calcul
async def calc_get(request):
    wb, ctx = W(request), ctx_of(request)
    pid = _project(request)
    sheet = await asyncio.to_thread(wb.calc.load, pid)
    br = wb.bridge()
    try:
        avail = await asyncio.to_thread(br.available)
    except Exception:  # noqa: BLE001
        avail = {}
    return ok({"sheet": {k: v for k, v in sheet.items() if k != "trash"},
               "trash": [{"id": c["id"], "code": c["code"][:200]} for c in sheet.get("trash", [])][-5:],
               "status": {"available": avail, "sandbox": br.sandbox_kind, "auto": bool(ctx.settings.experiments_auto),
                          "remote_allowed": bool(ctx.settings.experiments_remote), "local": bool(request["local"]),
                          "running": wb.lock(pid).locked()}})


async def calc_add(request):
    wb, ctx = W(request), ctx_of(request)
    pid = _project(request)
    data = await body(request)
    try:
        c = await asyncio.to_thread(wb.calc.add, pid, str(data.get("code", "")), str(data.get("language", "sage")),
                                    "user", after=str(data.get("after", "") or ""))
    except CalcError as e:
        return _calc_fail(e)
    ctx.publish("calcul.updated", {"project_id": pid, "cell": c})
    return ok({"cell": c}, status=201)


async def calc_edit(request):
    wb, ctx = W(request), ctx_of(request)
    pid = _project(request)
    data = await body(request)
    bad = [k for k in data if k not in ("code", "language", "note")]
    if bad:
        return error(400, "bad_fields", "Champs refusés : {fields}.", fields=", ".join(bad))
    try:
        c = await asyncio.to_thread(wb.calc.edit, pid, request.match_info["cid"],
                                    code=str(data["code"]) if "code" in data else None,
                                    language=str(data["language"]) if "language" in data else None,
                                    note=str(data["note"]) if "note" in data else None, by="user")
    except CalcError as e:
        return _calc_fail(e)
    ctx.publish("calcul.updated", {"project_id": pid, "cell": c})
    return ok({"cell": c})


async def calc_delete(request):
    wb, ctx = W(request), ctx_of(request)
    pid = _project(request)
    try:
        c = await asyncio.to_thread(wb.calc.delete, pid, request.match_info["cid"])
    except CalcError as e:
        return _calc_fail(e)
    ctx.publish("calcul.updated", {"project_id": pid, "removed": c["id"]})
    return ok({"removed": c["id"]})


async def calc_restore(request):
    wb, ctx = W(request), ctx_of(request)
    pid = _project(request)
    try:
        c = await asyncio.to_thread(wb.calc.restore, pid, request.match_info["cid"])
    except CalcError as e:
        return _calc_fail(e)
    ctx.publish("calcul.updated", {"project_id": pid, "cell": c})
    return ok({"cell": c})


async def calc_move(request):
    wb = W(request)
    pid = _project(request)
    data = await body(request)
    try:
        sheet = await asyncio.to_thread(wb.calc.move, pid, request.match_info["cid"], int(data.get("to", 0)))
    except (CalcError, ValueError, TypeError) as e:
        return _calc_fail(e) if isinstance(e, CalcError) else error(400, "bad_fields", "Champs refusés : {fields}.",
                                                                    fields="to")
    ctx_of(request).publish("calcul.updated", {"project_id": pid})
    return ok({"order": [c["id"] for c in sheet["cells"]]})


async def calc_approve(request):
    if (r := _exec_allowed(request)) is not None:
        return r
    wb, ctx = W(request), ctx_of(request)
    pid = _project(request)
    data = await body(request)
    try:
        c = await asyncio.to_thread(wb.calc.approve, pid, request.match_info["cid"], str(data.get("code_hash", "")),
                                    device_of(request))
    except CalcError as e:
        return _calc_fail(e)
    ctx.publish("calcul.updated", {"project_id": pid, "cell": c})
    return ok({"cell": c})


async def calc_run(request):
    if (r := _exec_allowed(request)) is not None:
        return r
    wb, ctx = W(request), ctx_of(request)
    pid = _project(request)
    cid = request.match_info["cid"]
    data = await body(request)
    sheet = await asyncio.to_thread(wb.calc.load, pid)
    c = next((x for x in sheet["cells"] if x["id"] == cid), None)
    if c is None:
        return error(404, "not_found")
    if not wb.calc.may_run(c, bool(ctx.settings.experiments_auto)):
        return error(403, "not_approved", "Ce code a été écrit par l'assistant : relisez-le et approuvez-le d'abord.")
    if wb.lock(pid).locked():
        return error(409, "busy", "Une opération est en cours : arrêtez-la d'abord (Échap).")
    timeout = max(1.0, min(float(data.get("timeout") or 60), 600.0))
    code, h, lang = c["code"], c["code_hash"], c["language"]

    def on_output(kind: str, text: str) -> None:
        ctx.publish("calcul.output", {"project_id": pid, "cell_id": cid, "kind": kind, "text": text[:20000]})
    async with wb.lock(pid):
        ctx.publish("calcul.running", {"project_id": pid, "cell_id": cid})
        res = await wb.bridge().run(f"calcul:{pid}", lang, code, timeout=timeout, on_output=on_output,
                                    workdir=f"calcul-{pid}", preamble=CALC_PREAMBLE)
        run = await asyncio.to_thread(wb.calc.record_run, pid, cid, res, device_of(request), h)
    ctx.publish("calcul.updated", {"project_id": pid, "cell_id": cid, "run": run})
    return ok({"run": run})


async def calc_interrupt(request):
    wb = W(request)
    pid = _project(request)
    br = wb.bridge()
    k = getattr(br, "kernels", {}).get(f"calcul:{pid}")
    if k:
        await br.interrupt(k["id"])
    return ok({"interrupted": bool(k)})


async def calc_assist(request):
    wb, ctx = W(request), ctx_of(request)
    pid = _project(request)
    data = await body(request)
    action = str(data.get("action", "write"))
    if action not in ("write", "fix", "explain"):
        return error(400, "bad_fields", "Champs refusés : {fields}.", fields="action")
    sheet = await asyncio.to_thread(wb.calc.load, pid)
    cell = next((x for x in sheet["cells"] if x["id"] == str(data.get("cell_id", ""))), None)
    if action != "write" and cell is None:
        return error(404, "not_found")
    lang_ = cell["language"] if cell else (str(data.get("language", "sage")) if data.get("language") in LANGS
                                           else "sage")
    last = (cell.get("runs") or [{}])[-1] if cell else {}
    msgs = assist_messages(action, lang_, language(), str(data.get("prompt", "")), cell["code"] if cell else "",
                           (last.get("error") or last.get("stderr") or "") if last else "",
                           output_text(last) if last else "")
    try:
        c = await complete_once(ctx, "assistant", msgs, ctx.settings.mode, owner=f"calcul-{pid}", max_tokens=3000,
                                temperature=0.2)
    except Exception as e:  # noqa: BLE001
        return error(503, "no_model", "Aucun modèle disponible ({err}).", err=str(e)[:200])
    model = getattr(c.model, "key", "") or ""
    if action == "explain":
        return ok({"text": c.text, "model": model})
    code = extract_code(c.text)
    if not code:
        return error(502, "no_code", "Le modèle n'a pas proposé de code ; reformulez la demande.")
    try:
        if action == "write":
            new = await asyncio.to_thread(wb.calc.add, pid, code, lang_, "assistant",
                                          after=str(data.get("after", "") or ""), note=str(data.get("prompt", "")),
                                          model=model)
        else:
            new = await asyncio.to_thread(wb.calc.edit, pid, cell["id"], code=code, by="assistant", model=model)
    except CalcError as e:
        return _calc_fail(e)
    ctx.publish("calcul.updated", {"project_id": pid, "cell": new})
    return ok({"cell": new, "model": model, "approval_required": not ctx.settings.experiments_auto}, status=201)


def _fact_text(cell: dict, run: dict) -> str:
    out = output_text(run)
    return f"```{cell['language']}\n{cell['code']}\n```\n\n" + (f"```\n{out[:6000]}\n```\n" if out else "")


async def calc_to(request):
    """One-click actions on a result: → conjecture, → note, → Lean dossier, → article (table / formula block)."""
    wb, ctx = W(request), ctx_of(request)
    pid = _project(request)
    cid = request.match_info["cid"]
    data = await body(request)
    target = str(data.get("target", ""))
    sheet = await asyncio.to_thread(wb.calc.load, pid)
    cell = next((x for x in sheet["cells"] if x["id"] == cid), None)
    if cell is None:
        return error(404, "not_found")
    run = (cell.get("runs") or [{}])[-1]
    text = str(data.get("text", "")).strip()[:20000]
    title = str(data.get("title", "")).strip()[:200]
    origin = {"kind": "calcul", "project_id": pid, "cell_id": cid, "run_id": run.get("id", "")}
    rs = getattr(ctx, "research", None)
    if target == "conjecture":
        if rs is None or not text:
            return error(400, "bad_fields", "Champs refusés : {fields}.", fields="text")
        from ...research.conjectures import ConjectureError, public as conj_public
        try:
            d = await rs.workshop.create(pid, text, motivation=_fact_text(cell, run), title=title, origin=origin,
                                         device=device_of(request))
        except ConjectureError as e:
            return web.json_response({"error": e.kind}, status=getattr(e, "status", 400))
        return ok({"target": "conjecture", "conjecture": conj_public(d)}, status=201)
    if target == "note":
        if rs is None:
            return error(503, "unavailable")
        from ...research.notes import NoteError
        md = (text + "\n\n" if text else "") + _fact_text(cell, run)
        for r in run.get("rich", []):
            if r.get("mime") == "text/latex":
                md += "\n" + r["data"] + "\n"
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
        from ...research import article as art_mod
        latex = [r["data"] for r in run.get("rich", []) if r.get("mime") == "text/latex"]
        if text:
            body_ = text
        elif latex:
            body_ = "\n".join(latex)
        else:
            out = (run.get("stdout", "") + "\n" + run.get("result", "")).strip()
            body_ = "```\n" + out[:20000] + "\n```" if out else ""
        if not body_:
            return error(409, "no_output", "Exécutez d'abord la cellule.")
        art = await asyncio.to_thread(art_mod.load, ctx, pid)
        b = art_mod.new_block("prose", title or msg("Résultat de calcul")["text"], body_, "user")
        b["calcul_origin"] = origin
        art["blocks"].append(b)
        await asyncio.to_thread(art_mod.save, ctx, pid, art)
        ctx.publish("article.updated", {"project_id": pid})
        return ok({"target": "article", "block": b}, status=201)
    return error(400, "bad_fields", "Champs refusés : {fields}.", fields="target")


async def calc_asset(request):
    wb = W(request)
    found = wb.calc.asset_path(request.match_info["aid"])
    if found is None:
        return error(404, "not_found")
    path, mime = found
    return web.FileResponse(path, headers={
        "Content-Type": mime, "X-Content-Type-Options": "nosniff", "Cache-Control": "private, max-age=86400",
        "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; img-src data:; sandbox"})


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
    if "Write one code cell" in first:
        return "```sage\n# twin primes below 200\n[p for p in primes(200) if is_prime(p + 2)]\n```"
    if "This cell failed" in first:
        return "```sage\nprint(factor(2^32 + 1))\n```"
    if "Explain what this cell computes" in first:
        return ("The cell factors $2^{32}+1$, the fifth Fermat number $F_5$: $F_5 = 641 \\times 6700417$, so $F_5$ "
                "is not prime (Euler, 1732). This computation proves that this one number is composite; it says "
                "nothing about other Fermat numbers.")
    return None


async def seed_demo(ctx, wbench: Workbench) -> None:
    from ...research.sagebridge import ExecResult
    projects = ctx.projects.list()
    if not projects:
        return
    pid = projects[0].id
    st = wbench.calc
    if st.load(pid)["cells"]:
        return
    c1 = st.add(pid, "F5 = 2^32 + 1\nprint(factor(F5))\ntex(factor(F5))", language="sage", origin="user")
    st.record_run(pid, c1["id"], ExecResult("ok", stdout="641 * 6700417\n", seconds=0.4, language="sage",
                                            sandbox="bwrap", rich=[{"mime": "text/latex",
                                                                    "data": "$$641 \\cdot 6700417$$"}]),
                  "host", c1["code_hash"])
    c2 = st.add(pid, "P = plot(prime_pi, 0, 1000, legend_label='π(x)')\nP += plot(x / log(x), 2, 1000, "
                     "linestyle='--', legend_label='x / ln x')\nP.show()", language="sage", origin="user")
    st.record_run(pid, c2["id"], ExecResult("ok", seconds=1.2, language="sage", sandbox="bwrap",
                                            rich=[{"mime": "image/svg+xml", "data": DEMO_SVG}]), "host",
                  c2["code_hash"])
    st.add(pid, "# twin primes below 200\n[p for p in primes(200) if is_prime(p + 2)]", language="sage", origin="assistant",
           note="les nombres premiers jumeaux inférieurs à 200", model="fake:fake-assistant")


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
    a.add_get("/api/calcul/assets/{aid}", calc_asset)
    a.add_get("/api/calcul/{pid}", calc_get)
    a.add_post("/api/calcul/{pid}/cells", calc_add)
    a.add_patch("/api/calcul/{pid}/cells/{cid}", calc_edit)
    a.add_delete("/api/calcul/{pid}/cells/{cid}", calc_delete)
    a.add_post("/api/calcul/{pid}/cells/{cid}/restore", calc_restore)
    a.add_post("/api/calcul/{pid}/cells/{cid}/move", calc_move)
    a.add_post("/api/calcul/{pid}/cells/{cid}/approve", calc_approve)
    a.add_post("/api/calcul/{pid}/cells/{cid}/run", calc_run)
    a.add_post("/api/calcul/{pid}/cells/{cid}/to", calc_to)
    a.add_post("/api/calcul/{pid}/interrupt", calc_interrupt)
    a.add_post("/api/calcul/{pid}/assist", calc_assist)
    a.add_get("/api/library/catalog", library_catalog)
    a.add_get("/api/library/catalog/export", library_catalog_export)
    a.add_patch("/api/library/meta/{name}", library_meta_patch)
    a.add_get("/api/glossary/uses", glossary_uses)
