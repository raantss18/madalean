"""Conductor answers: French accents re-read in a legacy code page are repaired (seen on the real API, 2026-11-22)."""
from madalean.brain._util import fix_mojibake, fix_mojibake_deep, looks_mojibake
from madalean.brain.conductor import validate_plan

GOOD = "Prouver le théorème, carrée, « det A ≠ 0 », français, ∀ x ∈ ℝ, Écrire, à côté, déjà, Γ ⊆ Δ"


def test_real_answers_are_repaired():
    assert fix_mojibake("Je cherche le thĂ©orĂšme de Mathlib, je prouve l'Ă©quivalence") == \
        "Je cherche le théorème de Mathlib, je prouve l'équivalence"
    assert fix_mojibake("On formalise l'Ă©quivalence Â«A inversible ssi det A â‰  0Â» pour une matrice carrĂ©e") == \
        "On formalise l'équivalence «A inversible ssi det A ≠ 0» pour une matrice carrée"
    assert fix_mojibake("l'Γ©quivalence entre inversibilitΓ© d'une matrice carrΓ©e") == \
        "l'équivalence entre inversibilité d'une matrice carrée"
    assert fix_mojibake("thÃ©orÃ¨me") == "théorème"


def test_correct_text_is_untouched():
    assert fix_mojibake(GOOD) == GOOD and not looks_mojibake(GOOD)
    assert fix_mojibake_deep({"a": [GOOD, 3]}) == {"a": [GOOD, 3]}


def test_unrepairable_summary_is_dropped():
    raw = {"difficulty": "easy", "summary": "thĂš", "tasks": [{"id": "t1", "kind": "prove", "goal": "x"}]}
    diff, summary, tasks = validate_plan(raw, {})
    assert summary == "" and tasks
