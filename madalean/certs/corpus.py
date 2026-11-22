"""The certificate corpus (session S-AT): about fifty statements across the kinds, with what is expected of each.

Used by the tests (real Sage, real Lean on every built workspace) and by `scripts/dev/cert_bench.py`, whose table
is in docs/PERFORMANCE.md. `expect` is the outcome's status; `kind` the kind that must produce it."""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass

from .. import leancheck


@dataclass(frozen=True)
class Case:
    id: str
    kind: str
    lean: str                    # everything between `theorem <name>` and `:= by sorry`
    expect: str = "verified"


CASES = [
    # --- primality, composites, plain arithmetic, modular powers
    Case("prime-97", "prime", ": Nat.Prime 97"),
    Case("prime-1e9+7", "prime", ": Nat.Prime 1000000007"),
    Case("prime-m61", "prime", ": Nat.Prime (2 ^ 61 - 1)"),
    Case("prime-m127", "prime", ": Nat.Prime (2 ^ 127 - 1)"),
    Case("prime-curve25519", "prime", ": Nat.Prime (2 ^ 255 - 19)"),
    Case("prime-293bits", "prime", ": Nat.Prime (7 * 2 ^ 290 + 1)"),
    Case("composite-fermat5", "composite", ": ¬ Nat.Prime 4294967297"),
    Case("composite-m67", "composite", ": ¬ Nat.Prime (2 ^ 67 - 1)"),
    Case("composite-1000001", "composite", ": ¬ Nat.Prime 1000001"),
    Case("arith-gcd", "arith", ": Nat.gcd 123456 7890 = 6"),
    Case("arith-lcm", "arith", ": Nat.lcm 12 18 = 36"),
    Case("arith-dvd", "arith", ": (641 : ℕ) ∣ 4294967297"),
    Case("arith-modeq", "arith", ": (17 * 2753 : ℕ) ≡ 1 [MOD 3120]"),
    Case("arith-int", "arith", ": (2 : ℤ) ^ 10 - 1 = 1023"),
    Case("arith-factorial", "arith", ": Nat.factorial 10 = 3628800"),
    Case("powmod-1e6", "powmod", ": 2 ^ 1000000 % 1000003 = 250001"),
    Case("powmod-1e18", "powmod", ": 3 ^ (10 ^ 18) % 1000000007 = 246336683"),
    Case("powmod-modeq", "powmod", ": 7 ^ 2024 ≡ 3 [MOD 13]"),
    # --- polynomial identities and consequences of polynomial equations
    Case("identity-cube", "identity", "(x y : ℝ) : (x + y) ^ 3 = x ^ 3 + 3 * x ^ 2 * y + 3 * x * y ^ 2 + y ^ 3"),
    Case("identity-int", "identity", "(a b : ℤ) : (a + b) * (a - b) = a ^ 2 - b ^ 2"),
    Case("identity-germain", "identity",
         "(a b : ℚ) : a ^ 4 + 4 * b ^ 4 = (a ^ 2 + 2 * b ^ 2 + 2 * a * b) * (a ^ 2 + 2 * b ^ 2 - 2 * a * b)"),
    Case("ideal-sum-product", "ideal", "(x y : ℝ) (h₀ : x + y = 3) (h₁ : x * y = 2) : x ^ 2 + y ^ 2 = 5"),
    Case("ideal-cubes", "ideal", "(a b c : ℝ) (h : a + b + c = 0) : a ^ 3 + b ^ 3 + c ^ 3 = 3 * a * b * c"),
    Case("ideal-int", "ideal", "(x y : ℤ) (h₀ : x + y = 3) (h₁ : x - y = 1) : x * x - y * y = 3"),
    Case("ideal-system", "ideal", "(x y : ℚ) (h₀ : 2 * x + y = 5) (h₁ : x - y = 1) : x = 2"),
    Case("ideal-radical", "ideal", "(x y : ℚ) (h₀ : x ^ 2 = y) (h₁ : y = 0) : x ^ 3 = 0"),
    Case("ideal-power", "ideal", "(x y : ℝ) (h₀ : (x - y) ^ 2 = 0) : x = y"),
    # --- linear arithmetic
    Case("linear-bound", "linear",
         "(x y z : ℝ) (h₁ : x + 2 * y ≤ 4) (h₂ : y - z ≤ 1) (h₃ : 3 * z ≤ 2) : x + 3 * y ≤ 17 / 3"),
    Case("linear-infeasible", "linear", "(x y : ℚ) (h₁ : x + y ≤ 1) (h₂ : x ≥ 2) (h₃ : y ≥ 0) : False"),
    Case("linear-forall", "linear", ": ∀ x y : ℝ, x ≤ y → 2 * x ≤ x + y"),
    Case("linear-strict", "linear", "(a b : ℝ) (h₁ : a < b) (h₂ : 0 < a) : a / 2 < b"),
    # --- polynomial inequalities over ℝ (sums of squares)
    Case("sos-amgm2", "sos", "(x y : ℝ) : x ^ 2 + y ^ 2 ≥ 2 * x * y"),
    Case("sos-form", "sos", "(x y : ℝ) : x ^ 2 + x * y + y ^ 2 ≥ 0"),
    Case("sos-quartic", "sos", "(x : ℝ) : x ^ 4 - 2 * x ^ 2 + 2 > 0"),
    Case("sos-three", "sos", "(a b c : ℝ) : a ^ 2 + b ^ 2 + c ^ 2 ≥ a * b + b * c + c * a"),
    Case("sos-hyps", "sos", "(x y : ℝ) (h₀ : 0 ≤ x) (h₁ : x ≤ y) : x ^ 2 ≤ y ^ 2"),
    Case("sos-quartic2", "sos", "(x y : ℝ) : x ^ 4 + y ^ 4 ≥ x ^ 3 * y + x * y ^ 3"),
    Case("sos-nonneg-vars", "sos",
         "(x y : ℝ) (h₀ : 0 ≤ x) (h₁ : 0 ≤ y) : x ^ 3 + y ^ 3 ≥ x ^ 2 * y + x * y ^ 2"),
    Case("sos-product", "sos", "(a b : ℝ) (h₀ : 1 ≤ a) (h₁ : 1 ≤ b) : a * b + 1 ≥ a + b"),
    # --- existence and counterexamples
    Case("exists-bezout", "exists", ": ∃ u v : ℤ, 123456 * u + 7890 * v = 6"),
    Case("exists-inverse", "exists", ": ∃ x : ℤ, 17 * x ≡ 1 [ZMOD 3120]"),
    Case("exists-inverse-nat", "exists", ": ∃ x : ℕ, 65537 * x % 1000000007 = 1"),
    Case("exists-circle", "exists", ": ∃ x y : ℤ, x ^ 2 + y ^ 2 = 25 ∧ x > 0 ∧ y > x"),
    Case("exists-root", "exists", ": ∃ x : ℚ, 6 * x ^ 2 - 5 * x + 1 = 0"),
    Case("exists-prime", "exists", ": ∃ p : ℕ, Nat.Prime p ∧ p > 1000 ∧ p % 4 = 1"),
    Case("exists-factors", "exists", ": ∃ a b : ℕ, a * b = 8633 ∧ 1 < a ∧ a < b"),
    Case("exists-system", "exists", ": ∃ x y : ℚ, x + y = 7 / 2 ∧ x * y = 3 ∧ x < y"),
    Case("cex-euler", "counterexample", ": ¬ ∀ n : ℕ, Nat.Prime (n ^ 2 + n + 41)"),
    Case("cex-real", "counterexample", ": ¬ ∀ x y : ℝ, x ^ 2 + y ^ 2 ≥ 3 * x * y"),
    Case("cex-freshman", "counterexample", ": ¬ ∀ a b : ℤ, (a + b) ^ 2 = a ^ 2 + b ^ 2"),
    # --- certified numerics
    Case("numeric-sqrt", "numeric", ": Real.sqrt 2 + Real.sqrt 3 < 3.15"),
    Case("numeric-sqrt-lower", "numeric", ": (1.41 : ℝ) < Real.sqrt 2"),
    Case("numeric-pi-square", "numeric", ": Real.pi ^ 2 < 10"),
    Case("numeric-e-pi", "numeric", ": Real.exp 1 + Real.pi < 5.86"),
    Case("numeric-log", "numeric", ": Real.log 2 > 0.69"),
    Case("numeric-sqrt-pi", "numeric", ": Real.sqrt 10 > Real.pi"),
    # --- finite exhaustive claims
    Case("finite-ball", "finite", ": ∀ n < 30, (n ^ 2 + n) % 2 = 0"),
    Case("finite-imp", "finite", ": ∀ n : ℕ, n < 200 → (n ^ 3 + 2 * n) % 3 = 0"),
    Case("finite-two", "finite", ": ∀ a < 12, ∀ b < 12, (a + b) ^ 2 % 2 = (a ^ 2 + b ^ 2) % 2"),
    Case("finite-growth", "finite", ": ∀ n : ℕ, n ≤ 60 → n ^ 2 < 2 ^ n + 9"),
    # --- false claims: reported with their witness, never proved
    Case("false-prime", "prime", ": Nat.Prime 91", "refuted"),
    Case("false-finite", "finite", ": ∀ n < 50, Nat.Prime (n ^ 2 + n + 41)", "refuted"),
    Case("false-identity", "identity", "(a b : ℝ) : (a + b) ^ 2 = a ^ 2 + b ^ 2", "refuted"),
    Case("false-arith", "arith", ": Nat.gcd 12 18 = 4", "refuted"),
]


def statement(c: Case) -> str:
    name = "cert_" + c.id.replace("-", "_").replace("+", "p")
    return f"{leancheck.GOEDEL_HEADER}theorem {name} {c.lean} := by sorry\n"


async def run(cases, ws, lean, produce, *, timeout_s: int = 240, sage_seconds: float = 40, parallel: int = 3):
    """[(case, Outcome)] with real checks: `lean` is a LeanRunner (fresh strict check), `produce` a producer."""
    from . import engine
    sem = asyncio.Semaphore(parallel)

    async def one(c: Case):
        async def check(code: str, name: str):
            return await lean.check(code, ws, timeout_s, name)
        async with sem:
            t0 = time.monotonic()
            o = await engine.certify(statement(c), ws, check, produce, sage_seconds=sage_seconds)
            o.seconds = time.monotonic() - t0
            return c, o
    return await asyncio.gather(*[one(c) for c in cases])
