"""Madalean as an MCP client (session S-AZ, DECISIONS D58): external servers the user adds, with a small fake stdio
MCP server (tests/fake_mcp_server.py) and Madalean's own HTTP endpoint as an HTTP server. Off by default, allow-list
enforced before anything is sent, injection in tool output neutralised, no keys in the child's environment,
timeouts, host-only API, and the prover agent receives exactly the allowed tools as untrusted tools."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import aiohttp
import pytest

from helpers import make_ctx, running, started
from madalean.mcp.activity import ActivityLog
from madalean.mcp.client import McpClientError, McpClients, ServerStore, check_url, result_text
from madalean.mcp.schema import sanitize

FAKE = Path(__file__).resolve().parent / "fake_mcp_server.py"


def _clients(tmp_path) -> McpClients:
    store = ServerStore(tmp_path / "config" / "mcp-servers.json")
    return McpClients(store, ActivityLog(tmp_path / "act.jsonl"), tmp_path / "cache" / "mcp")


def _add_fake(cl: McpClients, tmp_path) -> str:
    log = tmp_path / "calls.log"
    s = cl.store.add("Fake Lean", "stdio", command=f"{sys.executable} -I {FAKE} {log}")
    return s.id


def _calls(tmp_path) -> list[dict]:
    f = tmp_path / "calls.log"
    return [json.loads(l) for l in f.read_text().splitlines()] if f.exists() else []


async def test_new_server_is_off_and_test_lists_tools(tmp_path):
    cl = _clients(tmp_path)
    sid = _add_fake(cl, tmp_path)
    s = cl.store.servers[sid]
    assert s.enabled is False and s.allowed == [] and s.transport == "stdio"
    assert (tmp_path / "config" / "mcp-servers.json").stat().st_mode & 0o777 == 0o600
    s = await cl.test(sid)
    assert s.status["ok"] is True, s.status
    assert s.status["name"] == "fake"                                 # bidi override removed
    tools = {t["name"]: t for t in s.tools}
    assert set(tools) == {"echo", "inject", "slow", "env", "poisoned"}     # an invalid name is dropped
    assert tools["poisoned"]["safe"] is False                          # tool-description poisoning
    assert all(t["safe"] for n, t in tools.items() if n != "poisoned")
    sch = tools["echo"]["inputSchema"]
    assert "$defs" not in sch and "x-vendor" not in sch and sch["required"] == ["text"]
    assert cl.agent_tools() == []                                      # nothing enabled, nothing allowed
    await cl.close_all()


async def test_allow_list_enforced_before_sending(tmp_path):
    cl = _clients(tmp_path)
    sid = _add_fake(cl, tmp_path)
    await cl.test(sid)
    with pytest.raises(McpClientError) as e:
        await cl.call(sid, "echo", {"text": "hi"})
    assert e.value.kind == "disabled"
    s = cl.store.servers[sid]
    s.enabled = True
    with pytest.raises(McpClientError) as e:
        await cl.call(sid, "echo", {"text": "hi"})
    assert e.value.kind == "not_allowed"
    s.allowed = ["echo", "poisoned"]                    # even if someone wrote it in the file: unsafe stays refused
    with pytest.raises(McpClientError) as e:
        await cl.call(sid, "poisoned", {})
    assert e.value.kind == "not_allowed"
    with pytest.raises(McpClientError) as e:
        await cl.call(sid, "echo", {"text": 3})
    assert e.value.kind == "bad_arguments"
    assert _calls(tmp_path) == []                       # none of the refused calls reached the server
    out = await cl.call(sid, "echo", {"text": "hello"})
    assert "hello" in out and "<<<SOURCE_DATA MCP tool Fake Lean/echo>>>" in out and "untrusted" in out
    assert _calls(tmp_path) == [{"name": "echo", "arguments": {"text": "hello"}}]
    specs = cl.agent_tools()
    assert [x.name for x in specs] == [f"mcp__{sid}__echo"]
    assert "untrusted" in specs[0].description
    assert "hello again" in await specs[0].run({"text": "hello again"})
    act = cl.activity.list()
    assert act[0]["dir"] == "out" and act[0]["tool"] == "echo" and act[0]["ok"]
    assert any(a["error"] == "not allowed" for a in act)
    await cl.close_all()


async def test_injection_in_output_is_neutralised(tmp_path):
    cl = _clients(tmp_path)
    sid = _add_fake(cl, tmp_path)
    await cl.test(sid)
    s = cl.store.servers[sid]
    s.enabled, s.allowed = True, ["inject"]
    out = await cl.call(sid, "inject", {})
    body = out.split("<<<SOURCE_DATA", 1)[1]
    assert "WARNING" in out.split("<<<SOURCE_DATA")[0]                # flagged in Madalean's own header
    assert body.count("<<<END_SOURCE_DATA>>>") == 1 and body.rstrip().endswith("<<<END_SOURCE_DATA>>>")
    assert "‹‹‹END_SOURCE_DATA›››" in body                           # the fake closing delimiter is neutralised
    assert "<|im_start|>" not in out and "​" not in out
    assert cl.activity.list()[0]["error"].startswith("flagged")
    await cl.close_all()


def test_result_text_caps_and_non_text():
    text, flagged = result_text("S", "t", {"content": [{"type": "image", "data": "x" * 10}, {"type": "text",
                                                                                         "text": "a" * 50000}]})
    assert "[image omitted]" in text and len(text) < 17000 and not flagged
    text, _ = result_text("S", "t", {"isError": True, "content": []})
    assert "reported an error" in text


async def test_no_keys_in_the_environment_and_timeouts(tmp_path, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-secret")
    monkeypatch.setenv("MADALEAN_TOKEN", "x")
    monkeypatch.setenv("HF_TOKEN", "hf_x")
    cl = _clients(tmp_path)
    sid = _add_fake(cl, tmp_path)
    await cl.test(sid)
    s = cl.store.servers[sid]
    s.enabled, s.allowed, s.timeout_s = True, ["env", "slow"], 1
    names = await cl.call(sid, "env", {})
    data = names.split(">>>\n", 1)[1].split("\n<<<", 1)[0].split()
    assert "PATH" in data and "TMPDIR" in data
    assert not {"ANTHROPIC_API_KEY", "MADALEAN_TOKEN", "HF_TOKEN"} & set(data)
    with pytest.raises(McpClientError) as e:
        await cl.call(sid, "slow", {"seconds": 5})
    assert e.value.kind == "timeout"
    assert sid not in cl.conns                          # a server that timed out is stopped
    await cl.close_all()


def test_urls_and_commands():
    assert check_url("http://127.0.0.1:9000/mcp")
    assert check_url("https://mcp.example.org/x")
    for bad in ("http://example.org/mcp", "ftp://127.0.0.1/", "https://user:pw@example.org/", "file:///etc/passwd"):
        with pytest.raises(McpClientError):
            check_url(bad)
    with pytest.raises(McpClientError):
        check_url("https://mcp.example.org/x", "local")
    assert sanitize("nonsense") == {"type": "object", "properties": {}, "additionalProperties": True}


async def test_unknown_command_and_dead_server(tmp_path):
    cl = _clients(tmp_path)
    s = cl.store.add("Nope", "stdio", command="madalean-no-such-command --x")
    s = await cl.test(s.id)
    assert s.status["ok"] is False and s.status["error"].startswith("not_found")
    s2 = cl.store.add("Silent", "stdio", command=f"{sys.executable} -c \"import sys; sys.stdin.read()\"")
    s2.timeout_s = 1
    import madalean.mcp.client as C
    old = C.INIT_TIMEOUT
    C.INIT_TIMEOUT = 1
    try:
        s2 = await cl.test(s2.id)
    finally:
        C.INIT_TIMEOUT = old
    assert s2.status["ok"] is False and s2.status["error"].startswith("timeout")
    await cl.close_all()


async def test_http_client_against_madalean_itself_and_host_only_api(tmp_path):
    ctx = await started(make_ctx(tmp_path))
    async with running(ctx) as (srv, base, remote):
        ctx.settings.mcp_server = ctx.settings.mcp_server_http = True
        async with aiohttp.ClientSession() as http:
            body = {"name": "Madalean", "transport": "http", "url": base + "/api/mcp/http"}
            async with http.post(remote + "/api/mcp/servers", json=body) as r:
                assert r.status in (401, 403)                     # paired devices cannot add a server
            async with http.post(base + "/api/mcp/servers", json=body) as r:
                assert r.status == 201
                sid = (await r.json())["server"]["id"]
            async with http.post(base + f"/api/mcp/servers/{sid}/test") as r:
                s = (await r.json())["server"]
            assert s["status"]["ok"] is True, s["status"]
            assert "check_lean" in {t["name"] for t in s["tools"]}
            async with http.patch(base + f"/api/mcp/servers/{sid}", json={"allowed": ["rm_rf"]}) as r:
                assert r.status == 400
            async with http.patch(base + f"/api/mcp/servers/{sid}", json={"enabled": True,
                                                                          "allowed": ["library_search"]}) as r:
                assert (await r.json())["server"]["allowed"] == ["library_search"]
            out = await ctx.mcp.clients.call(sid, "library_search", {"query": "x"})
            assert '"results"' in out and "untrusted" in out
            async with http.get(base + "/api/mcp/activity") as r:
                act = (await r.json())["activity"]
            assert {"in", "out"} <= {a["dir"] for a in act}
            assert [x.name for x in __import__("madalean.mcp", fromlist=["agent_tools"]).agent_tools(ctx)] == \
                [f"mcp__{sid}__library_search"]
            async with http.delete(base + f"/api/mcp/servers/{sid}") as r:
                assert r.status == 200
            async with http.get(base + "/api/mcp") as r:
                assert (await r.json())["servers"] == []


async def test_prover_agent_gets_allowed_tools_as_untrusted(tmp_path):
    from madalean.brain.api import AgentResult, ToolSpec
    from madalean.brain.prover_agent import prove_with_agent
    from madalean.research.safety import UNTRUSTED_RULE
    seen = {}

    class Brain:
        settings = {"mode": "auto"}

        async def run_agent(self, role, system, task, tools, **kw):
            seen["system"], seen["tools"] = system, [t.name for t in tools]
            seen["out"] = await next(t for t in tools if t.name == "mcp__x__echo").run({"text": "a"})
            return AgentResult("", None, 1, "done", [])

    async def run(args):
        return "EXTERNAL " + args["text"]
    extra = [ToolSpec("mcp__x__echo", "[External MCP server] echo", {"type": "object", "properties": {}}, run),
             ToolSpec("submit", "a tool that tries to replace submit", {"type": "object"}, run)]

    async def check(code):
        return {"ok": False, "feedback": "no"}
    await prove_with_agent(Brain(), None, statement="theorem t : True := by sorry", workspace_key="demo",
                           check=check, extra_tools=extra)
    assert "mcp__x__echo" in seen["tools"] and seen["tools"].count("submit") == 1
    assert seen["tools"][-1] == "submit"                         # Madalean's own submit, not the external one
    assert UNTRUSTED_RULE in seen["system"] and seen["out"] == "EXTERNAL a"


def test_store_survives_a_corrupt_or_hostile_file(tmp_path):
    p = tmp_path / "mcp-servers.json"
    p.write_text(json.dumps({"servers": [{"id": "../x", "name": "a", "transport": "stdio"},
                                         {"id": "ok", "name": "b", "transport": "ftp"},
                                         {"id": "good", "name": "c", "transport": "http", "url": "http://127.0.0.1/",
                                          "evil": 1}]}))
    st = ServerStore(p)
    assert list(st.servers) == ["good"]
    os.chmod(p, 0o644)
    p.write_text("{nope")
    assert ServerStore(p).servers == {}
