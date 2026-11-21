---
id: publish
title: Publier un projet
order: 250
section: research
audience: researcher
summary: Publier un projet vérifié en site statique sur un dépôt GitHub de votre choix, revérifié indépendamment par lake build.
---

# Publier un projet

<!-- verify after integration: the « Publier » feature is not built yet; this page describes the design of ARCHITECTURE §17 and the template in site/publication -->

« Publier » transforme un projet en **site statique** que n'importe qui peut lire et revérifier :

- l'article (HTML et PDF) ;
- le **graphe des dépendances** du blueprint, avec l'état de chaque résultat ;
- une page par énoncé : énoncé en langage naturel, code Lean coloré, preuve rédigée, informations de vérification
  (version de Lean, révision de Mathlib, axiomes, date) ;
- la bibliographie ;
- le **projet Lake** complet à télécharger.

Le site est poussé sur un dépôt GitHub **que vous choisissez**, avec une action GitHub qui relance `lake build` sur
le projet Lean publié. Le badge de vérification affiché par le site vient de cette action, indépendante de votre
ordinateur : un lecteur n'a pas à croire Madalean sur parole.

## Ce qui part, et seulement avec votre accord

1. « Aperçu » construit le site localement : vous le parcourez avant toute publication.
2. L'écran de publication liste **exactement** ce qui quittera la machine : fichiers, dossiers, notes, sources.
   Rien de privé n'est publié sans un choix explicite, élément par élément. Les PDF de vos sources ne sont jamais
   publiés : seule leur référence bibliographique l'est.
3. La publication utilise l'outil `gh` ou un jeton GitHub gardé dans le trousseau de l'hôte.

## Ce que montre le site

| Couleur et marque | État |
|---|---|
| vert plein, ✓ | vérifié : preuve acceptée par Lean, et toutes ses dépendances vérifiées |
| vert clair | prouvé, mais une dépendance ne l'est pas encore |
| bleu | énoncé Lean accepté, sans preuve |
| contour pointillé | énoncé en langage naturel seulement |
| rouge | bloqué : dépend d'une définition sans énoncé Lean |

Un résultat non vérifié n'est jamais présenté comme théorème. Le site n'utilise ni traceur, ni police ou script
externe, et se lit sans JavaScript.
