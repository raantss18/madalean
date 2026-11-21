"""Wire-format tests against fake OpenAI-compatible and Anthropic servers: streaming, tool calls, errors
(401/429/529/overloaded mid-stream), fallbacks, stall watchdog, loop guard, cancellation, key isolation and the
local-mode network guarantee."""
import asyncio
import json
import socket
import time

import pytest

from madalean.brain.api import BrainError, Chunk
from madalean.brain.net import Http, KeyHostError, LocalModeViolation
from test_brain_fakes import (FakeServer, an_event, an_stream, free_provider, make_brain, model, oa_chunk, oa_stream,
                              run, write_catalogue)

ANTHROPIC_KEY = "sk-ant-api-TEST-SECRET-123456"
OR_KEY = "sk-or-v1-TEST-SECRET-abcdef"


def _two_free(tmp_path, s1, s2):
    write_catalogue(tmp_path, [free_provider("f1", s1.url), free_provider("f2", s2.url)],
                    [model("f1", "m-best", 0.9), model("f2", "m-second", 0.5)])


def test_openai_streaming_and_fallback_on_429(tmp_path):
    async def main():
        s1 = await FakeServer([{"status": 429, "headers": {"Retry-After": "42"},
                                "body": {"error": {"message": "Rate limit reached"}}}]).start()
        s2 = await FakeServer([oa_stream("Bonjour le monde", reasoning="hmm")]).start()
        _two_free(tmp_path, s1, s2)
        b = make_brain(tmp_path)
        seen: list[Chunk] = []
        try:
            c = await b.complete("explain", [{"role": "system", "content": "sys"}, {"role": "user", "content": "hi"}],
                                 on_chunk=seen.append, temperature=0.3)
        finally:
            await b.close(); await s1.stop(); await s2.stop()
        assert c.text == "Bonjour le monde" and c.model.key == "f2:m-second" and c.finish == "stop"
        assert c.fallbacks and c.fallbacks[0].startswith("f1:m-best: HTTP 429")
        assert (c.tokens_in, c.tokens_out) == (11, 7)
        until, why = b.states.pause_of("f1:m-best")
        assert why == "rate_limit" and 35 < until - time.time() <= 42
        assert "".join(x.text for x in seen if x.kind == "text") == "Bonjour le monde"
        assert any(x.kind == "thinking" for x in seen) and any(x.kind == "info" for x in seen)
        body = s2.requests[0].body
        assert body["stream"] is True and body["messages"][0]["role"] == "system" and body["temperature"] == 0.3
        assert "Authorization" not in s1.requests[0].headers            # keyless provider: no key sent
    run(main())


def test_openai_tool_call_assembly_and_temperature_retry(tmp_path):
    async def main():
        def first(body):
            if "temperature" in body:
                return {"status": 400, "body": {"error": {"message": "Unsupported parameter: temperature"}}}
            return oa_stream("", tool_calls=[("call_1", "lean_check", {"proof": "simp"})])
        s1 = await FakeServer([first]).start()
        s2 = await FakeServer([oa_stream("x")]).start()
        _two_free(tmp_path, s1, s2)
        b = make_brain(tmp_path)
        from madalean.brain.catalogue import Model
        try:
            res = await b._generate(Model("f1", "m-best", "m"), "prove", mode="auto", messages=[{"role": "user", "content": "x"}],
                                    tools=[{"name": "lean_check", "description": "d", "parameters": {"type": "object"}}],
                                    temperature=0.5)
        finally:
            await b.close(); await s1.stop(); await s2.stop()
        assert len(s1.requests) == 2 and "temperature" not in s1.requests[1].body
        assert s1.requests[1].body["tools"][0]["type"] == "function" and s1.requests[1].body["tool_choice"] == "auto"
        assert res.finish == "tool_use" and res.tool_calls[0].name == "lean_check"
        assert res.tool_calls[0].input == {"proof": "simp"} and res.tool_calls[0].id == "call_1"
    run(main())


