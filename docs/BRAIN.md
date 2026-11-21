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
