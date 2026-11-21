"""Session S-R plugin: the article's LaTeX project (docs/ARTICLE.md §5). Routes under
`/api/research/projects/{pid}/texproject…`; authentication, Origin checks and the remote listener's token are
applied by the app's middlewares like every other route."""
from __future__ import annotations

import asyncio
import json
import re
import time
import uuid

from aiohttp import web

from ... import texio
from ...i18n import msg
from ...logs import get
from ...research import overleaf, texbuild, texproject as tp
from ..common import CTX, body, error, ok, valid_id
from ..helpers import complete_once

log = get("article_editor")
TASKS = web.AppKey("article_editor_tasks", dict)
MESSAGES = {
    "conflict": "Ce fichier a changé ailleurs (autre appareil, suggestion acceptée ou import).",
    "bad_path": "Chemin de fichier refusé.",
    "too_large": "Fichier trop volumineux.",
    "bad_template": "Modèle inconnu.",
    "unsafe_tex": "Construction LaTeX refusée pour la sécurité ({found}).",
    "anchor_not_found": "Le texte visé par la suggestion n'existe plus.",
    "stale": "Le texte visé par la suggestion a changé : elle ne peut plus s'appliquer.",
    "decided": "Cette suggestion a déjà été traitée.",
    "bad_type": "Format d'image refusé (PNG, JPEG ou PDF).",
    "bad_archive": "Archive illisible ou trop grande.",
    "no_main": "L'archive ne contient pas de main.tex à sa racine.",
    "bad_encoding": "Fichier qui n'est pas en UTF-8 : {file}.",
    "local_mode": "Mode local : rien n'est téléchargé (changez de mode pour télécharger les fichiers TeX).",
    "busy": "Une opération est déjà en cours sur cet élément.",
    "not_found": "Introuvable.",
    "exists": "Le projet LaTeX existe déjà.",
    "bad_fields": "Champs refusés : {fields}.",
}


def _ctx(request):
    return request.app[CTX]


def _pid(request) -> str:
    pid = valid_id(request.match_info["pid"])
    if _ctx(request).projects.get(pid) is None:
        raise web.HTTPNotFound(text='{"error":"not_found"}', content_type="application/json")
    return pid


def _dev(request) -> str:
    dev = request.get("device")
    return dev.id if dev is not None else "host"


def _fail(e: tp.TexProjectError) -> web.Response:
    key = MESSAGES.get(e.kind, "")
    params = {k: v for k, v in e.info.items() if isinstance(v, (str, int))}
    for k in re.findall(r"{(\w+)}", key):
        params.setdefault(k, "")
    data = {"error": e.kind, **params}
    if key:
        data["message"] = msg(key, **params)
    return web.json_response(data, status=e.status)


def _guard(handler):
    async def wrapped(request):
        try:
            return await handler(request)
        except tp.TexProjectError as e:
            return _fail(e)
    wrapped.__name__ = handler.__name__
    return wrapped


def _publish(request, pid: str, changed: dict[str, str], by: str = "") -> None:
    ctx = _ctx(request)
    for path, text in changed.items():
        ctx.publish("texproject.file", {"project": pid, "path": path, "hash": tp.text_hash(text) if text else "",
                                        "deleted": not text, "by": by})


def _mode(ctx, pid: str, data: dict | None = None) -> str:
    from ...research.fetch import effective_mode
    mode = effective_mode(ctx, ctx.projects.get(pid))
    if data and data.get("mode") in ("local", "auto", "online") and mode != "local":
        mode = data["mode"]
    return mode


