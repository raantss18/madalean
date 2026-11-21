# Madalean 2.0 — architecture (contract for all work sessions)

Madalean = Lean AI Station renamed and rebuilt (user request, 2026-11-21). One host computer does all the work
(Lean, local models, storage); every screen (this PC, other PCs, tablet, phone) is the **same web interface**
talking to the host. User-facing texts: French by default, English switch. Code, comments, commits: English.
Everything converges on Lean: nothing is shown as proven unless Lean accepted it (strict verdict of
`leancheck.judge`, unchanged).

## 1. Layout of the repository

| Path | Content | Owner session |
|---|---|---|
| `madalean/` | Python 3.11+ package, asyncio server (aiohttp). Core modules moved from `app/lean_ai_station/` (leancheck, dossiers, names, workspaces, gguf, texio, updates, config, i18n) | S-A |
| `madalean/brain/` | Model engine: catalogue + router ported from L Katta (`~/GitHub/L-Katta/src/moteur.rs`), providers, agent loop, RAG | S-B |
| `madalean/static/` | Built web UI (output of `web/`, committed so that installing needs no Node) | S-D |
| `web/` | Web UI sources (Vite + Svelte 5 + TypeScript, CodeMirror 6, KaTeX) | S-D |
| `shells/` | Thin clients: desktop AppImage and Android APK (connect to the host, pairing screen) | S-C |
| `site/` | GitHub Pages site (FR + EN) | S-F |
| `tests/` | pytest (server, brain), `web/` has its own tests | each session |
| `app/`, `bin/lean-ai-station` | Old PySide6 app: kept until 2.0 is validated, then removed by the integrator | integrator |

Config `~/.config/madalean/`, cache `~/.cache/madalean/`, models `~/models/` (unchanged). On first start the server
**copies** (never moves) settings, dossiers and library from `~/.config/lean-ai-station/`.

## 2. Processes and ports

`madalean serve` (systemd user unit `madalean.service`) runs one aiohttp application on two listeners:

