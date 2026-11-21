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
<!-- verify after integration: button and screen names of the research screens (S-D) -->

Articles, livres, notes de cours, rangés par **étagère** : une par projet, une étagère générale, et l'étagère
*Mathlib* (lecture seule, tirée de la bibliographie de Mathlib). Pour ajouter une source :

| Par | Ce que fait Madalean |
|---|---|
| DOI, identifiant arXiv, ISBN, `Zbl …`, identifiant OpenAlex | récupère les métadonnées vérifiées ; pour arXiv, aussi les sources TeX et le PDF ; pour un DOI, le PDF seulement s'il est en accès ouvert |
| URL | métadonnées de la page seulement |
| fichier PDF, TeX, archive, EPUB | cherche un identifiant dans les premières pages ; sinon métadonnées devinées, marquées **non vérifiées** |
| BibTeX, RIS, CSL-JSON, export Zotero (RDF ou zip) | importe les références et les fichiers joints de l'archive |
| formulaire | saisie à la main |

Les doublons (même DOI, même arXiv, titre très proche) sont signalés. Chaque source a des étiquettes, des
collections, un état de lecture, des notes, et sa clé BibTeX. Export en BibTeX, RIS ou CSL-JSON.

Les métadonnées devinées à partir d'un fichier, ou proposées par un modèle, restent marquées « non vérifiées » tant
que vous ne les avez pas confirmées.

## Recherche bibliographique

« Chercher des articles » interroge arXiv, zbMATH Open, Crossref, OpenAlex et Semantic Scholar. **Seule votre
requête est envoyée.** Un fournisseur qui ne répond pas est signalé, sans bloquer les autres. À partir d'un article :
travaux liés, citants, cités (OpenAlex).

« Liste de lecture » : à partir d'une question, un modèle choisit parmi des résultats **réellement renvoyés par les
bases** et dit pourquoi ; il ne peut pas inventer de référence (tout identifiant inconnu est rejeté et compté).

En mode *Local*, ces recherches sont refusées : elles demandent le réseau.

## Lire et annoter

Le lecteur affiche le PDF à côté du texte extrait. Surlignez, ajoutez une note en marge : les annotations sont
ancrées à la page et à la position, et retrouvables dans la recherche.

Le texte intégral de chaque source est indexé **localement**, découpé en passages avec leur page et leur section.
Pour un PDF sans couche texte (scan), une reconnaissance de caractères existe, mais les formules lues ainsi ne sont
pas fiables.

## Questions ancrées dans vos sources

Posez une question sur une source, un projet, ou une sélection : la réponse cite des **passages** précis.

- Chaque citation renvoie au passage (clic : la page s'ouvre au bon endroit).
- La citation est vérifiée par le code : le passage cité doit contenir le texte cité. Une phrase sans citation
  valide est affichée barrée ou grisée.
- Si aucun passage pertinent n'est trouvé, la réponse le dit, **sans appeler de modèle**.
- Une partie « connaissances générales », facultative, est séparée et marquée comme telle, sans citation.

Ce que la vérification garantit : le passage cité existe et contient la citation. Ce qu'elle ne garantit pas : que le
passage *justifie* la phrase. Lisez le passage pour les points importants.

Autres demandes : « Résumer » (ce que prouve l'article, ses définitions, ses dépendances), « Comparer » deux à
quatre sources.

## Ce qui part sur Internet

Les requêtes de recherche, les identifiants (DOI, arXiv…) et le téléchargement des fichiers en accès ouvert. Les
questions sur vos sources passent par le modèle choisi, avec les passages retenus : en mode *Local*, uniquement par
un modèle local. Voir [Modèles et clés](models-keys.md#ce-qui-part-et-vers-qui).