# ================================================================ project
def snapshot_state(ctx, pid: str) -> dict:
    files = tp.read_files(ctx, pid)
    s = tp.read_settings(ctx, pid)
    order = tp.section_paths(files.get("main.tex", ""))
    heads, labels, cites = tp.outline(files, order)
    keys = []
    for k, it in tp._keys(ctx, pid).items():
        a = (it.get("author") or [{}])[0] if isinstance(it.get("author"), list) else {}
        year = ((it.get("issued") or {}).get("date-parts") or [[None]])[0][0]
        keys.append({"key": k, "title": str(it.get("title", ""))[:200], "author": a.get("family") or a.get("literal")
                     or "", "year": year})
    links = texbuild.linked_dossiers(files)
    states = texbuild.dossier_states(ctx, {d for d, _p, _l in links})
    dossiers = [{"id": d.id, "title": d.title, "status": ("verified" if d.proof_is_current else
                                                          "conditional" if (d.extra or {}).get("conditional_proof")
                                                          else "unverified")}
                for d in ctx.repo.list(pid) if not d.archived]
    last = texbuild.last_result(ctx, pid)
    lock_ = {}
    try:
        lock_ = json.loads((tp.root(ctx, pid) / "madalean.lock").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        pass
    return {"settings": s, "files": [{"path": p, "text": t, "hash": tp.text_hash(t)} for p, t in files.items()],
            "order": order, "outline": heads, "labels": labels, "cites": cites, "keys": keys,
            "links": [{"dossier": d, "path": p, "line": ln} for d, p, ln in links], "states": states,
            "dossiers": dossiers, "figures": tp.figures(ctx, pid),
            "templates": [{"id": k, "fr": v["fr"], "en": v["en"], "class": v["class"]} for k, v in tp.TEMPLATES.items()],
            "fonts": list(tp.FONTS), "lock": lock_, "last": last and {k: last.get(k) for k in
                                                                     ("ok", "hash", "pdf", "t", "engine", "seconds")},
            "suggestions": tp.list_suggestions(ctx, pid, "pending")}


@_guard
async def get_project(request):
    ctx, pid = _ctx(request), _pid(request)
    created = await asyncio.to_thread(tp.ensure, ctx, pid)
    st = await asyncio.to_thread(snapshot_state, ctx, pid)
    st["created"] = created
    return ok(st)


@_guard
async def new_project(request):
    """POST {template, title?, lang?} — only when no project exists yet (gallery on an empty article)."""
    ctx, pid = _ctx(request), _pid(request)
    data = await body(request)
    tpl = str(data.get("template", "amsart"))
    if tpl not in tp.TEMPLATES:
        raise tp.TexProjectError("bad_template")
    p = ctx.projects.get(pid)
    await asyncio.to_thread(tp.create_new, ctx, pid, tpl, str(data.get("title") or p.title)[:300],
                            "en" if data.get("lang") == "en" else "fr")
    return ok(await asyncio.to_thread(snapshot_state, ctx, pid), status=201)


@_guard
async def save_file(request):
    ctx, pid = _ctx(request), _pid(request)
    data = await body(request)
    path, text, base = str(data.get("path", "")), data.get("text"), str(data.get("base", ""))
    if not isinstance(text, str) or not tp.valid_path(path) or path.startswith("figures/"):
        raise tp.TexProjectError("bad_path")
    with tp.lock(pid):
        cur = tp.read_files(ctx, pid)
        if path in cur and base and tp.text_hash(cur[path]) != base:
            return web.json_response({"error": "conflict", "message": msg(MESSAGES["conflict"]),
                                      "current": {"path": path, "text": cur[path], "hash": tp.text_hash(cur[path])}},
                                     status=409)
        if cur.get(path) == text:
            return ok({"path": path, "hash": tp.text_hash(text), "unchanged": True})
        if path == "main.tex":
            # managed regions stay what the settings generate (edited through the drawer)
            s = tp.read_settings(ctx, pid)
            if s["madalean"].get("preamble") == "managed":
                text = tp.replace_region(text, "preamble", tp.gen_preamble(s))
            text = tp.replace_region(text, "front", tp.gen_front(s))
        tp.snapshot(ctx, pid, "autosave", auto=True, by=_dev(request))
        h = tp.write_file(ctx, pid, path, text)
    _publish(request, pid, {path: text}, _dev(request))
    return ok({"path": path, "hash": h, "text": text if path == "main.tex" else None})


@_guard
async def delete_section(request):
    ctx, pid = _ctx(request), _pid(request)
    path = request.query.get("path", "")
    if not tp.SECTION_PATH.match(path):
        raise tp.TexProjectError("bad_path")
    with tp.lock(pid):
        tp.snapshot(ctx, pid, f"delete {path}", auto=False, by=_dev(request))
        main = tp.read_files(ctx, pid).get("main.tex", "")
        order = [p for p in tp.section_paths(main) if p != path]
        main = tp.replace_region(main, "sections", tp.gen_sections(order))
        tp.write_file(ctx, pid, "main.tex", main)
        tp.delete_file(ctx, pid, path)
    _publish(request, pid, {"main.tex": main, path: ""}, _dev(request))
    return ok({"order": order, "undo": "versions"})


@_guard
async def add_section(request):
    ctx, pid = _ctx(request), _pid(request)
    data = await body(request)
    title = str(data.get("title", "")).strip()[:200] or "Section"
    after = str(data.get("after", ""))
    with tp.lock(pid):
        files = tp.read_files(ctx, pid)
        main = files.get("main.tex", "")
        order = tp.section_paths(main)
        name = f"sections/{len(order) + 1:02d}-{tp.slugify(title, 30)}.tex"
        while name in files:
            name = name[:-4] + "-" + uuid.uuid4().hex[:4] + ".tex"
        text = tp.region_text(tp.new_id(), "section", tp.heading_line(
            title if re.search(r"\\[A-Za-z]", title) else texio.escape_plain(title)) + "\n")
        idx = order.index(after) + 1 if after in order else len(order)
        order.insert(idx, name)
        tp.write_file(ctx, pid, name, text)
        main = tp.replace_region(main, "sections", tp.gen_sections(order))
        tp.write_file(ctx, pid, "main.tex", main)
    _publish(request, pid, {name: text, "main.tex": main}, _dev(request))
    return ok({"path": name, "text": text, "hash": tp.text_hash(text), "order": order}, status=201)


@_guard
async def set_order(request):
    ctx, pid = _ctx(request), _pid(request)
    data = await body(request)
    new = data.get("sections")
    with tp.lock(pid):
        main = tp.read_files(ctx, pid).get("main.tex", "")
        if not isinstance(new, list) or sorted(new) != sorted(tp.section_paths(main)):
            return error(400, "bad_fields", MESSAGES["bad_fields"], fields="sections")
        main = tp.replace_region(main, "sections", tp.gen_sections(new))
        tp.write_file(ctx, pid, "main.tex", main)
    _publish(request, pid, {"main.tex": main}, _dev(request))
    return ok({"order": new})


def _merge(dst: dict, src: dict) -> None:
    for k, v in src.items():
        if isinstance(v, dict) and isinstance(dst.get(k), dict) and k != "macros":
            _merge(dst[k], v)
        else:
            dst[k] = v


@_guard
async def patch_settings(request):
    ctx, pid = _ctx(request), _pid(request)
    data = await body(request)
    with tp.lock(pid):
        s = tp.read_settings(ctx, pid)
        unknown = [k for k in data if k not in s]
        if unknown:
            return error(400, "bad_fields", MESSAGES["bad_fields"], fields=", ".join(unknown))
        new = json.loads(json.dumps(s))
        _merge(new, data)
        new = tp.normalize_settings(new)
        bad = tp.validate_settings(new)
        if bad:
            return error(400, "bad_fields", MESSAGES["bad_fields"], fields=", ".join(bad))
        changed = tp.apply_settings(ctx, pid, new)
    _publish(request, pid, changed, _dev(request))
    return ok({"settings": new, "files": [{"path": p, "text": t, "hash": tp.text_hash(t)} for p, t in changed.items()]})


@_guard
async def set_template(request):
    ctx, pid = _ctx(request), _pid(request)
    data = await body(request)
    s = await asyncio.to_thread(tp.change_template, ctx, pid, str(data.get("template", "")))
    main = tp.read_files(ctx, pid)["main.tex"]
    _publish(request, pid, {"main.tex": main}, _dev(request))
    return ok({"settings": s, "files": [{"path": "main.tex", "text": main, "hash": tp.text_hash(main)}]})


# ================================================================ compile, PDF, SyncTeX, packages
@_guard
async def compile_(request):
    ctx, pid = _ctx(request), _pid(request)
    data = await body(request)
    online = bool(data.get("fetch"))
    if online and _mode(ctx, pid, data) == "local":
        raise tp.TexProjectError("local_mode", 409)
    await asyncio.to_thread(tp.ensure, ctx, pid)
    res = await texbuild.compile_project(ctx, pid, online=online, force=bool(data.get("force")))
    res = {**res, "pdf": (f"/api/research/projects/{pid}/texproject/pdf?h={res['pdf']}" if res.get("pdf") else None)}
    ctx.publish("texproject.compiled", {"project": pid, "ok": res["ok"], "hash": res.get("hash"),
                                        "by": _dev(request)})
    return ok(res)


@_guard
async def get_pdf(request):
    ctx, pid = _ctx(request), _pid(request)
    p = texbuild.pdf_path(ctx, pid)
    if p is None:
        return error(404, "not_found")
    return web.FileResponse(p, headers={"Content-Type": "application/pdf", "Cache-Control": "no-store",
                                        "Content-Security-Policy": "default-src 'none'; sandbox",
                                        "X-Content-Type-Options": "nosniff"})


@_guard
async def synctex(request):
    ctx, pid = _ctx(request), _pid(request)
    q = request.query
    try:
        if "path" in q:
            if not tp.valid_path(q["path"]):
                raise tp.TexProjectError("bad_path")
            r = await asyncio.to_thread(texbuild.forward, ctx, pid, q["path"], int(q.get("line", "1")))
        else:
            r = await asyncio.to_thread(texbuild.inverse, ctx, pid, int(q["page"]), float(q["x"]), float(q["y"]))
    except (KeyError, ValueError):
        return error(400, "bad_fields", MESSAGES["bad_fields"], fields="query")
    return ok({"result": r})


@_guard
async def packages(request):
    ctx, pid = _ctx(request), _pid(request)
    files = await asyncio.to_thread(tp.read_files, ctx, pid)
    s = await asyncio.to_thread(tp.read_settings, ctx, pid)
    a = await asyncio.to_thread(texbuild.analyse, files, s)
    await asyncio.to_thread(texbuild.write_lock, ctx, pid, a)
    return ok(a)


# ================================================================ history
@_guard
async def list_versions(request):
    ctx, pid = _ctx(request), _pid(request)
    return ok({"versions": await asyncio.to_thread(tp.versions, ctx, pid)})


@_guard
async def make_version(request):
    ctx, pid = _ctx(request), _pid(request)
    data = await body(request)
    v = await asyncio.to_thread(tp.snapshot, ctx, pid, str(data.get("label", ""))[:120] or "version", False,
                                _dev(request))
    return ok({"version": v and {k: v[k] for k in ("id", "t", "label", "auto")}}, status=201)


@_guard
async def version_file(request):
    ctx, pid = _ctx(request), _pid(request)
    text = await asyncio.to_thread(tp.version_file, ctx, pid, valid_id(request.match_info["vid"]),
                                   request.query.get("path", "main.tex"))
    return ok({"text": text})


@_guard
async def restore_version(request):
    ctx, pid = _ctx(request), _pid(request)
    changed = await asyncio.to_thread(tp.restore_version, ctx, pid, valid_id(request.match_info["vid"]),
                                      _dev(request))
    _publish(request, pid, changed, _dev(request))
    return ok({"changed": sorted(changed)})


# ================================================================ suggestions
def _pub_sug(request, pid: str, s: dict) -> None:
    _ctx(request).publish("article.suggestion", {"project": pid, "suggestion": s})


@_guard
async def list_sugs(request):
    ctx, pid = _ctx(request), _pid(request)
    return ok({"suggestions": await asyncio.to_thread(tp.list_suggestions, ctx, pid,
                                                      request.query.get("state", ""))})


@_guard
async def add_sug(request):
    ctx, pid = _ctx(request), _pid(request)
    data = await body(request)
    try:
        s = await asyncio.to_thread(lambda: tp.add_suggestion(
            ctx, pid, find=str(data.get("find", "")), replace=str(data.get("replace", "")),
            block_id=str(data.get("block_id", "")), path=str(data.get("path", "")),
            at=str(data.get("at", "replace")), occurrence=int(data.get("occurrence", 0) or 0),
            kind=str(data.get("kind", "rewrite")), origin="user" if data.get("origin") == "user" else "research"
            if data.get("origin") == "research" else "assistant", rationale=str(data.get("rationale", "")),
            model=str(data.get("model", ""))))
    except (TypeError, ValueError):
        return error(400, "bad_fields", MESSAGES["bad_fields"], fields="occurrence")
    _pub_sug(request, pid, s)
    return ok({"suggestion": s}, status=201)


@_guard
async def accept_sug(request):
    ctx, pid = _ctx(request), _pid(request)
    data = await body(request)
    s, changed = await asyncio.to_thread(tp.accept_suggestion, ctx, pid, valid_id(request.match_info["sid"]),
                                         _dev(request), bool(data.get("applied")))
    _publish(request, pid, changed, _dev(request))
    _pub_sug(request, pid, s)
    return ok({"suggestion": s, "files": [{"path": p, "text": t, "hash": tp.text_hash(t)} for p, t in changed.items()]})


@_guard
async def reject_sug(request):
    ctx, pid = _ctx(request), _pid(request)
    s = await asyncio.to_thread(tp.reject_suggestion, ctx, pid, valid_id(request.match_info["sid"]), _dev(request))
    _pub_sug(request, pid, s)
    return ok({"suggestion": s})


# ================================================================ assistant (suggestions only)
ACTIONS = {
    "rewrite": "Rewrite the passage below more clearly and precisely, same meaning, same length or shorter.",
    "shorten": "Shorten the passage below by about half without losing any mathematical content.",
    "formalise": "Rewrite the passage below in a more formal mathematical register (precise quantifiers, "
                 "definitions recalled, no hand-waving).",
    "translate_fr": "Translate the passage below into French (mathematical French usage).",
    "translate_en": "Translate the passage below into English (mathematical English usage).",
    "proof_sketch": "Write a short proof sketch (3 to 8 sentences) of the statement below, as a LaTeX "
                    "\\begin{proof}[Esquisse]...\\end{proof} environment (use the heading word of the article's "
                    "language). Say explicitly which step is the key one.",
    "sage": "Write ONE short SageMath cell that illustrates the statement below with a concrete example "
            "(computation or plot). Return only one fenced ```sage block.",
}
RULES = ("Rules: answer with the LaTeX of the new passage ONLY (no preamble, no Markdown, no explanation, no code "
         "fence unless asked); keep the author's macros, labels (\\label, \\ref, \\cite) unchanged; maths in $...$ "
         "or \\[...\\]; never define macros, never use \\input or file commands; cite only keys listed below, as "
         "\\cite{key}.")


def assist_messages(action: str, text: str, context: str, lang: str, keys: list[str], macros: dict) -> list[dict]:
    from ...research.safety import UNTRUSTED_RULE, wrap_untrusted
    task = ACTIONS[action]
    lang_rule = "" if action.startswith("translate") else (" Write in French." if lang == "fr" else
                                                           " Write in English.")
    content = (f"{task}{lang_rule}\n{RULES if action != 'sage' else ''}\n{UNTRUSTED_RULE}\n"
               f"Macros of the article: {', '.join(chr(92) + k for k in macros) or '(none)'}.\n"
               f"Citation keys that exist: {', '.join(keys[:80]) or '(none)'}.\n\n"
               f"Context (the paragraph around it):\n{wrap_untrusted(context[:3000], 'context')}\n\n"
               f"Passage:\n{wrap_untrusted(text[:8000], 'passage')}")
    return [{"role": "user", "content": content}]


def clean_latex(out: str) -> str:
    t = re.sub(r"<think>.*?(</think>|$)", "", out or "", flags=re.S).strip()
    m = re.match(r"^```[a-zA-Z]*\n([\s\S]*?)\n```\s*$", t)
    return (m.group(1) if m else t).strip()


@_guard
async def assist(request):
    ctx, pid = _ctx(request), _pid(request)
    data = await body(request)
    action = str(data.get("action", ""))
    if action not in ACTIONS:
        return error(400, "bad_fields", MESSAGES["bad_fields"], fields="action")
    path, text = str(data.get("path", "")), str(data.get("text", ""))
    if not tp.valid_path(path) or not text.strip():
        return error(400, "bad_fields", MESSAGES["bad_fields"], fields="path, text")
    files = await asyncio.to_thread(tp.read_files, ctx, pid)
    src = files.get(path, "")
    try:
        frm = int(data.get("from", src.find(text)))
    except (TypeError, ValueError):
        frm = src.find(text)
    if src[frm:frm + len(text)] != text:
        frm = src.find(text)
        if frm < 0:
            raise tp.TexProjectError("anchor_not_found", 409)
    occurrence = src.count(text, 0, frm)
    context = src[max(0, frm - 1200): frm + len(text) + 600]
    s = await asyncio.to_thread(tp.read_settings, ctx, pid)
    keys = list(tp._keys(ctx, pid))
    lang = s["document"].get("language", "fr")
    msgs = assist_messages(action, text, context, lang, keys, s["macros"])
    mode = _mode(ctx, pid, data)
    rid = "x-" + uuid.uuid4().hex[:10]
    dev = _dev(request)

    async def run():
        try:
            c = await complete_once(ctx, "explain", msgs, mode, owner=rid, max_tokens=3000, temperature=0.4)
            out = clean_latex(c.text)
            if action == "sage":
                from ...research.calcul import extract_code
                code = extract_code(c.text) or out
                from .workbench import WB
                wb = request.app.get(WB)
                cell = await asyncio.to_thread(wb.calc.add, pid, code[:100000], "sage", "assistant",
                                               note="article: " + text[:200], model=c.model.key)
                ctx.publish("article.assist.done", {"project": pid, "request_id": rid, "action": action,
                                                    "cell": {"id": cell["id"]}, "model": c.model.key})
                return
            if tp.looks_markdown(out) and not re.search(r"\\[A-Za-z]", out):
                out = tp.prose_to_latex(out, tp._keys(ctx, pid))      # a model that answered in Markdown
            at, find = ("after", text) if action == "proof_sketch" else ("replace", text)
            rep = ("\n" + out) if action == "proof_sketch" else out
            sug = await asyncio.to_thread(lambda: tp.add_suggestion(
                ctx, pid, find=find, replace=rep, path=path, at=at, occurrence=occurrence, kind=action,
                origin="assistant", rationale="", model=c.model.key, meta={"device": dev}))
            ctx.publish("article.suggestion", {"project": pid, "suggestion": sug})
            ctx.publish("article.assist.done", {"project": pid, "request_id": rid, "action": action,
                                                "suggestion": sug, "model": c.model.key})
        except tp.TexProjectError as e:
            ctx.publish("article.assist.error", {"project": pid, "request_id": rid, "error": e.kind,
                                                 "text": msg(MESSAGES.get(e.kind, "Introuvable."),
                                                             **{k: str(v) for k, v in e.info.items()})["text"]})
        except asyncio.CancelledError:
            ctx.publish("article.assist.error", {"project": pid, "request_id": rid, "error": "cancelled"})
        except Exception as e:  # noqa: BLE001
            log.exception("article assist failed")
            ctx.publish("article.assist.error", {"project": pid, "request_id": rid,
                                                 "error": getattr(e, "kind", "internal"), "text": str(e)[:300]})
    tasks = request.app[TASKS]
    t = ctx.spawn(run())
    tasks[rid] = t
    t.add_done_callback(lambda _t: tasks.pop(rid, None))
    return ok({"request_id": rid, "mode": mode}, status=202)


@_guard
async def lean_link(request):
    """« Vérifier avec Lean »: a dossier (not started) for the selected statement + a suggestion that links it."""
    ctx, pid = _ctx(request), _pid(request)
    data = await body(request)
    text, path = str(data.get("text", "")).strip(), str(data.get("path", ""))
    if not text or not tp.valid_path(path):
        return error(400, "bad_fields", MESSAGES["bad_fields"], fields="text, path")
    from ..routes_work import create_dossier
    files = await asyncio.to_thread(tp.read_files, ctx, pid)
    src = files.get(path, "")
    # the statement's environment line, when the selection is inside one
    i = src.find(text)
    begin = None
    if i >= 0:
        for m in re.finditer(r"\\begin\{(theorem|lemma|proposition|corollary|claim|conjecture|definition)\}"
                             r"(\[[^\]]*\])?(\\label\{[^}]*\})?[^\n]*", src[:i + len(text)]):
            begin = m
    plain = re.sub(r"\\label\{[^}]*\}", "", text)
    d, _job = await create_dossier(ctx, {"problem": plain[:20000], "title": str(data.get("title", ""))[:200],
                                         "project_id": pid, "start": bool(data.get("start", False))})
    d.extra["article_origin"] = {"path": path, "t": time.time()}
    await ctx.repo.save(d)
    if begin is not None:
        line = begin.group(0)
        sug = await asyncio.to_thread(lambda: tp.add_suggestion(
            ctx, pid, find=line, replace="\n% mdl:lean " + d.id, path=path, at="after", kind="lean", origin="user",
            rationale="link to dossier", meta={"dossier": d.id}))
        sug_ok = await asyncio.to_thread(tp.accept_suggestion, ctx, pid, sug["id"], _dev(request))
        _publish(request, pid, sug_ok[1], _dev(request))
    return ok({"dossier": {"id": d.id, "title": d.title}, "linked": begin is not None}, status=201)


# ================================================================ figures
@_guard
async def add_figure(request):
    ctx, pid = _ctx(request), _pid(request)
    if request.content_type.startswith("multipart/"):
        reader = await request.multipart()
        data = b""
        async for part in reader:
            if part.name == "file":
                buf = bytearray()
                while True:
                    chunk = await part.read_chunk(65536)
                    if not chunk:
                        break
                    buf += chunk
                    if len(buf) > 15 * 1024 * 1024:
                        raise tp.TexProjectError("too_large", 413)
                data = bytes(buf)
    else:
        j = await body(request)
        aid = str(j.get("calcul_asset", ""))
        from .workbench import WB
        wb = request.app.get(WB)
        found = wb.calc.asset_path(aid) if wb is not None else None
        if found is None:
            return error(404, "not_found", MESSAGES["not_found"])
        if found[1] != "image/png":
            raise tp.TexProjectError("bad_type", 415)
        data = await asyncio.to_thread(found[0].read_bytes)
    rel = await asyncio.to_thread(tp.add_figure, ctx, pid, data)
    return ok({"path": rel}, status=201)


@_guard
async def get_figure(request):
    ctx, pid = _ctx(request), _pid(request)
    rel = request.query.get("path", "")
    if not tp.FIGURE_PATH.match(rel):
        raise tp.TexProjectError("bad_path")
    p = tp.root(ctx, pid) / rel
    if not p.is_file():
        return error(404, "not_found")
    ctype = {"png": "image/png", "jpg": "image/jpeg", "pdf": "application/pdf"}[rel.rsplit(".", 1)[1]]
    return web.FileResponse(p, headers={"Content-Type": ctype, "Cache-Control": "private, max-age=31536000, immutable",
                                        "Content-Security-Policy": "default-src 'none'; sandbox",
                                        "X-Content-Type-Options": "nosniff"})


# ================================================================ Overleaf, exports, import
@_guard
async def overleaf_info(request):
    info = await asyncio.to_thread(overleaf.detect, request.query.get("refresh") == "1")
    return ok({**info, "local": bool(request.get("local"))})


@_guard
async def export_(request):
    ctx, pid = _ctx(request), _pid(request)
    fmt = request.query.get("format", "overleaf")
    p = ctx.projects.get(pid)
    from ...dossiers import slugify
    name = slugify(p.title or "article", 40)
    if fmt in ("overleaf", "zip"):
        data = await asyncio.to_thread(overleaf.export_zip, ctx, pid)
        return web.Response(body=data, content_type="application/zip",
                            headers={"Content-Disposition": f'attachment; filename="{name}-overleaf.zip"'})
    if fmt == "pdf":
        res = await texbuild.compile_project(ctx, pid)
        pdfp = texbuild.pdf_path(ctx, pid)
        if not res["ok"] or pdfp is None:
            return web.json_response({"error": "compile_failed", "diagnostics": res["diagnostics"][:20]}, status=422)
        return web.FileResponse(pdfp, headers={"Content-Type": "application/pdf",
                                               "Content-Disposition": f'attachment; filename="{name}.pdf"'})
    return error(400, "bad_format")


@_guard
async def import_(request):
    ctx, pid = _ctx(request), _pid(request)
    reader = await request.multipart()
    data = b""
    async for part in reader:
        if part.name == "file":
            buf = bytearray()
            while True:
                chunk = await part.read_chunk(65536)
                if not chunk:
                    break
                buf += chunk
                if len(buf) > 60 * 1024 * 1024:
                    raise tp.TexProjectError("too_large", 413)
            data = bytes(buf)
    if not data:
        return error(400, "bad_fields", MESSAGES["bad_fields"], fields="file")
    await asyncio.to_thread(tp.ensure, ctx, pid)
    res = await asyncio.to_thread(overleaf.import_zip, ctx, pid, data, _dev(request))
    files = await asyncio.to_thread(tp.read_files, ctx, pid)
    _publish(request, pid, {p: files.get(p, "") for p in res["changed"]}, _dev(request))
    bib_new = []
    if res.get("refs_bib"):
        from ...research import biblio
        items, _err = biblio.bibtex_to_items(res["refs_bib"])
        known = tp._keys(ctx, pid)
        bib_new = [it["_key"] for it in items if it.get("_key") not in known][:200]
    res["refs_bib"] = bool(res.get("refs_bib"))
    res["new_keys"] = bib_new
    return ok(res)


# ================================================================ registration
def register(app: web.Application, ctx) -> None:
    app[TASKS] = {}
    base = "/api/research/projects/{pid}/texproject"
    r = app.router
    r.add_get(base, get_project)
    r.add_post(base + "/new", new_project)
    r.add_post(base + "/file", save_file)
    r.add_delete(base + "/file", delete_section)
    r.add_post(base + "/sections", add_section)
    r.add_post(base + "/order", set_order)
    r.add_patch(base + "/settings", patch_settings)
    r.add_post(base + "/template", set_template)
    r.add_post(base + "/compile", compile_)
    r.add_get(base + "/pdf", get_pdf)
    r.add_get(base + "/synctex", synctex)
    r.add_get(base + "/packages", packages)
    r.add_get(base + "/versions", list_versions)
    r.add_post(base + "/versions", make_version)
    r.add_get(base + "/versions/{vid}", version_file)
    r.add_post(base + "/versions/{vid}/restore", restore_version)
    r.add_get(base + "/suggestions", list_sugs)
    r.add_post(base + "/suggestions", add_sug)
    r.add_post(base + "/suggestions/{sid}/accept", accept_sug)
    r.add_post(base + "/suggestions/{sid}/reject", reject_sug)
    r.add_post(base + "/assist", assist)
    r.add_post(base + "/lean", lean_link)
    r.add_post(base + "/figures", add_figure)
    r.add_get(base + "/figure", get_figure)
    r.add_get(base + "/overleaf", overleaf_info)
    r.add_get(base + "/export", export_)
    r.add_post(base + "/import", import_)
