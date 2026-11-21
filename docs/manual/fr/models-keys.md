---
id: models-keys
title: Modèles et clés
order: 300
section: settings
audience: all
summary: Les modes Local / Automatique / En ligne, ce qui part et vers qui, comment obtenir une clé Anthropic ou Gemini, et ce que cela coûte.
---

# Modèles et clés

Madalean fonctionne **sans aucune clé** : modèles locaux installés sur l'hôte et fournisseurs en ligne gratuits sans
compte. Une clé ajoute les modèles d'un fournisseur, souvent plus forts.

## Les trois modes

| Mode | Qui travaille | Réseau |
|---|---|---|
| *Local* | seulement les modèles de l'ordinateur hôte (Goedel-Prover, Goedel-Formalizer, Qwen3, et Ollama s'il tourne) | rien ne quitte l'hôte ; toute connexion non locale est refusée avant d'être ouverte |
| *Automatique* (défaut) | le meilleur modèle disponible pour chaque rôle, en ligne d'abord | sans réseau, quota épuisé ou erreur : bascule automatique sur les modèles locaux |
| *En ligne* | uniquement des modèles en ligne | sans réseau, le travail échoue avec un message clair |

Un projet peut être passé en « local uniquement » quel que soit le mode général. L'indicateur en haut de l'écran
(« Qui reçoit quoi ») dit à chaque instant quel modèle reçoit votre travail. Chaque texte produit par un modèle
indique son nom.

## Ce qui part, et vers qui

| Étape | Ce que reçoit le modèle |
|---|---|
| Compréhension | votre énoncé en langage courant |
| Traduction en Lean | votre énoncé et sa reformulation |
| Preuve | l'énoncé Lean, les messages d'erreur de Lean, des lemmes de Mathlib trouvés pour l'énoncé |
| Explication, preuve rédigée | l'énoncé et la preuve Lean |
| Questions sur les sources | votre question et les passages retenus de vos sources |
| Assistant du carnet | le carnet ouvert (cellules et sorties) |

Ce qui n'est **jamais** envoyé à un modèle : vos clés d'API, vos jetons d'appareils, vos autres dossiers, vos
fichiers. Une clé n'est envoyée qu'à **son** fournisseur : Madalean refuse de joindre une clé à une adresse qui n'est
pas celle de ce fournisseur.

Les fournisseurs gratuits sans compte (LLM7, OVHcloud, Kilo, Pollinations…) appliquent leurs propres conditions ;
supposez que ce que vous leur envoyez peut être conservé. Pour un travail confidentiel, utilisez le mode *Local*.
<!-- verify after integration: list of keyless providers in the shipped catalogue -->

## Ajouter une clé

« Réglages › Clés » : collez la clé, Madalean la **teste aussitôt** (« Ça marche : N modèles disponibles », ou la
raison du refus). La clé est gardée dans le trousseau de l'ordinateur hôte (sinon dans un fichier lisible par vous
seul) et ne s'affiche plus jamais. « Retirer la clé » la supprime en un clic.

![Réglages › Clés](../img/settings-keys.png)

### Clé Anthropic (Claude)

1. Ouvrez la console d'Anthropic : <https://platform.claude.com/> et créez un compte.
2. Ajoutez un moyen de paiement et achetez des crédits (facturation prépayée, à l'usage).
3. « API keys › Create key », copiez la clé (elle commence par `sk-ant-`). Elle n'est montrée qu'une fois.
4. Collez-la dans « Réglages › Clés › Anthropic ».

Conseil : fixez une **limite de dépense** mensuelle dans la console.
<!-- verify after integration: console URL and menu names at release time -->

### Clé Google Gemini

1. Ouvrez Google AI Studio : <https://aistudio.google.com/apikey> avec un compte Google.
2. « Create API key », copiez la clé.
3. Collez-la dans « Réglages › Clés › Gemini ».

L'offre gratuite de Gemini a des quotas ; quand ils sont atteints, Madalean passe au modèle suivant. Dans l'offre
gratuite, Google peut utiliser les contenus envoyés pour améliorer ses produits : lisez ses conditions avant d'y
envoyer un travail non publié.
<!-- verify after integration: Gemini free-tier data-use terms at release time -->

## Ce que cela coûte

Les fournisseurs payants facturent au nombre de *tokens* (≈ ¾ de mot) envoyés et reçus. Ordres de grandeur, prix
publics d'Anthropic en novembre 2026, par million de tokens (entrée / sortie) :

| Modèle | Entrée | Sortie |
|---|---|---|
| Claude Opus 5.5 | 4 $ | 20 $ |
| Claude Sonnet 5.5 | 2 $ | 10 $ |
| Claude Haiku 5.5 | 0,10 $ | 0,50 $ |

Une recherche de preuve en mode agent avec Claude Opus coûte typiquement de quelques centimes à 50 centimes ; un
énoncé difficile, avec beaucoup d'essais, davantage. Les limites (nombre d'étapes, durée, tokens) se règlent dans
« Réglages › Modèles ». Par défaut, un modèle payant n'est utilisé que si vous l'avez choisi pour un rôle, ou si vous
avez activé « payants d'abord ».
<!-- verify after integration: prices and the per-proof estimate (BRAIN.md: ≈ $0.05–0.50) with a real key -->

## Claude en renfort payant, avec plafonds

Avec une clé Anthropic, Claude peut entrer **en dernier** dans le tournoi d'une preuve, seulement quand les modèles
gratuits ont tous échoué (« Réglages › Modèles › Claude en renfort payant », activé par défaut quand la clé existe).
Deux plafonds, modifiables au même endroit :

- **par preuve** (1,00 $ par défaut) ;
- **par mois civil** (20 $ par défaut), pour tous les appels à Claude, y compris ceux d'un rôle où vous l'avez choisi.

Avant chaque appel, Madalean estime le coût au tarif public (taille de la demande et longueur de réponse permise) et
réduit la longueur de réponse si besoin ; si même une réponse courte dépasserait un plafond, l'appel **n'est pas
fait** et la preuve le signale. Après l'appel, le coût réel est calculé d'après l'usage renvoyé par Anthropic (jetons
d'entrée, de sortie, lus et écrits en cache) et noté dans un petit registre privé de l'hôte. Le total du mois est
affiché sous les plafonds.
<!-- verify after integration: a real Claude reinforcement round within the 1 $ cap, and the ledger total against the Anthropic console -->

## Choisir un modèle par rôle

« Réglages › Modèles » montre, pour chaque rôle (comprendre, traduire, prouver, expliquer, assistant), le classement
des modèles disponibles et la raison du classement. « Automatique » laisse le routeur choisir ; vous pouvez imposer
un modèle. Un modèle en erreur (quota, clé refusée, surcharge) est mis en pause et le suivant prend le relais.
