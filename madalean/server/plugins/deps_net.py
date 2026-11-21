"""Plugin of session S-I: self-contained components (§18) and the embedded Tailscale node.

Routes (all JSON, see docs/INSTALL.md):
- `GET  /api/deps`                          components of the prefix (version, path, state, repair) + install jobs
- `POST /api/deps/{component}/install`      host: install / repair a component (sage on demand…) in the background;
                                            progress as WebSocket events `deps.progress`
- `POST /api/deps/{component}/rollback`     host: switch back to the previous version
- `GET  /api/net`                           host: status of the Tailscale node (login URL, tailnet name, IPs, cert)
- `POST /api/net/start` | `/api/net/stop`   host
- `PATCH /api/net {enabled?, hostname?}`    host: stored in <config>/net.json (default: enabled, "madalean")
WebSocket events: `deps.progress`, `net.status {net}`.

The node starts with the server when madalean-net is installed in the prefix, the server is not in demo mode and
`net.json` does not disable it (env MADALEAN_NO_NET=1 disables it too)."""
from __future__ import annotations

import asyncio
import json
import os

from aiohttp import web

from ... import deps
from ...config import atomic_write_text, read_json
from ...deps import health as deps_health
from ...deps import service
from ...deps.installer import InstallError
from ...logs import get
from ...runtime.net import HOSTNAME_RE, NetManager
from ..auth import REMOTE_HOSTS
from ..common import ctx_of, error, host_only, ok

log = get("deps_net")
NET = web.AppKey("net_manager", NetManager)
COMPONENT_RE = r"{component:[a-z0-9.-]{1,40}}"


def shared_node_blocked(config_dir) -> str | None:
    """Why this server must not auto-start the shared Tailscale node (None: it is the installed server)."""
    from pathlib import Path
    from ... import config
    if os.environ.get("MADALEAN_NET") == "1":
        return None
    try:
        if deps.home().resolve() not in config.STATION_DIR.resolve().parents:
            return "dev_checkout"
        if Path(config_dir).resolve() != (Path.home() / ".config" / "madalean").resolve():
            return "custom_config_dir"
    except OSError:
        return "unknown_layout"
    return None


def _net_settings(ctx) -> dict:
    data = read_json(ctx.paths.config / "net.json")[0] or {}
    host = data.get("hostname") if isinstance(data.get("hostname"), str) else "madalean"
    return {"enabled": bool(data.get("enabled", True)), "hostname": host if HOSTNAME_RE.match(host) else "madalean"}


def _save_net_settings(ctx, s: dict) -> None:
    atomic_write_text(ctx.paths.config / "net.json", json.dumps(s))


async def deps_get(request: web.Request) -> web.Response:
    rep = await asyncio.to_thread(deps_health.report)
    rep["jobs"] = dict(service.JOBS)
    return ok(rep)


@host_only
async def deps_install(request: web.Request) -> web.Response:
    ctx = ctx_of(request)
    name = request.match_info["component"]
    if name not in {c["component"] for c in deps_health.components()}:
        return error(404, "not_found")
    job = service.JOBS.get(name) or {}
    if job.get("running"):
        return error(409, "busy")

    async def run():
        try:
            await service.install_async(name, ctx.publish)
            ctx.publish("deps.progress", {"component": name, "phase": "done", "done": 0, "total": 0,
                                          "message": ""})
        except (InstallError, OSError) as e:
            log.warning("install %s failed: %s", name, e)
    ctx.spawn(run())
    return ok({"component": name, "started": True}, status=202)


@host_only
async def deps_rollback(request: web.Request) -> web.Response:
    name = request.match_info["component"]
    try:
        return ok(await service.rollback_async(name))
    except InstallError as e:
        return error(409, e.key)


@host_only
async def net_get(request: web.Request) -> web.Response:
    app = request.app
    return ok({**app[NET].status(), "settings": _net_settings(ctx_of(request))})


@host_only
async def net_start(request: web.Request) -> web.Response:
    port = _remote_port(ctx_of(request))
    if not port:
        return error(409, "no_remote_listener")
    return ok(await request.app[NET].start(port))


@host_only
async def net_stop(request: web.Request) -> web.Response:
    await request.app[NET].stop()
    return ok(request.app[NET].status())


@host_only
async def net_patch(request: web.Request) -> web.Response:
    ctx = ctx_of(request)
    try:
        body = await request.json()
    except ValueError:
        return error(400, "bad_json")
    s = _net_settings(ctx)
    if "enabled" in body:
        s["enabled"] = bool(body["enabled"])
    if "hostname" in body:
        h = str(body["hostname"]).strip().lower()
        if not HOSTNAME_RE.match(h):
            return error(400, "bad_fields")
        s["hostname"] = h
    await asyncio.to_thread(_save_net_settings, ctx, s)
    nm: NetManager = request.app[NET]
    nm.hostname = s["hostname"]
    if not s["enabled"]:
        await nm.stop()
    return ok({**nm.status(), "settings": s})


def _remote_port(ctx) -> int | None:
    """Remote listener port of THIS server (server.json of a crashed previous run is ignored)."""
    try:
        info = json.loads(ctx.paths.server_info.read_text())
        return int(info["remote"]) if int(info.get("pid", 0)) == os.getpid() else None
    except (OSError, ValueError, KeyError, TypeError):
        return None


def register(app: web.Application, ctx) -> None:
    r = app.router
    r.add_get("/api/deps", deps_get)
    r.add_post(f"/api/deps/{COMPONENT_RE}/install", deps_install)
    r.add_post(f"/api/deps/{COMPONENT_RE}/rollback", deps_rollback)
    r.add_get("/api/net", net_get)
    r.add_patch("/api/net", net_patch)
    r.add_post("/api/net/start", net_start)
    r.add_post("/api/net/stop", net_stop)
    s = _net_settings(ctx)
    nm = NetManager(ctx.publish, hostname=s["hostname"])
    app[NET] = nm
    ctx.net = nm            # the pairing screen's remote_url comes from this node's status

    def on_status(st: dict) -> None:
        names = app[REMOTE_HOSTS]
        dns = (st.get("dns_name") or "").rstrip(".")
        if dns:
            names.add(dns)
    nm.on_change.append(on_status)
    try:
        from ...deps import checker
        checker.register(ctx)
    except Exception:  # noqa: BLE001 (never block the server on the update checker)
        log.exception("deps checker not registered")

    async def autostart(_app: web.Application) -> None:
        if getattr(ctx, "demo", False) or os.environ.get("MADALEAN_NO_NET") == "1":
            return
        if not _net_settings(ctx)["enabled"] or deps.tool_info("madalean-net")["source"] != "prefix":
            return
        why = shared_node_blocked(ctx.paths.config)
        if why:
            # the node's state lives in the PREFIX (one Tailscale identity « madalean »): a dev checkout or a test
            # server (--config-dir) must never start a second node on it (incident 2026-11-21, session S-Q: it
            # took over the installed server's status socket). Explicit POST /api/net/start still works.
            log.info("Tailscale node not started automatically (%s)", why)
            return

        async def later():
            for _i in range(100):                 # the listeners are bound right after the app starts
                port = _remote_port(ctx)
                if port:
                    await nm.start(port)
                    return
                await asyncio.sleep(0.1)
            log.warning("remote listener port unknown: Tailscale node not started")
        ctx.spawn(later())

    async def cleanup(_app: web.Application) -> None:
        await nm.stop()
    app.on_startup.append(autostart)
    app.on_cleanup.append(cleanup)
