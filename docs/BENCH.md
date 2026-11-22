# BENCH — measuring Madalean 2.x (« Mesurer », strategy 2.1 item 2, DECISIONS D53)

What Madalean proves, how fast and at what cost, measured by the application's own pipeline. The 1.x hardware
benchmark of the local model (llama.cpp settings, VRAM, tokens/s) stays in the root `BENCH.md`; proof-time profiling
of real jobs is `docs/PERFORMANCE.md` (`scripts/perf_report.py`).

```
madalean bench sets                                   # sets, pinned sources, licences, cache state
madalean bench fetch minif2f | putnam                 # download at the pinned commit (cache, outside the source tree)
madalean bench check SET --workspace W [--split valid]  # which statements does this Lean / Mathlib accept
madalean bench run SET --strategy S [options]         # run or resume; free / no-model only unless --paid-budget USD
madalean bench report RUN_DIR… [--publish]            # print summaries; --publish copies them to bench/results/
```

(`python -m madalean bench …` from a source checkout.)

## 1. What is measured

For each problem the runner (`madalean/bench/runner.py`):

1. puts the **formal statement** into a dossier, exactly as the statement editor holds it (`theorem … := by sorry`
   with its header);
2. submits a `proof` job to the application's own **orchestrator** (same slots, same `pipeline/runner.py`:
   Mathlib-first, tournament, conductor hook — nothing is re-implemented), with « Prouver quand même » so that no
   statement check asks a model whether the statement is true;
3. takes the proof the pipeline recorded and judges it **again**: the file must start with the statement's own
   preamble and contain the theorem signature exactly as given (comments and whitespace aside), and a **fresh strict
   Lean** in the workspace (`lean --json`, never the warm Lean) must accept it — `#print axioms` shows only
   `propext`, `Classical.choice`, `Quot.sound`; no `sorry`, no `axiom`, none of the forbidden constructs of the
   application (`leancheck.judge`, D28 gate).

Only step 3 makes `verified: true`. A proof the pipeline recorded but the fresh check refuses is a row
`rejected` (never seen in the real runs below; covered by a test).

**Statements that do not compile** in the chosen workspace (the set targets another Mathlib) are found before any
proof search — batches of 40 statements in one file, each in its own `section`; every statement touched by an error
of its batch is compiled again alone and that verdict decides — and are reported as `statement_error`: they are
neither attempted nor counted as failures.

Problems never help each other: the run's private library offers nothing and records nothing.

## 2. Strategies (`--strategy`)

| Strategy | Pipeline settings | Models |
|---|---|---|
| `mathlib` | Mathlib-first only (RAG candidates + templates + `exact?`, D38/S-K), no adaptation by a model | none (a brain with no model) |
| `tournament` | the application's default online chain: Mathlib-first, then the tournament (round 0 best model, then races) | free online models |
| `conductor` | `tournament` + the conductor hook (D41) | free conductor; Claude only with a paid budget |
| `single` | agent loop of one model (`--model provider:model_id`), no Mathlib-first, no tournament | that model |
| `goedel-local` | Goedel loop on the local GGUF (uses the GPU; never run by default) | local |
| `certificate` | reserved for S-AT (« Sage calcule, Lean vérifie »): refused until the strategy is in the pipeline | — |

Options: `--providers a,b` (model set), `--attempts` (per model in a tournament), `--rounds`, `--contestants`,
`--time-per-problem SECONDS`, `--time-budget MINUTES` (whole run), `--jobs` (problems in flight; the pipeline's
slots — online 3, lean 2 — bound the real parallelism), `--no-mathlib-first`, `--sample N --seed S`, `--split`,
`--id`, `--limit`, `--out DIR`, `--publish`.

## 3. Cost discipline

- **Default: no paid call is possible.** The engine reads keys through `ReadOnlyKeys`, a filter over the
  application's key store (`madalean.keys.KeyStore`, the user's `keys.json` / keyring, read-only): providers marked
  paid in the catalogue (`anthropic`, `huggingface`, `openai`, `deepseek`) have **no key** for the run; Claude
  reinforcement, Goedel online and the conductor's Claude are off; the spending caps are 0.
- `--paid-budget USD` gives the paid providers their keys and sets the engine's own ledger caps (month cap = the
  budget, in the run's private `brain-spend.json`): the engine refuses a call whose upper-bound estimate would pass
  the cap, before sending anything (`spend.Ledger.check`). The runner checks the total again before each problem and
  stops the run (`stop: paid_budget`).
- If a row ever shows a cost without a paid budget, the run stops at once (`stop: paid_call_without_budget`,
  exit code 3).
