"""Async face of the installer for the server: one install at a time per component, progress forwarded as
WebSocket events `deps.progress` ({"component", "phase", "done", "total", "message"}), on-demand components.

For other sessions (e.g. the Sage experiments): `await madalean.deps.service.ensure("sage", ctx.publish)` returns
when the component is installed (installing it first, with progress events) and raises `InstallError` otherwise."""
from __future__ import annotations

import asyncio
from typing import Callable

from . import health
from .installer import InstallError, install, load_state, rollback

_LOCKS: dict[str, asyncio.Lock] = {}
JOBS: dict[str, dict] = {}          # component -> last progress event / result (shown by GET /api/deps)


def _lock(name: str) -> asyncio.Lock:
    if name not in _LOCKS:
        _LOCKS[name] = asyncio.Lock()
    return _LOCKS[name]


def is_installed(name: str) -> bool:
    for c in health.components():
        if c["component"] == name:
            return c["state"] in ("ok", "outdated")
    return False


async def install_async(name: str, publish: Callable[[str, dict], None] | None = None, **kw) -> dict:
    loop = asyncio.get_running_loop()

    def progress(e: dict) -> None:
        JOBS[name] = {**e, "running": e["phase"] not in ("done", "error")}
        if publish is not None:
            loop.call_soon_threadsafe(lambda: publish("deps.progress", dict(e)))
    async with _lock(name):
        JOBS[name] = {"component": name, "phase": "queued", "running": True}
        try:
            r = await asyncio.to_thread(install, name, progress, **kw)
        except InstallError as e:
            JOBS[name] = {"component": name, "phase": "error", "message": str(e)[:500], "running": False}
            raise
        JOBS[name] = {"component": name, "phase": "done", "message": r.get("version", ""), "running": False}
        return r


async def ensure(name: str, publish: Callable[[str, dict], None] | None = None) -> dict:
    """Install `name` if it is not installed yet (on-demand components such as `sage`)."""
    if is_installed(name):
        return load_state().get(name, {})
    return await install_async(name, publish)


async def rollback_async(name: str) -> dict:
    async with _lock(name):
        return await asyncio.to_thread(rollback, name)
