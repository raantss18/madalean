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

Everything happens in the project's “Conjectures” screen.

- “Write a conjecture”: you write it in plain language; “Translate to Lean” then proposes a Lean statement, or you
  write one yourself (“Check and save the statement”).
- “Propose”: from the project's notes, proved results and sources, a model proposes a few with their motivation;
  “Keep this conjecture” keeps the ones you want. Proposals that are already known (duplicate, already a dossier,
  already in the library, already in Mathlib) are set aside and listed separately with the reason.

## Explore: the conjecture engine

The “Explore” button of the “Conjectures” screen opens a guided process to **find what to prove**. You ask a
question in words or with a formula (“the sum of the first n odd numbers”, “n^2 + n + 41”, a list of terms,
“connected graphs on n vertices”), then the steps follow one another before your eyes; each can be stopped, and
everything is recorded.

1. **Explore.** Madalean computes a table of data with Sage, in the project's notebook “Explorations (conjectures)”
   (the same protected space as Calcul). When the request is recognised, the code is written without a model,
   always the same for the same request. Otherwise a model writes it: **this code is shown to you and runs only
   after you approve this exact code**, as in [Calcul](calcul.md); an edit cancels the approval. Terms given by hand
   need no computation.
2. **Recognise.** The data are compared with the OEIS (the encyclopedia of integer sequences) and go through
   pattern finders that run on your computer, without the network: polynomial or rational formula, recurrence,
   generating function, multiplicativity, periodicity, congruences, order of growth, inequalities and relations
   between quantities. A formula is fitted on part of the terms and then **validated on terms kept aside**; a
   pattern that fails is discarded, and the journal says on which term. In Local mode the OEIS is not queried:
   nothing leaves the computer. The LMFDB database is not queried (it cannot be searched by a list of terms).
3. **State.** Each pattern kept becomes a precise conjecture, in words and formulas, with a Lean statement when
   possible (Lean must accept it) and an honest label: “checked up to n = 59 (60 cases), not proved”, “heuristic”,
   “agrees on 14 terms”. Never “true”.
4. **Attack.** “Look for a counter-example” takes the computation further and by sampling. A counter-example is
   kept only after a recomputation in a fresh kernel and, when there is a Lean statement, the check by Lean: the
   conjecture is then kept as “refuted”, with its counter-example. If it resists, “Attempt the proof” sends it into
   the usual pipeline (a dossier), or “Keep as an open conjecture” files it in the project.
5. **Journal.** Everything that was tried — patterns kept, patterns discarded and why, look-ups, hunts — stays in
   the exploration's journal, which you can export to a note or to the article. A conjecture already in the project
   is flagged as a duplicate.

Example of the demo mode: “n^2 + n + 41 up to 30” gives “always prime”, checked up to n = 30; the hunt finds
n = 40, and the conjecture is kept, refuted.

## States of a conjecture

| State | Meaning |
|---|---|
| proposed | stated, nothing tested |
| tested on cases | particular cases held (Lean or experiments) |
| Lean statement accepted | a Lean statement is accepted by Lean |
| proved | the dossier's current proof passes the strict verdict |
| refuted | a counter-example was **checked again** independently |

## Testing before believing

**Small cases in Lean** (“Test small cases with Lean”). Madalean writes one `example` per case (by default $n = 0, \dots, 9$ for the first integer
variable) and tries to close it by computation (`norm_num`, `decide`, `simp`, `omega`). Option: a bounded statement
`∀ n < K, …` closed by `decide`. These tests prove nothing beyond the cases tested.

**Sage or Python experiments.** The model writes (or you write) a two-part program: a predicate `holds(...)` and a
search that calls `report(...)`. **The code is shown to you and runs only after you approve this exact code** (“I read this code:
approve and run”); any edit cancels the approval. Experiments only run from the host computer. Runs are confined (see [Security](security.md#code-run-on-the-host)) and limited in time
and memory.

**Counter-example.** An announced counter-example is not taken on trust: the predicate alone is re-evaluated at the
witness in a fresh kernel and, if the conjecture has a Lean statement, Lean must accept the negation of the statement
at the witness. Only then does the conjecture become “refuted”.

**Literature.** “Search the literature” queries the bibliographic databases (see [Sources](sources.md)) to find out
whether the statement is known.

## The evidence log

On screen it is called “Evidence log”. Each test, experiment, check or search adds a dated entry (with the code run, the output, the model and the device).
The log is **append-only** and its entries are chained by SHA-256 fingerprints: an entry modified afterwards shows
(“log intact” / “log altered!”).

## Promoting

When the conjecture is proved, “Promote to theorem” changes its kind; the history is kept.

Example from demo mode: “$n^2 + n + 41$ is prime for every $n$” holds for $n = 0, \dots, 9$ in Lean, then an
experiment finds $n = 40$ ($40^2 + 40 + 41 = 41^2$), checked again: refuted.

## Explore: the conjecture engine

The « Explore » button of the « Conjectures » screen opens a guided process to **find what to prove**. Ask a question
in words or as a formula (“the sum of the first n odd numbers”, “n^2 + n + 41”, a list of terms, “connected graphs on
n vertices”); the steps then run in front of you, each can be stopped, and everything is logged.

1. **Explore.** Madalean computes a data table with Sage in the project's « Explorations (conjectures) » notebook
   (the same sandbox as Calcul). When the request is recognised, the code is written without a model, always the
   same for the same request. Otherwise a model writes it: **that code is shown to you and runs only after you approve
   that exact code**, as in [Calcul](calcul.md); editing it cancels the approval. Terms typed by hand need no
   computation.
2. **Recognise.** The data is compared with the OEIS (the encyclopedia of integer sequences) and run through pattern
   finders on your own computer, with no network: polynomial or rational formula, recurrence, generating function,
   multiplicativity, periodicity, congruences, growth, inequalities and relations between quantities. A formula is
   fitted on part of the terms and then **validated on held-out terms**; a pattern that fails is discarded, and the
   log says on which term. In Local mode the OEIS is not queried: nothing leaves the computer. The LMFDB is not
   queried (it cannot be searched by a list of terms).
3. **State.** Each surviving pattern becomes a precise conjecture, in words and formulas, with a Lean statement when
   possible (it must be accepted by Lean) and an honest label: “checked up to n = 59 (60 cases), not proved”,
   “heuristic”, “matches 14 terms”. Never “true”.
4. **Attack.** « Look for a counterexample » computes further and by random sampling. A counterexample counts only
   after a recomputation in a fresh kernel and, when there is a Lean statement, Lean's check: the conjecture is then
   kept as « refuted », with its counterexample. If it survives, « Try the proof » sends it to the usual pipeline (a
   dossier), or « Keep as an open conjecture » files it in the project.
5. **Log.** Everything tried — kept and discarded patterns, with the reason — stays in the conjecture's history, and
   can be exported to a note or the article.
