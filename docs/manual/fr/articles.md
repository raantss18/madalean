---
id: articles
title: Bibliographie, article et blueprint
order: 220
section: research
audience: researcher
summary: Citer dans les preuves, rédiger un article à partir d'un projet, transformer un article en blueprint de dossiers Lean, et ce qui est fiable.
---

# Bibliographie, article et blueprint

## Ce qui est fiable, et ce qui ne l'est pas

| Fonction | Fiabilité | Comment |
|---|---|---|
| Bibliographie dans les preuves et les exports | Élevée | Un fichier BibTeX par projet. Ajout par DOI, arXiv, zbMATH, BibTeX collé, ou depuis la bibliographie de Mathlib. Un modèle ne peut citer que des clés existantes : une référence inventée est retirée par le code, jamais imprimée. |
| Lean → article | Élevée pour la structure, dépend du modèle pour la prose | Projet → article LaTeX (amsart) : résumé, sections, chaque dossier en théorème + preuve rédigée, annexe Lean facultative, bibliographie, tableau de vérification. Un énoncé non prouvé est composé comme conjecture ou affirmation, marqué — jamais comme théorème. |
| Article → énoncés structurés | Élevée depuis les sources LaTeX (arXiv), moyenne depuis un PDF | Sources arXiv d'abord ; PDF par sa couche texte, et un modèle qui lit les PDF quand une clé le permet ; les formules d'un PDF scanné ne sont pas fiables sans relecture. Résultat : un **blueprint**, un dossier par définition, lemme ou théorème, avec le texte d'origine, sa place dans l'article et ses dépendances. |
| Article → énoncés Lean | Moyenne (niveau manuel, master), faible (recherche avec des objets absents de Mathlib) | Chaque nœud passe par compréhension → traduction avec recherche de lemmes ; les définitions manquantes sont détectées et deviennent des nœuds « à définir ». Toujours relu par vous : le texte de l'article est affiché à côté de l'énoncé Lean. |
| Article → preuves Lean | Faible à moyenne | La preuve de l'article est donnée au prouveur comme indice. Les lemmes élémentaires sont souvent prouvés, les résultats profonds rarement. Le graphe montre honnêtement ce qui est prouvé, seulement énoncé, ou bloqué. |

**Aucun résultat n'est présenté comme vérifié si Lean n'a pas accepté sa preuve et celles de toutes ses
dépendances.**

## Citer

Dans tout texte (énoncé, preuve rédigée, explication, note, section d'article), une citation s'écrit avec la clé
BibTeX : `[@hardy-wright]`, `[@hardy-wright, Thm 2.1]`, `[voir @a, p. 3; @b]`. L'autocomplétion propose les clés du
projet. Les exports n'impriment que les références citées : PDF avec biblatex et biber s'ils sont installés, sinon
BibTeX ; le `.zip` contient `refs.bib`.

## Rédiger l'article
<!-- verify after integration: button and screen names of the research screens (S-D) -->

« Rédiger l'article » assemble un article à partir du projet : titre, auteurs, résumé, sections, un bloc par
dossier. Chaque bloc est un brouillon modifiable et versionné. Le tableau de vérification indique, pour chaque
résultat : nom Lean, état (vérifié, énoncé accepté, non), version de Lean, révision de Mathlib, axiomes.
Sortie : PDF, `.tex`, `.md`, et un `.zip` avec les fichiers Lean des résultats vérifiés.

## D'un article à un blueprint

1. Ajoutez l'article à vos sources (de préférence par son identifiant arXiv : les sources LaTeX donnent un bien
   meilleur résultat que le PDF).
2. « Extraire le blueprint » : définitions, lemmes, théorèmes, avec leur numéro (« Lemme 2.3 »), leur texte, leur
   preuve, et les dépendances repérées dans les preuves (`\ref`, « par le lemme 2.3 »).
3. Les dépendances écrites en prose (« par le lemme précédent ») échappent souvent à l'extraction : une passe de
   modèle facultative propose des arêtes **marquées « proposées »**, que vous acceptez ou rejetez.
4. Créez les dossiers : chaque nœud devient un dossier relié à la source et à son emplacement dans l'article.
5. Le **graphe du blueprint** colore chaque nœud selon son état : non créé, énoncé, énoncé Lean accepté, défini,
   prouvé, vérifié (prouvé et toutes ses dépendances vérifiées), bloqué (utilise une définition sans énoncé Lean
   accepté). Un clic ouvre le dossier.

Mesure honnête (trois articles arXiv courts, vérifiés à la main) : énoncés trouvés 12 sur 12 depuis le TeX comme
depuis le PDF ; preuves 10 sur 11 depuis le TeX, 8 sur 11 depuis le PDF ; dépendances écrites en prose : 2 sur 7
sans passe de modèle. Ces chiffres viennent d'un petit échantillon.

## Publier

Un projet peut être publié sous forme de site statique vérifiable par tous : voir [Publier un projet](publish.md).
