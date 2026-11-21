---
id: follow-ups
title: Demandes de suivi et versions
order: 120
section: use
audience: all
summary: Continuer la discussion sur un dossier, choisir l'étape à refaire, revenir à une version antérieure.
---

# Demandes de suivi et versions

Un dossier n'est jamais figé. Dans le fil du dossier, la zone « Une précision, une correction ? » accepte une
demande en langage courant :

- « ajoute l'hypothèse $n > 0$ »
- « et la réciproque ? »
- « une preuve plus courte »
- « explique l'étape 2 »
- « sans utiliser `nlinarith` »

`Ctrl+Entrée` envoie.

## Quelle étape est refaite ?

Le menu à côté de « Envoyer » choisit ce qui doit changer :

| Choix | Effet |
|---|---|
| *Automatique* | un modèle lit la demande et choisit l'étape ; à défaut, des mots-clés décident |
| *Énoncé* | nouvel énoncé Lean (selon la demande) → nouvelle preuve → nouvelle explication |
| *Preuve* | nouvelle preuve du même énoncé → nouvelle explication |
| *Explication* | nouvelle explication seulement |

Si la demande change l'énoncé, l'ancienne preuve ne s'applique plus : Madalean en cherche une nouvelle. Les boutons
sous la preuve (« Preuve plus simple », « Autre méthode », « Expliquer plus en détail », « Découper en lemmes ») sont
des demandes toutes faites.

## Les versions

Chaque énoncé, chaque preuve, chaque explication produit une **nouvelle version** ; rien n'est effacé. Chaque
version indique sa source (modèle, avec son nom, ou vous), la demande qui l'a produite et, pour une preuve, son
verdict Lean.

« Revenir à cette version » rend une version courante sans supprimer les autres. Revenir à une preuve ramène aussi
l'énoncé qu'elle prouve. Une preuve ne compte comme preuve du dossier que si elle prouve l'énoncé **courant**.

## Ce que l'assistant retient

- **Votre profil** (« Réglages › Profil ») : lu avant chaque traduction et chaque explication.
- **Le fil du dossier** : chaque correction s'appuie sur les versions précédentes.
- **La bibliothèque** : chaque résultat prouvé est proposé comme lemme aux preuves suivantes du même espace Lean.
- Les noms de lemmes que Lean a déjà refusés dans ce dossier ne sont plus proposés.
