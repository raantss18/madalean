# STATE (memory across context resets / reboots)

## Snapshot
No root change was needed (D1) → no timeshift snapshot taken. Latest existing: 2026-10-03_13-48-44.

## Done (with evidence)
- 15:20 Phase 0 audit OK → AUDIT.md. root_steps.sh = documented no-op.
- 15:55 llama.cpp 436f6f8 built (CUDA sm_89, vendor/build.log "BUILD rc=0"). llama-bench qwen3-8B Q3_K_L:
  pp512 1844 t/s, tg128 36.85 t/s; "found 1 CUDA devices ... RTX 4060 Laptop GPU, VRAM 7888 MiB".
- 15:57 Direct `lean --json` (no lake) works; cold 28 s / warm 3.8 s on lean4web MathlibDemo.
- App written: app/lean_ai_station (config, gguf, leancheck, workspaces, services, errors, examples, ui/*).
- Tests: tests/test_leancheck.py + test_core.py (22, incl. byte-identical Goedel get_error_str),
  test_gui.py (7), test_integration.py (Lean 6/6 on MathlibDemo; server 4/4 with deepseek-r1 blob),
  test_process.py (double launch, kill -9 recovery: 2/2). Segfault on destroyed LeanCompiler fixed (bound slots).
- Cold start (offscreen, full window populated): ~0.55 s wall.
- Launcher bin/lean-ai-station + ~/.local/share/applications/lean-ai-station.desktop (validated) + icon.
- uninstall.sh, export_offline.sh written (syntax OK, not yet run).

- 17:00 Q4_K_M + Q5_K_M downloaded, sha256 OK; chat template identical to official (4168 chars). BENCH.md written; D7 defaults.
- 17:05 Real GUI run (scripts/screenshots.py, lean-current): wizard self-test 3/3, proof found in GUI, chat, crash → restart.
  Bug fixed: stale VRAM snapshot after crash made restart go CPU (0/36 layers) → free_excluding(own pid). Now 37/37, 4.0 s.
- 17:20 Idle: GUI 0.10 % CPU / 106 MiB, server 0.20 % CPU / 882 MiB RSS, VRAM 7047 MiB, GPU 1 %.
  kill -9 GUI → llama-server gone ≤300 ms, VRAM back to 484 MiB; relaunch OK; SIGTERM → clean (lock+pidfile removed).
- lean-current (Mathlib v4.34.1) built: "Build completed successfully (8925 jobs)".

- 17:25 Offline A-test OK in `unshare -rn` (lean-current): pairs + mathd_algebra_478 proved attempt 1 (28.5 s, 32.2 s),
  curl to huggingface fails inside ns. Fixed: GPU-snapshot race (D9), RAM prompt cache bounded (D8).
- uninstall.sh dry-run OK (pkill restricted to our binary).

## In progress (background, 17:26)
- Soak 30 min DONE: 47 cycles, 46 ok; VRAM flat 7049-7057 MiB; GUI RSS 108→132 MB (+24 MB, investigate: slow growth?); worst lag 447 ms (at model load), else 30-60 ms.
- lean-prover49 Mathlib build ~4157/4360 → logs/build_prover49.log.
- Model: scripts/download_model.sh Q4_K_M Q5_K_M (parallel, sha256) → logs/download.log.
- lean-prover49: Mathlib built from source (cache 404, D6) → logs/build_prover49.log.
- lean-current: v4.34.1 cache get → logs/setup_current.log.

## Status (2026-10-04): release 1.0.0
- Features: NL→Lean (Formalizer), prove (Prover), proof→French (Qwen3-8B), .tex in/out, loop guard, Chat tab removed,
  multi-distro installer (Fedora 44 / Ubuntu 24.04 / 22.04 container-tested, CPU backend).
- Release: tag v1.0.0 + GitHub release (see CHANGELOG.md). Local branch `dev-history` is NOT pushed (personal paths).
- Acceptance: ACCEPTANCE.md sections A–G.

## Gotchas
- NEVER `pkill -f`/`pgrep -f` with a pattern contained in the command itself (use "[x]yz" trick).
- The user's own GUI instance may hold the GPU (7 GB): ask before closing it; tests need the GPU free.
- New Lean prints "declaration uses `sorry`" with backticks; Lake 4.9 puts oleans in .lake/build/lib.
- llama-server needs `-lv 4` to log "offloaded N/M layers to GPU".
- Never connect a lambda that captures its own emitter (double delete).

## v1.1.0 TODO (user choices 2026-10-04: memory = profile + proof history + library; chaining = fully automatic;
## refinement = discussion thread per « dossier »; language switch = UI + model answers)
- [x] T1 leancheck: target the LAST theorem (library lemmas above it), per-dossier theorem names
- [x] T2 dossiers.py: Dossier (thread events, versions of statement/proof/explanation), atomic JSON store, list/rename/delete(undo)
- [x] T3 library.py: proven results saved automatically, relevance selection, insert as lemmas (same Lean version only)
- [x] T4 router.py: follow-up request → stage (statement / proof / explanation), FR+EN keywords, user override
- [x] T5 profile memory: settings.profile → translation (conventions) + explanation (audience); prover prompt untouched (D4)
- [x] T6 Pipeline service: translate → prove → explain automatically (model switch per stage), refinements with history
- [x] T7 UI: Lean tab = dossiers + thread + input + quick actions; artifacts tabs; versions « revenir à » ; Library tab
- [x] T8 i18n: `_()` on every visible string, EN catalogue, FR/EN switch (sidebar + Système), help/examples/README in EN
- [x] T9 tests: unit + fake-server pipeline + real-model e2e + i18n coverage + GUI; screenshots FR/EN
- [x] T11 updates: weekly check (Mathlib, Goedel models), notification, one-click install with verification, automatic deletion of obsolete versions (D21)
- [x] T12 (1.1.1) bug report video: « comprendre » step (D23), circular reasoning detector + exact detector false positive (D22)
- [x] T13 (1.1.2) bug report « même erreur » : correction chains ≤ 2, same-feedback restart, 8192-token floor, hints to the prover (D24)
- [x] T14 (1.1.3) real Mathlib names suggested for invented lemmas (D25)
- [x] T15 (1.1.4) follow-ups read by Qwen (D26), implication direction + French display, rejected names kept across samples
- [x] T10 docs (README FR/EN, CHANGELOG, DECISIONS, ACCEPTANCE), version 1.1.0, tag + GitHub release

### Resume point v1.1 (usage limit, 2026-10-04)
- Done & tested: T1–T6 (tests/test_dossiers.py, test_pipeline.py, test_prover_fake.py green), new Lean tab (dossiers +
  thread + quick actions + versions), Library tab, profile + language settings, help FR/EN, language switch rebuild,
  all UI strings wrapped in _(); job ids for Lean checks; stale-stream guards.
- NEXT: write app/lean_ai_station/i18n_en.py (628 keys: `.venv/bin/python scripts/dev/i18n_keys.py --dump`), add
  tests/test_i18n.py (all keys translated), fix test_gui language test, run full suite (LAS_TEST_WS=lean-prover49),
  real-model e2e of the chain, screenshots FR/EN, README.en.md, CHANGELOG 1.1.0, version bump, tag v1.1.0, release.
- NOT pushed to GitHub yet (local WIP commits on branch main).

- 2026-10-04: catalogue EN done (629 keys), full suite 109 passed on real models, screenshots FR/EN. Next: push + tag v1.1.0 + release.

## S-A — Madalean 2.0 server (session S-A, 2026-11-21)

### What exists
- `madalean/` package (Python ≥ 3.11, asyncio, aiohttp 3.x):
  - `server/` app (`app.py` listeners + `make_app` + plugin hook `register(app, ctx)` / `server/plugins/*.py`),
    `auth.py` (security middleware), `routes_core.py` (hello, pair, devices, state, settings, models, system,
    updates), `routes_work.py` (projects, dossiers, jobs, library, check, import, export, split), `routes_misc.py`
    (assistant, Jupyter endpoints + proxy, WebSocket, static UI with SPA fallback/placeholder), `bus.py` (seq + ring
    buffer 5 000 + resume/resync, tokens coalesced every 100 ms).
  - `context.py` (wiring, settings validation, host-only keys), `orchestrator.py` (jobs, parallel dossiers, cancel,
    history, sub-dossier parent retry), `slots.py` (gpu 1 / online 3 / lean 2, priority then FIFO, job id in a
    ContextVar), `jobs.py`, `repo.py`, `projects.py` (one directory per project), `paths.py`, `migrate.py` (1.x COPY),
    `security.py` (pairing, devices, rate limiter), `keys.py` (secret-tool else 0600 keys.json), `logs.py` (JSON logs
    `<config>/logs/server.log`, 2 MB × 5, secrets redacted), `prompts.py` (notes / informal proof / split / assistant),
    `demo.py`, `cli.py` (`serve [--demo]`, `pair`, `status`), `export.py` + `texio.py` (PDF/tex/lean/md/zip/html),
    `jupyter.py` (manager + reverse proxy).
  - `runtime/` `llama.py` (LocalRuntime: plan_launch verbatim, OOM fallback ×3, swap per role, orphan cleanup via our
    own pid file only, port ≥ 8765 skipping busy ones), `lean.py` (async `lean --json`, timeout, kill on cancel, lean
    slot), `monitor.py` (nvidia-smi + disk), `updates_mgr.py` (weekly check, install through scripts/updater.py).
  - `pipeline/` `goedel.py` (1.1.4 prove loop + formalizer, behaviour identical, tests ported), `runner.py`
    (stages understand/route/statement/notes/proof/explanation/informal, strategies goedel/agent/auto, agent code
    always re-checked), `io.py` (loop/rambling guard on streamed text → finish "loop").
  - `brain/fake.py` (FakeBrain, FakeRetriever, FakeLocal, FakeLean) — used by tests and `--demo` only; the real
    engine `madalean.brain.create_brain` (S-B) is used when importable (it is now), else the fake with `brain:"fake"`
    shown in /state and /system.
  - Core modules extended: `dossiers.py` (project_id, understood_display, statement_notes, informal_proofs, status,
    parent_id, retry_parent, kind/refs/source/uses, unknown fields round-tripped; 1.x files load unchanged),
    `config.py` (new settings), `updates.py` (data-driven `CHECKERS` + `register_checker`), `i18n.py` (`msg()`),
    `i18n_en.py` (+40 server strings).
- `docs/API.md`: full reference (endpoints, WS events, TypeScript types, plugins, demo).
- `bin/madalean`, `packaging/madalean.service` (systemd user unit); menu entry via the shells' `scripts/install_desktop_entry.sh`; `install.sh`
  (aiohttp, font/TeX report, unit install + start, `--no-service`, server probe), `uninstall.sh` (unit, keyring,
  ~/.config|cache/madalean*), `export_offline.sh` (madalean/ + aiohttp wheels + unit). `scripts/updater.py` now imports
  `madalean`. `scripts/dev/madalean_i18n_keys.py` (catalogue check).
- Tests: `./run_tests.sh` → 179 passed, 2 skipped (S-B online tests) in ~3 min, no GPU. S-A tests: 145 (api 8,
  auth 7, cli 2, core 8, dossiers 8, export 10, goedel 15, i18n 4, jupyter 3, leancheck 23, llama 5, names 3,
  orchestrator 7, pipeline 12, texio 13, updates 17). Old app tests moved to `tests/legacy/` (own conftest +
  pytest.ini): `./run_tests.sh --legacy` → 122 passed, 22 deselected (slow).

### How to run
- `bin/madalean serve` (or `systemctl --user start madalean` after install.sh) → http://127.0.0.1:11500/;
  remote listener 127.0.0.1:11501 for `tailscale serve`. `bin/madalean pair` prints a pairing code,
  `bin/madalean status` a summary. `--config-dir/--cache-dir` for isolated runs.
- `bin/madalean serve --demo --port 11600 --remote-port 11601` (data in ~/.config/madalean-demo): fake models + fake
  Lean, seeded project; a new dossier runs the whole chain in ≈ 15 s.

### Verified
- Real Lean (lean-prover49) in the prove loop, formalizer, pipeline, free check, dossier check; real XeLaTeX PDFs
  (Unicode Lean glyphs checked with pdftotext, pages looked at as PNG); real jupyter-lab behind the proxy (HTTP +
  kernel WebSocket executing `print(6*7)`); real child processes for a FAKE llama-server binary (swap, OOM fallback,
  orphan kill); `serve --demo` as a process (pair, status, single instance, SIGTERM, jupyter-lab dies after SIGKILL of
  the server); non-demo start with the real S-B brain (candidates per role, health checks all green) — no job run.
- Every route of the remote listener refuses requests without/with a bad token (enumerated from the router), pairing
  lockout, revoked token, WS auth + Origin, DNS-rebinding Host check, static/export/notebook path traversal.

### NOT verified (honestly)
- No real model was loaded (brief: GPU reserved for the integrator): LocalLlama never ran the real llama-server;
  the pipeline never ran with the real brain (local or online), so prompts reaching real models through S-B's
  engine, real streaming/loop detection timings and the agent strategy with a real model are untested end to end.
- `tailscale serve` in front of the remote listener not tested (Origin rule assumes the Host header is the ts.net
  name or `X-Forwarded-Host` is set; if tailscale rewrites Host to 127.0.0.1, set the UI origin in a future
  `allowed_origins` setting — the hook exists in auth.origin_ok).
- Updates install path only tested with a refused tag (no real Mathlib/model download). LAN listener not tested.
- secret-tool backend not exercised by tests (tests force keys.json); install.sh / uninstall.sh / export_offline.sh
  only syntax-checked, not run.
- LuaLaTeX fallback: luaotfload can't load OpenType fonts on this machine → XeLaTeX only; emoji/∎ glyphs dropped.

### Open questions
- Default `mode` is `local` (privacy first, 1.x was offline by default); 1.x users with offline=false migrate to
  `auto`. Confirm with the user.
- Jupyter kernels run in their own session: a SIGKILL of the server leaves kernels running (jupyter-lab itself dies).
- Lean 4 Jupyter kernel: not installed (lean4_jupyter 0.0.x / xeus-lean prototypes are not reliable); documented in
  `/api/jupyter` `lean_kernel.note`.
- Job attempts keep raw model answers (capped 200 k chars) in jobs/<dossier>.json history (last 50 jobs): watch size.

### S-A follow-up (shell endpoints, 2026-11-21)
- Added `POST /api/session/ticket` (Bearer only), `GET /api/session?ticket&next` (200 + meta refresh, HttpOnly
  SameSite=Strict cookie = a per-device session secret, hash stored in devices.json, revoked with the device;
  Secure when HTTPS / X-Forwarded-Proto=https; bad ticket → 303 /pair?reason=ticket), `POST /api/devices/self/forget`
  (204). Tests: tests/test_session.py (8). The access log is disabled (AppRunner access_log=None); no code logs this
  route's query string (tested).
- install.sh no longer installs its own madalean.desktop (removed packaging/madalean.desktop.in): it calls
  scripts/install_desktop_entry.sh when a desktop AppImage exists.
- shells/desktop/tests/e2e.sh was NOT run against the real server: it is hard-wired to shells/dev/mock_server.py
  (fixed ports 11630/11631, fixed code 123456 and the mock-only helpers /mock/new_code, /mock/revoke_all,
  /mock/events), so it cannot target `madalean serve --demo` without changes in shells/ (not S-A's directory).
