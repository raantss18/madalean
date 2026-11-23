# Certificats — Sage calcule, Lean vérifie (session S-AT, DECISIONS D52)

A computation is fast and not trusted; a proof is trusted and slow to find. A **certificate** joins the two: Sage
computes a *witness* (a divisor, a primitive root, cofactors, a sum of squares, multipliers, a solution, rational
bounds…), Madalean writes a Lean proof that only **checks** that witness, and Lean's strict verdict decides. No
model is called.

```
statement ──read──▶ shape ──Sage (sandbox, fixed program)──▶ witness ──render──▶ Lean proof ──fresh strict Lean──▶ « vérifiée »
```

Nothing is « vérifiée » without the fresh strict check (no `sorry`, axiom probe: only `propext`, `Classical.choice`,
`Quot.sound`). A witness that is wrong gives a proof that Lean refuses; that refusal is reported (« Certificat
refusé par Lean »), never hidden and never turned into a proof.

Code: `madalean/certs/` — `expr.py` (reader of the arithmetic part of a Lean statement), `evalcore.py` (exact
evaluation with Lean's conventions), `poly.py`, `problem.py` (shapes → tasks), `sage_producer.py` (the fixed Sage
program), `producer.py` (how it is run), `pratt.py`, `render.py` (witness → Lean proof), `engine.py` (the loop and
the registry `KINDS`), `fromcalcul.py` (Calcul cell → statement), `corpus.py` (the measured statements);
`madalean/pipeline/certificate.py` (proof strategy and the agent's tool), `madalean/server/plugins/certificates.py`
(API).

## 1. What is trusted

| Part | Trusted? |
|---|---|
| Sage, the producer, the reader of statements, the renderer | **No.** A bug there gives a proof Lean refuses, or no proof. |
| Lean's kernel and Mathlib, under the strict verdict | Yes — as for every proof in Madalean. |

Tactics the generated proofs use, all checked by Lean's kernel: `norm_num`, `decide`, `ring`, `linear_combination`,
`linarith`, `positivity`, `interval_cases`, `omega`, `rfl`; `nlinarith` only as a fallback of the last step.
**`native_decide` is never used**: it would add Lean's compiler to what has to be trusted, and Madalean refuses it
before compilation anyway (D28). The price is size limits (below), stated rather than worked around.

The producer is Madalean's **fixed** program (`evalcore.py` + `sage_producer.py`, always the same text). A request is
JSON data: polynomials are lists of integers, propositions are trees interpreted node by node. No text of a
statement, of a model or of a cell is ever evaluated as code; program and request travel base64-encoded so that
nothing goes through Sage's preparser. It runs in Calcul's sandboxed Sage kernel (`SageBridge`: bubblewrap, private
home, memory and time limits — docs/CALCUL.md §2, §10), in one warm kernel kept for certificates. Answers are read
strictly (`poly.integer`, `poly.fraction`, `poly.from_wire`, `render._cert`): only numbers are written into a proof;
names come from the statement.

## 2. The kinds

`engine.KINDS`. « Sage » = a witness is computed; otherwise Lean recomputes directly and Sage is not needed.

| Kind | Statement shape (examples) | Witness (Sage) | Lean check |
|---|---|---|---|
| `prime` | `Nat.Prime 97`, `Nat.Prime (2 ^ 127 - 1)` | below 100 000: none. Above: a Pratt tree (a primitive root `a`, the factorisation of p − 1, recursively) | `norm_num` · `lucas_primality` + `decide` on a square-and-multiply function |
| `composite` | `¬ Nat.Prime 4294967297` | a divisor d and the quotient | `Nat.dvd_prime` + `norm_num` |
| `arith` | `Nat.gcd 123456 7890 = 6`, `(17 * 2753 : ℕ) ≡ 1 [MOD 3120]`, `Nat.factorial 10 = 3628800`, `641 ∣ 4294967297` | — | `norm_num` / `decide` |
| `powmod` | `3 ^ (10 ^ 18) % 1000000007 = 246336683`, `7 ^ 2024 ≡ 3 [MOD 13]` | — (the remainder is recomputed) | `decide` on `madalean_cert_powmod`, proved equal to `a ^ e % n` |
| `identity` | `(a b : ℤ) : (a + b) * (a - b) = a ^ 2 - b ^ 2` | — | `ring` |
| `ideal` | `(h₀ : x + y = 3) (h₁ : x * y = 2) : x ^ 2 + y ^ 2 = 5` | cofactors cᵢ with goal^k = Σ cᵢ·hᵢ (Gröbner basis, `lift`; k ≤ 3) | `linear_combination (exp := k) …` |
| `linear` | linear hypotheses ⊢ linear inequality, or ⊢ `False` | Farkas multipliers (exact rational LP, PPL) | `linarith only [the hypotheses used]` |
| `sos` | `a ^ 2 + b ^ 2 + c ^ 2 ≥ a * b + b * c + c * a`; with hypotheses `0 ≤ x`, `x ≤ y` | c + Σ gᵢ·(sum of squares) + Σ λᵢⱼ gᵢgⱼ with rational coefficients (SDP with cvxopt, then made exact) | `ring` (the identity) + `positivity`, `mul_nonneg` + `linarith` |
| `exists` | `∃ u v : ℤ, 123456 * u + 7890 * v = 6`, `∃ x : ℕ, 65537 * x % 1000000007 = 1`, `∃ x y : ℚ, x + y = 7/2 ∧ x * y = 3 ∧ x < y` | the values (Bézout, modular inverse, rational solutions of polynomial systems, bounded search) | `⟨w, by norm_num⟩` |
| `counterexample` | `¬ ∀ n : ℕ, Nat.Prime (n ^ 2 + n + 41)` | a point where the claim fails | `absurd (h w) (by norm_num)` |
| `numeric` | `Real.sqrt 2 + Real.sqrt 3 < 3.15`, `Real.pi ^ 2 < 10`, `Real.exp 1 + Real.pi < 5.86` | rational bounds of each √q, π, exp 1, log 2 that make the inequality follow | `Real.sqrt_lt'` / `Real.lt_sqrt` + `norm_num`, Mathlib's bounds of π, e, log 2, then `linarith` |
| `finite` | `∀ n < 30, …`, `∀ n : ℕ, n ≤ 60 → n ^ 2 < 2 ^ n + 9`, two or three bounded variables | — (every case is evaluated first; a false claim is reported with its counterexample) | `decide`, else `interval_cases` |

A claim the computation finds **false** (`Nat.Prime 91`, a polynomial « identity » that is not one, a bounded ∀ with
a counterexample, a wrong numerical value) is reported as such with the witness (« Le calcul indique que l'énoncé
est faux »); no proof is attempted, and the usual stages go on (the statement check decides what to do with it).
Never done when the statement has hypotheses.

### How primality scales without `native_decide`

a^(p−1) is astronomically large; computing it is out of the question, and writing one fact per bit of the exponent
made Lean's elaboration quadratic (measured: a 127-bit prime did not pass in 200 s). The generated file defines

```lean
def madalean_cert_powmod : ℕ → ℕ → ℕ → ℕ → ℕ        -- fuel, a, e, p ↦ a ^ e % p by squaring
theorem madalean_cert_powmod_eq : ∀ f a e p, e < 2 ^ f → madalean_cert_powmod f a e p = a ^ e % p
```

proved once by induction, and each power is then a `decide`: the kernel does one multiplication per bit with its
big-number arithmetic. Measured on Lean 4.9, loading Mathlib not counted: 2¹²⁷ − 1 in about 2.4 s, 2²⁵⁵ − 19 in
about 4.5 s (less on Lean 4.36); see docs/PERFORMANCE.md.

## 3. Where it is used

**(a) Proof pipeline** — strategy « certificat » (`pipeline/certificate.py`, setting `certificates`, on by default).
When `certs.kinds_of(statement)` is not empty, the certificate runs next to Mathlib-first: as one more racer of the
parallel stages (D38), or before the search when stages are sequential. First Lean-verified proof wins; a « faux » /
« douteux » statement verdict still stops everything as before. The attempt is visible in the job
(`kind: certificate`, model `certificat:<kind>`), the proof's metadata carries `strategy: certificate`,
`certificate`, `certificate_checker`, `certificate_witness`, and the thread gets its own event (`kind: certificate`):
« Certificat (…) : témoin calculé par Sage, vérifié par Lean. » with the witness in the details. Its Lean check is
the job's own (`io.check` with the theorem name: a warm acceptance is always confirmed by a fresh strict Lean, D37).
Statements with no kind are untouched: no attempt, no event, no delay.

**(b) Prover agent** — tool `sage_witness {claim}` (`brain/prover_agent.py`): the model sends a claim in Lean
(`(x y : ℝ) (h : 0 ≤ x) : …`; empty = the theorem itself) and gets back either a proof that the strict Lean check
has already accepted (to paste as a helper lemma), or « the computation says this claim is false », or « no witness ».
The model never sends code to Sage. The conductor (D41) does not call tools: for it the strategy is the automatic one
of (a), whose attempt it sees in the job like any other.

**(c) Calcul** — « Certifier avec Lean » in a cell's menu (`fromcalcul.py`, `POST /api/certificates/dossier`). The
cell's text and its stored result are read (nothing is run again) and turned into a statement: `factor(n)` (n is
prime / n = p₁^e₁ · …, with the primality of the factors below 100 000), `is_prime`, `next_prime`, `gcd`, `lcm`,
`xgcd`, `power_mod`, `inverse_mod`, `factorial`, `binomial`, or an integer expression. When Lean accepts the
certificate, a dossier is created in the project with the statement and the proof (re-checked under the dossier's own
theorem name), and added to the library. Same rule as every Calcul run: from the host, or from a paired device when
`experiments_remote` is on.

