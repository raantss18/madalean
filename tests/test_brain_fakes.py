"""Fake OpenAI-compatible and Anthropic servers that mimic the real wire formats (SSE), for the brain tests.
(No tests here: helpers imported by the other test_brain_* modules.)"""
from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from aiohttp import web


@dataclass
class Rec:
    path: str
    headers: dict
    body: Any


@dataclass
class FakeServer:
    """Scripted HTTP server. `script` items are consumed in order (the last one repeats)."""
    script: list[Any] = field(default_factory=list)
    host: str = "127.0.0.1"
    requests: list[Rec] = field(default_factory=list)
    port: int = 0
    runner: web.AppRunner | None = None
    models: list[dict] = field(default_factory=list)
    closed_early: int = 0

    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.port}/v1"

    async def start(self) -> "FakeServer":
        app = web.Application()
        app.router.add_route("*", "/{tail:.*}", self.handle)
        self.runner = web.AppRunner(app)
        await self.runner.setup()
        site = web.TCPSite(self.runner, "127.0.0.1", 0)
        await site.start()
        self.port = site._server.sockets[0].getsockname()[1]
        return self

    async def stop(self) -> None:
        if self.runner:
            await self.runner.cleanup()

    async def handle(self, req: web.Request) -> web.StreamResponse:
        raw = await req.read()
        try:
            body = json.loads(raw) if raw else None
        except ValueError:
            body = raw.decode()
        self.requests.append(Rec(req.path, dict(req.headers), body))
        if req.method == "GET" and req.path.endswith("/models"):
            return web.json_response({"data": self.models})
        item = self.script[0] if len(self.script) == 1 else (self.script.pop(0) if self.script else {"status": 500})
        if callable(item):
            item = item(body)
        if "status" in item and item["status"] >= 400:
            return web.json_response(item.get("body", {"error": {"message": "error"}}), status=item["status"],
                                     headers=item.get("headers"))
        if "json" in item:
            return web.json_response(item["json"])
        resp = web.StreamResponse(headers={"Content-Type": "text/event-stream", "Cache-Control": "no-cache"})
        await resp.prepare(req)
        try:
            for ev in item["events"]:
                if isinstance(ev, (int, float)):
                    await asyncio.sleep(ev)
                    continue
                await resp.write(ev.encode())
            if item.get("hang"):
                await asyncio.sleep(item["hang"])
        except (ConnectionResetError, asyncio.CancelledError):
            self.closed_early += 1
            raise
        return resp


# ------------------------------------------------------------------ OpenAI SSE
def oa_chunk(delta: dict, finish: str | None = None, model: str = "fake") -> str:
    return "data: " + json.dumps({"model": model, "choices": [{"index": 0, "delta": delta, "finish_reason": finish}]}) + "\n\n"