- Cost per row = max(list-price cost of the tally of every call of the job, `usage.py`; real usage recorded by the
  ledger, `spend.py`). Free and local models cost 0. « Free » means what the application means: the providers'
  free tiers (a key with billing enabled at a provider is that account's business — check your provider console).
- Tokens of a call that was cancelled (problem timeout) are not counted: the provider never reported them.

## 4. Isolation

A run works in `<run dir>/state/` (its own configuration and cache directory). It never writes to
`~/.config/madalean`, never talks to the running server, never asks Ollama for anything (`ollama` off, embeddings
off: the Mathlib search is lexical only — the application may also use embeddings), never loads the local GGUF
unless `goedel-local`. To start as the application would, it **copies** (reads) the model catalogue, the measured
rankings and the Mathlib search index of the user's Madalean (`--no-seed` to start from the seed catalogue and
build the index). Lean runs in the built-in workspaces, read-only.

## 5. Problem sets

| Set | Source (pinned) | Licence | Upstream Lean | Content |
|---|---|---|---|---|
| `smoke` | `madalean/bench/smoke.py` | Apache-2.0 (Madalean) | — | 20 own statements over 11 branches; a test of the harness, not a benchmark |
| `minif2f` | `yangky11/miniF2F-lean4` @ `5746b7d6c47855ce1294bed87329618ff7f1bc31` | MIT | v4.24.0 | 244 valid + 244 test, one file per problem |
| `putnam` | `trishullab/PutnamBench` @ `a635813f5edf297d928f9bd5ef8324a26bdde09c` (`lean4/`) | Apache-2.0 | v4.33.1 | 672 Putnam problems 1962–2025 |

