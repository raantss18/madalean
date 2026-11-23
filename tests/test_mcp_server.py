"""Madalean as an MCP server (session S-AZ, DECISIONS D58, docs/MCP.md).

Protocol conformance over stdio with a raw client harness (the real `madalean mcp serve` process, JSON lines written
and read here — independent of Madalean's own client), the streamable HTTP transport, strict input schemas, the
strict fresh verdict of `check_lean` (and that it writes nothing), `sage_compute` limited to the catalogue, rate
limits, the activity log, host-only access."""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

import aiohttp
import pytest

from helpers import make_ctx, running, started
from madalean.mcp import protocol as P
from madalean.mcp import tools as T
from madalean.mcp.schema import validate

ROOT = Path(__file__).resolve().parents[1]
GOOD = "theorem mcp_t (a b : ℕ) : a + b = b + a := by sorry"


class Harness:
    """A minimal MCP client over stdio: newline-delimited JSON-RPC, as the specification describes it."""

    def __init__(self, port: int, config_dir: Path):
        self.port, self.config_dir = port, config_dir
        self.proc = None
        self.n = 0

    async def __aenter__(self):
        env = {**os.environ, "PYTHONPATH": str(ROOT)}
        self.proc = await asyncio.create_subprocess_exec(
            sys.executable, "-m", "madalean", "mcp", "serve", "--port", str(self.port), "--config-dir",
            str(self.config_dir), stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE, env=env)
        return self

    async def __aexit__(self, *exc):
        self.proc.stdin.close()
        try:
            await asyncio.wait_for(self.proc.wait(), 10)
        except asyncio.TimeoutError:
            self.proc.kill()

    async def send_raw(self, text: str) -> None:
        self.proc.stdin.write(text.encode() + b"\n")
        await self.proc.stdin.drain()

    async def read(self, timeout: float = 30) -> dict:
        line = await asyncio.wait_for(self.proc.stdout.readline(), timeout)
        assert line.endswith(b"\n") and line.count(b"\n") == 1      # one message per line
        return json.loads(line)

    async def request(self, method: str, params: dict | None = None) -> dict:
        self.n += 1
        msg = {"jsonrpc": "2.0", "id": self.n, "method": method}
        if params is not None:
            msg["params"] = params
        await self.send_raw(json.dumps(msg))
        out = await self.read()
        assert out["jsonrpc"] == "2.0" and out["id"] == self.n
        return out

    async def notify(self, method: str) -> None:
        await self.send_raw(json.dumps({"jsonrpc": "2.0", "method": method}))


async def _ctx(tmp_path):
    return await started(make_ctx(tmp_path))


