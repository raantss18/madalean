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

# Calcul : un seul code par demande (S-AG)

DECISIONS D39. `scripts/dev/calcul_determinism.py` (no network, no real model: a fake model that answers
differently every time stands in for the model path; throw-away directories). 31 typical requests (finite fields,
polynomials, integers, analysis, matrices, groups, curves, number fields, two partially covered), each asked, asked
again (« Réécrire ») and asked in another notation (F_125 / GF(5^3), plain / LaTeX / Unicode), 2026-11-22, this host.

| | Sage 10.10 | Python (sympy 1.14) |
|---|---|---|
| fully written by the verified catalogue (no model) | 29 / 31 | 22 / 31 |
| identical code after « Réécrire » | **31 / 31** | **31 / 31** |
| identical code in the other notation | **31 / 31** | **31 / 31** |
| model calls for 93 asks | 2 | 9 |
| analysis + assembly (median / max) | 2 ms / 44 ms | 1 ms / 603 ms (first: reads the kernel's versions) |
| « Réécrire » (best version, preparser check) | 37 ms median | 1 ms median |
| produced cells run in the installed Sage | 31 / 31 OK | — |

Before (S-AB; seen in the user's recipes file, read-only): temperature 0.2 with a race of up to 3 models
— the code of « Réécrire » changed by design, and the same field was written `GF(125, 'b')`, `F125` from an earlier
cell, or `F.<a> = GF(16)` depending on the model that answered first. Catalogue build: Sage 3.8 s (55 samples),
Python 1.1 s (39 samples), Lean: both workspaces compile the 21 entries (one file each).
