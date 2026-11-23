"""Madalean as an MCP server: the JSON-RPC dispatcher shared by both transports (session S-AZ, DECISIONS D58).

- stdio: `madalean mcp serve` (mcp/bridge.py), launched by the client, relays each message to the running server's
  host-only `POST /api/mcp/rpc`;
- streamable HTTP: `POST /api/mcp/http` on the local listener (127.0.0.1), host-only, off unless the host turns it
  on (`mcp_server_http`).
Both end here, inside the server process, where the tools find the Lean runner, the index, the library and the
dossiers. The dispatcher is stateless (no session id): every request carries everything it needs."""
from __future__ import annotations

import asyncio
import json
import time
from typing import Any

from .. import __version__
from ..logs import get
from . import protocol as P
from .activity import ActivityLog, RateLimiter
from .schema import validate
from .tools import REGISTRY, ToolEnv, ToolError, listed, safe_name

log = get("mcp")
GLOBAL_RATE = 120              # tool calls per minute, all tools together
CALL_TIMEOUT = 600             # seconds, whatever the tool (check_lean is bounded by its own timeout first)


class ServerSide:
    def __init__(self, activity: ActivityLog):
        self.activity = activity
        self.limits = RateLimiter()

    async def handle(self, msg: dict, env: ToolEnv) -> dict | None:
        """One parsed message → its response (None for notifications and responses)."""
        if not P.is_request(msg):
            return None                        # notifications/initialized, notifications/cancelled…: nothing to say
        rid, method, params = msg["id"], msg["method"], msg.get("params") or {}
        try:
            return P.response(rid, await self._method(method, params, env))
        except P.RpcError as e:
            return P.error_response(rid, e.code, e.message, e.data)
        except Exception:  # noqa: BLE001
            log.exception("mcp %s", method)
            return P.error_response(rid, P.INTERNAL_ERROR, "internal error")

    async def _method(self, method: str, params: dict, env: ToolEnv) -> dict:
        if method == "initialize":
            return P.initialize_result(params, __version__)
        if method == "ping":
            return {}
        if method == "tools/list":
            return {"tools": [t.describe() for t in listed(env.ctx)]}
        if method == "tools/call":
            return await self.call(params, env)
        raise P.RpcError(P.METHOD_NOT_FOUND, f"method not found: {method[:80]}")

    async def call(self, params: dict, env: ToolEnv) -> dict:
        name, args = params.get("name"), params.get("arguments")
        args = {} if args is None else args
        tool = REGISTRY.get(name) if isinstance(name, str) else None
        if tool is None or tool not in listed(env.ctx):
            self.activity.record(direction="in", transport=env.transport, tool=safe_name(name), ok=False, ms=0,
                                 error="unknown tool")
            raise P.RpcError(P.INVALID_PARAMS, f"unknown tool: {safe_name(name)}")
        problems = validate(args, tool.input_schema)
        if problems:
            self.activity.record(direction="in", transport=env.transport, tool=tool.name, ok=False, ms=0,
                                 error="invalid arguments")
            raise P.RpcError(P.INVALID_PARAMS, "invalid arguments", {"problems": problems[:20]})
        wait = self.limits.check("*", GLOBAL_RATE) or self.limits.check(tool.name, tool.rate)
        if wait:
            self.activity.record(direction="in", transport=env.transport, tool=tool.name, ok=False, ms=0,
                                 args=args, error="rate limited")
            return P.text_result({"error": "rate_limited", "message": f"too many calls, retry in {wait} s",
                                  "retry_after": wait}, is_error=True)
        t0 = time.monotonic()
        try:
            data = await asyncio.wait_for(tool.run(env, args), CALL_TIMEOUT)
            out = P.text_result(data)
            ok, err = True, ""
        except ToolError as e:
            out = P.text_result({"error": e.kind, "message": e.message, **e.extra}, is_error=True)
            ok, err = False, f"{e.kind}: {e.message}"
        except asyncio.TimeoutError:
            out = P.text_result({"error": "timeout", "message": "the tool did not finish in time"}, is_error=True)
            ok, err = False, "timeout"
        size = len(out["content"][0]["text"])
        self.activity.record(direction="in", transport=env.transport, tool=tool.name, ok=ok,
                             ms=(time.monotonic() - t0) * 1000, args=args, out_size=size, error=err)
        return out


def dumps(msg: Any) -> str:
    """One line of JSON (no raw newline inside: stdio framing)."""
    return json.dumps(msg, ensure_ascii=False, separators=(",", ":"))
