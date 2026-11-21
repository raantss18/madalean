"""OpenAI-compatible streaming client (/chat/completions): keyless free providers, OpenRouter, Gemini's
OpenAI-compatible endpoint, Groq…, Ollama and the local llama-server. Ported from L Katta's flux.rs / moteur.rs
(`lire`, temperature / tools retries) and Lean AI Station's ChatStream (loop guard, stall watchdog)."""
from __future__ import annotations

import json

from ..guards import LoopGuard
from ..net import Http, HttpStatusError, NetworkError, StallError, sse_events
from ..state import context_too_long, wait_from_headers
from .base import ProviderError, StreamResult, ToolCall, emit, parse_args

_NO_TOOLS = ("does not support tools", "tools are not supported", "tool use is not supported", "tool_choice",
             "does not support function", "function calling is not", "tools is not supported")


async def stream_chat(http: Http, *, base_url: str, model: str, messages: list[dict], mode: str,
                      provider: str, key: str | None = None, max_tokens: int | None = None,
                      temperature: float | None = None, tools: list[dict] | None = None, extra: dict | None = None,
                      on_chunk=None, stall: float = 90.0, first_byte: float = 120.0) -> StreamResult:
    body: dict = {"model": model, "messages": messages, "stream": True}
    if max_tokens:
        body["max_tokens"] = max_tokens
    if temperature is not None:
        body["temperature"] = temperature
    if tools:
        body["tools"] = tools
        body["tool_choice"] = "auto"
    body["stream_options"] = {"include_usage": True}
    body.update({k: v for k, v in (extra or {}).items() if not k.startswith("_")})
    url = base_url.rstrip("/") + "/chat/completions"
    for _attempt in range(4):
        try:
            return await _once(http, url, body, mode=mode, provider=provider, key=key, on_chunk=on_chunk,
                               stall=stall, first_byte=first_byte)
        except HttpStatusError as e:
            low = e.message.lower()
            if e.status == 400 and "temperature" in low and "temperature" in body:
                body.pop("temperature")
                continue
            if e.status in (400, 422) and "stream_options" in low and "stream_options" in body:
                body.pop("stream_options")
                continue
            if e.status in (400, 422) and ("max_tokens" in low or "max_completion_tokens" in low) and "max_tokens" in body:
                body.pop("max_tokens")
                continue
            if 400 <= e.status < 500 and "tools" in body and any(k in low for k in _NO_TOOLS):
                raise ProviderError("tools_unsupported", e.message, e.status) from e
            if context_too_long(e.status, e.message):
                raise ProviderError("context", e.message, e.status) from e
            raise ProviderError("http", e.message, e.status, wait_from_headers(e.headers)) from e
        except StallError as e:
            raise ProviderError("stall", str(e)) from e
        except NetworkError as e:
            raise ProviderError("network", str(e)) from e
    raise ProviderError("bad_param", "request rejected", 400)


async def _once(http: Http, url: str, body: dict, *, mode: str, provider: str, key: str | None, on_chunk,
                stall: float, first_byte: float) -> StreamResult:
    res = StreamResult()
    calls: list[dict] = []
    guard = LoopGuard()
    text_parts: list[str] = []
    think_parts: list[str] = []
    seen = False
    async with http.stream(url, body, mode=mode, provider=provider, key=key, first_byte_timeout=first_byte) as resp:
        async for event, data in sse_events(resp, stall):
            if event == "json":
                v = _loads(data)
                if v is None:
                    raise ProviderError("http", "unreadable answer", resp.status)
                if v.get("error"):
                    e = v["error"]
                    msg = e.get("message") if isinstance(e, dict) else e
                    code = e.get("code") if isinstance(e, dict) else None
                    status = int(code) if isinstance(code, int) or (isinstance(code, str) and code.isdigit()) else 0
                    raise ProviderError("http", str(msg), status)
                ch = (v.get("choices") or [{}])[0]
                msg = ch.get("message") or {}
                res.text = msg.get("content") or ""
                res.thinking = msg.get("reasoning_content") or msg.get("reasoning") or ""
                if res.thinking:
                    emit(on_chunk, "thinking", res.thinking)
                if res.text:
                    emit(on_chunk, "text", res.text)
                for i, tc in enumerate(msg.get("tool_calls") or []):
                    f = tc.get("function") or {}
                    a = f.get("arguments")
                    calls.append({"id": tc.get("id") or "", "name": f.get("name") or "",
                                  "arguments": a if isinstance(a, str) else json.dumps(a or {})})
                res.finish = _finish(ch.get("finish_reason"))
                _usage(res, v.get("usage"))
                res.model_reported = v.get("model") or ""
                seen = True
                break
            if data.strip() == "[DONE]":
                break
            v = _loads(data)
            if v is None:
                continue
            if v.get("error"):
                e = v["error"]
                msg = e.get("message") if isinstance(e, dict) else str(e)
                low = str(msg).lower()
                status = 429 if ("rate" in low or "quota" in low) else 0
                raise ProviderError("http", str(msg), status)
            res.model_reported = res.model_reported or v.get("model") or ""
            _usage(res, v.get("usage"))
            for ch in v.get("choices") or []:
                seen = True
                d = ch.get("delta") or {}
                r = d.get("reasoning_content") or d.get("reasoning") or ""
                if r:
                    think_parts.append(r)
                    emit(on_chunk, "thinking", r)
                    guard.feed(r)
                t = d.get("content") or ""
                if t:
                    text_parts.append(t)
                    emit(on_chunk, "text", t)
                    guard.feed(t)
                for tc in d.get("tool_calls") or []:
                    i = tc.get("index")
                    i = len(calls) - 1 if i is None and calls and not tc.get("id") else (len(calls) if i is None else i)
                    while len(calls) <= i:
                        calls.append({"id": "", "name": "", "arguments": ""})
                    c = calls[i]
                    c["id"] = tc.get("id") or c["id"]
                    f = tc.get("function") or {}
                    if f.get("name"):
                        c["name"] += f["name"]
                    a = f.get("arguments")
                    if isinstance(a, str):
                        c["arguments"] += a
                    elif isinstance(a, dict):
                        c["arguments"] = json.dumps(a)
                if ch.get("finish_reason"):
                    res.finish = _finish(ch["finish_reason"])
            if guard.tripped:
                break                                   # leaving the context closes the connection
    if not seen:
        raise ProviderError("empty", "empty stream")
    if text_parts or think_parts:
        res.text, res.thinking = "".join(text_parts), "".join(think_parts)
    if guard.tripped:
        res.finish = "loop"
        res.text = guard.cut(res.text) if res.text else res.text
        res.thinking = guard.cut(res.thinking) if not res.text else res.thinking
    for k, c in enumerate(calls):
        if not c["name"]:
            continue
        args, err = parse_args(c["arguments"])
        res.tool_calls.append(ToolCall(c["id"] or f"call_{k}", c["name"], c["arguments"], args, err))
    if res.tool_calls and res.finish == "stop":
        res.finish = "tool_use"
    return res


def _finish(reason: str | None) -> str:
    return {"length": "length", "tool_calls": "tool_use", "function_call": "tool_use",
            "content_filter": "refusal"}.get(reason or "", "stop")


def _usage(res: StreamResult, u) -> None:
    if isinstance(u, dict):
        res.tokens_in = int(u.get("prompt_tokens") or res.tokens_in or 0)
        res.tokens_out = int(u.get("completion_tokens") or res.tokens_out or 0)


def _loads(s: str):
    try:
        v = json.loads(s)
    except ValueError:
        return None
    return v if isinstance(v, dict) else None
