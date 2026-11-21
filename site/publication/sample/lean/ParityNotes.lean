import Mathlib

/-! Parité des carrés d'entiers — exemple du gabarit de publication de Madalean. -/

def IsEven (n : ℤ) : Prop := ∃ k, n = 2 * k

theorem isEven_add {a b : ℤ} (ha : IsEven a) (hb : IsEven b) : IsEven (a + b) := by
  obtain ⟨k, rfl⟩ := ha
  obtain ⟨l, rfl⟩ := hb
  exact ⟨k + l, by ring⟩

theorem isEven_iff_emod (n : ℤ) : IsEven n ↔ n % 2 = 0 := by
  constructor
  · rintro ⟨k, rfl⟩
    simp
  · intro h
    exact ⟨n / 2, by omega⟩

theorem isEven_of_isEven_sq {n : ℤ} (h : IsEven (n ^ 2)) : IsEven n := by
  rw [isEven_iff_emod] at h ⊢
  rcases Int.emod_two_eq_zero_or_one n with h0 | h1
  · exact h0
  · exfalso
    have : n ^ 2 % 2 = 1 := by
      rw [pow_two, Int.mul_emod, h1]
      norm_num
    omega

theorem isEven_sq_add_self (n : ℤ) : IsEven (n ^ 2 + n) := by
  sorry
