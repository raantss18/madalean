---
id: proof-plans
title: Proof plans and lemmas
order: 140
section: use
audience: researcher
summary: Splitting a result into lemmas proved in parallel, admitting temporarily, and what “proved modulo” means.
---

# Proof plans and lemmas

A statement too big for a proof in one piece gets split. Madalean offers two tools.

## Split into lemmas (quick)

“Split into lemmas” on a dossier: a model proposes up to four lemmas in Lean (or you write them, one per paragraph).
Each lemma becomes a **sub-dossier** started at once, in parallel. When all are finished and at least one is proved,
the parent dossier is restarted automatically with the proved lemmas at its disposal.

## Proof plan as a mind map (the main way)

« Plan » tab of a dossier (also from the thread and after a failed proof). One path:

1. **« Split this theorem »** (a hint for the AI is optional). The model proposes 2 to 6 lemmas, preferably
   independent, each with its statement in words, its Lean statement and why it helps, plus the **combination**: the
   Lean proof of the theorem from the lemmas. It keeps up to two **other tracks** (different strategies), dashed on
   the map.
2. Before showing you the plan, **Lean checks** that every statement compiles and that the theorem follows from the
   lemmas; otherwise the plan is asked again once with Lean's errors. An unchecked combination is marked « to check ».
   A lemma closed by a simple tactic (`simp`, `omega`, `exact?`…) is **obvious**: proved at once, never split again.
   A lemma that restates the theorem itself is **refused** (loop guard).
3. Read, edit if needed (any node can be edited by hand, each change is a version), then **« Approve the plan »** and
   **« Prove the plan »**: each lemma becomes a sub-dossier proved automatically (Mathlib first, then the model
   tournament); when all lemmas of a node are proved, the combination is compiled with the real proofs, strict
   verdict.
4. Madalean only comes back to you when a lemma **fails**, and offers in order: **another track**, **split it** one
   level deeper, or **leave a hole** (`sorry`).

At the top, a « where are we » line says what is left to do. Every node has a written status (to approve, in
progress, proved, failed, abandoned track, hole) and a path from the theorem. Limits: 3 levels of splitting
(adjustable), 6 lemmas per track, 2 other tracks, 30 nodes per plan, and a total time (Settings › Models ›
advanced). On a phone the collapsible list is the main view, the map is one tap away.

## Admitting temporarily

A node whose Lean statement is accepted can be marked “admitted for now”. The parent's proof can then rely on it:
Lean compiles the parent with the admitted lemma written as `sorry`.

The result is **proved modulo** the admitted lemmas. It is **not** a checked proof:

- it is not recorded as the dossier's proof, which stays “not proved”;
- the listed axioms contain `sorryAx`, Lean's trace of a `sorry`;
- the plan shows “proved modulo N admitted lemmas” with their names.

When each admitted lemma later gets a real proof, Madalean replaces the `sorry`s with the real lemmas and checks the
parent again with the strict verdict. Only then is the dossier proved.

## Good practice

- State the lemmas in Lean as early as possible: a node without an accepted Lean statement can be neither proved nor
  admitted.
- Prefer **general**, short lemmas; they enter the library and are reused.
- A lemma rejected several times is often badly stated (missing hypothesis) rather than hard: read it again as in
  [Reading a Lean statement](reading-lean.md).