- **local** `127.0.0.1:11500` — trusted (the host's own browser / desktop shell): no pairing needed.
- **remote** `127.0.0.1:11501` — every request needs a device token (see §4). Published on the tailnet only by
  `tailscale serve --bg --https=10500 http://127.0.0.1:11501` → `https://<host>.<tailnet>.ts.net:10500`.
  Never Funnel. Other `tailscale serve` entries of the machine (Sampana uses 10005–10447, 443, 80) must not be touched.
  Optional LAN listener (off by default) for networks without Tailscale.

Children managed by the server (all killed with it): `llama-server` (one local model in VRAM at a time, port 8765
range, existing flags), `lean` checks, `jupyter-lab` (§8).

## 3. Data model

- **Project** `{id, title, description, workspace, created, updated, archived}` — a body of work (a course chapter,
  a paper). Contains **dossiers**.
- **Dossier** (existing model, `dossiers.py`) = one theorem: thread of events, versions of statement / proof /
  explanation, plus new fields: `project_id`, `understood_display`, `statement_notes` (line-by-line gloss of the Lean
  statement for learners), `informal_proof` (natural-language proof used in the PDF), `status`
  (`draft|translating|proving|proved|failed|stopped`), `parent_id` (a lemma split from another dossier).
- **Library** (existing) — proven results, reused as lemmas.
- **Job** `{id, dossier_id, plan:[stage…], stage, state: queued|running|done|failed|cancelled, started, ended,
  attempts:[…], mode}` — one run of the pipeline on a dossier. History of jobs is kept per dossier.
- Storage: one JSON file per project / dossier (atomic writes, `.trash` undo) — as today. Single writer: the server.

## 4. Security

- Pairing: the host UI (local listener only) shows a 6-digit code (valid 5 min, single use, 5 wrong tries → 10 min
  lock). A new device posts it with its name and receives a 256-bit token; only its SHA-256 is stored
  (`devices.json`, 0600). Token sent as `Authorization: Bearer` (apps) or `HttpOnly; Secure; SameSite=Strict`
  cookie (browser). Devices can be listed and revoked from the host. WebSocket: same token.
- Remote listener: everything except `GET /api/hello` and `POST /api/pair` needs a valid token. CORS closed;
  `Origin` checked on state-changing requests and on WebSocket upgrade.
- API keys (Anthropic, Gemini, OpenRouter…): stored with `secret-tool` (system keyring) when available, else
  `keys.json` 0600. Never returned by the API (only `set: true/false`), never logged, never sent to another provider.
- Settings that open the machine (LAN listener, remote Jupyter, running code through the agent) are **host-only**
  (local listener). Jupyter can run arbitrary code: reachable remotely only from paired devices and only when the
  host enabled it.
- No telemetry. Network use is explicit: `mode` = `local` (nothing leaves the machine), `auto`, `online`.

## 5. HTTP + WebSocket API (JSON, prefix `/api`)

S-A writes the exact reference in `docs/API.md` (source of truth for S-D and S-C). Required surface:

- `GET /hello` → `{name:"madalean", version, paired:bool, local:bool, host_name}` (no auth)
- `POST /pair {code, device_name}` → `{token}` ; `POST /pairing/start` (host) → `{code, expires}` ;
  `GET /devices`, `DELETE /devices/{id}` (host)
- `GET /state` → everything a client needs at start (settings, projects, dossiers list, jobs, models, system)
- Projects: `GET/POST /projects`, `GET/PATCH/DELETE /projects/{id}`, `POST /projects/{id}/restore`
- Dossiers: `GET/POST /dossiers`, `GET/PATCH/DELETE /dossiers/{id}`, `POST /dossiers/{id}/restore`,
  `POST /dossiers/{id}/message {text, stage:"auto|statement|proof|explanation"}`,
  `POST /dossiers/{id}/statement {code}`, `POST /dossiers/{id}/check`, `POST /dossiers/{id}/run {plan}`,
  `POST /dossiers/{id}/stop`, `POST /dossiers/{id}/versions/{kind}/{index}/restore`,
  `GET /dossiers/{id}/export?format=pdf|tex|lean|md|zip`
- `POST /import/tex` (file) → candidate statements ; `POST /check {code, workspace}` (free Lean check)
- Library: `GET /library`, `DELETE /library/{name}`, `GET /library/export`
- Models: `GET /models` (local files, online catalogue, current choice per role), `POST /models/keys {provider,key}`,
  `DELETE /models/keys/{provider}`, `POST /models/test {provider}`, `PATCH /settings`
- System: `GET /system` (GPU, disk, health checks), `POST /system/repair/{id}`, updates (`/updates…`)
- Assistant (free chat with context, used by the notebook panel): `POST /assistant {messages, context}`
- `GET /ws` — WebSocket. Server → client events, each `{type, seq, ts, …}`:
  `job.updated`, `job.token {job_id, stage, attempt, text}`, `dossier.updated {dossier}`, `project.updated`,
  `library.updated`, `system.status`, `models.status`, `settings.updated`, `toast`. A client that reconnects sends
  `{type:"resume", seq}` and gets what it missed (ring buffer) or a `resync` order. All clients receive the same
  events: this is the synchronisation.
- Static UI at `/`, Jupyter proxy at `/jupyter/` (§8).
- `madalean serve --demo`: scripted fake brain + fake Lean so that the UI and the shells can be developed and tested
  without GPU, models or Lean.

## 6. Pipeline and orchestration

Stages (existing logic of `ui/pipeline.py`, moved to asyncio): `route` → `understand` → `statement` (+ Lean check,
+ `statement_notes` gloss) → `proof` → `explanation` (+ `informal_proof`). Follow-ups, versions, library, hints,
rejected-name memory, loop detectors: behaviour of 1.1.4 preserved (tests ported).
Before the first proof search of a statement: `verify` (« Vérifier l'énoncé »: fidelity by the general model + Lean
probes of the negation and of degenerate cases; « faux » only with a Lean proof of the negation) and, inside `proof`,
« Mathlib first » (known results tried with one-line tactics before any prover model). docs/BRAIN.md §12 (S-K).

**Orchestrator**: jobs of different dossiers run in parallel, limited by resource slots:
`gpu` = 1 (local llama-server, with model swap), `online` = 3, `lean` = 2 (compilations). A job only waits for the
slots its current stage needs; queue order is FIFO per resource, user-started jobs first. A dossier has at most one
active job. Sub-dossiers (`parent_id`): « split into lemmas » creates child dossiers that run in parallel; when
proven they enter the library and the parent is retried with them.

## 7. Brain (model engine) — interface in `madalean/brain/api.py`

- Catalogue + classifier + router + quotas ported from L Katta (seed catalogue, keyless free providers, pause on
  429/quota, observed reliability), plus keyed providers: Anthropic (native Messages API, tool use, streaming),
  Google Gemini (OpenAI-compatible endpoint), OpenRouter, Ollama, and the local llama-server (Goedel-Prover,
  Goedel-Formalizer, Qwen3).
- Per role (`understand`, `route`, `formalize`, `prove`, `explain`, `assistant`) the router picks the best available
  model for the mode; **offline fallback is automatic** (network down, quota, error → local models). The answer says
  which model produced it (shown in the UI).
- Proving strategies: `goedel` (1.1.4 loop, local, verbatim Goedel prompts) and `agent` (tool-using model:
  `lean_check`, `search_mathlib`, `read_declaration`, `library_search`, optional `lean_search_online`), bounded by
  steps/tokens/time; `auto` = agent with the strongest online model when allowed, else goedel. The final proof is
  always re-checked by the server with the strict verdict.
- Adaptive model selection (D30, docs/BRAIN.md §11): a leaderboard of what each model really solved here (per task
  and domain, Bayesian prior, decay) adds a bonus in the router; the proof stage is a bounded tournament — best model
  first (4 attempts), then up to 3 parallel races of untried models (the local Goedel prover is one contestant),
  first Lean-verified proof wins, ≤ 40 min / 16 attempts, paid models only when allowed.
- RAG: SQLite FTS5 index of the workspace's declarations (name, signature, docstring, module) built from sources
  (extends `names.py`), optional embeddings (Ollama) for semantic search; premises retrieved for the statement are
  given to every prover (as hints for Goedel, as a tool for agents).

## 8. Jupyter / Sage

The server starts `jupyter-lab` on demand (`--ServerApp.base_url=/jupyter/`, random token kept server-side, working
directory `~/Documents/Madalean/notebooks`, kernels: python3, sagemath, and a Lean 4 kernel if one can be installed
reliably), proxies HTTP + WebSocket under `/jupyter/` behind Madalean's own authentication, and the UI shows it next
to the same assistant panel (reads the open notebook through the Jupyter contents API, can append a cell).

## 9. Export (reliable, very readable)

`texio.py` → XeLaTeX/LuaLaTeX through `latexmk` in a temp dir, fonts with full Unicode maths coverage embedded
(check at start: DejaVu Sans Mono + Noto Sans Math present on the host; installer adds what is missing), Lean code
in a framed, line-numbered, wrapped listing, document = statement (natural language) → Lean statement with gloss →
proof in natural language → Lean proof → verification stamp (Lean version, Mathlib revision, date, axioms).
If no TeX engine is installed: self-contained HTML (KaTeX inlined) and the UI prints it to PDF.

## 10. Quality bar

- Each session ships tests that run without GPU (`./run_tests.sh`), and keeps existing tests green or ports them.
- Design: load the `frontend-design:frontend-design` skill, accessibility AA, usable on a 360 px phone, keyboard
  first on desktop, light and dark themes, no layout shift while streaming.
- Claude API code: load the `claude-api` skill first (model ids, tool use, streaming, caching).
- Never claim something works without having run it; record what was not verified in `ACCEPTANCE.md`.
- Sessions do **not** commit, push, tag, or touch `~/.config/lean-ai-station`, Sampana, L Katta or the user's running
  services; the integrator commits. GPU / real local models are reserved for the integrator's final tests.

## 11. Research layer: bibliography, articles ⇄ Lean (added 2026-11-21, session S-E)

Feasibility, stated honestly (DECISIONS D27 records the analysis):

| Feature | Reliability | How |
|---|---|---|
| Bibliography in proofs and exports | High | One BibTeX file per project (`refs.bib`). Add by DOI / arXiv id / title (Crossref, arXiv, zbMATH Open — online, queries only), by pasting BibTeX, or from Mathlib's own `docs/references.bib`. Dossiers carry `refs:[{key, locator, note}]`; statements and proofs cite with `[@key, Thm 2.1]`; exports use biblatex+biber (fallback bibtex). A model may only cite keys that exist in the project: invented references are rejected by code, never printed. |
| Lean → article | High for structure, model-dependent for prose | Project → LaTeX article (amsart): abstract, sections, each dossier as theorem + natural-language proof, optional Lean appendix, bibliography, and a verification table (which statements Lean checked, with which Lean/Mathlib). Unproven statements are typeset as conjectures/claims and marked — never as theorems. |
| Article → structured statements | High from LaTeX sources (arXiv e-print: theorem environments, labels, \cite), medium from PDF | arXiv source first; PDF via text layer (`pdftotext -layout`) + a vision-capable model for formulas when a key allows (Claude reads PDFs natively); formulas from scanned PDFs are not trusted without review. Result: a **blueprint** = one dossier per definition/lemma/theorem with the original text, its location in the paper, its dependencies (uses), linked to the bib entry of the paper. |
| Article → Lean statements | Medium (textbook/graduate level), low (research level with objects absent from Mathlib) | Each blueprint node goes through understand → formalize with retrieval; missing definitions are detected (unknown names) and become their own nodes « to define ». Always human-reviewed: the UI shows the paper's text next to the Lean statement. |
| Article → Lean proofs | Low to medium | The paper's proof is given to the prover as a hint (agent mode); elementary lemmas are often proved, deep results usually are not. The blueprint graph shows honestly what is proved, stated only, or blocked — like Lean blueprint projects. No result is ever presented as verified unless Lean accepted its proof and all its dependencies. |

UI: a « Bibliothèque d'articles » reader (PDF/TeX beside extracted statements), the blueprint graph per project
(status colours, click = dossier), « Rédiger l'article » export.

## 12. Systematic update checks (extends `updates.py`)

Checked weekly (and on demand), notification first, install only on click, verify-then-switch-then-delete as today:
Lean toolchains (elan), Mathlib and **every package of each managed workspace's `lake-manifest.json`** (batteries,
aesop, …, and libraries the user adds to a workspace), Goedel models (existing), llama.cpp (pinned; notify only),
Madalean itself (GitHub release, signed checksums), the online catalogue. **SageMath and its components, JupyterLab,
kernels, TeX**: system packages → detected version vs upstream latest, *notification with the exact command only*
(Madalean never runs pacman/apt/sudo). Each check lists what changed (release notes link) and what would be rebuilt.

