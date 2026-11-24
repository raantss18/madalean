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

L'écran « Article » du projet est un éditeur LaTeX visuel : le texte affiché *est* la source LaTeX (formules
rendues, encadrés de théorèmes, citations, figures), et « Source LaTeX » montre le même texte brut. À la première
ouverture, Madalean prépare l'article à partir du projet : introduction et un bloc par dossier. Le plan est à
gauche, l'« Aperçu PDF » à droite sur un grand écran ; « Compiler » produit le PDF. L'assistant (« Réécrire »,
« Raccourcir », « Formaliser »…) ne fait que des suggestions, que vous acceptez ou refusez dans le texte.

À la compilation, Madalean ajoute la bibliographie (seulement les références citées), la **table de vérification
Lean** (pour chaque résultat : nom Lean, vérifié ou non, versions de Lean et de Mathlib, axiomes) et, si vous le
demandez dans « Options avancées », une annexe avec le code Lean. Un théorème lié à un dossier dont la preuve n'est
pas vérifiée par Lean est imprimé comme affirmation, jamais comme théorème.

Sous « Plus d'actions » : « Versions » (une version automatique au plus toutes les 2 minutes d'écriture, et les
vôtres), « Télécharger le PDF », et « Overleaf… » pour envoyer le projet vers Overleaf (ou télécharger le projet en
`.zip`) puis le reprendre.

## D'un article à un blueprint

1. Ajoutez l'article à vos sources (de préférence par son identifiant arXiv : les sources LaTeX donnent un bien
   meilleur résultat que le PDF).
2. Dans le lecteur de la source, « Extraire le blueprint » : définitions, lemmes, théorèmes, avec leur numéro (« Lemme 2.3 »), leur texte, leur
   preuve, et les dépendances repérées dans les preuves (`\ref`, « par le lemme 2.3 »).
3. Les dépendances écrites en prose (« par le lemme précédent ») échappent souvent à l'extraction : une passe de
   modèle facultative propose des liens marqués **« proposé (à confirmer) »**, que vous confirmez (« Confirmer ») ou
   écartez (« Écarter »).
4. « Créer les dossiers » : chaque nœud devient un dossier relié à la source et à son emplacement dans l'article.
5. L'écran « Blueprint » colore chaque résultat selon son état : pas de dossier, énoncé en mots, énoncé Lean
   accepté, défini, prouvé (dépendances non vérifiées), vérifié (prouvé et toutes ses dépendances vérifiées),
   bloqué (utilise une définition sans énoncé Lean accepté), échec. « Ouvrir le dossier » ouvre le dossier.

Mesure honnête (trois articles arXiv courts, vérifiés à la main) : énoncés trouvés 12 sur 12 depuis le TeX comme
depuis le PDF ; preuves 10 sur 11 depuis le TeX, 8 sur 11 depuis le PDF ; dépendances écrites en prose : 2 sur 7
sans passe de modèle. Ces chiffres viennent d'un petit échantillon.

## Du blueprint au plan formel

L'onglet « Plan formel » de l'écran « Blueprint » transforme l'article en plan de travail Lean, pas à pas :

1. Cochez les théorèmes voulus (le résultat principal, par exemple). Le bouton indique combien d'énoncés compte leur
   **fermeture par dépendances** : tout ce qu'ils utilisent d'après les références explicites de l'article
   (`\ref`, « Proof of Theorem 3 », « par le lemme 2.3 » dans un PDF), et les liens proposés par un modèle seulement
   une fois que vous les avez confirmés. Une dépendance inconnue reste inconnue : rien n'est inventé.
2. « Formaliser la sélection et ses dépendances » : dépendances d'abord, chaque énoncé **cité mot pour mot** depuis
   l'article (avec les définitions qu'il utilise) part au traducteur ; Lean vérifie l'énoncé ; puis Madalean regarde
   si Mathlib (ou votre bibliothèque) le prouve déjà. Une passe s'arrête après le nombre d'énoncés choisi
   (« Énoncés par passe ») ou quand vous cliquez « Arrêter » ; relancez-la pour **reprendre** là où elle s'est
   arrêtée.
3. Quand toute la fermeture est traitée, Madalean ouvre un dossier pour le théorème principal et, dans son graphe du
   problème, un nœud par résultat utilisé : ceux de Mathlib sont vérifiés, les autres sont **conditionnels**
   (l'article les affirme, Lean ne les a pas prouvés) et chacun de ceux à prouver devient un **sous-dossier**. Rien
   n'est lancé : vous lancez les prouveurs depuis les dossiers.

Chaque résultat a un état : *prouvé (Lean)*, *dans Mathlib*, *à prouver*, *énoncé formalisé*, *non formalisé* ;
« Conditionnel : repose sur … » liste ce qui n'est pas encore prouvé. Le compteur donne les résultats du plan prouvés
ou dans Mathlib. Un clic sur un résultat montre son texte dans l'article (mot pour mot, avec sa place : numéro,
section, ligne ou page) à côté de l'énoncé Lean — une traduction par un modèle, acceptée par Lean, à relire.
« Exporter (LaTeX) » écrit un blueprint au format de `leanblueprint` (`\lean`, `\leanok`, `\mathlibok`, `\uses`),
« Exporter (HTML) » une page de synthèse. Les définitions ne sont pas encore formalisées.

## Publier

Un projet peut être publié sous forme de site statique vérifiable par tous : voir [Publier un projet](publish.md).
