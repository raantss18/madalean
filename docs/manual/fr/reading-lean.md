---
id: reading-lean
title: Lire un énoncé Lean
order: 110
section: use
audience: learner
summary: Décoder un énoncé Lean morceau par morceau, et repérer les traductions qui changent le sens.
---

# Lire un énoncé Lean

Lean prouve **exactement** l'énoncé Lean, pas la phrase que vous aviez en tête. Cette page apprend à lire un énoncé
assez bien pour juger une traduction, sans savoir écrire de preuves.

## L'anatomie d'un énoncé

```lean
theorem somme_pairs (a b : ℕ) (ha : Even a) (hb : Even b) : Even (a + b) := by
  sorry
```

| Morceau | Lecture |
|---|---|
| `theorem somme_pairs` | un théorème, et son nom (choisi par Madalean, unique) |
| `(a b : ℕ)` | « soient $a$ et $b$ des entiers naturels » |
| `(ha : Even a)` | hypothèse nommée `ha` : « $a$ est pair » |
| `(hb : Even b)` | hypothèse `hb` : « $b$ est pair » |
| `: Even (a + b)` | après le dernier `:` hors parenthèses vient la **conclusion** : « $a+b$ est pair » |
| `:= by sorry` | « la preuve suit, en mode tactique » ; `sorry` = preuve à compléter |

Tout ce qui est entre parenthèses avant le dernier `:` est **supposé** ; ce qui vient après est **à prouver**.
Un énoncé avec `sorry` est un énoncé sans preuve : Lean l'accepte comme énoncé, jamais comme théorème prouvé.

La même chose peut s'écrire avec des quantificateurs dans la conclusion ; c'est équivalent :

```lean
theorem somme_pairs' : ∀ a b : ℕ, Even a → Even b → Even (a + b) := by
  sorry
```

`→` se lit « implique » ; `∀ a b : ℕ,` « pour tous entiers naturels $a$, $b$ ».

## L'en-tête

Les énoncés de l'espace « Prouveur » commencent par un en-tête fixe :

```lean
import Mathlib
import Aesop
set_option maxHeartbeats 400000
open BigOperators Real Nat Topology Rat
```

`import Mathlib` charge la bibliothèque mathématique ; `set_option maxHeartbeats` augmente le temps de calcul
autorisé ; `open …` permet d'écrire `π` ou `√` sans préfixe. Cet en-tête ne change pas le sens de l'énoncé, mais
`open Nat Real` rend certains noms ambigus (`sqrt` existe dans les deux) : regardez les types.

## Les types : de quels nombres parle-t-on ?

| Lean | Mathématiques | Attention |
|---|---|---|
| `ℕ` | $\mathbb{N} = \{0, 1, 2, \dots\}$ | contient 0 ; soustraction et division tronquées (voir plus bas) |
| `ℤ` | $\mathbb{Z}$ | `/` est la division euclidienne : le reste `%` est toujours $\ge 0$, `-7 / 2 = -4` |
| `ℚ`, `ℝ`, `ℂ` | $\mathbb{Q}$, $\mathbb{R}$, $\mathbb{C}$ | division par zéro définie et égale à 0 |
| `Finset ℕ` | ensemble fini d'entiers | `Finset.range n` $= \{0, \dots, n-1\}$ |
| `Set ℝ` | partie de $\mathbb{R}$ | |
| `ℕ → ℝ` | suite réelle | `u n` est le terme $u_n$ |

Quand un même énoncé mélange plusieurs types, Lean insère des **conversions** : `(n : ℝ)` ou `↑n` désigne l'entier
$n$ vu comme réel. Un énoncé comme `(n : ℝ) / 2` n'a pas le même sens que `n / 2` sur `ℕ`.

## Les pièges qui changent le sens

Ces traductions sont acceptées par Lean, mais ne disent pas ce que l'on croit.

1. **Soustraction sur ℕ** : `2 - 5 = 0` dans `ℕ`. Un énoncé sur $a - b$ avec $a < b$ possible doit être écrit dans
   `ℤ` ou `ℝ`.
2. **Division sur ℕ et ℤ** : `7 / 2 = 3`. « $n/2$ » en mathématiques est souvent un rationnel.
3. **Division par zéro** : dans `ℝ`, `x / 0 = 0` par convention. Un énoncé `x / y * y = x` est faux pour
   `y = 0`, et une traduction qui oublie l'hypothèse `y ≠ 0` peut devenir fausse… ou triviale.
4. **Fonctions totales** : `Real.sqrt (-1) = 0`, `Real.log 0 = 0`. Une hypothèse oubliée ($x > 0$) ne provoque
   pas d'erreur.
5. **Hypothèses contradictoires** : si les hypothèses ne peuvent pas être toutes vraies, *n'importe quelle*
   conclusion se prouve. Une preuve très courte d'un énoncé difficile est un signal d'alarme.
6. **Indices** : `Finset.range n` commence à 0. $\sum_{k=1}^{n} k$ se traduit
   `∑ k in Finset.Icc 1 n, k` ; avec `Finset.range n` on somme de 0 à $n-1$.
7. **Quantificateurs** : l'ordre compte. `∀ ε > 0, ∃ N, …` n'est pas `∃ N, ∀ ε > 0, …`.
8. **« Il existe un unique »** s'écrit `∃! x, P x` ; `∃ x, P x` n'affirme pas l'unicité.

Notation : dans les versions récentes de Mathlib, la somme s'écrit `∑ k ∈ Finset.Icc 1 n, k` ; l'espace
« Prouveur » (Lean 4.9) utilise encore `∑ k in …`.

## Une méthode de relecture

1. Lisez la conclusion seule : est-ce bien ce que vous voulez prouver ?
2. Listez les hypothèses : en manque-t-il ? y en a-t-il de trop (une hypothèse superflue rend l'énoncé plus faible) ?
3. Vérifiez le type de chaque variable.
4. Cherchez une division, une soustraction, une racine, un logarithme : sont-ils dans le bon type, avec les bonnes
   hypothèses ?
5. Essayez de nier l'énoncé sur un petit exemple. Si l'énoncé Lean est vrai et le vôtre faux (ou l'inverse), la
   traduction est fausse.

Le panneau « Comprendre » (mode *Apprendre*) donne une glose ligne par ligne, écrite par un modèle : elle aide à lire,
mais elle peut se tromper aussi ; le code fait foi. Le vocabulaire est dans le [Glossaire](glossary.md).
