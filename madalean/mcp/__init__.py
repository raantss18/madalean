"""Model Context Protocol support (session S-AZ, DECISIONS D58, docs/MCP.md).

- protocol.py — the JSON-RPC / MCP subset spoken both ways (no dependency: the official SDK is not vendored, D58);
- schema.py — strict input validation, sanitising of external schemas;
- tools.py — the tools Madalean offers (registry: new tools plug in with `register`);
- server.py — the dispatcher of Madalean's MCP server (stdio bridge and streamable HTTP end there);
- bridge.py — `madalean mcp serve`, the stdio transport;
- client.py — external MCP servers the user adds, offered to the prover agent as untrusted tools;
- activity.py — the activity log of every call, both directions, and the rate limits.

`Hub` (one per server context, `ctx.mcp`, created by server/plugins/mcp.py) holds the shared pieces. Importing this
package costs nothing: the bridge must start fast."""
from __future__ import annotations

from pathlib import Path


class Hub:
    def __init__(self, ctx):
        from .activity import ActivityLog
        from .client import McpClients, ServerStore
        from .server import ServerSide
        paths = ctx.paths
        self.activity = ActivityLog(Path(paths.logs) / "mcp-activity.jsonl")
        self.server = ServerSide(self.activity)
        self.store = ServerStore(Path(paths.config) / "mcp-servers.json")
        self.clients = McpClients(self.store, self.activity, Path(paths.cache) / "mcp",
                                  mode=lambda: getattr(ctx.settings, "mode", "auto"))


def hub_of(ctx) -> Hub | None:
    return getattr(ctx, "mcp", None)


def agent_tools(ctx) -> list:
    """The external tools the prover agent may call (empty when none is enabled and allowed)."""
    h = hub_of(ctx)
    if h is None:
        return []
    try:
        return h.clients.agent_tools()
    except Exception:  # noqa: BLE001 (never break a proof search over an external tool)
        return []
