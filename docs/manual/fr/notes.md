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

Chaque note montre ses **liens entrants** (les notes qui pointent vers elle). Le **graphe** du projet (bouton
« Graphe ») relie notes, dossiers et sources ; il se filtre par étiquette. Les étiquettes s'écrivent `#étiquette` dans le texte.

Renommer une note met à jour les liens `[[Ancien titre]]` des autres notes du projet.

## Lean dans les notes

Sous l'éditeur, la partie « Blocs Lean » liste chaque bloc `lean` de la note. « Tout vérifier avec Lean » les
compile tous dans l'espace du projet (« Vérifier avec Lean » sur un bloc ne vérifie que celui-là) ; chaque bloc
affiche « Lean accepte » ou « Lean refuse », avec les erreurs à la bonne ligne. « En faire un dossier » ouvre un
dossier avec l'énoncé du bloc et ajoute un lien vers lui sous le bloc.

## Journal de recherche

« Note du jour » crée (ou ouvre) la note « Journal de recherche » datée du jour, avec la liste des dossiers
travaillés ce jour-là.

## Versions et plusieurs appareils

Chaque enregistrement crée une révision ; toutes sont gardées. On peut comparer deux révisions et restaurer une
ancienne (ce qui crée une nouvelle révision : rien n'est perdu). Une note supprimée va à la corbeille.

Si la même note est modifiée sur deux appareils, les changements de lignes différentes sont fusionnés
automatiquement. Si les deux appareils ont modifié les mêmes lignes, Madalean montre les deux versions de chaque
passage en conflit et vous choisissez.

## Export

Le bouton « .md » de l'éditeur télécharge la note en Markdown.
