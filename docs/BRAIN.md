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