async def test_stdio_conformance(tmp_path):
    ctx = await _ctx(tmp_path)
    async with running(ctx) as (srv, base, _remote):
        ctx.settings.mcp_server = True         # after the start (it reads the settings file)
        async with Harness(srv.ports["local"], tmp_path / "config") as h:
            r = await h.request("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                               "clientInfo": {"name": "harness", "version": "0"}})
            res = r["result"]
            assert res["protocolVersion"] == "2025-06-18"
            assert res["capabilities"]["tools"] == {"listChanged": False}
            assert res["serverInfo"]["name"] == "madalean" and res["serverInfo"]["version"]
            await h.notify("notifications/initialized")              # no answer to a notification…
            assert (await h.request("ping"))["result"] == {}           # … the next line answers the ping
            r = await h.request("initialize", {"protocolVersion": "1999-01-01", "capabilities": {},
                                               "clientInfo": {"name": "old", "version": "0"}})
            assert r["result"]["protocolVersion"] == P.LATEST          # unknown version: the server's latest

            r = await h.request("tools/list")
            assert "result" in r, r
            tools = r["result"]["tools"]
            names = {t["name"] for t in tools}
            assert {"search_mathlib", "check_lean", "certify", "explain_lean", "library_search",
                    "dossier_status"} <= names
            assert "sage_compute" not in names                         # off unless the host switches it on
            assert "literature_search" not in names                    # S-AX's hook absent here
            for t in tools:
                s = t["inputSchema"]
                assert s["type"] == "object" and s["additionalProperties"] is False
                assert t["annotations"]["destructiveHint"] is False and t["description"]

            r = await h.request("tools/call", {"name": "check_lean", "arguments": {"statement": GOOD,
                                                                                   "proof": "omega"}})
            res = r["result"]
            assert res["isError"] is False and res["structuredContent"]["ok"] is True
            assert json.loads(res["content"][0]["text"])["verdict"] == "accepted"
            r = await h.request("tools/call", {"name": "check_lean", "arguments": {"statement": GOOD,
                                                                                   "proof": "sorry"}})
            assert r["result"]["structuredContent"]["ok"] is False      # strict: sorry is not a proof

            # ---- errors
            await h.send_raw("{not json")
            e = await h.read()
            assert e["id"] is None and e["error"]["code"] == P.PARSE_ERROR
            await h.send_raw(json.dumps([{"jsonrpc": "2.0", "id": 99, "method": "ping"}]))
            assert (await h.read())["error"]["code"] == P.INVALID_REQUEST           # no batches
            await h.send_raw(json.dumps({"id": 98, "method": "ping"}))
            assert (await h.read())["error"]["code"] == P.INVALID_REQUEST           # jsonrpc missing
            assert (await h.request("resources/list"))["error"]["code"] == P.METHOD_NOT_FOUND
            r = await h.request("tools/call", {"name": "rm_rf", "arguments": {}})
            assert r["error"]["code"] == P.INVALID_PARAMS and "unknown tool" in r["error"]["message"]
            r = await h.request("tools/call", {"name": "check_lean", "arguments": {"statement": GOOD,
                                                                                   "shell": "id"}})
            assert r["error"]["code"] == P.INVALID_PARAMS
            assert any("unknown property" in p for p in r["error"]["data"]["problems"])

            # ---- the host switches it off: relayed calls say so
            ctx.settings.mcp_server = False
            r = await h.request("tools/list")
            assert r["error"]["code"] == P.SERVER_UNAVAILABLE and "switched off" in r["error"]["message"]
            assert (await h.request("ping"))["result"] == {}


async def test_stdio_server_not_running(tmp_path):
    async with Harness(1, tmp_path) as h:                    # nothing listens on port 1
        assert (await h.request("initialize", {"protocolVersion": P.LATEST, "capabilities": {},
                                               "clientInfo": {"name": "h", "version": "0"}}))["result"]
        r = await h.request("tools/call", {"name": "check_lean", "arguments": {"statement": GOOD}})
        assert r["error"]["code"] == P.SERVER_UNAVAILABLE and "not running" in r["error"]["message"]


def test_schemas_reject_bad_input():
    s = T.REGISTRY["check_lean"].input_schema
    assert validate({"statement": GOOD}, s) == []
    assert validate({}, s) == ["arguments: missing required 'statement'"]
    assert validate({"statement": 3}, s) == ["statement: expected string"]
    assert validate({"statement": ""}, s)
    assert validate({"statement": "x" * 20001}, s)
    assert validate({"statement": GOOD, "workspace": "../etc"}, s) == ["workspace: invalid format"]
    assert validate({"statement": GOOD, "extra": 1}, s)
    assert validate([GOOD], s) == ["arguments: expected object"]
    k = T.REGISTRY["search_mathlib"].input_schema
    assert validate({"query": "x", "k": True}, k)              # a boolean is not an integer
    assert validate({"query": "x", "k": "8"}, k)               # no coercion
    assert validate({"query": "x", "k": 21}, k) and validate({"query": "x", "k": 0}, k)
    assert validate({"query": "x", "k": 8}, k) == []
    assert validate({"code": "x", "mode": "run"}, T.REGISTRY["explain_lean"].input_schema)


async def _rpc(http, base, method, params=None, rid=1, path="/api/mcp/rpc", headers=None):
    msg = {"jsonrpc": "2.0", "id": rid, "method": method}
    if params is not None:
        msg["params"] = params
    async with http.post(base + path, json=msg, headers=headers or {}) as r:
        return r.status, await r.json(content_type=None)


async def test_check_lean_fresh_strict_and_writes_nothing(tmp_path):
    ctx = await _ctx(tmp_path)
    seen = []
    orig = ctx.lean.check

    async def spy(code, ws, timeout_s=180, strict_name=None, owner=None, warm=False):
        seen.append((code, strict_name, warm))
        return await orig(code, ws, timeout_s, strict_name, owner=owner, warm=warm)
    ctx.lean.check = spy

    def snapshot():
        return sorted(str(p.relative_to(tmp_path)) + str(p.stat().st_size) for p in (tmp_path / "config").rglob("*")
                      if p.is_file() and "logs" not in p.parts and p.name != "server.json")
    async with running(ctx) as (srv, base, _r):
        ctx.settings.mcp_server = True         # after the start (it reads the settings file)
        before = (snapshot(), len(ctx.library.entries), len(ctx.repo.list()))
        async with aiohttp.ClientSession() as http:
            st, r = await _rpc(http, base, "tools/call", {"name": "check_lean", "arguments": {
                "statement": GOOD, "proof": "theorem mcp_t (a b : ℕ) : a + b = b + a := by\n  omega"}})
            assert st == 200 and r["result"]["structuredContent"]["ok"] is True
            assert r["result"]["structuredContent"]["via"] == "fresh"
            # a proof that changes the statement is not a proof of it
            st, r = await _rpc(http, base, "tools/call", {"name": "check_lean", "arguments": {
                "statement": GOOD, "proof": "theorem mcp_t : True := by\n  trivial"}})
            checked = r["result"]["structuredContent"]["checked_code"]
            assert "(a b : ℕ) : a + b = b + a" in checked and "mcp_t : True" not in checked   # statement pinned
            st, r = await _rpc(http, base, "tools/call", {"name": "check_lean", "arguments": {"statement": GOOD}})
            sc = r["result"]["structuredContent"]
            assert sc["mode"] == "statement" and sc["ok"] is True
            # D28: code that could run on the host is refused before compiling
            st, r = await _rpc(http, base, "tools/call", {"name": "check_lean", "arguments": {
                "statement": GOOD, "proof": "omega\n#eval IO.Process.run {cmd := \"id\"}"}})
            assert r["result"]["structuredContent"]["ok"] is False
        assert (snapshot(), len(ctx.library.entries), len(ctx.repo.list())) == before
    assert seen and all(w is False for _c, _n, w in seen)            # never the warm Lean
    assert seen[0][1] == "mcp_t" and "#print axioms mcp_t" in seen[0][0]   # strict mode with the axiom probe


async def test_sage_compute_catalogue_only(tmp_path):
    ctx = await _ctx(tmp_path)
    ran = []

    async def runner(language, code, seconds):
        ran.append((language, code))
        return {"status": "ok", "stdout": "2^3 * 3^2 * 5", "result": "", "error": ""}
    ctx.mcp_sage_runner = runner
    async with running(ctx) as (srv, base, _r):
        ctx.settings.mcp_server = True         # after the start (it reads the settings file)
        async with aiohttp.ClientSession() as http:
            st, r = await _rpc(http, base, "tools/list")
            assert "sage_compute" not in {t["name"] for t in r["result"]["tools"]}
            st, r = await _rpc(http, base, "tools/call", {"name": "sage_compute", "arguments": {"request": "factor 360"}})
            assert r["error"]["code"] == P.INVALID_PARAMS                 # not listed = not callable
            ctx.settings.mcp_server_sage = True
            st, r = await _rpc(http, base, "tools/call", {"name": "sage_compute", "arguments": {"request": "factor 360"}})
            sc = r["result"]["structuredContent"]
            assert sc["code"] == "factor(360)" and sc["output"] == "2^3 * 3^2 * 5"
            assert ran == [("sage", "factor(360)")]
            for bad in ("import os; os.system('id')", "factor os.system('id')", "print(open('/etc/passwd').read())",
                        "factor x^2 + __import__('os')", "run this code: 1+1"):
                st, r = await _rpc(http, base, "tools/call", {"name": "sage_compute", "arguments": {"request": bad}})
                assert r["result"]["isError"] is True
                assert r["result"]["structuredContent"]["error"] in ("not_in_catalogue", "request_error"), bad
            st, r = await _rpc(http, base, "tools/call", {"name": "sage_compute",
                                                          "arguments": {"request": "factor 360", "code": "id"}})
            assert r["error"]["code"] == P.INVALID_PARAMS                 # no `code` argument exists
            assert ran == [("sage", "factor(360)")]                        # nothing else ever ran


async def test_tools_read_library_dossiers_and_rate_limit(tmp_path):
    ctx = await _ctx(tmp_path)
    from madalean.dossiers import LibEntry
    d = ctx.repo.new("2 + 2 = 4", "demo", "Deux et deux")
    await ctx.repo.save(d)
    async with running(ctx) as (srv, base, _r):
        ctx.settings.mcp_server = True         # after the start (it reads the settings file)
        ctx.library.entries.append(LibEntry("sum_comm", "Commutativité", "theorem sum_comm (a b : ℕ) : a + b = b + a",
                                            "theorem sum_comm (a b : ℕ) : a + b = b + a := by omega", "demo"))
        async with aiohttp.ClientSession() as http:
            st, r = await _rpc(http, base, "tools/call", {"name": "library_search", "arguments": {"query": "sum_comm add"}})
            assert r["result"]["structuredContent"]["results"][0]["name"] == "sum_comm"
            st, r = await _rpc(http, base, "tools/call", {"name": "dossier_status", "arguments": {}})
            assert [x["id"] for x in r["result"]["structuredContent"]["dossiers"]] == [d.id]
            st, r = await _rpc(http, base, "tools/call", {"name": "dossier_status", "arguments": {"dossier_id": d.id}})
            assert r["result"]["structuredContent"]["dossier"]["title"] == "Deux et deux"
            st, r = await _rpc(http, base, "tools/call", {"name": "dossier_status", "arguments": {"dossier_id": "nope"}})
            assert r["result"]["isError"] is True
            st, r = await _rpc(http, base, "tools/call", {"name": "search_mathlib", "arguments": {"query": "add comm"}})
            assert r["result"]["structuredContent"]["status"] in ("ok", "indexing", "unavailable")
            old = T.REGISTRY["library_search"].rate
            T.REGISTRY["library_search"].rate = 3        # one call already made above
            try:
                outs = [(await _rpc(http, base, "tools/call", {"name": "library_search", "arguments": {"query": "x"}},
                                    rid=10 + i))[1]["result"] for i in range(3)]
            finally:
                T.REGISTRY["library_search"].rate = old
            assert [o["isError"] for o in outs] == [False, False, True]
            assert outs[2]["structuredContent"]["error"] == "rate_limited"
            async with http.get(base + "/api/mcp/activity?dir=in") as resp:
                act = (await resp.json())["activity"]
            assert act[0]["tool"] == "library_search" and act[0]["error"] == "rate limited"
            assert any(a["tool"] == "dossier_status" and a["ok"] for a in act)
    f = tmp_path / "config" / "logs" / "mcp-activity.jsonl"
    assert f.exists() and (f.stat().st_mode & 0o777) == 0o600
    assert all(json.loads(l)["dir"] == "in" for l in f.read_text().splitlines())


async def test_streamable_http_transport(tmp_path):
    ctx = await _ctx(tmp_path)
    async with running(ctx) as (srv, base, remote):
        ctx.settings.mcp_server = True         # after the start (it reads the settings file)
        async with aiohttp.ClientSession() as http:
            h = {"Accept": "application/json, text/event-stream"}
            st, r = await _rpc(http, base, "initialize", {"protocolVersion": P.LATEST, "capabilities": {},
                                                          "clientInfo": {"name": "t", "version": "0"}},
                               path="/api/mcp/http", headers=h)
            assert st == 403 and r["error"] == "mcp_off"                  # HTTP needs its own switch
            ctx.settings.mcp_server_http = True
            st, r = await _rpc(http, base, "initialize", {"protocolVersion": P.LATEST, "capabilities": {},
                                                          "clientInfo": {"name": "t", "version": "0"}},
                               path="/api/mcp/http", headers=h)
            assert st == 200 and r["result"]["serverInfo"]["name"] == "madalean"
            async with http.post(base + "/api/mcp/http", json={"jsonrpc": "2.0", "method": "notifications/initialized"},
                                 headers=h) as resp:
                assert resp.status == 202 and await resp.read() == b""
            st, r = await _rpc(http, base, "tools/list", path="/api/mcp/http",
                               headers={**h, "MCP-Protocol-Version": P.LATEST})
            assert st == 200 and r["result"]["tools"]
            st, r = await _rpc(http, base, "tools/list", path="/api/mcp/http",
                               headers={**h, "MCP-Protocol-Version": "1999-01-01"})
            assert st == 400
            async with http.get(base + "/api/mcp/http", headers={"Accept": "text/event-stream"}) as resp:
                assert resp.status == 405
            async with http.post(base + "/api/mcp/http", data='{"jsonrpc":"2.0","id":1,"method":"ping"}',
                                 headers={"Content-Type": "text/plain"}) as resp:
                assert resp.status == 415
            # a web page of another origin (CSRF) and the remote listener are refused
            async with http.post(base + "/api/mcp/http", json={"jsonrpc": "2.0", "id": 1, "method": "ping"},
                                 headers={"Origin": "http://evil.example", **h}) as resp:
                assert resp.status == 403
            async with http.post(base + "/api/mcp/http", json={"jsonrpc": "2.0", "id": 1, "method": "ping"},
                                 headers={"Sec-Fetch-Site": "cross-site", "Sec-Fetch-Mode": "no-cors"}) as resp:
                assert resp.status == 403
            for path in ("/api/mcp/http", "/api/mcp/rpc"):
                async with http.post(remote + path, json={"jsonrpc": "2.0", "id": 1, "method": "ping"}) as resp:
                    assert resp.status in (401, 403)
            async with http.get(remote + "/api/mcp") as resp:
                assert resp.status in (401, 403)


async def test_settings_are_host_only_and_connect_snippet(tmp_path):
    ctx = await started(make_ctx(tmp_path))
    _s, errors = await ctx.patch_settings({"mcp_server": True}, local=False)
    assert errors == ["host_only:mcp_server"]
    async with running(ctx) as (srv, base, _r):
        async with aiohttp.ClientSession() as http:
            async with http.get(base + "/api/mcp") as resp:
                d = await resp.json()
            assert d["server"]["enabled"] is False and d["servers"] == []
            c = d["server"]["connect"]
            assert c["args"][:2] == ["mcp", "serve"] and "--config-dir" in c["args"]
            assert c["json"]["mcpServers"]["madalean"]["command"].endswith("bin/madalean")
            assert c["http_url"].startswith("http://127.0.0.1:") and c["http_url"].endswith("/api/mcp/http")
            st, r = await _rpc(http, base, "tools/list")
            assert st == 403 and r["error"] == "mcp_off"                  # off by default


async def test_check_lean_real_lean(tmp_path, ws):
    """The strict verdict of the real Lean (skipped when no workspace is built)."""
    from madalean.context import ServerContext
    from madalean.paths import Paths
    ctx = ServerContext(Paths(tmp_path / "config", tmp_path / "cache"), workspaces=[ws], use_keyring=False)
    from madalean.brain.fake import FakeBrain, FakeLocal, FakeRetriever
    ctx.local = FakeLocal(ctx.slots, 0)
    ctx.brain, ctx.retriever, ctx.brain_kind = FakeBrain(local=ctx.local), FakeRetriever(), "fake"
    await ctx.start()
    ctx.settings.workspace = ws.key
    try:
        async with running(ctx) as (srv, base, _r):
            ctx.settings.mcp_server = True
            async with aiohttp.ClientSession() as http:
                st, r = await _rpc(http, base, "tools/call", {"name": "check_lean", "arguments": {
                    "statement": "theorem mcp_real : (2 : ℕ) + 2 = 4 := by sorry", "proof": "norm_num"}})
                assert r["result"]["structuredContent"]["ok"] is True, r
                st, r = await _rpc(http, base, "tools/call", {"name": "check_lean", "arguments": {
                    "statement": "theorem mcp_real : (2 : ℕ) + 2 = 4 := by sorry", "proof": "sorry"}})
                assert r["result"]["structuredContent"]["ok"] is False
    finally:
        await ctx.stop()


@pytest.mark.parametrize("raw", [b"\xff\xfe", b"null", b'{"jsonrpc":"2.0","id":true,"method":"ping"}',
                                 b'{"jsonrpc":"2.0","id":1,"method":"ping","params":[1]}', b'{"jsonrpc":"1.0"}'])
def test_protocol_parse_errors(raw):
    msg, err = P.parse(raw)
    assert msg is None and err["error"]["code"] in (P.PARSE_ERROR, P.INVALID_REQUEST)
