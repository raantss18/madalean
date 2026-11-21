# Madalean 2.0 — HTTP + WebSocket API (source of truth for the web UI and the shells)

Server: `madalean serve` (package `madalean/server/`). All bodies are JSON (UTF-8) unless stated. All paths below
start with `/api`. Timestamps are Unix seconds (float). Ids are strings matching `^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$`.

- [Listeners and authentication](#1-listeners-and-authentication)
- [Conventions (errors, messages, i18n)](#2-conventions)
- [Endpoints](#3-endpoints)
- [WebSocket](#4-websocket-apiws)
- [Types (TypeScript)](#5-types)
- [Plugins](#6-plugins-for-other-sessions)
- [Demo mode](#7-demo-mode)

## 1. Listeners and authentication

| Listener | Address | Trust |
|---|---|---|
| local | `127.0.0.1:11500` (`--port`) | trusted (the host's own browser / desktop shell): no token |
| remote | `127.0.0.1:11501` (`--remote-port`), published by `tailscale serve --bg --https=10500 http://127.0.0.1:11501` | device token required |
| LAN (off by default, setting `lan_listener` + restart, or `serve --lan`) | `0.0.0.0:<lan_port>` (11502) | device token required |

The running ports are written to `<config>/server.json` (`{pid, local, remote, lan?, version, demo}`).

**Remote/LAN listener.** Every request needs a device token except: `GET /api/hello`, `POST /api/pair`,
`POST /api/logout`, `GET /api/session` (one-time ticket, §3.1b), and `GET` of static UI files (anything not under `/api` or `/jupyter`, so the pairing screen
loads). Token transport:
- apps (shells): `Authorization: Bearer <token>` (also on the WebSocket handshake);
- browser: the cookie `madalean_token` (`HttpOnly; Secure; SameSite=Strict; Path=/`, 10 years) set by `POST /api/pair`.

Missing/invalid/revoked token → `401 {"error":"unauthorized"}`. Host-only endpoints (marked **host**) answer
`403 {"error":"host_only"}` on the remote/LAN listeners.

**Origin / Host checks.** On state-changing methods (POST/PATCH/PUT/DELETE) and WebSocket upgrades, a browser
`Origin` header must be same-origin (its `host:port` equals the request's `Host` or `X-Forwarded-Host`), or a
loopback origin on the local listener; `Origin: null` or a foreign origin → `403 {"error":"bad_origin"}`. Requests
authenticated with a Bearer header skip the Origin check (an attacker page cannot attach it). No `Origin` header
(CLI, curl, native apps) is accepted. On the local listener the `Host` header must be `127.0.0.1`, `localhost` or
`[::1]` (DNS-rebinding guard) → else `403 {"error":"bad_host"}`. CORS is closed: no `Access-Control-*` header is
ever sent. Responses carry `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`,
`X-Frame-Options: SAMEORIGIN`, and `/api/*` responses `Cache-Control: no-store`.

**Pairing.** On the host, `POST /api/pairing/start` (or `madalean pair`) gives a 6-digit code valid 5 minutes,
single use. The device posts it with its name to `POST /api/pair` and receives its token (256 bits, shown once; only
its SHA-256 is stored in `devices.json`, mode 0600). 5 wrong codes → pairing locked 10 minutes and the code burnt.
`/api/pair` is also rate-limited (10/min per client, 30/min overall) → `429 {"error":"rate_limited"}`.

## 2. Conventions

**Errors**: `{"error": "<kind>", "message"?: Message, ...}` with an HTTP status: 400 bad input (`bad_json`,
`bad_id`, `bad_fields`, `bad_plan`, `bad_stage`, `bad_format`, `bad_path`, `empty`, `bad_statement`…), 401
`unauthorized`, 403 (`host_only`, `bad_origin`, `bad_host`, `jupyter_host_only`, pairing `wrong`/`expired`/
`no_code`), 404 `not_found`, 409 (`busy` — the dossier already has an active job, with `job`; `no_workspace`,
`no_proof`, `no_statement`, `jobs_running`), 413, 422 `no_lemmas`, 429 (`rate_limited`, `locked`), 503
(`no_model`, `jupyter_unavailable`).

**Messages (i18n)**: every user-facing text produced by the server is a `Message`:
`{"key": "<French source template>", "params": {...}, "text": "<text in the interface language>"}`. The language
is the setting `language` (`fr` default, `en`); clients may re-localize from `key` + `params`. Thread events store
the text as written at the time (`Event.text`) plus `key`/`params`; when `params.detail` is present the text is
`localized(key) + "\n" + detail` (the detail is model output, not translated).

**Model attribution**: every version (`Version.model`) and every thread event produced by a model
(`Event.model`) carries the model key `"<provider>:<model_id>"` (e.g. `local:Goedel-Prover-V2-8B.Q4_K_M.gguf`,
`anthropic:claude-…`). Lean results and user actions have `model: ""`.

**Modes**: `mode` = `local` (nothing leaves the machine) | `auto` | `online`. **Strategies** (proof search):
`goedel` (1.1.4 loop, local model) | `agent` (tool-using model) | `auto` (agent with an online model when the mode
allows, else goedel; goedel also as a fallback when the agent fails). Whatever the strategy, a proof is accepted
only when the server's Lean check gives the strict verdict.

## 3. Endpoints

### 3.1 Hello, pairing, devices

`GET /hello` (public)
```json
{"name":"madalean","version":"2.0.0.dev0","paired":true,"local":false,"host_name":"nitro","demo":false,"lang":"fr"}
```
`paired` = the request carried a valid token (always true on the local listener).

`POST /pair` (public) `{"code":"123456","device_name":"Pixel 8"}` →
`200 {"token":"<43 chars>","device":Device}` + `Set-Cookie: madalean_token=…`. Errors: 403 `wrong`|`expired`|
`no_code` (with `message`), 429 `locked` (`message.params.m` = minutes) | `rate_limited`.

`POST /logout` (public; remote) → revokes the calling device's token and clears the cookie → `{"ok":true}`.

`POST /pairing/start` **host** → `{"code":"482913","expires":1795250000.0,"expires_in":300}` (replaces any
previous code). `GET /pairing` **host** → `{"active":true,"expires_in":212.4,"locked_for":0}`.

`GET /devices` **host** → `{"devices":[Device]}`. `DELETE /devices/{id}` **host** → `{"ok":true}` (404 unknown).
Both publish `devices.updated`.

### 3.1b Shell sessions (desktop / Android shells, docs/SHELLS.md)

The shells never put the device token in a URL: they ask for a one-time ticket with their token and let the web view
swap it for the cookie.

`POST /session/ticket` — `Authorization: Bearer <device token>` only (a cookie is refused: no CSRF surface; works on
both listeners) → `200 {"ticket":"<32 chars, 192 random bits>","expires_in":60}`, `Cache-Control: no-store`;
otherwise `401 {"error":"unauthorized"}`. The ticket is single use, valid 60 s, bound to the device, kept in memory
only (lost on restart).

`GET /session?ticket=<t>&next=<path>` — public (the ticket is the credential):
- valid ticket → **`200 text/html`** (not a redirect: WebKitGTK withholds a `SameSite=Strict` cookie after a
  redirect chain started by a cross-site page) with
  `Set-Cookie: madalean_token=<session secret>; HttpOnly; SameSite=Strict; Path=/; Max-Age=315360000` (+ `Secure`
  when the request came over HTTPS or with `X-Forwarded-Proto: https`), `Cache-Control: no-store`,
  `Referrer-Policy: no-referrer`, `Content-Security-Policy: default-src 'none'; script-src 'none'; …`, body
  `<meta http-equiv="refresh" content="0;url=NEXT">`. NEXT = `next` HTML-escaped when it is a relative path
  starting with a single `/`, without `//` in the path, backslash or control characters; otherwise `/`.
  The cookie value is a fresh session secret bound to the device (only its SHA-256 is stored, in `devices.json`;
  revoked with the device), not the device token.
- missing / unknown / expired / reused ticket, or revoked device → `303 Location: /pair?reason=ticket`, no cookie.
- The query string of this route is never logged (no access log; tested).

`POST /devices/self/forget` — the calling device (Bearer, or the cookie of a paired browser) revokes itself →
`204` (cookie cleared); `401` without a device credential (also on the local listener: the host is not a device).
Same effect as `POST /logout`.

### 3.2 State

`GET /state` → everything a client needs at start:
```json
{"version":"2.0.0.dev0","host_name":"nitro","local":true,"device":null,"demo":false,"brain":"real",
 "lang":"fr","seq":1532,"boot":1795243259038,
 "settings":Settings,"host_only_settings":["agent_exec","lan_listener","lan_port","remote_jupyter"],
 "projects":[Project],"dossiers":[DossierSummary],
 "jobs":{"active":[Job],"recent":[Job]},
 "models":ModelsInfo,"system":{"monitor":Monitor,"slots":Slots,"lean_running":0,"workspaces":[WorkspaceInfo]},
 "library":{"count":12},"updates":UpdatesStatus,"jupyter":JupyterStatus,"migration":{…}}
```
`brain`: `real` (S-B engine), `fake` (scripted: demo, or engine missing — then `/system` reports it), `custom`.
Use `seq`/`boot` with the WebSocket `resume`.

### 3.3 Settings

`GET /settings` → `{"settings":Settings}`.
`PATCH /settings` `{key: value, …}` (partial; `server` and `sampling` are merged) → `{"settings":Settings}` and
event `settings.updated`. Validation: unknown key, bad enum (`mode`, `prove_strategy`, `language`), out of range
(`prove_attempts` 1–64, `translate_attempts` 1–10, `compile_timeout_s` 10–1800, `agent_max_steps` 1–200,
`agent_max_seconds` 30–7200, `lan_port` 1024–65535) → `400 {"error":"invalid_settings","details":["invalid:mode",…],
"settings":…}`; host-only keys from a remote device → `403` with `details:["host_only:lan_listener"]`. Nothing is
applied when any key is refused. `lan_listener`/`lan_port` take effect at the next start.

### 3.4 Projects

| | |
|---|---|
| `GET /projects` | `{"projects":[Project]}` |
| `POST /projects` `{title, description?, workspace?}` | `201 {"project":Project}` (`400 title_required`) |
| `GET /projects/{id}` | `{"project":Project,"dossiers":[DossierSummary]}` |
| `PATCH /projects/{id}` `{title?, description?, workspace?, archived?, refs_file?, sources?}` | `{"project":Project}` |
| `DELETE /projects/{id}` | `{"ok":true,"undo":"/api/projects/{id}/restore"}` (moves its directory to `.trash`; its dossiers keep their `project_id`) |
| `POST /projects/{id}/restore` | `{"project":Project}` |

Storage: `<config>/projects/<id>/project.json` (one directory per project: `refs.bib` and other per-project files
live there). Unknown fields of the file are preserved.

### 3.5 Dossiers

`GET /dossiers?project=<id>` → `{"dossiers":[DossierSummary]}` (most recently updated first; `project=` filters,
empty string = dossiers without project).

`POST /dossiers` — create, and start by default:
```json
{"problem":"Montrer que la somme de deux entiers pairs est paire.",   // natural language (optional)
 "statement":"theorem t (a b : ℕ) … := by sorry",                     // Lean statement (optional)
 "title":"…","project_id":"p-…","workspace":"lean-prover49","kind":"theorem","parent_id":"",
 "start":true,"mode":"auto","strategy":"auto","rename":true}
```
- with `statement`: the statement is normalised (`prepare_statement`: header added, `lemma`/`example` → `theorem`,
  ends with `:= by sorry`) and its theorem renamed to the dossier's unique name (`rename:false` keeps it); plan
  `notes → proof → explanation`;
- with only `problem`: plan `understand → statement → proof → explanation`;
- → `201 {"dossier":Dossier,"job":Job|null}`; `400 bad_statement` (with `message.text`).

`GET /dossiers/{id}` → `{"dossier":Dossier,"job":Job|null (active job),"children":[DossierSummary]}`.

`PATCH /dossiers/{id}` `{title?, project_id?, archived?, workspace?, kind?, refs?, source?, uses?, retry_parent?,
problem?}` → `{"dossier":Dossier}` (400 `bad_fields`).

`DELETE /dossiers/{id}` → `{"ok":true,"undo":…}` (409 `busy` while a job runs). `POST /dossiers/{id}/restore` →
`{"dossier":Dossier}`.

`POST /dossiers/{id}/message` `{"text":"et la réciproque","stage":"auto|statement|proof|explanation","mode"?,
"strategy"?}` → `202 {"job":Job,"stage":"auto|statement|proof|explanation"}`. Behaviour of 1.1.4:
- no statement yet → the text completes the problem; full plan;
- `stage:"auto"` and a routing model available → plan `[route]`: the general model decides (and writes the new
  theorem for STATEMENT), with the keyword router as fallback/override (D26);
- `stage:"auto"` without routing model → keyword router; explicit stage → that stage's plan:
  `statement` = statement(request) → proof → explanation; `proof` = proof(request) → explanation (refinement of the
  current proof when it proves the current statement, else a hint appended to the Goedel prompt);
  `explanation` = explanation(request) (preceded by proof when the proof is not current).
The user message is added to the thread (event `user`, `stage` updated by `route`). 409 `busy`.

`POST /dossiers/{id}/statement` `{"code":"…","check":true}` — the user edited the Lean statement: new statement
version (`source:"user"`), event; with `check` (default) Lean compiles it first →
`{"dossier":Dossier,"check":CheckResult|null}`; the version's `ok` = `check.statement_ok`.

`POST /dossiers/{id}/check` `{"what":"statement"|"proof"}` (default: proof if current) → `{"what":…,"check":CheckResult}`
(proof = strict verdict with the axiom probe). Does not modify the dossier.

`POST /dossiers/{id}/run` `{"plan":["proof",{"stage":"explanation","request":"plus simple"}],"mode"?,"strategy"?}`
→ `202 {"job":Job}`. Stages: `understand route statement notes proof explanation informal`.

`POST /dossiers/{id}/stop` → `{"stopped":true|false}` (cancels the active job: model request aborted, Lean killed;
event `Arrêté à votre demande.`; dossier status `stopped`, or `proved` if the current proof is still valid).

`POST /dossiers/{id}/versions/{kind}/{index}/restore` (`kind` = `statement|proof|explanation`) → `{"dossier":Dossier}`
(nothing is deleted; restoring a proof also restores its statement). 404 bad index, 409 busy.

`GET /dossiers/{id}/jobs[?raw]` → `{"jobs":[Job]}` (history, last 50, oldest first, + the active one; `raw` adds
the model answers to attempts).

`POST /dossiers/{id}/split` `{"lemmas"?:[{"title"?,"statement"?|"problem"?}],"n"?:4,"start"?:true,"mode"?}` —
« split into lemmas ». Without `lemmas` a model (role `prove`) proposes up to `n` Lean lemmas. Creates child
dossiers (`parent_id`, `kind:"lemma"`, same project/workspace) and starts them (in parallel, subject to slots); sets
`parent.retry_parent`. When all children are finished and ≥ 1 is proven, the parent is re-run automatically
(`proof → explanation`, automatic-priority job) with the proven children's library entries forced in as lemmas.
→ `201 {"children":[Dossier],"jobs":[Job]}`; 409 `no_statement`, 422 `no_lemmas`, 503 `no_model`.

`GET /dossiers/{id}/export?format=pdf|tex|lean|md|zip|html` → the file (`Content-Disposition: attachment;
filename="…"`). Header `X-Madalean-Fallback`: `""`, `"verbatim"` (model texts printed verbatim after a failed TeX
build) or `"html"` (no TeX engine, or TeX failed twice: a self-contained HTML is returned instead of the PDF, with
`Content-Type: text/html` — the UI should open it and offer « print to PDF »). The export never fails because of
model text. Content: title → statement (natural language) → Lean statement + gloss (`statement_notes`) →
natural-language proof (`informal_proof`, else the explanation) → Lean proof → verification stamp (Lean version,
Mathlib revision, date of the check, axioms, model) → appendix: tactic-by-tactic explanation. Unproved dossiers are
marked « Non prouvé / Not proved » and have no stamp. Typical PDF time: 2–4 s.

### 3.6 Jobs

`GET /jobs` → `{"active":[Job],"recent":[Job]}` (in-memory, last 200). `GET /jobs/{id}` → `{"job":Job}` (with raw
answers). `POST /jobs/{id}/cancel` → `{"cancelled":bool}`.

Job states: `queued` (waiting for a slot: see `waiting` = `gpu|online|lean`) ⇄ `running` → `done | failed |
cancelled`. Slots: `gpu` 1 (the local llama-server, model swap per role, reentrant per job), `online` 3 (any model
call when mode ≠ local), `lean` 2 (compilations). A job holds a slot only during the step that needs it; waiters
are served user-started jobs first, then FIFO.

### 3.7 Library

`GET /library` → `{"entries":[LibEntry]}`. `DELETE /library/{name}` → `{"removed":LibEntry}` (undo: `POST
/library/restore {"entry":LibEntry}` → `{"ok":true}`, 409 `exists`). `GET /library/export?workspace=<key>` → one
`.lean` file (text/plain, attachment) with every result of the workspace, dependencies first. Event
`library.updated {added|removed}`.

### 3.8 Free Lean check and LaTeX import

`POST /check` `{"code":"import Mathlib\n…","workspace"?,"strict"?:false,"timeout"?:180}` →
`{"check":CheckResult,"workspace":"lean-prover49"}`. `strict:true` = proof mode (target = last theorem, axiom
probe, forbidden constructs). Runs in a `lean` slot. 409 `no_workspace`, 400 `no_theorem`.

`POST /import/tex` — `multipart/form-data` with field `file` (≤ 5 MB) or JSON `{"tex":"…"}` →
`{"statements":[{"title":"Théorème 1 — Euclide","body":"…"}]}` (theorem-like environments, else the document body).

### 3.9 Models

`GET /models` → `ModelsInfo`:
```json
{"brain":"real","mode":"auto",
 "local":{"state":"ready","model":"Goedel-Prover-V2-8B.Q4_K_M.gguf","port":8766,"offload":"37/37","load_seconds":4.1,
          "ctx":24576,"gpu_layers":99,"notes":[],"error":null,"holder":"j-1a2b…",
          "roles":{"formalize":"Goedel-Formalizer-V2-8B.Q4_K_M.gguf","prove":"…","explain":"Qwen3-8B-Q4_K_M.gguf"}},
 "local_files":[{"file":"…gguf","path":"~/models/…","size":5027783488,"quant":"Q4_K_M","arch":"qwen3","n_layers":36}],
 "roles":{"prove":{"preferred":"","candidates":[ModelRef]}, "understand":…, "route":…, "formalize":…, "explain":…, "assistant":…},
 "status":{…brain.status()…}, "keys":{"anthropic":true}}
```
`POST /models/keys` `{"provider":"anthropic","key":"sk-…"}` → `{"provider":"anthropic","set":true,"backend":"keyring"|"file"}`.
Keys are stored with `secret-tool` when available, else `keys.json` (0600); they are **never** returned, logged or
sent elsewhere. `DELETE /models/keys/{provider}` → `{"provider":…,"set":false,"existed":bool}`. Event
`models.status {keys}`.
`POST /models/test` `{"provider"}` → `{"provider","ok":bool|null,"reason"?}` (`null` + `not_supported` when the
engine has no test). `POST /models/refresh` → `ModelsInfo` (rescan `~/models`, refresh the online catalogue).
`POST /models/local/stop` → unload the local model (409 `busy` while a job holds the GPU).
Choosing a model per role: `PATCH /settings {"prefer":{"prove":"anthropic:claude-…"}}`.

### 3.10 System, updates

`GET /system` → `{"monitor":Monitor,"slots":Slots,"lean_running":[{pid,workspace,started}],"workspaces":[WorkspaceInfo],
"checks":[HealthCheck],"local":{…},"brain":"real"}`. Health check ids: `workspace`, `llama`, `model_prover`,
`model_formalizer`, `model_explainer`, `tex`, `font_dejavu_sans_mono`, `font_noto_sans_math`, `jupyter`, `disk`,
`brain`; `repair` names the repair id to offer.

`POST /system/repair/{id}` **host**, ids: `workspaces` (rescan), `models` (rescan `~/models`), `local_model`
(stop the local server; 409 busy), `names_index` (rebuild the declarations index; → `{"names":164474}`).

`GET /updates` → `UpdatesStatus`. `POST /updates/check` → `202 {"checking":true}` (result as `updates.status`
event + a `toast`). `POST /updates/install {"key":"mathlib"|"prover"|"formalizer"|…}` → `202 UpdatesStatus`
(progress as `updates.status` events; 409 `busy`/`jobs_running`, 404 unknown). `POST /updates/cancel` →
`{"cancelled":bool}` (the old version is kept). Checks run weekly at start when `check_updates` (GitHub tags of
Mathlib, Hugging Face Goedel models); the list of checkers is data-driven (`madalean.updates.register_checker`).

### 3.11 Assistant

`POST /assistant` `{"messages":[{"role":"user","content":"…"}],"context"?:{"lean"?,"notebook"?,"cell"?,"cell_type"?,
"cells"?:[…],"text"?,"dossier_id"?},"mode"?}` → `202 {"request_id":"a-…"}`. The answer streams on the WebSocket:
`assistant.token {request_id, kind, text}` … then `assistant.done {request_id, text, model, finish}` or
`assistant.error {request_id, error, text}`. `dossier_id` adds the dossier's current proof/statement as context.
`POST /assistant/{request_id}/stop` → `{"stopped":bool}` (then `assistant.done` with `finish:"cancelled"`).

### 3.12 Jupyter / Sage

Reachable from the local listener; from paired devices only when the host enabled `remote_jupyter` (else
`403 jupyter_host_only`).

`GET /jupyter` → `JupyterStatus` `{"state":"stopped|starting|ready|failed","port":null,"root_dir":"~/Documents/Madalean/notebooks",
"kernels":["python3","sagemath"],"error":"","available":true,"lean_kernel":{"available":false,"note":"…"}}`.
`POST /jupyter/start` → JupyterStatus (idempotent; ~3–8 s). `POST /jupyter/stop` → JupyterStatus.
`GET /jupyter/notebooks?path=` → `{"notebooks":[{"name","path","type","last_modified"}]}`.
`GET /jupyter/notebook?path=a/b.ipynb` → `{"path","cells":[{"index","cell_type","source","outputs_text"}],"kernel"}`.
`POST /jupyter/notebook {"path","kernel"?:"python3"}` → `201 {"path"}` (creates parent folders).
`POST /jupyter/cells {"path","source","cell_type":"code|markdown|raw"}` → `{"path","index"}`.
Paths are relative to the notebooks root; `..`, absolute, hidden or `~` paths → `400 bad_path`.

**Proxy** `/jupyter/…` (all methods + WebSocket): JupyterLab itself (`/jupyter/lab`, kernels websockets…), behind
Madalean's authentication; Jupyter's own token stays server-side (the proxy strips the client's Cookie/Authorization,
adds Jupyter's token, removes it from HTML/JSON responses). The UI embeds `/jupyter/lab` in an iframe (same origin).
Jupyter is started on demand by the proxy. Lean 4 kernel: not installed (no reliable kernel — see `lean_kernel.note`).

### 3.13 Static UI

`GET /` and any non-API path: files of `madalean/static/` (`--static DIR` to override). Unknown paths without an
extension → `index.html` (SPA routing); missing files with an extension → 404. Files under `/assets/` are served
`Cache-Control: public, max-age=31536000, immutable`, others `no-cache`. When `static/` has no `index.html`, a
placeholder page is served.

## 4. WebSocket `/api/ws`

Same authentication as HTTP (local: none; remote: Bearer header or cookie; Origin checked). On connect the server
sends `{"type":"hello","seq":<current>,"boot":<id>,"version","local"}`. Then every event, to every client:
`{"type", "seq", "ts", …}`. `seq` increases by 1 per event (shared by all clients). Client → server:

- `{"type":"resume","seq":<last seq seen>,"boot":<boot from hello/state>}` → the missed events (from a ring buffer of
  5 000), in order, then live events without duplicates; if they are no longer available or `boot` differs (server
  restarted) → `{"type":"resync","seq","boot"}`: reload `GET /state`.
- `{"type":"ping","t":…}` → `{"type":"pong","t":…}` (the server also sends WS pings every 30 s).

A client too slow to read (10 000 queued events) is disconnected with close code 4000: reconnect + resume.

| type | payload |
|---|---|
| `job.updated` | `{job: Job}` — on submit, state/stage/waiting changes, every attempt change, end |
| `job.token` | `{job_id, stage, attempt, kind, text}` — streamed model text, coalesced every 100 ms; `attempt` = index in `job.attempts` (−1 for single calls: understand, route, notes, explanation, informal); `kind` = `text`, `thinking`, or for agents `tool_call`/`tool_result`/`info` |
| `job.info` | `{job_id, stage, text, data}` — engine notices (model switch, fallback) |
| `dossier.updated` | `{dossier: Dossier}` — full dossier after each change |
| `dossier.deleted` | `{id}` |
| `project.updated` | `{project: Project}` |
| `project.deleted` | `{id}` |
| `library.updated` | `{added?: name, removed?: name}` |
| `system.status` | `{system: {monitor, slots, lean_running}}` — every 3 s |
| `models.status` | `{local?: LocalStatus, keys?: {provider: true}}` |
| `settings.updated` | `{settings: Settings}` |
| `devices.updated` | `{devices: [Device]}` |
| `updates.status` | `{updates: UpdatesStatus}` |
| `jupyter.status` | `{jupyter: JupyterStatus}` |
| `assistant.token` / `assistant.done` / `assistant.error` | see §3.11 |
| `toast` | `{level: "info"|"ok"|"warn"|"error", key, params, text}` |

Plugins may publish other types (ignore unknown types).

## 5. Types

```ts
type Message = { key: string; params: Record<string, unknown>; text: string };
type Mode = "local" | "auto" | "online";
type Strategy = "goedel" | "agent" | "auto";
type Stage = "understand" | "route" | "statement" | "notes" | "proof" | "explanation" | "informal";

interface Device { id: string; name: string; created: number; last_seen: number; last_ip: string; sessions: number }

interface Project {
  id: string; title: string; description: string; workspace: string; created: number; updated: number;
  archived: boolean; refs_file: string; sources: unknown[]; [extra: string]: unknown;   // unknown fields kept
}

interface Version {
  code: string;            // Lean (statement/proof) or Markdown with $math$ (explanation, notes, informal proof)
  t: number; source: "ai" | "user"; ok: boolean;
  parent: number | null;   // statement index (proof, notes) or proof index (explanation, informal proof)
  note: string;            // the request that produced it
  model: string;           // "provider:model_id", "" for user versions
  meta: { axioms?: string[] | null; lean?: string; mathlib?: string; workspace?: string; seconds?: number;
          strategy?: Strategy; attempts?: number; checked?: number };   // proofs
}

type EventKind = "user" | "understood" | "statement" | "notes" | "proof" | "explanation" | "informal" | "info" | "error";
interface DossierEvent {
  kind: EventKind; text: string; t: number;
  ref: number | null;      // index of the version it produced (statements / proofs / explanations / statement_notes / informal_proofs by kind)
  stage: string;           // user events: "statement" | "proof" | "explanation" | "auto"
  model: string; key: string; params: Record<string, unknown>; job: string;
}

type DossierStatus = "draft" | "translating" | "proving" | "proved" | "failed" | "stopped";
interface Dossier {
  id: string; title: string; problem: string;
  understood: string;           // English statement given to the formalizer
  understood_display: string;   // the same in the interface language (shown)
  workspace: string; theorem: string; created: number; updated: number;
  events: DossierEvent[];
  statements: Version[]; proofs: Version[]; explanations: Version[];
  statement_notes: Version[];   // « learn » panel: line-by-line gloss of a statement (parent = statement index)
  informal_proofs: Version[];   // natural-language proof (parent = proof index)
  cur_statement: number; cur_proof: number; cur_explanation: number;
  lemmas_used: string[];
  project_id: string; status: DossierStatus; parent_id: string; retry_parent: boolean; archived: boolean;
  kind: "theorem" | "lemma" | "definition" | "claim";
  refs: { key: string; locator?: string; note?: string }[];
  source: { paper_key: string; locator: string; original_text: string } | null;
  uses: string[];
  current: { statement: string; proof: string; explanation: string; statement_notes: string; informal_proof: string;
             proof_is_current: boolean };   // computed
  [extra: string]: unknown;
}
interface DossierSummary {
  id: string; title: string; project_id: string; status: DossierStatus; parent_id: string; kind: string;
  theorem: string; workspace: string; created: number; updated: number; archived: boolean;
  has_statement: boolean; proved: boolean;
}

interface Attempt {
  index: number; stage: Stage; kind: "initial" | "correction" | "refinement" | "translation" | "agent" | "recheck";
  status: "generating" | "compiling" | "accepted" | "rejected" | "error" | "cancelled";
  summary: string; errors_text: string; code: string; raw?: string; model: string;
  gen_seconds: number; compile_seconds: number; tokens: number; finish: string; t: number;
}
interface Job {
  id: string; dossier_id: string; plan: { stage: Stage; request?: string }[];   // remaining steps
  mode: Mode; strategy: Strategy; user: boolean;
  state: "queued" | "running" | "done" | "failed" | "cancelled"; stage: Stage | ""; waiting: "" | "gpu" | "online" | "lean";
  created: number; started: number | null; ended: number | null;
  attempts: Attempt[]; done_stages: Stage[]; summary: Message | {}; error: string;   // error kind: no_model, workspace, no_proof, statement_rejected, unknown, cancelled, internal…
}

interface CheckResult {
  ok: boolean;               // strict verdict (proof mode) / file accepted
  statement_ok: boolean;     // no error (a statement with `sorry` is valid)
  summary: string; errors: { line: number; col: number; text: string; severity: string }[];
  axioms: string[] | null; has_sorry: boolean; reasons: string[]; seconds: number;
  timed_out: boolean; cancelled: boolean; infra_error: string;
}

interface LibEntry { name: string; title: string; statement: string; code: string; workspace: string;
                     dossier: string; deps: string[]; t: number }

interface ModelRef { key: string; provider: string; model_id: string; name: string; local: boolean; paid: boolean }

interface Settings {
  language: "fr" | "en"; mode: Mode; prove_strategy: Strategy; prefer: Record<string, string>;
  workspace: string; model_path: string; prove_attempts: number; translate_attempts: number;
  pause_after_translation: boolean; profile: string; statement_notes: boolean; informal_proof: boolean;
  compile_timeout_s: number; check_updates: boolean; overleaf_url: string; autoload_model: boolean;
  agent_max_steps: number; agent_max_seconds: number; host_name: string; wizard_done: boolean; offline: boolean;
  lan_listener: boolean; lan_port: number; remote_jupyter: boolean; agent_exec: boolean;   // host-only
  server: { port: number; ctx_size: number; gpu_layers: number; batch_size: number; ubatch_size: number;
            kv_type: "f16" | "q8_0" | "q4_0"; flash_attn: boolean; threads: number };
  sampling: { temperature: number; top_p: number; max_tokens: number };
}

interface Monitor {
  gpu: { name: string; total: number; used: number; free: number; temp: number; util: number;
         apps: Record<string, number> } | null;     // MiB, °C, %
  gpu_ok: boolean | null; gpu_error: string; disk: { path: string; total_gb: number; free_gb: number }[]; t: number;
}
type Slots = Record<"gpu" | "online" | "lean", { capacity: number; used: number; holders: string[]; waiting: number }>;
interface WorkspaceInfo { key: string; label: string; path: string; toolchain: string; readonly: boolean;
                          description: string; problems: string[]; ready: boolean }
interface HealthCheck { id: string; ok: boolean; level: "ok" | "warn"; repair: string; message: Message }

interface UpdatesStatus {
  checking: boolean; t: number | null; errors: string[];
  installed: { mathlib: string | null; models: Record<string, string> };
  candidates: { kind: string; key: string; title: string; current: string; latest: string; installable: boolean;
                note: string; size: number; spec: object; description: string }[];
  install: { key: string; title: string; step: string; step_text: string; progress: string } | null;
  last_result: (Message & { ok: boolean; details?: string }) | null;
}
interface JupyterStatus { state: "stopped" | "starting" | "ready" | "failed"; port: number | null; root_dir: string;
                          kernels: string[]; error: string; available: boolean; lean_kernel: { available: boolean; note: string } }
```

## 6. Plugins (for other sessions)

Every module in `madalean/server/plugins/` that defines `register(app: aiohttp.web.Application, ctx) -> None` is
called by `make_app` (also `make_app(ctx, extra_plugins=[fn])`). A plugin adds routes under `/api/…`
(`app.router.add_get(...)`) before the catch-alls; handlers get the context with
`request.app[madalean.server.common.CTX]`, see `request["local"]` / `request["device"]`, mark host-only handlers
with `@madalean.server.common.host_only`, answer with `common.ok(...)` / `common.error(...)`, publish events with
`ctx.publish("<type>", {...})`. Authentication, Origin checks and host-only enforcement apply automatically.
Update checks: `madalean.updates.register_checker(name, fn)` (`fn() -> list[Candidate]`; candidates without an
installer must be `installable=False`). Export: `export_dossier(..., bib_entries=[(key, csl)])` (or
`bib_keys=[...], bib_path=Path`) prints the cited references; citations `[@key, loc]` in texts. Research layer
(sources, literature search, grounded answers, blueprint, article, bibliography): see
[RESEARCH_SOURCES.md](RESEARCH_SOURCES.md) (`/api/research/…`).

## 7. Demo mode

`madalean serve --demo` (config `~/.config/madalean-demo` unless `--config-dir`): scripted fake brain (streams at
realistic speed, the right prompts per role, model keys `local:…gguf`), fake Lean (≈1.5 s per check; rejects
`sorry` and invented names), simulated model swaps (1.5 s), seeded project « Exemples (démo) » with one proven
dossier (statement, gloss, proof, explanation, informal proof) and one draft. The API is identical. A new dossier
with « Montrer que la somme de deux entiers pairs est paire. » runs the whole chain in ≈15 s.
Try: `madalean serve --demo --port 11600 --remote-port 11601`.
