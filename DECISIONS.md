# DECISIONS

## D1 — No root changes
- Choice: do not touch the system (no driver change, no `pacman -Syu`, no package install).
- Alternatives: install python-pytest-qt from repo; run nvidia-inst.
- Reason: audit shows the driver + CUDA already work; everything else can be user-level. Smallest blast radius.
- Evidence: AUDIT.md, nvcc sm_89 test kernel returned 0.

## D2 — Inference engine: llama.cpp built from source (CUDA, sm_89)
- Choice: `ggml-org/llama.cpp` built in `vendor/llama.cpp` with `-DGGML_CUDA=ON -DCMAKE_CUDA_ARCHITECTURES=89 -DGGML_NATIVE=ON`.
- Alternatives: `ollama-cuda` (repo, 0.35.1) or the existing manual ollama 0.18.2; AUR `llama.cpp-cuda` (does not exist).
- Reason: the mission requires an OpenAI-compatible `llama-server` that the GUI starts/stops with explicit control of
  `-ngl`, ctx, batch, KV-cache type and flash attention; it also ships `llama-bench`, `llama-quantize` and
  `convert_hf_to_gguf.py`. Ollama hides those knobs and runs as a separate daemon. User's ollama is left untouched.

## D3 — Model source: convert official safetensors ourselves
- Choice: download `Goedel-LM/Goedel-Prover-V2-8B` @ `dfd02e6271a58375dfbf3ece0175277cf6b6a89a`, convert + quantize locally.
- Alternatives: `mradermacher/Goedel-Prover-V2-8B-GGUF` (exists, ~370 downloads), `NikolayKozloff/...Q8_0-GGUF`.
- Reason: provenance from the official repo, exact tokenizer/chat template, freedom to produce Q4_K_M and Q5_K_M with the
  same llama.cpp version used for inference.

## D4 — Prompt format: verbatim from Goedel-Prover-V2 `src/utils.py` (DeepSeekCoTHandler)
- Initial: "Complete the following Lean 4 code:\n\n```lean4\n{stmt := by sorry}```\n\nBefore producing ... proof plan ..."
- Correction: previous assistant output appended, then "The proof (Round {n-1}) is not correct. Following is the compilation
  error message, where we use <error></error> to signal the position of the error.\n\n{errors}\n\nBefore producing ... analysis of the error message."
- Error string built exactly like `get_error_str` (max 8 errors, 4 lines context). Reference copy: `docs/goedel_utils_reference.py`.
- Sampling as in their inference: temperature 1.0, top_p 0.95 (GUI default; adjustable).

## D5 — Lean workspaces; reuse existing installs
- `lean-prover49`: clone of `xinhjBrant/mathlib4` @ `2f65ba7f1a9144b20c8e7358513548e317d26de1` (the Goedel-Prover-V2
  submodule), toolchain `leanprover/lean4:v4.9.0-rc1`. Used as the workspace directly, like Goedel's `DEFAULT_LEAN_WORKSPACE`.
- `lean-current`: new Lake project requiring Mathlib tag `v4.34.1` (toolchain v4.34.1 = latest Lean stable release).
- Existing user projects (lean4web `MathlibDemo`, `<projet de cours>`) are auto-detected and offered **read-only**;
  the app never runs `lake build`/`update` in them. Rationale: user said Lean and lean4web are already installed; reuse
  without risking their working setups. elan + `~/.cache/mathlib` are shared.

## D3b — Revised: community GGUF (mradermacher) instead of local conversion
- Evidence: official safetensors download ran at ~1 MB/s on flaky WiFi (2.1 GB in ~35 min ⇒ >4 h for 16.4 GB);
  intermittent DNS failures.
- Choice: `mradermacher/Goedel-Prover-V2-8B-GGUF` @ `43fab68ec71738a75b0a84738e18b222d2d4e249`, files Q4_K_M (5.03 GB)
  and Q5_K_M (5.85 GB), SHA-256 verified against the HF LFS oid (stored as `~/models/*.sha256`).
- Integrity vs official: the embedded `tokenizer.chat_template` is compared to the official `tokenizer_config.json`
  (downloaded from the official repo at the pinned revision) — see STATE.md.
- `scripts/download_model.sh` stays re-runnable; local conversion remains possible (`.venv-convert`, llama.cpp
  `convert_hf_to_gguf.py`) if the official weights are fetched on a faster link.

## D6 — lean-prover49: build Mathlib from source
- Evidence: `lake exe cache get` at 2f65ba7 tries `lakecache.blob.core.windows.net` → HTTP 404 for every file
  (also 404 on `mathlib4.lean-cache.cloud`): 2024 artifacts are no longer served.
- Choice: `lake build Mathlib` locally (nice 10, ~4650 files, CPU only, no network). One-time cost; then fully offline.
- lean-current (v4.34.1) uses the live cache. Setup split into `scripts/build_prover49.sh` and `scripts/setup_current.sh`.

## D7 — Default inference settings (evidence: BENCH.md)
- Q4_K_M, ctx 24576, KV q8_0, flash attention on, -b 2048 -ub 512, all layers on GPU.
- Alternatives: 16k f16 (6 % faster tg but truncates the 16k-token answers observed on miniF2F); 32k q8_0 (0.5 GB VRAM
  headroom only); Q5_K_M (10–12 % slower, needs ctx ≤ 16k to keep headroom).
- Sampling = Goedel-Prover-V2 inference script: temperature 1.0, top-p 0.95. max_tokens 16384 bounds one attempt
  to ~8 min worst case at ~30 tok/s.

## D8 — Bound llama-server host prompt cache (`-cram 1024`)
- Evidence: llama-server logs "cache state ... limits: 8192.000 MiB" — by default it may keep up to 8 GiB of prompt
  states in RAM; the soak test must show flat memory.
- Choice: 1024 MiB. With one slot and sequential attempts, the slot KV cache already reuses the shared prefix
  (`cache_prompt`); the RAM cache only helps when switching chat ↔ prove.

## D9 — Never plan a model load without a GPU snapshot
- Evidence: soak run started the server before the first `nvidia-smi` poll returned → planner saw "no GPU" → CPU
  (VRAM stayed 484 MiB, server RSS 9 GB, GUI lag > 1 s). `AppContext.with_gpu_info` now defers the load until a
  snapshot (or a definitive "no GPU") arrives, 3 s max.

## D10 — Support both Lake build layouts; strict test workspace
- Evidence: lean-prover49 (Lean 4.9) was reported "Mathlib n'est pas compilé" although the build succeeded: old
  Lake writes oleans to `.lake/build/lib`, newer Lake to `.lake/build/lib/lean`. The integration tests had silently
  fallen back to lean-current.
- Fix: `Workspace.lean_path()` uses whichever layout exists per package; `LAS_TEST_WS` now fails loudly instead of
  falling back. Verified: good proof accepted (9.6 s cold), sorry and wrong proofs rejected (2.2 s warm) on Lean 4.9.

## D11 — Lifetime fixes found by the full suite
- A lambda capturing its emitter (`p.started → lambda: p.processId()`) caused a double delete (segfault) → bound slot.
- One `ChatStream` per attempt was never freed (GUI RSS +24 MB over a 30-min soak) → streams `deleteLater()` after reporting.

## D12 — Natural language → Lean with Goedel-Formalizer-V2-8B (second model, swapped on the same GPU)
- Evidence: HF search shows `Goedel-LM/Goedel-Formalizer-V2-8B` (Apache-2.0, same team as the prover, thinks before
  answering) and community GGUFs; model card gives the exact prompt and sampling (T 0.9, top-k 20, top-p 0.95).
  Real run (`bench/translate_real.jsonl`): 3/3 problems (French plain text, French+LaTeX, English) compile on the
  first try in 9.5–21 s.
- Choice: Q4_K_M GGUF (mradermacher @ 7e10076, sha256 14f0cf69…), prompt verbatim, up to 3 tries until Lean accepts
  the statement (compiled with `sorry`), standard header enforced. The statement is then shown for **human review**
  (a statement that compiles can still mean something else) before any proof search.
- Alternatives: one general chat model to translate (no formalization training, worse); 32B formalizer (does not fit
  8 GB); keeping both models loaded (2 × 5 GB > 8 GB VRAM) → swap per task (≈ 4 s, `AppContext.ensure_model(role)`).

## D13 — Loop guard
- Evidence: user screenshot of the chat repeating two comment lines forever; chat had no repetition control.
- Choice: `leancheck.detect_loop` (shortest period repeated ≥ 5× covering ≥ 600 chars; ≥ 1500 chars when the period is
  < 60 chars so legitimate `· norm_num` lists are not cut) checked every 40 streamed chunks in `ChatStream`; on a loop the
  request is aborted, the first occurrence is kept and the prover / formalizer starts a fresh attempt. Chat also sends
  `repeat_penalty 1.1` and DRY (0.8, length 4). Prover sampling is left exactly as in the Goedel scripts.

## D14 — LaTeX in/out without touching Overleaf's API
- Input: `texio.extract_statements` (theorem/lemma/proposition/exercise… environments, comments and `\label` removed;
  fallback = document body). Output: self-contained `.tex` (XeLaTeX, `fvextra` Verbatim — `listings` mis-placed `⟩`
  under XeLaTeX), verified to compile with the local XeLaTeX (`test_exported_tex_compiles_with_xelatex`).
