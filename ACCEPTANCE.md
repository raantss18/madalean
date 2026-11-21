# ACCEPTANCE — evidence for each item

Machine: RTX 4060 Laptop 8 GB (60 W), Ryzen 7 7735HS, EndeavourOS, kernel 7.2.7. Test log of the full run:
`logs/full_tests_prover49.log` (not versioned; reproduce with `LAS_TEST_WS=lean-prover49 ./run_tests.sh --all`).
Result of the last full run: **52 passed** + usability tasks 2/3 re-run after a test fix (**2 passed**) → 54/54.
After the memory fixes: fast suite 37/37 green, final 30-min soak flat (below).

## A. Functional
| Item | Evidence | Status |
|---|---|---|
| 5 tabs work (+ home, wizard) | `test_gui.py::test_all_pages_render`; 19 real-state screenshots `docs/screenshots/` | ✅ |
| Full prove cycle without network (`unshare -rn`), easy theorem | `bench/offline_unshare_lean-current.jsonl`: `pairs` proved, attempt 1, 28.5 s; `curl huggingface.co` fails inside the namespace | ✅ |
| … miniF2F statement | same file: `mathd_algebra_478` proved, attempt 1, 32.2 s | ✅ |
| Full prove cycle on lean-prover49 (Goedel's Lean 4.9 + Mathlib) | `test_integration.py::test_full_prove_cycle[easy]`, `[mathd_algebra_478]` with `LAS_TEST_WS=lean-prover49` (strict, no fallback) | ✅ |
| Wrong proof rejected | `test_wrong_proof_rejected`, `test_prover_fake.py::test_statement_cannot_be_weakened` | ✅ |
| `sorry` proof rejected (both Lean message styles) | `test_sorry_proof_rejected`, `test_judge_rejects_sorry_both_lean_versions`, `test_sorry_answer_rejected` | ✅ |
| Non-standard axioms rejected | `test_native_decide_axiom_rejected` (`Lean.ofReduceBool`) | ✅ |
| Goedel prompt/feedback format exact | `test_initial_prompt_matches_goedel_readme`, `test_correction_prompt_matches_goedel`, `test_error_string_identical_to_goedel` (byte-identical to Goedel's `get_error_str`) | ✅ |

## B. Robustness (fault injection)
| Item | Evidence | Status |
|---|---|---|
| kill llama-server mid-generation → clear message + restart, no hang | `test_kill_server_midgeneration_reports_error`; screenshots 18→19 (banner « Redémarrer le modèle », back to 37/37 layers in 4.0 s); usability task 4: 1 click | ✅ |
| kill `lean` mid-compile | `test_kill_lean_midcompile` | ✅ |
| compile timeout fires | `test_compile_timeout_fires` (5 s limit, returns < 20 s) | ✅ |
| no orphan processes after quit / kill -9 | `test_kill9_gui_kills_llama_server` (server gone after GUI SIGKILL, `setpriv --pdeathsig`); manual: gone ≤ 300 ms, VRAM back to 484 MiB; SIGTERM quit removes lock + pid file | ✅ |
| model missing / corrupt | `test_missing_and_corrupt_model`, `test_gguf_corrupt_and_truncated` | ✅ |
| GGUF too large for VRAM | `test_plan_launch_fallbacks` (ctx shrink, then partial offload, then CPU); real: Q5_K_M auto-loaded with ctx 12288, 37/37 layers (usability task 2) | ✅ |
| CUDA out-of-memory (real) | forced ctx 40960 f16 → real CUDA OOM → automatic retries 20480 → 10240 → ready in 5.6 s, 37/37 layers, plain-French notices (`bench/oom_fallback.txt`) | ✅ |
| disk nearly full warning | `test_disk_nearly_full_warns` | ✅ |
| GPU unavailable → CPU fallback message | `test_gpu_unavailable_falls_back_to_cpu` | ✅ (simulated) |
| double click / double launch | `test_double_click_prove_starts_once`, `test_double_launch_forwards_and_exits` | ✅ |
| power loss (kill -9 GUI) → clean recovery | `test_kill9_gui_recovers_cleanly` (atomic JSON, stale lock detected, « Session restaurée ») | ✅ |
| 30-minute soak | `bench/soak.json`: 55 prove cycles, **55/55 proved**, VRAM 7049–7053 MiB, GUI RSS 113.4 → 114.0 MB over the last 27 min (flat), QObject count constant (750), event-loop lag ≈ 20 ms (302 ms once, during model load) | ✅ |

## C. Efficiency (details in BENCH.md)
| Metric | Value |
|---|---|
| GUI cold start (window populated, workspaces + models detected) | 0.53–0.58 s wall |
| Model load (server ready, Q4_K_M, 37/37 layers) | 3.3–4.2 s (8.3 s with cold page cache under heavy CPU load) |
| First-token latency | 0.10–0.15 s |
| Generation speed | 41.5 tok/s (API), 44.8 tok/s llama-bench @0, 33.4 @8k, 26.6 @16k |
| GPU utilisation during generation | 92–97 % at the 60 W power cap |
| VRAM idle / under load | 7047 MiB (model + 24k KV pre-allocated; flat during soak) |
| RAM idle | GUI 106 MiB, server 882 MiB RSS |
| Idle CPU | GUI 0.10 %, server 0.20 % |
| Lean check (lean-prover49) | 9.6 s first (cold), 2.2 s warm; never runs `lake` → no rebuilds |
| GUI thread never blocked | all I/O via QProcess/QNetworkAccessManager/thread pool; soak event-loop lag ≈ 20 ms during proving |
| Best alternative compared | BENCH.md §1–3 (FA on/off, KV f16/q8/q4, ubatch, Q4 vs Q5, ctx sizes) |

## D. Intuitiveness
| Task (fresh profile, after the wizard, no terminal) | Clicks | Evidence |
|---|---|---|
| 1. first launch → first verified proof | **1** (« ▶ Prouver » on an example) | `test_usability.py::test_task1` |
| 2. load a different model | **3** (Modèles → row → Charger; or 2 with a double-click) | `test_task2` |
| 3. verify my own `.lean` file | **1** (drag the file on the window; or Ouvrir… → file, auto-verify) | `test_task3` |
| 4. recover from a stopped server | **1** (« Redémarrer le modèle » in the banner) | `test_task4` |

Screenshots of every screen/state were reviewed; fixes applied: truncated buttons/labels, wizard width, hidden spinbox
arrows, disabled-button contrast, dark blocks inside cards, horizontal scrolling, jargon (tooltips for tokens, KV,
batch, top-p…), mismatched « Réparer »/« Recompiler » wording. All visible strings reviewed (French).

## E. Delivery
| Item | Evidence | Status |
|---|---|---|
| README (French, screenshots) | `README.md` | ✅ |
| uninstall.sh lists exactly what was installed | dry run output (asks before deleting; keeps shared elan toolchains and `~/.cache/mathlib` unless `--toolchains`) | ✅ |
| export_offline.sh | real run `--no-models`: app 48 MB + elan 855 MB + workspaces 3.3 GB = **4.2 GB** (+ ~5 GB per GGUF), `zstd -t` OK on all archives; `import_offline.sh` restored into a fresh HOME, app started in 0.47 s (bug found and fixed: relative destination path) | ✅ |
| one-command test suite | `./run_tests.sh` (fast) / `./run_tests.sh --all` | ✅ |
| git repository, clean history, Apache-2.0 | `LICENSE`, `NOTICE` | ✅ |
| reproducible install | `install.sh` (pinned llama.cpp commit, pinned model revision + sha256, pinned Mathlib commits) | ✅ |

## F. Natural language → Lean, LaTeX, loop guard (added 2026-10-04)
| Item | Evidence | Status |
|---|---|---|
| Plain-language problem → Lean statement checked by Lean (real models, 3 problems incl. French + LaTeX + English) | `bench/translate_real.jsonl`: 3/3 compile at try 1, 9.5–21 s | ✅ |
| Two models on one 8 GB GPU: translate → switch → prove, real | `test_integration.py::test_translate_then_prove_with_model_switch` | ✅ |
| Formalizer prompt is the model-card prompt; retries on invalid Lean / loops; keeps last statement when giving up | `test_leancheck.py::test_formalize_prompt_is_the_model_card_prompt`, `test_prover_fake.py::test_formalizer_*` (real Lean 4.9) | ✅ |
| Mandatory human review step in the UI | `docs/screenshots/08_enonce_a_relire.png`; `test_gui.py::test_translate_needs_text_and_model` | ✅ |
| Loop guard (chat screenshot reported by the user) | `test_tex_and_loop.py::test_chat_stream_stops_a_loop` (stops after <1500 of 5000 chunks), `test_prover_restarts_after_a_loop`, `test_loop_detector` (no false positive on 60 × `· norm_num`) | ✅ |
| .tex import (theorems/lemmas/exercises, comments ignored, choice dialog) | `test_extract_statements_from_tex`, `test_import_tex_fills_problem_box` | ✅ |
| LaTeX export compiles (XeLaTeX), cannot be broken by proof content | `test_exported_tex_compiles_with_xelatex`, `test_export_escapes_plain_text_and_keeps_latex`; real export `docs/exemple_export.pdf` | ✅ |
| Beginner help (Lean in 2 minutes, glossary, why review) | `docs/screenshots/06b_aide.png`, `test_help_dialog_opens` | ✅ |
| Overleaf | exported file / copied code / configurable URL. **Not automated**: the local instance answers 404 on 127.0.0.1:80 and an API import would need the user's login | ⚠️ by design |
| Faithfulness of a *compiling* translation | cannot be measured automatically → forced human review | ⚠️ limit |

## G. Explanation, Chat removal, portability (added 2026-10-04, release 1.0.0)
| Item | Evidence | Status |
|---|---|---|
| Proof → French explanation, real model | `test_integration.py::test_explain_in_french_with_real_model`; `docs/screenshots/10b_explication_en_francais.png`; 10.6 s / 19.0 s (BENCH §8) | ✅ |
| Prover model rejected for explanation (English, re-writes Lean) | measured comparison in DECISIONS D15 | ✅ |
| Explanation text → safe LaTeX (bold, lists, code, `%`, `_`, `&`, `#`) and included in the export | `test_markdown_and_math_for_display_and_latex`, `test_export_with_explanation_compiles` (XeLaTeX) | ✅ |
| Chat tab removed | `test_chat_tab_is_gone` | ✅ |
| Fresh `git clone` + `./install.sh --install-deps --backend cpu --no-models …` → app starts → fast tests | Fedora 44: 54 passed; Ubuntu 24.04: 54 passed; Ubuntu 22.04 (Python 3.10): 54 passed (9 skipped = need a Lean workspace/models) | ✅ |
| Real defects found by those runs | missing `libGL` (Fedora/openSUSE), missing `libglib` (Ubuntu minimal), test depending on installed models | fixed |
| CUDA build on non-Arch distributions | **not verified** (no NVIDIA GPU in the containers). Fallbacks for newer-GCC are coded (g++-14…11, `-allow-unsupported-compiler`) but untested | ⚠️ |
| Debian, openSUSE, AMD/Intel GPUs | package lists written from distribution naming, **not tested**; AMD/Intel run on the CPU | ⚠️ |
| CPU-only speed | 5.1 tok/s generation vs 44 on GPU (BENCH §7) | ✅ measured |

## H. Release 1.1.0 — dossiers, automatic chain, memory, library, English
Full suite on the real models and Lean 4.9 workspace: **109 passed** (`logs/full_tests_v11.log`, `LAS_TEST_WS=lean-prover49`).
| Item | Evidence | Status |
|---|---|---|
| Fully automatic chain translate → prove → explain, model switched per stage (real models) | `test_usability.py::test_task1` events `[user, statement, proof, info, explanation]`, 1 click; screenshots 07–08 | ✅ |
| Follow-up request in the thread (real models) | `test_task5_follow_up_request`: 2 clicks, second verified proof | ✅ |
| Follow-ups routed to the right stage, with history (prover sees the verified proof, formalizer the previous statement, explainer its previous answer) | `test_pipeline.py` (7 tests, fake model server + real Lean 4.9), `test_dossiers.py::test_router` | ✅ |
| Versions + « Revenir à cette version », delete with undo | `test_thread_shows_versions_and_restore_link`, `test_delete_dossier_is_undoable`, `test_cancel_and_restore` | ✅ |
| Memory: profile in translator/explainer prompts, not in the prover | `leancheck.formalize_input` / `explain_messages`; `test_pipeline` asserts prompts | ✅ |
| Library: auto-store, dedupe, same-Lean-version only, relevance, dependencies first, reused in the next dossier | `test_dossiers.py` (library tests), `test_library_result_is_offered_in_the_next_dossier`, `test_library_page_lists_and_removes` | ✅ |
| Target = last theorem; Goedel prompt unchanged for a single theorem | `test_target_is_the_last_declaration`, `test_single_theorem_prompt_unchanged_by_rsplit` | ✅ |
| English UI: every visible string translated, same placeholders, live switch without restarting the model | `test_i18n.py` (629 keys), `test_language_switch_rebuilds_ui_in_english`; screenshots 18–20 | ✅ |
| Explanations in the chosen language | `test_explanation_follow_up_and_language` (English prompt sent) | ✅ |
| Chat tab removed | `test_chat_tab_is_gone` | ✅ |
| Real defects found while building 1.1 | Lean check restarted right after « Stop » crashed or reused a stale result (job ids); stale stream signals after cancel; `_` shadowing the translation function | fixed |
| Updates: version logic (stable tags only, 8B only, GGUF pending, re-published file) | `test_updates.py` (recorded data) | ✅ |
| Updates: install → verify → switch → delete obsolete; failure keeps the old version; toolchain still used by a project kept | `test_updates.py` (stubbed network) + real run of `install_mathlib` (Mathlib v4.34.1 rebuilt in a test directory: 8 min, test theorem OK, switch and cleanup OK) + scan of the real home (finds the 5 user projects and their toolchains) + real run of `install_model` (5.03 GB downloaded from Hugging Face, SHA-256 OK, loaded and answered on the CPU, switched, an older dummy V1 file deleted) | ✅ |
| Updates: weekly check, notification once per new version, card in Système | `test_card_lists_updates_and_reports_install`; real check against GitHub/Hugging Face (nothing newer today) | ✅ |
| 1.1.1: named theorem understood before translation (user's exact request) | `test_task6_named_theorem_is_understood_before_translation` (real models); `test_pipeline.py` (understand → formalize, UNKNOWN stops the chain); Qwen3 rewrites measured on 6 requests (DECISIONS D23) | see below |
| 1.1.1: circular reasoning stopped, correct answers never stopped | 19 real Goedel-Prover answers (server settings of the app), each compiled with Lean 4.9: no naturally finished answer is stopped by either detector, including one that circles for a while and one with repeated tactic blocks, both accepted by Lean; runaways stopped (`test_rambling_*`, `test_exact_loop_detector_spares_*`, streaming test) | ✅ |
| 1.1.2: prove loop never stuck on one line of attack, never starved of tokens; follow-ups after a failure reach the prover with the user's hint | `test_same_error_twice_restarts_from_a_fresh_sample`, `test_at_most_two_corrections_per_line_of_attack`, `test_correction_never_starved_of_tokens`, `test_follow_up_after_a_failed_search_reaches_the_prover`, router tests. Live run of the new loop on the user's dossier (8 attempts, real model): chains of 1–3 attempts then fresh samples, every request ≥ 8 192 tokens, two runaways stopped at 7 200 and 9 400 tokens. Not proven: the model keeps citing lemmas absent from Mathlib 4.9 (no « odd degree real polynomial has a root » lemma exists there) | ✅ loop / ⚠️ model limit |
| 1.1.3: real names suggested for invented lemmas | `test_names.py` (parser, suggestions, Lean 4.9 « invalid field notation » wording, real index of lean-prover49: 164 474 names, end-to-end correction prompt with the real compiler). Live run on the user's cubic polynomial (8 attempts): the note reached the model on 6 refused attempts; one later attempt dropped the invented lemma for a direct proof (refused for `linarith`), still no proof: no such lemma exists in Mathlib 4.9 | ✅ feature / ⚠️ model limit |
| 1.1.4: implication direction, follow-ups read by the general model, rejected names never come back | `test_task7_direction_and_converse` (real models): « Montre qu'un carré pair est issu d'un entier pair » → `Even (n^2) → Even n` proved, then « et la réciproque » → new statement `Even n → Even (n^2)` proved; `test_converse_request_changes_the_theorem`, `test_unusable_routing_answer_falls_back_to_keywords`, `test_invented_names_are_recalled_in_fresh_samples`, `test_reusing_a_rejected_name_starts_a_fresh_sample`. Live run on the cubic (8 attempts): each invented name appeared once (was 6 times in 1.1.3), later attempts tried real proofs; still not proved | ✅ / ⚠️ model limit |
| Router is keyword-based | ambiguous requests may pick the wrong stage → the stage selector next to « Envoyer » lets the user choose | ⚠️ limit |
| English quality of model answers | the explainer's English was not reviewed by a native speaker | ⚠️ not verified |

## Defects found by this acceptance loop and fixed (see DECISIONS D8–D11)
1. Restart after a server crash loaded the model on the CPU (stale VRAM snapshot) → free VRAM computed excluding our own process.
2. Race: model load before the first `nvidia-smi` reading → CPU → load now waits for a GPU snapshot.
3. llama-server host prompt cache up to 8 GiB → bounded to 1 GiB.
4. Lean 4.9 workspace reported "not built" (old Lake layout) and tests silently fell back to another workspace → both layouts + strict tests.
5. Segfault from a lambda capturing its emitting QProcess → bound slots.
6. GUI memory growth (+20 MB / 30 min): one ChatStream leaked per attempt and the hidden server-log widget kept ~6.6 KB per line → streams freed, log buffered as text and rendered only when visible. Re-soak: flat.

## Not verified / known limits
- GPU-unavailable path is tested by simulation only (the real GPU was not removed).
- Olympiad-level miniF2F problems often fail with the 8B model (3/8 failures in BENCH §4); long answers (up to ~16k tokens) can take ~8 min per attempt.
- Quality of Q4_K_M vs Q5_K_M was not compared statistically (choice made on speed + VRAM headroom).

## 2.0 — research layer: sources, bibliography, grounded answers, blueprint, article (session S-E, 2026-11-21)
Verified: live calls to arXiv, doi.org/Crossref, OpenAlex, OpenLibrary, zbMATH Open, Semantic Scholar (recorded as
fixtures); SSRF refusals against real DNS (localtest.me → ::1, 10.0.0.1.nip.io); real XeLaTeX PDFs with biblatex+biber,
bibtex+amsalpha and thebibliography (formatted reference checked in the PDF text); article PDF with verification
table, « not verified » claims and Lean appendix (looked at as PNG); blueprint extraction hand-checked on 3 arXiv
papers (docs/RESEARCH_SOURCES.md §10); `serve --demo` seeds and serves the research project.
Not verified (needs a key or the GPU): grounded answers, reading lists, metadata proposals, blueprint model pass and
article drafts with a REAL model (only the fake brain ran); semantic re-ranking with a local Ollama embedding model;
OCR quality on a real scanned paper; EPUB extraction on a real book.

## 2.0 — self-contained install, embedded Tailscale node (session S-I, 2026-11-21)
Verified (temp prefix + temp config + temp unit `madalean-sitest`, details and numbers in docs/INSTALL.md §9):
install.sh --cpu end to end in 359 s (re-run 16 s, offline from an export in `unshare -rn` 26 s); the unit runs the
server from the prefix; /api/hello, /api/system all green; PDF export through the prefix's tectonic (also with no
network); Python kernel through the prefix's JupyterLab; Sage 10.10 installed on demand through the API and
`factor(2^64+1)` = 274177 * 67280421310721; kill -9 of the server → no child survives (systemd cgroup, and by hand:
jupyter-lab + kernel in its own session); real madalean-net reaches `needs_login` with a login URL (not authorised);
uninstall.sh leaves nothing but the kept config. pip-audit main env: 0 vulns; govulncheck: 0 affecting; SBOM
dist/sbom/madalean-prefix.cdx.json.
Not verified: real tailnet login / HTTPS with the Tailscale certificate / proxy over the tailnet; CUDA builds of
llama.cpp and any real model load (GPU reserved); other distributions; `--build-workspace`; madalean-net built on
another Go version. Accepted: pillow 12.3.0 in the Sage env (sage 10.10 pins pillow <13); x/crypto GO-2026-5932
(not called).

## 2.0 — real local-model run (integrator, 2026-11-21)
Real server (`bin/madalean serve`, test config dir), RTX 4060, local mode, strategy goedel, lean-prover49:
| Request | Result | Time |
|---|---|---|
| « Montrer que si n² est pair alors n est pair, pour tout entier n. » | understood in the right direction → `∀ n : ℤ, Even (n^2) → Even n` → proved on attempt 1 → notes, explanation, informal proof; PDF export readable | 8 min 36 |
| follow-up « et la réciproque » (auto routing by Qwen3) | new statement `∀ n : ℤ, Even n → Even (n^2)` → proved on attempt 2 | 21 min 31 (in parallel with the next) |
| « 6 divise n(n+1)(n+2) » (started at the same time) | proved on attempt 1 | 18 min 41 |
Two jobs shared the single GPU slot with model swaps; no error or warning in the server log. PDF defects seen: Mathlib
revision shown as « — » for lean-prover49, the informal proof repeats « Théorème. … », annex numbering restarts.

## 2.0 — independent security & robustness review (session S-H, 2026-11-21) — details in docs/SECURITY.md
| Item | Evidence | Status |
|---|---|---|
| Remote listener as unpaired client | every route enumerated from the router (core + plugins + static + `/jupyter`) → 401/200-static (`test_auth`, `test_sources_security`); host-only routes and host-only settings → 403 with a valid device token (`test_paired_device_reaches_no_host_only_route`); forged `X-Forwarded-*` grant nothing | ✅ |
| Local listener vs malicious web page (CSRF / rebinding / CORS) | every state-changing route × 6 foreign origins (other loopback ports included) × 3 content types → 403; Fetch Metadata blocks cross-site sub-resources and navigations to the API / Jupyter; WebSocket from another port refused; no CORS / PNA headers (`test_security_review.py`) | ✅ fixed (F2) |
| Lean code execution (D28) | bypass found (`attribute [command_elab …]` + `#check` wrote a file with real Lean 4.36); deny list extended (17 bypass forms tested) and every `lean` sandboxed with bubblewrap (no network/home, read-only), proof by test | ✅ fixed (F1) |
| TeX injection | `^^5c` rebuilt `\input`/`\openout` past the sanitiser; tectonic read `/etc/hostname` into the PDF and wrote a file at an absolute path; sanitiser + TeX sandbox → literal text / `Read-only file system` | ✅ fixed (F5) |
| Experiment sandbox | kernel could reach 127.0.0.1:11500 (trusted) and JupyterLab's token; now own network namespace (TCP→IPC relay), `/run` `/tmp` empty, Jupyter runtime hidden; real sage + python kernel tests pass | ✅ fixed (F6) |
| D29 | automatic installs blocked from a dev checkout / non-default config dir / without the prefix elan; Lean installs never with `~/.elan` (tests) | ✅ fixed (F4) |
| Fault injection on storage | ENOSPC (fsync), real EFBIG (RLIMIT_FSIZE), 12 × kill -9 during writes → target always complete (`test_robustness.py`) | ✅ |
| Load | 300 slow-loris sockets + 200 WebSockets + 50-event burst: API answers < 5 s, all sockets served, all subscribers released; bodies > 4/16 MiB → 413 | ✅ |
| Scaled soak (20 min, demo, ~6 parallel jobs, 5 paired devices on WebSockets, reconnect storms every 60 s, PATCH bursts) | 1088 jobs, 627 949 WS events, 3 091 reconnects, 0 errors; threads 4 and fds 14–20 flat; RSS 59 → 127 MB linear → cause: demo `FakeBrain.requests` unbounded (F14, fixed); re-soak 10 min after the fix: 761 jobs, 285 298 events, 1 659 reconnects, 0 errors, RSS 61 → 76 MB in the first 2 min (warm-up) then +0.6 MB/min while the bounded caches fill (jobs ≤ 200, event ring 5000, demo request log ≤ 4000), fds/threads flat. A plateau was not observed within 10 min; a 2-hour soak remains to be run by the integrator | ✅ |
| Dependency audit | pip-audit main env 0; npm audit 0; cargo audit 0 vulns; govulncheck 0 called; osv-scanner pubspec/Maven 0; llama.cpp b11375 has CVE-2026-133710 / CVE-2026-107183 (**open, blocking**) | ⚠️ |

### Accepted risks (S-H) — see docs/SECURITY.md §8
- R-1 Every local process (any user) that can reach 127.0.0.1:11500 has full host rights (single-user host design).
- R-2 JupyterLab and the user's own kernels run code unsandboxed and share the UI origin (host-only unless `remote_jupyter`).
- R-3 Without a working bubblewrap, Lean, TeX and experiments run unsandboxed (health page shows it).
- R-4 pillow 12.3.0 in the Sage env (sage pin; Sage kernels sandboxed and offline).
- R-5 libssh2 / libexpat advisories in the main conda env (not reachable in Madalean's flows).
- R-6 Global pairing lockout can be triggered by an unpaired tailnet node (DoS, 10 min).
- R-7 Paired devices see each other's names and last IPs.
- R-8 Update channel has no expiry (freeze attack delays updates, integrity unaffected).
- R-9 Online Lean search / literature search send model-chosen query text to public services (`local` mode disables).
- R-10 The D28 deny list may refuse legitimate files (10/87 Mathlib Archive files, 0/493 miniF2F) and cannot be complete.

### Release blockers (S-H verdict: GO with conditions)
1. F7: release signing key unencrypted in `~/.config/madalean/release-keys/` on the host that runs notebooks → encrypt
   and move it out (sign_release.sh now refuses otherwise).
2. F11: bump llama.cpp to ≥ b12556 (CVE-2026-133710, GGUF heap overflow; CVE-2026-107183).
Not verified: strace of madalean-net log upload (code path verified: `logtail.Disable()` before start drops uploads);
real tailnet requests; Gradle transitive dependencies; tesseract/tectonic CVEs (no CPE data).

## 2.0 — article editor: LaTeX project, visual editor, compilation (session S-R, 2026-11-22) — docs/ARTICLE.md

Verified for real:
- `tests/test_texproject.py` (16 tests): byte-identical view round trip on a corpus (theorems, align, TikZ, macros,
  comments, \verb, nested braces), v1 → LaTeX migration keeping block ids, managed regions, suggestions on stable ids
  (accept / reject / stale / editor-applied, after moving blocks), guard (12 injection forms), package analysis, truth
  rule, real PDF with the system XeLaTeX (dev engine) incl. SyncTeX both ways and a one-click fix, Overleaf zip round
  trip + unsafe import refused + history, assistant producing suggestions only (unsafe model output refused, Sage cell
  created as an unapproved assistant cell), remote listener 401.
- The prefix's tectonic from a TEMPORARY prefix (env linked read-only, copied cache): analysis against the bundle
  index, `bundle` files fetched once with « Télécharger une fois » (network shared only for that run), then the same
  document compiled `--only-cached` (`MADALEAN_ONLINE_TESTS=1`); all five templates (amsart FR/EN, article, report,
  beamer, elsarticle) compiled with tectonic, then again offline.
- `web/e2e/article.spec.ts` 4/4, `e2e/a11y.spec.ts` 3/3 (axe 0 on article visual, preview, drawer, versions,
  Overleaf, phone, dark), vitest 63/63, svelte-check 0 error / 0 warning.

Not verified / limits:
- The real Overleaf container was only detected read-only (docker ps + /status); upload into Overleaf CE and the zip it
  gives back were not exercised by hand (CE has no API: the round trip is a manual upload/download by design).
- The live install's tectonic cache predates the new templates: until `install tex-bundle` runs again (the warm-up now
  compiles the article templates), the first compile of an article offers « Télécharger une fois » (needs network).
- SyncTeX inverse search is approximate (nearest box); equation numbers are not shown in the visual mode; TikZ is not
  rendered in the editor (raw block, drawn in the PDF).
- `tests/test_i18n.py` reports 3 untranslated strings from the Calcul notebook (S-P), not from this session.
