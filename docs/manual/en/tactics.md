---
id: tactics
title: First tactics
order: 420
section: reference
audience: learner
summary: What the most common Lean 4 and Mathlib tactics do, with an example each, and when they fail.
---

# First tactics

A proof in tactic mode (`:= by …`) is a sequence of instructions that transform the **goal** (what remains to be
proved, shown after `⊢`) until nothing is left. The examples assume `import Mathlib`. The exact behaviour of a tactic
depends on the Mathlib version; what follows holds for both Madalean workspaces unless stated.

## Structuring

| Tactic | Effect | Example goal |
|---|---|---|
| `intro x` | introduces a variable or hypothesis: for `∀ x, P x` or `P → Q` | `⊢ ∀ n : ℕ, n + 0 = n` → `intro n` |
| `exact e` | closes the goal with a term of exactly the right type | `exact ha` when `ha : P` and `⊢ P` |
| `apply f` | reduces the goal to the hypotheses of `f` | `⊢ 0 < a * b` → `apply mul_pos` leaves `0 < a` and `0 < b` |
| `refine ⟨?_, ?_⟩` | like `exact`, with holes `?_` that become goals | |
| `constructor` | splits `P ∧ Q` (two goals) or `P ↔ Q` (both directions) | |
| `use 3` | provides the witness of an `∃` | `⊢ ∃ n : ℕ, n * n = 9` → `use 3` |
| `obtain ⟨x, hx⟩ := h` | unpacks `h : ∃ x, P x` (or `h : P ∧ Q`) | |
| `rcases h with h1 \| h2` | cases of a disjunction `h : P ∨ Q` | |
| `left`, `right` | chooses one side of an `∨` to prove | |
| `have h : P := by …` | proves an intermediate result and adds it to the hypotheses | |
| `show P` | restates the goal in a definitionally equal form (readability) | |
| `specialize h 2` | applies a universal hypothesis to a value | |
| `exfalso` | replaces the goal by `False` | |
| `by_contra h` | proof by contradiction: adds the negation of the goal | |
| `push_neg` | pushes negations inwards: `¬ ∀ x, P x` becomes `∃ x, ¬ P x` | |
| `contradiction` | closes the goal if the hypotheses contradict each other directly | `h : P` and `h' : ¬ P` |

## Induction and cases

```lean
theorem sum_odds (n : ℕ) : ∑ i in Finset.range n, (2 * i + 1) = n ^ 2 := by
  induction n with
  | zero => simp
  | succ n ih =>
    rw [Finset.sum_range_succ, ih]
    ring
```

`induction n with | zero => … | succ n ih => …` produces the base case and the inductive step; `ih` is the induction
hypothesis. `rcases`/`cases` handle the cases of an inductive type or of a disjunction; `interval_cases n` enumerates
the values of an integer bounded by the hypotheses. (In the “Recent Lean” workspace, write
`∑ i ∈ Finset.range n`.)

## Rewriting and simplifying

| Tactic | Effect | Fails when |
|---|---|---|
| `rw [h]` | replaces the left-hand side of `h : a = b` by the right-hand side in the goal; `rw [← h]` the other way; `rw [h] at h'` in a hypothesis | the pattern does not occur literally in the goal |
| `simp` | simplifies with Mathlib's lemmas tagged `@[simp]`; closes the goal if it becomes trivial | there is nothing to simplify |
| `simp only [a, b]` | simplifies with these lemmas only: more predictable and faster | |
| `simp at h` | simplifies a hypothesis | |
| `norm_num` | computes with explicit numbers: `2 ^ 10 = 1024`, `(7 : ℝ) / 2 > 3`, `Nat.Prime 97` | the goal contains variables it cannot eliminate |
| `field_simp` | clears denominators in a field (often needs `h : x ≠ 0`) | |
| `unfold f` | unfolds a definition | |
| `ext x` | equality of functions or sets: reduces to every `x` | |

## Arithmetic and inequalities

| Tactic | Domain | Does not do |
|---|---|---|
| `ring` | equalities in a commutative ring: `(a + b) ^ 2 = a ^ 2 + 2 * a * b + b ^ 2` | inequalities; equalities that need a hypothesis |
| `linarith` | **linear** combinations of hypotheses and inequalities, over an ordered field (`ℚ`, `ℝ`); often works on `ℕ` and `ℤ` too | products of variables |
| `nlinarith` | like `linarith`, adding products of hypotheses; help it by giving facts: `nlinarith [sq_nonneg (a - b)]` | guarantees: it is a heuristic |
| `positivity` | goals `0 < e`, `0 ≤ e`, `e ≠ 0` when the shape of `e` shows it (squares, sums of positives, exponentials…) | use complicated hypotheses |
| `omega` | **exact** linear arithmetic over `ℕ` and `ℤ`, with `/` and `%` by constants | products of variables; the reals |
| `decide` | decidable propositions on **concrete** values: `Nat.Prime 7` if the instance allows it, `2 ∣ 10` | free variables; large computations (slow) |
| `gcongr` | “same shape on both sides”: `a ≤ b → a + c ≤ b + c`, leaves the comparisons of the pieces | |

Example:

```lean
theorem two_mul_le_sq_add_sq (a b : ℝ) : 2 * a * b ≤ a ^ 2 + b ^ 2 := by
  nlinarith [sq_nonneg (a - b)]
```

Here $a^2 + b^2 - 2ab = (a-b)^2 \ge 0$: the fact given to `nlinarith` suffices, the combination is linear in that
fact.

## Searching

| Tactic | Effect |
|---|---|
| `exact?` | searches Mathlib for a lemma that closes the goal and suggests `exact …` |
| `apply?` | suggests applicable lemmas |
| `aesop` | automatic proof search (rules and `simp`) |
| `tauto` | propositional logic |

Madalean **rejects `exact?` and `apply?` in a final proof**: they are search tools, to be replaced by the lemma they
find. They remain useful in a notebook or in a Lean block of a note.

## Reading an error

| Lean's message | Usual meaning |
|---|---|
| `unknown identifier 'foo'` / `unknown constant` | the name does not exist in this Mathlib version (renamed, or invented by the model) |
| `type mismatch` | the term does not have the expected type: often a missing `ℕ`/`ℝ` conversion |
| `unsolved goals` | the proof stops while goals remain (shown) |
| `linarith failed` | the given hypotheses are not enough linearly: add facts |
| `motive is not type correct` | `rw` cannot rewrite at this place; try `simp only` or `conv` |
| `maximum recursion depth` / `deterministic timeout` | a tactic searches too long: make the proof more explicit |
| `declaration uses 'sorry'` | the proof contains a gap: it is not accepted |