- Overleaf: the instance on this machine answers 404 on 127.0.0.1:80 (OVERLEAF_SITE_URL is the Tailscale name) and
  an API import would need the user's login → no automation; the app exports a file / copies the code and opens the
  configurable URL (Système → adresse d'Overleaf). Passwords are never requested.

## D15 — Proof → French explanation: a third, general model (Qwen3-8B), not the prover
- Evidence (measured, same proof, same server): Goedel-Prover answered the English prompt in English with Markdown
  headings and re-wrote the Lean proof; with a French prompt it mixed French and English ("In Lean, this is expressed as…");
  with an assistant prefill it drifted back to "Step-by-Step Abstract Plan / Lean 4 Proof with have statements".
  Qwen3-8B Q4_K_M (the base architecture family of both Goedel models, official `Qwen/Qwen3-8B-GGUF` @ 7c41481,
  Apache-2.0) with the same prompt in French: fluent French, correct structure (statement / idea / numbered steps),
  10.6 s and 19.0 s for the two test proofs.
- Choice: `Explainer` service with `chat_template_kwargs.enable_thinking=false`, T 0.5, repeat_penalty 1.05, loop guard;
  Markdown + `$math$` rendered in the GUI (math → Unicode), converted to safe LaTeX for the export (compile-tested).
  The explanation is labelled « rédigée par une IA » everywhere; the Lean proof stays the authority.
- Cost: one more 5 GB model (3 × 5 GB on disk, swapped in 8 GB VRAM). `--no-explainer` skips it; the button then explains
  how to get the model.

## D16 — Chat tab removed
- The tab used the prover as a chat model, which it is not (it looped — user screenshot). Its value for the target user
  (learning Lean) is now covered by the guided flow, the Aide dialog and « Expliquer ». Settings keys are ignored on load.

## D17 — Portable installer
- Evidence: fresh `git clone` + `./install.sh --install-deps --backend cpu` in a **Fedora 44 container** found two real
  portability bugs (missing `libGL` for PySide6 wheels; a GUI test that depended on installed models) — both fixed.
- `install.sh`: distro family from /etc/os-release (arch/fedora/debian/suse), package lists per family, `--backend
  auto|cuda|cpu`, CUDA toolkit looked up in /opt/cuda, /usr/local/cuda*, retry with an older host compiler (g++-14…11) or
  `-allow-unsupported-compiler` when CUDA rejects a newer GCC (known Fedora/Arch issue), PySide6 from the distribution if
  importable else `PySide6-Essentials` in the venv, final start-up probe. Drivers and CUDA are never installed for the user.
- Not covered: AMD/Intel GPUs (Vulkan/ROCm builds) — the app then runs on the CPU.


## D18 — v1.1 design choices (asked to the user first, 2026-10-04)
- Memory = profile + dossier history + library (user selected all three). Chaining = fully automatic (user choice; the
  statement stays visible in the thread, a « Pause pour relire l'énoncé » option exists, off by default).
  Refinement = discussion thread per dossier. Language switch = interface + model answers.
- The profile is given to the formalizer (as « conventions » appended to the natural-language text; the model-card
  template itself is untouched) and to the explainer. **Not** to the prover: its prompt must stay Goedel's (D4).
- Follow-up routing: keyword router FR/EN (`dossiers.route`) with a visible override combo, instead of an extra LLM call
  that would cost a model switch (≈ 5 s) for every message.
- Proof refinement: prover conversation = [Goedel initial prompt, previous verified proof, « The proof above is correct
  … The user now asks: … »]; then the usual Lean-error correction rounds. Statement refinement: formalizer input =
  problem + previous statement + requested change. Explanation refinement: explainer conversation continued.
- Library: every accepted proof is stored (header stripped, dependencies recorded, same-workspace only); for a new
  statement, up to 3 entries with Jaccard vocabulary similarity ≥ 0.25 are pasted above the target theorem (with their
  proofs, so Lean checks everything). The target theorem is therefore always the LAST declaration of a file (D19).

## D19 — Target = last theorem; per-dossier theorem names
- `prepare_statement`, `theorem_name`, `initial_prompt` (rsplit, identical output for a single theorem — tested) and
  `assemble_proof` now target the last declaration; helper lemmas the model copies back are de-duplicated by name.
- Each dossier gets a unique Lean name (`slug(title)_xxxx`) so library entries never clash.

## D20 — i18n
- French is the source language; `_()` + `i18n_en.EN` (629 entries). An AST-based key extractor
  (`scripts/dev/i18n_keys.py`) feeds `tests/test_i18n.py` (no missing key, same placeholders, no French in English).
- Changing language rebuilds the main window in-process (model and dossiers untouched; refused while a task runs).
- Pitfall found: parameters/locals named `_` (`*_`, `lambda _=False`, `path, _ = …`, `for _ in`) shadow the function;
  all renamed, and a check confirmed none remain.

## D21 — Updates of Lean/Mathlib and of the Goedel models (asked to the user first, 2026-10-04)
- User choices: weekly check at start-up (on by default, can be turned off), one-click install, obsolete versions
  deleted automatically, shipped in 1.1.0. The check is a deliberate, visible exception to offline mode: only
  `git ls-remote` on mathlib4 (GitHub) and the Hugging Face model API are contacted; no identifier is sent.
- What is followed: the stable Mathlib tags (`v4.N.M`, no release candidates) for the `lean-current` workspace; new
  `Goedel-LM/Goedel-{Prover,Formalizer}-V*-8B` models (8B only: 8 GB card) installable once a Q4_K_M GGUF exists at
  mradermacher (same source as the installer), and re-published GGUF files (checksum changed).
- Not followed: `lean-prover49` (Lean 4.9 + Goedel's Mathlib fork) is the model's training environment and stays fixed;
  the Qwen3 explainer and llama.cpp stay pinned (reproducibility).
- Install = build next to the old version → verify (Mathlib: a test theorem compiled with the new workspace; model:
  SHA-256 + loaded by the bundled llama-server on the CPU and asked for a few tokens) → switch → delete the obsolete
  version (old workspace; old Lean toolchain only if no `lean-toolchain` in the home folder still pins it and it is not
  the elan default; older model files of the same role). Any failure before the switch leaves everything unchanged.
- The shared Mathlib download cache (`~/.cache/mathlib`) is not pruned: other Lean projects of the user use it.
- Limit: a future Goedel model could expect a different prompt format; the smoke test checks that it loads and
  answers, not its proof quality.

## D22 — Circular reasoning detector (bug report with a screen recording, 2026-10-04)
- Symptom: Goedel-Prover recycled the same paragraphs with small variations until the 16 384-token limit (≈ 6 min per
  attempt, 8 attempts planned). `detect_loop` only sees exact repetitions, so it never fired.
- `detect_rambling`: code blocks removed (proofs legitimately repeat tactic lines); in the last 8 000 characters of
  prose, the share of sentences (≥ 30 chars, normalised) already written earlier; fires at ≥ 60 % and ≥ 12 sentences,
  never before 20 000 characters of prose. Checked every 200 tokens in `ChatStream`; the attempt then ends as « loop ».
- Calibration on 11 real answers collected with the app's server settings (bench corpus, not committed except one
  excerpt in `tests/data/`): with a first setting (5 000/12 000) the detector fired on 4 answers that had a circling
  phase, one of which later escaped and **was accepted by Lean** (mathd_numbertheory_353). With the final setting it
  fires on none of the 19 naturally finished answers (8 more runs of the failing statement were added) and still
  catches the recorded failure pattern.
- The same corpus exposed a false positive of the **exact** detector (since 1.0): a correct answer
  (amc12b_2021_p3, accepted by Lean) repeats a 121-character tactic block 5 times and was stopped at 7 600 characters.
  Inside a Lean code block (odd number of fences in the whole answer, now passed instead of the last 12 000
  characters) an exact loop now needs 12 repetitions and 3 000 characters; the real runaway in code
  (imo_1959_p1, nested `Nat.gcd_eq_left/right` until the token limit) is still stopped, at 6 000 characters.

## D23 — « Comprendre » step before translation
- Same report: « donne une preuve du théorème de la base incomplète… » was formalised as « more than dim V vectors are
  dependent » (a different theorem); the formalizer only receives the user's words, and a theorem name gives it little.
- The general model (Qwen3-8B, already installed for explanations) now rewrites the request as one precise,
  self-contained statement in English (objects, types, hypotheses; named results stated in textbook form; plain
  statements only translated) before Goedel-Formalizer. Measured on the CPU: the incomplete basis theorem becomes
  « …let S be a linearly independent subset of V. Then there exists a basis of V that contains S ». Unknown names
  (« lemme des bergers ») or non-mathematical text give `UNKNOWN`: the chain stops and asks for the statement instead
  of inventing one (first prompt version hallucinated a theorem there).
- The rewritten statement is shown in the thread before the Lean statement, so the user sees the interpretation.
  Cost: one more model switch (≈ 5 s) and ≈ 5–20 s of generation. Skipped when the explainer is not installed, and for
  « Corriger l'énoncé » requests (they go to the formalizer with the previous statement, as before).
- Limit: ambiguous names are resolved by the model (« théorème de Bézout » → curves, not the arithmetic identity); the
  user corrects it in the thread.

## D24 — Prove loop: bounded correction chains, token floor, user hints (bug report, 2026-10-04)
- Symptom: « les 8 essais reproduisent la même erreur ». Replayed on the user's dossier (cubic polynomial has a real
  root, Lean 4.9): attempt 1 takes a bad line of attack, attempt 2 (correction) repeats it with the same errors, attempt
  3 gets only 1 556 tokens because the conversation filled the 24k context (`_fit_messages` allowed down to ≈ 2k), so
  it is cut and returns a `sorry` skeleton; every later attempt does the same.
- Goedel-Prover-V2 is evaluated with a few self-correction rounds on top of independent samples, not with one ever
  growing conversation. Now: at most 2 corrections per line of attack (`Prover.MAX_CORRECTIONS`), then a fresh sample;
  a fresh sample immediately when Lean returns exactly the same feedback twice; and the conversation restarts instead of
  requesting fewer than 8 192 tokens (`MIN_GEN_TOKENS`). Round numbers restart at 0 for each line of attack (Goedel's
  « Round {n-1} » convention).
- Router: before a proof exists, follow-ups were always sent to the formalizer (the statement was re-translated, the
  prover never saw the request). Now only statement-related requests are; others start a new proof search with the
  request appended to the initial prompt (`HINT_TEMPLATE`, the only addition to Goedel's prompt, used only when the
  user wrote something).

## D25 — Real names for invented lemmas
- Seen in the 1.1.2 live run: most refused attempts cite lemmas that do not exist in Mathlib 4.9
  (`Polynomial.exists_root_of_odd_degree`, `Polynomial.exists_root`, …); Lean's message gives no alternative, so the
  next attempt guesses another name.
- `names.py` indexes the declarations of the sources that are compiled in the workspace (module roots found in the
  `.lake/**/build/lib` directories of `lean_path()`, plus the toolchain's `Init`), with a light parser (namespaces,
  sections, `_root_`, declaration keywords, signature head up to `:=`). No Lean process; 5.4 s for lean-prover49
  (164 474 names), 9.8 s for lean-current (274 895), cached in `~/.cache/lean-ai-station/names/` (key: workspace,
  toolchain, mtimes of `lake-manifest.json` / `lean-toolchain`, so an update rebuilds it). Built in a background thread
  when a proof search starts; if not ready yet, the feedback is simply unchanged.
- Suggestions: same last component in another namespace first, then token overlap + string similarity (+ bonus for
  the same namespace). Added after Goedel's error string as « Note on unknown names » (up to 3 names × 5 suggestions,
  with signatures). Names generated by attributes (`@[to_additive]`, `@[simps]`) are not indexed: they can be missing
  from suggestions, never wrongly reported, because only names Lean itself rejected are looked up.
