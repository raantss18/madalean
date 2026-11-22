"""Primality certificates (Pratt / Lucas) and modular powers as Lean proofs (session S-AT, DECISIONS D52).

A certificate for a prime p is a tree: a witness `a` and the prime factorisation of p − 1, each prime factor with its
own certificate (or none when it is below `SMALL`, where `norm_num` proves primality by trial division). Lean checks
it with Mathlib's `lucas_primality`: a^(p−1) = 1 and a^((p−1)/q) ≠ 1 in ZMod p for every prime q dividing p − 1.

Modular powers are never computed as a^e (astronomically large). The generated file defines a square-and-multiply
function `madalean_cert_powmod` (plain structural recursion on a fuel argument), proves once and for all that it
equals `a ^ e % p`, and each concrete power is then a `decide` on that function: Lean's kernel evaluates about one
multiplication per bit of the exponent. Only kernel-checked tactics are used (no `native_decide`)."""
from __future__ import annotations

SMALL = 100_000          # below: `norm_num` (trial division, measured < 3 s on both workspaces)
MAX_BITS = 400           # larger primes are refused
MAX_NODES = 60

POW_HELPERS = """\
def madalean_cert_powmod : ℕ → ℕ → ℕ → ℕ → ℕ
  | 0, _, _, p => 1 % p
  | f + 1, a, e, p =>
    if e % 2 = 0 then madalean_cert_powmod f a (e / 2) p ^ 2 % p
    else madalean_cert_powmod f a (e / 2) p ^ 2 % p * a % p

theorem madalean_cert_powmod_eq : ∀ (f a e p : ℕ), e < 2 ^ f → madalean_cert_powmod f a e p = a ^ e % p := by
  intro f
  induction f with
  | zero =>
    intro a e p h
    have he : e = 0 := by omega
    subst he
    simp [madalean_cert_powmod]
  | succ f ih =>
    intro a e p h
    have hp : 2 ^ (f + 1) = 2 * 2 ^ f := by ring
    rcases Nat.even_or_odd' e with ⟨k, hk | hk⟩
    · subst hk
      have m : 2 * k % 2 = 0 := by omega
      have d : 2 * k / 2 = k := by omega
      have hk : k < 2 ^ f := by omega
      have h0 : a ^ k % p ≡ a ^ k [MOD p] := Nat.mod_modEq _ _
      have h2 : (a ^ k % p) ^ 2 ≡ (a ^ k) ^ 2 [MOD p] := h0.pow 2
      rw [← pow_mul, mul_comm k 2] at h2
      rw [madalean_cert_powmod, if_pos m, d, ih a k p hk]
      exact h2
    · subst hk
      have m : ¬ ((2 * k + 1) % 2 = 0) := by omega
      have d : (2 * k + 1) / 2 = k := by omega
      have hk : k < 2 ^ f := by omega
      have h0 : a ^ k % p ≡ a ^ k [MOD p] := Nat.mod_modEq _ _
      have h2 : (a ^ k % p) ^ 2 % p ≡ (a ^ k) ^ 2 [MOD p] := (Nat.mod_modEq _ _).trans (h0.pow 2)
      have h3 := h2.mul_right a
      rw [← pow_mul, mul_comm k 2, ← pow_succ] at h3
      rw [madalean_cert_powmod, if_neg m, d, ih a k p hk]
      exact h3
"""
HELPERS = POW_HELPERS + """
theorem madalean_cert_zmod_one (f a e p : ℕ) (hf : e < 2 ^ f) (h : madalean_cert_powmod f a e p = 1 % p) :
    ((a : ℕ) : ZMod p) ^ e = 1 := by
  have h1 : a ^ e ≡ 1 [MOD p] := by
    show a ^ e % p = 1 % p
    rw [← madalean_cert_powmod_eq f a e p hf]
    exact h
  have h2 := (ZMod.natCast_eq_natCast_iff (a ^ e) 1 p).mpr h1
  simpa using h2

theorem madalean_cert_zmod_ne (f a e p : ℕ) (hf : e < 2 ^ f) (h : madalean_cert_powmod f a e p ≠ 1 % p) :
    ((a : ℕ) : ZMod p) ^ e ≠ 1 := by
  intro h1
  apply h
  have h2 : ((a ^ e : ℕ) : ZMod p) = ((1 : ℕ) : ZMod p) := by simpa using h1
  have h3 : a ^ e % p = 1 % p := (ZMod.natCast_eq_natCast_iff (a ^ e) 1 p).mp h2
  rw [madalean_cert_powmod_eq f a e p hf]
  exact h3
"""
LT = "first | (norm_num; done) | (set_option exponentiation.threshold 100000 in norm_num; done) | decide"


