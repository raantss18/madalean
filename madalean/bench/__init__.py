"""« Mesurer » (strategy 2.1, item 2; DECISIONS D53): a reproducible benchmark of the real proof pipeline.

`madalean bench …` feeds formal statements through the same pipeline as the application (Mathlib-first, tournament of
free models, conductor…), headless, and counts a proof only when a fresh strict Lean accepts it. One JSONL row per
problem, one summary JSON per run; docs/BENCH.md describes the formats, the problem sets and their licences."""