def test_empty_answer_and_errors_fall_through_then_brainerror(tmp_path):
    async def main():
        s1 = await FakeServer([oa_stream("<think>only thinking</think>")]).start()       # empty after cleaning
        s2 = await FakeServer([{"status": 401, "body": {"error": {"message": "needs a key"}}}]).start()
        _two_free(tmp_path, s1, s2)
        b = make_brain(tmp_path)
        try:
            with pytest.raises(BrainError) as ei:
                await b.complete("route", [{"role": "user", "content": "x"}])
        finally:
            await b.close(); await s1.stop(); await s2.stop()
        assert "empty answer" in str(ei.value) and "needs a key" in str(ei.value)
        assert b.states.pause_of("f2:m-second")[1] == "needs_key"      # keyless provider: only that model paused
        assert len(ei.value.tried) == 2
    run(main())


def test_stall_watchdog_and_loop_guard(tmp_path):
    async def main():
        stall = {"events": [oa_chunk({"content": "Start"})], "hang": 4}
        s1 = await FakeServer([stall]).start()
        loop_text = "* `norm_num` then we repeat the same sentence again and again forever, really.\n"
        s2 = await FakeServer([{"events": [oa_chunk({"content": loop_text}) for _ in range(200)]
                                + [oa_chunk({}, "stop"), "data: [DONE]\n\n"]}]).start()
        _two_free(tmp_path, s1, s2)
        b = make_brain(tmp_path, stall_online=1.5)
        t0 = time.monotonic()
        try:
            c = await b.complete("explain", [{"role": "user", "content": "x"}])
            took = time.monotonic() - t0
        finally:
            await b.close(); await s1.stop(); await s2.stop()
        assert took < 10
        assert "stalled" in c.fallbacks[0]
        assert c.finish == "loop" and c.text.count(loop_text) == 1          # first occurrence kept
    run(main())


def test_cancellation_mid_stream_closes_connection_and_releases_local(tmp_path):
    async def main():
        slow = {"events": [oa_chunk({"content": "a"})] + [0.2, oa_chunk({"content": "b"})] * 50}
        srv = await FakeServer([slow]).start()
        write_catalogue(tmp_path, [free_provider("f1", srv.url)], [model("f1", "m", 0.9)])

        class Local:
            released = 0

            async def ensure(self, role):
                return srv.url

            def release(self):
                Local.released += 1

            def model_for(self, role):
                from madalean.brain.api import ModelRef
                return ModelRef("local", "goedel", "Goedel", local=True)
        b = make_brain(tmp_path, local=Local())
        got = []
        for mode in ("auto", "local"):
            t = asyncio.create_task(b.complete("prove", [{"role": "user", "content": "x"}], mode=mode,
                                               on_chunk=lambda ch: got.append(ch.text)))
            await asyncio.sleep(0.6)
            t.cancel()
            with pytest.raises(asyncio.CancelledError):
                await t
        await asyncio.sleep(0.3)
        await b.close(); await srv.stop()
        assert srv.closed_early >= 2
        assert Local.released == 1                                          # local call released in finally
        assert b.states.models.get("f1:m") is None                          # cancellation is not a failure
    run(main())


# ------------------------------------------------------------------ Anthropic
def _anthropic_brain(tmp_path, srv, **kw):
    write_catalogue(tmp_path, [free_provider("dead", "http://127.0.0.1:9/v1")], [model("dead", "dead", 0.01)])
    return make_brain(tmp_path, keys={"anthropic": ANTHROPIC_KEY}, endpoints={"anthropic": srv.url}, **kw)


