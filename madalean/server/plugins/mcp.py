"""MCP API (session S-AZ, DECISIONS D58, docs/MCP.md). Every route is host-only (paired devices get 403).

    GET    /api/mcp                         Madalean's MCP server (switches, tools, how to connect a client) and the
                                            external servers
    POST   /api/mcp/rpc                     one JSON-RPC message from the stdio bridge (`madalean mcp serve`)
    POST   /api/mcp/http                    streamable HTTP transport (127.0.0.1 only, needs `mcp_server_http`)
    GET    /api/mcp/activity?dir=in|out     the latest tool calls (activity log)
    POST   /api/mcp/servers                 {name, transport: stdio|http, command | url} → an external server
                                            (disabled, nothing allowed)
    PATCH  /api/mcp/servers/{id}            {name?, enabled?, allowed?: [tool], timeout_s?}
    DELETE /api/mcp/servers/{id}
    POST   /api/mcp/servers/{id}/test       start it, list its tools, stop it"""
from __future__ import annotations

import json
import os
import shlex
from pathlib import Path

from aiohttp import web

from ... import config
from ...logs import get
from ...mcp import Hub, protocol as P
from ...mcp.client import MAX_TIMEOUT, McpClientError
from ...mcp.tools import REGISTRY, ToolEnv, listed
from ..common import body, ctx_of, error, host_only, ok

log = get("mcp")
ROOT = Path(__file__).resolve().parents[3]


def _hub(request) -> Hub:
    return ctx_of(request).mcp


def launcher() -> str:
    """The command a client should run: the installed `current` launcher (stable across updates), else this
    checkout's bin/madalean."""
    home = os.environ.get("MADALEAN_HOME", "")
    if home:
        p = Path(home) / "current" / "bin" / "madalean"
        if p.exists():
            return str(p)
    return str(ROOT / "bin" / "madalean")


def connect_info(ctx, port: int) -> dict:
    args = ["mcp", "serve"]
    if port != 11500:
        args += ["--port", str(port)]
    if Path(ctx.paths.config).resolve() != Path(config.HOME / ".config" / "madalean").resolve():
        args += ["--config-dir", str(ctx.paths.config)]
    cmd = launcher()
    url = f"http://127.0.0.1:{port}/api/mcp/http"
    return {"command": cmd, "args": args,
            "shell": shlex.join([cmd, *args]),
            "claude_code": shlex.join(["claude", "mcp", "add", "madalean", "--", cmd, *args]),
            "json": {"mcpServers": {"madalean": {"command": cmd, "args": args}}},
            "http_url": url,
            "claude_code_http": shlex.join(["claude", "mcp", "add", "--transport", "http", "madalean", url])}


def _port(request) -> int:
    t = request.transport
    sn = t.get_extra_info("sockname") if t else None
    return int(sn[1]) if sn else 11500


@host_only
async def mcp_get(request: web.Request) -> web.Response:
    ctx = ctx_of(request)
    h = _hub(request)
    s = ctx.settings
    on = {t.name for t in listed(ctx)}
    tools = [{**t.describe(), "available": t.name in on, "rate": t.rate} for t in REGISTRY.values()]
    return ok({"server": {"enabled": bool(s.mcp_server), "http": bool(s.mcp_server_http),
                          "sage": bool(s.mcp_server_sage), "tools": tools, "protocol": P.LATEST,
                          "connect": connect_info(ctx, _port(request))},
               "servers": [x.public() for x in h.store.servers.values()],
               "max_timeout": MAX_TIMEOUT})


@host_only
async def mcp_activity(request: web.Request) -> web.Response:
    d = request.query.get("dir", "")
    return ok({"activity": _hub(request).activity.list(100, d if d in ("in", "out") else "")})


async def _dispatch(request: web.Request, transport: str) -> web.Response:
    ctype = request.headers.get("Content-Type", "").split(";")[0].strip().lower()
    if ctype != "application/json":
        return error(415, "content_type")
    if request.content_length and request.content_length > P.MAX_MESSAGE:
        return error(413, "too_large")
    raw = await request.content.read(P.MAX_MESSAGE + 1)
    msg, err = P.parse(raw)
    if err is not None:
        return web.json_response(err, status=400)
    if not P.is_request(msg):
        return web.Response(status=202)            # notifications and responses: accepted, nothing to answer
    env = ToolEnv(ctx_of(request), request, transport)
    out = await _hub(request).server.handle(msg, env)
    return web.json_response(out, dumps=lambda o: json.dumps(o, ensure_ascii=False, default=str))


@host_only
async def mcp_rpc(request: web.Request) -> web.Response:
    if not ctx_of(request).settings.mcp_server:
        return error(403, "mcp_off")
    return await _dispatch(request, "stdio")


