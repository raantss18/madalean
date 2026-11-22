---
id: measures
title: Mesures : ce que Madalean prouve, en combien de temps, à quel coût
order: 440
section: reference
audience: researcher
summary: Le banc d'essai intégré — miniF2F, PutnamBench et un jeu de contrôle — compte seulement les preuves qu'un Lean neuf et strict accepte, avec le temps et le coût par preuve.
---

# Mesures

Madalean se mesure lui-même. La commande `madalean bench` fait passer des énoncés formels par **la même chaîne que
l'application** (recherche dans Mathlib, tournoi de modèles gratuits, chef d'orchestre…), sans interface, et écrit
pour chaque problème : prouvé ou non, nombre d'essais, temps, jetons, coût, modèle qui a trouvé, temps de Lean.

Les résultats publiés sont sur la page « Mesures » du site (lien en bas de chaque page du site). Ils sont refaits à
chaque version.

## Ce qui compte comme « prouvé »

Une seule chose : la preuve trouvée est recompilée **à part**, par un Lean neuf, avec le verdict strict de
l'application — pas de `sorry`, pas d'axiome ajouté, seulement les axiomes standards — et elle doit démontrer
**l'énoncé donné**, pas un autre. Le mot du modèle, ou une vérification intermédiaire, ne compte jamais.

Un énoncé que le Lean de l'espace de travail n'accepte pas (le jeu a été écrit pour une autre version de Mathlib) est
compté **à part** : ce n'est pas un échec de la preuve.

## Les jeux de problèmes

| Jeu | Contenu | Licence |
|---|---|---|
| Jeu de contrôle | 20 énoncés écrits pour Madalean, de la logique à la topologie : vérifie que toute la chaîne marche | Apache-2.0 |
| miniF2F | 488 énoncés de niveau lycée et olympiades (244 « valid », 244 « test ») | MIT |
| PutnamBench | 672 énoncés du concours Putnam (1962–2025) | Apache-2.0 |

miniF2F et PutnamBench ne sont pas copiés dans Madalean : `madalean bench fetch` les télécharge depuis leur dépôt
public, à une version figée, dans un dossier de cache ; l'empreinte du contenu est contrôlée à chaque lecture.
PutnamBench demande de ne pas publier de preuves : seuls les comptes sont publiés.

## Les stratégies

| Stratégie | Ce qui tourne |
|---|---|
| `mathlib` | la recherche dans Mathlib seule, sans aucun modèle |
| `tournament` | le réglage par défaut de l'application : Mathlib d'abord, puis le tournoi de modèles gratuits |
| `conductor` | le tournoi dirigé par le chef d'orchestre |
| `single` | un seul modèle, que vous nommez |
| `goedel-local` | Goedel-Prover sur la carte graphique de la machine |

## Le coût

Par défaut, **aucun modèle payant ne peut être appelé** : le banc d'essai ne donne au moteur que les clés des
fournisseurs gratuits. Les modèles payants ne servent que si vous donnez un budget (`--paid-budget`, en dollars) ; ce
budget est un plafond ferme pour tout le passage. Le coût affiché est celui des appels payants au prix public ; les
modèles gratuits et Mathlib coûtent 0 $.

## Lancer une mesure

```
madalean bench sets
madalean bench fetch minif2f
madalean bench check minif2f --split valid --workspace lean-prover49
madalean bench run minif2f --split valid --sample 50 --seed 1 --strategy tournament --time-budget 30
```

Un passage interrompu reprend où il s'était arrêté : relancez la même commande. Le banc d'essai travaille dans son
propre dossier : il ne touche ni vos projets, ni vos réglages, ni le serveur en marche, et ne charge pas de modèle
sur la carte graphique sauf avec `goedel-local`.

## Ce que ces chiffres ne disent pas

- Un échantillon de 50 problèmes donne une estimation à une dizaine de points près.
- Les limites sont courtes (quelques minutes et quelques essais par problème) : c'est l'atelier tel qu'on s'en sert,
  pas le maximum atteignable avec des milliers d'essais.
- Les modèles en ligne changent et leurs réponses ne sont pas reproductibles à l'identique : l'ordre des problèmes
  et l'échantillon le sont, les réponses des modèles non.
- Les énoncés sont donnés en Lean : la traduction depuis le français ou l'anglais n'est pas mesurée ici.
