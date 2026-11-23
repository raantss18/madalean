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

`POST /pair` (public) `{"code":"123456","device_name":"Pixel 8","client":"app-android"}` — two outcomes (user
decision 2026-11-21: apps reconnect automatically; a browser needs a code at every connection):
- **app** (`client` = `app-desktop` | `app-android`, sent by the shells' native HTTP clients, which add no `Origin` /
  `Sec-Fetch-*` header; a request without `client` and without those headers is also treated as an app, for shells
  of before this change) → `200 {"kind":"app","token":"<43 chars>","device":Device}`, **no cookie**. The token is
  long-lived (kept by the shell in the OS keystore); the web view gets its cookie through a session ticket (§3.1b).
- **browser** (any request carrying `Origin` or `Sec-Fetch-*`, whatever `client` it claims) →
  `200 {"kind":"browser","device":Device (kind "browser", id "b-…", expires_in),"idle_minutes":120}` +
  `Set-Cookie: madalean_token=<session secret>; HttpOnly; SameSite=Strict; Path=/` (+ `Secure` over HTTPS / with
  `X-Forwarded-Proto: https`; no `Max-Age`/`Expires`: a session cookie). **No token in the body.** The session lives in
  server memory only: closed after `browser_session_idle_minutes` without a request (setting, default 120, host-only),
  after 12 h at most, and when the server restarts → the browser pairs again with a new code. Its secret is accepted
  only as the cookie (never as `Authorization: Bearer`, never for `/session/ticket`): it cannot become a device token.
Errors: 403 `wrong`|`expired`|`no_code` (with `message`), 429 `locked` (`message.params.m` = minutes) | `rate_limited`.
The same rules apply on the remote and the LAN listeners; the local listener needs no pairing.

`POST /logout` (public; remote) → revokes the calling app device or browser session and clears the cookie →
`{"ok":true}`.

`POST /pairing/start` **host** → `{"code":"482913","expires":1795250000.0,"expires_in":300,
"remote_url":"https://nitro.tail1234.ts.net:10500"|null}` (replaces any previous code). `remote_url` = the address
other devices use: from the embedded Tailscale status (`madalean.runtime.net.remote_url`, when present), else
`https://<host_name>:10500` when the setting `host_name` is a `*.ts.net` name, else `null`. Also
`"addresses":{"host":"madalean.tail1234.ts.net"|null,"ip":"100.74.179.13"|null,"lan":["192.168.1.20:11502"]}`:
fallbacks put in the pairing QR code for the Android app (tailnet IPv4 of the embedded node; `lan` only while the
LAN listener is open, RFC 1918 address of the default route; docs/SHELLS.md). `GET /pairing` **host** → `{"active":true,"expires_in":212.4,"locked_for":0}`.

