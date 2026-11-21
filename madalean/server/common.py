"""Small helpers shared by the route modules."""
from __future__ import annotations

import json
import re
from typing import Any

from aiohttp import web

from ..i18n import msg

ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$")
MAX_JSON = 4 * 1024 * 1024

CTX = web.AppKey("ctx", object)
HOST_ONLY = web.AppKey("host_only", set)


def ctx_of(request: web.Request):
    return request.app[CTX]


def error(status: int, kind: str, key: str = "", **params: Any) -> web.Response:
    body: dict = {"error": kind}
    if key:
        body["message"] = msg(key, **params)
    return web.json_response(body, status=status)


def ok(data: Any = None, status: int = 200) -> web.Response:
    return web.json_response({} if data is None else data, status=status,
                             dumps=lambda o: json.dumps(o, ensure_ascii=False, default=str))


async def body(request: web.Request) -> dict:
    """JSON object body ({} when empty). Raises HTTPBadRequest on anything else."""
    if request.content_length and request.content_length > MAX_JSON:
        raise web.HTTPRequestEntityTooLarge(max_size=MAX_JSON, actual_size=request.content_length)
    raw = await request.read()
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except ValueError:
        raise web.HTTPBadRequest(text=json.dumps({"error": "bad_json"}), content_type="application/json")
    if not isinstance(data, dict):
        raise web.HTTPBadRequest(text=json.dumps({"error": "bad_json"}), content_type="application/json")
    return data


def valid_id(value: str) -> str:
    if not isinstance(value, str) or not ID_RE.match(value):
        raise web.HTTPBadRequest(text=json.dumps({"error": "bad_id"}), content_type="application/json")
    return value


def host_only(handler):
    """Mark a handler as reachable only from the local (trusted) listener."""
    handler.__madalean_host_only__ = True
    return handler
