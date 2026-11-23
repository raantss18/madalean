"""`madalean mcp serve`: the stdio transport of Madalean's MCP server (session S-AZ, DECISIONS D58).

An MCP client (Claude Code, Claude Desktop, another agent of this computer) launches this command and talks to it
on stdin / stdout, one JSON-RPC message per line. The bridge answers `initialize` and `ping` itself and relays
`tools/list` and `tools/call` to the running Madalean server (`POST /api/mcp/rpc` on the local listener,
127.0.0.1:<port>), where the tools live — the Lean runner, the declaration index, the library and the dossiers
belong to that one process. Nothing but protocol messages is written to stdout; diagnostics go to stderr.

When the server is not running, or when the host has not switched « Madalean comme serveur MCP » on, the relayed
requests answer a JSON-RPC error that says so (code -32000)."""
from __future__ import annotations

import json
import sys
import threading
import urllib.error
import urllib.request

from .. import __version__
from . import protocol as P

RELAYED = {"tools/list", "tools/call"}
HTTP_TIMEOUT = 660


class Bridge:
    def __init__(self, port: int, out=None, err=None):
        self.url = f"http://127.0.0.1:{port}/api/mcp/rpc"
        self.port = port
        self.out = out or sys.stdout
        self.err = err or sys.stderr
        self._lock = threading.Lock()
        self._opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        self.threads: list[threading.Thread] = []

    def write(self, msg: dict) -> None:
        line = json.dumps(msg, ensure_ascii=False, separators=(",", ":"))
        with self._lock:
            self.out.write(line + "\n")
            self.out.flush()

    def note(self, text: str) -> None:
        try:
            self.err.write(f"madalean mcp: {text}\n")
            self.err.flush()
        except (OSError, ValueError):
            pass

    def relay(self, msg: dict) -> dict:
        data = json.dumps(msg, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(self.url, data=data, method="POST", headers={
            "Content-Type": "application/json", "Accept": "application/json", "X-Madalean-MCP": "stdio"})
        try:
            with self._opener.open(req, timeout=HTTP_TIMEOUT) as r:
                body = json.loads(r.read().decode("utf-8") or "{}")
        except urllib.error.HTTPError as e:
            try:
                body = json.loads(e.read().decode("utf-8") or "{}")
            except ValueError:
                body = {}
            kind = body.get("error") if isinstance(body, dict) else ""
            if kind == "mcp_off":
                return P.error_response(msg["id"], P.SERVER_UNAVAILABLE, "Madalean as an MCP server is switched off "
                                        "(Madalean › Réglages › Outils (MCP))")
            return P.error_response(msg["id"], P.SERVER_UNAVAILABLE, f"Madalean refused the request (HTTP {e.code})")
        except (urllib.error.URLError, OSError, ValueError) as e:
            self.note(f"server not reachable: {e}")
            return P.error_response(msg["id"], P.SERVER_UNAVAILABLE,
                                    f"Madalean is not running on 127.0.0.1:{self.port} (start it, then retry)")
        if not isinstance(body, dict) or body.get("id") != msg["id"]:
            return P.error_response(msg["id"], P.INTERNAL_ERROR, "unexpected answer from Madalean")
        return body

    def handle(self, msg: dict) -> dict | None:
        if not P.is_request(msg):
            return None
        method, params = msg["method"], msg.get("params") or {}
        if method == "initialize":
            return P.response(msg["id"], P.initialize_result(params, __version__))
        if method == "ping":
            return P.response(msg["id"], {})
        if method in RELAYED:
            return self.relay(msg)
        return P.error_response(msg["id"], P.METHOD_NOT_FOUND, f"method not found: {method[:80]}")

    def _work(self, msg: dict) -> None:
        try:
            out = self.handle(msg)
        except Exception as e:  # noqa: BLE001
            self.note(f"internal error: {type(e).__name__}")
            out = P.error_response(msg.get("id"), P.INTERNAL_ERROR, "internal error") if P.is_request(msg) else None
        if out is not None:
            self.write(out)

    def serve(self, stdin=None) -> int:
        stdin = stdin or sys.stdin.buffer
        while True:
            line = stdin.readline(P.MAX_MESSAGE + 1)
            if not line:
                break
            if not line.strip():
                continue
            msg, err = P.parse(line)
            if err is not None:
                if len(line) > P.MAX_MESSAGE and not line.endswith(b"\n"):
                    while (rest := stdin.readline(P.MAX_MESSAGE)) and not rest.endswith(b"\n"):
                        pass                       # drop the rest of an oversized line
                self.write(err)
                continue
            if msg.get("method") in RELAYED:       # relayed calls run concurrently (ping stays answered)
                t = threading.Thread(target=self._work, args=(msg,), daemon=True)
                self.threads = [x for x in self.threads if x.is_alive()] + [t]
                t.start()
            else:
                self._work(msg)
        for t in self.threads:
            t.join(timeout=HTTP_TIMEOUT)
        return 0


def main(port: int) -> int:
    return Bridge(port).serve()
