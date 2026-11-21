---
id: tactics
title: Premières tactiques
order: 420
section: reference
audience: learner
summary: Ce que font les tactiques les plus courantes de Lean 4 et Mathlib, avec un exemple chacune, et quand elles échouent.
---

# Premières tactiques

Une preuve en mode tactique (`:= by …`) est une suite d'instructions qui transforment le **but** (ce qui reste à
prouver, affiché après `⊢`) jusqu'à ce qu'il n'en reste plus. Les exemples supposent `import Mathlib`. Le
comportement exact d'une tactique dépend de la version de Mathlib ; ce qui suit vaut pour les deux espaces de
Madalean, sauf mention.

## Structurer

| Tactique | Effet | Exemple de but |
|---|---|---|
| `intro x` | introduit une variable ou une hypothèse : pour `∀ x, P x` ou `P → Q` | `⊢ ∀ n : ℕ, n + 0 = n` → `intro n` |
| `exact e` | ferme le but avec un terme exactement du bon type | `exact ha` quand `ha : P` et `⊢ P` |
| `apply f` | réduit le but aux hypothèses de `f` | `⊢ 0 < a * b` → `apply mul_pos` laisse `0 < a` et `0 < b` |
| `refine ⟨?_, ?_⟩` | comme `exact`, avec des trous `?_` qui deviennent des buts | |
| `constructor` | découpe `P ∧ Q` (deux buts) ou `P ↔ Q` (les deux sens) | |
| `use 3` | fournit le témoin d'un `∃` | `⊢ ∃ n : ℕ, n * n = 9` → `use 3` |
| `obtain ⟨x, hx⟩ := h` | déballe `h : ∃ x, P x` (ou `h : P ∧ Q`) | |
| `rcases h with h1 \| h2` | cas d'une disjonction `h : P ∨ Q` | |
| `left`, `right` | choisit un côté d'un `∨` à prouver | |
| `have h : P := by …` | prouve un résultat intermédiaire et l'ajoute aux hypothèses | |
| `show P` | réécrit le but sous une forme égale par définition (lisibilité) | |
| `specialize h 2` | applique une hypothèse universelle à une valeur | |
| `exfalso` | remplace le but par `False` | |
| `by_contra h` | raisonnement par l'absurde : ajoute la négation du but | |
| `push_neg` | pousse les négations vers l'intérieur : `¬ ∀ x, P x` devient `∃ x, ¬ P x` | |
| `contradiction` | ferme le but si les hypothèses se contredisent directement | `h : P` et `h' : ¬ P` |

## Récurrence et cas

```lean
theorem somme_impairs (n : ℕ) : ∑ i in Finset.range n, (2 * i + 1) = n ^ 2 := by
  induction n with
  | zero => simp
  | succ n ih =>
    rw [Finset.sum_range_succ, ih]
    ring
```

`induction n with | zero => … | succ n ih => …` produit le cas de base et l'hérédité ; `ih` est l'hypothèse de
récurrence. `rcases`/`cases` traitent les cas d'un type inductif ou d'une disjonction ; `interval_cases n` énumère
les valeurs d'un entier borné par les hypothèses. (Dans l'espace « Lean récent », écrivez `∑ i ∈ Finset.range n`.)

## Réécrire et simplifier

| Tactique | Effet | Échoue quand |
|---|---|---|
| `rw [h]` | remplace le membre gauche de `h : a = b` par le membre droit dans le but ; `rw [← h]` dans l'autre sens ; `rw [h] at h'` dans une hypothèse | le motif n'apparaît pas tel quel dans le but |
| `simp` | simplifie avec les lemmes marqués `@[simp]` de Mathlib ; ferme le but s'il devient trivial | il n'y a rien à simplifier |
| `simp only [a, b]` | simplifie avec ces lemmes seulement : plus prévisible et plus rapide | |
| `simp at h` | simplifie une hypothèse | |
| `norm_num` | calcule sur des nombres explicites : `2 ^ 10 = 1024`, `(7 : ℝ) / 2 > 3`, `Nat.Prime 97` | le but contient des variables qu'il ne sait pas éliminer |
| `field_simp` | chasse les dénominateurs dans un corps (demande souvent `h : x ≠ 0`) | |
| `unfold f` | déplie une définition | |
| `ext x` | égalité de fonctions ou d'ensembles : se ramène à tout `x` | |

## Arithmétique et inégalités

| Tactique | Domaine | Ne fait pas |
|---|---|---|
| `ring` | égalités dans un anneau commutatif : `(a + b) ^ 2 = a ^ 2 + 2 * a * b + b ^ 2` | les inégalités ; les égalités qui demandent une hypothèse |
| `linarith` | combinaisons **linéaires** d'hypothèses et d'inégalités, sur un corps ordonné (`ℚ`, `ℝ`) ; marche aussi souvent sur `ℕ` et `ℤ` | les produits de variables |
| `nlinarith` | comme `linarith`, en ajoutant des produits d'hypothèses ; on l'aide en donnant des faits : `nlinarith [sq_nonneg (a - b)]` | garantie : c'est une heuristique |
| `positivity` | buts `0 < e`, `0 ≤ e`, `e ≠ 0` quand la forme de `e` le montre (carrés, sommes de positifs, exponentielles…) | utiliser des hypothèses compliquées |
| `omega` | arithmétique linéaire **exacte** sur `ℕ` et `ℤ`, avec `/` et `%` par des constantes | les produits de variables ; les réels |
| `decide` | propositions décidables sur des valeurs **concrètes** : `Nat.Prime 7` si l'instance le permet, `2 ∣ 10` | les variables libres ; les grands calculs (lent) |
| `gcongr` | « même forme des deux côtés » : `a ≤ b → a + c ≤ b + c`, laisse les comparaisons des morceaux | |

Exemple :

```lean
theorem am_gm_deux (a b : ℝ) : 2 * a * b ≤ a ^ 2 + b ^ 2 := by
  nlinarith [sq_nonneg (a - b)]
```

Ici $a^2 + b^2 - 2ab = (a-b)^2 \ge 0$ : le fait donné à `nlinarith` suffit, la combinaison est linéaire en ce fait.

## Chercher

| Tactique | Effet |
|---|---|
| `exact?` | cherche dans Mathlib un lemme qui ferme le but et propose `exact …` |
| `apply?` | propose des lemmes applicables |
| `aesop` | recherche automatique de preuve (règles et `simp`) |
| `tauto` | logique propositionnelle |

Madalean **refuse `exact?` et `apply?` dans une preuve finale** : ce sont des outils de recherche, à remplacer par le
lemme qu'ils trouvent. Ils restent utiles dans un carnet ou un bloc Lean d'une note.

## Lire une erreur

| Message de Lean | Sens habituel |
|---|---|
| `unknown identifier 'foo'` / `unknown constant` | le nom n'existe pas dans cette version de Mathlib (renommé, ou inventé par le modèle) |
| `type mismatch` | le terme n'a pas le type attendu : souvent une conversion `ℕ`/`ℝ` manquante |
| `unsolved goals` | la preuve s'arrête alors qu'il reste des buts (affichés) |
| `linarith failed` | les hypothèses données ne suffisent pas linéairement : ajoutez des faits |
| `motive is not type correct` | `rw` ne peut pas réécrire à cet endroit ; essayez `simp only` ou `conv` |
| `maximum recursion depth` / `deterministic timeout` | une tactique cherche trop longtemps : rendez la preuve plus explicite |
| `declaration uses 'sorry'` | la preuve contient un trou : elle n'est pas acceptée |
