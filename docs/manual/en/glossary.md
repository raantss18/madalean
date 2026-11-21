---
id: glossary
title: Lean glossary
order: 410
section: reference
audience: learner
summary: The Lean and Mathlib vocabulary needed to read statements and proofs.
---

# Lean glossary

Terms are grouped by theme. For tactics, see [First tactics](tactics.md).

## Logic and notation

| Lean | Reads | Remark |
|---|---|---|
| `∀ x, P x` | for all $x$, $P(x)$ | `∀ x > 0, …` abbreviates `∀ x, x > 0 → …` |
| `∃ x, P x` | there exists $x$ such that $P(x)$ | `∃! x, P x`: there exists a unique $x$ |
| `P → Q` | $P$ implies $Q$ | also the type of functions from `P` to `Q` |
| `P ↔ Q` | $P$ if and only if $Q$ | |
| `P ∧ Q`, `P ∨ Q` | and, or | |
| `¬ P` | not $P$ | defined as `P → False` |
| `a ≠ b` | $a \neq b$ | abbreviates `¬ (a = b)` |
| `True`, `False` | true, false | propositions |
| `a ∣ b` | $a$ divides $b$ | special vertical bar, typed `\mid`; it is not the keyboard bar `\|` |
| `a % b` | remainder of the division | |
| `x⁻¹` | inverse | `0⁻¹ = 0` in a field |
| `↑n`, `(n : ℝ)` | $n$ seen in another type | conversion (*coercion*) |
| `fun x => e` | $x \mapsto e$ | also written `λ x => e` or `fun x ↦ e` |
| `f x` | $f(x)$ | application is written without parentheses |
| `∑ i in s, f i` | $\sum_{i \in s} f(i)$ | `∑ i ∈ s, f i` in recent versions |
| `∏ i in s, f i` | $\prod_{i \in s} f(i)$ | same |
| `Finset.range n` | $\{0, \dots, n-1\}$ | |
| `Finset.Icc a b` | $\{a, \dots, b\}$ | also `Ico`, `Ioc`, `Ioo` |
| `\|x\|` | absolute value | |
| `⌊x⌋`, `⌈x⌉` | floor, ceiling | `Int.floor`, `Int.ceil` |

## Declarations

| Term | Meaning |
|---|---|
| `theorem`, `lemma` | a statement with its proof (Madalean normalises `lemma` to `theorem`) |
| `example` | an unnamed theorem |
| `def` | a definition |
| `abbrev` | a definition that Lean unfolds readily |
| `structure`, `class`, `instance` | types with fields; type classes (« ℝ is a field ») and their instances |
| `axiom` | a statement admitted without proof; forbidden in a proof accepted by Madalean |
| `sorry` | « proof to be completed »: Lean accepts it provisionally, but reports a gap |
| `variable` | declares variables shared by several statements |
| `namespace X … end X` | prefixes names: `X.foo` |
| `open X` | lets you write `foo` instead of `X.foo` |
| `import` | loads a library (`import Mathlib`) |
| `#check e` | shows the type of `e` |
| `#eval e` | computes `e` |

## Arguments

| Syntax | Meaning |
|---|---|
| `(x : α)` | explicit argument, to be given |
| `{x : α}` | implicit argument, inferred by Lean |
| `[inst : Field α]` | instance argument, found by Lean (« α is a field ») |
| `(h : P)` | a hypothesis named `h`; a proof of `P` |

## Types and universes

| Term | Meaning |
|---|---|
| `Prop` | the type of propositions; a proof of `P : Prop` is a term of type `P` |
| `Type` | the type of « ordinary » types (`ℕ : Type`) |
| `ℕ`, `ℤ`, `ℚ`, `ℝ`, `ℂ` | natural numbers (with 0), integers, rationals, reals, complex numbers |
| `Fin n` | $\{0, \dots, n-1\}$ as a type |
| `Set α`, `Finset α` | subsets of `α`; finite (computable) subsets |
| `α × β` | Cartesian product; `p.1`, `p.2` the components |
| `List α` | lists |
| `Polynomial R` (`R[X]`) | polynomials with coefficients in `R` |
| `Matrix m n R` | matrices |

## Proofs

| Term | Meaning |
|---|---|
| goal | what remains to be proved, shown as `⊢ P` |
| hypothesis | what is assumed, above the `⊢` |
| tactic | an instruction that transforms the goal (`intro`, `simp`…) |
| `by` | switches to tactic mode |
| term mode | a proof written as a term: `fun h => h.1` |
| `h.1`, `h.2` | the two parts of a hypothesis `h : P ∧ Q` |
| `⟨a, b⟩` | builds a pair, a conjunction, or a witness with its proof |
| `·` | starts handling one of the goals |
| `<;>` | applies the next tactic to all the goals produced |
| `rfl` | « by definition »: both sides are equal after computation |

## Ecosystem

| Term | Meaning |
|---|---|
| Lean 4 | the language and proof checker |
| Mathlib | the community's mathematical library (≈ 290,000 declarations in a recent version) |
| kernel | the small part of Lean that actually checks proofs |
| standard axioms | `propext`, `Classical.choice`, `Quot.sound`: accepted by Mathlib and by Madalean |
| Lake | the build tool of Lean projects (`lake build`) |
| elan | the Lean version manager |
| toolchain | a precise Lean version, fixed by a project's `lean-toolchain` file |
| workspace | in Madalean, a Lake project with a Lean and Mathlib version |
| blueprint | the graph of a formalisation project's statements and their dependencies |
