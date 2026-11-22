---
id: jupyter
title: Jupyter et Sage
order: 240
section: research
audience: researcher
summary: JupyterLab intégré avec les noyaux Python et SageMath, l'assistant à côté du carnet, et qui peut y accéder.
---

# Jupyter et Sage

L'écran « Carnet » ouvre **JupyterLab**, démarré à la demande par l'ordinateur hôte, derrière la même connexion que
le reste de Madalean. Les carnets sont rangés dans `~/Documents/Madalean/notebooks/`.

## Noyaux

| Noyau | Disponible si |
|---|---|
| Python 3 | toujours (avec JupyterLab) |
| SageMath | la copie de Madalean est installée, ou le SageMath du système est compatible |
| Lean 4 | non fourni : aucun noyau Lean 4 n'est assez fiable aujourd'hui. Utilisez les dossiers ou les blocs `lean` des [notes](notes.md). |

Madalean installe sa propre copie de SageMath à la demande, ou réutilise celui de votre système s'il est compatible :
voir [Ce qu'installe Madalean › SageMath](components.md#sagemath).

## L'assistant à côté du carnet

Le panneau d'assistant lit le carnet ouvert (cellules et sorties) et peut **ajouter une cellule** à la fin, que vous
exécutez vous-même. Il répond avec le modèle du mode courant ; en mode *Local*, uniquement un modèle local.

## Qui peut y accéder

Un noyau Jupyter exécute n'importe quel code sur l'ordinateur hôte. Pour cette raison :

- sur l'hôte, le carnet est toujours disponible ;
- depuis un appareil relié, il n'est accessible que si l'hôte l'a autorisé (« Réglages › Carnet et accès »), réglage
  modifiable **seulement depuis l'hôte** ;
- le jeton interne de Jupyter ne quitte jamais le serveur.

Les expériences de l'[atelier de conjectures](conjectures.md) utilisent des noyaux confinés distincts, et ne
s'exécutent qu'après votre accord.
