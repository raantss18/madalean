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

## Proof plan (guided)

The plan is a **tree**: the root is the dossier's goal, each node an intermediate result with its statement in plain
language, why it helps and, when possible, its Lean statement.

1. “Draft a plan”: the model proposes a tree; you can give it an idea or paste the proof sketch of a paper.
2. Correct by hand: add, delete, move, rewrite nodes. A manual edit is marked and never overwritten without your
   consent (the old version stays restorable).
3. Accept the nodes you keep, then “Start”: each accepted node becomes a sub-dossier; the leaves go first, an
   internal node is proved once its children are.
4. A node fails? “Split again” divides it in turn.

Each change creates a version of the plan; if two devices edit the same plan, the second gets a conflict and
reloads the up-to-date plan (plans are not merged automatically).
<!-- verify after integration: button labels of the plan screen (S-D) -->

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
