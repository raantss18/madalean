---
id: pairing
title: Relier un téléphone, une tablette ou un autre PC
order: 30
section: start
audience: all
summary: Pas à pas pour relier un appareil à l'ordinateur hôte par un code à 6 chiffres, et pour le délier.
---

# Relier un téléphone, une tablette ou un autre PC

Un appareil relié affiche la même interface que l'ordinateur hôte et reste synchronisé avec lui : ce que vous
lancez au téléphone apparaît sur le PC, et inversement. Tout le calcul reste sur l'hôte.

Il faut trois choses :

1. l'ordinateur hôte allumé, Madalean démarré ;
2. l'hôte et l'appareil sur **votre réseau Tailscale** (voir [Tailscale](tailscale.md)) ;
3. un **code à 6 chiffres** affiché par l'hôte.

Sur l'ordinateur hôte lui-même, aucun code n'est nécessaire.

**Application ou navigateur ?**

- Les **applications Madalean** (Android, bureau Linux) se relient **une seule fois** : ensuite elles se reconnectent
  toutes seules, même après un redémarrage de l'hôte.
- Depuis un **navigateur** (iPhone, iPad, autre PC sans l'application), il faut un **code à chaque connexion** :
  l'accès dure le temps de la session, se ferme après **2 h sans activité** (réglable sur l'hôte) et au plus tard
  après **12 h**, et aussi quand l'hôte redémarre.

## Étape 1 — Mettre l'hôte sur votre réseau Tailscale (une fois)

Madalean apporte **son propre nœud Tailscale** : sur votre tailnet, l'hôte apparaît comme une machine à part,
nommée `madalean`, à l'adresse `https://madalean.tailXXXX.ts.net` (port HTTPS normal, aucun numéro de port à taper).
Il n'y a rien à installer sur l'hôte pour cela : ni Tailscale du système, ni `tailscale serve`.

La première fois, ce nœud doit être **approuvé** dans votre compte Tailscale (Madalean n'approuve jamais rien
lui-même) : ouvrez le lien de connexion Tailscale qu'il fournit, connectez-vous et acceptez la machine `madalean`.
Pour l'instant, ce lien se lit sur l'hôte, dans un terminal :

```bash
curl -s http://127.0.0.1:11500/api/net
```

(ligne `auth_url`). Une fois le nœud approuvé, la même commande indique `"state": "running"` et le nom complet de
l'hôte (`dns_name`). Le tailnet doit avoir les certificats HTTPS activés : voir
[Tailscale › Activer HTTPS](tailscale.md#activer-https).

Si vous préférez passer par le Tailscale déjà installé sur l'hôte, voir
[Tailscale › Autre possibilité](tailscale.md#autre-possibilite-le-tailscale-du-systeme).

## Étape 2 — Afficher un code sur l'hôte

Sur l'ordinateur hôte : « Réglages › Appareils », partie « Ajouter un appareil », bouton « Afficher un code ». Un
code à 6 chiffres s'affiche, valable **5 minutes**, utilisable **une seule fois**, avec un QR code.

![Réglages › Appareils : code et QR code](../img/devices-add.png)

Le champ « Adresse de cet ordinateur vue des autres appareils » se remplit tout seul quand le nœud Tailscale de
Madalean tourne (par exemple `madalean.tail1234.ts.net`). Il sert à fabriquer le QR code. Le QR code contient aussi
des adresses de secours, que l'application Android essaie si le nom ne répond pas : l'adresse IP Tailscale de l'hôte
et, si l'accès depuis le réseau local est activé, son adresse sur le réseau local (port 11502 par défaut, voir
[Tailscale › Sans Tailscale](tailscale.md#sans-tailscale)).

## Étape 3 — Sur l'appareil

### Téléphone ou tablette Android

1. Installez l'application **Tailscale** (Play Store) et connectez-vous avec **le même compte** que sur l'hôte.
2. Installez l'application **Madalean** depuis la [page d'installation](site:install) (fichier APK ; Android
   demande d'autoriser l'installation depuis votre navigateur, une fois).
3. Ouvrez Madalean et touchez « Scanner le QR code », puis visez le QR code affiché sur l'hôte : l'adresse et le code
   se remplissent tout seuls. L'application demande l'accès à l'appareil photo, seulement pour lire ce QR code.
   Sinon, « Ou saisir l'adresse et le code » permet de les taper à la main.
4. Donnez un nom à l'appareil (« Pixel de Marie ») et touchez « Appairer et ouvrir ».

![Écran de liaison sur un téléphone](../img/pair-phone.png)

### iPhone, iPad, ou tout appareil avec un navigateur

Il n'y a pas d'application iOS. Installez Tailscale (App Store), puis ouvrez dans le navigateur l'adresse de l'hôte,
par exemple `https://madalean.tail1234.ts.net`. La page « Relier cet appareil » demande le code et un nom d'appareil,
puis « Relier ». Scanner le QR code de l'hôte avec l'appareil photo ouvre directement cette page, code rempli.
**Code à saisir à chaque connexion depuis un navigateur** : à la visite suivante (ou après 2 h sans activité),
affichez un nouveau code sur l'hôte.

### Autre ordinateur Linux

Installez Tailscale, puis soit un navigateur (comme ci-dessus), soit l'application de bureau **Madalean**
(AppImage, [page d'installation](site:install)) qui garde le jeton dans le trousseau du système et se reconnecte
seule.

## Ce qui se passe au moment de la liaison

- **Application** : l'appareil envoie le code ; l'hôte lui remet un **jeton** secret (256 bits), rangé dans le
  trousseau du système, qui l'identifie ensuite. L'hôte ne garde qu'une empreinte de ce jeton, jamais le jeton
  lui-même.
- **Navigateur** : l'hôte ouvre une **session temporaire** (un cookie de session, effacé à la fermeture du
  navigateur, qu'aucune page ne peut lire) ; elle n'est jamais transformée en jeton permanent et n'est gardée qu'en
  mémoire par l'hôte.

Cinq codes faux d'affilée bloquent la liaison 10 minutes. Détails : [Sécurité](security.md).

## Délier un appareil

- Depuis l'hôte : « Réglages › Appareils », bouton « Délier » en face de l'appareil. La page montre deux listes :
  « Applications (connexion automatique) » et « Navigateurs (session temporaire) ». L'accès est coupé
  **immédiatement** : une page déjà ouverte perd aussitôt sa connexion en direct, la réponse en cours d'écriture pour
  elle est arrêtée, et elle revient à l'écran de liaison. Il en va de même quand une session de navigateur se termine
  (inactivité, limite de 12 h) et quand l'appareil se délie lui-même.
- Depuis l'appareil lui-même : « Réglages › Appareils › Délier cet appareil ». Dans l'application Android,
  « Oublier » retire aussi un serveur enregistré de l'écran de connexion.

Délier un téléphone perdu est la première chose à faire ; votre compte Tailscale permet aussi de retirer l'appareil
du réseau privé.

## Si ça ne marche pas

| Message | Que faire |
|---|---|
| « Code incorrect » | Retapez les 6 chiffres affichés sur l'hôte. |
| « Ce code a expiré » | « Nouveau code » sur l'hôte (validité 5 minutes). |
| « Trop d'essais : la liaison est bloquée N min » | Attendez, puis demandez un nouveau code. |
| L'adresse ne répond pas | Tailscale est-il connecté sur les deux appareils ? Voir [Dépannage](troubleshooting.md#lappareil-ne-joint-pas-lhote). |
