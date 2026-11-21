"""Retrieval quality measurement of the RAG index (hits@8, MRR) on three query sets.

    python -m madalean.brain.rag_eval --workspace lean-prover49 [--cache DIR] [--no-famous] [--build] [-v]

- DEV: the queries used while tuning (several are answered by the FAMOUS table of well-known results).
- SET2: written after a first tuning round and looked at during later tuning (semi-held-out).
- SET3: written last and measured without tuning afterwards (the honest number).
Expected names are those that exist in lean-prover49 (checked); recent Mathlib may have renamed some."""
from __future__ import annotations

import argparse
import asyncio
import sys
import time
from pathlib import Path

from . import rag

DEV = [
    ("sum of two even numbers is even", ["Even.add"]),
    ("every linearly independent set can be extended to a basis",
     ["exists_linearIndependent_extension", "Basis.extend", "exists_linearIndependent", "LinearIndependent.extend"]),
    ("intermediate value theorem", ["intermediate_value_Icc", "intermediate_value_Icc'", "intermediate_value_Ioo",
                                    "IsPreconnected.intermediate_value", "intermediate_value_uIcc"]),
    ("number of roots of a polynomial is at most its degree",
     ["Polynomial.card_roots'", "Polynomial.card_roots", "Polynomial.card_roots_sub_C'"]),
    ("there are infinitely many primes", ["Nat.exists_infinite_primes", "Nat.infinite_setOf_prime"]),
    ("product of two odd numbers is odd", ["Odd.mul"]),
    ("square root of 2 is irrational", ["irrational_sqrt_two", "Nat.Prime.irrational_sqrt"]),
    ("triangle inequality for absolute value", ["abs_add", "abs_sub_le", "abs_add_le", "abs_sub"]),
    ("continuous function on a compact set attains its maximum",
     ["IsCompact.exists_isMaxOn", "IsCompact.exists_forall_ge", "IsCompact.exists_max_image", "ContinuousOn.exists_forall_ge"]),
    ("Fermat's little theorem", ["ZMod.pow_card_sub_one_eq_one", "Int.ModEq.pow_card_sub_one_eq_one", "ZMod.pow_card"]),
    ("Bezout identity gcd as linear combination", ["Nat.gcd_eq_gcd_ab", "Int.gcd_eq_gcd_ab", "Nat.xgcd"]),
    ("Cauchy-Schwarz inequality", ["inner_mul_le_norm_mul_norm", "real_inner_mul_inner_self_le", "abs_real_inner_le_norm",
                                   "inner_mul_inner_self_le"]),
    ("derivative of sine is cosine", ["Real.deriv_sin", "Real.hasDerivAt_sin", "deriv_sin"]),
    ("geometric series sum formula", ["geom_sum_eq", "tsum_geometric_of_lt_one", "hasSum_geometric_of_lt_one", "geom_sum_Ico"]),
    ("a divides b and b divides c then a divides c", ["dvd_trans", "Dvd.dvd.trans", "Nat.dvd_trans"]),
    ("sum of first n natural numbers", ["Finset.sum_range_id_mul_two", "Gauss_sum", "Finset.sum_range_id"]),
    ("Finset.sum_le_sum", ["Finset.sum_le_sum"]),
    ("theorem t (a b : ℕ) (ha : Even a) (hb : Even b) : Even (a + b)", ["Even.add", "Nat.even_add"]),
    ("theorem t (s : Finset ℕ) (f g : ℕ → ℝ) (h : ∀ i ∈ s, f i ≤ g i) : ∑ i in s, f i ≤ ∑ i in s, g i",
     ["Finset.sum_le_sum"]),
]
SET2 = [
    ("every prime is at least two", ["Nat.Prime.two_le"]),
    ("reverse triangle inequality", ["abs_sub_abs_le_abs_sub", "abs_abs_sub_abs_le_abs_sub", "norm_sub_norm_le"]),
    ("a square is nonnegative", ["sq_nonneg", "mul_self_nonneg", "pow_two_nonneg"]),
    ("square of a sum (a+b)^2", ["add_sq", "add_pow_two", "add_sq'"]),
    ("exponential is positive", ["Real.exp_pos"]),
    ("log x is at most x minus one", ["Real.log_le_sub_one_of_pos", "Real.add_one_le_exp"]),
    ("cardinality of a subset is at most cardinality of the set", ["Finset.card_le_card", "Finset.card_le_of_subset",
                                                                   "Set.ncard_le_ncard"]),
    ("subset of a finite set is finite", ["Set.Finite.subset", "Finite.Set.subset"]),
    ("composition of continuous functions is continuous", ["Continuous.comp", "Continuous.comp'"]),
    ("sine is at most one", ["Real.sin_le_one", "Real.sin_le"]),
    ("remainder is less than the divisor", ["Nat.mod_lt", "Int.emod_lt_of_pos", "Int.emod_lt"]),
    ("every natural number is even or odd", ["Nat.even_or_odd", "Nat.even_or_odd'", "Int.even_or_odd"]),
    ("product of positive numbers over a finset is positive", ["Finset.prod_pos"]),
    ("determinant of a product of matrices", ["Matrix.det_mul"]),
    ("factorial is positive", ["Nat.factorial_pos"]),
    ("sum of a constant over a finset", ["Finset.sum_const", "Finset.sum_const_nat"]),
    ("1/x tends to zero at infinity", ["tendsto_inv_atTop_zero", "tendsto_one_div_atTop_nhds_zero_nat",
                                       "tendsto_const_div_atTop_nhds_zero_nat"]),
    ("theorem t (p : ℕ) (hp : p.Prime) : 2 ≤ p", ["Nat.Prime.two_le"]),
    ("theorem t (x : ℝ) : 0 ≤ x ^ 2", ["sq_nonneg", "pow_two_nonneg", "even_two.pow_nonneg"]),
    ("theorem t (a b : ℝ) : (a + b) ^ 2 = a ^ 2 + 2 * a * b + b ^ 2", ["add_sq", "add_pow_two"]),
]
SET3 = [
    ("a divisor of a prime is one or the prime itself", ["Nat.Prime.eq_one_or_self_of_dvd"]),
    ("a divisor of a positive number is at most the number", ["Nat.le_of_dvd"]),
    ("absolute value is nonnegative", ["abs_nonneg"]),
    ("square root is nonnegative", ["Real.sqrt_nonneg"]),
    ("square of the square root", ["Real.sq_sqrt", "Real.sqrt_sq", "Real.mul_self_sqrt"]),
    ("cardinality of a union is at most the sum of cardinalities", ["Finset.card_union_le"]),
    ("gcd is commutative", ["Nat.gcd_comm", "gcd_comm", "Int.gcd_comm"]),
    ("product of positive numbers is positive", ["mul_pos"]),
    ("sum of positive numbers is positive", ["add_pos", "Left.add_pos"]),
    ("exp of log", ["Real.exp_log"]),
    ("sin squared plus cos squared equals one", ["Real.sin_sq_add_cos_sq", "Real.cos_sq_add_sin_sq", "sin_sq_add_cos_sq"]),
    ("exponential of a sum is the product of exponentials", ["Real.exp_add", "NormedSpace.exp_add", "Complex.exp_add"]),
    ("absolute value of a product", ["abs_mul"]),
    ("swap the order of a double sum", ["Finset.sum_comm"]),
    ("antisymmetry of less or equal", ["le_antisymm"]),
    ("theorem t (a b : ℝ) (ha : 0 < a) (hb : 0 < b) : 0 < a * b", ["mul_pos"]),
    ("theorem t (x : ℝ) (hx : 0 < x) : Real.exp (Real.log x) = x", ["Real.exp_log"]),
    ("theorem t (a b : ℕ) (h : b ≤ a) : a - b + b = a", ["Nat.sub_add_cancel", "tsub_add_cancel_of_le"]),
    ("theorem t (x y : ℝ) : |x * y| = |x| * |y|", ["abs_mul"]),
    ("theorem t (a b : ℝ) (h₁ : a ≤ b) (h₂ : b ≤ a) : a = b", ["le_antisymm"]),
]