**Tracked components (S-V, 2026-11-22).** Réglages → Mises à jour → « Composants suivis » shows Lean, Mathlib, SageMath,
LaTeX (tectonic) and the TeX bundle: installed vs newest known, last / next check (weekly, `updates.CHECK_EVERY_S`),
and how each updates (`madalean/update_checkers/overview.py`, `updates.status.tracked`):
- Mathlib (+ its Lean): installable and automatic (`updates_auto`) — copy → build → verify → switch → old Mathlib
  removed, old toolchain uninstalled only when no project uses it (scripts/updater.py `toolchain_users`);
- Lean alone: notify only (comes with Mathlib);
- Sage env, tectonic (main env) and the TeX bundle: pinned in `deps/manifest.toml`; a newer pin (signed Madalean
  release) is now installed automatically too (`AUTO_KINDS` += `deps`): SHA-256 → new versioned dir → check → switch
  → previous kept for rollback, older pruned. Upstream news (conda-forge `sage`, `tectonic`; tectonic bundle probed on
  the relay, `deps/checker.bundle_latest`, ≤ 3 HEAD requests) is notify-only until a release pins it.
- D29 still applies to every automatic install (installed prefix, default config dir, prefix elan; otherwise notify).

## 13. Learning and understanding (applies to S-D)

