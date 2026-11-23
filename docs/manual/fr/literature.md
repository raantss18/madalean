---
id: literature
title: Littérature d'abord : résultats publiés et pièces jointes
order: 208
section: research
audience: researcher
summary: Pendant la preuve, Madalean cherche les résultats publiés liés à l'énoncé, les cite mot pour mot et les énonce en Lean ; un résultat cité mais non prouvé en Lean ne rend jamais une preuve « vérifiée ».
---

# Littérature d'abord : résultats publiés et pièces jointes

Quand la preuve d'un énoncé commence, Madalean cherche en parallèle, dans les bases savantes, les résultats publiés
qui s'y rapportent : **zbMATH Open** (littérature relue, avec ses recensions), **OpenAlex**, **arXiv**, et vos
**Sources**. La recherche ne retarde jamais la preuve.

## Ce que vous voyez

Dans l'étape **Preuve**, le panneau **Littérature** :

- chaque **référence** vient d'une base savante (jamais d'un modèle) ; un badge dit si elle est **publiée dans une
  revue (relue par des pairs)** ou une **prépublication (non relue)** ;
- l'**énoncé cité mot pour mot**, avec sa place (« résumé, phrase 2 », « recension zbMATH », « Theorem 2.1, p. 5 ») ;
- son **énoncé en Lean** quand un modèle a pu le traduire (à relire) et son état : **Dans Mathlib**, **Prouvé en
  Lean**, **À prouver (conditionnel)** ou **Pas d'énoncé Lean** ;
- les boutons **Ajouter aux Sources**, **Ajouter à la bibliographie de l'article**, **Prouver ce lemme**, et la notice
  BibTeX.

Si rien de fiable n'est trouvé, c'est écrit tel quel : Madalean n'invente jamais une référence ni une citation.

## Preuve conditionnelle

Si un résultat cité permet de conclure mais n'est pas prouvé en Lean, Madalean l'indique : **« Preuve conditionnelle
— pas vérifiée »**, avec la référence dont elle dépend. Elle n'entre ni dans les preuves du dossier ni dans la
bibliothèque, et l'export l'écrit en toutes lettres. Cliquez sur **Prouver ce lemme** : dès que Lean accepte la preuve
du résultat cité, la preuve est revérifiée strictement et devient **vérifiée**.

## Pièces jointes

Le trombone du fil du dossier (et le panneau **Littérature**) joint une **image**, un **PDF**, un fichier **LaTeX**
ou **BibTeX**, ou une **adresse web**. La pièce jointe devient une Source du projet et n'est **lue qu'une seule fois** :
Madalean en garde un résumé (la référence, les énoncés cités mot pour mot, leur énoncé Lean). Joindre le même fichier
dans un autre dossier du projet ne le relit pas. Une image est lue par un modèle capable de lire les images (sinon elle
reste « non lue ») ; sa transcription est marquée comme telle, l'original reste dans les Sources. **Relire** relit la
pièce jointe si vous le demandez.

Dans le fil, vous pouvez écrire par exemple « d'après la pièce jointe 2, lemme 3.1, conclure » : Madalean cite ce
lemme tel qu'il est écrit dans la pièce jointe.

## Réglages et confidentialité

**Réglages › Modèles › Options avancées** : « Chercher dans la littérature » (activé par défaut) et sa profondeur
(rapide ≈ 45 s, approfondie ≈ 2 min 30). En **mode local**, aucune recherche n'est envoyée sur le réseau : seules
vos Sources et Mathlib sont consultées. Ce qui quitte l'ordinateur : les mots de recherche tirés de l'énoncé et les
identifiants (DOI, arXiv) à vérifier ; jamais votre fichier Lean, vos notes, une clé ou votre nom.
