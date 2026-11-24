---
id: mathlib-contrib
title: Contributing to Mathlib
order: 255
section: research
audience: researcher
summary: From a verified result to a proposed addition to Mathlib — checked with current Mathlib, named, checked against the style rules, reviewed by you; nothing is sent without two clicks from you.
---

# Contributing to Mathlib

Mathlib is Lean's large library of mathematics. When one of your results
is missing from it, Madalean prepares what is needed to propose it: the file, the name, the checklist, the text of
the request. **You review everything**; nothing leaves without you.

## Where the button is

- in the **Library**: open a verified result, then “Prepare for Mathlib”;
- in a **dossier**: below the verified proof, “Prepare for Mathlib”.

Give your name (it goes at the top of the file, as Mathlib requires), then “Start the preparation”.

## The steps

1. **Check with current Mathlib.** Mathlib only accepts up-to-date code. When the proof was found with the prover's
   Lean (Lean 4.9), Madalean first replaces the names that changed since (those Lean reports as deprecated, those
   learned from your proofs, a small checked table) and has Lean 4.36 check it again. When that is not enough,
   “Restart the proof in current Lean” opens a new dossier, with the old proof as a hint.
2. **Look for it in Mathlib.** When a Mathlib lemma gives the result directly, Madalean says so, with its name, and
   stops: no duplicate contribution.
3. **Propose a name.** Mathlib names a theorem after its statement, read from left to right: `a + b ≤ c` gives
   `add_le`, `0 ≤ x` gives `x_nonneg`, a hypothesis adds `_of_…`. Madalean explains every word of the name and
   checks that it is free.
4. **Reduce the imports.** Instead of all of Mathlib, only the files needed — then Lean checks again.
5. **Check the final file** and run Mathlib's **style checks** (`#lint` and its automatic checks).

## The checklist

Each rule is marked *good*, *to review*, *blocking* or *not checked*: copyright header, file overview, an
explanatory sentence for each theorem, lines of at most 100 characters, no `sorry`, no raised time limit, `simp`
only at the end of a proof, ≤ rather than ≥, variables deduced from the hypotheses in braces, no deprecated name,
a free name, reduced imports. The explanatory sentence is written automatically from the statement: reread it.

## Sending

- **Copy** or **Download the file**: always possible, nothing leaves the computer.
- **Create a branch on my fork…**: only with a GitHub key saved in Settings → Keys, and from the host computer.
  Madalean first shows **exactly** what will be sent (each request, the content of the file); nothing leaves before
  “Confirm”.
- **Open the PR…**: a second, separate confirmation. The request is opened as a **draft**: you review it on GitHub
  before proposing it to the reviewers.

Mathlib's guides (contributing, naming, style, documentation) are linked at the bottom of the panel. Mathlib's
reviewers often ask for a shorter proof or a more general statement: that is normal.
