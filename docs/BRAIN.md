# Madalean brain — model engine (`madalean/brain/`)

Session S-B. Interface: `madalean/brain/api.py` (unchanged). The server calls exactly:

```python
from madalean.brain import create_brain, create_retriever
brain = create_brain(config_dir, local_runtime_or_None, get_key, settings)   # get_key(provider) -> str | None
retriever = create_retriever(cache_dir)                                        # RAG index under <cache_dir>/rag/
...
brain.update_settings(new_settings)        # after PATCH /settings (extra method)
await brain.close(); await retriever.close()
```

## 1. Modules

| File | Role |
|---|---|
| `__init__.py` | `create_brain`, `create_retriever` |
| `engine.py` | `MadaleanBrain`: `complete`, `run_agent`, `candidates`, `explain` (ranking + reason), `status`, `refresh` |
| `catalogue.py` | providers, models, seed (`assets/seed.json`, from Tontolo via L Katta), refresh every 12 h, Claude model list, Lean bonus |
| `classify.py` | request classifier (port of `moteur.rs::classify`) + role → categories |
| `router.py` | ranking (75 % quality, 25 % reliability, bonuses) and chain composition (`moteur.rs::route/composer`) |
| `state.py` | pauses / quotas / reliability (`moteur.rs::record_attente`), persisted `brain-state.json` 0600 |
| `net.py` | the only HTTP stack: local-mode enforcement, key↔host binding, reachability cache, SSE reader with stall watchdog |
| `guards.py` | loop / rambling guard (`leancheck.detect_loop`, `detect_rambling`, same cadence as 1.x `ChatStream`) |
| `providers/openai_compat.py` | OpenAI-compatible streaming (keyless providers, OpenRouter, Gemini, Groq…, Ollama, local llama-server) |
| `providers/anthropic.py` | native Anthropic Messages API (raw HTTP, see §4) |
| `convo.py` | provider-neutral agent history ↔ OpenAI / Anthropic / text protocol; text-protocol parser |
| `agent.py` | tool loop (`run_agent`), `StopAgent` |
| `prover_agent.py` | `prove_with_agent(...)` and its system prompt |
| `lean_parse.py`, `rag.py` | declaration parser and SQLite FTS5 retriever (+ optional Ollama embeddings) |
| `lean_search.py` | LeanSearch / Loogle clients (`lean_search_online` tool) |
| `leanrun.py` | minimal strict Lean checker (self-test and tests only; the server has its own) |
| `selftest.py`, `rag_eval.py` | manual provider test; retrieval measurement |
| `fake.py` | S-A's scripted brain (not touched) |

Files written: `<config_dir>/brain-catalogue.json`, `<config_dir>/brain-state.json` (both 0600, never contain keys),
`<cache_dir>/rag/<workspace>-<hash>.sqlite`.

## 2. Settings (dict given to `create_brain`, all optional — expose in PATCH /settings)

| Key | Default | Meaning |
|---|---|---|
| `mode` | `"auto"` | ceiling: `"local"` forces *every* call (and status/refresh) to stay on this machine, whatever the call says |
| `paid_first` | `false` | paid providers (Anthropic, OpenAI, DeepSeek) tried first (≤ 2 per chain, free ones follow). Otherwise a paid model is used only when chosen (`prefer` / `models[role]`) |
| `models` | `{}` | `{role: "provider:model_id"}` preferred model per role (`"auto"` = router) |
| `max_parallel` | 3 | simultaneous online requests (matches the orchestrator's `online` slots) |
| `max_chain` | 5 | online models tried per answer before the local fallback (one extra round of untried free models if all fail) |
| `agent_max_steps` / `agent_max_seconds` / `agent_max_tokens` | 24 / 900 / 600 000 | agent budgets (tokens = generated + uncached prompt) |
| `online_search` | `true` | offer `lean_search_online` to the prover agent (never in local mode) |
| `refresh_catalogue` | `true` | 12 h background refresh of the free catalogue (never in local mode) |
| `ollama` | `true` | use models of a running Ollama (127.0.0.1:11434) |
| `anthropic_thinking` | `true` | adaptive thinking, summarised, streamed as `thinking` chunks |
| `anthropic_effort` | `{}` | per role override; defaults prove/formalize `high`, explain/assistant `medium`, understand/route `low` |
| `anthropic_fallbacks` | `true` | server-side refusal fallback (`fallbacks: "default"`, beta `server-side-fallback-2026-07-01`) on Opus 5.5 / Sonnet 5.5 / Fable |
| `local_native_tools` | `false` | local llama-server gets OpenAI `tools` (needs `--jinja`); default is the text protocol |
| `stall_online` / `stall_local` | 90 / 180 | seconds without a byte before a stream is abandoned |
| `embeddings` | `true` | (retriever) semantic re-ranking when Ollama has an embedding model |

`_endpoints` (`{provider: base_url}`) exists for tests only: never expose it (it re-binds where keys go).

`complete(..., extra=...)`: passed through to OpenAI-compatible **local** servers (Goedel sampling: `top_p`, `seed`,
`cache_prompt`…); for online OpenAI-compatible models only `top_p/seed/stop/penalties`; for Anthropic only `effort`.
`Completion.text` is the visible content (Qwen `<think>` blocks inside `content` are kept raw, as 1.x did; separate
`reasoning_content` is streamed as `thinking` chunks, not put in `text`). Chunks: `text`, `thinking`, `tool_call`,
`tool_result`, `info` (`data.event`: `model`, `switch`, `restart` — drop the partial text, another model starts —,
`loop`, `protocol`).

## 3. How the router decides

Per role → categories: prove → `lean` (+ reasoning), formalize → `lean` (+ math), explain → `writing` (+ math),
understand → `math` (fast), route → `chat` (fast), assistant → classifier on the last user message.
`lean` quality = 0.6·math + 0.4·code + family bonus (`catalogue.LEAN_FAMILIES`: provers +0.30, Claude Opus/Sonnet
+0.15, Gemini Pro / GPT-5+ +0.12, DeepSeek / Qwen3 / Kimi / GLM / gpt-oss-120b… +0.08). Score =
0.75·(0.7·q_main + 0.3·q_second) + 0.25·reliability, ±0.05 fast/slow for fast roles, −0.25 local, +1 paid when
`paid_first`, +100 when chosen. Paused models are skipped. `brain.explain(role, mode)` returns the ranking with
the `why` string, e.g. `lean 0.73, (+0.08: good at maths and code), reasoning 0.56, reliability 0.80, free`.

Chain: ≤ 2 paid, then free online models, then local models (the server's llama-server model for the role first,
then Ollama). `auto`: online first, local fallback; a network error triggers a 1.5 s reachability probe (1.1.1.1 /
8.8.8.8 :443, cached 30 s) and the remaining online models are skipped when offline (no 30 s hangs: connect timeout
4 s). `online`: no local model; clear `BrainError("offline"|"no_model")`. `local`: only loopback models; any
non-loopback URL raises before connecting (checked twice: `Http.check` and an aiohttp `on_request_start` trace keyed on
a context variable set by `complete`/`run_agent`).

Failures (same rules as L Katta): 429 → pause for `Retry-After` / `x-ratelimit-reset*` / « retry in N seconds »;
« daily / quota » → until midnight UTC; 529/503/overloaded → short growing pause; 402 → 12 h; 401/403 on a keyed
provider → whole provider paused 12 h (`key_refused`), on a keyless one → that model only (`needs_key`); 404 /
« does not exist » → model paused 6 h; context too long → next model, no penalty; empty answer (nothing after
removing `<think>`) → failure; refusal → next model. Reliability = (ok+4)/(total+5), decayed ×0.97.
Saving or replacing a provider's key lifts all of that provider's pauses, backoffs and failure counters, its « down »
mark and last error at once, then a quick key test runs (S-AO, DECISIONS D47; `States.clear_provider`,
`Engine.key_saved`, docs/PROVIDERS.md §3).

## 4. Providers

| Provider | API | Key | Notes |
|---|---|---|---|
| LLM7, OVHcloud, Kilo, Pollinations | OpenAI-compatible | none | seed + `/models` refresh (Kilo `isFree`, LLM7 non-`pro`) |
| OpenRouter | OpenAI-compatible | `openrouter` | only `:free` models with zero prompt price |
| Gemini | OpenAI-compatible `generativelanguage.googleapis.com/v1beta/openai` | `gemini` | models from `/models` |
| Groq, Mistral, Cerebras, OpenAI, DeepSeek | OpenAI-compatible | own key | OpenAI/DeepSeek paid |
| Anthropic | native Messages API, `api.anthropic.com/v1/messages` | `anthropic` | `claude-opus-5-5`, `claude-sonnet-5-5`, `claude-haiku-5-5` (paid) |
| Ollama | OpenAI-compatible `127.0.0.1:11434/v1` | none | local, after the server's own model |
| local llama-server | `LocalRuntime.ensure(role)` → base URL (`/v1` appended if missing) | none | `release()` always in `finally` |

Anthropic (per the `claude-api` skill): header `anthropic-version: 2026-10-21`, `x-api-key`; never `temperature`
(400 on that API version); `thinking: {type: adaptive, display: summarized}`; `output_config.effort`; `tool_choice:
auto` only (forced choice is a 400 on Opus 5.5); client tools with `eager_input_streaming: true`, tool input parsed
strictly at `content_block_stop`, invalid input returned to the model as `INVALID_JSON`, tool calls never run on
`max_tokens`/`refusal`; system prompt cached (`cache_control` on the system block + top-level automatic
breakpoint); assistant content blocks (thinking + signature) replayed unchanged, history append-only (never
edited for Anthropic); after a mid-output `fallback` block, earlier thinking/tool_use blocks are dropped and the block
kept (echo rule); optional features (fallbacks beta, effort, thinking, cache_control) are removed and retried once if
the API rejects them. **Deviation from the skill:** raw HTTP through `aiohttp` instead of the `anthropic` SDK, so that
every request goes through `net.Http` (local-mode enforcement, key-host assertion, one stack, no new dependency).

Key isolation: keys are read through `get_key(provider)` at each request, never logged, never persisted, never put
in transcripts; `Http.check` refuses to attach a key unless the URL's hostname equals that provider's host
(`api.anthropic.com.evil.example` is refused).

## 5. Agent protocol (`run_agent`)

Neutral history (`convo.py`) converted per model: OpenAI `tools`/`tool_calls`/`tool` messages; Anthropic
`tool_use`/`tool_result` (all results of one turn in **one** user message; ids sanitised); or the **text protocol**
for models without tools (chosen when a model has `tools=false` or answers « does not support tools »):

```
<tool_call>
{"name": "lean_check", "arguments": {"proof": "simp"}}
</tool_call>
<tool_call name="lean_check">
```lean
exact Even.add ha hb
```
</tool_call>
```

Results come back as `<tool_result name=… id=…>…</tool_result>`. The parser tolerates missing closing tags, raw
newlines in JSON strings, trailing commas, `{"tool":…,"args":…}`, and ignores calls inside `<think>`. Parallel calls
run with `asyncio.gather`; a tool exception becomes an error result; arguments are validated (required keys, basic
types) before the tool runs. Bounds: `max_steps` (model calls), `max_seconds` (wall clock, also caps each call),
`agent_max_tokens`. A provider failure switches to the next model with the same transcript (once the chain is
exhausted, up to two extra rounds of untried free models). A tool may raise `agent.StopAgent(text)` to finish.
Extra keyword arguments of `run_agent` (optional, not in `api.py`): `require_tool="submit"` (the model is nudged twice
when it stops without calling it), `max_tokens_budget`. `AgentResult.finish`: done | max_steps | budget | error.

## 6. Prover agent

`prove_with_agent(brain, retriever, *, statement, workspace_key, check, library_search=None, hint="", on_chunk=None,
mode="auto", max_steps=24, max_seconds=900) -> {code, model, steps, finish, transcript, checks, seconds}`;
`finish`: proved | max_steps | budget | error | gave_up. Tools: `lean_check` (`proof` = tactic block, or `code` =
helpers + theorem; always assembled with `leancheck.assemble_proof`, so the statement cannot change; a whole theorem
passed as `proof` is accepted; tactic blocks are re-indented; `sorry`/axioms/`exact?`… rejected before compiling;
identical code is not recompiled), `search_mathlib`, `read_declaration` (with close names when absent),
`library_search` (server callback), `lean_search_online` (only when `mode != local` and `online_search`), `submit`.
Unknown names in Lean's feedback (incl. Lean 4.9's « invalid field notation ») get a « Note on unknown names » from
the index. The task message contains the statement, the user hint and the top-8 premises of the statement. The
system prompt (in `prover_agent.py`) states the workspace's Lean/Mathlib version, the fixed header, the forbidden
constructs, and a method: plan → look names up → check early → incremental `have`/`calc` → read errors → change
strategy after 3 failures → `submit`. `code` is the best code Lean accepted; the server re-checks it.

