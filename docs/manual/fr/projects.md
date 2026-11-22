---
id: projects
title: Projets et dossiers en parallèle
order: 130
section: use
audience: all
summary: Regrouper des dossiers en projets, lancer plusieurs travaux à la fois, comprendre la file d'attente.
---

# Projets et dossiers en parallèle

## Projets

Un **projet** regroupe des dossiers : un chapitre de cours, un article en préparation, une série d'exercices. Le
sélecteur en haut à gauche (« Tous les projets ») filtre la liste des dossiers. Un projet a son espace Lean, sa
bibliographie, ses sources, ses notes, son plan d'article.

Supprimer un projet le met à la corbeille : « Annuler » le restaure. Ses dossiers ne sont pas supprimés.

## Plusieurs dossiers à la fois

Vous pouvez lancer autant de dossiers que vous voulez ; ils avancent en parallèle, limités par les ressources de
l'hôte :

| Ressource | Places | Utilisée par |
|---|---|---|
| carte graphique | 1 | un modèle local à la fois (Madalean change de modèle selon l'étape) |
| en ligne | 3 | appels aux modèles en ligne |
| Lean | 2 | compilations |

Un travail n'attend que la ressource de l'étape en cours ; vos travaux passent avant les relances automatiques.
L'écran « Activité » montre ce qui tourne, ce qui attend et pourquoi (« en attente : carte graphique »).

![Activité : travaux en parallèle](../img/activity.png)

Un dossier n'a qu'un travail actif à la fois ; une nouvelle demande sur un dossier occupé est refusée avec un
message clair. Tout travail s'arrête à la demande.

## Sur tous les appareils

Tous les appareils reliés voient les mêmes projets, les mêmes dossiers et les mêmes travaux en direct. Lancez une
preuve depuis le téléphone, suivez-la sur le PC. Après une coupure réseau, l'appareil se resynchronise seul.

## Espaces Lean

Chaque projet utilise un **espace de travail** Lean (« Réglages › Espaces Lean ») :

- *Prouveur* : Lean 4.9 et la Mathlib d'entraînement des modèles Goedel. Épinglé : il n'est jamais mis à jour,
  pour que les modèles locaux restent efficaces.
- *Lean actuel* : dernière Mathlib, mise à jour automatiquement (voir [Mises à jour](updates.md)).

Un résultat de la bibliothèque n'est réutilisable que dans l'espace où il a été prouvé.
