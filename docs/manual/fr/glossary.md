---
id: glossary
title: Glossaire Lean
order: 410
section: reference
audience: learner
summary: Le vocabulaire de Lean et de Mathlib nécessaire pour lire les énoncés et les preuves.
---

# Glossaire Lean

Les termes sont groupés par thème. Pour les tactiques, voir [Premières tactiques](tactics.md).

Dans l'application, l'écran **Glossaire** reprend ces termes et bien d'autres (environ 250, classés par catégorie
et par niveau débutant / intermédiaire / avancé), avec pour chacun le sens, la forme Lean, un petit exemple, les
entrées liées, les déclarations Mathlib correspondantes et vos dossiers qui l'utilisent. Il sert aussi d'aide au
survol des énoncés en mode Apprendre.

## Logique et notations

| Lean | Se lit | Remarque |
|---|---|---|
| `∀ x, P x` | pour tout $x$, $P(x)$ | `∀ x > 0, …` abrège `∀ x, x > 0 → …` |
| `∃ x, P x` | il existe $x$ tel que $P(x)$ | `∃! x, P x` : il existe un unique $x$ |
| `P → Q` | $P$ implique $Q$ | aussi le type des fonctions de `P` vers `Q` |
| `P ↔ Q` | $P$ si et seulement si $Q$ | |
| `P ∧ Q`, `P ∨ Q` | et, ou | |
| `¬ P` | non $P$ | défini comme `P → False` |
| `a ≠ b` | $a \neq b$ | abrège `¬ (a = b)` |
| `True`, `False` | le vrai, le faux | propositions |
| `a ∣ b` | $a$ divise $b$ | barre verticale spéciale, tapée `\mid` ; ce n'est pas la barre `\|` du clavier |
| `a % b` | reste de la division | |
| `x⁻¹` | inverse | `0⁻¹ = 0` dans un corps |
| `↑n`, `(n : ℝ)` | $n$ vu dans un autre type | conversion (*coercion*) |
| `fun x => e` | $x \mapsto e$ | aussi écrit `λ x => e` ou `fun x ↦ e` |
| `f x` | $f(x)$ | l'application s'écrit sans parenthèses |
| `∑ i in s, f i` | $\sum_{i \in s} f(i)$ | `∑ i ∈ s, f i` dans les versions récentes |
| `∏ i in s, f i` | $\prod_{i \in s} f(i)$ | idem |
| `Finset.range n` | $\{0, \dots, n-1\}$ | |
| `Finset.Icc a b` | $\{a, \dots, b\}$ | aussi `Ico`, `Ioc`, `Ioo` |
| `\|x\|` | valeur absolue | |
| `⌊x⌋`, `⌈x⌉` | partie entière, plafond | `Int.floor`, `Int.ceil` |

## Déclarations

| Terme | Sens |
|---|---|
| `theorem`, `lemma` | un énoncé avec sa preuve (Madalean normalise `lemma` en `theorem`) |
| `example` | un théorème sans nom |
| `def` | une définition |
| `abbrev` | une définition que Lean déplie volontiers |
| `structure`, `class`, `instance` | types à champs ; classes de types (« ℝ est un corps ») et leurs instances |
| `axiom` | un énoncé admis sans preuve ; interdit dans une preuve acceptée par Madalean |
| `sorry` | « preuve à compléter » : Lean accepte provisoirement, mais signale un trou |
| `variable` | déclare des variables communes à plusieurs énoncés |
| `namespace X … end X` | préfixe les noms : `X.foo` |
| `open X` | permet d'écrire `foo` au lieu de `X.foo` |
| `import` | charge une bibliothèque (`import Mathlib`) |
| `#check e` | affiche le type de `e` |
| `#eval e` | calcule `e` |

## Arguments

| Écriture | Sens |
|---|---|
| `(x : α)` | argument explicite, à donner |
| `{x : α}` | argument implicite, deviné par Lean |
| `[inst : Field α]` | argument d'instance, trouvé par Lean (« α est un corps ») |
| `(h : P)` | une hypothèse nommée `h` ; une preuve de `P` |

## Types et univers

| Terme | Sens |
|---|---|
| `Prop` | le type des propositions ; une preuve de `P : Prop` est un terme de type `P` |
| `Type` | le type des types « ordinaires » (`ℕ : Type`) |
| `ℕ`, `ℤ`, `ℚ`, `ℝ`, `ℂ` | entiers naturels (avec 0), relatifs, rationnels, réels, complexes |
| `Fin n` | $\{0, \dots, n-1\}$ comme type |
| `Set α`, `Finset α` | parties de `α` ; parties finies (calculables) |
| `α × β` | produit cartésien ; `p.1`, `p.2` les composantes |
| `List α` | listes |
| `Polynomial R` (`R[X]`) | polynômes à coefficients dans `R` |
| `Matrix m n R` | matrices |

## Preuves

| Terme | Sens |
|---|---|
| but (*goal*) | ce qu'il reste à prouver, affiché `⊢ P` |
| hypothèse | ce qui est supposé, au-dessus du `⊢` |
| tactique | une instruction qui transforme le but (`intro`, `simp`…) |
| `by` | passe en mode tactique |
| mode terme | une preuve écrite comme un terme : `fun h => h.1` |
| `h.1`, `h.2` | les deux parties d'une hypothèse `h : P ∧ Q` |
| `⟨a, b⟩` | construit un couple, une conjonction, ou un témoin avec sa preuve |
| `·` | ouvre le traitement d'un des buts |
| `<;>` | applique la tactique suivante à tous les buts produits |
| `rfl` | « par définition » : les deux côtés sont égaux après calcul |

## Écosystème

| Terme | Sens |
|---|---|
| Lean 4 | le langage et le vérificateur de preuves |
| Mathlib | la bibliothèque mathématique de la communauté (≈ 290 000 déclarations dans une version récente) |
| noyau (*kernel*) | la petite partie de Lean qui vérifie réellement les preuves |
| axiomes standard | `propext`, `Classical.choice`, `Quot.sound` : admis par Mathlib et par Madalean |
| Lake | l'outil de construction des projets Lean (`lake build`) |
| elan | le gestionnaire de versions de Lean |
| toolchain | une version précise de Lean, fixée par le fichier `lean-toolchain` d'un projet |
| espace de travail | dans Madalean, un projet Lake avec une version de Lean et de Mathlib |
| blueprint | le graphe des énoncés d'un projet de formalisation et de leurs dépendances |
