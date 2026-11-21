---
id: calcul
title: Calcul (Sage et Python)
order: 205
section: research
audience: researcher
summary: Des cellules Sage ou Python dans un bac à sable hors ligne, l'assistant à côté, et un clic pour transformer un résultat en conjecture, note, dossier Lean ou bloc d'article.
---

# Calcul (Sage et Python)

L'écran **Calcul** (menu du projet) est une feuille de calcul par projet : une suite de cellules SageMath ou
Python, exécutées sur l'ordinateur hôte dans le **même bac à sable** que les expériences de l'atelier de
conjectures : pas d'accès au réseau, pas d'accès à vos clés ni à vos fichiers personnels, temps et sortie limités.
Les variables restent d'une cellule à l'autre (un noyau par projet).

## Qui peut exécuter quoi

- **Vos cellules** (celles que vous tapez) s'exécutent quand vous cliquez sur **Exécuter** (ou Ctrl+Entrée).
- **Les cellules de l'assistant** sont marquées « À relire » : elles ne s'exécutent qu'après **Approuver ce code**.
  L'accord porte sur ce code précis : si vous ou l'assistant le modifiez, il faut le relire et l'approuver à nouveau.
- Depuis un téléphone ou une tablette appairés, vous pouvez lire et écrire les cellules ; leur exécution n'est
  permise que si l'hôte a activé « expériences depuis les appareils » (réglage réservé à l'hôte).

## L'assistant

À droite (en haut sur téléphone), décrivez le calcul voulu : l'assistant **écrit une cellule**. Sous chaque cellule,
**Corriger** propose une version réparée après une erreur, **Expliquer** commente le code et sa sortie. Un calcul
ne prouve rien en général : il vérifie des cas.

## Sorties

Texte, formules (avec `tex(x)`, affichées par KaTeX) et graphiques (PNG ou SVG, nettoyés avant affichage). Chaque
cellule garde ses dernières exécutions et les versions de son code (**Historique**).

## Utiliser un résultat

Sous une sortie réussie :

| Bouton | Effet |
|---|---|
| → Conjecture | crée une conjecture du projet ; le calcul est joint comme motivation |
| → Note | copie le code et sa sortie dans une note (étiquette « calcul ») |
| → Dossier Lean | ouvre un dossier avec l'énoncé que vous écrivez ; rien ne démarre avant que vous l'ouvriez |
| → Article | ajoute la formule ou la sortie comme bloc de l'article du projet |

Les graphiques ne sont pas encore copiés dans l'export PDF de l'article.

## SageMath pas encore installé

Les cellules Python fonctionnent tout de suite. SageMath (environ 2 Go) s'installe à la demande : bouton
**Installer SageMath** sur l'hôte, avec la progression affichée.
<!-- verify after integration: Sage on-demand install progress from the Calcul screen on a machine without Sage -->
