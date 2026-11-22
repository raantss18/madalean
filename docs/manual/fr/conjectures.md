---
id: conjectures
title: Atelier de conjectures
order: 200
section: research
audience: researcher
summary: Proposer des conjectures, les tester (Lean sur petits cas, Sage, contre-exemples) avant d'y croire, et les promouvoir par une preuve.
---

# Atelier de conjectures

Une conjecture est un dossier d'un genre particulier, avec un **journal des indices** : tout ce qui a été tenté pour
l'éprouver. Une conjecture ne devient un théorème que par une preuve Lean.

## D'où viennent les conjectures

Tout se passe dans l'écran « Conjectures » du projet.

- « Écrire une conjecture » : vous l'écrivez en langage courant ; « Traduire en Lean » en propose ensuite un énoncé
  Lean, ou vous l'écrivez vous-même (« Vérifier et enregistrer l'énoncé »).
- « Proposer » : à partir des notes, des résultats prouvés et des sources du projet, un modèle en propose quelques-unes
  avec leur motivation ; « Garder cette conjecture » retient celles qui vous intéressent. Les propositions déjà
  connues (doublon, déjà un dossier, déjà dans la bibliothèque, déjà dans Mathlib) sont écartées et listées à part
  avec la raison.

## Les états d'une conjecture

| État | Signification |
|---|---|
| proposée | énoncée, rien de testé |
| testée sur des cas | des cas particuliers ont tenu (Lean ou expériences) |
| énoncé Lean accepté | un énoncé Lean est accepté par Lean |
| prouvée | la preuve courante du dossier passe le verdict strict |
| réfutée | un contre-exemple a été **revérifié** indépendamment |

## Tester avant de croire

**Petits cas en Lean** (« Tester les petits cas avec Lean »). Madalean écrit un `example` par cas (par défaut $n = 0, \dots, 9$ pour la première variable
entière) et tente de le fermer par calcul (`norm_num`, `decide`, `simp`, `omega`). Option : un énoncé borné
`∀ n < K, …` fermé par `decide`. Ces tests ne prouvent rien au-delà des cas testés.

**Expériences Sage ou Python.** Le modèle écrit (ou vous écrivez) un programme en deux parties : un prédicat
`holds(...)` et une recherche qui appelle `report(...)`. **Le code vous est montré et ne s'exécute qu'après votre
accord sur ce code exact** (« J'ai lu ce code : approuver et lancer ») ; une modification annule l'accord. Les
expériences ne se lancent que depuis l'ordinateur hôte. Les exécutions sont confinées (voir
[Sécurité](security.md#code-execute-sur-lhote)) et limitées en temps et en mémoire.

**Contre-exemple.** Un contre-exemple annoncé n'est pas cru sur parole : le prédicat seul est réévalué au témoin
dans un noyau neuf et, si la conjecture a un énoncé Lean, Lean doit accepter la négation de l'énoncé au témoin.
Alors seulement la conjecture passe à « réfutée ».

**Littérature.** « Chercher dans la littérature » interroge les bases bibliographiques (voir
[Sources](sources.md)) pour savoir si l'énoncé est connu.

## Le journal des indices

Dans l'écran, il s'appelle « Journal des preuves et essais ». Chaque test, expérience, vérification ou recherche ajoute une entrée datée (avec le code exécuté, la sortie, le
modèle et l'appareil). Le journal est **en ajout seul** et ses entrées sont chaînées par empreintes SHA-256 :
une entrée modifiée après coup se voit (« journal intact » / « journal altéré ! »).

## Promouvoir

Quand la conjecture est prouvée, « Promouvoir en théorème » change son genre ; l'historique est gardé.

Exemple du mode démo : « $n^2 + n + 41$ est premier pour tout $n$ » tient pour $n = 0, \dots, 9$ en Lean, puis une
expérience trouve $n = 40$ ($40^2 + 40 + 41 = 41^2$), revérifié : réfutée.
