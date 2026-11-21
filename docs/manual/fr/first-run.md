---
id: first-run
title: Premier démarrage
order: 20
section: start
audience: all
summary: Visite guidée, choix du mode, premier énoncé, mode démo.
---

# Premier démarrage

À la première ouverture sur l'ordinateur hôte, Madalean vérifie son environnement (espaces Lean, modèles, TeX,
polices, disque) et affiche ce qui manque avec un bouton de réparation quand il en existe un. Une courte visite
présente ensuite les quatre idées de l'interface : écrire un énoncé, vérifier la traduction, laisser Lean juger,
garder la main.
<!-- verify after integration: first-run checks and tour wording -->

## Trois choix à faire

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

puis lancez. Les étapes s'enchaînent seules : compréhension, traduction en Lean, recherche de preuve, explication.
La suite est décrite dans [De l'énoncé à la preuve](workflow.md).

## Essayer sans modèles ni Lean : le mode démo

```bash
~/madalean/bin/madalean serve --demo --port 11600 --remote-port 11601
```

puis ouvrez `http://127.0.0.1:11600`. Les modèles et Lean sont **simulés** : un bandeau le rappelle et rien n'y est
vraiment vérifié. Le mode démo sert à découvrir l'interface ; ses données sont séparées des vôtres
(`~/.config/madalean-demo`).
