---
id: publish
title: Publier un projet
order: 250
section: research
audience: researcher
summary: Publier un projet vérifié en site statique sur un dépôt GitHub de votre choix, revérifié indépendamment par lake build.
---

# Publier un projet

L'écran « Publier » (menu du projet) transforme un projet en **site statique** que n'importe qui peut lire et
revérifier :

- l'article (HTML, et le PDF si vous le joignez) ;
- le **graphe des dépendances**, avec l'état de chaque résultat ;
- une page par résultat : énoncé en langage naturel, code Lean coloré, preuve rédigée, informations de vérification
  (version de Lean, révision de Mathlib, axiomes) ;
- la table de vérification et la bibliographie ;
- le **projet Lean (Lake)** complet à télécharger, et, si vous le demandez, vos calculs (Calcul).

Un résultat publié emmène avec lui tout ce dont il dépend : un résultat n'est jamais montré sans ce sur quoi il
s'appuie.

Le site est envoyé sur un dépôt GitHub **que vous choisissez**, avec une action GitHub qui relance `lake build` sur
le projet Lean publié. Le badge de vérification affiché par le site vient de cette action, indépendante de votre
ordinateur : un lecteur n'a pas à croire Madalean sur parole.

## Ce qui part, et seulement avec votre accord

1. **« Ce que vous publiez »** : cochez les résultats, les notes (aucune par défaut), « Joindre le PDF de
   l'article », « Joindre les calculs (Calcul) », et choisissez la licence du site.
2. **« Préparer la liste exacte »** : rien n'est envoyé à cette étape. L'écran liste **exactement** ce qui quittera
   l'ordinateur (« Ce qui quittera cet ordinateur ») : chaque fichier, son type, son origine et sa taille, ce qui est
   écarté, et ce qui n'est jamais publié (vos clés, vos notes privées, les PDF des articles d'autres auteurs, vos
   réglages).
3. **« Aperçu local »** construit le site sur l'ordinateur ; « Ouvrir l'aperçu » le montre avant toute publication.
4. **« Envoyer sur GitHub »** : indiquez le dépôt (`compte/nom`), cochez au besoin « Créer le dépôt s'il n'existe
   pas » (et « Dépôt privé »), puis « Publier » et confirmez par « Oui, publier ». Il faut une clé GitHub (jeton),
   enregistrée dans les réglages des clés (l'écran y mène par un lien) ; à défaut, la connexion de l'outil `gh`,
   s'il est installé sur l'hôte, est utilisée. Madalean active ensuite le site GitHub Pages du dépôt ; s'il n'y
   arrive pas, il donne le lien pour l'activer à la main.

La publication se lance depuis l'ordinateur hôte. Si la liste change entre sa préparation et l'envoi, Madalean
demande de la préparer de nouveau. Une nouvelle publication ajoute un commit au dépôt ; rien n'est envoyé si rien
n'a changé.

## Ce que montre le site

Chaque état a une couleur, une forme de bordure et un libellé écrit (jamais la couleur seule) :

| Marque | Libellé sur le site |
|---|---|
| ✓ | vérifié par Lean (preuve acceptée par Lean, et toutes ses dépendances vérifiées) |
| (✓) | prouvé, dépendances non vérifiées |
| ≔ | définition acceptée par Lean |
| ◇ | énoncé Lean accepté, sans preuve |
| … | énoncé en langage naturel seulement |
| ✕ | bloqué : dépend d'une définition non formalisée |

Un théorème non vérifié n'est jamais présenté comme théorème : il est titré « Affirmation », avec un avertissement.
Le site n'utilise ni traceur, ni police ou script externe.
