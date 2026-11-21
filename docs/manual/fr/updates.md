---
id: updates
title: Mises à jour
order: 310
section: settings
audience: all
summary: Ce qui se met à jour tout seul, ce qui demande un clic, comment une mise à jour est vérifiée, et comment revenir en arrière.
---

# Mises à jour

Tout se met à jour depuis Madalean, sans terminal, selon une règle unique : **installer à côté, vérifier, basculer,
puis supprimer l'ancienne version**. Un échec ne change rien et vous est signalé.

## Ce qui est mis à jour, et comment

| Composant | Comportement par défaut |
|---|---|
| Madalean (serveur et interface) | téléchargé et vérifié en arrière-plan, installé à un moment calme (aucun travail en cours) ; version précédente gardée pour un retour en arrière en un clic |
| Application de bureau (AppImage) | se remplace elle-même puis redémarre |
| Application Android | téléchargée et vérifiée par l'application ; Android exige toujours **un appui** de votre part pour installer (règle du système) |
| Lean, Mathlib, paquets Lean de l'espace « Lean récent » | automatique : installé à côté, vérifié (théorème de test et revérification des dossiers prouvés), basculé |
| Modèles Goedel, catalogue des modèles en ligne | automatique, empreintes vérifiées |
| Espace « Prouveur » (Lean 4.9) | **jamais** : épinglé, c'est l'environnement d'entraînement des modèles |
| llama.cpp | notification seulement (version épinglée) |
| SageMath, JupyterLab, TeX, poppler | notification, et un bouton « Installer » qui ouvre un terminal avec la commande exacte ; vous tapez votre mot de passe. Madalean ne lance jamais `sudo`, `pacman`, `apt` ou `dnf` lui-même. |

Le réglage « Demander avant d'installer » (« Réglages › Mises à jour ») remplace l'automatique par une notification.
Les vérifications ont lieu chaque semaine et à la demande. En mode *Local*, aucune vérification ne touche le réseau.
<!-- verify after integration: self-update installer, AppImage updater and APK download are built (§16); setting label -->

## Pourquoi une mise à jour de Madalean est sûre

Chaque version publiée est accompagnée d'une liste d'empreintes (`SHA256SUMS`) **signée** avec une clé Ed25519 gardée
hors de GitHub. La clé publique est inscrite dans Madalean. Une version dont la signature ne correspond pas est
refusée, **même si le compte GitHub était compromis**. Le canal de mise à jour
(`updates/stable.json`, sur le site) est signé de la même façon.

Vérifier vous-même un téléchargement : voir la [page d'installation](site:install#verify).

## Après une mise à jour de Lean ou de Mathlib

Les dossiers prouvés de l'espace concerné sont marqués « à revérifier », puis revérifiés automatiquement. Un dossier
dont la preuve ne passe plus (un lemme renommé, une tactique changée) est signalé ; son ancien verdict n'est jamais
affiché seul.

## Revenir en arrière

« Réglages › Mises à jour › Revenir à la version précédente » pour Madalean. Pour Lean et Mathlib, la version
précédente reste installée tant qu'un de vos projets l'utilise.
<!-- verify after integration: rollback control exists and its label -->
