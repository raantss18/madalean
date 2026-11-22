---
id: measures
title: "Measurements: what Madalean proves, how fast, at what cost"
order: 440
section: reference
audience: researcher
summary: The built-in benchmark — miniF2F, PutnamBench and a smoke set — counts only the proofs a fresh strict Lean accepts, with the time and the cost per proof.
---

# Measurements

Madalean measures itself. The `madalean bench` command feeds formal statements through **the same pipeline as the
application** (Mathlib search, tournament of free models, conductor…), without the interface, and writes for each
problem: proved or not, number of attempts, time, tokens, cost, the model that found the proof, Lean time.

Published results are on the “Measurements” page of the site (link at the bottom of every page of the site). They
are redone for each version.

## What counts as “proved”

One thing only: the proof found is compiled again **on its own**, by a fresh Lean, with the application's strict
verdict — no `sorry`, no added axiom, the standard axioms only — and it must prove **the statement that was given**,
not another one. The model's word, or an intermediate check, never counts.

A statement that the workspace's Lean does not accept (the set was written for another Mathlib version) is counted
**apart**: it is not a failed proof.

## The problem sets

| Set | Content | Licence |
|---|---|---|
| Smoke set | 20 statements written for Madalean, from logic to topology: checks that the whole pipeline works | Apache-2.0 |
| miniF2F | 488 high-school and olympiad statements (244 “valid”, 244 “test”) | MIT |
| PutnamBench | 672 statements from the Putnam competition (1962–2025) | Apache-2.0 |

miniF2F and PutnamBench are not copied into Madalean: `madalean bench fetch` downloads them from their public
repository, at a pinned version, into a cache folder; the content hash is checked at each read. PutnamBench asks
that proofs not be published: only counts are published.

## The strategies

| Strategy | What runs |
|---|---|
| `mathlib` | the Mathlib search alone, with no model at all |
| `tournament` | the application's default: Mathlib first, then the tournament of free models |
| `conductor` | the tournament directed by the conductor |
| `single` | a single model that you name |
| `goedel-local` | Goedel-Prover on the machine's graphics card |

## Cost

By default, **no paid model can be called**: the benchmark gives the engine the keys of free providers only. Paid
models are used only if you give a budget (`--paid-budget`, in dollars); that budget is a hard cap for the whole
run. The cost shown is that of paid calls at list price; free models and Mathlib cost $0.

## Running a measurement

```
madalean bench sets
madalean bench fetch minif2f
madalean bench check minif2f --split valid --workspace lean-prover49
madalean bench run minif2f --split valid --sample 50 --seed 1 --strategy tournament --time-budget 30
```

An interrupted run resumes where it stopped: run the same command again. The benchmark works in its own folder: it
touches neither your projects, nor your settings, nor the running server, and loads no model on the graphics card
except with `goedel-local`.

## What these figures do not say

- A sample of 50 problems gives an estimate within about ten points.
- Limits are short (a few minutes and a few attempts per problem): this is the workshop as it is used, not the
  maximum reachable with thousands of attempts.
- Online models change and their answers cannot be reproduced exactly: the order of the problems and the sample
  are reproducible, the models' answers are not.
- Statements are given in Lean: the translation from French or English is not measured here.
