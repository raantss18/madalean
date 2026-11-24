---
id: proof-graph
title: Graphe du problème, recherche raisonnée et leçons
order: 145
section: use
audience: researcher
summary: Madalean garde la mémoire de chaque problème en graphe de lemmes, cherche une preuve avec des garde-fous, explique la démonstration avec sa bibliographie et retient ses erreurs.
---

# Graphe du problème, recherche raisonnée et leçons

Chaque dossier a un **graphe du problème** : la **cible** (le théorème ou la conjecture), les **résultats connus**
(Mathlib, votre bibliothèque, la littérature, les pièces jointes) et les **lemmes à prouver**, avec ce qui a été
essayé et pourquoi. Il prolonge le [plan de preuve](proof-plans.md) : onglet « Plan », affichage « Graphe ».

## Les statuts

Chaque nœud porte une icône, un mot et un style de bordure (jamais la couleur seule) :

| Statut | Sens |
| --- | --- |
| vérifié par Lean | prouvé par Lean (verdict strict), ou dans Mathlib, ou par un certificat |
| conditionnel | cité ou fourni sans preuve Lean, ou prouvé en utilisant un tel résultat |
| à prouver | encore ouvert |
| réfuté | Lean a prouvé la négation (contre-exemple) |
| abandonné | la raison est gardée ; la piste n'est pas réessayée tant que rien n'a changé |

Une preuve qui repose sur un résultat cité mais non prouvé en Lean est **toujours** « conditionnelle, repose sur … »,
jamais « vérifiée ». Elle devient vérifiée quand Lean prouve ce résultat.

Un même sous-lemme utilisé par deux lemmes n'existe qu'une fois : il est rangé sous le premier, l'autre affiche
« utilisé aussi par … ». Deux énoncés qui ne diffèrent que par une hypothèse restent distincts ; deux énoncés qui ne
diffèrent que par les noms des variables ou des hypothèses (`n` ou `k`, `hn` ou `h`) sont le même nœud (Lean le
confirme en cas de doute). Changer l'ordre des variables donne un autre nœud.

**Liste ou dessin.** Sur un écran large, « Dessin » montre le graphe dessiné : la cible en haut, chaque lemme sous
ceux qui l'utilisent, un sous-lemme partagé dessiné une seule fois. Glisser pour déplacer, molette ou + / − pour
zoomer ; Tab parcourt les nœuds dans l'ordre de la liste et Entrée ouvre le détail. Sur un téléphone, la liste reste
la seule vue.

## La recherche raisonnée

« Recherche raisonnée » essaie de prouver la cible seule, puis découpe en lemmes quand c'est utile. Avant de
travailler sur une piste, Madalean l'évalue (« Pourquoi cette piste ? ») : déjà prouvée ailleurs, déjà abandonnée,
proche d'une piste qui a échoué, même erreur de Lean deux fois, profondeur… et, si un modèle est disponible, un court
avis du modèle, toujours marqué comme tel. Les lemmes proposés sont d'abord vérifiés par Lean (énoncés, combinaison),
et Madalean cherche un contre-exemple : d'abord en calculant l'énoncé sur de petites valeurs quand c'est possible
(entiers de 0 à 12, rationnels simples — son propre calcul exact, jamais du code écrit par un modèle), puis Lean
essaie de prouver la négation. Un contre-exemple trouvé n'est retenu que si Lean le confirme : le lemme est alors
réfuté, avec le témoin. Sinon le détail du nœud indique « Testé sur n ∈ 0..12 : aucun contre-exemple », ce qui compte
un peu dans sa viabilité.

Garde-fous : limites de temps, d'essais, de profondeur, de jetons et de dépense (jamais au-delà du plafond du chef
d'orchestre), arrêt quand rien ne progresse, refus des boucles (un lemme qui utiliserait ce qui l'utilise). À la fin,
un résumé dit pourquoi la recherche s'est arrêtée et ce qui a été essayé. « Arrêter cette piste » et « Reprendre »
sont dans le détail de chaque nœud.

## Expliquer la démonstration

« Expliquer la démonstration » construit le récit **uniquement à partir de ce qui a été enregistré** : la piste
choisie et pourquoi, les autres pistes, les lemmes et leur statut, les tactiques employées et ce que fait chacune, ce
qui a échoué, et la bibliographie (déclarations Mathlib avec lien, ouvrages cités avec leur référence vérifiée,
BibTeX). Aucun modèle n'écrit ce texte. « Expliquer ligne par ligne » montre les buts de Lean après chaque tactique.
Exports : note du projet, LaTeX avec `\cite`, BibTeX.

## Sous-dossiers

« Ouvrir comme sous-dossier » fait d'un lemme un dossier complet (son fil, son propre graphe, Calcul, notes,
certificats), rangé sous son parent : « Projet › Dossier › Lemme ». Son verdict remonte au parent (prouvé →
prouvé ; conditionnel → conditionnel). La profondeur est bornée par « Profondeur max. du découpage ». Archiver,
déplacer ou supprimer un dossier fait de même pour ses sous-dossiers (« Annuler » les ramène ensemble).

## Adapter une méthode

Sur un résultat dont la méthode est connue (sa preuve Lean, ou le passage cité), « Adapter la méthode » propose un
énoncé généralisé et les lemmes de la preuve adaptée. Ce sont des **propositions** : leurs énoncés sont vérifiés par
Lean, et seule une preuve Lean les validera.

## Ce que Madalean a appris

Réglages › « Ce que Madalean a appris » : des leçons tirées **seulement de preuves vérifiées**, quel que soit le
modèle — un nom Mathlib qui n'existe pas et celui qui marche (appliqué sans modèle puis revérifié par Lean), ce qui a
corrigé une erreur de Lean, les pistes sans issue, les stratégies qui marchent. Chaque leçon montre ses preuves et ses
compteurs ; celles qui ne servent plus disparaissent. Vous pouvez en supprimer, tout oublier, exporter ou importer
un fichier.