## 7. RAG

Index built from the sources compiled in the workspace (`names.source_roots`): theorem, lemma, def, abbrev, instance
(named), structure, class, inductive, alias (incl. `alias ⟨a, b⟩`), opaque, axiom; namespaces/sections/`_root_`,
docstrings, attributes, `variable`s in scope, deprecated flag; names generated by `@[to_additive]` (from `#align`
pairs in 4.9-era Mathlib, explicit names, `attribute [to_additive x] y`, or guessed with to_additive's dictionary;
signature roughly translated and marked as such); names only known from `#align` (2 497 in lean-prover49) are
indexed by name. Popularity prior = how often a name is used in the sources. Search: FTS5 BM25 (name 10, name words
5, doc 1.5, signature 1) over three candidate pools (all concepts in name words, all concepts anywhere, any concept),
re-ranked by concept coverage of the name, unmatched name words, popularity, kind, deprecation; query expansion from
English (synonyms: sum→add, product→mul, divides→dvd, « number of »→card, « at most »→le…), a table of ~25 famous
results (Fermat's little theorem, Cauchy–Schwarz, IVT, Bézout…), and from Lean statements (identifiers minus bound
variables, notation ≤→le, ∑→sum, `0 ≤`→nonneg, `^ 2`→sq…; conclusion weighs 2, left side of `=` weighs more).
Semantic re-ranking: if Ollama runs with an embedding model (`nomic-embed-text` here) the top 30 are re-ranked
(0.6 lexical + 0.4 cosine); loopback only; never required. Build runs in a daemon thread at nice 19 + idle I/O.

Measured (this machine, 16 threads, 2026-11-21; `python -m madalean.brain.rag_eval --workspace …`):

| | lean-prover49 (Lean 4.9) | lean-current (Lean 4.34) |
|---|---|---|
| declarations / files | 178 817 / 4 831 | 289 628 / 9 606 |
| build time (low priority, warm disk) | 20–38 s | 50–74 s |
| index size | 118 MB | 198 MB |
| query latency | 50–60 ms | 85–135 ms |
| DEV set, hits@8 (19 queries, tuned on; with / without famous table) | 19 / 15 | 17 / 13 |
| SET2 hits@8 (20, seen during tuning) | 16 (MRR 0.70) | 16 (MRR 0.66) |
| **SET3 hits@8 (20, written last, no tuning after)** | **13 (MRR 0.47)** | 12 (MRR 0.51) |

Honest reading: name/notation-shaped queries and Lean statements whose lemma is named after its shape work well
(`Even.add`, `Finset.sum_le_sum`, `mul_pos`, `abs_mul`, `Real.exp_log`); paraphrases without the name words miss
(« antisymmetry of ≤ » → `le_antisymm`, « swap a double sum » → `Finset.sum_comm`, « exponential of a sum »). The
« polynomial of odd degree has a real root » query has no answer in either Mathlib (no such lemma), which the agent
must learn from the tools. Semantic re-ranking was **not measured** (it would load an Ollama model on the GPU, reserved).

## 8. Tests (`./run_tests.sh` runs them; no GPU, no network)

`tests/test_brain_router.py` (10), `test_brain_wire.py` (10: fake OpenAI and Anthropic servers with the real SSE
formats — streaming, thinking, tool calls, 401/429/529, mid-stream `overloaded_error`, beta rejection, refusal,
stall watchdog, loop guard, cancellation mid-stream + `release()`, key isolation, mode=local opens no external socket),
`test_brain_agent.py` (7), `test_brain_rag.py` (5, real lean-prover49 index built once into
`$TMPDIR/madalean-brain-test-<uid>`, ≈40 s the first time), `test_brain_prover.py` (3: scripted model + the REAL
Lean 4.9 compiler), `test_brain_online.py` (2, skipped unless `MADALEAN_ONLINE_TESTS=1`; marker `online` to be
registered in pytest.ini). `tests/test_brain_fakes.py` holds the fake servers (no tests).

## 9. Real runs (2026-11-21)

- Free keyless providers, `python -m madalean.brain.selftest --provider free`: completion OK; tool round OK
  (`ovh:nemotron3-omni-30b`); several OVH / LLM7 models answered 429 (rate limit, « free token allowance reached ») and
  were paused, Kilo models were reachable.
- `prove_with_agent` on `theorem t (a b : ℕ) (ha : Even a) (hb : Even b) : Even (a + b)` with real Lean 4.9: run 1
  proved in 2 steps / 1 Lean check / 26 s by `kilo:nvidia/nemotron-3-ultra-550b-a55b:free` (after 429s on OVH); run 2
  proved in 4 steps / 3 checks: first answer without a tool call (nudged), two submissions refused by Lean (an
  indentation problem of the tactic block — since fixed in the assembler — and a whole theorem passed as `proof` —
  now accepted), third accepted. Both runs used `Nat.even_add` (given among the premises), not `Even.add`.

## 10. Not verified / manual tests for the integrator

