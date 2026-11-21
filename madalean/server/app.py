"""The aiohttp application and its listeners.

`make_app(ctx)` builds the app (routes, security middleware, plugins); `Server` runs it on the local listener
(127.0.0.1:11500, trusted), the remote listener (127.0.0.1:11501, token required) and the optional LAN listener."""
from __future__ import annotations

import asyncio
import importlib
import json
import os
import pkgutil
import signal
import warnings
from pathlib import Path
from typing import Callable

from aiohttp import web

from .. import config
from ..logs import get
from . import plugins as plugins_pkg
from .auth import LOCAL_PORTS, security_middleware
from .common import CTX
from .routes_core import routes as core_routes
from .routes_extra import routes as extra_routes
from .routes_misc import ASSIST, STATIC_DIR, jupyter_proxy, routes as misc_routes, static_handler
from .routes_work import routes as work_routes

log = get("server")
# request["local"] / request["device"] are plain string keys on purpose (documented for plugins)
warnings.filterwarnings("ignore", category=getattr(web, "NotAppKeyWarning", Warning), message=".*RequestKey.*")
DEFAULT_STATIC = Path(__file__).resolve().parents[1] / "static"
Plugin = Callable[[web.Application, object], None]


def discover_plugins() -> list[Plugin]:
    out = []
    for info in pkgutil.iter_modules(plugins_pkg.__path__):
        try:
            mod = importlib.import_module(f"{plugins_pkg.__name__}.{info.name}")
        except Exception:  # noqa: BLE001 (a broken plugin must not stop the server)
            log.exception("plugin %s failed to import", info.name)
            continue
        fn = getattr(mod, "register", None)
        if callable(fn):
            out.append(fn)
    return out


def register(app: web.Application, ctx, plugin: Plugin) -> None:
    """Plugin hook: call `plugin(app, ctx)` before the catch-all routes are added."""
    plugin(app, ctx)


def make_app(ctx, static_dir: Path | None = None, extra_plugins: list[Plugin] | None = None) -> web.Application:
    app = web.Application(middlewares=[security_middleware], client_max_size=16 * 1024 * 1024)
    app[CTX] = ctx
    app[LOCAL_PORTS] = set()
    app[ASSIST] = {}
    app[STATIC_DIR] = Path(static_dir or DEFAULT_STATIC)
    app.add_routes(core_routes)
    app.add_routes(work_routes)
    app.add_routes(extra_routes)
    app.add_routes(misc_routes)
    for fn in discover_plugins() + list(extra_plugins or []):
        try:
            register(app, ctx, fn)
        except Exception:  # noqa: BLE001
            log.exception("plugin %r failed", fn)
    app.router.add_route("*", "/jupyter", jupyter_proxy)
    app.router.add_route("*", "/jupyter/{tail:.*}", jupyter_proxy)
    app.router.add_route("*", "/api/{tail:.*}", _api_404)
    app.router.add_get("/{tail:.*}", static_handler)
    return app


async def _api_404(request: web.Request) -> web.Response:
    return web.json_response({"error": "not_found"}, status=404)


class Server:
    def __init__(self, ctx, local_port: int = 11500, remote_port: int = 11501, static_dir: Path | None = None,
                 lan: bool | None = None):
        self.ctx = ctx
        self.local_port, self.remote_port = local_port, remote_port
        self.static_dir = static_dir
        self.lan = lan
        self.app: web.Application | None = None
        self.runner: web.AppRunner | None = None
        self.ports: dict[str, int] = {}

    async def start(self) -> dict[str, int]:
        await self.ctx.start()
        self.app = make_app(self.ctx, self.static_dir)
        self.runner = web.AppRunner(self.app, access_log=None, shutdown_timeout=5)
        await self.runner.setup()
        local = web.TCPSite(self.runner, "127.0.0.1", self.local_port, reuse_address=True)
        await local.start()
        self.ports["local"] = local._server.sockets[0].getsockname()[1]
        self.app[LOCAL_PORTS].add(self.ports["local"])
        remote = web.TCPSite(self.runner, "127.0.0.1", self.remote_port, reuse_address=True)
        await remote.start()
        self.ports["remote"] = remote._server.sockets[0].getsockname()[1]
        s = self.ctx.settings
        if self.lan if self.lan is not None else s.lan_listener:
            lan = web.TCPSite(self.runner, "0.0.0.0", s.lan_port, reuse_address=True)
            await lan.start()
            self.ports["lan"] = lan._server.sockets[0].getsockname()[1]
        info = {"pid": os.getpid(), **self.ports, "version": self.ctx.version, "demo": self.ctx.demo}
        await asyncio.to_thread(config.atomic_write_text, self.ctx.paths.server_info, json.dumps(info))
        log.info("madalean listening: local 127.0.0.1:%s, remote 127.0.0.1:%s%s", self.ports["local"],
                 self.ports["remote"], f", LAN 0.0.0.0:{self.ports['lan']}" if "lan" in self.ports else "")
        return self.ports

    async def stop(self) -> None:
        log.info("stopping")
        for t in list((self.app or {}).get(ASSIST, {}).values()) if self.app else []:
            t.cancel()
        try:
            await self.ctx.stop()
        finally:
            if self.runner is not None:
                await self.runner.cleanup()
            try:
                self.ctx.paths.server_info.unlink()
            except OSError:
                pass


async def serve_forever(server: Server) -> None:
    loop = asyncio.get_running_loop()
    stop = asyncio.Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop.set)
        except (NotImplementedError, RuntimeError):
            pass
    await server.start()
    try:
        await stop.wait()
    finally:
        await server.stop()
