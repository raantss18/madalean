"""Plugin of session S-AL (DECISIONS D44): the install state for the first-run wizard.

`GET /api/setup` (host only) → {
  schema: "madalean-setup-status/1",
  setup: <config>/setup.json written by install.sh / the graphical installer (detected machine, recommended plan,
         chosen plan, result, settings applied at first start) | null when Madalean was installed another way,
  detected: the machine check (from setup.json; fresh with `?refresh=1`, bounded, cached for the server's life),
  prefs: {sage_source, tex_engine, mode, wizard_done},
  components: health of every component of the prefix (as GET /api/deps),
  reuse: {sage: {...}, tex: {...}}  which copy is actually used and whether it works,
  keys: [providers with a key] (names only, never values),
  devices: number of paired devices,
  next_steps: [{id, done, title {fr,en}, help: manual page id}]   what is left to do, in order,
  recommended: assistant.recommend() for this machine (plan, items with reasons, advice, disk) | null   (S-AQ),
  models: {dir, files [{key, file, present, bytes, download_bytes}], download_bytes {all, prover, none}, choice,
           fetch}   the three local GGUF models and their download job                                   (S-AQ),
  wizard: as GET /api/setup/wizard                                                                       (S-AQ)
}

S-AQ (DECISIONS D49), for the in-app first-run assistant « Premiers pas » (all host only):
  GET   /api/setup/wizard  -> {schema "madalean-first-run/1", steps, step, visited, models, done, completed,
                               reminder, auto}   cheap: read at every start of the web app on the host
  PATCH /api/setup/wizard  {step?, visited?, models?, done?, completed?, reminder?}   progress in
                           <config>/first-run.json; `done` = Settings.wizard_done (« Plus tard » or finished),
                           `completed` = finished (also sets `done`)
  POST  /api/setup/reuse   {sage_source?, tex_engine?}  checked against this machine (« system » needs a system copy,
                           « tectonic » Madalean's tectonic), then saved like PATCH /api/settings; 409 + reason
  POST  /api/setup/models  {models: "prover" | "all"}   downloads the missing GGUF files the way install.sh does
                           (scripts/download_model.sh: pinned revisions, SHA-256 checked) in the background;
                           progress as WebSocket events `setup.models {fetch}`; refused in Local mode and in the demo
  POST  /api/setup/models/cancel
Every other setting goes through the existing PATCH /api/settings, keys through /api/models/keys + /api/models/test,
components through /api/deps/{c}/install and /api/system/repair/{id}, pairing through /api/pairing/start."""
from __future__ import annotations

import asyncio
import json
import os
import re
import time
from pathlib import Path

from aiohttp import web

from ... import config
from ...deps import assistant
from ...deps import health as deps_health
from ...logs import get
from ..common import body, ctx_of, error, host_only, ok

log = get("setup_api")
_DETECTED: dict = {}


def _reuse(prefs: dict, det: dict) -> dict:
    from ...export import _engines, tectonic_cmd
    from ... import deps
    from ...research.sagebridge import find_kernelspec
    spec = find_kernelspec("sagemath")
    sage_tool = (det.get("tools") or {}).get("sage") or {}
    sage_used = ("" if spec is None else
                 "own" if str(spec["argv"][0]).startswith(str(deps.home()) + "/") else "system")
    engines = _engines()
    first = engines[0][0] if engines else ""
    tex_used = "" if not first else ("tectonic" if tectonic_cmd() and engines[0] == tectonic_cmd() else "system")
    return {
        "sage": {"preference": prefs["sage_source"], "used": sage_used, "ok": spec is not None,
                 "system": {k: sage_tool.get(k) for k in ("found", "version", "kernelspec", "compatible")}},
        "tex": {"preference": prefs["tex_engine"], "used": tex_used, "ok": bool(engines),
                "engines": len(engines), "system": {k: ((det.get("tools") or {}).get("tex") or {}).get(k)
                                                    for k in ("found", "year", "fontspec", "compatible")}},
    }