class BadCertificate(ValueError):
    pass


def validate(cert: dict, depth: int = 0, count: list | None = None) -> int:
    """Shape and size of a certificate tree (the mathematics is Lean's job). Returns the number of nodes."""
    count = count if count is not None else [0]
    count[0] += 1
    if depth > 14 or count[0] > MAX_NODES:
        raise BadCertificate("certificate too large")
    p = cert.get("p") if isinstance(cert, dict) else None
    if not isinstance(p, int) or isinstance(p, bool) or p < 2:
        raise BadCertificate("bad prime")
    if p < SMALL:
        return count[0]
    if p.bit_length() > MAX_BITS:
        raise BadCertificate("prime too large")
    a, fs = cert.get("a"), cert.get("factors")
    if not isinstance(a, int) or isinstance(a, bool) or not 1 < a < p or not isinstance(fs, list) or not fs \
            or len(fs) > 40:
        raise BadCertificate("bad witness")
    for f in fs:
        if not (isinstance(f, dict) and isinstance(f.get("e"), int) and 0 < f["e"] < 4000):
            raise BadCertificate("bad factor")
        validate(f, depth + 1, count)
    return count[0]


def name_of(p: int) -> str:
    return f"madalean_cert_prime_{p}"


def _indent(lines: list[str], n: int = 2) -> list[str]:
    return [" " * n + ln for ln in lines]


def _node(cert: dict) -> list[str]:
    """Tactic lines closing `Nat.Prime p` for p ≥ SMALL; big prime factors are their own theorems."""
    p, a, fs = cert["p"], cert["a"], cert["factors"]
    fuel = (p - 1).bit_length()
    out: list[str] = []
    for j, f in enumerate(fs):
        out.append(f"have hp{j} : Nat.Prime {f['p']} := " + ("by norm_num" if f["p"] < SMALL else name_of(f["p"])))
    out.append(f"have hf : {p} - 1 = " + " * ".join(f"{f['p']} ^ {f['e']}" for f in fs) + f" := by {LT}")
    out.append(f"refine lucas_primality {p} (({a} : ℕ) : ZMod {p})")
    out.append(f"  (madalean_cert_zmod_one {fuel} {a} ({p} - 1) {p} (by {LT}) (by set_option maxRecDepth 100000 in decide)) ?_")
    out.append("intro q hq hdvd")
    out.append("rw [hf] at hdvd")

    def leaf(j: int) -> list[str]:
        return [f"have hq := (Nat.prime_dvd_prime_iff_eq hq hp{j}).mp (hq.dvd_of_dvd_pow hdvd)",
                "subst hq",
                f"exact madalean_cert_zmod_ne {fuel} {a} (({p} - 1) / {fs[j]['p']}) {p} (by {LT}) (by set_option maxRecDepth 100000 in decide)"]

    def cases(i: int) -> list[str]:
        if i == 0:
            return leaf(0)
        return (["rcases (Nat.Prime.dvd_mul hq).mp hdvd with hdvd | hdvd"]
                + ["· " + ln if k == 0 else "  " + ln for k, ln in enumerate(cases(i - 1))]
                + ["· " + ln if k == 0 else "  " + ln for k, ln in enumerate(leaf(i))])
    return out + cases(len(fs) - 1)


def nodes(cert: dict, acc: dict | None = None) -> dict:
    """{p: node} for every prime ≥ SMALL of the tree, children before parents."""
    acc = acc if acc is not None else {}
    if cert["p"] >= SMALL and cert["p"] not in acc:
        for f in cert["factors"]:
            nodes(f, acc)
        acc[cert["p"]] = cert
    return acc


def proof(cert: dict) -> tuple[str, str]:
    """(helper declarations, term proving `Nat.Prime p`) from the certificate tree; raises BadCertificate when the
    tree does not have the shape of one (its mathematics is left to Lean: a wrong tree gives a refused proof). Below SMALL there is no helper and the term is `(by norm_num)`."""
    validate(cert)
    if cert["p"] < SMALL:
        return "", "(by norm_num)"
    parts = [HELPERS]
    for p, node in nodes(cert).items():
        parts.append(f"theorem {name_of(p)} : Nat.Prime {p} := by\n" + "\n".join(_indent(_node(node))) + "\n")
    return "\n".join(parts), name_of(cert["p"])
