---
id: tailscale
title: Tailscale, le réseau privé de vos appareils
order: 40
section: start
audience: all
summary: Ce qu'est Tailscale, pourquoi Madalean l'utilise, comment l'installer, et ce qu'il ne fait pas.
---

# Tailscale, le réseau privé de vos appareils

## Ce que c'est

[Tailscale](https://tailscale.com/) relie **vos** appareils entre eux par des liaisons chiffrées (protocole
WireGuard), où qu'ils soient : même Wi-Fi, 4G, autre ville. L'ensemble forme un réseau privé, le *tailnet*. Chaque
appareil y reçoit un nom stable, par exemple `nitro.tail1234.ts.net`. Seuls les appareils connectés à **votre**
compte Tailscale font partie de ce réseau.

Madalean l'utilise pour une seule chose : que vos appareils joignent l'ordinateur hôte. Il ne se sert d'aucun
serveur de Madalean sur Internet (il n'y en a pas) et le site web de Madalean ne joue aucun rôle dans la
synchronisation.

## Ce que Madalean fait, et ne fait pas, avec Tailscale

- Madalean installe et lance **son propre nœud Tailscale**. Sur votre tailnet, l'hôte apparaît comme une machine à
  part, `madalean`, joignable en HTTPS à `https://madalean.<tailnet>.ts.net` (port HTTPS normal, sans numéro de port).
  Ce nœud est arrêté avec Madalean et n'envoie aucun journal à Tailscale.
- L'hôte n'a besoin ni du Tailscale du système ni de `tailscale serve`. S'il y en a un, Madalean n'y touche pas : les
  deux cohabitent.
- Madalean n'active **jamais Funnel**, la fonction de Tailscale qui ouvrirait l'accès à tout Internet.
- Être sur le tailnet **ne suffit pas** : chaque appareil doit en plus être relié par un code
  ([Relier un appareil](pairing.md)).

## Installer Tailscale

**Sur l'ordinateur hôte**, rien à installer : le nœud de Madalean est installé par `./install.sh`. La première fois,
il faut l'approuver dans votre compte Tailscale (voir [Relier un appareil › Étape 1](pairing.md)).

**Sur un téléphone, une tablette ou un autre ordinateur** : l'application Tailscale (App Store, Play Store, ou le
site de Tailscale pour un ordinateur), connectée au **même compte**.

Le compte Tailscale se crée avec un fournisseur d'identité (Google, Microsoft, GitHub, Apple…). Les offres et leurs
limites sont décrites sur le site de Tailscale ; un usage personnel avec quelques appareils entre en général dans
l'offre gratuite, mais vérifiez-le sur ce site.

## Activer HTTPS

Les appareils joignent l'hôte en HTTPS, avec un certificat que Tailscale émet pour le nom
`madalean.<tailnet>.ts.net`. Il faut, une fois, dans la console d'administration de Tailscale, activer **MagicDNS**
et les **certificats HTTPS** (les menus exacts sont décrits dans l'aide de Tailscale). La première connexion HTTPS
peut prendre quelques secondes, le temps que le certificat soit émis.

## Autre possibilité : le Tailscale du système

Si vous préférez utiliser le Tailscale déjà installé sur l'hôte (le service `tailscaled`, connecté à votre compte),
le script `scripts/tailscale_setup.sh` publie Madalean par lui, sur le port 10500 :
`https://nom-du-pc.<tailnet>.ts.net:10500`. Il ajoute **une seule** règle `tailscale serve`, ne touche à aucune
autre règle de la machine et n'active jamais Funnel. Il faut une fois `sudo tailscale set --operator=$USER` pour
qu'il agisse sans `sudo`. `--status` montre l'état, `--print` montre les commandes sans rien changer, `--remove`
retire la règle. Dans ce cas, tapez cette adresse (sans `https://`) dans le champ « Adresse de cet ordinateur vue des
autres appareils » de « Réglages › Appareils ».

## Sans Tailscale

« Réglages › Carnet et accès › Accès depuis le réseau local (sans Tailscale) » fait aussi écouter Madalean sur le
réseau local (« Port réseau local », 11502 par défaut ; désactivé par défaut). Les appareils doivent quand même être
reliés par un code, mais le trafic passe alors en HTTP simple, **non chiffré** : à réserver à un réseau de
confiance. Ce réglage ne se change que depuis l'hôte et prend effet au prochain démarrage de Madalean.
