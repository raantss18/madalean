"""Native Anthropic Messages API client (streaming SSE, tool use, prompt caching, adaptive thinking), written
against the raw HTTP wire format documented in the claude-api skill (API version 2026-10-21). Raw HTTP instead of
the `anthropic` SDK so that every request goes through brain.net.Http (local-mode enforcement, key-host check,
one aiohttp stack, no new dependency) — see docs/BRAIN.md.

Rules followed (claude-api skill): no `temperature` (400 on 2026-10-21); `thinking: {type: adaptive}` and
`output_config.effort` instead of budget_tokens; `tool_choice: auto` only (forced choice is a 400 on Opus 5.5);
`eager_input_streaming` on client tools with strict JSON parsing at content_block_stop; system prompt cached with
`cache_control`; assistant content blocks (thinking + signature) replayed unchanged; server-side refusal fallback
(`fallbacks: "default"`, beta server-side-fallback-2026-07-01) on the models that accept it."""
from __future__ import annotations

import json

from ..guards import LoopGuard
from ..net import Http, HttpStatusError, NetworkError, StallError, sse_events
from ..state import context_too_long, wait_from_headers
from .base import ProviderError, StreamResult, ToolCall, emit, parse_args

API_VERSION = "2026-10-21"
FALLBACK_BETA = "server-side-fallback-2026-07-01"
FALLBACK_MODELS = ("claude-opus-5-5", "claude-sonnet-5-5", "claude-fable-5-2", "claude-fable-5-1", "claude-opus-5")
_STOP = {"end_turn": "stop", "stop_sequence": "stop", "pause_turn": "stop", "max_tokens": "length",
         "tool_use": "tool_use", "refusal": "refusal", "model_context_window_exceeded": "context"}
_ERR_STATUS = {"overloaded_error": 529, "rate_limit_error": 429, "api_error": 500, "authentication_error": 401,
               "permission_error": 403, "billing_error": 402, "invalid_request_error": 400,
               "request_too_large": 413, "not_found_error": 404}


def to_anthropic_tools(tools: list[dict]) -> list[dict]:
    """[{name, description, parameters}] -> Anthropic tool definitions (eager input streaming on)."""
    return [{"name": t["name"], "description": t["description"], "input_schema": t["parameters"],
             "eager_input_streaming": True} for t in tools]


def split_system(messages: list[dict]) -> tuple[str, list[dict]]:
    """OpenAI-style messages -> (system text, Anthropic messages) — for plain completions."""
    system, out = [], []
    for m in messages:
        role, content = m.get("role"), m.get("content")
        if role == "system":
            system.append(content if isinstance(content, str) else json.dumps(content))
            continue
        role = "assistant" if role == "assistant" else "user"
        if out and out[-1]["role"] == role and isinstance(out[-1]["content"], str) and isinstance(content, str):
            out[-1]["content"] += "\n\n" + content          # the API wants alternating turns
        else:
            out.append({"role": role, "content": content if content is not None else ""})
    return "\n\n".join(system), out


def build_body(model: str, system: str, messages: list[dict], *, max_tokens: int, tools: list[dict] | None,
               effort: str | None, thinking: bool, fallbacks: bool, cache: bool) -> tuple[dict, dict]:
    body: dict = {"model": model, "max_tokens": max_tokens, "stream": True, "messages": messages}
    if system:
        blk: dict = {"type": "text", "text": system}
        if cache:
            blk["cache_control"] = {"type": "ephemeral"}
        body["system"] = [blk]
    if cache:
        body["cache_control"] = {"type": "ephemeral"}       # automatic breakpoint on the growing conversation
    if thinking:
        body["thinking"] = {"type": "adaptive", "display": "summarized"}
    if effort:
        body["output_config"] = {"effort": effort}
    if tools:
        body["tools"] = to_anthropic_tools(tools)
        body["tool_choice"] = {"type": "auto"}
    headers = {"anthropic-version": API_VERSION}
    if fallbacks and model in FALLBACK_MODELS:
        body["fallbacks"] = "default"
        headers["anthropic-beta"] = FALLBACK_BETA
    return body, headers


async def stream_messages(http: Http, *, base_url: str, model: str, system: str, messages: list[dict], mode: str,
                          key: str | None, max_tokens: int = 16000, tools: list[dict] | None = None,
                          effort: str | None = None, thinking: bool = True, fallbacks: bool = True,
                          cache: bool = True, on_chunk=None, stall: float = 90.0,
                          first_byte: float = 120.0) -> StreamResult:
    body, headers = build_body(model, system, messages, max_tokens=max_tokens, tools=tools, effort=effort,
                               thinking=thinking, fallbacks=fallbacks, cache=cache)
    url = base_url.rstrip("/") + "/messages"
    for _attempt in range(4):
        try:
            return await _once(http, url, body, headers, mode=mode, key=key, on_chunk=on_chunk, stall=stall,
                               first_byte=first_byte)
        except HttpStatusError as e:
            low = e.message.lower()
            if e.status == 400:                    # optional features the account / model may refuse: drop, retry
                if ("anthropic-beta" in low or "fallbacks" in low) and "fallbacks" in body:
                    body.pop("fallbacks")
                    headers.pop("anthropic-beta", None)
                    continue
                if "output_config" in low or "effort" in low:
                    if body.pop("output_config", None) is not None:
                        continue
                if "thinking" in low and "signature" not in low and "thinking" in body:
                    body.pop("thinking")
                    continue
                if "cache_control" in low and "cache_control" in body:
                    body.pop("cache_control")
                    continue
            if context_too_long(e.status, e.message):
                raise ProviderError("context", e.message, e.status) from e
            raise ProviderError("http", e.message, e.status, wait_from_headers(e.headers)) from e
        except StallError as e:
            raise ProviderError("stall", str(e)) from e
        except NetworkError as e:
            raise ProviderError("network", str(e)) from e
    raise ProviderError("bad_param", "request rejected", 400)


