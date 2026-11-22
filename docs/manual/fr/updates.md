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

Tout se règle dans « Réglages › Mises à jour ».

| Composant | Comportement par défaut |
|---|---|
| Madalean (serveur et interface), partie « Madalean lui-même » | cherché chaque semaine (sauf en mode *Local*), téléchargé, vérifié, installé à un moment calme (aucun travail en cours), puis redémarré ; « Installer » et « Redémarrer maintenant » le font tout de suite. La version précédente est gardée pour revenir en arrière |
| Application de bureau (AppImage) | se remplace elle-même après vérification ; la nouvelle version s'ouvre au prochain démarrage (ou tout de suite avec « Redémarrer ») |
| Application Android | réglage « Mises à jour automatiques » de l'application : elle vérifie au plus deux fois par jour, télécharge et contrôle la signature ; l'installation demande toujours votre confirmation (règle d'Android) |
| Lean, Mathlib, paquets Lean de l'espace « Lean actuel », SageMath, LaTeX (partie « Composants suivis ») | automatique : installé à côté, vérifié (théorème de test et revérification des dossiers prouvés), basculé |
| Modèles Goedel, catalogue des modèles en ligne | automatique, empreintes vérifiées |
| Espace « Prouveur » (Lean 4.9) | **jamais** : épinglé, c'est l'environnement d'entraînement des modèles |
| llama.cpp | notification seulement ; sa version épinglée change avec les versions de Madalean |
| Programmes installés sur le système hors de Madalean (partie « Composants du système ») | notification seulement, avec la commande exacte et un bouton « Ouvrir un terminal avec la commande » ; vous tapez votre mot de passe. Madalean ne lance jamais `sudo`, `pacman`, `apt` ou `dnf` lui-même. |

Décochez « Installer automatiquement quand rien ne tourne » pour être prévenu avant chaque installation au lieu de
l'installation automatique. « Chercher chaque semaine (rien ne s'installe sans votre clic) » règle la recherche
automatique ; « Chercher des mises à jour » la lance tout de suite.

## Pourquoi une mise à jour de Madalean est sûre

Chaque version publiée est accompagnée d'une liste d'empreintes (`SHA256SUMS`) **signée** avec une clé Ed25519 gardée
hors de GitHub. La clé publique est inscrite dans Madalean. Une version dont la signature ne correspond pas est
refusée, **même si le compte GitHub était compromis**. Le canal de mise à jour
(`updates/stable.json`, sur le site) est signé de la même façon.

Vérifier vous-même un téléchargement : voir la [page d'installation](site:install#verify).

## Après une mise à jour de Lean ou de Mathlib

Les dossiers prouvés de l'espace concerné sont revérifiés automatiquement (partie « Revérification des preuves »,
bouton « Revérifier maintenant »). Un dossier
dont la preuve ne passe plus (un lemme renommé, une tactique changée) est signalé ; son ancien verdict n'est jamais
affiché seul.

## Revenir en arrière

Pour Madalean : « Réglages › Mises à jour », partie « Madalean lui-même », bouton « Revenir à … » (avec le numéro de
la version précédente). Pour Lean et Mathlib, l'ancienne version n'est remplacée qu'après une vérification réussie ;
en cas d'échec, rien ne change.