- Real Anthropic, Gemini and OpenRouter calls (no keys here; wire formats tested against fakes only):
  ```
  ANTHROPIC_API_KEY=… .venv/bin/python -m madalean.brain.selftest --provider anthropic   # Opus 5.5, ≈ $0.05–0.50
  GEMINI_API_KEY=…    .venv/bin/python -m madalean.brain.selftest --provider gemini
  OPENROUTER_API_KEY=… .venv/bin/python -m madalean.brain.selftest --provider openrouter
  ```
  Each runs one completion, one tool round and one `prove_with_agent` with the real Lean, printing model, tokens,
  seconds and (Anthropic) an estimated cost. Check in particular: the `fallbacks` beta is accepted by the account,
  `cache_read_input_tokens` > 0 from the 2nd agent step, thinking blocks replay without signature errors.
- Local llama-server through a real `LocalRuntime`, Ollama chat and Ollama embeddings (GPU reserved).
- `madalean/brain/leanrun.py` is not the server's checker; the server must give `check` with its pooled checker.

## 11. Leaderboard and proof tournament (session S-J, DECISIONS D30)

**Leaderboard** (`leaderboard.py`, `<config_dir>/brain-leaderboard.json`, 0600, ≤ 600 rows, no keys). One row per
model × task (`prove`, `formalize`, `explain`) and per model × task × coarse domain (`domain_of()`: number_theory,
algebra, linear_algebra, analysis, combinatorics, geometry, logic; « other » is not stored separately). Counts are
time-decayed (half-life 30 days): tasks where the model ran, Lean-verified successes, attempts, attempts spent on
solved tasks, Lean errors, wall time, pauses (could not run at all: 429 / quota / overload / key). Raw totals are kept
for display. Score = (ok + 0.3·4)/(n + 4) (Bayesian prior 0.3 worth 4 tasks: 1/1 → 0.44, 9/10 → 0.73) − min(0.15,
0.03·(mean attempts − 1)) − 0.3·pauses/(pauses + n + 2). Router bonus for the role's task (prove/formalize/explain
only) = 1.0·(score − 0.3)·confidence, confidence = m/(m + 3) with m = n + pauses; the domain row is used when it has
≥ 2 observations, else the general row. The `why` string says it, e.g. « a prouvé 7/9 problèmes d'algèbre linéaire ici,
2.0 essais en moyenne (+0.23) » (English when the interface is in English). Recorded by the pipeline: every
tournament contestant (prove), every model of the statement stage (formalize: success = Lean accepted the
statement), the explanation's model (explain: success = an answer that was not cut as a loop), the Goedel fallback.
`MadaleanBrain.leaderboard`, `MadaleanBrain.pool(role, mode, domain=)` (the full ranking, not cut to a chain: the
tournament's contestants), `run_agent(..., only=key)` / `prove_with_agent(..., only=key)` (pin one model, no switch).
API: `GET /api/models/leaderboard` (any paired device), `POST /api/models/leaderboard/reset` (host only).

**Tournament** (`madalean/pipeline/tournament.py`, used by `runner._proof` when the strategy resolves to `agent`, i.e.
`auto`/`agent` with an online-capable mode, and `tournament_enabled`):

| Setting (server `Settings`) | Default | Meaning |
|---|---|---|
| `tournament_enabled` | `true` | off = the previous loop (one agent, ≤ 4 runs, then Goedel for `auto`) |
| `tournament_contestants` | 3 | models raced in parallel per exploration round (online ones ≤ the `online` slots) |
| `tournament_max_rounds` | 3 | exploration rounds after round 0 |
| `tournament_max_minutes` | 40 | wall-clock cap of the whole proof stage (round 0 may use at most half of it) |
| `tournament_attempts_per_model` | 4 | attempts of the best model in round 0 (also ≤ `prove_attempts`) |
| constants | 16 / 3 M | total attempts (agent runs + Goedel attempts), total tokens when known |

1. Round 0 (exploit): the router's best model for `prove` + this domain (leaderboard bonus included) gets up to 4 agent
   runs, pinned to that model. If it cannot run at all (429, quota, pause, no step), the second best takes its place
   at once; if it ran and failed, round 0 ends.
2. Rounds 1…3 (explore): K = 3 models never tried in this task race in parallel on the same statement (1 agent run
   each). The local Goedel prover is one of the K when the job may use the GPU (mode ≠ online and a prover model is
   installed), with up to 4 attempts; it leads round 0 instead when its leaderboard score is better. The first proof
   that passes the server's strict Lean verdict wins; the others are cancelled (their HTTP requests and Lean
   processes are killed with their tasks; their attempts show « Essai arrêté »).
3. Paid models (Anthropic, OpenAI, DeepSeek…) never enter unless `paid_first` (brain setting) or chosen for `prove`;
   when they do, the thread shows an estimated upper bound per run (`agent_max_tokens` × list price; Opus 5.5
   $4/$20, Sonnet 5.5 $2/$10, Haiku 5.5 $0.10/$0.50 per MTok).
4. Every finished contestant is recorded (cancelled losers are not); a pause is recorded as a pause, not as a failure.

Termination: no recursion; round 0 runs ≤ 2 contestants; each exploration round only takes models not yet tried in
this task and the number of rounds is capped; every contestant runs under `asyncio.wait_for(deadline)`; the attempt
and token budgets are checked before each round; cancelling the job cancels every contestant. Tests
(`tests/test_tournament.py`): every model always failing, models flapping between 429 and errors with an endless
candidate list, a contestant that never answers (time cap), cancellation mid-race, winner cancels the others, paid
exclusion, slots (`online` ≤ 3, `lean` ≤ 2), « the winner leads round 0 next time ».

Safety: contestants share the job's slots (`online` acquired per agent run, `lean` per check) — no oversubscription;
every candidate proof is re-checked by `io.check` (strict verdict, exec-risk gate D28); attempts carry `round` and the
model key; `Job.tournament` = `{round, models, names, domain, state, winner, tried, rounds, minutes}`; thread events
« Tournoi, round k : … » for races and the winner / failure summary.

Real run (2026-11-21, S-J; test server on spare ports with a temporary config, mode online, strategy agent, Lean 4.9
`lean-prover49`, free keyless models, empty leaderboard at start):
- `theorem even_sq (n : ℤ) : Even (n ^ 2) → Even n` — round 0: `kilo:inclusionai/ling-3.1-flash` and
  `llm7:DeepSeek-V4-Flash-0731` could not run (429/pause, 0 steps); rounds 1–2: six OVH/LLM7 models all 429 within
  ~1 s each; round 3: `kilo:nvidia/nemotron-3-ultra-550b-a55b:free` proved it (59 s generation + 6 s Lean), the two
  others of that race were rate-limited. 11 attempts (10 « unavailable »), 102 s in total.
- `theorem six_dvd (n : ℕ) : 6 ∣ n * (n + 1) * (n + 2)` — Nemotron Ultra now led round 0 thanks to the leaderboard
  and proved it at the first attempt (146 s + 6 s Lean), no race.
- `theorem cubic_roots (x : ℝ) (h : x ^ 3 - 6 * x ^ 2 + 11 * x - 6 = 0) : x = 1 ∨ x = 2 ∨ x = 3` (after the change
  below) — round 0, Nemotron Ultra, first attempt, 132 s + 7 s Lean. Leaderboard: Nemotron Ultra 3/3 (score 0.60),
  ten models « indisponible 1× ».
- Change made after the first run: a contestant that cannot run at all is replaced at once by the next untried
  model within the same race (≤ 2 × K replacements per round) and no longer uses the attempt budget, so a race is
  not wasted on rate-limited providers.


## 12. Statement check and Mathlib first (session S-K, DECISIONS D31)

Two bounded stages before any prover model (settings `statement_check`, `mathlib_first`, both on by default):

**« Vérifier l'énoncé »** (`madalean/pipeline/verify.py`, endpoint `POST /api/dossiers/{id}/verify`, run automatically
before the first proof search of each statement). In parallel: (a) fidelity — role `understand`, JSON issues with
severity and a one-line fix in the user's language (pedagogical wording when the step carries `learn`); (b) truth —
ONE Lean compilation (`probes.py`: each probe is its own `set_option autoImplicit false in set_option maxHeartbeats
20000 in theorem …`, messages mapped back by line) of short proofs of `¬ (∀ BINDERS, CONCL)` (decide, norm_num, simp,
push_neg + witnesses 0/1, degenerate instances ∅ / 0 / 1 / `fun _ => 0` on the explicit binders, closed with
`simp at this`/`norm_num at this`/`exact this (by fun_prop|continuity|simp)`) and of quick proofs of the statement
(decide, norm_num, simp, omega, aesop), plus `exact?` (60 000 heartbeats) in its own file; (c) the model's
counterexamples, as tactic proofs of the same pinned negation (the server writes the proposition, the model only the
tactics). A probe that closes its goal is re-compiled alone with the strict verdict before it counts. Verdict: `false`
only on a Lean proof of the negation; `doubtful` on a high-severity model issue without Lean evidence; `faithful`;
`unknown` when nothing could be checked. `false`/`doubtful` stop the automatic chain with the reasons, the evidence,
« Corriger l'énoncé avec : … » (one click = statement follow-up with the fix) and « Prouver quand même » (`proof`
step with `force`). Caps: model 150 s, Lean batches 90 s / 60 s / 60 s, strict re-checks 60 s; the demo's fake
Lean is never used for probes (it would « prove » any negation).

