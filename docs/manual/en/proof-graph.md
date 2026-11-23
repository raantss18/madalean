---
id: proof-graph
title: Problem graph, reasoned search and lessons
order: 145
section: use
audience: researcher
summary: Madalean keeps the memory of each problem as a graph of lemmas, searches for a proof with guards, explains the proof with its bibliography and learns from its mistakes.
---

# Problem graph, reasoned search and lessons

Each dossier has a **problem graph**: the **target** (the theorem or conjecture), the **known results** (Mathlib,
your library, the literature, attachments) and the **lemmas to prove**, with what was tried and why. It extends the
[proof plan](proof-plans.md): « Plan » tab, « Graph » view.

## Statuses

Each node has an icon, a word and a border style (never colour alone):

| Status | Meaning |
| --- | --- |
| verified by Lean | proved by Lean (strict verdict), or in Mathlib, or by a certificate |
| conditional | cited or provided without a Lean proof, or proved using such a result |
| to prove | still open |
| refuted | Lean proved the negation (counterexample) |
| abandoned | the reason is kept; the track is not retried while nothing has changed |

A proof that rests on a result cited but not proved in Lean is **always** “conditional, rests on …”, never
“verified”. It becomes verified when Lean proves that result.

A sub-lemma used by two lemmas exists once: it is listed under the first, the other shows “also used by …”. Two
statements that differ only by a hypothesis stay distinct.

## Reasoned search

“Reasoned search” tries to prove the target directly, then splits it into lemmas when useful. Before working on a
track, Madalean assesses it (“Why this track?”): already proved elsewhere, already abandoned, close to a failed track,
the same Lean error twice, depth… and, when a model is available, a short opinion of the model, always labelled as
such. Proposed lemmas are first checked by Lean (statements, combination), and Lean looks for a counterexample: a
false lemma is refuted before any work.

Guards: limits on time, attempts, depth, tokens and spending (never above the conductor's cap), a stop when nothing
progresses, loops refused (a lemma that would use what uses it). At the end, a summary says why the search stopped
and what was tried. “Stop this track” and “Resume” are in each node's detail.

## Explain the proof

“Explain the proof” builds the account **only from what was recorded**: the chosen track and why, the other tracks,
the lemmas and their status, the tactics used and what each does, what failed, and the bibliography (Mathlib
declarations with links, cited works with their verified reference, BibTeX). No model writes this text. “Explain line
by line” shows Lean's goals after each tactic. Exports: project note, LaTeX with `\cite`, BibTeX.

## Sub-dossiers

“Open as a sub-dossier” turns a lemma into a full dossier (its thread, its own graph, Calcul, notes, certificates),
listed under its parent: “Project › Dossier › Lemma”. Its verdict rolls up to the parent (proved → proved;
conditional → conditional). The depth is bounded by “Max depth of the lemma decomposition”. Archiving, moving or
deleting a dossier does the same to its sub-dossiers (“Undo” brings them back together).

## Adapt a method

On a result whose method is known (its Lean proof, or the quoted passage), “Adapt the method” proposes a generalised
statement and the lemmas of the adapted proof. These are **proposals**: their statements are checked by Lean, and only
a Lean proof will validate them.

## What Madalean learned

Settings › “What Madalean learned”: lessons drawn **only from verified proofs**, whatever the model — a Mathlib name
that does not exist and the one that works (applied without a model, then re-checked by Lean), what fixed a Lean
error, dead ends, strategies that work. Each lesson shows its evidence and counters; those that stop helping are
dropped. You can delete some, forget everything, export or import a file.