Madalean is both a research tool and a place to learn Lean and the mathematics. Design with the installed skills
`education-agent-skills:*` (worked-example fading, progressive hint ladder, self-explanation prompts, retrieve-first,
productive failure, erroneous examples, metacognitive checks) and `frontend-design`, `design:*`, `a11y-enforcer`:
- « Apprendre » mode on every Lean statement/proof: gloss line by line, hover any Lean token for its meaning and
  Mathlib doc, « why this tactic », hint ladder before showing a proof (nudge → strategy → key lemma → next step →
  full proof), « explain it back » check, and exercises generated from a proven dossier (faded proof to complete,
  checked by Lean).
- « Recherche » mode: dense, keyboard-first, nothing pedagogical in the way.
- Interface inspired by the user's own best projects (Sampana: one door, live status, calm dashboard; L Katta:
  threads « côtés et fils », gentle guidance, everything reversible; Lean AI Station 1.1: dossier thread, versions).

## 14. Research workspace (user decisions of 2026-11-21: everything ships in 2.0)

Goal: deep, modern mathematical research, quasi-local and autonomous — the useful ideas of NotebookLM (answers
grounded in *your* sources, with citations), Zotero (reference library), Obsidian (linked notes, graph), plus Lean.

- **Sources library (built in; import/export BibTeX, CSL-JSON, Zotero RDF/BibTeX exports; no Zotero dependency)**:
  articles, books, lecture notes added manually (PDF, TeX, arXiv id, DOI, URL) or found by **literature search**
  (arXiv, zbMATH Open, Crossref, OpenAlex, Semantic Scholar: metadata + open-access full text only; queries only are
  sent). Metadata, tags, collections per project, reading status, highlights and margin notes anchored to page/quad.
  Full text indexed locally (FTS5 + optional embeddings) per source, chunked with page/section anchors.
