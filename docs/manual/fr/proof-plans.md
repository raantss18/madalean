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

## Plan de preuve (guidé)

Le plan est un **arbre** : la racine est le but du dossier, chaque nœud un résultat intermédiaire avec son énoncé en
langage naturel, pourquoi il sert et, si possible, son énoncé Lean.

1. « Rédiger un plan » : le modèle propose un arbre ; vous pouvez lui donner une idée ou coller l'esquisse de preuve
   d'un article.
2. Corrigez à la main : ajoutez, supprimez, déplacez, réécrivez des nœuds. Une modification manuelle est marquée et
   n'est jamais écrasée sans votre accord (l'ancienne version reste restaurable).
3. Acceptez les nœuds retenus, puis « Lancer » : chaque nœud accepté devient un sous-dossier ; les feuilles
   partent en premier, un nœud interne est prouvé quand ses enfants le sont.
4. Un nœud échoue ? « Redécouper » le divise à son tour.

Chaque changement crée une version du plan ; si deux appareils modifient le même plan, le second reçoit un conflit
et recharge le plan à jour (les plans ne sont pas fusionnés automatiquement).
<!-- verify after integration: button labels of the plan screen (S-D) -->

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