@host_only
async def mcp_http(request: web.Request) -> web.Response:
    s = ctx_of(request).settings
    if not (s.mcp_server and s.mcp_server_http):
        return error(403, "mcp_off")
    if request.method != "POST":
        # no server-initiated stream and no session to end: GET / DELETE are not offered (spec: 405)
        return web.json_response({"error": "method_not_allowed"}, status=405, headers={"Allow": "POST"})
    ver = request.headers.get("MCP-Protocol-Version")
    if ver is not None and ver not in P.PROTOCOL_VERSIONS:
        return error(400, "protocol_version")
    accept = request.headers.get("Accept", "*/*").lower()
    if not any(a in accept for a in ("application/json", "*/*", "application/*")):
        return error(406, "accept")
    return await _dispatch(request, "http")


def _server(request):
    s = _hub(request).store.servers.get(request.match_info["id"])
    if s is None:
        raise web.HTTPNotFound(text='{"error":"not_found"}', content_type="application/json")
    return s


def _client_error(e: McpClientError) -> web.Response:
    return web.json_response({"error": e.kind, "message": {"key": "", "params": {}, "text": str(e)}}, status=400)


@host_only
async def servers_add(request: web.Request) -> web.Response:
    ctx = ctx_of(request)
    data = await body(request)
    try:
        s = _hub(request).store.add(str(data.get("name") or ""), str(data.get("transport") or ""),
                                    command=str(data.get("command") or ""), url=str(data.get("url") or ""),
                                    mode=ctx.settings.mode)
    except McpClientError as e:
        return _client_error(e)
    ctx.publish("mcp.updated", {"server": s.id})
    return ok({"server": s.public()}, status=201)


@host_only
async def servers_patch(request: web.Request) -> web.Response:
    ctx = ctx_of(request)
    h = _hub(request)
    s = _server(request)
    data = await body(request)
    if "name" in data:
        from ...mcp.schema import clean_text
        s.name = clean_text(str(data["name"]), 80).strip() or s.name
    if "enabled" in data:
        s.enabled = bool(data["enabled"])
    if "allowed" in data:
        names = {t["name"] for t in s.tools if t.get("safe")}
        want = data["allowed"] if isinstance(data["allowed"], list) else []
        bad = [str(x)[:64] for x in want if x not in names]
        if bad:
            return error(400, "unknown_tools", "Champs refusés : {fields}.", fields=", ".join(bad[:5]))
        s.allowed = [x for x in want if x in names]
    if "timeout_s" in data:
        try:
            s.timeout_s = max(1, min(int(data["timeout_s"]), MAX_TIMEOUT))
        except (TypeError, ValueError):
            return error(400, "bad_fields", "Champs refusés : {fields}.", fields="timeout_s")
    h.store.save()
    if not s.enabled:
        await h.clients.drop(s.id)
    ctx.publish("mcp.updated", {"server": s.id})
    return ok({"server": s.public()})


@host_only
async def servers_delete(request: web.Request) -> web.Response:
    ctx = ctx_of(request)
    h = _hub(request)
    s = _server(request)
    await h.clients.drop(s.id)
    h.store.servers.pop(s.id, None)
    h.store.save()
    ctx.publish("mcp.updated", {"server": s.id, "removed": True})
    return ok({"removed": s.id})


@host_only
async def servers_test(request: web.Request) -> web.Response:
    ctx = ctx_of(request)
    s = _server(request)
    s = await _hub(request).clients.test(s.id)
    ctx.publish("mcp.updated", {"server": s.id})
    return ok({"server": s.public()})


def register(app: web.Application, ctx) -> None:
    ctx.mcp = Hub(ctx)

    async def startup(_app):
        if ctx.brain is not None:      # the conductor names the allowed external tools in its plans (D58)
            try:
                ctx.brain.mcp_tool_names = lambda: [f"{s.name}: {t['name']}" for s, t in
                                                    ctx.mcp.clients.allowed_tools()]
            except AttributeError:
                pass
    app.on_startup.append(startup)
    r = app.router
    r.add_get("/api/mcp", mcp_get)
    r.add_get("/api/mcp/activity", mcp_activity)
    r.add_post("/api/mcp/rpc", mcp_rpc)
    r.add_post("/api/mcp/http", mcp_http)
    r.add_get("/api/mcp/http", mcp_http, allow_head=False)        # 405: no server-initiated stream
    r.add_delete("/api/mcp/http", mcp_http)                       # 405: no session to end
    r.add_post("/api/mcp/servers", servers_add)
    r.add_patch("/api/mcp/servers/{id}", servers_patch)
    r.add_delete("/api/mcp/servers/{id}", servers_delete)
    r.add_post("/api/mcp/servers/{id}/test", servers_test)

    async def cleanup(_app):
        await ctx.mcp.clients.close_all()
    app.on_cleanup.append(cleanup)
