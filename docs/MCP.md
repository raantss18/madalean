# Madalean and the Model Context Protocol (MCP)

Session S-AZ, DECISIONS D58. Package `madalean/mcp/`, plugin `madalean/server/plugins/mcp.py`, settings screen
Réglages › Outils (MCP) (`web/src/screens/settings/McpSettings.svelte`), manual page `docs/manual/{fr,en}/mcp.md`.

Madalean speaks MCP both ways:

1. **as a server** — another assistant of the host (Claude Code, Claude Desktop, any agent launched by the user)
   uses a small, read-mostly set of Madalean's tools;
2. **as a client** — the prover agent (and, by name, the conductor's plans) can use tools of external MCP servers
   the user adds, as untrusted tools.

Everything is **off by default** and configured **on the host only**.

## 1. Protocol

JSON-RPC 2.0, MCP revision **2025-06-18** (also accepts 2025-03-26 and 2024-11-05 from a client; an unknown
version gets the latest). `madalean/mcp/protocol.py` implements only what is used:

| Method | Server side | Client side |
|---|---|---|
| `initialize` | answers `{protocolVersion, capabilities: {tools: {listChanged: false}}, serverInfo, instructions}` | sends it; refuses a server without `tools` or with an unknown version |
| `notifications/initialized` | ignored (no response) | sent after `initialize` |
| `ping` | `{}` | answered `{}` when a server pings |
| `tools/list` | the available tools (no pagination: the list is short) | follows `nextCursor` (10 pages, 200 tools at most) |
| `tools/call` | see §2 | see §4 |
| anything else | `-32601` method not found | a server request other than `ping` → `-32601` (no sampling, roots, elicitation) |

Errors: `-32700` parse error (id `null`), `-32600` invalid request (not JSON-RPC 2.0, bad id, params not an object,
**batches** — removed from MCP in 2025-06-18), `-32601` unknown method, `-32602` unknown tool or invalid arguments
(`data.problems`: the list of schema problems), `-32603` internal error, `-32000` Madalean unavailable (the stdio
bridge: server not running, or « Madalean comme serveur MCP » switched off). A tool that runs but fails answers a
normal result with `isError: true` and a JSON `{error, message, …}`.

Messages are at most 2 MB. Results carry the JSON both as text (`content[0].text`) and as `structuredContent`.

**Why no SDK.** The official Python SDK (`mcp`) needs pydantic (a compiled extension), starlette, uvicorn, httpx,
anyio, sse-starlette, pydantic-settings and jsonschema: a second web stack beside aiohttp, outside the signed,
pinned conda lock (`madalean/deps/locks`), for a protocol subset of a few hundred lines. The subset is tested
message by message (`tests/test_mcp_server.py`, with a raw stdio harness that does not use Madalean's own client).

## 2. Madalean as an MCP server

### Transports

- **stdio** — `madalean mcp serve [--port P] [--config-dir D]`, started by the client. The bridge
  (`mcp/bridge.py`) answers `initialize` / `ping` itself and relays `tools/list` / `tools/call` to the running server
  (`POST /api/mcp/rpc` on the local listener, port from `server.json`): the Lean runner, the declaration index, the
  library and the dossiers belong to that one process (and its lock). Stdout carries protocol messages only.
- **streamable HTTP** — `POST http://127.0.0.1:<port>/api/mcp/http`, only when `mcp_server_http` is also on.
  JSON responses (no SSE stream is offered); notifications answer `202`; `GET`/`DELETE` answer `405`; an unknown
  `MCP-Protocol-Version` header answers `400`; a body that is not `application/json` answers `415`. Stateless: no
  `Mcp-Session-Id`.

Both routes are **host-only** (403 on the remote and LAN listeners) and behind the local listener's checks
(loopback `Host`, exact `Origin`, Fetch Metadata — a web page cannot drive them). Switches (host-only settings):
`mcp_server` (both transports), `mcp_server_http`, `mcp_server_sage`.

How to connect (Réglages › Outils (MCP) shows the exact text for this installation):

```sh
claude mcp add madalean -- ~/.local/share/madalean/current/bin/madalean mcp serve
claude mcp add --transport http madalean http://127.0.0.1:11500/api/mcp/http
```
```json
{"mcpServers": {"madalean": {"command": "/home/<you>/.local/share/madalean/current/bin/madalean",
                             "args": ["mcp", "serve"]}}}
```

### Tools

Registry: `madalean/mcp/tools.py` (`register(Tool(...))`; a tool whose `available(ctx)` is false is not listed and
cannot be called). Every input schema is strict (`additionalProperties: false`, lengths, ranges, patterns, enums; no
coercion — `madalean/mcp/schema.py`). Workspace keys and ids match `^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$`.

| Tool | Input | What it does | Rate / min |
|---|---|---|---|
| `search_mathlib` | `query` (1–200), `k` (1–20), `workspace` | the workspace's declaration index (`retriever.search`): name, kind, signature, doc, module; `status` ok / indexing / unavailable | 60 |
| `check_lean` | `statement` (≤ 20 000), `proof` (≤ 100 000), `workspace` | with `proof`: the statement is pinned (`assemble_proof`), axiom probe, **fresh strict verdict** (`ctx.lean.check(..., warm=False)`); without: the statement compiles (`sorry` allowed). D28 code is refused before compiling. Returns ok, verdict, summary, errors, axioms, `via: fresh`, the checked code | 20 |
| `certify` | `statement`, `workspace` | Madalean's certificates (D52): fixed Sage producer + fresh strict Lean | 10 |
| `explain_lean` | `code` (≤ 50 000), `mode` error / lines, `part`, `error`, `workspace` | « Expliquer » (D45); `fix` only when Lean accepted it. Uses Madalean's models (annotation `openWorldHint`) | 10 |
| `library_search` | `query`, `k`, `workspace` | the user's library (results already accepted by Lean) | 60 |
| `dossier_status` | `dossier_id` or `query`, `k` | a dossier (statement, proof when current, running job's state) or the latest ones | 60 |
| `literature_search` | `query`, `k` | listed only when the literature package (session S-AX) provides `madalean.literature.mcp_search(ctx, query, k) -> list[dict]` | 20 |
| `sage_compute` | `request` (words, ≤ 2000), `language` sage / python | listed only with `mcp_server_sage`. The request is analysed (`research/intent.py`); runs **only** when the verified catalogue (D39, `codecat.assemble`) writes the whole code; then in Calcul's sandboxed kernel (key `madalean-mcp`, 30 s). Anything else: `not_in_catalogue`. There is no argument for code | 10 |

All tools are read-only for Madalean's data: nothing creates a dossier, a library entry, a note or a file in a
workspace (tested by snapshotting the config directory). Limits: 120 calls per minute in total, the per-tool rates
above, two Lean checks at a time, 600 s per call.

## 3. Activity log

`<config>/logs/mcp-activity.jsonl` (0600, rotated at 1 MB, one old file kept), and the latest 200 in memory
(`GET /api/mcp/activity`). One line per call, both directions: `{t, dir: in|out, transport, server, tool, ok, ms,
in, out, args, error}` — `args` is a 160-character redacted preview; the answer itself is never logged.

## 4. Madalean as an MCP client

`madalean/mcp/client.py`. The list is `<config>/mcp-servers.json` (0600), edited from the host only:
`{id, name, transport: stdio|http, command: [argv], url, enabled, allowed: [tool], tools: [cached], timeout_s,
status}`.

1. **Add** (`POST /api/mcp/servers`): a command (split like a shell would, no shell is run) or a URL (http only
   for 127.0.0.1 / localhost / ::1, https elsewhere, no credentials; in Local mode only this computer). The new
   server is **disabled with an empty allow-list**.
2. **Test** (`POST /api/mcp/servers/{id}/test`): start, `initialize`, `tools/list`, stop. Tools are kept with a
   sanitised schema (a strict JSON-Schema subset: `$ref`, `oneOf`, vendor keys… dropped) and a capped description;
   a tool whose name is invalid is dropped; a tool whose description addresses a model (`looks_like_injection`,
   chat-template markers) is marked `safe: false` and can never be allowed.
3. **Enable and allow** (`PATCH`): only tested, safe tool names are accepted in `allowed`.

At proof time `madalean.mcp.agent_tools(ctx)` gives the prover agent (`prove_with_agent(extra_tools=…)`,
`pipeline/runner.py`) one `ToolSpec` per allowed tool of each enabled server, named `mcp__<server>__<tool>`; the
system prompt gains `UNTRUSTED_RULE`. An external tool can never replace Madalean's `submit` / `lean_check`
(duplicate names are dropped), and the proof is re-checked by the server anyway. The conductor's plan and
proof-fix prompts name the allowed tools so it can direct work to them; it makes no tool call itself.

Each call: allow-list and enablement checked **before** sending; arguments validated against the sanitised schema;
100 calls per minute; two calls at a time per server; timeout `timeout_s` (default 30, at most 120 s; first start 60
s); answers capped at 1 MB read and 16 000 characters given to a model; stdio servers kept warm and stopped after 5
idle minutes or after a timeout / protocol error.

**Output handling** (`result_text`): text parts kept (images / audio / binary resources replaced by « [… omitted] »),
control, zero-width and bidi characters removed, chat-template markers (`<|im_start|>`, `[INST]`, `<system>`…)
removed, wrapped by `wrap_untrusted` (so `<<<`/`>>>` inside cannot close the block), and a header that says it is
untrusted data — with a WARNING when the text addresses a model. The activity log notes « flagged ».

**Environment of a stdio server**: `PATH, HOME, LANG, LC_ALL, LC_CTYPE, USER, LOGNAME, SHELL`, `TMPDIR` = its private
directory `<cache>/mcp/<id>/tmp` (0700), `NO_COLOR`. No API key, no Madalean token, nothing else of the server's
environment (tested). Working directory: `<cache>/mcp/<id>` (0700). New session, stopped with its process group.
HTTP servers receive no cookie (dummy jar), no `Authorization`, no proxy from the environment.

### Example: a Lean language-server MCP

`lean-lsp-mcp` (third party, MIT) can be installed without sudo by the user (`uv tool install lean-lsp-mcp`, or
run by `uvx lean-lsp-mcp`); nothing is installed by Madalean. Add the command `uvx lean-lsp-mcp`, test, enable, and
allow, for example, its goal / diagnostics / search tools. It needs a Lean project (see its documentation for how to
point it at one, e.g. its project-path option or by starting it in the project directory); Madalean's environment
allow-list does not pass extra variables. Its answers stay untrusted data: Lean in Madalean's sandbox still decides.

## 5. API

See docs/API.md §6h.

## 6. Tests

- `tests/test_mcp_server.py` — stdio conformance with a raw harness (initialize and version negotiation,
  initialized, ping, tools/list, tools/call, parse error, batch, invalid request, unknown method, unknown tool,
  invalid arguments, switched off, server not running); strict schemas; `check_lean` fresh + strict + pinned
  statement + writes nothing; D28 refusal; `sage_compute` off by default and catalogue-only (injection attempts in
  the request); library / dossier tools; rate limit; activity log (0600); streamable HTTP (switch, 202, 405, 400,
  415, cross-origin and cross-site refused, remote listener refused); host-only settings; real Lean strict verdict
  when a workspace is built.
- `tests/test_mcp_client.py` — with `tests/fake_mcp_server.py`: off by default, tools listed and sanitised,
  poisoned description refused, allow-list and enablement enforced before sending (the fake server logs every call
  it receives), schema validation, injection neutralised, no keys in the child's environment, timeouts, unknown
  command, silent server; Madalean's own HTTP endpoint used as an external server through the host-only API;
  the prover agent receives the allowed tools, keeps its own `submit`, and gets `UNTRUSTED_RULE`.
- `web/e2e/mcp.spec.ts` — the settings screen (switch, snippet, refused address, add / test / allow / remove, axe
  in both themes), host-only API.
