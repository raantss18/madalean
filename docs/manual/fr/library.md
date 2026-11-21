---
id: library
title: Bibliothèque de résultats
order: 150
section: use
audience: all
summary: Vos résultats prouvés, rangés par domaine, projet ou étiquette, avec leur statut, qui les a prouvés, ce qu'ils utilisent et l'export.
---

# Bibliothèque de résultats

Chaque preuve acceptée par Lean entre dans la **Bibliothèque** ; ces résultats sont ensuite proposés comme lemmes à
vos prochaines preuves (même version de Lean et de Mathlib).

- **Ranger par** domaine (classé automatiquement d'après l'énoncé, modifiable), projet ou étiquette.
- **Cartes** ou **Tableau** : le choix est mémorisé sur cet appareil.
- **Statut** : *Vérifié* (Lean a accepté la preuve, verdict strict) ou *Conditionnel* (preuve obtenue en admettant
  des lemmes d'un plan de preuve : rien n'est vérifié tant qu'ils ne sont pas prouvés).
- Pour chaque résultat : l'énoncé en mots et en Lean, le modèle (ou vous) qui l'a prouvé, les axiomes, ce qu'il
  **utilise** et ce qui **l'utilise**.
- **Exporter** : tout en Markdown ou JSON ; un résultat seul en `.lean` (avec les résultats dont il dépend).

Le domaine et les étiquettes sont partagés entre vos appareils. Retirer un résultat se fait avec annulation possible.
