---
id: conjectures
title: Conjecture workshop
order: 200
section: research
audience: researcher
summary: Proposing conjectures, testing them (Lean on small cases, Sage, counter-examples) before believing them, and promoting them by a proof.
---

# Conjecture workshop

A conjecture is a dossier of a particular kind, with an **evidence log**: everything that was tried to test it. A
conjecture becomes a theorem only through a Lean proof.

## Where conjectures come from
<!-- verify after integration: button and screen names of the research screens (S-D) -->

- You write it (in plain language, and in Lean if you wish).
- “Propose conjectures”: from the project context you select (notes, dossiers, library results, sources), a model
  proposes a few with their motivation. Proposals that are already known (duplicate of a dossier, library result,
  lemma found in Mathlib) are set aside and listed separately with the reason.

## States of a conjecture

| State | Meaning |
|---|---|
| proposed | stated, nothing tested |
| tested on n cases | particular cases held (Lean or experiments) |
| Lean statement | a Lean statement is accepted by Lean |
| proved | the dossier's current proof passes the strict verdict |
| refuted | a counter-example was **checked again** independently |

## Testing before believing

**Small cases in Lean.** Madalean writes one `example` per case (by default $n = 0, \dots, 9$ for the first integer
variable) and tries to close it by computation (`norm_num`, `decide`, `simp`, `omega`). Option: a bounded statement
`∀ n < K, …` closed by `decide`. These tests prove nothing beyond the cases tested.

**Sage or Python experiments.** The model writes (or you write) a two-part program: a predicate `holds(...)` and a
search that calls `report(...)`. **The code is shown to you and runs only after you approve this exact code**; any
edit cancels the approval. Runs are confined (see [Security](security.md#code-run-on-the-host)) and limited in time
and memory.

**Counter-example.** An announced counter-example is not taken on trust: the predicate alone is re-evaluated at the
witness in a fresh kernel and, if the conjecture has a Lean statement, Lean must accept the negation of the statement
at the witness. Only then does the conjecture become “refuted”.

**Literature.** “Search the literature” queries the bibliographic databases (see [Sources](sources.md)) to find out
whether the statement is known.

## The evidence log

Each test, experiment, check or search adds a dated entry (with the code run, the output, the model and the device).
The log is **append-only** and its entries are chained by SHA-256 fingerprints: an entry modified afterwards shows
(“chain intact” / “chain broken”).

## Promoting

When the conjecture is proved, “Promote to theorem” changes its kind; the history is kept.

Example from demo mode: “$n^2 + n + 41$ is prime for every $n$” holds for $n = 0, \dots, 9$ in Lean, then an
experiment finds $n = 40$ ($40^2 + 40 + 41 = 41^2$), checked again: refuted.