- Lean 4.9 reports `T.foo x` with `T` a type (`Real`, `Nat`, `Eq`) as « invalid field notation » without the name:
  the name is then read from the `<error>` span of that error.

## D26 — Follow-up messages are read by the general model (bug report, 2026-10-04)
- Symptom: « Montre qu'un carré pair est issu d'un entier pair » was rewritten as the converse by the « comprendre »
  step, then « et la réciproque », « et si n^2 est pair montre que n est pair », « J'ai dis montre que si n^2 est pair
  alors n est aussi pair » were all routed to `proof` by the keyword router (no statement keyword; a proof existed), so
  the same theorem was proved three more times.
- Understanding: the prompt now asks to identify what is assumed and what must be concluded (with this very example)
  and to answer `EN:` (for the formalizer) + `FR:` (shown in the thread, in the interface language). Measured on Qwen3
  (CPU): the three phrasings give « If n² is even, then n is even »; real-model test `test_task7_direction_and_converse`
  proves `Even (n^2) → Even n`.
- Routing: in « Auto » mode, a follow-up goes first to the general model with the current theorem, its Lean statement
  and whether it is proven; it answers ACTION: STATEMENT | PROOF | EXPLANATION and, for STATEMENT, the complete new
  theorem (EN + user language). A new statement is then translated afresh (no « previous formalization » anchoring),
  proved and explained; the explanation now uses the understood statement rather than the original problem. Measured:
  10/11 messages classified as intended; the miss (« pourquoi utilises-tu ring ? » → PROOF) is overridden by the
  keyword router when it has explicit explanation/statement keywords and no proof keyword. Cost: one model switch per
  follow-up (≈ 5–15 s). The manual stage selector and quick-action buttons bypass it, as before.
- Rejected names (D25 addendum): the 1.1.3 note reached the model only inside a correction; every fresh sample
  (after 2 corrections or a repeated error) started without it, so `Polynomial.exists_root` came back. Names rejected by
  Lean are now kept for the whole search and appended to the first message of each fresh sample. Lean 4.34 writes
  « Unknown identifier `x` » (capital, backticks): both wordings are recognised.
- Live run on the user's cubic: the model also kept the rejected name inside its corrections, despite the note. Reusing
  a name Lean already rejected in this search now ends the line of attack at once: fresh sample, with the warning at
  the top of the task.

## D28 — No host code execution through Lean compilation (finding of S-E, 2026-11-21)
- Lean runs code while elaborating a file: `#eval` (IO), `initialize`, user-defined elaborators/tactics/macros
  (`elab`, `macro`, `syntax`, `@[tactic …]`, `run_cmd`…), `unsafe`/`implemented_by`, native code. Model output, paper
  text given as hints, and paired remote devices all reach the Lean checker, so this was a host code-execution path.
- `leancheck.exec_risks()` scans the code with a Lean-aware lexer (nested block comments, line comments, strings;
  unterminated comment/string = scanned as code, fail closed) and `runtime/lean.py` refuses to compile when any risk is
  found — single choke point before every compilation. Imports limited to Mathlib, Aesop, Batteries, Std, Qq,
  ProofWidgets, Plausible. Word-level matching can refuse a legitimate file using these words outside comments
  (e.g. a variable named `prefix`); accepted trade-off, refusal message names the construct. To be re-reviewed by S-H.

## D29 — Incident: an automatic update ran during a test and wrote to ~/.elan (2026-11-21)
- A test server started from the dev checkout with a temporary config (`updates_auto` defaults to true) upgraded the
  dev checkout's `workspaces/lean-current` to Lean 4.36.0 / recent Mathlib at 16:11 (verify-then-switch worked; the
  proven dossiers were re-checked), and installed the toolchain v4.36.0 into the user's `~/.elan` because the prefix
  did not exist yet (ELAN_HOME fallback). No toolchain was removed by Madalean (v4.34.1 is still there).
- Rules from now on: automatic installs only run from an installed prefix (never from a dev checkout or with a
  temporary config dir), and never with `~/.elan` — if the prefix elan is missing, the update is notify-only.

## D30 — Adaptive model selection for proofs: leaderboard + bounded tournament (user request, 2026-11-21, S-J)
- Request: when a task fails after 4 inconclusive attempts, switch model; remember which model solved what; keep the
  best and most efficient; or race several models on the same problem and keep the best two for the next tasks —
  « safe but fast, beware of infinite loops ».
- Observed: free keyless providers often answer 429 and the router falls through many models;
  `kilo:nvidia/nemotron-3-ultra-550b-a55b:free` proved 3 of 4 test problems in agent mode while others failed or were
  paused; a cubic-polynomial problem failed after 4 agent runs (55 min) on one model.
- Decision: a persisted, decayed, Bayesian leaderboard per model × task (× domain) feeds the router as a bonus
  (explainable); the proof stage runs round 0 with the best model (4 attempts, the 2nd best replaces it only when it
  cannot run), then up to 3 races of 3 never-tried models (Goedel local counts as one), first Lean-verified proof
  wins. Hard caps: 40 min, 16 attempts, 3 M tokens, 3 rounds, each model once per task beyond round 0. Paid models
  only with `paid_first` / explicit choice, with an estimated cost. Details: docs/BRAIN.md §11.
- Rejected: racing all contestants from the start (wastes free quotas, more 429s); unbounded « retry until proved »;
  recursive re-tournaments.

## D31 — Proof decomposition as THE way to prove hard theorems, bounded (user request, 2026-11-21, S-L)
- Request: Lean splits each hard theorem into lemmas shown as a graph (mind map); independent lemmas if possible; the
  user validates (or edits) the PLAN, then Madalean proves each lemma automatically and only asks again when one
  fails (another track, a new split, or a `sorry` hole); « ne pas se perdre », « attention au piège du découpage
  infini ».
- Decision (extends `research/proofplan.py`, no parallel system): an analysis writes a main track + ≤ 2 alternative
  tracks, each with 2–6 lemmas AND the combination (Lean proof of the parent from the lemmas). ONE Lean compile gates
  the plan before the user sees it: lemma statements with `sorry`, each combination, and equivalence probes (child ⇔
  parent by `exact`/`apply`/`simp_all only` both ways); a failing plan is regenerated with Lean's errors (≤ 2 tries),
  otherwise shown « à vérifier ». A second compile applies the obvious-stop rule (omega, norm_num, linarith, simp_all,
  aesop, `exact?` under a heartbeat cap; never citing itself): such a lemma is proved at once and never split.
  When all lemmas of a node are proved, the stored combination is compiled with the REAL lemma proofs under the
  strict verdict (D28 gate) — the node is proved, up to the root. A failed lemma: other track → split deeper →
  hole; a hole makes ancestors « Conditionnel — N trous », never verified (same invariant as S-G).
- Termination: depth ≤ `plan_max_depth` (3), ≤ 6 lemmas per track, ≤ 2 alternatives, ≤ 30 live nodes (the budget
  truncates alternatives first, then the last split), ≤ 2 model calls per analysis, a run budget
  (`plan_budget_minutes`, 180), a lemma equal (text) or equivalent (Lean) to its parent refuses its whole track, an
  obvious lemma cannot be split, and every split is a user action (failure options) — nothing splits by itself.
