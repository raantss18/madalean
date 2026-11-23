---
id: mcp
title: Outils MCP : relier Madalean à d'autres assistants
order: 325
section: settings
audience: all
summary: Laisser un autre assistant de cet ordinateur utiliser les outils de Madalean, et donner aux modèles de Madalean des outils d'autres programmes — éteint tant que vous ne l'allumez pas.
---

# Outils MCP : relier Madalean à d'autres assistants

**MCP** (*Model Context Protocol*) est une façon commune, pour les assistants d'IA, d'utiliser les outils d'autres
programmes. Madalean le parle dans les deux sens. Tout se règle dans **Réglages › Outils (MCP)**, sur l'ordinateur
hôte seulement, et tout est **éteint** au départ.

## Madalean comme serveur MCP

Un autre assistant de cet ordinateur (Claude Code, Claude Desktop…) peut alors :

- **chercher dans Mathlib** les noms exacts de la version installée ;
- **vérifier avec Lean** un énoncé, ou une preuve de cet énoncé — avec le verdict strict de Madalean (pas de
  `sorry`, pas d'axiome ajouté) ; l'énoncé ne peut pas être changé par la preuve ;
- **certifier** un énoncé calculatoire (Sage calcule un témoin, Lean le vérifie) ;
- **expliquer** une erreur Lean, ou un code ligne par ligne ;
- **chercher dans votre bibliothèque** et voir **l'état de vos dossiers**.

Ces outils **n'enregistrent rien** : pas de dossier créé, pas de résultat ajouté à la bibliothèque.

Pour le brancher :

1. allumez **« Autoriser les applications de cet ordinateur »** ;
2. copiez la commande affichée (Claude Code) ou le bloc JSON (Claude Desktop et les autres clients) ;
3. redémarrez le client. Madalean doit être en marche.

Deux interrupteurs de plus :

- **« Aussi par une adresse locale (HTTP) »** : pour les clients qui se branchent par une adresse
  `http://127.0.0.1:…`. Elle n'est ouverte qu'à cet ordinateur ;
- **« Autoriser les calculs Sage »** : le client décrit un calcul en mots (« factoriser x⁴ − 1 sur F₅ ») ; Madalean
  n'exécute que **son propre code vérifié**, dans le noyau isolé. Un code envoyé par le client n'est jamais exécuté.

Les appareils appairés (téléphone, autre ordinateur) n'y ont **jamais** accès.

## Serveurs MCP externes

À l'inverse, vous pouvez donner aux modèles de Madalean des outils d'autres programmes, par exemple un serveur MCP
du langage Lean. Ajoutez-le par sa **commande** (Madalean la lance) ou son **adresse**, puis :

1. **Tester** : Madalean le démarre, lit la liste de ses outils et l'arrête ;
2. **l'activer** ;
3. **cocher** les outils que les modèles peuvent appeler pendant une preuve. Rien n'est coché au départ.

Ce que Madalean fait pour vous protéger :

- les réponses de ces outils sont lues comme des **données**, jamais comme des ordres ; un texte qui essaie de donner
  des ordres au modèle est signalé et mis à l'écart ;
- un outil dont la description donne des ordres au modèle est **refusé** (on ne peut pas le cocher) ;
- le programme ne reçoit **aucune clé d'API**, aucun mot de passe ; chaque appel a une durée et une taille limitées ;
- seul **Lean** décide qu'une preuve est juste : un outil externe ne peut jamais faire passer une preuve.

Un serveur lancé par commande tourne avec **vos droits** : n'ajoutez que des programmes de confiance.

### Exemple : un serveur MCP pour Lean

Le projet `lean-lsp-mcp` (à installer vous-même, sans droits d'administrateur, par exemple avec `uv`) donne accès au
serveur de langage de Lean. Commande à ajouter : `uvx lean-lsp-mcp`. Il lit les fichiers d'un projet Lean : lancez-le
depuis le projet ou indiquez-le dans sa propre configuration (voir sa documentation).

## Le journal des appels

Chaque appel, dans un sens ou dans l'autre, est noté : quand, quel outil, réussi ou non, en combien de temps. Le
journal est en bas de la page, et dans `logs/mcp-activity.jsonl` du dossier de configuration.
