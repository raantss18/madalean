"""The subset of the Model Context Protocol that Madalean speaks (session S-AZ, DECISIONS D58, docs/MCP.md).

JSON-RPC 2.0 messages, one per line on stdio, one per POST on streamable HTTP. Madalean implements, as a server:
`initialize`, `notifications/initialized`, `ping`, `tools/list`, `tools/call`, `notifications/cancelled` (ignored:
calls are short and bounded); and as a client the same methods from the other side. Nothing else: no resources, no
prompts, no sampling, no roots, no elicitation (a server that asks for one of them gets « method not found »).
Batches (JSON arrays) were removed from the protocol in 2025-06-18 and are refused.

The official Python SDK was not vendored: it needs pydantic (compiled), starlette, uvicorn, httpx, anyio,
sse-starlette, pydantic-settings and jsonschema — a second web stack beside aiohttp, outside the signed conda lock.
The subset here is small, tested message by message (tests/test_mcp_server.py) and has no dependency."""
from __future__ import annotations

import json
from typing import Any

# newest first; the server answers the client's version when it knows it, else the newest
PROTOCOL_VERSIONS = ("2025-06-18", "2025-03-26", "2024-11-05")
LATEST = PROTOCOL_VERSIONS[0]
SERVER_NAME = "madalean"
MAX_MESSAGE = 2 * 1024 * 1024              # bytes of one JSON-RPC message (stdio line / HTTP body)

PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603
SERVER_UNAVAILABLE = -32000                 # implementation-defined: Madalean's server is off or not running

INSTRUCTIONS = (
    "Madalean is a Lean 4 + Mathlib proving assistant running on this computer. Lean is the only judge: "
    "`check_lean` answers with the strict verdict of a fresh Lean run (no sorry, no new axiom, standard axioms "
    "only). Search Mathlib before guessing a lemma name. Every result is data computed by Madalean; nothing is "
    "stored by these tools.")


class RpcError(Exception):
    def __init__(self, code: int, message: str, data: Any = None):
        super().__init__(message)
        self.code, self.message, self.data = code, message, data


def response(rid: Any, result: dict) -> dict:
    return {"jsonrpc": "2.0", "id": rid, "result": result}


def error_response(rid: Any, code: int, message: str, data: Any = None) -> dict:
    err: dict = {"code": code, "message": message}
    if data is not None:
        err["data"] = data
    return {"jsonrpc": "2.0", "id": rid, "error": err}


def parse(raw: bytes | str) -> tuple[dict | None, dict | None]:
    """(message, None) or (None, error response). The message is a JSON-RPC request, notification or response."""
    if isinstance(raw, bytes):
        if len(raw) > MAX_MESSAGE:
            return None, error_response(None, INVALID_REQUEST, "message too large")
        try:
            raw = raw.decode("utf-8")
        except UnicodeDecodeError:
            return None, error_response(None, PARSE_ERROR, "invalid UTF-8")
    if len(raw) > MAX_MESSAGE:
        return None, error_response(None, INVALID_REQUEST, "message too large")
    try:
        msg = json.loads(raw)
    except ValueError:
        return None, error_response(None, PARSE_ERROR, "parse error")
    if isinstance(msg, list):
        return None, error_response(None, INVALID_REQUEST, "batches are not supported (MCP 2025-06-18)")
    if not isinstance(msg, dict) or msg.get("jsonrpc") != "2.0":
        return None, error_response(msg.get("id") if isinstance(msg, dict) and _id_ok(msg.get("id")) else None,
                                    INVALID_REQUEST, "not a JSON-RPC 2.0 message")
    if "method" in msg:
        if not isinstance(msg["method"], str) or ("id" in msg and not _id_ok(msg["id"])):
            return None, error_response(None, INVALID_REQUEST, "invalid request")
        if "params" in msg and not isinstance(msg["params"], dict):
            return None, error_response(msg.get("id"), INVALID_REQUEST, "params must be an object")
        return msg, None
    if "id" in msg and ("result" in msg or "error" in msg):
        return msg, None                    # a response (the client side reads them)
    return None, error_response(None, INVALID_REQUEST, "invalid request")


def _id_ok(rid: Any) -> bool:
    # JSON-RPC ids are strings or numbers; MCP forbids null ids for requests
    return (isinstance(rid, str) and len(rid) <= 200) or (isinstance(rid, int) and not isinstance(rid, bool))


def is_request(msg: dict) -> bool:
    return "method" in msg and "id" in msg


def negotiate(requested: Any) -> str:
    return requested if isinstance(requested, str) and requested in PROTOCOL_VERSIONS else LATEST


def initialize_result(params: dict, version: str) -> dict:
    return {"protocolVersion": negotiate(params.get("protocolVersion")),
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": SERVER_NAME, "title": "Madalean", "version": version},
            "instructions": INSTRUCTIONS}


def text_result(data: Any, is_error: bool = False) -> dict:
    """A tools/call result: the data as JSON text (every client reads it) and as structured content."""
    text = data if isinstance(data, str) else json.dumps(data, ensure_ascii=False, indent=1, default=str)
    out: dict = {"content": [{"type": "text", "text": text}], "isError": bool(is_error)}
    if isinstance(data, dict):
        out["structuredContent"] = data
    return out
