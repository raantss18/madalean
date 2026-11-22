"""Plugin of session S-AL (DECISIONS D44): the install state for the first-run wizard — read only.

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
  next_steps: [{id, done, title {fr,en}, help: manual page id}]   what is left to do, in order
}
The future in-app wizard reads this; it changes settings through the existing PATCH /api/settings."""
from __future__ import annotations

import asyncio

from aiohttp import web

from ...deps import assistant
from ...deps import health as deps_health
from ..common import ctx_of, host_only, ok

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
    comps = await asyncio.to_thread(deps_health.components)
    reuse = await asyncio.to_thread(_reuse, prefs, det)
    keys = sorted(ctx.keys.providers())
    devices = len(ctx.devices.list())
    plan = (doc or {}).get("plan") or {}
    return ok({"schema": "madalean-setup-status/1", "setup": doc, "detected": det, "prefs": prefs,
               "components": comps, "reuse": reuse, "keys": keys, "devices": devices,
               "next_steps": next_steps(ctx, reuse, comps, keys, devices, plan)})


def register(app: web.Application, ctx) -> None:
    app.router.add_get("/api/setup", setup_get)