def next_steps(ctx, reuse: dict, comps: list[dict], keys: list[str], devices: int, plan: dict) -> list[dict]:
    from ...leansandbox import status as sandbox_status
    steps = [
        {"id": "keys", "done": bool(keys), "help": "first-config",
         "title": {"fr": "Ajouter au moins une clé de modèle en ligne (gratuite)",
                   "en": "Add at least one online model key (free)"}},
        {"id": "workspace", "done": any(not w.problems for w in ctx.workspaces), "help": "components",
         "title": {"fr": "Avoir un espace Lean + Mathlib prêt", "en": "Have a Lean + Mathlib workspace ready"}},
        {"id": "sandbox", "done": sandbox_status()["sandbox"] == "bwrap", "help": "components",
         "title": {"fr": "Installer bubblewrap (bac à sable) avec le gestionnaire de paquets",
                   "en": "Install bubblewrap (sandbox) with the package manager"}},
        {"id": "sage", "done": reuse["sage"]["ok"] or plan.get("sage") == "later", "help": "components",
         "title": {"fr": "SageMath prêt pour le calcul", "en": "SageMath ready for computations"}},
        {"id": "tex", "done": reuse["tex"]["ok"], "help": "components",
         "title": {"fr": "LaTeX prêt pour l'export PDF", "en": "LaTeX ready for the PDF export"}},
        {"id": "components", "done": all(c["ok"] for c in comps), "help": "components",
         "title": {"fr": "Tous les composants en bon état", "en": "Every component healthy"}},
        {"id": "pair", "done": devices > 0, "help": "pairing",
         "title": {"fr": "Relier un téléphone ou un autre ordinateur (facultatif)",
                   "en": "Link a phone or another computer (optional)"}},
    ]
    return steps


@host_only
async def setup_get(request: web.Request) -> web.Response:
    ctx = ctx_of(request)
    doc = await asyncio.to_thread(assistant.load, ctx.paths.config)
    det = (doc or {}).get("detected") or {}
    if request.query.get("refresh") == "1" or (not det and not _DETECTED):
        _DETECTED.clear()
        _DETECTED.update(await asyncio.to_thread(assistant.detect))
    if _DETECTED and (request.query.get("refresh") == "1" or not det):
        det = dict(_DETECTED)
    s = ctx.settings
    prefs = {"sage_source": s.sage_source, "tex_engine": s.tex_engine, "mode": s.mode, "wizard_done": s.wizard_done}
    wiz = wizard_state(request.app, ctx)
    comps = await asyncio.to_thread(deps_health.components)
    reuse = await asyncio.to_thread(_reuse, prefs, det)
    keys = sorted(ctx.keys.providers())
    devices = len(ctx.devices.list())
    plan = (doc or {}).get("plan") or {}
    return ok({"schema": "madalean-setup-status/1", "setup": doc, "detected": det, "prefs": prefs,
               "components": comps, "reuse": reuse, "keys": keys, "devices": devices,
               "next_steps": next_steps(ctx, reuse, comps, keys, devices, plan),
               "recommended": assistant.recommend(det, "en" if s.language == "en" else "fr") if det else None,
               "models": await asyncio.to_thread(models_state, wiz), "wizard": wiz})


# ---------------------------------------------------------------- S-AQ: the first-run assistant « Premiers pas »
STEPS = ("welcome", "tools", "local", "keys", "hf", "claude", "modes", "auto", "pair", "done")
WIZARD_SCHEMA = "madalean-first-run/1"


def _wiz_file(ctx) -> Path:
    return ctx.paths.config / "first-run.json"


def _wiz_load(ctx) -> dict:
    try:
        d = json.loads(_wiz_file(ctx).read_text(encoding="utf-8"))
        return d if isinstance(d, dict) and d.get("schema") == WIZARD_SCHEMA else {}
    except (OSError, ValueError):
        return {}


def wizard_state(app: web.Application, ctx) -> dict:
    """Where the user stopped. `auto`: open the assistant by itself at the next start of the web app on the host —
    never once it was finished or put off (« Plus tard » = Settings.wizard_done), nor on a server that already held
    the user's work when it started (an update from 2.0.0: the Home card offers it instead)."""
    d = _wiz_load(ctx)
    done, completed = bool(ctx.settings.wizard_done), bool(d.get("completed"))
    step = d.get("step") if d.get("step") in STEPS else STEPS[0]
    return {"schema": WIZARD_SCHEMA, "steps": list(STEPS), "step": step,
            "visited": [x for x in STEPS if x in (d.get("visited") or [])],
            "models": d.get("models") if d.get("models") in assistant.CHOICES["models"] else "",
            "done": done, "completed": completed, "reminder": bool(d.get("reminder", True)),
            "auto": not done and not completed}


@host_only
async def wizard_get(request: web.Request) -> web.Response:
    return ok(wizard_state(request.app, ctx_of(request)))


def _bad_wizard_patch(data: dict) -> bool:
    if set(data) - {"step", "visited", "models", "done", "completed", "reminder"}:
        return True
    if "step" in data and data["step"] not in STEPS:
        return True
    if "visited" in data and (not isinstance(data["visited"], list) or any(v not in STEPS for v in data["visited"])):
        return True
    if "models" in data and data["models"] not in assistant.CHOICES["models"]:
        return True
    return any(k in data and not isinstance(data[k], bool) for k in ("done", "completed", "reminder"))