- Rejected: splitting until every step is « obvious » (= line-by-line proofs, unbounded); recursive automatic
  re-splitting on failure (the user chooses); trusting the model's combination without Lean.

## D31 — Check the statement and look in Mathlib before proving (user's failures of 2026-11-21, S-K)
- Observed on the user's own dossiers: a compact set without « non vide » and two subsequences without « même limite »
  were translated into FALSE statements and searched 8 times; Cayley-Hamilton was translated with `minpoly`, then with
  `LinearMap.charpoly K f` (does not compile); Riesz with an invented `[Banach 𝕜 X]`; E/ker f ≅ Im f never compiled —
  although Mathlib has `LinearMap.aeval_self_charpoly`, `FiniteDimensional.of_isCompact_closedBall`,
  `LinearMap.quotKerEquivRange`.
- Decision: two bounded stages (docs/BRAIN.md §12). « Vérifier l'énoncé » before the first proof search of each
  statement: model fidelity check (JSON issues + fix) in parallel with Lean probes of the pinned negation
  `¬ (∀ BINDERS, CONCL)` (automatic tactics, degenerate instances ∅ / 0 / constant functions, the model's
  counterexample tactics). « Faux » only when Lean proves the negation (strict re-check, D28 gate); the model alone can
  only make it « douteux ». Both stop the automatic chain with the reasons and two buttons (« Corriger l'énoncé avec :
  … », « Prouver quand même »); never silent. « Mathlib d'abord » in the proof stage: famous table + RAG candidates,
  one-line templates in ONE compilation, `exact?`, then ≤ 2 short model proofs using the candidates; the translator
  gets Mathlib's statement as a reference when a known result is named.
- Rejected: trusting the model's « false » (free models over-flag and under-flag: on the real run one called the
  Riesz statement with `[NormedField 𝕜]` faithful); `slim_check`/`plausible` (random testing runs user definitions
  through the interpreter at elaboration: kept out until S-H reviews it); `exact?` as an accepted proof (forbidden in
  proofs: its « Try this » suggestion is re-checked instead).
- Loop guard (coordinator report): free reasoning models sometimes end a correct answer with endless
  `import Mathlib.…` lines; the guard stopped them (right) and the formalizer threw the whole answer away (wrong). The
  last complete ```lean4 block before the loop is now a candidate (Lean decides); the pipeline's guard is reset when
  the engine restarts with another model; loop-finished attempts record streamed tokens and time (were 0).

## D32 — LAN listener kept (user decision, 2026-11-21)
- The user keeps the LAN listener (port 11502, plain HTTP) for devices without Tailscale. Browsers there need a code at
  every visit and get a temporary session; app shells keep their device token. Accepted risk: on the LAN the code and
  the session cookie travel unencrypted on the Wi-Fi (no `Secure` flag possible over HTTP); Tailscale (HTTPS) stays
  the recommended path. Listed in docs/SECURITY.md accepted risks.

## D33 — Hugging Face Goedel online first; local models only offline (user decisions 2026-11-22, S-T)
- Goedel-Prover-V2-32B is served live on Hugging Face Inference Providers (featherless-ai). With the user's HF token
  it opens every proof (tournament round 0) with Goedel's own loop and verbatim prompts, pinned, paid within the same
  monthly / per-proof caps as Claude (no published price: conservative estimate $1.00 / $3.20 per MTok). Free models
  follow as before; Goedel-Formalizer is used when a provider serves it (none on 2026-11-22).
- Local models (Goedel 8B, Qwen on llama-server) run only without Internet or when no online model could run at all;
  never as a tournament contestant while online, never after online models searched and failed. llama-server stays
  stopped in normal online use. Reachability: cached probe (30 s / 10 s), « provider down » distinct from « offline ».
- Rejected: listing the router's whole catalogue (hundreds of paid general models; the Goedel prompts are the point);
  running Goedel 32B as a tool-using agent (it is not trained for tools); a key test by inference (costs credits:
  `whoami-v2` instead). Details: docs/BRAIN.md §13.


## D34 — Automatic model rankings and tracked component updates (user request, 2026-11-22, S-V)
- Request: « donner régulièrement les ranking des meilleurs modèles de façon automatique dans l'app comme dans
  Tontolo, bien suivre les nouveautés et les mises à jour. Sage, LaTeX, Lean et Mathlib doivent être à jour
  régulièrement. »
- Rankings: per domain, Madalean's own Lean-verified results first, then the public LMArena signal (keyless HF
  datasets-server, CC BY 4.0, cited with its publish date; verified 2026-11-22), then the catalogue estimate — each row
  says which. Exact-name matching only; no score for an unlisted model. Catalogue every 12 h, public weekly, manual at
  most hourly; never in local mode. New models get « Nouveau » for 14 days and a small exploration bonus in the router.
  Rejected: Artificial Analysis (needs a key; possible later), scraping leaderboard web pages (unstable, licence
  unclear), fuzzy name matching (would attribute scores to the wrong model).
- Components: pins brought by a signed release (`deps`: Sage env, main env incl. tectonic, TeX bundle, elan…) now
  install automatically at a quiet moment like Mathlib, with rollback; the tectonic bundle relay is probed for newer
  bundles (notify only). D29 unchanged. Details: docs/BRAIN.md §14, docs/ARCHITECTURE.md §12.


## D36 — Sandboxed tools get a real private home; smoke suite + health self-test (user request, 2026-11-22, S-AC)
- Request: fix « Read-only file system: '/nonexistent' » (Maxima in a Calcul cell) **at the root, for every case**.
- The sandboxed kernel's `HOME` was a missing, read-only path; each library that caches under `HOME` broke in turn.
  Decision: every sandboxed tool has a real, writable, private, short home — kernels: `/tmp/h` bound to
  `<experiments>/.home/<project|shared>` (persistent caches); Lean and TeX: `/tmp/home` on the sandbox's tmpfs
  (ephemeral). All XDG / Sage / Maxima / IPython / matplotlib / numba / cython / pip / TeX directories inside it.
  The writable surface of each sandbox is unchanged (the home is inside the already writable directory, or on the
  sandbox's private tmpfs); no network, no secret, hidden config directories as before (tests).
- Rejected: patching variables one library at a time (the integrator's `MAXIMA_USERDIR`: the next library breaks);
  `HOME` = the experiments directory itself (too long for GAP's probe; mixes caches with the user's files);
  `PYTHONPYCACHEPREFIX` (recompiles Sage at each start, 0.9 → 3.0 s); a throwaway home per kernel start (Maxima
  rebuilds its cache at every start: first Fourier cell 8.1 s, 0.9 s with the persistent home, measured).
- Regressions are caught before the user meets them: a smoke suite in the real sandboxed kernel (tests, marker
  `sage`) and its fast subset as a health self-test after each Sage / Madalean / Lean / TeX change, with « Réparer »
  (reset the kernels' homes, test again). Details: docs/CALCUL.md §10, docs/SECURITY.md (F6).


## D35 — Calcul: latency first for code transcription, automatic corrections, version-checked syntax, recipes (user requests, 2026-11-22, S-AB)
- Request: the « Demander » transcription was very slow; « Réécrire » was refused (« le dossier travaille »); the
  model must write code valid for the installed Sage / Lean / Mathlib; fewer buttons; explanations on demand;
  automatic correction of failing model code; learned recipes; long formulas cut on a phone.
- Transcription = a dedicated fast path of the brain (`classify.task("transcribe")`, docs/BRAIN.md §15): measured
  latency in the ranking, staggered race of ≤ 3 models, minimal thinking, short timeouts, own request pool, no job
  slot. Rejected: a new `Role` (the roles are a fixed interface used everywhere); always racing 3 models from the
  start (triples requests for nothing when the first model is fast); a fixed model (free quotas run out: 429/503 were
  seen during the measurements, the race absorbs them).
- One generation per cell: a new request replaces the running one; the automatic correction runs after the kernel
  lock is released. The notebook's « busy » is its own error (`calcul_busy`), never the dossier text.
- **Automatic correction policy** (safe and smooth): before display, code that does not compile goes back to the
  model up to 2 times (nothing runs). After a failed run, up to 3 corrections per request, each a visible version
  (« Corrigé automatiquement », « Revenir à la version précédente »). The corrected code **re-runs by itself only
  when the host's policy already lets model code run without approval (`experiments_auto`)**; otherwise it is shown
  for one click « Approuver et exécuter ». Rejected: « approval covers the request » (an approval of code X would let
  an unseen code Y run: the approval-by-hash rule of D28 / S-M stays exact); asking a confirmation for each
  intermediate attempt (too many clicks for code that does not even compile).
- **Syntax catalogue**: small cards per tool and installed version whose entries are executed (Sage) / compiled
  (Lean, plus the existing name index) during a build; failing or deprecated entries dropped; rebuilt on version
  change (start, update checkers' pass, Mathlib update). Fixed system prompt per version so provider prompt caching
  applies. Signatures and docstrings come from the installed Sage by introspection. Rejected: a hand-written card
  per version (drifts), the whole Sage reference manual in the prompt (slow, costly).
- **Recipes**: local only (`<config>/research/recipes.json`), tied to the Sage version and re-checked at each
  update; an exact-template match with safe parameter substitution answers without a model call (still model code:
  approval), otherwise a close recipe is an example for the model. Rejected: embeddings (an Ollama model may hold the
  GPU; word overlap + templates are enough for the notebook's short requests); sharing recipes between hosts.
- Cells: one « + », a new cell recognises code vs request (installed Sage's preparser + language markers) with a
  one-click « Code / Demande » chip; type menu in the cell head; actions right below what they act on.
- « Expliquer » is generic over sage | python | lean (`POST /api/code/explain`) for the Lean screens later.

## D38 — Stages in parallel, fast models for the short stages, nothing redone twice (TODO B12–B14, 2026-11-22, S-AF)
- Measured (B9): the first proof attempt started about 2.5 minutes after Lean accepted the statement (median 152 s
  on the user's jobs): guided reading (median 49 s) and statement check (40 s) ran first although only a « faux » /
  « douteux » verdict may stop the proof. Short stages sometimes landed on the local GPU model (265–395 s).
- **Parallel stages** (`pipeline/runner.py`, setting `parallel_stages`, on by default): after the statement, guided
  reading, statement check, Mathlib-first and the proof search run as asyncio tasks of the same job; explanation and
  informal proof are written together (the informal proof is recorded after the explanation, so the thread keeps its
  order). The first Lean-verified proof (Mathlib-first, a quick proof found by the check, or the search) cancels the
  other proof work; it is recorded only after the check, so a « faux » / « douteux » verdict still means « preuve
  non lancée » (same events, same `statement_false|doubtful` error, « Prouver quand même » unchanged) — even when the
  search had already found a proof (rejected: keeping that proof as verified; the user decides on the statement first).
  Mathlib-first's candidates reach the provers as soon as known (`job.mathlib_hint` is read at each new agent attempt).
- Safety: each stage task has its own resource owner `<job id>#<stage>` (the local GPU holder is per owner: two stages
  of one job never share or switch a loaded model under each other); « Arrêter » cancels the job task, whose
  `finally` cancels and awaits every stage task; leftover slots of the sub-owners are released by the orchestrator.
  Dossier writes stay safe: mutations happen on the event loop between awaits and `repo.save` serializes the whole
  dossier under its lock (the last writer always carries every earlier event / version). Stage results check that
  the statement / proof they were made for is still current before recording.
