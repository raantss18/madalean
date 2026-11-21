"""hello, pairing, devices, state, settings, models, system, updates."""
from __future__ import annotations

import asyncio
import shutil
import time

from aiohttp import web

from .. import config, names
from ..context import HOST_ONLY_SETTINGS
from ..i18n import msg
from ..security import TOKEN_COOKIE, PairingError, RateLimiter
from .common import body, ctx_of, error, host_only, ok, valid_id

routes = web.RouteTableDef()
PAIR_LIMIT = RateLimiter(10, 60.0)
PAIR_GLOBAL = RateLimiter(30, 60.0)


@routes.get("/api/hello")
async def hello(request: web.Request) -> web.Response:
    ctx = ctx_of(request)
    return ok({"name": "madalean", "version": ctx.version, "paired": request["local"] or request["device"] is not None,
               "local": request["local"], "host_name": ctx.settings.host_name or ctx.host_name, "demo": ctx.demo,
               "lang": ctx.settings.language})


@routes.post("/api/pair")
async def pair(request: web.Request) -> web.Response:
    ctx = ctx_of(request)
    who = request.headers.get("X-Forwarded-For", request.remote or "?").split(",")[0].strip()
    if not PAIR_GLOBAL.allow("*") or not PAIR_LIMIT.allow(who):
        return error(429, "rate_limited", "Trop d'essais : attendez une minute.")
    data = await body(request)
    try:
        ctx.pairing.consume(str(data.get("code", "")))
    except PairingError as e:
        keys = {"locked": "Appairage bloqué pendant {m} minutes après trop d'erreurs.",
                "expired": "Ce code a expiré : demandez-en un nouveau sur l'ordinateur hôte.",
                "no_code": "Aucun code actif : affichez-en un sur l'ordinateur hôte.",
                "wrong": "Code incorrect."}
        status = 429 if e.kind == "locked" else 403
        return error(status, e.kind, keys[e.kind], m=int(round(e.retry_after / 60)) or 1)
    dev, token = await asyncio.to_thread(ctx.devices.add, str(data.get("device_name", ""))[:80])
    ctx.publish("devices.updated", {"devices": ctx.devices.list()})
    resp = ok({"token": token, "device": dev.public()})
    resp.set_cookie(TOKEN_COOKIE, token, max_age=10 * 365 * 86400, httponly=True, secure=True, samesite="Strict",
                    path="/")
    return resp


@routes.post("/api/logout")
async def logout(request: web.Request) -> web.Response:
    """Forget this device (remote): its token is revoked and the cookie cleared."""
    ctx = ctx_of(request)
    dev = request["device"]
    if dev is not None:
        await asyncio.to_thread(ctx.devices.revoke, dev.id)
        ctx.publish("devices.updated", {"devices": ctx.devices.list()})
    resp = ok({"ok": True})
    resp.del_cookie(TOKEN_COOKIE, path="/")
    return resp


@routes.post("/api/pairing/start")
@host_only
async def pairing_start(request: web.Request) -> web.Response:
    code, ttl = ctx_of(request).pairing.start()
    return ok({"code": code, "expires": time.time() + ttl, "expires_in": ttl})


@routes.get("/api/pairing")
@host_only
async def pairing_status(request: web.Request) -> web.Response:
    return ok(ctx_of(request).pairing.status())


@routes.get("/api/devices")
@host_only
async def devices(request: web.Request) -> web.Response:
    return ok({"devices": ctx_of(request).devices.list()})


@routes.delete("/api/devices/{id}")
@host_only
async def device_revoke(request: web.Request) -> web.Response:
    ctx = ctx_of(request)
    if not await asyncio.to_thread(ctx.devices.revoke, valid_id(request.match_info["id"])):
        return error(404, "not_found")
    ctx.publish("devices.updated", {"devices": ctx.devices.list()})
    return ok({"ok": True})


@routes.get("/api/state")
async def state(request: web.Request) -> web.Response:
    from ..repo import dossier_summary
    ctx = ctx_of(request)
    dev = request["device"]
    return ok({
        "version": ctx.version, "host_name": ctx.settings.host_name or ctx.host_name, "local": request["local"],
        "device": dev.public() if dev else None, "demo": ctx.demo, "brain": ctx.brain_kind,
        "lang": ctx.settings.language, "seq": ctx.bus.seq, "boot": ctx.bus.boot,
        "settings": ctx.settings_public(), "host_only_settings": sorted(HOST_ONLY_SETTINGS),
        "projects": [p.to_dict() for p in ctx.projects.list()],
        "dossiers": [dossier_summary(d) for d in ctx.repo.list()],
        "jobs": {"active": [j.to_dict() for j in ctx.orchestrator.active()],
                 "recent": [j.to_dict() for j in ctx.orchestrator.recent(30)]},
        "models": await ctx.models_public(),
        "system": {**ctx.system_light(), "workspaces": ctx.workspaces_public()},
        "library": {"count": len(ctx.library.entries)},
        "updates": ctx.updates.status(),
        "jupyter": ctx.jupyter.status(),
        "migration": ctx.migration,
    })