- **Grounded answers**: every answer about sources cites chunk anchors (click → opens the page at the passage); an
  answer with no supporting passage says so. Summaries, « what does this paper prove », comparison of sources,
  extraction of definitions/theorems into blueprint nodes (§11).
- **Notes (internal to Madalean — not an Obsidian vault)**: Markdown + LaTeX + Lean blocks, `[[links]]` to notes,
  dossiers, sources and passages, backlinks, graph; stored by the server (versioned, undo), exportable.
- **Conjecture workshop**: from a project's context (notes, sources, proven results) propose conjectures; test them
  before believing them: numeric/symbolic experiments in Sage (through the Jupyter kernel), counter-example search,
  Lean `decide`/`norm_num`/`slim_check`-style checks on small cases; each conjecture is a dossier of kind
  `conjecture` with its evidence log; promote to theorem only through a Lean proof.
- **Guided proof design** (the main way to prove hard theorems, S-L, D31): analysis → lemmas + combination gated by
  Lean → the user validates the plan → lemmas proved automatically (sub-dossiers, parallel) → combination with the
  real proofs (strict verdict); failure → other track / deeper split / hole (conditional); bounded depth, nodes, time;
  shown as a mind map. Earlier wording: the agent proposes, the user edits any
  section by hand (statement, Lean code, natural-language proof, explanation, notes, bibliography, article sections)
  — every AI output is an editable, versioned draft; manual edits are never overwritten without asking.
