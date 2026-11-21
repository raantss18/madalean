---
id: proof-plans
title: Plans de preuve et lemmes
order: 140
section: use
audience: researcher
summary: Découper un résultat en lemmes prouvés en parallèle, admettre provisoirement, et ce que « prouvé modulo » veut dire.
---

# Plans de preuve et lemmes

Un énoncé trop gros pour une preuve d'un seul tenant se découpe. Madalean propose deux outils.

## Découper en lemmes (rapide)

« Découper en lemmes » sur un dossier : un modèle propose jusqu'à quatre lemmes en Lean (ou vous les écrivez, un par
paragraphe). Chaque lemme devient un **sous-dossier** lancé aussitôt, en parallèle. Quand tous sont terminés et
qu'au moins un est prouvé, le dossier parent est relancé automatiquement avec les lemmes prouvés à sa disposition.

## Plan de preuve en carte mentale (la voie principale)

Onglet « Plan » d'un dossier (aussi depuis le fil et après un échec de preuve). Un seul chemin :

1. **« Découper ce théorème »** (une piste pour l'IA est facultative). Le modèle propose 2 à 6 lemmes, de préférence
   indépendants, avec pour chacun son énoncé en mots, son énoncé Lean et pourquoi il aide, plus la **combinaison** :
   la preuve Lean du théorème à partir des lemmes. Il garde jusqu'à deux **autres pistes** (stratégies différentes),
   en pointillé sur la carte.
2. Avant de vous montrer le plan, **Lean vérifie** que chaque énoncé compile et que le théorème découle des lemmes ;
   sinon le plan est redemandé une fois avec les erreurs de Lean. Une combinaison non vérifiée est marquée
   « à vérifier ». Un lemme fermé par une tactique simple (`simp`, `omega`, `exact?`…) est **évident** : prouvé
   tout de suite, jamais redécoupé. Un lemme qui redit le théorème lui-même est **refusé** (garde-fou contre les
   boucles).
3. Relisez, modifiez si besoin (tout nœud se modifie à la main, chaque changement est une version), puis
   **« Valider le plan »** et **« Prouver le plan »** : chaque lemme devient un sous-dossier prouvé automatiquement
   (Mathlib d'abord, puis le tournoi de modèles) ; quand tous les lemmes d'un nœud sont prouvés, la combinaison est
   compilée avec les vraies preuves, verdict strict.
4. Madalean ne revient vers vous que si un lemme **échoue**, et propose dans l'ordre : une **autre piste**, le
   **redécouper** un niveau plus bas, ou **laisser un trou** (`sorry`).

En haut, une ligne « où en est-on » dit ce qu'il reste à faire. Chaque nœud a un état écrit (à valider, en cours,
prouvé, échoué, piste abandonnée, trou) et un chemin depuis le théorème. Limites : 3 niveaux de découpage
(réglable), 6 lemmes par piste, 2 autres pistes, 30 nœuds par plan, et une durée totale (Réglages › Modèles ›
avancé). Sur téléphone, la liste repliable est la vue principale, la carte est à un appui.

## Admettre provisoirement

Un nœud dont l'énoncé Lean est accepté peut être marqué « admis pour l'instant ». La preuve du parent peut alors
s'appuyer dessus : Lean compile le parent avec le lemme admis écrit `sorry`.

Le résultat est **prouvé modulo** les lemmes admis. Ce n'est **pas** une preuve vérifiée :

- il n'est pas enregistré comme preuve du dossier, qui reste « non prouvé » ;
- les axiomes listés contiennent `sorryAx`, la trace Lean d'un `sorry` ;
- le plan affiche « prouvé modulo N lemmes admis » avec leurs noms.

Quand chaque lemme admis reçoit ensuite une vraie preuve, Madalean remplace les `sorry` par les vrais lemmes et
revérifie le parent avec le verdict strict. Alors seulement le dossier est prouvé.

## Bon usage

- Énoncez les lemmes en Lean dès que possible : un nœud sans énoncé Lean accepté ne peut être ni prouvé ni admis.
- Préférez des lemmes **généraux** et courts ; ils entrent dans la bibliothèque et resservent.
- Un lemme refusé plusieurs fois est souvent mal énoncé (hypothèse manquante) plutôt que difficile : relisez-le
  comme dans [Lire un énoncé Lean](reading-lean.md).