async def _once(http: Http, url: str, body: dict, headers: dict, *, mode: str, key: str | None, on_chunk,
                stall: float, first_byte: float) -> StreamResult:
    res = StreamResult()
    blocks: dict[int, dict] = {}
    partial: dict[int, list[str]] = {}
    guard = LoopGuard()
    started = False
    async with http.stream(url, body, mode=mode, provider="anthropic", key=key, headers=headers,
                           first_byte_timeout=first_byte) as resp:
        async for event, data in sse_events(resp, stall):
            try:
                v = json.loads(data)
            except ValueError:
                continue
            if not isinstance(v, dict):
                continue
            t = v.get("type") or event
            if event == "json":                         # non-streamed answer (should not happen with stream: true)
                if v.get("type") == "error":
                    _raise_error(v)
                for i, b in enumerate(v.get("content") or []):
                    blocks[i] = b
                    if b.get("type") == "text":
                        emit(on_chunk, "text", b.get("text", ""))
                res.finish = _STOP.get(v.get("stop_reason") or "", "stop")
                _usage(res, v.get("usage"))
                res.model_reported = v.get("model") or ""
                started = True
                break
            if t == "error":
                _raise_error(v)
            if t == "message_start":
                started = True
                msg = v.get("message") or {}
                res.model_reported = msg.get("model") or ""
                _usage(res, msg.get("usage"))
            elif t == "content_block_start":
                i = int(v.get("index", len(blocks)))
                b = dict(v.get("content_block") or {})
                if b.get("type") == "tool_use":
                    b["input"] = {}
                    partial[i] = []
                blocks[i] = b
            elif t == "content_block_delta":
                i = int(v.get("index", 0))
                d = v.get("delta") or {}
                b = blocks.setdefault(i, {"type": "text", "text": ""})
                dt = d.get("type")
                if dt == "text_delta":
                    piece = d.get("text", "")
                    b["text"] = b.get("text", "") + piece
                    emit(on_chunk, "text", piece)
                    guard.feed(piece)
                elif dt == "thinking_delta":
                    piece = d.get("thinking", "")
                    b["thinking"] = b.get("thinking", "") + piece
                    emit(on_chunk, "thinking", piece)
                    guard.feed(piece)
                elif dt == "signature_delta":
                    b["signature"] = b.get("signature", "") + d.get("signature", "")
                elif dt == "input_json_delta":
                    partial.setdefault(i, []).append(d.get("partial_json", ""))
            elif t == "content_block_stop":
                i = int(v.get("index", 0))
                b = blocks.get(i)
                if b is not None and b.get("type") == "tool_use":
                    raw = "".join(partial.get(i, []))
                    args, err = parse_args(raw)
                    b["input"] = args if args is not None else {}
                    b["_raw"], b["_err"] = raw, err
            elif t == "message_delta":
                d = v.get("delta") or {}
                if d.get("stop_reason"):
                    res.finish = _STOP.get(d["stop_reason"], "stop")
                _usage(res, v.get("usage"))
            elif t == "message_stop":
                break
            if guard.tripped:
                break
    if not started:
        raise ProviderError("empty", "empty stream")
    ordered = [blocks[i] for i in sorted(blocks)]
    last_fb = max((k for k, b in enumerate(ordered) if b.get("type") == "fallback"), default=-1)
    keep: list[dict] = []
    for k, b in enumerate(ordered):
        bt = b.get("type")
        if k < last_fb and bt not in ("text", "fallback"):
            continue                                    # echo rule after a mid-output refusal fallback
        if bt not in ("text", "thinking", "redacted_thinking", "tool_use", "fallback"):
            continue
        keep.append(b)
    texts, thinks = [], []
    for b in keep:
        bt = b.get("type")
        if bt == "text":
            texts.append(b.get("text", ""))
        elif bt == "thinking":
            thinks.append(b.get("thinking", ""))
        elif bt == "tool_use":
            res.tool_calls.append(ToolCall(b.get("id", ""), b.get("name", ""), b.pop("_raw", json.dumps(b.get("input") or {})),
                                           None if b.get("_err") else b.get("input"), b.pop("_err", "")))
            b.pop("_err", None)
    res.raw_blocks = [{k: v for k, v in b.items() if not k.startswith("_")} for b in keep]
    res.text, res.thinking = "".join(texts), "\n".join(thinks)
    if guard.tripped:
        res.finish = "loop"
        res.text = guard.cut(res.text)
    if res.finish in ("length", "refusal") and res.tool_calls:
        for c in res.tool_calls:                         # never run a truncated / refused tool call
            c.input, c.error = None, c.error or f"tool call cut by stop_reason={res.finish}"
    return res


def _raise_error(v: dict) -> None:
    e = v.get("error") or {}
    et = e.get("type", "api_error")
    status = _ERR_STATUS.get(et, 500)
    msg = e.get("message") or et
    if context_too_long(status, msg):
        raise ProviderError("context", msg, status)
    raise ProviderError("http", f"{et}: {msg}", status)


def _usage(res: StreamResult, u) -> None:
    if not isinstance(u, dict):
        return
    if u.get("input_tokens") is not None:
        res.cache_read = int(u.get("cache_read_input_tokens") or res.cache_read or 0)
        res.cache_write = int(u.get("cache_creation_input_tokens") or res.cache_write or 0)
        res.tokens_in = int(u["input_tokens"]) + res.cache_read + res.cache_write
    if u.get("output_tokens") is not None:
        res.tokens_out = int(u["output_tokens"])