def test_anthropic_streaming_thinking_caching_and_headers(tmp_path):
    async def main():
        srv = await FakeServer([an_stream([("thinking", "Let me think.", "sig-abc"), ("text", "Hello from Claude")])]).start()
        b = _anthropic_brain(tmp_path, srv)
        seen = []
        try:
            c = await b.complete("prove", [{"role": "system", "content": "You prove."}, {"role": "user", "content": "hi"},
                                           {"role": "user", "content": "again"}],
                                 prefer="anthropic:claude-opus-5-5", on_chunk=seen.append, temperature=0.2)
        finally:
            await b.close(); await srv.stop()
        assert c.text == "Hello from Claude" and c.model.key == "anthropic:claude-opus-5-5" and c.model.paid
        assert (c.tokens_in, c.tokens_out) == (20, 9)
        r = srv.requests[0]
        assert r.path == "/v1/messages"
        assert r.headers["x-api-key"] == ANTHROPIC_KEY and r.headers["anthropic-version"] == "2026-10-21"
        assert "Authorization" not in r.headers
        body = r.body
        assert "temperature" not in body                                    # rejected by API version 2026-10-21
        assert body["thinking"] == {"type": "adaptive", "display": "summarized"}
        assert body["output_config"] == {"effort": "high"} and body["max_tokens"] == 64000 and body["stream"] is True
        assert body["system"][0]["cache_control"] == {"type": "ephemeral"} and body["system"][0]["text"] == "You prove."
        assert body["cache_control"] == {"type": "ephemeral"}
        assert body["messages"] == [{"role": "user", "content": "hi\n\nagain"}]
        assert body["fallbacks"] == "default" and r.headers["anthropic-beta"] == "server-side-fallback-2026-07-01"
        assert [x.kind for x in seen if x.kind in ("thinking", "text")][0] == "thinking"
    run(main())


def test_anthropic_errors_401_529_overloaded_and_beta_retry(tmp_path):
    async def main():
        def beta_check(body):
            if "fallbacks" in body:
                return {"status": 400, "body": {"type": "error", "error": {"type": "invalid_request_error",
                        "message": "Unexpected value(s) `server-side-fallback-2026-07-01` for the `anthropic-beta` header."}}}
            return an_stream([("text", "ok without beta")])
        srv = await FakeServer([beta_check]).start()
        b = _anthropic_brain(tmp_path, srv)
        try:
            c = await b.complete("explain", [{"role": "user", "content": "x"}], prefer="anthropic:claude-sonnet-5-5")
        finally:
            await b.close(); await srv.stop()
        assert c.text == "ok without beta" and "fallbacks" not in srv.requests[1].body
        assert "anthropic-beta" not in srv.requests[1].headers

        # 529 overloaded -> next model; mid-stream `overloaded_error` event -> next model (paid chain: 2 models)
        srv = await FakeServer([{"status": 529, "body": {"type": "error", "error": {"type": "overloaded_error", "message": "Overloaded"}}},
                                an_stream([("text", "partial")], error={"type": "overloaded_error", "message": "Overloaded"}),
                                {"status": 401, "body": {"type": "error", "error": {"type": "authentication_error", "message": "invalid x-api-key"}}}]).start()
        b = _anthropic_brain(tmp_path, srv, paid_first=True)
        seen = []
        try:
            with pytest.raises(BrainError) as ei:
                await b.complete("explain", [{"role": "user", "content": "x"}], mode="online", on_chunk=seen.append)
            tried = ei.value.tried
            assert "HTTP 529" in tried[0] and "overloaded" in tried[1].lower(), tried
            assert any(x.kind == "info" and x.data.get("event") == "restart" for x in seen)   # UI drops the partial
            assert b.states.pause_of("anthropic:claude-opus-5-5")[1] == "overloaded"
            # 401 -> the whole provider is paused (key refused)
            with pytest.raises(BrainError) as ei:
                await b.complete("explain", [{"role": "user", "content": "x"}], mode="online",
                                 prefer="anthropic:claude-haiku-5-5")
        finally:
            await b.close(); await srv.stop()
        assert "key refused" in ei.value.tried[0]
        assert b.states.pause_of("anthropic:claude-sonnet-5-5")[1] == "key_refused"
        assert b.states.pause_of("anthropic:claude-haiku-5-5")[1] == "key_refused"
    run(main())


def test_anthropic_refusal_and_context_window(tmp_path):
    async def main():
        srv = await FakeServer([an_stream([], stop="refusal"), an_stream([("text", "fine")])]).start()
        b = _anthropic_brain(tmp_path, srv, paid_first=True)
        try:
            c = await b.complete("explain", [{"role": "user", "content": "x"}], mode="online")
        finally:
            await b.close(); await srv.stop()
        assert c.text == "fine" and "refused" in c.fallbacks[0]
    run(main())