async def evaluate(r: rag.LeanRetriever, key: str, queries, verbose: bool = False) -> tuple[int, float, float]:
    hits, mrr, total = 0, 0.0, 0.0
    for q, exp in queries:
        t0 = time.perf_counter()
        res = await (r.premises(key, q, 8) if q.startswith("theorem") else r.search(key, q, 8))
        total += time.perf_counter() - t0
        names = [x["name"] for x in res]
        rank = next((i + 1 for i, n in enumerate(names) if n in exp), None)
        hits += bool(rank)
        mrr += 1 / rank if rank else 0
        if verbose:
            print(("HIT " if rank else "MISS"), rank, q[:60], "" if rank else names[:5])
    return hits, mrr / len(queries), total / len(queries)


async def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="python -m madalean.brain.rag_eval")
    ap.add_argument("--workspace", default="lean-prover49")
    ap.add_argument("--cache", default=str(Path.home() / ".cache" / "madalean"))
    ap.add_argument("--no-famous", action="store_true")
    ap.add_argument("-v", action="store_true")
    a = ap.parse_args(argv)
    if a.no_famous:
        rag.FAMOUS.clear()
    r = rag.LeanRetriever(Path(a.cache), embeddings=False)
    t0 = time.monotonic()
    if not await r.ensure(a.workspace, timeout=1800):
        print("index unavailable", r.errors)
        return 1
    if a.workspace in r.stats:
        print("built:", r.stats[a.workspace], f"(wall {time.monotonic() - t0:.0f} s, low priority)")
    for name, qs in (("DEV", DEV), ("SET2", SET2), ("SET3", SET3)):
        h, m, t = await evaluate(r, a.workspace, qs, a.v)
        print(f"{name}: hits@8 {h}/{len(qs)}  MRR {m:.2f}  avg {t * 1000:.0f} ms/query")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1:])))
