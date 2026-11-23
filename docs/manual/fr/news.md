---
id: news
title: Actualités
order: 205
section: research
audience: all
summary: Suivre ce qui est nouveau en mathématiques — articles par domaine, problèmes ouverts, Lean et Mathlib, IA pour les maths — et l'envoyer vers un projet.
---

# Actualités

L'écran **Actualités** (menu du logo) rassemble ce qui est nouveau en mathématiques. Madalean va le chercher pour
vous, de temps en temps, à des adresses publiques ; tout est gardé sur l'ordinateur hôte et se lit sans Internet.

## Ce que vous y trouvez

| Rubrique | Sources |
|---|---|
| Nouveaux articles | arXiv, toutes les catégories de mathématiques et la logique informatique |
| Problèmes ouverts | les problèmes d'Erdős (changements d'état), les questions « open-problems » de MathOverflow, le blog Polymath |
| Lean et Mathlib | les versions de Lean, les derniers ajouts à Mathlib, le blog de la communauté Lean, le blog Xena |
| IA pour les maths | les articles d'arXiv sur la preuve automatique, la formalisation et le raisonnement mathématique |
| Annonces, prix et vulgarisation | l'AMS, Quanta Magazine, Images des mathématiques, le blog de Terence Tao |
| Vos flux | les adresses RSS ou Atom que vous ajoutez vous-même |

Chaque élément montre sa source, sa date, ses auteurs, son résumé et un lien vers la page d'origine, qui s'ouvre dans
le navigateur. Madalean ne garde que le titre, un extrait et le lien : le texte complet se lit sur le site d'origine.

## Trier et chercher

- **Chercher** : un mot, un auteur ; les accents ne comptent pas.
- **Domaine** : algèbre, théorie des nombres, géométrie, topologie, analyse, équations aux dérivées partielles,
  probabilités, statistique, combinatoire, logique, théorie des catégories, analyse numérique, optimisation, physique
  mathématique, histoire et enseignement. Le domaine vient de la catégorie donnée par la source, sinon des mots du
  titre et du résumé.
- **Non lus**, **Enregistrés**, **Problèmes ouverts**.
- **Mes domaines** : seulement les domaines cochés dans Réglages › Actualités.
- **Pour mes projets** : les éléments qui partagent des mots rares avec vos projets (titres, énoncés des dossiers,
  titres des notes et des sources). Les mots en commun sont affichés. Ce tri se fait sur votre ordinateur : rien de
  vos projets n'est envoyé.

Ouvrir un élément le marque comme lu. « Enregistrer » le garde sans limite de durée.

## Envoyer vers un projet

Dans un élément ouvert, quatre boutons l'envoient vers le projet choisi dans la barre du haut :

- **Ajouter aux Sources du projet** (articles arXiv) : l'article entre dans la bibliothèque du projet, comme si vous
  aviez donné son identifiant dans l'écran Sources.
- **Créer une conjecture** : le titre et le résumé deviennent l'énoncé d'une conjecture, avec le lien d'origine.
- **Créer un dossier à partir de ce problème** : un dossier est créé avec ce texte comme énoncé. Rien n'est lancé :
  relisez et corrigez l'énoncé d'abord.
- **Envoyer dans une note** : une note avec la citation, les auteurs, le lien et la date.

## Résumé en français

« Résumer en français » demande à un modèle gratuit en ligne un résumé de deux ou trois phrases. Le texte d'origine
reste toujours affiché en dessous : le résumé est une aide de lecture, pas une source. Le bouton n'apparaît que pour
les sources dont la licence le permet (arXiv, MathOverflow, Mathlib, vos propres flux) ; pour un blog, un magazine ou
une société savante, Madalean s'en tient au titre, à l'extrait et au lien. Le réglage « Résumer
automatiquement » le fait pour quelques nouveautés de vos domaines à chaque mise à jour.

Un texte venu d'Internet peut contenir des phrases écrites pour tromper un programme. Madalean le traite comme un
texte à lire, jamais comme une consigne ; s'il repère de telles phrases, il l'indique et n'envoie pas ce texte à un
modèle.

## Mise à jour

Par défaut toutes les 6 heures, tant que l'ordinateur hôte est allumé et relié à Internet. « Mettre à jour » le fait
tout de suite. Une source qui ne répond pas est réessayée plus tard, de moins en moins souvent.

En **mode Local**, Madalean ne va rien chercher : vous lisez ce qui est déjà enregistré.

Le nombre de non lus apparaît sur l'accueil (« Nouveautés ») et dans le menu. Aucun message ne s'affiche tout seul.

## Réglages › Actualités

- les domaines suivis ;
- chaque source, à activer ou arrêter, avec sa licence et ses conditions ;
- vos propres flux RSS ou Atom (une adresse en `https` d'un site public) ;
- la fréquence, la durée de conservation, les résumés automatiques, l'affichage du nombre de non lus.

## Ce qui quitte votre ordinateur

Seulement des lectures anonymes des adresses listées dans Réglages › Actualités : pas de compte, pas de clé, pas de
nom, pas d'adresse e-mail. Si vous demandez un résumé, le titre et le résumé public de l'élément sont envoyés au
modèle en ligne, et rien d'autre. Voir aussi [Sécurité et vie privée](security.md).

## Vérifier vous-même

1. Menu du logo › Actualités : la liste se remplit après « Mettre à jour » (hors mode Local).
2. Cochez « Problèmes ouverts » : il ne reste que des questions MathOverflow et des problèmes d'Erdős ouverts.
3. Passez en mode Local, puis « Mettre à jour » : le bouton est inactif et la liste reste lisible.