- **Privacy default (user choice)**: online by default, best available model everywhere, including keyless free
  providers. A permanent indicator shows which model receives what; any project can be switched to « local only ».

## 15. Ease of use, security and robustness bar (user requirement, 2026-11-21)

- **As easy as L Katta**: study `~/GitHub/L-Katta` (settings, model choice, how a key is added and tested, first-run
  guidance, plain-language errors with one action button) and match or beat it. Adding a key = paste → automatic
  test call → « ça marche » with the model list, or a clear reason; link to where the key is obtained; remove in one
  click. Nothing requires a terminal. Every setting has a sensible default; every destructive action can be undone.
- **Security review before release (session S-H, independent of the authors)**: threat model for the sync surface
  (tailnet device compromised, malicious web page in the host's browser — CSRF/DNS-rebinding against 127.0.0.1:11500,
  hostile PDF/TeX/BibTeX/notebook input, prompt injection from sources and web results reaching tools, path
  traversal, SSRF through DOI/arXiv/URL fetchers, LaTeX `\write18`/`\input` abuse → compile with `-no-shell-escape`
  and `openin_any=p`, Jupyter proxy escape, WebSocket hijacking, token theft via the shells). Host header allow-list
  on both listeners, strict CSP on the UI (no inline script, no remote origins), rendered Markdown/LaTeX sanitised,
  model output never executed without the documented tool boundary, tools that write or run code confined to the
  project directory.
- **Dependencies and CVEs**: pinned versions with hashes (Python, npm, Rust, Flutter/Gradle), audit in CI and at
  release (`pip-audit`, `npm audit`, `cargo audit`, `osv-scanner`, Flutter/Gradle dependency check), minimal
  dependency count, SBOM published with the release, signed release artefacts, GitHub Dependabot + secret scanning
  enabled. No known high/critical CVE at release; anything accepted is listed with its reason.
- **Fluidity and reliability**: UI interactive < 1.5 s on the phone, streaming never blocks input, 60 fps scrolling
  with 10 000-line outputs (virtualised), reconnect without losing state, server survives kill -9 of any child,
  crash-safe storage (atomic writes, tested by fault injection), soak test (2 h of parallel jobs, flat memory),
  load test (5 devices connected), every long operation cancellable.

## 16. Internal, automatic updates (user requirement, 2026-11-21 — like L Katta's `src/maj.rs`)

Everything updates from inside Madalean, automatically when it is safe, with no terminal:
- **Madalean itself (server + web UI)**: GitHub releases of raantss18/madalean; `SHA256SUMS` signed with an Ed25519
  key kept outside git (`~/.config/madalean/release-keys/`), public key embedded in the code — a release without a
  valid signature is refused even if the GitHub account is compromised. Download + verify in the background, install
  into a new versioned directory, health-check it, switch, keep the previous version for one-click rollback; applied
  automatically at a quiet moment (no running job) unless the user turned « automatic » off. Clients reload the UI
  after the switch (version in `/api/hello`).
- **Desktop AppImage**: Tauri updater (signed with the same key scheme) — downloads and replaces itself, then
  restarts. **Android APK**: in-app download + signature/certificate check; Android always requires one tap from the
  user to install a sideloaded APK (system rule, cannot be bypassed) — the app prompts at a good moment.
- **Lean, Mathlib, Lean packages, Goedel models, catalogue**: automatic by default — install next to the old
  version, verify (test theorem + re-check of proven dossiers), switch, delete the obsolete version; failure ⇒ nothing
  changes and the user is told. lean-prover49 stays pinned (training environment). The settings keep a
  « demander avant d'installer » switch.