- **Nothing is vendored.** `fetch` downloads `codeload.github.com/<repo>/tar.gz/<commit>`, keeps only the problem
  files and the licence file (regular files matching the set's pattern; no link, no path outside), under
  `~/.cache/madalean-bench/sets/<set>-<commit12>/` (`MADALEAN_BENCH_CACHE` or `--cache-dir`), and writes
  `source.json`: repository, commit, licence, archive SHA-256, **content SHA-256** of the kept problem files.
  The content hash is pinned in `madalean/bench/sets.py` (miniF2F `c5e5ab3d…b8ce73`, PutnamBench `597367f4…bda9fb`)
  and checked at fetch and at every load: a changed upstream or a modified cache is refused.
- Both licences allow redistribution; the sets are still not copied into the repository (size, and a set that moves
  with its upstream is a different benchmark). The licence text is kept beside the cached files.
- **PutnamBench asks not to publish proofs** (« Do not include proofs as confirmation in any public setting »):
  verified proofs stay in the run directory (`proofs/`, never committed); published summaries hold counts and
  problem ids only.
- PutnamBench « answer » problems (`abbrev …_solution : T := sorry` followed by the answer in a comment): the
  answer is filled in, i.e. the task is « prove with the answer given ».
- The older `data/minif2f.jsonl` (244 test statements from Goedel-Prover's dataset, shipped since 1.0) is not used
  by the benchmark.

Statements accepted by each workspace (`madalean bench check`, 2026-11-22):

| Set | lean-prover49 (Lean v4.9.0-rc1, Goedel's Mathlib `2f65ba7f1a91`) | lean-current (Lean v4.36.0, Mathlib `fc4f59e577fe`) |
|---|---|---|
| smoke | 20 / 20 | 20 / 20 |
| miniF2F valid | 240 / 244 (4: `π` ambiguous between `Real.pi` and `Nat.Primes` counting) | 244 / 244 |
| miniF2F test | 241 / 244 | not run |
| PutnamBench | 649 / 672 | 636 / 672 |

## 6. Files of a run

Run directory (default `~/.cache/madalean-bench/runs/<set>[-split]-n<count>[-seed<S>]__<config>__<workspace>/`):

- `run.json` — configuration, selection, source; a different set / configuration / problem list is refused
  (budgets may change between a run and its resume).
- `statements.json` — `{ok: [ids], bad: {id: first Lean error}}`.
- `rows.jsonl` — one row per problem, appended (fsync) when it ends:
  `id, set, split, config, workspace, status, verified, attempts, wall_s, lean_s, verify_s, tokens_in, tokens_out,
  model_calls, cost_usd, model` (who found it: a model key or `mathlib:<lemma>`), `found_by` (mathlib | agent |
  goedel…), `models` (every model called), `axioms, proof_sha256, error, ts`.
  `status`: `verified` | `failed` | `timeout` (its own time limit) | `rejected` (the fresh check refused the
  pipeline's proof) | `statement_error` | `error` (infrastructure; redone on resume) | `unfinished` (cut by the
  run's time budget; redone on resume).
- `proofs/<id>.lean` — verified proofs only.
- `summary.json` — `set, config, strategy, date, madalean, commit, workspace, lean, mathlib, source, selection
  {split, set_size, sample, seed, count}, budgets, selected, attempted, statement_errors, solved, solved_ids,
  solved_without_model, rate, complete, stop, by_status, median_wall_s_solved, median_wall_s_all,
  median_lean_s_solved, wall_s_total, elapsed_s, attempts_total, tokens_in, tokens_out, model_calls, cost_usd,
  cost_per_verified_usd, paid, found_by, models`. `attempted` excludes `statement_error` and rows that are not
  final.

**Resume**: run the same command again; final rows are kept, the rest is redone. **Determinism**: problems are
sorted by id; a sample is `random.Random(seed).sample` over the sorted ids; problems are scheduled in a
seeded shuffled order (the same at every run), so a run cut by its time budget attempted an unbiased sub-sample. Model
answers are not reproducible (online models, sampling without a seed), nor is their availability (free quotas).

`bench/results/*.json` are published summaries (committed); the site page « Mesures » (`site/madasite/measures.py`,
`fr|en/measures.html`, linked from the footer) is generated from them, and the manual page `measures` explains the
benchmark in the application's help.

## 7. Results of 2026-11-22 (Madalean 2.0.3.dev0, commit 01c8c83 + this branch)

Machine: laptop, 16 threads, 30 GB RAM; workspace `lean-prover49`. No paid call (ledger empty, cost 0 on every row).

| Set | Selection | Strategy | Verified / attempted | Median time (verified) | Cost per verified proof | Found by |
|---|---|---|---|---|---|---|
| smoke | all 20 | `mathlib` (180 s) | **15 / 20** | 4.5 s | 0 $ (no model) | Mathlib × 15 |
| smoke | all 20 | `tournament` (180 s, 3 attempts, 1 round) | **18 / 20** | 10.9 s | 0 $ (free) | Mathlib alone × 15, nemotron-3-ultra × 3 |
| miniF2F valid | 50 of 244, seed 1 | `mathlib` (180 s) | **4 / 50** | 4.6 s | 0 $ (no model) | Mathlib alone × 4 |
| miniF2F valid | same 50 | `tournament` (120 s, 3 attempts, 1 round, 4 jobs) | **19 / 50** (38 %) | 68.5 s | 0 $ (free) | Mathlib alone × 4, Mathlib-first with a short proof by a model × 6, nemotron-3-ultra (NVIDIA NIM × 7, OpenRouter free × 2) |
| PutnamBench | 30 of 672, seed 1 | `mathlib` (180 s) | **0 / 28** (2 statements not compiling on Lean 4.9) | — | — | — |

Details: the smoke tournament run made 11 model calls (28.7 k tokens in, 24.2 k out) in 5 min 7 s of wall clock; the
miniF2F tournament run made 50 completed model calls (120 k tokens in, 108 k out), 252 recorded attempts, 21 min
14 s of wall clock, 31 problems stopped by the 120 s limit; the Mathlib-only runs took 62 s (smoke), 103 s (miniF2F)
and 64 s (PutnamBench). The four miniF2F proofs found without a model are `exact rfl` on closed arithmetic, found by
`exact?`. Only one free model family answered in these runs (nemotron-3-ultra through two providers); the other
free providers' models were not picked by the ranking or were unavailable. The PutnamBench run overlapped the
miniF2F tournament run on the same machine (Lean contention may have lengthened some of its attempts).

What these numbers show: the harness works end to end on real Lean and real free models; the no-model Mathlib
search closes textbook facts (15 of 20 smoke statements) but few competition problems (4 of 50 miniF2F, 0 of 28
PutnamBench); free models take the same miniF2F sample from 4 to 19 of 50 at zero cost, within two minutes per
problem.

What they do **not** show: an official miniF2F or PutnamBench score (samples of 50 / 30, validation split, minutes
per problem, a handful of attempts — published systems report thousands of samples per problem); the strength of
Goedel-Prover locally or of Claude (not run: no GPU use, no paid call in this session); natural-language
formalisation (statements are given); stability across days (free models' quotas and catalogue change; one run
per configuration, no confidence interval beyond the sample size: ±14 points at 95 % for 50 problems near 50 %).

## 8. Tests

`tests/test_bench.py` (scripted brain, Lean stand-in): only a fresh strict verdict counts, statements that do not
compile are apart, resume, per-problem timeout, paid budget stop and cost accounting, a paid call without budget
stops the run, free-by-default provider filter, statement pinning, safe extraction and content pinning of the
sets, Putnam answers, deterministic selection, the CLI and published summary names.