# ---------------------------------------------------------------- settings
@routes.get("/api/settings")
async def settings_get(request: web.Request) -> web.Response:
    return ok({"settings": ctx_of(request).settings_public()})


@routes.patch("/api/settings")
async def settings_patch(request: web.Request) -> web.Response:
    ctx = ctx_of(request)
    data = await body(request)
    s, errors = await ctx.patch_settings(data, request["local"])
    if errors:
        status = 403 if any(e.startswith("host_only:") for e in errors) else 400
        return web.json_response({"error": "invalid_settings", "details": errors, "settings": s}, status=status)
    return ok({"settings": s})


# ---------------------------------------------------------------- models
@routes.get("/api/models")
async def models(request: web.Request) -> web.Response:
    return ok(await ctx_of(request).models_public())


@routes.post("/api/models/keys")
async def models_key_set(request: web.Request) -> web.Response:
    ctx = ctx_of(request)
    data = await body(request)
    provider, key = str(data.get("provider", "")), data.get("key")
    if not isinstance(key, str) or not key.strip() or len(key) > 4096:
        return error(400, "bad_key")
    try:
        backend = await asyncio.to_thread(ctx.keys.set, provider, key)
    except ValueError:
        return error(400, "bad_provider")
    _notify_keys(ctx)
    return ok({"provider": provider, "set": True, "backend": backend})


@routes.delete("/api/models/keys/{provider}")
async def models_key_delete(request: web.Request) -> web.Response:
    ctx = ctx_of(request)
    had = await asyncio.to_thread(ctx.keys.delete, request.match_info["provider"][:41])
    _notify_keys(ctx)
    return ok({"provider": request.match_info["provider"], "set": False, "existed": had})


def _notify_keys(ctx) -> None:
    if hasattr(ctx.brain, "keys_changed"):
        try:
            ctx.brain.keys_changed()
        except Exception:  # noqa: BLE001
            pass
    ctx.publish("models.status", {"keys": {p: True for p in ctx.keys.providers()}})


@routes.post("/api/models/test")
async def models_test(request: web.Request) -> web.Response:
    ctx = ctx_of(request)
    data = await body(request)
    provider = str(data.get("provider", ""))
    fn = getattr(ctx.brain, "test", None)
    if fn is None:
        return ok({"provider": provider, "ok": None, "reason": "not_supported"})
    try:
        res = await asyncio.wait_for(fn(provider), 60)
    except Exception as e:  # noqa: BLE001
        return ok({"provider": provider, "ok": False, "reason": str(e)[:300]})
    return ok({"provider": provider, **(res if isinstance(res, dict) else {"ok": bool(res)})})


@routes.post("/api/models/refresh")
async def models_refresh(request: web.Request) -> web.Response:
    ctx = ctx_of(request)
    if hasattr(ctx.local, "refresh_models"):
        await ctx.local.refresh_models()
    if ctx.brain is not None:
        ctx.spawn(ctx.brain.refresh())
    return ok(await ctx.models_public())


@routes.post("/api/models/local/stop")
async def models_local_stop(request: web.Request) -> web.Response:
    ctx = ctx_of(request)
    if ctx.slots.holders.get("gpu"):
        return error(409, "busy", "Une opération est en cours : arrêtez-la d'abord (Échap).")
    if hasattr(ctx.local, "stop"):
        await ctx.local.stop()
    return ok({"local": ctx.local.status() if hasattr(ctx.local, "status") else {}})


# ---------------------------------------------------------------- system
def _fonts() -> dict:
    import subprocess
    out = {}
    for fam in ("DejaVu Sans Mono", "Noto Sans Math"):
        try:
            r = subprocess.run(["fc-list", fam], capture_output=True, text=True, timeout=10)
            out[fam] = bool(r.stdout.strip())
        except (OSError, subprocess.SubprocessError):
            out[fam] = False
    return out


