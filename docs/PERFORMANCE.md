# Madalean 2.0 — memory and idle work (session S-Q, 2026-11-21)

User decision: optimised, no redundancy, no useless task; kernels kept warm, ~1.5–2 GB at rest is acceptable.
Measured on the host (Ryzen, 31 GB RAM, RTX GPU) with a separate server (`bin/madalean serve --port 11630
--config-dir …`, real Lean workspace lean-prover49, keyless free online models) and `scripts/dev/memtree.py <pid>`
(RSS and PSS of the whole process tree, from `/proc/*/smaps_rollup`). The installed server was only observed
read-only.

## Numbers

| situation | before | after |
|---|---|---|
| server at rest, no UI open (Python process) | 63–78 MiB RSS | 63 MiB RSS (48 MiB PSS), no child process |
| child processes spawned at rest | 2 × `nvidia-smi` every 3 s (≈ 40 / min) | ≤ 2 / min (one poll per minute) |
| events written to the replay ring at rest | 1 `system.status` every 3 s (≈ 1 200 / h) | 0 |
| one UI open, 20 s | 7 `system.status` | 6 (only when the GPU / disk / slots snapshot changed) |
| one strict Lean check (`lean --json`, `import Mathlib`) | 3.4 GB PSS for ≈ 4.5 s, released | unchanged (no resident Lean) |
| real consigne run (3 Lean jobs in parallel + local Qwen3-8B llama-server) | — | peak 5.4 GB PSS (Lean 4.9 GB, llama-server 0.43 GB host RAM, server 77 MiB) |
| installed server at rest (observed) | 42 MiB RSS + 177 MiB swapped; cgroup peak 14.2 GB with llama + Lean | — (not modified) |

Lean processes share the memory-mapped Mathlib `.olean` files: two or three concurrent checks cost much less than
2–3 × 3.4 GB (8.2 GB RSS but 4.9 GB PSS above). Nothing of Lean stays resident between checks.

## What was changed

- **GPU / disk monitor** (`runtime/monitor.py`, `context.py`): fast pace (3 s) only when someone looks (an open
  WebSocket: `bus.clients`), the local model is loaded / loading, or a Lean check runs; otherwise one poll per minute.
  A new client wakes it at once (no latency regression). `system.status` is published only to an audience and only
  when the snapshot changed.
- **Event ring** (`server/bus.py`): still 5 000 events, now also ≤ 24 MB (article / blueprint / manifest events carry
  whole documents; 5 000 of them could hold hundreds of MB). A client too late resyncs, as before.
- **HTTP cache of the sources library** (`research/fetch.py`): was 500 answers of up to 8 MB each, never evicted by
  age; now ≤ 200 answers, ≤ 16 MB, expired entries dropped first, bodies > 2 MB (PDFs, archives: they are stored on
  the shelf) never kept in memory.
- **Embeddings** (`brain/rag.py`, `research/fulltext.py`): one shared `Embedder` for the Lean retriever and the
  sources library (each source search used to create a new one: new Ollama model detection, empty cache); its cache
  is an LRU of float32 vectors, 4 000 entries ≈ 12 MB (was up to 20 000 Python float lists ≈ 0.5 GB, then cleared all
  at once).
- **Catalogue refresh** (`brain/engine.py`): single flight — « Actualiser », a key test and the staleness check no
  longer start parallel refreshes; the GitHub key test no longer triggers a refresh at all.
- **Sage kernels** (`research/sagebridge.py`): kept warm 2 h (was 10 min: each experiment after a pause paid a Sage
  start of 10–20 s), at most 3 at once (least recently used shut down first) ≈ 1–1.8 GB when all are warm.
- **Tailscale node** (`server/plugins/deps_net.py`): a dev checkout or a server with `--config-dir` no longer
  auto-starts the shared `madalean-net` node (its state lives in the installation prefix). Incident during this
  measurement: the test server started a second node on the installed server's state directory and status socket
  for about two minutes; the installed node kept serving, but its status socket file `net.sock` was removed —
  restarting the installed service recreates it.

