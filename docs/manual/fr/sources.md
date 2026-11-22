---
id: sources
title: Sources, recherche bibliographique et questions ancrées
order: 210
section: research
audience: researcher
summary: La bibliothèque de sources (articles, livres), la recherche dans les bases, le lecteur annoté, et les réponses citant vos sources.
---

# Sources, recherche bibliographique et questions ancrées

## La bibliothèque de sources

L'écran « Sources » du projet a trois onglets : « Bibliothèque », « Recherche bibliographique » et « Poser une
question ». Articles, livres, notes de cours y sont rangés par **étagère** : une par projet, une étagère générale, et
l'étagère *Mathlib* (lecture seule, tirée de la bibliographie de Mathlib). Pour ajouter une source, « Ajouter »
propose trois façons : « Identifiant », « Fichier », « Coller ».

| Par | Ce que fait Madalean |
|---|---|
| « Identifiant » : DOI, identifiant arXiv, ISBN, `Zbl …`, identifiant OpenAlex | récupère les métadonnées vérifiées ; pour arXiv, aussi les sources TeX et le PDF ; pour un DOI, le PDF seulement s'il est en accès ouvert |
| « Identifiant » : adresse web | métadonnées de la page seulement |
| « Fichier » : PDF, source TeX (`.tex`, `.tar.gz`, `.zip`) | cherche un identifiant dans les premières pages ; sinon métadonnées devinées, marquées **non vérifiées** |
| « Fichier » ou « Coller » : BibTeX, RIS, CSL-JSON, export Zotero (RDF, ou `.zip` avec les fichiers joints) | importe les références et les fichiers joints de l'archive |

Les doublons (même DOI, même arXiv, même titre) sont signalés. Chaque source a des étiquettes, un état de lecture,
des annotations, et sa clé BibTeX. Le bouton « BibTeX » exporte l'étagère.

Les métadonnées devinées à partir d'un fichier restent marquées « métadonnées à vérifier » tant que vous ne les avez
pas confirmées (« Elles sont justes » dans le lecteur).

## Recherche bibliographique

L'onglet « Recherche bibliographique » interroge arXiv, zbMATH Open, Crossref, OpenAlex et Semantic Scholar et
fusionne les résultats. **Seule votre requête est envoyée.** Un service qui ne répond pas est marqué
« indisponible », sans bloquer les autres. « Ajouter » range un résultat dans vos sources.

En mode *Local*, ces recherches sont refusées : elles demandent le réseau.

## Lire et annoter

Le lecteur affiche le PDF à côté du texte extrait. « Surligner » un passage, ajouter une « Note en marge » : les
annotations sont ancrées à la page et à la position, et retrouvables dans la recherche.

Le texte intégral de chaque source est indexé **localement**, découpé en passages avec leur page et leur section.
Pour un PDF sans couche texte (scan), une reconnaissance de caractères existe, mais les formules lues ainsi ne sont
pas fiables.

## Questions ancrées dans vos sources

Posez une question (onglet « Poser une question », ou « Questions sur ce texte » dans le lecteur) : la réponse cite
des **passages** précis.

- Chaque citation renvoie au passage (clic : la page s'ouvre au bon endroit).
- La citation est vérifiée par le code : le passage cité doit contenir le texte cité. Une phrase sans citation
  valide est affichée barrée ou grisée.
- Si aucun passage pertinent n'est trouvé, la réponse le dit, **sans appeler de modèle**.
- Une partie « connaissances générales », facultative (« Compléter avec des connaissances générales »), est séparée
  et marquée comme telle, sans citation.

Ce que la vérification garantit : le passage cité existe et contient la citation. Ce qu'elle ne garantit pas : que le
passage *justifie* la phrase. Lisez le passage pour les points importants.

Autres demandes : « Résumer » (ce que prouve l'article, ses définitions, ses dépendances) et « Comparer » plusieurs
sources (« Comparer avec… » dans le lecteur).

## Ce qui part sur Internet

Les requêtes de recherche, les identifiants (DOI, arXiv…) et le téléchargement des fichiers en accès ouvert. Les
questions sur vos sources passent par le modèle choisi, avec les passages retenus : en mode *Local*, uniquement par
un modèle local. Voir [Modèles et clés](models-keys.md#ce-qui-part-et-vers-qui).