`GET /devices` **host** → `{"apps":[Device],"devices":[Device] (= apps, kept for compatibility),"browsers":[Device],
"browser_idle_minutes":120}` — apps (« Applications (connexion automatique) ») and browser sessions (« Navigateurs
(session temporaire) ») are listed separately. `DELETE /devices/{id}` **host** → `{"ok":true}` (404 unknown) for an
app (`d-…`) or a browser session (`b-…`). Both publish `devices.updated {devices, apps, browsers}`. Revoking a credential (host `DELETE`, `POST /logout`, `POST
/devices/self/forget`, or a browser session reaching its idle/absolute limit — swept every 5 s) closes every
WebSocket opened with it with close code **4401** and cancels the assistant answers it started.

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
`agent_max_seconds` 30–7200, `lan_port` 1024–65535, `tournament_contestants` 1–6, `tournament_max_rounds` 0–10,
`tournament_max_minutes` 1–240, `tournament_attempts_per_model` 1–16) → `400 {"error":"invalid_settings","details":["invalid:mode",…],
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
→ `202 {"job":Job}`. Stages: `understand route statement notes verify proof explanation informal`. A step object may
carry `"force":true` (`proof`: skip the statement-check gate — the « Prouver quand même » button) and `"learn":true`
(`verify`: explanations written for a student).

`POST /dossiers/{id}/verify` `{"learn"?:bool,"mode"?}` → `202 {"job":Job}` (409 `no_statement`, 409 `busy`) —
« Vérifier l'énoncé » (S-K, `madalean/pipeline/verify.py`). Runs in parallel, bounded (≈ 1–3 min): (a) the general
model (role `understand`) compares the user's words with the Lean statement and answers JSON issues
(`wrong_object | missing_hypothesis | extra_hypothesis | wrong_quantifier | wrong_direction | false_statement`, each
`severity` high/low, `explanation`, `fix`); (b) ONE Lean compilation of short proofs of the negation
`¬ (∀ BINDERS, CONCL)` (`decide`, `norm_num`, `simp`, `push_neg` + small witnesses, degenerate instances: ∅ for sets,
0/1 for numbers, constant functions) and of quick proofs of the statement (`simp`, `norm_num`, `omega`, `aesop`;
`exact?` in its own file); (c) the model's counterexamples as tactic proofs of that pinned negation. Every success is
re-compiled alone with the strict verdict. Result: event `check` (below) and `statements[i].meta.check` =
`{verdict, issues, fix, evidence:{kind,code,idea}, proof, proof_source, model, model_verdict, summary, seconds,
lean_seconds, probes, statement_index}`. `verdict`: `false` only when Lean proved the negation; `doubtful` when the
model reports a high-severity issue (or « false » without a Lean proof); `faithful`; `unknown` when nothing could be
checked. The same check runs automatically before the first proof search of each statement (`statement_check`);
`false`/`doubtful` stop the automatic chain (job `error` = `statement_false` / `statement_doubtful`) until the
statement changes, the user sends an explicit proof request, or a `proof` step with `force` is run.

`POST /dossiers/{id}/stop` → `{"stopped":true|false}` (cancels the active job: model request aborted, Lean killed;
event `Arrêté à votre demande.`; dossier status `stopped`, or `proved` if the current proof is still valid).

`POST /dossiers/{id}/versions/{kind}/{index}/restore` (`kind` = `statement|proof|explanation`) → `{"dossier":Dossier}`
(nothing is deleted; restoring a proof also restores its statement). 404 bad index, 409 busy.

`POST /dossiers/{id}/versions/{kind}` `{"code":"…","check":true}` — manual edit, `kind` = `proof | explanation |
informal | notes` → `{"dossier":Dossier,"check":CheckResult|null}`. Creates a new version with `source:"user"`
(`model:""`) and a thread event; nothing is overwritten, and AI stages only ever add new versions when asked.
A manual **proof** is pinned to the current statement (`assemble_proof`: the dossier's theorem signature is kept,
only the proof part of `code` is used) and re-checked by Lean with the strict verdict: `ok:true` only when Lean
accepts it (then status `proved` and the library is updated); otherwise the version is kept with `ok:false`, it is
current but **never counts as proven** (`proof_is_current` requires `ok`), event `error`. `check:false` → unverified
(`ok:false`). explanation / informal / notes: attached to the current proof / proof / statement. 400 `bad_kind`,
`empty`, `bad_proof`; 409 `busy`, `no_statement`.

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

`GET /jobs/{id}/stream?from=<offset>` (alias `since`) → replay of everything the job streamed (all stages, also the
single-call ones), for a page opened mid-job: `{"job_id","start","end","truncated","ended","segments":[{"offset",
"stage","attempt","kind","text"}]}`. Offsets count characters over the whole job; ask again with `from=end`, then
follow the live `job.token` events. Memory: 1 M characters per job (oldest dropped → `truncated`), 40 jobs, kept 10
minutes after the job ended (404 after that).

`GET /jobs` → `{"active":[Job],"recent":[Job]}` (in-memory, last 200). `GET /jobs/{id}` → `{"job":Job}` (with raw
answers). `POST /jobs/{id}/cancel` → `{"cancelled":bool}`.

Job states: `queued` (waiting for a slot: see `waiting` = `gpu|online|lean`) ⇄ `running` → `done | failed |
cancelled`. Slots: `gpu` 1 (the local llama-server, model swap per role, reentrant per job), `online` 3 (any model
call when mode ≠ local), `lean` 2 (compilations). A job holds a slot only during the step that needs it; waiters
are served user-started jobs first, then FIFO.

Parallel stages (D38, S-AF, setting `parallel_stages`): once Lean accepts the statement, the guided reading
(`notes`), the statement check (`verify`), the Mathlib-first search (`mathlib`) and the proof search (`proof`) run
together; explanation and informal proof are written together after the proof. Each stage owns the slots as
`<job id>#<stage>`; the job is `queued` only while all its running stages wait. A « faux » / « douteux » verdict of
the check cancels the proof work and stops the plan exactly as before (`error: statement_false|statement_doubtful`,
« Prouver quand même » = plan `[{"stage":"proof","force":true}]`); a proof found by Mathlib-first, by a quick proof
of the check or by the search cancels the other proof work (their running attempts end `cancelled`) and is recorded
once the check has not stopped it. A proof found before a « faux » / « douteux » verdict is kept on the dossier as
`pending_proof` (`{code, statement, statement_index, prepared, workspace, model, strategy, seconds, verdict, t,
job, mathlib?}`, S-AN / D46) — never recorded as verified, never in the library; the next `{"stage":"proof",
"force":true}` re-checks it with a FRESH strict Lean (attempt `kind: "pending"`) and records it at once when Lean
accepts it (`meta.pending_reused`, `meta.verdict_overridden`), else searches as before; a new statement (by hand,
by the model, by the conductor) drops it. `POST /jobs/{id}/cancel` stops every stage.

`GET /conductor/asks` → `{"asks":[ConductorAsk]}` and `POST /conductor/asks/{id} {approve: bool}` → `{answered}`
(400 when `approve` is not a boolean, 409 when nothing waits): the cap question « Plafond atteint : continuer avec
Claude (+0,50 $) ? » of a request outside a job (S-AN, D46) — a Calcul correction or an article compilation fix.
`ConductorAsk = {id, kind: "calcul"|"article", spent, cap, step, estimate, t, project_id?, doc?, cell_id?,
project?}`. No answer within 5 minutes = no (the request goes on without Claude). Never parallel in `local` mode (one
GPU model at a time). Same statement + same workspace / Lean / Mathlib: the check verdict and the Mathlib-first
result are reused (event « déjà vérifié … »; a reused Mathlib proof is checked again by Lean).

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

### 3.8a « Expliquer » for Lean (session S-AM, DECISIONS D45, plugin `lean_explain.py`)