API: docs/API.md §6g.

## 4. Limits (what is not supported)

- **Shapes.** Number variables must have explicit types ℕ, ℤ, ℚ, ℝ; one number type per statement (a coercion such as
  `(n : ℝ)` with n : ℕ is refused); no functions, sets, sums `∑`, `Finset`, `Fin n`, matrices, complex numbers,
  abstract rings (`[CommRing R]`) — those statements simply have no kind.
- **Primality**: up to 400 bits, and only when Sage factors p − 1 within the time limit (30 s); `Nat.Prime` only.
  A factorisation certified from Calcul includes the primality of the factors only below 100 000.
- **Modular powers**: ℕ only (`[ZMOD n]` powers are not handled), base and modulus written as numerals, exponent up
  to 4000 bits.
- **Ideal membership**: ℤ, ℚ, ℝ; total degree ≤ 12; powers of the goal up to 3; no division by a variable, no `≠`
  hypotheses (so no « x ≠ 0 → … » cancellations); natural-number subtraction is refused.
- **Linear arithmetic**: over ℚ / ℝ reasoning only — a goal that needs integrality (2x ≥ 3 ∧ 2x ≤ 4 → x = 2 in ℤ)
  has no certificate (Lean's `omega` is the tool; no witness is involved). Lean's `linarith` re-derives the
  combination from the hypotheses the multipliers select; the multipliers themselves are shown, not replayed.
- **Sums of squares**: ℝ / ℚ, at most 4 variables and degree 8; multipliers are hypotheses times sums of squares and
  products of two hypotheses with a non-negative number. Not every non-negative polynomial is a sum of squares
  (Motzkin), and a numerical solution on the boundary of the cone cannot always be made rational: then there is no
  certificate. Equalities among the hypotheses are not used. Needs `cvxopt` in Sage (present in SageMath 10.x).
- **Existence**: rational or integer witnesses only (no √2 as a witness); searches are bounded (2 · 10⁶ points,
  30 s); a graph or another combinatorial object as a witness is not supported.
- **Numerics**: inequalities only, between rational expressions of √q, π, exp 1 and log 2; π to 6 digits on
  lean-prover49 (Mathlib's `pi_gt_3141592`), 20 on lean-current (`pi_gt_d20`); e and log 2 to 9 digits. No `exp x` /
  `log x` at other points, no trigonometric values, no integrals, no interval arithmetic of general functions.
- **Finite claims**: natural numbers below explicit numeric bounds, at most 3 variables and 4000 cases.
  **No SAT / DRAT route**: Sage here only has its LP-based SAT backend, and a DRAT checker inside Lean without
  `native_decide` is future work. Graph and Ramsey-type claims are therefore out of reach for now.
- Without SageMath (Calcul not installed), only `arith`, `powmod`, `identity`, `finite` and small `prime` work.

## 5. Measured

`scripts/dev/cert_bench.py` runs the corpus (`certs/corpus.py`, 64 statements: 60 true across the 12 kinds, 4 false)
with the installed Sage and a fresh strict Lean on every built workspace; table in docs/PERFORMANCE.md
« Certificats (S-AT) ». Tests: `tests/test_certificates.py` (reader, strict reading of witnesses, the producer in the
real Sage, every kind with the real Lean on each workspace, wrong witnesses refused by Lean, pipeline, agent tool, API,
Calcul, and the sandboxed kernel path).

## 6. Adding a kind

1. `problem.py`: recognise the shape, build the request (data only) — `Task(kind, request, data)`.
2. `sage_producer.py`: compute the witness from the request; answer with integers and lists only.
3. `render.py`: read the answer strictly, write the tactics; do **not** check the mathematics there.
4. `engine.KINDS`, a title (and its English text in `i18n_en.py`), statements in `corpus.py` — true ones and a wrong
   witness in `tests/test_certificates.py` — and run `cert_bench.py` on both workspaces.
