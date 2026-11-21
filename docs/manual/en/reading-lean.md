---
id: reading-lean
title: Reading a Lean statement
order: 110
section: use
audience: learner
summary: Decoding a Lean statement piece by piece, and spotting translations that change the meaning.
---

# Reading a Lean statement

Lean proves **exactly** the Lean statement, not the sentence you had in mind. This page teaches you to read a
statement well enough to judge a translation, without knowing how to write proofs.

## Anatomy of a statement

```lean
theorem somme_pairs (a b : ℕ) (ha : Even a) (hb : Even b) : Even (a + b) := by
  sorry
```

| Piece | Reading |
|---|---|
| `theorem somme_pairs` | a theorem, and its name (chosen by Madalean, unique) |
| `(a b : ℕ)` | “let $a$ and $b$ be natural numbers” |
| `(ha : Even a)` | hypothesis named `ha`: “$a$ is even” |
| `(hb : Even b)` | hypothesis `hb`: “$b$ is even” |
| `: Even (a + b)` | after the last `:` outside parentheses comes the **conclusion**: “$a+b$ is even” |
| `:= by sorry` | “the proof follows, in tactic mode”; `sorry` = proof still to be written |

Everything in parentheses before the last `:` is **assumed**; what comes after is **to be proved**. A statement with
`sorry` is a statement without a proof: Lean accepts it as a statement, never as a proved theorem.

The same thing can be written with quantifiers in the conclusion; it is equivalent:

```lean
theorem somme_pairs' : ∀ a b : ℕ, Even a → Even b → Even (a + b) := by
  sorry
```

`→` reads “implies”; `∀ a b : ℕ,` “for all natural numbers $a$, $b$”.

## The header

Statements of the “Prover” workspace start with a fixed header:

```lean
import Mathlib
import Aesop
set_option maxHeartbeats 400000
open BigOperators Real Nat Topology Rat
```

`import Mathlib` loads the mathematical library; `set_option maxHeartbeats` raises the allowed computation time;
`open …` lets you write `π` or `√` without a prefix. This header does not change the meaning of the statement, but
`open Nat Real` makes some names ambiguous (`sqrt` exists in both): look at the types.

## Types: which numbers are we talking about?

| Lean | Mathematics | Watch out |
|---|---|---|
| `ℕ` | $\mathbb{N} = \{0, 1, 2, \dots\}$ | contains 0; truncated subtraction and division (see below) |
| `ℤ` | $\mathbb{Z}$ | `/` is Euclidean division: the remainder `%` is always $\ge 0$, `-7 / 2 = -4` |
| `ℚ`, `ℝ`, `ℂ` | $\mathbb{Q}$, $\mathbb{R}$, $\mathbb{C}$ | division by zero is defined and equals 0 |
| `Finset ℕ` | finite set of integers | `Finset.range n` $= \{0, \dots, n-1\}$ |
| `Set ℝ` | subset of $\mathbb{R}$ | |
| `ℕ → ℝ` | real sequence | `u n` is the term $u_n$ |

When one statement mixes several types, Lean inserts **coercions**: `(n : ℝ)` or `↑n` denotes the integer $n$ seen
as a real number. A statement like `(n : ℝ) / 2` does not mean the same as `n / 2` on `ℕ`.

## Pitfalls that change the meaning

These translations are accepted by Lean, but do not say what one thinks.

1. **Subtraction on ℕ**: `2 - 5 = 0` in `ℕ`. A statement about $a - b$ where $a < b$ is possible must be written in
   `ℤ` or `ℝ`.
2. **Division on ℕ and ℤ**: `7 / 2 = 3`. “$n/2$” in mathematics is often a rational number.
3. **Division by zero**: in `ℝ`, `x / 0 = 0` by convention. A statement `x / y * y = x` is false for `y = 0`, and a
   translation that forgets the hypothesis `y ≠ 0` may become false… or trivial.
4. **Total functions**: `Real.sqrt (-1) = 0`, `Real.log 0 = 0`. A forgotten hypothesis ($x > 0$) causes no error.
5. **Contradictory hypotheses**: if the hypotheses cannot all hold, *any* conclusion can be proved. A very short
   proof of a hard statement is a warning sign.
6. **Indices**: `Finset.range n` starts at 0. $\sum_{k=1}^{n} k$ is translated `∑ k in Finset.Icc 1 n, k`; with
   `Finset.range n` the sum runs from 0 to $n-1$.
7. **Quantifiers**: order matters. `∀ ε > 0, ∃ N, …` is not `∃ N, ∀ ε > 0, …`.
8. **“There exists a unique”** is written `∃! x, P x`; `∃ x, P x` does not assert uniqueness.

Notation: in recent versions of Mathlib the sum is written `∑ k ∈ Finset.Icc 1 n, k`; the “Prover” workspace (Lean
4.9) still uses `∑ k in …`.

## A reading method

1. Read the conclusion alone: is it really what you want to prove?
2. List the hypotheses: is one missing? Is there one too many (a superfluous hypothesis makes the statement weaker)?
3. Check the type of each variable.
4. Look for a division, a subtraction, a root, a logarithm: are they in the right type, with the right hypotheses?
5. Try to falsify the statement on a small example. If the Lean statement is true and yours false (or the reverse),
   the translation is wrong.

The “Understand” panel (*Learn* mode) gives a line-by-line gloss written by a model: it helps reading, but it can be
wrong too; the code is authoritative. The vocabulary is in the [Glossary](glossary.md).