@host_only
async def wizard_patch(request: web.Request) -> web.Response:
    ctx = ctx_of(request)
    data = await body(request)
    if _bad_wizard_patch(data):
        return error(400, "bad_fields")
    d = _wiz_load(ctx) or {"schema": WIZARD_SCHEMA}
    for k in ("step", "models", "completed", "reminder"):
        if k in data:
            d[k] = data[k]
    if "visited" in data:
        seen = set(d.get("visited") or []) | set(data["visited"])
        d["visited"] = [x for x in STEPS if x in seen]
    d["updated"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    await asyncio.to_thread(config.atomic_write_text, _wiz_file(ctx), json.dumps(d, indent=1, ensure_ascii=False))
    done = True if data.get("completed") else data.get("done")
    if isinstance(done, bool) and done != ctx.settings.wizard_done:
        _s, errors = await ctx.patch_settings({"wizard_done": done}, True)
        if errors:
            return error(400, "invalid_settings")
    st = wizard_state(request.app, ctx)
    ctx.publish("setup.wizard", {"wizard": st})
    return ok(st)


def _system_sage_kernel() -> str:
    """A `sagemath` kernel in the system kernel dirs (what `sage_source = system` will use), or ""."""
    from ...research import sagebridge
    for d in sagebridge.KERNEL_DIRS:
        f = Path(d) / "sagemath" / "kernel.json"
        if d != sagebridge.PREFIX_KERNELS and f.is_file():
            return str(f)
    return ""


def reuse_check(key: str, value: str, det: dict) -> str:
    """"" when `value` can be used on this machine, else the reason (a code the UI translates)."""
    from ... import deps
    from ...context import ENUMS
    from ...export import tectonic_cmd
    if value not in ENUMS[key]:
        return "invalid"
    tools = (det or {}).get("tools") or {}
    if key == "sage_source" and value == "system":
        if not _system_sage_kernel():
            return "no_system_sage"
        sage = tools.get("sage") or {}
        if sage.get("found") and sage.get("version") and not sage.get("compatible"):
            return "system_sage_too_old"
    if key == "tex_engine" and value == "system" and not (deps.tool("xelatex") or deps.tool("lualatex")):
        return "no_system_tex"
    if key == "tex_engine" and value == "tectonic" and not tectonic_cmd():
        return "no_tectonic"
    return ""


@host_only
async def reuse_post(request: web.Request) -> web.Response:
    ctx = ctx_of(request)
    data = await body(request)
    patch = {k: data[k] for k in ("sage_source", "tex_engine") if k in data}
    if not patch or set(data) - set(patch):
        return error(400, "bad_fields")
    doc = await asyncio.to_thread(assistant.load, ctx.paths.config)
    det = dict(_DETECTED) or (doc or {}).get("detected") or {}
    for k, v in patch.items():
        why = await asyncio.to_thread(reuse_check, k, v, det)
        if why:
            return web.json_response({"error": "unavailable", "field": k, "reason": why}, status=409)
    _s, errors = await ctx.patch_settings(patch, True)
    if errors:
        return web.json_response({"error": "invalid_settings", "details": errors}, status=400)
    s = ctx.settings
    prefs = {"sage_source": s.sage_source, "tex_engine": s.tex_engine, "mode": s.mode, "wizard_done": s.wizard_done}
    return ok({"prefs": prefs, "reuse": await asyncio.to_thread(_reuse, prefs, det)})


# ---- local models: the three GGUF files of install.sh, downloaded the same way (pinned, SHA-256 checked)
_FETCH: dict = {}
_PROC: dict = {}
PROGRESS_RE = re.compile(r"(\d+)/(\d+) segments\s+([\d.]+)/([\d.]+) GB")


def fetch_argv(keys: list[str]) -> list[str]:
    """The download command (tests replace it with a fake)."""
    return ["bash", str(config.STATION_DIR / "scripts" / "download_model.sh"), *keys]


def models_state(wiz: dict | None = None) -> dict:
    files = []
    for key in assistant.MODEL_SETS["all"]:
        f = config.MODELS_DIR / assistant.MODEL_FILES[key]
        try:
            size = f.stat().st_size if f.is_file() else 0
        except OSError:
            size = 0
        files.append({"key": key, "file": f.name, "present": size > 0, "bytes": size,
                      "download_bytes": 0 if size else assistant.MODEL_BYTES})
    sets = {name: sum(x["download_bytes"] for x in files if x["key"] in keys)
            for name, keys in assistant.MODEL_SETS.items()}
    return {"dir": config.tilde(config.MODELS_DIR), "files": files, "download_bytes": sets,
            "choice": (wiz or {}).get("models", ""), "fetch": dict(_FETCH)}


@host_only
async def models_post(request: web.Request) -> web.Response:
    ctx = ctx_of(request)
    data = await body(request)
    which = data.get("models")
    if which not in ("prover", "all") or set(data) - {"models"}:
        return error(400, "bad_fields")
    if _FETCH.get("running"):
        return error(409, "busy")
    if ctx.settings.mode == "local":
        return error(409, "local_mode")                # nothing leaves the machine in Local mode
    if ctx.demo:
        return error(409, "demo")                       # the demo never downloads 5–15 GB
    st = await asyncio.to_thread(models_state)
    keys = [f["key"] for f in st["files"] if f["key"] in assistant.MODEL_SETS[which] and not f["present"]]
    if not keys:
        return ok({"started": False, "models": st})
    _FETCH.clear()
    _FETCH.update({"running": True, "phase": "download", "keys": keys, "index": 0, "done_gb": 0.0,
                   "total_gb": 0.0, "message": "", "ok": None, "started": time.time()})

    def publish() -> None:
        ctx.publish("setup.models", {"fetch": dict(_FETCH)})

    async def run() -> None:
        try:
            env = {**os.environ, "MADALEAN_MODELS_DIR": str(config.MODELS_DIR), "PYTHONUNBUFFERED": "1"}
            proc = await asyncio.create_subprocess_exec(*fetch_argv(keys), stdout=asyncio.subprocess.PIPE,
                                                        stderr=asyncio.subprocess.STDOUT, env=env,
                                                        start_new_session=True)
            _PROC["p"] = proc
            assert proc.stdout is not None
            while True:
                b = await proc.stdout.readline()
                if not b:
                    break
                line = b.decode("utf-8", "replace").strip()
                m = PROGRESS_RE.search(line)
                if m:
                    _FETCH.update(done_gb=float(m.group(3)), total_gb=float(m.group(4)))
                elif line.startswith(("OK ", "already complete")):
                    _FETCH.update(index=min(_FETCH["index"] + 1, len(keys)), done_gb=0.0, total_gb=0.0)
                elif line:
                    _FETCH["message"] = line[-300:]
                publish()
            code = await proc.wait()
            ok_ = code == 0 and all((config.MODELS_DIR / assistant.MODEL_FILES[k]).is_file() for k in keys)
            _FETCH.update(running=False, phase="done" if ok_ else "error", ok=ok_)
            if ok_ and hasattr(ctx.local, "refresh_models"):
                await ctx.local.refresh_models()
        except OSError as e:
            _FETCH.update(running=False, phase="error", ok=False, message=str(e)[:300])
            log.warning("model download failed: %s", e)
        finally:
            if _FETCH.get("running"):                   # cancelled with the server: stop the download too
                _FETCH.update(running=False, phase="error", ok=False)
                _kill(_PROC.get("p"))
            _PROC.pop("p", None)
            publish()
    ctx.spawn(run())
    return ok({"started": True, "models": await asyncio.to_thread(models_state)}, status=202)


def _kill(p) -> None:
    """The script and its downloader (own process group). pdownload keeps its parts: a later download resumes."""
    if p is None or p.returncode is not None:
        return
    try:
        os.killpg(p.pid, 15)
    except (ProcessLookupError, PermissionError):
        pass


@host_only
async def models_cancel(request: web.Request) -> web.Response:
    p = _PROC.get("p")
    if p is None:
        return ok({"cancelled": False})
    _kill(p)
    return ok({"cancelled": True})


async def _reset_inherited_done(ctx) -> None:
    """`wizard_done` may come from 1.x / 2.0.0 settings (the old assistant, carried over by migrate.py). Until this
    assistant has been seen once (no first-run.json yet), that inherited value is reset so it opens at the first
    start, as the user asked; the file is written at once so this happens only once."""
    if getattr(ctx, "demo", False) or _wiz_file(ctx).exists():
        return
    if ctx.settings.wizard_done:
        await ctx.patch_settings({"wizard_done": False}, True)
    d = {"schema": WIZARD_SCHEMA, "step": STEPS[0], "visited": [], "reminder": True}
    await asyncio.to_thread(config.atomic_write_text, _wiz_file(ctx), json.dumps(d, indent=1, ensure_ascii=False))


def register(app: web.Application, ctx) -> None:
    # The assistant opens by itself at the first start of the host's web app, an update from 2.0.0 included (the
    # user's choice, 2026-11-22); « Plus tard » or « Terminer » sets wizard_done and it never opens by itself again.
    async def reset(_app: web.Application) -> None:
        await _reset_inherited_done(ctx)
    app.on_startup.append(reset)
    app.router.add_get("/api/setup", setup_get)
    app.router.add_get("/api/setup/wizard", wizard_get)
    app.router.add_patch("/api/setup/wizard", wizard_patch)
    app.router.add_post("/api/setup/reuse", reuse_post)
    app.router.add_post("/api/setup/models", models_post)
    app.router.add_post("/api/setup/models/cancel", models_cancel)
