---
id: first-run
title: Premier démarrage
order: 20
section: start
audience: all
summary: Visite guidée, choix du mode, premier énoncé, mode démo.
---

# Premier démarrage

Sur l'ordinateur hôte, la toute première ouverture commence par l'assistant « Premiers pas » (outils, modèle local,
clés, modes… ; voir [Première configuration](first-config.md#lassistant-premiers-pas)). Ensuite, à la première
ouverture de l'accueil (en mode *Apprendre*, celui par défaut), une courte visite en quatre étapes présente les
idées de l'interface : écrire un énoncé, vérifier la traduction, Lean vérifie chaque preuve, vous gardez la main.
« Passer la visite » la ferme.

L'état de l'installation (espaces Lean, modèles, TeX, polices, bac à sable, disque) se lit dans « Réglages ›
Système », partie « État de santé » : chaque problème y est signalé, avec un bouton « Réparer » quand une réparation
existe (à lancer depuis l'ordinateur hôte).

## Trois choix à faire

Ces choix, les clés des fournisseurs et chaque comportement automatique sont détaillés dans
[Première configuration](first-config.md).


1. **Où travaillent les modèles** (« Réglages › Modèles ») :
   - *Local* : rien ne quitte l'ordinateur hôte ; seuls les modèles installés ici travaillent.
   - *Automatique* (par défaut) : le meilleur modèle disponible, en ligne d'abord, les modèles locaux si le réseau
     manque.
   - *En ligne* : uniquement des modèles en ligne.

   Ce que chaque mode envoie, et à qui : [Modèles et clés](models-keys.md).
2. **Apprendre ou Recherche** (bouton en haut à droite) : *Apprendre* propose des indices avant la preuve, un
   glossaire au survol et des explications ligne par ligne ; *Recherche* est dense, pensé pour le clavier, sans rien
   de pédagogique sur le chemin. Vous pouvez changer à tout moment.
3. **Votre profil** (« Réglages › Profil ») : public visé, niveau, notations préférées. Il est lu avant chaque
   traduction et chaque explication.

## Un premier énoncé

Sur l'accueil, écrivez par exemple :

> Montrer que la somme de deux entiers pairs est paire.

puis « Traduire et prouver ». Les étapes s'enchaînent seules : compréhension, traduction en Lean, recherche de preuve, explication.
La suite est décrite dans [De l'énoncé à la preuve](workflow.md).

## Essayer sans modèles ni Lean : le mode démo

```bash
~/madalean/bin/madalean serve --demo --port 11600 --remote-port 11601
```

puis ouvrez `http://127.0.0.1:11600`. Les modèles et Lean sont **simulés** : un bandeau le rappelle et rien n'y est
vraiment vérifié. Le mode démo sert à découvrir l'interface ; ses données sont séparées des vôtres
(`~/.config/madalean-demo`).