`POST /lean/explain` (also `POST /code/explain` with `"language":"lean"`) `{"mode":"error|lines", "code"?,
"dossier"?, "part"?:"statement|proof", "note"?, "block"?, "workspace"?, "errors"?:[{line, col, text, severity}],
"error"?:"…", "stream"?:"<id>"}`. The place decides the workspace and the rules of a correction: `dossier` + `part`
(the dossier's workspace; `code` defaults to its statement / proof; a proof correction is pinned to the dossier's
statement and judged strictly — axiom probe, forbidden constructs), `note` + `block` (the project's workspace, the
block's code and the header it is checked with), else `workspace` / the default (a free file). Lean's messages:
`errors` as shown on screen (positions in `code`), or `error` (text), else the server compiles `code` itself (warm
Lean allowed, D37).
- `error` → `{"explanation","fix","fix_status":"accepted|rejected|none|unchecked","fix_check":{summary, via?,
  seconds?}|null,"fix_tries","no_error"?,"workspace","lean","model","cached"}`. `fix` is non-empty only when Lean
  accepted it (`accepted`); a refused correction goes back to the model once with Lean's errors, then is dropped
  (`rejected`, `fix:""`); `unchecked` = no Lean to check it (not offered). `no_error:true` = Lean accepts the code (no
  model call). Applying a fix is a manual edit: `POST /dossiers/{id}/statement` or `…/versions/proof` (fresh strict
  check decides « vérifiée »), or the note's own save.
- `lines` → `{"lines":[{"line","code","text","goal"}],"goals":"lean|none",…}`: one sentence per line (header lines
  `import` / `open` / `set_option` glossed without a model); `goal` = the goal state Lean printed after that line
  (`"no goals"` when that branch is done; `null` when Lean gave none — never invented).
- Errors: 400 `bad_fields` (`mode`, `part`, empty / too long code), 404 `not_found`, 409 `no_lean_block`, 503
  `no_model`. Answers are cached in memory (same code, place, Lean / Mathlib version, language; a refused or
  unchecked correction is not cached). WebSocket `lean.explain {stream, text, state: start|writing|checking|
  repairing|done|error}` while it runs (only when `stream` is given).

### 3.8b Declarations (hover / tap on Lean names) and examples

`GET /declarations/{workspace}/{name}` (also `GET /lean/declaration?name=&workspace=`, use this form for workspace
keys containing `/`) → `{"workspace","name","status":"ok|unknown|indexing|unavailable","declaration":{name, kind?,
signature, doc, module, …}|null}`. `GET /declarations/search?q=&workspace=&k=8` (also `/lean/search`) →
`{"workspace","status","results":[{name, signature, doc, module, score}]}`. Backed by the retriever (RAG index of the
workspace); `indexing` = the index is being built (ask again later). `workspace` defaults to the current one.

`GET /examples` → `{"examples":[{"key","statement","title","level","blurb","fr":{title,level,blurb},"en":{…}}]}`
(the built-in exercises of `madalean/examples.py`; top-level texts in the interface language).

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
`POST /models/keys` `{"provider":"anthropic","key":"sk-…","test"?:bool}` → `{"provider":"anthropic","set":true,"backend":"keyring"|"file","unpaused":n,"testing":bool}`.
S-AO (D47): saving a key lifts that provider's pauses, backoffs and failure counters (`unpaused` = models that were
paused); unless `test: false`, the quick key test of `POST /models/test` then runs on the server (event
`models.key_test {provider, ok, reason, …}`).
Keys are stored with `secret-tool` when available, else `keys.json` (0600); they are **never** returned, logged or
sent elsewhere. `DELETE /models/keys/{provider}` → `{"provider":…,"set":false,"existed":bool}`. Event
`models.status {keys}`.
`POST /models/test` `{"provider"}` → a real call: one tiny completion (« Reply with exactly: OK », 16 tokens) through
the brain, restricted to that provider's best model (role explain, online) →
`{"provider","ok":true,"model":"gemini:…","models":7,"latency_s":0.84,"reason":""}`. `ok:false` with `reason`
(`no_model` = no usable model of this provider (no key?), `timeout`, `fallback: …` = another model answered, or the
redacted error); `ok:null` with `reason:"local_mode"` when the mode is `local`. `models` = number of this provider's
models the router can use. The key is never echoed. Each `roles[role].candidates[i]` also has `why` (the router's reason for this position) and `score` (from
`brain.explain(role, mode)`; `""`/`null` when the engine gives none).
`POST /models/refresh` → `ModelsInfo` (rescan `~/models`, refresh the online catalogue).
`POST /models/local/stop` → unload the local model (409 `busy` while a job holds the GPU).
Choosing a model per role: `PATCH /settings {"prefer":{"prove":"anthropic:claude-…"}}`.
`GET /models/leaderboard[?task=prove|formalize|explain]` (any paired device, read-only) →
`{"entries":[LeaderboardRow],"tournament":{"tournament_enabled":true,"tournament_contestants":3,…}}`, where
`LeaderboardRow = {model, task, domain ("" = all domains, else number_theory | algebra | linear_algebra | analysis |
combinatorics | geometry | logic), tasks, solved, score (0–1), mean_attempts, mean_seconds, lean_errors, pauses,
last_success, updated}`, best first per (task, domain). `POST /models/leaderboard/reset` (**host only**) →
`{"entries":[]}`, event `models.status {leaderboard:"reset"}`. See docs/BRAIN.md §11.
`GET /models/rankings` (any paired device) → `{"domains":[{domain: lean|formalize|writing|code|reasoning, task,
public_slices, rows:[{key, name, provider, paid, local, score, evidence: measured|public|estimate, new, sources:[…]}]}],
"public":{source:"LMArena", dataset, url, license, verified, fetched, published, error, slices}, "catalogue_updated",
"next":{catalogue, public}, "auto", "news":[{t, kind: new|gone|provider_added, key?, name?, provider, models?}]}`.
`POST /models/rankings/refresh` → same body after refreshing the catalogue and (at most hourly) the public rankings;
nothing in local mode; event `models.rankings`. See docs/BRAIN.md §14. `GET /updates` now also has `tracked`
(`{components:[{id: lean|mathlib|sage|latex|tex-bundle, current, latest, pending, installable, key, policy}],
last_check, next_check, every_days}`).

Proof tournament settings (all in `Settings`, docs/BRAIN.md §11): `tournament_enabled` (true),
`tournament_contestants` (3), `tournament_max_rounds` (3), `tournament_max_minutes` (40),
`tournament_attempts_per_model` (4).

Mathlib first (S-K, `mathlib_first`, `madalean/pipeline/mathlib_first.py`): before the tournament / Goedel, the proof
stage takes ≤ 12 candidates from the RAG index (famous-results table, premises of the Lean statement, search with the
understood text), tries `exact N`, `exact N _`, `exact ⟨N _⟩`, `simpa using N`, `apply N` (+ `intros` first) then side goals by `assumption` / `norm_num` for all of
them in ONE compilation (+ `exact?` once, in parallel), then lets the general model (role `prove`, ≤ 2 calls) write a
1–5 line proof with the candidates; every proof is strict-checked. Success: proof version with `model`
`"mathlib:<name>"`, `meta.strategy` `"mathlib"`, `meta.mathlib_lemma`, info event « Ce théorème est dans Mathlib sous le
nom … », and the explanation cites the lemma. Failure: the candidates go to the agent provers as hints. The attempts
of this phase have `kind` `"mathlib"`. When the request names a known theorem, the translator also gets Mathlib's
statement as a reference (info event « Résultat connu de Mathlib donné au traducteur… »).

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