## Checked and left as is

- RAG index: one retriever, read-only SQLite opened per query (data in the page cache, not the Python heap).
- Sources full-text: per-shelf SQLite FTS, opened per query; shelves cached once per server.
- Leaderboard (600 rows), finished jobs (200), streamed model text (40 jobs × 1 M characters, 10 min after the end):
  bounded.
- Browser-session sweeper (5 s, in memory), research-workshop minute tick (update policy, cheap), llama-server idle
  unload after 10 min (gives the GPU back: kept, GPU sharing with Ollama).
- No duplicated poller where events exist: the proof-plan watcher subscribes to the bus; the consigne waits on the
  job tasks themselves.
- `texio` font caches (`lru_cache(maxsize=None)`) are bounded in practice by the installed fonts (S-O's file).

Tests: `tests/test_memory_bounds.py`.

# Proof time baseline (TODO B9, 2026-11-22)

Measured by `scripts/perf_report.py` (stage durations from the timestamps of the user's 15 real dossiers; raw data
in `bench/perf_baseline_2.0.json`) and `scripts/perf_report.py --lean` (one check of a trivial `import Mathlib`
proof through the server's sandbox). Re-run at every release.

| Stage | n | median | max | Note |
|---|---|---|---|---|
| Understanding | 12 | 4.7 s | 571 s | max: provider waits |
| Translation to Lean | 18 | 34.7 s | 324 s | max: local formalizer on GPU |
| Guided reading (`notes`) | 10 | 48.8 s | 226 s | does not feed the proof, yet runs before it |
| Statement check | 7 | 39.6 s | 59.7 s | runs before the proof too |
| Proof (to verified) | 11 | 31.3 s | 72.6 s | tournaments up to 686 s |
| Explanation | 12 | 21.0 s | 355 s | max: local Qwen3-8B picked while online models were up |
| Informal proof | 10 | 2.8 s | 395 s | same cause |

Lean check cost per attempt (bubblewrap, `lean --json`, fresh process every time):

| Workspace | first check (cold disk) | next checks (page cache warm) |
|---|---|---|
| lean-prover49 (v4.9.0-rc1) | 10.7 s | 2.0 s |
| lean-current (v4.36.0) | 25.8 s | 3.3 s |
| user MathlibDemo (v4.29) | 34.0 s | 3.5 s |
| user lean1 (v4.23) | 20.9 s | 3.5 s |

Findings:
1. The stages run strictly one after another: the first proof attempt starts about 2 minutes after the statement is
   accepted (reading + check), although only a « wrong statement » verdict should stop the proof.
2. Every attempt reloads Mathlib (2–3.5 s warm, 10–34 s cold, ~3.4 GB): an `exact <Mathlib lemma>` proof took
   33–56 s; a 32-attempt proof pays it 32 times.
3. Short text stages sometimes land on a slow local model while fast online ones are available.

Work started: S-AE (warm Lean, D37), S-AF (parallel stages, fast model choice for short stages, no recompute, D38).

# Étapes en parallèle (S-AF)

DECISIONS D38. Once Lean accepts the statement, guided reading, statement check, Mathlib-first search and proof
search run together; explanation and informal proof are written together; short text stages use the fastest
measured online model; the check verdict and the Mathlib-first result are kept per statement and Mathlib version.

**Real jobs before the change** (`scripts/perf_report.py`, the user's 2026-11-21/22 jobs, read-only): first proof
attempt **151.7 s** (median, max 194.4 s, n = 5) after the statement was accepted.

**Demo replay** (`scripts/dev/perf_stages_demo.py --realistic 10`): `madalean serve --demo` on spare ports with
throw-away config / cache directories; the scripted models answer after the real median of each stage divided by 10
(understanding 4.7 s, translation 34.7 s, guided reading 48.8 s, statement check 39.6 s, one proof attempt 15 s,
explanation 21 s, informal proof 2.8 s) and the simulated Lean takes 0.2 s per check; same problem, 3 runs each. « ×10 »
= the same timeline at the real medians.

| from the accepted statement | before (v2 `706d382`) | after (S-AF) | after, `parallel_stages: false` |
|---|---|---|---|
| first proof attempt | 9.98 s (≈ 100 s ×10) | **0.00 s** | 10.15 s, then 5.8 s (check reused) |
| proof verified | 19.6 s (≈ 196 s ×10) | **9.5 s** (≈ 95 s ×10) | 19.8 s, then 15.3 s |
| whole job (from its start) | 28.1 s (≈ 281 s ×10) | **17.2 s** (≈ 172 s ×10) | 28.3 s, then 23.8 s |
| stages running at once (max) | 1 | 3–4 | 1 (+ the check inside the proof) |

Reading: the first attempt no longer waits for the guided reading and the check (≈ 88 s of real medians); the proof
is recorded as soon as the check has let it through (here the check, 39.6 s, ends before the 4th attempt). With the
option off the order is the old one, and the second and third runs show B14: the check verdict of the same
statement and Mathlib is reused (« Énoncé déjà vérifié … »), −4.3 s (≈ −40 s real).

Not in this replay: the demo's Mathlib-first returns at once (simulated Lean); on a real Lean the Mathlib search
(33–56 s for `exact <lemma>` proofs) now runs beside the provers instead of before them, and a statement found in
Mathlib before is re-checked by one strict Lean run (2–3.5 s warm) instead of searched again. The model choice of
the short stages (BRAIN.md §16) is not visible with scripted models; it removes the 265–395 s local-model cases.

From now on, `scripts/perf_report.py` reads the exact stage durations: `seconds` in the result events and `timings`
(start / end of every stage) in the job history, plus « premier essai de preuve après l'énoncé accepté ».

## Chef d'orchestre (S-AI, DECISIONS D41)

**Demo replay** (`scripts/dev/conductor_bench.py --root . --runs 3 --scale 20`): one `madalean serve --demo` per
scenario × variant on ports 12100+, throw-away config / cache directories; the scripted workers answer after the
real median of their stage / 20 (as above), the scripted conductor after the latency measured on the real API /
20, the simulated Lean in 0.1 s; times multiplied back by 20 (≈ real seconds). `off` = conductor setting false (the
current pipeline), `claude` = Claude directs (scripted, priced at list prices from estimated tokens), `free` = no
Anthropic key, the best free model directs. Medians of 3 runs, `prove_attempts` 2, local Goedel prover (demo).

| scenario | variant | proved | job (≈ s) | worker calls | conductor calls | cost (USD) |
|---|---|---|---|---|---|---|
| everything succeeds | off | 3/3 | 90.6 | 6 | 0 | 0 |
| | claude | 3/3 | 92.9 | 6 | 2 (plan Haiku, final Haiku) | 0.0002 |
| | free | 3/3 | 98.4 | 6 | 2 | 0 |
| Lean rejects the translation (3×) | off | **0/3** | 116.2 | 4 | 0 | 0 |
| | claude | **3/3** | 174.1 | 8 | 3 (+ statement fixed) | 0.0013 |
| | free | 3/3 | 180.0 | 8 | 3 | 0 |
| provers fail without a hint | off | **0/3** | 90.3 | 5 | 0 | 0 |
| | claude | **3/3** | 91.9 | 6 | 2 (the plan's hint did it) | 0.0002 |
| | free | 3/3 | 98.3 | 6 | 2 | 0 |
| provers fail, plan without hint | off | **0/3** | 90.9 | 5 | 0 | 0 |
| | claude | **3/3** | 105.7 | 7 | 3 (+ proof fixed) | 0.0024 |
| | free | 3/3 | 113.8 | 7 | 3 | 0 |

Reading: on a request that already works, the conductor adds 2 calls and ≈ 2 s (the plan is written beside the
first stage; only the final check runs after the explanation); the worker calls are the same. When something fails,
one correction (≈ 3–8 s on the real API) replaces a failed job. The demo problem is « easy », so Haiku directs; the
demo's costs are estimates (3.5 characters per token) — see the real numbers below.

**Real API** (`scripts/dev/conductor_real_check.py`, the user's key read through the app's key store, throw-away
config, 2026-11-22; total spent **0.0851 USD** over 11 calls):

| decision (difficulty) | model chosen | wall | tokens in / out | cache read / write | cost |
|---|---|---|---|---|---|
| plan (medium) | Sonnet 5.5 | 10.4 s | 2 108 / 1 007 | 0 / 2 104 | 0.0153 $ |
| plan (medium), before the latency prior | Opus 5.5 | 9.7 s | 2 109 / 901 | 0 / 2 105 | 0.0286 $ |
| correction of a rejected statement | Sonnet 5.5 (thinking, effort medium) | 2.9 s | 1 323 / 158 | 0 / 1 319 | 0.0049 $ |
| final check (medium) | Sonnet 5.5 | 3.1–4.0 s | 1 180 / ≈ 300 | 960 / 0 (2nd run) | 0.0035–0.0060 $ |
| plan (medium), stable prefix only cached | Sonnet 5.5 | 8.1–10.3 s | 2 108 / 862–1 182 | **1 858** / 0 | 0.0093–0.0125 $ |
| plan (easy) | Haiku 5.5 | 7.5 s | 2 109 / 1 439 | 0 / 1 859 | 0.0010 $ |
| final check (easy) | Haiku 5.5 | 3.3–4.1 s | 1 181 / 261–339 | 961 / 0 (2nd) | 0.0002–0.0003 $ |

Two fixes came from these runs: (1) the top-level automatic cache breakpoint wrote the volatile request too (2 104
of 2 108 tokens written at 1.25×): with explicit stable blocks only the stable prefix is now cached (1 858 tokens
read at 0.1× on the next plan); (2) an unmeasured Opus beat a measured Sonnet on latency (unknown latency counted
as 0): every tier now has a latency prior from these measurements until it is measured here.

**Cost per request type** (real prices, measured tokens, stable prefix warm):
- simple request, easy (plan + final check on Haiku): ≈ **0.001 $**;
- typical request, medium (plan + final check on Sonnet): ≈ **0.013 $** warm, 0.021 $ cold;
- hard request (plan on Opus, final on Sonnet): ≈ **0.03 $**;
- + one correction (Sonnet): ≈ 0.005–0.03 $ each (≤ 3 per failure, the 3rd on Opus ≈ 0.05 $);
- workers assigned to Claude: only when clearly better than the free ones (penalty 0.10 + 3 × cost / budget left;
  never for proofs, where Claude stays the tournament's final reinforcement, S-M) — an explanation on Sonnet would
  cost ≈ 0.04 $.
A request stays far under the 1 USD cap unless the tournament's Claude reinforcement runs (bounded by the same cap).

**Prompt compaction** (`brain/toolcards.py`, estimates at 3.5 characters per token; the real tokenizer counts about
twice as many on these French / Lean texts — the plan's stable prefix is 915 estimated, 1 858 real):

| role | every card, every tool | the role's cards, unselected | sent (stable + this request) |
|---|---|---|---|
| formalize (Lean + conventions) | 2 055 | 671 | 438–538 (stable 377) |
| explain | 2 055 | 170 | 124–153 |
| conductor plan (+ role text 429) | 2 055 | 840 | 547–647 (stable 486) |
| conductor proof correction | 2 055 | 671 | 438–538 |
| conductor final check | 2 055 | 381 | 343–365 |

The stable block (role text + core rules, versioned) is byte-identical for every request of a role on the same tool
versions (tested); measured cache hit on the real API: 1 858 of 2 108 prompt tokens of a plan, 960 of 1 180 of a
final check — read at 0.1× the input price.