- **System components (SageMath, JupyterLab, TeX, poppler)**: Madalean never runs pacman/apt/sudo. It detects the
  available version, notifies, and offers « Installer » which opens a terminal with the exact command (the password is
  typed by the user), like L Katta's Konsole tool. Where a user-level install exists (pip --user kernels, elan) it is
  handled automatically.

## 17. GitHub Pages: three useful roles, no showcase (user decision, 2026-11-21)

The site plays no part in synchronisation (that is host ⇄ devices over Tailscale only). It serves:
1. **Publication of verified work**: « Publier » in a project builds a static site (article HTML+PDF, blueprint
   dependency graph with status, each statement with its Lean code and natural-language proof, verification table,
   bibliography, downloadable Lake project) and pushes it to a GitHub repository chosen by the user (gh CLI / token in
   the keyring), with a GitHub Action that re-runs `lake build` so readers see an independent verification badge.
   Preview locally before pushing; nothing private is published without an explicit per-item choice; the publish step
   lists exactly what leaves the machine.
2. **Signed update channel**: `raantss18.github.io/madalean/updates/stable.json` (versions, files, SHA-256, notes),
   signed with the release Ed25519 key; read by the server self-update, the AppImage updater and the APK; release files
   themselves stay on GitHub Releases. Install page with APK/AppImage links and a QR code for phones.
3. **Reference manual**: one Markdown source (`docs/manual/`, FR + EN) rendered both as the in-app help and as the
   site — guides, Lean glossary, tutorials, pairing and security guide. Built by a GitHub Action from the repo.

## 18. Self-contained installation (user requirement, 2026-11-21) — supersedes system-tool assumptions

Madalean installs and manages **all** its dependencies in one prefix, `MADALEAN_HOME` = `~/.local/share/madalean`
(config stays in `~/.config/madalean`, models may stay in `~/models` if they already exist — referenced, never moved).
No system package is required except the NVIDIA driver (and CUDA toolkit only if building the GPU engine), a C
toolchain is NOT required at runtime. One systemd user unit (`madalean.service`); every child process dies with it;
`madalean uninstall` removes the prefix, the unit, the desktop entry and nothing else; nothing is left running.

| Component | How it is provided inside the prefix |
|---|---|
| Python + Madalean's Python deps | micromamba (single static binary, pinned + SHA-256) creating `env/` from a **conda-lock** file (exact versions + hashes, conda-forge only) |
| JupyterLab, kernels, poppler (pdftotext/pdfinfo), LaTeX engine | same locked env (LaTeX: **tectonic** with a vendored, pinned bundle cache — offline after first install; fallback xelatex only if present on the system) |
| SageMath | separate locked env `envs/sage/`, installed **on demand** the first time a Sage feature is used, then updated by Madalean |
| Lean / Mathlib | elan with `ELAN_HOME=$MADALEAN_HOME/elan` (never touches `~/.elan`), workspaces under `$MADALEAN_HOME/workspaces` (existing ones reused read-only if present) |
| llama.cpp | prebuilt pinned release asset (CUDA or CPU) verified by SHA-256, or built from the pinned commit if no matching binary |
| Network to devices | **embedded Tailscale node** (tsnet, Go sidecar `madalean-net`, pinned, built by us, single static binary): the server is reachable at `https://madalean.<tailnet>.ts.net` with its own certificate; state in `$MADALEAN_HOME/tailscale/`; first start shows the Tailscale login URL; no `tailscale serve` entries on the host; the host's tailscaled is not required (if it runs, both coexist). Remote listener is bound to the tsnet listener only. |
| Web UI | built static files shipped in the package (no Node at runtime) |

All component versions live in one manifest (`madalean/deps/manifest.toml`) with hashes; the update system (§16)
updates them; the health page lists every component, its version, where it lives, and a repair button.