# ------------------------------------------------------------------ key isolation & local mode
def test_key_isolation(tmp_path):
    async def main():
        a = await FakeServer([an_stream([("text", "A")])]).start()
        o = await FakeServer([oa_stream("O")], host="localhost").start()     # another host name
        write_catalogue(tmp_path, [{"id": "openrouter", "name": "OR", "base_url": "https://openrouter.ai/api/v1",
                                    "keyed": True, "paid": False, "api": "openai", "local": False,
                                    "free_suffix": ":free", "key_url": ""}],
                        [model("openrouter", "x/y:free", 0.9)])
        b = make_brain(tmp_path, keys={"anthropic": ANTHROPIC_KEY, "openrouter": OR_KEY},
                       endpoints={"anthropic": a.url, "openrouter": o.url}, paid_first=False)
        try:
            c1 = await b.complete("explain", [{"role": "user", "content": "x"}])
            c2 = await b.complete("explain", [{"role": "user", "content": "x"}], prefer="anthropic:claude-haiku-5-5")
        finally:
            await b.close(); await a.stop(); await o.stop()
        assert c1.model.provider == "openrouter" and c2.model.provider == "anthropic"
        for r in o.requests:
            assert ANTHROPIC_KEY not in json.dumps(r.headers) + json.dumps(r.body)
            assert r.headers["Authorization"] == f"Bearer {OR_KEY}"
        for r in a.requests:
            assert OR_KEY not in json.dumps(r.headers) + json.dumps(r.body)
        # the central check refuses to send a key to any other host
        h = Http({"anthropic": "api.anthropic.com"})
        with pytest.raises(KeyHostError):
            h.check("https://evil.example/v1/messages", "online", "anthropic", ANTHROPIC_KEY)
        with pytest.raises(KeyHostError):
            h.check("https://api.anthropic.com.evil.example/v1", "online", "anthropic", ANTHROPIC_KEY)
        h.check("https://api.anthropic.com/v1/messages", "online", "anthropic", ANTHROPIC_KEY)
        with pytest.raises(LocalModeViolation):
            h.check("https://api.anthropic.com/v1/messages", "local")
        h.check("http://127.0.0.1:8765/v1/chat/completions", "local")
    run(main())


def test_local_mode_opens_no_external_socket(tmp_path, monkeypatch):
    """mode=local: only loopback connections, even with online models, keys and a stale catalogue."""
    connects: list = []
    real_connect = socket.socket.connect
    real_create = asyncio.base_events.BaseEventLoop.create_connection

    def spy_connect(self, addr):
        connects.append(addr)
        return real_connect(self, addr)

    async def spy_create(self, *a, **kw):
        host = a[1] if len(a) > 1 else kw.get("host")
        connects.append((host, a[2] if len(a) > 2 else kw.get("port")))
        return await real_create(self, *a, **kw)
    monkeypatch.setattr(socket.socket, "connect", spy_connect)
    monkeypatch.setattr(asyncio.base_events.BaseEventLoop, "create_connection", spy_create)

    async def main():
        local_srv = await FakeServer([oa_stream("local answer")]).start()

        class Local:
            async def ensure(self, role):
                return f"http://127.0.0.1:{local_srv.port}"

            def release(self):
                pass

            def model_for(self, role):
                from madalean.brain.api import ModelRef
                return ModelRef("local", "qwen3", "Qwen3", local=True)
        write_catalogue(tmp_path, [free_provider("f1", "https://f1.example/v1")], [model("f1", "m", 0.99)])
        b = make_brain(tmp_path, local=Local(), keys={"anthropic": ANTHROPIC_KEY}, refresh_catalogue=True)
        b.store.cat.updated = 0                         # stale catalogue: would refresh if allowed
        try:
            c = await b.complete("explain", [{"role": "user", "content": "x"}], mode="local")
            assert await b.http.online("local") is False
            b.update_settings({"mode": "local"})          # settings ceiling: even status() stays local
            st = await b.status()
            assert st["online"] is False
            c2 = await b.complete("explain", [{"role": "user", "content": "x"}], mode="online")
            assert c2.model.local
            r = None
        finally:
            await b.close(); await local_srv.stop()
        assert c.text == "local answer" and c.model.local
        return r
    run(main())
    for addr in connects:
        host = addr[0] if isinstance(addr, tuple) else addr
        assert host in (None, "127.0.0.1", "localhost", "::1") or str(host).startswith("/"), connects
    assert any(isinstance(a, tuple) and a[0] == "127.0.0.1" for a in connects)
