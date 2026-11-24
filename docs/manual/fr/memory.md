---
id: memory
title: Mémoire — exporter, importer, sauvegarder
order: 146
section: settings
audience: researcher
summary: Tout ce que Madalean a appris (bibliothèque, leçons, recettes, graphes, résumés) dans un seul fichier, revérifié par Lean à l'import ; sauvegardes automatiques ; jeu de données vérifiées.
---

# Mémoire — exporter, importer, sauvegarder

Madalean apprend sans entraîner de modèle : la **bibliothèque** des résultats prouvés, les **leçons** tirées de ses
erreurs, les **recettes** de calcul, les **graphes** de vos problèmes, les **résumés** des pièces jointes. Réglages ›
« Mémoire » met tout cela dans un seul fichier `.madalean-memory`, à garder ou à transporter sur un autre ordinateur.

## Exporter

Cochez les parties à inclure et, si vous voulez, seulement certains projets, puis « Exporter la mémoire ».

- Les **résumés de sources protégées** (©, ou licence inconnue) sont laissés de côté par défaut : leur licence peut
  interdire de les redistribuer. Le fichier dit ce qui manque. Cochez « Inclure les résumés de sources protégées »
  pour une copie strictement personnelle.
- Les **fichiers d'origine** des pièces jointes (PDF, images…) ne sont inclus que si vous le cochez.
- Le fichier porte l'empreinte (SHA-256) de chaque partie et les versions de Lean et de Mathlib de vos espaces.

## Importer

Sur l'ordinateur hôte seulement. Choisissez un fichier : Madalean montre d'abord un **aperçu** — ce qui serait
ajouté, vérifié, ignoré, et pourquoi — sans rien écrire. « Importer » applique.

Rien n'est cru sur parole :

- chaque **preuve** est revérifiée ici par Lean, dans un espace qui a **les mêmes versions de Lean et de Mathlib**.
  Acceptée, elle entre dans la bibliothèque. Sinon elle reste dans « Importées, non vérifiées » avec la raison
  (aucun espace de même version, Lean refuse la preuve, un résultat utilisé manque…) et ne sert à rien. Après avoir
  installé le bon espace, « Revérifier » ;
- les **recettes** de calcul sont relues par Sage ou Python (sans être exécutées) ; un code qui touche au système est
  refusé ; une recette importée ne remplace jamais la vôtre ;
- les **leçons** gardent leurs preuves mais repartent de zéro : elles ne comptent qu'une fois utiles ici ;
- les **graphes** venus d'ailleurs restent des **références** en lecture seule (l'aperçu dit combien de leurs lemmes
  sont déjà dans vos graphes) ; vos graphes ne sont jamais modifiés ;
- les **résumés** rejoignent le projet du même identifiant s'il existe (comme « résultats fournis » : jamais des
  preuves), sinon des références ;
- les doublons (même énoncé à un renommage près, même leçon, même code) sont ignorés ;
- un texte qui s'adresse à un modèle (« ignore les instructions… ») est refusé ; un fichier modifié (empreinte
  différente) est refusé en entier.

## Sauvegardes automatiques

Cochez « Sauvegarder automatiquement », choisissez la fréquence (jour, semaine, mois), le nombre de copies gardées
et le dossier (par défaut `~/.config/madalean/backups`). Les copies restent sur cet ordinateur ; seules les plus
anciennes copies de Madalean sont effacées, jamais vos autres fichiers. « Sauvegarder maintenant » en écrit une tout
de suite. Pour restaurer : « Importer » une copie.

## Jeu de données d'entraînement

« Exporter le jeu de données » écrit un fichier JSONL des paires **vérifiées par Lean** (énoncé → preuve, erreur →
correction), avec la licence et la provenance de chaque ligne. Il prépare un éventuel affinage d'un modèle local plus
tard (désactivé, non fourni) : Madalean n'entraîne aucun modèle.

Pour aller plus loin : [Graphe du problème et leçons](proof-graph.md) · [Bibliothèque](library.md) ·
[Sécurité](security.md).
