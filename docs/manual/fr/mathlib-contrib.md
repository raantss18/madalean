---
id: mathlib-contrib
title: Contribuer à Mathlib
order: 255
section: research
audience: researcher
summary: D'un résultat vérifié à une proposition d'ajout à Mathlib — vérifiée avec la Mathlib actuelle, nommée, contrôlée, relue par vous ; rien n'est envoyé sans deux clics de votre part.
---

# Contribuer à Mathlib

Mathlib est la grande bibliothèque de mathématiques de Lean. Quand un
de vos résultats y manque, Madalean prépare tout ce qu'il faut pour le proposer : le fichier, le nom, la liste des
contrôles, le texte de la demande. **Vous relisez tout** ; rien ne part sans vous.

## Où trouver le bouton

- dans la **Bibliothèque** : ouvrez un résultat vérifié, puis « Préparer pour Mathlib » ;
- dans un **dossier** : sous la preuve vérifiée, « Préparer pour Mathlib ».

Indiquez votre nom (il figure en tête du fichier, comme l'exige Mathlib), puis « Lancer la préparation ».

## Les étapes

1. **Vérifier avec la Mathlib actuelle.** Mathlib n'accepte que du code à jour. Si la preuve a été trouvée avec le
   Lean du prouveur (Lean 4.9), Madalean remplace d'abord les noms qui ont changé depuis (ceux que Lean signale
   comme périmés, ceux appris de vos preuves, une petite table vérifiée) puis la fait revérifier par Lean 4.36.
   Si cela ne suffit pas, « Relancer la preuve dans Lean actuel » ouvre un nouveau dossier, avec l'ancienne preuve
   comme indice.
2. **Chercher si Mathlib le contient déjà.** Si un lemme de Mathlib donne directement le résultat, Madalean le
   dit, avec son nom, et s'arrête : pas de contribution en double.
3. **Proposer un nom.** Mathlib nomme un théorème d'après son énoncé, lu de gauche à droite : `a + b ≤ c` donne
   `add_le`, `0 ≤ x` donne `x_nonneg`, une hypothèse ajoute `_of_…`. Madalean explique chaque mot du nom et vérifie
   qu'il est libre.
4. **Réduire les imports.** Au lieu de tout Mathlib, seulement les fichiers nécessaires — puis Lean revérifie.
5. **Vérifier le fichier final** et lancer les **contrôles de style** de Mathlib (`#lint` et ses vérifications
   automatiques).

## La liste de contrôle

Chaque règle est marquée *bon*, *à revoir*, *bloquant* ou *non vérifié* : en-tête de copyright, présentation du
fichier, phrase d'explication pour chaque théorème, lignes de 100 caractères au plus, pas de `sorry`, pas de limite
de temps relevée, `simp` seulement en fin de preuve, ≤ plutôt que ≥, variables déduites des hypothèses entre
accolades, aucun nom périmé, nom libre, imports réduits. La phrase d'explication est écrite automatiquement à
partir de l'énoncé : relisez-la.

## Envoyer

- **Copier** ou **Télécharger le fichier** : toujours possible, rien ne quitte l'ordinateur.
- **Créer une branche sur mon fork…** : seulement avec une clé GitHub enregistrée dans Réglages → Clés, et depuis
  l'ordinateur hôte. Madalean montre d'abord **exactement** ce qui sera envoyé (chaque requête, le contenu du
  fichier) ; rien ne part avant « Confirmer ».
- **Ouvrir la PR…** : une seconde confirmation, séparée. La demande est ouverte en **brouillon** : vous la relisez
  sur GitHub avant de la proposer aux relecteurs.

Les guides de Mathlib (contribuer, nommage, style, documentation) sont liés en bas du panneau. Les relecteurs de
Mathlib demandent souvent de raccourcir une preuve ou de généraliser un énoncé : c'est normal.