def oa_stream(text: str = "", tool_calls: list[tuple[str, str, dict]] | None = None, finish: str | None = None,
              pieces: int = 3, reasoning: str = "", usage: tuple[int, int] = (11, 7)) -> dict:
    ev: list = []
    if reasoning:
        ev.append(oa_chunk({"role": "assistant", "reasoning_content": reasoning}))
    if text:
        n = max(1, len(text) // pieces)
        for i in range(0, len(text), n):
            ev.append(oa_chunk({"content": text[i:i + n]}))
    for k, (cid, name, args) in enumerate(tool_calls or []):
        a = json.dumps(args)
        ev.append(oa_chunk({"tool_calls": [{"index": k, "id": cid, "type": "function", "function": {"name": name, "arguments": a[:5]}}]}))
        ev.append(oa_chunk({"tool_calls": [{"index": k, "function": {"arguments": a[5:]}}]}))
    ev.append(oa_chunk({}, finish or ("tool_calls" if tool_calls else "stop")))
    ev.append("data: " + json.dumps({"choices": [], "usage": {"prompt_tokens": usage[0], "completion_tokens": usage[1]}}) + "\n\n")
    ev.append("data: [DONE]\n\n")
    return {"events": ev}


# ------------------------------------------------------------------ Anthropic SSE
def an_event(name: str, data: dict) -> str:
    return f"event: {name}\ndata: {json.dumps(data)}\n\n"


def an_stream(blocks: list[tuple], stop: str | None = None, model: str = "claude-opus-5-5",
              usage: tuple[int, int] = (20, 9), error: dict | None = None) -> dict:
    """blocks: ("thinking", text, signature) | ("text", text) | ("tool_use", id, name, input_dict)."""
    ev = [an_event("message_start", {"type": "message_start", "message": {
        "id": "msg_fake", "type": "message", "role": "assistant", "model": model, "content": [], "stop_reason": None,
        "usage": {"input_tokens": usage[0], "output_tokens": 1, "cache_read_input_tokens": 0,
                  "cache_creation_input_tokens": 0}}}),
          an_event("ping", {"type": "ping"})]
    for i, b in enumerate(blocks):
        kind = b[0]
        if kind == "thinking":
            ev.append(an_event("content_block_start", {"type": "content_block_start", "index": i,
                                                       "content_block": {"type": "thinking", "thinking": "", "signature": ""}}))
            ev.append(an_event("content_block_delta", {"type": "content_block_delta", "index": i,
                                                       "delta": {"type": "thinking_delta", "thinking": b[1]}}))
            ev.append(an_event("content_block_delta", {"type": "content_block_delta", "index": i,
                                                       "delta": {"type": "signature_delta", "signature": b[2]}}))
        elif kind == "text":
            ev.append(an_event("content_block_start", {"type": "content_block_start", "index": i,
                                                       "content_block": {"type": "text", "text": ""}}))
            half = len(b[1]) // 2
            for part in (b[1][:half], b[1][half:]):
                ev.append(an_event("content_block_delta", {"type": "content_block_delta", "index": i,
                                                           "delta": {"type": "text_delta", "text": part}}))
        elif kind == "tool_use":
            ev.append(an_event("content_block_start", {"type": "content_block_start", "index": i, "content_block": {
                "type": "tool_use", "id": b[1], "name": b[2], "input": {}}}))
            a = json.dumps(b[3])
            for part in (a[:4], a[4:]):
                ev.append(an_event("content_block_delta", {"type": "content_block_delta", "index": i,
                                                           "delta": {"type": "input_json_delta", "partial_json": part}}))
        ev.append(an_event("content_block_stop", {"type": "content_block_stop", "index": i}))
    if error:
        ev.append(an_event("error", {"type": "error", "error": error}))
        return {"events": ev}
    has_tool = any(b[0] == "tool_use" for b in blocks)
    ev.append(an_event("message_delta", {"type": "message_delta", "delta": {
        "stop_reason": stop or ("tool_use" if has_tool else "end_turn"), "stop_sequence": None},
        "usage": {"output_tokens": usage[1]}}))
    ev.append(an_event("message_stop", {"type": "message_stop"}))
    return {"events": ev}


# ------------------------------------------------------------------ brain factory
def write_catalogue(config_dir: Path, providers: list[dict], models: list[dict]) -> None:
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "brain-catalogue.json").write_text(json.dumps({"updated": time.time(), "providers": providers,
                                                                  "models": models}))


def free_provider(pid: str, url: str) -> dict:
    return {"id": pid, "name": pid, "base_url": url, "keyed": False, "paid": False, "api": "openai", "local": False,
            "free_suffix": None, "key_url": ""}


def model(pid: str, mid: str, q: float = 0.6, tools: bool = True, **kw) -> dict:
    d = {"provider": pid, "model_id": mid, "name": mid, "tools": tools, "vision": False,
         "quality": {c: q for c in ("chat", "code", "math", "reasoning", "writing")}, "local": False, "paid": False,
         "context": 0}
    d.update(kw)
    return d


def make_brain(config_dir: Path, *, keys: dict | None = None, endpoints: dict | None = None, local=None, **settings):
    from madalean.brain import create_brain
    keys = keys or {}
    st = {"refresh_catalogue": False, "_offline": settings.pop("_offline", False), "ollama": False, "stall_online": 5, "_endpoints": endpoints or {}}
    st.update(settings)
    b = create_brain(config_dir, local, lambda p: keys.get(p), st)
    real_check = b.http.check

    def loopback_only(url, mode, provider=None, key=None):     # tests never reach the Internet
        from madalean.brain.net import LocalModeViolation, host_of, is_loopback_host
        if not is_loopback_host(host_of(url)):
            raise LocalModeViolation(host_of(url))
        return real_check(url, mode, provider, key)
    b.http.check = loopback_only

    async def offline(mode="auto"):
        return False
    if not settings.get("_allow_probe"):
        b.http.online = offline if st.get("_offline") else _always_online
    return b


async def _always_online(mode="auto"):
    from madalean.brain.net import CALL_MODE
    return mode != "local" and CALL_MODE.get() != "local"


def run(coro):
    return asyncio.run(coro)