`POST /assistant` `{"request_id"?:"<8–64 chars [A-Za-z0-9_-]>","messages":[{"role":"user","content":"…"}],"context"?:{"lean"?,"notebook"?,"cell"?,"cell_type"?,
"cells"?:[…],"text"?,"dossier_id"?},"mode"?}` → `202 {"request_id":"a-…"}`. The answer streams on the WebSocket:
`assistant.token {request_id, kind, text}` … then `assistant.done {request_id, text, model, finish}` or
`assistant.error {request_id, error, text}`. `dossier_id` adds the dossier's current proof/statement as context. The `202` is written before the first event
can be published; a client may also choose `request_id` itself (409 `request_id_in_use`, 400 `bad_request_id`).
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
`Cache-Control: public, max-age=31536000, immutable`, others `no-cache`. HTML pages carry the headers
`Content-Security-Policy` (the policy of `web/index.html`'s meta plus `frame-ancestors 'self'`),
`X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`, `Permissions-Policy: camera=(), microphone=(),
geolocation=(), payment=(), usb=(), interest-cohort=()`. When `static/` has no `index.html`, a
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
| `job.updated` | `{job: Job}` — on submit, state/stage/stages/waiting changes, every attempt change, end |
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
| `conductor.ask` | `ConductorAsk` (§3.6) — a cap question outside a job; `{id, …, done: true}` once answered or expired |
| `article.fix` | `{project, state: "working"|"proposed"|"none", path?, line?, suggestion?, name?, usd?}` — the conductor's fix of a failed compilation (docs/ARTICLE.md §10) |

Plugins may publish other types (ignore unknown types).

## 5. Types

```ts
type Message = { key: string; params: Record<string, unknown>; text: string };
type Mode = "local" | "auto" | "online";
type Strategy = "goedel" | "agent" | "auto";
type Stage = "understand" | "route" | "statement" | "notes" | "verify" | "proof" | "mathlib" | "explanation" | "informal";   // "mathlib": job stage only (D38)

interface Device {
  id: string;              // "d-…" app device, "b-…" browser session
  name: string; created: number; last_seen: number; last_ip: string;
  kind: "app" | "browser"; client: string;   // app-desktop | app-android | "" (older apps) | browser
  sessions?: number;       // apps: web-view cookies issued through tickets
  expires_in?: number;     // browsers: seconds before the session closes (idle or absolute limit)
}

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
          strategy?: Strategy | "mathlib"; attempts?: number; checked?: number;   // proofs
          mathlib_lemma?: string; mathlib_source?: "template" | "exact?" | "adapted" | "check";   // proofs (S-K)
          check?: StatementCheck };                                                         // statements (S-K)
}

type EventKind = "user" | "understood" | "statement" | "notes" | "check" | "proof" | "explanation" | "informal" | "info" | "error";
// "check" (S-K): ref = statement index; params = {verdict, fix, issues, evidence, proved, seconds, detail, cached?}
//   cached: true = verdict reused for the same statement, words and Mathlib version (D38), preceded by an "info"
// Result events understood / statement / notes / proof / explanation / informal carry params.seconds = duration of
// their stage (D38, read by scripts/perf_report.py).
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
  round: number;            // proof tournament round: 0 = best models, 1… = races; -1 = not in a tournament
}
interface Job {
  id: string; dossier_id: string; plan: { stage: Stage; request?: string }[];   // remaining steps
  mode: Mode; strategy: Strategy; user: boolean;
  state: "queued" | "running" | "done" | "failed" | "cancelled"; stage: Stage | ""; waiting: "" | "gpu" | "online" | "lean";
  created: number; started: number | null; ended: number | null;
  attempts: Attempt[]; done_stages: Stage[]; summary: Message | {}; error: string;   // error kind: no_model, workspace, no_proof, statement_rejected, unknown, cancelled, internal…
  tournament: {} | { round: number; models: string[]; names: string[]; domain: string;
    state: "running" | "won" | "exhausted" | "rounds" | "time" | "attempts" | "tokens";
    winner?: string; tried?: string[]; rounds?: number; minutes?: number };   // proof tournament (BRAIN.md §11)
  // D38 (S-AF): stages run in parallel once Lean accepts the statement. `stage` stays the MAIN running stage
  // (order: route, understand, statement, proof, mathlib, verify, explanation, informal, notes) — older clients keep
  // working; `stages` lists every stage running now; `timings` one row per stage run (unix seconds).
  stages: Stage[];
  timings: { stage: Stage; start: number; end: number | null; seconds: number | null }[];
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

interface ModelRef { key: string; provider: string; model_id: string; name: string; local: boolean; paid: boolean;
                     why?: string; score?: number | null }   // why/score in GET /models roles
// every `model` field of the API is a key string "provider:model_id" (never an object)

interface Settings {
  language: "fr" | "en"; mode: Mode; prove_strategy: Strategy; prefer: Record<string, string>;
  workspace: string; model_path: string; prove_attempts: number; translate_attempts: number;
  pause_after_translation: boolean; profile: string; statement_notes: boolean; informal_proof: boolean;
  statement_check: boolean;  // (true) « Vérifier l'énoncé » before the first proof search of a statement (S-K)
  mathlib_first: boolean;    // (true) look for the theorem in Mathlib before the prover models; Mathlib reference for the translator
  parallel_stages: boolean;  // (true) D38: guided reading, statement check, Mathlib search and proof search together;
                             // false = one stage after the other (1.x order). Never parallel in « local » mode.
  compile_timeout_s: number; check_updates: boolean; overleaf_url: string; autoload_model: boolean;
  agent_max_steps: number; agent_max_seconds: number; host_name: string; wizard_done: boolean; offline: boolean;
  lan_listener: boolean; lan_port: number; remote_jupyter: boolean; agent_exec: boolean;   // host-only
  browser_session_idle_minutes: number;   // host-only, 5–1440 (default 120)
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

## 6b. Calcul, library catalogue, glossary, spending (session S-M, plugin `workbench.py`)

**S-P: Calcul notebooks** — documents `/api/calcul/{pid}/docs[/{doc}]` (cells code/ask/markdown/figure, sequential
`…/run {all|until|from|cells}`, `…/cells/{cid}/ask {prompt}`, `interrupt|restart|shutdown|clear`, `variables`,
`ipynb`, `…/cells/{cid}/to`; S-AO: `POST /api/calcul/{pid}/warm {doc?}` and `status.warm` — kernel ready in
advance, CALCUL.md §11): full list in the docstring of `madalean/server/plugins/workbench.py` and
[CALCUL.md](CALCUL.md). The S-M routes below act on the default document `calcul` (cells now also carry `type`,
`outputs`, `exec_count`, `stale`; a run also returns nbformat-shaped `outputs`).
**S-AB**: `…/docs/{doc}/detect {text}` → `{kind: code|ask}`; `…/cells/{cid}/explain {mode: error|lines}`;
`…/cells/{cid}/suggestion {code}`; generic `POST /api/code/explain {language: sage|python|lean, code, error?, mode}`
→ `{explanation, fix, fix_valid, model}` | `{lines: [{line, code, text}], model}` (`lean`: the shape of §3.8a); `GET /api/calcul/recipes`,
`DELETE /api/calcul/recipes/{id}`. `ask` answers `{cell, model, approval_required, timing, checked, recipe, uses}`,
409 `replaced` when a newer request for the same cell replaced it; runs answer 409 `calcul_busy` while cells run.
Event `calcul.draft {project_id, doc, cell_id, code, state: start|writing|done|error}`.
**S-AJ (D42)**: `…/cells/{cid}/explain {mode: "steps"}` — the mathematical steps of a cell whose current code ran
successfully (409 `no_result` otherwise) → `{text (Markdown, numbered steps, LaTeX in $…$), facts: [{key, text,
status: verified|computed|failed}], verified, reason: ""|no_probe|language|not_approved|host_only|stale|busy|
probe_failed|differs|no_kernel, op: factor|integrate|roots|det|solve|"", model, cached}`; 409 `replaced` when a newer
explanation of the same cell replaced it. Facts come from Madalean's fixed Sage probe run in the document's kernel
(only when the cell may run, [CALCUL.md §3.7](CALCUL.md)); streamed as `calcul.steps {project_id, doc, cell_id,
text, state: start|writing|done|error}`. Generic: `POST /api/code/explain {language: sage|python, code, output,
request?, mode: "steps"}` → the same shape, model only (`reason: no_kernel`, never runs code); 400 without `output`.
**S-AN (D46)**: a run whose `autofix` was written by the conductor carries `autofix: {…, by: "conductor", name,
tier, usd, what, seconds, request_usd, code_hash}` and the new version `versions[-1].fix: {by, name, usd, what}`;
the cap question of that request is `conductor.ask` (§3.6). Article: `POST …/texproject/compile` also answers
`fixing: bool` (a conductor's fix is being looked for, `article.fix` events; docs/ARTICLE.md §10); suggestions
have `meta` (`compile_fix`: `{conductor, tier, usd, verified: "recompiled", error, line}`).

| Method | Path | Body → answer |
|---|---|---|
| GET | `/api/calcul/{pid}` | → `{sheet: {cells, rev}, trash, status: {available{sage,python}, sandbox, auto, remote_allowed, local, running}}` |
| POST | `/api/calcul/{pid}/cells` | `{code, language: sage\|python, after?}` → 201 `{cell}` (origin `user`) |
| PATCH | `/api/calcul/{pid}/cells/{cid}` | `{code?, language?, note?}` → `{cell}`; an assistant cell keeps its origin and loses its approval |
| DELETE / POST | `…/cells/{cid}` · `…/cells/{cid}/restore` · `…/cells/{cid}/move {to}` | undo-able delete, reorder |
| POST | `…/cells/{cid}/approve` | `{code_hash}` (sha256 of the code read) → `{cell}`; 409 `stale_code`; 403 from devices unless `experiments_remote` |
| POST | `…/cells/{cid}/run` | `{timeout?≤600}` → `{run}`; 403 `not_approved` (assistant code not approved, `experiments_auto` off), 403 `experiments_host_only`, 409 `busy`; output streamed as `calcul.output` |
| POST | `/api/calcul/{pid}/interrupt` | interrupts the project's kernel |
| POST | `/api/calcul/{pid}/assist` | `{action: write\|fix\|explain, cell_id?, prompt?, language?}` → 201 `{cell, approval_required}` or `{text}`; 502 `no_code` |
| POST | `…/cells/{cid}/to` | `{target: conjecture\|note\|dossier\|article, text?, title?}` → 201 with the created object |
| GET | `/api/calcul/assets/{aid}` | plot (PNG, sanitised SVG), `Content-Security-Policy: default-src 'none'; …; sandbox` |
| GET | `/api/library/catalog` | → `{entries: [{name, title, statement, nl, code, workspace, dossier, t, project_id, project, domain, domain_auto, domain_manual, tags, status: verified\|conditional, admitted, model, by_user, axioms, uses, used_by}], domains}` |
| PATCH | `/api/library/meta/{name}` | `{domain?: one of domains or "" (automatic), tags?: [str ≤ 40]}` (stored in `<config>/library-meta.json`) |
| GET | `/api/library/catalog/export?format=md\|json\|lean&name=` | attachment (`lean`: the entry with its dependencies, `import Mathlib` first) |
| GET | `/api/glossary/uses?term=` | → `{term, dossiers: [{id, title, project_id, status, in: statement\|proof}]}` (≤ 30) |
| GET | `/api/models/spend` | → `{month, spent_month, cap_month, cap_proof, calls_month, by_model, recent[{ts, model, scope, tokens_in, tokens_out, cache_read, cache_write, usd}], prices, enabled, key_set, model, models}` |

`POST /api/models/test` now calls the provider's cheap, stable model (`brain.test_model`: Gemini Flash-Lite / Flash,
Mistral Small, Claude Haiku…) and answers `tested` (model key) and `why`. Settings added: `claude_reinforce` (bool,
true), `claude_model` ("auto" or a Claude key), `claude_cap_proof_usd` (0–100, 1.0), `claude_cap_month_usd` (0–1000,
20.0). WebSocket events: `calcul.updated {project_id, cell? | cell_id + run | removed}`, `calcul.output {project_id,
cell_id, kind, text}`, `calcul.running {project_id, cell_id}`.

S-T (Hugging Face, docs/BRAIN.md §13): `POST /api/models/test {"provider": "huggingface"}` is an identity check
(`GET huggingface.co/api/whoami-v2`, nothing billed) → `{ok, login, warning ("" | "inference_permission"), models,
model (live Goedel-Prover key or ""), names, reason ("" | key_refused | network | offline | no_live_model |
local_mode)}`. Setting added: `hf_goedel` (bool, true). `GET /api/models` → `status` adds `internet`, `local_policy`
(`fallback` | `now` | `only` | `never`), `goedel_online` ({key, name} | null) and `providers[].down`; `roles.prove`
lists the online Goedel first when it leads the proof. `GET /api/models/spend` adds `hf_estimate`.

## 6c. Providers hub and Internet search (session S-U, plugin `providers_hub.py`)

- `GET /api/providers` → `{checked, groups[{id, fr, en}], starter[ids], cards[…], ocr{fr,en}, web_search, mode}`;
  a card: `{id, group, name, key (KeyStore provider id or null), kind (llm|search|keyless|info|token), price
  (free|free_tier|credits|paid), integrated (yes|auto|no|retired), good_for/free_tier/privacy/details {fr,en}, key_url,
  sources[], checked, prefix, models[], key_set, disabled, state?{models, ok, paused_until, reason},
  usage?{units, searches, unit, free_month}}`. Keys never appear.
- `POST /api/search/web {query, k?, lang?, providers?}` → `{query, provider, results[{n, title, url, snippet,
  published, source}], tried[{provider, error}]}`; 409 `local_mode` | `disabled`, 503 `no_provider`, 400 `bad_query`.
- `POST /api/search/test {provider}` → `{provider, ok, reason, results?, latency_s?}` (one tiny real search).
- Keys: `POST /api/models/keys {provider: "tavily"|"exa"|"brave"|"sambanova"|"nvidia"|…}` as before. Settings:
  `providers_disabled: [ids]` (`"keyless"` = every keyless model provider, `"wikipedia"` = the keyless search
  fallback), `web_search: bool`. Details and verified facts: docs/PROVIDERS.md.

## 6d. Setup status and the first-run assistant (S-AL D44, S-AQ D49, plugin `setup_api.py`, all **host** only)

- `GET /api/setup[?refresh=1]` → `{schema: "madalean-setup-status/1", setup (setup.json | null), detected, prefs
  {sage_source, tex_engine, mode, wizard_done}, components [as GET /api/deps], reuse {sage, tex}, keys [ids],
  devices (n), next_steps [{id, done, title {fr,en}, help}], recommended, models, wizard}` (docs/INSTALL.md).
  S-AQ added: `recommended` = `assistant.recommend(detected)` (`{plan, items [{id, recommended, why, detected,
  title, options [{value, label, available}]}], advice [{id, text, command}], disk}`, in the settings' language;
  null without a machine check), `models` = `{dir, files [{key: Q4_K_M|formalizer|explainer, file, present, bytes,
  download_bytes}], download_bytes {all, prover, none}, choice, fetch}` and `wizard` (below).
- `GET /api/setup/wizard` → `{schema: "madalean-first-run/1", steps [welcome, tools, local, keys, hf, claude, modes,
  auto, pair, done], step, visited [steps], models ("" | all | prover | none), done, completed, reminder, auto}`.
  `done` = setting `wizard_done` (« Plus tard » or finished); `completed` = finished with « Terminer »; `auto` = the
  web app opens the assistant by itself on the host's Home: `!done && !completed`, and false when the server started
  with the user's dossiers already there and no `first-run.json` (an update from 2.0.0; never in the demo).
- `PATCH /api/setup/wizard {step?, visited?, models?, done?, completed?, reminder?}` → the same object, saved in
  `<config>/first-run.json` (`visited` merges, in step order); `done` writes `wizard_done`; `completed: true` also sets
  `wizard_done`. 400 `bad_fields` on an unknown key or value. Event `setup.wizard {wizard}`.
- `POST /api/setup/reuse {sage_source?, tex_engine?}` → `{prefs, reuse}` after a check against this machine;
  409 `{error: "unavailable", field, reason}`, reason ∈ `no_system_sage` (no `sagemath` kernel outside the prefix),
  `system_sage_too_old`, `no_system_tex` (no XeLaTeX / LuaLaTeX), `no_tectonic` (the prefix's tectonic + bundle
  missing), `invalid`; 400 `bad_fields`. Saved like `PATCH /api/settings` (`settings.updated`).
- `POST /api/setup/models {models: "prover" | "all"}` → `202 {started: true, models}` (downloads the missing files
  with `scripts/download_model.sh` into `MADALEAN_MODELS_DIR`/`~/models`: pinned revisions, SHA-256 checked,
  resumable), `200 {started: false}` when nothing is missing; 409 `busy` | `local_mode` | `demo`. Progress:
  events `setup.models {fetch: {running, phase: download|done|error, keys, index, done_gb, total_gb, message, ok}}`;
  the local models are rescanned at the end. `POST /api/setup/models/cancel` → `{cancelled}` (parts kept: resumes).

## 6e. « Actualités », the mathematical watch (session S-AV, plugin `news.py`, docs/NEWS.md)

Available to paired devices (the store holds public information; settings are not host-only).
- `GET /api/news` → `{items [NewsItem], total, unread}`. Query: `q` (full text, accents ignored, prefix on the last
  word), `branch` (repeatable: any of them), `source`, `group` (papers | problems | lean | ai | community | custom),
  `open=1`, `projects=1` or `projects=<project id>`, `unread=1`, `saved=1`, `mine=1` (the followed fields),
  `order=date|relevance`, `limit` (≤ 100, default 40), `offset`. Items of sources that are turned off are hidden
  unless saved. `unread` = unread items of the followed fields (the badge).
  `NewsItem` = `{id, key, source, group, kind (paper|problem|question|release|change|post), url, title, summary,
  authors [], published, fetched, open, branches [], cats [], extra {arxiv?, primary?, comment?, erdos?,
  state?, prize?, oeis?, repo?, tag?, score?, answers?, licence?, suspect?}, read, saved, fr, fr_model, fr_t, projects [{project,
  score, terms []}], relevance}` — `title` / `summary` are plain text (may hold TeX), `fr` the French summary.
- `GET /api/news/overview` → `{unread, unread_all, items, saved, for_projects, open, newest [≤ 3 NewsItem],
  last_refresh, next_refresh, mode, demo, enabled, badge, summaries, branches [], errors [source ids]}`.
- `GET /api/news/sources` → `{sources [{id, group, enabled, custom, items, unread, checked, ok, error, retry_at,
  fr, en, about_fr, about_en, home, host, licence, terms, summaries, url?}], verified, groups [{id, fr, en}],
  branches [{id, fr, en}]}`.
- `GET /api/news/settings` → `{settings}`; `PATCH /api/news/settings {enabled?, interval_hours? (1–48),
  branches? [branch ids], sources? {id: bool}, feeds? [{id?, url, title?, enabled?}] (≤ 20), summaries?, badge?,
  keep_days? (3–365), max_items? (200–20000)}` → `{settings}`; 400 `bad_value` | `bad_url` (`field`). Removing a feed
  forgets its unsaved items.
- `POST /api/news/refresh {source?}` → `{sources [{id, status: ok|unchanged|error, new?, updated?, seen?, error?,
  http?}], new, unread}` or `{skipped: disabled|busy}`; 409 `local_mode`. A manual refresh skips the intervals but
  not a source's backoff, and not a source checked less than 5 minutes ago. Demo: re-seeds from the recordings
  (`{demo: true}`), no network.
- `POST /api/news/feeds {url, title?}` → `201 {settings, feed, tested, entries}` after one test read (not in Local
  mode: `tested: false`, read later); 400 `bad_url`, 409 `duplicate`, 422 `not_a_feed`, 502 `unreachable`.
  `DELETE /api/news/feeds/{id}` → `{settings}`.
- `PATCH /api/news/items/{id} {read?, saved?}` → `{item, unread}`; `POST /api/news/read-all {…the list's filters}`
  → `{marked, unread}`.
- `POST /api/news/items/{id}/summary` → `{item}` with `fr` (cached); 409 `local_mode`, 422 `rights` (a © source:
  title, excerpt and link only) | `short` (abstract under 200 characters) | `suspect` (the text addresses a model:
  never sent to one), 503 `no_model` | `failed`.
- Event `news.updated {unread, new, summaries?}` after a refresh that brought something, new summaries or a
  settings change.

## 6f. Conjecture engine (session S-AW, DECISIONS D55, plugin `conjecture_engine.py`)

Reference: docs/CONJECTURES.md. The conjecture API of §RESEARCH_WORKSHOP (`/api/conjectures…`) is unchanged; a kept
candidate is created through it and carries `origin.engine = {exploration, candidate, norm, kind, question}`.
Running an experiment needs a device allowed to execute (the host, or `experiments_remote`), else 403
`experiments_host_only`; model code not approved for its current hash → 403 `not_approved` (approve with
`POST /api/calcul/{pid}/docs/{doc}/cells/{cid}/approve`, §6b).

| Method, path | Body → answer |
|---|---|
| `GET /api/explore/status?project=` | → `{available {sage, python}, auto, remote_allowed, local, demo, oeis: "on" \| "off", lmfdb: "not_queried", mode, examples [{fr, en}]}` |
| `GET /api/projects/{pid}/explorations` | → `{explorations: [brief]}` (newest first) |
| `POST /api/projects/{pid}/explorations` | `{question, language?: "sage" \| "python"}` → 201 `View`; 400 `empty`, 413 `too_many` |
| `GET /api/explorations/{xid}` | → `View` |
| `PATCH /api/explorations/{xid}` | `{code}` → `View`; 422 `bad_contract` (the three `cj_…` names are required), 409 `busy` |
| `DELETE /api/explorations/{xid}` | → `{deleted}`; 409 `busy` |
| `POST /api/explorations/{xid}/run` | → 202 `{started, …View}`: Explore → Recognise → State in the background; 409 `busy` |
| `POST /api/explorations/{xid}/stop` | → `View` (task cancelled, kernel interrupted) |
| `POST /api/explorations/{xid}/warm` | → `{warm}`: the kernel of the experiment's notebook prepared in advance (D47) |
| `POST /api/explorations/{xid}/candidates/{cid}/attack` | → 202: the counter-example hunt in the background |
| `POST /api/explorations/{xid}/candidates/{cid}/keep` | → 201 `{conjecture_id, duplicate: false, …View}`; 200 with `duplicate: true` when it already exists |
| `POST /api/explorations/{xid}/candidates/{cid}/prove` | `{mode?}` → 202 `{job, conjecture_id, …View}` (normal pipeline); 409 `refuted`, 409 `busy` + `job` |
| `POST /api/explorations/{xid}/candidates/{cid}/discard` | `{reason?}` → `View` |
| `POST /api/explorations/{xid}/export` | `{to: "note" \| "article"}` → `{note_id}` or `{article: true}` |

`View` = `{exploration, cell, running, exec_allowed}`. `cell` (null for given terms) = `{doc, id, code, code_hash,
origin: "user" | "assistant", model, approved, may_run, language}` — what the screen needs for the approval prompt;
the workbench checks the notebook itself at run time. `exploration` = `{id, project_id, question, language, origin:
"catalogue" | "model" | "user" | "data", intent {kind, key, recognised, summary, sequences […]}, code, model, steps
{explore | recognise | state | attack: {state, error, seconds, detail?, candidate?}}, table {columns, rows (first
200), total, labels?}, oeis {column: {status: ok | none | off | too_short | error | unrecorded, matches [{number,
name, offset, shift, matched, formulas, url, data}], rejected […], url, cached}}, findings […], candidates […],
journal [{t, step, kind, fr, en, data}], lmfdb: "not_queried"}`.

A candidate = `{id, kind, columns, text {fr, en}, lean (null when the formalizer must write it), lean_ok, lean_error,
strength {kind: tested | heuristic | oeis, from, to, cases, fr, en}, status: candidate | kept | survived | refuted |
disputed | discarded, conjecture_id, duplicate_of {id, title} | null, hunt {cases, to, max, sparse} | null,
counterexample {witness, detail, sage, lean, lean_check {ok, code, errors}, verified} | null, finding {kind, status,
columns, params, tested {from, to, cases, fit, held_out}, reason, detail, heuristic}, norm}`.

Events: `explore.updated` `{exploration, running}` at every step change; the experiment's cell publishes the usual
`calcul.running` / `calcul.output` / `calcul.updated`. Evidence kinds added to a conjecture's log: `exploration`,
`hunt` (and the existing `counterexample_check`).

## 6g. Certificats — Sage computes, Lean checks (S-AT D52, plugin `certificates.py`)

docs/CERTIFICATES.md. The two POSTs run Madalean's fixed producer in Calcul's sandboxed Sage kernel: allowed from the
host, or from a paired device when `experiments_remote` is on (else 403 `experiments_host_only`). Every proof returned
as `verified` passed a fresh strict Lean check in the request.

- `GET /api/certificates` → `{enabled (setting `certificates`), sage: bool, kinds: [{id, title {key, params, text},
  sage: bool, checker}]}`.
- `POST /api/certificates/check {statement, workspace?}` — `statement`: a full `theorem … := by sorry` (with or
  without header) or only `BINDERS : PROP` (`": ∃ x : ℕ, 17 * x % 3120 = 1"`). → `{status: verified | refuted |
  rejected | no_witness | unavailable | none, kind, title, code (the checked Lean file), witness [{key, params,
  text}], checker, axioms, reason, errors (Lean's messages when it refused the certificate), sage_seconds,
  lean_seconds, seconds, lines, tried [{kind, status, reason?}], kinds, workspace}`. Nothing is stored. 400
  `bad_statement`, 409 `workspace`.
- `POST /api/certificates/dossier {statement | project_id + doc + cell_id, title?, workspace?, dry?}` — « Certifier
  avec Lean ». With a cell: the statement is built from the cell's text and stored result (400
  `certificate_unsupported` when the cell has no supported shape, or is stale / failed). `dry: true` → `{statement,
  kinds, what}` without running anything. Otherwise the outcome as above plus `statement` and `dossier`: when Lean
  accepted (201), a new dossier (in the project) holding the statement, the certificate proof (model
  `certificat:<kind>`, meta `strategy: certificate, certificate, certificate_checker, certificate_witness`) and the
  events `statement`, `proof`, `certificate`; `dossier: null` otherwise (200).
- Dossier events: kind `certificate` (text = one line + the witness as a list; params `title, cert_kind, checker,
  detail`). Job attempts: `kind: "certificate"`, model `certificat:<kind>`. Setting: `certificates: bool`.

## 6h. MCP — Madalean as a server and as a client (S-AZ D58, plugin `mcp.py`, all **host** only)

docs/MCP.md. Every route answers 403 `host_only` on the remote / LAN listeners. Settings (host-only, default off):
`mcp_server` (both transports), `mcp_server_http`, `mcp_server_sage`.

- `GET /api/mcp` → `{server: {enabled, http, sage, protocol, tools: [{name, title, description, inputSchema,
  annotations, available, rate}], connect: {command, args, shell, claude_code, json, http_url, claude_code_http}},
  servers: [External], max_timeout}`.
- `POST /api/mcp/rpc` — one JSON-RPC message (`Content-Type: application/json`, ≤ 2 MB) from the stdio bridge
  `madalean mcp serve`. 403 `mcp_off` when `mcp_server` is off; 415 otherwise-typed bodies; 400 with a JSON-RPC
  error body for unparsable / invalid messages; 202 (empty) for notifications; else 200 with the JSON-RPC response.
- `POST /api/mcp/http` — MCP streamable HTTP (same answers; also needs `mcp_server_http`). `GET` / `DELETE` → 405
  (`Allow: POST`); unknown `MCP-Protocol-Version` → 400 `protocol_version`; `Accept` without JSON → 406.
- `GET /api/mcp/activity?dir=in|out` → `{activity: [{t, dir, transport, server, tool, ok, ms, in, out, args,
  error}]}` (newest first, 100 at most).
- `POST /api/mcp/servers {name?, transport: stdio | http, command | url}` → 201 `{server: External}` (disabled,
  `allowed: []`). 400 `bad_command | bad_url | local_mode | too_many | bad_transport`.
- `PATCH /api/mcp/servers/{id} {name?, enabled?, allowed?: [tool], timeout_s? (1–120)}` → `{server}`; `allowed`
  accepts only tested tools marked `safe` (400 `unknown_tools`). Disabling stops a running stdio server.
- `DELETE /api/mcp/servers/{id}` → `{removed}`; `POST /api/mcp/servers/{id}/test` → `{server}` (start, list tools,
  stop; `status: {ok, t, error, name, version, protocol, tools, stderr?}`).
- `External = {id, name, transport, command: [argv], url, enabled, allowed, tools: [{name, title, description,
  inputSchema (sanitised), safe}], timeout_s, status, created}`.
- WebSocket event `mcp.updated {server, removed?}`.

## 7. Demo mode

`madalean serve --demo` (config `~/.config/madalean-demo` unless `--config-dir`): scripted fake brain (streams at
realistic speed, the right prompts per role, model keys `local:…gguf`), fake Lean (≈1.5 s per check; rejects
`sorry` and invented names), simulated model swaps (1.5 s), seeded project « Exemples (démo) » with one proven
dossier (statement, gloss, proof, explanation, informal proof) and one draft. The API is identical. A new dossier
with « Montrer que la somme de deux entiers pairs est paire. » runs the whole chain in ≈15 s.
« Actualités » is seeded from the recorded answers of `madalean/news/demo_data/` (dates shifted to now, one user
feed « Flux de démonstration » with a hostile sample), without any request.
Try: `madalean serve --demo --port 11600 --remote-port 11601`.
Conjecture engine in the demo (§6e): recognised sequences are computed by the catalogue's reference implementation (no kernel), OEIS answers from one recorded look-up, an unrecognised question gets a scripted model answer and waits for approval.