**Mathlib first** (`madalean/pipeline/mathlib_first.py`, inside the proof stage, not for refinements of an existing
proof): ≤ 12 candidates = famous table (`rag.FAMOUS`, extended with Cayley-Hamilton → `LinearMap.aeval_self_charpoly`,
Riesz → `FiniteDimensional.of_isCompact_closedBall`, first isomorphism theorem → `LinearMap.quotKerEquivRange`, extreme
values → `IsCompact.exists_isMaxOn`… — French and English patterns; names checked in both lean-prover49 and
lean-current), premises of the Lean statement, search with the understood text; names that the D28 gate would refuse
are dropped. Templates `exact N`, `exact N _`, `exact ⟨N _⟩`, `simpa using N`, `apply N` (+ `intros` first) then side goals by `assumption` / `norm_num` for all
candidates in ONE compilation (40 000 heartbeats each, 120 s), `exact?` in parallel unless the statement check already
found a quick proof; then ≤ 2 calls of role `prove` asking for a 1–5 line proof with the 6 best candidates. Success →
proof model `mathlib:<name>`, `meta.strategy = "mathlib"`, `meta.mathlib_lemma`, thread event « Ce théorème est dans
Mathlib sous le nom … », explanation prompt told to cite it. Failure → the candidates are appended to the agent
contestants' hint. The translator also receives Mathlib's own statement (name, section variables, signature) when
the request names a famous result.

## 12. Keyed model families, key test, Claude as paid reinforcement (session S-M)

**Bug seen on the live install (read-only GET /api/models, 2026-11-21):** Gemini key set (40 models), yet no Gemini
model among the `prove` candidates; the key test picked `gemini:gemma-4-31b-it` (503 overloaded); Mistral (23 models)
only ranked `ministral-14b`. Cause: the seed knows only the keyless providers, so every keyed model got the size-based
estimate (0.41 when the name has no size): « gemma-4-31b » (0.48) and « ministral-14b » (0.44) beat Gemini Pro and
Mistral Large. Fix (`catalogue.FAMILIES`, `family_quality`): quality per family on the seed's scale, first match wins
— Gemini 3 Pro ≈ 0.88 maths, Gemini 3 Flash ≈ 0.80, 2.5 Pro ≈ 0.82, 2.5 Flash ≈ 0.72, Flash-Lite ≈ 0.55–0.62, 2.0
Flash ≈ 0.48, Gemma 4 ≈ 0.40; Magistral Medium ≈ 0.76, Mistral Large ≈ 0.64, Devstral (code 0.78), Mistral Medium ≈
0.60, Mistral Small ≈ 0.46, Ministral 14B ≈ 0.40… (plus GPT-5 / DeepSeek). Applied at refresh *and* when the router
reads a catalogue saved by an older version (`_with_family`), so the live install is fixed without waiting 12 h. The
« why » says it: `(estimated: Gemini 3 Pro family)`; the leaderboard and observed reliability then correct it.
`is_text_chat` also drops computer-use, robotics, live, AQA and deep-research models. Magistral / Devstral get the
Lean « good at maths and code » bonus. **To verify with the user's keys:** the exact ids of their 40 Gemini / 23 Mistral
models (patterns cover `gemini-2.x/3.x-pro|flash|flash-lite[-preview]`, `gemini-(pro|flash|flash-lite)-latest`,
`*-latest` and dated Mistral ids), and that the ranking feels right on real proofs.

**Key test** (`MadaleanBrain.test_model`, `catalogue.key_test_model`): one tiny call (≤ 256 tokens) to the provider's
cheap, stable model — Gemini 2.5 Flash-Lite → Flash-Lite latest → 2.5 Flash → Flash latest → 2.0 Flash (never Gemma);
Mistral Small latest → Ministral 8B; Claude Haiku; Groq 8B instant… — else the first stable (non-preview) model.

**Claude as paid reinforcement** (user decision 2026-11-21): the tournament (§11) gets a **final round** after the
free rounds failed (not after a time stop): one paid contestant from `brain.reinforcements("prove")` — Claude, only
with its key, `claude_reinforce` on, outside local mode, while the month's cap leaves room; model `claude_model` or
the best Claude for the role. It is bounded by the remaining wall time, not by the free rounds' attempt/token budgets.

**Spending caps** (`brain/spend.py`): every paid Claude call goes through `MadaleanBrain._budget` before it is sent:
input tokens estimated (≈ 3.5 characters per token, nothing assumed cached) at list price + the allowed output at
output price; `max_tokens` is reduced to what the caps leave (per proof scope `SPEND_SCOPE` = `dossier:job`, set by
the runner around the tournament; and per calendar month); if fewer than 2,048 output tokens fit, the call is refused
(`ProviderError("budget")`, chunk `event: budget`, not a model failure, nothing sent). Calls in flight are reserved.
After the call, the real cost from the API usage (input, output, cache read at 0.1×, cache write at 1.25× input; Haiku
5.5 × 5 above 100 K prompt tokens) is written to `<config>/brain-spend.json` (0600, no prompt, ≤ 5,000 rows) and
emitted (`event: spent`). A network error / stall after sending records the estimated prompt cost. Prices
(claude-api skill, cached 2026-11-03): Opus 5.5 $4/$20, Sonnet 5.5 $2/$10, Haiku 5.5 $0.10/$0.50, Fable 5.2 $8/$40
per MTok. Defaults: 1.00 USD per proof, 20 USD per month (Réglages › Modèles). Tests: `tests/test_spend_keyed.py`
(fake Anthropic server: fitted `max_tokens`, recorded usage incl. cache, refusal without request, month cap,
reinforcement round, pipeline with the runner).

**Unfit models** (integrator report: `ovh:Olala-v1.0-summarise` was given `prove` twice, its Lean never compiled):
`catalogue.unfit_reason` flags task-specific families (summarise, embed, rerank, guard, moderation, classifier, TTS,
transcription, caption, OCR, vision-language `-VL`, translation) and small models (`nano`, `tiny`, `e1b…e4b`, or a
largest size in the name < 7 B). The router never offers them for `prove` / `formalize` (unless the user picked one
explicitly) and gives them −0.30 for `route`; Madalean's own local models are exempt. The leaderboard adds a « junk »
penalty (up to −0.25) to a model that ran ≥ 2 tasks, never succeeded and whose Lean was rejected at every attempt, so
it sinks below an unknown model. Test: `tests/test_spend_keyed.py::test_summariser_and_tiny_models_never_prove_or_formalize`.

## 13. Hugging Face Inference Providers, Goedel online, local only as the fallback (session S-T, DECISIONS D33)