- Never parallel in `local` mode or when the role has no online model (one GPU model at a time: parallel stages
  would swap models on the GPU and be slower). Rejected: a set-valued `job.stage` (breaks every client); kept the
  main stage in `stage`, added `stages` and `timings`.
- **Short stages** (understand, route, notes, check reading, explanation, informal): the latency-first path of D35
  with the role's own categories, half latency weight for writing, local models only when every online model failed
  (BRAIN.md §16). Rejected: a separate « fast » role list (roles are a fixed interface); excluding local models
  entirely (offline must keep working).
- **Never redo twice** (`pipeline/stagecache.py`, `<cache>/stage-cache.json`, 400 entries per kind, LRU): key =
  normalized statement (comments, spaces and the theorem's own name removed) + workspace + Lean + Mathlib versions
  (+ the user's words, learning flag and language for the check: fidelity is judged against the words). Reused: the
  check verdict (not « unknown »), a Mathlib-first success (tactic + lemma, re-assembled for the current theorem and
  judged by a fresh strict Lean check; dropped when Lean refuses it), a Mathlib-first failure with candidates (hint
  for the provers, no new search). Rejected: caching proofs as « vérifiée » without Lean; caching the adaptation by
  a model as a negative forever (it is only skipped for the same Mathlib version). Library lemmas offered first:
  unchanged (`lib.relevant`).
- Measured: job `timings` (start / end per stage, kept in the job history) and `seconds` in the result events;
  `scripts/perf_report.py` reads them; `scripts/dev/perf_stages_demo.py` replays the real medians on the demo
  server (docs/PERFORMANCE.md « Étapes en parallèle (S-AF) »).

## D40 — New visual identity: « Madal∃an », navy and orange (user request, 2026-11-22, S-AH)
- The user supplied the logo (« Voici désormais notre identité visuelle, remplace tout ») : navy `#002B5C` script,
  the « e » as an orange `#FE7B01` ∃, an orange swoosh. It replaces the baobab-∀ icon, the serif text wordmark and the
  ink / paper / laterite palette everywhere (web UI, site, READMEs, Android, AppImage / desktop entry). docs/BRAND.md.
- **Vector master traced, not redrawn**: navy and orange separated by colour, traced with potrace, written as three
  absolute paths (`shells/branding/madalean-wordmark.svg`); rendered back over the source the difference is only
  anti-aliased edges (RMSE 2.5 %). Rejected: redrawing the script by hand or setting it in a font (loses the user's
  lettering). One script (`scripts/build_brand.py`) derives every other file, so a future logo tweak is one run.
- **App icon = orange ∃ + swoosh on a navy rounded square**: the ∃ is the distinctive part of the logo and stays
  legible at 16 px; the whole wordmark does not (a 3.4:1 word is under 5 px tall in a 16 px square). The logo's own swoosh
  is a 14:1 hairline, so the icon redraws it as a thicker crescent with the same rise; ≤ 32 px uses a heavier variant.
  Android adaptive foreground keeps the mark inside the 66 dp safe zone; monochrome layer for themed icons.
- **Accessibility first**: orange on white is 2.6:1, so it is never text or a thin icon on light surfaces — only fills,
  rules, underlines, highlight outlines (`--laterite-mark`). Orange text uses `#A84B00` (5.7:1) in light, `#FF9A3D`
  (8.2:1) in dark. Primary buttons stay navy with a white label (14:1); an orange button would need a navy label
  (5.4:1), never white. Links and focus use a navy-family blue `#0B4F9C` (8.0:1) rather than navy itself, so links stay
  distinct from body text. Dark theme surfaces are navy-tinted. Token **names** kept (`--ink`, `--accent`,
  `--laterite`, `--laterite-mark` …) so no component changed meaning; added `--brand-navy`, `--brand-orange`,
  `--on-brand-orange`. axe (e2e) clean in both themes.
- Header: the wordmark (white-script file in dark themes, switched by CSS on `data-theme` / `prefers-color-scheme`)
  from 1024 px up, the icon below. Pairing screen: the wordmark. « À propos »: icon + wordmark. Text alternative is
  always « Madalean ». Added a PWA manifest (with a maskable icon), `favicon.ico`, a full-bleed apple-touch icon.

## D39 — Calcul: one canonical code per request — request analysis, catalogue of structures, the best version kept (user request, 2026-11-22, S-AG)
- Request: « l'écriture de code est trop aléatoire, ça doit retenir le meilleur ; sur Sage ça oublie de charger les
  bibliothèques ; F_125 doit être reconnu comme F_{5^3} avec une syntaxe unique si je regénère deux fois ; un
  catalogue de la structure des codes Sage, Python et Lean en analysant la demande ».
- Causes found: temperature 0.2 and a staggered race (the first model to answer won: another model, another style,
  each time); « Réécrire » bypassed the cache and the recipes on purpose; recipes matched words, not mathematics
  (F_125 / F_{5^3} / GF(125) were three requests); the syntax card is rules, not constructions; nothing checked
  imports or names relied on from earlier cells.
- **Request analysis without a model** (`research/intent.py`): objects with canonical parameters (finite fields by
  their factored order, F_12 refused with the reason; Z/nZ; Q, Z, R, C, Z[i]; K[x, y]; Q(√d) reduced to squarefree d,
  Q(i), Q(ζ_n), Q(∛2); matrices; S_n, A_n, D_n, C_n; elliptic curves by their Weierstrass equation or label;
  integers), the operation (≈ 50, French / English), formulas in one spelling (own tokenizer: implicit products, ²,
  √, π, LaTeX). Key = hash of that structure; unknown words stay in the key (two different requests never share
  code). Rejected: a model to normalize (non-deterministic, slow); sympy in the server (not in the installed env).
- **Catalogue** (`research/codecat.py`): one construction per object / operation in Sage and Python (sympy / numpy
  / matplotlib, every import explicit) with naming conventions (`F125.<a> = GF(5^3)`, `Z12`, `R.<x>`, `K`, `M`, `G`,
  `E`, symbolic variables always declared), and Lean / Mathlib constructions **per version** (Lean 4.9 of the
  prover: `Fintype.card` / `Nat.factors` / `∑ … in`; current Mathlib: `Nat.card` / `Nat.primeFactorsList` /
  `∑ … ∈`). Verified by running samples (request → assembly → assertion) in the installed Sage and the kernel's
  Python, compiling the Lean entries with each workspace; a failing entry is not used. Rebuilt by the syntax-card
  hooks (start, update checkers' pass, Mathlib update). Python refuses what sympy cannot do (F_{p^k}, Z[i], curves,
  number fields): the model writes it rather than wrong code.
- **Generation**: (1) the stored best version of the intent, as is — « Réécrire » included (the user wants one
  syntax per request); (2) fully covered → assembled, no model; (3) S-AB template shortcut; (4) model: the
  catalogue's constructions are a mandatory prefix, enforced after (the model's redefinitions of those names are
  dropped), temperature 0 + seed, ONE pinned model per language chosen by measured run success on Calcul (sticky:
  replaced only when another is ≥ 0.15 better over ≥ 5 runs, or after two misses), the race of D35 only as fallback;
  earlier failing versions are shown as « do not repeat ». Output canonicalized (imports on top, deduplicated,
  ordered; missing imports / conventional objects / single-line definitions of earlier cells added by static
  analysis). Rejected: temperature 0 alone (providers still differ; the race picks a different model); caching by
  text (F_125 vs GF(125)).
- **Keep the best** (`research/recipes.py`, schema 2, S-AB file migrated with a backup): per intent, every version
  and its runs; ranking ran OK > approved > ≥ 30 % faster > older (no flapping on timing noise); a version that
  only failed is never preferred again. « Autre version » (cell menu, small) asks the model on purpose for a
  different version (temperature 0.7, another seed); it replaces the best only when it ranks strictly higher.
- **Auto-fix**: a run error that is a missing name (`np`, a conventional `F9`, a definition of an earlier cell) is
  fixed deterministically first; only other errors go to the model (D35 policy unchanged: approval rules, ≤ 3).
- UI: « Reconnu : corps fini F₁₂₅ = F_{5³} · … » under the request; a wrong request (F_12) is said there, without
  code; the head shows « construction vérifiée » / « meilleure version ». Measured (docs/PERFORMANCE.md, CALCUL.md
  §3.6): 31 typical requests in two notations each → 31/31 byte-identical after « Réécrire » and across notations,
  29/31 without any model (Sage), all 31 Sage cells ran; analysis + assembly ≈ 2 ms.


## D37 — Lean kept warm for intermediate attempts; a fresh strict Lean still decides (user request, 2026-11-22, S-AE)
- Request (TODO B10): every check restarted Lean and reloaded Mathlib (2–3.5 s warm cache, 10–34 s cold, ~3.4 GB);
  « plus rapide sans perdre la fiabilité ».
- Decision: Lean's own language server (`lean --server`, shipped with every toolchain, measured on v4.9.0-rc1 and
  v4.36.0) kept per workspace in use, Mathlib loaded once, in the same `leansandbox` as every Lean (D28; `untitled:`
  document, no `lake`, gate before anything is sent). Opt-in per caller: only a job's intermediate checks
  (`RunnerIO.check`) use it; everything else stays fresh by default.