async def health(ctx) -> list[dict]:
    checks = []

    def add(cid: str, okv: bool, key: str, repair: str = "", level: str = "", **params):
        checks.append({"id": cid, "ok": okv, "level": level or ("ok" if okv else "warn"), "repair": repair,
                       "message": msg(key, **params)})
    ws = ctx.workspace()
    add("workspace", ws is not None and not ws.problems,
        "Espace de travail Lean prêt : {ws}." if ws is not None and not ws.problems else
        "L'espace de travail Lean n'est pas prêt : {ws}.", repair="workspaces",
        ws=(ws.key if ws else "—") + ("" if ws is None or not ws.problems else f" ({ws.problems[0]})"))
    exe = config.LLAMA_BIN_DIR / "llama-server"
    add("llama", exe.exists() or ctx.demo, "Moteur local llama-server présent." if exe.exists() or ctx.demo else
        "llama-server introuvable : relancez install.sh.")
    for role, key in (("prove", "prover"), ("formalize", "formalizer"), ("explain", "explainer")):
        m = ctx.local.model_for(role) if hasattr(ctx.local, "model_for") else None
        add("model_" + key, m is not None, "Modèle local « {role} » : {name}." if m else
            "Aucun modèle local « {role} » installé.", repair="models", role=key, name=m.model_id if m else "")
    tex = shutil.which("latexmk") and shutil.which("xelatex")
    add("tex", bool(tex), "LaTeX (latexmk + XeLaTeX) présent : export PDF possible." if tex else
        "LaTeX absent : l'export PDF devient une page HTML à imprimer.")
    fonts = await asyncio.to_thread(_fonts)
    for fam, present in fonts.items():
        add("font_" + fam.replace(" ", "_").lower(), present, "Police {f} : présente." if present else
            "Police {f} absente (export PDF moins lisible).", f=fam)
    add("jupyter", bool(shutil.which("jupyter-lab")), "JupyterLab présent." if shutil.which("jupyter-lab") else
        "JupyterLab absent : les carnets ne sont pas disponibles.")
    disks = ctx.monitor.disk or []
    low = [d for d in disks if d["free_gb"] < 10]
    add("disk", not low, "Espace disque suffisant." if not low else "Disque presque plein : {n} Go libres.",
        n=low[0]["free_gb"] if low else 0)
    add("brain", ctx.brain_kind != "fake" or ctx.demo, "Moteur de modèles : {kind}." if ctx.brain_kind != "fake"
        or ctx.demo else "Moteur de modèles absent : réponses simulées (installation incomplète).", kind=ctx.brain_kind)
    return checks


@routes.get("/api/system")
async def system(request: web.Request) -> web.Response:
    ctx = ctx_of(request)
    if ctx.monitor.t == 0:
        await ctx.monitor.poll()
    return ok({**ctx.system_light(), "workspaces": ctx.workspaces_public(), "checks": await health(ctx),
               "local": ctx.local.status() if hasattr(ctx.local, "status") else {}, "brain": ctx.brain_kind,
               "lean_running": list((getattr(ctx.lean, "running", {}) or {}).values())})


REPAIRS = ("workspaces", "models", "local_model", "names_index")


@routes.post("/api/system/repair/{id}")
@host_only
async def system_repair(request: web.Request) -> web.Response:
    ctx = ctx_of(request)
    rid = request.match_info["id"]
    if rid not in REPAIRS:
        return error(404, "unknown_repair")
    if rid == "workspaces":
        await ctx.refresh_workspaces()
    elif rid == "models":
        if hasattr(ctx.local, "refresh_models"):
            await ctx.local.refresh_models()
    elif rid == "local_model":
        if ctx.slots.holders.get("gpu"):
            return error(409, "busy", "Une opération est en cours : arrêtez-la d'abord (Échap).")
        if hasattr(ctx.local, "stop"):
            await ctx.local.stop()
    elif rid == "names_index":
        ws = ctx.workspace()
        if ws is None:
            return error(409, "no_workspace")
        idx = await asyncio.to_thread(names.get, ws, True)
        return ok({"repair": rid, "ok": idx is not None, "names": len(idx) if idx else 0})
    return ok({"repair": rid, "ok": True, "checks": await health(ctx)})


# ---------------------------------------------------------------- updates
@routes.get("/api/updates")
async def updates_get(request: web.Request) -> web.Response:
    return ok(ctx_of(request).updates.status())


@routes.post("/api/updates/check")
async def updates_check(request: web.Request) -> web.Response:
    ctx = ctx_of(request)
    ctx.spawn(ctx.updates.check(manual=True))
    return ok({"checking": True}, status=202)


@routes.post("/api/updates/install")
async def updates_install(request: web.Request) -> web.Response:
    ctx = ctx_of(request)
    data = await body(request)
    err = await ctx.updates.install(str(data.get("key", "")))
    if err == "jobs_running":
        return error(409, err, "Une opération est en cours : arrêtez-la d'abord (Échap).")
    if err:
        return error(409 if err == "busy" else 404, err)
    return ok(ctx.updates.status(), status=202)


@routes.post("/api/updates/cancel")
async def updates_cancel(request: web.Request) -> web.Response:
    return ok({"cancelled": await ctx_of(request).updates.cancel()})