**Provider** `huggingface` (`catalogue.KEYED`): OpenAI-compatible router `https://router.huggingface.co/v1`
(`POST /chat/completions`, `Authorization: Bearer hf_…`, SSE with `stream_options.include_usage`, model id
`<repo>:<provider>` — provider pinned, the router never swaps it). Keyed, paid. Verified on 2026-11-22: docs
(huggingface.co/docs/inference-providers: index, tasks/chat-completion, pricing, hub-api, routing), the public
`GET https://router.huggingface.co/v1/models/<repo>` (Goedel-Prover-V2-32B and -8B: `featherless-ai`, live,
`is_free: false`, **no `pricing`**), and an anonymous / bad-token call: router and `GET /api/whoami-v2` both answer
**401 `{"error": "Invalid username or password."}`**. Not verified (no token here): the 402 body when credits run out
(the engine's generic 402 → 12 h pause applies), the real featherless-ai context limit, real latency.

**Discovery** (`catalogue.refresh_hf`, at each catalogue refresh, public API, **without** the token):
`GET https://huggingface.co/api/models/<repo>?expand[]=inferenceProviderMapping` for Goedel-Prover-V2-32B/-8B and
Goedel-Formalizer-V2-32B/-8B; a model is listed only for a provider whose mapping is `status: live` (2026-11-22: both
provers on featherless-ai, **no provider for the formalizers** — `goedel_model("formalize")` is then None and the
formalize stage runs as before). The router's per-provider `pricing` is read when published. HF models never enter
the general pool (router: only when pinned, roles prove/formalize): they are Goedel's prompts' models, not agents.

**Key test** (`MadaleanBrain.hf_check`, `POST /api/models/test {provider: huggingface}`): `GET /api/whoami-v2` on the
Hub — no inference, nothing billed — then a refresh; returns `login`, the live Goedel names, `warning:
inference_permission` when a fine-grained token's `global` permissions lack `inference.serverless.write` (« Make calls
to Inference Providers »; field shape from HF's token docs, not seen with a real token). Key isolation: the token's
hosts are exactly `{router.huggingface.co, huggingface.co}` (`net.Http.key_hosts` takes a set; no subdomains).

**Goedel-Prover-V2-32B online leads the proof** (`hf_goedel`, default on): with the token, outside local mode, while
the month's cap leaves room, `runner._tournament` puts contestant kind `goedel_online` first in round 0. It runs
`GoedelProver(io, "online", model=key)`: the SAME loop as the local 8B (verbatim `leancheck.initial_prompt` /
`correction_prompt`, ≤ 2 corrections per line of attack, fresh samples, loop guard), every call `brain.complete(...,
only=key)` (pinned: no other model ever answers in its place), temperature 1.0, top_p 0.95 (Goedel's evaluation
defaults, as 1.1.x; the model card only shows `max_new_tokens=32768`), up to 32 768 output tokens, context 40 960. If it
ran and failed, round 0 ends and the free models race as before (§11); if it could not run (cap, credits, 401,
provider down), the next model takes round 0 at once. Strategy « Goedel » uses it too (else the local 8B). Shown first
in `candidates("prove")` / `explain` (« qui reçoit quoi » and « pourquoi ce modèle »).

**Spending** (`spend.py`): the same ledger and the SAME caps as Claude (`claude_cap_proof_usd`, `claude_cap_month_usd`)
apply to every paid OpenAI-compatible model with a known or estimated price. HF bills the provider's price without
markup (PRO: $2 credits a month; free accounts buy credits). No price is published for Goedel on featherless-ai, so
`spend.HF_ESTIMATE` = **$1.00 / $3.20 per MTok, a conservative estimate** (≈ the router's published featherless-ai price
of GLM-5.3, a far larger model, rounded up), flagged `estimated_price` in the `cost`/`spent` events; a published
price replaces it. Before a call: `max_tokens` fitted, refused below 2 048 affordable tokens (nothing sent). After:
usage recorded; a cancelled / cut stream records the prompt + streamed characters / 3.5.

**Local models only offline or as the last fallback** (user decision 3): in `auto`, `complete` probes reachability
once (cached: 30 s online, 10 s offline; three resolvers in parallel, first answer wins, ≤ 1.5 s) when the chain
holds local models; offline → straight to them. A provider whose connection fails while the probe succeeds is
« down » (`MadaleanBrain.down`, 60 s, `status.providers[].down`): its other models are skipped, not each waited for.
The proof stage: no Internet → strategy goedel locally at once (« Pas d'accès à Internet… »); the local Goedel is **no
longer a tournament contestant**; after the tournament it runs only when **no online contestant could run at all**
(every one unavailable) — a proof the online models searched and failed is not re-run on the 8B. `online` mode: never
local. So llama-server is not started in normal online use (GPU lending S-N unchanged for when it does start).
Mode `local` always uses the local models. A brain without `internet()` (the scripted demo brain of `--demo` and the
older tests) keeps the previous behaviour (local Goedel after a failed online search) — `runner._legacy_fallback`.
`status()` adds `internet`, `local_policy` (`fallback` | `now` | `only` | `never`) and `goedel_online`.

Tests: `tests/test_hf_goedel.py` (16: key isolation, mapping parsing, discovery without the token and only live
models, identity key test, wire format + usage + ledger + pinning (402 → 32B paused, 8B remains), caps refuse before
sending and the month cap hides Goedel, auto online never starts the local model, offline → local, all online failing
→ local, `online` mode never local, provider down ≠ offline, fast cached probe, pipeline: Goedel-32B pinned round 0
with the verbatim prompt and sampling, Goedel failing → free models and never local, offline → local, all unavailable
→ local fallback).


## 14. « Classement » of the models, model news, automatic refreshes (session S-V, DECISIONS D34)

`rankings.py` (state `brain-rankings.json`, 0600). Réglages → Modèles → « Classement des meilleurs modèles »:
per Madalean domain — Lean proofs, formalisation, LaTeX / writing, Sage / code, general reasoning — the best models
usable now (keyless providers + providers whose key is set, local models included, paused ones left out), each score
with its evidence:

| Evidence | Source | Weight |
|---|---|---|
| Measured here | leaderboard.py (Lean-verified results, task prove / formalize / explain) | takes over with its confidence n/(n+3) |
| Public signal | LMArena, HF dataset `lmarena-ai/leaderboard-dataset`, config `text`, split `latest`, read through `https://datasets-server.huggingface.co/filter` (keyless), categories overall / math / coding / creative_writing / hard_prompts, top 100 each; licence CC BY 4.0, cited with its `leaderboard_publish_date` | 50 % with the catalogue estimate when the model is listed |
| Estimate | catalogue.py (seed quality, family estimate) | the rest |

- Verified by hand on 2026-11-22 (publish date of the rows: 2026-11-19); same source as Tontolo
  (`core/tontolo/catalog/sources/rankings.py`, verified there 2026-10-10). Artificial Analysis (Tontolo's other source)
  needs a key: not used yet.
- An LMArena row counts only when its name normalises EXACTLY to the catalogue id (`slug`: lowercase, parentheses and
  `-instruct/-it/-chat/-latest/-free/date` suffixes dropped; « preview » and sizes kept). Effort variants fold to the
  plain name, else the lowest rating. Percentile within the slice → [0, 1]. It is a proxy (human votes), never shown
  as a Lean result. Unknown models get no public score (never invented).
- News: each online catalogue refresh diffs the usable models against the previous snapshot: `new` (badge
  « Nouveau » 14 days), `gone` (a model missing while its provider still answers), `provider_added` (a new key: one
  event, not one per model). First snapshot = no news. Bounded to 200 events.
- Router (`router.rank(signals=…)`): while nothing is measured here for the role's task, +0.05 for a new model (so
  the tournament's exploration rounds try it soon) and 0.10 × (public percentile − 0.5). Once measured, only the
  leaderboard counts.
- Cadence: the server's periodic loop calls `brain.tick()` every 10 min: catalogue when older than 12 h, public
  rankings when older than 7 days (≤ 5 GETs). « Actualiser » forces both, the public fetch at most once an hour. Only
  with `refresh_catalogue` on and never in `mode = local` (Http refuses non-loopback hosts anyway); a failed fetch keeps
  the previous data (`error: unreachable`).
- API: `GET /api/models/rankings` (domains, public source + dates, news, next refreshes), `POST
  /api/models/rankings/refresh`. Event `models.rankings` after a manual refresh.
- Tests: tests/test_rankings.py (fake datasets-server; slugs, folding, news, router bonus, cadence, local mode, failure
  keeps data, API).

## 15. Interactive transcription: latency first (session S-AB, DECISIONS D35)

`with classify.task("transcribe"): brain.complete("assistant", msgs, …)` — used by the Calcul screen (request → one
Sage cell, automatic corrections, « Expliquer »). Categories `code` + `math`, fast. Differences from a normal call:

- **Ranking**: `router.latency_bonus` — the measured time to the first visible text of each model
  (`States.latency`, `lat`/`lat_n` in `brain-state.json`, recorded for EVERY successful online call, moving average,
  weight 0.3 after 3 samples): ≤ 1.5 s +0.20, ≥ 12 s −0.30, linear between. Not measured yet: thinking / Pro-class
  names −0.10, flash / lite / mini / codestral +0.05, other reasoning models −0.05. Other roles keep their order.
- **Chain**: 10 online models (`FAST_CHAIN`), local models last as before.
- **Race** (`MadaleanBrain._race`): the first model starts; while no model has written visible text, the next one is
  started every 2.5 s (`HEDGE_AFTER`, ≤ 3 at once, online only); a failure starts the next one immediately; the first
  complete non-empty answer wins, the others are cancelled (a cancelled racer is not a failure). Only the first model
  that writes is streamed; if it fails and another wins: `info restart`, then the winner's text.
- **Thinking / timeouts**: Gemini `reasoning_effort: minimal` (a bare « invalid argument » 400 → `low`, then the
  model's default), Claude effort `low` and no thinking; 20 s first byte and stall.
- **Pool**: its own semaphore of 4 (`FAST_PARALLEL`), never the shared `max_parallel` pool held by long proof calls;
  the caller (research/codegen.py) takes no job-scheduler slot.
- Preferred model: `settings.prefer["calcul"]` (no UI), else the router.

Measured 2026-11-22 (real keys, free models): before (role `assistant`) 5.5–6.1 s at best, 128 s when the first
models failed (503, 404, a 120 s stall, 402); after 0.6–1.7 s to the first code, 3.9 s with a hedge, 6.7 s with
two providers out (503 + 429).

## 16. Short text stages of a dossier: latency first, never the GPU model while online works (session S-AF, D38)

`with classify.short_stage(): brain.complete(role, msgs, …)` — used by the pipeline for understand, route, guided
reading (`notes`), the statement check's fidelity reading, explanation and informal proof (`pipeline/runner.py`).
`classify.fast_task()` is true inside, so these calls take the transcription path of §15: measured latency in the
ranking, chain of up to 10 online models, staggered race (`_race`), Gemini `reasoning_effort: minimal`, Claude
effort `low` without thinking, 20 s first byte / stall, their own pool of 4 requests. Differences from §15:

- the role keeps its own quality categories (an explanation is ranked as `writing` + `math`, a reading as `math`);
- for writing roles the latency bonus counts half (≤ +0.10 / ≥ −0.15): a clearly better writer stays first, a
  faster one of similar quality goes ahead;
- local models stay at the end of the chain and the race starts them only when no online model is left running
  (all failed or skipped). `local` mode or a local model chosen by the user (`prefer`) are unchanged.
- formal roles (`prove`, `formalize`) are never affected.

Seen on the user's dossiers (2026-11-21, 4 jobs at once): explanation / informal proof written by local Qwen3-8B
in 265–395 s while online models were up; the server log shows llama-server swapping Goedel ↔ Qwen3 between the
jobs. Probable cause (the log keeps no fallback details): the online explain models waited on the shared request
pool held by the tournaments and failed or stalled one after the other (90 s each), so the chain reached the local
model, which then waited for the GPU.

French: no data marks a model as bad at French yet (`brain-leaderboard.json` has no `explain` rows on this host);
the `explain` leaderboard bonus (per language) still applies when such rows exist.

## 17. Lean kept warm for intermediate attempts (session S-AE, DECISIONS D37)

Every check used to start `lean --json` and reload Mathlib (2–3.5 s with the page cache warm, 10–34 s cold,
~3.4 GB). `runtime/leanwarm.py` keeps **one `lean --server` per workspace in use** with the header already
loaded; `LeanRunner.check(…, warm=True)` uses it. Only the pipeline's `RunnerIO.check` passes `warm=True` (Goedel
loop, agent `lean_check`, tournament, statement probes, Mathlib-first batches); every other caller (manual checks,
library and update re-checks, notes, proof plans, self-tests, the brain's `leanrun`) stays fresh by default.

**Protocol** (identical on Lean v4.9.0-rc1 and v4.36.0, both measured):
- `lean --server -Dserver.reportDelayMs=0` under `leansandbox.wrap` (same boundary as every Lean, D28), document URI
  `untitled:/madalean/Attempt.lean` (Lean then never runs `lake setup-file`), `LAKE=/nonexistent/lake`,
  `dependencyBuildMode: never`; no file of the attempt is written to disk.
- The worker's key is its **prefix**: the exact header text (imports, whitespace and comments up to the first
  command) **plus the first character after it**. Lean keeps the loaded imports across an edit only when the first
  difference between the two versions lies strictly after the header's trailing whitespace (`isBeforeEditPos`);
  with a header-only document v4.9 re-imported Mathlib at every switch (3 s, measured). Goedel-format files all
  start `import Mathlib\nimport Aesop\n\ns` (`set_option maxHeartbeats …`).
- Per attempt: reset the document to the prefix alone, then send the whole attempt text. Nothing of a previous
  attempt can be reused (no command or tactic snapshot exists in the prefix-only version), so every command after
  the header is elaborated from the header's environment, as in a fresh file.
- A version is complete when Lean has sent its « nothing in progress » `$/lean/fileProgress` **and** at least one
  `publishDiagnostics` for that version (`reportSnapshots`: diagnostics are published from the first wait on, else
  once right after « done »). `textDocument/waitForDiagnostics` is not used: on v4.9 its handler spins forever on a
  task-pool thread when the request reaches the worker before the new version (seen on the first edit).
- LSP diagnostics → `LeanMessage`: `fullRange`, 0-based lines + 1, UTF-16 columns → code points (𝓝, 𝕜…), a
  zero-width range → no end position (as `lean --json` prints parse errors), silent messages dropped; rendered as
  `lean --json` lines in `CompileResult.stdout` so `parse_lean_json`, `judge`, `errors_for_feedback` and the probe
  batches read exactly what a fresh run prints. Measured identical on the 21 attempts of
  `tests/data/warm_attempts.json` (errors, warnings, axiom lines, positions, feedback text) on both versions.

**Policy** (`LeanRunner._check_warm`; « plus rapide sans perdre la fiabilité »):
- D28 gate and workspace check first, as before. No worker yet → this check runs fresh and the worker starts in the
  background (the statement check of a job usually pays it, the proof attempts find it ready).
- Worker busy for more than 2 s, loading, other prefix, crashed, lost answer, error on a header line → fresh.
  Three checks in a row with another prefix restart the worker on that prefix.
- **A warm acceptance of a strict check is never returned**: the same file is checked again by a fresh `lean --json`
  whose verdict (and axioms) is returned (`via = "warm+fresh"`). Only rejections and non-strict results come from the
  warm Lean (`via = "warm"`).
- **Audit**: the first warm result after each start and then one in 20 are also checked fresh. Any verdict
  disagreement (warm accept / fresh reject, or the reverse) returns the fresh verdict, logs both, stops the worker
  and sets the warm Lean aside for that workspace until « Réparer » on the health page or a settings toggle.
- Timeout: the attempt is reported as timed out (partial messages, same wording as a fresh timeout; the warm budget
  never includes the Mathlib load, so a fresh run would have timed out too) and the worker is killed — the next
  attempt never meets a Lean still busy with the previous one. Cancel → the worker is killed; the lock and the `lean`
  slot are released.
- Resources: a warm check holds a `lean` slot while Lean works (a worker's start does not); at most one worker per
  workspace and 2 workspaces (least recently used stopped first); stopped after `lean_warm_idle_minutes` (10) without
  an attempt, when the workspace's toolchain / manifest / `Mathlib.olean` change (checked at every use, by the reaper
  and after `refresh_workspaces`), when `lean_warm` is switched off, and at server shutdown. bwrap
  `--die-with-parent` + PDEATHSIG: never orphaned.
- Memory (PSS, measured): ~3.9 GB once Mathlib is loaded (v4.9: worker 3.4 GB, mostly the shared `.olean` pages,
  + language-server process 0.45 GB); up to ~6 GB after an `exact?` (Lean caches its library index for the
  process). A worker above 8 GB is recycled by the reaper when idle. While it lives, Mathlib's files stay in the page
  cache, so the fresh confirmations never pay a cold load (10–34 s) either.
- Mathlib first (§12) now runs the template batch first (warm: 0.2–1.1 s) and `exact?` (3–9 s of library search on
  any Lean) only when no template passes the strict check.
- Health page: row « Lean prêt d'avance » (loading / ready with its memory / at rest / set aside / could not start).

**Early abort (TODO B11) — designed, not built.** Idea: check a streamed answer by blocks with the warm Lean and
stop the model at the first certain error.
- Where code appears: Goedel-style models write a plan, then ONE ```lean4 block at the end (the last ~10–20 % of
  the tokens); a model may also write a block, criticise it and write another one; only the last block counts
  (`extract_code`). Agents already get Lean's verdict at each `lean_check` tool call — now in a fraction of a second.
- Cut points: inside the last open block, after each complete top-level declaration (a helper `lemma … := by …`
  whose next line returns to column 0) and after each complete `have … := by …` of the main proof.
- Check: assemble the prefix (user's statement kept, as `assemble_proof` does) with `sorry` for everything not yet
  written, check it warm. A cut is **certain** only for an error inside a complete helper declaration that the main
  theorem uses — and even then the model may still close the block, criticise it and write a corrected one, which
  is exactly what the correction rounds rely on. Errors before the end of the text are therefore not certain, and
  a wrong cut loses a proof the model was about to fix.
- Decision: not built. The expected gain is the tail of one answer per failing attempt (seconds of generation),
  the risk is a lost proof; reliability first. Re-open if measurements show long code blocks that fail early.

## 18. The conductor (« chef d'orchestre », session S-AI, DECISIONS D41)

Files: `brain/conductor.py` (choice, prompts, schemas, fallback chain, measurements), `brain/toolcards.py` (tool rule
cards, compaction), `pipeline/conductor_hook.py` (the job integration, a contained hook of `runner.py`),
`brain/fake_conductor.py` (scripted brain for tests and `scripts/dev/conductor_bench.py`). Settings: `conductor`
(on), `conductor_cap_usd` (1.0). API: `POST /api/jobs/{id}/conductor {approve}`; `job.conductor` in every job.

**What it does per request** (only when a conductor can run: setting on, mode not `local`, a brain with the
interface below, and either a Claude key or a capable free model — otherwise `NullHook`, the pipeline is unchanged):
1. *Plan* (beside the first stage; statement / proof / explanation wait ≤ 25 s for it, never longer): the code ranks
   candidates per kind (`worker_candidates`: the router's score — quality, measured reliability, leaderboard for the
   domain, public signals — minus measured latency, minus for a paid model 0.10 + 3 × its estimated cost / budget
   left; paid provers never: Claude stays the tournament's final reinforcement). The conductor answers a JSON plan
   (`PLAN_SCHEMA`: difficulty, summary, 3–8 tasks with `depends_on`, `model` among the candidates or `auto`, `why`,
   `hint`); `validate_plan` drops unknown kinds, duplicate ids, unknown dependencies and cycles, models outside the
   candidates, computes parallel waves. Effects: `prefer` per role in `JobIO.complete` (understand / formalize /
   explain; the user's own choice always wins), the prover that leads tournament round 0 (`lead`), hints appended to
   the formalizer's text and the provers' hint. Advisory kinds (`lemmas`, `compute`, `latex`) are shown, never run
   (D31: splits are the user's). Madalean's stages keep running as before (S-AF's parallel machinery).
2. *Corrections* (only on failure): Lean rejected the translation → `fix_statement` (≤ 3, each compiled by Lean,
   trivial statements refused); no proof → `fix_proof` from the two closest attempts and their Lean errors (≤ 3,
   assembled with the pinned statement, strict verdict + axiom probe like every proof). Attempts are visible
   (`kind: correction`), events « Claude a corrigé l'erreur Lean : … ».
3. *Final check* (after the explanation): statement ↔ problem ↔ proof ↔ explanation, issues listed in the thread;
   nothing is overwritten. Lean stays the only judge of a proof.

**Who directs** — `Conductor.choose`, recomputed for every decision:
`utility = min(q, need) + 0.02·(q − need)⁺ − est/room − 0.004·latency`, where `q` = posterior success of that model
on that decision kind (`brain-conductor.json`, prior per tier worth 4 decisions: plan Haiku 0.55 / Sonnet 0.80 /
Opus 0.90; fix 0.40 / 0.75 / 0.88; final 0.70 / 0.85 / 0.90; a correction's success = Lean's verdict), `need` by
difficulty (easy 0.5, medium 0.8, hard 1.0; corrections 1.0), `est` = estimated cost (prompt tokens, stable prefix
at the cache-read price when used < 280 s ago, expected output), `room` = what the request's cap and the month's cap
leave, `latency` = measured seconds of that decision here, else a prior from the real runs. Example (room 1 $):
medium plan (2 100 prompt tokens, 1 850 of them a cold stable prefix) — Sonnet 0.80 − 0.014 − 0.038 = 0.748, Opus
0.802 − 0.028 − 0.040 = 0.734, Haiku 0.519 → **Sonnet**; easy plan → **Haiku** (0.470 vs Sonnet 0.454); hard plan →
**Opus** (0.832 vs 0.748); medium final check → Sonnet (0.779 vs Opus 0.767, Haiku 0.685); a correction Sonnet failed
twice → **Opus** first; 2 cents left → Haiku; Sonnet's plans failing here 8 times → another model.
After Claude: the free models with reasoning quality ≥ 0.6 (catalogue), ranked by quality, measured reliability and
latency (`free_conductors`); unfit models never.

**Fallback chain** for every decision: chosen Claude → next Claude → best free → second free → none (the decision is
skipped; the pipeline goes on). A model is skipped at once when paused (429 with `retry-after`, quota, refused key),
its provider is down, or it is not affordable; a call ends on HTTP error, 60–180 s timeout, `stop_reason: refusal`,
or an answer that is not the schema's JSON — and the next one is called. Calls: `MadaleanBrain.call_model` (one
pinned model, raw stop reason, usage with cache reads, failures recorded in `brain-state.json` like any call).

**Claude request** (`providers/anthropic.py`, raw HTTP as before — no SDK dependency): `output_config: {effort,
format: {type: json_schema, schema}}` (structured output; dropped and retried if refused, the JSON is validated
anyway); thinking off = Sonnet 5.5 `{type: between_tools}` (effort ≤ high), Opus / Haiku 5.5 thinking omitted with
`low` effort (`disabled` is a 400 on these models); corrections keep adaptive thinking at `medium`; no
`temperature`/`top_p`/`top_k`, no forced `tool_choice`, no prefill; refusal fallback beta as before.

**Budget**: the request's scope is its proof scope `dossier:job` with its own cap (`Ledger.scope_caps`, default
1 USD) replacing the per-proof cap for that job; the monthly cap always applies on top; every paid call (conductor,
Claude workers, tournament reinforcement, Goedel online) counts. When a Claude decision does not fit: the job asks
« Plafond atteint : continuer avec Claude (+0,50 $) ? » (`job.conductor.ask`, dialog in the dossier, 10 min); yes →
+0.50 $; no / no answer → Claude off for this request, the next best (free) conductor continues; month room < 0.50 $
→ no question, Claude off.

**Tool rule cards and compaction** (`toolcards.py`): cards `lean` (the VERIFIED syntax card of the workspace —
`syntaxcards`, S-AB — else the same entries marked unchecked), `madalean` (conventions: fixed name and header,
forbidden constructs, faithful statements, Lean decides), `sage` / `python`, `latex`, `explain`. Role → tools:
formalize / prove / corrections → madalean + lean; explain / understand → explain; final → madalean + explain;
sage → sage + python; latex → latex + explain. Core rules go into a **stable block** (role text + cards, versioned,
byte-identical across requests, cache breakpoint after it: Anthropic `cache_control` on that system block only;
merged into one identical system prefix for OpenAI-compatible providers); feature rules (`sum`, `induction`,
`real`, `cast`, `analysis`…, detected in the request) go after it, deduplicated across cards, within a token
budget per role (formalize 450, explain 200, plan 350…). Workers (understand, formalize, explain) get their cards in
front of their messages when the conductor directs (never pinned Goedel calls, which keep their verbatim prompts).

**Corrections outside a job** (session S-AN, DECISIONS D46, `research/conductorfix.py`): two more decisions,
`codefix` (a Calcul cell, prompt `fix_sage` / `fix_python`, cards sage + python / python, schema `{code, what}`) and
`texfix` (an article compilation, prompt `fix_latex`, card latex, schema `{find, replace, what}`), with their own
priors (Haiku 0.55 / 0.60, Sonnet 0.82, Opus 0.88), expected output (700 / 500 tokens), low effort, thinking off;
like `fix`, the 3rd try goes to Opus first and the success is the checker's verdict, recorded by the caller (the cell
ran OK — at its first run after the correction; the project compiled with the change). Same choice, fallback chain
and caps as in a job: each user request has its own scope (`calcul:<pid>:<doc>:<cell>:<hash of the request>`,
`article:<pid>:<source hash>`) with the cap `conductor_cap_usd` in `Ledger.scope_caps` (≤ 200 scopes kept, oldest
dropped); the cap question is the event `conductor.ask {id, kind: calcul|article, spent, cap, step, estimate…}`,
answered by `POST /api/conductor/asks/{id} {approve}` (dialog shown wherever the user is; closing it = « sans
Claude »; no answer within 5 min = no; month room < 0.50 $ = never asked, Claude off). `NoConductor` → `None`: the
caller keeps its usual path (Calcul: the pinned Calcul model of D39). Never in `local` mode, never with a brain
without the interface, never when the setting is off.

- *Calcul*: in `codegen.transcribe(fix_code=…, conductor={scope, where, attempt})`, AFTER the deterministic
  fixer (`codefix`) and BEFORE the usual model. The prompt carries the request, the failing code, the end of the
  traceback, the notebook's names, S-AG's recognized intent and the catalogue's canonical constructions (a mandatory
  prefix, re-enforced by `codefix.enforce_prefix`). The answer is canonicalized and validated like any code (installed
  Sage's preparser); an invalid answer counts as a failure of that conductor and the usual model repairs instead.
  The version is model code (`by: assistant`, approval by hash unchanged, same sandboxed kernel), shown « Corrigé
  par Claude Sonnet · 0,004 $ » under the cell and in its history (`versions[].fix`, `autofix.by = conductor`); a run
  OK records it in the recipes (origin `conductor`) so the ranking makes it the « meilleure version »; it never
  counts for the pinned Calcul model (Claude is not pinned for transcription).
- *Article*: `POST …/texproject/compile` answers at once with `fixing: true` when a compilation that ran failed on
  an error without a one-click fix (`diagnostics[].fix` null) and a conductor can run; once per source hash. The
  conductor gets the file excerpt (±20 lines, numbered) and Madalean's reading of the error; its `find` must be an
  exact substring of the excerpt near the error and its `replace` must pass `texbuild.guard_ai`; the project is then
  compiled with the change in a separate sandboxed build (`texbuild.trial_compile`, same engine, guard, offline,
  nothing kept). Only a change that compiles becomes a suggestion (`kind: compile_fix`, `meta: {conductor, usd,
  verified: recompiled}`) of the suggestions panel — accept / refuse, never applied silently; a failure goes back to
  the conductor with the new error (≤ 3 tries). Events `article.fix {state: working|proposed|none}`.

**Not done**: the plan does not reorder or skip stages (it assigns models and hints).

**Not done**: Sage / LaTeX corrections are not wired into Calcul or the article editor (owned by S-AG / S-R) — the
cards and `Conductor.ask` are ready for it; the plan does not reorder or skip stages (it assigns models and hints).

## 19. Lean explanations and the verified catalogue in the provers' prompts (session S-AM, DECISIONS D45)

Files: `research/leanexplain.py` (prompts, goal states, the checked correction), `server/plugins/lean_explain.py`
(`POST /api/lean/explain`, reached by the generic `POST /api/code/explain` with `language: lean`; API.md §3.8a),
`pipeline/leancat.py` (catalogue block of a job's model calls), `research/codecat.py` (`lean_relevant`,
`lean_prompt_block`), `web/src/components/LeanExplain.svelte`.

**« Expliquer » for Lean** — the fast short-text path of §15 (`codegen.fast_complete`: `classify.task("transcribe")`,
no job slot, staggered race), streamed (`lean.explain`), cached in memory like the Sage modes.
- *Prompt*: plain French for a mathematician, tactics and Mathlib names in backticks with their mathematical meaning;
  the workspace's versions (« Lean v4.9.0-rc1, Mathlib … »), a version note (Lean 4.9 / Goedel's Mathlib:
  `Fintype.card`, `Nat.factors`, `∑ i in s`; current Mathlib: `Nat.card`, `Nat.primeFactorsList`, `∑ i ∈ s`), the
  VERIFIED syntax card of the workspace (`syntaxcards.lean_card`) and the catalogue constructions relevant to the
  code (below). Errors are Lean's own messages in Goedel's format (code around each error, `<error>` marks); the
  model must quote only goals Lean printed.
- *Correction*: compiled by the workspace's Lean before it is offered (`ctx.lean.check(…, warm=True)`: the warm Lean
  of D37 answers in ≈ 0.04 s once running, a warm acceptance of a strict check is re-checked fresh by the runner
  anyway). Rules of the place: a proof is assembled with the dossier's statement (`assemble_proof`: a changed
  signature is never taken) and judged strictly (no `sorry`, standard axioms); a statement must compile (`sorry`
  expected); a note's block must compile with its header, without a new `sorry`. Refused → one repair round with
  Lean's errors → refused again: no correction is shown (« Lean a refusé les corrections proposées »). The UI says
  « Correction acceptée par Lean v… (vérification rapide) », never « vérifiée »: « Appliquer la correction » goes
  through the manual-edit endpoints (`…/statement`, `…/versions/proof`, the note's autosave + block check), whose
  fresh strict check alone can make a proof « vérifiée ».
- *Line by line*: one sentence per line; header lines (`import`, `open`, `set_option`) glossed without a model. Goal
  states come from Lean only: `instrument` inserts `trace_state` after each complete tactic — at a tactic level
  (after a line ending with `by` / `=>`, or a bullet), after the tactic's continuation lines and nested blocks,
  never before `_ …` calc steps, `| …` alternatives, `<;>` or closing brackets; plus one before the first tactic of a
  declaration (the goal to prove, shown on the theorem's line); a one-line `:= by sorry` statement gets that goal
  only. Lean's information messages at the inserted lines are the goals (empty = « no goals »); an error ON an
  inserted line drops every goal (the insertion may have changed the meaning). Measured on both Lean versions:
  identical verdicts; the instrumented file costs what the plain one costs (2.2 s fresh on lean-prover49, 3.5 s on
  lean-current with a warm page cache, 0.04 s warm). Latency first: the model waits ≤ 4 s for the goals; later goals
  are still attached to the lines (not to the prompt).

**Verified catalogue constructions in the prompts** — S-AG's Lean entries (`codecat.LEAN_ENTRIES`, compiled per
workspace by `codecat.build_lean`: Lean 4.9 vs current spellings) relevant to the request are given to every model
that writes Lean for a job. Relevance: the request's recognized intent (`intent.analyze` of the problem / what was
understood / the statement: objects F_q, Z/nZ, K[x], Q(√d), matrices, S_n…, operations gcd, φ, primality, divisors,
sums, determinant) plus Lean names already in the statement (`GaloisField`, `ZMod`, `∑`, `Nat.Prime` outside a
`Fact` instance, `Matrix`…). Only entries **verified on the dossier's workspace** (in `verified` and not in
`failed` of its build; nothing at all when the build is missing). Compact: `- doc:` + the verified code, in
catalogue order (stable bytes for one request), within a token budget (prove 220, formalize 160, conductor 220).
- Goedel loop, Mathlib-first, tournament contestants, formalizer: `JobIO.complete` (`leancat.inject`) appends the
  block to the END of the first user message (after the verbatim Goedel prompt, like a user hint): every round of
  a job sends a byte-identical first message, so provider prefix caching across rounds is unchanged.
- Agent: in its task message (the system prompt, with the workspace's card, stays the stable cached prefix).
- Conductor (`fix_statement`, `fix_proof`, `plan`): in the request block after the cache breakpoint
  (`toolcards.compact(…, intent_text=…)`), the stable block byte-identical (same hash).
- Measured (`scripts/dev/leancat_tokens.py`, estimated tokens ≈ 3.5 chars, both workspaces): odd-sum request
  (`sum_range`) Goedel first message 149 → 204, formalizer 77 → 132, agent task 76 → 131, conductor request block
  299 → 354; F_125 (`gf`) 150 → 237; primality / gcd ≈ +49; determinant +78; a request with nothing relevant
  (x² + 1 > 0): unchanged. The conductor's stable block: 384 tokens before and after (lean-prover49), 377 (current).

## 20. Certificates: a proof strategy without a model, and a tool for the prover (session S-AT, DECISIONS D52)

docs/CERTIFICATES.md has the kinds and the limits; here is what the brain sees.

- **Strategy « certificat »** (`pipeline/certificate.py`, setting `certificates`). After the statement is accepted,
  `certs.kinds_of(statement)` (a pure reader, microseconds) says whether the statement has a certificate shape. If
  so, one attempt runs beside Mathlib-first and the search (D38 racers; sequentially when stages are not parallel):
  Sage (sandbox, Madalean's fixed program) computes a witness, the proof that checks it is written by Madalean, and
  the job's strict Lean check decides. No model, no token, no slot `online` / `gpu` (only `lean`, and the Sage
  kernel). A success cancels the other racers like a Mathlib-first success; the proof is recorded with the model
  `certificat:<kind>` (not ranked: no leaderboard entry) and `meta.strategy = "certificate"`. A failure costs a few
  seconds and changes nothing for the search.
- **Tool `sage_witness {claim}`** of the prover agent (`brain/prover_agent.py`, given when the pipeline passes
  `witness`): certificate for the theorem or for an auxiliary claim written in Lean. Returns a Lean-accepted helper
  lemma, « false » with the witness, or « no witness ». The model's text only ever becomes a Lean *statement* (which
  goes through the D28 gate like every Lean file); it never reaches Sage as code.
- **Conductor** (§18): it plans stages and models and has no tools; it sees the certificate attempt in the job.
  Asking it to *request* a witness for a sub-goal is future work (it would go through the same tool).
- A claim the computation finds false is reported in the thread (« Le calcul indique que l'énoncé est faux ») and
  to the agent; the statement check (§S-K) stays the judge of what to do with the statement.

## 21. Literature first and attachments (session S-AX, DECISIONS D56, docs/LITERATURE.md)

- **Stage `literature`** (pipeline/literature_hook.py): beside Mathlib-first and certificates (D38), own owner
  `<job>#literature`, bounded by `Budget` (time, requests, model calls, Lean checks); never a racer, never awaited by
  the proof search; skipped in Local mode, when the setting is off, for a refinement, and for a cited lemma's own
  dossier (loop guard). Cached in the stage cache (`kind: literature`).
- **Models**: free online models only (`only=` pinned to a non-paid, non-local candidate; a paid answer is dropped):
  a few extra search keywords (`understand`, filtered to plain words — never a reference), the choice of a passage
  among numbered ids (« approfondi »), the formalization of a verified quote (`formalize`, Goedel prompt, Lean check).
  Their output is never shown as a reference or a quotation.
- **Provers**: `job.literature_hint` (Mathlib names of cited results first; then cited / provided results that are
  not available in Lean, as statements to prove inline) is appended like `job.mathlib_hint` at each new attempt.
- **Conditional proofs**: Lean checks the theorem with the cited lemmas stated with `sorry`; the strict verdict always
  refuses it (`sorryAx`), so it is stored apart (`extra.conditional_proof`, `source: literature`) and upgraded only
  by a strict check once every cited lemma has a Lean proof in the library.
- **Attachments**: read once per project (SHA-256 digests); images through a vision model (free online; local in
  Local mode), the transcription kept, the image never re-sent.
## 22. The problem graph, the reasoned search and the lessons (session S-AY, DECISIONS D57 / D57b)

docs/PROOF_GRAPH.md. What the models see and do:

- **Provers** (pipeline proof stage, any model): the hint ends with the problem memory (`pipeline/memory_hook.py`):
  « Cible / Target », « Connu / Known » (Lean-proved; cited / provided, NOT proved), « À prouver / To prove », failed
  approaches with reasons, refuted statements, tactics that worked, Lean errors already seen; then the relevant
  lessons. Bounded (≈ 600 + 250 tokens), sorted (stable bytes for prompt caching), empty for a fresh dossier. The
  agent's Lean feedback gets « Known renames » when Lean reports a name a lesson knows.
- **Reasoned search** (`research/graphsearch.py`, user action « Recherche raisonnée »): role `prove` through
  `complete_once` — lemma proposals (`[madalean:graph-expand]`, JSON, the digest inside), one short viability opinion
  per new lemma (`[madalean:graph-viability]`, ≤ 300 tokens, `graph_viability_model`), one proof per attempt (Goedel's
  prompt + digest). Spend scope `graph:<dossier>:<run>` with its cap = `min(graph_search_usd, conductor_cap_usd)`.
  Lean decides everything: statements, combinations, counterexamples (negation probes), proofs (strict verdict).
- **Adapter la méthode** (`[madalean:graph-adapt]`): generalised statement + lemmas, kept only when Lean accepts the
  statements, labelled « proposition ».
- **Explanations**: no model — templates over recorded facts (FR / EN).
- **Lessons** (`research/lessons.py`): no training, no model — signatures, counters, evidence; deterministic renames
  re-checked by Lean.
