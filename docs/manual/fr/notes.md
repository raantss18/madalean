---
id: notes
title: Notes
order: 230
section: research
audience: all
summary: Notes liées en Markdown, LaTeX et Lean ; liens, rétroliens, graphe, versions et édition sur plusieurs appareils.
---

# Notes

Les notes sont propres à Madalean (ce n'est pas un coffre Obsidian) et rangées par projet. On y écrit en Markdown,
avec des formules `$…$` et `$$…$$` et des blocs de code Lean.

## Liens

| Écriture | Cible |
|---|---|
| `[[Titre]]`, `[[Titre\|texte affiché]]` | une note du même projet (titre sans distinction de casse) |
| `[[dossier:Titre]]` ou `[[dossier:ID]]` | un dossier (théorème, conjecture, lemme…) |
| `[[@clé]]`, `[[@clé#p12]]` | une source, éventuellement à une page |
| `[[passage:ID]]` | un passage précis d'une source |
| `[[lib:Nom]]` | un résultat de la bibliothèque (nom Lean) |

Chaque note montre ses **rétroliens** (les notes qui pointent vers elle). Le **graphe** du projet relie notes,
dossiers et sources ; il se filtre par étiquette. Les étiquettes s'écrivent `#étiquette` dans le texte.

Renommer une note met à jour les liens `[[Ancien titre]]` des autres notes du projet.

## Lean dans les notes

« Vérifier avec Lean » compile chaque bloc `lean` de la note dans l'espace du projet et affiche les erreurs à la
bonne ligne. « Créer un dossier » à partir d'un bloc qui contient un théorème ouvre un dossier avec cet énoncé (ou,
à partir d'un paragraphe, un dossier dont c'est le problème) et ajoute un lien vers lui sous le bloc.
<!-- verify after integration: button labels in the notes editor (S-D) -->

## Journal de recherche

« Note du jour » crée (ou ouvre) la note datée du jour, avec la liste des dossiers travaillés ce jour-là.

## Versions et plusieurs appareils

Chaque enregistrement crée une révision ; toutes sont gardées. On peut comparer deux révisions et restaurer une
ancienne (ce qui crée une nouvelle révision : rien n'est perdu). Une note supprimée va à la corbeille.

Si la même note est modifiée sur deux appareils, les changements de lignes différentes sont fusionnés
automatiquement. Si les deux appareils ont modifié les mêmes lignes, Madalean montre les deux versions de chaque
passage en conflit et vous choisissez.

## Pièces jointes et export

Images (PNG, JPEG, GIF, WebP) et PDF jusqu'à 10 Mo. Export d'une note ou de tout le carnet du projet en Markdown,
HTML ou PDF.
