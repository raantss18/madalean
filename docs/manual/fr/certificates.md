---
id: certificates
title: Certificats : Sage calcule, Lean vérifie
order: 207
section: research
audience: researcher
summary: Pour les énoncés qui s'y prêtent, Sage cherche un témoin et Lean ne fait que le vérifier — sans modèle, sans coût, en quelques secondes.
---

# Certificats : Sage calcule, Lean vérifie

Un **certificat** est un témoin facile à vérifier : un facteur, un inverse, une somme de carrés, un contre-exemple…
Sage le cherche (cela peut être difficile), puis Lean le **vérifie** (c'est facile et sûr). Si le témoin est faux,
Lean le refuse : un certificat ne peut jamais faire passer une erreur pour une preuve.

## Ce qui est couvert

| Famille | Exemple d'énoncé | Ce que Lean vérifie |
|---|---|---|
| Primalité | « 1 000 003 est premier » | un certificat de Pratt |
| Nombre composé | « 2³² + 1 n'est pas premier » | un facteur |
| Arithmétique | pgcd, ppcm, divisibilité, congruences, factorielles | le calcul |
| Puissance modulaire | « 3^1000000 mod 7 = … » | le calcul pas à pas |
| Identité | une égalité polynomiale | `ring` |
| Idéal | « f est dans l'idéal engendré par g et h » | les cofacteurs (base de Gröbner) |
| Arithmétique linéaire | un système d'inégalités sans solution | la combinaison de Farkas |
| Somme de carrés | « x² + y² ≥ 2xy » | l'écriture comme somme de carrés |
| Existence | « ∃ x, 17x ≡ 1 (mod 3120) » | le témoin (x = 2753) |
| Contre-exemple | « n² + n + 41 est premier pour tout n » | le contre-exemple (n = 40) |
| Borne numérique | « √2 < 1,415 », bornes sur π, e, log 2 | l'encadrement |
| Cas finis | « pour tout n ≤ 20, … » | l'énumération |

Lean vérifie tout dans son noyau, sans passer par du code compilé (`native_decide` n'est jamais utilisé).

## Où les trouver

1. **Dans une preuve** — la stratégie « certificat » se lance seule, à côté de la recherche dans Mathlib, quand
   l'énoncé a une forme reconnue. Le fil du dossier affiche « témoin calculé par Sage, vérifié par Lean » avec le
   témoin. Elle se règle dans **Réglages › Modèles › Certificats** (activée par défaut).
2. **Pour les modèles qui prouvent** — ils peuvent demander un témoin à Sage pendant leur recherche. Ils envoient un
   énoncé, jamais du code.
3. **Dans Calcul** — sur une cellule qui a donné un résultat (factorisation, primalité, pgcd, puissance modulaire,
   inverse, binomial…), menu ⋯ › **Certifier avec Lean** : Madalean crée un dossier avec l'énoncé et sa preuve.

## Limites

Pas encore : graphes comme témoins, intégrales et arithmétique d'intervalles générale, sommes de carrés au-delà de
4 variables ou du degré 8, structures abstraites (anneaux quelconques, sommes ∑, nombres complexes). Sans SageMath
installé, seules l'arithmétique, les puissances modulaires, les identités, les cas finis et les petits nombres
premiers fonctionnent.
