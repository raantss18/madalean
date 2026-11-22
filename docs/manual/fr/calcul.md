---
id: calcul
title: Calcul (Sage et Python)
order: 205
section: research
audience: researcher
summary: Des carnets Sage ou Python dans un bac à sable hors ligne, un modèle qui écrit le code sur demande, et un clic pour transformer un résultat en conjecture, note, dossier Lean ou bloc d'article.
---

# Calcul (Sage et Python)

L'écran **Calcul** (menu du projet) contient les **carnets** du projet (« Nouveau carnet », SageMath ou Python).
Un carnet est une suite de cellules qui partagent un même noyau : les variables restent d'une cellule à l'autre. Le
fichier est un carnet Jupyter ordinaire : « Ouvrir dans JupyterLab » l'ouvre tel quel, « Télécharger (.ipynb) » en
donne une copie. Le code s'exécute sur l'ordinateur hôte dans le **même bac à sable** que les expériences de
l'atelier de conjectures : pas d'accès au réseau, pas d'accès à vos clés ni à vos fichiers personnels, temps et
sortie limités.

## Qui peut exécuter quoi

- **Vos cellules** (celles que vous tapez) s'exécutent avec **Exécuter** (ou Ctrl+Entrée, Maj+Entrée pour passer à
  la suivante). « Tout exécuter » relance le carnet entier.
- **Le code écrit par le modèle** est marqué « À relire » : il ne s'exécute qu'après **Approuver et exécuter**.
  L'accord porte sur ce code précis : s'il change, il faut le relire et l'approuver à nouveau.
- Depuis un téléphone ou une tablette reliés, vous pouvez lire et écrire les cellules ; leur exécution n'est permise
  que si l'hôte a coché « Autoriser les expériences depuis les appareils reliés » (« Réglages › Carnet et accès »,
  réglage réservé à l'hôte).

## Demander au modèle

Le bouton **+** sous la dernière cellule ajoute une cellule (une cellule vide apparaît aussi après l'exécution de
la dernière). Tapez du code Sage, ou décrivez le calcul en mots (« les racines de x^5+x^3+x+1 dans F_16 ») : la
cellule reconnaît ce que vous avez tapé et l'indique par « Code / Demande » — un clic corrige si elle se trompe.
Maj+Entrée exécute le code ou envoie la demande. Le type de la cellule (Code, Demande, Texte, Figure) se choisit dans
le petit menu en tête de cellule.

Pour une demande, le modèle écrit le code en quelques secondes ; il s'affiche pendant qu'il s'écrit, vérifié avant
d'être montré pour la version de Sage installée. « Réécrire », juste sous la demande, relance l'écriture à tout
moment ; « Approuver et exécuter » est juste sous le code. Quand le code utilise des noms définis plus haut, la
cellule le dit (« Utilise F, f des cellules précédentes »). Si l'exécution échoue, le modèle corrige automatiquement
(trois fois au plus) : chaque correction est une version de la cellule (« Revenir à la version précédente ») et reste
à approuver, sauf si l'hôte a choisi d'exécuter le code du modèle sans accord.

Sur une erreur, « Expliquer l'erreur » dit en mots simples ce qui ne va pas et propose une correction, que vous
appliquez d'un clic (elle reste à approuver). Dans « ⋯ », « Expliquer ligne par ligne » commente chaque ligne.
Les demandes qui ont fonctionné deviennent des **recettes apprises** : une demande semblable est écrite aussitôt
(« ⋯ » du carnet › « Recettes apprises » pour les voir ou les supprimer). Un calcul
ne prouve rien en général : il vérifie des cas.

## Sorties

Texte, formules (affichées comme en LaTeX) et graphiques. Une sortie devenue « Périmé » (code ou cellule au-dessus
modifiés depuis) est signalée. Chaque cellule garde les versions de son code (« Historique »).

## Utiliser un résultat

Dans « Plus d'actions » d'une cellule qui a une sortie :

| Action | Effet |
|---|---|
| Créer une conjecture | crée une conjecture du projet ; le code et sa sortie sont joints comme motivation |
| Ajouter à une note | copie le code et sa sortie dans une nouvelle note |
| Créer un dossier Lean | ouvre un dossier avec l'énoncé à prouver, prérempli depuis le résultat (à corriger si besoin) |
| Insérer dans l'article | le résultat entre dans l'article ; le code va dans la section « Calculs » en fin d'article |

Un graphique PNG de Calcul peut aussi être inséré comme figure de l'article (« Insérer › Figure… › Depuis Calcul »
dans l'éditeur d'article).

## SageMath pas encore installé

Les carnets Python fonctionnent tout de suite. SageMath s'installe à la demande (environ 1,5 Go à télécharger, près
de 5 Go sur le disque) : bouton **Installer Sage** dans un carnet Sage, sur l'ordinateur hôte. L'écran affiche
l'étape en cours et le pourcentage.