- Reliability rules: a warm acceptance of a strict check is re-checked by a fresh `lean --json`, whose verdict and
  axioms are returned (the warm Lean can only make attempts fail faster); the first warm verdict of each worker and
  one in 20 afterwards are audited fresh; any verdict disagreement keeps the fresh verdict and sets the warm Lean
  aside for that workspace (health row, « Réparer »); each attempt runs after a reset of the document to the header
  (no snapshot of a previous attempt reusable); timeout / cancel / crash kill the worker; other headers, busy or
  loading worker → fresh. Messages are mapped to `lean --json` lines: identical messages, positions, verdicts and
  model feedback on the 21 test attempts, both Lean versions (real-Lean test).
- Resources: lazily started (the first check of a job runs fresh meanwhile), ≤ 1 per workspace, ≤ 2 workspaces,
  stopped after 10 min idle (setting), on workspace change, when switched off, at shutdown; a warm check holds a
  `lean` slot. Setting « Garder Lean prêt d'avance » (default on), health row « Lean prêt d'avance ».
- Rejected: leanprover-community/repl (not shipped with the toolchains, would need a build per Lean version and
  a network download; the LSP route works on both versions); a new document per attempt (each document is a new
  file worker that reloads Mathlib); `textDocument/waitForDiagnostics` (spins forever on v4.9 when the request
  overtakes the edit); a header-only reset document (v4.9 re-imports Mathlib whenever the first edit position is
  not strictly after the header: the worker's prefix includes the first character after the header); trusting a
  warm acceptance; early abort of streamed answers (B11: designed in docs/BRAIN.md §17, not built — a cut is
  rarely certain and a wrong cut loses a proof).

## D41 — The conductor: Claude directs each request within 1 USD, the next best model otherwise (user request, 2026-11-22, S-AI)
- Request: « Claude orchestre tout de façon optimale » — reads the problem, splits it into tasks, picks the model of
  each task from the ranking, receives the outputs, corrects and optimises the errors, Madalean executes; under
  1 USD per request; the second best model when Claude is unavailable; each model reads the rules of the tools it
  uses; prompt compaction; costs, durations and slowness measured, not fixed; « tu ne casses rien ».
- User's answers: conductor chosen per decision among Haiku / Sonnet / Opus 5.5 from difficulty, budget left and
  measured data; 1 USD per request, then « Plafond atteint : continuer avec Claude (+0,50 $) ? » (yes: +0.50; no:
  without Claude); Claude reviews plans, failures and the final coherence only; on by default with a Claude key,
  switch in Réglages › Modèles, cost shown on each request; without Claude the best measured model directs, and with
  no capable one the pipeline runs unchanged.
- Decision (docs/BRAIN.md §18): a contained hook of the pipeline (`pipeline/conductor_hook.py`, ≈ 25 lines in
  `runner.py`) — plan written beside the first stage (the stages wait ≤ 25 s for it), structured JSON validated by
  code; model per task chosen by the conductor AMONG candidates the code ranks (router score − measured latency −
  cost penalty for paid models); corrections only when Lean rejects a statement or no proof is found (≤ 3 each, the
  3rd on Opus), each judged by Lean like any other; final coherence check reported, never overwriting. Conductor
  choice by a utility (posterior success per decision kind, difficulty, cost vs budget left, measured latency),
  fallback chain Claude → Claude → free → none on 429 / timeout / refusal / invalid JSON. Request cap = the job's
  spend scope cap (replaces the per-proof cap for that job; the monthly cap always wins). Tool rule cards (Lean card
  verified by S-AB's syntax catalogue, Madalean conventions, Sage/Python, LaTeX, explanation) compacted per role and
  request: a stable versioned block before the cache breakpoint, the request's rules after it.
- Rejected: Claude reviewing every output (cost × 5, slower; Lean already judges proofs); letting the conductor
  write proofs itself before the tournament (the free provers and the S-M reinforcement already do it; Claude
  corrects the closest failed attempt instead); assigning paid models to proofs from the plan (unbounded agent
  tokens: Claude stays the tournament's final reinforcement within the same cap); the `anthropic` SDK (not a
  dependency; every request keeps going through `brain.net.Http`: local-mode enforcement, key-host binding); a
  fixed conductor model (measured: an unmeasured Opus otherwise beat a measured Sonnet on latency); caching the
  whole request with the top-level breakpoint (measured: 2 104 of 2 108 tokens written at 1.25×, never read again);
  automatic splits into lemmas (D31: the user decides — the plan only suggests them); a free-model plan skipped
  when Claude is declined (the user's answer lists « cap declined » among the cases where the next best directs).
- Measured (docs/PERFORMANCE.md « Chef d'orchestre »): demo replay — same worker calls, +2 conductor calls, ≈ +2 s
  when everything works; a rejected statement or a failed proof is corrected instead of a failed job. Real API
  (11 calls, 0.085 USD in total): plan 7.5–10.4 s (Haiku 0.001 $, Sonnet 0.009–0.015 $, Opus 0.029 $), correction
  2.9 s (0.005 $), final check 3–4 s (0.0002–0.006 $); stable prefix read from the cache on the next call (1 858 of
  2 108 tokens).

## D42 — Calcul: « Expliquer les étapes du calcul », intermediate facts computed by Sage (user request, 2026-11-22, S-AJ)
- Request: « une explication des étapes de calculs est nécessaire dans Sage » — how the result of a cell is
  obtained, as a mathematician would do it by hand, ending on the cell's actual result.
- Decision (docs/CALCUL.md §3.7): a third mode `steps` of the existing « Expliquer » service (`research/explain.py`,
  fast short-text path of BRAIN.md §15, streamed as `calcul.steps`, cached in memory). Intermediate results are not
  left to the model: deterministic step probes (`research/steps.py`) keyed by the recognized operation (S-AG intent,
  else the code's last expression) — factor, integrate, roots, det, solve — compute and check the key quantities in
  the cell's own kernel (product of irreducible factors == input, F' == f and F(b) − F(a), f(r) == 0 and minimal
  polynomials, triangular form and det(P)·∏diag, substitution / A·x == b and kernel dimension); the model gets them
  as facts to use as is, the UI shows each with « vérifié par Sage » / « calculé par Sage ». No probe → the
  explanation is shown as « Explication sans vérification » with the reason.
- Safety: the probe is Madalean's fixed program; the cell's code enters it only as a JSON string and runs only if
  the cell itself may run (user code, or model code approved on this host, D35), from a device allowed to execute,
  never while the notebook runs. Evaluated in a copy of the kernel's namespace, outside the history (`_`, names and
  execution count unchanged). The recomputed value must equal the cell's output, else the facts are dropped.
- Rejected: asking the model to write the verification code (model code would need its own approval each time and
  could check the wrong thing); a probe for every operation (kept to the five with a clear by-hand derivation; the
  others get the method, unverified); Sage's own step-by-step (none exists in Sage for these operations); a cache
  on disk (the answer depends on the model and language; memory is enough for a session).

## D43 — One top bar: the logo is the menu, « Projet › Dossier » switcher, status panel; Enter sends; outside click closes; autosave everywhere (user request, 2026-11-22, S-AK)
- Request: « le logo est à la fois le menu déroulant et le retour à l'accueil ; les boutons du dessous ne sont pas
  nécessaires ; menu déroulant sur le nom de projet ou dossier, en texte complet ; le nuage de modèle affiche les
  ressources matérielles et les tokens ; simple mais complet, sans redondance ; Entrée pour lancer, Maj+Entrée pour
  aller à la ligne ; un volet se ferme en cliquant ailleurs ; enregistrement automatique de chaque modification ».
- Audit first (docs/UI.md §14.1, 20 findings): the same destinations were reachable from up to four places (☰, rail,
  rail bottom links, phone bottom bar, top bar), the mode switch and Réglages were duplicated, the project select
  was duplicated and truncated, the activity drawer repeated the Activité screen, the dossier list hid behind ☰
  below 1024 px, the « Qui reçoit quoi » pill was a cut sentence.
- Decision — **one top bar** `[logo ▾] [Projet › Dossier ▾] … [Chercher] [état]` + a **project bar** of the
  project's sections on project screens; no rail, no drawer, no bottom bar. The **logo menu** holds every other
  destination (Accueil first; Activité, Bibliothèque, Glossaire, Carnet, Aide, Réglages; Apprendre / Recherche;
  the bar toggle) and shows the project's sections only when the bar is not on screen. A second click on the logo
  while the menu is open goes home (the user's « à la fois menu et retour à l'accueil ») — a single click must open
  the menu, since home is also its first, pre-focused entry. The **context switcher** is the only project / dossier
  chooser: full names (two lines, tooltip), projects beside the highlighted project's dossiers (search, status,
  lemmas). The **status button** merges the privacy pill and the activity drawer: mode and model per running job,
  CPU / RAM / GPU / VRAM, tokens and cost (this request, today, this month), running jobs with Stop, links.
  Rejected: keeping the rail on desktop (it duplicated the bar and the switcher, and forced a different model on
  tablets); a hamburger next to the logo (two buttons for one menu); a separate dossier crumb (two switchers).
- **Tokens of every call** (`brain/usage.py`): the provider clients (and the demo's scripted brains) record tokens
  per day / provider (persisted, `model-usage.json`, 62 days) and per request (`slots.CURRENT_JOB`, the 200 most
  recent, in memory); USD comes from the spending ledger for paid calls (spend.py). `GET /api/usage` adds CPU (two
  reads of /proc/stat), RAM (/proc/meminfo), GPU (the existing nvidia-smi monitor, polled only when its snapshot is
  older than 4 s). The UI polls it every 3 s **only while the panel is open**. Rejected: pushing resources on the
  WebSocket (every client would pay for it all the time); psutil (not in the installed env).
- **Enter sends, Shift+Enter is a new line** in every field that sends / launches; Calcul code cells: Enter runs,
  Shift+Enter keeps the indentation, Tab / Shift+Tab indent (Escape leaves the cell: no keyboard trap). Exceptions on
  purpose: long-form editors (article, note body, text cells, profile, BibTeX paste, experiment code, plan node
  fields) keep Enter = new line. Never while an IME composes. On touch-only screens Enter stays a new line and the
  button sends (no Shift+Enter on on-screen keyboards). One rule in `lib/ui/enter.ts` + the CodeMirror keymap.
- **Outside click / Escape** close every non-modal panel through one action (`lib/ui/dismiss.ts`): a stack so Escape
  closes the innermost only, focus back on the opener, events inside a modal dialog opened from a panel ignored.
  Native dialogs already close on backdrop click / Escape; their drafts live in the screen; the plan node editor
  saves on close instead of discarding.
- **Autosave** (`lib/ui/autosave.svelte.ts`): debounce, flush on blur / in-app navigation (router hook) / hidden or
  closed page / unmount, retry with backoff up to 30 s, 409 = conflict (text kept, no retry). New: dossier title
  in place, statement while editing, Calcul cells while typing, experiment code, project title / description,
  profile; notes and article gained flush-on-leave. Removed: rename dialog, « Enregistrer seulement », Profile's
  « Enregistrer », plan « Enregistrer ». Kept explicit: actions that are not saving (Retraduire, Exécuter, Publier,
  Compiler…) and API keys (checked and tested, never autosaved).


## D44 — Guided install (one engine, terminal + graphical `.run`), reuse of system SageMath / TeX Live, showcase site, stable release names (user request, 2026-11-22, S-AL)

- **Request** (French, summarised): a more attractive site with the author's contacts on the site and in the apps; at
  install time Madalean must guide the user to the best tools for the machine (Sage, local model or none, LaTeX,
  Python…), check what is already there, help install the rest, and guide the first configuration — all documented on
  GitHub Pages. Answers: contacts = README's; assistant = terminal + first opening in the browser (the in-app part is a
  later session); existing system tools = proposed, the user chooses; site = showcase home + academic guide/manual.
  Then: a graphical self-extracting `.run` installer opening a wizard in the browser; the site shows no version and
  links to the latest server (.run, sources) and client (AppImage, APK) files.
- **One engine** `madalean/deps/assistant.py` (stdlib only, Python ≥ 3.8, runs under the system `python3` before
  Madalean's own environment exists; after step 3 with Madalean's Python when there is none): `detect()` (CPU, RAM,
  disk, NVIDIA GPU + VRAM + CUDA through `nvidia-smi --query-gpu`, SageMath + its `sagemath` Jupyter kernel, TeX Live
  year + fontspec, tectonic, Pythons, elan toolchains, Ollama, Tailscale, bubblewrap, models in ~/models, prefix
  state), `recommend()` (plan + reason per item, FR/EN, options marked unavailable when incompatible, advice with the
  exact package command — never run), `validate()`, `shell_vars()`, `record()`/`apply_pending()`. Front-ends: the
  terminal assistant of `install.sh` (interactive only when stdin and stdout are terminals and neither `--yes` nor
  `--plan` is given — `--yes`/non-TTY = the 2.0.0 defaults, unchanged, checked by a test), the graphical installer
  (`packaging/installer/server.py`), and `GET /api/setup` (host only, read-only) for the future in-app wizard.
  `install.sh` reads the plan as `KEY=value` lines matched against fixed allow-lists (no `eval`).
- **Plan items** and defaults (`--yes`): models `all` (≈ 15 GB; `prover` ≈ 5 GB; `none`), llama.cpp `auto` (CUDA when
  the driver allows) / `cpu`, Sage `later` (own copy on first use) / `now` / `system`, TeX `own` / `system`, workspace
  `import` / `build` / `skip`, mode `auto` / `online` / `local`. Recommendations: all models with ≥ 10 GB VRAM and
  ≥ 15 GiB RAM, prover only with ≥ 7.8 GB VRAM (24k context, q8_0 KV ≈ 7.0 GiB, config.py), otherwise « pas de modèle
  local conseillé » + CPU llama.cpp (23 MB instead of 660 MB) + mode `online`; system Sage when ≥ 10.0 AND its kernel
  exists; tectonic always (TeX Live stays the automatic fallback); build lean-current when no workspace and enough
  disk.
- **Reuse of system tools** = two settings, `sage_source` (auto | own | system) and `tex_engine` (auto | tectonic |
  system), published to `madalean.deps.preference()` whenever settings load or change, read by
  `sagebridge.find_kernelspec` (system = system kernel dirs only, own = prefix only, auto = prefix first — the 2.0.0
  behaviour) and `export._engines` (system = TeX Live first, tectonic last; tectonic = tectonic only). The S-AC/S-H
  sandbox is unchanged for both: the Sage launcher (env allow-list, private home, rlimits, bubblewrap with `/`
  read-only) and `tex_confine` (system TeX trees mounted read-only) already applied to system binaries. The install
  choices live in `<config>/setup.json` (schema `madalean-setup/1`: detected, recommended, plan, result, apply,
  applied, history ≤ 10) and are applied **once** at first start (`applied` flag; re-armed only when a later install
  uses a different plan, so a repair run never overrides what the user changed in the app).
- **Graphical installer**: `Madalean-installer.run` = `packaging/installer/header.sh` (payload SHA-256 + byte offset
  written by `scripts/build_installer.sh`) + an uncompressed tar of `SHA256SUMS` + `madalean-server.tar.gz`. The header
  verifies the whole payload, then `SHA256SUMS`, before unpacking anything; `--check`, `--extract DIR`, `--terminal`,
  `--yes`. With a graphical session and `python3`, a stdlib HTTP server on 127.0.0.1 (random port; never another
  interface) with a 256-bit one-time token in the URL (removed from the address bar by the page), required on every
  API call (`X-Install-Token`), Host header pinned to the loopback address (DNS rebinding), Origin checked on POST,
  strict CSP, no external resource. It streams `install.sh --plan FILE` (steps `==> n/9` → progress bar), offers
  « Réessayer » (install.sh resumes), « Ouvrir Madalean » (xdg-open of the local URL) and stops on « Fermer », or after
  30 min idle while no install runs. Fallbacks: no display/browser → the terminal assistant; no terminal either → the
  default install. Rejected: a Tk/GTK window (python3-tk is often missing, GTK needs bindings), Electron/Tauri for the
  installer (hundreds of MB), makeself itself (an extra tool to vendor; 60 lines of sh do the same, with our checks).
- **Site**: root `index.html` = French showcase, `en/home.html` = English; CSS-only demo (12 s loop, still frames
  under `prefers-reduced-motion`), SVG « how it works », 3 steps, FAQ, author band; `fr|en/about.html` with the
  contacts; footer with author, e-mail, GitHub, licence on every page; download page grouped **server** (`.run`
  recommended, sources/`install.sh`, server archive) / **clients** (APK with QR, AppImage, « un navigateur suffit »).
  **No version number anywhere**; links use `releases/latest/download/<stable name>` when the published release has
  that name, else the `releases/latest` page (v2.0.0 used versioned names: nothing on the live site breaks).
  Size +≈ 30 KiB (no new image: the home reuses the manual's screenshots).
- **Stable release asset names** from 2.0.1: `madalean-server.tar.gz`, `Madalean-installer.run`,
  `Madalean-x86_64.AppImage`, `Madalean-android.apk` (+ `Madalean-android-<abi>.apk`), collected by
  `scripts/stage_release.sh` (build scripts unchanged). The signed channel carries the version; readers never relied
  on names, except the server's GitHub-API fallback (`madalean-<v>.tar.gz`, now also `madalean-server.tar.gz`) and
  `sign_release.sh` (version now read from the archive when the name has none). `make_update_manifest.py`: `.run` →
  kind `installer`, an APK without ABI in its name → `universal`.
- **Contacts** (README's): RANIRIAMANJAKA Antsa, antsa.raniriamanjaka@univ-antananarivo.mg, github.com/raantss18,
  Apache-2.0, version — web About (licence sentence added; phone kept, the user had added it), Android (new About
  screen from the connect screens), desktop shell (About block on the connect screen), site footer + About, README.

## D46 — The conductor corrects Calcul and LaTeX errors; a proof found before « douteux » is kept aside (TODO B16 ter, 2026-11-22, S-AN)
- Request (conductor follow-ups): the conductor of D41 also corrects a Sage / Python cell that fails at run time and
  a LaTeX compilation that fails; a proof the search found while the statement check was still running must not be
  thrown away when the check says « douteux » (or « faux » if the user forces).
- **Calcul** (`research/conductorfix.fix_code`, inside `codegen.transcribe`): order deterministic fixer (S-AG) →
  conductor → the usual pinned Calcul model (D39). The conductor is a new decision `codefix` of `Conductor.ask`
  (Claude tier by utility, free models after, the same cap rules), with the Sage / Python cards and the catalogue's
  canonical constructions as a mandatory prefix. Its code is validated by the installed Sage's preparser before it
  is shown (invalid → counted as its failure, usual model instead), stays model code (approval by hash, D28 / D35,
  same sandboxed kernel, ≤ 3 per request), and a run OK ranks it in the recipes as for any version (origin
  `conductor`). « Corrigé par Claude Sonnet · 0,004 $ » under the cell and in its history. Rejected: the conductor
  BEFORE the deterministic fixer (cost and seconds for a missing `import numpy`); letting a run OK of Claude's code
  count for the pinned Calcul model (it would pin a paid model for every transcription; its success is measured in
  the conductor's own statistics instead); one approval for the request (D35's rule stays exact).
- **Article** (`conductorfix.fix_compile`, `texbuild.trial_compile`): only for a compilation that ran and failed on an
  error without a one-click fix, once per source hash; ONE local find → replace, checked by compiling the project with
  it in a separate sandboxed build (same engine and confinement, nothing kept), ≤ 3 proposals; offered as a
  `compile_fix` suggestion of the existing panel (accept / refuse) with the conductor and the cost. Rejected: applying
  a fix that compiles (« nothing an AI writes enters the source silently », ARTICLE §3); rewriting whole files (a
  diff the author cannot review); offering an unchecked change; a model for errors that already have a deterministic
  fix (packages, fetch, guard).
- **Budget outside a job**: one spending scope per user request (`calcul:…:<hash of the request>`,
  `article:<pid>:<source hash>`) with the request cap `conductor_cap_usd`; the cap question is a global dialog
  (`conductor.ask` event, `POST /api/conductor/asks/{id}`), 5 min then « no » because a run / compile request is
  waiting (10 min in a job). Closing the dialog answers « sans Claude ». Rejected: reusing the job question
  (`/jobs/{id}/conductor`): Calcul and the article editor have no job.
- **Proof kept aside** (`runner._keep_pending` / `_use_pending`): when the check stops the proof after a proof was
  found (or in the same batch), the proof goes to `dossier.pending_proof` with its statement and index — not
  « vérifiée », not in the library, the job still ends `statement_doubtful|false` exactly as before (D38). « Prouver
  quand même » (`force`) first re-checks it with a FRESH strict Lean (never the warm Lean of D37; axiom probe) and
  records it at once when accepted (library included); refused → the usual search. Any new statement drops it (by
  hand, by the model, by the conductor; a stale one is never used). Rejected: recording it as verified with a
  warning (the user decides on the statement first, D38); re-running the search after « Prouver quand même » (minutes
  for a proof already found); trusting the earlier acceptance without a new check (the workspace or the Lean
  version may have changed).
- Tests: fake brains / kernels / Lean (no paid call), the installed Sage's preparser and Sage itself for a corrected
  cell, the system XeLaTeX for the recompilation check (tests/test_conductor_fixes.py).

## D49 — « Premiers pas »: the in-app first-run assistant, on the host only, resumable, real settings only (user request, 2026-11-22, S-AQ)
- Request: at the first opening on the host, guide the whole starting configuration — tools (installed / missing,
  the system's SageMath or LaTeX vs Madalean's copy, recommended choice with its reason, install / repair with live
  progress), local model yes/no and which one with its download size, API keys one card per provider (where to get
  it, free tier, what it is good for, paste + « Tester », never autosaved, host only), Hugging Face for Goedel-Prover,
  Claude as conductor and its caps, modes (Local / Auto / En ligne; Apprendre / Recherche), automatic vs manual
  behaviours, pairing, a final checklist; each step linked to its manual page; skippable, resumable, « Plus tard »
  with a reminder on Home.
- Decision (docs/UI.md §15): a **full-screen route** `/premiers-pas/:step?` of ten steps (welcome, tools, local,
  keys, hf, claude, modes, auto, pair, done) built from S-AK's pieces — Réglages' `KeyForm` for keys (explicit
  save, then test; « Tester » again for a saved key), Réglages' `Devices` for pairing (one pairing flow), the
  existing `PATCH /api/settings` / `POST /api/deps/{c}/install` (+ `deps.progress`) / `GET /api/providers`. New
  files only (`screens/setup/`, `lib/setup/`), five one-line hooks (App, routes, logo menu, Home, Réglages).
- **When it opens**: on the host's Home while `wizard_done` is false and the server says `auto`. `auto` is false
  once finished or put off, and on a server that **started with the user's dossiers already there** (an update
  from 2.0.0: `wizard_done` was always false in 2.0.0 settings files, so opening it over existing work would
  surprise every current user; the Home card offers it instead). The demo's seeded examples do not count, so the
  demo shows it at first start (the e2e global setup marks it finished; its own spec reopens it). Deep links are
  never redirected. Paired devices never see it (no auto-open, no menu entry, no card; host-only API).
- **Progress on the server**: `<config>/first-run.json` (`madalean-first-run/1`: step, visited, models, completed,
  reminder) through `GET`/`PATCH /api/setup/wizard`; « Plus tard » = the existing `wizard_done` setting;
  « Terminer » = `completed` (+ `wizard_done`). The Home card stays until finished, « Ne plus afficher » hides it;
  the assistant stays in the logo menu and Réglages. Rejected: localStorage (per device: the host's other browser
  would start again), a new Settings field for the step (settings are user options; progress is not one).
- **Small endpoints added** (all host only, tested in `tests/test_setup_wizard.py`): `POST /api/setup/reuse` — the
  `sage_source` / `tex_engine` choice checked against the machine before it is saved (« system » needs a `sagemath`
  kernel outside the prefix and, when known, SageMath ≥ 10.0; TeX « system » needs XeLaTeX or LuaLaTeX; « tectonic »
  needs the prefix's tectonic), since PATCH /api/settings only checks the enum and a wrong choice silently leaves
  Calcul or the PDF export without an engine; `POST /api/setup/models` (+ `/cancel`) — the missing GGUF files of the
  chosen set downloaded exactly as install.sh does (`scripts/download_model.sh`, pinned revisions, SHA-256, resumable;
  the script now honours `MADALEAN_MODELS_DIR`), refused in Local mode and in the demo, progress as `setup.models`
  events; `GET /api/setup` gained `recommended` (the install engine's plan and reasons for this machine), `models`
  and `wizard`. Rejected: downloading models through the update manager (it only replaces installed models);
  a « remove SageMath » button (out of scope; the manual explains the manual removal).
- **Real option names only** (madalean/config.py): `sage_source`, `tex_engine`, `mode`, `language`, `hf_goedel`,
  `conductor`, `conductor_cap_usd`, `claude_reinforce`, `claude_cap_proof_usd`, `claude_cap_month_usd`,
  `experiments_auto`, `parallel_stages` (no switch elsewhere until now), `lean_warm`, `pause_after_translation`,
  `check_updates`, `updates_auto`; the « +0,50 $ » approval at the request cap is the conductor's runtime question
  (D41), explained, not a setting.
- The manual's « verify after integration » notes of S-AL are resolved: `sage_source` / `tex_engine` are shown and
  changed in « Premiers pas › Outils » (reachable from the logo menu and Réglages); the components with install /
  repair are in « Réglages › Système » and « Premiers pas › Outils »; no « remove SageMath » button; with
  `tex_engine = system` the export tries the system's XeLaTeX, LuaLaTeX, then tectonic last.
